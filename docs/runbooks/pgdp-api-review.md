---
Status: active
Owner: CT
Created: 2026-11-08
Last verified: 2026-11-12
Kind: runbook
---

# Review real PGDP pages through the API

Use the labeler's JSON control client to prepare PGDP pages, run scan OCR, inspect F2/P3 mappings, and direct an open browser. The source corpus stays read-only. Review decisions and exports stay with the prepared working book.

## Agent Index

- **Kind:** runbook
- **Status:** active
- **Owner:** CT
- **Last verified:** 2026-11-12
- **Read when:** operating the development P3/F2 review flow or running its real-data proof.
- **Search terms:** PGDP, P3, F2, API, automation, viewer, Tesseract, real proof

## Trigger

Use this flow when a person or LLM needs to prepare selected corpus pages and review their formatting against actual scan OCR. Shipped behavior and measured outcomes are in [layout review](../architecture/layout-review.md).

## Preconditions

Contracts `v0.3.0` (`1bd8261`) contains the matching APIs. Labeler and source-data masters require `pdomain-book-contracts>=0.3.0`. The 2026-11-08 installed environment predates that release and has contracts `0.2.2.dev1+g1bd8261b5`. The commands below still name that proof environment. Receipts that were under `/tmp/pdomain-p3-f2-20261108` are archived at `/mnt/work/projects/pdomain/.artifacts/tmp-archive-20261110/pdomain-p3-f2-20261108/`.

The labeler needs Tesseract with `eng`, a configured corpus root, a Python interpreter that can run the source-data JSON CLI, and a writable books folder outside the corpus. Prepared books must be written under the labeler's configured books folder. Loading a book from another folder returns `project_outside_source_root`.

For the installed local build:

```bash
LABELER_ENV=/mnt/work/projects/pdomain/pdomain-ocr-labeler-spa/.worktrees/p3-f2-installed-proof-20261108/venv
CONTROL="$LABELER_ENV/bin/pdomain-ocr-labeler-control"
BASE_URL=http://127.0.0.1:8795
"$CONTROL" --base-url "$BASE_URL" state
```

`/mnt/work/projects/pdomain/.artifacts/tmp-archive-20261110/pdomain-p3-f2-20261108/labeler-artifact-ready.json` records this build's version, server mode, and readiness as of 2026-11-08. Use `state` to check the server that is running now. An `api_only` server supports automation but does not serve the browser UI. Do not treat a restart marker as a live server.

To start a separate normal-mode server from that installed build, choose an unused port and keep its files outside the corpus. This example uses port 8794 and the bundled frontend.

```bash
REVIEW_ROOT=/tmp/pgdp-api-review
mkdir -p "$REVIEW_ROOT/books"
PDLABELER_MODE=normal \
PDLABELER_CONFIG_ROOT="$REVIEW_ROOT/config" \
PDLABELER_DATA_ROOT="$REVIEW_ROOT/data" \
PDLABELER_CACHE_ROOT="$REVIEW_ROOT/cache" \
PDLABELER_SOURCE_PROJECTS_ROOT="$REVIEW_ROOT/books" \
PDLABELER_PGDP_CORPUS_ROOT=/mnt/work/projects/pdomain-data/pgdp-corpus \
PDLABELER_SOURCE_DATA_PYTHON=/mnt/work/projects/pdomain/.artifacts/p3-f2-20261108/source-wheel-smoke-env/bin/python \
PDLABELER_OCR_ENGINE=tesseract PDLABELER_NO_PREFETCH=true \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES= \
  "$LABELER_ENV/bin/pdomain-ocr-labeler-ui" \
  --port 8794 --no-browser --projects-root "$REVIEW_ROOT/books"
```

Leave that process running. Initialize the operator's second terminal and check readiness:

```bash
LABELER_ENV=/mnt/work/projects/pdomain/pdomain-ocr-labeler-spa/.worktrees/p3-f2-installed-proof-20261108/venv
CONTROL="$LABELER_ENV/bin/pdomain-ocr-labeler-control"
REVIEW_ROOT=/tmp/pgdp-api-review
BASE_URL=http://127.0.0.1:8794
curl -fsS "$BASE_URL/healthz"
"$CONTROL" --base-url "$BASE_URL" state
```

