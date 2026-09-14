# D5 — ZERO-MASS AUDIT

**Diagnostics only.** No estimator was changed, no parameter was tuned, no
floor was added, nothing was promoted, nothing was committed. Everything below
is a measurement. Candidate B was measured; it remains SHADOW ONLY and frozen at
`32ea294a98145b24…`.

Written 2026-09-14 at HEAD `afefd39`, branch
`claude/nfl-greenfield-architecture-stsxmk`, `python3.12`. All artifacts under
`nfl/research/v2/d5/`.

---

## 0. THE ANSWER, FIRST

**The 41% is NOT an isolated pathology, and it is NOT the appearance model.**

It is the systematic, reproducible week-1 behaviour of a *different* layer —
`qb3_lib.allocate`, reached through `qb_allocation.py` — and it is produced by a
single identified mechanism that has nothing to do with `layers.appearance`.

**Two findings, and they point in opposite directions.**

1. **QB room path — excessive zero mass, systematic, and contradicted by the
   record.** Across 2021-2024 the depth-chart QB1 took zero dropbacks in
   **0 of 128 week-1 team-games**. The allocation model assigns that same
   population a **mean zero mass of 0.197**, a p90 of 0.399 and a maximum of
   0.465. Tonight's 0.412 is the 96th percentile of a distribution whose
   realised rate is exactly zero. **Fifty-four percent of week-1 rooms
   (69/128) fall in the cells that generate it.** This is systematic.

2. **Non-QB appearance path — no such defect on primary players, and the error
   runs the other way.** Pooled over RB1/WR1/TE1, 2021-2024, the incumbent's
   mean zero mass minus the realised zero-appearance rate is
   **−0.0026, game-clustered 95% CI [−0.0076, +0.0022]** in-season and
   **−0.0117 [−0.0423, +0.0140]** across the season boundary. Both are
   indistinguishable from zero and both lean *negative* — the model assigns
   slightly **too little** zero mass to primaries, not too much. Where the
   incumbent is badly wrong on this path it is wrong by **under**-assigning:
   cold-start rows get a mean zero mass of **0.0212 [0.0114, 0.0324]** against
   a realised zero-appearance rate of **0.4885 [0.4364, 0.5476]**.

**Consequence for V2 urgency.** The urgent participation work is the **QB room
path**, not the non-QB appearance layer. Nothing in the non-QB appearance
layer's treatment of primary players produced tonight's number or resembles it.
The incumbent's confirmed train/serve leak, measured by role class below, moves
primary-role zero mass by **0.0000** — it is a backup-and-fringe defect, and it
is also not what produced tonight's number.

---

## 1. WHAT WAS MEASURED, AND ON WHAT

### Chronology

Lawful historical play-by-play only: `pbp_2021`…`pbp_2024`, REG season,
grouped by `(game_id, posteam)`, kneels excluded from rushing via
`qb_kneel != '1'`.

| file | sha256 (16) | retrieved |
|---|---|---|
| `pbp_2021.e8743a568f99667a.csv.gz` | `e8743a568f99667a` | 2026-09-13T22:00:14Z |
| `pbp_2022.0c69a71eb3949895.csv.gz` | `0c69a71eb3949895` | 2026-09-13T22:00:20Z |
| `pbp_2023.4649804ee0f0a40b.csv.gz` | `4649804ee0f0a40b` | 2026-09-13T22:00:26Z |
| `pbp_2024.23370d5d10f8104d.csv.gz` | `23370d5d10f8104d` | 2026-09-13T22:00:32Z |

198,513 plays → **2,174 team-games**, 21,495 player-team-games with at least one
opportunity. **`pbp_2026` was never opened and never globbed.** Every glob in
this workstream is literal `pbp_202[1-4]`.

### Realised opportunity, defined per position

| position | opportunity | source column |
|---|---|---|
| QB | dropbacks | `passer_player_id` where `qb_dropback == '1'` |
| RB | carries | `rusher_player_id` where `qb_kneel != '1'` |
| WR / TE | targets | `receiver_player_id` |

Two realised quantities are kept apart throughout and must not be merged:
**zero appearance** (took no offensive snap) and **zero opportunity** (appeared
but recorded no carry/target/dropback). They differ a lot — a usage-tier-1 TE
has a realised zero-appearance rate of 0.0869 and a realised zero-target rate of
0.1605.

### Model-assigned zero mass

Two arms, forward-chained, each fitted strictly on earlier seasons and scored on
the held-out season:

- **`INCUMBENT_KNOWN_DEFECTIVE`** — `appearance_r8`,
  `appearance-r8-reliability-weighted-1`.
- **`CANDIDATE_B_LIVE_EVALUATION`** — `appearance_b`,
  `appearance-b-union-candidate-universe-1`, frozen. Measured, never promoted.

Both are scored on the **same rows** on **basis U** (`union_frame()`, V1 block
presence 1.0000 on all 59,784 rows). Basis U is the serve shape: at serve every
player carries a V1 block. The incumbent was additionally scored on **basis P**
(its native `enriched_frame()`, V1 presence 53,626 / 6,158) so the leak can be
located rather than assumed. Scored population after joining to the pbp
team-games: **39,533 player-team-games, 2021-2024, 2,174 team-games**, all from
the `nflverse_weekly` depth vendor.

