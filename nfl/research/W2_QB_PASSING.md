# W2 — QB / passing skill model

**Worker 2, NFL Greenfield Architecture research pass. 2026-09-06.**
Research only. No production model code was written. Everything below is
labelled `VERIFIED` / `DERIVED` / `UNVERIFIED-RECALL` per
`nfl/research/_GROUNDING.md`.

Measurement scripts live in the session scratchpad
(`/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-.../scratchpad/`):
`build_qb.py`, `inv.py`, `denom.py`, `denom2.py`, `xcheck.py`, `xcheck2.py`,
`xcheck3.py`, `panel.py`, `decomp.py`, `decomp2.py`, `rel.py`, `opp_rel.py`,
`randsplit.py`, `final_rel.py`, `null_check.py`, `overdisp.py`, `yoy.py`,
`env_rel.py`, `fwd.py`, `vol.py`, `dist.py`. They are evidence, not
deliverables, and are deliberately not committed.

---

## 0. Headline, before the detail

Five results drive everything else in this document.

1. `VERIFIED` **The nflverse `pass_attempt` column includes sacks.** 19,153
   plays have `pass_attempt == 1` in REG 2024, of which 1,314 are sacks. Real
   throws are 17,839. Any rate divided by `pass_attempt` is divided by the wrong
   denominator.
2. `VERIFIED` **`participation.ngs_air_yards` is 100% empty in 2024** — 0
   non-null of 45,919 rows. The `_GROUNDING.md` schema lists the column; the
   column carries no data. Use `pbp.air_yards` instead.
3. `VERIFIED` **Interception rate is a noise trap.** Robust within-season
   split-half r = 0.212 (95% CI −0.168 to +0.530, n=46 QBs); year-over-year
   r = −0.130 (2022→23, n=22), +0.049 (2023→24, n=26), +0.232 (2022→24, n=20).
   Every year-over-year interval covers zero. The odd-even split gives 0.523,
   which is a lucky-partition artefact — see §5.3.
4. `VERIFIED` **Almost all of the game-level discrimination in QB passing yards
   lives in the realised dropback count, and prior form predicts that count
   badly.** Forward-chained on 356 QB-games: prior-form prediction reaches
   r = +0.136; the same rate model handed the *realised* dropback count reaches
   r = +0.636. Prior dropbacks/game alone correlates +0.147 with realised
   dropbacks.
5. `VERIFIED` **The DerSimonian–Laird shrinkage method used at
   `v7/rates.py:220` transfers to some NFL rates and breaks on others.** For
   scheme/opponent rates the within-QB game-level dispersion is 1.6× to 3.0×
   binomial, so DL attributes opponent variation to player skill. DL gives
   k = 200 for blitz-faced rate; split-half says the QB-persistent signal is
   indistinguishable from zero (r = 0.020).

Result 4 is the architectural finding. Skill is the part we can measure;
opportunity is the part that carries the outcome.

---

## 1. Data and method

`VERIFIED` Sources are the shared cache described in `_GROUNDING.md`; nothing
new of size was downloaded. Small additions: `player_stats_2022.csv`
(1,689,929 bytes, HTTP 200) and `player_stats_2023.csv` (1,695,570 bytes,
HTTP 200) for the year-over-year section. `player_stats_2025.csv` returns
**404** — that release does not exist under that name.

`VERIFIED` The working panel is one row per play, joining
`play_by_play_2024` (49,492 rows) ← `pbp_participation_2024` on
`(game_id, play_id)` ← `ftn_charting_2024` on
`(nflverse_game_id, nflverse_play_id)`. Both joins validate `1:1`. Overall
match rates: participation 92.75%, FTN 97.05% (`build_qb.py`). **On the
dropback population both joins are effectively complete** — see §2.

`VERIFIED` Populations, REG 2024 only, excluding kneels, spikes and two-point
plays:

| Population | n | Definition |
|---|---|---|
| Games | 272 | distinct `game_id`, `season_type == 'REG'` |
| Dropbacks | 20,115 | `qb_dropback == 1` |
| Throws | 17,740 | dropback AND `pass_attempt == 1` AND `sack != 1` |
| Sacks | 1,314 | dropback AND `sack == 1` |
| Scrambles | 1,061 | dropback AND `qb_scramble == 1` |
| Completions | 11,629 | |
| Interceptions | 387 | |
| QB-game rows | 676 | 109 distinct QBs |
| QBs ≥ 200 dropbacks | 40 | ≥300: 31 · ≥100: 47 |

`VERIFIED` Throws + sacks + scrambles = 17,740 + 1,314 + 1,061 = 20,115 =
dropbacks exactly. The three-way partition is clean and mutually exclusive
(`denom.py` crosstab: zero plays in more than one cell, zero plays in none).

`VERIFIED` **Aggregation was validated against an independent file.** Summing
the play-level panel by passer and comparing with `player_stats_2024.csv`, for
the 46 QBs with ≥100 official attempts (`xcheck.py`):

| Quantity | QBs matching exactly | Max abs. diff | pbp total | player_stats total |
|---|---|---|---|---|
| Completions | 46 / 46 | 0 | 11,100 | 11,100 |
| Passing yards | 46 / 46 | 0 | 121,397 | 121,397 |
| Passing TDs | 46 / 46 | 0 | 776 | 776 |
| Interceptions | 46 / 46 | 0 | 371 | 371 |
| Attempts | 14 / 46 | 6 | 16,994 | 16,969 |

`VERIFIED` The attempt discrepancy is two separate effects: 99 two-point
conversion throws inflate the pbp count, and ~67 penalty-affected plays
(`pass == 1` but `pass_attempt != 1`, n = 1,168 season-wide, **penalty fraction
1.000**) deflate it. After removing two-point plays the residual is 67 of
16,969 = 0.39% (`xcheck2.py`, `xcheck3.py`). `DERIVED` Everything except the
attempt denominator reconciles to the byte; the attempt denominator has a
0.4% definitional gap that must be declared, not silently absorbed.

---

## 2. Inventory: what is actually measurable for a QB

`VERIFIED` Availability on the dropback population, measured with
`.notna().mean()` (`inv.py`). "Availability" here is presence of a value, not
correctness.

