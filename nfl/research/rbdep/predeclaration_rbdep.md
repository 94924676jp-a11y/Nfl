# RBDEP pre-registration — RB1 <-> RB2 opportunity dependence

**Written 2026-09-09, before any arm-SHR number existed.** Frozen by sha256;
`run_rbdep.py` recomputes the hash of this file at run time and refuses to
score if it has moved. Authorised under owner ruling B11.

---

## 1. What is already measured, and what is not

Measured BEFORE this document was written, and reported in `rbdep_baseline.json`:

* the incumbent allocator's dependence on the historical evaluation frame;
* the historical realised dependence on the same frame;
* an exact reproduction of the four numbers B11 quotes, from the artifact B11
  was computed on.

NOT measured before this document: **any arm-SHR result, on any frame.** The
ablation had not been run when this was written. The `p4c_build.gen_weights`
parameter existed and was proved to leave the default bit-identical, and that
is all.

## 2. The correction this pre-registration carries

B11 states `model +0.081` against `real -0.329` and calls the sign wrong. The
reproduction shows those two numbers are **not the same estimand**, and are not
computed on the same population.

| quantity | what it is | value |
|---|---|---|
| `+0.0809` | mean over team-games of corr **ACROSS DRAWS WITHIN one team-game**, 2026 week-1 production rehearsal (`payload_A30`, 32 team-games) | reproduced exactly |
| `-0.1792` | the same, on shares | reproduced exactly |
| `+0.1132`, `P(r>0)=0.680` | **BETWEEN** team-game, one draw each, same 32 production team-games | reproduced exactly |
| `-0.3294` | **BETWEEN** team-game correlation of REALISED carries, historical | reproduced as `-0.3330` |

Reality supplies one draw per team-game, so the realised figure is necessarily
a **between**-team-game correlation. `+0.081` is a **within**-team-game
conditional correlation. Setting one against the other is the like-for-like
defect this project has already found six times, in a new place. The
comparable production figure is `+0.1132`, and it is positive, so a real
wrong-signed result does exist — on the production rehearsal.

On the historical evaluation frame the SAME code gives a **correctly signed**
result (see `rbdep_baseline.json`). The two frames differ in the information
content of `C`, the per-player share point forecast. That is the hypothesis
this pre-registration tests, alongside the ablation the owner ordered.

## 3. Population, and the chronological rule

* Panel `panel_enriched.pkl`, seasons 2020-2025. **The runner asserts no season
  above 2025 is present**; 2026 outcomes are never read and do not exist here.
* Evaluation seasons **2022, 2023, 2024, 2025**. Every parameter for season
  `ev` is fitted on seasons strictly `< ev` by `p4c_build.fit_params`; the mass
  pool additionally excludes 2020. **2020 and 2021 are burn-in and are never
  scored.**
* Class `carries`, P4C system `C`, mode `simplex`. Team volume is the frozen
  P4B `team_carries` draw store, column `B`.
* Rows: `s_carries` present, appearance model available, `f_n_prior >= 1`,
  `_C` present, team-game present in the volume store. This is exactly
  `run_p4cc.py`'s eligibility and is not re-derived here.

## 4. Ranking RB1 and RB2 — outcome-free, and identical in both halves

Within a team-game of season `s`, week `w`, a back is ranked by his **carries
in weeks `< w` of season `s` only**. Ties break on prior appearances, then
`gsis_id`. Required: `w >= 5`, and both RB1 and RB2 must have at least one
prior-week carry. A team-game that cannot supply two such backs is dropped.

This uses no information from the game being ranked, and **the same ranking is
applied to the model draws and to the realised carries.** B11's model figure
ranked by the model's own predicted mean while its historical figure ranked by
prior form; that is a second like-for-like break and it is not repeated here.

## 5. Arms

| arm | `add_pool_groups` | description |
|---|---|---|
| **INC** (incumbent) | `None` | every player resamples the additive share residual INDEPENDENTLY. The current default, unchanged. |
| **SHR** (ablation) | one id per team-game | the players of a team-game share ONE resample position, A3's trick moved down a layer. |

Nothing else differs. Same seeds, same `C`, same appearance draws, same team
volume draws, same allocator. The per-player marginal law of the residual is
identical in both arms by construction (a uniform draw from the same pool), so
this is an ablation of dependence and not of marginals; the runner checks that
claim rather than asserting it.

**Simplest wins.** INC takes no argument and is the standing default. INC wins
ties. A tie is `|Delta CRPS| <= 0.2%` relative **and** `|Delta median r| <= 0.02`.

## 6. Frames

* **Frame H (primary).** The evaluation frame as specified in section 3, with
  `C` exactly as fitted. Outcomes exist, so this is the only frame on which
  marginal quality is scored.