The QB **allocation** path is a separate replay: `qb3_lib.build_frame` →
`fit(frame, Y)` → `allocate(...)`, forward-chained for Y ∈ {2021…2024}, 2,000
draws per team-game, 3,851 QB rows over 1,629 team-games.

### Role class — two definitions, both reported, neither clean

- **`usage tier`** (primary lens): point-in-time rank within
  (season, week, team, position) by the player's trailing mean snap share over
  his last four *prior* frame rows. No row sees its own game. This is the R6
  construction.
- **`chart rank`** (robustness lens): the depth rank the model actually
  consumes — `depth_vintage.weekly` → the `rank` feature.

**Disclosure the coordinator asked for.** I did **not** use
`role_prior.assign_tiers`; my usage tier is built here from the union frame. It
nonetheless carries the same structural bias D4 names: at a season boundary a
returning veteran's trailing snap share comes from the *previous* season, so a
player with no history ranks last by construction. Every week-1 and
boundary-crossing result below is therefore reported under **both** definitions,
and the conclusions do not depend on which one is used.

---

## 2. THE QB PATH — WHERE 0.412 ACTUALLY COMES FROM

`qb_allocation.py` never calls `layers.appearance`. Tonight's quarterback
numbers come from `qb3_lib.allocate` and from nothing else.

### 2.1 Exact reproduction

Replaying `qb3_lib.allocate` with the production room, `par = fit(frame, 2026)`,
`ordinal = 202601`, `seed = 20260908`, `m = 1000`, against the sealed draws in
`.../f91342d6787a66a1/player_draws.npz`:

| player | team | cell | reconstructed P(share = 0) | sealed board P(db = 0) |
|---|---|---|--:|--:|
| Patrick Mahomes | KC | (1, 0) | **0.4120** | **0.4120** |
| Justin Fields | KC | (2, 0) | 0.4560 | 0.4560 |
| (KC QB3) | KC | (3, 0) | 0.3990 | 0.4190 |
| Bo Nix | DEN | (1, 1) | 0.0500 | 0.0480 |
| Jarrett Stidham | DEN | (2, 0) | 0.7980 | 0.8030 |
| Sam Ehlinger | DEN | (3, 0) | 0.7610 | 0.7910 |

The rank-1 rows reproduce **exactly**. The small residuals on rank 2/3 are the
integerisation of a share into a dropback count. The brief's 0.413 is the run
record's 0.412 rounded; the sealed value is 0.4120.

### 2.2 The mechanism, named

`qb3_lib.allocate` draws the primary passer's identity, then resamples **the
drawn primary's share from his cell's UNCONDITIONAL empirical pool** — a pool
that includes every depth-charted quarterback in that cell who took zero
dropbacks.

But by construction of `primary_of` (which requires `db >= 1`):

> **`P(share = 0 | is the game's primary passer) = 0.0000` in every cell.**

Measured, `fit(frame, 2026)`:

| cell (rank, was_prev_primary) | n | `p_primary` | fraction of share pool **exactly 0** | fraction exactly 1 | P(share = 0 \| is primary) |
|---|--:|--:|--:|--:|--:|
| (1, 1) | 2,349 | 0.9046 | **0.0736** | 0.7765 | **0.0000** |
| (1, 0) | 321 | 0.4922 | **0.4735** | 0.4424 | **0.0000** |
| ('2+', 1) | 240 | 0.6167 | 0.3458 | 0.5083 | **0.0000** |
| (2, 0) | 2,436 | 0.0686 | 0.8120 | 0.0435 | **0.0000** |
| (3, 0) | 1,100 | 0.0282 | 0.9318 | 0.0173 | **0.0000** |

So the "did not play" event is counted **twice**: once in the categorical draw
of `who`, and again inside the share pool the winner then resamples from.

**Tonight, arithmetically:**

- Mahomes is cell (1, 0) — depth rank 1, **not** the previous primary.
  `previous_primary_detail(2026, 1)['KC']` → `00-0037324`, ordinal **202518**,
  and that player is **not in tonight's KC room** {Mahomes 1, Fields 2, QB3 3}.
  KC's configuration is **`NO_PREV_PRIMARY_IN_ROOM`**.
