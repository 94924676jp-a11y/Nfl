# WS04 — NON-QB APPEARANCE / ZERO-INFLATION, END TO END

**CODE CHANGED: NO.** No file outside `nfl/research/parallel_pass/ws04/` was
created or modified. Every number below was produced by importing production
modules read-only and by reading sealed artifacts. No sportsbook data was
opened. No realised 2026 outcome was consumed.

**Independence from QB3.** Nothing in this audit uses quarterback participation
logic as an explanation. The non-QB appearance path and the QB allocation path
share no code: `qb_allocation.py` never calls `layers.appearance`, and
`layers.appearance` is reached only from `football_engine.py:314`. Where QB
series appear below they are used only as a contrast, and are labelled.

---

## 1. The finding table

| # | finding | status | code path | data evidence | earliest failure point | repair class |
|---|---|---|---|---|---|---|
| 1 | Non-QB zero mass is an **independent per-player Bernoulli** with **no shared team or game latent** | **CONFIRMED** | `football_engine.py:314` → `layers.py:84 appearance` → `:181 _run_real` → `:222 draws = rng.binomial(1, p, size=m)` per pid in a single loop | Appearance-draw indicator variance equals the Poisson-binomial value in all 3 games and 6 team groups: ratio 0.9678–1.0260, every one inside a 2,000-draw independence interval. Mean pairwise corr +0.00033 / −0.00083 / −0.00049, sd equal to 1/√m to 2 dp | by construction: one RNG, one `binomial` call per player, no latent variate exists | SPECIFICATION_DEFECT (the model has no mechanism for correlated availability) |
| 2 | A weak **negative** same-team coupling exists downstream, from simplex renormalisation, not from a latent | **CONFIRMED** | `layers.py:358 A = (A > 0)` → `p4c_lib.py:107-139 allocate` (simplex) | Metric-zero corr, same team: mean −0.00911 / −0.01024 / −0.00938; opposing team −0.00106 / −0.00016 / −0.00465. Sign is negative, i.e. the opposite of a shared availability latent | `p4c_lib.py:137` divides by the group total, so one survivor's gain is another's loss | NOT A DEFECT — declared allocator behaviour |
| 3 | The appearance Bernoulli is the **dominant** zero source for high-share players and a **minor** one for bench players | **CONFIRMED** | `layers.py:222` (appearance) vs `p4c_build.py:281-283 gen_weights` `clip(C + add_pool, 0, 1)` | Share of P(X=0) attributable to appearance: Lamb 0.962, Javonte Williams 0.980, Ja'Marr Chase 0.937, Bijan Robinson 1.032 — but Camden Brown 0.009, Jack Endries 0.008, Nick Muse 0.052, Ko Kieft 0.048 | `C ≈ 0` for players with no prior appeared class share; board `share_of_game_pool = 0.0` and P(targets=0) = 1.0000 exactly | SPECIFICATION_DEFECT (two unreconciled availability channels) |
| 4 | An **officially inactive** player can carry a **near-certain** latent appearance probability before any downstream zeroing | **CONFIRMED** | `appearance_r8.py:358 predict` (no inactives input) → inactives applied only afterwards at `layers.py:236` | TB@CIN, ingested official list: **Jack Endries, INACTIVE, p_app = 0.9920, 3rd highest of 28.** Ke'Shawn Williams, INACTIVE, p_app = 0.5016. The two that were low (McMillan 0.0083, Tucker 0.0033) carry an injury-report **Doubtful**; the two that were high carry no designation | `predict` has no eligibility input at all; the official list reaches the pipeline one layer later | SPECIFICATION_DEFECT (ordering is correct; the latent is uninformed) |
| 5 | **The model does not learn "has historically appeared".** Among listed, non-designated players the history signal is **inverted** | **CONFIRMED (falsifies the hypothesis as posed, in the worse direction)** | `appearance_r7.py:318 featurise` + `appearance_r8.py:263 featurise` | Pooled 82 players: pearson(app_ewma, p_app) = **−0.2381**, spearman −0.2014 (n = 64 listed & no designation). pearson(cm_carried, p_app) = **+0.3683**, spearman +0.4324. prev_appeared = 0 → mean p 0.8502; prev_appeared = 1 → mean p 0.7331 | not the featuriser: see #7 | — (subsumed by #7) |
| 6 | The **training frame itself is correctly signed.** The inversion is not the R7 censoring story | **CONFIRMED** | `appearance_r7.py:134 build_frame` union frame, 59,784 rows | Frame appearance rate by app_ewma: .1436 / .2479 / .4951 / .7898 / **.9041** — monotone and correct. By depth rank: r1 .8547 → rank 18 .2390. `crossed & cm_carried ≥ 13`: **0.3333** (n=48), i.e. low, as it should be. Cold start & listed: 0.5957, **below** the 0.6385 base rate | — | — (this is the control that localises #7) |
| 7 | **The V1 feature block carries the label.** `r['v1'] is not None` is 1 for a training row **iff the player appeared**, and is 1 for **every** player at prediction time | **CONFIRMED — leakage + train/serve skew** | `appearance_r8.py:99-118 _panel_v1_features` (joins only onto panel rows) → `:312 fit` → `:415-424 predict` (populates `v1` for every player from `AM.prospective_feature_rows`) → `:305 featurise` last column `1.0 if r['v1'] is None else 0.0` | Training: v1 **present** n = 53,381, appearance rate **0.7106**; v1 **absent** n = 6,158, appearance rate **0.0000** — zero appearances in 6,158 rows. `v1_present == in_panel` on 99.96% of rows; `not in_panel` rate 0.0000. Serving: v1 present on **30/30, 24/24, 28/28** players. That one binary feature alone scores **AUC 0.6425** against the model's headline in-sample 0.9399 | `_panel_v1_features()` is keyed on the frozen panel, and the frozen panel holds a row for a player-team-week **iff he took a snap** | LEAKAGE (label-determined covariate) — the repair class is DATA/DESIGN, not a coefficient change |
| 8 | Conditioning on v1-present **reconstructs the exact appearance inversion R7 exists to remove** | **CONFIRMED** | as #7 | Week-1 training rows **with v1 present**: `cm_carried ≥ 9` → actual **1.0000** (n=20); `app_ewma` None → actual **1.0000** (n=624); `app_ewma < 0.05` → actual **1.0000** (n=18). Unconditionally those same cells run .3571 / .6575 / .2951 | R7 lifted the `LOOKBACK_CANDIDATE` censoring from the **frame** and then re-imported it through the **V1 join** | LEAKAGE |
| 9 | The fitted model is **well calibrated in-sample and badly miscalibrated at serve**, on the same week-1 slice | **CONFIRMED** | `appearance_r8.py:312 fit` / `:358 predict` | In-sample week-1 rows (n = 4,163): mean predicted **0.5438** vs actual **0.5371**, Brier 0.04745, and every cell agrees (r1 .9122/.9122; unlisted .0301/.0734; cold start .6575/.6542; cm_carried 9+ .3571/.3239). Served 2026 week-1 rows (n = 82): mean p **0.7996**, cold start **0.9920**, cm_carried 9+ **0.9622** | the serve rows differ from training rows in exactly one systematic way — #7 | LEAKAGE (consequence) |
| 10 | **R8's headline mechanism is inert in week 1.** The reliability weight is 0 for every served player | **CONFIRMED** | `appearance_r8.py:256 weight` `n_cur/(n_cur+k)`; `:263 featurise` | `reliability_weight_mean = 0.000000` in all three games; `n_cur = 0` for all 82 players. k = 1.217589 (within 0.139520 / between 0.114588). With w = 0 every `w·x` column is 0 and every `(1−w)` depth column equals R7's own depth dummy | week 1 has no current-season evidence by construction — the module says so and it is honest, but it means R8 ≡ R7 + V1 block here | NOT A DEFECT — scope statement |
| 11 | **Depth listing, not history, is the model** | **CONFIRMED** | `appearance_r7.py:318` rank-bucket block | Counterfactual on the 82 served players, all else held: `rank → None` **−0.6941** mean (median −0.7616, 77/82 moved); `inj_status → Out` **−0.6803**; `v1 → absent` **−0.7968**. Against that: `app_ewma → 0` −0.0853, `app_ewma → 1` +0.0178, `prev_appeared → 0` −0.0550, `prev_appeared → 1` +0.0107. The whole participation-history block spans ≈ 0.10 | — | SPECIFICATION_DEFECT (three near-binary levers, no graded availability) |
| 12 | **Depth rank is coarse and the deep bucket is undifferentiated** | **CONFIRMED** | `appearance_r7.py:320-325` buckets r1/r2/r3/r4plus/unlisted | 66 of 82 served players fall in `r4plus`, which spans charted ranks 4 to 18. Served mean 0.8098 with range 0.0033–0.9969. The frame says rank 4 → .7456, rank 14 → .4530, rank 18 → .2390: information the bucketing discards | bucketing, not the chart | SPECIFICATION_DEFECT |
| 13 | **No pregame eligibility signal reaches this layer.** R5 filters roster *membership*, not gameday availability | **CONFIRMED** | `run_forecast.py:630-648` → `roster_status.py:221 active_pool` | DAL@NYG 178 roster rows → 106 active pool → 30 WR/TE/RB. `active_pool` keeps unknown and unrecognised statuses by design. The vintage the run reads (`weekly_rosters.cef497eaeddef07b.reduced.csv.gz`) carries season/week/team/gsis_id/position and **no status column** | the reduction, upstream of this layer | DATA_GAP |
| 14 | **Depth-vintage (roster source) choice moves the whole board** | **CONFIRMED** | `depth_vintage.py captured` via `appearance_r8.py:379-390` | DAL@NYG at four clocks: 23:12:33Z → n 30, 27 listed, p_mean **0.7585**; 12:00Z 09-12 → n 28, 25 listed, p_mean 0.7264; 09-10 and 09-09 → n 29, 25 listed, p_mean **0.7017**. All four selected the same chosen capture `2026-09-13T12:42:08Z` for the listing itself; the movement is in who is in the frame | point-in-time selection is correct; the sensitivity is real and unreported on the board | REPORTING_GAP |
| 15 | Prior sample size `n_prior` has **essentially no effect**; being a cold start has a large **positive** one | **CONFIRMED** | `appearance_r7.py:340-341` `min(n_prior,20)/20`, `n_prior<4` flag | pearson(n_prior, p_app) = **+0.0291** (n = 64). By bin: cold start (n=12) mean **0.9920**; <20 (n=9) 0.7883; 20–59 (n=22) 0.7406; 60+ (n=39) 0.7762 | #7 — cold start + v1 present is a training cell with a 1.0000 appearance rate | LEAKAGE (consequence) |
| 16 | The `no_history_and_not_depth_listed` refusal is **working and never fired here** | **CONFIRMED** | `appearance_r7.py:309 is_unsupported`; `appearance_r8.py:472` | `n_declined = 0` in all three games. The refused cell in the frame: n = 245, appearance rate **1.0000** — the module's stated reason reproduces exactly | — | NOT A DEFECT |
| 17 | Official-inactive propagation, **where a governing list exists**, works end to end | **CONFIRMED** | `layers.py:236 INA.apply_to_appearance` → `accounting.py` share==0 where appearance==0 → `p4c_lib.py:137` renormalise | TB@CIN post-inactives board: all four inactive skill players show P(X=0) = **1.0000** on their primary metric across 1,000 draws | — | NOT A DEFECT |
| 18 | DAL@NYG has **no governing inactive list**; claims about "officially inactive" players in that game rest on a quarantined screenshot | **CONFIRMED** | `product/daily_board.py:474 official_inactive_ids` reads `INACTIVES_INGESTION.json`, which does not exist for this game | `nfl/research/live/2026_01_DAL_NYG/INACTIVES_DISCOVERY_QUARANTINED.json` is a RotoWire screenshot transcription, `governing: false`, names not resolved to ids. `official_inactive_ids('2026_01_DAL_NYG')` returns the empty set | — | EVIDENCE-QUALITY NOTE |
| 19 | ATL@PIT provides **no test** of the inactive question | **UNRESOLVED (by design, stated rather than glossed)** | — | All 11 ingested ATL/PIT inactives are QB/LB/DB/OL/DL. Zero are WR/TE/RB, so none is in the non-QB frame | — | — |
| 20 | Whether the missing correlation actually costs forecast accuracy | **UNRESOLVED** | — | Arm A consumes no 2026 outcome, so no graded comparison exists. Three games and 82 player-rows cannot settle it either way | — | — |

---

## 2. Zero-indicator correlation matrices

All from the sealed `player_draws.npz`, indexed by `gsis_id` through
`player_draws_manifest.json['layers'][layer]['row_ids']`. No positional
indexing was used anywhere.

### 2a. Summary across every non-QB series

`Z_i = 1[X_i == 0]`, one series per (player, metric), constant series dropped.

| game | draws | series | within-player, across metric | cross-player, same team | cross-player, opposing | 1/√m |
|---|--:|--:|--|--|--|--:|
| DAL@NYG | 8,000 | 138 (114 variable) | mean **+0.5282**, max 1.0000 | mean **−0.0109**, max 0.1785 | mean −0.0012, max 0.0412 | 0.0112 |
| ATL@PIT | 1,000 | — | — | mean −0.0102, max 0.0797 | mean −0.0002, max 0.1175 | 0.0316 |
| TB@CIN | 1,000 | — | — | mean −0.0094, max 0.0957 | mean −0.0047, max 0.0883 | 0.0316 |

Read it in two parts. Within a player, across metrics, the zero indicators are
strongly linked — a player with zero targets has zero receptions and zero
receiving yards, which is arithmetic, not modelling. Across players, the mean
correlation is small, **negative**, and of the size the simplex denominator
predicts. A shared availability latent would show as a **positive** same-team
correlation. It does not appear.

### 2b. Primary-metric excerpt, the eight most-projected players per game

One series per player: `receiving/targets` for WR and TE, `rushing/carries` for
RB. Full matrices are in `prim_<game>.json` alongside this file's working set;
the eight shown are those with the lowest P(X=0).

**DAL@NYG** (8,000 draws, ±0.0112 per cell)

| | Skattebo | Nabers | T.Johnson | Tracy | Lamb | Mooney | Ferguson | Flournoy |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Skattebo | +1.0000 | −0.0036 | +0.0063 | −0.0095 | −0.0117 | −0.0088 | +0.0156 | −0.0071 |
| Nabers | −0.0036 | +1.0000 | −0.0103 | −0.0056 | −0.0073 | −0.0178 | +0.0052 | −0.0095 |
| T.Johnson | +0.0063 | −0.0103 | +1.0000 | −0.0214 | +0.0076 | −0.0193 | +0.0117 | −0.0193 |
| Tracy | −0.0095 | −0.0056 | −0.0214 | +1.0000 | +0.0090 | −0.0058 | +0.0098 | −0.0083 |
| Lamb | −0.0117 | −0.0073 | +0.0076 | +0.0090 | +1.0000 | −0.0039 | +0.0003 | −0.0239 |
| Mooney | −0.0088 | −0.0178 | −0.0193 | −0.0058 | −0.0039 | +1.0000 | −0.0306 | +0.0169 |
| Ferguson | +0.0156 | +0.0052 | +0.0117 | +0.0098 | +0.0003 | −0.0306 | +1.0000 | −0.0175 |
| Flournoy | −0.0071 | −0.0095 | −0.0193 | −0.0083 | −0.0239 | +0.0169 | −0.0175 | +1.0000 |

P(X=0): Skattebo .0452, Nabers .0620, T.Johnson .0859, Tracy .1075, Lamb .1285,
Mooney .1584, Ferguson .1719, Flournoy .1754.

**ATL@PIT** (1,000 draws, ±0.0316 per cell)

| | Pitts | Metcalf | Bijan | Pittman | London | Heidenreich | Dowdle | Freiermuth |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Pitts | +1.0000 | −0.0439 | +0.0203 | +0.0604 | −0.0437 | −0.0151 | −0.0187 | −0.0289 |
| Metcalf | −0.0439 | +1.0000 | −0.0111 | −0.0496 | +0.0175 | +0.0300 | +0.0242 | −0.0145 |
| Bijan | +0.0203 | −0.0111 | +1.0000 | −0.0264 | −0.0385 | +0.0642 | +0.0026 | −0.0552 |
| Pittman | +0.0604 | −0.0496 | −0.0264 | +1.0000 | −0.0058 | +0.0645 | +0.0045 | −0.0627 |
| London | −0.0437 | +0.0175 | −0.0385 | −0.0058 | +1.0000 | −0.0025 | −0.0187 | +0.0198 |
| Heidenreich | −0.0151 | +0.0300 | +0.0642 | +0.0645 | −0.0025 | +1.0000 | −0.0244 | −0.0708 |
| Dowdle | −0.0187 | +0.0242 | +0.0026 | +0.0045 | −0.0187 | −0.0244 | +1.0000 | +0.0036 |
| Freiermuth | −0.0289 | −0.0145 | −0.0552 | −0.0627 | +0.0198 | −0.0708 | +0.0036 | +1.0000 |

**TB@CIN** (1,000 draws, ±0.0316 per cell)

| | Otton | Egbuka | Irving | Godwin | Higgins | Gainwell | Chase | C.Brown |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Otton | +1.0000 | −0.0101 | −0.0254 | +0.0277 | −0.0140 | −0.0157 | −0.0602 | −0.0455 |
| Egbuka | −0.0101 | +1.0000 | −0.0525 | −0.0213 | −0.0030 | −0.0096 | +0.0199 | +0.0180 |
| Irving | −0.0254 | −0.0525 | +1.0000 | +0.0025 | −0.0138 | +0.0763 | +0.0031 | +0.0009 |
| Godwin | +0.0277 | −0.0213 | +0.0025 | +1.0000 | +0.0531 | −0.0464 | −0.0214 | −0.0237 |
| Higgins | −0.0140 | −0.0030 | −0.0138 | +0.0531 | +1.0000 | −0.0475 | −0.0547 | −0.0145 |
| Gainwell | −0.0157 | −0.0096 | +0.0763 | −0.0464 | −0.0475 | −0.0019 | −0.0019 | +0.0039 |
| Chase | −0.0602 | +0.0199 | +0.0031 | −0.0214 | −0.0547 | −0.0019 | +1.0000 | −0.0107 |
| C.Brown | −0.0455 | +0.0180 | +0.0009 | −0.0237 | −0.0145 | +0.0039 | −0.0107 | +1.0000 |

### 2c. Shared latent versus independent Bernoulli — the decisive test

Correlation matrices are noisy at 24–30 series. The sharper test is the
variance of the **count** of non-appearing players per draw. Under independent
Bernoullis it equals `Σ p(1−p)`; under any shared latent it exceeds it. The
appearance draws were regenerated through `layers.appearance` with
`appearance_spec='r8'` at each board's own evidence clock and `inactive_ids=None`.

| game | group | n | Var(observed) | Var(if independent) | ratio | inside the 95% independence band |
|---|---|--:|--:|--:|--:|---|
| DAL@NYG | both | 30 | 3.2715 | 3.2769 | 0.9983 | yes [3.1765, 3.3760] |
| DAL@NYG | DAL | 14 | 2.2411 | 2.2592 | 0.9920 | yes |
| DAL@NYG | NYG | 16 | 1.0172 | 1.0177 | 0.9995 | yes |
| ATL@PIT | both | 24 | 2.7794 | 2.7830 | 0.9987 | yes |
| ATL@PIT | ATL | 11 | 1.4116 | 1.3758 | 1.0260 | yes |
| ATL@PIT | PIT | 13 | 1.3590 | 1.4072 | 0.9657 | yes |
| TB@CIN | both | 28 | 2.0947 | 2.1643 | 0.9678 | yes |
| TB@CIN | TB | 14 | 0.6713 | 0.6650 | 1.0095 | yes |
| TB@CIN | CIN | 14 | 1.4236 | 1.4994 | 0.9495 | yes |

Joint-versus-product, all primary-metric pairs, DAL@NYG (666 pairs, 8,000
draws): mean z = −0.026, sd 4.10 — but that sd is inflated entirely by the QB
pair, which is a different layer. Restricted to non-QB pairs the largest
absolute deviation of an observed joint from the product of its marginals is
**0.0131** (Luepke × Spann-Ford, 0.3053 observed against 0.3183 independent).

**Answer: INDEPENDENT Bernoulli, not a shared latent.** The code says so
(`layers.py:222`, one `rng.binomial` per player and no latent variate anywhere
in the module), and the draws agree to the precision the sample allows. The
consequence is that the engine can and does draw games in which nine of a
team's eleven skill players are absent and two are not, at the product of their
marginals.

---

## 3. Appearance-probability tables

Recomputed through the production path: `roster_status.active_pool` → WR/TE/RB
→ `appearance_r8.predict` at each board's own `observed_before`. Reproduction is
exact — `max |recomputed − predict| = 0.0` on all 82 players, and the
recomputed draws reproduce the sealed boards' P(X=0) through the
decomposition in §4.

Shared fit for all three: k = **1.217589**, in-sample Brier 0.09052, AUC 0.9399,
base rate 0.6371, coefficient sha256 as recorded in each board.
`reliability_weight_mean = 0.000000` in all three (§1, #10).

### 3a. DAL@NYG, `FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec`, clock 2026-09-13T23:12:33Z

n = 30, declined 0, depth-listed 27, p_mean 0.7585, min 0.0133, max 0.9909.

| player | tm | pos | **p_app** | rank | n_prior | prev | cm_carried | app_ewma | state |
|---|---|---|--:|--:|--:|--:|--:|--:|---|
| Camden Brown | DAL | WR | **0.9909** | 18 | **0** | — | 0 | — | NO_HISTORY |
| Malachi Fields | NYG | WR | **0.9909** | 9 | **0** | — | 0 | — | NO_HISTORY |
| Patrick Ricard | NYG | RB | 0.9858 | 1 | 101 | 1 | 0 | 0.941 | KNOWN_HEALTHY |
| Najee Harris | NYG | RB | **0.9755** | 7 | 89 | 0 | **16** | 0.018 | KNOWN_HEALTHY |
| Odell Beckham Jr. | NYG | WR | 0.9684 | 12 | 68 | 0 | 4 | 0.366 | KNOWN_HEALTHY |
| Cam Skattebo | NYG | RB | 0.9646 | 5 | 17 | 0 | 9 | 0.107 | KNOWN_HEALTHY |
| Braxton Berrios | NYG | WR | 0.9634 | 16 | 98 | 0 | 10 | 0.044 | KNOWN_HEALTHY |
| Thomas Fidone II | NYG | TE | 0.9604 | 14 | 17 | 0 | 8 | 0.054 | KNOWN_HEALTHY |
| Theo Johnson | NYG | TE | 0.9594 | 8 | 33 | 0 | 2 | 0.618 | KNOWN_HEALTHY |
| Israel Abanikanda | DAL | RB | **0.9527** | 10 | 27 | 0 | **13** | 0.036 | KNOWN_HEALTHY |
| Malik Nabers | NYG | WR | 0.9488 | 3 | 34 | 0 | **13** | 0.049 | KNOWN_HEALTHY |
| Darnell Mooney | NYG | WR | 0.9283 | 10 | 102 | 1 | 0 | 0.978 | KNOWN_HEALTHY |
| Isaiah Likely | NYG | TE | 0.9252 | 2 | 68 | 1 | 0 | 0.980 | KNOWN_HEALTHY |
| Tyrone Tracy Jr. | NYG | RB | 0.8924 | 11 | 34 | 1 | 0 | 0.977 | KNOWN_HEALTHY |
| CeeDee Lamb | DAL | WR | 0.8764 | 2 | 101 | 1 | 0 | 0.953 | KNOWN_HEALTHY |
| Jake Ferguson | DAL | TE | 0.8726 | 4 | 68 | 1 | 0 | 0.998 | KNOWN_HEALTHY |
| Ryan Flournoy | DAL | WR | 0.8656 | 12 | 34 | 1 | 0 | 0.827 | KNOWN_HEALTHY |
| George Pickens | DAL | WR | 0.7719 | 7 | 72 | 1 | 0 | 0.974 | KNOWN_HEALTHY |
| Brevyn Spann-Ford | DAL | TE | 0.7455 | 9 | 34 | 1 | 0 | 1.000 | KNOWN_HEALTHY |
| Devin Singletary | NYG | RB | 0.7389 | 13 | 108 | 1 | 0 | 0.999 | KNOWN_HEALTHY |
| Hunter Luepke | DAL | RB | 0.6940 | 5 | 51 | 1 | 0 | 0.999 | KNOWN_HEALTHY |
| Jonathan Mingo | DAL | WR | 0.6716 | 16 | 55 | 1 | 0 | 0.753 | KNOWN_HEALTHY |
| **Javonte Williams** | DAL | RB | **0.6701** | 3 | 80 | 0 | 1 | 0.770 | KNOWN_HEALTHY |
| KaVontae Turpin | DAL | WR | 0.6189 | 14 | 68 | 1 | 0 | 0.971 | KNOWN_HEALTHY |
| Emari Demercado | DAL | RB | 0.6128 | 8 | 51 | 1 | 0 | 0.758 | KNOWN_HEALTHY |
| Dalen Cambre | NYG | WR | 0.5103 | 15 | 7 | 1 | 0 | 0.488 | KNOWN_HEALTHY |
| Luke Schoonmaker | DAL | TE | 0.4595 | 11 | 51 | 1 | 0 | 1.000 | KNOWN_HEALTHY |
| Parris Campbell | DAL | WR | 0.1584 | — | 70 | 0 | 5 | 0.124 | UNKNOWN_STATUS |
| Darius Slayton | NYG | WR | 0.0677 | — | 101 | 1 | 0 | 0.911 | UNKNOWN_STATUS |
| Chris Manhertz | NYG | TE | 0.0133 | — | 112 | 1 | 0 | 0.974 | UNKNOWN_STATUS |

Read the bottom three rows against the top eleven. Slayton and Manhertz have
appeared in ~97% and ~91% of their recent games and are rated 0.068 and 0.013,
because they are off today's chart. Harris, Abanikanda and Nabers have missed
13–16 straight and are rated 0.95–0.98, because they are on it. The chart is
the model.

### 3b. ATL@PIT, `pre_inactives_V1_CANDIDATE_R8/f67d72ab0701d211`, clock 2026-09-13T15:46:51Z

n = 24, declined 0, all 24 depth-listed, p_mean 0.8252, min 0.4703, max 0.9954.

| player | tm | pos | **p_app** | rank | n_prior | cm_carried | app_ewma |
|---|---|---|--:|--:|--:|--:|--:|
| Zachariah Branch | ATL | WR | **0.9954** | 14 | **0** | 0 | — |
| Riley Nowakowski | PIT | TE | **0.9920** | 5 | **0** | 0 | — |
| Kaden Wetjen | PIT | WR | **0.9909** | 17 | **0** | 0 | — |
| Germie Bernard | PIT | WR | **0.9909** | 14 | **0** | 0 | — |
| Eli Heidenreich | PIT | RB | **0.9908** | 13 | **0** | 0 | — |
| Kyle Pitts | ATL | TE | 0.9815 | 2 | 83 | 0 | 1.000 |
| Nick Muse | ATL | TE | 0.9635 | 13 | 33 | 4 | 0.168 |
| DK Metcalf | PIT | WR | 0.9567 | 2 | 105 | 2 | 0.606 |
| Michael Pittman | PIT | WR | 0.9477 | 8 | 101 | 0 | 0.999 |
| Bijan Robinson | ATL | RB | 0.9319 | 4 | 51 | 0 | 1.000 |
| Jahan Dotson | ATL | WR | 0.9158 | 6 | 72 | 0 | 1.000 |
| Pat Freiermuth | PIT | TE | 0.9061 | 3 | 84 | 0 | 1.000 |
| Drake London | ATL | WR | 0.9038 | 3 | 68 | 0 | 0.678 |
| Rico Dowdle | PIT | RB | 0.8422 | 7 | 81 | 0 | 0.977 |
| Austin Hooper | ATL | TE | 0.8033 | 9 | 113 | 0 | 0.948 |
| Chris Blair | ATL | WR | 0.7760 | 16 | 18 | 2 | 0.300 |
| Jaylen Warren | PIT | RB | 0.7731 | 4 | 68 | 0 | 0.989 |
| Roman Wilson | PIT | WR | 0.7142 | 11 | 25 | 1 | 0.462 |
| Brian Robinson | ATL | RB | 0.6337 | 7 | 68 | 0 | 0.976 |
| Robert Tonyan | PIT | TE | 0.6301 | 10 | 95 | 0 | 0.589 |
| Ben Skowronek | PIT | WR | 0.6271 | 16 | 84 | 0 | 0.598 |
| Darnell Washington | PIT | TE | 0.5773 | 9 | 51 | 1 | 0.794 |
| Charlie Woerner | ATL | TE | **0.4906** | 5 | 105 | 0 | **0.999** |
| Olamide Zaccheaus | ATL | WR | **0.4703** | 11 | 112 | 0 | 0.813 |

The five cold starts occupy the top five places, above every established
starter in the game.

### 3c. TB@CIN, `post_inactives_V1_CANDIDATE_R8/e92b9e19466d27bd`, clock 2026-09-13T16:16:15.935964Z

n = 28, declined 0, all 28 depth-listed, p_mean 0.8216, min 0.0033, max 0.9969.
**INA** marks a player on the ingested official inactive list
(`INACTIVES_INGESTION.json`, 14 names, 4 of them WR/TE/RB).

| player | tm | pos | **p_app (latent, pre-zeroing)** | rank | n_prior | cm_carried | injury | official |
|---|---|---|--:|--:|--:|--:|---|---|
| Ted Hurst III | TB | WR | 0.9969 | 13 | 0 | 0 | — | |
| Bauer Sharp | TB | TE | 0.9920 | 14 | 0 | 0 | — | |
| **Jack Endries** | CIN | TE | **0.9920** | 13 | 0 | 0 | — | **INA** |
| Dohnte Meyers | CIN | WR | 0.9909 | 15 | 0 | 0 | — | |
| Colbie Young | CIN | WR | 0.9909 | 12 | 0 | 0 | — | |
| Kameron Johnson | TB | WR | 0.9866 | 16 | 28 | 4 | — | |
| Emeka Egbuka | TB | WR | 0.9748 | 4 | 17 | 0 | — | |
| Josh Williams | TB | RB | 0.9717 | 12 | 16 | 8 | — | |
| Cade Otton | TB | TE | 0.9678 | 2 | 68 | 0 | — | |
| Erick All | CIN | TE | **0.9658** | 10 | 30 | **21** | — | |
| Ko Kieft | TB | TE | 0.9646 | 9 | 68 | 14 | — | |
| Mike Gesicki | CIN | TE | 0.9594 | 1 | 109 | 0 | — | |
| Chris Godwin Jr. | TB | WR | 0.9513 | 5 | 95 | 0 | — | |
| Tee Higgins | CIN | WR | 0.9355 | 8 | 100 | 0 | — | |
| Kenny Gainwell | TB | RB | 0.9324 | 6 | 89 | 0 | — | |
| Bucky Irving | TB | RB | 0.9259 | 3 | 34 | 0 | — | |
| Drew Sample | CIN | TE | 0.9060 | 7 | 90 | 0 | — | |
| Chase Brown | CIN | RB | 0.8680 | 4 | 50 | 0 | — | |
| Ja'Marr Chase | CIN | WR | 0.8679 | 3 | 84 | 0 | — | |
| Andrei Iosivas | CIN | WR | 0.8376 | 9 | 51 | 0 | — | |
| Tez Johnson | TB | WR | 0.8290 | 15 | 17 | 0 | — | |
| Samaje Perine | CIN | RB | 0.7843 | 6 | 112 | 0 | — | |
| Payne Durham | TB | TE | 0.7085 | 7 | 51 | 0 | — | |
| Tahj Brooks | CIN | RB | 0.6066 | 11 | 17 | 1 | — | |
| Tanner Hudson | CIN | TE | 0.5862 | 14 | 87 | 0 | — | |
| **Ke'Shawn Williams** | CIN | WR | **0.5016** | 16 | 15 | 0 | — | **INA** |
| **Jalen McMillan** | TB | WR | **0.0083** | 11 | 34 | 0 | Doubtful | **INA** |
| **Sean Tucker** | TB | RB | **0.0033** | 10 | 51 | 0 | Doubtful | **INA** |

This is the direct answer to the inactive question. Four officially inactive
skill players. The two carrying an injury-report **Doubtful** are correctly
driven to ~0.005. The two carrying **no designation** are rated **0.9920** and
**0.5016**, and Endries is the third-highest appearance probability in the
game. The official list does zero them afterwards — P(X=0) = 1.0000 for all
four in the sealed draws — but the latent had no way to know.

### 3d. Grouped drivers, pooled over all 82 served players

| grouping | bin | n | mean p_app | median | frame's own rate in that cell |
|---|---|--:|--:|--:|--:|
| depth bucket | r1 | 2 | 0.9726 | 0.9726 | .8547 |
| | r2 | 5 | 0.9415 | 0.9567 | .7267 |
| | r3 | 6 | 0.8704 | 0.9050 | .6973 |
| | r4plus | 66 | 0.8098 | 0.8992 | .6296 |
| | unlisted | 3 | **0.0798** | 0.0677 | .2254 |
| n_prior | 0 (cold start) | 12 | **0.9920** | 0.9909 | **.5957** |
| | <20 | 9 | 0.7883 | 0.8290 | — |
| | 20–59 | 22 | 0.7406 | 0.8516 | — |
| | 60+ | 39 | 0.7762 | 0.8764 | — |
| app_ewma | None | 12 | 0.9920 | — | .5957 |
| | [0, .05) | — | — | — | **.1436** |
| | lowest served quintile | 23 | **0.9432** | 0.9908 | — |
| | highest served quintile | 41 | **0.7625** | 0.8656 | **.9041** |
| cm_carried | 0 | 62 | 0.7832 | 0.8745 | .6281 |
| | 1–2 | 7 | 0.7515 | 0.7142 | .4026 |
| | 3–8 | 6 | 0.8348 | 0.9660 | .5543 |
| | **9+** | 7 | **0.9622** | 0.9646 | **.3333** (13+) |
| injury | Doubtful | 2 | 0.0058 | — | — |
| | Questionable | 1 | 0.9488 | — | — |
| | none | 79 | 0.8178 | 0.9061 | — |
| R7 state | NO_HISTORY | 12 | 0.9920 | 0.9909 | .5957 |
| | KNOWN_HEALTHY | 67 | 0.7973 | 0.8726 | — |
| | UNKNOWN_STATUS | 3 | 0.0798 | 0.0677 | .2450 |

The last column is the point. Wherever the served probability differs sharply
from the frame's own empirical rate for that cell, it differs **upward**, and
it does so exactly in the cells the V1 join cannot populate correctly.

### 3e. Counterfactual sensitivity, one feature at a time, 82 players

Each row holds every other field fixed and re-scores through the same fitted
model. `base` reproduces `predict` to 0.0.

| counterfactual | mean Δp | median Δp | min | max | n moved >0.01 |
|---|--:|--:|--:|--:|--:|
| **`v1` → absent** | **−0.7968** | −0.9040 | −0.9950 | −0.0033 | 80 |
| **`rank` → None (unlisted)** | **−0.6941** | −0.7616 | −0.9432 | 0.0000 | 77 |
| **`inj_status` → Out** | **−0.6803** | −0.7517 | −0.8921 | +0.0136 | 81 |
| `cm_carried` → 16 | **+0.1311** | +0.0739 | 0.0000 | +0.4693 | 57 |
| `rank` → 1 | +0.1483 | +0.0671 | 0.0000 | +0.9375 | 68 |
| `app_ewma` → 0 | −0.0853 | −0.0693 | −0.2202 | −0.0002 | 66 |
| `cm_carried` → 0 | −0.0619 | 0.0000 | −0.4016 | 0.0000 | 20 |
| `prev_appeared` → 0 | −0.0550 | −0.0344 | −0.1508 | 0.0000 | 57 |
| `rank` → 4 | +0.0201 | 0.0000 | −0.2040 | +0.8640 | 15 |
| `inj_status` → none | +0.0198 | 0.0000 | −0.0565 | +0.7734 | 9 |
| `app_ewma` → 1 | +0.0178 | +0.0041 | 0.0000 | +0.1380 | 31 |
| `n_prior` → 0 (make cold start) | +0.0148 | +0.0120 | −0.1023 | +0.1804 | 60 |
| `prev_appeared` → 1 | +0.0107 | 0.0000 | −0.0024 | +0.1377 | 19 |

`cm_carried → 16` **raises** the probability by 0.131 on average and by 0.469 at
the extreme. Every appearance-history feature in the model, taken together,
spans about a tenth of the probability scale. The three levers that matter are
one leaked flag and two binary present/absent facts.

---

## 4. Zero-mass decomposition: what the appearance Bernoulli actually owns

`P(X = 0) ≥ 1 − p_app` by construction, since appearance = 0 forces the metric
to 0. The excess is contributed by the allocator, `W = clip(C + add_pool, 0, 1)`
at `p4c_build.py:281-283` (system C; `par['q_zero']` is **not** on this path —
`gen_weights` returns at the C branch before reaching it) and by integer
rounding of a small share.

| game | player (primary metric) | p_app | P(X=0) | from appearance | from allocation | appearance's share |
|---|---|--:|--:|--:|--:|--:|
| DAL@NYG | Javonte Williams (carries) | 0.6701 | 0.3365 | 0.3299 | 0.0066 | **0.980** |
| DAL@NYG | CeeDee Lamb (targets) | 0.8764 | 0.1285 | 0.1236 | 0.0049 | **0.962** |
| DAL@NYG | George Pickens (targets) | 0.7719 | 0.2358 | 0.2281 | 0.0076 | 0.968 |
| DAL@NYG | Malik Nabers (targets) | 0.9488 | 0.0620 | 0.0512 | 0.0108 | 0.826 |
| DAL@NYG | Camden Brown (targets) | 0.9909 | **1.0000** | 0.0091 | 0.9909 | **0.009** |
| DAL@NYG | Najee Harris (carries) | 0.9755 | **1.0000** | 0.0245 | 0.9755 | 0.025 |
| ATL@PIT | Bijan Robinson (carries) | 0.9319 | 0.0660 | 0.0681 | −0.0021 | 1.032 |
| ATL@PIT | Nick Muse (targets) | 0.9635 | 0.6990 | 0.0365 | 0.6625 | 0.052 |
| TB@CIN | Ja'Marr Chase (targets) | 0.8679 | 0.1410 | 0.1321 | 0.0089 | 0.937 |
| TB@CIN | Ko Kieft (targets) | 0.9646 | 0.7410 | 0.0354 | 0.7056 | 0.048 |
| TB@CIN | Jack Endries (targets) | 0.9920 | **1.0000** | 0.0080 | 0.9920 | 0.008 |

(Shares slightly above 1.0 are Monte Carlo noise at 1,000–8,000 draws; the
binomial SE is 0.0056 at 8,000 and 0.0158 at 1,000.)

Two things follow. First, the earlier claim that "the appearance Bernoulli IS
the zero mass" is true for the players who carry real projected volume — for
Lamb, Williams, Chase, Pickens it accounts for 94–98% of the zero mass — and
false for the bench, where 90–99% of the zero mass comes from an allocation
weight of essentially zero. Second, for the cold-start players the two layers
give contradictory answers about the same person: appearance says 0.99 and the
allocator says 0.00. Neither layer is aware of the other's verdict.

---

## 5. Where the defect actually is

The three measurements that localise it, in order.

**(a) The frame is right.** 59,784 union-frame rows. Appearance rate by
`app_ewma`: .1436 / .2479 / .4951 / .7898 / .9041. By depth rank: r1 .8547,
r2 .7267, r3 .6973, r4plus .6296, unlisted .2254; rank 14 .4530, rank 18 .2390.
`crossed & cm_carried ≥ 13`: .3333 on n = 48. Cold start & depth-listed: .5957
against a .6385 base. Every relationship a sensible appearance model needs is
present and correctly signed.

**(b) The fit is right, in-sample.** On the 4,163 week-1 training rows the same
fitted model predicts 0.5438 against an actual 0.5371, Brier 0.04745, and
matches cell by cell: r1 .9122/.9122, unlisted .0301/.0734, cold start
.6575/.6542, `cm_carried ≥ 9` .3571/.3239.

**(c) The serve rows are not the training rows.** On the 82 real week-1 2026
players the same model produces mean 0.7996 — **+0.256** against the training
slice — cold starts at 0.9920 against 0.6542, and `cm_carried ≥ 9` at 0.9622
against 0.3239.

The difference is one field. `_panel_v1_features()` (`appearance_r8.py:99-118`)
joins the V1 block onto rows of the **frozen panel**, and a player has a panel
row for a team-week if and only if he took a snap. Measured:

- v1 **present**: n = 53,381, appearance rate **0.7106**
- v1 **absent**: n = 6,158, appearance rate **0.0000** — not one appearance
- `v1_present == in_panel` on **99.96%** of rows; `not in_panel` rate 0.0000

At prediction time `predict` (`appearance_r8.py:415-424`) populates the block
for **every** player from `AM.prospective_feature_rows`, so the flag is 1 for
30/30, 24/24 and 28/28 players and the cell whose training rate is 0.0000 is
unreachable. The module's own docstring records that leaving the block empty at
serve was a defect and that populating it was the repair; the measurement above
says the repair moved the problem rather than removing it, because the flag
still carries the label **in training**.

That alone is a leaked binary predictor worth **AUC 0.6425** of the model's
headline 0.9399, and it is what makes the R8/R7 in-sample Brier of 0.09052 an
unsafe summary.

And conditioning on it reproduces, exactly, the inversion R7 was built to
eliminate. Week-1 training rows **with v1 present**:

| cell | n | actual appearance rate | model's prediction |
|---|--:|--:|--:|
| `app_ewma` is None (cold start) | 624 | **1.0000** | 0.9935 |
| `app_ewma < 0.05` | 18 | **1.0000** | 0.8859 |
| `cm_carried ≥ 9` | 20 | **1.0000** | 0.8962 |
| `app_ewma ∈ [.95, 1]` | 987 | 0.6778 | 0.6538 |

Unconditionally those same three cells run .6575, .2951 and .3571. "Was absent
for a long time **and** has a panel row" means "came back and played", which is
the `LOOKBACK_CANDIDATE` censoring arriving through a second door. R7 lifted it
from the frame; the V1 join re-imports it as a covariate.

So the served ordering is not a coefficient that needs its sign flipped. It is a
design in which a covariate is a function of the label.

---

## 6. Answers to the questions as posed

**P(appearance) per player for a real game** — §3a/3b/3c, 82 players across
three games, reproducing `predict` exactly.

**P(X = 0) per stat per player** — §4 and the full per-player tables in the
working set; the appearance share ranges from 0.008 to 1.03.

**Zero-indicator correlation matrix** — §2. Cross-player: mean −0.010 same
team, −0.001 opposing, max |r| 0.18 over 13,708 pairs at 8,000 draws.

**Shared latent or independent Bernoulli** — **INDEPENDENT**, proved two ways:
structurally at `layers.py:222` (no latent variate exists) and empirically by
the count-variance test in §2c, ratio 0.9678–1.0260 with every group inside its
independence band.

**Effect of prior sample size** — none: pearson(n_prior, p_app) = +0.0291. The
only n_prior effect is the cold-start jump to 0.9920, which is #7, not a
sample-size effect.

**Effect of depth rank** — dominant but coarse: removing the listing costs
−0.694; moving within the listing costs far less; 66 of 82 players sit in one
bucket spanning ranks 4 to 18, where the frame distinguishes .7456 from .2390.

**Effect of roster source** — the roster vintage supplies membership only (no
status column), and R5 keeps unknown statuses; 178 → 106 → 30 for DAL@NYG. The
depth-chart vintage is the consequential source: across four clocks the frame
size moved 28–30, listed 25–27, and p_mean 0.7017–0.7585.

**Can an officially inactive player carry a high latent appearance
probability** — **yes.** Jack Endries, on the ingested TB@CIN official list,
p_app = 0.9920, third highest of 28. The downstream zeroing does work
(P(X=0) = 1.0000 in the sealed draws), so this is not a board error; it is that
nothing upstream of the list knows anything about gameday eligibility.

**Does the model learn "has historically appeared" rather than "is expected to
play tonight"** — **no, and the truth is worse.** It learns neither. Among
listed, non-designated players the correlation between historical appearance
rate and modelled probability is **−0.238**, and between consecutive missed
games and modelled probability **+0.368**. What it actually reads is (i) whether
a V1 panel row exists, which in training is the label, (ii) whether the player
is on tonight's chart, and (iii) whether he carries an injury designation. The
second and third are genuinely about tonight; the first is about the past
outcome.

---

## 7. Evidence ceiling

- **Three games, 82 non-QB player-rows, week 1 of 2026 only.** Every served
  player has `n_cur = 0`, so R8's reliability-weighted block is identically zero
  and this audit says nothing about weeks 5–18, where that block is the whole
  point of R8. Findings #5, #7, #8, #15 are demonstrated on the `w = 0` slice.
- **No realised outcome was used.** Arm A consumes none, so nothing here is a
  measurement of forecast accuracy. Every accuracy statement is in-sample
  against the training frame, which is a statement about the fit, not about the
  world.
- **The fit diagnostics are in-sample by construction.** `fit(2026)` trains on
  every row with `s < 2026`, so §5(b) is a self-consistency check, not
  validation. The AUC 0.6425 for the leaked flag is likewise in-sample.
- **Correlation precision.** 8,000 draws give ±0.0112 per correlation cell;
  1,000 draws give ±0.0316. With 24–30 series per game the multiple-comparison
  ceiling means individual cells of 0.09–0.13 at n = 1,000 are not evidence of
  anything. The count-variance test in §2c is the one that carries the claim,
  and it is decisive only for *this* draw generator on *these* marginals.
- **ATL@PIT contributes nothing to the inactive question** — all 11 of its
  ingested inactives are non-skill positions. TB@CIN is the only game here with
  a governing skill-position inactive list, so #4 rests on n = 4 players in one
  game. It is a confirmed existence proof, not a rate.
- **DAL@NYG has no governing inactive list at all.** Any statement that Camden
  Brown or Israel Abanikanda was "officially inactive" derives from a
  quarantined third-party screenshot that the repository itself marks
  `governing: false`. Their appearance probabilities (0.9909, 0.9527) are
  measured facts; their inactive status is not a governed one.
- **No causal claim about coefficients.** I did not refit anything and did not
  inspect individual weights. #7 is established by the joint structure of the
  frame and the serve path, not by reading a coefficient's sign.
- **Not replicated across seasons.** The frame cell rates are pooled over
  2021–2025; no forward-chained check was run.

---

## 8. What would settle what remains

1. Refit R8 with the V1 block replaced by a version computed on the **union
   frame** rather than the panel, so `v1 present` stops being the label, and
   compare forward-chained week-1 Brier. Until then the R7-vs-V1 week-bucket
   table in the `appearance_r8` docstring is measured on a design that leaks.
2. Report `n_with_a_depth_listing`, the depth-vintage clock, and the served
   `p_mean` on the board, so a 0.26 gap against the training slice is visible
   without recomputation.
3. Decide whether the appearance layer should carry a shared team-level
   availability term at all. The current answer is "no latent exists", which is
   defensible; what is not defensible is that it was never declared as a choice.
4. Reconcile the two availability channels (#3): a player the appearance layer
   rates at 0.99 and the allocator rates at 0.00 is being described by two
   models that never meet.

---

*Working artifacts for this audit live in the session scratchpad and are not
committed. Every figure above is reproducible from the sealed boards plus
read-only imports of `appearance_r8`, `appearance_r7`, `layers`,
`roster_status`, `participation_prior` and `depth_vintage` at the clocks named.*
