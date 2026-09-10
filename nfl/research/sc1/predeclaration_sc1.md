# SC1 pre-registration — scramble/carry joint coherence

**Written before the repair is built or scored.** §1 is measurement of already-
frozen components against already-realised history; it fits nothing.

---

## 1. The audit the ruling asked for, first

**The identity is exact in football.** Over 3,230 team-games, 2020–2025 REG:
scrambles exceed team carries in **0**. It is a law, not a convention — a
scramble *is* a rush attempt.

| | mean | sd | extreme |
|---|---|---|---|
| team carries | 26.92 | 7.58 | min **5** |
| team scrambles | 1.82 | 1.70 | max **11** |
| corr(scrambles, carries) | **+0.1802** | | Spearman **+0.1628** |

**The supports overlap**, so no marginal argument alone excludes the violation:
a 5-carry team-game and an 11-scramble team-game both occur.

**What R2 already fixed.** Before R2 the model summed a scramble draw over
*every rostered quarterback as if each were the primary passer*: team scrambles
mean **5.973**, max 24, against a historical 1.82/11 — and **16 of 6,400** cells
violated. Under R2 the level is apportioned from D1 × QB3 and the same
measurement gives mean **2.046**, max 12, and **0 of 6,400** violations across
all 32 teams. *The level defect was never the coupling defect, and it is already
repaired.*

**What remains, isolated.** Running per game exactly as `run_forecast` does:

| game | A3G off | A3G `off_snaps` |
|---|---|---|
| TB/CIN | **0** | **1** cell — scrambles 8 against a carry draw of 5.3 |
| ARI/LAC | 0 | 0 |
| ATL/PIT | 0 | 0 |

A3G does not lower the carry draw — the minimum is 5.26 either way. It changes
**which draw index** that minimum lands on, and in one draw it lands where the
scramble count is high. So the residue is a **tail-overlap event under a draw
index on which the two quantities are independent**: model corr(scr, car) is
**+0.0299** against a historical **+0.1802**. The model is *under*-coupled, and
the violation is what under-coupling looks like in the tail.

**Answer to the ruling's first question:** yes — the existing D1/A3G joint
structure can carry this. A3G is already a rank copula that couples two draws
while preserving both marginals **by construction**, because it permutes which
draw index receives which value. No new estimator family is required.

## 2. SC1, the repair

**A feasibility-constrained permutation of the team carry draw index.**

For each team, the m carry draws are a multiset. SC1 chooses *which draw index
receives which carry value*, subject to `carries_j >= scrambles_j` in every
draw j. It changes no value, adds no parameter, fits nothing, and clips
nothing: a permutation leaves the marginal **exactly** invariant, element for
element.

1. Start from the draw index the current pipeline produced (A3G's, when on).
2. Where a cell violates, exchange its carry value with the smallest carry
   value that satisfies the constraint and whose own draw still satisfies it
   after the exchange. **Minimal swaps only** — a cell that already satisfies
   the constraint is never touched, so A3G's game-level pairing survives
   everywhere it was not the problem.
3. **Feasibility is checked, not assumed.** A satisfying assignment exists iff
   `sorted(scrambles)[k] <= sorted(carries)[k]` for every k. Verified on
   history: 0 of 3,230 ranks fail. When it fails, SC1 **REFUSES by name**
   (`SC1_NO_FEASIBLE_ASSIGNMENT`) rather than clipping, inflating or
   renormalising.

**What SC1 is not.** Not a redefinition of scrambles as a share of carries.
Not clipping scrambles after drawing. Not post-hoc inflation of carries. Not
survivor renormalisation. Not a new estimator. It is a choice of joint state,
made at generation time, among states the marginals already permit.

**Declared in advance:** SC1 will *raise* corr(scrambles, carries) slightly,
toward the historical +0.18 and away from the model's +0.03, because removing
the infeasible pairings removes exactly the most negatively-coupled ones. That
is a side effect of the constraint, **not a fitted target**, and SC1 will not
be tuned to reach any particular correlation.

## 3. Gates — pass/fail, never traded

0 cells with scrambles > carries · 0 negative rush-play budgets · A1 exact
rushing closure preserved · QB dropback closure preserved · scramble marginal
**exactly** unchanged (SC1 does not touch it) · team-carry marginal **exactly**
unchanged as a multiset (permutation) · QB rushing tails plausible · no new
clipping or capping · no duplicate ownership · game-level A3G dependence not
materially lost · no cross-game RNG contamination · deterministic replay.

Distributions are evaluated, never predictive means. The per-draw discipline
holds: any statistic compared against a realised series is computed one draw
per team-game and reported over draws.

## 4. Decision rule, declared before scoring

1. **Simplest wins, and the incumbent is "no coupling".** SC1 is retained only
   if it reaches **0 violations** while holding every gate in §3.
2. If SC1 reaches 0 violations but materially degrades a marginal, it is
   **rejected** — and since it is a permutation, any marginal change at all is
   evidence of an implementation defect, not a trade-off to accept.
3. If A3G's measured game-level dependence degrades materially, SC1 is
   rejected and the finding reported.
4. Development evidence may establish engineering suitability. It does not
   promote anything.

## 5. What this pre-registration does not license

No change to scramble ownership. No rushing-yard conversion model —
`RUSHING_CONVERSION_CONTROL_UNDEFINED` is untouched. No edit to
`PATH_C_STATE`. No 2026 outcome read. No second candidate: one repair is
specified here, so there is no ladder to score.
