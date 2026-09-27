# Defect ledger — DEF-074 … DEF-082

Filed 2026-09-27. HEAD at filing: see the commit that adds this file.

**Why this file exists.** DEF-074 through DEF-080 were established with evidence
during the 2026-09-26/27 guard-census and execution-lineage work, but were
recorded only in conversation and in test docstrings. A defect that exists only
in a transcript is not filed. Two of them (DEF-079, DEF-080) had already leaked
into `GUARD_REACHABILITY.json` by identifier with no definition anywhere in the
tree, so the identifier resolved to nothing. This closes that.

Every entry states what was observed, what it proves, and — where relevant —
what it does **not** prove. Entries marked FIX_IMPLEMENTED name the change.

---

## DEF-074 · Board-pass judge reported PASS on a refusal

**Status:** FIX_IMPLEMENTED.

`nfl-product-board.yml`'s judge step treated any completed run as a pass, so a
board run that refused every game exited 0 and the workflow went green. A
refusal is a valid result, but it is not a pass.

**Fix:** `nfl/tools/judge_board_pass.py`, five states over three exit codes —
`RAISED` / `REFUSED_UNDECLARED` → 1, `REFUSED_DECLARED_DEBT` / `NO_SUMMARY` →
78 (neutral), `CLEAN` → 0. The neutral exit is *conditional on a declaration*:
`declared()` reads `SYSTEM_STATE.json`, so deleting the declaration returns the
pass to red rather than leaving a permanent amnesty. The workflow step now runs
the module instead of an inline shell test.

**Not deployed to `main`.** The scheduler reads workflow definitions for
`schedule:` from the default branch only, so the fix is not yet live. That is
D24-R1/R2 territory and is not silently pending — it is stated here.

## DEF-075 · Capture workflows write back to `main`, not `capture-prod`

**Status:** OPEN. Resolves with D24-R2.

## DEF-076 · Guard census counted a truthy string as a proof

I reported all 15 executing-path guards as carrying a load-bearing proof. False.
`load_bearing_proof` holds the **string** `'NONE'` when there is no proof, and
`'NONE'` is truthy, so a `bool()` test passed on every row. The census was right
and my reading of it was wrong.

**What it proves:** a sentinel string is not a state. `'NONE'`, `'UNKNOWN'` and
`''` must not be distinguishable from a real value only by convention.

## DEF-077 · Workflow enumeration read the default branch only

`execution_lineage.py` enumerated workflows from the default branch, which is
correct for `schedule:` and `repository_dispatch:` but wrong for `push:` —
GitHub reads `push:` from the pushed ref. `agent-orchestrator.yml` exists only
on the engineering branch and was therefore invisible to the inventory.

**Fix:** `workflows()` now enumerates the default branch **plus** branch-local
ref-scoped workflows (`REF_SCOPED_EVENTS = push, pull_request,
pull_request_target, create, delete`), and `workflows_absent_from_default()`
names the gap explicitly.

**Withdrawn alongside it:** an earlier 109-module closure figure. The ref regex
had captured `${{ env.CAPTURE_BRANCH }}` as the literal `${{` and resolved every
tree to the engineering branch. With env resolution the trees separate:
engineering 95 → 101, `origin/main` 48, `origin/capture-prod` 16, plus one
`RUNTIME_RESOLVED` ref.

## DEF-078 · Orchestrator summary asserted autonomy was armed unconditionally

The summary step of `agent-orchestrator.yml` printed `Autonomy is armed in …`
as a fixed string, regardless of the policy flag. A reader of the run summary
would conclude LIVE autonomy was on when `autonomous_operation_enabled` was
`False`.

**Fix:** the step now reads the policy file and prints ARMED / NOT ARMED / NOT
ESTABLISHED. NOT ARMED carries the kill-switch text and says explicitly that it
is **not a failure** — the safe state must not read as a defect, or it will be
"fixed".

## DEF-079 · `forecast()` passes `None` sources through to a guard

`assert_sources_permitted(None)` raises `TypeError` rather than refusing,
because `forecast()` hands the `None` straight through. A crash is a defect; a
refusal is a valid result.

**Investigated and deliberately NOT filed alongside it:** the same call in
`live_features.build()`. `build()` normalises `sources or (...)` before the
call, so the guard never sees `None` there. Same function, different caller,
different verdict — the difference is the caller, so only the defective caller
is filed.

## DEF-080 · The completeness ratchet could not fail

**Status:** FIX_IMPLEMENTED.

