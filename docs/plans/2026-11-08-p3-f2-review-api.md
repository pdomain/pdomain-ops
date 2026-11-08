---
Status: implemented
Owner: CT
Created: 2026-11-08
Last verified: 2026-11-08
Kind: plan
---

# P3 and F2 alignment with API-driven review

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align real scan OCR through P3 to F2 formatting, expose preparation and review through an LLM-friendly API/client, and prove that API actions update the open UI.

**Architecture:** Reuse the immutable matching core in contracts. Source-data prepares selected PGDP pages and materializes F2↔P3 evidence. The labeler matches OCR↔P3, composes both mappings, and projects formatting without reorganizing OCR words. Existing review APIs remain authoritative; a thin automation API, event stream, viewer controls, and JSON CLI connect external clients to the same UI state.

**Tech Stack:** Existing Python contracts, source-data and FastAPI jobs; React, router and TanStack Query; httpx JSON client; local Tesseract for real OCR; Chromium for API-to-UI verification.

**Spec:** [Design](#design) records the approved request and implementation choices. The owner explicitly requested planning, building, and testing this flow on real data.

**Operation:** The [API review runbook](../runbooks/pgdp-api-review.md) documents the local development workflow.

## Goal

A person or LLM can select real PGDP pages, prepare a working book, OCR it, align P3/F2, inspect disagreements, review formatting and regions, save, and export. API mutations and explicit viewer commands appear in an already-open browser without a manual reload.

## Architecture

Contracts owns pure matching and formatting projection. Source-data owns corpus catalog and selected-page preparation. The labeler owns OCR, alignment jobs, persistence, review APIs, the automation client, and live browser synchronization. An independent proof runner exercises real data through those interfaces and records measured results.

The existing matcher is `pdomain_book_contracts.matching.match_documents`; book-tools exposes re-exports. The legacy labeler P3 route uses `Page.add_ground_truth` and can reorganize words. This build uses the immutable matcher for the new flow and preserves the old route's explicit behavior.

## Tech Stack

Keep the current Python and TypeScript stacks. HTTP and existing OpenAPI are the automation contract. Use a small httpx CLI rather than a new MCP service. Keep backend records/jobs authoritative, URL navigation in the router, and server records in the existing query cache. Add no new state library for this work.

## Global Constraints

- The PGDP corpus is read-only. Write OCR, prepared books, reports and exports to isolated application or experiment folders.
- P3 supplies corrected text; F2 supplies formatting evidence. Neither file is OCR output. Real tests must OCR actual scans.
- Keep existing prepared-bundle F2-derived word IDs. Do not reissue identities from P3, current text, boxes or changed reading order.
- Represent split/join mappings explicitly. Do not modify OCR word count, order, boxes or topology simply to make an alignment fit.
- Matching and formatting suggestions never silently overwrite human corrections. Any destructive legacy rematch stays explicit.
- `/* */` means a formatted/no-rewrap block, not proven poetry. Real numeric tables, contents and title pages use it too. Retain evidence and abstain when semantic role is uncertain.
- Preserve accepted, changed, ambiguous, unmapped and exhausted outcomes. Do not hide mismatches, fabricate full coverage or silently remove existing matching limits.
- Preserve the current labels export and the reviewed-structure sidecar. Existing old prepared books and ordinary review routes must keep working.
- Use local Tesseract `eng` for the real-data proof. No model download, real training, corpus mutation, new hash/provenance gate, or external service is needed.
- Scope catalog reads to the configured corpus root and selected projects. No whole-machine search or unbounded scan/image loading.
- Reuse existing job IDs, cancellation, page leases, generation ordering and mutation routes. Do not create a second authoritative job or content store.
- API-driven navigation is an explicit viewer command. Report browser acknowledgement separately from the accepted command; a disconnected browser is not a successful UI observation.
- Work on isolated branches. Commit tested owned files locally. This new feature request authorizes building/testing, not a new release, tag, merge or push. Use local wheels for cross-repo integration until separately authorized.

## Review Focus

- Verse, numbers and captions differ between real F2/P3 rounds. Tasks 1–3 test mapped formatting, split/join groups, relocations and visible unresolved results.
- Formatter comments and `<tb>` must not become visible words. Task 1 locks the real Poems page regression.
- Statistics `07.png` uses `/* */` around numeric tables. Tasks 1 and 3 prove it is not automatically proposed as poetry.
- External API writes, jobs and viewer commands must refresh an idle browser. Task 3 tests reconnects, stale events, page changes and acknowledgement.
- Real-page matching can exceed current work limits. Tasks 1 and 4 measure timing and exhaustion; partial results remain honest and bounded.

## Agent Index

- **Kind:** plan
- **Status:** implemented
- **Owner:** CT
- **Last verified:** 2026-11-08
- **Read when:** building or testing unified P3/F2 matching, real PGDP preparation, or LLM-driven review.
- **Search terms:** P3, F2, OCR alignment, real PGDP, automation API, CLI, viewer control, SSE, split join

## Design

### Share alignment through P3

Build word-level adapters for parsed F2 visible text, P3 transcription and actual OCR. Existing source-data lexical adapters expose raw F2 markup and are unsuitable for this purpose. Preserve original source ranges and the mapping from F2 token IDs to stored bundle word IDs.

First align F2 to P3, then P3 to OCR. Compose relation groups through the same P3 token identities. Store both graphs and their decisions, rather than performing another exact F2-string search for each layout hint. A group can contain several F2, P3 and OCR tokens. Its OCR box is the union of the linked scan words; that box does not change the source identity.

Project full layout spans through groups. Project inline style ranges only where composed grapheme operations support the range. Substituted, ambiguous and unmapped portions remain unresolved, with a reason and source snippets. Do not call a partial or exhausted page fully accepted.

Keep matching bounded. Measure full-page matching early. If the existing core exhausts its budget on real pages, use deterministic page/line or unique-text anchors to split bounded work while retaining global token IDs. Keep unmatched windows explicit. Do not introduce a second unrelated fuzzy matcher or silently raise work limits.

The labeler's current one-to-one `prepared_word_bindings` cannot represent real splits/joins. Add a separate grouped binding abstraction. Use it for region geometry, accepted structure validation and refreshed geometry snapshots. Retain scalar binding behavior only where a group is genuinely one-to-one. Unsupported scalar edits must explain the conflict instead of choosing an arbitrary word.

### Preserve formatted blocks without inventing verse

Extend the hint vocabulary with `formatted_block`. F2 `/* */` uses this kind, preserving lines, whitespace, markers and source evidence. Gutenberg's explicit verse evidence or defensible source/text/geometry evidence may resolve poetry. Numeric rows, contents leaders and title layouts must not inherit the poetry role from the marker alone.

Teach the F2 tokenizer about the real `<tb>` and formatter-note case without losing following text. Retain uncertain source markup as warnings. Do not broadly strip unknown tags or editor text without a source rule and regression.

### Prepare real books without manual hash forms

Expose a bounded corpus catalog with project titles, page keys, available rounds and image metadata. Preparation accepts a project ID and explicit page keys, resolves existing snapshots/audits internally, and writes a new prepared book under the configured books folder. Callers do not assemble hash-filled TOML files.

Selected-page preparation must retain the original F2/P3 snapshots, stable source identities and selected page manifest. Keep the old full-book preparation checks unchanged for old callers. The labeler calls a configured source-data JSON CLI bridge; it does not import source-data as a hard runtime dependency.

Materialize F2↔P3 page alignment once during preparation. Loose mirrors can build a temporary analysis through the same pure API, but do not gain unsupported persisted word identities by implication.

### Reuse domain APIs and synchronize the viewer

Existing project load, OCR, page-kind, proposal review, export and job routes remain the domain APIs. Add only the missing catalog/preparation and unified-alignment routes. Publish generated OpenAPI and structured errors through the existing error envelope.

Use a shared application event stream for successful project/page/job/review changes. One frontend observer invalidates existing query keys, discovers external jobs and rejects stale generations. On reconnect, reconcile a current snapshot; do not silently lose an externally completed operation.

The broker assigns monotonically increasing event revisions. It publishes only after successful state changes. `GET /api/automation/state` includes a revision watermark. Read that watermark before and after assembling the snapshot. Retry if it changed. Under the broker's lock, register a stream subscriber and replay events after the supplied watermark. Keep a bounded replay buffer. A missing or expired cursor emits an explicit reset requiring a fresh state snapshot, not a silent jump. Support `Last-Event-ID` on reconnect, reject stale event revisions, and retain existing page-generation ordering. Test changes between snapshot, subscription, and reconnect.

Viewer controls express navigation intent. The browser applies it through the existing router and local selection mechanisms, then acknowledges the command. Ordinary content writes must not unexpectedly navigate another viewer. Keep desired view, observed acknowledgement and disconnected state distinct.

Each browser tab registers its own `viewer_id`, retained in tab-scoped session storage. Viewer commands name that ID and carry a monotonically increasing per-viewer command sequence. Acknowledgements include the same viewer ID, command sequence, observed view, and page generation. An old acknowledgement or another tab cannot satisfy the pending command. Expose disconnected and pending viewers honestly. Reconnect replays the latest desired command. Test two tabs, command supersession, stale acknowledgements, and a viewer disconnect during navigation.

An applied acknowledgement must match the commanded project, page, panel and selected IDs, and the backend's current ready page generation. A wrong-view or stale-generation acknowledgement returns a structured conflict and leaves the command unacknowledged. Record explicit application failures and mismatched observations for inspection; do not report them as success. Test wrong project/page/selection and a generation change during navigation.

## Shared public interfaces

The contracts owner freezes exact typed records and JSON examples before consumer integration. Public names:

```python
align_pgdp_page(*, f2: MatchDocument, p3: MatchDocument, ocr: MatchDocument,
                policy: MatchPolicy,
                continuations: tuple[PgdpContinuation, ...] = ()) -> PgdpPageAlignment
compose_pgdp_alignments(*, f2_to_p3: MatchGraph,
                       p3_to_ocr: MatchGraph) -> PgdpPageAlignment
project_f2_formatting(*, alignment: PgdpPageAlignment,
                     hints: tuple[LayoutTextHint, ...],
                     style_spans: tuple[StyleSpan, ...]) -> PgdpFormattingProjection
```

Place these in `pdomain_book_contracts/matching/pgdp_layout_projection.py`. The result retains both graphs, grouped F2/P3/OCR token IDs, dispositions, warnings and work/timing summaries. Composition must validate the shared P3 document identity and token text. Include a parsed-visible-text adapter and an explicit source-word-ID lookup. Do not fabricate byte offsets from Python string indices.

Source-data adds a typed catalog/preparation library and a JSON CLI entry point. Requests carry configured corpus root, project ID, selected page keys and destination root. Responses carry prepared-book path, selected pages, alignment summaries and explicit failure details. It can be invoked by a configured Python interpreter with `-m`, avoiding shell command interpolation.

New labeler routes:

| Route | Meaning |
| --- | --- |
| `GET /api/pgdp/projects` | Bounded configured-corpus catalog, query/limit/offset |
| `GET /api/pgdp/projects/{id}/pages` | Available real page keys and source rounds |
| `POST /api/pgdp/prepare` | Submit selected-page preparation; return existing job ID |
| `POST /api/projects/{id}/pages/{index}/source-alignment` | Submit unified alignment through existing job runner |
| `GET /api/projects/{id}/pages/{index}/source-alignment` | Current result, group links, projected formatting, unresolved counts |
| `PATCH /api/projects/{id}/pages/{index}/source-alignment/groups/{group_id}` | Review a current group's suggestion, with expected generation |
| `GET /api/automation/state` | Loaded project, page readiness/generation, jobs, capabilities and viewer state |
| `GET /api/automation/events` | Typed app-change/viewer-command SSE |
| `POST /api/automation/viewers` | Register one browser tab and return its viewer ID |
| `GET /api/automation/view` | Desired command and latest browser acknowledgement |
| `PATCH /api/automation/view` | Explicit project/page/panel/selection command |
| `POST /api/automation/view/ack` | Browser acknowledgement tied to command sequence |

Use `pdomain-ocr-labeler-control` as the JSON CLI entry point. Commands cover catalog, prepare, load, page, OCR, align, inspect, view/select, proposals, accept/edit/reject, export and job wait/cancel. Wrap existing routes rather than duplicate their implementation. Long commands use bounded wait timeouts and return authoritative final job state. Use the existing job admission semantics so retrying one logical preparation/alignment operation does not silently create duplicate work.

For real OCR, expose an explicit `tesseract` engine through the job/provider boundary and capabilities. Keep the current default provider unchanged. The dedicated proof server uses Tesseract for page loading and explicit OCR requests, preventing accidental model downloads. A missing binary/language is a structured capability error, not a silent fallback.

Group review and saved decisions must reference the current alignment result/page generation. Stale requests fail explicitly. Suggestions do not overwrite human GT or typography edits. The new UI shows P3 wording, F2 formatting, OCR words, group mapping and unresolved reasons beside existing region review.

## Real examples and proof

The corpus root is `/mnt/work/projects/pdomain-data/pgdp-corpus`. Keep it read-only. All three books have matching F2/P3 page-key sets, and their `pages.json` equals P3; it is not OCR.

| Project and book | Selected pages | Required observations |
| --- | --- | --- |
| `projectID64ff850152930`, Poems by Elizabeth Bibesco | `008.png`, `009.png`, `026.png` | Verse indent/stanzas, capitalization difference, `<tb>` and formatter notes |
| `projectID68658d72319cb`, A Book of European Statistics | `03.png`, `07.png`, `15.png` | Contents leaders, numeric tables encoded with `/* */`, `11 717` versus `11717` |
| `projectID61186e62da1bd`, Century magazine May 1882 | `020.png`, `081.png`, `082.png` | Real physical two-column page with illustrations/caption relocation; quote, footnote and continuation |

Initial actual OCR has been generated with installed Tesseract 5.5.3, `eng`, `--psm 3`, one CPU thread per page. Outputs are in `/tmp/pdomain-p3-f2-20261108/artifacts/ocr`. The durable proof command must regenerate or explicitly validate/reuse actual OCR caches; it must never substitute P3 for OCR.

Report every selected page: input identities, OCR engine, word counts, F2↔P3 and P3↔OCR outcomes, projected/unresolved formatting, split/join examples, topology preservation and elapsed work. Distinguish source evidence, algorithm decisions and human review. Negative cases and exhausted pages stay in the report.

The browser proof uses a real prepared book. Keep it open and idle, then drive a separate HTTP/CLI client: load/navigate, OCR, align, inspect groups, propose and review regions, edit a decision, save/reload and export. Verify visible updates without reload, selected-ID acknowledgement, review queues and persisted/exported structure. Include cancellation, stale generations, missing source rounds, disconnected viewer and SSE reconnect. Existing synthetic regressions remain useful but do not replace this real-data proof.

## Tasks and ownership

### Pre-Task-1 gate: isolation and interface freeze

- [x] Assign owned worktrees and record them before product edits. Root owns this plan; product and proof owners have disjoint files.
- [x] Contracts publishes the exact typed records, serialized examples and first functional local wheel before contract-dependent graph adapters, materialization, grouped bindings and formatting integration begin. The wheel must pass its focused contract/matching tests; a stub package is not a handoff. Subsequent changes require coordinator notification and an updated wheel.
- [x] Independent catalog/page scanning, JSON transport, Tesseract provider, automation broker/client, viewer controls and frontend event synchronization may proceed against their frozen HTTP/CLI contracts and existing published dependencies. These files do not consume the unreleased matching types. Real OCR collection and proof-runner scaffolding may also proceed. Contract-dependent integration waits for the functional wheel/examples, and final verification uses the final reviewed wheel.

### Task 1: Pure shared alignment and formatting projection

**Owner:** contracts session. **Files:** new `matching/pgdp_layout_projection.py` and tests; F2 `tokens.py`/`structure.py`; `layout/text_hints.py` for `formatted_block`.

- [x] Write failing tests for graph composition, shared-P3 mismatch, many-to-many groups, exact style-grapheme projection and unresolved substitutions. Use real word excerpts for number split/join, caption relocation, `<tb>` comments and numeric formatted blocks.
- [x] Run focused tests to confirm missing behavior fails, then implement visible-text adapters and bounded composition using the existing matcher.
- [x] Benchmark actual full pages early against real Tesseract TSV/P3/F2. Add bounded anchors if necessary; record timing and exhaustion rather than hiding it.
- [x] Run the contracts gate and mandatory independent Python review. Freeze typed interfaces/JSON examples, build a local wheel, and report its exact path before consumers finalize.
- [x] Commit only owned tested files locally. Do not release or push.

### Task 2: Corpus catalog and selected-page preparation

**Owner:** source-data session. **Files:** new corpus catalog/preparation module and JSON CLI bridge; existing typography preparation/publication modules; tests and user-facing command documentation.

- [x] Write failing tests for bounded project/page queries, missing rounds, selected-page manifests, corpus read-only behavior, destination selection and old full-book compatibility.
- [x] Implement selected-page preparation and F2↔P3 materialization with contracts. Preserve existing F2-derived bundle IDs and immutable source snapshots.
- [x] Expose a JSON CLI that resolves necessary existing audit/source inputs internally. Return structured progress/results/errors for the labeler job adapter; do not require callers to fill hash templates.
- [x] Prepare the three real selected books/pages outside the corpus and publish artifacts to the coordinator. Run required gates and independent Python review with the real contracts wheel.
- [x] Commit owned tested files locally. No release/push or real-corpus mutation.

### Task 3: Unified labeler jobs, API controls and live UI

**Owner:** labeler session. It may delegate disjoint backend alignment/provider files, automation/client files, and frontend/event files to parallel subagents, with one integration owner.

**Files:** new alignment service/job/API models and routes; grouped bindings in `core/regions/layout_structure.py`; `core/regions/text_layout.py`; source-data process adapter; Tesseract provider; automation broker/routes/client; frontend API observer, alignment panel and viewer control; generated API types and tests.

- [x] Write failing backend tests for composed mappings, many-to-many bindings, human edit preservation, current-generation review, job cancellation, retry admission and real Tesseract integration.
- [x] Use materialized F2↔P3 and current OCR↔P3 mappings in the actual proposal path. Remove independent exact F2-text matching from the new flow. Keep unresolved results inspectable and old prepared books/legacy review functional.
- [x] Add the missing catalog/preparation and alignment HTTP routes through existing jobs and a configured source-data JSON subprocess bridge. Add explicit Tesseract capability/provider and per-job selection while retaining existing defaults.
- [x] Implement the JSON control client over existing domain routes and new endpoints. Test job waits, page-load jobs, cancellations, timeouts and structured errors against a real server.
- [x] Implement typed change SSE and viewer commands with acknowledgement. Reuse router/query owners and page generations. Test externally started jobs, external content changes, reconnect, out-of-order events and disconnected viewers.
- [x] Add review UI for source/group comparisons and projected formatting. Browser-test an already-open real book under external API/CLI actions through acceptance, edits, reload and export. Check existing keyboard/region/edit flows.
- [x] Run required backend/frontend gates, OpenAPI generation, Python and TypeScript reviews, and local-wheel runtime proof. Commit tested owned files locally; stop only test-owned servers.

### Task 4: Independent real-data proof tooling

**Owner:** proof implementer, separate from product owners. **Files:** `pdomain-ops/scripts/real_pgdp_review_proof.py`, focused harness tests and a scoped usage document if needed. Root owns this plan/current-state.

- [x] Build a repeatable bounded harness with explicit corpus/output/server/client paths, selected-case file, timeouts and JSON report. Existing actual OCR TSV is an initial cache, not a substitute for an executable real-data workflow.
- [x] Exercise source preparation and labeler operations through their public JSON CLI/HTTP interfaces. Record actual OCR, matching/projection metrics, unresolved cases and invariant failures for all nine pages.
- [x] Independently verify stats tables are not blindly poetry, source notes do not become words, verse/stanza/indent survives where mapped, real columns remain distinct, and topology/IDs survive review/export.
- [x] Drive browser-visible state through API commands on a real selected book. Preserve scan/source references and evidence screenshots/traces. Report exact failures; do not weaken cases to manufacture coverage.
- [x] Run the tooling gate and review. Commit owned tooling locally and publish evidence paths to the coordinator. Never modify product owners' files or the corpus.

### Task 5: Coordinator integration and completion

- [x] Review this combined design/plan and verify the pre-Task-1 gate was satisfied before dependent product edits.
- [x] Feed actual OCR and source discrepancies back into implementation early. Keep shared API changes synchronized across owners.
- [x] Inspect diffs, required reviews, real-data reports and browser traces; independently rerun the bounded proof from the built artifacts.
- [x] Record successes and remaining mismatches per real page, update current-state and usage instructions, and run docgraph checks after documentation changes.
- [x] Report runnable API/client commands and real examples. Keep this new work local until a separate merge/release request; do not claim trained-model quality or full-corpus coverage.

## Real-data outcome

The repeatable harness completed 152 public operations across all nine selected pages against the installed `0.6.1.dev11+gbbd043542` labeler wheel. It prepared real books and ran native Tesseract without a TSV cache. It then aligned F2 through P3 to OCR, reviewed groups and structured regions, saved, reloaded, and exported. A separate coordinator audit confirmed that all 1,530 OCR words retained their order, IDs, text, and boxes through review and reload. The corpus remained unchanged.

| Page | Actual OCR words | Composed alignment | Unresolved formatting items |
| --- | ---: | --- | ---: |
| Poems `008.png` | 38 | ambiguous | 1 |
| Poems `009.png` | 88 | changed | 1 |
| Poems `026.png` | 146 | ambiguous | 1 |
| Statistics `03.png` | 103 | exhausted | 1 |
| Statistics `07.png` | 155 | exhausted | 2 |
| Statistics `15.png` | 212 | exhausted | 2 |
| Century `020.png` | 241 | exhausted | 2 |
| Century `081.png` | 236 | exhausted | 1 |
| Century `082.png` | 311 | exhausted | 1 |

These results verify the workflow and the specified positive and negative checks. They do not mean that every page is fully matched or formatted. Safe local mappings remain useful on an ambiguous or exhausted page. Poems `008.png` and `009.png` exported five and nine reviewed verse lines, with 27 and 85 source word IDs respectively. Their remaining formatting uncertainty stays explicit.

Century `020.png` exported two separate paragraph regions with `column_flow` metadata, one shared column group, column indices 0/1, and reading order 0/1. Their boxes exclude the shared running header. They are not table regions. Statistics `07.png` produced actual non-poetry proposals, and Poems `026.png` retained no formatter-note or `<tb>` markers in its visible F2 text.

Century `081.png` and `082.png` produced no false inferred columns. The continuation on `082.png` retained an F2-backed blockquote and exported 27 lines with 258 source word IDs. Specific quotation details on `081.png` remain unresolved. The inference fix requires independent complete original OCR lines on both sides of a proposed gutter; fragments left after another hint cannot establish columns.

The real Poems browser proof verified explicit API navigation, F2/P3/OCR group display, visible review updates without a reload, two independent tab IDs, targeted word selection, offline command replay, and stale-generation acknowledgement rejection. Earlier render-loop and reconnect failures were fixed and retained as regression evidence.

The committed proof selection is `scripts/fixtures/real-pgdp-review-cases.tsv` in the `feat/p3-f2-proof` ops worktree. Its JSON report records raw operations, per-page metrics and unresolved outcomes. The [API runbook](../runbooks/pgdp-api-review.md) gives the executable workflow.

### Evidence locations

Coordination receipts and regenerable data live under `/tmp/pdomain-p3-f2-20261108`. The final installed nine-page report is `artifacts/proof/full9-column-guarded-installed-real.json`. Independent raw-page and actual export checks are in `artifacts/proof/coordinator-installed-raw-topology-check.json` and `artifacts/proof/coordinator-installed-export-check.json`. Earlier reports remain as historical evidence; they do not cover the final quotation-column guards. The real column API proof and independently checked exported files are recorded in `artifacts/browser/century-columns-api-proof.json` and `artifacts/browser/coordinator-column-export-check.json`. The browser result is `artifacts/browser/browser-proof.json`, with screenshots beside it.

Contracts commit `1bd8261` passed its 79-test gate and 103 downstream book-tools matching tests. Source-data commit `f3d73fd` passed 510 tests, with three optional corpus tests skipped, and prepared all nine pages from its installed wheel outside the checkout. Ops proof commit `adb148d` passed 485 tests, with one optional test skipped, plus independent Python review. Labeler commit `bbd0435` passed 2,254 backend tests with one expected GPU-unavailable skip, all four Docker checks, and 2,258 frontend tests. The installed `0.6.1.dev11+gbbd043542` wheel passed all eight Chromium tests and fresh native OCR checks on the real two-column page and two single-column quotation pages. The final installed nine-page run passed all 152 operations, seven behavior checks and two explicit partial verse results, with no behavior failures. No new feature release, merge or push has occurred.
