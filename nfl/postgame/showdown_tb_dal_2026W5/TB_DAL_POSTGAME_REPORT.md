# TB@DAL Week 5 Showdown: postgame forensic report (2026-10-08)

**Source of every number.** `TB_DAL_2026W5_POSTGAME.json` is produced by `nfl/postgame/showdown_postgame.py` from:
- nflverse play-by-play `NFLVERSE_PBP_2026.42ef5132fd211775.csv.gz` (172 plays for the game);
- the frozen pregame artifacts. All 97 hashes in `PREGAME_FREEZE_MANIFEST.json` were re-verified before grading.

Nothing in this report is a forecast input, and no pregame file was modified.

**One game is one draw.** Nothing here is evidence that a model is better or worse in general. Where a finding is
measurable beyond this game, the measurement is cited.

---

## A. Official game results

**Final: TB 24, DAL 16.**
- Score after each quarter (DAL–TB): 7–0, 10–7, 10–24, 16–24.
- Sources: nflverse play-by-play, matched by five outlets (ESPN, NFL.com, NBC/PFT, Dallas Cowboys, Fox 4). The web
  search notes kept at the time are in `raw/.../PROVISIONAL_WEB_FACTS_2026-10-09T0410Z.json`.

**Scoring plays, from the play-by-play:**
- Q1 10:53: J. Williams 1-yard run (Aubrey extra point).
- Q2 15:00: Daniels 5-yard pass to Irving (McLaughlin extra point).
- Q2 0:26: Aubrey 41-yard field goal.
- Q3 14:04: Egbuka 14-yard run on a jet sweep (extra point).
- Q3 7:35: Irving 1-yard run (extra point).
- Q3 3:02: McLaughlin 41-yard field goal.
- Q4 5:30: Prescott 18-yard pass to Pickens. No successful try followed.

| | DAL | TB |
|---|---|---|
| Offensive plays (pass + run) | 55 | 63 |
| Pass attempts / sacks taken | 42 / 0 | 25 / 1 |
| Pass rate | 0.76 | 0.41 |
| QB scrambles | 0 | 6 (Daniels: 7 carries, 5 scrambles, 23 yds) |
| Drives | 10 | 11 |
| Red-zone plays | 5 | 14 |
| Plays of 20+ yards | 6 | 4 |
| Turnovers | 3 (2 INT, 1 fumble lost) | 0 |
| EPA per play | −0.03 | +0.16 |

**Quarterbacks:**
- Prescott: 316 yards, 1 TD, 2 INT.
- Daniels: 19 of 25 for 189 yards, 1 TD, 0 INT. He also carried 7 times for 23 yards.

**In-game injuries, from the play-by-play:**
- Lamb left and **returned** in the 4th quarter (6:19). The departure isn't timestamped in the play-by-play.
- Also returned: S. Revel (DAL), J. Barham (DAL) and Wirfs (TB).
- Lamb was a full participant in practice; nflverse lists no injury designation for him.

**DraftKings points:**
- Every one of the 49 rosterable players is scored with the same DK scorer the projection used
  (`nfl.product.dk_scoring`): 4 per passing TD, 0.04 per passing yard, −1 per INT, 0.1 per rushing/receiving yard,
  6 per TD, 1 per reception, and +3 for 300 passing yards or 100 rushing/receiving yards.
- Kicker: missed field goals score 0, the rule DraftKings' own points confirmed on 172 of 172 ATL@NO entries.
- Defense: points-allowed bands.
- Prescott's 17.64 reproduces his line exactly: 316 × 0.04 + 4 − 2 + 3.

