"""Probe the CLI's Windows installation lock without following reparse points."""

from __future__ import annotations

import ctypes
import os
import stat
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from pathlib import Path

_READ_WRITE = 0xC0000000
_SHARE_READ_WRITE = 0x00000003
_OPEN_EXISTING = 3
_OPEN_REPARSE_POINT = 0x00200000


class _NativeFunction(Protocol):
    argtypes: tuple[type[object], ...]
    restype: type[object]

    def __call__(self, *args: object) -> int | None: ...


class _Kernel32(Protocol):
    CreateFileW: _NativeFunction
    CloseHandle: _NativeFunction


class _LoadLibrary(Protocol):
    def __call__(self, name: str) -> _Kernel32: ...


def _open_windows_lock(path: Path) -> int | None:
    import msvcrt

    load = cast("_LoadLibrary", vars(ctypes)["WinDLL"])
    kernel = load("kernel32")
    create = kernel.CreateFileW
    create.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    create.restype = ctypes.c_void_p
    # Omitting delete sharing prevents the name from being replaced while the lock is held.
    handle = create(
        str(path), _READ_WRITE, _SHARE_READ_WRITE, None, _OPEN_EXISTING, _OPEN_REPARSE_POINT, None
    )
    if handle is None or handle == ctypes.c_void_p(-1).value:
        return None
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY | os.O_NOINHERIT)
    except OSError:
        close = kernel.CloseHandle
        close.argtypes = (ctypes.c_void_p,)
        close.restype = ctypes.c_int
        _ = close(handle)
        raise


def _valid_lock(info: os.stat_result) -> bool:
    return (
        stat.S_ISREG(info.st_mode)
        and info.st_ino != 0
        and info.st_nlink == 1
        and info.st_size == 0
        and not info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        and info.st_reparse_tag == 0
    )


def inactive_windows_cli_lock(path: Path) -> bool:
    """Require an unchanged regular-file handle plus the exclusive byte-zero lock."""
    import msvcrt

    try:
        if path.parent.resolve() != path.parent:
            return False
        before = path.lstat()
        if not _valid_lock(before):
            return False
        descriptor = _open_windows_lock(path)
        if descriptor is None:
            return False
        try:
            opened = os.fstat(descriptor)
            if not _valid_lock(opened) or not os.path.samestat(before, opened):
                return False
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            try:
                after = path.lstat()
                return (
                    path.parent.resolve() == path.parent
                    and _valid_lock(after)
                    and os.path.samestat(opened, after)
                )
            finally:
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(descriptor)
    except (OSError, RuntimeError):
        return False
