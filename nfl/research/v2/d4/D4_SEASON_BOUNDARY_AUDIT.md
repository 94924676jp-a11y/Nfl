# D4 — the complete week-1 season-boundary inventory

**CODE CHANGED: NO.** Identification only. Nothing outside
`nfl/research/v2/d4/` was created or modified. No estimator, feature, frozen
parameter or artifact was touched. Frozen QB3 §4 was not read for modification
and `nfl/production/nonqb/layers.py` was not edited. No suite was run, no
market data was opened, no forecast was produced or resealed. Every measurement
below ran from a scratchpad against committed inputs.

Repo `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD `afefd39`. Interpreter `python3.12`. Written 2026-09-14.

Prior art this builds on and does not repeat:
`nfl/research/parallel_pass/ws20/WS20_SEASON_BOUNDARY.md` (16 components).
Where a document and the code disagree, the code wins and the document is named.

---

## 0. The headline, before the inventory

**Mahomes is not the only one.** Three further variables reach participation,
role or opportunity through a prior-season lookup, and two of them fail in the
same *shape* as the incumbent defect — a current-season signal exists and is
subordinated to, or contradicted by, a prior-season one.

| rank | variable | what it does at week 1 | measured |
|---|---|---|---|
| **P0-1** | `qb_allocation.previous_primary*` | the known defect | 59/160 (0.3688), pre-existing |
| **P0-2** | `role_prior.assign_tiers` (`role_prior.py:147-176`) | ranks the **whole** room by prior-season trailing snap share and appends every player the chart ranks **after** every veteran with any history | **47 of 47** week-1 depth-chart rank-1 skill players with no trailing history placed **below tier 1**; 29 of them in tier 4+. Their assigned tier implies a 0.0604 target share against a **realised 0.1031** |
| **P0-3** | `appearance_r7` `f_rate_ewma` and `app_ewma` / `prev_appeared` (`appearance_r7.py:261, 283, 456, 478`) | one slope carries a relationship whose **sign inverts** across the boundary | `f_rate_ewma < 0.3`: in-season appearance **0.3543** (n=3,280) vs **CROSSED 0.7036** (n=307). `prev_appeared == 0`: in-season **0.2778** (n=19,499) vs CROSSED **0.5079** (n=1,134) |
| P1 | `f_team_change` absent from R8 (`appearance_r8.py:94`) | no club-change flag anywhere in the design | **22.96%** of week-1 WR/TE/RB rows with a prior have their last frame row at a different club (329/1,433) against **1.35%** in weeks 2+; their participation prior is biased **−0.0635** against **−0.0091** for stayers |

P0-2 and P0-3 are **live on tonight's board**: `DEN_KC_LIVE_RUN_RECORD.json`
records `model_configuration: V1_CANDIDATE_R8`, and `candidate_mode.py:241-242`
builds `R8_FLAGS` from `R7_FLAGS` → `R6_FLAGS`, which sets
`role_prior = True` (`candidate_mode.py:190`). Thirteen KC receiving rows and
three KC rushing rows were sealed through both.

I am reporting these rather than repairing them, as instructed.

---

## 1. The full inventory

One row per feature or role variable consumed in a week-1 forecast that reaches
backward into a prior season. Grouped by the layer that consumes it. **"Reach"**
is the last column and it is the one that ranks the table.

Legend for reach: **GATE** = can set a player's opportunity to zero ·
**ROLE** = sets his position in the room · **OPPORTUNITY** = scales his share ·
**EFFICIENCY** = conditional rate only · **REPORT** = published but consumed
nowhere numerically · **NONE**.

### 1.1 The quarterback room

| # | feature / variable | current lookup behaviour | prior-season dependency | offseason roster / depth changes represented? | leakage or staleness risk | reach |
|---|---|---|---|---|---|---|
| 1 | `previous_primary_detail` (`qb_allocation.py:117`) and `previous_primary` (`:193`) | `bisect.bisect_left` over `season*100+week`, no season partition | **total** at week 1 — resolves to prior week 18 | **NO** | staleness. No leakage: the cut is strictly earlier | **GATE + OPPORTUNITY** |
| 2 | `was_prev_primary` bit → `qb3_lib.cell_of` (`qb3_lib.py:130`) | cells are `rank × was_prev_primary`; **no week and no opener term** | inherits #1 | NO | week-1 rows pooled with week-8 rows in one cell | **GATE + OPPORTUNITY** |
| 3 | depth-chart QB rank (`qb_allocation.captured_depth_chart`, `:86`) | newest captured chart in `nfl/vintage` | none — current season | **YES.** This is the boundary-aware half of the room | selector is newest-file; `dt` is daily | ROLE |
| 4 | unranked rostered QB → `r = 3` | constant, declared | none | n/a | a populated cell, not a null (27 of 119 QBs) | ROLE |
| 5 | `qb2_lib.attach` `h_games`, `h_db`, `h_att`, `h_cmp`, `h_pyds`, `h_ptd`, `h_int`, `h_drush`, `h_ryds`, `h_seq` (`qb2_lib.py:57-90`) | strict ordinal prefix, **lifetime**, no season and no team reset | **total** at week 1 | NO | staleness; a 2023 season weighs the same as 2025 | EFFICIENCY |
| 6 | `h_share` (dropback share) and `h_team_db_series` (`qb2_lib.py:78, 88`) | same | total | NO — and `h_team_db_series` has no **coach** reset either | under R2 the level is external, so these are dormant on the production path | OPPORTUNITY (dormant under R2) |
| 7 | `rung_weight` `h_games/(h_games+K)` (`qb2_lib.py:154`) | shrink on **lifetime** appearances | — | n/a | the shrink that would protect a stale history is weakest for the longest histories | EFFICIENCY |
| 8 | `qb2_lib.pools(allrows, ev)` (`:107`) | positional pools from seasons **strictly before** `ev` | by design | n/a | none — this is the correct construction | EFFICIENCY |
| 9 | `qb_v1.slate_prospective` cold-start exclusion (`qb_v1.py:203`) | `h_games < 1` rows dropped unless `include_cold_start` | a rookie has no prior season | n/a | OWN-1 measured 5.3168% of allocated team dropbacks reaching nobody on the 2026 week-1 slate. Week 1 is where most debuts land | **GATE** |

### 1.2 Appearance — R7 / R8. This layer gates every non-QB opportunity.

`layers.targets_carries` refuses any player without an appearance draw
(`layers.py:336`), so a zero here is a zero everywhere downstream.

| # | feature / variable | current lookup behaviour | prior-season dependency | offseason changes represented? | risk | reach |
|---|---|---|---|---|---|---|
| 10 | **`prev_appeared`** (`appearance_r7.py:261`, and again at `:456` on the serve path) | `past[-1]['appeared']` — the player's last **frame** row | total at week 1 (prior wk 18) | NO | **the relationship inverts.** See §2.1 | **GATE** |
| 11 | **`app_ewma`** (`:283`, `:478`), half-life 3 frame rows | EWMA over **all** prior frame rows, no reset | ≈100% of the weight at week 1 | NO | **non-monotone after crossing.** See §2.1 | **GATE** |
| 12 | `crossed` (`:263`) and `week == 1` (`:333`) | two indicator columns | — | — | **this is the repair, and it is only an intercept.** An intercept cannot correct a slope whose sign flips | GATE |
| 13 | `cm_within` `min(·,4)/4` (`:335`) | within-season absence run, reset at the boundary | none — correctly reset | n/a | none | GATE |
| 14 | `cm_carried` `min(·,4)/4` (`:337`, `appearance_r8.py:263`) | carried absence run, **capped at 4** | total | NO | WS20 #3: 576/576 identical design rows for cm=4 vs cm=13, 32.3 realised points apart | GATE |
| 15 | `n_prior` `min(·,20)/20` (`:344`) | lifetime frame-row count | total | n/a | saturates; no calendar | GATE (weak) |
| 16 | `rank` from `depth_vintage` (`appearance_r7.py:449`) | captured chart, current | none | **YES** | daily `dt`, 171/177 slices not durable | ROLE |
| 17 | `inj_status`, `inj_practice`, `inj_available` (`:481-484`) | current-season injury feed | none | **YES** | perishable; DEN filed one blank row tonight | GATE |
| 18 | `n_cur` and the reliability weight `w = n_cur/(n_cur+k)` (`appearance_r8.py:256`) | current-season appearances | none by construction | n/a | **degenerate at the boundary**: `n_cur == 0` on **3,046 of 3,046** crossed rows and 90.6% of week-1 rows, so eight R8 columns are identically zero there | GATE (null at wk 1) |
| 19 | depth bucket × `(1 − w)` (`appearance_r8.py:289`) | depth carries **full** weight when `w = 0` | none | **YES** | this is the good half: at the boundary R8 reduces to R7 plus depth at full strength | ROLE |
| 20 | `f_rate3`, `f_rate5`, **`f_rate_ewma`** (`stage_a.py:137-147`) | per-player rolling means and EWMA(hl 3) over `past`, **no season reset** | ≈100% at week 1 | NO | **`f_rate_ewma` is the inverted one.** §2.1 | **GATE** |
| 21 | `f_prev_snap`, `f_snap_ewma` (`stage_a.py:151-160`) | last / EWMA snap share, no reset | total | NO | prior-season workload read as current | GATE + OPPORTUNITY |
| 22 | `f_weeks_since_appear` (`stage_a.py:148`) | index distance in the player's frame-row list | total | NO | WS20 #4: 0.8377 in-season vs 0.6283 crossed at `wsa = 1`. My `prev_appeared == 1` split reproduces it at 0.8381 / 0.6281 | GATE |
| 23 | `f_snap_before_absence` (`p3_features.py:104`) | workload before the current absence run | total | NO | at week 1 this is a rest-game or a benching | GATE |
| 24 | `f_swing`, `f_volatility` (`p3_features.py:96-99`) | last-4 / last-5 snap-share dispersion | total | NO | prior-season volatility read as current | GATE |
| 25 | `f_vac_snap` / `_route` / `_target` / `_carry` (`p3_features.py:73-84`) | the team's **previous game** by team ordinal, crossed with a current injury row | total at week 1 | **partially — a departed teammate has no current injury row, so he contributes nothing; a new teammate has no prior-club row, so he also contributes nothing.** Both directions deflate | **deflated by 2.5×**: mean `f_vac_target` **0.00250** at week 1 vs **0.00615** in-season | OPPORTUNITY |
| 26 | `f_n_teammates_out` (`p3_features.py:86`) | same construction | total | same | **deflated by 4.5×**: 0.0163 at week 1 vs 0.0727 in-season | OPPORTUNITY |
| 27 | `f_prev_practice`, `f_practice_seq`, `f_practice_improving/worsening` (`p3_features.py:56-66`) | `inj.get((season, week-1, …))` | looks up week 0, which does not exist | n/a | **safe.** Falls to the declared `'none'` for every player. WS20 #15, confirmed | NONE at wk 1 |
| 28 | **`f_team_change`** (`stage_a.py:159`) | exists in the frozen P2 block | — | it is **the** offseason flag | **it is not in `appearance_r8.V1_NUMERIC` (`appearance_r8.py:94`) and reaches no model.** See §2.3 | would be GATE |
| 29 | `p1/model.extend_with_zeros` candidate set `ords[idx-4:idx]` | team candidate set from the last 4 team games, ordinals sorted across seasons | total in the **training** frame | NO | WS20 #13, PARTIAL — the R7 union frame repairs the prediction-time denominator | GATE (training only) |
| 30 | R7 boundary logic **duplicated** at `_walk` (`:254`) and inline in `predict` (`:452-479`) | two copies of `prev_appeared`, `crossed`, `cm_within`, `cm_carried`, `app_ewma` | — | — | **DUPLICATED.** A repair applied to one and not the other would pass the frame tests and ship a different serve path | — |

### 1.3 Role, share and opportunity

| # | feature / variable | current lookup behaviour | prior-season dependency | offseason changes represented? | risk | reach |
|---|---|---|---|---|---|---|
| 31 | **`role_prior.assign_tiers`** (`role_prior.py:147-176`) | players **with** trailing snap share are ranked 1..n by it; everyone else is appended **after** them by depth rank (`start = len(known)`, `:170`) | trailing snap share is 100% prior-season at week 1 | **the captured depth chart is present and is used only as a fallback for players with no history** — so it cannot promote anyone | **the severe one.** §2.2 | **ROLE + OPPORTUNITY** |
| 32 | `role_prior.build` `trail`, `TRAIL = 8` (`role_prior.py:56, 80`) | trailing mean of the last 8 appeared snap shares, **no season and no team reset** | total | NO | a player's tier is his old club's usage | ROLE |
| 33 | `role_prior.build` `tier_mean`, `k` (`:95-130`) | fitted on all rows `ord < cut`, EB `k = within/between` | by design, prior seasons | n/a | correct construction; ≥50 obs per tier enforced | OPPORTUNITY |
| 34 | `role_prior.weight` `n/(n+k)` (`:178`) | **lifetime** own-history count | total | NO | **with `n = 0` it returns the tier mean exactly** — which is why #31 is decisive: for a no-history player the tier *is* the whole forecast | OPPORTUNITY |
| 35 | `p4c_params.class_point_forecast` `C` (`p4c_params.py:130`, `:193`) | `p4c_build.ewma(h, hl=3)` over prior **appeared** class shares, no season and no team reset | 50% of weight on the last 3 appeared games | NO | **scored.** §2.4 — small, sign-flipped, CI-excluding for targets; null for carries | **OPPORTUNITY** |
| 36 | `p4c` positional fallback `pri[pos]` (`:191`) | training-mean share by position | prior seasons by design | n/a | 0.1253 for every WR — the flatness R6 exists to repair | OPPORTUNITY |
| 37 | `participation_prior.share_prior` `ewma_hl2` (`participation_prior.py:103`) | EWMA half-life 2 over prior appeared pass-snap shares, no season and no team reset | ~50% of weight on the prior season's **last two games** | NO | **scored, and it is the worst of its family at week 1.** §2.5 | **REPORT** — see the correction in §3 |
| 38 | `PARTICIPATION_HISTORY_STALE` guarded by `if week >= 2` (`participation_prior.py:120`) | the module's own staleness refusal **exempts week 1** | — | — | WS20 #8. The comment names the failure — *"last season weighted as if it were last week"* — and week 1 is exempted from the refusal that names it | REPORT |
| 39 | `roster_status` ACT/DEV/RES/CUT pool filter (R5) | current-season weekly roster, raw retained file | none | **YES** | not a boundary defect, but its *magnitude* peaks at week 1: the opening-week roster capture carries the most offseason churn (measured 45 SF/LA skill rows → 29 ACT, 10 DEV, 3 RES, 3 CUT) | OPPORTUNITY |

### 1.4 Team environment

| # | feature / variable | current lookup behaviour | prior-season dependency | offseason changes represented? | risk | reach |
|---|---|---|---|---|---|---|
| 40 | `p4b_volume.baselines` `last_game`, `roll3`, `roll5`, `ewma`, `team_expanding` (`p4b_volume.py:76-88`) | team history, ordinals sorted across seasons | total at week 1 | NO | `last_game` is the pure pathology and is **not selected anywhere** — week-1 MAE 11.08 vs 7.25 for `league_mean` | OPPORTUNITY |
| 41 | `coach_prior` (`p4b_volume.py:87`) | **expanding lifetime mean** over every game the coach has coached, keyed on **name only** | total | **NO — no reset on a club change** | selected for `dropbacks_part`, `carries`, `rz_carries`. Exposure 11/160 week-1 team-games (6.9%). Being an expanding mean it is *insensitive* to week-18 rest and *fully* sensitive to a scheme move | OPPORTUNITY |
| 42 | `prev_season` baseline (`p4b_volume.py:85`) | prior-season team mean | by design | NO | boundary-**aware** by construction; available and mostly not selected | OPPORTUNITY |
| 43 | head-coach identity (`team_volume_v1.coaches`, `:85`) | current captured schedule | none | **YES** | the boundary-aware half of #41 | OPPORTUNITY |
| 44 | joint residual pool by coach (`team_volume_v1.py:533-575`) | residuals resampled from that coach's own games; global pool fallback | total | NO | a first-year head coach falls back and it is counted (`rows_on_global_fallback`) | OPPORTUNITY |
| 45 | `rushing_a1._centre` (`rushing_a1.py:619` → `a1_lib.py:164`) | team category-share EWMA hl 2, shrunk `n/(n+4)` on **lifetime** team-games | 50% of weight on the prior season's final two games | NO | WS20 #9: shrink weight 0.9615–0.9619 on the committed frozen params; **cost measured and null at n=64** | OPPORTUNITY |

### 1.5 Conversion and efficiency

| # | feature / variable | current lookup behaviour | prior-season dependency | offseason changes represented? | risk | reach |
|---|---|---|---|---|---|---|
| 46 | `frozen_priors.receiving_priors` `own[pid]` — `h_n`, `h_tgt`, `h_rec`, `h_V_flat` (`frozen_priors.py:83-99`) | the player's **last** row's lifetime history plus that row folded in | total | NO | catch rate and the per-catch yardage pool are lifetime and cross clubs | EFFICIENCY |
| 47 | `pos_catch_rate`, `pos_yardage_pool` (`frozen_priors.py:82`) | RC1 pools, seasons strictly before | by design | n/a | correct | EFFICIENCY |
| 48 | `td_priors` B_pos (`frozen_priors.py:123`) | TD2 per-position rate, seasons strictly before | by design | n/a | correct | EFFICIENCY |
| 49 | `shared_pass.untargeted_rate` (`shared_pass.py:57`) | one rate read from `history_levels.json` | fixed historical artifact | n/a | not week-1 sensitive; refuses if the artifact is absent | EFFICIENCY (mode `off` by default) |

### 1.6 The boundary-aware components — named so the list is complete

`depth_vintage.captured`, `roster_status.status_map`, `readiness`/injuries,
`inactives`, `team_volume_v1.coaches`, and the `pools(…, ev)` / `fit_params(…,
ev)` / `build(…, ordinal_cut)` training cuts. Every one of these reads a
current-season source or partitions correctly on season. **They are where the
offseason actually is represented**, and in two cases (#31, #2) a correct
current-season signal is present and is overridden by a prior-season one. That
is the shape worth naming.

---

## 2. The measurements

### 2.1 R7's own carried features invert across the boundary — NEW

WS20 finding 4 reported the `wsa = 1` arm of this and stopped there. The
decisive fact is in the **other** arm, and in `f_rate_ewma`, neither of which
appears in WS20's table.

Built on `appearance_r8.enriched_frame()`, 59,784 rows, 2020–2025.

`prev_appeared` (`appearance_r7.py:261`):

| | in-season | crossed |
|---|---|---|
| `prev_appeared == 1` | **0.8381** (n=35,886) | **0.6281** (n=1,912) |
| `prev_appeared == 0` | **0.2778** (n=19,499) | **0.5079** (n=1,134) |
| spread | **56.0 pts** | **12.0 pts** |

`f_rate_ewma` (`stage_a.py:141`), the V1 block's appearance EWMA:

| bucket | in-season | crossed |
|---|---|---|
| [0.00, 0.30) | **0.3543** (n=3,280) | **0.7036** (n=307) |
| [0.30, 0.70) | 0.4954 (n=15,364) | 0.4430 (n=860) |
| [0.70, 0.95) | 0.7945 (n=13,064) | 0.6131 (n=791) |
| [0.95, 1.01) | 0.8973 (n=17,816) | 0.7828 (n=870) |

In-season the function is monotone increasing over a 54-point range. After
crossing it is **non-monotone**, and its **lowest** bucket carries the
**second-highest** realised rate. `app_ewma` (R7's own, `:283`) shows the same
inversion at the bottom: 0.4863 at [0.00, 0.20) against 0.4270 at [0.20, 0.50).

R8 carries every one of these on a **single slope** (`appearance_r8.py:290-304`,
`appearance_r7.py:339-343`). The boundary is represented by two indicator
columns and a capped absence streak — all three of which shift an **intercept**.
None can correct a slope whose sign flips.

**This is the Mahomes mechanism in the appearance layer.** "He was not playing
at the end of last season" is read as "he is not playing", when the players who
survive to a week-1 frame row with a low prior-season appearance rate are
precisely the re-signed, the recovered and the promoted.

### 2.2 `role_prior.assign_tiers` cannot promote anyone the chart promoted — NEW, SEVERE

`assign_tiers` (`role_prior.py:158-176`) sorts players **with** a trailing snap
share first, then appends everyone else at `start = len(known)`. A player the
current depth chart ranks first, but who has no prior-season snap history, is
therefore placed below **every** veteran with any history at all.

Replayed exactly, week 1 of 2021–2024, WR/TE/RB, trailing window `TRAIL = 8`,
depth charts `dc_2021…dc_2024`:

* 384 (team, position) rooms, 1,344 week-1 skill rows.
* **47** players whom the week-1 chart ranks **first** carry no trailing snap share.
* **47 of 47 (1.0000)** are placed below tier 1. Assigned tiers: 8 → tier 2, 10 → tier 3, **29 → tier 4+**.
* 223 ordered pairs where the chart's own ranking is inverted by the assigned tier.

What it costs, in the quantity the prior forecasts:

| | mean realised week-1 target share |
|---|---|
| those 47 players, realised | **0.1031** |
| assigned tier 2 (n=383) | 0.0854 |
| assigned tier 3 (n=312) | 0.0568 |
| assigned tier 4+ (n=265) | 0.0548 |
| **their tier-weighted implied share** | **0.0604** |

and for context, realised week-1 target share **by depth-chart rank**: rank 1
**0.1236** (n=696), rank 2 0.0530, rank 3 0.0290 — the chart is strongly
informative and is being discarded for exactly the players for whom it is the
only information.

`role_prior.weight` (`:178`) returns the tier mean **exactly** when `n_own = 0`,
so for these 47 the tier is not a prior nudging a history — it **is** the whole
forecast. The prior understates their opportunity by **41%**.

Roughly twelve such players per opening slate. This is a P0 and, in my
judgement, the finding in this pass comparable in severity to the incumbent
defect: same shape (a current-season signal subordinated to a prior-season
one), same layer of consequence (role → opportunity), and live tonight.

### 2.3 `f_team_change` — the exposure is larger than WS20 measured

WS20 #6 measured 15.17% of week-1 crossed **appearance frame** rows at a
different club. On the participation panel (`panel_p3.csv.gz`, WR/TE/RB with a
prior, 2020–2025) the figure is higher, and the consequence is now measured:

| | n | share at a different club | mean prior | mean realised | bias | MAE |
|---|---|---|---|---|---|---|
| **week 1**, same club | 1,104 | — | 0.5266 | 0.5175 | **−0.0091** | 0.1563 |
| **week 1**, changed club | 329 | **0.2296 of all wk-1 rows** | 0.4971 | 0.4336 | **−0.0635** | 0.1966 |
| weeks 2+, same club | 31,161 | — | 0.4764 | 0.4798 | +0.0035 | 0.1276 |
| weeks 2+, changed club | 427 | 0.0135 | 0.3095 | 0.1892 | **−0.1203** | 0.2096 |

A club change is **17× more common at week 1** than in-season, the bias on those
rows is **7× larger** than on stayers, and the one flag that would carry it
(`stage_a.py:159`) is not in `appearance_r8.V1_NUMERIC`.

### 2.4 `p4c` `C`: WS20's UNRESOLVED finding 7, now settled — and only half as predicted

WS20 could not score this because `nfl/research/p4b/panel_enriched.pkl` is
absent, and predicted "it comes back null too". **Half right.**

I scored a *proxy* for `C` built from `panel_p3.csv.gz` — `s_targets` as
`targets / Σ team targets in the game`, `s_carries` likewise — using the frozen
`p4c_build.ewma`, strictly-earlier prefix cuts, appeared rows only, MAE against
realised, 1,500-resample bootstrap clustered by team. **This is not the
production panel and the numbers are not `p4c`'s own**; the comparison between
estimators on one panel is what is being read.

| class | week | production `ewma_hl3` MAE | best alternative | Δ | team-clustered 95% CI | excludes 0 |
|---|---|--:|---|--:|---|---|
| targets | **1** (n=1,433) | 0.05291 | `ewma_hl6` 0.05198 | **−0.00093** | [−0.00142, −0.00047] | **yes** |
| targets | 2+ (n=31,588) | 0.04793 | `ewma_hl6` 0.04843 | **+0.00051** | [+0.00037, +0.00064] | **yes** |
| carries | **1** (n=395) | 0.11827 | `prev_season_mean` 0.11843 | +0.00015 | [−0.00548, +0.00584] | no |
| carries | 2+ (n=8,924) | 0.10656 | — | — | all worse | — |

**The sign flips.** A longer half-life is better at week 1 and worse in-season,
both with CIs excluding zero. That is the signature of an estimator selected on
pooled weeks being applied at the one week where recency and the boundary
diverge maximally. The magnitude is small — 1.8% of MAE — and carries should be
read as **null**.

### 2.5 `participation_prior` `ewma_hl2` is the worst of its family at week 1

Same design, replicating `participation_prior._history` / `share_prior` exactly
(`s2_lib.ewma`, half-life 2.0, appeared rows, `team_dropbacks_part > 0`,
strictly-earlier `bisect`), 2,000-resample bootstrap clustered by team.

| estimator | week-1 MAE (n=1,433) | Δ vs production | 95% CI | excl 0 | weeks-2+ MAE (n=31,588) | Δ |
|---|--:|--:|---|---|--:|--:|
| **`ewma_hl2` (production)** | **0.1655** | — | — | — | **0.1287** | — |
| `ewma_hl2`, prior-season wk ≥ 17 dropped | 0.1603 | −0.0053 | [−0.0083, −0.0022] | **yes** | 0.1287 | −0.0000 |
| prior-season mean | 0.1594 | −0.0062 | [−0.0097, −0.0026] | **yes** | 0.1337 | +0.0051 |
| `ewma_hl4` | 0.1589 | −0.0066 | [−0.0085, −0.0048] | **yes** | 0.1349 | +0.0062 |
| `ewma_hl8` | **0.1585** | **−0.0070** | [−0.0102, −0.0038] | **yes** | 0.1422 | +0.0135 |
| career mean | 0.1673 | +0.0018 | [−0.0033, +0.0068] | no | 0.1573 | +0.0286 |

The ordering **reverses completely** between week 1 and weeks 2+: the accepted
`ewma_hl2` is the best in-season and the worst of the recency family at the
opener, by 4.2% of MAE. And `week >= 2` at `participation_prior.py:120` exempts
week 1 from the staleness refusal whose own comment describes this exact
failure.

**But read §3 before ranking this.**

### 2.6 A hypothesis I formed and withdrew

I expected the week-17/18 rest effect that drives the QB defect to depress
skill-player pass-snap shares in the same way. It does not. Within player-season,
`mean(final 2 games) − mean(weeks ≤ 15)` is **+0.0200** (n=1,873, median +0.0134,
SD 0.1969); only **45.8%** of players are lower in the final two. Survivorship
runs the other way for skill players — the ones still on the field in week 18
absorb the snaps of the ones who are not. **The rest mechanism does not transfer
from the QB room to the receiving room, and I withdraw the expectation.** What
remains at #37 is a half-life misspecification, not a rest artefact.

---

## 3. A correction that changes the ranking: participation share is binarised

`layers.participation` computes `out[pid] = a * s` (`layers.py:266`) — the
appearance draw times the participation prior. Both numeric consumers then do:

* `layers.targets_carries`, `layers.py:358`: `A = (A > 0).astype(np.float32)`
* `football_engine`, `football_engine.py:1018`: `(A > 0).astype(np.float32)`

Since `s > 0` for all but a handful of players, `a*s > 0` **iff** `a > 0`. The
participation prior's **value therefore does not reach the target or carry
allocation at all.** It survives in exactly two places:

1. the published board metric `participation` (`football_engine.py:1423`), and
2. a **deterministic zero** when the EWMA is exactly 0 — measured at the 2026
   week-1 cut: **9 of 1,120** players with prior history.

So §2.5 is real as a forecast-quality defect in a **published number**, and is a
**GATE** for nine players, and is **not** an opportunity defect for anyone else.
I rank it P2 rather than P0 for that reason. Had I not traced it, the natural
reading of WS20 #8 plus §2.5 would have put it near the top. This is what the
"can it affect participation / role / opportunity" column is for, and it is the
column that demoted my own finding.

---

## 4. WS20: confirmed, extended, overturned

**Confirmed, not re-derived:** #1 and #2 (the QB3 defect and the missing week
term), #3 (the `cm_carried` cap), #13 (`extend_with_zeros`), #14 (team volume —
the crossing is present and is not the defect), #15 (`f_prev_practice` fails
safe — my read of `p3_features.py:56` agrees), #16 (R7's `crossed`/`cm_within`
are correctly specified).

**Extended:**

* **#4/#5 → §2.1.** WS20 had `f_weeks_since_appear` as a mechanism and a PARTIAL
  cost, reported on the `wsa = 1` arm. The zero arm and `f_rate_ewma` **invert**,
  which is a stronger and different claim than attenuation: no intercept repair
  can address it. `prev_appeared` and `app_ewma` were not in WS20's table at all.
* **#6 → §2.3.** Exposure 22.96% on the participation panel against WS20's
  15.17% on the appearance frame, plus a first measurement of the bias.
* **#7 → §2.4.** WS20 marked it UNRESOLVED and predicted null. Scored on a
  proxy: **null for carries, sign-flipped and CI-excluding for targets.**
* **#8 → §2.5 and §3.** Scored, and then partly **demoted** by tracing its reach.
* **#12 → row 25/26.** WS20 called `f_vac_*` PARTIAL without a number. Measured:
  2.5× and 4.5× deflation at week 1.

**Overturned / corrected:**

* WS20's summary — *"the crossing is near-universal and the demonstrated damage
  is narrow"* — **no longer holds.** Three variables now carry demonstrated
  week-1 damage beyond QB3: `assign_tiers` (§2.2, 47/47, 41% understatement),
  the inverted appearance slopes (§2.1), and the club-change bias (§2.3).
* WS20's prediction for finding 7 (*"the prior should be that it comes back null
  too"*) is **half wrong** (§2.4).
* Nothing in WS20 is contradicted on the components it scored. #9, #14 and #15
  remain falsified as costs and I did not relitigate them, as instructed.

**Not relitigated, per the brief:** A1's `hl = 2` boundary cost, the p4b
walk-forward selection, `f_prev_practice`.

---

## 5. Evidence ceiling

1. **Every ablation here is exploratory.** The alternative estimators in §2.4
   and §2.5 were chosen after inspecting the frame. No pre-registration, no
   held-out fold. They are directions, not verdicts.
2. **§2.4 uses a proxy panel.** `p4c_build.load_panel` needs
   `nfl/research/p4b/panel_enriched.pkl`, which is absent from this checkout.
   My `s_targets` is reconstructed from `panel_p3`. The estimator *ordering* is
   what is being read; the absolute MAEs are not `p4c`'s.
3. **§2.2 replays `assign_tiers`' logic against `dc_2021…dc_2024`**, not against
   the vintage-selected chart production would use. `depth_vintage`'s own
   ceiling says 171 of 177 captured `dt` slices persist nowhere, so a faithful
   historical replay of the production selector is not possible here. The
   inversion is a property of the code at `role_prior.py:170` and does not
   depend on which chart is supplied; the 47 and the 41% do.
4. **No equivalence margin was predeclared and no TOST was run.** Nothing here
   may be written as "unbiased", "stable" or "correct"; a null is "not
   distinguishable", not "equal".
5. **`crossed` is a frame-frequency fact, not a calendar fact.** WS20's ceiling
   item 5 applies unchanged to every "crossed" row above.
6. **Four eval seasons.** §2.2 rests on 47 players over four openers. §2.4's
   carries arm is n=395. Neither subgroup is established.
7. **Nothing here is validated on 2026.** Tonight's board is one game.

---

## 6. Reproduction

Measurement scripts were run from a scratchpad and are not committed; each
measurement names the module and function it calls.

```
# §2.1, rows 18/25/26 — the 59,784-row union frame
python3.12 -c "import sys;sys.path.insert(0,'/home/user/nfl');\
from nfl.production.nonqb import appearance_r8 as R8;\
rows=R8.enriched_frame().value;print(len(rows))"

# §2.2 — nfl/research/inputs/dc_2021..dc_2024.csv.gz + panel_p3.csv.gz,
#        replaying role_prior.TRAIL / MAX_TIER / assign_tiers ordering
# §2.3, §2.5 — nfl/research/inputs/panel_p3.csv.gz through s2_lib.ewma
# §2.4 — nfl/research/inputs/panel_p3.csv.gz through p4c_build.ewma
# §3 — read at nfl/production/nonqb/layers.py:266, :358 and
#      nfl/production/nonqb/football_engine.py:1018, :1423
```