| Field | Source | Avail. on dropbacks | Avail. on throws | Correct denominator |
|---|---|---|---|---|
| `qb_dropback`, `qb_scramble`, `sack`, `qb_kneel`, `qb_spike` | pbp | 1.0000 | — | plays |
| `complete_pass`, `incomplete_pass`, `interception`, `pass_touchdown` | pbp | 1.0000 | 1.0000 | throws |
| `passing_yards` | pbp | — | 1.0000 on completions | completions |
| `air_yards` | pbp | 0.8776 | **0.9945 on true throws** | throws |
| `yards_after_catch` | pbp | 0.5753 | **1.0000 on completions, 0.0000 otherwise** | completions |
| `cp` / `cpoe` | pbp (NGS model) | 0.8416 | **0.9537 on true throws** | throws with `cp` |
| `qb_epa` | pbp | 1.0000 | 1.0000 | dropbacks |
| `xpass`, `pass_oe` | pbp | 0.9951 | — | plays |
| `was_pressure` | participation | **1.0000** | 1.0000 | dropbacks |
| `time_to_throw` | participation | 0.8813 | 0.9295 | throws (absent on sacks/scrambles by construction) |
| `ngs_air_yards` | participation | **0.0000** | 0.0000 | — column is empty |
| `number_of_pass_rushers` | participation | 1.0000 | — | dropbacks |
| `defenders_in_box` | participation | 1.0000 | — | plays |
| `offense_formation` | participation | 0.9993 | — | plays |
| `defense_man_zone_type`, `defense_coverage_type` | participation | 0.9977 | — | dropbacks |
| `is_play_action`, `is_rpo`, `is_motion`, `is_screen_pass` | FTN | 1.0000 | — | plays |
| `is_qb_out_of_pocket`, `is_throw_away`, `is_qb_sneak` | FTN | 1.0000 | — | dropbacks / throws |
| `is_interception_worthy` | FTN | 1.0000 | 1.0000 | throws |
| `is_catchable_ball`, `is_contested_ball`, `is_drop` | FTN | 1.0000 | 1.0000 | throws |
| `read_thrown` | FTN | 1.0000 | — | throws (but see sentinel note) |
| `n_blitzers`, `n_pass_rushers`, `is_qb_fault_sack` | FTN | 1.0000 | — | dropbacks / sacks |

`VERIFIED` `time_to_throw` is null on exactly 2,400 dropbacks; sacks + scrambles
= 2,375. `DERIVED` The field exists when and only when the ball leaves the
hand, which is the correct behaviour and the correct denominator (throws), not
a defect.

`VERIFIED` `was_pressure` on dropbacks: 6,240 True / 13,975 False, no nulls.
Pressure rate 30.87%.

`VERIFIED` **FTN charting exists only from 2022** (`_GROUNDING.md`, re-read
here; 404 for 2016/2018/2020/2021). `DERIVED` Every FTN-derived feature —
play-action, RPO, motion, interception-worthy, throwaway, blitzers, QB-fault
sack — has a **four-season** history at most, and any multi-season prior built
on them is capped at four seasons while pbp-derived priors are not. Two
different history depths in the same model is a declaration-drift hazard
(`V8_FAILURE_TAXONOMY` class C) and must be recorded per feature, not per model.

---

## 3. Denominator and sentinel hazards found

This project has been burned by wrong denominators, so these are separated out.

### 3.1 `pass_attempt` includes sacks
`VERIFIED` (`denom.py`) Of 19,153 dropback plays with `pass_attempt == 1`,
1,314 are sacks. `air_yards` is null on 93.0% of the throws where it is missing
*because those are sacks*. `DERIVED` Completion percentage computed as
`complete_pass / pass_attempt` returns 11,629 / 19,153 = 0.6072 instead of the
true 11,629 / 17,740 = 0.6555 — a 4.8 percentage-point error, larger than the
entire measured between-QB spread in completion% (`sd_between` = 0.0343, §5.4).

### 3.2 The QB is not in `passer_player_id` on a scramble
`VERIFIED` `passer_player_id` is null on 5.25% of dropbacks; on scrambles it is
null 100% of the time and `rusher_player_id` is populated 100% of the time.
The cleaned `passer_id` column covers scrambles (99.91% non-null on scrambles,
matching `rusher_player_id` where present) and is identical to
`passer_player_id` on all 19,153 rows where both exist. `DERIVED` Group by
`passer_id`, never `passer_player_id`; grouping by the latter silently drops
every scramble and therefore biases dropback counts down by ~5%.

### 3.3 Zero is a sentinel, not a measurement
`VERIFIED` (`denom.py`, sentinel check) On the 27,059 non-dropback plays,
`n_pass_rushers == 0` on 24,441 and `defenders_in_box == 0` on 8,792. On
dropbacks, `n_pass_rushers == 0` on only 260 of 20,215. `read_thrown == '0'` on
2,604 dropbacks. `starting_hash == '0'` and `qb_location == '0'` behave the same
way. `DERIVED` These zeros are "not applicable / not charted", not measured
zeros. Averaging them is a textbook class-A failure — absence read as a value.
Ingest must map them to null on non-dropbacks and treat the residual dropback
zeros as missing.

### 3.4 `n_blitzers` is not a rusher count
`VERIFIED` `n_blitzers` on dropbacks: 0 → 14,398, 1 → 4,267, 2 → 1,329,
3 → 208, 4 → 12, 5 → 1. `n_pass_rushers` on the same rows: 4 → 13,852,
5 → 4,043, 6 → 1,084. `DERIVED` `n_blitzers` counts *additional* rushers beyond
the base rush, so "blitz" is `n_blitzers >= 1` (28.8% of dropbacks), **not**
`n_blitzers >= 5`. My first pass used `>= 5` and produced 1 blitz in an entire
season. Recorded here because it is the exact shape of defect the failure
taxonomy names, and because the wrong version looked like a working column.

### 3.5 Market columns ship inside the "neutral" data
`VERIFIED` `schedules/games.csv` carries `spread_line`, `total_line`,
`away_spread_odds`, `home_spread_odds` alongside `result`, `total`, `roof`,
`temp`, `wind`. `_GROUNDING.md` flags this for `play_by_play`; it is equally
true of the schedule file, which is the natural join for weather and venue.
`DERIVED` Quarantine must be applied at the *file* level on ingest, not to a
single file.

### 3.6 Sack yards are not passing yards
`VERIFIED` `passing_yards` is non-null on 0.0000 of 1,314 sacks; mean
`yards_gained` on a sack is −6.575 (SD 3.805). `DERIVED` A "passing yards" prop
and a "team net passing yards" quantity are different denominators by 8,640
yards across the season. Which one a market settles on must be read from the
market, never assumed.

---

## 4. Skill × Opportunity, measured

