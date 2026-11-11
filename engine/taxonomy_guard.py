"""Layer 4: deterministic taxonomy + safety guard. Ordinary code owns the final route.

The LLM proposes a verdict / repair / edit. This module:
  * rejects keys outside the closed taxonomy,
  * rejects edits outside the repair's allowed fields,
  * validates `find` against the RAW stored HTML/MathML (exact, unique, markup-safe),
  * re-derives `independent_confirmation` from evidence instead of trusting the model,
  * forces `faculty_review` for human-only repairs, weak evidence, failures and conflicts.
Anything without a tested auto-apply policy defaults to `faculty_review`.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .htmltext import has_partial_tag, tag_balance
from .ingestion import QUESTION_TYPES, format_like_stored, normalize_answer
from .schemas import (
    ContentChecks,
    FinalEdit,
    GuardDecision,
    Proposal,
    QuestionPayload,
    SolutionReading,
    SolverResult,
)

# Development heuristics, not calibrated probabilities. Tune against real cases.
LOW_RISK_FLOOR = 0.85
HIGH_RISK_FLOOR = 0.92
SOLVER_MIN_CONFIDENCE = 0.6
CONFLICT_SOLVER_CONFIDENCE = 0.75
FAILURE_CONFIDENCE_CAP = 0.4
SURGICAL_MAX_SHARE = 0.4
SURGICAL_MIN_CHARS = 200

LOW_RISK = {"spelling", "noise", "exam_reference", "markup_leak"}
LOCAL_FORM = {"notation", "answer_form"}
HIGH_RISK = {"stem_data", "option_repair", "solution_fix", "solution_missing", "answer_key", "type_mismatch"}
HUMAN_ONLY = {"identical_options", "diagram", "wrong_question", "unsound", "wrong_chapter", "syllabus"}
TESTED_AUTO_POLICIES = LOW_RISK | LOCAL_FORM | HIGH_RISK
WHOLE_FIELD_REWRITE_OK = {"solution_fix", "solution_missing"}

# Checks that must be independently verified before a high-risk repair may auto-apply.
REQUIRED_CHECKS: dict[str, set[str]] = {
    "answer_key": {"solver_agrees", "solution_agrees"},
    "stem_data": {"solution_states_value", "solver_agrees"},
    "option_repair": {"deterministic_check", "solution_agrees"},
    "solution_fix": {"solver_agrees"},
    "solution_missing": {"solver_agrees"},
    "type_mismatch": {"solver_agrees", "deterministic_check"},
}
MIN_VERIFIED_FOR_HIGH_RISK = 2

ENTITY_VARIANTS = (
    ("\u2019", "&rsquo;"),
    ("\u2018", "&lsquo;"),
    ("\u201c", "&ldquo;"),
    ("\u201d", "&rdquo;"),
    ("\u00a0", "&nbsp;"),
    ("\u2026", "&hellip;"),
    ("\u2013", "&ndash;"),
    ("\u2014", "&mdash;"),
)
OPTION_A_RAW = re.compile(r"\(\s*A\s*\)")


@dataclass
class GuardContext:
    payload: Optional[QuestionPayload]
    checks: Optional[ContentChecks] = None
    solver: Optional[SolverResult] = None
    reading: Optional[SolutionReading] = None
    forced_review: list[str] = field(default_factory=list)
    # Student-claimed value (e.g. "1") — used when solution ≠ key but solver final hallucinates.
    claimed_answer: Optional[str] = None


# ---------------------------------------------------------------- helpers


def answers_match(a: str, b: str, question_type: str) -> bool:
    na, nb = normalize_answer(a, question_type), normalize_answer(b, question_type)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if question_type == "integerQuestion":
        try:
            fa, fb = float(na), float(nb)
        except ValueError:
            return False
        return abs(fa - fb) <= 1e-9 * max(1.0, abs(fa), abs(fb))
    return False


def _solver_usable(solver: Optional[SolverResult]) -> bool:
    return bool(solver and solver.can_solve and solver.final_answer and solver.confidence >= SOLVER_MIN_CONFIDENCE)


def _reading_usable(reading: Optional[SolutionReading]) -> bool:
    return bool(reading and reading.solution_present and reading.matches_question)


def _stored_key_independently_supported(ctx: GuardContext, payload: QuestionPayload) -> bool:
    """True when solve + solution both already agree with the stored key (student-led flip ban)."""
    key = payload.answer_normalized
    qtype = payload.question_type
    solver = ctx.solver
    reading = ctx.reading
    if not (
        _solver_usable(solver)
        and answers_match(solver.final_answer, key, qtype)  # type: ignore[union-attr]
    ):
        return False
    if not (
        _reading_usable(reading)
        and reading.solution_final_answer  # type: ignore[union-attr]
        and answers_match(reading.solution_final_answer, key, qtype)
    ):
        return False
    return True


def _working_concludes_value(working: Optional[str], value: str) -> bool:
    """True if the solver's own working asserts `= <value>` (optional unit).

    Catches self-contradictions like working `a = 20 cm` then final_answer `10`,
    or `μ = 0.8` then final_answer `C`.
    """
    if not working or not value:
        return False
    raw = str(value).strip()
    if not raw:
        return False
    # Search most of the working — finals often contradict in the last line only.
    tail = working[-900:] if len(working) > 900 else working
    escaped = re.escape(raw)
    pat = re.compile(
        rf"(?:=|\\approx)\s*{escaped}"
        rf"(?:\s*(?:cm|mm|m|V|A|N|kg|g))?\b",
        re.IGNORECASE,
    )
    return bool(pat.search(tail))


def _option_text_for_letter(ctx: "GuardContext", letter: str) -> Optional[str]:
    if not ctx.checks or not ctx.checks.options:
        return None
    want = (letter or "").strip().upper()
    for opt in ctx.checks.options:
        if (opt.letter or "").strip().upper() == want:
            return (opt.text or "").strip() or None
    return None


def _working_supports_answer(ctx: GuardContext, answer: str) -> bool:
    """Working concludes this answer — as a bare value or as an SCQ option's text.

    Do NOT trust phrases like "correct option is (C)" alone — those are often the
    hallucinated last line after arithmetic that already printed another value.
    """
    if not ctx.solver or not ctx.solver.working:
        return False
    working = ctx.solver.working
    if _working_concludes_value(working, answer):
        return True
    # Letter key / proposed letter → match option body only (A → "0.8").
    if len(answer.strip()) <= 2 and answer.strip().isalpha():
        text = _option_text_for_letter(ctx, answer)
        if text and _working_concludes_value(working, text):
            return True
    return False


def _is_unit_scale_pair(a: str, b: str) -> bool:
    """True if a and b differ only by ×/÷ 10/100/1000 (e.g. 8 vs 0.08)."""
    try:
        fa, fb = float(a.replace(",", "")), float(b.replace(",", ""))
    except ValueError:
        return False
    if abs(fa) < 1e-15 or abs(fb) < 1e-15:
        return False
    for factor in (10.0, 100.0, 1000.0):
        if abs(fa * factor - fb) < 1e-6 or abs(fb * factor - fa) < 1e-6:
            return True
    return False


def _is_subsequence(short: str, long: str) -> bool:
    it = iter(long)
    return all(ch in it for ch in short)


def _resolve_find(raw: str, find: str, replace: str) -> tuple[str, str, list[str]]:
    """Map a decoded `find` back onto the raw HTML when the model unescaped entities."""
    if find in raw:
        return find, replace, []
    f, r = find, replace
    for char, entity in ENTITY_VARIANTS:
        f, r = f.replace(char, entity), r.replace(char, entity)
    if f in raw:
        return f, r, ["find re-encoded with HTML entities to match raw field"]
    escaped_f = html.escape(find, quote=False)
    if escaped_f in raw:
        return escaped_f, html.escape(replace, quote=False), ["find html-escaped to match raw field"]
    return find, replace, []


def _options_start(raw: str) -> int:
    m = OPTION_A_RAW.search(raw)
    return m.start() if m else -1


# ---------------------------------------------------------------- edit validation


def validate_text_edit(repair: str, field_name: str, raw: str, find: str, replace: str) -> tuple[Optional[tuple[str, str]], list[str], list[str]]:
    """Returns ((find, replace) | None, rejections, notes)."""
    rejections: list[str] = []
    find, replace, notes = _resolve_find(raw, find, replace)

    if not find:
        whole_ok = repair == "solution_missing" and not raw.strip()
        if not whole_ok:
            return None, ["empty find string"], notes
        return (find, replace), [], notes

    count = raw.count(find)
    if count == 0:
        return None, [f"find text not present in raw {field_name}"], notes
    if count > 1:
        return None, [f"find text is ambiguous ({count} occurrences in {field_name})"], notes
    if find == replace:
        return None, ["replace is identical to find"], notes
    if has_partial_tag(find) or has_partial_tag(replace):
        rejections.append("edit cuts through an HTML/MathML tag")
    if tag_balance(find) != tag_balance(replace):
        rejections.append("edit changes markup nesting (would damage HTML/MathML)")

    whole_field = repair in WHOLE_FIELD_REWRITE_OK
    if not whole_field:
        limit = max(SURGICAL_MIN_CHARS, int(SURGICAL_MAX_SHARE * len(raw)))
        if len(find) > limit:
            rejections.append(f"find spans {len(find)} chars; not surgical (limit {limit})")
        if len(replace) > len(find) + 400:
            rejections.append("replacement much larger than the span it replaces")

    letters_only = lambda s: re.sub(r"[A-Za-z\s]", "", s)
    if repair == "spelling" and letters_only(find) != letters_only(replace):
        rejections.append("spelling edit changes a value, symbol or markup (words only)")
    if repair in ("noise", "exam_reference") and not (len(replace) < len(find) and _is_subsequence(replace, find)):
        rejections.append(f"{repair} edit must only delete text")
    if repair == "answer_form" and not (len(replace) > len(find) and _is_subsequence(find, replace)):
        rejections.append("answer_form edit must be additive only")
    if repair == "markup_leak" and re.search(r"\\[A-Za-z]+", html.unescape(re.sub(r"<[^>]+>", "", replace))):
        rejections.append("markup_leak replacement still contains raw LaTeX")
    if repair == "notation" and len(find) > 300:
        rejections.append("notation edit is not local to one expression")

    if field_name == "question" and repair in ("option_repair", "stem_data"):
        opt_start = _options_start(raw)
        pos = raw.find(find)
        if repair == "option_repair" and opt_start >= 0 and pos < opt_start:
            rejections.append("option_repair edit touches the stem (must stay inside the options)")
        if repair == "stem_data" and opt_start >= 0 and pos + len(find) > opt_start:
            rejections.append("stem_data edit touches the options")

    if rejections:
        return None, rejections, notes
    return (find, replace), [], notes


def validate_answer_edit(payload: QuestionPayload, find: str, replace: str) -> tuple[Optional[FinalEdit], list[str]]:
    qtype = payload.question_type
    stored_norm = payload.answer_normalized
    raw_text = payload.answer_raw if isinstance(payload.answer_raw, str) else None
    if not (find == raw_text or normalize_answer(find, qtype) == stored_norm):
        return None, [f"answer find {find!r} does not match stored answer {payload.answer_raw!r}"]
    new_norm = normalize_answer(replace, qtype)
    if not new_norm:
        return None, ["replacement answer is empty"]
    if qtype == "scq" and not re.fullmatch(r"[A-D]", new_norm):
        return None, [f"scq replacement must be one letter, got {replace!r}"]
    if qtype == "mcq" and not re.fullmatch(r"[A-D](,[A-D])*", new_norm):
        return None, [f"mcq replacement must be letters, got {replace!r}"]
    if qtype == "integerQuestion":
        try:
            float(new_norm)
        except ValueError:
            return None, [f"integer replacement must be numeric, got {replace!r}"]
    malformed_fix = new_norm == stored_norm and isinstance(payload.answer_raw, list) and payload.answer_raw != format_like_stored(payload.answer_raw, new_norm)
    if new_norm == stored_norm and not malformed_fix:
        return None, ["replacement answer equals stored answer"]
    return FinalEdit(field="answer", find=payload.answer_raw, replace=format_like_stored(payload.answer_raw, new_norm)), []


# ---------------------------------------------------------------- evidence


def verify_checks(proposal: Proposal, ctx: GuardContext, repair: Optional[str], new_answer: Optional[str]) -> set[str]:
    """Re-derive which supporting checks actually hold. Model claims are not enough."""
    claimed = set(proposal.checks)
    verified: set[str] = set()
    payload, solver, reading, checks = ctx.payload, ctx.solver, ctx.reading, ctx.checks
    qtype = payload.question_type if payload else "scq"

    if _solver_usable(solver):
        if new_answer is not None:
            if answers_match(solver.final_answer, new_answer, qtype):
                verified.add("solver_agrees")
        elif "solver_agrees" in claimed:
            verified.add("solver_agrees")

    if _reading_usable(reading):
        if new_answer is not None:
            if reading.solution_final_answer and answers_match(reading.solution_final_answer, new_answer, qtype):
                verified.add("solution_agrees")
        elif "solution_agrees" in claimed:
            verified.add("solution_agrees")

    if reading and reading.values_used_not_in_stem and "solution_states_value" in claimed:
        verified.add("solution_states_value")

    if payload and payload.error_history and "error_history" in claimed:
        verified.add("error_history")

    if checks is not None and repair:
        deterministic = {
            "option_repair": bool(checks.missing_option_letters or checks.blank_option_letters),
            "identical_options": bool(checks.duplicate_option_groups),
            "markup_leak": bool(checks.latex_leaks),
            "exam_reference": bool(checks.exam_references),
            "noise": bool(checks.noise_snippets),
            "diagram": checks.references_figure and not checks.has_images,
            "type_mismatch": bool(checks.answer_malformed)
            or bool(
                solver
                and solver.can_solve
                and (
                    (qtype == "mcq" and len(solver.correct_options) == 1)
                    or (qtype == "scq" and len(solver.correct_options) > 1)
                )
            ),
            "answer_key": bool(checks.answer_malformed),
        }.get(repair, False)
        if deterministic:
            verified.add("deterministic_check")

    if "student_claim_verified" in claimed:
        verified.add("student_claim_verified")
    return verified


# ---------------------------------------------------------------- main entry


def decide(proposal: Proposal, ctx: GuardContext, taxonomy: dict[str, Any]) -> GuardDecision:
    verdicts: dict[str, str] = taxonomy["verdicts"]
    repairs: dict[str, dict[str, Any]] = taxonomy["repairs"]
    rejections: list[str] = []
    downgrades: list[str] = list(ctx.forced_review)
    payload = ctx.payload

    verdict = proposal.verdict
    repair = proposal.repair or None
    confidence = float(proposal.llm_confidence)

    if repair is not None and repair not in repairs:
        rejections.append(f"unknown repair key {repair!r}")
        repair = None
    if verdict not in verdicts:
        rejections.append(f"unknown verdict key {verdict!r}")
        verdict = "defect" if repair else "not_actionable"
        downgrades.append("invalid verdict from model")

    # ---- non-defect verdicts: no content change
    if verdict != "defect":
        if repair or proposal.edit:
            rejections.append(f"verdict {verdict} cannot carry a repair/edit; dropped")
        route = "no_change"
        solver = ctx.solver
        if (
            verdict == "no_error"
            and payload is not None
            and _solver_usable(solver)
            and solver.confidence >= CONFLICT_SOLVER_CONFIDENCE
            and not answers_match(solver.final_answer, payload.answer_normalized, payload.question_type)
        ):
            downgrades.append(
                f"independent solver got {solver.final_answer!r} but stored key is {payload.answer_normalized!r}; model said no_error"
            )
        if downgrades:
            route = "faculty_review"
            confidence = min(confidence, FAILURE_CONFIDENCE_CAP) if ctx.forced_review else confidence
        return GuardDecision(
            verdict=verdict,
            repair=None,
            edit=None,
            route=route,
            confidence=round(confidence, 3),
            rejections=rejections,
            downgrades=downgrades,
        )

    # ---- defect
    if repair is None:
        downgrades.append("defect without a valid repair key")
        return GuardDecision(
            verdict="defect", repair=None, edit=None, route="faculty_review",
            confidence=round(min(confidence, FAILURE_CONFIDENCE_CAP), 3),
            rejections=rejections, downgrades=downgrades,
        )

    spec = repairs[repair]
    allowed_fields: list[str] = spec.get("fields", [])
    auto_allowed: bool = bool(spec.get("auto")) and bool(allowed_fields)

    final_edit: Optional[FinalEdit] = None
    before: Any = None
    after: Any = None
    new_answer: Optional[str] = None
    edit = proposal.edit
    override_evidence: Optional[str] = None
    override_note: Optional[str] = None

    if edit is not None and not allowed_fields:
        rejections.append(f"repair {repair} has no writable fields; edit dropped (faculty authors the fix)")
        edit = None
    if edit is not None and edit.field not in allowed_fields:
        rejections.append(f"field {edit.field!r} outside scope of {repair} {allowed_fields}")
        edit = None

    if edit is not None and payload is None:
        rejections.append("no question record to validate edit against")
        edit = None

    if edit is not None:
        if edit.field == "answer":
            final_edit, errs = validate_answer_edit(payload, edit.find, edit.replace)
            rejections.extend(errs)
            if final_edit is not None:
                new_answer = normalize_answer(final_edit.replace, payload.question_type)
                before, after = payload.answer_raw, final_edit.replace
        elif edit.field == "questionType":
            if edit.find != payload.question_type:
                rejections.append(f"questionType find {edit.find!r} != stored {payload.question_type!r}")
            elif edit.replace not in QUESTION_TYPES or edit.replace == edit.find:
                rejections.append(f"invalid questionType replacement {edit.replace!r}")
            else:
                final_edit = FinalEdit(field="questionType", find=edit.find, replace=edit.replace)
                before, after = edit.find, edit.replace
        else:
            raw = payload.question_html if edit.field == "question" else payload.solution_html
            ok, errs, _notes = validate_text_edit(repair, edit.field, raw, edit.find, edit.replace)
            rejections.extend(errs)
            if ok is not None:
                f, r = ok
                final_edit = FinalEdit(field=edit.field, find=f, replace=r)
                before = raw
                after = raw.replace(f, r, 1) if f else r

    # Student-led answer_key flip: solve+solution already match stored key -> keep key.
    if (
        repair == "answer_key"
        and payload is not None
        and new_answer is not None
        and not answers_match(new_answer, payload.answer_normalized, payload.question_type)
        and _stored_key_independently_supported(ctx, payload)
    ):
        rejections.append(
            "rejected student-led answer_key flip: independent solve and solution already match stored key"
        )
        return GuardDecision(
            verdict="no_error",
            repair=None,
            edit=None,
            route="no_change",
            confidence=round(max(confidence, 0.9), 3),
            rejections=rejections,
            downgrades=downgrades,
            independent_confirmation=True,
        )

    # Working-vs-final hallucination: arithmetic supports the STORED key, but final flipped away.
    if (
        repair == "answer_key"
        and payload is not None
        and new_answer is not None
        and not answers_match(new_answer, payload.answer_normalized, payload.question_type)
        and _solver_usable(ctx.solver)
        and ctx.solver is not None
        and _working_supports_answer(ctx, payload.answer_normalized)
        and not _working_supports_answer(ctx, new_answer)
    ):
        key = payload.answer_normalized
        rejections.append(
            f"rejected answer_key flip to {new_answer!r}: solver working already concludes {key!r} "
            f"(self-inconsistent final {ctx.solver.final_answer!r})"
        )
        return GuardDecision(
            verdict="no_error",
            repair=None,
            edit=None,
            route="no_change",
            confidence=round(max(confidence, 0.9), 3),
            rejections=rejections,
            downgrades=downgrades
            + ["solver working supports stored key; ignore contradictory final_answer"],
            independent_confirmation=True,
            faculty_evidence=(
                f"The independent working itself gets the same result as the live key ({key}). "
                f"The model’s final_answer {ctx.solver.final_answer!r} contradicts that arithmetic, "
                f"so we are not changing the key to {new_answer}."
            ),
            faculty_note=(
                f"Keep key = {key}. Working supports it; treat the final letter/value as a hallucination."
            ),
        )

    # Solution-backed rewrite (Gauss trap): stored solution concludes X, key is Y≠X,
    # student claims X, but comparator/solver final hallucinated Z. Prefer X.
    if (
        repair == "answer_key"
        and payload is not None
        and new_answer is not None
        and _reading_usable(ctx.reading)
        and ctx.reading.solution_final_answer  # type: ignore[union-attr]
    ):
        qtype = payload.question_type
        sol = normalize_answer(ctx.reading.solution_final_answer, qtype)  # type: ignore[union-attr]
        key = payload.answer_normalized
        claim = (ctx.claimed_answer or "").strip()
        if (
            sol
            and not answers_match(sol, key, qtype)
            and claim
            and answers_match(claim, sol, qtype)
            and not answers_match(new_answer, sol, qtype)
        ):
            rejections.append(
                f"rewrote answer_key {new_answer!r} → {sol!r}: stored solution + student claim agree; "
                "solver/comparator final disagreed"
            )
            bad_solver = getattr(ctx.solver, "final_answer", None)
            new_answer = sol
            stored_shape = format_like_stored(payload.answer_raw, sol)
            replace_s = stored_shape if isinstance(stored_shape, str) else sol
            find_s = str(payload.answer_raw) if not isinstance(payload.answer_raw, list) else key
            final_edit = FinalEdit(field="answer", find=find_s, replace=str(replace_s))
            before = payload.answer_raw
            after = replace_s
            rewrite_evidence = (
                f"Student and the stored solution both give {sol}; the live key is {key}. "
                f"An independent solve proposed {bad_solver!r}, which disagrees with the solution’s own "
                f"final answer — prefer {sol}. Proposed correction: {key} → {sol}."
            )
            rewrite_note = (
                f"Approve {key} → {sol}. Solution + student agree; treat solver final "
                f"{bad_solver!r} as inconsistent."
            )
            downgrades.append("preferred stored solution final over inconsistent solver final")
            override_evidence = rewrite_evidence
            override_note = rewrite_note
            proposal = proposal.model_copy(
                update={
                    "independent_confirmation": False,
                    "checks": ["solution_agrees", "student_claim_verified"],
                    "evidence": rewrite_evidence,
                    "faculty_note": rewrite_note,
                }
            )

    # Option consistency: proposed new key must match solver — OR the stored solution
    # when we already rewrote to the solution final (solver may have hallucinated).
    if (
        repair == "answer_key"
        and payload is not None
        and new_answer is not None
        and _solver_usable(ctx.solver)
    ):
        solver = ctx.solver
        qtype = payload.question_type
        opts = [normalize_answer(o, qtype) for o in (solver.correct_options or []) if o]
        matches_final = answers_match(solver.final_answer, new_answer, qtype)  # type: ignore[union-attr]
        matches_opts = new_answer in opts if opts else False
        matches_solution = (
            _reading_usable(ctx.reading)
            and bool(ctx.reading.solution_final_answer)  # type: ignore[union-attr]
            and answers_match(ctx.reading.solution_final_answer, new_answer, qtype)  # type: ignore[union-attr]
            and not answers_match(ctx.reading.solution_final_answer, payload.answer_normalized, qtype)  # type: ignore[union-attr]
        )
        if not matches_final and not matches_opts and not matches_solution:
            rejections.append(
                f"option consistency failed: solver got {solver.final_answer!r} "
                f"but proposed key {new_answer!r}"
            )
            final_edit = None
            new_answer = None
            before = after = None
            downgrades.append("proposed answer_key does not match solver final/options")
            # Force faculty; never claim independent confirmation on a mismatched option.
            proposal = proposal.model_copy(update={"independent_confirmation": False})
        elif matches_solution and not matches_final and not matches_opts:
            downgrades.append(
                "solver final disagrees with proposed key; kept because stored solution supports it"
            )
            proposal = proposal.model_copy(update={"independent_confirmation": False})

    # Unit-scale key flip ban (0.08 m vs asked cm key "8"): never replace key with SI form.
    if (
        repair == "answer_key"
        and payload is not None
        and new_answer is not None
        and _is_unit_scale_pair(payload.answer_normalized, new_answer)
    ):
        rejections.append(
            "rejected unit-scale answer_key flip: keep stem units (e.g. 8 cm), use solution_fix instead"
        )
        return GuardDecision(
            verdict="no_error",
            repair=None,
            edit=None,
            route="faculty_review",
            confidence=round(min(confidence, 0.7), 3),
            rejections=rejections,
            downgrades=downgrades + ["unit-scale key flip blocked; prefer solution_fix"],
            independent_confirmation=False,
        )

    # Solution matches stored key, but solver alone wants a different letter/value:
    # do not auto-trust that flip — force faculty (still keep proposed edit for review
    # only when solution does NOT support the stored key).
    if (
        repair == "answer_key"
        and payload is not None
        and new_answer is not None
        and not answers_match(new_answer, payload.answer_normalized, payload.question_type)
        and _reading_usable(ctx.reading)
        and ctx.reading.solution_final_answer  # type: ignore[union-attr]
        and answers_match(ctx.reading.solution_final_answer, payload.answer_normalized, payload.question_type)
        and _solver_usable(ctx.solver)
        and answers_match(ctx.solver.final_answer, new_answer, payload.question_type)  # type: ignore[union-attr]
        and not answers_match(ctx.reading.solution_final_answer, new_answer, payload.question_type)
    ):
        # Classic student-led + wrong solve vs correct solution (amplitude D vs B).
        rejections.append(
            "rejected solve-vs-solution conflict flip: stored solution matches key; solver alone matched the edit"
        )
        sol_key = payload.answer_normalized
        return GuardDecision(
            verdict="no_error",
            repair=None,
            edit=None,
            route="no_change",
            confidence=round(max(confidence, 0.9), 3),
            rejections=rejections,
            downgrades=downgrades,
            independent_confirmation=True,
            faculty_evidence=(
                f"The stored solution already ends at the live key ({sol_key}). "
                f"A separate solve suggested {new_answer}, but we are not flipping the key on solver-alone evidence. "
                "Leave the answer as is unless faculty re-works the problem."
            ),
            faculty_note=(
                f"No key change. Solution supports {sol_key}; do not auto-apply solver’s {new_answer}."
            ),
        )

    verified = verify_checks(proposal, ctx, repair, new_answer)
    required = REQUIRED_CHECKS.get(repair, set())
    independent = bool(proposal.independent_confirmation) and required.issubset(verified)
    if repair in HIGH_RISK:
        independent = independent and len(verified - {"student_claim_verified"}) >= MIN_VERIFIED_FOR_HIGH_RISK

    route = "auto_apply"
    if not auto_allowed:
        downgrades.append(f"{repair} is human-only (auto: false)")
        route = "faculty_review"
    elif repair not in TESTED_AUTO_POLICIES:
        downgrades.append(f"no tested auto-apply policy for {repair}")
        route = "faculty_review"
    elif final_edit is None:
        downgrades.append("no valid surgical edit")
        route = "faculty_review"
    elif repair in HIGH_RISK:
        if confidence < HIGH_RISK_FLOOR:
            downgrades.append(f"confidence {confidence:.2f} below high-risk floor {HIGH_RISK_FLOOR}")
            route = "faculty_review"
        if not independent:
            missing = sorted(required - verified)
            downgrades.append(
                "independent confirmation not established"
                + (f" (missing: {', '.join(missing)})" if missing else "")
            )
            route = "faculty_review"
    else:
        if confidence < LOW_RISK_FLOOR:
            downgrades.append(f"confidence {confidence:.2f} below floor {LOW_RISK_FLOOR}")
            route = "faculty_review"
        if repair in ("exam_reference", "markup_leak") and "deterministic_check" not in verified:
            downgrades.append(f"{repair} not corroborated by deterministic scan")
            route = "faculty_review"

    if ctx.forced_review:
        route = "faculty_review"
        confidence = min(confidence, FAILURE_CONFIDENCE_CAP)

    return GuardDecision(
        verdict="defect",
        repair=repair,
        edit=final_edit if auto_allowed else None,
        route=route,
        confidence=round(confidence, 3),
        rejections=rejections,
        downgrades=downgrades,
        independent_confirmation=independent,
        before=before if auto_allowed else None,
        after=after if auto_allowed else None,
        faculty_evidence=override_evidence,
        faculty_note=override_note,
    )
