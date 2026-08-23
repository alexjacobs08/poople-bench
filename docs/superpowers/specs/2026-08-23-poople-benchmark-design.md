# Poople Bench — design spec (2026-08-23)

A daily LLM benchmark on the word game **Poople** (poople.io): transform the day's
4-letter start word into **POOP**, changing one letter per step, every rung a word in the
game's 2,398-word dictionary. Models attempt it **one-shot** (whole ladder in a single
response) and are scored against the provable optimum (par, computed by BFS). Results
compare **accuracy vs cost** across ~20 models via OpenRouter, run daily by GitHub
Actions, published on a static dashboard.

Decisions locked with Alex (2026-08-23): open-book headline task; sampled historical
backfill to start; exclude ultra-expensive models (Claude Fable 5, GPT-5.5 Pro) for now
but keep roster slots for them; Python; plain OpenRouter HTTP calls + pydantic models
(pydantic-ai only if a framework becomes necessary); repo on GitHub under alexjacobs08.

## Task format

- **One-shot, open-book.** Prompt contains: rules, the day's start word, and the full
  legal dictionary (~2.4k words, ~3.5k tokens, cacheable). No tools, no web. Par is NOT
  revealed — finding the shortest ladder is the task.
- Output: JSON object `{"ladder": ["girl", ..., "poop"]}` — ladder includes the start
  word first and ends with "poop". Requested via `response_format` JSON schema where the
  endpoint supports it; tolerant fallback parsing (extract last JSON object / word list)
  because schema enforcement is per-endpoint and unreliable on cheap providers.
- Sampling: provider defaults; `reasoning: {effort: "medium"}` where the model supports
  a reasoning parameter (roster field, per-model override allowed). Rationale: temp-0 is
  neither reproducible nor supported on many reasoning models.

## Scoring (two layers, ClemBench pattern)

- **Validity**: ladder starts with the day's word, ends with POOP, each step changes
  exactly one letter, every word (except validated start) in the dictionary. Invalid → 0
  for the headline, with failure diagnostics logged: `format_error` (unparseable),
  `invalid_word`, `broken_step`, `wrong_start`, `no_poop`; plus longest-valid-prefix.
- **Quality** (valid only): `par / steps` where `steps = len(ladder) - 1`
  (par = 1.0; displayed golf-style as "+N over par", matching the game's own
  "extra guesses" stat).
- Per-model-per-day score = mean over k trials of validity × quality (**avg@k**,
  headline). **pass@k** (any trial valid) and best-over-par as secondary columns.
- Leaderboard aggregates: mean daily score (all-time and rolling 30-day), solve rate,
  mean over-par among solves, invalid rate, mean cost/puzzle (sum of trial costs ÷ k),
  $-per-solved-puzzle. Daily rankings are entertainment; the rolling aggregate is the
  benchmark.

## Trials & schedule

- Daily run: **k = 3** trials per model, cron at ~08:20 UTC (puzzle flips 08:00 UTC).
- Backfill: **stratified sample of 50 past days** (by par, indices 1–373), **k = 1**.
  Full-history backfill is a possible later step.
- Day index formula (verified against live site): puzzle for index *i* is active from
  08:00 UTC on (2025-08-14 + *i* days); schedule + pars embedded in `research/data/`
  and re-verified by our own BFS (zero mismatches).

## Model roster (initial ~20)

Spans ~$0.03–$3/M input, ~$0.13–$25/M output. Stored as data (`roster.py` or yaml) with
`enabled` flags; Fable 5 / GPT-5.5 Pro present but disabled. Initial enabled set:
gpt-5.6-sol, gpt-5.6-luna, claude-opus-5, claude-sonnet-5, claude-haiku-4.5,
gemini-3.1-pro-preview, gemini-3.7-flash, gemini-3.5-flash-lite, grok-4.6,
deepseek-v4-pro-0813, deepseek-v4-flash-0731, muse-spark-1.2, muse-spark-1.2-contributor,
qwen3.8-max, qwen3.7-flash, kimi-k3, kimi-k2.6, mistral-medium-3-5, mistral-small-2603.
IDs verified against the live OpenRouter catalog snapshot in `research/data/`.

## Cost accounting

Exact per-request cost from the OpenRouter response `usage.cost` (native token counts,
reasoning tokens logged from `completion_tokens_details.reasoning_tokens`); provider
actually used recorded from the response. No provider pinning in v1 (recorded, not
constrained); revisit if cross-provider variance shows up in the data.

## Architecture

```
pyproject.toml            # uv-managed; deps: httpx, pydantic; dev: pytest
src/poople_bench/
  game.py                 # dictionary load, BFS distances, ladder validation, day index
  data/words.csv, schedule.csv   # packaged copies of extracted game data
  roster.py               # model roster (id, label, lab, pricing snapshot, enabled, reasoning)
  prompt.py               # prompt construction (fixed, versioned PROMPT_VERSION)
  client.py               # OpenRouter HTTP call, retries/backoff, usage extraction
  parse.py                # strict JSON + tolerant fallback ladder extraction
  score.py                # attempt scoring + aggregation to leaderboard
  cli.py                  # commands: daily, backfill, aggregate, verify-data
results/daily/YYYY-MM-DD.json   # one file per puzzle-day: all models × trials
results/leaderboard.json        # aggregate, regenerated by `aggregate`
site/index.html                 # static dashboard (Pareto scatter: score vs log-cost)
.github/workflows/daily.yml     # cron 08:20 UTC: run k=3, aggregate, commit, deploy Pages
tests/                          # TDD: game logic, parsing, scoring, aggregation
```

- Attempt record fields: date, index, word, par, model id, trial, provider, ladder (raw +
  parsed), valid, failure kind, steps, over_par, score, prompt/completion/reasoning
  tokens, cost USD, latency s, generation id, prompt version.
- Failures of the API (timeouts, 429 after retries) recorded as `api_error` and excluded
  from score aggregation (not zero-scored) but reported as a reliability column.
- Dashboard: score (y, linear) vs mean cost/puzzle (x, log) scatter with Pareto frontier
  highlighted; leaderboard table; per-day drill-down. Static JSON, no backend.
- Secrets: `OPENROUTER_API_KEY` in local `.env` (gitignored) and GitHub Actions secret.

## Error handling & edge cases

- Tolerant parse order: strict JSON schema response → last JSON object in text → fenced
  code block → uppercase/lowercase word-sequence heuristic; all recorded with which
  parser succeeded.
- Words compared case-insensitively; start word accepted whether or not model repeats it
  (ladder normalized to include it).
- Schedule exhaustion (2028-09) and site redesigns: harness never contacts poople.io; a
  `verify-data` command re-runs BFS validation of packaged data.

## Testing

TDD for pure logic: validation (legal/illegal ladders, all failure kinds), BFS pars vs
embedded values, day-index math against known anchors (#374 = GIRL on 2026-08-23),
parsing fallbacks, scoring math, aggregation. Client tested against a mocked transport;
one live smoke test with a cheap model before the full run.
