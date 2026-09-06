# W5 — Team and game environment

**Worker:** 5 (team / game environment layer)
**Date:** 2026-09-06
**Scope:** research only. No production model code was written. All measurement
scripts live in the session scratchpad and are evidence, not deliverables.
**Labelling:** every substantive claim carries `VERIFIED`, `DERIVED`, or
`UNVERIFIED-RECALL`, per `nfl/research/_GROUNDING.md`.

---

## 0. Data frame and how to reproduce

`VERIFIED` — Source is the shared cache described in the brief.
`pbp2024.csv` = nflverse `play_by_play_2024.csv`, 372 columns;
`schedules_games.csv` = nflverse `games.csv` (all seasons 1999–2026, 7,548 rows).

```
python3.12 -c "
import pandas as pd
p=pd.read_csv('pbp2024.csv',low_memory=False)
print(len(p), p[p.season_type=='REG'].game_id.nunique())"
# -> 49492 rows total, 272 REG games
```

`VERIFIED` — 2024 regular season: **272 games, 47,274 pbp rows, 544 team-games,
32 teams × 17 games each** (`w5_load.py`, `w5_s3.py`). This **confirms** the
`UNVERIFIED-RECALL` figure of ~272 regular-season games carried in
`_GROUNDING.md`; it is now measured.

`VERIFIED` — Schedule file covers seasons 1999–2026 (`w5_s6.py`), so multi-season
pooling is available without a further download. Every pooled figure below is
labelled with its season range.

`DERIVED` — Sample-size consequence, stated up front because it governs
everything else in this document. One NFL season = 272 games / 544 team-games.
`_GROUNDING.md` records that detecting r 0.11 → 0.25 needs ~377 games
independent and ~1,131 at MLB's measured threefold clustering. NFL team-games
within a game are strongly coupled (§3, §6), so a team-game is **not** an
independent observation. **A confirmatory NFL claim at team-total level needs
multiple seasons, not one.** Every number in this document from 2024 alone is
therefore descriptive, and §4 shows a concrete case where one season resolves
nothing.

---

## 1. The measured distributions — what the volume layer is actually made of

`VERIFIED` — All from `w5_s1.py` / `w5_s2.py`, 2024 REG.

| Quantity | Unit | n | Mean | SD | 5th–95th pct |
|---|---|---|---|---|---|
| Points | team-game | 544 | **22.912** | **9.795** | 7 – 40.85 |
| Points | game total | 272 | **45.824** | **13.113** | — |
| Drives | team-game | 544 | **10.800** | **1.659** | 8 – 14 |
| Drives | game | 272 | 21.599 | 3.198 | — |
| Offensive plays (pass\|rush, no kneel/spike/2pt) | team-game | 544 | **64.035** | **8.681** | 50.2 – 78 |
| Offensive plays (incl. kneel/spike/2pt) | team-game | 544 | 64.283 | 8.708 | — |
| Points per drive | drive | 5,875 | **2.059** | 2.852 | — |
| Points per drive | team-game | 544 | 2.101 | 0.957 | — |
| Neutral seconds per play | team-game | 490 | **32.702** | **3.090** | 27.3 – 37.6 |
| Neutral pass rate (early down) | team-game | 490 | **0.5167** | **0.1074** | 0.333 – 0.688 |
| Plays per drive | drive | 5,875 | 5.960 | 3.460 | — |
| Drive start field position (yards to opp. end zone) | drive | 5,627 | 70.084 | 14.971 | — |

Definitions actually used, because each one changes the number:

- `VERIFIED` **Drive** = distinct `fixed_drive` within a `game_id`, attributed to
  the `posteam` on its first row. 5,875 drives; outcomes:
  Punt 2,036 · Touchdown 1,331 · Field goal 937 · Turnover 579 ·
  End of half 435 · Turnover on downs 311 · Missed FG 175 · Opp TD 56 · Safety 15.
- `VERIFIED` **Offensive play** = `pass==1 or rush==1`, excluding `qb_kneel`,
  `qb_spike`, `two_point_attempt`, `aborted_play`. (nflfastR's `pass==1`
  includes sacks.)
- `VERIFIED` **Seconds per play** = `game_seconds_remaining` of the previous snap
  minus that of the current snap, for consecutive snaps **inside the same drive
  and same quarter**, kept when `0 < delta <= 60`. 28,522 usable pairs; mean
  29.295, median 36.0. **Neutral** adds: quarters 1–3, `|score_differential| <= 8`
  on the prior play, `half_seconds_remaining > 120`, prior down ≤ 3 →
  13,646 pairs, mean **32.549**.
  `DERIVED` — this definition drops drive-opening snaps and cross-quarter pairs,
  and the 60-second truncation removes clock stoppages, so it is a *within-drive
  tempo* measure, not "game seconds ÷ plays". Any comparison to a published pace
  figure must restate the definition before it means anything.
- `VERIFIED` **Neutral pass rate** = share of `pass==1` among offensive plays on
  downs 1–2, quarters 1–3, `|score_differential| <= 7`,
  `half_seconds_remaining > 120`. 12,747 plays, league value **0.5178**.
  Unconditional pass rate over all offensive plays is **0.6130** — the 9-point
  gap is game script, not team preference (§3).
- `VERIFIED` **Points per drive** = per-drive sum of
  `posteam_score_post − posteam_score`. League 2.059 offensive points/drive;
  defensive/return points add 0.063 per drive.
  Sanity: 10.80 drives × 2.059 = 22.24 vs the schedule's 22.91 points per
  team-game — the 0.68 gap is return and special-teams scoring, which the drive
  accounting correctly excludes.
- `VERIFIED` Overtime: 16 of 272 games (5.9%). Team-games in OT games average
  **71.00** offensive plays vs **63.60** in non-OT games.

### 1a. The SD ratio ceiling for NFL team totals

MLB's fatal weakness is `sd_pred/sd_actual = 0.1804` with `r = 0.1101`
(`CLAUDE.md`). The right way to ask the NFL question is through the identity
Rule 005 names.

