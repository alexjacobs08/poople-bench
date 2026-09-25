import datetime

import httpx

from poople_bench.choosers import JevJudge
from poople_bench.cli import pending_trials, run_to_record
from poople_bench.game import Puzzle
from poople_bench.roster import JEV, MODELS
from poople_bench.scaffold import Run, Turn

PUZZLE = Puzzle(index=374, date=datetime.date(2026, 8, 23), word="girl", par=5)


def test_jev_is_never_in_the_one_shot_roster():
    assert JEV.id not in {m.id for m in MODELS}


def test_pending_trials_skips_done_trials_of_the_same_experiment_only():
    done = [{"trial": 0, "with_word_list": True}, {"trial": 1}]  # no flag = word-list run
    assert pending_trials(done, 3, with_word_list=True) == [2]
    assert pending_trials(done, 3, with_word_list=False) == [0, 1, 2]


def test_run_to_record_carries_puzzle_cost_and_the_whole_run():
    run = Run(start_word="girl", par=5, path=["girl", "gill", "pill", "poll", "pool", "poop"],
              turns=[Turn(index=0, current_word="girl", legal=True)], solved=True, steps=5,
              strikes=0, strict_score=1.0, assisted_score=1.0, legality_judged=600)
    judge = JevJudge(api_key="k", client=httpx.Client())
    judge.requests, judge.input_tokens, judge.cost = 12, 50_000, 0.0021
    rec = run_to_record(PUZZLE, run, trial=2, with_word_list=True, judge=judge)
    assert rec["model"] == JEV.id and rec["label"] == JEV.label
    assert (rec["date"], rec["start_word"], rec["par"], rec["trial"]) == ("2026-08-23", "girl", 5, 2)
    assert (rec["requests"], rec["cost"], rec["legality_judged"]) == (12, 0.0021, 600)
    assert rec["turns"][0]["current_word"] == "girl"
    assert rec["with_word_list"] is True
