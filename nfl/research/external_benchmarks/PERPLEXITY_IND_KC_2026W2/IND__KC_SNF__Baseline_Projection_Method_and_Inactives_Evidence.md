# IND @ KC (SNF 2026-09-20, kickoff 00:20Z): inactives-adjusted baseline usage projections

Label: BASELINE_HEURISTIC, NOT_PROMOTED_MODEL. This is not output of the repository's promoted model (repo CURRENT_STATE.md: "No predictive model. NFL-1 not authorised."; the only board in `nfl/product/boards/` is `2026_01_SF_LA`). It has not been evaluated against the eight-rule promotion standard, no forward-chain parameter selection was performed (weights below are hand-set), and no opponent adjustment is applied. Sportsbook prices, commercial projections, and the Hard Rock board were not used as inputs anywhere in this build.

## Official inactives used (governing source: NFL.com Week 2 inactives article, retrieved 2026-09-20T23:08Z)
Source: https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
- Colts: LB Austin Ajiake, WR Ashton Dulin, RB DJ Giddens, DE George Gumbs Jr., QB Riley Leonard (emergency third QB), G Dalton Tucker
- Chiefs: OT Josh Simmons, S Chamarri Conner, TE Jared Wiley, QB Garrett Nussmeier, DT Bryson Eason, OT Diego Pounds, DE Jack Pyburn
Matches the owner-supplied screenshot (ESPN-style card, secondary). Team-site posts exist ("Colts announce 6 inactive players for Week 2 game vs. Kansas City Chiefs"; "Week 2 Inactive Players | Colts vs. Chiefs") but their raw bytes were not captured for this build. The 04:52Z-style raw evidence standard of the inactives package was NOT met here; treat as INCOMPLETE evidence, COMPLETE membership.

Offensive-usage effect of the inactives is small: Dulin had 1 Week 1 target, Giddens and Wiley had 0 Week 1 touches, Simmons and Conner were already out in Week 1 (so Week 1 usage already reflects the Benson-at-LT line). No IND RB other than Jonathan Taylor recorded a Week 1 carry; the RB2 with Giddens out is UNKNOWN from play-by-play and Taylor's carry share (0.865) is therefore likely overstated.

## Method (all from nflverse public play-by-play, 2025 REG + 2026 Week 1)
- Team volume: plays = 0.75 x 2025 plays/game + 0.25 x 2026 W1 plays; pass rate blended the same way. Pass plays include sacks; rush plays include QB scrambles.
- Player shares: target share and carry share = weighted blend of 2025 share (weight = min(games,8); x0.6 if the player was on another team in 2025: Walker SEA, K.Allen LAC) and 2026 W1 share (weight 2.5). Only players who recorded a Week 1 target, carry, or attempt are projected; no roster inference.
- Efficiency: player yards/target, catch rate, TD/target, yards/carry, TD/carry shrunk toward 2025 league means (k = 60/60/150/150/200 opportunities). QB yards/att, TD/att, INT/att shrunk with k = 300.
- Shares renormalized among active players with 3% of targets and 2% of carries left to "other".
- dk_pts_no_bonus: DraftKings scoring without the 100/300-yard bonuses.

## Known weaknesses (not fixed, stated)
- No game-script, opponent-defense, weather (8% rain, 9 mph wind per screenshot), or home/away adjustment.
- Hand-set weights; not validated on any holdout.
- Point estimates only; no distribution, so no prop-level probability claims should be made from this file.
