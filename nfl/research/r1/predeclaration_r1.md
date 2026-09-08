# R1 pre-registration — target rate conditional on participation

Written 2026-09-08. Start HEAD `11ea949`. Written **before any comparative R
result was computed or inspected**. Departures will be labelled where they
occur.

Authorised research unit: **R — target allocation / target rate conditional on
participation.** Nothing else is researched in this task.

## 0. The question, and what it is not

Stage 4 measured R at **46.0%** of oracle-removable target CRPS: LARGE and
UNTESTED. This study does not try to build the best target model. It asks:

> Is there chronology-safe, repeatable, out-of-sample signal in next-game target
> rate conditional on participation? And if so, how much of the R component can a
> simple, honest model recover?

**Recoverability is not inferred from oracle size.** 46% is not assumed
obtainable. A negative result is acceptable and will be reported as one.

## 1. Estimand — taken from Stage 4 unchanged

For player *i* in team-game *g*, exactly as committed in
`nfl/research/s4/run_s4.py`:

```
P*_i = pass_snaps_i / team_dropbacks_i        (realised participation share)
W*_i = S*_i x A*_i                            (realised target share x appearance)
R*_i = W*_i / P*_i     where P*_i > 0,   else 0
```

`R` is **not redefined** here. `P` is **pass-snap participation** and is never
called routes run.

**Known limitation, carried from Stage 2 and not weakened:** pass-snap
participation is an **upper bound** on route participation, because a player on
the field for a dropback may block. The gap to true routes run is directional
and its **magnitude is unknown**. Nothing in this study may conclude anything
about the value of true route information.

Because `S*` is a share of team targets and `P*` a share of team dropbacks, `R*`
is targets-per-participated-dropback scaled by `team_dropbacks / team_targets`.
It is bounded above by roughly 1.3 and below by 0.

## 2. Sample inclusion

Evaluation seasons **2022, 2023, 2024, 2025**, each reported separately, strict
next-game walk-forward.

A player-game enters the **evaluation** set when all hold:

1. it is in the Stage 4 target frame for that season (same filter, same sort);
2. the player appeared;
3. `P* > 0` — with no participation the rate is not defined, and a
   non-appearance is **never** silently scored as rate zero;
4. at least one prior game with `P* > 0` exists (there is something to persist
   from).

A player-game enters a player's **history** when the player appeared and
`P* > 0`. Counts of rows excluded by each clause are reported.

Position groups **WR, TE, RB**, reported separately and pooled.

## 3. Denominator integrity — audited, not assumed

Reported before any model is fitted:

- numerator: realised target share `S*`, and the raw target count behind it;
- denominators: `team_targets` and `team_dropbacks`, their ratio, and its spread;
- participation denominator `P*`: distribution, and the share of rows below
  0.02, 0.05 and 0.10;
- appearance: how many rows are excluded by clause 2 above;
- zero handling: how many appeared rows have `P* = 0` (structural, excluded) and
  how many have `P* > 0` with zero targets (a real zero rate, kept);
- N/A handling: how many rows have a missing component, and why.

**Numerical stability.** A rate from one pass snap is not the same evidence as a
rate from thirty. Two estimator variants are therefore pre-declared for every
history-based baseline: **unweighted**, and **participation-weighted** (each
prior game weighted by its `P*`). No floor is applied to `P*` when *forming*
`R*` — Stage 4's definition stands. Where a floor is needed to avoid a
divide-by-zero in a derived feature it is fixed at **0.02** and its activation
rate is reported.

## 4. Chronology rules

Training for any evaluation game contains only information available strictly
before that game. Strictly-earlier **ordinals**, not merely earlier processing
order — the same prefix cut P4E and Stage 2 needed for the 343 player-ordinal
pairs where a player changed team mid-week.

Forbidden and not read: same-game information of any kind; future games; 2026
outcomes; present-game injury result; postgame roster state;
`weekly_rosters.status`; current-game targets; current-game participation;
future teammate state; present-week depth chart; market data; observed weather;
fantasy or professional projection labels; fuzzy name matching; any field of
unknown fit provenance.

**Masking audit required**: blank every outcome field at ordinal ≥ k, rebuild
the features, and require features at ordinal == k to be bit-identical. Any
movement is a failure and the study stops as `DATA_BLOCKED`.

