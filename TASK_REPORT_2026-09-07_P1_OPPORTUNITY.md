# P1 — Opportunity forecasting baseline

**Date:** 2026-09-07 · **Repository:** `94924676jp-a11y/nfl`
**Track:** quarantined research. G0A untouched at **11/12**. NFL-1 not executed.
**2026 data used:** none.

---

## Headline answer to the question you asked

> *Can we reliably forecast who will actually be on the field and receive
> opportunities before trying to forecast what they do with those
> opportunities?*

**Partly, and the useful part is smaller than the raw numbers suggest.**

- **Continuity is strong and cheap.** Last week's snap share predicts this
  week's at r ≈ 0.71, MAE ≈ 0.15. For a stable role it is r ≈ 0.80, MAE ≈ 0.12.
- **Nothing in the simple-model family beats last-week persistence for snap
  share or route participation.** Every smoothed alternative is *worse*, and the
  block-bootstrap intervals exclude zero. Smoothing helps only for target share,
  and by ≈ 0.005 share.
- **Role changes are where it breaks, and they break it badly.** On a
  role-change week, snap-share MAE roughly doubles (0.123 → 0.233) and
  correlation falls from 0.80 to 0.45.
- **Team pass volume is close to unforecastable from a QB's own history**:
  r ≈ 0.10–0.22, and last week's value is *worse than the pooled prior*.
- **Vacated opportunity does not redistribute proportionally.** Assuming
  proportional transfer is worse than assuming no transfer at all.

So: forecast the stable majority cheaply, and treat role change and team volume
as unsolved. The honest summary is that most of what looks like predictive skill
here is persistence plus a large stable subpopulation.

---

## 1. Exact historical seasons and rows used

Seasons **2020–2025**, regular season only. 2026 excluded entirely.

| | |
|---|---|
| Source | nflverse-data GitHub releases |
| Files | `pbp`, `pbp_participation`, `snap_counts`, `weekly_rosters` × 6 seasons |
| Panel rows (players with any recorded activity) | **57,670** |
| Panel rows after adding pregame-identifiable non-appearances | **83,144** (+25,474) |
| Team-games | **3,230** |
| Distinct players | **2,234** |
| Evaluation seasons | 2022, 2023, 2024, 2025 |

Input identity (md5): `pbp_2024.csv` `3880d4554c66740ac1082d530215e142`,
`part_2024.csv` `9bd3bfa981cd302148836c67759cb02c`. **Both match the md5s
recorded in `nfl/research/W4_RECEIVER_OPPORTUNITY.md`** — byte-identical to the
files the earlier research pass used, which is a real cross-check rather than a
coincidence I am reporting as one.

Per-season rows: 2020 9,231 · 2021 9,754 · 2022 9,675 · 2023 9,744 ·
2024 9,628 · 2025 9,638.

---

## 2. Target definitions

| Target | Definition | Note |
|---|---|---|
| `snap_share` | `snap_counts.offense_pct` | **already a fraction**, see §15 |
| `rpr` | player pass-play participations / team dropbacks | participation `offense_players`; a *proxy*, see below |
| `target_share` | player targets / **team targets** | not / `pass_attempt`, see §15 |
| `carry_share` | player carries / team carries | |
| `rz_carry_share` | red-zone carries / team red-zone carries | `yardline_100 <= 20` |
| `team_dropbacks` | team dropbacks in the game | QB |
| `pass_att_as_passer` | QB pass attempts | QB |
| `scrambles` | QB scrambles, charged to the **rusher** | see §15 |
| `designed_rushes` | QB rushes that are not scrambles | |

**`rpr` is not routes run.** `pbp_participation.route` is one scalar per play —
the route of the *targeted* receiver — with 14 distinct values and no delimiter.
That was established in W4 and I did not re-derive it; I inherited the
constraint. What `offense_players` supports is *pass-play participation*: the
player was on the field for a team dropback. The gap to true routes run is pass
protection and chip responsibility, near zero for WR, moderate for TE, large for
RB. Any registry entry must keep the qualifier in the name.

---

## 3–5. Feature definitions, chronology, leakage exclusions

Every feature for a row at `(season s, week w)` reads only rows with
`season*100 + week` strictly less. No same-game column, no future week, no
season aggregate spanning the target week.

