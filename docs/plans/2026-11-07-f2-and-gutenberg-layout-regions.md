---
Status: implemented
Owner: CT
Created: 2026-11-07
Last verified: 2026-11-08
Kind: plan
---

# F2 and Gutenberg layout regions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use F2 and aligned Gutenberg formatting to propose page regions and verse structure that people can review, save, and export for training.

**Architecture:** Contracts describe text evidence without pixel boxes. Source-data extracts Gutenberg hints and attaches them to accepted edition alignments. The labeler combines those hints with F2 and OCR geometry through its existing proposal job. Accepted formatting survives export, and training reads it as optional data.

**Tech Stack:** Python, existing F2 tokenizer and Gutenberg HTML parser, immutable shared records, the labeler's region detectors and React review panel, and the existing layout-training export loader.

**Spec:** [What this pass may claim](#what-this-pass-may-claim) records the corrected requirements and implementation choices.

## Goal

A person can load a prepared book, propose regions, review verse and column structure, accept or edit it, reload the book, and export the reviewed result. Both F2 and Gutenberg can inform verse, stanza boundaries, line breaks, indentation, and block quotes. Columns remain distinct from tables.

## Architecture

Four repositories own the work. `pdomain-book-contracts` defines portable evidence and reviewed structure. `pdomain-source-data` extracts and aligns Gutenberg evidence. `pdomain-ocr-labeler-spa` resolves physical geometry. It also owns review, persistence, and export. `pdomain-ocr-training` reads the optional reviewed structure beside its existing region labels.

The coordinator owns this plan and session briefs. Each repository has one implementation session in its own Herdr tab. Sessions may use parallel subagents for independent files. They must assign ownership and integrate their subagents' changes before reporting completion.

## Tech Stack

Use the current Python and TypeScript stacks. Keep contracts free of imaging and ML dependencies. Keep the labeler independent of the source-data package. Run focused tests, each repository's required checks, and browser verification for the changed review flow.

## Global Constraints

These constraints governed the initial local proof. The later owner-authorized
release and merge stage is recorded under [Rollout outcome](#rollout-outcome).

- P3 remains ground-truth page text. F2 and Gutenberg provide reviewable formatting evidence.
- A `<table>` element can encode a data table, columns, verse alignment, or other presentation. The tag alone never assigns the `table` region role.
- Physical columns use separate regions with their content roles, such as `paragraph` or `poetry`, plus column grouping and reading order. Do not add a semantic column role merely to record placement.
- Source indentation and stanza breaks describe the source edition. Keep them distinct from measured scan geometry and expose disagreements.
- Use Gutenberg evidence only from accepted paired edition-alignment operations. A merged operation can name several possible scan pages; require page-specific text matching before proposing a box.
- Every proposed region needs matched OCR words and a valid nonempty pixel box. HTML supplies no scan coordinates.
- Reuse the existing book-scoped proposal handler as the sole run and proposal writer. Preserve locks, cancellation, facet digests, page eligibility, and accept/reject carry-forward.
- Preserve `TypographyPageRecord`, existing edition segment IDs, manifest wire formats, and `regions/labels.json` version 1.
- Record reviewed structure without moving words or renumbering the OCR hierarchy. Existing word identity must survive.
- Build a working local proof first. Use locally built wheels in isolated environments for cross-repo verification. Do not add tracked sibling path dependencies, new hash gates, or a release prerequisite.
- Do not publish, push, tag, train a model, download models, or modify the PGDP corpus in this implementation. A normal package release and index refresh are separate work after the proof is reviewed.
- Preserve unrelated changes and staged files. Work in isolated branches/worktrees, commit only owned files, and verify the effective repository identity before any local commit.

## Review Focus

- Gutenberg verse with nested inline markup and entities retains line order, stanza breaks, and source indentation. Tasks 1 and 2 test it; Task 3 verifies review and export.
- A layout table encoding two prose columns produces separate paragraph regions when scan geometry supports them, never one table merely because HTML uses `<table>`. Tasks 2 and 3 test this.
- Rejected alignment and ambiguous multi-page alignment cannot attach another page's evidence. Tasks 2 and 3 test page-specific selection.
- Combining characters, repeated phrases, reordered words, and missing OCR words cannot silently shift a region onto unrelated text. Tasks 1 and 3 test these cases.
- Acceptance, edits, rejection, reload, and repeated export retain only the current reviewed structure while keeping OCR word identities stable. Tasks 3 and 4 test the complete round trip.

## Agent Index

- **Kind:** plan
- **Status:** implemented
- **Owner:** CT
- **Last verified:** 2026-11-08
- **Read when:** implementing F2 and Gutenberg formatting evidence, physical column proposals, review, or layout-training export.
- **Search terms:** F2, Gutenberg, verse, poetry, stanza, indentation, blockquote, columns, table, layout hints, reviewed structure

## What this pass may claim

The owner corrected the earlier table-only plan. Gutenberg can also inform verse and other formatting. Two printed columns are a physical arrangement, not a table class. Source markup is evidence about structure. The scanned page and OCR positions determine physical regions.

F2 `/* */` supplies a poetry hint. `/# #/` supplies a display/block-quote candidate that still needs review. Gutenberg poem, poetry, verse, stanza, and blockquote markup can supply the corresponding hints. A plain paragraph or an isolated `<br>` does not establish verse. Preserve explicit line boundaries and raw indentation evidence from supported class/style declarations. This pass does not implement a browser's complete CSS layout engine.

A bare table remains a `table_candidate`. Preserve its rows, cells, attributes, and warnings for downstream inspection. A real-table proposal requires supporting source semantics and compatible scan geometry. Repeated paragraph columns or verse laid out in cells must keep those content roles. If evidence remains ambiguous, retain the hint and explain the unresolved choice instead of creating a confident table label.

Physical columns require separate geometric word groups with a real horizontal gap and overlapping vertical extent. Reuse the existing geometric reading-order helper when applicable. A full-width heading does not force the page into one table or one column. The labeler implementer must state and test deterministic gap/grouping thresholds. The first proof supports left-to-right printed pages. Bidirectional reading-order inference is outside this pass.

Agreement between F2 and Gutenberg can strengthen a suggestion. Disagreement remains visible and reviewable. Confidence values `0.9` for F2, `0.7` for Gutenberg, and `0.95` for agreeing source content are ranking values, not measured probabilities. Ambiguous table evidence does not acquire those values as a table decision automatically.

The first proof uses local fixtures and existing prepared-book evidence. It includes the real proposal caller and review/export path. Capturing stanza or column structure makes that data available to training; it does not train a stanza or reading-order model.

## Shared interfaces

Task 1 owns these public names. The other sessions may implement fixtures and private helpers in parallel. They must consume the contracts wheel before their final gate. If an interface needs changing, the contracts owner writes the change to its outbox. The coordinator then updates every consumer before integration.

`pdomain_book_contracts.layout.text_hints` defines immutable records with `to_dict()` and `from_dict()`:

- `LayoutTextLine(text: str, stanza_index: int | None = None, indent_hint: str | None = None)`.
- `LayoutTextHint(kind, source, text, lines, source_ref, grapheme_range=None, source_byte_range=None, attributes=(), table_rows=(), warnings=())`.
- `kind` is one of `poetry`, `blockquote`, `table_candidate`, or `column_flow`. `source` is `f2` or `gutenberg_html`. `text` is nonempty source-visible text, and `lines` is a tuple of `LayoutTextLine`.
- `source_ref` identifies the existing source artifact. Optional ranges are half-open integer pairs. F2 provides a visible grapheme range; Gutenberg provides a byte range in the original HTML artifact for alignment selection.
- `attributes` is a tuple of string key/value pairs preserving class/style or structural evidence. `table_rows` is a tuple of rows, each a tuple of visible cell strings. These carry evidence, not physical boxes or a confirmed role.
- `indent_hint` retains source-relative evidence such as `2em`, leading spaces, or a named class. It is never a scan-pixel offset. Preserve unknown units/classes rather than guessing conversions.

The same module defines a validated `LayoutStructure` representation for reviewed region data. It supports optional column grouping, index, and reading order. It also supports ordered verse lines with stable word IDs, stanza indices, and source indentation, plus optional reviewed table rows/cells. Source indentation stays separate from measured indentation. Validation rejects invalid ranges, negative indices, and non-finite measured values.

For this proof, word-bound reviewed structure uses the `word_id` values already stored on imported bundle `WordTypography` records. Preserve those IDs across text and geometry corrections. The labeler's legacy `stable_word_id` helper derives an ID from original text and reading order; it is not a persisted identity map and must not be used to promise stability after arbitrary legacy edits. Loose mirrors retain F2/geometry proposals, but saving word-bound stanza/line structure there is unsupported until they are prepared as a bundle. Explain that limitation in the review UI and reject unsupported writes clearly. Do not create a new identity migration system in this proof.

Optional `word_signatures` are geometry snapshots for consumers, never join keys. Resolve and refresh those snapshots by stored `word_ids` when exporting after a geometry edit. Keep shared layout records independent of typography imports to avoid a dependency cycle.

The contracts owner records its exact typed constructor and wire examples in `/tmp/pdomain-layout-20261108/contracts-outbox.txt` before consumers integrate. Field names in the reviewed wire record are `lines`, `word_ids`, `word_signatures`, `stanza_index`, `indent_hint`, `column_group_id`, `column_index`, and `reading_order`; optional table structure is `table_rows`. A nonempty reviewed line carries its ordered `word_ids`. Optional fields are omitted when unknown.

`edition/layout-hints.json` is an optional prepared-book artifact:

```json
{
  "schema": "pdomain.edition-layout-hints",
  "version": 1,
  "groups": [
    {"page_ids": ["scan-page-id"], "edition_unit_ids": ["edition-unit-id"], "hints": []}
  ]
}
```

Each group comes from one accepted paired alignment operation. Its hints use the shared record conversion. A group may list multiple candidate pages. The labeler must still match hint text against the current page. The artifact stays reachable through existing supporting-evidence graph references. Missing evidence is a supported F2-only or geometry-only case.

`regions/structure.json` accompanies the unchanged region-label export:

```json
{
  "schema": "pdomain.layout-structure",
  "version": 1,
  "regions": [
    {"prefix": "book/page", "page_index": 0, "region_id": "region-id", "structure": {}}
  ]
}
```

The join key is `(prefix, page_index, region_id)`. Export only confirmed, currently reviewed structure. Re-export replaces a page's entries and removes deleted structures. No rejected or unreviewed proposal structure enters this file.

## Repository work and dependencies

| Repository | Owned result | Depends on |
| --- | --- | --- |
| `pdomain-book-contracts` | Shared hint/structure records and F2 producers | Existing tokenizer |
| `pdomain-source-data` | Gutenberg hints and accepted alignment sidecar | Contracts interface |
| `pdomain-ocr-labeler-spa` | Evidence loading, geometric proposals, review, persistence, export | Contracts; source-data sidecar fixture |
| `pdomain-ocr-training` | Optional reviewed-structure reader and compatibility tests | Contracts; labeler export fixture |
| `pdomain-ops` | This plan, work assignment, integration evidence | All four owners |

No implementation is needed in the OCR CLI, simple GUI, trainer SPA, synth, or index repositories for this proof. They can consume later package releases through the normal update path.

### Task 1: Shared records and F2 evidence

**Owner:** contracts session.

**Files:**

- Create `pdomain-book-contracts/pdomain_book_contracts/layout/text_hints.py`.
- Create `pdomain-book-contracts/pdomain_book_contracts/sources/pgdp/f2/structure.py`.
- Modify the existing F2 `tokens.py` and `parser.py` only where structural markup needs normal child scanning.
- Add `tests/layout/test_text_hints.py` and `tests/pgdp/f2/test_structure.py`.

**Interfaces:**

- Consume `F2PageTokens` and its existing grapheme/source evidence.
- Produce `layout_hints_from_tokens(parsed: F2PageTokens, *, source_ref: str) -> tuple[LayoutTextHint, ...]` and the shared records above.
- Keep new layout records independent of typography base classes to avoid an import cycle.

- [x] **Step 1: Write failing tests.** Assert record/wire round trips, source-relative indentation, and reviewed structure validation. Assert F2 poetry lines/stanzas, display-block candidates, combining-character ranges, nested inline styles in table cells, one outer nested-table candidate, crossed/bare/unclosed markers, and ordinary text after an unclosed table. Assert existing page-record bytes/schema stay unchanged.
- [x] **Step 2: Confirm failures.** Run `uv run pytest tests/layout/test_text_hints.py tests/pgdp/f2/test_structure.py -v` from the contracts repository. Failure must identify the missing API or behavior.
- [x] **Step 3: Implement the records and producer.** Handle `<table>`, `<tr>`, `<td>`, and `<th>` without swallowing nested tokens. Preserve cell boundaries and attributes. Guard parser lookups for unfamiliar block tokens. Slice using grapheme boundaries, never Python string indices applied to grapheme offsets.
- [x] **Step 4: Verify and hand off.** Run focused tests and `make ci`. Build a local wheel into the coordination artifacts folder. Write exact field types, JSON examples, wheel path, commit and check results to the contracts outbox. No release or push.
- [x] **Step 5: Commit owned files locally.** Record the isolated branch/worktree and author/committer evidence. Leave other sessions' files untouched.

### Task 2: Gutenberg formatting and alignment transport

**Owner:** source-data session. Extraction fixtures can run in parallel with Task 1.

**Files:**

- Create `pdomain-source-data/pdomain_source_data/edition_text/layout_hints.py`.
- Modify `pdomain-source-data/pdomain_source_data/tasks/typography/prepare_edition_labeler_book.py`.
- Reuse `PreparedBookArtifact` and `PreparedLabelerBook.extra_artifacts` from `labeler_book_publication.py`.
- Add `tests/edition_text/test_layout_hints.py` and extend edition-labeler preparation tests.

**Interfaces:**

- Produce `extract_gutenberg_layout_hints(data: bytes, *, source_ref: str) -> tuple[LayoutTextHint, ...]`.
- Publish the optional edition sidecar through existing artifact and graph-reference paths. Do not change `EditionDocument` kinds, IDs, or baseline serialized bytes.

- [x] **Step 1: Write failing tests.** Explicit poetry/stanza wrappers preserve nested inline text, entities, line boundaries, and indentation evidence. Blockquotes produce hints. Plain `<br>` prose and generic containers do not become poetry. Preserve raw rows/cells in a table candidate, including a layout table containing verse or columns. Scripts, styles and Gutenberg boilerplate supply no text hints; supported stylesheet declarations may supply indentation evidence.
- [x] **Step 2: Confirm failures.** Run `uv run pytest tests/edition_text/test_layout_hints.py -v` plus the existing preparation test module from this repository.
- [x] **Step 3: Implement extraction and attachment.** Use raw HTML because the current edition model discards line boundaries. Map source byte ranges onto existing projection-unit ranges. Attach only after existing alignment acceptance/quality checks. Preserve all candidate page IDs for merged operations; rejected, unpaired or unrelated operations attach nothing. A malformed wrapper must not capture subsequent unrelated paragraphs.
- [x] **Step 4: Verify and hand off.** Test unchanged edition-document serialization and graph discovery of the optional sidecar. Run the repository gate with the local contracts wheel in an isolated environment. Produce a fixture prepared book containing verse, an ambiguous table, and accepted alignment evidence for labeler integration.
- [x] **Step 5: Commit owned files locally.** Report exact commands, results, branch, fixture and wheel paths. No corpus import, download, push, or publication.

### Task 3: Usable labeler proposals and reviewed formatting

**Owner:** labeler session. It may delegate detector/matching, persistence/export, and frontend/browser work to parallel subagents with separate files.

**Files:**

- Add `src/pdomain_ocr_labeler_spa/core/regions/text_layout.py`.
- Extend `core/regions/detector.py`, `bootstrap.py`, and `core/jobs/handlers/propose_regions.py`.
- Extend prepared evidence loading in `core/persistence/book_labeling_session.py` and `core/project_state.py` as needed.
- Extend `api/regions.py`, `core/regions/block_adapter.py`, and `core/jobs/handlers/export.py`.
- Update API payload models and `frontend/src/components/right-panel/RegionDetail.tsx`; add a focused structure editor if needed.
- Extend region proposal, persistence, export, word-identity and browser tests.

**Interfaces:**

- Consume the contracts producer and optional edition sidecar. Resolve F2 from prepared artifact payloads or `rounds/F2.json` for a loose mirror.
- Add a text-evidence detector returning the existing `DetectedRegion` type. Compose it through the existing `POST /api/projects/{id}/regions/propose` job, rather than adding another journal writer.
- Store reviewed `layout_structure` in `Block.additional_block_attributes`. Return it through confirmed-region APIs and the optional structure export.

- [x] **Step 1: Write failing tests.** Exercise F2-only, Gutenberg-only, agreeing and disagreeing verse evidence; source line/stanza/indent metadata; missing evidence; malformed optional sidecars; rejected and merged alignments; pixel and normalized OCR boxes; combining characters; repeated phrases; reordered and missing words. Ambiguous matches abstain instead of attaching to an unrelated occurrence.
- [x] **Step 2: Confirm failures.** Run new matching tests and the existing proposal-run integration modules. Failures must exercise the production detector/job seam.
- [x] **Step 3: Implement evidence resolution and geometry.** Match normalized source text to page words while retaining original source text. Use line geometry to split real columns, preserving semantic roles and reading order. Group across a full-width heading without merging both columns. Require stronger evidence for a table than the existence of an HTML element. Keep unresolved hints available for review with an explanation. Include every consumed facet in detector staleness dependencies.
- [x] **Step 4: Implement review and persistence.** Show source disagreements, verse lines, stanza groups, indentation, column grouping/order, and unresolved hints in readable fields. Let a person correct these fields before acceptance or edit a confirmed region. Copy only reviewed structure to the saved block. Use stored bundle IDs for word-bound structure. Test that a loose-mirror word-bound structure write is rejected with guidance to prepare the book, while its normal region acceptance still works. Do not move OCR words. Preserve all existing accept, reject, refine, undo and carry-forward behavior.
- [x] **Step 5: Export and verify.** Export the unchanged labels file plus current reviewed structure. Test accept/edit/reject/reload/delete/re-export, including removed sidecar entries and unchanged word identities. Correct a bound word's text and bounding box, reload, and export again: structure must keep the same `word_ids`, while geometry snapshots reflect the correction. Run `make openapi-export AI=1` when API payloads change, update frontend types, and run `make ci AI=1`.
- [x] **Step 6: Verify in the browser and commit.** Use an isolated fixture book: load it, confirm page kind, click Propose regions, inspect Gutenberg verse evidence, correct stanza/indent or reading order, accept, reload, and export. Repeat for two-column prose and verify two paragraph regions, plus a genuine table and an unresolved layout-table case. Inspect neighboring region/edit flows. Save reproducible browser evidence, export fixture, commands and local commit in the outbox.

### Task 4: Read reviewed structure for training

**Owner:** training session. Legacy compatibility tests can start in parallel.

**Files:**

- Modify `pdomain-ocr-training/pdomain_ocr_training/layout_regions.py`.
- Extend `pdomain-ocr-training/tests/test_layout_regions.py` and the existing fake-model training tests.

**Interfaces:**

- Preserve `load_layout_export(export_dir: Path) -> list[LayoutPageExample]`.
- Add `structure: NotRequired[LayoutStructure]` to `LayoutRegionExample`.
- Add `load_layout_structures(export_dir: Path, *, pages: Sequence[LayoutPageExample]) -> dict[tuple[str, int, str], LayoutStructure]`.

- [x] **Step 1: Write failing tests.** A missing sidecar returns exactly the old dictionaries. Valid verse and column data attach only to the matching page/region. Partial coverage is allowed. Unknown joins, duplicate keys, invalid versions and malformed structures fail clearly. A labeler fixture exported before and after a geometry correction retains the same structure `word_ids`. Class IDs and existing box training stay unchanged.
- [x] **Step 2: Confirm failures.** Run `uv run pytest tests/test_layout_regions.py -v` and the existing fake-model forwarding test from this repository.
- [x] **Step 3: Implement the optional join.** Return an empty mapping when the sidecar is absent. Omit the `structure` key for legacy regions. Use the shared validator for present records. Do not demand membership signatures from an existing empty region-membership list merely to load valid structure.
- [x] **Step 4: Verify.** Confirm the fake model receives structure unchanged. Load the labeler's Task 3 export fixture and verify verse/stanza/column data after acceptance. Run `make ci` with the local contracts wheel where needed. Do not run real training or claim improved model quality.
- [x] **Step 5: Commit owned files locally.** Report checks, compatibility outcome, local commit and integration fixture path.

### Task 5: Coordinator integration

- [x] Verify each session has one owner, a dedicated project tab, a fresh brief, and an outbox/status file. Do not prompt the user's coordinator pane.
- [x] Review the updated plan before dispatching product edits. The owner's request already authorizes coordinated execution; preserve that execution method.
- [x] Let repository owners develop independent fixtures/helpers concurrently. Release cross-repo integration after the contracts wheel and exact interface examples are available.
- [x] Inspect local commits/diffs and required review evidence. Run the prepared-book-to-labeler-export-to-training-reader fixture across the actual local wheels. Check legacy F2-only and legacy export cases too.
- [x] Record what is implemented, what the browser verified, and any blocked checks. Run docgraph reindex and strict checks for changed documentation. Do not present launched sessions as completed implementation.

## What this plan leaves out

This pass does not publish packages, refresh public indexes, change OCR engines, run model training, infer bidirectional reading order, or reconstruct the entire CSS layout of a Gutenberg edition. It does not add a legacy word-identity migration system: detailed word-bound formatting review requires a prepared bundle with stored word IDs. It preserves the existing region-label schema while making reviewed formatting available beside it. Release work and training experiments follow the working proof.

## Implementation proof

All four implementation tasks completed on 2026-11-08. The coordinator's fresh
check passed 92 focused tests: 21 contracts, 12 source-data, 27 labeler, and 32
training tests. The final cross-repository review found no actionable issues.

Eight interactive Chromium checks exercised review and export. The final
installed-wheel check loaded verse structure, both accepted paragraph columns
with a shared group and reading order `0, 1`, and reviewed 2×2 table cells.
Word IDs stayed stable after text and geometry corrections, while geometry
snapshots changed to match the corrected boxes. The training reader forwarded
the loaded records unchanged to a fake model without importing Torch.

These are synthetic fixture and browser checks. They do not establish accepted
production-corpus quality or improved trained-model quality. Detailed word-bound
formatting review still requires prepared bundles with stored word IDs. The
initial labeler gate used the local contracts wheel, preserved its prepared
environment, and excluded registry Docker builds. The rollout stage must verify
the published dependency through normal setup and required checks.

The implementation commits were:

| Repository | Reviewed implementation commit |
| --- | --- |
| `pdomain-book-contracts` | `94e4eef84a91c264c42b36097e49541eee4683ac` |
| `pdomain-source-data` | `d101379f51f92b3322edd0f5e82844e9d43a1dd4` |
| `pdomain-ocr-labeler-spa` | `92e6ef48a478b05a961cd171cba05161db3aaedc` |
| `pdomain-ocr-training` | `5c5b83587534e332600a33421a2679d0007a9c5e` |

## Rollout outcome

After reviewing the proof, the owner authorized the contracts release, consumer
dependency updates, local merges, and pushes on 2026-11-08. Contracts
[`v0.2.1`](https://github.com/pdomain/pdomain-book-contracts/releases/tag/v0.2.1)
was published from commit `94e4eef84a91c264c42b36097e49541eee4683ac`. The
[pip index](https://pdomain.github.io/pdomain-index-pip/simple/) was published at
commit `e30d081e654a34f7e8ec00b98bc731bb9c1bda0f`.
A clean environment installed contracts `0.2.1` from the public index and imported
the new layout APIs.

All four product changes are merged and pushed. The coordinator independently
verified these remote `master` commits:

| Repository | Verified remote `master` commit |
| --- | --- |
| `pdomain-book-contracts` | `94e4eef84a91c264c42b36097e49541eee4683ac` |
| `pdomain-source-data` | `4e30fd67cf5c0126422b8e22cf05991f65602d71` |
| `pdomain-ocr-labeler-spa` | `2d35bef7828f2a1464cc3bd0ac8f9f9952299ec0` |
| `pdomain-ocr-training` | `bc7ed72d55a76376b8f087c0f3fa62e1d98181bd` |

All three consumers now require `pdomain-book-contracts>=0.2.1`. Their normal
lockfiles resolve the published wheel, and their canonical environments import
stable `0.2.1` without a local-wheel or sibling-path override.

Normal checks against the published dependency passed:

- Contracts release preflight: 55 tests, build, typing, lint, and strict docgraph.
- Source-data: normal worktree and merged-master checks; 476 tests passed and
  three opt-in mounted-corpus tests skipped.
- Labeler: 2,181 backend tests, including all four Docker tests, and 2,240 frontend
  tests. Eight Chromium cases passed against the published dependency. Docker
  also imported the new layout and F2 APIs from contracts `0.2.1`.
- Training: normal worktree and merged-master checks; 156 tests passed. The final
  verse, columns, table, stable-ID, and refreshed-geometry proof passed with the
  published dependency.

The labeler merge was an exact fast-forward to the gated tree. Normal setup and
11 integration tests passed in the canonical checkout. All four canonical product
checkouts were clean after remote verification. Feature branches and worktrees
were retained. No consumer package was tagged or released, and no real model
training or corpus modification ran. Real-corpus acceptance and model quality
remain separate work.
