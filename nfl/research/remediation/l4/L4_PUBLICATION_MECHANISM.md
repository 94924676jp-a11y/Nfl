# L4 — the publication mechanism

**Repo** `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD at start `9c3c29a`. Interpreter `python3.12`.
**Files changed:** `nfl/production/authorization.py` and new
`nfl/tests/test_may_publish.py` — the two I own exclusively. Nothing else in
the repository was edited. No commit, no add, no stash, no push.

**No candidate was promoted, NFL-1 was not authorized, nothing is COMPLETE, and
no Wave-7 level assignment was activated.** See §7, which checks that last
claim mechanically rather than asserting it.

---

## 1. The defect, restated from the code

`may_publish()` took zero arguments. It read `PATH_C_STATE.gates.NFL_1` and an
owner authorization record, and returned one answer for the whole board. Four
call sites consume it — `run_forecast.py:1912`, `product/board.py:270`,
`nonqb/slate_rehearsal.py:88`, `nonqb/engine_rehearsal.py:190` — and every one
of them got the same verdict for every number on the slate.

So the facts commit `8c22815` had just repaired into the seal arrived somewhere
that could do nothing with them. The consequence is visible in the sealed runs:
a board whose receiving layer publishes `CALIBRATION_DEFECT` and a board whose
receiving layer does not are indistinguishable at the gate, because the gate
never looks at either.

---

## 2. The new signature, and every fact it consumes

```python
may_publish(ctx: PublicationContext | None = None) -> Outcome
```

`ctx=None` answers the board-wide question **exactly as before** — same state,
same codes, same `gates` evidence — so the four existing call sites are
unchanged and `test_production_pipeline`, `test_product_orchestration` and
`test_governance_transport` all still pass untouched. What is added is that the
context-free answer now declares its own scope:

```
evidence['scope']             = 'BOARD_WIDE'
evidence['metric_decision']   = 'NOT_MADE'
evidence['why_no_metric_decision'] = 'may_publish() was called without a
    PublicationContext, so no per-run, per-metric rule could be evaluated...'
