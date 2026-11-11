"""Layer 1: load the three JSON files, index questions, group reports. No LLM."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .htmltext import html_to_text
from .schemas import QuestionPayload, Report

QUESTION_TYPES = ("scq", "mcq", "integerQuestion")
LETTERS = ("A", "B", "C", "D")


class DataError(ValueError):
    pass


@dataclass
class Dataset:
    questions: dict[str, dict[str, Any]]
    payloads: dict[str, QuestionPayload]
    reports: list[Report]
    taxonomy: dict[str, Any]
    groups: dict[str, list[Report]] = field(default_factory=dict)
    missing_question_reports: list[str] = field(default_factory=list)

    @property
    def reported_question_ids(self) -> list[str]:
        return [qid for qid in self.groups if qid in self.payloads]

    @property
    def unreported_question_ids(self) -> list[str]:
        return [qid for qid in self.payloads if qid not in self.groups]

    def siblings(self, report: Report) -> list[Report]:
        return [r for r in self.groups.get(report.questionId, []) if r.reportId != report.reportId]


# ---------------------------------------------------------------- answers


def _canonical_number(text: str) -> str | None:
    t = text.strip().replace(" ", "")
    if not re.fullmatch(r"[-+]?\d*\.?\d+(e[-+]?\d+)?", t, flags=re.IGNORECASE):
        return None
    value = float(t)
    if value.is_integer():
        return str(int(value))
    return f"{value:.10g}"


def _letters(text: str) -> list[str]:
    cleaned = re.sub(r"(?i)\b(option|options|and|or)\b", " ", text)
    found = re.findall(r"(?<![A-Za-z])([A-Da-d])(?![A-Za-z])", cleaned)
    return sorted({f.upper() for f in found})


def normalize_answer(value: Any, question_type: str) -> str:
    """Canonical comparison form: 'C', 'A,B,D', or '3113'. Never used for writing edits."""
    if value is None:
        return ""
    if isinstance(value, list):
        flat = ",".join(str(v) for v in value if v is not None)
    else:
        flat = str(value)
    flat = flat.strip()
    if question_type == "integerQuestion":
        num = _canonical_number(flat)
        if num is not None:
            return num
        m = re.search(r"[-+]?\d*\.?\d+", flat)
        return _canonical_number(m.group(0)) if m else flat
    letters = _letters(flat)
    if question_type == "scq":
        return letters[0] if len(letters) == 1 else ",".join(letters) if letters else flat.upper()
    return ",".join(letters)


def answer_malformation(value: Any, question_type: str) -> str | None:
    """Describe structural problems with the stored key, if any."""
    if question_type == "mcq":
        if not isinstance(value, list):
            return "mcq answer is not a list"
        if any(isinstance(v, str) and not v.strip() for v in value):
            return f"mcq answer array contains empty entries: {value!r}"
        if len(_letters(",".join(map(str, value)))) == 1:
            return f"mcq answer has exactly one correct letter: {value!r}"
        return None
    if isinstance(value, list):
        return f"{question_type} answer stored as a list: {value!r}"
    text = str(value).strip()
    if not text:
        return "answer is empty"
    if question_type == "scq" and not re.fullmatch(r"[A-Da-d]", text):
        return f"scq answer is not a single letter: {text!r}"
    if question_type == "integerQuestion" and _canonical_number(text) is None:
        return f"integer answer is not numeric: {text!r}"
    return None


def format_like_stored(stored: Any, canonical: str) -> Any:
    """Render a canonical answer in the same shape as the stored one (string vs MCQ list)."""
    if isinstance(stored, list):
        return [", ".join(p for p in canonical.split(",") if p)]
    return canonical


# ---------------------------------------------------------------- loading


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise DataError(f"missing file: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(raw: dict[str, Any]) -> QuestionPayload:
    qtype = raw.get("questionType")
    if qtype not in QUESTION_TYPES:
        raise DataError(f"question {raw.get('_id')}: unknown questionType {qtype!r}")
    body = raw.get(qtype)
    if not isinstance(body, dict):
        raise DataError(f"question {raw.get('_id')}: missing '{qtype}' body")
    question_html = body.get("question") or ""
    solution_html = body.get("solution") or ""
    answer = body.get("answer")
    return QuestionPayload(
        id=raw["_id"],
        qid=raw.get("qid"),
        question_type=qtype,
        subject=raw.get("subject") or "Unknown",
        chapter=raw.get("chapter"),
        concept=raw.get("concept"),
        level=raw.get("level"),
        question_html=question_html,
        solution_html=solution_html,
        answer_raw=answer,
        answer_normalized=normalize_answer(answer, qtype),
        ques_images=body.get("quesImages") or [],
        solution_images=body.get("solutionImages") or [],
        error_history=raw.get("errorHistory") or [],
        updated_at=raw.get("updatedAt"),
        question_text=html_to_text(question_html),
        solution_text=html_to_text(solution_html),
    )


def load_dataset(data_dir: str | Path) -> Dataset:
    data_dir = Path(data_dir)
    questions_raw = _read_json(data_dir / "questions.json")
    reports_raw = _read_json(data_dir / "reports.json")
    taxonomy = _read_json(data_dir / "taxonomy.json")

    if not isinstance(questions_raw, list) or not isinstance(reports_raw, list):
        raise DataError("questions.json and reports.json must be JSON arrays")
    if "verdicts" not in taxonomy or "repairs" not in taxonomy:
        raise DataError("taxonomy.json must define 'verdicts' and 'repairs'")

    questions: dict[str, dict[str, Any]] = {}
    payloads: dict[str, QuestionPayload] = {}
    for raw in questions_raw:
        qid = raw.get("_id")
        if not qid:
            raise DataError("question without _id")
        if qid in questions:
            raise DataError(f"duplicate question _id {qid}")
        questions[qid] = raw
        payloads[qid] = build_payload(raw)

    reports = [Report(**r) for r in reports_raw]
    seen: set[str] = set()
    for r in reports:
        if r.reportId in seen:
            raise DataError(f"duplicate reportId {r.reportId}")
        seen.add(r.reportId)

    groups: dict[str, list[Report]] = {}
    missing: list[str] = []
    for r in sorted(reports, key=lambda x: (x.reportedAt or "", x.reportId)):
        groups.setdefault(r.questionId, []).append(r)
        if r.questionId not in payloads:
            missing.append(r.reportId)

    return Dataset(
        questions=questions,
        payloads=payloads,
        reports=reports,
        taxonomy=taxonomy,
        groups=groups,
        missing_question_reports=missing,
    )
