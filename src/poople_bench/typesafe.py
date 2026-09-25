"""TypeSafe System One client (Jev).

One endpoint, one call shape: a `state` blob plus a map of typed questions,
answered in parallel. Output tokens are free, so cost is computed locally from
`usage.input_tokens` rather than read off the response.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx

API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
INPUT_PER_M = 0.042  # $/M input tokens; output tokens are free
OUTPUT_PER_M = 0.0
BACKOFFS = [2.0, 8.0]
RETRY_STATUS = {429, 500, 502, 503, 529}


class TypeSafeError(Exception):
    pass


def request_cost(usage: dict[str, Any] | None) -> float:
    if not usage:
        return 0.0
    return (usage.get("input_tokens") or 0) / 1_000_000 * INPUT_PER_M


def call_system_one(
    state: Any,
    questions: dict[str, Any],
    api_key: str,
    client: httpx.Client,
    model: str = DEFAULT_MODEL,
    timeout: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"state": state, "model": model, "questions": questions}
    retries = 0
    while True:
        try:
            response = client.post(API_URL, json=payload, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            if retries < len(BACKOFFS):
                sleep(BACKOFFS[retries])
                retries += 1
                continue
            raise TypeSafeError(f"transport error: {exc!r}") from exc

        if response.status_code == 200:
            data = response.json()
            if "answers" not in data:
                raise TypeSafeError(f"no answers in response: {str(data)[:300]}")
            return data
        if response.status_code in RETRY_STATUS and retries < len(BACKOFFS):
            sleep(BACKOFFS[retries])
            retries += 1
            continue
        raise TypeSafeError(f"HTTP {response.status_code}: {response.text[:300]}")
