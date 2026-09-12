---
Status: draft
Owner: CT
Created: 2026-09-12
Last verified: 2026-09-12
Kind: plan
---

# Suite status and where to spend agent time

**Goal:** State where each of the seventeen workspace repositories stands, and allocate the next block of agent work across Claude, Codex, and Grok so that page-layout OCR reaches a state a person can use.

**Architecture:** Three layers. Shared contracts and engines, applications, and data and registries.

**Tech Stack:** Python with uv and hatchling, React with Vite and pnpm, PP-DocLayout and DocTR.

**Global Constraints:** Every task leaves its repository green under that repository's own gate, suppresses nothing to get there, and names the release that carries any contract it crosses.

## Agent Index

- **Kind:** plan
- **Status:** draft
- **Owner:** CT
- **Last verified:** 2026-09-12
- **Read when:** deciding what to work on next anywhere in the workspace, allocating agent sessions, or asking why page-layout OCR has not moved.
- **Search terms:** suite status, agent allocation, release debt, page layout OCR, region proposals, build failure, venv-container, Codex, Grok, Claude.

## Goal

Answer two questions in one place. Where is every repository, and what should the next agent session do?

The suite is not short of engineering capacity. It is held up by five owner decisions and by release debt that has been building for weeks. Roughly two hours of deciding unblocks several weeks of agent work that is already planned and reviewed.

## Architecture

The suite splits into three layers. Shared contracts and engines sit in `pdomain-book-contracts`, `pdomain-book-tools`, `pdomain-ops`, and `pdomain-ui`. Applications sit in the four single-page apps, the simple GUI, and the CLI. Data and registries sit in `pdomain-source-data`, `pdomain-fonts`, and the two package indexes.

Page-layout OCR crosses all three layers. A vocabulary defined in the contracts package must be released before the engine can enforce it, and the engine must be released before the labeling app can use it. That chain is why progress is gated on releases rather than on code.

## Tech Stack

Python 3.11 through 3.13 with uv, hatchling, pytest, Ruff, and basedpyright. React 19 with Vite, TypeScript, Vitest, and pnpm on the frontends. PP-DocLayout for layout detection and DocTR for detection and recognition training.

## Global Constraints

- Every task below must leave its repository green under that repository's own `make ci AI=1`.
- No task may suppress a lint or type error to pass a gate.
- A cross-repo task must name the release that carries its contract, because a contract that is not released cannot be consumed.
- Two agents must not hold the same repository in the same cycle.

## Every repository builds, after two fixes

A build of all seventeen repositories ran on 2026-09-12. Fifteen have a build target; `pdomain-fonts` and `pdomain-pgdp-api-client` do not. Thirteen built on the first attempt. Two failed for the same reason, and both now build.

`pdomain-ops` and `pdomain-ocr-training` packed the container's virtual environment into their source distribution. The build rejects that, because the environment holds an absolute symlink to the Python interpreter. The devcontainer names its environment `.venv-container`, but both repositories excluded only `.venv`. Their siblings `pdomain-book-contracts` and `pdomain-book-tools` already carried the right exclusion.

The fix copies the sibling pattern into each `pyproject.toml`. Both repositories now produce a clean source distribution and wheel, and the resulting archive contains no environment files. The change is **uncommitted**. Step 2 of the sequence below commits and verifies it.

```toml
[tool.hatch.build.targets.sdist]
exclude = ["**/.venv", "**/.venv-container"]
```

The suite build is not a bottleneck. Build times ran from one second to forty-five seconds.

## Release debt is the real bottleneck

Five shared packages have drifted well behind their last tag. Nothing downstream can consume what has not been released, so this debt turns directly into blocked tasks.

| package | last tag | commits since |
| --- | --- | ---: |
| `pdomain-ops` | v0.11.2 | 59 |
| `pdomain-ui` | v0.11.0 | 55 |
| `pdomain-ocr-training` | v0.2.3 | 50 |
| `pdomain-book-tools` | v0.27.0 | 10 |
| `pdomain-pgdp-measure` | none | never released |

