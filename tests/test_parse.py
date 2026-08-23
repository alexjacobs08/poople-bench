from poople_bench.parse import parse_ladder


def test_clean_json_object():
    ladder, parser = parse_ladder('{"ladder": ["girl", "gill", "poop"]}')
    assert ladder == ["girl", "gill", "poop"] and parser == "json"


def test_bare_json_array():
    ladder, parser = parse_ladder('["girl", "gill", "poop"]')
    assert ladder == ["girl", "gill", "poop"] and parser == "json"


def test_fenced_json_with_prose():
    text = 'Sure! Here is my ladder:\n```json\n{"ladder": ["girl", "gill"]}\n```\nGood luck!'
    ladder, parser = parse_ladder(text)
    assert ladder == ["girl", "gill"] and parser == "json_embedded"


def test_last_json_object_wins():
    text = '{"ladder": ["wrong"]} some thinking... {"ladder": ["girl", "gill", "poop"]}'
    ladder, _ = parse_ladder(text)
    assert ladder == ["girl", "gill", "poop"]


def test_arrow_tokens_fallback():
    ladder, parser = parse_ladder("My answer: GIRL -> GILL -> PILL -> POLL -> POOL -> POOP")
    assert ladder == ["girl", "gill", "pill", "poll", "pool", "poop"] and parser == "tokens"


def test_tokens_after_rambling():
    text = "girl gill pall no wait that fails. Final answer: girl gill pill poll pool poop"
    ladder, parser = parse_ladder(text)
    assert ladder == ["girl", "gill", "pill", "poll", "pool", "poop"] and parser == "tokens"


def test_garbage():
    assert parse_ladder("I cannot solve this puzzle, sorry.") == (None, "none")


def test_empty():
    assert parse_ladder("") == (None, "none")
    assert parse_ladder(None) == (None, "none")


def test_non_string_items_rejected():
    ladder, parser = parse_ladder('{"ladder": [1, 2, 3]}')
    assert ladder is None and parser == "none"
