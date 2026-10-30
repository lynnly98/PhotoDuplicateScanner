"""One process at a time may scan or recycle photos."""
from contextlib import contextmanager
from database import DATA


@contextmanager
def operation_lock():
    import msvcrt
    handle = (DATA / 'operation.lock').open('a+b')
    handle.seek(0, 2)
    if not handle.tell():
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        raise RuntimeError('Another scan or recycle operation is running. Please wait.')
    try:
        yield
    finally:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()
