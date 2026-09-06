# W4 — Receiver / TE opportunity

**Worker 4, NFL Greenfield Architecture research pass. Written 2026-09-06.**
Research only. No production model code was written and no file outside this one
was modified.

Every substantive claim below carries exactly one of `VERIFIED` (a command was
run here, and is shown), `DERIVED` (arithmetic from something VERIFIED, shown),
or `UNVERIFIED-RECALL` (believed from training, not checked here).

---

## 0. Provenance of everything below

`VERIFIED` — all measurements ran in this container against files already in the
shared cache, plus two small files I fetched (§7). Working directory for every
command:

```
SP=/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-4781-5a10-ae09-ef74590f8116/scratchpad
```

`VERIFIED` — input identity (`md5sum $SP/*.csv`):

| File | md5 | Source |
|---|---|---|
| `part2024.csv` | `9bd3bfa981cd302148836c67759cb02c` | nflverse `pbp_participation/pbp_participation_2024.csv` |
| `pbp2024.csv` | `3880d4554c66740ac1082d530215e142` | nflverse `pbp/play_by_play_2024.csv` |
| `ftn2024.csv` | `4d60b101d93def24dffe59c68b97a239` | nflverse `ftn_charting/ftn_charting_2024.csv` |
| `rosters_roster_2024.csv` | `1451e94aef184b28d1a8609388745c66` | nflverse `rosters/roster_2024.csv` |
| `ngs_rec.csv` | `27a9527e75742a03186871ef357bc2e8` | nflverse `nextgen_stats/ngs_receiving.csv.gz`, gunzipped (fetched by me, §7) |

Measurement scripts, all in `$SP`, all throwaway evidence and deliberately **not**
committed to `nfl/` (grounding brief, "Hard scope limit"):
`extract_pbp.py`, `build_pg.py`, `reliability.py`, `tdreg.py`, `highvol.py`,
`ftn_rec.py`, `extras.py`, and the frozen spec `PREDECLARATION.md`.

`VERIFIED` — the reliability analysis spec (population, split rule, metric list,
statistic, bootstrap seed, shrinkage estimator) was written to
`$SP/PREDECLARATION.md` **before** `reliability.py` was run, per Constitution
Rule 004a. Two subgroup analyses were added *after* reading results; both are
marked `[EXPLORATORY / POST-HOC]` wherever they appear and are never used as a
design commitment on their own.

---

## 1. The routes-run primitive

### 1.1 CRITICAL FINDING — `participation.route` is not per-player and cannot support routes run

`VERIFIED`. This is the finding the task asked me to test first, and it is
negative.

```
python3.12 - <<'EOF'
import csv, collections; csv.field_size_limit(10**9)
rc=collections.Counter()
for row in csv.DictReader(open('part2024.csv',newline='')): rc[row['route']]+=1
print(len(rc)); print(rc.most_common(40))
EOF
```

Result: **14 distinct values across 45,919 rows**, one scalar per play, and
**zero rows contain a `;`** (checked explicitly). It is not a delimited list.

```
''  26809 | QUICK OUT 3462 | HITCH/CURL 3299 | SCREEN 1995 | IN/DIG 1760
GO 1683 | DEEP OUT 1435 | SHALLOW CROSS/DRAG 1286 | SLANT 1085 | CORNER 949
SWING 891 | POST 838 | WHEEL 229 | TEXAS/ANGLE 198
```

`DERIVED` — it is the route of the **targeted** receiver, not of the play and
not of every receiver. Mean `pbp.air_yards` conditioned on `route`, over the
19,110 non-empty rows:

| route | n | mean air yards |
|---|---|---|
| GO | 1463 | +24.86 |
| POST | 782 | +20.08 |
| CORNER | 848 | +19.08 |
| WHEEL | 210 | +16.03 |
| DEEP OUT | 1317 | +12.80 |
| IN/DIG | 1630 | +12.48 |
| HITCH/CURL | 3146 | +6.05 |
| SLANT | 1027 | +5.90 |
| SHALLOW CROSS/DRAG | 1221 | +3.71 |
| TEXAS/ANGLE | 187 | +3.15 |
| QUICK OUT | 3329 | +2.80 |
| SWING | 850 | −3.18 |
| SCREEN | 1894 | −3.18 |

If `route` described the play rather than the target, air yards would not
separate by 28 yards across route labels. It does. Also 18,006 of the 19,110
non-empty rows are `pass_attempt == 1` and 17,611 carry a
`receiver_player_id`.

**Consequence, stated plainly as the task requires:** *true* routes run per
player — the PFF/SIS-style count of "this receiver ran a pattern on this
dropback" — is **not derivable from `pbp_participation`**. Any NFL feature named
"routes run" that is built from this feed is a different quantity wearing that
name. That naming collision is exactly Failure Taxonomy Class C (declaration
drift) and should be blocked at the registry, not at review.

`UNVERIFIED-RECALL` — per-player routes-run charting is a paid product (PFF,
Sports Info Solutions) and is not in any free nflverse release. I could not
check this here; it must be confirmed before anyone plans around it.

### 1.2 What IS available, and it is strong: `offense_players` on dropbacks

`VERIFIED` — `offense_players` is a `;`-delimited gsis_id list, and
`offense_players` / `offense_names` / `offense_positions` / `offense_numbers`
are **positionally aligned**: on the first 3,000 rows, gsis→roster name matched
the parallel `offense_names` entry in **32,998 of 33,000** cases (the 2
exceptions are one gsis id, `00-0029542`, which the roster file maps to a
different player — a roster-file defect, not a participation defect).

`VERIFIED` — `n_offense == 11` on **45,906 of 45,919** rows.