`test_completeness_ratchet.py` carried baselines above the measured values, so
every assertion had slack and no regression could trip it. `_consumers_of` also
used substring matching, which counted a module name appearing in a comment as
a consumer.

**Fix:** baselines lowered to measured (`PARTIAL_JOIN` 16, `FIXTURE_PINNED` 24,
`ORPHANED_OUTPUT` 1, `UNTESTED_REFUSAL_CODES` 511); `_consumers_of` rewritten
to AST import detection; new `_orphaned_guard_modules()` (single indexed pass,
2.7 s) with `ORPHANED_GUARD_MODULES = 19`, so test_C can now fail.

**Withdrawn during this work:** my re-measurement of 1,140 refusal codes /
552 untested. My AST scan dropped module-constant codes and table-held codes.
The authoritative source is `cross_layer_audit.untested_refusal_codes()` →
**511 of 942**.

---

## DEF-081 · One refusal code covered two different slate-window faults

**Status:** FIX_IMPLEMENTED. Found while resolving the Week-3 Early Only slate.

`early_only.slate()` raised `DK_POOL_SPANS_MORE_THAN_ONE_WINDOW` for two
distinct conditions:

1. the pool genuinely spans more than one kickoff window — a **mixed** pool;
2. the pool has exactly one window, but it is not the window the caller
   **declared** — a correct pool against a wrong expectation.

These have different causes and different remedies. The first means the export
is not an Early Only export. The second means the caller's `expected_kickoff` is
wrong, or the contest moved. Reporting both as "spans more than one window" is
false in case 2 — the pool spans exactly one.

**Fix:** case 2 now raises `DK_POOL_WINDOW_IS_NOT_THE_DECLARED`, carrying both
the observed and the declared window. Case 1 keeps the original code and is
raised only when `len(kicks) > 1`, which is now literally what it says.

**Why this is not cosmetic:** a code is a contract with the reader. A caller
branching on `DK_POOL_SPANS_MORE_THAN_ONE_WINDOW` to reject a mixed export would
also have rejected a perfectly good single-window export whose declared time
disagreed, and the log would have explained it wrongly.

## DEF-082 · `identity.reconcile()` and `early_only.pool()` disagree on schema, and `dk_id` was dropped

**Status:** FIX_IMPLEMENTED (both halves).

Two separate faults found in one call:

**(a) Schema mismatch.** `reconcile()` requires `opponent` and `is_home`;
`pool()` emits `away_team`, `home_team`, `team`. Passing `pool()` output
straight to `reconcile()` raises `KeyError: 'opponent'`. The two modules are
meant to compose and do not.

**Fix:** `early_only.as_identity_rows(pool_rows)` derives `opponent` and
`is_home` from the away/home/team triple and records what it did **on each row**
— `derived_fields` names the two it derived, `absent_fields` names the two the
export does not supply (`inj_flag`, `dk_depth`), which are set to `None`.

Per-row rather than on a wrapper, deliberately: a wrapper's note is lost the
moment a caller iterates the rows, whereas a declaration carried on the row
travels with the evidence into whatever consumes it. (A first draft of this
entry was ambiguous about where the declaration lives; the regression test
looked for it on the return value and failed, which is how the wording got
fixed.)

`None` here means *not supplied by this export*, named rather than defaulted. A
missing injury flag is not a clean bill of health, and a missing depth is not a
starter. Where the club appears in neither slot of its own game string,
`opponent` and `is_home` are both `None` — the adapter refuses to pick a side.

**(b) `dk_id` was dropped.** `reconcile()` built its output record without
carrying `dk_id`, so the DraftKings player id — the only identifier that is
authoritative for the contest — did not survive the identity step. Every
downstream consumer was left joining on name and team, which is exactly the join
that produced the four false FC-only rows recorded in
`DK_WEEK3_EARLY_BASELINE.md` §6.

**Fix:** `reconcile()` now carries `'dk_id': d.get('dk_id')`.

**What this does not fix:** the six UNMATCHED rows. `dk_id` surviving the join
means an unmatched row is now *identifiable* downstream; it does not resolve it
to a canonical id. UNMATCHED remains UNMATCHED, and the canonical roster — not
a third-party file — is what may resolve it.

## DEF-083 · The guard census is read as ground truth and can go stale silently

**Status:** FIX_IMPLEMENTED.

`nfl/research/audit/GUARD_REACHABILITY.json` is not documentation. Other tests
read it as evidence — `test_uncalled_governance_guards.py` establishes that a
supersession is real by comparing two rows out of it. So a stale census does not
merely mislead a reader; it makes those tests assert stale facts and pass.

