# Pre-registration: PORT-D3 candidate-pool recall and stage attribution (BUF@LAR 2026 W5, DIAGNOSTIC ONLY)

- **Written:** 2026-10-13, before any recall or enriched-pool number was computed. The commit time is authoritative.
- **Status:** DIAGNOSTIC / discovery. The game's outcome is known and has been inspected, so **nothing here can confirm
  a challenger**. Confirmation requires untouched future slates (week 6 onward), under the existing
  `PREREG_W6_PLUS_EVALUATION.md` structure. No production change follows from this document.

## Frozen inputs (pre-lock, immutable)

| input | file | sha256 |
|---|---|---|
| primary worlds | `FINAL_CV1/SHOWDOWN_BUF_LAR_2026W5_DRAWS.json` (corrected arm, seed 20261005, 2,000 worlds) | `a1592f79…` |
| independent panel | `SHADOW_S1SEED_FINAL_CV1/…_DRAWS.json` (same arm and inputs, seed + 1) | `24925301…` |
| the production pool | `FINAL_CV1/SHOWDOWN_BUF_LAR_CANDIDATES.csv` (5,946 lineups) | `8dda2af6…` |
| code | `9291223e` | — |

## Definitions, fixed now

- **Universe U.** Every legal Showdown lineup over the players with draws in the primary worlds:
  - one CPT plus five distinct FLEX;
  - CPT salary 1.5 × FLEX;
  - total salary ≤ $50,000;
  - both clubs represented.
- **Exact world optimum.** The maximum over U, per world. It must equal the production solver's optimum
  (`showdown_portfolio.world_optimum`) in every world. Any mismatch is reported and stops the study.
- **Persistence h(L).** The number of primary worlds in which L scores at least (1 − `NEAR_OPTIMAL_LOSS_BAND`) × the
  exact world optimum. This is the production band, 0.10.

## Measurements

1. **Recall.** For thresholds T at the production pool's own median h, its 75th percentile and its 90th percentile: the
   share of lineups in U with h ≥ T that are in the production pool. Also reported:
   - for the top-N lineups of U by h, with N = 5,946;
   - stratified by captain, and by number of RBs in the lineup.
2. **Stage attribution.** The same selector `showdown_portfolio.build_contests`, with the same caps, ladder, polish,
   GLOBAL overlap policy and contests, run on three pools:
   - **(a)** the production pool;
   - **(b)** an enriched pool of the **same size** (5,946): the top-5,946 lineups of U by h, ties broken by mean score;
   - **(c)** the union of (a) and (b).

   Each portfolio is scored on the **independent panel** for coverage and objective E[min(depth, m)], the
   decision-relevant out-of-sample number. It is also scored on the primary worlds (in-sample, labelled as such).
   Selector runtime is reported.
3. **Hindsight, labelled HINDSIGHT and never a decision input:**
   - each arm's portfolio scored with the actual DK points;
   - the rank of the actual winning lineup by h in U.

## Interpretation, fixed now

- If (b) or (c) beats (a) on the independent panel, candidate recall is a **measured** contributor on this slate's own
  worlds. That says nothing about ROI.
- If none does, the blind spot exists but does not cost coverage on our own model's worlds, and the loss was forecast or
  variance.
- No result may be read as "a bigger pool would have won Monday".
- Selector failure, as distinct from candidate failure, is assessed separately: exact or bounded selection on the same
  pool. It is not part of this registration.