**Excluded by rule:** same-game realised stats; postgame roster status;
`weekly_rosters.status` (quarantined); market variables; nflfastR
model-derived fields; 2026 anything.

**The leakage probe, predeclared before any result.** Shuffle each player's
target values across his own games — order destroyed, level preserved. An honest
lagged builder must degrade; a builder reading game *t* would not.

| Baseline | real MAE | shuffled | Δ |
|---|---|---|---|
| lag1 | 0.1540 | 0.2506 | **+0.0965** |
| ma3 | 0.1617 | 0.2180 | **+0.0563** |
| ewma3 | 0.1663 | 0.2054 | **+0.0391** |
| season-to-date mean | 0.2027 | 0.1993 | −0.0034 |
| pooled prior | 0.2967 | 0.2954 | −0.0013 |

*(`rpr`, 2024.)* Order-sensitive baselines degrade sharply; order-insensitive
ones do not move. That is the correct signature. It is a **necessary condition,
not a proof** — it cannot detect a leak that is constant within a player.

---

## 6. Baseline formulas

`prior` pooled positional mean over training seasons · `std` season-to-date
player mean · `lag1` previous game · `ma3` / `ma5` trailing means · `ewma3`
half-life 3 games · `shrink{k}` `(n·player_mean + k·prior)/(n+k)` for k = 2, 4, 8.

## 7. Walk-forward design

Train on all seasons strictly before the evaluation season; evaluate on that
season alone. No shuffling. Uncertainty on any model difference is a **block
bootstrap over players**, 1,000 resamples, seed 20260907 — a player's games are
not independent, so the resampling unit is the player and all his games travel
together.

The incumbent is always `lag1`. The challenger is always the best *non-lag1*
baseline. When `lag1` itself wins, comparing "best" to `lag1` gives zero by
construction and answers nothing.

---

## 8. Results by target — unconditional arm

MAE, evaluation seasons. **Bold** = best. The verdict column is the
block-bootstrap on (challenger − lag1); negative and excluding zero means the
challenger genuinely beats persistence.

### snap_share (WR/TE/RB) — persistence wins, decisively

| Season | n | prior | std | **lag1** | ma3 | ewma3 | r (lag1) | challenger vs lag1 |
|---|---|---|---|---|---|---|---|---|
| 2022 | 7,945 | 0.2814 | 0.1931 | **0.1506** | 0.1583 | 0.1651 | 0.711 | +0.0077 [+0.0042,+0.0115] ✗ |
| 2023 | 7,675 | 0.2746 | 0.1882 | **0.1458** | 0.1513 | 0.1558 | 0.731 | +0.0055 [+0.0020,+0.0088] ✗ |
| 2024 | 7,641 | 0.2763 | 0.1962 | **0.1519** | 0.1577 | 0.1613 | 0.711 | +0.0056 [+0.0016,+0.0097] ✗ |
| 2025 | 7,532 | 0.2743 | 0.1932 | **0.1522** | 0.1579 | 0.1605 | 0.710 | +0.0057 [+0.0019,+0.0095] ✗ |

### rpr (WR/TE/RB) — persistence wins

| Season | n | prior | **lag1** | ma3 | ewma3 | r | challenger vs lag1 |
|---|---|---|---|---|---|---|---|
| 2022 | 8,209 | 0.2988 | **0.1555** | 0.1646 | 0.1723 | 0.714 | +0.0091 [+0.0053,+0.0128] ✗ |
| 2023 | 7,941 | 0.2937 | **0.1498** | 0.1553 | 0.1609 | 0.742 | +0.0055 [+0.0017,+0.0095] ✗ |
| 2024 | 7,852 | 0.2967 | **0.1540** | 0.1617 | 0.1663 | 0.726 | +0.0076 [+0.0036,+0.0116] ✗ |
| 2025 | 7,875 | 0.2935 | **0.1556** | 0.1621 | 0.1656 | 0.721 | +0.0065 [+0.0027,+0.0104] ✗ |

### target_share (WR/TE/RB) — the one clean win for smoothing

