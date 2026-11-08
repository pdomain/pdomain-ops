---
Status: implemented
Owner: CT
Created: 2026-11-08
Last verified: 2026-11-08
Kind: plan
---

# Source tabs and page refresh implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show F2, P3 and a read-only consolidated transcript in the text tabs, and refresh page-specific content correctly during navigation.

**Architecture:** The router owns the displayed page. Existing query caches own server records, with project-load epochs separating generation sequences. A read-only source endpoint reads verified prepared snapshots and projects supported F2 formatting through the persisted F2-to-P3 graph.

**Tech Stack:** Existing FastAPI, Python contracts, React, TypeScript, TanStack Query and Chromium tests.

**Spec:** [Accepted design](#accepted-design), including the owner's explicit choice of a read-only consolidated preview.

## Agent Index

- **Kind:** plan
- **Status:** implemented
- **Owner:** CT
- **Last verified:** 2026-11-08
- **Read when:** implementing source text tabs or diagnosing stale content after navigation.
- **Search terms:** P3, F2, consolidated GT, Working GT, page refresh, generation, navigation

## Goal

Make source rounds and their consolidated preview available beside existing text review, with consistent page navigation.

## Architecture

The labeler reads verified source snapshots and persisted matching evidence. Its existing router and query cache keep the displayed page and loaded records consistent.

## Tech Stack

Reuse FastAPI, Python contracts, React, TypeScript, TanStack Query and the existing Chromium test environment.

## Global Constraints

- Keep the source corpus read-only and preserve OCR word identities and saved corrections.
- Consolidated GT is a preview. P3 supplies its wording; supported F2 evidence supplies formatting.
- Keep unresolved formatting visible and identify its source text. Do not force an exact mapping through changed or exhausted spans.
- Keep word-correction controls in Matches. Working GT shows the current corrected text as a read-only view.
- Source tabs must work without OCR or an OCR alignment job.
- Keep existing libraries, domain routes, structured errors and test IDs. Add no state library.
- The new work stays local. No merge, push, model downloads, training or corpus writes.

## Review Focus

- Clicking Go must use the typed number even when the input loses focus before the click handler runs.
- A completed project or page reload must accept generation zero while rejecting late responses from the previous load.
- Page-local selections must not carry reused line or node indexes into another page.
- A late source response must not appear under a different page's source tab.
- Missing PGDP sources must show an unavailable state while ordinary OCR and correction tabs remain usable.
- Supported F2 verse indents and line structure must appear in the main consolidated preview, rather than only in its evidence details.

## Accepted design

The text tabs will be Matches, Working GT, P3, F2, Consolidated GT and OCR. P3 and F2 show the prepared page's original transcription, including F2 markers. Working GT shows the current corrected text; individual word edits remain in Matches. Consolidated GT shows P3 visible text with reliable F2 formatting and named unresolved spans. It does not change reviewed GT or OCR.

Source-to-source formatting is independent of OCR matching. A misspelled OCR word must not prevent an exact F2-to-P3 style from appearing in the source preview. Formatted blocks do not automatically become poetry or tables. Existing verified whitespace and supported layout evidence remain inspectable.

Normal page navigation, Go, Enter, browser back/forward and API-directed navigation must agree on page identity. Worklist, Hierarchy, text views and source panels use that identity. Queue remains book-wide and must say so.

## Implementation ownership

Only the labeler needs product changes. Contracts supplies existing immutable matching records; source-data already stores verified F2/P3 snapshots and alignment evidence. Ops owns this plan and the final browser receipts.

### Task 1: Repair navigation and page state

**Files:** `frontend/src/components/ProjectNavigationControls.tsx`, `frontend/src/lib/page-cache-order.ts`, `frontend/src/hooks/usePage.ts`, `frontend/src/hooks/usePageMutations.ts`, `frontend/src/hooks/useAutomationViewer.tsx`, the automation event parser, Worklist, Hierarchy, their stores and focused tests. The backend publication wrapper and broker add the explicit reload marker.

**Interfaces:** Preserve existing page query keys and within-epoch generation ordering. Add an explicit project-load boundary that rejects responses from the old load. Only a successful terminal response from `POST /api/projects/{project_id}/pages/{page_index}/load` publishes `page_changed.generation_reset: true`. Ordinary events retain their existing field shape and omit the marker. Consumers cancel old requests before resetting ordering and refetching. Coordinate any ProjectPage wiring with Task 3.

- [x] Write failing tests for fill-then-click-Go, page-local selections and lower generations after project reload.
- [x] Fix the navigation handler and state ownership without removing stale-response protection.
- [x] Run frontend lint, types and focused tests; obtain TypeScript review.
- [x] Reset the response epoch at successful explicit page-reload completion, including API-driven reloads, and test late pre-reload responses.

### Task 2: Expose a read-only source preview

**Files:** `src/pdomain_ocr_labeler_spa/core/source_text.py`, `src/pdomain_ocr_labeler_spa/api/source_alignment.py`, `tests/unit/core/test_source_text.py`, `tests/integration/test_book_manifest_loader.py` and generated OpenAPI types in the labeler worktree.

**Interfaces:** `GET /api/projects/{project_id}/pages/{page_index}/source-text` returns project/page identity, availability, raw and visible F2/P3, consolidated text and styled runs, supported layout hints, unresolved source text and warnings. Styled runs concatenate exactly to P3 visible text. The coordination wire contract is `/tmp/pdomain-source-tabs-20261108/contract.json`.

- [x] Write failing tests for source access before OCR, exact style projection, named unresolved spans, quarantined windows, mismatched evidence, missing sources and unchanged review data.
- [x] Read verified prepared artifacts and the persisted F2-to-P3 graph through existing public records.
- [x] Generate OpenAPI types and run Python lint, types and scoped tests; obtain Python review.

### Task 3: Integrate source tabs

**Files:** `frontend/src/components/TextTabs.tsx`, `frontend/src/components/SourceTextPreview.tsx`, `frontend/src/api/source-text.ts`, `frontend/src/pages/ProjectPage.tsx` and their focused tests.

**Interfaces:** Consume Task 2's endpoint through a project/page-scoped query. Preserve the existing `text-tab-ground-truth` test ID for Working GT. Add stable selectors for P3, F2 and Consolidated GT.

- [x] Write failing tests for each tab, read-only behavior, unavailable sources and late page responses.
- [x] Integrate the source views and existing correction controls without duplicate editors beneath the tab panels.
- [x] Run frontend lint, types and focused tests; obtain TypeScript review with Task 1.
- [x] Project accepted layout-line target ranges and render their F2 indents while preserving P3 line and stanza structure in the main preview.

### Task 4: Verify and install the combined build

**Files:** Existing labeler CI/build tools and coordination receipts outside the corpus.

- [x] Run the repository's full CI gate with the reviewed local contracts dependency before committing.
- [x] Commit locally, build and install the wheel, and preserve prepared books and saved reviews during restart.
- [x] Test the installed UI on real Century and Poems pages through arrows, Go, Enter and back/forward, checking every page-specific tab and source text.
- [x] Verify exact supported italics and verse evidence, visible unresolved formatting, preserved Working GT and all three project Open buttons.
- [x] Record measured results and limitations, then run docgraph checks.

## Outcome

Navigation, source API and tab integration are implemented. Initial focused checks passed 148 frontend tests and 10 backend tests, plus lint and type checking.

Source previews were exercised through HTTP on nine real prepared pages without loading OCR pages or starting OCR jobs. Explicit GUI and API page-reload boundaries are implemented and reviewed. The working-tree browser proof passed all six tabs through Go, Next, Enter, Back and Forward. External reload accepted generation zero and was acknowledged without a browser refresh.

The final candidate passed full CI: 2,269 backend tests, one expected GPU-unavailable skip, 2,290 frontend tests across 164 files and all four Docker checks. Lint, formatting, strict TypeScript compilation, backend type checking, OpenAPI and Knip passed.

The noneditable installed wheel `0.6.1.dev14+ga96cff907` passed the final nine-page source API check and browser proof on isolated copies. All three project Open buttons loaded images and OCR records and survived a browser reload. All six tabs matched the current page through seven navigation transitions; Worklist, Hierarchy, History and the book-wide Queue also remained usable. External page reload reset generation 2 to 0 with a viewer acknowledgement and no browser navigation.

All 241 Century word records, their IDs and boxes, GT/OCR text and source preview were preserved. The installed poem preview displayed both eight-character indents, and Century displayed italic `régime` with `voyageur` still unresolved.

### Source-only preview results

The reviewed HTTP proof read all nine prepared pages without loading OCR page records or starting OCR jobs. Consolidated runs concatenate exactly to P3 visible text.

These results cover the selected source previews, not complete formatting or corpus-wide quality.

| Page | Styled runs | Supported layout blocks | Unresolved items |
| --- | ---: | ---: | ---: |
| Poems `008.png` | 0 | 1 | 0 |
| Poems `009.png` | 0 | 0 | 1 |
| Poems `026.png` | 0 | 1 | 0 |
| Statistics `03.png` | 0 | 0 | 1 |
| Statistics `07.png` | 0 | 1 | 1 |
| Statistics `15.png` | 3 | 0 | 1 |
| Century `020.png` | 1 | 0 | 1 |
| Century `081.png` | 0 | 0 | 1 |
| Century `082.png` | 0 | 1 | 0 |

Century `020.png` projects italic `régime` independently of its OCR error. The word `voyageur` remains unresolved because its saved F2-to-P3 evidence does not establish an accepted mapping.

The main preview preserves P3 wording, and layout evidence is collapsed by default. Mapped layout lines expose exact P3 grapheme ranges and F2 indentation columns. The UI suppresses projections with mismatched text or incomplete line boundaries and avoids adding indentation already present in P3.

The real Poems `008.png` browser check measured both mapped lines at an eight-character indent, or 56 pixels in that browser, while preserving P3 text exactly. The extension passed 32 focused frontend tests and 11 backend tests, strict TypeScript compilation, lint, formatting, Knip and both focused code reviews.

The normal-mode service at `http://127.0.0.1:8795` runs the same dev14 wheel from local commit `a96cff907df6ca340565cae537229aff1f9a877a`. The ready page was saved before restart, and all 178 book/data files were preserved. The source corpus was unchanged.

No merge, push or publication was performed. Hard-refresh the browser to load the new frontend. Final receipts are under `/tmp/pdomain-source-tabs-20261108/installed-proof/`.
