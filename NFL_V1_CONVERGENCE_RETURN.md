# NFL V1 convergence packet

**2026-09-09.** Suite **47 modules, 489 test functions, 2,863 checks, 0 failing,
0 raised**. G0A **11/12**. NFL-1 **NOT AUTHORIZED**. `PATH_C_STATE` untouched.
No 2026 outcome read. Nothing promoted.

---

## A. V1 verdict

# `V1_REHEARSAL_READY_WITH_NAMED_BLOCKERS`

**Not** `V1_ENGINEERING_READY_WAITING_ON_G0A`, and the distinction is the point.

The system now runs the real slate end to end and refuses correctly, which it
could not do this morning. But three of the four freeze criteria are not met,
and the failures are **engineering-visible and unrepaired**, not merely waiting
on an external event:

- **Accounting coherence — FAILS.** One football event is generated twice
  (passing↔receiving yards and TDs), QB dropback share leaks 2.3–6.9%, and
  four accounting verdicts read FAIL on every game while records are emitted
  anyway.
- **Joint coherence — FAILS.** The two teams in a game are drawn
  independently; RB1↔RB2 competition is **wrong-signed**.
- **Distributional validity — FAILS.** Production emits four quantiles and no
  draws, so no proper score can be computed from its output at all.
- **Production/governance validity — PASSES**, as of today's repairs.

Declaring engineering-ready would require calling a +0.081 RB1↔RB2 correlation
against a realised −0.329 "directionally credible". It is not: it is the wrong
sign on the most-used correlated pair in NFL player props.

## B. Blocking table

| # | blocker | causal layer | measured severity | repaired? | evidence | remaining action |
|---|---|---|---|---|---|---|
| B1 | Whole slate refused on a Python traceback | production entrypoint | **16 of 16 games** `STAGE_RAISED` | **YES** | 16/16 now `SEALED`, 84 QB forecasts | none |
| B2 | Implemented layers reported "unimplemented" and counted PASS | entrypoint ↔ non-QB chain | 5 layers × 16 games | **YES** | per-game `INJURY_REPORT_NOT_YET_FILED` ×15, `INJURY_REPORT_INCOMPLETE` ×1 | none |
| B3 | Fixture could seal distributions no model produced; `eligibility_verdict` hardcoded `'PASS'` | artifact sealing | 1 fixture → full sealed artifact | **YES** | exploit re-run → `EMPTY_FORECAST_ARTIFACT`; `distributions_source` + `TEST_ONLY` now stamped | none |
| B4 | Artifact named a commit that was not the code that ran | provenance | observed live: clean hash, 125 modified lines | **YES** | `code_commit` now `…+dirty[16]`, and it enters execution identity | none |
| B5 | `invariants.check`/`le_check` returned PASS over **zero groups** | accounting | any zero-row read → green invariant | **YES** | `INVARIANT_NOT_MEASURED_*` | none |
| B6 | `reconcile_team` checked nothing on a key-shape mismatch | QB accounting | guard "has never refused anything" | **YES** | `QB_TEAM_RUSH_BUDGET_KEY_MISMATCH`; both shapes accepted | none |
| B7 | **Every game on a slate shared one RNG stream** | seeds / layers | two disjoint games at **r = +0.545**; target-mass vectors bit-identical | **YES** | after: **0.0634** (noise at m=200); same `game_id` reproduces exactly | none |
| B8 | QB composition stretches a small draw; **49.14 composed passing TDs** (record is 7) | football engine | 4.50% of dropback draws = 1; factor to **59.85**; 55.8% of cells stretched | **MEASURED, NOT REPAIRED** | verdict now `FAIL[QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED]` | **R2** — pre-registered, needs authorisation |
| B9 | Passing yards and TDs generated **twice**, reconciled never | cross-layer | identity fails **12,800 of 12,800 draws**; mean \|residual\| 98.7 yd on 221.7; corr(pass, recv) ≈ **+0.001** | NO | `xl1_results.json`, engine `cross_layer` | **promote C3** — built, `SHARED_PASS_DEFAULT='off'` |
| B10 | Two teams in a game drawn independently | team volume | corr(home, away) carries **+0.015 model vs −0.534 real**; SD(total plays) +33%; **2.0% of games outside the entire 2020–25 range** | NO | Stream C, executed | extend A3 to one shared index **per game** |
| B11 | RB1↔RB2 competition **wrong-signed** | allocation × volume | model **+0.081**, real **−0.329**; P(r>0) 0.68 vs 0.029 | NO | Stream C, executed | ablation first: share one `add_pool` index per team-game |
| B12 | QB allocation share leaves the system | QB allocation | **2.29%** (ARI/LAC), **6.91%** (ATL/PIT) of dropbacks | NO (fail-closed) | `QB_ALLOCATION_SHARE_UNCONSUMED` | owner decision, OWN-1 |
| B13 | Output is four quantiles; **no draws, no CDF** | player record | every metric | NO | `player_record.py:81-93` | store draws or a dense CDF |
| B14 | Accounting FAILs do not gate emission | engine | 4 FAILs per game, records emitted | NO | `football_engine` records strings and continues | make publication assert accounting |
| B15 | Non-QB player coverage | data | **2 of 32 teams** filed | N/A — **DATA_BLOCKED** | readiness report | wait for filings |

## C. Accepted V1 architecture — one owner per quantity

