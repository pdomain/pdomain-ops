---
Status: built
Owner: CT
Created: 2026-07-13
Last verified: 2026-11-10
Kind: architecture
---

# Batched OCR dispatch

## Agent Index

- **Kind:** architecture
- **Status:** built
- **Read when:** changing DocTR batch sizing, local OCR dispatch, or OOM recovery.
- **Search terms:** batched OCR, DocTR, OOM backoff, StageDispatcher, predictor cache.

## Current behavior

`pdomain-ops` owns the application-neutral GPU boundary. This boundary covers
request and result types, device selection, stage registration, dispatcher
protocols, and local execution. Applications own product workflow, persistence,
and UI. A stage implementation receives the resolved device through the
dispatcher seam. It does not discover application state or reach into a sibling
repository.

Local OCR accepts batch requests through the stage-dispatch protocol. The worker
sizes DocTR detection and recognition batches for the selected device. It reuses
predictors by batch size and retries CUDA allocation failures with a smaller
detection batch. The worker returns page objects. The dispatcher serializes
results at its boundary.

The worker accepts image bytes or arrays, not filesystem paths. This design
keeps the dispatcher contract usable across local and remote transports. The
caller owns predictor caching and supplies any smaller-predictor builder. The
worker remains location-independent. If detection batch size 1 still exhausts
memory, the worker falls back to per-image CPU OCR. Non-memory failures surface
unchanged.

CPU and GPU use the same batched worker. Each batch runs in the event loop's
default executor; the dispatcher does not serialize concurrent batch calls.
Predictor lookup and construction go through `get_or_build_predictor`, which
builds each cache key once. Its single module lock covers the build but not the
OCR run, so batches stay concurrent. Cold builds for different keys take turns.
The dispatcher does its first lookup in the executor, so waiting for a build
does not block the event loop. A build that raises caches nothing and can be
retried. Callers must not assume
that dispatch enforces one active OCR job.
Consumer orchestration may split work into chunks to retain earlier results
when a later chunk fails. Chunk size and DocTR's internal detection batch size
remain separate controls.

Remote Modal and shared-container batch dispatch remain explicit, unsupported
stubs. A future implementation can use the existing request and protocol seam.
It is not part of the shipped local path.

## Ownership boundary

The package extends sibling applications through typed adapters. It does not
replace their orchestration or require one transport. The shipped path is local
dispatch with registered default stages. Remote Modal and shared-container
transports are unbuilt. Their stubs must not be described as available backends.

## Open calibration questions

- Real GPU measurements may justify changing the device-to-batch-size table.
- The single-image OCR protocol remains separate from the batch API until a
  consumer migration proves that removing it is safe.

## Evidence

- **Code:** `pdomain_ops/gpu/doctr_batch.py`, `pdomain_ops/gpu/device.py`,
  `pdomain_ops/gpu/protocols.py`, `pdomain_ops/gpu/types.py`,
  `pdomain_ops/gpu/local_stage.py`, `pdomain_ops/gpu/default_stages.py`
- **Tests:** `tests/gpu/test_doctr_batch.py`,
  `tests/gpu/test_pick_doctr_batch_sizes.py`,
  `tests/gpu/test_local_batch_dispatcher.py`,
  `tests/gpu/test_remote_batch_stubs.py`
- **Commits:** `8703224`, `eee600b`, `bcb369d`, `fa1ae94`, `2015ef5`
- **Salvaged sources:**
  `_tbd/ocr-container-docs/archive/plans/2026-05-16-pd-ocr-ops-new-repo.md`,
  `_tbd/ocr-container-docs/archive/plans/2026-05-16-phase-1-7-gpu-adapter-migration.md`,
  `_tbd/ocr-container-docs/specs/2026-05-16-cross-cut-design.md`
- **Verified:** 2026-11-07 by reading the source and focused tests above.
  These tests use OCR doubles; they do not measure real GPU capacity.
- **Verified:** 2026-11-10 by `tests/gpu/test_predictor_cache_concurrency.py`.
  Two threads racing on one cold key build one predictor at both call sites.
  The test uses a stand-in builder on CPU, not a real CUDA run.
