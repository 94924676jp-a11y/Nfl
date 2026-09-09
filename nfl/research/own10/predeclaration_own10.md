# OWN-10 pre-registration — A2 dependence refinement

**Written before A2 is built or scored.** §1 is measurement of an already-frozen
A1 against already-realised history; it fits nothing and chooses no parameter.
§2 onward is the pre-registered test.

---

## 1. The chartered premise does not survive measurement

The ruling authorising OWN-10 states A1's remaining weakness as:

> Observed: corr(designed_QB_rush, team_carries) ≈ +0.314; A1: ≈ +0.507

**The +0.507 is not a measurement of A1's dependence. It is an artifact of my
own OWN-9 reporting code**, and the defect is one this project has now found six
times in a different costume.

`run_own9.py` built the co-movement series as
`np.mean(d['designed_qb'])` — the **per-team-game predictive mean over 400
draws** — and correlated that against the realised `team_carries`. Reality
supplies one draw per team-game, carrying its full idiosyncratic noise.
Averaging 400 draws removes exactly that noise while leaving the budget-aligned
component intact, so the ratio Cov/(SD·SD) is inflated. The two series are not
the same statistic and were never comparable.

The same file carries, eleven lines above the defect, the correct reasoning for
CRPS — *"a distribution of predictive MEANS has almost no zero mass and a far
narrower spread"* — and then, three lines below it, the assertion that means are
*"the right object for a correlation against a per-team-game budget."* Both
cannot be true. The comment is wrong and the code followed the comment.

**Computed identically on model and reality — one draw per team-game, the
structure reality actually has — A1's dependence matches.** n = 1,630 team-games,
400 draws, evaluation 2022–2024.

| statistic | observed | A1 per-draw mean | A1 90% band | z | mean-based (not comparable) |
|---|---|---|---|---|---|
| designed QB rush vs team carries | **+0.3140** | **+0.3065** | [+0.2768, +0.3388] | **+0.40** | +0.5070 |
| designed QB rush vs dropbacks | **−0.1521** | **−0.1603** | [−0.1920, −0.1285] | **+0.42** | −0.2651 |

And it holds in every fold separately, so it is not a pooled coincidence:

| fold | n | observed | A1 per-draw | 90% band | inside |
|---|---|---|---|---|---|
| 2022 | 542 | +0.3291 | +0.2988 | [+0.2410, +0.3517] | yes |
| 2023 | 544 | +0.2963 | +0.2750 | [+0.2161, +0.3280] | yes |
| 2024 | 544 | +0.3141 | +0.3434 | [+0.2958, +0.3956] | yes |

The regression slope on the budget agrees to three decimals: A1 **0.1033**
against observed **0.1039**.

**Therefore the defect A2 was chartered to repair is not present in A1.** This
is stated as a withdrawal of my own prior claim, not as a disagreement with the
ruling: the ruling quoted the number my artifact gave it.

## 2. A2 is still tested, because a withdrawal argued is weaker than one measured

Rather than close OWN-10 on the argument above, A2 is built as chartered and
scored. If the premise is genuinely absent, A2 must be shown to **cost**
something, not merely to be unnecessary.

**A2(τ) — A1 plus a budget-orthogonal latent on the designed-QB share.**
Identical to A1 in every other respect: same categories, same estimator family,
same centres, same residual pool, same multinomial partition of the same
`rush_play_budget`, same RNG streams. The single difference is one additional
additive term on the designed-QB share, drawn per team-game per draw:

    u ~ Normal(0, tau)         independent of budget, dropbacks and every other category
    p_designed_qb = max(centre + residual + u, 0)

then normalised across all six categories exactly as A1 normalises. The latent
therefore cannot break closure: it moves a share, and the multinomial partitions
the same integer budget regardless.

**τ grid, declared now:** `0, 0.0025, 0.005, 0.01, 0.02, 0.04`. **τ = 0 is
exactly A1** and is included so the grid contains the null. No τ outside this
grid will be fitted, and the grid will not be extended after seeing results.

## 3. Metrics — the ruling's list, each computed per draw

Dependence (designed QB rush vs team carries; vs dropbacks; kneel, RB, WR, TE,
fringe vs both), cross-category dependence, CRPS per category, zero mass, SD,
p95, p99, and the per-fold behaviour of each. Every model statistic is computed
on **one draw per team-game** and reported as the distribution over draws, so
the realised value is compared against a distribution of the same statistic.

Uncertainty is reported as the across-draw band. It is **not** a sampling
interval for the underlying dependence and is not written as one: it holds the
budgets, the fitted parameters and the schedule fixed.

## 4. Hard gates, from the ruling, checked per draw and reported as counts

0 closure violations · 0 negative allocations · 0 category budget overruns ·
no clipping · no renormalisation repair · every carry exactly one owner ·
kneels explicit · 0 production files changed · no 2026 outcome consumed.

`max(·, 0)` on a share is A1's existing floor, not new clipping, and it is
**counted and reported for both arms** so that a claim of "no clipping" is a
measurement rather than an assertion. A share floor is not an allocation clip:
it cannot move a carry, only a probability.

## 5. Decision rule, declared before scoring

1. **Simplest wins.** τ = 0 (A1) is the incumbent. A2 is retained only if some
   τ > 0 improves dependence agreement **and** does not materially worsen CRPS,
   **in every fold with the same sign**.
2. A single-fold improvement, an improvement in one metric paid for by another,
   or an improvement inside the across-draw band is **not** an improvement.
3. If the criterion is optimised at τ = 0, A2 is **rejected and A1 retained**,
   and the latent has not earned its complexity.
4. Equivalence or indeterminacy resolves to the simpler arm.
5. Nothing here is promoted. Development evidence rejects; it never promotes.

## 6. What this pre-registration does not license

No production file is touched. No 2026 outcome is read. No parameter outside the
τ grid is fitted. The budgets remain oracled identically across arms, so this
tests the allocation architecture and not a whole-forecast gain — the same limit
OWN-9 carried.
