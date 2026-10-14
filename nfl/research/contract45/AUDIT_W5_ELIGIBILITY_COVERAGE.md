# Audit: W5 Classic eligibility is a coverage problem (owner OD-002, 2026-10-14)

**What this file is.** A measurement of the 2026W5 Early-Only Classic slate. The state was built
`pit_exempt` (logic replay, NOT_POINT_IN_TIME) from the slate's own registered inputs. Projections come from
role_state → proj_v1 (FOOTBALL_ONLY) in a temporary directory.

**Policy.** This is not a forecast and changes no release. Under OD-002 every certified W5 release would now refuse.

## What the roster evidence was

| item | value |
|---|---|
| Roster capture | `nfl/vintage/weekly_rosters.8729b73ef500cdf9.raw.csv.gz` (nflverse weekly rosters) |
| Capture clock | `20261010T074137Z` (vintage manifest capture id), **33.3 h before the 13:00 ET kickoff** |
| Elevation records | **none registered** for the slate |
| Transactions | `classic_early_2026W5/transactions/TRANSACTIONS_2026W5.json` |
| Corroboration list | declared; under OD-002 it no longer filters anything |

## The 99 players the first cycle-2 draft withheld

| question | answer |
|---|---|
| Truly (confirmed) ineligible | **0 provable from this repository.** All 99 were ELIGIBILITY_UNRESOLVED, none CONFIRMED_INELIGIBLE. |
| Practice squad without an elevation record | **92**, across 16 clubs (5 to 7 per club) |
| Absent from the week capture | **7.** All are identity-unresolved or deep reserves, each projected under 0.05 DK. |

**A bound, not a count.** The NFL practice-squad rule (two standard elevations per club per game) would cap the
eligible players at 32 of the 92, so at least 60 were ineligible.

- This bound is **not used anywhere in code.**
- The rule's text must be confirmed against the league source; engineering has no network.
- The bound cannot say **which** 60. That needs the elevation records (RES-009).

**Distortion from withholding them** (incumbent, which keeps them, against withheld):

| measure | value |
|---|---|
| Total projected DK the incumbent gave the 99 | **3.13** |
| Median player | 0.018 DK |
| Largest | Van Jefferson WAS 0.56; Sterling Shepard NYJ 0.32; Salvon Ahmed CHI 0.17 |
| Largest club share of club volume | WAS: 1.4% of targets, 0.6% of carries |
| Largest change in a club's skill-position total | 0.055 DK (redistribution keeps club volume) |

**Reading.**

- The W5 distortion was small in points.
- The defect was the **policy**, not its size. Withholding the unresolved would have falsely excluded any player who
  was in fact elevated. Veterans on the practice squad, such as Van Jefferson, are the players clubs elevate.
- OD-002 keeps them in the forecast, labelled with the missing evidence and unselectable. A certified release now
  refuses while any of them carries projected opportunity: **all 99 do** (7.64 DK in the corrected state).

## Reserve, exempt and released under OD-002 (ELIG-D3)

| count | outcome |
|---|---|
| RES/EXE/CUT players in the W5 pool | 56 |
| Absent on roster grounds | **49**; under the 2026-10-11 corroboration rule only 5 were |
| Already out on the official report | 5 |
| **Conflicts** | **2**: a RES capture against a reported activation, both reported AFTER the Friday capture. Tim Patrick NYJ ("The Jets activated Patrick (groin)…") and Ben Yurosek MIN. Left as the incumbent had them, unselectable; the release record refuses. |

**Effect of the 44 newly absent.**

- The incumbent had given them **18.75 projected DK**, 42 of them above zero. The largest were Josh Jacobs GB (EXE)
  3.25, De'Von Achane MIA 3.17, Travis Etienne Jr. NO 2.76, Josh Oliver MIN 2.72 and A.J. Brown NE 1.20.
- Their volume is redistributed to active teammates. The largest change in a club's total is 0.29 DK (GB).

## What this shows about "sufficiently current" (ELIG-D4, owner standard needed)

1. **The capture predates the Saturday transaction window.** Both conflicts are players activated after it. A Friday
   capture is therefore current evidence that a player was **on** a reserve list on Friday. It is not proof that he
   was still there at Sunday's kickoff.
2. **The freshness is now recorded.** Both the state and the release record carry `roster_source_freshness`
   (capture clock, hours before kickoff). Nothing yet acts on it.
3. **Turning it into a rule needs a standard.** Two candidate standards:
   - a capture after the league's final pre-game transaction deadline;
   - a declared transactions feed covering the gap.

   Either is a value judgement or a sourced rule, so it is the owner's. Until it is set, a stale capture is reported,
   not silently trusted or silently discarded.

## What closes the coverage gap

- **RES-009:** capture game-day elevation records per slate, before the release cutoff. With them, each of the 92
  becomes confirmed eligible or confirmed ineligible.
- **A roster or transactions capture after the last pre-game transaction window,** so reserve statuses are current at
  kickoff.
- **No probability of eligibility is used,** and none will be without registered historical evidence (OD-002).