`pdomain-pgdp-measure` has no tag at all. It was extracted on 2026-09-07 and reproduces its pre-move baseline byte for byte. No repository in the workspace lists it as a dependency. It is a finished package with no consumers.

The book-tools gap has a concrete cost. The labeler pins `pdomain-book-tools` v0.27.0 exactly, so 14 of the 34 roles still fail every region route it serves.

The block role vocabulary was widened from 20 roles to the full 34 on 2026-09-08, and the widened set now matches the released `RegionRole` enum exactly. That commit is on master and is not in v0.27.0.

An older note describes this as unfinished code. It is finished code waiting on a release.

## Page-layout OCR: the vocabulary shipped, and nothing generates a proposal

The labeling track has seven slices. Slice 1 shipped and released. Slice 2 is nearly complete. Slices 3 through 7 are unplanned by intent, because each needs its own design first.

**Slice 1 shipped and released.** `pdomain-book-contracts` v0.2.0 carries a 34-value `RegionRole` enum and a 14-value `PageKind` enum. Both import without the imaging or machine-learning stack.

**Slice 2's stores and seven of its eight routes shipped and merged.** The labeler has a region store, a proposal journal, a decision journal, a resolver, and an adapter that lifts marked blocks out of the page tree. The routes cover create, edit, delete, word membership, list proposals, accept, and reject. The canvas renders confirmed regions and above-threshold proposals, drawn so the two are visibly different.

**The eighth route did not ship.** The book-scoped propose route and the proposal-run job were skipped, because they import two modules the page-kind work had not yet built. The handoff states the consequence plainly: every proposal in the system today was written by a test. Nothing generates a proposal in production.

**Three branches carrying page-kind work have sat unmerged since 2026-09-09.** All three are built, reviewed, and gate-green. The integration question was put to the owner and not answered.

| repository | branch |
| --- | --- |
| `pdomain-book-tools` | `feature/page-kind-field` |
| `pdomain-pgdp-measure` | `feature/page-class-confidence` |
| `pdomain-ocr-labeler-spa` | `feature/page-kind-stores` |

**No region review surface exists.** The labeler frontend carries generated TypeScript types for the seven shipped routes and no client code that calls any of them. A person can see a region on the canvas and cannot draw, edit, accept, or reject one.

**No geometry proposal engine exists.** This is the slice that turns measured typography into proposals, and therefore the slice that makes the labeler produce anything worth reviewing. The signals it needs are measured and on disk. Nothing reads them.

**Nothing can train a layout model.** `pdomain-ocr-training` ships DocTR detection and recognition only. The layout registry in `pdomain-book-tools` offers three built-in detectors and accepts registered ones, but only its own tests register anything. The CLI accepts a layout checkpoint path, and nothing in the workspace produces a checkpoint. The workspace training and validation directories are empty.

**No region ground truth exists anywhere in the suite.** The roadmap names this as the fact that drives the whole track. The labeler is not only a review tool. It is the only thing that can produce the corpus a layout model would need.

## What each written plan is actually doing

Nine plans were written for this track. Four have shipped, one is partly shipped, and four have never run. Statuses in the plan files still read active in every case, so they cannot be trusted. The dispositions below come from the code.

| plan | disposition |
| --- | --- |
| Annotation vocabularies | shipped and released in book-contracts v0.2.0 |
| Annotation preconditions | merged to book-tools master, unreleased |
| Region stores and resolver | shipped and merged in the labeler |
| Region routes and proposal run | seven of eight routes merged; Task 5 never ran |
| Page kind end to end | Tasks 1 to 5 on three unmerged branches; Tasks 6 and 7 blocked on releases |
| Word and glyph provenance | never run |
| Explicit membership and matching | never run |
| Style span review surface | never run |
| Editorial corrections | never run |

The four that never ran are deferred for this cycle, not dropped. Revisit them once proposals reach production.

## The five decisions that unblock the most work

Each of these is the owner's to make, and none needs engineering first.

