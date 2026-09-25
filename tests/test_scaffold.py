import random
import re

import pytest

from poople_bench.game import load_words
from poople_bench.scaffold import (
    TARGET,
    differs,
    edits,
    play,
    script_play,
)

WORDS = load_words()  # word -> BFS distance to POOP
VOCAB = set(WORDS)


def read(description):
    """(word the move makes, follow-up word or None), recovered from the text Jev reads."""
    quoted = re.findall(r'"([a-z]{4})"', description)
    return quoted[1], (quoted[2] if len(quoted) > 2 else None)


class OracleJudge:
    """Perfect judgments, so tests pin the harness rather than a model."""

    def __init__(self, words=VOCAB, fake_words=()):
        self.words = set(words) | set(fake_words)
        self.legality_asked: list[str] = []
        self.closest_groups: list[dict] = []
        self.choose_calls: list[dict] = []

    def legality(self, strings):
        self.legality_asked += list(strings)
        return {s: 1.0 if s in self.words else 0.0 for s in strings}

    def closest(self, groups):
        self.closest_groups.append(groups)
        return {k: min(ws, key=lambda w: (differs(w), w)) for k, ws in groups.items()}

    def choose(self, state, criteria):
        self.choose_calls.append({"state": state, "criteria": criteria})
        look = {k: read(v) for k, v in criteria.items()}
        best = min(criteria, key=lambda k: (differs(look[k][1] or look[k][0]), differs(look[k][0]), k))
        return best, {k: float(k == best) for k in criteria}, 1.0


def test_edits_are_the_100_single_letter_changes_with_their_results():
    es = edits("hype")
    assert len(es) == 100
    assert ("p2=o", "hope") in es
    assert all(k != f"p{i}={c}" for k, _ in es for i, c in enumerate("hype", 1))


def test_differs_counts_letters_out_of_place_against_poop():
    assert differs("poop") == 0
    assert differs("pomp") == 1
    assert differs("hope") == 3
    assert differs("hype") == 4


def test_a_perfect_judge_solves_and_scores_like_the_main_bench():
    run = play("hype", 5, OracleJudge(), WORDS)
    assert run.solved
    assert run.path[0] == "hype" and run.path[-1] == TARGET
    assert all(w in VOCAB for w in run.path)
    assert run.strikes == 0
    assert run.strict_score == run.assisted_score == pytest.approx(5 / run.steps)


def test_a_word_is_never_offered_twice():
    judge = OracleJudge()
    run = play("race", 6, judge, WORDS)
    for call, here in zip(judge.choose_calls, run.path):
        assert not any(w in run.path[: run.path.index(here) + 1]
                       for w in (read(v)[0] for v in call["criteria"].values()))


def test_no_string_is_judged_for_legality_twice_in_one_run():
    judge = OracleJudge()
    play("fund", 5, judge, WORDS)
    assert len(judge.legality_asked) == len(set(judge.legality_asked))


def test_a_non_word_the_judge_approves_costs_a_strike_and_is_not_offered_again():
    # "pooe" is not a Poople word; this judge thinks it is, and it looks closest.
    judge = OracleJudge(fake_words={"pooe"})
    run = play("pope", 3, judge, WORDS)
    assert run.strikes >= 1
    assert run.strict_score == 0.0
    struck = [t for t in run.turns if t.result_word == "pooe"]
    assert struck and not struck[0].legal
    later = judge.choose_calls[run.turns.index(struck[0]) + 1:]
    assert all("p3=o" not in c["criteria"] for c in later if '"pope"' in next(iter(c["criteria"].values())))


def test_closest_is_only_asked_about_moves_with_more_than_one_follow_up():
    judge = OracleJudge()
    play("hype", 5, judge, WORDS)
    assert judge.closest_groups
    assert all(len(ws) > 1 for g in judge.closest_groups for ws in g.values())


def test_option_descriptions_carry_no_counts_or_distances():
    judge = OracleJudge()
    play("hype", 5, judge, WORDS)
    text = " ".join(v for c in judge.choose_calls for v in c["criteria"].values())
    assert "letter" not in text and not any(ch.isdigit() for ch in text)


def test_turns_record_whether_each_pick_was_legal_and_on_a_shortest_path():
    run = play("hype", 5, OracleJudge(), WORDS)
    assert all(t.legal for t in run.turns)
    assert run.turns[0].result_word == run.path[1]
    assert run.turns[0].optimal == (WORDS[run.path[1]] == WORDS["hype"] - 1)


def test_the_run_stops_at_max_strikes():
    class AlwaysWrong(OracleJudge):
        def legality(self, strings):
            return {s: 1.0 for s in strings}  # approves every string

        def choose(self, state, criteria):
            bad = next(k for k, v in criteria.items() if read(v)[0] not in VOCAB)
            return bad, None, None

    run = play("hype", 5, AlwaysWrong(), WORDS, max_strikes=3)
    assert run.failure == "max_strikes" and run.strikes == 3 and not run.solved


def test_the_run_stops_at_three_times_par_turns():
    class Wanderer(OracleJudge):
        def choose(self, state, criteria):
            worst = max(criteria, key=lambda k: (differs(read(criteria[k])[0]), k))
            return worst, None, None

    run = play("hype", 5, Wanderer(), WORDS)
    assert not run.solved
    assert run.steps <= 15


def test_script_baselines_are_ordered_by_how_far_they_look():
    rng = random.Random(0)
    starts = [("hype", 5), ("race", 6), ("fund", 5), ("girl", 5), ("ahem", 8)]
    mean = lambda depth: sum(script_play(w, p, WORDS, depth, random.Random(s))
                             for s in range(10) for w, p in starts) / 50
    assert mean(0) < mean(1) <= mean(2)
    assert script_play("hype", 5, WORDS, 2, rng) <= 1.0
