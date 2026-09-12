# Q9 promotion-readiness / model-family audit

# PROMOTION_READY_FOR_PROSPECTIVE_TEST

**No production promotion in this task.** Q9 stayed frozen throughout: the
allocator, the one-target floor, the hurdle predictors, the fallback rules and
the decision thresholds were imported and called, never reimplemented or
refitted.

---

## 1. Identifiability — the hurdle IS structural

22,958 appearing player-games, 2022–2025. Under a multinomial with budget `N`
and shares `π`, the implied zero mass is exactly `(1−π)^N`, so the observed
zero rate decomposes without argument.

| component | value |
|---|---|
| observed zero rate | 0.25089 |
| **multinomial sampling zero** at the correct share | 0.22410 (89.3 %) |
| mis-estimated-share component | −0.01224 |
| **structural excess** | **+0.02679** — 10.68 % of the zero mass |
| production allocator's implied zero | 0.21186 |

Against the rule fixed in code before the numbers were read — a structural
excess of at least 2 percentage points **and** at least 5 % of the zero mass —
**the hurdle is identified.** Nearly nine tenths of the observed zero mass is
ordinary multinomial sampling; the remaining tenth is not reachable by any
share.

**`π*` is a parameter oracle, not a realisation oracle** — the player's
realised share averaged over his appearing games in the evaluation season,
renormalised within the team-week. That game's own share would hand a
zero-target player a share of exactly zero and predict his zero with
certainty, which is the conditioning-on-the-outcome trap in a new place.

## 2. The plain family cannot recover it

| arm | zero Brier | predicted zero | gap vs 0.5044 | marginal CRPS | PIT χ² |
|---|---|---|---|---|---|
| `BASELINE` | 0.131875 | 0.47948 | −0.02490 | 0.825816 | 8,821 |
| `MNL_PLUS` | 0.131242 | 0.46370 | **−0.04068** | 0.821149 | **7,033** |
| `Q9_HURDLE` | **0.130107** | 0.49978 | **−0.00460** | **0.820727** | 8,913 |

`MNL_PLUS` is a conditional logit given **the hurdle's own covariates** plus
the log production share. It closes **−63.4 %** of the baseline's zero-mass
shortfall: it moves the zero mass *further from* the observation. The hurdle
closes **+81.5 %**.

Both improve marginal CRPS significantly and by almost the same amount
(−0.565 % against −0.616 %), so **the CRPS gain is recoverable by a better
share model and the zero-mass gain is not.** Only the hurdle does both.

### My prediction was wrong in direction, and that matters more than it hurts

The audit's mis-estimation component was −0.01224, so I predicted a plain
better-share arm would *raise* zero mass by about a point. `MNL_PLUS` lowered
it by 1.6. The reason is that **"better by multinomial likelihood" is not
"correct" in the audit's sense**: maximising the allocation likelihood
concentrates the shares, and a concentrated share produces fewer zeros. The
qualitative conclusion survives — the structural excess is unreachable by
reshaping π — but the quantitative prediction is withdrawn rather than
retrofitted.

## 3. No Dirichlet-multinomial arm, for a measured reason

The dispersion audit compares realised variance to the multinomial's own
`N·π·(1−π)` **at the correct share**, so a ratio above 1 cannot be an artefact
of a bad share. Median **1.193**, against a threshold of **1.25** fixed in
code before the number was read. This system does not exhibit the
overdispersion a DM exists to model, and the external scan is prior art, not a
reason.

## 4. Fallback audit — located, bounded, benign

`HURDLE_MORE_CLEARERS_THAN_BUDGET`, 2,141 events in 869,600 draws (0.246 %):

* **Every single event is in the `<25` budget band.** Mean *drawn* budget
  **5.61**, maximum **13**, against a mean of 11.1 appearing players and 8.7
  clearers. It fires only in the low tail of the budget's own residual pool —
  simulated team-weeks with a handful of targets — not in real slates.
* **Selection rates rise monotonically with the declared hurdle probability**:
  0.150 at `p≈0.2` through 0.839 at `p≈1.0`. The subsample is weighted by the
  base share, not by `p_hurdle`, and the gradient is the correlation between
  the two rather than an inversion. No player with a high declared probability
  is being preferentially dropped. The rates cannot equal `p_hurdle` — only
  `budget` of 8.7 clearers can survive — and that bound is arithmetic, not a
  defect.
* **Affected team-games score better, not worse**: marginal CRPS 0.8104 in
  affected games against 0.8307 elsewhere, with a zero gap of −0.0094 against
  +0.00006. The fallback is not carrying the result and is not damaging the
  games it touches.

`HURDLE_NO_CLEARERS` fired **0** times in this run (1 in 869,600 in Q9's own
run). Reported whatever its rate, as registered.

**Nothing was changed.** The directive said measure first and that is all this
did.

