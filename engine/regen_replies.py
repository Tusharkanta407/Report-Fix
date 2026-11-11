"""Regenerate only student_reply fields from an existing cases.json.

  python -m engine.regen_replies            # try LLM, fall back to templates
  python -m engine.regen_replies --offline  # templates only (no API)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .ingestion import load_dataset
from .llm import LLMClient, ModelConfig
from .reply_generator import fallback_reply, generate_reply, key_fact_for
from .schemas import FinalEdit, GuardDecision
from .token_meter import TokenMeter

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="template replies only; no LLM")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    out = ROOT / "output"
    cases_path = out / "cases.json"
    results_path = out / "results.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    results = json.loads(results_path.read_text(encoding="utf-8"))
    by_id = {r["reportId"]: r for r in results}
    dataset = load_dataset(ROOT / "data")
    client = LLMClient(ModelConfig.from_env(), TokenMeter(), offline=args.offline)

    print(f"[regen] {len(cases)} replies ({'offline templates' if args.offline else client.config.fast})")
    for case in cases:
        rid = case["reportId"]
        decision_raw = case["decision"]
        edit = decision_raw.get("edit")
        decision = GuardDecision(
            verdict=decision_raw["verdict"],
            repair=decision_raw.get("repair"),
            edit=FinalEdit(**edit) if edit else None,
            route=decision_raw["route"],
            confidence=decision_raw["confidence"],
            independent_confirmation=case.get("independent_confirmation", False),
        )
        repair_label = dataset.taxonomy["repairs"].get(decision.repair or "", {}).get("label", "")
        evidence = (case.get("proposal") or {}).get("evidence") or decision_raw.get("evidence") or ""
        solver = case.get("solver") or {}
        fact = key_fact_for(decision, solver.get("working"), evidence)
        if args.offline:
            reply, notes = fallback_reply(decision, fact), ["offline template"]
        else:
            reply, notes = generate_reply(
                client,
                report_id=rid,
                question_id=case["questionId"],
                comment=(case.get("hints") or {}).get("cleaned") or case.get("comment") or "",
                decision=decision,
                evidence=evidence,
                repair_label=repair_label,
                key_fact=fact,
            )
        case["student_reply"] = reply
        case["decision"]["student_reply"] = reply
        case["reply_notes"] = notes
        by_id[rid]["student_reply"] = reply
        print(f"  {rid}: {reply[:120]}")

    for r in results:
        r["student_reply"] = by_id[r["reportId"]]["student_reply"]
    results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    cases_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    usage = client.meter.summary()
    print(f"[regen] done ~${usage['run_totals']['estimated_usd']:.4f}  tokens {usage['run_totals']['total_tokens']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
