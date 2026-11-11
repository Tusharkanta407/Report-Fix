import json

import pytest

from engine.content_checks import inspect_question
from engine.ingestion import DataError, load_dataset


def test_counts_match_data(dataset):
    assert len(dataset.reports) == 44
    assert len(dataset.payloads) == 43
    assert len(dataset.reported_question_ids) == 39
    assert len(dataset.unreported_question_ids) == 4
    assert dataset.missing_question_reports == []


def test_r005_payload_surfaces_stored_key_for_investigation(dataset):
    report = next(r for r in dataset.reports if r.reportId == "R005")
    payload = dataset.payloads[report.questionId]
    assert payload.question_type == "integerQuestion"
    assert payload.answer_raw == "2"
    assert "(q)/(2ε_(0))" in payload.solution_text


def test_duplicate_reports_grouped_on_one_question(dataset):
    group = dataset.groups["60f744b3f1b9bc7cc7b4a949"]
    assert sorted(r.reportId for r in group) == ["R001", "R002", "R003"]
    sib = dataset.siblings(group[0])
    assert len(sib) == 2


def test_typed_payload_for_mcq_keeps_raw_list(dataset):
    p = dataset.payloads["68c8153cfb6b2f16e2d3ceaf"]
    assert p.answer_raw == ["A, B, D"]
    assert p.answer_normalized == "A,B,D"


def test_content_checks_find_known_structural_defects(dataset):
    assert inspect_question(dataset.payloads["622f08d7b70e4b50e4500a1b"]).missing_option_letters == ["D"]
    assert inspect_question(dataset.payloads["68e872546e45ba37dcc16bc0"]).blank_option_letters == ["C"]
    assert inspect_question(dataset.payloads["6956d79788d7701e5617bc29"]).duplicate_option_groups == [["B", "C"]]
    assert inspect_question(dataset.payloads["617fa18efd53ff1629ed890f"]).exam_references
    assert "\\frac" in inspect_question(dataset.payloads["63765a28f1d8416ae0408d89"]).latex_leaks


def test_missing_question_is_recorded_not_invented(tmp_path, dataset):
    (tmp_path / "taxonomy.json").write_text(json.dumps(dataset.taxonomy), encoding="utf-8")
    (tmp_path / "questions.json").write_text("[]", encoding="utf-8")
    (tmp_path / "reports.json").write_text(
        json.dumps([{"reportId": "RX", "questionId": "nope", "studentId": "s", "comment": "wrong"}]),
        encoding="utf-8",
    )
    ds = load_dataset(tmp_path)
    assert ds.missing_question_reports == ["RX"]
    assert "nope" not in ds.payloads


def test_duplicate_report_ids_rejected(tmp_path, dataset):
    (tmp_path / "taxonomy.json").write_text(json.dumps(dataset.taxonomy), encoding="utf-8")
    (tmp_path / "questions.json").write_text("[]", encoding="utf-8")
    dup = {"reportId": "R1", "questionId": "q", "studentId": "s", "comment": ""}
    (tmp_path / "reports.json").write_text(json.dumps([dup, dup]), encoding="utf-8")
    with pytest.raises(DataError):
        load_dataset(tmp_path)
