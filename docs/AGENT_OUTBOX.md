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
