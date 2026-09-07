# Briefing for an agent working on the NFL repository

## Reporting convention — owner instruction, 2026-09-07

**Always produce a markdown file when a task is finished, and send it.** Not a
chat summary — a file, committed to this repository. The owner audits the
repository directly, so a report that exists only in a conversation is a report
that cannot be checked later.

Shape it as: what was asked, what was done, what was measured (with the command
or the artifact), what was corrected, what is still open, and what needs the
owner. Name the commit. If a claim is not measured, label it.

## What this project is

A research-grade NFL prediction system, built as a greenfield sibling product on
a shared scientific platform — not a fork of the MLB engine with football nouns
substituted. The MLB system lives at `94924676jp-a11y/mlb-prop-system-v7` and its
NFL tree was retired on 2026-09-07; this repository is canonical.

**Status: NFL-0 (evidence system). No predictive model exists. NFL-1 is not
authorised.** Do not build one until the owner says so.

## The governing rules

1. **The goal is not to make the checklist green. The goal is to make a false
   green state difficult to produce.** If the honest result is 11/12, return
   11/12.
2. **No silent constants.** Any coefficient needs empirical estimation, a
   published source, an explicit derivation, or a documented prior.
3. **Zeros and empties are errors, not results.** Never report that a step
   succeeded unless it ran and you read the output.
4. **A guard is not demonstrated because compliant data passes it.** It must
   reject a seeded violation, and critical guards must fail their replay test
   when the guard is bypassed. Use `nfl/tests/bypass.py`.
5. **Never optimise toward a sportsbook line.** No parlays, ever, including in
   discussion. Never recommend a wager.
6. **Corrections stay visible.** Withdraw a claim in writing rather than editing
   it away. Fourteen of this project's recorded corrections are to its own
   earlier claims, and that history is load-bearing.
7. **`python3.12`**, not `python3`.

## Layout

```
sportsplatform/governance/   Outcome (five states), Provenance (five clocks), Scorecard
nfl/ingest/                  column quarantine, denominator-aware validation, identifiers
nfl/identity/                execution identity, forecast sealing, effective scope
nfl/capture/                 kickoff-anchored scheduler, source registry
nfl/tools/                   vintage capture, source probe
nfl/tests/                   adversarial replay tests
.github/workflows/           the capture executor
returns/                     owner return records
```

The package is `sportsplatform`, **not** `platform`: a top-level `platform/`
shadows the stdlib module of that name.

`sportsplatform/governance` is a copy of the MLB repo's `v8/governance` and
**nothing compares the two.** The source commit is pinned in
`PLATFORM_PROVENANCE.json`. Treat a change to it as a change to the platform.

## Tests

```
python3.12 nfl/tests/test_<name>.py
cd sportsplatform/governance && python3.12 test_outcome.py
```

**911 assertions, 0 failing.** Every control has a positive test, a
seeded-violation test, and where critical a load-bearing test.

## The two results that matter most

**Opportunity is predictable; efficiency mostly is not.** Measured three times
independently. Prior-form prediction of QB passing yards reaches r = 0.136; the
same rate model handed the *realised* dropback count reaches **r = 0.636**.
Nearly all available discrimination sits in a quantity not yet forecast. This is
an EXPERIMENTAL empirical thesis, not an axiom — future evidence may overturn it.

**The SD ratio is not a dial.** At calibration slope 1.0, `slope = r·SD_act/SD_pred`
collapses to `SD_pred/SD_act = r`. Report r, SD ratio and calibration slope
together; they are one fact in three forms.

## What is open

- **G0A item 1** — the executor now exists (GitHub Actions reaches nfl.com and
  has captured it), but point 7 of the twelve-point proof is partial: a captured
  page is file-level and not attributed to a game, because **no parser exists**.
  Do not write one against markup nobody has inspected.
- **`PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE`** — open. May **not** be closed
  with `weekly_rosters.status`, which is post-hoc (INA → 0 snaps of 3,438).
- Six of eight scheduler cadences are `confirmed=False` — inferred, not verified.

## Frozen artifacts — do not revisit

The cold-start specification (`b356ecaa…`) was frozen before any 2026 outcome
existed. Its constants must not change; revising one after the first result
forfeits the fixed-holdout property for the season. Owner rulings T1 (retain the
2002 estimation floor) and T3 (retain the home term) are closed.
