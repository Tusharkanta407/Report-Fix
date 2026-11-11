import pytest

from engine.content_checks import inspect_question
from engine.schemas import Proposal, ProposedEdit, SolutionReading, SolverResult
from engine.taxonomy_guard import (
    HIGH_RISK,
    HUMAN_ONLY,
    LOCAL_FORM,
    LOW_RISK,
    GuardContext,
    decide,
)

LCR = "60f744b3f1b9bc7cc7b4a949"  # key C (130 V), solution and physics give 50 V = A
PLEXUS = "61ee6c9d90a1a968a168686b"  # "Choroid plexux" typo in option D
FIGURE = "622df25ab70e4b50e44ff837"


def solver(answer, conf=0.95, options=None):
    return SolverResult(
        can_solve=True, final_answer=answer, correct_options=options or [answer], working="w",
        confidence=conf, missing_information=[], figure_required=False, observations=[],
    )


def reading(answer, matches=True):
    return SolutionReading(
        solution_present=True, matches_question=matches, solution_final_answer=answer, confidence=0.9,
    )


def proposal(verdict="defect", repair=None, edit=None, conf=0.95, indep=True, checks=()):
    return Proposal(
        verdict=verdict, repair=repair, edit=ProposedEdit(**edit) if edit else None,
        llm_confidence=conf, independent_confirmation=indep, checks=list(checks), evidence="e",
    )


def ctx(dataset, qid, **kw):
    p = dataset.payloads[qid]
    return GuardContext(payload=p, checks=inspect_question(p), **kw)


def test_policy_sets_cover_every_taxonomy_repair(taxonomy):
    covered = LOW_RISK | LOCAL_FORM | HIGH_RISK | HUMAN_ONLY
    assert covered == set(taxonomy["repairs"])
    for name in HUMAN_ONLY:
        assert taxonomy["repairs"][name]["auto"] is False


def test_verified_answer_key_auto_applies(dataset, taxonomy):
    d = decide(
        proposal(repair="answer_key", edit={"field": "answer", "find": "C", "replace": "A"},
                 checks=["solver_agrees", "solution_agrees"]),
        ctx(dataset, LCR, solver=solver("A"), reading=reading("A")),
        taxonomy,
    )
    assert d.route == "auto_apply"
    assert d.independent_confirmation
    assert d.edit.model_dump() == {"field": "answer", "find": "C", "replace": "A"}


def test_answer_key_without_solver_agreement_goes_to_faculty(dataset, taxonomy):
    d = decide(
        proposal(repair="answer_key", edit={"field": "answer", "find": "C", "replace": "A"},
                 checks=["solver_agrees", "solution_agrees"]),
        ctx(dataset, LCR, solver=solver("C"), reading=reading("A")),
        taxonomy,
    )
    assert d.route == "faculty_review"
    assert not d.independent_confirmation


def test_student_led_answer_key_flip_rejected_when_solve_matches_key(dataset, taxonomy):
    """Solve+solution already match stored B; model must not flip key to student A."""
    d = decide(
        proposal(
            repair="answer_key",
            edit={"field": "answer", "find": "B", "replace": "A"},
            checks=["solver_agrees", "solution_agrees", "student_claim_verified"],
        ),
        ctx(dataset, PLEXUS, solver=solver("B"), reading=reading("B")),
        taxonomy,
    )
    assert d.verdict == "no_error"
    assert d.repair is None
    assert d.edit is None
    assert d.route == "no_change"
    assert any("student-led" in r for r in d.rejections)


def test_high_confidence_alone_never_unlocks_auto_apply(dataset, taxonomy):
    d = decide(
        proposal(repair="answer_key", edit={"field": "answer", "find": "C", "replace": "A"}, conf=0.99,
                 indep=True, checks=["solver_agrees", "solution_agrees"]),
        ctx(dataset, LCR, solver=None, reading=None),
        taxonomy,
    )
    assert d.route == "faculty_review"


def test_diagram_edit_rejected_and_routed_to_faculty(dataset, taxonomy):
    d = decide(
        proposal(repair="diagram", edit={"field": "question", "find": "figure", "replace": "figure <img/>"}),
        ctx(dataset, FIGURE),
        taxonomy,
    )
    assert d.route == "faculty_review"
    assert d.edit is None
    assert any("no writable fields" in r for r in d.rejections)


