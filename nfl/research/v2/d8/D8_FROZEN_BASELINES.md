# D8 — FROZEN SIMPLE BASELINES FOR NFL V2

**Diagnostics only.** Nothing in this work is adopted, promoted, or wired into a
projection path. No estimator in `nfl/production/**` or `nfl/product/**` was
changed, read from, or tuned. No sportsbook data, no Fantasy Cruncher, no
floors.

**Why this exists.** We cannot judge whether a future V2 model is better without
a frozen simple baseline to beat. Every V2 model family will have to compete
against these. They are frozen and hashed **now**, before the external research
returns, so that no baseline can be chosen after a candidate's result is known.

**Frozen document:** `nfl/research/baselines/BASELINE_SPECS.json`
`document_sha256 = fb6d5912c39b7505e6deefe8937d7a26205c69cd7a8ac4e735648e88c521f9ee`

---

## 1. What was asked, and what was done

| Asked | Where it is |
|---|---|
| season-to-date average | `B1-SEASON-TO-DATE` |
| recent-N average | `B2-RECENT-N` |
| EWMA | `B3-EWMA` |
| prior-season + current-season shrinkage | `B4-SHRINK` |
| role-average baseline | `B5-ROLE-AVERAGE` |
| league / position prior | `B6-LEAGUE-POSITION-PRIOR` |
| an explicit week-1 definition | `W1-PRIOR-SEASON-SHRUNK`, with `W1-PRIOR-SEASON-MEAN` and `W1-FINAL-GAME` scored beside it as diagnostics |

Quantities covered: QB attempts / completions / passing yards / passing TD /
INT; RB carries / rushing yards; WR-TE targets / receptions / receiving yards /
receiving TD; and team volume as plays, pass attempts, rush attempts and
dropbacks. Fifteen quantities, nine baseline definitions, three evaluation
frames plus a season-opener frame.

### Files

| Path | What |
|---|---|
| `nfl/research/baselines/panel.py` | chronology-guarded play-by-play panel |
| `nfl/research/baselines/estimators.py` | the estimators, pure functions of a pre-cut history |
| `nfl/research/baselines/frame.py` | frames, history index, role ranks, variance components |
| `nfl/research/baselines/specs.py` | spec assembly, hashing, verification |
| `nfl/research/baselines/freeze.py` | writes the freeze; refuses to overwrite one |
| `nfl/research/baselines/evaluate.py` | scores the freeze; refuses an unverified spec |
| `nfl/research/baselines/sensitivity.py` | two diagnostics that change no frozen value |
| `nfl/research/baselines/BASELINE_SPECS.json` | **the freeze** |
| `nfl/research/baselines/D8_BASELINE_RESULTS.json` | all results, all frames |
| `nfl/research/baselines/D8_SENSITIVITY.json` | loss-sensitivity and the week-1 evidence |
| `nfl/tests/test_baselines.py` | 24 test functions, 95 checks |

Reproduce:

```
python3.12 -m nfl.research.baselines.freeze          # refuses; the spec exists
python3.12 -m nfl.research.baselines.evaluate
python3.12 -m nfl.research.baselines.sensitivity
python3.12 nfl/tests/run_suite.py --only test_baselines
```

`run_suite.py --only test_baselines`: **24 test functions, 95 checks, 0 failing,
0 raised, 0 zero-check functions, 0 blocked. SUITE PASS.**

---

## 2. The frozen baselines and their hashes

| baseline | role | spec_sha256 |
|---|---|---|
| `B1-SEASON-TO-DATE` | season-to-date average | `70926a7f70b34a893f61018e4a356a1cfef7d2359ec7c0144b0ad8975c3efaea` |
| `B2-RECENT-N` | recent-N average | `6092c42df798cce06511f96b355675a6e35884014b8a0bfa81e4558f69c1d14d` |
| `B3-EWMA` | EWMA | `a5d992569e5f2b32aba45c4e1eb7838aa24baf2bff838a00e80e57fdc17a9ec6` |
| `B4-SHRINK` | prior-season + current-season shrinkage | `0b13caa107db71cb9e22c6ed2400eb40513a1c365b60f91e75e29b36742534eb` |
| `B5-ROLE-AVERAGE` | role-average baseline | `e4b5b68cd3066c97953a956ed026a75cf6e8243965963017537c6febd68e7f9b` |
| `B6-LEAGUE-POSITION-PRIOR` | league / position prior (the floor) | `67827619f38d04d67ecbf56b850822857e23f37ff082c32853cc5c77dfa14a07` |
| `W1-FINAL-GAME` | week-1 diagnostic comparator: the engine's shape (REJECTED as default) | `e407c88a5de8119011855147acc83ea6e64c041fe45e4ce3beab86ded1aa91d4` |
| `W1-PRIOR-SEASON-MEAN` | week-1 diagnostic: window without shrinkage | `4076f622a42150dfe30817cc0053aaf9e56abb52c11c3258febb80e0dfec6f16` |
| `W1-PRIOR-SEASON-SHRUNK` | FROZEN week-1 / season-opener transition | `0c1d2287d5a4f7760c7417e00b2d5bb9629e258854335a1d2ed017aff6fd4cd9` |

Each `spec_sha256` covers the canonical JSON of that baseline's own definition —
estimator, window, boundary behaviour, fallback chain, frame definition,
constants and how each was obtained — **together with the sha256 of every input
byte**. A spec hash that excluded the data identity would stay stable across a
silent corpus swap, which is exactly the trap the sibling MLB project fell into
when `SIM_FORMULA` excluded `corpus.py` and the fingerprint stayed identical
while the inputs moved. `test_e3` proves ours does not: substituting one blob
hash invalidates every spec hash.

### Data identity

| season | blob | sha256 |
|---|---|---|
| 2021 | `nfl/research/postgame/pbp_2021.e8743a568f99667a.csv.gz` | `e8743a568f99667a8bdcd29ba12224ee1782ad2b7916bee78ee335c099383739` |
| 2022 | `nfl/research/postgame/pbp_2022.0c69a71eb3949895.csv.gz` | `0c69a71eb39498956c7b1d5c1ca52ce7fe679934a95d1af249facb5ea9829ea4` |
| 2023 | `nfl/research/postgame/pbp_2023.4649804ee0f0a40b.csv.gz` | `4649804ee0f0a40b41e51ec75a1ce921949d7fab5459213488656b92f78560e8` |
| 2024 | `nfl/research/postgame/pbp_2024.23370d5d10f8104d.csv.gz` | `23370d5d10f8104d80d46a1fc5e61f4f6f5a3263fe96fe2dd629913cfcb08c06` |
| (position labels only) | `nfl/research/inputs/panel_p3.csv.gz` | `6cb51092175c7a066ceb937e9443762c10f00150d146b8c9264a6ac5b95ab596` |

`panel_p3` supplies **position labels only**. No quantity is taken from it.

---

## 3. Chronology — what is lawful and how the refusal is enforced

Lawful seasons are **2021, 2022, 2023, 2024**. 2025 has no play-by-play blob in
this repository. **2026 is refused**: one week-1 game (DEN@KC) is still unplayed
and the rest are this season's own outcomes.

The refusal is structural, not documentary. `panel.blob_for(season)` raises
`ChronologyRefused` for anything outside the lawful set, and resolves the file
with an **exact-season glob** `pbp_{season}.*.csv.gz`, requiring exactly one
match. A prior agent globbed `pbp_20*` and pulled 2026 into a frame it then
called historical; `test_a2` proves that pattern would still match the two 2026
blobs physically present on disk, and that none of the four lawful patterns
does. The test is therefore not vacuous — the thing it guards against is
present in the directory.

Other frame rules, all declared in the freeze:

- **Grouping is `(game_id, posteam)`, never by game.** Grouping by game alone
  selects the better of the two starting quarterbacks and inflates everything.
  `test_d1` seeds that error on a real game and shows it discards the second
  passer.
- **Kneels excluded** (`qb_kneel != '1'`): 1654 plays across the four
  seasons. `test_d2` recounts them independently from the 2024 blob and requires
  the builder's count to match exactly.
- **Regular season only.** Postseason has a different team population and a
  different week numbering.

### The panel, and an independent check on it

21457 player-game rows and 2174 team-games. The 2,174 team-games match the
count WS07 used for 2021–2024, independently.

`test_d5` cross-validates the whole panel against
`nfl/research/inputs/panel_p3.csv.gz`, built by a different agent from a
different pipeline for a different purpose:

- **targets agree exactly on all 21,457 shared rows** — two independent
  derivations landing on the same integer, which is not an identity that holds
  by construction;
- carries disagree on 920 rows, and **every one of those 920 is a
  quarterback** — that is the kneel exclusion and nothing else.