Confirm that Tesseract and PGDP preparation are available. Open that URL in the browser; a missing frontend must be fixed before browser verification. The source interpreter above runs the final built wheel outside its checkout; its path is recorded in `source-ready.json`.

## Steps

### Prepare and load a book

List a bounded catalog window or query a known project's pages:

```bash
"$CONTROL" --base-url "$BASE_URL" catalog --query Poems --limit 100 --offset 0
"$CONTROL" --base-url "$BASE_URL" catalog-pages projectID64ff850152930
```

Catalog offsets count scanned metadata entries. A query can return no matches and still have a `next_offset`; follow that cursor before concluding that a book is absent.

Prepare the three selected Poems pages through the server's configured source bridge:

```bash
"$CONTROL" --base-url "$BASE_URL" prepare projectID64ff850152930 \
  --page 008.png --page 009.png --page 026.png \
  --request-id poems-selected-review-1 --wait --timeout 120 > /tmp/pgdp-prepare.json
BOOK_PATH=$(jq -r '.result.book_path' /tmp/pgdp-prepare.json)
"$CONTROL" --base-url "$BASE_URL" load "$BOOK_PATH" --page-index 0
```

Reuse a request ID only for the same logical request and identical inputs. A conflicting reuse fails. After an uncertain transport timeout, inspect the existing job or retry the same idempotent request instead of inventing a new ID.

### Read source rounds before OCR

The text tabs are Matches, Working GT, P3, F2, Consolidated GT and OCR. Working GT shows current corrections; edit individual words in Matches. F2 and P3 retain the prepared source transcription. Consolidated GT is a read-only preview of P3 wording with F2 formatting supported by accepted source-to-source matches. Unresolved formatting names the affected source text.

Supported verse indents appear in the main consolidated transcript. Optional layout-line `grapheme_range` values identify half-open positions in P3 visible text; `indent_columns` records the mapped F2 indent. The UI checks exact line text and boundaries before applying any remaining indent. Source layout details stay collapsed by default.

The source endpoint does not load OCR pages, start OCR jobs or change corrections:

```bash
PROJECT_ID=projectID64ff850152930
"$CONTROL" --base-url "$BASE_URL" request GET \
  "/api/projects/$PROJECT_ID/pages/1/source-text" > /tmp/pgdp-source-text.json
jq '{page_key, available, warnings,
     unresolved: .consolidated.unresolved}' /tmp/pgdp-source-text.json
```

API page indices are zero-based. A project without prepared F2/P3 snapshots returns `available: false`; its normal correction and OCR views remain usable. Source availability does not imply that every formatting span can be consolidated.

### Run OCR and inspect alignment

API page indices are zero-based; the browser's `pageno` URL uses one-based page numbers. The prepared page order follows the original source order, even if the preparation request listed pages differently.

```bash
PROJECT_ID=projectID64ff850152930
"$CONTROL" --base-url "$BASE_URL" page "$PROJECT_ID" 1 --wait --timeout 120
"$CONTROL" --base-url "$BASE_URL" ocr "$PROJECT_ID" 1 \
  --engine tesseract --wait --timeout 120
"$CONTROL" --base-url "$BASE_URL" page "$PROJECT_ID" 1 --wait > /tmp/pgdp-page.json
GENERATION=$(jq -r '.generation' /tmp/pgdp-page.json)
"$CONTROL" --base-url "$BASE_URL" align "$PROJECT_ID" 1 \
  --request-id poems-page-009-alignment-1 --generation "$GENERATION" \
  --wait --timeout 120
"$CONTROL" --base-url "$BASE_URL" inspect "$PROJECT_ID" 1 > /tmp/pgdp-alignment.json
jq '{generation, stale, result_id: .result.result_id,
     groups: [.result.groups[] | {group_id, disposition, decision, f2_text, p3_text, ocr_text}],
     unresolved: .result.projection.unresolved}' /tmp/pgdp-alignment.json
```

