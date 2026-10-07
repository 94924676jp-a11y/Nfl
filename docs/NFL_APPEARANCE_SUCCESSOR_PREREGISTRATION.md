# Appearance successor (SC-APPEAR-1 rates + strict hurdle gate + field-specific pi) — pre-registration

Status: **SHADOW_ONLY. Not on the production execution path. Nothing here promotes anything.**
Written 2026-10-07, before the 2025 development scores of this candidate were computed and before the 2026 week-5
seal was written. Its sha256 is recorded in
`nfl/prospective/appearance/APPEARANCE_SUCCESSOR_PREREG_LOCK.json` (chmod 444); the seal writer refuses to run if
this file's bytes no longer match that lock, and the grader refuses a seal whose recorded prereg hash differs.

Owner directive 2026-10-07, priority 2. Code: `nfl/research/appearance/appearance_successor.py` (core),
`nfl/prospective/appearance/seal_appearance_w5.py` (seal), `nfl/research/appearance/grade_appearance_seal.py`
(grader), `nfl/research/appearance/appearance_successor_dev.py` (2025 development scoring),
`nfl/tests/test_appearance_successor.py`.

## 1. Evidence classes, stated first

| Data | Class | Why |
|---|---|---|
| 2024 | FIT | every fitted pi comes from 2024 snap-count-dressed player-games only |
| 2025 | **DEVELOPMENT** | read three times already (SC-APPEAR-1 forward test, production-path replay, propagation prototype). The scores of this candidate on 2025 are the fourth read. They can describe the candidate; they cannot confirm it. |
| 2026 week 5 onward | **PROSPECTIVE** | each week sealed before its first kickoff, graded only after the games, by this document's rules |

No 2025 number in any artifact of this candidate may be quoted as confirmatory, and none may change anything in
sections 2-6 below after this file is locked.

## 2. The candidate, exactly

**Allocation (the means).** SC-APPEAR-1: the production allocator `nfl/tools/proj_v1.allocate_opportunity` with
the SC-APPEAR-1 rate placed at its appearance-rate read (line 879) for qualifiers, via
`sc_appear_1_production_path.allocate_with_hook`; production allocation for everyone else. A qualifier is an
RB (carries, targets), WR (targets) or TE (targets) with h = 3 (below). In 2025 development a qualifier must also be
dressed (as in every earlier SC-APPEAR-1 read); prospectively dressing is unknown pregame (section 4).

**History class h.** The number of the club's previous 3 games **present in the panel** (weeks strictly before the
scored week) in which the player recorded >= 1 of the field. A week absent from the committed panel is
**MISSING_FROM_REPO**, never zero participation. For the week-5 seal, 2026 week 4 is MISSING_FROM_REPO (the panel
holds weeks 1-3 for every club), so h uses weeks 1-3. This is the "last 3 games present" option; no player is
marked NOT_EVALUABLE.

**Field-specific pi** (P(>= 1 opportunity in the field | dressed, position, h)), fitted on 2024:

| cell | h=0 | h=1 | h=2 | h=3 (= SC-APPEAR-1 rate) |
|---|---|---|---|---|
| RB carries | 0.256000 (n 250) | 0.564706 (n 170) | 0.750000 (n 188) | 0.942434 (n 608) |
| RB targets | 0.254902 (n 306) | 0.483871 (n 248) | 0.659004 (n 261) | 0.884712 (n 399) |
| WR targets | 0.368201 (n 239) | 0.574766 (n 214) | 0.806780 (n 295) | 0.951830 (n 1038) |
| TE targets | 0.271028 (n 214) | 0.541063 (n 207) | 0.708812 (n 261) | 0.897287 (n 516) |

h = 3 is computed on exactly `sc_appear_1_forward.rows_for`'s rows (identical to the SC-APPEAR-1 rate). h = 0-2 use
the same estimator on `dressed_rows` (rows_for without its pregame-rank filter, which by construction contains no
h = 0 row in a table field, while the pools the gate is applied to do). Cells with n < 100 are refused (binomial SE
<= 0.05 derivation); none binds. Not gated, production allocation untouched: QB pass attempts and carries, WR/TE
carries.

