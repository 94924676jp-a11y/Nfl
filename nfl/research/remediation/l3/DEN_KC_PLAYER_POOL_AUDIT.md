# DEN @ KC — player-pool audit

**Game** `2026_01_DEN_KC` · Denver at Kansas City · GEHA Field at Arrowhead Stadium
**Kickoff** 2026-09-15T00:15:00Z (schedule vintage `schedules.2b59c058ffa3ab99`, `gameday 2026-09-14`, `gametime 20:15`, `result` empty)
**Forecast cutoff declared for this audit** `written_at = 2026-09-14T16:30:00Z` → as-of cut **2026-09-14T16:30:00+00:00**
**Mode audited** `V1_CANDIDATE_R8` (`active_roster_only: true`), with `V1_CANDIDATE` / `PRODUCTION_BASELINE` (`active_roster_only` **absent**) reported beside it.
**Module** `nfl/production/pool_audit.py` · **Tests** `nfl/tests/test_pool_audit.py` (17 functions, 40 checks, SUITE PASS)

**CODE CHANGED OUTSIDE MY OWN TWO FILES: NO.** Nothing was repaired. Every
defect below is flagged and left standing.

---

## 0. The answer in one paragraph

**180 players were considered** — every 2026 week-1 roster row for DEN
and KC in the selected roster vintage. **34 reach the
allocation pool** and **7 reach a modelled quantity**, and
all 7 of them are quarterbacks. Not one non-quarterback is
modelled for this game, because Denver's injury report carries **one row with
`report_status` unfilled** and `layers.appearance` defers the **whole game**
when either club is not READY. The 27 non-QB players who
cleared every eligibility test are stopped at that gate, Kansas City's
included. Separately and independently, **a Kansas City quarterback on the
reserve list is in the model pool** and is the club's declared incumbent.

---

## 1. Report early: does the roster `status` column survive the reduce step?

**No — and the audit is not blocked by it.** Both halves matter.

`vintage_selector.column_check` run against the roster vintage this pool is
built from returns **`VINTAGE_DECLARED_COLUMN_ABSENT`**, missing
**['status', 'full_name']**. The persisted reduced blob is five columns:
`season, week, team, gsis_id, position`. That is WS-L / RL-2 confirmed live
today, on the vintage captured at 2026-09-14T16:16:33.199666+00:00.

What has changed since WS05 wrote E5 is that the **full bytes of the same
capture are now retained durably inside the repository**. The manifest row for
`bdab6ecee12d44a4` declares
`raw_blob = nfl/vintage/weekly_rosters.bdab6ecee12d44a4.raw.csv.gz` with
`raw_blob_durable: True`, and this audit reads status from
**that file, resolved by content hash, not by a directory glob**. So:

* the reduced artifact still cannot answer eligibility at all;
* the same capture's 36-column bytes can, and they are durable rather than
  ephemeral;
* `roster_status.py` and `vintage_selector.raw_candidates` still resolve raw
  bytes by globbing `nfl_vintage/raw/<source>.*.csv` — an uncompressed file in
  a directory `capture_vintage._persist` labels `full_bytes_ephemeral_at`. That
  glob happens to find this capture too, because the capture layer writes
  **both** copies. **Checked, and it is not a live split**: the pool vintage and
  the status vintage are the same content hash, `bdab6ecee12d44a4`.
  The two-selector structure that WS21 records as P3d is unchanged and remains
  latent; it did not fire here and I am not claiming it did.

**One thing that does not survive and is not retained twice:** `full_name`. The
reduced blob has no player name, so a board built only from it can identify
players by `gsis_id` and by nothing a human reads.

---

## 2. Which vintage each column came from

Every input was selected through `vintage_selector` under a declared clock.
Forbidden inputs, recorded in the artifact: filesystem mtime, glob order, filename order, file size, row count, latest on disk.

| Column | Source family | Blob | Clock | Note |
|---|---|---|---|---|
| PLAYER, ROSTER STATUS, `status_description_abbr` | `weekly_rosters` raw | `nfl/vintage/weekly_rosters.bdab6ecee12d44a4.raw.csv.gz` | retrieved 2026-09-14T16:16:33.199666+00:00 | same capture as the pool vintage, resolved by content hash |
| TEAM, POSITION (pool identity) | `weekly_rosters` reduced | `nfl/vintage/weekly_rosters.bdab6ecee12d44a4.reduced.csv.gz` | retrieved 2026-09-14T16:16:33.199666+00:00 | 5 columns; carries no eligibility fact |
| DEPTH STATUS (vendor rank) | `depth_charts` raw | `nfl/vintage/depth_charts.f66f0c2583dba463.raw.csv.gz` | vendor `dt` 2026-09-14T13:53:31Z | `pos_slot` present: True |
| depth ordinal actually consumed | `depth_charts` reduced via `depth_vintage.captured` | `depth_charts.f66f0c2583dba463.reduced.csv.gz` | vendor `dt` 2026-09-14T13:53:31Z, 2.61h before the cut | `pos_slot_available: False` |
| INJURY STATUS | `injuries` | `injuries.66e960ec81fccc6e.csv.gz` | retrieved 2026-09-13T15:45:56.665261+00:00 | walked newest-first; the feed is not monotone |
| GAME-DAY STATUS | `official_inactives` | **none** | — | `POOL_AUDIT_NO_OFFICIAL_INACTIVES` for ['DEN', 'KC'] |
| newly signed / newly elevated | `official_transactions` | **none exist** | — | `POOL_AUDIT_NO_TRANSACTIONS_FEED` |

