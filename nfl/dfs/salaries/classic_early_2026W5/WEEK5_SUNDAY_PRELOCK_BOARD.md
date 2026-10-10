# Week 5 Early Classic (Sunday 2026-10-11, 1:00 ET, 8 games): prelock board, 2026-10-10 ~19:10Z

**Scope.** The eight-game Early Only Classic slate: CHI@GB, CIN@MIA, CLE@NYJ, HOU@TEN, IND@PIT, LV@NE, MIN@NO, NYG@WAS.
It is not the main slate, the London game or a Showdown.

**This board reconciles the owner-supplied independent review** (pinned to `ddaebacd`) against HEAD `fd25431f` and
the artifacts built since. The review is an audit, not an authority: each finding below is re-measured here.

**Projection of record:** `research_projection/rebuild_2026-10-10_prelock/` (253 players × 2,000 worlds, football
sanity PASS). It is built on:
- the Friday designations (nflverse `20261010T074137Z`);
- the 10-10 depth chart and refreshed roster;
- evidence packet `2026W5-owner-20261010-chi-starter`;
- the transfer guard.

## Readiness labels

| Label | State | Blocker |
|---|---|---|
| Research forecasts | **READY (research only)** | — |
| Joint personnel scenarios | **READY**: 17 scenarios, all pass propagation | — |
| Legal DK pool | **BLOCKED** `SUN_INVALID_DK_POOL_OR_ENTRY_MAPPING` | no Early Only DKSalaries.csv delivered |
| Game-day state | **BLOCKED** `SUN_INACTIVES_COVERAGE_INCOMPLETE` | 0 of 16 club lists (published from 15:30Z Sunday) |
| Upload-ready portfolios | **BLOCKED** | both rows above |
| Simulation certification | **NOT CERTIFIED** | five world-accounting laws fail (known); QB environment not conditioned; DST anchor |
| Model promotion | **none**: no candidate promoted | — |

## P0 issues

### P0-1. Chicago starter: FIXED in the pipeline (evidence relayed, not captured)

**Evidence.**
- *Admitted:* the Bears' 2026-10-09 release, as cited in the owner's review bundle (reviewer sha `fdc858cf…`).
  It says Johnson announced that Tyson Bagent will start; Williams is Questionable (hamstring, Limited); Swift has no
  designation; Monangai is Out.
- *Not fetched here:* `chicagobears.com` does not resolve from this executor.
- *Corroboration (discovery signals only):* the Sun-Times (10-05) and an ESPN 1000 report agree on Bagent.
- *Requested:* OUT-046 asks the networked agent to capture the page.

**Path.** The owner-relayed packet `evidence_packets/2026W5_OWNER_20261010_CHI_STARTER.json` (cited
OFFICIAL_RELEASE) goes through the existing `classic_slate_state` evidence-packet intake. The packet re-ranks the QB
chart, and `predicted_lineup_context` carries CONFIRMED_BY_TEAM_PUBLISHED_EVIDENCE, tier OFFICIAL_TEAM_PUBLISHED, with
the packet id. Williams is **not** marked inactive: he stays Questionable, and is now QB2.

**Before → after** (roster build → prelock):

| Player | Before | After | Note |
|---|---|---|---|
| Bagent | 0.08 | **19.63** | ALPHA |
| Williams | 23.31 | **0.21** | QB2 appearance rate 0.138, an eligible backup with no starter workload |
| Swift | 19.74 | 20.53 | |

No other CHI player moves.

**Propagation, verified.** The change reaches state, role (Bagent ALPHA, Williams SECONDARY), projection and worlds:
- one starting workload: Bagent 34.7 attempts, Keenum 0.1;
- the Williams-inactive scenario passes.

**Tests:** `test_sunday_prelock_p0`:
- the chart cannot defeat the admitted starter;
- Williams is not made absent;
- a starter who is also listed inactive is refused.

**What responds to the QB in this engine, measured at one vintage** (`scenarios_2026-10-10_prelock`; Bagent base vs
Williams-start counterfactual):