And it goes stale silently, because `guard_reachability.py --json` **prints** to
stdout. The committed file is produced by shell redirection, so no step anywhere
fails when the code and the artifact disagree.

**Observed, not hypothesised.** After adding an entry to `LOAD_BEARING_PROOFS`
and a classification to `CLASSIFICATION`, the committed JSON still reported
`load_bearing_proof: NONE` and `classification: NOT_ESTABLISHED` for that
guard. I read those values back and briefly concluded my edit had not landed —
the edit was fine; the artifact was two hours and one code change out of date,
and every test reading it was content.

**Fix:** `nfl/tests/test_guard_census_is_not_stale.py`, 14 checks. It
regenerates the census in memory and compares field by field and then byte for
byte, with the regeneration command in the failure message. It deliberately does
**not** rewrite the file: a test that repairs what it checks converts a
detectable defect into an invisible one.

Verified able to fail: perturbing one row's `line` by 999 produces two failures
naming the field; restoring returns it to 14/14. Two further checks close
adjacent holes — every path in `LOAD_BEARING_PROOFS` must exist, and no guard
may be classified `LOAD_BEARING` without a named proof file.

**Two things caught while writing it, both mine:**

The first version keyed rows on the guard name alone. Two guards share a name
(`assert_complete` in `identity_crosswalk.py` and `contracts/completeness.py`;
likewise `assert_publishable`), so the dict dropped one and compared the
survivor against the other's row, reporting drift that was not there. It
disagreed with the byte-level check three lines below it, which is how it
surfaced. Now keyed on name **and** defining file, with the non-uniqueness
pinned by its own test so the reason cannot be lost.

The first version also called `census()` up to three times per test, which
parses the whole tree each time and made the module one of the slowest in the
suite for no benefit. Memoised, with the determinism test deliberately left
using two independent censuses.

**What it does not establish:** that the census is *correct*, only that it is
*current*. A wrong classification committed alongside its own generator output
passes, as it should — whether a guard is load-bearing is settled by a bypass
proof, not by a file agreeing with the function that wrote it.

---

## Census movement recorded with these entries

`assert_no_postgame_inputs` moves NOT_ESTABLISHED → **LOAD_BEARING**, taking the
census from 13 to 14 load-bearing and 69 to 68 not-established of 91.

Its proof is `nfl/tests/test_leakage_guard_is_load_bearing.py`, 23 checks. The
guard already had a unit test asserting it returns `POSTGAME_INPUT_DECLARED`,
which establishes a return value and nothing else. What the new file establishes
is the **protected action**: a canary records whether the stage function ran.

  * the leaking stage's own `fn` never executes;
  * every **later** stage's `fn` never executes either, because `halted_by` is
    set — the pipeline previously recorded a refusal and then went on to run the
    QB model on unresolved players and seal the artifact;
  * with the guard stubbed to its pass shape, **both** functions run — which is
    what makes the observation a proof rather than a description.

The stub returns `Outcome.ok('INPUTS_ARE_PREGAME', ...)` because it must match
the guard's real pass shape; a `None`-returning stub previously broke a caller
and produced a passing test for the wrong reason.

## DEF-084 · The one accessor that fixes the `.value` asymmetry is used barely half the time

**Status:** FIX_IMPLEMENTED (adoption), asymmetry itself left as declared debt.

`Outcome.ok(code, value, ...)` has `value` as a real parameter. `Outcome.fail`,
`.blocked`, `.deferred` and `.not_applicable` have the signature
`(code, detail, **evidence)` — no `value` parameter — so `value={...}` on those
does not set `.value`, it silently becomes `evidence['value']`.

**Measured at HEAD: 80 call sites** pass `value=` to a non-ok constructor.
Every one of those authors wrote `value=` expecting `.value`, and on every one a
consumer reading `.value` gets `None` on exactly the outcome it most needs to
inspect.

*A first pass here reported 78 across 28 files.* That scan's base-name test used
a broken fallback expression and dropped two sites. The figure is **80**, from
the AST scan now pinned in `test_outcome_payload_accessor.py`, which is also
what a future reader should re-derive rather than quote.

**This is already known, and the correct fix already exists.**
`nfl/production/review/gate.py:848` defines `payload(outcome)`, whose own
docstring says "this project has now written that bug twice. One accessor." It
is correct: it tests `isinstance(v, dict)` rather than truthiness.