**Cross-check against nflverse weekly player stats** (08:48Z), recorded in `NFLVERSE_STATS_CROSS_CHECK.json`:
- **First run: 1 disagreement in 480 cells.** Flournoy had 5 targets in our count and 4 in nflverse's.
- **The cause was ours.** A failed two-point try (Q4 5:26, Prescott's incomplete pass to Flournoy) had been counted as
  a target and as a pass attempt. That's also why the DAL counts read 43 attempts, 56 plays and 6 red-zone plays.
- **Fixed in the scorer**, with a regression test (`test_failed_two_point_try_is_not_an_ordinary_play`).
- **Now AGREE on all 528 cells**, pass attempts included. No player's DK points changed.

## B. Player projection errors (frozen forecasts against the result)

Errors are actual minus projection. "Where actual fell" is the share of our simulated outcomes below the actual
score: 0.97 means it beat 97% of our simulations, and 0.001 means it beat almost none of them.

| Player | Ours | FC | Actual | Our error | FC error | Where actual fell in our range |
|---|---|---|---|---|---|---|
| Bucky Irving | 16.5 | 10.3 | **34.5** | +18.0 | +24.2 | 0.97 |
| George Pickens | 11.7 | 18.0 | **31.0** | +19.3 | +13.0 | 0.98 |
| CeeDee Lamb | 28.3 | 22.1 | **2.9** | −25.4 | −19.2 | **0.001** |
| Dak Prescott | 22.5 | 22.6 | 17.6 | −4.8 | −5.0 | 0.28 |
| Javonte Williams | 18.7 | 18.8 | 14.2 | −4.5 | −4.6 | 0.32 |
| Emeka Egbuka | 12.0 | 7.6 | 17.2 | +5.2 | +9.6 | 0.81 |
| Jalon Daniels | 14.0 | 12.1 | 13.9 | −0.1 | +1.8 | 0.54 |
| Ryan Flournoy | 5.4 | 9.3 | 12.0 | +6.6 | +2.7 | 0.92 |
| Cade Otton | 11.6 | 7.3 | 5.5 | −6.1 | −1.8 | 0.16 |
| Jake Ferguson | 10.1 | 9.4 | 4.9 | −5.2 | −4.5 | 0.19 |
| Chris Godwin Jr. | 8.5 | 6.9 | 7.0 | −1.5 | +0.1 | 0.45 |
| Tez Johnson | 1.1 | 3.7 | 7.4 | +6.3 | +3.7 | 0.99 |
| Brandon Aubrey | 9.3 | 11.2 | 5.0 | −4.3 | −6.2 | 0.22 |
| Buccaneers DST | 4.3 | 3.0 | 7.0 | +2.7 | +4.0 | 0.70 |

**Across all 49 players:**
- 79.6% of actual scores fell inside our 10th–90th percentile range (nominal 80%).
- 6.1% fell below that range and 14.3% above it. The average "where actual fell" value was 0.50.
- Average absolute error: ours 2.81, FC's 2.53.

**On the 20 players either source projected at 3 points or more:**
- Average absolute error: ours 6.28, FC's 5.72. We were closer on 9 of the 20.
- By position, average absolute error:

| Position | Ours | FC |
|---|---|---|
| WR | 8.79 | 6.90 |
| TE | 5.62 | 3.16 |
| RB | 7.05 | 8.25 |
| QB | 2.47 | 3.35 |

- **Where we and FC differed by 2 points or more (10 players), FC was closer on 7.**
  - FC closer: Pickens, Lamb, Otton, Flournoy, Turpin, Goodson, Tez Johnson.
  - Ours closer: Irving, Egbuka, Gainwell.

**Team level:**
- Our average DAL score was 30.1; the actual 16 beat only 6% of our simulated DAL scores.
- TB: our average 19.7; the actual 24 beat 68% of our simulations.
- Total: our average 49.9; the actual 40 beat 24% of our simulations.
- We gave **DAL an 81% chance to win**.
- The exact scoreboard result (DAL ≤ 16 and TB ≥ 24) occurred in **2.2%** of our 2,000 simulated games.

**The underlying statistics behind the biggest misses:**
- **Lamb:** we projected 12.1 targets, 9.2 catches and 124 yards. He had **5 targets, 2 catches, 9 yards**.
  - His weekly target share was 0.27, 0.29, 0.20, **0.49** (week 4, 17 catches for 189 yards), then 0.12 tonight.
    Our 0.32 is about the average of the first four weeks.
  - Pickens played 86% of snaps in week 4, so that game was not an availability artifact.
  - Lamb left and came back mid-game.
- **Pickens:** we projected 6.3 targets (0.16 share). He had **13 targets, 9 catches, 130 yards**. His 2026 shares were
  0.20, 0.26, 0.28, 0.07, and 0.31 tonight.
- **Irving:** we projected 16.4 carries for 71 yards. He had **21 carries for 165 yards**, including a 72-yard run.
- **Daniels:** we projected **34.6 pass attempts; he threw 25** (beat only 11% of our simulations). We projected
  **3.3 carries; he had 7**.
- **Prescott:** 42 attempts (we projected 38.7), 316 yards (we projected 268), 2 interceptions (we projected 0.77).
  He had no carries; we projected 3.1.

**Thin low tails, measured beyond this game.** `nfl/research/tail_calibration/STAR_DUD_RATE_2021_2025.json`:
- In 2021–2025, receivers whose season-to-date average was 20+ DK points scored **under 5 points in 6.6% of games**.
  That's 350 games across 70 player-seasons. Resampling by player-season puts the rate between **4.0% and 9.5%**
  (95% interval).
- Our worlds gave Lamb **0.45%** and gave Olave 0.5% in the week-4 game.
- For players averaging 15–20 points the real rate is 10.4% (8.8%–12.0%). Our worlds gave Irving 2.0% and Javonte
  Williams 1.5%.
- The season-to-date average regresses toward the mean, which pushes the reference rate up somewhat. But even "under a
  quarter of the player's average" happens 6.5% of the time against our roughly 1%. Our bad-game tail for top players is
  roughly ten times too thin.

## C. Real portfolio performance

**Contest financials are UNKNOWN.** No DraftKings entry-history or standings export has been captured for contests
196438543, 196438555 or 196438556. That leaves all of the following unknown:
- which file DraftKings actually held for each entry;
- each entry's points, rank and the field size;
- fees and winnings;
- duplication with other contestants;
- the payout table.

Nothing below is a return. `showdown_postgame.contest_financials` will fill this section and will identify which
portfolio was accepted from DraftKings' own points for each entry, the way it identified 172 of 172 entries for ATL@NO.
The request is in `docs/AGENT_OUTBOX.md`.

## D. Showdown construction, scored with actual DK points

Six portfolios are scored separately. Before kickoff, only CORRECTED_R1 was recommended for upload.

| Portfolio | Lineups (distinct) | Best | Average | Median | Worst | Short of best possible | Avg salary |
|---|---|---|---|---|---|---|---|
| OFFICIAL_SEALED (11 ineligible lineups) | 190 (163) | **133.15** | 77.7 | 76.4 | 25.9 | 3.8 | 47,699 |
| **CORRECTED_R1** (recommended) | 190 (158) | 130.00 | 78.7 | 80.1 | 38.6 | 7.0 | 48,397 |
| Research: FC reference | 190 (163) | 124.90 | 78.9 | 79.2 | 29.1 | 12.1 | 46,446 |
| Research: halfway on TB | 190 (159) | 130.00 | 78.4 | 77.4 | 25.9 | 7.0 | 47,608 |
| Research: re-projected | 190 (162) | 122.81 | 78.6 | 78.7 | 38.6 | 14.2 | 48,968 |
| DK template placeholder (1 lineup × 190) | 190 (1) | 77.59 | 77.6 | 77.6 | 77.6 | 59.4 | 49,500 |

**Best possible lineup, in hindsight.** This is an exact search over the 31 players the eligibility gate allowed:
- **136.99**: Irving as captain, with Prescott, Pickens, Egbuka, Flournoy and Tez Johnson. Salary 46,600.
- Before kickoff our worlds gave that lineup an **average of 77.4 and a 95th percentile of 113.0**. It was not in either
  candidate pool. No method that selects from our worlds would have chosen it; it is a hindsight lineup, not one that
  could have been picked.

**Best lineup by contest (CORRECTED_R1):**
- 150-max: 130.0, and 11 lineups scored 110 or more.
- Each 20-max: 108.9. The two 20-max portfolios are identical, a known defect.

**What decided the result: Lamb.**
- **Lamb was in 95 of 190 corrected lineups** and captain in 45. Lineups with Lamb averaged **69.6**; lineups without
  him averaged **87.8**.
- **He sat exactly at the 50% player cap in every contest** (75 of 150, 10 of 20, 10 of 20), so the optimizer wanted
  more of him than the cap allowed.
- Captain: 33 of 150 in the 150-max (cap 45), and 6 of 20 in each 20-max, where the 30% captain cap bound.
- Lamb was the best captain in 36.8% of our simulated games, the most of anyone.
- **Irving-captain lineups averaged 101.8**, but there were only 19 of them. Irving was the best captain in 11.5% of
  our simulations.
- **Pickens was captain in only 6**. He was the best captain in just 2.4% of our simulations.

**The Tampa Bay receiver concern raised before lock** (Egbuka, Godwin, Otton) **was not what cost us**:
- Egbuka scored 17.2, above both our number and FC's.
- Godwin scored 7.0, about our number.
- Otton scored 5.5, below ours; FC was closer.
- The sensitivity portfolios that leaned away from TB receivers did no better: FC-reference best 124.9, halfway best
  130.0.

**The eligibility correction cost this game's best lineup.** The OFFICIAL portfolio's best lineup (133.15: Irving
captain, McLaughlin, Egbuka, Pickens, J. Williams, Flournoy) was all eligible players. The corrected run re-optimized
globally and did not keep it. That's chance, not evidence about either portfolio.

**Disclosure I did not make before lock.** To fill the 150-max, the re-projected research build had to relax its
**player cap from 75 to 98** (`relaxation_level 2`). That's why Lamb and Prescott each sit in 118 of 190 of its
lineups. I reported that build as "a tie" without saying this. It is recorded as defect D-09.

## E. Root causes and defect register

The machine-readable register is `TB_DAL_DEFECT_REGISTER.json`. In summary:

| ID | Class | Severity | Finding | Evidence |
|---|---|---|---|---|
| D-01 | Weak statistical model | High | Our bad-game tail for top players is about 10 times too thin, so the optimizer over-trusts stars as captain and core | Section B; `star_dud_rate.py` |
| D-02 | Missing football dependency | High | Team pass volume and pass rate have no QB argument. Daniels' two starts: 27 and 25 attempts, pass rate 0.49 and 0.41, against our 34.6 and Mayfield's 0.60–0.67 | `qb_regime_audit.py`; play-by-play weeks 1–5 |
| D-03 | Missing football dependency | Medium | QB rushing comes from a generic cohort prior. Daniels: 8 and 7 carries (6 and 5 scrambles) against our 3.3 | `docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md` §1 |
| D-04 | Unvalidated assumption | Medium | Target shares are pooled across games weighted by targets, so one high-volume game (Lamb week 4, 0.49) moves the share; nothing models volatility between games | `proj_v1` share `_combine` |
| D-05 | Confirmed correctness defect | High | Published worlds break NFL accounting: receiving yards without catches (2,640 player-world cells), TB receivers about 30 yards per game above what the QB throws, interceptions not credited to the opposing defense, points not equal to scoring events | `WORLD_ACCOUNTING_OFFICIAL.json`; repair in progress (F) |
| D-06 | DFS optimization weakness | High | No ownership or field model. The objective counts simulated games where a lineup scores within 90% of the best possible, with no payout, duplication or ownership modelling | `showdown_portfolio.py` |
| D-07 | DFS optimization weakness | Medium | The two 20-max contests receive identical portfolios | Section D |
| D-08 | Operational defect | Critical (fixed) | Ineligible players selected (Sills, Demercado, Josh Williams + 8 more entries) | `roster_eligibility.py` + 16 negative controls; **not yet wired into the runner** |
| D-09 | Operational / release defect | Medium | A research build's player-cap relaxation (75 → 98) was not reported before lock | Section D |
| D-10 | Incomplete data | Medium | No accepted-entry or contest-result evidence is captured automatically | Section C |
| D-11 | Unexplained, needs research | Medium | Lamb's 2.9 points: an in-game injury (he returned in Q4) and coverage. Our 28.3 against FC's 22.1: the efficiency step scaled his receiving yards per target by ×1.41. How much of the 6-point gap is efficiency and how much is volume (0.32 target share) has not been broken down yet | `DRAWS.player_mean_anchor` |
| D-12 | Unvalidated assumption | Medium | On the large disagreements with FC, FC was closer on 7 of 10 this game. One game cannot establish whether disagreement predicts our errors; the ledger now measures it across slates | `SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl` |

**Predictable from pregame evidence and not used:** D-02 and D-03. Daniels' week-4 start already showed both, and
the prelock audit flagged them. Tonight is the second start in the same direction. Two starts are still two starts, so
the fix is the partially pooled model in section G, not a two-game adjustment.

**Not reasonably predictable before the game:** Lamb's in-game injury, Irving's 72-yard run, three Dallas turnovers,
and Tez Johnson's 64-yard catch. These count against the luck of the night, not against a mechanism.

**Built into the system:** D-01, D-04, D-05 and D-06. They don't explain this one loss on their own, but each makes
losses like it more likely, and each can be measured.

See `TB_DAL_REPAIR_PROGRAM.md` for sections F to I.
