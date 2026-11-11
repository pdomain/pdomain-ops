---
kind: handoff
status: "active"
created: "2026-11-11"
created_at: "2026-11-11T04:33:59Z"
owner: "CT"
branch: "worktree-fix-predictor-cache-gpu-probe"
scope: "predictor-cache-gpu-probe"
worktree: "/mnt/work/projects/pdomain/pdomain-ops/.claude/worktrees/fix-predictor-cache-gpu-probe"
base_commit: "373c924558f1f7234b0a5e2aa6fd362d3136bfdd"
supersedes: "2026-11-11-032239-predictor-cache-and-gpu-probe-fixes-ready-for-review.md"
handoff_reason: "stopping"
host: "claude-code"
---

# Runbook corrected, GPU probe acceptance still open

## Goal

Fix the predictor cache race and the device probe crash on a full GPU, and correct the stale contracts and `/tmp` claims in the docs.

## Done

- `373c924` corrects `docs/runbooks/pgdp-api-review.md`. The Preconditions section now says published contracts v0.3.0 contains the matching APIs, so a new install needs no local wheel.
- The same commit points the runbook at the moved `labeler-artifact-ready.json` and `source-ready.json` in `/mnt/work/projects/pdomain/.artifacts/tmp-archive-20261110/pdomain-p3-f2-20261108/`.
- `make ci AI=1` on the runbook change exited 0, read from the command's own status: 499 passed, 1 skipped because Modal is not installed. `docgraph check` exited 0 with one advisory.
- Earlier on this branch: racing threads build one predictor per key (`04fa5db`), a failed memory query or a card with 0 MiB free is reported as unavailable (`9594e32`), and the predictor issue is retired (`728e5f2`, `b81c0ff`).

## Not done

- The device probe issue stays open. Its last acceptance check is three `pdomain-ocr-simple-gui` tests on a full GPU. They were deliberately not run in the overnight session of 2026-11-10.
- Both fixes were tested with stand-ins on CPU, never against a real GPU.
- A low-severity review note is unfixed: the hardware scan can repeat when both the name and memory queries fail for a card.
- Found but left alone because they were outside the request. In the runbook's Verification section, `PROOF_TREE` names `pdomain-ops/.worktrees/p3-f2-proof`, which no longer exists. The harness is now on master at `scripts/real_pgdp_review_proof.py`, so "lives in a separate local worktree" is also stale.
- `docs/plans/2026-11-08-p3-f2-review-api.md` lines 164 and 258 still name the old `/tmp/pdomain-p3-f2-20261108` folder.
- The runbook's `Last verified` stays 2026-11-08, because only the corrected passages were checked.

## Failed approaches

- `docgraph_handoff_active` returned no handoff until `repo` was passed with the worktree path, so pass `repo` explicitly.

## Decisions

- Open for the owner: whether a card with little free memory also counts as unavailable. Only the 0 MiB case was applied, which the issue calls clear.
- Open for the owner: whether to fix the stale `PROOF_TREE` path and the plan's `/tmp` mentions.
- Consumers do not all pin v0.3.0. The labeler and source-data require `>=0.3.0`. Training requires `>=0.2.1` and ops `>=0.2.0`, but neither imports the new APIs.

## State

Worktree clean after this handoff lands. Nothing was pushed, merged, tagged, released or deployed. The GPU stayed hidden and no GPU job ran. As of 2026-11-10 no labeler release tag contains the feature, and the installed build's server on port 8795 was not listening. Set `TMPDIR` on the work drive before gates, because `/tmp` is a small shared tmpfs.

## Pointers

- `docs/runbooks/pgdp-api-review.md`
- `docs/issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md`
- `docs/architecture/batched-ocr-dispatch.md`
- `docs/context/current-state.md`

## Resume steps

1. Review and merge when the owner asks.
2. Run the three simple-gui tests on a full GPU to close the probe issue.
3. If the owner agrees, fix the stale proof path in the runbook and the `/tmp` mentions in the plan.
