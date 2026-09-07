# Task report — Directive 7: the event-targeted T−90 capture path

**Date:** 2026-09-07
**Repository:** `94924676jp-a11y/nfl`, `main`
**G0A:** **11/12**. Item 1: **PARTIAL / PENDING REAL EVENT**.
**NFL-1:** not authorized, not executed, not requested.

---

## 1. Repository HEAD

`8fe3b79` — *Declare the execution target before fetching; retire post-hoc
attribution*.

## 2. Test count

**1,220 assertions across 19 suites, 0 failing.** New this task:

| Suite | Assertions |
|---|---|
| `test_execution_target.py` | 84 |
| `test_preflight.py` | 14 |
| `test_attribution.py` | rewritten, 46 → 9 (see §4) |

---

## 3. Event-anchored execution architecture

Directive 7 §6 named a real defect in what I built yesterday, and it is the
centre of this task.

`attribution.claims_for` computed a capture's target set from `retrieved_at` — a
clock that exists **only after the bytes arrive**. Every claim it produced was a
post-hoc reading of a timestamp. A capture that wandered into a window by
coincidence and one taken *because* that window was open produced identical
records. §2 requires a `game_id` to mean the execution was intentionally
scheduled for that obligation, and a timestamp cannot express intent.

So intent is now **declared before the fetch**:

```
run start
  → build the nearby plan from the captured schedule snapshot
  → declare(): which targets' windows contain this instant, + executor identity
  → [ declaration is fixed; every row of this execution carries it ]
  → fetch each source
  → eligibility(): judge THESE bytes against THOSE declared targets
  → manifest
  → coverage: re-verify everything from persisted artifacts
```

`nfl/tools/gen_t90_schedule.py` generates the cron from real kickoff times (16
entries, 6 windows, 5-minute step, 102 nominal firings all inside a window). No
second schedule system: the generator, the declaration and coverage all read the
same `capture_plan`.

### The declaration basis, and what may discharge

| Basis | When | Can discharge |
|---|---|---|
| `SCHEDULED_WINDOW_ANCHORED` | anchored workflow, `event_name == schedule` | **yes** |
| `OPERATOR_TARGETED` | anchored workflow, manually dispatched | no |
| `PERIODIC_SWEEP` | the `*/30` baseline, or any unrecognised workflow | no |
| `LOCAL_INVOCATION` | a developer's machine | no |

**This reverses something I told you yesterday.** I said a baseline run landing
inside a window "counts exactly the same". Under §5 — *"a generic background
capture does not discharge it"* — it does not, and the directive is right. The
point of anchoring is that the execution knew what it was for.

Manual dispatch is excluded too. §11 says a dispatched run is not equivalent
proof, and a mechanism that let me dispatch during a live window and record a
discharge would be a way to hand-write the result of the one test this gate
exists for.

Unknown workflows fall back to `PERIODIC_SWEEP` — the default is the class that
cannot certify anything.

---

## 4. Exact game-attribution semantics

Four scopes, four fields, never merged (§2):

| Scope | Value | Meaning |
|---|---|---|
| `source_artifact_scope` | `LEAGUE_WIDE` | The page covers every game. Fetching it for one target does not make it that target's document. |
| `execution_target_scope` | `execution_target.targets[]` | The obligations this run set out to satisfy. **This is where a game_id lives.** |
| parsed-row applicability | — | Parser territory. Not decided here at all. |
| `coverage_obligation` | `discharge_eligibility.targets[]` | What this capture is *permitted* to discharge, computed from the other three plus the evidence. |

Collapsing any two produces a specific lie. The first two collapsed says the
league page is a document about one game. The second and fourth collapsed says
intending to capture something is the same as having captured it.

**`attribution.py` is retired** to a stub that raises `RetiredMechanism`,
keeping only the legacy reader. A stub rather than a deletion because §3 warns
against a second competing mechanism, and a deleted file can be re-added by
someone who remembers it working. The 6 pre-Directive-7 rows in the manifest
stay readable and discharge nothing; `test_attribution.py` now proves the
retirement holds rather than proving the old path worked.

---

## 5. Manifest fields added

On **every** row of an execution — including `BLOCKED`, `DEFERRED` and sources
that never ran, because §14 requires an attempt to stay visible:

```
execution_target:                       discharge_eligibility:
  declaration_version                     source_artifact_scope   LEAGUE_WIDE
  declared_at                             scope_note
  declared_before_fetch  true             evaluated_at_clock      retrieved_at
  basis / basis_can_discharge             targets[]:
  executor:                                 game_id, kind
    workflow, run_id, run_attempt,          eligible (bool)
    run_number, event_name,                 refusals[]   (named)
    repository, ref, sha, runner_os         window_start/end_utc, kickoff_utc
  plan_snapshot                           n_eligible
  targets[]: game_id, kind, label,
    window_start/end_utc, due_utc,
    kickoff_utc, cadence_confirmed
```