```

A caller that has not been wired is now visible in the artifact instead of
being served a metric-shaped answer to a board-shaped question.

### The context

`PublicationContext` is a frozen dataclass with **thirteen fields and no
defaults**. `authorization.context(**facts)` is the constructor; it is
keyword-only, every declared field is required, an omitted field raises
`PUBLICATION_CONTEXT_INCOMPLETE` and an undeclared field raises
`PUBLICATION_CONTEXT_UNKNOWN_FACT`. A caller that does not hold a fact passes
the sentinel `authorization.NOT_SUPPLIED` **explicitly**.

| Fact | Source it comes from |
|---|---|
| `run_id` | `run_status.run_id` |
| `metric` | `product.metrics.SUPPORTED` key, e.g. `receiving/receiving_yards` |
| `layer` | eligibility/PATH_C_STATE layer name, e.g. `receiving_conversion` |
| `model_configuration` | `candidate_mode.MODES` |
| `chronology` | `{family: verdict}` in `vintage_selector.CHRONOLOGY` |
| `eligibility` | `eligibility.matrix()[layer]` |
| `hard_invariants` | `draw_coherence` verdict + `accounting_verdicts` |
| `warnings` | `run_status.stages[].warnings_detail` (WS-D) |
| `governance` | `run_status.stages[].governance` (WS-D) |
| `spec_version` | `run_status.stages[].spec_version` (WS-D, composed) |
| `completeness` | `run_status.completeness` / `artifact.COMPLETENESS` |
| `model_health` | a `model_health.evaluate()` row, or `None`, or NOT_SUPPLIED |
| `test_only` | the TEST_ONLY fixture quarantine flag |
| `dry_run` | `run_status.dry_run` |

`spec_version` is a channel I added after measuring that leaving it out missed
two of the four tokens Wave 7 calls transport-blocked.
`layers.SPEC['targets_carries']` is `p4c-system-C-frozen; governance
DATA_BLOCKED` and `layers.SPEC['appearance']` carries
`INFORMATION_CONSTRAINED` the same way — **neither layer passes a `governance=`
key at all**, so a scan of only the governance records and the warnings would
have missed `DATA_BLOCKED` and `INFORMATION_CONSTRAINED` entirely. That would
have been a mechanism built to read the tokens, missing half of them.

`dry_run` was added after finding that `make_board.build_one` passes
`dry_run=True` on **every board it has ever produced**, and that nothing at the
gate read it. `run_forecast`'s own `--dry-run` help says *"historical fixture
run; NEVER prospective evidence"*. That is an existing declaration, not a new
policy; the rule reads it at the gate instead of leaving it in a help string.

### NOT_SUPPLIED is not `None`

`None` is a lawful value for several of these — a metric with no model-health
row genuinely has none. "We could not supply this" is a different statement and
the two must not collapse. `NOT_SUPPLIED` is a singleton that **raises on
`bool()`** (`NOT_SUPPLIED_TRUTHINESS`), mirroring `Outcome.__bool__`, so
`if fact:` cannot turn "we did not ask" into "it was fine".

---

## 3. How UNDECIDED is represented, distinctly

Four verdicts, composed worst-first and never averaged:

```
REFUSE       4   a settled rule, on these facts, refuses
UNEVALUABLE  3   the fact the rule takes was not supplied
UNDECIDED    2   no rule has been set; here is every input it would take
ALLOW        1   a settled rule, on these facts, permits
```

`UNEVALUABLE` deliberately outranks `UNDECIDED`: *"we do not know the fact"* is
a worse position than *"we know the fact and no rule has been set for it"*, and
reporting the second while the first is true overstates what the board knows.

At the `Outcome` level the three are **three different states**, not three
strings:

| Disposition | Outcome | Code |
|---|---|---|
| ALLOW | `PASS` | `PUBLICATION_AUTHORIZED` |
| REFUSE | `BLOCKED` cause `GOVERNANCE` | `NFL1_NOT_AUTHORIZED` / `PUBLICATION_REFUSED` |
| UNEVALUABLE | `BLOCKED` cause `DATA` | `PUBLICATION_FACTS_NOT_SUPPLIED` |
| UNDECIDED | `DEFERRED` | `PUBLICATION_RULE_UNDECIDED` |

`DEFERRED` is the right state and the platform already says why: *"not yet, and
it remains OWED until something closes it"*. An unsettled publication rule is
exactly a debt. The Outcome's `owed` payload carries every missing ruling by
name. Its detail says, verbatim, that the number *"is neither published nor
withheld by this mechanism"*.

### Two dispositions, kept apart

`decide(ctx)` returns `board_disposition`, `metric_disposition`,
`ranking_disposition` and the composed `disposition`. Collapsing board and
metric is the original defect, so they are never merged into one number.
Ranking is a third axis and is **excluded from the composed answer**:
`product/model_health.py` says in its own words that a warning makes a metric
ineligible for ranking and *"does not delete the row"*. A ranking refusal
therefore lands in `ranking_refusals`, not `refusals`, and cannot block
publication.

### A refusal never truncates the report

Tonight the board gate refuses. The per-metric findings are still computed and
still ride in the evidence, and the refusal's own detail names them:

```
BLOCKED[NFL1_NOT_AUTHORIZED] ... ALSO UNDECIDED, and reported rather than
hidden behind the refusal: ['ELIGIBILITY_VS_PRODUCT_STATUS',
'LAYER_GOVERNANCE_TOKEN:CALIBRATION_DEFECT@governance:receiving_conversion',
'LAYER_GOVERNANCE_TOKEN:HOLD_CHARACTERIZED@governance:receiving_conversion',
'LAYER_GOVERNANCE_TOKEN:SIGNAL_WEAK@warning:receiving_conversion',
'MODEL_HEALTH_PUBLICATION'].
```

---

## 4. The declared rules

Precedence is the declared order, so a reader can predict which refusal a run
reports without running it. A verdict of ALLOW or REFUSE **must** name the
authority that settled it (`PUBLICATION_RULE_WITHOUT_AUTHORITY` otherwise), and
an UNDECIDED **must not** name one.

**Settled — each reads a ruling that already exists in this repository:**

| Rule | Scope | Authority |
|---|---|---|
| `NFL1_AUTHORIZATION` | BOARD | owner gate + owner authorization record |
| `TEST_ONLY_DATA` | METRIC | `layers.assert_publishable` fixture quarantine |
| `DRY_RUN` | METRIC | `run_forecast --dry-run`: "NEVER prospective evidence" |
| `METRIC_HAS_GOVERNED_CONTROL` | METRIC | `product.metrics` SUPPORTED / UNSUPPORTED |
| `HARD_INVARIANT_STATE` | METRIC | `artifact.HARD_REFUSING_STATES` (FAIL/BLOCKED only) |
| `CHRONOLOGY_LAWFUL` | METRIC | `vintage_selector` closed vocabulary; `refusal.SOURCE_TOO_LATE` |
| `CANDIDATE_CONFIGURATION` | METRIC | `candidate_mode`: candidate components are REHEARSAL_ONLY |
| `MODEL_HEALTH_RANKING` | **RANKING** | `model_health.assert_ranking_admissible` |

**Undecided — no ruling exists, and this file does not write one:**

| Rule | What is owed |
|---|---|
| `LAYER_GOVERNANCE_TOKEN:<token>` | the publication level for that token |
| `ELIGIBILITY_VS_PRODUCT_STATUS` | which of `eligibility.matrix()` and `product.metrics` governs publication |
| `HARD_INVARIANT_UNEVALUATED_AT_PUBLICATION` | treatment of HARD DEFERRED / HARD NOT_APPLICABLE at the publication boundary |
| `COMPLETENESS` | whether a PARTIAL board may publish, and separately whether it may be *called* complete |
| `MODEL_HEALTH_PUBLICATION` | whether a metric under a health warning may publish (health rules only on ranking) |

### The token vocabulary is derived, not retyped

`governance_tokens()` reads `PATH_C_STATE.axes.action` and removes
`eligibility.PRODUCTION_ACTIONS`. A token added to the governance artifact is
weighed here without an edit, and the test asserts the file contains no retyped
copy of the axis. `SIGNAL_WEAK` is the exception and is carried **with its
provenance defect attached** — `UNREGISTERED: no PATH_C_STATE home; layer-
authored free text` — rather than being quietly promoted to the standing of a
registered state. Wave 7 row 3 makes the same observation.

### Two contradictions are surfaced, not resolved

1. **`eligibility.matrix()` vs `product.metrics`.** The matrix records all ten
   pipeline layers `publication_eligible: False` — a *constant* False whose
   in-code reason is "NFL-1 gates everything anyway" — while `metrics.py` marks
   13 of 20 SUPPORTED entries `MODELED` and `daily_board.eligibility` ranks on
   exactly that status. The rule emits UNDECIDED with a `contradiction: true`
   fact and both sides attached. It does not pick a winner.
2. **A stage-name mismatch that silently voided the join.** `run_status` names
   the stage `conversion`; eligibility and PATH_C_STATE name the layer
   `receiving_conversion`. Measured: `eligibility.matrix().get('conversion')`
   returns nothing, so reading a sealed run by its stage name yields **no
   eligibility row at all** and the layer's governance state never reaches the
   metric. `METRIC_ORIGIN` declares both names per metric, and
   `assert_metric_origin_complete()` fails if the product contract gains a
   metric the table does not place, so the join cannot go quietly stale. It is
   declared here only because `run_forecast.STAGE_LAYERS` — which holds the
   same join — is a local inside `build` and cannot be imported.

### A green suite is now refused mechanically

`authorization.py` has always said in prose that there is no path from a green
test suite to authorization. A context object creates somewhere to *try*, so
`context()` raises `ForbiddenBasis` on any of
`tests_passed, suite_green, suite, test_result, checklist,
checklist_discharged, override, force, authorized, authorize, publish`.
No rule in the file reads a test result.

---

## 5. What changes for tonight's board

Measured on a real sealed run,
`nfl/research/live/2026_01_GB_MIN/post_inactives_V1_CANDIDATE_R8/b14c40c4d6005b6b/`,
through `decide_board`:

```
qb/att                     board=REFUSE  metric=REFUSE       rank=REFUSE
...
receiving/targets          board=REFUSE  metric=REFUSE       rank=ALLOW
receiving/receiving_yards  board=REFUSE  metric=REFUSE       rank=REFUSE
```

`metric=REFUSE` on that run is `DRY_RUN` — every board in the tree was built
with `dry_run=True`. The findings underneath are still complete, and for
`receiving/receiving_yards` they read:

```
REFUSE       NFL1_AUTHORIZATION
UNEVALUABLE  TEST_ONLY_DATA
REFUSE       DRY_RUN
ALLOW        METRIC_HAS_GOVERNED_CONTROL
ALLOW        HARD_INVARIANT_STATE
ALLOW        CHRONOLOGY_LAWFUL
UNEVALUABLE  CANDIDATE_CONFIGURATION
UNDECIDED    ELIGIBILITY_VS_PRODUCT_STATUS
UNDECIDED    LAYER_GOVERNANCE_TOKEN:CALIBRATION_DEFECT@spec_version:receiving_conversion
UNDECIDED    LAYER_GOVERNANCE_TOKEN:HOLD_CHARACTERIZED@spec_version:receiving_conversion
UNDECIDED    LAYER_GOVERNANCE_TOKEN:SIGNAL_WEAK@spec_version:receiving_conversion
UNDECIDED    HARD_INVARIANT_UNEVALUATED_AT_PUBLICATION
UNEVALUABLE  COMPLETENESS
REFUSE       MODEL_HEALTH_RANKING
UNDECIDED    MODEL_HEALTH_PUBLICATION
```

That is the design target: every input to the unset rule attached, an explicit
UNDECIDED on each unset rule, nothing silently published and nothing silently
withheld.

On a **live, non-dry, WS-D-transported** run with the corrected health artifact
supplied, the same board reads (simulated on the real transport shape):

```
receiving/receiving_yards  metric=UNDECIDED  rank=REFUSE  tokens=[CALIBRATION_DEFECT, HOLD_CHARACTERIZED, SIGNAL_WEAK]
receiving/receptions       metric=UNDECIDED  rank=REFUSE  tokens=[CALIBRATION_DEFECT, HOLD_CHARACTERIZED, SIGNAL_WEAK]
receiving/targets          metric=UNDECIDED  rank=ALLOW   tokens=[DATA_BLOCKED]
rushing/carries            metric=UNDECIDED  rank=REFUSE  tokens=[DATA_BLOCKED]
receiving/receiving_td     metric=UNEVALUABLE rank=UNEVALUABLE tokens=[HOLD_TENTATIVE]
qb/ryds                    metric=UNEVALUABLE rank=UNEVALUABLE tokens=[]
qb/att                     metric=UNDECIDED  rank=REFUSE  tokens=[]
```

Three things to read off that. The tokens now reach a decision point and are
reported per metric. `receiving/targets` is the one metric `model_health`
finds rankable, and it is still UNDECIDED for publication — ranking and
publication are visibly different answers about the same number. The
`UNEVALUABLE` rows are metrics with **no** model-health row: nothing has been
measured about them, and that reads as unevaluable rather than as clean.

---

## 6. The un-applied call-site patches

**Not applied. Handed over for integration.** Both were generated against
copies, syntax-checked with `ast.parse`, and the working tree of
`run_forecast.py` and `make_board.py` is untouched — `git status` shows neither.

### Patch A — `nfl/production/run_forecast.py` (~line 1911)

Records the SCOPE of the seal-time answer. It does **not** make a per-metric
decision there, because the seal does not hold the chronology verdicts (they
live in the board's vintage selection) or model health (a graded research
artifact whose vintage the caller must vouch for), and supplying either from
`build` would be inventing a fact to make a decision look complete.

```diff
     # publication is a SEPARATE gate and is checked last, never assumed
