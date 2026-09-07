# Task report — event-anchored T−90 capture and `game_id` attribution

**Date:** 2026-09-07
**Repository:** `94924676jp-a11y/nfl`, `main`
**HEAD:** `4646141`
**Authorized scope:** the two narrow changes, nothing else.
**NFL-1:** not authorized, not executed, not requested.
**G0A:** still **11/12**. Item 1 still **PARTIAL / PENDING REAL EVENT**.

---

## A correction before anything else

In my previous message I said Week 1 opens "in ~45 hours". It does not. The
first T−90 window opens **2026-09-09T22:50Z**, which was **68.6 hours** out at
the time I wrote it. I had the right window and misstated the gap. There is more
runway than I implied, and none of the work below depended on the wrong figure.

---

## What was authorized, and what I built

> *"AUTHORIZE only the narrow event-anchored T−90 capture change."*

Two pieces, because the blocker had two halves and neither works alone.

### 1. `game_id` attribution on the capture row

`nfl/capture/attribution.py`. Every capture row now records which game(s) it was
taken for: targets whose window contains `retrieved_at`, and whose kind this
source is authorised to serve.

**The clock is `retrieved_at` and only `retrieved_at`.** Not `requested_at`, not
the workflow's start time. A request issued at T−91 whose bytes arrive at T−89
captured the T−89 page; one whose bytes arrive after kickoff captured the wrong
information state. The clock that decides is the one on the bytes.

**It is a claim, not a verdict.** The capture layer proposes; `coverage`
disposes. Every claim is re-checked against the plan independently, and the
record is never taken at its word.

### 2. Event-anchored execution

`nfl/tools/gen_t90_schedule.py` generates `.github/workflows/nfl-t90.yml` from
real kickoff times in the captured schedule snapshot.

```
2026-09-09 22:50Z -> 00:10Z   1 game   2026_01_NE_SEA
2026-09-10 23:05Z -> 00:25Z   1 game   2026_01_SF_LA
2026-09-13 15:30Z -> 16:50Z   8 games  ATL_PIT, BAL_IND, BUF_HOU, CHI_CAR, ...
2026-09-13 18:55Z -> 20:15Z   4 games  ARI_LAC, GB_MIN, MIA_LV, WAS_PHI
2026-09-13 22:50Z -> 00:10Z   1 game   2026_01_DAL_NYG
2026-09-14 22:45Z -> 00:05Z   1 game   2026_01_DEN_KC
```

16 cron entries, 5-minute step. **Verified: 102 nominal firings, 102 inside a
window, 0 outside, 17 per window.** Every entry exists because a kickoff put a
window there. None is a round-number cadence — that is the difference from the
`*/30` baseline, and it is what "event-anchored" means here.

Only the 80-minute per-game window is anchored. Practice and final-status
windows are 20 hours wide and the baseline covers them many times over; 20 hours
of five-minute entries would bury the ones that matter.

---

## What this does not claim

**It does not guarantee execution.** GitHub documents that scheduled runs may be
delayed or dropped under load, and no arrangement of cron entries prevents that.
This raises the chances inside an 80-minute window from about two to about
seventeen. It does not promise seventeen, or one.

**Discharge is decided on evidence, never on which workflow fired.** In-window,
authorised source, attributed to the game. A baseline `*/30` run that lands
inside a window is a real capture and counts exactly the same. Anchoring
improves the odds that the evidence exists; it is not itself the evidence.

**A capture inside the window does not prove the page listed that game's
inactives.** It proves the official artifact was retrieved during that game's
window, which is the obligation. Confirming the content names the game is parser
work and is not claimed here.

---

## The property the whole mechanism rests on

A written attribution is only worth something if it cannot be used to write
"covered" into a file. Section F of `test_attribution.py` forges five claims and
requires that every one of them discharges nothing:

| Forgery | Result |
|---|---|
| right game, **wrong time** | target still missed |
| **unauthorised source**, perfectly timed | target still missed |
| claim naming a **different game** | target still missed |
| claim naming a **game that does not exist** | target still missed |
| claim declaring its **own ten-year window** | target still missed |
| *the honest version of the same row* | **discharges** |

The last line matters as much as the others: a function that refuses everything
would pass the first five and be useless.