- P(Mahomes is drawn primary) = 0.8357.
- P(his cell's pool draws exactly 0) = 0.4735.
- 0.8357 × 0.4735 = **0.3957**, plus the non-primary path (he is not primary and
  the man who is takes share 1.0) → **0.412**.
- Nix is cell (1, 1) because Nix *was* the 2025 week-18 primary. DEN is
  **`AGREE`**. 0.9034 × 0.0736 = 0.0665 → **0.048**.

**The entire KC/DEN asymmetry is one binary feature: whether the chart's QB1 is
also the previous primary.** It is not eligibility, not injury, not the
appearance model.

### 2.3 Is it systematic? Yes, and the record contradicts it

Depth-chart rank-1 quarterbacks, **week 1 only**, 2021-2024, forward-chained:

| configuration | n team-games | model zero mass: mean | p90 | max | frac ≥ 0.41 | **realised zero dropbacks** |
|---|--:|--:|--:|--:|--:|--:|
| AGREE | 59 | 0.0718 | 0.082 | 0.092 | 0.000 | **0 / 59** |
| DISAGREE | 21 | 0.3687 | 0.447 | 0.465 | 0.333 | **0 / 21** |
| NO_PREV_PRIMARY_IN_ROOM | 48 | 0.2766 | 0.400 | 0.428 | 0.062 | **0 / 48** |
| **all week-1 rank-1 QBs** | **128** | **0.1973** | 0.399 | 0.465 | 0.078 | **0 / 128** |

Distribution, not just the mean: p50 0.087, p75 0.354, p90 0.399, p99 0.455,
max 0.465. **39.8% of week-1 chart QB1s carry ≥ 0.25 zero mass and 7.8% carry
≥ 0.41.** The realised rate is 0 of 128; the rule-of-three 95% upper bound on a
0/128 rate is **0.0234**.

**Tonight is the ordinary case, not the outlier.** 69 of 128 week-1 rooms
(53.9%) were DISAGREE or NO_PREV — the two cells that generate this. Tonight
both clubs cross the season boundary; KC lands in the bad cell and DEN does not,
which is why one club shows it and the other does not.

### 2.4 The same cell is mis-specified in the opposite direction in-season

Rank-1 quarterbacks, **weeks 2-18**, 2021-2024:

| configuration | n | model mean zero | **realised zero** | game-clustered 95% CI |
|---|--:|--:|--:|---|
| AGREE | 1,833 | 0.0677 | 0.0747 | [0.0633, 0.0878] |
| DISAGREE | 184 | 0.3808 | **0.7174** | [0.6575, 0.7772] |
| NO_PREV_PRIMARY_IN_ROOM | 13 | 0.2037 | 0.6154 | [0.3077, 0.8462] |

In-season, "the chart says QB1 but he was not the last primary" usually means an
injured or benched starter still listed at rank 1 — realised zero 0.717 against
a model 0.381, a **−0.34 under**-assignment. In week 1 the identical cell means
"a club changed starters over the offseason, or rested its starter in week 18" —
realised zero 0.000 against a model 0.369, a **+0.37 over**-assignment.

**One cell, two populations, opposite errors, and the season boundary is the
switch.** This is exactly the condition `qb_allocation.qb3_configuration`
already flags as `week1_specification_defect` /
`QB3_WEEK1_SEASON_BOUNDARY`. What this audit adds is the sign, the size and the
realised denominator: the flag is on tonight's board and it is on the right row.

### 2.5 Named outliers — QB path

The twenty largest model zero masses on rank-1 QBs, 2022-2024, are **all**
`DISAGREE`. Eighteen of twenty realised zero dropbacks, which is why the
in-season aggregate looks under-assigned. The two that did not are the
instructive ones, and both are **season openers**:

| game | player | cfg | opener | model P(zero) | realised dropbacks |
|---|---|---|---|--:|--:|
| 2024 wk1 LV | Gardner Minshew | DISAGREE | **yes** | 0.465 | **37** |
| 2024 wk1 CIN | Joe Burrow | DISAGREE | **yes** | 0.458 | **32** |
| 2024 wk12 CAR | Andy Dalton | DISAGREE | no | 0.484 | 0 |
| 2024 wk3 GB | Jordan Love | DISAGREE | no | 0.476 | 0 |
| 2024 wk11 JAX | Trevor Lawrence | DISAGREE | no | 0.472 | 0 |
| 2024 wk11 DAL | Dak Prescott | DISAGREE | no | 0.469 | 0 |

**Joe Burrow, 2024 week 1, carried a 0.458 probability of taking zero
dropbacks, and took 32.** That is the closest historical analogue to tonight's
Mahomes row, and it is the second-best evidence in this report that the number
is a model artefact rather than a football statement. The best evidence is
0 of 128.

---

## 3. THE NON-QB APPEARANCE PATH

Appearance is drawn as an independent per-player Bernoulli
(`layers.py:222`), so a player's zero mass is `1 − p_appear` at that layer.
For tonight's KC RB1 that is essentially the whole story: Kenneth Walker's
incumbent appearance zero mass is **0.1653** and his sealed
`P(carries = 0)` is **0.1500** — a 1.3 Monte-Carlo-SE difference at m = 1000.
Conditional on appearing, a lead back essentially always gets a carry. So the
non-QB comparison below is `1 − p_appear` against realised outcomes, and it is
the right comparison.

### 3.1 Distributions by role class — usage tier, 2021-2024, basis U

| class | n | games | realised zero-**opp** | realised zero-**app** | incumbent zero mass: mean | p50 | p90 | p99 | max | frac ≥ 0.41 | B mean |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| QB1 | 2,174 | 1,087 | 0.1771 | 0.1734 | 0.1705 | 0.036 | 0.683 | 0.999 | 1.000 | 0.155 | 0.1792 |
| QB2 | 2,166 | 1,087 | 0.7613 | 0.7170 | 0.5194 | 0.531 | 0.887 | 0.998 | 1.000 | 0.641 | 0.7113 |
| QB3+ | 1,438 | 863 | 0.8595 | 0.8442 | 0.4239 | 0.349 | 0.928 | 0.998 | 1.000 | 0.427 | 0.8037 |
| **RB1** | 2,174 | 1,087 | 0.1495 | 0.1145 | **0.1166** | 0.036 | 0.290 | 0.995 | 1.000 | 0.085 | 0.1164 |
| RB2 | 2,174 | 1,087 | 0.3243 | 0.1877 | 0.2100 | 0.100 | 0.689 | 0.998 | 1.000 | 0.152 | 0.2127 |
| RB3 | 2,157 | 1,087 | 0.5647 | 0.3792 | 0.3484 | 0.232 | 0.833 | 0.999 | 1.000 | 0.339 | 0.3745 |
| RB4+ | 3,371 | 1,042 | 0.7143 | 0.5972 | 0.4584 | 0.406 | 0.900 | 0.998 | 1.000 | 0.496 | 0.5755 |
| **WR1** | 2,174 | 1,087 | 0.0892 | 0.0731 | **0.0663** | 0.016 | 0.086 | 0.987 | 0.999 | 0.047 | 0.0652 |
| WR2 | 2,174 | 1,087 | 0.1486 | 0.1191 | 0.1233 | 0.029 | 0.353 | 0.997 | 1.000 | 0.094 | 0.1209 |
| WR3 | 2,174 | 1,087 | 0.2548 | 0.1776 | 0.1907 | 0.066 | 0.670 | 0.998 | 1.000 | 0.146 | 0.1855 |
| WR4+ | 8,381 | 1,087 | 0.6413 | 0.4655 | 0.4171 | 0.323 | 0.898 | 0.999 | 1.000 | 0.434 | 0.4651 |
| **TE1** | 2,174 | 1,087 | 0.1605 | 0.0869 | **0.0825** | 0.021 | 0.128 | 0.995 | 1.000 | 0.058 | 0.0798 |
| TE2 | 2,174 | 1,087 | 0.4232 | 0.1564 | 0.1694 | 0.065 | 0.527 | 0.996 | 1.000 | 0.131 | 0.1655 |
| TE3+ | 4,235 | 1,087 | 0.7207 | 0.4519 | 0.3799 | 0.255 | 0.884 | 0.998 | 1.000 | 0.384 | 0.4436 |
| **QB_no_prior** | 52 | 46 | 0.7692 | 0.7115 | **0.0103** | 0.007 | 0.013 | 0.086 | 0.159 | 0.000 | 0.5930 |
| **RB_no_prior** | 108 | 69 | 0.6019 | 0.4907 | **0.0039** | 0.003 | 0.006 | 0.046 | 0.053 | 0.000 | 0.3295 |
| **WR_no_prior** | 150 | 76 | 0.5400 | 0.4267 | **0.0362** | 0.005 | 0.006 | 0.869 | 0.870 | 0.040 | 0.3718 |
| **TE_no_prior** | 83 | 56 | 0.8434 | 0.4578 | **0.0233** | 0.003 | 0.006 | 0.807 | 0.858 | 0.024 | 0.3565 |

The tail the brief asked about exists — p99 ≈ 0.99 and max ≈ 1.00 in **every**
class including WR1, RB1 and TE1 — and **6.30%** of tier-1 non-QB rows (411 of
6,522) carry ≥ 0.41. The next section is the test of whether that tail is a
defect.

### 3.2 It is not a defect: the high zero mass is earned

Reliability of the incumbent's zero mass on **primary-role non-QB rows**
(usage tier 1, n = 8,696 incl. QB1, 1,087 games):

| model zero mass bucket | n | games | mean model | **realised zero-app** | realised zero-opp |
|---|--:|--:|--:|--:|--:|
| [0.00, 0.05) | 6,323 | 1,087 | 0.0218 | 0.0160 | 0.0452 |
| [0.05, 0.15) | 1,229 | 767 | 0.0809 | 0.0928 | 0.1538 |
| [0.15, 0.25) | 227 | 205 | 0.1911 | **0.2863** | 0.3348 |
| [0.25, 0.41) | 170 | 158 | 0.3201 | **0.3941** | 0.4059 |
| [0.41, 0.60) | 148 | 137 | 0.5141 | 0.5000 | 0.5270 |
| [0.60, 0.85) | 170 | 152 | 0.7147 | 0.7529 | 0.7647 |
| [0.85, 1.01) | 429 | 351 | 0.9664 | 0.9907 | 0.9907 |

**When the incumbent says 41-60% zero on a primary, it happens 50.0% of the
time. When it says ≥85%, it happens 99.1% of the time.** The only visible
mis-calibration is in the **middle** buckets, where realised exceeds model —
i.e. the model is under-assigning, not over-assigning.

Restricting to the 411 non-QB tier-1 rows at ≥ 0.41:

| subgroup | n | games | mean model zero | **realised zero-app** | game-clustered 95% CI |
|---|--:|--:|--:|--:|---|
| with an Out/Doubtful/Questionable designation | 264 | 240 | 0.9156 | 0.9318 | [0.8985, 0.9615] |
| with **no** injury designation at all | 147 | 115 | 0.7168 | **0.8299** | [0.766, 0.8903] |

Even the undesignated high-zero-mass primaries genuinely did not appear 83% of
the time. **There is no population of "primary players wrongly assigned large
zero mass" in the non-QB appearance layer.**

### 3.3 Named outliers — non-QB path

The largest incumbent zero masses on tier-1 non-QB rows, and what happened:

| game | player | class | zero mass | (B) | injury | appeared | opportunity |
|---|---|---|--:|--:|---|--:|--:|
| 2021 wk3 LV | Josh Jacobs | RB1 | 1.000 | 1.000 | Doubtful | 0 | 0 |
| 2023 wk17 IND | Zack Moss | RB1 | 1.000 | 1.000 | Out | 0 | 0 |
| 2021 wk7 NYG | Saquon Barkley | RB1 | 1.000 | 1.000 | Out | 0 | 0 |
| 2021 wk2 NYG | Evan Engram | TE1 | 1.000 | 1.000 | Out | 0 | 0 |
| 2021 wk5 TB | Rob Gronkowski | TE1 | 0.999 | 0.999 | Out | 0 | 0 |
| 2021 wk17 NYJ | Jamison Crowder | WR1 | 0.999 | 0.998 | Doubtful | 0 | 0 |
| 2021 wk11 NO | Alvin Kamara | RB1 | 0.999 | 0.999 | Out | 0 | 0 |
| 2024 wk13 DAL | Jake Ferguson | TE1 | 0.999 | 0.998 | Out | 0 | 0 |

**Every one of the top twenty was right.** There is no Burrow-equivalent here.

The interesting outliers on this path are the **opposite** kind — primaries the
incumbent was most over-confident about who then produced nothing:

| game | player | class | zero mass | n_prior | appeared | opportunity |
|---|---|---|--:|--:|--:|--:|
| 2021 wk11 DAL | Amari Cooper | WR1 | **0.002** | 25 | 0 | 0 |
| 2024 wk8 TB | Chris Godwin | WR1 | 0.007 | 74 | 0 | 0 |
| 2023 wk18 KC | Travis Kelce | TE1 | 0.007 | 66 | 0 | 0 |
| 2023 wk13 TB | Cade Otton | TE1 | 0.007 | 28 | 1 | 0 |
| 2021 wk14 LA | Tyler Higbee | TE1 | 0.008 | 28 | 0 | 0 |

### 3.4 Boundary stratification (coordinator's request / D4)

D4's inversion replicates on this frame:

| `prev_appeared` | stratum | n | realised appearance rate | incumbent mean `p_appear` | B mean |
|---|---|--:|--:|--:|--:|
| 0 | in-season | 12,550 | 0.3045 | 0.4540 | 0.2998 |
| 0 | **CROSSED** | 882 | **0.5340** | 0.6677 | 0.5244 |
| 1 | in-season | 24,173 | 0.8314 | 0.8354 | 0.8346 |
| 1 | **CROSSED** | 1,535 | **0.6319** | 0.6974 | 0.6987 |

The sign flip is real and D4's direction is confirmed. **But it does not create
excess zero mass on primaries.** Pooled, with game-clustered CIs:

| population | stratum | n | games | model | realised zero-app | **gap** | 95% CI |
|---|---|--:|--:|--:|--:|--:|---|
| RB1/WR1/TE1 | in-season | 6,195 | 1,057 | 0.0882 | 0.0909 | **−0.0026** | [−0.0076, +0.0022] |
| RB1/WR1/TE1 | **CROSSED** | 327 | 64 | 0.0923 | 0.1040 | **−0.0117** | [−0.0423, +0.0140] |
| QB1 (appearance path) | in-season | 2,062 | 1,038 | 0.1689 | 0.1673 | +0.0016 | [−0.0097, +0.0120] |
| QB1 (appearance path) | **CROSSED** | 112 | 63 | 0.2007 | 0.2857 | **−0.0851** | [−0.1447, −0.0292] |

**Both boundary gaps are negative.** Where the boundary bites in the appearance
path — QB1 crossed — the incumbent assigns **too little** zero mass, by 8.5
points with an interval excluding zero. D4's inversion therefore predicts
*under*-assignment at the boundary, which is what is measured. It cannot explain
tonight's 0.412, and I am not offering it as an explanation for the QB number.

**Robustness under the chart-rank definition** (so the conclusion does not rest
on my usage tier):

| class | stratum | n | realised zero-app | model | gap | 95% CI | frac ≥ 0.41 |
|---|---|--:|--:|--:|--:|---|--:|
| RB1 | in-season | 2,055 | 0.1805 | 0.1671 | −0.0134 | [−0.0276, +0.0002] | 0.110 |
| RB1 | CROSSED | 118 | 0.1356 | 0.0462 | −0.0894 | [−0.1535, −0.0310] | **0.000** |
| WR1 | in-season | 2,067 | 0.2042 | 0.1704 | −0.0337 | [−0.0491, −0.0190] | 0.107 |
| WR1 | CROSSED | 109 | 0.1101 | 0.0527 | −0.0573 | [−0.1136, −0.0064] | **0.009** |
| TE1 | in-season | 2,050 | 0.1000 | 0.1023 | +0.0023 | [−0.0066, +0.0114] | 0.068 |
| TE1 | CROSSED | 124 | 0.0323 | 0.0324 | +0.0001 | [−0.0281, +0.0216] | **0.008** |

Under either role definition, **at the season boundary the non-QB appearance
layer assigns essentially no high zero mass to primaries** — 0.0% to 0.9% of
rows at ≥ 0.41 — and its error is under-assignment. Tonight's 0.412 has no
non-QB analogue.

### 3.5 The cold-start defect — the opposite error, and it is on tonight's board

Rows with **no prior frame history at all**, 2021-2024:

| | n | games | value | 95% CI (game-clustered) |
|---|--:|--:|--:|---|
| incumbent mean zero mass | 393 | 117 | **0.0212** | [0.0114, 0.0324] |
| Candidate B mean zero mass | 393 | 117 | 0.3862 | [0.3619, 0.4119] |
| **realised zero-appearance** | 393 | 117 | **0.4885** | [0.4364, 0.5476] |
| realised zero-opportunity | 393 | 117 | 0.6514 | — |

A 46-point under-assignment with a non-overlapping interval. This is R6's
survivorship finding, now with a denominator. **It is live on tonight's card:**

| tonight, KC | pos | chart rank | n_prior | incumbent zero mass | Candidate B |
|---|---|--:|--:|--:|--:|
| `00-0041013` | RB | 8 | **0** | **0.0092** | 0.5725 |
| `00-0040890` | WR | 14 | **0** | **0.0091** | 0.5623 |
| `00-0040081` | TE | 13 | 17 (17 carried absences) | **0.0030** | 0.5248 |

Tonight the incumbent's largest non-QB zero mass is **0.3647** (Jared Wiley, TE
rank 10). Nothing on the non-QB side of tonight's board is above 0.41. The
non-QB defect on this card is three players the model is 99%+ certain will play
when it has never seen one of them take a snap.