```
schedule ─► team_volume_v1 (D1, frozen P4B)
              ├─ team_off_snaps ─┐
              ├─ team_dropbacks ─┤  ONE OWNER EACH, per team
              ├─ team_carries ───┤  ✗ NOT paired across the two teams (B10)
              ├─ team_targets ───┤  ✗ DUPLICATE of the throw process (B9)
              └─ team_rz_carries ┘
                       │
   ┌───────────────────┴────────────────────┐
   ▼                                        ▼
QB V1 ──► QB3 allocation (share)      P3 appearance ──► Stage-2 participation
   │        │                                              │
   │        └─► composition = target/drawn                 ▼
   │             ✗ stretches small draws (B8)        P4C system C simplex
   │             ✓ mass conserved (OWN-4)             ├─ targets  ─► RC1 conversion ─► TD2
   │             ✗ 2.3–6.9% share leaks (B12)         └─ carries  ─► (rushing conversion
   ▼                                                                 UNDEFINED)
passing yards, passing TD ◄──✗ SAME EVENT, GENERATED TWICE (B9) ──► receiving yards, receiving TD

rushing budget: team_carries ─┬─ scrambles      (dropback-owned)   ✓ OWN-8
                              └─ rush_play_budget
                                   ├─ kneels, designed QB, RB, WR, TE, fringe
                                   └─ A1 closes this exactly — research only
```

**Resolved ownership:** scramble → dropback; designed QB rush and kneels →
carry (OWN-8, two independent tests). **Unresolved:** the passing event has two
owners; `team_targets` has two owners; the QB dropback level has two owners
(QB V1's own draw and D1×QB3), reconciled by the division that causes B8.

## D. Full-system rehearsal — real 2026 week 1, no fixture

| | |
|---|---|
| games attempted / completed | **16 / 16 SEALED** |
| roster source | `weekly_rosters.0b005c45d924a541`, 2,955 rows |
| player coverage | **84 QB forecasts** across the slate; **187 roster players per game** — QB-only, declared `PARTIAL_PLAYER_COVERAGE` |
| refusal reasons | `appearance` `INJURY_REPORT_NOT_YET_FILED` ×15, `INJURY_REPORT_INCOMPLETE` ×1; then `BLOCKED_UPSTREAM_*` ×16 each |
| stages PASS | capture, identity, team_environment, qb_layer, joint_reconciliation, player_draws, scoring, artifact_sealing — 16 each |
| per-draw accounting | receiving identities **0 violations** / 10,400 cells; simplex closure max dev **1.6e-07**; rushing `qb_rush_contained_in_other` **162 of 2,800**; cross-layer TD mismatch **~185 of 200 draws per team** |
| mass conservation | QB composition **0 cells lost** (OWN-4 donor repair active, 1 cell repaired); allocation share **2.29% / 6.91% leaked, refused not renormalised** |
| dependence | corr(passing, receiving) **+0.001**; corr(home, away carries) **+0.015** vs real −0.534; RB1↔RB2 **+0.081** vs real −0.329; cross-game **0.0634** (was +0.545) |
| distribution sanity | QB `att` p10 2 / p50 16 / p90 38 — wide because no model names the starter (`QB_PRIMARY_PASSER_SELECTION`, 2.62 starters/team) |
| deterministic replay | **16 distinct run ids for 16 games**; `code_commit` carries `+dirty[n]`; same `game_id` reproduces bit-for-bit |
| publication | `NFL1_NOT_AUTHORIZED` on all 16 |

## E. Scientific status

See `NFL_V1_RESEARCH_LEDGER.md`. Production baseline: QB V1, D1, P4C system C,
Stage-2, P3 appearance, RC1, TD2, plus the OWN-1/4/7 accounting layer.
Rehearsal-only: QB3, A3, C3, C0, A1, ABC_MPR, `ewma_hl1`. Rejected: ~40
candidates including A2 twice. Falsified diagnoses: 50 catalogued. Post-V1
backlog: kneel game-state dependence, the additive-share residual family (floor
fires on **20.68%** of share draws), receiving calibration, `rint` erasure,
continuous target emission.

## F. Governance

**G0A = 11 / 12.** Item 1 needs an anchored capture inside a real T−90 window;
it cannot be discharged by engineering and was not touched. **NFL-1 = NOT
AUTHORIZED**; no code path can change it. `PATH_C_STATE` unedited. C3, C0, A1,
A3, QB3 all remain rehearsal-only.

## G. What still prevents us from using V1 — five items

1. **One football event is generated twice** (B9). C3 is built, pre-registered
   and measured; promoting it is an owner decision, not engineering.
2. **The two teams in a game are independent, and RB1↔RB2 is wrong-signed**
   (B10, B11). Minimal fix identified: extend A3's shared index from per-team
   to per-game. It changes every drawn number, so it is the same decision class
   A3 already is.
3. **The QB composition stretches small draws into impossible outcomes** (B8).
   Now measured and refused rather than reported PASS; the repair is R2.
4. **Production emits no draws** (B13), so no proper score, tail probability or
   PIT can be computed from V1 output — criterion 3 cannot be met as built.
5. **Non-QB player coverage is data-blocked** (B15): 2 of 32 teams have filed.
   Nothing engineering can do; the chain correctly defers.

Items 1–4 are engineering-visible. Item 4 is the only one I can complete
without an owner decision or a new pre-registration, and it is the one I would
do next.
