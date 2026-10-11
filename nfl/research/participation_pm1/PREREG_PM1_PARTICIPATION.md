# PM-1 pre-registration: how players on the injury report actually participate

- **Written:** 2026-10-11 at about 19:15 UTC, before any of the data below was downloaded or read in this repository.
  The commit time is authoritative.
- **Owner authorization:** 2026-10-11 (decision E1). Download nflverse `pbp_participation` and `injuries`, 2016-2025.
  Do not use `snap_counts`: they come from Pro Football Reference, whose terms are PROHIBITED_BY_TERMS
  (`nfl/research/integrations/PLATFORM_TERMS_AND_APIS.md`).
- **Status:** PRE-REGISTERED, SHADOW ONLY. It produces a measured participation table. Using that table in the
  production forecast is decision E2: the candidate runs beside the incumbent from week 6, the owner chooses, and
  promotion follows only if this protocol's bars pass.

## 1. Question

When the evidence says a player is active but questionable, doubtful or limited, what does he actually do?

- **P(no participation).** He records zero offensive plays.
- **Share of his normal workload when he plays,** r = (offensive plays he was on the field for) / (his club's
  offensive plays), divided by his own baseline r0.
- **P(early exit).** He plays, and his last on-field play falls before 75% of his club's offensive plays in that game.

These outcomes are defined from **participation**: who was on the field. They are not defined from fantasy
production. Defects are defined against predictions, never against outcomes. The table is a prediction input; the
outcomes are only labels.

## 2. Data (frozen definitions)

| source | file | use |
|---|---|---|
| nflverse `pbp_participation` | `pbp_participation_<season>.csv`, 2016-2025 | `offense_players` per play → plays on field per player-game; `play_id` order → last on-field play |
| nflverse `injuries` | `injuries_<season>.csv`, 2016-2025 | the final game designation (`report_status`) and the practice status of that week (`practice_status`) |

Each file is stored as downloaded (gzip of the original bytes), with URL, retrieval time and SHA-256 in
`nfl/research/participation_pm1/ACQUISITION.json`. Nothing is edited.

**Unit.** One player-game. QB, RB, WR and TE only. Regular season only. Games with participation rows for both clubs.

**Baseline r0.** The median r over the player's most recent up to 4 games with the same club in the same season in
which he had no game designation and played at least one offensive play.

- If fewer than 2 such games exist, use the prior season with the same club.
- If there are still fewer than 2, the player-game is **NO_BASELINE**. It counts toward P(no participation) but is
  excluded from the r distribution. The exclusion is counted, never hidden.

**Strata (declared):**

| dimension | levels |
|---|---|
| designation | QUESTIONABLE, DOUBTFUL, NONE_WITH_LIMITED_OR_DNP_PRACTICE (on the report, no game designation) |
| last practice status that week | DID_NOT_PARTICIPATE, LIMITED, FULL, NONE_RECORDED |
| position | QB, RB, WR_TE |
| injury class | SOFT_TISSUE_LOWER (hamstring, groin, calf, quadriceps, thigh), OTHER |

**Pooling (declared, a prior and not a fit).**

- A cell with n < 30 is shrunk toward its parent, in this order: drop injury class, then practice status, then position.
- The shrinkage is beta-binomial with prior strength **20 pseudo-observations** at the parent rate.
- Sensitivity at 5 and 80 is reported. It is not chosen on outcomes.

## 3. Data roles

| role | seasons | status |
|---|---|---|
| fit | 2016-2023 | to be read after this commit |
| held-out validation | 2024-2025 | untouched until the table is frozen from the fit seasons |
| prospective confirmation | 2026 weeks 6-11 | untouched |

## 4. Endpoints and bars (frozen)

The incumbent behaves this way:
- a QUESTIONABLE or DOUBTFUL player who is not ruled out plays his full role: P(no participation) = 0, r = 1;
- DOUBTFUL is not absence (`availability.py`).

Uncertainty for every endpoint comes from a cluster bootstrap by club-week, B = 4,000, seed 20261011.

| endpoint | definition | bar for SHADOW-CONTINUE |
|---|---|---|
| **H-a** P(no participation) | Brier score on held-out 2024-2025 player-games, PM-1 against the incumbent's 0 | Brier improvement > 0, lower 95% bound > 0 |
| **H-b** calibration | held-out reliability of P(no participation), deciles | calibration slope 95% CI contains 1 **and** intercept 95% CI contains 0 |
| **H-c** workload | CRPS of r on held-out players who played, PM-1's empirical cell distribution against the incumbent's point mass at 1 | CRPS improvement lower 95% bound > 0 |
| **H-d** no harm to undesignated players | PM-1 is applied only to players on the report; for everyone else its output is identical to the incumbent's | verified by construction and by a test |

**Verdicts:**
- SHADOW-CONTINUE: every bar is met;
- REJECT: any H-a, H-b or H-c bar fails;
- REVERSED: an interval lies entirely on the harmful side;
- NOT_EVALUABLE: fewer than 500 held-out designated player-games.

The 2026 prospective weeks repeat H-a to H-c with no change to the table.

## 5. What this does not claim

- A designation is an association. It is not a cause, and nothing here measures why a player sat.
- The table describes the 2016-2025 league. Teams' reporting habits change, and the prospective weeks are what test
  whether the table still holds.
- The DK-points consequence (better forecasts for designated players, through the per-world simulation) is a
  separate, later endpoint. It is run through the existing forward-chain harness, and it needs its own
  pre-registration.

## 6. What voids this

- Any change to the definitions, strata, pooling, endpoints or bars after the fit seasons are read.
- Any use of 2024-2025 or 2026 outcomes in building the table.
- A changed protocol is a new protocol with a new id, PM-2.
