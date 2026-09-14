# EVIDENCE CEILING — the injury feed carries no publication clock

Branch **stopped**. Every other branch in the model-recovery directive
continues.

## What this branch was going to repair

`readiness.py` refuses a team whose injury rows all carry a blank
`report_status` (`INJURY_REPORT_INCOMPLETE`), and that refusal is
**game-scoped**: it cost the entire non-QB board for BUF@HOU, GB@MIN and
MIA@LV on 2026-09-13. Houston, Minnesota and Miami were the only three clubs
of 32 with nobody carrying a game designation.

The motivating observation is real. In the game-day capture
(`injuries.66e960ec81fccc6e.csv.gz`) Dallas carried four rows, **three of them
blank in `report_status` with `practice_status` filled**, and passed — only
because a fourth, unrelated player was designated `Out`. Houston's four rows
are structurally identical to those three. What separated the two clubs was
whether anybody happened to be designated, which is a fact about the club's
health rather than about whether the report was published.

## The repair I attempted, and why I withdrew it

I changed the condition to refuse only when a team's rows are blank in
**both** `report_status` and `practice_status` — the idea being that a
published row with no game designation carries a practice status, and an
unpublished one carries nothing.

Measured across all seven injury captures held in `nfl/vintage/`:

| capture | rows | teams | report filled | practice filled | **both blank** |
|---|--:|--:|--:|--:|--:|
| 0bc645a4b9aa6255 | 48 | 20 | 48 | 0 | **0** |
| 1bf460ad261559a8 | 11 | 2 | 0 | 11 | **0** |
| 272a3c5c04fa8579 | 29 | 4 | 5 | 29 | **0** |
| 66e960ec81fccc6e | 182 | 32 | 61 | 182 | **0** |
| 96dcc98e297a38ec | 139 | 30 | 8 | 139 | **0** |
| bfa4aa0ee7cde902 | 11 | 2 | 0 | 11 | **0** |
| cd7338473dd852d0 | 167 | 32 | 8 | 167 | **0** |

**`both blank` is zero everywhere.** The proposed condition would never fire
on any capture this repository holds, so it does not tighten the guard in one
place and loosen it in another — it removes it. That is a materially weaker
contract than the one it replaces and the measurement says so, so the change
is withdrawn and `readiness.py` is restored to `3f5fc82`.

## Why the distinction cannot be drawn from the feed we have

The two states that must be told apart are:

1. **Mid-week practice report.** `report_status` is legitimately absent
   because the final report is not out yet. Capture `cd7338473dd852d0`: 8 of
   167 rows carry a designation.
2. **Final report, nobody designated.** Capture `66e960ec81fccc6e`: 61 of 182
   rows carry one — but Houston's share of that is 0 of 4.

At the **slate** level the two are far apart (4.8% against 33.5% of rows
designated). At the **team** level they are identical: four rows, practice
status filled, no designation. Houston in the final capture and any club in
the mid-week capture are the same bytes.

The feed's columns are `season, season_type, game_type, team, week, gsis_id,
position, full_name, first_name, last_name, report_primary_injury,
report_secondary_injury, report_status, practice_primary_injury,
practice_secondary_injury, practice_status`. **There is no publication date,
no report-type field and no filing timestamp.** The capture's own
`retrieved_at` records when we fetched it, which is a different quantity and
does not substitute: a Friday fetch of a Wednesday report carries a Friday
clock.

A slate-level rule — "if enough of the slate carries designations the final
report is filed, so a team with none genuinely has none" — would work, but
"enough" is a fitted threshold with no derivation, and this project logs a
fitted constant as a bug rather than tuning one quietly.

## What would lift this ceiling

Any ONE of these, and the branch resumes:

1. **A publication or filing clock on the injury report itself** — the NFL's
   own report carries a date and a designation ("Wednesday practice report",
   "Friday final"). A feed or parser that preserves it resolves the ambiguity
   outright, per team, with no threshold.
2. **The official final injury report as its own source**, captured
   separately from the practice reports, so its presence IS the publication
   signal. `official_injury_report` already exists as a capture name in the
   source list; whether it carries the distinction has not been established.
3. **A historical series long enough to derive the slate-level rule rather
   than choose it** — enough weeks that the designated-row share is a
   measured bimodal separation with a derived cut, not a number picked to make
   three games pass.

This is written into `docs/AGENT_OUTBOX.md` because acquiring (1) or (2)
needs bytes from outside this checkout.

## What is NOT blocked by this

The other two instances of the same blast-radius defect class were repaired
and needed no new evidence, because they are pure scoping:

- `NONQB_PLAYER_FRAME_INCOMPLETE` — one player of 190 lacking a position cost
  NYJ@TEN its whole board. Now excluded by name under the exclusion limit
  `identity_resolution` already declares, and NYJ@TEN produces 34 players.
- `ALLOCATION_PLAYER_WITHOUT_APPEARANCE` — one player without an appearance
  draw cost CHI@CAR and CLE@JAX theirs. Now excluded by name, refusing only
  when a team would be left with nobody. Both games produce full boards.

So three of the six games that lost their non-QB board are recovered on
evidence already in hand, and three wait on this ceiling.
