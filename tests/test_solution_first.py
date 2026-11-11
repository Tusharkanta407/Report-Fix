"""Solution-first short-circuit: solution matches key vs student claim → no_error."""

from engine.ingestion import load_dataset
from engine.normalizer import normalize_comment
from engine.schemas import Interpretation, SolutionReading, SolverResult
from engine.solution_first import try_solution_first_no_error


def _interp(claimed: str, category: str = "answer_key") -> Interpretation:
    return Interpretation(
        claim_summary=f"says answer should be {claimed}",
        claimed_answer=claimed,
        category=category,
        target="answer",
        injection_attempt=False,
        comment_language="English",
    )


def _reading(answer: str) -> SolutionReading:
    return SolutionReading(
        solution_present=True,
        matches_question=True,
        solution_final_answer=answer,
        confidence=0.9,
    )


def _solver(answer: str) -> SolverResult:
    return SolverResult(
        can_solve=True,
        final_answer=answer,
        correct_options=[answer],
        working="w",
        confidence=0.95,
        missing_information=[],
        figure_required=False,
        observations=[],
    )


def test_sigfig_3112_vs_3113_solution_first():
    ds = load_dataset("data")
    report = next(r for r in ds.reports if r.reportId == "R033")
    payload = ds.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    prop = try_solution_first_no_error(
        interpretation=_interp("3112.99"),
        hints=hints,
        payload=payload,
        solver=_solver("3113"),
        reading=_reading("3113"),
    )
    assert prop is not None
    assert prop.verdict == "no_error"
    assert prop.repair is None
    assert "3113" in prop.evidence or "integer" in prop.evidence.lower() or "solution-first" in prop.evidence.lower()


def test_amplitude_student_b_when_solution_says_d():
    ds = load_dataset("data")
    report = next(r for r in ds.reports if r.reportId == "R030")
    payload = ds.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    prop = try_solution_first_no_error(
        interpretation=_interp("B"),
        hints=hints,
        payload=payload,
        solver=_solver("D"),
        reading=_reading("D"),
    )
    assert prop is not None
    assert prop.verdict == "no_error"
    assert prop.edit is None


def test_real_key_defect_not_short_circuited():
    """LCR: solution/solve say A, key is C — must NOT force no_error."""
    ds = load_dataset("data")
    report = next(r for r in ds.reports if r.reportId == "R001")
    payload = ds.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    prop = try_solution_first_no_error(
        interpretation=_interp("A"),
        hints=hints,
        payload=payload,
        solver=_solver("A"),
        reading=_reading("A"),
    )
    assert prop is None


def test_flux_n1_vs_key2_not_sigfig_false_positive():
    """R005: student/solver say 1, key 2 — must NOT treat as rounding noise."""
    ds = load_dataset("data")
    report = next(r for r in ds.reports if r.reportId == "R005")
    payload = ds.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    prop = try_solution_first_no_error(
        interpretation=_interp("1"),
        hints=hints,
        payload=payload,
        solver=_solver("1"),
        reading=_reading("2"),
    )
    assert prop is None


def test_unit_trap_0_08_vs_8_not_frozen_no_error():
    """R032: 0.08 m vs key 8 cm — leave for comparator (solution_fix)."""
    ds = load_dataset("data")
    report = next(r for r in ds.reports if r.reportId == "R032")
    payload = ds.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    prop = try_solution_first_no_error(
        interpretation=_interp("0.08"),
        hints=hints,
        payload=payload,
        solver=_solver("8"),
        reading=_reading("8"),
    )
    assert prop is None