### 3.6 Where the confirmed train/serve leak actually lands

Incumbent scored on basis P versus basis U, same rows, same coefficients:

| class | n | basis P mean zero | basis U mean zero | difference | rows with V1 absent |
|---|--:|--:|--:|--:|--:|
| RB1 | 2,174 | 0.1165 | 0.1166 | **0.0000** | **0** |
| WR1 | 2,174 | 0.0662 | 0.0663 | **0.0000** | **0** |
| TE1 | 2,174 | 0.0825 | 0.0825 | **0.0000** | **0** |
| QB1 | 2,174 | 0.1695 | 0.1705 | +0.0011 | 1 |
| RB2 | 2,174 | 0.2100 | 0.2100 | −0.0000 | 2 |
| TE2 | 2,174 | 0.1696 | 0.1694 | −0.0002 | 2 |
| WR2 | 2,174 | 0.1232 | 0.1233 | +0.0001 | 0 |
| **QB2** | 2,166 | 0.6992 | 0.5194 | **−0.1799** | **566** |

**The leak is a backup-and-fringe defect.** Every primary-role row already
carries a V1 block, so basis makes no difference to them at all. The leak is
severe exactly where the frame's depth-added rows live — backup quarterbacks and
unlisted players — which is precisely the population whose serve-time
probabilities the L2 live artifact shows inflated. It is real and it should be
fixed. It is not the cause of tonight's 0.412 and it does not touch primaries.