@pytest.mark.parametrize("repair", sorted(HUMAN_ONLY))
def test_every_human_only_repair_routes_to_faculty(dataset, taxonomy, repair):
    d = decide(proposal(repair=repair), ctx(dataset, LCR), taxonomy)
    assert d.route == "faculty_review"
    assert d.edit is None


def test_spelling_cannot_touch_answer(dataset, taxonomy):
    d = decide(
        proposal(repair="spelling", edit={"field": "answer", "find": "B", "replace": "D"}),
        ctx(dataset, PLEXUS),
        taxonomy,
    )
    assert d.edit is None
    assert d.route == "faculty_review"
    assert any("outside scope" in r for r in d.rejections)


def test_exact_spelling_fix_auto_applies(dataset, taxonomy):
    d = decide(
        proposal(repair="spelling", edit={"field": "question", "find": "Choroid plexux", "replace": "Choroid plexus"}, conf=0.95),
        ctx(dataset, PLEXUS),
        taxonomy,
    )
    assert d.route == "auto_apply"
    assert "Choroid plexus" in d.after and "plexux" not in d.after


def test_spelling_that_changes_a_number_is_rejected(dataset, taxonomy):
    d = decide(
        proposal(repair="spelling", edit={"field": "question", "find": "100 N", "replace": "101 N"}),
        ctx(dataset, "60ca4feb6420652745f55522"),
        taxonomy,
    )
    assert d.route == "faculty_review"
    assert d.edit is None


def test_find_missing_from_raw_is_rejected(dataset, taxonomy):
    d = decide(
        proposal(repair="spelling", edit={"field": "question", "find": "Choroyd", "replace": "Choroid"}),
        ctx(dataset, PLEXUS),
        taxonomy,
    )
    assert d.edit is None
    assert any("not present" in r for r in d.rejections)


def test_ambiguous_find_is_rejected(dataset, taxonomy):
    d = decide(
        proposal(repair="spelling", edit={"field": "question", "find": "span", "replace": "spam"}),
        ctx(dataset, PLEXUS),
        taxonomy,
    )
    assert d.edit is None
    assert any("ambiguous" in r for r in d.rejections)


def test_edit_that_breaks_markup_is_rejected(dataset, taxonomy):
    d = decide(
        proposal(repair="noise", edit={"field": "question", "find": "<h3><span style=\"color:#000000\">Aggregates", "replace": "Aggregates"}),
        ctx(dataset, PLEXUS),
        taxonomy,
    )
    assert d.edit is None


def test_unknown_repair_key_rejected(dataset, taxonomy):
    d = decide(proposal(repair="rewrite_everything"), ctx(dataset, LCR), taxonomy)
    assert d.repair is None
    assert d.route == "faculty_review"
    assert any("unknown repair" in r for r in d.rejections)


def test_unknown_verdict_rejected(dataset, taxonomy):
    d = decide(proposal(verdict="corrected", repair=None), ctx(dataset, LCR), taxonomy)
    assert d.verdict in taxonomy["verdicts"]
    assert d.route == "faculty_review"


def test_non_defect_verdict_drops_edits(dataset, taxonomy):
    d = decide(
        proposal(verdict="app_issue", repair="answer_key", edit={"field": "answer", "find": "C", "replace": "A"}),
        ctx(dataset, LCR),
        taxonomy,
    )
    assert d.route == "no_change"
    assert d.edit is None and d.repair is None


def test_no_error_conflicting_with_solver_goes_to_faculty(dataset, taxonomy):
    d = decide(proposal(verdict="no_error", repair=None), ctx(dataset, LCR, solver=solver("A")), taxonomy)
    assert d.route == "faculty_review"


def test_forced_review_on_failure(dataset, taxonomy):
    c = ctx(dataset, LCR, solver=solver("A"), reading=reading("A"))
    c.forced_review.append("comparator returned invalid JSON")
    d = decide(
        proposal(repair="answer_key", edit={"field": "answer", "find": "C", "replace": "A"},
                 checks=["solver_agrees", "solution_agrees"]),
        c, taxonomy,
    )
    assert d.route == "faculty_review"
    assert d.confidence <= 0.4


