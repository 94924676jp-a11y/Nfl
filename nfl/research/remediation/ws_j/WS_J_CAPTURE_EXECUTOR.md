# WS-J — the anchored capture executor

**CODE CHANGED: YES.** Nine files modified, two created. No commit, no stage, no
push — the coordinator integrates. Measured 2026-09-14 UTC on branch
`claude/nfl-greenfield-architecture-stsxmk`, base HEAD `837d52f`, `python3.12`.

**No manifest row was rewritten, no coverage verdict moved, and nothing was
backfilled.** Week-1 coverage is 63 targets, 15 covered, **47 missed**, 1 not yet
due, before and after every change in this pass. It is the same number because a
miss is a fact about a window that closed, and none of these repairs can reach
backwards into 2026-09-09.

---

## 0. Headline

The capture executor did not fail. **It stopped.** Four independent scheduled
workflows — the `*/30` baseline, the T-90 anchored path, the status anchored path
and the availability watch — ceased within 35 minutes of each other on
2026-09-11 and never ran again. The crons for the twelve-game Sunday slate were
already committed and are demonstrably correct; they simply never fired.

Nothing in this repository said anything for three days. That is the defect worth
fixing, and it is not the stoppage: **the only detector the project had was
`coverage.py`, which by design cannot report a target until its window has
closed — so its alarm is downstream of the loss it reports.** `preflight_t90.py`,
run 10.9 hours before the last surviving window with the executor dead for 83
hours and 47 targets already lost, printed `10 checks, 0 failing` and exited 0.
The test suite was green throughout, correctly: it measures the repository, and
the repository was fine.

Everything repairable without egress is repaired. The cause of the stoppage is
outside this checkout and is filed as **OUT-011**, with the exact API calls that
would answer it.

---

## 1. The diagnosed cause of the 2026-09-11 stop

### 1a. What is established, from the repository alone

Counted on `origin/main` by exact author-string match (`--author=nfl-capture[bot]`
reads the brackets as a regex character class and returns 0 against a real 208):

| workflow | file | schedule | commits | first (UTC) | last (UTC) |
|---|---|---|---|---|---|
| NFL vintage capture | `nfl-capture.yml` | `*/30 * * * *` | 161 | 09-07T00:24:50Z | **09-11T03:38:27Z** |
| NFL status anchored capture | `nfl-status.yml` | generated, hourly | 32 | 09-08T20:04:53Z | **09-11T03:01:09Z** |
| NFL T-90 anchored capture | `nfl-t90.yml` | generated, 5-min step | 14 | 09-07T02:23:46Z | **09-11T00:44:04Z** |
| NFL availability watch | `nfl-availability.yml` | — | 1 | 09-10T18:31:05Z | 09-10T18:31:05Z |

`origin/main` HEAD **is** the last of these, `6d15619`, 2026-09-11T03:38:27Z.
Nothing has been pushed to the default branch since. The last GitHub-Actions
manifest row in this checkout is `20260911T004357Z`, matching WAVE0's
`1034e27 @ 00:44:04Z`.

### 1b. What that rules out, and it rules out a lot

**The workflow definitions are not the cause.**

- Last edit to any workflow: `19ef57a`, 2026-09-10T05:02:19Z. Runs continued
  successfully for **22.6 hours afterwards**. A definition defect does not wait
  a day.
- `main` and the working branch carry **byte-identical** `.github/workflows/`.
  The files are on the default branch, which is where scheduled workflows run
  from.
- The 2026-09-13 crons are present, valid, and **verified to fire inside the
  windows they were generated for** — `test_capture_obligations.py::test_I`
  evaluates every one of the 16 entries minute-by-minute against the real
  window boundaries. The Sunday 13:00 ET window (15:30–16:50Z) has cron cover;
  so does DEN@KC (22:45–00:05Z).
- The same workflow's own crons for 09-09 and 09-10 **did** fire, producing 14
  T-90 commits. The mechanism was working four days earlier.
- **Four independent workflows cannot be stopped by a defect in one of them.**

That leaves an Actions-level or repository-level halt: a disabled workflow, a
disabled Actions setting, an exhausted minutes allowance or spending cap, a
suspended app installation, or a default-branch change. **Distinguishing among
those requires the GitHub Actions API and it is not in this checkout.** WS13 §9.3
says the same thing and it is still true: absence of a commit is not proof a run
did not start.