* **Frame L (diagnostic, no outcome scored).** `C` shrunk toward the team-game
  mean of the modelled backs: `C_lam = lam*C + (1-lam)*mean_group(C)`, over the
  **pre-declared grid `lam = 1.00, 0.75, 0.50, 0.25, 0.00`**. `lam = 1` is
  Frame H. `lam = 0` is a team-game whose backs carry no role separation at
  all. This traverses the axis on which the production rehearsal differs from
  the historical frame, and its purpose is to locate the sign crossing and to
  ask whether SHR moves it. **No CRPS, no calibration and no quality claim of
  any kind is read off Frame L**; it reports dependence and gates only.

## 7. Metrics

**Primary (dependence), computed LIKE-FOR-LIKE.** For each draw index `j`,
Pearson `r` between RB1's and RB2's carry counts **across team-games**, one
draw per team-game. Reported as the distribution over `j`: median, mean,
`P(r>0)`, p05, p95. The realised value is the single between-team-game Pearson
`r` of the realised carries over the same team-games.

Also reported for context, and never compared against a realised series:
the within-team-game across-draw correlation, and the correlation of predictive
means. The second is labelled in the artifact as the forbidden statistic.

Also reported: the same suite on shares `N / T`, and the fraction of RB1's
carry variance attributable to team-volume variance.

**Secondary (marginal quality, Frame H only).** Per-player CRPS on carry
counts, pooled and by season, against realised `y_carries`. Distribution
summary: mean, sd, p05, p50, p95, zero-mass `P(N < 0.5)`, pooled over rows.
Also MAE, RMSE, bias, and interval coverage at 50/80/90/95.

## 8. Hard gates — counts, in every arm and every frame

Reported as counts, not as adjectives. G1-G4 are refusals.

| id | gate | rule |
|---|---|---|
| **G1** | simplex closure | for every (team-game, draw), `\|sum_i S_i + other - 1\| <= 1e-5`. Violations must be **0**. |
| **G2** | team budget partitioned | `\|sum_i N_i - T*(1 - other)\| <= 1e-3 * max(T,1)`. Violations must be **0**. |
| **G3** | no negative allocation | count of `S < 0` and of `N < 0` must be **0**. |
| **G4** | no cap repair | `waterfill` binding count must be **0** (a simplex whose shares sum below 1 cannot reach the cap). |
| **G5** | weight flooring | the `np.clip(W, 0, 1)` rate is REPORTED in both arms and is **not** a refusal: the incumbent already floors, and the V1 ledger records 20.68% of share draws. A rate is not a pass. |
| **G6** | degenerate team-games | rate of team-games whose modelled weights are all zero in a draw, so the non-modelled block takes the whole share. **Predicted in advance: SHR must inflate this**, because a shared negative residual floors every back at once whereas independent residuals rarely do. Declared threshold: if SHR's rate exceeds **3x** INC's, the artifact records `SHARED_ARM_DEGENERACY_INFLATION` and it counts against SHR. |

Nothing anywhere clips, renormalises or repairs a result into shape. If a gate
fails the arm is reported failed with its counts.

## 9. Decision rule

Evaluated in this order. Defaults are the lead's; this rule fixes only the
verdict recorded in `rbdep_results.json`.

1. If either arm fails **G1-G4**, that arm is `GATE_FAILED` and carries no
   dependence claim.
2. **Frame H necessity.** If INC's primary median `r < 0` with `P(r>0) <= 0.05`
   on Frame H, record `ABLATION_UNNECESSARY_ON_FRAME_H`: the sign is not
   materially wrong where outcomes exist, and no fix is warranted there.
3. **Frame L sufficiency.** Let `Lam+` be the set of grid points at which INC's
   primary median `r >= 0`. If `Lam+` is empty, record
   `SIGN_NEVER_WRONG_ON_GRID`. Otherwise, if SHR's median `r < 0` at **every**
   point of `Lam+`, record `ABLATION_FIXES_SIGN`; else
   `ABLATION_DOES_NOT_FIX_SIGN`, and the report states plainly what it did
   instead. **No escalation to a redesign follows from this branch.**
4. **Marginal guard, Frame H.** If SHR's pooled CRPS exceeds INC's by more than
   **1.0% relative**, record `MARGINAL_DETERIORATION` whatever the dependence
   result. A dependence fix that costs more than that is not a fix.
5. **Tie.** Under section 5's tie definition, INC wins.

`materially wrong` is defined here, once: **median `r >= 0` over draws, on the
like-for-like between-team-game statistic.** Exact replication of `-0.329` is
not required and is not a criterion, per the owner's instruction.

## 10. What this cannot establish

The evaluation seasons are the same seasons P4B and P4C were selected on. This
is **exploratory**, not confirmatory, and every artifact says so. A confirmatory
result needs games no design decision has touched. Frame L is a synthetic
degradation of `C` and says nothing about how good any real production `C` is;
it locates a crossing, nothing more.