Team totals differ definitionally and the differences are attributed rather than
waved away: `team_pass_att + sacks` equals `panel_p3`'s `team_pass_att` in 1,942
of 2,174 team-games, and `panel_p3`'s `team_plays` counts roughly 20 more plays
per team-game because it is not restricted to scrimmage pass/rush.

---

## 4. The frames

Getting the frame wrong is the most common way to publish a flattering number,
so three are declared and all three are reported.

| Frame | Definition | Conditions on the outcome? |
|---|---|---|
| **FRAME_A** (primary) | point-in-time eligible: ≥1 opportunity for this team in the team's 3 most recent completed games before the forecast ordinal; at a season opener, the team's last 3 games of the previous season | **No.** Membership is a function of prior games only |
| **FRAME_B** | FRAME_A restricted to rows with ≥1 realised opportunity | **Yes**, once (appearance). Reported in the JSON |
| **FRAME_C** | FRAME_B restricted to the within-team usage **rank-1** subject — the starting QB, the lead back, the top target. Rank is assigned from prior games only | **Yes**, once (appearance) |
| **SEASON_OPENER** | FRAME_A rows where the team has no completed game in the current season | **No** |

A player selected into FRAME_A who then does not play scores an **actual of
zero** and the baseline eats that error. That is the honest accounting: absence
is a forecasting problem, not a sampling inconvenience. Roughly 29–32% of
FRAME_A rows are such zeros, and the rate is reported per quantity in the JSON.

**FRAME_C exists because an r computed over a population containing backups is
mostly measuring starter-versus-backup.** It is not comparable to an r computed
over starters. This matters directly for reading these numbers against the
repository's own `r = 0.136` for prior-form QB passing yards: the frames are not
the same population, and until one is matched to the other the two numbers must
not be subtracted. FRAME_C is the closest available.

**Games are not independent observations.** Every interval here is a block
bootstrap over **game ids** (400 replicates, seed 20260914). The resample is
drawn once per (quantity, frame) and shared across baselines, so the delta
against the league prior is a **paired** comparison.

---

## 5. Point-in-time correctness, and how it was actually tested

### The mechanism

Every estimator takes `hist` — a list of `(ordinal, value)` pairs the caller has
**already cut** at the forecast ordinal — and nothing else that varies with the
forecast game. An estimator cannot peek at the game it is forecasting because
the game is not in its arguments. The cut is one function, `estimators.prior`,
using `bisect_left` on the ordinal, so a row at the same ordinal as the forecast
(the forecast game itself, or a second game a club plays in the same week after
a postponement) lands on the **future** side.

Role ranks, frame membership, the league/position prior table and the
role-average table are all built from strictly prior games or strictly prior
seasons.

### The test, and why it can fail

A leak test that asserts `forecast(week 5) == forecast(week 5)` proves nothing.
So `test_c1` **mutates the future and requires the past not to move**: every
player row and team row at or after ordinal 202310 is multiplied by 7.5 and
shifted by 1000 (7,996 rows touched), the index is rebuilt, and every baseline's
forecast for games *at* the cut must be bit-identical.

Result: **0 of 2,480 forecasts moved.**

That is the easy half. Three further tests make it load-bearing:

| Test | Seeded violation | Result |
|---|---|---|
| `test_c2` | an estimator differing by one character — `bisect_right`, so the forecast game enters its own history | **259 of 355** forecasts moved. The mutation does detect a leak |
| `test_c5` | `estimators.prior` itself replaced via `nfl/tests/bypass.guard_bypassed` with the leaking cut, and `test_c1`'s comparison rerun | **1,036 of 1,420** forecasts moved. With the cut removed the leak test fails, so on the real cut it was measuring something |
| `test_c3` | the forecast game's own rows corrupted | frame membership and rank unchanged |
| `test_c4` | 2023 and 2024 frame rows poisoned | the 2023 prior table is unchanged; the **2024** table does change, proving the poisoning was real and the first check not vacuous |

### Where correctness is asserted rather than proved

- **Position is treated as a static roster attribute**, not a point-in-time one.
  It is taken as each player's modal label across the lawful seasons. 13 of
  1,793 players ever carry more than one label. The defensible part of the claim
  is that a position label cannot be a function of the forecast game's outcome;
  the part that is measured is how little it moves.
- **There is no roster feed here.** A player who changed clubs in the offseason
  is forecast for his prior club and scores zero. This is a real limitation of
  the week-1 frame and its cost is reported rather than assumed away.

---

## 6. The week-1 / season-opener baseline

**Frozen definition — `W1-PRIOR-SEASON-SHRUNK`:** the player's prior-season
per-game mean, carried over by the measured slope `c` and shrunk toward the
position mean with prior weight `k` games. With no prior season it collapses to
the position prior, which is the correct degenerate case for a rookie rather
than a special case.

It is also the declared fallback that `B1-SEASON-TO-DATE` fires at a season
opener. `test_f3` confirms that at every 2023 season-opener row `B1` is
genuinely undefined and the declared week-1 baseline is what actually runs.

**Why this and not "last season's final game".** The choice was made on a stated
principle before any evaluation-window score existed: *a mean over a player's
whole prior season has strictly smaller sampling variance than any single game
drawn from it, for the same estimand.* That is a property of the estimator, not
of the outcomes.

The rejected alternative is the shape the engine already carries.
`previous_primary_detail(2026, 1)['KC']` resolves to **2025 week 18**, and the
charted QB1 equals the prior-season final-game primary in only **59 of 160**
week-1 rooms (**0.3688**). `test_f4` asserts that wiring still exists, so this
citation cannot go stale silently. A week-1 baseline built on the final game
inherits that pathology; ours does not use it.

**Supporting evidence, measured on the estimation window only (2021 → 2022), so
that it could not have chosen the estimator:**

| quantity | n players | r(prior-season FINAL GAME, next-season mean) | r(prior-season MEAN, next-season mean) |
|---|--:|--:|--:|
| pass_att | 33 | 0.4858 | 0.7459 |
| pass_cmp | 33 | 0.5079 | 0.7815 |
| pass_yds | 33 | 0.4663 | 0.7090 |
| pass_td | 33 | 0.3336 | 0.6049 |
| pass_int | 33 | 0.0923 | 0.0170 |
| carries | 69 | 0.6059 | 0.8476 |
| rush_yds | 69 | 0.5223 | 0.8003 |
| targets | 169 | 0.4535 | 0.7793 |
| receptions | 169 | 0.4351 | 0.7799 |
| rec_yds | 169 | 0.3967 | 0.7971 |
| rec_td | 169 | 0.1250 | 0.5461 |

The prior-season mean dominates the final game on every quantity except
interceptions, where both are indistinguishable from zero.

**And the comparator, scored only after the freeze:**