**So the defect is not the asymmetry. It is that the fix is not reached.**
Correct code that is not reached is inert.

| | count |
|---|---|
| calls to the canonical `payload()` | **7** |
| ad-hoc `x.value or x.evidence.get('value')` sites | **8** |

Two of the eight are **inside `gate.py` itself** (lines 712 and 901), in the
same module that defines the accessor 60 lines further down. And
`nfl/production/board/run_board.py` uses the accessor at line 60 —
`gv=GATE.payload(gt)` — while using the ad-hoc idiom at line 54, four lines
apart, in the same function.

**Why the ad-hoc idiom is not merely uglier, but wrong.** `x.value or
x.evidence.get('value')` uses `or`, so a `.value` that is legitimately falsy —
`{}`, `0`, `[]`, an empty result set — is treated as absent and the read falls
through to `evidence`. That is the project's own recurring defect class: falsy
is not missing. It is the same shape as DEF-076, where the string `'NONE'`
tested truthy and a census of proofs read as complete. `payload()` avoids it by
type-checking; the idiom does not.

`run_board.py:54` is the sharpest instance: `a.value or a.evidence['value']`,
with no `.get`. A falsy `.value` on an outcome carrying no `value` key raises
`KeyError` rather than reporting the refusal. A refusal is a valid result; a
crash is a defect. (Consequence is bounded — `run_board.py` is a pinned
single-game script, not the production path — so this is filed as a real but
low-blast-radius instance, not as a production outage.)

**Fix applied:** the 8 ad-hoc sites call `payload()`. Mechanical, no behaviour
change except where the `or` idiom was wrong, which is the point.

**Not fixed, and deliberately:** the 80 producer sites, and the asymmetry in
`Outcome` itself. Making the non-ok constructors accept `value` — or reject it
with a named error — is a change to the governance type every layer depends on,
with an 80-site blast radius. That belongs in its own change with its own
before/after, not bundled into an accessor cleanup. Recorded here as debt with
the measurement attached so the next person does not have to re-derive it.

**Guarded by** `nfl/tests/test_outcome_payload_accessor.py`, 17 checks: the
accessor's behaviour including the falsy-value case the idiom got wrong, a
ratchet that the ad-hoc idiom is absent from production (checked per line and
across line breaks, since one instance was split over two lines), a check that
the accessor actually has production callers so the ratchet cannot pass
vacuously, and the producer-side count held in a band so that a large move
forces this entry to be updated rather than quietly diverging.

## DEF-085 · Running a test module directly mutates a tracked production artifact

**Status:** OPEN (observed, not fixed). Low consequence, real.

Invoking test modules directly — not through `run_suite.py` — bumped
`nfl/research/v2/r5/active_board_pointer.json`: `pointer_version` went
**163 → 166**, one increment per invocation, with `at` and `written_at`
restamped each time. `nfl/product/board_pointer.py` is what writes it.

**A second artifact, observed the same way an hour later:**
`nfl/prospective/q9shadow/Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl` also gains rows
from direct invocation. So this is not one stray writer -- it is a small class,
and the count of members is not established. `nfl/tests/_suite_progress.jsonl` is
a third, though that one is the suite's own bookkeeping and arguably belongs to
it.

**Two consequences, and the second is the one that matters.**

*It dirties the tree.* The churn was swept into a commit and had to be backed
out. Minor.

*`pointer_version` does not count what its name says.* It is incremented by test
runs as well as by real board writes, so it is not a count of boards. Anything
reading it as a monotonic board counter, or diffing two pointer versions to infer
how many boards were produced between them, is reading test invocations as
football. I have not found a consumer that does this — which is why this is filed
OPEN and low rather than as a live defect — but the number is not what it claims
and the next person to reach for it should know.

**Why `run_suite.py` does not have the problem:** it runs each module in an
isolated state root and diffs the working tree before and after. Direct
invocation bypasses that isolation, which is exactly why a direct run is a weaker
form of evidence than a suite run, and why the concurrent suite run earlier
tonight was discarded rather than quoted — I was writing to the tree while it was
measuring the tree.

**Not fixed here** because the fix is a choice between two designs — make the
pointer write refuse outside a state root, or have the tests that reach it use
one — and that belongs with A10 / the evidence-storage work rather than being
decided in a commit about guard proofs.

## DEF-086 · The T-90 capture cron on the default branch has covered no game day since 2026-09-15

**Status:** FIX WRITTEN, NOT DEPLOYABLE FROM HERE. Time-critical today.