`VERIFIED` — **the field list has zero missingness on pass plays.** The decisive
test: on every one of the 17,013 regular-season non-two-point targets, was the
targeted receiver present in `offense_players`?

```
target_on_field: 17013 / 17013     (miss rate 0.0000 in all 18 weeks)
passer present:  17013 / 17013
```

That is the primitive. It is not routes run; it is **pass-play participation**:
*the player was on the field for a team dropback*. I will call it `pass_snaps`
and its rate `RPR` (route participation rate proxy) throughout, and the name
should keep a qualifier in any registry entry.

`DERIVED` — the gap between `pass_snaps` and true routes run is **pass
protection and chip responsibility**. It is near-zero for WRs, moderate for TEs,
and large for RBs. `UNVERIFIED-RECALL` — I could not measure that gap here
because no ground-truth routes-run source is reachable; the RB numbers in §2
(TPRR reliability 0.466 vs 0.746 for WR/TE) are consistent with the denominator
being badly wrong for RBs, but that is suggestive, not a measurement of the gap.

### 1.3 Join accounting, in full

`VERIFIED` (`python3.12 $SP/build_pg.py`):

| Step | Rows | Note |
|---|---|---|
| `pbp_participation_2024.csv` rows | 45,919 | |
| matched to `play_by_play_2024` on `(nflverse_game_id, play_id)` → `(game_id, play_id)` | **45,919 (100.00%)** | zero unmatched |
| dropped: `season_type != REG` | 2,053 | postseason, out of scope for the frame |
| dropped: `two_point_attempt == 1` | 135 | see 1.4 |
| surviving | 43,731 | |
| `possession_team != pbp.posteam` | **0** | |
| team dropbacks (`qb_dropback == 1`) | **20,116** | includes sacks and scrambles |
| targets (`pass_attempt == 1` and `receiver_player_id` non-empty) | **17,013** | |
| player-game rows emitted | 17,563 | |
| distinct games / team-games | **272 / 544** | full 2024 regular season |

`VERIFIED` — 3,573 pbp plays have **no** participation row; 2,127 are
`play_type == 'no_play'` and 1,446 have an empty `play_type`. None of them carry
`qb_dropback == 1` or a target, so nothing opportunity-bearing is lost. A
further 2,704 `no_play` rows *do* appear in participation and were kept; they
also carry no dropback and no target, so they are inert.

### 1.4 External validation of the join — it reconciles to official stats

`VERIFIED` — my per-player-week aggregates against nflverse
`player_stats_2024.csv` (`season_type == REG`), over 4,263 player-weeks with a
non-zero count on either side:

| Quantity | Mine | Official | Player-weeks exact |
|---|---|---|---|
| Receptions | **11,629** | **11,629** | **4,263 / 4,263 = 1.00000** |
| Targets | 17,013 | 17,013 | 0.97795 → **1.00000 after the two-point fix** |
| Receiving yards | 126,853.0 | 126,964.0 | 0.99531 |
| Receiving TDs | 806 | 807 | 0.99977 |
| Receiving air yards | 131,675.0 | 131,664.0 | — |

The initial target discrepancy was **exactly +90**. `VERIFIED`: there are
exactly 90 two-point-conversion targets in 2024 REG, and all 90 have blank
`air_yards`; nflverse excludes them from `targets`. After excluding
`two_point_attempt == 1` the target total is 17,013, matching official to the
unit. The residual 111 receiving yards and 1 TD are `UNVERIFIED-RECALL` almost
certainly lateral receiving yards (`lateral_receiving_yards`,
`lateral_receiver_player_id`) which I did not attribute; I did not confirm this.

This reconciliation is the thing that makes the rest of the document usable. It
is also the Class A guard the grounding brief asks for: the primitive is not
"non-empty", it is *equal to an independently published total*.

### 1.5 Measured per-player-game quantities, 2024

`VERIFIED` — top 20 WR/TE by season pass-play participation (`$SP/extras.py`).
`RPR = pass_snaps/team_db`, `TS = tgt/team_tgt`, `TPRR = tgt/pass_snaps`,
`AYS = air_yards/team_air_yards`.

```
player                  pos   g  psnaps  teamDB    RPR  tgt     TS   TPRR    AYS   aDOT  TD
Jerry Jeudy             WR   17     711     762  0.933  145  0.229  0.204  0.321  11.11   4
Ja'Marr Chase           WR   17     705     721  0.978  175  0.279  0.248  0.337   8.72  17
DJ Moore                WR   17     664     680  0.976  140  0.266  0.211  0.252   7.49   6
Garrett Wilson          WR   17     650     665  0.977  154  0.261  0.237  0.354   9.14   7
Tre Tucker              WR   17     635     700  0.907   81  0.137  0.128  0.248  12.56   3
Jaxon Smith-Njigba      WR   17     624     670  0.931  137  0.241  0.220  0.294   8.66   6
Rome Odunze             WR   17     621     680  0.913  101  0.192  0.163  0.335  13.84   3
Brock Bowers            TE   17     617     700  0.881  153  0.258  0.248  0.225   6.03   5
Justin Jefferson        WR   17     612     625  0.979  154  0.298  0.252  0.375  10.92  10
Travis Kelce            TE   16     596     655  0.910  133  0.240  0.223  0.248   6.64   3
```

`VERIFIED` — 220 WR/TE cleared 100 season pass snaps; league-wide mean
`RPR = 0.6113` across that set; 379 distinct WR/TE recorded ≥1 pass snap;
4,128 WR/TE player-games and 1,526 RB player-games have `pass_snaps > 0`;
4,255 player-games have ≥1 target.

---

## 2. Reliability — the key deliverable

### 2.1 Method (frozen in `$SP/PREDECLARATION.md` before results were read)

