# Result: SEL-2, fixed-policy caps for 20-entry contests (diagnostic, frozen slates)

- **Pre-registration:** `PREREG_SEL2_FIXED_POLICY.md` (`092ca711`).
- **Code:** `NFL_SHOWDOWN_SELECTOR=FIXED_POLICY_V1` in `nfl/tools/showdown_portfolio.ladder` (opt-in; the default stays
  GREEDY). Test: `nfl/tests/test_showdown_sel1_fill_repair.py::test_sel2_fixed_policy_level_2_for_20s_untouched_150_and_loud_when_unfillable`.
- **Harness:** `sel2/sel2_eval.py`, the SEL-1 harness with the selector pair changed and an `unfillable` flag added.
  Summary: `sel2/sel2_summary.json`.
- **Status:** **DIAGNOSTIC** on model worlds of three frozen slates whose outcomes are known. It says nothing about
  money or about predictive accuracy. All the numbers come from one model's worlds.

## Results (held-out odd worlds; 20s: E[min(depth, 2)]; 150s: coverage)

| slate | contest | GREEDY full (level) | SEL-2 full (level) | GREEDY subsample min-max, spread | SEL-2 subsample min-max, spread |
|---|---|---|---|---|---|
| BUF@LAR | 150 | 0.947 (L0) | 0.947 (L0) | identical | identical |
| BUF@LAR | $10K 20 | 0.880 (L2) | 0.880 (L2) | 0.782-0.945, **0.163** (levels 2,0,2,1,2) | 0.903-0.945, **0.042** (all L2) |
| BUF@LAR | $5K 20 | 0.801 (**L1**) | **0.892** (L2) | 0.845-0.877, **0.032** (all L2) | 0.845-0.882, **0.037** (all L2) |
| TB@DAL | 150 | 0.953 (L0) | 0.953 (L0) | identical | identical |
| TB@DAL | 20 (a) | 1.192 (L2) | 1.192 (L2) | 1.091-1.196, **0.105** (levels 2,0,0,0,0) | 1.181-1.201, **0.020** (all L2) |
| TB@DAL | 20 (b) | 1.047 (**L1**) | **1.131** (L2) | 1.091-1.194, **0.103** (all L2) | 1.124-1.161, **0.037** (all L2) |
| ATL@NO | 150 | 0.985 (L2) | 0.985 (L2) | identical | identical |
| ATL@NO | 20 | 1.311 (L2) | 1.311 (L2) | 1.272-1.282, 0.010 | identical, 0.010 |
| ATL@NO | 2-entry | out of scope | out of scope | identical | identical |

- **No contest was unfillable** at the policy, on the full pool or on any subsample. The exchange repair was never
  needed (`repaired` false everywhere).
- **The 150s are untouched**, as declared: same lineups, same levels.
- **Runtime** is unchanged (BUF 56 s against 58 s, TB 34 s against 30 s, ATL 113 s against 121 s for the full pool).

## Pre-registered reading, applied as written

| slate | contest | 1. fills | 2. spread ≤ greedy's | 3. objective ≥ greedy's subsample min | acceptable |
|---|---|---|---|---|---|
| BUF@LAR | $10K 20 | yes | yes (0.042 ≤ 0.163) | yes (0.880 in 0.782-0.945) | yes |
| BUF@LAR | $5K 20 | yes | **NO (0.037 > 0.032)** | yes (0.892 above 0.877) | **NO** |
| TB@DAL | 20 (a) | yes | yes (0.020 ≤ 0.105) | yes | yes |
| TB@DAL | 20 (b) | yes | yes (0.037 ≤ 0.103) | yes | yes |
| ATL@NO | 20 | yes | yes (equal) | yes (above the max) | yes |

**SEL-2 is acceptable on TB@DAL and ATL@NO and NOT acceptable on BUF@LAR.** The promotion rule requires all three, so
**SEL-2 does not meet the pre-registered bar for promotion to default.** It stays opt-in.

## What the failure is, without moving the bar

- The BUF $5K 20's two selectors **both ran at level 2 on every subsample**. SEL-2 changes nothing inside that
  contest's own selection. The 0.005 difference in spread comes from **upstream**: under GLOBAL exclusion the $5K 20
  excludes the $10K 20's lineups, and on two subsamples greedy built the $10K at levels 0 and 1, SEL-2 at level 2. So
  the $5K saw a different excluded set.
- This is the third discontinuity named in SEL-1 (sequential GLOBAL exclusion). Fixing the cap level does not remove it.
- A spread from five subsamples has no interval, and 0.005 is very likely noise. **That is not grounds to pass it.** The
  criterion was fixed before the run and is applied as written.

## What the data does show (diagnostic, not confirmatory)

- Where greedy's level jumped, it jumped to **stricter** caps (L1, or L0 on subsamples), and the objective fell with it:
  BUF $5K full pool 0.801 against 0.892, TB 20 (b) 1.047 against 1.131.
- Fixing the level cut the subsample spread from 0.163 to 0.042 and from 0.105 to 0.020 where greedy's level moved.
- Where greedy's level did not move (ATL@NO), the two are identical.

## Decision needed (owner)

The owner set the level-2 policy as a decision of its own (2026-10-13). This result does not overturn it; it says the
pre-registered **evidence** bar for making it the code default was missed on one contest, by an upstream effect the
policy does not address. The two options are:

1. **Keep SEL-2 opt-in.** Week 6 runs set `NFL_SHOWDOWN_SELECTOR=FIXED_POLICY_V1` explicitly per the owner's policy, and
   both selectors are scored prospectively on the same metrics.
2. **Promote by owner ruling,** recorded as a policy decision and not as passed evidence.

The next selector challenger targets the remaining discontinuity: building the 20-entry contests **jointly** rather than
in sequence under GLOBAL exclusion. It will be pre-registered before it is run.
