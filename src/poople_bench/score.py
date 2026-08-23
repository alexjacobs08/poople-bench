"""Scoring and leaderboard aggregation over daily result documents.

Headline per-attempt score = validity x (par / steps). Attempts with an API
error are excluded from score denominators but counted in n_api_errors and
reported as reliability.
"""

from __future__ import annotations

import datetime
from statistics import mean
from typing import Any

from .roster import model_by_id

ROLLING_DAYS = 30


def score_ladder(par: int, valid: bool, steps: int | None) -> float:
    if not valid or not steps:
        return 0.0
    return par / steps


def _metrics(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [a for a in attempts if a.get("error") is None]
    solved = [a for a in scored if a["valid"]]
    costs = [a["cost"] for a in attempts if a.get("cost") is not None]
    rtoks = [a["reasoning_tokens"] for a in scored if a.get("reasoning_tokens")]
    dates = {a["date"] for a in scored}
    total_cost = sum(costs)
    return {
        "mean_reasoning_tokens": round(mean(rtoks)) if rtoks else None,
        "n_days": len(dates),
        "n_attempts": len(attempts),
        "n_api_errors": len(attempts) - len(scored),
        "avg_score": mean(a["score"] for a in scored) if scored else 0.0,
        "solve_rate": len(solved) / len(scored) if scored else 0.0,
        "invalid_rate": (len(scored) - len(solved)) / len(scored) if scored else 0.0,
        "pass_rate_days": (
            len({a["date"] for a in solved}) / len(dates) if dates else 0.0
        ),
        "mean_over_par_solved": (
            mean(a["over_par"] for a in solved if a.get("over_par") is not None)
            if any(a.get("over_par") is not None for a in solved)
            else None
        ),
        "total_cost": total_cost,
        "mean_cost_per_attempt": mean(costs) if costs else None,
        "cost_per_solve": total_cost / len(solved) if solved else None,
    }


def aggregate(day_docs: list[dict[str, Any]]) -> dict[str, Any]:
    attempts_by_model: dict[str, list[dict[str, Any]]] = {}
    for doc in day_docs:
        for attempt in doc["attempts"]:
            attempts_by_model.setdefault(attempt["model"], []).append(attempt)

    all_dates = sorted({doc["date"] for doc in day_docs})
    cutoff = None
    if all_dates:
        latest = datetime.date.fromisoformat(all_dates[-1])
        cutoff = (latest - datetime.timedelta(days=ROLLING_DAYS - 1)).isoformat()

    rows = []
    for model_id, attempts in sorted(attempts_by_model.items()):
        try:
            m = model_by_id(model_id)
            label, lab = m.label, m.lab
            pricing = {
                "input_per_m": m.input_per_m,
                "output_per_m": m.output_per_m,
                "reasoning_effort": m.reasoning_effort,
            }
        except KeyError:
            label, lab, pricing = model_id, "?", {}
        recent = [a for a in attempts if cutoff and a["date"] >= cutoff]
        rows.append(
            {
                "model": model_id,
                "label": label,
                "lab": lab,
                **pricing,
                **_metrics(attempts),
                "rolling30": _metrics(recent),
            }
        )
    rows.sort(key=lambda r: r["avg_score"], reverse=True)

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "n_days": len(all_dates),
        "dates": all_dates,
        "prompt_versions": sorted(
            {
                a.get("prompt_version", "?")
                for doc in day_docs
                for a in doc["attempts"]
            }
        ),
        "models": rows,
    }
