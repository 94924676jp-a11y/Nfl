# Result: D1 target-share shrink, one-look 2025 holdout: **FAIL** by its pre-registered rule

**Inputs.** Pre-registration `PREREG_D1_TARGET_SHRINK.md` (+ amendment 1). `w* = 0.8` was frozen on 2024 in
`D1_ESTIMATE_2024.json` (commit d464f4b1) before 2025 was read. This look is logged in `HOLDOUT_LOOKS.jsonl` (look 1).

| measure (2025, 14 weeks, week-blocked 95%) | value |
|---|---|
| unconditional MAE, D1 − incumbent (6566 rows) | **-0.2275 [-0.2704, -0.1885]** |
| conditional MAE, D1 − incumbent (3779 rows) | -0.4727 [-0.5405, -0.4055] |
| WR | -0.3792 [-0.4656, -0.2949] |
| TE | -0.3762 [-0.4487, -0.3015] |
| RB | **0.0007 [0.0001, 0.0012]** |
| QB | 0.0 |
| top-decile WR+TE level, given play | incumbent 1.256 → D1 1.0135 (naive control 1.1321) |
| D1 − naive STD_U | 0.333 [0.2753, 0.39] (incumbent − naive 0.5605) |

## The rule, applied as written

| condition | outcome |
|---|---|
| unconditional upper 95% bound below 0 | met |
| no position worse with an interval excluding 0 | **not met:** RB +0.0007 DK |
| top-decile level moves toward the naive control | met |

**Verdict: FAIL.**

## What this does and does not say

**Why RB moved at all.**
- RB volume is not shrunk.
- Receiving touchdowns are allocated by red-zone receiving opportunities, and those follow the shrunk WR/TE targets
  (amendment 1). So RB receiving TDs move by a negligible amount.
- The effect is seven ten-thousandths of a DK point per RB-week.

**The design flaw is in the pre-registration, not the data.** It stated no materiality or equivalence margin for "no
position worse". Choosing that margin is a value judgement, so it is the owner's decision. The rule is not reinterpreted
after the fact.

**Consequences.**
- D1 is not tuned further on 2025.
- Any variant, such as a declared margin or holding TD shares fixed, is a new pre-registration. It is evaluated
  **prospectively from W6**, never on the inspected 2025 holdout again.

**Even improved, the core does not beat naive on equal information.** D1 − naive is still positive.
