# SF@LA — FINAL PREGAME DATA INTEGRITY

**Game** `2026_01_SF_LA` · **kickoff** `2026-09-11T00:35:00Z` ·
**cutoff for everything below** `written_at = 2026-09-10T21:18:56Z`

Nothing here is promoted. The market appears once, as a comparator, and no
price entered any fit.

---

## 1. Live input freshness

Every source the forecast actually consumed, selected as the latest content
observed strictly before `written_at`.

| source | authority rank | vintage (sha16) | observed_at | basis | age at kickoff | refetches returning identical bytes | consumer | freshness verdict |
|---|--:|---|---|---|--:|--:|---|---|
| `schedules` | 99 ARCHIVE | `566d12fdc0fd173a` | 2026-09-10T21:08:02Z | capture_id | 3.45 h | 0 | kickoff, venue, team identity | **CORRECTED — see below. New bytes, unchanged game row.** |
| `espn_injuries_json` | 9 FALLBACK | `217444ecc1559baa` | 2026-09-10T17:05:23Z | capture_id | 7.49 h | 1 | not consumed by the model | stale but unused |
| `depth_charts` | 99 ARCHIVE | `db0a09454965e6fc` | 2026-09-10T12:07:17Z | capture_id | 12.46 h | **16** | R6 tier fallback, R7/R8 depth block | **CURRENT** — unchanged, not unfetched |
| `injuries` | 99 ARCHIVE | `96dcc98e297a38ec` | 2026-09-10T12:07:17Z | capture_id | 12.46 h | **16** | appearance injury features | **CURRENT** |
| `weekly_rosters` | 99 ARCHIVE | `3b0d5d40dc7816f7` | 2026-09-10T12:07:17Z | capture_id | 12.46 h | **16** | player frame; R5 pool via the raw blob | **CURRENT** |
| `official_injury_report` | **1 OFFICIAL** | `3aa790936d7e96f7` | 2026-09-08T17:06:03Z | capture_id | **55.48 h** | 38 | **nothing** | **STALE — pre-week page** |
| `official_inactives` | **1 OFFICIAL** | `88a19528350ea23f` | 2026-09-08T17:06:03Z | capture_id | **55.48 h** | 38 | **nothing** | **STALE — pre-week page, and tonight's list has not published** |
| `official_transactions` | 1 OFFICIAL | — | — | — | — | — | — | **ABSENT** `ENDPOINT_NOT_YET_VERIFIED` |
| `pbp_participation` | 20 MIRROR | — | — | — | — | — | — | **ABSENT** watch-only, 404 for 2026 |
| `snap_counts` | 20 MIRROR | — | — | — | — | — | — | **ABSENT** watch-only, 404 for 2026 |

### "Fresh" is not "recently retrieved", and the manifest proves it

A capture ran at `2026-09-10T21:08:02Z`, three and a half hours before kickoff.
It returned **byte-identical content** for `depth_charts`, `injuries` and
`weekly_rosters` — the same sha256 first seen at 12:07:17Z. The selector times a
source by the **earliest capture carrying that content hash**, so none of the
three moved forward, and the freshness column above says 12:07 rather than
21:08. The 16 refetches are a *measurement* that the football has not changed,
not evidence that it has.

`schedules` did change, **and I called it FRESH, which was wrong.** Its file
hash moves on nearly every capture because other games' rows churn. Hashing the
slice the model actually consumes — the single `2026_01_SF_LA` row — gives
`262533af14c12aec` across **all eight** captures from 15:11:56Z to 21:53:57Z:
same gameday, same 20:35 kickoff, same Melbourne Cricket Ground, same dome, same
matrixturf. The bytes moved eight times and the football did not move once.

The same slice test applied to every source the model reads:

| source | file hash moved | SF@LA consumed slice | rows | moved |
|---|--:|---|--:|---|
| `schedules` | **8×** | `262533af14c12aec` | 1 | **no** |
| `weekly_rosters` | 0 | `fe00c25f08623c12` | 181 | no |
| `injuries` | 0 | `4cdf7f67265e0b24` | 18 | no |
| `depth_charts` | 0 | `62652f7f9b0eb85d` | 140 | no |

**No new football information about SF@LA has arrived since 2026-09-10T15:11:56Z**,
about 9.4 hours before kickoff. A file hash answers "did the vendor's bytes
move"; only the consumed slice answers "did our football move", and for a
league-wide file those are different questions.

### The selection bound was wrong and is repaired

