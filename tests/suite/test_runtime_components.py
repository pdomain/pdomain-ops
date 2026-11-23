"""The Windows runtime record is shared between OCR products."""

from pathlib import Path

from pdomain_ops.suite.components import ComponentRegistry
from pdomain_ops.suite.runtime_components import (
    RuntimeRegistration,
    preview_runtime_cleanup,
    record_runtime_use,
    remove_runtime,
)


def test_runtime_claim_keeps_origin_and_does_not_adopt_unknown_package(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    package = RuntimeRegistration.from_json(
        '{"PackageId":"11111111-1111-1111-1111-111111111111",'
        '"Version":"14.44.35211.0","Architecture":"x64","UninstallPath":null}'
    )
    assert record_runtime_use(registry, "cli", package) is None
    created = record_runtime_use(registry, "gui", package, installed_here=True)
    assert created is not None
    shared = record_runtime_use(registry, "cli", package)
    assert shared is not None
    assert shared.installed_by == "gui"
    assert shared.claims == ("cli", "gui")


def test_runtime_cleanup_requires_last_claim_matching_preview_and_consent(tmp_path: Path) -> None:
    registry = ComponentRegistry(tmp_path / "components.json")
    registration = RuntimeRegistration(
        "11111111-1111-1111-1111-111111111111",
        "14.44.35211.0",
        "x64",
        r"C:\ProgramData\Package Cache\runtime\VC_redist.x64.exe",
    )
    assert not preview_runtime_cleanup(registry, "cli", registration)
    assert record_runtime_use(registry, "cli", registration, installed_here=True) is not None
    assert preview_runtime_cleanup(registry, "cli", registration)
    current: RuntimeRegistration | None = registration

    def probe() -> RuntimeRegistration | None:
        return current

    def uninstall(_confirmed: RuntimeRegistration) -> bool:
        nonlocal current
        current = None
        return True

    assert not remove_runtime(
        registry,
        "cli",
        registration,
        probe=probe,
        uninstall=lambda _package: False,
        siblings_safe=lambda: True,
    )
    assert preview_runtime_cleanup(registry, "cli", registration)
    assert record_runtime_use(registry, "gui", registration) is not None
    assert not remove_runtime(
        registry, "cli", registration, probe=probe, uninstall=uninstall, siblings_safe=lambda: True
    )
    registry.release("gui")
    assert remove_runtime(
        registry, "cli", registration, probe=probe, uninstall=uninstall, siblings_safe=lambda: True
    )
    assert registry.list() == ()
