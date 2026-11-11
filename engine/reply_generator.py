"""Per-report step 4: student-facing reply.

Voice: a teacher talking TO the student in class — never a case summary ABOUT them.
"""

from __future__ import annotations

import re
from typing import Optional

from .llm import LLMClient, LLMFailure, load_prompt
from .schemas import GuardDecision, ReplyDraft

MAX_SENTENCES = 3
MAX_WORDS = 55

CLAIMS_FIXED = re.compile(
    r"\b(has|have|'ve)\s+(now\s+)?(been\s+)?(fixed|corrected|updated|changed|replaced)\b"
    r"|\b(is|it's|it is)\s+(now\s+)?(fixed|corrected)\b"
    r"|\bwe\s+(just\s+)?(fixed|corrected|updated|changed)\b"
    r"|(^|[.!?]\s+)(fixed|corrected|updated)\b",
    re.IGNORECASE,
)
INTERNAL_TERMS = re.compile(
    r"\b(AI|LLM|prompt|auto_apply|faculty_review|no_change|confidence score|pipeline|"
    r"Intent=|Unit/form path|independent solve|stored solution|"
    r"faculty member is (checking|reviewing)|sent (it )?for (faculty )?review)\b",
    re.IGNORECASE,
)
BLAMES_STUDENT = re.compile(r"\byou (were|are) wrong\b|\byou misread\b|\byou made a mistake\b", re.IGNORECASE)
# Third-person case-dump voice — the bug that produced "The student claims that…"
ABOUT_THE_STUDENT = re.compile(
    r"\bthe student (claims?|says|said|is correct|reported|suggests?)\b"
    r"|\bstudent claims?\b"
    r"|\bthe reporting student\b",
    re.IGNORECASE,
)
CASE_DUMP = re.compile(
    r"\b(Intent=|Unit/form|claim_summary|verified evidence|key fact for)\b",
    re.IGNORECASE,
)

FIX_SEND_ROUTES = {"auto_apply", "faculty_review"}

FALLBACK = {
    "no_error": (
        "Nice check. We went through the working again — it matches the key, "
        "so we're leaving the answer as is. Thanks for double-checking."
    ),
    "app_issue": (
        "Thanks for letting us know. The question content looks fine; "
        "this seems like an app issue and we've passed it to the tech team."
    ),
    "display_issue": (
        "Thanks for flagging. The content is fine — this looks like a display glitch on our side, "
        "and we've passed it on."
    ),
    "language_mode": (
        "Thanks for asking. This one isn't available in that language yet — we've noted your request."
    ),
    "already_fixed": "Thanks for reporting this. It's already fixed in the live question.",
    "not_actionable": (
        "Thanks for writing in. We couldn't spot a clear content issue — "
        "reply with the exact step that looked wrong if you can."
    ),
}

# Repair-specific teacher lines (no evidence paste).
REPAIR_LINES = {
    "spelling": "You're right — there was a spelling slip. We've corrected it. Thanks for flagging!",
    "exam_reference": "You're right — that exam tag didn't belong there. We've cleaned it up. Thanks!",
    "markup_leak": "You're right — some raw markup was showing. We've cleaned the text. Thanks!",
    "noise": "You're right — there was stray text in the question. We've cleaned it up. Thanks!",
    "notation": "You're right — the notation was off. We've fixed the expression. Thanks!",
    "answer_form": "You're right — the answer form/unit needed clarifying. We've updated it. Thanks!",
    "diagram": "You're right — the figure is missing. Thanks for flagging; we're fixing it.",
    "identical_options": "You're right — two options are the same. Thanks for flagging; we're fixing them.",
    "wrong_chapter": (
        "You're right — this question looks filed under the wrong chapter. "
        "We'll move it to the right one. Thanks for flagging!"
    ),
    "syllabus": (
        "You're right — the syllabus tagging looks off for this one. "
        "We'll correct the filing. Thanks for flagging!"
    ),
    "stem_data": "You're right — a required value was missing from the stem. We've added it. Thanks for flagging!",
    "option_repair": "You're right — one of the options needed a fix. We've corrected it. Thanks!",
    "solution_fix": "You're right — there was an issue in the solution. We've corrected it. Thanks for flagging!",
    "solution_missing": "You're right — the solution needed work. We've updated it. Thanks for flagging!",
    "type_mismatch": "You're right — the question type was stored wrong. We've corrected it. Thanks!",
}


def _pretty_answer(value) -> str:
    if isinstance(value, list):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(parts) if parts else str(value)
    return str(value)


def _looks_like_case_dump(text: str) -> bool:
    if not text or len(text) < 8:
        return True
    if ABOUT_THE_STUDENT.search(text) or CASE_DUMP.search(text):
        return True
    if text.lower().startswith(("the student", "student claims", "intent=")):
        return True
    return False


def _defect_fallback(decision: GuardDecision, key_fact: str = "") -> str:
    """Safe teacher-voice reply — never paste raw evidence."""
    if decision.edit is not None and decision.edit.field == "answer":
        return (
            f"You're right. The answer key was wrong; it's ({_pretty_answer(decision.edit.replace)}). "
            "Fixed, thanks for flagging."
        )
    if decision.edit is not None and decision.repair == "spelling":
        return (
            f"You're right — spelling: {decision.edit.find} → {decision.edit.replace}. "
            "Fixed, thanks for flagging."
        )
    if decision.edit is not None and decision.edit.field == "questionType":
        return (
            f"You're right — this was stored as {decision.edit.find} but should be {decision.edit.replace}. "
            "Fixed, thanks for flagging."
        )
    if decision.repair == "solution_fix" and decision.edit and "cm" in (decision.edit.replace or "").lower():
        return (
            "Good catch on the units. The stem asks for cm, so the key stays in that form — "
            "we're clarifying the conversion in the solution. Thanks!"
        )
    if decision.repair in REPAIR_LINES:
        return REPAIR_LINES[decision.repair]
    if decision.repair == "answer_key":
        return "You're right — the answer key needed a correction. We've updated it. Thanks for flagging!"
    return "You're right — thanks for flagging this. We've corrected the question."