+    # [comment: a seal cannot make a per-metric decision and must say so]
     pub = AUTH.may_publish()
     summary['publication'] = {'state': pub.state.value, 'code': pub.code,
-                              'detail': pub.detail[:200]}
+                              'detail': pub.detail[:200],
+                              'scope': pub.evidence.get('scope'),
+                              'metric_decision': pub.evidence.get(
+                                  'metric_decision'),
+                              'mechanism_spec_version': pub.evidence.get(
+                                  'spec_version')}
```

### Patch B — `nfl/tools/make_board.py`

Adds `AUTH` and `VS` imports, a `model_health_path` parameter and a
`--model-health` flag, and after `bd` is assembled:

```python
chronology = {name: (VS.LAWFUL if rec['observed_at'] < written_at
                     else VS.REJECT_LATE)
              for name, rec in info['sources'].items()}
health = AUTH.NOT_SUPPLIED
if model_health_path:
    _h = json.loads(pathlib.Path(model_health_path).read_text())
    _d = str(_h.get('date') or '')
    if not _d or _d >= written_at[:10]:
        raise SystemExit('MODEL_HEALTH_NOT_BEFORE_CUT: ...')
    health = {r['metric']: r for r in (_h.get('metrics') or [])}
bd['publication_decisions'] = AUTH.decide_board(
    summary, chronology=chronology, model_health=health)