Skill is a rate. Opportunity is a count. The exact decomposition used is the
log identity: for `Y = V × R`,

```
Var(ln Y) = Var(ln V) + Var(ln R) + 2·Cov(ln V, ln R)
```

which is exact, sums to the total by construction, and was checked to sum
(`decomp.py`, "check sum" line in every block).

### 4.1 Quantity 1 — passing yards, across QBs over a season

`VERIFIED` n = 40 QBs with ≥200 dropbacks, REG 2024. Per-game normalised, so
games-played is not counted as skill or opportunity (`decomp2.py`):

**yards/game = (dropbacks/game) × (yards/dropback)**, Var(ln Y) = 0.02724

| Component | Var(ln) | Share |
|---|---|---|
| dropbacks per game (OPPORTUNITY) | 0.01333 | 48.96% |
| yards per dropback (SKILL) | 0.01644 | 60.34% |
| 2·Cov | −0.00253 | −9.30% |

`VERIFIED` A three-way split of the same quantity:
**yards/game = (throws/game) × (completion%) × (yards/completion)**

| Component | Var(ln) | Share |
|---|---|---|
| throws per game | 0.01398 | 51.33% |
| completion % | 0.00534 | 19.61% |
| yards per completion | 0.01028 | 37.73% |
| 2·Cov(throws, comp%) | +0.00728 | +26.74% |
| 2·Cov(throws, yds/cmp) | −0.00662 | −24.29% |
| 2·Cov(comp%, yds/cmp) | −0.00303 | −11.11% |

`DERIVED` Across a season the split is close to even — roughly half opportunity,
half efficiency, with the covariance terms small and partly cancelling. The
positive throws↔completion% covariance and negative throws↔yards-per-completion
covariance are the checkdown trade-off: high-volume passing games are shorter
passing games.

`VERIFIED` Without the per-game normalisation, volume dominates (71.45% for
dropbacks vs 9.32% for yards/dropback, n=40). `DERIVED` That version is
misleading: `Var(ln games) = 0.09779` with games ranging 7 to 17, so most of the
apparent "opportunity" variance is availability, not usage rate. Availability is
a real modelling problem but it is the injury layer, not the QB skill layer, and
folding it into "opportunity" overstates the case.

### 4.2 Quantity 2 — completions, across QBs over a season

`VERIFIED` **completions = throws × completion%**, n = 40, Var(ln Y) = 0.15415:
volume 79.53%, rate 3.46%, 2·Cov 17.00% (corr +0.512).
`DERIVED` Completions are almost purely an opportunity statistic. Completion
percentage contributes 3.5% of the between-QB variance in season completions.
A completions market is a volume market wearing an accuracy costume.

### 4.3 The same decompositions at the game level

`VERIFIED` n = 555 QB-games with ≥15 dropbacks (`decomp.py`):

| Quantity | volume share | rate share | 2·Cov |
|---|---|---|---|
| passing yards = dropbacks × yards/dropback | 50.36% | 59.48% | −9.85% (corr −0.090) |
| completions = throws × completion% | 80.17% | 25.55% | −5.72% |

`VERIFIED` Between-QB vs within-QB variance of *game* passing yards, restricted
to 33 QBs with ≥8 qualifying games (451 QB-games, grand mean 233.3 yards):
R²_between = **0.1141**. For yards/dropback R²_between = 0.1874; for dropbacks
R²_between = 0.1287.

`DERIVED` Even a model that knew the QB's identity perfectly and nothing else
would explain 11.4% of the game-to-game variance in his passing yards on this
sample. **This is not a ceiling on prediction** — the remaining 88.6% contains
opponent, game script, weather and injury effects that are partly forecastable,
and CLAUDE.md explicitly withdraws a ceiling claim of exactly this shape from
the MLB work. It is a statement about how much of the variance is *player
identity* and no more than that.

### 4.4 Forward-chained: where the discrimination actually is

`VERIFIED` (`fwd.py`) 356 QB-games with ≥10 dropbacks and ≥4 prior games in the
same season (weeks 5–18). Every predictor uses only prior weeks. Target is the
QB's passing yards in that game.

| Predictor | r | SD ratio | slope | MAE | RMSE |
|---|---|---|---|---|---|
| 0. league mean (constant) | n/a | 0.000 | — | 59.2 | 75.1 |
| 1. prior yards/game | +0.1356 | 0.452 | +0.300 | 62.7 | 78.4 |
| 2. prior dropbacks/game × league yards/dropback | +0.0084 | 0.322 | +0.026 | 62.6 | 79.4 |
| 3. league dropbacks/game × prior yards/dropback | +0.1335 | 0.415 | +0.322 | 61.6 | 77.4 |
| 4. prior dropbacks/gm × prior yards/dropback | +0.1356 | 0.452 | +0.300 | 62.7 | 78.4 |
| **5. ORACLE realised dropbacks × league yards/dropback** | **+0.6204** | 0.733 | +0.846 | 46.8 | 59.9 |
| **6. ORACLE realised dropbacks × prior yards/dropback** | **+0.6355** | 0.832 | +0.764 | 47.3 | 59.9 |

`VERIFIED` Rows 5 and 6 are oracles: they consume the realised dropback count.
`VERIFIED` corr(prior mean dropbacks/game, realised dropbacks) = +0.147 (n=371);
corr(prior mean yards/dropback, realised yards/dropback) = +0.191 (n=371)
(`vol.py`).

`DERIVED` Three things follow, and they set the whole QB architecture.

- A prior-form QB model lands at r ≈ 0.14 on game passing yards. That is the
  same order as MLB's r = 0.1101 baseline. Starting the NFL work at MLB's
  ending point is the default outcome, not a bad outcome to be surprised by.
- Knowing the opportunity count is worth roughly r 0.14 → 0.62. Knowing the
  efficiency rate given league-average volume is worth r 0.13. **Opportunity is
  where the available discrimination lives**, and the rate layer contributes
  almost nothing on top of an oracle volume (0.6204 → 0.6355).
- The reason a prior-form model cannot cash that in is that prior form predicts
  the count badly (+0.147). `VERIFIED` What does correlate with a QB's dropback
  count in a game is the game itself: corr with team offensive plays +0.482,
  with |final margin| −0.182, with game total points +0.149, with final margin
  −0.114 (n=573, `vol.py`). Those are game-state quantities, and at prediction
  time they are unknown.

`DERIVED` **The single highest-value target for the NFL QB layer is a
forecast of team pass volume, not a better QB efficiency estimate.** That
crosses into the game/environment worker's territory, and the QB layer's job is
to consume a volume distribution rather than to produce a point estimate of one.