| Season | n | prior | lag1 | ma3 | **ewma3** | r | ewma3 vs lag1 |
|---|---|---|---|---|---|---|---|
| 2022 | 8,209 | 0.0704 | 0.0504 | 0.0469 | **0.0464** | 0.681 | −0.0041 [−0.0054,−0.0029] ✓ |
| 2023 | 7,941 | 0.0704 | 0.0495 | 0.0458 | **0.0451** | 0.711 | −0.0044 [−0.0056,−0.0032] ✓ |
| 2024 | 7,852 | 0.0716 | 0.0515 | 0.0476 | **0.0467** | 0.691 | −0.0048 [−0.0060,−0.0035] ✓ |
| 2025 | 7,875 | 0.0710 | 0.0504 | 0.0468 | **0.0459** | 0.696 | −0.0045 [−0.0058,−0.0033] ✓ |

Consistent across all four seasons, interval excludes zero every time. The
effect is real and it is **0.005 of share** — about a quarter of a target per
game on a 30-attempt offence.

### carry_share (RB) — nothing beats persistence

| Season | n | prior | lag1 | ma3 | ewma3 | r | challenger vs lag1 |
|---|---|---|---|---|---|---|---|
| 2022 | 2,399 | 0.1988 | **0.1033** | 0.1062 | 0.1075 | 0.743 | +0.0028 [−0.0010,+0.0065] ✗ |
| 2023 | 2,281 | 0.2023 | **0.1051** | 0.1110 | 0.1132 | 0.722 | +0.0059 [+0.0016,+0.0105] ✗ |
| 2024 | 2,199 | 0.2029 | 0.1255 | **0.1197** | 0.1210 | 0.696 | −0.0060 [−0.0118,+0.0000] ✗ |
| 2025 | 2,209 | 0.2060 | 0.1057 | 0.1070 | **0.1054** | 0.777 | −0.0002 [−0.0053,+0.0053] ✗ |

Note 2024 and 2025 point the other way from 2022–23 and neither interval
excludes zero. **This is a target where the ranking is not stable across
seasons**, and picking the per-season winner would be fitting noise.

### rz_carry_share (RB) — smoothing helps in 2 of 4 seasons

| Season | n | prior | lag1 | **ewma3/ma3** | r | vs lag1 |
|---|---|---|---|---|---|---|
| 2022 | 2,237 | 0.2354 | 0.1716 | **0.1641** | 0.550 | −0.0075 [−0.0148,+0.0003] ✗ |
| 2023 | 2,130 | 0.2390 | 0.1653 | **0.1614** | 0.549 | −0.0038 [−0.0102,+0.0028] ✗ |
| 2024 | 2,056 | 0.2451 | 0.1866 | **0.1710** | 0.565 | −0.0159 [−0.0253,−0.0063] ✓ |
| 2025 | 2,069 | 0.2427 | 0.1768 | **0.1629** | 0.598 | −0.0138 [−0.0211,−0.0068] ✓ |

Correlation ≈ 0.55–0.60 — the weakest of the WR/TE/RB share targets. Red-zone
usage is genuinely noisier, and the denominator is small (a team has ~4 red-zone
carries a game).

### QB targets

| Target | Season | prior | lag1 | best | r | verdict |
|---|---|---|---|---|---|---|
| `team_dropbacks` | 2022 | 7.204 | 9.157 | **7.024** (shrink8) | **0.221** | shrinkage beats lag1 ✓ |
| | 2023 | 6.359 | 8.232 | **6.331** | **0.107** | ✓ |
| | 2024 | 6.636 | 8.497 | **6.625** | **0.100** | ✓ |
| | 2025 | 6.909 | 8.871 | **6.724** | **0.188** | ✓ |
| `pass_att_as_passer` | 2022 | 16.865 | **10.680** | 10.680 | 0.617 | persistence ✗ |
| | 2023 | 16.884 | **8.975** | 8.975 | 0.653 | ✗ |
| | 2024 | 16.552 | **9.053** | 9.053 | 0.645 | ✗ |
| | 2025 | 16.418 | **9.188** | 9.188 | 0.651 | ✗ |
| `scrambles` | 2022–24 | ~1.11 | ~0.95 | **~0.87** (ewma3) | 0.46–0.55 | ✓ 3 of 4 |
| `designed_rushes` | 2022–25 | ~1.45 | ~1.27 | **~1.14** (ewma3) | 0.43–0.56 | ✓ 4 of 4 |

