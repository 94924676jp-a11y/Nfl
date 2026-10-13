# Result: PROJ-FIX-1 (a measured zero claim is evidence): REJECTED by its pre-registered bar

- **Pre-registration:** `PREREG_PROJFIX1_ZERO_CLAIM.md` (`44f1b54e`).
- **Code under test:** `projfix1/patch_projfix1.py`. It adds the opt-in `NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE=1` to
  `proj_v1.allocate_opportunity`:
  - a claim that is **measured** (not None) and ≤ 0 takes weight 0 in that field;
  - the half-depth fallback stays only for a **missing** claim.
- **One change from the drafted patch, made before any run:** the test keys on the **raw measured claim**, not on the
  claim after the appearance multiply. Otherwise a player with a nonzero claim and a zero appearance rate would also
  lose his fallback, which the pre-registration does not declare.
- **Production is unchanged.** The change was rejected, so `nfl/tools/proj_v1.py` was restored byte for byte. The
  patch, the harness, a unit check against a patched copy (`projfix1_unit_check.py`), and the per-week rows are kept
  here so the result can be reproduced.

## Run

- **Harness:** `projfix1/projfix1_eval.py` runs `forward_chain.evaluate` with the production arm (`DEPTH_CLAIM_BLEND`
  1.0, `PRIOR_WEIGHT_CAP`) on held-out 2024-2025. That is 28 scored weeks and 7,182 player-weeks, conditional on playing.
- **Isolation:** each arm ran in its own overlay of the repository; no derived file was written.
- **Three arms:**
  - the incumbent code;
  - the patched code with the flag off;
  - the patched code with the flag on.

**The default is byte-identical.** The incumbent and the flag-off arm produce identical per-week rows for all 28 weeks.
The unit check also shows identical allocation records, unset against `0`.

## Paired result (flag on − off)

Pooled n-weighted over weeks, with a week-blocked bootstrap: 10,000 resamples, seed 20261013. Lower MAE is better.

| metric | off | on | difference | 95% interval |
|---|---|---|---|---|
| **DK-points MAE, all** | 5.9119 | 5.9174 | **+0.0055** | **[+0.0032, +0.0080]** |
| **RB MAE** | 5.8450 | 5.8649 | **+0.0199** | **[+0.0106, +0.0295]** |
| TE MAE | 4.4942 | 4.4928 | −0.0014 | [−0.0023, −0.0004] |
| QB MAE | 7.6935 | 7.6959 | +0.0023 | [−0.0030, +0.0075] |
| WR MAE | 6.1602 | 6.1612 | +0.0010 | [+0.0003, +0.0017] |
| RB level ratio | 0.7804 | 0.7920 | +0.0116 | [+0.0107, +0.0126] |
| TE level ratio | 0.8692 | 0.8683 | −0.0009 | [−0.0010, −0.0008] |

Pearson goes from 0.5108 to 0.5115 and RMSE from 8.2398 to 8.2438.

## Pre-declared reading, applied as written

1. **The overall MAE interval must exclude harm (upper bound ≤ 0). FAILS:** [+0.0032, +0.0080] lies entirely on the
   harmful side.
2. **Neither the RB nor the TE MAE may worsen with an interval excluding 0. FAILS for RB:** [+0.0106, +0.0295].

**REJECTED.** The defect `PROJ-D-TE-CARRIES` stays **logged and open**, and the production allocator is unchanged.

## What this does and does not say

- The effect is small either way: half a hundredth of a DK point overall, two hundredths for backs. The fix sends tight
  ends' fallback carries to the backs. That raises the backs' level, and their absolute error rises slightly anyway.
- **A hypothesis, not tested here, and not to be tuned into the fix after the fact:** a "measured" zero from a short
  window is weak evidence. The half-depth fallback may act as useful shrinkage for players who carry occasionally. Any
  variant that conditions on window length needs its own pre-registration and a sourced, not fitted, threshold.
- Monday's Kincaid outcome plays no part in this verdict. The harness never sees week-5 2026.
- The harness is conditional on playing, so these are upper bounds on live performance.

## Unrelated test states recorded while running this

These failures were **already present at HEAD**; they were checked in an overlay with the incumbent code:

- `test_showdown_family.py`: 10 of 12 fail. The test pins its data-cutoff file to `pbp_2026.79b02496d26004ee.csv.gz`,
  but the latest captured blob is now `pbp_2026.2b3e9f2c6f92123f.csv.gz`. The pin has gone stale; it is not a code fault.
- `test_role_depth_adversarial.py`: 1 of 22 fails, with `SLATE_STATE_NO_IMPLIED_TOTAL` in the state builder.

Neither is touched here.