| quantity | n | games | baseline | MAE | dMAE vs league prior | 95% CI (game-clustered) | r | 95% CI (game-clustered) | SD ratio | calib slope |
|---|--:|--:|---|--:|--:|---|--:|---|--:|--:|
| pass_att | 115 | 32 | W1-PRIOR-SEASON-SHRUNK | 15.80 | -1.66 | [-2.87, -0.62] | 0.4559 | [0.3433, 0.5568] | 0.4451 | 1.024 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 15.68 | -1.75 | [-3.56, -0.10] | 0.4559 | [0.3432, 0.5568] | 0.7081 | 0.644 |
|  |  |  | W1-FINAL-GAME | 16.50 | -0.95 | [-2.48, 0.51] | 0.2894 | [0.1594, 0.4220] | 0.7496 | 0.386 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 17.47 | 0.00 | [0.00, 0.00] | 0.0773 | [-0.0986, 0.2531] | 0.0006 | 140.297 |
| pass_cmp | 115 | 32 | W1-PRIOR-SEASON-SHRUNK | 10.13 | -1.23 | [-2.09, -0.48] | 0.4951 | [0.3837, 0.5946] | 0.4682 | 1.057 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 10.09 | -1.26 | [-2.49, -0.21] | 0.4951 | [0.3837, 0.5945] | 0.7050 | 0.702 |
|  |  |  | W1-FINAL-GAME | 10.52 | -0.83 | [-1.73, 0.01] | 0.3528 | [0.2068, 0.4896] | 0.7564 | 0.467 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 11.36 | 0.00 | [0.00, 0.00] | 0.0734 | [-0.1069, 0.2346] | 0.0004 | 173.154 |
| pass_yds | 115 | 32 | W1-PRIOR-SEASON-SHRUNK | 110.98 | -12.43 | [-23.15, -2.81] | 0.5284 | [0.3976, 0.6335] | 0.4434 | 1.192 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 109.83 | -13.36 | [-29.42, 1.35] | 0.5284 | [0.3975, 0.6335] | 0.7543 | 0.701 |
|  |  |  | W1-FINAL-GAME | 112.47 | -10.97 | [-23.85, 2.39] | 0.4162 | [0.2371, 0.5697] | 0.8669 | 0.480 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 123.67 | 0.00 | [0.00, 0.00] | 0.0210 | [-0.1522, 0.1936] | 0.0013 | 16.556 |
| pass_td | 115 | 32 | W1-PRIOR-SEASON-SHRUNK | 0.76 | -0.06 | [-0.12, 0.00] | 0.4065 | [0.2444, 0.5549] | 0.4205 | 0.967 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 0.74 | -0.08 | [-0.19, 0.05] | 0.4060 | [0.2425, 0.5542] | 0.7734 | 0.525 |
|  |  |  | W1-FINAL-GAME | 0.82 | -0.00 | [-0.15, 0.14] | 0.3083 | [0.1084, 0.4910] | 1.2536 | 0.246 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.82 | 0.00 | [0.00, 0.00] | 0.0366 | [-0.1388, 0.2182] | 0.0076 | 4.783 |
| pass_int | 115 | 32 | W1-PRIOR-SEASON-SHRUNK | 0.55 | 0.01 | [0.00, 0.02] | 0.0555 | [-0.0436, 0.1666] | 0.0864 | 0.642 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 0.63 | 0.08 | [0.01, 0.16] | 0.0558 | [-0.0433, 0.1668] | 0.7712 | 0.072 |
|  |  |  | W1-FINAL-GAME | 0.83 | 0.28 | [0.15, 0.41] | -0.0382 | [-0.1776, 0.1378] | 1.5641 | -0.024 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.54 | 0.00 | [0.00, 0.00] | -0.0662 | [-0.2315, 0.1018] | 0.0005 | -146.126 |
| carries | 221 | 32 | W1-PRIOR-SEASON-SHRUNK | 5.00 | -1.03 | [-1.44, -0.58] | 0.5022 | [0.3902, 0.6055] | 0.6854 | 0.733 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 4.96 | -1.07 | [-1.56, -0.58] | 0.5023 | [0.3905, 0.6055] | 0.8340 | 0.602 |
|  |  |  | W1-FINAL-GAME | 5.67 | -0.36 | [-0.94, 0.15] | 0.4690 | [0.3831, 0.5658] | 1.1420 | 0.411 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 6.02 | 0.00 | [0.00, 0.00] | -0.0116 | [-0.1337, 0.1081] | 0.0085 | -1.371 |
| rush_yds | 221 | 32 | W1-PRIOR-SEASON-SHRUNK | 22.38 | -2.78 | [-4.66, -0.96] | 0.4834 | [0.3795, 0.5958] | 0.7331 | 0.659 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 22.61 | -2.56 | [-4.85, -0.42] | 0.4834 | [0.3795, 0.5957] | 0.8910 | 0.542 |
|  |  |  | W1-FINAL-GAME | 27.20 | 1.95 | [-0.87, 4.58] | 0.3663 | [0.2706, 0.4774] | 1.3144 | 0.279 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 25.14 | 0.00 | [0.00, 0.00] | -0.0140 | [-0.1441, 0.1055] | 0.0014 | -10.116 |
| targets | 497 | 32 | W1-PRIOR-SEASON-SHRUNK | 2.57 | -0.31 | [-0.49, -0.15] | 0.5972 | [0.5288, 0.6671] | 0.6321 | 0.945 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 2.59 | -0.29 | [-0.49, -0.10] | 0.5990 | [0.5318, 0.6695] | 0.7664 | 0.781 |
|  |  |  | W1-FINAL-GAME | 2.85 | -0.04 | [-0.29, 0.23] | 0.3976 | [0.2916, 0.5149] | 0.9146 | 0.435 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 2.88 | 0.00 | [0.00, 0.00] | 0.1320 | [0.0772, 0.1796] | 0.1815 | 0.727 |
| receptions | 497 | 32 | W1-PRIOR-SEASON-SHRUNK | 1.71 | -0.24 | [-0.33, -0.15] | 0.6046 | [0.5396, 0.6714] | 0.6244 | 0.968 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 1.72 | -0.24 | [-0.35, -0.12] | 0.6041 | [0.5377, 0.6719] | 0.7662 | 0.788 |
|  |  |  | W1-FINAL-GAME | 1.93 | -0.03 | [-0.19, 0.14] | 0.3616 | [0.2692, 0.4561] | 0.9838 | 0.368 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 1.95 | 0.00 | [0.00, 0.00] | 0.1182 | [0.0680, 0.1669] | 0.1349 | 0.876 |
| rec_yds | 497 | 32 | W1-PRIOR-SEASON-SHRUNK | 22.00 | -2.51 | [-3.78, -1.43] | 0.5774 | [0.4945, 0.6541] | 0.6200 | 0.931 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 22.15 | -2.36 | [-4.00, -0.97] | 0.5772 | [0.4931, 0.6549] | 0.7583 | 0.761 |
|  |  |  | W1-FINAL-GAME | 25.66 | 1.12 | [-1.31, 3.99] | 0.3048 | [0.2226, 0.3768] | 1.1459 | 0.266 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 24.52 | 0.00 | [0.00, 0.00] | 0.1635 | [0.1096, 0.2055] | 0.1814 | 0.901 |
| rec_td | 497 | 32 | W1-PRIOR-SEASON-SHRUNK | 0.22 | 0.00 | [-0.00, 0.01] | 0.1989 | [0.1068, 0.2816] | 0.2810 | 0.708 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 0.23 | 0.01 | [-0.01, 0.02] | 0.1948 | [0.1038, 0.2821] | 0.5470 | 0.356 |
|  |  |  | W1-FINAL-GAME | 0.24 | 0.02 | [-0.01, 0.05] | 0.0488 | [-0.0422, 0.1489] | 1.3855 | 0.035 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.22 | 0.00 | [0.00, 0.00] | 0.0695 | [-0.0039, 0.1321] | 0.0593 | 1.171 |
| team_plays | 64 | 32 | W1-PRIOR-SEASON-SHRUNK | 7.15 | 0.03 | [-0.11, 0.18] | -0.0610 | [-0.2788, 0.1414] | 0.0931 | -0.655 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 7.62 | 0.50 | [0.08, 0.96] | -0.0633 | [-0.2836, 0.1394] | 0.3268 | -0.194 |
|  |  |  | W1-FINAL-GAME | 10.45 | 3.31 | [2.21, 4.55] | -0.1959 | [-0.3689, 0.0195] | 0.8599 | -0.228 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 7.12 | 0.00 | [0.00, 0.00] | 0.1912 | [0.0307, 0.3418] | 0.0016 | 118.115 |
| team_pass_att | 64 | 32 | W1-PRIOR-SEASON-SHRUNK | 6.71 | 0.46 | [-0.03, 0.98] | 0.0127 | [-0.2380, 0.2111] | 0.3552 | 0.036 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 6.97 | 0.73 | [0.03, 1.46] | 0.0119 | [-0.2387, 0.2102] | 0.5040 | 0.024 |
|  |  |  | W1-FINAL-GAME | 8.59 | 2.31 | [1.11, 3.54] | -0.0489 | [-0.2753, 0.1811] | 0.9335 | -0.052 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 6.27 | 0.00 | [0.00, 0.00] | 0.2077 | [-0.0057, 0.4095] | 0.0046 | 45.378 |
| team_rush_att | 64 | 32 | W1-PRIOR-SEASON-SHRUNK | 5.20 | -0.20 | [-0.56, 0.12] | 0.1880 | [-0.0299, 0.3835] | 0.2193 | 0.858 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 5.25 | -0.13 | [-0.81, 0.45] | 0.1882 | [-0.0303, 0.3841] | 0.4317 | 0.436 |
|  |  |  | W1-FINAL-GAME | 8.61 | 3.18 | [1.95, 4.41] | -0.2098 | [-0.4149, 0.0123] | 1.0110 | -0.207 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 5.42 | 0.00 | [0.00, 0.00] | -0.0070 | [-0.1536, 0.1404] | 0.0032 | -2.177 |
| team_dropbacks | 64 | 32 | W1-PRIOR-SEASON-SHRUNK | 7.16 | 0.30 | [-0.08, 0.65] | -0.0010 | [-0.2455, 0.1911] | 0.2117 | -0.005 |
|  |  |  | W1-PRIOR-SEASON-MEAN | 7.64 | 0.79 | [0.11, 1.47] | 0.0011 | [-0.2428, 0.1931] | 0.4313 | 0.003 |
|  |  |  | W1-FINAL-GAME | 9.61 | 2.72 | [1.50, 3.88] | -0.0407 | [-0.2438, 0.1757] | 0.8712 | -0.047 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 6.88 | 0.00 | [0.00, 0.00] | -0.1806 | [-0.3685, 0.0375] | 0.0047 | -38.530 |

