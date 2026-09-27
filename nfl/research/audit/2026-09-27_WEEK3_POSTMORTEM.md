# Week 3 postmortem — why three Sundays exposed the same class of failure

Written 2026-09-27, after lock, before V1. Every number here was measured from the
repository at commit `88bcf80`, not recalled. Where I could not measure something I say so.

The instruction was not to defend the architecture and not to optimise for preserving prior
work. I have followed it. Several of my own artifacts are classified PREMATURE or
LOW-ROI below.

---

## 1. Executive summary

**The single finding.** The readiness gate was GREEN because it enumerated the components
that existed, not the components the product required. A gate built by listing what you
built cannot detect what you never built. That one property explains every other failure
below, including the regression guard I wrote today that reproduced the bug it was meant to
catch.

Three measurements carry the whole argument:

| measurement | value |
|---|--:|
| `pregame_readiness.py` mentions of "DST" or "position" | **0** |
| test files on governance / guards / audit / contracts / provenance | **51** |
| test files on projection / opportunity / efficiency / draws / simulation | **10** |
| the same ratio counting prior/role/usage/volume as projection work too | **53 : 20** |

A 5:1 ratio of assurance machinery to the thing being assured -- 2.65:1 even on the most
generous reading of what counts as projection work, which is the reading
`product_readiness.assurance_ratio` enforces so the rule fires only when the inversion is
undeniable. The project built an
excellent apparatus for proving that components behave, around a set of components that
did not include a projection for four of five rosterable positions.

**The second finding, which is the one that explains the recurrence.** The engine was
validated at a universe of **156 players**. The DraftKings product requires **457**. Every
GREEN row on the Thursday board — identity, depth charts, roles, opportunity, dossiers,
determinism — was true of a 156-player universe and silently untrue of the product. The
first test in this repository to reference 457 was written **today**.

**The third finding.** The Thursday readiness board for 2026-09-24 states, in its own
headline: *"the forecasting engine is closer to ready than the DFS operation is… What is
missing for Thursday is mostly operational — a daily workflow, a player board, a change
log, a classic optimizer — not model correctness."* That sentence was written on
2026-09-22 and it was wrong. Model correctness was exactly what was missing. The board had
15 GREEN rows and 1 RED row, and it reached a confident conclusion because none of its rows
asked the question that mattered.

---

## 2. Timeline of failures

1,184 commits in the 20 days from 2026-09-08, averaging 59 per day. High output, and the
distribution of that output is the problem.

| # | event | when | what actually happened |
|---|---|---|---|
| 1 | DK 457-player universe ingested correctly | W3 | Correct, and it worked. The universe is exactly right and matched the newest contest file with zero drift. |
| 2 | identity and post-inactives reconciliation became strong | W2→W3 | Also correct. 433 matched / 18 DST / 6 named unmatched; 20 availability states resolved with quoted provenance. This is the strongest part of the system. |
| 3 | large effort into governance, audits, evidence classification | W1→W3 | **2,711** file-changes under `nfl/research` against **151** under `nfl/dfs`. 51 assurance test files against 10 projection test files. |
| 4 | projection coverage incomplete across QB/RB/WR/TE/DST | all three | Measured today: **0** of 457 players had a proprietary projection before V0. |
| 5 | DST never implemented | all three | **0** files in the whole repository match `dst` or `defense` in 20 days of commits. Not "started and unfinished" — never begun. |
| 6 | proprietary projection blocked until minutes before lock | W3 | `player_draws` FAIL ← two layers `CONTRACT_DECLARED_LAYER_ABSENT` ← `participation_prior` BLOCKED ← a 404 feed. Diagnosed 2026-09-27, not earlier. |
| 7 | V0 created under extreme time pressure | 12:47–12:53 ET | ~10 minutes of specification. |
| 8 | V0 omitted player priors, role state, TD shrinkage, positional coverage | W3 | All four were knowable from the formula without data. |
| 9 | V0 produced stale replacement usage, starter haircuts, zero TDs, top-of-board underprojection | W3 | 19 stale-role players, 62 shrinkage violations, 9 zero-TD players, top-100 ratio 0.739. |
| 10 | the first level guard repeated V0's population-averaging mistake | W3, post-lock | Flat mean over 223 players gave ratio 0.901, inside band. The guard PASSED a board I had already called broken. |
| 11 | FC remained the numerical fallback | W3 | Correct outcome, wrong reason: it was a fallback by necessity, not by design. |
| 12 | Watson exposure driven by FC salary/value mechanics | W3 | 54.2% of lineups; FC value 4.55 pts/$1k, the highest on the slate; one independent support (a snap share every starting QB has). |
| 13 | lock-time awareness was wrong | W3 | I asserted kickoff had passed at 16:47Z from a stale 16:38Z reading instead of re-checking `date`. |
| 14 | foundational gaps still being discovered in the final minutes | W3 | The DST hole and the four V0 defects were all found after 12:00 ET. |

