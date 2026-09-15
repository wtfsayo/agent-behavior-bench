"""Harness-neutral transcript model.

Every adapter converts its native event stream into this structure so graders
and reports never need to know which CLI produced the run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Iterator


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    is_error: bool = False
    id: str | None = None

    def args_text(self) -> str:
        try:
            return json.dumps(self.args, sort_keys=True, ensure_ascii=False)
        except Exception:
            return str(self.args)


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    text: str = ""
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float | None = None
    ttft_ms: float | None = None
    stop_reason: str | None = None


@dataclass
class Transcript:
    adapter: str
    model: str
    thinking: str | None
    turns: list[Turn] = field(default_factory=list)
    wall_s: float = 0.0
    timed_out: bool = False
    exit_code: int | None = None
    error: str | None = None
    raw_path: str | None = None

    # -- helpers used by graders / metrics --------------------------------
    def assistant_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.role == "assistant"]

    def tool_calls(self) -> Iterator[ToolCall]:
        for t in self.assistant_turns():
            yield from t.tool_calls

    def final_text(self) -> str:
        for t in reversed(self.assistant_turns()):
            if t.text.strip():
                return t.text
        return ""

    def all_text(self) -> str:
        return "\n".join(t.text for t in self.assistant_turns() if t.text)

    def all_thinking(self) -> str:
        return "\n".join(t.thinking for t in self.assistant_turns() if t.thinking)

    def output_tokens(self) -> int:
        return sum(t.output_tokens for t in self.assistant_turns())

    def input_tokens(self) -> int:
        return sum(t.input_tokens for t in self.assistant_turns())

    def thinking_chars(self) -> int:
        return sum(len(t.thinking) for t in self.assistant_turns())

    def tool_histogram(self) -> dict[str, int]:
        h: dict[str, int] = {}
        for c in self.tool_calls():
            h[c.name] = h.get(c.name, 0) + 1
        return h

    def identical_consecutive_calls(self) -> int:
        """Count assistant turns whose tool-call set is identical to the previous
        turn's. A cheap proxy for 'retrying the same thing'."""
        n = 0
        prev: list[tuple[str, str]] | None = None
        for t in self.assistant_turns():
            cur = [(c.name, c.args_text()) for c in t.tool_calls]
            if cur and cur == prev:
                n += 1
            prev = cur
        return n

    def metrics(self) -> dict[str, Any]:
        a = self.assistant_turns()
        ttfts = sorted(t.ttft_ms for t in a if t.ttft_ms)
        return {
            "turns": len(a),
            "tool_calls": sum(len(t.tool_calls) for t in a),
            "tools": self.tool_histogram(),
            "input_tokens": self.input_tokens(),
            "output_tokens": self.output_tokens(),
            "thinking_chars": self.thinking_chars(),
            "wall_s": round(self.wall_s, 1),
            "ttft_median_ms": ttfts[len(ttfts) // 2] if ttfts else None,
            "ttft_max_ms": ttfts[-1] if ttfts else None,
            "identical_consecutive_calls": self.identical_consecutive_calls(),
            "timed_out": self.timed_out,
            "exit_code": self.exit_code,
            "stop_reasons": _count(t.stop_reason for t in a),
            "final_text_chars": len(self.final_text()),
        }

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _count(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        k = str(i)
        out[k] = out.get(k, 0) + 1
    return out
