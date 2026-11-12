---
Status: built
Owner: CT
Created: 2026-11-12
Last verified: 2026-11-12
Kind: architecture
---

# Layout review

Reviewed page structure is shared across five repositories.

- Contracts describe text evidence without pixel boxes.
- Source-data prepares selected PGDP pages.
- The labeler reviews regions and source text.
- Training reads the optional reviewed structure.
- This repository owns the repeatable real-data proof.

## Agent Index

- **Kind:** architecture
- **Status:** built
- **Read when:** changing PGDP alignment, source tabs, region export, or the real-data proof.
- **Search terms:** layout review, F2, Gutenberg, P3, columns, verse, source tabs, proof harness.

P3 is the ground-truth page text.

F2 and Gutenberg supply formatting evidence.

Scan OCR and measured boxes decide physical regions.

## Who owns which part

`pdomain-book-contracts` defines the portable records.

Layout text hints shipped in `v0.2.1` (`94e4eef`).

Bounded F2-to-P3-to-OCR alignment shipped in `v0.3.0` (`1bd8261`), in `pdomain_book_contracts/matching/pgdp_layout_projection.py`.

The package stays free of imaging and machine-learning dependencies.

`pdomain-source-data` extracts Gutenberg hints from accepted edition alignments and prepares selected pages.

Its master requires `pdomain-book-contracts>=0.3.0`.

Callers pass a project id and page keys. They do not assemble hash-filled TOML.

The labeler calls a configured source-data JSON command. It does not import source-data as a hard dependency.

`pdomain-ocr-labeler-spa` owns review, persistence, export, and the automation API.

Its master requires `pdomain-book-contracts>=0.3.0`.

Text tabs are Matches, Working GT, P3, F2, Consolidated GT, and OCR.

- Working GT shows current corrections.
- Word edits stay in Matches.
- Consolidated GT is a read-only preview of P3 wording plus supported F2 formatting.
- P3 and F2 tabs show the prepared transcription.

The control client is `pdomain-ocr-labeler-control`.

`pdomain-ocr-training` reads optional reviewed structure beside existing region labels.

Its master still requires `pdomain-book-contracts>=0.2.1`.

The reader forwards loaded records and rejects a missing model.

It does not train a layout model by itself.

`pdomain-ops` owns `scripts/real_pgdp_review_proof.py` and `scripts/fixtures/real-pgdp-review-cases.tsv`.

The operator steps are in the [PGDP API runbook](../runbooks/pgdp-api-review.md).

## Rules the review path keeps

An HTML `<table>` can be a data table, columns, verse, or other presentation. The tag alone never assigns the table role. A bare table stays a table candidate.

Physical columns are separate regions with their content roles, plus column grouping and reading order. There is no semantic column role.

The first proof is left-to-right. Bidirectional reading order is not implemented.

F2 `/* */` is a formatted block. It is not poetry by itself.

Gutenberg poem, poetry, verse, stanza, or blockquote markup can support those hints.

A plain paragraph or an isolated line break does not establish verse.

Gutenberg evidence is used only from an accepted paired edition alignment, and only after page-specific text matching.

A proposal needs matched OCR words and a nonempty pixel box.

HTML supplies no scan coordinates.

Source indentation and stanza breaks describe the edition. They stay distinct from measured scan geometry. Disagreement stays visible.

Review does not move words or renumber the OCR hierarchy. Suggestions do not overwrite human ground truth or typography edits.

Ranking values `0.9` for F2, `0.7` for Gutenberg, and `0.95` when those sources agree are ranks, not measured probabilities.

Page navigation from Go, Enter, browser history, and the API uses one page identity.

Only a successful terminal response from the page-load route publishes `page_changed.generation_reset: true`.

Each browser tab has its own viewer id. An acknowledgement must match that tab, the command sequence, and the current page generation.

## What the proofs established

The checks below are the recorded proofs.

On 2026-11-12 the named commits were ancestors of each repository's master.

This pass did not rerun the browser proof or the test gates.

The published F2 and Gutenberg path was checked on 2026-11-08 with 92 focused tests. Of those, 21 were in contracts, 12 in source-data, 27 in the labeler, and 32 in training.

Eight Chromium checks ran.

An installed-wheel check kept verse structure, two paragraph columns with reading order `0, 1`, reviewed 2×2 table cells, stable word ids, and refreshed geometry.

Contracts `v0.2.1` was published from `94e4eef`.

The pip index publish was `e30d081`.

Later normal checks against that published dependency passed.

- Contracts release preflight passed 55 tests.
- Source-data passed 476 tests and skipped 3 mounted-corpus tests.
- The labeler passed 2,181 backend tests, 4 Docker tests, 2,240 frontend tests, and 8 Chromium cases.
- Training passed 156 tests.

No consumer package was tagged in that rollout.

No model was trained.

The later alignment proof, now in contracts `v0.3.0`, ran 152 public operations on nine real pages against labeler wheel `0.6.1.dev11+gbbd043542`.

All 1,530 OCR words kept their order, ids, text, and boxes through review and reload. The corpus was unchanged.

Eight Chromium tests passed.

Two verse cases stayed partial.

- Poems `008.png` exported 5 reviewed verse lines and 27 source word ids.
- Poems `009.png` exported 9 lines and 85 source word ids.
- Century `020.png` exported two paragraph regions in one column group, indices 0 and 1, reading order 0 and 1, excluding the running header.
- Century `081.png` and `082.png` produced no false columns.
- Century `082.png` kept an F2-backed blockquote and exported 27 lines with 258 source word ids.

| Page | OCR words | Composed alignment | Unresolved formatting items |
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

Source tabs were proved on the same nine pages with labeler wheel `0.6.1.dev14+ga96cff907`, from commit `a96cff907`. That commit is on labeler master.

The final candidate reported 2,269 backend tests and one expected GPU-unavailable skip. It reported 2,290 frontend tests across 164 files, and four Docker checks.

All six tabs followed seven navigation transitions.

An external reload reset generation 2 to 0.

- Century `020.png` kept all 241 word records and showed italic `régime`.
- On Century `020.png`, the word `voyageur` stayed unresolved.
- Poems `008.png` showed both mapped lines at an eight-character indent, 56 pixels in that browser.

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

These proofs do not establish full-corpus quality or a trained model.

Detailed word-bound formatting still needs a prepared bundle with stored word ids.

Safe local mappings can remain on an ambiguous or exhausted page.

## Evidence

- **Code:** `scripts/real_pgdp_review_proof.py`, `scripts/fixtures/real-pgdp-review-cases.tsv`, `tests/scripts/test_real_pgdp_review_proof.py`. Sibling masters were checked on 2026-11-12. Contracts was `a50c756`, with tags `v0.2.1` and `v0.3.0`. Source-data was `4601095`. Labeler was `5a5fbcf0`, including `src/pdomain_ocr_labeler_spa/core/source_text.py` and `frontend/src/components/TextTabs.tsx`. Training was `e50bb66`.
- **Tests:** The 2026-11-08 counts in the section above. This documentation pass did not rerun them.
- **Artifacts:** Proof receipts moved from `/tmp/pdomain-p3-f2-20261108` to `/mnt/work/projects/pdomain/.artifacts/tmp-archive-20261110/pdomain-p3-f2-20261108/`.
- **Verified:** 2026-11-12 by `git merge-base --is-ancestor` for `94e4eef`, `1bd8261`, `4e30fd6`, `f3d73fd`, `2d35bef`, `bbd0435`, `a96cff907`, `bc7ed72`, `5c5b835`, and `adb148d`, plus the contracts tag `v0.3.0^{commit}`.
