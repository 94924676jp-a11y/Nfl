# Football-world coherence repair (event-linked worlds): pre-registration

Status: SHADOW_ONLY. Written 2026-10-07, before this harness scored any 2025 or 2026 game. Up to this point the
only runs have been in-sample 2024 smoke runs (`dry-run`, with the gate closed), and their numbers are not
evidence.

Harness: `nfl/research/coherence/event_linked_world.py`. Checker: `nfl/research/coherence/invariants.py`.
Tests: `nfl/tests/test_event_linked_world.py`.

Frozen inputs, all from 2024 or earlier:

- `nfl/research/coherence/EVENT_LINKED_FROZEN.json`, sha256
  `b3853c56c8e57956c692ba406b11e71f8b90dba4007bcb4576134dbd2a19336e`. Hash of its event rates:
  `b3bc161b431831c1a4ec356376039dc4d69773131849742f03c8f7e9c4f7d1fc`.
- The SC-COH-1 clean refits, reused unchanged: `nfl/research/coherence/SC_COH_1_CLEAN_FROZEN.json`, sha256
  `e0e4243e40b4c81f95481d3458d8e89235165fbc76178d97a20e5c97901f41c6`, `fits_sha256`
  `19c7928d87c47aaa1926a4b1a759f752d71067f2de1129e91e17674834c86646`. The harness refits them before scoring
  and requires the same hash.

The harness refuses to score unless this file and both frozen files match, byte for byte, the hashes recorded in
`nfl/research/coherence/EVENT_LINKED_PREREG_LOCK.json`. The refusal codes are `EL_PREREG_CHANGED`,
`EL_FROZEN_CHANGED` and `EL_CLEAN_FROZEN_CHANGED`.

## 1. What is being repaired

The SC-COH-1 clean evaluation (`SC_COH_1_CLEAN_EVAL.json`, 2025 confirmation weeks, 108,800 club-worlds) counted
these breaks in the live transform chain. The root causes below were verified by reading the code.

| Id | Where | What it does | Identity it breaks | Count |
|---|---|---|---|---|
| R1 | `nfl/tools/classic_slate_run.py:106-124` (`efficiency_worlds`) | Multiplies each player's pass, rush and receiving yards by his own factor, independently | QB passing yards = sum of receiving yards | 0 → 106,879 |
| R2 | `classic_slate_run.py:125-126` | Draws interceptions Binomial(attempts, rate) without reading the DST takeaways already fixed by `game.py:323` / `dst.py:241-253` | Opposing QB INTs ≤ DST takeaways | 25,965 |
| R3 | `showdown_slate_run.py:94-95`, `classic_slate_run.py:276-277`, then `anchor_means:150` | Rescales DST DK multiplicatively and leaves the components untouched | DST DK = tier + components | 0 → 104,113 |
| R4 | `nfl/sim/game.py:472, 515, 483-490, 301-316, 360-361` | Draws receptions, receiving yards and TDs independently. Leaves a ghost rushing-TD bucket. Draws points continuously. Has no sack events | Yards and TDs require a catch or carry. Team TD = pass TD + rush TD. Points are an event sum | 103,757 / 28,733 / 6,960 / 3,633 / 107,308 |
| R5 | `nfl/tools/kicker_world.py:204-212` | Derives FGs as a remainder of the non-event points | Points = 6 TD + XP + 2·2pt + 3 FG + 2·safety | remainder < 0 in 15,319 |

## 2. The replacement (registered design)

The choice is a transformation of the incumbent's raw draw into event ledgers, not a new generator. The incumbent's
volume engine is kept exactly: the same `nfl/sim/game.py:simulate_game_centred` call, the same seeds and the same
2024-or-earlier refits. A score difference can then come only from the accounting repair and its declared
re-expressions.

**EL_S0, raw.**

- Each pass attempt is one event: passer, intended receiver or throwaway, complete flag, yards if complete, TD flag,
  INT flag, and a fumble flag with the fumbler. Each sack is one event: passer, yards lost, fumble flag. A sack is
  not an attempt. Each carry is one event: rusher, yards, TD flag, fumble flag.
- Kept from the incumbent: attempts per QB, targets per receiver, receptions, throwaways, carries per player, club
  passing yards, per-player rushing yards, and the passing-TD and club-TD counts.
- Yards and TDs that the incumbent placed on a player with no reception or carry are moved to a teammate who has
  one. The re-expression rules are listed in `EVENT_LINKED_WORLD.json` `DESIGN.re_expressions_declared`.
- Sacks, INTs and fumbles lost on an offence are the opposing DST's incumbent tuple. That tuple is the empirical
  joint draw within the band of the same world's points (`dst.py`). Takeaways are split into INTs and fumbles using
  the 2021-2024 share. So the DST's sacks, INTs and recoveries are the offence's events.
