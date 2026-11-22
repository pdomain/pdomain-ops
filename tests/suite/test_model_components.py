"""Model cleanup stays within one exact snapshot entry."""

from pathlib import Path

import pytest

from pdomain_ops.suite.components import ComponentRegistry
from pdomain_ops.suite.model_components import (
    ModelCacheEntry,
    preview_cached_models,
    preview_model_cleanup,
    remove_model_entry,
    track_model_download,
)


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
    track_model_download("cli", "setup", (entry,), entry.path.touch, registry=registry)
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
        track_model_download("cli", "installer", (entry,), entry.path.touch, registry=registry)
    assert [item.path for item in preview_cached_models(registry, "cli", cache)] == [old.path]


def test_runtime_download_adds_a_new_revision_to_app_cleanup(tmp_path: Path) -> None:
    app = "pdomain-ocr-cli"
    registry = ComponentRegistry(tmp_path / "components.json")
    cache = tmp_path / "cache"
    installed = ModelCacheEntry(cache, "pdomain/models", "a" * 40, "model.pt")
    updated = ModelCacheEntry(cache, "pdomain/models", "b" * 40, "model.pt")
    for entry in (installed, updated):
        entry.path.parent.mkdir(parents=True)
    track_model_download(app, "installer", (installed,), installed.path.touch, registry=registry)
    track_model_download(app, "runtime", (updated,), updated.path.touch, registry=registry)
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
