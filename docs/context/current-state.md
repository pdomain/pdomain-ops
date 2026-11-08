---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-11-08
Kind: context
---

# Current state

## Agent Index

- **Kind:** context
- **Status:** active
- **Last verified:** 2026-11-08
- **Read when:** starting work that depends on current repository documentation.
- **Search terms:** current state, remaining work, open issues, active plans.

## Remaining work

- Source tabs and page refresh fixes are installed locally in dev14. Consolidated GT previews P3 wording with supported F2 formatting, including mapped verse indents. P3 and F2 also have separate tabs. Working GT displays current corrections; word edits remain in Matches. Nine source pages and installed browser navigation/reload checks passed; unresolved formatting remains explicit. [Follow-up plan](../plans/2026-11-08-source-tabs-and-page-refresh.md)
- Unified P3/F2 matching and API-driven review are built locally. A nine-page real-data workflow completed 152 public operations and preserved all 1,530 OCR words through review and reload. The installed build passed eight Chromium tests and the final nine-page proof, including true columns and single-column negative cases. Matching and formatting remain partial on several pages. [Implementation plan](../plans/2026-11-08-p3-f2-review-api.md). [API runbook](../runbooks/pgdp-api-review.md)
- The predictor cache is still an unguarded check-then-set. [Concurrent OCR jobs can each build a duplicate DocTR predictor](../issues/2026-08-08-predictor-cache-not-thread-safe.md)
- The CUDA probe still lets memory-query failures escape and marks queried CUDA devices available regardless of free memory. [The device probe raises instead of reporting when the GPU is full](../issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md)
- Weekly dep-refresh auto-land is still open. Commit `7ff9c7d` removed the GitHub workflows. Branch protection on master is off. Thirteen `dep-refresh/*` branches remain on origin. Closing the issue needs an owner decision. [Weekly dep-refresh cannot auto-land in this repo](../issues/2026-08-08-dep-refresh-cannot-auto-land.md)
- Book-contracts extraction still needs evidence for data rescue, digest compatibility of stored artifacts, and repository retirement. The package move and checked consumer repoints exist. [Extract Book Contracts and Retire the pd- Repos](../plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md)
- The suite work order still needs accepted production-corpus quality and a usable model and checkpoint. The F2/Gutenberg proposal, review, persistence, export, and training-reader path now has synthetic fixture and interactive browser proof. This does not establish real-corpus or model quality. [Suite status and where to spend agent time](../plans/2026-09-12-suite-status-and-agent-allocation.md). [F2 and Gutenberg proof](../plans/2026-11-07-f2-and-gutenberg-layout-regions.md#implementation-proof)

The other remaining-work items were checked against repository source and
focused sibling evidence on 2026-11-07. Each plan records its scope and the
outcomes still unverified.
The local `make ci` passed: 464 tests passed and one skipped because Modal is
not installed. This does not establish real GPU behavior or every consumer's gate.

The F2/Gutenberg path was checked separately on 2026-11-08. All 92 focused
cross-repository tests passed, along with eight interactive browser checks.
The installed-wheel export check retained verse structure, two separate
paragraph columns, reviewed 2×2 table cells, stable word IDs, and refreshed
geometry snapshots. Detailed word-bound formatting requires prepared bundles
with stored word IDs. These checks use synthetic fixtures.

The four product changes are merged and pushed. Contracts `v0.2.1` is published,
and the source-data, labeler, and training consumers require `>=0.2.1` and install
that release through their normal lockfiles. Normal consumer checks passed,
including all four labeler Docker tests and eight Chromium checks against the
published dependency. [Verified rollout](../plans/2026-11-07-f2-and-gutenberg-layout-regions.md#rollout-outcome)

The newer P3/F2/API work is separate local development. Contracts owns bounded
matching and grouped projection. Source-data owns catalog and selected-book
preparation. The labeler owns jobs, review, JSON controls, and viewer updates.
Ops owns the repeatable real-data harness. The installed local source wheel
prepares all nine pages. Real structured exports preserve verse word IDs and
two separate paragraph columns. API-driven browser checks cover two tabs,
reconnect, stale acknowledgements, and visible review changes without reload.
These checks establish bounded workflow coverage. They do not establish
full-corpus annotation quality or a trained model. The new contracts APIs
require the reviewed local wheel; the published `v0.2.1` release does not
contain them.

Deferred, blocked, and rejected bets stay in the [intent map](intent-map.md).

Remote Modal and shared-container batch dispatch stay deferred there.

## Shipped behavior

- [Batched OCR dispatch](../architecture/batched-ocr-dispatch.md)
- [Page lifecycle and storage](../architecture/page-lifecycle-and-storage.md)
- [Shared suite services](../architecture/suite-services.md)
- [Shared paths and DocTR export manifests](../architecture/shared-paths-and-export-manifest.md)
- Strict type checking with no baseline file: [lint deviations](../process/lint-deviations.md)

Governed reports under [the issue index](../issues/README.md) are the work tracker. GitHub Issues is not.
