# D1 — why Denver sealed zero skill rows, and Kansas City thirteen

**Verdict: (b), a plumbing defect.** Denver does not lack the input. The input
exists in this checkout, captured, clocked and content-hashed, a day before the
board was built. The readiness gate cannot read it, because the schema it reads
has no field for it. Repaired in `readiness.py`; no frozen file touched.

Frozen candidate identity `nfl/production/nonqb/layers.py`:
**`481f005f682cd721` at start, `481f005f682cd721` at end.** Unchanged.

---

## 1. The deciding line

**`nfl/production/nonqb/readiness.py:742`**

```python
if NEEDS_REPORT_STATUS and pop['report_status'] == 0:
    return {'team': team, 'state': 'INJURY_REPORT_INCOMPLETE', ...}
```

`pop['report_status']` is the count of that club's injury rows whose
`report_status` column is non-empty, built at `readiness.py:517-520` from the
`injuries` vintage family. The condition is **"not one single row on this club
carries a game designation."**

A second, slate-level copy of the same condition is at `readiness.py:307`.

The verdict propagates: `layers.appearance` (frozen, `layers.py:119`) tests
`state.startswith('READY')` and defers; `football_engine.py:588-630` scopes
that deferral to the one club and records `APPEARANCE_TEAM_DEFERRED`.

## 2. The exact inputs that differ

Both clubs are read from the same blob,
`nfl/vintage/injuries.66e960ec81fccc6e.csv.gz`, at the same cut
`2026-09-14T20:58:33Z`:

| | rows | `report_status` filled | verdict |
|---|---|---|---|
| **DEN** | 1 | **0** | `INJURY_REPORT_INCOMPLETE` |
| **KC** | 11 | **2** | `READY` |

Denver's single row is **Marvin Mims Jr., WR, Foot, Full Participation in
Practice, no designation**. Kansas City's two filled rows are **Josh Simmons
(Out)** and **Chamarri Conner (Out)**. Kansas City's other **nine** rows are
blank exactly as Denver's one is.

That is the whole difference. The gate does not check that a club's report is
complete — under it Kansas City passes with 9 of 11 rows blank. It checks
whether **at least one player on the club is hurt enough to be designated**.
Denver failed it for being healthy.

## 3. The input the mechanism could not see

The 2026 Week 1 **official league game-status report** for this game says, in
full, under its own `## MONDAY, SEPT. 14` heading:

> ### **BRONCOS**
> No injury designations
>
> ### **CHIEFS**
> * **OUT:** OT Josh Simmons (back), DB Chamarri Conner (knee)

The same report produced both verdicts. Kansas City passed because two of its
players are Out. Denver failed because none of its are.

This is not an inference. It is a captured artifact:

* raw bytes `nfl/vintage/delivered_injury_evidence.df1dd90380b8d720.html.gz`
* ingested by `nfl/tools/ingest_delivered_injuries.py`, step 5, recorded in
  `nfl/research/live/DELIVERED_INJURY_INGEST_2026-09-13.json`:
  *"5 club(s): DEN,HOU,MIA,MIN,WAS — recorded as evidence, NOT converted to
  rows and NOT clearing any gate"*
* durable in `nfl/vintage_manifest.jsonl`, capture `20260913T124700Z`, under
  `value.explicit_no_designations`. The DEN record carries
  `kind: EXPLICIT_TEAM_NO_INJURY_DESIGNATIONS`,
  `evidence_text: "No injury designations"`, `game_date: 2026-09-14`,
  `report_period: "2026 REG Week 1 game-status report; explicit game date"`,
  `source_id: NFL_final_report`,
  `content_sha256: df1dd90380b8d720…`, `retrieved_at: 2026-09-13T12:47:00.990929Z`,
  `publication_time: 2026-09-11T21:02:00Z`,
  `source_modified_time: 2026-09-12T23:07:53.998Z`,
  and an XPath `locator`.

Every clock is before the board's cut and before kickoff.

