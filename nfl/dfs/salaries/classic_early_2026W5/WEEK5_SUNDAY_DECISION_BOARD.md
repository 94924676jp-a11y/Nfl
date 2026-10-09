# Week 5 Classic (Sunday 1:00 ET, 8 games): decision board, refreshed Friday 2026-10-09 ~19:55Z

**Readiness: NOT READY to produce entered Classic portfolios.** Three things are missing:
- the DraftKings salary file;
- the official Friday designations (not yet published in the nflverse feed at 19:21Z; trigger 21:30Z);
- a starter decision for CHI (see A1).

Our independent projections exist (266 players, 2,000 worlds), but **eleven player numbers are unreliable** (§3) and the
simulated worlds carry five known unrepaired defects (§6). Nothing here recommends a lineup or a wager. FC is a
benchmark only.

**Owner rulings recorded:** `docs/OWNER_RULINGS_RELAYED_2026-10-09.md`.
- Tie repair provisionally retained.
- Accounting repair not promoted.
- Opponent adjustment: research only.

## 1. Official eligibility and QB status

**Captured OFFICIAL tier.** The newest capture is the nflverse injury file at 19:21Z (Thursday practice). No Sunday-club
game designation is in it yet.

**SECONDARY tier (Friday web reports, discovery only:** `raw/classic_early_2026W5/NEWS_SUPPLEMENT_WEB_FRIDAY_2026-10-09.63b7c01f3a1c9533.json`).
These do not move the engine until captured.

| Club | QB in the engine | Expected starter (QB verification) | Friday reports (SECONDARY) | Status |
|---|---|---|---|---|
| **CHI** | **Caleb Williams** (stale 10-08 chart) | **Tyson Bagent** | Williams listed Questionable after a limited Friday practice; Ben Johnson: Bagent starts | **CONFLICT: see A1** |
| **WAS** | Jayden Daniels | Daniels | Quinn: Daniels will play; **Diggs ruled out**; McLaurin Questionable (first practice Friday) | provisional |
| CIN | Burrow | Burrow | **Chase Questionable**: in concussion protocol, practised Friday | QB fine; WR1 uncertain |
| GB, MIA, LV, NE, MIN, NO, CLE, NYJ, IND, PIT, HOU, TEN, NYG | chart QB1 | same | — | consistent across sources, not yet official |

**A1, CHI. A Questionable tag does not make the engine drop Williams.** It consumes a starter only from a captured
official document, or one you relay. Johnson's statement reaches us only through outlets. Two ways to resolve it:
- you relay "Bagent starts" (recorded as OWNER_RELAYED); or
- an official inactive or Out is captured Sunday.

Until then, use the `CHI_BAGENT_STARTS` scenario. **Do not use production's 21.92 for Williams.**

## 2. Major personnel dependencies (scenario runs on the final engine; `research_projection/final_2026-10-09/`)

| Dependency | Production now | If it goes the other way | Notes |
|---|---|---|---|
| CHI: Bagent starts | Williams 21.92, Bagent 0.07 | Bagent **19.01**, Williams 0, Swift +0.8 | **CHI receivers move < 0.5**: QB identity is not consumed (W5-G18), so their numbers are unreliable either way |
| CHI: Monangai out (reported) | Monangai 7.61, Swift 16.85 | Swift **19.74** | — |
| CIN: Chase out | Chase 18.70, Higgins 16.77 | Higgins **25.07**, Gesicki +1.9 | the Higgins jump is partly slot mechanics (§3) |
| WAS: Diggs out (reported) | Diggs 11.74, McLaurin 13.77 | McLaurin **15.91**, A. Williams 4.17 → **8.12** | — |
| WAS: McLaurin out | | Diggs 16.48 | if both are out, A. Williams becomes WR1 (not run) |
| WAS: Daniels does not start | Daniels 19.83 | Mariota 18.07, or Kaliakmanis 12.44 | Quinn says Daniels plays |
| NYJ: Hall + Mitchell out | Hall 15.00, Mitchell 8.09, B. Allen 4.72 | B. Allen **10.56**, G. Wilson **19.71**, I. Williams 7.52, Sadiq 9.55 | both DNP Wednesday and Thursday |
| PIT: Pittman out | Pittman 7.97 | R. Wilson **8.43**, Bernard 3.38 | latest OFFICIAL practice: DNP Thursday (foot); the engine state still shows Wednesday's Limited (W5-G14) |

## 3. Projections: corrected, provisional, unreliable

**Corrected by the tie repair (production).**