I am not going to name one of those five as the cause. The repository supports
"the stop is external to the workflow definitions", which is a real narrowing,
and it does not support more.

### 1c. The structural finding, which stands whatever the answer turns out to be

**Nothing that runs inside GitHub Actions can detect GitHub Actions being off.**
A scheduled job cannot page about its own scheduler. Every detector this project
could build in-repo is either downstream of the loss (`coverage.py`) or silenced
by the same event it is meant to report (any workflow).

So the repair is in two halves and only one of them is mine:

1. **Partial failures are now detected in-repo** — one workflow disabled while
   others run, captures that execute but stop writing manifest rows, a runner
   that cannot reach the sources, a cron schedule whose absolute dates have all
   elapsed. That is `.github/workflows/nfl-capture-liveness.yml` plus the
   liveness checks in `preflight_t90.py`.
2. **A total halt needs an observer outside Actions.** Filed as OUT-011. Until
   one exists, the honest answer to "is the capture executor alive" is only ever
   "no evidence has arrived", which observes the consequence and not the cause,
   and the tool now says exactly that rather than implying more.

---

## 2. The second, independent failure of the Actions path — and it is not the stoppage

Measured here for what is now the **third** independent time (WS-L, then WS-K per
blob, now this pass over the 13 distinct `durability: reduce` vintages). It
separates with **zero exceptions**:

| | vintages | raw upstream bytes survive |
|---|---|---|
| observed **only** from GitHub Actions | 6 | **0** |
| observed **at least once** from a non-Actions run | 7 | **7** |

```
depth_charts   361f1c69443cba69  gh=21  local=0   raw LOST
depth_charts   ecc4973e8715d866  gh=44  local=0   raw LOST
depth_charts   f57ef0724d907160  gh=11  local=0   raw LOST
weekly_rosters 0b005c45d924a541  gh=21  local=0   raw LOST
weekly_rosters 125c300ff066d314  gh=11  local=0   raw LOST
weekly_rosters e157129706145664  gh=44  local=0   raw LOST
depth_charts   76d7bcb384ec11e3  gh=23  local=16  raw kept
depth_charts   a14e8dfe865a4b03  gh=0   local=18  raw kept
depth_charts   db0a09454965e6fc  gh=43  local=8   raw kept
weekly_rosters 3b0d5d40dc7816f7  gh=43  local=6   raw kept
weekly_rosters 5ec59c5228198f57  gh=23  local=16  raw kept
weekly_rosters cef497eaeddef07b  gh=0   local=18  raw kept
weekly_rosters fb79560b5c4738a2  gh=0   local=2   raw kept
```

**Read this as a mechanism, not as a statistic.** n=13 with perfect separation is
not a strong statistical claim and none is made. The mechanism does not need one:
`nfl_vintage/raw/` is gitignored (`.gitignore:7`) and Actions runners are
ephemeral, so bytes written there by a runner cannot survive the job. Raw
retention is currently a property of **which machine happened to look**.

That is a second, independent defect of the Actions path sitting alongside the
stoppage: **the runner that stops is also the runner whose evidence never
survives.** It is the coordinator's RL-9 — no artifact consumed by production or
governance may have its only copy in an untracked, gitignored store — and it is
unresolved in the general case. It is not mine to resolve: the persistence path
is `nfl/tools/capture_vintage.py`, WS-K's.

It has one consequence inside my own repair, and I flag it rather than quietly
banking it. WS-L's correction to WS13 §3b is confirmed exactly here: of the three
distinct blobs cited at a nonexistent repo-root `raw/` path,

```
nfl_vintage/raw/depth_charts.76d7bcb384ec11e3.csv    PRESENT
nfl_vintage/raw/weekly_rosters.5ec59c5228198f57.csv  PRESENT
nfl_vintage/raw/schedules.c563178ace7c6637.csv       ABSENT   <- the only real loss
```

So **4 of the 6 rows are a path defect and 2 are a genuine loss**, not 6 losses.
But the corrected location is the gitignored store, so a row that resolved there
would be "verified" against bytes that are not tracked, not backed up, and absent
from any Actions runner. **I have not extended `resolve_blob` to reach it** — that
is WS-K's module and doing so would trade a clean `RAW_ARTIFACT_MISSING_ON_DISK`
for a verification that quietly depends on RL-9 being violated. Handed over in §7.

---

## 3. What was repaired, without egress

### R1 — `preflight_t90.py`: the false green that let 47 windows close

