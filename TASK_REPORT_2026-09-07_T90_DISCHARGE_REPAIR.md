# T−90 discharge repair — identity and basis, for every kind

**Status:** complete. Governance repair only. **No predictive component was
touched.** G0A remains 11/12 and was not self-promoted.

---

## Commit SHAs

| SHA | content |
|---|---|
| `b1d8514` | HEAD at task start — "P4C-CARRY return", the report that found the defect |
| **`2e6cc2a`** | **the repair**: discharge semantics, new test suite, regression fixture, updated coverage tests |
| *(this report)* | `TASK_REPORT_2026-09-07_T90_DISCHARGE_REPAIR.md` |

---

## 1. The defect, stated exactly

`coverage.performed_from_manifest` emitted one **unattributed** entry per PASS
row — `(ts, source, None)` — with this comment:

```python
# Unattributed entry: still clears team-week kinds, where one fetch of a
# weekly report legitimately serves every game that team plays.
```

and `schedule._clears` required a matching `game_id` **only** for kinds inside
`GAME_SPECIFIC_KINDS = ('inactives',)`. `practice` is outside it. So any
in-window capture from an authorised source discharged a practice obligation.

On 2026-09-07 the `*/30` periodic vintage sweeps at **20:05:40Z** and
**20:37:36Z** discharged `2026_01_NE_SEA/practice_a` and
`2026_01_SF_LA/practice_mon`. No declaration, `PERIODIC_SWEEP` basis, `game_id`
`None`. Coverage reported **`PASS` with `covered: 2` and
`attributed_captures: 0` in the same summary**, 49.5 hours before the first real
T−90 window.

**The reasoning was wrong in the same way twice.** Artifact scope — what the
retrieved bytes cover — is not discharge authority. A weekly team report does
serve every game that team plays; that is a true statement about the bytes and
it says nothing about whether the execution knew which obligation it was
discharging.

---

## 2. The rule now implemented

> Every event-anchored coverage obligation requires an explicitly declared
> target identity and an authorised discharging execution basis.

Universal — not "only certain source kinds require game identity".

### `schedule._clears`

Requires, for **every** kind:

- `game_id` present and equal to the target's;
- `kind` equal to the target's, when carried;
- window membership and source authority via `target.discharges`.

An absent `game_id` now refuses unconditionally. The tuple was widened to
`(ts, source, game_id, kind)`; the 2- and 3-tuple shapes still parse and both
now refuse for want of identity.

**Carrying the kind is a new guard, not cosmetic.** `practice` and
`final_status` windows overlap, so without it a capture declared for one would
have silently cleared the other for the same game.

### `coverage.performed_from_manifest`

The unattributed entry is gone. A capture is dischargeable only via
`execution.eligible_targets`, which emits a `(game_id, kind)` pair only where
the run **declared that target before fetching** and `execution.eligibility`
then passed it on all of: capture state, source authority, execution basis,
`retrieved_at` inside that exact declared window, sha256, persisted blob and
provenance. Unattributed rows are counted (`unattributed_captures`) and
reported, and discharge nothing.

### `GAME_SPECIFIC_KINDS` — reviewed, and it was the wrong abstraction

The owner asked. It was wrong **as a discharge gate** and remains true **as
artifact scope**: inactives are per-game, a practice report is per team-week,
and that is why `execution.declare` may legitimately name several targets for
one fetch. So the constant is retained, retitled, and demoted out of the
discharge path — `test_discharge_identity` §L asserts **by AST** that neither
`schedule` nor `coverage` tests membership of it to decide anything (a grep
would have matched the docstring that explains it).

### `coverage.event_anchored` widened

From `GAME_SPECIFIC_KINDS` to every obligation-bearing kind: **16 → 63** week-1
targets. Restricting it understated the anchoring requirement by exactly the
`practice` / `final_status` set the false cover was discharged in.

### The four scopes are preserved

`source_artifact_scope` (LEAGUE_WIDE, unchanged), `execution_target_scope`
(where a game_id lives), parsed-row applicability (parser territory, untouched),
`coverage_obligation` (computed from the others). Multi-target discharge still
works and is tested — but only where the full target set was declared at
execution.

---

## 3. Requirement-by-requirement

| # | requirement | where it is enforced |
|---|---|---|
| 1 | target declared before retrieval | `execution.declare` at run start |
| 2 | exact target game declared | `declare` → `targets[].game_id` |
| 3 | exact kind/window declared | `declare` → `kind`, `window_*_utc` |
| 4 | scheduled anchored basis | `DISCHARGING_BASES = (BASIS_ANCHORED,)` |
| 5 | authorised source | `registry.can_discharge` |
| 6 | non-empty persisted raw bytes | `eligibility` blob check + `_blob_ok` |
| 7 | valid `retrieved_at` | `eligibility`; undated PASS rows BLOCK |
| 8 | inside that exact target's window | `eligibility` per declared target |
| 9 | immutable sha / content-addressed | `_blob_ok` re-hashes the file |
| 10 | manifest PASS | reader skips non-PASS |
| 11 | exact target attribution | `eligible_targets` → `(game_id, kind)` |
| 12 | coverage independently re-verifies | `_blob_ok` + `_clears` re-check |
| 13 | sweep cannot certify on timing | **`_clears` refuses an absent game_id** |

