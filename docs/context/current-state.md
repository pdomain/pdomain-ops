---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-11-07
Kind: context
---

# Current state

## Agent Index

- **Kind:** context
- **Status:** active
- **Last verified:** 2026-11-07
- **Read when:** starting work that depends on current repository documentation.
- **Search terms:** current state, remaining work, open issues, active plans.

## Remaining work

- The predictor cache is still an unguarded check-then-set. [Concurrent OCR jobs can each build a duplicate DocTR predictor](../issues/2026-08-08-predictor-cache-not-thread-safe.md)
- The CUDA probe still lets memory-query failures escape and marks queried CUDA devices available regardless of free memory. [The device probe raises instead of reporting when the GPU is full](../issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md)
- Weekly dep-refresh auto-land is still open. Commit `7ff9c7d` removed the GitHub workflows. Branch protection on master is off. Thirteen `dep-refresh/*` branches remain on origin. Closing the issue needs an owner decision. [Weekly dep-refresh cannot auto-land in this repo](../issues/2026-08-08-dep-refresh-cannot-auto-land.md)
- Book-contracts extraction still needs evidence for data rescue, digest compatibility of stored artifacts, and repository retirement. The package move and checked consumer repoints exist. [Extract Book Contracts and Retire the pd- Repos](../plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md)
- The suite work order still needs proof of production proposal wiring, accepted corpus quality, and a usable model and checkpoint. Region review, geometry detectors, and layout training interfaces now exist. [Suite status and where to spend agent time](../plans/2026-09-12-suite-status-and-agent-allocation.md)

These items were checked against repository source and focused sibling evidence
on 2026-11-07. Each plan records its scope and the outcomes still unverified.
The local `make ci` passed: 464 tests passed and one skipped because Modal is
not installed. This does not establish real GPU behavior or every consumer's gate.

Deferred, blocked, and rejected bets stay in the [intent map](intent-map.md).

Remote Modal and shared-container batch dispatch stay deferred there.

## Shipped behavior

- [Batched OCR dispatch](../architecture/batched-ocr-dispatch.md)
- [Page lifecycle and storage](../architecture/page-lifecycle-and-storage.md)
- [Shared suite services](../architecture/suite-services.md)
- [Shared paths and DocTR export manifests](../architecture/shared-paths-and-export-manifest.md)
- Strict type checking with no baseline file: [lint deviations](../process/lint-deviations.md)

Governed reports under [the issue index](../issues/README.md) are the work tracker. GitHub Issues is not.
