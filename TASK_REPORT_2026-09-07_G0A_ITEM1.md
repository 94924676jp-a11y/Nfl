# Task report — G0A Item 1, Directive 6

**Date:** 2026-09-07
**Repository:** `94924676jp-a11y/nfl`, branch `main`
**HEAD:** `fb8d1cf`
**Verdict returned:** Item 1 **PARTIAL / PENDING REAL EVENT**. G0A stays **11/12**.
**NFL-1:** not authorized, not executed, and not requested.

---

## 1. Repository HEAD and test count

| | |
|---|---|
| HEAD | `fb8d1cf` |
| Commits added this task | `e2058ba`, `fb8d1cf` |
| Test suites | 15 (12 under `nfl/tests/`, 3 under `sportsplatform/governance/`) |
| Assertions | **1,078**, **0 failing** |
| Interpreter | python3.12 |

Enumerated from the filesystem, not from a number written down:

```
test_capture_schedule.py        99      test_source_registry.py    122
test_capture_states.py         107      test_volatility.py          32
test_capture_windows.py        107      test_outcome.py             47
test_coverage.py                50      test_provenance.py          21
test_denominator_validation.py  61      test_scorecard.py           25
test_effective_scope.py        100
test_identifier_mapping.py      61
test_injury_parser.py           85
test_quarantine.py              64
test_seal_ordering.py           97
```

The directive asked me to verify a previously reported 911 / 0. It reproduced
exactly at the start of this task (818 NFL + 93 platform). The 1,078 above is
that number plus the 167 assertions added here.

### Verification pass before changing anything

| Claim | Result |
|---|---|
| main HEAD | `4338fe5` at start, as reported |
| 911 assertions / 0 failures | reproduced exactly |
| Raw artifacts content-addressed | **19 of 21 verified**, 2 mismatched |
| MLB duplicate retired, tombstone points here | confirmed — `git ls-files nfl/` returns 0 files in the MLB repo; `NFL_MOVED.md` names this repository and the migration commit |
| Unattended capture evidence | confirmed — see §9 |

The 2 mismatches are the `.reduced.csv.gz` projections. Their filename hash
identifies the **source** file they were derived from, not the projection
itself. That is a documented weakness carried forward from the previous report,
not a new finding and not an integrity failure — but it does mean two blobs on
disk cannot be verified against their own names.

---

## 2. Live artifacts inspected

All captured by the GitHub-hosted runner, all content-addressed, all pushed by
`nfl-capture[bot]`.

| Source | Blobs | Bytes each | Notes |
|---|---|---|---|
| `official_injury_report` | 4 | 328,961 | real report content, 11 player rows |
| `official_inactives` | 4 | 417,665 | real page, no inactives published yet |
| `espn_injuries_json` | 3 | — | secondary, unpromoted |
| `schedules` | 7 | — | nflverse, source of kickoff times |
| `depth_charts`, `weekly_rosters` | 2 | — | nflverse, `.reduced` projections |

Manifest: 60 PASS rows. The injury report artifact carries 4 Did Not
Participate, 4 Limited Participation, 3 Full Participation.

---

## 3. Point 7 — parser architecture

`nfl/parse/injury_report.py`, `PARSER_VERSION = "official_injury_report/1.0.0"`.

Every selector was read out of the real 328,961-byte artifact. Nothing is
recalled page structure. The capture was deliberately done first so the parser
could be written against evidence.

The raw artifact stays authoritative. The parser is a pure downstream
transformation: it never writes to the artifact, and §J of the tests proves the
bytes, the file on disk, its mtime and the caller's own scope dict are all
unchanged after a parse.

Each `ParsedRow` keeps five compartments apart and never merges them:

```
raw_sha256          the 64-char digest of the exact bytes this row came from
parser_version      bumping it changes every downstream record identity
source_provided     what the page literally said
normalized          what we mapped it to, using a map the page supplied
derived             what we concluded, with method + evidence + authority
refusals            named debts carried on the row itself
```

Plus `transformation_id` (`NFLTX-…`), a digest over `(raw_sha256,
parser_version)` — the parser version is **inside** the identity, not recorded
beside it. That is the MLB M0 lesson applied: `SIM_FORMULA` excluded the corpus,
so substituting the input left `FP-ab18309e17e7e16e` identical and nothing could
detect it.

