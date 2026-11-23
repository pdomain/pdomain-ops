"""Shared component ownership contract."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from pdomain_ops.suite.components import ComponentProbe, ComponentRegistry


def test_external_component_cannot_be_claimed(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    component = tmp_path / "uv"
    _ = component.write_text("external")

    def probe() -> str | None:
        return component.read_text() if component.exists() else None

    assert (
        registry.acquire("uv", str(component), "cli", "setup", probe=probe, install=component.touch)
        is None
    )
    assert not registry.remove(
        "uv",
        str(component),
        "cli",
        probe,
        component.unlink,
        expected_fingerprint="fixture",
        siblings_safe=lambda: True,
    )
    assert component.read_text() == "external"


def test_record_created_requires_the_captured_instance(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    component = tmp_path / "python"
    _ = component.write_text("replacement")
    probe = ComponentProbe("python", str(component), component.read_text)
    assert registry.record_created("cli", "installer", probe, "original") is None
    acquired = registry.record_created("gui", "installer", probe, "replacement")
    assert acquired is not None
    assert registry.record_created("cli", "installer", probe, "replacement") is None
    assert registry.list() == (acquired,)


def test_last_claimant_can_remove_after_original_installer_leaves(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    component = tmp_path / "uv"

    def probe() -> str | None:
        return "fixture" if component.exists() else None

    first = registry.acquire(
        "uv", str(component), "cli", "setup", probe=probe, install=component.touch
    )
    assert first is not None
    assert first.installed_by == "cli"
    second = registry.acquire(
        "uv", str(component), "gui", "setup", probe=probe, install=component.touch
    )
    assert second is not None
    assert second.claims == ("cli", "gui")
    assert not registry.remove(
        "uv",
        str(component),
        "cli",
        probe,
        component.unlink,
        expected_fingerprint="fixture",
        siblings_safe=lambda: True,
    )
    registry.release("cli")
    assert registry.remove(
        "uv",
        str(component),
        "gui",
        probe,
        component.unlink,
        expected_fingerprint="fixture",
        siblings_safe=lambda: True,
    )
    assert not component.exists()
    assert not (tmp_path / "components.json").exists()


def test_concurrent_acquisitions_install_once(tmp_path: Path) -> None:
    path = tmp_path / "components.json"
    component = tmp_path / "uv"
    entered = Event()
    finish = Event()
    sibling_started = Event()

    def probe() -> str | None:
        return "fixture" if component.exists() else None

    def install() -> None:
        entered.set()
        assert finish.wait(timeout=5)
        component.touch()

    def claim_sibling() -> object:
        sibling_started.set()
        return ComponentRegistry(path).acquire("uv", str(component), "gui", "setup", probe=probe)

    with ThreadPoolExecutor(max_workers=2) as pool:
        installer = pool.submit(
            ComponentRegistry(path).acquire,
            "uv",
            str(component),
            "cli",
            "setup",
            probe=probe,
            install=install,
        )
        try:
            assert entered.wait(timeout=5)
            sibling = pool.submit(claim_sibling)
            assert sibling_started.wait(timeout=5)
        finally:
            finish.set()
        assert installer.result(timeout=5) is not None
        assert sibling.result(timeout=5) is not None

    (record,) = ComponentRegistry(path).list()
    assert record.claims == ("cli", "gui")
    assert record.installed_by == "cli"


def test_download_batch_claims_new_and_known_entries_only(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    existing = tmp_path / "external"
    managed = tmp_path / "managed"
    absent = tmp_path / "optional"
    existing.touch()

    def download() -> Path:
        managed.touch()
        return managed

    probes = tuple(
        ComponentProbe("model", str(path), lambda path=path: "present" if path.exists() else None)
        for path in (existing, managed, absent)
    )
    assert registry.acquire_batch("cli", "setup", probes, download) == managed
    assert registry.acquire_batch("gui", "reuse", probes, download) == managed
    (record,) = registry.list()
    assert record.identity == str(managed)
    assert record.installed_by == "cli"
    assert record.claims == ("cli", "gui")


def test_download_keeps_unverifiable_entries_unclaimed(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    known = tmp_path / "known"
    redirected = tmp_path / "redirected"

    def unresolved() -> str | None:
        raise ValueError("Untrusted cache location")

    def redirect_after_install() -> str | None:
        if redirected.exists():
            raise OSError("New cache link targets another directory")
        return None

    def install() -> None:
        known.touch()
        redirected.touch()

    registry.acquire_batch(
        "cli",
        "setup",
        (
            ComponentProbe("model", "external", unresolved),
            ComponentProbe("model", str(redirected), redirect_after_install),
            ComponentProbe("model", str(known), lambda: "present" if known.exists() else None),
        ),
        install,
    )
    assert redirected.exists()
    (record,) = registry.list()
    assert record.identity == str(known)


def test_failed_app_uninstall_keeps_component_claim(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    path = tmp_path / "component"

    def probe() -> str | None:
        return "fixture" if path.exists() else None

    acquired = registry.acquire("uv", str(path), "cli", "setup", probe=probe, install=path.touch)
    assert acquired is not None

    def fail() -> None:
        raise RuntimeError("Uninstall failed")

    with pytest.raises(RuntimeError, match="Uninstall failed"):
        registry.release("cli", uninstall=fail)
    assert registry.list() == (acquired,)
    registry.release("cli", uninstall=lambda: None)
    (record,) = registry.list()
    assert record.claims == ()
    assert record.installed_by == "cli"


def test_cleanup_rechecks_claim_after_waiting_for_concurrent_acquisition(tmp_path: Path) -> None:
    path = tmp_path / "components.json"
    model = tmp_path / "model"
    registry = ComponentRegistry(path)
    probing = Event()
    finish = Event()
    removal_started = Event()

    def probe() -> str | None:
        return "fixture" if model.exists() else None

    def sibling_probe() -> str | None:
        probing.set()
        assert finish.wait(timeout=5)
        return probe()

    def remove() -> bool:
        removal_started.set()
        return ComponentRegistry(path).remove(
            "model",
            str(model),
            "cli",
            probe,
            model.unlink,
            expected_fingerprint="fixture",
            siblings_safe=lambda: True,
        )

    assert (
        registry.acquire("model", str(model), "cli", "setup", probe=probe, install=model.touch)
        is not None
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        sibling = pool.submit(
            ComponentRegistry(path).acquire,
            "model",
            str(model),
            "gui",
            "setup",
            probe=sibling_probe,
        )
        try:
            assert probing.wait(timeout=5)
            cleanup = pool.submit(remove)
            assert removal_started.wait(timeout=5)
        finally:
            finish.set()
        assert sibling.result(timeout=5) is not None
        assert not cleanup.result(timeout=5)
    assert model.exists()


def test_app_uninstall_cleans_component_before_releasing_claim(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    app = tmp_path / "app"
    uv = tmp_path / "uv"
    app.touch()

    def probe() -> str | None:
        return "fixture" if uv.exists() else None

    assert (
        registry.acquire("uv", str(uv), "cli", "setup", probe=probe, install=uv.touch) is not None
    )

    def cleanup() -> None:
        assert not app.exists()
        assert registry.remove(
            "uv",
            str(uv),
            "cli",
            probe,
            uv.unlink,
            expected_fingerprint="fixture",
            siblings_safe=lambda: True,
        )

    registry.release("cli", uninstall=app.unlink, cleanup=cleanup)
    assert not uv.exists()
    assert registry.list() == ()