- D/ST TDs are attached to a takeaway with the 2021-2024 probability; otherwise they are kick or punt returns.
- Tries follow every TD. FGs follow `kicker_world`'s remainder rule, applied to the incumbent's latent points with
  the 2021-2024 `fg_share`. The latent points drive the FG count and are never used as a total.
- Team points = 6·TD + XP + 2·2pt + 3·FG + 2·safety, exactly.

**EL_S1, efficiency per event.**

- Each completion's yards are multiplied by the receiver's production factor (`classic_slate_run.py:113`,
  MIN_SIM_OPPORTUNITIES 30). Each carry's yards are multiplied by the rusher's factor.
- Passer yards are the sum of the same events.
- The QB's own yards-per-attempt row is not applied, because that would scale the same yards twice. The resulting
  drift is reported as `qb_centre_drift`.
- INTs are not redrawn.

**EL_S2, DST level on event rates.**

- The anchor on the post-draw total is removed.
- For each defence and each event type (sacks, INT, fumbles lost, D/ST TD, safeties), the multiplier is
  m = club blended rate ÷ league blended rate. Both use the `dst_model.club_rates` form: weeks before W, plus the
  prior season at PRIOR_GAMES pseudo-games. These are the production anchor target's own inputs.
- Counts are thinned when m ≤ 1 (Binomial) and superposed when m > 1 (+ Poisson((m − 1) × the 2024-or-earlier band
  mean)). The events are then placed again.
- Points, points allowed and DST DK are recomputed from the events.

**EL_S3.** DK core and DK classic are computed from the reconciled stat lines only.

### Declared conventions

- **SACK_YARDS**: sack yards reduce the team's net passing yards, not the passer's gross yards.
- **ALL_PASSERS**: passing identities sum over every player who threw.
- **TWO_POINT**: a two-point try is a try, not a TD or a reception. DK's +2 to the player is NOT_REPRESENTED.
- **DK_PA_v1**: DST points allowed are the opponent's points minus its takeaway-return TDs, the tries after them,
  and its safeties. Kick and punt return TDs do count. Sources: the DraftKings rule text recorded at
  `external-research/engine-full-product-research-mandate-2026-09-21/nfl-full-product-research-packet.pplx.md:344`
  and `nfl/dfs/salaries/postgame/FINDINGS_2026W4_STANDINGS.md` F1.
- **Not represented, inherited from the incumbent tuples or not drawn**: kickoff-return TDs, blocked kicks, try
  returns, and 2pt player credit.
- **History-only exceptions, which a simulated world may never claim**: LATERAL (excuses P02, P05 and C01) and
  OFFENSIVE_FUMBLE_RECOVERY_TD (excuses C05).

## 3. Invariants (hard requirement)

The 46 invariants registered in `invariants.INVARIANTS` are all hard requirements:

- **Player scope**: P01-P12, including the weak forms P06W, P07W and P09W.
- **Club scope**: C01-C12, covering the passing, TD, points, try, FG-band, kicker-DK, net-yards and volume
  identities.
- **DST scope**: D01-D10, covering INT, sack and fumble identities, takeaway arithmetic, D/ST TDs and safeties on the
  scoreboard, DK_PA_v1, tier and DST DK.
- **Scored stage**: S01-S02, the DK core and classic recomputations.
- **Ledger**: E01-E06, covering event placement and the rule that aggregation reproduces every stat line.

They are checked after every stage of both providers: S0_raw, S1_after_efficiency, S2_after_dst and
S3_after_scoring. The checker never repairs anything. A field a provider does not draw is reported
NOT_REPRESENTED with a count of None, never 0.

## 4. Data

- **Fits**: every coefficient comes from 2021-2024 (EVENT_LINKED_FROZEN.json), or from the SC-COH-1 clean refits
  of 2024 or earlier, or is a named production constant.
- **Development**: 2025 regular season, weeks 2-18. 2025 has been read three or more times by SC-COH-1 work, so it
  is DEVELOPMENT ONLY. No claim rests on it. It may be re-run, and each run is numbered. Bug fixes after the lock
  are recorded in `DEVIATIONS`. A change that is not a bug fix needs a new registration.
- **Confirmation**: 2026 regular season, weeks 2-3, read once, from the pinned capture
  `nfl/research/postgame/pbp_2026.79b02496d26004ee.csv.gz` (sha256 `79b02496d26004eec350c9e671bcc92ba5cb2587e4fc6af22ada51d9513d89ac`, weeks 1-3,
  48 games). The harness refuses any other bytes (`EL_CONFIRMATION_FILE_CHANGED`).
  - Week 1 cannot be scored, because a point-in-time pool needs an earlier week.
  - Week 4 has no play-by-play, and its TEAM_GAME points are null. The only week-4 data is a player-week box
    (`nfl/postgame/raw/2026W4`), which has no scoring-event or DST attribution, so it is insufficient for these
    endpoints and is not used.
  - Pregame inputs for a 2026 week-W game come from 2026 weeks before W and the whole of 2025 as the prior
    season.
  - Before this registration, a grep of every earlier coherence harness (`sc_coh_1_*.py`,
    `team_coherence_history.py`) showed that each pins `EVAL_SEASON = 2025` and fits through 2024. 2026 appears in
    them only in comments and date stamps. 2026 weeks 1-3 have been read by production postgame grading, not by
    any coherence study, and no design choice here used them.
