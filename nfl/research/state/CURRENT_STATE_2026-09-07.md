# NFL Greenfield — what is going on right now

**Snapshot:** 2026-09-07 · **Week 1 kicks off 2026-09-09** (2 days)
**Status:** NFL-0 evidence system built. No predictive model. **NFL-1 not authorised.**
**G0A: 11 PASS / 1 FAIL** — and Item 1's blocker is now **resolved in substance**,
pending the owner's verdict on two remaining points of the twelve-point proof.

**The executor exists.** A GitHub-hosted runner reaches nfl.com and has captured
the official injury report and inactives page — content-addressed, gzipped,
committed and pushed by the runner itself at `33c34de`, with `unmet_targets`
returning empty for the first time.

---

## 1. The two repositories

| | `94924676jp-a11y/nfl` | `94924676jp-a11y/mlb-prop-system-v7` |
|---|---|---|
| Branch | `main` @ `a559da2` | `claude/nfl-greenfield-architecture-stsxmk` @ `74bfa95` |
| Role | **Canonical for NFL** | MLB engine; NFL copy now stale |
| Contents | `sportsplatform/`, `nfl/`, `returns/` | 47k-line MLB system + a duplicate `nfl/` tree |
| Tests | **1,230 assertions across 19 suites, 0 failing** (re-enumerated 2026-09-07) | retired; see `NFL_MOVED.md` there |

**Live drift: RESOLVED.** The MLB repo's duplicate `nfl/` tree was retired on
2026-09-07 and replaced with `NFL_MOVED.md`. This repository is the only source
of truth.

---

## 2. What is scheduled and running

| Routine | State | Notes |
|---|---|---|
| `NFL vintage capture` | **DISABLED** | Turned off for cause at 22:36Z |
| `Agent poll — projections track` | **ENABLED**, hourly | Pre-existing MLB track, unrelated to NFL. Last fired 2026-09-07 00:03Z |

**Nothing NFL-related is running on a schedule.** The capture runs only when
invoked by hand.

### Why the capture trigger is off

Not because it lacks permission. Because it cannot be expressed:

- `create_session` **can** attach a repository source — but does not recur.
- `create_trigger` **recurs** — but accepts no `source_url`.

A trigger-fired session therefore starts with an empty `sources` list, has to
clone the repository itself, and that is what demanded credentials and `gh`.
A scheduled, unattended, repo-attached capture is **not expressible with the
tools available to this session**.

Left enabled it would fire every six hours, spawn a session titled "⚡ NFL vintage
capture", and appear in the routines list as a working capture — which is the
false-green pattern one layer down in the infrastructure.

### One ambiguity I am not resolving in either direction

The second trigger firing recorded `ROUTINE_RUN_STATUS_SUCCEEDED` at 22:51Z,
after I had observed it blocked at 22:31Z and disabled the routine at 22:36Z.
**No commit ever reached the branch.** So: the routine says the run succeeded; the
repository shows nothing arrived; whether the capture executed inside that
session is **unknown to me**. What is verified is narrower than I said earlier —
**no scheduled capture is recorded in the manifest**, all 11 captures there being
manual.

---

## 3. The one thing blocking G0A

**Item 1 — the perishable official cascade is not captured.** Practice
participation, final game status, inactives.

```
UNMET CAPTURE TARGETS: ['final_status', 'inactives', 'practice']
```

Printed on every capture run. The cause is **egress alone**:

| | Result |
|---|---|
| DNS `www.nfl.com` | resolves → 151.101.65.55 |
| `CONNECT www.nfl.com:443` | **`< HTTP/1.1 403 Forbidden`** — local proxy |
| Externally (networked researcher) | **HTTP 200**, server-rendered HTML |
| From a second cloud session | **same 403**, measured not inferred |

**The source is fine. Every executor available here is denied.** The policy is
environment-level, so attaching a repository fixes execution and does nothing for
egress. Those were always two separate failures and only one has been closed.

**What would close Item 1** is not code in either repository: an executor with
egress to nfl.com that can run at kickoff−90 minutes.

---

## 4. Clock pressure

Week 1 opens **2026-09-09** — Wed 09-09, Thu 09-10, Sun 09-13, Mon 09-14.

Every week the official cascade is uncaptured is **permanently lost**: ~132 bits
of availability entropy and ~331 practice trajectories. The archive keeps one row
per player-week, the 2025 schema dropped its only timestamp, and
`injuries_2026.csv` is still **404**.

