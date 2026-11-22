"""Scratch verification for exact component files."""

from pathlib import Path

import pytest

from pdomain_ops.suite.component_files import ComponentFile, install_staged_uv
from pdomain_ops.suite.components import ComponentRegistry


def test_replacement_at_uv_path_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "uv"
    item = ComponentFile(path)
    registry = ComponentRegistry(tmp_path / "components.json")
    record = registry.acquire(
        "uv",
        item.identity,
        "ocr-cli",
        "setup",
        probe=item.fingerprint,
        install=lambda: path.write_bytes(b"same bytes"),
    )
    assert record is not None
    replacement = tmp_path / "replacement"
    _ = replacement.write_bytes(b"same bytes")
    _ = replacement.replace(path)
    assert not registry.remove(
        "uv",
        item.identity,
        "ocr-cli",
        item.fingerprint,
        lambda: item.remove(record.fingerprint),
        expected_fingerprint=record.fingerprint,
        siblings_safe=lambda: True,
    )
    assert path.read_bytes() == b"same bytes"


def test_component_file_refuses_symlink(tmp_path: Path) -> None:
    actual = tmp_path / "user-file"
    _ = actual.write_bytes(b"keep")
    launcher = tmp_path / "uv"
    launcher.symlink_to(actual)
    with pytest.raises(ValueError, match="regular file"):
        _ = ComponentFile(launcher).fingerprint()
    assert actual.read_bytes() == b"keep"


def test_removes_only_recorded_file(tmp_path: Path) -> None:
    path = tmp_path / "uv"
    sibling = tmp_path / "another-tool"
    _ = path.write_bytes(b"uv")
    _ = sibling.write_bytes(b"keep")
    item = ComponentFile(path)
    exact = item.fingerprint()
    assert exact is not None
    item.remove(exact)
    assert item.fingerprint() is None
    assert sibling.read_bytes() == b"keep"


@pytest.mark.parametrize("preexisting", [True, False])
def test_install_staged_uv_records_only_new_destination(tmp_path: Path, preexisting: bool) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    staged = tmp_path / "staging/uv"
    staged.parent.mkdir()
    _ = staged.write_bytes(b"staged")
    uv = tmp_path / "bin/uv"
    uv.parent.mkdir()
    if preexisting:
        _ = uv.write_bytes(b"external")
    record = install_staged_uv(registry, "cli", staged, uv)
    assert uv.read_bytes() == (b"external" if preexisting else b"staged")
    if preexisting:
        assert record is None
        assert registry.list() == ()
    else:
        assert record is not None
        assert record.installed_by == "cli"
        assert record.fingerprint == ComponentFile(uv).fingerprint()