`VERIFIED` — population: roster position in {WR, TE}, 2024 REG, season
`pass_snaps ≥ 100` **and** ≥ 6 games with `pass_snaps > 0` → **n = 219 players**,
median 16 games each. Split: a player's games ordered by week; indices
0,2,4,… = half A, 1,3,5,… = half B (the task's "odd vs even games"). Each half's
metric is `sum(numerator)/sum(denominator)`, not a mean of per-game rates. A
player is dropped from a metric only if a half's denominator is 0 (drops
reported; **zero drops** for WR/TE on every metric). Statistic: Pearson r
between halves, with Spearman ρ, the Spearman–Brown full-season projection
`r_SB = 2r/(1+r)`, and a 95% CI from 2,000 player-resampled bootstrap
replicates, seed 20260906.

Command: `python3.12 $SP/reliability.py`.

### 2.2 WR + TE, n = 219 — ranked by stability

`VERIFIED`:

| Rank | Metric | denominator (median, half A) | r | ρ | r_SB | 95% CI on r |
|---:|---|---:|---:|---:|---:|---|
| 1 | **route participation** (`pass_snaps/team_db`) | 294 dropbacks | **0.9478** | 0.9420 | 0.9732 | [0.9180, 0.9673] |
| 2 | **target share** (`tgt/team_tgt`) | 245 team targets | **0.9154** | 0.9281 | 0.9558 | [0.8939, 0.9345] |
| 3 | **air yards share** | 1876 team air yds | **0.8870** | 0.8938 | 0.9401 | [0.8492, 0.9174] |
| — | *receiving yards per game* | 8 games | 0.8423 | 0.8820 | 0.9144 | [0.7975, 0.8827] |
| 4 | **TPRR** (`tgt/pass_snaps`) | 167 pass snaps | **0.7463** | 0.7623 | 0.8547 | [0.6788, 0.8027] |
| 5 | **red-zone target share** | 32 team RZ tgts | 0.6166 | 0.6322 | 0.7629 | [0.5201, 0.7053] |
| — | *TDs per game* | 8 games | 0.4893 | 0.5427 | 0.6571 | [0.3759, 0.6028] |
| 6 | **yards per reception** | 18 receptions | 0.4610 | 0.4631 | 0.6310 | [0.3551, 0.5550] |
| 7 | **catch rate** (`rec/tgt`) | 30 targets | 0.2996 | 0.3435 | 0.4611 | [0.1497, 0.4428] |
| 8 | **yards per target** | 30 targets | 0.2529 | 0.2935 | 0.4037 | [0.1281, 0.3791] |
| 9 | **TD rate per target** | 30 targets | **0.1671** | 0.2563 | 0.2863 | [0.0258, 0.3385] |

**The ordering is the architecture.** Opportunity (who is on the field, who gets
thrown at, how far downfield) is highly stable. Efficiency conditional on
opportunity (catch rate, yards per target, TD rate) is barely stable at all.

### 2.3 Measured shrinkage constants — the MLB `rates.py:220` analogue

`VERIFIED` — method of moments on the **full season** (not the halves), for
count-denominator rates:

```
V_obs  = population variance of player rates
E_samp = mean_i [ pbar(1-pbar)/n_i ]
V_true = V_obs - E_samp
k      = pbar(1-pbar) / V_true          reliability(n) = n/(n+k)
```

WR + TE, n = 219:

| Metric | p̄ | V_obs | E_samp | V_true | **k** | reliability at median season n |
|---|---:|---:|---:|---:|---:|---:|
| route participation | 0.6177 | 0.054959 | 0.000458 | 0.054501 | **4.3** dropbacks | 0.993 (n=574) |
| target share | 0.1333 | 0.006532 | 0.000264 | 0.006268 | **18.4** team targets | 0.963 (n=484) |
| TPRR | 0.1695 | 0.003768 | 0.000531 | 0.003237 | **43.5** pass snaps | 0.878 (n=312) |
| red-zone target share | 0.1328 | 0.008753 | 0.002064 | 0.006689 | **17.2** team RZ tgts | 0.780 (n=61) |
| catch rate | 0.6603 | 0.013068 | 0.006558 | 0.006509 | **34.5** targets | 0.610 (n=54) |
| TD rate per target | 0.0495 | 0.001721 | 0.001377 | 0.000344 | **137.0** targets | **0.283** (n=54) |

`VERIFIED` — same estimator by position:

| Metric | WR only (n=142) k | TE only (n=77) k | RB (n=76) k |
|---|---:|---:|---:|
| route participation | 4.7 | 4.6 | 8.4 |
| target share | 21.0 | 19.1 | 47.8 |
| TPRR | 49.3 | 46.3 | 107.2 |
| catch rate | 45.2 | 62.7 | 37.8 |
| TD rate per target | **1421.6** | **51.6** | 60.2 |
| red-zone target share | 19.3 | 15.6 | 36.1 |

`DERIVED` — the WR/TE TD-rate split is the most interesting cell on this page.
For **WRs alone**, `V_true = 0.000033` against `E_samp = 0.001101`: 97% of the
observed spread in WR TD-per-target is sampling noise and `k ≈ 1,422` targets,
which no WR reaches in three seasons. For **TEs**, `V_true` is 28× larger and
`k = 51.6`. TEs really do differ in TD rate per target; WRs, within one season,
essentially do not. Any receiver layer that applies one TD-rate shrinkage
constant across WR and TE is wrong by a factor of ~28 in true variance for one of
the two groups.

### 2.4 RB, n = 76 — separately, because the denominator is broken for them

`VERIFIED`: route participation r = 0.8977; target share 0.7688; TPRR 0.4663;
**air yards share 0.3078** [0.0247, 0.5379]; catch rate 0.1275; yards per
reception **−0.0664** [−0.3441, 0.2211]; TD rate 0.1890; yards per target 0.0910.

