"""Approval modes and the auto-approve risk policy.

Three modes, like a "suggest / approve / automate" setting in a buying tool:
- suggest:  the agent only writes proposals; nothing executes (shadow mode).
- approve:  every move waits for a reviewer; approved moves execute.
- automate: low-risk moves execute immediately; the rest wait for a reviewer.

A move is low risk only if ALL hold: the executed change is within +/-10%, no guardrail
touched it, and it is not an increase on a campaign the agent itself flagged. Anything
else is high risk. The thresholds are deliberately conservative and live here, in code,
so a reviewer can read them.
"""

from __future__ import annotations

MODES = ("suggest", "approve", "automate")
AUTO_APPROVE_MAX_CHANGE_PCT = 10.0


def classify_risk(current: float, final: float, guardrails_fired: list[str],
                  flagged: bool) -> str:
    change_pct = abs(final - current) / current * 100 if current else 100.0
    if change_pct > AUTO_APPROVE_MAX_CHANGE_PCT + 1e-9 or guardrails_fired:
        return "high"
    if flagged and final > current:
        return "high"
    return "low"
