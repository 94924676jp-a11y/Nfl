# NFL Showdown engine: excellence program (owner directive 2026-10-05)

Status of every item as of 2026-10-05, before ATL @ NO lock. **HAVE** = in the code path tonight;
**PARTIAL** = present with a named gap; **MISSING** = not built. Nothing here is validated:
PROJECTION_SYSTEM_STATE stays NOT_VALIDATED, and no item is promoted on one slate (item 18).

**Tonight vs after lock.** The same day's finalization directive says "do not introduce a
last-minute structural rewrite" of DST. This directive says "until full coupling is implemented,
label DST tails UNVALIDATED". Both hold if the DST coupling is the first post-lock job and the
label goes on tonight. That is the reading applied. Tonight adds reporting only: tail labels,
ROLE_DATA_MISSING, uncertainty reason codes, the correlation table, and candidate counts by game
script and QB count.

| # | Item | Status | Evidence / gap |
|---|---|---|---|
| 1 | Full player coverage | HAVE | every DK row ends PROJECTED / PROJECTED_WITH_UNCERTAINTY / ZERO_OPPORTUNITY / INACTIVE / BLOCKED (`showdown_portfolio.classify`); counts by position in the audit; DK input gate (`dk_input_gate`) |
| 2 | One joint world | PARTIAL | total, margin, volume, yards and TDs reconcile by identity (`nfl/sim/game.py`, 7 identities checked per game); kicker scored from the world's points and TDs (`kicker_world.py`); DST points allowed from the opponent's world points. **Gaps:** QB INT ↔ DST INT, sack taken ↔ DST sack and fumble lost ↔ DST FR are drawn independently (DST tuple vs QB efficiency step); defensive/return TDs do not add to the scoreboard; QB sacks taken and fumbles are not simulated |
| 3 | Role model | PARTIAL | target/carry share, red-zone share, depth, teammate-absence redistribution in `proj_v1`; snaps/RZ/GL/3rd-down/2-minute measured in `showdown_role_review.py` but reported, not consumed. Routes, route participation, alignment, personnel: **ROLE_DATA_MISSING** (no capture; outbox 2026-10-04). Week 4 confirmed the depth-curve concentration defect (postgame report §2) |
| 4 | Opportunity first | HAVE (QB/RB/WR/TE/K) | attempts/carries/targets projected before DK scoring; kicker FG/XP attempts per world. QB dropbacks and RB routes are not separate quantities; DST opportunity is the empirical tuple |
| 5 | Kicker | HAVE, UNVALIDATED | same-world FG_ATT, XP_ATT, measured make rates by band, distance mix, mean/P75/P90/P95, P(10+), P(15+) (`kicker_world.py`, audit `kickers`). Missed-FG rule unverified: SCORING_A/B both reported, with materiality |
| 6 | DST event-linked | PARTIAL, tails UNVALIDATED | points allowed from simulated opponent scoring; sacks/takeaways/TD/safety from the measured joint tuple in that band. Coupling to the opposing QB's events is the P0 gap; measured every run in `dst_coherence` |
| 7 | CPT | HAVE | CPT = same-world FLEX × 1.5; CPT salary from DK's own item; every archetype, K and DST included, gets a forced-captain exact solve; CPT board carries ceiling, first-place proxy, salary left, correlation with own QB, script dependence |
| 8 | Game scripts | PARTIAL | away/home lead, shootout, low total, blowouts, one-score, run-control, pass-heavy comeback, kicker-heavy, turnover-heavy (QB INTs), DST spike, read off the same worlds; candidate counts by best script. Overtime is inside the empirical residuals, not a labelled world |
| 9 | Correlation | HAVE (measured, not validated) | same-world correlation table: QB-WR/TE/RB, K-offense, DST-opposing QB/WR, RB-own DST, same-team receivers, opposing QBs, team points. Not yet validated against realised pairwise correlations |
| 10 | Ownership/field layer | MISSING for Showdown | `nfl/field/` is classic-only and NOT_CALIBRATED_NO_ARCHIVED_CONTEST_OWNERSHIP. Football never reads ownership (enforced by architecture: the portfolio reads draws only) |
| 11 | Duplication | PARTIAL | structural index only (salary used, chalk captain, top-six count, QB double stack, 5-1); no field frequency |
| 12 | Portfolio EV | PARTIAL | objective is top-tail world coverage against the exact per-world optimum (first-place proxy). P(top 1%), P(top 0.1%), expected payout: UNAVAILABLE until a field model exists |
| 13 | Candidate depth | HAVE | near-optimal generator + forced captain for every person; counts by CPT position, away-home split, salary band, best script, QB count (PIT@CLE test: 7,712) |
| 14 | External comparison | HAVE for classic | `classic_fc_diff.py`; the showdown equivalent is a copy of that decomposition (ROLE/VOLUME/EFFICIENCY/TD/INJURY/DEPTH/DATA/MODEL), not built for Showdown tonight |
| 15 | Uncertainty | PARTIAL | mean/median/P75/P90/P95 for every player; reason codes (designation, small sample, low prior confidence, backup QB, teammate absence). Widening by reason code is NOT applied: Week 4 measured WR/TE tails too narrow, the fix (P1) is role-volume variance, untested |
| 16 | Prelock audit | HAVE | `SHOWDOWN_<GAME>_FINAL_BOARD.md/.json` from `showdown_tonight.final_board` |
| 17 | Validation | PARTIAL | classic postgame grader exists (`nfl/postgame/classic_week.py`); a Showdown grader (CPT performance, optimal-lineup capture, first-place distance) is to be adapted from it after the game |
| 18 | Promotion | HAVE (governance) | CLAUDE.md rules 2-5; nothing here promoted |
| 19 | Priority order | adopted below | |
| 20 | Success condition | not met | items 2, 6, 10, 12 are the gap |

## Engineering order (owner)

- **P0 — joint-event coherence.** Simulate per club per world: dropbacks, sacks taken, interceptions
  thrown, fumbles lost, from measured rates conditional on the world's volume and game state. The
  opposing DST's sacks, INTs and fumble recoveries then **are** those events (an identity, not a
  correlation); defensive/return TDs and safeties are drawn per world and added to the scoreboard so
  points allowed and team points stay one ledger. Acceptance: identity checks QB INT == DST INT and
  sacks taken == DST sacks in every world; held-out calibration of DST points no worse than today.
  Also (found 2026-10-05 from the Week-4 standings, `nfl/dfs/salaries/postgame/FINDINGS_2026W4_STANDINGS.md`
  F1): DK's points allowed EXCLUDES the opponent's defensive and return touchdowns. Once those TDs are
  per-world events, points allowed must be computed that way, in the simulator and in the grader.
- **P1 — role/usage allocation** (POST-LOCK #1, task #120): within-club share model with depth-player
  involvement and role-volume variance; acceptance per the Week-4 postgame report §9.
- **P2 — Showdown ownership/field/duplication model**, fitted when archived Showdown contest
  ownership exists (OUT-040); until then structural and labelled NOT_CALIBRATED.
- **P3 — contest EV optimisation** against the real payout table using the field.
- **P4 — prospective calibration**: freeze every slate, grade after, accumulate across slates.
