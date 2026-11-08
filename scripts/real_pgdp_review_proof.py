#!/usr/bin/env python3
"""Run bounded, auditable setup checks for the real PGDP review proof.

The final proof deliberately waits for the separately-owned source bridge and
labeler API.  This command still makes the nine-case corpus selection and its
real Tesseract cache inspectable now, and writes a report that records every
missing public dependency instead of substituting P3 for OCR.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import shlex
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict

_TESSERACT_COLUMNS = (
    "level",
    "page_num",
    "block_num",
    "par_num",
    "line_num",
    "word_num",
    "left",
    "top",
    "width",
    "height",
    "conf",
    "text",
)
_WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)

ProofMode = Literal["describe", "validate-ocr", "proof"]
ReviewDecision = Literal["pending", "accepted", "rejected", "edited"]


class CaseListError(ValueError):
    """Raised when a selected-case file cannot identify a bounded proof set."""


class OcrTsvError(ValueError):
    """Raised when a purported OCR artifact is not a Tesseract TSV."""


@dataclass(frozen=True, slots=True)
class ProofCase:
    """One explicitly selected corpus page and the behavior it exercises."""

    project_id: str
    page_key: str
    intent: str

    @property
    def ocr_filename(self) -> str:
        """Return the stable filename assigned to this page's cached OCR TSV."""
        return f"{self.project_id}-{self.page_key}.tsv"


class WordCounts(TypedDict):
    """Observed word counts before public matching is available."""

    f2_raw: int | None
    p3: int | None
    ocr: int | None


class AlignmentMetrics(TypedDict):
    """Metrics populated only by the later public source/labeler proof."""

    f2_to_p3_mapped: int | None
    p3_to_ocr_mapped: int | None
    unresolved: int | None
    style_projection: int | None
    split_join_groups: int | None
    disagreements: int | None
    timing_ms: int | None


class FileIdentity(TypedDict):
    """A non-hash identity for a concrete proof input."""

    path: str
    size_bytes: int
    mtime_ns: int


class PublicOperation(TypedDict):
    """One public CLI operation and its unmodified JSON outcome."""

    subject: str
    stage: str
    argv: list[str]
    status: Literal["ok", "error", "blocked"]
    payload: dict[str, object] | None
    error: str | None


class CaseReport(TypedDict):
    """A per-page setup result preserved even when one page fails."""

    project_id: str
    page_key: str
    intent: str
    status: str
    word_counts: WordCounts
    metrics: AlignmentMetrics
    blockers: list[str]
    input_identities: dict[str, FileIdentity]


class SetupSummary(TypedDict):
    """Aggregate result for the complete requested selection."""

    case_count: int
    requested_case_count: int
    setup_ready_count: int
    setup_failed_count: int
    complete_selection: bool


class SetupReport(TypedDict):
    """Machine-readable report for setup and later public-interface stages."""

    schema_version: int
    generated_at: str
    mode: ProofMode
    commands: dict[str, str]
    input_sources: dict[str, str]
    input_identities: dict[str, FileIdentity]
    summary: SetupSummary
    integration: dict[str, list[str] | str]
    cases: list[CaseReport]
    public_operations: list[PublicOperation]


def load_cases(
    cases_path: Path,
    *,
    case_limit: int | None,
    allow_partial: bool,
) -> list[ProofCase]:
    """Read the TSV selection, rejecting duplicate or silently partial work."""
    if case_limit is not None and case_limit < 1:
        raise CaseListError("case-limit must be at least one")
    try:
        with cases_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle, delimiter="\t"))
    except OSError as error:
        raise CaseListError(f"cannot read selected cases from {cases_path}: {error}") from error

    cases: list[ProofCase] = []
    seen: set[tuple[str, str]] = set()
    for line_number, row in enumerate(rows, start=1):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 3:
            raise CaseListError(f"{cases_path}:{line_number}: expected three tab-separated columns")
        project_id, page_key, intent = (cell.strip() for cell in row)
        if not project_id or not page_key or not intent:
            raise CaseListError(
                f"{cases_path}:{line_number}: project, page, and intent are required"
            )
        key = (project_id, page_key)
        if key in seen:
            raise CaseListError(
                f"{cases_path}:{line_number}: duplicate selected page {project_id}/{page_key}"
            )
        seen.add(key)
        cases.append(ProofCase(project_id=project_id, page_key=page_key, intent=intent))

    if not cases:
        raise CaseListError(f"{cases_path}: no selected cases")
    if case_limit is not None and case_limit < len(cases):
        if not allow_partial:
            raise CaseListError(
                "case-limit would omit selected cases; pass --allow-partial to record an explicit partial run"
            )
        return cases[:case_limit]
    return cases


