# C3 — The Week-1 cold-start policy, specified and frozen

**Pass:** NFL greenfield **correction** pass, item C.
**Date:** 2026-09-06. **Author:** worker C3.
**Scope:** specification and measurement only. No predictive production code was
written; no module was added to `nfl/`. Every measurement script lives in the
session scratchpad and is evidence, not a deliverable.
**Labelling:** every substantive claim carries `VERIFIED`, `DERIVED`, or
`UNVERIFIED-RECALL`, per `nfl/research/_GROUNDING.md`.

**Read before writing this:** `nfl/research/_GROUNDING.md` including its
corrections C1–C6; `nfl/NFL_EXPERIMENTAL_ROADMAP.md`;
`nfl/research/W5_TEAM_ENVIRONMENT.md` §2c (the trivial baseline, r = 0.339) and
its shrinkage grid.

**The constraint this document was written under.** `VERIFIED` — the 2026 season
is unplayed. `games.csv` carries 272 rows with `season == 2026, game_type ==
'REG'`, **272 of 272 with a null `home_score`**. No 2026 outcome was inspected
because none exists. All evidence below is backtest on completed seasons.

---

## 0. The decision, stated first

`DERIVED` — Weeks with no current-season history are handled by a **prior-season
team rating regressed toward the prior-season league mean by a factor of about
0.4**, plus a home-field constant, and the transition into season-to-date
information is a **pseudo-game blend with a single derived constant per side**
(offence 8.88 pseudo-games, defence 23.22).

Three things make that choice defensible rather than arbitrary, and all three are
measured below:

1. The regression factor λ ≈ 0.4 is reached **twice by independent routes** — a
   direct OLS on 23 prior season-pairs (λ_off = 0.4306, λ_def = 0.4147) and a
   variance-components derivation that never looks at a regression
   (λ_off = 0.4257, λ_def = 0.3874). §4, §5.
2. The pseudo-game constants are **derived from variance components**, and the
   backtest's own optimum lands on them: grid argmin (M_off, M_def) = (8, 24)
   against derived (8.88, 23.22). §6. Under `CLAUDE.md` rule 3 they are derived
   quantities with a shown derivation, not fitted constants.
3. Nothing else in the candidate set can be distinguished from it. The five
   families in §3 span **r = 0.3238 to 0.3420** pooled over 2023–2025 weeks 1–4,
   inside a game-clustered 95% CI roughly ±0.10 wide. §5.

`DERIVED` — The honest headline is therefore twofold. A prior-season prior is
**clearly** better than a league mean (paired ΔRMSE +0.4405 points, 95%
[+0.2295, +0.6515], `P(league mean better) = 0.000`). Which *form* of prior-season
prior is used is **not resolvable at this sample size**, and this document does
not pretend it is.

---

## 1. What is being specified, and what is not

`DERIVED` — The object specified here is the **team-level scoring prior** that the
NFL-1 frozen baseline (roadmap N1-1) needs in order to produce a number in week 1
at all. It is a conditional-mean specification for **team points scored** — and,
by the identity in §5.4, simultaneously for **team points allowed**.

Not specified here, and out of scope: the predictive *distribution* (NFL-3 stores
full joint draws; this document produces a mean and a measured residual SD, and a
residual SD is not a substitute for a simulated distribution); player-level
priors; opponent-adjustment beyond the additive term below; and any market input,
which is quarantined per roadmap N0-4.

---

## 2. Data frame and how to reproduce it

`VERIFIED` — Single source: nflverse `games.csv`, already in the shared cache; no
new download was made for the season-level work, and no 2024 pbp or participation
file was re-fetched.

```
path   : <scratchpad>/games.csv
sha256 : c563178ace7c66375e4bce993419cbf4f58b22c65b2cd2df0de7c283ca68fda9
shape  : 7,548 rows x 46 columns, seasons 1999-2026
```

`VERIFIED` — Regular-season game counts and completeness, by season
(`c3_panel.py`): 2015–2020 = 256 each; 2021 = 272; **2022 = 271** (one game
cancelled); 2023 = 272; 2024 = 272; 2025 = 272 (all scored); 2026 = 272, **0
scored**.

`VERIFIED` — The panel is one row per team-game: `(season, week, game_id, team,
opp, home, pf, pa)`. 13,934 rows, 1999–2025. Franchise continuity is applied as
`OAK→LV, SD→LAC, STL→LA`; with that map the league is **exactly 32 teams in every
season from 2002 onward** (`c3_lib.py`, printed per season).

`VERIFIED` — Cross-check against W5: this panel gives 2024 mean team points
**22.9118** and 544 team-games. `W5_TEAM_ENVIRONMENT.md` §1 gives **22.912** and
544. The frames agree.

`VERIFIED` — Weeks 1–4 contain no byes in any of 2021–2025: 128 team-games per
season, every team exactly 4.

### 2.1 Column allowlist — market quarantine

