# AI1 review: the ordering constraint as written was too strong

**Status: AI1 v1 is AMENDED, not withdrawn. Nothing is implemented.**
The original `predeclaration_ai1.md` is preserved unchanged as the record of
what was first proposed.

## The objection, and it is correct

AI1 v1 declared:

> Assert that zero-opportunity probability is **non-increasing** in that rank:
> a higher-ranked player may not be absent more often than a lower-ranked one
> in the same room.

**As a permanent invariant that is false football.** A legitimate specialist
role violates it by design:

- a short-yardage or goal-line back who plays a handful of snaps and dominates
  them;
- a blocking tight end who is TE1 on the depth chart and runs few routes;
- a designated returner or gadget player with real but narrow usage;
- a veteran on a snap count returning from injury.

Each is a **low appearance probability with a high conditional share**, which
is exactly the shape CS2's decomposition exists to represent. A rule that
forbade it would replace one modelling error with another, and would do so
permanently rather than for the one fixture where the defect was measured.

The original wording also made the constraint a property of *rank*, when the
evidence it was built on was a property of *unsupported inversion*. Those are
not the same claim.

## The amendment

AI1 does not assert an ordering. It asserts that an inversion must be
**SUPPORTED**, and reorders only where it is not.

An inversion between a higher-ranked player A and a lower-ranked player B is
**supported** when at least one of these holds, from evidence lawful before the
forecast clock:

1. **Availability** — A carries a designation, a snap count, or a documented
   limitation that B does not.
2. **Current depth** — the official depth chart does not in fact rank A above
   B at the relevant role, whatever the label suggests.
3. **Prior-week usage** — B out-opportunitied A in the most recent completed
   week.
4. **Role specialisation** — A's historical usage shows a narrow-but-dense
   pattern (low appearance rate, high conditional share) rather than an
   every-down one.

Where an inversion is supported, **it is left alone and the support is
recorded**. Where it is supported by none of the four, it is reordered, and the
artifact names which tests were checked and that all four failed.

Applied to the measured case: Cook carries no designation, is RB1 on the depth
chart, out-carried Davis 13 to 1 in week 1, and has an every-down historical
pattern rather than a specialist one. All four tests fail, so the inversion is
unsupported. **That is a statement about this fixture, not a law.**

## What AI1 is, restated

A **narrow experimental repair**, testing one hypothesis: *does correcting
unsupported starter/backup zero-opportunity inversions materially fix the
observed defect while preserving conditional role?* It is not a permanent
football law, and it does not survive on its own merits if CS2 subsumes it.

## The James Cook regression fixture

These sealed values are **the failing baseline, not promotion targets**:

| Quantity | Sealed value |
|---|---|
| Cook `P(carries = 0)` | **0.375** |
| Davis `P(carries = 0)` | **0.292** |
| Cook carry share, conditional on appearing | **≈ 0.692** |
| Cook receiving `P(= 0)` | **≈ 0.558** |
| Share of that zero mass from zero targets | **93.8%** |

They are preserved as regression evidence of the defect mechanism. **Any
successor must explain what changed through football evidence** — depth,
availability, prior-week usage, specialisation — **and not by matching a
sportsbook line.** A successor that moved these numbers toward the market
without a football account of why would fail this fixture, not pass it.

## Is AI1 still the smallest justified experiment, now that CS2 is defined?

**Partly, and its scope is narrower than it was.**

CS2 subsumes AI1's *purpose*: a layer that estimates `P(eligible)`,
`P(appears | eligible)` and `share | appears` separately would not have
produced an unsupported inversion, because the appearance term would be
estimated from prior-week opportunity rather than inherited from a role
parameter. If CS2 is built, AI1 is redundant.

But CS2 is a **capture-and-build project** — it needs a non-QB current-season
panel, and two of its natural inputs do not exist in-season at all
(`snap_counts` is 404 for 2026 and WATCH_ONLY; route data arrives after the
postseason). It will not be ready soon.

So the honest position:

- **AI1 remains justified as a diagnostic experiment**, because it tests
  whether the inversion is the dominant mechanism. That answer is needed
  *before* CS2 is built, since it tells CS2 whether appearance or conditional
  share is the thing to get right first.
- **AI1 is no longer justified as a shipping repair.** A monotonicity-style
  patch on an appearance model's output is treating a symptom, and the
  diagnostic's own falsification clause already says so: if the constraint
  fires on many rooms across many fixtures, the appearance model has a general
  ordering problem and the patch is the wrong fix.
- **Its acceptance gates are unchanged**, including "DET must be
  byte-identical" and "Cook's conditional share must not move by more than
  0.02".

Recommendation: run AI1 as a measurement, read what it says about how much of
the defect the inversion accounts for, and let that result size CS2. Do not
ship AI1.

**MARKET IS DIAGNOSTIC EVIDENCE ONLY, NOT A TARGET**

**V2 NOT YET EARNED**