`DERIVED` — RB TPRR is far less stable than WR/TE TPRR (0.466 vs 0.746) and
`k` is 2.5× larger (107 vs 44). That is what a mis-specified denominator looks
like: `pass_snaps` counts pass-protection snaps as if they were routes, and the
contamination rate varies by back and by game script. **RB targets should not use
`pass_snaps` as a denominator** until a real routes source exists; use team
dropbacks or team targets instead and accept the coarser rate.

### 2.5 `[EXPLORATORY / POST-HOC]` — the denominator, not the metric, is what moves

Added after reading §2.2. Not predeclared. Command: `python3.12 $SP/highvol.py`.

| Metric | ≥100 pass snaps (n=219) | ≥80 season targets (n=64) | ≥120 season targets (n=21) |
|---|---:|---:|---:|
| catch rate | 0.2996 | 0.4497 | 0.4983 |
| yards per reception | 0.4610 | 0.5656 | 0.6883 |
| yards per target | 0.2529 | 0.5048 | 0.3453 |
| **TD rate per target** | **0.1671** | **0.0547** | **0.0854** |
| target share | 0.9154 | 0.6692 | 0.2805 |
| route participation | 0.9478 | 0.8316 | 0.6463 |

Two readings, and one of them is a trap:

- The efficiency metrics rise with denominator, as a noise story predicts. TD
  rate **does not** — it is the only metric that stays flat near zero at every
  sample size.
- The opportunity metrics *appear* to collapse. `DERIVED` — that is **range
  restriction**, not instability: selecting on ≥120 season targets removes almost
  all the between-player variance in target share, so r falls even though the
  measurement got more precise. Anyone quoting "target share r = 0.28 for
  high-volume receivers" would be quoting a selection artifact. It is the same
  class of error as the within-quartile calibration slopes in
  `validation_actuals.json` that `CLAUDE.md` forbids quoting.

---

## 3. TD rate specifically — quantifying the regression

### 3.1 Within season

`VERIFIED` (§2.2, §2.3): split-half r = 0.1671 [0.0258, 0.3385]; `k` = 137
targets for WR+TE, 1,422 for WR alone. `VERIFIED` — season target counts in the
219-player population: median **54**, p90 117, max 175. Only **14 of 219 (6.4%)**
reach 137 targets and only 39 (17.8%) reach 100.

`DERIVED` — at the *median* receiver's full season (54 targets), reliability of
observed TD-per-target is `54/(54+137) = 0.283`. The correct weight on a
receiver's own observed TD rate, at a full season of data, is roughly
**one quarter**, with three quarters going to the positional mean. For a WR
using the WR-only constant it is `54/(54+1422) = 0.037` — effectively zero.

### 3.2 Between seasons — n = 760 pairs, the stronger evidence

`VERIFIED` — nflverse NGS season-level receiving rows (`week == 0`), all seasons
2016–2025, paired season *t* → *t+1* for the same `player_gsis_id`, requiring
≥40 targets in both years: **760 pairs from 248 distinct players**. 95% CI from a
**cluster bootstrap resampling players** (not pairs), 2,000 reps, seed 20260906 —
a player contributes up to 9 pairs, so pair-level resampling would understate the
interval, exactly the mistake `CLAUDE.md` "Two pending methodology fixes" #1
describes.

| Metric | r (t → t+1) | 95% CI (clustered on player) |
|---|---:|---|
| average intended air yards (aDOT) | **0.7681** | [0.7227, 0.8054] |
| share of team intended air yards | 0.6563 | [0.5984, 0.7029] |
| **average separation** | **0.5921** | [0.5275, 0.6481] |
| average cushion | 0.4985 | [0.4253, 0.5602] |
| catch percentage | 0.4820 | [0.4192, 0.5402] |
| average YAC | 0.4711 | *not computed — see note* |
| YAC above expectation | 0.3646 | [0.2399, 0.4652] |
| yards per target | 0.2951 | [0.2187, 0.3615] |
| **TD per target** | **0.1434** | **[0.0606, 0.2175]** |

*Note:* `avg_yac` (0.4711) and `avg_expected_yac` (0.4619) come from the first,
no-bootstrap run; the cluster bootstrap was run over the eight metrics that
carry an interval above. Their point estimates are `VERIFIED`; their intervals
were not computed and must not be inferred from the neighbouring rows.

`DERIVED` — TD per target is the least persistent quantity measured anywhere in
this document, on a 760-pair sample, and its interval excludes zero only barely.
The optimal linear weight on a receiver's prior-season TD rate, assuming
comparable variance across years, is **r ≈ 0.14 — about 86% regression to the
positional mean.**

`VERIFIED` — caveat that must travel with this table: the NGS season rows are a
**qualified leaderboard**, not full coverage (§4.3). The population is
target-selected, which compresses volume-related variance. This makes the
opportunity-metric r's here conservative; it does not rescue TD rate.

### 3.3 The back-test that shows the naive projection actually losing

`VERIFIED` (`python3.12 $SP/tdreg.py`). Predict half-B TD count for the 219
WR/TE, from half-A only. League TD/target in the population = 0.05145.

| Predictor for half-B TDs | RMSE | MAE |
|---|---:|---:|
| naive: player's half-A TD rate × half-B targets | **1.7711** | 1.1319 |
| league TD rate × half-B targets (no player term) | **1.2692** | 0.9812 |
| shrunk to league with k = 137 | 1.2768 | 0.9518 |
| league TD-per-yard × player half-A yards/target × half-B targets | 1.2956 | 0.9890 |

Mean actual half-B TDs = 1.393.

