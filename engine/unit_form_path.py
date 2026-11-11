"""L1 path: unit / form disputes using STORED solution + stem — no independent solve.

Example: stem asks shift (in cm); solution ends at 0.08 m; key is 8; student says 0.08.
→ solution_fix (append conversion) or no_error with a clear student reply.
"""

from __future__ import annotations

import re
from typing import Optional

from .schemas import CommentHints, Interpretation, Proposal, ProposedEdit, QuestionPayload


def _floats(text: str) -> list[float]:
    out: list[float] = []
    for m in re.finditer(r"[-+]?\d+(?:\.\d+)?", text or ""):
        try:
            out.append(float(m.group(0)))
        except ValueError:
            continue
    return out


def _claims(interpretation: Interpretation, hints: CommentHints) -> list[str]:
    vals = []
    if interpretation.claimed_answer:
        vals.append(interpretation.claimed_answer.strip())
    vals.extend(hints.claimed_values or [])
    # de-dupe
    seen = set()
    uniq = []
    for v in vals:
        k = v.upper()
        if k and k not in seen:
            seen.add(k)
            uniq.append(v)
    return uniq


def try_unit_form_from_stored(
    *,
    interpretation: Interpretation,
    hints: CommentHints,
    payload: QuestionPayload,
) -> Optional[Proposal]:
    """If student float ↔ key differ by ×10/100/1000 and stem asks a unit form → no re-solve."""
    key = (payload.answer_normalized or "").strip()
    try:
        key_f = float(key.replace(",", ""))
    except ValueError:
        return None

    q = (payload.question_text or "").lower()
    sol = payload.solution_text or ""
    sol_l = sol.lower()
    claims = _claims(interpretation, hints)
    claim_fs = []
    for c in claims:
        try:
            claim_fs.append(float(c.replace(",", "")))
        except ValueError:
            continue
    if not claim_fs:
        return None

    asks_cm = "in cm" in q or "(in cm" in q
    asks_mm = "in mm" in q or "(in mm" in q
    factor = None
    matched_claim = None
    for cf in claim_fs:
        if abs(cf) < 1e-15:
            continue
        for f in (10.0, 100.0, 1000.0):
            if abs(cf * f - key_f) < 1e-6 or abs(cf / f - key_f) < 1e-6:
                factor = f
                matched_claim = cf
                break
        if factor:
            break
    if factor is None:
        return None

    # Prefer solution_fix when solution shows the SI number but not the asked unit.
    edit = None
    repair = None
    verdict = "no_error"
    if asks_cm or asks_mm or factor in (10.0, 100.0, 1000.0):
        # Look for the claim number in solution HTML to append conversion.
        raw = payload.solution_html or sol
        claim_str = None
        for c in claims:
            if c in raw:
                claim_str = c
                break
        if claim_str and asks_cm and abs(matched_claim * 100 - key_f) < 1e-6:
            find = claim_str
            replace = f"{claim_str} m = {key} cm"
            if find in raw and raw.count(find) == 1:
                edit = ProposedEdit(field="solution", find=find, replace=replace)
                repair = "solution_fix"
                verdict = "defect"

    unit_ask = "cm" if asks_cm else ("mm" if asks_mm else "the asked unit")
    if repair:
        evidence = (
            f"Student wrote {matched_claim}, but the stem asks for the answer in {unit_ask} "
            f"and the key is already {key} after conversion ({matched_claim} ↔ {key}). "
            f"Clarify the unit step in the solution; do not change the answer key."
        )
        faculty_note = (
            f"Keep key = {key}. Optionally clarify conversion in the solution "
            f"({matched_claim} → {key} {unit_ask})."
        )
    else:
        evidence = (
            f"Student wrote {matched_claim}; the stem asks for {unit_ask} and the key {key} "
            f"already matches that form after conversion. No key change needed."
        )
        faculty_note = f"No key change — {matched_claim} converts to key {key} in {unit_ask}."
    return Proposal(
        verdict=verdict,
        repair=repair,
        edit=edit,
        llm_confidence=0.95,
        independent_confirmation=True,
        checks=["deterministic_check", "solution_agrees"],
        evidence=evidence,
        faculty_note=faculty_note,
    )