---

## 5. Reliability and stabilization

This is the quantitative core, and the analogue of the DerSimonian–Laird
shrinkage measured at `v7/rates.py:220`. Per CLAUDE.md rule 3 none of these
constants is chosen; all are measured, and the ones that could not be measured
are reported as such.

### 5.1 Method

`VERIFIED` Split-half across **games**, not plays: for each QB the 2024 REG
games are partitioned into two halves, each half's rate is computed on its own
denominator, and the two halves are correlated across QBs. QBs qualify when
their combined denominator ≥ 100. Reported `r` is the median over **1,000
random partitions**, each paired with a fresh bootstrap resample of QBs, so the
interval carries both partition and player uncertainty (`final_rel.py`, seed
20260906).

`DERIVED` The stabilization constant follows from the split-half correlation.
If each half has n̄ trials, ρ = τ²/(τ² + σ²/n̄), so

```
k = σ²/τ² = n̄ · (1 − r) / r
```

is the denominator at which reliability = 0.5 — the same object as the `k` in
`rates.py`. `n@r=.7` is `k · 0.7/0.3`, the denominator at which reliability
reaches 0.7.

`VERIFIED` **Null calibration** (`null_check.py`): re-drawing both halves
binomially at the pooled league rate, with the real half sizes and no true
spread, gives simulated r of +0.001 (INT), +0.001 (completion%), +0.003 (sack
rate), +0.004 (int-worthy), with a 95% band of roughly ±0.32 at n = 46 QBs. The
estimator is unbiased, and **±0.32 is the resolution floor of this whole
table.** Anything below about 0.32 cannot be separated from zero on one season.

### 5.2 The measured table

`VERIFIED` REG 2024. `r` is the median over 1,000 random partitions; the
interval is the 2.5/97.5 percentile of the paired partition + QB bootstrap.

`VERIFIED` Footnote on the `QBs` and `n/half` columns: they are recorded from
the final partition of the 1,000, not fixed across them. They move slightly
(46 vs 47 QBs; 204.7 vs 208.1 per half on the same `dropbacks` denominator)
because a QB with few games can land entirely inside one half of a given random
partition and is then dropped from that partition. `DERIVED` `k` inherits that
~2% partition dependence through `n̄`. It is reported because the alternative —
quoting a single fixed number that the estimator does not actually use — would
be a small piece of declaration drift.

| Quantity | Denominator | Mostly attributable to | QBs | n/half | r | 95% CI | k (rel .5) | n at r=.7 |
|---|---|---|---|---|---|---|---|---|
| motion rate | dropbacks | scheme | 46 | 208 | 0.733 | [+0.477, +0.876] | 76 | 177 |
| scramble rate | dropbacks | QB | 47 | 205 | 0.670 | [+0.382, +0.840] | 101 | 235 |
| out-of-pocket rate | dropbacks | QB | 45 | 211 | 0.610 | [+0.318, +0.826] | 135 | 315 |
| yards per dropback | dropbacks | QB | 47 | 205 | 0.573 | [+0.202, +0.782] | 152 | 355 |
| aDOT (air yds/throw) | throws w/ air yds | QB + scheme | 46 | 184 | 0.542 | [+0.092, +0.798] | 156 | 363 |
| EPA per dropback | dropbacks | QB | 47 | 205 | 0.528 | [+0.180, +0.775] | 183 | 428 |
| time to throw | throws w/ TTT | QB | 45 | 186 | 0.513 | [+0.174, +0.736] | 177 | 412 |
| play-action rate | dropbacks | scheme | 46 | 208 | 0.505 | [+0.159, +0.725] | 204 | 476 |
| xpass per dropback | plays w/ xpass | game state | 47 | 205 | 0.495 | [+0.128, +0.758] | 208 | 486 |
| CPOE | throws w/ cp | QB | 46 | 176 | 0.456 | [+0.042, +0.716] | 210 | 489 |
| sack given pressure | pressured dropbacks | QB | 29 | 81 | 0.452 | [+0.048, +0.722] | 98 | 229 |
| completion % | throws | QB | 46 | 184 | 0.425 | [+0.001, +0.719] | 248 | 579 |
| pass-TD rate | throws | QB + context | 46 | 184 | 0.413 | [+0.020, +0.680] | 261 | 610 |
| sack rate | dropbacks | QB + OL | 47 | 205 | 0.399 | [−0.004, +0.696] | 308 | 719 |
| throwaway rate | throws | QB | 46 | 184 | 0.399 | [−0.042, +0.693] | 276 | 645 |
| pressure-allowed rate | dropbacks | OL + QB | 46 | 208 | 0.382 | [+0.036, +0.657] | 336 | 785 |
| deep-throw rate ≥20 ay | throws w/ air yds | QB + scheme | 46 | 184 | 0.356 | [−0.106, +0.689] | 333 | 777 |
| screen rate | dropbacks | scheme | 47 | 205 | 0.347 | [−0.051, +0.656] | 385 | 897 |
| **int-worthy rate (FTN)** | throws | QB | 46 | 184 | **0.259** | [−0.126, +0.590] | 524 | 1,224 |
| YAC per completion | completions | receivers | 42 | 129 | 0.222 | [−0.194, +0.563] | 451 | 1,052 |
| **interception rate** | throws | QB | 46 | 184 | **0.212** | [−0.168, +0.530] | 682 | 1,591 |
| RPO rate | dropbacks | scheme | 47 | 205 | 0.180 | [−0.172, +0.497] | 935 | 2,181 |
| **5+ rushers faced** | dropbacks charted | opponent | 46 | 208 | 0.037 | [−0.289, +0.355] | 5,427 | 12,663 |
| **blitz-faced (FTN ≥1)** | dropbacks | opponent | 47 | 205 | 0.020 | [−0.302, +0.350] | 10,221 | 23,848 |
| **drop rate charged** | throws | receivers | 46 | 184 | 0.008 | [−0.418, +0.420] | 21,738 | 50,722 |

`VERIFIED` Opportunity metrics, split on games rather than plays, QBs with ≥4
games in each half, n = 36 QBs, mean 6.9 games per half (`opp_rel.py`):

