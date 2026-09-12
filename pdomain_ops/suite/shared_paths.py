"""Suite shared-paths API: publish and resolve well-known data paths."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import filelock
from typing_extensions import override

_logger = logging.getLogger(__name__)

#: Finite default lock timeout — matches prefs.DEFAULT_LOCK_TIMEOUT.
DEFAULT_LOCK_TIMEOUT: float = 5.0

#: Env var for overriding the default timeout, consistent with PDOMAIN_PREFS_LOCK_TIMEOUT.
LOCK_TIMEOUT_ENV_VAR = "PDOMAIN_SHARED_PATHS_LOCK_TIMEOUT"


class SharedPathsLockTimeout(filelock.Timeout):
    """Raised when the shared-paths file lock cannot be acquired within the timeout.

    Subclasses ``filelock.Timeout`` for the same reason as ``PrefsLockTimeout``:
    existing callers catching the upstream exception keep working, while new callers
    can catch this typed error and map it to an HTTP 503.
    """

    def __init__(self, lock_file: str, timeout: float) -> None:
        super().__init__(lock_file)
        self.timeout = timeout

    @override
    def __str__(self) -> str:
        return (
            f"Could not acquire shared-paths lock on {self.lock_file!r} within "
            f"{self.timeout}s; another process may be holding it (orphaned?)."
        )


def _shared_paths_json() -> Path:
    from pdomain_ops.suite.paths import shared_paths_json_path

    return shared_paths_json_path()


def _resolve_timeout(lock_timeout: float | None) -> float:
    """Resolve effective lock timeout using the same precedence as prefs.

    # Precedence: explicit kwarg > PDOMAIN_SHARED_PATHS_LOCK_TIMEOUT env var > DEFAULT_LOCK_TIMEOUT
    """
    if lock_timeout is not None:
        return lock_timeout
    env_val = os.environ.get(LOCK_TIMEOUT_ENV_VAR)
    if env_val is not None:
        try:
            return float(env_val)
        except ValueError:
            _logger.warning(
                "%s=%r is not a valid float; using default %ss",
                LOCK_TIMEOUT_ENV_VAR,
                env_val,
                DEFAULT_LOCK_TIMEOUT,
            )
    return DEFAULT_LOCK_TIMEOUT


def _read_raw(json_path: Path) -> dict[str, Any]:
    """Read shared-paths.json, returning an empty structure on any error."""
    if not json_path.exists():
        return {"paths": {}}
    try:
        raw: Any = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — JSON parse failure treated as empty/default (resilience)
        return {"paths": {}}
    else:
        if isinstance(raw, dict):
            return cast("dict[str, Any]", raw)
        return {"paths": {}}


def _open_staged(path: Path) -> tuple[int, Path]:
    """Create a staging file beside *path*, open for writing.

    Not ``tempfile.mkstemp``: that hardcodes 0600 and ignores the umask, which
    is right for a private scratch file and wrong for one about to be
    published, because a rename preserves the mode. Passing the mode to
    ``os.open`` lets the kernel apply the umask exactly as for a plain
    ``open()``, so there is no chmod to forget and no umask to read. 0666, not
    0777: nothing published this way is a program.

    ``O_EXCL`` keeps ``mkstemp``'s guarantee that creation fails rather than
    opening an existing file or following a symlink into one.
    """
    while True:
        staged = path.parent / f".{path.name}.{uuid4().hex}.tmp"
        try:
            return os.open(staged, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666), staged
        except FileExistsError:  # pragma: no cover - needs a uuid4 collision
            continue


def _atomic_write(json_path: Path, data: dict[str, Any]) -> None:
    """Write *data* as JSON, publishing it at a mode other uids can read.

    ``tempfile.mkstemp`` hardcodes 0600 and ignores the umask by design, and a
    rename preserves that mode. Without the chmod, every file written here
    lands at 0600 whatever the umask says, which hides it from any reader
    running as a different uid — the host's restic backup included. Start from
    0666, never 0777: nothing written here is a program.
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = _open_staged(json_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp_path.replace(json_path)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def publish_shared_path(
    key: str,
    path: Path,
    *,
    app: str,
    lock_timeout: float | None = None,
) -> None:
    """Record *path* under *key* in the suite shared-paths registry.

    Last writer wins when two apps publish the same key concurrently —
    the write is atomic (tmp + os.replace) and serialised through a
    finite-timeout FileLock so corrupt interleaved writes are impossible.

    Args:
        key: Arbitrary string identifier (e.g. ``"doctr-export-root"``).
        path: The filesystem path to publish. Must be absolute.
        app: The publishing app id (informational, stored alongside the path).
        lock_timeout: Seconds to wait for the file lock. Falls back to
            ``PDOMAIN_SHARED_PATHS_LOCK_TIMEOUT`` env var, then
            :data:`DEFAULT_LOCK_TIMEOUT`.

    Raises:
        ValueError: If *path* is not absolute.
        SharedPathsLockTimeout: If the lock cannot be acquired in time.
    """
    if not path.is_absolute():
        raise ValueError(f"publish_shared_path: path must be absolute, got {path!r}")
    timeout = _resolve_timeout(lock_timeout)
    json_path = _shared_paths_json()
    lock_file = str(json_path.with_suffix(".json.lock"))
    lock = filelock.FileLock(lock_file, timeout=timeout)
    try:
        with lock:
            data = _read_raw(json_path)
            paths: dict[str, Any] = data.get("paths") or {}
            paths[key] = {"path": str(path), "app": app}
            data["paths"] = paths
            _atomic_write(json_path, data)
    except filelock.Timeout as exc:
        raise SharedPathsLockTimeout(lock_file, timeout) from exc


def resolve_shared_path(
    key: str,
    *,
    lock_timeout: float | None = None,
) -> Path | None:
    """Return the path published under *key*, or ``None`` if not found.

    The returned path may not exist on disk — the caller is responsible for
    verifying existence if needed. A missing or corrupt registry file returns
    ``None`` silently.

    Args:
        key: The key to look up.
        lock_timeout: Seconds to wait for the file lock.

    Raises:
        SharedPathsLockTimeout: If the lock cannot be acquired in time.
    """
    timeout = _resolve_timeout(lock_timeout)
    json_path = _shared_paths_json()
    lock_file = str(json_path.with_suffix(".json.lock"))
    lock = filelock.FileLock(lock_file, timeout=timeout)
    try:
        with lock:
            data = _read_raw(json_path)
    except filelock.Timeout as exc:
        raise SharedPathsLockTimeout(lock_file, timeout) from exc

    paths: dict[str, Any] = data.get("paths") or {}
    entry = paths.get(key)
    if not isinstance(entry, dict):
        return None
    raw_path = cast("dict[str, Any]", entry).get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    return Path(raw_path)
