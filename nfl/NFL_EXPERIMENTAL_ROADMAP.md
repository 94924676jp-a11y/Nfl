# NFL Experimental Roadmap (revised)

**Revision 2**, 2026-09-06, under owner Directive 2.
**Supersedes** revision 1 of the same date, which is preserved in git history.
**Status:** NFL-1 is authorised **only** after G0A passes. No broad predictive
implementation is authorised.

Changes in this revision, all owner-directed:
- **NFL-0 is split into G0A and G0B**, resolving a contradiction in revision 1.
- **G1 no longer requires beating r = 0.339.** It requires faithful reproduction
  of a reference baseline under a frozen implementation.
- **A Week-1 cold-start policy is a named prerequisite**, frozen before any 2026
  outcome exists.
- **2026 evaluation terminology is corrected** — fixed prospective holdout and
  sequential prospective evaluation are different things and revision 1 conflated
  them.
- **Power, pooled player r, the ffopportunity bracket and market timing are
  demoted** to planning-level or withdrawn pending measurement.

Order of work is unchanged and follows `CLAUDE.md`: make the experiment
trustworthy, then make the model intelligent, then prove the intelligence
survives unseen data, and only then let it influence money.

---

## The contradiction revision 1 contained

Revision 1's G0 required **≥2 weeks of reconciliation** before NFL-1 could begin,
while NFL-4 required predictions **sealed prospectively from Week 1**. Those
cannot both hold: waiting two weeks to satisfy the gate destroys the Week-1 and
Week-2 prospective evidence the gate exists to protect.

Governance that consumes the evidence it is protecting is a defect in the
governance, not an acceptable cost. The split below fixes it **without weakening
any control** — every G0 requirement survives, allocated to whichever gate it
actually belongs to.

---

## The clock that sits outside the phases

**Injury vintage capture is running and must not stop.** Accepted by the owner as
a justified exception to the research-only constraint: it is evidence
acquisition, not predictive production.

It is not gated on anything, because the data it captures is destroyed by
waiting: the archive keeps one row per player-week, the 2025+ schema carries no
clock, `injuries_2026.csv` is 404 as of 2026-09-06, and week 1 opens
**2026-09-09**. Cost of a missed week: ~132 bits of availability entropy and ~331
practice trajectories.

Outstanding on it, from the G0A audit: it is **not scheduled** and **not
kickoff-anchored**, and its raw blobs live outside git in an ephemeral container.
See `nfl/NFL_G0A_CHECKLIST.md`.

---

## G0A — Pre-kickoff integrity gate

**Must pass before any frozen predictive baseline may execute.**

Current state: **2 of 12 PASS**. Full audit with per-item evidence in
`nfl/NFL_G0A_CHECKLIST.md`.

| # | Requirement | State (2026-09-06) |
|---|---|---|
| 1 | Kickoff-anchored vintage capture scheduled and demonstrably running | FAIL — runs manually, no scheduler, no kickoff anchoring |
| 2 | Raw bytes before parse | PASS (durability unresolved) |
| 3 | Append-only / content-addressed storage | PASS (durability unresolved) |
| 4 | Complete five-clock provenance | FAIL — `effective_for_date` absent; `Provenance` never constructed or validated |
| 5 | sha256 of every consumed partition inside execution identity | FAIL — hashes recorded, no execution identity exists to hold them |
| 6 | Market / outcome / post-hoc leakage quarantine at ingest | FAIL — not implemented |
| 7 | Replay test that fails if quarantine is removed | FAIL — no NFL test exists |
| 8 | Denominator-aware non-null validation | FAIL — not implemented |
| 9 | Named `PFR_ID_UNMAPPED` failure with replay test | FAIL — not implemented |
| 10 | Draw-archive schema frozen, incl. `cross_game_dependence` | FAIL — prose, not a frozen artifact |
| 11 | `written_at` / `captured_at` / kickoff ordering enforced | FAIL — not implemented |
| 12 | Seal a forecast artifact immutably before kickoff | FAIL — not implemented |

**Nothing here is recorded DEFERRED.** DEFERRED means *not yet, and owed by
something specific*. These are unbuilt, and calling unbuilt work deferred is the
attractive lie Rule 001 exists to refuse.

