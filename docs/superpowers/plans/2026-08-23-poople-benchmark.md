# Poople Bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daily one-shot Poople (word-ladder-to-POOP) benchmark across ~20 OpenRouter models, scored against BFS-provable par, with accuracy-vs-cost dashboard and GitHub Actions cron.

**Architecture:** Pure-logic core (game data, validation, scoring) is fully offline and TDD'd; a thin httpx client hits OpenRouter chat completions and records exact `usage.cost`; a CLI orchestrates daily runs / sampled backfill / aggregation into static JSON; a single-file static dashboard renders the Pareto scatter; GitHub Actions runs daily at 08:20 UTC and deploys Pages.

**Tech Stack:** Python 3.12, uv, httpx, pydantic, pytest. No LLM framework (plain HTTP; pydantic-ai only if needed later). Static HTML/JS dashboard, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-08-23-poople-benchmark-design.md`

## Global Constraints

- Python >= 3.12, uv-managed; runtime deps ONLY httpx + pydantic; dev deps pytest.
- Harness never contacts poople.io; game data is packaged from `research/data/`.
- Words compared lowercase; ladder normalized to include start word; steps = len(ladder) - 1.
- Par is never revealed in the prompt. PROMPT_VERSION recorded on every attempt.
- API errors excluded from score aggregation (reported separately); invalid ladders score 0.
- Secrets only via env `OPENROUTER_API_KEY` (local `.env` is gitignored; Actions secret already set).
- Attribution trailer on every commit (Co-Authored-By + Claude-Session, per session config).

---

### Task 1: Scaffold + game core (data, BFS, day index, validation)

**Files:**
- Create: `pyproject.toml`, `src/poople_bench/__init__.py`, `src/poople_bench/game.py`, `src/poople_bench/data/words.csv` (copy of `research/data/poople_words.csv`), `src/poople_bench/data/schedule.csv` (copy of `research/data/poople_schedule.csv`)
- Test: `tests/test_game.py`

**Interfaces:**
- Produces: `load_words() -> dict[str, int]` (word→par); `load_schedule() -> list[Puzzle]`; `Puzzle` (pydantic: `index: int, date: datetime.date, word: str, par: int`); `puzzle_for_date(d: date) -> Puzzle`; `bfs_distances(words: set[str]) -> dict[str, int]`; `validate_ladder(start: str, ladder: list[str], words: set[str]) -> Validation` where `Validation` (pydantic) has `valid: bool, failure: str | None, steps: int | None, ladder: list[str]` (normalized), failure ∈ {`wrong_start`, `invalid_word`, `broken_step`, `no_poop`, `empty`}.

- [ ] **Step 1:** `uv init --lib` shape: write `pyproject.toml` (name `poople-bench`, `requires-python >=3.12`, deps `httpx`, `pydantic`; `[dependency-groups] dev = ["pytest"]`), copy the two CSVs into `src/poople_bench/data/`.
- [ ] **Step 2:** Write failing tests in `tests/test_game.py`:

```python
import datetime
from poople_bench.game import (load_words, load_schedule, puzzle_for_date,
                               bfs_distances, validate_ladder)

def test_words_load():
    w = load_words()
    assert len(w) == 2398 and w["poop"] == 0 and w["boop"] == 1

def test_schedule_anchor_girl():
    p = puzzle_for_date(datetime.date(2026, 8, 23))
    assert (p.index, p.word, p.par) == (374, "girl", 5)

def test_schedule_bounds():
    s = load_schedule()
    assert s[1].word == "dawn" and s[1].date == datetime.date(2025, 8, 15)
    assert s[-1].date == datetime.date(2028, 9, 23)

def test_bfs_matches_embedded():
    w = load_words()
    assert bfs_distances(set(w)) == w

def test_valid_ladder():
    w = set(load_words())
    v = validate_ladder("ends", ["ends","ands","aids","bids","bods","boos","boop","poop"], w)
    assert v.valid and v.steps == 7 and v.failure is None

def test_start_word_not_repeated_is_normalized():
    w = set(load_words())
    v = validate_ladder("girl", ["gird","bird","bind","band","bond","bood","pood","poop"], w)
    # normalization prepends start; here girl->gird is 1 letter so chain continues
    assert v.ladder[0] == "girl"

