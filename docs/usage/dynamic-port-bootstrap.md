---
Status: active
Owner: CT
Created: 2026-05-31
Last verified: 2026-11-07
Kind: usage
---

# Dynamic-port SPA bootstrap

## Agent Index

- **Kind:** usage
- **Status:** active
- **Read when:** adopting dynamic-port startup in a suite SPA.
- **Search terms:** dynamic port, find available port, register self, SPA bootstrap.

## Problem

pdomain-* SPAs use a fixed port by default (e.g. simple-gui = 8004). If
something else on the machine already binds that port, the app crashes at
startup with `OSError: [Errno 98] Address already in use`. A hardcoded
fallback port moves the same collision risk to that port.

## Solution

`pdomain_ops.suite` provides two helpers that work together:

- `find_available_port(preferred, host, max_attempts)` — probes the
  preferred port, then checks higher ports until it finds a free one.
- `register_self(..., actual_port=port)` — records the port that the app
  binds in the suite registry. Cross-app links then use the correct address.

## Canonical bootstrap snippet

```python
import uvicorn
from pdomain_ops.suite import find_available_port, register_self

PREFERRED_PORT = 8004


def main() -> None:
    port = find_available_port(PREFERRED_PORT)
    register_self(
        _caller_package="pdomain_ocr_simple_gui",
        actual_port=port,
    )
    uvicorn.run("pdomain_ocr_simple_gui.app:app", host="127.0.0.1", port=port)
```

`find_available_port` uses a temporary `socket.bind` probe with
`SO_REUSEADDR=0`. The probe therefore reflects whether the OS considers the
port free. It always closes the probe socket before returning, and uvicorn
then binds the port for real.

Another process can claim the port between the probe and uvicorn's bind.
The helper does not reserve the port or retry server startup. If the bind
fails, the caller must probe again, update the registry, and retry startup.
A second probe still cannot reserve the port.

`bootstrap_spa(preferred=..., caller_package=...)` combines port selection,
best-effort registration, and startup URL output. It returns the selected
port for the caller to bind. It logs registration failures and continues;
direct `register_self` calls in the snippet above propagate those failures.

## Notes for stage-2 SPA consumers

When adopting this pattern in `pdomain-ocr-simple-gui`,
`pdomain-prep-for-pgdp`, `pdomain-ocr-labeler-spa`, and the trainer SPA:

1. Import `find_available_port` and `register_self` from
   `pdomain_ops.suite`.
2. Call `find_available_port(PREFERRED_PORT)` before `uvicorn.run`.
3. Pass the result to both `register_self(actual_port=port)` and
   `uvicorn.run(..., port=port)`.
4. Set the `_caller_package` argument to the top-level Python package name
   (e.g. `"pdomain_ocr_simple_gui"`), not the distribution name.
5. If the app already calls `register_self` without `actual_port`, add the
   parameter. The default (`None`) is backward-compatible.

## Evidence

- **Code:** `pdomain_ops/suite/ports.py`,
  `pdomain_ops/suite/register_self.py`, `pdomain_ops/suite/bootstrap.py`,
  `pdomain_ops/suite/__init__.py`.
- **Tests:** `tests/suite/test_ports.py`,
  `tests/suite/test_register_self.py`, `tests/suite/test_bootstrap.py`.
- **Verified:** 2026-11-07 by reading the helper implementations and tests for
  occupied ports, exhausted attempts, registry port overrides, and nonfatal
  registration failures. This does not establish adoption in every sibling SPA.
