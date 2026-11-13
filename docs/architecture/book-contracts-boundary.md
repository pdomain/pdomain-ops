---
Status: built
Owner: CT
Created: 2026-11-13
Last verified: 2026-11-13
Kind: architecture
---

# Book contracts package boundary

`pdomain-book-contracts` owns the shared value types and pure transformations.
`pdomain-book-tools` owns imaging and OCR implementations and imports contracts
in one direction. This record preserves the shipped extraction boundary; it does
not establish data rescue or retirement of the old `pd-` repositories. Those
outcomes remain in the [extraction plan](../plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md).

## Agent Index

- **Kind:** architecture
- **Status:** built
- **Last verified:** 2026-11-13
- **Read when:** changing contracts imports or deciding where a shared type belongs.
- **Search terms:** book contracts, module layout, extraction, image provider, dependency direction.

## Module responsibilities

The package groups code by responsibility:

| Package | Responsibility |
|---|---|
| `annotation/` | Provenance, roles, page kinds and mappings |
| `geometry/` | Points, bounding boxes and the image-provider boundary |
| `text/` | Label normalization and text transformations |
| `typography/` | Labels, spans, normalization, records, annotations, exchange and review |
| `matching/` | Alignment, matching models and engine, continuation handling and legacy projections |
| `ocr/` | Characters, glyph annotations, review, provenance and blob protocols |
| `layout/` | Layout types and regions |
| `sources/pgdp/` | Shared round containers and offsets; F2-specific markup under `f2/` |
| `licensing.py`, `_schemas.py` | Licensing values and shared schema configuration |

Alignment lives in `matching/` alongside the engine and matching vocabulary.
Text transformations live in `text/`, while typography normalization stays in
`typography/`: it depends on typography labels and spans, and records import
its comparison operation. Moving it to `text/` previously caused a runtime
import cycle.

PGDP `rounds.py` and `offsets.py` handle the shared round-JSON container.
F2 tokens, parsing, project rules and warnings remain under `f2/`. P3 needs no
separate markup parser. `layout/regions.py` avoids confusing layout regions
with geometry values; one root `_schemas.py` holds shared schema configuration.
Typography review and OCR review remain separate modules.

## Dependency direction

The inspected cross-package imports are:

```text
_schemas, text               no cross-package dependencies
geometry                     depends on _schemas
layout, licensing            no cross-package dependencies
annotation                   depends on layout
typography                   depends on geometry, _schemas, annotation
ocr                          depends on geometry, text, _schemas, annotation
matching                     depends on geometry, typography, layout, sources/pgdp
sources/pgdp                 depends on typography, layout
```

This is a source inspection, not an exhaustive cycle-enforcement test.
Package import tests do not replace consumer type checks.

## Imaging and structural protocols

Contracts do not import book-tools to run image operations. Bounding-box
compatibility methods `refine`, `crop_top` and `crop_bottom` dispatch through
`ImageOpsProvider`. An unregistered call raises `ImageOpsUnavailableError`.
Book-tools registers its implementation when `geometry/image_ops.py` loads.
Registration stays out of the geometry package initializer so importing
geometry does not eagerly load cv2. Book-tools also uses a lazy root
`__getattr__` for compatibility exports.

`matching/legacy_projection.py` uses private structural protocols for words,
lines and pages instead of importing concrete book-tools classes. The line
and page protocols are generic in word type. This accommodates concrete
`remove_item` parameter types, a constraint that required consumer type checks
to expose. The old book-tools `ocr/ground_truth_matching.py` shim is outside
this extraction; retiring it remains separate work.

## Evidence

- **Source:** sibling `pdomain-book-contracts` at `1b1605a`, including
  `geometry/bounding_box.py`, `matching/legacy_projection.py`, and the packages
  above; sibling `pdomain-book-tools` at `50fcb0e`, including its root
  `__init__.py` and `geometry/image_ops.py`.
- **Tests inspected:** contracts `tests/test_package.py`,
  `tests/test_torch_free_import.py`, `tests/test_bounding_box_image_ops.py`.
- **Prior review:** the retired module-layout spec records thirteen passing
  tests on 2026-11-07 and corrections to annotation and schema dependencies.
  That review did not replay every historical move or every consumer gate.
- **Verified:** 2026-11-13 by fresh source and test inspection. Sibling tests
  were not rerun in this migration. Historical line counts are not current
  measurements, and stored-data compatibility and repository retirement
  remain unproved.
