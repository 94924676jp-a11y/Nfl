# P3B — NON-G0A ANCHORED CAPTURE + G0A REASON CORRECTION

**Starting HEAD** `2840a299ca739cd7be5e2044f96c7730077bc239`
**Date** 2026-09-08 · **Repo** `94924676jp-a11y/Nfl` · **Branch** `main`

**G0A = 11/12. NFL-1 = NOT AUTHORIZED. The existing G0A inactives workflow is
byte-identical and unchanged. No evidence was manufactured. No prior miss was
rewritten. Nothing was promoted.**

Two narrow objectives, both met. A third thing is **pending and cannot be
asserted yet** — §7 says exactly what and why.

---

## 1. The G0A inactives path did not change. Proof, not assurance.

| | value |
|---|---|
| schedule identity **before** | `SCHED-2a2924d4966fbd3d` |
| schedule identity **after** | `SCHED-2a2924d4966fbd3d` |
| `nfl-t90.yml` sha256 **before** (at accepted HEAD `2840a29`) | `41325fd9384b9d7373a1c9fbdd4b7a82db00f308522e8252543a0448b6e18982` |
| `nfl-t90.yml` sha256 **now** | `41325fd9384b9d7373a1c9fbdd4b7a82db00f308522e8252543a0448b6e18982` |
| `ANCHORED_KINDS` in `gen_t90_schedule.py` | `("inactives",)` — unchanged |
| NE@SEA cron firings | 17, 5-minute step, 22:50Z → 00:10Z — unchanged |

Verified two ways: `git show 2840a29:.github/workflows/nfl-t90.yml \| sha256sum`
against the working file, and `git log 2840a29..HEAD -- nfl-t90.yml
gen_t90_schedule.py`, which is **empty** — neither I nor the capture bot touched
either file. A test now asserts the frozen identity on every run.

---

## 2. The new non-G0A path

| | value |
|---|---|
| generator | `nfl/tools/gen_status_schedule.py` |
| workflow | `.github/workflows/nfl-status.yml` |
| workflow name | `NFL status anchored capture` |
| **schedule identity** | **`SCHEDNG-906facecf4b1f272`** |
| execution basis | `SCHEDULED_WINDOW_ANCHORED_NON_G0A` |
| windows / targets / cron entries | 5 / 47 / 10 |
| step inside a window | hourly |
| registered on GitHub | workflow id `353428977`, state **active**, 2026-09-08T19:24:13Z |

**Kinds it CAN serve:** `practice`, `final_status`.
**Kinds it CANNOT serve:** `inactives` — the G0A kind — and anything else.

A distinct identity **prefix** (`SCHEDNG-` vs `SCHED-`) was chosen deliberately
so the two schedules can never be misread as one another in a log line.

**Why hourly rather than five-minutely.** The inactives window is 80 minutes
and unrecoverable, which is what justifies a five-minute step there. These
windows are **twenty hours**. A five-minute step would be 240 entries per
window, burying the schedule in noise to buy nothing — the defect being fixed
is having *no* anchored execution, not having too few. Hourly gives ~20
anchored chances per window.

It carries every property the packet required: predeclared target identities
with exact `game_id`, `kind` and window; authorized source mapping;
raw-before-parse; append-only manifest; **commit-before-failure-gate**; and an
anchored execution basis.

---

## 3. The isolation is structural, not conventional

Four independent layers, each asserted:

1. **A distinct workflow name** → `declaration_basis` maps it to
   `BASIS_ANCHORED_NON_G0A`, not `BASIS_ANCHORED`.
2. **`execution.BASIS_KINDS`** confines that basis to
   `("practice", "final_status")`.
3. **A module-level `assert`** in `execution.py` refuses to let `G0A_KIND`
   into that tuple — widening it is an explicit, reviewable edit, never a side
   effect of adding a cron entry.
4. **The generator asserts** its own `NON_G0A_KINDS` excludes the G0A kind
   *and* matches what the basis may discharge, so the workflow can never fire
   for a target it structurally cannot satisfy.

The decisive test: an `inactives` target with **everything else made
maximally favourable** — inside the T−90 window, authorised source
(`official_inactives`), `capture_state=PASS`, valid provenance, raw blob
persisted, correct sha256 — is still **refused**, with the named reason
`BASIS_NOT_AUTHORISED_FOR_KIND:SCHEDULED_WINDOW_ANCHORED_NON_G0A`.

And the restriction is real rather than a broken code path: the same basis
**does** discharge `practice` and `final_status` in their own windows. Both
directions are asserted.

### Only one execution can reach the G0A obligation

| execution | can discharge `inactives`? |
|---|---|
| scheduled firing of **`NFL T-90 anchored capture`** | **YES** |
| scheduled firing of `NFL status anchored capture` | no — `BASIS_NOT_AUTHORISED_FOR_KIND` |
| manual dispatch of `NFL status anchored capture` | no — `MANUAL_DISPATCH_NOT_SELF_CERTIFYING` |
| manual dispatch of the G0A workflow | no — same |
| the `*/30` periodic baseline | no — `BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP` |
| an unknown workflow | no — falls back to the non-discharging class |

