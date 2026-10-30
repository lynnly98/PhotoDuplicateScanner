"""Extension-based classification; exact matches still require full SHA-256."""
from pathlib import Path

PHOTO_EXTS = {'.jpg','.jpeg','.png','.webp','.heic','.heif','.bmp','.tif','.tiff','.gif','.avif','.jfif'}
VIDEO_EXTS = {'.mp4','.mov','.m4v','.avi','.mkv','.wmv','.webm','.mpg','.mpeg','.mts','.m2ts','.3gp','.3g2','.ts','.vob'}
SCAN_MODES = ('photos','videos','both')


def classify(path):
    extension = Path(path).suffix.lower()
    return 'video' if extension in VIDEO_EXTS else ('photo' if extension in PHOTO_EXTS else None)


def types_for(mode):
    if mode not in SCAN_MODES:
        raise ValueError('Invalid scan type')
    return ('photo','video') if mode=='both' else (('photo',) if mode=='photos' else ('video',))


def type_sql(mode):
    # Only constant values above may enter SQL, never client-supplied text.
    return 'media_type IN ('+','.join(repr(t) for t in types_for(mode))+')'
