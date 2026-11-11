"""Intent gate + deterministic short-circuit.

STRICT LOOP (token-saving):
  1. Read the student REPORT only (rules + optional cheap NLP).
  2. Map intent → taxonomy.
  3. Solve the question ONLY if the report disputes answer / solution / stem physics.
  4. Chapter, spelling, exam tag, app, syllabus → NEVER call the solver.

This module:
  - `needs_academic_solve`: whitelist of intents that may burn solver tokens
  - `try_deterministic_proposal`: proposal without interpreter/comparator/solver
"""

from __future__ import annotations

import re
from typing import Optional

from .schemas import (
    CommentHints,
    ContentChecks,
    Interpretation,
    Proposal,
    ProposedEdit,
    QuestionPayload,
)

# ---- Intent classes ---------------------------------------------------------

# Cheap / filing / cosmetic — never run independent solve.
NO_SOLVE_INTENTS = {
    "spelling",
    "exam_reference",
    "markup_leak",
    "display",
    "app",
    "language",
    "empty",
    "wrong_chapter",
    "syllabus",
    "stray_text",  # noise
}

# Only these burn solver + solution_reader tokens.
SOLVE_REQUIRED_INTENTS = {
    "answer_key",
    "wrong_option_value",
    "solution_wrong",
    "solution_mismatch",
    "missing_data",
    "unit_or_format",
    "wrong_type",
}

# Structural option issues — content_checks, not a physics re-solve.
STRUCTURAL_INTENTS = {
    "missing_option",
    "blank_option",
    "identical_options",
    "figure_missing",
}

# Back-compat aliases used elsewhere.
DETERMINISTIC_INTENTS = NO_SOLVE_INTENTS | STRUCTURAL_INTENTS
ACADEMIC_INTENTS = SOLVE_REQUIRED_INTENTS | {"unclear"}  # unclear: solve only if no other path
METADATA_ONLY_INTENTS = {"wrong_chapter", "syllabus"}

KNOWN_TYPOS: tuple[tuple[str, str], ...] = (
    ("Choroid plexux", "Choroid plexus"),
    ("Epithellial tisue", "Epithelial tissue"),
    ("Epithellial tissue", "Epithelial tissue"),
    ("shurbs", "shrubs"),
)


def needs_academic_solve(hints_list: list[CommentHints]) -> bool:
    """Legacy helper: True only for L2 (answer/solution) intents from rules.

    Prefer `routing.spend_tier` / orchestrator phase-1 for the real gate
    (rules + mini interpretation). Chapter / spelling / NEET → False.
    """
    from .routing import spend_tier

    if not hints_list:
        return True
    hard_inject = {"ignore_instructions", "role_claim", "command_to_system", "prompt_probe", "markup_payload"}
    for hints in hints_list:
        if hints.injection_flags and (set(hints.injection_flags) & hard_inject):
            continue
        if spend_tier(hints, None) == "L2":
            return True
    return False


def _raw_field(payload: QuestionPayload, field: str) -> str:
    if field == "question":
        return payload.question_html or ""
    if field == "solution":
        return payload.solution_html or ""
    return ""


def _unique_occurrence(haystack: str, needle: str) -> bool:
    if not needle or needle not in haystack:
        return False
    return haystack.count(needle) == 1


def _strip_exam_tag(raw: str, tag: str) -> Optional[ProposedEdit]:
    if not tag:
        return None
    if _unique_occurrence(raw, tag):
        return ProposedEdit(field="question", find=tag, replace="")
    pattern = re.compile(re.escape("(") + r"[^)]{0,40}" + re.escape(tag) + r"[^)]{0,40}" + re.escape(")"))
    m = pattern.search(raw)
    if m and _unique_occurrence(raw, m.group(0)):
        return ProposedEdit(field="question", find=m.group(0), replace="")
    return None


def _spelling_edit(payload: QuestionPayload, hints: CommentHints) -> Optional[ProposedEdit]:
    for find, replace in KNOWN_TYPOS:
        for field in ("question", "solution"):
            raw = _raw_field(payload, field)
            if find in raw and _unique_occurrence(raw, find):
                return ProposedEdit(field=field, find=find, replace=replace)
    for term in hints.quoted_terms:
        if len(term) < 3:
            continue
        for field in ("question", "solution"):
            raw = _raw_field(payload, field)
            if term in raw and _unique_occurrence(raw, term):
                # Without a known replacement, surface for faculty via markup path — skip.
                continue
    return None