def parse_ocr_tsv(ocr_path: Path) -> int:
    """Return nonempty word-row count from a real Tesseract TSV artifact."""
    try:
        with ocr_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if reader.fieldnames != list(_TESSERACT_COLUMNS):
                raise OcrTsvError(f"{ocr_path}: expected the Tesseract TSV header")
            word_count = 0
            for row in reader:
                if row.get("level") == "5" and row.get("text", "").strip():
                    word_count += 1
    except OSError as error:
        raise OcrTsvError(f"cannot read OCR TSV {ocr_path}: {error}") from error
    return word_count


def build_setup_report(
    *,
    cases: list[ProofCase],
    corpus_root: Path,
    ocr_root: Path,
    mode: ProofMode,
    requested_case_count: int | None = None,
    cases_path: Path | None = None,
    invocation: str = "not recorded",
) -> SetupReport:
    """Inspect every requested real input without modifying the read-only corpus."""
    reports = [
        _inspect_case(case=case, corpus_root=corpus_root, ocr_root=ocr_root) for case in cases
    ]
    ready_count = sum(case["status"] == "setup_ready" for case in reports)
    failed_count = len(reports) - ready_count
    total_requested = len(cases) if requested_case_count is None else requested_case_count
    report_identities: dict[str, FileIdentity] = {}
    if cases_path is not None:
        selection_identity = _file_identity(cases_path)
        if selection_identity is not None:
            report_identities["cases_tsv"] = selection_identity
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "commands": {
            "cached_ocr_origin": "OMP_THREAD_LIMIT=1 tesseract IMAGE stdout -l eng --psm 3 tsv",
            "source_bridge": "PYTHON -m pdomain_source_data.pgdp_review_cli",
            "labeler_control": "pdomain-ocr-labeler-control --base-url URL",
            "invocation": invocation,
        },
        "input_sources": {
            "corpus_root": str(corpus_root),
            "ocr_root": str(ocr_root),
            "cases_tsv": str(cases_path) if cases_path is not None else "not supplied",
        },
        "input_identities": report_identities,
        "summary": {
            "case_count": len(reports),
            "requested_case_count": total_requested,
            "setup_ready_count": ready_count,
            "setup_failed_count": failed_count,
            "complete_selection": len(reports) == total_requested,
        },
        "integration": {
            "status": "blocked_pending_public_components",
            "requirements": [
                "functional contracts-ready.json wheel and examples",
                "source preparation CLI",
                "labeler HTTP API and JSON control client",
                "labeler browser automation acknowledgement flow",
            ],
        },
        "cases": reports,
        "public_operations": [],
    }


def _inspect_case(*, case: ProofCase, corpus_root: Path, ocr_root: Path) -> CaseReport:
    project_root = corpus_root / case.project_id
    image_path = project_root / case.page_key
    f2_path = project_root / "rounds" / "F2.json"
    p3_path = project_root / "rounds" / "P3.json"
    ocr_path = ocr_root / case.ocr_filename
    blockers: list[str] = []
    identities: dict[str, FileIdentity] = {}
    f2_text = _page_text(f2_path, case.page_key, "F2", blockers, identities)
    p3_text = _page_text(p3_path, case.page_key, "P3", blockers, identities)
    _record_identity("scan", image_path, blockers, identities)
    ocr_words = _ocr_word_count(ocr_path, blockers, identities)
    if f2_text is None or p3_text is None or ocr_words is None:
        status = "setup_failed"
    else:
        status = "setup_ready"
    blockers.extend(
        (
            "source preparation CLI has not produced the selected prepared book",
            "labeler public OCR/alignment/review/export APIs are not available",
        )
    )
    return {
        "project_id": case.project_id,
        "page_key": case.page_key,
        "intent": case.intent,
        "status": status,
        "word_counts": {
            "f2_raw": _count_words(f2_text),
            "p3": _count_words(p3_text),
            "ocr": ocr_words,
        },
        "metrics": {
            "f2_to_p3_mapped": None,
            "p3_to_ocr_mapped": None,
            "unresolved": None,
            "style_projection": None,
            "split_join_groups": None,
            "disagreements": None,
            "timing_ms": None,
        },
        "blockers": blockers,
        "input_identities": identities,
    }


