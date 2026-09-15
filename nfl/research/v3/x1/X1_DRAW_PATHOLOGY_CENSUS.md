# X1 — Draw pathology census

**DIAGNOSTIC ONLY. Nothing was repaired. No file outside `nfl/research/v3/x1/` was written.**

`nfl/production/nonqb/layers.py` verified unchanged at start and end:
`481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`.

Machine-readable companion: `X1_CENSUS.json`.

---

## 0. Scope, and a correction to it

The brief says 104 sealed boards. **There are 121.** 116 store `player_draws.npz`;
five more, all under `2026_01_SF_LA/`, store `player_draws.npz.gz` and are missed by
any sweep globbing `*.npz`. All 121 carry `board.json` `pipeline_status == SEALED`.
109 sit under a game directory, 12 under `REPLAY_C1`.

The number 104 has two independent derivations that happen to coincide, which is
probably how it stuck: 116 − 12 REPLAY_C1 = 104, and separately there are exactly
104 **C3-bound team-sides** in the corpus. Neither is the board count.

Row identity came from `player_draws_manifest.json` `layers[<layer>].row_ids`
throughout; nothing is positional.

## 1. Definitions, fixed before looking

**IMPOSSIBLE** — violates an arithmetic identity of the box score or a rule of the
game. Never justified by plausibility.

**SUSPICIOUS** — inside the rules, but outside the support of five seasons of
realised games at the same conditioning count, or structurally degenerate. *A
suspicious cell is not a defect.* A Monte Carlo engine is supposed to produce
extreme draws.

**The yardage bound, derived rather than invented.** A completed forward pass gains
or loses at most 99 yards: the line of scrimmage sits at most on either 1-yard line
and the play ends between the goal lines. So per-completion yardage is bounded to
[−99, +99] and a game total to [−99·cmp, +99·cmp]. That is the only HARD yardage
bound available, it is deliberately loose, and **it does not catch D19.**

> **First correction.** D19 says 16 completions for −32 yards "is not a football
> outcome". Against the only bound the rules supply, it is: −2.0 per completion is
> far inside −99. **D19 is SUSPICIOUS, not impossible**, and I have classified it
> that way. What makes it indefensible is empirical, not logical — see §3.

**The empirical support bound** is the observed min/max of yards-per-completion on
3,787 QB games (2020–2025, `nfl/research/qb2/qb.pkl`), banded by the completion
count that produced it. It is not a threshold chosen to make a number look bad; it
is the same statistic at the same count.

| completions | n games | min ypc | max ypc |
|---|---|---|---|
| 1 | 222 | **−7.000** | 75.000 |
| 2–4 | 180 | **−2.000** | 40.000 |
| 5–9 | 204 | **+4.111** | 27.333 |
| 10–14 | 410 | **+3.462** | 22.091 |
| 15–19 | 846 | **+4.235** | 21.000 |
| 20+ | 1,925 | **+5.125** | 21.200 |

Negative yards-per-completion exists in real football **only at 1–2 completions.**
Across 3,181 games with 5 or more completions, the minimum is +3.462.

---

## 2. The census

### 2.1 Impossible states

Denominators: 990,000 qb cells per metric, 1,924,000 receiving, 516,000 rushing,
270,000 team_volume.

| Check | Layer | Cells | Boards | Rate |
|---|---|---|---|---|
| `cmp == 0` with `pyds != 0` | qb | **18,041** | 50 | 1.822% |
| `cmp > att` | qb | **8,214** | 50 | 0.830% |
| `cmp + int > att` | qb | **9,189** | 50 | 0.928% |
| `ptd > cmp` | qb | **1,113** | 50 | 0.112% |
| `ptd > att` | qb | **30** | 20 | 0.003% |
| `rushing_td > carries` | rushing | **442** | 50 | 0.086% |
| `pyds > 99·cmp` at `cmp ≥ 1` | qb | **2** | 2 | 0.0002% |
| named carries > `team_carries` | cross-layer | **314** | 53 sides | 0.238% |

