"""Jev track: a word ladder played through three small judgments per turn.

Jev cannot plan or search, so it is never asked to. Each turn code lays the
board out two moves deep and Jev answers three kinds of question:

  legality - is this string a word?        (one Noul per string, goal not mentioned)
  closest  - which follow-up word looks most like POOP?  (one Choice per move)
  choose   - which move?                   (one Choice over the approved moves)

Code only does mechanics: it spells strings out, remembers answers, applies the
move and refuses to reuse a word. It never looks a word up to decide anything and
never counts letters for the model. The dictionary is used exactly where the game
itself uses it: Poople rejects a non-word (a strike), and scoring.

`script_play` is the free reference line: the same rules played by code with the
true word list, looking 0 (random), 1 or 2 moves ahead by letter matching.
"""

from __future__ import annotations

import random
from typing import Any, Protocol

from pydantic import BaseModel

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
TARGET = "poop"
LEGAL_THRESHOLD = 0.5


def edits(word: str) -> list[tuple[str, str]]:
    """The 100 single-letter changes: ("p2=o", "hope") for word "hype"."""
    return [
        (f"p{i + 1}={c}", word[:i] + c + word[i + 1 :])
        for i in range(len(word))
        for c in ALPHABET
        if c != word[i]
    ]


def differs(word: str) -> int:
    """Letters out of place against POOP. Used for baselines and stats only."""
    return sum(a != b for a, b in zip(word, TARGET))


class Judge(Protocol):
    def legality(self, strings: list[str]) -> dict[str, float]: ...
    def closest(self, groups: dict[str, list[str]]) -> dict[str, str]: ...
    def choose(
        self, state: dict[str, Any], criteria: dict[str, str]
    ) -> tuple[str, dict[str, float] | None, float | None]: ...


class Turn(BaseModel):
    index: int
    current_word: str
    approved: int = 0  # moves Jev judged to be words
    chosen: str | None = None
    result_word: str | None = None
    lookahead_word: str | None = None  # follow-up Jev picked for the chosen move
    legal: bool = False  # did Poople accept the word
    optimal: bool = False  # on a shortest path from here
    contested: bool = False  # legal options differed in distance, so the pick mattered
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    similarity_checks: int = 0
    similarity_correct: int = 0


class Run(BaseModel):
    start_word: str
    par: int
    path: list[str]
    turns: list[Turn]
    solved: bool
    steps: int
    strikes: int
    failure: str | None = None
    strict_score: float = 0.0
    assisted_score: float = 0.0
    legality_judged: int = 0
    legality_wrong: int = 0


def describe(current: str, word: str, follow_up: str | None) -> str:
    if follow_up is None:
        return f'"{current}" becomes "{word}". Nothing new is reachable after it.'
    return (
        f'"{current}" becomes "{word}". The word after it that looks most like the '
        f'target is "{follow_up}".'
    )


def play(
    start: str,
    par: int,
    judge: Judge,
    words: dict[str, int],
    max_strikes: int = 10,
    max_turns: int | None = None,
) -> Run:
    """`words` maps each Poople word to its BFS distance to POOP. It is the game's
    rulebook (rejections, scoring), never an input to a decision."""
    max_turns = max_turns if max_turns is not None else 3 * par
    known: dict[str, float] = {}

    def is_word(strings: list[str]) -> set[str]:
        todo = sorted(set(strings) - known.keys() - {TARGET})
        if todo:
            known.update(judge.legality(todo))
        return {s for s in strings if s == TARGET or known[s] >= LEGAL_THRESHOLD}

    current, path, selections = start, [start], []
    turns: list[Turn] = []
    rejected: set[str] = set()
    strikes = 0
    failure: str | None = None

    while current != TARGET:
        if len(path) - 1 >= max_turns:
            failure = "max_turns"
            break
        if strikes >= max_strikes:
            failure = "max_strikes"
            break

        candidates = {k: w for k, w in edits(current) if w not in path and k not in rejected}
        ok = is_word(list(candidates.values()))
        approved = {k: w for k, w in candidates.items() if w in ok}
        turn = Turn(index=len(turns), current_word=current, approved=len(approved))
        if not approved:
            failure = "stuck"
            turns.append(turn)
            break

        ok2 = is_word([m for w in approved.values() for _, m in edits(w)])
        follow = {
            k: sorted({m for _, m in edits(w) if m in ok2 and m not in path and m != w})
            for k, w in approved.items()
        }
        lookahead = {k: (fs[0] if len(fs) == 1 else None) for k, fs in follow.items()}
        groups = {k: fs for k, fs in follow.items() if len(fs) > 1}
        if groups:
            picked = judge.closest(groups)
            for k, fs in groups.items():
                lookahead[k] = picked[k]
                turn.similarity_checks += 1
                turn.similarity_correct += differs(picked[k]) == min(differs(f) for f in fs)

        if len(approved) == 1:
            chosen = next(iter(approved))
        else:
            state = {
                "start_word": start,
                "target_word": TARGET,
                "current_word": current,
                "selections_so_far": selections,
            }
            criteria = {k: describe(current, w, lookahead[k]) for k, w in approved.items()}
            chosen, turn.probabilities, turn.confidence = judge.choose(state, criteria)

        result = approved[chosen]
        turn.chosen, turn.result_word, turn.lookahead_word = chosen, result, lookahead[chosen]
        turn.legal = result in words
        legal_options = [w for w in candidates.values() if w in words]
        turn.contested = len({words[w] for w in legal_options}) > 1
        turn.optimal = turn.legal and words[result] == min(words[w] for w in legal_options)
        turns.append(turn)

        if not turn.legal:
            strikes += 1
            rejected.add(chosen)
            continue
        selections.append({"selected": chosen, "word_became": result})
        path.append(result)
        current, rejected = result, set()

    solved = current == TARGET
    steps = len(path) - 1
    score = par / steps if solved and steps else 0.0
    return Run(
        start_word=start,
        par=par,
        path=path,
        turns=turns,
        solved=solved,
        steps=steps,
        strikes=strikes,
        failure=failure,
        strict_score=score if strikes == 0 else 0.0,
        assisted_score=score,
        legality_judged=len(known),
        legality_wrong=sum((p >= LEGAL_THRESHOLD) != (s in words) for s, p in known.items()),
    )


def script_play(
    start: str, par: int, words: dict[str, int], depth: int, rng: random.Random
) -> float:
    """Reference line: same rules, true word list, no model. depth 0 picks at
    random; depth n prefers the move whose best string within n moves has the
    most letters matching POOP. Returns the score (par / steps, 0 if unsolved)."""

    def neighbours(w: str) -> list[str]:
        return [m for _, m in edits(w) if m in words]

    def reach(w: str, n: int, seen: frozenset[str]) -> int:
        best = differs(w)
        if n > 1 and best:
            for m in neighbours(w):
                if m not in seen:
                    best = min(best, reach(m, n - 1, seen | {m}))
        return best

    current, seen, steps = start, {start}, 0
    while current != TARGET and steps < 3 * par:
        options = [m for m in neighbours(current) if m not in seen]
        if not options:
            return 0.0
        if depth == 0:
            current = rng.choice(options)
        else:
            current = min(
                options,
                key=lambda o: (reach(o, depth, frozenset(seen | {o})), differs(o), rng.random()),
            )
        seen.add(current)
        steps += 1
    return par / steps if current == TARGET else 0.0
