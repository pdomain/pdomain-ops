---
Status: active
Owner: CT
Created: 2026-05-19
Last verified: 2026-11-07
Kind: usage
---

# pdomain-ops

`pdomain-ops` provides suite plumbing, shared preferences, and GPU dispatch
adapters for the pdomain-* suite through a library and a small CLI.

The library is not a daemon. It runs in-process inside each pdomain-* app's
FastAPI server and provides:

- **Suite registry** (`installed.toml`): apps self-register so the AppShell launcher
  can discover and spawn siblings.
- **Shared UI preferences** (`ui-prefs.json`): cross-app theme, density, accent color,
  layer colors, and per-app extension blobs.
- **Sibling launcher**: spawns sibling apps by binary, polls `/healthz`, and
  reports the URL.
- **Auth and storage adapters**: `NoAuthAdapter` and local filesystem storage.
  Cloud backends remain deferred.
- **GPU dispatch adapters**: `StageDispatcher` for short page-level calls,
  `LongJobRunner` (SQLite-backed) for training runs and batch jobs.

## Mount suite routes

```python
from fastapi import FastAPI
from pdomain_ops import mount_routes

app = FastAPI()
mount_routes(app)  # adds /api/suite/*
```

## Dynamic-port SPA bootstrap

Single-page applications (SPAs) use `find_available_port` to select an available
port when the preferred port is already taken. Selection does not reserve the
port, so another process can take it before the server binds. They use
`register_self(actual_port=port)` to record the real port in the suite
registry:

```python
import uvicorn
from pdomain_ops.suite import find_available_port, register_self

PREFERRED_PORT = 8004


def main() -> None:
    port = find_available_port(PREFERRED_PORT)
    register_self(_caller_package="pdomain_ocr_simple_gui", actual_port=port)
    uvicorn.run(app, host="127.0.0.1", port=port)
```

For the full pattern and its limits, see
[`docs/usage/dynamic-port-bootstrap.md`](docs/usage/dynamic-port-bootstrap.md).

## JSON Schema for downstream codegen

```sh
uv run python -m pdomain_ops.schemas > schemas.json
```

The registration surface is `pdomain_ops/schemas/emit.py::PUBLIC_MODELS`.

## Design history and shipped GPU dispatch

The shipped design is documented in
[shared suite services](docs/architecture/suite-services.md) and
[batched OCR dispatch](docs/architecture/batched-ocr-dispatch.md).

Phase 1.7 shipped in v0.2.0. It moved `pdomain-prep-for-pgdp`'s GPU dispatch
primitives (`ModalStageDispatcher`, `SharedContainerStageDispatcher`, and
`register_default_stages()`) into `pdomain-ops`. Callers use
`register_default_stages()` to register DocTR and Tesseract OCR stages on a
local dispatcher.

## Verification evidence

Checked against source and test coverage on 2026-11-07:

- `pdomain_ops/suite/types.py`, `auth.py`, `storage.py`, and `routes.py`;
  `tests/suite/test_auth.py`, `test_storage.py`, and `test_mount_routes_signature.py`.
- `pdomain_ops/suite/ports.py` and `register_self.py`;
  `tests/suite/test_ports.py` and `test_register_self.py`.
- `pdomain_ops/gpu/default_stages.py` and `schemas/emit.py`;
  `tests/gpu/test_default_stages.py` and `tests/test_schemas_emit.py`.

## Repository entry points

- [Release history](CHANGELOG.md)
- [Canonical agent guidance](AGENTS.md)
- [Claude compatibility entry point](CLAUDE.md)
- [Codex docgraph entry point](CODEX.md)
