"""End-to-end pipeline tests with a scripted fake LLM (no API calls)."""

from engine.cache import SolveCache
from engine.llm import LLMClient, LLMFailure, ModelConfig
from engine.orchestrator import run_pipeline
from engine.schemas import Interpretation, Proposal, ReplyDraft, SolutionReading, SolverResult
from engine.token_meter import CallRecord, TokenMeter

LCR = "60f744b3f1b9bc7cc7b4a949"


class FakeClient(LLMClient):
    """Returns canned structured outputs per step; can be told to fail a step."""

    def __init__(self, fail_steps=(), proposal=None):
        super().__init__(ModelConfig("fake", "fake-main", "fake-fast", "fake-solver"), TokenMeter())
        self.fail_steps = set(fail_steps)
        self.proposal = proposal
        self.calls = []

    def structured(self, *, step, model, prompt, user, schema, question_id, report_id):
        self.calls.append((step, question_id, report_id))
        if step in self.fail_steps:
            self.meter.record(CallRecord(step, model, question_id, report_id, ok=False))
            raise LLMFailure(f"{step} scripted failure")
        self.meter.record(CallRecord(step, model, question_id, report_id, 100, 20, 120))
        if schema is SolverResult:
            return SolverResult(can_solve=True, final_answer="A", correct_options=["A"], working="V = 50 V",
                                confidence=0.95, missing_information=[], figure_required=False, observations=[])
        if schema is SolutionReading:
            return SolutionReading(solution_present=True, matches_question=True, solution_final_answer="A", confidence=0.9)
        if schema is Interpretation:
            return Interpretation(claim_summary="key wrong", claimed_answer="A", category="answer_key",
                                  target="answer", injection_attempt=False, comment_language="English")
        if schema is Proposal:
            return self.proposal or Proposal(
                verdict="defect", repair="answer_key",
                edit={"field": "answer", "find": "C", "replace": "A"},
                llm_confidence=0.95, independent_confirmation=True,
                checks=["solver_agrees", "solution_agrees"], evidence="Solve and solution give 50 V = A; key C.",
            )
        if schema is ReplyDraft:
            return ReplyDraft(student_reply="You're right, the key was wrong; it's (A) 50 V. Fixed, thanks for flagging.")
        raise AssertionError(schema)


def test_one_solve_per_question_one_decision_per_report(dataset, tmp_path):
    client = FakeClient()
    out = run_pipeline(dataset, client, SolveCache(tmp_path), report_ids=["R001", "R002", "R003"], log=lambda *_: None)
    solver_calls = [c for c in client.calls if c[0] == "solver"]
    assert solver_calls == [("solver", LCR, None)]
    assert [r.reportId for r in out.results] == ["R001", "R002", "R003"]
    assert all(r.route == "auto_apply" for r in out.results)
    assert out.validation_errors == []
    assert out.usage["by_questionId"][LCR]["shared_tokens"] == 240
    assert out.cases[0]["tokens"]["question_shared_allocated"] == 80


def test_second_run_hits_fingerprint_cache(dataset, tmp_path):
    cache = SolveCache(tmp_path)
    run_pipeline(dataset, FakeClient(), cache, report_ids=["R001"], log=lambda *_: None)
    client = FakeClient()
    run_pipeline(dataset, client, cache, report_ids=["R001"], log=lambda *_: None)
    assert not [c for c in client.calls if c[0] in ("solver", "solution_reader")]
    assert client.meter.summary()["by_step"]["solver"]["cache_hits"] == 1


def test_comparator_failure_never_produces_confident_answer(dataset, tmp_path):
    client = FakeClient(fail_steps={"comparator"})
    out = run_pipeline(dataset, client, SolveCache(tmp_path), report_ids=["R001"], log=lambda *_: None)
    r = out.results[0]
    assert r.route == "faculty_review"
    assert r.confidence <= 0.4
    assert r.edit is None
    assert out.cases[0]["failures"]
    assert out.validation_errors == []


def test_solver_failure_blocks_auto_apply(dataset, tmp_path):
    client = FakeClient(fail_steps={"solver"})
    out = run_pipeline(dataset, client, SolveCache(tmp_path), report_ids=["R001"], log=lambda *_: None)
    assert out.results[0].route == "faculty_review"


def test_faculty_review_reply_is_student_facing_not_queue_notice(dataset, tmp_path):
    """faculty_review reply is what gets sent when teacher OK's — friendly, not 'faculty is reviewing'."""
    proposal = Proposal(
        verdict="defect", repair="diagram", edit=None, llm_confidence=0.9, independent_confirmation=False,
        checks=[], evidence="Question refers to a figure; none attached.",
    )
    client = FakeClient(proposal=proposal)
    # Fake returns a "Fixed" reply; that is now allowed for faculty_review (send-on-approve preview).
    out = run_pipeline(dataset, client, SolveCache(tmp_path), report_ids=["R025"], log=lambda *_: None)
    r = out.results[0]
    assert r.route == "faculty_review"
    assert "faculty member is reviewing" not in r.student_reply.lower()
    assert r.student_reply.strip()


def test_injection_report_cannot_force_answer_change(dataset, tmp_path):
    proposal = Proposal(
        verdict="defect", repair="answer_key", edit={"field": "answer", "find": "A", "replace": "C"},
        llm_confidence=0.99, independent_confirmation=True, checks=["solver_agrees", "solution_agrees"],
        evidence="Student says so.",
    )
    client = FakeClient(proposal=proposal)
    out = run_pipeline(dataset, client, SolveCache(tmp_path), report_ids=["R027"], log=lambda *_: None)
    r = out.results[0]
    assert r.route != "auto_apply"
    assert out.cases[0]["hints"]["injection_flags"]