def fallback_reply(decision: GuardDecision, key_fact: str = "") -> str:
    if decision.verdict == "defect":
        return _defect_fallback(decision, key_fact)
    return FALLBACK.get(decision.verdict, FALLBACK["not_actionable"])


def reply_violations(text: str, decision: GuardDecision) -> list[str]:
    problems: list[str] = []
    stripped = text.strip()
    if not stripped:
        return ["empty reply"]
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", stripped) if s.strip()]
    if len(sentences) > MAX_SENTENCES:
        problems.append(f"{len(sentences)} sentences (max {MAX_SENTENCES})")
    if len(stripped.split()) > MAX_WORDS:
        problems.append(f"too long ({len(stripped.split())} words)")
    if decision.route not in FIX_SEND_ROUTES and decision.verdict != "already_fixed" and CLAIMS_FIXED.search(stripped):
        problems.append("claims a fix was published but nothing is being corrected for this student")
    if INTERNAL_TERMS.search(stripped):
        problems.append("mentions internal system / review-queue language")
    if BLAMES_STUDENT.search(stripped):
        problems.append("blames the student")
    if ABOUT_THE_STUDENT.search(stripped):
        problems.append("talks about the student in third person instead of to them")
    if CASE_DUMP.search(stripped):
        problems.append("pastes internal case notes into the student reply")
    return problems


def reply_user_message(comment: str, decision: GuardDecision, evidence: str, repair_label: str, key_fact: str) -> str:
    send_note = (
        "This reply is sent to the student now."
        if decision.route == "auto_apply"
        else "Faculty will send this when they OK the fix. Write the final student-facing message."
        if decision.route == "faculty_review"
        else "No content change. Reassure / explain; do not claim a fix."
    )
    # Never hand the model a case-dump as "key fact".
    safe_fact = key_fact.strip() if key_fact and not _looks_like_case_dump(key_fact) else ""
    if not safe_fact and decision.edit is not None and decision.edit.field == "answer":
        safe_fact = f"correct answer is {_pretty_answer(decision.edit.replace)}"
    elif not safe_fact and decision.repair:
        safe_fact = repair_label or decision.repair

    return (
        "Write as a teacher talking TO this student (use you/your). "
        "Do NOT say \"the student claims\". Do NOT paste evidence verbatim.\n\n"
        f"verdict: {decision.verdict}\n"
        f"repair: {decision.repair or 'none'} ({repair_label})\n"
        f"route: {decision.route}\n"
        f"send_policy: {send_note}\n"
        f"one plain fact for the student: {safe_fact or '(say the outcome simply from the repair type)'}\n"
        f"(internal evidence — do not quote): {(evidence or '')[:240]}\n\n"
        f"<student_comment>\n{comment or '(empty)'}\n</student_comment>"
    )


def generate_reply(
    client: LLMClient,
    *,
    report_id: str,
    question_id: str,
    comment: str,
    decision: GuardDecision,
    evidence: str,
    repair_label: str,
    key_fact: str,
) -> tuple[str, list[str]]:
    """Returns (reply, notes). Falls back to a safe template rather than ship a rule-breaking reply."""
    notes: list[str] = []
    user = reply_user_message(comment, decision, evidence, repair_label, key_fact)
    for attempt in range(2):
        try:
            draft = client.structured(
                step="reply",
                model=client.config.fast,
                prompt=load_prompt("reply"),
                user=user,
                schema=ReplyDraft,
                question_id=question_id,
                report_id=report_id,
            )
        except LLMFailure as exc:
            notes.append(f"reply generation failed: {exc}")
            break
        except Exception as exc:
            notes.append(f"reply error: {type(exc).__name__}: {exc}")
            break
        problems = reply_violations(draft.student_reply, decision)
        if not problems:
            return draft.student_reply.strip(), notes
        notes.append(f"reply attempt {attempt + 1} rejected: {'; '.join(problems)}")
        user += (
            f"\n\nYour previous draft broke these rules: {'; '.join(problems)}. "
            "Rewrite as a teacher speaking to the student. Example: "
            "'You're right — L was missing from the stem; we've added it. Thanks!'"
        )
    notes.append("used safe fallback reply")
    return fallback_reply(decision, key_fact), notes


def key_fact_for(decision: GuardDecision, solver_working: Optional[str], proposal_evidence: str = "") -> str:
    if decision.edit is not None and decision.edit.field == "answer":
        return f"correct answer is {_pretty_answer(decision.edit.replace)}"
    if decision.edit is not None and decision.repair == "spelling":
        return f"{decision.edit.find} → {decision.edit.replace}"
    if decision.edit is not None and decision.edit.field in ("question", "solution"):
        # Short human hint only — not a raw HTML dump.
        return f"updated the {decision.edit.field}"
    if decision.repair in REPAIR_LINES:
        return decision.repair or ""
    if decision.verdict == "no_error":
        return ""
    # Refuse to treat case-dump evidence as a student-facing fact.
    if proposal_evidence and not _looks_like_case_dump(proposal_evidence) and len(proposal_evidence) < 80:
        return proposal_evidence
    return ""
