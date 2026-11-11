"""Deterministic inspection of a stored question. Cheap evidence the LLM steps can lean on."""

from __future__ import annotations

import re

from .ingestion import LETTERS, answer_malformation
from .schemas import ContentChecks, OptionInfo, QuestionPayload

OPTION_MARKER = re.compile(r"\(\s*([A-Da-d])\s*\)")
LATEX_LEAK = re.compile(
    r"\\(?:frac|dfrac|sqrt|times|cdot|alpha|beta|gamma|theta|lambda|mu|pi|omega|Omega|Delta|delta|"
    r"epsilon|varepsilon|rho|sigma|phi|vec|hat|left|right|circ|degree|text|mathrm|propto|infty|int|sum)\b"
    r"|\$[^$\n]{1,80}\$|\^\{[^}]*\}|_\{[^}]*\}"
)
EXAM_REF = re.compile(
    r"[\(\[]?\s*\b(?:NEET|AIPMT|JEE(?:\s*(?:Main|Mains|Advanced|Adv))?|AIEEE|AIIMS|BITSAT|KCET|MHT[- ]?CET|WBJEE|CBSE)\b"
    r"[^()\[\]\n]{0,25}?\b(?:19|20)\d{2}\b[^()\[\]\n]{0,15}[\)\]]?",
    re.IGNORECASE,
)
NOISE_PATTERNS = (
    re.compile(r"space\s+for\s+rough\s+work", re.IGNORECASE),
    re.compile(r"^\s*(?:Q\.?\s*\d+|Question\s*\d+)\s*[.):-]", re.IGNORECASE),
    re.compile(r"\b(?:source|ref(?:erence)?)\s*:\s*\S+", re.IGNORECASE),
)
FIGURE_WORDS = re.compile(r"\b(?:figure|fig\.?|diagram|shown\s+(?:in|below|above)|graph\s+shown|as\s+shown)\b", re.IGNORECASE)


def _norm_option(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().strip(".").lower()


def parse_options(text: str) -> list[OptionInfo]:
    markers = list(OPTION_MARKER.finditer(text))
    # Keep the last run of A.. markers in order; earlier "(a)" can appear inside the stem.
    best: list[re.Match] = []
    for i, m in enumerate(markers):
        if m.group(1).upper() != "A":
            continue
        run = [m]
        expected = 1
        for nxt in markers[i + 1 :]:
            if expected < len(LETTERS) and nxt.group(1).upper() == LETTERS[expected]:
                run.append(nxt)
                expected += 1
        if len(run) >= len(best):
            best = run
    options: list[OptionInfo] = []
    for idx, m in enumerate(best):
        end = best[idx + 1].start() if idx + 1 < len(best) else len(text)
        options.append(OptionInfo(letter=m.group(1).upper(), text=text[m.end() : end].strip()))
    return options


def inspect_question(payload: QuestionPayload) -> ContentChecks:
    checks = ContentChecks()
    text = payload.question_text

    if payload.question_type in ("scq", "mcq"):
        options = parse_options(text)
        checks.options = options
        checks.option_letters_found = [o.letter for o in options]
        checks.missing_option_letters = [l for l in LETTERS if l not in checks.option_letters_found]
        checks.blank_option_letters = [
            o.letter for o in options if not re.sub(r"[\s.,;:\-]", "", o.text)
        ]
        by_text: dict[str, list[str]] = {}
        for o in options:
            key = _norm_option(o.text)
            if key:
                by_text.setdefault(key, []).append(o.letter)
        checks.duplicate_option_groups = [v for v in by_text.values() if len(v) > 1]
        if not options:
            checks.notes.append("no (A)-(D) option markers found in question text")

    for source in (payload.question_text, payload.solution_text):
        checks.latex_leaks.extend(m.group(0) for m in LATEX_LEAK.finditer(source))
    checks.latex_leaks = sorted(set(checks.latex_leaks))
    checks.exam_references = sorted({m.group(0).strip() for m in EXAM_REF.finditer(text)})
    for pat in NOISE_PATTERNS:
        checks.noise_snippets.extend(m.group(0) for m in pat.finditer(text))

    checks.references_figure = bool(FIGURE_WORDS.search(text))
    checks.has_images = bool(payload.ques_images) or "<img" in payload.question_html.lower()
    if checks.references_figure and not checks.has_images:
        checks.notes.append("question text refers to a figure but no image is attached")
    if not payload.solution_text.strip():
        checks.notes.append("stored solution is empty")
    checks.answer_malformed = answer_malformation(payload.answer_raw, payload.question_type)
    return checks
