# W3 — Running backs, backfield opportunity, and the redistribution problem

**Worker:** 3 (RB / rushing / backfield opportunity)
**Date measured:** 2026-09-06, in this container.
**Inputs:** `nfl/research/_GROUNDING.md`; nflverse-data 2024 releases (pbp,
pbp_participation, snap_counts, injuries, players, pfr_advstats);
`v8/FEATURE_REGISTRY.md`; `v8/V8_SYSTEM_CONSTITUTION.md` Rules 004a / 005 / 006.
**Scope limit honoured:** research only. No production or predictive code
written. All measurement scripts are throwaway, live in the session scratchpad
(`.../scratchpad/w3/s1_build.py` … `s23_rec.py`), and are **not** committed.
This file is the only file created or modified.

Every substantive claim is labelled `VERIFIED`, `DERIVED`, or
`UNVERIFIED-RECALL` per the grounding brief.

---

## 0. Executive summary — the five numbers that decide the architecture

All `VERIFIED`, all 2024 regular season, derivations in the sections named.

| # | Finding | Number | §|
|---|---|---|---|
| 1 | Opportunity is far more predictable than efficiency. Identical random game splits, same 92 players. | half-season split-half r: **snap share 0.925 / carry share 0.926** vs **YPC 0.385 / EPA per rush 0.308 / success rate 0.132** | §4 |
| 2 | Forward-chained week-ahead, prior games only. | opportunity share **r = 0.75** ; per-carry efficiency **r = 0.08–0.12**, and R² against the pooled mean is **negative** for all three efficiency metrics | §4.3 |
| 3 | Game rushing yards are an opportunity quantity. | corr(carries, rush yards) = **0.866** (r² 0.749) vs corr(YPC, rush yards) = **0.453** (r² 0.205); log-variance shares carries **62.7%**, YPC **25.1%**, covariance 12.2% | §4.4 |
| 4 | "The goal-line back" is **not** a separable role at 2024 sample sizes. Out-of-sample skill of a player's own first-half goal-line share over just using his overall carry share. | goal-line **+0.5%**, goal-to-go **+0.0%**, short-yardage +3.7%, two-minute +7.7%, **third down +13.3%** | §3 |
| 5 | When a lead back is Out, the vacated share does **not** mostly go to the #2. | of the vacated backfield carry share, backs ranked 3rd-or-lower plus zero-baseline backs absorb a mean **+0.627**; the top remaining back absorbs mean **+0.102** (median +0.357). 39 events, 21 focal players | §5 |

The architectural consequence, `DERIVED` from 1–4: **the RB layer must be an
opportunity-allocation model with a heavily-pooled efficiency kernel, not a
player-efficiency model.** The consequence of 5 is that the allocation model has
to be a *distribution* over reallocations, not a rule, because no rule fits well
(best MAE 0.201 on a quantity with SD ≈ 0.30).

---

## 1. Method, joins, and join-rate verification

### 1.1 Files used

`VERIFIED` — `sha256sum` in this container, 2026-09-06. The first five are the
shared cache; hashes agree exactly with W1's table, so we measured the same
bytes.

| file | release path | bytes | sha256 (first 16) |
|---|---|---|---|
| pbp 2024 | `pbp/play_by_play_2024.csv` | 99,483,794 | `6ae564c2c49378ec` |
| participation 2024 | `pbp_participation/pbp_participation_2024.csv` | 49,688,308 | `b1f436a98b2a7759` |
| snap_counts 2024 | `snap_counts/snap_counts_2024.csv` | 2,402,841 | `a2aa58efe093f8aa` |
| injuries 2024 | `injuries/injuries_2024.csv` | 816,989 | `498bce8e13cb64b2` |
| players | `players/players.csv` | 7,289,018 | `fb6a961ca631ab92` |
| **pfr rush advstats 2024** | `pfr_advstats/advstats_week_rush_2024.csv` | **205,511** | `6e61097bacd6bd33` |

The last one is new — downloaded by me, HTTP 200, 205,511 bytes:

```
curl -sS -L -w "HTTP %{http_code} bytes %{size_download}\n" -o adv_rush2024.csv \
  "https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_rush_2024.csv"
```

### 1.2 Environment

`VERIFIED`: `python3.12 -c "import pandas"` failed at session start;
`python3.12 -m pip install --break-system-packages pandas numpy` succeeded and
gave `pandas 3.0.5 / numpy 2.5.3`. `python3`, `python3.11`, `python3.13` still
have no pandas. This reproduces W1's Class-D observation from the other side:
**pandas availability in this container is mutable and interpreter-specific.**
Any NFL tooling must assert its imports with a named `BLOCKED` code at start-up.

### 1.3 The pbp ↔ participation join — verified before use

`VERIFIED` (`w3/s2_join.py`):

- pbp 2024: **49,492 data rows**, **285 distinct `game_id`**, zero duplicates on
  `(game_id, play_id)`.
- participation 2024: **45,919 data rows**, **285 distinct `nflverse_game_id`**,
  zero duplicates on `(nflverse_game_id, play_id)`.
- Naive left join over all pbp rows: **45,919 / 49,492 = 0.9278** matched. The
  3,573 unmatched are kickoffs, punts, field goals, extra points, timeouts,
  penalty-only and no-play rows — participation does not carry them.
- **On the population that matters** — `season_type == REG`, `play_type ∈
  {run, pass}`, `two_point_attempt == 0`: **33,335 rows, join rate 1.0000**,
  zero unmatched games, zero unmatched weeks, and `offense_players` null on
  **0.00000** of matched rows.

`VERIFIED`: the REG frame is **272 games**. This settles the grounding brief's
`UNVERIFIED-RECALL` "NFL has ~272 regular-season games per season" — it is
exactly 272 in 2024, and 285 − 272 = 13 postseason games (`DERIVED`).

`VERIFIED`: `offense_players` and `offense_positions` are `;`-delimited and
**always length 11**, and their lengths agree on **1.00000** of rows. Exploding
the 33,335 plays gives **366,685 player-play rows**.

### 1.4 Independent cross-check of the derived snap counts

Participation-derived snaps were checked against PFR `snap_counts`, which is a
*different vendor's* count. Crosswalk `players.csv` `pfr_id` → `gsis_id`:
**99.85%** of REG snap_counts rows crosswalk (`VERIFIED`, `w3/s5_validate.py`).