## 5. PIT diagnosis — located, and not optimised

Q9 improves CRPS and zero mass while marginal PIT χ² rises 8,821 → 8,913. χ²
per row, Q9 minus baseline:

| cut | Δχ² per row | |
|---|---|---|
| actual = 0 | −0.0509 | better |
| actual 1–2 | **+0.0543** | **worse** |
| actual 3–6 | −0.0449 | better |
| actual 7+ | +0.0409 | worse |
| starter | −0.0068 | better |
| rotational | +0.0193 | worse |
| fringe | +0.0283 | worse |
| prior depth 0 | **+0.3763** | **worst by an order of magnitude** |
| prior depth 1–3 | +0.0431 | worse |
| prior depth 4–8 | −0.0183 | better |
| prior depth 9–16 | −0.0058 | better |
| prior depth 17+ | −0.0013 | better |

**The deterioration is the one-target floor, seen from the rank histogram.**
It is concentrated in cold-start players and in realised counts of one or two
— precisely where a clearer is forced to exactly 1 and mass piles on that
value. The zero mass and the middle both improve.

Cold start is therefore where Q9's CRPS gain is largest (−7.30 % in its own
run) **and** where its PIT is worst. Both are true and neither is smoothed.

**PIT was diagnosed and never optimised.** No arm was selected on it and no
decision function reads it.

## 6. Production parity — bit-for-bit

Twelve frozen 2024 team-weeks, run through `layers.appearance` — the real
production interface, its Outcome contract and its `_game_stream` seeding —
then through the frozen Q9 allocator via an adapter that **consumes** the
appearance draws and never redraws them.

| invariant | |
|---|---|
| `RECONCILES_EXACTLY` | ✓ max absolute error 0.0 |
| `SAME_UPSTREAM_BUDGET` | ✓ |
| `SAME_R8_APPEARANCE_DRAWS` | ✓ consumed, not redrawn |
| `NO_MARKET_INPUTS` | ✓ |
| `NO_2026_FITTING` | ✓ |
| `NO_Q8_BUDGET_REPAIR` | ✓ |
| `DETERMINISTIC_REPRODUCIBLE` | ✓ two runs at one seed identical |
| `RESEARCH_HARNESS_PARITY` | ✓ **bit-for-bit**, zero differing cells |

**`test_only` propagates and that is the guard working.** The slice is
historical so the fixture path is used, the run produces no artifact and the
sealer would refuse it. A parity test that quietly produced a publishable
artifact would be the defect.

**What this cannot claim**: Q9 has no promoted production path, so this is not
"the promoted pipeline ran". It is the production interfaces being exercised
by the frozen candidate and agreeing exactly with the research harness. That
is what was available to test and the limit is stated rather than glossed.

## 7. Prospective freeze — recorded, nothing consumed

`Q9_PROSPECTIVE_FREEZE.json` records the candidate's identity rather than a
description of it: the source hash of every executing module, the 25-feature
schema in order with its own hash (`f620eeed09d0dd6e`), the hurdle
coefficients (`9491bb9f4b09b6a2`), the standardiser, the class prior, the
shrinkage constant, the budget estimator and its residual pool, the production
interface version, both fallback counters, and the decision metrics as they
stand.

**No 2026 outcome was read.** A refit is declared a different candidate
needing its own freeze, and the artifact records what would falsify the
candidate: the zero-rate gap failing to narrow on unseen games, or the
marginal CRPS gain not reproducing outside the seasons that selected it.

---

## Status

**PROMOTION_READY_FOR_PROSPECTIVE_TEST.**

* mechanism identified as structural, against a rule fixed before the numbers ✓
* the plain family does not match it — it moves the zero mass the wrong way ✓
* production parity holds on every invariant, bit-for-bit ✓
* fallbacks measured, located, bounded and benign; nothing changed ✓

The one thing that argues for caution rather than against readiness is the PIT
deterioration at cold start, and it is diagnosed to a specific mechanism — the
one-target floor — rather than left as a number.

**Nothing is promoted.** The next step is unseen 2026 games against the frozen
candidate.

## Artifacts

| file | what it is |
|---|---|
| `Q9B_PREREGISTRATION.md` | the arm set, registered before any was built |
| `Q9B_IDENTIFIABILITY.json` | the zero-mass decomposition and the dispersion audit |
| `Q9B_FAMILY_RESULTS.json` | three arms, every stratum, the falsifiable check, the PIT scan |
| `Q9_FALLBACK_AUDIT.json` | where the fallback fires and what it costs |
| `Q9_PRODUCTION_PARITY.json` | eight invariants on twelve frozen team-weeks |
| `Q9_PROSPECTIVE_FREEZE.json` | the candidate's identity, hashed |
| `Q9B_FAMILY_ROWS.csv.gz` | 104,130 scored rows, three arms |