Read with care. The opener frame carries **32 game clusters** (16 games × 2
seasons), so precision beyond two significant figures is not supported and none
should be quoted. Within that limit:

- `W1-FINAL-GAME` is worse than `W1-PRIOR-SEASON-SHRUNK` on **every** quantity.
- On team volume it is worse than the **league prior** by +2.3 to +3.3 plays of
  MAE with intervals excluding zero — that is, at a season opener, last
  season's final game is actively harmful information about team volume.
- Its SD ratios exceed 1.0 on several quantities (1.14 carries, 1.31 rush yards,
  1.56 interceptions): a single game is noisier than the thing it predicts.

This is a post-freeze confirmation of a pre-freeze choice. It is **not** the
reason for the choice, and it must not be cited as though it were.

---

## 7. The derived and fitted constants

Two classes, labelled separately in the freeze because they audit differently.

- **`k` — DERIVED_FROM_PRINCIPLE.** The normal-normal posterior weight
  `sigma_w^2 / sigma_b^2`. Both variances are measured on seasons 2021–2022;
  `sigma_b^2` has the sampling component `sigma_w^2 / n` removed so that k does
  not collapse merely because short seasons are noisy. This is a derivation,
  not a search over scores.
- **`c`, `N`, `H` — FITTED_PRIOR_WINDOW.** The season carry-over slope, the
  recent-window length and the EWMA half-life **are** selected — on seasons
  2021–2022 only, strictly before the 2023–2024 evaluation window. `test_e4`
  asserts the two windows do not overlap and that every window's declared
  selection season is prior to every evaluation season.

| quantity | positions | k (derived) | c (fitted) | c n_pairs | N (fitted) | EWMA half-life (fitted) |
|---|---|--:|--:|--:|--:|--:|
| pass_att | QB | 1.125 | 0.6285 | 42 | 1 | 0.5 |
| pass_cmp | QB | 1.113 | 0.6641 | 42 | 1 | 0.5 |
| pass_yds | QB | 1.251 | 0.5879 | 42 | 10 | 4.0 |
| pass_td | QB | 2.940 | 0.5438 | 42 | 16 | 4.0 |
| pass_int | QB | 17.884 | 0.1121 | 42 | 8 | 12.0 |
| carries | RB | 0.725 | 0.8217 | 89 | 2 | 1.0 |
| rush_yds | RB | 1.189 | 0.8228 | 89 | 3 | 2.0 |
| targets | WR,TE | 0.916 | 0.8125 | 199 | 6 | 2.0 |
| receptions | WR,TE | 1.208 | 0.8090 | 199 | 6 | 3.0 |
| rec_yds | WR,TE | 1.654 | 0.8046 | 199 | 16 | 3.0 |
| rec_td | WR,TE | 12.225 | 0.5054 | 199 | 1 | 0.5 |
| team_plays | TEAM | 14.390 | 0.2848 | 32 | 16 | 12.0 |
| team_pass_att | TEAM | 4.342 | 0.7049 | 32 | 16 | 6.0 |
| team_rush_att | TEAM | 9.361 | 0.5076 | 32 | 16 | 8.0 |
| team_dropbacks | TEAM | 5.971 | 0.4901 | 32 | 16 | 6.0 |

`k` behaves the way it should without being told to: near 1 for volume
quantities, where player heterogeneity dominates, and 12–18 for interceptions
and receiving touchdowns, where almost everything is noise and the estimator is
pulled hard to the position mean.

### A caveat on N and H that a reader must have

The windows were frozen by **MAE**. MAE is minimised by a conditional **median**,
and roughly 30% of FRAME_A rows are structural zeros, so short windows are
favoured for a reason that has nothing to do with football. `D8_SENSITIVITY.json`
records what RMSE would have chosen instead:

| quantity | frozen by MAE (N, H) | RMSE would have chosen (N, H) | agree |
|---|---|---|---|
| pass_att | (1, 0.5) | (16, 1.0) | NO |
| pass_cmp | (1, 0.5) | (16, 1.0) | NO |
| pass_yds | (10, 4.0) | (10, 2.0) | NO |
| pass_td | (16, 4.0) | (16, 6.0) | NO |
| pass_int | (8, 12.0) | (16, 12.0) | NO |
| carries | (2, 1.0) | (3, 1.0) | NO |
| rush_yds | (3, 2.0) | (10, 3.0) | NO |
| targets | (6, 2.0) | (10, 3.0) | NO |
| receptions | (6, 3.0) | (16, 4.0) | NO |
| rec_yds | (16, 3.0) | (16, 6.0) | NO |
| rec_td | (1, 0.5) | (16, 12.0) | NO |
| team_plays | (16, 12.0) | (16, 12.0) | yes |
| team_pass_att | (16, 6.0) | (16, 6.0) | yes |
| team_rush_att | (16, 8.0) | (10, 8.0) | NO |
| team_dropbacks | (16, 6.0) | (16, 6.0) | yes |

The team quantities are stable; the player quantities are **not**, and for
`pass_att`, `pass_cmp` and `rec_td` the disagreement is extreme (N = 1 under MAE
against N = 16 under RMSE). **The frozen choice stands** — re-freezing after
seeing this would destroy the property the freeze exists to provide — but any
future comparison against `B2` or `B3` should be read knowing the window is
loss-dependent, and a candidate that beats `B2` on RMSE has beaten a baseline
tuned for a different loss.

---

## 8. Historical performance, 2023–2024

544 games, 1,088 team-games. Constants from 2021–2022; history for any forecast
is every strictly prior lawful game.

### Summary

| quantity | frame A: baselines strictly better than the league prior | best baseline (frame A) | its dMAE [95% CI] | its r | frame C (primary role): count better | season opener: count better |
|---|--:|---|---|--:|--:|--:|
| pass_att | 5 of 5 | B5-ROLE-AVERAGE | -4.659 [-5.133, -4.223] | 0.5779 | 5 of 5 | 2 of 3 |
| pass_cmp | 5 of 5 | B5-ROLE-AVERAGE | -2.980 [-3.286, -2.702] | 0.5798 | 5 of 5 | 2 of 3 |
| pass_yds | 5 of 5 | B5-ROLE-AVERAGE | -31.789 [-35.094, -28.377] | 0.5701 | 5 of 5 | 1 of 3 |
| pass_td | 5 of 5 | B5-ROLE-AVERAGE | -0.149 [-0.169, -0.128] | 0.4268 | 4 of 5 | 0 of 3 |
| pass_int | 1 of 5 | B5-ROLE-AVERAGE | -0.058 [-0.066, -0.050] | 0.2586 | 0 of 5 | 0 of 3 |
| carries | 5 of 5 | B3-EWMA | -1.803 [-1.942, -1.662] | 0.6695 | 5 of 5 | 2 of 3 |
| rush_yds | 5 of 5 | B5-ROLE-AVERAGE | -6.438 [-6.997, -5.883] | 0.5457 | 5 of 5 | 2 of 3 |
| targets | 5 of 5 | B5-ROLE-AVERAGE | -0.723 [-0.762, -0.683] | 0.6090 | 5 of 5 | 2 of 3 |
| receptions | 5 of 5 | B5-ROLE-AVERAGE | -0.440 [-0.467, -0.416] | 0.5680 | 5 of 5 | 2 of 3 |
| rec_yds | 5 of 5 | B5-ROLE-AVERAGE | -5.230 [-5.545, -4.915] | 0.5390 | 5 of 5 | 2 of 3 |
| rec_td | 2 of 5 | B5-ROLE-AVERAGE | -0.016 [-0.018, -0.015] | 0.2659 | 0 of 5 | 0 of 3 |
| team_plays | 0 of 5 | B4-SHRINK | -0.032 [-0.096, 0.040] | 0.0704 | 0 of 5 | 0 of 3 |
| team_pass_att | 0 of 5 | B4-SHRINK | -0.008 [-0.142, 0.147] | 0.1931 | 0 of 5 | 0 of 3 |
| team_rush_att | 2 of 5 | B4-SHRINK | -0.216 [-0.328, -0.100] | 0.2507 | 3 of 5 | 0 of 3 |
| team_dropbacks | 0 of 5 | B4-SHRINK | -0.054 [-0.172, 0.072] | 0.1833 | 0 of 5 | 0 of 3 |

### FRAME_A — point-in-time frame (primary)

