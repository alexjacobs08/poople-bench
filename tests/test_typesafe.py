import json

import httpx
import pytest

from poople_bench.typesafe import (
    INPUT_PER_M,
    TypeSafeError,
    call_system_one,
    request_cost,
)

OK_BODY = {
    "model": "jev-1.13.0",
    "answers": {
        "next_move": {
            "type": "choice",
            "choice": "p4=p",
            "confidence": 0.2,
            "probabilities": {"p4=p": 0.6, "p1=z": 0.4},
        }
    },
    "usage": {"input_tokens": 362, "output_tokens": 65},
}


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_posts_state_questions_and_model_with_bearer_auth():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=OK_BODY)

    call_system_one(
        state={"current_word": "corn"},
        questions={"next_move": {"type": "choice", "instructions": "go", "criteria": {"p4=p": None}}},
        api_key="key",
        client=make_client(handler),
    )
    assert seen["url"] == "https://api.typesafe.ai/v1/systemone"
    assert seen["auth"] == "Bearer key"
    assert seen["body"]["model"] == "jev-latest"
    assert seen["body"]["state"] == {"current_word": "corn"}
    assert seen["body"]["questions"]["next_move"]["type"] == "choice"


def test_returns_parsed_answers_and_usage():
    data = call_system_one(
        state={}, questions={}, api_key="k",
        client=make_client(lambda r: httpx.Response(200, json=OK_BODY)),
    )
    assert data["answers"]["next_move"]["choice"] == "p4=p"
    assert data["usage"]["input_tokens"] == 362


def test_retries_on_429_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json=OK_BODY)

    data = call_system_one(
        state={}, questions={}, api_key="k",
        client=make_client(handler), sleep=lambda s: None,
    )
    assert len(calls) == 3
    assert data["model"] == "jev-1.13.0"


def test_retries_on_529_overloaded():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(529, text="overloaded")

    with pytest.raises(TypeSafeError, match="529"):
        call_system_one(
            state={}, questions={}, api_key="k",
            client=make_client(handler), sleep=lambda s: None,
        )
    assert len(calls) == 3  # initial + 2 backoffs


def test_422_validation_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(422, text="bad question")

    with pytest.raises(TypeSafeError, match="422"):
        call_system_one(
            state={}, questions={}, api_key="k",
            client=make_client(handler), sleep=lambda s: None,
        )
    assert len(calls) == 1


def test_401_raises_immediately():
    with pytest.raises(TypeSafeError, match="401"):
        call_system_one(
            state={}, questions={}, api_key="bad",
            client=make_client(lambda r: httpx.Response(401, text="nope")),
            sleep=lambda s: None,
        )


def test_cost_is_computed_locally_because_output_tokens_are_free():
    assert INPUT_PER_M == 0.042
    assert request_cost({"input_tokens": 1_000_000, "output_tokens": 999}) == pytest.approx(0.042)
    assert request_cost({"input_tokens": 0, "output_tokens": 500}) == 0.0


@pytest.mark.parametrize("status", [500, 502, 503])
def test_transient_server_errors_are_retried(status):
    # Seen live 2026-09-25: a one-off HTTP 500 "internal_error" from TypeSafe.
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 2:
            return httpx.Response(status, text="internal_error")
        return httpx.Response(200, json=OK_BODY)

    data = call_system_one(
        state={}, questions={}, api_key="k",
        client=make_client(handler), sleep=lambda s: None,
    )
    assert len(calls) == 2 and data["model"] == "jev-1.13.0"