**L1's captures were available and were used.** The roster and depth vintages
here are the 2026-09-14T16:16Z capture, 8.0 hours before kickoff. The injuries
feed has **not** been recaptured since 2026-09-13T15:45:56Z; that is the newest
lawful one and it is what the readiness gate is reading.

---

## 3. Counts

| | QB | RB | WR | TE | total |
|---|--:|--:|--:|--:|--:|
| Considered (all positions: 180 rows, 58 at modelled positions) | 7 | 13 | 25 | 13 | 58 |
| Allocation pool, **R8** (`active_roster_only` on) | 7 | 7 | 12 | 8 | **34** |
| Allocation pool, **V1_CANDIDATE / baseline** (no filter) | 7 | 13 | 25 | 13 | **58** |
| **Model pool** (reaches a modelled quantity) | 7 | 0 | 0 | 0 | **7** |

Roster status, both clubs, from the capture at 2026-09-14T16:16:33.199666+00:00:
* **ACTIVE_ROSTER** — 106 players (33 at modelled positions)
* **PRACTICE_SQUAD** — 34 players (11 at modelled positions)
* **RELEASED** — 23 players (7 at modelled positions)
* **RESERVE_LIST** — 17 players (7 at modelled positions)

No `RET` row and no `INA` row exists for either club — the content guard that
proves the capture is pregame for these two clubs passed.

### Every exclusion reason, with counts

| Reason | Players | What it means |
|---|--:|---|
| `POSITION_NOT_MODELLED(DB)` | 31 | the engine governs no estimand for this position; `RECEIVING_POS = (WR, TE, RB)`, `CARRY_POS = (RB,)`. |
| `POSITION_NOT_MODELLED(OL)` | 29 | the engine governs no estimand for this position; `RECEIVING_POS = (WR, TE, RB)`, `CARRY_POS = (RB,)`. |
| `POSITION_NOT_MODELLED(DL)` | 28 | the engine governs no estimand for this position; `RECEIVING_POS = (WR, TE, RB)`, `CARRY_POS = (RB,)`. |
| `POSITION_NOT_MODELLED(LB)` | 27 | the engine governs no estimand for this position; `RECEIVING_POS = (WR, TE, RB)`, `CARRY_POS = (RB,)`. |
| `APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE)` | 27 | `layers.appearance` defers the WHOLE game because DEN is not READY. Applies to both clubs. |
| `R5_ROSTER_STATUS_DEV` | 11 | practice squad. Removed by R5. Under `V1_CANDIDATE` he is NOT removed. |
| `R5_ROSTER_STATUS_CUT` | 7 | released. Removed by R5. Under `V1_CANDIDATE` he is NOT removed. |
| `R5_ROSTER_STATUS_RES` | 5 | reserve / injured reserve. Removed by R5. Under `V1_CANDIDATE` he is NOT removed. |
| `POSITION_NOT_MODELLED(LS)` | 3 | the engine governs no estimand for this position; `RECEIVING_POS = (WR, TE, RB)`, `CARRY_POS = (RB,)`. |
| `POSITION_NOT_MODELLED(K)` | 2 | the engine governs no estimand for this position; `RECEIVING_POS = (WR, TE, RB)`, `CARRY_POS = (RB,)`. |
| `POSITION_NOT_MODELLED(P)` | 2 | the engine governs no estimand for this position; `RECEIVING_POS = (WR, TE, RB)`, `CARRY_POS = (RB,)`. |
| `QB_POOL_EXEMPT_FROM_R5(ROSTER_STATUS_RES)` | 1 | **NOT an exclusion — the opposite.** A reserve-list QB is IN the pool because the QB list bypasses `active_pool` entirely (`run_forecast.py:735-741`). |
| `R5_ROSTER_STATUS_EXE` | 1 | exempt list. Removed by R5. Under `V1_CANDIDATE` he is NOT removed. |

**Read the position rows correctly.** 122 players are excluded because the engine
models no quantity for their position. That is not an eligibility judgement and
it is not a defect; it is the scope of the engine. It is listed because the
deliverable asks for every player considered and every reason.

---

## 4. The special categories, by name