**Pre-repair, reproduced verbatim at 2026-09-14T11:52Z** — 10.9 h before the last
open week-1 window, executor dead 83.4 h, 47 targets already lost, 48 orphan
blobs in the store:

```
  ok    the runner has already pushed evidence unattended
        198 commit(s) in the whole history are authored by nfl-capture[bot]; most recent 1034e27 2026-09-11
  ok    the first target is not already covered
        coverage says FAIL[PERISHABLE_WINDOWS_MISSED]: covered=15, not_yet_due=1

10 checks, 0 failing          exit 0
```

Two separate mechanisms produced that, and both are worth naming because they are
different bugs:

1. *A capability read as a liveness property.* The check asked "has the executor
   EVER pushed" — 198 times — and printed the date of the most recent push as
   decoration. The file's own comment argues, correctly, that recency is a
   separate question; what it never did is ask that question anywhere.
2. *A FAIL swallowed by the caller.* The second check **received**
   `FAIL[PERISHABLE_WINDOWS_MISSED]`, **printed it**, and marked itself `ok`,
   because it failed only on `covered > 0` while coverage was in PASS. A coverage
   FAIL was structurally invisible to it.

**Post-repair**, same command, same moment:

```
MECHANISM -- is the anchored capture path correctly built?     10 checks, 0 failing
LIVE STATE -- can the next window actually produce evidence?    5 checks

  FAIL  the anchored executor is alive
        NO EVIDENCE HAS ARRIVED FROM ANY GitHub-Actions execution for 83.4 hours.
        last GitHub-Actions manifest row 2026-09-11T00:44:00Z, 83.4h ago
        = 167 missed 30-minute ticks; horizon is 2 ticks (60 min)
  BLKD  this executor's basis can discharge an obligation
        LOCAL_INVOCATION (is_github_actions=False)
  ok    a cron entry fires inside the next window
        3 of 16 cron entries fire inside 2026_01_DEN_KC inactives 22:45Z -> 00:05Z
  FAIL  no window has already closed unfilled
        47 of 63 ... 12 have uncredited game-anchored bytes; 35 have nothing at all
  FAIL  the vintage store has no orphan blobs
        48 file(s) named by no manifest row

15 checks (10 mechanism + 5 live state), 3 failing, 1 blocked     exit 1
```

**The staleness horizon is derived, not chosen.** The cadence is *read from
`nfl-capture.yml`* (`*/30` → 30 minutes) rather than written into the check. The
only judgement is the multiplier, and it is the smallest one that can separate
the two things GitHub's own documentation separates: scheduled runs "may be
delayed". A delay past the next tick is indistinguishable from a drop, so one
missed tick proves nothing; **two consecutive ticks cannot be one delayed run.**
It is a floor on detection, not a tuned threshold — raising it hides outages,
lowering it cannot make the check more correct. The measured gap was 167 ticks.
Nothing about this detection needed to be sensitive.

**Liveness is measured on manifest rows, not on commits.** A bot commit is a
proxy: the workflow commits only when the tree changed, so a run that captured
nothing leaves no commit and is indistinguishable from a run that never happened.
A manifest row carries the executor identity the run recorded about itself
(`value.execution_target.executor.is_github_actions`), which answers the question
directly. It also correctly refuses to count the 32 local runs of 2026-09-13 as
the executor being alive — that is exactly the state the check exists to catch.

**On the two result sets.** `_checks()` asks whether the mechanism is correctly
built; `_live_state()` asks whether the world is in a state where the next window
can produce evidence. They are separate functions because they are different
questions and because `test_preflight.py::test_A` asserts every `_checks()`
result passes today — an assertion about the mechanism, which is sound, and which
would otherwise force a live-state observation to be softened to stay green.
Neither set is privileged: `main()` prints both, counts both in one summary line,
and exits non-zero on a failure in either.
`test_capture_obligations.py::test_L` locks the exit code and asserts the string
`0 failing` never appears while the store says otherwise, so the split cannot be
used to hide anything.

### R2 — `check_retention.py`: W7, and the W3 guard generalised

Pre-repair the tool was pointed at `availability.BLOB_ROOT` / `availability.MANIFEST`
and nothing else. Its own output said so: `blobs before 0 after 2 · rows before 0
after 6`. **`R8 NO_ORPHAN_BLOBS` reported PASS throughout the 50-run episode that
left 48 orphans in `nfl/vintage/`.** The check was not wrong about what it
checked; its scope was narrower than its name read.

