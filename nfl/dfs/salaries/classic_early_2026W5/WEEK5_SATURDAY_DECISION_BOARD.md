# Week 5 Classic (Sunday 1:00 ET, 8 games): Saturday decision board, 2026-10-10 ~15:15Z

**Readiness: NOT READY for upload-ready portfolios.** Research portfolios can be built from the projections and
scenarios below. Upload-ready ones need three things:

1. **The DraftKings salary file.** None is in `nfl/dfs/inbox/drop/`. It needs only DKSalaries.csv, not DKEntries.
2. **The official inactives at 15:30Z Sunday,** for which no reliable automated route exists (§5).
3. **Resolution of five players' roster histories** (§4).

Nothing here recommends a lineup or a wager. Fantasy Cruncher (FC) is a benchmark only, and its export is from Friday
13:27Z, before the designations.

**Projection of record:** `research_projection/rebuild_2026-10-10_roster/`
- As of 15:08Z, 253 players × 2,000 worlds, football sanity PASS.
- Inputs:
  - the Friday designations (nflverse injuries capture `20261010T074137Z`);
  - the 10-10 depth chart;
  - a roster slice refreshed from the 10-10 roster (§4).

**Football sanity PASS is not certification.** The published worlds still fail five ordinary-event accounting laws (§6).

## 1. Questionable starters: separate scenarios, no blended number

**Method.**
- Each scenario sets one player (or a pair) inactive and lets the engine's own role layer reassign his role.
- Base: `scenarios_2026-10-10/BASE`, which reproduces the projection of record exactly (0 of 266 players differ).
- Runs: `scenarios_2026-10-10/<LABEL>/`. Analysis: `scenarios_2026-10-10/SCENARIO_ANALYSIS.json`. Scripts:
  `research_projection/scripts/run_scenarios.py` and `analyse_scenarios.py`.

**No probability of playing is estimated.** Nothing in this repository measures how often a Questionable player with
a given practice pattern plays, so the active case and the inactive case are reported separately and **never blended**.
Each active-case number is conditional on the player being active.

**"Active but workload-limited" is NOT IMPLEMENTED.**
- The engine has no workload control: `availability.py` records a `workload_note`, and no projection code reads it.
- No such scenario is shown, rather than inventing a share cut.

Ranges are the 10th / 50th / 90th percentiles of the simulated worlds.

| Player (Friday practice) | Active case | If inactive: who gains (active → scenario) |
|---|---|---|
| **Ashton Jeanty** LV RB (**DNP**) | 19.65 [9.6 / 17.9 / 30.3] | Mike Washington Jr. 4.20 → **13.75**; Bowers 18.59 → 22.02; Tucker 11.75 → 13.96 |
| **Caleb Williams** CHI QB (Limited) | 23.31 [12.7 / 22.7 / 35.5] | Bagent 0.08 → **19.64**; Swift 19.74 → 20.57. **Receivers unchanged** (§2) |
| **Ja'Marr Chase** CIN WR (Full) | 18.70 [8.4 / 18.0 / 31.5] | Higgins 16.77 → **25.07**; Meyers 1.61 → 4.67; Gesicki 13.46 → 15.40 |
| **Tee Higgins** CIN WR (Full) | 16.77 [6.7 / 15.5 / 29.8] | Chase 18.70 → 22.51; Meyers → 4.81; Gesicki → 15.90; Chase Brown → 19.33 |
| Chase **and** Higgins | both 0 | Meyers → **11.20**; Tinsley → 7.32; Gesicki → 19.76; Chase Brown → 21.90 |
| **Justin Jefferson** MIN WR (Limited) | 16.55 [6.5 / 14.7 / 28.2] | Addison 7.40 → **12.16**; Hockenson 13.17 → 16.29 |
| **Terry McLaurin** WAS WR (Limited) | 15.45 [7.0 / 14.6 / 26.9] | A. Williams 7.96 → 11.66; Burks 3.21 → 6.52; D. Brown 1.54 → 4.42 |
| **Carnell Tate** TEN WR (Limited) | 14.98 [6.5 / 13.5 / 25.7] | Wan'Dale Robinson 9.59 → **13.93**; Ridley → 4.08; Ayomanor → 7.46 |
| **Alvin Kamara** NO RB (Limited) | 14.29 [6.9 / 14.0 / 23.8] | Kendre Miller 3.70 → 7.90; Olave 23.49 → 26.30; Shough 20.87 → 22.84 |
| **Rhamondre Stevenson** NE RB (Limited) | 13.47 [6.3 / 12.7 / 22.3] | TreVeyon Henderson 5.42 → **10.34**; Kiner → 4.04; Doubs → 18.16 |
| Keenan Allen IND WR (Full) | 10.75 [3.9 / 9.9 / 19.2] | Treadwell 3.99 → 7.75; Downs 13.92 → 16.25; Warren → 14.71 |
| Jordan Addison MIN WR (Limited) | 7.40 [1.8 / 6.3 / 14.0] | Jefferson 16.55 → 18.92; Hockenson → 14.98 |
| Rico Dowdle PIT RB (Limited) | 6.49 [1.6 / 5.4 / 12.5] | Homer 1.42 → 4.35; Warren 18.68 → 20.82 |

