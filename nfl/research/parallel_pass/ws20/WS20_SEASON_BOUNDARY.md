# WS20 — where "last observed" silently becomes "current expected"

**CODE CHANGED: NO.** Research only. No file outside
`nfl/research/parallel_pass/ws20/` was created or modified, no repo file was
edited, no suite was run, no market data was opened, no forecast was produced
or resealed. Every ablation below was run on a scratchpad copy of the design
row and never written back.

Repo HEAD `57d38ad`. Interpreter `python3.12`. Written 2026-09-14.

## The question, and the shape of the answer

The calibration case is `QB3_WEEK1_SEASON_BOUNDARY`: `qb_allocation.py:193
previous_primary()` resolves the incumbent quarterback by ordinal with
`bisect`, so in week 1 it returns the prior season's **week-18** starter, the
game clubs most often rest a starter in.

That is one instance of a class. The class is: **a feature whose semantics are
"the most recent observation" or "the trailing window", built over an ordinal
history that is never partitioned by season, so an offseason gap is indexed as
one game step.** This pass enumerates the class across the repository.

The headline result is not uniform, and two of the components I expected to be
worst came back clean. Reported that way.

## Finding table

| # | component | crossing feature | what "last observed" means there | defect in week 1? | measured effect | status |
|---|---|---|---|---|---|---|
| 1 | `nfl/production/nonqb/qb_allocation.py:193` `previous_primary` / `:117` `previous_primary_detail` | `bisect` over `season*100+week` | prior season's **final** game primary passer | YES — already recorded | prior audit: chart QB1 == prior-season FINAL-game primary in only **59/160** week-1 rooms (0.3688), vs modal primary 77/160; 40.1% of team-seasons end with a non-modal primary | **CONFIRMED (pre-existing, `QB3_WEEK1_SEASON_BOUNDARY`)** |
| 2 | `nfl/research/qb3/qb3_lib.py:130 cell_of` / `:138 fit` | cells are `rank × was_prev_primary`, **no week or opener term** | week-1 rows (bit derived from week 18) are pooled with week-8 rows (bit derived from last week) into one cell | YES | the audit's own contract check: *"s4 … NO WEEK TERM EXISTS"* | **CONFIRMED (pre-existing, recorded in `QB3_WEEK1_INCUMBENT_AUDIT.json`)** |
| 3 | `nfl/production/nonqb/appearance_r8.py:263 featurise` — `min(cm_carried,4)/4.0` | carried absence streak, **capped at 4** | a player who missed the prior season's last 4 games and one who missed its last 13 are the **same design row** | YES, as an expressiveness failure | counterfactual on 576 week-1 crossed rows: forcing `cm_carried` to 4 and to 13 produced **identical design rows in 576/576 cases, 0 different**. Realised rates inside that one feature value: `cm==4` 0.6667 (n=228) vs `cm>=13` 0.3438 (n=32), a 32.3-point spread | **CONFIRMED** |
| 4 | `appearance_r8.py:94 V1_NUMERIC` + `:299` — `f_weeks_since_appear` | index distance in the player's frame-row list | "1" means *played the immediately preceding frame row*; at week 1 that row is the prior season's week 18 | YES, as a shared-slope failure | same feature value, different populations: `IN_SEASON, wsa=1` appearance rate **0.8377** (n=35,906) vs `WEEK-1 CROSSED, wsa=1` **0.6283** (n=1,913) — a 20.9-point gap the design carries on one slope | **CONFIRMED as a mechanism; PARTIAL as a cost** (see §3) |
| 5 | `appearance_r8.py` V1 block generally — `f_rate3`, `f_rate5`, `f_rate_ewma`, `f_prev_snap`, `f_snap_ewma`, `f_swing`, `f_volatility`, `f_snap_before_absence` (built in `nfl/research/p2/stage_a.py:117 build`, `nfl/research/p3/p3_features.py:41 enrich`) | per-player rolling windows and EWMAs over `past`, **no season reset** | prior-season usage read as current usage | YES | `f_rate_ewma` half-life is 3 games: **50.0%** of a week-1 player's value sits on his last three frame rows, all prior-season | **CONFIRMED as a mechanism** |
| 6 | `appearance_r8.py:94` — **`f_team_change` is absent from `V1_NUMERIC`** | — | R8 drops the one boundary-relevant flag the frozen P2 block carried (`stage_a.py:159`) | YES | **15.17%** of week-1 crossed frame rows (428/2,822) belong to a player whose **last frame row was at a different club**, vs 6.49% in-season; 16.5% (467/2,822) have ≥1 of their last three frame rows at another club | **CONFIRMED** |
| 7 | `nfl/production/nonqb/p4c_params.py:130 class_point_forecast` (production) and `nfl/research/p4c/p4c_build.py:73 prepare_class` / `:88 fit_params` | `hist[gsis_id]` over all prior **appeared** rows, `ewma(hl=3)`; **no season reset, no team reset** | the point forecast `C` of a *team-relative* share is a prior-season share, possibly of a different team's denominator | YES | 50.0% of week-1 `C` sits on the player's last three appeared games; `RP.weight` shrink is `n/(n+k)` on **lifetime** n, so the shrink that would protect a stale history is weakest exactly for the longest histories. Docstring states this as a feature: *"With a long history the shrinkage weight goes to one"* | **CONFIRMED as a mechanism; UNRESOLVED as a cost** (§5) |
| 8 | `nfl/production/nonqb/participation_prior.py:120` | `PARTICIPATION_HISTORY_STALE` refusal is guarded by **`if week >= 2`** | the module's own comment names the failure: *"last season weighted as if it were last week"* — and week 1 is exempted from the refusal that names it | YES, by declaration | `week2_data_debt.json` asserts *`"why_week_1_is_safe": "a week-1 forecast conditions only on PRIOR seasons"`*. That is safety in the **data-availability** sense and is the defect in the **semantic** sense. The two uses of "safe" are not distinguished anywhere | **CONFIRMED as an unexamined assumption** |
| 9 | `nfl/production/nonqb/rushing_a1.py:619 _centre` → `nfl/research/own9/a1_lib.py:164` | team category-share EWMA `hl=2`, shrunk `n/(n+4)` on **lifetime** team-games | prior season's final two games are half the team's rushing split | YES, structurally | read off the **committed** frozen params `nfl/derived/rushing_a1_params_2026w01.json`: every team's `n` is 100–101 so the shrink weight is **0.9615–0.9619** (league share contributes <4%); EWMA weight on the last game 0.2929, last two **0.5000**. Dropping the last two 2025 games moves the RB share by 0.0288 mean / **0.1419 max (NO)** against a cross-team SD of 0.0441. **Cost measured and null** — see §5 | **CONFIRMED as a mechanism; FALSIFIED as a cost at n=64** |
| 10 | `nfl/research/q6/frame.py:118 attach_role_class` and `nfl/research/q6/forward_chain.py:173 role_base` | `trail[pid]` / `hist[pid]`, trailing 8, `n/(n+k)` on lifetime n | week-1 role class and share base are the prior season's last 8 appeared games, ranked inside the **new** team | YES | inherits finding 6 (15.17% changed club). q8 (`repair.py`) imports both, so it inherits them too | **CONFIRMED as a mechanism** |
| 11 | `nfl/production/nonqb/role_prior.py:69` / `:133` | `trail[gsis_id]`, `TRAIL=8`, no season or team reset | same as 10, in production | YES | same population | **CONFIRMED as a mechanism** |
| 12 | `nfl/research/p3/p3_features.py:73` `f_vac_*`, `f_n_teammates_out` | `prev = by_tw[(tm, ords[i-1])]` — the team's previous **game** | at week 1, "what a teammate held last week" is his 2025 week-18 usage, crossed with a 2026 injury designation | YES, as a composite | a departed teammate carries no 2026 injury row, so the value is not fabricated — but a returning teammate's vacated share is a rest-game share | **PARTIAL** |
| 13 | `nfl/research/p1/model.py:66 extend_with_zeros` — `ords[idx-4:idx]` | team candidate set = who appeared in the team's last 4 games, **ordinals sorted across seasons** | the week-1 candidate set is the prior season's weeks 15–18 roster | YES, in the **training** frame | the R7 union frame repairs the denominator at prediction time but the panel half of the training frame still carries it. Visible as the inversion at exactly `cm_carried == 4` (rate 0.6667 against 0.2768 at 3) | **PARTIAL** |
| 14 | `nfl/research/p4b/p4b_volume.py:59 attach` / `:76 baselines` → `nfl/production/team_volume_v1.py` | `last_game`, `roll3`, `roll5`, `ewma` all cross; `coach_prior` keyed on **coach name only**, crossing clubs | team volume from the prior season's tail | **MOSTLY NO** | the layer already **selects** walk-forward among 8 baselines including `prev_season` and `league_mean`. With the actual production selections, no week-1 difference against boundary-free `league_mean` excludes zero (§4). The coach-move exposure is **11/160** week-1 team-games (6.9%) | **FALSIFIED as an unexamined crossing; PARTIAL on `coach_prior`** |
| 15 | `nfl/research/p3/p3_features.py:55` `f_prev_practice` / `f_practice_seq` | `inj.get((season, week-1, ...))` | at week 1 this looks up week 0, which does not exist | NO | fails to the declared null `'none'` for every player. Boundary-safe by accident, not by design, but safe | **FALSIFIED** |
| 16 | `appearance_r7.py:262` `crossed`, `:268` `cm_within`, `:333–337` week-1 indicator | the repair itself | — | NO | see §2 — this is the repair, and at the marginal level it works | **FALSIFIED (correctly specified)** |

