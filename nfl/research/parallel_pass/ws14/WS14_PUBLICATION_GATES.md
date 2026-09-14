# WS14 — Can a known defect still publish a board marked PASS?

**CODE CHANGED: NO.** Nothing outside `nfl/research/parallel_pass/ws14/` was
written. All probes below ran in memory (monkeypatched module attributes in a
throwaway interpreter); no repository file was modified, and the full suite was
not run.

Repo `/home/user/nfl`, HEAD `57d38ad`. Interpreter `python3.12`.

---

## 1. The answer, stated first

**Yes.** Every warning in the brief is currently either prose or a recorded
diagnostic. Not one of them is read by the function that decides publication.

The decisive fact is structural, not circumstantial:

```
nfl/production/authorization.py:28
    def may_publish() -> Outcome:
```

`may_publish()` takes **zero arguments**. It reads
`nfl/research/PATH_C_STATE.json` `gates.NFL_1` and
`nfl/NFL1_OWNER_AUTHORIZATION.json`, and nothing else. It cannot see a run, an
artifact, a stage state, a warning, a completeness value or an accounting
verdict, because none of them are passed to it. Publication eligibility in this
repository is therefore a **global constant**, not a property of the forecast
being published.

Probe (in memory, repository untouched):

```
real may_publish()            -> BLOCKED NFL1_NOT_AUTHORIZED
may_publish signature         -> ()
source mentions artifact/run_status/warning/completeness/verdict/stage -> False
after forcing gates NFL_1=AUTHORIZED + a valid owner record:
  may_publish()               -> PASS PUBLICATION_AUTHORIZED
  board.authorization_state(sealed artifact)
                              -> label 'LIVE NFL-1 FORECAST',
                                 may_be_called_published = True
  artifact completeness       -> still PARTIAL_PLAYER_COVERAGE
  DIAGNOSTIC verdicts FAILing -> still ['nonqb_layer_availability',
                                        'qb_known_limitations']
```

The same sealed run that carries `PARTIAL_PLAYER_COVERAGE`, two DIAGNOSTIC
`FAIL`s, one HARD invariant `DEFERRED`, `qb_inactive_ownership.enforced =
false`, and five governance tokens buried in prose is relabelled
**LIVE NFL-1 FORECAST** by flipping one string in one JSON file. The single
thing standing between the current state and a published board carrying every
known defect is an owner decision — which is exactly the gate it is supposed to
be, and exactly *not* a defect gate.

---

## 2. Verified evidence from the sealed run

Run: `nfl/research/live/2026_01_DAL_NYG/FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec/`
(`run_id 4b186a21b83a49ec`, arm A, `V1_CANDIDATE_R8`, `dry_run: true`,
`status: SEALED`, `n_refusals: 0`, `first_failure: null`).

### 2.1 Governance tokens inside `spec_version` — confirmed

From `run_status.json` (verbatim), reproduced identically in
`board.json.layer_governance` and rendered into `BOARD.md` lines 458–470:

| stage | state | spec_version |
|---|---|---|
| team_environment | **PASS** | `team-volume-v1-p4b-frozen-1` + warning `known limitation: team_volume_is_near_unforecastable` |
| participation | **PASS** | `Stage2 ewma_hl2; governance INFORMATION_CONSTRAINED` |
| targets_carries | **PASS** | `P4C system C; governance DATA_BLOCKED` |
| conversion | **PASS** | `RC1 baseline; SIGNAL_WEAK; governance HOLD_CHARACTERIZED + CALIBRATION_DEFECT` |
| td_layer | **PASS** | `TD2 pooled positional control; governance HOLD_TENTATIVE` |
| feature_build | **PASS** | code `STAGE_DECLARED_UNIMPLEMENTED` |

These strings are **hard-coded literals in a `for`-loop tuple** at
`nfl/production/run_forecast.py:918-930`. `Pipeline.run_stage`
(`nfl/production/pipeline.py:99-101`) accepts `spec_version` as a caller-supplied
parameter and stores it verbatim at `pipeline.py:153`. **Nothing in the
repository ever parses a `spec_version` string.** `Pipeline.status()`
(`pipeline.py:170-180`) reads only `StageResult.state`.

So `PASS` here means "the callable returned an `Outcome` whose state was PASS".
It does not mean, and was never computed to mean, anything about governance.

Note `feature_build` **PASS** with code `STAGE_DECLARED_UNIMPLEMENTED`: a stage
that ran nothing reports the same state word as a stage that ran.

### 2.2 A DIAGNOSTIC-class FAIL that did not prevent sealing — confirmed

`forecast_artifact.json.accounting_verdicts`:

| invariant | class | state | code |
|---|---|---|---|
| `nonqb_layer_availability` | DIAGNOSTIC | **FAIL** | `NONQB_LAYERS_UNAVAILABLE` |
| `qb_known_limitations` | DIAGNOSTIC | **FAIL** | `QB_LAYER_KNOWN_LIMITATIONS` |
| `qb_cross_layer_reconciliation` | HARD | **DEFERRED** | `CROSS_LAYER_RECONCILIATION_NOT_RUN` |

The artifact sealed. The sealing stage's own detail says so plainly:
`"11 of 12 hard invariant(s) were evaluated and hold; 1 carried as OWED; 2
diagnostic(s) not clean (recorded, not gating)"`.

This is **by design and correctly implemented**: `HARD_REFUSING_STATES =
('FAIL', 'BLOCKED')` at `nfl/prospective/artifact.py:115`, and
`assert_hard_invariants` (`artifact.py:287`) refuses only on a HARD invariant in
one of those two states. Seeded probes confirm the boundary is real:

```
HARD invariant DEFERRED        -> PASS  HARD_INVARIANTS_HOLD
HARD invariant BLOCKED         -> FAIL  HARD_INVARIANT_FAILED
DIAGNOSTIC invariant FAIL      -> PASS  HARD_INVARIANTS_HOLD
ALL 12 HARD -> NOT_APPLICABLE  -> PASS  HARD_INVARIANTS_HOLD
ALL 12 HARD -> DEFERRED        -> PASS  HARD_INVARIANTS_HOLD
```

The last two are the gate hole. `artifact.py:344-351` anticipates it in a
comment — *"otherwise an artifact could mark every hard invariant
NOT_APPLICABLE and its verdict would read exactly like a clean run"* — then
counts and names them rather than refusing. An artifact in which **no** hard
invariant was ever evaluated returns `PASS HARD_INVARIANTS_HOLD`. The detail
string says `0 of 12 ... were evaluated and hold`, so it is honest; but the
Outcome state a caller branches on is PASS. The module docstring's own rule
("a check that did not run has not passed") is enforced for `BLOCKED` and not
for `DEFERRED` or `NOT_APPLICABLE`.

The sealed run exercises 1 of 12, not 12 of 12, so this is a latent hole, not a
realised one.

### 2.3 Layer warnings are silently dropped in stage aggregation — new finding

`nfl/production/nonqb/layers.py` emits real structured warnings:

- `layers.py:271` participation — `known limitation: pass-snap participation is an upper bound on routes run`
- `layers.py:466` conversion — `governance='HOLD_CHARACTERIZED + CALIBRATION_DEFECT'`
- `layers.py:470-472` conversion — `['known limitation: RC1 SIGNAL_WEAK', 'governance: receiving_baseline_calibration CALIBRATION_DEFECT']`
- `layers.py:522-525`, `573-577` td_layer / rushing_td — `governance='HOLD_TENTATIVE'` + warning

`_nonqb_stage` (`run_forecast.py:871`) aggregates those layers and returns at
`run_forecast.py:908-914`:

```python
return Outcome.ok(
    f'{_st.upper()}_OK',
    value={...}, layers={...}, spec_versions={...}, test_only=...)
```

There is **no `warnings=` key and no `governance=` key**. `StageResult`
(`pipeline.py:154`) copies only `evidence['warnings']`, and only the whitelisted
metrics keys — `spec_versions` and `governance` are dropped too. That is why the
sealed run shows `"warnings": []` on participation, targets_carries, conversion
and td_layer while the layers underneath them raised warnings naming
SIGNAL_WEAK and CALIBRATION_DEFECT by name.

`team_environment` shows its warning only because it takes a *different* code
path (`run_forecast.py:1079-1080`) that does pass `warnings=`.

**This is the mechanism by which a governance state became prose.** The layer
emits it as data; the pipeline discards the data; a human then retypes it into a
literal `spec_version` string at `run_forecast.py:918-930`. The two copies have
already drifted: `layers.SPEC['appearance']` (`layers.py:34-35`) says
`governance INFORMATION_CONSTRAINED`, while the appearance stage is passed the
literal `'P3 appearance'` (`run_forecast.py:920`). Appearance's governance state
reaches neither `run_status.json` nor the board.

### 2.4 The candidate QB path drops QB limitations — new finding

The **baseline** QB return (`run_forecast.py:1063-1064`) carries
`warnings=[f'known limitation: {k}' for k in QBV1.KNOWN_LIMITATIONS]`
(`multi_qb_over_prediction`, `int_discrimination`,
`discrete_low_count_intervals`). The **candidate** return
(`run_forecast.py:418-425`, reached because this run is `V1_CANDIDATE_R8`)
carries none. Sealed run: `qb_layer` `"warnings": []`.

The limitations still reach the artifact through the `qb_known_limitations`
DIAGNOSTIC verdict, so nothing is lost outright — but the stage table a reader
sees says the QB layer raised no warning while running the *less* validated of
the two configurations.

### 2.5 `qb_inactive_ownership.enforced == false` — what it actually gates