| Quantity | Bagent | Williams | Responds? |
|---|---|---|---|
| Team pass attempts | 35.06 | 34.87 | no (invariant: team-level) |
| Team passing yards | 233.9 | 228.0 | no; the QB's own efficiency prior moves his line only |
| Pass TDs / INTs | 1.83 / 0.71 | 1.82 / 0.71 | no |
| Team targets / receptions | 30.87 / 21.75 | 30.88 / 21.76 | no |
| Team rushing yards | 146.2 | 154.1 | **yes** (QB rushing) |
| CHI points / GB points | 25.99 / 21.43 | 26.01 / 21.92 | no |
| Receivers, GB DST | unchanged | | no |
| Sacks, fumbles, kicker | not modelled; DK Classic has no K | | |

**Verdict.** The correct starter now reaches every consumer. **The offense is NOT QB-conditioned** (W5-G18): passing
volume, receiver targets and efficiency, scoring and the opponent's DST do not depend on QB identity. The likely
direction is CHI pass catchers overstated and GB DST understated; the size is unmeasured.

**The Williams-start counterfactual is contaminated and is not a usable forecast.** Bagent's packet label survives the
re-rank, so he keeps 4.56 pass attempts as QB2.

### P0-2. Kaytron Allen's club: FIXED in state; projection-side remainder awaits the owner

**Evidence.** The transaction record is `transactions/TRANSACTIONS_2026W5.json`, keyed by GSIS `00-0041096`.

| Event | Effective | Evidence |
|---|---|---|
| WAS waived (W03) | 10-08 | roster capture `20261009T192103Z` |
| MIA claimed | 10-09 | roster capture `20261010T074137Z` shows MIA ACT; Dolphins announcement and NFL waiver log cited by the review; PFT and Pro Football Rumors as discovery |

Weeks 1–4 remain attributed to WAS.

**Fixes, in order:**
1. **Roster slice refreshed** (earlier today, `1e4c1fba`): the universe has him at MIA, not WAS.
2. **Transfer guard** (`fd25431f`), in `nfl/tools/classic_slate_state.py`: a player whose observed usage or usage rank
   was measured at another club carries none of it into his new club. The guard records `club_transfer`; the rank
   comes from the current chart under the existing no-usage limit. Only Allen is affected on this slate.

**Before → after:**

| Build | DK points | Role | Basis |
|---|---|---|---|
| Roster build | 1.22 | ROTATIONAL | ranked MIA RB3 by his WAS usage |
| Prelock | **0.70** | FRINGE | unranked |
| With the proposed `proj_v1` patch as well | 0.60 | | |

**Remaining defect (W5-G24).** `proj_v1.current_season_shares` divides his WAS carries by MIA's totals, giving a 0.185
"current" carry share, about 0.10 DK. The fix is a 5-line patch
(`docs/sunday_executor/proj_v1_current_club_shares.PROPOSED.patch`). **It is not applied**, because editing `proj_v1`
breaks the recorded SC-APPEAR-1 replay pin (`test_sc_appear_1_production_path`). Changing a pinned production module
is your decision.

**Pool.** `dk_pool_check.py` now names IDENTITY_TEAM_CONFLICT: a DK row putting him on WAS fails the pool (tested).
His MIA eligibility stays unresolved until MIA's inactives, and he is blocked from upload until then.

### P0-3. Sunday inactives executor: NOT VERIFIED; authorized manual fallback rehearsed

Full audit: `docs/sunday_executor/SUNDAY_INACTIVES_EXECUTOR_AUDIT_2026-10-10.md`.

**Window.** All eight games share one window: kickoff 17:00Z, so the T-90 window opens at **15:30Z (11:30 ET)**.

