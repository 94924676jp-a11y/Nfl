# P3 pre-declaration — written before any P3 policy or role-transition result

Written 2026-09-07, after the identifier audit in §0 (a data-quality
measurement, not a modelling result) and **before** any selective-policy or
role-transition score existed. Departures are labelled where they occur.

## 0. Facts established before any modelling

- `snap_counts.pfr_player_id` maps to `gsis_id` through nflverse
  `players.csv` (sha256 `5d14969f…`), loaded by the repository's existing
  `nfl/ingest/identifiers.Crosswalk`. **22,653 pairs, reported injective.**
- Coverage on 150,351 REG snap rows 2020–2025: **150,183 mapped (99.8883%)**,
  168 unmapped (0.1117%), every failure carrying the existing named refusal
  `PFR_ID_UNMAPPED`.
- The alternative bridge via `weekly_rosters.pfr_id` covers only 77.51% and is
  **non-injective** (`IzzoRy00`, `YounBy01` each map to two gsis ids). It is
  therefore rejected in favour of `players.csv`.

No fuzzy-name matching is used anywhere. `map_by_name` exists in the module and
is deliberately not called.

## 1. Role-transition candidate targets — all predeclared, none chosen yet

P2's accepted target is `|snap(t) − mean(t−1..t−3)| > 0.20`. Candidates to be
scored **all of them**, with the winner reported by stability across seasons and
not by best AUC:

| id | definition |
|---|---|
| `abs_10` / `abs_20` / `abs_30` | absolute snap-share change > 0.10 / 0.20 / 0.30 |
| `up_20` | upward jump > +0.20 |
| `down_20` | downward loss > −0.20 |
| `to_starter` | prior mean < 0.50 → this game ≥ 0.50 |
| `from_starter` | prior mean ≥ 0.50 → this game < 0.50 |
| `pos_specific` | > 0.20 for WR/TE, > 0.25 for RB (RB committees are noisier) |

**Selection rule, fixed now:** report every candidate; nominate as primary the
one whose AUC varies least across the four evaluation seasons among those with a
base rate between 0.05 and 0.40. AUC magnitude alone does not decide it.

## 2. Selective mixture policies — predeclared, §9/§10

Each is a pregame rule choosing per player-game between `U` (P1 unconditional)
and `A×C`. Thresholds are tuned on 2022–2023 and evaluated on 2024–2025.

| id | rule |
|---|---|
| `P0_always_U` | always U (the P1 incumbent, control) |
| `P1_always_AC` | always A×C (mechanical, the P2 model, control) |
| `P2_info_quality` | A×C when current-week injury evidence is chronology-proven, else U |
| `P3_uncertain_band` | A×C when `θ_lo ≤ p_appear ≤ θ_hi`, else U |
| `P4_zero_persistence` | U when the player did not appear last week, else A×C |
| `P5_scale` | A×C for small-scale targets (target/carry share), U for snap/rpr |
| `P6_combined` | A×C when injury evidence exists AND the player appeared last week |

Band endpoints for `P3` are tuned on 2022–2023 over a fixed grid
`θ_lo ∈ {0.05,0.10,0.20,0.30}`, `θ_hi ∈ {0.70,0.80,0.90,0.95}` and the chosen
pair is reported along with its stability on 2024–2025. No threshold is chosen
after seeing 2024 or 2025.

## 3. Information-quality classes — §12, defined before being tested

| class | definition |
|---|---|
| HIGH | a chronology-proven current-week injury row exists for this player-game |
| MEDIUM | no such row, but the player's team has ≥1 proven row this week **and** the player has ≥4 prior games |
| LOW | neither |

Definition is structural, not tuned. The hypothesis under test is P2's: A×C's
value depends on information quality, so the HIGH−LOW gap should be positive.

## 4. Acceptance rule

P3's selective policy is accepted only if, on **2024–2025 evaluated after
tuning on 2022–2023**, it beats BOTH `P0_always_U` and `P1_always_AC` on pooled
MAE, and does not worsen the role-change cohort. If it beats one and not the
other, that is reported as a partial result in those words.

## 5. Bootstrap

Player-block bootstrap, 400 resamples, seed 20260907, as in P2.