| Player | Before | After | Notes |
|---|---|---|---|
| Chase | 14.81 | **18.70** | — |
| Higgins | 21.09 | **16.77** | — |
| McLaurin | 9.82 | **13.77** | — |
| Diggs | 14.70 | **11.74** | — |
| Freiermuth | 10.49 | 10.49 | unchanged; TE usage-first |
| Washington | 3.99 | 3.99 | unchanged |

Player-level review: `WEEK5_ROLE_CHANGE_REVIEW.md`. The ordering is supported for CIN and PIT; WAS is decided by
availability.

**Unreliable: do not use as point estimates without the stated condition.**

| # | Player | Production | Why | Use instead |
|---|---|---|---|---|
| 1 | Caleb Williams (CHI QB) | 21.92 | Bagent expected to start | CHI_BAGENT_STARTS |
| 2 | Tyson Bagent (CHI QB) | 0.07 | same | CHI_BAGENT_STARTS: 19.01 |
| 3 | CHI receivers: Odunze, Burden, Loveland, Swift (and Monangai) | starter-QB volume | QB identity not consumed (W5-G18) | no validated adjustment; treat as wide uncertainty |
| 4 | Breece Hall (NYJ) | 15.00 | DNP Wed and Thu; "essentially out" | NYJ scenario (expectation ≈ 0) |
| 5 | Adonai Mitchell (NYJ) | 8.09 | same | NYJ scenario |
| 6 | Braelon Allen (NYJ) | 4.72 | depends on Hall | 10.56 if Hall is out |
| 7 | Michael Pittman (PIT) | 7.97 | DNP Thursday; "multiple weeks" | PIT scenario |
| 8 | Stefon Diggs (WAS) | 11.74 | reported OUT by Quinn | WAS_DIGGS_OUT |
| 9 | Ja'Marr Chase / Tee Higgins (CIN) | 18.70 / 16.77 | Chase Q (concussion) carries P(plays) 1.0; Higgins is discounted to 0.861 by the slot table despite 72–93% snaps | read both with CIN_CHASE_OUT |
| 10 | Jaylin Noel (HOU) | 0.48 | slot P(plays) 0.077 despite targets every week (W5-G16); rank pushed down by the Collins/Hutchinson tie | AP-1 research gives 3.71 |
| 11 | Kyle Monangai (CHI) | 7.61 | turf toe, reported out; also slot P(plays) 0.635 | CHI_MONANGAI_OUT |

**Provisional (number defensible, a known defect or open question applies).** Each is listed with its FC benchmark.

| Player | Ours | FC | Open question |
|---|---|---|---|
| Warren | 18.38 | 13.28 | TD expectation 0.63/game vs 0 TDs in 2026 |
| Doubs | 14.79 | 9.05 | renormalised volume, 7.0 targets vs 5.0 observed |
| Malik Washington | 14.34 | 8.16 | share ×1.31 renormalisation |
| Olave | 23.49 | 18.17 | **new foot injury, Limited Thursday**, not represented |
| Mason Taylor | 0.38 | 8.19 | — |
| Dowdle | 6.38 | 12.79 | — |
| McLaurin | 13.77 | 13.22 | Questionable |

**Also limited Thursday, undesignated:** Collins, Jeanty, A. Jones and Swift.

## 4. Material disagreements with FC (`fc_diagnosis/FC_DISAGREEMENT_DIAGNOSIS_FINAL.{md,json}`)

Of the 16 players with |ours − FC| ≥ 5, plus the 4 FC omits:

| Verdict | Count | Players |
|---|---|---|
| Our number supported | 6 | McClain, Henderson, Jennings, Austin Jr., Theo Johnson, Hockenson |
| Provisional | 8 | B. Allen, M. Taylor, Dowdle, Monangai, Warren, Olave, Doubs, M. Washington |
| Unreliable | 6 | Bagent, C. Williams, Pittman, Hall, Mitchell, Noel |

Primary causes:

| Cause | Players |
|---|---|
| FC-specific (our number tracks 2026 usage) | 9 |
| Availability assumption | 6 |
| Volume model | 3 |
| Role judgement | 1 |
| Role defect | 1 |
| Identity errors | **0** |

## 5. Accepted fixes; remaining defects

**Accepted (in production):**

| Fix | Commit | Notes |
|---|---|---|
| Absent starter holds no depth rank | `8d7c9822` | — |
| Tied depth rank broken by evidence | `39340321` + `a8efedae` | provisional per owner; rollback = revert both |
| Football universe independent of the DK entries file | `d41ef192` | — |
| `world_accounting_check` reads each club's own game | `8e10cc5f` | validation tool only |

**Measured, not promoted:**