**What `main` actually runs:**
- **`nfl-t90.yml`** is generated for week 1, last run **2026-09-15**; nothing is scheduled for 10-11.
- **The periodic capture** ran today at 06:07, 12:48 and 17:33Z, gaps of 4–6 h.
- **Since week 1, no inactives capture has succeeded inside a Sunday window:** W2 and W3 returned DEFERRED with no
  rows, and W4 had no capture in the window.

**Prepared, not deployed.**
- The week-5 schedule (`nfl-t90.WEEK5.PROPOSED.yml`) and its patch against `main`, which changes schedule lines only.
- Deploying it is your decision:
  - OD-4: it lands on the default branch;
  - OD-1: the job reads `nfl.com/inactives`, whose terms appear to bar automated retrieval.
- This branch's mode boundary forbids editing the workflow file, and the guard stays in force.

**Fallback, fixed and rehearsed.**
- **Fixed:** `sunday_paste.py` would have **failed** on this research-universe slate; it now takes `--state` and
  records per-club receipt times.
- **New gate:** `inactives_coverage.py` passes only when all 16 clubs have their own list at or after 15:30Z.
- **Rehearsal:**
  - paste;
  - gate: BLOCKED for all 16 clubs (REHEARSAL_NOT_EVIDENCE);
  - state → role → projection → worlds: rehearsed-inactive Jeanty is absent everywhere, and the label carries
    through.

## Questionable players: separate states, no probabilities

Every one of the 17 stored Questionable skill rows is either a scenario below or a low-volume row. Each OUT branch is
a counterfactual while the player is Questionable. Ranges are the 10th / 50th / 90th percentiles of the simulated
worlds.

**What the numbers do not include:**
- **No probability is estimated.** `injury_state_probability = NOT_ESTIMATED` in every receipt.
- **`p_plays` is depth-slot appearance, not medical availability.** Do not multiply it by a guessed injury rate.
- **"Workload-limited" is NOT IMPLEMENTED.** No engine control reads a workload note.

**Scenario receipts.** Every scenario (`scenarios_2026-10-10_prelock/<id>/RUN_OUTCOME.json`) records:
- `code_commit fd25431f`, `engine_code_dirty false`;
- base-state sha, cutoff `2026-10-10T18:22:50Z`, packet id, seed policy;
- labels research_only=true, legal_pool / game_day / upload = false.

**Propagation audit** (`SCENARIO_ANALYSIS.json`), **17/17 PASS**:
- each absent player's state is absent, role NOT_PLAYING, projection NOT_PLAYING with zero DK, and he is absent from
  the worlds;
- team attempts, carries and targets reconcile with the base;
- one starting QB workload per club;
- `market_arm` is FOOTBALL_ONLY.

The optimizer stage is BLOCKED by design until a DK pool exists: research-universe ids can never reach a portfolio.

All confirmed Outs are in the base, so they are preserved in every scenario: Hall, Mitchell, Monangai, Pittman, Diggs,
Mariota, Nailor, Hollins, Gilliam, Douglas, Joly, Brooks, Dulin, Wallace and Ryan. Players on reserve (Thornton Jr.,
Savion Williams, Tank Dell, Mallory) are excluded from the universe.