`DERIVED` — `games.csv` ships `spread_line`, `total_line`, `away_moneyline`,
`home_moneyline`, `away_spread_odds`, `home_spread_odds`, `under_odds`,
`over_odds`, `result`, `total`. Per `_GROUNDING.md` ("a *neutral* data source
therefore ships sportsbook information inside it") and roadmap N0-4, the cold
start reads an **exhaustive allowlist** and must fail on anything else:

```
ALLOWED = {game_id, season, game_type, week, gameday, gametime,
           home_team, away_team, home_score, away_score}
```

`result` and `total` are excluded even though they are arithmetic functions of the
scores, because they sit in the quarantined block and re-deriving them costs
nothing.

---

## 3. The candidate policies, and input availability

`DERIVED` — Notation, all quantities from the **prior** season `S−1` only:

- `L` = league mean team points per team-game in season S−1
      = (Σ over all team-games of pf) / (number of team-games).
- `OFF_i` = team i's mean points scored in S−1 = `Σpf_i / G_i`.
- `DEF_i` = team i's mean points allowed in S−1 = `Σpa_i / G_i`.
- `h`     = mean(home team points) − mean(away team points), pooled over a
            declared window of completed seasons.

All five candidates predict team i's points against opponent j additively:
`pred = L + (off-term for i) + (def-term for j) [+ home term]`.

| # | Policy | Exact inputs consumed | Available before week-1 kickoff? |
|---|---|---|---|
| **(a)** | **League mean only.** `pred = L` (optionally `± h/2`) | prior-season final scores | `VERIFIED` yes — 2025 fully scored in `games.csv` today |
| **(b)** | **Prior-season rating, count-shrunk.** `off_i = (Σpf_i + K·L)/(G_i + K)`, same for def; `pred = L + (off_i − L) + (def_j − L)`. K selected by RMSE grid on seasons strictly before S | prior-season final scores; K from earlier seasons | `VERIFIED` yes |
| **(c)** | **Prior-season regressed by a measured factor.** `pred = L + λ_off·(OFF_i − L) + λ_def·(DEF_j − L)`, λ by OLS on seasons strictly before S | as (b), plus λ from earlier seasons | `VERIFIED` yes |
| **(d)** | **Hierarchical / partial pooling.** λ derived from variance components (τ², σ²) and the disattenuated season-to-season carryover ρ: `λ = ρ · τ²/(τ² + σ²/Ḡ)` | as (b), plus τ², σ², ρ from earlier seasons | `VERIFIED` yes |
| **(e)** | **Recency-weighted across ≥2 prior seasons.** `OFF_i(ρ_w) = Σ_k ρ_w^{k−1}(OFF_{S−k,i} − L_{S−k}) / Σ_k ρ_w^{k−1}`, k = 1..3, then regressed by λ; ρ_w and λ by grid + OLS on earlier seasons | last three seasons' final scores | `VERIFIED` yes |

`VERIFIED` — Availability is not an assumption. `games.csv` today contains every
2025 final score (272/272) and the full 2026 schedule with kickoff dates — week 1
runs **2026-09-09, 09-10, 09-13, 09-14**, 16 games, 32 teams. Every input above is
a function of seasons ≤ 2025 and is therefore fixed before the first 2026 kickoff.

`DERIVED` — Every tuned quantity for evaluation season S was estimated **only on
seasons ≤ S−1**. Tuning targets run from 2003 to S−1, each paired with its own
prior season; the floor of 2002 is the first season of the current 32-team,
eight-division structure, not a round number. Sensitivity to that floor is
measured in §7.2.

---

## 4. Roster discontinuity — how much prior-season signal actually survives

This is item 4 of the task, placed before the scorecards because it is what sets λ.

### 4.1 Year-over-year persistence and its decay

`VERIFIED` (`c3_yoy.py`), target = team's mean points scored in weeks 1–4 of
season s, predictor = that team's full prior-season deviation; 10 target seasons
2016–2025, n = 320 team-seasons; 95% CI by team-clustered bootstrap, 4000 reps,
seed 20260906.

| Lag | r | OLS β | 95% CI on r (team-clustered) |
|---|---|---|---|
| 1 season back | **0.3475** | 0.4650 | [+0.2209, +0.4658] |
| 2 seasons back | 0.2703 | 0.3626 | [+0.1679, +0.3584] |
| 3 seasons back | 0.1425 | 0.1905 | [−0.0109, +0.2658] |
| 4 seasons back | 0.1340 | 0.1756 | [+0.0232, +0.2290] |

`VERIFIED` — Points **allowed** decays faster: lag 1 r = 0.2923 (β = 0.4900),
lag 2 r = 0.1603, lag 3 r = **0.0275**. Defensive identity is essentially gone
after two seasons.

`DERIVED` — **Prior-season signal is real but weak, and this is a finding, not a
disappointment.** A single prior season explains r² ≈ 0.12 of between-team
variation in early-season scoring. That is what argues for heavy regression to the
league mean, and it is why λ ≈ 0.4 rather than ≈ 1.

### 4.2 Is the loss roster turnover, or just noise?

`VERIFIED` (`c3_yoy.py`) — pooled within-season half-to-half correlation
(weeks 1–8 mean vs weeks 10–18 mean, 2016–2025, n = 320): **r = 0.4514,
β = 0.4895**. Per season it ranges 0.2494 (2019) to 0.6380 (2016).

`DERIVED` — Within one season, with the roster largely intact, an 8-game team
scoring mean predicts the next 8 games at r = 0.45. Across the offseason, a
17-game mean predicts the next 4 games at r = 0.35. The two are not directly
comparable because the sample sizes differ on both sides, which is exactly why the
variance-components route below exists.

### 4.3 Variance components, and the carryover corrected for attenuation

`VERIFIED` (`c3_var.py`, seasons 2002–2025, `nbar` = 16.206 games per team-season):

| Quantity | Points scored | Points allowed |
|---|---|---|
| pooled within-team-season game variance σ² | **90.1147** (sd 9.4929) | 97.5339 |
| observed variance of team season means | 19.1913 | 12.0237 |
| **τ² = observed − σ²/nbar** | **13.6306** (sd **3.6920**) | **6.0052** (sd 2.4506) |
| implied K = σ²/τ² | **6.611 games** | **16.242 games** |

`DERIVED` — arithmetic shown: `13.6306 = 19.1913 − 90.1147/16.206`.

`DERIVED` — Reliability of an n-game team mean, `τ²/(τ² + σ²/n)`, offence:
n=1 → 0.1314; n=4 → 0.3770; n=8 → 0.5475; n=17 → **0.7200**.

`VERIFIED` — Disattenuated season-to-season carryover of *true* team quality
(observed prior→wk1-4 correlation divided by √(rel_prior · rel_target), 2003–2025,
n = 736): **offence ρ = 0.5984, defence ρ = 0.7734**.

`DERIVED` — Two things follow, and the second is the more useful:

- Defensive *identity* carries over **better** than offensive identity
  (0.773 vs 0.598), but defensive *ratings* are far less reliable
  (rel 0.499 vs 0.710). The two effects nearly cancel.
- The optimal week-1 shrinkage is `λ = ρ · rel_prior`:
  offence `0.5984 × 0.7127 = 0.4265`; defence `0.7734 × 0.5024 = 0.3886`.
  **Both land at ≈ 0.4, from a route that never fits a regression.**

`VERIFIED` (`c3_pol.py`) — the direct OLS estimate on the same window agrees:
λ_off = **0.4306**, λ_def = **0.4147** (fitted on 2003–2025 targets, n = 2,870).
Two independent estimation routes, one fitted and one derived, agree to within
0.03–0.05.

`UNVERIFIED-RECALL` — that offensive team quality is conventionally held to
stabilise faster than defensive is a familiar claim; W5 §2c reports the same
ordering from 2024 alone. Here it is measured over 2002–2025, and the measurement
**splits** the claim: offence has the more reliable *rating*, defence the more
persistent *identity*. Anyone quoting "offence is stickier" should say which of
the two they mean.

---

## 5. Backtest of the five candidates — 2023, 2024, 2025, weeks 1–4

Task item 2. Every parameter for evaluation season S was estimated on seasons
≤ S−1 only (`c3_pol.py` prints the window and every constant per season).

### 5.1 Parameters selected, per evaluation season

`VERIFIED` (`c3_pol.py`):

| Eval season | tuning window (n) | h | (b) K* → λ | (c) λ_off / λ_def | (d) EB λ_off / λ_def | (e) ρ_w*, λ_off / λ_def |
|---|---|---|---|---|---|---|
| 2023 | 2003–2022 (2,486) | 2.1907 | 25 → 0.3916 | 0.4023 / 0.3891 | 0.3998 / 0.3691 | 0.5, 0.5331 / 0.5420 |
| 2024 | 2003–2023 (2,614) | 2.2143 | 25 → 0.3922 | 0.4145 / 0.4054 | 0.4080 / 0.3811 | 0.5, 0.5515 / 0.5509 |
| 2025 | 2003–2024 (2,742) | 2.1985 | 25 → 0.3928 | 0.4157 / 0.4081 | 0.4086 / 0.3829 | 0.5, 0.5561 / 0.5499 |
| **2026** | **2003–2025 (2,870)** | **2.1928** | 20 → 0.4476 | **0.4306 / 0.4147** | 0.4257 / 0.3874 | 0.4, 0.5601 / 0.5376 |

`DERIVED` — the constants barely move as the window grows by three seasons. λ_off
travels 0.4023 → 0.4306 over 23 years of added data.

### 5.2 The full linked scorecard, pooled 2023 + 2024 + 2025, weeks 1–4, n = 384

`VERIFIED` (`c3_eval.py`). Per `_GROUNDING.md` and V8 Rule 005, **r, SD ratio and
calibration slope are reported together** because they are algebraically one fact.

| Policy | r | SD ratio | slope | MAE | RMSE | bias |
|---|---|---|---|---|---|---|
| (a) league mean only | 0.0652 | 0.052 | 1.262 | 7.767 | 9.939 | −0.188 |
| (a) league mean + home | 0.1460 | 0.122 | 1.196 | 7.662 | 9.855 | −0.188 |
| (b) prior season raw, λ = 1 | 0.3238 | 0.496 | 0.653 | 7.419 | 9.576 | −0.185 |
| (b) prior season shrunk, K* = 25 | 0.3248 | 0.200 | 1.623 | 7.439 | 9.501 | −0.186 |
| (c) OLS λ | 0.3239 | 0.208 | 1.558 | 7.435 | 9.495 | −0.274 |
| **(c) OLS λ + home** | **0.3420** | **0.238** | **1.439** | **7.369** | **9.418** | −0.274 |
| (d) hierarchical/EB λ | 0.3238 | 0.203 | 1.599 | 7.438 | 9.500 | −0.186 |
| (d) hierarchical/EB λ + home | 0.3413 | 0.235 | 1.455 | 7.367 | 9.421 | −0.186 |
| (e) 3-season recency ρ_w = 0.5 | 0.3197 | 0.216 | 1.482 | 7.437 | 9.496 | −0.286 |
| (e) 3-season recency + home | 0.3416 | 0.244 | 1.399 | 7.352 | 9.413 | −0.286 |

`VERIFIED` — 95% bootstrap CIs on r, 4000 reps, seed 20260906:

| Policy | r | game-clustered | team-clustered |
|---|---|---|---|
| (a) league mean + home | 0.1460 | [+0.0473, +0.2410] | [+0.0440, +0.2427] |
| (b) shrunk K* | 0.3248 | [+0.2232, +0.4237] | [+0.1927, +0.4382] |
| (c) OLS λ + home | 0.3420 | [+0.2389, +0.4360] | [+0.2221, +0.4516] |
| (d) EB λ + home | 0.3413 | [+0.2391, +0.4351] | [+0.2216, +0.4503] |
| (e) recency + home | 0.3416 | [+0.2425, +0.4357] | [+0.2222, +0.4465] |

`DERIVED` — **The CI on r is ~0.21 wide. The spread between candidates (b)–(e) is
0.018. The backtest cannot rank them.** Reporting a winner here would be reading
noise, and this document does not.

`DERIVED` — Rule 005 demonstrated again, and more sharply than W5's grid: (b) with
λ = 1 and (b) with K* = 25 have **identical r to four decimals in every season**,
because one is a positive affine transform of the other. Their SD ratios are 0.496
and 0.200 and their slopes 0.653 and 1.623. An SD ratio quoted without r and slope
beside it carries no information about discrimination.

### 5.3 Paired comparisons — what *is* resolved

`VERIFIED` (`c3_eval.py`, `c3_sens.py`), paired game-clustered bootstrap, 4000 reps:

| Comparison (weeks 1–4, 2023–25) | ΔRMSE | 95% CI | verdict |
|---|---|---|---|
| league mean + home → prior-season prior (c+) | **+0.4405** | [+0.2295, +0.6515] | **resolved**: the prior-season prior helps |
| λ = 1 → λ ≈ 0.4 (no home) | +0.0813 | [−0.2215, +0.3791] | not resolved |
| no home term → home term | +0.0778 | [−0.0361, +0.1840] | not resolved (P(home better) = 0.908) |

`DERIVED` — One comparison in this study is decided and it is the coarse one. The
home term and the shrinkage strength both point the right way and neither clears
its own noise at n = 384. They are retained on grounds stated in §7, not on this
evidence.

### 5.4 Points allowed is the same scorecard, exactly

`VERIFIED` (`c3_pa.py`) — Constructing `pred_pa(i vs j) = pred_pf(j vs i)` and
scoring against realised points allowed reproduces the points-scored scorecard to
machine precision in all three seasons (r difference ≤ 5.55e-17, RMSE difference
exactly 0).

`DERIVED` — This is an identity, not a coincidence: the evaluation set contains
both team-games of every game, each team's points allowed is its opponent's points
scored, and the additive form makes `pred_pa(i,j)` the same number as
`pred_pf(j,i)`. **A separate "points allowed" scorecard on this frame carries no
additional information and must not be reported as a second result.** It would be
double-counting of exactly the kind `CLAUDE.md`'s "list overlap" fix exists to
prevent.

### 5.5 Week 1 alone — the actual cold start

`VERIFIED` (`c3_final.py`), 2023 + 2024 + 2025 week 1 only, n = 96:

| Policy | r | SD ratio | slope | MAE | RMSE | r 95% CI (game-clustered) |
|---|---|---|---|---|---|---|
| league mean + home | 0.0503 | 0.133 | 0.377 | 7.238 | 9.163 | [−0.1433, +0.2445] |
| prior season raw, λ = 1, no home | 0.4256 | 0.549 | 0.776 | 6.827 | 8.357 | [+0.2567, +0.5681] |
| **frozen policy (λ ≈ 0.4 + home)** | **0.3949** | **0.265** | **1.493** | **6.835** | **8.490** | [+0.2537, +0.5224] |

`DERIVED` — Week 1 is **not** the hardest week for this policy; it is among the
better ones. That is not surprising once §4 is read: at week 1 the prior season is
the *only* information, and it is worth r ≈ 0.4 here. n = 96 and the CI is 0.27
wide, so do not quote 0.3949 as a point estimate of week-1 skill.

### 5.6 Where this sits against W5's baseline

`VERIFIED` — W5 §2c: shrunken **season-to-date** team ratings, forward-chained
from week 8, 2024 only, reach r = 0.339 [0.244, 0.425], SD ratio 0.332, slope
1.021.

`VERIFIED` (`c3_final.py` final block) — this document's frozen policy carried
across the whole season with the §6 transition, 2021–2025, n = 2,718:
**r = 0.3160 [0.2801, 0.3508], SD ratio 0.324, slope 0.976**, MAE 7.487,
RMSE 9.391, bias +0.123.

`DERIVED` — The cold-start policy plus its transition rule reaches the same
territory as W5's baseline **while also covering weeks 1–7, which W5's baseline
could not produce a number for at all.** It does not beat it: the intervals sit on
top of each other, and the frames differ (2021–25 all weeks vs 2024 weeks 8+).
This is a statement of adequacy for the purpose, not a claim of improvement.

---

## 6. The transition rule — when does current-season information take over?

Task item 3.

### 6.1 The family, and why it has one parameter and not seventeen

`DERIVED` — Write `μ_i` for the pre-season prior mean of team i (§7.1) and `x̄_i`
for its raw season-to-date mean after `g` games. Blending
`R_i = (1−θ)·μ_i + θ·x̄_i` and the pseudo-game form
`R_i = (Σ pf + M·μ_i)/(g + M)` are **the same estimator**, with
`θ = g/(g + M)`. So "estimate the blending weight by week" and "choose one
pseudo-game constant" are the same question asked twice, and the second form has
one parameter instead of one per week.

`DERIVED` — M is derivable, not fittable. The posterior weight on data is
`M = σ² / Var(true_S | prior)`, and
`Var(true_S | prior) = τ²·(1 − ρ²·rel_prior)`. From §4.3, with the 2003–2025 window:

```
offence:  ρ² · rel = 0.599414² × 0.710250 = 0.255191
          M_off = 90.114663 / (13.630604 × (1 − 0.255191)) =  8.8764
defence:  ρ² · rel = 0.775715² × 0.499449 = 0.300520
          M_def = 97.533858 / ( 6.005219 × (1 − 0.300520)) = 23.2199
```

### 6.2 What the backtest says about M

`VERIFIED` (`c3_trans.py` §T3c), 2021–2025, all 18 weeks, n = 2,718, RMSE over a
2-D grid:

| M_off \ M_def | 8 | 12 | 16 | **24** | 32 | 48 |
|---|---|---|---|---|---|---|
| 4 | 9.4509 | 9.4243 | 9.4137 | 9.4083 | 9.4093 | 9.4147 |
| 6 | 9.4328 | 9.4061 | 9.3954 | 9.3900 | 9.3910 | 9.3963 |
| **8** | 9.4319 | 9.4051 | 9.3944 | **9.3890** | 9.3900 | 9.3954 |
| 12 | 9.4465 | 9.4196 | 9.4090 | 9.4036 | 9.4046 | 9.4100 |
| 16 | 9.4660 | 9.4392 | 9.4286 | 9.4233 | 9.4243 | 9.4298 |

`VERIFIED` — grid argmin **(M_off, M_def) = (8, 24)**, RMSE 9.3890.
`DERIVED` — against the derived (8.8764, 23.2199). The derivation and the backtest
land on the same place, from different evidence.

`VERIFIED` (`c3_final.py` §F4) — 400 game-clustered bootstrap resamples of the
argmin over the grid {2,4,6,8,12,16,24,32,48,64}:

- `M_off`: median 8, 5–95 pct **[6, 12]**; the argmin was 6 on 175 resamples,
  8 on 200, 12 on 21, 4 on 4.
- `M_def`: median 24, 5–95 pct **[16, 48]**; argmin 16 on 59, 24 on 169,
  32 on 135, 48 on 32.

`DERIVED` — **The optimum is not well-resolved and must not be reported as if it
were.** Every cell with M_off ∈ [4, 16] and M_def ∈ [8, 48] lies within 0.06
points of RMSE of the best — 0.6% of a 9.4-point RMSE. The defensive constant in
particular is resolved only to a factor of three.

### 6.3 Per-week blending weight, measured directly

`VERIFIED` (`c3_trans.py` §T3a), 2021–2025 pooled, θ constrained equal on both
sides, grid 0 to 1 by 0.05. "Band" = every θ whose RMSE is within 1% of the best.

| Week | mean g | θ* observed | within-1% band | θ = g/(g+11) | in band? |
|---|---|---|---|---|---|
| 1 | 0 | — (no data exists) | — | 0 | n/a |
| 2 | 1.00 | 0.00 | [0.00, 0.10] | 0.083 | yes |
| 3 | 2.00 | 0.15 | [0.00, 0.30] | 0.154 | yes |
| 4 | 3.00 | 0.15 | [0.00, 0.30] | 0.214 | yes |
| 5 | 4.00 | 0.30 | [0.15, 0.45] | 0.267 | yes |
| 6 | 4.92 | 0.25 | [0.05, 0.40] | 0.309 | yes |
| 8 | 6.68 | 0.25 | [0.10, 0.45] | 0.378 | yes |
| 10 | 8.44 | 0.30 | [0.10, 0.50] | 0.434 | yes |
| 12 | 10.23 | 0.70 | [0.50, 0.90] | 0.482 | **no** |
| 15 | 13.00 | 0.60 | [0.35, 0.85] | 0.542 | yes |
| 18 | 15.99 | 0.45 | [0.25, 0.70] | 0.592 | yes |

`VERIFIED` — full 17-week table in `c3_final.py` §F5. The smooth pseudo-game
schedule lies inside the observed within-1% band in **16 of 17 weeks**.

`DERIVED` — The per-week optima are **not monotone** (0.00, 0.15, 0.15, 0.30,
0.25, 0.40, 0.25, 0.30, 0.30, 0.55, 0.70, 0.65, 0.50, 0.60, 0.50, 0.75, 0.45),
and their bands are 0.30–0.50 wide. A fitted per-week curve would be tracing
sampling noise with 17 parameters. Per `CLAUDE.md` rule 3 that curve would be 17
constants each needing its own justification, and none of them has one.

### 6.4 The decisive check against a fitted curve

`VERIFIED` (`c3_sens.py` §S3), weeks 2–18, 2021–2025:

```
derived two-constant rule            RMSE = 9.4246   r = 0.3172
per-week theta fitted IN-SAMPLE      RMSE = 9.4320   (17 free parameters,
                                                      fitted on the scored data)
```

`DERIVED` — **A 17-parameter curve fitted on the very data it is scored on is
0.0074 points of RMSE *worse* than the two-constant derived rule.** The two are
not nested — the per-week family forces θ_off = θ_def, the derived rule lets them
differ — and that is the point: the one structural distinction that matters
(offence and defence stabilise at different rates) buys more than seventeen
free parameters do, even with the fitted curve given the unfair advantage of
in-sample scoring. The falsely precise fitted curve is rejected on measurement,
not on taste.

### 6.5 When does current-season information beat the prior?

`VERIFIED` (`c3_trans.py` §T3d), 2021–2025, RMSE by week:

| Week | prior-only | current-season-only | derived blend |
|---|---|---|---|
| 1 | 8.8397 | (undefined) | 8.8397 |
| 2 | **9.1770** | 15.5552 | 9.2251 |
| 3 | 10.1513 | 12.8214 | **10.0720** |
| 4 | 9.1434 | 11.0238 | **9.0353** |
| 5 | 9.4919 | 10.5923 | **9.3647** |
| 6 | 9.0673 | 10.2964 | **8.8679** |
| 8 | 9.2203 | 10.3282 | **9.0643** |
| 10 | 9.9224 | 10.5884 | **9.6802** |
| 11 | 9.6510 | **9.5262** | **9.2772** |
| 12 | 9.3587 | 8.6644 | **8.5722** |

`DERIVED` — Three separate answers to "when does the season take over", and they
must not be conflated:

1. As a **replacement** for the prior: **week 11**. Before that, throwing the
   prior away and using season-to-date alone is worse in every single week.
2. As a **contribution** to a blend: **week 3**. From week 3 onward the blend
   beats prior-only in every week measured. At week 2 the blend is 0.048 worse
   than prior-only — inside noise, and the schedule's own weight there is only
   0.101, so this is not a case for a discontinuity at week 2.
3. As a **majority** of the weight: `θ_off` crosses 0.5 at g = 9 (week 10 in a
   bye-free path); `θ_def` crosses 0.5 at g = 24, i.e. **never within a season**.
   Defensive ratings never stop leaning mostly on the prior season.

---

## 7. THE FROZEN SPECIFICATION

Task item 5. This section is the deliverable. It is written to be executed
identically by two people who have never spoken.

### 7.1 Inputs

`SPEC-1`. **Source file.** nflverse `games.csv` from the
`nflverse/nflverse-data` releases, downloaded once, content-hashed with sha256,
and the hash recorded in the execution identity (roadmap N0-3). The vintage used
for the 2026 season must be a snapshot taken **after the 2025 season's final game
is scored and before 2026-09-09 00:00 UTC**, and that snapshot is frozen for the
whole season.

`SPEC-2`. **Column allowlist**, exhaustive: `game_id, season, game_type, week,
gameday, gametime, home_team, away_team, home_score, away_score`. Reading any
other column is a named error `MARKET_COLUMN_ACCESS`. Reading a column outside the
list at all is `COLUMN_NOT_ALLOWLISTED`.

`SPEC-3`. **Row filter.** `game_type == 'REG'` and both scores non-null.

`SPEC-4`. **Franchise map**, applied to both team columns before any aggregation:
`OAK→LV`, `SD→LAC`, `STL→LA`. If after mapping any season in the window has other
than exactly 32 distinct teams, raise `FRANCHISE_SET_UNEXPECTED` and stop.

`SPEC-5`. **Windows**, fixed:
- *Prior-season window*: season `S−1` only, used for `L`, `OFF_i`, `DEF_i`.
- *Constant-estimation window*: target seasons 2003 … S−1, each paired with its
  own prior season; equivalently team-game rows from weeks 1–4 of those seasons.
  For S = 2026 that is 2003–2025, n = 2,870 team-games.
- *Home-effect window*: all REG team-games in seasons 2002 … S−1.

### 7.2 Constants, with their estimation procedure

`SPEC-6`. Every constant below is **derived or fitted on the windows in SPEC-5 and
on nothing else**. Its procedure is stated so it can be recomputed; its value for
S = 2026 is stated so a recomputation can be checked.

| Symbol | Procedure | Value for S = 2026 |
|---|---|---|
| `L` | Σ pf over all team-games of season S−1, ÷ count | **23.012868** (= 12,519 / 544) |
| `λ_off` | OLS coefficient on `(OFF_i − L_{t−1})` in `pf − L_{t−1} ~ 1 + (OFF_i − L) + (DEF_j − L)` over the constant-estimation window | **0.430572** |
| `λ_def` | OLS coefficient on `(DEF_j − L_{t−1})` in the same regression | **0.414683** |
| `c` | the intercept of that regression | measured **−0.063919**; **set to 0** in the spec (SPEC-9) |
| `h` | mean(home pf) − mean(away pf) over the home-effect window | **2.192833** |
| `σ²_off, τ²_off` | pooled within-team-season variance of pf; variance of team season means minus σ²/Ḡ | 90.114663, 13.630604 |
| `σ²_def, τ²_def` | same on pa | 97.533858, 6.005219 |
| `ρ_off, ρ_def` | observed prior→(weeks 1–4) team-level correlation ÷ √(rel_prior · rel_4) | 0.599414, 0.775715 |
| `M_off` | `σ²_off / (τ²_off · (1 − ρ_off²·rel_off))` | **8.8764** |
| `M_def` | `σ²_def / (τ²_def · (1 − ρ_def²·rel_def))` | **23.2199** |

`VERIFIED` (`c3_sens.py` §S1) — sensitivity of the constants to the 2002 floor:

| Floor | n | λ_off | λ_def | h |
|---|---|---|---|---|
| **2002** | 2,870 | **0.4306** | **0.4147** | **2.1928** |
| 2010 | 1,898 | 0.4678 | 0.4061 | 2.0153 |
| 2015 | 1,270 | 0.4729 | 0.5121 | 1.7402 |
| 2018 | 892 | 0.5282 | 0.5384 | 1.5726 |

`VERIFIED` (`c3_era2.py` §E2) — and the effect of that choice on the scorecard,
weeks 1–4, 2021–2025, n = 640: floor 2002 gives r = 0.2813 / ratio 0.272 /
slope 1.033; floor 2018 gives r = 0.2862 / ratio 0.309 / slope 0.926. Paired
game-clustered ΔRMSE = **+0.0117, 95% [−0.0372, +0.0595]**.

`DERIVED` — the floor choice is not resolvable. 2002 is declared because it is the
first season of the current 32-team structure and gives the largest window. The
alternative is in §8.

`VERIFIED` (`c3_era.py` §E1) — the one place the window visibly matters is `h`,
by four-season block: 2002-05 +2.9893, 2006-09 +2.1201, 2010-13 +2.6748,
2014-17 +2.2754, **2018-21 +0.9692**, 2022-25 +2.1500. Per season 2019 = −0.1406,
2020 = +0.0547, then 2021 = +1.7132 … 2025 = +2.0699.

`DERIVED` — the short-window estimates (1.57, 1.74) are pulled down by 2019–2020,
two seasons that the most recent four do not resemble. The long-window value
**2.1928 is closer to the 2022–2025 block value 2.1500** than either short-window
estimate is. That is the argument for the long window, and it is an argument from
the measurement rather than from a preference for old data.

### 7.3 The arithmetic

`SPEC-7`. **Pre-season team priors**, computed once per season, before week 1:

```
G_i    = number of REG games team i played in season S-1
OFF_i  = (sum of team i's points scored in S-1) / G_i
DEF_i  = (sum of team i's points allowed in S-1) / G_i
mu_off_i = L + lambda_off * (OFF_i - L)
mu_def_i = L + lambda_def * (DEF_i - L)
```

`SPEC-8`. **Season-to-date state**, updated once per week, from completed games of
season S strictly before the forecast week:

```
g_i     = games team i has completed in season S before this week
xbar_off_i = (sum of team i's points scored so far in S) / g_i     [undefined if g_i = 0]
xbar_def_i = (sum of team i's points allowed so far in S) / g_i    [undefined if g_i = 0]
```

`SPEC-9`. **The rating, and the forecast.** For team i playing opponent j:

```
theta_off = g_i / (g_i + M_off)          # = 0 exactly when g_i = 0
theta_def = g_j / (g_j + M_def)

R_off_i = (1 - theta_off) * mu_off_i + theta_off * xbar_off_i     if g_i > 0
        = mu_off_i                                                if g_i = 0
R_def_j = (1 - theta_def) * mu_def_j + theta_def * xbar_def_j     if g_j > 0
        = mu_def_j                                                if g_j = 0

pred_points(i vs j) = L + (R_off_i - L) + (R_def_j - L)
                        + h/2   if i is the home team
                        - h/2   if i is the away team
                        + 0     if the game is at a neutral site

pred_points_allowed(i vs j) = pred_points(j vs i)      # by SPEC-13
```

The intercept `c` is set to 0. Its measured value is −0.063919 points; carrying it
would change a forecast by 0.06 of a point and would add a constant that has to be
re-justified every season. This is a **declared** simplification with its measured
cost shown, not a silent omission.

`SPEC-10`. **Week 1 is the g = 0 case and needs no separate branch.** At week 1
`g_i = g_j = 0`, so `theta = 0`, and the forecast reduces to
`L + λ_off(OFF_i − L) + λ_def(DEF_j − L) ± h/2`. This is the point of the
pseudo-game form: the cold start is not a special case bolted on, it is the
schedule evaluated at zero games.

`SPEC-11`. **The schedule is by games played, not by week number.** A team coming
off a bye has the `g` it has, not `week − 1`. Byes therefore need no rule.

`SPEC-12`. **Rounding and order of operations.** IEEE-754 double precision
throughout; no intermediate rounding; sums accumulated in the order rows appear in
the source file after a deterministic sort on `(season, week, game_id, home_team)`.
Reported forecasts are rounded to 4 decimal places at output only.

`SPEC-13`. **Points allowed is not modelled separately.** It is defined as the
opponent's points-scored forecast. `VERIFIED` in §5.4 that this reproduces the
identical scorecard; producing a separate points-allowed model and scoring it as
independent evidence is forbidden.

### 7.4 Determinism

`SPEC-14`. `DERIVED` — the output is a deterministic function of exactly five
things: the sha256-identified `games.csv` snapshot; the allowlist; the franchise
map; the eight constants in SPEC-6; and the forecast week. **No random number is
drawn anywhere in this specification. There is no seed because there is nothing to
seed.** `VERIFIED` (`c3_final.py` §F6) — recomputing the weeks-1–4 forecasts twice
gives bitwise-identical IEEE-754 output.

`SPEC-15`. **Named errors, not silent fallbacks** (roadmap N0-5, Failure Taxonomy
Class A):

| Condition | Named error |
|---|---|
| team in season S absent from season S−1 (expansion, relocation not in the map) | `PRIOR_SEASON_TEAM_MISSING` — **must not** silently fall back to `L` |
| season S−1 has any REG game with a null score at snapshot time | `PRIOR_SEASON_INCOMPLETE` |
| a season in the estimation window has ≠ 32 teams after mapping | `FRANCHISE_SET_UNEXPECTED` |
| the forecast timestamp is at or after the kickoff of the game being forecast | `FORECAST_AFTER_KICKOFF` |
| `g_i > 0` but `xbar_off_i` is null | `SEASON_TO_DATE_EMPTY` |
| any read outside the allowlist | `COLUMN_NOT_ALLOWLISTED` / `MARKET_COLUMN_ACCESS` |

`SPEC-16`. **Information-set boundary.** Every input is a completed game with a
kickoff strictly earlier than the forecast timestamp. `VERIFIED` — the
pre-season priors depend only on seasons ≤ 2025; the season-to-date state depends
only on games already played. No injury report, no lineup, no weather, no market
number enters this specification at all.

### 7.5 The freeze declaration

`SPEC-17`. **This specification is frozen as of 2026-09-06, before any 2026 game
has been played.**

- The constants in SPEC-6 are fixed for the entire 2026 season. They are **not**
  re-estimated as 2026 games arrive. Only `g`, `xbar_off` and `xbar_def` change
  during the season, and they change by SPEC-8 alone.
- **This specification must never be revised after observing 2026 results.**
  A 2026 result that makes the policy look bad is a *result*, recorded as such. If
  a revision is genuinely warranted, it is a **new named policy** evaluated on a
  window that the revision decision did not touch — it does not inherit this
  document's name, its constants, or its record.
- Recomputation for S = 2027 re-runs SPEC-6's procedures with the window advanced
  by one season. That is the procedure being frozen, not the numbers; the 2027
  numbers are then themselves frozen before 2027 week 1.
- `DERIVED` — this is `CLAUDE.md` rule 4 ("preserve the unfixed baseline") and
  V8 Rule 004a (metrics frozen before scoring) applied to a policy rather than to
  a metric.

### 7.6 Reference values for verification

`VERIFIED` (`c3_final.py` §F7, run against the sha256 above) — the 2025 inputs, so
that an independent implementation can check itself. `L = 23.012868`.

| Team | G | PF | PA | OFF | DEF | mu_off | mu_def |
|---|---|---|---|---|---|---|---|
| ARI | 17 | 355 | 488 | 20.8824 | 28.7059 | 22.0955 | 25.3737 |
| ATL | 17 | 353 | 401 | 20.7647 | 23.5882 | 22.0449 | 23.2515 |
| BAL | 17 | 424 | 398 | 24.9412 | 23.4118 | 23.8431 | 23.1783 |
| BUF | 17 | 481 | 365 | 28.2941 | 21.4706 | 25.2868 | 22.3733 |
| CAR | 17 | 311 | 380 | 18.2941 | 22.3529 | 20.9811 | 22.7392 |
| CHI | 17 | 441 | 415 | 25.9412 | 24.4118 | 24.2737 | 23.5930 |
| CIN | 17 | 414 | 492 | 24.3529 | 28.9412 | 23.5899 | 25.4712 |
| CLE | 17 | 279 | 379 | 16.4118 | 22.2941 | 20.1706 | 22.7148 |
| DAL | 17 | 471 | 511 | 27.7059 | 30.0588 | 25.0335 | 25.9347 |
| DEN | 17 | 401 | 311 | 23.5882 | 18.2941 | 23.2606 | 21.0561 |
| DET | 17 | 481 | 413 | 28.2941 | 24.2941 | 25.2868 | 23.5442 |
| GB  | 17 | 391 | 360 | 23.0000 | 21.1765 | 23.0073 | 22.2513 |
| HOU | 17 | 404 | 295 | 23.7647 | 17.3529 | 23.3366 | 20.6658 |
| IND | 17 | 466 | 412 | 27.4118 | 24.2353 | 24.9069 | 23.5198 |
| JAX | 17 | 474 | 336 | 27.8824 | 19.7647 | 25.1095 | 21.6659 |
| KC  | 17 | 362 | 328 | 21.2941 | 19.2941 | 22.2728 | 21.4708 |
| LA  | 17 | 518 | 346 | 30.4706 | 20.3529 | 26.2240 | 21.9098 |
| LAC | 17 | 368 | 340 | 21.6471 | 20.0000 | 22.4248 | 21.7635 |
| LV  | 17 | 241 | 432 | 14.1765 | 25.4118 | 19.2082 | 24.0076 |
| MIA | 17 | 347 | 424 | 20.4118 | 24.9412 | 21.8929 | 23.8125 |
| MIN | 17 | 344 | 333 | 20.2353 | 19.5882 | 21.8169 | 21.5927 |
| NE  | 17 | 490 | 320 | 28.8235 | 18.8235 | 25.5148 | 21.2756 |
| NO  | 17 | 306 | 383 | 18.0000 | 22.5294 | 20.8545 | 22.8124 |
| NYG | 17 | 381 | 439 | 22.4118 | 25.8235 | 22.7540 | 24.1784 |
| NYJ | 17 | 300 | 503 | 17.6471 | 29.5882 | 20.7025 | 25.7396 |
| PHI | 17 | 379 | 325 | 22.2941 | 19.1176 | 22.7034 | 21.3976 |
| PIT | 17 | 397 | 387 | 23.3529 | 22.7647 | 23.1593 | 22.9100 |
| SEA | 17 | 483 | 292 | 28.4118 | 17.1765 | 25.3375 | 20.5926 |
| SF  | 17 | 437 | 371 | 25.7059 | 21.8235 | 24.1724 | 22.5197 |
| TB  | 17 | 380 | 411 | 22.3529 | 24.1765 | 22.7287 | 23.4954 |
| TEN | 17 | 284 | 478 | 16.7059 | 28.1176 | 20.2973 | 25.1297 |
| WAS | 17 | 356 | 451 | 20.9412 | 26.5294 | 22.1209 | 24.4711 |

`VERIFIED` — worked example, every step shown, for a hypothetical **BUF at home
vs NYJ in week 1**:

```
mu_off[BUF] = 23.012868 + 0.430572 * (28.294118 - 23.012868) = 25.286826
mu_def[NYJ] = 23.012868 + 0.414683 * (29.588235 - 23.012868) = 25.739561
g = 0 for both, so theta_off = theta_def = 0 and R = mu
pred = 23.012868 + (25.286826 - 23.012868) + (25.739561 - 23.012868) + 2.192833/2
     = 29.109936
```

An implementation that does not return **29.109936** for this input has diverged
from the specification. (This is an arithmetic verification case, not a 2026
forecast; whether BUF actually hosts NYJ in week 1 is irrelevant to it.)

### 7.7 Expected performance, registered in advance

`VERIFIED` (`c3_final.py` last block) — the frozen policy, run over 2021–2025 with
the SPEC-9 transition. Registered here so that 2026 is scored against a number
written down before 2026 happened.

| Frame | n | r | SD ratio | slope | MAE | RMSE | residual SD | bias |
|---|---|---|---|---|---|---|---|---|
| weeks 1–4 | 640 | 0.2893 [+0.211, +0.363] | 0.286 | 1.012 | 7.290 | 9.305 | 9.309 | +0.234 |
| weeks 1–18 | 2,718 | 0.3160 [+0.280, +0.351] | 0.324 | 0.976 | 7.487 | 9.391 | 9.392 | +0.123 |

`DERIVED` — This is a **registered expectation, not a target**. If 2026 comes in
materially below it, that is the result and it is reported as the result. Per
roadmap §"What would falsify the plan itself", clause 3, the response called for
on a collapse is to say so and stop, not to re-tune.

Two cautions attached to the table. First, the residual SD of ~9.3–9.4 points is a
**marginal** spread and is not a predictive distribution; NFL-3 owes the joint
draws, and nine percentiles is how MLB lost CRPS and tail calibration. Second, the
slopes here (1.012, 0.976) sit near 1, but per `CLAUDE.md` rule 8 that is not
written as "calibrated": there is no predeclared equivalence margin and no TOST
behind it.

---

## 8. Owner-level tradeoffs

Task item 6. Three, and only the first is close.

### T1 — Estimation window: 2002 floor (specified) vs recent-era floor

`DERIVED` — **Specified: 2002.** It is the first season of the current 32-team,
eight-division structure, gives n = 2,870 team-games of estimation data, and
produces constants that move least as the window is extended (`VERIFIED`:
λ_off travels 0.4023 → 0.4306 across 23 added seasons).

The case against it is real and should be stated rather than dismissed:
a 2018 floor gives λ ≈ 0.53 and h ≈ 1.57, and one could argue the game since 2018
is the relevant population. `VERIFIED` — the scorecard cannot separate them
(ΔRMSE +0.0117, 95% [−0.0372, +0.0595]); `VERIFIED` — but h by four-season block
shows the short window is dominated by 2019–2020, and the most recent block
(2022–25, +2.1500) is closer to the long-run value (+2.1928) than to the
short-window one (+1.5726).

**What the owner is choosing between:** a longer window whose constants move less
and which is demonstrably not stale on the one constant where staleness would
show; versus a
shorter window that tracks era drift and is, on this evidence, tracking a
two-season anomaly rather than a trend. The evidence favours 2002 and does not
settle it.

### T2 — Two derived constants (specified) vs a per-week fitted curve

`DERIVED` — **Specified: two derived constants.** There is no tradeoff to make
here and the file says so on measurement rather than on principle: §6.4 shows the
17-parameter per-week curve is **worse in-sample** than the two-constant rule. The
apparent flexibility buys nothing and would cost seventeen constants that
`CLAUDE.md` rule 3 would each require justifying. **No owner decision needed.**

### T3 — The home term: retained at h/2, and it is the weakest element

`DERIVED` — **Specified: retained.** It improves pooled r from 0.3239 to 0.3420
and RMSE by 0.0778 points, and it is the single most-studied effect in the sport.

`VERIFIED` — but its paired game-clustered 95% CI is [−0.0361, +0.1840]: at
n = 384 it does **not** clear its own noise, `P(better) = 0.908`. At week 1 alone
the unshrunk no-home variant scored higher r (0.4256 vs 0.3949) on n = 96.

**What the owner is choosing between:** retaining a term that is right on prior
grounds, cheap, symmetric, and measured at +2.19 points over 24 seasons; versus a
strict rule that nothing enters a frozen spec until it clears a clustered interval
on this project's own data. This document retains it and flags it as the element
most likely to be removed by a stricter evidence rule. If the owner prefers the
stricter rule, set `h = 0` and change nothing else — SPEC-9 already handles it.

---

## 9. What this document cannot establish

Stated plainly, per `CLAUDE.md` rule 8 and V8 Rule 006.

1. `DERIVED` — **This is exploratory work and the 2023–2025 weeks 1–4 frame is now
   inspected data.** The *family* of policy was chosen after seeing that a
   prior-season prior beats a league mean on those seasons. Freezing them does not
   make them a holdout. The confirmatory test of this specification is the 2026
   season, which is why the freeze in §7.5 is the operative part of this document.
2. `DERIVED` — **The 2026 constants in SPEC-6 were estimated on a window that
   includes 2023, 2024 and 2025** — legitimately, since those are prior
   information for 2026, but it means the exact constants that will run in 2026
   are not the ones whose scorecard appears in §5.2. The §7.7 registered numbers
   use per-season strictly-prior constants and are the right reference.
3. `DERIVED` — **n is small and this is the binding constraint.** 384 team-games
   over three seasons of weeks 1–4; game-clustered CIs on r are ~0.21 wide.
   `_GROUNDING.md` C1 records ~377 games for a game-level r comparison; weeks 1–4
   of one season is 128 team-games = 64 games. **A single season's weeks 1–4
   cannot resolve anything about this policy**, and a 2026 week-1–4 review should
   be registered `DEFERRED / UNDERPOWERED` in advance rather than discovered to be
   so afterwards.
4. `DERIVED` — Nothing here says the *level* of these forecasts is right. The
   biases (−0.186 pooled 2023–25; +0.234 on 2021–25 weeks 1–4) are small relative
   to a 9.3-point residual SD, and no equivalence margin was predeclared, so per
   rule 8 the words "unbiased" and "calibrated" do not appear about them.
5. `DERIVED` — `M_def` is resolved only to a factor of roughly three
   ([16, 48] at 5–95%). The specification picks the derived 23.2199 and the
   backtest agrees with it; that agreement is reassurance, not resolution.
6. `UNVERIFIED-RECALL` — that offseason roster movement (free agency, the draft,
   coaching change, quarterback change) is the mechanism behind the decay measured
   in §4 is a plausible mechanism that **this document did not test**. It measured
   the decay, not its cause. A test would need roster-continuity data joined at the
   team-season level, and none was consulted here.

---

## 10. Reproduction

`VERIFIED` — scripts in the session scratchpad, run under `python3.12`,
all reading only `games.csv`:

| Script | Produces |
|---|---|
| `c3_panel.py` | the team-game panel, source hash, game counts, bye check |
| `c3_lib.py` | shared metrics, clustered bootstrap, season aggregates |
| `c3_yoy.py` | §4.1, §4.2 — persistence by lag, within-season split-half |
| `c3_var.py` | §4.3 — variance components and disattenuated carryover |
| `c3_pol.py` | §5.1 — per-season constants, all five policy families |
| `c3_eval.py` | §5.2, §5.3 — scorecards, clustered CIs, paired ΔRMSE |
| `c3_pa.py` | §5.4 — the points-allowed identity |
| `c3_trans.py` | §6.2, §6.3, §6.5 — M grid, per-week θ, crossover |
| `c3_final.py` | §5.5, §6.3, §7.6, §7.7 — week 1, θ schedule, constants, registered scorecard |
| `c3_sens.py` | §7.2, §5.3, §6.4 — window sensitivity, paired tests, fitted-curve test |
| `c3_era.py`, `c3_era2.py` | §7.2 — home advantage by era, floor sensitivity |

`DERIVED` — No 2024 pbp or participation file was re-downloaded; the shared cache
was reused. No additional pbp season was fetched. Nothing was deleted from the
cache. No file outside `nfl/research/C3_COLD_START_SPEC.md` was modified.