Post-repair it covers both stores by default. First run against the vintage store:

```
  [vintage]  root nfl/vintage  manifest nfl/vintage_manifest.jsonl
    FAIL  R8   no orphan blobs (standing census)   ORPHAN_BLOB_NOT_FROM_AN_OBSERVATION
          48 file(s) ... named by no manifest row
```

**48, not 49.** RL-8's trap is handled: the collector reads `value.blob`,
`value.blob_sidecar` and the nested list at `value.delivery.raw_evidence_blobs`,
which is the only reference anywhere to
`delivered_injury_evidence.df1dd90380b8d720.html.gz`. It is also **audited**: a
recursive scan finds every string in a row naming a path in the store, and if the
explicit collector missed one the tool returns `BLOCKED
[BLOB_REFERENCE_LOCATION_UNKNOWN]` rather than reporting a false orphan.
Explicit 448 names, recursive 445, missed 0.

**The W3 guard, taken off the log string.** The committed guard is
`grep -qE '^manifest rows appended: [1-9]'` over stdout — and the 50 runs that
lost 2026-09-09 **printed no summary line at all**, which is precisely when a
stdout guard can see least. Two new filesystem checks replace the dependency:

- **R9 `BLOB_WRITTEN_WITHOUT_MANIFEST_ROW`** — every blob this run added is named
  by some manifest row afterwards.
- **R10 `BLOBS_WITHOUT_ANY_MANIFEST_APPEND`** — a run that added bytes appended
  rows. Weaker than R9, kept beside it deliberately: R10 is the condition the 50
  runs actually violated, stated in the terms the incident is recorded in.

Two more honesty repairs, both of which were live false greens:

- **Vacuity is labelled.** With no before-state, R4/R5/R9/R10 compare the store
  against an empty prior and are trivially true. The old tool printed
  `before 0 after 2` and let them read as PASS. They now print
  `[VACUOUS: no before-state]` and do not gate.
- **Standing loss and recurrence are gated separately.** `--gate delta` gates on
  R4/R5/R9/R10 — what *this run* did. The standing R8 census is computed and
  printed on every run and never suppressed. This is not a loosened threshold:
  nothing that was failing now passes, and the alternative was to delete 48
  orphan blobs (destroying evidence) or switch the check off, which is how guards
  die.

### R3 — `coverage.py`: W5, made visible without being credited

Pre-repair, 1,061 PASS rows resolved into `attributed 12 / unattributed 1,049`.
That single bucket contained 1,031 periodic sweeps **and** the 18 rows written by
`nfl/production/nonqb/inactives.py` under `spec_version: official-inactives-1` —
hash-verified, game-anchored, published before kickoff, covering 13 games. Twelve
Sunday games therefore read `inactives: MISSED` with no indication that verified
bytes for them were sitting in the same file. A reader could not tell **"we never
fetched it"** from **"we fetched it and cannot credit it"**, and those need
opposite responses: one is a capture failure, the other is a declaration-and-schema
failure.

The refusal itself was never the defect and has not been touched. Directive 7 §6
requires the target to be declared *before* the fetch; those rows declare nothing;
`eligible_targets` correctly returns `[]` for them and still does — asserted in
`test_F`.

What changed:

- **Seven named dispositions partition every PASS row**, verified to sum exactly:
  `DISCHARGING 12 · DECLARED_NOT_ELIGIBLE 545 · SWEEP_NO_OPEN_TARGET 259 ·
  LEGACY_PRE_DIRECTIVE_7 6 · FOREIGN_SCHEMA 19 · PRE_DECLARATION_CAPTURE 62 ·
  UNDECLARED_NO_ARTIFACT 0 · ARTIFACT_UNVERIFIED 158` = 1,061.
- **A schema registry that refuses.** `KNOWN_SPEC_VERSIONS` names the three
  writers that exist. A row carrying a `spec_version` this module has never read
  returns `BLOCKED[MANIFEST_SPEC_VERSION_UNKNOWN]`. A second writer announces
  itself in exactly one place — it stamps its own `spec_version` — so that is
  where the check belongs. The next one will be refused by name instead of
  quietly counting as nothing.
- **Each miss now says which kind of miss it is**, reported, never credited:
  `missed_with_uncredited_evidence 12`, `missed_with_no_evidence_at_all 35`,
  summing to 47. Every one of the 12 remains in `missed_detail`; `test_F` asserts
  it.
