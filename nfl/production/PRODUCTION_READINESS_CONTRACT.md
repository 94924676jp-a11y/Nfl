# Production readiness contract

**Production-ready** means the system can, from an **authorized point-in-time
input state**, carry a slate end to end and produce an immutable forecast
artifact — **or refuse, in writing, with a named code.**

It does **not** mean the model is good. Model quality is a separate axis with
its own gates, and this contract deliberately says nothing about it.

## The twelve capabilities

| # | capability | enforced by | state |
|---|---|---|---|
| 1 | identify the game slate | `schedules` capture + `capture.schedule` | **GREEN** |
| 2 | resolve teams and players deterministically | `nfl/identity`, `players.csv` crosswalk (`pff_id`/`nfl_id` 100% of the WR/TE/RB frame) | **GREEN** |
| 3 | retrieve and validate authorized source data | `capture/registry.py`, `capture_vintage.py` | **GREEN** |
| 4 | verify source timestamps and hashes | `governance/provenance.py`, `availability.verify_record` | **GREEN** |
| 5 | build model inputs without leakage | ordinal prefix cut; `pipeline.assert_no_postgame_inputs` | **GREEN** |
| 6 | generate player-level football distributions | RC1 receiving, P4C carries, Stage 2 participation, TD1 layer | **PARTIAL** — QB layer is `BASELINED`, not modelled |
| 7 | reconcile team/player accounting | `nfl/accounting/invariants.py` | **GREEN** |
| 8 | generate joint draw artifacts | `production/joint.py` minimum-viable coupling | **BASELINE** |
| 9 | deterministic fantasy scoring as a downstream view | `nfl/scoring/engine.py` | **GREEN** |
| 10 | write immutable prospective forecast artifacts | `prospective/artifact.py` | **GREEN** |
| 11 | register in the benchmark/evaluation framework | `prospective/registries.py`, evaluation protocol | **GREEN** |
| 12 | refuse output when provenance or integrity fails | `production/refusal.py`, 17 named codes | **GREEN** |

## The rules the entrypoint enforces

- **Fail closed.** A stage with no production model returns
  `STAGE_NOT_IMPLEMENTED`, never a fabricated number.
- **No implicit current time for a scientific clock.** `written_at` is a
  required argument. The wall clock may stamp *operational* fields; it may
  never stand in for `written_at`, `retrieved_at` or `source_timestamp`.
- **No silent fallback to an unauthorized source.** An input outside the
  registry is `UNAUTHORIZED_INPUT`.
- **No fuzzy identity joins.** Ever.
- **No 2026 outcome consumption** unless the arm and the owner state both
  allow it. Arm A never.
- **No mutation of a prior artifact.** A correction is a new artifact naming
  what it supersedes.

## What production may and may not do while NFL-1 is NOT AUTHORIZED

| action | allowed? |
|---|---|
| compute a forecast | **YES** |
| seal it locally as an immutable artifact | **YES** |
| run the pipeline on historical fixtures, tagged non-prospective | **YES** |
| **publish** a forecast | **NO** — `authorization.may_publish()` refuses |
| register a dry run as prospective evidence | **NO** |
| flip authorization because tests pass | **NO** — there is no such path |

## What "not perfect" does not mean

A model whose measured signal is weak is **shippable** if it is honest,
chronology-safe, reconciled and auditable. RC1 and RC2 both returned weak
results; neither is a reason to withhold a baseline. **What is not shippable is
an unverifiable forecast** — that is a scientific-integrity requirement and it
is blocking.
