import json

import httpx
import pytest

from poople_bench.client import ApiError, call_openrouter, extract_response
from poople_bench.roster import Model

MODEL = Model(id="test/model", label="Test", lab="Test", input_per_m=1.0, output_per_m=2.0)
NO_REASONING = MODEL.model_copy(update={"reasoning_effort": None})

OK_BODY = {
    "id": "gen-123",
    "provider": "TestProvider",
    "choices": [{"message": {"content": '{"ladder": ["girl", "poop"]}'}}],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "cost": 0.00123,
        "completion_tokens_details": {"reasoning_tokens": 30},
    },
}


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_success_sends_schema_and_reasoning():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer key"
        return httpx.Response(200, json=OK_BODY)

    data = call_openrouter(MODEL, "prompt", "key", make_client(handler))
    assert data["id"] == "gen-123"
    assert seen["response_format"]["type"] == "json_schema"
    assert seen["reasoning"] == {"effort": "medium"}
    assert seen["model"] == "test/model"


def test_reasoning_omitted_when_none():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=OK_BODY)

    call_openrouter(NO_REASONING, "prompt", "key", make_client(handler))
    assert "reasoning" not in seen


def test_retry_on_429():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return httpx.Response(200, json=OK_BODY)

    sleeps = []
    data = call_openrouter(MODEL, "p", "k", make_client(handler), sleep=sleeps.append)
    assert data["id"] == "gen-123" and calls["n"] == 2 and sleeps == [5]


def test_persistent_500_raises():
    def handler(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(ApiError):
        call_openrouter(MODEL, "p", "k", make_client(handler), sleep=lambda s: None)


def test_schema_400_falls_back_without_schema():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": {"message": "response_format not supported"}})
        return httpx.Response(200, json=OK_BODY)

    data = call_openrouter(MODEL, "p", "k", make_client(handler), sleep=lambda s: None)
    assert data["id"] == "gen-123"
    assert "response_format" in bodies[0] and "response_format" not in bodies[1]


def test_200_with_error_body_raises():
    def handler(request):
        return httpx.Response(200, json={"error": {"message": "moderation"}})

    with pytest.raises(ApiError):
        call_openrouter(MODEL, "p", "k", make_client(handler), sleep=lambda s: None)


def test_extract_response():
    out = extract_response(OK_BODY)
    assert out["raw"] == '{"ladder": ["girl", "poop"]}'
    assert out["prompt_tokens"] == 100
    assert out["completion_tokens"] == 50
    assert out["reasoning_tokens"] == 30
    assert out["cost"] == 0.00123
    assert out["provider"] == "TestProvider"
    assert out["generation_id"] == "gen-123"


def test_extract_response_content_parts():
    body = dict(OK_BODY, choices=[{"message": {"content": [{"type": "text", "text": "hi"}]}}])
    assert extract_response(body)["raw"] == "hi"
