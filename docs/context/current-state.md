---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-11-06
Kind: context
---

# Current state

## Agent Index

- **Kind:** context
- **Status:** active
- **Last verified:** 2026-11-06
- **Read when:** starting work that depends on current repository documentation.
- **Search terms:** current state, remaining work, open issues, active plans.

## Remaining work

- The predictor cache is still an unguarded check-then-set. [Concurrent OCR jobs can each build a duplicate DocTR predictor](../issues/2026-08-08-predictor-cache-not-thread-safe.md)
- The CUDA probe still raises when the card is out of memory. It still marks every device it finds as available. [The device probe raises instead of reporting when the GPU is full](../issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md)
- Weekly dep-refresh auto-land is still open. Commit `7ff9c7d` removed the GitHub workflows. Branch protection on master is off. Thirteen `dep-refresh/*` branches remain on origin. Closing the issue needs an owner decision. [Weekly dep-refresh cannot auto-land in this repo](../issues/2026-08-08-dep-refresh-cannot-auto-land.md)
- Book-contracts extraction is still open. The 2026-09-02 handoff says Tasks 1, 3, and 4 are done. Those plan checkboxes are still empty. Task 2's three steps are unchecked. In Task 5, Step 2 is checked and Steps 0, 1, 3, and 4 are open. Step 1's prose says the api-client repoint was done on 2026-09-02. The handoff says the package is unpublished. `pdomain-book-contracts` v0.2.0 exists. [Extract Book Contracts and Retire the pd- Repos](../plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md). [Handoff](../handoff/2026-09-02-045132-book-contracts-extraction.md)
- The suite allocation plan stays in place as an active cross-repo work order. In this repo, `v0.12.0` is current master, so the plan's count of 68 unreleased commits is out of date. [Suite status and where to spend agent time](../plans/2026-09-12-suite-status-and-agent-allocation.md)

These items were checked against this repository on 2026-11-06.

Deferred, blocked, and rejected bets stay in the [intent map](intent-map.md).

Remote Modal and shared-container batch dispatch stay deferred there.

## Shipped behavior

- [Batched OCR dispatch](../architecture/batched-ocr-dispatch.md)
- [Page lifecycle and storage](../architecture/page-lifecycle-and-storage.md)
- [Shared suite services](../architecture/suite-services.md)
- [Shared paths and DocTR export manifests](../architecture/shared-paths-and-export-manifest.md)
- Strict type checking with no baseline file: [lint deviations](../process/lint-deviations.md)

Governed reports under [the issue index](../issues/README.md) are the work tracker. GitHub Issues is not.
