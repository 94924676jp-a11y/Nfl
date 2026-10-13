# Pre-registration: PROJ-FIX-1, a measured zero claim is evidence, not a missing value

- **Written:** 2026-10-13, before the fix was implemented or backtested. The commit time is authoritative.

## The defect (verified at code level on the BUF@LAR pre-lock projection)

**Where.** `proj_v1.allocate_opportunity` builds each player's claim as `max(0, claim or 0)`, which erases the
difference between **missing** (None) and **measured zero**. The blend step (`proj_v1.py:921-926`) then gives any player
whose claim is 0 **half his depth prior** ("one side has no evidence at all").

**What it did.** Tight ends with a **measured** carry claim of 0 received carries taken from the running backs:

| team | share of carries given to zero-claim players |
|---|---|
| BUF | 5.2% (Kincaid) |
| LA | 6.4% (Higbee 5.2%, Parkinson 1.2%) |

The fallback is right for a *missing* measure ("never silently removed by a missing measure"), wrong for a measured
zero.

## The fix (`NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE=1`, opt-in; the default is byte-identical)

- A claim that was **measured** (not None) and is zero takes weight 0 in that field.
- The half-depth fallback is kept **only** for a claim that is missing (None, for example a cold start).
- No new constant.

## Test: the production allocator on held-out seasons

- **Harness:** `nfl/tools/forward_chain.evaluate`. Point in time: priors through the previous season, current-season
  evidence strictly before the scored week.
- **Arm:** production settings (`DEPTH_CLAIM_BLEND` 1.0, `PRIOR_WEIGHT_CAP`), with the flag off against on.
- **Seasons:** 2024 and 2025 (the harness's held-out seasons).
- **Isolation:** run in an isolated overlay; no derived file is written.

**Metrics, paired by week**, with the difference = on − off and a week-blocked bootstrap 95% interval:

- DK-points MAE, overall;
- DK-points MAE and level ratio for RB and for TE.

**Pre-declared reading.** **Adopt** (as a registered change, promoted only with the owner's approval) if both hold:

1. the overall MAE difference's interval excludes harm (upper bound ≤ 0);
2. neither the RB nor the TE MAE worsens with an interval excluding 0.

**Otherwise reject**, and keep the defect logged.

**The harness's own limit applies:** it is conditional on playing, so the numbers are upper bounds on live performance.
