# WS06 — Audit of every published confidence / role-certainty field

**CODE CHANGED: NO.** Nothing outside
`nfl/research/parallel_pass/ws06/` was written. No score was recomputed into
any board, no existing file was edited, and the suite was not run.

Repo `/home/user/nfl`, HEAD `57d38ad`. Interpreter `python3.12`.
Evidence run: `nfl/research/live/2026_01_DAL_NYG/FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec/`
(game `2026_01_DAL_NYG`, 8,000 draws, draw digest
`c3347111c976adcce3bec731a5f546f7faaa583cdc9d2ef0e6a2254d86a16ea0`,
36 board players). Every player was addressed by `gsis_id` through
`Forecast.row_index()`, which reads the artifact's own `draws_ref.row`
(`nfl/product/distributions.py:94-100`). No row was taken positionally.

---

## 1. The complete inventory of published confidence-like fields

Grepping `confidence|role_certainty|distribution_width` across `nfl/` outside
tests returns hits in exactly three product modules. `daily_board.py` has one
hit and it is a **comment** (`nfl/product/daily_board.py:63`) about correlation
grouping — it computes and publishes no confidence field of its own, and does
not carry the board's confidence forward into the slate artifact.

| # | Field | Produced at | Reaches a board at | Numeric? |
|---|---|---|---|---|
| 1 | `confidence.score` | `confidence.py:104-105` | `render.py:62-63` (per-player `_conf 0.XX_`), `render.py:202`, `render.py:215` | yes, [0,1] |
| 2 | `confidence.parts.input_completeness` | `confidence.py:78` | `render.py:199-200` (reason text) | yes, {0.0, 0.6, 1.0} |
| 3 | `confidence.parts.role_certainty` | `confidence.py:82` via `_role()` `:121-147` | `render.py:199-200` | yes, [0,1] |
| 4 | `confidence.parts.distribution_width` | `confidence.py:88` via `_score_width()` `:62-66` | `render.py:209-215` (its own board section) | yes, [0,1] |
| 5 | `confidence.parts.status_certainty` | `confidence.py:93` via `_status()` `:150-166` | `render.py:199-200` | yes, table lookup |
| 6 | `confidence.parts.layer_completeness` | `confidence.py:98` via `_layers()` `:169-187` | `render.py:199-200` | yes, [0,1] |
| 7 | `confidence_board.highest_confidence` (ordering) | `confidence.py:193,197` | `render.py:190-203` | ranking |
| 8 | `confidence_board.widest_uncertainty` (ordering) | `confidence.py:201-205` | `render.py:204-216` | ranking |
| 9 | player sort order within position | `board.py:212-214` | every position table in `render.py:136-139` | ranking |
| 10 | `opportunity_share[*].share_of_game_pool` | `board.py:244-261` | `render.py:58-60` (`_share: carries 25.0%_`) | yes, [0,1] |
| 11 | "Status confidence" column header | `render.py:126` | readiness table | **no** — categorical |

Fields 1-9 all originate in `nfl/product/confidence.py`. Field 10 is a second,
independent share computation in `board.py` that shares field 3's denominator
bug but **not** its docstring error — `board.py:260` names it
`share_of_game_pool` and its `basis` string says "the game-wide pool", which is
accurate. Field 11 is a naming collision only: it prints a categorical
readiness state (`READY`, `INJURY_REPORT_STALE`, …), never a number.

---

## 2. What "confidence" currently means, mathematically

For player *i* at position *p*, with primary metric *m(p)* and draw vector
**x**_i ∈ ℝ^8000:

```
score_i = (1/5) · [ C_inputs + R_i + W_i + S_team(i) + L_p ]
```

`confidence.py:104`: `total = sum(WEIGHTS[d] * parts[d] for d in DIMENSIONS)`
with `WEIGHTS = {d: 1.0/5}` (`:27`). Term by term:

**C_inputs** — `confidence.py:78`:
`inputs = 1.0 if len(caps) >= 5 else (0.6 if caps else 0.0)`.
A count of `source_captures` on the artifact. **Identical for every player in a
run.** Measured: 1.0 for all 36.