**Zero in every board, every cell** — negative counts anywhere (qb, receiving,
rushing, team_volume); `att+sacks+scr ≠ db`; `scr > rush_opp`; `rtd > rush_opp`;
`rush_opp == 0` with `ryds != 0`; `receptions > targets`; `receiving_td >
receptions`; `receptions == 0` with yards; any yardage outside ±99 per event in the
receiving layer; `team_rz_carries > team_carries`; and **all three C3 identities**
(completions, passing yards, passing TDs), which bind to 5.7e−14 on all 104 bound
team-sides.

All 18,041 `cmp == 0` cells carry **positive** yards; none is negative. All 442
`rushing_td > carries` cells have `carries > 0`.

### 2.2 The 121 boards split into three families, cleanly

| Family | Boards | Credit function | Impossible per-QB cells |
|---|---|---|---|
| `QB_ONLY` (no receiving layer) | 68 | none — raw `qb_v1` | **0** |
| `C3_OLD_CREDIT` | 50 | `shared_pass.credit_to_passers` | **27,564** |
| `C3_NEW_CREDIT` | 3 | `football_engine.credit_passing_line` | **0** |

This is not a distribution of severity. It is a switch. Every impossible per-QB
cell in the corpus is on a board built by one function, and that function has
already been replaced in the tree.

`nfl/production/nonqb/shared_pass.py:172` `credit_to_passers` splits team
completions multinomially on **attempt share** — sampling a finite pool *with*
replacement — and splits yards on the same attempt share, independent of the
completion draw (`pyds_q = w * team_pyds`, line 189). Nothing constrains the
per-QB result. The team total closes exactly; the per-QB split is not a box score.
Example, board `797eed72f07fbd9b`, ARI `00-0033119` draw 57: `att=4, db=4, cmp=7,
pyds=36.36`.

`nfl/production/nonqb/football_engine.py:84` `credit_passing_line` replaces it:
multivariate hypergeometric over `attempts − interceptions`, then TDs over credited
completions, then yards on the **completion** share — and it asserts `cmp <= att`,
`cmp <= att − int`, `ptd <= cmp` and `cmp == 0 → pyds == 0` on the values it is
about to write (lines 285–300).

### 2.3 Suspicious states

| Check | Cells | Boards | Denominator |
|---|---|---|---|
| `qb/pyds` negative | **2,262** | 67 | 990,000 |
| `qb/ryds` negative | 3,353 | 121 | 990,000 |
| `receiving_yards` negative | 11,479 | 53 | 1,924,000 |
| `qb/pyds` non-integer | 300,841 | 121 | 990,000 (30.4%) |
| `qb/ryds` non-integer | 126,700 | 121 | 990,000 |
| ypc out of historical support at `cmp ≥ 10` | **2,140** | — | 130,422 (1.64%) |
| rows whose middle half of `pyds` draws is identical | 346 | 97 | 906 rows |
| rows whose middle half of `ryds` draws is identical | 493 | 121 | 906 rows |

`draw_coherence.py:47` states 2,261 / 2,821 / 8,213 for the three negative-yardage
counts. Measured now: **2,262 / 3,353 / 11,479**. The docstring is stale rather than
wrong — boards were added after it was written. It is the same failure mode as a
suite count written into a README.

### 2.4 The two most recent DEN@KC boards: **better**, and for a traceable reason

| Board | `cmp>att` | `cmp0 & pyds≠0` | `ptd>cmp` | `rtd>carries` | neg `pyds` |
|---|---|---|---|---|---|
| `f91342d6787a66a1` (R8) | 0 | 0 | 0 | **1** | 0 |
| `96954efc523bd7d3` (R9) | 0 | 0 | 0 | 0 | 0 |
| `d1e2727743c93990` (R9) | 0 | 0 | 0 | 0 | **1** |
| the other 50 C3 boards | 8,214 | 18,041 | 1,113 | 441 | 0 |