| check | value |
|---|---|
| RB player-games from participation (modal position `RB`, ≥1 offensive snap) | **1,430** |
| RB player-games in PFR snap_counts with `offense_snaps > 0` | **1,457** |
| matched both ways | **1,429** |
| in PFR only | **28** — all with 1–3 offensive snaps (max 3, median 2) |
| in participation only | **1** |
| corr(participation snaps, PFR `offense_snaps`) | **0.9966** |
| mean absolute difference | **1.57 snaps** (mean 23.36 vs 24.92) |
| within ±3 snaps | **87.3%** |

`DERIVED`: the two sources agree. The systematic −1.57 gap is that participation
carries only run/pass scrimmage plays while PFR counts kneels, spikes, penalty
plays and two-point tries as offensive snaps. **Both are usable; they are not
interchangeable, and a system must declare which denominator it means.** This is
exactly the MLB `FEATURE_REGISTRY` denominator discipline (Rule 019) applied to
NFL: "snap share" is not one quantity.

`VERIFIED`: 140 distinct RBs, 544 team-games, **1,430 RB player-games**; RBs per
team-game: 1 (×1), 2 (×225), 3 (×293), 4 (×25).

`VERIFIED`: fullbacks are a separate `offense_positions` label and are
**excluded** from every RB denominator below. 154 FB player-games; FB carries are
**0.33%** of RB+FB carries. `DERIVED`: excluding FBs is immaterial to shares but
must be declared, because "the backfield" is ambiguous otherwise.

### 1.5 A correction to `_GROUNDING.md` — routes run per player are NOT computable

The grounding brief states (line ~85) that `offense_players` together with
`route` "is what makes **route participation** and **targets per route run**
computable." `VERIFIED` (`w3/s3_route.py`), that is **not correct for
per-player routes**:

- `route` is **one scalar per play**, never a `;`-delimited list (fraction of
  non-null values containing `;` = **0.0000**).
- It is non-null on **0.9010** of pass plays and **0.0009** of run plays, and on
  **0.9867** of pass plays that have a `receiver_player_id`.
- It takes 13 values (`QUICK OUT` 3,191, `HITCH/CURL` 3,006, `SCREEN` 1,823,
  `IN/DIG` 1,561, `GO` 1,399, …).

`DERIVED`: `route` is the route run by the **targeted** receiver. The number of
routes run by a *non-targeted* player is not in this feed. Therefore **targets
per route run (TPRR) cannot be computed from nflverse participation**, and any
NFL design that assumes it can is building on an absence read as a presence —
Failure Taxonomy Class A.

The computable substitute, and what I use throughout: **pass-snap
participation** — the player was on the field for a `play_type == 'pass'` snap
(which includes sacks). `targets / pass-snaps` is a TPRR *proxy* with a
different, larger denominator. It should be registered under its own name, never
as TPRR.

**Escalation-free handoff:** if TPRR is wanted, it needs a charted route source
(PFF or similar). That is outside this repository and outside nflverse. Under
`docs/AGENT_PROTOCOL.md` DEC-029 that is *assigned*, not blocked — it belongs in
`docs/AGENT_OUTBOX.md` if anyone decides they need it.

---

## 2. Measured backfield opportunity shares (2024)

`VERIFIED`, `w3/s6_dist.py`. n = 1,430 RB player-games, 140 RBs, 544 team-games.
Denominators are stated on every row because they are not interchangeable.

| quantity | denominator | mean | sd | p10 | p25 | p50 | p75 | p90 | p95 |
|---|---|---|---|---|---|---|---|---|---|
| snap share | team run/pass scrimmage plays | 0.381 | 0.252 | 0.065 | 0.167 | 0.343 | 0.587 | 0.753 | 0.820 |
| carry share | team rush attempts | 0.314 | 0.251 | 0.000 | 0.095 | 0.262 | 0.526 | 0.686 | 0.760 |
| carry share | **RB** rush attempts | 0.380 | 0.300 | 0.000 | 0.118 | 0.316 | 0.632 | 0.846 | 0.900 |
| target share | team targets | 0.064 | 0.065 | 0.000 | 0.000 | 0.048 | 0.105 | 0.156 | 0.190 |
| pass-snap share | RB pass snaps | 0.380 | 0.261 | 0.053 | 0.154 | 0.343 | 0.586 | 0.758 | 0.843 |
| opportunities (carries+targets) | count | 10.26 | 8.11 | 1 | 3 | 9 | 16 | 22 | 25 |
| carries | count | 8.25 | 7.07 | 0 | 2 | 6 | 13 | 19 | 22 |
| targets | count | 2.01 | 2.06 | 0 | 0 | 1 | 3 | 5 | 6 |

**By backfield rank within the team-game** (rank 1 = most snaps), `VERIFIED`:

| rank | n | snap share (sd) | carry share of RB carries | carries | targets | opportunities | team target share |
|---|---|---|---|---|---|---|---|
| 1 | 544 | 0.656 (0.136) | 0.685 | 14.84 | 3.46 | **18.30** | 0.111 |
| 2 | 543 | 0.279 (0.113) | 0.246 | 5.36 | 1.51 | **6.88** | 0.049 |
| 3 | 318 | 0.113 (0.073) | 0.116 | 2.49 | 0.52 | 3.01 | 0.016 |
| 4 | 25 | 0.040 (0.031) | 0.029 | 0.64 | 0.12 | 0.76 | 0.004 |

**Concentration**, `VERIFIED`: the top RB takes ≥70% of his team's RB carries in
**53.9%** of team-games, ≥85% in **25.7%**, 40–70% in **45.4%**, and <40% in
**0.7%**. Backfield carry HHI: mean 0.617, median 0.581, p10 0.414, p90 0.867.

`DERIVED`: "the NFL is a committee league" is false as stated for 2024 — more
than half of team-games are ≥70% concentrated — but a pure bell-cow is a
minority (25.7%). The distribution is bimodal-ish and wide, and the model must
carry the whole distribution, not a modal assumption.

**Team-level pie**, `VERIFIED` (544 team-games): offensive run/pass plays mean
61.3 (sd 8.2); team rush attempts mean 26.3 (sd 7.2); **team RB rush attempts
mean 21.7 (sd 6.5)**; RB share of all team rush attempts **0.826** (the balance
is QB scrambles and designed QB runs).

`DERIVED`: the owner's framing — 8 opportunities to 19 — is a movement across
roughly the rank-2 (6.9) to rank-1 (18.3) gap. That gap is **real and large:
+11.4 opportunities on a base of 6.9, a 2.7× change with no change in talent.**
Whether it *happens* on an absence is §5.

---

## 3. Situational roles — is "the goal-line back" real?

### 3.1 How much situational volume exists at all

