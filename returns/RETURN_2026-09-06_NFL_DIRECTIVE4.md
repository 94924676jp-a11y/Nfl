# Return: NFL Greenfield — Owner Directive 4

**Date:** 2026-09-06 · **Branch:** `claude/nfl-greenfield-architecture-stsxmk` · **Head:** `3455166`
**NFL-1 was not executed.** No NFL-2, simulator, DFS, market or Hard Rock work.
Original frozen constants and the original freeze record untouched.

**Both overrides accepted without argument.** Item 4 especially: I marked it PASS
because all five provenance fields existed. That is schema-correctness standing in
for semantic-correctness — the exact substitution this project exists to
eliminate — made inside the checklist written to catch it.

---

## 10. Final G0A score — first, because it gates everything

# **11 PASS · 1 FAIL · 0 DEFERRED**

**Item 4: CLOSED.** **Item 1: still FAIL, on the external dependency only.**

Test evidence: **829 assertions across nine files, 0 failing.**

---

## 1. Revised G0A status

`nfl/NFL_G0A_CHECKLIST.md` revision 3. Revisions 1 (2/12, mine) and 2 (12/12,
mine, owner-overruled to 10/12) preserved.

| # | Requirement | State |
|---|---|---|
| **1** | Kickoff-anchored capture scheduled and running | **FAIL** — external |
| 2–3 | Raw bytes before parse · append-only / content-addressed | PASS |
| **4** | Complete five-clock provenance | **PASS — closed this pass** |
| 5–12 | identity · quarantine · replay tests · validation · identifiers · draw schema · ordering · seal | PASS |

---

## 2. Exact changes closing item 4

**`nfl/identity/effective_scope.py`** — new. A scope carries what the source
pinned **and**, separately, any narrowing derived from it with method, evidence
and authority class. Refusals, each with its own code: `TOO_COARSE`,
`WRONG_WEEK` (prior-week reuse), `WRONG_TEAM`, `WRONG_GAME`, `WRONG_SEASON`,
`AFTER_FORECAST`, `EXPIRED`, plus per-kind construction refusals.

**Three rules enforced structurally, not by convention:**
- The raw `source_value` is **never overwritten**. Narrowing is additive.
- A derived value **may not wear source authority** — refused at construction.
- A `Derivation` must **say something**; empty method or evidence is refused.

**`registry.bound_from_series`** — new. Closes a file-level interval using the
next capture of the same source whose content hash differs. Deterministic and
evidenced, not guessed.

### The adversarial pass defeated my first attempt, and that is the main result

**D1 — the gate read the label, not the content.** `INSUFFICIENT_ALONE` was
`(ScopeKind.SEASON,)`, and only `GAME` and `WEEK_TEAM` required any content. So
**the item-4 artifact verbatim** — a bare season string — relabelled
`DATE_INTERVAL` with no interval, **certified use for any game in the season.**
One enum value. No derivation needed, so `DERIVATION_UNDECLARED` never fired.

**Relabelling is not narrowing, and a gate that reads a label is a gate on the
caller's honesty.** Both halves of the fix were applied rather than either:

1. Every kind declares the content it must carry → relabel refused at
   construction, with a distinct code per kind (a shared `CONTENT_MISSING` would
   be the code-reuse V7 proved sends an operator to the wrong place).
2. The gate asks `game_level_discriminators()` what the scope **holds**:
   a `game_id`, or a week **with** teams, or a **bounded** interval.

**D4** — `build_scope` ignored reachability, so `official_inactives` (never
successfully contacted) got a `SOURCE_PROVIDED / TEAM_GAME` scope that certified
a real game. `resolve()` refused to invent the endpoint while `build_scope()`
invented the semantics: the same defect in different clothes. Both refuse now.

**D3** — `build_scope` raised out of an Outcome-returning boundary, on the one
source item 1 depends on. Returns a named FAIL.

**D2** — `DERIVATION_UNDECLARED` checked an object existed, not that it said
anything. `method=''` passed.

### The honest consequence, stated not hidden

A season file narrowed only by its own `Last-Modified` is **FILE-level** and is
**correctly `TOO_COARSE`** for game-level certification — an interval open at the
top cannot separate two games in a season. That is the control working.
`bound_from_series` closes it from the vintage series; an **unsuperseded** vintage
stays `DEFERRED / VINTAGE_NOT_YET_SUPERSEDED` rather than being closed at "now",
which would make a scope look game-certifiable on the strength of when somebody
happened to ask.

---

## 3. Effective-clock semantics by registered source

| Source | Source pins | Derived to | Level |
|---|---|---|---|
| `depth_charts` | **EXACT_TIMESTAMP**, source-provided (`dt`) | — | game-certifiable once bounded |
| `injuries` | SEASON | DATE_INTERVAL from `Last-Modified`, `DERIVED_DETERMINISTIC` | FILE |
| `schedules` | SEASON | same | FILE |
| `weekly_rosters` | SEASON | same | FILE |
| `official_injury_report` | WEEK_TEAM *(expected)* | — | **no scope built** |
| `official_inactives` | TEAM_GAME *(expected)* | — | **no scope built** |
| `official_transactions` | EXACT_TIMESTAMP *(expected)* | — | **no scope built** |

The three official rows are **expectations about a verified endpoint, not facts
about bytes we hold**, and `build_scope` refuses them with
`SCOPE_UNAVAILABLE_UNVERIFIED_SOURCE`.

---

## 4. Item-4 adversarial test matrix

`nfl/tests/test_effective_scope.py` — **100 assertions, 0 failing.** All seven
required cases, plus the relabelling attack.

