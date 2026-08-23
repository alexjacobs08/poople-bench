"""Poople game core: packaged game data, BFS pars, daily index, ladder validation.

Data files are extracted from the poople.io JS bundle (see research/GAME.md);
the harness never contacts the site.
"""

from __future__ import annotations

import csv
import datetime
from collections import deque
from functools import cache
from importlib import resources
from typing import Iterable

from pydantic import BaseModel

# Puzzle for index i is active from 08:00 UTC on (EPOCH + i days) for 24h.
EPOCH = datetime.date(2025, 8, 14)
DAY_FLIP_UTC_HOUR = 8
TARGET = "poop"


class Puzzle(BaseModel):
    index: int
    date: datetime.date
    word: str
    par: int


class Validation(BaseModel):
    valid: bool
    failure: str | None = None  # wrong_start | invalid_word | broken_step | no_poop | empty
    steps: int | None = None
    ladder: list[str] = []


def _data_text(name: str) -> str:
    return (resources.files("poople_bench") / "data" / name).read_text()


@cache
def load_words() -> dict[str, int]:
    """Accepted 4-letter words mapped to their BFS distance from POOP (par)."""
    rows = csv.DictReader(_data_text("words.csv").splitlines())
    return {r["word"]: int(r["par"]) for r in rows}


@cache
def load_schedule() -> list[Puzzle]:
    rows = csv.DictReader(_data_text("schedule.csv").splitlines())
    return [
        Puzzle(
            index=int(r["index"]),
            date=datetime.date.fromisoformat(r["date"]),
            word=r["word"],
            par=int(r["par"]),
        )
        for r in rows
    ]


def puzzle_for_date(d: datetime.date) -> Puzzle:
    index = (d - EPOCH).days
    schedule = load_schedule()
    if not 0 <= index < len(schedule):
        raise ValueError(f"no puzzle scheduled for {d} (index {index})")
    return schedule[index]


def current_puzzle_date(now: datetime.datetime | None = None) -> datetime.date:
    """The puzzle-day active at `now` (UTC): flips at 08:00 UTC."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.hour < DAY_FLIP_UTC_HOUR:
        return now.date() - datetime.timedelta(days=1)
    return now.date()


def _hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(x != y for x, y in zip(a, b))


def _neighbors(word: str, vocab: set[str]) -> Iterable[str]:
    for i in range(len(word)):
        for c in "abcdefghijklmnopqrstuvwxyz":
            if c != word[i]:
                candidate = word[:i] + c + word[i + 1 :]
                if candidate in vocab:
                    yield candidate


def bfs_distances(vocab: set[str]) -> dict[str, int]:
    dist = {TARGET: 0}
    queue = deque([TARGET])
    while queue:
        w = queue.popleft()
        for n in _neighbors(w, vocab):
            if n not in dist:
                dist[n] = dist[w] + 1
                queue.append(n)
    return dist


def validate_ladder(start: str, ladder: list[str], vocab: set[str]) -> Validation:
    start = start.lower()
    ladder = [w.lower() for w in ladder if w]
    if not ladder:
        return Validation(valid=False, failure="empty")
    if ladder[0] != start:
        if _hamming(start, ladder[0]) == 1:
            # Model started with its first move; prepend the given start word.
            ladder = [start, *ladder]
        else:
            return Validation(valid=False, failure="wrong_start", ladder=ladder)
    for prev, cur in zip(ladder, ladder[1:]):
        if _hamming(prev, cur) != 1:
            return Validation(valid=False, failure="broken_step", ladder=ladder)
        if cur not in vocab:
            return Validation(valid=False, failure="invalid_word", ladder=ladder)
    if ladder[-1] != TARGET:
        return Validation(valid=False, failure="no_poop", ladder=ladder)
    return Validation(valid=True, steps=len(ladder) - 1, ladder=ladder)