**S_team** — `confidence.py:150-166`: a 7-entry lookup on the team's readiness
string. **Identical for every player on a team.** Measured: 0.85 for all 36.

**L_p** — `confidence.py:169-187`:
`0.5·(|got|/|want|) + 0.5·(n_modelled/|declared metrics|)`. A property of the
*position*, not the player. **Identical for every player at a position.**
Measured: QB 0.8636, RB/WR/TE 0.75.

**R_i (role_certainty)** — `confidence.py:121-147`. For a QB:
```python
v   = fc.vector('qb', 'db', gsis_id)
tot = fc.arrays.get('qb__db')
sh  = float(v.mean()) / max(float(tot.sum(0).mean()), 1e-9)     # :127
return (min(1.0, sh / 0.8), ...)                                # :128
```
For a skill player the same shape with divisor `0.25` (`:146`). So
```
R_i = min(1, E[x_i] / (κ_p · Σ_j E[x_j]))      κ_QB = 0.8, κ_skill = 0.25
```
where *j* ranges over **every row of the array**, which spans both teams
(section 3). This is a ratio of two **means**. It contains no variance, no
quantile, no per-draw quantity, and no measure of how uncertain the share is.

**W_i (distribution_width)** — `confidence.py:34-66`:
```python
iqr = P75(x) - P25(x)
if iqr <= 0: return None                 # -> DEGENERATE, scores 0.0
d = iqr / P50(x)  if P50(x) > 0  else  iqr / mean(x)
W = max(0, min(1, 1 - d/1.5))
```

**Therefore, stated precisely:** the published `confidence` score is

> a per-position affine function of one quantity — the player's mean share of a
> game-wide opportunity pool — plus one robust relative-spread term that is
> floored at zero for 21 of 36 players, plus a constant.

Three of the five dimensions carry **no player-level information at all**.
Measured constant floors in this run: QB **0.5427**, RB/WR/TE **0.5200**. The
observed score spans were QB 0.2126, RB 0.2706, WR 0.1680, TE 0.1506. So
roughly **70-78% of every published confidence number is a constant**, and the
remaining variation is dominated by share magnitude.

---

## 3. Finding table