| State | Subject active-case DK [p10/50/90] | Main beneficiaries (active → scenario) |
|---|---|---|
| **LV Jeanty out** (Ankle/Foot; FP→LP→DNP) | 19.65 [9.6/17.9/30.3] | M. Washington Jr. 4.20→13.75; Bowers 18.59→22.02; Tucker 11.75→13.96 |
| **CHI Williams inactive** (Bagent starts either way) | 0.21 | none: an inactive backup removes only his backup share |
| **CIN Chase out** (concussion; protocol clearance separate) | 18.70 [8.6/17.5/30.4] | Higgins 16.77→25.07; Meyers →4.67; Gesicki →15.40 |
| **CIN Higgins out** | 16.77 [6.7/15.3/29.0] | Chase →22.51; Meyers →4.81; Gesicki →15.90; Chase Brown →19.33 |
| **CIN Chase + Higgins out** | — | Meyers →11.20; Tinsley →7.32; Gesicki →19.76; Chase Brown →21.90; C. Young →4.08 |
| **CIN Chase + Higgins + Young out** | — | Tinsley →13.80; Meyers →11.96; Gesicki →18.23 |
| **MIN Jefferson out** | 16.55 [6.5/14.7/28.2] | Addison 7.40→12.16; Hockenson 13.17→16.29 |
| **MIN Addison out** | 7.40 [1.8/6.3/14.0] | Jefferson →18.92; Hockenson →14.98 |
| **MIN Jefferson + Addison out** | — | Hockenson →19.72; Jennings 1.89→6.78; Felton →3.28 |
| **NO Kamara out** | 14.29 [6.9/14.0/23.8] | K. Miller 3.70→7.90; Olave 23.49→26.30; Shough 20.87→22.84 (QB +2.0 includes W5-G22) |
| **NE Stevenson out** | 13.47 [6.3/12.7/22.3] | Henderson 5.42→10.34; Kiner →4.04; Doubs →18.16 |
| **WAS McLaurin out** | 15.46 [6.8/14.6/26.8] | A. Williams 7.96→11.67; Burks 3.21→6.53; D. Brown →4.43 |
| **TEN Tate out** | 14.98 [6.3/13.5/26.2] | Wan'Dale Robinson 9.59→13.93; Ridley →4.08; Ayomanor →7.46 |
| **IND Keenan Allen out** | 10.75 [3.9/9.9/19.2] | Treadwell 3.99→7.75; Downs →16.25 |
| **PIT Dowdle out** | 6.49 [1.6/5.4/12.5] | Homer 1.42→4.35; Warren 18.68→20.82 |
| **MIA Wright out** | 2.13 [0.1/1.3/6.0] | K. Allen 0.70→2.13 (eligibility unresolved); Herman 0.69→2.11 |

**Not given scenarios** (low volume, each under 2.4 DK even if active): Slayton (IND), Barion Brown (NO),
Martin-Robinson (TEN), Colbie Young (CIN; covered in the joint CIN state).

**Mechanics that still distort these states** (measured, not repaired):
- **QB inherits an absent RB's carries (W5-G22):** NO and NE QBs lean high by roughly 1–2 points.
- **Rank-ceiling lift on promotion (RC-1, preregistered):** Higgins and Robinson lean upper.
- **Team volume and efficiency are invariant to absences:** no club gets worse when a star sits.
- **No in-simulation did-not-play states (W5-G16):** a late inactive is handled by choosing the evidence-matched
  scenario at lock and rebuilding, never by keeping a known-inactive pick.

## Source conflicts recorded, not merged

- **Jeanty:** the Raiders table and the NFL table say Ankle/Foot; the NFL summary article says hamstring. The state now
  keeps the secondary injury (Ankle + Foot). Keenan Allen's record keeps Groin behind the rest-day entry.
- **Williams:** a Sun-Times headline (10-05) said "ruled out". The Friday official report says Questionable, and the
  later Bears release names Bagent as starter. The Questionable designation and the named starter are both admitted;
  the earlier "ruled out" is superseded and not admitted.

## Before inactives: what the owner must supply

1. **DKSalaries.csv for the Early Only (8-game) Classic slate**, dropped in `nfl/dfs/inbox/drop/`. Not the main slate,
   a prior week, a Showdown file or a third-party list.
   - `dk_pool_check.py` validates the game set, kickoff, positions, salaries, ids and identity, including
     IDENTITY_TEAM_CONFLICT.
   - DK AvgPoints is never read as football.
   - DKEntries is not needed for research portfolios.
2. **Decisions:**
   - the `proj_v1` patch (W5-G24);
   - OD-1 / OD-4 for the T-90 schedule;
   - the DST mean decision.
3. **At 15:30Z Sunday:** the 16 official club inactive lists, through the paste route
   (`docs/sunday_executor/…AUDIT… §4`), or the networked agent's captures (OUT-045). The gate must PASS before any
   game-day label changes.
