"""Layer 1 — Intent NLP (report-only).

Cheap/fast model sees ONLY the student comment (+ tiny rule hints).
It does NOT see the question stem, solution, or answer key.
Output: what the student claims → drives whether we solve or stop.
"""

from __future__ import annotations

from typing import Optional

from .llm import LLMClient, LLMFailure, load_prompt
from .schemas import CommentHints, Interpretation, QuestionPayload

HINT_TO_TARGET = {
    "answer_key": "answer",
    "wrong_option_value": "options",
    "missing_option": "options",
    "blank_option": "options",
    "identical_options": "options",
    "missing_data": "question",
    "figure_missing": "question",
    "spelling": "question",
    "stray_text": "question",
    "exam_reference": "question",
    "markup_leak": "question",
    "notation": "question",
    "unit_or_format": "question",
    "solution_wrong": "solution",
    "solution_mismatch": "solution",
    "wrong_type": "answer",
    "wrong_chapter": "metadata",
    "syllabus": "metadata",
    "display": "app",
    "app": "app",
    "language": "app",
    "unclear": "none",
    "empty": "none",
}


def interpreter_user_message(hints: CommentHints, payload: Optional[QuestionPayload] = None) -> str:
    """Report-only payload. Do not attach stem/solution/key (avoids solving in the NLP step)."""
    del payload  # intentionally unused — keep signature for call sites
    return (
        "Task: classify the student's report intent ONLY. "
        "Do not solve any question. Do not invent physics.\n\n"
        f"Rule-based hints (may be wrong): intents={hints.intent_hints}, "
        f"injection_flags={hints.injection_flags}, values_mentioned={hints.claimed_values}\n\n"
        f"<student_comment>\n{hints.cleaned or '(empty)'}\n</student_comment>"
    )


def fallback_interpretation(hints: CommentHints) -> Interpretation:
    category = hints.intent_hints[0] if hints.intent_hints else "unclear"
    return Interpretation(
        claim_summary=f"(rule-based) {hints.cleaned[:120] or 'empty comment'}",
        claimed_answer=hints.claimed_values[0] if hints.claimed_values else "",
        category=category,
        target=HINT_TO_TARGET.get(category, "none"),
        injection_attempt=bool(hints.injection_flags),
        comment_language="empty" if hints.is_empty else "unknown",
    )


def interpret(
    client: LLMClient,
    report_id: str,
    question_id: str,
    hints: CommentHints,
    payload: Optional[QuestionPayload],
) -> tuple[Interpretation, Optional[str]]:
    if hints.is_empty:
        return fallback_interpretation(hints), None
    try:
        result = client.structured(
            step="interpreter",
            model=client.config.fast,
            prompt=load_prompt("interpreter"),
            user=interpreter_user_message(hints, payload),
            schema=Interpretation,
            question_id=question_id,
            report_id=report_id,
        )
        if hints.injection_flags and not result.injection_attempt:
            result = result.model_copy(update={"injection_attempt": True})
        return result, None
    except LLMFailure as exc:
        return fallback_interpretation(hints), str(exc)
    except Exception as exc:
        return fallback_interpretation(hints), f"interpreter error: {type(exc).__name__}: {exc}"