---

## 4. A SEPARATE DEFECT FOUND WHILE BUILDING THE ROLE CLASSES

The incumbent's only role-adjacent feature is the depth `rank`. On the
2021-2024 `nflverse_weekly` vendor, `depth_vintage.weekly` takes each player's
**minimum `depth_team` across all his depth-chart slots** and then orders within
position by `(depth_team, depth_position)`. `depth_position` is a string, and
`KOR < KR < PR < WR` alphabetically.

Measured over 2,432 team-weeks per position, the depth_position that **won the
rank-1 slot**:

| position | rank-1 won by a non-offensive slot (KR/PR/KOR) | detail |
|---|--:|---|
| **WR** | **1,665 / 2,432 = 68.5%** | PR 44.1%, KR 21.0%, KOR 2.7%; genuine `WR` slot only **31.5%** |
| **RB** | 653 / 2,432 = 26.9% | KR 18.7%, PR 3.4%, KOR 3.3%; plus **FB 32.7%**; genuine `RB` slot only 36.1% |
| TE | 29 / 2,431 = 1.2% | `TE` 97.1% |
| QB | 19 / 2,431 = 0.8% | `QB` 99.2% |

Worked example, KC 2023 week 1: Richie James holds `(KR, 1)` and `(PR, 1)`, so
his best rank is 1 and he sorts first — **the model's "WR1" for Kansas City is
the kick returner**, while Rashee Rice sorts fifth or sixth.