| Quantity | r (odd-even) | 95% CI | k (games) |
|---|---|---|---|
| designed QB rushes / game | +0.911 | [+0.821, +0.967] | 0.7 |
| scrambles / game | +0.696 | [+0.508, +0.828] | 3.0 |
| sacks / game | +0.669 | [+0.437, +0.847] | 3.4 |
| pass TD / game | +0.534 | [+0.219, +0.722] | 6.0 |
| dropbacks / game | +0.489 | [+0.230, +0.717] | 7.2 |
| throws / game | +0.460 | [+0.185, +0.694] | 8.1 |
| passing yards / game | +0.458 | [+0.197, +0.691] | 8.1 |
| INT / game | +0.333 | [−0.041, +0.677] | 13.8 |

`DERIVED` Designed QB rushes are the most player-stable quantity anywhere in
this document (k ≈ 0.7 games — one game of observation already carries most of
the signal). That is a role assignment, not a skill, and it is nearly a
constant per QB. It should be treated as a near-deterministic input, not a rate
to be shrunk.

### 5.3 Why the interception number in an earlier pass was wrong, and what it means

`VERIFIED` The **odd-even chronological** split gives INT-rate r = 0.523
(`rel.py`). Over 500 **random** partitions with no bootstrap the median is
0.206 with IQR [+0.140, +0.281] (`randsplit.py`); over 1,000 random partitions
each paired with a QB bootstrap the median is 0.212 (`final_rel.py`). 0.523 sits
far outside that IQR under either run.

`DERIVED` A single named partition of ~13 games per QB is itself a random draw,
and with n = 46 QBs the partition-to-partition SD of r is large. **Reporting a
reliability from one split is reporting one draw from a wide distribution.**
Any NFL stabilization constant in this project must be estimated over many
partitions, and the odd-even convention alone is not adequate. This is a
methodology requirement, not a preference.

`VERIFIED` Cross-check by year-over-year on season totals, QBs with ≥200
attempts in both seasons (`yoy.py`):

| Rate | Denominator | 2022→23 (n=22) | 2023→24 (n=26) | 2022→24 (n=20) |
|---|---|---|---|---|
| completion % | attempts | +0.368 [−0.274, +0.707] | +0.428 [+0.139, +0.668] | +0.027 [−0.393, +0.469] |
| **interception rate** | attempts | **−0.130** [−0.511, +0.259] | **+0.049** [−0.384, +0.411] | **+0.232** [−0.215, +0.539] |
| pass-TD rate | attempts | +0.514 [+0.080, +0.798] | +0.352 [+0.092, +0.604] | +0.283 [−0.179, +0.653] |
| **sack rate** | attempts+sacks | **+0.725** [+0.521, +0.894] | **+0.571** [+0.227, +0.805] | **+0.423** [+0.059, +0.672] |
| yards per attempt | attempts | +0.455 [+0.018, +0.745] | +0.557 [+0.148, +0.766] | +0.096 [−0.269, +0.476] |
| aDOT | attempts | +0.306 [−0.063, +0.636] | +0.607 [+0.426, +0.782] | +0.048 [−0.411, +0.657] |
| YAC per completion | completions | +0.371 [−0.138, +0.710] | +0.233 [−0.113, +0.533] | +0.109 [−0.386, +0.530] |

`DERIVED` Interception rate is the one quantity where within-season and
across-season evidence agree that the signal is weak, and the across-season
evidence is if anything worse. **Interception rate should be modelled as
league-rate-plus-small-adjustment, and any INT-heavy market should be treated as
near-unforecastable from QB identity.** With k ≈ 682 throws and ~34 throws per
game, `DERIVED` a QB needs roughly 20 games before his own INT rate outweighs
the league rate 50/50 — and that estimate is itself only weakly separated from
zero.

`DERIVED` Sack rate is the mirror image: it is the *most* year-over-year-stable
rate measured (+0.725, +0.571, +0.423, all intervals excluding zero) while its
within-season split-half is a middling 0.399. The reason is visible in §5.5 —
sack rate is substantially an offensive-line/team property that persists across
a season and across seasons, which the within-season split does not reward
because both halves share it. **Sack rate is stable but it is not purely a QB
statistic**, and modelling it as a QB rate assigns team credit to the player.

`VERIFIED` Leave-one-QB-out ranges of the odd-even r (`null_check.py`) confirm
no single QB drives any headline: INT full 0.523 → LOO [0.455, 0.582];
pass-TD 0.548 → [0.473, 0.597]; completion% 0.356 → [0.236, 0.393];
sack rate 0.400 → [0.369, 0.515]; CPOE 0.567 → [0.527, 0.588];
aDOT 0.511 → [0.354, 0.539]. `DERIVED` The instability is in the partition, not
in an outlier player.

### 5.4 The MLB shrinkage method does not transfer uniformly

`VERIFIED` DerSimonian–Laird applied exactly as at `v7/rates.py:220`
(`τ² = (Q − (m−1)μ(1−μ)) / (N − Σn²/N)`, `k = μ(1−μ)/τ² − 1`) to 2024 season
totals, QBs with denominator ≥150 (`null_check.py`):

| Rate | Den. | QBs | μ | τ² | sd_between | k (DL) | k (split-half) |
|---|---|---|---|---|---|---|---|
| completion % | throws | 43 | 0.6582 | 1.18e-03 | 0.0343 | 190 | 248 |
| interception rate | throws | 43 | 0.0217 | 2.34e-05 | 0.0048 | 908 | 682 |
| pass-TD rate | throws | 43 | 0.0465 | 9.32e-05 | 0.0097 | 475 | 261 |
| sack rate | dropbacks | 44 | 0.0646 | 3.00e-04 | 0.0173 | 200 | 308 |
| scramble rate | dropbacks | 44 | 0.0527 | 7.29e-04 | 0.0270 | 67 | 101 |
| pressure-allowed | dropbacks | 44 | 0.3079 | 1.49e-03 | 0.0386 | 142 | 336 |
| int-worthy (FTN) | throws | 43 | 0.0331 | 6.34e-05 | 0.0080 | 504 | 524 |
| play-action rate | dropbacks | 44 | 0.2267 | 1.97e-03 | 0.0444 | 88 | 204 |
| throwaway rate | throws | 43 | 0.0394 | 2.33e-04 | 0.0153 | 161 | 276 |
| **blitz-faced (FTN≥1)** | dropbacks | 44 | 0.2867 | 1.02e-03 | 0.0319 | **200** | **10,221** |

`VERIFIED` The reason, measured directly: within-QB game-level dispersion
relative to binomial (`overdisp.py`, φ = pooled Pearson χ² / dof, QBs with
denominator ≥ 150):