| ID | Finding | Verdict | Evidence |
|---|---|---|---|
| F1 | `_role()`'s docstring says "Share of his own team's opportunity" but `tot.sum(0)` spans BOTH teams | **CONFIRMED** | `confidence.py:122` docstring vs `:127`/`:143`. `qb__db` is shape (6, 8000) = 3 DAL QBs + 3 NYG QBs. DAL rows sum to 40.654, NYG to 32.802, `tot.sum(0).mean()` = **73.456** |
| F2 | The *reason strings* are correct even though the docstring is not | **CONFIRMED** | `:129` `"of the game's quarterback dropbacks"`, `:146` `"of the game's {key}"`. The published prose says "game", the docstring says "own team". The defect is that the **scale constants were chosen for the docstring's denominator** (F3) |
| F3 | κ_QB = 0.8 is a team-denominator constant applied to a game denominator | **CONFIRMED** | Jaxson Dart, a clear starter: share of NYG dropbacks **0.8914** → `/0.8` = capped **1.0000**, which is what the constant was evidently built for. Share of the *game* pool **0.3981** → `/0.8` = **0.4976**, his published score |
| F4 | No QB can reach role_certainty 1.0, and the ceiling depends on the OPPONENT | **CONFIRMED** | A QB taking 100% of his team's dropbacks scores at most **0.6918** (DAL) or **0.5582** (NYG) in this run. Both < 1.0. The published ceiling is a property of the game's pace split, not of the player |
| F5 | A player's role score is contaminated by the other team's volume | **CONFIRMED** | Holding Dart's own-team share fixed at 0.8914 and varying DAL dropbacks ×0.70→×1.30 moves his published role score **0.5967 → 0.4267**, a 28% swing caused entirely by Dallas |
| F6 | κ_skill = 0.25 makes the "featured" threshold team-asymmetric | **CONFIRMED** | Reaching role = 1.0 on targets needs **44.1%** of team targets if DAL, **57.7%** if NYG. On carries: **54.9%** (DAL) vs **45.9%** (NYG). Same football role, different published certainty |
| F7 | `role_certainty` measures share MAGNITUDE, not uncertainty about the role | **CONFIRMED** | It is `mean/mean` (`:127`, `:143`). Per-draw share dispersion exists and is ignored: Dak Prescott's per-draw share of DAL dropbacks has **sd 0.4869**, p10 **0.0000**, p90 **1.0000** — maximal role uncertainty — and is scored on its mean alone (0.5417 → 0.3747 after the game denominator) |
| F8 | The published score is POSITIVELY rank-correlated with predictive entropy | **CONFIRMED** (with caveat) | Over the 30 players with a positive-mean primary metric: Spearman(score, entropy) = **+0.847**; Spearman(role_certainty, entropy) = **+0.889**; Spearman(score, mean) = **+0.749**. Caveat: for count metrics entropy and magnitude are confounded (a larger count has larger support), which is itself the point — the score tracks magnitude |
| F9 | The score is essentially unrelated to normalised IQR, the one dimension that is supposed to be about spread | **CONFIRMED** | Spearman(score, IQR/mean) = **−0.023**. Even `distribution_width` itself reaches only **−0.376** against IQR/mean, because of F10 and F11 |
| F10 | `IQR/median` is unstable when zero mass pushes the median toward 0 | **CONFIRMED** | Sam Howell IQR = **237.00**, Dak Prescott IQR = **270.00** — Howell's spread is *smaller* — yet Howell's `IQR/median` is **25.947** against Dak's **1.731**, a 15× difference produced solely by his median landing at 9.13 (P(pyds=0) = 0.487) instead of 156.0 |
| F11 | `distribution_width` is floored at 0 for the majority of players, destroying its ordering | **CONFIRMED** | 21 of 36 players score exactly 0.0 (11 DEGENERATE, 10 saturated at `IQR/median ≥ 1.5`). **Zero players** score 1.0. Within the floored 21 the dimension carries no information |
| F12 | The rushing denominator is not the game's carries either — it is the sum of the modelled rushing rows | **CONFIRMED** | `rushing__carries` rows sum to **36.939**; the model's own `team_volume/team_carries` game total is **59.706** (the 22.8-carry gap is QB rushing, in a different layer). Javonte Williams is published as **"25% of the game's carries"**; against the model's own team-volume pool he is **15.5%**, and of his own team **32.8%**. Three denominators, three numbers, one label |
| F13 | A degenerate all-zero distribution still publishes a mid-range confidence score | **CONFIRMED** | Joe Milton III, P(dropbacks = 0) = **1.0000** in all 8,000 draws, role 0.0000, width 0.0000, publishes **score 0.5427** — above eight real WR/TE on the same board (e.g. Darius Slayton 0.5230, Camden Brown 0.5200). The constant floor (§2) is doing this |
| F14 | Depth-chart inversion at the top of the board | **CONFIRMED** | Tyrone Tracy Jr. (depth chart **RB3**) publishes **0.7906**, the highest score of any player in the game, above Cam Skattebo (**RB1**, 0.7741). Driven entirely by role 0.8637 vs 0.7896, i.e. share magnitude |
| F15 | Degeneracy *is* correctly caught and is not scored as precision | **FALSIFIED as a defect** — the guard works | `dispersion()` returns `None` on `iqr <= 0` (`:49-50`) and `_score_width(None)` returns 0.0 (`:63-64`); `board()` excludes DEGENERATE rows from `widest_uncertainty` (`:201-205`). Verified on the 11 degenerate players. The regression described in the `:38-45` docstring does not recur |
| F16 | `_primary()` ignores the position argument it is passed | **PARTIAL** | `confidence.py:113-118` iterates `qb → rushing → receiving` and never reads `position`. In this run no player is mis-assigned (layer sets seen: `('qb',)`, `('receiving',)`, `('receiving','rushing')`). A WR or TE carrying a rushing layer would be scored on `rushing/carries`. `_role()` at `:133-135` *does* branch on position; `_primary()` does not. Latent, not triggered here |
| F17 | The QB branch takes the denominator from the raw array, not from mapped players | **PARTIAL** | `:126` `fc.arrays.get('qb__db')` sums all rows including any with no `distributions` entry. In this run all 6 rows map to board players, so no contamination is observable. The skill branch (`:141`) has the same shape |
| F18 | Whether the game denominator was a deliberate design choice or a slip | **UNRESOLVED** | `board.py:260-261` names its parallel quantity `share_of_game_pool` with an accurate `basis` string, which reads deliberate; `confidence.py:122` says "his own team" and the κ constants only make sense against a team pool, which reads accidental. Both are in the tree at HEAD and nothing adjudicates them. Not resolvable from code alone |
| F19 | Provenance of κ_QB = 0.8 and κ_skill = 0.25 | **UNRESOLVED** | `:146` carries a prose justification ("A featured back or a WR1 sits near 0.25 of his game's pool") but no estimate, source, derivation or prior. Under CLAUDE.md rule 2 these are silent constants. Whether 0.25 was ever measured is not determinable from the repository |
| F20 | `daily_board.py` publishes a confidence-like field | **FALSIFIED** | Its single match is the comment at `:63`. It computes no confidence score and does not propagate the board's |