1. **Merge, open pull requests for, or hold the three page-kind branches.** The labeler branch is the one that unblocks other work.
2. **Release `pdomain-pgdp-measure`.** This blocks page-kind Task 6, which turns a classifier residual into a confidence the labeler can show.
3. **Release `pdomain-book-tools`** carrying the page-kind field, and bump the labeler's pin from 0.27.0. This blocks Task 7 and restores the 14 failing roles.
4. **Close or restate Gate 3 on the glyph inventory.** Label correctness measures 0.978 against a floor of 0.98, and two of five books fail. Filtering five quality flags gives 0.994 with every book clear. Filtering is the only route that passes as measured. Re-running the alignment chain changes nothing, and showing label style recovers only three of the 23 marks.
5. **Pick the text-chain design** in `pdomain-prep-for-pgdp`: compound wordcheck, rewiring the stage graph, or fan-in at the runner. Its own plan makes this the first step of the next session, and no pipeline work should start without it.

## Where the ancillary apps stand

**`pdomain-prep-for-pgdp` has a complete skeleton and cannot finish a book.** Twenty-four pipeline stages are registered with real callables, and every stage has a state machine. A real book walk still fails on nine counts, including a wordcheck stage that emits flags where the next stage expects text, and a shell that runs only the first page for most page stages. All thirteen Wave 0 and Wave 1 issues are still marked active, unchanged since 2026-07-21, and thirty issue documents are open in total.

The working tree holds six uncommitted files on the zip tool as of 2026-09-12: five in the frontend and one a statechart document.

**`pdomain-book-tools` carries the largest engine backlog and is not quiet.** Sixty-six issue documents are active. Several are layout work that needs no model at all: reclassifying small ornamental figures as decoration, tuning the sidenote height ratio, estimating true x-height by projection, cross-checking drop caps against the heading above, and page-order detection. These improve page layout OCR directly.

**`pdomain-ocr-simple-gui` has one open item, and its blocker is stale.** The suite launcher opener isolation issue is recorded as blocked on a `pdomain-ui` release. That fix is already in the released v0.11.0, and all four single-page apps already pin that line. The item needs verification, not a release.

**`pdomain-ocr-trainer-spa` is quiet.** Six active issue documents, five of them from the July cutover. The immediate item is documenting the two job surfaces. The next is extending evaluation with glyph-keyed slices.

**`pdomain-ocr-cli` has two correctness items.** Layout detection and illustration crops run against the unrotated page image, and no test asserts that default layout reorganization preserves every OCR word.

**`pdomain-ocr-synth` owns the roadmap and is waiting on the labeling track.** Its product track stops at M10, and M11 is being rescoped onto FastAPI and React. Its measurement track shipped through M15 and stops at M16, the join between measurement and synthesis, which is still unspecified.

**The remaining support repositories are healthy.** `pdomain-book-contracts`, `pdomain-ops`, `pdomain-ui`, `pdomain-source-data`, `pdomain-pgdp-api-client`, `pdomain-fonts`, and the two package indexes carry three or fewer open issues each and need no scheduled work beyond the releases named above.

## How to split work across the three agents

The three hosts share the same lint, type, and test gates, so split by task shape rather than by capability. Judge each task by how much cross-repo judgment it needs and how falsifiable its finish line is.

**Give Claude the cross-repo contract work.** These tasks span two or three repositories, need the plan corrected when execution finds it wrong, and finish only when a whole-branch review says so. The page-kind session is the evidence. Two adversarial reviews and a gap scan all missed three plan defects that execution caught, including a stored null actor that read back as the string `"None"`.

1. Page-kind Tasks 6 and 7, once the releases land.
2. The proposal-log guard, landed alongside Task 6 rather than after it. Three methods index a record key without guarding it, in two files that must keep the same shape. The existing malformed-line test cannot catch this, because it feeds a syntactically broken line that an existing handler already swallows. The guard is done when a test feeds well-formed JSON of the wrong shape and fails without the fix.
3. Region-routes Task 5, the propose route and the proposal-run job. Done when a proposal written outside a test appears in the journal and renders on the canvas.
4. Slice 4, the geometry proposal engine, in two halves. The design half is done when a reviewed design note records the recomputed chapter-opening figure and states whether it is precision or recall. The build half needs its own acceptance criteria, written into that design.

