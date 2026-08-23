"""Fixed benchmark prompt. Version-stamped on every attempt; any wording
change must bump PROMPT_VERSION. Par is never revealed."""

from __future__ import annotations

from typing import Iterable

PROMPT_VERSION = "1"

_TEMPLATE = """\
You are playing Poople, a daily word-ladder puzzle.

Rules:
- Start from the word "{start}".
- Change exactly one letter at each step to form a new word. The other three \
letters keep their positions (no rearranging).
- Every word in your ladder must come from the legal word list below.
- The ladder is complete when you reach the word "POOP".
- Fewer steps is better. Find the shortest ladder you can.

Legal word list ({length}-letter words, lowercase):
{words}

Respond with only a JSON object of this exact form, and no other text:
{{"ladder": ["{start_lower}", ..., "poop"]}}
The first element must be "{start_lower}" and the last must be "poop".
"""


def build_prompt(start: str, words: Iterable[str]) -> str:
    return _TEMPLATE.format(
        start=start.upper(),
        start_lower=start.lower(),
        length="4",
        words=" ".join(sorted(words)),
    )