`DERIVED` — **the naive per-player TD rate is 40% worse in RMSE than ignoring
the player entirely.** Sensitivity over the shrinkage constant:

```
K=0 → 1.7711 | 20 → 1.4916 | 50 → 1.3604 | 100 → 1.2940
K=137 → 1.2768 | 200 → 1.2651 | 300 → 1.2601 | 500 → 1.2596 | ∞ → 1.2692
```

The curve is flat from K≈200 upward. `DERIVED` — any K in [137, ∞) is
defensible on this data; **nothing below ~100 is**, and K = 0 is a large,
measurable error. The floor of that curve sits 0.7% below the pure-league
predictor, so within one season the player-specific TD-rate term buys
approximately nothing.

`VERIFIED` — the same exercise for **yards**: naive player yards-per-target ×
half-B targets gives RMSE 71.73; league yards-per-target × half-B targets gives
**58.05** (mean actual 228.9 yards). In the `[EXPLORATORY]` ≥80-target subgroup
the naive predictor still loses (95.10 vs 82.35), and in the ≥120 subgroup it
still loses (118.99 vs 104.64).

`DERIVED` — this generalises past TDs and is the single most important number
for a receiver market model: **at one-season samples, per-player receiving
efficiency does not beat the league rate applied to the player's own volume.**
Volume is the projection; efficiency is a shrinkage problem, not a feature.

`UNVERIFIED-RECALL` — public and DFS receiver models commonly project TDs from a
player's recent TD rate or from red-zone TD share without shrinkage. I believe
this is widespread; I did not check any external model here. The measurement
above stands on its own regardless.

---

## 4. Alignment and deployment — what is actually recoverable

### 4.1 Slot vs wide is ABSENT. Stated plainly.

`VERIFIED` — `offense_positions` is a **depth-chart position**, not an
alignment. Cross-tabulated against `rosters/roster_2024.csv` `position` over
5,000 plays, every disagreement is a vocabulary difference:
`OL → T/G/C`, `DB → CB/FS/SS`, `LB → ILB/OLB/MLB`, `RB → FB`. Skill positions
agree exactly (`WR→WR` 11,215; `TE→TE` 6,742; `RB→RB` 4,806).

`VERIFIED` — worse for alignment purposes, **`offense_positions` is
alphabetically sorted on 45,919 of 45,919 rows** (`p == sorted(p)`). The list
order therefore carries **no** left-to-right field information. There is no slot
index, no wide/inside flag, no receiver-side field.

`VERIFIED` — `ftn_charting_2024` has 29 columns and none of them is a receiver
alignment: the positional fields are `starting_hash`, `qb_location`,
`n_offense_backfield`, `n_defense_box`. `is_motion` is play-level only, with no
player attached.

**So: slot/wide/alignment is not recoverable from `pbp_participation`, `pbp`, or
`ftn`.** Do not plan a slot-rate feature on these feeds.

`UNVERIFIED-RECALL` — I believe PFR's advanced receiving splits and PFF both
publish slot snap counts, and that NFL Next Gen Stats computes alignment
internally without publishing it per player-game. None of that was checkable
here. `VERIFIED` — the one PFR receiving file that exists at
`pfr_advstats/advstats_week_rec_2024.csv` has 17 columns and no alignment field:
`rushing_broken_tackles, receiving_broken_tackles, passing_drops,
passing_drop_pct, receiving_drop, receiving_drop_pct, receiving_int,
receiving_rat` plus keys.

### 4.2 Personnel and formation ARE recoverable, cleanly

`VERIFIED` — `offense_personnel` is a raw position-count string
(e.g. `"1 C, 2 G, 1 QB, 1 RB, 2 T, 1 TE, 3 WR"`), 1,458 distinct strings, not a
standard personnel code. Parsing `(\d+)\s+([A-Z]+)` and forming the conventional
`RB+FB / TE` code over the 20,116 dropback plays: **24 rows (0.12%) fail to sum
to 11**, all others parse.

Share of WR/TE dropback participation snaps by personnel:

```
11: 0.7148 | 12: 0.1880 | 21: 0.0438 | 13: 0.0237 | 22: 0.0081
10: 0.0057 | 01: 0.0054 | 02: 0.0052
```

`VERIFIED` — `offense_formation` on dropback plays:
`SHOTGUN 0.8212 | UNDER CENTER 0.1447 | PISTOL 0.0335 | blank 0.0006`.
(Over all 45,919 rows including special teams, 9,237 are blank — the blanks are
concentrated in non-scrimmage plays.)

`DERIVED` — the recoverable deployment vocabulary is therefore: personnel
grouping, formation, `n_offense_backfield` and `qb_location` (ftn),
`is_motion` / `is_play_action` / `is_screen_pass` / `is_rpo` (ftn, play-level,
attributable to the *targeted* receiver only), plus a player's own
personnel-conditional participation rate. That is a real deployment axis. It is
not alignment, and the registry entry must not call it that.

### 4.3 FTN and NGS — two extra receiver layers, with one hazard each

`VERIFIED` — **FTN joins perfectly.** 48,031 of 48,031 `ftn_charting_2024` rows
match `pbp` on `(nflverse_game_id, nflverse_play_id)`, covering all 17,013
targets. Attributing the play-level flags to `pbp.receiver_player_id` gives
per-receiver rates. Split-half (odd/even week index, WR/TE, ≥50 season targets,
≥6 weeks, n = 120):

| Metric | denominator (median) | r | r_SB |
|---|---:|---:|---:|
| screen rate | 41 targets | **0.7158** | 0.8344 |
| catch rate (this population) | 41 targets | 0.5084 | 0.6741 |
| **catchable-ball rate** | 41 targets | **0.4845** | 0.6527 |
| play-action rate | 41 targets | 0.4222 | 0.5937 |
| contested-ball rate | 41 targets | 0.2724 | 0.4282 |
| catch rate **given catchable** | 31 catchable | 0.2211 | 0.3622 |
| created reception per reception | 29 receptions | 0.1305 | 0.2308 |
| **drops per catchable ball** | 31 catchable | **0.0201** | 0.0394 |

