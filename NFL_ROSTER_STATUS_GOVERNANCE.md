# `weekly_rosters.status` — GOVERNANCE RULING

**Date** 2026-09-10 · decided by measurement, not by argument.

## RULING: **B — the old rule was too broad**, with one addition the evidence forced

The prohibition was right about the thing it measured and wrong to generalise
from it. The narrower rule now in force:

> **Roster status may govern point-in-time roster MEMBERSHIP where provenance
> proves the observation was already effective before the team's kickoff, and
> may never represent game-day active status. Post-hoc codes such as `INA` are
> prohibited.**

**The addition, which the evidence forced and which the drafted rule did not
contain:** provenance must be established by **two independent checks, not
one** — an observation clock strictly before kickoff **and** the absence of any
post-hoc code for the teams in scope. Neither alone is sufficient. The vendor
took about twelve hours to populate `INA` after the NE/SEA kickoff, so a capture
inside that window is post-game **and `INA`-free**, and a content check alone
would pass it.

---

## 1. Is it literally the same field?

**Yes, literally.** `nfl/ingest/allowlist.py` line 121 quarantines
`'weekly_rosters': {'status': Category.POSTHOC}`. `roster_status.status_map`
reads `r.get('status')` from the raw `weekly_rosters` capture. Same source, same
column name, no aliasing.

The prohibition's stated reason, verbatim:

> `weekly_rosters.status` is the dangerous one — measured ACT → 0.9715 snap
> rate, INA → 0 of 3,438. A near-perfect predictor of playing, available only
> afterwards.

That measurement is correct. **It is a measurement of a retrospective file**,
and it is close to a tautology there, for the reason in §2.

---

## 2. What each value means, and when it is established

**The decisive measurement, from ONE capture** — `weekly_rosters.3b0d5d40dc7816f7`,
observed `2026-09-10T12:07:17Z`, 2026 week 1:

| team | had played? | ACT | INA | ACT + INA |
|---|---|--:|--:|--:|
| SF | no | **53** | 0 | 53 |
| LA | no | **52** | 0 | 52 |
| NE | **yes** | **48** | **7** | 55 |
| SEA | **yes** | **48** | **7** | 55 |

**After a team plays, the vendor re-partitions the roster.** Before the game
`ACT` is the 53-man active roster; after it, `ACT` is the **48 who dressed** and
`INA` is the 7 who did not. 48 is the league gameday active limit. The same
label carries two different quantities, and which one you get depends entirely
on whether the capture precedes that team's kickoff.

This is why the prohibition's measurement came out at 0.9715. In a
retrospective file `ACT` already means *was active for that game*, so predicting
snaps from it is not forecasting — it is reading the answer.

| value | meaning **before** the team's kickoff | established | post-hoc? |
|---|---|---|---|
| `ACT` | on the 53-man active roster | on signing / elevation | **only after the game**, when it is re-cut to the 48 who dressed |
| `DEV` | practice squad | on signing to the squad | no |
| `RES` | reserve / injured reserve | on the transaction | no |
| `CUT` | released | on the transaction | no |
| `EXE` | exempt list | on the league action | no |
| `INA` | **does not exist pregame** | **only after the game** | **YES** |

---

## 3. Do values mutate retrospectively? **Yes, and here is the ledger**

Two captures of the same season and week, `5ec59c5228198f57`
(`2026-09-06T18:50:51Z`) against `3b0d5d40dc7816f7` (`2026-09-10T12:07:17Z`),
2,945 shared `(season, week, player)` keys:

| transition | on the two teams that PLAYED | on the other thirty | reading |
|---|--:|--:|---|
| **`ACT → INA`** | **14** | **0** | **entirely game-driven** |
| `CUT → DEV` | 1 | 24 | ordinary transactions |
| `RES → CUT` | 3 | 13 | ordinary transactions |
| `DEV → ACT` | 5 | 5 | elevations, some post-game |
| `ACT → RES` | 0 | 3 | ordinary |
| `ACT → CUT` | 1 | 1 | ordinary |
| `ACT → DEV` | 0 | 1 | ordinary |
| **total** | 24 | 47 | |

17 rows appear only in the later capture (15 `DEV`, 1 `EXE`, 1 `ACT`); none
disappear.

**`ACT → INA` is 14 of 14 on the two played clubs and 0 elsewhere** — perfectly
attributable to the game. The non-`INA` transitions are 10 of 57 on those clubs
against a 2-of-32 team share (17.5% against 6.3%): elevated, because a club also
transacts after playing, but 82.5% of them happen to clubs that had not played
at all. Those are transactions, not outcomes.

**Three SF players moved between the two captures** (`DEV → ACT`, `ACT → RES`,
`ACT → DEV`), so the churn is not confined to played teams and the later capture
is genuinely more current for SF.

---

## 4. Is the file point-in-time or retrospectively finalised?

