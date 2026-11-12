"""OpenAI-compatible (local model) provider, against a mock server."""

import json

import httpx
import pytest

from app.config import settings
from app.llm import ClaudeLLM, ExtractionResult, LLMError, make_llm
from app.llm_openai import OpenAICompatibleLLM, extract_json
from app.pipeline import extract_from_text

GOOD = {"summary": "School bid.", "requirements": [{
    "text": "Submit a 10% bid bond.", "kind": "form", "section": None, "page": 1,
    "source_quote": "Bidders shall submit a 10% bid bond.", "mandatory": True,
    "needs_response": False, "page_limit": None}]}


def reply(content: str, finish: str = "stop", prompt_tokens: int = 500) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 50}}


@pytest.fixture(autouse=True)
def local_settings(monkeypatch):
    monkeypatch.setattr(settings, "openai_model", "qwen3:32b")
    monkeypatch.setattr(settings, "openai_base_url", "http://model-server/v1")
    monkeypatch.setattr(settings, "openai_output_mode", "json_schema")
    monkeypatch.setattr(settings, "openai_retries", 2)


def make(handler) -> tuple[OpenAICompatibleLLM, list[dict]]:
    seen: list[dict] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        status, payload = handler(body, len(seen))
        return httpx.Response(status, json=payload)

    client = httpx.Client(base_url="http://model-server/v1", transport=httpx.MockTransport(wrapped))
    return OpenAICompatibleLLM(client=client), seen


def test_request_shape_and_success():
    llm, seen = make(lambda body, n: (200, reply(json.dumps(GOOD))))
    result = llm.extract_requirements("[Page 1]\nBidders shall submit a 10% bid bond.")
    assert isinstance(result, ExtractionResult) and result.requirements[0].kind == "form"
    body = seen[0]
    assert body["model"] == "qwen3:32b" and body["temperature"] == 0
    assert body["messages"][0]["role"] == "system" and "compliance analyst" in body["messages"][0]["content"]
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False
    assert llm.usage["calls"] == 1 and llm.usage["input_tokens"] == 500


def test_strips_reasoning_and_code_fences():
    assert json.loads(extract_json('<think>long reasoning {not json}</think>\n```json\n{"a": 1}\n```')) == {"a": 1}
    assert json.loads(extract_json('Sure! Here it is: {"a": 2} Hope this helps.')) == {"a": 2}


def test_retries_invalid_output_with_the_error():
    def handler(body, n):
        return (200, reply('{"summary": "x"}')) if n == 1 else (200, reply(json.dumps(GOOD)))

    llm, seen = make(handler)
    llm.extract_requirements("text")
    assert len(seen) == 2
    retry_msgs = seen[1]["messages"]
    assert retry_msgs[-1]["role"] == "user" and "not valid" in retry_msgs[-1]["content"]
    assert "requirements" in retry_msgs[-1]["content"]  # the validation error names the missing field


def test_gives_up_after_retries():
    llm, seen = make(lambda body, n: (200, reply("I cannot help with that.")))
    with pytest.raises(LLMError, match="valid structured output after 3 attempts"):
        llm.extract_requirements("text")
    assert len(seen) == 3


def test_cut_off_reply_is_retried():
    llm, seen = make(lambda body, n: (200, reply('{"summary": "x", "requ', "length")) if n == 1
                     else (200, reply(json.dumps(GOOD))))
    llm.extract_requirements("text")
    assert "cut off" in seen[1]["messages"][-1]["content"]


def test_falls_back_when_server_rejects_json_schema():
    def handler(body, n):
        if body.get("response_format", {}).get("type") == "json_schema":
            return 400, {"error": {"message": "response_format json_schema is not supported"}}
        return 200, reply(json.dumps(GOOD))

    llm, seen = make(handler)
    llm.extract_requirements("text")
    assert seen[1]["response_format"] == {"type": "json_object"}
    assert "must match this JSON schema" in seen[1]["messages"][0]["content"]  # schema moved into the prompt
    llm.extract_requirements("text again")  # later calls go straight to the fallback mode
    assert seen[2]["response_format"] == {"type": "json_object"}


def test_detects_silently_truncated_prompt():
    llm, _ = make(lambda body, n: (200, reply(json.dumps(GOOD), prompt_tokens=2048)))
    with pytest.raises(LLMError, match="cut off"):
        llm.extract_requirements("Bidders shall submit a bond. " * 2000)  # ~58k chars but only 2048 tokens read


def test_helpful_errors():
    llm, _ = make(lambda body, n: (404, {"error": "model not found"}))
    with pytest.raises(LLMError, match="ollama pull"):
        llm.extract_requirements("text")


def test_requires_a_model_name(monkeypatch):
    monkeypatch.setattr(settings, "openai_model", None)
    with pytest.raises(LLMError, match="RFP_OPENAI_MODEL"):
        OpenAICompatibleLLM()


def test_provider_selection(monkeypatch):
    assert isinstance(make_llm("openai_compatible"), OpenAICompatibleLLM)
    assert isinstance(make_llm("local"), OpenAICompatibleLLM)
    monkeypatch.setattr(settings, "anthropic_api_key", "test")
    assert isinstance(make_llm("claude"), ClaudeLLM)
    with pytest.raises(ValueError):
        make_llm("nope")


def test_full_extraction_pipeline_runs_on_the_local_provider():
    llm, seen = make(lambda body, n: (200, reply(json.dumps(GOOD))))
    _, reqs = extract_from_text("[Page 1]\nBidders shall submit a 10% bid bond.\nThe Owner will provide parking.", llm)
    assert [r.kind for r in reqs] == ["form"]