**The order matters.** Items 1 and 2 are genuine successes and they are not accidental —
they got attention. Items 4, 5 and 6 are the load-bearing product path and they got almost
none. That is a prioritisation outcome, not a technical accident.

---

## 3. Root-cause matrix

| # | failure | root causes (precise) |
|---|---|---|
| 3 | effort concentrated on assurance | **over-auditing / under-building**; **wrong development priority**; **unclear ownership of product-critical stages** — no one stage owned "a number exists for every rosterable player" |
| 4 | projection coverage incomplete | **missing architecture** (no receiving or rushing layer); **positional completeness failure**; **missing readiness gate** — the gate has no row for coverage |
| 5 | DST never implemented | **positional completeness failure**; **missing readiness gate**; **incorrect assumption** that a position with no player-level features needs no component. DST is the one position whose absence produces no error anywhere, so nothing complained |
| 6 | projection blocked until lock | **incomplete specification** — `participation_prior` was specified with a *single* arm that consumed a feed we do not control, so one 404 became a total block; **insufficient end-to-end testing**; **missing readiness gate** |
| 7 | V0 under time pressure | **insufficient pre-Sunday dry run**; **no explicit no-new-foundation window**; **wrong development priority** carried all the way to game day |
| 8/9 | V0's four defects | **projection-model failure** (population-mean shrinkage target); **role-model failure** (role state computed but never consumed); **cold-start failure** (no player prior, so a quiet sample erases a career); **incomplete specification** (TD rate as a raw two-game count); **insufficient historical validation** — none of the four would survive a forward-chained replay on 2025 |
| 10 | guard repeated the bug | **insufficient end-to-end testing**; **incorrect assumption** that a population mean represents the population that matters. Same mechanism as the defect it targeted |
| 12 | Watson concentration | **portfolio-construction failure** — construction optimised an external points-per-dollar ratio with no proprietary distribution to argue with it |
| 13 | lock-time error | **time-state failure** — I inferred a clock instead of reading one. A `date` call costs nothing |
| 14 | gaps found at the end | **missing readiness gate**; **insufficient pre-Sunday dry run**; **governance overhead** absorbing the capacity that would have found them |

**Two causes recur and they are the ones to fix.** *Missing readiness gate* appears five
times. *Wrong development priority* appears four times. Everything else is downstream of
those two.

---

## 4. Wasted-effort and premature-work accounting

Uncomfortable, as requested. None of this work is *wrong*; the question is whether it
earned its place ahead of a projection for four positions.

### LOAD-BEARING — keep, these carried the product

| work | why |
|---|---|
| DK universe / identity resolution | 457 rows exact, zero drift against the newest contest file. The foundation everything else joined to. |
| post-inactives availability + evidence tiers | The best component in the repo. 20 states resolved with quoted provenance, zero confirmed claims without a document. |
| observed-2026 layer | Measured usage across 482 of 518 player-weeks. This is what made V0 possible at all and what will make V1 correct. |
| `Outcome` governance type | Cheap, pervasive, and it genuinely prevents silent success. Earns its 2,455 lines. |
| redistribution trees | Right shape, right refusal, and they will be V1's priors. |
| FC firewall | Structural, proven both directions, and it cost one file. |

### IMPORTANT BUT SECONDARY — correct, but sequenced too early

| work | why |
|---|---|
| guard reachability census (91 guards classified) | Real value, but classifying guards ranks below having a projection to guard. |
| `baseline_diff.py` | Superseded by the semantic comparator within a day of being written. |
| fingerprint / sealing / determinism machinery | Excellent, and validated against a 156-player universe that is not the product. |
| defect ledger discipline | Genuinely useful; it caught five of my own stale claims. Keep the practice, reduce the volume. |

### PREMATURE — built ahead of its dependency

