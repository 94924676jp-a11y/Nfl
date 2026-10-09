# Week 5 Classic (Sunday 1:00 ET, 8 games): prioritized decision board, Friday 2026-10-09 ~17:10Z

**State: NOT READY TO EXPORT LINEUPS.** Two things are missing:
- there is no DraftKings file for this slate;
- the Friday official designations are not yet captured (the trigger runs at 21:30Z).

**Our projections exist** for 266 players across 8 games, at 2,000 simulated games, with the sanity check passing:
`nfl/dfs/salaries/runs/w5_final/` (the production code, including the tie-order repair), board
`WEEK5_EVIDENCE_BOARD.{json,csv}`.

Nothing here recommends a lineup or a wager. Nothing was uploaded or entered. FantasyCruncher (FC) is a benchmark, never
an input.

The previous version of this board is in git history (commit `78c66ef3`).

## A. What could materially change Sunday's lineups (ranked)

| # | Item | Evidence and tier | Our number now | Scenario / research number | Resolves when |
|---|---|---|---|---|---|
| 1 | **CHI starting QB** | Williams: DNP Wed and Thu (OFFICIAL practice report). Bagent: every SECONDARY source, including Ben Johnson's "Tyson will be the guy" relayed by six outlets; he threw all 34 W4 attempts. The engine starts Williams only because the 10-08 chart capture lists him QB1 | Williams 21.92, Bagent 0.07 | Bagent starts: Bagent **19.01**, Williams 0; Swift +0.8; **CHI receivers move < 0.5** | Friday designation (21:30Z refresh) or a team statement relayed to us |
| 2 | **Ja'Marr Chase availability** | OFFICIAL practice: Limited, **concussion**. SECONDARY: in protocol, needs a full practice to clear | **18.70** (was 14.81 before the tie repair) | — | Friday designation; Sunday inactives |
| 3 | **WAS QB** | Daniels: full practice Wed and Thu (OFFICIAL), first game back. Mariota: DNP (knee). Kaliakmanis threw 33 of 37 W4 attempts | Daniels 19.83 | Mariota starts: 18.07. Kaliakmanis starts: 12.44. WAS receivers move < 0.5, RBs +1 to +2.2 | Friday designation |
| 4 | **NYJ backfield and receivers** | Hall and Mitchell: DNP Wed and Thu (OFFICIAL). "Essentially out" is REPORTED only | Hall 15.00, Mitchell 8.09, Braelon Allen 4.72 | Both out: Allen **10.56** (ceiling SECONDARY → ALPHA under the committed absent-rank fix), G. Wilson +3.7, I. Williams +3.9 | Friday designation |
| 5 | **Depth-tie repair moves major receivers** | W5-G13, repaired in production (§B) | Chase 18.70 (+3.89), McLaurin 13.77 (+3.95), Higgins 16.77 (−4.32), Diggs 11.74 (−2.97), Hollins 7.06 (−3.28) | — | done; McLaurin and Diggs both DNP (OFFICIAL), so see row 6 |
| 6 | **WAS receivers' availability** | McLaurin DNP Wed and Thu (OFFICIAL; missed W4). Diggs DNP (OFFICIAL); SECONDARY conflicting | as above | — | Friday designation |
| 7 | **PIT** | Pittman: limited then DNP (OFFICIAL); "multiple weeks" (SECONDARY, CONFIRMED tag) | Pittman 7.97 | out: R. Wilson +3.6, Bernard +2.1 | Friday designation |
| 8 | **Appearance-rate defect** (W5-G16, research) | Backups who played every week get P(plays) from a club-slot table: Noel 0.077, Monangai 0.635, Henderson 0.635 | e.g. Noel 0.48, Monangai 7.63 | research arm AP-1 (not used) | prospective test, preregistered |

**The QB-identity limitation applies to rows 1 and 3** (W5-G1). Changing the starter moves the QB's own projection but
not his teammates' volume or shares. Bagent starting changes no CHI receiver by even half a point. The QB-conditioned
candidate failed its bar, so this is a known gap, not a hidden one.

## B. Fixed: correctness repairs in production

1. **An absent starter no longer holds a depth rank** (`8d7c9822`). 34/34 checks. 41-suite regression: every failure
   matches the baseline.
