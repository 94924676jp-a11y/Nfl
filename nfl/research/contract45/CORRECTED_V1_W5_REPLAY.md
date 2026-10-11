# CORRECTED_V1 beside the incumbent: the W5 2026-10-11 replay, end to end (recorded 20:20 UTC)

- **What this is:** a post-lock replay. The corrected arm was built in an overlay, on the 16:17Z production state, with
  pre-lock evidence only.
- **What it is not:** something to enter or upload. No production file changed. The production PROJ, DRAWS, WORLDS
  and UPLOAD hashes are unchanged: 87f826b1…, 5dbe7836…, b6cec1bd…, cce6dfb5….

## Chain

| stage | tool | result |
|---|---|---|
| lock check | `classic_slate_pipeline.py --dry-run` | records `AFTER_LOCK` at 20:06:17Z, 186 min after the 17:00Z kickoff. A non-dry run refuses. |
| state | copied: production 16:17Z STATE | — |
| run | `classic_slate_run.py`, arm CORRECTED_V1 | PASS. 378 players × 2,000 worlds. Participation (PM-1/PM-3), QBCTX-DB1 volume, ECW-3 worlds. |
| book | `classic_research_book.py` | PASS. 409 cards, accounting PASS. |
| portfolios | `classic_portfolio.py`, plus reproA and reproB in parallel | PASS. MAX150 150/150, MAX20 20/20, MAX20 20/20. |
| verify | `classic_upload_verify.py` | PASS |
| release | `classic_release.py` | **BLOCKED**, as it must be: `BUILT_AFTER_LOCK`. Every other link holds. |

### Release record (re-evaluated after the two fixes below)

- Chain links: all 9 hold.
- World accounting: 0 violations on every law. The incumbent's 16:17Z worlds have 35,234 across 5 laws.
- The two 20-entry contests share 0 lineups. The incumbent's shared 20.
- Evidence: McLaurin is modelled (PM-3 φ). The unmodelled list is empty.
- Uncertified for these reasons, in addition to the block:
  - EVIDENCE_CURRENCY_UNCHECKED: no newer packet was supplied;
  - NOT_ORCHESTRATED: the stages were run one by one, because a ledgered run is refused after lock;
  - 6 open forecast defects: L4, W5-G18 (now partly conditioned), SIM-D10, PM-3 unvalidated, undesignated
    appearance, ECW predictive unvalidated.

## Two release defects the replay found, fixed (with tests)

1. **The note overrode the model.** The packet's "Restriction NOT MODELLED" note listed McLaurin as unmodelled even in
   the arm that modelled him. A model that consumed the player now supersedes the note, which was written about the
   incumbent engine. Test: `test_classic_release` 06b.
2. **A post-lock portfolio read CURRENT_BUT_UNCERTIFIED.** A lineup built at or after kickoff is now `BLOCKED`
   (`BUILT_AFTER_LOCK`). Test: `test_classic_release` 06, case g3.

## What the portfolios did with the information

Exposure is the share of lineups.

| player | incumbent 16:17Z (150 / 20 / 20) | CORRECTED_V1 (150 / 20 / 20) |
|---|---|---|
| Terry McLaurin WAS | 0.22 / 0.30 / 0.30 | **0.093 / 0.10 / 0.10** |
| Jayden Daniels WAS | 0.10 / 0.10 / 0.10 | 0.067 / 0.05 / 0.05 |
| Chris Olave NO | 0.447 / 0.55 / 0.55 | 0.427 / 0.55 / 0.50 |

- Identical lineups across the two arms: **0** of 190.
- Each arm's "expected best entry" and "P(any entry clears the bar)" are computed on **its own worlds**, so they are
  not comparable across arms and are not quoted as an improvement.

## What this does and does not show

- **Shows:** the participation evidence now reaches the lineups through the whole governed chain. The redistribution
  reconciles exactly (`test_contract45_integration` 04). The worlds satisfy every box-score law. Each contest is
  optimised on its own.
- **Does not show:** that either arm forecasts better or would have scored better. That is PREREG_ECW2 section 3:
  weeks 6-11, paired CRPS against the incumbent.
- Today's outcomes are not used to rate either arm.
