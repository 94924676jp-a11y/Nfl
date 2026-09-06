# Return: NFL Greenfield — Owner Directive 5

**Date:** 2026-09-06 · **Branch:** `claude/nfl-greenfield-architecture-stsxmk` · **Head:** `4526d74`
**NFL-1 not executed.** No NFL-2, opportunity, skill, simulator, DFS, market or
Hard Rock work. Frozen constants and the original freeze record untouched.

---

## 0. A false green of mine, withdrawn before anything else

I reported in Directives 3 and 4 that vintage capture was **"scheduled and
demonstrably running."** The schedule exists. **It has never run.**

Fired deliberately as this pass's diagnostic, the scheduled session blocks on a
permission prompt trying to **clone the repository** — it never reaches the
capture. Verified against the manifest: **zero scheduled captures have
completed**; all eight entries are manual runs from this session.

I saw a trigger register and reported it as running. That is exactly the false
green the owner standard warns about. It is withdrawn, and it makes Item 1's FAIL
firmer rather than weaker.

---

## 10. Final G0A score — **11 PASS / 1 FAIL. Item 1 remains FAIL.**

## 9. Item 1 verdict — **FAIL**

Not because the source is unknown. Because **no executor exists that can capture
it**, and the one scheduled path cannot even run the captures it *can* reach.

---

## 1. Exact local NFL.com failure class

**`LOCAL_PROXY_CONNECT_403` — a local egress-policy denial. Not source-side.**

| Check | Result |
|---|---|
| DNS `www.nfl.com` | **resolves → 151.101.65.55** |
| TCP to proxy `127.0.0.1:37673` | connected |
| `CONNECT www.nfl.com:443` | **`< HTTP/1.1 403 Forbidden`**, `Connection: close` |
| TLS | never reached |
| Origin HTTP status | never reached |

The proxy's own log records it, unprompted:

```
connect_rejected | www.nfl.com:443 |
  gateway answered 403 to CONNECT (policy denial or upstream failure)
```

Same class for `static.nfl.com`, `api.nfl.com` and `site.api.espn.com`.

**This corrects my own earlier record.** I previously wrote "nfl.com measured at
000". `-w %{http_code}` reports 000 for DNS failure, TCP refusal, TLS failure and
a proxy refusal alike — so "000" reads as *the site is down* when the truth is
*our proxy refused a site that answers 200 elsewhere*. `probe_nfl_sources.py` now
classifies the five cases separately and records a proxy refusal as **BLOCKED**
with `says_about: "this executor's egress policy"`, never as a FAIL about the
source. Audit: 33 targets, 25 PASS / 1 FAIL / 7 BLOCKED.

---

## 2. Updated source registry and authority hierarchy

Three axes, deliberately not merged:

| Source | Authority | Rank | Source status | Executor access | Serves |
|---|---|---|---|---|---|
| `official_injury_report` | **OFFICIAL** | 1 | VERIFIED_REACHABLE_EXTERNALLY | LOCAL_PROXY_CONNECT_403 | practice, final_status |
| `official_inactives` | **OFFICIAL** | 1 | VERIFIED_REACHABLE_EXTERNALLY | LOCAL_PROXY_CONNECT_403 | inactives |
| `official_transactions` | OFFICIAL | 1 | UNVERIFIED | UNTESTED | — |
| `espn_injuries_json` | **CANDIDATE_FALLBACK** | 9 | VERIFIED_REACHABLE_EXTERNALLY | LOCAL_PROXY_CONNECT_403 | **none** |
| `injuries`, `schedules`, `depth_charts`, `weekly_rosters` | ARCHIVE | — | reachable | REACHABLE | **none** |

**Why `SourceStatus` and `ExecutorAccess` are separate fields.** Conflating them
produced a false statement in this repository. A source that answers and an
executor that is denied are different facts with different owners and different
fixes.

**A regression this introduced, and closed.** When the official sources gained
real URLs they moved off `PENDING_ENDPOINT_VERIFICATION` and **silently vanished
from the capture output** — the most important gap in the system became invisible
by being better understood. Every non-`REACHABLE` source is now reported on every
run, with its own code (`LOCAL_EXECUTOR_NO_EGRESS`).

`can_discharge` is unchanged in intent and now enforced across a wider set: no
ARCHIVE source and no CANDIDATE_FALLBACK may discharge any perishable target.

---

## 3. `NFLVERSE_INJURY_SOURCE_STATUS_CONFLICT` — resolved by appended record

