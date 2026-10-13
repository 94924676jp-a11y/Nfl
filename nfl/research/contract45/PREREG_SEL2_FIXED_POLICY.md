# Pre-registration: SEL-2, fixed-policy caps for 20-entry contests (owner decision 2026-10-13)

- **Written:** 2026-10-13, before SEL-2 was implemented or run. The commit time is authoritative.
- **Owner decision**, AskUserQuestion, 2026-10-13: for 20-entry contests the policy is **fixed level 2**.
  - player ≤ 13 of 20 (65%);
  - captain ≤ 6;
  - overlap ≤ 5.
  - No greedy-triggered relaxation.
  - A contest that cannot fill at this policy **fails loudly**.
- **Scope:** contests with 3 ≤ entries < 100. The 150-max and 2-entry contests keep the current ladder (no owner
  decision covers them).

## Mechanism (`NFL_SHOWDOWN_SELECTOR=FIXED_POLICY_V1`, opt-in until promoted)

1. Build the contest at `LADDER[2]` only.
2. If greedy is short, apply the SEL-1 exchange repair at that level.
3. If still short, return the short portfolio flagged `POLICY_UNFILLABLE`. The upload verifier then refuses the file
   (entry counts no longer match). No silent relaxation.

## Test (the same harness, data and splits as SEL-1)

- **Selectors:** GREEDY against FIXED_POLICY_V1.
- **Pools:** identical.
- **Overlap policy:** GLOBAL.
- **Worlds:** select on even worlds, score on odd worlds.
- **Stability:** 5 random 90% pool subsamples.
- **Metrics:** 20s E[min(depth, 2)]; 150s coverage.

**Reading, fixed now.** SEL-2 is **acceptable** for promotion on a slate if, for each 20-entry contest, all three hold:

1. it fills at its policy (no `POLICY_UNFILLABLE`);
2. its subsample spread is ≤ the greedy's;
3. its held-out objective is within the greedy's subsample min-max range or above it.

**Promotion to default** for week 6 onward requires acceptability on all three frozen slates. This is diagnostic
evidence on model worlds. It is not evidence about money.