**The correspondence is exact and is the strongest single piece of evidence
here.** The gate deferred five clubs on this slate — DEN, HOU, MIA, MIN, WAS.
The delivered package carries an explicit no-designation statement for five
clubs — DEN, HOU, MIA, MIN, WAS. Same five. No false positives, no misses. The
gate was never detecting missing reports. It was detecting *"this club
designated nobody"* and reporting it as *"this club has not filed"*.

### Why it was unwired, and why that is not the usual defect

Unlike `board.depth_rank`, nothing was swallowed. `delivered_injuries.py:90-95`
and `:429-452` name three team states — (a) designations present, (b) rows
filed and no designation filed **yet**, (c) the club has explicitly stated it
has none — observe that the nflverse schema can spell only (a) and (b), and
state in writing that wiring (c) into the gate *"is a governance decision, not
an ingestion repair"*. `test_delivered_injury_ingest.py:519` pins it.

`docs/AGENT_OUTBOX.md` then declared this an **EVIDENCE CEILING** on
2026-09-14, naming HOU, MIN and MIA as having lost their whole non-QB board to
it, and listing what would lift it — *"the official final injury report
captured as its own source"* and *"a feed or parser that preserves the report's
own date and type"*. **Both had already arrived on 2026-09-13**, the day
before, in the package above, which carries `report_period` and `game_date`.
The ceiling was lifted and nobody joined the two halves.

## 4. The repair

One file, `nfl/production/nonqb/readiness.py`, three changes:

1. `GAME_STATES` gains `READY_BY_EXPLICIT_NO_DESIGNATION`. Spelled with a
   `READY` prefix because **every** consumer tests `state.startswith('READY')`
   — `layers.py:119` (frozen), `football_engine.py:595-605`,
   `readiness.py:700`, `pool_audit.py:679`, `completeness.py:123`. Nothing
   outside this file needed editing.
2. A new `explicit_no_designation(season, team, kickoff_utc, as_of)` reads the
   statement from the manifest under the **same as-of cut** as the rest of the
   gate.
3. At the `INJURY_REPORT_INCOMPLETE` branch, that statement — if it exists and
   is lawful at the cut — returns the new state, carrying its full citation on
   the readiness record.

**What was deliberately not done.** No threshold was invented; nothing is
derived from row counts or blank counts or from how many clubs would pass.
`NEEDS_REPORT_STATUS` is still `True` and the test that pins it still passes —
the requirement is not lowered, a second way of meeting it is recognised. The
statement does **not** clear `INJURY_REPORT_NOT_YET_FILED` (a club with no rows
filed no *practice* report either, a different field with different consumers),
nor `INJURY_REPORT_STALE`, nor a chronology failure.

**The cut is load-bearing, and proved so:**

