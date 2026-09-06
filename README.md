# NFL Greenfield Forecasting

A research-grade NFL prediction system, built as a **greenfield sibling product
on a shared scientific platform** — not a fork of the MLB engine with football
nouns substituted.

**Status: NFL-0 (evidence system). No predictive model exists. NFL-1 is not
authorised.** G0A, the pre-kickoff integrity gate, stands at **11 of 12**.

## Layout

```
sportsplatform/governance/   sport-neutral: Outcome, Provenance, Scorecard
nfl/ingest/                  column quarantine, denominator-aware validation, identifiers
nfl/identity/                execution identity, forecast sealing, effective scope
nfl/capture/                 kickoff-anchored scheduler, source registry
nfl/tools/                   vintage capture, source probe
nfl/tests/                   adversarial replay tests
```

The package is `sportsplatform`, not `platform`: a top-level `platform/`
would shadow the Python standard library module of that name, which
`governance/environment.py` imports.

## Tests

```
python3.12 nfl/tests/test_<name>.py          # 811 assertions, 9 files
cd sportsplatform/governance && python3.12 test_outcome.py   # 93 assertions, 3 files
```

**904 assertions, 0 failing.** Every control carries a positive test, a
seeded-violation test, and — for critical guards — a *load-bearing* test proving
the replay test fails when the guard is bypassed. A guard that passes on
compliant data has not been demonstrated.

## The two things worth knowing before reading anything else

**1. Opportunity is predictable; efficiency mostly is not.** Measured three times
independently. Split-half reliability: receiver participation 0.948, target share
0.915, RB carry share 0.926 — against catch rate 0.300, yards per carry 0.385,
TD per target 0.167. The sharpest form: prior-form prediction of QB passing yards
reaches r = 0.136, while the same rate model handed the *realised* dropback count
reaches **r = 0.636**. Nearly all available discrimination sits in a quantity the
system does not yet forecast.

**2. G0A item 1 fails on an external dependency.** The perishable official
cascade — practice participation, final game status, inactives — is not captured.
nfl.com answers HTTP 200 externally and this executor's proxy answers 403 to
`CONNECT`. DNS resolves fine. The source is reachable; the executor is denied.
Every capture run prints its own gap:

```
UNMET CAPTURE TARGETS: ['final_status', 'inactives', 'practice']
```

## Governance

Inherited by reference, not reinvented. Five states (`PASS` / `FAIL` /
`BLOCKED` / `DEFERRED` / `NOT_APPLICABLE`), five clocks kept apart, no silent
constants, and the rule that a status above EXPERIMENTAL must cite the experiment
that earned it. **Nothing is CORE**, because no NFL experiment has run.

Start with `nfl/NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md`, then
`nfl/NFL_EXPERIMENTAL_ROADMAP.md`, then `nfl/NFL_G0A_CHECKLIST.md`.
