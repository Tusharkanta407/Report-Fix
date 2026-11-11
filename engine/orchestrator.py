"""Intent-first pipeline (token-minimised).

Ideal spend order:
  1. What is the student asking? (rules + mini on REPORT only)
  2. Taxonomy tier:
       L0 — cosmetic / chapter / app → fix or flag, NEVER solve
       L1 — unit/form vs stored solution → explain, NEVER gpt-4o solve
       L2 — answer/solution wrong → solve once per question (strong model)
  3. taxonomy_guard → student reply (mini / template)
  4. validate

Do not re-solve spelling, chapter, NEET tags, or 0.08↔8 unit confusions.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .cache import SolveCache
from .comparator import compare, comparator_user_message, fallback_proposal
from .content_checks import inspect_question
from .fast_path import interpretation_from_hints, try_deterministic_proposal
from .ingestion import Dataset
from .interpreter import interpret
from .llm import LLMClient
from .normalizer import normalize_comment
from .reply_generator import fallback_reply, generate_reply, key_fact_for
from .routing import spend_tier
from .schemas import CommentHints, ContentChecks, GuardDecision, Interpretation, Proposal, Report, Result
from .solution_first import try_solution_first_no_error
from .solver import QuestionWork, run_question_work
from .taxonomy_guard import GuardContext, decide
from .unit_form_path import try_unit_form_from_stored
from .validation import validate_results

ACADEMIC_VERDICTS = {"defect", "no_error", "not_actionable"}

TEMPLATE_REPAIRS = {
    "spelling",
    "exam_reference",
    "noise",
    "markup_leak",
    "wrong_chapter",
    "syllabus",
    "identical_options",
    "diagram",
    None,
}


@dataclass
class RunOutput:
    results: list[Result]
    cases: list[dict[str, Any]]
    usage: dict[str, Any]
    validation_errors: list[str]
    question_work: dict[str, QuestionWork] = field(default_factory=dict)


@dataclass
class _ReportPrep:
    report: Report
    hints: CommentHints
    checks: ContentChecks
    interpretation: Optional[Interpretation]
    fast: Optional[Proposal]
    tier: str
    failures: list[str] = field(default_factory=list)


def _missing_question_case(report: Report, taxonomy: dict[str, Any]) -> tuple[Result, dict[str, Any]]:
    decision = GuardDecision(
        verdict="not_actionable",
        repair=None,
        edit=None,
        route="faculty_review",
        confidence=0.0,
        downgrades=["question record not found; nothing was verified"],
    )
    evidence = f"Question {report.questionId} is not in questions.json; the report could not be checked."
    reply = fallback_reply(decision)
    result = Result(
        reportId=report.reportId,
        questionId=report.questionId,
        verdict=decision.verdict,
        repair=None,
        edit=None,
        route=decision.route,
        confidence=0.0,
        evidence=evidence,
        student_reply=reply,
    )
    case = {
        "reportId": report.reportId,
        "questionId": report.questionId,
        "comment": report.comment,
        "failures": ["question record missing"],
        "decision": decision.model_dump(),
        "evidence": evidence,
        "student_reply": reply,
    }
    return result, case


def _empty_question_work(question_id: str, reason: str) -> QuestionWork:
    work = QuestionWork(question_id=question_id)
    work.prompt_versions = {"solver": "skipped", "solution_reader": "skipped"}
    work.cache_hits = []
    work.solver_failure = None
    work.reading_failure = None
    setattr(work, "skip_reason", reason)
    return work


def _category_from_fast(fast: Proposal) -> tuple[str, str]:
    category = {
        "exam_reference": "exam_reference",
        "spelling": "spelling",
        "markup_leak": "markup_leak",
        "wrong_chapter": "wrong_chapter",
        "syllabus": "syllabus",
        "identical_options": "identical_options",
        "option_repair": "blank_option",
        "diagram": "figure_missing",
        "solution_fix": "unit_or_format",
        "app_issue": "app",
        "display_issue": "display",
        "language_mode": "language",
        "no_error": "unclear",
        "not_actionable": "empty",
        "already_fixed": "spelling",
    }.get(fast.repair or fast.verdict, "unclear")
    target = {
        "wrong_chapter": "metadata",
        "syllabus": "metadata",
        "app": "app",
        "display": "app",
        "language": "app",
        "none": "none",
        "unclear": "none",
        "empty": "none",
    }.get(category, "question")
    return category, target


def _prepare_report(
    report: Report,
    dataset: Dataset,
    client: LLMClient,
    checks: ContentChecks,
) -> _ReportPrep:
    """Phase 1: intent only. No solver. Mini only if rules cannot classify."""
    payload = dataset.payloads[report.questionId]
    hints = normalize_comment(report.comment, payload)
    failures: list[str] = []

    fast = try_deterministic_proposal(hints, checks, payload)
    if fast is not None:
        cat, target = _category_from_fast(fast)
        interpretation = interpretation_from_hints(hints, category=cat, target=target)
        tier = spend_tier(hints, interpretation)
        # Deterministic proposal forces L0/L1 behaviour.
        if fast.repair in {"wrong_chapter", "syllabus", "spelling", "exam_reference", "markup_leak", "identical_options", "diagram"}:
            tier = "L0"
        elif fast.repair == "solution_fix":
            tier = "L1"
        return _ReportPrep(report, hints, checks, interpretation, fast, tier, failures)

    interpretation, err = interpret(client, report.reportId, payload.id, hints, payload)
    if err:
        failures.append(err)
    tier = spend_tier(hints, interpretation)
    # If claimed number is only a unit-scale of the key, force L1 (no strong solve).
    if interpretation is not None and try_unit_form_from_stored(
        interpretation=interpretation, hints=hints, payload=payload
    ) is not None:
        tier = "L1"
    return _ReportPrep(report, hints, checks, interpretation, None, tier, failures)


def _finalize(
    prep: _ReportPrep,
    dataset: Dataset,
    client: LLMClient,
    work: QuestionWork,
    proposal: Proposal,
    used_fast_path: bool,
    forced: list[str],
) -> tuple[Result, dict[str, Any]]:
    taxonomy = dataset.taxonomy
    report = prep.report
    payload = dataset.payloads[report.questionId]
    failures = list(prep.failures) + list(work.failures)

    claimed = ""
    if prep.interpretation and prep.interpretation.claimed_answer:
        claimed = prep.interpretation.claimed_answer
    elif prep.hints.claimed_values:
        claimed = prep.hints.claimed_values[0]
    ctx = GuardContext(
        payload=payload,
        checks=prep.checks,
        solver=work.solver,
        reading=work.reading,
        forced_review=forced,
        claimed_answer=claimed or None,
    )
    decision = decide(proposal, ctx, taxonomy)
    repair_label = taxonomy["repairs"].get(decision.repair or "", {}).get("label", "")
    published_evidence = decision.faculty_evidence or proposal.evidence
    published_note = decision.faculty_note or proposal.faculty_note

    # Never draft a "you're right / we fixed it" reply from a rejected defect proposal.
    # Guard may flip answer_key → no_error; evidence still reads like a flip.
    guard_blocked_flip = any("conflict flip" in r or "rejected" in r for r in (decision.rejections or []))
    use_template = (
        (used_fast_path and decision.repair in TEMPLATE_REPAIRS)
        or decision.verdict in {"no_error", "already_fixed", "app_issue", "display_issue", "language_mode", "not_actionable"}
        or guard_blocked_flip
        or decision.repair in {"wrong_chapter", "syllabus"}
        or bool(decision.faculty_evidence)
    )

    if use_template:
        # Never pass raw evidence into the student-facing template.
        key_fact = ""
        if decision.edit is not None and decision.edit.field == "answer":
            key_fact = f"correct answer is {decision.edit.replace}"
        elif decision.edit is not None and decision.repair == "spelling":
            key_fact = f"{decision.edit.find} → {decision.edit.replace}"
        reply = fallback_reply(decision, key_fact)
        reply_notes = ["template reply (teacher voice, no evidence paste)"]
    else:
        reply, reply_notes = generate_reply(
            client,
            report_id=report.reportId,
            question_id=payload.id,
            comment=prep.hints.cleaned,
            decision=decision,
            evidence=published_evidence,
            repair_label=repair_label,
            key_fact=key_fact_for(
                decision,
                work.solver.working if work.solver else None,
                published_evidence,
            ),
        )

    result = Result(
        reportId=report.reportId,
        questionId=payload.id,
        verdict=decision.verdict,
        repair=decision.repair,
        edit=decision.edit,
        route=decision.route,
        confidence=decision.confidence,
        evidence=published_evidence,
        student_reply=reply,
    )
    group = dataset.groups.get(payload.id, [])
    case = {
        "reportId": report.reportId,
        "questionId": payload.id,
        "studentId": report.studentId,
        "source": report.source,
        "reportedAt": report.reportedAt,
        "comment": report.comment,
        "question": {
            "qid": payload.qid,
            "subject": payload.subject,
            "chapter": payload.chapter,
            "concept": payload.concept,
            "level": payload.level,
            "questionType": payload.question_type,
            "answer_raw": payload.answer_raw,
            "answer_normalized": payload.answer_normalized,
            "error_history": payload.error_history,
        },
        "siblings": {
            "report_ids": [r.reportId for r in group],
            "report_count": len(group),
            "unique_students": len({r.studentId for r in group}),
        },
        "hints": prep.hints.model_dump(),
        "content_checks": prep.checks.model_dump(),
        "interpretation": prep.interpretation.model_dump() if prep.interpretation else None,
        "spend_tier": prep.tier,
        "solver": work.solver.model_dump() if work.solver else None,
        "solution_reading": work.reading.model_dump() if work.reading else None,
        "prompt_versions": work.prompt_versions,
        "question_cache_hits": work.cache_hits,
        "fast_path": used_fast_path,
        "proposal": proposal.model_dump(),
        "llm_confidence": proposal.llm_confidence,
        "independent_confirmation": decision.independent_confirmation,
        "guard": {"rejections": decision.rejections, "downgrades": decision.downgrades},
        "decision": result.model_dump(),
        "preview": {
            "field": decision.edit.field if decision.edit else None,
            "before": decision.before,
            "after": decision.after,
        },
        "faculty_note": published_note,
        "reply_notes": reply_notes,
        "failures": failures,
    }
    return result, case


def process_report_with_prep(
    prep: _ReportPrep,
    dataset: Dataset,
    client: LLMClient,
    work: QuestionWork,
) -> tuple[Result, dict[str, Any]]:
    """Phases 3–4 for one report after solves (if any) are done."""
    report = prep.report
    payload = dataset.payloads.get(report.questionId)
    if payload is None:
        return _missing_question_case(report, dataset.taxonomy)

    forced: list[str] = []
    used_fast = False

    if prep.fast is not None:
        return _finalize(prep, dataset, client, work, prep.fast, True, forced)

    assert prep.interpretation is not None

    # L1: unit/form from stored solution — never call comparator with a fresh solve.
    if prep.tier == "L1" or prep.interpretation.category in {"unit_or_format", "answer_form"}:
        unit = try_unit_form_from_stored(
            interpretation=prep.interpretation,
            hints=prep.hints,
            payload=payload,
        )
        if unit is not None:
            return _finalize(prep, dataset, client, work, unit, True, forced)

    # L0 should have been caught by deterministic; if mini said chapter etc., force metadata proposal.
    if prep.tier == "L0":
        chapter = payload.chapter or "(unknown)"
        cat = prep.interpretation.category
        if cat == "wrong_chapter":
            prop = Proposal(
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
            return _finalize(prep, dataset, client, work, prop, True, forced)
        if cat in {"spelling", "exam_reference", "markup_leak", "syllabus", "app", "display", "language"}:
            # Fall through to comparator only if we somehow have no deterministic edit —
            # still forbid strong solve (work should be empty).
            pass

    # Solution-first (uses stored reading if solve ran; else may no-op).
    solution_first = try_solution_first_no_error(
        interpretation=prep.interpretation,
        hints=prep.hints,
        payload=payload,
        solver=work.solver,
        reading=work.reading,
    )
    if solution_first is not None:
        return _finalize(prep, dataset, client, work, solution_first, True, forced)

    # Also try unit path for answer_key comments that are really 0.08 vs 8.
    unit = try_unit_form_from_stored(
        interpretation=prep.interpretation,
        hints=prep.hints,
        payload=payload,
    )
    if unit is not None:
        return _finalize(prep, dataset, client, work, unit, True, forced)

    # L2 (or leftover): comparator. If solve was skipped, force faculty on academic repairs.
    siblings = dataset.siblings(report)
    user_msg = comparator_user_message(
        taxonomy=dataset.taxonomy,
        report=report,
        payload=payload,
        checks=prep.checks,
        hints=prep.hints,
        interpretation=prep.interpretation,
        solver=work.solver,
        solver_failure=work.solver_failure,
        reading=work.reading,
        reading_failure=work.reading_failure,
        sibling_comments=[s.comment or "" for s in siblings],
    )
    # Prefer fast model when we never solved (shouldn't be L2); main when we did.
    raw_proposal, comp_failure = compare(client, user_msg, report.reportId, payload.id)
    if comp_failure or raw_proposal is None:
        prep.failures.append(comp_failure or "comparator returned nothing")
        proposal = fallback_proposal(prep.interpretation, comp_failure or "no output")
        forced.append("comparator failed; decision not verified")
    else:
        proposal = raw_proposal

    if work.solver_failure and proposal.verdict in ACADEMIC_VERDICTS:
        forced.append("independent solver unavailable for an academic decision")
    skip_reason = getattr(work, "skip_reason", None)
    if skip_reason and proposal.verdict in ACADEMIC_VERDICTS and proposal.repair in {
        "answer_key",
        "stem_data",
        "solution_fix",
        "solution_missing",
        "option_repair",
        "type_mismatch",
    }:
        forced.append(f"academic solve was skipped ({skip_reason}); cannot auto-apply academic repair")

    return _finalize(prep, dataset, client, work, proposal, used_fast, forced)


# Back-compat name used by tests.
def process_report(
    report: Report,
    dataset: Dataset,
    client: LLMClient,
    work: Optional[QuestionWork],
    checks: Optional[ContentChecks],
) -> tuple[Result, dict[str, Any]]:
    if work is None or checks is None or report.questionId not in dataset.payloads:
        return _missing_question_case(report, dataset.taxonomy)
    prep = _prepare_report(report, dataset, client, checks)
    # If caller already solved, keep tier from prep but use provided work.
    return process_report_with_prep(prep, dataset, client, work)


def run_pipeline(
    dataset: Dataset,
    client: LLMClient,
    cache: SolveCache,
    report_ids: Optional[list[str]] = None,
    workers: int = 4,
    log: Callable[[str], None] = print,
) -> RunOutput:
    reports = dataset.reports
    if report_ids:
        wanted = set(report_ids)
        reports = [r for r in reports if r.reportId in wanted]
        unknown = wanted - {r.reportId for r in reports}
        if unknown:
            raise ValueError(f"unknown report ids: {sorted(unknown)}")

    question_ids = sorted({r.questionId for r in reports if r.questionId in dataset.payloads})
    checks = {qid: inspect_question(dataset.payloads[qid]) for qid in question_ids}

    # ----- Phase 1: INTENT for every report (rules → maybe mini). NO solver. -----
    log(f"[engine] phase1 intent: {len(reports)} reports (mini/rules only, no solve)")
    preps: list[_ReportPrep] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        def _prep(r: Report) -> _ReportPrep:
            return _prepare_report(r, dataset, client, checks[r.questionId])

        preps = list(pool.map(_prep, reports))

    prep_by_id = {p.report.reportId: p for p in preps}
    tier_counts = {"L0": 0, "L1": 0, "L2": 0}
    for p in preps:
        tier_counts[p.tier] = tier_counts.get(p.tier, 0) + 1
    log(f"[engine] tiers: L0={tier_counts['L0']} L1={tier_counts['L1']} L2={tier_counts['L2']}")

    # ----- Phase 2: SOLVE only questions that have ≥1 L2 sibling -----
    to_solve: list[str] = []
    for qid in question_ids:
        sibling_preps = [p for p in preps if p.report.questionId == qid]
        if any(p.tier == "L2" for p in sibling_preps):
            to_solve.append(qid)

    skipped = [qid for qid in question_ids if qid not in to_solve]
    log(
        f"[engine] phase2 solve: {len(to_solve)} questions need strong solve; "
        f"{len(skipped)} skipped (L0/L1 only)"
    )

    work: dict[str, QuestionWork] = {}
    for qid in skipped:
        work[qid] = _empty_question_work(qid, "L0/L1 intent — solve not required")
        log(f"  skip-solve {qid} [{dataset.payloads[qid].subject}]")

    def _solve(qid: str) -> QuestionWork:
        w = run_question_work(client, cache, dataset.payloads[qid])
        status = "cache" if len(w.cache_hits) == 2 else ("FAILED" if w.failures else "ok")
        log(f"  solved {qid} [{dataset.payloads[qid].subject}] {status}")
        return w

    if to_solve:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for w in pool.map(_solve, to_solve):
                work[w.question_id] = w

    # ----- Phase 3: decide each report -----
    log(f"[engine] phase3 decide: {len(reports)} reports")

    def _decide(report: Report) -> tuple[Result, dict[str, Any]]:
        prep = prep_by_id[report.reportId]
        res, case = process_report_with_prep(prep, dataset, client, work[report.questionId])
        tag = f"{prep.tier}/{'fast' if case.get('fast_path') else 'llm'}"
        log(f"  {res.reportId} [{tag}]: {res.verdict}/{res.repair or '-'} -> {res.route} ({res.confidence:.2f})")
        return res, case

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        pairs = list(pool.map(_decide, reports))

    pairs.sort(key=lambda p: p[0].reportId)
    results = [p[0] for p in pairs]
    cases = [p[1] for p in pairs]

    groups = {
        qid: [r.reportId for r in dataset.groups[qid] if r in reports]
        for qid in dataset.groups
        if any(r in reports for r in dataset.groups[qid])
    }
    decisions = {r.reportId: r.model_dump() for r in results}
    usage = client.meter.summary(decisions, groups)
    for case in cases:
        qid = case["questionId"]
        case["tokens"] = client.meter.report_tokens(case["reportId"], qid, len(groups.get(qid, [])) or 1)

    errors = validate_results(results, dataset, expected_report_ids=[r.reportId for r in reports])
    return RunOutput(results=results, cases=cases, usage=usage, validation_errors=errors, question_work=work)