From `run_status.json`:

```
enforced: false
failed_conditions: ['official_inactive_evidence_ingested', 'no_unresolved_identity']
unresolved_qb_room_risk.blocks_qb_enforcement: true
inactive_qbs_in_modelled_room: {'DAL': ['00-0039398']}
```

At the same time the HARD invariant `qb_inactive_owns_nothing` reports
**PASS** (`QB_INACTIVE_OWNS_NOTHING`). Those are not in conflict: the invariant
checks that resolved inactive QBs hold zero share; `enforced` additionally
requires the official list to have been *ingested and tied to this game*. The
artifact's own `what_true_does_not_mean` block says this correctly.

`enforced == false` **does** gate, and it is the only warning in the brief that
does. Probe on this board:

```
qb/att, qb/pyds : _defect_flags -> ['QB_INACTIVE_NOT_CONSUMED'] (contaminating)
                  qb_metric_blockers(PRE)  -> ['QB_AVAILABILITY_UNRESOLVED_PRE_INACTIVES',
                                               'QB3_WEEK1_SEASON_BOUNDARY']
                  qb_metric_blockers(POST) -> ['QB3_WEEK1_SEASON_BOUNDARY',
                                               'QB_INACTIVE_OWNERSHIP_NOT_ENFORCED']
receiving/*, rushing/* : no flags, no blockers
```

`nfl/tools/market_comparison.py:422-444` turns those into a per-row refusal
(`CONTAMINATING_DEFECT`) before a quote is priced, and
`rank_candidates` (`market_comparison.py:295`) drops `DEFECT_FLAGGED` rows from
the ranked table. That gate is real, tested, and scoped to `qb/` metrics only.

### 2.6 One accidental extra guard, worth recording

`FS.resolve_stage('.../4b186a21b83a49ec')` returns
**BLOCKED `FORECAST_STAGE_UNKNOWN`** — the run-id directory matches neither
`pre_inactives` nor `post_inactives`. The comparator cannot name this board's
stage and fails closed. So *this particular* sealed directory could not reach
the market comparator at all. The properly-named sibling
`nfl/research/live/2026_01_DAL_NYG/pre_inactives_V1_CANDIDATE_R8/` could.
The refusal is a directory-naming accident, not a defect gate.

---

## 3. The five levels

| Level | Definition | Where implemented | Effect on a reader |
|---|---|---|---|
| **1. INFORMATIONAL ANNOTATION** | Appears only as text — a `spec_version` string, a `caveat`, a `note`, a label. No code branches on it. | `run_forecast.py:918-930`; `nfl/product/metrics.py` `caveat`; `board.py:139` `layer_governance` | Sees it if they read the prose. Nothing changes. |
| **2. DEGRADATION WARNING** | Carried as structured data a program *could* branch on — an `Outcome` warning, a DIAGNOSTIC verdict, `completeness`, `metric_status = PROVISIONAL` — but no gate consumes it. | `artifact.py` DIAGNOSTIC class; `run_forecast.py:1434` `_completeness`; `metrics.PROVISIONAL`; `market_comparison.py:257` `_data_status` | Row is published with a marker (`*`, a `data_status` column). Still ranked. |
| **3. RANKING GATE** | Row stays visible in the comparison but is removed from the ordered candidate table. | `market_comparison.py:293-295` (`DEFECT_FLAGGED` only); `daily_board.py:223` `eligibility()` → `RANKING_ELIGIBLE`; `model_health.py:136` `assert_ranking_admissible` (**orphaned — zero importers**) | Number is shown; it is not presented as a candidate. |
| **4. PUBLICATION GATE** | The number does not reach the published comparison/board at all, by name. | `market_comparison.py:433-444` per-row `CONTAMINATING_DEFECT`; `forecast_stage.py:129` `qb_metric_blockers`; `forecast_stage.py:76` `resolve_stage`; `authorization.may_publish()` (board-wide, run-independent) | Row absent from the card; reason recorded in the refusals file. |
| **5. HARD REFUSAL** | The run does not seal. No artifact exists. | `artifact.py:287` `assert_hard_invariants` on HARD `FAIL`/`BLOCKED`; `run_forecast.py:856` `_assert_every_layer_is_reported` (`ENGINE_LAYER_NOT_REPORTED`); `pipeline.py:159` halt-on-first-refusal; `RF.refuse(...)` | Nothing to read. `status: REFUSED`. |

Two structural notes on this table:

- Level 4 exists in **two incompatible granularities**. `qb_metric_blockers` is
  per-metric and defect-driven. `may_publish()` is board-wide and
  defect-*blind*. There is no per-board defect gate between them.