def test_invalid_word():
    w = set(load_words())
    v = validate_ladder("girl", ["girl","gxrl","poop"], w)
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
    w = set(load_words())
    v = validate_ladder("girl", ["dawn", "down", "poop"], w)
    assert not v.valid and v.failure == "wrong_start"

def test_case_insensitive():
    w = set(load_words())
    v = validate_ladder("GIRL", ["GIRL","GIRD","BIRD","BIND","BOND","BOOD","POOD","POOP"], w)
    assert v.valid
```

(Real ladder fixtures must be checked against the dictionary while implementing; adjust fixture words to legal ones if any is absent, keeping the tested property intact.)
- [ ] **Step 3:** Run `uv run pytest -x` → expect import failures.
- [ ] **Step 4:** Implement `game.py`: CSV loads via `importlib.resources`; `EPOCH = date(2025, 8, 14)`; `puzzle_for_date` index = `(d - EPOCH).days`; BFS from "poop" over one-letter neighbors; `validate_ladder` lowercases, drops empty, prepends start if `ladder[0] != start`, checks in order: wrong_start (first elem ≠ start after normalize — only when model gave a different explicit start), each pair hamming distance == 1 else `broken_step`, each word after index 0 in dict else `invalid_word`, last == "poop" else `no_poop`.
- [ ] **Step 5:** `uv run pytest -x` → all pass. Commit.

### Task 2: Output parsing (`parse.py`)

**Files:** Create `src/poople_bench/parse.py`; Test `tests/test_parse.py`

**Interfaces:**
- Produces: `parse_ladder(text: str) -> tuple[list[str] | None, str]` returning (ladder-or-None, parser name ∈ {`json`, `json_embedded`, `tokens`, `none`}).

- [ ] **Step 1:** Failing tests: clean JSON object; JSON with markdown fence + prose around it; JSON array only (`["girl","poop"]` → accepted as ladder); prose with arrow-separated uppercase words ending in POOP (tokens parser); garbage → `(None, "none")`; JSON with non-string items → None.
- [ ] **Step 2:** Implement: (1) `json.loads` of whole text, accept `{"ladder": [...]}` or bare list; (2) scan for last balanced `{...}`/`[...]` block that parses and contains a ladder (strip code fences first); (3) tokens fallback: all 4-letter alpha tokens lowercased, truncate at last `poop`, walk backwards keeping consecutive hamming-distance-1 chain. Return longest chain ≥ 2.
- [ ] **Step 3:** Tests pass. Commit.

### Task 3: Roster + prompt

**Files:** Create `src/poople_bench/roster.py`, `src/poople_bench/prompt.py`; Test `tests/test_roster.py`

**Interfaces:**
- Produces: `Model` (pydantic: `id, label, lab, input_per_m: float, output_per_m: float, enabled: bool = True, reasoning_effort: str | None = None`); `MODELS: list[Model]`; `enabled_models() -> list[Model]`; `build_prompt(start: str, words: Iterable[str]) -> str`; `PROMPT_VERSION = "1"`.

- [ ] **Step 1:** Failing tests: every `MODELS` id exists in `research/data/openrouter_models_2026-08-23.json`; disabled set contains `anthropic/claude-fable-5` and `openai/gpt-5.5-pro`; ≥ 18 enabled; prompt contains start word uppercase, all 2,398 words, the string `"ladder"`, and does NOT contain the digits of par (assert "par" not mentioned / no leak of schedule).
- [ ] **Step 2:** Implement roster (19 enabled per spec + 2 disabled slots, prices from snapshot; `reasoning_effort="medium"` for models whose catalog entry supports the `reasoning` parameter, else None — check snapshot while writing). Prompt per spec: rules (exactly one letter changes per step, positions preserved), legal word list space-separated lowercase, instruction to output ONLY `{"ladder": ["<start>", ..., "poop"]}`, "find the shortest ladder you can". 
- [ ] **Step 3:** Tests pass. Commit.

### Task 4: OpenRouter client

**Files:** Create `src/poople_bench/client.py`; Test `tests/test_client.py`

**Interfaces:**
- Produces: `Attempt` (pydantic: `date: str, index: int, word: str, par: int, model: str, trial: int, mode: str, provider: str | None, raw: str | None, ladder: list[str] | None, parser: str, valid: bool, failure: str | None, steps: int | None, over_par: int | None, score: float, prompt_tokens: int | None, completion_tokens: int | None, reasoning_tokens: int | None, cost: float | None, latency_s: float | None, generation_id: str | None, prompt_version: str, error: str | None`); `call_openrouter(model: Model, prompt: str, api_key: str, client: httpx.Client, timeout: float = 300) -> dict` (raw response json) raising `ApiError(str)` after retries.

- [ ] **Step 1:** Failing tests with `httpx.MockTransport`: success path returns json and request body contained `response_format.json_schema` and `reasoning.effort` when set (and omitted when None); 429 then success (retry works); persistent 500 → `ApiError`; 400 mentioning response_format → retried once WITHOUT `response_format` and succeeds.
- [ ] **Step 2:** Implement: POST `https://openrouter.ai/api/v1/chat/completions`, headers incl. `HTTP-Referer`/`X-Title` (repo URL / "Poople Bench"), body `{model, messages:[{role:"user",content:prompt}], response_format:{type:"json_schema",json_schema:{name:"ladder",strict:true,schema:{type:"object",properties:{ladder:{type:"array",items:{type:"string"}}},required:["ladder"],additionalProperties:false}}}}` + `reasoning:{effort}` if set. Retries: up to 2 on 429/5xx/transport with 5s/20s sleeps; one schema-less retry on 400 containing "response_format"/"json_schema"/"structured". Extract helper `attempt_from_response(resp_json, ...) -> Attempt` pulling `usage.cost`, tokens, `completion_tokens_details.reasoning_tokens`, `provider`, `id`.
- [ ] **Step 3:** Tests pass. Commit.

