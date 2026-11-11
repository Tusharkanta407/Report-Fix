"""Per-report step 2: compare all evidence and propose verdict / repair / surgical edit."""

from __future__ import annotations

import json
from typing import Any, Optional

from .llm import LLMClient, LLMFailure, load_prompt
from .schemas import (
    CommentHints,
    ContentChecks,
    Interpretation,
    Proposal,
    QuestionPayload,
    Report,
    SolutionReading,
    SolverResult,
)

MAX_RAW_CHARS = 9000


def _taxonomy_block(taxonomy: dict[str, Any]) -> str:
    verdicts = "\n".join(f"- {k}: {v}" for k, v in taxonomy["verdicts"].items())
    repairs = "\n".join(
        f"- {k} (fields={v.get('fields', [])}, auto={str(v.get('auto')).lower()}): {v.get('label', '')}"
        for k, v in taxonomy["repairs"].items()
    )
    return f"VERDICTS:\n{verdicts}\n\nREPAIRS:\n{repairs}"


def _checks_block(checks: ContentChecks) -> str:
    data = checks.model_dump(exclude={"options"})
    data["options_parsed"] = {o.letter: o.text[:120] for o in checks.options}
    return json.dumps({k: v for k, v in data.items() if v not in (None, [], {}, False)}, ensure_ascii=False)


def _clip(text: str) -> str:
    return text if len(text) <= MAX_RAW_CHARS else text[:MAX_RAW_CHARS] + "\n...[truncated]"


def comparator_user_message(
    *,
    taxonomy: dict[str, Any],
    report: Report,
    payload: QuestionPayload,
    checks: ContentChecks,
    hints: CommentHints,
    interpretation: Interpretation,
    solver: Optional[SolverResult],
    solver_failure: Optional[str],
    reading: Optional[SolutionReading],
    reading_failure: Optional[str],
    sibling_comments: list[str],
) -> str:
    solver_txt = solver.model_dump_json() if solver else f"UNAVAILABLE ({solver_failure})"
    reading_txt = reading.model_dump_json() if reading else f"UNAVAILABLE ({reading_failure})"
    history = json.dumps(payload.error_history, ensure_ascii=False) if payload.error_history else "[]"
    siblings = "\n".join(f"- {c}" for c in sibling_comments) or "(none)"
    return f"""{_taxonomy_block(taxonomy)}

QUESTION {payload.id}
subject={payload.subject} | chapter={payload.chapter} | concept={payload.concept} | type={payload.question_type} | updatedAt={payload.updated_at}
images attached: question={len(payload.ques_images)}, solution={len(payload.solution_images)}

<question_text>
{payload.question_text}
</question_text>

<question_raw_html>
{_clip(payload.question_html)}
</question_raw_html>

<solution_text>
{payload.solution_text or '(empty)'}
</solution_text>

<solution_raw_html>
{_clip(payload.solution_html)}
</solution_raw_html>

STORED ANSWER KEY (raw): {json.dumps(payload.answer_raw, ensure_ascii=False)}  | normalized: {payload.answer_normalized}
ERROR HISTORY: {history}

INDEPENDENT SOLVE (no key, no solution, no comment): {solver_txt}
SOLUTION AUDIT (no key, no comment): {reading_txt}
DETERMINISTIC SCANS: {_checks_block(checks)}

COMMENT INTERPRETATION: {interpretation.model_dump_json()}
RULE HINTS: intents={hints.intent_hints} injection_flags={hints.injection_flags} quoted_terms_present_in_live_text={hints.quoted_terms_present}
OTHER STUDENTS ON THIS QUESTION:
{siblings}

REPORT {report.reportId} (source={report.source}, at={report.reportedAt})
<student_comment>
{hints.cleaned or '(empty)'}
</student_comment>
"""


def compare(client: LLMClient, user_message: str, report_id: str, question_id: str) -> tuple[Optional[Proposal], Optional[str]]:
    try:
        proposal = client.structured(
            step="comparator",
            model=client.config.main,
            prompt=load_prompt("comparator"),
            user=user_message,
            schema=Proposal,
            question_id=question_id,
            report_id=report_id,
        )
        return proposal, None
    except LLMFailure as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"comparator error: {type(exc).__name__}: {exc}"


NON_CONTENT_VERDICT = {"app": "app_issue", "display": "display_issue", "language": "language_mode"}


def fallback_proposal(interpretation: Interpretation, reason: str) -> Proposal:
    """Used when the comparator failed. Low confidence; the orchestrator also forces faculty review."""
    verdict = NON_CONTENT_VERDICT.get(interpretation.category, "not_actionable")
    return Proposal(
        verdict=verdict,
        repair=None,
        edit=None,
        llm_confidence=0.2,
        independent_confirmation=False,
        checks=[],
        evidence=f"Automated comparison failed ({reason[:160]}); student claim: {interpretation.claim_summary}",
        faculty_note="Pipeline could not verify this report; please review manually.",
    )
