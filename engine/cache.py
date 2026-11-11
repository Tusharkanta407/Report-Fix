"""Content-fingerprint cache for question-level LLM work (solver, solution reader).

Keyed by question id + content + stored answer + type + prompt version + model, so editing a
question, a prompt or the model during debugging invalidates the stale entry automatically.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Optional

from .schemas import QuestionPayload


def fingerprint(payload: QuestionPayload, step: str, prompt_version: str, model: str) -> str:
    material = json.dumps(
        {
            "id": payload.id,
            "question": payload.question_html,
            "solution": payload.solution_html,
            "answer": payload.answer_raw,
            "type": payload.question_type,
            "step": step,
            "prompt_version": prompt_version,
            "model": model,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


class SolveCache:
    def __init__(self, root: str | Path, enabled: bool = True):
        self.root = Path(root)
        self.enabled = enabled
        self._lock = threading.Lock()

    def _path(self, step: str, key: str) -> Path:
        return self.root / step / f"{key}.json"

    def get(self, step: str, key: str) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None
        path = self._path(step, key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, step: str, key: str, value: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._path(step, key)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
