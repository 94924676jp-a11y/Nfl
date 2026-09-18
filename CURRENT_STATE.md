# NFL — current state

**Generated** by `nfl/tools/system_state.py` at 2026-09-18T20:38:52.267682+00:00 from `SYSTEM_STATE.json`. Do not hand-edit this file: regenerate it.

Every value under `measured` was computed by reading this repository at the timestamp above. Every value under `declared` was asserted by somebody and says who, when, and why it cannot be measured here. Do not quote one as the other.

---

## 1. Repository

|  |  |
|---|---|
| branch | `claude/nfl-greenfield-architecture-stsxmk` |
| HEAD | `20468a5` — P9: OAS1 Week 2 is fitted, and the selection selected nothing |
| HEAD committed | 2026-09-18T18:49:44+00:00 |
| commits on branch | 879 |
| source scope | 2 dirty source file(s) |
| dirty tree entries (source and not) | 20 |
| code_version | `20468a56f6e269ddd93a814e563f5cf0104f5643+src1[63a11d3f20432192]` |
| python modules | 659 |
| lines of python | 211,384 |

## 2. Test suite

Source: `nfl/research/suite_attribution/SUITE_DIFF_p9_discovery.json`. measured at WORKING_TREE, HEAD is 20468a5. This total is not a statement about the tree as it stands.

|  | at WORKING_TREE | baseline 20468a5 | delta |
|---|---|---|---|
| modules | 184 | 183 | 1 |
| test functions | 1997 | 1987 | 10 |
| checks | 10632 | 10583 | 49 |
| failing checks | 61 | 63 | -2 |
| raised | 21 | 21 | 0 |
| zero check functions | 0 | 0 | 0 |
| blocked functions | 23 | 23 | 0 |

Verdict: **SUITE FAIL**. Classification against the baseline: {'PRE_EXISTING': 133, 'RESOLVED_SINCE_BASELINE': 3}.

No item is newly introduced since the baseline.

## 3. Captured evidence

`nfl/vintage_manifest.jsonl` carries **4529 rows**; the vintage store holds **1449 files**. Retrieval spans 2026-09-06T18:50:49.540119+00:00 to 2026-09-17T23:42:25.952893+00:00.

| source | manifest rows |
|---|---|
| depth_charts | 471 |
| espn_injuries_json | 462 |
| hardrock_market_snapshot | 1 |
| injuries | 472 |
| official_inactives | 483 |
| official_injury_report | 465 |
| official_status_evidence | 1 |
| official_transactions | 462 |
| pbp | 4 |
| pbp_participation | 383 |
| schedules | 471 |
| snap_counts | 383 |
| weekly_rosters | 471 |

Manifest row states: {'BLOCKED': 567, 'DEFERRED': 40, 'FAIL': 108, 'NOT_APPLICABLE': 766, 'PASS': 3048}.

## 4. Governed assumptions

| assumption | status | criticality |
|---|---|---|
| A1_APPEARANCE_CERTAINTY | FALSIFIED | CRITICAL |
| A2_PROPORTIONAL_REDISTRIBUTION | FALSIFIED | CRITICAL |
| A3_ROLE_CONTINUITY_ACROSS_REGIME_CHANGE | DECLARED | MATERIAL |
| A4_STATIC_TEAM_VOLUME_SUFFICIENCY | DECLARED | CRITICAL |
| A5_TD_CONVERSION_PORTABILITY | DECLARED | MATERIAL |

A FALSIFIED assumption blocks the production path that depends on it and rewrites no model output.

## 5. Dependency DAG (P7 Phase 1)

`PHASE_1_DECLARATION_ONLY`, audit **PASS EVERY_VINTAGE_READ_DECLARED**, 27 declared edges over 4 package(s), 3 runtime-keyed read(s).

| producer | declared readers |
|---|---|
| depth_charts | 3 |
| espn_injuries_json | 1 |
| injuries | 2 |
| schedules | 4 |
| vintage_manifest | 6 |
| weekly_rosters | 11 |

Not implemented:

- PHASE_2: a read(node, cut) accessor. Every read below still happens by globbing a directory; the declaration bounds who reads what, it does not mediate the bytes.
- PHASE_3: content-addressed recomputation ACROSS RUNS. The identity algebra and the cache exist and are exercised inside a run; nothing is persisted between runs yet.

## 6. Forecast and postgame artifacts

160 `run_status.json` file(s), by status {'REFUSED': 10, 'SEALED': 150}. 18 live board directory(ies).

Prospective evaluation ledger: 2 rows over 1 block(s) ['DET_BUF_2026W2'], by status {'AWAITING_OUTCOME': 1, 'GRADED': 1}. Captured game outcomes: 1 (DET_BUF_2026W2).

Production readiness (`nfl/production/production_readiness.json`, updated 2026-09-08): {'BASELINE': 1, 'GREEN': 10, 'PARTIAL': 1} over 12 capabilities.

- 6 generate player-level football distributions: **PARTIAL**
- 8 generate joint draw artifacts: **BASELINE**

## 7. Work queue

