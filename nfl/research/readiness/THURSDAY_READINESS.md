# Thursday readiness board — 2026-09-24

Built 2026-09-22 from measurement, not from recollection. Every RED and YELLOW
below carries the probe that produced it.

**Headline: the forecasting engine is closer to ready than the DFS operation
is.** Five of six P0s are fixed and tested. The sixth is a deliberate hard
block. What is missing for Thursday is mostly *operational* — a daily
workflow, a player board, a change log, a classic optimizer — not model
correctness.

---

## GREEN — working and validated

| System | Evidence |
|---|---|
| **schedule / identity** | vintage selector PASS at cut; `player_universe` 156 rows, 0 unaccounted states |
| **depth charts** | offensive and special-teams axes selected independently; byte-identical under reversed input and 60 shuffles, 4 dual-role cases |
| **injuries** | injuries vintage PASS, designations typed, absence ≠ clean bill |
| **inactives** | owner board applied at its true tier; ACTIVE never inferred from omission; 13/13 resolved, 0 ambiguous |
| **current-season carries / targets** | `usage_vintage` 16 games, 32 clubs, weeks < N enforced twice |
| **current-season snaps** | PFR 1,492 rows, 32 clubs, week 1 |
| **roles** | `role_state` typed, 6 conflict codes, governor now reaches the generator |
| **opportunity (Stage 6)** | CS6: current-season evidence connected under forward-chained estimated weights |
| **simulation determinism** | 8 identical calls → 1 result; ordering by (season, week), never by arrival |
| **sealing** | fails closed; `HARD_INVARIANT_FAILED` demonstrated on both runs |
| **dossiers** | 156 per slate, 28/28 publishable covered (1.0000), saved per player |
| **review gate** | PASS / PASS_WITH_WARNINGS / BLOCKED; 14 blocking codes; unregistered code blocks |
| **refusal propagation** | `UPSTREAM_RUN_REFUSED`; missing status is `RUN_STATUS_ABSENT`, not presumed fine |
| **exact sportsbook-line probability** | `market.evaluate.evaluate_line(x, line)` counts P(over)/P(under)/P(push) **from draws** with MCSE — never reconstructed from quantiles |
| **postgame actuals** | `postgame/actuals.py` + `grade_projections.py` operational |

## YELLOW — usable with a disclosed limitation

| System | Limitation |
|---|---|
| **routes / personnel** | **UNAVAILABLE for 2026.** `pbp_participation` 404s; no pass/run split in the snap file. 21–22 receivers per slate carry `RECEIVING_ROLE_RESTS_ON_RAW_SNAPS_ONLY`. A *claim* on this evidence BLOCKS. Assigned, not blocked. |
| **efficiency / TD model** | frozen priors by design; not refreshed with 2026 |
| **CSV export** | exists for Showdown (`DKEntries_UPLOAD_*.csv` verified 20 lineups) — **not verified for classic** |
| **projection audit** | works, but `P1-01`: the inversion check reports "not supported by any axis the review can read" when the supporting axis is the prior-season share it cannot read |
| **two role systems** | narrowed by CS6 for the opportunity centre; tiers are still computed independently from 2025 trailing snaps |

## RED — blocks production

| System | Why |
|---|---|
| **team volume** | `denom_panel` / `team_volume_history` newest ordinal **202518**. `team_targets` is an EWMA whose most recent observation is 2025 week 18. Declared `CURRENT_SEASON_SOURCE_UNVERIFIED`; blocks at sealing **and** now upstream. **Connecting player opportunity share did not connect team volume.** |
| **classic optimizer** | does not exist. `nfl/dfs/` holds `salaries/`, `scoring/`, `showdown/` only |
| **daily workflow** | no Mon→Sat pipeline, no `EARLY_SLATE_PLAYER_BOARD`, no `SATURDAY_FINAL_CANDIDATE_BOARD` |
| **projection change log** | no artifact records old → new → delta → cause |
| **player board** | no single Fantasy-Cruncher-equivalent surface; the data exists across dossiers and draws but is not assembled |

## UNKNOWN — not yet measured

| System | What is missing |
|---|---|
| **ownership** | `OWNERSHIP_MODEL_UNAVAILABLE`. Code exists only under `nfl/research/*`; nothing in production. **No GPP profitability may be claimed.** |
| **field / contest simulation** | `FIELD_MODEL_UNAVAILABLE`. No payout, field-size or duplication module in production. |
| **historical validation of CS6** | the before/after is a diagnostic on one slate. No forward-chained DFS-level validation exists. |
| **79 except-continue sites / 150 zero-for-missing sites** | counts measured, individual triage NOT done. Most are legitimate; a minority may be real. |

---

## Definition-of-ready checklist

| Requirement | State |
|---|---|
| all P0 fixed or hard-blocked | **YES** — 5 fixed, 1 hard-blocked by design |
| current-season opportunity connected | **YES** (CS6) |
| no stale current-season input silently publishes | **YES** — refuses upstream and at sealing |
| dossier complete for every publishable player | **YES** — 28/28, 1.0000 |
| review gate enforced | **YES** — structural bypass test |
| official inactive handling proven | **YES** |
| role redistribution proven | **YES** — conserved 31.34 → 31.34 |
| projection decomposition available | **YES** — Stage-6 attribution emitted per player |
| simulation deterministic | **YES** |
| exact sportsbook-line probabilities | **YES** — counted from draws |
| DFS optimizer gated | **YES for Showdown**; no classic optimizer exists |
| CSV export verified | **Showdown only** |
| postgame evaluation operational | **PARTIAL** — actuals + projection grading exist; no slate rewind |
| all known limitations visible | **YES** — this board plus the failure register |

**Verdict: NOT production-ready as a full DFS operation on Thursday.** Ready as
a *single-game forecasting and review system* with disclosed limits. The gap is
operational breadth, not model correctness.