---

## 4. New tests — `nfl/tests/test_discharge_identity.py`, 50 assertions

All sixteen required cases:

| # | case | section | result |
|---|---|---|---|
| 1 | periodic **practice** capture in window does not discharge | A | refused |
| 2 | periodic **injury** capture in window does not discharge | A | refused |
| 3 | periodic **inactives** capture in window does not discharge | A | refused |
| 4 | manual dispatch without anchored basis | B | `MANUAL_DISPATCH_NOT_SELF_CERTIFYING`; sweep, local and unknown bases also refused |
| 5 | `game_id=None` cannot discharge | C | refused |
| 6 | wrong-game attribution | C | refused |
| 7 | wrong target kind | C | refused |
| 8 | correct game, undeclared target | C | never emitted |
| 9 | attribution created after retrieval | D | legacy `discharge_claims` not honoured; refused-eligibility rows not emitted |
| 10 | timestamp coincidence infers nothing | E | refused at three offsets inside the window |
| 11 | predeclared anchored **practice** capture | F | **discharges**, and only its own game |
| 12 | predeclared anchored **inactives** capture | F | **discharges**, and only its own game |
| 13 | predeclared multi-target execution | G | both declared targets discharge; an undeclared third game is untouched; artifact scope stays LEAGUE_WIDE |
| 14 | **guard deletion — execution basis** | H | see below |
| 15 | **guard deletion — explicit target** | I | see below |
| 16 | the two real false positives replayed | J | both sweeps are **inside the window** and **refused**, for both targets |

Plus §K (the live manifest state) and §L (the AST assertion on
`GAME_SPECIFIC_KINDS`).

### Guard-deletion proofs

**Three, where two were required.**

| proof | evidence |
|---|---|
| **§H** widen `DISCHARGING_BASES` to include `PERIODIC_SWEEP` | clean: `n_eligible = 0`; bypassed: `n_eligible = 1`. The tuple is the guard. |
| **§I** restore the pre-repair `_clears` predicate | clean: unattributed refused; bypassed: covered again. |
| **`test_coverage` §I** restore **both** pre-repair layers, end to end | clean: `covered = 0`; bypassed: **`covered = 2` from an unattributed periodic capture** — the regression reproduced through the real code path. And deleting only `_clears` gives `covered = 0`, because the reader no longer emits an unattributed capture for it to accept: **both layers are load-bearing.** |

---

## 5. Full repository test suite — actually executed

```
test_attribution.py                9 passed, 0 failed
test_capture_schedule.py          99 passed, 0 failed
test_capture_states.py           107 passed, 0 failed
test_capture_windows.py          107 passed, 0 failed
test_coverage.py                  52 passed, 0 failed
test_denominator_validation.py    61 passed, 0 failed
test_discharge_identity.py        50 passed, 0 failed     <- new
test_effective_scope.py          100 passed, 0 failed
test_execution_target.py          84 passed, 0 failed
test_identifier_mapping.py        61 passed, 0 failed
test_injury_parser.py             85 passed, 0 failed
test_preflight.py                 14 passed, 0 failed
test_quarantine.py                64 passed, 0 failed
test_seal_ordering.py             97 passed, 0 failed
test_source_registry.py          122 passed, 0 failed
test_t90_workflow.py              41 passed, 0 failed
test_volatility.py                35 passed, 1 failed
  NFL: 1188 passed, 1 failed
test_outcome.py                   47 passed, 0 failed
test_provenance.py                21 passed, 0 failed
test_scorecard.py                 25 passed, 0 failed
  governance: 93 passed, 0 failed

TOTAL ASSERTIONS: 1282   PASSED: 1281   FAILED: 1
```

Pre-flight: **10 checks, 0 failing.**

### Exact previously failing tests, and their state now

| test | assertion | before | after |
|---|---|---|---|
| `test_coverage.py` §A | "the game-level answer is never PASS while nothing has come due" | **FAIL** | **pass** |
| `test_preflight.py` §A | "every check passes today" | **FAIL** | **pass** |
| `test_preflight.py` §A | "and it is reported as not yet covered" (`TARGET_OPEN`) | **FAIL** | **pass** |
| `test_preflight.py` §F | "and the real state is open" | **FAIL** | **pass** |

**All four of the regression's own failures are repaired.**

### Tests I changed, and why each change was necessary rather than convenient