### Practice-squad players — 34 (11 at modelled positions)
Roster `status == DEV`. All are excluded under R8. **None is excluded under
`V1_CANDIDATE` or `PRODUCTION_BASELINE`**, where no eligibility filter runs.

| Team | Pos | Player | abbr | Depth | In pool if R5 is off? |
|---|---|---|---|---|---|
| DEN | RB | Adam Prentice | `P07` | NOT_CHARTED | **YES** |
| DEN | RB | Cody Schrader | `P01` | NOT_CHARTED | **YES** |
| DEN | TE | Lucas Krull | `P07` | NOT_CHARTED | **YES** |
| DEN | WR | Dane Key | `P01` | NOT_CHARTED | **YES** |
| DEN | WR | Kolbe Katsis | `P01` | NOT_CHARTED | **YES** |
| DEN | WR | Michael Bandy | `P06` | NOT_CHARTED | **YES** |
| KC | RB | Ben VanSumeren | `P07` | NOT_CHARTED | **YES** |
| KC | RB | Jaydn Ott | `P01` | NOT_CHARTED | **YES** |
| KC | RB | Nate Carter | `P06` | NOT_CHARTED | **YES** |
| KC | WR | Andrew Armstrong | `P01` | NOT_CHARTED | **YES** |
| KC | WR | Omari Evans | `P01` | NOT_CHARTED | **YES** |

Two of them are the coarse **FB→RB** collapse WS21 records as P4: **Adam
Prentice (DEN)** and **Ben VanSumeren (KC)** carry roster `position = RB` with
`depth_chart_position = FB`. Under R5 they are excluded as `DEV` and the
collapse never bites. **Under `V1_CANDIDATE` it does** — both would compete for
the running-back budget on the same simplex. That is the mechanism, not a
request to reclassify two players.

### Reserve-list players — 17 (7 at modelled positions)
Roster `status` in {RES, EXE}.

| Team | Pos | Player | Status | abbr | Depth | R8 pool | Pool if R5 off |
|---|---|---|---|---|---|---|---|
| DEN | TE | Caleb Lohner | RES | `R48` | TE5 | no | **YES** |
| KC | QB | Chris Oladokun | RES | `R01` | NOT_CHARTED | **YES** | **YES** |
| KC | RB | EJ Smith | RES | `R01` | NOT_CHARTED | no | **YES** |
| KC | TE | John Michael Gyllenborg | RES | `R01` | TE5 | no | **YES** |
| KC | TE | Thomas Odukoya | EXE | `E02` | NOT_CHARTED | no | **YES** |
| KC | WR | Jeff Caldwell | RES | `R01` | WR7 | no | **YES** |
| KC | WR | Jimmy Holiday | RES | `R01` | WR8 | no | **YES** |

**Four reserve-list players hold a current depth-chart rank** — Caleb Lohner
(DEN TE5), John Michael Gyllenborg (KC TE5), Jeff Caldwell (KC WR7), Jimmy
Holiday (KC WR8). This is WS05's F13 live on tonight's game: *a depth rank is
not an eligibility signal.* The audit excludes all four on status and reads
their rank as a rank.

### Retired / released players — 23 released, 0 retired
Roster `status == CUT` (7 at modelled positions). **No `RET` row exists for either club**, so
the `kept_unrecognised_status` path that put two retired receivers into sealed
boards elsewhere has no instance here.

| Team | Pos | Player | abbr | Pool if R5 off |
|---|---|---|---|---|
| DEN | WR | Cameron Ross | `W03` | **YES** |
| DEN | WR | Joseph Manjack | `W03` | **YES** |
| KC | TE | Mason Pline | `W03` | **YES** |
| KC | WR | Jacob De Jesus | `W03` | **YES** |
| KC | WR | Jason Brownlee | `W03` | **YES** |
| KC | WR | Jeff Weimer | `W03` | **YES** |
| KC | WR | Xavier Loyd | `W03` | **YES** |

### Emergency / extra quarterbacks — **UNRESOLVED, and unestablishable from anything we hold**

Seven quarterbacks are on the two rosters; three are charted for each club.
Nothing in this tree can say which of them dresses, and nothing models a third
quarterback:

* the emergency-third-QB rule is **not implemented anywhere**. WS05 E6 records
  that `inactives_segmentation.py` preserves the annotation `(emergency third
  QB)` and *refuses to read it as a position*. There is no such annotation for
  this game because there is no inactives document for this game.
* the only source that carries the annotation is the official inactive list,
  and `POOL_AUDIT_NO_OFFICIAL_INACTIVES` — no list has been published for either club.

**What would settle it:** the official inactives bytes for DEN and KC, plus the
league rule text stating when a third quarterback may enter without counting
against the 48 (WS05 E6).

### Newly elevated players — **UNRESOLVED**

* `official_transactions` has **no URL at all**: 177 manifest rows, all
  BLOCKED, zero bytes. Elevations are not observable as events.