| id | priority | status | blocker |
|---|---|---|---|
| P6 | 1 | DONE |  |
| P7 | 2 | DONE |  |
| P8 | 3 | DONE |  |
| P9 | 4 | DONE |  |
| A3 | 12 | QUEUED |  |
| DISC-1 | 1 | DONE |  |
| DISC-2 | 2 | BLOCKED | **measured, not assumed — the conditioning variable has no contrast.** `A1_SUCCESSOR_FEASI |
| DISC-3 | 3 | ACTIVE |  |
| DISC-4 | 8 | QUEUED |  |
| DISC-5 | 13 | QUEUED |  |
| OAS1-TIEBREAK | 5 | BLOCKED | **owner decision, and it may not be taken by whoever has seen the scores.** The three vari |
| OAS1-HURDLE | 6 | BLOCKED | the captured 2026 play-by-play carries **week 1 only** — read from the file, 2,756 rows, z |
| OAS1-FLAT-SURFACE | 7 | QUEUED |  |
| A5 | 6 | QUEUED |  |
| A4 | 7 | BLOCKED | the remaining estimand is not yet measurable. Completing it before it is measurable would  |
| GAME_STATE | 8 | BLOCKED | prerequisite work has not made it lawful. The T1-C pregame-only generator exists; what is  |
| OUT-022C | 9 | BLOCKED | no FanDuel salary export is in the repository and none can be fetched from here. **This is |
| PRE-PORCELAIN | 11 | QUEUED |  |
| SUITE-PRE | 10 | QUEUED |  |

Source: `nfl/WORK_QUEUE.md`. Full descriptions and acceptance criteria are there.

## 8. Declared — asserted, not measured here

Each of these is a statement nobody can settle by reading this repository. They are kept because they are load-bearing, and labelled because a declaration standing beside a measurement in the same voice is how this file went eleven days wrong.

**EGRESS_DENIED** — This executor has no outbound network. The egress proxy returns 403 on every outbound request, including to nfl.com, measured from two separate cloud sessions rather than inferred from one.

- declared by agent (this checkout), corroborated by a second session, 2026-09-07 (STANDING)
- not measurable here: a repository read cannot establish a network fact, and a generator that tried would be measuring the moment it ran rather than the standing policy.
- what would verify it: an executor with egress to nfl.com that can run at kickoff−90 minutes.

**NETWORKED_AGENT_EXISTS** — A second agent on this project has network, holds the live sportsbook odds connector, can see project storage outside this git checkout, and can run long simulations.

- declared by owner, 2026-09-07 (STANDING)
- not measurable here: the other agent's capabilities are not recorded in this tree.
- what would verify it: nothing here; it is a standing fact about the team. Its operational consequence is written down instead: a task blocked only for this executor is **assigned**, not blocked, and the request goes into `docs/AGENT_OUTBOX.md` before anything is marked blocked.

**REAL_MONEY_NOT_ENABLED** — No money has been staked and none may be. Real money is NOT ENABLED and the weekly exposure cap is deliberately UNSET.

- declared by owner, standing (STANDING)
- not measurable here: a governance decision, not a repository property. The repository can show the flag; it cannot show the intent behind it.
- what would verify it: an owner ruling changing it. Until then the cap stays unstated and is not filled in.

**V2_NOT_EARNED** — V2 is not earned. A version number follows evidence; it is not a label applied in advance to work that hopes to earn it.

- declared by owner, standing (STANDING)
- not measurable here: promotion is a decision.
- what would verify it: a methodological change large enough to justify it, demonstrated on data that selected none of it.

**FANDUEL_PROVENANCE** — FanDuel single-game rules are recorded at provenance `VERIFIED_RULE_VALUE_RELAYED_SOURCE`. They were relayed, not read from a FanDuel document by this executor, and the provenance is not upgraded.

- declared by agent, on the relay, 2026-09-16 (STANDING)
- not measurable here: the repository holds the values; it cannot hold the fact of having seen the source.
- what would verify it: a FanDuel slate export or rules page retrieved with provenance. Until then OUT-022C stays open and no salary is inferred from DraftKings.

**MARKET_IS_EVALUATION_ONLY** — Sportsbook prices may evaluate a forecast and may never feed one. DFS ownership and contest behaviour never flow backward into football prediction.

- declared by owner, standing (STANDING)
- not measurable here: the repository can be audited for a market column reaching a model — and the P7 dependency DAG now does exactly that for the `schedules` blob's price columns — but the rule itself is a decision.
- what would verify it: nothing; it is the rule. The DAG's `EDGE_DECLARES_MARKET_FIELD` refusal is its enforcement, not its source.

**SCHEDULED_CAPTURE_STATE** — The state of any GitHub-hosted capture routine — enabled, disabled, last fired — is not knowable from this checkout.

- declared by agent, 2026-09-18 (STANDING)
- not measurable here: routines live in a scheduler this executor cannot query. The previous `CURRENT_STATE.md` asserted a routine was DISABLED and recorded, in the same file, that a later firing reported success with no commit ever reaching the branch — an unresolved contradiction that it presented as state.
- what would verify it: a scheduler query by an agent that can make one, or a commit arriving on the branch from a runner. What this repository CAN say is measured instead: whether any capture is recorded in the manifest and when the newest one was retrieved.

## 9. Superseded

Hand-written state files this generated one replaces. They are kept unedited, because a note prepended to a historical document changes the document; the pointer belongs in the successor.

- `nfl/research/state/CURRENT_STATE_2026-09-07.md` (9024 bytes, sha256 e0dea212d4d1ab6a…)

---

To refresh: `python3.12 nfl/tools/system_state.py --write`.