| Seeded violation | Required outcome |
|---|---|
| Capture effective for the exact game | **PASS** |
| Prior-week record reused for a later game | `FAIL / EFFECTIVE_SCOPE_WRONG_WEEK` |
| Season-only value, no narrowing rule | `BLOCKED / EFFECTIVE_SCOPE_TOO_COARSE` |
| Source value + legitimate deterministic narrowing | **PASS** |
| Derived applicability presented as source-provided | refused at construction |
| Information effective only after the forecast timestamp | `FAIL / EFFECTIVE_AFTER_FORECAST` |
| Cross-team record applied to another team's game | `FAIL / EFFECTIVE_SCOPE_WRONG_TEAM` |
| **Season string relabelled to a finer kind** | refused per kind at construction |
| **Well-formed but unbounded interval** | `BLOCKED / TOO_COARSE` — a finer label is not a finer fact |
| Derivation with empty method / evidence | refused |
| Scope expired before the forecast | `FAIL / EFFECTIVE_SCOPE_EXPIRED` |
| Unparseable timestamps | `BLOCKED`, not FAIL |

Load-bearing proofs bypass `game_level_discriminators`, `_parse`, the
`EffectiveScope` class, `WINDOWS`, `narrow` and `BY_NAME` — each removal makes
the detection vanish.

---

## 5. Event-anchored T−90 scheduler

`nfl/capture/schedule.py`, `nfl/tests/test_capture_windows.py` — **107
assertions, 0 failing.**

Each target declares its **own one-sided window**, opening at or after the moment
its artifact can exist. `missed_captures` **no longer accepts a `tolerance`
argument at all** — its removal is the fix.

| Target | Window |
|---|---|
| practice / final_status | deadline → **+20h** (the filed report stays the current vintage) |
| **inactives** | **T−90 → T−10, exactly 80 minutes** |

Verified: a 6-hourly poll cannot discharge T−90; a capture at or after kickoff
never can; a capture **before** a deadline discharges nothing.

**Two things the tests forced me to get right.** `satisfied_by` is now a pure
timing predicate and `discharges()` adds source authority — mixing them made a
timing check depend on registry state. And **per-game attribution** is required
for game-specific targets: one fetch of a weekly practice report serves every
game that team plays that week, but each game's inactives are its own.

**One assertion of mine was wrong in an instructive way**, corrected in place:
shifting three captures 5h earlier does **not** leave all three owed, because
Thursday−5h lands inside *Wednesday's* 20h window and discharging Wednesday there
is correct. The guarantee is narrower — **a capture never discharges its own
target early** — and that is now what is asserted.

---

## 6. Source interface, ready for the endpoint

`nfl/capture/registry.py`. All three official sources are **registered, wired to
the targets they can discharge, and carry their scope semantics — with no URL.**
Adding a verified endpoint is a **one-line registry edit**; no scheduler change.

**No endpoint was invented.** A guessed URL that 404s is indistinguishable from a
real one that is down, and that difference is the whole point of the state.

`can_discharge('injuries', 'inactives')` is **False** by design — a terminal
weekly snapshot is not the intraweek cascade, so a mirror poll can never appear
to satisfy a deadline it cannot serve. `nfl/tests/test_source_registry.py`:
**133 assertions, 0 failing.**

---

## 7. `NFLVERSE_INJURY_SOURCE_STATUS_CONFLICT` — OPEN

`nfl/NFLVERSE_INJURY_SOURCE_STATUS_CONFLICT.json`. Recorded, not decided.
Measured here: `injuries_2025.csv` complete at 6,068 rows over 18 REG weeks.
Reported externally: died after 2024. Also measured: `injuries_2026.csv` 404.

The record states what must **not** be concluded — the 2025 file does not
establish 2026 availability, and a status sentence does not retire a row count.

**Effect on the build: none.** The mirror already discharges no intraweek target,
so the architecture is correct whichever way it resolves. Assigned.

---

## 8. `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` — OPEN

Unchanged and open, by design. `weekly_rosters.status` remains quarantined; the
escape hatch that once accepted it as a closing source is fixed and now returns
`ELIGIBILITY_SOURCE_NOT_RECOGNISED`. **NFL-1 remains outside the debt** —
team-level, consumes no player availability. Closes only via a declared source:
official inactives, transactions, or the gameday designation at publication time.

---

## 9. Does an external dependency still prevent item 1 passing?

**Yes, and it is the only thing preventing it.**

Every capture run now ends with:

```
UNMET CAPTURE TARGETS (no reachable source can discharge these):
  ['final_status', 'inactives', 'practice']
  pending endpoint verification: ['official_inactives',
    'official_injury_report', 'official_transactions']
```

nfl.com measures **000** from here. The T−90 half of item 1 is implemented and
tested and is **no longer part of why it fails**. What remains is an endpoint.

**More code in this repository moves none of it.** Recorded as outbox §34 with
what is already built, so returned evidence lands as a registry edit.

---

## What I would still flag

- **Item 4's verdict is mine and I have been generous once already.** The bar I
  applied: the machinery answers `assert_usable_for(game_id, forecast_timestamp)`,
  refuses every seeded violation including the relabelling attack, and produces a
  game-certifiable scope from a real vintage series. If your bar is instead *"a
  capture taken today certifies a specific game today"*, it is **not** closed —
  today's file-level captures correctly refuse, and only a bounded series
  certifies.
- Six of the eight cadences in the scheduler remain `confirmed=False`. Three of
  2026 week 1's four game days run on inferred calendars.
