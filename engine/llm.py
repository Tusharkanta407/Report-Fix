"""Thin structured-output LLM client with metering, retries and explicit failures.

Provider is pluggable through LangChain's `init_chat_model` (TRIAGE_PROVIDER, default openai).
A call either returns a validated Pydantic object or raises LLMFailure; it never fabricates output.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from .token_meter import CallRecord, TokenMeter, estimate_tokens

T = TypeVar("T", bound=BaseModel)
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

# Output caps per step. OpenRouter reserves credit for max_tokens, so leaving it unset fails on small balances.
# Reasoning models spend part of the cap on hidden reasoning, hence the larger solver budget.
MAX_OUTPUT_TOKENS = {
    "solver": 2500,
    "solution_reader": 700,
    "interpreter": 250,
    "comparator": 1400,  # room for faculty-readable evidence + faculty_note
    "reply": 220,
}

# Free OpenRouter models often spend most of max_tokens on hidden reasoning; leave room for JSON.
FREE_MAX_OUTPUT_TOKENS = {
    "solver": 6000,
    "solution_reader": 2500,
    "interpreter": 1200,
    "comparator": 4000,
    "reply": 1000,
}


def max_tokens_for(step: str, model: str) -> int:
    table = FREE_MAX_OUTPUT_TOKENS if ":free" in model or model == "openrouter/free" else MAX_OUTPUT_TOKENS
    return table.get(step, 1000)


class LLMFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str


def load_prompt(name: str) -> Prompt:
    """Prompt files start with a `version: vN` line, then a `---` line, then the system prompt."""
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    m = re.match(r"\s*version:\s*(\S+)\s*\n-{3,}\s*\n", text)
    if not m:
        raise ValueError(f"prompt {name} missing 'version:' header")
    return Prompt(name=name, version=m.group(1), system=text[m.end():].strip())


@dataclass
class ModelConfig:
    provider: str
    main: str
    fast: str
    solver: str
    temperature: float = 0.0
    max_retries: int = 2
    timeout: float = 120.0

    @classmethod
    def from_env(cls) -> "ModelConfig":
        default_provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY") else "openai"
        provider = os.getenv("TRIAGE_PROVIDER", default_provider)
        prefix = "openai/" if provider == "openrouter" else ""
        main = os.getenv("TRIAGE_MODEL", f"{prefix}gpt-4o")
        return cls(
            provider=provider,
            main=main,
            fast=os.getenv("TRIAGE_FAST_MODEL", f"{prefix}gpt-4o-mini"),
            solver=os.getenv("TRIAGE_SOLVER_MODEL", f"{prefix}gpt-5-mini"),
        )


class LLMClient:
    def __init__(self, config: ModelConfig, meter: TokenMeter, offline: bool = False):
        self.config = config
        self.meter = meter
        self.offline = offline
        self._models: dict[str, object] = {}

    def _chat(self, model: str, max_tokens: int):
        key = f"{model}|{max_tokens}"
        if key not in self._models:
            from langchain.chat_models import init_chat_model

            kwargs = {"temperature": self.config.temperature, "timeout": self.config.timeout, "max_tokens": max_tokens}
            if re.match(r"^(?:[\w-]+/)?(o\d|gpt-5)", model):
                kwargs.pop("temperature")
            provider = self.config.provider
            if provider == "openrouter":
                provider = "openai"
                kwargs["base_url"] = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
                kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")
            self._models[key] = init_chat_model(model, model_provider=provider, **kwargs)
        return self._models[key]

    def structured(
        self,
        *,
        step: str,
        model: str,
        prompt: Prompt,
        user: str,
        schema: Type[T],
        question_id: Optional[str],
        report_id: Optional[str],
    ) -> T:
        if self.offline:
            self.meter.record(CallRecord(step, model, question_id, report_id, ok=False))
            raise LLMFailure("offline mode: no LLM call made")

        from langchain_core.messages import HumanMessage, SystemMessage

        runnable = self._chat(model, max_tokens_for(step, model)).with_structured_output(schema, include_raw=True)
        messages = [SystemMessage(content=prompt.system), HumanMessage(content=user)]
        last_error = "unknown error"
        for attempt in range(self.config.max_retries + 1):
            try:
                out = runnable.invoke(messages)
            except Exception as exc:  # network / auth / rate limit
                last_error = f"{type(exc).__name__}: {exc}"
                self._record(step, model, question_id, report_id, None, prompt.system + user, ok=False)
                lowered = last_error.lower()
                if any(s in lowered for s in ("auth", "api key", "402", "credits")):
                    break
                time.sleep(1.5 * (attempt + 1))
                continue
            raw = out.get("raw")
            parsed = out.get("parsed")
            ok = parsed is not None and out.get("parsing_error") is None
            self._record(step, model, question_id, report_id, raw, prompt.system + user, ok=ok)
            if ok:
                return parsed
            last_error = f"invalid structured output: {out.get('parsing_error')}"
            messages = messages + [
                HumanMessage(content="Your previous reply did not match the required schema. Reply again using only the schema fields.")
            ]
        raise LLMFailure(f"{step} failed after retries: {last_error}")

    def _record(self, step, model, question_id, report_id, raw, sent_text, ok):
        usage = getattr(raw, "usage_metadata", None) if raw is not None else None
        if usage:
            rec = CallRecord(
                step, model, question_id, report_id,
                prompt_tokens=int(usage.get("input_tokens", 0)),
                completion_tokens=int(usage.get("output_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
                ok=ok,
            )
        elif raw is None:
            # Request rejected before generation (auth, credits, network): not billed.
            rec = CallRecord(step, model, question_id, report_id, ok=False)
        else:
            pt = estimate_tokens(sent_text, model)
            rec = CallRecord(step, model, question_id, report_id, prompt_tokens=pt, total_tokens=pt, estimated=True, ok=ok)
        self.meter.record(rec)
