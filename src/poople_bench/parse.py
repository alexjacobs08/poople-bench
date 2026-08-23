"""Tolerant extraction of a word ladder from model output.

Parse order: whole-text JSON -> last embedded JSON block -> 4-letter-token
chain heuristic. The parser used is recorded on every attempt.
"""

from __future__ import annotations

import json
import re


def _as_ladder(obj: object) -> list[str] | None:
    if isinstance(obj, dict):
        obj = obj.get("ladder")
    if (
        isinstance(obj, list)
        and obj
        and all(isinstance(w, str) and w.isalpha() for w in obj)
    ):
        return [w.lower() for w in obj]
    return None


def _strip_fences(text: str) -> str:
    return re.sub(r"^```[a-zA-Z]*\s*$", "", text, flags=re.MULTILINE)


def _hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(x != y for x, y in zip(a, b))


def _embedded_json(text: str) -> list[str] | None:
    decoder = json.JSONDecoder()
    starts = [m.start() for m in re.finditer(r"[{\[]", text)]
    for i in reversed(starts[-2000:]):
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except ValueError:
            continue
        ladder = _as_ladder(obj)
        if ladder:
            return ladder
    return None


def _token_chain(text: str) -> list[str] | None:
    tokens = [t.lower() for t in re.findall(r"\b[A-Za-z]{4}\b", text)]
    if "poop" not in tokens:
        return None
    end = len(tokens) - 1 - tokens[::-1].index("poop")
    chain = [tokens[end]]
    for i in range(end - 1, -1, -1):
        if _hamming(tokens[i], chain[-1]) == 1:
            chain.append(tokens[i])
        else:
            break
    if len(chain) < 2:
        return None
    return chain[::-1]


def parse_ladder(text: str | None) -> tuple[list[str] | None, str]:
    if not text or not text.strip():
        return None, "none"
    stripped = _strip_fences(text).strip()
    try:
        ladder = _as_ladder(json.loads(stripped))
        if ladder:
            return ladder, "json"
    except ValueError:
        pass
    ladder = _embedded_json(stripped)
    if ladder:
        return ladder, "json_embedded"
    ladder = _token_chain(text)
    if ladder:
        return ladder, "tokens"
    return None, "none"
