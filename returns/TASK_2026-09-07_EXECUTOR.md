# Task report — owner decisions + the executor

**Date:** 2026-09-07 · **Repo:** `94924676jp-a11y/nfl` @ `bba7ebf`
**Tests:** 911 assertions, 0 failing · **NFL-1 not executed**

---

## What was asked

1. Retire the duplicate `nfl/` tree from the MLB repo, preserving history with a
   pointer rather than pretending it never existed.
2. No NFL-1 waiver — Item 1 protects perishable evidence.
3. **Highest priority:** get one real executor with outbound access to NFL.com,
   integrate it into the raw-byte → clock → hash → manifest → seal chain, and
   prove it can execute the T−90 window.

---

## 1. Duplicate retired — done

Verified **before** deleting: all 58 files under `nfl/` and all 5 return records
present in this repository. The comparison came back empty in the direction that
mattered.

`NFL_MOVED.md` is the tombstone — where the work went, the commit it went at, why
it moved, and the platform-extraction drift hazard a reader would otherwise have
to reconstruct from a diff. **`v7/` and `v8/` untouched**, confirmed by diff.

MLB repo: `226c994`.

## 2. No waiver — recorded

Your reasoning held. Nothing was relaxed, and the gate went on to catch five real
defects (below).

## 3. The executor — found, integrated, proven

**GitHub Actions.** A mechanism that already existed rather than one invented:
you hold admin, its runners have unrestricted egress.

### Reachability, proven before anything was built on it

Run `34069329836`:

| Source | Result |
|---|---|
| `nfl.com/injuries/` | **HTTP 200, 328,961 bytes** |
| `nfl.com/inactives/` | **HTTP 200, 417,665 bytes** |
| ESPN injuries JSON | **HTTP 200, 8,996,076 bytes** |
| Content check | 126 team names, 35 status words, **no JS-shell marker** |

Server-rendered and parseable — not a shell returning a healthy-looking 200.

### The chain, end to end

Run `34069726496` → commit `33c34de`, **pushed by the runner itself**.
Verified after pulling it back:

| Link | Evidence |
|---|---|
| raw bytes | `official_injury_report...html.gz`, **328,961 bytes** raw |
| content is real | 4 "Did Not Participate", 4 "Limited Participation", 3 "Full Participation", 4 "Questionable" |
| clock | HTTP `Date`, attributed as `source_timestamp_header: "Date"` — never relabelled as `Last-Modified` |
| hash | **sha256 matches filename on both blobs** |
| manifest | append-only, 8 rows per capture, every source accounted for |
| unmet targets | **empty for the first time** |

### It then ran unattended, with no involvement from me

Cron fired at **00:44:55Z** → run `34070777638` → commit `5c892b8`, authored by
`nfl-capture[bot]`. All official sources PASS. **The inactives blob has a new
hash** (`220bbcbb…` vs `2fc477fa…`) — the page changed between 00:24 and 00:44,
so a real vintage series is forming. The injury report deduped correctly, adding
a manifest row and no blob.

**14 captures, 79 manifest rows.**

---

## What running it for real exposed

Five defects, none reachable from a local run because the sources were BLOCKED
before that code ever executed:

| # | Defect | Why it mattered |
|---|---|---|
| 1 | HTML treated as CSV | A JS shell returns a healthy 200 over nothing. Now fails closed on `HTML_SHELL_OR_EMPTY` |
| 2 | No `Last-Modified` on a rendered page | Refusing to backfill was right and would have blocked every HTML capture. `Date` is used and **attributed as a different clock** |
| 3 | Minified JSON is one line | 8,996,076 bytes read as "a header with nothing under it" |
| 4 | Capture scope declared `WEEK_TEAM` | A captured page has no week and no team — that is a **parsed row**. Refused construction, correctly |
| 5 | `retrieved_at` stamped at request time | Against a live origin the server's `Date` read **later** than our retrieval, asserting we held bytes before the source produced them. The provenance guard caught it |

**And one false green of my own, caught within a minute.** Marking the official
sources REACHABLE made `unmet_targets` report all three perishable targets as MET
while nothing had been captured — because it computed `met` from the
*declaration*. It is now evidence-based: a target is met when a source authorised
to serve it has a recorded PASS, and a BLOCKED row discharges nothing.

---

## Item 1 — not a self-declared PASS

Against your twelve-point proof:

| Points | State |
|---|---|
| 1–6, 8–11 | **Demonstrated on the live path** |
| **7** — attribute to game/team/week | **Partial.** A captured page is file-level. No parser exists, and writing one against markup nobody had inspected would be inventing the schema |
| **12** — event-anchored execution scheduled | **Scheduled and proven unattended**, but no real T−90 window has occurred — Week 1 opens 2026-09-09 |

The verdict is yours, and it is now auditable directly in the repository.

---

## Open

- **Point 7** needs a parser, written against markup that now exists in the repo
  as captured artifacts — which is the right order.
- **Point 12** completes on its own at the first Week 1 kickoff.
- `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` — open; may not be closed with
  `weekly_rosters.status`.
- Six of eight scheduler cadences remain `confirmed=False`.
- `sportsplatform/governance` and the MLB `v8/governance` now diverge silently;
  nothing compares them.

## Also done

`CLAUDE.md` added, carrying your standing instruction — **always produce a
markdown file when a task is finished, and send it** — plus the project rules,
the naming reason, the drift hazard and the frozen artifacts, so a future session
inherits them rather than reconstructing them.