`VERIFIED`, `w3/s7_situ.py`. Base: **11,809 RB rush attempts**, REG 2024.

| situation | definition | plays | % of RB carries |
|---|---|---|---|
| goal-line | `yardline_100 <= 5` | 624 | 5.3% |
| goal-to-go | `goal_to_go == 1` | 896 | 7.6% |
| short-yardage | `ydstogo <= 2 and down in (3,4)` | 745 | 6.3% |
| two-minute | `half_seconds_remaining <= 120` | 769 | 6.5% |
| third down | `down == 3` | 1,066 | 9.0% |
| early down | `down in (1,2)` | 10,589 | 89.7% |

**Per-RB season counts, RBs with ≥50 season carries (n = 70)** — this table is
the whole answer:

| | carries | goal-line | short-yd | two-min | 3rd down | goal-to-go |
|---|---|---|---|---|---|---|
| mean | 151.7 | 8.3 | 9.2 | 8.7 | 12.7 | 11.9 |
| median | 133.5 | **6** | 8 | 6.5 | 11 | 9 |
| p25 | 76.3 | 4 | 5 | 4 | 7 | 6 |
| p90 | 260.3 | 17 | 18 | 19 | 23 | 23 |
| max | 345 | **22** | 28 | 34 | 42 | 34 |

`DERIVED`: the *entire season's* evidence about whether a given back is "the
goal-line back" is a median of **6 carries**, and the maximum any 2024 RB got
was 22. No estimator can extract a stable role from that. This is the same shape
as MLB's rejected line-drive-rate feature ("stabilises at 600 BIP, which no
player reaches in a season").

### 3.2 Is there excess dispersion at all? (in-sample)

`VERIFIED`, `w3/s8_role.py`. For each (team, player), expected situational
carries = team situational carries × that player's **out-of-situation** carry
share; z is the binomial-standardised residual. Under the null of "no role", var(z) = 1.

| situation | n players | mean team situational carries | var(z) | excess | fraction \|z\| > 2 |
|---|---|---|---|---|---|
| goal-line | 138 | 19.4 | 1.92 | +0.92 | 0.080 |
| goal-to-go | 138 | 27.8 | 1.89 | +0.89 | 0.080 |
| short-yardage | 138 | 22.7 | 3.42 | +2.42 | 0.138 |
| two-minute | 133 | 24.5 | 5.56 | +4.56 | 0.211 |
| third down | 138 | 33.2 | 5.21 | +4.21 | 0.246 |

`VERIFIED`: the same test on `early-down` gives var(z) = 30.1, and **that number
must not be quoted.** The expected share is estimated from the complement, and
for early-down the complement is only ~10% of carries, so the "expected" value is
itself noisy and the statistic is inflated by construction. Reported here only so
it is not rediscovered as a finding.

`DERIVED`: role separation exists in-sample for every situation, and it is
**smallest exactly where the folk model is loudest** — goal-line and goal-to-go
have the least excess dispersion of the five.

### 3.3 Does it survive out of sample? (the decisive test)

`VERIFIED`, `w3/s9_role2.py`. Split the season at week 9/10. Predict each
player's **second-half** situational share from (a) his first-half situational
share, (b) his first-half **overall** carry share, (c) the best fixed blend
`w·(a) + (1−w)·(b)`, with `w` chosen on the second half — i.e. **generous to the
role hypothesis**, since the blend weight is fitted on the very data being
scored.

| situation | n players | median 1H situational carries | MSE using overall share | MSE using situational share | best w\* | MSE at w\* | **skill added by role information** |
|---|---|---|---|---|---|---|---|
| goal-line | 39 | 5 | 0.04911 | 0.07115 | 0.09 | 0.04888 | **+0.5%** |
| goal-to-go | 48 | 8 | 0.03323 | 0.05336 | 0.00 | 0.03323 | **+0.0%** |
| short-yardage | 42 | 4 | 0.03970 | 0.05038 | 0.26 | 0.03823 | +3.7% |
| two-minute | 41 | 5 | 0.04897 | 0.07299 | 0.27 | 0.04519 | +7.7% |
| third down | 53 | 6 | 0.03580 | 0.04019 | 0.42 | 0.03104 | **+13.3%** |

Residual (situational minus overall) split-half r: goal-line +0.367, goal-to-go
+0.249, short-yardage +0.313, third down +0.436, two-minute +0.206.

**The answer, `DERIVED`:**

1. **"The goal-line back" is a real effect that is not usable.** The residual
   correlation is positive (+0.37), so something is there; but at the sample
   sizes the season actually provides, using it adds **0.5%** skill over simply
   using the back's overall carry share, and the fitted weight on the
   goal-line-specific signal is **0.09**. Goal-to-go adds **nothing** (w\* = 0.00).
   A negative result, and it is the finding.
2. **The passing-down / third-down role is the one that is real and usable.**
   +13.3% skill, w\* = 0.42, residual r = 0.44. That matches the receiving-role
   evidence in §4 (RB pass-snap share splits at r = 0.913, essentially as
   reliable as rushing snap share).
3. **Design consequence:** the RB layer should carry **one** role split —
   early-down/rushing versus passing-down — and should **not** carry a separate
   goal-line back parameter. A goal-line term should be a *team-level* rate
   (how often this offence runs from inside the 5) times the back's ordinary
   backfield share, not a player-specific goal-line share.

**Caveats, stated rather than buried.** n is 39–53 players per row. The split is
within-season and within-team, so mid-season trades and role changes are
mislabelled as noise. The blend weight was fitted on the scored half, which
*inflates* the skill numbers — the true out-of-sample skill of goal-line share is
≤ +0.5%. Under Rule 006 this is **development-grade exploratory** evidence: it is
sufficient to refuse to build a goal-line-back parameter, and insufficient to
declare the effect absent.

---

## 4. Reliability — the opportunity/efficiency gap, quantified

### 4.1 The like-for-like comparison

`VERIFIED`, `w3/s11_relcmp.py`. 92 RBs with ≥8 RB player-games, 1,285
player-games, mean 14.0 games. **The same 200 random game-level splits are used
for every row**, so the comparison is not confounded by different samples or
different split procedures. Spearman–Brown extrapolates the half-season
correlation to a full season.