The consequence is visible in the realised rates under the chart-rank
definition: chart-"WR1" has a realised zero-target rate of **0.3520** against
chart-"WR2" 0.1570 and chart-"WR3" 0.1572 — non-monotone, because chart rank 1
is not a role. Under the usage-tier definition the same quantities are
0.0892 / 0.1486 / 0.2548 — monotone, as a role ordering should be.

**This is not the cause of tonight's number and I am not proposing a fix.** It
is a measurement: for WR and RB the incumbent is close to role-blind in the
direction it believes it is role-aware, which is worse than being role-blind. It
is the historical-vendor twin of the caveat already recorded on tonight's live
artifact — that the ESPN daily vendor ranks **offence-wide**, so "both clubs'
rank 1 is a tight end tonight". **The role signal is broken in both eras, in two
different ways, and a coefficient fitted across them is fitted to two different
quantities.**

---

## 5. INCUMBENT VERSUS CANDIDATE B — WHERE LAWFUL

Same 39,533 rows, same basis U, forward-chained 2021-2024, game-clustered
bootstrap. **EXPLORATORY.** Candidate B's hypothesis was selected on this same
panel; freezing it does not make this a holdout and no promotion follows from
it. B is measured here and stays SHADOW ONLY.

| class | n | realised zero-app | inc mean | inc Brier | B mean | B Brier | ΔBrier (B − inc) | 95% CI |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| QB1 | 2,174 | 0.1734 | 0.1705 | 0.0641 | 0.1792 | 0.0647 | +0.00052 | [−0.0005, +0.0015] |
| QB2 | 2,166 | 0.7170 | 0.5194 | 0.2571 | 0.7113 | 0.1723 | **−0.08483** | [−0.0966, −0.0726] |
| QB3+ | 1,438 | 0.8442 | 0.4239 | 0.3782 | 0.8037 | 0.1171 | **−0.26105** | [−0.2800, −0.2422] |
| RB1 | 2,174 | 0.1145 | 0.1166 | 0.0372 | 0.1164 | 0.0399 | **+0.00267** | [+0.0018, +0.0036] |
| RB2 | 2,174 | 0.1877 | 0.2100 | 0.0749 | 0.2127 | 0.0782 | +0.00332 | [+0.0020, +0.0046] |
| RB3 | 2,157 | 0.3792 | 0.3484 | 0.1598 | 0.3745 | 0.1495 | −0.01033 | [−0.0147, −0.0060] |
| RB4+ | 3,371 | 0.5972 | 0.4584 | 0.2431 | 0.5755 | 0.1878 | −0.05532 | [−0.0632, −0.0472] |
| WR1 | 2,174 | 0.0731 | 0.0663 | 0.0314 | 0.0652 | 0.0338 | **+0.00237** | [+0.0013, +0.0035] |
| WR2 | 2,174 | 0.1191 | 0.1233 | 0.0408 | 0.1209 | 0.0437 | +0.00285 | [+0.0018, +0.0040] |
| WR3 | 2,174 | 0.1776 | 0.1907 | 0.0729 | 0.1855 | 0.0775 | +0.00461 | [+0.0031, +0.0060] |
| WR4+ | 8,381 | 0.4655 | 0.4171 | 0.1770 | 0.4651 | 0.1609 | −0.01610 | [−0.0195, −0.0126] |
| TE1 | 2,174 | 0.0869 | 0.0825 | 0.0355 | 0.0798 | 0.0374 | **+0.00191** | [+0.0009, +0.0030] |
| TE2 | 2,174 | 0.1564 | 0.1694 | 0.0610 | 0.1655 | 0.0643 | +0.00339 | [+0.0020, +0.0047] |
| TE3+ | 4,235 | 0.4519 | 0.3799 | 0.1832 | 0.4436 | 0.1511 | −0.03214 | [−0.0382, −0.0262] |
| QB_no_prior | 52 | 0.7115 | 0.0103 | 0.6945 | 0.5930 | 0.1697 | **−0.52479** | [−0.6541, −0.3754] |
| RB_no_prior | 108 | 0.4907 | 0.0039 | 0.4858 | 0.3295 | 0.2904 | −0.19544 | [−0.2610, −0.1256] |
| WR_no_prior | 150 | 0.4267 | 0.0362 | 0.3846 | 0.3718 | 0.2334 | −0.15124 | [−0.2120, −0.0874] |
| TE_no_prior | 83 | 0.4578 | 0.0233 | 0.4310 | 0.3565 | 0.2467 | −0.18435 | [−0.2639, −0.1114] |
| **ALL** | **39,533** | 0.3534 | 0.2934 | 0.1420 | 0.3496 | 0.1148 | **−0.02728** | [−0.0291, −0.0255] |

