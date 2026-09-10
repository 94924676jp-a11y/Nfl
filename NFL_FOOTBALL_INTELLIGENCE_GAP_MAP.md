# FOOTBALL-INTELLIGENCE GAP MAP

**Date** 2026-09-10 · **Audit only. Nothing in Parts B or C was implemented.**

Classification vocabulary as directed: **PRODUCTION** (runs in the sealed
forecast) · **PARTIAL** (some of it runs) · **PROXY** (a different quantity
stands in) · **EXPERIMENTAL** (measured in research, never deployed) ·
**ABSENT** (not modelled anywhere) · **DATA_BLOCKED** (the input does not exist
to us).

Three rules were applied throughout. A thing is PRODUCTION only if it changes a
number in a sealed artifact. A measured *rejection* is a finding and is quoted
as one. And where the repository already answered a question, its answer is
cited rather than re-derived — several of these were measured properly in
W2–W8 and re-measuring them would be waste.

---

## 11. Current-state matrix

### The causal chain, as actually implemented

```
Personnel + team identity + opponent
    |  personnel: R5 active pool, R6 role prior, R7 depth (candidate only)
    |  opponent : ABSENT except A3G's draw coupling
    v
Game environment ............................ ABSENT
    v
Game state (score, clock, down) ............. ABSENT
    v
Team play volume ............................ PRODUCTION (static draw)
    |  league_mean / coach_prior / ewma, no opponent, no game state
    v
Situational pass/run choice ................. ABSENT
    |  the pass/run split is a drawn LEVEL, not a decision
    v
Participation / routes / rush participation . PARTIAL (pass snaps, no routes)
    v
Targets / carries / red-zone opportunity .... PRODUCTION (simplex allocation)
    v
Opponent-adjusted efficiency ................ ABSENT (no opponent term anywhere)
    v
TD / turnover / sack events ................. PARTIAL (TD2, sacks; no opponent)
    v
Joint player distributions .................. PARTIAL (A3G, C3, SC1, identities)
```

### B1 — Offensive identity and tendencies

| signal | class | evidence |
|---|---|---|
| Neutral-situation pass rate | **EXPERIMENTAL** | measured in W5: split-half **0.532**, Spearman-Brown 0.695, ICC 0.116. A genuinely reliable team trait. Zero occurrences in `nfl/production` or `nfl/product`. |
| Early-down pass rate | **ABSENT** | same measurement family; not consumed |
| Pace / seconds per play | **REJECTED-ADJACENT** | W5: neutral seconds per play split-half 0.410; **plays per game ICC 0.000**, out of sample worse than the league mean; **drives per team-game split-half 0.001**. Recorded REJECTED in `NFL_FEATURE_REGISTRY.md`. |
| Shotgun / under-centre | **ABSENT** | `nflverse.participation` reachable; 12 research files touch it; nothing in production |
| Play action | **ABSENT** (source PARTIAL) | needs FTN charting; `nflverse.ftn.2022/2025` reachable |
| Motion | **DATA_BLOCKED for a decision, PARTIAL for description** | FTN-S2: alignment primitives exist but **one game cannot resolve them**; a ~10-game sample request is justified and small |
| Personnel groupings | **ABSENT** | `personnel_group` occurs nowhere in the repository |
| Red-zone play selection | **PARTIAL** | `team_rz_carries` is a drawn team volume; there is no red-zone pass/run *choice* |
| Goal-to-go behaviour | **REJECTED** | W3: "the goal-line back" adds **+0.5%** over overall carry share; goal-to-go adds **0.0%** |
| Third / fourth down tendencies | **ABSENT** | `third_targets` is a panel column; no down-state model |
| Leading / trailing behaviour | **ABSENT** | see B4 |
| Two-minute offence | **ABSENT** | no clock state exists |
| Coach / coordinator continuity | **PARTIAL, and it is PRODUCTION** | `p4b_volume.priors` builds `coach_prior` from the **head coach's** own prior team-games (≥8, else league mean); it is the selected estimator for `team_dropbacks_part`, `team_carries` and `team_rz_carries`. It is a *level* prior. No coordinator identity, and `GAP-PLAYCALLER` records that a play-caller change moves pass rate discontinuously and that team history lags it by weeks. |

### B2 — Defensive identity

W6 measured all of this properly on 32 defences and 544 team-games. **The
finding that organises the whole category: behaviour is reliable, outcomes are
not.**