| quantity | class | half-season r | 95% band over splits | Spearman–Brown (full season) |
|---|---|---|---|---|
| snap share | OPPORTUNITY | **0.925** | 0.900 – 0.945 | 0.961 |
| carry share (of RB carries) | OPPORTUNITY | **0.926** | 0.902 – 0.946 | 0.962 |
| carry share (of team rushes) | OPPORTUNITY | 0.924 | 0.900 – 0.943 | 0.961 |
| pass-snap share (of RB) | OPPORTUNITY | 0.913 | 0.882 – 0.937 | 0.954 |
| opportunities per game | OPPORTUNITY | 0.913 | 0.885 – 0.934 | 0.955 |
| carries per game | OPPORTUNITY | 0.904 | 0.878 – 0.930 | 0.950 |
| target share (of team) | OPPORTUNITY | 0.832 | 0.781 – 0.872 | 0.908 |
| **yards per carry** | EFFICIENCY | **0.385** | 0.206 – 0.550 | 0.550 |
| **EPA per rush** | EFFICIENCY | **0.308** | 0.153 – 0.490 | 0.465 |
| **success rate** | EFFICIENCY | **0.132** | −0.042 – 0.313 | 0.221 |

`DERIVED`: **the gap is 0.54 to 0.79 in correlation, and the bands do not
overlap.** Success rate's band **includes zero** — at half a season, an RB's
rushing success rate is not distinguishable from a coin.

Note per Rule 005: reliability is one number and I am not quoting it as though
it were forecasting skill. §4.3 gives the forecasting version.

### 4.2 How many carries before efficiency is usable

`VERIFIED`, `w3/s10_rel.py`. Carry-level variance decomposition on the 70 RBs
with ≥50 season carries (mean 152 carries). `var_true = var(player means) −
var_within × mean(1/n)`; reliability at n carries is
`var_true / (var_true + var_within/n)`.

| metric | within-carry variance | implied true between-player variance | **carries for reliability 0.5** | **for 0.7** |
|---|---|---|---|---|
| rushing yards per carry | 38.589 | 0.194 | **199** | 463 |
| EPA per rush | 0.8889 | 0.00815 | **109** | 254 |
| success rate | 0.2378 | 0.00183 | **130** | 304 |

Reliability at realistic season volumes (`DERIVED` from the same fit):

| carries | YPC | EPA/rush | success |
|---|---|---|---|
| 50 | 0.201 | 0.314 | 0.278 |
| 100 | 0.335 | 0.478 | 0.434 |
| 150 | 0.430 | 0.579 | 0.535 |
| 200 | 0.502 | 0.647 | 0.606 |
| 300 | 0.602 | 0.733 | 0.697 |

`VERIFIED`: only **70 of 140** RBs reached 50 carries in 2024, and the median
among those was 133.5. `DERIVED`: **the median NFL running back never reaches
reliability 0.5 on any efficiency metric in a full season.** Compare opportunity
share, which reaches r ≈ 0.93 in *half* a season.

**An honest ceiling on "true between-player variance".** This decomposition
attributes to the *player* everything that is stable across his carries within
the season — which includes his offensive line, his scheme, his quarterback and
his opponents. It is an **upper bound on player skill**, not a measurement of
it. §6.3 shows this bound is loose.

### 4.3 Forward-chained week-ahead prediction — the forecasting version

`VERIFIED`, `w3/s12_fwd.py`. For each RB player-game with ≥3 prior games,
predict from the mean of **prior games only** (no future information; Rule 003
respected by construction). `R² vs pooled mean` is 1 − SSE/SST against the
pooled sample mean of the target.

| target | n | r | r² | R² vs pooled mean | MAE |
|---|---|---|---|---|---|
| carry share (of RB carries) | 1,049 | **0.753** | 0.567 | **+0.560** | 0.147 |
| carry share (of team rushes) | 1,049 | 0.755 | 0.570 | +0.565 | 0.125 |
| snap share | 1,049 | 0.746 | 0.557 | +0.543 | 0.125 |
| opportunities | 1,049 | 0.733 | 0.537 | +0.531 | 4.30 |
| carries | 1,049 | 0.716 | 0.512 | +0.507 | 3.83 |
| target share | 1,049 | 0.554 | 0.306 | +0.280 | 0.041 |
| **yards per carry** | 693 | **0.116** | 0.014 | **−0.097** | 1.598 |
| **EPA per rush** | 693 | 0.094 | 0.009 | **−0.107** | 0.259 |
| **success rate** | 693 | 0.075 | 0.006 | **−0.110** | 0.141 |

`DERIVED`, and this is the single most consequential line in the document:
**for next-game per-carry efficiency, a player's own prior average is worse than
the league constant** (R² of −0.10 to −0.11 against the pooled mean). Naive
carry-forward of RB efficiency is an actively harmful estimator.

For calibration against the project's own history: MLB's V7 baseline scores
r = 0.1101 on game totals (`CLAUDE.md`). The NFL RB **opportunity** channel
scores r = 0.75 week-ahead. **These are different targets and are not
comparable as model quality** — I am quoting them only to say that the RB
opportunity signal is not a marginal one.

### 4.4 Where the yards actually come from

`VERIFIED`, `w3/s20_final.py`. RB player-games with ≥1 carry, n = 1,283.

- corr(carries, rushing yards) = **0.8657** (r² = 0.749)
- corr(YPC, rushing yards) = **0.4527** (r² = 0.205)
- restricted to ≥8 carries (n = 651): carries 0.742, YPC 0.711

Log decomposition, `log yards = log carries + log YPC`, on the 1,241
player-games with positive yards (`VERIFIED`):

| component | variance | share of var(log yards) = 1.2731 |
|---|---|---|
| var(log carries) | 0.7983 | **62.7%** |
| var(log YPC) | 0.3192 | 25.1% |
| 2·cov | 0.1557 | 12.2% |

`DERIVED`: ~63% of the cross-sectional variance in a back's rushing yards is
volume, and volume is the part that is forecastable (§4.3). Efficiency
contributes a quarter of the variance and almost none of the predictability.

### 4.5 Receiving role

`VERIFIED`, `w3/s23_rec.py`. Same split procedure.

- RB pass-snap share (of RB pass snaps): split-half **0.913**, SB 0.954 — an
  opportunity quantity, and as reliable as the rushing ones.
- targets per RB pass-snap (the TPRR proxy of §1.5): split-half **0.369**,
  SB 0.535 — a rate quantity, reliability in the efficiency band.
- season-level targets per pass-snap, 69 RBs with ≥100 pass snaps: mean 0.1513,
  sd 0.0390, p10 0.1025, p50 0.1508, p90 0.2018.

`DERIVED`: the receiving channel has the same two-layer structure as the rushing
channel — a highly stable participation share and a weakly stable conversion
rate — and should be modelled the same way.

---