| written_at | DEN verdict |
|---|---|
| `2026-09-13T12:00:00Z` (before the statement was retrieved) | `INJURY_REPORT_INCOMPLETE` |
| `2026-09-13T12:47:01Z` | `INJURY_REPORT_STALE` |
| `2026-09-14T20:58:33Z` (the board's cut) | `READY_BY_EXPLICIT_NO_DESIGNATION` |

## 5. Before and after

**Controlled comparison** — same tree, same moment, only the gate's DEN verdict
substituted (`nfl/research/v2/d1/DIAG_DEN_READY/efc10ecd2f927abb`):

| | players | DEN skill | `UNATTRIBUTED_OPPORTUNITY_MASS` |
|---|---|---|---|
| baseline | 19 | 0 | **2** (DEN/rushing, DEN/receiving) |
| DEN read as READY | **33** | **14** | **0** |

33 is exactly the intended figure, and 14 exactly the deferred count, from
`DEN_KC_GAME_LEVEL_POOL_MANIFEST.json`.

**Real build with the repair applied**, `python3.12 /tmp/run_tonight.py
2026-09-14T20:58:33Z nfl/research/v2/d1/DEN_NODESIG_REPAIR 1000
V1_CANDIDATE_R9` → `SEALED`, `nfl/research/v2/d1/DEN_NODESIG_REPAIR/b282c52f7976c682`:

* **33 players** — DEN 3 QB / 4 RB / 6 WR / 4 TE, KC 3 QB / 3 RB / 6 WR / 4 TE
* DEN readiness `READY_BY_EXPLICIT_NO_DESIGNATION`
* hard findings **27 → 6**, both `UNATTRIBUTED_OPPORTUNITY_MASS` **gone**

**Read that 27 → 6 carefully; most of it is not mine.** The real build sits on
a later tree that includes other agents' in-flight work on `board.py` and
`names.py`, which cleared all 20 `IDENTITY_DEPTH_ROLE_CONFLICT` findings. The
controlled comparison is the one that isolates this change, and in it
`IDENTITY_DEPTH_ROLE_CONFLICT` went 20 → **34** — one per newly sealed player,
the same pre-existing name-join defect, simply applied to 14 more rows.

**And one finding IS mine, and it is not good news.**
`RUSH_ACCOUNTING_FAILURE` went 1 → 2:

> DEN/rushing: 149 of 1000 draws deal the named rush owners MORE carries than
> the team's own carry level, by up to 6.12 carries.

Kansas City has carried the identical defect all along (148 of 1000, up to
9.69). Denver's was invisible only because Denver had no rushing rows to fail
on. So the repair does **not** make DEN/rushing publishable — it is still
`QUARANTINE_FAMILY`. What changed is the reason: from *"we refuse because we
believe Denver never filed a report"*, which was false, to *"we refuse because
the carry arithmetic does not close"*, which is true and which someone else
owns (`rushing_a1.py` / `football_engine.py`, both held elsewhere).

## 6. Open items for reconciliation

1. **`nfl/tests/test_appearance_team_scope.py` now fails 8 checks, and this
   change is the cause.** That suite hardcodes `SCOPED_GAME =
   ('2026_01_DEN_KC', '2026-09-14T16:30:00Z')` at line 80 and asserts at line
   212 `check('DEN is INJURY_REPORT_INCOMPLETE', ...)`. It uses DEN's deferral
   as the live fixture for the team-scoping mechanism. With DEN ready there is
   no scoped game to test. **I did not edit the suite** — rewriting a guard's
   test so it agrees with my change is the wrong direction. It needs a fixture
   that is genuinely deferred with no explicit statement, and at this cut the
   slate has none: of 32 clubs, 22 `READY`, 3 `READY_WITH_COMPLETE_INPUT`, 5
   `READY_BY_EXPLICIT_NO_DESIGNATION`, and only NE and SEA incomplete — and
   they are *both* incomplete, so NE@SEA is a whole-game deferral, not a
   one-club scoping. The scoping path at `football_engine.py:588-630` has no
   live exercise on this slate. That is a real loss of coverage and it is worth
   a decision, not a patch.
2. **This changes what the gate counts as evidence.** `delivered_injuries.py`
   says that is a governance call. It is reversible — one uncommitted file —
   and it is flagged rather than assumed.
3. **Four other games are recoverable by the same repair**: BUF@HOU, GB@MIN,
   MIA@LV, WAS@PHI, the three named in the evidence-ceiling entry plus
   Washington. Not built here; D1 owns `nfl/research/v2/d1/` only.
4. **Freshness, requested in `docs/AGENT_OUTBOX.md` OUT-014.** The newest
   `injuries` capture is `2026-09-13T15:45:56Z`, **29.2 hours** before the
   board's cut, and the no-designation statement's `source_modified_time` is
   **~46 hours** before it. Lawful, not fresh. Neither blocks anything.

## 7. What was checked and found sound

* Denver's sparseness is real and independently corroborated: the NFL's own
  report page captured at `2026-09-11T00:45Z`
  (`official_injury_report.f42a6ad10fcfb7dc.html.gz`) also carries exactly one
  Denver row, Marvin Mims Jr., and ten for Kansas City.
* The vintage selector picked the correct, newest lawful capture. No path is
  wrong, no exception is swallowed, no key mismatched.
* The 33 sealed rows are real Denver and Kansas City players from the captured
  roster vintage. Nothing zero-filled, nothing substituted, no league average
  dressed as a player. Jaylen Waddle appearing on Denver was checked against
  `weekly_rosters.bdab6ecee12d44a4.raw.csv.gz` and is what the capture says:
  `2026 / week 1 / DEN / WR / ACT`.
