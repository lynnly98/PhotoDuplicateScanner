"""Exact decoded photo pixels, with orientation and colour information preserved.

This is deliberately not a perceptual/similarity hash. Decode one static image
at a time; never treat resized, animated or unsupported high-bit-depth input as
an approximate match. Metadata differences are not written back to originals.
"""
import hashlib
import json
import os
import stat
from PIL import Image, ImageOps
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

MAX_PIXELS = 40_000_000


class UnsupportedPhoto(ValueError):
    pass


def match_column(kind='exact', media_type='photo'):
    if kind=='auto':return 'match_key'
    if kind=='similar' and media_type=='photo':return 'review_key'
    if kind=='video' and media_type=='video':return 'video_sha256'
    if kind=='exact': return 'sha256'
    if kind=='pixels' and media_type=='photo': return 'image_sha256'
    raise ValueError('Invalid duplicate match type')


def stable_image_digest(path, stopped=None):
    before=os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400:
        raise ValueError('Links and reparse points cannot be compared as photo pixels.')
    fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    with open(path,'rb') as source:
        opened=os.fstat(source.fileno())
        if fields(before)!=fields(opened):raise ValueError('Photo changed before verification.')
        with Image.open(source) as image:
            if getattr(image,'n_frames',1)!=1 or getattr(image,'is_animated',False):
                raise UnsupportedPhoto('Animated or multi-page image: exact-file matching only.')
            if image.width*image.height>MAX_PIXELS:
                raise UnsupportedPhoto('Photo exceeds the 40-megapixel pixel-check limit; exact-file matching remains available.')
            if image.mode not in ('RGB','RGBA','L','LA','P') or image.info.get('bit_depth',8)>8:
                raise UnsupportedPhoto('Unsupported colour mode/bit depth: exact-file matching only.')
            # Include display-relevant colour information. Camera notes, dates,
            # descriptions and other EXIF text do not enter the comparison.
            exif=image.getexif()
            nested=exif.get_ifd(34665) if 34665 in exif else {}
            colour={'gamma':image.info.get('gamma'),'srgb':image.info.get('srgb'),
                    'chromaticity':image.info.get('chromaticity'),
                    'exif_colour_space':nested.get(40961)}
            profile=image.info.get('icc_profile') or b''
            if isinstance(profile,str):profile=profile.encode('utf-8')
            digest=hashlib.sha256(b'photo-rgba-v1\0')
            digest.update(hashlib.sha256(profile).digest())
            digest.update(json.dumps(colour,sort_keys=True).encode('utf-8'))
            with ImageOps.exif_transpose(image) as oriented, oriented.convert('RGBA') as rgba:
                digest.update(str(rgba.size).encode('ascii')+b'\0')
                for y in range(0,rgba.height,32):
                    if stopped and stopped():return None,fields(opened)
                    with rgba.crop((0,y,rgba.width,min(y+32,rgba.height))) as strip:
                        digest.update(strip.tobytes())
        after=os.fstat(source.fileno())
    current=os.lstat(path)
    if (fields(before)!=fields(after) or fields(after)!=fields(current) or
        before.st_ctime_ns!=current.st_ctime_ns or opened.st_ctime_ns!=after.st_ctime_ns):
        raise ValueError('Photo changed during verification. Scan again.')
    return digest.hexdigest(),fields(current)


def refresh_match_keys(c):
    """One key per raw-identical family, so no file appears in two groups."""
    c.execute('CREATE TEMP TABLE IF NOT EXISTS media_key_map(media_type TEXT,sha256 TEXT,key TEXT,PRIMARY KEY(media_type,sha256))')
    c.execute('DELETE FROM media_key_map')
    c.execute("""INSERT INTO media_key_map SELECT media_type,sha256,media_type||':'||CASE
        WHEN media_type='photo' AND max(image_sha256) IS NOT NULL THEN 'pixels:'||max(image_sha256)
        WHEN media_type='video' AND max(video_sha256) IS NOT NULL THEN 'video:'||max(video_sha256)
        ELSE 'raw:'||sha256 END FROM photos WHERE active=1 AND sha256 IS NOT NULL GROUP BY media_type,sha256""")
    c.execute("""UPDATE photos SET match_key=(SELECT key FROM media_key_map m WHERE m.media_type=photos.media_type AND m.sha256=photos.sha256) WHERE active=1""")


def verify_matching_content(path,keeper,raw_digest,keeper_digest,key,fingerprint,keeper_fingerprint):
    """Whole-file equality is always valid; otherwise verify complete content."""
    if raw_digest==keeper_digest:return
    parts=key.split(':',2) if key else []
    if len(parts)!=3:raise ValueError('No verified matching content. Scan again.')
    if parts[1]=='pixels':function=stable_image_digest
    elif parts[1]=='video':
        from video_match import stable_video_digest
        function=stable_video_digest
    else:raise ValueError('No verified identical copy. Scan again.')
    left,meta=function(path);right,other_meta=function(keeper)
    if left!=parts[2] or right!=left or meta!=fingerprint or other_meta!=keeper_fingerprint:
        raise ValueError('Media content changed since scanning. Scan again.')