---

## 4. Pathological examples

All values computed from the stored draws in run `4b186a21b83a49ec`, addressed
by `gsis_id`. "Published" columns are read from `board.json`, not recomputed.

### 4a. Primary-metric distribution vs the published score

| Player (gsis_id) | Pos | Primary | **Published score** | role | width | mean | IQR/med | CV | w80/mean | **P(0)** | H_norm | Bimod. coef | mid-third mass |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Jaxson Dart `00-0040691` | QB | qb/pyds | **0.7553** | 0.4976 | 0.5652 | 161.54 | 0.652 | 0.510 | 1.300 | 0.070 | 0.918 | 0.326 | 0.485 |
| Dak Prescott `00-0033077` | QB | qb/pyds | **0.6177** | 0.3747 | 0.0000 | 147.99 | 1.731 | 0.991 | 2.329 | **0.427** | 0.651 | **0.622** | **0.242** |
| Sam Howell `00-0037077` | QB | qb/pyds | **0.6061** | 0.3171 | 0.0000 | 118.32 | **25.947** | 1.161 | 2.662 | **0.487** | 0.600 | **0.677** | **0.202** |
| Jake Haener `00-0038998` | QB | qb/pyds | **0.5462** | 0.0174 | 0.0000 | 5.54 | 0.000 (degen) | 2.834 | 3.197 | **0.784** | 0.291 | 0.628 | 0.033 |
| Joe Milton III `00-0039398` | QB | qb/pyds | **0.5427** | 0.0000 | 0.0000 | 0.00 | degen | n/a | n/a | **1.000** | 0.000 | — | 1.000 |
| Javonte Williams `00-0036997` | RB | rushing/carries | **0.7200** | **1.0000** | 0.0000 | 9.24 | 1.543 | 0.866 | 2.119 | 0.337 | 0.723 | 0.478 | 0.341 |
| Emari Demercado `00-0038705` | RB | rushing/carries | **0.6250** | 0.5249 | 0.0000 | 4.85 | 2.921 | 1.350 | 3.063 | 0.433 | 0.640 | 0.672 | 0.149 |
| Hunter Luepke `00-0038738` | RB | rushing/carries | **0.6288** | 0.2969 | 0.2472 | 2.74 | 1.129 | 1.872 | 3.263 | 0.526 | 0.528 | 0.779 | 0.085 |
| Israel Abanikanda `00-0038389` | RB | rushing/carries | **0.5200** | 0.0000 | 0.0000 | 0.00 | degen | n/a | n/a | **1.000** | 0.000 | — | 1.000 |
| CeeDee Lamb `00-0036358` | WR | receiving/targets | **0.6880** | 0.5067 | 0.3333 | 7.64 | 1.000 | 0.681 | 1.832 | **0.129** | 0.796 | 0.326 | 0.443 |
| Cam Skattebo `00-0040715` | RB | rushing/carries | **0.7741** | 0.7896 | 0.4809 | 7.29 | 0.779 | 0.633 | 1.435 | 0.045 | 0.764 | 0.423 | 0.411 |
| Tyrone Tracy Jr. `00-0039384` | RB | rushing/carries | **0.7906** | 0.8637 | 0.4895 | 7.98 | 0.766 | 0.621 | 1.771 | 0.107 | 0.791 | 0.317 | 0.463 |