**Verified output on the real artifact:**

```
PASS REPORT_PARSED | 11 rows, 2026 week 1, 16 games;
                     refusals: ['PLAYER_GSIS_UNMAPPED']
```

All four `official_injury_report` blobs parse identically.

### A correction to my own earlier claim

The first version of this parser's docstring said the page carries "no kickoff
time, no game date". **That was wrong.** The page embeds a broadcast listing
payload with 79 `"StartTime"` values (ISO UTC), 79 `"EndTime"`, and 79
`"GameId"` UUIDs. I wrote it from the visible markup rather than the whole
artifact.

Parser 1.0.0 still does not consume it, and the reason is the count: **79
entries against the 16 matchup strips** the injury tables are organised by. The
correspondence is nowhere stated on the page, so joining them would be an
assumption presented as a field. `GameId` is also a broadcast UUID, not a gsis
or nflverse identifier, so it resolves no identifier debt. This is now a named
open item rather than a claimed absence.

What the page genuinely does not carry is any gsis identifier — **measured,
zero matches** for `00-0NNNNNN` across the whole artifact.

---

## 4. Exact attribution semantics

| Level | Established how | Authority |
|---|---|---|
| **Season / week** | `<option value="/injuries/league/2026/reg1" selected>` **and** independently the `<title>`. Both must agree. | derived, two agreeing signals |
| **Team** | The page's **own** matchup strips carry abbreviation and full name adjacent, so the document supplies its own name→abbr map. None is brought along. | derived deterministic |
| **Game** | Each strip names exactly two teams; a section's team must belong to the pair its table sits under. | derived deterministic |
| **Player** | Profile slug + display name only. | source-provided, identifier unresolved |

One signal is a claim; two agreeing is evidence. Where they disagree, neither is
used — `AMBIGUOUS_ATTRIBUTION`, refuse, do not choose.

Capture-level scope is never relabelled as row-level scope: `derived.authority`
is constrained to a derived class at construction, and a `derived` compartment
claiming `SOURCE_PROVIDED` raises `AuthorityViolation` — see §L of the tests.

---

## 5. Identifier failure / refusal behaviour

Named refusals, reusing the project's existing vocabulary rather than inventing
parallel terms:

`TEAM_UNMAPPED` · `GAME_UNMAPPED` · `PLAYER_UNMAPPED` · `PLAYER_GSIS_UNMAPPED` ·
`AMBIGUOUS_ATTRIBUTION` · `RAW_SHA256_MISMATCH` · `VINTAGE_MISREPRESENTED` ·
`CAPTURE_SCOPE_UNIDENTIFIED` · `PARSER_SCHEMA_DRIFT` · `PARSER_INPUT_EMPTY` ·
`NO_REPORT_ROWS_PUBLISHED`

**Every row today carries `PLAYER_GSIS_UNMAPPED`**, because the page has no gsis
identifier at all. No fuzzy-name fallback exists anywhere. Measured on the six
real unmapped MLB players, a name fallback recovers two, **silently mis-joins
two**, and fails two — so the refusal holds even for the rows it would have got
right.

A player listed twice under one team is two competing claims about one person's
status; both rows are flagged `AMBIGUOUS_ATTRIBUTION` rather than one being
silently kept.

---

## 6. Parser / schema-drift behaviour

Six structures are required. Any absence is `PARSER_SCHEMA_DRIFT` — a **FAIL**,
never an empty parse. A parser that returns `[]` against changed markup produces
plausible-looking nothing, which is worse than failing.

Proven to fail closed: truncated document · table markup changed · a column
added · a header renamed · the week selector removed · zero bytes · a JS shell ·
a consent interstitial · a 200-response error page.

**A truncation guard was added because the test exposed the gap.** The injury
tables sit early in the document, so the page truncated to half its length
parsed to a perfectly plausible eleven rows. `</html>` is now required.

Distinct from all of the above: structure intact, no player rows published yet →
`NOT_APPLICABLE[NO_REPORT_ROWS_PUBLISHED]`, whose detail says in words that it
**discharges nothing**. That is a real state early in a week and it must not
read as success.