| Candidate | Result |
|---|---|
| RC-1 WR2 ceiling | half of 1,890 WR2-weeks realise above the cap; did not replicate on the real W4 pool. Preregistered W6–W11 |
| AP-1 appearance history | WR5 that played 3 straight weeks plays again 67% vs the engine's 7.7%. Preregistered W6–W11 |
| Accounting repair | damage detected; not promoted |
| **DST integer-event scorer** (`5e21aed2`, OFF) | root cause found: `classic_slate_run.py:150` multiplies a realised integer DST score by the mean anchor (raw draws 100% integer; published 92–98% non-integer). Fix keeps every club and player draw and rebuilds the DST from integer events. History (mean / P(≥15)): **6.49 / 9.8%**; incumbent 5.94 / 6.4%; fix (mean follows events) 6.35 / 7.5%. **Owner decision: whether the DST mean follows the events or the projection.** Kicker: no defect |
| Opponent adjustment (research) | **FAILS** its preregistered bar on held-out 2024–2025 (CRPS −0.9% to −1.5%, intervals include zero). Unplanned finding: the own-team baseline over-reacts (slopes 0.59–0.67) |

## 6. Simulation calibration and accounting limitations (`world_audit/WEEK5_WORLD_CORRECTNESS_AUDIT.md`)

**None of these can be safely repaired before Sunday.** The optimizer bias is stated for each.

| Defect | Size on Week 5 | Optimizer bias |
|---|---|---|
| Star lower tail too thin (D-01) | players projected 20+: P(<5 DK) 0.62% simulated vs 6.57% historical for 20+ ppg WR (Olave 8.8×, Collins 6×, Shough 20×) | **toward stars and stacks built on them** |
| World accounting (D-05) | receiving yards ≠ passing yards in 30,641 of 32,000 club-worlds (CHI receivers +28 yds/world, MIA −26); receiving yards with no catch 17,192; receiving TD with no catch 4,151 | toward CHI/GB/MIN pass-catchers; away from MIA/NYJ |
| No did-not-play worlds; slot P(plays) (W5-G16) | 157 players' P(plays) < 1 is spread as reduced volume in every world; no world is a backup-QB game | away from active WR2/WR3/RB2/TE2 |
| QB identity ignored (W5-G18) | CHI and WAS receivers unchanged under a QB switch | toward those receivers if a backup starts |
| DST rescale | 96% of DST worlds non-integer; factors 0.56–1.34 | distribution-based selection only: toward MIN/PIT/LV DST, away from NYJ/MIA/TEN/GB |

**Also:**
- Fumbles are not modelled.
- 93 cells exceed the NFL single-game passing record.
- Simulated-minus-projected TDs run NO +0.24 and CLE −0.28 per club.

**Conditional vs unconditional:**
- `dk_points` is P(plays) × if-plays, and the worlds are centred on it.
- `dk_points_if_plays` summed over a club is 28–59% higher than the club total. Never sum or jointly use the
  conditional numbers.

## 7. Readiness to produce independent Classic portfolios

| Requirement | State |
|---|---|
| Independent projections and worlds | **READY**: 266 players, 2,000 worlds, plus 10 scenario runs |
| Availability resolved | **NOT READY**: Friday designations, CHI starter, Chase protocol, Diggs/McLaurin, NYJ, PIT |
| Correct DK pool with salaries and ids | **MISSING**: no DKSalaries or DKEntries file |
| Optimizer inputs free of known bias | **NO**: §6. A portfolio built today would over-concentrate on stars and on CHI/GB/MIN pass-catchers |
| Ownership and duplication model | research only (FC-proportional no-fit incumbent declared; no Classic field model) |
| Payout tables | **MISSING**: no EV objective possible |

## 8. Exact requirements for final DraftKings salary mapping and upload

1. **The DK file for the Week 5 Sunday Early Classic slate.**
   - `DKSalaries.csv` is enough to map our universe to DK ids and salaries.
   - `DKEntries.csv` adds entry and contest ids and is required for the upload.
   - Register it as `pool_blob` / `entries_blob` in `early_only.SLATES['2026W5']` (its hash goes into the vintage
     manifest), then rebuild the state from the DK pool. The research universe is not uploadable by construction.
2. **Identity join:** every DK pool row must resolve to a GSIS id. Unresolved rows are carried as non-playable and
   counted, never guessed.
3. **Friday designations** captured into the vintage manifest (21:30Z trigger), then rebuild.
4. **CHI starter:** your relay, or a captured official document, entered through the evidence packet.
5. **Sunday official inactives** (15:40Z trigger), then rebuild, the roster-eligibility gate, `classic_upload_verify`
   and the freeze manifest before 17:00Z.
6. **Your decisions:**
   - the DST mean anchor;
   - whether to build portfolios on worlds with the §6 biases, with the caps unchanged;
   - payout tables, before any EV claim.