## §2 — the "R7-A2" question: does the repair exist, and what does it cover?

**No artifact named `R7-A2` exists in this checkout.** `grep -rn 'R7-A2\|R7_A2'`
over the whole tree returns nothing. The repair matching the description
"season-boundary semantics for absence features" **does** exist, unnamed:

* `nfl/production/nonqb/appearance_r7.py:254–292` `_walk` — `crossed`,
  `cm_within` (reset at the boundary), `cm_carried` (fires only when crossed);
* `appearance_r7.py:333–337` `featurise` — a `week == 1` indicator, a `crossed`
  indicator, and `cm_carried` in its own column;
* documented at `NFL_R7_APPEARANCE_FRAME_AUDIT.md:139` and
  `nfl/research/r7/R7_EVIDENCE.json → season_boundary`;
* inherited verbatim by R8 (`appearance_r8.py:73–78`).

**What it covers.** The *level*. Forward-chained, 2025 week 1, n=761: R8's mean
P(appear) is 0.5009 against a realised 0.4849, and by `cm_carried` bucket the
bias is −0.001 (cm 0, n=377), −0.013 (cm 1, n=64), +0.004 (cm 4–7, n=74),
−0.012 (cm 8+, n=15). Week-1 Brier 0.0697 / AUC 0.9632 is **better** than the
same model's weeks 5+ (0.1007 / 0.9264). I went looking for a marginal week-1
calibration failure in R7/R8 and **did not find one**. That hypothesis is
withdrawn.

