"""Solution-first short-circuit (human triage order).

Faculty instinct:
  1. Read what the student claims
  2. Check whether the stored solution already justifies the stored key
  3. If yes → no_error + short reply (do not invent an answer_key flip)

Runs BEFORE the comparator LLM so weak/free models cannot student-lead a key change.
"""

from __future__ import annotations

import re
from typing import Optional

from .schemas import (
    CommentHints,
    Interpretation,
    Proposal,
    QuestionPayload,
    SolutionReading,
    SolverResult,
)
from .taxonomy_guard import _reading_usable, _solver_usable, answers_match

_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
_ANSWERISH_INTENTS = {
    "answer_key",
    "wrong_option_value",
    "unit_or_format",
    "solution_wrong",
    "unclear",
}
_ANSWERISH_CATS = {
    "answer_key",
    "wrong_option_value",
    "unit_or_format",
    "solution_wrong",
    "unclear",
}


def _claim_candidates(interpretation: Interpretation, hints: CommentHints) -> list[str]:
    out: list[str] = []
    for raw in (interpretation.claimed_answer, *(hints.claimed_values or [])):
        s = (raw or "").strip()
        if not s:
            continue
        out.append(s)
        if len(s) <= 32:
            m = re.search(r"\b([A-D])\b", s, re.I)
            if m:
                out.append(m.group(1).upper())
            out.extend(_NUM.findall(s))
    seen: set[str] = set()
    uniq: list[str] = []
    for c in out:
        k = c.strip().upper()
        if k and k not in seen:
            seen.add(k)
            uniq.append(c.strip())
    return uniq


def _claims_differ_from_key(claims: list[str], key: str, qtype: str) -> bool:
    if not claims:
        return False
    return any(not answers_match(c, key, qtype) for c in claims)


def _as_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _key_is_integer(key: str) -> Optional[int]:
    f = _as_float(key)
    if f is None or abs(f - round(f)) > 1e-9:
        return None
    return int(round(f))


def payload_looks_sigfig(blob: str) -> bool:
    low = blob.lower()
    return "significant" in low or "round" in low


def _unrounded_float_vs_integer_key(claims: list[str], key: str, solution_blob: str) -> bool:
    """Student quotes a fractional decimal; key is the rounded integer (3112.99 vs 3113)."""
    key_i = _key_is_integer(key)
    if key_i is None:
        return False
    blob = solution_blob or ""
    key_in_solution = str(key_i) in blob
    for c in claims:
        if "." not in c:
            continue
        cf = _as_float(c)
        if cf is None or abs(cf - key_i) < 1e-9:
            continue
        rounds_to_key = abs(round(cf) - key_i) == 0
        close_frac = abs(cf - key_i) < 1.0
        if (rounds_to_key or close_frac) and (key_in_solution or payload_looks_sigfig(blob)):
            return True
    return False


def _unit_scale_dispute(claims: list[str], key: str, question_text: str) -> bool:
    """0.08 m vs key 8 (cm) — leave to comparator for possible solution_fix."""
    key_f = _as_float(key)
    if key_f is None:
        return False
    for c in claims:
        cf = _as_float(c)
        if cf is None or abs(cf) < 1e-15:
            continue
        for factor in (10.0, 100.0, 1000.0):
            if abs(cf * factor - key_f) < 1e-6 or abs(cf / factor - key_f) < 1e-6:
                return True
    return False


def try_solution_first_no_error(
    *,
    interpretation: Interpretation,
    hints: CommentHints,
    payload: QuestionPayload,
    solver: Optional[SolverResult],
    reading: Optional[SolutionReading],
) -> Optional[Proposal]:
    key = payload.answer_normalized
    qtype = payload.question_type
    claims = _claim_candidates(interpretation, hints)
    if not _claims_differ_from_key(claims, key, qtype):
        return None

    intents = set(hints.intent_hints or [])
    cat = (interpretation.category or "").lower()
    if not (intents & _ANSWERISH_INTENTS or cat in _ANSWERISH_CATS or claims):
        return None

    if _unit_scale_dispute(claims, key, payload.question_text or ""):
        return None

    # Student + independent solve agree against the key → real answer_key candidate.
    if (
        _solver_usable(solver)
        and not answers_match(solver.final_answer, key, qtype)  # type: ignore[union-attr]
        and any(answers_match(c, solver.final_answer, qtype) for c in claims)  # type: ignore[union-attr]
    ):
        return None

    reading_supports = bool(
        _reading_usable(reading)
        and reading.solution_final_answer  # type: ignore[union-attr]
        and answers_match(reading.solution_final_answer, key, qtype)
    )
    solver_supports = bool(
        _solver_usable(solver) and answers_match(solver.final_answer, key, qtype)  # type: ignore[union-attr]
    )

    solution_blob = f"{payload.solution_text or ''}\n{payload.solution_html or ''}"
    sigfig_case = qtype == "integerQuestion" and _unrounded_float_vs_integer_key(
        claims, key, solution_blob
    )

    if reading_supports and solver_supports:
        reason = "stored solution and independent solve both match the key"
    elif sigfig_case:
        reason = "student quoted an unrounded decimal; solution/key already give the full integer"
    elif reading_supports and not _solver_usable(solver):
        reason = "stored solution final answer matches the key"
    else:
        return None

    claim_show = claims[0] if claims else interpretation.claim_summary
    evidence = (
        f"Solution-first: student claims {claim_show!r}; stored key is {key!r}. "
        f"Stop reason: {reason}. "
        f"{'Independent solve also agrees. ' if solver_supports else ''}"
        f"No answer_key change — student dispute is wrong (form/rounding/option)."
    )
    return Proposal(
        verdict="no_error",
        repair=None,
        edit=None,
        llm_confidence=0.96,
        independent_confirmation=True,
        checks=["solution_agrees"] + (["solver_agrees"] if solver_supports else ["deterministic_check"]),
        evidence=evidence,
        faculty_note=(
            "Solution already justifies the stored key against the student's claim. "
            "Do not flip the key. Glance at the solution's last line only if unsure."
        ),
    )