**Exit gate G0A.** All twelve PASS, with items 7 and 9 demonstrated by tests that
**fail when the control is removed** — a quarantine with no test that breaks on
its deletion is not enforcement. That is the `assert_batch_games_are_new` lesson:
a guard that passed on every input it was ever given, because it read a field no
row carried.

---

## G0B — Evidence-system maturation gate

**Runs concurrently after G0A.** Nothing here blocks NFL-1; some of it may gate
promotion later.

| Requirement | Notes |
|---|---|
| ≥2 weeks vintage/archive reconciliation | Our captured `T-2d` vintage against the nflverse archive when it publishes |
| Reconciliation match rate | A **first-class reported metric**, not a log line. The archive row *is* the T-2d vintage (median 47.2h pre-kickoff), so we already know what it should equal |
| Owed-`DEFERRED` debt closure behaviour | Demonstrated end to end: `injuries` moves from `SOURCE_NOT_YET_PUBLISHED` to PASS when the season opens, and the debt closes rather than being forgotten |
| Operational monitoring | Missed captures are surfaced, not silently absent |
| Long-running source checks | Fit windows for `xpass`/`pass_oe` and the 31 model-derived columns (outbox §33 A2); anything else needing elapsed time |

**Exit gate G0B.** Reconciliation match rate reported for ≥2 weeks with
mismatches resolved rather than averaged, and at least one owed debt observed
closing.

---

## NFL-1 — the frozen control

**Begins after G0A.** Requires the cold-start policy below to be frozen first.

**G1 is corrected.** Revision 1 required the frozen baseline to beat r = 0.339.
That was wrong: 0.339 came from the shrunken season-to-date family itself, on
inspected data, so requiring the frozen implementation of substantially that same
family to beat its own exploratory result is either trivial or an invitation to
tune. **The baseline's job is to be a faithful, permanent control — not to win.**

| Work item | Detail |
|---|---|
| N1-0 | **Freeze the cold-start specification** (below) before any 2026 outcome exists |
| N1-1 | Reproduce the historical reference baseline under a **frozen implementation** |
| N1-2 | **Predeclare numerical reproduction tolerances** before running it |
| N1-3 | Produce the **complete linked scorecard** — r, SD ratio and calibration slope reported together, plus CRPS, PIT and coverage from stored draws |
| N1-4 | **Bit-identical rerun** under the same execution identity |
| N1-5 | Preserve permanently as the control. Name it when frozen; it does **not** inherit "M0" |

**Exit gate G1.** The frozen implementation reproduces the reference baseline
within predeclared tolerance, reruns bit-identically under the same execution
identity, has every input hashed inside that identity, and emits the full linked
scorecard. **Improvement is not required at this gate.**

**NFL-2 candidates — not NFL-1 itself — must demonstrate improvement over the
frozen NFL-1 control.**

---

## The Week-1 cold-start policy (prerequisite to NFL-1)

A season-to-date baseline is **undefined before any game is played**. Revision 1
did not address this, which would have left the Week-1 behaviour to be invented
at run time — i.e. after outcomes had begun to exist.

The policy must:
- use only information available **before the forecast timestamp**;
- be **deterministic** from its declared inputs;
- transition into season-to-date information by a **predeclared rule**;
- **never be retroactively revised after observing 2026 results.**

It may use prior-season and/or hierarchical league/team priors where justified by
backtest on completed seasons (2022–2025). Specification and supporting
measurement: `nfl/research/C3_COLD_START_SPEC.md`.

**FROZEN 2026-09-06T19:37:33Z**, spec sha256 `b356ecaa…9b9fa`, against `games.csv`
snapshot `c563178a…8fda9` verified to hold 272 REG rows for 2026 with 272 of 272
null results. Record: `nfl/NFL_COLDSTART_FREEZE.json`, corrected by appended
record `nfl/NFL_COLDSTART_FREEZE_CORRECTION_01.json` (the original is not
rewritten).

**Owner rulings, 2026-09-06, both closed:**
- **T1 — estimation window: retain the 2002 floor.** Not to be revisited after the
  first 2026 outcome. Scorecards were statistically indistinguishable; the shorter
  sample has materially less estimation stability and is dominated by the
  anomalous 2019–2020 home values. This is a frozen control, not a tuning exercise.
- **T3 — retain the frozen home term `h`.** Its incremental benefit is unresolved,
  but removing it now buys little and adds another discretionary change to an
  already frozen control. NFL-2 or later may test `h = 0` prospectively **against**
  the control.

---

