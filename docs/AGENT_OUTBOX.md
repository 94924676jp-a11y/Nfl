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
