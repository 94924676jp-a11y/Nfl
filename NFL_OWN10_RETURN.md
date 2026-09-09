# OWN-10 return — A2 rejected, and the premise it was chartered on is withdrawn

**Verdict: `OWN10_A2_LATENT_DOES_NOT_EARN_ITS_COMPLEXITY`. A1 retained.**
Nothing promoted. 0 production files changed. No 2026 outcome read.

Pre-registration `nfl/research/own10/predeclaration_own10.md`,
sha256 `59ea7fa4363b202899e76f7668d2d3f8e517e2c572e4afd040079dbb14de5954`,
committed before A2 was built and re-checked by the runner at execution.

---

## 1. The headline, first: the defect A2 was chartered to fix does not exist

The ruling authorising OWN-10 states A1's remaining weakness as

> Observed: corr(designed_QB_rush, team_carries) ≈ +0.314; A1: ≈ +0.507

**The +0.507 came from my own OWN-9 reporting code and is not a measurement of
A1's dependence.** `run_own9.py` built the co-movement series from
`np.mean(d['designed_qb'])` — the per-team-game predictive mean over 400 draws —
and correlated it against realised `team_carries`. Reality supplies **one** draw
per team-game, carrying its full idiosyncratic noise. Averaging 400 draws
removes exactly that noise while leaving the budget-aligned component intact, so
the ratio is inflated. The two series were never the same statistic.

The same file argued the point correctly for CRPS eleven lines earlier — *"a
distribution of predictive MEANS has almost no zero mass and a far narrower
spread"* — and then asserted three lines later that means were *"the right
object for a correlation against a per-team-game budget."* Both cannot be true.
The comment was wrong and the code followed the comment. **This is the sixth
appearance of the point-for-distribution defect class in this project, and the
first time it reached a headline number in an accepted return.**

Computed identically on model and reality — one draw per team-game — A1 agrees.
n = 1,630 team-games, 400 draws, chronological, evaluation 2022–2024.

| statistic | observed | A1 per draw | A1 90% band | z |
|---|---|---|---|---|
| designed QB rush vs team carries | **+0.3140** | **+0.3065** | [+0.2768, +0.3388] | **+0.40** |
| designed QB rush vs dropbacks | **−0.1521** | **−0.1603** | [−0.1920, −0.1285] | **+0.42** |

And in every fold separately, so it is not a pooled coincidence:

| fold | n | observed | A1 per draw | 90% band | inside |
|---|---|---|---|---|---|
| 2022 | 542 | +0.3291 | +0.2988 | [+0.2410, +0.3517] | yes |
| 2023 | 544 | +0.2963 | +0.2750 | [+0.2161, +0.3280] | yes |
| 2024 | 544 | +0.3141 | +0.3434 | [+0.2958, +0.3956] | yes |

The regression slope on the budget agrees to three decimals: A1 **0.1033**,
observed **0.1039**.

I am withdrawing my own claim, not disputing the ruling. The ruling quoted the
number my artifact gave it.

## 2. A2 was still built and scored, so the withdrawal is measured

A2(τ) is A1 plus one per-team-game per-draw latent `u ~ N(0, τ)` on the
designed-QB share, independent of budget and dropbacks, normalised across the
six categories exactly as A1 normalises. **τ = 0 reproduces A1 draw for draw** —
verified exactly on 200 team-games × 400 draws × 6 categories, 0 differences —
so the grid contains its own null and "A2 does not help" and "A1 is A2 at τ = 0"
are one statement rather than two.

**Dependence agreement, |model − observed|. Lower is better. τ = 0 is A1.**

| τ | POOLED | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| **0 (=A1)** | **0.0075** | 0.0303 | **0.0212** | 0.0293 |
| 0.0025 | 0.0079 | **0.0296** | 0.0228 | 0.0292 |
| 0.005 | 0.0081 | 0.0300 | 0.0230 | 0.0292 |
| 0.01 | 0.0084 | 0.0304 | 0.0229 | 0.0287 |
| 0.02 | 0.0092 | 0.0307 | 0.0232 | 0.0266 |
| 0.04 | 0.0136 | 0.0345 | 0.0274 | **0.0214** |

Pooled, the criterion is **monotonically worst as τ grows and optimised at
τ = 0**. Per fold the best τ is 0.0025, 0, and 0.04 — three different answers,
no consistent sign. Decision rule 1 requires the same sign in every fold; rule 2
says a single-fold improvement is not an improvement; rule 3 says an optimum at
τ = 0 is a rejection. All three fire.

**Reported against my own interest:** designed-QB CRPS *is* consistently
slightly better at τ = 0.01, in all four folds — 1.00826 → 1.00598 pooled,
1.06127 → 1.05888, 0.99615 → 0.99232, 0.96756 → 0.96693. That is a 0.23% pooled
gain with the same sign everywhere, and it is the one thing in this experiment
that favours the latent. It does not meet the pre-registered rule, which
requires a dependence improvement **and** no CRPS worsening; dependence does not
improve at any τ, so the conjunction fails and rule 4 resolves equivalence to
the simpler arm. I am recording it rather than omitting it because a 0.23% CRPS
gain is exactly the size of thing that gets quietly dropped from a rejection.

**Hard gates, every arm, 652,000 draws each:** closure violations **0**,
negative allocations **0**, category budget overruns **0**, degenerate draws
**0**, every carry exactly one owner, kneels explicit, production files changed
**0**, 2026 outcomes consumed **none**.

## 3. What the corrected metric does expose — and it is not designed QB rush

Making the statistic comparable moved several categories out of agreement and
one category badly so. **These are A1's real residual defects and none of them
was visible under the mean-based metric**, which reported everything as
uniformly over-coupled.