**`team_dropbacks` is the striking negative.** Correlation of **0.10–0.22**, and
last week's value is *substantially worse than simply guessing the league mean*
(lag1 8.5 vs prior 6.6 in 2024). A team's pass volume in a given game is
dominated by game script — score, opponent, pace — none of which is in a QB's
own history. **If a projection system multiplies a well-forecast share by a
badly-forecast team volume, the volume term is where the error will come from.**

---

## 9–10. By position and by season

`snap_share`, 2024, MAE under `lag1`:

| Group | n | MAE | r |
|---|---|---|---|
| WR | 3,465 | 0.1640 | 0.704 |
| TE | 2,022 | 0.1424 | 0.716 |
| RB | 2,154 | 0.1413 | 0.651 |

`target_share`, 2024:

| Group | n | MAE (lag1) | r |
|---|---|---|---|
| WR | 3,601 | 0.0609 | 0.627 |
| TE | 2,052 | 0.0455 | 0.603 |
| RB | 2,199 | 0.0415 | 0.430 |

RB target share has the lowest correlation of the three by a wide margin —
receiving work for backs is the least stable role in the study.

**By season the ranking is essentially flat.** Across 2022–2025, `snap_share` r
moves only between 0.710 and 0.731, and `rpr` between 0.714 and 0.742. No
season-over-season trend; nothing here suggests the league is becoming more or
less predictable in this respect.

---

## 11. Stable role vs role change — the main subgroup finding

Role change is the predeclared label
`|snap_share(t−1) − mean snap_share(t−2..t−4)| > 0.20`, computed only from prior
games. 2024, `lag1`:

| Target | Stable | | Role change | | Damage |
|---|---|---|---|---|---|
| | MAE | r | MAE | r | |
| `snap_share` | 0.1231 | **0.803** | 0.2332 | **0.450** | MAE ×1.89, r −0.353 |
| `rpr` | 0.1244 | **0.814** | 0.2382 | **0.473** | MAE ×1.91, r −0.341 |
| `target_share` | 0.0457 | 0.684 | 0.0688 | 0.437 | MAE ×1.51, r −0.247 |
| `carry_share` | 0.1062 | 0.739 | 0.2005 | 0.438 | MAE ×1.89, r −0.301 |

Role change is ~27% of player-games and carries roughly double the error. This
is the subgroup that a pooled average hides, and it is where any further
modelling effort belongs.

Broken down by pregame trigger (2022–2025 pooled, `snap_share`):

| Trigger | n | lag1 MAE | ewma3 MAE | r (lag1) |
|---|---|---|---|---|
| stable | 15,729 | **0.1327** | 0.1386 | 0.793 |
| workload jump prior week | 3,561 | 0.2487 | **0.2354** | 0.484 |
| workload drop prior week | 3,738 | **0.2379** | 0.2430 | 0.321 |
| team change | 573 | 0.2651 | **0.1669** | 0.287 |
| returning from absence | 8,314 | 0.1239 | 0.1560 | **0.161** |

**Two of these need a warning rather than a reading.**

*Team change* is the one case where smoothing clearly wins — `ewma3` cuts MAE
from 0.265 to 0.167. A player's last game on his old team is a bad guide; his
longer average is better. n = 573, so this is suggestive, not settled.

*Returning from absence* looks like the **easiest** bucket on MAE (0.124) and is
the **hardest** on correlation (r = 0.161). That contradiction is the artifact
described in §12: 61.9% of those rows have a snap share of exactly zero, because
most players flagged "returning" do not in fact return. Predicting zero scores
well on MAE and carries no information. **Reading MAE alone here would invert
the conclusion.**

---

## 12. A measurement trap that shapes every number above

The panel is **zero-inflated by construction**, because I added rows for
pregame-identifiable candidates who did not appear (players who played for that
team in any of the previous 4 games). Measured on 2022–2025 WR/TE/RB:

| Target | zero fraction | mean |
|---|---|---|
| `snap_share` | **0.290** | 0.331 |
| `rpr` | **0.285** | 0.340 |
| `target_share` | **0.460** | 0.068 |
| `carry_share` | **0.790** | 0.057 |