`96954efc523bd7d3` is clean on every check in this census. `d1e2727743c93990`
differs by exactly one cell — D19 — and that cell sits on the DEN side, which
`credit_passing_line` never touches because DEN has no receiving layer.

### 2.5 The carry-exceedance claim does not reproduce

The brief states ~149/1000 draws per team, as already known. **It is not in the
sealed corpus.** Source located: `nfl/research/v2/d1/D1_DEN_UNIVERSE.md:175`, which
measured an in-flight D1 research build, not a board under `nfl/research/live/`.

Measured here over 104 team-sides × 1,000 draws = 132,000:

- **314 draws (0.238%)** deal named rushers more carries than `team_volume/team_carries`
- worst excess **0.743 carries**; **zero** draws exceed by a full carry
- D1's "up to 6.12 carries" appears nowhere

And the comparison is int-vs-float: `team_carries` is a continuous level
(non-integrality up to 0.495) while dealt carries are `int16`. A sub-carry excess is
a representation mismatch, not a lost carry.

**A genuine cross-layer divergence does exist**, on the 2 R9 boards: the A1
`rush_category` sum runs *below* `team_carries` by 2.4–2.9 on average and up to
10.2, on 1,702 of 4,000 draws. It never over-allocates. This is the divergence
`draw_coherence.py:591-597` already names — `football_engine._team_carries` returns
the SC1-coupled vector while `run_forecast` seals D1's raw vector. Two layers
answering the same question differently, already declared. Not impossible.

---

## 3. D19 mechanism, traced to a line

### 3.1 The cell, verified

`d1e2727743c93990`, `00-0039732`, draw 885: `att=30, cmp=16, pyds=−32.0`,
`db=33, int=1, ptd=1, sacks=1, scr=2`. Implied **−2.0 yards per completion**.
It is the single minimum of that row; the next lowest value is 0.0.

### 3.2 The generator

**`nfl/research/qb2/qb2_lib.py:306-307`**, reached from production via
`nfl/production/qb_v1.py:235` → `qb2_lib.simulate`:

```python
ypc_d = _mix(rng, r['h_ypc'], po['ypc'], w, m, ew)
PY = CMP * ypc_d
```

`PY` is **not a per-completion yardage draw.** One *game-level* yards-per-completion
ratio is resampled whole — from the QB's own history with probability
`w = h_games/(h_games+K)`, `K = 4.0`, otherwise from the positional pool
(`_mix`, lines 184–196) — and multiplied by a completion count drawn independently.
The ratio carries no record of the completion count that produced it, and is not
weighted by it.

`h_ypc` is built at `qb2_lib.py:80` and the pool at `qb2_lib.py:121`, both as
`pass_yards / completions` per game, with no minimum completion count.

### 3.3 The arithmetic, exactly

The pool has 3,787 entries. **Ten are negative. Every one comes from a 1- or
2-completion game:**

| season | week | team | completions | pass yards | ypc |
|---|---|---|---|---|---|
| 2023 | 13 | CIN | 1 | −7 | −7.0 |
| 2022 | 9 | MIN | 1 | −3 | −3.0 |
| 2022 | 10 | LA | 1 | −3 | −3.0 |
| 2024 | 5 | WAS | 1 | −2 | **−2.0** |
| 2024 | 7 | CAR | 2 | −4 | **−2.0** |
| 2024 | 17 | NE | 1 | −2 | **−2.0** |
| 2025 | 12 | ARI | 1 | −2 | **−2.0** |
| 2023 | 2 | JAX | 1 | −1 | −1.0 |
| 2023 | 14 | CIN | 1 | −1 | −1.0 |
| 2023 | 8 | NYG | 2 | −1 | −0.5 |

**−2.0 × 16 completions = −32.0.** Exactly.

Bo Nix has 34 prior games, `h_ypc` min **+5.0**, zero negatives — so the draw came
from the **pool** branch, not his own history. Rate check:
`P(pool) = 1 − 34/38 = 0.1053`; `P(pool value negative) = 10/3787 = 0.002641`;
product `2.78e−4`; expected **0.278** cells in 1,000 draws; observed 1;
Poisson P(≥1) = 0.243. Entirely consistent.

