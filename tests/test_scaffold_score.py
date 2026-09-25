import pytest

from poople_bench.game import load_words
from poople_bench.scaffold_score import BASELINES, aggregate_scaffold

WORDS = load_words()


def run(solved=True, steps=5, par=5, strikes=0, date="2026-09-01", start="hype",
        with_word_list=True, turns=None, cost=0.002, judged=100, wrong=0):
    score = par / steps if solved else 0.0
    return {
        "model": "jev-latest", "label": "Jev 1.13", "lab": "TypeSafe",
        "with_word_list": with_word_list, "date": date, "start_word": start, "par": par,
        "trial": 0, "solved": solved, "steps": steps, "strikes": strikes,
        "strict_score": score if not strikes else 0.0, "assisted_score": score,
        "cost": cost, "requests": 20, "legality_judged": judged, "legality_wrong": wrong,
        "turns": turns or [],
    }


def turn(contested=True, optimal=True, checks=0, correct=0):
    return {"contested": contested, "optimal": optimal,
            "similarity_checks": checks, "similarity_correct": correct}


def jev_rows(result):
    return [r for r in result["rows"] if r["kind"] == "model"]


def test_word_list_and_no_word_list_runs_are_separate_rows():
    rows = jev_rows(aggregate_scaffold([run(with_word_list=True), run(with_word_list=False)], WORDS))
    assert sorted(r["with_word_list"] for r in rows) == [False, True]


def test_strict_zeroes_a_run_with_any_strike_and_assisted_forgives_it():
    row = jev_rows(aggregate_scaffold([run(steps=5), run(steps=10, strikes=2)], WORDS))[0]
    assert row["mean_strict"] == pytest.approx(0.5)
    assert row["mean_assisted"] == pytest.approx(0.75)
    assert row["solve_rate"] == 1.0 and row["at_par_rate"] == 0.5


def test_right_call_rate_counts_only_contested_turns():
    turns = [turn(True, True), turn(True, False), turn(False, False)]
    row = jev_rows(aggregate_scaffold([run(turns=turns)], WORDS))[0]
    assert row["right_call_rate"] == pytest.approx(0.5)


def test_similarity_and_legality_accuracy_pool_across_runs():
    rows = jev_rows(aggregate_scaffold([
        run(turns=[turn(checks=4, correct=3)], judged=100, wrong=1),
        run(turns=[turn(checks=6, correct=6)], judged=300, wrong=1),
    ], WORDS))
    assert rows[0]["similarity_accuracy"] == pytest.approx(0.9)
    assert rows[0]["legality_error_rate"] == pytest.approx(2 / 400)


def test_cost_is_reported_per_puzzle():
    row = jev_rows(aggregate_scaffold([run(cost=0.002), run(cost=0.004)], WORDS))[0]
    assert row["cost_per_puzzle"] == pytest.approx(0.003)


def test_script_baselines_are_scored_on_exactly_the_same_puzzles():
    result = aggregate_scaffold([run(date="2026-09-01", start="hype", par=5),
                                 run(date="2026-09-02", start="race", par=6)], WORDS)
    base = [r for r in result["rows"] if r["kind"] == "baseline"]
    assert [b["model"] for b in sorted(base, key=lambda b: b["depth"])] == [b.id for b in BASELINES]
    assert all(b["n_puzzles"] == 2 for b in base)
    rnd = next(b for b in base if b["depth"] == 0)
    two = next(b for b in base if b["depth"] == 2)
    assert rnd["mean_strict"] < two["mean_strict"]


def test_baselines_are_deterministic():
    runs = [run(start="fund", date="2026-09-03")]
    a = aggregate_scaffold(runs, WORDS)["rows"]
    b = aggregate_scaffold(runs, WORDS)["rows"]
    assert [r["mean_strict"] for r in a] == [r["mean_strict"] for r in b]


def test_rows_are_ranked_by_strict_score():
    result = aggregate_scaffold([run(start="race", par=6, steps=6, date="2026-09-02")], WORDS)
    scores = [r["mean_strict"] for r in result["rows"]]
    assert scores == sorted(scores, reverse=True)