Definitions: `w80/mean` = (P90−P10)/mean. `H_norm` = Shannon entropy of the
draws rounded to integer, over log(number of distinct values). Bimodality
coefficient = (skew² + 1) / (excess kurt + 3(n−1)²/((n−2)(n−3))); > 0.555
is the conventional bimodality threshold. "mid-third mass" = fraction of draws
in the middle third of [P5, P95]; low values indicate mass at the extremes.

**What the table says.**

- **Dart vs Dak.** Dart's published score is 0.1376 higher. Every uncertainty
  measure agrees Dart is the cleaner forecast (P(0) 0.070 vs 0.427, CV 0.51 vs
  0.99, BC 0.326 vs 0.622, mid-third 0.485 vs 0.242). So the *direction* is
  right — but obtained for the wrong reason: Dart gains 0.1229 of that gap from
  `role_certainty`, a share-magnitude term, and the width term separates them
  only because Dak is floored.
- **Dak vs Haener.** Dak is a genuine starter in ~57% of worlds and Haener is a
  third-stringer with P(0) = 0.784. The published gap is **0.0715** — smaller
  than the gap between Dart and Dak. Nothing in the score records that Haener's
  distribution is 78% zero mass.
- **Howell's IQR/median = 25.947** is the instability of F10 in the open. His
  *absolute* IQR (237) is smaller than Dak's (270). Both are floored at
  width 0.0, so the pathology is masked in the published score here; it would
  not be masked in a run where one of them landed just below 1.5.
- **Dak/Howell is a genuine two-regime mixture** and the score has no
  representation of it: corr(Dak dropbacks, Howell dropbacks) = **−0.924**,
  corr on passing yards **−0.827**. Dak's dropbacks are 0 in 42.7% of draws and
  ≥20 in 54.1%; his `qb/pyds` quantiles are **[P1…P25 = 0, P50 = 156, P75 = 270,
  P90 = 345]** — a point mass at zero and a broad starter mode with almost
  nothing between. Bimodality coefficient 0.622 and mid-third mass 0.242 both
  flag it. The published fields flag nothing: Dak reads as an ordinary
  mid-table 0.6177.
- **CeeDee Lamb** is the WR1 zero-mass case: P(targets = 0) = **0.129**, close
  to the 0.13 in the brief. `IQR/median` = 1.000 → width 0.3333. The 12.9%
  chance he takes no targets at all is not represented in any published number;
  it is visible only in his `receiving/targets` P1-P10 all being 0.
- **Javonte Williams** is the only player in the game with role = **1.0000**,
  published as "25% of the game's carries" — he is at 0.2500 of the `_role`
  denominator to four decimals, i.e. exactly at the κ = 0.25 cap. Against the
  model's own `team_volume` pool he is 15.5% of the game and 32.8% of his team
  (F12).
- **Milton and Abanikanda** have identically-zero distributions across 8,000
  draws and still publish 0.5427 and 0.5200 — above eight real players.

### 4b. Denominator counterfactual and per-draw share dispersion