Conditional on actually appearing, `snap_share` has zero zeros and mean 0.466.

This is not a defect — it is the honest population for "will he be on the field
and get opportunity", which is what you asked. But it means **MAE rewards
predicting zero**, and any comparison against a published figure computed on
appearances only is not like-for-like. Both arms are reported for that reason;
the conditional arm is §12b.

---

## 13–14. Incremental value, and what failed

Per the directive I stopped at the simple controls, because they did not leave
the kind of headroom that justifies escalating.

| Addition | Verdict |
|---|---|
| recency weighting (EWMA h=3) | **Helps `target_share`** (−0.005, all 4 seasons, interval excludes zero). **Hurts `snap_share` and `rpr`** (+0.006 to +0.009, all 4 seasons). |
| trailing means (ma3, ma5) | Worse than lag1 for snap/rpr; ma5 always worse than ma3 |
| season-to-date mean | Worse than lag1 for every share target |
| shrinkage to positional prior | Worse for every share target; **the best model for QB `team_dropbacks`**, where the player signal is so weak that the prior wins |
| pooled positional prior alone | Always worst except QB team volume |

**Features that failed to help — stated because the directive asks:** every
smoothing scheme tested is a net loss for snap share and route participation.
The signal in those targets is almost entirely "what happened last week", and
averaging it with older weeks destroys information rather than denoising.

**Not tested here, deliberately:** team play volume, pass/run tendency, teammate
prior opportunity, depth-chart vintage, age/experience. The reason is §8: for
five of nine targets nothing beat a one-line persistence rule, so adding
covariates before understanding the role-change subgroup would be optimising the
part that already works.

---

## 15. Unavailable and unsafe fields — including three defects I introduced

**Structurally unavailable:**

- **True routes run.** `pbp_participation.route` is the *targeted* receiver's
  route, one scalar per play, 14 values, no delimiter (W4, not re-derived here).
  Per-player routes-run charting is a paid product. `rpr` is a proxy and must
  keep the qualifier.
- **`ngs_air_yards`** — 0 non-null of 45,919 (W4).
- **Third-down role** — computable in principle; I built `third_targets` but did
  not model it, because the per-game denominator is ~6 plays and the resulting
  share is dominated by sampling noise. Excluded rather than reported thin.
- **Air-yards share** — computed but **not reported**. Its provenance chain runs
  through fields I have not audited for this purpose, and the directive
  conditioned it on provenance being valid.

**Three defects I introduced and then caught. Each would have changed a
conclusion:**

1. **`snap_share` divided by 100 twice.** `snap_counts.offense_pct` is already a
   fraction (2024: min 0.000, max 1.000, mean 0.236, n = 26,615). The first run
   reported MAE **0.0015**, which would have made snap share look like the most
   forecastable quantity in the study by two orders of magnitude. Real value
   0.152.
2. **`scrambles` charged to the passer.** On all 1,134 qb_scramble plays of 2024,
   `passer_player_id` is NULL and `rusher_player_id` is set on 1,062. The column
   was structurally zero for every player in every season and the baselines
   "predicted" it with MAE 0.0000. Now charged to the rusher.
3. **Target share denominated on `pass_attempt`.** Measured: `pass_attempt` =
   19,125 in 2024 and **includes all 1,314 sacks**; 2,112 attempts carry no
   receiver. targets/pass_attempt = 0.8896, and the shortfall varies by
   team-game with the sack rate — so the denominator would have injected
   offensive-line noise into a receiver metric. Denominators are now sums of
   what was counted, so shares total exactly 1.

The first two were caught by results that were *too good*. That is worth saying
plainly: the numbers that looked best were the ones that were wrong.

---

## 16. Open research questions

1. **Role change is the whole problem.** ~27% of player-games, double the error.
   What pregame evidence actually anticipates it? Depth chart vintage, the
   official injury cascade this repo is now capturing, transaction feeds.
2. **Team volume is unforecastable from player history** (r ≈ 0.15). It needs a
   team/game-script model, and it is a multiplicative term — errors there
   propagate into every player projection.
3. **Vacated opportunity does not redistribute proportionally** (§17). What does
   it do? Measuring the true transfer function is a self-contained study.
