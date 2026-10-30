"""Full decoded video/audio comparison, with strict playback information.

Descriptive tags (title, creation date, encoder name) are ignored. All streams,
timing, rotation, colour and audio layout are retained. No sampled-frame or
perceptual matching is used. Unsupported streams retain whole-file matching.
"""
import hashlib
import json
import os
import stat
from fractions import Fraction
import av


class UnsupportedVideo(ValueError):
    pass


def _value(value):
    return getattr(value,'value',value)


def _add(digest,value):
    data=json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode('utf-8')
    digest.update(len(data).to_bytes(8,'big'));digest.update(data)


def stable_video_digest(path,stopped=None):
    before=os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400:
        raise ValueError('Links/reparse points cannot be compared as video content.')
    fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    with open(path,'rb') as source:
        opened=os.fstat(source.fileno())
        if fields(before)!=fields(opened):raise ValueError('Video changed before verification.')
        with av.open(source,mode='r') as container:
            streams=list(container.streams)
            if not any(s.type=='video' for s in streams):raise UnsupportedVideo('No video stream: exact-file matching only.')
            if any(s.type not in ('video','audio','subtitle') for s in streams):
                raise UnsupportedVideo('Unsupported auxiliary stream: exact-file matching only.')
            origin=Fraction(container.start_time or 0,av.time_base)
            hashes={};counts={};ends={}
            for s in streams:
                context=s.codec_context
                if context is None:raise UnsupportedVideo('Unsupported video stream.')
                context.thread_count=1
                context.options={**context.options,'err_detect':'explode'}
                digest=hashlib.sha256(b'video-stream-v1\0')
                _add(digest,dict(type=s.type,codec=context.name,extra=hashlib.sha256(context.extradata or b'').hexdigest(),
                    disposition=_value(s.disposition),language=s.metadata.get('language','und'),rotate=s.metadata.get('rotate'),
                    aspect=getattr(s,'sample_aspect_ratio',None),
                    colour=[_value(getattr(context,k,None)) for k in ('color_range','color_primaries','color_trc','colorspace','field_order')]))
                hashes[s.index]=digest;counts[s.index]=0
            for packet in container.demux():
                if stopped and stopped():return None,fields(opened)
                if packet.is_corrupt:raise ValueError('Corrupt media packet; content comparison skipped.')
                stream=packet.stream;digest=hashes[stream.index]
                if stream.type=='subtitle':
                    if not packet.size:continue
                    if packet.pts is None:raise UnsupportedVideo('Subtitle timing is unavailable.')
                    _add(digest,[str(packet.pts*packet.time_base-origin),str(packet.duration*packet.time_base),packet.size])
                    digest.update(bytes(packet));counts[stream.index]+=1
                    continue
                for frame in packet.decode():
                    if stopped and stopped():return None,fields(opened)
                    if frame.pts is None or frame.time_base is None:raise UnsupportedVideo('Frame timing is unavailable.')
                    timestamp=Fraction(frame.pts)*frame.time_base-origin
                    _add(digest,dict(pts=str(timestamp),duration=str(getattr(frame,'duration',0)*frame.time_base)))
                    if getattr(frame,'is_corrupt',False):raise ValueError('Corrupt media frame; content comparison skipped.')
                    # Preserve every decoded side-data payload, including
                    # embedded captions, stereo/HDR/Dolby Vision information,
                    # audio trim, replay gain and downmix instructions.
                    for side in frame.side_data.values():
                        payload=bytes(side)
                        _add(digest,[side.type.name,len(payload)]);digest.update(payload)
                    if stream.type=='video':
                        if frame.width*frame.height>40_000_000:
                            raise UnsupportedVideo('Oversize video frame: exact-file matching only.')
                        if getattr(frame,'is_corrupt',False):raise ValueError('Corrupt video frame; content comparison skipped.')
                        _add(digest,[frame.width,frame.height,frame.rotation,frame.format.name])
                        # Hash native component values, preserving 10/12/16-bit
                        # video. Never include uninitialised stride padding.
                        for index,plane in enumerate(frame.planes):
                            components=[c for c in frame.format.components if c.plane==index]
                            if not components or any(c.bits not in (8,9,10,12,14,16,32) for c in components):
                                raise UnsupportedVideo('Unsupported packed video format: exact-file matching only.')
                            width=sum(c.width*((c.bits+7)//8) for c in components)
                            if width>plane.line_size:raise UnsupportedVideo('Unsupported video plane layout.')
                            data=memoryview(plane)
                            for y in range(plane.height):digest.update(data[y*plane.line_size:y*plane.line_size+width])
                    else:
                        channels=len(frame.layout.channels)
                        _add(digest,[frame.format.name,frame.layout.name,frame.sample_rate,frame.samples])
                        needed=frame.samples*frame.format.bytes*(1 if frame.format.is_planar else channels)
                        for plane in frame.planes:digest.update(memoryview(plane)[:needed])
                    counts[stream.index]+=1
            for s in streams:
                if not counts[s.index]:raise UnsupportedVideo('Empty stream: exact-file matching only.')
                if s.type=='video' and s.frames and counts[s.index]!=s.frames:
                    raise ValueError('Video frame count is incomplete; content comparison skipped.')
            result=hashlib.sha256(b'video-content-v1\0')
            # Stream order is significant: default audio/subtitle playback must match.
            for s in streams:
                _add(result,[s.type,counts[s.index]]);result.update(hashes[s.index].digest())
        after=os.fstat(source.fileno())
    current=os.lstat(path)
    if fields(before)!=fields(after) or fields(after)!=fields(current) or before.st_ctime_ns!=current.st_ctime_ns or opened.st_ctime_ns!=after.st_ctime_ns:
        raise ValueError('Video changed during verification. Scan again.')
    return result.hexdigest(),fields(current)
