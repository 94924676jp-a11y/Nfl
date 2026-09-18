# Amendment B1 to `predeclaration_cs2.md` — the three open choices, resolved

**Declared before any CS2 stage-2 fit. `predeclaration_cs2.md` is not
rewritten.** This file is additive, exactly as OAS1 amendment A1 is additive
to its preregistration.

Stage 1 shipped as measurement. `stage2_state()` refused with
`PREREGISTRATION_INCOMPLETE` on `half_life`, `min_opportunity` and
`shrinkage_target`. Two of the three turn out not to be choices at all.

## `half_life` — REMOVED for this forecast

Identical to OAS1 A1, and for the identical reason. For the 2026 week-2
forecast the conditioning set is **one** current-season week, so every
observation is zero weeks back and a decay has nothing to act on: all values
produce the same weights.

Re-declared, with its scope stated, before any fit whose conditioning set
carries two or more current-season weeks. The forward chain in `fit_cs2.py`
conditions on up to seventeen weeks and therefore runs **without** a decay at
all, which is a declared simplification of the chain rather than a claim that
decay does not matter.

## `min_opportunity` — REMOVED as a selection axis, RETAINED as a field

The predeclaration's only sentence about it is a reporting rule. Reporting
cannot move an out-of-sample score, so selecting over it would be selecting
over nothing. `n_opportunity` and `n_weeks_with_opportunity` travel on every
row instead, so a reader can see how much evidence is behind a number without
a threshold deciding it for them.

## `shrinkage_target` — DECLARED, because this one is real

Three candidates were open: the room mean, the prior-season share, and the
depth-chart ordering. They give different answers for exactly the rooms the
defect lives in, so this had to be chosen rather than dropped.

**The target is the player's own prior-season share of his room**, with the
room mean used ONLY for a man with no prior-season history, and every such
fallback counted in `n_prior_fallbacks`.

The predeclaration itself rules out the third candidate: *"Depth rank alone
does not determine role. It orders a room; it does not set a share."* And it
names the first: *"Prior-season role history | shrunk prior"*. The room mean
survives only as the uninformative fallback it is.

## What replaces the removed axes

One estimator with two prior strengths, both **fitted out of sample**, which
is what *"a declared, tuned quantity, not a constant"* requires:

```
p_appears        = (kappa_a * a0 + appeared)      / (kappa_a + n_weeks)
share | appears  = (kappa_s * s0 + opportunity)   normalised over the room
```

Posterior means under a Beta prior on appearance and a Dirichlet prior on the
room split. `KAPPA_A_GRID = (0, 1, 2, 4, 8, 16)`,
`KAPPA_S_GRID = (0, 2, 5, 10, 25, 50, 100)`, both declared here and not
widened after seeing a result.

**They are separable, and the selection uses that.** `kappa_s` cannot move an
appearance score and `kappa_a` cannot move an allocation score, so `kappa_a`
is selected on Brier and `kappa_s` on log-loss independently. That is an
algebraic property of the estimator, not a convenience.

## What is NOT imposed

**No depth-rank monotonicity.** `role_invariants` reports an inversion; it
does not repair one, and nothing in CS2 forces RB1 above RB2. A short-yardage
back who plays rarely and dominates his room when he does is a high
conditional share with a low appearance probability, and a monotonicity
shortcut would erase exactly that man.

**The objective is not to raise James Cook.** It is to let current-season
evidence reach the layer at all. Whether it raises him is a measurement.

## Acceptance

Forward-chained on 2022-2025, week 2 to week 18, predicting week W from weeks
1..W-1 of season S plus all of S-1. Scored on **opportunity**, never yards, so
a role change cannot be confounded with an efficiency change. Comparators
declared in advance: `PRIOR_ONLY` (kappa to infinity — the prior season alone,
which is what a non-QB layer without CS2 effectively has) and `UNIFORM` (the
no-information floor).

**2026 is excluded from the chain.** It has one week, which cannot be
forward-chained, and it is the season the state will be applied to.

**A measured negative is a result.** If no arm beats `PRIOR_ONLY` out of
sample, the grid is not widened and stage 2 does not ship.

**V2 NOT YET EARNED**