| work | why |
|---|---|
| **Q7 → Q8 → Q9 → Q9B → Q9P → Q9R (21 of 94 tasks, 22%)** | Six consecutive refinement families on the QB layer while RB, WR, TE and DST had **no layer**. 293 QB-path file-touches against **1** receiving and **0** DST. This is the single clearest misallocation in the project. |
| prospective ledger, CLV, market lifecycle scaffolding | Infrastructure for grading predictions that did not exist. |
| autonomy / orchestrator contracts | Automating a pipeline whose central stage refuses. |
| SGP pricing scoping | Explicitly blocked on shared-world semantics that are unbuilt. |

### LOW-ROI FOR CURRENT PRODUCT STAGE

| work | why |
|---|---|
| 51 assurance test files vs 10 projection test files | The ratio is inverted for a project whose projection path is empty. |
| repeated audit tooling (`*_audit.py`, `*_census.py`, `*_proof.py`) | Each defensible alone; collectively they are a second system maintained beside the first. |
| manifest / vintage churn (**1,793** file-changes under `nfl/vintage`) | Necessary plumbing, but an enormous share of total motion. |
| `SYSTEM_STATE.json` / `CURRENT_STATE.md` / `HANDOFF.md` / `WORK_QUEUE.md` regeneration | Four overlapping state documents. Status reporting became a workstream. |

### Should have received more priority

Receiving and rushing opportunity layers · player-level historical priors · role state as a
*consumed input* · **DST at all** · a coverage row in the readiness gate · a second
`participation_prior` arm so one 404 cannot block a slate · forward-chained replay on 2025
· a Saturday end-to-end rehearsal at the real 457 universe.

---

## 5. Load-bearing pieces still missing

| stage | state | what is missing |
|---|---|---|
| universe / identity | **GREEN** | nothing |
| availability | **GREEN** | complete enumerated inactive lists (OUT-035) |
| current role | **AMBER** | computed and *described*, never consumed by a projection |
| player prior | **RED** | does not exist. The gap that produced Chase at 7.82 |
| current usage | **GREEN** | nothing |
| team volume | **RED** | newest ordinal 202518 — an EWMA whose last observation is 2025 week 18. Flagged RED on 2026-09-22 and still RED |
| opportunity | **AMBER** | computable now without routes, at a stated cost |
| efficiency | **AMBER** | fields present; needs declared shrinkage to the existing multi-season panel |
| TD allocation | **RED** | raw two-game counts; produced 0.000 for a 26-target receiver |
| positional completeness | **RED** | DST absent entirely; K undefined |
| distribution | **RED** | means only. A floor and a ceiling are not a distribution |
| joint simulation | **RED** | nothing built. The largest remaining piece |
| fallback | **GREEN** | four-mode contract, built today |
| readiness gate | **RED** | exists, and cannot express positional coverage |

Five RED, three AMBER, three GREEN.

---

## 6. Why this recurred for three Sundays

**The gate enumerated components, not requirements.** `pregame_readiness.py` builds one row
per *declared layer*. A layer nobody wrote declares nothing, so it produces no row, so it
cannot be RED. **DST was invisible to the readiness matrix by construction** — not
overlooked, structurally unrepresentable. Three Sundays of GREEN boards were all honest
about the components that existed.

**The universe mismatch made every GREEN row locally true and globally irrelevant.** 156
validated, 457 required. Nothing compared the two until today.

**Local validation without chain validation.** The Thursday board already contained the
diagnosis, in its own RED row: *"Connecting player opportunity share did not connect team
volume."* That is exactly V0's failure mode and exactly my guard's failure mode — a
component fixed and verified in isolation while the chain it belongs to stayed broken. The
project has said this sentence about itself and did not generalise it.

**Which process controls existed:**

| control | existed? | why it did not help |
|---|---|---|
| slate-independent unit tests | **yes, 292 of them** | 51 on assurance, 10 on projection. They tested what was built |
| historical replay | **partially** — forward-chaining exists for QB arms | never run for RB/WR/TE/DST because those layers do not exist |
| Thursday dry run | **yes** — `THURSDAY_READINESS.md`, built 2026-09-22 | declared the engine ready and the gaps "operational". No coverage row |
| Saturday production rehearsal | **no** | nothing in the tree for it |
| Sunday-morning readiness gate | **partially** | `preflight_t90.py` exists; the T-90 cron covers Sept 9–15 only, so it cannot fire |
| no-new-foundation window before lock | **no** | I wrote a projection model at 12:47 PM ET |

So the honest answer is the worse one: **most of these controls existed and passed.** The
failure was not missing process. It was process pointed at the wrong question.

---

## 7. Regression-guard failure analysis