* The only candidate signature in bytes we hold is `status == ACT` together
  with a practice-squad `status_description_abbr` (`P01`/`P07`). **No DEN or KC
  row carries it**: all 106 ACT rows are `A01` in every lawful capture,
  including the 2026-09-14T16:16Z one.
* That absence is **not** evidence that no elevation was made. `P07` is
  **undecoded** — WS05 E3 is open, and the audit labels every
  `status_description_abbr` `UNDECODED` rather than guessing. Note that Taylor
  Rapp (DEN, DB) carries `DEV` + `P07`, so `P07` alone is plainly not
  "elevated to the active roster", which is the whole reason a published decode
  table is needed.

**What would settle it:** a verified `official_transactions` endpoint (E1), or
a published decode table for `status_description_abbr` (E3).

### Newly signed players — **UNRESOLVED as transactions; measured as observations**

Same refusal, same reason. What *can* be said is weaker and true: a row was
absent at observation A and present at observation B. Across the four lawful
roster captures:

| From | To | Appeared | Disappeared | Status changed |
|---|---|---|---|---|
| 2026-09-13T15:46:04.716751+00:00 | 2026-09-14T16:16:33.199666+00:00 | — | — | — |
| 2026-09-11T12:19:25.611603+00:00 | 2026-09-13T15:46:04.716751+00:00 | — | — | — |
| 2026-09-10T12:07:21.167358+00:00 | 2026-09-11T12:19:25.611603+00:00 | — | — | — |
| 2026-09-06T20:11:17.241139+00:00 | 2026-09-10T12:07:21.167358+00:00 | DEN Taylor Rapp (DB, DEV), KC Thomas Odukoya (TE, EXE) | DEN Kyrese Rowan (WR, CUT) | DEN Drew Sanders RES→CUT |

**The DEN/KC roster has not moved since 2026-09-10T12:07Z.** The only movement
on record is between the 09-06 and 09-10 observations. A diff **dates the
observation, not the transaction**, and it cannot distinguish a signing from a
vendor correction — which is exactly why it is reported here and not in the
"newly signed" column of the table.

---

## 5. Inversions and mechanism defects — FLAGGED, NOT FIXED

### D-1 (CRITICAL) A reserve-list quarterback is in the model pool, and he is Kansas City's declared incumbent

**Chris Oladokun**, KC, QB, roster `status = RES` (`R01`), **not on the depth
chart**, reaches the QB layer. Three independent mechanisms compose:

1. **P3** — `run_forecast.py:735-736` splits `nonqb = [q for q in players if
   q.get('position') != 'QB']` and hands only the non-QBs to
   `RS.active_pool`. The comment at `:723` states the exemption. So the only
   eligibility filter in the production path does not apply to him.
2. **P6** — `qb_allocation.py:472-475`: a rostered QB with no depth row is not
   dropped, he is **ranked 3**. Oladokun is unranked, so he is rank 3.
3. **P7** — `qb_allocation.previous_primary_detail(2026, 1)` returns
   `{"KC": {"pid": "00-0037324"}}`, measured today. `00-0037324` **is Chris
   Oladokun**. The incumbent bit is keyed on who started the club's week-18
   game last season, not on who is on the roster now.

He therefore enters the room at cell `(3, 1)` — clipped rank 3, incumbent bit
1 — while **Patrick Mahomes** enters at `(1, 0)`. That is the same pair of
cells that produced the Dallas inversion on 2026_01_DAL_NYG, where
`TONIGHT_R8_PREFLIGHT_READY.json` records `('2+', 1)` at `p_primary = 0.6167`
for a practice-squad quarterback against `(1, 0)` at `0.4922` for Dak Prescott,
and a 52.2%/42.1% dropback split. **I did not run tonight's QB layer and I am
not quoting a number for it**; the cells are measured, the consequence on the
DAL board is quoted from that artifact, and whether the same inversion is
realised here is for whoever runs the board to measure.

Denver is the benign configuration: `previous_primary` is `00-0039732` = **Bo
Nix**, ACT and QB1.

**Not repaired. Not hand-fixed.** Removing one player would leave all three
mechanisms in place.

### D-2 (HIGH) One club's unfiled injury report empties the non-QB half of the board for both clubs

`readiness.team_readiness` returns **`INJURY_REPORT_INCOMPLETE`** for DEN: 1
row, `report_status` filled on 0 of 1. KC is **READY**: 11 rows, 2 filled.
`layers.py:117-127` collects both verdicts and defers the whole appearance
layer if **either** is bad. Consequence, measured: 27 non-quarterbacks pass every
eligibility test and **none of them is modelled**, Kansas City's 13 included.

The refusal itself is correct — *a club with no filed designation is not a club
with nobody injured.* What is worth flagging is the **blast radius**: readiness
is resolved per club and then applied per game, so a data gap on one side
deletes the other side's projections too. That is a design question about the
gate's scope, not a bug in the gate, and it is the direct cause of the QB-only
board this game will produce.

