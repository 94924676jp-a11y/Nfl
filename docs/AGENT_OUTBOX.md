# Agent outbox — requests that need bytes or work outside this checkout

Written by the repository-side agent. Each item is ASSIGNED, not blocked: it is
work this agent cannot do here, with the exact identifiers needed.

---

## 2026-09-10 — OUT-001: retain `status` in the reduced weekly-roster vintage

**Why.** `p4c_params.class_point_forecast` returns a share conditional on a
player appearing; the allocator consumes it as an unconditional weight over the
roster it is handed. The historical fitting panel holds 14.6 WR/TE/RB per
team-game summing to 1.24; the prospective full roster holds 22.5 summing to
2.14, which halves every starter share. Of 45 SF/LA WR/TE/RB roster rows, 29
are ACT, 10 DEV, 3 RES and 3 CUT.

**What is missing.** The raw nflverse `weekly_rosters_2026.csv` carries
`status` (ACT/DEV/RES/CUT/EXE) and `depth_chart_position`. The vintage
reduction keeps only `season, week, team, gsis_id, position`, so both are
captured and then discarded. Only one raw roster blob is retained locally
(`weekly_rosters.5ec59c5228198f57.csv`, observed 2026-09-06T18:50:51Z).

**Request.** Add `status` and `depth_chart_position` to the reduced roster
columns from the next capture onward. This is a capture-layer change and was
deliberately not made from here.

**Consequence if not done.** The R5 repair can only run against a capture whose
raw blob happens to be retained, and refuses by name
(`ROSTER_STATUS_UNAVAILABLE`) otherwise.

---

## 2026-09-10 — OUT-002: historical weekly-roster vintages carrying `status`

**Why.** R5 removes players who were never eligible to take a snap. The
historical corpus contains only players who APPEARED, so the contamination R5
removes does not exist in it and the counterfactual cannot be constructed. This
is why the audit reports distributional evidence rather than a per-game held-out
CRPS/PIT comparison, and says so.

**Request.** Weekly roster files for 2020–2025 with the `status` column, so a
historical team-game's full roster can be reconstructed and V1 versus R5 scored
per game against realised outcomes.

**Exact need.** `weekly_rosters_{season}.csv` for seasons 2020, 2021, 2022,
2023, 2024, 2025, from the nflverse `weekly_rosters` release, with `status`
retained.

---

## 2026-09-10 — OUT-003 (informational): egress works from this container

A request to the nflverse release endpoint returned HTTP 200 and 65,119 bytes
from this environment on 2026-09-10. The project has been treating egress as
universally 403 and `pbp_sources()` still returns BLOCKED. No source or
connector has been changed on the strength of this; it is recorded because it
changes what is genuinely blocked for both agents rather than assigned to one.

---

## 2026-09-10 — OUT-004: OUT-002 is PARTLY DISCHARGED from here, and by a different route

**What changed.** OUT-002 asked for historical weekly rosters carrying `status`
so a team-game's full roster could be reconstructed. The underlying need — a
denominator that contains players who did NOT appear — turns out to be
satisfiable from the depth chart instead, which lists a team's players whether
or not they play and is already committed and hash-verified for 2020–2024
(`nfl/research/inputs/dc_20{20..24}.csv.gz`, 152,246 entries).

Unioning the panel with the depth listing adds **6,181 player-team-weeks the
panel does not hold at all**, including listed rank-1 players who missed the
game. That is the censored mass OUT-002 was asking for.

**OUT-002 is NOT withdrawn.** The depth chart is a listing, not an eligibility
status: it cannot distinguish inactive from waived from practice-squad, and a
player off the chart with no panel row still produces no row, so the tail is
reduced rather than eliminated. `status` remains the better instrument and the
request stands at lower priority.

---

## 2026-09-10 — OUT-005: the 2025 depth-chart leaf was fetched from here

**What was done.** `depth_charts_2025.csv` (52,917,870 bytes, sha256
`f5a4aa3f…`) was fetched from the nflverse release endpoint on 2026-09-10 and
column-reduced to `nfl/research/inputs/dc25_daily.csv.gz` (146,246 rows, five
columns, every daily snapshot retained). Recorded in `INPUT_MANIFEST.json` with
the upstream URL, the full-file hash and the reduction rule.

**Why it matters to you.** This closes the 2025 hole in the depth feature —
`stage_a.depth()` defaults to `range(2020, 2025)` and returned nothing for
13,813 2025 panel rows. It also establishes that the 2025+ ESPN daily schema is
genuinely point-in-time: over the 544 team-weeks of the 2025 regular season,
every one resolves to a snapshot 6.3 to 18.7 hours before kickoff, median 10.8.

**What is still yours.** The two feeds do not overlap in time — nflverse weekly
ends after 2024, ESPN daily begins 2025-08 — so **no measurement in this
repository can establish that a 2024 "WR2" and a 2026 "WR2" mean the same
thing.** Measured appearance rate at rank 1 is 0.707–0.812 under the weekly feed
and 0.895–0.923 under the daily one, which is consistent with either a genuine
vendor difference or a genuinely fresher chart. If any archived ESPN daily depth
snapshot exists for a 2024-or-earlier week, it would settle this; nothing in
this checkout can.

---

## 2026-09-10 — OUT-006 (informational): `GAP-DEPTH-CHART-PIT` is overstated

`nfl/INFORMATION_GAP_REGISTRY.json` records `GAP-DEPTH-CHART-PIT` with
`proxy_adequacy: "good prospectively; ZERO historical as-of depth"` and
`action: PROSPECTIVE_ONLY`, on the basis that the project's vintage record
begins 2026-09-06. That is true of OUR capture and false of the source: the
upstream 2025 release carries the vendor's own daily `dt` series back to
2025-08-03, and the 2020–2024 weekly leaves are already committed. The registry
entry has been corrected rather than left standing.

---

## 2026-09-10 21:15Z — OUT-007: **TIME-CRITICAL.** SF@LA official inactives, T-90

**Deadline.** Kickoff `2026-09-11T00:35:00Z`. The lists publish at about
**`2026-09-10T23:05:00Z`**. Anything delivered after kickoff is worthless for
tonight, and the page is not recoverable later.

**Why it is yours and not mine.** Measured from this container at 21:08Z, this
capture and a direct probe:

| endpoint | result |
|---|---|
| `https://www.nfl.com/inactives/` | HTTP **000**, connection refused by the local proxy |
| `https://www.nfl.com/injuries/` | HTTP **000** |
| `https://site.api.espn.com/apis/site/v2/.../teams` | HTTP **000** |
| `https://github.com/nflverse/nflverse-data/...` | HTTP **200** |

Egress is host-restricted, not absent. `capture_vintage.py` records
`official_inactives`, `official_injury_report` and `espn_injuries_json` as
`BLOCKED[NO_EGRESS]` on every capture. Those are the only three sources in the
registry with `authority_rank` 1 and 9; **everything the model consumes tonight
is `authority_rank` 99 ARCHIVE.**

**Exactly what is needed.**

1. `https://www.nfl.com/inactives/` — the **raw bytes**, saved before any
   parsing, for the 2026 week 1 SF@LA game. Both clubs must be present.
2. The **publication clock** if the page carries one, and your **retrieval
   clock** in UTC, to the second. Both, kept apart.
3. The same for `https://www.nfl.com/injuries/` (the club report) if it is
   cheap — second priority, it does not block.

**Format.** Anything that preserves the bytes: the HTML file itself plus a
sidecar JSON carrying `retrieved_at`, `source_url`, `http_status`, and the
sha256 of the bytes. Do not send a summary, a table you typed out, or a
paraphrase — the whole point is the artifact.

**What I will do with it.** Hash it, store it immutably under
`nfl/vintage/official_inactives.<sha16>.html.gz`, append a manifest row, verify
both teams are represented, map every player to a `gsis_id` deterministically,
emit explicit ACTIVE / INACTIVE sets, propagate them into the appearance layer,
re-run all five candidates at one cutoff, and seal a new artifact. The
propagation machinery and its seeded tests are already built and passing
(`nfl/tests/test_inactives_propagation.py`); what is missing is only the bytes.

**If it does not arrive.** I will not label any run `POST_INACTIVES_COMPLETE`.
The pregame board stands as the pre-inactives shadow board, labelled as such,
and the gap is reported rather than filled from a reporter or a price.

**Do not send me a sportsbook line or a reporter's expectation as a substitute
for the official list.** Those are comparators. They are not the list.

---

## 2026-09-10 22:35Z — OUT-007 UPDATE: the block is at the gateway, on three channels

Re-measured at 22:22Z and 22:34Z. The refusal is now evidenced on **three
independent channels** rather than inferred from one:

| channel | result |
|---|---|
| `curl` direct | `www.nfl.com` HTTP **000**; `site.api.espn.com` HTTP **000** |
| agent `WebFetch` tool | `EGRESS_BLOCKED: Access to www.nfl.com is blocked by the network egress proxy` |
| proxy's own status endpoint | `connect_rejected` — *"gateway answered 403 to CONNECT (policy denial or upstream failure)"*, logged for `www.nfl.com:443` and `site.api.espn.com:443` at 22:22:23Z, 22:22:24Z, 22:25:35Z, 22:25:36Z |

The stored response header for the last attempt is `HTTP/1.1 403 Forbidden` from
the proxy, not from nfl.com. **The origin was never reached.** So this is a
host allowlist decision in the execution environment, not a site error, not
rate limiting, and not something a retry, a different user-agent or a
per-tool setting will move.

Controls run in the same breath, so this is a boundary and not an outage:
`github.com` → 400 (reached), `raw.githubusercontent.com` → 301 (reached), and
the 22:25:31Z capture took **four** nflverse sources PASS. Archive hosts are
allowed; both game-day authoritative hosts are denied.

**Nothing about the request changes.** Still the raw bytes of
`https://www.nfl.com/inactives/` for 2026 week 1 SF@LA, both clubs, with your
retrieval clock to the second, kept apart from any publication clock on the page.

**What changed on my side: it is now one command.** `nfl/tools/ingest_inactives.py`
runs the whole chain — store bytes before parsing, assert both clubs present,
resolve identities to `gsis_id`, refuse on partial resolution, re-fetch the
perishables and diff the *consumed slice*, propagate to all five candidates at
one common `written_at`, seal beside the untouched pre-inactives boards:

    python3.12 nfl/tools/ingest_inactives.py --game-id 2026_01_SF_LA \
        --bytes <file> --source-url <url> --retrieved-at <iso8601Z> \
        --out nfl/research/live/2026_01_SF_LA

Rehearsed twice end-to-end against a synthetic list in an isolated vintage root
(`--vintage-root`, `--dry-run`); the live manifest was verified unchanged after
both. The first rehearsal **refused at step 4** because the reduced vintage
carries no name column and 0 of 6 names resolved — that refusal was the test
working, and the name crosswalk it forced is now wired to the raw capture.
87 seeded checks pass across `test_inactives_propagation.py` and
`test_inactives_drill.py`.

So the turnaround once bytes land is minutes, not hours. **Send the file.**

**Still do not send** a sportsbook line, a reporter's expectation, a typed-out
table, or a retrospective `weekly_rosters.status == INA`. The last one is
especially tempting and especially wrong: that vendor field is re-partitioned
*after* the game, so using it pregame is reading tomorrow's paper.

---

## 2026-09-10 22:45Z — OUT-007 CORRECTION: check the bytes carry a list before you send them

I found 83 real captures of `https://www.nfl.com/inactives/` already in this
repository under `nfl/vintage/official_inactives.*.html.gz`, taken 2026-09-07
00:25Z through 2026-09-08 17:28Z, back when egress to nfl.com still worked.
They are genuine 72 KB nfl.com pages, not error bodies. **I had not looked at
them.** They change the request.

**What they show.** Every one is the page's EMPTY STATE. Strip the tags and the
main content reads, in full:

> NFL Inactive Reports — Please check back soon for NFL Inactive Reports for
> this Season

No table, no player, no club block. Two useful things follow. First, the page
**is server-rendered** — the empty-state sentence is in the served HTML, so
when the lists publish they will very probably be in the served HTML too, and
plain bytes should be enough. Second, and this is the part that would have
cost us tonight: **a successful fetch of that URL is not the same as a fetch
that contains a list.**

**What it did to my parser, and why I am telling you rather than quietly
fixing it.** I fed one of those real captures to the parser that was going to
consume tonight's bytes. With team tokens `SF`/`LA` it refused. With `49ers`/
`Rams` — the spelling a rendered page is likelier to use — it returned
**PASS with 311 "names"**:

    'NFL Week', 'Lumen Field', 'Americano NFL', 'The Seattle Seahawks',
    'New England Patriots', 'San Francisco', 'The New York Giants', ...

all 311 assigned to one club and **zero to the other**, harvested out of the
navigation and the news tray. The page also carries promo headlines reading
*"Rams HC Sean McVay expects WR Puka Nacua … to play in Week 1 vs. 49ers"* and
*"TE George Kittle trending in right direction"* — so the failure mode was not
abstract. It was a parser one team-token spelling away from **manufacturing an
official inactive list out of reporter headlines**, which is the precise thing
the owner's ruling forbids. Nothing but luck stood in the way.

Three independent guards now sit in `parse()`, each verified to fire on its own
with the earlier ones deliberately defeated: the page's own empty-state text;
a club that yields no names; and a size ceiling of 12, since a club dresses 48
of 53 and a real list is 5 to 8 names. The real capture is now a permanent
fixture in `test_inactives_drill.py` — the only adversarial input in that file
the site actually served rather than one I wrote. 78 checks, 0 failing.

One of those guards was itself wrong on its first pass, and the drill caught
it: rejecting any candidate containing a club word also rejects **Justin
Houston, A.J. Green, Dwayne Washington** and the drill's own synthetic "Rams
Runner". Club matching is now whole-phrase only.

**So, concretely, before you send anything:**

1. Grep the bytes for `check back soon`. If it is there, **the page has no
   list** — do not send it, wait and re-fetch. Sending it costs us a cycle we
   do not have at T-90.
2. Confirm the bytes contain **both** clubs with player names under each. A
   page naming only one club is not tonight's answer.
3. Send it the moment both are there, with your retrieval clock to the second.
   Do not tidy, extract, or summarise — the guards need the original document.

If the lists turn out to be injected client-side after all and the served HTML
stays empty, say so and send the **rendered DOM** or the JSON the page fetches,
labelled as such so it is stored for what it is. What I cannot use is a typed
table, and what I will not accept is a headline.

---

## 2026-09-10 22:50Z — OUT-007 ADDENDUM: a parser refusal is not a lost window

Closing a gap I left open an hour ago. I hardened the parser to refuse
anything it cannot read, which is right, but it means the reverse risk is now
the live one: **the parser has never seen a populated inactives page**, every
capture in this repository is the empty state, so it may well refuse bytes
that plainly do carry both clubs' lists. I tried building a segmenter that
would handle a populated page and stopped, because the only populated examples
available were ones I wrote myself, and a segmenter fitted to my own mock-up
is fitted to my assumptions rather than to the league's HTML. I would rather
say that than ship a guess with a confident name on it.

So there is a second path, and it is now tested (`--names-json`):

    python3.12 nfl/tools/ingest_inactives.py --game-id 2026_01_SF_LA \
        --bytes <file> --source-url <url> --retrieved-at <iso8601Z> \
        --names-json <file> --out nfl/research/live/2026_01_SF_LA

The rule that makes it safe: **every supplied name must occur verbatim in the
stored official bytes**, checked in code against the same document that was
hashed at step 1. A name that is not in the league's own page is refused and
nothing from that call is accepted, not even the names that did match. So what
the operator supplies is the *segmentation* — which name belongs to which club
— and never the information. The artifact records
`segmentation: operator_supplied_verified_against_bytes` alongside the machine
parse's refusal code, so a later reader can tell an assisted reading from a
machine one and re-check every name against the stored hash.

That check is necessary and not sufficient, and I want the limitation on the
record rather than buried: the captured page's news promos contain "George
Kittle" and "Puka Nacua", so a substring test alone would accept those from
*any* nfl.com page. It is the pairing that carries the weight — bytes that are
a real fetch of the real inactives page, **plus** every name traceable into
them. Neither half stands alone.

**What this means for you: send the bytes even if you are unsure.** If the
parser reads them, we are done in minutes. If it refuses, I can still complete
the chain from the same bytes, with the refusal recorded, provided you also
tell me which names sat under which club heading. What I still cannot use is a
list without the bytes behind it.

---

## 2026-09-11 03:40Z — OUT-008: SF@LA actuals, for the postgame scoring row

The owner has asked for a full postgame postmortem of SF@LA: distributional
scoring (PIT, interval coverage, CRPS), a team/QB/player breakdown, a
V1→R8 architecture comparison on the realised game, a market comparison and a
top-10 plays grade. **None of it can be produced here, because no actuals
exist in this checkout and I cannot fetch any.** Measured, not assumed:

| what I need | what is here |
|---|---|
| play-by-play for 2026_01_SF_LA | `pbp_participation` is `DEFERRED[SOURCE_NOT_YET_PUBLISHED]` in `nfl/availability_manifest.jsonl` |
| snap counts | `snap_counts_2026.3e40ec0361391e8c.csv.gz` holds 93 rows, **0 for SF or LA**, first retrieved 2026-09-10T18:31:04Z — before kickoff |
| a box score of any kind | no `pbp`/`snap`/`boxscore`/`actual` blob on `origin/main` at `568d012` |
| fetching it myself | HTTP 000, gateway CONNECT denial |

`nfl/research/shadow/actuals.py` is already written and takes a play-by-play
file: `load(pbp_gz, game_id)`, then `team_actuals`, `qb_actuals`,
`receiving_rushing_actuals`, `qb_timeline`. It raises `OUTCOME_EMPTY` on a
file with no rows for the game rather than returning an empty result, so the
scoring path is ready the moment the bytes land.

**What I need, in priority order.**

1. **nflverse play-by-play for 2026 week 1**, once published, filtered to or
   containing `game_id` 2026_01_SF_LA. This is the one that unlocks almost
   everything: team plays, dropbacks, carries, pass/run split, sacks, QB
   attempts/completions/yards/INTs, player carries, targets, receptions,
   receiving yards and touchdowns.
2. **snap counts for 2026 week 1** including SF and LA. Needed for the
   appearance-layer check and for `team_off_snaps`, which `actuals.py` notes
   is NOT derivable from play-by-play.
3. **The final score and team totals**, if they are cheap and arrive sooner
   than 1 and 2. They let me do the team-environment layer early.

Raw bytes plus your retrieval clock, as always. Do not type out a stat line.

**What I am NOT asking for and will not accept as a substitute:** a
journalist's game recap, a fantasy-points summary, a betting-results page, or
any human-written table of who did what. Those are the same category error as
a reporter's inactive list, and the whole point of the scoring row is that it
is re-derivable from the same bytes by someone else.

**What is already done and does not wait on you.** The information-set
integrity layer is verified (delivery and seal both pregame, 11 of 11
identities resolved, 0 sources retrieved after kickoff, all 7 consumed source
blobs re-hash to their recorded digests). The QB-inactive accounting
counterfactual is complete, because it is a forecast-versus-forecast
comparison that needs no outcome at all. The prospective scoring row is open
at `nfl/research/live/2026_01_SF_LA/PROSPECTIVE_SCORING_ROW.json` with
`status: AWAITING_ACTUALS`; actuals attach to it and never modify a sealed
board.

---

# Q9 prospective shadow deployment — the one thing I need from outside

Written 2026-09-12. The frozen Q9 target-hurdle candidate is now integrated
into the prospective shadow-forecast path: registered in
`nfl/prospective/registries.py`, identity-gated against the pre-season freeze,
and provable end to end — the dry-run proof at
`nfl/prospective/q9shadow/Q9_PROSPECTIVE_DRYRUN_PROOF.json` passes 10 of 10
checks, including determinism and inability to read an outcome.

**It has sealed zero live forecasts, and three named things stand in the way.
Exactly one of them is yours.**

| blocker | whose | state |
|---|---|---|
| `INJURY_REPORT_INCOMPLETE` | **yours — needs bytes** | the 2026 injury captures carry rows whose `report_status` is unfilled on every row for the team. `nfl/production/nonqb/inputs.py` refuses that by name, so the appearance layer never runs and neither arm gets an availability draw. Measured on 2026-09-12: 12 of the 13 week-1 games still ahead of the clock carry `NOT_APPLICABLE[INJURY_REPORT_INCOMPLETE]` at the appearance stage; the thirteenth (`2026_01_NYJ_TEN`) carries `NOT_APPLICABLE[NONQB_PLAYER_FRAME_INCOMPLETE]` |
| `LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED` | mine | `nfl/research/q6/frame.py` refuses 2026 rows by design (`Q9_LIVE_SEASON_IN_FRAME`) and production reports `feature_build: STAGE_DECLARED_UNIMPLEMENTED`. This is test-first work inside the repository and I am not marking it blocked |
| `G0A_11_OF_12` | governance | protocol §1: no forecast written before G0A is discharged counts toward promotion |

**What I need.** The **official NFL injury report for 2026 week 1 with the
game-status designations filled in** — the Friday/Saturday practice report
carrying `Out` / `Doubtful` / `Questionable` per player, not the Wednesday
participation-only rows. Raw bytes plus your retrieval clock. It feeds
`inj_status`, `inj_practice` and `inj_available`, which are 5 of the 25
declared stage-1 features, and it unblocks the upstream appearance layer that
both arms consume.

I also need, less urgently, **snap counts for 2026 week 1** — same reason as
the earlier request on this page.

**What I am not asking for.** A reporter's list of who is expected to play, a
fantasy site's status column, or anything derived from `weekly_rosters.status`.
`weekly_rosters` is already in the bundle and is marked RESTRICTED: `status ==
INA` is game-day information, so it is structurally kept out of stage 1 by a
ten-key projection derived from the featuriser's own source. Substituting a
transcription for the official designation would put that back.

**What does not wait on you.** The sealing path, the ledger schema, the
four-unit accounting, the §4 floor evaluation, the randomized-PIT emission and
the dry-run proof are all complete and green. The pregame feature builder is
mine and is next. When your bytes land, the live path runs with no code change
on my side: `python3.12 -m nfl.prospective.q9shadow.seal --season 2026`.

---

## 2026-09-13T23:30Z — DAL_NYG official inactives. ASSIGNED, not blocked.

Kickoff `2026-09-14T00:20:00Z`. RotoWire was showing both clubs' lists at about
19:17 ET, so the information EXISTS publicly. I cannot reach it.

**Proven, not assumed.** The egress gateway answers **403 to CONNECT** for the
authoritative hosts. Timestamped relay failures recorded by the proxy:

```
2026-09-13T23:12:11.643Z  connect_rejected  www.nfl.com:443
2026-09-13T23:12:11.884Z  connect_rejected  www.nfl.com:443
2026-09-13T23:12:12.134Z  connect_rejected  site.api.espn.com:443
2026-09-13T23:18:41.777Z  connect_rejected  www.nfl.com:443
```

`nfl/tools/capture_vintage.py` independently reports `official_inactives:
NO_EGRESS`, `official_injury_report: NO_EGRESS`, `espn_injuries_json:
NO_EGRESS`. GitHub is reachable — I pulled nflverse play-by-play and weekly
rosters today without trouble — so this is a host policy denial, not a network
outage.

**What I need, exactly.**

* The official NFL or club game-day INACTIVE declaration for **DAL** and for
  **NYG**, 2026 week 1.
* The original document bytes, not a transcription.
* The official URL each came from.
* Your retrieval timestamp in UTC.
* The publication timestamp if the source states one explicitly. If it does
  not, say so rather than supplying your retrieval clock in its place.
* A sha256 of the raw bytes.
* Both clubs in the same delivery. One club alone cannot clear
  `POST_INACTIVES_COMPLETE`.
* Exact names and statuses as printed. No normalisation, no expansion of
  abbreviations, no reordering.

The existing delivery path handles it with no code change on my side:

```
python3.12 nfl/tools/ingest_inactives.py --game-id 2026_01_DAL_NYG \
  --bytes <file> --source-url <official url> --retrieved-at <UTC> \
  --published-at <UTC or omit> --delivery --delivery-source-url <url> \
  --delivered-by "<who>" --names-json <names> --positions-json <positions> \
  --out nfl/research/live/2026_01_DAL_NYG
```

**What I will not substitute for it.**

* **RotoWire.** The owner's instruction is explicit that it is discovery and
  corroboration only, never governing evidence. I have recorded it as a
  quarantined discovery artifact and it governs nothing.
* **`weekly_rosters.status`.** nflverse carries ACT/DEV/RES/RET/CUT for week 1,
  and I checked it today: 109 ACT across DAL and NYG. That is ROSTER status,
  not game-day inactive status. `nfl/capture/delivered_injuries.py` lists
  `status` in `ROSTER_FORBIDDEN_COLUMNS` for exactly this reason. Reading ACT
  as "active tonight" would be the collapse this project has already banned in
  code.
* **Anything derived from omission.** A player not named on a list is not
  thereby active.

**What does not wait on you.** The PRE_INACTIVES projection is sealed and
stands: run_id `3dddf9f62c9260b0`, written_at `2026-09-13T23:12:33Z`, 8,000
draws, 117 projection rows, 36 players. It was built from evidence legitimately
available before kickoff and needs nothing from this request. Official
inactives REFINE that forecast; they did not have to create it. When your bytes
land the chain is about nine minutes end to end.

---

## 2026-09-14 — injury-report publication clock (BLOCKS 3 of 14 games)

**Status: EVIDENCE CEILING.** Written up in full at
`nfl/research/slate_audit/EVIDENCE_CEILING_injury_report_publication.md`.

**What I need, and why it is yours.** The injury feed we capture carries no
publication date, no report-type field and no filing timestamp. Its columns
are `season, season_type, game_type, team, week, gsis_id, position,
full_name, first_name, last_name, report_primary_injury,
report_secondary_injury, report_status, practice_primary_injury,
practice_secondary_injury, practice_status` and that is the whole schema. The
capture's `retrieved_at` records when WE fetched it, which is a different
quantity — a Friday fetch of a Wednesday report carries a Friday clock.

Without it, a club with four rows, practice statuses filled and no game
designation is byte-identical in two states that have opposite meanings:

* the **final** report is out and this club has nobody designated — the most
  benign injury state there is; or
* only the **mid-week practice** report is out and no designation has been
  filed yet.

Measured: in the game-day capture `injuries.66e960ec81fccc6e.csv.gz`, 61 of
182 rows carry a designation (33.5%); in the mid-week capture
`injuries.cd7338473dd852d0.csv.gz`, 8 of 167 (4.8%). The slate separates
cleanly. **A single team does not.** Houston, Minnesota and Miami each carried
zero designations on game day and lost BUF@HOU, GB@MIN and MIA@LV their entire
non-QB player board.

**Exactly what would lift it — any one is enough:**

1. An injury feed or parser that **preserves the report's own date and type**
   ("Wednesday practice report" / "Friday final injury report"). This resolves
   it per team with no threshold.
2. **The official final injury report captured as its own source**, so its
   presence is itself the publication signal. `official_injury_report` already
   appears in our source list; whether it carries the date and type has not
   been established, and establishing that needs the bytes.
3. Enough **historical weeks** of the feed that the designated-row share is a
   measured separation with a derived cut rather than a number chosen to make
   three games pass.

**What I will not do.** Pick a threshold. Infer publication from
`retrieved_at`. Read "no designation" as "nobody hurt". I attempted a repair
that refused only when `report_status` AND `practice_status` were both blank,
measured it across all seven captures we hold, found `both blank` is **zero in
every one** — so it would never fire and would delete the guard rather than
correct it — and withdrew it. `readiness.py` is restored to `3f5fc82`.

