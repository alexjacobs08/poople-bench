# Poople: game mechanics & data (research notes, 2026-08-23)

Poople (https://poople.io — "The Official Daily Word Game") is a daily **word ladder**:
transform the day's 4-letter starting word into **POOP**, changing exactly one letter per
step; every intermediate must be an accepted 4-letter word. Score = number of guesses
(words entered after the start, including POOP). The game's own stat is **"extra guesses"
= guesses − par** (strokes over par). New puzzle daily at **08:00 UTC**. Stats are
device-local only — there is **no global human leaderboard**, so "daily best score" means
the provable optimum (par).

## Everything is client-side and extractable

The entire game ships in one JS bundle (`/assets/index-*.js`). Verified 2026-08-23:

- **Dictionary**: 2,398 accepted 4-letter words, each with its BFS distance to POOP,
  embedded as a `word,dist` list → `data/poople_words.csv`. All 2,398 words are reachable
  from POOP.
- **Daily schedule**: 1,137 entries of `WORD,par`, one per day, embedded in the bundle →
  `data/poople_schedule.csv` (with computed dates). Covers 2025-08-14 (index 0, pre-launch)
  through **2028-09-23** (index 1136).
- **Day index formula** (from bundle fn `Vt`): count how many 1-day steps it takes to get
  from `now` strictly back past `2025-08-15 08:00 UTC`; equivalently, puzzle for index *i*
  is active from 08:00 UTC on (2025-08-14 + *i* days) for 24h. Verified live: computed
  index 374 → GIRL, and poople.io showed "#374: GIRL" on 2026-08-23.
- **Par validation**: independent BFS over the extracted dictionary reproduces all 2,398
  embedded distances and all 1,137 schedule pars with zero mismatches. The harness can
  therefore verify solutions and compute par with no dependence on the site.
- Yesterday's optimal path (and whether it was unique) is shown in-game; uniqueness/count
  of shortest paths is computable from the dictionary.

## Par distribution in the schedule

par 5: 634 days · par 6: 376 · par 7: 66 · par 8: 41 · par 9: 16 · par 10: 3 · par 11: 1

## Misc

- Share format: emoji grid, copyable after solving.
- Contact: admin@poople.io. Solver prior art: nerdymark.com/generators/poople-solver
  (uses the same harvested 2,398-word list).