**Read with these mechanics in mind.** Each one is a measured property of the engine, not of football.

- **Team volume does not respond to an absence.** In every scenario the club's pass attempts, yards and touchdowns
  move only by simulation noise (pass attempts within ±0.9, passing yards within about ±8). No club gets worse at
  football when a star sits; the same opportunity is redistributed.
- **Promotion to rank 1 lifts the role ceiling.** A promoted WR2 moves from SECONDARY to ALPHA, so Higgins's +8.3
  without Chase and Robinson's +4.3 without Tate are partly the rank-ceiling mechanics (the WR2 cap, RC-1, still a
  preregistered candidate). Treat these jumps as upper-leaning.
- **The quarterback inherits an absent back's carries:**
  - Shough +2.11 without Kamara;
  - Maye +1.13 without Stevenson;
  - Caleb Williams +1.53 from Monangai's Out;
  - Geno Smith +2.06 from Hall's Out.

  That is not role-appropriate: an RB2 absence does not create quarterback designed runs. **New defect W5-G22**; the
  QB numbers in RB-out scenarios lean high by roughly 1–2 points.
- **Opponents never move.** No opponent player or defence changes by 0.25 points in any scenario.

**Dependencies: implemented vs missing.**

| Implemented | Missing |
|---|---|
| Inactive player zeroed | Probability of playing for Questionable players |
| Role reassignment by depth and usage | Workload-limited state |
| Per-player efficiency for the replacement | Team efficiency loss from an absence |
| | Opponent response |
| | Did-not-play worlds inside one simulation (W5-G16), so a late inactive is a scenario, never a draw |

**Sources.**
- Designations and practice lines: nflverse injuries `injuries.b440d6d8b06300da`, derived from the official report.
- Depth: nflverse depth charts `779f5b89c5c9dec4`.

## 2. Chicago: Williams vs Bagent, and what actually responds to the quarterback

| CHI team, per world | Williams starts | Bagent starts | Responds? |
|---|---|---|---|
| Pass attempts | 34.96 | 35.34 | no (noise) |
| Passing yards | 227.9 | 235.7 | no; Bagent's role-group prior gives 6.67 yds/att against Williams's own 6.52 |
| Passing TDs | 1.78 | 1.81 | no |
| Interceptions | 0.72 | 0.72 | no |
| Team carries | 34.04 | 34.67 | no |
| Team rushing yards | 166.3 | 144.1 | **yes**: Williams's 8.47 carries for 53 yds become Bagent's 6.08 for 18 yds, plus Swift +1.87 carries |
| Completions (receptions as proxy) | 21.6 | 21.9 | no |
| CHI points / GB points | 25.74 / 22.38 | 26.13 / 22.15 | no |
| Odunze, Burden, Loveland, Raymond | 14.63, 13.45, 11.76, 7.27 | 14.63, 13.50, 11.76, 7.27 | **no** |
| GB DST | 3.55 | 3.55 | **no** |
| Sacks, fumbles | not modelled | not modelled | not in the worlds |
| Kicker | no kicker in DK Classic; none simulated | | |

**Verdict.** This scenario is **NOT QB-conditioned** (gap W5-G18, now measured). The quarterback's own line changes,
and nothing downstream does: passing volume, receiver targets and efficiency, team scoring, and the opponent's
defence. The 19.64 for Bagent is the starter's passing environment with a role-group efficiency prior.

Bagent's own 2023 starts are not used (prior tier ROLE_GROUP). The likely direction of the error is that **CHI pass
catchers and the CHI stack are overstated if Bagent starts, and GB DST is understated**. The size is not measured
here.

**Do not build Bagent-scenario stacks on these receiver numbers.** FC projected Bagent at 13.14 on Friday morning,
consistent with FC expecting him to start, and FC's Williams row is absent from its export. Williams is Questionable
after a limited Friday practice.

## 3. Redistribution audit for the players ruled Out (`saturday_audit/REDISTRIBUTION_AUDIT.json`)

