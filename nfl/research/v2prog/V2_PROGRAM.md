# V2 refinement program — live tracker

Master status for the overnight directive. **This file is the source of truth
for what is done, what is running, and what is blocked.** Updated as work
lands; the morning report is assembled from it.

## Scope honesty, stated once

The directive spans ten phases. Phases 2, 3, 4 and 7 are architecture programs
measured in weeks, not hours — a coordinated role-state model, a single causal
chain with duplicate owners removed, a hardened bitemporal data plane, and six
new product surfaces. **They will not all be finished by morning.** What this
night can honestly deliver is: Phase 1 largely closed, Phases 5, 6 and 9
substantially closed, and Phases 2, 3, 4, 7, 8 converted from ambitions into
specified, testable work with the first components built. The morning report
will say which is which rather than blurring them.

Per the directive's own rule: **V2 earns "better" only through structural
correctness plus chronological/out-of-time scoring.** Nothing here is promoted
because a number looks more reasonable.

## Standing constraints, applied to every item

- No tuning to DEN@KC. Its realized outcome is not in this repository — the
  2026 pbp capture predates kickoff and holds zero DEN or KC rows — and is not
  to be sought.
- No sportsbook, Hard Rock, Fantasy Cruncher or external projection as a
  predictive input, ever.
- Every seal preserved byte-identical; `board_pointer.verify_seal` checked.
- Any coefficient-changing or closure-changing implementation gets a **new
  candidate identity**. R8 and R9 are never edited.
- Every repair begins with a **failing reproduction test**.
- A blocked or refused invariant is a **failure to certify**, never a success.

---

## PHASE 1 — structural correctness

| # | item | state | owner | note |
|---|---|---|---|---|
| 1.1 | `f_weeks_since_appear` encoding | RUNNING | P1 | non-monotonic: None/0/9+ all encode 1.0000 |
| 1.2 | missingness semantics, every numeric | RUNNING | P1 | 12 `V1_NUMERIC` have indicators; this one does not |
| 1.3 | position/role-specific depth semantics | RUNNING | P1 | rank is offence-wide, ties break on `gsis_id` |
| 1.4 | QB starter/share calibration | RUNNING | P2 | PIT χ² 929.0 on 9 df; above P90 in 79% of games |
| 1.5 | QB cold-start share ownership | QUEUED | — | depends on 1.4 landing |
| 1.6 | QB rush composition | RUNNING | P3 | RB-only 2/1000; +QB rush 206–237/1000, max 9.69 |
| 1.7 | passing-credit generation | RUNNING | P4 | 27,564 impossible cells on 50 boards |
| 1.8 | impossible distribution tails | QUEUED | — | 680 cells above the 554-yd record, max 1,587 |
| 1.9 | integer count support | PARTIAL | — | 271,691 non-integer carry cells corpus-wide |
| 1.10 | rush ownership closure | RUNNING | P3 | category partition off by 8.43 / 10.20 carries |
| 1.11 | target ownership closure | QUEUED | — | |
| 1.12 | receiving/pass-event identity | QUEUED | — | |
| 1.13 | eligibility-before-choice-set | DONE (earlier) | — | gate replaced allocate-then-zero; 17.60 units |
| 1.14 | identity/name propagation | DONE (earlier) | — | 19/19 resolved with provenance |
| 1.15 | `.npz.gz` audit coverage | **DONE** | me | repair 7; cause was path depth, not extension |
| 1.16 | false-green BLOCKED/PASS paths | RUNNING | me | Phase 9 invariant manifest |
| 1.17 | temp staging leak | IN PROGRESS | me | `stage_inputs` mkdtemp, never removed |

## PHASE 5 — research artifact rebuild

| item | state | owner |
|---|---|---|
| Q7 scramble rebuild from raw PBP | RUNNING | P5 |
| Mark conclusions depending on defective Q7 fields INVALIDATED | RUNNING | P5 |
| Re-run 2025 forward-chained QB share study on corrected data | QUEUED | after P5 + P2 |
| Re-run appearance calibration with corrected features | RUNNING | P1 |

## PHASE 6 — distribution quality

Census exists (`nfl/research/v3/x1/`) and found: 27,564 impossible per-QB
cells on 50 boards; 680 cells above the all-time single-game passing record;
2,262 negative passing-yard cells all traceable to 1–2 completion donor games.
**Outstanding: report frequency by candidate and component**, and re-census
after the migration. No clipping anywhere.

## PHASE 9 — operations

| item | state |
|---|---|
| staging leak fix | IN PROGRESS |
| content-addressed reusable staging | IN PROGRESS |
| invariant-execution manifest (`required → executed → result`) | QUEUED |
| Tier-0 game-day board validation | QUEUED |

## Blocked information gaps

| gap | why | outbox |
|---|---|---|
| DEN@KC realized outcome | capture predates kickoff; executor halted | OUT-014 |
| Official inactives, all of week 1 | proxy 403 on every attempt; window closed unfilled | OUT-013 |
| Preseason / coaching usage signal | no such source family is captured | OUT-015 |

## Owner decisions needed

1. **Q9 frozen candidate re-freeze.** R3's `depth_vintage` repair moved three
   fitted blocks inside the Q9 import closure. Six checks are failing on
   purpose. Re-sealing to match the tree would be rewriting evidence.
2. **Coefficient-forfeiting repairs.** Items 1.1–1.3 and 1.4 each invalidate a
   frozen coefficient vector. New candidates are being registered rather than
   edits — but the ORDER in which they are promoted, and whether any is
   promoted at all, is an owner call.
3. **REPLAY_C1 namespace.** Excluded from corpus fences by name with a stated
   reason. Confirm that is intended.
