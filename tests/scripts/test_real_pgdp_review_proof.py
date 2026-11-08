"""Tests for the bounded real-PGDP proof harness setup stages."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from scripts import real_pgdp_review_proof as proof
from scripts.real_pgdp_review_proof import (
    CaseListError,
    OcrTsvError,
    build_setup_report,
    load_cases,
    main,
    parse_ocr_tsv,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_load_cases_reads_tab_separated_three_column_selection(tmp_path: Path) -> None:
    cases_file = tmp_path / "cases.tsv"
    cases_file.write_text(
        "projectIDone\t008.png\tverse_indent\nprojectIDtwo\t07.png\tnumeric_tables\n",
        encoding="utf-8",
    )

    cases = load_cases(cases_file, case_limit=None, allow_partial=False)

    assert [(case.project_id, case.page_key, case.intent) for case in cases] == [
        ("projectIDone", "008.png", "verse_indent"),
        ("projectIDtwo", "07.png", "numeric_tables"),
    ]


def test_load_cases_rejects_implicit_partial_selection(tmp_path: Path) -> None:
    cases_file = tmp_path / "cases.tsv"
    cases_file.write_text(
        "projectIDone\t008.png\tverse_indent\nprojectIDtwo\t07.png\tnumeric_tables\n",
        encoding="utf-8",
    )

    with pytest.raises(CaseListError, match="allow-partial"):
        load_cases(cases_file, case_limit=1, allow_partial=False)


def test_parse_ocr_tsv_counts_only_nonempty_word_rows(tmp_path: Path) -> None:
    ocr_file = tmp_path / "sample.tsv"
    ocr_file.write_text(
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "4\t1\t1\t1\t1\t0\t0\t0\t0\t0\t-1\t\n"
        "5\t1\t1\t1\t1\t1\t0\t0\t0\t0\t99\tAlpha\n"
        "5\t1\t1\t1\t1\t2\t0\t0\t0\t0\t99\t \n"
        "5\t1\t1\t1\t1\t3\t0\t0\t0\t0\t99\tBeta\n",
        encoding="utf-8",
    )

    assert parse_ocr_tsv(ocr_file) == 2


def test_parse_ocr_tsv_rejects_a_non_tesseract_header(tmp_path: Path) -> None:
    ocr_file = tmp_path / "invalid.tsv"
    ocr_file.write_text("word\nAlpha\n", encoding="utf-8")

    with pytest.raises(OcrTsvError, match="Tesseract TSV header"):
        parse_ocr_tsv(ocr_file)


def test_build_setup_report_preserves_failed_case_and_real_counts(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    project_root = corpus_root / "projectIDone"
    rounds_root = project_root / "rounds"
    rounds_root.mkdir(parents=True)
    (project_root / "008.png").write_bytes(b"real-scan-placeholder")
    (rounds_root / "F2.json").write_text(
        json.dumps({"008.png": "/*\nA visible F2 line\n*/"}), encoding="utf-8"
    )
    (rounds_root / "P3.json").write_text(json.dumps({"008.png": "A P3 line"}), encoding="utf-8")
    ocr_root = tmp_path / "ocr"
    ocr_root.mkdir()
    (ocr_root / "projectIDone-008.png.tsv").write_text(
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t0\t0\t0\t0\t99\tA\n",
        encoding="utf-8",
    )
    cases_file = tmp_path / "cases.tsv"
    cases_file.write_text("projectIDone\t008.png\tverse_indent\n", encoding="utf-8")

    report = build_setup_report(
        cases=load_cases(cases_file, case_limit=None, allow_partial=False),
        corpus_root=corpus_root,
        ocr_root=ocr_root,
        mode="validate-ocr",
        cases_path=cases_file,
        invocation="real_pgdp_review_proof.py --mode validate-ocr",
    )

    assert report["summary"]["case_count"] == 1
    assert report["summary"]["requested_case_count"] == 1
    assert report["summary"]["complete_selection"] is True
    case = report["cases"][0]
    assert case["status"] == "setup_ready"
    assert case["word_counts"] == {"f2_raw": 4, "p3": 3, "ocr": 1}
    assert case["metrics"]["p3_to_ocr_mapped"] is None
    assert any("source preparation CLI" in blocker for blocker in case["blockers"])
    assert report["input_identities"]["cases_tsv"]["path"] == str(cases_file)
    assert report["commands"]["invocation"] == "real_pgdp_review_proof.py --mode validate-ocr"


def test_proof_mode_returns_one_blocked_machine_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cases_file = tmp_path / "cases.tsv"
    cases_file.write_text("projectIDone\t008.png\tverse_indent\n", encoding="utf-8")
    report_path = tmp_path / "proof.json"

    exit_code = main(
        [
            "--mode",
            "proof",
            "--cases",
            str(cases_file),
            "--corpus-root",
            str(tmp_path / "missing-corpus"),
            "--ocr-root",
            str(tmp_path / "missing-ocr"),
            "--json-report",
            str(report_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert payload["ok"] is False
    assert payload["error"]["code"] == "dependencies_unavailable"
    assert payload["report"] == str(report_path)


def test_public_proof_sequences_each_page_without_inventing_review_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[tuple[str, ...], dict[str, object] | None]] = []

    def run_command(
        argv: tuple[str, ...], *, request: dict[str, object] | None, timeout_seconds: float
    ) -> proof.PublicOperation:
        del timeout_seconds
        calls.append((argv, request))
        if request is not None and request["command"] == "prepare":
            payload: dict[str, object] = {
                "ok": True,
                "result": {"book_path": "/prepared/projectIDone"},
            }
        elif "load" in argv:
            payload = {"project": {"project_id": "labeler-project"}}
        elif "page" in argv:
            payload = {"generation": 7}
        else:
            payload = {"ok": True}
        return {
            "subject": "",
            "stage": "",
            "argv": list(argv),
            "status": "ok",
            "payload": payload,
            "error": None,
        }

    monkeypatch.setattr(proof, "_run_json_command", run_command)
    operations = proof.run_public_proof(
        cases=[
            proof.ProofCase("projectIDone", "008.png", "verse_indent"),
            proof.ProofCase("projectIDone", "009.png", "verse_stanzas_case"),
        ],
        corpus_root=tmp_path / "corpus",
        source_python=tmp_path / "python",
        source_module="pdomain_source_data.pgdp_review_cli",
        source_output_root=tmp_path / "prepared",
        labeler_control=tmp_path / "control",
        labeler_base_url="http://127.0.0.1:8000",
        timeout_seconds=10.0,
    )

    assert sum(operation["stage"] == "labeler_ocr" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_page_after_ocr" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_align" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_export" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_review_group" for operation in operations) == 2
    assert all(
        operation["status"] == "blocked"
        for operation in operations
        if operation["stage"] == "labeler_review_group"
    )
    align_commands = [
        operation["argv"] for operation in operations if operation["stage"] == "labeler_align"
    ]
    assert all("--generation" in command and "7" in command for command in align_commands)
    prepare_requests = [
        request for _, request in calls if request is not None and request["command"] == "prepare"
    ]
    assert prepare_requests == [
        {
            "command": "prepare",
            "corpus_root": str(tmp_path / "corpus"),
            "project_id": "projectIDone",
            "page_keys": ["008.png", "009.png"],
            "output_root": str(tmp_path / "prepared"),
        }
    ]