**Read it honestly, and the sign matters.** B's whole gain is on backups,
fringe players and cold starts — the classes where the incumbent's leak and its
survivorship defect live. On **every primary-role class B is slightly worse**,
and those intervals exclude zero too: RB1 +0.0027, WR1 +0.0024, TE1 +0.0019,
QB1 +0.0005. A promotion decision on this evidence is a trade, not a strict
improvement, and it is the kind of trade that needs an untouched fold to settle.
Nothing here authorises promoting B and nothing here should be read as
recommending it.

Week 1 only, non-QB primaries, both arms:

| class | n | realised zero-app | inc mean | inc p90 | inc max | B mean |
|---|--:|--:|--:|--:|--:|--:|
| RB1 | 128 | 0.2891 | 0.2278 | 0.893 | 0.968 | 0.2114 |
| WR1 | 128 | 0.2109 | 0.1544 | 0.701 | 0.977 | 0.1258 |
| TE1 | 128 | 0.2109 | 0.1609 | 0.807 | 0.974 | 0.1340 |

Both arms **under**-assign zero mass to non-QB primaries in week 1, B more so
than the incumbent.

---

## 6. WHAT THIS CHANGES ABOUT V2 PARTICIPATION URGENCY

Stated as measurements and their consequences, not as instructions.

