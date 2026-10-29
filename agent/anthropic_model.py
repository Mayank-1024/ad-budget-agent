"""ModelClient backed by the Claude Messages API (anthropic SDK 2.x).

- The SDK's own retries are off (max_retries=0) because the agent loop owns retry policy;
  otherwise retries would multiply.
- Tool definitions use `strict: true`, so tool inputs match their JSON schema.
- The final answer is constrained with structured outputs (`output_config.format`) and is
  *still* validated by our own code, because a JSON schema cannot check that a campaign id
  belongs to the brand or that "increase" really increases the budget.
- `response.content` is passed back verbatim (including thinking blocks).
- No temperature/top_p: current models reject sampling parameters.
"""

from __future__ import annotations

from typing import Any

import anthropic

from agent.model_client import ModelError, ModelTurn, ToolCall, TransientModelError


class AnthropicModel:
    def __init__(self, model: str, *, effort: str = "medium", max_tokens: int = 16000,
                 timeout_s: float = 60.0, client: Any | None = None):
        self.name = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = client or anthropic.Anthropic(max_retries=0, timeout=timeout_s)

    def complete(self, *, system: str, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]], output_schema: dict[str, Any]) -> ModelTurn:
        try:
            response = self._client.messages.create(
                model=self.name,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                tools=tools,
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": output_schema},
                },
            )
        except anthropic.APIConnectionError as exc:  # includes APITimeoutError
            raise TransientModelError(f"connection/timeout: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise TransientModelError("rate limited") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:  # InternalServerError, OverloadedError (529)
                raise TransientModelError(f"server error {exc.status_code}") from exc
            raise ModelError(f"API error {exc.status_code}: {exc.message}") from exc

        if response.stop_reason == "refusal":
            raise ModelError("model refused the request")
        if response.stop_reason == "max_tokens":
            raise ModelError("response hit max_tokens")

        tool_calls = [ToolCall(id=b.id, name=b.name, input=dict(b.input))
                      for b in response.content if b.type == "tool_use"]
        text = "".join(b.text for b in response.content if b.type == "text")
        usage = response.usage
        return ModelTurn(
            assistant_content=list(response.content),
            tool_calls=tool_calls,
            text=text,
            stop_reason=response.stop_reason or "",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )
