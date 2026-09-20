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

## Continuous discovery

After every completed cycle, `python3.12 nfl/tools/discovery.py --write`
inspects captures, gaps, assumption statuses, suite classification, prospective
counts and technical debt, and emits `nfl/DISCOVERY.json` with the candidates
it detected mechanically.

**It detects; this file ranks.** The four factors -- downstream impact,
uncertainty, measurability, expected value of information -- are judgements and
none of them is measurable from this tree, so every item above carries a
`ranking` line stating them in words. A number for any of them in the generated
artifact would be a silent constant wearing a measurement's clothes.

**An empty candidate list is a result.** It means do validation and monitoring,
not find something to build.

**On A3 stepping back from ACTIVE to QUEUED.** A3 had a feasibility measurement
done (108 QB-starter changes over 2024-2025; head-coach changes undetectable
because the pbp coach field appears season-constant). It is MATERIAL and
DECLARED. DISC-1 and DISC-2 concern an assumption that is CRITICAL and
FALSIFIED with no successor, and newly available data bears directly on it.
That is what justifies the jump; the queue is not reordered for novelty.

## Regeneration obligation

Three generated files must be refreshed before a commit that changes the tree,
or their own tests fail:

```
python3.12 nfl/production/pipeline.py --write-read-inventory
python3.12 nfl/tools/system_state.py --write
python3.12 nfl/tools/agent_state.py --write
```

That is the contract working, not an inconvenience: a generated file that does
not track the tree is exactly the defect P7 repaired.

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
- **status**: DONE
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
- **status**: DONE
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
- **status**: DONE
- **dependencies**: none
- **description**: Resume OAS1 from its amended preregistration state. Pass
  and rush stay separate. `GO_NO_GO` still records NO-GO gates and those stay
  recorded.
- **blocker**: none known
- **acceptance criteria**:
  - the amended preregistration is read and quoted before any run;
  - no gate is loosened to obtain a GO.

## ID: A3
- **priority**: 12
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

## ID: DISC-1
- **priority**: 1
- **status**: DONE
- **dependencies**: none
- **description**: Write the successor research specification for
  `A1_APPEARANCE_CERTAINTY`. A1 is FALSIFIED and CRITICAL and has **no
  successor spec**, while A2 -- falsified the same day, and only MATERIAL --
  has one. The spec must declare what would un-falsify A1: the conditioning
  variable, the estimand, the population, the forward-chained cuts, and the
  falsifier. It must be written BEFORE DISC-2 measures anything, or DISC-2 is
  exploratory rather than confirmatory.
- **blocker**: none
- **acceptance criteria**:
  - the successor spec names its conditioning variable and its falsifier;
  - it is committed before any measurement under it is run;
  - it does not hand-pick a clipping value, a floor, or a shrinkage constant;
  - the falsified A1 record is superseded, not rewritten.
- **classification**: RESEARCH_BLOCKER
- **ranking**: impact HIGH (CRITICAL, blocks three declared consumers) x
  uncertainty LOW (the defect is known) x measurability HIGH (writing) x EVI
  HIGH (it governs the design of DISC-2, which is the measurement that matters)

## ID: DISC-2
- **priority**: 2
- **status**: BLOCKED
- **dependencies**: DISC-1 (DONE)
- **description**: Measure whether official injury designations condition
  appearance in 2026. `injuries` began publishing 2026-09-07 and this
  repository holds **9 content-addressed vintages through 2026-09-17**,
  carrying weeks 1 and 2 with `report_status` (Out 33, Questionable 28,
  Doubtful 6 on the newest blob) and `practice_status`. Appearance outcomes for
  week 1 are in the captured play-by-play. Subsumes the older `PRI-A` item.