- Level 3 is almost entirely unwired. `nfl/product/model_health.py` — the module
  whose docstring states the rule *"a giant model-versus-market gap must NEVER
  automatically become a top-ranked recommendation when the governing layer is
  under a health warning"* — has **no importers anywhere in the repository**
  (`grep -rn model_health --include=*.py` returns nothing outside the module
  itself). Its `WARNINGS` vocabulary (`COVERAGE_BELOW_NOMINAL`,
  `MARKET_GAP_ANTICALIBRATED`, `LAYER_SPECIFICATION_DEFECT`, …) shares **no
  token** with any warning in section 4. Its `declared_defects` parameter — the
  one hook that could carry `CALIBRATION_DEFECT` in — is never passed by anyone.

---

## 4. Per-warning: the four questions

Columns: **(a)** informational only? **(b)** should it gate publication?
**(c)** does it currently gate? **(d)** if not, what does it do instead?

### INFORMATION_CONSTRAINED
*(subsystem `appearance`; `PATH_C_STATE.subsystems.appearance.action`)*

- **(a)** In the production path, **yes**. It survives only as the literal at
  `run_forecast.py:922` (participation) and is lost entirely for appearance
  (`run_forecast.py:920` passes `'P3 appearance'`, dropping the token that
  `layers.py:34-35` assigns).
- **(b)** **No — it should gate RANKING, not publication.** It is a claim that
  the information to do better does not exist. A forecast under an honest
  information ceiling is still an honest forecast. But a wide honest
  distribution compared against a sharp book line manufactures large
  "disagreement gaps" that are width artefacts, and `rank_candidates` orders
  precisely by that gap.
- **(c) No.** Nothing parses it.
- **(d)** Nothing. Not even an annotation: no metric carries an
  INFORMATION_CONSTRAINED caveat in `metrics.py`.
- **Level today: 1 — INFORMATIONAL ANNOTATION.** Recommended: **3 — RANKING GATE.**

### DATA_BLOCKED
*(subsystem `target_allocation`; `knowledge: UNEXPLORED`, `blocked_on: "participation adequacy"`)*

- **(a)** Yes — literal at `run_forecast.py:924`, and `layers.py:38`.
- **(b)** **Yes, for ranking; arguably for publication.** This subsystem is
  `UNEXPLORED` *and* blocked on an upstream adequacy question that is itself
  `INFORMATION_CONSTRAINED`. Yet `('receiving','targets')` is
  `status: MODELED` in `metrics.py:62-64` — no asterisk, no caveat, fully
  ranking-eligible. A metric whose governing subsystem has never been explored
  is presented to a reader as cleanly as one that has.
- **(c) No.**
- **(d)** Nothing.
- **Level today: 1 — INFORMATIONAL ANNOTATION.** Recommended: **3 — RANKING
  GATE** (minimum), with `metrics.py` status demoted `MODELED → PROVISIONAL`.

### SIGNAL_WEAK
*(subsystem `receiving_conversion`; `recovered_pct_of_oracle: 4.89`)*

- **(a)** Partly. It reaches the reader as a `metrics.py:67-69` caveat on
  Receiving yards (`*` in `BOARD.md`) and as the `run_forecast.py:926` literal.
  As a *warning* it is dropped (section 2.3).
- **(b)** **Gate ranking, not publication.** RC1 recovers 4.89% of the oracle
  share. That is a weak but honest signal; refusing to publish it would refuse a
  number the model genuinely produced. Ranking it by gap size against a book is
  what is indefensible.
- **(c) No.** `metric_status = PROVISIONAL` is explicitly *ranking-eligible*:
  `daily_board.py:234` accepts `('MODELED', 'PROVISIONAL')`.
- **(d)** Annotation (the `*`) plus a caveat line.
- **Level today: 2 — DEGRADATION WARNING.** Recommended: **3 — RANKING GATE.**

### CALIBRATION_DEFECT
*(subsystem `receiving_baseline_calibration`; evidence: "RC1 measured bias +2.18 yards and over-coverage at all four nominal levels")*

- **(a)** Yes, in effect. It is inside the same caveat string as SIGNAL_WEAK and
  inside the `run_forecast.py:926-927` literal. The layer raises it as a
  structured warning at `layers.py:472` and as `governance=` evidence at
  `layers.py:466`; **both are discarded** before `run_status.json`.
- **(b)** **YES — this one should gate publication, at metric granularity.**
  It is the strongest case of the nine and is different in kind from the others.
  SIGNAL_WEAK says *"we know little"*. CALIBRATION_DEFECT says *"the number we
  emit is measurably wrong in a named direction, by +2.18 yards, with
  over-coverage at all four nominal levels"*. The product's only downstream
  consumer of that number computes `P(over line)` from the draws and compares it
  to a de-vigged book price. A distribution with declared directional bias and
  declared over-coverage produces a systematically wrong probability and
  therefore a systematically wrong "disagreement". Publishing it beside a market
  price is a false-green state by the project's own definition, and the project
  rule is that calibration is the *gate*.
