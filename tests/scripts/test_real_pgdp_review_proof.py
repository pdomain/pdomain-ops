"""Tests for the bounded real-PGDP proof harness setup stages."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

import pytest

from scripts import real_pgdp_review_proof as proof
from scripts.real_pgdp_review_proof import (
    DEFAULT_CASES_PATH,
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


def test_default_cases_fixture_does_not_depend_on_the_current_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    parsed = proof._parser().parse_args([])

    assert parsed.cases == DEFAULT_CASES_PATH
    assert load_cases(parsed.cases, case_limit=None, allow_partial=False)


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


def test_proof_setup_keeps_native_ocr_primary_when_cache_is_not_requested(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    project_root = corpus_root / "projectIDone"
    rounds_root = project_root / "rounds"
    rounds_root.mkdir(parents=True)
    (project_root / "008.png").write_bytes(b"real-scan-placeholder")
    (rounds_root / "F2.json").write_text(json.dumps({"008.png": "F2 source"}), encoding="utf-8")
    (rounds_root / "P3.json").write_text(json.dumps({"008.png": "P3 source"}), encoding="utf-8")
    cases_file = tmp_path / "cases.tsv"
    cases_file.write_text("projectIDone\t008.png\tverse_indent\n", encoding="utf-8")

    report = build_setup_report(
        cases=load_cases(cases_file, case_limit=None, allow_partial=False),
        corpus_root=corpus_root,
        ocr_root=None,
        mode="proof",
        cases_path=cases_file,
    )

    assert report["summary"]["setup_failed_count"] == 0
    assert report["input_sources"]["ocr_root"] == "not requested; native labeler OCR is primary"
    assert report["cases"][0]["cached_ocr_validation"] == "not_requested"
    assert report["cases"][0]["word_counts"]["ocr"] is None


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


def test_validate_ocr_requires_an_explicit_cache_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["--mode", "validate-ocr", "--json-report", str(tmp_path / "report.json")])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["code"] == "cached_ocr_required"


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
        elif "inspect" in argv:
            payload = {
                "generation": 7,
                "result": {
                    "result_id": "result-1",
                    "groups": [{"group_id": "group-1", "ocr_text": "Alpha"}],
                },
            }
        elif "proposals" in argv:
            payload = {"proposals": [{"proposal_id": "proposal-1", "role": "paragraph"}]}
        elif "region-review" in argv:
            payload = {"generation": 8}
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
        review_decision="pending",
    )

    assert sum(operation["stage"] == "labeler_ocr" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_page_after_ocr" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_align" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_export" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_review_group" for operation in operations) == 2
    assert all(
        operation["status"] == "ok"
        for operation in operations
        if operation["stage"] == "labeler_review_group"
    )
    align_commands = [
        operation["argv"] for operation in operations if operation["stage"] == "labeler_align"
    ]
    assert all("--generation" in command and "7" in command for command in align_commands)
    assert sum(operation["stage"] == "labeler_proposals" for operation in operations) == 2
    assert sum(operation["stage"] == "labeler_region_review" for operation in operations) == 2
    assert (
        sum(operation["stage"] == "labeler_save_after_region_review" for operation in operations)
        == 2
    )
    assert all(
        operation["status"] == "ok"
        for operation in operations
        if operation["stage"] == "labeler_save_after_region_review"
    )
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


def test_public_proof_confirms_working_copy_page_kinds_before_proposals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requests: list[tuple[str, ...]] = []

    def run_command(
        argv: tuple[str, ...], *, request: dict[str, object] | None, timeout_seconds: float
    ) -> proof.PublicOperation:
        del request, timeout_seconds
        requests.append(argv)
        payload: dict[str, object] = {"ok": True, "result": {"book_path": "/prepared/book"}}
        if "load" in argv:
            payload = {"project": {"project_id": "labeler-project"}}
        elif "page" in argv:
            payload = {"generation": 7}
        elif "inspect" in argv:
            payload = {
                "generation": 7,
                "result": {
                    "result_id": "result-1",
                    "groups": [{"group_id": "group-1", "ocr_text": "Alpha"}],
                },
            }
        return {
            "subject": "",
            "stage": "",
            "argv": list(argv),
            "status": "ok",
            "payload": payload,
            "error": None,
        }

    monkeypatch.setattr(proof, "_run_json_command", run_command)
    proof.run_public_proof(
        cases=[proof.ProofCase("projectID68658d72319cb", "03.png", "contents_leaders")],
        corpus_root=tmp_path / "corpus",
        source_python=tmp_path / "python",
        source_module="pdomain_source_data.pgdp_review_cli",
        source_output_root=tmp_path / "prepared",
        labeler_control=tmp_path / "control",
        labeler_base_url="http://127.0.0.1:8000",
        timeout_seconds=10.0,
        review_decision="edited",
    )

    confirmation = next(
        argv for argv in requests if any("/page-kinds/confirm" in arg for arg in argv)
    )
    body = json.loads(confirmation[confirmation.index("--json") + 1])
    assert body == {
        "pages": [{"page_index": 0, "kind": "contents"}],
        "note": "Algorithm review for real PGDP proof working copy",
    }


def test_public_proof_reviews_both_members_of_a_structured_column_pair(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requests: list[tuple[str, ...]] = []

    def run_command(
        argv: tuple[str, ...], *, request: dict[str, object] | None, timeout_seconds: float
    ) -> proof.PublicOperation:
        del request, timeout_seconds
        requests.append(argv)
        payload: dict[str, object] = {"ok": True, "result": {"book_path": "/prepared/book"}}
        if "load" in argv:
            payload = {"project": {"project_id": "labeler-project"}}
        elif "page" in argv:
            payload = {"generation": 7}
        elif "inspect" in argv:
            payload = {
                "generation": 7,
                "result": {
                    "result_id": "result-1",
                    "groups": [{"group_id": "group-1", "ocr_text": "Alpha"}],
                },
            }
        elif "proposals" in argv:
            payload = {
                "proposals": [
                    {"proposal_id": "plain-proposal", "role": "paragraph"},
                    {
                        "proposal_id": "column-proposal-0",
                        "role": "paragraph",
                        "evidence": {
                            "layout_structure": {
                                "kind": "column_flow",
                                "column_group_id": "columns-1",
                                "column_index": 0,
                                "reading_order": 0,
                            }
                        },
                    },
                    {
                        "proposal_id": "column-proposal-1",
                        "role": "paragraph",
                        "evidence": {
                            "layout_structure": {
                                "kind": "column_flow",
                                "column_group_id": "columns-1",
                                "column_index": 1,
                                "reading_order": 1,
                            }
                        },
                    },
                ]
            }
        elif "region-review" in argv:
            payload = {"generation": 8}
        return {
            "subject": "",
            "stage": "",
            "argv": list(argv),
            "status": "ok",
            "payload": payload,
            "error": None,
        }

    monkeypatch.setattr(proof, "_run_json_command", run_command)
    proof.run_public_proof(
        cases=[proof.ProofCase("projectIDone", "020.png", "physical_columns_captions")],
        corpus_root=tmp_path / "corpus",
        source_python=tmp_path / "python",
        source_module="pdomain_source_data.pgdp_review_cli",
        source_output_root=tmp_path / "prepared",
        labeler_control=tmp_path / "control",
        labeler_base_url="http://127.0.0.1:8000",
        timeout_seconds=10.0,
        review_decision="edited",
    )

    region_reviews = [argv for argv in requests if "region-review" in argv]
    assert len(region_reviews) == 2
    assert {argv[argv.index("region-review") + 3] for argv in region_reviews} == {
        "column-proposal-0",
        "column-proposal-1",
    }
    bodies = [json.loads(argv[argv.index("--json") + 1]) for argv in region_reviews]
    assert sorted(body["layout_structure"]["column_index"] for body in bodies) == [0, 1]


def test_region_review_structure_evidence_requires_a_matching_reloaded_region() -> None:
    operation: proof.PublicOperation = {
        "subject": "project/008.png",
        "stage": "labeler_region_review",
        "argv": [
            "control",
            "region-review",
            "labeler-project",
            "0",
            "proposal-1",
            "accept",
            "--json",
            '{"layout_structure":{"kind":"poetry","lines":[]}}',
        ],
        "status": "ok",
        "payload": {
            "regions": [
                {
                    "proposal_id": "proposal-1",
                    "layout_structure": {"kind": "poetry"},
                }
            ]
        },
        "error": None,
    }

    proposal_id, requested_kind = proof._region_review_request(operation)

    assert (proposal_id, requested_kind) == ("proposal-1", "poetry")
    assert proof._region_structure_kind(operation, proposal_id) == "poetry"
    assert (
        proof._region_structure_kind_for_proposal(
            {"regions": [{"proposal_id": "proposal-1", "layout_structure": {"kind": "poetry"}}]},
            proposal_id,
        )
        == "poetry"
    )


def test_one_column_only_makes_physical_column_proof_incomplete(tmp_path: Path) -> None:
    case = proof.ProofCase("project", "020.png", "physical_columns_captions")
    report = build_setup_report(
        cases=[case],
        corpus_root=tmp_path / "corpus",
        ocr_root=None,
        mode="proof",
    )
    subject = "project/020.png"
    before_group = {
        "group_id": "group-1",
        "ocr_text": "Alpha",
        "box": {"x": 1},
        "source_word_ids": ["source-1"],
        "note": "",
        "reviewed_text": None,
    }
    after_group = {**before_group, "note": f"real-proof:{subject}", "reviewed_text": "Alpha"}
    operations: list[proof.PublicOperation] = [
        {
            "subject": subject,
            "stage": "labeler_page_after_ocr",
            "argv": [],
            "status": "ok",
            "payload": {"page_text_ocr": "Alpha", "page_text_gt": "Alpha"},
            "error": None,
        },
        {
            "subject": subject,
            "stage": "labeler_inspect",
            "argv": [],
            "status": "ok",
            "payload": {"result": {"groups": [before_group]}},
            "error": None,
        },
        {
            "subject": subject,
            "stage": "labeler_inspect_after_reload",
            "argv": [],
            "status": "ok",
            "payload": {"result": {"groups": [after_group]}},
            "error": None,
        },
        {
            "subject": subject,
            "stage": "labeler_proposals",
            "argv": [],
            "status": "ok",
            "payload": {"proposals": [{"proposal_id": "column-0", "role": "paragraph"}]},
            "error": None,
        },
        {
            "subject": subject,
            "stage": "labeler_page_after_region_review",
            "argv": [],
            "status": "ok",
            "payload": {
                "page_text_ocr": "Alpha",
                "page_text_gt": "Alpha",
                "regions": [
                    {
                        "confirmed": True,
                        "role": "paragraph",
                        "layout_structure": {
                            "kind": "column_flow",
                            "column_group_id": "columns-1",
                            "column_index": 0,
                        },
                    }
                ],
            },
            "error": None,
        },
    ]

    proof.populate_proof_evidence(report=report, cases=[case], operations=operations)

    evidence = report["cases"][0]["proof_evidence"]
    assert evidence["behavior_observations"]["independent_columns"] == "genuine_mismatch"
    assert evidence["status"] == "invariants_incomplete"


def test_changed_public_ocr_word_snapshot_makes_proof_incomplete(tmp_path: Path) -> None:
    case = proof.ProofCase("project", "plain.png", "ordinary")
    report = build_setup_report(
        cases=[case],
        corpus_root=tmp_path / "corpus",
        ocr_root=None,
        mode="proof",
    )
    subject = "project/plain.png"
    before_word = {
        "word_index": 0,
        "ocr_text": "Alpha",
        "word_id": "word-1",
        "bbox": {"x": 1, "y": 2, "width": 3, "height": 4},
    }
    after_word = {**before_word, "bbox": {"x": 2, "y": 2, "width": 3, "height": 4}}
    before_group = {
        "group_id": "group-1",
        "ocr_text": "Alpha",
        "box": {"x": 1},
        "source_word_ids": ["source-1"],
        "note": "",
        "reviewed_text": None,
    }
    after_group = {**before_group, "note": f"real-proof:{subject}", "reviewed_text": "Alpha"}
    operations: list[proof.PublicOperation] = [
        {
            "subject": subject,
            "stage": "labeler_page_after_ocr",
            "argv": [],
            "status": "ok",
            "payload": {
                "page_text_ocr": "Alpha",
                "page_text_gt": "Alpha",
                "line_matches": [{"line_index": 0, "word_matches": [before_word]}],
            },
            "error": None,
        },
        {
            "subject": subject,
            "stage": "labeler_inspect",
            "argv": [],
            "status": "ok",
            "payload": {"result": {"groups": [before_group], "ocr": {"ocr_words": [{}]}}},
            "error": None,
        },
        {
            "subject": subject,
            "stage": "labeler_inspect_after_reload",
            "argv": [],
            "status": "ok",
            "payload": {"result": {"groups": [after_group]}},
            "error": None,
        },
        {
            "subject": subject,
            "stage": "labeler_proposals",
            "argv": [],
            "status": "ok",
            "payload": {"proposals": []},
            "error": None,
        },
        {
            "subject": subject,
            "stage": "labeler_page_after_region_review",
            "argv": [],
            "status": "ok",
            "payload": {
                "page_text_ocr": "Alpha",
                "page_text_gt": "Alpha",
                "line_matches": [{"line_index": 0, "word_matches": [after_word]}],
                "regions": [],
            },
            "error": None,
        },
    ]

    proof.populate_proof_evidence(report=report, cases=[case], operations=operations)

    evidence = report["cases"][0]["proof_evidence"]
    assert evidence["raw_ocr_token_count"] == 1
    assert "alignment_group_order_boxes_source_ids_preserved" in evidence["invariants"]
    assert "raw_ocr_word_order_ids_boxes_preserved" not in evidence["invariants"]
    assert evidence["status"] == "invariants_incomplete"


def test_job_elapsed_ms_uses_public_job_timestamps() -> None:
    operation: proof.PublicOperation = {
        "subject": "project/plain.png",
        "stage": "labeler_align",
        "argv": [],
        "status": "ok",
        "payload": {
            "created_at": "2026-11-08T12:00:00.000000Z",
            "updated_at": "2026-11-08T12:00:01.250000Z",
        },
        "error": None,
    }

    assert proof._job_elapsed_ms(operation) == 1250


def test_malformed_public_ocr_word_snapshot_is_unavailable() -> None:
    snapshot = proof._page_ocr_word_snapshot(
        {"line_matches": [{"line_index": 0, "word_matches": [{"ocr_text": "Alpha"}]}]}
    )

    assert snapshot is None


def test_public_proof_does_not_propose_regions_after_page_kind_confirmation_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def run_command(
        argv: tuple[str, ...], *, request: dict[str, object] | None, timeout_seconds: float
    ) -> proof.PublicOperation:
        del request, timeout_seconds
        payload: dict[str, object] = {"ok": True, "result": {"book_path": "/prepared/book"}}
        status: Literal["ok", "error", "blocked"] = "ok"
        if "load" in argv:
            payload = {"project": {"project_id": "labeler-project"}}
        elif any("/page-kinds/confirm" in arg for arg in argv):
            status = "error"
            payload = {"error": "confirmation_failed"}
        elif "page" in argv:
            payload = {"generation": 7}
        elif "inspect" in argv:
            payload = {
                "generation": 7,
                "result": {
                    "result_id": "result-1",
                    "groups": [{"group_id": "group-1", "ocr_text": "Alpha"}],
                },
            }
        return {
            "subject": "",
            "stage": "",
            "argv": list(argv),
            "status": status,
            "payload": payload,
            "error": None,
        }

    monkeypatch.setattr(proof, "_run_json_command", run_command)
    operations = proof.run_public_proof(
        cases=[proof.ProofCase("projectIDone", "008.png", "verse_indent")],
        corpus_root=tmp_path / "corpus",
        source_python=tmp_path / "python",
        source_module="pdomain_source_data.pgdp_review_cli",
        source_output_root=tmp_path / "prepared",
        labeler_control=tmp_path / "control",
        labeler_base_url="http://127.0.0.1:8000",
        timeout_seconds=10.0,
        review_decision="edited",
    )

    proposal = next(
        operation for operation in operations if operation["stage"] == "labeler_propose"
    )
    assert proposal["status"] == "blocked"
    assert not any(operation["stage"] == "labeler_proposals" for operation in operations)


def test_public_proof_rejects_an_empty_all_pass_operation_list() -> None:
    assert proof.public_proof_complete(cases=[], operations=[]) is False


def test_semantic_observations_do_not_pass_empty_or_null_evidence() -> None:
    numeric = proof._behavior_observations(
        proof.ProofCase("project", "07.png", "numeric_tables"),
        {"layout_hints": [{"kind": "poetry"}], "regions": []},
        None,
        {"proposals": []},
    )
    formatter = proof._behavior_observations(
        proof.ProofCase("project", "026.png", "formatter_comments_tb"),
        {"page_text_ocr": "plain scan"},
        {
            "result": {
                "f2": {
                    "visible_text": "source <tb> marker",
                    "document": {"pages": []},
                }
            }
        },
        {"proposals": [{"role": "paragraph"}]},
    )
    verse = proof._behavior_observations(
        proof.ProofCase("project", "009.png", "verse_stanzas_case"),
        {
            "layout_hints": [{"lines": [{"stanza_index": None, "indent_hint": None}]}],
            "regions": [],
        },
        {"result": {"projection": {"unresolved": ["missing"]}}},
        {"proposals": [{"role": "poetry", "evidence": {"alignment_group_ids": []}}]},
    )
    quote_false_positive = proof._behavior_observations(
        proof.ProofCase("project", "081.png", "quote_footnote"),
        None,
        None,
        {
            "proposals": [
                {
                    "role": "paragraph",
                    "evidence": {"layout_structure": {"kind": "column_flow"}},
                }
            ]
        },
    )
    quote_continuation = proof._behavior_observations(
        proof.ProofCase("project", "082.png", "quote_continuation"),
        None,
        None,
        {
            "proposals": [
                {
                    "role": "blockquote",
                    "evidence": {
                        "layout_structure": {"kind": "blockquote"},
                        "layout_hints": [
                            {
                                "kind": "blockquote",
                                "source": "f2",
                                "source_ref": "source/F2.json",
                            }
                        ],
                    },
                }
            ]
        },
    )
    quote_missing_source_metadata = proof._behavior_observations(
        proof.ProofCase("project", "082.png", "quote_continuation"),
        None,
        None,
        {
            "proposals": [
                {
                    "role": "blockquote",
                    "evidence": {
                        "layout_structure": {"kind": "blockquote"},
                        "layout_hints": [{"kind": "blockquote", "source": "f2"}],
                    },
                }
            ]
        },
    )
    quote_wrong_hint_kind = proof._behavior_observations(
        proof.ProofCase("project", "082.png", "quote_continuation"),
        None,
        None,
        {
            "proposals": [
                {
                    "role": "blockquote",
                    "evidence": {
                        "layout_structure": {"kind": "blockquote"},
                        "layout_hints": [
                            {
                                "kind": "paragraph",
                                "source": "f2",
                                "source_ref": "source/F2.json",
                            }
                        ],
                    },
                }
            ]
        },
    )

    assert numeric["not_poetry"] == "missing_proposal"
    assert formatter["formatter_or_tb_visible"] == "mismatch"
    assert verse["verse_stanzas_or_indents"] == "partial_unresolved"
    assert quote_false_positive["quote_columns_abstained"] == "genuine_mismatch"
    assert quote_continuation == {
        "quote_columns_abstained": "verified",
        "blockquote_source_metadata": "verified",
    }
    assert quote_missing_source_metadata["blockquote_source_metadata"] == "genuine_mismatch"
    assert quote_wrong_hint_kind["blockquote_source_metadata"] == "genuine_mismatch"
    assert proof._behavior_observations_complete(numeric) is False
    assert proof._behavior_observations_complete(formatter) is False
    assert proof._behavior_observations_complete(verse) is True
    assert proof._behavior_observations_complete(quote_false_positive) is False


def test_alignment_metrics_count_changed_groups_and_linked_relations() -> None:
    metrics: proof.AlignmentMetrics = {
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
    }
    payload: dict[str, object] = {
        "result": {
            "groups": [
                {"disposition": "accepted"},
                {"disposition": "changed"},
                {"disposition": "changed"},
            ],
            "ocr": {"ocr_words": [{}, {}, {}, {}, {}]},
            "alignment": {
                "warnings": ["boilerplate"],
                "f2_to_p3": {
                    "best_alternative": {
                        "relations": [
                            {"source_token_ids": ["f2"], "target_token_ids": ["p3"]},
                            {"source_token_ids": ["f2"], "target_token_ids": []},
                        ]
                    }
                },
                "p3_to_ocr": {"best_alternative": {"relations": []}},
            },
            "projection": {"layout_hints": [], "style_spans": [], "unresolved": []},
        }
    }

    proof._populate_metrics(metrics, payload)

    assert metrics["disagreements"] == 2
    assert metrics["f2_to_p3_mapped"] == 1
    assert metrics["ocr_token_count"] == 5