**What does not wait on you.** The other two instances of the same
blast-radius class are repaired and needed no new evidence:
NYJ@TEN, CHI@CAR and CLE@JAX all now produce full boards where they produced
none. Three of six recovered; three wait on this.


---

## 2026-09-14 — OUT-011: why every scheduled workflow stopped at 2026-09-11T03:38:27Z

**ASSIGNED, not blocked.** This is the sole cause of 47 missed week-1 capture
targets and it is the highest-value unanswered question in the capture layer.
Everything repairable from inside the repository has been repaired (see
`nfl/research/remediation/ws_j/WS_J_CAPTURE_EXECUTOR.md`); the cause itself is
not visible from this checkout.

**What is established here, and it is not a guess.** Four independent scheduled
workflows stopped within 35 minutes of each other and never ran again:

| workflow | commits | first | last (UTC) |
|---|---|---|---|
| `NFL vintage capture` (`nfl-capture.yml`, `*/30 * * * *`) | 161 | 2026-09-07T00:24:50Z | **2026-09-11T03:38:27Z** |
| `NFL status anchored capture` (`nfl-status.yml`) | 32 | 2026-09-08T20:04:53Z | **2026-09-11T03:01:09Z** |
| `NFL T-90 anchored capture` (`nfl-t90.yml`) | 14 | 2026-09-07T02:23:46Z | **2026-09-11T00:44:04Z** |
| `NFL availability watch` (`nfl-availability.yml`) | 1 | 2026-09-10T18:31:05Z | 2026-09-10T18:31:05Z |

Counted on `origin/main` by exact author-string match on `nfl-capture[bot]` /
`nfl-availability[bot]`; 208 bot commits in total. The last GitHub-Actions
manifest row in this checkout is `20260911T004357Z`.

**What this rules out, from the repository alone.** The workflow definitions are
not the cause. They were last edited at `19ef57a`, 2026-09-10T05:02:19Z, and ran
successfully for 22.6 hours afterwards. `main` and the working branch carry
byte-identical `.github/workflows/`. The T-90 crons for 2026-09-13 15:30-16:50Z,
18:55-20:15Z and 22:50-00:10Z and for 2026-09-14 22:45-00:05Z are present,
syntactically valid, and verified by
`nfl/tests/test_capture_obligations.py::test_I` to fire inside the windows they
were generated for. A defect in one workflow also cannot explain four stopping
together. Whatever happened is at the Actions or repository level.

**Exactly what I need, and none of it is inferable from here.** For repository
`<owner>/<repo>`, branch `main`:

1. `GET /repos/{owner}/{repo}/actions/runs?created=>=2026-09-11` — every run,
   its `name`, `event`, `status`, `conclusion`, `created_at`, `run_attempt`.
   **The decisive question: did runs exist and fail, or were there no runs?**
   Absence of a commit is not proof a run did not start, and this repository
   cannot tell the two apart.
2. `GET /repos/{owner}/{repo}/actions/workflows` — the `state` field of each of
   `nfl-capture.yml`, `nfl-t90.yml`, `nfl-status.yml`, `nfl-availability.yml`.
   `disabled_manually` / `disabled_inactivity` would answer this outright.
3. Billing: `GET /repos/{owner}/{repo}/actions/cache/usage` and the account's
   Actions minutes / spending-limit state as of 2026-09-11. The cadence in this
   repository is roughly 48 baseline runs a day plus up to ~96 anchored runs on
   a slate day; a private-repo minute allowance is a live hypothesis and cheap
   to confirm or kill.
4. Whether `main` is still the default branch. Scheduled workflows run only from
   the default branch; every commit since 2026-09-11T03:38Z has gone to
   `claude/nfl-greenfield-architecture-stsxmk` instead.
5. If runs exist for 2026-09-13: the job logs for any run of
   `NFL T-90 anchored capture`, so the failure can be classified as egress,
   parser, permissions or push.

**The structural point, which stands whatever the answer is.** Nothing that runs
inside GitHub Actions can detect GitHub Actions being off; a scheduled job
cannot page about its own scheduler. `.github/workflows/nfl-capture-liveness.yml`
now catches every PARTIAL failure — one workflow disabled while others run,
captures that execute but stop writing manifest rows, a runner that cannot reach
the sources, a cron schedule whose absolute dates have all elapsed — and it is
silenced by the same event as everything else in a total halt. **Closing that
needs an observer outside Actions.** Please either stand one up or tell me it is
out of scope, because until then the answer to "is the capture executor alive"
is only ever "no evidence has arrived", which is an observation of the
consequence and not of the cause.

**Time-critical, today.** `2026_01_DEN_KC` inactives, window
**2026-09-14T22:45Z -> 2026-09-15T00:05Z**, kickoff 2026-09-15T00:15Z, is the
last open week-1 obligation and the only one that has not already been lost.
Three cron entries in `nfl-t90.yml` fire inside it (`45,50,55 22 14 9 *`,
`*/5 23 14 9 *`, `0,5 0 15 9 *`). If the executor is still halted it will close
unfilled like the other 47. **Do not backfill it afterwards** — a miss recorded
as a miss is worth more than a reconstruction.

---

## 2026-09-14 — OUT-012: a live source fetch cannot be proven from this executor

**ASSIGNED, not blocked.** `nfl/tests/test_capture_obligations.py` carries two
proofs recorded as `BLOCKED(cause=NETWORK)` rather than as passing tests. This
is the first of them and it is deliberate: a mock of a fetch proves that the
mock returns what the mock was told to return, and
`nfl/research/parallel_pass/ws11/WS11_FALSE_GREEN_AUDIT.md` already names three
P0 false greens of that shape.

**The state, measured.** Every 2026-09-13 manifest row carries
`basis: LOCAL_INVOCATION`, `is_github_actions: false`,
`basis_can_discharge: false`; 18 runs recorded `NO_EGRESS` on
`official_injury_report`, `official_inactives` and `espn_injuries_json`, and 90
such rows across 32 runs overall. **Two independent blocks are live at once and
fixing either alone changes nothing**: this executor has no egress, AND its
basis cannot discharge an obligation even if the bytes arrived. The second is
not a bug — Directive 7 §5 is explicit that a generic background capture does
not discharge a perishable window — so the remedy is the anchored runner, not a
different threshold here.

**What would discharge this request.** Any ONE of:

1. Confirmation from an executor with egress that these three URLs return real
   content, with the HTTP status and byte count, so the sources can be
   distinguished from an origin outage: `https://www.nfl.com/injuries/`,
   `https://www.nfl.com/inactives/`, and the ESPN injuries JSON endpoint named
   in `nfl/capture/registry.py`.
2. A verified URL for `official_transactions`, which has **177 consecutive
   `ENDPOINT_NOT_YET_VERIFIED` BLOCKED rows and has never been captured once**.
   It is registered and wired; it has no endpoint. This is a declared open debt,
   not a regression, and it needs one working URL from you.
3. A test of `reduce_recoverability_assumption` — whether nflverse still serves
   the older `dt` slices for `depth_charts` and `weekly_rosters`. WS-K's repair
   makes the reduction auditable and leaves this one assumption untested;
   `reduce_recoverability_checked` is `false` on all 368 rows and correctly says
   so. Requested on WS-K's behalf, since this file is mine.

**What I will not do.** Stub the fetch, mock it into a passing test, or route
around the proxy. The tests are recorded BLOCKED and this entry is why.


---

## 2026-09-14T21:20Z — OUT-013: DEN@KC inactives, status at T-3h, and a correction

**Update to the "Time-critical, today" note above, not a new request.** The
DEN@KC board has been rebuilt and sealed since that entry was written and the
inactives position is unchanged, so this records the evidence rather than
asking again.

**Two further attempts today, both refused at the proxy.** Manifest rows
`20260914T161625Z` and `20260914T173936Z`, both `official_inactives`, both
`BLOCKED` / `NO_EGRESS`:

    curl: (56) CONNECT tunnel failed, response 403
    http_code_reported "000", proxy_refusal_status "403"
    discharge_eligibility.targets: []

`targets: []` on both is correct and is worth reading carefully: at 16:16Z and
17:39Z the DEN@KC inactives window had not opened, so there was no obligation
to discharge even had the bytes arrived. The window is
**2026-09-14T22:45Z -> 2026-09-15T00:05Z**. Nothing before it can fill it.

**A correction to something an agent reported and I nearly repeated.** A
workstream reported that its re-run "carries `official_inactives` and
`official_injury_report` hashes that the sealed run did not have", which I was
one step from relaying as "the inactives landed". **They did not land.** What
appears in that run's `capture_validation` is the record of the *failed*
attempts. That is the capture discipline working exactly as designed — the
bytes are refused, the refusal is stored with its cause, and nothing is
stubbed — but a stored refusal is not a stored inactive list, and the two must
never be read as the same artifact.

**What this costs the board, concretely.** Tonight's rebuilt board fires two
HARD `ROLE_STATE_SOURCE_CONFLICT` findings, one per club, both reading:

> the inactive ownership mechanism reports `enforced=False` with failed
> conditions `['official_inactive_evidence_ingested',
> 'evidence_tied_to_this_game_and_team', 'no_unresolved_identity']`

so the quarterback family is quarantined on both teams for want of an
authoritative list. The board is `PRELIMINARY_PROVISIONAL` and **`FINAL` is not
reachable from this executor.** Per the owner's first ruling the ladder is
NFL -> club -> PRELIMINARY; the first two rungs need bytes from outside this
checkout, which is what this entry is for.

**Still not doing.** No stub, no mock, no reconstruction after the window
closes, and no loosening of the FINAL requirement to make tonight's board look
more finished than its evidence supports. If the window closes unfilled, it is
recorded as a miss.

---

## 2026-09-14 — OUT-014: the injury-report publication ceiling was ALREADY LIFTED by bytes you delivered, plus a freshness request

**Part 1 — a correction to the entry above titled "injury-report publication
clock (BLOCKS 3 of 14 games)". It is discharged. Please do not work it.**

That entry asks for either (1) a feed or parser preserving the report's own
date and type, or (2) the official final injury report captured as its own
source. **Both arrived on 2026-09-13, before that entry was written**, in the
package you delivered as `NFL_final_report`. They were ingested by
`nfl/tools/ingest_delivered_injuries.py` (step 5) and are durable in
`nfl/vintage_manifest.jsonl`, capture `20260913T124700Z`, under
`value.explicit_no_designations` — one record per club, each carrying
`report_period` ("2026 REG Week 1 game-status report; explicit game date"),
`game_date`, `evidence_text`, `content_sha256`
(`df1dd90380b8d720ef61790a40a96e3bdaf535b6bd7ea5af9bcde184aa212ac9`),
`retrieved_at`, `publication_time`, `source_modified_time` and an XPath
`locator`. Raw bytes at
`nfl/vintage/delivered_injury_evidence.df1dd90380b8d720.html.gz`.

The five clubs it covers — **DEN, HOU, MIA, MIN, WAS** — are *exactly* the five
the readiness gate was deferring, with no false positives and no misses. The
gate was not detecting missing reports; it was detecting "this club designated
nobody" and calling it "this club has not filed yet". `readiness.py` now reads
the statement and returns `READY_BY_EXPLICIT_NO_DESIGNATION`. No threshold was
invented and `NEEDS_REPORT_STATUS` is still `True`.

So the three games that entry lists as blocked — **BUF@HOU, GB@MIN, MIA@LV** —
plus **WAS@PHI** and **DEN@KC** are recoverable from bytes already in this
checkout. Nothing is owed to you for them.

**Part 2 — what IS still owed, and it is narrow.**

1. **A fresh `injuries` capture.** The newest lawful one is
   `injuries.66e960ec81fccc6e.csv.gz`, `retrieved_at`
   **2026-09-13T15:45:56.665261Z**. Tonight's DEN@KC board cuts at
   **2026-09-14T20:58:33Z**. That is a **29.2-hour** unobserved window over a
   Monday-night game. Source:
   `https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv`.

2. **Re-confirmation of the DEN@KC game-status report.** The statement we rely
   on has `source_modified_time` **2026-09-12T23:07:53.998Z**, about 46 hours
   before the cut. It is lawful and it is what the league published, but it is
   not fresh. What would settle it is the same page,
   `https://www.nfl.com/news/nfl-week-1-injury-report-2026-season`, re-read at
   or after 2026-09-14T20:00Z, specifically the **MONDAY, SEPT. 14** section:
   whether "BRONCOS — No injury designations" still stands, and whether Kansas
   City's two OUT designations (OT Josh Simmons, back; DB Chamarri Conner,
   knee) are unchanged.

**Not blocked on either.** The diagnosis and the repair stand on bytes already
here; both requests would only raise confidence, and neither is a precondition
for the board. Assigned, not blocking.