The raw bytes are preserved unchanged so a future parser can reprocess every
historical artifact.

---

## 7. Adversarial tests added and results

**`nfl/tests/test_injury_parser.py` — 85 assertions, 0 failing.**
Sections A–N are the directive's fourteen requirements in order; section O is
the guard-deletion proof. Every mutation is the real page with one thing broken,
never a hand-written fixture — `_mutate` refuses if its target is not present in
the real artifact.

| # | Requirement | § | Result |
|---|---|---|---|
| 1 | real page parses | A | PASS |
| 2 | rows link to raw SHA-256 | B | PASS |
| 3 | team cannot cross teams | C | PASS |
| 4 | week cannot cross weeks | D | PASS |
| 5 | game cannot cross games | E | PASS |
| 6 | unknown identifiers fail closed | F | PASS |
| 7 | duplicate / ambiguous fails closed | G | PASS |
| 8 | malformed HTML fails closed | H | PASS |
| 9 | JS shell / empty fails closed | I | PASS |
| 10 | cannot modify the artifact | J | PASS |
| 11 | version changes transformation identity | K | PASS |
| 12 | cannot claim finer authority | L | PASS |
| 13 | earlier capture ≠ later vintage | M | PASS |
| 14 | parsing discharges nothing | N | PASS |

**Four guard-deletion proofs (§O).** Each deletes the control and replays the
same seeded violation:

| Control deleted | With guard | Bypassed |
|---|---|---|
| digest recomputation | wrong artifact caught | **not caught** |
| week cross-check made non-independent | disagreement caught | **accepted as week 7** |
| capture-scope check | foreign vintage caught | **rides along unexamined** |
| `Authority` validation | derived-as-source refused | **record constructed** |

**`nfl/tests/test_coverage.py` — 50 assertions**, and
**`nfl/tests/test_volatility.py` — 32 assertions**, both 0 failing, both with
their own guard-deletion sections. See §8 and §13.

### Four gaps closed so the tests could prove something

The requirements were not all testable against the parser as written. Rather
than write assertions that restated intent, I closed the gaps: transformation
identity with the version inside it; authority enforced at construction;
capture-scope cross-checked against the bytes; and an explicit
`discharges_capture_obligation` that can be refused.

---

## 8. T−90 scheduling implementation — **the main finding**

The directive asked me to verify that a generic periodic cron is not being
mistaken for fulfilment of the T−90 obligation. **It was being mistaken for it,
in one specific place.**

### The false green, measured before anything was changed

```
registry.unmet_targets('nfl/vintage_manifest.jsonl')
  -> {'unmet': [], 'met': ['final_status', 'inactives', 'practice'], ...}
```

All three perishable targets reported **MET**. At that moment:

- the earliest T−90 window was `2026-09-09T22:50Z`, **two days away**;
- **no window had opened**;
- **not one capture carried a game_id**.

The claim is true of the question `unmet_targets` actually asks — "was an
authorised source ever captured for this kind at all" — and false of the
question a reader takes it for. It has **no time dimension and no game
dimension**. Read as coverage it says a Sunday poll discharges a Thursday
kickoff's obligation.

Meanwhile `schedule._clears` was already refusing exactly that: for a
game-specific kind it requires the capture to carry the target's own `game_id`.
**Two modules, opposite answers to the same question, and the runner printed the
optimistic one.**

### What was built

`nfl/capture/coverage.py` joins the kickoff-anchored plan to the manifest and
makes the game-anchored answer the printed one. Both answers now appear, each
labelled:

```
SOURCE-LEVEL (has this kind ever been captured at all): met=[...] unmet=[...]
  This is NOT coverage. It carries no window and no game.

GAME-LEVEL COVERAGE  DEFERRED[NO_WINDOW_HAS_CLOSED_YET]
  targets=63 covered=0 missed=0 not_yet_due=63 game_attributed_captures=0/60
```

Covered means: a manifest PASS, from a source authorised for that kind, whose
`retrieved_at` is inside **this** target's window, attributed to **this** game.
Nothing weaker counts. An open window is DEFERRED, never MISSED.

**Guard-deletion proof:** reduce `_clears` to a timing check and **one
unattributed capture covers 16 targets**. That is the false green, made visible.

