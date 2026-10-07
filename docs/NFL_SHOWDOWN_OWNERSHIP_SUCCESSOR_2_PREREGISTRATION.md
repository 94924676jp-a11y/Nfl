# SC-OWN-ROTATION-2 — Showdown ownership successor: pre-registration (design and bar only; nothing fitted)

Declared 2026-10-07, after SC-OWN-ROTATION-1 failed its pre-registered bar on both testable folds
(`nfl/postgame/dupe_research/CHEAP_OWNERSHIP_LOSO.json`). That failure is registered in
`nfl/research/registry/CANDIDATE_STATUS_REGISTER.json` and is not reopened here. SC-OWN-ROTATION-2 is a different
candidate with a different id. **SHADOW_ONLY.** It never influences lineup selection, exposures or the objective.

## 1. What the failure taught (the design responds to this, nothing else)

- **The misses are player-level, not bucket-level.** The baseline under-owned ATL@NO's cheap rotation players by
  6.7 pp and over-owned PIT@CLE's by 8.5 pp. A fixed bucket correction learned on one slate pushes the other slate
  the wrong way.
- **The baseline ownership is an optimizer field.** It cannot give ownership to players whom its own projection keeps
  out of optimal lineups (B. Robinson Jr.: 17.6% actual FLEX against ~0%). Humans do roster them.
- **Marginals are not a field.** CPT must total 100%, FLEX must total 500%, each slot marginal must be ≤ 100%, and
  lineups must be legal. Normalising totals does not guarantee feasibility.

## 2. Candidate

**A legal-lineup ownership forecaster.**

- **Lineup distribution:** `p_c(L) ∝ 1[L legal] · exp(Σ_{i∈L} u_slot(i)(i) + θ·φ(L))` over the enumerated legal
  universe. This is the same universe and solver as the B-family duplication model (`nfl/field/showdown_dupe_research.py`).
- **The difference from B-family:** slot utilities are **predicted from prelock player features**, instead of being
  profiled to a given ownership forecast.
- **Forecast ownership:** per-player CPT% and FLEX% are the marginals of `p_c`. Feasibility holds by construction.

**Player utility, per slot s ∈ {CPT, FLEX}:**

```
u_s(i) = β0_s
       + β1_s·log(base_s(i) + ε)          base = the frozen prelock shadow ownership (BLEND), ε = 0.001
       + β2_s·value_z(i)                  (own football-only projection / salary), z-scored within the slate
       + β3_s·salary_rank_at_pos(i)       1 = cheapest at his DK position on the slate
       + β4_s·role(i)                     prelock depth rank and prior-week offensive snap share
                                          (weeks strictly before the slate)
       + β5_s·opened(i)                   1 if a player ahead of him on the depth chart is officially OUT/inactive
       + β6_s·cheap(i)·active(i)          the prelock cheap-active-rotation indicator (definition below)
```

**θ (construction features):** the B3S set, salary-free: own-QB stack, both QBs, 5-1 / 4-2 splits, any K/DST.

**Rules on inputs:**
- No future or realised ownership enters a feature.
- No sportsbook price enters anything.
- FC enters only through `base` (as in `showdown_shadow_field.py`), never as a separate feature.

**Smoothing (frozen):**
- Every officially active DK player gets per-slot ownership of at least 0.05%.
- Inactive players get exactly 0.
- The floor mass is taken proportionally from the other players in the same slot. Totals stay 100% / 500%.
- The floor applies before scoring, and only for the log score.

**Buckets.** The prelock definitions from SC-OWN-ROTATION-1, section 3 of its document, are reused unchanged (stars,
midrange, cheap active rotation, punt/fringe, K/DST). They were ATL-motivated. They are frozen here, so they cannot
be re-tuned to the new evidence.

## 3. Fitting

- **Fitted on:** every archived full field available at the freeze: PIT@CLE (196187080), and ATL@NO (196285137,
  196285160, 196285161).
  - PHI@CHI is used only if its salaries have arrived (outbox 2026-10-07), and then only for the salary-free terms.
- **Method:** joint penalised maximum likelihood over entries. L2 penalty λ = 1.0 on β1…β6 and θ, a declared prior.
- **Freeze:** the code hashes, fitted β and θ, and the fitting data hashes are written to
  `nfl/research/ownership/SC_OWN_ROTATION_2_FREEZE.json` **before the first evaluation slate locks**.
- **No refit during evaluation.** A refit is a new candidate, with a new id and a new freeze.

## 4. Evaluation: prospective only

- **Evaluation slates:** every DK NFL Showdown slate whose prelock freeze predates its lock **and** whose complete
  full-field standings are later captured. The first possible slate is TB@DAL 2026-10-08.
- **Excluded from evaluation:** PIT@CLE, PHI@CHI and ATL@NO.
- **Primary contest per slate:** the largest-field contest we hold standings for. Other contests are reported, not
  scored against the bar.
- **Minimum before any verdict: N = 4 evaluation slates with salaries.** Fewer is `NOT_YET_EVALUABLE`. That is never
  a pass and never a fail.
- **Baseline:** the frozen prelock shadow ownership (BLEND) for the same slate, i.e. today's method.
- **Metrics:** MAE and signed bias on CPT% and FLEX% per bucket, and total-ownership MAE.

  Smoothed log score of the realised ownership, with the multinomial over entries per slot computed as follows:
  - **Unit:** slate; CPT and FLEX reported separately.
  - **Uncertainty:** blocked by slate, by bootstrap over slates (2,000 resamples, seed 20261007). With N = 4 this is
    coarse, and is stated so.

### Bar

**PASS_SHADOW** only if all of the following hold, on the first N = 4 evaluation slates:

1. **Cheap active rotation, FLEX MAE:** candidate below baseline on at least 3 of the 4 slates, **and** the pooled
   improvement is positive.
2. **Cheap active rotation, |signed bias|:** candidate ≤ baseline, pooled.
3. **Cheap active rotation, CPT MAE:** candidate ≤ baseline + 0.5 pp, pooled.
4. **Every other bucket:** candidate MAE ≤ baseline + 1.0 pp FLEX and + 0.5 pp CPT, pooled.
5. **Smoothed log score:** candidate ≥ baseline on at least 3 of 4 slates.

Otherwise **FAIL**, registered as such. The margins are declared value judgements, taken over from
SC-OWN-ROTATION-1; the owner may change them before the first freeze, never after.

**A pass is not a promotion.** Promotion requires the owner. Its proposed threshold is ≥ 8 Showdown slates (the
SC-OWN-ROTATION-1 proposal) and is not decided here.

## 5. What would falsify the design before any fit

- The legal-lineup solver cannot reproduce a slate's realised marginals when its utilities are profiled to them
  (`max_abs_grad` > 1e-6). This is checked on the archived slates as a solver test, not as evidence.
- A feature is not computable prelock for a slate. Then that slate is `NOT_EVALUABLE`; no imputation.

## 6. Status

**DECLARED.** Nothing has been fitted or scored. This document's sha256 is recorded in the freeze when the fit is
run. Any later edit makes the freeze refuse.