bd['publication_mechanism'] = {..., 'wave7_levels_activated': []}
```

plus a per-metric disposition line in `main()`'s printout.

Two things in Patch B are load-bearing and should be read before it lands.

**Chronology is carried, not re-asserted.** Every source in `info` is already
compared against `written_at` a hundred lines above and the build raises
`SOURCE_AFTER_WRITTEN_AT` if any is not earlier. The dict reports that check's
result in the selector's own closed vocabulary; it cannot disagree with it.

**Model health is refused if its vintage is not strictly before the cut.** It is
graded on realised outcomes, so loading one whose scored games include this
board's own game would carry post-kickoff information into a pregame artifact.
Absent a path the facts are `NOT_SUPPLIED`, the health rules answer
UNEVALUABLE, and the board says so — the honest answer, not a failure.

The full unified diff is reproducible from this description; I did not write it
into the tree because the files are not mine to touch.

---

## 7. No Wave-7 level assignment was activated

`nfl/research/remediation/wave7/GOVERNANCE_RECOMMENDATION_MATRIX.md` was read
for the shape of the decision. **None of its level assignments is implemented.**
This is checked, not asserted:

- every `LAYER_GOVERNANCE_TOKEN:*` finding resolves `UNDECIDED` with
  `authority is None`;
- `_finding` **raises** if an UNDECIDED verdict carries an authority, and raises
  if an ALLOW or REFUSE does not;
- `decide()` emits `wave7_matrix: {path, status: 'RECOMMENDATION AWAITING
  OWNER RULING -- NO LEVEL ACTIVATED', levels_activated: []}`;
- the test greps `authorization.py` and fails if the strings `L1`–`L5` appear
  anywhere in it.

The matrix's own §2 says four tokens were transport-blocked. They are no longer
blocked and they are no longer silently at "Level 1 by accident of plumbing"
either — they are explicitly UNDECIDED, which is the state the matrix says is
better than an undeclared one.

---

## 8. Tests

`nfl/tests/test_may_publish.py`, run only through the sanctioned runner:

```
python3.12 nfl/tests/run_suite.py --only test_may_publish
modules 1  test functions 25  checks 94  FAILING CHECKS 0  RAISED 0
ZERO-CHECK FUNCTIONS 0  BLOCKED FUNCTIONS 0
SUITE PASS
```

What it proves, beyond the per-rule cases: the zero-argument call is unchanged
in state, code, cause and gate evidence; all three of ALLOW / REFUSE /
UNDECIDED are reachable and are three distinct `State` values; **withholding
any one of ten facts can never produce a PASS**; one silent channel next to an
empty one is UNEVALUABLE rather than "no token raised"; a ranking refusal does
not become a publication refusal; two metrics on one run and two runs of one
metric get different answers; and the token vocabulary is read from
`PATH_C_STATE` rather than retyped.

Two fixtures are labelled in the file as fixtures and assert their own
unreality: `_hypothetically_eligible()` asserts that **no** layer is
`publication_eligible` today, and the ALLOW case asserts that **every**
non-None `layers.SPEC` entry names a governance token. They exist so the ALLOW
branch is reachable at all — a mechanism whose "yes" cannot be exercised has
not been shown to have one — and neither is a claim about any layer.

Regression: `test_production_pipeline` (69 checks), `test_product_orchestration`
(52), `test_governance_transport` (74), `test_prospective_contract` (63),
`test_availability_watch` (114) and `test_availability_retention` (70) all
still PASS unchanged. Those six are every module in the tree that imports
`authorization`.

### The full-suite run, and why its FAIL is not a result

A whole-tree `run_suite.py` was launched in parallel and reported **SUITE
FAIL** on three modules. All three are **torn reads of a shared working tree**,
not failures, and none involves `authorization.py`:

| Module | Reported | Diagnosis |
|---|---|---|
| `test_persisted_provenance` | `AttributeError: module 'nfl.capture.persisted_provenance' has no attribute 'defect_rows'` | `nfl/capture/**` is L1's, and both the module and its test were mid-edit (`M` in `git status`) |
| `test_r5_active_pool` | 2 checks: "the R5 branch returns a fatal on a status refusal" / "and on an empty pool" | both are **source-text greps** of `nfl/production/run_forecast.py`, which another agent was rewriting during the run (+109 lines) |
| `test_r8_synthesis` | "run_forecast refuses an ambiguous appearance spec" | same file, same window, same cause |

Re-run afterwards, all three PASS: `test_r5_active_pool` 21 checks,
`test_r8_synthesis` 69 checks, `test_persisted_provenance` 94 checks, zero
failing in each. The two grep anchors were also checked against the **committed
HEAD** copy of `run_forecast.py` and against the working tree, and both are
present in both — so there was never a version of that file in which the
property was absent; the suite simply read it between two writes.

**The honest statement is therefore: the full suite has not been observed green
on this tree, because the tree was being edited by other agents while it ran.**
That is a statement about the measurement, not about this work. What is
established is the six authorization-importing suites plus these three, all
re-run individually and all passing, and none of the three failures touched a
line L4 wrote.

---

## 9. What I did not do, and what is still owed

- **No policy was set.** Which token blocks publication is an owner ruling.
- **No contradiction was resolved by fiat.** The eligibility-vs-metrics
  disagreement and the constant-False `publication_eligible` are surfaced with
  both sides attached.
- **`assert_no_stale_labels` is still a guard that cannot fire** (case-sensitive,
  same-line, single-file default). It is in `eligibility.py`, which I do not
  own. Not touched.
- **`nfl/product/model_health.py` is still orphaned** in the sense that
  `assert_ranking_admissible` has no caller. The mechanism now consumes a
  health *row* and reproduces the ranking rule as a scoped finding, but wiring
  `assert_ranking_admissible` into the ranked table is a `daily_board` /
  `market_comparison` change and those are not mine.
- **The rulings owed** are enumerated by the mechanism itself, per metric, in
  `decision.owed_rulings`. That list is the input to the next owner session and
  it is derived from the run rather than from this document.