`assert_level_within_band` v1 took the mean of my projections over all 223 players with an
external counterpart and compared it to their mean. Ratio **0.901**, inside the declared
0.85–1.15 band. It PASSED a board I had already reported as broken.

| slice | ratio |
|---|--:|
| all 223 joined | **0.901** |
| salary ≥ $4,000 | 0.863 |
| salary ≥ $4,500 | 0.791 |
| top 100 by external projection | **0.739** |
| the players in the 48 lineups | **0.61** |

~80 low-salary players where both boards project two or three points and agree closely
diluted the mean until the failure disappeared. **That is the same mechanism as the defect
it was built to catch**: V0 shrank Chase toward a positional mean diluted by 40 reserves
under a 5% target share; my guard diluted the level check with the same kind of population.

**Why it happened.** I chose the validation population by convenience — "everyone I can
join" — instead of by relevance. Choosing the population is a modelling decision and I
treated it as a data-handling detail. The specific trap: for a *detector of
contributor-level failure*, a population containing mostly non-contributors has almost no
power.

**The principle that would have prevented it.** *Validate on the population the decision is
about, and on every stratum separately, never only on the pooled whole.* A board must not
be able to pass globally while failing catastrophically on the players who matter.
Permanent slices: starters · salary tiers · top-projection tiers · rostered players ·
high-opportunity players · role holders · **each position separately**.

This is the same statistical error the parent project already knows by another name: it is
why `board_config` demands clustered standard errors instead of pooled ones. Pooling across
heterogeneous units hides the units that matter. I made a governance-rule error, not a
coding error.

---

## 8. Permanent architecture changes

1. **The readiness gate becomes requirement-driven.** A declared list of required stages
   and positions, each of which must produce a row. A missing component is RED because
   nothing reported it, never absent because nothing declared it.
2. **Positional completeness is a first-class contract.** QB, RB, WR, TE, DST (and K when a
   surface needs it) each have: feature inputs, opportunity model, efficiency model, TD/RZ
   model, uncertainty model, cold-start path, fallback path, validation, calibration,
   failure behaviour. Any blank is RED.
3. **Role state becomes a consumed input,** not a descriptive field. Projection reads
   current role; an injury-replacement share expires when the starter is available.
4. **Every prior is a player prior first.** Population means are a last-resort fallback for
   true cold starts, and then the *role-holder* mean, never the whole-position mean.
5. **No single-arm dependency on an uncontrolled feed.** Any stage consuming an external
   source declares a second arm that does not. One 404 must never block a slate.
6. **Slice-based validation everywhere**, per §7.
7. **The validation universe is the product universe.** Tests run at 457, not 156.
8. **Fallback is designed, not improvised.** The four-mode contract built today becomes the
   permanent path.

---

## 9. Weekly operating cadence, with gates

Each gate is a command that returns PASS/FAIL. A FAIL stops the day's later work.

**MONDAY — grade and calibrate.** Grade last slate against actuals; per-position error
decomposition; calibration update; defect review.
→ `GATE_M`: last slate graded, every material miss attributed to a named layer.

**TUESDAY — model fixes and replay.** Fix what Monday attributed. Forward-chained replay on
prior seasons for every changed layer.
→ `GATE_T`: replay run, no changed layer worse than its predecessor on the declared metric.

**WEDNESDAY — completeness.** Positional coverage; cold-start tests; projection board dry
run on the *real* universe.
→ `GATE_W`: **every required position has non-zero proprietary or declared-fallback
coverage.** This is the gate that would have caught DST in Week 1.

**THURSDAY — first live board.** Full readiness matrix; slice-based level checks; coverage
report.
→ `GATE_TH`: readiness matrix has a row per required stage *and* per required position; all
slice level checks in band.

**FRIDAY — role and simulation.** Injury/role branches; simulation dry run; external
comparison.
→ `GATE_F`: role state demonstrably consumed (a returning starter changes his replacement's
projection); simulation reconciles player to team.

**SATURDAY — full rehearsal.** End-to-end production run; legal lineup export; fallback
path exercised deliberately.
→ `GATE_SA`: readiness GREEN, **or** explicitly `FALLBACK_READY` with the fallback tested.
Nothing else is permitted to pass.

**SUNDAY MORNING — refresh only.** News and inactives; re-run role trees, projections,
simulation, portfolio.
→ `GATE_SU`: every re-run completes on refreshed data with no code change.

