"""Token accounting for every LLM call, rolled up per step, per question and per report.

Shared question-level work (solver, solution reader) is recorded once on the question and
amortized across that question's reports for display. Cache hits record zero new tokens.
"""

from __future__ import annotations

import os
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

QUESTION_STEPS = ("solver", "solution_reader")
REPORT_STEPS = ("interpreter", "comparator", "reply")

# USD per 1M tokens (input, output). Approximate list prices; override with TRIAGE_PRICE_<MODEL>="in,out".
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o4-mini": (1.10, 4.40),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5": (1.25, 10.00),
    "o3": (2.00, 8.00),
}


def price_for(model: str) -> tuple[float, float]:
    env_key = "TRIAGE_PRICE_" + model.upper().replace("-", "_").replace(".", "_").replace(":", "_")
    override = os.getenv(env_key)
    if override:
        try:
            pin, pout = (float(x) for x in override.split(","))
            return pin, pout
        except ValueError:
            pass
    base = model.split(":")[-1].split("/")[-1]
    for name in sorted(DEFAULT_PRICES, key=len, reverse=True):
        if base.startswith(name):
            return DEFAULT_PRICES[name]
    return (0.0, 0.0)


@dataclass
class CallRecord:
    step: str
    model: str
    question_id: Optional[str]
    report_id: Optional[str]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_hit: bool = False
    estimated: bool = False
    ok: bool = True

    @property
    def usd(self) -> float:
        pin, pout = price_for(self.model)
        return (self.prompt_tokens * pin + self.completion_tokens * pout) / 1_000_000


def _blank() -> dict[str, float]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0, "cache_hits": 0, "estimated_usd": 0.0}


def _add(bucket: dict[str, float], rec: CallRecord) -> None:
    bucket["prompt_tokens"] += rec.prompt_tokens
    bucket["completion_tokens"] += rec.completion_tokens
    bucket["total_tokens"] += rec.total_tokens
    bucket["calls"] += 1 if (rec.ok and not rec.cache_hit) else 0
    bucket.setdefault("failed_calls", 0)
    bucket["failed_calls"] += 0 if rec.ok else 1
    bucket["cache_hits"] += 1 if rec.cache_hit else 0
    bucket["estimated_usd"] += rec.usd


def estimate_tokens(text: str, model: str = "gpt-4o") -> int:
    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model.split(":")[-1].split("/")[-1])
        except KeyError:
            enc = tiktoken.get_encoding("o200k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


@dataclass
class TokenMeter:
    records: list[CallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, rec: CallRecord) -> None:
        with self._lock:
            self.records.append(rec)

    # ------------------------------------------------------------ rollups

    def report_tokens(self, report_id: str, question_id: str, sibling_count: int) -> dict[str, Any]:
        """Per-report breakdown, including this report's share of shared question work."""
        out: dict[str, Any] = {s: 0 for s in REPORT_STEPS}
        for rec in self.records:
            if rec.report_id == report_id and rec.step in REPORT_STEPS:
                out[rec.step] += rec.total_tokens
        shared = sum(r.total_tokens for r in self.records if r.question_id == question_id and r.step in QUESTION_STEPS)
        share = shared / max(1, sibling_count)
        out["question_shared_total"] = shared
        out["question_shared_allocated"] = round(share, 1)
        out["total_allocated"] = round(sum(out[s] for s in REPORT_STEPS) + share, 1)
        return out

    def summary(self, decisions: dict[str, dict[str, Any]] | None = None, groups: dict[str, list[str]] | None = None) -> dict[str, Any]:
        decisions = decisions or {}
        groups = groups or {}
        run = _blank()
        by_step: dict[str, dict[str, float]] = {}
        by_model: dict[str, dict[str, float]] = {}
        by_question: dict[str, dict[str, Any]] = {}
        by_report: dict[str, dict[str, Any]] = {}

        for rec in self.records:
            _add(run, rec)
            _add(by_step.setdefault(rec.step, _blank()), rec)
            _add(by_model.setdefault(rec.model, _blank()), rec)
            if rec.question_id:
                q = by_question.setdefault(rec.question_id, {"shared_tokens": 0, "report_tokens": 0, "total_tokens": 0, "estimated_usd": 0.0, "cache_hits": 0})
                if rec.step in QUESTION_STEPS:
                    q["shared_tokens"] += rec.total_tokens
                else:
                    q["report_tokens"] += rec.total_tokens
                q["total_tokens"] += rec.total_tokens
                q["estimated_usd"] += rec.usd
                q["cache_hits"] += 1 if rec.cache_hit else 0

        for qid, rids in groups.items():
            q = by_question.setdefault(qid, {"shared_tokens": 0, "report_tokens": 0, "total_tokens": 0, "estimated_usd": 0.0, "cache_hits": 0})
            q["reportIds"] = rids
            mix = {"auto_apply": 0, "faculty_review": 0, "no_change": 0}
            for rid in rids:
                route = decisions.get(rid, {}).get("route")
                if route in mix:
                    mix[route] += 1
            q["route_mix"] = mix
            for rid in rids:
                entry = self.report_tokens(rid, qid, len(rids))
                d = decisions.get(rid, {})
                entry.update({k: d.get(k) for k in ("verdict", "repair", "route")})
                by_report[rid] = entry

        for bucket in [run, *by_step.values(), *by_model.values(), *by_question.values()]:
            bucket["estimated_usd"] = round(bucket["estimated_usd"], 5)

        by_repair: dict[str, dict[str, float]] = {}
        for rid, entry in by_report.items():
            key = entry.get("repair") or entry.get("verdict") or "unknown"
            b = by_repair.setdefault(key, {"reports": 0, "total_allocated": 0.0})
            b["reports"] += 1
            b["total_allocated"] += entry["total_allocated"]
        for b in by_repair.values():
            b["avg_tokens_per_report"] = round(b["total_allocated"] / b["reports"], 1)
            b["total_allocated"] = round(b["total_allocated"], 1)

        return {
            "run_totals": run,
            "by_step": by_step,
            "by_model": by_model,
            "by_repair_or_verdict": by_repair,
            "by_questionId": by_question,
            "by_reportId": by_report,
            "pricing_note": "USD estimates use approximate list prices in engine/token_meter.py; override via TRIAGE_PRICE_<MODEL>.",
        }

    def raw(self) -> list[dict[str, Any]]:
        return [asdict(r) | {"usd": round(r.usd, 6)} for r in self.records]
