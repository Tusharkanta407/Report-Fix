"""Layer 2: rule-based reading of the student comment.

Produces hints for the LLM steps. Never decides a verdict and never rejects a comment
for being short ("D?" is a meaningful report).
"""

from __future__ import annotations

import re

from .schemas import CommentHints, QuestionPayload

MAX_COMMENT_CHARS = 600

INTENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "answer_key": (
        r"\b(ans|answer|key|uttar)\b",
        r"\bshould be\b",
        r"\b(galat|incorrect)\b",
        r"\bhona chahiye\b|\baana chahiye\b",
        # "why 130" / "why ans is" — not "why NEET 2019 written…"
        r"\b(kyu|why)\b.{0,20}\b(ans|answer|key|option)\b",
        r"\b(kyu|why)\b\s*(?:is\s+)?(?:it\s+)?\d",
        r"\bnot\s+\d",
    ),
    "missing_option": (r"option\s*[a-d]?\s*(is\s*)?missing", r"only\s*\d\s*options?", r"option.*nahi"),
    "blank_option": (r"\bblank\b", r"\bkhali\b", r"\bempty option\b"),
    "identical_options": (r"\bsame\b", r"\brepeat", r"\bidentical\b", r"two options"),
    "missing_data": (r"not given", r"\bmissing\b", r"nahi di", r"\bdata\b", r"value.*(nahi|not)"),
    "figure_missing": (r"\bfig(ure)?\b", r"\bdiagram\b", r"\bimage\b", r"\bgraph\b"),
    "spelling": (r"spell", r"\btypo\b", r"\bgrammar\b"),
    "exam_reference": (r"\b(neet|jee|aieee|aiims)\b\s*\d{4}", r"\bwritten in question\b"),
    "markup_leak": (r"\\[a-z]+", r"\bcode\b", r"\blatex\b", r"\bhtml\b", r"\$"),
    "unit_or_format": (r"\bunit", r"\bdecimal", r"\bround", r"\bsignificant"),
    "solution_mismatch": (r"other question", r"different question", r"kuch aur", r"some other"),
    "solution_wrong": (r"\bsolution\b",),
    "wrong_type": (r"multiple correct", r"single correct", r"\bnegative\b", r"more than one"),
    "wrong_chapter": (r"\bchapter\b",),
    "syllabus": (r"syllabus",),
    "display": (r"\bscreen\b", r"\bcut\b", r"\bload", r"\bslow\b", r"forever", r"\brender", r"\bblur", r"\bshowing\b"),
    "app": (r"\bclicked\b", r"\btapped\b", r"\bsaved\b", r"\bselected\b", r"\brecorded\b", r"\bkeyboard\b", r"\blag\b", r"\bcrash", r"\bmarked\b"),
    "language": (r"\bhindi\b", r"\benglish\b", r"\blanguage\b", r"\bbhasha\b", r"\bmarathi\b", r"\btamil\b", r"\btelugu\b", r"\bbengali\b"),
}

INJECTION_PATTERNS: dict[str, str] = {
    "ignore_instructions": r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)?\s*(instructions|rules|prompts?)",
    "role_claim": r"\byou are (now )?(the |an? )?(admin|system|developer|bot|assistant)\b|\bi am (the |an? )?(admin|teacher|faculty|moderator|developer)\b|\bas (an? )?(admin|faculty)\b",
    "command_to_system": r"\b(change|set|update|mark)\b.{0,30}\b(answer|report|status|key)\b.{0,20}\b(to|as)\b",
    "prompt_probe": r"system prompt|jailbreak|developer mode",
    "markup_payload": r"<\s*(script|iframe|img|svg)\b|javascript:",
}


def _clean(comment: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", comment)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_COMMENT_CHARS]


def _claimed_values(text: str) -> list[str]:
    values: list[str] = []
    for m in re.finditer(r"(?:answer|ans|key|option|should be|hona chahiye|aana chahiye)\s*(?:is|should be|=|:)?\s*\(?([A-Da-d])\)?(?![A-Za-z])", text, re.IGNORECASE):
        values.append(m.group(1).upper())
    # "only 3 options showing" — the digit is a count, not a claimed answer.
    if re.search(r"\bonly\s*\d+\s*options?\b", text, re.IGNORECASE):
        return values
    values.extend(re.findall(r"[-+]?\d+(?:\.\d+)?(?:\s*:\s*\d+(?:\.\d+)?)?", text))
    seen: list[str] = []
    for v in values:
        if v not in seen:
            seen.append(v)
    return seen


def _quoted_terms(text: str) -> list[str]:
    return [m.strip() for m in re.findall(r"['\"\u2018\u201c]([^'\"\u2019\u201d]{2,40})['\"\u2019\u201d]", text) if m.strip()]


def normalize_comment(comment: str | None, payload: QuestionPayload | None = None) -> CommentHints:
    original = comment or ""
    cleaned = _clean(original)
    lowered = cleaned.lower()

    intents = [
        intent
        for intent, patterns in INTENT_PATTERNS.items()
        if any(re.search(p, lowered) for p in patterns)
    ]
    if not cleaned:
        intents = ["empty"]
    elif not intents:
        intents = ["unclear"]

    injection = [name for name, pat in INJECTION_PATTERNS.items() if re.search(pat, lowered)]

    quoted = _quoted_terms(cleaned)
    present: dict[str, bool] = {}
    if payload is not None and quoted:
        haystack = f"{payload.question_text}\n{payload.solution_text}".lower()
        for term in quoted:
            present[term] = re.search(rf"(?<![a-z]){re.escape(term.lower())}(?![a-z])", haystack) is not None

    return CommentHints(
        original=original,
        cleaned=cleaned,
        is_empty=not cleaned,
        intent_hints=intents,
        injection_flags=injection,
        claimed_values=_claimed_values(cleaned),
        quoted_terms=quoted,
        quoted_terms_present=present,
    )
