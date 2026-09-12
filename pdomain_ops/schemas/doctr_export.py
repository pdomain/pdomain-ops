"""DocTR export manifest schema and IO helpers.

The manifest file lives at ``<export_root>/manifest.json`` and records
which projects have been exported, when, and with what task item counts.

Forward-compat: ``version > 1`` is accepted with a log warning rather than
raising — the caller decides whether to reject an unexpected version.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import datetime  # noqa: TC003  # Pydantic requires runtime import
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = "manifest.json"
_CURRENT_VERSION = 1


class DoctrExportTaskStats(BaseModel):
    """Per-task item count for one export."""

    model_config = ConfigDict(extra="ignore")

    item_count: int


class DoctrExportProject(BaseModel):
    """Export record for one project."""

    model_config = ConfigDict(extra="ignore")

    exported_at: datetime
    page_count: int
    tasks: dict[str, DoctrExportTaskStats]


class DoctrExportManifest(BaseModel):
    """Top-level DocTR export manifest.

    The JSON key ``"schema"`` maps to the Python field ``schema_id``
    to avoid collision with Pydantic's own ``.model_json_schema()`` method.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    schema_id: str = Field(
        default="pdomain.doctr-export-manifest",
        alias="schema",
    )
    version: int = _CURRENT_VERSION
    generated_at: datetime
    app: str
    projects: dict[str, DoctrExportProject] = {}


def read_manifest(export_root: Path) -> DoctrExportManifest | None:
    """Read the manifest from ``<export_root>/manifest.json``.

    Returns ``None`` if the file does not exist.
    Raises ``ValueError`` with "corrupt" in the message if the file exists
    but cannot be parsed or fails model validation.

    Version > 1 is accepted with a log warning — caller decides to reject.
    """
    path = export_root / _MANIFEST_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"corrupt manifest at {path}: {exc}") from exc
    try:
        manifest = DoctrExportManifest.model_validate(data)
    except Exception as exc:
        raise ValueError(f"corrupt manifest at {path}: {exc}") from exc
    if manifest.version > _CURRENT_VERSION:
        _logger.warning(
            "manifest at %s has version %d > current %d; parsing best-effort",
            path,
            manifest.version,
            _CURRENT_VERSION,
        )
    return manifest


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


def write_manifest(export_root: Path, manifest: DoctrExportManifest) -> None:
    """Write *manifest* to ``<export_root>/manifest.json`` atomically.

    Uses a temporary file in the same directory + ``os.replace`` so
    readers never see a partial write. Creates ``export_root`` if it
    does not exist.
    """
    export_root.mkdir(parents=True, exist_ok=True)
    dest = export_root / _MANIFEST_FILENAME
    fd, tmp_path = _open_staged(dest)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(by_alias=True, indent=2))
        tmp_path.replace(dest)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise
