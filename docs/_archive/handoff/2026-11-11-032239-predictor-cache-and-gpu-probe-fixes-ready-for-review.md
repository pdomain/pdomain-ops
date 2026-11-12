---
kind: archive
status: retired
created_at: "2026-11-11T03:22:38Z"
owner: "CT"
branch: "worktree-fix-predictor-cache-gpu-probe"
scope: "predictor-cache-gpu-probe"
worktree: "/mnt/work/projects/pdomain/pdomain-ops/.claude/worktrees/fix-predictor-cache-gpu-probe"
base_commit: "b81c0ff9bb3c327447038b02ff1191bb22a0556b"
handoff_reason: "user_requested"
host: "claude-code"
created: "2026-11-11"
last_verified: "2026-11-11"
---

# Predictor cache and GPU probe fixes ready for review

> **Retired — superseded by `docs/handoff/2026-11-11-043359-runbook-corrected-gpu-probe-acceptance-still-open.md`.**

## Goal

Fix the predictor cache race and the device probe crash on a full GPU, and correct the stale contracts claim in current-state.

## Done

- Racing threads now build one predictor per key at both call sites (`04fa5db`). The lock covers the build but not the OCR run, so cold builds for different keys take turns.
- A failed memory query now lists the card as unavailable with a reason, and a card with 0 MiB free is unavailable (`9594e32`).
- The predictor issue is retired (`728e5f2`, `b81c0ff`), and current-state says the matching APIs ship in contracts v0.3.0.
- `make ci AI=1` passed with 499 passed and 1 skipped because Modal is not installed.

## Not done

- The device probe issue stays open. Its last acceptance check is three `pdomain-ocr-simple-gui` tests on a full GPU.
- Both fixes were tested with stand-ins on CPU, never against a real GPU.
- `docs/runbooks/pgdp-api-review.md` line 28 still makes the stale local-wheel claim.
- A low-severity review note is unfixed: the hardware scan can repeat when both the name and memory queries fail for a card.

## Failed approaches

- None.

## Decisions

- Open for the owner: whether a card with little free memory also counts as unavailable. Only the 0 MiB case was applied, which the issue calls clear.
- Consumers do not all pin v0.3.0. The labeler and source-data require `>=0.3.0`. Training requires `>=0.2.1` and ops `>=0.2.0`, but neither imports the new APIs.

## State

Worktree clean. The owner paused this work on 2026-11-10 and the session's herdr tab is closed. Nothing was pushed, merged, tagged, released or deployed. All work ran on CPU with the GPU hidden. The session's last terminal output is saved in `/mnt/work/projects/pdomain/.artifacts/handoff-20261110/session-output/`. `/tmp` is a shared tmpfs that ran out of quota several times on 2026-11-10 while ten sessions ran gates. If a gate fails with a quota error, point `TMPDIR` at the work drive and rerun before suspecting the code.

## Pointers

- `docs/issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md`
- `docs/architecture/batched-ocr-dispatch.md`
- `docs/context/current-state.md`

## Resume steps

1. Fix the stale line in the runbook.
2. Review and merge when the owner asks.
3. Run the three simple-gui tests on a full GPU to close the probe issue.