**Gate.** Per club-world, from a separate stream `Random(seed + 7919)`: one uniform u per gated player; field f open
iff u < pi_f (one uniform per player, so an RB's two gates are comonotone: P(both closed) = 1 - max(pi)). Closed:
weight 0 in the field and in its TD share (receiving TD with targets, rushing TD with carries), so exactly 0.

**Hurdle (zero-truncated positive part).** The field's production Dirichlet-multinomial draw (`alloc()`, production
concentration, the drawn club total) is conditioned on every open gated player receiving >= 1, by rejection (at
most 200 redraws, a compute bound), else the reservation fallback (1 unit reserved per open player, remainder drawn
by the same `alloc()`); both count. Hence **P(N_f = 0) = 1 - pi_f exactly per gated field**, except in a world whose
club total is below the number of open gated players (HURDLE_INFEASIBLE, counted). Positive-part weights:
**TRUNCATION_MATCHED_RENORMALISED** — an open player's target conditional mean is his production unconditional share
over pi, renormalised over the open set; the weight delivering that mean after truncation is solved from the
beta-binomial marginal; pool weights are renormalised to the production pool sum so the unallocated (ghost) weight
stays at production's; a target conditional mean <= 1 is met by reserving exactly one unit (MEAN_FLOOR_BINDING:
there the mean rises to pi, because E[N] >= P(N > 0) — the hurdle holds the zero mass and lets the mean move).

*Selection of the positive part, on a NON-OUTCOME criterion, before any score:* both constructions were run on the
2026 week-4 ATL@NO pregame harness (1,000 worlds, seed 123), measuring mean drift of the simulated count against the
candidate allocation's expected count. PROTOTYPE_WEIGHTS: mean |drift| 0.398, max 1.391, ghost targets fraction
0.01425 (production 0.00016). TRUNCATION_MATCHED_RENORMALISED: mean |drift| 0.256, max 0.679, ghost 0.00018. The
second is the candidate. No outcome was read.

**Eligibility is separate.** A player in `availability.ABSENT_STATUSES` (or INACTIVE) is removed before shares are
built, exactly as production removes NOT_PLAYING rows (no share, no draws, no gate). **UNKNOWN_ACTIVE_STATE** is
treated as eligible: he stays in the pool and is gated; his pi is conditional on being active, so a grader scores him
only if found dressed (section 4).

**Identity.** Successor disabled (no gate key): byte-identical to production draws, stat lines and club worlds.
All pi = 1: **not** byte-identical by design (a gated field with pi = 1 is zero-truncated, P(0) = 0 exactly). Both
are tested.

## 3. The comparator

Current production: production allocator (depth table and group split as production calls them, `through=None`, on
the pregame panel), production `simulate_game_centred` (volume centre = projection, CLUB_TOTAL_IMPOSED, DIRICHLET,
n_calib = n_sims), FOOTBALL_ONLY centre (`football_points.centre_for_game`), then `classic_slate_run.efficiency_worlds`,
the DST anchor step and DK scoring, in showdown_slate_run's order. Same seed, same pool, same club volume centre in
both arms. Harness, not the live path: claims from `V.project_player` with priors through the previous season, club
volume from earlier weeks, QB starter proxy from prior pass attempts (the sc_appear_1_production_path harness).
Prospective seals use 2,000 worlds per arm per game.

## 4. Units and outcomes (prospective)

Pregame pool: a player is in a club's pool iff his most recent panel row of the season before the scored week
carries that club; sealed units are RB carries, RB targets, WR targets, TE targets of pool players whose position
comes from the roster index (USAGE_INFERRED players are allocated, not sealed). No information from the scored week
or later is read (panel truncated to earlier weeks; football centre reads earlier weeks only).

