"""Identity and cleanup for individual pdomain-installed executable files."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdomain_ops.suite.components import Component, ComponentRegistry


def install_staged_uv(
    registry: ComponentRegistry, app: str, staged: Path, destination: Path
) -> Component | None:
    """Publish a private uv bootstrap without replacing an existing tool."""
    target = ComponentFile(destination)

    def install() -> None:
        source = ComponentFile(staged)
        if source.fingerprint() is None:
            raise FileNotFoundError(staged)
        target.path.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=target.path.parent) as directory:
            candidate = Path(directory) / "uv-stage"
            _ = shutil.copy2(source.path, candidate)
            os.link(candidate, target.path)

    return registry.acquire(
        "uv", target.identity, app, "installer", probe=target.fingerprint, install=install
    )


def file_identity(info: os.stat_result) -> tuple[int, ...]:
    """Identify the filesystem instance described by a stat result."""
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_ctime_ns,
        info.st_mtime_ns,
        info.st_nlink,
    )


class ComponentFile:
    """Identify an exact file without granting ownership of the directory."""

    def __init__(self, path: Path) -> None:
        if not path.is_absolute() or not path.name:
            raise ValueError("An absolute component file path is required")
        self.path = path.parent.resolve() / path.name

    @property
    def identity(self) -> str:
        """Return the canonical location shared by consumers."""
        return os.path.normcase(str(self.path))

    def fingerprint(self) -> str | None:
        """Return an instance fingerprint, or None if the file is absent."""
        if self.path.parent.resolve() != self.path.parent:
            raise ValueError("The component parent path changed")
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"Expected an unlinked regular file at {self.path}")
        expected = file_identity(info)
        with self.path.open("rb") as stream:
            if file_identity(os.fstat(stream.fileno())) != expected:
                raise ValueError("The component changed while opening it")
            content = hashlib.file_digest(stream, "sha256").hexdigest()
        if file_identity(self.path.lstat()) != expected:
            raise ValueError("The component changed during verification")
        return ":".join([*(str(field) for field in expected), content])

    def remove(self, expected: str) -> None:
        """Remove only the verified file instance."""
        if self.fingerprint() != expected:
            raise ValueError("The component changed before removal")
        self.path.unlink()
