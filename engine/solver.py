"""Question-level work, done once per unique question and cached by content fingerprint.

1. Independent solver: subject-aware prompt; sees only the question (no key, no solution, no comment).
2. Solution reader: sees question + stored solution (no key, no comment); reports what it concludes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .cache import SolveCache, fingerprint
from .content_checks import inspect_question
from .llm import LLMClient, LLMFailure, load_prompt
from .schemas import QuestionPayload, SolutionReading, SolverResult
from .token_meter import CallRecord

_EQ_VALUE = re.compile(
    r"(?:=|≈|\\approx)\s*([-+]?\d+(?:\.\d+)?)\s*(?:cm|mm|m|V|A|N|kg|g|μ|µ)?\b",
    re.IGNORECASE,
)

SUBJECT_PROMPTS = {
    "physics": "solver_physics",
    "mathematics": "solver_maths",
    "maths": "solver_maths",
    "math": "solver_maths",
    "chemistry": "solver_chemistry",
    "biology": "solver_biology",
    "botany": "solver_biology",
    "zoology": "solver_biology",
}
TYPE_LABEL = {
    "scq": "scq (single correct option)",
    "mcq": "mcq (one or more correct options)",
    "integerQuestion": "integerQuestion (numeric answer)",
}


def solver_prompt_name(subject: str) -> str:
    return SUBJECT_PROMPTS.get((subject or "").strip().lower(), "solver_physics")


@dataclass
class QuestionWork:
    question_id: str
    solver: Optional[SolverResult] = None
    solver_failure: Optional[str] = None
    reading: Optional[SolutionReading] = None
    reading_failure: Optional[str] = None
    prompt_versions: dict[str, str] = field(default_factory=dict)
    cache_hits: list[str] = field(default_factory=list)

    @property
    def failures(self) -> list[str]:
        return [f for f in (self.solver_failure, self.reading_failure) if f]


def _images_note(payload: QuestionPayload) -> str:
    if payload.ques_images:
        return f"The question has {len(payload.ques_images)} attached image(s) that you cannot see."
    return "No images are attached to this question."


def solver_user_message(payload: QuestionPayload) -> str:
    return (
        f"Subject: {payload.subject}\n"
        f"Chapter (as filed): {payload.chapter or 'unknown'}\n"
        f"Question type: {TYPE_LABEL.get(payload.question_type, payload.question_type)}\n"
        f"{_images_note(payload)}\n\n"
        f"<question>\n{payload.question_text}\n</question>"
    )


def reader_user_message(payload: QuestionPayload) -> str:
    return (
        f"Subject: {payload.subject}\n"
        f"Question type: {TYPE_LABEL.get(payload.question_type, payload.question_type)}\n\n"
        f"<question>\n{payload.question_text}\n</question>\n\n"
        f"<stored_solution>\n{payload.solution_text or '(empty)'}\n</stored_solution>"
    )


def _last_computed_number(working: str) -> Optional[str]:
    """Last `= <number>` in working — the arithmetic conclusion before any closing prose."""
    if not working:
        return None
    matches = list(_EQ_VALUE.finditer(working))
    if not matches:
        return None
    return matches[-1].group(1)


def _option_letter_for_value(payload: QuestionPayload, value: str) -> Optional[str]:
    try:
        target = float(value.replace(",", ""))
    except ValueError:
        target = None
    checks = inspect_question(payload)
    for opt in checks.options or []:
        text = (opt.text or "").strip()
        if not text:
            continue
        if text == value or text.replace(" ", "") == value.replace(" ", ""):
            return opt.letter
        if target is not None:
            m = re.search(r"[-+]?\d+(?:\.\d+)?", text)
            if m:
                try:
                    if abs(float(m.group(0)) - target) < 1e-9:
                        return opt.letter
                except ValueError:
                    pass
    return None


def align_final_answer_to_working(solver: SolverResult, payload: QuestionPayload) -> SolverResult:
    """If working's last computed number disagrees with final_answer, trust the working."""
    if not solver or not solver.can_solve or not solver.working:
        return solver
    last = _last_computed_number(solver.working)
    if not last:
        return solver
    final = (solver.final_answer or "").strip()
    qtype = payload.question_type

    # Integer: final must equal last number.
    if qtype == "integerQuestion":
        try:
            if abs(float(final.replace(",", "")) - float(last)) > 1e-9:
                notes = list(solver.observations or [])
                notes.append(f"aligned final_answer {final!r} → {last!r} from working arithmetic")
                return solver.model_copy(update={"final_answer": last, "observations": notes})
        except ValueError:
            notes = list(solver.observations or [])
            notes.append(f"aligned final_answer {final!r} → {last!r} from working arithmetic")
            return solver.model_copy(update={"final_answer": last, "observations": notes})
        return solver

    # SCQ/MCQ: map last number to option letter; override contradictory letter.
    letter = _option_letter_for_value(payload, last)
    if letter and final.upper() != letter.upper():
        notes = list(solver.observations or [])
        notes.append(
            f"aligned final_answer {final!r} → {letter!r} because working concluded {last}"
        )
        opts = [letter] if qtype == "scq" else sorted(set((solver.correct_options or []) + [letter]))
        return solver.model_copy(
            update={"final_answer": letter, "correct_options": opts, "observations": notes}
        )
    return solver


def _cached_call(client: LLMClient, cache: SolveCache, payload: QuestionPayload, step: str, prompt_name: str, model: str, schema, user: str, work: QuestionWork):
    prompt = load_prompt(prompt_name)
    work.prompt_versions[step] = f"{prompt.name}@{prompt.version}"
    key = fingerprint(payload, step, f"{prompt.name}@{prompt.version}", model)
    hit = cache.get(step, key)
    if hit is not None:
        try:
            result = schema.model_validate(hit)
            client.meter.record(CallRecord(step, model, payload.id, None, cache_hit=True))
            work.cache_hits.append(step)
            return result
        except Exception:
            pass
    result = client.structured(
        step=step, model=model, prompt=prompt, user=user, schema=schema,
        question_id=payload.id, report_id=None,
    )
    cache.put(step, key, result.model_dump())
    return result


def run_question_work(client: LLMClient, cache: SolveCache, payload: QuestionPayload) -> QuestionWork:
    work = QuestionWork(question_id=payload.id)
    model = client.config.solver
    try:
        work.solver = _cached_call(
            client, cache, payload, "solver", solver_prompt_name(payload.subject), model,
            SolverResult, solver_user_message(payload), work,
        )
        if work.solver is not None:
            work.solver = align_final_answer_to_working(work.solver, payload)
    except LLMFailure as exc:
        work.solver_failure = str(exc)
    except Exception as exc:  # never let one question crash the run
        work.solver_failure = f"solver error: {type(exc).__name__}: {exc}"

    try:
        work.reading = _cached_call(
            client, cache, payload, "solution_reader", "solution_reader", client.config.main,
            SolutionReading, reader_user_message(payload), work,
        )
    except LLMFailure as exc:
        work.reading_failure = str(exc)
    except Exception as exc:
        work.reading_failure = f"solution reader error: {type(exc).__name__}: {exc}"
    return work
