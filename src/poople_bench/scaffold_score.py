"""Aggregation for the Jev track.

Headline is `mean_strict`: par / steps, and 0 for a run that took any rejected
guess, which is the main bench's rule that one bad rung fails the ladder.
`mean_assisted` forgives strikes and is reported beside it.

Every Jev row is published next to three free script rows played on exactly
the same puzzles with the true word list: random, and letter matching that
looks one or two moves ahead. Jev's number only means something against them.
"""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass
from statistics import mean
from typing import Any

from .scaffold import script_play

BASELINE_SEEDS = 20


@dataclass(frozen=True)
class Baseline:
    id: str
    label: str
    depth: int


BASELINES = [
    Baseline("script-random", "Script: random move", 0),
    Baseline("script-lookahead-1", "Script: letter match, 1 move ahead", 1),
    Baseline("script-lookahead-2", "Script: letter match, 2 moves ahead", 2),
]


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def _jev_row(runs: list[dict[str, Any]]) -> dict[str, Any]:
    turns = [t for r in runs for t in r.get("turns", [])]
    contested = [t for t in turns if t.get("contested")]
    first = runs[0]
    return {
        "kind": "model",
        "model": first["model"],
        "label": first.get("label", first["model"]),
        "lab": first.get("lab", "?"),
        "with_word_list": bool(first.get("with_word_list", True)),
        "n_runs": len(runs),
        "n_puzzles": len({r["date"] for r in runs}),
        "mean_strict": mean(r["strict_score"] for r in runs),
        "mean_assisted": mean(r["assisted_score"] for r in runs),
        "solve_rate": mean(float(r["solved"]) for r in runs),
        "at_par_rate": mean(float(r["solved"] and r["steps"] == r["par"]) for r in runs),
        "mean_strikes": mean(r["strikes"] for r in runs),
        "right_call_rate": _ratio(sum(bool(t.get("optimal")) for t in contested), len(contested)),
        "similarity_accuracy": _ratio(sum(t.get("similarity_correct", 0) for t in turns),
                                      sum(t.get("similarity_checks", 0) for t in turns)),
        "legality_error_rate": _ratio(sum(r.get("legality_wrong", 0) for r in runs),
                                      sum(r.get("legality_judged", 0) for r in runs)),
        "cost_per_puzzle": mean(r.get("cost") or 0.0 for r in runs),
        "requests_per_puzzle": mean(r.get("requests") or 0 for r in runs),
    }


def _baseline_row(b: Baseline, puzzles: list[tuple[str, str, int]], words: dict[str, int]) -> dict[str, Any]:
    scores = [
        script_play(start, par, words, b.depth, random.Random(f"{date}/{b.id}/{seed}"))
        for date, start, par in puzzles
        for seed in range(BASELINE_SEEDS)
    ]
    return {
        "kind": "baseline",
        "model": b.id,
        "label": b.label,
        "lab": "Reference",
        "depth": b.depth,
        "with_word_list": True,
        "n_runs": len(scores),
        "n_puzzles": len(puzzles),
        "mean_strict": mean(scores),  # scripts use the true list, so they never strike
        "mean_assisted": mean(scores),
        "solve_rate": mean(float(s > 0) for s in scores),
        "at_par_rate": mean(float(s == 1.0) for s in scores),
    }


def aggregate_scaffold(runs: list[dict[str, Any]], words: dict[str, int]) -> dict[str, Any]:
    grouped: dict[tuple[str, bool], list[dict[str, Any]]] = {}
    for r in runs:
        grouped.setdefault((r["model"], bool(r.get("with_word_list", True))), []).append(r)
    puzzles = sorted({(r["date"], r["start_word"], r["par"]) for r in runs})

    rows = [_jev_row(g) for g in grouped.values()]
    if puzzles:
        rows += [_baseline_row(b, puzzles, words) for b in BASELINES]
    rows.sort(key=lambda r: r["mean_strict"], reverse=True)
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "n_runs": len(runs),
        "dates": sorted({r["date"] for r in runs}),
        "baseline_seeds": BASELINE_SEEDS,
        "rows": rows,
    }
