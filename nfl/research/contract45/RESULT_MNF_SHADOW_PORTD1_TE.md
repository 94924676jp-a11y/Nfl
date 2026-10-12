# Result: BUF@LAR prelock shadow tests S1 (PORT-D1 guard G1) and S2 (Higbee/Parkinson both active)

- **Pre-registration:** `PREREG_MNF_SHADOW_PORTD1_TE.md`, commit `3da6c673`.
- **Inputs:** the CV1_R2 precompute state (corrected arm), code `e0adeb91`.
- **Status:** shadow only; nothing money-facing was changed.
- **Harness check:** the unguarded rebuild reproduces CV1_R2's upload byte for byte.
- Owner contest data (entry IDs, uploads) is not in this repository.

## S1, guard G1

**G1:** a lineup is admissible only if it is within `NEAR_OPTIMAL_LOSS_BAND` of the best same-pool candidate in at least
one world of an independent panel (same arm and inputs, seed + 1, 2,000 worlds).

- 1,021 of 6,616 candidates were inadmissible. The largest primary first-place proxy among them was 0.002.
- **150-max:** 1 lineup replaced.
  - Out: CPT Kincaid / Bills DST / Rams DST / Parkinson / Coleman / Nacua; $36,900; mean 63.4; p95 98.2.
  - In: the same lineup with Davante Adams for Parkinson; $43,900; mean 80.2; p95 120.3.
- **20s:** unchanged.
- **Objective:** 0.9955 / 0.9985 / 0.9375, both arms.
- **150-max coverage, unchanged on all three panels:** primary 0.9955; independent 0.9555; incumbent 0.942.

**Reading.** G1 removes the non-credible filler at zero measured cost. It does **not** remove the mechanism: the
replacement is also near-optimal in a single primary world. A saturated coverage objective still fills its last seats
with single-world lineups. The structural fix (a secondary objective for saturated seats) needs its own registration.

## S2, both tight ends active

**Evidence:** 2025 both active, 8 games: Higbee 10.6% pooled target share. 2026 weeks 1-3: pooled 41 of 369 = 11.1%.
Projection: 18.0%.

**Scenario.** Higbee's target share is set to 11.1% in every allocator pass. The other LA rows are scaled by 1.084, and
the club total is held (identity checked on all 48 calls).

| | CV1_R2 | S2 |
|---|---|---|
| Higbee targets if plays | 6.59 | 4.06 |
| Higbee DK if plays | 11.64 | 7.13 |
| Nacua DK if plays | 21.43 | 22.92 |
| Adams DK if plays | 19.83 | 21.43 |
| Higbee exposure, 150 | 40.7% | 22.0% |
| Higbee exposure, 20 ($10K) | 65% | 10% |
| Higbee exposure, 20 ($5K) | 65% | 25% |
| lineups shared with CV1_R2 (150 / 20 / 20) | — | 10 / 3 / 1 |

**Fixed panel** (coverage on CV1_R2 worlds / S2 worlds):

| portfolio | CV1_R2 worlds | S2 worlds |
|---|---|---|
| CV1_R2 150 | 0.9955 | 0.894 |
| S2 150 | 0.912 | 0.9985 |
| CV1_R2 20s | 0.652 / 0.593 | 0.526 / 0.493 |
| S2 20s | 0.453 / 0.459 | 0.535 / 0.532 |

The 20s comparison is **confounded** by relaxation level. In CV1_R2 both 20s reached only 19 of 20 at level 0 and were
built at level 2 (player cap 13 of 20); in S2 they were built at level 0.

**Verdict: UNRESOLVED; the direction is supported.** The both-active evidence (n = 11 games, per-game share 0% to 22%)
says the 18% claim is high. The engine does not condition roles on which teammates are active. The fix is registered
post-lock work, not a hand override.

## Side findings, logged

| defect | finding |
|---|---|
| **PROJ-D-TE-CARRIES** | The carries depth prior at Higbee's rank is read from the targets table. A tight end with a carry claim of 0 is allocated 1.39 carries, taken from LA's running-back pool (his own DK effect is 0.03). |
| **PORT-D2** | In CV1_R2 both 20-entry builds came up short at relaxation level 0 (19 of 20), because core players reached the 10-of-20 cap. They were filled at level 2, with five players at 13 of 20. |