Already present and unchanged: `requested_at`, `provenance.retrieved_at`,
`provenance.source_timestamp`, `sha256`, `blob`, `blob_durable`, `http_status`,
`substantive`, `effective_scope`.

`kickoff_utc` is new on every `CaptureDue`: §4 requires it, and for a practice
target it is **not** recoverable from `due_utc` — that is a filing deadline days
earlier, tied to no fixed offset from the game.

Append-only preserved. Nothing rewritten.

---

## 6. Coverage / discharge rule

A target is covered only when **all** hold:

1. manifest row state is `PASS`;
2. source authorised for that kind (`can_discharge`);
3. the run **declared** this exact target before fetching;
4. declaration basis is `SCHEDULED_WINDOW_ANCHORED`;
5. `retrieved_at` inside **this game's** T−90 → T−10 window;
6. provenance valid;
7. `sha256` present and well-formed;
8. the raw blob **exists on disk**;
9. **coverage gunzips it and rehashes it, and the hash matches.**

Points 8–9 are new. §5 requires "a real persisted raw artifact", and §9.9/§9.11
require persistence and hash failures to *prevent* coverage — so coverage opens
the file rather than believing the row.

**That immediately found something.** 30 rows fail `RAW_SHA256_MISMATCH`: the
known `.reduced` blob naming weakness, where the filename hash identifies the
source file rather than the projection. Previously prose; now caught by a
verifier. **All three official sources verify 6/6**, so the T−90 path is
unaffected. Recorded as a debt, not chased (§13).

---

## 7. Multi-game handling

Eight games share the `2026-09-13T15:30Z` window. One capture of the league-wide
page legitimately serves all eight — and the relationship is **explicit**: the
declaration lists all eight `game_id`s before the fetch, and coverage grants
exactly those eight.

Tested both directions (§9.12, §9.13):

- a capture declared for the 15:30Z window covers `CHI_CAR`, `TB_CIN`,
  `ATL_PIT` — and **not** `ARI_LAC`, `DAL_NYG` or `DEN_KC`, whose windows are
  later the same day;
- a capture declared for **only** `CHI_CAR`, taken inside the shared window,
  does **not** cover `TB_CIN`. Timing alone would have granted it; attribution
  refuses.

---

## 8. Raw SHA vs substantive digest

Unchanged from Directive 6, and deliberately so. Raw SHA-256 remains the
authoritative identity of the exact bytes and is what coverage rehashes. The
substantive digest is derivative evidence only, labelled
`DERIVED_DETERMINISTIC`, and is not consulted for discharge. No historical blob
rewritten or coalesced. The nonce rules stay narrow — anchored to
`data-jsonid` and `<script id>`, proved against real artifacts, and proved *not*
to touch the `sportradar_id` column that a broader rule would have eaten.

---

## 9. Adversarial tests and guard-deletion proofs

`test_execution_target.py`, 84 assertions, §9's sixteen requirements as sections
A–P:

| § | Requirement | Result |
|---|---|---|
| 9.1 | target carries exact game id | PASS |
| 9.2 | capture before window | not covered |
| 9.3 | capture after window | not covered |
| 9.4 | in-window, wrong game | not covered |
| 9.5 | unattributed | not covered |
| 9.6 | generic source-level PASS | not covered |
| 9.7 | event-targeted PASS in-window | **covers** |
| 9.8 | BLOCKED / FAIL / DEFERRED / N-A in-window | not covered |
| 9.9 | raw persistence failure | not covered |
| 9.10 | invalid provenance | not covered |
| 9.11 | incorrect raw hash | not covered |
| 9.12 | no silent multi-game credit | not covered |
| 9.13 | declared multi-target | covers only the declared |
| 9.14 | attempting ≠ completing | not covered |
| 9.15 | open until durable evidence | stays open |
| 9.16 | reproducible from artifacts alone | reproduces |

**Three guard-deletion proofs**, each replaying the same seeded violation:

| Control deleted | With guard | Bypassed |
|---|---|---|
| basis gate | sweep covers nothing | **sweep becomes eligible** |
| `_clears` game attribution | CHI-only capture doesn't cover TB@CIN | **it does** |
| artifact rehash | wrong hash blocks coverage | **row covers** |

**One of these proofs was wrong on my first attempt.** It used two games four
days apart, so *timing* already refused and bypassing the attribution guard
changed nothing — the test proved nothing while claiming to prove attribution.
It now uses two of the eight games sharing one window, where only attribution
can tell them apart.

---

## 10. Pre-flight status — §10, as a command

`python3.12 nfl/tools/preflight_t90.py --season 2026 --week 1` → **10 checks, 0
failing.**

```
ok  anchored workflow matches the current schedule   16 cron entries
ok  first upcoming inactives target                  NE@SEA, opens in 68.2h
ok  the window is exactly the owner's T-90 -> T-10    80 min, kickoff -90
ok  the first target is not already covered           covered=0, pending=63
ok  the runner has already pushed evidence unattended 6 of last 25 commits
ok  official_inactives: artifacts verify              6/6 byte-for-byte
ok  official_injury_report: artifacts verify          6/6 byte-for-byte
ok  a sweep cannot discharge                          only ANCHORED
ok  unknown workflow falls back to non-discharging
ok  anchored workflow name matches the generated file
```