**What it does not cover, and this is the substantive gap.** The R7 audit names
three offending features by name — *"`f_consec_missed`, `f_weeks_since_appear`
and `f_prev_appeared` all walk backwards through the offseason without noticing
it"*. The repair it shipped rebuilt **R7's own** absence streak. It did not
touch the frozen P2/P3 block. R8 then **re-imported that block raw**
(`appearance_r8.py:94, :290–304`), with the stated reason that *"damping them
would be re-introducing the deficit by another route"* — which is true of
damping, but the repair R7 shipped was not damping, it was **separation**.

So the boundary is represented in R8 as **two intercept columns** (`week==1`,
`crossed`) plus `min(cm_carried,4)/4`, while **every continuous history feature
carries a single season-invariant slope**, and `f_team_change` — the one
club-change flag the frozen block had — is not carried across at all.

## §3 — does the missing separation cost anything? (exploratory)

Scratchpad ablation only. Four columns added to a **copy** of R8's design row:
`crossed × min(cm_carried,16)/16`, `crossed × 1[cm_carried ≥ 8]`,
`crossed × min(f_weeks_since_appear,9)/9`, `crossed × f_rate_ewma`. Same
estimator, same L2, forward-chained fit on seasons `< EV`, scored on week 1 of
`EV`. Brier difference bootstrapped with 4,000 resamples clustered by team.

