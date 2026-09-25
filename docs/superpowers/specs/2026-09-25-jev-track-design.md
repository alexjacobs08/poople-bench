# Jev track

**Status:** approved 2026-09-25. Replaces an earlier, never-shipped design (one
100-way Choice per turn) that scored 0; see `research/JEV.md` for why.

## Why a separate track

Jev (TypeSafe, "System One") answers typed questions with a probability
distribution. It does not generate text, so it cannot emit a ladder and never
appears on the one-shot leaderboard. It can play one rung at a time.

## The rule that shapes everything

Code may do **mechanics**: spell strings out, remember answers, apply a move,
refuse to reuse a word. Code may not make a **decision** for the model: it never
looks a word up to decide legality, never counts letters for the model, and
never searches. The dictionary is used only where the game itself uses it
(Poople rejects a non-word; scoring).

## One turn

1. **Legality.** One Noul per one-letter change to the current word: "Is X an
   entry in `accepted_word_list`?" The goal is never mentioned; putting it in
   made Jev write POOP's letters into non-words (`popp`, `pooe`).
2. **Legality, one step further.** The same question for the changes to every
   word Jev approved.
3. **Closest.** One request, one Choice per approved move: which of its
   approved follow-up words looks most like `target_word`.
4. **Choose.** One Choice over the approved moves (`p3=m`), each described in
   words: the word it makes and the follow-up Jev picked in step 3. No numbers.

A move Poople rejects costs a strike; that option is dropped and the turn is
re-asked. Runs stop at POOP, 10 strikes, 3 x par turns, or no approved moves.

This shape follows TypeSafe's Doom demo: code reshapes the world into something
a snap judgment can act on, and asks several small questions per tick.

## Scoring

- `strict`: par / steps, 0 for any run with a strike. Headline; same rule as
  the main board.
- `assisted`: par / steps, strikes forgiven.
- Per-judgment accuracy: legality error rate, similarity accuracy, right call
  on contested turns (the move was on a shortest path when the pick mattered).

**Reference rows** play exactly the same puzzles with the true word list and no
model: random, and letter matching looking one or two moves ahead (20 seeded
games per puzzle). Jev's number is read against them.

## Ablation

`--no-word-list` makes legality rely on Jev's own vocabulary. It fails in an
understandable way: Jev approves real words Poople omits (`poos`, `pogs`).

## Interfaces

- `scaffold.py`: `play()` game loop, `edits()`, `script_play()` baselines.
- `choosers.py`: `JevJudge`, the three request builders.
- `scaffold_score.py`: aggregation plus reference rows.
- CLI: `poople-bench jev [--date D] [--days N]`, `poople-bench jev-aggregate`,
  writing `results/jev/YYYY-MM-DD.json` and `results/jev_leaderboard.json`.
- Cron: runs after the one-shot bench, TypeSafe key only, `continue-on-error`.
