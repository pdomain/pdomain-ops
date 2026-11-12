---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-11-12
Kind: context
---

# Intent map

This is the suite roadmap.

Shipped behavior is in `docs/architecture/`.

Open bugs in this repository are in the [issue index](../issues/README.md).

One extraction plan is still open.

The September 2026 suite schedule is retired.

## Agent Index

- **Kind:** context
- **Status:** active
- **Last verified:** 2026-11-12
- **Read when:** choosing the next suite task, or deciding which repository should own it.
- **Search terms:** roadmap, intent, separate repository, deferred work, owner decision.

Checked on 2026-11-12 from this repository's docs and from sibling `master` commits. External infrastructure and historical cross-repository decisions keep their recorded evidence dates. This date does not revalidate them.

## Build next in this repository

- **Finish GPU-probe acceptance.** A failed CUDA memory query, or a device with 0 MiB free, is reported unavailable (`9594e32`). The hardware scan runs once per device listing (`851d1dc`, checked by `e879976`). The issue stays open until three `pdomain-ocr-simple-gui` tests pass on a full GPU. Those tests were not run. Whether a card with some free memory, but not much, counts as unavailable is still an owner question. [Issue](../issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md).
- **Decide whether to close dep-refresh.** Commit `7ff9c7d` on 2026-09-13 deleted the GitHub workflows. A 2026-11-07 GitHub API check found master unprotected and thirteen `dep-refresh/*` branches. It also found nine open PRs (85 through 93). It found `delete_branch_on_merge=false`. Do not recreate the deleted workflows. The owner chooses close-as-abandoned or a new design. [Issue](../issues/2026-08-08-dep-refresh-cannot-auto-land.md).
- **Keep the PGDP proof harness with the labeler control client.** The harness is `scripts/real_pgdp_review_proof.py`. It is maintenance of the [layout review](../architecture/layout-review.md) path, not a new product.

## Finish in the repository that already owns it

- **Labeler: production proposal wiring and the partial pages.** On 2026-11-07, region review client code existed in `frontend/src/components/right-panel/RegionDetail.tsx` and `frontend/src/hooks/useRegionMutations.ts`. Geometry proposal code existed under `core/regions/`. The handler still fell back to `null_region_detector` when no detector was supplied. That check did not prove every deployed app wires a detector. Every proved page's composed alignment is still ambiguous, changed, or exhausted. See [layout review](../architecture/layout-review.md). Owner: `pdomain-ocr-labeler-spa`.
- **Source-data: accepted corpus quality, and the extraction residue.** Prove historical data rescue, digest compatibility of stored artifacts, and retirement of the `pd-` repositories. The package move and checked consumer repoints exist. [Extraction plan](../plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md). Owner: `pdomain-source-data` for stored artifacts, with this repository coordinating the retirement evidence.
- **Training: a usable layout model and checkpoint.** On 2026-11-07 the runner read region exports, delegated training to a supplied model, and rejected a missing model. That does not prove a production model, a real checkpoint, or a large enough accepted corpus. Training master still requires `pdomain-book-contracts>=0.2.1`. The labeler and source-data require `>=0.3.0`. Owner: `pdomain-ocr-training`.
- **Book-tools: layout fixes that already have no model dependency.** The 2026-11-11 overnight handoff left these open: the floated-caption bug on normalized pages, drop-cap Iteration C, sidenote-aware row blocks, and sidenote x-height projection. The September plan also recorded an x-height-spread figure of 43 to 67 percent with no evidence file. It said to recompute that figure before anything depends on it. Owner: `pdomain-book-tools`. [Handoff](../handoff/2026-11-11-125544-pdomain-overnight-branches-await-owner-review.md).
- **Prep-for-PGDP: its own app.** Overnight branches from 2026-11-10 await owner review. The 2026-09-12 survey said the app could not finish a book. Do not treat that survey as the current state. Owner: `pdomain-prep-for-pgdp`.
- **Contracts: move the module-layout spec.** The package and its tree live in `pdomain-book-contracts`. The layout writeup still sits here as [Book Contracts Module Layout](../specs/2026-09-02-book-contracts-module-layout.md). Move that current description into the contracts repository. Do not grow contracts code inside `pdomain-ops`.