| EV | n | base Brier | +boundary Brier | Δ | team-clustered 95% CI | excludes 0 |
|---|--:|--:|--:|--:|---|---|
| 2023 | 683 | 0.050705† | 0.050705† | −0.000768 | [−0.001505, −0.000049] | yes |
| 2024 | 702 | 0.046931 | 0.046743 | −0.000188 | [−0.000882, +0.000531] | no |
| 2025 | 761 | 0.069666 | 0.067711 | −0.001954 | [−0.002644, −0.001225] | yes |

† the 2023 base/variant Briers round identically at 6 dp in the printed table;
the per-row difference does not, which is what the CI is computed on.

AUC moves 0.9632 → 0.9653 (2025) and 0.9787 → 0.9793 (2024).

**Read this narrowly.** The direction is consistent across three seasons and
two of three CIs exclude zero, but (a) the columns were chosen **after**
inspecting the frame, so this is exploratory and not a confirmatory result;
(b) the bundle is not attributed — the `cm_carried ≥ 8` subgroup barely moved
(2025: 0.3209 → 0.3312 against a realised 0.3333, n=15), so the gain is almost
certainly coming from the `crossed × f_rate_ewma` and `crossed × wsa` terms and
**not** from uncapping `cm_carried`; (c) absolute magnitude is ~3% of Brier.

Finding 3 (the cap) therefore stands as a **demonstrated expressiveness
failure** — 576/576 identical design rows, 32.3 realised points inside one
feature value — and **not** as a demonstrated forecasting cost. Those are
different claims and the data supports only the first.

## §4 — team volume: the crossing is there and it is not the defect

`nfl/production/team_volume_v1.py:118 selected()` reads the estimator chosen by
the frozen P4B walk-forward. For 2025 those are `league_mean` (off_snaps),
`coach_prior` (dropbacks_part, carries, rz_carries) and `ewma` (targets).

Week 1 only, eval seasons 2022–2025, n=128 team-games each, production
estimator against boundary-free `league_mean`, 4,000-resample bootstrap
clustered by team:

| metric | prod estimator | week-1 MAE prod | week-1 MAE league_mean | Δ | 95% CI | excludes 0 |
|---|---|--:|--:|--:|---|---|
| team_off_snaps | league_mean | 7.2472 | 7.2472 | 0.0000 | — | — |
| team_dropbacks_part | coach_prior | 7.1377 | 6.8170 | +0.3207 | [−0.0302, +0.6730] | no |
| team_targets | ewma | 6.5262 | 6.2231 | +0.3031 | [−0.4005, +1.0402] | no |
| team_carries | coach_prior | 5.6159 | 5.6850 | −0.0691 | [−0.4609, +0.3307] | no |
| team_rz_carries | coach_prior | 2.5523 | 2.5366 | +0.0158 | [−0.1180, +0.1368] | no |

**Nothing excludes zero.** The layer is not defective at the boundary, because
it already tested boundary-free alternatives and mostly chose them. That is the
correct outcome and it should be preserved, not "fixed".

