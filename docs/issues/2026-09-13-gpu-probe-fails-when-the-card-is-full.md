---
Status: active
Owner: CT
Created: 2026-09-13
Last verified: 2026-11-10
Kind: issue
---

# The device probe raises instead of reporting when the GPU is full

## Agent Index

- **Kind:** issue
- **Status:** active
- **Owner:** CT
- **Last verified:** 2026-11-10
- **Resolution:** Open. The probe fix is committed; acceptance criterion 4 is unverified.
- **Severity:** High. Mounted local device routes return a 500 when the CUDA probe raises during memory queries.
- **Read when:** a test fails with a CUDA out-of-memory error, the device route returns 500, or you are deciding what can be verified without a free GPU.
- **Search terms:** CUDA out of memory, AcceleratorError, device probe, mem_get_info, suite device route, GPU saturated, vram_free_mb.

## Summary

`_probe_cuda` in `pdomain_ops/gpu/device_probe.py` catches only `ImportError`. Every CUDA call below that guard is unprotected. When the card has no free memory, creating the CUDA context raises `torch.AcceleratorError` and the exception escapes the probe, the `/api/suite/device` route, and any caller asking what hardware is present.

Asking which devices exist should never fail because one of them is busy. The probe should report the device as unavailable and say why.

There is a second, smaller problem in the same function. It sets `available=True` for every device it finds, without consulting the free memory it just measured. A card with no free memory is reported as available.

## Fix status — 2026-11-10

The probe no longer raises when a CUDA memory query fails. Commit `9594e32`
made these changes:

- A device whose memory query raises is listed with `available=False` and the
  first line of the error as `reason`.
- A device with 0 MiB free is listed with `available=False` and the reason
  `No free GPU memory.`
- A failing `torch.cuda.is_available` or `device_count` call logs a warning and
  lists no CUDA devices.
- If the device name query also fails and the hardware scan finds as many cards
  as CUDA, the label comes from the scan, so `list_devices` does not list the
  card twice. Otherwise the label is `CUDA device N`.

Criteria 1 to 3 are met. `tests/gpu/test_device_probe.py` simulates each failure
with a fake `torch` module, so no card was used. Criterion 4 is not verified: the
three `pdomain-ocr-simple-gui` tests were not run, because they live in another
repository, need this fix in the `pdomain-ops` version that repository installs,
and need a saturated GPU. This issue stays open until they pass.

The sections below describe the code before this fix.

## Verification — 2026-11-07

The defect remains at `9234e21`: `_probe_cuda` in
`pdomain_ops/gpu/device_probe.py:33-53` still catches only the import error,
calls `mem_get_info` without an exception guard, and sets `available=True`.
`tests/gpu/test_device_probe.py` replaces `_probe_cuda` in probe tests; it
does not simulate a raising `mem_get_info`. This is a source and test review,
not a fresh saturated-GPU reproduction. The hardware measurements and suite
test totals below are the 2026-09-13 observations. They do not describe the
current host or establish that every current sibling gate passes.

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

**Not blocked, despite involving GPU code.** The `tests/gpu/` tree in this repository guards on availability and runs without a card, as does everything in `pdomain-book-tools` covered by `GPU_TESTING.md`. The 2026-09-13 investigation reported ordinary `make ci` passing in the repositories it checked, except for the three tests named above. That suite-wide result was not rerun on 2026-11-07.

**Not GPU work at all.** Nothing on the page-layout OCR critical path needs a local GPU right now. Region proposals, the review surface, and the geometry engine are all processor work. Training a layout model does need one, and the existing plan already puts that on rented cloud hardware rather than the 8 GB laptop GPU described by the original investigation.

## Outcome / acceptance criteria

1. `_probe_cuda` returns a list rather than raising, whatever state the card is in. A device it cannot interrogate is reported with `available=False` and a populated `reason`.
2. `available` reflects measured free memory rather than being hardcoded true.
3. A test proves both, by simulating a raising `mem_get_info` rather than by needing a full card.
4. The three `pdomain-ocr-simple-gui` tests pass on a saturated GPU.

## Dependencies

None. The fix is contained in one function, and `DeviceInfoEntry` already carries the `reason` field it needs.

## Next steps

1. Once `pdomain-ocr-simple-gui` installs a `pdomain-ops` version with this fix, re-run its three tests on a saturated GPU.
2. Optional: decide whether a card with little free memory should also be reported unavailable. The fix applies only the case this report calls clear, 0 MiB free. The batch-size code sets no minimum: `pick_doctr_batch_sizes` still uses a detection batch of 1 when free memory is below one page's estimate.

## Resolution

Open. The fix is in commit `9594e32`. Criterion 4 remains. See Fix status.
