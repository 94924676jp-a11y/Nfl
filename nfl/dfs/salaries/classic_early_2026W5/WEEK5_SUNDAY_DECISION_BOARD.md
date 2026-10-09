# Week 5 Classic (Sunday 1:00 ET, 8 games): decision board, as of Friday 2026-10-09 ~15:45Z

**State: NOT READY TO EXPORT LINEUPS.**
- There is no DraftKings file for this slate in the repository.
- The Friday injury designations have not been captured yet.

**Our own football projections now exist without any DK file** (§9). Nothing on this board recommends a lineup or a
wager, and nothing was uploaded or entered.

**Games:** CHI@GB, CIN@MIA, LV@NE, MIN@NO, CLE@NYJ, IND@PIT, HOU@TEN, NYG@WAS.

**Evidence tiers used below:**
- **OFFICIAL**: nflverse captures derived from the NFL's GSIS rosters and official injury and practice reports.
- **SECONDARY**: the web-search news supplement. It is a discovery signal, never a model input, and its own
  CONFIRMED / REPORTED / CONFLICTING tag is the outlet's claim, not ours.

## 1. Research coverage

| Item | Coverage | Artifact |
|---|---|---|
| Positively benchmarked players | **156 of 156** with a full evidence row | `WEEK5_EVIDENCE_BOARD.{json,csv}` |
| Active players the benchmark omits but we project ≥ 4 DK points | 4: Breece Hall, Caleb Williams, Michael Pittman, Adonai Mitchell | same |
| Our projection | **266 players** (250 skill + 16 DST), 2,000 simulated worlds, football sanity PASS | `research_projection/incumbent/` |
| Player records (facts / estimates / reported news kept apart) | 156 | `WEEK5_PLAYER_RESEARCH_RECORDS.{json,md}` |
| QB regime per club | 16 clubs | `WEEK5_QB_REGIME_BOARD.json` |
| Stored-but-not-consumed information | **140 of 160** rows carry at least one flag | evidence board, column `stored_not_consumed` |