**FINAL 90 MINUTES — frozen.** Data refresh, validation and controlled swaps only. No new
architecture, no new model, no new formula.
→ `GATE_LOCK`: the diff in the final 90 minutes touches no module under the projection,
simulation or portfolio paths.

`GATE_LOCK` is the one that would have stopped V0 from being written at 12:47 PM.

---

## 10. Stop-work rules

1. Any required position with zero proprietary **and** zero fallback coverage → **STOP all
   secondary development.** Coverage first.
2. Player distributions unavailable → **STOP portfolio sophistication.** No ownership
   model, no duplication estimate, no leverage work.
3. Role state not consumed by projections → **STOP projection calibration.** Calibrating a
   model that ignores who is starting is fitting noise.
4. Historical replay fails → **STOP promotion.** No version advances.
5. Saturday rehearsal not production-ready → **Sunday enters FALLBACK mode automatically.**
   Not a judgement call.
6. Any stage depending on a single uncontrolled external feed → **STOP** until a second arm
   is declared.
7. **New rule from today:** any *new* guard or validator must demonstrate a catch on a known
   bad artifact before it counts as a control. A guard that has never refused anything is
   not a control.
8. **Second new rule:** assurance work may not exceed the load-bearing work it assures.
   When the assurance-to-projection test ratio exceeds 2:1, assurance stops until the ratio
   recovers. It is currently 5:1.

---

## 11. V1 acceptance criteria — defined before writing V1

V1 shows no owner-facing number until all of these pass.

**Role and availability**
1. Current starter/backup/committee state read from the role layer and consumed.
2. A returning starter demonstrably invalidates his replacement's share — Lock/Darnold is
   the fixture.
3. Availability state consumed; no reported-absent player projected.

**Priors**
4. Player-level multi-season prior with declared recency weighting.
5. Cold-start fallback for no-history players, declared.
6. Shrinkage target is the player, then role-holders; the whole-position mean is never used
   for an established player.
7. No established role (observed share ≥ 0.18) projected below its observed share.

**Touchdowns**
8. TD expectation from a shrunk rate with a positional floor. No player with real volume
   carries 0.000.

**Coverage**
9. QB, RB, WR, TE, **DST** all covered. K declared.
10. Coverage reported per position with counts and provenance.

**Level and calibration**
11. Slice-based level checks in band: all, per position, salary tiers, top-50, top-100,
    role-holders, rostered.
12. No catastrophic high-salary or top-projection bias — top-100 slice within band.
13. Per-position calibration reported.

**Validation**
14. Forward-chained validation on prior seasons for every layer, no layer worse than its
    predecessor.
15. All seven `projection_guards` PASS.

**Output**
16. Mean, median and quantiles — not a mean alone.
17. Provenance on every projection: mode, source, timestamp, uncertainty treatment.

---

## 12. Work to delete, defer or demote

**Delete**
- `baseline_diff.py` as a football comparator — superseded; keep only if a DK-field differ
  is separately wanted, and rename it so it cannot be mistaken for one.
- Redundant state documents: collapse `SYSTEM_STATE.json`, `CURRENT_STATE.md`,
  `HANDOFF.md`, `WORK_QUEUE.md` into one. Four overlapping status surfaces is a workstream
  that produces no football.

**Defer until the projection path is GREEN**
- Autonomy / orchestrator expansion (A8), evidence-storage redesign (A10), CLV and market
  lifecycle (C2, C3), SGP (C5), explainability (C6), ownership/field model (C4a) — the last
  only until distributions exist, then it becomes urgent.
- Further QB refinement. Q9 is the most-refined component in a system with four unbuilt
  ones. **Freeze it.**

**Demote**
- New audit and census tooling: no new `*_audit.py` or `*_census.py` until the
  assurance-to-projection test ratio is under 2:1.
- Defect-ledger volume: keep the discipline, stop the prose.

---

## 13. Work to accelerate

1. **Receiving and rushing opportunity layers** — measured shares already exist.
2. **Player-level priors** — the multi-season panel already exists; it is not wired in.
3. **Role state as a consumed input** — the state already exists; nothing reads it.
4. **DST from zero** — the only position with no component at all.
5. **Second `participation_prior` arm** — one change unblocks four stages.
6. **TD rate with shrinkage and a floor.**
7. **Requirement-driven readiness gate with a coverage row.**
8. **Team volume refresh** — RED since 2026-09-22, ordinal still 202518.
9. **Saturday end-to-end rehearsal at 457.**
10. Then, and only then, the joint simulator.

