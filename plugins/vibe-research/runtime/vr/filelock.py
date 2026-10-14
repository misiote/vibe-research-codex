"""Small cross-platform exclusive lock adapter for one-byte lock files."""
import os

LOCK_EX = 2
LOCK_NB = 4
LOCK_UN = 8

if os.name != "nt":
    import fcntl as _native

    def flock(handle, operation):
        return _native.flock(handle, operation)
else:
    import errno
    import msvcrt

    def _prepare(handle):
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write("\0" if "b" not in handle.mode else b"\0")
            handle.flush()
        handle.seek(0)

    def flock(handle, operation):
        _prepare(handle)
        if operation & LOCK_UN:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        blocking = not bool(operation & LOCK_NB)
        mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
        try:
            msvcrt.locking(handle.fileno(), mode, 1)
        except OSError as exc:
            if not blocking and exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise BlockingIOError(exc.errno, "lock is held") from exc
            raise
