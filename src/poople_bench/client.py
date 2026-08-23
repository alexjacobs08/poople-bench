"""OpenRouter chat-completions client with retries and exact usage accounting.

Cost comes from the response's `usage.cost` (OpenRouter credits == USD).
A 400 caused by response_format is retried once without the schema, since
structured-output support is per-endpoint.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx
from pydantic import BaseModel

from .roster import Model

API_URL = "https://openrouter.ai/api/v1/chat/completions"
HEADERS_EXTRA = {
    "HTTP-Referer": "https://github.com/alexjacobs08/poople-bench",
    "X-Title": "Poople Bench",
}
BACKOFFS = [5.0, 20.0]

LADDER_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "ladder",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"ladder": {"type": "array", "items": {"type": "string"}}},
            "required": ["ladder"],
            "additionalProperties": False,
        },
    },
}


class ApiError(Exception):
    pass


class Attempt(BaseModel):
    date: str
    index: int
    word: str
    par: int
    model: str
    trial: int
    mode: str  # daily | backfill
    provider: str | None = None
    raw: str | None = None
    ladder: list[str] | None = None
    parser: str = "none"
    valid: bool = False
    failure: str | None = None
    steps: int | None = None
    over_par: int | None = None
    score: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost: float | None = None
    latency_s: float | None = None
    generation_id: str | None = None
    prompt_version: str
    error: str | None = None


def _payload(model: Model, prompt: str, include_schema: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model.id,
        "messages": [{"role": "user", "content": prompt}],
    }
    if include_schema:
        payload["response_format"] = LADDER_SCHEMA
    if model.reasoning_effort:
        payload["reasoning"] = {"effort": model.reasoning_effort}
    return payload


def _is_schema_rejection(response: httpx.Response) -> bool:
    text = response.text.lower()
    return any(k in text for k in ("response_format", "json_schema", "structured"))


def call_openrouter(
    model: Model,
    prompt: str,
    api_key: str,
    client: httpx.Client,
    timeout: float = 300.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", **HEADERS_EXTRA}
    include_schema = True
    retries = 0
    while True:
        try:
            response = client.post(
                API_URL,
                json=_payload(model, prompt, include_schema),
                headers=headers,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            if retries < len(BACKOFFS):
                sleep(BACKOFFS[retries])
                retries += 1
                continue
            raise ApiError(f"transport error: {exc!r}") from exc

        if response.status_code == 200:
            data = response.json()
            if not data.get("choices"):
                raise ApiError(f"no choices in response: {str(data)[:300]}")
            return data
        if response.status_code == 400 and include_schema and _is_schema_rejection(response):
            include_schema = False  # does not consume a retry
            continue
        if response.status_code == 429 or response.status_code >= 500:
            if retries < len(BACKOFFS):
                sleep(BACKOFFS[retries])
                retries += 1
                continue
        raise ApiError(f"HTTP {response.status_code}: {response.text[:300]}")


def extract_response(data: dict[str, Any]) -> dict[str, Any]:
    content = data["choices"][0].get("message", {}).get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return {
        "raw": content,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": details.get("reasoning_tokens"),
        "cost": usage.get("cost"),
        "provider": data.get("provider"),
        "generation_id": data.get("id"),
    }