## 5. Baseline identity — a hard gate

The Stage 4 all-projected corner must reproduce
`nfl/research/p4c/p4c_results.json` at `targets/<season>/scores/C/crps` through
**Rule 006**, tolerance **0.0**, hash reported. If it does not, the study stops
and classifies `REPRODUCIBILITY_BLOCKED` or `IMPLEMENTATION_DEFECT`. No manually
copied or rounded value is admissible.

## 6. Simple baselines first — Block 0

No complex context is added until persistence and shrinkage are understood.

| id | estimator |
|---|---|
| `pos_mean` | pooled position mean rate, from strictly prior games |
| `last_obs` | player's last observed rate |
| `expanding` | player's expanding mean |
| `ewma_hl2/3/5/8` | EWMA at half-lives 2, 3, 5, 8 |
| `prev_season` | player's prior-season mean where available |
| `eb_shrink` | empirical-Bayes shrinkage toward the position prior |
| `career_shrink` | career prior with shrinkage |

Each in **unweighted** and **participation-weighted** form. The EB shrinkage
constant is fitted on **prior seasons only**, never on the evaluation season.

## 7. The ladder — small, pre-declared, and only if Block 0 warrants it

| block | contents |
|---|---|
| **A history quantity** | prior targets, prior rate, prior sample size, recency, long-window history |
| **B role / participation context** | prior `P` level, change in `P`, stability of `P`, appearance probability, role-change indicator |
| **C team opportunity** | prior team target concentration, prior dropback environment, team passing baseline |
| **D teammate competition** | prior teammate participation shares, prior teammate target shares, vacated participation, returning-competitor indicator |
| **E position context** | WR / TE / RB indicators and their interaction with the base rate **only** |

Rungs: `R0` (best Block 0), then `R_A`, `R_AB`, `R_ABC`, `R_ABCD`, `R_ABCDE`,
plus each block alone on top of `R0` so a block's contribution is not read off a
cumulative sequence alone.

**Complexity ceiling, fixed now.** Linear and ridge only. At most **48 design
columns** including missingness flags. No interactions beyond block E's
pre-declared position terms. **No boosting, no trees, no neural nets, no
large nonlinear search** — those are not justified unless the simple study first
demonstrates signal, and this study is not authorised to spend that cost.

**Hyperparameter search space**: ridge penalty from the fixed grid
`0.03, 0.1, 0.3, 1, 3, 10, 30, 100`, selected on an **inner validation season**
inside the training block, never on the evaluation season. No other
hyperparameter is searched.

## 8. Metrics

**On R itself (primary):** MAE, RMSE, correlation, R², bias, SD ratio
(`sd_pred / sd_actual`). Pooled and per season, by position and by cohort.

**Downstream (composition):** target-count CRPS from the Stage 4 pipeline with
**A, T and P frozen exactly as Stage 4 leaves them**, substituting only the R
leg. Compared against the Stage 4 `BASELINE` corner. Paired block bootstrap
clustered by team-game.

**Distributional scoring is not forced.** If no probabilistic R distribution is
constructed, the return says so and says why, rather than inventing one to
generate CRPS/PIT/coverage numbers.

## 9. Recoverability accounting — wording fixed in advance

The denominator is the Stage 4 R Shapley component, in CRPS units, per season:
**0.4140 / 0.4418 / 0.4422 / 0.4216** (2022–2025).

Reported: raw improvement in R prediction; downstream target CRPS improvement;
and the fraction of the Stage 4 R oracle opportunity recovered.

The wording is fixed now: **"this model family recovered X% of the currently
measured R oracle opportunity."** Never "R is only X% recoverable." A model
family's failure is a fact about the family, not about the information.

## 10. Cohorts — thresholds fixed now, never after results

- **position**: WR / TE / RB
- **prior appeared games**: `<4` / `4–9` / `10–24` / `25+`
- **appearance probability**: `<0.25` / `0.25–0.50` / `0.50–0.80` / `0.80–0.95` / `≥0.95`
- **participation level** (prior EWMA hl2 of `P`): low `<0.25`, medium `0.25–0.60`, high `≥0.60`
- **role change** (prior participation step, mean of last 2 minus mean of prior 2): `up ≥ +0.10`, `down ≤ −0.10`, else `stable`
- **prior target volume** (career prior targets): low `<25`, medium `25–99`, high `≥100`
- **team target concentration** (prior team-game top target share): alpha `≥0.30`, balanced `0.20–0.30`, diffuse `<0.20`