`nfl/NFLVERSE_INJURY_SOURCE_STATUS_RESOLUTION_01.json`. The original artifact is
**untouched — sha256 verified identical before and after** (`880b1e0b…`).

**Status: `RESOLVED — DOCUMENTATION STALE / UPSTREAM REPLACED / 2025 ARTIFACT
RETROACTIVE`.**

**Both claims were true, which is why neither could settle it alone.** The status
page was accurate about the *original upstream* (NFL GSIS Data Exchange, dead)
and stale about the *pipeline* (replaced, restored). The row count was accurate
about the *file* and silent about *how it came to exist*.

Recorded as explicitly **not** established: that the 2025 artifact has
point-in-time integrity, and that the restored pipeline establishes 2026 live
reliability.

**The standing rule is unchanged and is now better founded.** The mirror
discharges no intraweek obligation — enforced by `serves_kinds=()`, not by
convention. Before, that was a defensible precaution; now it is the documented
shape of the artifact, because **a retroactive backfill cannot carry vintages it
never observed.**

---

## 4. ESPN endpoint semantic audit — **cannot be performed from here**

The audit the directive asks for — practice participation? game status?
inactives? publication timestamps? overwritten history? — **requires fetching the
endpoint, and the same proxy denies it** (`CONNECT` → 403).

So the honest answer is that **it has not been audited**, and it is registered
accordingly:

- `CANDIDATE_FALLBACK`, rank 9, **`serves_kinds = ()`** — it discharges nothing.
- Tests assert it may not discharge practice, final_status or inactives, and that
  OFFICIAL outranks it.

Being easier to parse than the official page is not a promotion. The audit is
assigned.

---

## 5. Executor for perishable capture — **none exists**

The decisive finding, and it is measured rather than assumed.

- **`list_environments` returns exactly one environment**: `env_013685uC8YBUxYXMC6Cqi6Mf`.
- The scheduled session I fired ran in **that same environment** (confirmed in
  its own session record), so it inherits the same proxy policy.
- And it **never got as far as testing that**, because it blocked on a
  permission prompt cloning the repo.

**Mechanisms considered and rejected, per "do not invent infrastructure":**

| Candidate | Verdict |
|---|---|
| This session | Denied by proxy (403 CONNECT) |
| Scheduled trigger → new cloud session | Same environment, same policy; and blocks on a credential prompt before running |
| A second environment with egress | **Does not exist** — one environment total |
| The networked researcher | Manual, human-mediated. Cannot guarantee a T−90 window, and per the directive a one-time research fetch is not scheduled capture |
| An external capture runner | **Would have to be invented.** Not proposed |

---

## 6. Event-anchored execution schedule

Implemented and tested (`nfl/capture/schedule.py`, 107 assertions):

| Target | Window | Cadence source |
|---|---|---|
| practice | filing deadline → +20h | Wed/Thu, **confirmed** for Sunday games |
| final_status | filing deadline → +20h | Friday, **confirmed** |
| **inactives** | **T−90 → T−10, exactly 80 min** | **confirmed** externally |

Retained per §4: **no return to six-hour polling for inactives.** A general
background poll may remain, but the inactives target is discharged only by an
execution inside its own window, from a source authorised to serve it.

**It has no executor for the official targets.** The schedule is correct and
unrunnable.

---

## 7. End-to-end live capture evidence available now

Against the twelve-point proof, honestly:

| # | Requirement | Archive sources | **Perishable official targets** |
|---|---|---|---|
| 1 | Reach the registered source | ✅ | ❌ proxy 403 |
| 2 | Retrieve non-empty real bytes | ✅ | ❌ |
| 3 | Raw bytes before parse | ✅ | — |
| 4 | Record clocks without fabrication | ✅ | — |
| 5 | Content-address | ✅ | — |
| 6 | Append manifest | ✅ | — |
| 7 | Attribute to target/game/team/week | partial | — |
| 8 | Source authorised to discharge | n/a — archive serves none | ❌ no reachable authorised source |
| 9 | Early capture cannot discharge | ✅ tested | ✅ tested |
| 10 | Post-kickoff cannot discharge inactives | ✅ tested | ✅ tested |
| 11 | Obligation clears only on a persisted artifact | ✅ tested | ✅ tested |
| 12 | **Future event-anchored execution scheduled** | ❌ **zero scheduled runs have completed** | ❌ |

**Points 9–11 are tests, and the directive is explicit that tests are necessary
and not sufficient.** Points 1, 2, 8 and 12 are the live requirements, and all
four fail for the perishable targets. Point 12 now fails for the archive sources
too.

---

## 8. Evidence obtainable only when the first Week 1 artifact publishes