- **Zero participation.** All 15 Out players are excluded from every world: INACTIVE_NO_EVENTS, 0 violations
  (`saturday_audit/WORLD_ACCOUNTING_SAT_BASE.json`).
- **Scoring.** Published DK points equal points recomputed from the stat lines in all 470,000 player-world cells.
- **Team totals reconcile exactly.** Every affected club's targets, carries and pass attempts are unchanged from
  Friday to Saturday, so volume was moved, not created or lost.
- **Role-appropriate, with one exception:**
  - WR targets go about 80% to WRs, the rest to TEs and backs;
  - RB carries go to RBs;
  - the exception is the QB carry inheritance above (CHI Williams +1.53 of Monangai's 8.45; NYJ Geno Smith +2.06
    of Hall's 15.27).
- **Specific checks:**
  - Braelon Allen (+7.85 carries, to RB1) and Isaiah Davis (+3.85) take Hall's carries.
  - Garrett Wilson (+1.84 targets) and Isaiah Williams (+1.89) take Mitchell's and part of Hall's targets.
  - Roman Wilson (+2.19 targets) and Germie Bernard (+1.34) take Pittman's.
  - Swift (+3.68 carries) and Roschon Johnson (+3.03) take Monangai's.
  - McLaurin (+1.09 targets) and Antonio Williams (+2.15) take Diggs's.
- **Braelon Allen's band stays SECONDARY at RB1.** By design (`proj_v1.py:1470`), a backup does not inherit a
  starter's workload wholesale.

## 4. Roster and transaction audit (`saturday_audit/ROSTER_AUDIT.json`)

Each projected player's week-5 status was compared across five roster captures:
- 10-07, 10-08, the universe slice, 10-09 19:21Z, and 10-10 07:41Z;
- 237 players: 232 ACT in every capture, **5 unresolved**.

| Player | History | Finding |
|---|---|---|
| **Kaytron Allen** | WAS ACT, ACT, ACT, **CUT (W03, waived)**, **MIA ACT** | Waived by WAS, now active with MIA. The universe had him on WAS until the slice refresh today |
| Pierre Strong (GB RB) | DEV ×3, then ACT | Promoted from the practice squad; was missing from the universe |
| Bryce Oliver (HOU WR) | absent ×3, then ACT | New to the roster; was missing from the universe |
| Jake Haener (NYG QB), Mark Gronowski (HOU QB) | DEV/absent, then ACT | Backup QBs, about 0 projected |

**Fix applied.** `nfl/integrations/raw_slice.py` refreshes the universe's roster slice from the newest full roster
capture, keeping the old slice under `raw/.../superseded/`. The rebuild moved the projection by at most 1.09 points
(K. Allen 0.13 → 1.22 at MIA; DJ Herman 1.01 → 0.13).

**Upload rule.** The five unresolved players are **BLOCKED** from upload-ready portfolios until the official
inactives (or a dated transaction) resolve them; `nfl/integrations/dk_pool_check.py` enforces it. A single roster
snapshot is not taken as proof of game-day eligibility. Every other player is ELIGIBLE_PENDING_INACTIVES.

## 5. Inactives: windows and an authorized route

**Windows.** All eight slate games kick off at **13:00 ET = 17:00Z** (schedule capture `322e30495d45d3d8`):
CHI@GB, CIN@MIA, LV@NE, MIN@NO, CLE@NYJ, IND@PIT, HOU@TEN, NYG@WAS. Inactive lists are due 90 minutes before
kickoff, **15:30Z (11:30 ET)**, for all eight together. PHI@JAX (09:30 ET, London) is not on the slate.

**What exists today, and why none of it is sufficient:**
- **nflverse** publishes no pregame inactives.
- **NFL.com inactives page:**
  - unreachable from this executor;
  - its terms appear to bar automated retrieval (OD-1);
  - the `nfl-t90.yml` capture workflow has cron entries for week 4 only, none for 10-11, and a schedule change must
    land on the default branch (OD-4).
- **The armed Sunday trigger** (15:40Z, 10 minutes after the deadline) can rebuild, but it cannot itself obtain an
  official list. Web search is a discovery signal, never confirmation.

**Authorized routes, in order:**
1. **Owner relay:** paste the official lists into `nfl/tools/sunday_paste.py` (tier OWNER_RELAYED, never relabelled
   OFFICIAL_CAPTURED). This is the one route needing no new permission, and the most reliable.
2. **The networked agent:** captures club or league official releases with provenance (OUT-045).
3. **A licensed feed with inactives** (OD-3). It costs money, so it is your decision.

Until a list arrives, a Questionable player is unresolved, and the scenarios in §1 are the plan for each outcome.

## 6. Why the simulation limitations matter for lineups

These are the five defects from `world_audit/`, updated with today's measurements. None is repairable before Sunday
without promoting unvalidated changes.

| Defect | Who is affected | Lineup decision it distorts |
|---|---|---|
| QB identity ignored (W5-G18, measured §2) | CHI (and any team whose QB changes); receivers and the opposing DST | QB-receiver stacks under a backup QB look as good as under the starter; the opposing DST looks no better |
| No did-not-play worlds (W5-G16) | every Questionable player | late-inactive risk is invisible to the optimizer; it can only be handled by scenario portfolios and late swap (your manual action) |
| QB inherits RB carries (W5-G22, new) | NO, NE, CHI, NYJ QBs in RB-out cases | QB slightly overstated, by about 1–2 points |
| Star lower tail too thin (D-01) | Olave, Shough, C. Williams, Jeanty and other 20+ projections | bust risk understated 3–23×; floors and variance penalties favour stars and their stacks |
| World accounting (D-05) | passing yards ≠ receiving yards in 30,834 of 32,000 club-worlds; at least one receiving-yards-without-a-catch cell in every one of 2,000 worlds, and a receiving-TD-without-a-catch cell in 1,818 | pass-catcher correlations with their QB are wrong in both directions; GB/CHI/MIN receivers favoured |
| DST non-integer anchor | all 16 DSTs | distribution-based selection only: MIN/PIT/LV DST favoured, NYJ/MIA/TEN/GB disfavoured |

**Readiness labels:**

| Label | State |
|---|---|
| Football sanity | **PASS** |
| World accounting | **FAIL** (five laws, known defects) |
| Simulation calibration | **NOT CERTIFIED** |
| QB-conditioned environment | **NOT IMPLEMENTED** |
| Production | **NOT PROMOTED** |

## 7. Sunday optimisation: prepared, not exported

- **Research forecasts continue now.** They are built on the projection of record and the §1 scenarios.
- **DK salary file.** When DKSalaries.csv lands in the drop folder:
  1. `inbox.py` ingests it;
  2. `dk_pool_check.py` validates the game set, kickoffs, legal positions, salaries, unique ids, identity mapping
     against the universe, and upload eligibility;
  3. the rebuild planner switches the pool from the research universe to DK ids. Tested: 15 functions, 54 checks.
- **DKEntries is not required** for research portfolios. It is needed only to assign lineups to your entries.
- **Contest assignment and upload stay manual.** Contest assignment is a separate, later step. Upload is yours, with
  verified acceptance of the uploaded entries. The system never uploads.
- **Do not tune the optimizer on Thursday's realised winners.**

## 8. Summary: blockers and what to prepare for

**Most consequential unresolved situations:**
1. **CHI QB:** Williams Questionable. The Bagent case is not QB-conditioned (§2).
2. **Jeanty:** DNP Friday, Questionable. If out, Mike Washington Jr. becomes the LV back (13.75).
3. **CIN receivers:** both Questionable. The joint-out case makes Meyers and Gesicki large movers.
4. **Jefferson, McLaurin, Tate, Kamara, Stevenson:** each with a named beneficiary in §1.

**External benchmark disagreements** (FC, Friday, pre-designation; `saturday_audit/FC_BENCHMARK_KEY_PLAYERS.json`):

| Player | Ours | FC |
|---|---|---|
| Rico Dowdle | 6.49 | 12.79 |
| Garrett Wilson | 19.59 | 15.99 |
| Carnell Tate | 14.98 | 11.61 |
| Jeanty | 19.65 | 16.16 |
| Braelon Allen | 10.57 | 13.13 |
| Isaiah Davis | 5.73 | 3.05 |

Not in FC's export: Williams, Chase, Hall, Pittman.

**Eligible-player coverage.**
- 253 projected; 237 with a GSIS identity checked against five roster captures; 5 blocked pending inactives.
- DK id coverage is UNKNOWN until the DK file arrives.

**Exact remaining blockers:**

| # | Blocker | Owner of the fix |
|---|---|---|
| 1 | DKSalaries.csv in the drop folder | you |
| 2 | Official inactives at 15:30Z by an authorized route (owner relay is the ready one) | you, or the networked agent |
| 3 | OD-1 / OD-4 if you want the T-90 page capture | your decision |
| 4 | The CHI QB answer | inactives |
| 5 | DST mean decision (Decision 2 follow-up) | your decision |