1. **The QB room path is where the urgent participation defect is.** It is
   reached only through `qb_allocation.py`, it is one function
   (`qb3_lib.allocate`), and the mechanism is fully identified: a categorical
   draw of the primary followed by a resample from a share pool that is not
   conditioned on that draw, in a cell whose zero fraction is 0.4735. The
   model's own frame says `P(share = 0 | is primary) = 0.0000`. This is a
   coherence defect inside one sampler, not a modelling disagreement. It maps
   onto V2 item 15 (QB-P2 room state), which should be understood as carrying
   this specific, measured, week-1-certain error rather than a general
   preference for a better QB model.
2. **The non-QB appearance layer does not need emergency work on primaries.**
   Its primary-role zero mass is calibrated to within ±0.01 with intervals
   spanning zero, and its high-zero-mass tail on primaries is *earned* (realised
   0.50 at [0.41, 0.60), 0.99 at [0.85, 1.00]). Reordering V2 to attack it on
   the strength of tonight's 0.412 would be attacking the wrong layer.
3. **The non-QB appearance layer does need work on cold starts**, where it is
   46 points under-assigned with a non-overlapping interval, and on the leak,
   which is worth −0.18 mean zero mass on backup quarterbacks. Both are
   already-named defects; this audit supplies the denominators.
4. **The role signal should be treated as unestablished, not as present.** For
   WR the model's rank-1 is a special-teams slot 68.5% of the time historically
   and an offence-wide ordinal today. Any V2 work that assumes `rank` carries
   role is building on a feature that does not.
5. **The season boundary is a mixture indicator on both paths and is currently
   modelled as an intercept shift on one of them.** On the QB path it flips the
   sign of a cell's error from −0.34 to +0.37. On the non-QB path it flips the
   slope of the history features (D4) in a direction that produces
   under-assignment. Neither is a calendar effect; both are population effects
   that happen to coincide with week 1.

---

## 7. LIMITATIONS, STATED PLAINLY

- **This is exploratory.** The historical panel selected the hypotheses in this
  repository, including Candidate B's. Freezing it does not make it a holdout.
  Nothing here is a confirmatory result and nothing here licenses a promotion.
- **`pbp_2025` does not exist in this repository**, so 2025 has no realised
  opportunity and is excluded from every realised rate. The 2025 depth vendor is
  also the ESPN daily one, whose ranks are offence-wide; mixing it into a
  role-class table would average two different quantities.
- **Neither role definition is clean at a season boundary.** Usage tier ranks a
  returning veteran above a player with no history by construction; chart rank
  is contaminated by special-teams slots. Every boundary result is therefore
  reported under both, and the conclusions agree under both. They would not
  survive a third definition being materially different, and no third definition
  was tried.
- **`0 of 128` is a small denominator for a rare event.** The rule-of-three 95%
  upper bound is 0.0234. The claim "a week-1 chart QB1 essentially never takes
  zero dropbacks" is supported up to about 2.3%, not to zero. That is still an
  order of magnitude below the 0.197 the model assigns and two below the 0.412
  on tonight's board.
- **The QB replay uses 2,000 draws per team-game** (m = 1,000 for the
  tonight reconstruction, to match the sealed board exactly). Monte Carlo SE on a
  p ≈ 0.4 estimate at m = 2,000 is 1.1pp; none of the comparisons above turn on
  a difference that small.
- **`0.412` was reconstructed, not inferred.** The rank-1 rows match the sealed
  `player_draws.npz` to four decimal places. If that reconstruction is wrong,
  every claim in section 2 is wrong with it, and re-running
  `qb3_lib.allocate(fit(frame, 2026), [(Mahomes, 1, 0), (Fields, 2, 0),
  (QB3, 3, 0)], m=1000, seed=20260908, ordinal=202601, team='KC')` is the way to
  find out.
- **Tonight's outcome is not evidence about any of this**, and this document
  must not be revisited after the game to see whether Mahomes played.