`test_preflight.py` breaks each check on purpose and requires it to notice — a
stale cron, a loosened gate, a renamed workflow, a widened window, and a target
reading covered before its event.

The workflow-name check earns its place: `execution.ANCHORED_WORKFLOW` must
equal the `name:` the generator writes, or **every anchored run would silently
classify as a sweep and discharge nothing forever**.

Nothing was manually marked covered. No synthetic evidence was written to the
production manifest.

---

## 11. First Week 1 target and exact window

| | |
|---|---|
| Game | `2026_01_NE_SEA` |
| Kickoff | **2026-09-10T00:20:00Z** |
| Window opens (T−90) | **2026-09-09T22:50:00Z** |
| Window closes (T−10) | **2026-09-10T00:10:00Z** |
| Width | 80 minutes, unchanged |
| Cron coverage | 17 nominal firings |
| Coverage says now | `DEFERRED[NO_WINDOW_HAS_CLOSED_YET]`, covered 0 |
| Opens in | ~68 hours from this report |

The T−90 / T−90→T−10 distinction is intact: T−90 is the official inactive
deadline; the 80-minute span is **our** engineering acceptance window, not an
externally verified NFL publication-latency fact.

---

## 12. What is proven before the real event

- The declaration is made before any fetch, on every row, including failures.
- Every one of §9's sixteen refusals behaves as specified.
- Three controls are load-bearing under deletion.
- Coverage reproduces from manifest + artifacts alone, and verifies the bytes.
- The anchored workflow is registered, active, and runs on a real runner.
- The official sources return real content whose artifacts verify byte-for-byte.
- Pre-flight is clear and is itself tested against its own failure modes.

## 13. What remains unproven until the real event

Everything that only reality supplies: that GitHub fires a scheduled run inside
the window; that nfl.com serves the inactives list at that moment; that
`retrieved_at` lands inside T−90→T−10; that the whole chain closes and coverage
reports the target discharged.

**A manually dispatched run is not offered as any part of this.** I dispatched
the workflow once to smoke-test the new code path on a real runner — and it
classifies as `OPERATOR_TARGETED`, which by construction discharges nothing.

---

## 14. G0A Item 1 verdict

**PARTIAL / PENDING REAL EVENT.** The implementation is in place; no qualifying
event has occurred. Nothing simulated, no waiver, no administrative closure.

## 15. G0A score

**11 / 12 — unchanged.**

---

## 16. Open debts

Recorded, not chased (§13):

| Debt | State |
|---|---|
| `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` | **OPEN**, untouched. `weekly_rosters.status` still forbidden. |
| `PLAYER_GSIS_UNMAPPED` | **OPEN**. Zero gsis identifiers on the page, measured. |
| Broadcast UUID join (79 vs 16) | **OPEN**. |
| `.reduced` blob hash names its source | **OPEN** — now *measured*: 30 rows fail rehash. No effect on the T−90 path. |
| Blob dedup defeated by render nonce | **OPEN**. Digest recorded; storage policy unchanged, your call. |
| ESPN authority | **UNCHANGED** — CANDIDATE FALLBACK, discharges nothing, tested. |
| Weekly cron regeneration | **OPEN**. Week 1 committed; week 2 needs a run. Drift guard fails the suite if forgotten. |
| A dropped scheduled run | **OPEN and unfixable by me.** 17 chances per window; GitHub may still drop all of them. |

---

## 17. Files and commits changed

Commit **`8fe3b79`**:

```
A  nfl/capture/execution.py               declare-before-fetch, eligibility
A  nfl/tools/preflight_t90.py             §10 as a command
A  nfl/tests/test_execution_target.py     84 assertions, §9.1-9.16 + 3 proofs
A  nfl/tests/test_preflight.py            14 assertions
M  nfl/capture/attribution.py             RETIRED to a raising stub
M  nfl/tests/test_attribution.py          now proves the retirement holds
M  nfl/capture/coverage.py                opens and rehashes the artifact
M  nfl/capture/schedule.py                kickoff_utc on every CaptureDue
M  nfl/tools/capture_vintage.py           declares once, before any fetch
```

Nothing deleted. No capture rewritten. No historical blob touched.

## 18. Is NFL-1 authorized?

**No.** G0A is 11/12; the gate requires 12/12. I am not requesting it, and I
would not accept the checklist as green before the first real window closes.

## 19. Markdown task-report path

`TASK_REPORT_2026-09-07_DIRECTIVE7.md`, repository root.

---

*Stopping after the return, per the directive. NFL-2, player models,
projections, simulation, DFS, markets, ownership, optimization and contest logic
not begun. No wager recommended or discussed.*