**Guard-deletion proofs, both halves:**

| guard | with it | bypassed |
|---|---|---|
| `BASIS_KINDS` restriction | `inactives` refused | the non-G0A basis **would** discharge `inactives` |
| workflow → basis mapping | non-G0A workflow gets its own basis | forced to `BASIS_ANCHORED`, the same identity **would** discharge |

**G0A readiness is unmoved by non-G0A success**, and that is asserted too:
`q2_discharged == 11`, the remaining item names the T−90 proof, no artifact
claims 12/12, and code cannot authorize NFL-1.

---

## 4. The two closed misses remain MISSED, and cannot be rescued

Live coverage, 2026-09-08T19:26Z: `FAIL[PERISHABLE_WINDOWS_MISSED]`,
63 targets, **0 covered, 2 missed, 61 not_yet_due**.

    MISSED  2026_01_NE_SEA / practice_a
    MISSED  2026_01_SF_LA  / practice_mon

**The new generator emits the whole week, including the window that already
closed** (2026-09-07T20:00Z → 2026-09-08T16:00Z). That is deliberate:
filtering by wall-clock would make the generator's output depend on when it is
run and break its own byte-identity drift test. Determinism matters more, and
those entries are harmless — **cron entries in the past never fire**, and a
capture taken now is refused `RETRIEVED_AT_OUTSIDE_DECLARED_WINDOW`. Both facts
are asserted rather than argued.

No backfill was attempted. No retrieval time was restamped.

---

## 5. `2026_01_NE_SEA / final_status_b` — PENDING, not captured

**Window: 2026-09-08T20:00:00Z → 2026-09-09T16:00:00Z.**
At the time the workflow was registered it was **NOT_YET_OPEN**.

The packet's four conditions, honestly separated into what is established and
what is not:

| condition | status |
|---|---|
| the workflow / target declaration exists **before** retrieval | **MET.** Workflow active 19:24:13Z; window opens 20:00Z — a 36-minute margin, and the first cron entry for that window is `0 20-23 8 9 *`. |
| execution is truly anchored | **MET.** A scheduled firing classifies `SCHEDULED_WINDOW_ANCHORED_NON_G0A`, which is in `DISCHARGING_BASES` and permits `final_status`. |
| retrieval occurs naturally inside the still-open window | **PENDING.** Depends on GitHub firing the schedule. Not assertable now. |
| all normal source/provenance rules pass | **PENDING.** Depends on `official_injury_report` returning rows with valid provenance. Not assertable now. |

**So the honest answer is: it may now be legitimately satisfiable, and it has
not been satisfied.** Two of four conditions are established by construction;
the other two are prospective facts about a scheduler and an origin server that
I cannot and must not pre-empt. **I executed no qualifying run and dispatched
nothing.** If the remaining two do not hold, it becomes MISSED, and that is the
correct outcome.

This is a genuine prospective rescue rather than a backfill precisely because
the declaration was committed while the window was still shut.

The same applies to the other **60 open obligations**, which previously had no
anchored path at all.

---

## 6. The G0A item-1 reason correction

**`nfl/NFL_G0A_ITEM1_REASON_CORRECTION.json`**, dated 2026-09-08T19:30:00Z.

**History is preserved, not rewritten.** `NFL_G0A_CHECKLIST.md` is **not
modified** — the original wording still reads *"fails on egress alone"*, and a
test asserts it is still there. The correction stands beside it with its own
date.

| | |
|---|---|
| **old diagnosis** | *"Item 1 therefore fails on egress alone, and would still fail with a perfect scheduler."* — and *"more code here moves nothing."* |
| **was it correct when written?** | **Yes**, and the artifact says so. The measurement behind it was real and is still true *of the local executor*: the proxy answers 403 to `CONNECT www.nfl.com:443`. |
| **measured correction** | GitHub Actions egress **works**. `official_inactives` 84 PASS captures at HTTP 200 (~419KB each); `official_injury_report` 84 more (~329KB). 168 successful captures with durable blobs committed. The checklist generalised one executor's 403 into a universal blocker; those are different facts. |
| **second error in the old wording** | *"more code here moves nothing"* — P3A found **two** code defects that would each have prevented the discharge alone. Code moved a great deal. |
| **current reason item 1 is incomplete** | No legitimate real-event anchored T−90 inactives proof has yet occurred. It is **pending, not blocked**. |
| **numerical state** | **G0A = 11/12, unchanged.** Item 1 verdict stays FAIL. |

**Machine-readable readiness now points at it.** `nfl1_readiness.report()`
carries a new `q4a_item1_reason_correction` block with the superseded reason,
the current reason, the unchanged count, and confirmation the checklist was not
rewritten — so no downstream report repeats the stale egress explanation. If
the artifact ever goes missing the field reports `MISSING` rather than silently
omitting itself, because the failure being guarded against is a quiet reversion
to the stale text.

---

## 7. Tomorrow's G0A path, rechecked (inspection only)

