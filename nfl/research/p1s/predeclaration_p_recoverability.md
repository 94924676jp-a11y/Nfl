# P recoverability pre-registration — pass-snap participation

Written 2026-09-08. Start HEAD `647f620`. Written **before any new comparative
P result was computed or inspected**. Departures will be labelled where they
occur.

Authorised research unit: **P = pass-snap participation.** No other football
layer is researched in this task.

## 0. The question

> Can next-game pass-snap participation be predicted materially better than the
> accepted Stage 2 representation, and if so does that improvement produce
> downstream target-distribution value?

This is a **recoverability** study. It is not a routes-run study, a target-rate
study, a receiving-yards study, a DFS study or a fantasy projection study.

## 1. Estimand

```
P_i,g = player pass snaps / team dropbacks
```

conditional on appearance, by the exact Stage 2 construction (`s_pass_snaps` in
the P1-built panel).

**Appearance is kept separate.** `A` (whether the player played at all) and `P`
(participation given he played) are distinct. Appearance forecasting is **not**
permitted to absorb P. No combined A×P experiment is run, because none is
pre-declared here.

**Route limitation, carried forward unweakened.** P is **PASS-SNAP
PARTICIPATION — an UPPER BOUND ON ROUTE PARTICIPATION**, because a player on the
field for a dropback may block. It is **not routes run**. True routes are
unavailable in this project, the magnitude of the gap is unknown, and nothing
here concludes anything about the value of route information.

## 2. Baseline identity — a hard gate

The accepted control is **Stage 2's EWMA half-life 2**, by its exact
construction. It must reproduce `nfl/research/s2/s2_results.json` at
`by_season/<pos>/ewma_hl2/pooled` through **Rule 006**, tolerance **0.0**, hash
reported, for MAE, RMSE, r, R² and SD ratio, for WR, TE and RB.

Published values it must match:

| pos | MAE | RMSE | r | R² | SD ratio |
|---|---|---|---|---|---|
| WR | 0.142312 | 0.202278 | 0.795338 | 0.627091 | 0.868202 |
| TE | 0.118063 | 0.163658 | 0.836432 | 0.695940 | 0.897059 |
| RB | 0.119637 | 0.159306 | 0.772257 | 0.589617 | 0.854484 |

If exact identity fails the study **STOPS** and classifies
`REPRODUCIBILITY_BLOCKED` or `IMPLEMENTATION_DEFECT`. Rounded logs are not
admissible as gate truth.

## 3. Sample and chronology

Evaluation seasons **2022–2025**, each reported separately, strict next-game
walk-forward. Sample inclusion is Stage 2's, unchanged: the player appeared,
`s_pass_snaps` is present, at least one prior appeared game exists, and the
running position mean is defined.

Training for any evaluation game contains only information available strictly
before that game, on **strictly earlier ordinals** — the prefix cut P4E, Stage 2
and R1 all required for the 1,318 player-ordinal pairs where a player changed
team mid-week.

**Forbidden and not read**: current-game participation, pass snaps, team
dropbacks or targets; any future game; future teammate participation; postgame
roster state; `weekly_rosters.status`; present-week depth-chart state unless
independently PIT-proven (it is not, so it is quarantined); market data;
observed weather; 2026 outcomes; fantasy or professional projection labels;
fuzzy name matching; any field of unknown fit provenance.

**Masking audit required**: blank every outcome field at ordinal ≥ k, rebuild,
require features at ordinal == k bit-identical. Any movement stops the study as
`P_DATA_BLOCKED`.

## 4. Residual anatomy first — before any model

The accepted baseline's residual is characterised before a candidate exists:
MAE, RMSE, r, R², bias, SD ratio; per season; WR/TE/RB; and by every cohort in
§7. Then residual structure against prior P, recent P change, history length,
teammate role change, appearance probability; residual autocorrelation; and
residual dispersion by player, team, position and week.

**Recoverability is not inferred from residual size.**

## 5. Simple baselines

