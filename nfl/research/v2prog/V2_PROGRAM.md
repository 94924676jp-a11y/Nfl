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

| # | item | state | candidate | evidence |
|---|---|---|---|---|
| 1.1 | `f_weeks_since_appear` encoding | **DONE** | R10 | live collision is `None` vs 9+, not `0` — the value is generated 1-based (`i + 1`), so my "0 encodes to max" was a latent hazard, not a live defect |
| 1.2 | missingness semantics, every numeric | **DONE** | R10 | `featurise_r10` gives value+flag, explicit `is None`, monotone. **Left open one column over**: `f_n_teammates_out` still reads `or 0.0`, folding "no v1 block" into "zero teammates out" |
| 1.3 | position/role depth semantics | **DONE** | R10 | worse than diagnosed — a train/serve **scale break**: `weekly` groups within position, `daily` ranks offence-wide. One column held two quantities |
| 1.4 | QB starter/share calibration | **DONE** | R12 | rPIT χ² 32.481 → 8.667, bias −0.0778 → −0.0190, CRPS −1.298 [−2.198, −0.436] |
| 1.5 | QB cold-start share ownership | QUEUED | — | next tick |
| 1.6 | QB rush composition | **DONE** | R11 | 149→0 and 148→0 over-allocation, max excess 9.69 → 0.0000 |
| 1.7 | passing-credit generation | **DONE (42/50)** | — | 42 boards migrated to 0 impossible cells; **8 unmigratable**, named, 9,541 cells |
| 1.8 | impossible distribution tails | QUEUED | — | 680 cells above the 554-yd record, max 1,587; owned by `qb2_lib.py:306-307` |
| 1.9 | integer count support | OPEN | — | `rushing/carries` 63.4% non-integer; every `rtd>carries` cell is `0<carries<1` with `td==1` |
| 1.10 | rush ownership closure | **DONE** | R11 | and my 8.43/10.20 "non-closure" was a mis-specified comparison — it closes at 0.000000 |
| 1.11 | target ownership closure | QUEUED | — | |
| 1.12 | receiving/pass-event identity | QUEUED | — | |
| 1.13 | eligibility-before-choice-set | DONE (earlier) | R2 | |
| 1.14 | identity/name propagation | DONE (earlier) | — | |
| 1.15 | `.npz.gz` audit coverage | **DONE** | — | cause was **path depth**, not extension; 17 boards at depth 2 |
| 1.16 | false-green BLOCKED/PASS paths | RUNNING | — | P6; one already fixed by me (`assert_not_promoted` skipped R9/R10/R11) |
| 1.17 | temp staging leak | **DONE** | — | content-addressed; two processes now share one stage |
| 1.18 | **CONFIRMED LEAK — depth-chart chronology guard never executed** | **DONE** | — | `run_forecast.py:501` passed no clock; 74 of 79 week-1 kickoffs precede the selected chart |

## PHASE 5 — research artifact rebuild

Q7 rebuilt (`q7-panel-2`): scr **1 → 5,864**, db 116,190 → 122,053, player-games
agreeing with nflverse 1,518/4,024 → **4,047/4,056**, unexplained **2,506 → 0**.
The single scramble v1 held was one row double-counted as sack *and* scramble.
Receiver panel decompressed-identical — the control.

**Every published Q7 conclusion SURVIVES**: 588 of 1,003 quantities move, **0 of
60 significance flags and 0 of 4 verdicts**. Two numbers need re-issuing in
`Q7_DECISION.md` (COMPOSED decomposition; cold-start table) — not edited, not
mine. v1 superseded, never overwritten.

Re-run of the 2025 share study on corrected data: **still queued** (P2 used
`qb.pkl`, correctly, not the defective panel).

## PHASE 6 — distribution quality

Census done. **Headline corrected**: 36,587 impossible passing-line cells over
121 boards; 27,301 over the 109-board fence corpus; 9,286 in REPLAY_C1. The
figure 27,564 reproduces from no corpus. Outstanding: frequency **by candidate
and component**, and re-census after migration.

## PHASE 9 — operations

Staging leak fixed. Invariant-execution manifest RUNNING. Tier-0 board
validation QUEUED.

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