The injuries feed has not been recaptured since 2026-09-13T15:45:56Z, ~32.5
hours before kickoff. **This is the single highest-value unblock for tonight.**

### D-3 (MEDIUM) The depth rank the appearance layer consumes is not the vendor's rank

`depth_vintage.captured()` — the selector WS21 scored *correct* — returns a
**team-wide ordinal over skill players**, 1..18 for DEN and 1..19 for KC, not
the vendor's within-position `pos_rank`. Measured on tonight's chart: Evan
Engram (TE1) is ordinal 1, J.K. Dobbins (RB1) is 2, Jaylen Waddle (WR1) is 3,
Bo Nix (QB1) is 4. Players tied at the same `pos_rank` are separated by
**`gsis_id`**, because `pos_slot` is absent from every persisted *reduced*
blob (`pos_slot_available: False`) — RL-10, still live. An identifier is
not a football fact.

New today, and worth someone's attention: the **raw** depth blob
`nfl/vintage/depth_charts.f66f0c2583dba463.raw.csv.gz` **does** carry `pos_slot`
and is now durable. The reduction still drops it. The column exists; the code
that needs it cannot see it.

Both quantities are in the table below — `DEPTH STATUS` is the vendor rank,
`ord` is the consumed ordinal — precisely so nobody has to guess which one a
downstream number was built from.

### D-4 (MEDIUM) The inactives parser's verdict depends on which other clubs were in the same call

Measured on both real inactives documents, for the same bytes:

* `IN.parse(html, ['DEN','KC'])` → `INACTIVES_TEAM_HAS_NO_NAMES`, naming
  **DEN only**;
* `IN.parse(html, ['DEN'])` → `INACTIVES_BLOCK_IMPLAUSIBLY_LARGE`, 231 and 282
  names;
* `IN.parse(html, ['KC'])` → the same, identical counts.

Both are refusals and **nothing leaked** — the implausibility ceiling caught the
document sweep, which is the guard working. What is wrong is that the *reason*
given for refusing the same club on the same bytes changes with the call's
other arguments, and the identical name counts for two different clubs are the
signature of a whole-document sweep rather than a per-club block. Flagged for
whoever owns `inactives.parse`.

### D-5 (LOW, latent) `weekly_rosters` is the one family with no declared columns

`vintage_selector.FAMILIES['weekly_rosters']` declares no `declared_columns`, so
`column_check` returns **`VINTAGE_NO_DECLARED_COLUMNS`** — "this is a gap in the
declaration, not a pass", in its own words — for exactly the family whose
reduction is known to drop the column everything downstream needs. Every other
declared family has a column list. This audit names the columns itself. Not
changed: `vintage_selector` is shared.

### Checked and NOT a defect — withdrawn before it was written up

I expected to find the WS21 **P3d** raw/reduced vintage split live, because the
retention repair began writing full bytes to `nfl/vintage/*.raw.csv.gz` while
`roster_status._raw_rosters()` still globs `nfl_vintage/raw/*.csv`. **It is not
live.** The capture layer writes both copies, so the glob resolves the same
capture, and the pool vintage and the status vintage share content hash
`bdab6ecee12d44a4`. Two selectors over two file populations remains a
latent hazard; today it agrees.

---

## 6. UNRESOLVED rows, and what would settle each

**Every one of the 180 rows is UNRESOLVED on GAME-DAY STATUS.** Not one player
of either club can be shown to be dressing or not dressing tonight, because no
official inactive list has been published for this game. `GAME_ACTIVE` is
therefore never emitted — the audit has the state and refuses to assert it, and
a test asserts that refusal.

| Unresolved cell | Rows | What would settle it |
|---|--:|---|
| GAME-DAY STATUS | 180 (all) | the official inactives bytes for DEN and KC. Historically these have arrived only from `nfl.com/news/inactive-reports-<day>-week-<n>-<season>-nfl-season`, never from the registered `/inactives/` endpoint (92 of 95 captures are the empty placeholder). WS05 E2. |
| INJURY STATUS — designation | 168 rows have no injury row at all; 10 have a row with no `report_status` | a recaptured `injuries` vintage with DEN's designations filed, or delivered authoritative injury-report bytes for DEN. **This is also what unblocks D-2.** |
| newly elevated | 180 — the category cannot be evaluated for anyone | a verified `official_transactions` endpoint (E1), or a decode table for `status_description_abbr` (E3) |
| newly signed | 180 — same | E1 |
| emergency / extra QB | 7 quarterbacks | the official inactives document (E2) **and** the league rule text (E6) |
| `status_description_abbr` | 180 — every code is `UNDECODED` | a published nflverse or league reference (E3). Codes observed on these two clubs: `A01` ×106, `E02` ×2, `P01` ×22, `P03` ×1, `P06` ×3, `P07` ×9, `R01` ×11, `R04` ×2, `R48` ×2, `W03` ×22 |