def test_mcq_answer_edit_preserves_stored_shape(dataset, taxonomy):
    qid = "68c8153cfb6b2f16e2d3ceaf"
    d = decide(
        proposal(repair="answer_key", edit={"field": "answer", "find": "A,B,D", "replace": "A,B"},
                 checks=["solver_agrees", "solution_agrees"]),
        ctx(dataset, qid, solver=solver("A,B", options=["A", "B"]), reading=reading("A,B")),
        taxonomy,
    )
    assert d.edit.find == ["A, B, D"]
    assert d.edit.replace == ["A, B"]


def test_option_repair_may_not_touch_stem(dataset, taxonomy):
    qid = "622f08d7b70e4b50e4500a1b"
    p = dataset.payloads[qid]
    stem_word = p.question_html[p.question_html.find(">") + 1 :][:12]
    d = decide(
        proposal(repair="option_repair", edit={"field": "question", "find": stem_word, "replace": stem_word + " X"},
                 checks=["deterministic_check", "solution_agrees"]),
        ctx(dataset, qid, solver=solver("C"), reading=reading("C")),
        taxonomy,
    )
    assert d.route == "faculty_review"


def test_working_supports_key_blocks_hallucinated_final_flip(dataset, taxonomy):
    """R016-style: working ends at a=20 (=key) but final_answer says 10."""
    qid = "6263d75bdd44e265ef926d97"
    working = (
        "2a^2 = 800\na^2 = 400\na = 20 cm\nThus, the side of the cube is 10 cm. The final answer is 10."
    )
    d = decide(
        proposal(
            repair="answer_key",
            edit={"field": "answer", "find": "20", "replace": "10"},
            checks=["solver_agrees", "deterministic_check"],
        ),
        ctx(
            dataset,
            qid,
            solver=SolverResult(
                can_solve=True,
                final_answer="10",
                correct_options=[],
                working=working,
                confidence=0.95,
                missing_information=[],
                figure_required=False,
                observations=[],
            ),
            reading=reading("40"),
        ),
        taxonomy,
    )
    assert d.verdict == "no_error"
    assert d.edit is None
    assert any("working already concludes" in r for r in d.rejections)


def test_friction_working_0_8_blocks_flip_to_c(dataset, taxonomy):
    """R029: working μ=0.8 (=A) but final says C (0.6)."""
    qid = "68e8734442c06737d6e56da4"
    working = (
        "F = 90 N.\n90 - μ * 100 = 10\nμ * 100 = 80\nμ = 0.8.\n"
        "The correct option is (C) 0.6."
    )
    d = decide(
        proposal(
            repair="answer_key",
            edit={"field": "answer", "find": "A", "replace": "C"},
            checks=["solver_agrees", "deterministic_check"],
        ),
        ctx(
            dataset,
            qid,
            solver=SolverResult(
                can_solve=True,
                final_answer="C",
                correct_options=["C"],
                working=working,
                confidence=0.95,
                missing_information=[],
                figure_required=False,
                observations=[],
            ),
            reading=reading("A"),
        ),
        taxonomy,
    )
    assert d.verdict == "no_error"
    assert d.edit is None
    assert any("working already concludes" in r for r in d.rejections)


def test_gauss_trap_rewrites_hallucinated_n5_to_solution_n1(dataset, taxonomy):
    """R005: solution+student say n=1; key is 2; solver final hallucinated 5."""
    qid = "68dea616d0cda73d07e93ae6"
    d = decide(
        proposal(
            repair="answer_key",
            edit={"field": "answer", "find": "2", "replace": "5"},
            checks=["solver_agrees", "deterministic_check"],
        ),
        ctx(
            dataset,
            qid,
            solver=solver("5", options=[]),
            reading=reading("1"),
            claimed_answer="1",
        ),
        taxonomy,
    )
    assert d.verdict == "defect"
    assert d.repair == "answer_key"
    assert d.edit is not None
    assert d.edit.replace == "1"
    assert d.edit.find == "2"
    assert d.route == "faculty_review"  # no solver_agrees on 1
    assert any("rewrote answer_key" in r for r in d.rejections)
