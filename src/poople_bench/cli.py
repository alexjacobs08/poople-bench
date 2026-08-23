"""CLI: daily runs, sampled backfill, aggregation, data verification.

Results live in results/daily/YYYY-MM-DD.json (one doc per puzzle-day, all
models x trials, resumable) and results/leaderboard.json.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from .client import ApiError, Attempt, call_openrouter, extract_response
from .game import (
    Puzzle,
    bfs_distances,
    current_puzzle_date,
    load_schedule,
    load_words,
    puzzle_for_date,
    validate_ladder,
)
from .parse import parse_ladder
from .prompt import PROMPT_VERSION, build_prompt
from .roster import Model, enabled_models, model_by_id
from .score import aggregate, score_ladder

RESULTS_DIR = Path("results")
DAILY_DIR = RESULTS_DIR / "daily"


def _load_env_key() -> str:
    if key := os.environ.get("OPENROUTER_API_KEY"):
        return key
    env = Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            name, _, value = line.strip().partition("=")
            if name == "OPENROUTER_API_KEY" and value:
                return value
    sys.exit("OPENROUTER_API_KEY not set (env or .env)")


def stratified_sample(
    schedule: list[Puzzle], n: int, seed: int, max_index: int
) -> list[int]:
    """Deterministic sample of past puzzle indices, stratified by par so hard
    days are represented proportionally (each par stratum keeps >= 1 pick)."""
    pool = [p for p in schedule if 1 <= p.index < max_index]
    by_par: dict[int, list[int]] = {}
    for p in pool:
        by_par.setdefault(p.par, []).append(p.index)
    rng = random.Random(seed)
    picks: dict[int, list[int]] = {}
    for par, idxs in sorted(by_par.items()):
        k = max(1, round(n * len(idxs) / len(pool)))
        picks[par] = rng.sample(idxs, min(k, len(idxs)))
    while sum(len(v) for v in picks.values()) > n:
        largest = max(picks, key=lambda p: len(picks[p]))
        picks[largest].pop()
    return sorted(i for idxs in picks.values() for i in idxs)


def _run_attempt(
    puzzle: Puzzle,
    model: Model,
    trial: int,
    mode: str,
    prompt: str,
    vocab: set[str],
    api_key: str,
    client: httpx.Client,
    timeout: float,
) -> Attempt:
    base = dict(
        date=puzzle.date.isoformat(),
        index=puzzle.index,
        word=puzzle.word,
        par=puzzle.par,
        model=model.id,
        trial=trial,
        mode=mode,
        prompt_version=PROMPT_VERSION,
    )
    start = time.monotonic()
    try:
        data = call_openrouter(model, prompt, api_key, client, timeout=timeout)
    except (ApiError, Exception) as exc:  # noqa: BLE001 — never kill the run
        return Attempt(**base, latency_s=time.monotonic() - start, error=repr(exc)[:300])
    latency = time.monotonic() - start
    extracted = extract_response(data)
    reasoning = extracted.pop("reasoning", None)
    ladder, parser = parse_ladder(extracted["raw"])
    if ladder is None and reasoning:
        # Empty/unparseable content but a reasoning trace: models sometimes
        # state the final ladder only there. Flagged via the parser name.
        ladder, parser = parse_ladder(reasoning)
        parser = f"reasoning:{parser}" if ladder else "none"
    if ladder is None:
        valid, failure, steps, norm = False, "format_error", None, None
    else:
        v = validate_ladder(puzzle.word, ladder, vocab)
        valid, failure, steps, norm = v.valid, v.failure, v.steps, v.ladder
    return Attempt(
        **base,
        **{k: v for k, v in extracted.items() if k != "raw"},
        raw=(extracted["raw"] or "")[-4000:] or None,
        ladder=norm,
        parser=parser,
        valid=valid,
        failure=failure,
        steps=steps,
        over_par=(steps - puzzle.par) if steps is not None else None,
        score=score_ladder(puzzle.par, valid, steps),
        latency_s=round(latency, 2),
    )


def _day_path(puzzle: Puzzle) -> Path:
    return DAILY_DIR / f"{puzzle.date.isoformat()}.json"


def run_puzzle(
    puzzle: Puzzle,
    models: list[Model],
    trials: int,
    mode: str,
    api_key: str,
    workers: int,
    timeout: float,
) -> None:
    path = _day_path(puzzle)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = (
        json.loads(path.read_text())
        if path.exists()
        else {
            "date": puzzle.date.isoformat(),
            "index": puzzle.index,
            "word": puzzle.word,
            "par": puzzle.par,
            "mode": mode,
            "attempts": [],
        }
    )
    done = {
        (a["model"], a["trial"]) for a in doc["attempts"] if a.get("error") is None
    }
    jobs = [
        (m, t) for m in models for t in range(trials) if (m.id, t) not in done
    ]
    if not jobs:
        print(f"{puzzle.date} #{puzzle.index} {puzzle.word.upper()}: nothing to do")
        return
    # re-running errored attempts: drop their stale records
    rerun = {(m.id, t) for m, t in jobs}
    doc["attempts"] = [
        a for a in doc["attempts"] if (a["model"], a["trial"]) not in rerun
    ]
    vocab = set(load_words())
    prompt = build_prompt(puzzle.word, load_words())
    print(
        f"{puzzle.date} #{puzzle.index} {puzzle.word.upper()} (par {puzzle.par}): "
        f"{len(jobs)} attempts across {len({m.id for m, _ in jobs})} models"
    )
    with httpx.Client() as client, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _run_attempt, puzzle, m, t, mode, prompt, vocab, api_key, client, timeout
            ): (m, t)
            for m, t in jobs
        }
        for future in as_completed(futures):
            attempt = future.result()
            doc["attempts"].append(attempt.model_dump())
            doc["attempts"].sort(key=lambda a: (a["model"], a["trial"]))
            path.write_text(json.dumps(doc, indent=1))
            status = (
                f"err({attempt.error[:60]})"
                if attempt.error
                else f"{'SOLVED +' + str(attempt.over_par) if attempt.valid else 'invalid:' + str(attempt.failure)}"
            )
            cost = f"${attempt.cost:.4f}" if attempt.cost is not None else "$?"
            print(f"  {attempt.model:40s} t{attempt.trial} {status:18s} {cost} {attempt.latency_s or 0:.0f}s")


def cmd_daily(args: argparse.Namespace) -> None:
    date = (
        datetime.date.fromisoformat(args.date) if args.date else current_puzzle_date()
    )
    puzzle = puzzle_for_date(date)
    models = _select_models(args.models)
    run_puzzle(
        puzzle, models, args.trials, "daily", _load_env_key(), args.workers, args.timeout
    )


def cmd_backfill(args: argparse.Namespace) -> None:
    schedule = load_schedule()
    today_index = puzzle_for_date(current_puzzle_date()).index
    indices = stratified_sample(schedule, args.sample, args.seed, today_index)
    models = _select_models(args.models)
    key = _load_env_key()
    print(
        f"backfilling {len(indices)} sampled days (seed {args.seed}), "
        f"{args.day_workers} days at a time"
    )
    # Days are independent (one result file each), so run them concurrently:
    # total in-flight requests = day_workers x workers.
    with ThreadPoolExecutor(max_workers=args.day_workers) as days:
        futures = [
            days.submit(
                run_puzzle,
                schedule[i],
                models,
                args.trials,
                "backfill",
                key,
                args.workers,
                args.timeout,
            )
            for i in indices
        ]
        for future in as_completed(futures):
            future.result()


def cmd_aggregate(_: argparse.Namespace) -> None:
    docs = [json.loads(p.read_text()) for p in sorted(DAILY_DIR.glob("*.json"))]
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "leaderboard.json").write_text(json.dumps(aggregate(docs), indent=1))
    (RESULTS_DIR / "index.json").write_text(
        json.dumps(
            {
                "days": [
                    {
                        "date": d["date"],
                        "index": d["index"],
                        "word": d["word"],
                        "par": d["par"],
                        "file": f"daily/{d['date']}.json",
                    }
                    for d in docs
                ]
            },
            indent=1,
        )
    )
    print(f"aggregated {len(docs)} days -> results/leaderboard.json")


def cmd_verify_data(_: argparse.Namespace) -> None:
    words = load_words()
    if bfs_distances(set(words)) != words:
        sys.exit("BFS distances disagree with packaged pars")
    anchor = puzzle_for_date(datetime.date(2026, 8, 23))
    if (anchor.index, anchor.word, anchor.par) != (374, "girl", 5):
        sys.exit("schedule anchor mismatch")
    for p in load_schedule():
        if words.get(p.word) != p.par:
            sys.exit(f"schedule par mismatch at index {p.index}")
    print("data OK: 2398 words, BFS pars verified, anchor #374=GIRL")


def _select_models(spec: str | None) -> list[Model]:
    if not spec:
        return enabled_models()
    return [model_by_id(model_id.strip()) for model_id in spec.split(",")]


def main() -> None:
    parser = argparse.ArgumentParser(prog="poople-bench")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("daily", help="run the daily puzzle")
    daily.add_argument("--date", help="puzzle date YYYY-MM-DD (default: today's puzzle)")
    daily.add_argument("--trials", type=int, default=3)
    daily.add_argument("--models", help="comma-separated model ids (default: enabled roster)")
    daily.add_argument("--workers", type=int, default=8)
    daily.add_argument("--timeout", type=float, default=600.0)
    daily.set_defaults(func=cmd_daily)

    backfill = sub.add_parser("backfill", help="run a stratified sample of past days")
    backfill.add_argument("--sample", type=int, default=50)
    backfill.add_argument("--seed", type=int, default=42)
    backfill.add_argument("--trials", type=int, default=1)
    backfill.add_argument("--models", help="comma-separated model ids")
    backfill.add_argument("--day-workers", type=int, default=8, help="days run concurrently")
    backfill.add_argument("--workers", type=int, default=6, help="parallel attempts within a day")
    backfill.add_argument("--timeout", type=float, default=600.0)
    backfill.set_defaults(func=cmd_backfill)

    agg = sub.add_parser("aggregate", help="rebuild leaderboard.json + index.json")
    agg.set_defaults(func=cmd_aggregate)

    verify = sub.add_parser("verify-data", help="re-verify packaged game data")
    verify.set_defaults(func=cmd_verify_data)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