**Kneels. This is the finding.**

| statistic | observed | A1 per draw | 90% band | z |
|---|---|---|---|---|
| kneel vs team carries | **+0.3009** | +0.1688 | [+0.1302, +0.2040] | **+6.10** |
| kneel vs dropbacks | **−0.2430** | −0.0653 | [−0.1025, −0.0277] | **−7.49** |
| kneel vs RB (cross-category) | **+0.1733** | −0.0116 | [−0.0553, +0.0326] | outside |
| kneel SD | **1.0433** | 1.3329 | [1.2470, 1.4341] | outside, 1.28× |

Fails in all three folds with the same sign. A1 **under**-couples kneels and
**over**-disperses them. The mechanism is not subtle and does not need a search:
a kneel is a game-state play — a team kneels because it is winning late — and a
team winning late also runs the ball more. A1 draws kneels as an exchangeable
share of the budget, which has no channel for that.

**Small-share categories are over-dispersed, and one mechanism explains it.**

| category | observed SD | A1 SD | ratio | share floor binds |
|---|---|---|---|---|
| RB | 6.7517 | 6.8343 | 1.01 | **0.07%** |
| designed QB | 2.7751 | 2.6495 | 0.95 | 19.45% |
| WR | 1.5627 | 1.8606 | 1.19 | 23.36% |
| TE | 0.2179 | 0.3809 | **1.75** | 24.73% |
| kneel | 1.0433 | 1.3329 | 1.28 | 27.05% |
| fringe | 0.5292 | 0.6278 | 1.19 | 29.40% |

The right-hand column is the diagnosis. A1's additive share residual is
resampled from a **league-wide pool for the category**, so a team whose centre
is near zero receives residuals sized for teams whose share is large. The result
goes negative and the `max(·, 0)` floor catches it — **808,823 times out of
3,912,000 share draws, 20.68%**. For RB, whose centre is ~0.80, it happens
0.07% of the time. The floor cannot move a carry, only a probability, so it
breaks no gate; but a residual family that needs a floor one time in five is
mis-specified for every category except the large one.

That single mechanism plausibly generates the over-dispersion, the zero-mass
errors (designed QB 0.398 against 0.367, kneel 0.597 against 0.551, WR 0.538
against 0.497, and TE too *low* at 0.939 against 0.954), and the p99 tails
(TE 1.97 against 1.00, kneel 5.67 against 4.00, fringe 3.11 against 2.00).
It is a hypothesis with an obvious test, not an established cause.

**What A1 gets right, unchanged:** RB vs carries +0.8502 observed against
+0.8472 [+0.8341, +0.8586]; RB vs dropbacks −0.3843 against −0.3939; WR, TE and
fringe vs dropbacks; designed QB vs both budgets; designed QB vs RB and vs WR
cross-category; RB dispersion; RB and designed-QB p95/p99. Closure remains
exact in all 652,000 draws.

## 4. Repairs made to the record

`nfl/research/own9/run_own9.py` now computes co-movement **per draw** and
reports the distribution over draws. The mean-based figure is retained under a
key named `..._MEAN_BASED_NOT_COMPARABLE` so the old number stays auditable and
cannot be lifted as a measurement. `own9_results.json` re-recorded from the
corrected code. The wrong comment is replaced by one stating what the defect
was.

`nfl/tests/test_own10_dependence_metric.py`: the predeclaration hash, the
runner's pin, an **AST**-based guard that OWN-9 exposes a per-draw helper (a
substring guard here would match the comment explaining the defect — that
failure mode already happened once in this project), a schema guard that every
co-movement key compared against reality is per-draw or explicitly named
non-comparable, a **bypass test** that seeds the defect and requires the guard
to reject it, exact τ = 0 ≡ A1 reproduction, closure/negativity/overrun at
every τ, the τ grid pinned to the predeclared one, and a guard that +0.507 may
not appear unqualified.

## 5. What I did not do

I did not fit a kneel game-state model, a multiplicative or logit-scale residual
family, or anything else arising from §3. Those touch P4C's estimator family,
which is production, and this project pre-registers before fitting. They are
offered as the successor candidates, not started.

**The OWN-9 verdict survives the correction, and I re-ran it to check rather
than assume.** A1 beat A0 on CRPS in every category and on per-draw closure
(0 against 535,354 violations); neither depended on the mean-based statistic.
The sign result also survives — A0 is still backwards on both budgets — but its
**magnitudes were overstated and are corrected here**:

| designed QB rush vs | observed | A0 per draw [90%] | A1 per draw [90%] |
|---|---|---|---|
| team carries | **+0.3140** | **−0.1235** [−0.1612, −0.0835] | **+0.3065** [+0.2768, +0.3388] |
| dropbacks | **−0.1521** | **+0.2918** [+0.2540, +0.3289] | **−0.1603** [−0.1920, −0.1285] |

A0's headline figures in the OWN-9 return — −0.4115 and +0.9724 — were the same
mean-based artifact and are withdrawn with A1's +0.5070. A0 is wrong-signed on
both budgets either way, so the conclusion is unchanged and the evidence for it
is weaker than reported. What the correction removes is the caveat that A1
*overshot the magnitude*: it did not.

## 6. Limits

Budgets are oracled identically across arms, so this tests the allocation
architecture and not a whole-forecast gain. The across-draw bands hold budgets,
fitted parameters and schedule fixed; they are **not** sampling intervals for
the underlying dependence and must not be quoted as such. Development evidence
rejects; it never promotes. 2020–2021 are burn-in and were never scored.
