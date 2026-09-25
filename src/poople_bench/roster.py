"""Model roster. Prices are $/M tokens, snapshotted 2026-09-25 from the
OpenRouter catalog (research/data/openrouter_models_2026-09-25.json) — display
only; actual cost comes from usage.cost per request.

reasoning_effort: sent as {"reasoning": {"effort": ...}} when set. "medium"
where supported; models whose effort ladder lacks "medium" get their middle
tier; models with no effort list get None (no reasoning parameter sent).
"""

from __future__ import annotations

from pydantic import BaseModel


class Model(BaseModel):
    id: str
    label: str
    lab: str
    input_per_m: float
    output_per_m: float
    enabled: bool = True
    trials: int = 3  # daily trials; expensive models run 1, cheap run 3
    reasoning_effort: str | None = "medium"


MODELS: list[Model] = [
    Model(id="openai/gpt-5.6-sol", label="GPT-5.6 Sol", lab="OpenAI", input_per_m=2, output_per_m=10),
    Model(id="openai/gpt-5.6-luna", label="GPT-5.6 Luna", lab="OpenAI", input_per_m=0.2, output_per_m=1.2),
    # Added 2026-09-25 (released 2026-09-21/22); 30-day backtest pending credit.
    Model(id="anthropic/claude-opus-5.5", label="Claude Opus 5.5", lab="Anthropic", input_per_m=4, output_per_m=20, trials=1),
    Model(id="openai/gpt-6-sol", label="GPT-6 Sol", lab="OpenAI", input_per_m=2, output_per_m=10),
    Model(id="openai/gpt-6-luna", label="GPT-6 Luna", lab="OpenAI", input_per_m=0.1, output_per_m=0.5),
    Model(id="x-ai/grok-4.7", label="Grok 4.7", lab="xAI", input_per_m=1.6, output_per_m=4.8, trials=1),
    Model(id="deepseek/deepseek-v4.1-flash", label="DeepSeek V4.1 Flash", lab="DeepSeek", input_per_m=0.15, output_per_m=0.6, reasoning_effort="high"),
    # Disabled 2026-09-25: reasoned past the 10-minute request timeout on the ladder prompt.
    Model(id="xiaomi/mimo-v2.6-pro", label="MiMo V2.6 Pro", lab="Xiaomi", input_per_m=0.435, output_per_m=0.87, trials=1, enabled=False),
    # Ceiling tier, parked for cost like GPT-5.5 Pro ($10/$50 per M).
    Model(id="openai/gpt-6-astra", label="GPT-6 Astra", lab="OpenAI", input_per_m=10, output_per_m=50, trials=1, enabled=False),
    Model(id="anthropic/claude-opus-5", label="Claude Opus 5", lab="Anthropic", input_per_m=5, output_per_m=25, trials=1),
    Model(id="anthropic/claude-sonnet-5", label="Claude Sonnet 5", lab="Anthropic", input_per_m=2, output_per_m=10, trials=1),
    Model(id="anthropic/claude-haiku-4.5", label="Claude Haiku 4.5", lab="Anthropic", input_per_m=1, output_per_m=5, reasoning_effort=None),
    Model(id="google/gemini-3.1-pro-preview", label="Gemini 3.1 Pro", lab="Google", input_per_m=2, output_per_m=12, trials=1),
    Model(id="google/gemini-3.7-flash", label="Gemini 3.7 Flash", lab="Google", input_per_m=0.75, output_per_m=3.75),
    Model(id="google/gemini-3.5-flash-lite", label="Gemini 3.5 Flash Lite", lab="Google", input_per_m=0.3, output_per_m=2.5),
    Model(id="x-ai/grok-4.6", label="Grok 4.6", lab="xAI", input_per_m=2, output_per_m=6, trials=1),
    Model(id="deepseek/deepseek-v4-pro-0813", label="DeepSeek V4 Pro", lab="DeepSeek", input_per_m=0.34584, output_per_m=1.03752, reasoning_effort="high", trials=1),
    Model(id="deepseek/deepseek-v4-flash-0731", label="DeepSeek V4 Flash", lab="DeepSeek", input_per_m=0.03, output_per_m=0.32, reasoning_effort="high"),
    Model(id="meta/muse-spark-1.2", label="Muse Spark 1.2", lab="Meta", input_per_m=1.25, output_per_m=4.25, trials=1),
    # Disabled 2026-08-24: every request 404s behind an account guardrail the
    # main Muse model doesn't hit. Re-enable if the attestation ever clears.
    Model(id="meta/muse-spark-1.2-contributor", label="Muse Spark 1.2 Contributor", lab="Meta", input_per_m=0.1, output_per_m=0.2, enabled=False),
    # Disabled 2026-08-25 (cost cut): 0% over 51 days while billing ~$0.08/attempt.
    Model(id="qwen/qwen3.8-max", label="Qwen3.8 Max", lab="Qwen", input_per_m=2.0, output_per_m=6.0, enabled=False),
    Model(id="qwen/qwen3.7-flash", label="Qwen3.7 Flash", lab="Qwen", input_per_m=0.03, output_per_m=0.13, reasoning_effort=None),
    Model(id="moonshotai/kimi-k3", label="Kimi K3", lab="Moonshot", input_per_m=3, output_per_m=15, reasoning_effort="high", trials=1),
    Model(id="moonshotai/kimi-k2.6", label="Kimi K2.6", lab="Moonshot", input_per_m=0.95, output_per_m=4, reasoning_effort=None, trials=1),
    # Disabled 2026-08-25 (cost cut): worst $/solve on the board (20%/11% scores).
    Model(id="mistralai/mistral-medium-3-5", label="Mistral Medium 3.5", lab="Mistral", input_per_m=1.5, output_per_m=7.5, reasoning_effort="high", enabled=False),
    Model(id="mistralai/mistral-small-2603", label="Mistral Small 26.03", lab="Mistral", input_per_m=0.15, output_per_m=0.6, reasoning_effort="high", enabled=False),
    Model(id="z-ai/glm-5.3", label="GLM-5.3", lab="Zhipu", input_per_m=1.4, output_per_m=4.4, reasoning_effort="high", trials=1),
    Model(id="minimax/minimax-m3", label="MiniMax M3", lab="MiniMax", input_per_m=0.3, output_per_m=1.2, reasoning_effort=None),
    Model(id="nvidia/nemotron-3-ultra-550b-a55b", label="Nemotron 3 Ultra", lab="Nvidia", input_per_m=0.6, output_per_m=2.4),
    Model(id="thinkingmachines/inkling", label="Inkling", lab="Thinking Machines", input_per_m=1, output_per_m=4.05),
    Model(id="thinkingmachines/inkling-small", label="Inkling Small", lab="Thinking Machines", input_per_m=0.45, output_per_m=1.2),
    # Disabled 2026-08-24: no active endpoints on OpenRouter (every request 404s).
    Model(id="allenai/olmo-3-32b-think", label="OLMo 3 32B Think", lab="AI2", input_per_m=0.15, output_per_m=0.5, reasoning_effort=None, enabled=False),
    # Ceiling models. Fable enabled 2026-08-24 at Alex's request; GPT-5.5 Pro still parked (cost).
    Model(id="anthropic/claude-fable-5", label="Claude Fable 5", lab="Anthropic", input_per_m=10, output_per_m=50, trials=1),
    Model(id="openai/gpt-5.5-pro", label="GPT-5.5 Pro", lab="OpenAI", input_per_m=30, output_per_m=180, enabled=False),
]


def enabled_models() -> list[Model]:
    return [m for m in MODELS if m.enabled]


def model_by_id(model_id: str) -> Model:
    for m in MODELS:
        if m.id == model_id:
            return m
    raise KeyError(model_id)



class JevEntry(BaseModel):
    """The Jev track's one contender. It is not in MODELS: Jev cannot generate a
    ladder, so it never plays the one-shot benchmark."""

    id: str = "jev-latest"  # resolves to jev-1.13.0 as of 2026-09
    label: str = "Jev 1.13"
    lab: str = "TypeSafe"
    trials: int = 3  # Jev is nearly deterministic; 3 catches its run-to-run wobble


JEV = JevEntry()
