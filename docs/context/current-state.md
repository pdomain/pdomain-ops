---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-11-13
Kind: context
---

# Current state

CUDA probe acceptance and weekly dep-refresh auto-land are still open in this repository.

Book-contracts extraction still needs evidence.

Accepted production-corpus quality and a usable layout model are still open.

## Agent Index

- **Kind:** context
- **Status:** active
- **Last verified:** 2026-11-13
- **Read when:** starting work that depends on current repository documentation.
- **Search terms:** current state, remaining work, open issues, layout review, roadmap.

## Remaining work

These reports are still open in this repository.

- The CUDA probe reports a failed memory query, or 0 MiB free, as unavailable (`9594e32`). The hardware scan runs once per listing (`851d1dc`, checked by `e879976`). Full-GPU acceptance tests are unrun. [The device probe raises instead of reporting when the GPU is full](../issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md)
- Weekly dep-refresh auto-land is still open. A 2026-11-07 GitHub check found master unprotected and thirteen `dep-refresh/*` branches. It also found nine open PRs. Do not recreate the deleted workflows. Closing or replacing the issue needs an owner decision. [Weekly dep-refresh cannot auto-land in this repo](../issues/2026-08-08-dep-refresh-cannot-auto-land.md)

Book-contracts extraction still needs evidence for data rescue, digest compatibility of stored artifacts, and repository retirement.

The package move and checked consumer repoints exist. [Extract Book Contracts and Retire the pd- Repos](../plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md)

Accepted production-corpus quality and a usable layout model are still open. They are owned by source-data and training.

The [roadmap](intent-map.md) names the repository for each remaining bet.

Every proved page's composed alignment is still ambiguous, changed, or exhausted. [Layout review](../architecture/layout-review.md)

The historical 2026-11-07 `make ci` run passed 464 tests and skipped one because Modal was not installed.

The current gate is `just ci`. The 2026-11-13 migration-worktree baseline at
`810eeb7` passed 504 tests, skipped one because Modal is absent, built the
package, and passed strict docgraph. It does not establish real GPU behavior
or every consumer's gate.

Deferred, blocked, and rejected bets stay in the [roadmap](intent-map.md).

Remote Modal and shared-container batch dispatch stay deferred there.

## Shipped behavior

- [Layout review](../architecture/layout-review.md), including F2 and Gutenberg hints, contracts `v0.3.0` alignment, source tabs, and the nine-page proof
- [Batched OCR dispatch](../architecture/batched-ocr-dispatch.md)
- [Page lifecycle and storage](../architecture/page-lifecycle-and-storage.md)
- [Shared suite services](../architecture/suite-services.md)
- [Shared paths and DocTR export manifests](../architecture/shared-paths-and-export-manifest.md)
- [Book contracts package boundary](../architecture/book-contracts-boundary.md), including dependency direction, structural protocols and the image-provider seam
- Strict type checking with no baseline file: [lint deviations](../process/lint-deviations.md)

On 2026-11-12 the layout-review commits cited in that architecture doc were ancestors of the sibling masters.

On 2026-11-13, the inspected labeler, source-data and training checkouts all
declared `pdomain-book-contracts>=0.3.1`. This repository declares the same
minimum and `pdomain-book-tools>=0.31.0` in `pyproject.toml` (`64f9bec`). These
are source declarations, not verification of deployed consumer versions.

The module-layout spec and superseded predictor/GPU handoffs are retired in
the [decision log](decisions.md). The extraction plan remains partial, and
both open issues retain their acceptance or owner-decision requirements.

Governed reports under [the issue index](../issues/README.md) are the work tracker. GitHub Issues is not.
