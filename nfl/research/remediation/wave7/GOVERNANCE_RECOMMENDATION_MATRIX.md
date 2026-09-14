# Wave 7 — Governance recommendation matrix

**CODE CHANGED: NO. NO GOVERNANCE FILE EDITED. NOTHING APPLIED.**

This workstream produces a recommendation for an owner ruling. It does not make
one. No gate, threshold, policy file or governance artifact was modified. No
candidate was promoted, NFL-1 was not authorized, nothing is COMPLETE.

`nfl/research/PATH_C_STATE.json` was read and re-hashed to confirm it is
unchanged: sha16 `ebd1274086ec9c81`, identical to `WAVE0_BASELINE.json`
`artifact_sha16`.

Repo `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD `837d52f`. Interpreter `python3.12`. Written only under
`nfl/research/remediation/wave7/`.

---

## 0. Read this before the table

### 0.1 The matrix is written against the post-WS-D world

Six of the ten tokens below cannot be gated today at any level, for a reason
that has nothing to do with whether gating them is right: **the token does not
reach the gate**. `nfl/production/nonqb/layers.py` emits `governance=` evidence
and structured `warnings=`; `_nonqb_stage` (`run_forecast.py:908-914`) returns
neither; `StageResult` copies only `evidence['warnings']`; and a human then
retypes the governance state into a literal `spec_version` string at
`run_forecast.py:918-930`.

Verified on the sealed run
`nfl/research/live/2026_01_DAL_NYG/FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec/`:

```
team_environment     PASS  warnings=['known limitation: team_volume_is_near_unforecastable']
appearance           PASS  warnings=[]   spec='P3 appearance'
participation        PASS  warnings=[]   spec='Stage2 ewma_hl2; governance INFORMATION_CONSTRAINED'
targets_carries      PASS  warnings=[]   spec='P4C system C; governance DATA_BLOCKED'
conversion           PASS  warnings=[]   spec='RC1 baseline; SIGNAL_WEAK; governance HOLD_CHARACTERIZED + CALIBRATION_DEFECT'
td_layer             PASS  warnings=[]   spec='TD2 pooled positional control; governance HOLD_TENTATIVE'
```

`team_environment` carries its warning only because it takes a different code
path (`run_forecast.py:1079-1080`) that passes `warnings=`. Every other layer
raised warnings that the seal records as `[]`.

The two copies have already drifted, which is the proof that a retyped state is
not a state: `layers.SPEC['appearance']` (`layers.py:34-35`) reads
`appearance-p3-logistic-frozen; governance INFORMATION_CONSTRAINED`, while
`run_forecast.py:920` passes the literal `'P3 appearance'`. **Appearance's
governance token reaches neither `run_status.json` nor the board.**

So: every row marked **TRANSPORT-DEPENDENT** below is a recommendation whose
proposed level is unimplementable until WS-D lands the structured transport.
Until then those tokens are not at Level 1 by anyone's decision — they are at
Level 1 or Level 0 by accident of plumbing, which is a worse state than a
declared Level 1 because nobody chose it.

### 0.2 Scope doctrine, from WS15

WS15 established the distinction that governs the SCOPE column, and this matrix
uses it without amendment:

- **EVIDENCE-GAP refusal** — "I do not know X about unit U." The right scope is
  the scope of U. Narrowing it recovers real forecasts that were never in
  doubt. Over-scoping one of these is the measured defect WS15 costed at
  roughly 52 player distributions destroyed on clubs whose evidence was
  complete.
- **CONSTRUCTION-INVARIANT refusal** — an arithmetic identity that must hold by
  construction. One violated cell means the code that produced every other cell
  is wrong. **Must not be narrowed**, even when a single row is what tripped it.

Eight of the ten tokens below are EVIDENCE-GAP and are scoped to a metric or a
layer. Two — the HARD DEFERRED and HARD NOT_APPLICABLE rows — are
CONSTRUCTION-INVARIANT and are deliberately not narrowed.

### 0.3 Two things this matrix does not do

1. **No threshold is loosened anywhere in it.** An empty ranked table is a valid
   result. `rank_candidates` (`market_comparison.py:279`) already returns N rows
   and is never padded to ten; the honest consequence of §4.1 and §4.2 is that
   N becomes small or zero today, and that is the result, not a problem to
   engineer around.
2. **`team_volume_is_near_unforecastable` is not treated as a defect.** It is a
   declared limitation and it stays at Level 2. See §4.5, which also keeps it
   separate from `MODEL_VOLUME_BIAS` — a statement about the mean that WS07
   measured and did **not** support (z = +0.02, +0.07, +0.46).
3. **A green suite is never evidence for lowering a level.** `authorization.py`
   states there is *"no path from a green test suite to authorization"*, and
   WS16 §0 extends the same rule to health. No row below cites a passing test.

### 0.4 One correction to a fact I was handed

The brief states that WS07 upheld the team-volume limitation with "team volume
within 2–8% of its own oracle floor". **WS07 does not record that figure.** What
`WS07_TEAM_VOLUME.md` finding 10 records is `PARTIAL`: model r
0.327 / 0.319 / 0.266 for carries / targets / dropbacks against team-identity
ceilings √ω² of 0.315 / 0.383 / 0.337 — i.e. 104%, 83% and 79% of ceiling — with
the explicit caveat that the model CIs are wide at n = 20, so "at the ceiling"
is *consistent with* the data rather than demonstrated by it. WS07's own verdict
on the warning is "broadly confirmed and slightly overstated as phrased".

The conclusion the brief drew is unchanged and I endorse it: this is a declared
limitation, not a defect. But the number behind it is not 2–8%, and quoting it
as a measured margin would be quoting something that is not in the artifact.

---

## 1. The matrix

Levels are the five from `WS14_PUBLICATION_GATES.md` §3:
**L1** informational annotation · **L2** degradation warning (structured, not
consumed) · **L3** ranking gate (visible, unranked) · **L4** metric/publication
gate (absent by name, refusal recorded) · **L5** hard refusal (run does not
seal).

| # | TOKEN | CURRENT SOURCE | CURRENT EFFECT | PROPOSED LEVEL | SCOPE | RATIONALE | FALSE-POSITIVE RISK | WHAT EVIDENCE CLEARS IT |
|---|---|---|---|---|---|---|---|---|
| 1 | `INFORMATION_CONSTRAINED` | `PATH_C_STATE.subsystems.appearance.action`; `layers.SPEC['appearance'/'participation']` | **L1 for participation** (literal reaches `spec_version`); **L0 for appearance** — token dropped entirely at `run_forecast.py:920` | **L3 RANKING GATE** | **Metric-scoped**, propagated by `eligibility.REQUIRED_INPUTS`: appearance + participation, and the metrics declared to consume them | EVIDENCE-GAP: an information ceiling is not a defect and the forecast under it is honest. But `rank_candidates` orders by model-vs-book disagreement, and a wide honest distribution manufactures large gaps that are width artefacts. Rank ordering is the thing to refuse, not the number. | **LOW-MODERATE.** No number is suppressed; the row stays visible. Risk is that today this empties the ranked table for every non-QB metric. That is the honest result, not a false positive — but the owner must accept it before the ruling, not after. | `PATH_C_STATE.subsystems.appearance.action` moving to `PROSPECTIVELY_VALIDATED` or `PROMOTED` on a preregistered out-of-sample appearance study. Separately: the WS04 leak evidence (`presence_bit_alone_auc 0.6425`; served week-1 mean p 0.7996 against in-sample 0.5438) is a **different** open question and does not clear here. |
| 2 | `DATA_BLOCKED` | `PATH_C_STATE.subsystems.target_allocation.action`, `knowledge: UNEXPLORED`; `layers.SPEC['targets_carries']` | **L1** — literal at `run_forecast.py:924`. Meanwhile `metrics.py` marks `receiving/targets`, `receiving/receptions`, `rushing/carries` **`MODELED`**, the system's top status | **L3 RANKING GATE**, plus the `metrics.py` status demoted `MODELED → PROVISIONAL` (an L1/L2 label change, not a gate) | **Metric-scoped** to the metrics `targets_carries` produces, propagated to metrics drawn from them | EVIDENCE-GAP. This is WS23 C1 in one cell: `MODELED` is defined as *"a governed layer produced a full distribution"*, and the governance artifact that `eligibility.py:1` declares authoritative records this layer `DATA_BLOCKED` / `UNEXPLORED`, `production_role None`, `publication_eligible False`. A subsystem never explored is presented to a reader as cleanly as one that was. | **LOW at L3. HIGH at L4** — and L4 is why the token's name is dangerous. `DATA_BLOCKED` here means *"knowledge UNEXPLORED, blocked on participation adequacy"*, **not** "the layer could not run". The layer ran and produced draws. Reading the word as a hard-refusal trigger would suppress computed numbers. | `target_allocation.knowledge` moving off `UNEXPLORED` with the named upstream blocker (participation adequacy) discharged, and the action reaching a `PRODUCTION_ACTIONS` value. Until then, demotion to `PROVISIONAL` is a statement of fact, not a penalty. |
| 3 | `SIGNAL_WEAK` | **No governance-artifact home.** Layer-authored free text: `layers.py:39,53,401,470`; `metrics.py:69` caveat; `run_forecast.py:926`. `PATH_C_STATE.receiving_conversion.action` is `HOLD_CHARACTERIZED`, not `SIGNAL_WEAK` | **L2** — reaches the reader as the `*` caveat on Receiving yards. As a structured warning (`layers.py:470`) it is dropped | **L3 RANKING GATE** + register the token in `PATH_C_STATE` so it is derivable rather than authored | **Metric-scoped** to the metrics RC1 produces: `receiving/receiving_yards`, `receiving/receptions` | EVIDENCE-GAP. RC1 recovers **4.89%** of the conversion oracle = 0.96% of baseline CRPS; prior-to-next-game conversion r = **0.083** against opportunity r = **0.591**. A weak honest signal is a legitimate forecast. Ordering it by disagreement gap orders noise. | **LOW.** The row is published with its caveat. The residual risk is the reverse one: leaving it at L2 lets a near-zero-skill layer occupy the top of a disagreement ranking. | A preregistered forward-chained out-of-sample study showing the conversion ladder materially beats the opportunity-only control, **scored by composition into receiving yards, never on the primitive** (RC1-LESSON-PRIMITIVE-REVERSAL), clustered by game. |
| 4 | `CALIBRATION_DEFECT` | `PATH_C_STATE.subsystems.receiving_baseline_calibration.action`, `knowledge: BASELINED`; `layers.py:466` `governance=`, `layers.py:472` warning | **L1/L2** — inside the `metrics.py:69` caveat string and the `run_forecast.py:926` literal. Both structured copies discarded by `_nonqb_stage` | **L4 METRIC / PUBLICATION GATE** — *with the reservation in §4.4*; **L3** is the defensible fallback | **Metric-scoped** to the metrics the RC1 receiving baseline produces. **Explicitly NOT board-scoped** — it must not destroy QB rows | The only token here that says *the emitted number is measurably wrong in a named direction*, rather than *we know little*. The downstream consumer computes `P(over line)` from the draws and compares to a de-vigged price; a declared directional bias yields a systematically wrong probability and therefore a systematically wrong disagreement. Calibration is the gate. | **MODERATE-TO-HIGH, and higher than WS14 assessed.** See §4.4: the development evidence is bias **+2.18** yards (over-prediction); the live artifact `MODEL_HEALTH_2026-09-13.json` records `receiving/receiving_yards` `mean_signed_error` **−2.5197** (under-prediction) on n=48. **The two measurements disagree in sign.** The over-coverage half of the defect is in the conservative direction. An L4 built on a bias whose sign is not stable is a gate built on an unreplicated number. | A preregistered bias-and-width study of the receiving baseline on forward-chained 2026 weeks, clustered by game, with a declared equivalence margin and a TOST — reporting the sign and magnitude on **out-of-sample** rows, not development rows. `PATH_C_STATE` already declares the reopen condition as "materially new INFORMATION". |
| 5 | `team_volume_is_near_unforecastable` | `team_volume_v1.KNOWN_LIMITATIONS` (`team_volume_v1.py:62`) | **L2** — the **only** token in this matrix that reaches `run_status.stages[].warnings` as structured data (verified above) | **L2, UNCHANGED.** Propagate as annotation to derived metrics; **do not gate** | **Layer-scoped annotation**, propagated to the metrics that consume team volume | **This is a declared limitation, not a defect, and the two are different kinds of object.** Its own policy — *"reported on every run, never presented as skill"*, *"these draws are honest about that width; they do not narrow it"* — is correct. WS07: the layer beats climatology on CRPS on all four quantities and sits at or near the team-identity ceiling on three. Keep strictly separate from `MODEL_VOLUME_BIAS`, which WS07 measured and did **not** support. | **HIGH if raised.** Gating on it would punish an honestly wide forecast for being honest, on a layer measured to be at its own ceiling — the exact inference that manufactures defects for any forecaster including a correct one. Leaving it at L2 carries the smaller risk that inherited team-volume width propagates into disagreement rankings; §4.5 handles that by annotation, not by a gate. | Nothing "clears" a declared limitation. What would **change** it is a genuinely new informative input demonstrated out-of-sample. WS07 names the one place with real headroom: PLAYS sits at r = 0.000 against a ceiling of 0.221 because `league_mean` encodes no team identity. That is an improvement target, not a gate release. |
| 6 | `PARTIAL_PLAYER_COVERAGE` | `run_forecast._completeness` (~`:1434`); a lawful value of `artifact.COMPLETENESS`; this run `absent_layers: ['feature_build']` | **L2** on the product side (`data_status` column); **L5-equivalent inside the promotion path** — `q9shadow.ledger.BLOCKERS['COMPLETE_ARTIFACT_LAYERS_ABSENT']`, `promotion_gate()` refuses with no override, but is imported only by q9shadow and its tests | **L2 for publication of rows, UNCHANGED.** **L4 board-scoped for any completeness *claim*** — it must gate the word, not the rows. Plus render `completeness` and `absent_layers` in `BOARD.md`, which currently prints neither | **Row-level: scoped to the absent units.** Claim-level: board-scoped | EVIDENCE-GAP, and the textbook case for narrowing: the players who **were** modelled are modelled properly. It describes coverage, not correctness. What it must gate is the assertion that the board is complete. | **LOW as proposed. HIGH if raised to a board refusal** — that is precisely the over-scoping WS15 measured, destroying correct forecasts for covered players. | `absent_layers` empty for a run; or the absent layer declared `NOT_APPLICABLE` to this run's scope **with a reason**, rather than `feature_build` reporting `PASS` under code `STAGE_DECLARED_UNIMPLEMENTED`. |
| 7 | `NONQB_LAYERS_UNAVAILABLE` | DIAGNOSTIC verdict, `run_forecast.py:1512`; in the sealed artifact naming `['feature_build']` | **L2** — recorded in `accounting_verdicts`, named in the sealing detail. DIAGNOSTIC never gates, by design (`artifact.py:113`) | **L2, UNCHANGED.** One L1 change: the **state word**. A DIAGNOSTIC verdict whose state is `FAIL` while its class by design never gates teaches a reader that FAIL is survivable | **Layer-named annotation.** Same fact as row 6, with the layer named | The DIAGNOSTIC classification is correct and `artifact.py:236-242` argues it soundly: a layer blocked on a feed is a coverage fact, not an accounting violation. The defect here is vocabulary, not level. | **VERY HIGH if raised to L5** — it would refuse every run in which any layer is absent, which is every run in the tree today. **NIL** for the proposed vocabulary change: it alters no branch. | The named layers producing output, or being declared `NOT_APPLICABLE` for this run's declared scope. |
| 8 | `QB3_WEEK1_SEASON_BOUNDARY` | `qb_allocation.py:183` → `run_status.qb3_configuration` → `board.json` → `forecast_stage.qb_metric_blockers` (`:129`) → `market_comparison.py:430-444` | **L4 already, metric-scoped, and working.** The one chain in the repository that keeps the defect a typed field from origin to gate. Fails closed at `forecast_stage.py:158-170` when the board cannot answer | **L4, NO CHANGE.** Two additive recommendations, neither of which touches the gate: (a) render it in `BOARD.md`, which never mentions QB3; (b) give the fail-closed path a **distinct code** | **Metric-scoped to `qb/*`.** Correct as built | It is a SPECIFICATION fact, and `forecast_stage.py:134-149` reasons about it explicitly: ingesting an inactive list does not repair a cell definition, so it does not clear at POST. This is the model the other tokens should copy. | **REAL, and currently invisible.** `_derived_week1_blocker` returns the blocker on an unparseable `game_id`, an import failure, absent `teams`, or any exception. A **non**-week-1 board can therefore be blocked for a reason unrelated to a season boundary, and the emitted code says "week 1 boundary". The conservative direction is right; the **name** is wrong in that branch. Splitting the code separates "measured defect" from "could not establish" and loosens nothing. | It clears structurally at week 2+, when the incumbent signal is within-season — `qb3_configuration[team].week1_specification_defect` false for both rooms. Within a season-opener room, nothing clears it, by design. |
| 9 | **HARD `DEFERRED`** | `HARD_REFUSING_STATES = ('FAIL','BLOCKED')` at `artifact.py:115`; this run `qb_cross_layer_reconciliation` / `CROSS_LAYER_RECONCILIATION_NOT_RUN` | **L2** — seals, recorded in `hard_owed`, named in the detail string. Reproduced independently: all 12 HARD `DEFERRED` → `PASS HARD_INVARIANTS_HOLD` | **L2 at the seal, UNCHANGED** (see §4.9). **L4 board-scoped at the publication boundary** and at the promotion-evidence boundary. Plus an **L5 bound** on the count of unevaluated HARD invariants, **declared relative to run scope, never as a fitted number** | **CONSTRUCTION-INVARIANT. NOT NARROWABLE.** `qb_cross_layer_reconciliation` asserts team passing yards == player receiving yards on the same draw index — the same quantity counted twice. If it is unevaluated, nothing establishes that the numbers describe one football game, and narrowing the consequence to the receiving rows would hide it in the QB rows | Sealing is right: the debt is recorded honestly with an `owed` payload naming the blocking stage, and the artifact **is** the record. Publishing is different: a board offered to a reader while a construction identity was never checked is a claim the artifact does not support. The latent hole is real and separate — an artifact with **no** hard invariant evaluated returns `PASS HARD_INVARIANTS_HOLD`. | **HIGH if the L5 bound is implemented as a count.** A legitimately QB-only run cannot evaluate a receiving invariant; an absolute count would refuse it. **The bound must be scope-relative** — every HARD invariant applicable to the layers this run declares — and it must be derived, not chosen. Setting `MIN_HARD_EVALUATED = 11` because today's run evaluates 11 would be fitting a constant to the data, which this project logs as a bug rather than a tuning. | For the specific DEFERRED: the receiving draw set supplied to the run and the reconciliation evaluated. For the bound: an owner ruling declaring what "applicable to this run's scope" means, written before any run is measured against it. |
| 10 | **HARD `NOT_APPLICABLE`** | Same exclusion from `HARD_REFUSING_STATES`; anticipated explicitly at `artifact.py:344-351` and answered by counting and naming rather than refusing | **L2** — counted into `hard_not_applicable`, named in the detail. Reproduced: all 12 HARD `NOT_APPLICABLE` → `PASS HARD_INVARIANTS_HOLD` | **L2 when justified. L5 when unjustified** — refuse when an invariant is marked `NOT_APPLICABLE` while the layers it depends on **are present** in the run's manifest. Additionally require a `not_applicable_because` payload, mirroring the `owed` payload DEFERRED already carries (`artifact.py:281-283`) | **CONSTRUCTION-INVARIANT. NOT NARROWABLE.** An unjustified `NOT_APPLICABLE` means the run's **scope declaration** is wrong, and the scope declaration is what produced every other cell's applicability | **`NOT_APPLICABLE` and `DEFERRED` are different in kind and must not share a level.** DEFERRED says *"this applies to this run and was not evaluated; here is the debt"*. NOT_APPLICABLE says *"this does not apply to this run's scope"* — and that is **self-asserted by the run about itself, with no independent check**. A run that silently dropped the receiving layer and marked the cross-layer invariant NOT_APPLICABLE reads identically to a run that never had one. DEFERRED at least carries a payload. | **LOW as proposed**, because the trigger is a contradiction rather than a judgement: an invariant declared inapplicable while its required layer is in the manifest is an internal inconsistency, not a close call. **HIGH if implemented as a count bound** — same failure as row 9. | Nothing needs to "clear" a justified NOT_APPLICABLE; it is a lawful answer and `artifact.py` is right to say so. What the proposal asks for is that the justification be **recorded and checkable** rather than asserted. |

---

## 2. Transport dependency on WS-D

WS-D is repairing `_nonqb_stage` (`run_forecast.py:908-914`) so that layer
`warnings` and `governance` survive into `StageResult` instead of being dropped
and retyped as prose.

| Row | Token | Transport-dependent? | Why |
|---|---|---|---|
| 1 | `INFORMATION_CONSTRAINED` | **YES — hard blocker** | For appearance the token does not reach the seal at all (`'P3 appearance'`). There is nothing at the gate to branch on. |
| 2 | `DATA_BLOCKED` | **YES** | Reaches the seal only inside an English `spec_version` string that nothing parses. The alternative path — calling `eligibility.matrix()` at board-build time — does not require WS-D and is noted in §4.2. |
| 3 | `SIGNAL_WEAK` | **YES, doubly** | Dropped by the transport **and** absent from `PATH_C_STATE`, so even a repaired transport carries a layer-authored string rather than a governance state. Needs both. |
| 4 | `CALIBRATION_DEFECT` | **YES — hard blocker** | `layers.py:466` `governance=` and `layers.py:472` warning are the structured origin, and both are discarded. The `PATH_C_STATE` subsystem entry is a second, transport-independent route (§4.4). |
| 5 | `team_volume_is_near_unforecastable` | **NO** | Already arrives as structured data via `run_forecast.py:1079-1080`. It is the existence proof that the transport repair is sufficient — the other layers differ only in code path. |
| 6 | `PARTIAL_PLAYER_COVERAGE` | **NO** | Already structured on `run_status.json` and `forecast_artifact.json`. |
| 7 | `NONQB_LAYERS_UNAVAILABLE` | **NO** | Already a structured verdict in `accounting_verdicts`. |
| 8 | `QB3_WEEK1_SEASON_BOUNDARY` | **NO** | Typed field end to end already. |
| 9 | HARD `DEFERRED` | **NO** | Lives entirely inside `artifact.py`. |
| 10 | HARD `NOT_APPLICABLE` | **NO** | Same. |

**Four rows blocked, six not.** The four blocked are rows 1–4 — which are
exactly the four governance tokens. That is not a coincidence: the transport gap
*is* the reason governance has no path to the gate, and the seal's own
`"warnings": []` on four layers that raised warnings is the evidence.

One consequence worth stating plainly: **until WS-D lands, a ruling on rows 1–4
is a ruling that cannot be implemented.** It is still worth taking, because the
ruling determines what WS-D's output should be wired *to*, and wiring built
before the ruling would be someone choosing the policy by choosing the plumbing.

---

## 3. The DEFERRED / NOT_APPLICABLE adjudication

Rows 9 and 10 are the subtlest and share a mechanism, so the reasoning is set
out once, here.

### 3.1 What was measured

```
python3.12, HEAD 837d52f, nfl.prospective.artifact.assert_hard_invariants
n_hard = 12, n_diagnostic = 3, HARD_REFUSING_STATES = ('FAIL', 'BLOCKED')

ALL HARD PASS             -> PASS  HARD_INVARIANTS_HOLD
ALL HARD DEFERRED         -> PASS  HARD_INVARIANTS_HOLD
ALL HARD NOT_APPLICABLE   -> PASS  HARD_INVARIANTS_HOLD
ALL HARD BLOCKED          -> FAIL  HARD_INVARIANT_FAILED
ALL HARD FAIL             -> FAIL  HARD_INVARIANT_FAILED
ALL DIAGNOSTIC FAIL       -> PASS  HARD_INVARIANTS_HOLD
```

This reproduces WS14 §2.2 independently. It is a **latent** hole: no artifact in
the tree is in the all-DEFERRED or all-NOT_APPLICABLE state. The sealed run
evaluates 11 of 12.

### 3.2 The design intent is correct and should be preserved

`artifact.py:105-115` is explicit and it is right:

> `BLOCKED` the invariant could not be evaluated. A check that did not run has
> not passed, and this project has been bitten by treating the two the same.
> `DEFERRED` is different: it is an explicit, recorded debt with an `owed`
> payload, and it is carried into the artifact rather than silently cleared.

Verified on the sealed run: the DEFERRED verdict does carry `owed`, naming
`blocking_stage: 'conversion (RC1 baseline; SIGNAL_WEAK)'`. The debt is real and
recorded, not a label.

**So DEFERRED should not refuse the seal.** Refusing would destroy the record of
the debt in order to object to the debt. `artifact.py:344-351` makes the same
choice for NOT_APPLICABLE and states the hazard it is accepting in a comment —
*"otherwise an artifact could mark every hard invariant NOT_APPLICABLE and its
verdict would read exactly like a clean run"*.

### 3.3 Where the two states diverge, and why they get different levels

| | HARD `DEFERRED` | HARD `NOT_APPLICABLE` |
|---|---|---|
| Claim | "This applies to this run and was not evaluated" | "This does not apply to this run's scope" |
| Carries a payload | **Yes** — `owed`, set at `artifact.py:281-283` | **No** |
| Who asserts it | The run, about a measurement it owes | The run, **about its own scope** |
| Independently checkable today | Partly — `owed` names the blocking stage | **No** |
| Failure mode | A debt is carried forever and quietly normalised | A dropped layer is indistinguishable from a layer that never existed |

That asymmetry is the whole adjudication. DEFERRED is an **honest admission**
and the right response is to stop it being *published* while it stands, not to
stop it being *recorded*. NOT_APPLICABLE is a **self-certification** and the
right response is to make it checkable.

### 3.4 The adjudication

- **HARD `DEFERRED` → L2 at the seal (unchanged); L4 board-scoped at the
  publication boundary and at the promotion-evidence boundary.** A sealed
  artifact carrying a HARD DEFERRED may exist and is the correct record. It may
  not be published, and it may not be evidence for promotion. Note the promotion
  half is already implemented and already refuses —
  `q9shadow.ledger.promotion_gate()` blocks with no override — but it is
  imported only by q9shadow and its tests, never by `run_forecast`, `board` or
  `market_comparison`.
- **HARD `NOT_APPLICABLE` → L2 when justified; L5 when unjustified.** The L5
  trigger is a contradiction, not a threshold: an invariant declared
  inapplicable while the layers it depends on are present in the run's manifest.
  Plus a required `not_applicable_because` payload, mirroring `owed`.
- **Neither may be given a count-based bound as its primary mechanism.** A count
  is a silent constant unless it is derived from the run's declared scope, and a
  count chosen so that today's 11-of-12 run passes is a constant fitted to the
  data.
- **Scope: CONSTRUCTION-INVARIANT for both. Not narrowable.** Per WS15, a
  refusal triggered by an arithmetic identity that must hold by construction
  must not be scoped down to the offending row, because narrowing it hides the
  defect in the rows it did not narrow. `qb_cross_layer_reconciliation` —
  "these are the same quantity counted twice; disagreement is arithmetic, not
  disagreement about football" — is exactly that kind of invariant.

### 3.5 What this adjudication does not claim

It does not claim the current behaviour is a defect that has fired. It has not.
It is a latent hole demonstrated on seeded inputs, and the honest statement is
that the gate is **under-specified for states no artifact has yet occupied**.
That is a good time to rule on it, not evidence that something went wrong.

---

## 4. Per-row detail where the table cell is too small

### 4.1 INFORMATION_CONSTRAINED — the propagation question

`eligibility.REQUIRED_INPUTS` already declares the dependency chain:
`targets_carries` needs `appearance output (availability A)` and
`participation share point forecast C`. So an L3 on appearance propagates to
targets, carries, receptions, receiving yards and the TD metrics.

The owner should know the size of that before ruling: **it is every non-QB
metric.** `eligibility.matrix()`, run on this checkout, returns
`allowed_runtime_role: REHEARSAL_ONLY` for all ten pipeline layers — including
`qb_layer` (`OWNER_BASELINE_SELECTION`) and `qb_allocation` (`CANDIDATE`). So a
strict reading propagates to the QB metrics as well.

```
team_environment      team_volume            HOLD_CHARACTERIZED       REHEARSAL_ONLY
appearance            appearance             INFORMATION_CONSTRAINED  REHEARSAL_ONLY
participation         appearance             INFORMATION_CONSTRAINED  REHEARSAL_ONLY
targets_carries       target_allocation      DATA_BLOCKED             REHEARSAL_ONLY
receiving_conversion  receiving_conversion   HOLD_CHARACTERIZED       REHEARSAL_ONLY
rushing_conversion    rushing_conversion     HOLD_CHARACTERIZED       REHEARSAL_ONLY
td_layer              td_red_zone            HOLD_TENTATIVE           REHEARSAL_ONLY
qb_layer              (none)                 OWNER_BASELINE_SELECTION REHEARSAL_ONLY
qb_allocation         (none)                 CANDIDATE                REHEARSAL_ONLY
joint_accounting      joint_dependence       INVESTIGATE              REHEARSAL_ONLY
```

`RUNTIME_ROLE['REHEARSAL_ONLY']` is declared as *"may execute, but the artifact
is not publishable"*. That mapping from governance token to publication
consequence **already exists and is already correct**. It is simply never
called: `run_forecast.py` does not import `eligibility`.

**The honest consequence of ruling L3 on rows 1–3 is that the ranked candidate
table is empty today.** `rank_candidates` returns N rows and is never padded, so
an empty table is a lawful output. This matrix does not propose loosening
anything to avoid that.

### 4.2 DATA_BLOCKED — the one change that needs no WS-D

Row 2's proposed L3 has a transport-independent route: call
`eligibility.matrix()` at board-build time and derive `metric_status` from
`allowed_runtime_role`, instead of reading it from the hand-written table in
`metrics.py`. That reads `PATH_C_STATE` directly and does not depend on anything
travelling through `_nonqb_stage`.

It also removes a standing hazard. `eligibility.py:155` hard-codes
`'publication_eligible': False` with the comment *"NFL-1 gates everything
anyway"*. That is true today and becomes false the moment NFL-1 is authorized —
at which point the field stops being a conservative default and becomes a
constant that no longer describes anything.

### 4.3 The guard that cannot fire (WS23 C3) — measured again here

`assert_no_stale_labels` is the declared defence against exactly the
`MODELED`-versus-`DATA_BLOCKED` contradiction in row 2. Measured on this
checkout:

```
assert_no_stale_labels()                       -> PASS NO_STALE_GOVERNANCE_LABELS
assert_no_stale_labels([p4c_params.py])        -> PASS NO_STALE_GOVERNANCE_LABELS
assert_no_stale_labels([layers.py, metrics.py])-> PASS NO_STALE_GOVERNANCE_LABELS

p4c_params.py line 1:
  """D3 production parameters: the ACCEPTED P4C fit, not a reconstruction.
target_allocation action: DATA_BLOCKED
```

It passes because it requires a case-sensitive `\b(ACCEPTED|PROMOTED)\b` **and**
a pipeline-layer name on the same line, and defaults to scanning one file. Line
1 of `p4c_params.py` says "the ACCEPTED P4C fit" and contains no layer name, so
no offence is raised.

This is not a recommendation to change the guard — that is another workstream's
file. It is recorded here because **it is the reason row 2's contradiction
survived**, and any ruling on row 2 that assumes this guard is watching would be
assuming a defence that does not exist.

### 4.4 CALIBRATION_DEFECT — the reservation, stated honestly

This is the row WS14 called "the highest-value single change in this report",
and I am recommending it at L4 while recording evidence that WS14 did not weigh.

**The case for L4 is strong on its own terms.** It is the only token that says
the number is wrong rather than uncertain, and the product's sole downstream
consumer turns that number into a probability and compares it to a price.

**Two things weaken it, and the owner should have both.**

1. **The bias sign does not replicate.** Development:
   bias **+2.18 yards** (over-prediction), coverage 0.65 / 0.883 / 0.943 / 0.969
   at 50/80/90/95. Live, from `nfl/research/model_health/MODEL_HEALTH_2026-09-13.json`
   (baseline sha16 `4639ff1a0fdcb8a6`): `receiving/receiving_yards`, n = 48,
   `mean_signed_error` **−2.5197**, `pit_mean` 0.5721, coverage
   0.583 / 0.896 / 0.958. **Opposite sign, similar magnitude.** n = 48, which is
   far below anything this project treats as a sample, and the rows are not
   independent — they cluster by game and by player-game.
2. **The width half of the defect is in the conservative direction.**
   Over-coverage means intervals that are too wide, which pulls `P(over)` toward
   0.5 and *shrinks* disagreement gaps. It produces fewer candidates, not more.
   The directional-bias half is the genuine hazard; the coverage half is not,
   and "over-coverage at all four nominal levels" should not be cited as though
   it were.

**What that means for the ruling.** The governance token
`receiving_baseline_calibration = CALIBRATION_DEFECT` is a registered owner
state, and an L4 scoped to metrics produced by that estimator is a defensible
reading of *the token*. But it should not be sold as following from a
replicated measurement, because on the evidence in this tree the measurement
does not replicate in sign. **L3 is the defensible fallback**, and the honest
version of the recommendation is: L4 if the ruling is "a registered
CALIBRATION_DEFECT means the number does not publish"; L3 if the ruling is "the
measured evidence must carry the gate".

### 4.5 team_volume — annotate, do not gate

The concern that keeps this row from being purely decorative is real: `targets`
and `carries` are drawn from team volume, so ranking those metrics by
disagreement gap is partly ranking inherited team-volume width. The answer is
**annotation propagated along `eligibility.REQUIRED_INPUTS`** — the metric's row
carries the layer's warning — not a gate.

Two labels, kept separate, in the words of the DAL/NYG audit:

- `team_volume_is_near_unforecastable` — a statement about **discrimination and
  dispersion**. DAL `team_carries` sd 5.89, p05 19.43 to p95 45.29. Honest.
- `MODEL_VOLUME_BIAS` — a statement about the **mean**. **Not supported**:
  z = +0.02, +0.07, +0.46, all positive if anything.

> Conflating them would license shifting the team layer on evidence that does
> not exist. The layer's weakness is that it is *uninformative*, not that it is
> *low*.

### 4.6 The orphaned gate that already computes the right answer

`model_health.assert_ranking_admissible` has **zero importers** — confirmed here
by `grep -rn model_health --include=*.py`, which returns nothing outside the
module itself. Its docstring calls itself *"THE GATE. This is the rule the
product exists to enforce."*

It is not merely orphaned. It has already **run** and already produced a
per-metric L3 verdict on measured outcomes, stored in
`MODEL_HEALTH_2026-09-13.json`:

```
declared gate: "a metric under ANY warning is ranking_eligible=false. The row is
still published with its warning attached; it is removed from RANKING, not from
the comparison."

n_metrics 11, n_ranking_eligible 1

receiving/receiving_yards  n=48  elig=False  DIRECTIONAL_SKEW, SELECTED_SIDE_BELOW_EVEN, MARKET_GAP_ANTICALIBRATED
receiving/receptions       n=48  elig=False  (same three)
receiving/targets          n=48  elig=True   -
rushing/carries            n=12  elig=False  COVERAGE_BELOW_NOMINAL + the three
qb/att,cmp,db,int,ptd,pyds,sacks  n=18 each  elig=False  LAYER_SPECIFICATION_DEFECT, CONTAMINATED_STRATUM (+)
```

That is a Level-3 gate, on outcome evidence rather than on a token, reaching
almost exactly the conclusion rows 1–4 reach from governance — and nothing reads
it.

**Its false-positive risk is the one thing that must be said out loud before it
is wired:** these verdicts fire on n = 12 to n = 48 graded rows, unclustered. A
metric can be marked ranking-ineligible on twelve observations. WS16 §0's rule
applies to this artifact as much as to any other — a status is a statement about
measured evidence, and twelve rows is thin evidence. The fix is not to loosen
the warnings; it is that a gate reading them should carry the cluster count and
the n alongside the verdict, so a reader can tell a measured defect from a small
sample.

`model_health.WARNINGS` also shares **no token** with any governance token in
this matrix, and its `declared_defects` parameter — the one hook that could
carry `CALIBRATION_DEFECT` in — is never passed by anyone. Two vocabularies,
one job.

### 4.7 Where a board-level defect gate would go, and where it must not

`authorization.may_publish()` takes **zero arguments**. It reads
`PATH_C_STATE.gates.NFL_1` and an owner authorization record, and nothing else.
It cannot see a run, an artifact, a stage state, a warning or a completeness
value, because none are passed to it. Publication eligibility is therefore a
**global constant**, not a property of the forecast being published.

**That is correct and must not be changed.** Its value is that it is
un-argumentable: *"No test result, checklist state or caller flag can change
this."* Adding run arguments would create exactly the path from a computed
result to an authorization that the module exists to forbid.

Any board-scoped defect gate proposed above — row 6's completeness claim, row
9's publication boundary — belongs **beside** `may_publish()`, as a separate
function the board calls and reports separately, so that neither can be
satisfied by the other. Level 4 currently exists in two incompatible
granularities (`qb_metric_blockers`, per-metric and defect-driven;
`may_publish()`, board-wide and defect-blind) with nothing between them. The
gap, not either end of it, is what these recommendations would fill.

---

## 5. What I would put in front of the owner first

Three rulings, ranked, each with its false-positive risk stated as I actually
assess it rather than as it would be most persuasive.

### Ruling 1 — Does a governance token have a path to the gate at all? (rows 1–4, WS23 C1)

The narrow question: may `metric_status` continue to be hand-declared in
`metrics.py`, or must it be **derived** from the governance artifact that
`eligibility.py:1` declares authoritative?

Today `MODELED` is defined as *"a governed layer produced a full distribution"*
and is carried by `receiving/targets`, `receiving/receptions`, `rushing/carries`,
`qb/db`, `qb/pyds` and eight others, while `eligibility.matrix()` returns
`REHEARSAL_ONLY` and `publication_eligible: False` for **all ten** pipeline
layers, `target_allocation` on `DATA_BLOCKED` / `UNEXPLORED`. The guard that was
supposed to catch this cannot fire (§4.3). `daily_board.eligibility()` gates
ranking on `metric_status in ('MODELED','PROVISIONAL')`, so the hand-written
label **is** the gate input.

I rank this first because every other row depends on it: rows 1, 2, 3 and 4 are
all requests to move something to L3 or L4, and there is no wire from governance
to either level until this is settled.

**False-positive risk: LOW on the mechanism, HIGH on the consequence, and the
two should not be blurred.** Deriving a label from an authoritative artifact
cannot produce a false positive — it can only make the label agree with the
governance state. But the consequence today is that **every** metric becomes
`PROVISIONAL` or worse and, under rows 1–3, the ranked table empties. That is
the honest result of the current governance state, not an over-reach, and the
project's own rule is that an empty card is a valid result. It is still a
consequence the owner should accept deliberately rather than discover.

### Ruling 2 — Does a registered CALIBRATION_DEFECT publish? (row 4)

L4 metric-scoped, or L3. The full argument and the reservation are in §4.4.

I rank it second rather than first because it is the strongest *single* claim
but the weakest *evidentially*: development says bias +2.18, the live health
artifact says −2.52 on n = 48, and the over-coverage half of the defect pushes
in the conservative direction. WS14 recommended L4 and called it the
highest-value change in its report; I agree it is the most consequential, and I
think its evidential base is thinner than that framing conveys.

**False-positive risk: MODERATE-TO-HIGH.** A metric-scoped L4 suppresses a
number the model genuinely produced, on the strength of a bias whose sign does
not replicate between development and live. The scope is at least correct —
metric-scoped, never board-scoped, so it cannot destroy QB rows. If the owner
wants the gate to rest on measurement rather than on the registered token, the
answer is L3 now and L4 after a preregistered forward-chained study with a
declared equivalence margin.

### Ruling 3 — What does an unevaluated HARD invariant permit? (rows 9 and 10)

Three sub-questions, in the order they matter:

1. May a board be **published** while a HARD invariant stands DEFERRED?
   (Recommended: no — L4 board-scoped, seal unchanged at L2.)
2. Must `NOT_APPLICABLE` carry a justification payload and be checked against
   the run's manifest? (Recommended: yes — L5 only on the contradiction.)
3. Is there a floor on how many HARD invariants a run must actually evaluate,
   and how is it derived? (Recommended: scope-relative, declared in advance,
   never a fitted count.)

I rank it third because it is latent — no artifact in the tree is in the failing
state, and the sealed run evaluates 11 of 12. But it is the only row where the
gap is in the **L5** layer, and an L5 hole is the one kind that leaves nothing
behind to audit.

**False-positive risk: LOW as scoped above; HIGH if implemented as a count.**
A count bound refuses a legitimately partial run — a QB-only run cannot evaluate
a receiving invariant, and that is lawful. The contradiction-based trigger for
NOT_APPLICABLE has no such failure mode, because an invariant declared
inapplicable while its required layer sits in the manifest is an internal
inconsistency rather than a judgement call. And the honest hazard in sub-question
3 is the project's own no-silent-constants rule: `MIN_HARD_EVALUATED` set to 11
because today's run evaluates 11 is a constant fitted to the data.

---

## 6. Evidence ceiling

1. **One sealed run** underpins every claim about what the seal contains:
   `4b186a21b83a49ec`, `2026_01_DAL_NYG`, arm A, `V1_CANDIDATE_R8`,
   `dry_run: true`. No POST-inactives board was examined. Claims about the
   baseline QB path are read from source, not observed.
2. **The suite was not run** (instructed — many agents are editing the tree).
   No end-to-end execution of `run_forecast.build` was performed. Every claim is
   either a source reading with `file:line`, a re-hash, or an in-memory probe of
   a pure function.
3. **Probes were in-memory and read-only.** `assert_hard_invariants` and
   `assert_no_stale_labels` were called with seeded arguments in a throwaway
   interpreter. No repository file was modified; `PATH_C_STATE.json` was
   re-hashed after the fact and is unchanged at `ebd1274086ec9c81`.
4. **The live calibration evidence in §4.4 is n = 48, unclustered**, from a
   single dated health artifact. It is enough to establish that the development
   bias sign does not obviously replicate. It is **not** enough to establish the
   opposite sign, and §4.4 does not claim it is.
5. **Orphan claims rest on grep**, not a call-graph tool. Dynamic import by
   string would not be caught; I found no `importlib` use of `model_health`.
6. **`eligibility.matrix()` was run with no `input_states`**, so every
   `current_input_state` reads `UNKNOWN` and no layer was marked `BLOCKED` for a
   missing input. The `REHEARSAL_ONLY` results are driven purely by the
   governance action, which is the intended reading for this matrix.
7. **Line numbers are HEAD `837d52f`** and will move. WS14's line references
   were taken at `57d38ad`; where I cite a line I re-read it at `837d52f`.
8. **`PATH_C_STATE.json` is itself stale** — WS23 M2 records `registered_utc
   2026-09-08` with no entry for QB V1, QB3, SC1, R5–R8 or Q6–Q9B. Rows 1–4
   propose deriving gate inputs from an artifact that is six days behind the
   code citing it. That is a reason to update the artifact, not a reason to keep
   deriving labels by hand, but it is a real caveat on every "derive it from
   governance" recommendation above.
9. **Not assessed:** whether `nfl/product/orchestrator.py`,
   `nfl/tools/market_product_export.py` or `nfl/research/slate_runner.py` apply
   gates this matrix did not find.

**CODE CHANGED: NO. NO GOVERNANCE FILE EDITED. NOTHING APPLIED.**
