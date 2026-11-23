"""Exact Hugging Face model snapshot entries for component ownership."""

from __future__ import annotations

import errno
import importlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from pdomain_ops.suite.component_files import file_identity
from pdomain_ops.suite.components import ComponentRegistry

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
    """Claim existing verified entries after an opaque legacy download."""
    result = download()
    store = registry if registry is not None else ComponentRegistry()
    for entry in entries:
        try:
            _ = store.acquire("model", entry.identity, app, source, probe=entry.fingerprint)
        except (OSError, RuntimeError, ValueError):
            continue
    return result


class _NoReplaceUnavailableError(OSError):
    """The cache filesystem cannot make a verified no-replace publication."""


def _publish_snapshot(source: Path, destination: Path) -> str:
    before = source.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_ino == 0 or before.st_nlink != 1:
        raise _NoReplaceUnavailableError("The staged model has no verifiable file identity")
    if destination.parent.resolve() != destination.parent:
        raise ValueError("The snapshot directory is redirected")
    try:
        if os.name == "nt":
            # Windows rename fails if the destination exists.
            _ = source.rename(destination)
        else:
            os.link(source, destination)
    except OSError as error:
        if error.errno in {errno.EXDEV, errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EPERM}:
            raise _NoReplaceUnavailableError(
                "The cache filesystem cannot publish a model safely"
            ) from error
        raise
    if os.name != "nt":
        source.unlink()
    after = destination.lstat()
    if (
        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        or not stat.S_ISREG(after.st_mode)
        or after.st_nlink != 1
    ):
        raise ValueError("The published model changed before ownership could be confirmed")
    return ":".join(str(value) for value in file_identity(after))


def _claim_existing(
    store: ComponentRegistry, app: str, source: str, entry: ModelCacheEntry
) -> bool:
    present = False

    def probe() -> str | None:
        nonlocal present
        try:
            fingerprint = entry.fingerprint()
        except (OSError, RuntimeError, ValueError) as error:
            raise _NoReplaceUnavailableError(
                "The existing model cache cannot be verified"
            ) from error
        present = fingerprint is not None
        return fingerprint

    _ = store.acquire("model", entry.identity, app, source, probe=probe)
    return present


def publish_model_download(
    app: str,
    source: str,
    entry: ModelCacheEntry,
    fetch: Callable[[Path], Path],
    *,
    registry: ComponentRegistry | None = None,
) -> Path:
    """Download in private staging and claim only an exact no-replace publication."""
    store = registry if registry is not None else ComponentRegistry()
    if _claim_existing(store, app, source, entry):
        return entry.path

    entry.path.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = entry.repository
    if staging_parent.stat().st_dev != entry.path.parent.stat().st_dev:
        staging_parent = entry.path.parent
    with TemporaryDirectory(prefix=".pdomain-model-", dir=staging_parent) as directory:
        cache = Path(directory)
        staged = entry.in_cache(cache)
        if fetch(cache) != staged.path or staged.fingerprint() is None:
            raise ValueError("Download returned a different model or revision")
        payload = staged.path.resolve(strict=True)
        if not payload.is_relative_to(cache):
            raise ValueError("Staged model points outside the private download cache")
        published: str | None = None

        def install() -> None:
            nonlocal published
            published = _publish_snapshot(payload, entry.path)

        def probe() -> str | None:
            fingerprint = entry.fingerprint()
            if published is not None and published != fingerprint:
                raise ValueError("The published model changed before ownership could be recorded")
            return fingerprint

        try:
            # An external reader may already be using the snapshot if the registry write fails.
            _ = store.acquire("model", entry.identity, app, source, probe=probe, install=install)
        except FileExistsError:
            # A Hugging Face writer can publish independently of the component registry.
            if not _claim_existing(store, app, source, entry):
                raise
    return entry.path


@runtime_checkable
class _HubDownloader(Protocol):
    def hf_hub_download(
        self, *, repo_id: str, filename: str, revision: str | None, cache_dir: Path
    ) -> object: ...


def make_model_file_fetcher(app: str, source: str) -> Callable[[str, str, str | None], Path]:
    """Build a Book Tools resolver for managed pinned Hugging Face files."""
    from huggingface_hub.constants import HF_HUB_CACHE

    hub = importlib.import_module("huggingface_hub.file_download")
    if not isinstance(hub, _HubDownloader):
        raise TypeError("Hugging Face does not provide a file downloader")
    cache = Path(HF_HUB_CACHE).absolute()

    def fetch(repo: str, filename: str, revision: str | None) -> Path:
        def download(cache_dir: Path) -> Path:
            value = hub.hf_hub_download(
                repo_id=repo, filename=filename, revision=revision, cache_dir=cache_dir
            )
            if not isinstance(value, str):
                raise TypeError("Hugging Face did not return a cached model file")
            return Path(value)

        if revision is not None:
            try:
                entry = ModelCacheEntry(cache, repo, revision, filename)
            except ValueError:
                pass
            else:
                try:
                    return publish_model_download(app, source, entry, download)
                except _NoReplaceUnavailableError:
                    pass
        return download(cache)

    return fetch


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
        self._repo_id = repo
        self._revision = revision
        self._filename = filename
        self._repo = cache.resolve() / ("models--" + "--".join(repo_parts))
        self.path = self._repo / "snapshots" / revision / relative

    @property
    def repository(self) -> Path:
        """Return the model repository's cache directory."""
        return self._repo

    def in_cache(self, cache: Path) -> ModelCacheEntry:
        """Address the same pinned file in a private staging cache."""
        return ModelCacheEntry(cache, self._repo_id, self._revision, self._filename)

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
            target = self.path.parent / self.path.readlink()
            alias = target.parent.resolve(strict=True) / target.name
            if alias.parent != self._repo / "blobs":
                raise ValueError(
                    "The snapshot link must reference a blob in the same cache repository"
                )
            blob = self.path.resolve(strict=True)
            shared_blobs = self._repo.parent / "blobs"
            shared = (
                re.fullmatch(r"[0-9a-f]{64}", blob.name) is not None
                and blob.parent == shared_blobs / blob.name[:2]
            )
            if blob != alias and not shared:
                raise ValueError("The repository blob points outside the shared cache blob store")
            blob_stat = blob.lstat()
            if not stat.S_ISREG(blob_stat.st_mode):
                raise ValueError("The model blob must be a regular file")
            alias_details = file_identity(alias.lstat()) if shared else ()
            return ":".join(
                [
                    str(blob),
                    *(
                        str(value)
                        for value in (*details, *alias_details, *file_identity(blob_stat))
                    ),
                ]
            )
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("The model entry must be a file or snapshot link")
        return ":".join(str(value) for value in details)

    def remove(self, expected: str) -> None:
        """Remove one verified snapshot entry, retaining any shared blob."""
        if self.fingerprint() != expected:
            raise ValueError("The model entry changed before removal")
        self.path.unlink()