| Rate | φ | Reading |
|---|---|---|
| interception rate | 1.008 | binomial |
| throwaway rate | 1.039 | binomial |
| scramble rate | 1.046 | binomial |
| sack rate | 1.076 | binomial |
| completion % | 1.142 | binomial |
| pass-TD rate | 0.901 | binomial |
| int-worthy (FTN) | 0.955 | binomial |
| screen rate | 1.352 | mild |
| pressure-allowed | 1.646 | **strong** |
| play-action rate | 1.686 | **strong** |
| **blitz-faced (FTN≥1)** | **2.691** | **strong** |
| **motion rate** | **3.020** | **strong** |

`DERIVED` DL assumes the within-player trials are i.i.d. binomial. For the
*outcome* rates (completion, INT, TD, sack, scramble, throwaway, int-worthy)
that assumption holds to within 15%, and DL and split-half agree to within a
factor of about two. For the *scheme and opponent* rates the plays are strongly
clustered by game — because the opponent and the game plan change between games
and not within them — so DL reads that clustering as player skill. The blitz
case is the extreme: DL claims a real 3.2-point between-QB spread and k = 200,
while direct replication across game halves finds r = 0.020.

`DERIVED` **Rule for the NFL build: the shrinkage constant must be estimated by
game-level split-half replication over many partitions, not by a beta-binomial
moment estimator on season totals.** Where a moment estimator is used it must
carry a φ correction, and φ must be measured per rate, not assumed. The MLB
implementation at `rates.py:220` is correct for MLB plate appearances and would
be a live defect if copied across without this check.

### 5.5 The environment layer, measured on the same footing

`VERIFIED` Same split-half method applied to teams instead of QBs, 32 teams,
odd-even game split, ~314 dropbacks per half (`env_rel.py`):

| Quantity | Defence (opponent) r | 95% CI | Offence (own team) r | 95% CI |
|---|---|---|---|---|
| blitz rate | +0.704 | [+0.449, +0.852] | +0.305 | [−0.065, +0.619] |
| pressure rate | +0.289 | [−0.074, +0.569] | +0.474 | [+0.233, +0.698] |
| completion % | +0.193 | [−0.158, +0.516] | +0.366 | [+0.036, +0.625] |
| CPOE | +0.213 | [−0.153, +0.540] | +0.423 | [+0.132, +0.683] |
| EPA / dropback | +0.086 | [−0.299, +0.413] | +0.607 | [+0.422, +0.754] |
| **sack rate** | **−0.004** | [−0.324, +0.317] | +0.617 | [+0.439, +0.781] |
| **yards / dropback** | **+0.007** | [−0.320, +0.320] | +0.650 | [+0.454, +0.815] |
| dropbacks / game | +0.278 | [−0.009, +0.551] | +0.531 | [+0.233, +0.749] |

`DERIVED` and stated with care, because n = 32 gives a resolution floor of about
±0.35: **on one season of data, a defence's pass-defence *quality* cannot be
distinguished from noise by this method, while its *scheme* (blitz rate) can.**
This is "we could not resolve it", not "it is zero" — CLAUDE.md rule 8 and
constitution Rule 005's `DEFERRED / UNDERPOWERED` verdict both apply, and the
correct disposition is DEFERRED pending more seasons, not a finding that defence
does not matter.

`DERIVED` The offence-side numbers are confounded by construction: the offence
includes the QB, so "team yards/dropback r = 0.650" is not separable from
"QB yards/dropback r = 0.573" without a cross-classified QB × team model. A QB
who never changed team in 2024 contributes identically to both. Any claim that
attributes this to the line or to the receivers is not supported by this
measurement.

---

## 6. CORE candidates and noise traps

Statuses use `v8/FEATURE_REGISTRY.md` vocabulary. `VERIFIED` **No NFL feature
can be CORE today**, because Rule 024 requires a status above EXPERIMENTAL to
cite the experiment that earned it and no NFL experiment has run. What follows
is a ranking of candidates for EXPERIMENTAL registration, plus the ones that
should be registered REJECTED so they are not re-proposed as untested.

### CORE candidates — propose as EXPERIMENTAL, expect to earn CORE

| Feature | Denominator | Measured r | k | Why |
|---|---|---|---|---|
| designed QB rushes per game | games | +0.911 | 0.7 games | near-deterministic role assignment |
| scramble rate | dropbacks | 0.670 | 101 | most player-stable per-play rate; φ = 1.05 so DL is also valid here |
| yards per dropback | dropbacks | 0.573 | 152 | the efficiency term in §4.1; carries r = 0.13 forward-chained on its own |
| aDOT | throws with air yards | 0.542 | 156 | stable within season *and* +0.607 year-over-year 2023→24 |
| time to throw | throws with TTT | 0.513 | 177 | QB-attributable, and the natural mediator between pressure and sack |
| CPOE | throws with `cp` | 0.456 | 210 | accuracy net of depth; the right skill term, not raw completion% |
| completion % | **throws (not `pass_attempt`)** | 0.425 | 248 | needed for the market, but §4.2 shows it explains 3.5% of season completions |
| sack rate | dropbacks | 0.399 within / **+0.571 YoY** | 308 | the year-over-year evidence is the strongest in the document; must carry a team term |
| dropbacks per game | games | +0.489 | 7.2 games | the opportunity term — highest leverage per §4.4, and belongs jointly to the game layer |

### SECONDARY / context candidates

`DERIVED` play-action rate (0.505), screen rate (0.347), motion rate (0.733)
and blitz rate are **team-scheme** features, not QB features. They are φ-inflated
(1.35–3.02) and must be modelled at the offensive-unit level with a game-clustered
estimator. Registering them on a QB denominator would be a denominator defect.

`DERIVED` `xpass` / `pass_oe` (r = 0.495 per dropback) is a **game-state**
quantity — it is a model output conditioned on down, distance, score and time.
It is a legitimate input to a volume forecast but it is not a QB skill, and it
is derived, so its provenance chain runs through a third-party model whose
version must be pinned.

### Noise traps — propose as REJECTED-for-now, with the measurement attached

