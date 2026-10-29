"""The seam between the agent loop and any language model.

The loop only depends on this protocol, which is what lets the same loop run against
Claude for real runs and against scripted fakes in tests and the offline eval.
Messages use the Messages API shape (role + content blocks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ModelTurn:
    """One model response, normalized."""
    assistant_content: list[Any]  # appended verbatim as the assistant message
    tool_calls: list[ToolCall]
    text: str  # concatenated text blocks (the final answer when there are no tool calls)
    stop_reason: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class ModelError(Exception):
    """Non-retryable model failure (bad request, refusal, auth, script exhausted)."""


class TransientModelError(ModelError):
    """Retryable failure: rate limit, overloaded/5xx, timeout, connection error."""


class ModelClient(Protocol):
    name: str

    def complete(self, *, system: str, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]], output_schema: dict[str, Any]) -> ModelTurn: ...