`VERIFIED` — the identity holds numerically to 4 dp in this data (`w5_boot.py`):

```
slope = r × sd_actual / sd_predicted
  OOS team points     r 0.3389  ratio 0.3318  slope(fit) 1.0213  r·sa/sp 1.0213
  book implied total  r 0.4298  ratio 0.3586  slope(fit) 1.1984  r·sa/sp 1.1984
```

`DERIVED` — **Setting slope = 1 gives `sd_pred/sd_act = r` exactly.** So for any
forecaster that is calibrated in the regression sense, the SD ratio *is* its
correlation. "Raise the SD ratio" and "raise r" are the same instruction, and a
SD ratio raised without r is the `DISPERSION_WITHOUT_SIGNAL` failure that
`sportsplatform/governance/scorecard.py` refuses. MLB's 0.1804 against r = 0.1101 is not a
ceiling statement at all — it is a slope of 0.61, i.e. *over*-dispersed relative
to its own signal.

Two independent estimates of where the NFL ceiling sits:

**(a) Market benchmark.** `VERIFIED` (`w5_boot.py`, game-clustered bootstrap,
B = 2000, seed 20240906). This uses the quarantined market columns **as an
external comparison only** — never as a model input (§6c), which is exactly the
use `CLAUDE.md` rule 1 and constitution Rule 004 permit.

| Target (2024 REG) | n | r | 95% CI (game-clustered) | SD ratio | slope |
|---|---|---|---|---|---|
| Book implied **team total** vs team points | 544 | **0.4298** | [0.3572, 0.5007] | 0.3586 | 1.198 |
| Book `total_line` vs **game total** | 272 | **0.3052** | [0.1920, 0.4167] | 0.3067 | 0.995 |
| Book `spread_line` vs **margin** | 272 | **0.5012** | [0.4075, 0.5885] | 0.3853 | 1.301 |

**(b) Variance decomposition.** `VERIFIED` (`w5_s3.py`) — shrinkage-adjusted
between-team SD of team points scored = 3.987, of team points allowed = 2.026,
against a team-game SD of 9.795. `DERIVED` — if offence and defence ratings were
known perfectly and were independent, ceiling `sd_pred = sqrt(3.987² + 2.026²)
= 4.472`, i.e. SD ratio **0.457**.

`DERIVED` — **The honest statement.** For a *calibrated* NFL team-total
forecast, a plausible SD ratio is **0.34 to 0.46**, and the same number is its
correlation with outcomes. The two estimates agree for team totals. They
**disagree for game totals**: the decomposition implies ≈0.48 while the market
achieves 0.31. I trust the market benchmark, because it is an out-of-sample
measurement and the decomposition depends on an independence assumption between
the offence and defence components that I did not test. Recorded as a
disagreement rather than averaged away.

`DERIVED` — **The single most important number in this section:** NFL's plausible
team-total ceiling (~0.40) is roughly **3.5× MLB's realised 0.18, and ~4× MLB's
realised r of 0.11**. The between-game spread NFL offers is genuinely larger.
That is an argument for the *sport*, not for any model — nothing here shows a
model reaching it.

`VERIFIED` — **Game totals are the hardest of the three targets, not the
easiest.** The market itself gets only r = 0.305 [0.192, 0.417] on game totals
while getting 0.501 on margin. A design that treats "predict the game total" as
the natural first target picks the weakest available signal.

---

## 2. Team-level stability — what a team layer may legitimately carry

Two independent measurements, because split-half over a season and
forward-chained out-of-sample answer different questions and disagree in an
informative way.

### 2a. Split-half reliability across the 32 teams

`VERIFIED` (`w5_s3.py`) — each team's 17 games ordered by week, split odd/even
game index (8 vs 9 games), team means correlated across the 32 teams.
`SB` = Spearman-Brown 2r/(1+r), the implied full-season reliability. CI is
Fisher-z on n = 32 and is **wide by construction** — 32 is a small n and this is
the honest cost of a league with 32 teams.

| Trait | split-half r | 95% CI | Spearman-Brown | ICC (shrunk) |
|---|---|---|---|---|
| Points scored per game | **0.714** | [0.487, 0.851] | 0.833 | 0.166 |
| Points per drive | **0.722** | [0.499, 0.855] | 0.839 | 0.177 |
| Drive score rate (TD or FG) | **0.558** | [0.259, 0.759] | 0.716 | 0.134 |
| Neutral pass rate | **0.532** | [0.225, 0.743] | 0.695 | 0.116 |
| Points allowed per game | 0.408 | [0.069, 0.662] | 0.579 | — |
| Neutral seconds per play (pace) | 0.410 | [0.071, 0.664] | 0.581 | 0.060 |
| First downs per drive | 0.364 | [0.018, 0.632] | 0.534 | — |
| Offensive plays per game | **0.220** | [−0.139, 0.528] | 0.361 | **0.000** |
| **Drives per team-game** | **0.001** | [−0.347, 0.350] | 0.003 | 0.027 |

### 2b. Forward-chained out-of-sample, weeks 8–18

`VERIFIED` (`w5_s9.py`) — for each week w ≥ 8, team ratings are built from
**weeks < w only**, shrunk toward the league mean with a fixed prior weight
K = 8 games, and used to predict that week's team-game. No future information,
no market input. n = 330 team-games.

| Target ← predictor (own team, prior weeks) | r | SD ratio | slope | RMSE | RMSE (league mean) |
|---|---|---|---|---|---|
| Pass share ← prior pass share | **0.366** | 0.280 | 1.31 | 0.0962 | 0.1028 |
| Points ← prior points scored | 0.335 | 0.265 | 1.26 | 9.301 | 9.838 |
| Points per drive ← prior pts/drive | 0.338 | 0.275 | 1.23 | 0.911 | 0.964 |
| Pass share ← prior *neutral* pass rate | 0.301 | 0.252 | 1.20 | 0.0982 | 0.1028 |
| Neutral pass rate ← prior neutral pass rate | 0.276 | 0.249 | 1.11 | 0.1010 | 0.1051 |
| Pass attempts ← prior pass attempts | 0.249 | 0.258 | 0.97 | 8.386 | 8.648 |
| Neutral sec/play ← prior neutral sec/play | 0.120 | 0.250 | 0.48 | 3.057 | 3.052 |
| **Drives ← prior drives** | **0.065** | 0.190 | 0.34 | 1.726 | **1.715 (worse)** |
| **Offensive plays ← prior plays** | **0.002** | 0.178 | 0.011 | 8.938 | **8.796 (worse)** |
| **Offensive plays ← prior pace** | **−0.099** | 0.086 | −1.15 | 8.911 | **8.796 (worse)** |