`information_set.build` selected against **kickoff** and `make_board` then
*refused* the whole board if the selected observation turned out to be later
than `written_at` (`SOURCE_AFTER_WRITTEN_AT`). Those are two different
situations: "no lawful vintage exists at this cutoff" is a refusal; "a newer
capture landed between `written_at` and kickoff" is ordinary, and the correct
earlier vintage is sitting right there. On a night when captures are still
running, the second case refuses a board it should have produced. Selection is
now bounded by `min(written_at, kickoff)` and the old check is retained as a
proof that selection did its job.

---

## 2. Semantic correctness

### `status == ACT` is roster membership, not tonight's list

| SF + LA, week 1 | ACT | DEV | RES | CUT | EXE |
|---|--:|--:|--:|--:|--:|
| players | **105** | 34 | 21 | 20 | 1 |

105 ACT across two clubs; each club dresses at most 48. `ACT` cannot be and does
not claim to be tonight's active list.

### `INA` is a gameday OUTCOME, and tonight's file contains a live example

The selected roster capture (`3b0d5d40dc7816f7`, observed 12:07:17Z) carries
**14 `INA` rows for week 1 — 7 NE and 7 SEA**, the two clubs whose game was
played Thursday night, and **zero for SF or LA**. So an `INA` row is not merely
undesirable data: for a team in scope it is *proof that the capture is
post-kickoff for that team*.

**This was an unguarded path.** `active_pool` dropped **any** non-ACT code and
labelled it "not on the active roster"; `INA` was not in the excluded-codes
table, so an inactive player would have been filtered out silently, under a
generic label, using the outcome. It did not bite tonight only because SF and LA
have not played yet.

Repaired:
* `roster_status.POSTHOC = {'INA': ...}` and `status_map` refuses with
  `ROSTER_STATUS_POSTHOC_CONTAMINATION`, naming the players and the counts;
* `active_pool` now drops **only** the four declared codes (DEV, RES, CUT, EXE);
  anything unrecognised is **kept and named** under `kept_unrecognised_status`,
  because dropping on a code we do not understand is the forcing-concentration
  move R5 exists to avoid.

### Injury designation is not inactivity

SF + LA week 1 carries **three** designations in total: `Out` 2,
`Questionable` 1, blank 15. Those three are **Aaron Donald (LA, DT)**,
**Alfred Collins (SF, DT)** and **James Thompson Jr. (SF, DE)** — **all
defenders**. Not one offensive skill player on tonight's board is governed by an
injury designation, so the appearance model's injury features are inert for
every player in the comparison below. That is worth knowing before reading any
of it.

The designation enters the model as a **feature**, never as a status. The
resolution of a designation into 0/1 is what the inactive list does, and the
list has not published.

The 2025+ injury schema carries **no `date_modified`**, so these rows have no
clock of their own and are timed by the capture that observed them. Where that
distinction matters it is stated rather than assumed away.

### Depth belongs to the right team, date and week

`depth_vintage.captured` selected the `2026-09-10T12:01:46Z` ESPN daily chart
for both clubs — 9.47 h before the cutoff, 20 skill players listed for SF and 19
for LA. Selection is the newest snapshot **strictly before** the clock; a clock
before every snapshot is `DEPTH_PIT_UNAVAILABLE`, a deferral, not a fallback to
the newest. Today's chart is never substituted for an older game.

### Depth is for role; the roster is for the pool

39 skill players are depth-listed against 105 ACT. Neither overrides the other:
the roster forms the **pool** and the depth chart informs the **role**, and
conflating them is what would let a depth chart become an eligibility list.

### Pass snaps are pass snaps

`GAP-ROUTES` records `s_pass_snaps` as an **upper bound** on route
participation — "a player on the field for a dropback may block" — and
FTN-S1 measured WR route participation at 0.989, a structural null. Nothing in
the production layers renames one as the other.

### Transactions and team changes

The frame keys every row by `(season, week, team, player)` and carries
`f_team_change` as its own feature. 585 of 1,353 players in the frame appear
for more than one team across seasons, and their history follows the *player*
while the team stays a column rather than an assumption.

### DEV / RES / CUT cannot re-enter the pool

The R5 filter runs on the roster; the R6 role prior, R7 depth block and R8
reliability weighting all operate **inside** the pool R5 produced. No later
stage re-adds a player, and `layers.targets_carries` refuses by name
(`ALLOCATION_PLAYER_WITHOUT_APPEARANCE`) if a player reaches allocation without
an appearance draw.

---

## 3. Source precedence