F2 supplies formatting and P3 supplies corrected wording. Neither is OCR output. The new alignment route preserves OCR word count, order and boxes. A group can link several source or OCR words; it is not necessarily a one-to-one match.

`accepted` in a group's disposition is the algorithm's mapping decision. Its separate `decision` field records review. Changed, ambiguous, unmapped and exhausted groups remain inspectable. A formatted block is not automatically poetry, and physical columns are not data tables.

### Review and direct the browser

Read the current `result_id`, `generation` and chosen `group_id` from the inspect response. Submit a review with `review-group`, `--result-id`, `--generation` and `--decision`. Add `--json '{"note":"…","reviewed_text":"…"}'` for an annotation. These annotations do not overwrite OCR or human ground truth. Refresh the generation after a successful write; stale writes return a conflict.

Set `GROUP_ID` to a group you inspected. This example leaves its review pending and records a note:

```bash
RESULT_ID=$(jq -r '.result.result_id' /tmp/pgdp-alignment.json)
GENERATION=$(jq -r '.generation' /tmp/pgdp-alignment.json)
"$CONTROL" --base-url "$BASE_URL" review-group "$PROJECT_ID" 1 "$GROUP_ID" \
  --result-id "$RESULT_ID" --generation "$GENERATION" --decision pending \
  --json '{"note":"Needs review against the scan"}'
```

Open the normal-mode server in a browser and obtain that tab's `viewer_id` from `state`. With several tabs open, identify the intended tab using its session-storage key `pdomain-ocr-labeler.viewer-id`. A viewer command targets one tab of the currently loaded project:

```bash
"$CONTROL" --base-url "$BASE_URL" view \
  --viewer-id "$VIEWER_ID" --project "$PROJECT_ID" --page-index 1 \
  --panel source_alignment --alignment-id "$RESULT_ID" \
  --alignment-group-id "$GROUP_ID" --wait-ack --timeout 30
"$CONTROL" --base-url "$BASE_URL" view-state --viewer-id "$VIEWER_ID"
```

Set those three IDs from the current state and inspect responses. `--wait-ack` waits for the browser's observed project, page, panel, selection and generation. An accepted command alone does not prove that the browser displayed it. A disconnected viewer stays pending or times out.

Review the page kind before running region proposals. The following request confirms that the selected Poems page is body text. Without a proposed or confirmed page kind, the existing region job skips the page.

```bash
"$CONTROL" --base-url "$BASE_URL" request POST \
  "/api/projects/$PROJECT_ID/page-kinds/confirm" \
  --json '{"pages":[{"page_index":1,"kind":"body"}],"note":"Reviewed verse body page"}'
```

Then run proposals for eligible pages of the loaded book and inspect the chosen page. Set `PROPOSAL_ID` from the proposal you reviewed. Detailed formatting needs an explicit reviewed `layout_structure` in the acceptance payload. Omitting it accepts the box and role only. The following commands carry the selected proposal's structure after you review it, then obtain the confirmed `REGION_ID`. Proposal and region IDs have different meanings.