`pos_mean` · `last_obs` · `expanding` · EWMA half-lives **1, 2, 3, 5, 8** ·
empirical-Bayes shrinkage toward the position prior (constant fitted on prior
seasons only) · prior-season player mean · career prior ·
**role-transition-conditioned persistence** (a separate persistence estimate for
each of the three §7 role-transition states, fitted on prior seasons).

The Stage 2 hl2 baseline is the **control** and is not replaced unless a method
beats it.

## 6. Limited ladder

| block | contents |
|---|---|
| **A player role history** | prior P level, last P, short and long EWMA, P variance, P trend, prior snap share, prior pass-snap share, history count |
| **B appearance / availability context** | prior appearance probability, prior availability history, prior role stability, prior missed-game pattern — all from P2/P3 accepted inputs only |
| **C teammate role context** | teammate prior P shares, recent teammate participation changes, vacated prior participation, returning-competitor indicator, concentration of pass-snap participation |
| **D team / coach context** | team personnel stability, team passing environment baseline, coach prior where already accepted, prior formation/personnel tendencies where chronology-safe |
| **E position terms** | WR / TE / RB indicators and their interaction with the base rate only |

Rungs: control → `P0` (best simple baseline) → each block alone on top of `P0` →
cumulative `P_A`, `P_AB`, `P_ABC`, `P_ABCD`, `P_ABCDE`.

**Complexity ceiling, fixed now.** Linear, ridge and empirical Bayes. At most
**48 design columns** including missingness flags. Ridge penalty from the fixed
grid `0.03, 0.1, 0.3, 1, 3, 10, 30, 100`, selected on an **inner validation
season** inside the training block, never on the evaluation season.

**One monotonic family is pre-declared and no others**: isotonic regression of
realised P on the control's forecast, fitted on prior seasons only. It is
justified in advance by Stage 2's measured SD ratio of 0.85–0.90 — the control
is mildly under-dispersed, and a monotonic recalibration is the minimal
correction for that. **No boosting, no neural network, no large feature search.**

## 7. Cohorts — thresholds fixed now

- **position**: WR / TE / RB
- **history** (prior appeared games): `<4` / `4–9` / `10–24` / `25+`
- **appearance probability**: `<0.25` / `0.25–0.50` / `0.50–0.80` / `0.80–0.95` / `≥0.95`
- **prior P** (EWMA hl2 of prior P): low `<0.25`, medium `0.25–0.60`, high `≥0.60`
- **role transition** (prior P step, mean of last 2 minus mean of prior 2): up `≥ +0.10`, down `≤ −0.10`, else stable
- **prior role** (prior mean **snap** share, deliberately a different quantity from prior P): starter-like `≥0.60`, rotation `0.25–0.60`, fringe `<0.25`
- **teammate change**: `vacated_opportunity` if the summed prior-game P of teammates who did not appear is `≥0.20`; `returning_competitor` if a teammate absent in the prior game has prior appeared history; else `stable`

Role labels used as **predictors** are built from strictly prior information.
Outcome-defined labels may be used **only** for retrospective cohort evaluation
and are marked as such.

## 8. Metrics

**Primary**: MAE, RMSE, correlation, R², bias, SD ratio. Pooled and per season,
by position and by cohort.

**No probabilistic P distribution will be constructed.** Stage 2's P is a point
forecast, and inventing a dispersion model to generate CRPS, PIT and coverage
would measure the invention rather than P. Distributional evidence comes from
the downstream target CRPS in §9, which scores the full composed predictive
distribution.

## 9. Downstream test — mandatory

Freeze A, T, R and every other accepted target-pipeline component. Substitute
**only P**.

**Draw-preserving substitution rule, applying R1's lesson explicitly.** In the
Stage 4 pipeline `W = Pc × Rhat`, where `Rhat` is a draw matrix and `Pc` a
per-row scalar. Substituting P means `W_new = P̂_new[:, None] × Rhat`, which
leaves the entire draw structure intact — the dispersion lives in `Rhat` and is
untouched. **A draw distribution is never replaced by a point estimate**, and no
new distribution is introduced, because none is pre-declared.

