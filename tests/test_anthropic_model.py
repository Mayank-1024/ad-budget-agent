from types import SimpleNamespace

import anthropic
import httpx
import pytest

from agent.anthropic_model import AnthropicModel
from agent.model_client import ModelError, TransientModelError
from agent.proposal import proposal_json_schema
from agent.tools import TOOL_DEFINITIONS


class StubMessages:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.kwargs = response, exc, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.exc:
            raise self.exc
        return self.response


def stub(response=None, exc=None):
    return SimpleNamespace(messages=StubMessages(response, exc))


def response(content, stop="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=1200, output_tokens=300))


def call(model):
    return model.complete(system="sys", messages=[{"role": "user", "content": "hi"}],
                          tools=TOOL_DEFINITIONS, output_schema=proposal_json_schema())


def test_request_shape():
    client = stub(response([SimpleNamespace(type="text", text="{}")]))
    call(AnthropicModel("claude-haiku-5-5", effort="low", client=client))
    kw = client.messages.kwargs
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["output_config"]["effort"] == "low"
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["tools"] is TOOL_DEFINITIONS
    for banned in ("temperature", "top_p", "top_k", "tool_choice"):
        assert banned not in kw


def test_tool_use_mapping():
    content = [SimpleNamespace(type="thinking", thinking=""),
               SimpleNamespace(type="tool_use", id="toolu_1", name="get_campaign_metrics",
                               input={"window_days": 7})]
    turn = call(AnthropicModel("m", client=stub(response(content, "tool_use"))))
    assert turn.tool_calls[0].input == {"window_days": 7}
    assert turn.assistant_content == content  # passed back verbatim, thinking included
    assert (turn.input_tokens, turn.output_tokens) == (1200, 300)


def _status_error(cls, code):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("err", response=httpx.Response(code, request=req), body=None)


@pytest.mark.parametrize("exc, expected", [
    (_status_error(anthropic.RateLimitError, 429), TransientModelError),
    (_status_error(anthropic.InternalServerError, 500), TransientModelError),
    (_status_error(anthropic.BadRequestError, 400), ModelError),
    (anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")),
     TransientModelError),
])
def test_error_classification(exc, expected):
    with pytest.raises(expected) as info:
        call(AnthropicModel("m", client=stub(exc=exc)))
    if expected is ModelError:
        assert not isinstance(info.value, TransientModelError)


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_unusable_stop_reasons(stop):
    with pytest.raises(ModelError):
        call(AnthropicModel("m", client=stub(response([], stop))))