- **Units named.** `attributed_captures` counts `(game_id, kind)` *pairs* and
  always has; its name reads as rows and it was identically equal to
  `dischargeable_captures` (103 = 103) against 12 rows. **It is not redefined** —
  three test modules and `capture_vintage.py` read that key, and silently changing
  a published number is worse than an awkward name. `attributed_rows` is added
  beside it.

### R4 — `_blob_ok`: WS-K's patch, taken as written

Applied from `WS_K_PERSISTED_PROVENANCE.md` §10 rather than re-derived. Effect on
the 368 reduce rows, matching WS-K's prediction exactly:

| | pre | post |
|---|---|---|
| `RAW_SHA256_MISMATCH` | 366 | **0** |
| verify against a digest of the **stored** bytes | 0 | **216** |
| `PERSISTED_DIGEST_ABSENT_HISTORICAL` | — | **152** |
| `RAW_ARTIFACT_MISSING_ON_DISK` | 9 | 6 |
| total artifact-excluded | 375 | 158 |

**The trap is locked by a test, and it is the load-bearing one.** A reduce row
with no persisted digest must never fall back to `value["sha256"]` — that field
describes an upstream file that was never stored, and using it silently
re-asserts the exact claim WS-K disproved.
`test_G` constructs the adversarial case: a row whose `sha256` **does** match the
stored bytes, marked `durability: reduce`, with no persisted digest. It must
still refuse with `PERSISTED_DIGEST_ABSENT_HISTORICAL`. The 152 read **"cannot be
checked"** — never "wrong", never "fine". Hashing an unattested blob and
recording the result would be circular and is refused.

**No coverage verdict moves on this.** All 368 reduce rows carry
`discharge_eligibility.n_eligible == 0`: they discharge nothing and never could.
15 covered / 47 missed, unchanged.

### R5 — the workflows

| repair | where | what it was |
|---|---|---|
| `${PIPESTATUS[0]}` instead of `$?` after a pipe | `nfl-capture.yml`, `nfl-status.yml` | `$?` after `\| tee` is **tee's** status, always 0. `nfl-t90.yml` has carried a comment naming this bug since 09-10; the other two still had it. The recorded `exit=` said nothing about the capture. |
| interpreter asserted | all three + liveness | below 3.12 the engine does not import and two of the causes are at AST level, before any test can report. A cache-missed setup-python would have failed for a reason nothing named. |
| store snapshot before capture | all three | supplies the before-state that makes R4/R5/R9/R10 non-vacuous |
| filesystem blob/manifest gate after the commit | all three | the W3 guard, not dependent on a line of stdout having printed |
| **the manifest-row guard at all** | **`nfl-status.yml`** | it never had one. The guard was added to `nfl-capture.yml` and `nfl-t90.yml` on 2026-09-10 and this file was not touched, so a status run could commit a blob, append no row, and report success — the exact condition that lost 2026-09-09. |
| new | `nfl-capture-liveness.yml` | hourly, read-only, captures nothing, outside the capture concurrency group so it can never delay a T-90 window. Fails when evidence stops arriving or the next window has no cron entry. States the limit it cannot overcome. |

Step ordering is preserved everywhere: the commit still runs **before** the FAIL
gate, guarded with `if: always()`, so a control failure cannot discard captured
bytes. `test_J` asserts the ordering in all three files.

`nfl-t90.yml` and `nfl-status.yml` are generated. I edited
`nfl/tools/gen_t90_schedule.py` and `nfl/tools/gen_status_schedule.py` and
regenerated, because a generated file cannot be repaired at the artifact —
hand-editing it fails the drift guard on the next run. **Those two generators
were not on my owned-files list; flagging the boundary crossing explicitly.**
Schedule identities are unchanged: `SCHED-2a2924d4966fbd3d`,
`SCHEDNG-906facecf4b1f272`, 16 and 10 cron entries.

---

## 4. What is proven, and what is BLOCKED

`nfl/tests/test_capture_obligations.py` — 20 functions, **101 checks, 0 failing,
2 BLOCKED**.

