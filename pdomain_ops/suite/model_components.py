"""Exact Hugging Face model snapshot entries for component ownership."""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, TypeVar

from pdomain_ops.suite.component_files import file_identity
from pdomain_ops.suite.components import ComponentProbe, ComponentRegistry

if TYPE_CHECKING:
    from collections.abc import Callable

_Result = TypeVar("_Result")


@dataclass(frozen=True)
class ModelCleanupSelection:
    """The exact model cache entry and instance shown during confirmation."""

    entry: ModelCacheEntry
    fingerprint: str

    @property
    def path(self) -> Path:
        """Return the path shown in the removal preview."""
        return self.entry.path


def preview_model_cleanup(
    registry: ComponentRegistry,
    app: str,
    entries: tuple[ModelCacheEntry, ...],
) -> tuple[ModelCleanupSelection, ...]:
    """Find unchanged model entries with just the requesting app's claim."""
    owned = {
        record.identity: record.fingerprint
        for record in registry.list()
        if record.kind == "model" and record.claims == (app,)
    }
    return tuple(
        ModelCleanupSelection(entry, fingerprint)
        for entry in entries
        if (fingerprint := owned.get(entry.identity)) is not None
        and entry.fingerprint() == fingerprint
    )


def preview_cached_models(
    registry: ComponentRegistry,
    app: str,
    cache: Path,
) -> tuple[ModelCleanupSelection, ...]:
    """Preview all tracked revisions in the selected Hugging Face cache."""
    root = cache.resolve()
    selections: list[ModelCleanupSelection] = []
    for record in registry.list():
        if record.kind != "model" or record.claims != (app,):
            continue
        path = Path(record.identity)
        if not path.is_relative_to(root):
            continue
        parts = path.relative_to(root).parts
        if len(parts) < 4 or not parts[0].startswith("models--") or parts[1] != "snapshots":
            continue
        repo = parts[0].removeprefix("models--").replace("--", "/")
        filename = "/".join(parts[3:])
        try:
            entry = ModelCacheEntry(root, repo, parts[2], filename)
            if entry.identity == record.identity and entry.fingerprint() == record.fingerprint:
                selections.append(ModelCleanupSelection(entry, record.fingerprint))
        except (OSError, ValueError):
            continue
    return tuple(selections)


def remove_model_entry(
    registry: ComponentRegistry,
    app: str,
    selection: ModelCleanupSelection,
    *,
    siblings_safe: Callable[[], bool],
) -> bool:
    """Recheck consent, current claims, and legacy siblings before deletion."""
    entry = selection.entry
    return registry.remove(
        "model",
        entry.identity,
        app,
        entry.fingerprint,
        lambda: entry.remove(selection.fingerprint),
        expected_fingerprint=selection.fingerprint,
        siblings_safe=siblings_safe,
    )


def track_model_download(
    app: str,
    source: str,
    entries: tuple[ModelCacheEntry, ...],
    download: Callable[[], _Result],
    *,
    registry: ComponentRegistry | None = None,
) -> _Result:
    """Track only the stated cache entries populated by a model download."""
    probes = tuple(ComponentProbe("model", entry.identity, entry.fingerprint) for entry in entries)
    store = registry if registry is not None else ComponentRegistry()
    return store.acquire_batch(app, source, probes, download)


def _safe_segment(part: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part) is not None and not part.endswith(".")


class ModelCacheEntry:
    """Identify one revision's snapshot file without owning shared blobs."""

    def __init__(self, cache: Path, repo: str, revision: str, filename: str) -> None:
        if not cache.is_absolute():
            raise ValueError("An absolute model cache path is required")
        repo_parts = repo.split("/")
        if len(repo_parts) not in (1, 2) or any(
            not _safe_segment(part) or "--" in part for part in repo_parts
        ):
            raise ValueError("Invalid model repository")
        if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            raise ValueError("An exact model revision commit is required")
        relative = PurePosixPath(filename)
        if not relative.parts or any(not _safe_segment(part) for part in relative.parts):
            raise ValueError("Invalid model filename")
        self._repo = cache.resolve() / ("models--" + "--".join(repo_parts))
        self.path = self._repo / "snapshots" / revision / relative

    @property
    def identity(self) -> str:
        """Return the exact location the two products can claim."""
        return os.path.normcase(str(self.path))

    def fingerprint(self) -> str | None:
        """Validate the snapshot and identify its current file or link."""
        if self.path.parent.resolve() != self.path.parent:
            raise ValueError("The snapshot directory is redirected")
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return None
        details = file_identity(info)
        if stat.S_ISLNK(info.st_mode):
            blob = self.path.resolve(strict=True)
            if blob.parent != self._repo / "blobs":
                raise ValueError(
                    "The snapshot link must reference a blob in the same cache repository"
                )
            blob_stat = blob.lstat()
            if not stat.S_ISREG(blob_stat.st_mode):
                raise ValueError("The model blob must be a regular file")
            return ":".join(
                [str(blob), *(str(value) for value in (*details, *file_identity(blob_stat)))]
            )
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("The model entry must be a file or snapshot link")
        return ":".join(str(value) for value in details)

    def remove(self, expected: str) -> None:
        """Remove one verified snapshot entry, retaining any shared blob."""
        if self.fingerprint() != expected:
            raise ValueError("The model entry changed before removal")
        self.path.unlink()
