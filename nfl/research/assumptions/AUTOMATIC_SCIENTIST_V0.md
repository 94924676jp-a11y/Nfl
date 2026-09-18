# Automatic Scientist v0 — one assumption, end to end

**Scope is deliberately one vertical slice.** There is no source-code
assumption scanner and none is wanted yet. What had to be proved first is that
a single assumption can be **identified, measured, falsified, classified and
governed** without a human deciding at each step what the answer should be.

`A1_APPEARANCE_CERTAINTY` is that one, and it came out **false**.

## The six steps, and the one that is missing on purpose

| step | what ran |
|---|---|
| identify | `registry.A1`, falsifier written **before** any test |
| audit | `audit_appearance.audit` over CS2's live 2026 week-2 output |
| measure | `cohort_appearance_certainty.measure` on 2022–2025 |
| falsify | the falsifier applied **as written**, both limbs recorded separately |
| classify | `assumption.settle`, legal edge only, evidence required |
| govern | `assert_promotable`, wired into `adjustment_registry.assert_may_apply` |

**There is no step that changes a probability.** The audit reports, the
measurement measures, the registry blocks. CS2's output is byte-identical
before and after the whole pipeline runs, and `test_F` asserts that by hashing
it either side.

## What the model asserts

`audit_appearance` over CS2's carries room for 2026 week 2, at the sealed
board's 8,000 draws:

**90 of 196 rows assert certainty** — 13 at exactly 1.0, 77 at exactly 0.0, 0
inside the near-boundary band.

The near-boundary band is **`1 / n_draws` = 1.25e-4**, derived rather than
chosen: below it the other outcome is expected fewer than once across every
simulated world, so it is invisible to everything downstream. At 80,000 draws
the band tightens to 1.25e-5 and the audit becomes stricter by itself.

## What football says

The cohort **is** the assumption turned into a group of people: every non-QB
with a prior-season appearance rate of 1.0 who has taken opportunity in every
week so far, whose club plays the next week.

| season | appeared / cohort weeks |
|---|---|
| 2022 | 329 / 348 |
| 2023 | 471 / 502 |
| 2024 | 347 / 379 |
| 2025 | 438 / 473 |
| **pooled** | **1,585 / 1,702 = 0.9313** |

**95% Wilson [0.9182, 0.9423]. 117 failures.**

The cohort CS2 assigns probability **1.0** appears **93.1%** of the time.
Roughly one week in fourteen, the man the model says cannot miss, misses.

Wilson rather than normal on purpose: at `k == n` a normal interval is
`[1, 1]`, which would make a perfect run look like proof.

## The falsifier, applied as written

> the cohort appearance rate is below 1.0 by more than Monte Carlo
> resolution — concretely, the upper bound of the 95% Wilson interval is
> below 1.0, or any member of the cohort is observed not appearing. Either
> alone falsifies it.

Both limbs fired and both are recorded separately. `A1` moved
`DECLARED → FALSIFIED` on a legal edge with the evidence attached, and the
settlement did not touch the falsifier text.

## What is now blocked, and what is not

| consumer | verdict |
|---|---|
| `CS2_STAGE2_PRODUCTION_ALLOCATION` | **BLOCKED** |
| `nfl.production.nonqb.cs2_state` | **BLOCKED** |
| `nfl.production.nonqb.cs2_state.state` | **BLOCKED** |
| everything else in the registry | not blocked |

The block reaches the **real** production path:
`adjustment_registry.assert_may_apply` consults the gate before it checks
ownership, so a falsified critical assumption stops an adjustment on the same
code path every other governance rule uses. It is not a parallel gate.

**Research purpose is not gated.** CS2 stays fully usable as research — its
forward-chain result stands, its numbers stay quotable as what they are. What
is refused is promotion.

## Declaration and measurement are kept apart

The registry **declares** — claim, estimand, falsifier, criticality,
dependencies — and those live in code, immutable and reviewable in a diff. A
**status is a measurement result**, so it lives in `ASSUMPTION_AUDIT.json` and
is overlaid at read time.

An overlay is applied only along a legal transition edge and only with
evidence. `test_I` forges an artifact claiming `SUPPORTED` with no evidence,
and another claiming a status off the transition graph; both are ignored and
the declaration stands. A corrupt artifact cannot promote anything.

## No clipping value was produced, anywhere

The audit does not floor. The measurement returns a rate and an interval, not
a replacement number. **93.1% is not a floor** — it is the rate for one
cohort, and what floor should follow, whether it should vary with prior-season
games played, and whether the Beta prior should be replaced outright are
modelling decisions with numbers in them. They belong in a preregistration,
written before the fit that uses them.

## The next four, seeded and DECLARED

Each carries a falsifier written now, before any test:

| id | criticality | what it would break |
|---|---|---|
| `A2_PROPORTIONAL_REDISTRIBUTION` | CRITICAL | `rushing_a1`, `shared_pass`, CS2 allocation |
| `A3_ROLE_CONTINUITY_ACROSS_REGIME_CHANGE` | MATERIAL | `role_prior`, CS2, OAS1 baselines |
| `A4_STATIC_TEAM_VOLUME_SUFFICIENCY` | CRITICAL | `layers`, `TEAM_VOLUME_V2`, shared game environment |
| `A5_TD_CONVERSION_PORTABILITY` | MATERIAL | `rushing_conversion`, `statline`, anytime-TD props |

**A4 is half-measured and deliberately left DECLARED.**
`GAME_OFFENSE_COUPLING` already answered its first limb — historical coupling
indistinguishable from zero, simulated −0.131. Its second limb is the live
one: the sealed board emits no score, so a score-state dependence cannot even
be expressed, let alone measured. Settling on half an estimand is exactly the
failure this registry exists to stop, so it stays open.

A3 is worth reading next to CS2 amendment B1, which declared the shrinkage
target to be the player's own prior-season share. That choice is only as good
as A3, and the two must be tested together rather than one justifying the
other.

**V2 NOT YET EARNED**
