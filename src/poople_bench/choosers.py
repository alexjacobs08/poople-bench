"""JevJudge: the three kinds of question the Jev track asks.

Each method is one request (legality may split into several). Jev only ever sees
what is in the request; the game loop in scaffold.py decides what to send.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from .scaffold import TARGET
from .typesafe import DEFAULT_MODEL, call_system_one, request_cost

LEGALITY_STATE = {"task": "Judging whether four-letter strings are real English words."}

CLOSEST_INSTRUCTIONS = (
    "Which of these words is most like `target_word` - the most letters matching "
    "`target_word` in the same positions?"
)

CHOOSE_INSTRUCTIONS = (
    "You are playing a word ladder from `start_word` to `target_word`, changing one letter "
    "per step through real words. `selections_so_far` lists the changes you have made, in "
    "order. Each option is one change to `current_word`. Its description shows the word that "
    "change produces, and the word after that which looks most like `target_word`. Choose the "
    "change that ends up looking most like `target_word`. A change that produces "
    "`target_word` itself is always the right answer."
)


@dataclass
class JevJudge:
    api_key: str
    client: httpx.Client
    word_list: list[str] | None = None  # None: Jev relies on its own vocabulary
    model: str = DEFAULT_MODEL
    batch_size: int = 250
    requests: int = 0
    input_tokens: int = 0
    cost: float = 0.0
    served_by: str | None = field(default=None)

    def _ask(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        data = call_system_one(state, questions, self.api_key, self.client, model=self.model)
        usage = data.get("usage") or {}
        self.requests += 1
        self.input_tokens += usage.get("input_tokens") or 0
        self.cost += request_cost(usage)
        self.served_by = data.get("model") or self.served_by
        return data["answers"]

    def legality(self, strings: list[str]) -> dict[str, float]:
        if self.word_list is not None:
            state: Any = {"accepted_word_list": " ".join(sorted(self.word_list))}
            ask = lambda s: f'Is "{s}" an entry in `accepted_word_list`?'
        else:
            state = LEGALITY_STATE
            ask = lambda s: f'Is "{s}" a real English word?'
        out: dict[str, float] = {}
        for i in range(0, len(strings), self.batch_size):
            batch = strings[i : i + self.batch_size]
            answers = self._ask(state, {s: {"type": "noul", "instructions": ask(s)} for s in batch})
            out.update({s: answers[s]["noul"] for s in batch})
        return out

    def closest(self, groups: dict[str, list[str]]) -> dict[str, str]:
        ids = {f"q{i}": key for i, key in enumerate(groups)}
        answers = self._ask(
            {"target_word": TARGET},
            {
                qid: {
                    "type": "choice",
                    "instructions": CLOSEST_INSTRUCTIONS,
                    "criteria": {w: None for w in groups[key]},
                }
                for qid, key in ids.items()
            },
        )
        return {key: answers[qid]["choice"] for qid, key in ids.items()}

    def choose(
        self, state: dict[str, Any], criteria: dict[str, str]
    ) -> tuple[str, dict[str, float] | None, float | None]:
        answer = self._ask(
            state,
            {"next_change": {"type": "choice", "instructions": CHOOSE_INSTRUCTIONS,
                             "criteria": criteria}},
        )["next_change"]
        return answer["choice"], answer.get("probabilities"), answer.get("confidence")