## Consider a separate repository

These do not have a home that should absorb them into `pdomain-ops`.

- **Hosted and remote execution.** Modal, shared-container batch dispatch, `RemotePageStore`, and managed persistence stay deferred until a consumer commits. This repository owns the local protocol seams. A deployment repository should own the hosted runtime. Windows and macOS packaging are the same kind of split. Linux shortcuts ship. The other shortcut functions raise `NotImplementedError`.
- **OCR, HTR, and dewarp comparison.** Compare PP-OCRv5 ONNX, HTR engines, historical datasets, and selected dewarp options with the shipped DocTR, Tesseract, textline-disparity, and UVDoc baseline. Require dataset-license review and reproducible metrics before adoption. Owner of adoption: `pdomain-book-tools` and the OCR training repositories. The comparison harness should be its own project.
- **Where layout-model training runs.** The September plan left two choices open. Either `pdomain-ocr-training` widens its runner, or layout training lands in another project. It also left open whether real fine-tuning uses rented cloud GPUs. Do not add that trainer to `pdomain-ops`. The September plan's note of an 8 GB local GPU is historical hardware wording, not a 2026-11-12 machine measurement.
- **The synthesizer's labeled-dataset contract.** The September plan called this M16 and left it unspecified. It joins synthesis and training. Owner: `pdomain-ocr-synth` and `pdomain-ocr-training`.
- **Cross-repo release, SHA, and static-security policy.** Active repositories implement many gates. Their release workflows differ. The old claim of one universal release CI is false. First inventory every active and legacy repository. An owner then decides what must match. A workspace release tool should hold that policy. Owner: workspace release maintainers.
- **Shared review widgets.** If more than one SPA needs the same review controls, extend `pdomain-ui`. Do not copy them into this repository. Do not start a second UI kit.

## Not this repository

These stayed on the old roadmap after the salvaged-docs review. They are not pdomain-ops work.

- **Isolated ebook sessions.** Keep standalone ebook work isolated from parent repository instructions and from shared working-directory state. Owner: the se-llm-skills or ebook-tool maintainer. Source mapped: `_tbd/ocr-container-docs/process/se-ebook-isolated-sessions.md`.
- **Page-model adoption in each consumer.** Check that repository's code before recording a gap in `PageRecord`, `PagePayload`, provenance, extensions, or persistence. Current ops evidence is [page lifecycle and storage](../architecture/page-lifecycle-and-storage.md). Source mapped: `_tbd/ocr-container-docs/archive/specs/2026-06-01-page-split-downstream-rollout.md`.
- **Behavior-capture templates.** Derive a cross-interface method and scanner-safe templates from current tests. Start with one Web implementation. Owner: the repository that runs the pilot.
- **Docgraph-native documentation and UI inventories.** Prove one inventory and one UI contract before proposing a workspace standard. Owner: the first repository that asks for a pilot.
- **Notifications, configuration sync, and cost visibility.** Owner: workspace tooling. Do not revive the old ctask data model.
- **A current project announcement.** Replace the unfinished pd-* post with verified names, install paths, measured quality, and current hosted-inference intent. Owner: CT or the communications owner.
- **Product residue to recheck in the product repos.** The residue is open-in-labeler links, `PageRecord` replacement of manifest bridges, simple-GUI managed deployment, missing shared UI components, and platform or real-engine coverage. Copy only confirmed gaps into that repository's intent map.
- **Semantic review or scheduled convention audits.** Consider them only if installed plugins leave a measured gap. Owner: workspace tooling.
- **GitHub label deletion.** The retired ship-issue bot's labels remain: `bot:*`, `model:*`, `model-effort:*`, and `recurring:*`. Those were fifteen or more of pdomain-prep-for-pgdp's 53 labels on 2026-08-08. The eight `wip/ship-issue*` and `worktree-agent-*` branches were deleted that day. Deleting labels is an outward-facing remote change. It needs explicit approval.
- **Phone-access infrastructure.** This repository cannot confirm Tailscale, SSH, Termux, tmux, ACL, or credential state. Owner: CT. If it is active, write a secret-safe runbook elsewhere. Otherwise retire the old material.
- **Unavailable repositories.** The workspace could not verify remaining work in se-llm-skills or pd-png-optimizer. Owner: each repository owner.
- **Legacy bot workspaces.** Decide whether `/srv/bot-workspaces`, bot slots, and related devcontainer permissions still serve current automation. Some Makefiles retain the filesystem support. The claude-bot, ctask, and ship-issue protocol is stale. Owner: CT and devcontainer maintainers.
- **Codex persistence.** Decide whether Codex state still needs an owner-maintained backup and restore procedure. `/home/vscode/.codex` remained relevant when this was recorded. The old volume, workspace, and scripts were obsolete. Owner: CT and devcontainer maintainers.