- Whether `injuries_2026.csv` publishes at all, and on what cadence — the
  restored pipeline is unproven for live 2026.
- Whether any future nflverse injury artifact carries a per-row clock. The 2025
  schema does not.
- Whether the official practice report for a Thursday game actually lands on the
  **derived** Mon/Tue/Wed calendar. Six of eight cadences are `confirmed=False`,
  and three of week 1's four game days run on inferred calendars.
- Real markup for `nfl.com/injuries/`, needed for the §7 HTML discipline —
  raw-first, fingerprint the bytes not a normalised DOM, parser version in
  provenance, fail closed on shell-only content. **Not written, because writing a
  parser against markup nobody has seen would be inventing the schema.**

---

## 11. Tests and artifacts changed

**Changed:** `nfl/capture/registry.py` (three-axis model, ESPN, `LOCAL_EXECUTOR_NO_EGRESS`),
`nfl/tools/probe_nfl_sources.py` (failure classification, official URLs probed),
`nfl/tools/capture_vintage.py` (report every non-reachable source),
`nfl/tests/test_source_registry.py` (two-axis assertions; PENDING exemplar moved).

**New:** `nfl/NFLVERSE_INJURY_SOURCE_STATUS_RESOLUTION_01.json`.

**Untouched, deliberately:** the cold-start freeze, its constants, its correction
record, and the original conflict artifact.

**Suite: 811 assertions, 0 failing.**

---

## 12. May NFL-1 be authorised under the existing gate, without a waiver?

# **No.**

G0A is **11/12**. Item 1 is FAIL. The gate requires 12/12 and the directive is
explicit that no waiver, DEFERRED state or reinterpretation may substitute.

**What would change the answer** is not code in this repository. It is an
executor with egress that can run at T−90 — and, separately, a scheduled path
that can complete a run unattended, which today it cannot for any source.

If the owner wants NFL-1 to proceed before that exists, it needs an explicit
waiver naming Item 1, and I would record it as a waiver rather than a pass.

**The honest result is 11/12, so 11/12 is what I am returning.**

---

## Addendum — the retry, 2026-09-06 22:30–22:36 UTC

The scheduled capture was retried once, with the network probes deliberately
ordered **before** any git operation so the clone blocker could not hide the
answer. It blocked again.

| Attempt | Fired | Blocked on | Elapsed |
|---|---|---|---|
| 1 | 22:23:11Z | `git clone` with a credential askpass helper | ~90s |
| 2 | 22:30:48Z | **`command -v gh`** | ~49s |

**The second block is the informative one.** `command -v gh` is a read-only
existence check with no credentials, no network and no side effects. A session
running in `auto` permission mode still halted on it and moved to
`SESSION_STATUS_REQUIRES_ACTION`.

**Conclusion, and it is broader than Item 1.** The blocker is not egress, not
credentials, and not the repo. **Scheduled sessions in this environment cannot
execute unattended at all** — they stop for approval on ordinary commands and
wait for a human who, by construction, is not there. That forecloses the
scheduled-executor option for *every* source, official or archive, and it is why
Item 1 could not have been closed by adjusting the trigger prompt.

**Whether the network probes ran before the block is unknown to me.** `get_session`
exposes the pending action, not the transcript. I am not claiming the diagnostic
result either way — the local measurement stands on its own evidence (DNS
151.101.65.55, proxy `CONNECT` → 403), and the environment identity is the
argument that a scheduled session inherits it.

### The trigger is now disabled

`trig_01WvoJ4HywtxxAKDEaW4LJWV` → `enabled: false`, renamed
**"NFL vintage capture (DISABLED — no unattended executor)"**.

Left enabled it would have fired every six hours, spawned a session titled
"⚡ NFL vintage capture", blocked, and produced nothing — while appearing in the
routines list as a working capture. That is the false-green pattern again, one
layer down in the infrastructure: **a schedule that looks like a running capture
and is not one.** Better to have it visibly off than invisibly broken.

Re-enabling is one `update_trigger` call once an executor exists that can run
unattended. Nothing else about it needs to change.

### Effect on the verdicts

**None. Both are reinforced.**

- **Item 1: FAIL**, and now for two independent reasons rather than one — no
  egress to the official sources, *and* no unattended execution path at all.
- **G0A: 11/12.**
- **NFL-1: not authorisable** under the existing gate without an explicit waiver.

The twelve-point proof's point 12 — "demonstrate that a future event-anchored
execution is scheduled for the required window" — now fails on the plainest
possible reading: there is no scheduled execution, because the schedule has been
turned off for cause.