4. **Is `rpr` good enough as a routes proxy?** The WR/TE/RB gap is unmeasured
   because no ground-truth routes source is reachable.
5. **The appearance question is unsolved and is not a modelling problem yet** —
   it is the prediction-time eligibility debt, still open.

---

## 17. Vacated opportunity — measured, not assumed

The directive says: *do not assume vacated opportunity transfers proportionally
to backups; measure it.*

**Event:** a player with prior-game `target_share` ≥ 0.20 does not appear.
**285 events, 4,231 surviving teammate player-games.**

| Rule | MAE |
|---|---|
| Proportional redistribution — everyone grows in proportion to prior share | **0.0453** |
| Assume no redistribution at all — keep prior share | **0.0384** |

Proportional redistribution beats doing nothing on **625 of 4,231 player-games
(14.8%)**.

**Proportional transfer is not just unsupported — it is worse than ignoring the
vacancy.** Vacated targets concentrate on specific replacements rather than
spreading with existing shares, and a proportional rule systematically
over-predicts the players who were already busy. Any projection system that
redistributes vacated opportunity pro-rata will be wrong in a direction that
correlates with player prominence, which is exactly where a market would price
it first.

---

## 12b. The two arms disagree about which model wins — and this is the finding

Running the identical pipeline conditional on the player actually appearing
**reverses the model ranking for five of the nine targets**.

| Target | Unconditional | Conditional |
|---|---|---|
| `snap_share` | lag1 wins, all 4 seasons | **ewma3/ma3 wins, all 4 seasons** |
| `rpr` | lag1 wins, all 4 seasons | **ewma3/ma3 wins, 3 of 4** |
| `carry_share` | lag1 wins, no stable challenger | **ewma3 wins, all 4 seasons** |
| `rz_carry_share` | mixed, 2 of 4 | **ewma3 wins, all 4, by ×2 the margin** |
| `pass_att_as_passer` | lag1 wins, all 4 seasons | **ewma3 wins, all 4 seasons** |
| `target_share` | ewma3 wins | ewma3 wins, margin doubles |
| `team_dropbacks` | shrinkage wins | shrinkage wins |

Conditional detail, `snap_share`:

| Season | n | lag1 | ewma3/ma3 | r | challenger − lag1 |
|---|---|---|---|---|---|
| 2022 | 5,500 | 0.1386 | **0.1338** | 0.778 | −0.0048 [−0.0081,−0.0014] ✓ |
| 2023 | 5,539 | 0.1319 | **0.1267** | 0.795 | −0.0051 [−0.0078,−0.0025] ✓ |
| 2024 | 5,483 | 0.1377 | **0.1314** | 0.780 | −0.0063 [−0.0098,−0.0024] ✓ |
| 2025 | 5,352 | 0.1403 | **0.1291** | 0.779 | −0.0112 [−0.0143,−0.0079] ✓ |

**Why the reversal happens.** In the unconditional panel a player who did not
play last week has `lag1 = 0`, and most such players do not play this week
either. Persistence therefore wins by exploiting *absence carryover*, not by
describing opportunity dynamics. Smoothing dilutes that zero and is penalised
for it. Remove the non-appearances and the ordering flips everywhere.

**What this means practically.** The apparent superiority of "just use last
week" in the unconditional arm is an artifact of mixing two different questions:
*will he play* and *how much will he be used*. They want different models. Any
future opportunity model should be built as **two stages — P(appear) × usage
given appearance — and the P1 evidence is that fitting them jointly will pick
the wrong usage model.**

This is also the clearest instance of the thing the directive warned about: the
pooled number does not merely hide a subgroup failure, it inverts a model
selection decision.

Correlations are also uniformly *higher* conditionally (`snap_share` 0.78 vs
0.71, `rpr` 0.80 vs 0.72). The unconditional correlation is dragged down by the
0→positive and positive→0 transitions, which are exactly the role-change cases
of §11.

---

## 12c. Best simple model for every target