**Derived from `nfl/capture/registry.py`, not invented for tonight.** Every
source already declares an `authority` and an `authority_rank`.

| rank | authority | sources | reachable from this executor |
|--:|---|---|---|
| **1** | OFFICIAL | `official_inactives`, `official_injury_report`, `official_transactions` | **NO** |
| 9 | CANDIDATE_FALLBACK | `espn_injuries_json` | **NO** (`LOCAL_PROXY_CONNECT_403`) |
| 20 | INDEPENDENT_MIRROR | `pbp_participation`, `snap_counts` | yes, but 404 for 2026 |
| 99 | ARCHIVE | `depth_charts`, `injuries`, `schedules`, `weekly_rosters` | yes |

**Sources at rank ≤ 9 reachable from here: NONE.** Everything the model consumes
tonight is rank 99.

Measured at 21:08Z: `https://www.nfl.com/inactives/` → HTTP **000**,
`https://www.nfl.com/injuries/` → **000**,
`https://site.api.espn.com/...` → **000**, `https://github.com/nflverse/...` →
**200**. Egress is host-restricted, not absent.

**The rule for tonight**, in force order: official inactive publication beats
official club report beats point-in-time roster/depth beats third-party
aggregation beats reporter expectation. Where the higher-ranked source is
unavailable the lower one is used **and the substitution is recorded**, never
silently promoted.

---

## 4. Conflicts and resolutions

| field | source A | value A | time A | source B | value B | time B | chosen | authority reason |
|---|---|---|---|---|---|---|---|---|
| who dresses tonight | `weekly_rosters.status` | 105 ACT | 12:07:17Z | `official_inactives` | not available | 2026-09-08T17:06:03Z | **NEITHER** | ACT is roster membership; the rank-1 list has not published and the held blob predates the week |
| player availability | `injuries.report_status` | Out 2, Q 1 | 12:07:17Z | `weekly_rosters.status` | ACT for all three | 12:07:17Z | **BOTH** | they answer different questions; a designation is not a status |
| who is on the field | `depth_charts` (ESPN) | 39 skill listed | 12:01:46Z | `weekly_rosters` | 105 ACT | 12:07:17Z | **BOTH** | depth for role, roster for pool |
| injury designation | `official_injury_report` (rank 1) | 55 h stale | 2026-09-08T17:06:03Z | `injuries` (rank 99 mirror) | Out 2, Q 1 | 12:07:17Z | **mirror** | the rank-1 source is unreachable and its held blob predates the week; the substitution is recorded here |

No conflict was resolved silently.

---

## 5. Official inactive completeness

**REFUSED. `POST_INACTIVES_COMPLETE` is not claimed.**

The list publishes at about `2026-09-10T23:05:00Z` and **cannot be fetched from
this executor**. The request is filed as **OUT-007** in `docs/AGENT_OUTBOX.md`
with the deadline, the exact bytes needed, both clocks, and an explicit
instruction not to substitute a reporter or a price.

The machinery it would feed is **built and proven** —
`nfl/production/nonqb/inactives.py`, 40 checks in
`nfl/tests/test_inactives_propagation.py`:

1. raw bytes stored **before** parsing, gzip round-tripped to the exact input;
2. sha256 of those bytes recorded; content-addressed blob; append-only manifest;
3. publication and retrieval clocks kept as **separate fields**;
4. game identity carried on the capture row;
5. **both** clubs required — one missing is `POST_INACTIVES_INCOMPLETE`,
   DEFERRED, naming the club;
6. identity resolved against the same roster vintage the forecast consumed; a
   name matching two rostered players is `INACTIVES_IDENTITY_AMBIGUOUS`, a FAIL;
   an unmatched name is reported, never guessed;
7. explicit ACTIVE / INACTIVE sets;
8. propagation into appearance (below);
9. downstream re-run;
10. a new artifact — **no earlier shadow board is overwritten or relabelled**.

### A defect this module produced in itself, and the guard that now prevents it

The first run of these tests wrote a **70-byte synthetic inactives blob and four
manifest rows stamped 23:05Z into the live vintage**, and the information-set
selector immediately began choosing that file as tonight's official list. The
rows were removed, the blob deleted, `store()` now takes a `root` so tests
cannot reach the live vintage, and
`test_the_live_vintage_was_not_touched_by_this_module` fails if it ever happens
again.

---

## 6. Inactive propagation

Seeded, with the inactive player's own club and the opposing club both checked.