| signal | class | reliability @17 games (W6) |
|---|---|--:|
| Cover-3 rate | **EXPERIMENTAL** | **0.878** [0.770, 0.923] |
| Man-coverage rate | **EXPERIMENTAL** | **0.875** [0.807, 0.907]; repeated split-half +0.776 |
| Cover-1 rate | **EXPERIMENTAL** | 0.859 |
| Blitz rate (≥5 rushers) | **EXPERIMENTAL** | 0.810 |
| Pressure rate generated | **EXPERIMENTAL** | 0.693 [0.426, 0.796] |
| Takeaways per play | EXPERIMENTAL | 0.499 |
| Rush EPA/play allowed | weak | 0.475 [0.000, 0.658] |
| Completion rate allowed | weak | 0.429 |
| Explosive rate allowed | weak | 0.315 |
| INT per dropback | **REJECTED** | 0.187 |
| **Pass EPA/play allowed** | **REJECTED** | **0.094** [0.000, 0.341] |
| Explosive pass allowed | **REJECTED** | 0.024 |
| **Sack rate per dropback** | **REJECTED** | **0.000** [0.000, 0.234] — "a sack is definitionally a pressure" |
| Defensive front / box structure | **ABSENT** | `box_count` occurs nowhere |
| Run-defence quality | PROXY | rush EPA allowed, reliability 0.475 |
| Red-zone defence | **ABSENT** | — |
| Opponent adjustment | **EXPERIMENTAL, marginal** | W6 D-7: all-EPA gain p = 0.0033 survives; **pass-EPA p = 0.040 fails Holm**. The write-up itself calls "pass-EPA reliability nearly tripled" its least secure number. |

**Nothing defensive is in production.** Zero occurrences of pressure, blitz,
coverage or box in `nfl/production`.

### B3 — Offence × defence interaction

**ABSENT, completely.** The simulator models neither independent team strengths
nor matchup interactions on the defensive side, because it has no defensive term
at all. Team volume is drawn from the offence's own history and its coach's
history; the opponent enters exactly once, in `A3G`, and even there only as a
**shared draw index** that couples the two teams' volume marginals without
moving either marginal.

None of the four named interactions is modelled: pressure-prone offence ×
pressure-generating defence; mobile QB × aggressive rush; pass-heavy offence ×
coverage tendency; receiving-RB usage × blitz; run tendency × box.