`nfl-t90.yml` is the event-anchored capture workflow. Its whole purpose is to be
awake in the T−90 window, which is the only window in which an official inactives
publication can be captured. Its cron entries are generated from a kickoff
snapshot and therefore go stale every week.

**Measured 2026-09-27:**

| branch | cron entries | dates covered |
|---|---|---|
| `origin/main` (the default branch) | 16 | **September 9–15** |
| engineering branch, before this change | 16 | September 17–22 |
| engineering branch, after this change | 16 | September 24–28 |

**GitHub reads `schedule:` from the default branch only.** So the deployed
schedule has had no cron entry matching any game day for twelve days, and none
matching today. Today's 1 PM ET slate needs **2026-09-27 15:30Z–16:50Z**, which
the generator produces for all nine games and which `main` does not have.

**This is a second and independent cause.** `docs/AGENT_OUTBOX.md` already
records that the four capture workflows stopped producing commits after
2026-09-11 and concluded the cause was at the Actions or repository level, noting
at the time that "`main` and the working branch carry byte-identical
`.github/workflows/`". **That sentence was true on 2026-09-11 and is not true
now** — the two have diverged. Even if the Actions-level problem were fixed
today, no T−90 run would fire, because the deployed cron has no matching entry.
Fixing one cause would not have revealed the other, which is why both belong on
the record.

**What was done here:** regenerated with
`python3.12 nfl/tools/gen_t90_schedule.py --season 2026 --week 3 --write`, the
repository's own documented procedure. `test_t90_workflow.py` goes from **11
failing checks to 41 passed / 0 failed**, so the guard was working correctly and
was reporting a real stale schedule rather than crying wolf.

**What was NOT done, and is not mine to do:** deploying it. The workflow must be
on the default branch to be scheduled, and pushing to `main` is outside what I am
authorised to do. Escalated in `docs/AGENT_OUTBOX.md` under OUT-033, because the
inactives request and this are the same deadline: OUT-033 asks for the bytes by
hand precisely because the mechanism that would capture them automatically cannot
fire.