**The magnitude is manufactured by the multiplication, not drawn.** Conditional on
the pool handing over a negative ratio, the size of the loss is set by the draw's
own completion count, which averages 20.6 for this row.

### 3.4 Proof across the whole corpus, not by plausibility

For all **2,262** negative `qb/pyds` cells I recomputed `pyds/cmp` and matched it
against the exact set of historical ratios:

- ypc exactly equals a **pool** historical game ratio: **2,262**
- ypc from the QB's own history only: **0**
- unmatched: **0**

Only **four distinct values** appear across all 2,262 cells: **−3.0, −2.0, −1.0,
−0.5.** Completion counts range 1 to 38 (median 5); `pyds` ranges −76.0 to −0.5.

### 3.5 The hypothesis in the brief is **rejected**

> *Is the negative tail a symmetric-distribution artifact — a Normal fitted to a
> heavily right-skewed quantity, whose left tail goes where the real distribution
> never goes?*

**No.** No distribution is fitted anywhere on this path. `_mix` is an empirical
resample *with replacement* of realised game-level ratios, so every value it can
emit was observed in a real NFL game. Q7's per-reception skew 2.197 / excess
kurtosis 7.830 describes the **receiving** generator, which is a different path and
is not what produced this cell.

The defect is **scale non-exchangeability**: a ratio estimated at n=1 completion is
applied at n=16 completions with no shrinkage and no denominator weighting. That is
why the empirical support table in §1 is the right evidence and the ±99 bound is not.

### 3.6 D19's blast radius is wrong, and the defect is larger than it says

D19 claims the invariant *"every negative passing-yard cell lives on a run WITHOUT
the shared passing event"* is "now false, by one cell."

**The 2,262 total reproduces exactly. The inference does not.** C3 binds per
**team-side**, not per board. Board `d1e2727743c93990` carries a receiving layer for
**KC only** — 13 KC receivers, 0 DEN. Bo Nix is DEN. Measured per team-side:

- 104 sides are C3-bound (team `qb/pyds` sum equals team `receiving_yards` sum to 5.7e−14)
- 2 sides are not
- **0 of 2,262** negative cells sit on a C3-bound side
- **2,262 of 2,262** sit on a side with no receiving layer

**The invariant holds, exactly, at the level that generates the number.** Board
`d1e2727743c93990` is simply the first in the corpus to carry C3 for one of its two
teams only.

And D19 presents itself as "1 cell in 1,000 draws on ONE board." The same mechanism
produces **156 cells at or below −30 yards** and 2,262 in total. The cell was found
because a fence happened to point at that board, not because it is rare.

### 3.7 The right tail is the larger defect, and nothing points at it

Same generator, opposite direction. Measured over the 520,000 raw `qb_v1` cells:

- `pyds` maximum: **1,587 yards** in a single game
- NFL single-game record: 554 (Van Brocklin, 1951)
- cells above 554: **680** (0.131%); above 700: 192; above 800: 82

At `cmp ≥ 10` (n = 130,422), against the historical support [3.462, 22.091]:

| | cells | rate |
|---|---|---|
| below support | 1,554 | 1.192% |
| above support | 586 | 0.449% |

**2,016 of those 2,140 out-of-support cells (94.2%) trace to a donor game with
exactly ONE completion.** The left tail has 156 cells worse than −30 yards; the
right tail has 680 above the all-time record. By magnitude the right tail is worse.

---

## 4. Downstream effect, quantified

Unit: one QB row on a non-C3 side, 1,000 draws. 490 rows carry a live distribution.
"Contaminated" = ypc outside the §1 historical support at that cell's completion band.

4,935 contaminated cells in total; mean 10.1 per 1,000, **median 2**, max 111;
361 of 490 rows carry at least one.