## 5. Redistribution — what actually happens when a back is Out

This is the NFL-specific mechanism the owner named, and it is the section with
the smallest sample. Every count is stated.

### 5.1 Event construction

`VERIFIED`, `w3/s13_redist.py` / `s16_event2.py`.

- `injuries_2024.csv` REG rows: **5,954**. `report_status`: `NaN` 3,203,
  `Questionable` 1,464, **`Out` 1,091**, `Doubtful` 190, `Note` 6.
- Distinct `(team, week, gsis_id)` with `Out`: **1,091**. Of these, position RB:
  **79 rows, 45 distinct players**.
- Team codes in `injuries` and in pbp `posteam` are **identical sets** (verified
  set-difference both directions is empty) — no mapping needed.
- Built a full team × week × RB panel (2,431 rows) with zero-filled shares.
  **77** panel rows carry an `Out` flag, and **0 of the 77 recorded a snap** —
  the `Out` label is clean in 2024 for RBs.
- **Events** = an `Out` RB whose backfield carry share over his **last ≤3 games
  in which he actually played** was ≥ 0.25, with ≥2 such baseline games:
  **39 events, 21 distinct focal players, 16 distinct teams, 29 distinct
  consecutive-week spells, 141 teammate-rows.**
- Baseline for teammates is computed over **the same games** — the games the
  focal back played — so no teammate baseline is contaminated by an earlier
  absence of the focal back.
- Vacated backfield carry share V: mean **0.528**, median 0.522, p10 0.288,
  p90 0.791. Focal baseline opportunities per game: mean 13.3, median 12.0.

**Sample-size honesty.** 39 events over 21 players is small, and consecutive
weeks of the same injury are not independent (29 spells, not 39). Everything
below is bootstrapped by clustering on the event. Under Rule 006 none of it is
promotable; it is enough to *rule out* rules that clearly do not fit and to size
the uncertainty a model must carry.

### 5.2 Does the backfield pie change?

`VERIFIED`:

| | baseline (focal-played games) | absence game | delta |
|---|---|---|---|
| team RB rush attempts | 20.26 | 21.64 | **+1.38** (95% CI −1.18 … +3.95) |
| team offensive plays | 59.35 | 62.44 | +3.09 |

`DERIVED`: **the pie is approximately conserved.** The point estimate is
slightly positive and the interval comfortably includes zero, and the RB-carry
increase is roughly proportional to the play-count increase. A redistribution
model may treat total backfield rush attempts as unchanged by the absence, and
must not claim it *is* unchanged — Rule 008 of `CLAUDE.md` (no "stable" without
a predeclared margin and a TOST) applies, and no margin was predeclared.

### 5.3 Which reallocation rule fits?

`VERIFIED`, `w3/s17_rules2.py`. Target = each remaining back's actual backfield
carry share in the absence game. n = 141 teammate-rows across 39 events. CIs are
event-clustered bootstrap, 3,000 resamples.

| rule | MAE | 95% CI (event-clustered) | RMSE | bias |
|---|---|---|---|---|
| no reallocation (keep baseline share) | 0.2183 | 0.1876 – 0.2508 | 0.3182 | +0.146 |
| proportional to baseline **carry** share | 0.2384 | 0.1853 – 0.2947 | 0.3610 | 0.000 |
| proportional to baseline **snap** share | 0.2205 | 0.1699 – 0.2716 | 0.3229 | 0.000 |
| **equal split of the vacated share** | **0.2011** | 0.1687 – 0.2361 | **0.2711** | 0.000 |
| next-man-up takes all | 0.2554 | 0.2013 – 0.3116 | 0.3850 | 0.000 |

`DERIVED`: the intuitive rules are the worst. **Next-man-up is the worst of the
five.** Proportional-to-prior-carries is worse than proportional-to-prior-snaps,
which is worse than a flat split. The intervals overlap heavily, so the ordering
is not established — but "next-man-up takes all" is separated from "equal split"
by more than the width of either interval and can be **rejected as a default**.

### 5.4 Where the vacated share actually went

`VERIFIED`. Absorption is `(actual share − baseline share) / V`, per event, backs
ranked by baseline share among the *remaining* backs.

| absorber | mean fraction of V | median | IQR |
|---|---|---|---|
| top remaining back (rank 1) | **+0.102** | +0.357 | −0.222 … +0.628 |
| second remaining back | +0.271 | +0.231 | +0.010 … +0.457 |
| rank 3 and below | **+0.627** | +0.399 | 0.000 … +0.782 |
| backs with **zero** baseline snaps and carries | **+0.496** | +0.180 | 0.000 … +0.754 |

Top remaining back: baseline share 0.385 → absence-game share 0.478
(mean +0.093, median +0.196). 31 of 39 events contained at least one back with a
zero baseline.

In opportunity **counts** rather than shares:

| | baseline opps/game | absence game | mean delta | median delta |
|---|---|---|---|---|
| top remaining back (n=39) | 10.12 | 13.95 | **+3.82** (95% CI +1.06 … +6.59) | +5.67 |
| second remaining back (n=39) | 1.96 | 5.77 | +3.81 | +2.33 |

Top remaining back's snap share: 0.396 → 0.466 (+0.069).

`DERIVED`, and it is the most surprising thing I measured: **the mean/median
divergence for rank 1 (+0.102 vs +0.357) means the distribution is strongly
left-skewed — in a substantial minority of events the presumed heir absorbs
*negative* share, i.e. he is passed over.** A "next man up" point forecast will
be badly wrong in exactly the cases that matter for pricing.

### 5.5 The owner's "8 opportunities to 19" — measured

`VERIFIED`. Teammate-rows with a baseline under 8 opportunities per game
(n = 118): baseline mean 1.52 → absence-game mean 5.54 (mean +4.02, median
+1.67). Outcome quantiles in the absence game: p10 0.0, p25 0.0, p50 3.5,
p75 9.0, p90 14.3. **10.2% reach ≥15 opportunities; 3.4% reach ≥19.**

`DERIVED`: the mechanism the owner describes is **real, large, and rare in that
extreme form.** The typical low-usage back given an opening gets a few more
touches; roughly one in ten gets a genuine workload; roughly one in thirty gets
the full 19. **This is a distributional claim, not a point claim, and it is the
strongest available argument that the RB layer must emit a joint draw rather
than an expectation.** A point projection of "5.5 opportunities" is wrong at
both tails simultaneously.

### 5.6 Backfield churn independent of injury

