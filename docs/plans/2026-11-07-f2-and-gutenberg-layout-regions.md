---
Status: draft
Owner: CT
Created: 2026-11-07
Last verified: 2026-11-07
Kind: plan
---

# F2 and Gutenberg layout regions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn one page's F2 text, and a Gutenberg table when the edition alignment accepts that page, into region proposals a person can accept and export for layout training.

**Architecture:** `pdomain-book-contracts` reads F2 into poetry, blockquote, and table spans with grapheme ranges. `pdomain-source-data` reads Gutenberg HTML only for `<table>` text. The labeler matches those words to OCR word boxes and appends a `RegionProposal`. The box is the union of the matched word boxes. Training keeps reading `regions/labels.json` after a person accepts the proposal. This plan does not train a model or invent a column box.

**Tech Stack:** Python, Pydantic models in `pdomain-book-contracts`, the existing Gutenberg HTML parser in `pdomain-source-data`, and `RegionProposalLog` in `pdomain-ocr-labeler-spa`.

**Spec:** [What this pass may claim](#what-this-pass-may-claim) in this file.

## Goal

Turn one page's F2 text, and a Gutenberg table when the edition alignment accepts that page, into region proposals a person can accept and export for layout training.

## Architecture

`pdomain-book-contracts` reads F2 into poetry, blockquote, and table spans with grapheme ranges. `pdomain-source-data` reads Gutenberg HTML only for `<table>` text. The labeler matches those words to OCR word boxes and appends a `RegionProposal`. The box is the union of the matched word boxes. Training keeps reading `regions/labels.json` after a person accepts the proposal. This plan does not train a model or invent a column box.

## Tech Stack

Python, Pydantic models in `pdomain-book-contracts`, the existing Gutenberg HTML parser in `pdomain-source-data`, and `RegionProposalLog` in `pdomain-ocr-labeler-spa`.

## Global Constraints

- Do not add a column role and do not draw a column box. A Gutenberg table that imitates two columns becomes one `table` proposal, which a person can reject.
- Do not write a `RegionProposal` unless at least one OCR word matches and the union box has left ≤ right and top ≤ bottom.
- An unmatched or crossed `/* */` or `/# #/` pair produces no span.
- An unclosed `<table>` produces no span and does not consume the rest of the page.
- Gutenberg table text is attached only when an accepted edition alignment names that page. With no alignment, only F2 is used.
- Proposals are appended to `.pd-pages/region-proposals.jsonl`. They are not written into the page content blob.
- `depends_on` is exactly `{word_text, word_boxes}`.
- `model_id` is `f2-gutenberg-layout` and `model_version` is `1`.
- Confidence is `0.9` for F2 alone, `0.7` for Gutenberg alone, and `0.95` when both sources have the same role and the same word sequence.
- Word splitting uses `[^\W_]+(?:['\u2019][^\W_]+)*`. Matching to OCR words is casefold and must be one contiguous run. The first run wins.
- Do not modify the PGDP corpus. Do not download Gutenberg. Do not bump `pdomain.layout-regions` version 1. Do not add `structural_spans` to `TypographyPageRecord`. That record's vendored schema is hashed by `test_vendored_page_record_schema_is_exact_and_offline_resolvable`.
- After Tasks 1 and 3, publish `pdomain-book-contracts` with `BUMP=patch ./scripts/do-release.sh`, publish the pip index, and pin the labeler to that release. Do not use a path dependency. Do not publish the labeler. Do not set `FORCE=1`. Do not set `SKIP_PUSH=1`.
- Commit as `ConcaveTrillion <concavetrillion@gmail.com>`. Do not pass `--author`. Do not change global git config.

## Review Focus

- An F2 `<table summary="x">` with no closer must emit no span, and the following paragraph's token kind must be `text`. Task 1 tests this.
- A page that ends with a bare `*/` must not gain a poetry span. Task 1 tests this.
- Gutenberg HTML that reflows two printed columns into one paragraph must not produce two regions. Task 2 tests that a paragraph without `<table>` produces no table text.
- A rejected edition alignment must not attach a Gutenberg table. Task 3 tests `gutenberg_attached=False`.
- OCR words that skip a middle word, reorder the span, or differ only by case must follow the contiguous casefold rule, and the first matching run wins. Task 5 tests those cases.

## Agent Index

- **Kind:** plan
- **Status:** draft
- **Owner:** CT
- **Last verified:** 2026-11-07
- **Read when:** starting layout regions from PGDP F2 and a Project Gutenberg text, before training a layout model.
- **Search terms:** F2, Gutenberg HTML, layout regions, poetry block, table, region proposal, labels.json

## What this pass may claim

P3 in `pages.json` stays the ground-truth page text. It does not supply a region role.

`rounds/F2.json` maps an image filename, such as `001.png`, to formatting text. The tokenizer already finds `/* */` as poetry and `/# #/` as a block quote. It also finds the inline tags `<i>`, `<b>`, `<sc>`, `<g>`, `<f>`, and `<u>`. The page record stores only the names `poetry_block` and `display_block`, once per page, and drops the range. `<table` is an unknown tag today, and its body remains visible text.

Gutenberg HTML can contain a real `<table>`. The edition model already allows a segment kind of `table`, and the extractor does not emit one. The HTML usually reflows two printed columns into one reading order. This pass does not reconstruct those columns.

Neither file contains a pixel box. The box comes from OCR words already on the page. `RegionProposal.box` is required, so a span with no matched word is skipped.

A person accepts or rejects the proposal in the existing region panel. Export writes `regions/labels.json` with schema `pdomain.layout-regions` version 1. `load_layout_export` already reads that file. This plan uses the existing `poetry`, `blockquote`, and `table` values of `RegionRole`.

The labeler depends on `pdomain-book-contracts`, not `pdomain-source-data`. It receives HTML table text as strings. F2 still works when that list is empty. The new contracts symbols reach the labeler only through a contracts release.

## File map

- `pdomain-book-contracts/pdomain_book_contracts/sources/pgdp/f2/tokens.py` tokenizes a table as normal text inside block markers.
- `pdomain-book-contracts/pdomain_book_contracts/sources/pgdp/f2/structure.py` returns structural spans. It does not store them on the page record.
- `pdomain-source-data/pdomain_source_data/edition_text/gutenberg.py` returns table text without changing edition segment kinds or ids.
- `pdomain-ocr-labeler-spa/src/pdomain_ocr_labeler_spa/core/regions/text_layout.py` matches words to OCR boxes and builds proposals.

### Task 1: F2 spans with ranges

**Files:**

- Create: `pdomain-book-contracts/pdomain_book_contracts/sources/pgdp/f2/structure.py`
- Modify: `pdomain-book-contracts/pdomain_book_contracts/sources/pgdp/f2/tokens.py`
- Modify: `pdomain-book-contracts/pdomain_book_contracts/sources/pgdp/f2/parser.py`
- Test: `pdomain-book-contracts/tests/pgdp/f2/test_structure.py`

**Interfaces:**

- Consumes: `F2PageTokens` from `pdomain_book_contracts.sources.pgdp.f2.tokens`.
- Produces: `StructuralSpan` and `structural_spans_from_tokens(parsed: F2PageTokens) -> tuple[StructuralSpan, ...]`. The page record is unchanged.

`StructuralSpan` has `role` of `poetry`, `blockquote`, or `table`. It has a half-open grapheme `start` and `end`, `source` fixed to `f2`, `source_slices`, and `warnings` as a tuple of strings. `start < end` is required. A normal span has `warnings == ()`.

`/* */` maps to `poetry`, and `/# #/` maps to `blockquote`. An opening `<table…>` through `</table>` maps to `table`. The open token keeps its attributes and has empty `visible_text`. Text inside the table stays normal tokens, so an inner `<i>` still parses. A nested table emits one outer span with `warnings` set to `("nested_table",)`. It emits no second span.

- [ ] **Step 1: Write the failing tests**

```python
def test_poetry_span_covers_the_line_inside_the_markers() -> None:
    parsed = _tokens("/*\nLine one\n*/")
    spans = structural_spans_from_tokens(parsed)
    assert len(spans) == 1
    assert spans[0].role == "poetry"
    assert parsed.visible_text[spans[0].start : spans[0].end].strip() == "Line one"


def test_bare_closer_emits_no_span() -> None:
    assert structural_spans_from_tokens(_tokens("*/")) == ()


def test_crossed_blocks_emit_no_span() -> None:
    assert structural_spans_from_tokens(_tokens("/* /# text */ #/")) == ()


def test_unclosed_table_leaves_the_following_words() -> None:
    parsed = _tokens('<table summary="x">\nCell\nNo closer\nNext paragraph')
    assert structural_spans_from_tokens(parsed) == ()
    tail = parsed.tokens[-1]
    assert tail.kind is F2TokenKind.TEXT
    assert "Next paragraph" in tail.text


def test_table_body_keeps_an_inner_italic_tag() -> None:
    parsed = _tokens("<table><td><i>Alpha</i></td></table>")
    assert any(
        token.kind is F2TokenKind.OPEN_TAG and token.text == "<i>" for token in parsed.tokens
    )
    assert any(token.kind is F2TokenKind.TEXT and token.text == "Alpha" for token in parsed.tokens)


def test_nested_table_emits_one_outer_span() -> None:
    parsed = _tokens("<table><td>Outer</td><table><td>Inner</td></table></table>")
    spans = structural_spans_from_tokens(parsed)
    assert len(spans) == 1
    assert spans[0].role == "table"
    assert spans[0].warnings == ("nested_table",)
```

`_tokens` must call the real F2 tokenizer. The poetry assertion compares the visible slice because the markers include the newlines around the line.

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd /mnt/work/projects/pdomain/pdomain-book-contracts && uv run pytest tests/pgdp/f2/test_structure.py -v`

Expected: FAIL because `structural_spans_from_tokens` is missing.

- [ ] **Step 3: Implement the spans**

In `tokens.py`, an opening tag named `table` becomes `BLOCK_OPEN`, and `</table>` becomes `BLOCK_CLOSE`. Both have empty `visible_text`. The open token keeps its attributes. Continue the scan after each tag. A missing `</table>` must not consume the rest of the page as `UNKNOWN`. The following paragraph stays `TEXT`.

In `parser.py`, do not look up a block token in `_BLOCK_CONTEXT` when its text is not `/*`, `*/`, `/#`, or `#/`. That token must not change `structural_context`. Do not call the span function from the page-record builder. Do not modify `records.py`.

- [ ] **Step 4: Re-run the tests**

Run the same pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/work/projects/pdomain/pdomain-book-contracts
git add pdomain_book_contracts/sources/pgdp/f2/structure.py pdomain_book_contracts/sources/pgdp/f2/tokens.py pdomain_book_contracts/sources/pgdp/f2/parser.py tests/pgdp/f2/test_structure.py
git commit -m "feat: read F2 poetry, blockquote, and table spans"
```

### Task 2: Gutenberg table text

**Files:**

- Modify: `pdomain-source-data/pdomain_source_data/edition_text/gutenberg.py`
- Test: `pdomain-source-data/tests/edition_text/test_gutenberg.py`

**Interfaces:**

- Consumes: HTML bytes already accepted by `_extract_html`.
- Produces: `gutenberg_table_texts(data: bytes) -> tuple[str, ...]`. Each string is the visible text of one `<table>`, in source order, with tags removed. A paragraph that is not a table is absent.

- [ ] **Step 1: Write the failing tests**

```python
def test_html_table_text_keeps_cell_order() -> None:
    html = b"<html><body><p>Before</p><table><tr><td>Alpha</td><td>Beta</td></tr></table><p>After</p></body></html>"
    assert gutenberg_table_texts(html) == ("Alpha Beta",)


def test_reflowed_paragraph_is_not_a_table() -> None:
    html = b"<html><body><p>Left column text</p><p>Right column text</p></body></html>"
    assert gutenberg_table_texts(html) == ()


def test_unclosed_html_table_returns_nothing() -> None:
    html = b"<html><body><table><tr><td>Alpha</td></tr><p>After</p></body></html>"
    assert gutenberg_table_texts(html) == ()
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd /mnt/work/projects/pdomain/pdomain-source-data && uv run pytest tests/edition_text/test_gutenberg.py::test_html_table_text_keeps_cell_order tests/edition_text/test_gutenberg.py::test_reflowed_paragraph_is_not_a_table tests/edition_text/test_gutenberg.py::test_unclosed_html_table_returns_nothing -v`

Expected: FAIL because `gutenberg_table_texts` is missing.

- [ ] **Step 3: Return table text without changing segments**

Build `gutenberg_table_texts` from decoded cell text inside each complete `<table>`. Remove tags inside each cell and join the cells with one space. A missing `</table>` returns nothing for that table and must not run to the end of the file. Leave `EditionSegment.kind` and `segment_id` unchanged. Do not add a column kind.

If `git status` in this repo shows other uncommitted work, stop and report that. Do not stash it.

- [ ] **Step 4: Re-run the tests**

Run the same pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/work/projects/pdomain/pdomain-source-data
git add pdomain_source_data/edition_text/gutenberg.py tests/edition_text/test_gutenberg.py
git commit -m "feat: extract Gutenberg table text in cell order"
```

### Task 3: Merge the two sources for one page

**Files:**

- Modify: `pdomain-book-contracts/pdomain_book_contracts/sources/pgdp/f2/structure.py`
- Test: `pdomain-book-contracts/tests/pgdp/f2/test_structure.py`

**Interfaces:**

- Consumes: `StructuralSpan` from Task 1 and table strings from Task 2.
- Produces: `PageLayoutSpan` and `merge_page_layout_spans(*, f2_spans: tuple[StructuralSpan, ...], f2_visible_text: str, gutenberg_table_texts: tuple[str, ...] = (), gutenberg_attached: bool) -> tuple[PageLayoutSpan, ...]`.

`PageLayoutSpan` has `role`, `sources` as a tuple of `f2` and `gutenberg_html`, `words` as a tuple of strings, and `confidence` as a float.

Add `visible_span_text(visible_text: str, start: int, end: int) -> str`. Segment the complete string with `regex.findall(r"\X", visible_text)`. Validate `0 <= start < end <= len(graphemes)`, then join `graphemes[start:end]`. Invalid bounds raise `ValueError`. Use this helper for every structural-span slice, including poetry, blockquote, and table cell extraction. Grapheme indices must never index the Python string directly.

When `gutenberg_attached` is false, ignore `gutenberg_table_texts`. When a Gutenberg table's words casefold-equal an F2 table's words, emit one span with both sources, confidence `0.95`, and the F2 word casing. Otherwise, emit each source on its own. Poetry and blockquote come only from F2. F2 alone has confidence `0.9`. Gutenberg alone has confidence `0.7`.

For an F2 table, take each complete `<td>` or `<th>` body from `visible_span_text(f2_visible_text, span.start, span.end)`. Join those bodies with one space before applying the word pattern. The agreeing test must pass `parsed.visible_text` because the tokenizer does not insert the space Gutenberg uses. Poetry and blockquote apply the word pattern to the helper's visible slice. A Gutenberg table string is already cell-joined, so apply the word pattern to it.

- [ ] **Step 1: Write the failing tests**

```python
def test_rejected_alignment_drops_the_gutenberg_table() -> None:
    spans = merge_page_layout_spans(
        f2_spans=(),
        f2_visible_text="",
        gutenberg_table_texts=("Alpha Beta",),
        gutenberg_attached=False,
    )
    assert spans == ()


def test_span_slice_uses_graphemes_after_a_combining_character() -> None:
    assert visible_span_text("e\u0301Alpha", 1, 6) == "Alpha"
    parsed = _tokens("e\u0301/*Alpha*/")
    spans = merge_page_layout_spans(
        f2_spans=structural_spans_from_tokens(parsed),
        f2_visible_text=parsed.visible_text,
        gutenberg_attached=False,
    )
    assert spans[0].words == ("Alpha",)
    with pytest.raises(ValueError):
        visible_span_text("Alpha", 0, 6)


def test_agreeing_tables_become_one_span() -> None:
    parsed = _tokens("<table><tr><td>Alpha</td><td>Beta</td></tr></table>")
    spans = merge_page_layout_spans(
        f2_spans=structural_spans_from_tokens(parsed),
        f2_visible_text=parsed.visible_text,
        gutenberg_table_texts=("Alpha Beta",),
        gutenberg_attached=True,
    )
    assert len(spans) == 1
    assert spans[0].sources == ("f2", "gutenberg_html")
    assert spans[0].confidence == 0.95
    assert spans[0].words == ("Alpha", "Beta")


def test_gutenberg_only_table_uses_confidence_0_7() -> None:
    spans = merge_page_layout_spans(
        f2_spans=(),
        f2_visible_text="",
        gutenberg_table_texts=("Alpha Beta",),
        gutenberg_attached=True,
    )
    assert len(spans) == 1
    assert spans[0].role == "table"
    assert spans[0].sources == ("gutenberg_html",)
    assert spans[0].confidence == 0.7
    assert spans[0].words == ("Alpha", "Beta")


def test_different_word_sequences_stay_two_spans() -> None:
    parsed = _tokens("<table><tr><td>Alpha</td><td>Beta</td></tr></table>")
    spans = merge_page_layout_spans(
        f2_spans=structural_spans_from_tokens(parsed),
        f2_visible_text=parsed.visible_text,
        gutenberg_table_texts=("Gamma Delta",),
        gutenberg_attached=True,
    )
    assert len(spans) == 2
    assert {span.words for span in spans} == {("Alpha", "Beta"), ("Gamma", "Delta")}
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd /mnt/work/projects/pdomain/pdomain-book-contracts && uv run pytest tests/pgdp/f2/test_structure.py::test_rejected_alignment_drops_the_gutenberg_table tests/pgdp/f2/test_structure.py::test_agreeing_tables_become_one_span tests/pgdp/f2/test_structure.py::test_gutenberg_only_table_uses_confidence_0_7 tests/pgdp/f2/test_structure.py::test_different_word_sequences_stay_two_spans -v`

Also run `uv run pytest tests/pgdp/f2/test_structure.py::test_span_slice_uses_graphemes_after_a_combining_character -v` from the same repository.

Expected: FAIL because `merge_page_layout_spans` is missing.

- [ ] **Step 3: Implement the merge**

Use the word pattern in the global constraints. Join F2 cells with one space before that pattern. Do not import `pdomain-source-data`.

- [ ] **Step 4: Re-run the tests**

Run the same pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/work/projects/pdomain/pdomain-book-contracts
git add pdomain_book_contracts/sources/pgdp/f2/structure.py tests/pgdp/f2/test_structure.py
git commit -m "feat: merge F2 layout spans with Gutenberg table text"
```

### Task 4: Publish the contracts and pin the labeler

**Files:**

- Modify: `pdomain-ocr-labeler-spa/pyproject.toml`
- Modify: `pdomain-ocr-labeler-spa/uv.lock`

**Interfaces:**

- Consumes: the symbols from Tasks 1 and 3, committed on `master` in `pdomain-book-contracts`.
- Produces: a GitHub release of `pdomain-book-contracts` whose wheel contains those symbols, an updated pip index, and a labeler lock that installs that wheel.

The labeler currently requires `pdomain-book-contracts>=0.2.0` from the index `pdomain-index-pip`. `uv.lock` downloads that wheel from the GitHub release. There is no path dependency.

- [ ] **Step 1: Confirm the release command**

The command is `scripts/do-release.sh` in `pdomain-book-contracts`. The Makefile has no `release-*` target. That script is the publisher. If the script is missing, stop and report that. Do not invent another publisher.

- [ ] **Step 2: Release the contracts**

Tasks 1 and 3 must already be committed. The working tree must be clean and the branch must be `master`. If either is false, stop.

```bash
cd /mnt/work/projects/pdomain/pdomain-book-contracts
flock /tmp/pdomain-release.lock env BUMP=patch ./scripts/do-release.sh
```

Do not set `FORCE=1`. Do not set `SKIP_PUSH=1`. Preflight is `make ci`. The script pushes `master` and the tag, then creates the GitHub release with the wheel and sdist. Read the printed tag. If preflight fails, stop. No tag should exist in that case.

- [ ] **Step 3: Publish the index**

The labeler resolves the package from `https://pdomain.github.io/pdomain-index-pip/simple/`. A GitHub release alone does not update that index.

```bash
cd /mnt/work/projects/pdomain/pdomain-index-pip
flock /tmp/pdomain-index-publish.lock ./scripts/publish-index.sh
```

Do not set `DRY_RUN=1` for the real publish. Do not publish the labeler.

- [ ] **Step 4: Pin the labeler and commit**

If the labeler working tree is dirty, stop and report that. Do not stash it.

In `pyproject.toml`, raise `pdomain-book-contracts>=0.2.0` to `>=` the released version, without the leading `v`. Keep `index = "pdomain-index-pip"`. Do not add `tool.uv.sources`.

```bash
cd /mnt/work/projects/pdomain/pdomain-ocr-labeler-spa
uv lock
git add pyproject.toml uv.lock
git commit -m "chore: pin pdomain-book-contracts for layout spans"
```

Expected: `uv.lock` records the new release URL under `pdomain-book-contracts`. The commit does not include labeler source.

### Task 5: Proposals from OCR word boxes

**Files:**

- Create: `pdomain-ocr-labeler-spa/src/pdomain_ocr_labeler_spa/core/regions/text_layout.py`
- Test: `pdomain-ocr-labeler-spa/tests/unit/core/regions/test_text_layout.py`

**Interfaces:**

- Consumes: `PageLayoutSpan` and `merge_page_layout_spans` from the wheel pinned in Task 4. OCR words have `text` and `bounding_box` (`minX`, `minY`, `maxX`, `maxY`, and `is_normalized`). `RegionProposalLog` takes the project root.
- Produces: `propose_text_layout(*, project_root: Path, page_index: int, page_key: str, f2_page_text: str, ocr_words: Sequence[object], page_width: int, page_height: int, created_at: str, page_facet_digests: dict[int, dict[str, str]], gutenberg_table_texts: Sequence[str] = (), gutenberg_attached: bool = False, run_id: str) -> tuple[RegionProposal, ...]`.

`created_at` is UTC ISO-8601 and is stored as given. `page_facet_digests` must contain this `page_index` with non-empty `word_text` and `word_boxes`. Any other shape raises `ValueError`. The production caller passes `compute_page_facet_digests`. This function does not compute digests.

Each call requires a non-empty `run_id` unique within this project's proposal log, including calls for different pages. Before writing anything, read the existing runs and reject an empty or reused ID with `ValueError`. Rejection leaves the log bytes unchanged. A call appends exactly one run, then its proposals. The caller serializes calls for the same project; concurrent writers are outside this function's contract.

The run uses `model_id="f2-gutenberg-layout"`, `model_version="1"`, `depends_on=frozenset({FACET_WORD_TEXT, FACET_WORD_BOXES})`, `page_kind_decision_ref=None`, and `page_kind_was_confirmed=False`. Evidence stores `page_key` and `sources` as a list of strings. Convert each word with `_bbox_to_model(bounding_box, page_width=page_width, page_height=page_height)`. The proposal box is `(min x, min y, max x+width, max y+height)`. A span with no contiguous casefold match is omitted. The first contiguous run wins.

F2 text for a mirrored page is `rounds/F2.json` keyed by the image filename. This function receives that page's string. It does not open the corpus and does not download Gutenberg.

- [ ] **Step 1: Write the failing tests**

`_word` sets `text` and a bounding box with `minX`, `minY`, `maxX`, `maxY`, and `is_normalized`. `_call` fills `page_width=100`, `page_height=200`, `created_at="2026-11-07T00:00:00+00:00"`, and `page_facet_digests={0: {"word_text": "digest-text", "word_boxes": "digest-boxes"}}`.

```python
def test_poetry_proposal_unions_the_matched_word_boxes(tmp_path: Path) -> None:
    words = [_word("Line", 0, 0, 10, 10), _word("one", 12, 0, 30, 10)]
    proposals = _call(tmp_path, f2_page_text="/*\nLine one\n*/", ocr_words=words)
    assert len(proposals) == 1
    assert proposals[0].role.value == "poetry"
    assert proposals[0].box == (0, 0, 30, 10)
    assert proposals[0].confidence == 0.9
    assert proposals[0].evidence["page_key"] == "001.png"
    assert proposals[0].evidence["sources"] == ["f2"]
    runs = RegionProposalLog(tmp_path).runs()
    assert runs[0].created_at == "2026-11-07T00:00:00+00:00"
    assert runs[0].page_facet_digests[0] == {
        "word_text": "digest-text",
        "word_boxes": "digest-boxes",
    }


def test_reordered_ocr_words_emit_nothing(tmp_path: Path) -> None:
    words = [_word("one", 0, 0, 10, 10), _word("Line", 12, 0, 30, 10)]
    assert _call(tmp_path, f2_page_text="/*\nLine one\n*/", ocr_words=words) == ()


def test_skipped_middle_word_emits_nothing(tmp_path: Path) -> None:
    words = [
        _word("Line", 0, 0, 10, 10),
        _word("extra", 12, 0, 20, 10),
        _word("one", 22, 0, 30, 10),
    ]
    assert _call(tmp_path, f2_page_text="/*\nLine one\n*/", ocr_words=words) == ()


def test_casefold_match_and_first_run_wins(tmp_path: Path) -> None:
    words = [
        _word("line", 0, 0, 10, 10),
        _word("ONE", 12, 0, 30, 10),
        _word("Line", 100, 0, 110, 10),
        _word("one", 112, 0, 130, 10),
    ]
    proposals = _call(tmp_path, f2_page_text="/*\nLine one\n*/", ocr_words=words)
    assert len(proposals) == 1
    assert proposals[0].box == (0, 0, 30, 10)


def test_normalized_box_is_scaled_by_page_size(tmp_path: Path) -> None:
    words = [
        _word("Line", 0.0, 0.0, 0.10, 0.05, normalized=True),
        _word("one", 0.12, 0.0, 0.30, 0.05, normalized=True),
    ]
    proposals = _call(tmp_path, f2_page_text="/*\nLine one\n*/", ocr_words=words)
    assert proposals[0].box == (0, 0, 30, 10)


def test_mismatch_proposes_the_gutenberg_words(tmp_path: Path) -> None:
    words = [_word("Gamma", 0, 0, 10, 10), _word("Delta", 12, 0, 30, 10)]
    proposals = _call(
        tmp_path,
        f2_page_text="<table><tr><td>Alpha</td><td>Beta</td></tr></table>",
        ocr_words=words,
        gutenberg_table_texts=("Gamma Delta",),
        gutenberg_attached=True,
    )
    assert len(proposals) == 1
    assert proposals[0].role.value == "table"
    assert proposals[0].confidence == 0.7
    assert proposals[0].evidence["sources"] == ["gutenberg_html"]
    assert proposals[0].box == (0, 0, 30, 10)


def test_empty_facet_digests_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        propose_text_layout(
            project_root=tmp_path,
            page_index=0,
            page_key="001.png",
            f2_page_text="/*\nLine one\n*/",
            ocr_words=[_word("Line", 0, 0, 10, 10), _word("one", 12, 0, 30, 10)],
            page_width=100,
            page_height=200,
            created_at="2026-11-07T00:00:00+00:00",
            page_facet_digests={},
            run_id="run-1",
        )
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run this only after Task 4. The contracts import must succeed. The expected failure is the missing labeler function.

Add a duplicate-ID test that calls the function successfully, snapshots `.pd-pages/region-proposals.jsonl`, then calls it with the same `run_id` for another page. Assert `ValueError`, unchanged log bytes, and exactly one run. Add an empty-ID test that asserts `ValueError` before any log write. Successful calls for two pages with distinct IDs must produce exactly two runs and their matching page proposals.

Run: `cd /mnt/work/projects/pdomain/pdomain-ocr-labeler-spa && uv run pytest tests/unit/core/regions/test_text_layout.py -v`

Expected: FAIL because `propose_text_layout` is missing.

- [ ] **Step 3: Implement the matcher and append the run**

Append the run before the proposals. Return the proposals that were written. Do not add a UI component. The existing region panel lists this log. Do not add a path dependency.

If the labeler working tree has other uncommitted work, stop and report that.

- [ ] **Step 4: Re-run the tests**

Run the same pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/work/projects/pdomain/pdomain-ocr-labeler-spa
git add src/pdomain_ocr_labeler_spa/core/regions/text_layout.py tests/unit/core/regions/test_text_layout.py
git commit -m "feat: propose layout regions from F2 and Gutenberg text"
```

## What this plan leaves out

The labeler does not yet call `propose_text_layout` when a page finishes OCR. Wiring that call is the next change after these tasks. It should pass `rounds/F2.json` for the current image filename, the page width and height, `created_at`, and `compute_page_facet_digests` for that page. Gutenberg table strings come from `gutenberg_table_texts` only for pages named by an accepted edition alignment.

Accepting a proposal and exporting `regions/labels.json` already exist. This plan does not change that export and does not run training.
