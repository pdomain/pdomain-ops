---
Status: active
Owner: CT
Created: 2026-09-13
Last verified: 2026-09-13
Kind: issue
---

# The device probe raises instead of reporting when the GPU is full

## Agent Index

- **Kind:** issue
- **Status:** active
- **Owner:** CT
- **Last verified:** 2026-09-13
- **Severity:** High. Every suite application serves a 500 from its device route on a busy GPU.
- **Read when:** a test fails with a CUDA out-of-memory error, the device route returns 500, or you are deciding what can be verified without a free GPU.
- **Search terms:** CUDA out of memory, AcceleratorError, device probe, mem_get_info, suite device route, GPU saturated, vram_free_mb.

## Summary

`_probe_cuda` in `pdomain_ops/gpu/device_probe.py` catches only `ImportError`. Every CUDA call below that guard is unprotected. When the card has no free memory, creating the CUDA context raises `torch.AcceleratorError` and the exception escapes the probe, the `/api/suite/device` route, and any caller asking what hardware is present.

Asking which devices exist should never fail because one of them is busy. The probe should report the device as unavailable and say why.

There is a second, smaller problem in the same function. It sets `available=True` for every device it finds, without consulting the free memory it just measured. A card with no free memory is reported as available.

## Evidence / motivation

Reproduced on 2026-09-13 with the card at 7743 MiB of 8192 MiB in use by unrelated work:

```text
AcceleratorError : CUDA error: out of memory
Search for `cudaErrorMemoryAllocation' ...
```

The failing path is short. `torch.cuda.is_available()` returns true, because the driver and device are present. The loop then calls `torch.cuda.mem_get_info(i)`, which initialises the CUDA context, which is the allocation that fails.

Three tests in `pdomain-ocr-simple-gui` fail because of this, all of them merely asking the route for a response:

- `tests/test_suite_device_update_routes.py::test_device_route_mounted`
- `tests/test_suite_device_update_routes.py::test_routes_not_shadowed_by_spa_catchall`
- `tests/test_app_suite_mount.py::test_device_put_persists_under_real_app_id`

These were confirmed pre-existing, not caused by the dependency upgrade that uncovered them, by reverting to the pre-upgrade lockfile and reproducing the identical failures. The other 631 tests in that repository pass.

`pdomain-book-tools` already documents the case where no GPU exists, in `GPU_TESTING.md`, and that path skips cleanly. The case this issue describes is different: the GPU exists, the driver answers, and the memory is gone. Nothing handles it.

## What cannot be verified while the card is full

This is the honest list of work that needs a free GPU, so it is not mistaken for work that is failing.

**Blocked outright.** The three tests above, and anything else that reaches a real device probe rather than a mocked one.

**Blocked by intent, and unaffected by this bug.** These need real GPU capacity rather than a working probe:

- `make test-slow` in `pdomain-book-tools`, which downloads models and runs them.
- `make test-integration` and `make test-layout-integration` in `pdomain-ocr-cli`, which run real layout detection.
- `make integration` in `pdomain-ocr-labeler-spa`, a real DocTR pipeline of roughly ten minutes.
- `make e2e-real-ocr` in `pdomain-ocr-simple-gui`.
- Any DocTR training or evaluation run in `pdomain-ocr-training`.

**Not blocked, despite involving GPU code.** The `tests/gpu/` tree in this repository guards on availability and runs without a card, as does everything in `pdomain-book-tools` covered by `GPU_TESTING.md`. The ordinary `make ci` in every repository passes on a saturated card, with the single exception of the three tests named above.

**Not GPU work at all.** Nothing on the page-layout OCR critical path needs a local GPU right now. Region proposals, the review surface, and the geometry engine are all processor work. Training a layout model does need one, and the existing plan already puts that on rented cloud hardware rather than this machine, whose card is an 8 GB laptop part.

## Outcome / acceptance criteria

1. `_probe_cuda` returns a list rather than raising, whatever state the card is in. A device it cannot interrogate is reported with `available=False` and a populated `reason`.
2. `available` reflects measured free memory rather than being hardcoded true.
3. A test proves both, by simulating a raising `mem_get_info` rather than by needing a full card.
4. The three `pdomain-ocr-simple-gui` tests pass on a saturated GPU.

## Dependencies

None. The fix is contained in one function, and `DeviceInfoEntry` already carries the `reason` field it needs.

## Next steps

1. Widen the guard in `_probe_cuda` to cover the whole loop body, not just the import.
2. Decide the threshold below which a device is reported unavailable rather than merely low. Zero free memory is clearly unavailable; the rest is a judgment the batch-size code may already imply.
3. Add the simulated-failure test.
4. Re-run the three `pdomain-ocr-simple-gui` tests to confirm.

## Resolution

Open.
