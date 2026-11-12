"""OpenAI-compatible provider: local models (Ollama, vLLM, llama.cpp server, LM Studio)
or any hosted endpoint that speaks POST /v1/chat/completions.

Runs the same prompts and schemas as the Claude provider (see PromptedLLM). Smaller
models are less reliable at structured output, so this adapter:

1. asks the server to constrain decoding to the JSON schema (`response_format`),
   falling back to plain JSON mode or schema-in-the-prompt if the server rejects it;
2. strips <think>...</think> reasoning that some models emit before the answer;
3. validates the result with Pydantic and retries with the validation error;
4. detects silently truncated prompts (Ollama cuts input to the model's context
   length without an error, which would look like missed requirements).
"""

import json
import logging
import re

import httpx
from pydantic import BaseModel, ValidationError

from .config import settings
from .llm import LLMError, PromptedLLM

log = logging.getLogger(__name__)

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)
# Fewer prompt tokens than this per character means the server dropped part of the prompt.
# English text runs ~4 chars per token; 1 token per 8 chars is a deliberately loose floor.
_MIN_TOKENS_PER_CHAR = 1 / 8


def _strict(schema: dict) -> dict:
    """Close every object in the schema (no extra keys), which constrained decoders prefer."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema.setdefault("additionalProperties", False)
        for v in schema.values():
            if isinstance(v, (dict, list)):
                _strict(v)
    elif isinstance(schema, list):
        for v in schema:
            _strict(v)
    return schema


def extract_json(text: str) -> str:
    """Return the JSON part of a model reply (drops reasoning blocks and code fences)."""
    text = _THINK.sub("", text).strip()
    text = _FENCE.sub("", text).strip()
    if not text.startswith(("{", "[")):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return text


class _ModeFallback(Exception):
    """The server rejected the structured-output mode; self.mode has been degraded."""


class OpenAICompatibleLLM(PromptedLLM):
    provider = "openai_compatible"

    def __init__(self, client: httpx.Client | None = None):
        super().__init__()
        if not settings.openai_model:
            raise LLMError(
                "No local model configured. Set RFP_OPENAI_MODEL (e.g. qwen3:32b) and RFP_OPENAI_BASE_URL in backend/.env."
            )
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"} if settings.openai_api_key else {}
        self.client = client or httpx.Client(
            base_url=settings.openai_base_url.rstrip("/"), headers=headers, timeout=settings.openai_timeout_s
        )
        self.mode = settings.openai_output_mode

    @property
    def model_name(self) -> str:
        return settings.openai_model or ""

    def _request(self, messages: list[dict], schema: type[BaseModel], max_tokens: int) -> dict:
        body: dict = {"model": settings.openai_model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
        if self.mode == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "strict": True,
                                "schema": _strict(schema.model_json_schema())},
            }
        elif self.mode == "json_object":
            body["response_format"] = {"type": "json_object"}
        try:
            r = self.client.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise LLMError(f"The model server did not answer within {settings.openai_timeout_s:.0f}s "
                           "(raise RFP_OPENAI_TIMEOUT_S or use a smaller model / faster hardware).") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach the model server at {settings.openai_base_url}: {e}") from e
        unsupported = any(w in r.text.lower() for w in ("response_format", "json_schema", "schema", "format"))
        if r.status_code == 400 and self.mode != "prompt" and unsupported:
            # Server does not support this structured-output mode: degrade one step and retry.
            self.mode = "json_object" if self.mode == "json_schema" else "prompt"
            log.warning("Model server rejected structured output; falling back to %s mode", self.mode)
            raise _ModeFallback
        if r.status_code in (401, 403):
            raise LLMError("The model server rejected the API key (RFP_OPENAI_API_KEY).")
        if r.status_code == 404:
            raise LLMError(f"Model {settings.openai_model!r} or endpoint not found at {settings.openai_base_url}. "
                           "For Ollama, run `ollama pull <model>` first.")
        if r.status_code >= 400:
            raise LLMError(f"Model server error {r.status_code}: {r.text[:300]}")
        return r.json()

    def _system_prompt(self, system: str, schema: type[BaseModel]) -> str:
        if self.mode == "json_schema":
            return system  # the server enforces the schema
        return (system + "\n\nReply with a single JSON object and nothing else. It must match this JSON schema:\n"
                + json.dumps(schema.model_json_schema()))

    def _parse(self, system: str, user: str, schema: type[BaseModel], max_tokens: int | None = None):
        max_tokens = min(max_tokens or settings.openai_max_tokens, settings.openai_max_tokens)
        corrections: list[dict] = []  # previous bad reply + error, sent back on retries
        last_error = ""
        for attempt in range(settings.openai_retries + 1):
            sys_prompt = self._system_prompt(system, schema)  # rebuilt: the mode may have fallen back
            messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}, *corrections]
            while True:
                try:
                    data = self._request(messages, schema, max_tokens)
                    break
                except _ModeFallback:
                    # The server rejected constrained output; resend with the schema in the prompt.
                    messages[0]["content"] = self._system_prompt(system, schema)
            usage = data.get("usage") or {}
            self._add_usage(input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0))
            prompt_chars = len(messages[0]["content"]) + len(user)
            if (pt := usage.get("prompt_tokens")) and prompt_chars > 4000 and pt < prompt_chars * _MIN_TOKENS_PER_CHAR:
                raise LLMError(
                    f"The model server read only {pt} tokens of a ~{prompt_chars // 4}-token prompt, so part of the "
                    "document was cut off. Increase the model's context length (Ollama: OLLAMA_CONTEXT_LENGTH or "
                    "num_ctx) or lower RFP_EXTRACTION_WINDOW_CHARS."
                )
            choice = (data.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content") or ""
            if choice.get("finish_reason") == "length":
                last_error = "the reply was cut off at the token limit"
            else:
                try:
                    return schema.model_validate_json(extract_json(content))
                except ValidationError as e:
                    last_error = str(e)[:1500]
            log.info("Invalid structured output (attempt %d): %s", attempt + 1, last_error[:200])
            corrections = [
                {"role": "assistant", "content": content[:4000]},
                {"role": "user", "content": f"That reply was not valid: {last_error}\nReply again with only the "
                                            "corrected JSON object matching the schema."},
            ]
        raise LLMError(f"The model did not return valid structured output after {settings.openai_retries + 1} "
                       f"attempts ({last_error[:300]}). Try a larger model.")