| test | change | reason |
|---|---|---|
| `test_coverage` §E2 (3 assertions) | assert on `n_pass_rows` / `n_unattributed` instead of `n_captures` | `n_captures` now counts *dischargeable* captures, legitimately 0. The property this test guards — the 54-of-60 dropped-rows bug — is unchanged and is now asserted as `n_captures + n_unattributed == n_pass_rows`, **on the rows**, so the original drop would still fail it. A third assertion was added, not removed. |
| `test_coverage` §H (1 assertion) | `n_windows == 16` → `== every obligation-bearing target` and `> 16` | the widened `event_anchored` scope. A companion assertion pins the 16 inactives targets as a strict subset, so the old fact is still checked. |
| `test_coverage` §I (2 assertions) | rewritten as a two-layer end-to-end guard-deletion proof | the guard moved from one layer to two; the rewrite is **stronger** — it reproduces `covered = 2` through the real code path and proves each layer alone is insufficient. |

Net: `test_coverage` went 50 → 52 assertions. Nothing was deleted to get green.

### The one remaining failure, and why I did not touch it

`test_volatility.py`: *"official_inactives: and the collapse is substantial,
not cosmetic — 15 substantive of 43 raw"*, against `len(subs) <= max(2,
len(raws) // 3)`, i.e. a threshold of 14. It fails by one.

**Confirmed pre-existing and unrelated.** I re-ran it with my changes stashed:
**35 passed, 1 failed** at the pre-repair HEAD. The module imports nothing from
`coverage` or `schedule` (0 references).

**Cause:** the ratio was calibrated when the bot held ~8 blobs. As the season
approaches, the injury report genuinely changes content day to day, so the
substantive count rises for a real reason — that is the mask working, not
failing.

**I did not adjust the threshold.** Loosening a live-data assertion to turn a
suite green is the anti-pattern this project refuses, and it is a different
defect from the one I was sent to fix. The right repair keys the assertion to
the durable property — that the mask collapses *render nonce* churn, tested
against known-identical pages — rather than to a ratio that must drift. Logged
as a debt in §7.

---

## 6. Evidence

### The two false targets are no longer covered

```
2026_01_NE_SEA/practice_a   kind=practice: clearing captures = 0  -> NOT COVERED
2026_01_SF_LA/practice_mon  kind=practice: clearing captures = 0  -> NOT COVERED
```

Coverage summary now:

```
state: DEFERRED[NO_WINDOW_HAS_CLOSED_YET]
covered=0  missed=0  not_yet_due=63  of 63
attributed_captures=0  dischargeable_captures=0
unattributed_captures=316  total_pass_rows=316
```

`covered` and `attributed_captures` can no longer disagree — asserted in
`test_discharge_identity` §K.

### The historical periodic captures remain persisted

```
manifest rows: 415  (append-only file, not rewritten)
dated PASS rows read: 316
classified unattributed (kept, ineligible to discharge): 316
sweep 20:05:40Z still in the manifest: True
sweep 20:37:36Z still in the manifest: True
official_injury_report blobs on disk: 43
git diff HEAD -- nfl/vintage_manifest.jsonl nfl/vintage/  ->  (empty)
```

**No raw capture was deleted and no manifest was rewritten.** The captures
happened, they are real evidence, and they are now correctly classified as
ineligible to discharge.

### The regression itself is preserved

`nfl/tests/fixtures/regression_2026_09_07_practice_false_cover.json` records
the observed bad state — the `PASS`/`covered: 2`/`attributed_captures: 0`
summary, both target specifications, both discharging sweeps with their bases
and commit names, the mechanism, the rule violated, and the four failing
assertions. `test_discharge_identity` §J replays it from that file.

### The real future T−90 obligation remains pending

```
first inactives T-90 target: 2026_01_NE_SEA
  window 2026-09-09T22:50:00Z -> 2026-09-10T00:10:00Z  (opens in 48.7h)
  pending, not covered: True
```

---

## 7. Unresolved debts

- **`test_volatility` live-data ratio** (§5). Pre-existing, unrelated, not
  loosened. Needs an assertion keyed to the durable property rather than a
  count ratio.
- **`RAW_SHA256_MISMATCH` on `depth_charts` and `weekly_rosters`** in ~100
  manifest rows, surfaced by the artifact verifier. Pre-existing, excluded from
  discharge already, and outside this directive.
- The `.reduced` blobs are named for a digest that is not their own — recorded
  in the `_blob_ok` docstring, still true.

---

## 8. G0A

**G0A remains 11 PASS / 1 FAIL. I did not self-promote it and did not edit any
G0A record.** This repair restored the honest state; it did not produce
evidence. Item 1 still requires a genuine unattended event-anchored T−90
execution inside the authorised real window, with the persisted evidence
passing owner review. **A synthetic, manual or pre-flight run cannot satisfy
it**, and nothing in this task attempted one. The first window opens in 48.7
hours.

---

## Constraints honoured

P4C-CARRY untouched and its findings unchanged (share 50.1%, team volume 29.8%,
appearance 20.0%). No player-share redesign, no RB-competition fix, no
low-history allocation fix, no appearance change, no team-volume change, no
rushing-conversion change. No P5B, receiving, targets, touchdowns or J0. No
markets, no DFS, no fantasy. NFL-1 not authorised. **T−90 was modified only in
the discharge semantics this directive ordered repaired**, and G0A was not
touched. No 2026 outcome consumed.

**Stopping here, as instructed.**