| Player | Pos | share of GAME pool (current) | share of OWN TEAM | published role | role if team denominator | per-draw team share: mean | **sd** | p10 | p90 |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Jaxson Dart | QB | 0.3981 | 0.8914 | 0.4976 | **1.0000** | 0.8914 | 0.2731 | 0.5955 | 1.0000 |
| Dak Prescott | QB | 0.2998 | 0.5416 | 0.3747 | 0.6770 | 0.5417 | **0.4869** | 0.0000 | 1.0000 |
| Sam Howell | QB | 0.2537 | 0.4584 | 0.3171 | 0.5730 | 0.4583 | **0.4869** | 0.0000 | 1.0000 |
| Jake Haener | QB | 0.0139 | 0.0311 | 0.0174 | 0.0389 | 0.0311 | 0.0805 | 0.0000 | 0.1036 |
| Javonte Williams | RB | 0.2500 | 0.5489 | **1.0000** | 1.0000 | 0.5080 | 0.3938 | 0.0000 | 1.0000 |
| Emari Demercado | RB | 0.1312 | 0.2881 | 0.5249 | **1.0000** | 0.2667 | 0.3329 | 0.0000 | 1.0000 |
| Hunter Luepke | RB | 0.0742 | 0.1629 | 0.2969 | 0.6518 | 0.1528 | 0.2735 | 0.0000 | 0.4987 |
| CeeDee Lamb | WR | 0.1267 | 0.2234 | 0.5067 | 0.8937 | 0.2231 | 0.1424 | 0.0000 | 0.4000 |
| Cam Skattebo | RB | 0.1974 | 0.3625 | 0.7896 | **1.0000** | 0.3618 | 0.1788 | 0.1726 | 0.5661 |
| Tyrone Tracy Jr. | RB | 0.2159 | 0.3965 | 0.8637 | **1.0000** | 0.3961 | 0.1931 | 0.0000 | 0.6104 |

Two things to read here.

1. **The counterfactual is not a proposed fix and must not be treated as one.**
   Swapping to the team denominator with the κ constants unchanged saturates
   four of ten cases at 1.0 and compresses the top of the board. It is shown
   only to demonstrate that κ = 0.8 and κ = 0.25 are dimensionally matched to a
   team pool (Dart lands exactly on 1.0000) and dimensionally wrong against a
   game pool. The denominator and the constants have to move together.

2. **The per-draw share columns are the uncertainty the current field throws
   away.** Dak and Howell each have a per-draw team dropback share with sd
   **0.4869** and a [p10, p90] of **[0.000, 1.000]** — the model is saying it
   does not know which of them plays, and says so with maximal clarity. The
   published `role_certainty` reads only the mean of that same distribution and
   reports 0.3747 and 0.3171. Contrast Cam Skattebo: mean share 0.3618, sd
   **0.1788**, [0.173, 0.566] — a genuinely settled committee share. His role
   certainty (0.7896) is *twice* Dak's, which is correct in direction but
   arrives there through magnitude, not through the sd column that actually
   distinguishes them.

### 4c. Rank agreement between the published score and candidate measures

Over the 30 board players with a positive-mean primary metric:

| Candidate | Spearman vs `score` | vs `role_certainty` | vs `distribution_width` |
|---|--:|--:|--:|
| mean of primary metric | **+0.749** | +0.727 | +0.201 |
| P(metric = 0) | −0.815 | −0.800 | −0.624 |
| predictive entropy | **+0.847** | **+0.889** | +0.352 |
| bimodality coefficient | −0.694 | −0.724 | −0.572 |
| 80% interval width / mean | −0.379 | −0.371 | −0.281 |
| coefficient of variation | −0.809 | −0.818 | −0.581 |
| IQR / mean | **−0.023** | +0.268 | −0.376 |

Top-8 overlap with the published `highest_confidence` list: P(0) 6/8, CV 6/8,
w80/mean 6/8, bimodality 6/8, **raw entropy 0/8**. The entropy list is
dominated by all-but-degenerate players (Chris Manhertz, Darius Slayton, Jake
Haener) because raw entropy on a near-point-mass is near zero — which is why
entropy needs the zero-mass split of §5, not naive use.

---

## 5. Candidate uncertainty measures and their properties

Listed as candidates. None is recommended for adoption here; adoption is a
separate decision with its own evidence.

