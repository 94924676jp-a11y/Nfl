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

---

## Tick 2026-09-15T13:28Z — TASK ZERO, D20, and queue item 1

**Branch state.** Reconciled with `main` (`619a00bd`). Working HEAD `586c975`,
pushed and confirmed at the remote. Ancestry and verification in
`nfl/research/v4/TASK_ZERO_RECONCILIATION.md`.

### Landed

| | |
|---|---|
| **TASK ZERO** | 289 main commits, all capture evidence, zero code. 1368 blobs verified / 0 mismatches. 121 of 121 board seals recompute. |
| **D20** | Repaired. The inactives source served an empty page for nine days and passed 374 times; coverage was crediting 15 of week 1's 63 targets to it. |
| **D21** | Statistic built and proven. **Not wired** — every call site is sealed. |

### Two premises this tick destroyed

1. **`main` never stopped capturing.** The "executor halted 2026-09-11" reading
   came from a stale remote-tracking ref and had been load-bearing for four
   days, including in `OUT-011` and in seven test assertions.
2. **The DEN@KC inactives window was not unattempted.** Eight lawful in-window
   captures were made. They are empty. The miss stands, for a different reason.

### The thing to carry forward

Five successive claims I made this tick were wrong, and each was corrected by
looking one layer deeper than the last: branch → repository, manifest row →
blob, window → corpus, source → sibling source, and finally **my own fix → what
it deleted**. The fifth is the one worth keeping: a repair is a step that
returns something too, and mine returned a cleaner number by discarding the only
genuine inactives evidence in the store. Section 7 of the Task Zero artifact has
the full list.

And from D21: **a freeze is over the source file, not over behaviour.** A
diagnostic-only edit that cannot move a single draw still destroys the candidate
identity. "It does not change the numbers" is not a licence to edit sealed code.

### Queue status

| # | item | state |
|---|---|---|
| 1 | recon_error tautology | **statistic built and proven; wiring BLOCKED on a successor candidate identity** |
| 2 | R14 target published level | not started |
| 3 | track1 build_state_panel scrambles | not started |
| 4 | h1_frame reading the superseded q7 panel | not started |
| 5 | team_volume_v1 drift | not started |
| 6 | wire R10 to a board | not started |
| 7 | the 377 unconstructed refusal codes | not started |
| 8 | Tier-0 game-day board validation | not started |
| 9 | Phase 7 K and DST surfaces | not started |
| 10 | a confirmatory frame | not started |

### New, undiagnosed, and it belongs near the top of the queue

**Historical dry-runs are not stable across corpus growth.** The same 2024 game
now resolves to different vintage partitions than its own sealed rows
(`depth_charts@bd431f6c551c64e4` where the sealed row has `db0a09454965e6fc`,
and likewise for four other sources), because reconciliation brought newer
vintages and the selector takes the latest lawful one.
`test_q9_live_feature_builder` reports the same drift on four 2024/2025 games.
This is a reproducibility question and it is not yet diagnosed.

### Suite

129 modules, 1581 test functions, 8681 checks, **46 failing, 8 raised, 17
blocked** — measured on the merged tree *before* this tick's work, so it still
counts the six `test_capture_obligations` failures since fixed, and it does not
cover anything committed after it started. A re-run is in flight and is **not**
claimed here.

**V2 NOT YET EARNED**

---

## Tick 2026-09-15T15:10Z — D22, coverage truth, and the team-volume mechanism

Working HEAD `19e16d0`, pushed. Task Zero accepted and not reopened; merge
history, D20 semantics, every candidate freeze and every seal preserved.

### The D20 blast radius, answered

**The corruption was confined to capture and coverage reporting. No prediction
consumed a false inactive list.** All 13 real ingestions cite per-game
`nfl.com/news` articles; none cites `/inactives/`. Pre-inactives boards carry the
empty blob only as provenance, stamped 67.7 hours before kickoff, with no
inactive-derived key at all. The eligibility gate's `None` vs `()` distinction is
what protected it. Full record: `nfl/research/v4/D20_COVERAGE_CORRECTION.md`.

**The project already knew, on 2026-09-10.** The SF@LA ingestion record has a
field named `what_this_is_not` calling the landing page "a placeholder carrying
no list and the wrong document". Five days before D20 was found. The failure was
not discovery — it was **propagation**: the fact sat in one game's provenance
block and never reached the registry, the capture guard or the coverage reader.