- **(c) No.** It gates nothing. `receiving/receiving_yards` is PROVISIONAL,
  which is ranking-eligible, and `_defect_flags` (`daily_board.py:252-269`)
  knows exactly one defect id — `QB_INACTIVE_NOT_CONSUMED` — and nothing else.
- **(d)** Annotation only.
- **Level today: 1/2 — ANNOTATION.** Recommended: **4 — PUBLICATION GATE**
  (metric-scoped), or **3** at absolute minimum.

### team_volume_is_near_unforecastable
*(`team_volume_v1.KNOWN_LIMITATIONS`; "best simple baseline was the league mean in two seasons of four and correlation peaked at 0.167")*

- **(a)** No — it is the **one** warning in the brief that actually reaches
  `run_status.json.stages[].warnings` and `board.json.layer_governance` as
  structured data, because `run_forecast.py:1079-1080` passes `warnings=`.
- **(b)** **No.** Its own declared policy is right: *"reported on every run,
  never presented as skill"*, and *"these draws are honest about that width;
  they do not narrow it"*. An honestly wide distribution is not a defect. It
  should, however, propagate to the metrics that *consume* team volume — carries
  and targets are drawn from it — so that ranking by gap is not ranking by
  inherited team-volume width.
- **(c) No.** Nothing reads `stages[].warnings`. Grep confirms: the token has
  exactly two occurrences in `.py` files — its definition
  (`team_volume_v1.py:62`) and a test assertion.
- **(d)** Renders into `BOARD.md` line 460 and stays there.
- **Level today: 2 — DEGRADATION WARNING.** Recommended: **stay at 2**, but
  propagate to downstream metrics (see §5, mechanism M4).

### QB3_WEEK1_SEASON_BOUNDARY
*(`run_status.json.qb3_configuration`: both rooms `week1_specification_defect: true`; DAL `configuration: DISAGREE`)*

- **(a)** **No.** This is a genuine, working gate.
- **(b)** Yes — and it does.
- **(c) YES.** `forecast_stage.qb_metric_blockers` (`forecast_stage.py:129`)
  emits it at **both** PRE and POST stages, and `market_comparison.py:430-444`
  refuses every `qb/` quote carrying it. It is the only warning here whose
  implementation reasons explicitly about *not clearing*: ingesting an inactive
  list does not repair a cell definition.
- **(d)** n/a. Note the fail-closed path at `forecast_stage.py:158-170`: a board
  with no `qb3_configuration` field recomputes the condition from the governed
  source, and if even that is unreachable applies the blocker anyway. That is
  the right shape and is the model the other warnings should copy.
- **Level today: 4 — PUBLICATION GATE (metric-scoped).** Correct. **No change.**
  One residual: `BOARD.md` itself never mentions QB3 — the defect gates the
  *market comparison* but is invisible on the board a human reads.

### qb_inactive_ownership.enforced == false

- **(a)** No.
- **(b)** Yes — and it does, at POST.
- **(c) YES, partially.** Two independent paths:
  `daily_board._defect_flags` (`daily_board.py:262`) raises
  `QB_INACTIVE_NOT_CONSUMED` — but **only when `'R2' in component_manifest`**;
  and `forecast_stage.qb_metric_blockers` raises
  `QB_INACTIVE_OWNERSHIP_NOT_ENFORCED` — but **only at stage POST**. The
  comment at `market_comparison.py:414-424` records that the first path alone
  once let a board without R2 price QB quotes unrefused, which is why the second
  was added.
- **(d)** n/a. Remaining hole: a **PRE**-stage board without `R2` raises
  neither `QB_INACTIVE_NOT_CONSUMED` (no R2) nor
  `QB_INACTIVE_OWNERSHIP_NOT_ENFORCED` (not POST). It is covered in practice
  only because PRE boards always carry `QB_AVAILABILITY_UNRESOLVED_PRE_INACTIVES`
  — coverage by a *different* blocker, which is the kind of accidental overlap
  `forecast_stage.py:134-149` explicitly warns against.
- **Level today: 4 — PUBLICATION GATE (metric-scoped, conditional).**
  Recommended: keep, and make the POST condition unconditional on stage.

### PARTIAL_PLAYER_COVERAGE
*(`run_forecast.py:1434`; this run: `absent_layers: ['feature_build']`)*

- **(a)** No — it is structured, on both `run_status.json` and
  `forecast_artifact.json`, and `artifact.COMPLETENESS` declares it a lawful
  value.
- **(b)** **No, not for publication of the board.** It correctly describes
  coverage, not correctness: the players who *were* modelled are modelled
  properly. It **should** gate any claim that the board is complete, and it
  already does so where that claim matters most.
