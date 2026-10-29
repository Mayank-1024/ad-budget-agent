"""Offline stand-ins for Claude, for tests and the offline eval. Neither is a model.

ScriptedModel replays a fixed list of steps:

    {"tool_calls": [{"name": "get_campaign_metrics", "input": {"window_days": 7}}]}
    {"final": {...proposal dict...}}
    {"final_raw": "any text, e.g. invalid JSON"}
    {"error": "transient"} / {"error": "fatal"}

Tools, validation and guardrails still run for real, so a script that misbehaves (asks
for +80%, names an unknown campaign, returns broken JSON) exercises exactly the code path
a misbehaving real model would.

RulePlayingModel plays a fixed decision rule through the real tool interface: it calls
get_campaign_metrics for 3 and 7 days, reads the tool results back out of the message
history, and proposes +15% / -15% moves by 7-day ROAS. With `reads_memory=True` it skips
any (campaign, direction) the <reviewer_memory> block says was rejected. It exists so the
offline eval exercises the whole pipeline (tools, ClickHouse queries, guardrails,
approvals, memory) without an API key. Its results say nothing about Claude.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agent.model_client import ModelError, ModelTurn, ToolCall, TransientModelError


def _final_turn(text: str) -> ModelTurn:
    return ModelTurn([{"type": "text", "text": text}], [], text=text, stop_reason="end_turn")


def _tool_turn(n: int, calls: list[dict[str, Any]]) -> ModelTurn:
    tc = [ToolCall(id=f"toolu_{n}_{i}", name=c["name"], input=c["input"])
          for i, c in enumerate(calls)]
    content = [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in tc]
    return ModelTurn(content, tc, text="", stop_reason="tool_use")


class ScriptedModel:
    name = "scripted"

    def __init__(self, steps: list[dict[str, Any]]):
        self.steps = list(steps)
        self.calls = 0
        self.seen_messages: list[list[dict[str, Any]]] = []

    def complete(self, *, system: str, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]], output_schema: dict[str, Any]) -> ModelTurn:
        self.seen_messages.append(list(messages))
        if self.calls >= len(self.steps):
            raise ModelError("script exhausted")
        step = self.steps[self.calls]
        self.calls += 1
        if "error" in step:
            if step["error"] == "transient":
                raise TransientModelError("scripted transient error")
            raise ModelError("scripted fatal error")
        if "tool_calls" in step:
            return _tool_turn(self.calls, step["tool_calls"])
        return _final_turn(step["final_raw"] if "final_raw" in step
                           else json.dumps(step["final"]))


_REJECTED = re.compile(r"^- \S+: (increase|decrease) (\S+) \([^)]*\) was REJECTED", re.M)


class RulePlayingModel:
    def __init__(self, reads_memory: bool = True, step_pct: float = 0.15,
                 scale_above: float = 2.5, cut_below: float = 1.5):
        self.reads_memory = reads_memory
        self.step_pct, self.scale_above, self.cut_below = step_pct, scale_above, cut_below
        self.name = "rule-playing-scripted" + ("" if reads_memory else "-no-memory")

    def complete(self, *, system: str, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]], output_schema: dict[str, Any]) -> ModelTurn:
        results = [json.loads(b["content"]) for m in messages if m["role"] == "user"
                   and isinstance(m["content"], list) for b in m["content"]
                   if b.get("type") == "tool_result" and not b.get("is_error")]
        if not results:
            return _tool_turn(1, [{"name": "get_campaign_metrics", "input": {"window_days": 3}},
                                  {"name": "get_campaign_metrics", "input": {"window_days": 7}}])
        by_window = {r["window_days"]: {c["campaign_id"]: c for c in r["campaigns"]}
                     for r in results if "window_days" in r}
        rejected = set()
        if self.reads_memory:
            rejected = {(d, c) for d, c in _REJECTED.findall(messages[0]["content"])}
        moves, flags = [], []
        for cid, c7 in by_window.get(7, {}).items():
            c3 = by_window.get(3, {}).get(cid, c7)
            cur = c7["current_daily_budget"]
            if c3["clicks"] >= 300 and c3["conversions"] == 0:
                flags.append({"campaign_id": cid, "issue": "clicks but zero conversions"})
                continue
            roas = c7["roas"] or 0.0
            if roas >= self.scale_above:
                action, new = "increase", round(cur * (1 + self.step_pct), 2)
            elif roas < self.cut_below:
                action, new = "decrease", round(cur * (1 - self.step_pct), 2)
            else:
                continue
            if (action, cid) in rejected:
                continue
            moves.append({"campaign_id": cid, "action": action, "new_daily_budget": new,
                          "reason": f"7-day ROAS {roas:.2f} vs thresholds "
                                    f"{self.cut_below}/{self.scale_above}",
                          "expected_effect": "move spend toward higher-ROAS campaigns"})
        return _final_turn(json.dumps({"moves": moves, "flags": flags,
                                       "summary": "Rule-based scripted proposal."}))