### Is the cron event-anchored? No, and frequency cannot fix it

`event_anchored()` returns `BLOCKED[PERIODIC_CADENCE_IS_NOT_EVENT_ANCHORING]`:
16 per-game targets, narrowest window 80 minutes, against a 30-minute cadence.
A 1-minute cadence returns the same refusal — **the missing thing is
attribution, not frequency**.

The workflow's own comment claimed a 30-minute cadence "lands at least twice
inside" the 80-minute window and treated that as fulfilment. That comment is
now corrected in place. Measured cron behaviour to date: **n = 3 scheduled
runs**, delays 14.8 / 5.5 / 6.7 minutes, actual gaps 20.7 and 31.2 minutes. n=3
supports no statement about GitHub's drop probability, and I am not making one.

**The T−90 → T−10 window is preserved unchanged**, and the distinction the
directive asked for is intact in `schedule.py`: T−90 is the official inactive
deadline; T−90 → T−10 is **our** engineering acceptance window, not an
externally verified NFL publication-latency fact.

### What still needs building, and is not built

An execution anchored on `schedule.next_target`, and a capture row carrying the
`game_id` it was taken for. I did not build it in this task. It is a change to
what the capture system executes, the directive said not to redesign the capture
system, and it is the piece that would make Item 1 provable — so it should be
authorized explicitly rather than slipped in. **Week 1 opens 2026-09-09T22:50Z,
about 45 hours from now.**

---

## 9. What is already demonstrated live

- Outbound reachability to nfl.com from a GitHub runner, 200 with real bytes.
- The full chain on real artifacts: raw bytes → clocks → sha256 →
  content-addressed blob → manifest row → push.
- **Unattended scheduled execution**: 3 runs with `event: schedule`
  (`34070777638`, `34071864329`, `34073576340`), no human in the loop, each
  captured and committed on its own.
- Append-only manifest: 60 PASS rows, nothing rewritten.
- Fail-closed capture states proven live: `NO_EGRESS`, `HTML_SHELL_OR_EMPTY`,
  `SOURCE_NOT_YET_PUBLISHED`, `ENDPOINT_NOT_YET_VERIFIED`.
- A working parser producing 11 attributed rows from the real page.

---

## 10. What still requires the first real kickoff-relative event

The chain the directive specified, end to end, **inside** T−90 → T−10:

```
scheduled event → runner execution → official retrieval → non-empty authentic
bytes → raw persistence → clocks → SHA-256 → manifest → correct game/team
attribution → authorized target discharge
```

Nothing before "correct game/team attribution" is in doubt; that link and the
one after it have never executed. **No qualifying window has occurred.** I have
not simulated one, and a manually dispatched run is not offered as equivalent.

Blocking on my side before the event can prove anything: the event-anchored
execution and the `game_id` on the capture row (§8).

---

## 11. G0A Item 1 verdict

**PARTIAL / PENDING REAL EVENT.**

Point 7 (parser) is proven on real captured bytes with 85 adversarial
assertions and four guard-deletion proofs. Point 12 (T−90) has not occurred and
— on today's wiring — could not be recorded as discharged even if it did,
because no capture carries a game attribution.

No waiver. No DEFERRED-as-PASS. No administrative closure.

---

## 12. G0A score

**11 PASS / 1 FAIL — unchanged.**

I found no basis to move it and did not look for one. The directive's rule is
explicit: Point 7 proven without a real qualifying T−90 event returns 11/12.

---

## 13. Open debts

| Debt | State | Note |
|---|---|---|
| `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` | **OPEN** | untouched. `weekly_rosters.status` remains forbidden. Capturing official pages does not close it. |
| `PLAYER_GSIS_UNMAPPED` | **OPEN** | zero gsis identifiers on the page, measured. Needs a crosswalk, not name matching. |
| Broadcast payload join | **OPEN, new** | 79 `StartTime`/`GameId` entries vs 16 matchup strips. Correspondence not stated on the page. |
| Event-anchored T−90 execution | **OPEN, blocking Item 1** | §8. |
| `game_id` on capture rows | **OPEN, blocking Item 1** | §8. |
| Blob dedup defeated by render nonce | **OPEN** | below. |
| `.reduced` blob hash names its source | **OPEN** | 2 of 21 blobs unverifiable against their own filename. |
| ESPN authority | **UNCHANGED** | still CANDIDATE FALLBACK. Not promoted. Discharges no official obligation. |
| `--store` outside the repo | **minor, new** | `_persist` raises `ValueError` on a non-repo store path. |