| quantity | n | games | baseline | MAE | dMAE vs league prior | 95% CI (game-clustered) | r | 95% CI (game-clustered) | SD ratio | calib slope |
|---|--:|--:|---|--:|--:|---|--:|---|--:|--:|
| pass_att | 1677 | 544 | B1-SEASON-TO-DATE | 10.883 | -4.132 | [-4.663, -3.537] | 0.5581 | [0.5188, 0.5949] | 0.7103 | 0.786 |
|  |  |  | B2-RECENT-N | 10.879 | -4.132 | [-4.666, -3.561] | 0.5861 | [0.5498, 0.6156] | 0.8335 | 0.703 |
|  |  |  | B3-EWMA | 10.848 | -4.160 | [-4.653, -3.653] | 0.5956 | [0.5613, 0.6231] | 0.7481 | 0.796 |
|  |  |  | B4-SHRINK | 11.524 | -3.494 | [-3.935, -3.009] | 0.5557 | [0.5145, 0.5925] | 0.5509 | 1.009 |
|  |  |  | B5-ROLE-AVERAGE | 10.357 | -4.659 | [-5.133, -4.223] | 0.5779 | [0.5331, 0.6214] | 0.6065 | 0.953 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 15.028 | 0.000 | [0.000, 0.000] | 0.0269 | [-0.0143, 0.0666] | 0.0005 | 50.504 |
| pass_cmp | 1677 | 544 | B1-SEASON-TO-DATE | 7.170 | -2.784 | [-3.123, -2.384] | 0.5793 | [0.5411, 0.6139] | 0.7141 | 0.811 |
|  |  |  | B2-RECENT-N | 7.193 | -2.754 | [-3.112, -2.394] | 0.6029 | [0.5706, 0.6326] | 0.8439 | 0.715 |
|  |  |  | B3-EWMA | 7.167 | -2.781 | [-3.109, -2.414] | 0.6141 | [0.5814, 0.6408] | 0.7591 | 0.809 |
|  |  |  | B4-SHRINK | 7.619 | -2.336 | [-2.607, -2.012] | 0.5771 | [0.5389, 0.6121] | 0.5657 | 1.020 |
|  |  |  | B5-ROLE-AVERAGE | 6.975 | -2.980 | [-3.286, -2.702] | 0.5798 | [0.5383, 0.6201] | 0.5973 | 0.971 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 9.963 | 0.000 | [0.000, 0.000] | 0.0193 | [-0.0234, 0.0618] | 0.0004 | 47.696 |
| pass_yds | 1677 | 544 | B1-SEASON-TO-DATE | 81.177 | -30.545 | [-34.518, -25.791] | 0.5824 | [0.5444, 0.6168] | 0.7103 | 0.820 |
|  |  |  | B2-RECENT-N | 88.935 | -22.812 | [-26.305, -19.300] | 0.5487 | [0.5165, 0.5790] | 0.5971 | 0.919 |
|  |  |  | B3-EWMA | 86.968 | -24.776 | [-28.377, -21.130] | 0.5742 | [0.5404, 0.6031] | 0.5976 | 0.961 |
|  |  |  | B4-SHRINK | 86.685 | -25.039 | [-28.384, -21.416] | 0.5801 | [0.5430, 0.6118] | 0.5522 | 1.051 |
|  |  |  | B5-ROLE-AVERAGE | 79.947 | -31.789 | [-35.094, -28.377] | 0.5701 | [0.5273, 0.6097] | 0.5872 | 0.971 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 111.871 | 0.000 | [0.000, 0.000] | 0.0156 | [-0.0287, 0.0627] | 0.0011 | 13.633 |
| pass_td | 1677 | 544 | B1-SEASON-TO-DATE | 0.768 | -0.140 | [-0.171, -0.107] | 0.4248 | [0.3847, 0.4608] | 0.6314 | 0.673 |
|  |  |  | B2-RECENT-N | 0.821 | -0.087 | [-0.114, -0.062] | 0.4190 | [0.3786, 0.4532] | 0.5316 | 0.788 |
|  |  |  | B3-EWMA | 0.795 | -0.114 | [-0.142, -0.085] | 0.4529 | [0.4150, 0.4853] | 0.5620 | 0.806 |
|  |  |  | B4-SHRINK | 0.821 | -0.088 | [-0.109, -0.067] | 0.4402 | [0.4007, 0.4752] | 0.4225 | 1.042 |
|  |  |  | B5-ROLE-AVERAGE | 0.759 | -0.149 | [-0.169, -0.128] | 0.4268 | [0.3889, 0.4555] | 0.4404 | 0.969 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.909 | 0.000 | [0.000, 0.000] | -0.0222 | [-0.0675, 0.0242] | 0.0058 | -3.848 |
| pass_int | 1677 | 544 | B1-SEASON-TO-DATE | 0.627 | 0.005 | [-0.013, 0.026] | 0.1157 | [0.0750, 0.1573] | 0.6060 | 0.191 |
|  |  |  | B2-RECENT-N | 0.659 | 0.036 | [0.018, 0.054] | 0.0534 | [0.0144, 0.0936] | 0.4809 | 0.111 |
|  |  |  | B3-EWMA | 0.659 | 0.036 | [0.021, 0.051] | 0.0571 | [0.0198, 0.0994] | 0.3932 | 0.145 |
|  |  |  | B4-SHRINK | 0.628 | 0.006 | [0.001, 0.010] | 0.0993 | [0.0602, 0.1410] | 0.1191 | 0.834 |
|  |  |  | B5-ROLE-AVERAGE | 0.565 | -0.058 | [-0.066, -0.050] | 0.2586 | [0.2163, 0.2991] | 0.2676 | 0.966 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.623 | 0.000 | [0.000, 0.000] | -0.0360 | [-0.0806, 0.0056] | 0.0003 | -107.529 |
| carries | 3509 | 544 | B1-SEASON-TO-DATE | 4.132 | -1.726 | [-1.868, -1.584] | 0.6472 | [0.6211, 0.6696] | 0.7916 | 0.818 |
|  |  |  | B2-RECENT-N | 4.207 | -1.653 | [-1.794, -1.495] | 0.6468 | [0.6222, 0.6682] | 0.8680 | 0.745 |
|  |  |  | B3-EWMA | 4.055 | -1.803 | [-1.942, -1.662] | 0.6695 | [0.6467, 0.6915] | 0.8275 | 0.809 |
|  |  |  | B4-SHRINK | 4.171 | -1.689 | [-1.825, -1.552] | 0.6520 | [0.6258, 0.6742] | 0.7316 | 0.891 |
|  |  |  | B5-ROLE-AVERAGE | 4.056 | -1.803 | [-1.923, -1.693] | 0.6305 | [0.6052, 0.6533] | 0.6156 | 1.024 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 5.866 | 0.000 | [0.000, 0.000] | 0.0129 | [-0.0072, 0.0335] | 0.0076 | 1.702 |
| rush_yds | 3509 | 544 | B1-SEASON-TO-DATE | 20.908 | -6.159 | [-6.925, -5.444] | 0.5764 | [0.5457, 0.6061] | 0.7628 | 0.756 |
|  |  |  | B2-RECENT-N | 21.571 | -5.494 | [-6.179, -4.739] | 0.5624 | [0.5315, 0.5912] | 0.8211 | 0.685 |
|  |  |  | B3-EWMA | 21.066 | -6.004 | [-6.688, -5.288] | 0.5863 | [0.5577, 0.6131] | 0.7550 | 0.776 |
|  |  |  | B4-SHRINK | 21.212 | -5.857 | [-6.492, -5.170] | 0.5882 | [0.5605, 0.6147] | 0.6688 | 0.879 |
|  |  |  | B5-ROLE-AVERAGE | 20.630 | -6.438 | [-6.997, -5.883] | 0.5457 | [0.5182, 0.5706] | 0.5376 | 1.015 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 27.095 | 0.000 | [0.000, 0.000] | 0.0291 | [0.0049, 0.0540] | 0.0011 | 26.773 |
| targets | 8227 | 544 | B1-SEASON-TO-DATE | 2.160 | -0.597 | [-0.646, -0.547] | 0.6180 | [0.6008, 0.6355] | 0.7273 | 0.850 |
|  |  |  | B2-RECENT-N | 2.196 | -0.560 | [-0.606, -0.512] | 0.6237 | [0.6058, 0.6393] | 0.7252 | 0.860 |
|  |  |  | B3-EWMA | 2.159 | -0.598 | [-0.643, -0.550] | 0.6391 | [0.6229, 0.6554] | 0.7232 | 0.884 |
|  |  |  | B4-SHRINK | 2.182 | -0.575 | [-0.618, -0.529] | 0.6290 | [0.6113, 0.6459] | 0.6624 | 0.950 |
|  |  |  | B5-ROLE-AVERAGE | 2.036 | -0.723 | [-0.762, -0.683] | 0.6090 | [0.5918, 0.6253] | 0.5962 | 1.021 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 2.759 | 0.000 | [0.000, 0.000] | 0.1542 | [0.1386, 0.1694] | 0.1628 | 0.947 |
| receptions | 8227 | 544 | B1-SEASON-TO-DATE | 1.569 | -0.371 | [-0.401, -0.338] | 0.5830 | [0.5608, 0.6008] | 0.7160 | 0.814 |
|  |  |  | B2-RECENT-N | 1.589 | -0.350 | [-0.382, -0.316] | 0.5888 | [0.5682, 0.6067] | 0.7110 | 0.828 |
|  |  |  | B3-EWMA | 1.570 | -0.369 | [-0.402, -0.335] | 0.6053 | [0.5867, 0.6224] | 0.6862 | 0.882 |
|  |  |  | B4-SHRINK | 1.584 | -0.355 | [-0.382, -0.321] | 0.5994 | [0.5792, 0.6158] | 0.6320 | 0.948 |
|  |  |  | B5-ROLE-AVERAGE | 1.500 | -0.440 | [-0.467, -0.416] | 0.5680 | [0.5503, 0.5861] | 0.5492 | 1.034 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 1.940 | 0.000 | [0.000, 0.000] | 0.0969 | [0.0780, 0.1148] | 0.1163 | 0.833 |
| rec_yds | 8227 | 544 | B1-SEASON-TO-DATE | 20.953 | -4.183 | [-4.620, -3.742] | 0.5374 | [0.5171, 0.5562] | 0.7118 | 0.755 |
|  |  |  | B2-RECENT-N | 21.640 | -3.490 | [-3.912, -3.070] | 0.5552 | [0.5341, 0.5735] | 0.6489 | 0.856 |
|  |  |  | B3-EWMA | 21.107 | -4.027 | [-4.429, -3.579] | 0.5615 | [0.5407, 0.5802] | 0.6773 | 0.829 |
|  |  |  | B4-SHRINK | 21.232 | -3.903 | [-4.273, -3.488] | 0.5599 | [0.5386, 0.5790] | 0.6119 | 0.915 |
|  |  |  | B5-ROLE-AVERAGE | 19.913 | -5.230 | [-5.545, -4.915] | 0.5390 | [0.5208, 0.5556] | 0.5127 | 1.051 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 25.148 | 0.000 | [0.000, 0.000] | 0.1523 | [0.1362, 0.1679] | 0.1562 | 0.975 |
| rec_td | 8227 | 544 | B1-SEASON-TO-DATE | 0.259 | -0.008 | [-0.013, -0.003] | 0.1743 | [0.1497, 0.1993] | 0.5663 | 0.308 |
|  |  |  | B2-RECENT-N | 0.270 | 0.004 | [-0.005, 0.013] | 0.1042 | [0.0782, 0.1283] | 1.0604 | 0.098 |
|  |  |  | B3-EWMA | 0.267 | 0.001 | [-0.007, 0.008] | 0.1305 | [0.1040, 0.1547] | 0.8518 | 0.153 |
|  |  |  | B4-SHRINK | 0.272 | 0.006 | [0.003, 0.008] | 0.2376 | [0.2121, 0.2658] | 0.2576 | 0.923 |
|  |  |  | B5-ROLE-AVERAGE | 0.251 | -0.016 | [-0.018, -0.015] | 0.2659 | [0.2444, 0.2875] | 0.2368 | 1.123 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.267 | 0.000 | [0.000, 0.000] | 0.0697 | [0.0485, 0.0876] | 0.0463 | 1.506 |
| team_plays | 1088 | 544 | B1-SEASON-TO-DATE | 7.173 | 0.536 | [0.338, 0.761] | 0.0721 | [0.0191, 0.1312] | 0.5090 | 0.142 |
|  |  |  | B2-RECENT-N | 6.833 | 0.197 | [0.084, 0.320] | 0.0111 | [-0.0448, 0.0689] | 0.2894 | 0.038 |
|  |  |  | B3-EWMA | 6.686 | 0.049 | [-0.049, 0.157] | 0.0604 | [0.0047, 0.1175] | 0.2369 | 0.255 |
|  |  |  | B4-SHRINK | 6.606 | -0.032 | [-0.096, 0.040] | 0.0704 | [0.0127, 0.1295] | 0.1552 | 0.454 |
|  |  |  | B5-ROLE-AVERAGE | 6.641 | 0.000 | [0.000, 0.000] | 0.0560 | [0.0135, 0.0936] | 0.0017 | 33.151 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 6.641 | 0.000 | [0.000, 0.000] | 0.0560 | [0.0135, 0.0936] | 0.0017 | 33.151 |
| team_pass_att | 1088 | 544 | B1-SEASON-TO-DATE | 6.459 | 0.368 | [0.155, 0.609] | 0.1610 | [0.1014, 0.2092] | 0.5402 | 0.298 |
|  |  |  | B2-RECENT-N | 6.194 | 0.099 | [-0.054, 0.284] | 0.1616 | [0.0968, 0.2227] | 0.4144 | 0.390 |
|  |  |  | B3-EWMA | 6.089 | -0.002 | [-0.161, 0.167] | 0.1910 | [0.1253, 0.2473] | 0.3929 | 0.486 |
|  |  |  | B4-SHRINK | 6.083 | -0.008 | [-0.142, 0.147] | 0.1931 | [0.1282, 0.2429] | 0.3496 | 0.552 |
|  |  |  | B5-ROLE-AVERAGE | 6.093 | 0.000 | [0.000, 0.000] | 0.0614 | [0.0092, 0.1083] | 0.0045 | 13.560 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 6.093 | 0.000 | [0.000, 0.000] | 0.0614 | [0.0092, 0.1083] | 0.0045 | 13.560 |
| team_rush_att | 1088 | 544 | B1-SEASON-TO-DATE | 6.027 | 0.108 | [-0.091, 0.320] | 0.2065 | [0.1551, 0.2613] | 0.5435 | 0.380 |
|  |  |  | B2-RECENT-N | 5.769 | -0.152 | [-0.306, 0.025] | 0.2231 | [0.1609, 0.2814] | 0.3933 | 0.567 |
|  |  |  | B3-EWMA | 5.717 | -0.202 | [-0.347, -0.057] | 0.2536 | [0.1951, 0.3068] | 0.3595 | 0.705 |
|  |  |  | B4-SHRINK | 5.702 | -0.216 | [-0.328, -0.100] | 0.2507 | [0.1896, 0.3037] | 0.2792 | 0.898 |
|  |  |  | B5-ROLE-AVERAGE | 5.918 | 0.000 | [0.000, 0.000] | -0.0130 | [-0.0525, 0.0319] | 0.0030 | -4.397 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 5.918 | 0.000 | [0.000, 0.000] | -0.0130 | [-0.0525, 0.0319] | 0.0030 | -4.397 |
| team_dropbacks | 1088 | 544 | B1-SEASON-TO-DATE | 6.896 | 0.428 | [0.202, 0.637] | 0.1518 | [0.0942, 0.2054] | 0.5347 | 0.284 |
|  |  |  | B2-RECENT-N | 6.588 | 0.118 | [-0.033, 0.298] | 0.1467 | [0.0831, 0.2000] | 0.3862 | 0.380 |
|  |  |  | B3-EWMA | 6.479 | 0.010 | [-0.139, 0.178] | 0.1766 | [0.1081, 0.2271] | 0.3665 | 0.482 |
|  |  |  | B4-SHRINK | 6.416 | -0.054 | [-0.172, 0.072] | 0.1833 | [0.1254, 0.2359] | 0.2822 | 0.650 |
|  |  |  | B5-ROLE-AVERAGE | 6.472 | 0.000 | [0.000, 0.000] | -0.0624 | [-0.1068, -0.0136] | 0.0049 | -12.836 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 6.472 | 0.000 | [0.000, 0.000] | -0.0624 | [-0.1068, -0.0136] | 0.0049 | -12.836 |