| assertion | result |
|---|---|
| an inactive WR appears in **no** draw | sum over 200 draws = **0** |
| the same for an inactive RB | 0 |
| the same for an inactive TE | 0 |
| every other player's draws are **bit-identical** | yes |
| the opposing club is untouched | yes |
| an inactive not in the draw set is **counted**, not ignored | yes |
| an empty list is `NOT_APPLICABLE`, not a successful application | yes |
| zero appearance **forces** zero share in the accounting | PASS |
| **an inactive player holding share is REFUSED** | FAIL, as required |

**Redistribution adds nothing.** Zeroing the appearance draws is the whole
intervention. `accounting.reconcile_nonqb` already enforces `share == 0 wherever
appearance == 0` per cell and the P4C simplex renormalises over the survivors,
so the opportunity moves by the configuration's **own declared mechanism** —
proportional renormalisation under every candidate today. A bespoke reallocation
here would be a second, undeclared model of substitution, which is what Track 3
exists to test properly.

---

## 7. Chronology and freshness guards

| refuses | code | state |
|---|---|---|
| post-kickoff inactive list | `INACTIVES_POST_KICKOFF` | FAIL |
| depth data with no snapshot before the clock | `DEPTH_PIT_UNAVAILABLE` | DEFERRED |
| depth selection with no clock at all | `DEPTH_PIT_NO_CLOCK` | FAIL |
| a snapshot exactly **at** the clock | selects the earlier one | proven |
| one-sided inactive completeness | `POST_INACTIVES_INCOMPLETE` | DEFERRED |
| a team absent from the captured document | `INACTIVES_TEAM_NOT_REPRESENTED` | DEFERRED |
| ambiguous duplicate player mapping | `INACTIVES_IDENTITY_AMBIGUOUS` | FAIL |
| empty capture bytes | `INACTIVES_EMPTY_BYTES` | FAIL |
| a capture with no retrieval clock | `INACTIVES_NO_RETRIEVAL_CLOCK` | FAIL |
| post-hoc roster status in scope | `ROSTER_STATUS_POSTHOC_CONTAMINATION` | FAIL |
| a roster capture later than the cutoff | `ROSTER_STATUS_NO_ELIGIBLE_VINTAGE` | BLOCKED |
| **a `written_at` in the future** | `WRITTEN_AT_IN_THE_FUTURE` | **NEW** |
| a source observed at or after `written_at` | `SOURCE_AFTER_WRITTEN_AT` | retained |
| stale content restamped by a newer retrieval | timed by first-seen hash | proven, 16× tonight |

### The future-`written_at` guard, and why it exists

Every clock in `make_board` was guarded except `written_at` itself. Measured at
`2026-09-10T21:19:30Z`: the first tournament tonight was sealed claiming
`written_at = 21:30:00Z`, **eleven minutes ahead of the wall clock**, and nothing
objected. That artifact asserted a provenance that had not happened, and a
future cutoff silently *widens* the information set — any capture landing before
it would be admitted as though available at write time.

The error was mine. The tournament was re-run at `21:18:56Z`, and the draw
artifacts came back **identical** (no capture landed in the interval), so no
number changed — but the provenance is now true, and the guard makes the class
of error unavailable.

---

## 8. Same-cutoff candidate tournament

All five at `written_at = 2026-09-10T21:18:56Z`, kickoff `2026-09-11T00:35:00Z`,
1,000 draws, seed 20260908, identical source vintages, identical teams.
**Differences below are model differences.**

| configuration | run id | draw artifact | sealed |
|---|---|---|---|
| `V1_CANDIDATE` | `902773709d0d7212` | `39576c0d74ce5f66` | `nfl/research/live/2026_01_SF_LA/pre_inactives_V1_CANDIDATE/` |
| `V1_CANDIDATE_R5` | `5acd5ed656da2ea5` | `abdaa2ca1684679f` | `…pre_inactives_V1_CANDIDATE_R5/` |
| `V1_CANDIDATE_R6` | `ed926983745479e8` | `35411f11b3b53ad5` | `…pre_inactives_V1_CANDIDATE_R6/` |
| `V1_CANDIDATE_R7` | `36d437ecc21c71f7` | `d5c89c813302743c` | `…pre_inactives_V1_CANDIDATE_R7/` |
| `V1_CANDIDATE_R8` | `7e6a57e748975203` | `b4b135117bff90d1` | `…pre_inactives_V1_CANDIDATE_R8/` |

Per-team QB dropback closure: **CLOSES, 2,000 cells, 0 violating, worst 0.0** on
all five. QB pass attempts identical to `0.000000` across all five.