### Two defects found this task, one of them mine

**Mine, found an hour after I wrote it.** The manifest carries two schemas: 54
of 60 PASS rows nest the clock at `value.provenance.retrieved_at`, 6 older rows
carry `value.retrieved_at`. My `performed_from_manifest` read only the top
level — **kept 6 rows, dropped 54, reported `total_captures: 6` in silence**.
Class A, an absence read as a result, produced by the module written to prevent
Class A. It now reads both, and a PASS row with no clock anywhere **BLOCKS**
rather than being skipped. `requested_at` is not accepted as a substitute.

**The source's.** Four captures each of the inactives page and the injury report
produced **four distinct raw sha256 apiece and exactly one substantive page
apiece**. The pages embed per-request UUIDs (100 and 45, in `data-jsonid` and the
matching `<script id>`) that rotate every render. Two captures twenty minutes
apart differ on two lines, in the UUID only. So every `content_unchanged: false`
on those rows is a **fake new content version**, `bound_from_series` collapses
every vintage interval to a point, and at the first T−90 window the manifest
could not have distinguished *"the inactives list was published"* from *"the
nonce rotated"* — which is precisely the evidence that window exists to produce.

`nfl/capture/volatility.py` records a **derived** substantive digest beside the
authoritative sha256. It changes nothing about what is fetched or stored: blob
dedup still runs on the raw digest and the inflation continues, because changing
what the capture system stores is your call.

**And the error that rule almost made.** Its first version matched any
UUID-shaped string anywhere. Against the real payloads it neutralised **4,821
tokens in `weekly_rosters` and 272 in `schedules`** — `sportradar_id`, a real
column identifying a real player. That would have turned a genuine roster change
into a false "unchanged", the worse of the two errors. The rule is now anchored
to the two attribute positions where the nonce was measured, and §C of
`test_volatility.py` keeps that counter-case as a permanent test.

---

## 14. Exact files and commits changed

**`e2058ba`** — parser, its tests, coverage, workflow comment correction

```
A  nfl/parse/injury_report.py            364 lines
A  nfl/tests/test_injury_parser.py        85 assertions
A  nfl/capture/coverage.py
A  nfl/tests/test_coverage.py             42 assertions
M  nfl/tools/capture_vintage.py           game-level coverage in the report
M  .github/workflows/nfl-capture.yml      cadence claim corrected
```

**`fb8d1cf`** — the two defects

```
A  nfl/capture/volatility.py
A  nfl/tests/test_volatility.py           32 assertions
M  nfl/capture/coverage.py                manifest reader reads both schemas
M  nfl/tests/test_coverage.py             42 -> 50 assertions
M  nfl/tools/capture_vintage.py           substantive digest recorded
```

Nothing was deleted. No capture was rewritten. No existing artifact was touched.

---

## 15. May NFL-1 be authorized under the existing gate?

**No.**

G0A is 11/12 and the gate requires 12/12. Item 1 protects perishable evidence
that cannot be reconstructed later — the same reasoning you used in declining a
waiver — and the T−90 link is not merely unproven, it is currently
**unrecordable**, because no capture carries a game attribution.

I am not asking for a waiver and would not accept the checklist as green.

**What I would ask for instead, before Week 1 opens in ~45 hours:** authorization
to make the capture event-anchored and to put `game_id` on the capture row. That
is a change to what the capture system executes, which you told me not to
redesign, so I stopped and am asking. Without it the first real T−90 window will
pass and produce evidence that cannot be attributed — and unlike code, that
window does not come back.

---

## 16. Markdown task-report path

`TASK_REPORT_2026-09-07_G0A_ITEM1.md` (this file), at the repository root of
`94924676jp-a11y/nfl`, commit `fb8d1cf`.

---

*Stopping here, per the directive. NFL-1 not executed. NFL-2, projections,
simulation, DFS, market integration and optimization not begun. No wager
recommended or discussed.*