**Absence was not read as a state anywhere.** A player with no injury row is
`NO_INJURY_ROW`, not healthy. A player not named on a list that was never
published is `UNRESOLVED`, not active.

### Corroboration that agrees — and changes nothing

`espn_injuries_json` is the largest unconsumed eligibility corpus in the tree
(`authority_rank = 9`, `CANDIDATE_FALLBACK`, discharges no target). Bridged to
this roster by `espn_id`, its newest lawful capture
(`espn_injuries_json.0cd99d47b1cc389f.json.gz`, 2026-09-11T00:44Z) resolves 40
DEN/KC players: 33 `Active`, 4 `Injured Reserve`, 2 `Out`, 1 `Questionable`.
**Zero contradictions with the roster status column** — no player ESPN calls
Injured Reserve is roster-ACT, and no player ESPN calls Active is roster-RES.

It is quoted as corroboration and it moved no cell. One incidental note for
whoever pursues E3: ESPN's narrative says Omarr Norman-Lott (KC, `R04`) "was
placed on the active/PUP list". That is a **hint**, from a rank-9 source, and it
is not a decode table.

---

## 7. Every player considered

`ELIG` is roster membership only. `R8` / `V1` are allocation-pool membership
under the two modes. `MODEL` is whether the player reaches a modelled quantity.
`ord` is the team-wide ordinal `depth_vintage.captured()` hands the appearance
layer; `DEPTH` is the vendor's own within-position rank.

### Modelled positions (QB / RB / WR / TE)

| Player | Team | Pos | Roster | abbr | Depth | ord | Injury | Game-day | ELIG | R8 | V1 | MODEL | Exclusion reason |
|---|---|---|---|---|---|--:|---|---|---|---|---|---|---|
| Bo Nix | DEN | QB | ACT | `A01` | QB1 | 4 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | Y | — |
| Jarrett Stidham | DEN | QB | ACT | `A01` | QB2 | 6 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | Y | — |
| Sam Ehlinger | DEN | QB | ACT | `A01` | QB3 | 9 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | Y | — |
| J.K. Dobbins | DEN | RB | ACT | `A01` | RB1 | 2 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| RJ Harvey | DEN | RB | ACT | `A01` | RB2 | 8 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Jonah Coleman | DEN | RB | ACT | `A01` | RB3 | 12 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Tyler Badie | DEN | RB | ACT | `A01` | RB4 | 13 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Adam Prentice | DEN | RB | DEV | `P07` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Cody Schrader | DEN | RB | DEV | `P01` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Jaylen Waddle | DEN | WR | ACT | `A01` | WR1 | 3 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Courtland Sutton | DEN | WR | ACT | `A01` | WR2 | 5 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Marvin Mims Jr. | DEN | WR | ACT | `A01` | WR3 | 11 | NO_DESIGNATION_FILED / Full Participation in Practice | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Pat Bryant | DEN | WR | ACT | `A01` | WR4 | 14 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Troy Franklin | DEN | WR | ACT | `A01` | WR5 | 16 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Lil'Jordan Humphrey | DEN | WR | ACT | `A01` | WR6 | 18 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Cameron Ross | DEN | WR | CUT | `W03` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_CUT |
| Dane Key | DEN | WR | DEV | `P01` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Joseph Manjack | DEN | WR | CUT | `W03` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_CUT |
| Kolbe Katsis | DEN | WR | DEV | `P01` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Michael Bandy | DEN | WR | DEV | `P06` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Evan Engram | DEN | TE | ACT | `A01` | TE1 | 1 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Adam Trautman | DEN | TE | ACT | `A01` | TE2 | 7 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Nate Adkins | DEN | TE | ACT | `A01` | TE3 | 10 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Dallen Bentley | DEN | TE | ACT | `A01` | TE4 | 15 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Caleb Lohner | DEN | TE | RES | `R48` | TE5 | 17 | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_RES |
| Lucas Krull | DEN | TE | DEV | `P07` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Patrick Mahomes | KC | QB | ACT | `A01` | QB1 | 2 | NO_DESIGNATION_FILED / Full Participation in Practice | UNRESOLVED | ROSTER_ACTIVE | Y | Y | Y | — |
| Justin Fields | KC | QB | ACT | `A01` | QB2 | 6 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | Y | — |
| Garrett Nussmeier | KC | QB | ACT | `A01` | QB3 | 12 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | Y | — |
| Chris Oladokun | KC | QB | RES | `R01` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | Y | Y | Y | QB_POOL_EXEMPT_FROM_R5(ROSTER_STATUS_RES) |
| Kenneth Walker III | KC | RB | ACT | `A01` | RB1 | 3 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Emmett Johnson | KC | RB | ACT | `A01` | RB2 | 8 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Brashard Smith | KC | RB | ACT | `A01` | RB3 | 11 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Ben VanSumeren | KC | RB | DEV | `P07` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| EJ Smith | KC | RB | RES | `R01` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_RES |
| Jaydn Ott | KC | RB | DEV | `P01` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Nate Carter | KC | RB | DEV | `P06` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Rashee Rice | KC | WR | ACT | `A01` | WR1 | 4 | NO_DESIGNATION_FILED / Full Participation in Practice | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Xavier Worthy | KC | WR | ACT | `A01` | WR2 | 7 | NO_DESIGNATION_FILED / Full Participation in Practice | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Tyquan Thornton | KC | WR | ACT | `A01` | WR3 | 9 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Cyrus Allen | KC | WR | ACT | `A01` | WR4 | 14 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Jalen Royals | KC | WR | ACT | `A01` | WR5 | 15 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Nikko Remigio | KC | WR | ACT | `A01` | WR6 | 17 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Jeff Caldwell | KC | WR | RES | `R01` | WR7 | 18 | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_RES |
| Jimmy Holiday | KC | WR | RES | `R01` | WR8 | 19 | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_RES |
| Andrew Armstrong | KC | WR | DEV | `P01` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Jacob De Jesus | KC | WR | CUT | `W03` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_CUT |
| Jason Brownlee | KC | WR | CUT | `W03` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_CUT |
| Jeff Weimer | KC | WR | CUT | `W03` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_CUT |
| Omari Evans | KC | WR | DEV | `P01` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_DEV |
| Xavier Loyd | KC | WR | CUT | `W03` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_CUT |
| Travis Kelce | KC | TE | ACT | `A01` | TE1 | 1 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Noah Gray | KC | TE | ACT | `A01` | TE2 | 5 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Jared Wiley | KC | TE | ACT | `A01` | TE3 | 10 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| Jake Briningstool | KC | TE | ACT | `A01` | TE4 | 13 | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE | Y | Y | · | APPEARANCE_DEFERRED(DEN:INJURY_REPORT_INCOMPLETE) |
| John Michael Gyllenborg | KC | TE | RES | `R01` | TE5 | 16 | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_RES |
| Mason Pline | KC | TE | CUT | `W03` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_CUT |
| Thomas Odukoya | KC | TE | EXE | `E02` | NOT_CHARTED | — | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED | · | Y | · | R5_ROSTER_STATUS_EXE |

