import pytest

from poople_bench.score import aggregate, score_ladder


def test_score_math():
    assert score_ladder(5, True, 5) == 1.0
    assert score_ladder(5, True, 7) == pytest.approx(5 / 7)
    assert score_ladder(5, False, None) == 0.0


def _attempt(date, model, trial, *, valid, score, cost, over_par=None, error=None):
    return {
        "date": date, "index": 1, "word": "x", "par": 5, "model": model,
        "trial": trial, "mode": "daily", "valid": valid, "score": score,
        "cost": cost, "over_par": over_par, "error": error, "prompt_version": "1",
    }


DOCS = [
    {
        "date": "2026-01-01", "index": 1, "word": "dawn", "par": 5, "mode": "backfill",
        "attempts": [
            _attempt("2026-01-01", "m1", 0, valid=True, score=1.0, cost=0.01, over_par=0),
            _attempt("2026-01-01", "m1", 1, valid=False, score=0.0, cost=0.02),
            _attempt("2026-01-01", "m1", 2, valid=False, score=0.0, cost=None, error="HTTP 500"),
        ],
    },
    {
        "date": "2026-08-02", "index": 2, "word": "opts", "par": 6, "mode": "daily",
        "attempts": [
            _attempt("2026-08-02", "m1", 0, valid=True, score=0.75, cost=0.03, over_par=2),
            _attempt("2026-08-02", "m2", 0, valid=False, score=0.0, cost=0.005),
        ],
    },
]


def test_aggregate_basics():
    board = aggregate(DOCS)
    m1 = next(r for r in board["models"] if r["model"] == "m1")
    assert m1["n_days"] == 2
    assert m1["n_attempts"] == 4
    assert m1["n_api_errors"] == 1
    assert m1["avg_score"] == pytest.approx((1.0 + 0.0 + 0.75) / 3)
    assert m1["solve_rate"] == pytest.approx(2 / 3)
    assert m1["invalid_rate"] == pytest.approx(1 / 3)
    assert m1["pass_rate_days"] == 1.0
    assert m1["mean_over_par_solved"] == pytest.approx(1.0)
    assert m1["total_cost"] == pytest.approx(0.06)
    assert m1["mean_cost_per_attempt"] == pytest.approx(0.02)
    assert m1["cost_per_solve"] == pytest.approx(0.03)


def test_aggregate_no_solves():
    m2 = next(r for r in aggregate(DOCS)["models"] if r["model"] == "m2")
    assert m2["cost_per_solve"] is None
    assert m2["avg_score"] == 0.0


def test_rolling_window():
    m1 = next(r for r in aggregate(DOCS)["models"] if r["model"] == "m1")
    # window anchored at latest date (2026-08-02); 2026-01-01 excluded
    assert m1["rolling30"]["avg_score"] == pytest.approx(0.75)
    assert m1["rolling30"]["solve_rate"] == 1.0
    assert m1["rolling30"]["mean_cost_per_attempt"] == pytest.approx(0.03)


def test_toplevel():
    board = aggregate(DOCS)
    assert board["n_days"] == 2
    assert board["dates"] == ["2026-01-01", "2026-08-02"]
    assert board["prompt_versions"] == ["1"]


def test_known_model_gets_roster_metadata():
    docs = [dict(DOCS[1], attempts=[_attempt("2026-08-02", "x-ai/grok-4.6", 0, valid=True, score=1.0, cost=0.01, over_par=0)])]
    row = aggregate(docs)["models"][0]
    assert row["label"] == "Grok 4.6" and row["lab"] == "xAI"