| Feature | Evidence | Verdict |
|---|---|---|
| **interception rate as a QB skill** | within-season r 0.212 [−0.168, +0.530]; YoY −0.130 / +0.049 / +0.232, every interval covering zero; k ≈ 682 throws ≈ 20 games | REJECTED as a discriminating feature. Use the league rate with a small, heavily-shrunk adjustment; do not build an INT-rate market edge on it |
| **interception-worthy rate (FTN)** | r 0.259 [−0.126, +0.590], k ≈ 524. Charted judgment is *less* replicable than the outcome it is meant to de-noise | REJECTED for now. The intuition that it is a cleaner signal than actual INTs is not supported here |
| **blitz-faced rate as a QB property** | r 0.020 [−0.302, +0.350], k ≈ 10,221; φ = 2.69 | REJECTED at the player level. It is an opponent property (defence r = +0.704) |
| **5+ rushers faced** | r 0.037 [−0.289, +0.355] | same |
| **charged drop rate** | r 0.008 [−0.418, +0.420], k ≈ 21,738 — the least stable quantity measured | REJECTED at the QB level; belongs to the receiver worker if anywhere |
| **YAC per completion as a QB skill** | within-season r 0.222; YoY +0.371 / +0.233 / +0.109 | REJECTED at the QB level. `VERIFIED` corr(air yards, YAC \| completion) = −0.181 and air yards are 51.4% of completion yards, so YAC is a real half of the outcome — it just is not the QB's |
| **RPO rate** | r 0.180 [−0.172, +0.497] | DEFERRED — only four seasons of FTN exist and one season cannot resolve it |
| **`participation.ngs_air_yards`** | 0 non-null of 45,919 | REJECTED — SOURCE EMPTY, exactly as `umpire` was for MLB Statcast |
| **defence pass-quality adjustment (one season)** | sack rate r −0.004, yards/dropback +0.007, EPA/db +0.086, all inside a ±0.35 null band at n=32 | DEFERRED / UNDERPOWERED, not rejected. One season cannot resolve it; do not conclude defence does not matter |

---

## 7. Proposed QB projection structure

`DERIVED` throughout this section. Nothing here is measured; it is a design
that the measurements above constrain.

### 7.1 Three layers, three different denominators

```
                      ┌─ GAME / ENVIRONMENT LAYER  (not this worker) ──────┐
                      │  team plays · pace · pass-rate-over-expected ·     │
                      │  score-state path · weather · venue                │
                      └───────────────┬───────────────────────────────────┘
                                      │ hands down a DISTRIBUTION over
                                      │ team dropbacks, not a point estimate
                                      ▼
  OPPORTUNITY   D  = QB dropbacks in the game        denominator: the game
                    = team dropbacks x QB dropback share
                       (share from snap_counts / depth_charts, ~1.0 for a
                        healthy starter; the tail is the injury layer)
                                      │
                                      ▼
  SKILL         per-dropback outcome multinomial, all on denominator D:
                    P(sack) · P(scramble) · P(throw)
                and conditional on throw, on denominator "throws":
                    aDOT distribution -> P(complete | air yards)
                    -> YAC distribution | completion, air yards
                    -> P(intercepted | air yards)
                                      │
                                      ▼
  ENVIRONMENT   multiplicative/logit adjustments applied to the SKILL rates:
                    opponent pass-defence      [DEFERRED, underpowered]
                    own offensive line          -> sack and pressure terms
                    receiving corps             -> YAC and drop terms
                    weather                     -> deep-throw and aDOT terms
```

### 7.2 Latent components, with their denominators and shrinkage targets

| Latent | Denominator | Shrink toward | Measured k | Note |
|---|---|---|---|---|
| dropback share of team dropbacks | team dropbacks | 1.0 for a listed starter | not measured here | availability, not skill; owned by the injury layer |
| P(sack \| dropback) | dropbacks | **team-season sack rate**, then league | 308 | must not shrink to league directly — YoY evidence says the team term is real |
| P(scramble \| dropback) | dropbacks | league scramble rate | 101 | most player-specific rate measured |
| aDOT \| throw | throws with air yards | **team-scheme aDOT**, then league | 156 | scheme and player are confounded; the two-stage target is the honest form |
| P(complete \| throw, air yards) | throws with `cp` | the NGS `cp` model, i.e. shrink **CPOE** toward 0 | 210 | shrinking completion% directly re-introduces the depth confound |
| P(intercepted \| throw) | throws | **league rate, hard** | 682 | k ≈ 20 games; treat the player term as near-zero |
| YAC \| completion, air yards | completions | **receiving corps**, then league | 451 (QB level) | do not attribute to the QB |
| time to throw | throws with TTT | league, conditioned on pressure | 177 | mediator, not an output |

`DERIVED` Two shrinkage targets appear repeatedly — **team** and **league** —
and the measurements in §5.5 are why. A single-stage shrink to league gives the
QB credit for his line and his receivers. That is the NFL analogue of the MLB
pooled-bullpen defect: a label that says `bullpen_{team_id}` over a league-wide
pool. Here the risk runs the other way — a player label over a team quantity.

### 7.3 What the QB layer must hand a play simulator

`DERIVED` Per dropback, and per simulated draw, not as a summary:

1. A categorical draw over `{sack, scramble, throw}` with the adjusted rates.
2. On `throw`: an **air-yards value drawn from a distribution**, not a mean.
   `VERIFIED` the empirical air-yards distribution on throws has mean 7.685,
   SD 10.102, skew +1.37, excess-kurtosis-style ratio 5.48, median 5, p95 28,
   p99 42, max 61 (`dist.py`). A Gaussian on this is wrong at the tail, which is
   where a passing-yards over/under lives.
3. Conditional on air yards: completion, interception, or incompletion.
4. On completion: a **YAC value drawn from a distribution**. `VERIFIED` YAC
   given completion has mean 5.301, SD 6.898, skew +2.94, kurtosis ratio 17.43,
   median 3, p95 18, p99 32, max 78. It is the heaviest-tailed component in the
   passing game and cannot be represented by a mean.
5. `VERIFIED` corr(air yards, YAC | completion) = −0.181, and air yards are
   51.4% of completion yards. `DERIVED` The two components must be drawn
   **jointly**, or the game-total variance will be wrong.
6. On sack: a yardage draw. `VERIFIED` mean −6.575, SD 3.805; and
   `VERIFIED` sack yards do **not** enter `passing_yards` (0 of 1,314 sacks
   carry a `passing_yards` value).

`VERIFIED` **The compound approximation is close to adequate for the game
total.** SD of (game passing yards − throws × league mean per throw) = 55.89
against √throws × per-throw SD = 52.72; ratio **1.0600** (555 QB-games with ≥15
dropbacks). `DERIVED` Game-to-game passing-yard dispersion is within 6% of what
independent per-throw draws predict, so the excess variance attributable to
within-game correlation ("hot" games) is about 12% of variance. A compound draw
over per-throw outcomes is a defensible generative structure, and adding a
game-level dispersion term should be an *experiment* with a measurable 6% target,
not an assumption.

