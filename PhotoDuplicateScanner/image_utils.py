import hashlib
import io
from pathlib import Path
from database import BASE
from PIL import Image, ImageOps, UnidentifiedImageError
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

CACHE=BASE/'cache'/'thumbnails'
CACHE.mkdir(parents=True,exist_ok=True)


def thumbnail(path, size=480):
    try:
        p=Path(path)
        st=p.stat()
        key=hashlib.sha256(f'{p}|{st.st_size}|{st.st_mtime_ns}|{size}'.encode('utf-8')).hexdigest()
        dest=CACHE/(key+'.jpg')
        if dest.is_file(): return str(dest)
        with Image.open(p) as im:
            im=ImageOps.exif_transpose(im)
            im.thumbnail((size,size))
            if im.mode!='RGB': im=im.convert('RGB')
            im.save(dest, 'JPEG',quality=82)
        return str(dest)
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):
        return None