`VERIFIED`, `w3/s20_final.py`: over 448 team-weeks from week 4 onward, **39
(8.7%)** contained a back with **zero snaps in the team's prior 3 games** who
then took **≥5 opportunities**; their opportunity counts were mean 10.6, median
9, max 21.

`DERIVED`: about one team-week in eleven has a backfield member with **no usable
prior-usage history at all**. Any RB layer needs an explicit prior for a
zero-history back (draft capital, depth chart, roster transaction), or it will
silently assign him zero — the Class-A failure mode again, in a place where the
absence looks exactly like a legitimate zero.

---

## 6. What is NOT available, and what pfr_advstats does provide

### 6.1 Available — `pfr_advstats/advstats_week_rush_2024.csv`

`VERIFIED`, `w3/s18_adv.py`. HTTP 200, 205,511 bytes, **2,359 rows** (2,255 REG),
**333 players**, **272 REG games**. 17 columns:

```
game_id, pfr_game_id, season, week, game_type, team, opponent,
pfr_player_name, pfr_player_id, carries,
rushing_yards_before_contact, rushing_yards_before_contact_avg,
rushing_yards_after_contact, rushing_yards_after_contact_avg,
rushing_broken_tackles, receiving_broken_tackles
```

So **yards before contact, yards after contact, and broken tackles ARE
available** for rushing. The join is exact (`VERIFIED`):

- `players.csv` `pfr_id` → `gsis_id` crosswalk on this file: **1.0000**.
- RB player-games with ≥1 pbp carry: 1,283; matched in advstats: **1.0000**.
- Carry counts agree **exactly** on 1.0000 of matched rows (mean absolute
  difference 0.000, corr 1.0000). Season totals: 11,810 advstats vs 11,809 pbp —
  a single-carry discrepancy somewhere in the season, worth one line in an
  ingest assertion, not a blocker.

### 6.2 Not available — and one column that is a source-empty trap

`VERIFIED`: `receiving_broken_tackles` has a null rate of **1.0000** across all
2,255 REG rows. This is the exact analogue of MLB's `umpire` field in
`v8/FEATURE_REGISTRY.md` (missing fraction 1.0, **REJECTED — SOURCE EMPTY**). It
must be registered as REJECTED-SOURCE-EMPTY so nobody proposes it, and any
ingest must raise a named error rather than emitting a column of nulls.

`VERIFIED` — not present anywhere in the nflverse files examined here, and
therefore `UNVERIFIED-RECALL` as to whether any public source has them: **tackles
avoided per attempt at play level, contact location, defenders in the box on the
specific carry** (`defenders_in_box` *is* in participation — that one exists),
**gap/hole charting, blocking grades, offensive-line continuity, rushing yards
over expected (RYOE) and any Next Gen Stats rushing metric.** The grounding brief
already records `nextgen_stats/*` returning 404 under the names tried.
`DERIVED`: RYOE and NGS-style rushing metrics are **assigned, not blocked** — if
wanted they must be requested through `docs/AGENT_OUTBOX.md` with the exact
release path to probe.

### 6.3 Do the charted metrics help? Measured, and the answer reorders the layer

`VERIFIED`, `w3/s19_adv2.py`. Identical random game splits, same 70 RBs with ≥50
carries, all four rates computed on the same denominator (carries):

| per-carry rate | split-half r | 95% band | Spearman–Brown |
|---|---|---|---|
| yards per carry | 0.313 | 0.137 – 0.469 | 0.469 |
| **yards BEFORE contact** per carry | 0.245 | 0.086 – 0.398 | 0.386 |
| **yards AFTER contact** per carry | 0.288 | 0.138 – 0.437 | 0.442 |
| broken tackles per carry | 0.190 | 0.012 – 0.369 | 0.310 |

Forward-chained (≥40 prior carries, ≥5 carries this game, n = 523 player-games),
correlation with **this game's** YPC:

| prior-season-to-date quantity | corr with this-game YPC |
|---|---|
| prior YPC | **+0.1776** |
| prior yards **before** contact per carry | **+0.1811** |
| prior yards **after** contact per carry | **+0.0469** |

(This-game YPC: mean 4.275, sd 1.800.)

`DERIVED`, and it is the important result in this section: **yards before
contact — a blocking and scheme quantity, not a running-back quantity — predicts
a back's future yards per carry at least as well as his own yards per carry
does, and roughly four times better than yards after contact does.** The
persistent component of "RB rushing efficiency" appears to be mostly the offence
he runs behind.

`DERIVED` consequence: yards-before-contact belongs in a **team/offensive-line
layer**, not the player layer, and the player-specific efficiency residual —
yards after contact, broken tackles — is the *least* reliable thing measured in
this whole document (SB 0.442 and 0.310, band on broken tackles nearly touching
zero). It is also the thing conventional football analysis most confidently
attributes to the back.

`UNVERIFIED-RECALL`, flagged as needing confirmation: PFR's before/after-contact
split is a human charting judgement and its inter-rater reliability is unknown to
me. That is a ceiling on the numbers above and should be checked before any
before/after-contact feature is promoted above EXPERIMENTAL.

### 6.4 Should efficiency be shrunk all the way to the league mean?

The §4.3 result (own prior YPC has **negative** R² against the pooled mean for
*next-game YPC*) tempts one to shrink to zero. `VERIFIED`, `w3/s21_shrink.py` and
`w3/s22_boot.py`, that would be an overcorrection. Forward-chained next-game
**rushing yards**, n = 701 RB player-games (≥4 prior games, ≥30 prior carries),
league mean YPC 4.3825:

| predictor | r | r² | MAE | RMSE |
|---|---|---|---|---|
| prior carries/g × **league** YPC | 0.5802 | 0.337 | 25.13 | 32.45 |
| prior carries/g × **own prior** YPC | **0.6192** | 0.383 | 24.25 | **31.32** |
| prior carries/g × blend, w = 0.50 own | 0.6106 | 0.373 | 24.50 | 31.56 |
| constant (pooled mean yards) | 0.0000 | 0.000 | 31.96 | 39.79 |

Best own-YPC weight w\* = 0.93; RMSE gain from using own prior YPC = **+1.135
yards** out of 32.45. Cluster bootstraps of that gain, 3,000 resamples each:

| clustering | clusters | 95% CI on the gain | P(gain > 0) |
|---|---|---|---|
| by player | 78 | +0.115 … +2.205 | 0.989 |
| by game | 208 | +0.334 … +1.934 | 0.998 |
| by week | 14 | +0.209 … +1.996 | 0.991 |