```bash
"$CONTROL" --base-url "$BASE_URL" propose "$PROJECT_ID" --wait --timeout 120
"$CONTROL" --base-url "$BASE_URL" proposals "$PROJECT_ID" 1 > /tmp/pgdp-proposals.json
REGION_REVIEW_JSON=$(jq -c --arg id "$PROPOSAL_ID" \
  '.proposals[] | select(.proposal_id == $id) |
   if .evidence.layout_structure == null then {}
   else {layout_structure: .evidence.layout_structure} end' \
  /tmp/pgdp-proposals.json)
"$CONTROL" --base-url "$BASE_URL" region-review "$PROJECT_ID" 1 "$PROPOSAL_ID" accept \
  --json "$REGION_REVIEW_JSON" > /tmp/pgdp-accepted-region.json
REGION_ID=$(jq -r --arg id "$PROPOSAL_ID" \
  '.regions[] | select(.proposal_id == $id and .confirmed == true) | .region_id' \
  /tmp/pgdp-accepted-region.json)
"$CONTROL" --base-url "$BASE_URL" region-edit "$PROJECT_ID" 1 "$REGION_ID" \
  --json '{"role":"poetry"}'
"$CONTROL" --base-url "$BASE_URL" page "$PROJECT_ID" 1 > /tmp/pgdp-page.json
GENERATION=$(jq -r '.generation' /tmp/pgdp-page.json)
"$CONTROL" --base-url "$BASE_URL" save "$PROJECT_ID" 1 --generation "$GENERATION"
"$CONTROL" --base-url "$BASE_URL" reload "$PROJECT_ID" 1 --wait --timeout 120
"$CONTROL" --base-url "$BASE_URL" inspect "$PROJECT_ID" 1 > /tmp/pgdp-reloaded-alignment.json
"$CONTROL" --base-url "$BASE_URL" export "$PROJECT_ID" \
  --regions-only --page-index 1 --wait --timeout 120
```

The role edit above is appropriate only for a reviewed verse region. Other regions can use another role, a corrected `box`, or `layout_structure` through `--json`. Do not classify a region as poetry merely because its F2 source used `/* */`. Consult `/openapi.json` for those request bodies.

Completed API page reloads refresh an open browser without a manual browser reload. Only a successful terminal response from `POST /api/projects/{project_id}/pages/{page_index}/load` publishes `page_changed.generation_reset: true`. Custom event consumers must cancel old page requests before resetting response ordering. Ordinary events retain their existing field shape, omit this marker and preserve generation ordering.

Region-only exports write `labels.json` and `structure.json` under `<data_root>/doctr-export/<project_id>/all/regions/`. The job reports completion; these sidecars are separate from the full DocTR export-manifest listing. With the development server configured above, inspect the detailed output with:

```bash
jq . "$REVIEW_ROOT/data/doctr-export/$PROJECT_ID/all/regions/structure.json"
```

## Verification

The real-data proof selects nine pages across Poems, European Statistics and Century magazine. Keep every selected page in the report, including partial and exhausted alignments. The harness on this repository's master is `scripts/real_pgdp_review_proof.py`, committed in `adb148d`. It checks raw OCR identities, review persistence, exported verse, paired columns, and false column proposals on single-column quotations. The quotation continuation must retain an F2-backed blockquote proposal. The command below is the 2026-11-08 invocation. The worktree `.worktrees/p3-f2-proof` is gone, so that command cannot be rerun as written.

Run the harness against the installed build, keeping its prepared output under the same books root used by the server:

```bash
PROOF_TREE=/mnt/work/projects/pdomain/pdomain-ops/.worktrees/p3-f2-proof
"$PROOF_TREE/.venv/bin/python" "$PROOF_TREE/scripts/real_pgdp_review_proof.py" \
  --mode proof --cases "$PROOF_TREE/scripts/fixtures/real-pgdp-review-cases.tsv" \
  --corpus-root /mnt/work/projects/pdomain-data/pgdp-corpus \
  --source-python /mnt/work/projects/pdomain/.artifacts/p3-f2-20261108/source-wheel-smoke-env/bin/python \
  --source-output-root "$REVIEW_ROOT/books" \
  --labeler-control "$CONTROL" --labeler-base-url "$BASE_URL" \
  --output-dir "$REVIEW_ROOT/proof"
```

The installed development build completed all 152 operations on these nine pages. Seven behavior checks passed. Two verse cases remained explicitly partial. Several whole-page alignments remain ambiguous, changed, or exhausted. This proves the selected workflow, not full-corpus formatting quality.

Check the report's final completion state and per-page operation counts. A setup report or a report still being written is not a completed API proof. Confirm actual OCR, unchanged word topology and source identities, persisted review annotations, and exported structure. Browser evidence must show an already-open page changing after external API commands without a reload.

## Rollback

The corpus needs no rollback because this workflow does not write to it. Keep prepared books, review stores and exports separate from the corpus. Stop only a server you started, using its recorded PID. Preserve working books and reports until their review is complete.