With an opponent term added (own offence + opponent defence, same shrinkage):

| Target | r | SD ratio | slope | RMSE |
|---|---|---|---|---|
| Team points ← own PF + opp PA | **0.341** | 0.331 | **1.029** | 9.256 |
| Pass share ← own + opponent | 0.250 | 0.363 | 0.689 | 0.100 |
| Offensive plays ← own + opponent | −0.005 | 0.255 | −0.019 | 9.095 (worse than mean) |

`VERIFIED` (`w5_s4.py`, `w5_boot.py`) — the same team-strength model, scored at
three levels, with game-clustered bootstrap CIs (B = 2000, seed 20240906):

| Target | n | r | 95% CI | SD ratio | slope |
|---|---|---|---|---|---|
| Team points | 330 | **0.3389** | [0.2441, 0.4252] | 0.3318 | **1.021** |
| Game total | 165 | 0.1271 | **[−0.0216, 0.2688]** | 0.2684 | 0.474 |
| Margin | 165 | **0.4861** | [0.3765, 0.5878] | 0.3842 | 1.265 |

### 2c. What this establishes

`DERIVED` — **Volume is not a team trait. Mix and efficiency are.**

1. **Drives per team-game carries essentially zero team signal.** Split-half
   r = 0.001; out-of-sample it is *worse than predicting the league mean*. A
   "drives" term in a team layer would be fitting noise.
2. **Offensive plays per game is barely better** (split-half 0.220, shrunk ICC
   0.000, OOS r = 0.002 and worse RMSE than the mean). This is the finding most
   likely to be assumed away, because "fast teams run more plays" is intuitive
   and *false in this data*: predicting a team's play count from its own prior
   neutral pace gives **r = −0.099, the wrong sign**.
3. **Pace is a real but weak trait** — split-half 0.410 over a season, but only
   r = 0.120 game-to-game out of sample, and it does not translate into play
   volume.
4. **Neutral pass rate is a real trait** (split-half 0.532; OOS 0.276–0.366 on
   pass share). This is the strongest *behavioural* team signal available.
5. **Points per drive / points scored are the strongest team traits**
   (split-half ≈ 0.72; OOS r ≈ 0.34). Points **allowed** is materially weaker
   (split-half 0.408) — offence stabilises faster than defence. `UNVERIFIED-RECALL`
   that this ordering is a well-known regularity; measured here for 2024 only,
   and it needs multi-season confirmation before it is designed around.
6. **A trivially simple, market-free, leakage-free team-strength model already
   reaches r = 0.339 [0.244, 0.425] on team points with a calibration slope of
   1.021.** `DERIVED` — that is 3× MLB's r = 0.1101 baseline, produced by
   shrunken season-to-date scoring averages and nothing else. The NFL baseline
   bar is therefore **much higher than MLB's**, and the first frozen NFL baseline
   must be at least this strong or it is not a baseline, it is a strawman.

`DERIVED` — Caution required on that r = 0.339. K = 8 was chosen from a grid
[2, 4, 6, 8, 12, 16, 24] **after** seeing the results, which is exactly the
Rule 004a defect. The grid shows why it barely matters for r and matters
enormously for the other two members of the linked triple (`w5_s4.py`):

| K | r | SD ratio | slope |
|---|---|---|---|
| 2 | 0.3365 | 0.489 | 0.688 |
| 8 | 0.3389 | 0.332 | 1.021 |
| 24 | 0.3394 | 0.182 | 1.866 |

`DERIVED` — **r is flat at 0.339 across a 2.7× range of SD ratio.** This is
Rule 005 demonstrated live: shrinkage moves dispersion and slope without moving
discrimination at all. Note that K = 24 lands on an SD ratio of **0.182 — MLB's
exact headline number — with three times MLB's r.** Anyone quoting an SD ratio
without r and slope beside it can be handed this table.

---

## 3. Game-script coupling — opportunity is endogenous

This is the largest single effect measured in this document and the one with the
most direct consequence for a player simulator.

### 3a. Pass rate against score differential

`VERIFIED` (`w5_s5.py`) — all offensive plays, 2024 REG.