| Target | Population | Best simple model | MAE | r |
|---|---|---|---|---|
| `snap_share` | conditional | **EWMA half-life 3** | 0.129–0.134 | 0.78–0.80 |
| `snap_share` | unconditional | **previous game** | 0.146–0.152 | 0.71–0.73 |
| `rpr` | conditional | **EWMA half-life 3** | 0.135–0.141 | 0.79–0.81 |
| `target_share` | either | **EWMA half-life 3** | 0.046–0.049 | 0.68–0.75 |
| `carry_share` | conditional | **EWMA half-life 3** | 0.101–0.109 | 0.80–0.82 |
| `rz_carry_share` | conditional | **EWMA half-life 3** | 0.191–0.196 | 0.55–0.60 |
| `team_dropbacks` | either | **shrink-to-prior (k=8)** | 6.2–6.8 | **0.10–0.29** |
| `pass_att_as_passer` | conditional | **EWMA half-life 3** | 8.9–9.2 | 0.53–0.58 |
| `scrambles` | conditional | **EWMA half-life 3** | 1.09–1.14 | 0.45–0.48 |
| `designed_rushes` | unconditional | **EWMA half-life 3** | 1.08–1.28 | 0.43–0.56 |

No advanced model was tested, and none is recommended yet: see §17.

---

## 17. Recommendation for Projection Directive P2

**Do not go to fantasy points next, and do not go to a larger model next.** The
P1 evidence points somewhere else.

**P2 should be the two-stage decomposition, because P1 showed that fitting it
jointly selects the wrong model.** Concretely:

1. **P(appears)** — a separate, honestly-scored classifier. This is where the
   official injury cascade the capture track is now collecting actually pays
   off, and it is the only stage where those artifacts are decision-relevant.
   Scored with log loss and calibration, not MAE.
2. **Usage | appears** — EWMA half-life 3 is the incumbent to beat for every
   share target. It is one line of code and it is not a strawman: on the
   conditional arm it beat persistence on 4 of 4 seasons for five targets.

**Then attack role change, not the stable majority.** 27% of player-games carry
double the error. Improving the stable 73% from r = 0.80 is worth very little;
the open question is whether any pregame evidence anticipates a role change at
all. I would frame P2's second half as that single question, with a predeclared
negative result permitted.

**Treat team volume as a separate team-level problem.** r ≈ 0.15 from player
history, and it multiplies every player projection. It needs game script — total,
spread, pace, opponent — which means it is the first place a market-derived
variable would genuinely help and therefore the first place the "never optimise
toward the book" rule needs a careful reading before anyone starts.

**Do not build the vacated-opportunity redistribution rule that everyone
builds.** Measured here, proportional transfer is worse than ignoring the
vacancy (14.8% win rate). If P2 wants that mechanism, it has to learn the
transfer function, not assume it.

**What I would not do in P2:** add covariates to the share models. For five of
nine targets a one-line EWMA is unbeaten, and the headroom is in the two places
above, not in the part that already works.

## 18. Files and commits changed

Research artifacts only. No production module, no G0A file, no 2026 artifact,
no capture path touched.

```
A  nfl/research/p1/PREDECLARATION_P1.md        written before any result
A  nfl/research/p1/build_panel.py              panel construction
A  nfl/research/p1/model.py                    baselines, walk-forward, bootstrap
A  nfl/research/p1/rolechange.py               role-change + vacated opportunity
A  nfl/research/p1/leakage_probe.py            predeclared chronology probe
A  nfl/research/p1/run_unconditional.log       full output
A  nfl/research/p1/run_conditional.log         full output
A  nfl/research/p1/results_unconditional.json  every metric, every subgroup
A  nfl/research/p1/results_conditional.json
A  TASK_REPORT_2026-09-07_P1_OPPORTUNITY.md    this file
```

The raw nflverse downloads (≈1.4 GB) stay in the scratchpad and are not
committed; they are reproducible from the release URLs and the md5s in §1.

## 19. Markdown task-report path

`TASK_REPORT_2026-09-07_P1_OPPORTUNITY.md`, repository root.

---

## Governance

Research only. Nothing here is promoted by having improved a retrospective
metric, and no promotion is requested. G0A remains **11/12**, Item 1 remains
PARTIAL / PENDING REAL EVENT, NFL-1 remains unexecuted. No DFS, ownership,
market, lineup or wagering logic was written. No wager is recommended or
discussed.
