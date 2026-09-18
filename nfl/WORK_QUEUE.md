# WORK QUEUE

The ordered work queue for the standing autonomous execution directive
(owner, 2026-09-18). This file is the **input**: item text, priority,
dependencies and acceptance criteria are authored here.
`nfl/AGENT_STATE.json` and `nfl/HANDOFF.md` are **generated from it plus git**
by `python3.12 nfl/tools/agent_state.py --write`, so they cannot drift from it.

## Status vocabulary

`QUEUED` `ACTIVE` `BLOCKED` `DONE` `SUPERSEDED`

An item is **not** `DONE` until its acceptance criteria, its tests, its
artifact verification, its commit and its push have all completed and been
read. A printed terminal line is not verification; the artifact or the remote
ref is.

## Discovery classification

A newly discovered defect is classified before it is allowed to interrupt the
order: `CRITICAL_CORRECTNESS`, `PRODUCTION_BLOCKER`, `RESEARCH_BLOCKER`,
`MEASUREMENT_DEFECT`, `NONBLOCKING_TECH_DEBT`. It jumps the queue only when
its downstream impact justifies it.

---

## ID: P6
- **priority**: 1
- **status**: DONE
- **dependencies**: suite attribution at `7d46f39` (DONE)
- **description**: Implement the existing P7 dependency-DAG specification
  inside `nfl/production/pipeline.py`. Do not redesign it and do not create a
  second orchestrator.
- **blocker**: none
- **acceptance criteria**:
  - the four node types, declared edges with enumerated `fields`, and node
    identity `H(spec_version, code_identity, sorted(input identities),
    declared_fields)` live in `nfl/production/pipeline.py`;
  - an AST audit fails on any read of the vintage store not declared as an
    edge, and a synthetic undeclared read is proven to fail it;
  - the three invalidation cases are demonstrated: unchanged input reuses the
    cached node, an inactives change invalidates only downstream of inactives,
    an unrelated research artifact does not invalidate the game-day forecast;
  - a real slice is wired into `run_forecast`, not merely tested beside it;
  - full suite shows no newly introduced failure against `7d46f39`;
  - committed and pushed to `claude/nfl-greenfield-architecture-stsxmk`.

## ID: P7
- **priority**: 2
- **status**: ACTIVE
- **dependencies**: P6
- **description**: Generate a canonical `SYSTEM_STATE.json` and derive
  `CURRENT_STATE.md` from it. Two independently maintained truths is the
  defect; one generated from the other is the repair.
- **blocker**: none known
- **acceptance criteria**:
  - `SYSTEM_STATE.json` is generated from the repository, never hand-edited;
  - `CURRENT_STATE.md` is generated from `SYSTEM_STATE.json`;
  - a test fails if either is stale against a live regeneration;
  - no number in either file is retyped from prose.

## ID: P8
- **priority**: 3
- **status**: QUEUED
- **dependencies**: none
- **description**: Reconcile Contract 4: the prose says 18/20 and the
  executable constant requires 19/20. Trace the chronology and resolve by
  append-only supersession, never by editing the older text.
- **blocker**: none known
- **acceptance criteria**:
  - the chronology is traced to commits and stated;
  - the resolution is a successor record, not a rewrite;
  - test `CONTRACT_TEXT_AND_EXECUTABLE_CONSTANT_MUST_AGREE` exists and passes.

## ID: P9
- **priority**: 4
- **status**: QUEUED
- **dependencies**: none
- **description**: Resume OAS1 from its amended preregistration state. Pass
  and rush stay separate. `GO_NO_GO` still records NO-GO gates and those stay
  recorded.
- **blocker**: none known
- **acceptance criteria**:
  - the amended preregistration is read and quoted before any run;
  - no gate is loosened to obtain a GO.

## ID: A3
- **priority**: 5
- **status**: QUEUED
- **dependencies**: assumption registry (DONE, A1/A2 settled)
- **description**: Automatic Scientist — test
  `A3_ROLE_CONTINUITY_ACROSS_REGIME_CHANGES` against measurement.
- **blocker**: none known
- **acceptance criteria**:
  - forward-chained, strictly prospective cuts;
  - the settlement moves only along a legal status edge and carries evidence;
  - a falsification blocks only the affected production path and rewrites no
    model output.

## ID: A5
- **priority**: 6
- **status**: QUEUED
- **dependencies**: assumption registry
- **description**: Automatic Scientist — test
  `A5_TD_CONVERSION_PORTABILITY`.
- **blocker**: none known
- **acceptance criteria**:
  - forward-chained, strictly prospective cuts;
  - the settlement moves only along a legal status edge and carries evidence;
  - a falsification blocks only the affected production path and rewrites no
    model output;
  - portability is tested ACROSS the boundary it claims to cross, not within
    one side of it.

## ID: A4
- **priority**: 7
- **status**: BLOCKED
- **dependencies**: an identified estimand
- **description**: `A4_STATIC_TEAM_VOLUME_SUFFICIENCY` is half-measured and
  deliberately DECLARED rather than TESTED.
- **blocker**: the remaining estimand is not yet measurable. Completing it
  before it is measurable would manufacture a settlement, which is the
  failure mode the registry exists to prevent.
- **acceptance criteria**:
  - the remaining estimand is stated and shown to be identified at the
    available sample before any measurement is attempted.

## ID: GAME_STATE
- **priority**: 8
- **status**: BLOCKED
- **dependencies**: P6, P7, and a lawful pregame-only state generator
- **description**: The score/clock/game-state generative layer.
- **blocker**: prerequisite work has not made it lawful. The T1-C pregame-only
  generator exists; what is missing is the evidence that a game-state layer
  may consume it without a postgame path.
- **acceptance criteria**:
  - no postgame field reaches the generator, proven by a declared DAG edge
    rather than by the absence of a reader.

## ID: OUT-022C
- **priority**: 9
- **status**: BLOCKED
- **dependencies**: an actual FanDuel slate salary export
- **description**: FanDuel single-game salaries. Stays open until a real
  export exists.
- **blocker**: no FanDuel salary export is in the repository and none can be
  fetched from here. **This is assigned, not blocked for both agents**: it
  needs bytes from outside this checkout. FanDuel provenance stays
  `VERIFIED_RULE_VALUE_RELAYED_SOURCE` and is not upgraded.
- **acceptance criteria**:
  - a real FanDuel export is present with provenance;
  - no salary is inferred from DraftKings, at any point, for any player.

## ID: SUITE-PRE
- **priority**: 10
- **status**: QUEUED
- **dependencies**: none
- **description**: The 136 PRE_EXISTING suite failures classified at
  `7d46f39`. Not to be fixed merely to obtain a green suite; to be worked
  deliberately, by cause, when a cause is on the critical path.
- **blocker**: none — deliberately low priority
- **acceptance criteria**:
  - any failure fixed is traced to its cause and its test is updated rather
    than suppressed.
