# Pre-registration: SEL-2 against the incumbent selector, prospective from Week 6

- **Written:** 2026-10-13, before any Week 6 slate exists. The commit time is authoritative.
- **Owner decision, 2026-10-13:** SEL-2 (`NFL_SHOWDOWN_SELECTOR=FIXED_POLICY_V1`) stays a **governed experimental
  switch** for Week 6. It is **not** the production default.
  - Promotion requires that SEL-2 consistently improve selection and pass the existing governance tests.
  - It is not to be promoted on the strength of one synthetic example or one retrospective slate.
- **Excluded:** W4 and W5 (ATL@NO, TB@DAL, BUF@LAR) are **diagnostic only**, and nothing from them enters this test.
  Monday's outcome is not used to tune anything.

## Arms and identical inputs

| | |
|---|---|
| Incumbent | `GREEDY` (the production default) |
| Challenger | `FIXED_POLICY_V1` |

Per slate, both arms use exactly the same:

- frozen pre-lock draws file;
- candidate CSV;
- DK export and contest definitions;
- overlap policy (whatever production uses for that slate);
- world split.

Any difference in input hashes between the arms voids that slate.

## Harness (`sel2/sel2_paired.py`, fixed with this file)

**World split.** Selection worlds S are the even indices; evaluation worlds H are the odd indices. `hit` is computed on
S against the pool's own per-world best, and portfolios are scored on H.

**Metrics, per contest and arm:**

1. **H objective.** For 3 ≤ n < 100: E[min(depth, m)], using the arm's own m. For the other contests, coverage.
2. **Pool stability.** The spread (max − min) of the H objective over 5 random 90% pool subsamples, with the subsample
   draw fixed at `default_rng(1)`.
3. **Nested-pool monotonicity** (the package's EDU02 pattern).
   - The count of subsamples in which the **full** pool's S objective is **below** that subsample's S objective.
   - A full pool is a superset of each subsample, so a monotone selector never does worse on it.
4. **Order sensitivity.** The build order of equal-size contests is reversed by swapping their prize-pool labels in a
   copy of the contest definitions; production code is not touched. The measure is |ΔH objective| for each affected
   contest.
5. **Runtime** of the full build, in seconds.
6. **Constraint compliance**, checked by an independent checker that shares no state with the selector:
   - the portfolio size equals n, and its lineups are distinct;
   - excluded lineups are honoured (no lineup shared across contests under GLOBAL);
   - player and captain counts are within the caps, recomputed from the reported level (floor at level 0, ceil at
     levels 1-3, n for n ≤ 2);
   - pairwise overlap is within the level's limit;
   - for SEL-2, every 3 ≤ n < 100 contest sits at level 2.

## Confirmatory unit

**Each contest with 3 ≤ n < 100 entries.** It is the only kind in which the arms differ by construction. The 150-entry
and 2-entry contests are the **negative control**: they must be identical between the arms.

## Decision rule (fixed now)

### Hard gates

Any failure on any slate blocks promotion, and the failure is recorded:

| gate | condition |
|---|---|
| G1 | zero violations from the independent checker, in either arm |
| G2 | no `POLICY_UNFILLABLE` |
| G3 | the negative-control contests are identical between the arms |
| G4 | SEL-2's full-build runtime ≤ 2 × the incumbent's. This is a declared operational tolerance, not a fitted value. |

### Primary: stability

- d = spread(SEL-2) − spread(incumbent), per contest. Ties (d = 0) are excluded.
- **Promote-eligible** if a one-sided exact sign test favours SEL-2 at p ≤ 0.05. That requires at least 5 of 5, 6 of 7
  or 7 of 8, and so on.

### Secondary conditions (all must hold)

- **Objective non-inferiority:** in every contest, SEL-2's H objective ≥ the incumbent's subsample minimum.
- **Order sensitivity not worse:** the one-sided sign test for "SEL-2's |Δ| is larger" must not reach p ≤ 0.05.
- **Monotonicity not worse:** SEL-2's total count of nested-pool violations ≤ the incumbent's.

### When the analysis is run

- **Once**, when the number of non-tied contests first reaches **6**.
- If that has not happened by the end of Week 10, the result is **INCONCLUSIVE**.
- There is no interim look.

### Outcomes

| result | what follows |
|---|---|
| PASS | **eligible for promotion**, which is still the owner's decision |
| FAIL | rejected, with the result preserved |
| INCONCLUSIVE | stays opt-in |

## Realised outcomes

After each game, the arms' portfolios are scored on actual DK points. That record includes:

- each arm's best realised lineup score;
- whether each arm contains a lineup within 10% of the realised optimum.

This is **descriptive only**. One game per slate cannot rank selectors, and it is never used in the decision.

## What this does not test

- Payout, ROI and duplication against a real field: no lawful field or prize model exists.
- The candidate generator, which is a separate experiment with a fixed pool size and compute budget.

## AMENDMENT 1 (2026-10-13, ~20:00 UTC, before any Week 6 data exists; the decision rules are unchanged)

**The limitation:** production generates its candidates from **all** worlds (`showdown_portfolio.py:909-918`). The H
worlds therefore helped shape the shared pool.

**What this does and does not affect:**

- It does **not** bias the paired comparison: both arms use the same pool.
- It **does** make the absolute H objectives optimistic.

So H values are reported as **paired differences only**, never as absolute out-of-sample performance. Generation worlds
that are disjoint from evaluation worlds belong to the candidate-generator experiment (CG-1), not to this test.

## AMENDMENT 2 (2026-10-13, ~20:30 UTC, before any Week 6 data exists; the decision rules are unchanged)

**1. Equal objectives only.** Nested-pool monotonicity compares S objectives only where the full pool and the subsample
ran with the **same m**. E[min(depth, m)] under a different m is a different objective. Each contest reports
`nested_comparable` beside `nested_violations`.

**2. What the metric means for each contest.**

- **First-built contest:** a clean selector-monotonicity test, because nothing is excluded.
- **Later contests:** under sequential exclusion, a later contest's feasible set depends on what the earlier contests
  took. Its count therefore measures selector and exclusion coupling **together**, and it is reported as such.

**Shakedown, diagnostic only.** On the frozen W5 slates, m was equal in all comparisons, and the counts were unchanged
by this amendment.
