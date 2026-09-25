import json
import re
from pathlib import Path

from poople_bench.game import load_words
from poople_bench.prompt import PROMPT_VERSION, build_prompt
from poople_bench.roster import MODELS, enabled_models

SNAPSHOT = Path(__file__).parent.parent / "research/data/openrouter_models_2026-09-25.json"


def test_all_roster_ids_exist_in_catalog():
    catalog = {m["id"] for m in json.loads(SNAPSHOT.read_text())["data"]}
    # Disabled models may have been delisted; that is usually why they are off.
    missing = [m.id for m in MODELS if m.enabled and m.id not in catalog]
    assert missing == []


def test_expensive_models():
    by_id = {m.id: m for m in MODELS}
    assert by_id["anthropic/claude-fable-5"].enabled  # opted in 2026-08-24
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


def test_trial_tiers():
    by_id = {m.id: m for m in MODELS}
    assert by_id["anthropic/claude-fable-5"].trials == 1
    assert by_id["x-ai/grok-4.6"].trials == 1
    assert by_id["deepseek/deepseek-v4-flash-0731"].trials == 3
    for mid in ["mistralai/mistral-medium-3-5", "mistralai/mistral-small-2603", "qwen/qwen3.8-max"]:
        assert not by_id[mid].enabled
