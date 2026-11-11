"""Post-run validation of results.json: schema, taxonomy keys, field scope, find-match, routes."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .ingestion import Dataset, normalize_answer
from .schemas import Result

RESULT_KEYS = {"reportId", "questionId", "verdict", "repair", "edit", "route", "confidence", "evidence", "student_reply"}
ROUTES = {"auto_apply", "faculty_review", "no_change"}


def validate_results(results: Iterable[Result | dict[str, Any]], dataset: Dataset, expected_report_ids: Optional[list[str]] = None) -> list[str]:
    errors: list[str] = []
    taxonomy = dataset.taxonomy
    rows = [r.model_dump() if isinstance(r, Result) else r for r in results]
    expected = expected_report_ids if expected_report_ids is not None else [r.reportId for r in dataset.reports]

    ids = [r.get("reportId") for r in rows]
    if len(rows) != len(expected):
        errors.append(f"expected {len(expected)} results, got {len(rows)}")
    if len(set(ids)) != len(ids):
        errors.append("duplicate reportIds in results")
    missing = set(expected) - set(ids)
    if missing:
        errors.append(f"missing results for {sorted(missing)}")

    report_q = {r.reportId: r.questionId for r in dataset.reports}
    for row in rows:
        rid = row.get("reportId")
        tag = f"{rid}:"
        if set(row) != RESULT_KEYS:
            errors.append(f"{tag} keys {sorted(row)} != required {sorted(RESULT_KEYS)}")
        if report_q.get(rid) != row.get("questionId"):
            errors.append(f"{tag} questionId does not match the report")
        verdict, repair, edit, route = row.get("verdict"), row.get("repair"), row.get("edit"), row.get("route")
        if verdict not in taxonomy["verdicts"]:
            errors.append(f"{tag} unknown verdict {verdict!r}")
        if route not in ROUTES:
            errors.append(f"{tag} unknown route {route!r}")
        conf = row.get("confidence")
        if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
            errors.append(f"{tag} confidence out of range")
        if not (row.get("evidence") or "").strip():
            errors.append(f"{tag} empty evidence")
        if not (row.get("student_reply") or "").strip():
            errors.append(f"{tag} empty student_reply")

        if verdict != "defect":
            if repair is not None or edit is not None:
                errors.append(f"{tag} non-defect verdict carries repair/edit")
            if route == "auto_apply":
                errors.append(f"{tag} non-defect verdict routed to auto_apply")
            continue

        if repair is not None and repair not in taxonomy["repairs"]:
            errors.append(f"{tag} unknown repair {repair!r}")
            continue
        spec = taxonomy["repairs"].get(repair or "", {})
        if route == "auto_apply" and (not spec.get("auto") or edit is None):
            errors.append(f"{tag} auto_apply without an auto-eligible repair and edit")
        if edit is None:
            continue
        if edit.get("field") not in spec.get("fields", []):
            errors.append(f"{tag} edit field {edit.get('field')!r} outside {repair} scope")
            continue
        payload = dataset.payloads.get(row.get("questionId"))
        if payload is None:
            continue
        field = edit["field"]
        if field == "answer":
            if normalize_answer(edit["find"], payload.question_type) != payload.answer_normalized:
                errors.append(f"{tag} answer find does not match stored key")
        elif field == "questionType":
            if edit["find"] != payload.question_type:
                errors.append(f"{tag} questionType find does not match stored type")
        else:
            raw = payload.question_html if field == "question" else payload.solution_html
            find = edit["find"]
            if find and raw.count(find) != 1:
                errors.append(f"{tag} find occurs {raw.count(find)} times in raw {field}")
    return errors