**Give Codex the single-repo work that already has a written finish line.** Every Wave 0 and Wave 1 issue in `pdomain-prep-for-pgdp` carries a falsifiable clause, a governed issue document, and a repository gate. That shape runs well without supervision.

1. Wave 0, six issues, once decision 5 is made. The text-chain contract, the project-stage job adapter, the attestation writer, the multi-page stage run, the text-zones split contract, and the golden-path regression in default CI.
2. Wave 1, seven issues, after Wave 0 exits green.
3. The two `pdomain-ocr-cli` correctness items.

**Give Grok the broad mechanical passes where the gate is objective and the work repeats.** These are wide, shallow, and tedious, and each passes or fails mechanically. None of them touches the labeler, so none collides with Claude.

1. The `pdomain-pgdp-measure` test tree. Measured on 2026-09-12 at current master, the repository reports 1442 errors and 948 warnings. The test tree alone accounts for all 1442 errors, and the source tree is clean, at zero errors and 229 warnings. The repository's own configuration comment describes only the source tree and states 176 warnings, which is wrong.
2. The `pdomain-book-tools` layout items listed above. Each is self-contained and improves layout output without a model.
3. The flat-ascender review queue. Five books carry 490 queued, unreviewed words in their glyph manifests, written by the glyph inventory in `pdomain-pgdp-measure`. The rendering script is `render_flat_queue.py` in the workspace-root evidence directory `.m15f-evidence/`.
4. Verifying and closing the stale `pdomain-ocr-simple-gui` launcher item.

**Hold one labeler task for a later cycle.** The dictionary type annotations across the labeler's page-kind and region modules should be one pass over both directories. Claude holds those files for this whole cycle, so schedule this pass only after the labeler branch merges and Task 5 lands.

## Sequence the first three weeks like this

1. **Make the five decisions.** Nothing below starts cleanly without them.
2. **Commit and verify the build fix.** Commit the exclusion in `pdomain-ops` and `pdomain-ocr-training`, run each repository's full gate and a build, and confirm the archive carries no environment files. If either gate or an install breaks, revert the exclusion line. Nothing else depends on it.
3. **Merge the three branches, then cut the releases, in that order.** Book-tools cannot be released carrying the page-kind field until its branch merges. Release `pdomain-pgdp-measure` and `pdomain-book-tools` first, and consider `pdomain-ops`, `pdomain-ui`, and `pdomain-ocr-training` in the same pass to clear the drift, after step 2 lands.
4. **Run Claude and Codex in parallel.** Claude takes page-kind Tasks 6 and 7 with the proposal-log guard, then region-routes Task 5. Codex takes Wave 0. The two touch no repository in common.
5. **Start Grok at the same time.** Its four items block nothing and unblock an honest gate.
6. **Design Slice 4 before building it.** The recorded claim is that 43 to 67 percent of pages show high x-height spread. That figure reads either as precision or as recall, and the two say different things about whether the signal is usable. No evidence file records the calculation. Recompute it before anything depends on it.
7. **Build Slice 4 before Slice 3.** Slice 4 would produce proposals with no surface to review them, and Slice 3 would build a surface with nothing to review. Build the engine first, drive it over the REST interface, and let the review surface follow once proposals are real. The owner settled this ordering on 2026-09-12; it is a decision, not a recommendation.

## What this plan does not settle

- The labeled-dataset contract the synthesizer reads at M16. It joins the two halves of the suite and is still unspecified.
- Whether the confirmed corpus will be large enough to train a layout model. That cannot be known until the middle slices have run on real books.
- Whether `pdomain-ocr-training` widens its runner protocols for a third task pair, or layout training lands elsewhere. The roadmap argues for widening, because that repository already owns the DocTR training loops.
- Where region model training runs. This machine has an 8 GB laptop GPU, and the existing plan puts real fine-tuning on rented cloud GPUs.