### Positions the engine models no quantity for

122 players. Listed because the deliverable is *every* player considered.
None of them can reach any layer regardless of eligibility, so the eligibility
columns are reported and the pool columns are uniformly empty.

| Player | Team | Pos | Roster | abbr | Injury | Game-day | ELIG |
|---|---|---|---|---|---|---|---|
| Brandon Jones | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Brent Austin | DEN | DB | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Devon Key | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| JL Skinner | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Ja'Quan McMillian | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Jahdae Barron | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Kris Abrams-Draine | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Miles Scott | DEN | DB | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Parker Robertson | DEN | DB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Pat Surtain II | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Ricardo Hallman | DEN | DB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Riley Moss | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Sean Fresch | DEN | DB | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Talanoa Hufanga | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Taylor Rapp | DEN | DB | DEV | `P07` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Tycen Anderson | DEN | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| D.J. Jones | DEN | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| David Agoha | DEN | DL | DEV | `P03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Eyioma Uwazurike | DEN | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Israel Antwine | DEN | DL | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Jordan Jackson | DEN | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Kristian Williams | DEN | DL | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Malcolm Roach | DEN | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Matt Henningsen | DEN | DL | RES | `R01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Sai'vion Jones | DEN | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Tyler Onyedim | DEN | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Zach Allen | DEN | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Wil Lutz | DEN | K | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Alex Singleton | DEN | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Dasan McCullough | DEN | LB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Dondrea Tillman | DEN | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Drew Sanders | DEN | LB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Johnny Walker Jr. | DEN | LB | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Jonah Elliss | DEN | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Jonathon Cooper | DEN | LB | EXE | `E02` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Jordan Turner | DEN | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Justin Strnad | DEN | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Karene Reid | DEN | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Levelle Bailey | DEN | LB | RES | `R01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Nik Bonitto | DEN | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Que Robinson | DEN | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Red Murdock | DEN | LB | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Ron Stone Jr. | DEN | LB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Taurean York | DEN | LB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Luke Basso | DEN | LS | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Mitchell Fraboni | DEN | LS | DEV | `P07` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Alex Forsyth | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Alex Palczewski | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Ben Powers | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Calvin Throckmorton | DEN | OL | DEV | `P07` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Frank Crum | DEN | OL | RES | `R48` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Garett Bolles | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Gavin Ortega | DEN | OL | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Kage Casey | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Luke Wattenberg | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Matt Peart | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Michael Deiter | DEN | OL | RES | `R01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Mike McGlinchey | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Nick Gargiulo | DEN | OL | RES | `R04` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Quinn Meinerz | DEN | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Tyler Miller | DEN | OL | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Jeremy Crawshaw | DEN | P | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Alohi Gilman | KC | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Chamarri Conner | KC | DB | ACT | `A01` | Out / Did Not Participate In Practice | UNRESOLVED | ROSTER_ACTIVE |
| Christian Roland-Wallace | KC | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| D'Arco Perkins-McAllister | KC | DB | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| DeShon Singleton | KC | DB | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Jaden Hicks | KC | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Jadon Canady | KC | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Kader Kohou | KC | DB | DEV | `P07` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Kristian Fulton | KC | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| L'Jarius Sneed | KC | DB | ACT | `A01` | NO_DESIGNATION_FILED / Limited Participation in Practice | UNRESOLVED | ROSTER_ACTIVE |
| Mansoor Delane | KC | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Nohl Williams | KC | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Tanner McCalister | KC | DB | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Xavier Nwankpa | KC | DB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Zelmar Vedder | KC | DB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Amari McNeill | KC | DL | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Ashton Gillotte | KC | DL | ACT | `A01` | NO_DESIGNATION_FILED / Full Participation in Practice | UNRESOLVED | ROSTER_ACTIVE |
| Bryson Eason | KC | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Chris Jones | KC | DL | ACT | `A01` | NO_DESIGNATION_FILED / Did Not Participate In Practice | UNRESOLVED | ROSTER_ACTIVE |
| Cole Brevard | KC | DL | CUT | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Damon Payne | KC | DL | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Emmanuel Ogbah | KC | DL | DEV | `P07` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Ethan Hurkett | KC | DL | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Felix Anudike-Uzomah | KC | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| George Karlaftis | KC | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Khyiris Tonga | KC | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Marcus Harris | KC | DL | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Niles King | KC | DL | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Omarr Norman-Lott | KC | DL | RES | `R04` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Peter Woods | KC | DL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| R Mason Thomas | KC | DL | ACT | `A01` | NO_DESIGNATION_FILED / Full Participation in Practice | UNRESOLVED | ROSTER_ACTIVE |
| Tyreke Smith | KC | DL | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Harrison Butker | KC | K | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Cam Jones | KC | LB | DEV | `P07` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Cole Christiansen | KC | LB | DEV | `P06` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Cooper McDonald | KC | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Drue Tranquill | KC | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Ethan Downs | KC | LB | RES | `R01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Jack Cochrane | KC | LB | ACT | `A01` | NO_DESIGNATION_FILED / Full Participation in Practice | UNRESOLVED | ROSTER_ACTIVE |
| Jack Pyburn | KC | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Jeffrey Bassa | KC | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Kam Arnold | KC | LB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Nick Bolton | KC | LB | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Wesley Bissainthe | KC | LB | CUT | `W03` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| James Winchester | KC | LS | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| C.J. Hanson | KC | OL | RES | `R01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Creed Humphrey | KC | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Diego Pounds | KC | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Ethan Driskell | KC | OL | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Hunter Nourzad | KC | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Jaylon Moore | KC | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Josh Simmons | KC | OL | ACT | `A01` | Out / Did Not Participate In Practice | UNRESOLVED | ROSTER_ACTIVE |
| Joshua Ezeudu | KC | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Kahlil Benson | KC | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Kingsley Suamataia | KC | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Matt Waletzko | KC | OL | RES | `R01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Mike Caliendo | KC | OL | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |
| Pete Nygra | KC | OL | DEV | `P01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_EXCLUDED |
| Trey Smith | KC | OL | ACT | `A01` | NO_DESIGNATION_FILED / Full Participation in Practice | UNRESOLVED | ROSTER_ACTIVE |
| Matt Araiza | KC | P | ACT | `A01` | NO_INJURY_ROW | UNRESOLVED | ROSTER_ACTIVE |

---

## 8. What this audit did NOT establish

* **Whether anybody dresses tonight.** No official inactive list exists for this
  game. Nothing here is a game-day availability statement.
* **Whether the KC quarterback inversion is realised in numbers.** The three
  mechanisms and both cells are measured. I did not run the QB layer, and the
  0.6167 / 0.4922 figures quoted are from the DAL_NYG artifact, not from this
  game.
* **Whether any elevation was made for either club.** The signature is absent
  and the signature is undecoded; those are different statements and neither is
  "no elevations were made".
* **Whether R5 being off in `V1_CANDIDATE` costs anything here.** The
  24-player difference between the modes is measured. Whether it moves a
  forecast is not, and this game cannot answer it: the non-QB layers do not run.
* **Anything about prices.** No sportsbook data was read. No wager is
  recommended.

---

*Generated by `nfl/production/pool_audit.py` (pool-audit-1) under
`vintage_selector` (vintage-selector-1). Machine-readable companion:
`DEN_KC_PLAYER_POOL_AUDIT.json`.*