### FRAME_C — primary role, appeared

| quantity | n | games | baseline | MAE | dMAE vs league prior | 95% CI (game-clustered) | r | 95% CI (game-clustered) | SD ratio | calib slope |
|---|--:|--:|---|--:|--:|---|--:|---|--:|--:|
| pass_att | 928 | 526 | B1-SEASON-TO-DATE | 7.476 | -4.784 | [-5.273, -4.211] | 0.1315 | [0.0688, 0.1954] | 0.5736 | 0.229 |
|  |  |  | B2-RECENT-N | 8.795 | -3.470 | [-4.035, -2.802] | 0.1097 | [0.0407, 0.1754] | 0.9074 | 0.121 |
|  |  |  | B3-EWMA | 7.981 | -4.284 | [-4.804, -3.695] | 0.1345 | [0.0736, 0.1906] | 0.7343 | 0.183 |
|  |  |  | B4-SHRINK | 7.324 | -4.934 | [-5.409, -4.390] | 0.1425 | [0.0752, 0.2093] | 0.4961 | 0.287 |
|  |  |  | B5-ROLE-AVERAGE | 7.598 | -4.663 | [-4.964, -4.322] | 0.0551 | [-0.0030, 0.1171] | 0.0063 | 8.698 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 12.250 | 0.000 | [0.000, 0.000] | 0.0551 | [-0.0030, 0.1171] | 0.0010 | 54.857 |
| pass_cmp | 928 | 526 | B1-SEASON-TO-DATE | 5.299 | -3.062 | [-3.439, -2.683] | 0.1778 | [0.1133, 0.2489] | 0.5707 | 0.311 |
|  |  |  | B2-RECENT-N | 6.343 | -2.020 | [-2.478, -1.590] | 0.1465 | [0.0805, 0.2089] | 0.9076 | 0.161 |
|  |  |  | B3-EWMA | 5.769 | -2.592 | [-3.015, -2.179] | 0.1751 | [0.1091, 0.2349] | 0.7390 | 0.237 |
|  |  |  | B4-SHRINK | 5.232 | -3.130 | [-3.465, -2.766] | 0.2003 | [0.1363, 0.2674] | 0.5091 | 0.393 |
|  |  |  | B5-ROLE-AVERAGE | 5.500 | -2.867 | [-3.079, -2.643] | 0.0230 | [-0.0324, 0.0810] | 0.0049 | 4.670 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 8.354 | 0.000 | [0.000, 0.000] | 0.0230 | [-0.0324, 0.0810] | 0.0007 | 32.641 |
| pass_yds | 928 | 526 | B1-SEASON-TO-DATE | 66.416 | -29.623 | [-33.569, -24.536] | 0.1853 | [0.1243, 0.2455] | 0.5765 | 0.322 |
|  |  |  | B2-RECENT-N | 64.395 | -31.596 | [-35.840, -26.706] | 0.2320 | [0.1711, 0.2882] | 0.5450 | 0.426 |
|  |  |  | B3-EWMA | 63.221 | -32.770 | [-36.896, -27.704] | 0.2367 | [0.1762, 0.2890] | 0.5042 | 0.469 |
|  |  |  | B4-SHRINK | 65.044 | -30.965 | [-34.665, -26.526] | 0.2055 | [0.1445, 0.2634] | 0.4977 | 0.413 |
|  |  |  | B5-ROLE-AVERAGE | 67.429 | -28.573 | [-30.993, -25.663] | 0.0086 | [-0.0560, 0.0804] | 0.0066 | 1.292 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 95.876 | 0.000 | [0.000, 0.000] | 0.0086 | [-0.0560, 0.0804] | 0.0018 | 4.679 |
| pass_td | 928 | 526 | B1-SEASON-TO-DATE | 0.947 | -0.009 | [-0.056, 0.033] | 0.1788 | [0.1192, 0.2370] | 0.5055 | 0.354 |
|  |  |  | B2-RECENT-N | 0.916 | -0.041 | [-0.081, -0.001] | 0.2072 | [0.1417, 0.2718] | 0.4137 | 0.501 |
|  |  |  | B3-EWMA | 0.910 | -0.047 | [-0.092, -0.003] | 0.2274 | [0.1569, 0.2887] | 0.4405 | 0.516 |
|  |  |  | B4-SHRINK | 0.904 | -0.052 | [-0.086, -0.020] | 0.2135 | [0.1539, 0.2763] | 0.3502 | 0.610 |
|  |  |  | B5-ROLE-AVERAGE | 0.923 | -0.033 | [-0.052, -0.014] | -0.0554 | [-0.1166, 0.0087] | 0.0112 | -4.930 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.956 | 0.000 | [0.000, 0.000] | -0.0554 | [-0.1166, 0.0087] | 0.0056 | -9.821 |
| pass_int | 928 | 526 | B1-SEASON-TO-DATE | 0.739 | 0.032 | [0.008, 0.058] | 0.0128 | [-0.0417, 0.0732] | 0.4712 | 0.027 |
|  |  |  | B2-RECENT-N | 0.713 | 0.006 | [-0.016, 0.028] | 0.0056 | [-0.0505, 0.0689] | 0.3478 | 0.016 |
|  |  |  | B3-EWMA | 0.708 | 0.002 | [-0.016, 0.019] | -0.0095 | [-0.0653, 0.0584] | 0.2464 | -0.039 |
|  |  |  | B4-SHRINK | 0.705 | -0.002 | [-0.009, 0.006] | 0.0036 | [-0.0498, 0.0632] | 0.0991 | 0.036 |
|  |  |  | B5-ROLE-AVERAGE | 0.710 | 0.003 | [-0.006, 0.012] | -0.0420 | [-0.1001, 0.0150] | 0.0009 | -46.300 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.706 | 0.000 | [0.000, 0.000] | -0.0420 | [-0.1001, 0.0150] | 0.0003 | -140.670 |
| carries | 966 | 537 | B1-SEASON-TO-DATE | 4.761 | -3.827 | [-4.172, -3.462] | 0.3352 | [0.2757, 0.3983] | 0.6013 | 0.557 |
|  |  |  | B2-RECENT-N | 5.129 | -3.461 | [-3.840, -3.008] | 0.3231 | [0.2565, 0.3886] | 0.7391 | 0.437 |
|  |  |  | B3-EWMA | 4.769 | -3.819 | [-4.163, -3.415] | 0.3765 | [0.3138, 0.4336] | 0.6542 | 0.575 |
|  |  |  | B4-SHRINK | 4.651 | -3.936 | [-4.254, -3.577] | 0.3512 | [0.2919, 0.4118] | 0.5491 | 0.640 |
|  |  |  | B5-ROLE-AVERAGE | 5.043 | -3.542 | [-3.818, -3.238] | 0.0056 | [-0.0530, 0.0613] | 0.0037 | 1.521 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 8.594 | 0.000 | [0.000, 0.000] | 0.0056 | [-0.0530, 0.0613] | 0.0088 | 0.636 |
| rush_yds | 966 | 537 | B1-SEASON-TO-DATE | 28.659 | -10.234 | [-12.080, -8.243] | 0.3309 | [0.2690, 0.3866] | 0.5743 | 0.576 |
|  |  |  | B2-RECENT-N | 29.865 | -9.004 | [-11.152, -7.041] | 0.3252 | [0.2688, 0.3838] | 0.6531 | 0.498 |
|  |  |  | B3-EWMA | 28.432 | -10.437 | [-12.335, -8.546] | 0.3601 | [0.3025, 0.4159] | 0.5403 | 0.667 |
|  |  |  | B4-SHRINK | 27.730 | -11.149 | [-12.868, -9.417] | 0.3522 | [0.2890, 0.4077] | 0.4717 | 0.747 |
|  |  |  | B5-ROLE-AVERAGE | 29.330 | -9.540 | [-10.977, -8.131] | -0.0591 | [-0.1146, 0.0025] | 0.0105 | -5.659 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 38.900 | 0.000 | [0.000, 0.000] | 0.0591 | [-0.0025, 0.1146] | 0.0010 | 57.874 |
| targets | 1004 | 541 | B1-SEASON-TO-DATE | 2.738 | -1.850 | [-2.071, -1.623] | 0.3009 | [0.2526, 0.3532] | 0.5691 | 0.529 |
|  |  |  | B2-RECENT-N | 2.720 | -1.870 | [-2.087, -1.664] | 0.3468 | [0.2987, 0.3908] | 0.5817 | 0.596 |
|  |  |  | B3-EWMA | 2.712 | -1.877 | [-2.087, -1.651] | 0.3527 | [0.3041, 0.3960] | 0.5556 | 0.635 |
|  |  |  | B4-SHRINK | 2.658 | -1.930 | [-2.135, -1.740] | 0.3378 | [0.2937, 0.3856] | 0.5096 | 0.663 |
|  |  |  | B5-ROLE-AVERAGE | 2.779 | -1.807 | [-1.977, -1.655] | 0.0901 | [0.0293, 0.1483] | 0.1299 | 0.694 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 4.581 | 0.000 | [0.000, 0.000] | 0.0953 | [0.0385, 0.1573] | 0.1236 | 0.771 |
| receptions | 1004 | 541 | B1-SEASON-TO-DATE | 2.133 | -1.083 | [-1.240, -0.927] | 0.3095 | [0.2564, 0.3637] | 0.5621 | 0.550 |
|  |  |  | B2-RECENT-N | 2.121 | -1.097 | [-1.256, -0.942] | 0.3313 | [0.2779, 0.3848] | 0.5715 | 0.580 |
|  |  |  | B3-EWMA | 2.072 | -1.146 | [-1.298, -1.000] | 0.3550 | [0.3033, 0.4037] | 0.5232 | 0.678 |
|  |  |  | B4-SHRINK | 2.059 | -1.157 | [-1.305, -1.019] | 0.3389 | [0.2864, 0.3885] | 0.4884 | 0.694 |
|  |  |  | B5-ROLE-AVERAGE | 2.173 | -1.043 | [-1.170, -0.929] | 0.0153 | [-0.0514, 0.0754] | 0.0746 | 0.204 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 3.210 | 0.000 | [0.000, 0.000] | 0.0166 | [-0.0476, 0.0803] | 0.0793 | 0.209 |
| rec_yds | 1004 | 541 | B1-SEASON-TO-DATE | 31.916 | -9.537 | [-11.567, -7.525] | 0.2789 | [0.2195, 0.3418] | 0.5474 | 0.509 |
|  |  |  | B2-RECENT-N | 30.569 | -10.883 | [-12.780, -8.839] | 0.3329 | [0.2749, 0.3952] | 0.4714 | 0.706 |
|  |  |  | B3-EWMA | 31.651 | -9.817 | [-11.798, -7.815] | 0.2967 | [0.2467, 0.3534] | 0.4806 | 0.617 |
|  |  |  | B4-SHRINK | 30.728 | -10.726 | [-12.578, -8.807] | 0.3099 | [0.2554, 0.3707] | 0.4633 | 0.669 |
|  |  |  | B5-ROLE-AVERAGE | 31.376 | -10.060 | [-11.660, -8.548] | 0.1286 | [0.0792, 0.1786] | 0.0989 | 1.300 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 41.351 | 0.000 | [0.000, 0.000] | 0.1326 | [0.0830, 0.1848] | 0.0964 | 1.375 |
| rec_td | 1004 | 541 | B1-SEASON-TO-DATE | 0.496 | 0.046 | [0.025, 0.067] | 0.0889 | [0.0288, 0.1553] | 0.4606 | 0.193 |
|  |  |  | B2-RECENT-N | 0.576 | 0.127 | [0.085, 0.166] | -0.0043 | [-0.0628, 0.0569] | 1.0224 | -0.004 |
|  |  |  | B3-EWMA | 0.552 | 0.103 | [0.070, 0.136] | 0.0174 | [-0.0444, 0.0817] | 0.8033 | 0.022 |
|  |  |  | B4-SHRINK | 0.482 | 0.033 | [0.021, 0.044] | 0.1339 | [0.0765, 0.1930] | 0.2045 | 0.655 |
|  |  |  | B5-ROLE-AVERAGE | 0.509 | 0.060 | [0.049, 0.070] | 0.0946 | [0.0437, 0.1443] | 0.0317 | 2.988 |
|  |  |  | B6-LEAGUE-POSITION-PRIOR | 0.449 | 0.000 | [0.000, 0.000] | 0.0957 | [0.0489, 0.1429] | 0.0241 | 3.975 |