### P(appear)

| player | V1 (full roster) | V1 / R5 / R6 (R5 pool) | R7 | R8 |
|---|--:|--:|--:|--:|
| Christian McCaffrey | 0.9743 | 0.9743 | 0.8492 | **0.9499** |
| Kyren Williams | 0.9509 | 0.9509 | 0.8525 | **0.9008** |
| Puka Nacua | 0.9469 | 0.9469 | 0.7682 | **0.8918** |
| George Kittle | 0.9454 | 0.9454 | 0.8490 | **0.9497** |
| *pool mean* | 0.8346 (n=99) | — | 0.6587 (n=28) | **0.8575 (n=28)** |

V1, R5 and R6 all run the **frozen** appearance mechanism — only the pool
differs — so their P(appear) is identical by construction. Quarterbacks do not
pass through this layer at all (`qb_accounting.py:377`), so Stafford and Purdy
have no P(appear) under any candidate.

### Architecture delta, V1 → R5 → R6 → R7 → R8

Mean, with p10 / p50 / p90 from the stored draws.

| player · metric | V1 | R5 | R6 | R7 | **R8** |
|---|--:|--:|--:|--:|--:|
| Stafford attempts | 30.266 | 30.266 | 30.266 | 30.266 | **30.266** |
| Stafford pass yds | 218.3 | 224.6 | 224.6 | 223.1 | **221.8** |
| Purdy attempts | 26.708 | 26.708 | 26.708 | 26.708 | **26.708** |
| Purdy pass yds | 203.1 | 205.5 | 207.7 | 212.0 | **210.7** |
| McCaffrey carries | 7.29 | 9.53 | 12.23 | 12.92 | **11.98** |
| McCaffrey targets | 3.14 | 4.43 | 4.71 | 5.12 | **4.53** |
| McCaffrey receptions | 2.56 | 3.60 | 3.85 | 4.17 | **3.70** |
| McCaffrey rec yds | 21.9 | 31.8 | 34.5 | 37.4 | **32.9** |
| Kyren carries | 6.68 | 11.19 | 11.21 | 10.99 | **10.84** |
| Kyren receptions | 1.06 | 1.47 | 1.66 | 1.69 | **1.45** |
| Nacua targets | 4.99 | 7.30 | 7.97 | 6.85 | **6.82** |
| Nacua receptions | 3.56 | 5.24 | 5.73 | 4.93 | **4.91** |
| Nacua rec yds | 47.0 | 69.3 | 76.0 | 65.1 | **64.7** |
| Kittle targets | 3.24 | 4.83 | 5.12 | 5.68 | **5.13** |
| Kittle receptions | 2.44 | 3.64 | 3.88 | 4.28 | **3.89** |
| Kittle rec yds | 31.9 | 47.2 | 51.0 | 56.5 | **51.3** |

**A tail worth noticing.** R7 puts **p10 = 0.0** on McCaffrey's carries, Kyren's
carries, Nacua's receptions and Kittle's receptions — its lower appearance
probabilities generate draws in which the player does not play at all. R8's p10
is non-zero for all four. That is R8's better-calibrated appearance showing up
directly in the left tail rather than only in a mean.

---

## 9. Pre-versus-post inactives delta

**NOT AVAILABLE.** No inactive list has been obtained, so there is no
information delta to report. It is not zero — it is unmeasured, and the two must
not be confused. The pre-inactives boards stand, labelled as pre-inactives
shadow boards.

The two deltas are kept apart on purpose: everything in §8 is an
**architecture** delta at one fixed information set, and nothing in this
document is an **information** delta.

---

## 10. Refusals and unresolved data

| item | state | why |
|---|---|---|
| tonight's official inactives | **BLOCKED** | `NO_EGRESS`; filed as OUT-007 |
| official club injury report | **BLOCKED** | `NO_EGRESS`; held blob is 55 h stale |
| `official_transactions` | **ABSENT** | `ENDPOINT_NOT_YET_VERIFIED` |
| `pbp_participation`, `snap_counts` for 2026 | **ABSENT** | 404 upstream; watch-only |
| `POST_INACTIVES_COMPLETE` | **REFUSED** | the label requires both clubs |
| per-game perishable capture windows | **20 of 63 missed** | recorded by the coverage check; not recoverable |
| external Perplexity report | **NOT SUPPLIED** in this mission | the only market snapshot available is the sealed MKT1 one from earlier; nothing new was benchmarked |
