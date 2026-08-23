import json
import re
from pathlib import Path

from poople_bench.game import load_words
from poople_bench.prompt import PROMPT_VERSION, build_prompt
from poople_bench.roster import MODELS, enabled_models

SNAPSHOT = Path(__file__).parent.parent / "research/data/openrouter_models_2026-08-23.json"


def test_all_roster_ids_exist_in_catalog():
    catalog = {m["id"] for m in json.loads(SNAPSHOT.read_text())["data"]}
    missing = [m.id for m in MODELS if m.id not in catalog]
    assert missing == []


def test_expensive_models_present_but_disabled():
    by_id = {m.id: m for m in MODELS}
    assert not by_id["anthropic/claude-fable-5"].enabled
    assert not by_id["openai/gpt-5.5-pro"].enabled


def test_enabled_count_and_uniqueness():
    assert len({m.id for m in MODELS}) == len(MODELS)
    assert len(enabled_models()) >= 18


def test_prompt_contents():
    words = load_words()
    prompt = build_prompt("girl", words)
    assert "GIRL" in prompt
    assert '"ladder"' in prompt
    for w in words:
        assert w in prompt
    # no par leak: the only digit in the prompt is the word length
    assert set(re.findall(r"\d+", prompt)) <= {"4"}
    assert PROMPT_VERSION == "1"
