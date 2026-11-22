"""Exact uv-managed Python installations for shared component cleanup."""

from __future__ import annotations

import os
import re
import shutil
import stat
from typing import TYPE_CHECKING

from pdomain_ops.suite.component_files import ComponentFile, file_identity

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pdomain_ops.suite.components import Component, ComponentRegistry


def claim_existing_tools(
    registry: ComponentRegistry,
    app: str,
    uv: Path,
    managed_root: Path,
    base: Path,
) -> tuple[Component, ...]:
    """Claim only verified, previously recorded tools used by this app."""
    claims: list[Component] = []
    companion_names = ("uvx.exe", "uvw.exe") if uv.suffix.casefold() == ".exe" else ("uvx",)
    for executable in (uv, *(uv.with_name(name) for name in companion_names)):
        try:
            uv_file = ComponentFile(executable)
            claimed = registry.acquire(
                "uv", uv_file.identity, app, "installer", probe=uv_file.fingerprint
            )
        except (OSError, ValueError):
            continue
        if claimed is not None:
            claims.append(claimed)
    python = managed_python_from_executable(managed_root, base)
    if python is None:
        return tuple(claims)
    claimed = registry.acquire(
        "python", python.identity, app, "installer", probe=python.fingerprint
    )
    if claimed is not None:
        claims.append(claimed)
    return tuple(claims)


def managed_python_from_executable(root: Path, executable: Path) -> ManagedPython | None:
    """Identify the exact uv-managed build containing an interpreter."""
    if not root.is_absolute() or not executable.is_absolute():
        return None
    root = root.resolve()
    executable = executable.resolve()
    if not executable.is_relative_to(root):
        return None
    relative = executable.relative_to(root)
    if len(relative.parts) < 2:
        return None
    try:
        return ManagedPython(root, relative.parts[0], executable)
    except ValueError:
        return None


class ManagedPython:
    """Identify a full uv installation key and its verified interpreter."""

    def __init__(self, root: Path, key: str, executable: Path) -> None:
        if (
            re.fullmatch(r"cpython-[0-9]+\.[0-9]+\.[0-9]+-[a-z0-9_]+-[a-z0-9_]+-[a-z0-9_]+", key)
            is None
        ):
            raise ValueError("An exact uv build key is required")
        if not root.is_absolute() or not executable.is_absolute():
            raise ValueError("Absolute uv and interpreter paths are required")
        self.root = root.resolve()
        self.key = key
        self.path = self.root / key
        resolved = executable.resolve()
        if not resolved.is_relative_to(self.path) or resolved == self.path:
            raise ValueError("The interpreter is outside its uv-managed installation")
        self._executable = ComponentFile(resolved)

    @property
    def identity(self) -> str:
        """Return the exact managed directory rather than a version alias."""
        return os.path.normcase(str(self.path))

    def fingerprint(self) -> str | None:
        """Identify the installed directory and interpreter together."""
        if self.root.resolve() != self.root:
            raise ValueError("The uv-managed Python root changed")
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISDIR(info.st_mode) or self.path.resolve() != self.path:
            raise ValueError("The uv-managed Python directory is redirected")
        executable = self._executable.fingerprint()
        if executable is None:
            raise ValueError("The uv-managed interpreter is missing")
        return ":".join([*(str(value) for value in file_identity(info)), executable])

    def remove(self, uv: Path, expected: str, *, run: Callable[[list[str]], object]) -> None:
        """Use uv to remove only the verified full installation key."""
        if not uv.is_absolute():
            raise ValueError("An absolute uv executable path is required")
        if self.fingerprint() != expected:
            raise ValueError("The uv-managed Python installation changed before removal")
        _ = run(
            [
                str(uv),
                "--offline",
                "python",
                "uninstall",
                "--install-dir",
                str(self.root),
                self.key,
            ],
        )

    def stage_cleanup_interpreter(self, destination: Path, expected: str) -> Path:
        """Copy the verified build so Windows can remove the original interpreter."""
        if not destination.is_absolute() or destination.resolve().is_relative_to(self.path):
            raise ValueError("The cleanup interpreter must be staged outside the managed build")
        destination = destination.resolve()
        if self.fingerprint() != expected:
            raise ValueError("The uv-managed Python installation changed before staging")
        executable = self._executable.path.relative_to(self.path)
        _ = shutil.copytree(self.path, destination, symlinks=True)
        candidate = destination / executable
        if candidate.resolve() != candidate or not candidate.is_file():
            raise ValueError("The staged cleanup interpreter is redirected or missing")
        if self.fingerprint() != expected:
            raise ValueError("The uv-managed Python installation changed while staging")
        return candidate


def uv_installed_build(output: str) -> str | None:
    """Return the exact newly installed build reported by a uv install."""
    reported = re.findall(r"^ +\+ (cpython-[^\s]+)$", output, re.MULTILINE)
    if len(reported) != 1 or not re.search(r"^Installed Python [0-9]", output, re.MULTILINE):
        return None
    return reported[0]