def _markup_edit(payload: QuestionPayload, checks: ContentChecks) -> Optional[ProposedEdit]:
    if not checks.latex_leaks:
        return None
    leak = checks.latex_leaks[0]
    for field in ("question", "solution"):
        raw = _raw_field(payload, field)
        if _unique_occurrence(raw, leak):
            return ProposedEdit(field=field, find=leak, replace=leak)
    return None


def try_deterministic_proposal(
    hints: CommentHints,
    checks: ContentChecks,
    payload: QuestionPayload,
) -> Optional[Proposal]:
    """Return a Proposal when intent + rules are enough — no solver, no comparator."""
    intents = set(hints.intent_hints)

    hard_inject = {"ignore_instructions", "role_claim", "command_to_system", "prompt_probe", "markup_payload"}
    if hints.injection_flags and (set(hints.injection_flags) & hard_inject):
        return Proposal(
            verdict="no_error",
            repair=None,
            edit=None,
            llm_confidence=0.99,
            independent_confirmation=True,
            checks=["deterministic_check"],
            evidence=(
                "This comment looks like an attempt to instruct the system, not a real content report. "
                "No change to the question."
            ),
            faculty_note="Treat as noise / injection. Leave academic content unchanged.",
        )

    # Chapter / syllabus FIRST — never invent an answer_key from a filing report.
    if intents & METADATA_ONLY_INTENTS and not (intents & SOLVE_REQUIRED_INTENTS):
        chapter = payload.chapter or "(unknown chapter)"
        if "wrong_chapter" in intents:
            return Proposal(
                verdict="defect",
                repair="wrong_chapter",
                edit=None,
                llm_confidence=0.95,
                independent_confirmation=False,
                checks=["deterministic_check"],
                evidence=(
                    f"Student says the chapter is wrong. This question is currently filed under "
                    f"“{chapter}”, but the topic does not match that chapter. "
                    f"Only the chapter/metadata needs a refile — do not change the answer key or solution."
                ),
                faculty_note=f"Refile chapter (currently “{chapter}”). Leave answer key as is.",
            )
        return Proposal(
            verdict="defect",
            repair="syllabus",
            edit=None,
            llm_confidence=0.9,
            independent_confirmation=False,
            checks=["deterministic_check"],
            evidence=(
                f"Student flags a syllabus / coverage issue. Question is filed under “{chapter}”. "
                "Please confirm filing — no answer-key change."
            ),
            faculty_note="Confirm syllabus tagging. Leave answer key as is.",
        )

    if ("exam_reference" in intents or checks.exam_references) and (
        "exam_reference" in intents or re.search(r"\b(neet|jee|aieee|aiims)\b", hints.cleaned, re.I)
    ):
        if checks.exam_references:
            tag = checks.exam_references[0]
            edit = _strip_exam_tag(payload.question_html or "", tag)
            if edit is not None:
                return Proposal(
                    verdict="defect",
                    repair="exam_reference",
                    edit=edit,
                    llm_confidence=0.98,
                    independent_confirmation=True,
                    checks=["deterministic_check"],
                    evidence=f"Found exam tag “{tag}” in the question text. Safe to remove — answer key unchanged.",
                    faculty_note=f"Remove exam tag “{tag}” from the stem.",
                )

    if "spelling" in intents:
        edit = _spelling_edit(payload, hints)
        if edit is not None and edit.find != edit.replace:
            return Proposal(
                verdict="defect",
                repair="spelling",
                edit=edit,
                llm_confidence=0.95,
                independent_confirmation=True,
                checks=["deterministic_check"],
                evidence=f"Spelling fix: “{edit.find}” → “{edit.replace}”. Answer key unchanged.",
                faculty_note=f"Approve spelling: {edit.find} → {edit.replace}.",
            )
        quoted_gone = [
            t for t, ok in hints.quoted_terms_present.items() if ok is False and len(t) >= 3
        ]
        if quoted_gone and not any(hints.quoted_terms_present.get(t) for t in hints.quoted_terms):
            gone = quoted_gone[0]
            return Proposal(
                verdict="already_fixed",
                repair=None,
                edit=None,
                llm_confidence=0.95,
                independent_confirmation=True,
                checks=["deterministic_check"],
                evidence=f"The reported spelling “{gone}” is already gone from the live text.",
                faculty_note="Already fixed on live — no further edit.",
            )

    if "markup_leak" in intents and checks.latex_leaks:
        leak = checks.latex_leaks[0]
        return Proposal(
            verdict="defect",
            repair="markup_leak",
            edit=None,
            llm_confidence=0.9,
            independent_confirmation=False,
            checks=["deterministic_check"],
            evidence=f"Raw markup is visible to students (e.g. “{leak}”). Needs an editor cleanup — answer key unchanged.",
            faculty_note="Clean markup leak in question/solution HTML.",
        )

    # Structural options / figure — scans only.
    if intents & STRUCTURAL_INTENTS and not (intents & SOLVE_REQUIRED_INTENTS):
        if "identical_options" in intents or checks.duplicate_option_groups:
            return Proposal(
                verdict="defect",
                repair="identical_options",
                edit=None,
                llm_confidence=0.9,
                independent_confirmation=False,
                checks=["deterministic_check"],
                evidence="Two or more options have the same text. Faculty need to rewrite the duplicate distractors — answer key not auto-changed.",
                faculty_note="Rewrite duplicate options (human-only).",
            )
        if ("blank_option" in intents or checks.blank_option_letters) and checks.blank_option_letters:
            letters = ",".join(checks.blank_option_letters)
            return Proposal(
                verdict="defect",
                repair="option_repair",
                edit=None,
                llm_confidence=0.85,
                independent_confirmation=False,
                checks=["deterministic_check"],
                evidence=f"Option(s) {letters} look blank or incomplete. Faculty should restore the option text.",
                faculty_note=f"Fill blank option(s): {letters}.",
            )
        if "figure_missing" in intents or (checks.references_figure and not checks.has_images):
            return Proposal(
                verdict="defect",
                repair="diagram",
                edit=None,
                llm_confidence=0.9,
                independent_confirmation=False,
                checks=["deterministic_check"],
                evidence="The question refers to a figure that is missing (or not attached). Needs a diagram upload — no key change from AI.",
                faculty_note="Attach / restore the missing figure.",
            )

    if intents and intents <= {"app", "display", "language"}:
        verdict = {"app": "app_issue", "display": "display_issue", "language": "language_mode"}[
            next(iter(intents))
        ]
        labels = {
            "app_issue": "This looks like an app / platform issue, not a mistake in the question content.",
            "display_issue": "This looks like a display / rendering issue, not a content defect.",
            "language_mode": "Student is asking for another language. Question content itself is fine.",
        }
        return Proposal(
            verdict=verdict,
            repair=None,
            edit=None,
            llm_confidence=0.9,
            independent_confirmation=True,
            checks=["deterministic_check"],
            evidence=labels[verdict],
            faculty_note="Route to tech / product if needed. No academic edit.",
        )

    if hints.is_empty or intents == {"empty"}:
        structural = (
            checks.blank_option_letters
            or checks.missing_option_letters
            or checks.duplicate_option_groups
            or checks.latex_leaks
            or checks.exam_references
            or checks.answer_malformed
        )
        if not structural:
            return Proposal(
                verdict="not_actionable",
                repair=None,
                edit=None,
                llm_confidence=0.85,
                independent_confirmation=True,
                checks=["deterministic_check"],
                evidence="Empty report and no obvious content defect on scan. Nothing to change.",
                faculty_note="Close as not actionable unless the student adds detail.",
            )

    return None


def interpretation_from_hints(hints: CommentHints, category: str, target: str = "question") -> Interpretation:
    return Interpretation(
        claim_summary=f"(deterministic) {hints.cleaned[:160] or '(empty)'}",
        claimed_answer="",
        category=category,
        target=target,  # type: ignore[arg-type]
        injection_attempt=bool(hints.injection_flags),
        comment_language="unknown",
    )