def _page_text(
    json_path: Path,
    page_key: str,
    round_name: str,
    blockers: list[str],
    identities: dict[str, FileIdentity],
) -> str | None:
    _record_identity(round_name.lower(), json_path, blockers, identities)
    if not json_path.is_file():
        return None
    try:
        parsed: object = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        blockers.append(f"cannot parse {round_name} data {json_path}: {error}")
        return None
    if not isinstance(parsed, dict):
        blockers.append(f"{round_name} data {json_path} is not a page mapping")
        return None
    page_text = parsed.get(page_key)
    if not isinstance(page_text, str):
        blockers.append(f"{round_name} data has no string entry for {page_key}")
        return None
    return page_text


def _record_identity(
    label: str,
    path: Path,
    blockers: list[str],
    identities: dict[str, FileIdentity],
) -> None:
    try:
        stat_result = path.stat()
    except OSError as error:
        blockers.append(f"missing {label} input {path}: {error}")
        return
    identities[label] = {
        "path": str(path),
        "size_bytes": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
    }


def _file_identity(path: Path) -> FileIdentity | None:
    try:
        stat_result = path.stat()
    except OSError:
        return None
    return {
        "path": str(path),
        "size_bytes": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
    }


def _ocr_word_count(
    ocr_path: Path,
    blockers: list[str],
    identities: dict[str, FileIdentity],
) -> int | None:
    _record_identity("ocr_tsv", ocr_path, blockers, identities)
    if not ocr_path.is_file():
        return None
    try:
        return parse_ocr_tsv(ocr_path)
    except OcrTsvError as error:
        blockers.append(str(error))
        return None


def _count_words(text: str | None) -> int | None:
    if text is None:
        return None
    return len(_WORD_PATTERN.findall(text))


def _run_json_command(
    argv: tuple[str, ...], *, request: dict[str, object] | None, timeout_seconds: float
) -> PublicOperation:
    """Run one configured public CLI without a shell and parse its sole JSON result."""
    try:
        stdout, stderr, returncode = asyncio.run(
            _communicate(argv, request=request, timeout_seconds=timeout_seconds)
        )
    except (OSError, TimeoutError) as error:
        return _error_operation(argv, str(error))
    try:
        parsed: object = json.loads(stdout)
    except json.JSONDecodeError as error:
        return _error_operation(argv, f"invalid JSON stdout: {error}; stderr: {stderr.strip()}")
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        return _error_operation(argv, "JSON stdout must be one object")
    payload = {key: value for key, value in parsed.items() if isinstance(key, str)}
    if returncode != 0:
        return _error_operation(
            argv, f"exit {returncode}: {stderr.strip() or payload}", payload=payload
        )
    return {
        "subject": "",
        "stage": "",
        "argv": list(argv),
        "status": "ok",
        "payload": payload,
        "error": None,
    }


async def _communicate(
    argv: tuple[str, ...], *, request: dict[str, object] | None, timeout_seconds: float
) -> tuple[str, str, int]:
    input_bytes = None if request is None else json.dumps(request).encode("utf-8")
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE if input_bytes is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(input_bytes), timeout_seconds)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    returncode = process.returncode
    if returncode is None:
        raise RuntimeError("owned command completed without a return code")
    return stdout.decode("utf-8"), stderr.decode("utf-8"), returncode


def _error_operation(
    argv: tuple[str, ...], error: str, *, payload: dict[str, object] | None = None
) -> PublicOperation:
    return {
        "subject": "",
        "stage": "",
        "argv": list(argv),
        "status": "error",
        "payload": payload,
        "error": error,
    }


def _operation(outcome: PublicOperation, *, subject: str, stage: str) -> PublicOperation:
    outcome["subject"] = subject
    outcome["stage"] = stage
    return outcome