Each evidence row holds:
- eligibility;
- availability state;
- designation and practice line;
- captured depth chart;
- our role band and ceiling;
- the club QB (schedule listing vs the engine's starter);
- 2026 workload;
- our volume and DK points;
- simulated p10 / p50 / p90;
- the FC benchmark;
- the named stored-not-consumed flags.

**Flag counts (players):**

| Flag | Players | What it means |
|---|---|---|
| TEAMMATE_PRACTICE_NOT_CONSUMED | 111 | a teammate did not practise and is undesignated; no volume moves yet |
| SECONDARY_NEWS_NOT_CONSUMED | 63 | by rule |
| DEPTH_TIE_BROKEN_BY_ID | 38 | see §4 and W5-G13 |
| PRACTICE_STATUS_NOT_CONSUMED | 36 | — |
| ROLE_HISTORY_ABOVE_CEILING | 31 | — |
| QB_REGIME_NOT_CONSUMED | 27 | — |
| LISTED_STARTER_NOT_CONSUMED | 10 | all CHI and its opponents' rows |
| OPPONENT_QB_NOT_CONSUMED | 3 | DST rows |

## 2. Confirmed personnel changes (OFFICIAL roster capture, week 4 → week 5)

**Moved to reserve:**
- Braxton Berrios (NYG WR);
- Jaylin Lane (WAS WR).

**Released:**
- Jerome Ford (MIN RB);
- Messiah Swinson (CLE TE);
- Bryce Oliver (HOU WR);
- Justin Shorter (LV WR).

**Moved to practice squad (not eligible without an elevation):**
- Nick Westbrook-Ikhine (IND);
- Sterling Shepard (NYJ);
- Carlos Washington (MIA);
- Lew Nichols III (PIT);
- Craig Reynolds (WAS);
- Jeshaun Jones (MIN).

**Added to the active roster:** Mark Gronowski (HOU QB).

**Week 4 game-day inactives, now active again** (nothing yet says they will play):
- Caleb Williams;
- Justin Jefferson;
- Breece Hall;
- Adonai Mitchell;
- Terry McLaurin;
- Rico Dowdle;
- Keenan Allen;
- Jayden Daniels;
- Rachaad White;
- Mason Taylor;
- Noah Fant;
- several backups.

**Not confirmed:**
- **Kaytron Allen (WAS).** He is still ACT in the official week 5 roster capture. The SECONDARY report of a waiver is
  unconfirmed; recheck at the Friday refresh.
- **Marcus Mariota (WAS).** ACT. SECONDARY reports call him doubtful, but no designation exists yet.

## 3. Starters still uncertain (designations arrive Friday afternoon; inactives about 11:30 ET Sunday)

| Club | Question | OFFICIAL evidence | SECONDARY report | What our engine does now |
|---|---|---|---|---|
| **CHI** | QB: Williams or Bagent | Williams DNP Wed and Thu, no designation; the nflverse schedule capture lists **Bagent** | Williams ruled out, Bagent starts [CONFIRMED tag, Chicago Sun-Times 10-05] | Starts **Williams** (chart rank 1): 21.96, Bagent 0.07. **Every CHI and GB row is conditioned on this.** An OUT designation flips it with no code change (W5-G15) |
| **WAS** | QB Daniels returns | Daniels ACT, full practice | full go [CONFIRMED tag] | Starts Daniels: 19.82 |
| **MIN** | QB Murray | listed starter | — | Starts Murray: 16.72 (QB_CHURN flag) |
| NYJ | Breece Hall, Adonai Mitchell | DNP Wed and Thu, no designation | "essentially out" [REPORTED] | Projects Hall 15.00 and Mitchell 8.09 as if playing; Braelon Allen 4.72 as RB2 |
| WAS | McLaurin, Diggs | McLaurin DNP both days; Diggs DNP | Diggs CONFLICTING | Projects both as playing |
| PIT | Pittman, Dowdle | Pittman limited then DNP; Dowdle limited | Pittman "multiple weeks" [CONFIRMED tag] | Pittman 7.97 as playing |
| CHI | Monangai, Swift | Monangai DNP; Swift limited | turf toe [CONFIRMED tag] | Monangai 7.63 |
| CIN | Higgins, Chase | Higgins DNP; Chase limited | — | Both as playing |

**Rule followed:** an UNKNOWN or undesignated player is not inactive, and a missing designation is not "not playing".
The engine moves volume only on an OUT designation or an official inactive.

## 4. Forecasting limitations (what the numbers cannot see)

1. **QB identity is not an input to team volume or receiver shares** (W5-G1).
   - CHI is the live case: if Bagent starts, our CHI receiver numbers rest on a Williams-era club baseline.
   - The QB-conditioned candidate **failed** its predeclared bar and is not used (§5).
2. **Practice participation does not change a projection** until a designation exists. There is no
   partial-workload model (W5-G4).
3. **Depth ties are broken by player-ID order (W5-G13, found today).**
   - 10 rooms are tied at rank 1, among them Chase/Higgins, Jefferson/Addison, Diggs/McLaurin and Watson/Golden.
   - The same football facts give different projections under DK IDs and under research IDs.
   - A tie-aware candidate (TIE-1) was measured: 58 players move by more than 0.05 points, up to ±4.5. **It is not
     validated and is not used.**
4. **Injury evidence lag (W5-G14).** The engine state reads Wednesday's practice line; Thursday's is stored but
   not in the manifest.
5. **Lower-tail volatility for high-mean players is under-stated** (D-01).
6. **Event accounting in the worlds is inconsistent** (D-05). The repair exists as a shadow with zero violations
   on TB@DAL and is not promoted.
7. **Not modelled at all:**
   - weather;
   - offensive-line injuries;
   - opponent-specific defence beyond the club environment;
   - DOUBTFUL / QUESTIONABLE as probabilities.

## 5. Correctness repairs completed today

| Repair | Status | Evidence |
|---|---|---|
| **An absent starter no longer suppresses his replacement's depth ceiling** (W5-G12) | **COMMITTED** `8d7c9822` | `nfl/tests/test_role_state_absent_rank.py`: 7 fn, 34 checks, 0 failing; 29 of 34 fail without the fix |
| The football universe no longer needs the DK entries file | built and tested in a separate worktree (§9) | `nfl/tests/test_pool_entries_separation.py`: 15/15 |
| Event-consistent worlds (accounting repair) | **SHADOW**, committed on its branch, not promoted | 74/74; every checked law 0 / 2,000 worlds |
| QBCTX shadow candidate | **preserved as FAILED** (1 of 3), commits `eddf6459`, `d990493e` | pass rate and QB rushing are not reclassified |
| QBCTX-DB1 (dropbacks alone) | **preregistered** `17a833f4`, prospective W6–W14, ≥ 40 QB-change team-games | nothing evaluated yet |

**Role fix test coverage:**
- every skill position: QB, RB, WR, TE;
- all five absent statuses;
- two absences in one room;
- QB, RB and TE out at once at one club, with a TE out at another, showing no cross-room leak;
- the converse: DOUBTFUL and UNKNOWN keep their rank;
- a no-absence no-op;
- the real states: Kamara on ATL@NO, Braelon Allen on W4 Early.

**Week 5 effect of the role fix:** none yet. No Week 5 player carries an absent status until the Friday
designations are captured.

## 6. Regression tests

**41-suite role and projection run** (`nfl/tests/certificates/ROLEFIX_ABSENT_RANK_REGRESSION_20261009.json`):
- Run on HEAD `bf3e802f` plus the fix. The tested diff was verified unchanged after the run (sha `a688575c…`).
- 41 of 41 modules completed and none timed out: **35 pass, 6 fail**.
- `test_depth_chart_vintage_selection` ran about 30 minutes against its usual 5–6, and passed.

| Failing module | Now | Accepted baseline | Verdict |
|---|---|---|---|
| test_classic_slate_state | 1 | 1 | identical (week-4 games are now played) |
| test_football_only_arm | 4 | 4 | identical |
| test_role_depth_adversarial | 1 | 1 | identical |
| test_v1_draw_artifact | 3 | 3 | identical |
| test_v1_rushing_a1 | 3 | 3 | identical |
| test_v1_projection | 1 | 0 in an earlier run | **fails identically on the base commit without the fix**; the check asserts the Jets have zero interceptions and the data has moved. Recorded, not loosened |

**Separate-worktree checks of the pool change:**

| Suite | Result |
|---|---|
| test_classic_slate_state | 24/25 (the same pre-existing failure) |
| test_early_slate_window_and_identity_carry | 33/33 |
| test_classic_pipeline | 15/15 |
| test_classic_upload_verify | 16/16 |
| test_classic_roster_gate | 9/9 |
| test_classic_staging | 9/9 |
| test_classic_portfolio | 16/16 |
| test_classic_failure_injection | 24/24 |
| test_pool_entries_separation | 15/15 |

## 7. Disagreements with the FC projection (diagnostic only; FC is never an input, and agreement is not a target)

**Overall, on 156 players:**
- correlation **0.868**;
- mean ours − FC **−0.78**;
- mean absolute difference **2.37**;
- 17 players differ by 5 or more points.

**By position, mean ours − FC:**

| WR | QB | RB | TE | DST |
|---|---|---|---|---|
| −0.84 | −1.53 | −0.80 | −0.61 | −0.09 |

**The large gaps, each with its cause:**

- **Availability assumption: FC drops players we keep.**
  - Bagent: ours 0.07, FC 13.1. FC drops Williams; we start him (CHI QB, §3).
  - Breece Hall: ours 15.0, FC omits him; Braelon Allen: ours 4.7, FC 13.1. FC treats Hall as out.
- **Depth tie broken by ID** (W5-G13):
  - Chase: ours 14.8, FC 23.5. He is tied with Higgins at rank 1, assigned SECONDARY, and his history is flagged
    above the ceiling.
  - Watson: ours 18.8, FC 17.6; Golden: ours 11.4, FC 8.3. The tie order moves them ±4.4 in the TIE-1 arm.
- **RB2 role cap** (SECONDARY, p_plays 0.63):
  - TreVeyon Henderson: ours 5.3, FC 12.8.
  - Rico Dowdle: ours 6.4, FC 12.8.
  - Kyle Monangai: ours 7.6, FC 13.9.
- **Ours far above FC:**
  - Malik Washington: ours 14.3, FC 8.2.
  - Romeo Doubs: ours 14.7, FC 9.1.
  - Hockenson: ours 13.2, FC 7.7.
  - Olave: ours 23.5, FC 18.2.
  - Jaylen Warren: ours 18.4, FC 13.3.

  All five are ALPHA in our role state, and the gap is a role or volume disagreement to read in the player records.

## 8. Ownership and duplication research status

- **Pregame incumbent:** the no-fit FC-proportional ownership baseline, declared before kickoff
  (`WEEK5_OWNERSHIP_AND_DUPLICATION_RESEARCH_BOARD.md`). It beat every fitted model on TB@DAL (CPT MAE 1.09).
- **Classic field simulator:** not built. Duplication levels: the Showdown B4 model ranks well (Spearman 0.71) but
  its level is about 6× too low, which fails its bar.
- **Payout tables:** none, so there is no EV, ROI or cash-rate objective (`docs/NFL_SHOWDOWN_TOURNAMENT_PLAN_2026-10-09.md`).
- **Exposure caps** (TB@DAL research, `nfl/research/exposure_caps/TB_DAL_2026W5/README.md`):
  - A 40% cap is infeasible.
  - 60% and uncapped raise the in-simulation objective and the average lineup, but concentrate exposure to 79–85%.
  - Our worlds under-state star dud rates, so this cannot justify removing the cap.
  - **Production caps unchanged.**

## 9. Why a DraftKings entries export was "required", the exact dependency, and the separation made today

**Before today, one call tied football forecasting to the entries file.**
- At `nfl/tools/classic_slate_state.py:216` (HEAD `bf3e802f`), `EO.pool(files['entries_blob'], files['entries_sha'])`.
  That built the player universe from the pool block that DK prints beside the entry rows (`early_only.pool`,
  header at column 14).
- Projection (`role_state`, `proj_v1`) and simulation (`showdown_draws`) read only that state.
- **So no entries file meant no state, and no state meant no projection.** The football never needed the entries
  themselves, only a list of players.

**Where a DK file is genuinely needed, and which one:**

| Stage | Needs | Why |
|---|---|---|
| Player universe → projection → worlds | **no DK file** (roster-derived research universe), or DKSalaries, or DKEntries | football facts only |
| Pricing and lineup optimization | **a DK pool with salaries**: DKSalaries.csv *or* DKEntries.csv | salaries, roster slots, DK IDs |
| Contest assignment (`nfl/opt/classic_portfolio.py:373`, `EO.entries`) | **DKEntries.csv** | entry IDs, contest IDs, fees |
| Upload verification (`nfl/tools/classic_upload_verify.py:137`) | **DKEntries.csv** | the upload template rows and the roster gate |

**The separation, built and tested in a separate worktree:**
- `early_only.pool` finds the pool header by its own cells. DKSalaries (column 0) and DKEntries (column 14) now
  give identical rows.
- `slate_files` carries a `pool_blob` that defaults to the entries file, so earlier weeks are unchanged.
- `nfl/tools/research_universe.py` builds a universe from the official roster capture:
  - ACT QB/RB/WR/TE plus a DST per club;
  - practice squad and reserve excluded and counted;
  - synthetic `RU-` IDs, salary None.
- `classic_slate_state.build(research_universe=…)` consumes it and never writes the production state path. The
  state is labelled `RESEARCH_UNIVERSE_NOT_UPLOADABLE`, so no portfolio or upload stage can read it.

## 10. Outstanding requirements for final lineup exports

1. **A DK file from the owner.**
   - DKEntries.csv is needed for the upload itself.
   - DKSalaries.csv is enough to price and optimise.
   - Neither can be produced here (DK API 403).
2. **Friday designations** captured into the vintage manifest (trigger 21:30Z). Then rebuild the state: OUT players
   leave the depth ranks under the committed fix, and their volume is redistributed.
3. **CHI starting QB** from a team source, or an OUT designation for Williams.
4. **Sunday official inactives** (trigger 15:40Z), then a freeze manifest before lock.
5. **The pipeline on the DK pool:** state → run → portfolios → verify, which includes the roster-eligibility gate and
   the upload template check → board → prelock → finalize.
6. **Owner decisions still open:**
   - promotion of TIE-1 or the accounting repair (neither is proposed for this slate);
   - payout tables, before any EV claim.
