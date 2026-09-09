# XL1 pre-registration — cross-layer passing ↔ receiving

**Written and committed before any candidate is fitted or scored.** Its sha256
is recorded in the commit that adds it and is re-checked by `run_xl1.py`, which
refuses to run against a modified file.

**Authority.** Owner packet NFL-INTEL-1: *"For that cross-layer problem, do not
simply force equality after independently generating QB and receiver outcomes.
Determine the correct causal ownership of the shared passing event … Preregister
any research comparison before fitting/scoring if the solution requires a model
choice rather than a pure identity-preserving engineering correction."*

It requires a model choice. §3 says exactly which, and why the choice could not
be avoided.

---

## 1. The defect, as measured — and it is not the defect it was reported as

`nfl/research/xl1/diagnose_xl1.py`, 2026 week 1 rehearsal slate, A3 enabled,
TEST_ONLY. Historical column is `history_levels.json`: REG 2020–2025, **3,230
team-games**.

| link | receiving side | QB side | history | mean abs diff per draw | corr |
|---|---|---|---|---|---|
| team completions | 19.59 | 20.59 | **21.71** | 5.42 | 0.494 |
| team passing yards | 220.21 | 231.49 | **237.88** | 85.45 | 0.321 |
| team passing TD | 1.371 | 1.522 | **1.497** | 1.516 | 0.069 |
| targeted throws | 29.57 (D1) | 31.86 (QB att) | **32.13** targets / **33.55** throws | 2.29 | — |

**Both sides are approximately level-calibrated. Neither is the wrong one.**
The largest level error is the receiving side's completions at −9.8% of the
historical mean; the QB side's passing yards is −2.7%. An earlier reading of
this defect as "the two disagree by ~45% of the quantity" was reading a
**per-draw absolute difference** as a level error. It is not one.

The disagreement is almost exactly what two independent draws of one quantity
would produce. For independent X, Y, `E|X−Y| = sqrt(2/π)·sqrt(σx²+σy²)`:

| link | σ receiving | σ QB | E&#124;d&#124; if independent | E&#124;d&#124; observed |
|---|---|---|---|---|
| completions | 5.96 | 7.20 | 7.46 | **5.42** |
| passing yards | 80.79 | 102.16 | 103.92 | **85.45** |
| passing TD | 1.22 | 2.23 | 2.03 | **1.52** |

Observed sits below the independence prediction by exactly the amount the
measured correlations imply — those correlations exist because both layers
descend from D1's team volume, and A3 couples D1's metrics. **This is a pure
dependence defect.** The identity that must hold is exact, and it holds in the
simulator in **0 of 1,600 draws** for completions and for passing yards.

The identity it must hold to, measured on the same 3,230 team-games:

| identity | exact | mean abs diff |
|---|---|---|
| team completions == team receptions | **3,230 / 3,230** | 0 |
| team passing TD == team receiving TD | **3,230 / 3,230** | 0 |
| team passing yards == team receiving yards | 3,154 / 3,230 (97.65%) | 0.26 yd |
| passing yards == receiving yards **+ lateral receiving yards** | 3,214 / 3,230 (99.50%) | 0.033 yd, max 20 |

The 16 team-games that do not close after laterals are a **source
discrepancy**, reported and never absorbed into a residual. Our generator emits
no laterals and no fumble advances, so its construction target is the **exact**
identity in every draw.

**Consequence for the design, and it is the load-bearing consequence.** A
candidate that repairs the identity by moving one side's level onto the other's
trades a dependence defect for a level defect. Both must be scored. This is why
§5 scores levels as well as identities.

---

## 2. Correct causal ownership of the shared event

A dropback resolves into exactly one of **sack**, **scramble**, or **throw**.
The QB layer already owns that partition and already draws it as a chained
multinomial that closes exactly.

A **throw** resolves into: an untargeted throw (throwaway, spike — no intended
receiver), or a throw at an intended receiver which is **incomplete**,
**intercepted**, or **complete**.

A **completion** is one event. It generates, simultaneously and from one draw:

