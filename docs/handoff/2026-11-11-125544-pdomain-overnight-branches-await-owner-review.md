---
kind: handoff
status: "active"
created: "2026-11-11"
created_at: "2026-11-11T12:56:10Z"
owner: "CT"
branch: "master"
scope: "pdomain-overnight-review"
worktree: "/mnt/work/projects/pdomain/pdomain-ops"
base_commit: "0fde158e42a9049dbf017fb6dfa70936067d1588"
supersedes: ""
handoff_reason: "user_requested"
host: "claude-code"
---

# pdomain overnight branches await owner review

## Goal

Review, decide on and merge the work that agent sessions did across ten pdomain repositories on 2026-11-10 and
overnight into 2026-11-11. This handoff is the index. Each branch carries its own handoff with details and open
decisions.

## Done

All work is on unmerged local branches. Nothing was pushed, merged, tagged, released or deployed. Several branches
were built on earlier ones, so in each chain below the last branch contains the ones before it. Each session
reported `make ci AI=1` exit 0 on its final commits. The coordinator did not rerun the gates.

- `pdomain-prep-for-pgdp`: `fix/job-reliability` then `feat/wave2-interface` then `feat/night-wave3` then
  `feat/night-prep4` then `fix/zip-entry-timestamps`. Cancel survives progress writes, stage cancel route (owner
  chose real cancel), stuck-job reclaim, cookie and CORS hardening, Wave 2 interface items W2.1 to W2.5,
  browser fixes, W3.2, W3.3, W3.5, part of W3.9, the dependency audit gate, save-a-copy, text zones in Konva
  (checked in Chromium), the Postgres adapter (checked on a live Postgres 17), and deterministic zip timestamps.
- `pdomain-ocr-labeler-spa`: `feature/memfd-tsconfig-state` then `feature/glyph-pgdp-completion` then
  `feature/typography-suggestion-undo`. memfd capability check with a 503, strict test TypeScript, glyph
  annotation completion and shared shell alignment (Chromium checks passed). The last branch only records two
  open design questions in `OPEN_QUESTIONS.md`.
- `pdomain-ocr-simple-gui`: `fix/doc-recheck-bugs` then `fix/word-overlay-flake` then `fix/e2e-flakes`.
  Five recheck bugs and three flaky end-to-end tests. `feat/download-model` only records that the download
  redesign is deferred in the intent map.
- `pdomain-ops`: `worktree-fix-predictor-cache-gpu-probe` then `fix-gpu-probe-single-scan`. Predictor cache
  lock, device probe reports a full or failing card, runbook corrected, hardware scan runs once.
- `pdomain-ui`: `worktree-fix-compute-panel-and-dep-updater` then `night-audit-residuals`. Friendly device
  labels, panel gating on the device list, the dependency updater, the CropCard guard, CoverPlaceholder tokens
  and suppression rationale.
- `pdomain-book-tools`: `fix/roadmap-no-owner-items` then `feat/layout-no-owner-items`. C1, C4, D1, D2, B4,
  C5 and the B3 record. The second branch changed no code.
- `pdomain-book-contracts` `feat/coverage-floor`: tests to 96.90%, a floor of 95, three bugs, and the
  BoundingBox and NaN fixes that book-tools theme C3 needed.
- `pdomain-source-data` `fix/release-manifest-and-context-docs`: release manifest pin, permissions issue
  retired as already fixed, runbook and current state corrected.
- `pdomain-ocr-cli` `fix/spec-review-followups`: eight and a half spec review follow-ups.
- `pdomain-index-pip` `worktree-fix-gh-executable-resolution`: `gh` resolved before index regeneration.

## Not done

- No branch is merged. Merging is the owner's call.
- GPU tests were skipped everywhere. The three `pdomain-ocr-simple-gui` tests on a full GPU, which close the
  device probe issue in `pdomain-ops`, are still unrun.
- `pdomain-book-tools`: the floated-caption bug on normalized pages, drop-cap Iteration C, sidenote-aware row
  blocks and sidenote x-height projection stay open, because no fixture proves them.
- `pdomain-ops` plan docs from 2026-11-08 still cite `/tmp/pdomain-p3-f2-20261108`. That folder moved to
  `/mnt/work/projects/pdomain/.artifacts/tmp-archive-20261110/`. Only the runbook was corrected.