- **Machinery reused from the clean harness**: the football-only centre (`football_points.centre_for_game` on
  whitelisted TEAM_GAME), the volume centre, point-in-time SEASON_TO_DATE pools, the efficiency rows, the DST
  anchor target, and `guard_no_market`, which refuses any line, odds, moneyline, implied, spread, vegas, vig, juice,
  price, sportsbook, book, market, wager or bet field. The play-by-play whitelist is the clean one plus the kicking,
  try, sack-yard, lateral and play-order columns. None of those added columns carries a market token.
- **Worlds**: 400 per game. The incumbent seed is 20261008 + game index (the clean harness's seeds). The
  event-linked offsets are +7 (S0), +11 (S2) and +13 (incumbent kicker).

## 5. Scored variants

| Variant | Stage | Role |
|---|---|---|
| INCUMBENT_PROD | S2: simulator, then efficiency_worlds, then DST anchor (the live order) | primary comparator |
| INCUMBENT_RAW | S0 | secondary |
| EVENT_LINKED | S3 (after efficiency per event and DST rates) | primary candidate |
| EVENT_LINKED_RAW | S0 | secondary |

Pairs: EVENT_LINKED vs INCUMBENT_PROD (primary), EVENT_LINKED_RAW vs INCUMBENT_RAW, and EVENT_LINKED vs
INCUMBENT_RAW.

## 6. Primary endpoints

The rule is conjunctive. All three parts are evaluated in the confirmation phase.

- **(a) Zero invariant violations, at every event-linked stage.** This is a hard requirement. Every required
  invariant must be CHECKED and none may be violated. S01 and S02 are required at S3 only.
- **(b) Non-inferiority on CRPS.** For player DK-core CRPS and team-points CRPS, the ratio EVENT_LINKED ÷
  INCUMBENT_PROD must have an upper 95% bound below **1.02** under both the game-blocked and the week-blocked
  bootstrap.
- **(c) Non-inferiority on the joint scores.** The energy score and the variogram score (p = 0.5) of the 12-part
  game vector must meet the same condition: upper 95% bound below 1.02 under both blocks.

The 1.02 margin, at most 2% worse, is the value the SC-COH-1 registration declared. It is reused here as a
**declared value judgement**, not a derived quantity, and the owner may override it.

Passing earns the shadow label `ALL_PRIMARY_PASSED` and promotes nothing. A failure to show non-inferiority is not
evidence of inferiority. With at most 32 confirmation games, the intervals are expected to be wide.

## 7. Secondary and descriptive outputs

- CRPS, coverage (50/80/90), randomised PIT and count log score on every SC-COH-1 unit variable.
- DST DK scored against two actuals: the clean harness's full-score tier, and DK_PA_v1.
- Brier tail events at the frozen 2024 90th percentiles.
- The 15 coherence statistics against history, with the frozen SC-COH-1 equivalence margins (TOST at 90%).
- Invariant counts per stage for both providers.
- The event-linked accounting counters, the QB centre drift, and the DST multipliers.

## 8. Uncertainty

Game-blocked and week-blocked bootstraps, 2,000 resamples, seed 20261009. Means are ratio-of-sums, and every
comparison is paired: both providers are scored on the same units, and an unpaired comparison is refused.
Intervals are 95% percentile intervals, with 90% intervals for TOST.

## 9. Missing input and refusals

- A club-game without an earlier passer, target or carry is excluded and listed.
- A game without a football centre or volume centre is excluded and listed.
- A game is excluded from both providers and listed if the incumbent refuses it (`EL_INCUMBENT_REFUSED`, for
  example VOLUME_CENTRE_NOT_RECONCILED), or if its raw draw cannot be re-expressed
  (`EL_INCUMBENT_VOLUME_NOT_RECONCILED`).
- Any other named error stops the run. Empty or partial input is never reported as a result.

## 10. Stop rules

1. Confirmation is read once, only after a development run of the same code (`EL_CODE_CHANGED_SINCE_DEVELOPMENT`),
   only at the registered settings (`EL_CONFIRMATION_NOT_AS_REGISTERED`), and never again
   (`EL_CONFIRMATION_ALREADY_READ`). Each attempt is recorded before any 2026 row is read.
2. Whatever the result, STATUS stays SHADOW_ONLY. No production file is changed and nothing is promoted.
3. A model change after confirmation needs a new registration, a new holdout and a new name.