League totals over the 17,013 targets: catchable 12,650 (0.744), contested 2,431,
drops 581, created receptions 529, screens 1,757, play-action 3,798,
motion 8,474.

`DERIVED` — two conclusions that change how catch rate should be modelled:

1. **Drop rate is noise.** r = 0.020 over a full season. A "drop-prone receiver"
   term is not identifiable within one season and should be REJECTED rather than
   left untested.
2. **Catch rate decomposes, and only the first half is stable.**
   `catch rate = P(catchable | target) × P(catch | catchable)`. The first factor
   has r = 0.485; the second has r = 0.221. The stable part of catch rate is
   *whether the throw was catchable*, which is a property of the throw and the
   route depth, not of the hands.
   `VERIFIED` — and even that is largely depth: across the 120 receivers,
   **r(catchable rate, aDOT) = −0.6179** (mean catchable 0.722, mean aDOT 9.73).
   `DERIVED` — so ~38% of the variance in catchable rate is aDOT alone; once
   aDOT is in the model there is little independent receiver-level catch signal
   left within one season.

`VERIFIED` — **NGS receiving carries `avg_separation` and `avg_cushion`, which
exist nowhere else in these feeds**, and its year-to-year r (0.592 and 0.499,
§3.2) makes separation the most persistent *skill* quantity measured in this
document after aDOT.

`VERIFIED` — **the NGS hazard is selection.** For 2024 REG weekly rows:
1,253 rows, 198 distinct players, covering only **29.4%** of the 4,255
player-weeks that had ≥1 target. Median targets among covered player-weeks = 7;
median among uncovered = 2; minimum among covered = 5; **maximum among uncovered
= 11**. So it is not a clean threshold — availability of the feature is
correlated with volume in a way I could not fully characterise. `DERIVED` — a
model that conditions on `avg_separation` being present is conditioning on
opportunity, and any measured effect of separation will be confounded with
volume. NGS-derived features must carry an explicit missingness indicator and a
declared imputation, and must never be silently dropped-to-complete-cases.

---

## 5. Red-zone opportunity — measurably NOT separable within one season

`VERIFIED` (`python3.12 $SP/reliability.py`, red-zone block). WR+TE, n = 219,
red zone defined as `pbp.yardline_100 ≤ 20`, red-zone target share =
`player RZ targets / team RZ targets`, halves as in §2.1:

```
r(rzTS_A, rzTS_B)                 = 0.6166
r(rzTS_A,  TS_A)                  = 0.7667
r(rzTS_B,  TS_A)                  = 0.7322
partial r(rzTS_A, rzTS_B | TS_A)  = 0.1263
season RZ targets per player: median 7, mean 8.16, max 36
```

`DERIVED` — three readings, and they agree:

1. **Overall target share from half A predicts half B's red-zone target share
   (r = 0.732) nearly as well as half A's own red-zone target share does
   (r = 0.617).** The red-zone-specific measurement adds almost nothing over the
   general one, and is *worse* at predicting itself than the general metric is.
2. The partial correlation, once overall target share is controlled, is
   **0.126** — the residual "distinct red-zone role" signal.
3. The denominator is the reason: the **median receiver sees 7 red-zone targets
   in an entire season**. At n = 7 with p̄ = 0.133, sampling SD alone is
   ≈ 0.13, which is larger than the between-player true SD (√0.006689 = 0.082
   from §2.3).

`VERIFIED` — the season-aggregate correlation matrix says the same thing
(n = 220 WR/TE, ≥100 pass snaps):

```
          RPR      TS    TPRR     AYS    aDOT    rzTS
RPR     1.000   0.868   0.555   0.813   0.321   0.762
TS      0.868   1.000   0.854   0.878   0.220   0.866
TPRR    0.555   0.854   1.000   0.697   0.116   0.725
AYS     0.813   0.878   0.697   1.000   0.562   0.740
aDOT    0.321   0.220   0.116   0.562   1.000   0.141
rzTS    0.762   0.866   0.725   0.740   0.141   1.000
```

`rzTS` sits at r = 0.866 with plain target share. `aDOT` is the only column that
is close to orthogonal to volume (0.116–0.562).

**Answer to the task's question:** within one season, a distinct red-zone role is
**not identifiable** for the median receiver. It is mostly noise plus a
re-measurement of overall target share. `DERIVED` — the correct treatment is a
**hierarchical** one: model red-zone target share as overall target share plus a
heavily shrunk player deviation (k = 17.2 team red-zone targets from §2.3, i.e.
at the median 7 the deviation is weighted `7/(7+17.2) = 0.29`), never as a
free-standing rate. `UNVERIFIED-RECALL` — I believe multi-season pooling would
identify a real TE red-zone effect specifically (consistent with the TE TD-rate
`k = 51.6` vs the WR 1,422 in §2.3); that is a hypothesis for a pre-registration,
not something this data establishes.

---

## 6. Proposed receiver layer

Research proposal only. Nothing here is registered; every row below would enter
`FEATURE_REGISTRY.md` at **EXPERIMENTAL** at best, and Rule 024 forbids anything
higher until the named experiment has run. The registry statuses shown are the
*proposed target*, not a claim.

### 6.1 The split: opportunity is modelled, efficiency is shrunk

`DERIVED` from §2–§5. The receiver layer should be two-stage, and the stages
should not share a denominator.

**Stage 1 — opportunity (modelled per player-game).** All three of these earned
their place with split-half r ≥ 0.89 and `k` ≤ 18.4.

| Component | Denominator | Measured stability | Proposed shrinkage | Target status |
|---|---|---|---|---|
| route participation rate | team dropbacks | r = 0.9478, k = 4.3 | essentially none | EXPERIMENTAL → CORE |
| target share \| on field, i.e. TPRR | player pass snaps | r = 0.7463, k = 43.5 | k = 43.5 measured | EXPERIMENTAL → CORE |
| aDOT | player targets | year-to-year r = 0.7681 | modest | EXPERIMENTAL → CORE |

`DERIVED` — decomposing target share as `RPR × TPRR × (team dropbacks)` rather
than modelling target share directly is preferable *even though target share is
itself more stable (0.915)*, because the two factors respond to different
real-world events: RPR moves with injuries, snap counts and personnel; TPRR moves
with role. A depth-chart change alters RPR without altering TPRR, and a
target-share model cannot express that. This is a design argument, not a
measurement, and the falsification test in §6.3 is exactly what would settle it.

**Stage 2 — efficiency conditional on a target (shrunk hard, mostly to league).**

| Component | Denominator | Measured stability | Proposed shrinkage | Target status |
|---|---|---|---|---|
| catchable-ball rate | targets | r = 0.4845, but r = −0.62 with aDOT | model from aDOT first, small player residual | EXPERIMENTAL |
| catch \| catchable | catchable balls | r = 0.2211 | near-total shrinkage | EXPERIMENTAL |
| YAC above expectation | receptions | year-to-year r = 0.3646 | heavy | EXPERIMENTAL |
| separation (NGS) | targets, **29.4% coverage** | year-to-year r = 0.5921 | heavy + explicit missingness | EXPERIMENTAL |
| **TD per target** | targets | r = 0.1671; k = 137 (WR+TE), 1,422 (WR), 51.6 (TE) | **near-total; position-specific k** | EXPERIMENTAL |
| drops per catchable | catchable balls | r = 0.0201 | — | **REJECTED — measured as noise** |
| free-standing red-zone target rate | team RZ targets | partial r = 0.126 given TS | — | **REJECTED as free-standing; keep only as a shrunk deviation** |

`DERIVED` — every `k` above is *measured* (method of moments, §2.3) or
*bounded by a back-test* (§3.3), never chosen. That is the property `CLAUDE.md`
rule 3 demands and the property `rates.py:220` has in MLB. Two of them are
position-specific and must stay that way.

### 6.2 Denominators, stated once, because mixing them is the recurring defect

`DERIVED`. Constitution Rule 019's MLB analogue applies directly: these are
different denominators and rates on them may not be pooled.

```
team dropbacks   -> route participation rate
player pass snaps-> TPRR                      (RB: DO NOT USE, see §2.4)
player targets   -> aDOT, catch rate, TD/target, yards/target
catchable balls  -> catch|catchable, drops
receptions       -> YPR, YAC, created receptions
team targets     -> target share
team air yards   -> air yards share
team RZ targets  -> red-zone deviation only
```

### 6.3 Falsification experiment, one per component

Each is stated as what would make me withdraw the component. Metrics, splits and
clustering are to be hashed into the ticket before the run (Rule 004a); the
control is the trivial benchmark named in each row (Rule 004).

| # | Component | Falsification test | Withdraw if |
|---|---|---|---|
| F1 | routes-run naming | Obtain any per-player routes-run source for ≥2 weeks and correlate with `pass_snaps` | corr(pass_snaps, true routes) < 0.95 for WR — then the proxy needs a position-specific correction, and the name must change regardless |
| F2 | RPR × TPRR vs target share | Forward-chained: predict week *t* targets from weeks 1..*t*−1, RPR×TPRR×dropbacks vs direct target share. Held-out weeks only | the decomposition does not beat direct target share on CRPS **and** log score |
| F3 | aDOT as a separate axis | Add aDOT to a volume-only yardage model | ΔCRPS not distinguishable from zero with date+team clustering |
| F4 | catch-rate decomposition | `P(catchable\|aDOT, player)` × `P(catch\|catchable)` vs a single shrunk catch rate | the two-factor form does not improve out-of-sample log score |
| F5 | TD rate, position-specific k | Out-of-sample TD prediction: WR k=1422 / TE k=52 vs a single pooled k=137 vs league-rate-only | position-specific k does not beat pooled k — then use pooled, and if pooled does not beat league-rate-only, **drop the player TD term entirely** |
| F6 | red-zone deviation | Hierarchical shrunk deviation vs overall target share alone | no improvement — then §5's conclusion stands and the component is REJECTED |
| F7 | NGS separation | Fit with and without, on the 29.4%-covered subset **and** on the full set with missingness indicator | the effect is present only on the covered subset — that is confounding with volume, not signal |

### 6.4 Three things the layer must carry from day one

`DERIVED` from `CLAUDE.md` and the grounding brief, applied to what I measured:

1. **Full joint draws, not percentiles.** F2/F4 are scored on CRPS and log
   score. MLB stored nine percentiles and can score neither.
2. **Clustered SEs, refused if naive.** A receiver's targets, yards and TDs in
   one game are one draw, and the four markets on that player-game move
   together. Every interval in this document that could be clustered was
   (§3.2 clusters on player); §2.2 bootstraps players, which is the relevant
   cluster for a season-level split-half but is *not* sufficient for game-level
   scoring, where date and team clustering is required.
3. **Quarantine the market columns at ingest.** `play_by_play` ships
   `spread_line`, `total_line`, `vegas_wp`, `vegas_wpa`, `vegas_home_wp`. My
   `extract_pbp.py` selected 29 columns and touched none of them, but that is
   discipline, not enforcement. `DERIVED` — a receiver opportunity model has a
   specific reason to care: game script drives dropback volume, `vegas_wp` is a
   near-perfect game-script summary, and it is the single most tempting leak in
   this dataset.

