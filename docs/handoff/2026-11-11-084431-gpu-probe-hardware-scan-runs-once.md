---
kind: handoff
status: "active"
created: "2026-11-11"
created_at: "2026-11-11T08:44:31Z"
owner: "CT"
branch: "fix-gpu-probe-single-scan"
scope: "predictor-cache-gpu-probe"
worktree: "/mnt/work/projects/pdomain/pdomain-ops/.claude/worktrees/fix-gpu-probe-single-scan"
base_commit: "e879976d4e1d829926ace75546635b53bdad3e8e"
supersedes: "2026-11-11-043359-runbook-corrected-gpu-probe-acceptance-still-open.md"
handoff_reason: "stopping"
host: "claude-code"
---

# GPU probe hardware scan now runs once per listing

## Goal

Fix the low-severity review note on the predictor cache and GPU probe work: the hardware scan repeated when a card failed both its name and memory queries.

## Done

- New branch `fix-gpu-probe-single-scan`, made from the unmerged `worktree-fix-predictor-cache-gpu-probe` at `f5e9b11`, in its own worktree.
- `851d1dc` adds a lazy `_HardwareScan` in `pdomain_ops/gpu/device_probe.py`. One `list_devices` call now runs the `nvidia-smi`, `/proc` and `lspci` scan at most once. Before, each card that failed both queries ran its own scan and `list_devices` ran one more. `_probe_cuda` takes an optional `hardware` argument; three older tests that patch it were updated.
- Test-first with stand-ins on CPU: two new tests failed before the fix with 2 and 3 scans, and pass after.
- The same commit adds one bullet to the fix status in `docs/issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md`.
- One Python review ran. Its only finding was a test that passed whether or not the label path scanned. `e879976` replaces it with a test that `_probe_cuda` makes no scan when names are known.
- `make ci AI=1` exited 0 after each commit, read from the command's own status: 502 passed, 1 skipped because Modal is not installed. `docgraph check` exited 0 with two advisories.

## Not done

- Carried over: the device probe issue stays open until the three `pdomain-ocr-simple-gui` tests pass on a full GPU. No real GPU was used.
- Carried over: the runbook's stale `PROOF_TREE` path and the plan's `/tmp` mentions, listed in the superseded handoff.

## Failed approaches

- `docgraph check .` rejects the path argument; run `docgraph check` from the worktree root.

## Decisions

- Open for the owner, carried over: whether a card with little free memory also counts as unavailable, and whether to fix the stale runbook and plan paths.
- This branch sits on top of `worktree-fix-predictor-cache-gpu-probe`. Merging this branch brings that branch's commits too.

## State

Worktree clean after this handoff lands. Nothing was pushed, merged, tagged, released or deployed. The GPU stayed hidden and no GPU job ran. Gates ran with `TMPDIR` on the work drive.

## Pointers

- `pdomain_ops/gpu/device_probe.py`
- `tests/gpu/test_device_probe.py`
- `docs/issues/2026-09-13-gpu-probe-fails-when-the-card-is-full.md`
- `docs/_archive/handoff/2026-11-11-043359-runbook-corrected-gpu-probe-acceptance-still-open.md`

## Resume steps

1. Review `851d1dc` and `e879976`, then merge this branch instead of the older one when the owner asks.
2. Run the three simple-gui tests on a full GPU to close the probe issue.
3. If the owner agrees, fix the stale proof path in the runbook and the `/tmp` mentions in the plan.
