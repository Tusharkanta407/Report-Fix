"""Deterministic fast-path: spelling / exam tags / injection skip academic solve."""

from engine.cache import SolveCache
from engine.content_checks import inspect_question
from engine.fast_path import needs_academic_solve, try_deterministic_proposal
from engine.normalizer import normalize_comment
from engine.orchestrator import run_pipeline
from engine.schemas import Interpretation, Proposal, ReplyDraft, SolutionReading, SolverResult
from engine.token_meter import CallRecord, TokenMeter
from tests.test_orchestrator import FakeClient


def test_exam_tag_report_is_deterministic(dataset):
    report = next(r for r in dataset.reports if r.reportId == "R013")
    payload = dataset.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    checks = inspect_question(payload)
    assert "exam_reference" in hints.intent_hints
    assert "answer_key" not in hints.intent_hints
    prop = try_deterministic_proposal(hints, checks, payload)
    assert prop is not None
    assert prop.repair == "exam_reference"
    assert prop.edit is not None
    assert "NEET 2019" in prop.edit.find
    assert prop.edit.replace == ""
    assert "deterministic" in prop.evidence.lower() or "exam tag" in prop.evidence.lower()


def test_spelling_reports_are_deterministic(dataset):
    for rid, find in (("R012", "Epithellial tisue"), ("R022", "Choroid plexux")):
        report = next(r for r in dataset.reports if r.reportId == rid)
        payload = dataset.payloads[report.questionId]
        prop = try_deterministic_proposal(
            normalize_comment(report.comment, payload), inspect_question(payload), payload
        )
        assert prop is not None
        assert prop.repair == "spelling"
        assert prop.edit is not None
        assert prop.edit.find == find


def test_injection_is_dismissed_without_solve(dataset):
    report = next(r for r in dataset.reports if r.reportId == "R027")
    payload = dataset.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    assert hints.injection_flags
    prop = try_deterministic_proposal(hints, inspect_question(payload), payload)
    assert prop is not None
    assert prop.verdict == "no_error"
    assert prop.repair is None
    assert needs_academic_solve([hints]) is False


def test_already_fixed_spelling_quote(dataset):
    report = next(r for r in dataset.reports if r.reportId == "R017")
    payload = dataset.payloads[report.questionId]
    prop = try_deterministic_proposal(
        normalize_comment(report.comment, payload), inspect_question(payload), payload
    )
    assert prop is not None
    assert prop.verdict == "already_fixed"


def test_pipeline_skips_solver_for_exam_tag(dataset, tmp_path):
    client = FakeClient()
    out = run_pipeline(
        dataset, client, SolveCache(tmp_path), report_ids=["R013"], log=lambda *_: None
    )
    assert not [c for c in client.calls if c[0] in ("solver", "solution_reader", "interpreter", "comparator")]
    r = out.results[0]
    assert r.reportId == "R013"
    assert r.repair == "exam_reference"
    assert r.route == "auto_apply"
    assert out.cases[0]["fast_path"] is True


def test_pipeline_still_solves_answer_key(dataset, tmp_path):
    client = FakeClient()
    out = run_pipeline(
        dataset, client, SolveCache(tmp_path), report_ids=["R001"], log=lambda *_: None
    )
    assert [c for c in client.calls if c[0] == "solver"]
    assert out.results[0].repair == "answer_key"


def test_chapter_report_skips_solver(dataset, tmp_path):
    """R042: 'chapter is wrong…' must NOT burn a physics solve or flip the key."""
    report = next(r for r in dataset.reports if r.reportId == "R042")
    payload = dataset.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    assert "wrong_chapter" in hints.intent_hints
    assert needs_academic_solve([hints]) is False
    prop = try_deterministic_proposal(hints, inspect_question(payload), payload)
    assert prop is not None
    assert prop.repair == "wrong_chapter"
    assert prop.edit is None

    client = FakeClient()
    out = run_pipeline(
        dataset, client, SolveCache(tmp_path), report_ids=["R042"], log=lambda *_: None
    )
    assert not [c for c in client.calls if c[0] in ("solver", "solution_reader", "comparator")]
    r = out.results[0]
    assert r.repair == "wrong_chapter"
    assert r.edit is None
    assert r.route == "faculty_review"
    assert out.cases[0]["fast_path"] is True