### Task 5: Scoring + aggregation

**Files:** Create `src/poople_bench/score.py`; Test `tests/test_score.py`

**Interfaces:**
- Consumes: `Attempt`, `Validation`.
- Produces: `score_ladder(par: int, valid: bool, steps: int | None) -> float` (= `par/steps` if valid else 0.0); `run_attempt_record(...)` assembled in cli (not here); `aggregate(day_docs: list[dict]) -> dict` building leaderboard: per model `{model, label, lab, input_per_m, output_per_m, n_days, n_attempts, n_api_errors, avg_score, solve_rate, pass_rate_days, mean_over_par_solved, invalid_rate, mean_cost_per_attempt, total_cost, cost_per_solve, rolling30: {avg_score, solve_rate, mean_cost_per_attempt}}` plus top-level `{generated_at, n_days, dates, prompt_version(s)}`. Scored attempts = those with `error is None`.

- [ ] **Step 1:** Failing tests: score math (par 5, steps 5 → 1.0; steps 7 → 5/7; invalid → 0); aggregation over two synthetic day-docs with one api_error attempt (excluded from avg_score denominator but counted in `n_api_errors`), cost sums, `cost_per_solve = total_cost / n_solves` and `inf`→`None` when no solves; rolling30 respects date window.
- [ ] **Step 2:** Implement. Tests pass. Commit.

### Task 6: CLI (`daily`, `backfill`, `aggregate`, `verify-data`)

**Files:** Create `src/poople_bench/cli.py`; register `[project.scripts] poople-bench = "poople_bench.cli:main"`; Test `tests/test_cli.py` (backfill sampling only)

**Interfaces:**
- Consumes: everything above.
- Produces: `results/daily/YYYY-MM-DD.json` docs `{date, index, word, par, mode, attempts: [Attempt...]}`; `results/leaderboard.json`; `results/index.json` (manifest: list of daily files + dates). Commands:
  - `daily [--date D] [--trials 3] [--models a,b] [--workers 8] [--timeout 300]` — resumable: skips (model, trial) pairs already recorded without error; ThreadPoolExecutor over (model, trial).
  - `backfill [--sample 50] [--trials 1] [--seed 42]` — stratified-by-par proportional sample of indices 1..today_index-1 (round up per stratum, then trim), runs same machinery with `mode="backfill"`.
  - `aggregate` — rebuild leaderboard.json + index.json from all daily files.
  - `verify-data` — BFS check vs packaged pars + GIRL anchor; exit nonzero on mismatch.
- Env: `OPENROUTER_API_KEY` read from environment; also parse `.env` if present (tiny loader, no dependency).