**What is not at risk:** the cold-start specification was frozen at
2026-09-06T19:37Z, before any 2026 outcome existed (`b356ecaa…`, verified against
a snapshot with 272/272 null results). The fixed-prospective-holdout property
comes from that freeze predating outcomes, **not** from executing predictions
pre-kickoff. It survives whatever happens to the capture.

---

## 5. Open debts and their owners

| Item | State | Owner |
|---|---|---|
| G0A Item 1 | **FAIL** — egress | External: needs an executor with egress |
| `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` | **OPEN** | Networked researcher — official inactives/transactions |
| Official endpoint verification | 3 sources registered, **no URL invented** | Networked researcher |
| ESPN semantic audit | **Cannot be done here** — same proxy denies it | Networked researcher |
| Six of eight scheduler cadences | `confirmed=False` — inferred | Networked researcher |
| MLB repo's duplicate `nfl/` tree | **Live drift** | You |
| NFL-1 authorisation | Blocked at 11/12 | You |
| `NFLVERSE_INJURY_SOURCE_STATUS_CONFLICT` | **RESOLVED** by appended record | — |
| A3 ffopportunity | **CLOSED** — oracle benchmark, non-deployable | — |
| T1 / T3 cold-start rulings | **CLOSED** — 2002 floor, home term retained | — |
| `ARTIFACT_REFERENCE_INTEGRITY` (Rule 006) | **REGISTERED** 2026-09-07 — module + 39 assertions | — |


### Appended 2026-09-07 — `ARTIFACT_REFERENCE_INTEGRITY`, a Class-A failure class

Registered as **Rule 006**, `sportsplatform/governance/artifact_reference.py`,
tested by `test_artifact_reference.py` (39 assertions, 0 failed). Owner ruling
of 2026-09-07, following the P4E baseline-gate incident.

**The rule.** A validation or reproducibility gate must not compare against a
manually transcribed approximation of a canonical artifact value when the
artifact itself is available. A gate must:

1. load its comparison value directly from the canonical artifact;
2. hash and pin the artifact's identity;
3. report that hash in the run output;
4. never take gate truth from a display-rounded rendering — `.log`, `.txt`,
   `.out`, `.md` and `.rst` are refused at source with
   `GATE_SOURCE_IS_DISPLAY_ONLY` and cause `GOVERNANCE`;
5. refuse a comparison value that arrives without artifact provenance
   (`GATE_VALUE_UNSOURCED`), because a typed float and a loaded float are
   indistinguishable once both are floats.

**The incident it names.** P4E's baseline gate carried
`PUBLISHED = {2024: 2.1102566719055176, ...}` as a source literal.
`p4c_results.json` says `2.110274841594967`. The literal agreed with the
artifact to **four** decimal places — the precision `run_p4c.log` prints, and
the precision `predeclaration_p4e.md` §3 quotes — and diverged after it. The
gate then failed at 1.8e-05 against a 1e-9 tolerance and cost a full diagnostic
cycle before the answer turned out to be that the number had never been read.
`transcription_signature()` reports that agreeing-precision as a diagnostic; it
explains a mismatch and never excuses one.

**Debt this closes, and one it does not.** It closes the class. It does not
retroactively re-verify every gate already written in this repository; each is
converted when next touched. `TASK_REPORT_2026-09-07_P4E.md` is left exactly as
written — this record is the appended correction, not a rewrite of it.

---

## 6. What is ready and waiting

Built, tested, and idle until an executor exists:

- **Kickoff-anchored scheduler** — inactives window T−90 → T−10, exactly 80
  minutes. A six-hourly poll cannot discharge it; a capture before the artifact
  exists cannot either; nor can a source not authorised to serve that target.
- **Source registry** — three official sources wired to the targets they serve,
  with their scope semantics. Adding a verified endpoint is **a one-line edit**.
- **Forecast sealing** — `written_at < kickoff`, every consumed partition
  retrieved before the write, input hashes inside the fingerprint.
- **Ingest quarantine** — 47 model-derived, 8 market, 5 outcome, 11 post-hoc
  columns refused for forecast use while remaining readable for archive.

---

## 7. If you want to move something today

1. **Authorise retiring the MLB `nfl/` tree** — closes the drift while the two
   copies are still identical apart from the last three commits.
2. **Point the networked researcher at the endpoint list** — outbox §34 names
   exactly what would close Item 1, and the registry is shaped to accept it.
3. **Decide on NFL-1 under waiver** — the gate says no at 11/12. A waiver naming
   Item 1 would be recorded as a waiver, never as a pass.

Nothing here is blocked on more code in this repository.