def run_public_proof(
    *,
    cases: list[ProofCase],
    corpus_root: Path,
    source_python: Path,
    source_module: str,
    source_output_root: Path,
    labeler_control: Path,
    labeler_base_url: str,
    timeout_seconds: float,
    review_decision: ReviewDecision,
) -> list[PublicOperation]:
    """Exercise only frozen source and labeler public commands for every selected case.

    It records the raw inspect response and submits at most one representative
    group review per page using the frozen DTO, avoiding bulk synthetic review.
    """
    operations: list[PublicOperation] = []
    source_prefix = (str(source_python), "-m", source_module)
    control_prefix = (str(labeler_control), "--base-url", labeler_base_url)
    grouped_cases: dict[str, list[ProofCase]] = {}
    for case in cases:
        grouped_cases.setdefault(case.project_id, []).append(case)
    catalog = _run_json_command(
        source_prefix,
        request={
            "command": "projects",
            "corpus_root": str(corpus_root),
            "limit": 100,
            "offset": 0,
        },
        timeout_seconds=timeout_seconds,
    )
    operations.append(_operation(catalog, subject="catalog", stage="source_projects"))
    for project_id, project_cases in grouped_cases.items():
        pages = _run_json_command(
            source_prefix,
            request={
                "command": "pages",
                "corpus_root": str(corpus_root),
                "project_id": project_id,
                "limit": 100,
                "offset": 0,
            },
            timeout_seconds=timeout_seconds,
        )
        operations.append(_operation(pages, subject=project_id, stage="source_pages"))
        prepare = _run_json_command(
            source_prefix,
            request={
                "command": "prepare",
                "corpus_root": str(corpus_root),
                "project_id": project_id,
                "page_keys": [case.page_key for case in project_cases],
                "output_root": str(source_output_root),
            },
            timeout_seconds=timeout_seconds,
        )
        operations.append(_operation(prepare, subject=project_id, stage="source_prepare"))
        book_path = _source_book_path(prepare)
        if book_path is None:
            continue
        loaded = _run_json_command(
            (*control_prefix, "load", book_path, "--page-index", "0"),
            request=None,
            timeout_seconds=timeout_seconds,
        )
        operations.append(_operation(loaded, subject=project_id, stage="labeler_load"))
        labeler_project_id = _payload_nested_string(loaded, "project", "project_id")
        if labeler_project_id is None:
            operations.append(
                {
                    "subject": project_id,
                    "stage": "labeler_case_sequence",
                    "argv": [],
                    "status": "blocked",
                    "payload": loaded["payload"],
                    "error": "load response has no published project_id field",
                }
            )
            continue
        for page_index, case in enumerate(project_cases):
            _run_case_sequence(
                operations=operations,
                control_prefix=control_prefix,
                labeler_project_id=labeler_project_id,
                page_index=page_index,
                case=case,
                timeout_seconds=timeout_seconds,
                review_decision=review_decision,
            )
    return operations


def _source_book_path(operation: PublicOperation) -> str | None:
    payload = operation["payload"]
    if payload is None or payload.get("ok") is not True:
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    book_path = result.get("book_path")
    return book_path if isinstance(book_path, str) else None


def _payload_string(operation: PublicOperation, field_name: str) -> str | None:
    payload = operation["payload"]
    if payload is None:
        return None
    value = payload.get(field_name)
    return value if isinstance(value, str) else None


def _payload_nested_string(
    operation: PublicOperation, object_name: str, field_name: str
) -> str | None:
    payload = operation["payload"]
    if payload is None:
        return None
    nested = payload.get(object_name)
    if not isinstance(nested, dict):
        return None
    value = nested.get(field_name)
    return value if isinstance(value, str) else None


