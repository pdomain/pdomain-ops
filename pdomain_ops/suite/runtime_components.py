"""One identity format for the Windows Visual C++ Redistributable."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import TYPE_CHECKING, cast
from uuid import UUID

from pdomain_ops.suite.components import ComponentProbe

if TYPE_CHECKING:
    from collections.abc import Callable

    from pdomain_ops.suite.components import Component, ComponentRegistry


@dataclass(frozen=True)
class RuntimeRegistration:
    """The package Windows registered for the x64 runtime."""

    package_id: str
    version: str
    architecture: str
    uninstall_path: str | None

    @classmethod
    def from_json(cls, raw: str) -> RuntimeRegistration:
        """Parse the structured Windows registration probe."""
        value: object = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError("Invalid Windows runtime registration")
        entry = cast("dict[str, object]", value)
        package_id = entry.get("PackageId")
        version = entry.get("Version")
        architecture = entry.get("Architecture")
        uninstall_path = entry.get("UninstallPath")
        if (
            not isinstance(package_id, str)
            or str(UUID(package_id)) != package_id
            or not isinstance(version, str)
            or re.fullmatch(r"14\.[0-9]+\.[0-9]+(?:\.[0-9]+)?", version) is None
            or architecture != "x64"
        ):
            raise ValueError("Invalid Windows runtime package identity")
        if uninstall_path is not None and (
            not isinstance(uninstall_path, str)
            or not PureWindowsPath(uninstall_path).is_absolute()
            or PureWindowsPath(uninstall_path).name.casefold() != "vc_redist.x64.exe"
        ):
            raise ValueError("Invalid Windows runtime uninstall path")
        return cls(package_id, version, "x64", uninstall_path)

    @property
    def identity(self) -> str:
        """Return the architecture and bundle ID."""
        return f"{self.architecture}:{self.package_id}"

    @property
    def fingerprint(self) -> str:
        """Bind the record to the registered package version and uninstaller."""
        return json.dumps(
            {
                "PackageId": self.package_id,
                "Version": self.version,
                "Architecture": self.architecture,
                "UninstallPath": self.uninstall_path,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def record_runtime_use(
    registry: ComponentRegistry,
    app: str,
    package: RuntimeRegistration,
    *,
    installed_here: bool = False,
) -> Component | None:
    """Record a verified new install or claim a previously recorded package."""

    def probe() -> str:
        return package.fingerprint

    if installed_here:
        return registry.record_created(
            app,
            "installer",
            ComponentProbe("vc-runtime", package.identity, probe),
            package.fingerprint,
        )
    return registry.acquire("vc-runtime", package.identity, app, "installer", probe=probe)


def preview_runtime_cleanup(
    registry: ComponentRegistry, app: str, package: RuntimeRegistration
) -> bool:
    """Return whether the registered path and last claim permit a preview."""
    return package.uninstall_path is not None and any(
        component.kind == "vc-runtime"
        and component.identity == package.identity
        and component.fingerprint == package.fingerprint
        and component.claims == (app,)
        for component in registry.list()
    )


def remove_runtime(
    registry: ComponentRegistry,
    app: str,
    package: RuntimeRegistration,
    *,
    probe: Callable[[], RuntimeRegistration | None],
    uninstall: Callable[[RuntimeRegistration], bool],
    siblings_safe: Callable[[], bool],
) -> bool:
    """Remove the confirmed package only if its registration and last claim match."""
    if package.uninstall_path is None:
        return False

    def fingerprint() -> str | None:
        current = probe()
        return current.fingerprint if current is not None else None

    return registry.remove(
        "vc-runtime",
        package.identity,
        app,
        fingerprint,
        lambda: uninstall(package),
        expected_fingerprint=package.fingerprint,
        siblings_safe=siblings_safe,
    )