---

## Two things I got wrong and fixed

**A guessed week.** My first version of the attribution picked a "current week"
from the schedule by proximity to kickoff. It returned `None` on 2026-09-07 — a
day on which Week 1 practice windows opened at 20:00Z — because it measured the
wrong distance. Worse than wrong, it was unnecessary: a window is an absolute
interval, so the honest question is *which windows contain this instant*, and
the week is an output rather than an input. Guessing a week can attribute a
capture to the wrong game. Asking about windows cannot.

**An environment-dependent test.** The workflow tests use PyYAML, which is not
in the standard library. On a bare runner they would have skipped silently and
the suite would have reported green for work it did not do — Class D. They now
report `BLOCKED` and are counted apart from passes. Verified by simulating the
import failure: `32 passed, 0 failed, 1 blocked`.

---

## Tests

**1,159 assertions across 17 suites, 0 failing** (up from 1,078).

| New suite | Assertions |
|---|---|
| `test_attribution.py` | 46 |
| `test_t90_workflow.py` | 35 |

Both carry guard-deletion proofs:

- bypass `can_discharge` and ESPN claims **16 inactives targets** — the
  promotion the directive forbids, made visible;
- strip the attribution block from an otherwise identical capture and the target
  goes back to missed, so the attribution is what closed it.

**Drift guard.** `test_t90_workflow.py` §D regenerates the workflow from the
current snapshot and fails if the committed file differs by a byte. A cron block
made stale by one moved kickoff is silent, and its cost is an unrecoverable
window — so the suite notices, not a missed kickoff.

---

## Verified live

- Workflow registered on GitHub as **"NFL T-90 anchored capture"**, `state:
  active`, id `351929134`. It parsed on GitHub's side — the earlier YAML defect
  showed up as the file path being used as the workflow name, and that is not
  what happened here.
- Dispatched once (run `34076132045`) as a smoke test of the new code path on a
  real runner. **This is explicitly not offered as T−90 proof** and is not a
  substitute for one; the directive rules out a manual dispatch as equivalent
  evidence and I am not proposing it as such.
- The baseline capture continues unattended; `bdb8bcf` was pushed by
  `nfl-capture[bot]` during this task.

---

## What is still open

| | |
|---|---|
| **The real T−90 event** | Not occurred. First window `2026-09-09T22:50Z`, ~68h out. Nothing about it is simulated. |
| Parser confirms the page names the game | Open. Not claimed by attribution. |
| `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` | **OPEN**, untouched. `weekly_rosters.status` still forbidden. |
| `PLAYER_GSIS_UNMAPPED` | **OPEN**. Zero gsis identifiers on the page, measured. |
| Broadcast payload join (79 vs 16) | **OPEN**. |
| Blob dedup defeated by render nonce | **OPEN**. Substantive digest is recorded; storage policy unchanged, since that is your call. |
| Weekly regeneration of the cron | **OPEN**. Week 1 is committed; week 2 needs a regeneration run. The drift guard will fail the suite if it is forgotten, which is the intended behaviour. |
| ESPN | **UNCHANGED** — CANDIDATE FALLBACK. Claims nothing, tested. |

---

## Files changed

```
A  nfl/capture/attribution.py
A  nfl/tools/gen_t90_schedule.py
A  .github/workflows/nfl-t90.yml        generated, 16 cron entries
A  nfl/tests/test_attribution.py        46 assertions
A  nfl/tests/test_t90_workflow.py       35 assertions
M  nfl/tools/capture_vintage.py         claims on every capture row
M  nfl/capture/coverage.py              reads claims, one entry per game
```

Commit `4646141`. Nothing deleted, no capture rewritten, no existing artifact
touched.

---

## What happens next, without further instruction

Nothing that needs authorizing. The cron entries are in place, the attribution
runs on every capture, and the accounting will record whatever the first window
actually produces — including, if it comes to it, `PERISHABLE_WINDOWS_MISSED`
naming the games it missed. I would rather report that honestly than have the
system unable to tell.

I am not starting NFL-1, NFL-2, projections, simulation, DFS, market integration
or optimization. No wager recommended or discussed.

---

*Report path: `TASK_REPORT_2026-09-07_T90_ANCHORING.md`*