def _payload_integer(operation: PublicOperation, field_name: str) -> int | None:
    payload = operation["payload"]
    if payload is None:
        return None
    value = payload.get(field_name)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _run_case_sequence(
    *,
    operations: list[PublicOperation],
    control_prefix: tuple[str, ...],
    labeler_project_id: str,
    page_index: int,
    case: ProofCase,
    timeout_seconds: float,
    review_decision: ReviewDecision,
) -> None:
    subject = f"{case.project_id}/{case.page_key}"
    index = str(page_index)
    timeout = str(timeout_seconds)
    page = _operation(
        _run_json_command(
            (*control_prefix, "page", labeler_project_id, index, "--wait", "--timeout", timeout),
            request=None,
            timeout_seconds=timeout_seconds,
        ),
        subject=subject,
        stage="labeler_page",
    )
    operations.append(page)
    ocr = _operation(
        _run_json_command(
            (
                *control_prefix,
                "ocr",
                labeler_project_id,
                index,
                "--engine",
                "tesseract",
                "--wait",
                "--timeout",
                timeout,
            ),
            request=None,
            timeout_seconds=timeout_seconds,
        ),
        subject=subject,
        stage="labeler_ocr",
    )
    operations.append(ocr)
    page_after_ocr = _operation(
        _run_json_command(
            (*control_prefix, "page", labeler_project_id, index, "--wait", "--timeout", timeout),
            request=None,
            timeout_seconds=timeout_seconds,
        ),
        subject=subject,
        stage="labeler_page_after_ocr",
    )
    operations.append(page_after_ocr)
    generation = _payload_integer(page_after_ocr, "generation")
    if generation is None:
        operations.append(
            {
                "subject": subject,
                "stage": "labeler_align",
                "argv": [],
                "status": "blocked",
                "payload": page_after_ocr["payload"],
                "error": "post-OCR page response has no published generation field",
            }
        )
    else:
        operations.append(
            _operation(
                _run_json_command(
                    (
                        *control_prefix,
                        "align",
                        labeler_project_id,
                        index,
                        "--request-id",
                        f"proof-{uuid.uuid4()}",
                        "--generation",
                        str(generation),
                        "--wait",
                        "--timeout",
                        timeout,
                    ),
                    request=None,
                    timeout_seconds=timeout_seconds,
                ),
                subject=subject,
                stage="labeler_align",
            )
        )
    inspect = _operation(
        _run_json_command(
            (*control_prefix, "inspect", labeler_project_id, index),
            request=None,
            timeout_seconds=timeout_seconds,
        ),
        subject=subject,
        stage="labeler_inspect",
    )
    operations.append(inspect)
    result_id, review_generation, group_ids = _review_targets(inspect)
    if result_id is None or review_generation is None:
        operations.append(
            {
                "subject": subject,
                "stage": "labeler_review_group",
                "argv": [],
                "status": "blocked",
                "payload": inspect["payload"],
                "error": "inspect response has no result_id/current generation",
            }
        )
    else:
        operations.extend(
            _operation(
                _run_json_command(
                    (
                        *control_prefix,
                        "request",
                        "PATCH",
                        f"/api/projects/{labeler_project_id}/pages/{index}/source-alignment/groups/{group_id}",
                        "--json",
                        json.dumps(
                            {
                                "expected_generation": review_generation,
                                "result_id": result_id,
                                "decision": review_decision,
                                "note": "",
                                "reviewed_text": None,
                            }
                        ),
                    ),
                    request=None,
                    timeout_seconds=timeout_seconds,
                ),
                subject=subject,
                stage="labeler_review_group",
            )
            for group_id in group_ids[:1]
        )
    operations.append(
        _operation(
            _run_json_command(
                (
                    *control_prefix,
                    "export",
                    labeler_project_id,
                    "--page-index",
                    index,
                    "--regions-only",
                    "--wait",
                    "--timeout",
                    timeout,
                ),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=subject,
            stage="labeler_export",
        )
    )


def _review_targets(operation: PublicOperation) -> tuple[str | None, int | None, tuple[str, ...]]:
    payload = operation["payload"]
    if payload is None:
        return None, None, ()
    generation = payload.get("generation")
    result = payload.get("result")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or not isinstance(result, dict)
    ):
        return None, None, ()
    result_id = result.get("result_id")
    groups = result.get("groups")
    if not isinstance(result_id, str) or not isinstance(groups, list):
        return None, None, ()
    group_ids = tuple(
        group_id
        for group in groups
        if isinstance(group, dict) and isinstance((group_id := group.get("group_id")), str)
    )
    return result_id, generation, group_ids


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("describe", "validate-ocr", "proof"),
        default="describe",
        help="describe inputs, validate cached real OCR, or run the later public-interface proof",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("cases.tsv"),
        help="TSV with project ID, page key, and intended behavior",
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path("/mnt/work/projects/pdomain-data/pgdp-corpus"),
        help="read-only PGDP corpus root",
    )
    parser.add_argument(
        "--ocr-root",
        type=Path,
        default=Path("artifacts/ocr"),
        help="directory containing real Tesseract TSV cache artifacts",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/proof"),
        help="directory for regenerable proof reports",
    )
    parser.add_argument("--json-report", type=Path, help="explicit JSON report destination")
    parser.add_argument(
        "--source-python",
        type=Path,
        help="interpreter that will run the source JSON CLI after the contracts freeze",
    )
    parser.add_argument(
        "--source-module",
        default="pdomain_source_data.pgdp_review_cli",
        help="source JSON CLI module; default is the frozen source bridge contract",
    )
    parser.add_argument(
        "--source-output-root",
        type=Path,
        default=Path("artifacts/source/books"),
        help="prepared-book output root passed to the source JSON CLI",
    )
    parser.add_argument("--labeler-base-url", help="labeler HTTP base URL for the final proof")
    parser.add_argument("--labeler-control", type=Path, help="labeler JSON-control executable")
    parser.add_argument(
        "--review-decision",
        choices=("pending", "accepted", "rejected", "edited"),
        default="pending",
        help="explicit non-destructive group-review decision",
    )
    parser.add_argument(
        "--server-timeout-seconds",
        type=float,
        default=15.0,
        help="bounded HTTP request timeout for the final proof",
    )
    parser.add_argument(
        "--job-timeout-seconds",
        type=float,
        default=120.0,
        help="bounded wait for source/labeler jobs in the final proof",
    )
    parser.add_argument(
        "--case-limit", type=int, help="explicitly limit cases only with --allow-partial"
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="record that a requested case limit omits selected pages",
    )
    return parser


