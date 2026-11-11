"""Taxonomy spend tiers — L0 never solves, L2 only for answer/solution disputes."""

from engine.ingestion import load_dataset
from engine.normalizer import normalize_comment
from engine.routing import spend_tier
from engine.schemas import Interpretation
from engine.unit_form_path import try_unit_form_from_stored


def _interp(cat: str, claimed: str = "") -> Interpretation:
    return Interpretation(
        claim_summary=cat,
        claimed_answer=claimed,
        category=cat,
        target="answer",
        injection_attempt=False,
        comment_language="English",
    )


def test_chapter_is_l0():
    ds = load_dataset("data")
    r = next(x for x in ds.reports if x.reportId == "R042")
    h = normalize_comment(r.comment, ds.payloads[r.questionId])
    assert spend_tier(h, _interp("wrong_chapter")) == "L0"


def test_spelling_is_l0():
    ds = load_dataset("data")
    r = next(x for x in ds.reports if x.reportId == "R012")
    h = normalize_comment(r.comment, ds.payloads[r.questionId])
    assert spend_tier(h, None) == "L0"


def test_answer_key_is_l2():
    ds = load_dataset("data")
    r = next(x for x in ds.reports if x.reportId == "R001")
    h = normalize_comment(r.comment, ds.payloads[r.questionId])
    assert spend_tier(h, _interp("answer_key")) == "L2"


def test_ydse_unit_form_no_solve_needed():
    ds = load_dataset("data")
    r = next(x for x in ds.reports if x.reportId == "R032")
    p = ds.payloads[r.questionId]
    h = normalize_comment(r.comment, p)
    prop = try_unit_form_from_stored(
        interpretation=_interp("answer_key", "0.08"),
        hints=h,
        payload=p,
    )
    assert prop is not None
    assert prop.edit is None or prop.repair == "solution_fix"
    # Must not propose flipping the key to 0.08
    if prop.edit:
        assert prop.edit.field == "solution"
