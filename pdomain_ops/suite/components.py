"""Provenance and claims for components installed by pdomain products."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, TypeVar, cast

from filelock import FileLock

from pdomain_ops.suite.paths import suite_data_dir

if TYPE_CHECKING:
    from collections.abc import Callable

_Result = TypeVar("_Result")


@dataclass(frozen=True)
class ComponentProbe:
    """An exact component to inspect before and after an installer action."""

    kind: str
    identity: str
    fingerprint: Callable[[], str | None]


@dataclass(frozen=True)
class Component:
    """An exact installed component and its pdomain consumers."""

    kind: str
    identity: str
    fingerprint: str
    installed_by: str
    source: str
    claims: tuple[str, ...]


class ComponentRegistry:
    """Serialize component acquisition and cleanup across cooperating processes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else suite_data_dir() / "components.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(str(self.path.with_suffix(".lock")), timeout=120)

    def _read(self) -> dict[tuple[str, str], Component]:
        try:
            raw: object = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(raw, dict):
            raise TypeError("Invalid component registry")
        header = cast("dict[str, object]", raw)
        rows = header.get("components")
        if header.get("version") != 1 or not isinstance(rows, list):
            raise ValueError("Invalid component registry")
        result: dict[tuple[str, str], Component] = {}
        for row in cast("list[object]", rows):
            if not isinstance(row, dict):
                raise TypeError("Invalid component registry entry")
            match cast("dict[str, object]", row):
                case {
                    "kind": str(kind),
                    "identity": str(identity),
                    "fingerprint": str(fingerprint),
                    "installed_by": str(installed_by),
                    "source": str(source),
                    "claims": claims,
                }:
                    if not isinstance(claims, list):
                        raise TypeError("Invalid component claims")
                    raw_claims = cast("list[object]", claims)
                    parsed_claims = tuple(claim for claim in raw_claims if isinstance(claim, str))
                    if len(parsed_claims) != len(raw_claims):
                        raise ValueError("Invalid component claims")
                    key = kind, identity
                    if key in result:
                        raise ValueError("Duplicate component registry entry")
                    result[key] = Component(
                        kind, identity, fingerprint, installed_by, source, parsed_claims
                    )
                case _:
                    raise ValueError("Invalid component registry entry")
        return result

    def _write(self, records: dict[tuple[str, str], Component]) -> None:
        if not records:
            self.path.unlink(missing_ok=True)
            return
        payload = {"version": 1, "components": [asdict(records[key]) for key in sorted(records)]}
        with NamedTemporaryFile(dir=self.path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                _ = stream.write(json.dumps(payload, indent=2).encode("utf-8") + b"\n")
                stream.close()
                _ = temporary.replace(self.path)
            finally:
                temporary.unlink(missing_ok=True)

    def list(self) -> tuple[Component, ...]:
        """Read the current records for preview. Removal rechecks them."""
        with self._lock:
            return tuple(self._read().values())

    def record_created(
        self, app: str, source: str, probe: ComponentProbe, expected: str
    ) -> Component | None:
        """Record an exact instance created by a verified bootstrap operation."""
        with self._lock:
            records = self._read()
            key = probe.kind, probe.identity
            if probe.fingerprint() != expected or key in records:
                return None
            record = Component(probe.kind, probe.identity, expected, app, source, (app,))
            records[key] = record
            self._write(records)
            return record

    def acquire(
        self,
        kind: str,
        identity: str,
        app: str,
        source: str,
        *,
        probe: Callable[[], str | None],
        install: Callable[[], object] | None = None,
    ) -> Component | None:
        """Claim a known instance or install a missing instance while locked.

        The probe returns an exact fingerprint or None for absence. It must
        raise if presence cannot be determined. Unknown present instances
        receive no claim.
        """
        with self._lock:
            records = self._read()
            key = kind, identity
            current = records.get(key)
            fingerprint = probe()
            if fingerprint is None:
                if install is None:
                    return None
                _ = install()
                fingerprint = probe()
                if fingerprint is None:
                    raise RuntimeError(
                        "Component installation did not produce the expected instance"
                    )
                prior_claims = current.claims if current is not None else ()
                claims = tuple(sorted({*prior_claims, app}))
                current = Component(kind, identity, fingerprint, app, source, claims)
            elif current is None or current.fingerprint != fingerprint:
                return None
            elif app not in current.claims:
                current = replace(current, claims=tuple(sorted((*current.claims, app))))
            records[key] = current
            self._write(records)
            return current

    def release(
        self,
        app: str,
        *,
        uninstall: Callable[[], object] | None = None,
        cleanup: Callable[[], object] | None = None,
    ) -> None:
        """Uninstall, optionally clean shared components, then release claims."""
        if cleanup is not None and uninstall is None:
            raise ValueError("Cleanup requires an application uninstall")
        with self._lock:
            records = self._read()
            if uninstall is not None:
                _ = uninstall()
            try:
                if cleanup is not None:
                    _ = cleanup()
            finally:
                # A cleanup callback can remove records via this same lock.
                if cleanup is not None:
                    records = self._read()
                self._write(
                    {
                        key: replace(
                            record, claims=tuple(claim for claim in record.claims if claim != app)
                        )
                        for key, record in records.items()
                    }
                )

    def acquire_batch(
        self,
        app: str,
        source: str,
        probes: tuple[ComponentProbe, ...],
        install: Callable[[], _Result],
    ) -> _Result:
        """Track exact entries created by an operation that fetches several files."""
        with self._lock:
            records = self._read()
            before: list[tuple[ComponentProbe, str | None]] = []
            for probe in probes:
                try:
                    before.append((probe, probe.fingerprint()))
                except (OSError, ValueError):
                    # An unverifiable entry is never evidence of absence.
                    continue
            result = install()
            for probe, previous in before:
                try:
                    fingerprint = probe.fingerprint()
                except (OSError, ValueError):
                    continue
                if fingerprint is None:
                    continue
                key = probe.kind, probe.identity
                current = records.get(key)
                if previous is None:
                    prior = current.claims if current is not None else ()
                    claims = tuple(sorted({*prior, app}))
                    records[key] = Component(
                        probe.kind, probe.identity, fingerprint, app, source, claims
                    )
                elif current is not None and current.fingerprint == previous == fingerprint:
                    records[key] = replace(current, claims=tuple(sorted({*current.claims, app})))
            self._write(records)
            return result

    def remove(
        self,
        kind: str,
        identity: str,
        app: str,
        probe: Callable[[], str | None],
        uninstall: Callable[[], object],
        *,
        expected_fingerprint: str,
        siblings_safe: Callable[[], bool],
    ) -> bool:
        """Remove the exact instance if the requesting app is its sole claimant."""
        with self._lock:
            records = self._read()
            key = kind, identity
            record = records.get(key)
            if (
                record is None
                or record.claims != (app,)
                or record.fingerprint != expected_fingerprint
                or not siblings_safe()
                or probe() != expected_fingerprint
            ):
                return False
            if uninstall() is False:
                return False
            if probe() is not None:
                raise RuntimeError("Component removal did not remove the expected instance")
            del records[key]
            self._write(records)
            return True