Two things the same run does show, and they belong on the record because they
are the pattern in its pure form:

* the naive **`last_game`** estimator — literally "last observed is current
  expected" — is catastrophic at week 1 on all five metrics, e.g. off_snaps
  MAE **11.0781** against 7.2472 for `league_mean` (+52%), targets 8.7891 vs
  6.2231, carries 8.7422 vs 5.6850. It is not the production choice anywhere,
  which is the point: the crossing is only a defect where nothing tested it;
* the walk-forward selection **pools all weeks**. Week 1 is the only week where
  a recency-weighted estimator and a boundary-free one diverge maximally. Run
  on week 1 alone, `league_mean` is the best of the eight baselines on 4 of 5
  metrics and `coach_prior` on the fifth, against `ewma` winning 3 of 5 on
  weeks 2+. **This is not evidence that the selection is wrong** — it is a
  small sample and the selection is not week-conditional by design. It is the
  named, testable residual: *should the estimator be selected separately for
  the season opener?* Not answered here.

## §5 — finding 9 measured: the mechanism is real, the cost is not detectable

`rushing_a1`'s week-1 exposure can be backtested after all. Four play-by-play
leaves — `nfl/research/postgame/pbp_2021…pbp_2024` — are present in the working
tree as **untracked artifacts staged by a concurrent workstream**; they are not
repository state at HEAD `57d38ad`, and `pbp2020` and `pbp2025` are still
absent, so eval is limited to 2023 and 2024. The A1 frame rebuilt from them
through `a1_lib.build_frame` / `attach_prior` closes on 2,174 team-games,
matching the count J1 quotes.

Week 1 only, eval 2023–2024, 32 teams each, mean absolute error of the category
share against realised, production `_centre` (EWMA hl=2, shrunk `n/(n+4)`)
versus the boundary-free alternatives:

| category | production EWMA | prior-season mean | flat league share | Δ (ewma − season mean) | team-clustered 95% CI | excludes 0 |
|---|--:|--:|--:|--:|---|---|
| rb | 0.0842 | 0.0845 | 0.0830 | −0.0003 | [−0.0079, +0.0079] | no |
| designed_qb | 0.0704 | 0.0676 | 0.0738 | +0.0028 | [−0.0043, +0.0098] | no |
| wr | 0.0409 | 0.0414 | 0.0370 | −0.0005 | [−0.0042, +0.0028] | no |

**All three are indistinguishable.** The half-the-weight-on-two-games structure
is exactly as described, and at n=64 with 32 clusters it costs nothing
measurable. Finding 9 is therefore a confirmed *mechanism* and a **falsified**
*cost* — with the caveat that n=64 over two seasons is thin, no equivalence
margin was predeclared, and "not distinguishable" is not "equal".

This is the second component (after §4) where the crossing is present, obvious,
and not the defect. That is now the majority pattern in this pass.

### What still cannot be measured here

* **Finding 7 (`p4c` `C`).** Measured as a mechanism — the EWMA arithmetic is
  exact, and `nfl/production/nonqb/p4c_params.py:158–163` builds `hist` keyed on
  `gsis_id` with no season or team term. Not measured as a cost:
  `p4c_build.load_panel` reads `nfl/research/p4b/panel_enriched.pkl` and
  `volume_store.npy`, and neither is in this checkout (only
  `nfl/derived/panel_enriched.pkl` exists, at a different path). The settling
  test: eval seasons 2022–2025, week 1 only, score `C = ewma(h)` against
  `C = prior-season mean` and `C = tier mean` on CRPS and MAE, clustered by
  team-game. Given §4 and the table above, the prior should be that it comes
  back null too.
* **Findings 10 and 11 (`q6` / `role_prior` trailing windows).** Same shape,
  same missing artifacts, same test.