- **blocker**: **measured, not assumed — the conditioning variable has no
  contrast.** `A1_SUCCESSOR_FEASIBILITY.json`: the A1 cohort at 2026 week 2 is
  **59 players and none carries an Out, Doubtful or Questionable
  designation** (13 listed with no status, 46 not listed). The effect of
  designation is not estimable at any sample size. A second, independent
  block: the week-2 outcome is not captured either, so even a cohort with
  contrast could not be graded. Both need bytes from outside this checkout;
  the request for 2022–2025 injury captures is in `docs/AGENT_OUTBOX.md`.
  **ASSIGNED, not blocked for both agents.**
- **acceptance criteria**:
  - the read is point-in-time: a designation is used only from a vintage whose
    `learned_at` precedes the cut, through the declared DAG edge;
  - the estimand and falsifier come from DISC-1's spec, not from the data;
  - forward-chained, strictly prospective cuts;
  - a null result is recorded as a measured null and A1 stays falsified.
- **classification**: RESEARCH_BLOCKER
- **ranking**: impact HIGH (appearance is upstream of every non-QB projection)
  x uncertainty HIGH (never measured for 2026) x measurability HIGH (captured,
  content-addressed, bitemporal, with week-1 outcomes) x EVI HIGH (could move a
  CRITICAL assumption from blocking to conditioned)

## ID: DISC-3
- **priority**: 3
- **status**: DONE
- **dependencies**: none
- **description**: The information gap registry has no freshness field and
  nothing re-reads it. `GAP-2026-PARTICIPATION` still records "MEASURED: both
  404 for 2026 as of 2026-09-08" while its sibling `injuries` has been
  publishing since 2026-09-07 -- and nothing in the repository said so.
  `nfl/tools/discovery.py` now detects this class; the remaining work is to
  give each gap a `last_rechecked_utc` and a `recheck_horizon_days`, and to
  re-state the three claims past the horizon from measured evidence. Those
  three, named rather than counted: `GAP-2026-PARTICIPATION`,
  `GAP-PREGAME-ROLE` and `GAP-INJURY-VINTAGE`.
- **blocker**: none
- **acceptance criteria**:
  - every gap carries when it was last rechecked and by what;
  - a claim past its horizon is surfaced rather than trusted;
  - a recheck this executor cannot perform is recorded as ASSIGNED with an
    outbox entry, never as a standing fact.