- +1 completion for the passer and +1 reception for the catcher — the same event
- one **yardage gain**, credited in full to both passer and catcher
- optionally one **touchdown**, credited to both

Neither the QB layer nor the receiving layer owns this event. The **throw budget**
is the passer's (it is his action). The **assignment** of a targeted throw to a
receiver is the receiving competition's. The **gain** is a property of the
completion. That is the ownership the architecture must express.

Measured decomposition of the historical throw budget, per team-game: **33.55
throws**, of which **32.13 targeted** and **1.42 untargeted**. Pass attempts as
nflverse reports them are ~35.9 because `pass_attempt` includes sacks (W2 §3.1),
so the identity must use **targeted throws**, never attempts. This is the
constraint NFL-INTEL-1 named and it is now quantified.

---

## 3. Candidates, and the model choices each forces

**B0 — baseline.** The current engine. Declared and unchanged.

**C1 — receiver-owned derivation.** The receiving layer is untouched: RC1's
catch rate, RC1's per-catch resampled yardage and TD2's rate all produce
byte-identical draws to B0. The QB's `cmp`, `pyds`, `ptd` are discarded and
replaced by the team sum over its receivers.

*The model choice C1 cannot avoid:* the derived quantity is a **team** total and
the QB layer emits **per-QB** lines. Splitting it requires an allocation, and the
only specified one is QB3's dropback share — an existing, unpromoted candidate.
So C1 is not a pure engineering correction either. It also makes a QB's passing
yards a function of his receivers alone, with no QB contribution, which is
football-wrong even where it is arithmetically coherent.

*Guards:* `att ≥ cmp` per draw, refused by name, never clipped.

**C3 — event-owned construction. This is the architecture the ownership analysis
in §2 implies.** Per team, per draw:

1. throws := the QB layer's `att`, already a closed multinomial component of DB
2. throws split into **targeted** and **untargeted**; the untargeted pool is a
   **named quantity**, never a residual
3. each targeted throw is assigned to a receiver by the **existing target
   simplex** — receiver competition preserved exactly, now on a coherent
   denominator
4. each targeted throw resolves `{complete, incomplete, intercepted}` — a
   multinomial mirroring the dropback one, one level down
5. each completion draws its gain from the **catching receiver's RC1 per-catch
   pool**, unchanged
6. each completion is a touchdown at that receiver's **TD2 rate**, unchanged

Then, by construction and with no clipping anywhere:
`team completions == Σ receptions == Σ QB cmp`,
`team passing yards == Σ receiving yards == Σ QB pyds`,
`team passing TD == Σ receiving TD == Σ QB ptd`,
and `targeted throws ≤ throws ≤ dropbacks`.
Each completion belongs to a specific passer, so the per-QB credit is coherent
without an allocation — the thing C1 must approximate.

*The model choices C3 forces, declared:*
- **the untargeted-throw rate.** Estimated from history (2020–2025, mean 1.42
  per team-game) with source and n stated in the artifact. **If it cannot be
  estimated it is refused, not assumed.** No fitted constant.
- **the throw-terminal multinomial.** Completion probability is the catching
  receiver's RC1 shrunk rate — so C3 **nests** C1's catch model rather than
  introducing a new one. Interception rate comes from the QB's existing `int`
  rate, re-expressed per targeted throw. No new estimator is fitted.
- **whose catch rate.** Receiver-only, matching RC1. A QB×receiver combination
  is NOT tried here; it is named as out of scope so that a later study can test
  it against this as a control.

**C2 — QB-owned allocation.** The QB retains `cmp`/`pyds`/`ptd`; receiver
quantities are allocated to sum to them. This requires a **compositional
yardage-allocation model that does not exist**, and any naive normalisation
would flatten the per-catch tail RC1 exists to preserve — measured skew 2.197,
excess kurtosis 7.830, `P(gain>40)` 0.0203 empirical against 0.0016 Gaussian.
Declared as the last resort and not built unless both C1 and C3 fail.

### Simplest-wins ordering, declared now

**C1 < C3 < C2** on structural simplicity. C1 is run **first, as a control C3
must match or beat on §5**, not because it is expected to win: §2 and the
per-QB-credit problem say C3 is the correct construction. Declaring the order in
advance is what stops the winner being chosen after the numbers arrive.