**The durable fix is not another regeneration.** This is the second time the
windows for an upcoming slate did not exist (`f9148b0`, "The T-90 windows for
tomorrow's slate did not exist"). A weekly manual regeneration that silently
means zero capture attempts when missed is the defect; the test that catches it
exists and is not run by CI, which is the same not-reached pattern as DEF-084.
D24-R0b already proposes moving the pin into the generator. Whatever the design,
it has to make a stale schedule loud at the point of deployment rather than
discoverable only by running the suite.

## DEF-087 · Two checks in the capture-obligations guard could not pass

**Status:** FIX_IMPLEMENTED. Found by reading the suite output rather than the
headline count.

`test_capture_obligations.py::test_I` hard-coded **week-1 dates** — 2026-09-14/15
for the DEN@KC window and 2026-09-13 for that Sunday's 13:00 ET slate — and
asserted the *current* `nfl-t90.yml` carried cron entries firing inside them.

But that workflow is a **rolling one-week artifact**: it is regenerated per week
and only ever covers the current week. So those two checks became permanently
unsatisfiable the moment the schedule advanced past week 1, and had been failing
ever since. They were 2 of the module's 5 failing checks.

**This is the exact inverse of DEF-080.** There the defect was a test that could
not fail; here it was a test that could not pass. Both stop carrying information.
The asymmetry is that a permanently red check is worse than merely useless: it
trains a reader to skim past the module, and this module is the
capture-obligations guard — the one that most needs to be believed when it goes
red. It sat beside the genuine DEF-086 finding in the same suite output.

**The historical fact is not lost, and was never this test's to hold.** Week 1's
crons existed, were syntactically valid, and the runs never fired. That is
written up in `docs/AGENT_OUTBOX.md` with the run evidence, which is where a
finding about a past incident belongs. A live assertion about a rolling file is
not a place to store history.

**Fix:** the check now reads the windows the file **declares in its own schedule
comments** and requires at least one cron firing inside each — the standing
obligation, stated relatively so it survives every weekly roll. Correctness of
the windows against the kickoff snapshot remains `test_t90_workflow.py`'s job by
regeneration and byte-comparison; this is the self-consistency check beside it.
The one check in the function that was always right is kept and also made
relative: no entry may fire a week past the last declared window, so silent
expiry of an absolute-date schedule stays detectable.

Module goes from **5 failing to 3**. A vacuity guard is included: if the
generator ever stops emitting the window comments, the declaration count check
fails rather than the coverage check passing over an empty list.

**Verified able to fail**, and it caught a defect of my own while doing so.
Dropping the two cron entries for the 2026-09-27 15:30Z window while leaving its
declaration standing produces a failure naming exactly
`['2026-09-27 15:30Z->16:50Z']`. That run also revealed that my summary line
printed "6 declared window(s), all covered" **while a window was uncovered** — a
log line asserting the good outcome regardless of what happened, which is the
same shape as DEF-078's unconditional "Autonomy is armed" echo. It now prints
"5 covered, 1 NOT" when perturbed and "6 covered, 0 NOT" when restored.

## DEF-088 · The suite's failing total is not reproducible across environments

**Status:** OPEN (measured). It invalidates a comparison I made, and it is the
mechanism behind a rule this project already had.

I ran the full suite twice to test whether tonight's work regressed anything: at
HEAD `f067eed` in the working tree, and at the pre-session commit `e62d630` in a
fresh `git worktree`. The totals:

| | baseline `e62d630` | HEAD `f067eed` |
|---|---|---|
| modules | 284 | 291 |
| checks | 14,487 | 14,930 |
| **failing** | **131** | **139** |
| raised | 79 | 40 |
| blocked | 36 | 23 |

**The +8 is not a regression. The two runs measured different amounts of the
suite, and my method caused it.**

`test_qb2_production.py` is the whole story. At baseline it executed **40
checks** with 0 failing and **nine** test functions RAISED —
`test_08_same_week_leakage` through `test_17_guard_deletions` — every one with
`FileNotFoundError: nfl/research/p4b/panel_enriched.pkl`. Their checks never
ran. At HEAD the same module executed **66 checks** and 13 failed, because those
nine functions completed instead of aborting.

`panel_enriched.pkl` is **gitignored** (`.gitignore:12`) and generated by
`nfl/research/repro/regenerate.py`. A fresh worktree does not reproduce it, so
nine functions in a production-QB module silently measure less at baseline than at
HEAD. The +13 from this one module more than accounts for the +8 net; the six
modules that appear "fixed" at HEAD and the three changed counts are the same
mechanism in both directions.

**The sharpest part: the artifact is absent from BOTH trees right now.** It
existed during the HEAD run and does not exist after it. So its presence during
any given run is not reproducible even in the same directory, which means the
suite's failing total is a function of run history and not only of the code.

**What follows.** The standing rule — only a specific changed check is a
regression, never the total — is not conservatism, it has this concrete
mechanism underneath it. And a "clean worktree at the old commit" is NOT a valid
way to baseline this suite, which is the methodological error here: I reached for
a clean room and got a different experiment. A valid comparison needs the same
generated state on both sides, or must be done per-check on the modules that do
not depend on it.

**What is established about tonight's work, without the invalid comparison:** my
7 new test modules contribute **zero** failing checks, and the 8 modules covering
the 5 production files I edited are **identical** at both commits. No evidence of
regression from these changes. Not the same as a measured absence, and I am not
writing it as one.

## DEF-089 · An existing load-bearing proof is vacuous because an earlier stage refuses first

**Status:** OPEN. Pre-existing — it RAISED at both commits.

`test_qb2_production.py::test_17_guard_deletions` calls
`assert_guard_is_load_bearing` for `nfl.production.qb_accounting.reconcile_team`
and the harness refuses it:

> the violation was still caught with the guard BYPASSED, so this test does not
> depend on the guard and would pass if the guard were deleted. … This is the
> `assert_batch_games_are_new` failure: a test that proves nothing.

The reason is visible in the returned record. The pipeline never reaches
`reconcile_team` at all: `capture_validation` refuses first with
`REQUIRED_SOURCE_NOT_DECLARED` — the run declares `['schedules']` while its
layers select vintages of `['depth_charts', 'injuries', 'schedules',
'weekly_rosters']` — and every later stage is `STAGE_NOT_REACHED`. So the
"violation" the test seeds is caught by a stage twelve steps earlier, with or
without the guard under test.

**This is DEF-080's shape inside the bypass harness itself**, and it is the third
variant tonight: a test that cannot fail (DEF-080), a test that cannot pass
(DEF-087), and now a test whose subject is never reached, so the proof is about a
different guard than the one it names. The harness is working correctly — it
refuses rather than reporting a proof — which is exactly why this is visible at
all.

**Not fixed here,** because the fix is to make the fixture declare the sources
its layers select so the run reaches the QB layer, and that is a change to a
production test fixture that deserves its own before/after rather than being
folded into a night of guard proofs. Filed so the census is not tempted to count
`reconcile_team` as proven: it is not.

## Census movement, second pass

`assert_pregame_untouched` NOT_ESTABLISHED → **LOAD_BEARING**, and
`assert_cut_lawful` NOT_ESTABLISHED → **ANNOTATE_BY_DESIGN**. Census now
LOAD_BEARING **17**, NOT_ESTABLISHED **64**, ANNOTATE_BY_DESIGN 2,
ORPHANED_CONTROL 3, of 91.

### `assert_pregame_untouched` — the strongest bypass result so far

`pregame_frozen` holds the thing being graded: the sealed player draws, their
manifest, the salary file. If the postgame path can write into it, the forecast
is being marked by a paper it was allowed to edit afterwards — and it would not
look like a bug, it would look like a good grade.

Coverage already existed and was real:
`test_postgame_slate_is_addressable.py` seeds a stray file into a second slate
and checks the guard returns `PREGAME_FROZEN_SET_MUTATED`, also establishing that
the slate parameterisation is not cosmetic. What it never showed was a **caller**
refusing.

`nfl/tests/test_pregame_frozen_guard_is_load_bearing.py`, 20 checks, drives the
two real production entry points — `grade_projections.grade` and
`grade_portfolios.grade` — against a mutated copy of the slate. Both refuse with
the guard's own code and return no grade.

**The bypass half is the part worth quoting.** With the guard stubbed to its pass
shape, on the *same mutated* frozen set:

    grade_projections bypassed on a MUTATED slate: PASS/PROJECTIONS_GRADED
    grade_portfolios  bypassed on a MUTATED slate: PASS/PORTFOLIOS_GRADED

A complete, passing grade produced against tampered evidence. Nothing downstream
catches it. That is what makes this guard the thing standing in the way rather
than an annotation beside it.

Three details that keep the proof honest: **both** call sites are driven, because
the shape is duplicated at `grade_projections.py:92` and
`grade_portfolios.py:155` and proving one says nothing about the other; a check
asserts each grader reaches the guard through `nfl.postgame.outcome` rather than
holding its own reference, or the bypass would be a silent no-op and the test
would pass for the wrong reason; and a final check confirms the **real** default
slate is still intact, since every mutation happens in a temp copy.

Deletion is tested as well as addition — an over-eager cleanup removes files, and
that direction must refuse too.

### `assert_cut_lawful` — classified, deliberately not filed

`pipeline.cut_check` records it with `enforcement:
OBSERVATIONAL_IN_THIS_SLICE` and a stated `why_not_enforced`:
`bitemporal.readable_at` requires `learned_at < cut` strictly, while
`capture_validation` refuses only `retrieved_at > written_at`, so the DAG is
stricter at exact equality and that boundary has not been measured against sealed
runs.

Declared non-enforcement with a named reason is not an unproven guard, and the
honest next step is **measuring the equality boundary**, not wiring a STOP to
make a census row look better. Recorded as ANNOTATE_BY_DESIGN with the reason
carried in the census, per the standing instruction to look for downstream
enforcement and stated intent before filing anything.

## DEF-090 · `assert_promotable` is correct and cannot refuse anything in production

**Status:** OPEN (measured). Classified `ENFORCEMENT_UNREACHABLE`, a new census
category, because neither LOAD_BEARING nor NOT_ESTABLISHED describes it.

**The guard is not the problem.** `assert_promotable` is well built and its logic
is proven against the real registry: a FALSIFIED CRITICAL assumption blocks, a
still-DECLARED CRITICAL one blocks under `require_tested`, a FALSIFIED MATERIAL
one only warns, and it rewrites nothing. The census had it as
`effect_on_failure: STOP`, `EXTERNALLY_CALLED`, 2 production callers — which is
true of the *shape* and false of the *effect*.

**Two independent reasons it cannot refuse a production action, both measured.**

*1. The enforcing function has no production caller.* The chain is
`assert_promotable` → `adjustment_registry._assumption_gate` →
`assert_may_apply`. `_assumption_gate` is called exactly once, inside
`assert_may_apply`, and `assert_may_apply` is called **only from tests** (2 test
callers, 0 production). Nothing in production turns the verdict into a refusal.

*2. The consumer join is cross-namespace, so the gate passes vacuously.*
`_assumption_gate` passes `consumer=calling_layer`, and `assert_promotable`
selects by `consumer in a.downstream_dependencies`. Measured:

| | values |
|---|---|
| adjustment registry `applied_at` (5) | `coverage`, `game_state`, `line_play`, `team_environment`, `team_volume` |
| assumption `downstream_dependencies` (13) | dotted module paths (`nfl.production.nonqb.cs2_state`, …) and candidate names (`CS2_STAGE2_PRODUCTION_ALLOCATION`, `TEAM_VOLUME_V2`, …) |
| **intersection** | **EMPTY** |

So `mine` is always empty for every adjustment layer, and each returns PASS with
`n_assumptions == 0`. **Every one of the five layers passes the gate because it
selects nothing, not because it is sound.** Fixing reason 1 alone would change
nothing.

**The asymmetry is why this went unnoticed, and it is the part worth remembering.**
The guard's other caller, `nfl/production/assumptions/run_audit.py`, derives its
consumers **from the assumptions themselves** — `{d for a in settled for d in
a.downstream_dependencies}` — so that join always matches by construction. All 13
consumers it reports on select at least one assumption, and the promotion report
looks meaningful and healthy. It writes the verdict into `body['promotion']` and
refuses nothing.

So the guard is **informative exactly where it only reports, and inert exactly
where it would enforce.** A reader checking whether the assumption machinery works
would look at the audit report, find it correct and populated, and conclude the
gate was live.

**Not repaired here, deliberately.** Which namespace is right — and whether an
adjustment layer should be a promotion consumer at all — is a design question
about what the assumption registry is meant to govern, and two falsified CRITICAL
assumptions currently name production modules (`nfl.production.nonqb.cs2_state`,
`nfl.production.nonqb.rushing_a1`, `nfl.production.nonqb.shared_pass`). Wiring
the join tonight could start refusing real layers on my reading of an owner's
governance model, which is not mine to decide. Filed with the measurement
attached.

**Pinned by** `nfl/tests/test_assumption_gate_cannot_fire.py`, 17 checks. It
proves the guard's logic is right, then pins both unreachability reasons with
failure messages that say explicitly: if the intersection becomes non-empty or a
production caller appears, that is **good**, and this entry plus the census must
be updated rather than left asserting the gate cannot fire.

## DEF-091 · The board refusal names the first non-PASS stage, not the cause — and it has misdirected the project

**Status:** OPEN (reporting defect, no production change made). Highest-value
finding of this pass.

`nfl/product/orchestrator.py` builds its refusal label as:

```python
first = next((s for s in summary['stages']
              if s['state'] not in ('PASS', 'NOT_APPLICABLE')), {})
... 'refusal': f'{first.get("stage")}: {first.get("code")}'
```

`DEFERRED` is neither `PASS` nor `NOT_APPLICABLE`, so a **deferred** stage is
reported as the refusal even when a later stage is the one that actually failed.
`pipeline.py:284` halts only on `FAIL`/`BLOCKED`, so a DEFERRED stage does not
stop the run and cannot be the cause.

**Measured on today's slate.** `refresh_boards.py` reports
`feature_build: STAGE_DECLARED_UNIMPLEMENTED`, while the same summary's
`first_failure` field correctly reports `player_draws FAIL
DECLARED_DRAW_ARTIFACT_INCOMPLETE`. The artifact already carries the right answer
in a field nobody reads, next to a label everybody reads.

**The cost is not cosmetic.** That label was copied into
`SYSTEM_STATE.json`'s work-queue item 14 ("the second of the two blockers"), into
`nfl/AGENT_STATE.json`, into my own summaries, and into the owner's brief for
today. The whole project has been treating an unimplemented feature builder as the
thing standing between it and a board, when the run reaches a **passing QB layer**
and a **passing joint reconciliation** and fails five stages later on absent
`receiving`/`rushing` layers, whose root cause is an uncaptured dataset.

Full trace: `nfl/research/audit/2026-09-27_FEATURE_BUILD_BLOCKER.md`. Capture
request: OUT-034.

**The fix is one line of selection logic** — prefer `first_failure`, or exclude
`DEFERRED` from the label and report it separately as owed. I have not made it,
because this is the reporting surface the whole board pipeline is judged by and
changing what it says about a live slate a few hours before kickoff is not a
change to make casually. It is also the third instance tonight of the same
family: DEF-084 (the accessor that was not reached), DEF-090 (the guard whose
enforcement was not reached), and now a refusal label that is not the refusal.

**What to preserve if it is fixed:** DEFERRED must stay visible. The correct
output names the failing stage *and* carries the declared debt alongside it —
collapsing `feature_build`'s DEFERRED into silence would trade one wrong reading
for another.