def _write_report(report: SetupReport, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    (destination.parent / ".nobackup").touch()
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run the requested setup stage and return a machine-meaningful exit code."""
    args = _parser().parse_args(argv)
    mode: ProofMode = args.mode
    destination = args.json_report or args.output_dir / "real-pgdp-review-proof.json"
    invocation_args = sys.argv[1:] if argv is None else argv
    invocation = shlex.join([sys.argv[0], *invocation_args])
    try:
        requested_cases = load_cases(args.cases, case_limit=None, allow_partial=False)
        cases = load_cases(args.cases, case_limit=args.case_limit, allow_partial=args.allow_partial)
        report = build_setup_report(
            cases=cases,
            corpus_root=args.corpus_root,
            ocr_root=args.ocr_root,
            mode=mode,
            requested_case_count=len(requested_cases),
            cases_path=args.cases,
            invocation=invocation,
        )
    except CaseListError as error:
        print(json.dumps({"ok": False, "error": {"code": "case_selection", "message": str(error)}}))
        return 2
    _write_report(report, destination)
    if mode == "proof":
        missing_configuration = [
            name
            for name, value in (
                ("--source-python", args.source_python),
                ("--labeler-base-url", args.labeler_base_url),
                ("--labeler-control", args.labeler_control),
            )
            if value is None
        ]
        if not missing_configuration:
            report["public_operations"] = run_public_proof(
                cases=cases,
                corpus_root=args.corpus_root,
                source_python=args.source_python,
                source_module=args.source_module,
                source_output_root=args.source_output_root,
                labeler_control=args.labeler_control,
                labeler_base_url=args.labeler_base_url,
                timeout_seconds=args.server_timeout_seconds,
                review_decision=args.review_decision,
            )
            report["integration"]["status"] = "public_commands_executed_review_schema_pending"
            _write_report(report, destination)
        reason = (
            f"missing required public-interface configuration: {', '.join(missing_configuration)}"
            if missing_configuration
            else "review-group payload waits for the labeler inspect schema example"
        )
        print(
            json.dumps(
                {
                    "ok": False,
                    "report": str(destination),
                    "error": {
                        "code": "dependencies_unavailable",
                        "message": reason,
                    },
                }
            )
        )
        return 3
    print(json.dumps({"ok": True, "report": str(destination), "summary": report["summary"]}))
    return 2 if report["summary"]["setup_failed_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