| required proof | section | state |
|---|---|---|
| the scheduled workflow actually runs | H, H2, I, I2 | **proven at the definition level**: liveness detects silence and clears on fresh evidence; every cron entry evaluated minute-by-minute; an expired absolute-date schedule is detected. **That GitHub honoured a cron: BLOCKED, OUT-011.** |
| a source fetch is attempted | M | **BLOCKED (NETWORK), OUT-012.** Not mocked. |
| failures write explicit manifest evidence | D, E | proven: unknown schema BLOCKS; dispositions partition every PASS row |
| blobs cannot be written without manifest rows | A, A2, B, B2, C, J | proven, with the guard-deletion control |
| a manifest cannot claim PASS with no qualifying capture | E, F, L | proven, including that the tool never prints `0 failing` while the store disagrees |
| `basis_can_discharge` represents authority | G2 | proven for all six basis classes |
| T-90 and status jobs can discharge what they are scheduled for | I, J, G2 | proven |

**Why two proofs are BLOCKED rather than passing.** A mock of a fetch proves that
the mock returns what the mock was told to return.
`nfl/research/parallel_pass/ws11/WS11_FALSE_GREEN_AUDIT.md` already names three
P0 false greens of exactly that shape. `run_suite.py` reports them as BLOCKED —
explicitly not a pass — and `test_N` asserts that the corresponding outbox entries
exist, so a blocked proof is a filed request rather than a shrug.

---

## 5. Filed to the outbox

- **OUT-011** — why every scheduled workflow stopped at 2026-09-11T03:38:27Z.
  Carries the four-workflow stoppage table, what the repository rules out, and
  five numbered API requests: the run list since 2026-09-11 (**the decisive
  question is whether runs existed and failed, or whether there were no runs**),
  each workflow's `state` field, the Actions minutes / spending-limit state,
  whether `main` is still the default branch, and the 2026-09-13 job logs if any
  runs exist. Also asks for an observer outside Actions, or for a ruling that it
  is out of scope. **Marked time-critical**: `2026_01_DEN_KC` inactives,
  22:45Z–00:05Z tonight, is the last open week-1 obligation and the only one not
  already lost. Three cron entries fire inside it. **Do not backfill it if it
  closes unfilled.**
- **OUT-012** — a live source fetch cannot be proven from this executor. Records
  that **two independent blocks are live at once** — no egress, *and* a basis
  that cannot discharge even with egress — so fixing either alone changes
  nothing. Asks for any one of: confirmation the three official URLs serve
  content; a verified `official_transactions` endpoint (**177 consecutive
  `ENDPOINT_NOT_YET_VERIFIED` rows, never captured once**); a test of
  `reduce_recoverability_assumption`, requested on WS-K's behalf since the outbox
  is mine.

---

## 6. Escalation — RL-7, held, not resolved

`assert_retention_policy` returns `NOT_APPLICABLE` for 8 of 10 sources. The
obvious repair is to widen its scope. **I did not, and I am holding the same line
WS-K took.** RET-001 R7 forbids reduction outright while both affected sources
are `durability="reduce"`; widening the scope as written fails both immediately.
That is a policy contradiction, not a bug, and resolving it from either side
decides an owner question by implementation. **Owner ruling requested.** I have
also not widened `reduce_cols`, even though WS-L showed the reduction drops
`status` and `pos_slot` that production consumes.

---

## 7. Handed to WS-K

**Requirement — the blob/manifest invariant belongs in the writer, not only in
the guard.** Mine is a *detector*: it runs after the fact, in the workflow, and
catches a violation once the bytes are already on disk. That is the right place
for the recurrence gate and the wrong place for the guarantee. WS-K's
"every persisted blob must self-verify" and my "no blob without a manifest row"
meet inside the persistence path, and only the writer can make the second one
structural:

> **A durable blob must not become visible to git without the manifest row that
> names it, in the same operation.** Concretely: stage the blob and append the
> row before either is committed, and on any failure between the two, remove the
> staged blob rather than leaving it. A blob that outlives its row is an orphan —
> nothing attributes it to a source, a game, a window or a basis, so it can
> discharge nothing and cannot be told apart from a file dropped in by hand.
> `check_retention.py --store vintage --gate delta` will then be a *check on a
> guarantee* rather than the guarantee itself.

**Second item, smaller.** `resolve_blob` could resolve the two rows citing
`raw/depth_charts.76d7bcb384ec11e3.csv` and
`raw/weekly_rosters.5ec59c5228198f57.csv` — the bytes are present and verify.
**I deliberately did not.** The corrected location is `nfl_vintage/raw/`, which
is gitignored, so resolving there converts a clean `RAW_ARTIFACT_MISSING_ON_DISK`
into a verification that quietly depends on RL-9 being violated. If it is done,
it should carry its own resolution code naming the untracked store rather than
reading as an ordinary PASS. `raw/schedules.c563178ace7c6637.csv` (2,177,171
bytes) is in neither store and is a real, final loss.

