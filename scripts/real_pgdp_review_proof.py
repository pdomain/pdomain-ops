#!/usr/bin/env python3
"""Run a bounded, auditable proof through the real PGDP review public APIs."""

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
CachedOcrValidation = Literal["not_requested", "validated", "unavailable"]
DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "fixtures" / "real-pgdp-review-cases.tsv"


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
    group_dispositions: dict[str, int] | None
    projected_hints: int | None
    unresolved_hints: int | None
    ocr_token_count: int | None
    split_relations: int | None
    join_relations: int | None
    accepted_groups: int | None
    alignment_warning_count: int | None


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
    cached_ocr_validation: CachedOcrValidation
    word_counts: WordCounts
    metrics: AlignmentMetrics
    blockers: list[str]
    input_identities: dict[str, FileIdentity]
    proof_evidence: ProofEvidence


class ProofEvidence(TypedDict):
    """Public observations required to distinguish a completed proof from setup."""

    status: str
    raw_ocr_text: str | None
    ground_truth_text: str | None
    raw_ocr_token_count: int | None
    raw_ocr_word_count: int | None
    ocr_engine: str | None
    reviewed_group_id: str | None
    reviewed_note: str | None
    reviewed_text: str | None
    reviewed_region_proposal_id: str | None
    reviewed_region_structure_kind: str | None
    reviewed_region_structure_status: str
    region_count_after_reload: int | None
    proposal_count: int | None
    invariants: list[str]
    behavior_observations: dict[str, str]