- **classification**: MEASUREMENT_DEFECT
- **ranking**: impact MEDIUM (it is how DISC-2's data nearly stayed invisible)
  x uncertainty LOW x measurability HIGH x EVI MEDIUM-HIGH (prevents the same
  near-miss recurring across ten gaps)
- **result**: all ten gaps carry `last_rechecked_utc`, `evidence_as_of_utc`,
  `recheck_horizon_days`, `recheck_horizon_basis`, `recheck_method`,
  `recheck_executable_here` and `recheck_assignment`. The load-bearing design
  choice is that **the horizon is measured against `evidence_as_of_utc`, not
  against `last_rechecked_utc`** -- re-reading an unchanged file is not a
  recheck and must not reset the clock, which is exactly how the 2026-09-08
  claim survived snap_counts publishing on 2026-09-10.

  Horizons are per gap, 2 to 90 days, each with its reason: two days for a
  weekly-published file because snap_counts flipped inside two days; ninety
  for `GAP-AIRYARDS-YAC` and `GAP-TD-RECOVERABILITY`, which do not age at all
  because one is semantic and the other is an unrun experiment.

  Three claims restated from measured evidence:
  - `GAP-2026-PARTICIPATION` -- the old claim is **half false**. Measured from
    `nfl/availability_manifest.jsonl`, 24 probes: snap_counts 404 on
    2026-09-08T13:28:42Z, 200 on 2026-09-10T18:31:04Z with 93 rows, 187 rows
    on 09-11, 1,397 rows on 09-14, one unchanging column-order digest.
    pbp_participation 404 at all 12 of its probes. Availability is still not
    predictive eligibility: `NOT_AUTHORIZED_BY_OWNER`, `NO_FORECAST_TO_JUDGE`.
  - `GAP-PREGAME-ROLE` -- "capture running since 2026-09-06" replaced by the
    yield: 663 depth_charts captures PASS over 19 distinct content blobs,
    2026-09-06T18:50:49Z to 2026-09-19T15:05:38Z. Nineteen distinct pregame
    role states over 12.8 days is not yet enough to test a within-week role
    change, and now says so.
  - `GAP-INJURY-VINTAGE` -- 624 `injuries` PASS over 12 blobs; 566
    `official_injury_report` PASS over **546** distinct documents. The
    official report is where the real vintage depth is, because it
    republishes within the week.

  One gap surfaces today: `GAP-2026-PARTICIPATION`, as
  `ASSIGNED_PAST_HORIZON`, 4.4 days against its 2-day horizon, because the
  availability watch stopped. Assigned as OUT-019 and OUT-024.

  Tests: `nfl/tests/test_discovery.py`, 100 checks, 0 failing. The four new
  ones drive synthetic registries so they pin the RULE and not today's state
  -- including the pair that separates "looked today at 30-day-old evidence"
  (past horizon) from "looked 60 days ago at one-day-old evidence" (current).
  The old test asserted `'GAP-2026-PARTICIPATION' in stale`, which encoded the
  day rather than the rule, and is replaced.
- **commit**: see SUN-0 below; DISC-3 ships with it

## ID: SUN-0
- **priority**: 0
- **status**: DONE
- **dependencies**: none
- **description**: **Priority override, owner 2026-09-19: system-wide Sunday
  readiness.** Before anything else could be measured, establish which tree
  the capture actually writes to. I reported earlier in this session that no
  source was fresher than 39.7 hours and that the official status sources were
  98.3 hours old, and began writing that up as a readiness blocker. That was a
  measurement of a branch, not of the system.
- **blocker**: none
- **acceptance criteria**:
  - the freshness claim names the tree it was measured from;
  - capture evidence is ingested append-only with no seal rewritten;
  - the correction is recorded, not quietly dropped.
- **classification**: MEASUREMENT_DEFECT
- **ranking**: impact HIGH (every downstream readiness claim inherits it)
  x uncertainty LOW x measurability HIGH x EVI HIGH
- **result**: the scheduled capture has been healthy throughout, writing to
  the `capture-prod` branch since 2026-09-15T19:27Z (b9b6ff4). Measured on
  capture-prod at 763b776, the six core sources were last captured
  2026-09-19T15:05:38Z -- half an hour old, not four days. Merged into this
  branch as 8b8555b: 2,257 manifest lines appended in capture_id order with
  the common ancestor's 4,191 lines verified intact on BOTH sides first;
  2,878 blobs verified against their recorded sha256 with zero mismatches
  (2,103 before the merge, so 775 added and none broken); the same six
  pre-existing absent paths before and after; 150 of 150 board seals recompute.

  **This is the second time a stale ref has been read here as a dead
  executor** -- 2c0c36b had to withdraw "main stopped capturing on 09-11" for
  the same reason. The generalising rule, now in the registry's own
  `recheck_rule`: a freshness number means nothing unless it names the tree.

## ID: SUN-1
- **priority**: 1
- **status**: QUEUED
- **dependencies**: SUN-0
- **description**: The participation availability watch
  (`nfl-availability.yml`) last ran 2026-09-15T06:37:05Z and has not run
  since. It still pushes to `main` (lines 129-130) while the four capture
  workflows were moved to `capture-prod` twenty-two minutes after its last
  successful run. Point it at the governed surface, and get the run history
  read so "stopped" is distinguished from "failing at the push step".
- **blocker**: the Actions run log is not readable from this executor. Raised
  as OUT-024.
- **acceptance criteria**:
  - the workflow writes to the same branch as the surface it belongs to;
  - a fresh probe result for both URLs restates `GAP-2026-PARTICIPATION`
    inside its 2-day horizon;
  - the watch's own liveness is detectable without reading Actions.
- **classification**: MEASUREMENT_DEFECT
- **ranking**: impact MEDIUM (it buys provenance, not a feature -- these are
  postgame files and remain NOT_AUTHORIZED_BY_OWNER) x uncertainty LOW
  x measurability HIGH x EVI MEDIUM

## ID: SUN-2
- **priority**: 1
- **status**: BLOCKED
- **dependencies**: none
- **description**: `.github/workflows/nfl-t90.yml` is regenerated for week 2
  and correct on this branch. GitHub schedules workflows from the DEFAULT
  branch, so it changes nothing about what fires. It must be merged there
  before 2026-09-20T15:30Z.
- **blocker**: merging to the default branch is not available to this
  executor. Raised as OUT-026.
- **acceptance criteria**:
  - the six week-2 windows exist on the branch Actions schedules from;
  - `official_inactives` records a PASS with a game_id inside each window.
- **classification**: PRODUCTION_BLOCKER
- **ranking**: impact HIGH (the inactives file cannot be reconstructed after
  the window closes) x uncertainty LOW x measurability HIGH x EVI HIGH

## ID: SUN-3
- **priority**: 4
- **status**: QUEUED
- **dependencies**: none
- **description**: Three clubs -- JAX, CHI and NYG -- have an incomplete
  official injury report in our capture, and the appearance layer correctly
  refuses a club with no filed report. Cost on the week-2 slate: JAX deferred
  (15 players), CHI deferred (12), and NYG@LA halted entirely at appearance
  because NYG's 7 rows carry `report_status` unfilled on every one. The layer
  is right; the gap is the bytes.
- **blocker**: the reports are outside this checkout.
- **acceptance criteria**:
  - a filled report for the three clubs, or a recorded finding that the
    league did not publish one;
  - re-run shows non-QB coverage on all three games, or names why not.
- **classification**: PRODUCTION_BLOCKER
- **ranking**: impact HIGH (it is one whole game and two halves of the slate)
  x uncertainty LOW x measurability HIGH x EVI MEDIUM

## ID: SUN-4
- **priority**: 5
- **status**: QUEUED
- **dependencies**: none
- **description**: Opportunity conservation does not close exactly in every
  draw. Measured over the twelve fully covered week-2 games: targets close
  exactly in a median 81.2% of draws, carries in 77.5%, and the carry spread
  runs from 0.935 (PIT@NE) down to 0.030 (MIA@SF) and 0.035 (SEA@ARI). The
  discrepancy is ALWAYS a shortfall -- over-allocation fraction is exactly 0
  across all 14 games and both identities -- so this is unassigned mass, not
  impossible football.
- **blocker**: none
- **acceptance criteria**:
  - the shortfall is attributed to a declared residual or named a leak;
  - a game closing in 3% of draws is explained rather than averaged away;
  - no accounting is "repaired" by widening a tolerance.
- **classification**: MEASUREMENT_DEFECT
- **ranking**: impact MEDIUM-HIGH (every player share inherits it)
  x uncertainty MEDIUM x measurability HIGH x EVI MEDIUM-HIGH

## ID: SUN-5
- **priority**: 6
- **status**: BLOCKED
- **dependencies**: none
- **description**: `artifact_sealing` refuses every board of the 2026 season
  because `denom_panel.csv.gz` holds 3,230 rows from 202001 to 202518 and
  ZERO rows for 2026. `team_volume_history` reads the same file and is stale
  at 202518 against a required 202601; `denom_panel` is additionally
  BLOCKED-BY-DECLARATION on `CURRENT_SEASON_SOURCE_UNVERIFIED`. This is the
  single reason no Week-2 forecast can be sealed, under either configuration.
- **blocker**: no current-season source for the denominator panel has been
  established. `current_season_panel` did this for `panel_p3` and there is no
  sibling for the denominators.
- **acceptance criteria**:
  - a current-season denominator source with a declared clock, additive to
    the frozen panel exactly as CS1 is -- the frozen bytes are inside every
    sealed candidate's identity and must not move;
  - `check_all` returns PASS for all three inputs at 2026 week 2;
  - no threshold is loosened and `MAX_TRAIL_WEEKS` is not touched.
- **classification**: PRODUCTION_BLOCKER
- **ranking**: impact HIGHEST (it is the gate between a simulation and a
  board) x uncertainty MEDIUM x measurability HIGH x EVI HIGHEST

## ID: SUN-6
- **priority**: 7
- **status**: QUEUED
- **dependencies**: SUN-5
- **description**: `feature_build` is DEFERRED[STAGE_DECLARED_UNIMPLEMENTED]
  on all 15 reachable games: the accepted research baseline "prior-only,
  ordinal prefix cut" has no production implementation. It is declared as
  debt rather than reported as a forecast, which is right, and it is the
  second of the two blockers.
- **blocker**: none technical; it is unwritten.
- **acceptance criteria**:
  - the production implementation reproduces the research baseline on a
    fixture, checked rather than asserted;
  - it is not a stub that returns PASS.
- **classification**: PRODUCTION_BLOCKER
- **ranking**: impact HIGH x uncertainty LOW x measurability HIGH x EVI HIGH

## ID: SUN-7
- **priority**: 2
- **status**: BLOCKED
- **dependencies**: none
- **description**: **A rule the owner set was changed and this item exists to
  say so.** `nfl/tests/test_non_g0a_isolation.py` pins
  `G0A_IDENTITY = "SCHED-2a2924d4966fbd3d"` with the comment "Frozen by owner
  ruling until the event" -- it is the week-1 `nfl-t90.yml` schedule, and the
  window it protects carries the outstanding G0A `inactives` obligation, "the
  single item standing between G0A 11/12 and 12/12". Regenerating the workflow
  for week 2 (f9148b0) changed that identity to SCHED-5e2e890466c87284 and
  removed the week-1 crons, so five checks across three modules now fail:
  the two identity checks, and two in `test_capture_obligations` asserting
  that entries still exist inside the 2026-09-14 DEN@KC window and the
  2026-09-13 Sunday slate.

  The conflict is structural, not accidental: `nfl-t90.yml` is being used at
  once as a LIVE SCHEDULER and as a FROZEN RECORD of what was scheduled for
  week 1, and those two roles become incompatible the moment a second week
  arrives.
- **blocker**: OWNER DECISION. Changing a frozen identity is not this
  executor's to make. The week-2 regeneration is retained meanwhile because
  the alternative loses the 2026-09-20 inactives windows, which cannot be
  reconstructed, while the week-1 window it displaced closed eleven days ago
  and no cron can reopen it.
- **acceptance criteria**:
  - the owner rules on whether the freeze survives its event;
  - if it does, the record and the scheduler are separated so one file stops
    doing both jobs -- the frozen week-1 schedule preserved as an artifact,
    the live workflow free to advance;
  - **the five failing checks are NOT edited to match.** They are correctly
    reporting that a frozen value moved.
- **classification**: CRITICAL_CORRECTNESS
- **ranking**: impact HIGH (it is a governance freeze) x uncertainty LOW
  (the facts are unambiguous) x measurability HIGH x EVI HIGH

## ID: SUN-8
- **priority**: 9
- **status**: QUEUED
- **dependencies**: none
- **description**: Ingesting capture-prod moved two evidence censuses that
  `nfl/tests/test_inactives_substance.py` pins: uncredited game-anchored rows
  18 -> 20, and excluded landing pages 374 -> 382. The test says what to do --
  "if this drifts, D20 needs updating, not this test". Separately and more
  interesting: **48 of 50** captured pages carry the page's own empty-state
  sentence, so two do not. That is a content question about newly captured
  bytes, not a count.
- **blocker**: none
- **acceptance criteria**:
  - D20's census is updated from the manifest, not from the test;
  - the two pages without the empty-state sentence are read and classified
    before any count is adjusted around them.
- **classification**: MEASUREMENT_DEFECT
- **ranking**: impact LOW-MEDIUM x uncertainty MEDIUM (the two odd pages)
  x measurability HIGH x EVI MEDIUM

## ID: DFS-FS1
- **priority**: 8
- **status**: DONE
- **dependencies**: none
- **description**: A canonical, leakage-safe full-slate prediction-time
  dependence panel: mutually exclusive declared roles, prior-weeks-only
  labels, certified DK and FD scoring, Pearson and joint-tail dependence
  reported separately with game-clustered intervals.
- **blocker**: none
- **acceptance criteria**:
  - role labels re-derive from a history truncated strictly before their own
    week, checked rather than asserted;
  - no role collisions;
  - every point estimate carries a game-clustered interval;
  - DST pairs named NOT_MEASURABLE rather than omitted;
  - no coefficient reachable from production.
- **classification**: RESEARCH_BLOCKER
- **ranking**: impact HIGH (it is the validation target the world generator
  will be judged against) x uncertainty MEDIUM x measurability HIGH x EVI
  HIGH

## ID: DFS-FS2
- **priority**: 9
- **status**: BLOCKED
- **dependencies**: DFS-FS1
- **description**: Compare simulated dependence against the FS1 panel — sign
  and ordering of Pearson and of tail lift, separately, scored with the same
  certified adapters.
- **blocker**: no full-slate joint-world generator exists; the only sealed
  worlds are one single-game board. This is item A7 of the roadmap and it is
  football work, not DFS work.
- **acceptance criteria**:
  - magnitudes are NOT compared — history is one observation per game and a
    sealed board is many observations of one fixture;
  - a disagreement in sign is reported, never tuned away.
- **classification**: RESEARCH_BLOCKER

## ID: DISC-4
- **priority**: 8
- **status**: QUEUED
- **dependencies**: none
- **description**: `DEBT-RECV-CALIB` blocks promotion by its own declaration:
  receiving bias +2.18 yards, P(Y=0) predicted 0.3004 against 0.3293 actual,
  and all four pre-declared repairs failed their bar. Its named next action is
  a new pre-registration for a history-cohort centring family; R1 improved
  CRPS, MAE, r and PIT together but missed |bias| < 1.00.
- **blocker**: none — but it needs a new pre-registration, written before it
  is run, and it is a larger build than DISC-1 through DISC-3.
- **acceptance criteria**:
  - the pre-registration is committed before the family is fitted;
  - the reported over-coverage is treated as the zero-point-mass artifact the
    registry says it is, not as a width defect;
  - a failure to clear the bar is recorded as a measured negative.
- **classification**: PRODUCTION_BLOCKER
- **ranking**: impact HIGH (calibration is the GATE in the two-stage bar) x
  uncertainty MEDIUM (the defect is characterised) x measurability HIGH x EVI
  HIGH, but it is ranked below DISC-1..3 because those are cheaper and one of
  them governs a CRITICAL assumption

## ID: DISC-5
- **priority**: 13
- **status**: QUEUED
- **dependencies**: none
- **description**: The other promotion-blocking debts detected by
  `discovery.py`: `DEBT-JOINT-TARGETS`, `DEBT-SNAP-IMPOSSIBILITY`,
  `DEBT-HISTORICAL-VINTAGE`, `DEBT-TD-RECOVERABILITY`. Each declares
  `blocks_promotion` and names a next action.
- **blocker**: none — parked as a group deliberately
- **acceptance criteria**:
  - each is separated into its own item before work starts on it;
  - none is closed by weakening what it blocks.
- **classification**: NONBLOCKING_TECH_DEBT
- **ranking**: impact HIGH in aggregate x uncertainty MEDIUM x measurability
  MEDIUM x EVI MEDIUM. Parked because four items with one entry is not a plan,
  and splitting them before any is worked would be paperwork.

## ID: OAS1-TIEBREAK
- **priority**: 5
- **status**: BLOCKED
- **dependencies**: P9
- **description**: The OAS1 pre-registration declares `garbage_time` as a
  search axis and declares no tie-break for it, in either the original
  five-axis order or the amended three-axis one. Executing the selection left
  all three rules tied after the declared axes. A tie-break must be declared
  before the Week-2 candidate has a single identity.
- **blocker**: **owner decision, and it may not be taken by whoever has seen
  the scores.** The three variants' MAEs are now on the record
  (pass 1.159614 / 1.159721 / 1.159993 for A / none / B), so any rule written
  here is a selection rule written after seeing them — the exact thing the
  one-SE rule and the tie-break exist to prevent. The gap is pre-existing in
  the pre-registration, not introduced by amendment A1.
- **acceptance criteria**:
  - the tie-break is declared by someone who has not read the variant scores,
    or is declared on a ground that does not reference them;
  - it is committed before the Week-2 candidate is named;
  - the existing three-variant artifact is superseded, not rewritten.
- **classification**: RESEARCH_BLOCKER

## ID: OAS1-HURDLE
- **priority**: 6
- **status**: BLOCKED
- **dependencies**: P9
- **description**: Evaluate OAS1 against B5 and B4 (pass) and B5 with B3 as
  `POST_HOC_STRONGEST_BASELINE` (rush), clustered by game and by team.
- **blocker**: the captured 2026 play-by-play carries **week 1 only** — read
  from the file, 2,756 rows, zero at ordinal 202602. Scoring needs Week-2
  plays, which are bytes outside this checkout. **Assigned, not blocked for
  both agents**: the request is in `docs/AGENT_OUTBOX.md`. The candidate's unit
  strengths are committed before those bytes arrive, which is the position a
  hurdle test should be run from.
- **acceptance criteria**:
  - the Week-2 plays are captured with URL, retrieval time, `Last-Modified`
    and sha256;
  - the committed grader runs unchanged;
  - a negative result is recorded as a MEASURED NEGATIVE and B5 is used for the
    early-season opponent layer. No retuning until OAS1 wins.
- **classification**: RESEARCH_BLOCKER

## ID: OAS1-FLAT-SURFACE
- **priority**: 7
- **status**: QUEUED
- **dependencies**: P9
- **description**: All 864 configurations fall within one standard error of the
  best in both classes, so the pre-registered tie-break does 100% of the
  selecting and the data does none of it. The SE in the one-SE rule is the
  standard error of the mean ACROSS FOLDS, and fold-to-fold variation swamps
  configuration-to-configuration variation by roughly twenty to one. A PAIRED
  comparison — same folds, differenced per configuration — would have a far
  smaller standard error and might discriminate.
- **blocker**: none — but changing the rule is a change to the
  pre-registration and is a new pre-registration, not an edit to the old one.
- **acceptance criteria**:
  - the paired-SE alternative is pre-registered before it is run;
  - the existing result is not reinterpreted under the new rule;
  - if the surface is still flat under a paired SE, that is the finding and no
    further rule is tried.
- **classification**: MEASUREMENT_DEFECT

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

## ID: PRE-PORCELAIN
- **priority**: 11
- **status**: QUEUED
- **dependencies**: none
- **description**: `sportsplatform/governance/commit_claim.py` calls
  `git status --porcelain` and is the sole remaining offender of
  `test_determinism_proof.test_v_only_the_identity_module_reads_working_tree_state`.
  Pre-existing at `e050090` and at every baseline since. Named here rather
  than left inside a 61-item failing total, because P7's own generators joined
  that list for an hour and the only reason it was noticed is that the list is
  printed.
- **blocker**: none — deliberately low priority
- **acceptance criteria**:
  - the module reads working-tree state through `nfl/identity/code_identity`
    or states why it cannot;
  - the fix is not a widening of the rule's exemption list.
- **classification**: NONBLOCKING_TECH_DEBT

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