**Receiver-versus-corner is not merely absent, it is measured and refused.**
W6: opposing defence explains **0.66%** of receiver yardage residual, placebo
p = 0.113. `GAP-COVERAGE-MATCHUP` holds it at HOLD. The directive's own caution
("do not recommend receiver-vs-corner modelling unless point-in-time data
supports it") is already the repository's position, on evidence.

### B4 — Game-state dynamics

**ABSENT, and this is the largest structural gap in the engine.**

Zero occurrences of `game_script`, `score_differential` or `win_prob` anywhere
in `nfl/production` or `nfl/product`. No down, no distance, no clock, no
possession. Team volume is a **single static draw per team-game**: the estimator
menu is `league_mean`, `coach_prior`, `ewma`, `prev_season`, `team_empirical`,
`coach_empirical`, and the selected point estimators for 2025 are
`team_off_snaps: league_mean`, `team_dropbacks_part: coach_prior`,
`team_targets: ewma`, `team_carries: coach_prior`, `team_rz_carries:
coach_prior`.

The directive's own example — "the same team may throw 43 times when trailing
and 27 when leading" — is exactly what cannot happen today. The model draws one
dropback count from a marginal distribution and allocates it. The *spread* of
that marginal contains game-script variance implicitly; the *conditioning* does
not exist, so nothing about the specific opponent, spread or expected script
moves it.

**A3G is the one piece of coupling and it is honest about its limits**: it
shares a draw index so game totals are not the sum of independent marginals,
with "marginals unmoved by construction", and its own pre-registered verdict
did **not** clear — it was integrated on corrected clauses in an addendum.

### B5 — Player role architecture

| role | class | evidence |
|---|---|---|
| RB early-down role | **ABSENT** | no down state |
| RB receiving-down role | **PROXY** | the `targets` class simplex includes RBs; no down conditioning |
| Goal-line role | **REJECTED as a free-standing role** | W3: own goal-line share adds +0.5% over overall carry share |
| WR outside / slot | **DATA_BLOCKED (resolvable, cheaply)** | FTN-S2: alignment "varies genuinely within players and produces an effect of the right sign and a plausible size"; one game cannot tell whether it is real; **~10 games would** |
| Possession vs field-stretcher | **ABSENT** | needs target depth; `GAP-ENDZONE-TARGETS` and `GAP-AIRYARDS-YAC` |
| TE route vs blocking | **PROXY, and the proxy is an upper bound** | `GAP-ROUTES`: `s_pass_snaps` is pass-snap participation, an upper bound on route participation, "a player on the field for a dropback may block" |
| QB scramble tendency | **PRODUCTION** | SC1 makes the scramble/carry joint state coherent by permuting the draw index; A1 owns the rush partition including `qb_scramble` |
| QB checkdown / aggressiveness | **ABSENT** | needs target depth |

**One measured result retires a large part of this category.** FTN-S1:
**WR route participation is 0.989.** Routes are a *structural* null for
receivers — there is almost nothing for a route feature to correct. ρ_FTN =
+0.0062 [−0.0705, +0.0916], a CRPS gain of ~0.6% against a placebo floor of
−0.87%. The remaining route question is TEs and RBs, where blocking is real.

### B6 — Conditional substitution

**PROXY, and the proxy is exactly the naive one the directive suspects.**

When a player does not appear in draw *j*, his weight is zeroed and the P4C
simplex renormalises. That is **redistribution in proportion to the surviving
players' existing shares** — no empirical substitution relationship, no notion
that a specific backup inherits a specific role. `layers.targets_carries`
refuses by name (`ALLOCATION_PLAYER_WITHOUT_APPEARANCE`) if a player has no
appearance draw, so the *tie* is sound; what is missing is the *structure*.

The appearance model does carry a `teammate_availability` feature group
(`f_vac_snap`, `f_vac_route`, `f_vac_target`, `f_vac_carry`,
`f_n_teammates_out`), so vacated share informs **whether a player plays**. It
does not inform **how much** he gets once he does.

`GAP-PREGAME-ROLE` records the cost: the participation control's residual sits
in role transitions — R² 0.753 for stable roles against **0.496 / 0.498** for
roles moving up or down, with lag bias −0.027 rising and +0.038 falling.

### B7 — Offensive line / defensive front

| item | class | evidence |
|---|---|---|
| Pressure allowed / generated | **EXPERIMENTAL** | `nflverse.pfr_advstats.pass.2024` REACHABLE; W6 pressure reliability 0.693 |
| Pass protection (player level) | **DATA_BLOCKED** | FTN sample shows `ppro` as a charted role (16 of 156 plays); needs the vendor agreement, which `ROUTE-BB1 §7` found is an **unsigned draft granting no written permitted use** |
| Run blocking | **ABSENT** | `advstats.receiving_broken_tackles` is **100% null**; no run-block source |
| OL injuries | **PARTIAL** | the injury feed covers all positions; the appearance model only runs on skill players, so an OL injury reaches nothing |
| DL / front injuries | **ABSENT** | no defensive model to reach |

The OL is the largest **completely unmodelled unit**: 22,502 of 83,144 panel
rows are OL, they carry depth data at 85.5% coverage, and not one of them
influences a projection.

### B8 — Red-zone / TD opportunity

| item | class | evidence |
|---|---|---|
| Inside-20 carries | **PRODUCTION** | `team_rz_carries` drawn; `rz_carry_share` allocated |
| Inside-10 / inside-5 | **PARTIAL** | `gl_carries` is a panel column; used in research, one production reference |
| End-zone / red-zone targets | **DATA_BLOCKED** | `GAP-ENDZONE-TARGETS`: the available proxy is **line of scrimmage, not target depth — a different quantity**. Marked unavailable in the TD1 pre-registration rather than approximated. TD1 put red-zone allocation at ~13% of TD oracle share. |
| QB rushing opportunity | **PRODUCTION** | A1 partitions `designed QB` and `qb_scramble` |
| Team red-zone volume | **PRODUCTION** | `team_rz_carries`, `coach_prior` |
| Role-specific TD opportunity | **REJECTED as free-standing** | W4: free-standing red-zone target rate partial r = 0.126, and **overall target share predicts next-half red-zone share better than red-zone share predicts itself** |
| Conversion shrinkage | **PARTIAL, and under-characterised** | `GAP-TD-RECOVERABILITY`: TD1 measured conversion at 76.55% receiving / 75.07% rushing of TD oracle share, but **the recoverability ladder and composition test were not run**. Funding conversion modelling on the 75% alone is named as the exact mistake RC1 exists to prevent. |

The directive's instruction — keep opportunity distinct from noisy TD conversion
— is already the architecture, and the two W3/W4 rejections above are what
happens when the distinction is tested.

### B9 — Context and environment

**ABSENT in production, and one part of it is QUARANTINED on purpose.**

| item | class | note |
|---|---|---|
| Home / away / neutral | **PARTIAL** | present in the schedule and the game id; no home-field term in any estimator |
| International travel | **ABSENT** | — |
| Timezone / body clock | **ABSENT** | `timezone` in production is `ZoneInfo` for kickoff parsing, nothing more |
| Rest days | **ABSENT** | `rest_days` occurs nowhere |
| Surface | **ABSENT** | — |
| Roof / stadium | **ABSENT** | — |
| Wind | **QUARANTINED** | `nfl/ingest/allowlist.py`: `temp` and `wind` are POSTHOC. They are **observed conditions, not forecasts** — "a totals model reading them from the archive is reading the weather it is predicting under". A forecast vintage would be a different field, registered separately. |
| Precipitation | **ABSENT** | no source registered |
| Temperature | **QUARANTINED** | as above |
| Altitude | **ABSENT** | — |

The directive says not to assume these are predictive because they are
intuitive. The repository has already acted on that: the weather fields are not
absent through oversight, they are **enforced out at ingest**.

### B10 — Injuries and late information

| does injury affect... | class | evidence |
|---|---|---|
| probability active | **PRODUCTION** | `f_inj_status` (Out/Doubtful/Questionable), `f_inj_practice` (DNP), practice-progression sequences, `f_inj_available` |
| participation if active | **ABSENT** | a designation moves P(appear); it does not move share-given-appearance |
| efficiency if limited | **ABSENT** | no efficiency term reads injury |
| teammate redistribution | **PARTIAL** | vacated share informs P(appear) for teammates, not their share |
| team efficiency / volume | **ABSENT** | team volume never reads the injury report |

So the directive's concern is precise and correct: **it is not a binary flag —
it is richer than binary for one question and absent for the other four.** R7's
calibration confirms the one it does answer is answered well: `Out` predicted
0.0100 against observed 0.0000 (n=855), `Doubtful` 0.0219/0.0063, `Questionable`
0.6523/0.6387.

`GAP-INJURY-VINTAGE` is the standing constraint: the weekly cascade cannot be
reconstructed after the fact (one archive row per player-week; 2025+ dropped
`date_modified`), so this is prospective-only from 2026-09-06.

### B11 — Joint dependence

| dependence | class | evidence |
|---|---|---|
| QB ↔ receiver | **PRODUCTION (C3)** | one passing event: the target budget comes from the throw process and the passer line is credited from the receiving event |
| Competing receivers | **PRODUCTION (structural)** | the P4C simplex: `sum(share) + other == 1` per draw, checked per cell |
| RB rush ↔ QB pass volume | **PARTIAL (A1 + SC1)** | A1 gives the rush-play budget exactly one owner per carry; SC1 permutes the carry draw index so team carries ≥ QB scrambles in every draw |
| Teammate TD competition | **PARTIAL** | receiving TD ≤ receptions per cell; no explicit competition term |
| Opposing-team game environment | **PARTIAL (A3G)** | shared draw index; marginals unmoved; its own verdict did not clear |
| Trailing / leading states | **ABSENT** | no game state |
| Backup usage conditional on starter absence | **PROXY** | proportional renormalisation, per B6 |

Enforced identities (`nfl/production/nonqb/accounting.py`, per draw, FAIL not
clip): share simplex closure, share ≥ 0, targets sum to team targets,
receptions ≤ targets, receiving TD ≤ receptions, receiving yards ≥ 0, and the
load-bearing one, **share == 0 wherever appearance == 0**.

`joint.py` states the open debts explicitly and leaves them **neutral rather
than fitted**: WR1↔RB1 and TE1↔RB1 coupling, and the 2024 carry rank1↔rank2
anomaly. Tuning to those anomalies is forbidden there.

---

## 12. Missing high-value signals

Ranked by the directive's criterion — expected incremental predictive
information × causal importance × evidentiary feasibility — not by
sophistication.

1. **Situational pass/run choice conditioned on game state.** The single
   largest structural gap. It sits high in the causal graph, it is what makes
   the same team throw 43 times or 27, and every downstream player projection
   inherits its variance. `pbp` is reachable for every season; the target
   (dropbacks per game, conditioned) is measurable; nothing is licensed.
2. **Neutral-situation pass rate as a team trait.** Already measured reliable
   (0.532 split-half, 0.695 Spearman-Brown) and already not used. The cheapest
   real signal in the repository.
3. **Role-conditional substitution.** B6's proportional renormalisation is known
   to be inadequate and the cost is quantified (role-transition R² 0.496/0.498
   against 0.753 stable). This is the natural successor to R5/R6/R7 and stays
   inside the opportunity layer.
4. **Defensive behaviour as an opponent term.** Coverage-shell and blitz rates
   are the most reliable defensive quantities anyone has measured here
   (0.810–0.878 at 17 games) and there is no opponent term anywhere in the
   engine to put them in. The value is in *behaviour*, not outcome rates.
5. **Pressure rate, both directions.** 0.693 reliability, `pfr_advstats`
   reachable, and it is the mechanism behind sack and scramble counts the model
   already emits.
6. **WR alignment (slot vs wide).** FTN-S2 found a real-signed, plausible-sized
   effect and named the exact remedy: **~10 games**. Small, bounded, and it is
   the only charting request with a pre-computed sample size.
7. **Injury designation acting on share-given-appearance.** The feed is already
   captured, already parsed, already consumed for one question, and is not
   consumed for the obvious second one.
8. **Target depth / end-zone targets.** High value for TD allocation
   (TD1: ~13% of TD oracle share) but DATA_BLOCKED on a charting source.

---

## 13. Signals we should NOT pursue

Each of these is a **measured** rejection in this repository. They are listed so
they are not re-proposed.

| signal | why not |
|---|---|
| Plays per game as a team trait | split-half 0.220, **shrunk ICC 0.000**, out of sample worse than the league mean (W5) |
| Drives per team-game as a team trait | split-half **0.001**; pace predicts next-half play count at r = −0.099, **wrong sign** (W5) |
| "The goal-line back" | own goal-line share adds **+0.5%** over overall carry share; goal-to-go **0.0%** (W3) |
| Free-standing red-zone target rate | partial r = 0.126; overall target share predicts next-half red-zone share better than red-zone share predicts itself (W4) |
| Defensive sack rate as a team trait | reliability **0.000**; a sack is definitionally a pressure — model pressure instead (W6) |
| Pass EPA allowed as a defensive trait | reliability 0.094 [0.000, 0.341] (W6) |
| Explosive pass allowed | reliability 0.024 (W6) |
| Interception rate as a QB skill | within-season 0.212 [−0.168, +0.530]; YoY intervals all cover zero (W2) |
| Blitz-faced rate as a QB trait | r = 0.020 (W2) |
| Charged drop rate | r = 0.020 WR, 0.008 QB (W4, W2) |
| Fumble-recovery share / forced fumbles | variance ratios 0.98 / 1.03 — chance (W6) |
| **Individual receiver-vs-defender matchup** | opposing defence explains **0.66%** of receiver yardage residual, placebo p = 0.113 (W6) |
| **WR routes run** | route participation is **0.989** — a structural null. ρ_FTN = +0.0062 [−0.0705, +0.0916] (FTN-S1) |
| `participation.ngs_air_yards` | **SOURCE EMPTY** — 0 non-null of 45,919 |
| `advstats.receiving_broken_tackles` | **SOURCE EMPTY** — 100% null |
| Observed `temp` / `wind` from the archive | reading the weather being predicted under; quarantined at ingest |
| `ffopportunity` expected points | ORACLE / NON-DEPLOYABLE — consumes realised opportunity identity. Legitimate as a bound, never as an input, **never as a promotion gate** |

---

## 14. Data blockers

| blocker | what it blocks | state |
|---|---|---|
| **Charting vendor agreement** | pass protection, target depth, motion, personnel groupings, alignment at scale | `ROUTE-BB1 §7`: unsigned draft, no written permitted use, §6.1 licenses only a *Client* under an executed agreement. ML/training rights, retention, derived-output ownership and identifier crosswalk all UNRESOLVED. **Identity is not the blocker** — `pff_id` covers 100% of the WR/TE/RB frame. |
| **2026 participation and snap counts** | the whole P component prospectively | both **404 for 2026** as of 2026-09-08; watch running under RET-001, **not authorized for predictive use** |
| **Historical injury vintages** | as-of injury evidence before 2026-09-06 | archive keeps one row per player-week; 2025+ dropped `date_modified`. **Cannot be reconstructed at any price.** |
| **Historical weekly-roster `status`** | eligibility-based population repairs before 2026 | OUT-002, still open — **partly relieved** by the depth-chart union R7 built (OUT-004) |
| **Depth-chart vendor comparability** | equating a 2024 rank with a 2026 one | the two schemas do not overlap in time. OUT-005. |
| **End-zone target depth** | role-specific TD opportunity | no free source carries it; the available proxy is line of scrimmage, a different quantity |
| **Official NFL injury / inactives endpoints** | a second, authoritative status source | `LOCAL_PROXY_CONNECT_403` from this container (`NFL_DATA_AVAILABILITY.json`) |

**Not blocked, contrary to the registry's assumption:** `nflverse` releases are
reachable from this container — 25 of 33 probe targets PASS, including `pbp`,
`participation`, `snap_counts`, `pfr_advstats`, `ftn` and `depth_charts` for
every season. OUT-003 recorded this and R7 used it.

---

## 15. Ranked research roadmap

Scored on the directive's product. Upside = expected incremental predictive
information. Causal = position in the graph (upstream beats downstream).
Feasible = data available, historically validatable, low leakage risk.

| # | track | upside | causal | feasible | leakage risk | complexity | already addressed? |
|---|---|---|---|---|---|---|---|
| 1 | **Game-state-conditioned team volume** | high | **highest** | high (pbp all seasons) | low — pbp state is in-play, so the *conditioning* must be on pregame expectations, not realised state | high | no |
| 2 | **Neutral pass rate as a team/coach trait** | medium-high | high | **highest** | low | **low** | measured (W5), never deployed |
| 3 | **Role-conditional substitution** | medium-high | high | medium (needs the R7 frame) | low | medium | diagnosed (GAP-PREGAME-ROLE), not built |
| 4 | **Defensive behaviour as an opponent term** | medium | high | high | low | medium | measured (W6), never deployed |
| 5 | **Pressure both directions → sacks/scrambles** | medium | medium | high | low | medium | measured (W6) |
| 6 | **Injury designation on share-given-appearance** | medium | medium | high (feed already captured) | **medium** — needs the vintage discipline R7 used | low | no |
| 7 | **Blend depth information with participation history** | medium | medium | **highest** — both halves exist | low | low | this mission's own finding |
| 8 | WR alignment | low-medium | medium | blocked on ~10 charted games | low | medium | FTN-S2, sized |
| 9 | Target depth / end-zone targets | medium | medium | **blocked** | unknown | medium | GAP-ENDZONE-TARGETS |
| 10 | TD conversion recoverability | low-medium | low | high | low | low | GAP-TD-RECOVERABILITY, CHEAP_PROBE |
| 11 | Environment (rest, travel, surface, roof) | **unknown, possibly zero** | low | high for schedule fields | low | low | no — and it must be tested, not assumed |
| 12 | OL / run blocking | unknown | medium | blocked | unknown | high | no |

**The ranking's shape is the point.** Foundational primitives — what the team
does, who is on the field, who inherits work — sit above everything ornate.
The two most sophisticated-sounding items on the list (receiver-vs-corner,
routes) are not on it at all, because they were measured and refused.

---

## 16. The next three research tracks

Audit only. Each is stated as a pre-registration would state it, so the
hypothesis is fixed before the data is looked at again.

### TRACK 1 — Game-state-conditioned team volume

**Hypothesis (H1).** Team dropbacks in a game-week are predictable beyond the
`coach_prior` baseline from **pregame-knowable** expectations of game script,
and the gain is concentrated in games whose expected script is asymmetric.

**Why first.** It is the highest node in the causal chain that is currently a
constant. Every player projection is a share of it, so its unconditional
variance is inherited by all of them, and the SD-of-conditional-means problem
that dogged the sibling MLB project is the same problem in a different sport.

**The leakage trap, stated in advance.** Realised score differential, realised
win probability and `vegas_wp` are **outcome and market columns, quarantined at
ingest**. The predictor must be built from pregame quantities only. That
constraint is what makes this a real experiment rather than a fit: if the only
thing that predicts script is the market line, the honest finding is that we
have no pregame script signal of our own, and that is a publishable answer.

**Design.** Forward-chained by season, 2020–2024 fit, 2025 held out. Baseline is
the frozen P4B estimator selection. Candidate adds one pregame script feature
group. Metrics: CRPS on team dropbacks and team carries, plus the SD of
conditional means against the SD of realised values. Clustering by game and by
date, blocked bootstrap, predeclared equivalence margin.

**Falsification.** If the SD ratio of conditional means does not rise, or CRPS
does not improve on the held-out season with a blocked interval excluding zero,
H1 is rejected and recorded as rejected.

### TRACK 2 — Neutral pass rate as a deployable team trait

**Hypothesis (H2).** A shrunk neutral-situation early-down pass rate, estimated
from strictly prior games, improves the team pass/run split beyond
`coach_prior`, and its advantage persists after conditioning on the same team's
overall volume.

**Why second.** It is nearly free. The quantity is measured
(split-half 0.532, Spearman-Brown 0.695, ICC 0.116), the source is reachable for
every season, there is no licensing question, and it is currently used nowhere.
It is also the cheapest possible test of whether the volume layer can be
improved at all — if a trait this reliable does not help, Track 1's more
elaborate conditioning is much less likely to.

**The trap.** W5 found *plays per game* has ICC 0.000 and *drives per game*
0.001. Pass **rate** being reliable while play **count** is not means the trait
predicts the split, not the volume, and the experiment must not quietly test the
second while claiming the first.

**Design.** Same forward-chained frame. The estimand is `team_dropbacks_part /
team_off_snaps`. Shrinkage `n/(n+k)` with `k` estimated from within/between team
variance, never chosen. Baseline `coach_prior`; candidate adds the shrunk
neutral rate. Metrics: CRPS and calibration slope on the split, and the
downstream effect on player target projections measured separately so a volume
gain is not credited to allocation.

**Falsification.** No improvement on held-out seasons with blocked intervals
excluding zero → rejected, and recorded in the feature registry as such.

### TRACK 3 — Role-conditional substitution

**Hypothesis (H3).** When a player is absent, his opportunity does **not**
redistribute in proportion to the surviving players' overall shares; it
redistributes preferentially to players occupying an adjacent point-in-time
role, and modelling that adjacency improves projections for the players who
inherit.

**Why third.** It is the direct successor to R5, R6 and R7 and stays inside the
opportunity layer, which is where the directive says the value is. It also has
the cost already quantified: role-transition R² is 0.496/0.498 against 0.753 for
stable roles, with lag bias −0.027 rising and +0.038 falling.

**Why it is newly feasible.** The R7 union frame is the first population in this
project that contains players who were *available and did not play*. Naive
next-man-up cannot be tested against a frame that only holds people who played.

**Design.** Identify absence events historically on the union frame. For each,
measure the realised redistribution of targets and carries by point-in-time
depth adjacency, against the proportional-renormalisation counterfactual the
engine currently implements. Predeclare adjacency from the depth chart, not from
realised outcomes. Cluster by team-game — the players in one game are not
independent observations, and this is exactly the setting where that bites.

**Falsification.** If realised redistribution is statistically indistinguishable
from proportional renormalisation, the current behaviour is **vindicated**, and
that is a valuable result: it closes `GAP-PREGAME-ROLE`'s substitution half and
removes an assumed defect from the register.

---

## Hard principles, checked

| principle | state |
|---|---|
| Opportunity before efficiency | held — the whole ranking puts opportunity first, and every efficiency track is below it |
| No direct fantasy-point target | held — no track proposes one |
| Coherent team totals | held — Track 1 changes the volume *distribution*, never the accounting identities |
| Actual outcomes are truth | held — every falsification condition is against realised outcomes |
| Sportsbook is comparator only | held — and Track 1 names the market explicitly as the thing it must **not** use as a predictor |
| Point-in-time legality | held — every track's features are pregame; Track 3's adjacency comes from the point-in-time chart |
| Immutable vintages | held — nothing here changes capture |
| No unsupported feature synthesis | held — §13 lists what was measured and refused |
| No bankroll / wager constraints in architecture | held — none appears |
| **No RB/WR/TE rushing-yards shortcut** | held — `RUSHING_CONVERSION_CONTROL_UNDEFINED` remains open; carries × YPC appears nowhere and is named in `nfl/product/metrics.py` as the substitute that is refused |