| Score differential (offence's view) | n | pass rate | Q4 only n | Q4 pass rate |
|---|---|---|---|---|
| ≤ −17 | 2,667 | 0.747 | 1,422 | 0.776 |
| −17 … −11 | 2,612 | 0.745 | 1,022 | **0.878** |
| −11 … −8 | 2,160 | 0.682 | 825 | 0.806 |
| −8 … −4 | 5,633 | 0.639 | 1,205 | 0.725 |
| −4 … −1 | 3,720 | 0.614 | 1,051 | 0.674 |
| tied | 6,327 | 0.587 | 447 | 0.653 |
| +1 … +3 | 2,759 | 0.577 | 751 | 0.499 |
| +3 … +7 | 4,002 | 0.586 | 797 | 0.462 |
| +7 … +10 | 1,686 | 0.521 | 580 | 0.421 |
| +10 … +16 | 1,697 | 0.517 | 561 | 0.392 |
| > +16 | 1,572 | **0.417** | 779 | **0.284** |

`VERIFIED` — **Q4 pass rate spans 0.284 to 0.878 — a 59-percentage-point swing
driven purely by score state.** For comparison, the entire *between-team*
season-long spread in neutral pass rate is 0.421 to 0.638 (32 teams, SD 0.042,
`w5_s2.py`). `DERIVED` — **game script moves pass rate roughly three times as
far as team identity does.**

`VERIFIED` — First half vs second half at the same score differential shows the
interaction is real and not just a score effect: at > +16 the pass rate is 0.675
in H1 and 0.380 in H2; at −17…−11 it is 0.691 in H1 and 0.770 in H2.

`VERIFIED` — Linear probability model on early downs (n = 26,812):

```
pass ~ 1 + score_diff + minutes_remaining + score_diff × minutes_remaining
  const           +0.566354  (se 0.005940, t  95.4)
  score_diff      -0.015198  (se 0.000517, t -29.4)
  minutes_left    -0.000624  (se 0.000175, t  -3.6)
  score_diff×min  +0.000386  (se 0.000022, t +17.2)
```

`DERIVED` — the marginal effect of one point of lead on pass probability is
**+0.0022 with 45 minutes left and −0.0133 with 5 minutes left** — a sign flip
and a 6× magnitude change. `DERIVED` — a simulator that applies a static
team pass rate is not slightly wrong; it is wrong by a factor that swings sign
across the game. Standard errors are naive (plays are clustered inside
team-games); the t-statistics are large enough that the sign and rough magnitude
survive any plausible clustering inflation, but the SEs themselves must not be
quoted.

### 3b. Pace against score differential

`VERIFIED` (`w5_s5.py`) — mean seconds per play by prior-play score state.

| Score diff | Q1–Q3 sec/play | Q4 sec/play |
|---|---|---|
| ≤ −17 | 26.52 | 22.80 |
| −17 … −11 | 28.57 | 20.95 |
| −4 … −1 | 30.86 | 25.38 |
| tied | 32.50 | 26.08 |
| +3 … +7 | 30.01 | 28.68 |
| +10 … +16 | 30.79 | 32.48 |
| > +16 | 31.59 | **35.51** |

`DERIVED` — In Q4 pace spans **20.95 to 35.51 seconds per play, a 14.6-second
range**, against a between-team season-long SD of 0.99 seconds (`w5_s2.py`,
32 teams, range 30.79 KC to 34.42 TB). **Game script moves pace ~15× as far as
team identity does.** In quarters 1–3 the same effect exists but is one third
the size (26.5 to 32.5).

### 3c. What it does to team-game volume

`VERIFIED` (`w5_s5.py`) — 544 team-games, correlation with the team's own final
margin:

| Quantity | corr with final margin |
|---|---|
| Pass attempts | **−0.344** |
| Rush attempts | **+0.544** |
| Pass share | **−0.545** |
| Total offensive plays | +0.100 |
| Drives | −0.023 |

| Game state | n | pass att | rush att | plays | pass share |
|---|---|---|---|---|---|
| Trailing by 8+ | 131 | 42.9 | 19.4 | 62.3 | 0.688 |
| Within 8 | 282 | 39.9 | 24.9 | 64.8 | 0.616 |
| Leading by 8+ | 131 | 34.2 | 29.9 | 64.2 | 0.533 |

`DERIVED` — **The two most consequential facts for a player-prop simulator:**

1. **Total plays barely move with game script (r = +0.100), but the pass/run
   split moves violently.** Between "trailing by 8+" and "leading by 8+" a team
   loses 8.7 pass attempts and gains 10.5 rush attempts while its total play
   count changes by 1.9. Volume is close to conserved; **mix is not.**
2. Therefore the RB and WR opportunity distributions are **anti-correlated
   through the scoreboard**, and the scoreboard is itself an output of the
   scoring model. A simulator that draws pass attempts and rush attempts from
   independent team-level distributions will reproduce the marginals and get the
   joint badly wrong — and joint structure is precisely what a prop book prices.
   This is the strongest argument in this document for simulating the game
   sequentially rather than sampling team volumes directly.

### 3d. Within-game coupling

`VERIFIED` (`w5_s8.py`, `w5_s1.py`):

| Pair | corr |
|---|---|
| home drives vs away drives (per game) | **+0.851** |
| home plays vs away plays (per game) | **−0.513** |
| home neutral sec/play vs away | −0.009 |
| home score vs away score, 2024 | −0.098 |
| home score vs away score, 2015–2024 (n = 2,623) | −0.025 |

`VERIFIED` — the two teams' drive counts differ by 0 in 107 games and by 1 in 98
of 223 measurable games; within-game between-team SD of drives is **0.429**
against a game-level SD of **3.198**.

`DERIVED` — **Drives are a game-level quantity, not a team-level one.** The
possession count is set by the game (its clock, its scoring pattern, its
turnovers) and then split almost exactly in half. The environment layer should
model **total game drives once** and allocate, rather than model two team drive
counts and hope they agree. Plays, by contrast, are genuinely zero-sum
(r = −0.513): one team's clock consumption is the other's loss.

`VERIFIED` — Team scores are close to uncorrelated within a game
(−0.098 in 2024; −0.025 pooled over 10 seasons, n = 2,623). `DERIVED` — this
does **not** license independent team-score draws: the near-zero total is a net
of a positive pace/environment component and a negative game-script component,
which §3a–3c show are both large. Independent draws would reproduce this one
correlation and misprice every conditional.

---

## 4. Home field and rest — a case where one season resolves nothing

### 4a. Home field, 2024 alone

`VERIFIED` (`w5_s6.py`), 2024 REG, 272 games, of which **5 were at neutral
sites** (`location != 'Home'`):

| Statistic | Value |
|---|---|
| Home − away margin, all 272 | +1.868 (SD 14.458, SE 0.877), 95% CI **[+0.149, +3.586]**, t = 2.13 |
| Home − away margin, 267 true-home | +1.719 (SE 0.889), 95% CI **[−0.023, +3.461]** |
| Home points | 23.846 |
| Away points | 21.978 |
| Home win rate | 0.5331 (0 ties), SE 0.0303, 95% CI **[0.474, 0.592]** |

`DERIVED` — **2024 alone cannot resolve home-field advantage.** Dropping 5
neutral-site games moves the interval across zero. The win-rate interval spans
0.474 to 0.592 and contains 0.500. This is exactly the shape of the MLB
home-field artefact recorded in `CLAUDE.md` ("This split cannot distinguish
anything and must not be used as a finding"), and it must not be repeated here:
**a single NFL season is not enough to estimate home field.**

### 4b. Home field pooled

`VERIFIED` (`w5_s6.py`), REG, true-home games only:

| Season | n | home − away margin | SE | home win rate |
|---|---|---|---|---|
| 2015 | 253 | +1.482 | 0.882 | 0.538 |
| 2016 | 252 | +2.595 | 0.816 | 0.575 |
| 2017 | 251 | +2.502 | 0.899 | 0.570 |
| 2018 | 253 | +2.344 | 0.902 | 0.601 |
| 2019 | 251 | −0.048 | 0.938 | 0.518 |
| 2020 | 253 | +0.138 | 0.899 | 0.502 |
| 2021 | 269 | +1.565 | 0.938 | 0.509 |
| 2022 | 265 | +2.125 | 0.757 | 0.562 |
| 2023 | 267 | +2.712 | 0.888 | 0.558 |
| 2024 | 267 | +1.719 | 0.889 | 0.524 |
| **Pooled 2015–2024** | **2,581** | **+1.720** | **0.279** | 95% CI **[+1.173, +2.267]**, win rate **0.5455** |

`VERIFIED` — margin SD pooled = 14.181. `DERIVED` — n for 80% power at α = 0.05
on a true 1.0-point effect is (2.8 × 14.181 / 1.0)² ≈ **1,577 games ≈ 5.8
seasons**; on a 2.0-point effect, ≈ **394 games ≈ 1.4 seasons**.

`DERIVED` — **The honest statement on home field:** pooled over ten seasons it is
real and about **+1.7 points [+1.2, +2.3]**. Any single season is underpowered
for it. Note also 2019 (−0.05) and 2020 (+0.14) — the effect is not stationary,
so pooling is itself a modelling assumption that has to be declared, not a free
lunch. **A home-field term must be estimated from a stated multi-season window
with the window written into the experiment ticket, never fitted on the
evaluation season.**

### 4c. Rest and travel

`VERIFIED` (`w5_s6.py`) — `home_rest` / `away_rest` are present in the schedule
release. 2024 distribution of home rest: 4 days ×19, 6 ×22, 7 ×177, 8 ×21,
10 ×14, 13 ×2, 14 ×12, plus singletons. Rest differential is 0 in **169 of 272
games**; the tails are ±7 and ±8 (Thursday and post-bye).

| Model | const | rest_diff coef | SE | t |
|---|---|---|---|---|
| 2024, margin ~ rest_diff | +1.903 (0.880) | +0.198 | 0.348 | 0.57 |
| 2015–2024 (n = 2,581) | +1.732 (0.279) | +0.137 | 0.113 | 1.21 |

`DERIVED` — **No resolvable rest effect, even pooled over ten seasons.** The
point estimate (+0.14 points per day of rest advantage) is small and its
interval comfortably contains zero. A rest term is not currently earned. What is
worth carrying is the *variable itself* as a `DESCRIPTIVE` covariate so the
question can be re-asked with more data, and because short-week status plausibly
interacts with the injury layer (W7) even if it does not move points directly.

`VERIFIED` — Travel: the schedule carries `location`, `stadium_id` (34 distinct
in 2024), `stadium`, `gameday`, `weekday`, `gametime`, `div_game`. 2024 weekdays:
Sunday 221, Monday 21, Thursday 19, Saturday 7, Friday 2, Wednesday 2. Kickoff
times: 13:00 ×135, 16:25 ×41, 20:15 ×33, 16:05 ×26, 20:20 ×20, 16:30 ×5.
`div_game` = 1 in 96 of 272.

`DERIVED` — Distance and time-zone crossing are **not** present as fields and
would have to be constructed from stadium coordinates, which are not in this
release. `UNVERIFIED-RECALL` that stadium latitude/longitude are obtainable from
public sources; **this is an assignment for the networked agent**, not a blocker,
and per `docs/AGENT_PROTOCOL.md` DEC-029 it is "not blocked — assigned". It
should not be built as a lookup table of coordinates typed from memory —
`CLAUDE.md` rule 3 forbids exactly that.

---

## 5. Weather, roof, surface — what is present, and what it supports

### 5a. What is actually in the data

`VERIFIED` (`w5_s7.py`), 2024 REG:

| Field | Coverage |
|---|---|
| `roof` | outdoors 178, dome 51, closed 43. No missing. |
| `surface` | grass 143, fieldturf 68, matrixturf 26, sportturf 17, a_turf 8, astroturf 8, **2 missing** |
| `temp` | **173 of 178 outdoor games; 0 of 94 dome/closed** |
| `wind` | identical coverage to `temp` |
| pbp `weather` | free-text string, non-null for **257 of 272** games, e.g. `"Cloudy Temp: 75° F, Humidity: 64%, Wind: C 13 mph"` — carries **humidity**, which the schedule's numeric fields do not |

`VERIFIED` — outdoor games with weather: temp mean 59.9, SD 17.2, range 14–93;
wind mean 7.9, SD 4.0, range 0–20.

`DERIVED` — **The missingness is structural, not random.** `temp` and `wind` are
`NaN` for every dome and closed-roof game. Under `v8/V8_FAILURE_TAXONOMY.md`
Class A, imputing a league-mean temperature into a dome is "absence read as
success" and would silently create a fake covariate. Roof state must be a
declared branch, and the weather block must be **structurally absent** for
indoor games, not filled.

### 5b. What can be measured

`VERIFIED` (`w5_s7.py`), 2024 REG, game total points:

| Split | n | mean total | SE |
|---|---|---|---|
| roof = closed | 43 | 46.256 | 1.865 |
| roof = dome | 51 | 47.902 | 2.074 |
| roof = outdoors | 178 | 45.124 | 0.960 |

| Outdoor bucket | n | mean total | SE |
|---|---|---|---|
| temp ≤ 32 | 13 | 47.00 | 4.00 |
| 32–45 | 22 | 43.09 | 2.17 |
| 45–60 | 50 | 44.86 | 1.95 |
| 60–75 | 51 | 44.35 | 1.71 |
| > 75 | 37 | 45.78 | 2.14 |
| wind 0–4 | 37 | 43.86 | 2.21 |
| wind 5–9 | 80 | 45.92 | 1.51 |
| wind 10–14 | 41 | 44.07 | 1.69 |
| wind ≥ 15 | 15 | 43.60 | 2.98 |

`VERIFIED` — 2024 regressions on outdoor games (n = 173):
`total ~ temp` slope **+0.0130 (SE 0.0563, t = 0.23)**, r = 0.018;
`total ~ wind` slope **−0.0462 (SE 0.2394, t = −0.19)**, r = −0.015.

`VERIFIED` — pooled 2015–2024 outdoor games (n = 1,723):
`total ~ temp` slope **+0.0471 (SE 0.0192, t = 2.45)** → +0.47 points per 10 °F;
`total ~ wind` slope **−0.2627 (SE 0.0627, t = −4.19)** → **−2.63 points per
10 mph**.
Pooled roof means: outdoors 44.517 (n = 1,842), closed 46.950 (343),
dome 48.702 (386), open 49.019 (52).

`DERIVED` — **2024 alone resolves nothing about weather** (both t-statistics
below 0.25). Pooled over ten seasons, wind is the one weather variable with a
clearly resolvable relationship to scoring; temperature is marginal. `CLAUDE.md`
records the MLB weather layer as a cautionary case, and the mechanism of the
caution is visible here: a one-season fit would have produced a coefficient of
approximately zero with the wrong sign on wind, and any adjustment built from it
would have been noise carrying a decimal point.

`DERIVED` — **No hardcoded adjustment is proposed, and none should be.** Under
`CLAUDE.md` rule 3, a wind coefficient may enter only as a fitted parameter with
its estimation window, sample size, standard error and refit date recorded in
the input manifest, refit on a declared schedule, and never on the evaluation
window. The roof/dome gap (+3.5 to +4.2 points pooled) is **confounded** with
which franchises play indoors and with climate, and I did not decompose it; it
must not be read as a causal roof effect.

`DERIVED` — **Leakage warning on the weather fields themselves.** `temp` and
`wind` in this release are the conditions **observed at the game**, not a
forecast made before it. Using them directly in a historical backtest is a Rule
003 violation of exactly the "looks superb" kind: a live system at prediction
time has only a forecast, which is noisier. Either the environment layer takes a
captured forecast vintage (a live-capture assignment, like the injury vintages
in `_GROUNDING.md`), or realised weather is used **only** for descriptive
post-hoc analysis and is quarantined from any feature that scores a prediction.

---

## 6. Proposed environment layer

Everything below is a **proposal for experiments**, not a design commitment. Per
`v8/FEATURE_REGISTRY.md` every component starts at `EXPERIMENTAL` or lower
because no NFL experiment has run.

### 6a. What it estimates, and at which grain

The measurements dictate the grain — this is the part of the proposal that is
`DERIVED` rather than chosen.

| Component | Grain | Status | Because |
|---|---|---|---|
| **Total game drives** | **Game**, not team | `EXPERIMENTAL` | corr(home drives, away drives) = +0.851; within-game between-team SD 0.429 vs game SD 3.198 (§3d) |
| **Team offensive strength** (points per drive) | Team, opponent-adjusted | `EXPERIMENTAL` | split-half 0.722; OOS r 0.338 (§2) |
| **Team defensive strength** (pts/drive allowed) | Team, opponent-adjusted | `EXPERIMENTAL` | split-half 0.408 — real but weaker; must not be given equal weight to offence by assumption |
| **Neutral pass tendency** | Team | `EXPERIMENTAL` | split-half 0.532; OOS r 0.301–0.366 (§2) |
| **Neutral pace** | Team | `EXPERIMENTAL` | split-half 0.410 but OOS game-to-game only 0.120; weakest of the surviving traits |
| **Game-script response functions** (pass rate and pace as functions of score differential × time) | **League**, not team | `EXPERIMENTAL` | effects are 3× (pass) and 15× (pace) the between-team spread (§3a–3b); team-specific script response is not identified at 17 games/team and should not be attempted first |
| **Home field** | League constant, multi-season window | `EXPERIMENTAL` | +1.72 [1.17, 2.27] pooled; single season underpowered (§4) |
| **Wind** (outdoor branch only) | League coefficient, multi-season, refit-dated | `EXPERIMENTAL` | pooled t = −4.19; 2024 t = −0.19 (§5) |
| **Temperature** | outdoor branch | `DESCRIPTIVE` initially | pooled t = 2.45, marginal |
| **Roof / surface** | branch flag | `DESCRIPTIVE` | means differ but are confounded with franchise and climate (§5b) |
| **Rest / short week / bye** | Team | `DESCRIPTIVE` | no resolvable effect on margin even pooled (§4c); carried so the question can be re-asked |
| **Travel distance / time zones** | Team | `BLOCKED → assigned` | stadium coordinates are not in this release; assignment for the networked agent, written to `docs/AGENT_OUTBOX.md` (§4c) |
| **Drives per team-game as a team trait** | — | **`REJECTED`** | split-half r = 0.001; OOS worse than the league mean (§2c) |
| **Plays per team-game as a team trait** | — | **`REJECTED`** | split-half 0.220, shrunk ICC 0.000, OOS r = 0.002 and worse than the mean; pace→plays has the wrong sign (r = −0.099) |

`DERIVED` — the two REJECTED rows are the most useful output of this worker.
They are recorded so they are not re-proposed as untested, which is exactly what
the REJECTED status exists for.

### 6b. What it hands downstream

`DERIVED` — the handoff must be a **sequential state generator, not a vector of
team volumes**, because §3c shows total plays are nearly conserved while the
pass/run split swings by 15 percentage points with game state. Concretely the
environment layer should hand the drive/play model:

1. A **game-level drive count** and the alternation of possession, plus drive
   start field position. Substrate measured (`w5_s8.py`, corrected to the first
   offensive snap of each drive): drive start mean 70.08 yards from the opponent
   end zone, SD 14.97; start transitions KICKOFF 2,799 (mean start 70.1, score
   rate 0.375), PUNT 1,998 (76.7, 0.347), INTERCEPTION 351 (56.6, 0.499),
   DOWNS 297 (61.9, 0.407), FUMBLE 224 (51.1, 0.598), MISSED_FG 152 (62.0, 0.461).
   Score rate by start position: ≤25 yards out 0.922 (TD 0.600), 25–50 0.635,
   50–65 0.497, 65–75 0.389, 75–85 0.308, 85–100 0.266.
2. A **running game state** — score differential, clock, timeouts, field
   position — that is *updated by the simulation*, so that pass rate and pace are
   read off the league response functions at the current state rather than fixed
   at kickoff.
3. **Team offsets** applied to the neutral point of those functions (pass
   tendency offset, pace offset, offensive and defensive efficiency), not to the
   game-state slopes.
4. **Full joint draws retained** — every simulated game's play sequence, not
   percentiles. `_GROUNDING.md` records that MLB's nine stored percentiles
   cannot support CRPS, log score or tail calibration; the correlation structure
   in §3c and §3d is only recoverable from joint draws.

### 6c. Keeping the environment layer free of market inputs

`VERIFIED` (`w5_s8.py` and a direct column read) — the market-derived columns:

- `play_by_play_2024.csv`, 372 columns, **6 market-derived**:
  `vegas_wpa`, `vegas_home_wpa`, `vegas_wp`, `vegas_home_wp`, `spread_line`,
  `total_line`.
- `games.csv` (schedules), **8 market-derived**: `away_moneyline`,
  `home_moneyline`, `spread_line`, `away_spread_odds`, `home_spread_odds`,
  `total_line`, `under_odds`, `over_odds`.

`DERIVED` — Required handling, and the reasoning for each:

1. **Drop at ingest, not at feature selection.** A column that is present in the
   dataframe can be picked up by a wildcard, a `select_dtypes`, or an
   auto-feature step. `_GROUNDING.md` already states the rule; the operational
   form is that the ingest step writes a **market-free frame** and a separate
   **market frame**, with the split asserted by a named error if a market column
   name ever appears in the model frame's schema (the Phase 1 pattern in
   `CLAUDE.md`: assert non-empty and schema-correct, raise a named error
   otherwise).
2. **Two derived columns are also contaminated and are easy to miss.**
   `nflfastR`'s `vegas_wp` / `vegas_wpa` are the spread-informed win-probability
   series, so any feature built on them inherits the line. `wp` / `wpa` (the
   non-`vegas` pair) are model outputs but not market-derived; `xpass` and
   `pass_oe` are likewise model outputs. `UNVERIFIED-RECALL` that `xpass` does
   not consume the spread — **this must be confirmed against the nflfastR model
   definition before `xpass` or `pass_oe` is used**, and until confirmed they are
   treated as contaminated. I used neither in any measurement above; every
   game-script number in §3 is computed from raw `score_differential`,
   `game_seconds_remaining` and `pass`/`rush`.
3. **`result` and `total` in the pbp file are the game outcome**, replicated onto
   every play row. They are not market data but they are pure future information
   inside a play-level frame and must be quarantined on the same pass.
4. **The market is permitted in exactly one place: the scorecard**, as an
   external comparison under constitution Rule 004. §1a uses it that way. Nothing
   in the environment layer may read it, and no environment change may be
   accepted because it moved a number toward a line — `CLAUDE.md` rule 1.
5. **The quarantine needs a test, not a convention.** Class E of the failure
   taxonomy is "guard verified in isolation, call site never exercised". The
   assertion belongs on the path the model frame actually travels, with a replay
   test that feeds it a frame containing `spread_line` and requires the named
   error.

### 6d. Falsification experiment for each component

Each is stated so that a specific measured result kills it. Metrics, splits and
clustering are to be frozen in the ticket **before** the run (Rule 004a); the
clustering scheme for all of them is **by game and by week**, because §3d shows
the two team-games in a game are strongly coupled.

| # | Component | Falsification test | Kill condition |
|---|---|---|---|
| E1 | Game-level drive count | Predict total game drives out of sample from environment features; compare against the league mean | Does not beat the league mean on RMSE with a game-clustered CI excluding zero. **Prior from §2c: expect this to fail**, and the layer should then emit drives as a pure distribution with no per-game conditioning |
| E2 | Team offensive efficiency | Forward-chained team points-per-drive, opponent-adjusted, vs the K = 8 shrunken-mean baseline of §2b (r = 0.338) | No improvement in r with the game-clustered CI on Δr excluding zero. Reported with SD ratio and slope beside it, per Rule 005 |
| E3 | Team defensive efficiency | Same, on points allowed per drive | Same. Note the weak prior measured in §8: a naive opponent-allowed term gives OOS r = 0.062 alone and *reduces* r on points per drive when added (0.338 → 0.321). The kill condition is no improvement in r; a slope improvement alone does not pass |
| E4 | Neutral pass tendency | Forward-chained team pass share vs the prior-pass-share baseline (r = 0.366) | No improvement. A neutral-situation filter that does **not** beat raw prior pass share does not earn its complexity — in §2b it did not (0.301 vs 0.366) |
| E5 | Pace | Forward-chained neutral sec/play, and separately whether pace improves the *play-count* distribution | Kill the play-count use outright unless it beats the mean; the measured OOS relationship is r = −0.099 |
| E6 | Game-script response functions | Simulate full games; compare the **joint** distribution of (team pass attempts, team rush attempts) and its correlation with final margin against the measured −0.344 / +0.544 / −0.545 | Simulated correlations outside a predeclared band around the measured values. This is the test a static-rate simulator fails, and it is the reason for the sequential architecture |
| E7 | Home field | Estimate on a declared window ending before the evaluation season; score on held-out seasons | Interval on the held-out estimate excludes the fitted value, or the term does not improve margin RMSE. Note §4b: the effect is non-stationary (2019 −0.05, 2023 +2.71), so a stability check across windows is part of the test |
| E8 | Wind | Fit on seasons ≤ Y−1, evaluate on Y, outdoor games only, forecast-vintage inputs where available | Coefficient sign flips out of sample, or no RMSE improvement. Must be re-run every season; a wind coefficient with no refit date is a silent constant |
| E9 | Roof / surface | Test as a branch flag after controlling for team identity | Effect vanishes under team controls — the pooled means are confounded (§5b) |
| E10 | Market quarantine | Feed the ingest a frame containing each of the 14 named market columns | Any market column reaches the model frame without a named error |
| E11 | Whole layer | Score the composed environment layer at all three levels — team points, game total, margin — against the §2b baseline **and** the market benchmark of §1a | Failing to beat the no-market baseline of r = 0.339 on team points. Passing the baseline while trailing the market is a `DEFERRED`, not a `FAIL` — and per Rule 006a, a layer that has promoted nothing is not thereby broken |

`DERIVED` — E1 and E5 are written expecting to fail. That is deliberate: they
are the two components a football-literate designer is most likely to assume,
and §2c measures both as absent. Writing them as experiments with an expected
negative result is cheaper than discovering later that a drives model and a pace
model were fitting noise.

---

## 7. Summary of what this worker established

1. `VERIFIED` — 2024 REG is 272 games / 544 team-games. Team points mean 22.912,
   SD 9.795. Drives 10.800 ± 1.659 per team-game. Offensive plays 64.035 ± 8.681.
   Points per drive 2.059. Neutral pace 32.702 s ± 3.090. Neutral pass rate
   0.5167 ± 0.1074.
2. `DERIVED` — At calibration slope 1.0, SD ratio **is** r. A plausible ceiling
   for a calibrated NFL team-total forecast is **0.34–0.46**, against MLB's
   realised 0.18 at slope 0.61. Game totals are the *hardest* target (market
   r = 0.305), margins the easiest (market r = 0.501).
3. `VERIFIED` — A market-free, leakage-free, forward-chained shrunken-average
   team-strength model already reaches **r = 0.339 [0.244, 0.425] with slope
   1.021** on team points — 3× MLB's baseline. The first NFL baseline must clear
   this.
4. `VERIFIED` — **Drives per team-game (split-half r = 0.001) and offensive
   plays per team-game (0.220, OOS r = 0.002) are not team traits.** Points per
   drive (0.722), points (0.714), drive score rate (0.558) and neutral pass rate
   (0.532) are. Pace (0.410) is real over a season but weak game-to-game (OOS
   0.120) and does **not** predict play volume (OOS r = −0.099, wrong sign).
5. `VERIFIED` — Game script dominates team identity: Q4 pass rate spans
   0.284–0.878 by score state against a 0.042 between-team SD; Q4 pace spans
   20.95–35.51 s against a 0.99 s between-team SD. Total plays are nearly
   conserved (corr with margin +0.100) while pass share swings (−0.545).
6. `VERIFIED` — Drives are a game-level quantity (between-team within-game SD
   0.429 vs game SD 3.198; corr +0.851), plays are zero-sum (−0.513).
7. `DERIVED` — 2024 alone cannot resolve home field (CI [−0.023, +3.461] on true
   home games) or weather (|t| < 0.25). Pooled 2015–2024: home field +1.720
   [+1.173, +2.267], wind −0.263 points per mph (t = −4.19). Rest shows no
   resolvable effect even pooled (t = 1.21).
8. `VERIFIED` — 14 market-derived columns identified across the two files
   (6 in pbp, 8 in schedules), plus `vegas_wp`/`vegas_wpa` as the easily-missed
   derived pair and `result`/`total` as outcome leakage inside the play frame.
   Quarantine at ingest with a named error and a replay test on the real call
   site.

## 8. Open items handed on

- **To the networked agent** (`docs/AGENT_OUTBOX.md`, not blocked — assigned):
  stadium latitude/longitude for travel distance and time-zone crossing; and a
  captured **pre-game weather forecast** vintage, since the `temp`/`wind` in this
  release are observed conditions and are a Rule 003 leak if used as prediction
  -time inputs.
- **To W6 (defence & matchup):** points allowed per game splits at 0.408 against
  offence's 0.714, and the defensive term did not earn its place in my simple
  model. `VERIFIED` (measured after an earlier version of this document asserted
  it without testing it, which was a defect): forward-chained team points per
  drive, K = 8, n = 330 —

  | Predictor | r | SD ratio | slope | RMSE | RMSE (league mean) |
  |---|---|---|---|---|---|
  | own prior pts/drive | **0.3376** | 0.275 | 1.228 | 0.9112 | 0.9644 |
  | own + opponent pts/drive allowed | 0.3209 | 0.328 | 0.978 | 0.9150 | 0.9644 |
  | opponent pts/drive allowed only | **0.0618** | 0.202 | 0.306 | 0.9734 | **0.9644 (worse)** |

  `DERIVED` — an opponent-defence term built this way **does not improve
  discrimination on points per drive and alone is worse than the league mean**,
  though it does move the slope from 1.228 to 0.978. Note the tension with §2b,
  where an opponent points-allowed term did marginally help *team points*
  (0.335 → 0.341, slope 1.26 → 1.03). Both are within noise at n = 330 and
  neither is a finding; recorded as a disagreement rather than resolved. W6
  should treat "defence is roughly half as stable as offence, and a naive
  opponent adjustment may buy calibration rather than discrimination" as the
  measured 2024 starting point, and test it across seasons.
- **To W2/W3/W4:** §3c is the constraint on player opportunity. Pass and rush
  attempts are anti-correlated through the scoreboard (−0.344 / +0.544), total
  plays are not. Marginal opportunity distributions fitted independently will
  not reproduce the joint.
- **To the lead:** the K-grid in §2c is a ready-made worked example for the
  Rule 005 documentation — r flat at 0.339 while the SD ratio moves 0.489 → 0.182
  and the slope moves 0.688 → 1.866, with K = 24 landing on MLB's exact headline
  SD ratio at three times MLB's r.
