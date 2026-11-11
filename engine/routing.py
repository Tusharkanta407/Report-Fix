"""Taxonomy-tier routing: what a report is allowed to spend tokens on.

Read `data/taxonomy.json` mentally as three spend levels:

  L0 — never solve (cosmetic / filing / platform / human-authored content)
  L1 — explain from STORED solution + stem (unit/form, sig-fig student confusion)
  L2 — independent solve with strong model (answer / solution dispute)

Intent comes from rule hints + optional mini interpreter (report text only).
"""

from __future__ import annotations

from typing import Iterable, Optional

from .schemas import CommentHints, Interpretation

# L0: taxonomy repairs / verdicts that must NOT trigger physics solve.
L0_NO_SOLVE = {
    "spelling",
    "noise",
    "exam_reference",
    "markup_leak",
    "notation",
    "wrong_chapter",
    "syllabus",
    "identical_options",
    "diagram",
    "wrong_question",
    "display",
    "app",
    "language",
    "display_issue",
    "app_issue",
    "language_mode",
    "already_fixed",
    "empty",
    "not_actionable",
    "stray_text",
}

# L1: use stored solution / stem only (mini reply OK). No gpt-4o solve.
L1_EXPLAIN_STORED = {
    "unit_or_format",
    "answer_form",
}

# L2: only these may call the strong solver.
L2_SOLVE = {
    "answer_key",
    "wrong_option_value",
    "solution_wrong",
    "solution_mismatch",
    "missing_data",
    "stem_data",
    "wrong_type",
    "unsound",
}


def intent_keys(hints: CommentHints, interpretation: Optional[Interpretation] = None) -> set[str]:
    keys = set(hints.intent_hints or [])
    if interpretation and interpretation.category:
        keys.add(interpretation.category)
    return keys


def spend_tier(hints: CommentHints, interpretation: Optional[Interpretation] = None) -> str:
    """Return 'L0' | 'L1' | 'L2'."""
    keys = intent_keys(hints, interpretation)
    if not keys:
        return "L2"  # unknown → conservative solve once
    if keys & L2_SOLVE:
        return "L2"
    if keys & L1_EXPLAIN_STORED:
        return "L1"
    if keys <= (L0_NO_SOLVE | L1_EXPLAIN_STORED) or (keys & L0_NO_SOLVE and not (keys & L2_SOLVE)):
        # Prefer L0 when any no-solve intent and no solve intent.
        if keys & L0_NO_SOLVE and not (keys & L2_SOLVE):
            return "L0"
        if keys & L1_EXPLAIN_STORED:
            return "L1"
        return "L0"
    if keys == {"unclear"}:
        return "L2"
    return "L2"


def question_needs_solve(
    hints_list: Iterable[CommentHints],
    interpretations: Optional[dict[str, Interpretation]] = None,
    report_ids: Optional[list[str]] = None,
) -> bool:
    """True if any sibling report is L2 (answer/solution dispute)."""
    interpretations = interpretations or {}
    # hints_list alone (legacy): use rules only
    for i, hints in enumerate(hints_list):
        interp = None
        if report_ids and i < len(report_ids):
            interp = interpretations.get(report_ids[i])
        if spend_tier(hints, interp) == "L2":
            return True
    return False