| Measure | Definition on stored draws | Scale-free? | Defined at P50 = 0? | Sees zero mass? | Sees bimodality? | Known failure |
|---|---|---|---|---|---|---|
| **P(x = 0)** | `(x <= 0).mean()` | yes (already a probability) | yes | **it is the measure** | no | says nothing about the shape of the non-zero part |
| **CV** = sd/mean | `x.std(ddof=1)/x.mean()` | yes | yes (needs mean > 0) | indirectly (inflates it) | no | undefined at mean 0; unbounded; dominated by the tail for heavy-tailed counts |
| **80% interval width / mean** | `(P90−P10)/mean` | yes | yes | partly (P10 = 0 is visible) | no | collapses to 0 for a near-point-mass, same trap as the current IQR/median |
| **IQR / mean** (not median) | `(P75−P25)/mean` | yes | **yes — this is the F10 fix** | partly | no | still 0 for a degenerate distribution, so the DEGENERATE branch must survive |
| **Conditional dispersion** | CV or IQR/mean computed on `x[x > 0]`, published *beside* P(0) | yes | yes | separated out by construction | no | needs a minimum non-zero sample; two numbers, not one |
| **Normalised predictive entropy** | H(round(x)) / log(#distinct) | partly | yes | yes | yes, weakly | confounded with magnitude for counts (a 300-yard metric has more support than a 7-target one); binning is a choice and choices are constants |
| **Bimodality coefficient** | (skew²+1)/(exkurt + 3(n−1)²/((n−2)(n−3))) | yes | yes | yes (a zero spike is extreme skew) | **it is the measure** | cannot distinguish "bimodal" from "one mode plus a heavy tail"; conventional 0.555 threshold is a published convention, not an estimate from this data |
| **Mid-third mass** | fraction of draws inside the middle third of [P5, P95] | yes | yes | yes | yes, directly | ad hoc; the thirds are an undocumented choice |
| **Per-draw share sd** | `sd(x_i / Σ_{j ∈ own team} x_j)` per draw | yes | yes | yes | **yes — separates Dak (0.487) from Skattebo (0.179)** | requires a team row map, which `_role()` does not currently build |
| **Per-draw share [p10, p90]** | same, quantiles | yes | yes | yes | yes | two numbers |
| **CRPS / log score / PIT** | — | — | — | — | — | **not computable as a confidence field**: they need a realised outcome, so they belong to the postgame ledger, not a pregame board |

The single sharpest separator on this run's pathological set is the pair
**(P(x = 0), per-draw own-team share sd)**. It puts Dak Prescott (0.427,
0.487) and Sam Howell (0.487, 0.487) unambiguously below Cam Skattebo (0.045,
0.179) and Jaxson Dart (0.070, 0.273), which is the ordering the current field
gets right only by accident and gets wrong at the very top (F14).

---

## 6. Evidence ceiling

What this audit can and cannot support.

1. **One game.** Every measured number comes from a single run, 36 players,
   two teams, 8,000 draws. The rank correlations in §4c have n = 30 **players
   in one game**, which are not independent observations: they share a game
   script, a pace draw, and in the simplex layers an explicit allocation
   constraint. No standard error is quoted for them and none should be
   inferred. Whether these orderings hold on a full slate is untested here.
2. **The structural findings do not depend on the sample.** F1, F3, F4, F6,
   F12, F16 and F17 are properties of the code, readable at
   `confidence.py:121-147` and `board.py:244-261`, and the run is only an
   illustration. F5's 28% figure is a specific measurement of a general
   property. F8-F11, F13 and F14 are single-run measurements and are stated as
   such.
3. **No outcome data.** Nothing here tests whether high confidence predicts a
   smaller miss. That is the question the field's own docstring
   (`confidence.py:3-8`) says it is not answering, and it is not answerable
   without a graded postgame ledger. Every statement above is about what the
   field *measures*, never about whether it *works*.
4. **F18 and F19 are not resolvable from the repository.** Whether the game
   denominator was intended, and whether κ = 0.8 / κ = 0.25 were ever estimated,
   require the decision history, not the code.
5. **Existing tests do not cover any of this.** `nfl/tests/test_product_layer.py:143-169`
   pins the *semantics* string, the flat weights, and the degeneracy guard
   (which passes — F15). Nothing in the suite exercises the denominator, the
   scale constants, cross-team mixing, or the median instability. A fix to any
   of F1-F14 would pass the current suite unchanged, which means the suite
   cannot be cited as evidence that the current behaviour is correct.
6. **The suite was not run** (WS06 constraint). No claim here rests on suite state.
7. **Reproduction.** Every number above is regenerable from
   `4b186a21b83a49ec` with `nfl.product.distributions.Forecast` plus numpy, on
   `python3.12`. No probe script was left in the repository; the measured
   values are transcribed into the tables rather than stored as an artifact.

---

**CODE CHANGED: NO.**
