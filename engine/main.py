"""CLI.

  python -m engine.main run                    # all reports -> output/results.json, cases.json, usage.json
  python -m engine.main run --report R005      # one report -> output/single/R005.json
  python -m engine.main run --offline          # no LLM calls; exercises failure paths -> output/offline/
  python -m engine.main validate               # re-validate output/results.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_usage(usage: dict) -> None:
    run = usage["run_totals"]
    print("\n== Token usage ==")
    print(f"total {run['total_tokens']:,} tokens  (prompt {run['prompt_tokens']:,} / completion {run['completion_tokens']:,})"
          f"  calls {run['calls']}  failed {run.get('failed_calls', 0)}  cache hits {run['cache_hits']}  ~${run['estimated_usd']:.4f}")
    print("by step:")
    for step, b in sorted(usage["by_step"].items()):
        print(f"  {step:<16} {b['total_tokens']:>9,} tok  calls {b['calls']:>3}  cache {b['cache_hits']:>3}  ~${b['estimated_usd']:.4f}")
    print("avg tokens per report, by repair/verdict:")
    for key, b in sorted(usage["by_repair_or_verdict"].items(), key=lambda kv: -kv[1]["avg_tokens_per_report"]):
        print(f"  {key:<18} {b['avg_tokens_per_report']:>9,.0f}  ({b['reports']} reports)")
    top = sorted(usage["by_questionId"].items(), key=lambda kv: -kv[1]["total_tokens"])[:5]
    print("highest-cost questions:")
    for qid, b in top:
        print(f"  {qid}  {b['total_tokens']:>8,} tok  reports={len(b.get('reportIds', []))}")


def cmd_run(args) -> int:
    from .cache import SolveCache
    from .ingestion import load_dataset
    from .llm import LLMClient, ModelConfig
    from .orchestrator import run_pipeline
    from .token_meter import TokenMeter

    load_dotenv(ROOT / ".env")
    if not args.offline and not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")):
        print("Set OPENAI_API_KEY or OPENROUTER_API_KEY in .env. Use --offline to exercise the pipeline without LLM calls.")
        return 2

    dataset = load_dataset(args.data)
    config = ModelConfig.from_env()
    meter = TokenMeter()
    client = LLMClient(config, meter, offline=args.offline)
    out_dir = Path(args.out)
    cache = SolveCache(out_dir / ".cache", enabled=not args.no_cache and not args.offline)
    print(f"[engine] provider={config.provider} main={config.main} fast={config.fast} solver={config.solver}"
          f"{' OFFLINE' if args.offline else ''}")

    output = run_pipeline(dataset, client, cache, report_ids=args.report or None, workers=args.workers)

    results = [r.model_dump() for r in output.results]
    if args.report:
        target = out_dir / "single"
        for res, case in zip(results, output.cases):
            _write(target / f"{res['reportId']}.json", {"result": res, "case": case})
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        target = out_dir / "offline" if args.offline else out_dir
        _write(target / "results.json", results)
        _write(target / "cases.json", output.cases)
        _write(target / "usage.json", output.usage | {"calls": meter.raw()})
        print(f"\nwrote {target / 'results.json'} ({len(results)} results), cases.json, usage.json")

    routes: dict[str, int] = {}
    for r in results:
        routes[r["route"]] = routes.get(r["route"], 0) + 1
    print(f"routes: {routes}")
    _print_usage(output.usage)

    if output.validation_errors:
        print("\nVALIDATION FAILED:")
        for e in output.validation_errors:
            print("  -", e)
        return 1
    print("\nvalidation: OK")
    return 0


def cmd_validate(args) -> int:
    from .ingestion import load_dataset
    from .validation import validate_results

    dataset = load_dataset(args.data)
    path = Path(args.file)
    rows = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_results(rows, dataset)
    if errors:
        print(f"{path}: {len(errors)} problem(s)")
        for e in errors:
            print("  -", e)
        return 1
    print(f"{path}: OK ({len(rows)} results)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="triage reports")
    run.add_argument("--data", default=str(ROOT / "data"))
    run.add_argument("--out", default=str(ROOT / "output"))
    run.add_argument("--report", action="append", help="only this reportId (repeatable)")
    run.add_argument("--offline", action="store_true", help="no LLM calls; every academic decision goes to faculty")
    run.add_argument("--no-cache", action="store_true")
    run.add_argument("--workers", type=int, default=2, help="concurrent LLM calls; keep low on small OpenRouter balances")
    run.set_defaults(func=cmd_run)

    val = sub.add_parser("validate", help="validate a results.json")
    val.add_argument("--data", default=str(ROOT / "data"))
    val.add_argument("--file", default=str(ROOT / "output" / "results.json"))
    val.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