`DERIVED`: the gain is small (3.5% of RMSE) but resolvable under all three
clusterings. **Full shrinkage to the league mean is not supported.** The apparent
conflict with §4.3 is real and worth stating plainly: prior YPC is a poor
estimate of *future per-carry rate*, yet `prior carries × prior YPC` is a
slightly better estimate of *future yards* than `prior carries × league YPC` —
because prior yards-per-game is itself a marginally better volume proxy than
prior carries alone. `UNVERIFIED-RECALL` as an interpretation; §6.3 supports it
(the persistent part tracks blocking, which also tracks volume) but I have not
separated the two here, and doing so is experiment RB-E5 below.

Per Rule 005, I am reporting r, RMSE and MAE together for every row above rather
than the single metric that made the case cleanest.

---

## 7. Proposed RB layer, and the falsification experiment for each component

**Nothing below is built.** This is a design proposal with the experiment that
would kill each piece, per Rule 004a — metrics, splits, clustering and
multiplicity written down **before** anything runs.

### 7.1 Structure

```
L0  TEAM VOLUME             offensive plays, pass rate, team rush attempts
                            (consumes W1/W2 game-script work; not mine)
        |
L1  AVAILABILITY SET        which RBs are active this week
                            live-captured status vintages, NOT the archive (§8)
        |
L2  BACKFIELD ALLOCATION    Dirichlet over the available set, two channels:
                            (a) rush-attempt share   (b) pass-snap share
                            conditioned on availability; redistribution is a
                            DRAW from L2, not a rule applied after the fact
        |
L3  TOUCH CONVERSION        carries   = team RB rush attempts x rush share
                            targets   = RB pass snaps x targets-per-pass-snap
        |
L4  YARDAGE KERNEL          per-carry yardage drawn from a heavily pooled
                            distribution; team/OL component (yards before
                            contact) separated from the player residual
        |
L5  JOINT DRAWS STORED      full draws, never percentiles (CLAUDE.md, grounding)
```

Two structural commitments, both `DERIVED` from measurements above:

- **Redistribution lives inside L2, not after it.** Conditioning the allocation
  on the availability set is the only way the +3.82 mean / +5.67 median
  opportunity swing (§5.4) and its skew (§5.5) appear as *distributional* output
  rather than as a point adjustment.
- **The goal-line channel is a team rate, not a player role** (§3.3). There is no
  goal-line-back parameter.

### 7.2 Registry rows, in `v8/FEATURE_REGISTRY.md` vocabulary

Everything is EXPERIMENTAL or lower because **no NFL experiment has run**. That
is the registry's own rule and it applies here without exception.

| feature | denominator | proposed status | evidence / why not higher |
|---|---|---|---|
| RB rush-attempt share | team RB rush attempts | EXPERIMENTAL | split-half 0.926, week-ahead r 0.753 (§4.1, §4.3). No out-of-sample season |
| RB snap share | team run/pass scrimmage plays | EXPERIMENTAL | split-half 0.925 (§4.1). Denominator differs from PFR's by 1.57 snaps (§1.4) |
| RB pass-snap share | team RB pass snaps | EXPERIMENTAL | split-half 0.913 (§4.5) |
| targets per RB pass-snap | RB pass snaps | EXPERIMENTAL | split-half 0.369 (§4.5). **Not TPRR** (§1.5) |
| third-down / passing-down role residual | 3rd-down RB carries | EXPERIMENTAL | +13.3% OOS skill, residual r 0.436 (§3.3) |
| availability-conditioned reallocation | vacated share V | EXPERIMENTAL | 39 events (§5). Underpowered by construction |
| team yards-before-contact per carry | team RB carries | EXPERIMENTAL | corr +0.1811 with future YPC, ≥ own YPC (§6.3). Belongs to a team layer |
| RB yards per carry (own) | carries | EXPERIMENTAL | small but resolvable gain, +1.135 RMSE yards (§6.4) |
| **goal-line carry share (player)** | goal-line RB carries | **REJECTED** | +0.5% OOS skill, fitted weight 0.09, median 6 season carries (§3) |
| **goal-to-go carry share (player)** | goal-to-go RB carries | **REJECTED** | +0.0% OOS skill, fitted weight 0.00 (§3.3) |
| RB rushing success rate | carries | **REJECTED as a player feature** | split-half band includes zero; week-ahead R² −0.110 (§4.1, §4.3) |
| `receiving_broken_tackles` | — | **REJECTED — SOURCE EMPTY** | null rate 1.0000 on all 2,255 REG rows (§6.2) |
| targets per **route run** | routes run | **NOT AVAILABLE** | `route` is one value per play, the targeted receiver's (§1.5) |
| RYOE / NGS rushing | — | **UNKNOWN — assigned** | 404 under names tried; needs an outbox request (§6.2) |

### 7.3 Falsification experiments

Each states the metric, the split, the clustering and the multiplicity
correction **before** execution, per Rule 004a. Sample-size arithmetic is
`DERIVED` from `_GROUNDING.md`'s power note (r 0.11→0.25 needs ~377 games
independent, ~1,131 at threefold clustering) — NFL has 272 REG games per season
(`VERIFIED`, §1.3), so **anything needing that much power needs multiple
seasons, and every experiment below must say so up front.**

**RB-E1 — Does opportunity share beat efficiency, out of sample?**
*Kill condition:* on held-out 2025, a model using only forward-chained
opportunity share × pooled efficiency does **not** beat one using
forward-chained efficiency × pooled opportunity on RMSE of rushing yards.
*Metrics (frozen):* r, RMSE, MAE, calibration slope + intercept, CRPS, PIT,
90%/50% interval coverage — the full Rule-005 scorecard, never r alone.
*Split:* fit nothing on 2025; 2024 is development only.
*Clustering:* by game and by week, both reported; `DEFERRED / UNDERPOWERED`
rather than FAIL when the interval cannot resolve.
*Prediction:* passes easily. The §4.3 gap is 0.75 vs 0.11.

**RB-E2 — Is the goal-line-back rejection right?**
*Kill condition:* on 2025 + 2023, adding a player-specific goal-line share term
improves out-of-sample rushing-touchdown log score by more than the
Bonferroni-corrected threshold across the five situations tested in §3.3
(α = 0.05/5 = 0.01).
*Note in advance:* §3.1 says the median RB gets 6 goal-line carries a season, so
**two extra seasons roughly triples that to ~18**, which is still below any
plausible stabilisation point. This experiment is expected to return
`DEFERRED / UNDERPOWERED`, and that outcome must be recorded as such and not as
"no effect".

