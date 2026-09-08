# Release checklist

**"Not perfect" is not "cannot ship." A scientific-integrity requirement is
never non-blocking.** Those two sentences decide every row below.

## GREEN NOW — completed production dependencies

| item | evidence |
|---|---|
| Source registry and authorized-input enforcement | `capture/registry.py`; `UNAUTHORIZED_INPUT` refusal tested |
| Provenance and five-clock validation | `governance/provenance.py` |
| Deterministic identity resolution | `pff_id`/`nfl_id` cover 100% of the 1,126-player frame; no fuzzy matching |
| Leakage-free feature build | ordinal prefix cut; `assert_no_postgame_inputs`; guard-deletion proof |
| Team/player accounting invariants | 8 hold exactly on 3,230 real team-games; the 9th named and bounded |
| Canonical player draw schema | per-draw ordering checks; complete trace required |
| Deterministic fantasy scoring | hand-calculated fixtures; enforced isolation from football |
| Immutable forecast artifact contract | ordering gate, immutability, arm separation |
| Benchmark and candidate registries | projections benchmark-only; nothing promoted |
| Prospective evaluation protocol | predeclared before any 2026 outcome |
| **17 named refusal codes, all persisted** | 16 adversarial cases fail with the right code |
| **Production entrypoint and 14-stage orchestrator** | `run_forecast.py`; fails closed |
| **Idempotency and execution identity** | bit-identical rerun; any input hash change alters identity |
| **Authorization gate** | `may_publish()` refuses; guard-deletion proof |
| T−90 readiness | 10 preflight checks, 0 failing |

## BLOCKED BY G0A — cannot legitimately activate yet

| item | why |
|---|---|
| **Publishing any forecast** | NFL-1 NOT AUTHORIZED. Compute and local seal are allowed; publication is refused. |
| Registering a forecast as prospective evidence | requires a forecast written live after G0A is discharged |
| Activating the live workflow | built, **not enabled**; terminates before publication while unauthorized |
| Any promotion decision | needs prospective evidence that does not yet exist |

## BLOCKED EXTERNAL

| item | why |
|---|---|
| True routes run | licensing; FTN externally pending. Adapter fails closed. |
| 2026 `pbp_participation` / `snap_counts` | both 404. Watch running under RET-001; **not authorized for predictive use.** |
| Point-in-time professional projections | none held; registered unavailable, never backfilled |

## NON-BLOCKING RESEARCH DEBT — improves quality, does not prevent shipping

| item | state |
|---|---|
| Receiving calibration (bias +2.18) | `CALIBRATION_DEFECT_CONFIRMED`; R1 direction promising |
| Receiving conversion | `SIGNAL_WEAK` — measured, honest, shippable |
| TD conversion | `SIGNAL_WEAK` — production uses the accepted control |
| QB decomposition | `BASELINED`; production uses a shrinkage baseline |
| Joint dependence beyond volume coupling | production baseline is deliberately neutral where unsupported |
| 2024 carry rank1↔rank2 anomaly | registered, explicitly not tuned to |

**None of the above is a reason to withhold a baseline.** RC1, RC2 and TD2 all
returned weak results; a weak but honest, chronology-safe, reconciled and
auditable model is shippable. What is **not** shippable is an unverifiable
forecast — and that is why every row in BLOCKED BY G0A stays blocked.
