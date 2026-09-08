# ROUTE-BB1 ADDENDUM — three defects in my own first run, named before the repair

Written **before** the corrected run. Pre-registration
`8d7383bf7f2a7a909f501d9395abf365becb05cdd9d3f243287aa3daa0bc5512` unchanged.
The FTN sample remains sealed and unread.

## What fired

The pre-registration's §3 predicted that a position-constant route rate would
**cancel exactly**, giving ΔCRPS = 0. The first run gave −0.0599 CRPS
[−0.0812, −0.0362] — a large, clearly significant "improvement" from a
denominator carrying **no information whatsoever**.

That is a placebo returning a result, which is the signature of a defect rather
than a discovery. It is the same shape as the information-gap probe earlier in
this project, where +8.81% turned out to be an artifact and pure Gaussian noise
scored +9.01%. I did not report the number; I went looking for the cause.

## Defect 1 — ZERO DISPERSION. The draws were point masses.

    def _draw(n_trials, rate, m, rng):
        n = np.maximum(np.rint(n_trials), 0).astype(int)
        return rng.binomial(n, np.clip(rate, 0.0, 1.0))    # no size=m

`n_trials` is a scalar inside the row loop, so `rng.binomial` returned a
**scalar**, which numpy then broadcast across all 400 draw columns. Every row
was a point mass.

Measured: mean per-row draw SD **0.000**, and reported CRPS equalled reported
MAE to four decimals in every arm (1.648156 vs 1.6482) — the tell, because the
CRPS of a point mass is exactly `|point − y|`.

So nothing in that run was a distribution, the coverage numbers would have been
meaningless, and the whole comparison was of point predictions wearing a CRPS
label.

**This is the third time in this project that a distribution has been replaced
by a point.** R1 did it by substituting a point estimate for a draw; QB2 did it
by rounding `DB × rate`; this does it by dropping `size=`. Recording that
pattern here because the recurrence is more informative than the instance.

## Defect 2 — the shrinkage prior was not in the denominator's units.

    rate = w * (h_targets / hist_den) + (1 - w) * pool,   pool = 0.16

`pool` is a rate **per unit of denominator**. In the control arm that unit is a
pass snap; in the route arms it is a route. Those are different units, so the
constant does not mean the same thing in the two arms and the level does **not**
cancel even when it algebraically should.

Measured consequence at CV = 0: mean point predictions differed by **1.52
targets** per player-game between arms that are supposed to be identical.

The algebra is only exact when the prior is expressed in the same units:

    control  mean = ps × [w·(T/S)      + (1−w)·q]
    oracle   mean = ps·p × [w·(T/(S·p)) + (1−w)·q/p]   =  control mean

## Defect 3 — the necessity curve measured the wrong thing.

§5 declared a sweep over the **game-to-game dispersion** of an injected route
rate. The injected rate is fictional and has **no causal connection to the
observed targets**, which are real. So increasing its dispersion adds pure
noise to the denominator and the oracle arm degrades — which is exactly what
the first run showed (oracle − control ran from −0.060 at CV = 0 to **+0.084**
at CV = 0.40, the oracle getting *worse* the more it "knew").

A design in which more oracle information makes the forecast worse is not
measuring the value of information. The sweep answers "what happens if I
corrupt the denominator", not "what would route knowledge be worth".

## The repairs, stated before the numbers move

1. `size=m` on the binomial draw. Dispersion restored, and the corrected run
   asserts per-row SD > 0 and that CRPS ≠ MAE, so this defect cannot recur
   silently.
2. The shrinkage prior is expressed in the denominator's own units, so the
   level cancels exactly. The corrected run **asserts** the CV = 0 equivalence
   numerically rather than predicting it.
3. **The necessity curve is redesigned to sweep the decision-relevant
   quantity.** Instead of injecting dispersion, it asks:

   > if perfect route knowledge explained a fraction **ρ** of the control
   > architecture's residual error, what would that be worth in target CRPS?

   with ρ swept over a predeclared grid. This is the quantity a purchase
   decision needs, and it can be computed without route labels — which matters
   because no source available to this project has any.

   It also carries its own binding sanity check: recovering ρ of the residual
   implies a route count, and that count must satisfy `routes ≤ pass_snaps`.
   Where it cannot, route information **cannot** explain that much error, by
   construction — an upper bound on FTN's value that comes from football
   accounting rather than from modelling.

## What this invalidates

Every number in the first run is superseded and none is quoted as a result.
The §3 claim as originally written — "cancels exactly" — was correct about the
**mean** and silent about the **dispersion**; the corrected run tests both
separately.

## Constraints unchanged

FTN sample sealed and unread. G0A remains 11/12. NFL-1 remains NOT AUTHORIZED.
Nothing promoted. No production model touched.