- **(c) YES, but only in the evidence/promotion path.**
  `q9shadow.ledger.BLOCKERS['COMPLETE_ARTIFACT_LAYERS_ABSENT']` is evaluated
  live and reads `BLOCKED — "completeness is PARTIAL_PLAYER_COVERAGE"`;
  `ledger.promotion_gate()` (`ledger.py:1087`) refuses on it and has no
  override. Measured now: all three blockers BLOCKED
  (`COMPLETE_ARTIFACT_LAYERS_ABSENT`, `INJURY_REPORT_INCOMPLETE`,
  `G0A_11_OF_12`). **But `promotion_gate` is imported only by the q9shadow
  subsystem and its tests — never by `run_forecast`, `board`, or
  `market_comparison`.**
- **(d)** On the product side it becomes a `data_status` column value
  (`market_comparison.py:276-277`) and nothing more.
- **Level today: 2 — DEGRADATION WARNING** (product) / **5-equivalent for
  promotion evidence** (q9shadow). Recommended: **stay at 2** for publication;
  surface `absent_layers` on `BOARD.md`, which currently omits it.

### NONQB_LAYERS_UNAVAILABLE
*(DIAGNOSTIC verdict, `run_forecast.py:1512`)*

- **(a)** No — structured verdict in the artifact.
- **(b)** **No.** It is the same fact as PARTIAL_PLAYER_COVERAGE, named so the
  artifact says *which* layers. `artifact.py:236-242` states the reasoning and it
  is sound: a layer blocked on a feed is a coverage fact.
- **(c) No.** DIAGNOSTIC never gates, by design (`artifact.py:113`). Probe:
  DIAGNOSTIC FAIL → `PASS HARD_INVARIANTS_HOLD`.
- **(d)** Recorded in `accounting_verdicts`; named in the sealing detail string.
- **Level today: 2 — DEGRADATION WARNING.** Correct. **No change.**

### Others found

**`qb_known_limitations` (DIAGNOSTIC FAIL, every run).** `multi_qb_over_prediction`,
`int_discrimination`, `discrete_low_count_intervals`. Correctly non-gating —
`artifact.py:220-227` is right that refusing here would refuse every run ever
made. But `('qb','int')` is `status: MODELED` in `metrics.py:47-48`, i.e. no
annotation at all, while `int_discrimination` is a declared limitation of the
layer that produces it. **Level 2 → should be Level 1-and-2: at minimum
PROVISIONAL with a caveat.**

**HARD invariant in `DEFERRED` / `NOT_APPLICABLE`.** Section 2.2. An artifact
with all twelve hard invariants unevaluated returns PASS. **Latent Level-5
hole.**

**`feature_build` PASS / `STAGE_DECLARED_UNIMPLEMENTED`.** A stage that ran
nothing reports the same state word as a stage that ran. It is caught downstream
(`_absent` → `PARTIAL_PLAYER_COVERAGE` → `NONQB_LAYERS_UNAVAILABLE`), so the
information survives — but the stage table in `BOARD.md` reads PASS.

**`nonqb/eligibility.py` is the missing wire.** `NON_PRODUCTION_ACTIONS`
(`eligibility.py:31-35`) already lists **exactly** the tokens in this brief —
`INFORMATION_CONSTRAINED`, `CALIBRATION_DEFECT`, `ESTIMATOR_DEFECT`,
`DATA_BLOCKED`, `HOLD_TENTATIVE`, `HOLD_CHARACTERIZED` — and maps each to
`allowed_runtime_role: REHEARSAL_ONLY`, whose declared meaning
(`eligibility.py:92`) is **"may execute, but the artifact is not publishable"**.
The mapping from governance token to publication consequence *already exists and
is already correct*. It is simply never called: `run_forecast.py` does not
import `eligibility`, and `eligibility.py:155` hard-codes
`'publication_eligible': False` with the comment *"NFL-1 gates everything
anyway"* — which is true today and becomes false the moment NFL-1 is authorized.

**`model_health.py` is orphaned.** Zero importers. §3.

**`UNREPORTED_LAYERS`** (`run_forecast.py:851-855`) exempts `rushing_conversion`
from the layer-reporting guard. If it ever failed, no stage would report it. Low
impact today because `rushing/rushing_yards` is declared UNAVAILABLE.

---

## 5. Recommended mapping, and the smallest mechanism for each

| Warning | Today | Recommended | Mechanism |
|---|---|---|---|
| INFORMATION_CONSTRAINED | 1 | **3 RANKING GATE** | M1 + M2 |
| DATA_BLOCKED | 1 | **3 RANKING GATE** | M1 + M2 |
| SIGNAL_WEAK | 2 | **3 RANKING GATE** | M2 |
| **CALIBRATION_DEFECT** | 1/2 | **4 PUBLICATION GATE** (metric-scoped) | M3 |
| team_volume_is_near_unforecastable | 2 | 2 (unchanged) + propagate | M4 |
| QB3_WEEK1_SEASON_BOUNDARY | 4 | 4 (unchanged) | — |
| qb_inactive_ownership.enforced == false | 4 (conditional) | 4 (unconditional) | M5 |
| PARTIAL_PLAYER_COVERAGE | 2 | 2 (unchanged) + surface | M6 |
| NONQB_LAYERS_UNAVAILABLE | 2 | 2 (unchanged) | — |
| qb_known_limitations | 2 | 2 + annotate | M4 |
| HARD invariant DEFERRED/NOT_APPLICABLE | latent | **5 HARD REFUSAL** above a declared bound | M7 |

