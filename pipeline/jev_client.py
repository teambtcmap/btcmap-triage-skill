"""Headless Jev 1.13 (TypeSafe AI System One) client for batch triage.

Jev is not a chat model: it answers typed questions about a state and returns values
and probabilities. Zen's Go subscription cannot reach it — this needs a Zen key
(OPENCODE_ZEN_API_KEY, or the one the opencode CLI stores under ["opencode"]["key"]).

Kept separate from the interactive Hermes plugin (~/.hermes/plugins/jev/) so the batch
runs headless on a server without loading the agent.

Cost: jev-1.13-free is free; jev-1.13 bills $0.042/1M input. The per-run call budget is
enforced here so a runaway loop cannot spend silently.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://opencode.ai/zen/v1/systemone"
FREE = "jev-1.13-free"
PAID = "jev-1.13"
QUESTION_TYPES = ("noul", "choice", "score")


class BudgetExceeded(RuntimeError):
    pass


ZEN_TOKEN_FILES = (
    Path("~/.config/btcmap/zen.token"),      # the project's own Zen key, created for this job
    Path("~/.config/btcmap/opencode-zen.token"),
)


def zen_key() -> str:
    """Zen credential, project key first: the BTC Map job must not spend the personal key."""
    for var in ("BTCMAP_ZEN_KEY", "OPENCODE_ZEN_API_KEY", "OPENCODE_API_KEY"):
        value = (os.environ.get(var) or "").strip()
        if value:
            return value
    for path in ZEN_TOKEN_FILES:
        try:
            value = path.expanduser().read_text().strip()
        except Exception:
            continue
        if value:
            return value
    for path in (Path("~/.local/share/opencode/auth.json").expanduser(),
                 Path("~/.config/opencode/auth.json").expanduser()):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        for account in ("opencode", "opencode-zen"):
            entry = data.get(account) if isinstance(data, dict) else None
            if isinstance(entry, dict):
                key = str(entry.get("key") or entry.get("apiKey") or "").strip()
                if key:
                    return key
    raise RuntimeError("no Zen key: set OPENCODE_ZEN_API_KEY or run `opencode auth login opencode`")


class JevClient:
    def __init__(self, model: str = FREE, max_calls: int = 1000, key: str | None = None):
        if model not in (FREE, PAID):
            raise ValueError(f"model must be {FREE} or {PAID}")
        self.model = model
        self.max_calls = max_calls
        self.calls = 0
        self.rate_limited = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._key = key

    @property
    def key(self) -> str:
        if not self._key:
            self._key = zen_key()
        return self._key

    def cost_usd(self) -> float:
        if self.model == FREE:
            return 0.0
        return self.input_tokens / 1_000_000 * 0.042

    def ask(self, state: str, questions: dict, retries: int = 4) -> dict:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"call budget {self.max_calls} reached")
        for qid, q in questions.items():
            if q.get("type") not in QUESTION_TYPES:
                raise ValueError(f"question {qid}: type must be one of {QUESTION_TYPES}")
        payload = {"model": self.model, "state": state, "questions": questions}
        request = urllib.request.Request(
            ENDPOINT, data=json.dumps(payload).encode(),
            headers={"User-Agent": "HermesAgent/1.0", "Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json", "Accept": "application/json",
                     "x-opencode-session": "hermes-btcmap-triage"},
            method="POST")
        # The free id rate-limits (`429 FreeUsageLimitError`) part-way through a backlog run;
        # back off and retry rather than losing the pass. Give up gracefully when it persists —
        # the caller saves progress and the run resumes.
        delay = 45.0
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    body = json.loads(response.read().decode() or "{}")
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:300]
                if exc.code in (429, 502, 503, 504) and attempt < retries:
                    self.rate_limited += 1
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise RuntimeError(f"Jev HTTP {exc.code}: {detail}") from None
        else:  # pragma: no cover - loop always breaks or raises
            raise RuntimeError("Jev request failed after retries")
        self.calls += 1
        usage = body.get("usage") or {}
        self.input_tokens += int(usage.get("input_tokens") or 0)
        self.output_tokens += int(usage.get("output_tokens") or 0)
        return body


def expected_value(answer: dict) -> float | None:
    """Collapse a `score` answer's probabilities into a 0..1 expected value."""
    probs = answer.get("probabilities") or {}
    if not probs:
        return None
    total = 0.0
    weight = 0.0
    for key, prob in probs.items():
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        n = max(1, len(probs) - 1)
        total += index / n * float(prob)
        weight += float(prob)
    return round(total / weight, 4) if weight else None