FRAME_B (all appearances) is in `D8_BASELINE_RESULTS.json`.

### Two reading warnings

1. **`B6`'s r is an artifact, not a signal.** The league prior takes only two
   distinct values across the evaluation window (2023 computed from 2021–2022,
   2024 from 2021–2023), so its SD ratio is ~0.001–0.16 and its correlation is a
   two-point artifact. Read `B6` as the MAE floor it is; do not read its r.
2. **`B5-ROLE-AVERAGE` is degenerate for team quantities.** A team is its own
   only role, so `B5` collapses exactly onto `B6` in those four rows. It is
   reported for completeness, not as a fifth team baseline.

---

## 9. Which quantities have no defensible simple baseline, and why

The test applied: a baseline is *defensibly better* only if its ΔMAE against the
league/position prior has a **game-clustered 95% interval entirely below zero**.

**Team volume — `team_plays`, `team_pass_att`, `team_dropbacks`: no defensible
simple baseline exists.** Not one of the five clears the league prior on
FRAME_A. `B1-SEASON-TO-DATE` is *worse* than the prior on all three
(`team_plays` +0.54 MAE, interval [+0.34, +0.76]). The best of them,
`B4-SHRINK`, is indistinguishable from a constant. `team_rush_att` is the lone
exception and the margin is tiny: `B4` at −0.216 MAE, interval [−0.328,
−0.100], on a quantity whose MAE is ~5.9. This corroborates WS07 from the other
direction: team volume sits close to its own noise ceiling, and *the correct
baseline for team volume is the league mean*. A V2 team-volume model should be
judged against a constant, and beating a constant at all would be the result.