`DERIVED` Per `_GROUNDING.md`, **store the full joint draws** — sack/scramble/
throw, air yards, YAC, and the resulting per-play yardage — not nine percentiles.
MLB's percentile storage is what made CRPS, log score and tail calibration
uncomputable, and the passing-yards market lives in exactly the tail that
percentiles destroy.

---

## 8. Falsification — how each component gets shown not to help

`DERIVED`. All metrics frozen here, before any candidate runs, per constitution
Rule 004a. Clustering by **game** and by **team**, per CLAUDE.md rule 9 and the
measured threefold understatement of naive SEs. Every comparison is against
three controls, per Rule 004: league-rate constant, the trivial "prior yards per
game" benchmark of §4.4 row 1, and the candidate.

| Component | Falsification experiment | Metric that decides it | It does NOT help if |
|---|---|---|---|
| **QB efficiency term (yards/dropback, CPOE, aDOT)** | forward-chained weeks 5–18, oracle-volume held fixed at realised dropbacks so only the rate varies | CRPS on game passing yards, game-clustered | CRPS does not beat row 5 of §4.4 (oracle volume × league rate) by more than the block-bootstrap interval |
| **Volume forecast** | replace realised dropbacks with the forecast; compare against realised-dropback oracle and against prior-mean volume | r and CRPS on game passing yards | r does not rise materially above +0.147 correlation with realised dropbacks |
| **Two-stage shrinkage (team then league) for sack rate** | fit both single-stage-to-league and two-stage; score out-of-sample sack counts | log score on per-dropback sacks, clustered by team | two-stage log score does not beat single-stage; if so the team term is not carrying information and the simpler model wins |
| **Interception term** | predeclared TOST against the league-rate-only model with an equivalence margin of ±0.15 in r | log score on per-throw INT, clustered by game | the TOST concludes equivalence — which is the *expected* outcome given r = 0.212 and YoY ≈ 0, and would confirm the REJECTED status |
| **Interception-worthy (FTN) as a de-noised INT signal** | add `is_interception_worthy` rate as a second predictor of next-period INT rate; test its coefficient | incremental log score over prior INT rate alone | the coefficient is not distinguishable from zero — the MLB "swinging-strike adds nothing once K% is known" precedent applies |
| **Joint air-yards × YAC draw vs independent draws** | simulate both; compare the predictive distribution of game passing yards | PIT uniformity and tail calibration at 5% / 95%, plus interval coverage | PIT and tail coverage are indistinguishable — then the −0.181 correlation is not economically material and independence is preferable |
| **Game-level dispersion term** | add a per-game multiplicative dispersion; target is the measured 6% SD excess | interval coverage at 50/80/90/95 and Winkler score | Winkler scores are not minimised away from dispersion = 1.0, exactly the test that contradicted "widen the intervals" on MLB |
| **Opponent pass-defence adjustment** | withhold; score with and without, forward-chained | CRPS, clustered by defence | the comparison returns `DEFERRED / UNDERPOWERED` rather than FAIL — which on one season is the likely honest answer, and must be reported as such |
| **Split-half k values themselves** | re-estimate on 2022, 2023, 2025 independently | overlap of the bootstrap intervals across seasons | the k values do not replicate across seasons, in which case they are not constants and must be refit per season with the refit declared |

`DERIVED` **Power.** `_GROUNDING.md` records that detecting r 0.11 → 0.25 needed
~377 games independent and ~1,131 with MLB's measured clustering. NFL supplies
272 games and about 555 usable QB-games per season. `DERIVED` One season is
therefore **not enough for a confirmatory QB result**, and the honest plan is
either multi-season back-testing with the design frozen first, or forward
capture, with every underpowered comparison returned as `DEFERRED / UNDERPOWERED`
rather than allowed to read as "no improvement".

---

## 9. Things I could not measure, and what would settle them

| Question | Why not measurable here | What would settle it |
|---|---|---|
| Does a defence's pass quality persist? | n = 32 teams, one season, null band ±0.35 | 2022–2025 participation is reachable; the same split-half over four seasons |
| Is QB skill separable from offensive-line and receiver quality? | every 2024 QB-team pair is nearly constant within the season | cross-classified model over multiple seasons using QB and team changes as the identifying variation |
| Does a QB's rate change with age, injury or scheme change? | no aging or injury covariate was joined | `injuries_2024.csv` is cached; `rosters` carries birthdates. Not attempted because it is Worker 1 / injury-layer scope |
| Do the k values replicate across seasons? | only 2024 pbp/participation is cached and I was instructed not to download another season of either | re-run `final_rel.py` on 2022, 2023, 2025 |
| Is the FTN `read_thrown` field usable? | `'0'` on 2,604 dropbacks is a sentinel; the remaining categories (`1`, `2`, `CHK`, `DES`, `SD`) were not validated | a codebook, or an owner/other-agent lookup of the FTN definitions |
| What does the market actually settle "passing yards" on? | no book data in this container | the other agent holds the Hard Rock Bet connector; the sack-yards question in §3.6 is the concrete ask |

`DERIVED` Per CLAUDE.md's "not blocked — assigned" rule, none of the above is
blocked; three of them are simply another agent's or another worker's to run,
and the last two belong in `docs/AGENT_OUTBOX.md` if the lead wants them chased.

---

## 10. Summary in plain language

The QB layer can measure how a quarterback throws — how deep, how accurately for
that depth, how fast, how often he scrambles or takes a sack — and those
measurements replicate well enough within one season to be worth carrying, with
measured shrinkage constants between roughly 100 and 350 attempts.

What it cannot do is turn that into a good forecast of a game, because the thing
that decides a QB's box score is how many times he drops back, and his own past
barely predicts that. Knowing the rate is worth about r = 0.13; knowing the
count is worth about r = 0.62.

Two commonly-used numbers do not survive measurement. Interception rate looks
stable within a season under one convenient split and is not stable under any
other, and does not carry across seasons at all. Everything about how a QB is
defended — blitz rates, pressure faced — belongs to the opponent, not to him.

And the shrinkage recipe that works for MLB batters does not transfer as-is:
NFL plays cluster inside games far more than plate appearances cluster inside
games, so the moment estimator credits opponents and game plans to players. The
constants have to come from replication across games, measured over many random
partitions, and reported with the interval — which for one season is wide enough
that most of this document's numbers are candidates for experiment, not
conclusions.
