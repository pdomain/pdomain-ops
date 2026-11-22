"""Verify uv can remove just one exact managed Python build."""

import shutil
import subprocess
from pathlib import Path

import pytest

from pdomain_ops.suite.component_files import ComponentFile
from pdomain_ops.suite.components import ComponentRegistry
from pdomain_ops.suite.python_components import (
    ManagedPython,
    claim_existing_tools,
    uv_installed_build,
)


def test_uv_output_distinguishes_install_from_reuse() -> None:
    key = "cpython-3.13.14-linux-x86_64-gnu"
    assert uv_installed_build(f"Installed Python 3.13.14 in 1s\n + {key}\n") == key
    assert uv_installed_build("Python 3.13.14 is already installed\n") is None
    assert uv_installed_build(f"Installed Python 3.13.14 in 1s\n + {key}\n + {key}\n") is None


@pytest.mark.parametrize("names", [("uv", "uvx"), ("uv.exe", "uvx.exe", "uvw.exe")])
def test_reuse_claims_only_previously_recorded_tools(
    tmp_path: Path, names: tuple[str, ...]
) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    items = tuple(ComponentFile(tmp_path / name) for name in names)
    root = tmp_path / "managed"
    executable = root / "cpython-3.13.14-linux-x86_64-gnu/bin/python3.13"
    executable.parent.mkdir(parents=True)
    executable.touch()
    for item in items:
        assert (
            registry.acquire(
                "uv",
                item.identity,
                "gui",
                "installer",
                probe=item.fingerprint,
                install=item.path.touch,
            )
            is not None
        )
    claims = claim_existing_tools(registry, "cli", items[0].path, root, executable)
    assert {claim.identity for claim in claims} == {item.identity for item in items}
    for claim in claims:
        assert claim.kind == "uv"
        assert claim.installed_by == "gui"
        assert claim.claims == ("cli", "gui")
    external_uv = tmp_path / "external" / names[0]
    external_uv.parent.mkdir()
    external_uv.touch()
    assert claim_existing_tools(registry, "cli", external_uv, root, executable) == ()


def test_uv_removes_only_exact_managed_build(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    root = tmp_path / "managed"
    key = "cpython-3.13.14-linux-x86_64-gnu"
    executable = root / key / "bin/python3.13"
    executable.parent.mkdir(parents=True)
    executable.touch()
    sibling = root / "cpython-3.13.13-linux-x86_64-gnu"
    sibling.mkdir()
    component = ManagedPython(root, key, executable)
    fingerprint = component.fingerprint()
    assert fingerprint is not None
    component.remove(
        Path(uv), fingerprint, run=lambda argv: subprocess.run(argv, check=True, timeout=15)
    )
    assert component.fingerprint() is None
    assert sibling.is_dir()


def test_managed_python_rejects_alias_and_external_interpreter(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exact uv build"):
        _ = ManagedPython(tmp_path, "3.13", tmp_path / "system/python")
    with pytest.raises(ValueError, match="outside"):
        _ = ManagedPython(tmp_path, "cpython-3.13.14-linux-x86_64-gnu", tmp_path / "system/python")


def test_stages_cleanup_python_outside_verified_build(tmp_path: Path) -> None:
    root = tmp_path / "managed"
    key = "cpython-3.13.14-windows-x86_64-none"
    executable = root / key / "python.exe"
    executable.parent.mkdir(parents=True)
    _ = executable.write_bytes(b"fixture interpreter")
    component = ManagedPython(root, key, executable)
    fingerprint = component.fingerprint()
    assert fingerprint is not None
    with pytest.raises(ValueError, match="outside the managed build"):
        _ = component.stage_cleanup_interpreter(executable.parent / "copy", fingerprint)
    staged = component.stage_cleanup_interpreter(tmp_path / "scratch", fingerprint)
    executable.unlink()
    assert staged.read_bytes() == b"fixture interpreter"
    with pytest.raises(ValueError, match="interpreter is missing"):
        _ = component.stage_cleanup_interpreter(tmp_path / "another-scratch", fingerprint)
