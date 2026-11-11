"""Merge single-report outputs into output/results.json and cases.json.

Skips rate-limited / failed-comparator placeholders so they cannot overwrite good rows.

  python -m engine.merge_results
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _is_rate_limited_placeholder(res: dict, case: dict | None) -> bool:
    evidence = (res.get("evidence") or "").lower()
    if "rate limit" in evidence or "free-models-per-day" in evidence:
        return True
    if case:
        for f in case.get("failures") or []:
            fl = str(f).lower()
            if "rate limit" in fl or "free-models-per-day" in fl:
                return True
        if res.get("confidence", 1) <= 0.25 and res.get("verdict") == "not_actionable":
            # Only skip if a failure was recorded for this run.
            if case.get("failures"):
                return True
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="src", default=str(ROOT / "output" / "single"))
    parser.add_argument("--results", default=str(ROOT / "output" / "results.json"))
    parser.add_argument("--cases", default=str(ROOT / "output" / "cases.json"))
    args = parser.parse_args(argv)

    src = Path(args.src)
    results_path = Path(args.results)
    cases_path = Path(args.cases)
    results = {r["reportId"]: r for r in json.loads(results_path.read_text(encoding="utf-8"))}
    cases = {c["reportId"]: c for c in json.loads(cases_path.read_text(encoding="utf-8"))}

    updated, skipped = [], []
    for path in sorted(src.glob("R*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        res = payload.get("result") or payload
        case = payload.get("case")
        rid = res["reportId"]
        if _is_rate_limited_placeholder(res, case):
            skipped.append(rid)
            print(f"skip {rid}: rate-limited / failed placeholder")
            continue
        results[rid] = res
        if case:
            cases[rid] = case
        updated.append(rid)
        print(f"merged {rid}: {res['verdict']}/{res.get('repair')} -> {res['route']}")

    ordered_results = [results[k] for k in sorted(results)]
    ordered_cases = [cases[k] for k in sorted(cases)]
    results_path.write_text(json.dumps(ordered_results, ensure_ascii=False, indent=2), encoding="utf-8")
    cases_path.write_text(json.dumps(ordered_cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"updated {len(updated)}; skipped {len(skipped)} -> {results_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