### 4.1 Shift when contaminated cells are dropped

| statistic | mean shift | median | min | max | rows moving >1 yd |
|---|---|---|---|---|---|
| mean (yards) | −0.453 | **0.000** | −13.857 | +6.456 | 63 |
| P10 | +0.566 | **0.000** | −0.048 | +36.052 | 29 |
| P50 | −0.031 | **0.000** | −5.401 | +11.110 | 89 |
| P90 | −1.006 | **0.000** | −26.821 | +8.065 | 103 |
| SD | −2.112 | **0.000** | −53.481 | +1.577 | — |

### 4.2 Threshold probabilities

| P(pyds > k) | mean shift | max abs | rows moving >0.5pp |
|---|---|---|---|
| 175 | −0.024 pp | 2.123 pp | 49 |
| 200 | −0.057 pp | 2.342 pp | 44 |
| 225 | −0.082 pp | 2.281 pp | 31 |
| 250 | −0.105 pp | 2.334 pp | 36 |
| 275 | −0.120 pp | 2.432 pp | 35 |
| 300 | −0.126 pp | 2.618 pp | 35 |

**The median row moves by exactly zero at every statistic.** The effect is
concentrated: roughly 35–50 rows of 490 move more than half a percentage point at a
threshold, and a handful move P90 by tens of yards.

### 4.3 The D19 cell alone — negligible, and reported as negligible

| | with | without | delta |
|---|---|---|---|
| mean | 210.1484 | 210.3907 | **+0.2424** |
| SD | 78.9895 | 78.6564 | −0.3331 |
| P10 | 117.00 | 117.22 | +0.2182 |
| P50 | 209.42 | 209.88 | +0.4583 |
| P90 | 306.98 | 307.02 | +0.0344 |

Threshold shifts: +0.067 pp at 175 falling to +0.012 pp at 300. **One cell in a
thousand moves the mean by 0.12% and no threshold probability by more than 0.07
percentage points.** The honest expectation in the brief is confirmed. This is not
inflated into a finding.

The finding is not D19. The finding is the 2,140 out-of-support cells and the
27,564 impossible ones that D19 led to.

### 4.4 CRPS and PIT — what the artifacts actually support

**CRPS is exact, not approximated.** `player_draws.npz` stores the full 1,000
simulated draws per row, not nine percentiles, so the closed form applies directly.

**Log score is NOT available** without a smoothing choice. A 1,000-draw empirical
measure with atoms at zero has no density; any log score would be scoring a kernel
the engine never declared. I did not compute one.

**PIT is NOT assessable here.** Only 20 QB-game passing lines in this repository
have a realised outcome. PIT on 20 clustered observations measures nothing.

Outcomes available: `nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz`,
10 of 15 week-1 games, retrieved 2026-09-14T00:25:56Z. It has **zero DEN and zero KC
rows** and predates the 2026-09-15T00:15Z kickoff. The DEN@KC result is not in this
repository and was not used.

CRPS measured on the 9 raw-`qb_v1` rows that have both a board and an outcome:

| | value |
|---|---|
| mean CRPS with contamination | 63.4571 |
| mean CRPS with cells dropped | 63.0862 |
| delta | **−0.3709 yards** |
| per-row delta | median −0.0068, min −3.897, max +0.441 |

**n = 9 rows over 9 games. This establishes nothing** about whether cleaning
improves forecast quality, and must not be quoted as evidence either way. It is
reported because it was measured, with its n attached.

---

## 5. Market comparison — the boundary

**No market feed exists in this system and no sportsbook data is in this
repository.** `board.json` carries its own `threshold_disclaimer` saying so. No
price was fetched, no line estimated, no edge computed. Nothing here is a wager
recommendation.

What can legitimately be said is a property of **our own distribution**: where the
stored quantity is contaminated in the region an external threshold would sit.

**Unsafe to compare against any external threshold:**

