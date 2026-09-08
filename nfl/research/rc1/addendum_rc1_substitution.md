# Addendum — the pre-registration contradicts itself on substitution

Written 2026-09-08, **after writing the simulator and before running it**. No
evaluation result has been computed or inspected. Pre-registration sha256
`34f8ac10be7bc0c5b39ee0e89340a3061ff0910dca803d4975887b8811c02cdd`.

## The contradiction

The pre-registration says two things that cannot both hold.

§5, on the oracle arms:

> | E | A + B + C (**mechanical identity check — must reproduce `Y` exactly**) |

§5, immediately below, on substitution:

> **Substitution is draw-preserving.** A component's draws are replaced by a
> distribution centred on the oracle value with the arm's own dispersion
> retained where dispersion exists.

If arm E retains dispersion on all three components, it cannot reproduce `Y`
exactly — it produces a distribution around `Y`. The identity check, which is
the one arm whose correct answer is known in advance and which therefore detects
implementation defects in every other arm, would be unable to pass.

## Why this happened

I imported R1's lesson into the wrong place. R1's finding was about substituting
a **candidate model's estimate** as a point value: that destroyed dispersion of
CV 0.914 and accounted for +0.0542 of an apparent +0.0100 of harm, so the
substitution machinery was blamed on the candidate. That lesson is real and it
governs the **composition test** in §8.

It does not govern an oracle. An oracle is the realised truth; "perfect target
count" means the count, not a distribution over counts. Collapsing dispersion is
the definition of the arm, not a defect in it.

## The resolution, fixed before any result

The pre-registration is **not edited** — §11 forbids editing the specification
to match an outcome, and that has to hold when the outcome is my own
inconvenience. The sentence is instead **split into the two rules it conflated**,
and the stronger, checkable constraint governs:

- **ORACLE substitution collapses to the realised value.** `T := T_actual`,
  `C := R_actual / T_actual`, `V := Y_actual / R_actual`. Arm E then reproduces
  `Y` exactly, and that exactness is asserted by test rather than assumed.
- **CANDIDATE substitution preserves dispersion**, per R1. In the §8
  composition test a candidate replaces a component's *estimate* while the draw
  structure around it is retained. Asserted by a separate test that a point
  substitution is detected and refused.

Both rules are implemented in `rc1_sim.simulate` and each has its own test. The
distinction is now stated in the module docstring so a later reader cannot
collapse them again.

## What this does not change

Nothing else. Seasons, positions, frame, minimum history, chronology rule,
primitive definitions, the ladder, the metrics, the bootstrap, the subgroups and
the seed are all unchanged, and no result had been seen when this was written.

This addendum is a **specification defect found and recorded**, not a threshold
moved. It is reported in the return under its own heading.