---

## 8. Not backfilled — the list, and it stays

- **47 week-1 targets missed. Still 47.** 17 `practice`, 16 `final_status`, 14
  `inactives`.
- **All of 2026-09-09 absent from the manifest**, including the four runs inside
  the NE@SEA T-90 inactives window (22:56, 23:07, 23:23, 23:46Z). 31 runs
  executed; zero rows survive. Perishable pages are overwritten in place. **No
  remedy exists; the guards prevent recurrence only.**
- **Six lost raw vintages**, named in §2. With the roster three go the
  active-roster state for those days and every name→`gsis_id` crosswalk from
  those vintages; WS-L proved them unrecoverable at any price, since no `dt`
  column exists to slice back to.
- **`schedules.c563178ace7c6637`**, in neither store.
- **152 reduce rows** that will never carry an attested digest of their stored
  bytes. They read `PERSISTED_DIGEST_ABSENT_HISTORICAL` and must not be
  "verified" by hashing what is there.
- **DAL@NYG has no inactives evidence of any kind.** The RotoWire quarantine
  stays quarantined.

---

## 9. Blast radius and identity impact

**Identity impact: none.** No freeze file, no `SIM_FORMULA`-equivalent, no
parameter, no projection, no price, no schedule identity. `SCHED-2a2924d4966fbd3d`
and `SCHEDNG-906facecf4b1f272` are unchanged; the 16 and 10 cron entries are
unchanged; no file under `nfl/production/` was touched.

**Coverage impact: none, by construction.** 63 / 15 / 47 / 1 before and after.

Files changed (9 modified, 2 created, +1,409 / −78):
`.github/workflows/nfl-capture.yml`, `nfl-status.yml`, `nfl-t90.yml`,
`nfl-capture-liveness.yml` (new), `nfl/capture/coverage.py`,
`nfl/tools/preflight_t90.py`, `nfl/tools/check_retention.py`,
`nfl/tools/gen_t90_schedule.py`, `nfl/tools/gen_status_schedule.py`,
`docs/AGENT_OUTBOX.md` (append only), `nfl/tests/test_capture_obligations.py` (new).

Not touched: `nfl/tools/capture_vintage.py`, `nfl/capture/registry.py`,
`nfl/capture/persisted_provenance.py`, `nfl/capture/availability.py`,
`nfl/capture/execution.py`, `nfl/capture/schedule.py`, everything under
`nfl/production/`, `nfl/prospective/`, and the other workstreams' test modules.

Regression sweep over every test module that imports `coverage`,
`check_retention`, `preflight_t90`, `_blob_ok` or `persisted_provenance`, plus the
capture suites — run one module at a time, never the full suite:

```
test_attribution  test_coverage  test_discharge_identity  test_execution_target
test_non_g0a_isolation  test_perishable_immutability  test_persisted_provenance
test_preflight  test_t90_workflow  test_vintage_selector  test_volatility
test_capture_manifest_integrity  test_availability_retention  test_capture_states
test_capture_schedule  test_capture_windows  test_t90_synthetic_eligibility
test_product_orchestration  test_harness_audit
```

---

## 10. Reproduction

```bash
cd /home/user/nfl
python3.12 nfl/tools/preflight_t90.py --season 2026 --week 1            # exit 1
python3.12 nfl/tools/preflight_t90.py --season 2026 --week 1 --gate scheduler
python3.12 nfl/tools/check_retention.py                                 # both stores
python3.12 nfl/tools/check_retention.py --store vintage --snapshot-to /tmp/pre
python3.12 nfl/tools/check_retention.py --store vintage --gate delta \
    --before-blobs /tmp/pre.blobs --before-manifest /tmp/pre.manifest
python3.12 nfl/tests/run_suite.py --only test_capture_obligations
python3.12 -c "
from nfl.capture.coverage import coverage
e = coverage(2026, 1, manifest_path='nfl/vintage_manifest.jsonl').evidence
print(e['covered'], e['missed'], e['missed_with_uncredited_evidence'])"
git log --format='%an|%ad|%s' --date=iso origin/main | head -40
```

**CODE CHANGED: YES. NOTHING COMMITTED. 47 STILL MISSED.**
