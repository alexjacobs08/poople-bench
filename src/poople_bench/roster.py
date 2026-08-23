"""Model roster. Prices are $/M tokens, snapshotted 2026-08-23 from the
OpenRouter catalog (research/data/openrouter_models_2026-08-23.json) — display
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
    reasoning_effort: str | None = "medium"


MODELS: list[Model] = [
    Model(id="openai/gpt-5.6-sol", label="GPT-5.6 Sol", lab="OpenAI", input_per_m=2.0, output_per_m=10.0),
    Model(id="openai/gpt-5.6-luna", label="GPT-5.6 Luna", lab="OpenAI", input_per_m=0.2, output_per_m=1.2),
    Model(id="anthropic/claude-opus-5", label="Claude Opus 5", lab="Anthropic", input_per_m=5.0, output_per_m=25.0),
    Model(id="anthropic/claude-sonnet-5", label="Claude Sonnet 5", lab="Anthropic", input_per_m=2.0, output_per_m=10.0),
    Model(id="anthropic/claude-haiku-4.5", label="Claude Haiku 4.5", lab="Anthropic", input_per_m=1.0, output_per_m=5.0, reasoning_effort=None),
    Model(id="google/gemini-3.1-pro-preview", label="Gemini 3.1 Pro", lab="Google", input_per_m=2.0, output_per_m=12.0),
    Model(id="google/gemini-3.7-flash", label="Gemini 3.7 Flash", lab="Google", input_per_m=0.375, output_per_m=1.875),
    Model(id="google/gemini-3.5-flash-lite", label="Gemini 3.5 Flash Lite", lab="Google", input_per_m=0.3, output_per_m=2.5),
    Model(id="x-ai/grok-4.6", label="Grok 4.6", lab="xAI", input_per_m=2.0, output_per_m=6.0),
    Model(id="deepseek/deepseek-v4-pro-0813", label="DeepSeek V4 Pro", lab="DeepSeek", input_per_m=1.122, output_per_m=3.366, reasoning_effort="high"),
    Model(id="deepseek/deepseek-v4-flash-0731", label="DeepSeek V4 Flash", lab="DeepSeek", input_per_m=0.08, output_per_m=0.18, reasoning_effort="high"),
    Model(id="meta/muse-spark-1.2", label="Muse Spark 1.2", lab="Meta", input_per_m=1.25, output_per_m=4.25),
    Model(id="meta/muse-spark-1.2-contributor", label="Muse Spark 1.2 Contributor", lab="Meta", input_per_m=0.1, output_per_m=0.2),
    Model(id="qwen/qwen3.8-max", label="Qwen3.8 Max", lab="Qwen", input_per_m=2.0, output_per_m=6.0),
    Model(id="qwen/qwen3.7-flash", label="Qwen3.7 Flash", lab="Qwen", input_per_m=0.03, output_per_m=0.13, reasoning_effort=None),
    Model(id="moonshotai/kimi-k3", label="Kimi K3", lab="Moonshot", input_per_m=3.0, output_per_m=15.0, reasoning_effort="high"),
    Model(id="moonshotai/kimi-k2.6", label="Kimi K2.6", lab="Moonshot", input_per_m=0.541, output_per_m=2.28, reasoning_effort=None),
    Model(id="mistralai/mistral-medium-3-5", label="Mistral Medium 3.5", lab="Mistral", input_per_m=1.5, output_per_m=7.5, reasoning_effort="high"),
    Model(id="mistralai/mistral-small-2603", label="Mistral Small 26.03", lab="Mistral", input_per_m=0.15, output_per_m=0.6, reasoning_effort="high"),
    Model(id="z-ai/glm-5.3", label="GLM-5.3", lab="Zhipu", input_per_m=1.4, output_per_m=4.4, reasoning_effort="high"),
    Model(id="minimax/minimax-m3", label="MiniMax M3", lab="MiniMax", input_per_m=0.3, output_per_m=1.2, reasoning_effort=None),
    Model(id="nvidia/nemotron-3-ultra-550b-a55b", label="Nemotron 3 Ultra", lab="Nvidia", input_per_m=0.6, output_per_m=3.6),
    Model(id="thinkingmachines/inkling", label="Inkling", lab="Thinking Machines", input_per_m=0.95, output_per_m=4.05),
    Model(id="thinkingmachines/inkling-small", label="Inkling Small", lab="Thinking Machines", input_per_m=0.45, output_per_m=1.2),
    Model(id="allenai/olmo-3-32b-think", label="OLMo 3 32B Think", lab="AI2", input_per_m=0.15, output_per_m=0.5, reasoning_effort=None),
    # Ceiling models. Fable enabled 2026-08-24 at Alex's request; GPT-5.5 Pro still parked (cost).
    Model(id="anthropic/claude-fable-5", label="Claude Fable 5", lab="Anthropic", input_per_m=10.0, output_per_m=50.0),
    Model(id="openai/gpt-5.5-pro", label="GPT-5.5 Pro", lab="OpenAI", input_per_m=30.0, output_per_m=180.0, enabled=False),
]


def enabled_models() -> list[Model]:
    return [m for m in MODELS if m.enabled]


def model_by_id(model_id: str) -> Model:
    for m in MODELS:
        if m.id == model_id:
            return m
    raise KeyError(model_id)
