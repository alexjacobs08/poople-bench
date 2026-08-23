# Poople Bench 💩

**Can LLMs one-shot the daily [Poople](https://poople.io) word ladder?**

Poople is a daily word game: transform the day's 4-letter start word into **POOP**,
changing one letter per step, where every rung must be an accepted word. This benchmark
gives ~20 models (via [OpenRouter](https://openrouter.ai)) the puzzle **one-shot** — the
whole ladder in a single response, no feedback, no tools — and scores them against the
**provable optimum** (par, computed by BFS over the game's own dictionary).

**Dashboard:** https://alexjacobs08.github.io/poople-bench/

## Method

- **Open book:** the prompt contains the rules, the day's start word, and the full
  2,398-word legal list (extracted from the game's own JS — see `research/GAME.md`).
  Par is never revealed; finding the shortest ladder is the task.
- **Scoring:** a legal ladder scores `par ÷ steps` (optimal = 100%, displayed
  golf-style as +N over par); an illegal ladder scores 0, with the failure kind logged
  (bad format / invalid word / broken step / didn't reach POOP). API errors are excluded
  from scores and reported separately.
- **Trials:** k=3 per model per day (avg@k headline), provider-default sampling,
  reasoning effort pinned per model. Backfilled historical days (a par-stratified
  sample) run at k=1. Single-day rankings are entertainment — trust the rolling
  30-day aggregate.
- **Cost:** exact per-request charges from OpenRouter's `usage.cost`, plotted as a
  score-vs-cost Pareto frontier.
- The harness never contacts poople.io: the dictionary, daily schedule, and pars are
  packaged and re-verified by independent BFS (`poople-bench verify-data`).

## Running it

```bash
uv sync
echo "OPENROUTER_API_KEY=sk-or-..." > .env

uv run poople-bench verify-data          # sanity-check packaged game data
uv run poople-bench daily --trials 3     # run today's puzzle
uv run poople-bench backfill --sample 50 # stratified historical sample (k=1)
uv run poople-bench aggregate            # rebuild results/leaderboard.json
uv run pytest                            # test suite
```

Results land in `results/daily/YYYY-MM-DD.json` (every attempt, including the raw
ladders); `results/leaderboard.json` powers the dashboard. A GitHub Actions cron runs
the daily puzzle at 08:20 UTC (20 minutes after the puzzle flips) and redeploys the
dashboard.

## Repo map

- `src/poople_bench/` — harness (game logic, prompt, OpenRouter client, scoring, CLI)
- `results/` — all attempts + aggregated leaderboard (committed daily)
- `site/` — static dashboard
- `research/` — how the game works, extracted data, design notes
- `docs/superpowers/` — design spec and implementation plan