**One thing I did not do.** Two of Kansas City's delivered rows — Simmons and
Conner — were quarantined at ingest as `NOT_PROMOTED_BY_DELIVERY` ("present in
the evidence set, absent from the candidates"). They reached us anyway through
the nflverse feed, so nothing was lost this time. If the candidate set is meant
to carry every club in the package, that is a gap in the delivery worth
checking on your side before the next one.


---

## 2026-09-15T01:50Z — OUT-014: the realized DEN@KC outcome, for the postgame autopsy

**ASSIGNED, not blocked for both of us.** A postgame layer decomposition of
`2026_01_DEN_KC` was requested. The forecast side is complete and sealed. The
**actual** side does not exist in this checkout, and I will not reconstruct it
from numbers quoted in conversation.

**Measured, not assumed.** The newest 2026 play-by-play capture is
`nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz`, sha256 `1415dd98…`,
`retrieved_at` **2026-09-14T00:25:56Z** — roughly 24 hours BEFORE the
2026-09-15T00:15Z kickoff. It holds **10 games, all week 1, and zero rows for
DEN or KC**. The prior capture `d9e442ae…` (2026-09-11T19:16Z) likewise. So the
game is absent because it had not been played when the bytes were taken, and no
capture has been attempted since 17:39Z because the executor is halted.

**What I need, and why each field.** A postgame capture of `2026_01_DEN_KC`
sufficient to populate the same reduction as `nfl/research/q7/panel.py`, whose
definitions are fixed and must not be reinterpreted downstream:

    attempt     pass_attempt AND NOT sack AND NOT qb_spike
    completion  an attempt that completed
    dropback    attempts + sacks + scrambles   (COMPOSED, never read from qb_dropback)

Per team: offensive snaps, dropbacks, carries, targets. Per quarterback:
dropbacks, attempts, completions, passing yards, passing TD, INT, sacks,
scrambles, rush attempts, rushing yards. Per back and receiver: carries,
rushing yards, targets, receptions, receiving yards, receiving TD.

`https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz`
is the registered source and rank-1 authority; a refreshed pull carrying week 1
complete would discharge this entirely.

**Why the layer decomposition cannot proceed without it.** The request was for
FORECAST -> ACTUAL -> ERROR -> CONTRIBUTION across nine layers: team plays,
team dropbacks, QB dropback share, attempts/dropback, completions/attempt,
yards/completion, passing TD/attempt, INT/attempt, scramble/rush opportunity.
A final passing-yard total identifies **none** of those nine. Four numbers were
quoted to me in conversation (Mahomes 184 passing yards, Nix 131, Walker 23
carries, Johnson 8). Even taking all four as correct, they pin one endpoint and
leave every intermediate layer free: the sequential counterfactual
(actual volume -> actual share -> actual attempt conversion -> actual completion
conversion -> actual yards/completion) is **underdetermined**, and any
attribution I produced from them would be a decomposition of my own
assumptions wearing the costume of a measurement.

**What I did instead, and it needs no bytes from you.** The reported outcomes
are POSITIONED inside the sealed predictive distribution — exact, because the
board stores 1,000 draws per quantity rather than percentiles — and the
one-at-a-time layer sensitivity is computed from the sealed forecast alone.
Both are in the autopsy. Neither asserts the quoted numbers are true.

**What I will not do.** Fabricate the actual layer values, infer them from a
box score I have not read, treat conversation-quoted figures as a capture, or
write any of them into the prospective ledger as a scored outcome. The
`2026_01_DEN_KC` inactives obligation is already recorded MISSED and unfilled
(covered 15, missed 48) and is not being backfilled either.

---

## 2026-09-15T05:10Z — OUT-015: a pregame role-intent source. No such family is captured

**COVERAGE GAP, not a bug, and not blocked for both of us.** Raised by B1's
root-cause work on Kansas City's backfield
(`nfl/research/v3/b1/B1_KC_BACKFIELD_ROOT_CAUSE.md`).

**What the gap is.** Kenneth Walker III (`00-0038134`) joined Kansas City for
2026; every one of his 67 panel rows is Seattle, 2022-2025. Emmett Johnson
(`00-0041013`) has **zero** rows in `panel_p3`, in `panel_enriched.pkl` and in
`q7_recv_game.csv.gz` — a true cold start. The only pregame evidence this
repository holds that speaks to which of them leads the backfield is the ESPN
daily depth chart (`pos_rank` 1 and 2, clean, no tie, stable 2026-09-09 through
2026-09-14). That is one bit, from one vendor, and the appearance layer degrades
it before use.

**Measured, not assumed.** `nfl/vintage/` holds ten source families:
`delivered_injury_evidence`, `depth_charts`, `espn_injuries_json`,
`hardrock_market_snapshot`, `injuries`, `official_inactives`,
`official_injury_report`, `official_status_evidence`, `schedules`,
`weekly_rosters`. Seven were sealed into `d1e2727743c93990`. **None of the ten
carries preseason participation, camp usage, or a coaching statement.**

**What I am asking for, and why each one.**

1. **Preseason play-by-play and snap counts, 2026.**
   `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz`
   filtered to `season_type == 'PRE'`, and
   `https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2026.csv.gz`.
   Dates needed: **2026-08-07 through 2026-08-30** (the three preseason weeks
   preceding the 2026-09-14/15 week-1 slate). Per player: `offense_snaps`,
   `offense_pct`, carries, targets. This is the only quantitative pregame
   observation of a rookie or a newly-acquired back in his current club's
   offence, and it is exactly the quantity `appearance_r8` has to impute for a
   `NO_HISTORY` player today.

2. **Weekly rosters for the 2026 preseason weeks**, same source family as the
   already-captured `weekly_rosters` (`bdab6ecee12d44a4`, retrieved
   2026-09-14T16:16:25Z), for `week` values covering **2026-08-07 to
   2026-08-30**, so a preseason snap can be attributed to a club.

3. **Depth-chart `pos_slot`.** The capture reduction currently drops it: the
   reduced header is `dt,team,gsis_id,pos_abb,pos_rank` while the raw carries
   `pos_slot`. `depth_vintage.py:307-325` records this and measures the harm as
   zero **so far** (0 tie groups on all six persisted blobs). Retaining it is a
   capture-layer change, and it is cheap insurance against the first vendor tie.

**What I am NOT asking for.** Beat-reporter copy, depth-chart commentary, or
coaching quotes. They are not a governed source, they carry no schema, and I
would not know how to refuse a bad one. If a structured, dated, attributable
feed of stated role intent exists, name it and I will spec an ingest; otherwise
this item is closed as out of scope rather than left open.

**What this does not license.** None of the above may be used to score, revise
or re-seal `d1e2727743c93990`, or any board already written. It is an input for
future forecasts only. The root cause of the Kansas City parity is internal and
needs no bytes from anyone — it is in `appearance_r8.featurise` and
`depth_vintage.daily` and is fully diagnosed in the report above. This request
would have made the forecast **better informed**; it would not have made it
**correct**, and I am not offering it as a substitute for the repair.

---

## 2026-09-15T13:40Z — OUT-016: the inactives endpoint is the wrong endpoint, and it has been passing for nine days

**Supersedes a premise in OUT-011 and OUT-013.** OUT-011 asked you why "every
scheduled workflow stopped at 2026-09-11T03:38:27Z". It never stopped. That came
from a stale remote-tracking ref on my side; `main` captured continuously through
2026-09-15T13:06:52Z. **Do not spend time answering OUT-011's question** — there
is no outage to explain. Its entry stays in this file unedited, because an
outbox is a record of what was asked and when, not a list of things that turned
out to be true.


**This is not a blocked task. It is an assigned one, and it is the highest-value
thing I can hand you this week.** I found it while reconciling with main and I
can prove all of it from committed bytes. What I cannot do is confirm the
replacement endpoint, because that needs a fetch.

**What the registry points at.** `nfl/capture/registry.py:234`,
`official_inactives`, `url_template = "https://www.nfl.com/inactives/"`, marked
`required=True`, `authority_rank=1`, and noted as *"the only source that can
discharge an inactives target."*

**What that URL actually served for the whole of Week 1.** An empty-state page.
Its own body text, verbatim:

> Please check back soon for NFL Inactive Reports for this Season

Zero `<table>`. Zero `<tr>`. Not one player name.

**How many times we stored it and called it a capture.** 374. Every
`official_inactives` capture from `20260907T002448Z` to `20260915T130638Z`,
nine days, each one `state: PASS`, `code: CAPTURED`, each with a non-zero
`n_data_rows` (4, 23, 30, 34 or 41 — the number drifts because it is counting
how many news tiles the page happened to be showing).

**Why the substance guard did not catch it, in one line.** The guard is correct
and deliberate — `capture_vintage.py:345` defers a zero-marker HTML payload as
`SOURCE_HAS_NO_ROWS_YET` precisely so an unpublished page is recorded as a debt.
It never fires because this source's marker vocabulary is the single word
`"inactive"` and that word appears 41 times in the page's own furniture: the
`<title>`, the meta description, `og:url`, the canonical link, the ad and
analytics config blobs, a visually-hidden `<h1>`, the placeholder promo, and the
`data-link_name` / `href` / `aria-label` attributes of news tiles. One of the 41
is the empty-state sentence itself. **The page's written statement that it has no
data counts as one unit of evidence that it has data.** Then `:358` assigns that
count to `n_data_rows`, so page chrome is laundered into a row count and every
consumer downstream sees rows.

Recorded as **D20** in `nfl/research/live/OPEN_DEFECTS.json`, replayed by
`nfl/tests/test_inactives_substance.py` (sections B and C fail by design).

**The part that matters for DEN@KC, and it corrects me twice.** I reported in
OUT-013 that the window closed with nothing attempted. That was wrong: eight
captures were taken inside the declared window 22:45:00Z–00:05:00Z, by the
GitHub Actions workflow `NFL T-90 anchored capture` on `refs/heads/main`, each
with `execution_target.declared_before_fetch: true` and basis
`SCHEDULED_WINDOW_ANCHORED`, each passing `discharge_eligibility` for
`2026_01_DEN_KC` with `refusals: []`. I then corrected myself to "so the window
was filled," and committed that. **That was wrong too.** The eight are
provenance-lawful and substantively empty. The scheduler did its job perfectly
and fetched a page with nothing on it.

Had this branch consumed those eight, the R2 eligibility gate would have been
handed 41 rows of navigation furniture and would have reported the inactives
obligation **discharged over an empty set**. The board would have published
claiming knowledge it did not have. That is worse than the miss we actually took.
**The Week-1 miss remains a miss** and nothing here changes `d1e2727743c93990`.

**What I need from you.**

1. **The correct endpoint pattern.** The empty page links to its own replacement.
   Occurrences 17–22 of the marker word are the `href` and `title` of
   `/news/week-1-monday-night-inactives-denver-broncos-at-kansas-city-chiefs`,
   summarised as *"Here are the official inactives for the Denver Broncos at the
   Kansas City Chiefs."* So the data was published, on time, at a per-game URL.
   I need to know whether that slug is derivable before the article exists —
   from `season`, `week`, kickoff slot and the two club names — or whether it can
   only be discovered by reading an index. **Those two answers imply completely
   different capture designs** and I will not guess between them. If it is only
   discoverable, name the index that lists it and I will spec a two-stage fetch.

2. **One populated inactives page, any game, as a positive control.** This is the
   blocking item. The repair bar is two-sided: a fix must make the empty page
   stop passing *and* leave a page with real rows still passing. I have zero
   blobs for the second half — all 392 PASS records are either the empty landing
   page or your delivered markdown. Section D of my test reports `NOT_EXECUTED`
   rather than skipping, and it stays `NOT_EXECUTED` until you send bytes.
   **Without it I can make the test green and I would have no idea whether I had
   broken real captures, so I am not going to.**

3. **Confirmation on one point of fact.** You already solved this once. Your
   delivered capture `20260910T234420Z`, *"SF @ LA: Final Pregame Intelligence
   Capture,"* carries both complete official inactive lists and cites
   `https://www.nfl.com/news/australia-game-inactives-san-francisco-49ers-at-los-angeles-rams`.
   You went to the per-game article by hand. Was `https://www.nfl.com/inactives/`
   ever populated this season and we missed the window, or has it been an
   empty shell since the registry was written? If the latter, the endpoint has
   never once worked and `source_status: VERIFIED_REACHABLE_EXTERNALLY` is
   measuring reachability while saying nothing about content — which is a
   registry-vocabulary problem I will fix on my side either way.

**What this does not license.** No bytes you send may score, revise or re-seal
any board already written. Anything that arrives now is a pregame input for
future forecasts only, and the captures already in the tree stay exactly as they
are: `PASS`, empty, and annotated.

---

## 2026-09-15T15:05Z — OUT-017: three sources have no payload contract and I cannot write one without a sample

**Small, cheap, and blocking a guard rather than a model.** Not urgent; do it
whenever a capture window is convenient.

**Background.** D20 was an html source that passed for nine days over a page
carrying no players. Auditing the other content kinds found the same hole in
both — the validity check counts the ENVELOPE. ESPN's injuries document is
`{injuries:[32 teams], season, status, timestamp}`, which scores 32 + 3 = 35
against 800 real injury entries, **and still scores 35 when every team's list is
emptied**. The csv check counts rows and never looks at a column.

That is closed (D22). Each source now declares where its entities live —
`row_container` for html, `payload_path` for json, `required_columns` plus
`substantive_any_of` for csv — and `nfl/capture/payload_contract.py` goes and
looks. Positive control: all 428 espn blobs, all 296 csv blobs and all 354
injury-report blobs still pass. Negative control: six seeded emptiness cases all
refused, including the one the old check provably could not see.

**What I cannot do.** Three sources have **zero committed blobs**, so their
schema cannot be read:

| source | state | what I need |
|---|---|---|
| `official_transactions` | `PENDING_ENDPOINT_VERIFICATION` | one successful capture, any date |
| `pbp_participation` | `REACHABLE`, `watch_only` | one file, any week of 2025 or 2026 |
| `snap_counts` | `REACHABLE`, `watch_only` | one file, any week of 2025 or 2026 |

For each I need **one real payload**, or failing that just **the exact header
line**. That is enough to declare the contract.

**Why I am asking instead of writing plausible column names.** Because this
project has already shipped that exact defect: an export wrote 7,926 rows with
every meaningful column blank, *because the field names were guessed instead of
read from the schema*. Declaring `('player_id', 'team', 'snaps')` because it
sounds right would put a guess into a guard whose whole job is to refuse
guesses. `nfl/tests/test_payload_contract.py` reports all three as
**NOT_EXECUTED** — not a pass — and names this request as what discharges them.

**One thing worth knowing if you go for `snap_counts` anyway.** OUT-015 already
asks you for 2026 preseason snap counts for the appearance model. The same
fetch answers both: I need the header for the contract, the rows for the model.

**No hurry and nothing is blocked on it.** The three sources capture nothing
today, so an undeclared contract costs nothing yet. It becomes load-bearing the
moment any of them starts producing.

## OUT-018 — 2023-2025 historical point-in-time availability sources

**Filed** 2026-09-15. **Assigned, not blocked for both of us.** I have no egress;
this is yours.

### What I measured before asking

`nfl/vintage_manifest.jsonl`, 4,492 rows: **4,474 are season 2026 and 18 carry no
season. Zero rows for 2023, 2024 or 2025.** No row in the file carries a
`partition_id`, so the durable partitions are addressed by the blob names rather
than the manifest rows -- worth knowing before you diff anything against it.

So the 2023-2025 time machine currently has:

| family | what exists | grade it can honestly carry |
|---|---|---|
| play-by-play outcomes | `nfl/research/postgame/pbp_20{21..25}.*.csv.gz`, nflverse, sha256-addressed, provenance JSON alongside | postgame only -- quarantined from pregame features |
| trailing usage / volume / efficiency | derivable from the above | **RECONSTRUCTED_PIT** at best |
| injury report, depth chart, inactives, transactions, snap participation | **nothing** | **UNAVAILABLE** |

### Why the pbp files do not fix this

They were all retrieved 2026-09-13 in one pull. A 2023 Week 5 forecast at T-72H
needs what was *knowable* on that date; what we hold is what nflverse says
*today* about the whole 2023 season. Filtering to `event_time < cutoff` makes the
football events lawful, and that is the RECONSTRUCTED_PIT grade -- it does not
make them EXACT_PIT, because revisions between 2023 and 2026 are invisible to us.
I will not label them EXACT_PIT and I will not repair the gap by inference.

### What I need

nflverse publishes per-season historical datasets. For **2023, 2024 and 2025**:

```
injuries_{season}.csv          releases/download/injuries/
depth_charts_{season}.csv      releases/download/depth_charts/
snap_counts_{season}.csv       releases/download/snap_counts/
pbp_participation_{season}.csv releases/download/pbp_participation/
rosters_weekly_{season}.csv    releases/download/weekly_rosters/
```

Same discipline as the 2026 capture: write the raw response to disk before
parsing, record `retrieved_at`, the resolved URL, `sha256` and `n_bytes`, and
refuse a body that arrives without provenance.

### The field that decides whether any of this is usable

For each of those datasets, tell me **which column carries the content's own
timestamp** -- report week and report date for injuries, week for depth charts,
game date for snap counts. `known_from` has to come from the content, never from
our retrieval date. A 2023 Wednesday injury report is lawfully knowable before a
Sunday 2023 kickoff *because the report says when it was published*; the fact
that we downloaded it in 2026 is irrelevant to chronology and fatal to it only if
we have nothing else to go on.

Where a dataset carries no such column, say so plainly and I will grade that
family APPROXIMATE or UNAVAILABLE rather than invent a date for it.

### What I am not asking for

No sportsbook prices, no market data, no projections from any vendor. None of
those may enter as predictive inputs.

### What happens meanwhile

I am building the mart, the four forecast clocks, the chronology guards and the
leakage tests against what exists, and grading the availability families
UNAVAILABLE. That work is not blocked. Only the honest grade for those families
is.

## OUT-019 — pbp_participation 2026, the last thing between us and a skill-position board

**Filed** 2026-09-15. **Assigned, not blocked for both of us.** No egress here.

### What it blocks

DET-BUF (`2026_02_DET_BUF`, Thursday 2026-09-17) seals with quarterbacks only.
Appearance, participation, targets_carries, conversion and td_layer all return:

```
SLATE_FITS_UNAVAILABLE
  participation_prior BLOCKED[PARTICIPATION_HISTORY_STALE]:
  the newest participation history is ordinal 202518 and the forecast is
  2026 week 2. ewma_hl2 weights the most recent games hardest, so running it
  with no 2026 game would be a different estimator.
  missing_source: pbp_participation_2026
```

That refusal is CORRECT and I am not suppressing it. `week2_data_debt.json`
promised it. Running the accepted estimator on 2025 data alone would be a
different estimator wearing the accepted one's name.

### Why I cannot clear it myself

`pbp_participation` is in the manifest 380 times, every row:

```
NOT_APPLICABLE  WATCH_ONLY_SOURCE_NOT_CAPTURED_HERE
"registered and reachable, but handled by the periodic availability watch,
 which is not event-anchored and discharges nothing. Deliberately outside
 this execution."
```

**Reachable, and never captured.** Not a code defect, not a missing endpoint --
an uncaptured source.

### What I need

`pbp_participation_2026` covering **week 1** (and week 2 once it exists):

```
releases/download/pbp_participation/pbp_participation_2026.csv
```

Same discipline as every other capture: raw bytes to disk before parsing,
`retrieved_at`, resolved URL, `sha256`, `n_bytes`, and a refusal on a body with
no provenance.

### One question that decides how much it buys us

Week 1 is the ONLY 2026 week that has been played. `share_prior` needs a
current-season observation to satisfy its staleness rule; one week will satisfy
it. Tell me whether the file carries `offense_players` per play (the route
denominator) or only the snap aggregate -- that decides whether the receiving
layer gets routes or only a snap proxy, and I will grade it accordingly rather
than assume.

### Not asked for

No sportsbook prices, no vendor projections. Neither may enter as a predictive
input.

---

## 2026-09-17 — OUT-020: the official DET @ BUF inactive declaration, tonight

**ASSIGNED, not blocked for both of us.** Everything downstream of the bytes is
built and tested here. What this executor cannot do is reach the page.

**Kickoff** `2026-09-18T00:15:00Z`. The list publishes about T-90, so it exists
now.

### What I need — the raw document, nothing parsed

```
https://www.nfl.com/inactives/
```

or the equivalent official club pages:

```
https://www.detroitlions.com/  (official inactive declaration, Week 2 vs BUF)
https://www.buffalobills.com/  (official inactive declaration, Week 2 vs DET)
```

Raw bytes only. Not a summary, not a vendor table, not a screenshot
transcription — `nfl/tools/ingest_inactives.py` refuses all four by design:

> It will not accept a reporter's summary, a sportsbook line, an inferred
> dress list, or a retrospective INA column. `--bytes` must be the
> authoritative document.

With the bytes on disk the whole chain is one command:

```
python3.12 nfl/tools/ingest_inactives.py \
    --game-id 2026_02_DET_BUF --bytes /path/to/inactives.html \
    --source-url https://www.nfl.com/inactives/ \
    --retrieved-at <UTC> [--published-at <UTC>] \
    --out nfl/research/live/2026_02_DET_BUF
```

It hashes and content-addresses the bytes before parsing, requires BOTH clubs
before emitting `POST_INACTIVES_COMPLETE`, refuses an ambiguous name rather
than guessing, and zeroes an inactive player's appearance draws in every draw
through the candidate's own mechanism.

### Why I cannot clear it myself — measured, not assumed

Attempted 2026-09-17T23:31:01Z. Every official host is refused by the
environment's network policy at the CONNECT stage:

```
www.nfl.com:443            403  CONNECT tunnel failed   curl exit 56
www.detroitlions.com:443   403  CONNECT tunnel failed   curl exit 56
www.buffalobills.com:443   403  CONNECT tunnel failed   curl exit 56
api.nfl.com:443            403  CONNECT tunnel failed   curl exit 56
operations.nfl.com:443     403  CONNECT tunnel failed
www.espn.com:443           403  CONNECT tunnel failed
```

The control matters: `raw.githubusercontent.com` answers `200` from this same
executor, which is how the pbp blobs were captured this afternoon. So this is a
per-host policy denial, not a broken network and not a code defect.

### What I will NOT do instead

A RotoWire screenshot of both inactive lists is in hand. It is secondary
evidence and it is not being ingested, not being transcribed into the governed
path, and not being used to zero anybody. `inactives.verify_supplied_names`
exists precisely for supplied names — and it verifies them AGAINST the official
HTML, so it cannot run without the document either.

### The thing that is worse than the missing bytes

`AVAILABILITY_AUDIT_DET_BUF.json` (run `e58206e3e8473dc1`, 2026-09-16T13:20Z)
reports `official_feed_weeks: ["1"]`, with 21 of 32 pool players at
`EXISTS_BUT_DID_NOT_JOIN` and Ty Johnson carrying `p_appear = 0.8929` with
`f_inj_available = 0`.

**CORRECTED 2026-09-17T23:37Z, and the correction matters.** An earlier draft
of this item read "the governed injury feed carries no 2026 week-2 row at
all". That was wrong, and it was wrong in the direction that would have sent
somebody looking in the wrong place. `injuries_2026.csv` was published
`Last-Modified: 2026-09-17T12:34:06Z` carrying **194 week-2 rows**. What was
stale was this repository's newest CAPTURE of it, `20260914T173936Z`, 20,631
bytes, week 1 only. The 13:20Z run read that capture and reported week 1
correctly. The defect is capture cadence, not the join.

`capture_vintage.py --season 2026` has now been run: capture
`20260917T233739Z`, new blob `nfl/vintage/injuries.d25887c3df86bf99.csv.gz`,
41,688 bytes, 377 lines. **And it changes no projection**, which is the useful
part: the only two Week-2 `Out` designations across both clubs are Christian
Mahogany (OG) and Blake Miller (OT), neither of whom the model carries as a
player; Ty Johnson is `Questionable`, not `Out`; and Skyler Bell has **no
injury row at all**, because a healthy scratch never appears on an injury
report. Tonight's own data therefore demonstrates the thing this item is
asking for: the injury report cannot substitute for the inactives declaration.

One smaller defect noticed in passing and NOT fixed under a kickoff clock: the
capture recorded `source_timestamp: None` for `injuries` while the final hop
did send `Last-Modified`. Same class as the pbp header-truncation defect fixed
earlier today.

---

## 2026-09-18 — OUT-021: professional NFL Showdown portfolio practice under known model uncertainty

**ASSIGNED.** This is a literature and practitioner-practice question, and the
open web is refused at CONNECT from this executor (`www.espn.com` and every
non-GitHub host tested 2026-09-17T23:28Z and 23:36Z; `raw.githubusercontent.com`
answers 200 from the same process, so it is a per-host policy denial).

**Why it is not being written from recollection.** Tonight's failure was an
unsourced number being treated as trustworthy because nothing flagged it.
Writing a "research package" on professional DFS practice from memory and
presenting it as research would be that same failure in a different medium.

### The question

A model has known player-level uncertainty or a recorded defect shortly before
lock, and the optimizer still has to produce a portfolio. What do strong
Showdown players actually do?

1. how they cap or remove uncertain players;
2. when they override raw projections, and on what evidence;
3. how they handle cheap punts with weak or unresolved roles;
4. how they diversify captain exposure, and against what objective;
5. how they use projected ownership and duplication risk;
6. how they build game-script buckets;
7. how they treat questionable, inactive and role-uncertain players;
8. how many lineups go to contrarian versus core scenarios;
9. how they distinguish projection error from intentional leverage;
10. what stops a known model bug becoming portfolio concentration.

### What is wanted back

A workflow, exposure-governance rules, captain-selection rules, punt rules,
uncertainty controls, scenario-bucket architecture, ownership and duplication
integration, and a post-lock review checklist -- each with its source, so a
claim can be checked rather than trusted.

### What already exists here, so it is not duplicated

`nfl/production/dfs/projection_confidence.py` and `portfolio_guard.py` answer
(1), (2), (7) and (10) as **governance**, with declared caps that are
explicitly not fitted. Questions (3), (5), (8) and (9) need an ownership and
field model, which does not exist. Questions (4) and (6) need a contest-payout
simulator, which does not exist. The architecture in
`nfl/production/DFS_ARCHITECTURE.md` names all three layers.

### Not asked for

No sportsbook prices, no vendor projections. Neither may enter as a predictive
input, and nothing learned here may reach the football simulator -- that
boundary is the whole point of the DFS architecture file.

---

## 2026-09-18 — OUT-022: FanDuel rules and a slate salary export

**SPLIT AND PARTIALLY RESOLVED 2026-09-18.**

| item | status |
|---|---|
| **OUT-022A** FanDuel scoring rules | **RESOLVED** — official Rules & Scoring, retrieved 2026-09-17 |
| **OUT-022B** FanDuel single-game structure | **RESOLVED** — first-party documentation; 6 slots, $60,000, MVP salary 1.5x |
| **OUT-022C** FanDuel slate salary export | **STILL REQUIRED** |

**022C is what remains.** Slate-specific player ids, salaries and eligibility
must come from the actual contest file. They may NOT be inferred from the
DraftKings salaries in this repository, from public articles, or from any
projection: a DK salary is DK's opinion of a player's price, not FanDuel's, and
the two sites price the same slate differently.

Until 022C lands, `nfl/dfs/scoring/site_rules.py` will validate a FanDuel
lineup's SHAPE but there is no FanDuel player universe to build one from.

**What the resolved half corrected, kept on the record rather than erased:**
all three FanDuel yardage bonuses were recalled as 0.0 and are +3; the format
was recalled as 5 slots with unmultiplied MVP salary and is 6 slots with
multiplied MVP salary. Every one of those was a field the module had already
flagged `HIGHEST_RISK_IF_WRONG` and refused to ship on.

---

## SUPERSEDED — original OUT-022 text

**ASSIGNED.** The adapter is built and unit-tested; what is missing is the
authority for its numbers. The open web is refused at CONNECT from this
executor.

### Why this is not written from recollection and shipped

DraftKings scoring in this repository is **verified**: the engine carries its
own DK implementation and `nfl/dfs/scoring/draftkings.py` reproduces
`dk_scoring/dk_points` to 7.1e-15 over 29 players and 8,000 worlds. FanDuel has
no such anchor here, so its coefficients are marked
`UNVERIFIED_FROM_RECOLLECTION` and `fanduel.rules_state()` BLOCKS.

Half a point per reception moves every pass-catcher on a slate. On this board
Amon-Ra St. Brown is 4.19 DK points lower on FanDuel and Josh Allen only 0.72 —
almost all of that gap is the reception rule and the missing yardage bonuses. If
the recalled table is wrong, it is wrong in the place that reorders the entire
receiver market.

### What is needed

1. **One FanDuel NFL single-game salary export.** It settles roster size, salary
   cap, positional eligibility, whether kickers are offered, and — the field
   that changes the shape of the optimisation rather than rescaling it —
   whether the MVP row carries its own multiplied salary. DraftKings multiplies
   captain salary by 1.5; FanDuel is believed not to. Believed is not good
   enough to build a submittable lineup on.

2. **The current FanDuel NFL scoring table**, to check these three first:
   `reception` (believed 0.5, DraftKings 1.0), `bonus_100_rec_yards` and
   `bonus_300_pass_yards` (believed zero, DraftKings 3.0 each).

Dropping a verified table at
`nfl/dfs/scoring/FANDUEL_RULES_VERIFIED.json` clears the block.

### Not asked for

No projections, no ownership, no contest results. Site rules and a salary file.

---

## 2026-09-18T04:10Z — OUT-023: the DET @ BUF final outcome. ASSIGNED, not blocked.

**What is needed:** the authoritative final result of `2026_02_DET_BUF`,
kickoff 2026-09-18T00:15:00Z — final score by side, and a per-player stat line
for every player who took a snap, covering the twelve fields
`nfl/postgame/outcome.py:STATS` names: `pass_att pass_cmp pass_yards pass_td
interceptions rush_att rush_yards rush_td targets receptions rec_yards rec_td`.

Preferred form, in order: the nflverse `stats_player_week_2026` row set once it
carries week 2; the nflverse `play_by_play_2026` file once it does; an official
box score with its URL and retrieval time.

**What was already tried here, with results** (recorded in
`nfl/research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME/CAPTURE_ATTEMPT.json`):

| source | result |
|---|---|
| nflverse `play_by_play_2026.csv.gz` | HTTP 200, sha256 `b69f55a172965e16` — **byte-identical to the pre-kickoff capture**, week 1 only, 0 DET_BUF rows |
| nflverse `stats_player_week_2026.csv` | HTTP 200, week 1 only |
| nflverse `snap_counts_2026.csv` | HTTP 200, week 1 only |
| nflverse `schedules.csv` | HTTP 404 |
| nfl.com, espn.com, detroitlions.com | 403 at CONNECT |

This is a publication lag, not a failure: the game ended a few hours ago and
the weekly files had not rebuilt. **It is assigned rather than blocked** — if
the other agent can reach a box score now, it does not need to wait for the
nflverse rebuild.

**What must travel with the bytes.** Source URL, retrieval timestamp in UTC,
and the sha256 of the raw file. `nfl/postgame/outcome.py` refuses an artifact
without `source`, `retrieved_at_utc` and `source_sha256`, and it is right to.

**What must NOT be sent.** A score recalled in conversation. The sentence "a
high-scoring 41-31 game" reached this executor and is recorded as
`UNVERIFIED_SECONDARY — NOT INGESTED`: it carries no source, no timestamp, no
hash, and it does not even say which side scored 41. Three graders and a
prospective ledger block are built, tested and waiting; all of them refuse
until a verified artifact lands at
`nfl/research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME/OUTCOME.json`.

**A second, smaller request, and it is now permanently unrecoverable if it is
not already held.** There is no closing player-prop vintage for this game. The
only prop capture is 2026-09-17T21:44–21:45Z, about two and a half hours before
kickoff; vintages 2 and 3 are game-line displays at 23:05Z and 23:06Z. If a
Hard Rock player-prop snapshot from nearer kickoff exists in storage outside
this checkout, it would make a closing-line comparison possible. If it does
not, closing-line value for DET @ BUF props stays `NOT_AVAILABLE` and is stated
as such rather than approximated from the pre-kickoff board.

**Not asked for.** No projections, no ownership, no contest results, no market
prices as model input. Market data may only evaluate a forecast that was sealed
before it.

---

## 2026-09-18 — 2026 Week-2 play-by-play, for the OAS1 hurdle

**Assigned, not blocked.** The Week-2 OAS1 candidate is fitted; it cannot be
scored here, and the reason is one file.

**What is needed.** The nflverse 2026 play-by-play release **including week 2**:

    https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz

The capture in this repository is `pbp_2026.b69f55a172965e16.csv.gz`, retrieved
2026-09-17T18:57Z, `Last-Modified: Thu, 17 Sep 2026 14:17:35 GMT`. It carries
**2,756 rows, all week 1** — verified by reading the file, not inferred. Week-2
plays are absent, so `oas1_epa_target` has no held-out values at ordinal 202602
and OAS1 cannot be compared with B5 or B4.

**What must travel with the bytes.** Source URL, retrieval timestamp in UTC,
`Last-Modified` as sent, and the sha256 of the raw file. The existing capture
path (`nfl/ingest/pbp_capture.py`) already records all four and is
content-addressed, so a recapture that returns identical bytes is recognised as
one vintage rather than two. A capture that still carries only week 1 is a
useful answer: it means nflverse has not rebuilt yet, and that is a publication
lag to record rather than a failure to chase.

**What this unblocks, exactly.** `nfl/research/oas1/week2.py` fits the
candidate today and returns `OAS1_WEEK2_SCORE_NOT_COMPUTABLE_HERE`. With week-2
plays present, `score_availability` passes and the pre-registered hurdles can
be evaluated: OAS1 against B5 and B4 for pass, B5 for rush with B3 labelled
`POST_HOC_STRONGEST_BASELINE`, clustered by game and by team.

**Sequencing that matters.** The candidate's unit strengths are already written
to `nfl/research/oas1/OAS1_WEEK2_RESULT.json` and committed. The forecast
therefore exists in the repository **before** the outcome bytes arrive, which
is the position a hurdle test is supposed to be run from. Please do not send a
scored comparison — send the plays, and let the committed grader run.

**Not asked for.** No sportsbook price, no projection, no ownership. Market
data may evaluate a forecast that was sealed before it and may never feed one.

---

## 2026-09-18 — historical injury designations, 2022–2025

**Assigned, not blocked.** The A1 successor test is specified and cannot run.

**What is needed.** The nflverse injuries release for **2022, 2023, 2024 and
2025**:

    https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_<season>.csv

This repository holds `injuries` for **2026 only**: 1,145 rows across 9
content-addressed vintages from 2026-09-07 to 2026-09-17, weeks 1 and 2,
carrying `report_status` and `practice_status`. The existing capture path
already records URL, retrieval time, `Last-Modified` and sha256, and is
content-addressed, so a recapture returning identical bytes is one vintage.

**Why it is the efficient path.** `A1_APPEARANCE_CERTAINTY` is FALSIFIED and
CRITICAL: the cohort it called certain appears 93.13% of the time, n=1,702 over
2022–2025. The successor question is what conditions the missing 6.87%, and the
obvious candidate is the pre-kickoff injury designation.

Measured, not assumed: at 2026 week 2 the cohort is **59 players and none of
them carries an Out, Doubtful or Questionable designation** — 13 listed with no
status, 46 not listed. The conditioning variable has no contrast, so its effect
is not estimable at any sample size
(`nfl/research/assumptions/A1_SUCCESSOR_FEASIBILITY.json`). With 2022–2025
designations the test runs against the same population that falsified A1, at
adequate n, immediately. Waiting for prospective weeks works too and is slow.

**A note on what a null would mean.** If designations do not explain the 6.87%,
that is a useful result and must be recorded as one. Please send the captures,
not an opinion about whether they will help.

**Not asked for.** No sportsbook price, no projection, no ownership.

---

## 2026-09-19 — the four companion files of the full-slate DFS packet

**Assigned, not blocked.** The report arrived; its four companion files did not.

**What is needed.** From the same engagement that produced
`nfl-fullslate-dfs-lineup-construction.pplx.md`:

    measure_dfs_correlations.py
    measure_tails.py
    dfs_correlation_results.json
    dfs_tail_results.json

The report states at line 35 that these are "included alongside this report".
Only the markdown reached this session. `EXTERNAL_PACKET_PROVENANCE.json`
records the report's sha256 and the absence.

**Why it matters, specifically.** The method was re-implemented from the
report's prose and the **realized-label panel reproduces almost exactly** —
QB with PC1 at 0.421 and 0.445 against their 0.420 and 0.438. The **ex-ante
panel does not**: 0.207 and 0.170 against their 0.368 and 0.274. Because the
realized half matches, the stat-line building, the scoring and the correlation
code are all validated, and the disagreement is isolated to how prior-week role
labels are formed — which the report's prose under-specifies.

Two candidate causes were measured and both move the number the right way:
role collisions (26.2% of team-games have the quarterback also ranked as the
second carrier, which the prose's literal reading permits), and an ex-ante
window that includes the current game (this closes most of the gap and lands
QB with PC2 on +0.293 against their +0.296). **The scripts would settle which,
in minutes.**

**Not asked for.** No conclusions, no re-analysis, no opinion on who is right —
just the four files as they were written.

---

## 2026-09-19 — official DK and FD Classic rules, for machine-readable site contracts

**Assigned, not blocked.** The directive requires DraftKings Classic and
FanDuel Classic rules to be **independently verified against the operators' own
rules pages** and encoded as machine-readable contracts. This executor has no
egress, so no contract is written in this pass — encoding rules from
recollection and labelling them verified is the exact defect the FanDuel
episode already cost, and a relayed value keeps relayed provenance.

**What is needed, per site, from the operator's own page.** Please send the
page bytes with URL, retrieval timestamp in UTC and sha256 — not a summary.

**DraftKings Classic (NFL main slate).** Roster positions and counts; salary
cap; FLEX eligibility; minimum games represented; minimum teams represented;
full scoring for QB/RB/WR/TE/K if applicable; **DST scoring including the
points-allowed ladder and every tier boundary**; late-swap behaviour.

**FanDuel Classic (NFL main slate).** Roster positions and counts; salary cap;
FLEX eligibility; minimum teams; **maximum players per team**; full scoring
including the half-point reception and the fumble penalty; DST scoring in full;
late-swap behaviour.

**Do not infer one site's rules from the other**, and do not fill a gap from
memory — an unverified field should come back marked unverified.

**Why the DST ladder specifically.** There is no DST scoring adapter in this
repository at all (`statline.NOT_SIMULATED`: "the engine produces no
team-defence outputs at all"). That absence blocked five claims of the
full-slate packet from being reproduced — every claim involving a defence,
including QB with opposing DST and RB with DST — and it blocks any Classic
lineup, which must field one.

**What it unblocks.** Stage A of
`nfl/research/dfs/fullslate/FULLSLATE_GAP_MAP_AND_ROADMAP.md`: the site
contracts, the roster universe, the legal solver and the brute-force legality
fixtures for both sites. Note that A7 — a full-slate joint football-world
generator — remains the gating item and is football work, not DFS work, so
these bytes do not by themselves enable an optimizer.

**Not asked for.** No strategy content, no ownership data, no contest results,
no optimizer settings.

---

## 2026-09-19 — OUT-024: the participation availability watch has been dead for four days, and the vintage capture is not

**ASSIGNED, not blocked.** This is a workflow fault with a named cause, and the
fix is a one-line change I can make; what I cannot do is confirm it took.

### What I measured

`nfl/availability_manifest.jsonl` holds 24 probe records and its newest is
**2026-09-15T06:37:05Z** — 4.4 days old at the time of writing. The last
`nfl-availability[bot]` commit on `main` is 2026-09-15T18:30:34Z. Nothing since.

Over the same period the *vintage* capture has been entirely healthy: on
`capture-prod` at 763b776 the six core sources — depth_charts,
espn_injuries_json, injuries, official_injury_report, schedules,
weekly_rosters — were all last captured **2026-09-19T15:05:38Z**, i.e. half an
hour old, on a thirty-minute cadence with no gaps.

### The cause, as far as this tree can see it

On 2026-09-15T19:27Z `b9b6ff4` ("Point the scheduled capture at the governed
capture surface") moved the capture workflows onto the `capture-prod` branch.
`nfl-availability.yml` was **not** moved: lines 129-130 still read

    git pull --rebase --autostash origin main
    git push origin HEAD:main

So it writes to `main` while the surface it belongs to writes to
`capture-prod`. That alone would not stop it from running, which is why this is
an ASSIGNED question rather than a finding: I can see that it stopped, and I can
see one change that landed twenty-two minutes before the last run, but I cannot
read the Actions run log from here to distinguish "disabled", "failing at the
push step", "scheduled but never fired" or "succeeding and pushing to a branch
nobody reads".

### What I need

1. The **run history of `NFL participation availability watch`** since
   2026-09-15 — fired / not fired, and if it fired, the failing step.
2. If it is failing on the push: confirmation that pointing it at
   `capture-prod` is the intended fix, since that is what the other four
   workflows now do.
3. One **current probe result** for the two URLs, so the claim can be restated
   without waiting for the workflow:
   - `https://github.com/nflverse/nflverse-data/releases/download/pbp_participation/pbp_participation_2026.csv`
   - `https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2026.csv`
   HTTP status, byte count, and the first line only. Nothing parsed.

### Why this is not cosmetic

`GAP-2026-PARTICIPATION` in `nfl/INFORMATION_GAP_REGISTRY.json` carries a
two-day recheck horizon, and it has one because **snap_counts went from 404 to
200 two days after the claim that both files were absent**. The watch is the
only thing that would notice the same happening to `pbp_participation`. With
the watch dead, that gap's claim is now 4.4 days old against its own horizon and
is surfaced by `nfl/tools/discovery.py` as `ASSIGNED_PAST_HORIZON`.

### What it does NOT unblock, stated so it is not misread

Availability is not predictive eligibility. The snap_counts record carries
`authorization_code: NOT_AUTHORIZED_BY_OWNER` and
`ordering_code: NO_FORECAST_TO_JUDGE`. These are postgame files. Restarting the
watch buys provenance, not a feature.

### Not asked for

No parsing, no ingestion, no model change, and no decision about predictive use.

---

## 2026-09-19 — OUT-025: the three information gaps whose recheck is not executable here

**ASSIGNED.** `nfl/INFORMATION_GAP_REGISTRY.json` now carries, per gap, when it
was last rechecked, the newest instant in the evidence that recheck read, and a
horizon measured against the evidence rather than the reading. Three gaps have
`recheck_executable_here: false`, and the project's own rule is that such a
recheck is recorded as ASSIGNED with an outbox entry rather than left standing
as a fact. This is that entry. **None of the three is urgent** — all three are
inside their horizons as of today — so this is a standing request, not a
Sunday one.

**`GAP-ROUTES`** (action BLOCKED, 30-day horizon). Per-player routes-run from a
licensed vendor. What is needed is only the **state of the licensing question**,
not the data: is the FTN agreement still unsigned, and are ML/training rights,
local retention, derived-output ownership, post-termination rights, `skp_role`
coverage and the identifier crosswalk still unresolved? Note that identity is
*not* the blocker — `pff_id` covers 100% of the WR/TE/RB frame (1,126 players,
47,215 player-games), so a join would be deterministic.

**`GAP-ENDZONE-TARGETS` and `GAP-COVERAGE-MATCHUP`** (action HOLD, 30-day
horizon). Both want a charting source: target *depth* for the first, receiver-
specific coverage for the second. What is needed is whether any such source
exists on terms this project could use. The current proxy for end-zone targets
is line of scrimmage, which is a different quantity, and it is marked
UNAVAILABLE in the TD1 pre-registration rather than approximated — that should
stay true until a real source arrives.

**`GAP-PLAYCALLER`** (action HOLD, 30-day horizon). Whether any structured feed
of play-caller changes exists. The current proxy is team history, which lags a
change by weeks.

### Not asked for

No vendor data, no trial downloads, no scraped substitutes, and no
recommendation about whether to license anything.

---

## 2026-09-19 — OUT-026: **TIME-CRITICAL.** The T-90 windows for tomorrow's slate do not exist on the branch that schedules them

**Deadline: 15:30Z Sunday 2026-09-20**, which is the first window. After that the
evidence for eight games is gone and cannot be reconstructed.

### What I measured

`.github/workflows/nfl-t90.yml` carries sixteen cron entries and every one is
anchored to a **week-1** kickoff — 2026-09-09, 09-10, 09-13, 09-14. There is
nothing for 09-17, nothing for 09-20 and nothing for 09-21. Consistent with
that, `official_inactives` last reached state PASS at **2026-09-15T17:05:12Z**
and carries 184 DEFERRED records since.

The cause is in the drift test, not the generator: `test_t90_workflow.py` read
`SEASON, WEEK = 2026, 1`, so it regenerated week 1, compared it to a week-1
workflow and passed all week. Both are fixed on
`claude/nfl-greenfield-architecture-stsxmk` at f9148b0 — the workflow is
regenerated for week 2 and the test now derives the week from the schedule
snapshot instead of pinning it.

### What I need, and it is the whole request

**Get `.github/workflows/nfl-t90.yml` from f9148b0 onto the branch GitHub
schedules from** — the repository default branch. A scheduled workflow fires
from the default branch's copy, so a correct file on a feature branch changes
nothing about what runs tomorrow. I can commit it; I cannot merge it there.

The six windows it declares:

| window (UTC) | games |
|---|---|
| 2026-09-17 22:45 → 00:05 | DET@BUF (already passed) |
| **2026-09-20 15:30 → 16:50** | **8: CAR@ATL, CIN@HOU, CLE@TB, GB@NYJ, MIN@CHI, NO@BAL, PHI@TEN, PIT@NE** |
| **2026-09-20 18:35 → 19:55** | **2: JAX@DEN, LV@LAC** |
| **2026-09-20 18:55 → 20:15** | **3: MIA@SF, SEA@ARI, WAS@DAL** |
| **2026-09-20 22:50 → 00:10** | **1: IND@KC** |
| 2026-09-21 22:45 → 00:05 | 1: NYG@LA |

### What I verified before asking, so it is not a blind merge

The regeneration was diffed against the committed file over everything except
cron lines and their comments. The **only** other change is the two header
lines (invocation and schedule identity, SCHED-2a2924d4966fbd3d →
SCHED-5e2e890466c87284). The three D24-R0 safety steps and the capture-prod
pin — `CAPTURE_BRANCH: capture-prod` and the explicit checkout ref — all
survive. I checked those specifically because an earlier generator run had
deleted safety steps once.

### The fallback if the merge cannot happen in time

A manual capture of the official inactives page inside each window, attributed
to a game_id, is worth more than a missed window. The endpoint correction from
OUT-016 applies. If neither is possible, say so and I will record the windows
as closed unfilled rather than let them look covered.

### Not asked for

No parsing, no ingestion, no model change. The bytes and the merge, nothing
else.

---

## 2026-09-19 — OUT-027: three clubs' official injury reports are unfilled, and it costs a game and two halves

**ASSIGNED.** The appearance layer is behaving correctly; the gap is bytes.

### What I measured

The full Week-2 slate rehearsal (`nfl/research/sunday/SUNDAY_REHEARSAL_2026W2.json`)
shows the appearance layer refusing any club whose official injury report is
incomplete, on its own stated ground: *"a team with no filed report is NOT a
team with no injuries."*

| game | effect | players left with no appearance estimate and no projection |
|---|---|---|
| JAX @ DEN | `APPEARANCE_TEAM_DEFERRED` — JAX deferred, the layer ran on DEN only | 15 |
| MIN @ CHI | `APPEARANCE_TEAM_DEFERRED` — CHI deferred, the layer ran on MIN only | 12 |
| NYG @ LA | `INJURY_REPORT_INCOMPLETE` — **the whole game halts at appearance.** NYG has 7 rows and `report_status` is unfilled on every one | every non-QB player, both clubs |

Twelve of the fourteen Sunday games have both clubs covered. These three clubs
are the whole gap.

### What I need

For **JAX, CHI and NYG**, Week 2: the official injury report with
`report_status` populated — the practice-participation and game-status
designations as filed. Raw document, nothing parsed, with its retrieval
instant.

If the league genuinely did not publish one for a club, **say that**, because
"not published" and "we did not fetch it" are different facts and the layer
should record the first rather than continue to wait on the second.

### Why I cannot clear it myself

No egress. The standing `EGRESS_DENIED` declaration in
`nfl/STATE_DECLARATIONS.md` applies. The endpoint correction from OUT-016
applies to whatever is fetched.

### What it unblocks, stated narrowly

Non-QB coverage for those three clubs in a rehearsal. **It does not unblock a
board** — `artifact_sealing` refuses every game of the season on a separate
and unrelated cause (no 2026 denominator panel, SUN-5), so a filled report
buys coverage in the simulation, not a forecast.

### Not asked for

No parsing, no ingestion, no interpretation of a designation. The documents.

---

## 2026-09-19 — OUT-028 (informational): no market snapshot exists for tomorrow, and none is needed yet

Recording this so it is not mistaken for an oversight.

`hardrock_market_snapshot` holds exactly **one** capture: 166 quotes,
retrieved 2026-09-13T18:13:12Z, marked `immutable`, `never_refresh`,
`never_restamp`, `role: DOWNSTREAM_COMPARATOR_ONLY`. There are no prices for
the Week-2 Sunday slate.

**I am not requesting any.** The directive's own ordering is that
model-vs-market comparison happens only after forecast sealing, and sealing
refuses every game. Prices fetched tonight would have nothing to compare
against, and a snapshot taken now would age before it could be used.

When SUN-5 clears and a board seals, the request becomes real. Until then this
is a BLOCKED item whose blocker is upstream and internal, and it should not be
counted against the networked agent.

Sportsbook prices remain evaluation data. They never become predictive inputs.

---

## 2026-09-19 — OUT-029: **OWNER DECISION.** I changed a value your ruling froze

Escalating rather than deciding, because this changes a rule you set.

### What I did and what it broke

To give tomorrow's slate T-90 capture windows (OUT-026), I regenerated
`.github/workflows/nfl-t90.yml` for week 2. That changed its schedule identity:

    SCHED-2a2924d4966fbd3d  ->  SCHED-5e2e890466c87284

`nfl/tests/test_non_g0a_isolation.py:38` pins the first value with the comment
**"The accepted, repaired G0A workflow. Frozen by owner ruling until the
event."** The window it guards — 2026-09-09 22:50Z — carries the outstanding
G0A `inactives` obligation, described in that file as *"the single item
standing between G0A 11/12 and 12/12."*

Five checks across three modules now fail, correctly:

- `test_non_g0a_isolation`: the frozen identity is gone (×2)
- `test_capture_obligations`: no cron fires inside the DEN@KC T-90 window
- `test_capture_obligations`: no cron covers the 2026-09-13 Sunday slate

### The conflict is structural, and worth seeing clearly

`nfl-t90.yml` is doing two jobs at once: it is the **live scheduler** and it
is the **frozen record of what was scheduled for week 1**. Those roles are
compatible for exactly one week. A second week makes them contradictory: you
cannot schedule tomorrow and preserve last week's schedule in the same sixteen
cron lines.

### Why I kept the change rather than reverting, and why it is reversible

The week-1 window closed eleven days ago. No arrangement of cron entries
reopens it, so reverting recovers nothing — it only removes tomorrow's
windows, and tomorrow's inactives cannot be reconstructed after T-90 either.
So one side of the trade is unrecoverable-and-future, the other is
already-lost-and-past.

Reverting is one `git revert f9148b0` if you disagree. **I have not touched
the frozen constant and I have not edited any of the five checks.** They are
red, and they are red for the right reason — a frozen value moved. Making them
green would be the defect.

### What I need

1. Does the freeze survive its event? It says "until the event", and the event
   has passed.
2. If the record matters independently of the scheduler — and I think it does —
   the week-1 schedule should be preserved as its own artifact so the live
   workflow can advance each week without breaking a freeze. I have not built
   that, because the shape of it is your call, not mine.

Queued as SUN-7 with the same content.

### Not asked for

No change to the G0A accounting, no discharge of the outstanding obligation,
and no edit to the tests.

---

## 2026-09-20 — OUT-030: the DraftKings Classic contest game set, and one player we cannot identify

Two small asks against the owner-supplied Week-2 salary file
(sha256 `c143c94f…b28b2bec`, 537 rows, preserved at
`nfl/vintage/dk_salaries.c143c94f152a7d6b.csv.gz`).

### 1. The contest game set — blocks main-slate eligibility

The file holds **all 32 clubs and all 16 Week-2 games**. Which of them the DK
Classic main slate covers is a fact about a contest, not about this file, so
`DK_WEEK2_MAIN_SLATE_ELIGIBLE_UNIVERSE` is `DEFERRED
[DK_MAIN_SLATE_GAME_SET_NOT_SUPPLIED]` rather than guessed. I did not fall
back on "the Sunday 1pm and 4pm games": that is a convention about how slates
are usually built, and the directive says to leave eligibility unresolved
rather than infer it.

**What I need:** the game list of the specific DK Classic main-slate contest —
away/home pairs, nothing else.

One game is already excluded without it, on the clock rather than on any DK
rule: **BUF–DET (44 rows)** kicked off 2026-09-18T00:15Z and is played.

### 2. `Ed Williams`, JAC, WR, $3,000 — unmatched

One of 537 rows does not join to a canonical identity. No `Ed Williams` exists
in any club in the 2026 week-2 roster capture (8 vintages, 2,527 distinct
players). Jacksonville carries `C.J. Williams` (WR) and `Wesley Williams` (DL);
neither is Ed.

**Not guessed** — there is no edit distance anywhere in this package, by
design. Either DK lists a player our roster vintage does not carry (a practice
squad or a very recent signing, consistent with the near-minimum salary), or a
name is wrong on one side.

**What I need:** confirmation of who this is, or that DK has him wrong.

### 3. Still outstanding from OUT-025, and this file does not touch it

The DK **Classic** site contract. `site_rules.py` holds
`DRAFTKINGS_SHOWDOWN` and `FANDUEL_SINGLE_GAME` and no Classic entry at all —
no salary cap, no roster slots, no FLEX rule, no minimum-teams rule. A salary
file is not a contract, and lineup legality cannot be certified from one.

Note the harder half is not a bytes problem: a Classic lineup must field a
DST and the engine produces no team-defence outputs at all, so all 32 DSTs in
this file are `DK_ELIGIBLE_MODEL_UNSUPPORTED`.

### Not asked for

No projections, no ownership, no contest results, no optimizer settings. The
file's own projection columns are dropped at parse time and are not authorized
as predictive inputs.

---

## OUT-031 — the Early Only projection audit's first version understated the blocker, and the correction changes the plan

**Raised:** 2026-09-20, ~05:00Z. **Assignment:** informational to the owner;
DK-3 and DK-4 are mine and need no one else.

I reported earlier tonight that 229 of the 256 Early Only players have readable
distributions from runs that refused at `artifact_sealing`, 13.5 hours stale.
Both statements are true and I am not withdrawing them. They were not the whole
disqualifier and I should have read the runs' own status files before writing.

Every one of those 15 runs carries `dry_run: true` and
`prospective_eligible: false`. That is structural: `run_slate.py` is the only
slate driver in the repository, it opens "REHEARSAL ONLY", and it passes
`dry_run=True` in the call. The reason sits one line above
(`run_slate.py:96`) — it satisfies `capture_validation` with a source set of
one entry whose sha256 is `'b' * 64`.

And `capture_validation` accepts it, because it iterates the set it is handed
and has no required-source check.

**Said precisely, because two things are easy to conflate here.** The football
layers below that stage read real captures through `vintage_selector`, with
real capture ids — that is how the 13.5-hour figure was measurable. The numbers
rest on real evidence. What rests on a placeholder is the stage that certifies
the inputs. A number computed from real data with no valid provenance record is
exactly the state we are in.

**What this changes.** My answer to "smallest step to a preliminary board
tonight" was: emit the refused run's output as `PROVISIONAL_UNSEALED`. I am
withdrawing that. Those numbers' input validation passed on a placeholder, and
no label repairs that. The smallest honest step is DK-4 — build a fixture
assembler that reads the vintage manifest and emits true source hashes — and it
does not produce a board tonight either, because sealing still refuses on the
2026 denominator panel (SUN-5) behind it.

**So there is no honest preliminary Early Only board for the 1:00 PM ET lock.**
The deadline does not change that and I am not routing around it.

Recorded as DK-3 (`CRITICAL_CORRECTNESS`) and DK-4 (`PRODUCTION_BLOCKER`) in
`nfl/WORK_QUEUE.md`, characterised by
`nfl/tests/test_capture_validation_provenance.py` (8 checks, all passing
against the defect as it stands), and amended into
`nfl/dfs/salaries/DK_EARLY_ONLY_PROJECTION_AUDIT.{json,md}`.

**Nothing requested of the network agent by this item.** OUT-025 (the DK
Classic contract) and OUT-027 (the CHI injury report) are unchanged and still
outstanding.

---

## OUT-032 — three byte requests that decide the 1 PM Early Only slate

**Raised:** 2026-09-20, ~08:10Z. Lock 17:00Z. **Assignment:** network agent.
All three are refreshes or captures of sources ALREADY REGISTERED. None is a
new source and none needs a decision.

### 1. `pbp_participation` for 2026 week 1 — THE ONE THAT MATTERS

This is the single named missing input behind the entire non-QB chain.
`participation_prior` refuses `PARTICIPATION_HISTORY_STALE`, which propagates
to appearance, participation, targets_carries, conversion and td_layer, and the
board therefore carries **no receiving layer and no per-player rushing layer at
all** — 8 QB rows and 2 kicker rows per game, and nothing for RB, WR or TE.
Seven of the nine DraftKings Classic roster slots have no modelled player.

`offense_players`, `offense_personnel`, `defense_players` and `n_offense` are
all absent from the play-by-play — checked, not assumed — so per-play on-field
presence exists only in `pbp_participation`. `panel_2026w1.py` can approximate
`pass_snaps` without it and says of itself that the approximation is
"systematically wrong for exactly the players it matters for".

**Exactly what I need:** `pbp_participation` for season 2026, week 1.

### 2. `snap_counts_2026` refreshed — one game short

The held capture (`4da350a50d0bb39b`, first retrieved 2026-09-14T18:33:36Z)
carries **15 of 16 games and 30 of 32 clubs**. Missing: `2026_01_DEN_KC`. That
one absence is why `denom_panel`'s completeness and coverage properties cannot
be established, which is why its `declared_blocked` stands.

This is a STALE WATCH, not a missing source: `snap_counts` is registered,
REACHABLE, and `watch_only=True`, so the vintage capture path skips it by
design (602 manifest rows, all `NOT_APPLICABLE[WATCH_ONLY_SOURCE_NOT_CAPTURED_
HERE]`).

**Exactly what I need:** a `snap_counts_2026` capture taken after
`2026_01_DEN_KC` was finalised.

### 3. Official inactives for the eight 1 PM games

PHI@TEN, PIT@NE, MIN@CHI, CAR@ATL, GB@NYJ, NO@BAL, CIN@HOU, CLE@TB. Newest
`official_inactives` PASS is `20260917T234100Z`, Thursday's DET@BUF. Publish
around T-90, ~15:30Z.

**Requirements, unchanged:** authoritative NFL/club evidence, retrieval clock,
publication clock where available, both teams, raw bytes preserved, and no
ACTIVE inferred from omission.

### What I am NOT asking for

No projections. No ownership. No DST ratings. No sportsbook data — the Hard
Rock board delivered earlier today is a comparator and is not to be joined to
anything until a sealed board exists.

### What does not unblock even with all three

`denom_panel` and `team_volume_history` would still need the panel rebuilt and
the `declared_blocked` lifted, and lifting it is a governance decision with a
stated precondition. And CS1 and the 2026 week-1 panel are candidate
components not present in R8, the accepted baseline; moving them in is an owner
ruling about a frozen specification. Neither is a thing to decide against a
clock, and I am not proposing either today.


## 2026-09-21T23:24Z — NYG@LAR official inactives verification (ASSIGNED, not blocked)

**Needed before kickoff 2026-09-22T00:15:00Z.** I have no egress: nfl.com,
therams.com and giants.com all return connection code 000 from this container,
tested at 23:20Z. This is assigned to the network-capable agent, not blocked
for the project.

**Request.** Both clubs' COMPLETE official inactive lists for `2026_02_NYG_LA`,
with, for each source: the exact URL, the raw bytes, the retrieval timestamp,
and the publication timestamp where the page exposes one.

Sources, in preference order:
1. `https://www.nfl.com/news/` weekly inactives article for week 2.
2. Club posts: `https://www.giants.com/news/`, `https://www.therams.com/news/`.
3. Gamebook after the game, for reconciliation only.

**What I am working from meanwhile, and at what tier.** An owner-supplied
screenshot, recorded as `OWNER_SUPPLIED_SCREENSHOT` in
`nfl/research/showdown_fixture/OWNER_INACTIVES_NYG_LAR_2026W2.json`. It lists
13 names; all 13 resolved to gsis_ids by declared suffix-strip plus exact
surname, club and first initial, 0 ambiguous. It is NOT presented as an
official capture and carries no URL, publisher timestamp or content hash.

**Specifically to confirm or refute:** Rams — Puka Nacua, Jordan Whittington,
CJ Daniels, Ty Simpson, Kamren Kinchens, Bill Murray. Giants — Thomas
Fidone II, Darius Alexander, Deonte Banks, J.C. Davis, Bobby Jamison-Travis,
Micah McFadden, Jason Pinnock.

**And the completeness question, which matters more than any single name.**
A list that omits a player is not evidence that the player is active. I need
each club's list in full, with the count, so absence from the captured list is
distinguishable from absence from the club's list. No ACTIVE status will be
inferred from omission.

---

## REQUEST 2026-09-22 — PARTICIPATION AND PERSONNEL DATA FOR 2026 (GOVERNED, STANDING)

**Status: ASSIGNED, not blocked.** The work inside this repository is done;
what is missing is bytes from outside it. Registered in code as
`nfl.production.review.evidence.UNAVAILABLE_SOURCES`, so every player dossier
on every slate already discloses the gap by name rather than approximating it.

**What is unavailable and why.** `nflverse pbp_participation` returns 404 for
the 2026 season, and the PFR snap-count file carries `offense_snaps` /
`offense_pct` / `st_snaps` / `st_pct` with no pass-versus-run split. Measured:
zero participation columns present for 2026.

**Six axes needed, in priority order.**

1. **Routes run**, per player per game. This is the single highest-value item.
   Routes are the correct denominator for a receiving role; raw offensive
   snaps are not, and a tight end who blocks on 60% of his snaps is
   indistinguishable from one who runs routes on 90% under the data we have.
2. **Routes per dropback**, or enough to compute it (team dropbacks per game
   are already available, so routes alone would suffice).
3. **Pass-blocking snaps** per player per game.
4. **Run-blocking snaps** per player per game.
5. **Personnel packages** — 11 / 12 / 13 / 21 usage rates by team and by
   player.
6. **Alignment** — slot versus outside versus inline.

**Requirements, because a source that cannot be point-in-time cannot be used.**

- Every row must carry a **publication timestamp**, not just a game date. A
  feed we cannot prove was published before kickoff cannot enter a pregame
  projection and will be refused by `chronology.certify`.
- **Per player per game**, not season aggregates. A season rate computed after
  week 6 leaks weeks 2 through 6 into a week-2 forecast.
- Coverage from **2026 week 1 forward**, and for whatever prior seasons the
  same source can supply on the same schema.
- A stable **player identifier** that joins to `gsis_id` without edit-distance
  matching. If the source keys on another id, send the crosswalk.

**Candidate sources to try, in the order we think most likely.** nflverse
participation for a season that does resolve, to confirm the schema; PFF or
SIS if either is licensable; the NFL's own Next Gen Stats endpoints; ESPN
play-level participation.

**What happens until it arrives, and what must not.** TE and WR dossiers
disclose the evidence ceiling on every slate: 21 receivers on
2026_02_NYG_LA carry `RECEIVING_ROLE_RESTS_ON_RAW_SNAPS_ONLY`. That is a
WARNING and does not stop a slate, which is the right disposition for an
optional source being absent.

**But the contradiction blocks.** If the projection model ever acts as though
one of these axes was measured while it is UNAVAILABLE, that is
`UNAVAILABLE_EVIDENCE_CLAIMED_AS_MEASURED` and it BLOCKS publication. An
absent source is a disclosed limitation; a claim resting on an absent source
is a false statement about the evidence.

**Not to be worked around.** No synthesis of 2026 route or personnel data from
snaps, from prior seasons, or from any model. The axes stay UNAVAILABLE until
real point-in-time bytes exist.

---

## URGENT 2026-09-22 — WEEK 2 PLAY-BY-PLAY BLOCKS THE ENTIRE WEEK 3 SLATE

**This is the single highest-priority external dependency and it is on the
Thursday critical path.**

Measured at cut 2026-09-22T12:00Z:

| source | weeks present | needed for a week-3 forecast |
|---|---|---|
| `usage_vintage` play-by-play 2026 | **[1] only** | weeks 1 and 2 |
| PFR snap counts 2026 | [1, 2] | weeks 1 and 2 |

The two current-season sources are at **different freshness**. Snaps already
carry week 2; play-by-play does not.

**Consequence, and it is not a soft one.** `current_season_evidence.assert_fresh`
refuses a week-3 forecast with `CURRENT_SEASON_INPUT_STALE`, because the newest
usage week available is 1 and a week-3 forecast needs week 2. That is the gate
working as designed — it will not let a week-3 slate publish off week-1
opportunity — and it means **no Week 3 projection can be produced until week-2
play-by-play is captured.**

**What is needed:** the 2026 week-2 play-by-play, all 16 games, into the
governed vintage store, with a retrieval clock. The same source and shape as
`pbp_2026.b69f55a172965e16.csv.gz`, which carried week 1 across all 32 clubs.

**Deadline:** before Thursday 2026-09-24. The Sunday main slate (2026-09-27,
16 games) is the acceptance target and cannot be researched without it.

**What is NOT needed:** nothing is to be synthesised, back-filled from snaps,
or inferred. Snap counts are not usage. A week-3 forecast built on week-1
opportunity is exactly what the repair this week was for.

**Also still open, from the 2026-09-22 request above:** routes, routes per
dropback, pass/run blocking split, personnel packages, alignment. Those are
WARNING-level and do not block a slate. Week-2 play-by-play is BLOCKING.

---

## 2026-09-22 — DK IDENTITY CROSSWALK NEEDED (not blocking, but on the Sunday path)

Measured today while wiring the Classic optimizer to real DraftKings files.

**What works.** `nfl/dfs/classic/dk_identity.py` parses DraftKings' own salary
export, including the player table **embedded to the right of the entry rows**
(header at column 14 in the week-2 file). It reads 409 players, every position
recognised, no duplicate DK ids, and `Roster Position` confirms DK's own FLEX
eligibility. DraftKings' file is the only authority on what position DK will
accept a player at, and the board's modelled ROOM is not that: a pass-catching
back sits in the targets room and is an RB on DraftKings.

**What does not.** There is no `gsis_id` <-> `dk_id` crosswalk. Resolving by
EXACT (name, team) across two different DK files resolved only **232 of 393**
non-DST rows -- 59% -- and the misses include Ja'Marr Chase, Nico Collins, Zay
Flowers and Josh Jacobs. Different DK exports spell names and team context
differently, and **no edit-distance matching is permitted**, correctly.

**What is needed.** A durable `dk_id` -> `gsis_id` crosswalk, built once and
maintained, rather than re-derived by name each week. Either:

- a source that carries both ids, or
- a one-time reviewed mapping keyed on DK id, which then persists because DK
  ids are stable for a player across weeks.

**Also measured: DST carries no gsis_id at all** -- 16 of 16 defences in this
file. They are not modelled players, have no dossier, and cannot come through
the player board. They enter the DFS pool from the DK file keyed on DK id, and
`dk_identity.crosswalk` separates and names them so their absence from the
board is an expected state rather than a defect.

**Consequence if unresolved:** the CSV export REFUSES with `DK_ID_MISSING`
rather than writing a blank DraftKings would reject or mis-match. So this
fails safe. But 41% of the pool being unrosterable is not a Sunday-ready state.

**Still the hard blocker, unchanged:** `WEEK2_USAGE_CAPTURE_REQUIRED`. See the
URGENT entry above. Verified again at cut 2026-09-22T23:00Z: usage_vintage
sees week [1] only; a week-3 forecast refuses `CURRENT_SEASON_INPUT_STALE` and
team volume refuses `TEAM_VOLUME_STALE`.

---

## 2026-09-24 — ATL @ GB official game-day inactives: content-bearing artifact

**Requested by** Claude Code (no network) · **For** the networked agent
**Game** `2026_03_ATL_GB` · kickoff `2026-09-25T00:15:00Z`
**Status** BLOCKED FOR ME, ASSIGNED TO YOU

### Why this is being asked

`https://www.nfl.com/inactives/` is captured on every pass and has **never
returned the inactive list**. Measured across the whole archive at capture-prod
`b970749`:

- 382 captures in state PASS
- `n_bytes` min 366,780 / median 403,809 / max 419,516 — a 14% spread
- **zero captures more than 15% above median**, so no capture ever carried the
  ~90 extra names a real list would add
- the largest capture in the archive (`20260908T163934Z`, 419,516 bytes) still
  contains the literal string `check back soon`
- six captures parsed with `nfl/production/nonqb/inactives.py`
  (`official-inactives-1`), including four spanning Sunday 2026-09-13 from
  16:29 to 17:05 UTC — straddling the ~11:30 ET publication window for 1pm
  games. All six: `DEFERRED / INACTIVES_PAGE_EMPTY_STATE`.
- the page carries `application/json` payloads but no `__NEXT_DATA__`, no React
  or Angular markers, so the list is very likely fetched by a request the
  capture never makes

The parser is not the defect. **The bytes being collected cannot contain the
answer**, and 382 PASS rows have been recording a successful fetch of a page
with no content in it.

### What is needed

ONE actual content-bearing official artifact for ATL/GB game-day inactives,
when it exists. Priority order:

1. an NFL official game- or week-specific inactives article / game-specific
   NFL content
2. an official Atlanta Falcons publication
3. an official Green Bay Packers publication

### Preserve, for any candidate

source URL · publisher · publication timestamp if present · retrieval
timestamp UTC · raw bytes · SHA-256 · game/team attribution · visible inactive
names · content type · whether the artifact is static/content-bearing versus a
client-rendered shell.

### Acceptance test

The raw preserved bytes must themselves contain enough content to identify the
inactive players for ATL and GB **without inference**.

- HTTP 200 / capture PASS is **not** evidence unless the returned bytes
  actually contain the list. That is precisely the failure being reported.
- Do not infer ACTIVE from omission.
- Do not convert an injury designation such as OUT into
  `OFFICIAL_GAMEDAY_INACTIVE`. They are different claims from different
  authorities, and the availability feed ranks them differently on purpose.

### If nothing qualifies

Return `NO_VERIFIED_OFFICIAL_INACTIVES_ARTIFACT` with the sources checked and
their timestamps. That is a real result and is preferred over a plausible one.

### Scope

Return the artifact so the **existing** parser can be tested against those
exact bytes before any endpoint or parser change is proposed. Do not redesign
the capture system. Do not modify governance, NFL-1 authorization, V2 status,
or capture-routing policy.

**The pre-inactive forecast proceeds independently and is not waiting on this.**

### CORRECTION 2026-09-24 — the request is now specific, and my earlier claim was wrong

An earlier version of this entry said no source in this repository could
supply official inactives. **That was wrong** and it is retracted. I searched
the preserved article HTML for the string `Inactives:` (with a colon), found
none, and reported absence. The article does not use that string; the lists
were in the bytes throughout. A probe that finds nothing is evidence about the
probe until shown otherwise.

**The carrier is known and is already proven in our own capture history.**
`https://www.nfl.com/news/inactive-reports-sunday-week-1-2026-nfl-season`
(captured 2026-09-13T16:00:17Z, 889,811 bytes) is server-rendered and contains
the full official lists as `<h3>TEAM</h3><ul><li>POS Name</li>…` per game.

So this request is no longer "find us something". It is:

> **Retrieve the NFL.com Week 3 Thursday-night inactives article for
> ATL @ GB**, and preserve its raw bytes.

Three URL shapes have each worked before and any of them is acceptable:

1. Weekly article — `/news/inactive-reports-sunday-week-3-2026-nfl-season`
   (a Thursday-night equivalent is the likely name for this game).
2. Single-game article — e.g.
   `/news/australia-game-inactives-san-francisco-49ers-at-los-angeles-rams`.
3. Operator plain-text relay, as delivered for Week 2 TNF (DET @ BUF) at
   `operator-relay://official_inactives_delivery_2026-09-17T2351Z`.

**What is dead, so please do not spend time on it:**

- `https://www.nfl.com/inactives/` — the landing page. 363 of 367 preserved
  blobs are an explicit empty-state page reading *"Please check back soon for
  NFL Inactive Reports for this Season"*, every one recorded as a capture
  PASS. HTTP 200 here is not evidence.
- The ESPN injuries JSON — closed status vocabulary (`Active` 585,
  `Questionable` 161, `Injured Reserve` 25, `Out` 22, `Doubtful` 7) with zero
  inactive-bearing values. `Out` is an injury designation and must not be
  converted; `Active` must not be read as confirmation a player will dress.

**The parser is already built and tested against real bytes of exactly these
shapes** — `nfl/truth/official_inactives_parser.py`, 26 checks passing,
including the whole 367-blob population sweep. It refuses the empty-state page
by name and refuses to attribute a game unless both teams are present. Nothing
further is needed from us but the document itself.

Full write-up: `nfl/truth/findings/2026-09-24_OFFICIAL_INACTIVES_CARRIER.md`.

Acceptance test is unchanged: the preserved raw bytes must themselves identify
the inactive players for ATL and GB without inference.
`NO_VERIFIED_OFFICIAL_INACTIVES_ARTIFACT` is a real result and is preferred
over a plausible one. **The pre-inactive forecast proceeds independently and is
not waiting on this.**

## ESPN injuries endpoint — can the 25-per-club page cap be lifted?

**Raised 2026-09-24. Small, bounded, and worth a single request.**

Measured offline over the entire preserved history: 648 captures x 32 clubs =
**20,736 club entries, every one carrying exactly 25 injury items.** Never 24,
never 26. That is a page size, not a census. The response says
`"status": "success"` and carries no pagination metadata at all — no `count`,
`pageIndex`, `pageCount` or `next` — so a truncated answer arrives wearing the
word "success".

The cap is not spent on injured players. In one capture's 800 items, 585 (73%)
are `Active`. One club's 25 slots held 16 `Active`, 4 `Questionable`, 4
`Injured Reserve` and a single `Out`. A genuinely OUT player ordered past the
25th is invisible to us.

**The question:** does the endpoint honour a `limit`, `page`, `offset`, or
per-club query that returns the full list? Please try and report what the
bytes actually contain, not what the status field claims.

* If it does, this is a one-line capture change and a real gain in
  availability coverage.
* If it does not, ESPN is permanently a partial secondary source and we will
  document it as one. **That is a real answer and is preferred over a
  plausible one.**

Nothing downstream is broken by this: `availability_feed.states()` already
refuses to read absence as health. What we lose is coverage, not correctness.
Full write-up: `nfl/research/findings/2026-09-24_ESPN_FEED_TRUNCATED_AT_25.md`.

## BLOCKING TONIGHT — refreshed DK Showdown export for ATL @ GB

**Raised 2026-09-24 ~20:10Z. Contest locks 00:15Z.** Two of the owner's five
pre-lock priorities cannot be executed from inside this checkout, and neither
is a modelling problem — both need bytes we do not have.

### 1. A refreshed DraftKings ATL @ GB Showdown export

The export we hold was an owner upload captured **13:34:48Z** and it is
already provably stale against the live contest. `Pierre Strong Jr.` appears
in the live lobby with a Q flag and is **absent from all 958 rows** of that
file. He is GB, RB, gsis `00-0038098`, roster status **DEV** — which is what a
practice-squad elevation looks like.

Needed, per the owner, from the refreshed source directly and **not** by
inference:

* Pierre Strong: salary, team, roster position, contest eligibility, status
  flag, and whether he was added after 13:34Z.
* The exact DK identity row for the Captain the owner entered as
  **`B. Robinson`**. Atlanta rosters Bijan (CPT $17,700) and Brian (CPT
  $6,600). Salary arithmetic implies Bijan and the owner has explicitly
  ruled that out as a resolution method: *"Do not infer identity from salary
  arithmetic if the refreshed source can identify the player directly."*
  A contest export carries the player id; please return that row.
* The full refreshed slate so the playable universe can be rebuilt and diffed
  against the pinned one (adds, removes, salary moves, by name).

### 2. The official ATL @ GB inactives artifact

Unchanged from the request above, and now on a clock: the list publishes
around **22:45Z**, roughly 90 minutes before lock. The parser is built and
tested against real bytes of all three proven shapes, so nothing is needed
from us but the document. See
`nfl/research/findings/2026-09-24_OFFICIAL_INACTIVES_CARRIER.md` for the URL
family that works and the two dead ends.

### What proceeds without either

The research portfolio builder is being built now against the pinned universe
so it runs the moment refreshed data lands. It is explicitly labelled
`RESEARCH_DFS_PORTFOLIO_NOT_JOINT-WORLD_VALIDATED` and claims no lineup-level
win probability. **This request blocks the refresh and the rerun, not the
build.**


## REQUESTED 2026-09-25 04:15Z — authoritative ATL @ GB box score

The game is final (**ATL 35, GB 14**) and the day audit at
`nfl/research/audit/2026-09-25_DAY_AUDIT_ATL_GB.md` grades what can be verified.
Eight of the twenty-six players in the entered lineups still have **no verified
stat line**: MarShawn Lloyd, Tucker Kraft, Jahan Dotson, Kyle Pitts Sr., Chris
Brooks, J. Michael Sturdivant, Chris Blair, Jonnu Smith.

**Correcting how this class of request has been worded.** Previous items here
said the bytes "do not exist for us". That was untested. `WebSearch` is
reachable from this session and returned a consistent scoring summary from four
independent outlets. What is NOT reachable is any content-bearing page: ESPN,
Pro-Football-Reference, CBS, Fox, Yahoo, packers.com and site.api.espn.com all
return `EGRESS_BLOCKED` or a proxy 403 on CONNECT. So a **secondary relay** is
available to me and a **provenanced artifact** is not, and the governed pipeline
is correct to refuse the former.

**What is needed:** the full box score as bytes, with provenance — complete
passing, rushing, receiving and kicking lines for both clubs, plus the official
inactive list as published. Any one of the blocked hosts above will do.

**What it unblocks:** completing the portfolio grade from lower bounds to actual
scores, and the first real entry in the prospective grading ledger (C1) against
a forecast cut that was registered before kickoff (`CUT-e3a92fca9dbe8cb7`).

Not blocking anything else. The audit stands as written, labelled partial.

## 2026-09-25 — kicker outcome fields (DEF-061) — **WITHDRAWN, MY ERROR**

**Nothing is needed from you. Please ignore the request below; I have struck it
through rather than deleting it, because a withdrawn request is worth being able
to find.**

I asked for `xp_made`, `xp_att` and field-goal distance buckets. **We already
have all three.** Every player row in `POSTGAME_OUTCOME/OUTCOME.json` carries a
`kicking` sub-dict with `fg_made`, `fg_att`, `xp_made`, `xp_att` *and*
`fg_made_by_bucket`. `grade_portfolios.py` has been reading those exact fields
the whole time.

What I did wrong: I checked `nfl/postgame/actuals.py`'s `NUMERIC` tuple, which
is a **different loader** for the weekly stats CSV, and concluded the outcome
feed lacked the fields. The grader does not read that file.

Kickers now grade with exact actuals, and the numbers check by hand: Tyler Bass
5 extra points = 5.0 DK; Jake Bates one field goal from the 30s plus 4 extra
points = 7.0 DK.

A real defect did surface underneath, and it was fixed here, not by you:
neither kicker appears in `frozen_board_names.json`, so the name index could
not find them and they were graded against a **zero line** while the outcome
held their real ones. The outcome's rows carry `player_id`, so grading matches
by identity first now.

---

<details>
<summary>The withdrawn request, kept for the record</summary>

**Assigned, not blocked.** This needs bytes from outside the checkout, which is
yours; everything inside the repository is done.

`nfl/postgame/actuals.py` pulls `fg_made` and `fg_att` for a kicker and nothing
else. DK and FanDuel both score kickers 3 / 4 / 5 by field-goal distance plus 1
per extra point, so with neither `xp_made` nor distance detail, `score_kicker()`
charges every make at the under-40 rate and every extra point at zero. A kicker
with two field goals — one from 45 — and three extra points scores **6 against a
true 10**.

The asymmetry is the point: the pregame side is exact. `SL.assemble` already
reads `fgm`, `fga`, `xpm`, `xpa` and the distance buckets off the `kicking`
layer, so we project a kicker precisely and cannot score what he actually did.
Grading him from the fields that do exist would put a confident wrong actual
into the ledger and attribute the error to the model, so grading currently
enumerates kickers and marks their DK points `KICKER_ACTUALS_INSUFFICIENT`.

**What is needed, per player-game:**

- `xp_made` and `xp_att`
- field goals made and attempted **by distance bucket** — `FG<20`, `FG20s`,
  `FG30s`, `FG40s`, `FG50+` — or per-kick distances from which those derive
- the same identity key already used elsewhere (`gsis_id`), so this joins
  without a name match

Games needed first: **2026_03_ATL_GB** (the sealed run, ids `00-0025565` Folk
and `00-0040899` Smack), then any week whose board we intend to grade.

Until it arrives the named state stands and the gap stays countable. Please do
not stub it: a fabricated kicker actual is worse than an absent one, because it
enters the prospective ledger as evidence.


</details>

---

## 2026-09-27 — OUT-033: official inactives for today's nine 1 PM ET games

**Status: ASSIGNED, and time-boxed.** Kickoff is **2026-09-27T17:00Z**. The
publication window this repository models is 80 minutes wide from T−90, so
roughly **15:30Z–16:50Z today**. After 17:00Z the bytes are still worth having
for the record, but `inactives.sets()` will refuse them with
`INACTIVES_POST_KICKOFF` — a list retrieved at or after kickoff is not pregame
information about who would dress, and the module will not pretend otherwise.

**Why this is not blocked.** Nothing here is blocked for the project. I cannot
reach the publication (403 on every outbound request), and the parse, resolve
and propagate path is already built and tested locally against synthetic bytes.
What is needed is the bytes.

**The nine games**, as resolved from DraftKings' own entries export and frozen
in `nfl/dfs/salaries/DK_WEEK3_EARLY_BASELINE.json`:

| away | home |
|---|---|
| CAR | CLE |
| CIN | PIT |
| HOU | IND |
| KC | MIA |
| LAC | BUF |
| NE | JAX |
| NYJ | DET |
| SEA | WAS |
| TEN | NYG |

Eighteen clubs. `sets()` emits `POST_INACTIVES_COMPLETE` only when **both**
clubs of a game are represented, so a game is covered or it is not — half a
governed forecast is not a governed forecast.

**What to send, per game.** `inactives.store()` takes bytes, so please send the
raw document rather than a transcription:

- the **raw bytes** of the publication, unparsed and unedited;
- `retrieved_at` as an ISO-8601 UTC instant — this is load-bearing, not
  metadata: `sets()` refuses without a retrieval clock
  (`INACTIVES_NO_CLOCK`) and refuses a clock at or after kickoff;
- `source_url`;
- `published_at` and `http_status` if the response exposes them.

**Please do not** transcribe names into a list for me, do not fill a gap with a
plausible inactive, and do not send a page whose empty state reads as "no
inactives" — the module carries `INACTIVES_PAGE_EMPTY_STATE` and
`INACTIVES_EMPTY_DOCUMENT` precisely because an empty page is not an empty
inactive list. A fabricated inactive is worse than an absent one: it becomes
evidence.

**What I will do with it, and what I will not.** Resolve identity
deterministically against the roster vintage the forecast consumed; an ambiguous
name is a refusal, not a fuzzy match. Then record availability against the
frozen 457-row contest universe.

I will **not** be able to turn it into a projection today, and that is a
separate, already-declared problem: `feature_build` refuses every game of this
slate with `STAGE_DECLARED_UNIMPLEMENTED` (declared debt at
`SYSTEM_STATE.json .measured.work_queue.items[14]`, corroborated by scheduled
run `36257140735` refusing all 15 Week-3 games). So the inactives are being
requested to establish an **auditable availability record**, not to feed a board
that does not exist. Worth sending anyway: today's pregame bytes are
unrecoverable tomorrow, and this project has already had to write off a corpus
once.

**Six identities I could not resolve** are recorded UNMATCHED in the baseline
(§3). They are on DraftKings' contest export, so they are rosterable; our
failure to map them is our defect, not evidence they are not playing:

`44246968` RB Al-Jay Henderson NYJ · `44246912` RB Nick Singleton TEN ·
`44247126` WR Joshua Palmer BUF · `44247216` WR Mitch Tinsley HOU ·
`44247168` WR River Cracraft WAS · `44247446` TE Drew Ogletree IND

A canonical `gsis_id` for any of these would help. Note that the third-party
comparison file happens to carry two of them under short forms ("Josh Palmer",
"Andrew Ogletree") — **that is not a resolution and I have not used it as one.**
A third-party file may not enter the identity chain any more than it may enter a
projection.

### OUT-033 addendum, 2026-09-27 ~03:20Z — the automated capture cannot fire today

**Read this with OUT-033 above; it is why the request is by hand.**

`nfl-t90.yml` on `origin/main` carries 16 cron entries covering **September 9–15
only**. GitHub reads `schedule:` from the default branch, so the T−90 capture has
had no cron entry matching any game day for twelve days, and has none for today.
The window today's nine 1 PM ET games need is **2026-09-27 15:30Z–16:50Z**.

I regenerated the workflow on the engineering branch with the repository's own
generator (`gen_t90_schedule.py --season 2026 --week 3 --write`); it produces all
six week-3 windows including that one, and `test_t90_workflow.py` goes from 11
failing checks to 41 passed. Filed as DEF-086.

**I cannot deploy it.** It has to be on the default branch to be scheduled, and
pushing to `main` is outside what I am authorised to do. So:

1. **Today:** the inactives bytes have to come by hand, per OUT-033. Nothing
   automated will collect them.
2. **Then:** someone who can push to `main` needs to carry the regenerated
   `.github/workflows/nfl-t90.yml` across, or the same thing happens next week.

**Note for whoever investigates the wider capture stoppage.** The existing entry
above concluded the four workflows stopping after 2026-09-11 was an Actions- or
repository-level problem, and recorded that "`main` and the working branch carry
byte-identical `.github/workflows/`". That was true when written and is **no
longer true**. The stale cron on `main` is a *second, independent* reason no T−90
run can fire. Fixing the Actions-level cause alone would not produce a run, and
would look like the fix having failed.

---

## 2026-09-27 — OUT-034: `pbp_participation_2026`, the one input blocking every non-QB layer

**This is the blocker for today's board, and it is a capture, not a code change.**
Full trace in `nfl/research/audit/2026-09-27_FEATURE_BUILD_BLOCKER.md`.

**What has been believed, and is wrong.** The production path reports
`REFUSED feature_build: STAGE_DECLARED_UNIMPLEMENTED`. That names a bystander —
the orchestrator labels a refusal with the first stage that is not PASS or
NOT_APPLICABLE, and DEFERRED qualifies. The run's own `first_failure` says
`player_draws`, and `feature_build`'s DEFERRED halts nothing.

**The measured chain.** `player_draws` FAILs `DECLARED_DRAW_ARTIFACT_INCOMPLETE`
because the `receiving` and `rushing` layers are absent; they are absent because
the five non-QB stages returned `SLATE_FITS_UNAVAILABLE`; that is
`participation_prior` BLOCKED `PARTICIPATION_HISTORY_STALE` — *the newest
participation history is ordinal 202518 (2025 week 18) and the forecast is 2026
week 3*. The QB layer, capture validation, identity resolution, team environment
and joint reconciliation all **PASS**.

**Request: `pbp_participation_2026` for 2026 weeks 1 and 2**, and thereafter
weekly. This is the only source of **per-play on-field presence**. A
field-by-field audit already in the tree (`nfl/production/nonqb/panel_2026w1.py`)
established that six of the seven panel fields derive **exactly** from evidence we
already hold, and that `pass_snaps` is the single field that does not, because
`offense_players`, `offense_personnel`, `defense_players` and `n_offense` are all
absent from the play-by-play.

**Please do not substitute.** Snap counts are already here and are not the same
thing: `nfl/availability_raw/snap_counts_2026.271167b454534d6e.csv.gz` carries
1,492 rows for week 1 and 93 for week 2, and gives `offense_pct`, not per-play
presence. The approximation we already have —
`offense_snaps * (team_dropbacks / team_offense_plays)` — is fenced to the
separately identified candidate `V1_CANDIDATE_R9_W1P` and its own module says it
*"MUST NEVER BE FED TO"* the accepted `ewma_hl2` arm, which needs TRUE
`pass_snaps`.

**Also worth flagging: week-2 snap coverage looks thin.** 93 rows against week
1's 1,492 is roughly one club's worth, not a league week. If week 2 was captured
incompletely, that is a second gap and it will limit anything built from weeks 1–2
even once participation arrives.

**What this unblocks, and what it does not.** It unblocks the non-QB chain, hence
the `receiving` and `rushing` layers, hence the draw contract, hence a board. It
does **not** implement `feature_build`, which is separately and correctly recorded
as declared debt — `fx['features']` has no producer anywhere in production. It
also does not affect G0A item 1, whose root cause is EGRESS (`CONNECT
www.nfl.com:443 -> 403`, measured) and which the artifact says *"would still fail
with a perfect scheduler."*

### OUT-034 correction, 2026-09-27 — the ask is a RE-PROBE and a revived watch, not a capture

**I got the request wrong an hour ago and am correcting it before anyone acts on
it.** `nfl/INFORMATION_GAP_REGISTRY.json`'s `GAP-2026-PARTICIPATION` already
holds the measurement, and it changes what should be asked for:

> `pbp_participation` returned **404 at every one of its 12 probes**,
> 2026-09-08T13:28:42Z through 2026-09-15T06:37:05Z. … **THE WATCH HAS NOT RUN
> SINCE 2026-09-15T06:37:05Z**, so neither half of this sentence is current, and
> the horizon that would surface that is **two days**.

So `pbp_participation_2026` is not a dataset we have failed to capture. On twelve
consecutive probes over a week it **did not exist upstream**. Asking to "please
capture it" was the wrong ask.

**What is actually needed, in order:**

1. **Re-probe `pbp_participation_2026`.** The last observation is 12 days old
   against a stated 2-day horizon, so the 404 is formally not current. Its
   sibling is the precedent for why this matters: `snap_counts_2026` was 404 on
   2026-09-08 and **200 on 2026-09-10**, growing 93 → 187 → 1,397 rows. The
   registry says as much itself — the previous combined claim "both 404" was
   "true when written and is now HALF FALSE". If participation has started
   publishing, this whole blocker dissolves without anyone writing code.
2. **Revive the participation watch — this is already authorized as SUN-1, status
   QUEUED.** `nfl-availability.yml` last ran 2026-09-15T06:37:05Z. Line 130 is
   still `git push origin HEAD:main`, while the four capture workflows were moved
   to `capture-prod` twenty-two minutes after its last successful run. SUN-1's own
   wording: point it at the governed surface, and read the run history so
   "stopped" is distinguished from "failing at the push step". I cannot read that
   history from here.

**If the re-probe still returns 404**, then the conclusion is materially
different from anything in the queue and worth stating plainly: the accepted
`ewma_hl2` arm cannot run for 2026 **at all** until nflverse publishes
participation, because true `pass_snaps` has no other source. That is an external
data-availability fact — not a code task, not an owner ruling — and the only
routes would be to wait, to accept an estimator that does not need true
`pass_snaps`, or for the owner to authorise a candidate-identified board built on
the bounded approximation already in `panel_2026w1.py`.

**What we already hold and do not need:** `snap_counts_2026` is here and healthy
(1,492 rows week 1). It supplies `offense_pct`, and six of the seven panel fields
derive exactly from evidence in the tree. Only `pass_snaps` is missing. Please do
not send snap counts again as a substitute — the registry is explicit that these
two "are NOT one fact and must stop being recorded as one".

**One more thing worth a look while you are in the run history:** week-2
`snap_counts` is 93 rows against week 1's 1,492. Given the growth pattern above,
93 is plausibly just an early-week partial that never got re-fetched after the
watch died on 2026-09-15.

### OUT-034 second correction, 2026-09-27 15:10Z — the re-probe is ANSWERED, and the watch is alive

**Both halves of my previous request were based on a stale claim. `origin/main` has
the answer and I did not need network to read it.**

**1. The watch is NOT dead.** `origin/main` carries `NFL availability watch`
commits at `20260925T183106Z`, `20260926T063438Z`, `20260926T183149Z` and
**`20260927T063457Z` — this morning**. So the registry's "THE WATCH HAS NOT RUN
SINCE 2026-09-15T06:37:05Z", written 2026-09-19, is stale and now false. SUN-1's
premise needs revisiting: the watch runs and pushes to main. Whatever stopped it
between 09-15 and 09-25 has resolved on its own, or was never what it looked
like.

**2. The re-probe is answered, and the answer is negative.** From
`origin/main:nfl/availability_manifest.jsonl`:

| retrieved_at | source | status |
|---|---|---|
| 2026-09-26T06:34:38Z | pbp_participation | **404** |
| 2026-09-26T18:31:49Z | pbp_participation | **404** |
| **2026-09-27T06:34:57Z** | **pbp_participation** | **404** |
| 2026-09-27T06:34:57Z | snap_counts | 200, 3,086 rows |

`pbp_participation_2026` is **still 404 as of 8.5 hours ago**. So the blocker does
**not** dissolve, and the branch I flagged is the live one: **the accepted
`ewma_hl2` arm cannot run for 2026 until nflverse publishes participation**,
because true `pass_snaps` has no other source. External data availability, not a
code task and not a ruling.

**3. Week-2 snap coverage is COMPLETE, and my "93 rows" was stale.** Main's
freshest blob `snap_counts_2026.62419bd0b011368e.csv.gz` (uncompressed sha256
verified against its name) holds **week 1: 1,492 · week 2: 1,502 · week 3: 92**.
My local copy had 1,585 rows and I reported week 2 as "93 rows, probably a partial
never re-fetched". That was true of my checkout and false of the project. Please
disregard that flag.

**4. What the watch does NOT cover, which is today's actual gap.** It probes
exactly two sources, `pbp_participation` and `snap_counts`. It does **not** probe
`official_inactives`. So the inactives capture is a different mechanism — the one
DEF-086 established cannot fire, because `nfl-t90.yml` on `main` carries crons for
September 9–15 only. **No official inactives for today have arrived and none will
arrive automatically.** OUT-033 stands unchanged and is now the only route.

---

## OUT-035 — the nine official inactive lists. This is the whole of Phase 2 and it is yours, not blocked.

**Filed 2026-09-27T16:10:04Z by Claude Code. Priority: highest on the board today.**

The owner opened the resumed task with "Official inactives are now available." **They
are not available to me, and they are not in this repository.** I checked before
saying so rather than after:

| what I looked for | what I found |
|---|---|
| a 2026 week-3 game directory | only `2026_03_ATL_GB` (Thursday). None of the nine. |
| `*inactive*` anywhere in the tree | every capture is `2026_01_*`, plus two week-2 benchmark files |
| `2026-09-27` in any json/csv/html | four files, **all four written by me**: the gap registry and my own three DK artifacts |
| the one `NFL_OFFICIAL_INACTIVES.html` in the upload set | **Week 1.** 889,867 bytes, dated Sep 13, headline "NFL Week 1 inactives: Players ruled out for Sunday's 13 games", 86 occurrences of "Week 1" and zero of any September 27 date |

And the supplied research package says so itself, in its own words, in two places:
`**State:** PRE-INACTIVES`, and under Limitations, "official inactives were
unavailable at retrieval". Its `snapshot.type` is `PRE_INACTIVES` and its
`second_pass.trigger` is `official_inactives_release`. The trigger has not fired
for me.

**So Phase 2 is assigned, not blocked.** Per CLAUDE.md I am not permitted to call it
blocked without writing the request, and I am not permitted to route around it. I
have not stubbed it, not mocked it, and not promoted a single QUESTIONABLE to
ACTIVE. Everything else in the task ran; only this is parked.

### Exactly what I need

The official game-day inactive list for **all nine** Early Only games, kickoff
2026-09-27T17:00:00Z. Both clubs per game — one club is not a complete game, and
`ingest_inactives.py` already refuses a one-club capture.

```
CAR @ CLE    CIN @ PIT    HOU @ IND
KC  @ MIA    LAC @ BUF    NE  @ JAX
NYJ @ DET    SEA @ WAS    TEN @ NYG
```

Per game, and this is the shape `nfl/tools/ingest_inactives.py` already accepts, so
no new plumbing is needed:

- `--bytes` the **authoritative document itself**, saved unparsed. NFL.com
  `/inactives/` or the club's own release. The module's docstring is explicit that
  it "will not accept a reporter's summary, a sportsbook line, an inferred dress
  list, or a retrospective INA column", and I am not going to weaken that today.
- `--source-url`
- `--retrieved-at` in UTC
- `--published-at` where the document carries one
- `--game-id` in the `2026_03_AWAY_HOME` form

A single combined NFL.com inactives page covering all nine is fine and is one
fetch; per-club releases are equally fine. What I cannot use is a summary of them.

### The eleven branches that actually change football if you can only get some

Ranked by how much of the slate moves, from the internal observed layer rather than
from the external write-up:

1. **PIT Jaylen Warren** — with Dowdle already out this is the whole Pittsburgh
   backfield, and observed W1–2 is Warren 21 carries to Dowdle 15, a near-split, so
   there is no incumbent to promote.
2. **BUF DJ Moore + Keon Coleman** — joint, and the slate-high 50.0 total.
3. **CAR Jalen Coker + Xavier Legette** — Coker is 18 targets and 5 red-zone
   targets over two weeks, which is not a depth profile.
4. **PIT Michael Pittman** — DK lists him PIT; see the identity conflict below.
5. **NYJ Adonai Mitchell** — 15 targets, 360 air yards.
6. **TEN Tyjae Spears** — Pollard's ceiling depends on it.
7. **NYG Brian Burns** — the only one that moves a DST distribution rather than a
   skill player.
8. **NE Eli Raridon**, **MIA Jaylen Wright** (doubtful).

### Two things worth your attention while you are in there

**WITHDRAWN, same day, by measurement.** This paragraph originally claimed the
external `player_usage_evidence.csv` carried club assignments that *contradict* the DK
contest file, and listed six. **It does not, and I had not checked when I wrote it.**
I was relaying the research report's own self-flagged "mapping anomalies" as though I
had verified them against DK. Measured against the authoritative DK 457:
`Kenneth Walker III` KC 7400, `David Montgomery` HOU 6000, `Michael Pittman Jr.` PIT
4700, `Carnell Tate` TEN 5000, `Jadarian Price` SEA 5300, `Malachi Fields` NYG 4400 --
**every club and every salary matches**. Three sources agree and there was never
anything to reconcile. Please disregard; nothing is needed from you on it. Recorded
rather than deleted because this is the fifth time in two days that a claim in this
project was stale or unchecked rather than wrong-in-substance, and an unreal conflict
left standing costs the same attention as a real one.

**`pbp_participation_2026` was still 404 at 06:34:57Z today**, so routes remain
`UNKNOWN_SOURCE_UNAVAILABLE` and I have not estimated them from pass snaps. That is
OUT-033/OUT-034 and unchanged; noted here only so you do not re-derive it.

### What is already built and waiting

The comparator, the availability resolver and the redistribution layer all ran and
are committed. They are written against the evidence tier, not against a hardcoded
list, so the moment you deliver captures the POST state regenerates with
`CONFIRMED_INACTIVE` / `ACTIVE_NOT_ON_INACTIVE_LIST` filled in and the PRE→POST diff
becomes a real availability diff instead of the mostly-empty one it honestly is now.
Nothing is waiting on my side.

### OUT-035 addendum, 2026-09-27T16:16:22Z — the second pass arrived and it narrows the ask

The owner relayed the research thread's **POST_INACTIVES_SECOND_PASS**, snapshot
2026-09-27 12:04 ET. It changes what I need from you, so read this before acting on the
request above.

**What it resolved.** Fifteen reported inactives and eight reported actives, by name,
each with a quoted sentence and a cited URL. Houston's list is cited to
`houstontexans.com`, Dulin to `colts.com`, Mason Taylor to `newyorkjets.com`, Darnold
to `seahawks.com`. The rest is RotoWire's populated inactive lists.

**What it explicitly does not claim, in its own words:** "the other RotoWire inactive
lists should remain `REPORTED_HIGH_CONFIDENCE` rather than `CONFIRMED_OFFICIAL` until
matched to an NFL or team release." I have honoured that exactly. No player in the POST
artifact carries `CONFIRMED_INACTIVE`, because that status requires bytes and we hold
none.

**The gap that remains, and it is the one worth your time.** The source states the nine
lists are populated and relays the names that matter. It does **not** enumerate any
list in full. So of 457 DK rows, **23 resolve by name and roughly 420 stay
`UNKNOWN_NOT_RELAYED`**. I will not read "not mentioned" as "not on the list" -- that
activates 420 rows on silence, which is the same defect as reading missing as zero.

**So the revised ask, smaller than OUT-035 above:** the *complete* inactive list per
club, even as plain text, for the nine games. Names only is enough; I do not need the
HTML if bytes are hard. With complete lists, ~420 rows move from `UNKNOWN_NOT_RELAYED`
to `ACTIVE_NOT_ON_INACTIVE_LIST` in one run. With captured bytes they additionally
reach `CONFIRMED_INACTIVE` / `ACTIVE_NOT_ON_INACTIVE_LIST` at document tier, which is
what `ingest_inactives.py` was built for. Complete-lists-as-text is the high-value,
low-cost half; get that first.

**One thing you can drop.** The identity conflict in the original OUT-035 is withdrawn
above -- do not spend a fetch on it.

**One new small conflict, not worth a fetch on its own.** The second pass names
`Matthew McClain` as a predicted Jets starter. The DK universe has `Malik McClain`, NYJ
WR, 3000, and no Matthew. Probably a first-name slip, but I have not renamed him; he is
carried as a redistribution candidate with the conflict attached. If you are already
reading the Jets list, the name on it settles it.

## OUT-036 — WITHDRAWN 2026-09-28. The lines were already in this repository.

**Status: WITHDRAWN BY MEASUREMENT.** The request below is struck. It is left visible rather than
deleted because the mistake is more instructive than the request was.

I wrote "This repository holds no line history -- `nfl/research/postgame/` carries play-by-play
only". I checked one directory and declared a gap. `nfl/vintage/schedules.*.csv.gz` carries
**7,548 games over 1999-2026** with `spread_line`, `total_line`, `away_moneyline`,
`home_moneyline`, `over_odds`, `under_odds`, `temp`, `wind`, `roof`, `surface`, `away_rest`,
`home_rest`, `overtime`, both scores, and PFR/PFF/ESPN cross-reference ids.

Measured coverage of the two fields I said were absent:

| season | games | spread_line | total_line | temp/wind |
|---|---|---|---|---|
| 1999 | 259 | **1.00** | **1.00** | 0.76 |
| 2000 | 259 | **1.00** | **1.00** | 0.80 |
| 2012 | 267 | **1.00** | **1.00** | 0.72 |
| 2025 | 285 | **1.00** | **1.00** | 0.67 |
| 2026 | 272 | 0.24 | 0.24 | 0.07 |

Twenty-seven complete seasons of closing lines, one hundred per cent covered. The temp/wind gap is
not missing data: it is domes, and `roof` says which.

This is the exact failure the project briefing names -- marking something unavailable because it
was not in the first place looked, when the repository is not the whole world and in this case the
repository was not even fully searched. It cost a real capability: `proj_v1.team_volume()` currently
applies NO market scaling to play volume and says the coefficient "cannot be estimated here", which
is false. It can be estimated on 27 seasons, and now will be.

The original request follows, struck.

## ~~OUT-036 — historical closing lines, to estimate the volume/market relationship~~ (WITHDRAWN)

**Requested by:** Claude (no network). **Status:** OPEN. **Filed:** 2026-09-28.

V0 multiplied every club's plays, pass attempts, carries and targets by
`implied_total / league_mean_implied`. Buffalo at a 28.75 implied total therefore had its
measured 31.6 pass attempts per game lifted to 41.5 — an assertion that a club expected to
score 31 per cent more runs 31 per cent more plays. That is not how scoring more works: it
comes largely from efficiency, and a favoured club tends to run *more* and throw *less* as it
protects a lead, so even the sign of the effect on pass volume is not obvious.

V1 therefore applies **no market scaling to volume at all** (`scale = 1.0`), and lets the
market enter exactly once, where it is measured: the club touchdown pool, from a regression of
offensive touchdowns on club points over 2,689 club-games (`nfl/derived/TD_RATES.json`).

**What is needed to do better:** historical **pregame closing totals and spreads** joined to
historical games, 2021–2025, so the relationship between market expectation and each of
plays / dropbacks / pass attempts / rush attempts / red-zone plays can be estimated rather
than declared. Team-level per-game is sufficient; no player detail needed.

This repository holds no line history — `nfl/research/postgame/` carries play-by-play only —
so the coefficient cannot be estimated here. It is **not invented** in the meantime.

This is **assigned, not blocked**: V1 is complete and runs without it. The coefficient would
improve the volume layer; its absence does not stop anything.

## OUT-037 — the 2025 capture credits the Jets defence with ZERO interceptions

**Requested by:** Claude (no network). **Status:** OPEN. **Filed:** 2026-09-28.
**Severity:** a whole scoring term silently deleted from one club.

Measured in `nfl/research/postgame/pbp_2025.2f135887790a013f.csv.gz`, regular season:

* New York Jets defensive plays: **1,419**. Interceptions credited with `defteam == NYJ`: **0**.
* **31 of 32** clubs recorded interceptions. The next-lowest are TEN, DAL and SF on **six**.
* All **13** interceptions occurring in Jets games have `posteam == NYJ` — every one was thrown
  *by* the Jets, none caught by them. So opposing quarterbacks threw none against them all year.
* No interception row anywhere in the season has a blank `defteam`, so these are not
  misfiled-to-empty; they are absent.

Against the measured league rate of **0.75341** interceptions per club-game, the expectation over
the 19 club-weeks used is **14.3**, and P(observing zero) is **6.07e-07**. This is a defect in the
capture, not a property of the defence.

**Handled here, but only as a floor.** `dst_model.py` now runs a Poisson plausibility test on
every club-measure and substitutes the measured league rate when a zero is this improbable,
labelling the row `PROJECTED_WITH_LEAGUE_RATE_SUBSTITUTION`. It fires on exactly one of 192
club-measure combinations and correctly leaves safeties and blocked kicks alone, where a zero over
19 games is ordinary. A substituted league rate is still not the Jets' own rate.

**What is needed:** a re-pull of 2025 play-by-play, verified by the check that every club records
at least one defensive interception, and a reason why this capture lost them. If other event
classes are affected the same way for other clubs the substitution is masking more than it says.

This is **assigned, not blocked**: DST projects for all 18 clubs today.

## OUT-038 — historical weekly rosters, 2021-2025

**Requested by:** Claude (no network). **Status:** OPEN. **Filed:** 2026-09-28.
**Severity:** caused survivorship bias in the forward-chained evaluation harness.

Every roster blob in `nfl/vintage/weekly_rosters.*` is **2026** — 11 files, 60,331 rows, one
season. So `player_prior.position_index()` can only classify players who are on a 2026 roster, and
any historical evaluation silently restricted itself to **players who survived to 2026**:

| season | players in panel | classifiable as QB/RB/WR/TE |
|---|---|---|
| 2021 | 703 | **208** |
| 2022 | 675 | 284 |
| 2023 | 645 | 356 |
| 2024 | 648 | 442 |
| 2025 | 652 | 528 |

That is not merely a smaller sample. Club totals are counted from the play rows and include
everybody, so every unclassified player's volume was redistributed among the survivors. It
inflated the projected level by **67 per cent** in 2021-2022, and it selects for better players,
who are the ones still employed. It reversed the sign of a real finding: the multi-season prior
appeared to LOSE to a current-season-only baseline on role-transition weeks, and after the bias was
removed it WINS there.

**Handled here, but only as a floor.** `forward_chain.positions_for_chain()` infers position from
usage where the roster is silent. QB and RB are reliable from usage. **WR and TE are not
distinguishable from usage**, so an inferred receiver is assigned WR, which misplaces some tight
ends into the receiver group split and depth curve. Inferred players are included in allocation
and excluded from every scored metric.

**What is needed:** weekly rosters for 2021-2025 with `season`, `week`, `gsis_id`, `position`,
`team`. Position per player-season is the minimum; per player-week is better.

This is **assigned, not blocked**: the chain runs today with inferred positions.

## OUT-039 — player-game and play-by-play for 2000-2020 (the warehouse's one real gap)

**Requested by:** Claude (no network). **Status:** OPEN. **Filed:** 2026-09-28.
**Priority:** this is the critical-path input for the forward-chained calibration the owner ordered
(train ≤2018 → test 2019, and so on back). Everything else in the warehouse is built.

### What is already here, so this request is narrow

| table | coverage held | rows |
|---|---|---|
| **team-game: market + environment** | **2000-2026 complete** | 13,982 club-games |
| team-game: play detail | 2021-2026 only | 2,782 club-games |
| **player-game** | **2021-2026 only** | 27,577 player-games |
| role history | 2021-2026 only | 17,721 player-club-weeks |

The coverage ledger (`nfl/warehouse/COVERAGE_LEDGER.json`, 945 statistic-seasons) reads **384
AVAILABLE, 531 UNKNOWN_PENDING_ACQUISITION, 30 NOT_AVAILABLE_FOR_ERA**. Nearly all of the 531 are
one thing: **no play-by-play or player-game data before 2021.**

### What is needed

Season-level play-by-play, **2000 through 2020**, in the same schema as the captures already here
(`nfl/research/postgame/pbp_YYYY.<digest>.csv.gz` plus a `.provenance.json` sidecar carrying
`sha256`, `source_url`, `retrieved_at`, `games`). nflverse/nflfastR release assets are the obvious
route and match the existing schema exactly, so nothing downstream needs changing — `sources.py`
will pick them up by pattern and verify the digest.

Required columns are those the current builders read: `game_id`, `season_type`, `week`, `posteam`,
`defteam`, `play_type`, `passer_player_id`, `rusher_player_id`, `receiver_player_id`,
`pass_attempt`, `rush_attempt`, `complete_pass`, `passing_yards`, `rushing_yards`,
`receiving_yards`, `air_yards`, `pass_touchdown`, `rush_touchdown`, `interception`, `sack`,
`qb_scramble`, `fumble_lost`, `fumbled_1_player_id`, `fumbled_1_team`, `fumble_recovery_1_team`,
`return_touchdown`, `td_team`, `safety`, `punt_blocked`, `yardline_100`, `down`, `qtr`,
`score_differential`, `game_seconds_remaining`, `drive`, `two_point_attempt`,
`two_point_conv_result`, `home_score`, `away_score`, `home_team`, `away_team`.

**Secondary, and separable:** weekly rosters for 2000-2025 with `season`, `week`, `gsis_id`,
`position`, `team` — this is OUT-038, still open, and it is what forces the chain to infer position
from usage today.

### What must NOT happen

Do not synthesise, interpolate or zero-fill any of it. A season that does not arrive stays
`UNKNOWN_PENDING_ACQUISITION` and the warehouse says so per statistic per season. Snap counts are a
separate matter: they do not exist before 2012 at any price, and that is
`NOT_AVAILABLE_FOR_ERA` rather than a gap to fill.

### Why it is worth the fetch

With 2000-2020 present, the forward chain runs 19 train/test folds instead of 4, the cold-start and
promoted-player cohorts grow from a few hundred events to thousands, and the redistribution study
(currently 180 quarterback, 158 back, 111 receiver, 159 tight-end absence events) gains roughly four
times the sample. The study already contradicts an assumption worth contradicting -- a lead
receiver's absence makes a club pass LESS, not more -- and that finding rests on 111 events.

**Assigned, not blocked**: every warehouse table builds today on what is here.

## OUT-040 — archived DFS contest ownership, for the field model

**Status:** OPEN, and **SHARPENED 2026-09-28 into an exact list**. **Raised:** 2026-09-28.
**Blocks:** GAP 4 calibration, and therefore every contest-aware portfolio decision (GAP 6) that
depends on the ownership LEVEL rather than its ordering.

**THIS IS TIME-SENSITIVE AND IT IS THE ONLY ITEM ON THIS LIST THAT CAN EXPIRE.** The source registry
records access as *"contests the account entered or can view"* and historical vintage support as
*"final only unless downloaded during contest"*. If DraftKings stops serving a finished contest page,
that week's ownership is gone and cannot be reconstructed from anywhere. Everything else in this
outbox will still be there next month.

**What is needed — the exact contests, read out of the entry files on disk.** The owner entered
these, so this is not "find ownership somewhere", it is fourteen authenticated downloads by the
entering account. For each one: the DraftKings contest standings CSV, whose ownership block carries
`Player, Roster Position, %Drafted, FPTS`. The raw entry list is strictly better where it is
offered, because whole lineups carry duplication and pairwise correlation and `%Drafted` carries
neither.

| contest id | game type | fee | our entries | contest name |
|---|---|---|---|---|
| `195700995` | CLASSIC | $0.50 | 33 | NFL $15K mini-MAX [150 Entry Max] (Early Only) |
| `195700996` | CLASSIC | $0.25 | 20 | NFL $3K Quarter Jukebox [Just $0.25!] (Early Only) |
| `195700997` | CLASSIC | $0.10 | 20 | NFL $1K Dime Package [Just $0.10!] (Early Only) |
| `195955835` | CLASSIC | $0.10 | 4 | NFL $1K Dime Package [Just $0.10!] (Early Only) |
| `196110787` | CLASSIC | $0.10 | 20 | NFL $400 Dime Package [Just $0.10!] (Early Only) |
| `196117165` | CLASSIC | $0.50 | 6 | NFL $2.5K mini-MAX [150 Entry Max] (Early Only) |
| `196122720` | CLASSIC | $0.25 | 20 | NFL $625 Quarter Jukebox [Just $0.25!] (Early Only) |
| `195785338` | SHOWDOWN | $0.10 | 20 | NFL Showdown $200 Dime Package [Just $0.10!] (DET @ BUF) |
| `195785364` | SHOWDOWN | $0.25 | 20 | NFL Showdown $250 Quarter Jukebox [Just $0.25!] (DET @ BUF) |
| `195785966` | SHOWDOWN | $0.50 | 36 | NFL Showdown $50K mini-MAX [150 Entry Max] (IND @ KC) |
| `195785967` | SHOWDOWN | $0.25 | 20 | NFL Showdown $6K Quarter Jukebox [Just $0.25!] (IND @ KC) |
| `195785968` | SHOWDOWN | $0.10 | 20 | NFL Showdown $3K Dime Package [Just $0.10!] (IND @ KC) |
| `195786074` | SHOWDOWN | $0.10 | 20 | NFL Showdown $5K Dime Package [Just $0.10!]  (NYG @ LAR) |
| `195943240` | SHOWDOWN | $0.10 | 10 | NFL Showdown $4K Dime Package [Just $0.10!] (ATL @ GB) |

**The seven CLASSIC ids are the ones that matter most** — the Classic field model cannot be
calibrated on Showdown ownership, because it is a different game with a different lineup shape.

**Where to put them:** `nfl/dfs/contest_results/`. `nfl/field/contest_ownership.py` reads that
directory, validates every file against the real export schema, and refuses a partial or malformed
one by name rather than reading around it. Run `python3.12 nfl/field/contest_ownership.py` after
dropping files in; it reports what loaded and what it refused, and rewrites
`nfl/field/OWNERSHIP_ACQUISITION_MANIFEST.json`.

**What is NOT a substitute, and it is an easy mistake to make.** `nfl/dfs/vintage/*.slice.csv`
carries FantasyCruncher `Exp.`, `EXP+` and `Used`. Those are a *projected* exposure from another
model, not realised ownership. Calibrating our field model against them would be fitting our
forecast to somebody else's forecast — the same category error as tuning a projection toward a
sportsbook line — and FantasyCruncher is context-only and may never become a feature input. The
ingest module has no code path to those columns, which is checked by a test rather than promised in
a comment.

**Also still wanted, and not urgent:** 2024–2025 contests if any were archived, and field size and
entry date per contest.

**Why the repository cannot answer it.** I searched for it before asking. There is no archived
contest ownership anywhere in the checkout — no `%Drafted` column in any CSV, no contest
standings export, nothing in `nfl/dfs/salaries/raw/`. The only lineup file present is
`OWNER_PLACEHOLDERS_FC_48_AUDIT_2026W3.csv`, which is the owner's 48 placeholder entries, not
the field. The external research packet says the same thing from the other direction: field
labels come "from self-archived contest CSVs", and none were archived. Published work
(Haugh & Singal) gives the problem shape but no coefficients, and the commercial pOWN products
state that their formulas are unpublished.

**What was built without it, and what it cost.** The field model ships STRUCTURAL and declared
`NOT_CALIBRATED_NO_ARCHIVED_CONTEST_OWNERSHIP`. Three things are earned without the data: the
accounting identities (shares sum to nine slots, nobody exceeds 100%, and the ownership-weighted
salary equals the field's expected spend, which SOLVES the salary tilt rather than declaring it),
the generator reproducing its own marginals, and a sensitivity grid standing in for calibration.

The sensitivity result is the reason this request matters rather than being a nicety. Across the
plausible parameter range the top-40 leverage set is **not** stable — worst overlap 0.4 against a
predeclared 0.80 threshold. So the field can order players for a given parameter setting and
cannot yet support a contest-aware decision that depends on the level. Two or three real contest
files would close that.

**If it does not exist,** say so and it will be recorded as permanently unavailable, with the
field model staying structural and the GAP 6 portfolio work restricted to what survives the
sensitivity grid. Do not synthesise ownership to unblock it.

## OUT-041 — defensive and return touchdowns, per club-game

**Status:** CLOSED IN REPOSITORY, 2026-09-28, no outside data needed. **Raised:** 2026-09-28.

**How it closed, and the mistake worth keeping.** This was written as a request for data because
`TEAM_GAME` cannot answer it. That is true of `TEAM_GAME` and false of the repository. Play-by-play
carries `td_team`, `return_touchdown` and `safety` on every row, so a touchdown scored by the club
that was NOT on offence is directly identifiable, which is exactly what DK credits to a defence. The
tail is now MEASURED over 2021-2026 regular-season play-by-play rather than excluded. The general
lesson is the one already in the briefing: *the repository is not the whole world, and neither is
any one table in it.* One table lacking a field is not the same as the field being unavailable, and
the second question — which other table already holds it — had not been asked.

**What was measured.** 0.1197 defensive or return touchdowns per club-game, 11.2% of club-games with
at least one, maximum 3; safeties 0.0237 per club-game. Together 0.766 DK points per club-game on
average, which is small in the mean and is not where it matters. Conditioned on points allowed the
rate falls with the score, 0.188 per club-game holding a club to 0-10 against 0.099-0.102 allowing
24 or more, so the tail is drawn jointly with sacks and takeaways from the same empirical 4-tuple
inside each points-allowed band and keeps its dependence on the game.

**The effect is in the tail, which is the point.** The 99th percentile moved 22 → 30 DK points for a
defence allowing 6, 15 → 20 allowing 20, and 10 → 15 allowing 34; the maximum draw allowing 34 moved
12 → 24. The mean barely moves. Defensive projections are therefore no longer floors.

**Known omission, named rather than absorbed.** A muffed kick recovered in the end zone by the
KICKING team is not counted. It is rare, and it is recorded in the artifact under
`scoring_tail.known_omission` instead of being folded into the rate.

**What is still outstanding and is NOT closed by this.** Blocked kicks, and field goals and extra
points per club-game. Those would let the 7.4945-point non-touchdown remainder be decomposed
properly. They do not affect DST scoring under DK rules, so they are a data-quality item rather than
a projection defect, and the request below stands at lower priority.

---

**Original request, preserved.** **Affects:** every defensive projection, which was
a FLOOR until this was measured.

**What is needed.** Per club-game, for 2000 onward: defensive touchdowns (interception and fumble
returns), kick and punt return touchdowns, safeties, and blocked kicks. Field goals made and
attempted, and extra points, would also let the non-offensive points remainder be decomposed
properly instead of carried as one number.

**Why the repository cannot answer it.** `TEAM_GAME` records `points`, `offensive_td`, `pass_td` and
`rush_td`. A club's points decompose into offensive touchdowns, kicks, defensive and return scores
and safeties, and only the first is present, so the rest are not separable from the total. The
measured non-touchdown remainder is 7.4945 points per club-game and that single figure contains all
of them.

**What was built without it, and the bias it leaves.** `nfl/sim/dst.py` models a defence off the
opponent's simulated points — the DK tier table plus sacks and takeaways drawn from the empirical
pairs within the relevant points-allowed band, measured over 2,782 club-games. Sacks fall from 3.675
to 1.638 and takeaways from 1.850 to 0.825 as points allowed rise, so the conditioning is doing real
work and a defence comes out correctly short the offence it faces: holding a club to 3 averages
14.36 DK points against −0.72 when allowing 38.

Defensive and return touchdowns are EXCLUDED, not estimated. No plausible rate was substituted. So
every defensive projection is a floor, and the understatement is concentrated in the upside tail —
which is exactly the part a tournament portfolio is selected on, so this is not a rounding concern.

**If it does not exist,** say so and it will be recorded as permanently unavailable, with the
defensive projections staying explicitly labelled as floors wherever they are consumed.

*(That last paragraph is why refusing to synthesise a rate was right, and the close above is why
refusing was not the end of it. The rate was measured, not invented.)*

## OUT-042 — verify the depth ordering for 82 players whose history says a higher role

**Status:** OPEN. **Raised:** 2026-09-28. **Affects:** projection quality for 82 players on the Week 3
slate (50 WR, 21 TE, 11 RB).

**What is needed.** Confirmation of the current depth/usage position for the flagged players, or a
refreshed depth ordering. The list is in `DK_WEEK3_PROJ_V1.json` under `role_evidence_conflict`; the
largest by projected points are Najee Harris, Darren Waller, Sterling Shepard, A.J. Brown and Kimani
Vidal.

**What the flag means.** Each of these players has held a role at least two bands above what the
supplied depth evidence allows. A.J. Brown sits at within-position depth rank 6 with ALPHA history;
the ordering may be stale, or his role may genuinely have changed, and this checkout cannot tell
which. The consequence is quantified rather than hidden: a low evidence ceiling makes a player's own
history count as off-role, which discounts it toward the role-similarity floor, which leaves the
hierarchical prior little weight and lets the current fortnight decide the projection. A.J. Brown
comes out at 2.7 DK points with 0.06 expected touchdowns against a career 0.487 per game.

**What was fixed here first, so this is not a request to paper over a bug.** Two unit mismatches were
found and repaired. The supplied `depth_rank` is CLUB-WIDE and was being read as position depth —
Buffalo's rows run (1, WR), (3, RB), (4, TE), (6, TE), (7, WR) — so every club's second receiver and
beyond was capped at FRINGE; it is now re-indexed within club and position, which moved 124 players
out of rank 4-plus and corrected 49 role bands. And the hierarchical prior's WEIGHT was counted over
the at-role subset while its VALUE was built from the player's whole history, so a correct prior took
12% of the blend; the weight is now counted over the rows the value came from, discounted by role
similarity and floored at the at-role count.

After both fixes 82 conflicts remain, and they are data disagreements rather than code defects.
Quarterbacks are deliberately excluded: a backup passer genuinely has alpha history and a fringe role
today, which the appearance-probability model already handles.

**What is NOT wanted.** Do not send a depth chart inferred from our own projections, and do not ask us
to override the evidence with history — that would discard current role state, which is the one thing
this layer exists to consume. If the ordering is correct and these players really are buried, say so
and the flags will be recorded as confirmed rather than pending.
## OUT-043 — repeated Hard Rock board snapshots, so a line has a history

**Status:** OPEN. **Raised:** 2026-09-28. **Blocks:** closing-line comparison, edge-bucket
calibration, and the TRIGGER stage of the two-stage bar, all of which need a price to have moved.

**What exists, measured rather than assumed.** Exactly one Hard Rock board:
`nfl/market/raw/HR_NYG_LAR_BOARD_2026-09-21T2320Z.csv`, 969 rows over 12 market types for one game,
yielding 1,622 priced sides. It carries 74 distinct `ts_utc` values, which looks like a time series
and is not: the row ages span 0.4 to 8.9 minutes, so those are the per-row capture moments inside a
single scrape. **One game, one pass.** `nfl/market/price_history.py` reports
`n_markets_with_movement_measurable: 0` and refuses closing-line value with
`CLOSING_LINE_VALUE_UNCOMPUTABLE_ONE_PASS` rather than reporting a movement of zero, because a
movement of zero would be reporting an absence as a measurement.

**What is needed.** The same board export, for the same game, **at several separated times**. The
existing exporter already produces the right columns; nothing new has to be written, it has to be
run more than once. Per slate, per game, a pass at each of:

| pass | when | what it establishes |
|---|---|---|
| OPEN | as soon as the market posts | the opening line |
| T−24h | day before kickoff | early movement, and a price we could have acted on |
| T−3h | after the inactives window | movement attributable to news |
| T−15m | as close to kickoff as is safe | **the close**, which is what closing-line value needs |

Two passes make movement measurable at all; four make it attributable. Anything is better than one.

**One ordering requirement, and it is not negotiable.** A pass is only useful for comparison if our
forecast was **sealed before that pass was captured**. `price_history.comparable()` enforces it
arithmetically and refuses `PRICE_PREDATES_THE_SEAL`, so a board captured before the sealed forecast
exists is stored but cannot be compared. If a choice has to be made, seal first and capture late.

**Where to put them:** `nfl/market/raw/`, any filename containing `BOARD` and ending `.csv`. Then run
`python3.12 nfl/market/price_history.py`, which validates each file against the real board schema,
refuses a partial one by name, and rewrites `nfl/market/PRICE_HISTORY.json`.

**Book scope and direction, restated because both are easy to erode.** Hard Rock Bet only. No
parlays. And the comparison runs ONE WAY: a sealed forecast is scored against a price, and no
projection is ever adjusted toward a price. `nfl/market/price_history.py` has no import path to any
projection module and a test asserts it.


---

## REQUEST 2026-10-01 — current-season football results (PRIORITY ZERO)

**Why this is Priority Zero and not a chore.** Every 2026 projection this system makes currently
rests on two games. `nfl/production/world_clock.py` now refuses on it:

```
FAIL EVIDENCE_BEHIND_THE_WORLD
  latest_completed_game_in_world      2026-09-28   (week 3)
  latest_completed_game_in_evidence   2026-09-21   (week 2)
  missing_weeks [3]   n_missing_games 16
```

**Root cause, so nobody re-diagnoses it.** The selected play-by-play capture,
`nfl/research/postgame/pbp_2026.6643f82adb1158c8.csv.gz`, was pulled **2026-09-24 15:20** and holds
Weeks 1 and 2 only — 2,756 and 2,733 regular-season plays, 32 games. Week 3 was played
**2026-09-25 to 09-28**, after that pull. The selected schedules capture,
`nfl/vintage/schedules.9d3644487c6021f2.csv.gz`, carries scores for Weeks 1–2 and blanks from Week 3
on. Nothing is broken in `nfl/warehouse/team_game.py`; there is nothing in the source to ingest. This
is an **acquisition** gap and it needs bytes from outside the checkout.

**What is needed.** Two nflverse pulls, both covering the season to date:

| data | drop it at | tier | required columns |
|---|---|---|---|
| 2026 play-by-play | `nfl/research/postgame/pbp_2026.<hash>.csv.gz` | PRIMARY | `game_id, season_type, week, posteam, play_type` |
| schedules (all seasons) | `nfl/vintage/schedules.<hash>.csv.gz` | PRIMARY | `game_id, season, week, home_team, away_team` |

Weeks 3 and 4 are what is missing today; Week 4 completes 2026-10-05, so a pull after that is worth
more than two pulls before it. **Do not** hand-edit the existing captures — add new files.

**Nothing has to be rewired.** `sources.select` prefers candidates by
`('tier', 'weeks', 'completeness', 'rows')` for play-by-play and
`('tier', 'seasons', 'weeks', 'completeness', 'freshness')` for schedules, so a newer capture with
more weeks is chosen automatically. Then:

```
python3.12 nfl/warehouse/team_game.py          # rebuild the club-game table
python3.12 nfl/production/world_clock.py       # must now print EVIDENCE_REACHES_THE_WORLD
```

If `world_clock` still reports a gap after the rebuild, the capture did not contain the weeks it was
believed to contain — read its week histogram before concluding anything else.

**One thing to preserve.** `assert_no_post_cutoff_outcomes` currently PASSES over 223 future games
across 17 named outcome fields. A capture that populates a score on a game that has not kicked off
would turn that into `POST_CUTOFF_OUTCOME_PRESENT`, which is leakage. If that fires, the capture is
wrong and must not be ingested.

## REQUEST 2026-10-01 — tonight's DK Showdown export, PIT at CLE

**The game is identified and the repository already knows it.** From
`nfl/vintage/schedules.9d3644487c6021f2.csv.gz`: `2026_04_PIT_CLE`, gameday **2026-10-01**, gametime
**20:15**, the only game on the date.

**What is needed.** The DraftKings **Showdown** entries export for that contest — the file DK serves
as `DKEntries….csv`, carrying both blocks: the entries block (`Entry ID, Contest Name, Contest ID,
Entry Fee, CPT, FLEX, FLEX, FLEX, FLEX, FLEX`) and the player-pool block (`Position, Name + ID, Name,
ID, Roster Position, Salary, Game Info, TeamAbbrev, AvgPointsPerGame`). A salary-only export is not
enough: the entry rows are what the upload is written against.

**Where to put it:** `nfl/dfs/salaries/raw/`, any filename containing `DKEntries`. Then:

```
python3.12 nfl/tools/showdown_to_portfolio.py nfl/dfs/salaries/raw/<the file>.csv
```

The runner takes the matchup and the kickoff from the pool's `Game Info` column, so nothing needs to
be told which game it is. It will stop at `SHOWDOWN_PROJECTION_DOES_NOT_COVER_THIS_GAME` until a
projection covering PIT and CLE exists — which is the first request above, since a projection for
those clubs needs the results that are missing.

**Also useful, separately:** the official inactives for the game once published, as a JSON list of
names, passed with `--inactives`. Until then the runner reports
`SHOWDOWN_OFFICIAL_INACTIVES_NOT_SUPPLIED` as DEFERRED and will not treat the absence as "everyone
plays".

**Not wanted, explicitly.** `AvgPointsPerGame` is in that file and is a third-party projection. It is
never a model input and never fills a missing projection. Do not strip it, do not use it.


---

## SATISFIED 2026-10-01 — the DK Showdown export for PIT at CLE has arrived

The owner supplied both files. Recorded here so the request is closed rather than left standing.

| file | stored as | measured |
|---|---|---|
| DK Showdown entries export | `nfl/dfs/salaries/raw/DKEntries_PIT_CLE_SHOWDOWN_2026W4.csv` | 51 people, **102 priced items** (51 CPT + 51 FLEX), 78 entries across 4 contests, PIT 26 / CLE 25, QB 8 / RB 12 / WR 18 / TE 9 / K 2 / DST 2 |
| vendor projection sheet | `nfl/dfs/salaries/raw/THIRDPARTY_showdown_PIT_CLE_2026W4_CONTEXT_ONLY.csv` | 74 rows, 37 unique names |

`showdown_to_portfolio.py` reads the game and the kickoff from the pool's `Game Info` alone:
**PIT@CLE at 2026-10-01T20:15:00 ET**. Ingest and slate identity both PASS, which means all 51 people
carry distinct CPT and FLEX ids and a captain price at exactly 1.5x flex.

**The vendor sheet is CONTEXT ONLY and is named so it cannot be mistaken.** Its columns include `FC`,
`My`, `FC Proj`, `My Proj`, `Floor`, `Ceiling` and `Exp.` — third-party projections of the same class
as FantasyCruncher. They are never a model input, never a blend, and never a fallback for a missing
projection. Owner's instruction, 2026-10-01, and the firewall already enforced it.

**Two facts about that sheet that matter if anyone is tempted to lean on it.** It covers 37 names
against DK's 51, and an exact-name join leaves **17 DK people with no vendor row and 3 vendor rows
matching no DK person**. So it is not even a complete substitute for the thing it is not allowed to
substitute for.

**All 78 entries already carry the owner's lineups.** The runner writes its own upload file at
`nfl/dfs/salaries/DK_SHOWDOWN_UPLOAD_GENERATED.csv` and never modifies the input; a test compares the
input bytes before and after the run.

### What is still blocking tonight, in order

1. **Week 3 (and Week 4) results.** Unchanged and still Priority Zero — see the request above.
   `world_clock` reports `EVIDENCE_BEHIND_THE_WORLD`, world through 2026-09-28, evidence through
   2026-09-21, 16 played games absent.
2. **Projections covering PIT and CLE**, including both kickers and both defences. Blocked by (1):
   the existing Week 3 artifact covers 18 clubs and neither PIT nor CLE projections exist for Week 4.
   The runner stops here with `SHOWDOWN_PROJECTION_DOES_NOT_COVER_THIS_GAME`.
3. **Simulated draws** for those 51 players. `near_optimal_candidates` refuses
   `SHOWDOWN_DRAWS_ABSENT` without them and will not manufacture a distribution from a projected mean.
4. **Official inactives** for PIT@CLE when published, as a JSON list of names passed with
   `--inactives`. Until then availability is DEFERRED and publication is withheld.

Stages 5 to 7 of the owner's plan — optimiser, portfolio, DK-ready export — are built, tested and
waiting on 1 to 4. Nothing about tonight is usable until (1) lands and the world-clock gate passes.

---

## 2026-10-01 — what the six candidate refreshes actually reach, measured from the code

The owner located six current nflverse assets. Before fetching five more files, here is what each one
is wired to **today**. Only four data types are registered in `nfl/warehouse/sources.py`:
`play_by_play`, `schedules`, `weekly_rosters`, `depth_charts`. The other feeds have no registered
source, so dropping a file in changes nothing until a reader exists.

| feed | registered? | reaches tonight's projection? | verdict |
|---|---|---|---|
| **weekly rosters** | YES `nfl/vintage/weekly_rosters.*raw.csv.gz` | **YES, deeply** | **fetch first** |
| official inactives | separate capture path | YES — flips availability | **fetch when published** |
| depth charts | YES `nfl/vintage/depth_charts.*.raw.csv.gz` | not yet — see below | useful, needs wiring |
| snap counts | **NO** | no reader | needs registry + reader |
| injuries | **NO** | no reader | manual designations cover tonight |
| weekly player stats | **NO** | redundant | lowest value |

### Weekly rosters are the identity backbone, and that makes them the top of the list

`player_prior.py:54` is `ROSTERS = 'nfl/vintage/weekly_rosters.*raw.csv.gz'`, and both
`name_index()` and `position_index()` are built from those roster blobs. So a refresh moves four
things at once:

- **identity resolution** — tonight 49 of 51 DK players resolved and 3 needed suffix stripping. A
  newly signed or promoted player who is not in a 2026-09-24 roster blob cannot resolve at all.
- **`position_index()`**, which is `pos_of` in `role_state_history.pregame_depth` — so **depth ranks
  depend on it**. A player whose listed position is stale is ranked in the wrong group.
- club membership, for anyone who moved.
- the two team defences, which resolve as `TEAM_DEFENCE_NOT_A_PLAYER_IDENTITY` by design and are
  unaffected.

The newest installed roster blob is **2026-09-24**. The owner's is 2026-10-01 14:27.

### Depth charts: registered, but NOT what produced tonight's depth ranks

This is worth being precise about, because the expectation is reasonable and currently wrong.
Tonight's `depth_rank` came from `role_state_history.pregame_depth`, which ranks players **by measured
usage in the completed weeks** — carries for RB, targets for WR and TE, pass attempts for QB. It does
not read `depth_charts` at all. `depth_charts` is consumed by `nfl/identity/effective_scope.py` and by
research modules, not by `role_state`.

So a fresh depth chart improves identity scope and would be the right **evidence** for role, but it
will not change a single projection until it is wired into `role_state`. That wiring is a real piece of
work and it has a known hazard: the published depth chart and measured usage will sometimes disagree,
and which one wins is a modelling decision, not a plumbing one. The Warren example is the case in
point — 56 snaps against no other Steelers back above three is a *usage* fact, and usage is what the
current depth rank already uses, which is why Warren came out ALPHA and 21.84 points tonight.

### Snap counts: a declared slot with no source, and a forbidden shortcut

`era.py` declares `snap_counts` with PFR coverage from 2012 and states plainly that
*"any fabricated snap count or snap share"* is forbidden, and that before 2012 the column stays
`NOT_AVAILABLE_FOR_ERA`. `player_game.py` carries a `snap_counts` field that is currently the era
marker rather than data. There is no registry candidate for it.

It is worth wiring, and the reason is specific: `role_state._observed_band` reads
`mean_offense_pct` for every position that is not WR, TE or RB — which is exactly **QB and K**. That
field is unavailable today, so quarterbacks and kickers get no observed band and fall through to
history. Snap share is the missing input there.

### Weekly player stats: redundant with what is already installed

The usage panel is built from play-by-play, which is current through Week 3 as of this afternoon
(8,311 plays, 962 player-weeks). A weekly-stats file would be a second route to numbers the panel
already holds, and a second route to the same quantity is a reconciliation problem rather than new
evidence. Low value until there is a reason to cross-check.

### Where to put them

```
weekly rosters   nfl/vintage/weekly_rosters.<hash>raw.csv.gz      (note: no dot before "raw")
depth charts     nfl/vintage/depth_charts.<hash>.raw.csv.gz
                 nfl/vintage/depth_charts.<hash>.reduced.csv.gz
```

`<hash>` is **sha256[:16] of the file's own bytes**, which is the convention the installed files
follow and which was verified against them before use. Then:

```
python3.12 nfl/tools/player_prior.py        # rebuilds name_index / position_index
python3.12 nfl/production/world_clock.py    # must still read EVIDENCE_REACHES_THE_WORLD
```

and rebuild the slate state, role state and projections from the showdown state artifact.

### 2026-10-02 — capture definitions on this branch take effect only on the default branch

GitHub reads a `schedule:` workflow definition from the default branch only. Four definitions
changed on `claude/nfl-greenfield-architecture-stsxmk` and are inert until merged to `main`:

- `.github/workflows/nfl-t90.yml` — regenerated for 2026 week 4 (the deployed pin is September's,
  so no T-90 window exists for any October kickoff on the deployed surface);
- `.github/workflows/nfl-status.yml` — regenerated for week 4 and now checks out / pushes
  `capture-prod` instead of `main`;
- `.github/workflows/nfl-availability.yml` — now checks out / pushes `capture-prod` (it has been
  writing the availability manifest to `main`, which is where `origin/main`'s recent commits come from);
- the generators behind the first two (`nfl/tools/gen_t90_schedule.py`, `gen_status_schedule.py`).

Merging to `main` is the owner's call. Until then the baseline `nfl-capture.yml` keeps running every
30 minutes (confirmed: run 1197 at 04:56Z today, success) and `nfl/tools/sync_captures.py` brings its
captures into this branch verified. Nothing here needs network from this agent.

### 2026-10-02 — GOV-1/2/3: three governance controls, and what was read as ratified

The owner approved the patch surface ("Yes.") for the three controls: (1) nothing measured cannot
PASS, (2) every detector carries a demonstrated trip case, (3) BUILD / VERIFY / OPERATE / RESEARCH
modes with enforceable write boundaries. Two things in that approval are recorded here so the owner
can object if the reading was too wide:

- **The mode table was read as ratified as written.** It is now `coordination/MODE_POLICY.json`,
  enforced by `coordination/orchestrator/locks.mode_boundary` (retrospective, run_suite's first
  step and `coordination/mode.py check`) and `coordination/mode_guard.py` (prospective, a PreToolUse
  hook registered in `.claude/settings.json`). The file is listed in `PROTECTED_PATHS`: agents may
  not edit it; the owner amends it. The table says what each mode may write; the owner's own rule
  that BUILD may not self-certify is enforced in `refresh_state` (test_surface is marked current only
  from a VERIFY-mode suite row at the current head).
- **The mode in force today is none.** No `mode` block exists in `PROJECT_STATE.json` yet, so the
  boundary reports NOT_EXECUTED rather than CLEAN (rule 1 applied to rule 3) and the hook makes no
  decision. The owner can pin a mode with `mode_declared: {"mode": "...", "reason": "..."}` in
  PROJECT_STATE.json; an agent sets the measured mode with `python3.12 coordination/mode.py set
  <MODE> --reason "..."`, which is refused while a pin exists and always logs a HANDOFF row.

**Hook caveat, stated plainly.** This session's project directory is the MLB repository, so the NFL
hook cannot fire in this session. Its firing is proven by pipe-test (`test_mode_boundaries.py`
test 5: synthesized PreToolUse JSON for an OPERATE write to `nfl/sim/game.py` returns `deny`). Live
firing is proven the first time a session is rooted in this repository.

**Rule 2 reports the true state and it is red.** `nfl/tests/DETECTORS.json` lists every refusal code
in the seed modules (174 at seed, growing as rule-1 sites are repaired). The suite now FAILS on any
listed detector without a control that ran and tripped in that run. Controls are being tagged; until
every listed detector has one, `SUITE FAIL` is the rule working, not a regression. Detectors that
cannot be tripped by any constructible input are reported with the reason -- that is a finding about
the detector (unreachable refusal), not something to hide by delisting.

**The broader operating-system proposal (constitution, per-run manifests, typed agent contracts,
independent verifiers, claim-evidence graph, two-model-of-reality rule, mutation authority levels,
adversarial verifier, command-center OPERATE output, self-measurement) is NOT started**, per the
owner's instruction to prove these three controls first and prepare the constitution / agent-authority
rewrite separately for ratification. It is the next item after the proof.

#### Two owner items raised by the rule-1 sweep (2026-10-03)

1. **`nfl/production/review/gate.py` is PROTECTED and has a rule-1 defect.** `evaluate()` with zero
   dossiers and no conflict returns `PLAYER_REVIEW_PASS`: a slate of nobody passes review. The
   repair (BLOCKED `PLAYER_REVIEW_NO_DOSSIERS`, cause EMPTY_INPUT) is at
   `coordination/EVIDENCE/proposals/2026-10-02_review_gate_rule1.patch`, reverted from the tree
   because the path is propose-only. `test_non_evidentiary_refusal_production_b` test 17 pins the
   defect by name until the owner applies it.
2. **The assumption gate on adjustments (DEF-090).** `sportsplatform.governance.assumption.assert_promotable`
   now refuses with `PROMOTION_VERDICT_EMPTY_INPUT` when no governed assumption names the consumer,
   and today that is every adjustment layer. `adjustment_registry.assert_may_apply` carries this on
   the verdict as `assumption_gate: NOT_EXAMINED` and decides on the registry record and frame
   lineage alone; a true gate FAIL still refuses. The alternative, refusing every production
   adjustment until each layer registers its assumptions, is fail-closed and would stop the
   adjustment path outright. That is the owner's call; the current behaviour is recorded and tested,
   not hidden.

#### Correction (2026-10-03): the capture-surface mismatch predates the rule-1 edits

The GOV-1/2/3 commit message says the rule-1 edits under `nfl/capture/` make
`test_capture_deployment_integrity` and `test_capture_prod_deployment` report
`CAPTURE_EXECUTOR_SURFACE_MISMATCH`. Measured at the previous head (8f3a9c38, a worktree run of the
same three suites): the running surface already hashed to `efab90d6…` against approved release
`CAPREL-361a020a66c673b8`'s `8094370a…`, with the same 1 + 5 failing checks, and
`test_capture_obligations` already carried the same 4 (orphan count 51 vs the pinned 48; T-90 cron
entries 18). The rule-1 edits moved the running hash to `2a59c19e…`; they did not open the gap.
Both facts stand: a new capture release approval is the owner's, and the pinned counts in
`test_capture_obligations` are a separate drift item, not touched here.

#### Full-run classification (2026-10-03)

First full run on the governance tree: 338 modules, 15,634 checks executed, 180 failing, 69 raised,
54 red modules. Control: the same 54 modules at the pre-batch head 7d3d0e90 in a worktree.
43 fail with identical counts there; 3 improved; 8 were worse. Of the 8, five were this batch's
and are fixed (orchestrator sandbox mode check; the runner's NOT_EXECUTED verdict keyed on
executed functions, found by the harness audit's seeded module; two protected-gate expectations
pinned as the proposal they are; the PIT guard's empty-rows control converted to rule 1; the
guard-reachability census accepting a test caller as NO_PROD_CALLER). The remaining one,
`test_qb2_production`, is environmental: at 7d3d0e90 the derived cache is absent and the module
raises before reaching the pipeline; in this tree the cache was built by earlier runs, the module
runs further and meets the pre-existing `REQUIRED_SOURCE_NOT_DECLARED` refusal at
capture_validation (run_forecast.py:379, untouched by this batch). That refusal is the gate
working; the test's fixture declares only `schedules`.

### 2026-10-03 — REQUEST to the networked agent: Week 4 Early Only (8 games, 1:00 PM ET Sun 2026-10-04)

The owner is playing DraftKings Classic Early Only. Games, from DraftKings' own entries export:
NE@BUF, TEN@BAL, JAX@CIN, DAL@HOU, LAR@PHI, ARI@NYG, GB@TB, NYJ@CHI (nflverse ids 2026_04_NE_BUF,
2026_04_TEN_BAL, 2026_04_JAX_CIN, 2026_04_DAL_HOU, 2026_04_LAR_PHI, 2026_04_ARI_NYG, 2026_04_GB_TB,
2026_04_NYJ_CHI). Lock 2026-10-04T17:00Z. This agent has no network; these are yours, not blockers
for the rest of the build, which proceeds on the captures synced at 20261003T150307Z.

1. **Official inactives** for those 16 clubs, from the NFL.com inactives page and team sites, as
   they post (~15:30Z Sunday). Same capture shape as `official_inactives` 20260917T234100Z
   (raw HTML + parsed rows with gsis_id where resolvable). The deployed T-90 workflow is pinned to
   September and will not fetch them; `nfl-t90.yml` for week 4 sits on this branch, inert until
   the owner merges it.
2. **Hard Rock Bet board** for the same 8 games only, two captures: one now (Saturday) and one
   after inactives. Game markets (spread, moneyline, total, team totals) and player markets
   (pass yds/att/TD/INT, rush yds/att, rec yds, receptions, anytime TD, alternates where shown).
   Per row: player, team, market, line, over/under price, book timestamp, capture timestamp,
   game, market id. Append-only into the Hard Rock price history store (seal-before-price:
   the proprietary board for week 4 is frozen before these are read).
3. **Weather** for the seven open-air games (NE@BUF, TEN@BAL, JAX@CIN, LAR@PHI, ARI@NYG, GB@TB,
   NYJ@CHI; DAL@HOU is under a retractable roof, so record its roof status if reported):
   kickoff-hour wind, precipitation, temperature, with the forecast's own issue time. Recorded as
   context; the model has no validated weather term. *(Corrected 2026-10-03: this item first said
   five outdoor games and listed PHI and TB as covered. Both are open-air stadiums.)*

### 2026-10-03 — Week 4: two defects found while building the portfolios, one declared step

1. **The simulator has no player efficiency.** `nfl/sim/game.py` (USAGE_FIRST yards block) draws
   every player's yards per target and per carry as a league club draw plus a league player
   deviation, with no player-specific centre. `showdown_draws._shares` passes shares, catch rate
   and TD shares, not efficiency. Measured on the week-4 draws: simulated mean minus projection
   from -5.95 (Zay Flowers) to +3.33 (Jalon Daniels), Monte Carlo SE about 0.2. Low-efficiency
   spot-start quarterbacks were inflated (Bagent +2.9, Daniels +3.3, Brissett +2.8) and the
   portfolio's top quarterback was Bagent in every contest.
2. **The projection does not close on club passing yards.** Receivers' projected receiving yards
   minus the quarterbacks' projected passing yards, per club: CHI +38.0, PHI -38.7, TB +19.9,
   NYJ -19.7, JAX +16.5, others within about 12. The simulator enforces QB yards = receivers'
   yards in every world, so a player-efficiency centre cannot be added to the simulator until the
   projection closes this, and which side anchors (QB efficiency or receiver efficiency) is a
   modelling question with no evidence yet. Not fixed tonight.
3. **Declared step, switchable:** `classic_slate_run.anchor_means` rescales each player's draws
   so the mean is his `dk_points_if_plays` (owner ruling 2026-10-02: the projection is the
   expected-value centre). Correlations and each player's coefficient of variation are unchanged.
   The raw gap per player is kept in the draws artifact under `player_mean_anchor`. Off with
   `--player-mean-anchor NONE`. The unanchored portfolio is kept for comparison in the owner
   package. This is a stopgap for (1), not a validation of anything.

### 2026-10-03 — Week 4: Hard Rock capture must FOLLOW our seal (sequence for Sunday)

The football distributions are now sealed (`nfl/dfs/salaries/DK_2026W4_EARLY_SEAL.json`, written
2026-10-03T18:20Z; projection and stored-worlds hashes inside). `classic_prop_compare.py` reads prices
only through `price_history.comparable()`, which refuses a price captured before the seal or after
kickoff. So the order on Sunday matters, and it is:

1. You capture **official inactives** for the 16 clubs (~15:30Z) and push them.
2. This agent re-runs state -> projection -> worlds -> research book; the book writes a **new seal**
   (only if the projection or worlds changed). The new `written_at` is posted in this file.
3. You capture the **Hard Rock board** for the 8 games *after* that `written_at`, in the board
   format `price_history.load_board` reads (`HR_<AWAY>_<HOME>_BOARD_<UTC>.csv`: market, selection,
   points, is_main, over, under, price, ts_utc, age_min, flag, over_id, under_id, price_id,
   player_id, team_id), into `nfl/market/raw/`.

A Saturday board captured after 18:20Z is comparable against the Saturday seal only until the
Sunday reseal; after that, only a board captured after the new seal is compared. A board captured
before the current seal is refused by name, which is the rule working. Every seal is kept in
`DK_2026W4_EARLY_SEAL_HISTORY.jsonl`.

### 2026-10-03 — Week 4: two more requests (roster moves, QB starters), and what the audit found

4. **Week-4 roster capture** (nflverse `weekly_rosters` 2026 week 4, or the clubs' 53-man lists) for the
   16 Early Only clubs. DraftKings' pool places eight players on clubs our week-1-3 capture does not
   (J.J. McCarthy NYG, Will Levis NYJ, Dare Ogunbowale HOU, Coleman Owen GB, Chandler Brayboy NE,
   Brock Lampe BUF, Cody Hardy NYJ, Shedrick Jackson BAL). All project under 2 DK points, so no lineup
   moves on them; the capture is still stale and the audit says so.
5. **Starting quarterback confirmation** for CHI (we start Tyson Bagent behind Caleb Williams, OUT)
   and TB (Jalon Daniels behind Baker Mayfield, OUT; Brett Rypien signed this week, identity
   unresolved here). Club announcement or league-cited report, with its time. Feed it to
   `classic_prelock.py --confirmed-starters` as `{"CHI": "<name>", "TB": "<name>"}`. Bagent is 16% of
   the 150-max, 35% of the 20-max and 2 of 3 entries, so this is the single largest pre-lock risk.

Audit (nfl/dfs/salaries/DK_2026W4_EARLY_AUDIT.json): accounting PASS on all 16 clubs; 11 sampled role
cards match an independent play-by-play recount; yards props blocked for CHI, JAX, NYG, NYJ, PHI, TB
(receiving vs passing yards gap over 5%, largest where the QB-receiver pairing changed this week).

### 2026-10-03 — Authoritative full suite at 54a3d19e (clean worktree), classified against 776cce7e

| | 776cce7e (control) | 54a3d19e (authoritative) |
|---|---|---|
| modules | 340 | 348 |
| test functions | 3,518 | 3,561 |
| checks | 15,477 | 15,633 |
| failing checks | 167 | 166 |
| raised | 135 | 135 |
| blocked functions | 36 | 36 |
| zero-check functions | 1 | 1 |
| detectors not executed (unvalidated) | 9 of 248 | 9 of 260 |
| red modules | 58 | 58 (same set) |

New failures introduced: 0 (no module newly red, none worse; test_system_state 6 -> 5). Every
classic_* module passes. Path-adjacent red modules: test_role_state_history and
test_football_only_arm fail only in a clean checkout (absent derived caches) and pass in the
production tree (9/9 and 6/6 checks); test_v1_draw_artifact is the incumbent run_forecast capture
declaration; test_showdown_family is the showdown product; test_draw_coherence is a docstring check.
None blocks the Early Only path. SUITE FAIL stands: the repository is not green.

### 2026-10-04 — Week 4 Sunday: how to hand us the news, and two new specifics

The post-news path is staged. Everything Sunday needs enters as ONE evidence packet
(`nfl/tools/sunday_evidence.py`; template in `nfl/dfs/salaries/DK_2026W4_EARLY_SUNDAY_INPUTS.json`),
written to `nfl/dfs/salaries/evidence/<packet_id>.json` and run as

    python3.12 nfl/tools/classic_slate_pipeline.py 2026W4 --as-of <UTC> \
        --evidence-packet nfl/dfs/salaries/evidence/<packet_id>.json --page <out>.html

- **Your capture of the official inactive lists** goes in with `"source": "OFFICIAL_CAPTURED"` and
  `"complete_clubs": [...]` naming every club whose FULL list you hold. Only that makes the unlisted
  players of a club ACTIVE_NOT_ON_INACTIVE_LIST; anything partial resolves only the names on it.
- **The owner's 10:30 ET list** goes in as `"source": "OWNER_RELAYED"`. It is never relabelled official:
  an uncited INACTIVE lands as REPORTED_OUT_UNVERIFIED, and the FINAL files say OWNER_RELAYED_NOT_OFFICIAL.
- A name that does not resolve to exactly one DraftKings pool row refuses the whole packet by name.

6. **TB quarterback depth beyond Daniels.** The captured TB chart lists only Mayfield (OUT) and
   Daniels. If Daniels is ruled out, nothing we hold names the starter: the projection then splits
   passing between Brett Rypien (21.5 attempts) and Easton Stick (12.5), which is the honest reading of
   no evidence and a poor one for lineups. A current TB chart or a club statement settles it.
7. **Official inactives as early as they post** (about 11:30 ET for the 13:00 ET games), as an
   OFFICIAL_CAPTURED packet for all 16 clubs. The full rerun took **16.6 minutes** in rehearsal
   (`nfl/dfs/salaries/DK_2026W4_EARLY_REHEARSAL.json`), so a packet landing by about **12:15 ET** leaves
   time to run, verify and hand the owner the FINAL files before 13:00 ET lock.

### 2026-10-04 15:55Z — LOCK-CRITICAL: game-day inactives, 16 clubs, needed now (lock 17:00Z)

This machine cannot reach the sources the owner named (egress proxy blocks www.rotowire.com and x.com).
Please capture, verbatim with retrieval time:
- https://www.rotowire.com/football/lineups.php: the inactive list for each of BAL, TEN, BUF, NE, CHI, NYJ,
  CIN, JAX, HOU, DAL, NYG, ARI, PHI, TB, GB (RotoWire = aggregation of the official lists, cite as such);
- https://x.com/sarahbarshop/status/2106770137592557697: the LA Rams inactives (RotoWire not yet showing LA).
Write it in the paste format of `nfl/tools/sunday_paste.py` (one `CLUB: name, name` line per club, a
`SOURCE:` line before each source; `CLUB: none` when a club lists no one). Applying it and the full rerun
take about 17 minutes, so it is needed by 16:30Z to leave review time before lock.

### 2026-10-04 16:3xZ — Week 4 Early Only: owner chose Option A (submit current finals)

FINAL upload sha256 bf50aaee… (173/173 verified) stands; no rebuild before lock. Accepted limitations:
the McClain stale input and the within-club target concentration (team volume sound).

POST-LOCK #1 MODELLING FIX (owner priority): replace the generic depth-rank target curve with an
empirically calibrated role/usage allocation (route share, target share, snap share, personnel,
teammate-absence redistribution). Pre-register it and evaluate forward-chained before it touches
production. Evidence: DK_2026W4_EARLY_FINAL_DISAGREEMENT_AUDIT.json and FINAL_DEPTH_REVIEW.csv
(Raymond 3.6 vs 7.0, Flournoy 3.1 vs 6.0, Boutte 0.7 vs 3.0, Noel 0.2 vs 3.0 targets/game; Lamb +1.8,
Washington +2.5, Wilson +2.8 above measured). Also: roster-capture refresh so recently elevated players
(McClain, Tinsley) resolve and carry usage.

### 2026-10-04 — post-lock data request for the role-allocation successor (roadmap item 1)

For weeks 1-4 2026 (and 2024-2025 for history), all 32 clubs: per player per game routes run, route
participation, slot/outside/inline alignment, personnel grouping on each snap, pass-block snaps, RB
routes, red-zone and goal-line snaps. Source and retrieval time with each file. See
docs/NFL_POSTLOCK_ROADMAP_2026W4.md. Not needed before lock.

### 2026-10-04 22:xxZ — Week 4 postgame: results needed (grader built, refusing until they arrive)

`nfl/postgame/classic_week.py` grades the locked Week-4 Early Only state (lock commit 039cfd0e, upload
bf50aaee…) and refuses until it holds results. Needed, each as the raw file with its source and capture time:
1. nflverse `stats_player_week_2026.csv` (player_stats release) including week 4 for the 16 Early Only
   clubs; the def_* and special_teams_tds columns let us score the DSTs ourselves.
2. nflverse `games.csv` with week-4 final scores (DST points allowed).
3. Optional: week-4 snap counts and participation/route data for the role audit.
The owner supplies the three DraftKings contest-standings exports (196208416 / 196208417 / 196208418).
This machine cannot reach the nflverse release files (404 through the proxy).

### 2026-10-05 — Week 4 postgame: public results acquired here; one owner item remains

This machine reached the nflverse releases (tag `stats_player`, not `player_stats`) and nfldata `games.csv`;
both are ingested under nfl/postgame/raw/2026W4/ with provenance and the Week-4 grade is built
(nfl/dfs/salaries/postgame/WEEK4_POSTGAME_REPORT.md). Items 1-2 of the previous request are CLOSED.
Still wanted from the networked agent: week-4 snap counts and participation/route data (role audit).
Owner-only: the three DraftKings standings exports (196208416 / 196208417 / 196208418).

### 2026-10-05 12:xxZ — Week 4 MNF ATL @ NO DraftKings Showdown (kickoff 00:15Z)

Staged here: public injuries, depth charts, weekly rosters and snap counts captured 11:39Z from nflverse
(nfl/dfs/salaries/raw/showdown_atl_no_2026W4/, hashed); role review
(nfl/dfs/salaries/showdown_atl_no/SHOWDOWN_ATL_NO_ROLE_REVIEW.csv); kickers now scored inside the
simulated world (nfl/tools/kicker_world.py); one-game runner and tournament builder ready.
draftkings.com and api.draftkings.com are refused by this machine's proxy (403).

1. OWNER: the DKEntries CSV for the ATL@NO Showdown contest(s): Entry IDs, Contest IDs, and the
   player pool with CPT and FLEX item IDs and salaries. Nothing can be priced without it.
2. NETWORKED AGENT or OWNER, at about 22:45Z (18:45 ET): the official ATL and NO inactive lists,
   as captured documents (URL plus capture time). Relayed lists are applied as
   REPORTED_INACTIVE_HIGH_CONFIDENCE and are never relabelled official.
3. NETWORKED AGENT: confirm from DraftKings' published NFL Showdown scoring whether a missed field
   goal deducts a point. kicker_model.py says -1 and dfs/scoring/statline.py says 0; the
   same-world draws use 0 and report the mean under -1 beside it.

### 2026-10-05 16:5xZ — ATL @ NO Showdown: Hard Rock capture after our projection is sealed

The owner's DK entries (172: 150 / 20 / 2 in 196285137 / 196285160 / 196285161) are ingested; our
football-only projection and 2,000-world simulation run here. NETWORKED AGENT, after the seal: capture
Hard Rock Bet ATL @ NO markets -- QB passing yards/attempts/TDs/INTs, rushing yards/attempts, receiving
yards/receptions, anytime TD, kicker points if offered, and the game lines -- each with line, price,
timestamp and source. Downstream comparison only; nothing flows back into the projection.
Also still open: the official inactives at ~22:45Z, and DK's missed-FG rule.

## OWNER MANUAL QUEUE 2026-10-05 — DraftKings exports (Cycle 1 ledger; deferred until the owner has computer access)

Manual only: DK's Fair Play Commitment forbids automated collection (DATA-11). Nothing here may be scripted. Each file,
once supplied, is hashed into a new `nfl/postgame/raw/<capture>/` directory with a PROVENANCE row; no capture is ever
overwritten. Completed-contest CSVs are only available for **10 days after the contest ends** (DATA-02).

| # | What | Where (DK) | Deadline | Ledger | Why |
|---|---|---|---|---|---|
| M1 | ATL@NO standings, contests 196285137 / 196285160 / 196285161, after FINAL | My Contests -> contest -> Export Lineups to CSV | by ~2026-10-15 | DATA-01, prereg doc | observation #1 for every shadow ownership / field / dupe method (docs/NFL_SHOWDOWN_ATL_NO_POSTGAME_PREREGISTRATION.md) |
| M2 | ATL@NO flagship Showdown + one small-field + one 20-max Showdown we did NOT enter, after lock and after final | Lobby -> NFL -> Watch Live -> contest -> Export Lineups to CSV | by ~2026-10-15 | DATA-01 | contest-size / entry-limit ownership differences (OWN-01/02, FC-05); tests whether not-entered completed contests stay exportable |
| M3 | PHI@CHI 2026-09-28 Showdown CSV(s) | same | **~2026-10-08** | DATA-02 | second Showdown observation; window closes first |
| M4 | PIT@CLE 2026-10-01 Showdown CSV(s) | same | **~2026-10-11** | DATA-02, DATA-06 | third observation; verifies the ledger's Warren / Watson / Rodgers CPT:FLEX points |

Owner decisions this ledger raises (not taken here): approve the manual capture SOP (export every NFL Showdown tier after lock
and after final, hashed, within the 10-day window); whether to buy one month of stat-api Pro as a research-only single-user
archive AFTER a free-preview cross-check against our 10/4 CSVs (vendor collection method unknown: a lawful-acquisition
question, DATA-03 / DATA-12); whether to ask DFS Hero for export terms (DATA-07).

## REQUEST 2026-10-05 22:50Z — LOCK-CRITICAL: official ATL and NO game-day inactives (lock 00:15Z)

This session's egress policy DENIES every host that publishes them (403 CONNECT, recorded 22:45Z): www.nfl.com,
site.api.espn.com, www.neworleanssaints.com, www.atlantafalcons.com, www.espn.com, www.rotowire.com; WebFetch is
blocked the same way. Web search returns only 2017-18 lists (Marshall, Te'o, Hendrickson) -- rejected, wrong game.
So this is BLOCKED FOR ME, NOT BLOCKED: it is the networked agent's to capture.

Needed, as soon as both teams post (normally ~90 min before the 8:15 PM ET kickoff):
1. The OFFICIAL inactive list for ATL and for NO, every name (not only skill players), with the source URL and the
   post time. Primary sources: neworleanssaints.com and atlantafalcons.com "inactives" articles, the NFL Gamecenter
   inactive list, or the teams' official X accounts.
2. Delivered as `nfl/dfs/salaries/raw/showdown_atl_no_2026W4/OFFICIAL_INACTIVES_ATL_NO_2026W4.json`, in the same shape
   as OFFICIAL_INACTIVES_PIT_CLE_2026W4.json (a JSON list of full names), plus a sibling
   `OFFICIAL_INACTIVES_ATL_NO_2026W4.PROVENANCE.json` with {source_url, posted_at, captured_at, captured_by}. Commit and
   push to claude/nfl-greenfield-architecture-stsxmk. This session polls that branch every 2 minutes and runs the
   OFFICIAL scenario the moment the file appears.

Already recorded (owner relay, tier RELAYED_OWNER_MESSAGE): game-day elevations ATL S Jammie Robinson (00-0038587),
NO EDGE Fadil Diggs (00-0040249), NO LB Jackson Sirmon (00-0039288) -- all practice-squad (DEV) in nflverse; none is
a priced DK Showdown player.

## REQUEST 2026-10-05 23:50Z — Hard Rock ATL@NO player-prop board, captured AFTER the seal and BEFORE kickoff (00:15Z)

The prop forecast is SEALED: nfl/market/atl_no_2026W4/PROP_FORECAST_SEAL.json, written_at 2026-10-05T23:49:04Z,
seal_sha256 e08e8a4a.... nfl/market/price_history.comparable refuses any price captured before that time or after
kickoff, so capture now, once, and again as close to kickoff as possible.

Needed: the full Hard Rock ATL@NO board in the existing board schema (market, selection, points, is_main, over, under,
price, ts_utc, age_min, flag, over_id, under_id, price_id, player_id, team_id -- as HR_NYG_LAR_BOARD_*.csv), saved as
nfl/market/raw/HR_ATL_NO_BOARD_<UTC stamp>.csv, priority markets: player_receptions, player_receiving_yards,
player_rushing_yards, player_passing_yards, player_passing_touchdowns, anytime touchdown. Push to
claude/nfl-greenfield-architecture-stsxmk. This session then runs `atl_no_prop_shadow.py compare <board>`.
DOWNSTREAM COMPARISON ONLY: nothing from the board touches the football model or any DFS lineup.

## STATUS 2026-10-06 — ATL@NO postgame: M1 still outstanding; Hard Rock board never arrived

- **M1 (owner, manual DK export) is still needed**: full-field standings for **196285137, 196285160, 196285161**
  (My Contests -> contest -> Export Lineups to CSV), inside DK's ~10-day window (by ~2026-10-15). The zip supplied on
  2026-10-06 (`contest-standings-196208417_1.zip`) is the Sunday classic contest, byte-identical to the existing capture
  (CSV e7212baf), not ATL@NO. Until M1 lands, every pre-registered field measurement in
  docs/NFL_SHOWDOWN_ATL_NO_POSTGAME_PREREGISTRATION.md, autopsy questions 3-4, and realised duplicate counts are
  NOT_AVAILABLE (recorded so in nfl/postgame/showdown_atl_no_2026W4/).
- **Hard Rock ATL@NO board (request 2026-10-05 23:50Z)**: nothing was pushed; the branch had no new commits on
  2026-10-06. Recorded as `NO_VALID_PRELOCK_MARKET_CAPTURE` (ATL_NO_HARD_ROCK_STATUS.json). Do NOT backfill historical
  prices for this game. For the next Showdown: capture the board after the prop seal and before kickoff, as requested.

## FULFILLED 2026-10-06 — M1 ATL@NO standings received

The owner uploaded full-field standings for 196285137, 196285160 and 196285161 on 2026-10-06. Preserved content-addressed
under nfl/postgame/raw/showdown_history/<cid>_ATL_NO/ (PROVENANCE.jsonl, sha256 of the uncompressed CSV). All five
pre-registered measurements are scored in nfl/postgame/showdown_atl_no_2026W4/ATL_NO_FIELD_ACTUAL_PREREGISTERED.json.
M2 (contests we did not enter) remains open and optional.

## REQUEST 2026-10-07 — PHI@CHI Showdown salaries (and any public projection file) for contest 196036243

For the duplication study (docs/NFL_SHOWDOWN_DUPLICATION_PREREGISTRATION.md). PHI@CHI (Showdown, 2026-09-28,
contest 196036243, DK $10K Quarter Jukebox 20-max) has full standings in the repo but **no salaries**, so its feasible
lineup universe cannot apply the $50,000 cap and every salary- or projection-conditioned duplication model can only be
tested PIT@CLE <-> ATL@NO (two folds instead of three).

Needed: the DK draftables for that contest's draft group -- per player: name, team, position, FLEX salary, CPT salary,
DK player ids (the same fields as a DKEntries export). If a FantasyCruncher-style Showdown projection file for that slate
exists anywhere in project storage, that too (it is used only as a description of what the field's optimizers saw,
never as a football input). Save as nfl/dfs/salaries/raw/DK_DRAFTABLES_PHI_CHI_SHOWDOWN_2026W3.<sha16>.csv with a
provenance line; push to claude/nfl-greenfield-architecture-stsxmk. Not blocking the next slate.

## REQUEST 2026-10-07 — nflverse 2024-2025 weekly rosters and game-day inactives (SC-APPEAR-1 follow-up)

SC-APPEAR-1 was replayed through the production allocator on held-out 2025 (nfl/research/appearance/
SC_APPEAR_1_PRODUCTION_PATH.json). Two limits trace to data this checkout does not hold: "dressed" is approximated by
presence in snap counts (an active player with zero snaps drops out of both arms, so observed zero shares are too low by
an unmeasured amount), and practice-squad elevations cannot be identified (that cohort is a labelled proxy).

Needed, for 2024 and 2025 regular seasons: nflverse `weekly_rosters` (roster_{season}_weekly: gsis_id, team, week,
status, status_description_abbr, game_type) and any game-day inactive / active list per game (team, week, gsis_id or
name, ACTIVE/INACTIVE). Save under nfl/postgame/raw/role_audit_history/ with sha256 rows added to its PROVENANCE.json;
push to claude/nfl-greenfield-architecture-stsxmk. Not blocking the next slate; it decides whether the SC-APPEAR-1
promotion recommendation survives the snap-count leak.

## REQUEST 2026-10-07 — next Showdown: inputs for nfl/tools/showdown_next_slate.py, then the Hard Rock board

The live path is now one command per phase from a slate config (template: nfl/dfs/salaries/NEXT_SLATE_CONFIG_TEMPLATE.json).
For the next Showdown slate, needed in nfl/dfs/salaries/raw/showdown_<away>_<home>_2026W<n>/: the DKEntries export,
the FC context file (optional; field shadow and B4 need it), the depth-chart capture for both clubs, confirmed starting
QBs, and at the inactive deadline the OFFICIAL inactive list with a PROVENANCE record (OFFICIALLY_VERIFIED true only for
an official team/NFL publication; its sha256 must equal the list's). After `run` prints SEAL_PROPS PASS: capture the Hard
Rock board in the existing schema as nfl/market/raw/HR_<AWAY>_<HOME>_BOARD_<UTC stamp>.csv, before kickoff, and push;
this session then runs `showdown_next_slate.py market`. The board is downstream only.

## REQUEST 2026-10-07 — Stat-api: a VERIFICATION SAMPLE only (no purchase, no bulk ingest)

The external gap audit (2026-10-07) cites Stat-api's FAQ: DK contest lineups from 2021, separate CPT/FLEX ownership,
complete-field ownership for complete contests, `mode=pre` = data at kickoff, personal plans prohibit publishing. Vendor
documentation is not validation. Before anyone recommends buying anything, we need an ALLOWED sample for contests we
already hold original DK exports for, so it can be reconciled field by field:

- contest ids: 196285137, 196285160, 196285161 (ATL@NO 2026-10-05), 196187080 (PIT@CLE), 196036243 (PHI@CHI);
- per contest: entry count, every lineup (CPT identity + five FLEX identities), rank, score, payout, CPT and FLEX
  ownership per player, finality flag and capture timestamps, contest metadata (fee, pool, entry cap, payout table);
- the terms of use for the sample and for any paid plan (internal research use, retention, no publication), in writing.

Save under nfl/postgame/raw/statapi_sample/ with a PROVENANCE.jsonl (url, retrieved_at, sha256, plan/terms). Do NOT
purchase or sign up for a paid plan: that is an owner decision (recorded in the readiness report). If no free/allowed
sample exists, record NOT_AVAILABLE and stop.

## REQUEST 2026-10-07 — TB@DAL Showdown (2026_05_TB_DAL, kickoff 2026-10-09T00:15:00Z): captures for the generic runner

Slate prepared at nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/ (SLATE.json draft + SLATE_PREP.json: what was
reconstructed from the repo and what was not). The runner refuses until each item below exists; nothing is stubbed.
Save into that directory unless stated, sha16-suffixed like the ATL@NO captures, and push to
claude/nfl-greenfield-architecture-stsxmk:

1. **DKEntries export** for the TB@DAL Showdown contests the owner enters (owner download):
   `DKEntries_TB_DAL_SHOWDOWN_2026W5.<sha16>.csv`, plus each contest's id, prize pool, entry fee, max entries per
   user and DK field size.
2. **nflverse depth_charts** for TB and DAL captured this week: `depth_charts_2026_TB_DAL.<sha16>.csv` (same schema as
   the ATL@NO capture). The newest committed chart is 2026-09-14 and is not used.
3. **Week-4 box data**: nflverse player stats and snap counts for 2026 week 4 (at least 2026_04_GB_TB and
   2026_04_DAL_HOU; ideally the whole week) — the committed panel ends at week 3 for every club.
4. **Final injury designations** for both clubs (Wednesday's final report for TNF), with source URLs.
5. **Starting QBs** confirmed by a current team/depth source (provisional from the panel: Baker Mayfield TB,
   Dak Prescott DAL).
6. **FC Showdown context file** (optional; the field shadow and B4 need it).
7. **At the inactive deadline (~22:45Z Thu)**: the official inactive list
   `OFFICIAL_INACTIVES_TB_DAL_2026W5.json` + `.PROVENANCE.json` (OFFICIALLY_VERIFIED true only for an official
   team/NFL publication; its sha256 must equal the list's).
8. **After SEAL_PROPS, before kickoff**: the Hard Rock board `nfl/market/raw/HR_TB_DAL_BOARD_<UTC>.csv` with its
   `.CAPTURE.json` sidecar (book, jurisdiction, product, settlement_rules, captured_at_utc, captured_by,
   board_sha256).
9. **After the game, inside DK's 10-day window**: full-field standings for every contest entered (owner export), for
   `showdown_next_slate.py postgame`.

## REQUEST 2026-10-07 — weekly 2026 nflverse refresh for the sealed appearance shadow (and every projection)

The appearance successor sealed week-5 shadow predictions before the first kickoff
(nfl/prospective/appearance/APPEARANCE_SUCCESSOR_W5_SEAL.json, written 2026-10-07T15:22:07Z). To grade it, and to seal
weeks 6+ before their kickoffs (`python3.12 nfl/prospective/appearance/seal_appearance_w5.py --week W`), the repo needs,
each week after Monday night: nflverse 2026 player stats (weekly), snap counts, and play-by-play for the completed
week, so nfl/derived/USAGE_HISTORY_2021_2026.json can be rebuilt with that week's rows. Today the panel ends at 2026
week 3 for every club (week 4 is missing). Save under nfl/postgame/raw/role_audit_history/ (or the existing
nfl/vintage capture convention) with sha256 provenance rows; push to claude/nfl-greenfield-architecture-stsxmk.

## UPDATE 2026-10-07 17:20Z — TB@DAL: captured here, still needed from you

**Now captured in the repo (no longer needed):** nflverse depth charts (2026-10-07T14:25Z), weekly rosters through
week 5, injuries with week-5 practice statuses, play-by-play weeks 1-4 (derived cache rebuilt, generation 2).

**TB starting QB is UNRESOLVED.** Baker Mayfield was INACTIVE in week 4 (thumb); Jalon Daniels started (30 att).
Mayfield is ACT on the week-5 roster and QB1 on the chart but DID NOT PARTICIPATE in the first week-5 practice report.
Please capture the official TB injury report designations as they publish (Tue/Wed for TNF; final status), with
source URLs, and any official team statement on the starter. Also watch: TB K Chase McLaughlin (groin, DNP).

**Still needed (unchanged):** the owner's DKEntries export + contest metadata (prize, fee, max entries, field size)
— DK is unreachable from here; the FC context file; the official inactive list + provenance at the deadline; the
Hard Rock board + capture sidecar after SEAL_PROPS; full-field standings after the game.

## UPDATE 2026-10-08 12:50Z — TB@DAL (kickoff 2026-10-09T00:15Z): still needed from you, in order

Captured here at 12:34Z (nflverse relay): week-5 formal statuses. **Baker Mayfield Out (thumb)**; TB also Out
Winfield, Morrison, Dennis; DAL Out Durant, Overshown, Shelton; Questionable Mingo, T. Smith. McLaughlin no status
(Full). Designations rebuilt from formal report_status only. Both TB QB precomputes are staged; Daniels is the leading
scenario, Mayfield is kept as a recorded counterfactual. Nothing below can be fetched from this container (NO_EGRESS).

1. **DKEntries export** `DKEntries_TB_DAL_SHOWDOWN_2026W5.csv` (any name; I rename to the sha16 form) **plus per
   contest: contest id, prize pool, entry fee, max entries per user, field size**. Blocks both precomputes.
2. **FC file** `THIRDPARTY_FC_showdown_TB_DAL_2026W5_CONTEXT_ONLY.csv` (ownership context only). Blocks both precomputes.
3. **Authoritative TB starter**: team announcement or reporter-of-record line naming the starting QB, with URL and
   capture time UTC -> `nfl/dfs/salaries/showdown_tb_dal/STARTERS_TB_DAL_2026W5.json` + `.PROVENANCE.json`
   (`CONFIRMED: true`, `source`, `sha256` of the starters file). The official inactive list also suffices.
4. **Official inactives** at ~22:45Z: `OFFICIAL_INACTIVES_TB_DAL_2026W5.json` + `.PROVENANCE.json`, with
   `OFFICIALLY_VERIFIED: true` only for an nfl.com/club official list (sha256 of the list). A relayed list is
   recorded as relayed and does not open the READY gate.
5. **After I post SEAL_PROPS** (final mode), before kickoff: Hard Rock board `nfl/market/raw/HR_TB_DAL_BOARD_<UTC>.csv`
   + `CAPTURE.json` sidecar.
6. **Postgame**: full-field standings zip per contest id.
