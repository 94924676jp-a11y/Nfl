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