- Repos not touched, because their work is blocked or their folders were never trusted for Claude Code:
  `pdomain-ocr-trainer-spa`, `pdomain-ocr-training`, `pdomain-ocr-synth`, `pdomain-pgdp-measure`,
  `pdomain-index-npm`, `pdomain-pgdp-api-client`, `pdomain-fonts`.

## Failed approaches

- Ten sessions at once overloaded the machine and the `/tmp` quota, which caused false test failures. Three to
  five sessions with `TMPDIR` on the work drive worked.
- A long `TMPDIR` broke a Unix socket test (path over 107 bytes). Short paths under `/mnt/work/pdt/` worked.
- New Claude Code sessions stop at the folder trust dialog for untrusted repos. Only the owner can accept it.
- The background usage watcher was stopped by Claude Code's memory reaper. Usage was then checked every 30
  minutes. It ended at 80% weekly and never reached the 90% pause line.

## Decisions

Every branch handoff lists its own owner decisions. The largest sets are in `pdomain-prep-for-pgdp`
(`fix/job-reliability` three, `feat/wave2-interface` six, `feat/night-wave3` the W3.9 detector and audit
wiring, and the archive inventory half of W3.10). Others:

- Whether to delete old `.viewer.png` and `.viewer.webp` files from users' folders in
  `pdomain-ocr-simple-gui`.
- Whether a card with little free memory counts as unavailable in `pdomain-ops`.
- Typography suggestion accept, edit and undo design in the labeler, recorded as OQ-TYPO-1 and OQ-TYPO-2.
- The provenance home and default overrides in `pdomain-book-tools`, plus accepting its B3 xfail reasons.
- Whether to close the 29 open weekly dep-refresh PRs, as the workflows that made them are gone.

## State

`pdomain-ops` master is unchanged apart from this handoff. The worktrees listed below were clean when this was
written. No agent sessions or tabs from this work are still open.

## Pointers

Latest handoff on each branch:

- pdomain-book-contracts `feat/coverage-floor`: `/mnt/work/projects/pdomain/pdomain-book-contracts/.worktrees/coverage-floor/docs/handoff/2026-11-11-043740-coverage-floor-and-geometry-fixes-committed.md`
- pdomain-book-tools `feat/layout-no-owner-items`: `/mnt/work/projects/pdomain/pdomain-book-tools/.claude/worktrees/layout-no-owner-items/docs/handoff/2026-11-11-061618-layout-items-skipped-on-fixture-evidence.md`
- pdomain-book-tools `fix/roadmap-no-owner-items`: `/mnt/work/projects/pdomain/pdomain-book-tools/.claude/worktrees/roadmap-no-owner-items/docs/handoff/2026-11-11-051125-roadmap-items-caption-bug-left-open.md`
- pdomain-index-pip `worktree-fix-gh-executable-resolution`: `/mnt/work/projects/pdomain/pdomain-index-pip/.claude/worktrees/fix-gh-executable-resolution/docs/handoff/2026-11-11-032241-gh-resolution-fix-ready-for-review.md`
- pdomain-ocr-cli `fix/spec-review-followups`: `/mnt/work/projects/pdomain/.worktrees/ocr-cli-spec-review-followups/docs/handoff/2026-11-11-032239-spec-review-follow-ups-ready-for-review.md`
- pdomain-ocr-labeler-spa `feature/glyph-pgdp-completion`: `/mnt/work/projects/pdomain/pdomain-ocr-labeler-spa/.worktrees/glyph-pgdp-completion/docs/handoff/2026-11-11-075408-glyph-parity-and-shared-ui-alignment-done.md`
- pdomain-ocr-labeler-spa `feature/memfd-tsconfig-state`: `/mnt/work/projects/pdomain/pdomain-ocr-labeler-spa/.worktrees/memfd-tsconfig-state/docs/handoff/2026-11-11-060138-memfd-and-test-types-committed-gate-green.md`
- pdomain-ocr-labeler-spa `feature/typography-suggestion-undo`: `/mnt/work/projects/pdomain/pdomain-ocr-labeler-spa/.worktrees/typography-suggestion-undo/docs/handoff/2026-11-11-082317-typography-suggestion-and-undo-need-owner-design.md`
- pdomain-ocr-simple-gui `feat/download-model`: `/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/.worktrees/download-model/docs/handoff/2026-11-11-051343-download-model-deferred-not-built.md`
- pdomain-ocr-simple-gui `fix/e2e-flakes`: `/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/.worktrees/e2e-flakes/docs/handoff/2026-11-11-092702-two-e2e-flakes-fixed.md`
- pdomain-ocr-simple-gui `fix/doc-recheck-bugs`: `/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/.worktrees/fix-doc-recheck-bugs/docs/handoff/2026-11-11-032238-doc-recheck-bug-fixes-ready-for-review.md`
- pdomain-ocr-simple-gui `fix/word-overlay-flake`: `/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/.worktrees/word-overlay-flake/docs/handoff/2026-11-11-085305-word-overlay-flake-fixed.md`
- pdomain-ops `fix-gpu-probe-single-scan`: `/mnt/work/projects/pdomain/pdomain-ops/.claude/worktrees/fix-gpu-probe-single-scan/docs/handoff/2026-11-11-084431-gpu-probe-hardware-scan-runs-once.md`
- pdomain-ops `worktree-fix-predictor-cache-gpu-probe`: `/mnt/work/projects/pdomain/pdomain-ops/.claude/worktrees/fix-predictor-cache-gpu-probe/docs/handoff/2026-11-11-043359-runbook-corrected-gpu-probe-acceptance-still-open.md`
- pdomain-prep-for-pgdp `feat/wave2-interface`: `/mnt/work/projects/pdomain/pdomain-prep-for-pgdp/.worktrees/feat-wave2-interface/docs/handoff/2026-11-11-063139-wave-2-interface-items-committed-and-awaiting-review.md`
- pdomain-prep-for-pgdp `fix/job-reliability`: `/mnt/work/projects/pdomain/pdomain-prep-for-pgdp/.worktrees/fix-job-reliability/docs/handoff/2026-11-11-052844-job-reliability-fixes-committed-and-awaiting-merge.md`
- pdomain-prep-for-pgdp `feat/night-prep4`: `/mnt/work/projects/pdomain/pdomain-prep-for-pgdp/.worktrees/night-prep4/docs/handoff/2026-11-11-080600-text-zones-konva-and-postgres-adapter-committed.md`
- pdomain-prep-for-pgdp `feat/night-wave3`: `/mnt/work/projects/pdomain/pdomain-prep-for-pgdp/.worktrees/night-wave3/docs/handoff/2026-11-11-072044-night-wave3-browser-fixes-and-issue-work.md`
- pdomain-prep-for-pgdp `fix/zip-entry-timestamps`: `/mnt/work/projects/pdomain/pdomain-prep-for-pgdp/.worktrees/zip-entry-timestamps/docs/handoff/2026-11-11-084911-submission-zip-entries-stamped-with-built_at.md`
- pdomain-source-data `fix/release-manifest-and-context-docs`: `/mnt/work/projects/pdomain/pdomain-source-data/.worktrees/release-manifest-and-context/docs/handoff/2026-11-11-043307-runbook-fixed-ci-blocked-by-temp-path-length.md`
- pdomain-ui `night-audit-residuals`: `/mnt/work/projects/pdomain/pdomain-ui/.claude/worktrees/audit-residuals/docs/handoff/2026-11-11-081941-audit-residuals-fixed-on-top-of-compute-panel-branch.md`
- pdomain-ui `worktree-fix-compute-panel-and-dep-updater`: `/mnt/work/projects/pdomain/pdomain-ui/.claude/worktrees/fix-compute-panel-and-dep-updater/docs/handoff/2026-11-11-043304-compute-panel-and-updater-ready-for-merge-review.md`

Other records:

- Session outcomes, one line each: `/mnt/work/projects/pdomain/.artifacts/night-20261110/*.done`
- Usage readings: `/mnt/work/projects/pdomain/.artifacts/night-20261110/usage.log`
- Pre-overnight patches and session output: `/mnt/work/projects/pdomain/.artifacts/handoff-20261110/`
- Former `/tmp` files, including the 2026-11-08 proof reports: `/mnt/work/projects/pdomain/.artifacts/tmp-archive-20261110/`
- Suite roadmap: `docs/context/intent-map.md`

## Resume steps

1. Read the decision lists in the branch handoffs above and answer them.
2. For each repo, review the last branch in its chain with `git log master..<branch>`, then merge when satisfied.
3. Run the GPU-marked tests on a free card before merging `pdomain-book-tools` and `pdomain-ops`.
4. Decide release order. `pdomain-book-contracts` changes geometry behaviour that other packages consume, so
   release it before consumers that need the fix.
5. Delete `/mnt/work/projects/pdomain/.artifacts/tmp-archive-20261110/` and `/mnt/work/projects/pdomain/.artifacts/night-20261110/` once the evidence is
   no longer needed.
