"""Video poster frames only; duplicate verification lives in video_match.py."""
import hashlib
import os
import threading
from pathlib import Path
from database import BASE

CACHE=BASE/'cache'/'thumbnails'/'videos'
CACHE.mkdir(parents=True,exist_ok=True)


def cache_path(path,size):
    p=Path(path)
    meta=p.stat()
    key=hashlib.sha256(f'{p}|{meta.st_size}|{meta.st_mtime_ns}|{size}|video1'.encode('utf-8')).hexdigest()
    return CACHE/(key+'.jpg')


def details(path,size=800):
    result={'cache':None,'dimensions':None,'date':None,'duration':None}
    temp=None
    try:
        import av
        destination=cache_path(path,size)
        with av.open(str(path),mode='r') as container:
            if not container.streams.video:
                return result
            stream=container.streams.video[0]
            stream.codec_context.thread_count=1
            width,height=stream.codec_context.width,stream.codec_context.height
            result['dimensions']=(width,height) if width and height else None
            if stream.duration is not None and stream.time_base is not None:
                result['duration']=max(0,float(stream.duration*stream.time_base))
            elif container.duration is not None:
                result['duration']=max(0,float(container.duration)/av.time_base)
            if destination.is_file():
                result['cache']=str(destination)
                return result
            # Only a poster frame, never load the whole video into memory.
            for index,packet in enumerate(container.demux(stream)):
                if index>=200:
                    break
                frames=packet.decode()
                if not frames:
                    continue
                frame=frames[0]
                scale=min(1,size/max(frame.width,frame.height))
                image=frame.to_image(width=max(1,int(frame.width*scale)),height=max(1,int(frame.height*scale)))
                temp=destination.with_name(destination.stem+f'_{os.getpid()}_{threading.get_ident()}.tmp')
                image.save(temp,'JPEG',quality=82)
                image.close()
                os.replace(temp,destination)
                result['cache']=str(destination)
                break
    except Exception:
        # Codec failures or corrupt containers must not prevent SHA-256 scanning.
        pass
    finally:
        if temp:
            temp.unlink(missing_ok=True)
    return result


def thumbnail(path,size=480):
    try:
        cached=cache_path(path,size)
        if cached.is_file():
            return str(cached)
    except OSError:
        return None
    return details(path,size)['cache']
