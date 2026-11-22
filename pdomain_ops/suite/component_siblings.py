"""Recognize legacy OCR installations before offering shared cleanup."""

from __future__ import annotations

import os
import stat
import tomllib
from pathlib import Path
from typing import cast

_UV_METADATA = frozenset({".gitignore", ".lock", ".nobackup", "CACHEDIR.TAG"})


def _inactive_cli_lock(path: Path) -> bool:
    if os.name != "posix":
        return False
    import fcntl

    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size:
                return False
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        finally:
            os.close(descriptor)
    except OSError:
        return False


def other_uv_tools_absent(roots: tuple[Path, ...], *, departing_tool: str | None = None) -> bool:
    """Check the active tool root and any other supported roots."""
    seen: set[Path] = set()
    try:
        for index, root in enumerate(roots):
            resolved = root.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                children = tuple(resolved.iterdir())
            except FileNotFoundError:
                continue
            for child in children:
                if child.name in _UV_METADATA or (index == 0 and child.name == departing_tool):
                    continue
                if child.name == ".pdomain-ocr-cli.in-use.lock" and _inactive_cli_lock(child):
                    continue
                return False
    except (OSError, RuntimeError):
        return False
    return bool(roots)


def macos_ocr_sibling_absent(
    app: str,
    *,
    home: Path,
    tool_dir: Path,
    bin_dir: Path,
    installed_apps: Path,
    system_applications: Path = Path("/Applications"),
) -> bool:
    """Return false if supported locations contain a sibling or cannot be read."""
    if app == "pdomain-ocr-cli":
        sibling = "pdomain-ocr-simple-gui"
        launchers = (sibling, f"{sibling}-desktop")
        bundles = tuple(
            root / "OCR Simple GUI.app" for root in (home / "Applications", system_applications)
        )
    elif app == "pdomain-ocr-simple-gui":
        sibling = "pdomain-ocr-cli"
        launchers = ("pdomain-ocr",)
        bundles = ()
    else:
        raise ValueError("Unknown OCR application")

    candidates = (
        *bundles,
        tool_dir / sibling,
        home / ".local/share/uv/tools" / sibling,
        *(root / name for root in (bin_dir, home / ".local/bin") for name in launchers),
    )
    for candidate in candidates:
        try:
            _ = candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return False
        return False

    try:
        with installed_apps.open("rb") as stream:
            data = cast("dict[str, object]", tomllib.load(stream))
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False
    apps = data.get("apps")
    return isinstance(apps, dict) and sibling not in apps