**Interceptions — `pass_int`: no defensible simple baseline at the level that
matters.** On FRAME_C (starting quarterbacks) **zero of five** clear the prior;
`B1` is significantly *worse* (+0.032, interval [+0.008, +0.058]). On FRAME_A
only `B5-ROLE-AVERAGE` clears, and it does so by predicting *which* quarterback
is starting, not how many interceptions he throws. A quarterback's own
interception history does not forecast his next game.

**Receiving touchdowns — `rec_td`: no defensible simple baseline at the level
that matters.** On FRAME_C **zero of five** clear the prior and `B2-RECENT-N` is
much worse (+0.127, interval [+0.085, +0.166]) with an SD ratio of 1.02 — it is
producing more variance than the outcome has. On FRAME_A only `B1` and `B5`
clear, and both by margins under 0.02 touchdowns.

**Passing touchdowns — `pass_td`: marginal.** Four of five clear on FRAME_C but
the best margin is −0.052 MAE on a base of 0.956, and `B1` does not clear at all.

**Everything else has a strong baseline, and the bar is high.** Volume and
yardage — attempts, completions, passing yards, carries, rushing yards, targets,
receptions, receiving yards — all five baselines clear the prior on **both**
FRAME_A and FRAME_C for every one of those eight quantities, cutting the prior's
MAE by **14–31% on FRAME_A** and **23–46% on FRAME_C**. Excluding the two
degenerate rows (`B5` at rank 1 and `B6` itself), correlations run **0.537–0.669
on FRAME_A** and **0.110–0.377 on FRAME_C**. `B3-EWMA` on RB carries is the
strongest single cell on both frames (r = 0.669 and r = 0.377).

On the season-opener frame the same eight quantities are carried by the week-1
family, which has three members rather than five: two of three clear the prior
on seven of them, and only one of three on passing yards.

**The pattern is the repository's own thesis, reproduced from a fourth
independent direction: opportunity is predictable, efficiency and scoring events
are mostly not.** The quantities with no defensible simple baseline are exactly
the rate and scoring quantities; the quantities with strong baselines are
exactly the opportunity and yardage quantities that scale with opportunity.

---

## 10. What this is not

- **Not a confirmatory evaluation of anything.** These are baselines, not
  candidates. No V2 model exists to compare them against.
- **Not a holdout for 2026.** 2023–2024 is the evaluation window here; a V2
  candidate scored on those same seasons is doing exploratory work, because
  these baselines' windows and the carry-over slope were selected on 2021–2022
  and the frames were designed with 2023–2024 visible in aggregate. A
  confirmatory comparison needs games that no design decision has touched.
- **Not comparable to the engine's published r values without matching the
  population.** See §4.
- **Not a distributional baseline.** These are point forecasts. CRPS, log score
  and PIT need a predictive distribution, and a mean is not one. Extending any
  of these to a distribution is a separate piece of work and would need its own
  freeze.
- **Not robust to roster movement.** No roster feed; see §5.
- **Not a 2025 fold.** There is no `pbp_2025` blob in this repository, so the
  natural forward-chained fold between the estimation window and the live season
  does not exist here.

## 11. Open, and what would need the owner

1. **A 2025 play-by-play blob** would give a clean forward-chained fold
   (constants 2021–2022, evaluation 2023–2024, confirmation 2025) without
   touching the live season. It needs someone with network egress; it is not
   blocked for this repository, it is assigned outside it.
2. **The MAE-versus-RMSE window disagreement** (§7) is a real methodological
   fork. My reading is that the freeze should stand and the sensitivity be
   carried alongside it. If the owner would rather the baselines be frozen under
   a squared loss, that is a re-freeze and it must happen **before** any V2
   candidate is scored, not after.
3. **Distributional baselines** — whether V2 candidates will be scored on CRPS
   and PIT, in which case a distributional counterpart to each of these is
   needed and should be frozen on the same schedule.