Reported: baseline target CRPS, candidate target CRPS, delta, per-season delta,
paired block bootstrap clustered by team-game, and cohort deltas for
role-change, high-confidence starters and low-history players.

## 10. Oracle accounting

Denominator is the Stage 4 P Shapley component, per season: **0.2849 / 0.2638 /
0.2548 / 0.2627** CRPS (2022–2025).

Required wording, fixed now: **"this model family recovered X% of the currently
measured P oracle opportunity."** Never "only X% of P is recoverable." No
information ceiling is inferred from one family.

## 11. P → R interaction — diagnostic only

Four cells, reported as a factorial:

`P_control × R_control` · `P_candidate × R_control` · `P_control × R_R1` ·
`P_candidate × R_R1`

Purpose: determine whether improving P unlocks R1's weak signal. **R_R1 is NOT
promoted, is not accepted, and must not replace accepted R in any architecture.**
The R1 substitution uses R1's own shape-preserving centre rescale.

## 12. Stage 3 joint diagnostic — consumer only

Pre and post reconciliation where technically supported: marginal P calibration,
individual cap violations, team-group physical coherence, dependence, the effect
of reconciliation on P, and its effect on downstream target CRPS. **The joint
simulator is not fixed here and no combined score is produced.**

## 13. Adversarial

Materiality fixed now at **5% relative P MAE improvement** — lower than R1's 10%
because the control here is strong (r ≈ 0.80), so a smaller move is meaningful.
Not lowered after observation.

Probes: current-game P; future P; current-game pass snaps; current-game team
dropbacks; future teammate participation; postgame roster state;
`weekly_rosters.status`; present-week depth chart; current-game targets; future
target data; market data; observed weather; same-week duplicate chronology;
identifier leakage; wrong denominator; zero/N-A conflation; future residual
pool; evaluation-season fit leakage; post-hoc hyperparameter selection; manually
rounded artifact reference.

Minimum **two load-bearing guard-deletion proofs**. A probe that cannot fire is
**UNRESOLVED**, never PASS.

## 14. Decision states — defined before results

- **P_SIGNAL_FOUND** — the candidate beats the Stage 2 control on pooled P MAE
  by **≥ 5% relative** in **≥ 3 of 4** seasons for **≥ 2 positions**, AND the
  downstream target CRPS *improves* with a paired block-bootstrap 95% interval
  excluding zero.
- **P_SIGNAL_WEAK** — a stable improvement exists (interval excludes zero) but
  falls short on magnitude, season count, position count or downstream effect.
- **P_MODEL_CLASS_FAILED** — the tested families do not reach `P_SIGNAL_WEAK`.
  **This is not an information ceiling.**
- **P_INFORMATION_CONSTRAINED_CANDIDATE** — only if materially different
  approaches fail and independent evidence supports the reading. One family is
  insufficient.
- **P_CALIBRATION_DEFECT** / **P_ESTIMATOR_DEFECT** / **P_DATA_BLOCKED** /
  **P_UPSTREAM_DATA_LIMITED**.

No other primary state is invented after results.

## 15. Action and promotion

Only **RETAIN_STAGE2_P** or **RETAIN_P_DEVELOPMENT_CANDIDATE**.

**NO PROMOTION. NO PROSPECTIVE FREEZE.** If a candidate improves P but worsens
downstream target CRPS the action is **RETAIN_STAGE2_P** — whole-chain
performance decides, exactly as it did in R1.

2022–2025 are heavily mined development data. Nothing here is confirmation, and
no bootstrap interval computed on them is described as one.

## 16. Stop conditions

Stop and classify without proceeding if the baseline does not reproduce exactly,
or the masking audit is not clean.

After the return is committed and pushed: **stop**. No true-routes acquisition,
target follow-up, catch probability, receiving yards, YAC, air yards, touchdowns,
red zone, QB, defence, DFS, markets, props, NFL-1 or prospective freeze without
a further owner directive.