## NFL-2 — opportunity first, skill second

Unchanged from revision 1 in substance. The ordering rests on the measured
result that opportunity is predictable and efficiency mostly is not — which the
owner has accepted as the working thesis while explicitly recording that it is
**an EXPERIMENTAL empirical finding, not a permanent architectural axiom.**
Future evidence may overturn it, and the roadmap must not be written so that it
cannot be overturned.

| Work item | Detail |
|---|---|
| N2-1 | Opportunity allocation model — snap / carry / target / pass-play-participation shares |
| N2-2 | Availability model: `P(active)` and `P(role \| active)` as a **distribution**, conditioned on the population established in `C1_AVAILABILITY_POPULATION_AUDIT.md` |
| N2-3 | Redistribution **inside** the allocation draw; flat-split prior, no within-position renormalisation |
| N2-4 | Skill conversion, shrunk hard. Constants estimated by game-level split-half over many random partitions — **not** imported from `v7/rates.py:220` |
| N2-5 | Rebuild the healthy-baseline construction forward-chained; as measured it is contemporaneous and is a Rule 003 leak |
| N2-6 | Defence enters as **scheme**, not outcome. Use `was_pressure`, never sack rate |
| N2-7 | Opponent adjustment shrunk by games played; off early — through ~week 5 the spread in schedules faced exceeds the entire true defensive spread |
| N2-8 | **No individual receiver-vs-defender term** — not identifiable in any reachable feed |

**Exit gate G2.** Opportunity forecast beats the persistence baseline by a
predeclared margin under date- and team-clustering, with metrics and multiplicity
hashed **before** the candidate runs. Skill-error and opportunity-error reported
**separately**. Improvement is measured against the **frozen NFL-1 control**.

---

## NFL-3 — the simulator

Unchanged. Game environment → drive model → play model, each gated.

**Exit gate G3.** Simulated **joint** behaviour matches held-out reality on
correlation structure — QB↔WR coupling, team pass/rush anti-correlation through
score state, zero-sum play split between opponents. Marginal calibration alone
does not pass this gate.

---

## NFL-4 — prospective evaluation

**The terminology is corrected twice.** Revision 1 called the season "a genuinely
untouched prospective window". Revision 2 replaced that with a two-way split —
which was **still too strong**, because the frozen transition `θ_g = g/(g+M)`
consumes 2026 results for every week after the first. **A frozen formula is not a
frozen information set.** Three arms, never pooled (full specification in
`nfl/NFL_EVALUATION_ARMS.md`):

| Arm | Specification frozen pre-2026 | Consumes 2026 outcomes | Strength |
|---|---|---|---|
| **A — static fixed prospective holdout** | yes | **never** | strongest untouched arm |
| **B — frozen-specification prequential** | yes | yes, by the pre-frozen rule only | strong prospective |
| **C — sequential adaptive** | no | yes | weakest |

**Only Arm A is a fixed holdout.** Arm B is prequential evidence and must be
described as such — the specification was untouched, the information set was not.
Arm C is anything revised after seeing 2026 results.

**Arm A is nearly free and is therefore kept:** it is the frozen specification
held at `g = 0` for the whole season, which sets `θ = 0` exactly and leaves only
the prior-season component. It introduces no new constant and re-parameterises
nothing. Its forecasts are identical in Week 1 and Week 18, it will lose to Arm B
on accuracy, and that is not its job — its job is to be the one arm whose result
cannot be explained by within-season adaptation.

**The A-vs-B contrast is worth more than either alone.** They share every
constant and differ only in whether the season's own results are consumed, so
their difference is a clean estimate of what the within-season update is actually
worth.

| Work item | Detail |
|---|---|
| N4-1 | Seal predictions before kickoff, every week, with complete execution identity |
| N4-2 | Run **Arm A** and **Arm B** side by side from Week 1; Arm A is the permanently frozen static holdout stream |
| N4-3 | Report the three arms separately and **never pool them**; arm membership is checkable from the seal ledger via `spec_sha256` |
| N4-4 | Forward-chained weekly evaluation; never random row splits |
| N4-5 | Clustered SEs by date and team. Refuse to emit a naive SE; carry the cluster count |

**Power is corrected, not merely demoted.** MLB's 7.93 is **not** promoted to an
NFL constant, and the "~2,000–3,000 game-equivalents / 7–11 seasons" figure is
**withdrawn as a unit error** — it multiplied a game count by a row-level design
effect measured on a calibration statistic, a defect
`v8/experiments/J2_STOPPING_RULE.md:47-52` had already recorded for MLB.