---

## 14. Shortest path from here to a dependable product

**Stage 1 — make the gate honest (1 day).** Requirement-driven readiness with a row per
required stage and position. Run it and expect RED. This is first because without it every
later claim of progress is unverifiable.

**Stage 2 — coverage before quality (2–3 days).** Receiving and rushing layers on measured
shares; player priors wired from the existing panel; role state consumed; TD rate shrunk
with a floor; DST built. Crude but complete beats sophisticated but partial.

**Stage 3 — validate before showing (1–2 days).** Forward-chained replay per layer. All
seven guards PASS. Slice-based level checks in band. No owner-facing number before this.

**Stage 4 — distributions (2–3 days).** Quantiles, not means. This is the gate to everything
downstream: ownership, duplication and expected payout are all uncomputable without it.

**Stage 5 — joint simulation (the real project, weeks).** Shared latent game state with
within-draw reconciliation. Correlation emerges from football.

**Stage 6 — portfolio on our own distributions.** Candidate generation, ownership, joint
selection.

**The cadence runs from Stage 1 onward**, not after Stage 6. A Saturday rehearsal that
exercises a FALLBACK product is worth more than a Sunday that discovers a hole.

---

## What I would want said about my own conduct

Three things I got wrong today that are mine, not the architecture's:

1. **I wrote a projection model 13 minutes before lock.** No process forced that; I chose
   it. `GATE_LOCK` exists in §9 because I needed a rule I would not have to rely on my own
   judgement to follow.
2. **I reported a 39% deficit as a property of the board when it was a property of the
   lineup slice.** I ran the comparison before checking the level, which is backwards, and
   the level check costs one line.
3. **I built a detector that reproduced the bug it targeted**, then only found it because a
   test I wrote insisted the guard must fire on a known bad board. That test convention is
   the most valuable thing produced today and it is now stop-work rule 7.

The uncomfortable summary: the project has been unusually good at proving that what it
built works, and unusually bad at asking whether what it built is what the product needs.
Those are different questions, and only the second one produces a Sunday board.


---

## SUPERSEDED — owner ruling on sequencing, 2026-09-27

Section 14 of this postmortem put the ownership/field model ahead of fixing the proprietary
projections, on the reasoning that it is the only thing that can price diversification.
**The owner overruled that and the owner is right:**

> "I would not put the ownership/field model ahead of fixing the proprietary projections.
> The ownership model is important because it tells us what those 4.4 points of
> diversification are worth. But if the football projections underneath are still bad, then
> we would be optimizing contest strategy around the wrong player distributions."

That is the decisive argument. A field model built on top of V0-quality player numbers would
compute leverage against noise, and would do it convincingly enough to be trusted. The
binding order is now:

1. **V1 projections** — role state, player priors, TD priors, positional completeness, DST
2. **Search quality** — exact or near-exact solver, and it must recover or beat 171.59
3. **Ownership / field model** — then duplication and leverage become quantifiable
4. **Joint simulator** — then heuristic correlation rules are replaced by simulated football
5. **SIM_OPTIMAL** — only when 1 to 4 are real

This supersedes section 14's ordering. Sections 1 to 13 stand.

### Three distinct problems, no longer one

The other durable outcome of the frontier work is that "the model is bad" has resolved into
three separable failures with different owners and different fixes:

| problem | evidence | fix |
|---|---|---|
| **projection quality** | Chase 7.82 vs FC 27.08; 62 shrinkage violations; 9 zero-TD players; DST absent | V1, item 1 above |
| **search / optimizer quality** | the optimizer cannot find a lineup that provably EXISTS in a benchmark file on the same pool — 169.48 against 171.59 | item 2 above |
| **missing field / ownership model** | 4.4 points of diversification cost cannot be priced against duplication protection | item 3 above |

Lumping these together is what produced the wrong diagnosis on 2026-09-27, when a search
failure was reported as the cost of diversification.

### The benchmark is now a build gate

Owner ruling: *"Claude should treat that file as a minimum search-quality regression target
going forward. If a new optimizer cannot at least recover that quality on the same pool and
projections, it should fail the build."*

Implemented as `nfl/tools/search_quality_gate.py`, frozen against the placeholder file's
digest, comparing **unconstrained** so a deliberate diversification trade-off can never be
mistaken for a search defect. It is RED today by 2.11 points on the best lineup and 3.91 on
the portfolio mean, and it says in its own output that being red on the day it was written is
the point.