- [ ] **Step 1:** Failing test for `stratified_sample(schedule, n=50, seed=42)`: returns 50 unique indices in 1..373, includes at least one index with par ≥ 8, deterministic for same seed.
- [ ] **Step 2:** Implement sampling + CLI wiring (argparse). Attempt assembly: call → parse → validate → score → `Attempt`; on `ApiError` record attempt with `error` set and `score=0` but flagged. Write day doc after each model completes (crash-safe incremental writes).
- [ ] **Step 3:** Tests pass; `uv run poople-bench verify-data` passes. Commit.
- [ ] **Step 4:** Live smoke: `uv run poople-bench daily --models deepseek/deepseek-v4-flash-0731 --trials 1` — inspect the produced JSON (cost present, ladder validated). Fix reality mismatches (response shapes). Commit.

### Task 7: Dashboard (`site/index.html`)

**Files:** Create `site/index.html` (self-contained HTML/CSS/JS)

**Interfaces:** Consumes `./results/leaderboard.json` + `./results/index.json` + daily files (fetched relative; the deploy step copies `results/` into the site root).

- [ ] **Step 1:** LOAD the `dataviz` skill before writing any chart code (required trigger), and follow it.
- [ ] **Step 2:** Build: header with today's puzzle + link to poople.io; Pareto scatter (y = rolling-30 or all-time avg score 0–100%, x = mean cost/attempt USD log scale, frontier stepped line, non-frontier dimmed, frontier labels); leaderboard table (rank, model, lab, avg score, solve rate, mean +over-par, invalid rate, cost/attempt, $/solve); per-day drill-down (date picker → per-model trial outcomes incl. ladders); methodology footnote. Hand-rolled SVG (no CDN deps), light/dark aware.
- [ ] **Step 3:** Test locally: `python3 -m http.server` with results copied in; verify rendering via Playwright browser. Commit.

### Task 8: GitHub Actions (daily cron + Pages)

**Files:** Create `.github/workflows/daily.yml`, `.github/workflows/pages.yml` (or single workflow with two jobs)

- [ ] **Step 1:** `daily.yml`: `schedule: cron "20 8 * * *"` + `workflow_dispatch`; permissions `contents: write`; steps: checkout, `astral-sh/setup-uv`, `uv sync`, `uv run poople-bench daily --trials 3`, `uv run poople-bench aggregate`, commit+push results (skip-ci), then trigger pages job. `pages.yml` (on push to main + workflow_call): build artifact = `site/` + `results/` copied inside, `actions/upload-pages-artifact` + `actions/deploy-pages`; permissions `pages: write, id-token: write`.
- [ ] **Step 2:** Enable Pages via `gh api repos/alexjacobs08/poople-bench/pages -X POST -f build_type=workflow`. Push; `workflow_dispatch` the pages build; verify site URL serves.
- [ ] **Step 3:** Commit.

### Task 9: Live runs (today + backfill sample) and verification

- [ ] **Step 1:** `uv run poople-bench daily --trials 3` locally (full enabled roster, today = GIRL). Watch for per-model failures; record total cost from key usage endpoint.
- [ ] **Step 2:** `uv run poople-bench backfill --sample 50 --trials 1 --seed 42`.
- [ ] **Step 3:** `aggregate`, commit results, deploy, verify dashboard live in browser (Pareto chart sane, costs sum ≈ OpenRouter dashboard usage).
- [ ] **Step 4:** README.md: what it is, methodology summary (link spec), how to run, dashboard link. Commit, push. Verify Actions dispatch of daily.yml end-to-end once.

## Self-review notes

- Spec coverage: task 1 (data/index/validation), 2 (tolerant parsing), 3 (open-book prompt, roster incl. disabled expensive slots), 4 (usage.cost accounting, schema fallback), 5 (two-layer scoring, avg@k via aggregation over trials, rolling window), 6 (k=3 daily, stratified 50-day backfill k=1, resumability), 7 (Pareto dashboard), 8 (08:20 UTC cron, Pages), 9 (verification). Provider pinning deliberately deferred per spec ("record, don't constrain").
- Types consistent: `Attempt`/`Validation`/`Model` defined once (tasks 1/3/4) and consumed by 5/6.