2. **A tied depth rank is broken by football evidence, never by the player ID** (`39340321`, plus `a8efedae` for
   tight ends). Details:
   - **The defect.** The state gives a back or receiver the *minimum* of his usage and chart ranks, so the chart WR1
     and the usage WR1 both held rank 1, and the DraftKings ID decided which took the ALPHA ceiling. Relabelling the
     IDs of the stored W4 state changed the band or ceiling of Nacua, Adams, Watson, Golden and Doubs.
   - **The rule now:** rank, then the chart rank (usage first for TEs, whose chart TE1 is often the blocker), then
     usage rank, then observed share. The ID is used only when nothing else separates them.
   - **Evidence.** Across 47 tied rooms in 2026 W2–W4, the chart's choice was the player who led his room in targets or
     carries in 28. Usage's choice was in 11 and ID order's in 18; by position, WR 20 vs 5 vs 10 of 32.
   - **Replays.** In point-in-time replays of 2026 W2–W4 (25 games, oracle availability), absolute DK error on changed
     players fell by 0.148, 95% club-week interval [−0.271, −0.034]. On the real W4 Early pool it was neutral: +0.069
     [−0.098, +0.259]. The rule was chosen on the same 2026 weeks, so this evidence is **exploratory**, not
     confirmatory.
   - **The ten tied Week 5 groups** are in `nfl/research/role_ceiling/W5_TIED_GROUPS_AUDIT.json`. Three changed
     (CIN WR, WAS WR, PIT TE); seven were already in chart order.
   - Tests: `test_role_state_tie_order` 11/11. On the old code, the tie and ID-invariance checks fail.
   - The 58-suite regression is recorded in `nfl/tests/certificates/`.
3. **Football forecasting no longer needs the DraftKings entries file** (`d41ef192`). The research universe comes from
   the official roster capture. DKSalaries is enough to price the slate; DKEntries is needed only to assign entries.

## C. Research-only (measured, not promoted)

| Item | Result | Why not promoted |
|---|---|---|
| RC-1 formation ceiling (WR2 and WR3 read as starters) | A rank-2 WR realises above the SECONDARY cap in 50% of 1,890 weeks (RB2 18%, TE2 10%). Oracle replays −0.217 [−0.327, −0.102]; real W4 pool +0.054 [−0.154, +0.294] | did not replicate on the real pool; preregistered W6–W11 |
| AP-1 appearance history | WR5 who played the prior three weeks appears again 67% of the time vs the table's 7.7%; RB3 75% vs 23%. Real W4 pool −0.116 [−0.274, +0.046]; RB MAE 4.86 → 4.55 | one week; preregistered W6–W11 |
| Simulation-accounting repair | event laws 0/2,000 violations; DST incumbent shown defective (non-integer DST scores in 92–98% of worlds). But receivers are over-dispersed, ties run 1.8–3.7% vs 0.29% historical, there is no overtime, defensive TDs are double-counted, and only 21 of 190 lineups survive | `nfl/research/accounting_repair/INTEGRATION_EVALUATION_2026-10-09.md`; needs fixes and an owner ruling on the anchor |
| QBCTX shadow | FAILED 1 of 3 | dropbacks alone preregistered (QBCTX-DB1), W6–W14 |
| Simulation-query tool | 90/90 checks; answers only from stored worlds, with SEs and refusals | `nfl/tools/sim_query.py`, research tool |

## D. Starting quarterbacks (`qb_verification/WEEK5_QB_STARTER_VERIFICATION.json`)

**None is confirmed at the OFFICIAL tier yet.** At 16:14Z no Friday designation was out. Fifteen clubs are
REPORTED_SECONDARY_CONSISTENT and need no scenario. Scenarios exist for CHI (Bagent) and WAS (Mariota or
Kaliakmanis).

| CHI | GB | CIN | MIA | LV | NE | MIN | NO |
|---|---|---|---|---|---|---|---|
| **Bagent** (engine: Williams, row A1) | Love | Burrow | Willis | Cousins | Maye | Murray | Shough |

