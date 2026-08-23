import datetime

from poople_bench.game import (
    bfs_distances,
    load_schedule,
    load_words,
    puzzle_for_date,
    validate_ladder,
)


def test_words_load():
    w = load_words()
    assert len(w) == 2398
    assert w["poop"] == 0
    assert w["boop"] == 1


def test_schedule_anchor_girl():
    # Verified against live poople.io on 2026-08-23: "#374: GIRL", par 5
    p = puzzle_for_date(datetime.date(2026, 8, 23))
    assert (p.index, p.word, p.par) == (374, "girl", 5)


def test_schedule_bounds():
    s = load_schedule()
    assert s[1].word == "dawn"
    assert s[1].date == datetime.date(2025, 8, 15)
    assert s[-1].date == datetime.date(2028, 9, 23)


def test_bfs_matches_embedded():
    w = load_words()
    assert bfs_distances(set(w)) == w


def test_valid_ladder():
    w = set(load_words())
    v = validate_ladder("ends", ["ends", "ands", "aids", "bids", "bods", "boos", "boop", "poop"], w)
    assert v.valid and v.steps == 7 and v.failure is None


def test_optimal_girl_ladder():
    w = set(load_words())
    v = validate_ladder("girl", ["girl", "gill", "pill", "poll", "pool", "poop"], w)
    assert v.valid and v.steps == 5


def test_start_word_not_repeated_is_normalized():
    w = set(load_words())
    v = validate_ladder("girl", ["gill", "pill", "poll", "pool", "poop"], w)
    assert v.valid and v.ladder[0] == "girl" and v.steps == 5


def test_invalid_word():
    w = set(load_words())
    v = validate_ladder("girl", ["girl", "gxrl", "gxrp", "poop"], w)
    assert not v.valid and v.failure == "invalid_word"


def test_broken_step():
    w = set(load_words())
    v = validate_ladder("girl", ["girl", "pool", "poop"], w)
    assert not v.valid and v.failure == "broken_step"


def test_no_poop():
    w = set(load_words())
    v = validate_ladder("girl", ["girl", "gird"], w)
    assert not v.valid and v.failure == "no_poop"


def test_wrong_start():
    # First word is neither the start word nor one step from it
    w = set(load_words())
    v = validate_ladder("girl", ["dawn", "down", "poop"], w)
    assert not v.valid and v.failure == "wrong_start"


def test_empty_ladder():
    w = set(load_words())
    v = validate_ladder("girl", [], w)
    assert not v.valid and v.failure == "empty"


def test_case_insensitive():
    w = set(load_words())
    v = validate_ladder("GIRL", ["GIRL", "GILL", "PILL", "POLL", "POOL", "POOP"], w)
    assert v.valid and v.steps == 5
