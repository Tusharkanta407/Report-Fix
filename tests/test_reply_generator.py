from engine.reply_generator import (
    fallback_reply,
    reply_violations,
    key_fact_for,
)
from engine.schemas import FinalEdit, GuardDecision


def _dec(**kw):
    base = dict(
        verdict="defect",
        repair="stem_data",
        edit=None,
        route="faculty_review",
        confidence=0.9,
        rejections=[],
        downgrades=[],
        independent_confirmation=False,
    )
    base.update(kw)
    return GuardDecision(**base)


def test_stem_fallback_is_teacher_voice_not_evidence_paste():
    reply = fallback_reply(
        _dec(repair="stem_data"),
        key_fact="The student claims that data is missing, specifically the inductance value.",
    )
    assert "The student claims" not in reply
    assert "You're right" in reply
    assert "missing" in reply.lower()


def test_rejects_third_person_student_dump():
    bad = (
        "You're right — The student claims that data is missing, specifically the inductance value. "
        "Thanks for flagging; we've corrected this."
    )
    problems = reply_violations(bad, _dec())
    assert any("third person" in p for p in problems)


def test_key_fact_refuses_case_dump_evidence():
    fact = key_fact_for(
        _dec(repair="stem_data"),
        None,
        "The student claims that data is missing, specifically the inductance value.",
    )
    assert fact == "stem_data" or fact == ""


def test_answer_key_fallback_names_value():
    reply = fallback_reply(
        _dec(
            repair="answer_key",
            edit=FinalEdit(field="answer", find="2", replace="1"),
            route="auto_apply",
        )
    )
    assert "(1)" in reply
    assert "The student" not in reply