| CLE | NYJ | IND | PIT | HOU | TEN | NYG | WAS |
|---|---|---|---|---|---|---|---|
| Watson | G. Smith | D. Jones | Rodgers | Stroud | Ward | Winston | Daniels (scenario needed) |

**The nflverse schedule's QB field is unreliable.** It listed Keenum for CHI's W4 game, but the play-by-play shows
Bagent threw every pass. It is classified unverified and never consumed.

## E. The 140 "stored but not consumed" flags, classified

Source: `nfl/research/evidence_consumption/WEEK5_EVIDENCE_CONSUMPTION_CLASSIFICATION.json`. There are 314 flags on 141
of 161 rows.

| Category | Flags | What |
|---|---|---|
| C1 confirmed, should consume | 42 | appearance history (32 rows, W5-G16, research arm AP-1); CHI starter identity (10 rows, scenario until official). The 38 depth-tie rows are now consumed correctly (repaired) |
| C2 represented indirectly | 112 | teammate practice: redistribution engages when a teammate is designated OUT or inactive |
| C3 research required | 86 | practice participation → P(plays) (36); WR ceiling (29); QB identity → team volume (17); opponent QB for DST (3) |
| C4 unverified | 74 | secondary news (64, discovery only); schedule QB listing (10) |
| C5 must not influence | — | FC, sportsbook prices, third-party sims and ownership, contest ownership before lock |

**Highest-impact bounded improvements, in order:**
1. The tie repair (**done**).
2. The CHI and WAS starter scenarios (**done**). They switch on an official designation, with no code change.
3. The Friday designation capture into the manifest (scheduled).
4. AP-1 and RC-1, prospectively.
5. QB-conditioned team volume: research. QBCTX-DB1 covers dropbacks.

## F. FC disagreements (diagnostic; `fc_diagnosis/FC_DISAGREEMENT_DIAGNOSIS.json`)

On 156 players: correlation **0.874**, mean ours − FC −0.78, mean absolute 2.32, and **16** players differ by 5 or
more.

For the 21 largest gaps (17 differences of at least 5 points plus the 4 players FC omits), the primary cause is:

| Cause | Players | Detail |
|---|---|---|
| FC-specific (our number tracks 2026 production) | 10 | Henderson, Dowdle, Olave, Hockenson, M. Taylor, McClain, Jennings, Austin, T. Johnson, Chase (before the repair) |
| Availability assumption | 6 | Bagent, Allen, Hall, Mitchell, Pittman, Williams |
| Volume model | 3 | Warren, Doubs, Washington |
| Role judgement | 1 | Monangai |
| Role defect | 1 | Noel (appearance) |
| Identity errors | **0** | — |

The tie defect was the primary cause of none of them, but it did move Chase by +3.9 once repaired.

## G. Ownership and duplication; contest construction

- **No Classic field model yet.** The no-fit FC-proportional ownership incumbent is declared pregame.
- **The TB@DAL study** (`nfl/research/external_strategy/stokastic_tb_dal_2026W5/`) shows our optimizer has no field,
  duplication or payout term:
  - our lineups averaged 40 field copies;
  - the on-air "most-duped" lineup had 295 actual copies;
  - our star lower tail is about 10× too thin (Lamb P(<5 DK) 0.45% vs 6.6% observed).
- **Classic plan:** `CLASSIC_PORTFOLIO_RESEARCH_PLAN.md`.
- **Gap board:** `IMPLEMENTATION_GAP_BOARD.md`. GAP-05, opponent adjustment, is excluded by your instruction (item 9)
  and needs your ruling.

## H. Requirements for final lineup exports

1. **DK file:**
   - DKSalaries.csv is enough to price and optimise (preliminary optimisation can run then);
   - DKEntries.csv is needed for entry assignment and the upload check.
2. **Friday designations** (21:30Z trigger): rebuild the state, the projections, the evidence board and this board.
3. **CHI and WAS starters:** official designation or a team statement relayed to us. Switch to the matching scenario.
4. **Sunday inactives** (15:40Z trigger): rebuild, then roster-eligibility gate, upload verify and freeze manifest.
5. **Owner decisions:**
   - RC-1 and AP-1 promotion after prospective evidence;
   - the accounting-repair anchor;
   - GAP-05;
   - payout tables before any EV claim.
