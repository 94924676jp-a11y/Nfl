# Result: SEL-1 fill-repair selector. FAILED its pre-registered test (diagnostic, three frozen slates)

- **Pre-registration:** `PREREG_SEL1_FILL_REPAIR.md` (`de47858f`).
- **Code:** SEL-1 is opt-in (`NFL_SHOWDOWN_SELECTOR=FILL_REPAIR_V1`). The default is unchanged.
- **Byte-identity check:** the default selector on the BUF@LAR final pool reproduces the production portfolio exactly in
  all three contests.
- **Raw output:** `sel1/sel1_summary.json` (per-run results); harness `sel1/sel1_eval.py`.

## Design, as registered

- **Pools:** identical (each slate's production pool).
- **Policy:** the same (GLOBAL overlap, caps, ladder, polish).
- **Worlds:** select on even worlds, score on odd worlds against the exact per-world optimum.
- **Stability:** 5 random 90% pool subsamples.
- **Metrics:**
  - 150-max: coverage.
  - 20s: E[min(depth, 2)].
  - **Deviation, disclosed:** the registered "objective with the selector's own m" is not comparable for the 150s,
    because m steps from 1 to 2 to 3 when coverage saturates. The 150s are compared on coverage instead.

## Results (held-out worlds)

| slate | contest | greedy (level) | SEL-1 (level) | subsample spread, greedy / SEL-1 | verdict |
|---|---|---|---|---|---|
| BUF@LAR | $10K 20 | 0.880 (L2) | 0.767 (L0) | 0.163 / **0.016** | **FAIL** (objective) |
| BUF@LAR | $5K 20 | 0.801 (L1) | 0.755 (L0) | 0.032 / 0.116 | **FAIL** |
| TB@DAL | 20 #1 | 1.192 (L2) | 1.093 (L1) | 0.105 / 0.105 | **FAIL** |
| TB@DAL | 20 #2 | 1.047 (L1) | 1.142 (L2) | 0.103 / 0.057 | pass |
| ATL@NO | all three | identical | identical | identical | no effect (repair never completed) |
| all slates | 150-max | identical | identical | identical | no effect |

**The 150-max coverage subsample spread is small** (0.009-0.011) under both selectors. The 150 is not where the
instability lives.

## What this establishes

1. **SEL-1 is rejected as designed.** It is kept opt-in, not promoted.
2. **The ladder's looser caps raise the simulated objective.** A selector that holds the declared caps scores lower by
   construction.
   - The instability is not "greedy is bad".
   - **The cap policy is being chosen by the greedy's failures**: whether a 20-entry contest ends at level 0, 1 or 2
     depends on pool composition and on which lineups earlier contests took.
3. **There are three separate discontinuities:**
   - ladder relaxation on greedy shortfall;
   - the depth target m escalating on saturation (the 150s: m between 1 and 3);
   - sequential contest building under GLOBAL exclusion (repairing contest #1 moved contest #2 from L1 to L2 on TB@DAL).

## Next challenger, to be registered separately

**SEL-2.** Caps declared per contest **by policy**, with no greedy-triggered relaxation. A contest that cannot fill at
its declared caps fails loudly, and the exclusion is applied jointly.

**This needs an owner decision on the cap level for 20-entry contests.** Every 20-entry build on these slates ended at
level 2 (player cap 13 of 20 = 65%) at least some of the time.

**These are engineering metrics on model worlds.** They say nothing about predictive accuracy or money.