1. **`qb/pyds` on any team-side with no receiving layer** — 68 QB-only boards plus
   the DEN side of the two R9 DEN@KC boards. 1.19% of cells at `cmp ≥ 10` fall
   below, and 0.45% above, the yards-per-completion support of 3,181 realised games.
   Individual rows move up to 2.6 pp at a 175–300 yard threshold and up to 26.8 yards
   at P90 when those cells are removed. A threshold in the tail is reading a region
   built almost entirely out of 1-completion donor games.

2. **`qb/cmp`, `qb/pyds`, `qb/ptd` on the 50 `C3_OLD_CREDIT` boards** — 27,564 cells
   are impossible box scores. The *team* total is exact; the *per-QB* split is not a
   football line at all.

3. **`rushing/rushing_td` on those same 50 boards** — 442 cells carry more rushing
   touchdowns than carries.

**Clean by this census:** the three DEN@KC boards `f91342d6787a66a1`,
`96954efc523bd7d3` and `d1e2727743c93990` carry none of the per-QB impossible
states, and D19's own measured effect is negligible.

---

## 6. Fixes proposed — **none applied**

**X1-F1 — `nfl/research/qb2/qb2_lib.py:306-307`.** `PY = CMP * ypc_d` applies a
game-level ratio estimated at any completion count to a completion count drawn
independently. Three options, all mechanism changes requiring pre-registration:

- weight the `_mix` resample by the donor game's completion count, so a
  1-completion game cannot carry the same mass as a 30-completion game;
- shrink each donor ratio toward the pooled rate by its own completion count,
  `n/(n+k)` — the same shrinkage form this file already uses for `w`;
- replace the product with a per-completion yardage draw, so game yardage is a *sum*
  of `cmp` draws rather than a scalar multiple. This also removes the zero
  conditional dispersion of `pyds` given `cmp`, and the 30.4% non-integrality.

**Not a fix: clipping** `pyds` at zero or at any −k. D19's own `test_required` says
so and it is right — the check must go to zero by construction, never by widening or
moving a fence.

**X1-F2 — the 50 `C3_OLD_CREDIT` boards.** No code change needed:
`credit_passing_line` already replaces `credit_to_passers` and is coherent by
construction. What is missing is that 50 sealed boards carry the defect and nothing
marks them. Propose a board-level provenance field naming which credit function
produced the QB passing line, so a consumer can refuse the old ones.

**X1-F3 — `nfl/production/draw_coherence.py:47`.** Derive the negative-yardage
counts at run time instead of writing them into prose.

**X1-F4 — `OPEN_DEFECTS.json` D19 `blast_radius`.** Correct per-board to
per-team-side; the stated invariant is not broken. Record that the same mechanism
produces 2,262 cells and a larger right-tail contamination, so D19 is not a
one-cell defect.

---

## 7. Every claim in the brief, checked

| Claim | Verdict |
|---|---|
| D19 cell: `att=30, cmp=16, pyds=−32.0`, board `d1e2727743c93990`, draw 885 | **Verified exactly** |
| 2,262 negative `qb/pyds` cells across the corpus | **Reproduced exactly** (67 boards) |
| 2,261 on QB-only boards, 1 on a C3 board | True of *boards*; **misleading as an inference**. Per team-side it is 2,262 / 0 |
| 104 sealed boards | **Wrong — 121.** Five are `.npz.gz` |
| `96954efc523bd7d3` carries none and is clean | **Verified** — clean on every check here |
| ~149/1000 draws per team deal excess carries | **Not reproducible.** 314/132,000 (0.238%), worst excess 0.743 carries. Source is `D1_DEN_UNIVERSE.md:175`, an in-flight build |
| Negative tail is a symmetric-distribution artifact | **Rejected.** Empirical resample; nothing fitted |
| Negative yardage is legitimate and deliberately unclipped | **Confirmed** — and the fix must not be a clip |
| No market feed / no sportsbook data | **Confirmed**, including in `board.json` |
| DEN@KC result not in the repository | **Confirmed** — 0 DEN and 0 KC rows, capture predates kickoff |