* **2026 evidence.** Nine graded games. Nothing here is validated on 2026, and
  the DAL case (Abanikanda, `cm_carried=13`, P(appear)=0.9465) is one
  player-game, cited as an illustration of finding 3, never as evidence for it.

## Evidence ceiling

1. **Two eval seasons of five is not five.** The R7/R8 measurements pool
   2021–2025 week 1 = 3,667 frame rows, of which 2,822 cross the boundary. The
   long-carried-absence cells are small: `cm_carried ≥ 8` is n=64 pooled and
   n=15 in any one season. Nothing about that subgroup is established.
2. **The ablation in §3 is exploratory.** Columns chosen after inspecting the
   frame. A confirmatory result needs pre-registration and a fold the design
   choice did not see. It is reported as a direction, not a verdict.
3. **Five metrics, one test each, in §4.** No multiplicity correction was
   applied and none is needed for the conclusion drawn, which is a *null*.
4. **n=128 per metric with 32 clusters** is thin. The §4 nulls are
   "not distinguishable", not "equal". No equivalence margin was predeclared and
   no TOST was run, so none of them may be written as "unbiased" or "correct".
5. **`cm_carried` and `crossed` are frame-frequency quantities, not calendar
   quantities.** A player whose last frame row is a prior season but whose game
   is week 9 (n=224, 59.8% at a different club) is also `crossed`. R7 gets this
   right; any reader of this document who reduces it to "week 1" does not.
6. **The `f_weeks_since_appear` ≥ 5 buckets are contaminated** by the
   `LOOKBACK_CANDIDATE = 4` censoring that R7 was written to lift — rates jump
   to 0.8967 (in-season) and 0.9947 (week-1 crossed). They are excluded from
   every reading above and must not be quoted.

## What this does not establish

* It does not establish that any repair improves a forecast. Nothing was
  implemented in the repository and nothing was promoted.
* It does not establish that findings 7, 10, 11 cost anything. They are
  mechanisms with exact arithmetic and no scored counterfactual. Finding 9 was
  scored and came back null; findings 14 and 15 were scored and came back null.
  **Three of the four components I could actually score showed no measurable
  week-1 cost.** The honest summary of this pass is that the crossing is
  near-universal and the demonstrated damage is narrow: `QB3` (recorded),
  the `cm_carried` cap as an expressiveness failure, and the shared-slope
  ablation in §3.
* It does not re-open `QB3_WEEK1_SEASON_BOUNDARY` or propose a change to it.
  Findings 1 and 2 are re-derivations of a recorded defect, included so the
  class is enumerated completely.
* The DAL/NYG root-cause audit
  (`nfl/research/live/2026_01_DAL_NYG/DAL_NYG_PARTICIPATION_ROOT_CAUSE_AUDIT.md`)
  already records finding 3 as its item 4 and finding 1 as its item 1. This
  document adds the counterfactual that proves the cap collapses the cells
  (576/576), the population sizes, and findings 4–15.

## Reproduction

```
python3.12 -c "import sys;sys.path.insert(0,'/home/user/nfl');\
from nfl.production.nonqb import appearance_r8 as R8;print(R8.enriched_frame().evidence)"
```
builds the 59,784-row union frame (2020–2025, 6,181 rows added by the depth
chart, 0 team-weeks without a lawful chart) that findings 3–6, 10, 13 and §2–§3
are measured on. §4 reads `nfl/research/inputs/denom_panel.csv.gz` (3,230
team-games) through `nfl/research/p4b/p4b_volume.py`'s own `attach` and
`baselines`. Finding 9 reads `nfl/derived/rushing_a1_params_2026w01.json`
directly. §5 rebuilds the A1 frame from the four untracked `pbp_202x` leaves in
`nfl/research/postgame/`, which may not be present in another checkout. The
measurement scripts were run from a scratchpad and are not
committed; each measurement above names the module and function it calls so it
can be rebuilt from the repository alone.