### 6.5 Power — the binding constraint, restated for receivers

`VERIFIED` — 2024 REG gives 272 games, 544 team-games, 4,128 WR/TE player-games
with a pass snap, 4,255 player-games with a target.

`DERIVED` — 4,128 player-games looks large next to MLB's 251 games, and is not.
They cluster into 544 team-games and 272 games; the grounding brief's measured
threefold clustering inflation on MLB props is a *lower* bound here, since a
receiver's targets are drawn from a fixed team total (target shares within a
team-game sum to 1 by construction — a hard negative dependency, not merely a
correlation). Any confirmatory receiver claim should be powered on **team-games
(544 per season)**, not player-games, until the clustering is measured directly.
That measurement is not in this document and should be done before any
confirmatory ticket is written.

---

## 7. Corrections and additions to the grounding brief

`VERIFIED` — one correction, and it matters because the brief records it as an
absence:

> The brief lists `nextgen_stats/ngs_2024_receiving.csv` and
> `nextgen_stats/ngs_receiving.csv` as **404**, under a heading warning not to
> assume absence without trying variants.

The variants exist:

```
curl -sS -o /dev/null -w "%{http_code} %{size_download}\n" -L \
  "https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/ngs_receiving.csv.gz"
# 200 981431
```

| Path | HTTP | bytes |
|---|---|---|
| `nextgen_stats/ngs_receiving.csv.gz` | **200** | 981,431 (2,821,416 gunzipped) |
| `nextgen_stats/ngs_receiving.parquet` | **200** | 1,118,797 |
| `nextgen_stats/ngs_2024_receiving.csv.gz` | 200 | 651 — a stub, not usable |
| `nextgen_stats/ngs_2024_receiving.rds` | 200 | 924 — a stub, not usable |
| `pfr_advstats/advstats_week_rec_2024.csv` | **200** | 388,683 |
| `ngs_data/ngs_2024_receiving.csv` | 404 | |
| `pfr_advstats/advstats_season_rec_2024.csv` | 404 | |

`VERIFIED` — the working file is the **all-seasons, un-suffixed, `.csv.gz`**
form. It contains **2016–2025, 10 seasons**, weekly plus `week == 0` season rows,
with `avg_cushion`, `avg_separation`, `avg_intended_air_yards`,
`avg_yac_above_expectation` — none of which is derivable from pbp or
participation. It is 981 KB. I downloaded it and
`pfr_advstats/advstats_week_rec_2024.csv` (389 KB); total 1.4 MB, well inside the
"small files fine" allowance. No pbp or participation season was re-downloaded.

`DERIVED` — the operational lesson is the brief's own: the extension was wrong,
not the dataset. A 404 on one spelling is not evidence of absence, and this one
cost the project the only separation/cushion source in the stack.

---

## 8. What I could not check, and what I would hand to the networked agent

`VERIFIED` — these are gaps in this document, not conclusions.

1. **No ground-truth routes run.** F1 cannot be run from here. Needed: any
   per-player routes-run source for ≥2 weeks of 2024, to calibrate the
   `pass_snaps` proxy by position. Until then the proxy's error is unmeasured.
2. **Only 2024 was available for the play-level work.** Every split-half number
   in §2 is one season. The year-to-year table in §3.2 uses 9 transitions but
   only NGS's qualified population and NGS's column set. `pbp_participation`
   exists for 2016, 2018, 2020–2025 (brief, VERIFIED there), so a multi-season
   RPR/TPRR persistence study is possible and is the obvious next measurement.
3. **The NGS selection rule is uncharacterised.** Covered player-weeks have
   min 5 targets; uncovered ones reach 11. I could not determine the rule.
4. **Slot/wide.** Absent here, believed available from paid sources
   (`UNVERIFIED-RECALL`). Someone should establish whether it is obtainable at
   all before any design assumes it.
5. **The 111 residual receiving yards and 1 TD** in the §1.4 reconciliation are
   believed to be laterals. Not confirmed.
6. **Direct measurement of within-team-game clustering for receiver markets.**
   §6.5 argues it is worse than MLB's threefold; it does not measure it.

---

## 9. The four claims a reader should take away

1. `VERIFIED` — **`participation.route` cannot produce routes run.** It is one
   scalar per play, the targeted receiver's route. The usable primitive is
   `offense_players` on dropbacks, which has **zero missingness** (17,013/17,013
   targets on the field list) and reconciles to official receptions **exactly**
   (11,629 = 11,629).
2. `VERIFIED` — **opportunity is stable and efficiency is not.** Route
   participation r = 0.948 (k = 4.3), target share 0.915 (k = 18.4), air yards
   share 0.887, TPRR 0.746 (k = 43.5); catch rate 0.300, yards per target 0.253,
   TD per target 0.167.
3. `VERIFIED` + `DERIVED` — **TD rate needs near-total regression, and the
   naive version actively loses.** k = 137 targets for WR+TE and 1,422 for WR
   alone; year-to-year r = 0.143 [0.061, 0.218] on 760 player-clustered pairs;
   and predicting half-B TDs from a player's own half-A TD rate has RMSE 1.771
   against 1.269 for ignoring the player entirely. The same holds for receiving
   yards (71.73 vs 58.05).
4. `VERIFIED` + `DERIVED` — **a distinct red-zone role is not identifiable in
   one season.** Partial r = 0.126 once overall target share is controlled, and
   overall target share predicts next-half red-zone share (0.732) better than
   red-zone share predicts itself (0.617). Median receiver: 7 red-zone targets a
   season.
