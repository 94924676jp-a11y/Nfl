# Showdown historical performance report (deliverable D), 2026-10-08

**Evidence class: RETROSPECTIVE DEVELOPMENT, one game.** ATL@NO has already been used for development: the post-game
study, the TE-order fix and SC-OWN-ROTATION-1. Nothing here is held-out or prospective evidence.

**How portfolios were graded.**
- Every portfolio was built before it was scored, from sealed prelock worlds.
- Grading tool: `nfl/postgame/showdown_ab_grade.py`.
- **Ranks are exact** against the archived full fields. DraftKings ties share a rank.
- **Dollar figures are estimates** from the conservative curve built on the owner's own graded entries, because the
  prize table is absent. The curve is capped at the best observed entry and is unavailable for the 2-entry contest.
- Only the portfolio actually entered has an actual return, the owner's recorded winnings.

## ATL@NO, by contest

| Portfolio | Contest | Entries | Fees | Best pts | Exact best rank (field) | Top 1% | Est. payout | Actual return | Overlap with production |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Production v2** (`8f4d9a77`) | 196285137 (150-max) | 150 | $75.00 | 142.54 | **6** (237,812) | 4 | $131.94 (curve) | **$134.47** | 150 |
|  | 196285160 (20-max) | 20 | $5.00 | 110.45 | 9,748 (47,562) | 0 | $1.00 | **$1.00** | 20 |
|  | 196285161 (2-max) | 2 | $0.20 | 98.44 | 29,262 (59,453) | 0 | n/a | **$0.00** | 2 |
| Historical reproduction (`b0a2b57b`) | all | 172 | $80.20 | identical | identical | identical | identical | (not entered) | 172 / 172 |
| Incumbent `66990085`, point-in-time data | all | 172 | $80.20 | identical | identical | identical | identical | — | 172 / 172 |
| P0 `0ea3bc21`, point-in-time data | all | 172 | $80.20 | identical | identical | identical | identical | — | 172 / 172 |
| C1 `_chart_rank`, point-in-time data | all | 172 | $80.20 | identical | identical | identical | identical | — | 172 / 172 |
| **Incumbent on post-lock data (drift)** | 196285137 | 150 | $75.00 | 132.15 | 1,377 | 2 | $44.00 (curve) | — | **27** |
|  | 196285160 | 20 | $5.00 | 114.09 | 7,700 | 0 | $1.00 | — | 7 |
|  | 196285161 | 2 | $0.20 | 98.44 | 29,262 | 0 | n/a | — | 2 |

**Production, aggregate:** $80.20 in fees, **$135.47 actual return**, net +$55.27 on one game.

## Reading this correctly

1. **The P0 repairs and C1 produce the same lineups as the historical production portfolio.**
   - DFS performance is unchanged by construction, so there is nothing to win or lose on this slate.
   - This is the "same valid projections and lineups, now more safely produced" outcome.
2. **The drifted run is not a candidate.**
   - It is today's code fed post-lock information: roster captures, and PBP that contains this game.
   - That it did worse on this one game is **not** evidence about any model.
   - What it does show is that an uncontrolled data-vintage change rewrites 123 of 150 lineups silently. That is the
     reason replay environments must be point-in-time, and why the capture-selection proposals F2 and F3 exist.
3. **One game is one draw.** The production portfolio's rank-6 lineup is a single outcome. Nothing here distinguishes
   a better objective from a lucky one.
4. **PIT@CLE and PHI@CHI add no portfolio evidence.**
   - In both, the owner played a hand lineup (PIT@CLE CPT Watson, 90.94 pts; PHI@CHI 74.53 pts) that no system run
     produced.
   - PHI@CHI has no salary file.
   - The system's PIT@CLE prelock board could be ranked against that field. It was not tonight: its 2026-10-01 code
     has no WORLDS bundle to replay, and ranking a static board adds no A/B information.

## Football prediction quality (C1, the only candidate whose numbers moved)

- **Conditional (if-plays) MAE** on the 13 moved ATL@NO players with actuals: 3.932 → 3.930. That is negligible on
  n = 13 from one game.
- Unconditional projections and every draw are unchanged, so calibration, CRPS and correlations are unchanged.