The [lint-deviation catalog](../process/lint-deviations.md) stays a maintenance obligation under `CONVENTIONS.md`. It is not a roadmap bet.

## Completed

- **One DocTR predictor per cache key.** `get_or_build_predictor` builds each key once under a lock, and the batch build waits off the event loop. A failed build is not cached. Evidence: `04fa5db` and `tests/gpu/test_predictor_cache_concurrency.py`. Those tests use a stand-in builder on CPU. Behavior is in [batched OCR dispatch](../architecture/batched-ocr-dispatch.md).
- **Layout review, F2 and Gutenberg, source tabs, and the nine-page API proof.** Behavior and measurements are in [layout review](../architecture/layout-review.md). The 2026-11-08 writeups said the newest line was local-only. On 2026-11-12 those commits were on sibling masters. Contracts `v0.3.0` is the alignment commit `1bd8261`. Partial pages remain.
- **Clear the basedpyright strict backlog.** All 33 baseline diagnostics are fixed. The baseline file is deleted. Evidence: commit `f09d2b7`. Owner: CT.
- **Remove `desktop._noop_app`.** The dead ASGI placeholder is gone. Evidence: commit `d73c331`. Owner: CT.
- **Salvaged holding-area migration.** All 210 Markdown sources were red-teamed. Useful content was promoted. All 222 tracked holding-area files were retired. Evidence: the [red-team ledger](../research/2026-07-13-salvaged-docs-red-team.md). Owner: CT.
- **Releases that unblocked the September labeling track.** By 2026-11-07, local tags included book-tools `v0.30.1`, training `v0.3.0`, and pgdp-measure `v0.1.0`. Source-data and the labeler pinned book-tools `0.30.1`. Tags do not establish deployed runtime versions. Ops `v0.12.0` pointed at `02b201a` during that check. The old figure of 68 unreleased ops commits was false then.

## Rejected

- **A parallel archive tree.** Retired docs are reduced into architecture, decisions, and residual intent.
- **A persistent coding bot and ship-issue system.** Do not revive the custom daemon, rolling WIP branch, state and cost databases, or unattended PAT-driven runner.
- **GitHub issue synchronization.** Governed issue reports are the only work tracker. A future read-only export needs a new owner-approved design.
- **The full historical UI schema as a workspace standard.** Do not require the complete state-matrix and interaction-id schema without a successful reduced pilot.

## Needs owner decision

- **Close or keep the dep-refresh issue.** Evidence is the open issue above. The file stays until the owner decides.
- **Legacy bot workspaces, Codex persistence, phone access, and the GitHub label deletion.** Each is listed under [Not this repository](#not-this-repository). Each still needs the owner named there. None of them is a reason to add code to `pdomain-ops`.

## Legacy-unverified sweep

<!-- needs-owner-review resolved as active: docs/process/lint-deviations.md; the catalog is reconciled against current source. -->