### M1 — stop retyping governance into prose (prerequisite, ~6 lines)

`_nonqb_stage` (`run_forecast.py:908-914`) already collects each layer's
`spec_version` into `spec_versions=`. Add the same for `warnings` and
`governance`, and have `StageResult` (`pipeline.py:146-157`) carry a
`governance` field alongside `warnings`. The tokens then travel as **data** from
`layers.py:33-46` to `run_status.json` without a human retyping them, and the
`run_forecast.py:918-930` literals can be deleted rather than maintained. This
alone closes the appearance/participation drift in §2.3 and is a strict
information gain with no behaviour change.

### M2 — one call to a function that already exists (~3 lines)

`nonqb/eligibility.matrix()` already maps every governance token to
`allowed_runtime_role`. Call it once at board-build time and set
`metric_status = PROVISIONAL` for every metric whose layer is not
`PRODUCTION`, then change `daily_board.eligibility()` (`daily_board.py:234`) so
`PROVISIONAL` appends `LAYER_NOT_PRODUCTION:<subsystem>:<action>` to `why`,
making the row ranking-**in**eligible while remaining fully visible. That is the
declared contract of `RUNTIME_ROLE['REHEARSAL_ONLY']` — *"may execute, but the
artifact is not publishable"* — finally being read. It also removes the standing
hazard in `eligibility.py:155`, where publication eligibility is hard-coded
False "because NFL-1 gates everything anyway".

Effect check: this makes every non-QB metric ranking-ineligible today, because
every non-QB subsystem is in a NON_PRODUCTION action. **That is the honest
result, not an over-reach** — `rank_candidates` returns N rows, never pads to
ten, and an empty ranked table is a valid result.

### M3 — one entry in a table that already gates (~8 lines)

`daily_board._defect_flags` (`daily_board.py:252-269`) is a one-defect table.
Add a second entry driven by `PATH_C_STATE`:

```
id: LAYER_CALIBRATION_DEFECT
condition: subsystem action == 'CALIBRATION_DEFECT'
contaminates_this_metric: metric's layer maps to that subsystem
```

Nothing else changes. `_data_status` already returns `DEFECT_FLAGGED` for a
contaminating flag (`market_comparison.py:272`); `rank_candidates` already drops
it (`:295`); `eligibility()` already appends `KNOWN_DEFECT:<id>`
(`daily_board.py:244-246`). To reach **Level 4** rather than 3, the flag also
needs to be added to the `bad` list at `market_comparison.py:413` for non-`qb/`
metrics — that is the existing `qb/`-scoped branch generalised, one condition
removed.

This is the highest-value single change in this report: a measured +2.18-yard
bias with declared over-coverage currently reaches a market comparison with a
`*` beside it and full ranking eligibility.

### M4 — propagate a layer warning to the metrics it feeds (~10 lines)

Extend `_defect_flags` to walk `eligibility.LAYER_SUBSYSTEM` /
`REQUIRED_INPUTS` so a warning on `team_environment` marks the metrics drawn
from team volume (`receiving/targets`, `rushing/carries`) as annotated rather
than clean, and `qb_known_limitations` annotates `qb/int`. Annotation only —
Level 2, not a gate.

### M5 — delete one stage condition (1 line)

`forecast_stage.py:170`: `if stage == POST and not board.get('qb_inactive_ownership_enforced')`.
Drop the `stage == POST` clause. A PRE board that also lacks `R2` then raises
`QB_INACTIVE_OWNERSHIP_NOT_ENFORCED` on its own authority instead of relying on
`QB_AVAILABILITY_UNRESOLVED_PRE_INACTIVES` happening to cover it. This is the
same fix already applied once at `market_comparison.py:414-424`, applied to the
remaining hole.

### M6 — render what is already in the artifact (~4 lines)

`nfl/product/render.py`: print `completeness` and `absent_layers` in the
`BOARD.md` header, and print `qb3_configuration` where it exists. Both are
already on `board.json`. `BOARD.md` currently mentions neither, so the human
reader of the board sees `PASS` on thirteen stages and no coverage statement at
all.

### M7 — bound the unevaluated hard invariants (~6 lines)

In `assert_hard_invariants` (`artifact.py:344-352`), after counting `owed` and
`na`, refuse when `len(held) < MIN_HARD_EVALUATED` (declared, not inferred) or
when a named invariant is DEFERRED without an `owed` payload. The function
already computes every number it needs; it just does not branch on them. Today's
sealed run (11 of 12 held) would be unaffected.

