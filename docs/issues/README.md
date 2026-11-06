---
Status: active
Owner: CT
Created: 2026-07-15
Last verified: 2026-11-06
Kind: process
Level: I1
---

# Issues

## Agent Index

- **Kind:** process
- **Status:** active
- **Level:** I1
- **Last verified:** 2026-11-06
- **Read when:** filing a bug / defect / investigation report, or looking up an
  open issue's status, evidence, or resolution.
- **Search terms:** issues folder, bug report, defect report, issue template,
  issue lifecycle, kind issue.

## Remaining work

- The predictor cache is still an unguarded check-then-set. [Concurrent OCR jobs can each build a duplicate DocTR predictor](2026-08-08-predictor-cache-not-thread-safe.md)
- The CUDA probe still raises when the card is out of memory. It still marks every device it finds as available. [The device probe raises instead of reporting when the GPU is full](2026-09-13-gpu-probe-fails-when-the-card-is-full.md)
- Weekly dep-refresh auto-land is still open. Commit `7ff9c7d` removed the GitHub workflows. Branch protection on master is off. Thirteen `dep-refresh/*` branches remain on origin. Closing the issue needs an owner decision. [Weekly dep-refresh cannot auto-land in this repo](2026-08-08-dep-refresh-cannot-auto-land.md)
- Book-contracts extraction is still open. The 2026-09-02 handoff says Tasks 1, 3, and 4 are done. Those plan checkboxes are still empty. Task 2's three steps are unchecked. In Task 5, Step 2 is checked and Steps 0, 1, 3, and 4 are open. Step 1's prose says the api-client repoint was done on 2026-09-02. The handoff says the package is unpublished. `pdomain-book-contracts` v0.2.0 exists. [Extract Book Contracts and Retire the pd- Repos](../plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md). [Handoff](../handoff/2026-09-02-045132-book-contracts-extraction.md)
- The suite allocation plan stays in place as an active cross-repo work order. In this repo, `v0.12.0` is current master, so the plan's count of 68 unreleased commits is out of date. [Suite status and where to spend agent time](../plans/2026-09-12-suite-status-and-agent-allocation.md)

These items were checked against this repository on 2026-11-06.

The same list is in [current state](../context/current-state.md).

## Shipped behavior

- [Batched OCR dispatch](../architecture/batched-ocr-dispatch.md)
- [Page lifecycle and storage](../architecture/page-lifecycle-and-storage.md)
- [Shared suite services](../architecture/suite-services.md)
- [Shared paths and DocTR export manifests](../architecture/shared-paths-and-export-manifest.md)

## Purpose

`docs/issues/` is the canonical tracker for bounded work: bugs, regressions,
investigations, features, chores, and documentation work. GitHub Issues is not
authoritative for this repository. Each report is an evidence-bearing docgraph
node, so work remains retrievable, reviewable, and versioned with the code.

## Convention

- **Location:** `docs/issues/`
- **Filename:** `YYYY-MM-DD-short-slug.md` (creation date + a terse kebab slug).
- **Metadata:** YAML frontmatter **and** a matching `## Agent Index` block. Keep
  frontmatter `Status:` and Agent Index `Status:` identical — a mismatch trips a
  `field_conflict` (→ `status-reconciler`).
  - `Kind: issue`
  - `Level:` informational scope — `I1` repo-wide, `I2` narrow/local.
  - `Status:` governed lifecycle, **not** the issue's open/closed state (see below).
  - `Issue type:` one of `Bug`, `Regression`, `Investigation`, `Feature`,
    `Chore`, or `Docs`.
  - `Priority:` one of `P0`, `P1`, `P2`, or `P3`, from urgent to low.
  - `Area:` a stable repository component or `Cross-cutting`.
  - `Triage:` one of `Accepted`, `Needs evidence`, or `Deferred` while the issue
    is open. Rejected or duplicate work uses the matching `Resolution` value.
  - `Parent`, `Children`, `Blocked by`, and `Blocks:` relative Markdown links,
    or `None`. Keep each dependency direction consistent in both reports.
- **Issue state vs governed status:** the docgraph lifecycle is
  `draft → active → implemented → retired`. Express the *issue's* resolution state
  as a separate **`Resolution:`** line in the Agent Index (`Open` / `Resolved` /
  `Won't fix` / `Duplicate`) and a final `## Resolution` section. Map the governed
  `Status:`:
  - **Open** → `Status: active`.
  - **Resolved / Won't fix / Duplicate** → `Status: retired`, routed through
    `doc-retirer`. Promote any durable specific into the architecture or process
    doc that needs it, then delete the report, drop its README pointer, and
    append a tombstone to [`decisions.md`](../context/decisions.md). Git history
    holds the report itself, so do not keep a resolved file in the tree.
  - A `Won't fix` or `Duplicate` decision changes `Resolution` immediately;
    it cannot remain an open triage state.
- **Index it (no orphans):** add every open issue to the remaining-work list
  in this README. This is the sole issue index. Unfinished plans are listed
  there too. Resolved work lives in the
  [decisions](../context/decisions.md) tombstones and in git history.
  Context docs link here or to a specific issue only when the work changes
  current state or durable intent.
- **Stage + reindex:** under `mode = "git"` a new doc is invisible until
  `git add`ed; stage it, then `docgraph reindex` and `docgraph check --strict` the
  same turn (a new `dangling` blocks completion).
- **Template:** copy `TEMPLATE.md` in this folder. It is index-excluded (a
  top-of-file `<!-- docgraph: ignore -->` marker), so **do not markdown-link to
  it** from a governed doc — the link would dangle. Refer to it by path / inline
  code.

## Recommended structure

Every issue contains Summary, Outcome / acceptance criteria, Evidence /
motivation, Dependencies, Next steps, and Resolution. Bugs and regressions also
record environment, reproduction, ranked root-cause hypotheses, defects to fix,
and what is not broken.

Lead with the **smallest decisive evidence** and separate **observation** from
**hypothesis**. Bugs and regressions always include a **What is NOT broken**
section.