| check | result |
|---|---|
| game | `2026_01_NE_SEA` |
| kickoff | 2026-09-10T00:20:00Z ✓ |
| qualifying window | **2026-09-09T22:50:00Z → 2026-09-10T00:10:00Z** (1:20:00) ✓ |
| status | `NOT_YET_DUE`, opens in ~27h |
| workflow byte-identical to the accepted repaired version | ✓ `41325fd9…` |
| unrelated capture-bot rebases touching it | **none** |
| anchored firings inside the window | 17, exact 5-minute step ✓ |
| basis for a scheduled firing | `SCHEDULED_WINDOW_ANCHORED`, discharging, **no kind restriction** ✓ |
| new workflow able to interfere | **no** — §3 |

**No fake qualifying capture was executed.**

---

## 8. Canonical suite

    python -m nfl.tests.run_suite -v

    modules 34   test functions 352   checks 2101
    FAILING CHECKS 0   RAISED 0
    SUITE PASS

All 34 discovered modules tally-backed, 0 vacuous, 0 raised. Up from P3A's
33 / 340 / 2,045 — one module added (`test_non_g0a_isolation`) and 56 checks.

**One intermediate run was red**, recorded rather than smoothed over:

    modules 34  test functions 352  checks 2097  FAILING CHECKS 2  RAISED 0
    FAIL and only the anchored basis is in DISCHARGING_BASES
    FAIL only the anchored scheduled basis can discharge at all

That is my own change breaking two pre-existing guards. See §9.

---

## 9. Two pre-existing guards that my change broke, and how I repaired them

Adding a second discharging basis turned the suite red on two assertions that
had been green since the 2026-09-07 directive:

    test_discharge_identity:  "only the anchored basis is in DISCHARGING_BASES"
    test_execution_target:    "only the anchored scheduled basis can discharge at all"

Both asserted the **literal tuple** `DISCHARGING_BASES == (BASIS_ANCHORED,)`.
With a second anchored path that literal is false.

**This is the moment where loosening would be easy and wrong.** Deleting the
assertions, or relaxing them to "at least one anchored basis", would throw away
the rule they exist to enforce. What they actually protect is: *nothing but an
anchored SCHEDULED execution ever discharges anything.* That is unchanged.

Repaired by asserting the rule directly rather than a snapshot of its shape:

- **every** discharging basis begins `SCHEDULED_WINDOW_ANCHORED`;
- **no** sweep, local run, or operator dispatch is in the discharging set;
- **exactly one** basis may serve the G0A kind, and it is the original
  `BASIS_ANCHORED` — computed from `BASIS_KINDS`, so adding a third basis later
  cannot quietly gain G0A capability.

The third assertion is strictly **stronger** than what it replaced: the old
tuple check said nothing about kinds, so it would have passed a second basis
that could discharge `inactives`. The new one fails that case.

---

## 10. Changes made

| file | change |
|---|---|
| `nfl/capture/execution.py` | `NON_G0A_ANCHORED_WORKFLOW`, `BASIS_ANCHORED_NON_G0A`, `BASIS_KINDS`, `G0A_KIND` + assert; basis→kind refusal in `eligibility` |
| `nfl/tools/gen_status_schedule.py` | **new** — the non-G0A generator |
| `.github/workflows/nfl-status.yml` | **new** — generated, `SCHEDNG-906facecf4b1f272` |
| `nfl/NFL_G0A_ITEM1_REASON_CORRECTION.json` | **new** — the dated correction |
| `nfl/prospective/nfl1_readiness.py` | `q4a_item1_reason_correction` points at it |
| `nfl/tests/test_non_g0a_isolation.py` | **new**, 52 checks, 2 guard-deletion proofs |
| `nfl/tests/test_discharge_identity.py` | tuple-shape assertion → the rule it protects (§9) |
| `nfl/tests/test_execution_target.py` | same |

**Not changed:** `.github/workflows/nfl-t90.yml`, `gen_t90_schedule.py`,
`ANCHORED_KINDS`, `SCHED-2a2924d4966fbd3d`, `NFL_G0A_CHECKLIST.md`,
`PATH_C_STATE.json`, any model, any authorization.

---

## 11. Explicit restatements

- **G0A = 11/12.** Unchanged. The correction addresses the recorded *reason*
  only and says so in its own text and in a test.
- **NFL-1 = NOT AUTHORIZED.** `assert_no_auto_authorization` and
  `assert_no_artifact_claims_12_of_12` both pass.
- **The existing G0A inactives workflow is unchanged** — byte-identical sha256,
  same schedule identity, same cron entries, `ANCHORED_KINDS` untouched.
- **No evidence was manufactured.** No qualifying capture was executed, nothing
  was dispatched, no retrieval time was restamped, no periodic capture was
  reinterpreted as anchored.
- **No prior miss was rewritten.** Both remain MISSED and are now additionally
  protected against rescue by the new path.
- **Nothing was promoted.**

---

## 12. What happens next without me

The non-G0A workflow fires hourly inside each open window from 20:00Z tonight.
The G0A workflow fires 17 times inside tomorrow's 80-minute window. Neither
needs me, and neither can authorize anything.

Per your instruction I am not touching T−90 code again unless a real defect
appears. **STOPPING HERE.**

**Final HEAD:** stamped by the commit that follows this file.