NFL clustering is now measured directly (`C2_POWER_AND_CLUSTERING.md`): the
design effect is a **function of rows per player-game** (0.83–1.12 at one row,
2.39 single-line, 7.12 laddered), and the **discrimination** DEFF is ~3.5×
smaller than the **calibration** DEFF on the same rows. Corrected planning
figures: **0.2–1.0 seasons** for broad receiving / anytime-TD, **2.3–5.9** for
QB/RB. These remain **planning-level DERIVED** — measured clustering, assumed
effect sizes — and the reported design effects are upper bounds.

**Exit gate G4.** A predeclared confirmatory comparison on sealed unseen weeks,
scored on the full scorecard, with the evaluation regime named.
**`DEFERRED / UNDERPOWERED` is the expected first answer and is not a failure.**

---

## NFL-5 — DFS and the market layer

Unchanged in structure; two claims are demoted.

**Player-baseline metrics.** The pooled **r = 0.5907** may **not** be used as a
promotion target on its own — pooled player results carry large between-player
variance. Any use must carry within-player or appropriately residualised metrics
alongside it.

**The ffopportunity bracket is not a gate.** The oracle-opportunity **r = 0.8419**
may not be used as a gate until outbox §33 **A3** confirms that the
expected-points field is genuinely oracle-opportunity **and establishes its
information set**. It currently rests on schema inference, not documentation.

**Market gate timing is corrected.** The "369 skill player-games" reasoning is
**withdrawn** — 369 was never per-market supply and the gate is per market.
Measured week-1 supply is 152 / 39 / 34 rows for `rec_yds` / `rush_yds` /
`pass_yds`. The binding constraint is **`min_distinct_dates = 10`**, a calendar
floor reached at week 3. "Fast" holds for 3 of 8 markets; `rush_yds` and
`pass_yds` need **8–11 weeks**.

**The 300 floor is not re-scaled.** `board_config.json` sets
`gate_floor_unit: "rows"` with a 2026-08-30 ruling assigning correlation to the
estimator rather than the floor. Applying a design effect to it would be a
reinterpretation contrary to an existing ruling, not a measurement.
`board_config.json` was not changed.

The **≥5-season trigger** statement remains **DEFERRED planning guidance only**,
until Hard Rock NFL market availability and actual eligible-play frequency are
measured (outbox §33 A4, A5).

`real_money.status` stays `NOT ENABLED`. `weekly_exposure_cap` stays `UNSET`.

---

## The freeze that has a 2026-09-09 deadline

Stated separately because it is the one time-critical decision in this revision,
and because it is **not** what revision 1 implied was time-critical.

Revision 1 implied the *baseline implementation* had to exist before Week 1. It
does not. What makes 2026 a **fixed prospective holdout** is that **the
specification was frozen before any 2026 outcome existed** — not that predictions
were executed pre-kickoff.

So if the cold-start and baseline specification is **frozen, hashed and committed
before 2026-09-09**, and is deterministic enough that execution adds no freedom,
it can be **executed after G0A passes** and the fixed-holdout property still
holds for every week it is applied to.

That converts an impossible three-day build into a document and a hash. It
weakens no control, requires no G0A item, and preserves the full season as a
fixed prospective holdout.

If the specification is **not** frozen in time, the cost is bounded and should be
stated rather than feared: the season degrades to **sequential prospective
evaluation**, which is weaker but not worthless, and Week 1 is 16 of 272 games.

---

## What would falsify the plan itself

Unchanged, and retained deliberately so the roadmap is not unfalsifiable.

1. **If opportunity is not forecastable** — if N2 cannot beat the persistence
   baseline — the central thesis is wrong and the oracle result is unreachable
   rather than merely unreached. The owner's framing of that thesis as
   EXPERIMENTAL rather than axiomatic is what keeps this outcome reportable.
2. **If the joint simulator's correlation does not beat independent marginals**
   on held-out games, the complexity is not paid for.
3. **If prospective 2026 results collapse to the MLB pattern** — calibration near
   nominal, discrimination near zero — the exploratory findings were selection
   effects on inspected data, and the correct response is to say so and stop, not
   to re-tune.

None of these is a reason to loosen a gate.