**RB-E3 — Does availability-conditioned reallocation beat ignoring availability?**
*Kill condition:* on out-of-sample absence events, an allocation model
conditioned on the availability set does not beat the naive "renormalise the
baseline shares" model on CRPS of each remaining back's opportunity count.
*Metric:* CRPS (needs full draws — L5 is a precondition, not an optimisation),
plus coverage of the 50/80/90 intervals, plus MAE.
*Clustering:* by event; 3,000-resample bootstrap, as in §5.3.
*Power, stated now:* 2024 yielded **39 events / 29 spells**. Three seasons gives
~90–120 events. `DERIVED`: with per-event MAE spread as measured
(CI half-width ≈ 0.034 on 39 events), separating two rules that differ by ~0.02
MAE needs roughly 4× the events, i.e. **about four seasons**. Say this before
running, not after.

**RB-E4 — Is the zero-history back handled?**
*Kill condition:* the model assigns a zero-history back a projection of exactly
zero in an out-of-sample week where he took ≥5 opportunities. §5.6 says this
arises in ~8.7% of team-weeks, so the test has adequate frequency in one season.
*This is a Class-A assertion test, not a skill test* — the stage must raise a
named error rather than emit a silent zero.

**RB-E5 — Does yards-before-contact belong to the team rather than the player?**
*Kill condition:* a model with a team-level before-contact term and **no**
player efficiency term is beaten out of sample by one with a player efficiency
term, on rushing-yard RMSE, clustered by player.
*Direct test of §6.3 and the interpretation offered in §6.4*, which is currently
`UNVERIFIED-RECALL` as an explanation.
*Confound to predeclare:* backs do not move between offences at random. Restrict
to within-season, or predeclare a team fixed effect.

**RB-E6 — Are the derived snap shares stable across vendors?**
*Kill condition:* participation-derived and PFR-derived snap share disagree by
more than the ±3-snap band measured in §1.4 on any out-of-sample season.
*Rationale:* not a model experiment. It is the input-manifest discipline
`CLAUDE.md` says MLB's M0 lacked — a content-hashed, cross-vendor assertion at
ingest, so that a silent schema change is caught by a named failure and not by a
model result nobody can reproduce.

---

## 8. Three things the rest of NFL-0 should take from this

1. **The archive cannot answer the redistribution question going forward.**
   The grounding brief's finding — `injuries_2024.csv` is a terminal Friday
   snapshot, one row per player-week — means §5's events are all measured
   *after* the fact. `DERIVED`: the question "how much did knowing on Wednesday
   that the starter was doubtful improve the projection?" is **not answerable
   from any historical file**, for RBs or anyone else. It requires live weekly
   capture starting from the next unplayed week. This is the RB-specific case
   for the brief's general warning, and it is the highest-value thing that can
   be started today rather than researched.

2. **Store full joint draws, and store them at the backfield level.** MLB's nine
   percentiles cannot support CRPS. The RB case is worse than the general case:
   §5.5 shows the interesting quantity is a **left-skewed, multi-modal
   distribution over a shared budget** (one back's gain is another's loss), so
   marginal percentiles per player would lose the correlation that makes the
   whole thing useful. The draws must be joint across the backfield, not
   per-player.

3. **The folk model and the data disagree in a specific, testable place.**
   Conventional analysis attributes rushing outcomes to the back and treats
   goal-line work and "next man up" as known structure. Measured here: goal-line
   role adds +0.5% (§3.3), next-man-up is the worst of five reallocation rules
   (§5.3), and the persistent part of efficiency tracks blocking rather than the
   back (§6.3). `DERIVED`: **if this project's RB layer has an edge, it is most
   likely to come from being distributionally honest about opportunity, not from
   a better efficiency estimate.**

---

## 9. Reproduction

All numbers came from throwaway scripts in the session scratchpad, run under
`python3.12` with `pandas 3.0.5` / `numpy 2.5.3` installed as described in §1.2.
They are evidence, not deliverables, and are deliberately not committed.

| script | produces |
|---|---|
| `s1_build.py` | column-subset slims of pbp and participation |
| `s2_join.py` | §1.3 join rates |
| `s3_route.py` | §1.5 route-column analysis |
| `s4_opp.py` | the player-game opportunity table |
| `s5_validate.py` | §1.4 PFR cross-check |
| `s6_dist.py` | §2 distributions |
| `s7_situ.py`, `s8_role.py`, `s9_role2.py` | §3 |
| `s10_rel.py`, `s11_relcmp.py`, `s12_fwd.py` | §4.1–4.3 |
| `s13_redist.py`, `s16_event2.py`, `s17_rules2.py` | §5 |
| `s18_adv.py`, `s19_adv2.py` | §6.1–6.3 |
| `s20_final.py` | §4.4, §5.6, team pie, FB note |
| `s21_shrink.py`, `s22_boot.py` | §6.4 |
| `s23_rec.py` | §4.5 |

Core definitions, so the numbers are rebuildable without the scripts:

- **Frame:** `season_type == 'REG'`, `play_type ∈ {'run','pass'}`,
  `two_point_attempt == 0`, `posteam` non-null → 33,335 plays, 272 games,
  544 team-games.
- **Player-play:** explode participation `offense_players` and
  `offense_positions` (`;`-delimited, always 11, always aligned).
- **Position:** modal `offense_positions` label for that player within that
  team-game.
- **snap share** = player scrimmage plays / team scrimmage plays.
- **carry share (RB)** = player rush attempts / sum of RB rush attempts on that
  team-game. Rush attempts from pbp `rush_attempt == 1` and non-null
  `rusher_player_id`.
- **target share** = player targets / team targets, targets from non-null
  `receiver_player_id`.
- **pass snaps** = scrimmage plays with `play_type == 'pass'` (sacks included).
- **Situations:** goal-line `yardline_100 <= 5`; goal-to-go `goal_to_go == 1`;
  short-yardage `ydstogo <= 2 and down in (3,4)`; two-minute
  `half_seconds_remaining <= 120`; third down `down == 3`.
- **Split-half:** 200 random per-player splits of that player's games, Pearson r
  between halves, Spearman–Brown `2r/(1+r)`; seeds fixed
  (`numpy.random.default_rng(20260906)` in `s11`, `(5)` in `s23`, `(3)` in
  `s19`).
- **Forward-chained:** prediction for game *i* uses games `0..i-1` only.
- **Absence events:** `report_status == 'Out'` in `injuries_2024.csv`, matched on
  `(team, week, gsis_id)`; baseline = the focal back's last ≤3 games in which he
  played; V ≥ 0.25 required; teammate baselines computed over those same games.
