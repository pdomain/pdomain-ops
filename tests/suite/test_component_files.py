"""Scratch verification for exact component files."""

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdomain_ops.suite import component_files
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


@pytest.mark.parametrize("modern_python", [False, True])
@pytest.mark.parametrize("replacement", [False, True])
def test_windows_executable_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modern_python: bool, replacement: bool
) -> None:
    path = tmp_path / "uv.exe"
    content = b"uv"
    _ = path.write_bytes(content)
    item = ComponentFile(path)
    fields = {
        "st_dev": 17202882042848204125 if modern_python else 3169441117,
        "st_ino": 1125899907079812,
        "st_mode": 33279,
        "st_size": len(content),
        "st_ctime_ns": 100,
        "st_mtime_ns": 200,
        "st_nlink": 1,
    }
    if modern_python:
        fields["st_birthtime_ns"] = 100
    path_info = SimpleNamespace(**fields)
    handle_info = SimpleNamespace(
        **(
            fields
            | {
                "st_ino": fields["st_ino"] + int(replacement),
                "st_mode": 33206,
                "st_ctime_ns": 300 if modern_python else 100,
            }
        )
    )
    monkeypatch.setattr(component_files, "_IS_WINDOWS", True, raising=False)
    monkeypatch.setattr(Path, "lstat", lambda _path: path_info)
    monkeypatch.setattr(os, "fstat", lambda _fd: handle_info)

    if replacement:
        with pytest.raises(ValueError, match="changed while opening"):
            _ = item.fingerprint()
    else:
        digest = hashlib.sha256(content).hexdigest()
        assert item.fingerprint() == f"3169441117:1125899907079812:33279:2:100:200:1:{digest}"


@pytest.mark.parametrize("preexisting", [True, False])
def test_install_staged_uv_records_only_new_destination(tmp_path: Path, preexisting: bool) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    staged = tmp_path / "staging/uv.exe"
    staged.parent.mkdir()
    _ = staged.write_bytes(b"staged")
    uv = tmp_path / "bin/uv.exe"
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