Where it did reach: 83 artifacts name an empty blob in their consumed partitions,
so it enters identity fingerprints. Provenance, not input. Recorded, not
repaired — repairing it means re-sealing forecasts.

### Coverage truth

**28/63**, superseding 43/63. All 15 targets that moved are inactives targets;
nothing else moved either way. Of the 35 misses, 13 hold real game-anchored bytes
the ledger correctly refuses (delivered route, no declaration block) — an exact
13-to-13 match with the games holding an `INACTIVES_INGESTION.json` — and 22 have
nothing. Reading 28/63 as "we do not know who was inactive" would be a second
error in the opposite direction.

### D22 — the same hole in the other two content kinds

Both count the **envelope**. ESPN's injuries document scores 32 + 3 = 35 against
800 real entries, and still scores 35 with every team's list emptied. The csv
check counts rows and never looks at a column. No live corruption; a latent hole
closed. Contracts declared per source, both controls, bypass proof.

Two things it uncovered: the `SOURCE_HAS_NO_ROWS_YET` branch D20 kept unreachable
was **itself broken** (a `NameError` on an undefined `url`), and a test fixture
had been keying its player column `player` where the feed sends `gsis_id`.

### D21 — my framing was wrong, and the fourth seeded test is what showed it

Duplicated ownership: a duplication that **creates** units is caught by the old
`|sum − n|` (7.0) and is **invisible** to the new residual (1.83, inside its own
null). Theft that preserves the total is the exact reverse. **Neither statistic
dominates.** The old one is a *conservation* check and a correct one; what was
wrong was reading it as a check on the *allocation*, above all as a key named
`exact`. The successor reports both. `recon_error` is marked
`INVALIDATED_NON_INFORMATIVE_AS_AN_ALLOCATION_CHECK` — how it may be read, not
whether it may exist — and its 385,446 zeros stay so artifacts remain
reproducible.

**The successor candidate identity is still not built.** D21 stays
`repaired=False`.

### Team volume — the mechanism, confirmed

Two of five metrics carry a bias distinguishable from zero under team-season
block bootstrap, both positive, both feeding passing: `team_off_snaps` +0.996 ±
0.266 and `team_dropbacks_part` +0.605 ± 0.296.

It is **season drift**, monotone — dropbacks go −0.157, +0.856, +1.115 across
2023–25, *crossing zero*, which no fixed offset does. Confirmed directly: the
league mean of actuals falls 2.91 for snaps and 2.65 for dropbacks since 2020,
while `team_carries` moves 0.10 and `team_rz_carries` 0.13 — and **neither of
those carries a bias**. The two that drift are exactly the two falling fastest.
Every estimator in the family is an average of the past and none has a trend
term, so the selection could not have avoided it.

Week 1 is **UNDERPOWERED, not fine**: every Week-1 CI covers zero at n=96.

**Open contradiction, deliberately unresolved:** the autopsy has 2025 dropbacks
UNDER-projected by −1.3697; this has them OVER-projected by +1.115. Different
layers. If both hold, the intervening layers remove ~2.5 dropbacks per
team-game. Until that is decomposed, "team volume is biased" must name the layer.

### Regressions: all classified, none unexplained

Pre-existing (reproduced identically at `382556b` in a clean worktree):
`test_c1_denominator` 1, `test_q9_live_feature_builder` 5, `test_stat_contract`
1. **My earlier attribution of the candidate drift to the merge was wrong.**

Merge-*exposed*, not merge-introduced: `test_live_capture_den_kc` 1 — the
pre-existing dangling `raw/schedules.c563178ace7c6637.csv` reference became
reachable. Merge-caused: `test_persisted_provenance` 3, frozen counts moved by
corpus growth.

Fixed this tick: `test_capture_obligations` 3 (one of them an environment
dependence **I** introduced — asserting ambient liveness inside a harness that
isolates the state root), `test_p7_data_plane` 4 (stale premises).

Deliberate: `test_p6_false_greens` 17, `test_passer_credit_migration` 3.

### Not done, and not claimed

QB cold-start ownership, R14 pass-event single ownership, R10 to a board, track1
scramble repair, Tier-0 board validation, the data-plane DAG, the stacked V2
challenger. **Nothing promoted. R10–R13 remain isolated challengers with zero
boards between them.**

**V2 NOT YET EARNED**