---

## 4. Prohibitions

Binding on every candidate. A violation rejects the candidate outright.

1. **No forcing equality after independent generation.** Reconciliation comes
   from construction. No clipping, no renormalising a drawn vector onto a
   target, no post-hoc overwriting of either layer's output.
2. **No point estimate where a distribution belongs.** This defect class has been
   found five times in this project. RC1's per-catch resampling must survive
   intact and is checked, not assumed.
3. **No silent constants.** Every rate is estimated from named data with its n,
   or refused by name.
4. **Receiver competition is preserved.** The target simplex and its closure are
   unchanged; a candidate may change the denominator it applies to, never the
   competition itself.
5. **No 2026 outcomes.** None exist and none may be used.
6. **No market, sportsbook, DFS or restricted-vendor input.**
7. **PATH_C_STATE.json is not edited. G0A stays 11/12. NFL-1 stays NOT
   AUTHORIZED. A3 and QB3 stay unpromoted.** Nothing here is promoted.
8. **Every existing guard keeps its input.** A candidate that makes a guard
   unreachable is rejected. Three dormant guards have already been found in this
   project; a fourth will not be created here.

---

## 5. What is scored, and what is deliberately not

There are **no 2026 outcomes**, so **there is no confirmatory forecast
comparison in this study and none will be claimed.** Saying which architecture
forecasts better needs outcomes and an untouched holdout, and this study has
neither. What can be established is whether the identity holds by construction
and what it cost.

### Gate 1 — structural. Deterministic, decisive, no scoring involved.

Full 2026 week-1 rehearsal slate, A3 enabled, TEST_ONLY, 400 draws.

- all three identities **exact in 100% of draws**
- **zero** clipping events; every refusal named and reachable
- `reconcile_nonqb`, `reconcile_team_volume`, `reconcile_cross_layer` all PASS
- `assert_publishable` still refuses a TEST_ONLY run
- R2 per-slate cache equivalence preserved
- the full suite passes with no test weakened

**A candidate failing any Gate 1 item is rejected. No appeal on Gate 2.**

### Gate 2 — marginal displacement, against margins fixed now

Compared against B0 and against the historical team-game means in §1.

*Team level* — completions, passing yards, passing TD, mean and SD.
**Flag if a candidate's mean is further from the historical mean than B0's is,
by more than 5% of the historical mean.**

*Player level* — every receiver's targets, receptions, receiving yards,
receiving TD; every QB's completions, passing yards, passing TD. Mean, p50, p95.
**Flag if a mean or a p95 moves more than 10% relative to B0.**

*Rationale for 5% and 10%, stated before the candidates run.* B0's own team-level
distance from history is 2.7%–9.8% depending on which side is read (§1). A margin
at 5% is therefore the scale of the discrepancy already present: a candidate that
moves a level by more than that is doing something material rather than
incidental. 10% at player level because player marginals at 400 draws are
noisier than team aggregates. These are declared thresholds with a stated
rationale, not fitted values, and they are not adjusted after results.

**Flags do not auto-reject.** They are reported alongside the identity gain and
adjudicated in the return. A candidate that restores three exact identities while
moving a team mean 6% has made a trade, and the trade is the finding — it is not
hidden and it is not automatically accepted either.

### Reported regardless of outcome

- every identity violation count, before and after
- every refusal raised, by name
- the untargeted-throw pool as a named quantity with its historical anchor
- what each candidate cost in every player and QB marginal
- anything that disagrees with this pre-registration

---

## 6. What this study cannot conclude

- That any candidate **forecasts** better. No outcomes, no holdout.
- That C3 is **correct**. It is coherent, which is a different and weaker claim.
- Anything about 2026 performance.
- Anything that would justify promotion. Nothing here promotes.

## 7. Order of execution

1. Commit this file. Record its sha256.
2. Build C1. Gate 1, then Gate 2.
3. Build C3. Gate 1, then Gate 2.
4. C2 only if both fail Gate 1.
5. Report, including every result that disagrees with what is written above.