### Not recommended

- Do **not** make INFORMATION_CONSTRAINED, SIGNAL_WEAK, HOLD_TENTATIVE,
  HOLD_CHARACTERIZED or `team_volume_is_near_unforecastable` publication gates.
  Each describes an honest width or an information ceiling. Suppressing a row
  the model genuinely produced is the dishonesty `model_health.py`'s own
  docstring warns about.
- Do **not** make `may_publish()` defect-aware by adding run arguments to it.
  Its value is that it is un-argumentable: *"No test result, checklist state or
  caller flag can change this."* A defect gate belongs **beside** it, as a
  separate function the board calls and reports separately, so that neither can
  be satisfied by the other.

---

## 6. Blocker propagation — the actual chain

```
PATH_C_STATE.json  subsystem action token
   |
   |-- nonqb/eligibility.py:31  NON_PRODUCTION_ACTIONS
   |      -> allowed_runtime_role = REHEARSAL_ONLY
   |      -> publication_eligible = False (hard-coded)
   |      ***DEAD END: run_forecast does not import this module***
   |
   |-- layers.py:33  SPEC[...] string     -- retyped by hand into
   |-- layers.py:466 governance=...       -- DROPPED by _nonqb_stage
   |-- layers.py:470 warnings=[...]       -- DROPPED by _nonqb_stage
   |
   v
run_forecast.py:918-930  hard-coded literal
   v
pipeline.py:153  StageResult.spec_version   (stored verbatim, never parsed)
   v
run_status.json stages[].spec_version = "... governance CALIBRATION_DEFECT"
   v
board.py:139 layer_governance()  (verbatim copy)
   v
BOARD.md line 464: "| conversion | PASS | RC1 baseline; SIGNAL_WEAK; ... |"
   v
***END. No branch, no gate, no consumer.***
```

Against the one chain that does close:

```
qb_allocation.py:183  defect_id = QB3_WEEK1_SEASON_BOUNDARY
   v
run_status.json qb3_configuration[team].week1_specification_defect = true
   v
board.json qb3_configuration          (carried, not re-derived)
   v
forecast_stage.py:151  qb_metric_blockers() -> ['QB3_WEEK1_SEASON_BOUNDARY']
   v
market_comparison.py:430  bad += blockers
   v
market_comparison.py:433  refused.append(reason='CONTAMINATING_DEFECT'); continue
   v
***ROW NEVER PRICED. Refusal recorded by name.***
```

The difference between the two chains is not rigour of intent — both were
written carefully. It is that the second keeps the defect as a **typed field**
from origin to gate, and the first converts it to **English** at step two.

---

## 7. Evidence ceiling

What this report rests on, and what it cannot support:

1. **One sealed run.** `4b186a21b83a49ec`, one game (`2026_01_DAL_NYG`), arm A,
   `V1_CANDIDATE_R8`, `dry_run: true`. Conclusions about the *baseline*
   configuration's warning propagation (§2.4) are read from source, not
   observed. Conclusions about a POST_INACTIVES board are read from source; no
   POST board was examined.
2. **The suite was not run** (instructed). Every claim about what gates is
   either a source reading with `file:line`, or an in-memory probe of a pure
   function. No end-to-end execution of `run_forecast.build` was performed.
3. **`may_publish()` under AUTHORIZED was simulated**, by replacing
   `AUTH.gate_state` and `AUTH.AUTH_RECORD` on the imported module object in a
   throwaway interpreter. `nfl/research/PATH_C_STATE.json` and
   `nfl/NFL1_OWNER_AUTHORIZATION.json` were not touched and
   `NFL1_OWNER_AUTHORIZATION.json` does not exist. What is *proved* is that
   `may_publish()` has no run-dependent input; what is *inferred* is that a real
   authorization would behave as the simulation did.
4. **Orphan claims rest on grep**, not on a call-graph tool. `model_health` has
   no importers per `grep -rn "model_health" --include=*.py`; dynamic import by
   string would not be caught. I found no `importlib` usage of it.
5. **Seeded-violation probes were run on `assert_hard_invariants` only.** The
   all-DEFERRED and all-NOT_APPLICABLE results are real returns from the real
   function, but no artifact in the repository is in that state, so this is a
   demonstrated **latent** hole, not an observed failure.
6. **Not assessed:** whether any *other* entrypoint (`nfl/product/orchestrator.py`,
   `nfl/tools/market_product_export.py`, `nfl/research/slate_runner.py`) applies
   gates this report did not find. `market_product_export.py:258` references
   `QB3_WEEK1_SEASON_BOUNDARY` and was not read in full.
7. **Line numbers are HEAD `57d38ad`** and will move.

**CODE CHANGED: NO.**