**Neither, and the distinction matters.** It is a **rolling current-state
table** whose rows are *labelled* by season and week. The week key is a label,
not a freeze: week-1 rows changed four days into week 1.

A capture taken at time *T* is a faithful record of the roster **as of T**. That
makes our immutable vintage a genuine point-in-time record of *what the vendor
said when we looked* — which is what question 6 asks — but only at the instants
we actually captured. It cannot answer what the roster was between captures, and
it must never be read as a frozen statement about the week it is labelled with.

---

## 5. Does the vintage preserve what was knowable at forecast time?

**Yes, for roster membership, at each capture instant** — the bytes are stored
before parsing, content-addressed, and append-only, and the information-set
selector times a source by the earliest capture carrying that content hash.

**No, for game-day active status** — that quantity did not exist at forecast
time for a team that had not played, and where it does exist in the file it is
an outcome.

---

## 6. The three concepts, kept apart

| concept | source that establishes it | available pregame? | R5 may use it? |
|---|---|---|---|
| **ROSTER MEMBERSHIP** | `weekly_rosters.status`, pregame capture | yes | **YES**, for pool construction |
| **GAME ELIGIBILITY** | no reachable source | **no** | no — `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` stands |
| **GAME-DAY ACTIVE / INACTIVE OUTCOME** | official inactives at T-90; `INA` retrospectively | only via the official list | **never** from this field |

`ACT` is never turned into `GAME_ACTIVE`. The vocabulary in
`nfl/production/nonqb/inactives.py` keeps `ROSTER_ACTIVE`, `GAME_ACTIVE`,
`OFFICIAL_INACTIVE`, `INJURY_QUESTIONABLE` and `UNKNOWN` as five distinct
names precisely so the collapse cannot be written down.

---

## 7. Are `DEV` / `RES` / `CUT` / `EXE` safely knowable at the forecast clock?

**Yes, and the proof is that they are transactions rather than outcomes.** Each
is established by a dated league action that precedes our capture; 82.5% of
observed transitions among them occur on clubs that had not played; and none of
them is created by a game being played, unlike `ACT → INA` which is created by
nothing else.

**The honest caveat:** `DEV → ACT` occurred 5 times on the two played clubs, so
a *post-game* capture can carry post-game transactions for that club. That is
not a reason to distrust the codes pregame; it is a reason to require the
observation clock to precede kickoff, which is exactly what the new guard does.

---

## 8. What changed in the code

`nfl/production/nonqb/roster_status.py`:

* `POSTHOC = {'INA': ...}` — declared, with the measurement in the docstring.
* `status_map(..., kickoff_utc=...)` refuses `ROSTER_STATUS_OBSERVED_AFTER_KICKOFF`
  when the chosen capture is at or after kickoff for the teams in scope. **This
  is the clock check and it runs first**, because it does not depend on the
  vendor having updated anything.
* `status_map` refuses `ROSTER_STATUS_POSTHOC_CONTAMINATION` when a post-hoc
  code appears for those teams. **This is the content check.**
* `active_pool` drops **only** the four declared codes. Anything unrecognised is
  **kept and counted** under `kept_unrecognised_status`, because dropping a
  player on a code we do not understand is the forcing-concentration move R5
  exists to avoid — and it was how `INA` would have been silently removed.
* `run_forecast` passes the game's kickoff to the R5 call site.

Verified on tonight's data: SF/LA pregame → `ROSTER_STATUS_OK` (ACT 105);
NE/SEA with their kickoff → `ROSTER_STATUS_OBSERVED_AFTER_KICKOFF`; NE/SEA with
no clock supplied → `ROSTER_STATUS_POSTHOC_CONTAMINATION`. Each guard catches it
alone.

---

## 9. Why not A, and why not C

**Not A.** A blanket prohibition would forbid the pregame quantity on evidence
gathered entirely from the retrospective one. The measurement behind the ban —
`ACT → 0.9715` — is a property of a file in which the 48/7 re-partition has
already happened, and it does not describe the 53-man reading at all. Keeping
the rule as written would also forbid nothing useful: it would leave R5's
measured contamination repair unavailable while the actual leak, `INA`,
remained reachable through the generic "not on the active roster" fallback that
existed until today.

**Not C.** The semantics are not unresolved. They are measured, in one file, on
four clubs, with the transition ledger to match, and the resulting rule is
enforceable by two independent mechanical checks rather than by a reader's care.

**And not B merely because it preserves R5.** If the evidence had shown
`DEV`/`RES`/`CUT` mutating in a game-driven way, or the pregame `ACT` count
sitting at 48 rather than 53, the answer would have been A. It showed the
opposite, twice, in the same file.

---

## 10. Amendment to record

`nfl/ingest/allowlist.py` keeps `weekly_rosters.status` as `POSTHOC` — **the
quarantine is not lifted**. What is now written down is the single narrow
exemption and its conditions: `roster_status.py` is the only permitted consumer,
for pool construction only, under both guards, and any other reader of that
column remains refused.