class SetupSummary(TypedDict):
    """Aggregate result for the complete requested selection."""

    case_count: int
    requested_case_count: int
    setup_ready_count: int
    setup_failed_count: int
    complete_selection: bool
    behavior_verified_count: int
    behavior_partial_count: int
    behavior_failure_count: int


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
    ocr_root: Path | None,
    mode: ProofMode,
    requested_case_count: int | None = None,
    cases_path: Path | None = None,
    invocation: str = "not recorded",
) -> SetupReport:
    """Inspect every requested real input without modifying the read-only corpus."""
    require_cached_ocr = mode == "validate-ocr"
    reports = [
        _inspect_case(
            case=case,
            corpus_root=corpus_root,
            ocr_root=ocr_root,
            require_cached_ocr=require_cached_ocr,
        )
        for case in cases
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
            "cached_ocr_origin": (
                "OMP_THREAD_LIMIT=1 tesseract IMAGE stdout -l eng --psm 3 tsv"
                if ocr_root is not None
                else "not requested; proof invokes native labeler OCR"
            ),
            "source_bridge": "PYTHON -m pdomain_source_data.pgdp_review_cli",
            "labeler_control": "pdomain-ocr-labeler-control --base-url URL",
            "invocation": invocation,
        },
        "input_sources": {
            "corpus_root": str(corpus_root),
            "ocr_root": (
                str(ocr_root)
                if ocr_root is not None
                else "not requested; native labeler OCR is primary"
            ),
            "cases_tsv": str(cases_path) if cases_path is not None else "not supplied",
        },
        "input_identities": report_identities,
        "summary": {
            "case_count": len(reports),
            "requested_case_count": total_requested,
            "setup_ready_count": ready_count,
            "setup_failed_count": failed_count,
            "complete_selection": len(reports) == total_requested,
            "behavior_verified_count": 0,
            "behavior_partial_count": 0,
            "behavior_failure_count": 0,
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


def _inspect_case(
    *,
    case: ProofCase,
    corpus_root: Path,
    ocr_root: Path | None,
    require_cached_ocr: bool,
) -> CaseReport:
    project_root = corpus_root / case.project_id
    image_path = project_root / case.page_key
    f2_path = project_root / "rounds" / "F2.json"
    p3_path = project_root / "rounds" / "P3.json"
    blockers: list[str] = []
    identities: dict[str, FileIdentity] = {}
    f2_text = _page_text(f2_path, case.page_key, "F2", blockers, identities)
    p3_text = _page_text(p3_path, case.page_key, "P3", blockers, identities)
    _record_identity("scan", image_path, blockers, identities)
    ocr_words: int | None = None
    if ocr_root is None:
        cache_validation: CachedOcrValidation = "not_requested"
    else:
        ocr_words = _ocr_word_count(ocr_root / case.ocr_filename, blockers, identities)
        cache_validation = "validated" if ocr_words is not None else "unavailable"
    if f2_text is None or p3_text is None or (require_cached_ocr and ocr_words is None):
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
        "cached_ocr_validation": cache_validation,
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
            "group_dispositions": None,
            "projected_hints": None,
            "unresolved_hints": None,
            "ocr_token_count": None,
            "split_relations": None,
            "join_relations": None,
            "accepted_groups": None,
            "alignment_warning_count": None,
        },
        "blockers": blockers,
        "input_identities": identities,
        "proof_evidence": {
            "status": "not_run",
            "raw_ocr_text": None,
            "ground_truth_text": None,
            "raw_ocr_token_count": None,
            "raw_ocr_word_count": None,
            "ocr_engine": None,
            "reviewed_group_id": None,
            "reviewed_note": None,
            "reviewed_text": None,
            "reviewed_region_proposal_id": None,
            "reviewed_region_structure_kind": None,
            "reviewed_region_structure_status": "not_run",
            "region_count_after_reload": None,
            "proposal_count": None,
            "invariants": [],
            "behavior_observations": {},
        },
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
        page_kind_confirmation = _operation(
            _run_json_command(
                (
                    *control_prefix,
                    "request",
                    "POST",
                    f"/api/projects/{labeler_project_id}/page-kinds/confirm",
                    "--json",
                    json.dumps(
                        {
                            "pages": [
                                {
                                    "page_index": page_index,
                                    "kind": _proof_page_kind(case),
                                }
                                for page_index, case in enumerate(project_cases)
                            ],
                            "note": "Algorithm review for real PGDP proof working copy",
                        }
                    ),
                ),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=project_id,
            stage="labeler_page_kind_confirm",
        )
        operations.append(page_kind_confirmation)
        if page_kind_confirmation["status"] != "ok":
            operations.append(
                {
                    "subject": project_id,
                    "stage": "labeler_propose",
                    "argv": [],
                    "status": "blocked",
                    "payload": page_kind_confirmation["payload"],
                    "error": "page-kind confirmation failed; region proposal was not attempted",
                }
            )
            continue
        propose = _operation(
            _run_json_command(
                (*control_prefix, "propose", labeler_project_id, "--wait"),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=project_id,
            stage="labeler_propose",
        )
        operations.append(propose)
        for page_index, case in enumerate(project_cases):
            _run_region_review_sequence(
                operations=operations,
                control_prefix=control_prefix,
                labeler_project_id=labeler_project_id,
                page_index=page_index,
                case=case,
                timeout_seconds=timeout_seconds,
            )
    return operations


def _proof_page_kind(case: ProofCase) -> str:
    return "contents" if case.page_key == "03.png" else "body"


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
    result_id, review_generation, groups = _review_targets(inspect)
    target = groups[0] if groups else None
    review: PublicOperation | None = None
    if result_id is None or review_generation is None or target is None:
        operations.append(
            {
                "subject": subject,
                "stage": "labeler_review_group",
                "argv": [],
                "status": "blocked",
                "payload": inspect["payload"],
                "error": "inspect response has no editable current group",
            }
        )
    else:
        group_id, reviewed_text = target
        note = f"real-proof:{case.project_id}/{case.page_key}"
        review = _operation(
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
                            "note": note,
                            "reviewed_text": reviewed_text,
                        }
                    ),
                ),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=subject,
            stage="labeler_review_group",
        )
        operations.append(review)
    save_generation = (
        _payload_integer(review, "generation") if review is not None else review_generation
    )
    operations.append(
        _operation(
            _run_json_command(
                (
                    *control_prefix,
                    "save",
                    labeler_project_id,
                    index,
                    "--generation",
                    str(save_generation),
                ),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=subject,
            stage="labeler_save",
        )
    )
    operations.append(
        _operation(
            _run_json_command(
                (
                    *control_prefix,
                    "reload",
                    labeler_project_id,
                    index,
                    "--wait",
                    "--timeout",
                    timeout,
                ),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=subject,
            stage="labeler_reload",
        )
    )
    operations.append(
        _operation(
            _run_json_command(
                (*control_prefix, "inspect", labeler_project_id, index),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=subject,
            stage="labeler_inspect_after_reload",
        )
    )


def _review_targets(
    operation: PublicOperation,
) -> tuple[str | None, int | None, tuple[tuple[str, str], ...]]:
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
        (group_id, reviewed_text)
        for group in groups
        if isinstance(group, dict)
        and isinstance((group_id := group.get("group_id")), str)
        and isinstance((reviewed_text := group.get("ocr_text")), str)
    )
    return result_id, generation, group_ids


def _run_region_review_sequence(
    *,
    operations: list[PublicOperation],
    control_prefix: tuple[str, ...],
    labeler_project_id: str,
    page_index: int,
    case: ProofCase,
    timeout_seconds: float,
) -> None:
    subject = f"{case.project_id}/{case.page_key}"
    index = str(page_index)
    proposals = _operation(
        _run_json_command(
            (*control_prefix, "proposals", labeler_project_id, index),
            request=None,
            timeout_seconds=timeout_seconds,
        ),
        subject=subject,
        stage="labeler_proposals",
    )
    operations.append(proposals)
    targets = _region_review_targets(proposals, case=case)
    if not targets:
        region_reviews: list[PublicOperation] = [
            {
                "subject": subject,
                "stage": "labeler_region_review",
                "argv": [],
                "status": "ok",
                "payload": proposals["payload"],
                "error": "no genuine region proposal was returned",
            }
        ]
    else:
        region_reviews = []
        for target in targets:
            command = (
                *control_prefix,
                "region-review",
                labeler_project_id,
                index,
                target.proposal_id,
                "accept",
            )
            if target.layout_structure is not None:
                command = (
                    *command,
                    "--json",
                    json.dumps({"layout_structure": target.layout_structure}),
                )
            region_reviews.append(
                _operation(
                    _run_json_command(
                        command,
                        request=None,
                        timeout_seconds=timeout_seconds,
                    ),
                    subject=subject,
                    stage="labeler_region_review",
                )
            )
    operations.extend(region_reviews)
    final_region_review = region_reviews[-1]
    region_generation = _payload_integer(final_region_review, "generation")
    if region_generation is None:
        operations.append(
            {
                "subject": subject,
                "stage": "labeler_save_after_region_review",
                "argv": [],
                "status": "blocked",
                "payload": final_region_review["payload"],
                "error": "region review response has no published generation field",
            }
        )
    else:
        operations.append(
            _operation(
                _run_json_command(
                    (
                        *control_prefix,
                        "save",
                        labeler_project_id,
                        index,
                        "--generation",
                        str(region_generation),
                    ),
                    request=None,
                    timeout_seconds=timeout_seconds,
                ),
                subject=subject,
                stage="labeler_save_after_region_review",
            )
        )
    operations.append(
        _operation(
            _run_json_command(
                (
                    *control_prefix,
                    "reload",
                    labeler_project_id,
                    index,
                    "--wait",
                    "--timeout",
                    str(timeout_seconds),
                ),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=subject,
            stage="labeler_reload_after_region_review",
        )
    )
    operations.append(
        _operation(
            _run_json_command(
                (*control_prefix, "page", labeler_project_id, index),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=subject,
            stage="labeler_page_after_region_review",
        )
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
                ),
                request=None,
                timeout_seconds=timeout_seconds,
            ),
            subject=subject,
            stage="labeler_export",
        )
    )


@dataclass(frozen=True, slots=True)
class RegionReviewTarget:
    """One published proposal selected for a bounded reviewed-region operation."""

    proposal_id: str
    layout_structure: dict[str, object] | None


def _region_review_targets(
    operation: PublicOperation, *, case: ProofCase | None
) -> tuple[RegionReviewTarget, ...]:
    """Select one representative proposal, or both members of a real column pair."""
    payload = operation["payload"]
    if payload is None:
        return ()
    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        return ()
    generic_target: RegionReviewTarget | None = None
    structured_targets: list[RegionReviewTarget] = []
    for proposal in proposals:
        if not isinstance(proposal, dict) or not isinstance(
            (proposal_id := proposal.get("proposal_id")), str
        ):
            continue
        structure = _proposal_layout_structure(proposal)
        if structure is not None:
            structured_targets.append(
                RegionReviewTarget(proposal_id=proposal_id, layout_structure=structure)
            )
            continue
        if generic_target is None:
            generic_target = RegionReviewTarget(proposal_id=proposal_id, layout_structure=None)
    if case is not None and case.intent == "physical_columns_captions":
        column_pair = _column_pair_targets(structured_targets)
        if column_pair:
            return column_pair
    if structured_targets:
        return (structured_targets[0],)
    return (generic_target,) if generic_target is not None else ()


def _column_pair_targets(
    targets: list[RegionReviewTarget],
) -> tuple[RegionReviewTarget, ...]:
    pairs: dict[str, dict[int, RegionReviewTarget]] = {}
    for target in targets:
        structure = target.layout_structure
        if structure is None or structure.get("kind") != "column_flow":
            continue
        group_id = structure.get("column_group_id")
        column_index = structure.get("column_index")
        if (
            isinstance(group_id, str)
            and isinstance(column_index, int)
            and not isinstance(column_index, bool)
        ):
            pairs.setdefault(group_id, {})[column_index] = target
    for columns in pairs.values():
        if 0 in columns and 1 in columns:
            return columns[0], columns[1]
    return ()


def _proposal_layout_structure(proposal: dict[str, object]) -> dict[str, object] | None:
    evidence = proposal.get("evidence")
    if not isinstance(evidence, dict):
        return None
    layout_structure = evidence.get("layout_structure")
    return layout_structure if isinstance(layout_structure, dict) else None


def public_proof_complete(*, cases: list[ProofCase], operations: list[PublicOperation]) -> bool:
    """Return whether every selected page completed each bounded public stage."""
    if not cases or not operations or any(operation["status"] != "ok" for operation in operations):
        return False
    required = {
        "labeler_ocr",
        "labeler_align",
        "labeler_inspect",
        "labeler_review_group",
        "labeler_save",
        "labeler_reload",
        "labeler_inspect_after_reload",
        "labeler_proposals",
        "labeler_region_review",
        "labeler_save_after_region_review",
        "labeler_reload_after_region_review",
        "labeler_page_after_region_review",
        "labeler_export",
    }
    observed = {(operation["subject"], operation["stage"]) for operation in operations}
    if any(
        (f"{case.project_id}/{case.page_key}", stage) not in observed
        for case in cases
        for stage in required
    ):
        return False
    return all(
        (case.project_id, stage) in observed
        for case in cases
        for stage in ("labeler_page_kind_confirm", "labeler_propose")
    )


def populate_proof_evidence(
    *, report: SetupReport, cases: list[ProofCase], operations: list[PublicOperation]
) -> None:
    """Populate per-page metrics and persistence evidence from raw public responses."""
    for case_report, case in zip(report["cases"], cases, strict=True):
        subject = f"{case.project_id}/{case.page_key}"
        before_page = _operation_payload(operations, subject, "labeler_page_after_ocr")
        after_page = _operation_payload(operations, subject, "labeler_page_after_region_review")
        before_inspect = _operation_payload(operations, subject, "labeler_inspect")
        after_inspect = _operation_payload(operations, subject, "labeler_inspect_after_reload")
        proposals = _operation_payload(operations, subject, "labeler_proposals")
        region_review = _operation_for(operations, subject, "labeler_region_review")
        region_export = _operation_for(operations, subject, "labeler_export")
        evidence = case_report["proof_evidence"]
        before_ocr, before_gt = _page_texts(before_page)
        after_ocr, after_gt = _page_texts(after_page)
        before_groups = _inspection_groups(before_inspect)
        after_groups = _inspection_groups(after_inspect)
        note = f"real-proof:{subject}"
        reviewed = next((group for group in after_groups if group[3] == note), None)
        invariants: list[str] = []
        if before_ocr == after_ocr and before_ocr is not None:
            invariants.append("raw_ocr_text_preserved")
        if before_gt == after_gt and before_gt is not None:
            invariants.append("ground_truth_text_preserved")
        if _group_topology(before_groups) == _group_topology(after_groups):
            invariants.append("alignment_group_order_boxes_source_ids_preserved")
        if reviewed is not None and reviewed[4] is not None:
            invariants.append("edited_group_note_and_reviewed_text_survived_reload")
        proposal_id, requested_structure_kind = _region_review_request(region_review)
        returned_structure_kind = _region_structure_kind(region_review, proposal_id)
        persisted_structure_kind = _region_structure_kind_for_proposal(after_page, proposal_id)
        if requested_structure_kind is None:
            structure_status = "not_requested"
        elif (
            returned_structure_kind == requested_structure_kind
            and persisted_structure_kind == requested_structure_kind
            and region_export is not None
            and region_export["status"] == "ok"
        ):
            structure_status = "verified"
            invariants.append("reviewed_region_structure_returned_persisted_and_exported")
        else:
            structure_status = "incomplete"
        base_invariants_complete = all(
            invariant in invariants
            for invariant in (
                "raw_ocr_text_preserved",
                "ground_truth_text_preserved",
                "alignment_group_order_boxes_source_ids_preserved",
                "edited_group_note_and_reviewed_text_survived_reload",
            )
        )
        observations = _behavior_observations(case, after_page, after_inspect, proposals)
        evidence["status"] = (
            "verified"
            if (
                base_invariants_complete
                and structure_status in {"not_requested", "verified"}
                and _behavior_observations_complete(observations)
            )
            else "invariants_incomplete"
        )
        evidence["raw_ocr_text"] = before_ocr
        evidence["ground_truth_text"] = before_gt
        evidence["raw_ocr_token_count"] = len(before_groups)
        evidence["raw_ocr_word_count"] = _count_words(before_ocr)
        evidence["ocr_engine"] = _ocr_engine(operations, subject)
        evidence["reviewed_group_id"] = reviewed[0] if reviewed is not None else None
        evidence["reviewed_note"] = reviewed[3] if reviewed is not None else None
        evidence["reviewed_text"] = reviewed[4] if reviewed is not None else None
        evidence["reviewed_region_proposal_id"] = proposal_id
        evidence["reviewed_region_structure_kind"] = requested_structure_kind
        evidence["reviewed_region_structure_status"] = structure_status
        evidence["region_count_after_reload"] = _list_length(after_page, "regions")
        evidence["proposal_count"] = _list_length(proposals, "proposals")
        evidence["invariants"] = invariants
        evidence["behavior_observations"] = observations
        _populate_metrics(case_report["metrics"], before_inspect)


def _operation_payload(
    operations: list[PublicOperation], subject: str, stage: str
) -> dict[str, object] | None:
    for operation in reversed(operations):
        if operation["subject"] == subject and operation["stage"] == stage:
            return operation["payload"]
    return None


def _operation_for(
    operations: list[PublicOperation], subject: str, stage: str
) -> PublicOperation | None:
    for operation in reversed(operations):
        if operation["subject"] == subject and operation["stage"] == stage:
            return operation
    return None


def _region_review_request(operation: PublicOperation | None) -> tuple[str | None, str | None]:
    if operation is None:
        return None, None
    try:
        command_index = operation["argv"].index("region-review")
    except ValueError:
        return None, None
    proposal_index = command_index + 3
    if proposal_index >= len(operation["argv"]):
        return None, None
    proposal_id = operation["argv"][proposal_index]
    try:
        body_index = operation["argv"].index("--json")
        body = json.loads(operation["argv"][body_index + 1])
    except (IndexError, ValueError, json.JSONDecodeError):
        return proposal_id, None
    if not isinstance(body, dict) or not isinstance(
        (structure := body.get("layout_structure")), dict
    ):
        return proposal_id, None
    kind = structure.get("kind")
    return proposal_id, kind if isinstance(kind, str) else None


def _region_structure_kind(
    operation: PublicOperation | None, proposal_id: str | None
) -> str | None:
    return _region_structure_kind_for_proposal(
        operation["payload"] if operation is not None else None, proposal_id
    )


def _region_structure_kind_for_proposal(
    payload: dict[str, object] | None, proposal_id: str | None
) -> str | None:
    if (
        proposal_id is None
        or payload is None
        or not isinstance((regions := payload.get("regions")), list)
    ):
        return None
    for region in regions:
        if not isinstance(region, dict) or region.get("proposal_id") != proposal_id:
            continue
        structure = region.get("layout_structure")
        if isinstance(structure, dict) and isinstance((kind := structure.get("kind")), str):
            return kind
    return None


def _page_texts(payload: dict[str, object] | None) -> tuple[str | None, str | None]:
    if payload is None:
        return None, None
    ocr = payload.get("page_text_ocr")
    ground_truth = payload.get("page_text_gt")
    return (
        ocr if isinstance(ocr, str) else None,
        ground_truth if isinstance(ground_truth, str) else None,
    )


def _list_length(payload: dict[str, object] | None, name: str) -> int | None:
    if payload is None:
        return None
    value = payload.get(name)
    return len(value) if isinstance(value, list) else None


def _ocr_engine(operations: list[PublicOperation], subject: str) -> str | None:
    for operation in operations:
        if operation["subject"] == subject and operation["stage"] == "labeler_ocr":
            try:
                engine_index = operation["argv"].index("--engine")
            except ValueError:
                return None
            engine = operation["argv"][engine_index + 1 : engine_index + 2]
            return engine[0] if engine else None
    return None


def _inspection_groups(
    payload: dict[str, object] | None,
) -> list[tuple[str, str, str, str, str | None]]:
    if payload is None:
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    groups = result.get("groups")
    if not isinstance(groups, list):
        return []
    snapshots: list[tuple[str, str, str, str, str | None]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = group.get("group_id")
        ocr_text = group.get("ocr_text")
        box = group.get("box")
        source_ids = group.get("source_word_ids")
        note = group.get("note")
        reviewed_text = group.get("reviewed_text")
        if (
            isinstance(group_id, str)
            and isinstance(ocr_text, str)
            and isinstance(note, str)
            and (reviewed_text is None or isinstance(reviewed_text, str))
        ):
            snapshots.append(
                (
                    group_id,
                    ocr_text,
                    json.dumps(
                        {"box": box, "source_word_ids": source_ids},
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    note,
                    reviewed_text,
                )
            )
    return snapshots


def _group_topology(
    groups: list[tuple[str, str, str, str, str | None]],
) -> list[tuple[str, str, str]]:
    return [(group_id, ocr_text, box) for group_id, ocr_text, box, _note, _reviewed in groups]


def _populate_metrics(
    metrics: AlignmentMetrics,
    payload: dict[str, object] | None,
) -> None:
    if payload is None or not isinstance((result := payload.get("result")), dict):
        return
    alignment = result.get("alignment")
    projection = result.get("projection")
    if isinstance(alignment, dict):
        metrics["f2_to_p3_mapped"] = _mapping_count(alignment.get("f2_to_p3"))
        metrics["p3_to_ocr_mapped"] = _mapping_count(alignment.get("p3_to_ocr"))
        metrics["alignment_warning_count"] = _list_value_length(alignment.get("warnings"))
        metrics["timing_ms"] = _timing_ms(alignment.get("timing"))
    if isinstance(projection, dict):
        metrics["projected_hints"] = _value_count(projection.get("layout_hints"))
        metrics["style_projection"] = _value_count(projection.get("style_spans"))
        metrics["unresolved_hints"] = _value_count(projection.get("unresolved"))
        metrics["unresolved"] = metrics["unresolved_hints"]
    dispositions = _group_dispositions(payload)
    metrics["group_dispositions"] = dispositions
    metrics["accepted_groups"] = dispositions.get("accepted", 0)
    metrics["disagreements"] = dispositions.get("changed", 0)
    metrics["ocr_token_count"] = _ocr_word_count_from_result(result)
    split_count, join_count = _relation_counts(alignment)
    metrics["split_relations"] = split_count
    metrics["join_relations"] = join_count
    metrics["split_join_groups"] = split_count + join_count


def _ocr_word_count_from_result(result: dict[str, object]) -> int | None:
    """Count public OCR words, never many-to-many alignment review groups."""
    ocr = result.get("ocr")
    if not isinstance(ocr, dict) or not isinstance((words := ocr.get("ocr_words")), list):
        return None
    return len(words)


def _group_dispositions(payload: dict[str, object]) -> dict[str, int]:
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance((groups := result.get("groups")), list):
        return {}
    counts: dict[str, int] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        disposition = group.get("disposition")
        if isinstance(disposition, str):
            counts[disposition] = counts.get(disposition, 0) + 1
    return counts


def _relation_counts(alignment: object) -> tuple[int, int]:
    if not isinstance(alignment, dict):
        return 0, 0
    split_count = 0
    join_count = 0
    for mapping_name in ("f2_to_p3", "p3_to_ocr"):
        mapping = alignment.get(mapping_name)
        if not isinstance(mapping, dict) or not isinstance(
            (alternative := mapping.get("best_alternative")), dict
        ):
            continue
        relations = alternative.get("relations")
        if not isinstance(relations, list):
            continue
        for relation in relations:
            if not isinstance(relation, dict) or not isinstance(
                (kind := relation.get("kind")), str
            ):
                continue
            split_count += int(kind == "source_to_fragments")
            join_count += int(kind == "sources_to_one")
    return split_count, join_count


def _mapping_count(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    alternative = value.get("best_alternative")
    if not isinstance(alternative, dict):
        return 0
    relations = alternative.get("relations")
    if not isinstance(relations, list):
        return 0
    return sum(
        1
        for relation in relations
        if isinstance(relation, dict)
        and _nonempty_string_list(relation.get("source_token_ids"))
        and _nonempty_string_list(relation.get("target_token_ids"))
    )


def _nonempty_string_list(value: object) -> bool:
    return isinstance(value, list) and any(isinstance(item, str) and item for item in value)


def _integer_value(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _value_count(value: object) -> int | None:
    integer = _integer_value(value)
    if integer is not None:
        return integer
    return len(value) if isinstance(value, list) else None


def _list_value_length(value: object) -> int | None:
    return len(value) if isinstance(value, list) else None


def _timing_ms(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    seconds = [
        item
        for item in value.values()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    ]
    return round(sum(seconds) * 1000) if seconds else None


def _behavior_observations(
    case: ProofCase,
    page: dict[str, object] | None,
    inspect: dict[str, object] | None,
    proposals: dict[str, object] | None,
) -> dict[str, str]:
    observations: dict[str, str] = {}
    proposal_records = _proposal_records(proposals)
    proposal_roles = _record_roles(proposal_records)
    confirmed_roles = _confirmed_region_roles(page)
    if case.intent == "numeric_tables":
        if not proposal_records:
            observations["not_poetry"] = "missing_proposal"
        elif "poetry" in proposal_roles or "poetry" in confirmed_roles:
            observations["not_poetry"] = "mismatch"
        else:
            observations["not_poetry"] = "verified"
    if case.intent == "formatter_comments_tb":
        source_text = _source_visible_text(inspect)
        if source_text is None:
            observations["formatter_or_tb_visible"] = "incomplete_source_evidence"
        elif _contains_source_markup(source_text):
            observations["formatter_or_tb_visible"] = "mismatch"
        else:
            observations["formatter_or_tb_visible"] = "verified"
    if case.intent.startswith("verse"):
        metadata_present = _has_nonempty_verse_metadata(page)
        poetry_sources_present = _poetry_proposal_has_sources(proposal_records)
        unresolved = _unresolved_layout_count(inspect)
        if not proposal_records:
            observations["verse_stanzas_or_indents"] = "missing_proposal"
        elif metadata_present and poetry_sources_present and unresolved == 0:
            observations["verse_stanzas_or_indents"] = "verified"
        elif metadata_present or poetry_sources_present or unresolved > 0:
            observations["verse_stanzas_or_indents"] = "partial_unresolved"
        else:
            observations["verse_stanzas_or_indents"] = "genuine_mismatch"
    if case.intent == "physical_columns_captions":
        proposal_count = _list_length(proposals, "proposals")
        column_pairs = _column_pairs(page)
        if proposal_count == 0:
            observations["independent_columns"] = "missing_proposal"
        elif any(indices == {0, 1} for indices in column_pairs.values()):
            observations["independent_columns"] = "verified"
        else:
            observations["independent_columns"] = "genuine_mismatch"
    return observations


def _behavior_observations_complete(observations: dict[str, str]) -> bool:
    failed_statuses = {
        "genuine_mismatch",
        "incomplete_source_evidence",
        "mismatch",
        "missing_proposal",
    }
    return not any(status in failed_statuses for status in observations.values())


def populate_behavior_summary(report: SetupReport) -> None:
    """Count verified, honestly partial, and failed behavior observations."""
    verified = 0
    partial = 0
    failed = 0
    for case_report in report["cases"]:
        observations = case_report["proof_evidence"]["behavior_observations"]
        if not _behavior_observations_complete(observations):
            failed += 1
        elif "partial_unresolved" in observations.values():
            partial += 1
        else:
            verified += 1
    report["summary"]["behavior_verified_count"] = verified
    report["summary"]["behavior_partial_count"] = partial
    report["summary"]["behavior_failure_count"] = failed


def _proposal_records(payload: dict[str, object] | None) -> list[dict[str, object]]:
    if payload is None or not isinstance((proposals := payload.get("proposals")), list):
        return []
    return [proposal for proposal in proposals if isinstance(proposal, dict)]


def _record_roles(records: list[dict[str, object]]) -> set[str]:
    return {role for record in records if isinstance((role := record.get("role")), str)}


def _confirmed_region_roles(payload: dict[str, object] | None) -> set[str]:
    if payload is None or not isinstance((regions := payload.get("regions")), list):
        return set()
    return {
        role
        for region in regions
        if isinstance(region, dict)
        and region.get("confirmed") is True
        and isinstance((role := region.get("role")), str)
    }


def _source_visible_text(payload: dict[str, object] | None) -> str | None:
    if payload is None or not isinstance((result := payload.get("result")), dict):
        return None
    f2 = result.get("f2")
    if not isinstance(f2, dict):
        return None
    visible_text = f2.get("visible_text")
    if not isinstance(visible_text, str):
        return None
    token_texts: list[str] = []
    document = f2.get("document")
    if isinstance(document, dict) and isinstance((pages := document.get("pages")), list):
        for page in pages:
            if not isinstance(page, dict) or not isinstance((lines := page.get("lines")), list):
                continue
            for line in lines:
                if not isinstance(line, dict) or not isinstance(
                    (tokens := line.get("tokens")), list
                ):
                    continue
                token_texts.extend(
                    text
                    for token in tokens
                    if isinstance(token, dict) and isinstance((text := token.get("text")), str)
                )
    return "\n".join((visible_text, *token_texts))


def _contains_source_markup(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in ("<tb", "[**", "**]", "/*", "*/"))


def _has_nonempty_verse_metadata(payload: dict[str, object] | None) -> bool:
    if payload is None or not isinstance((hints := payload.get("layout_hints")), list):
        return False
    for hint in hints:
        if not isinstance(hint, dict) or not isinstance((lines := hint.get("lines")), list):
            continue
        for line in lines:
            if not isinstance(line, dict):
                continue
            stanza = line.get("stanza_index")
            indent = line.get("indent_hint")
            if (isinstance(stanza, int) and not isinstance(stanza, bool)) or (
                isinstance(indent, str) and indent.strip()
            ):
                return True
    return False


def _poetry_proposal_has_sources(records: list[dict[str, object]]) -> bool:
    for record in records:
        if record.get("role") != "poetry":
            continue
        evidence = record.get("evidence")
        if isinstance(evidence, dict) and _nonempty_string_list(
            evidence.get("alignment_group_ids")
        ):
            return True
    return False


def _unresolved_layout_count(payload: dict[str, object] | None) -> int:
    if payload is None or not isinstance((result := payload.get("result")), dict):
        return 0
    projection = result.get("projection")
    if not isinstance(projection, dict):
        return 0
    return _value_count(projection.get("unresolved")) or 0


def _page_layout_hints(payload: dict[str, object] | None) -> list[str]:
    if payload is None:
        return []
    values = payload.get("layout_hints")
    return (
        [json.dumps(value, sort_keys=True) for value in values] if isinstance(values, list) else []
    )


def _column_pairs(payload: dict[str, object] | None) -> dict[str, set[int]]:
    if payload is None or not isinstance((regions := payload.get("regions")), list):
        return {}
    pairs: dict[str, set[int]] = {}
    for region in regions:
        _record_column_pairs(region, pairs)
    return pairs


def _record_column_pairs(value: object, pairs: dict[str, set[int]]) -> None:
    if isinstance(value, list):
        for item in value:
            _record_column_pairs(item, pairs)
        return
    if not isinstance(value, dict):
        return
    group_id = value.get("column_group_id")
    column_index = value.get("column_index")
    if (
        isinstance(group_id, str)
        and isinstance(column_index, int)
        and not isinstance(column_index, bool)
    ):
        pairs.setdefault(group_id, set()).add(column_index)
    for nested in value.values():
        _record_column_pairs(nested, pairs)


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
        default=DEFAULT_CASES_PATH,
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
        help="optional real Tesseract TSV cache; required only for --mode validate-ocr",
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
        default="edited",
        help="explicit bounded group-review decision",
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
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)


def main(argv: list[str] | None = None) -> int:
    """Run the requested setup stage and return a machine-meaningful exit code."""
    args = _parser().parse_args(argv)
    mode: ProofMode = args.mode
    destination = args.json_report or args.output_dir / "real-pgdp-review-proof.json"
    invocation_args = sys.argv[1:] if argv is None else argv
    invocation = shlex.join([sys.argv[0], *invocation_args])
    if mode == "validate-ocr" and args.ocr_root is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "cached_ocr_required",
                        "message": "--mode validate-ocr requires an explicit --ocr-root",
                    },
                }
            )
        )
        return 2
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
            report["integration"]["status"] = "public_workflow_running"
            _write_report(report, destination)
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
            populate_proof_evidence(
                report=report, cases=cases, operations=report["public_operations"]
            )
            populate_behavior_summary(report)
            report["integration"]["status"] = "public_workflow_evidence_collected"
            _write_report(report, destination)
            evidence_complete = all(
                case_report["proof_evidence"]["status"] == "verified"
                for case_report in report["cases"]
            )
            if (
                public_proof_complete(cases=cases, operations=report["public_operations"])
                and evidence_complete
            ):
                report["integration"]["status"] = "public_workflow_complete"
                report["integration"]["requirements"] = []
                _write_report(report, destination)
                print(
                    json.dumps(
                        {"ok": True, "report": str(destination), "summary": report["summary"]}
                    )
                )
                return 0
            report["integration"]["status"] = "public_workflow_incomplete"
            report["integration"]["requirements"] = [
                case_report["project_id"] + "/" + case_report["page_key"]
                for case_report in report["cases"]
                if case_report["proof_evidence"]["status"] != "verified"
            ]
            _write_report(report, destination)
            reason = "required public stages or persistence invariants are incomplete"
        else:
            reason = f"missing required public-interface configuration: {', '.join(missing_configuration)}"
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
