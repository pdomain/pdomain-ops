"""Legacy OCR installations protect shared components on macOS."""

from pathlib import Path

import pytest

from pdomain_ops.suite.component_siblings import macos_ocr_sibling_absent, other_uv_tools_absent


@pytest.mark.parametrize("marker", ["tool", "app", "registry", "broken-launcher"])
def test_macos_cleanup_is_blocked_by_legacy_sibling(tmp_path: Path, marker: str) -> None:
    home = tmp_path / "home"
    tools = tmp_path / "tools"
    bin_dir = tmp_path / "bin"
    applications = tmp_path / "Applications"
    installed = tmp_path / "installed.toml"
    for folder in (home, tools, bin_dir, applications):
        folder.mkdir()

    def safe() -> bool:
        return macos_ocr_sibling_absent(
            "pdomain-ocr-cli",
            home=home,
            tool_dir=tools,
            bin_dir=bin_dir,
            system_applications=applications,
            installed_apps=installed,
        )

    assert safe()
    if marker == "tool":
        (tools / "pdomain-ocr-simple-gui").mkdir()
    elif marker == "app":
        (applications / "OCR Simple GUI.app").mkdir()
    elif marker == "registry":
        _ = installed.write_text('[apps."pdomain-ocr-simple-gui"]\nbinary = "/custom/GUI"\n')
    else:
        (bin_dir / "pdomain-ocr-simple-gui").symlink_to(tmp_path / "missing")
    assert not safe()


def test_auxiliary_uv_tool_prevents_dependency_cleanup(tmp_path: Path) -> None:
    current = tmp_path / "tools"
    defaults = tmp_path / "defaults"
    current.mkdir()
    defaults.mkdir()
    (current / "pdomain-ocr-cli").mkdir()
    (current / ".lock").touch()
    roots = (current, defaults)
    assert other_uv_tools_absent(roots, departing_tool="pdomain-ocr-cli")
    assert not other_uv_tools_absent(roots)
    (defaults / "external-tool").mkdir()
    assert not other_uv_tools_absent(roots, departing_tool="pdomain-ocr-cli")


def test_cli_in_use_lock_is_only_ignored_when_idle(tmp_path: Path) -> None:
    fcntl = pytest.importorskip("fcntl")
    lock = tmp_path / ".pdomain-ocr-cli.in-use.lock"
    lock.touch()
    assert other_uv_tools_absent((tmp_path,))
    with lock.open("rb") as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        assert not other_uv_tools_absent((tmp_path,))
    assert other_uv_tools_absent((tmp_path,))