A unit is **graded** iff (a) its game's kickoff is after the seal's `written_at`, (b) the player is **dressed** for
that game — present in the nflverse `snap_counts` file for that season (offense or special-teams row), the same
definition as every 2025 read — and (c) the postgame panel carries the club's team row for that week. Outcome y =
the panel's count in the field; a dressed player with no panel row has y = 0. A game missing from the postgame panel
is NOT_GRADABLE, never zero. Undressed sealed players are excluded and counted (eligibility, not a forecast miss).

## 5. Endpoints and bars (prospective; all on graded RB/WR/TE units)

Let y0 = 1{y = 0}. Probabilities are clipped to [0.5/n, 1 - 0.5/n], n = worlds per arm.

**PRIMARY — draw-level zero-opportunity Brier, successor vs current production.** Per unit
d = (P0_draws_current - y0)^2 - (P0_draws_successor - y0)^2 (positive = successor better). Blocked by week (mean of
week means, SE = sd/sqrt(n_weeks)) and by club (32 blocks). Bar, all required:
1. club-blocked z > 2, and
2. week-blocked mean > 0 with t = mean/SE > t(0.975, n_weeks - 1) (3.182 at 4 weeks).

**POSITIVE-COUNT — conditional CRPS given > 0.** On units with y > 0: CRPS of each arm's count histogram restricted
to counts > 0 and renormalised, at y. d = CRPS_current - CRPS_successor. Bar: club-blocked mean >= -2 club-blocked SE
(not worse by more than 2 SE).

**RANK-1 NO-REGRESSION.** On units whose table-field depth rank is 1: the primary d's club-blocked mean >= -2
club-blocked SE.

**Verdict rule.** PASS iff primary, positive-count and rank-1 bars all hold. Anything else is FAIL. A pass would
mean the successor's world-level zero mass scored better than production's on unseen games; it would **not**
establish adequacy, DFS value, or calibration of the positive part beyond the stated bar, and it is not a promotion.

**Minimum sample before any verdict.** At least 4 graded weeks (weeks 5-8 at the earliest), at least 1,500 graded
units and at least 25 clubs with graded units. Before that the grader reports INSUFFICIENT_SAMPLE and no verdict.
**One look:** the verdict is computed once, at the first grading at which the minimum is met; later weeks are
reported descriptively and do not re-open it. A week whose seal was written at or after its first kickoff, or fails
its hash, is excluded (never imputed), and the exclusion is reported.

**Secondary, descriptive, no bar:** projection-layer Brier of both arms; log scores; DK-zero shares against
opportunity zeros; the same endpoints by cell (position x field x h) and by rank; ungraded/undressed counts; hurdle
counters (redraws, reservation fallbacks, infeasible worlds, floor binding).

## 6. 2025 development scoring (computed after this lock)

Same harness as `sc_appear_1_propagation.replay` (fit <= 2024, dressed universe, weeks >= 4, 1,000 worlds per arm),
arms CURRENT (production draws), CANDIDATE (SC-APPEAR-1 allocation, ungated) and SUCCESSOR (this candidate). The
endpoints of section 5 are computed with week blocks (15) and club blocks; reported as **DEVELOPMENT** only.

## 7. Limitations declared now

- Active players with zero snaps are invisible in both the fit and the grading (snap-count dressing).
- Simulator constants (concentrations, efficiency, football-points residuals) were fitted on data including 2025.
- The pi table is constant within (position, field, h): it carries no rank or share information, so the hurdle's zero
  mass discriminates only through h.
- MEAN_FLOOR_BINDING raises the mean of low-share players with high pi; club totals stay exact, so starters give up the
  difference.
- The prospective pool includes players who will be inactive (unknown pregame) and misses players who join a club
  after the panel's last week; both arms share that.
- The week-5 seal uses a panel one week stale (week 4 MISSING_FROM_REPO).
- The harness is not the live Showdown path.
