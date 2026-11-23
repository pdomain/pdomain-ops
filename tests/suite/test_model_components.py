"""Model cleanup stays within the exact published snapshot."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest

from pdomain_ops.suite import model_components
from pdomain_ops.suite.components import ComponentRegistry
from pdomain_ops.suite.model_components import (
    ModelCacheEntry,
    make_model_file_fetcher,
    preview_cached_models,
    preview_model_cleanup,
    publish_model_download,
    remove_model_entry,
    track_model_download,
)


def _stage(entry: ModelCacheEntry, cache: Path, content: bytes = b"weights") -> Path:
    path = entry.in_cache(cache).path
    path.parent.mkdir(parents=True)
    _ = path.write_bytes(content)
    return path


def test_removing_snapshot_link_keeps_shared_blob_and_other_revision(tmp_path: Path) -> None:
    repo = tmp_path / "models--pdomain--models"
    blob = repo / "blobs" / "weights"
    blob.parent.mkdir(parents=True)
    _ = blob.write_bytes(b"weights")
    first = ModelCacheEntry(tmp_path, "pdomain/models", "a" * 40, "nested/model.pt")
    second = ModelCacheEntry(tmp_path, "pdomain/models", "b" * 40, "nested/model.pt")
    for entry in (first, second):
        entry.path.parent.mkdir(parents=True)
        entry.path.symlink_to(blob)
    fingerprint = first.fingerprint()
    assert fingerprint is not None
    first.remove(fingerprint)
    assert first.fingerprint() is None
    assert second.path.read_bytes() == b"weights"


def test_external_link_and_traversal_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="model filename"):
        _ = ModelCacheEntry(tmp_path, "pdomain/models", "a" * 40, "../output.txt")
    entry = ModelCacheEntry(tmp_path, "pdomain/models", "a" * 40, "model.pt")
    output = tmp_path / "output.txt"
    _ = output.write_text("OCR output")
    entry.path.parent.mkdir(parents=True)
    entry.path.symlink_to(output)
    with pytest.raises(ValueError, match="blob"):
        _ = entry.fingerprint()
    assert output.read_text() == "OCR output"


def test_snapshot_removal_keeps_deduplicated_blob_and_repository_alias(tmp_path: Path) -> None:
    entry = ModelCacheEntry(tmp_path, "pdomain/models", "a" * 40, "nested/model.pt")
    entry.path.parent.mkdir(parents=True)
    digest = "ab" * 32
    blob = tmp_path / "blobs" / digest[:2] / digest
    blob.parent.mkdir(parents=True)
    _ = blob.write_bytes(b"weights")
    alias = tmp_path / "models--pdomain--models" / "blobs" / ("cd" * 32)
    alias.parent.mkdir()
    alias.symlink_to(blob)
    entry.path.symlink_to(Path("../../..") / "blobs" / alias.name)
    fingerprint = entry.fingerprint()
    assert fingerprint is not None
    entry.remove(fingerprint)
    assert not entry.path.is_symlink()
    assert alias.read_bytes() == b"weights"


def test_model_cleanup_rechecks_preview_and_siblings(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    entry = ModelCacheEntry(tmp_path, "pdomain/models", "a" * 40, "model.pt")
    entry.path.parent.mkdir(parents=True)
    _ = publish_model_download(
        "cli", "setup", entry, lambda cache: _stage(entry, cache), registry=registry
    )
    (selection,) = preview_model_cleanup(registry, "cli", (entry,))
    assert selection.path == entry.path
    assert not remove_model_entry(registry, "cli", selection, siblings_safe=lambda: False)
    track_model_download("gui", "runtime", (entry,), lambda: None, registry=registry)
    assert not remove_model_entry(registry, "cli", selection, siblings_safe=lambda: True)
    registry.release("cli")
    (selection,) = preview_model_cleanup(registry, "gui", (entry,))
    assert remove_model_entry(registry, "gui", selection, siblings_safe=lambda: True)
    assert not entry.path.exists()


def test_preview_finds_old_tracked_revision_in_selected_cache_only(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    cache = tmp_path / "cache"
    old = ModelCacheEntry(cache, "pdomain/models", "a" * 40, "nested/model.pt")
    unrelated = ModelCacheEntry(tmp_path / "other", "pdomain/models", "b" * 40, "model.pt")
    untracked = ModelCacheEntry(cache, "pdomain/models", "c" * 40, "model.pt")
    for entry in (old, unrelated, untracked):
        entry.path.parent.mkdir(parents=True)
    untracked.path.touch()
    for entry in (old, unrelated):

        def fetch(cache: Path, model: ModelCacheEntry = entry) -> Path:
            return _stage(model, cache)

        _ = publish_model_download("cli", "installer", entry, fetch, registry=registry)
    assert [item.path for item in preview_cached_models(registry, "cli", cache)] == [old.path]


def test_runtime_download_adds_a_new_revision_to_app_cleanup(tmp_path: Path) -> None:
    app = "pdomain-ocr-cli"
    registry = ComponentRegistry(tmp_path / "components.json")
    cache = tmp_path / "cache"
    installed = ModelCacheEntry(cache, "pdomain/models", "a" * 40, "model.pt")
    updated = ModelCacheEntry(cache, "pdomain/models", "b" * 40, "model.pt")
    for entry in (installed, updated):
        entry.path.parent.mkdir(parents=True)
    _ = publish_model_download(
        app, "installer", installed, lambda stage: _stage(installed, stage), registry=registry
    )
    _ = publish_model_download(
        app, "runtime", updated, lambda stage: _stage(updated, stage), registry=registry
    )
    records = {record.identity: record for record in registry.list()}
    assert records[installed.identity].source == "installer"
    assert records[updated.identity].source == "runtime"
    assert {item.path for item in preview_cached_models(registry, app, cache)} == {
        installed.path,
        updated.path,
    }
    track_model_download(
        "pdomain-ocr-simple-gui", "runtime", (updated,), lambda: None, registry=registry
    )
    assert [item.path for item in preview_cached_models(registry, app, cache)] == [installed.path]


def test_opaque_cache_hit_cannot_claim_files_created_by_another_process(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    cache = tmp_path / "hub"
    entry = ModelCacheEntry(cache, "pdomain/models", "a" * 40, "model.pt")

    def cache_hit() -> Path:
        entry.path.parent.mkdir(parents=True)
        _ = entry.path.write_bytes(b"incumbent")
        return entry.path

    assert (
        track_model_download("gui", "installer", (entry,), cache_hit, registry=registry)
        == entry.path
    )
    assert not registry.list()
    assert not preview_cached_models(registry, "gui", cache)
    assert entry.path.read_bytes() == b"incumbent"


def test_external_publication_during_staging_is_preserved(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    entry = ModelCacheEntry(tmp_path / "hub", "pdomain/models", "a" * 40, "model.pt")

    def fetch(cache: Path) -> Path:
        _ = entry.path.write_bytes(b"incumbent")
        return _stage(entry, cache)

    assert publish_model_download("cli", "installer", entry, fetch, registry=registry) == entry.path
    assert entry.path.read_bytes() == b"incumbent"
    assert not registry.list()


def test_external_publication_at_no_replace_boundary_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    entry = ModelCacheEntry(tmp_path / "hub", "pdomain/models", "a" * 40, "model.pt")

    def late_publish(_source: Path, destination: Path) -> str:
        _ = destination.write_bytes(b"incumbent")
        raise FileExistsError(errno.EEXIST, "Model already exists", destination)

    monkeypatch.setattr(model_components, "_publish_snapshot", late_publish)
    assert (
        publish_model_download(
            "cli", "installer", entry, lambda stage: _stage(entry, stage), registry=registry
        )
        == entry.path
    )
    assert entry.path.read_bytes() == b"incumbent"
    assert not registry.list()


def test_known_publication_survives_failure_to_stage_later_file(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    cache = tmp_path / "hub"
    first = ModelCacheEntry(cache, "pdomain/models", "a" * 40, "model.pt")
    second = ModelCacheEntry(cache, "pdomain/models", "a" * 40, "model.arch")

    def fail(stage: Path) -> Path:
        _ = _stage(second, stage, b"incomplete")
        raise RuntimeError("network interrupted")

    assert (
        publish_model_download(
            "cli", "installer", first, lambda stage: _stage(first, stage), registry=registry
        )
        == first.path
    )
    with pytest.raises(RuntimeError, match="network interrupted"):
        _ = publish_model_download("cli", "installer", second, fail, registry=registry)
    assert [record.identity for record in registry.list()] == [first.identity]
    assert not tuple(first.repository.glob(".pdomain-model-*"))
    assert not second.path.exists()

    def unexpected(_stage: Path) -> Path:
        pytest.fail("A known exact file should be reused")

    _ = publish_model_download("gui", "runtime", first, unexpected, registry=registry)
    registry.release("cli")
    (selection,) = preview_cached_models(registry, "gui", cache)
    assert remove_model_entry(registry, "gui", selection, siblings_safe=lambda: True)
    assert not first.path.exists()


def test_fetcher_uses_private_cache_only_for_pinned_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from huggingface_hub import constants, file_download

    cache = tmp_path / "hub"
    settings = tmp_path / "suite"
    revision = "a" * 40
    requests: list[Path] = []
    monkeypatch.setenv("PD_SUITE_DATA_DIR", str(settings))
    monkeypatch.setattr(constants, "HF_HUB_CACHE", str(cache))

    def download(*, repo_id: str, filename: str, revision: str | None, cache_dir: Path) -> str:
        requests.append(cache_dir)
        entry = ModelCacheEntry(cache_dir, repo_id, revision or "b" * 40, filename)
        path = _stage(entry, cache_dir)
        return str(path)

    monkeypatch.setattr(file_download, "hf_hub_download", download)
    fetch = make_model_file_fetcher("gui", "installer")
    path = fetch("pdomain/models", "model.pt", revision)
    _ = fetch("pdomain/models", "other.pt", None)
    assert requests[0] != cache
    assert not requests[0].exists()
    assert requests[1] == cache
    assert path.read_bytes() == b"weights"
    assert not path.is_symlink()
    entry = ModelCacheEntry(cache, "pdomain/models", revision, "model.pt")
    assert [record.identity for record in ComponentRegistry().list()] == [entry.identity]


def test_registry_write_failure_retains_published_model_without_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    cache = tmp_path / "hub"
    entry = ModelCacheEntry(cache, "pdomain/models", "a" * 40, "model.pt")
    replace = Path.replace

    def reject_registry_replace(path: Path, target: str | Path) -> Path:
        if target == registry.path:
            raise OSError(errno.ENOSPC, "Registry disk is full")
        return replace(path, target)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "replace", reject_registry_replace)
        with pytest.raises(OSError, match="Registry disk is full"):
            _ = publish_model_download(
                "cli", "runtime", entry, lambda stage: _stage(entry, stage), registry=registry
            )

    assert entry.path.read_bytes() == b"weights"
    assert not tuple(entry.repository.glob(".pdomain-model-*"))

    def unexpected_fetch(_stage: Path) -> Path:
        pytest.fail("The published model should survive the registry error")

    assert (
        publish_model_download("cli", "runtime", entry, unexpected_fetch, registry=registry)
        == entry.path
    )
    assert not registry.list()
    assert not preview_cached_models(registry, "cli", cache)
