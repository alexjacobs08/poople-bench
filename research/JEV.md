# Jev on Poople: what worked, what didn't, and why

Design: `docs/superpowers/specs/2026-09-25-jev-track-design.md`. Every number below
comes from live runs against `jev-1.13.0`, September 2026.

## The model

[Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) is TypeSafe's
"System One" model. It answers typed questions (`choice`, `score`, `noul`) with a
probability distribution, in ~0.3s, at $0.042 per million input tokens (output is free).
Many questions in one request are answered in parallel against one shared `state`.

It gives one snap answer per question, with no intermediate steps. TypeSafe's own
jaggedness page lists generation, counting and multi-hop reasoning as weaknesses. A word
ladder is mostly lookahead, so the question was never "can Jev play" but "what can it
contribute if code is not allowed to play for it".

## Rule adopted

Code may do mechanics (spell strings out, remember answers, apply a move, refuse to reuse
a word). It may not decide for the model: no dictionary lookups to judge legality, no
letter counting for the model, no search. Early attempts broke this rule in both
directions, which is how it was found.

## The road here (same 30 past puzzles unless noted)

| Version | Mean score | What it showed |
|---|---|---|
| One 100-way Choice, bare `p3=o` options, goal in the question (first build) | 0.000 | Jev cannot apply an edit in its head: AUC 0.997 judging "hope", 0.75 judging "replace the y in hype with o". |
| Same, each option spelled out (`"hype" becomes "hope"`) | 0.061 | Spelling fixes legality alone (88% legal mass) but with the goal in the same question Jev writes POOP's letters into non-words: `popp` at 0.56 from `pope`, 0.85 from `pops`. |
| Two asks: legality (no goal), then direction | 0.318 | Separating the judgments removes the non-word chasing. Direction is the weak spot: 45% right on turns that matter. |
| Code does A* search, Jev only judges legality (5 puzzles) | 1.000 | Rejected: that measures Python, not Jev. |
| Composed, code counts letters two moves out and tells Jev the count | 0.781 | Rejected: a two-line script reading the same counts scores 0.741. The model was mostly reading a number. |
| **Composed, Jev judges similarity too (adopted)** | **0.617** | Every judgment is Jev's. Similarity pick correct 87% of the time. Beats the 1-move script (0.508), trails the 2-move script it imitates (0.741). |

Reference on the same puzzles: random 0.002, 1-move letter-match script 0.508, 2-move
0.741.

## Findings worth keeping

- **Judging a finished string is easy; building one is not.** Legality with the word list
  in state: 38,788 calls, 0.03% wrong. Without the list: AUC 0.997, and the "errors" are
  real words Poople omits or censors (`pone`, `tope`, `poos`, `pogs`).
- **One question, one property.** Putting "and toward POOP" into the legality question
  cut first-pick legality from ~100% to 53%.
- **Features beat raw lists.** Showing Jev the full list of reachable words did nothing
  (0.312). Showing it one chosen word per option worked. This is the Doom demo's lesson:
  code turns coordinates into `bearing_deg` before Jev sees them.
- **Direction is where Jev is weak.** Its 13% similarity misses compound over a game: at
  `pope` it picked `oops` as the look-ahead for `pops`, not seeing `pome -> pomp -> poop`.

## Cost

About $0.008 per game, 20-80 requests, dominated by the legality asks that carry the word
list. Earlier spike figures of a fraction of a cent were wrong: that script reused one
legality cache across all puzzles.

## 30-day backtest

Daily puzzles 2026-08-27 to 2026-09-25, 3 games each (90 games), word list readable
for legality. Reference scripts: 20 seeded games per puzzle.

| Player | Strict | Assisted | Solved | At par |
|---|---|---|---|---|
| Script: letter match, 2 moves ahead | 0.748 | 0.748 | 96% | 34% |
| Jev 1.13 | 0.692 | 0.714 | 96% | 24% |
| Script: letter match, 1 move ahead | 0.485 | 0.485 | 71% | 12% |
| Script: random move | 0.000 | 0.000 | 0% | 0% |

Jev: right call on 71% of contested turns, similarity pick correct
87% of the time, 164 wrong legality calls out of 404,207, 3
rejected guesses in 90 games, $0.0081 per game.

Reading: Jev solves as often as the 2-move script but takes longer routes (24% at par vs
34%). It is well clear of the 1-move script, so the look-ahead question adds real signal,
and it has not beaten the script whose judgment it is imitating.
