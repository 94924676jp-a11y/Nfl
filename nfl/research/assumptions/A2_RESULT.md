# A2 — proportional redistribution does not survive measurement

**`A2_PROPORTIONAL_REDISTRIBUTION` → FALSIFIED.** The proportional allocator
in production is **unchanged**, and nothing here writes a substitution matrix.

## The cohort

A shock is **one** materially involved player (trailing-3-game share ≥ 0.10)
who takes zero opportunity in week W while his club plays. Thresholds declared
before the run: `MIN_SHARE 0.10`, `WINDOW 3`, `MIN_SURVIVORS 2`,
`MIN_VOLUME 8`, `MIN_CELL 25`.

**1,257 single-shock room-weeks over 2022–2025. 368 multi-shock weeks
excluded** — with two men gone the redistribution cannot be attributed to
either, and averaging over them would let a clean rule look wrong because two
shocks interacted.

| room | events |
|---|---:|
| carries | 531 |
| targets | 537 |
| rz_carries | 110 |
| rz_targets | 79 |

**Routes and pass participation are NOT scored.** `pbp_participation` is not
captured in this repository for any season; substituting targets would be a
different quantity wearing the same name. Snap counts exist for 2026 only, and
the cohort is 2022–2025.

## Finding 1 — the work does not stay in the room

| room | mean share to players outside the trailing room | events with any |
|---|---:|---:|
| targets | 6.1% | 60.1% |
| carries | 9.5% | 55.6% |
| rz_carries | 16.0% | 60.0% |
| **rz_targets** | **22.8%** | 75.9% |

The claim says opportunity is "redistributed to the rest of his room".
Between 6% and 23% of it is not. **Proportional assigns those players
probability exactly zero**, so every elevation and every new name is priced at
`−log(1e-6)`.

This is a defect of **room membership**, not of the redistribution rule, and
the two are scored apart for exactly that reason. `NO_TRANSFER` wins the
*total* log score in every room purely by holding mass back for outsiders —
and its **in-room score is identical to `PROPORTIONAL`'s**, because
renormalising survivors' raw shares over survivors *is* the proportional
answer. Reporting one merged number would have answered a question nobody
asked.

## Finding 2 — the transfer is about twice too large on the ground

Regressing realised gain on the gain proportional predicts, across survivors:

| room | slope | intercept |
|---|---:|---:|
| carries | **0.495** | +0.005 |
| rz_carries | **0.522** | −0.014 |
| targets | **−0.161** | +0.013 |
| rz_targets | **−0.262** | +0.003 |

On carries, survivors absorb roughly **half** of what the default predicts,
with essentially no intercept — a clean magnitude error. **On targets the
slope is negative**: the receivers proportional says gain most are, if
anything, the ones who gain least. That is a sign error, not a scaling one.

## Finding 3 — and the falsifier's named mechanism was wrong

The falsifier, written before any of this ran, had two limbs:

> the observed redistribution ratio departs from 1.0 systematically by role —
> **specifically**, if the nearest depth-chart neighbour absorbs materially
> more than his proportional share, with a cluster-robust interval excluding
> proportionality.

**The general limb fires in all four rooms. The specific limb fires in none.**

Excess absorption — realised fraction of the vacated mass minus the fraction
proportional predicts for that man — by share-rank distance from the absent
player, with a **cluster bootstrap over shock events** (2,000 resamples, seed
20260918):

| room | rd = −2 | rd = −1 | **rd = 0** | rd = +1 |
|---|---:|---:|---:|---:|
| carries | **−0.320** | **−0.414** | +0.030 | −0.009 |
| targets | **−0.286** | **−0.189** | **−0.052** | −0.016 |
| rz_carries | **−1.075** | **−0.326** | +0.000 | **−0.180** |
| rz_targets | **−0.828** | **−0.757** | +0.007 | +0.033 |

Bold = cluster-bootstrap interval excludes zero.

**The nearest neighbour absorbs about exactly his proportional share** — not
more. What departs is the *other* end: survivors who were **already larger**
than the absent man absorb far **less** than proportional predicts. The
vacated work spreads **down the room and out of it**, and proportional's error
is concentrated in over-crediting the players who were already big.

That is close to the opposite of the mechanism the falsifier guessed. The
guess is recorded as wrong rather than quietly repaired: a falsification that
rewrites its own reasoning is worth less than the measurement under it.

## Finding 4 — heterogeneity: one global rule is invalid

Cells whose interval excludes proportionality: carries 3 of 7, targets **6 of
7**, rz_carries 3 of 4, rz_targets **5 of 7**. The spread of mean excess runs
from −1.07 to +0.04.

A single global substitution rule cannot be right in three of four rooms, and
the room where it is least wrong — carries — is also the one where its
magnitude error is largest and cleanest.

## Finding 5 — and no learned arm rescues it

In-room log score, forward-chained, `LEARNED` fitted only on strictly earlier
events:

| room | PROPORTIONAL | LEARNED | ROOM_UNIFORM |
|---|---:|---:|---:|
| carries | **1.13016** | 1.13974 | 1.16289 |
| targets | 2.03972 | 2.02838 | **2.02488** |
| rz_carries | **0.85576** | 0.86326 | 0.88400 |
| rz_targets | **1.44076** | 1.44398 | 1.44940 |

`LEARNED` beats the default only on targets, and `ROOM_UNIFORM` — the weak
benchmark — beats them both there. **The objective was never to show a
role-specific model wins, and it does not.** What is established is that the
incumbent is wrong in a measurable, structured way, not that a replacement is
ready.

## What is blocked

| consumer | verdict |
|---|---|
| `nfl.production.nonqb.rushing_a1` | **BLOCKED** |
| `nfl.production.nonqb.shared_pass` | **BLOCKED** |
| `CS2_STAGE2_PRODUCTION_ALLOCATION` | **BLOCKED** |
| `layers`, `role_prior`, `rushing_conversion`, `statline`, OAS1 baselines | not blocked |

Only the substitution path. Research purpose is not gated; the allocator keeps
running and its outputs stay quotable as what they are.

## What was NOT done

No substitution matrix was written. `LEARNED` is fitted per fold and
discarded. No coefficient from this measurement is installed anywhere, and the
successor is a **specification for a model to be fitted**, not a table of
numbers. See `A2_SUCCESSOR_SPEC.md`.

**V2 NOT YET EARNED**