## 11. Questions the return must answer explicitly

1. Is player rate persistence materially better than the pooled position mean?
2. Does shrinkage beat raw recency?
3. Does recency help beyond long-window history?
4. Do role changes break persistence?
5. Does participation change carry incremental information about rate?
6. Does teammate competition add value?
7. Does team passing environment add value after conditioning on participation?
8. Are WR/TE/RB different enough to justify position-specific models?
9. Is signal concentrated in established players?
10. Do low-history players create systematic over- or under-allocation?
11. Does any practical model recover a meaningful share of the R oracle opportunity?
12. Is the residual plausibly noise, missing route information, missing role
    information, or unresolved? **The final cause is not claimed without
    evidence**; `unresolved` is an available answer and will be used if it is
    the honest one.

## 12. P/R error coupling

Because R is defined conditional on P, report `corr(P forecast error,
R forecast error)` and its downstream consequence. If coupling is strong, the
return says so and does **not** treat P and R errors as independent. The
simulator is **not** redesigned in this task; the coupling is recorded as a
dependency finding.

## 13. Stage 3 scaffold — consumer only

The Stage 3 diagnostic scaffold may report pre/post accounting, marginal
calibration, dependence and physical violations for an R candidate where
technically supported. It may **not** fix a marginal, promote R, hide a defect
through reconciliation, choose features, or change any threshold in this
document. **The primary R decision rests on marginal predictive evidence, not on
a joint aggregate score.**

## 14. Decision outcomes — defined before results

- **SIGNAL_FOUND** — the best chronology-safe model beats `pos_mean` on pooled R
  MAE by **≥ 10% relative** in **≥ 3 of 4** seasons for **≥ 2 positions**, AND
  the downstream target CRPS improvement has a paired block-bootstrap 95%
  interval excluding zero.
- **SIGNAL_WEAK** — a stable improvement exists (bootstrap interval excludes
  zero) but falls short of the above on magnitude, season count, position count
  or downstream effect.
- **MODEL_CLASS_FAILED** — the tested family does not reach even `SIGNAL_WEAK`.
  **This is not an information ceiling.**
- **INFORMATION_CONSTRAINED_CANDIDATE** — used **only** if ≥ 2 materially
  different model families fail and the evidence supports the reading. One
  narrow failure is insufficient, and the return must argue the case rather than
  asserting it.
- **CALIBRATION_DEFECT** / **ESTIMATOR_DEFECT** / **DATA_BLOCKED** /
  **UPSTREAM_DEPENDENCY_LIMITED** (the last if P-proxy uncertainty materially
  prevents clean interpretation).

**No label is invented after results.**

## 15. Promotion

**NO PROMOTION IS AUTHORISED**, however strong the result. The best available
action conclusion is `RETAIN_DEVELOPMENT_CANDIDATE` with a recommendation about
a future prospective freeze; otherwise `RETAIN_P4C`. **This directive does not
authorise a prospective freeze and none will be performed.**

2022–2025 are heavily mined development data. Nothing here is confirmation, and
no bootstrap interval computed on them will be described as independent
confirmation.

## 16. Adversarial

Materiality fixed now at **10% relative R MAE improvement**, and not lowered
after observation. Probes: current-game targets; future targets; current-game
participation; future participation; postgame roster state;
`weekly_rosters.status`; future teammate state; present-week depth chart; future
team target total; a forbidden market field; observed weather; identifier
leakage; same-week duplicate chronology; wrong denominator; zero/N-A
conflation; target-rate division instability; future residual pool;
evaluation-season fit leakage; post-hoc hyperparameter selection; a manually
rounded artifact reference.

Minimum **two load-bearing guard-deletion proofs**. A probe that cannot fire is
**UNRESOLVED**, never PASS.

## 17. Stop conditions

Stop and classify without proceeding to modelling if: the baseline does not
reproduce exactly; the masking audit is not clean; or the denominator audit
shows the estimand is not what Stage 4 defined.

After the return is committed and pushed: **stop**. No receiving yards, catch
rate, YAC, air yards, touchdowns, red zone, QB, defence, DFS, markets, props,
prospective freeze or NFL-1 work without a further owner directive.
