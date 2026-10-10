# Sunday 2026-10-11 final inactives: executor audit and authorized fallback (written 2026-10-10 ~18:30Z)

**Verdict: no automated executor is verified to deliver the final inactives for the eight 1:00 ET games.** The
authorized manual fallback is built and rehearsed end to end (§4). The automated route needs two owner decisions (§3).

## 1. Windows (schedule capture `schedules.322e30495d45d3d8`)

All eight games share one window. Kickoff is 2026-10-11 13:00 ET = **17:00Z**. The nominal inactive deadline is T-90 =
**15:30Z**, and the generated capture window runs 15:30Z–16:50Z. The 16 clubs are CHI, GB, CIN, MIA, CLE, NYJ, HOU,
TEN, IND, PIT, LV, NE, MIN, NO, NYG and WAS.

| Game | Kickoff |
|---|---|
| 2026_05_CHI_GB | 17:00Z |
| 2026_05_CIN_MIA | 17:00Z |
| 2026_05_CLE_NYJ | 17:00Z |
| 2026_05_HOU_TEN | 17:00Z |
| 2026_05_IND_PIT | 17:00Z |
| 2026_05_LV_NE | 17:00Z |
| 2026_05_MIN_NO | 17:00Z |
| 2026_05_NYG_WAS | 17:00Z |

## 2. What actually runs (GitHub API, read 2026-10-10 ~18:15Z)

The default branch is `main` at `da671be6`, which is not branch-protected per the API. GitHub reads `schedule:`
definitions from the default branch only.

| Workflow on `main` | Definition | Last runs (actual receipts) | Can it deliver Sunday's inactives? |
|---|---|---|---|
| `nfl-t90.yml` (T-90 anchored) | generated for **week 1**; every cron entry is in September | last run **2026-09-15T00:05Z** | **No**: nothing is scheduled for 10-11 |
| `nfl-status.yml` (status anchored) | generated for week 1 | last run 2026-09-12T16:05Z | No |
| `nfl-capture.yml` (periodic) | `*/30` | today: 06:07Z, 12:48Z, 17:33Z, all success. **Observed gaps are 4–6 hours**, not 30 minutes | **Not reliably**: it may or may not land inside 15:30–16:50Z |

**Evidence from the capture manifest** (what the inactives source returned inside past Sunday windows,
15:00–17:00Z):

| Sunday | Week | Result |
|---|---|---|
| 09-13 | W1 | T-90 schedule live: 14 PASS captures in the window (pages captured) |
| 09-20 | W2 | 4 in-window captures, all DEFERRED (SOURCE_HAS_NO_ROWS_YET) |
| 09-27 | W3 | 4 in-window captures, all DEFERRED (SOURCE_HAS_NO_ROWS_YET) |
| 10-04 | W4 | **no capture in the window at all** |

So no automated route has delivered a usable Sunday inactive list since Week 1. A green workflow run is not that
evidence. Both NO_EGRESS rows and DEFERRED rows mean the list was not obtained.

## 3. Automated route: prepared, not deployed (owner decisions)

- **The schedule change.** `docs/sunday_executor/nfl-t90.WEEK5.PROPOSED.yml` is the file
  `nfl/tools/gen_t90_schedule.py --season 2026 --week 5 --write` produces: 18 cron entries over 7 windows, schedule
  identity `SCHED-d577f05fff8d8ca9`. `docs/sunday_executor/nfl-t90.main-to-week5.patch` is its diff against `main`,
  and only schedule lines change: main's job section is byte-identical.
- **Why it is not applied:**
  1. It must land on the default branch, an outward change that is yours to make (OD-4).
  2. Editing `.github/workflows/nfl-t90.yml` on this branch trips the repository's own mode boundary (`run_suite.py`
     reports BOUNDARY VIOLATED). The guard stays in force.
  3. The job fetches `nfl.com/inactives/`, whose terms appear to bar automated retrieval (OD-1, still open).
- **Even if applied,** Weeks 2–3 show the source returning no rows inside the window, and GitHub may delay or drop
  scheduled runs. Treat it as additional chances, not as a guarantee.

## 4. The authorized manual fallback: built and rehearsed today

**Route.** At or after 15:30Z, you copy each club's official inactive list (from the club or league release) into a
text file, one club per line, `CLUB: Name, Name, ...`, with a `SOURCE:` line. Then run:

```
python3.12 nfl/tools/sunday_paste.py 2026W5 PASTE.txt \
    --packet nfl/dfs/salaries/classic_early_2026W5/evidence_packets/2026W5_SUNDAY_OWNER.json \
    --state  nfl/dfs/salaries/classic_early_2026W5/research_projection/rebuild_2026-10-10_prelock/STATE.json
python3.12 nfl/integrations/inactives_coverage.py \
    --state  nfl/dfs/salaries/classic_early_2026W5/research_projection/rebuild_2026-10-10_prelock/STATE.json \
    --packet nfl/dfs/salaries/classic_early_2026W5/evidence_packets/2026W5_SUNDAY_OWNER.json
```

Then rebuild with `nfl/integrations/rebuild.py ... --evidence-packet <the Sunday packet>`.

**What was fixed to make this work today:**
- `sunday_paste.py` read only the production state path `DK_<slate>_EARLY_STATE.json`, which does not exist for a
  research-universe slate. The fallback would have **failed on Sunday**. It now takes `--state`.
- It records a per-club receipt time (`club_lists`), so the coverage gate can tell a list taken before 15:30Z from a
  final one.

**Coverage gate** (`nfl/integrations/inactives_coverage.py`, new). PASS only when every one of the 16 clubs has its own
list received at or after 15:30Z. Otherwise it is `BLOCKED[SUN_INACTIVES_COVERAGE_INCOMPLETE]`, naming each club as
MISSING, STALE_BEFORE_WINDOW, RECEIPT_TIME_UNKNOWN or REHEARSAL_NOT_EVIDENCE. A missing list is never "everyone active".
Pasted lists are AGGREGATOR tier, never upgraded to a captured document.

**Rehearsal**, 2026-10-10, packet `2026W5-REHEARSAL-20261010`, synthetic lists built from the Friday Outs plus Jeanty:

1. The paste resolved all 16 club lines: 16 pool inactives and 16 Questionables written ACTIVE-not-on-list.
   Williams was ACTIVE; Bagent stayed the named starter.
2. The coverage gate gave **BLOCKED for all 16 clubs (REHEARSAL_NOT_EVIDENCE)**, as designed.
3. State → role → projection → worlds (252 players × 2,000 worlds, sanity PASS; written only to the ignored
   `nfl/dfs/salaries/runs/w5_rehearsal_2026-10-10/`). Jeanty went:
   - state REPORTED_INACTIVE_HIGH_CONFIDENCE;
   - role NOT_PLAYING;
   - projection NOT_PLAYING_REPORTED_INACTIVE;
   - **absent from every world**.

   Mike Washington Jr. took the LV backfield at 10.52. The state's packet record reads REHEARSAL_NOT_EVIDENCE.

**Also armed:** the 15:40Z Sunday trigger in this session, and OUT-045/OUT-046 to the networked agent for the club
releases.
