# W7 — Injury, news and availability intelligence

**Worker:** W7, NFL Greenfield Architecture research pass
**Date of measurement:** 2026-09-06 (all figures below measured in this container on this date)
**Scope:** research and architecture only. No production model code was written. No file
outside this one was modified.
**Governing documents read before starting:** `nfl/research/_GROUNDING.md` (in full),
`v8/V8_SYSTEM_CONSTITUTION.md` Rules 001 and 002, `v8/V8_FAILURE_TAXONOMY.md` Class B,
`docs/AGENT_PROTOCOL.md` (Rule 5 and DEC-029), `CLAUDE.md`.

**Labelling.** Every substantive claim carries exactly one of `VERIFIED` (a command was run
here and is shown), `DERIVED` (arithmetic or logic from something VERIFIED, derivation shown),
`UNVERIFIED-RECALL` (believed from training, not checked here).

**Headline, stated once so it is not buried.** `VERIFIED` — an official NFL game-status
designation is not a probability of playing, and the gap is not small. On the final (Friday)
report in 2024, `Out` played 0.09% of the time and `Doubtful` played 0.00% of the time, while
`Questionable` played 65.50% of the time and a player listed on the report with *no* game
designation played 94.30% of the time. `Questionable` is the only designation that carries
material uncertainty, and it carries almost all of it. `DERIVED` — a system that treats
`Questionable` as "probably plays" is wrong about one player in three, and a system that treats
it as a binary at all discards the second and larger half of the problem, which is *role given
active*: among offensive skill players who were `Questionable` **and did play**, median snap
share was 53% of their team's offensive snaps against 53% for players not on the injury report
at all — but the *dispersion* is where the money is, with p10 = 0.12 and p90 = 0.90.

---

## 0. Data used, and the reason the numbers below can be trusted

### 0.1 Files

`VERIFIED` — all from the shared cache at
`/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-4781-5a10-ae09-ef74590f8116/scratchpad`,
except where a download is noted.

| File | Rows (excl. header) | Provenance |
|---|---|---|
| `inj2024.csv` | 6,215 | pre-cached by the lead; `injuries/injuries_2024.csv` |
| `snaps2024.csv` | 26,615 | pre-cached; `snap_counts/snap_counts_2024.csv` |
| `players_players.csv` | 24,828 | pre-cached; `players/players.csv` — the ID crosswalk |
| `depth_charts_depth_charts_2024.csv` | 37,312 | pre-cached |
| `schedules_games.csv` | all seasons ≤2026 | pre-cached; used for kickoff times and bye detection |
| `inj2025.csv` | 6,068 | **downloaded by W7** (695,623 B, authorised) |
| `snaps2025.csv` | 26,612 | **downloaded by W7** (2,401,193 B) |

**Declared deviation from my brief.** `VERIFIED` — I was authorised to download
`injuries_2025.csv` and `depth_charts_2024.csv`. I additionally downloaded
`snap_counts_2025.csv` (2.40 MB) because `injuries_2025.csv` is useless without it, and I
temporarily downloaded `depth_charts_2026.csv` (47.6 MB — **not** small, contrary to the 2024
file's 3.4 MB, because the schema changed) and **deleted it after extracting §3.3**. Peak extra
disk 50 MB against 30 GB free (`df -h /tmp` → `252G total, 30G avail`). No pbp or participation
file was re-downloaded. Recording this because an undeclared deviation is a governance defect
even when it is harmless.

### 0.2 The join, and its honest success rate

The ID mismatch named in my brief is real: `injuries` keys on `gsis_id`, `snap_counts` keys on
`pfr_player_id` plus a display name. `players.csv` carries both.

`VERIFIED` — crosswalk coverage:

```
python3.12 - <<'EOF'
import pandas as pd
pl=pd.read_csv('players_players.csv',dtype=str); sub=pl[pl.gsis_id.notna()&pl.pfr_id.notna()]
inj=pd.read_csv('inj2024.csv',dtype=str)
inj['pfr']=inj.gsis_id.map(dict(zip(sub.gsis_id,sub.pfr_id)))
print(inj.pfr.notna().sum(), len(inj), inj[inj.pfr.isna()].gsis_id.nunique())
EOF
```

- `players.csv`: 24,828 rows, 22,653 carry both `gsis_id` and `pfr_id`, **zero duplicate
  `gsis_id`, zero duplicate `pfr_id` among those**. It is a clean 1:1 map.
- 6,213 of 6,215 injury rows map to a `pfr_id` = **99.97%**. Exactly one distinct player fails
  (`00-0037428`, Alec Anderson, G, BUF).
- 2025: 99.75% map.

Join executed twice, independently, and cross-checked:

| Join key | Matched rows | Rate |
|---|---|---|
| `(season, week, team, pfr_id)` | 4,188 | 67.39% |
| `(season, week, team, normalised name)` | 4,023 | 64.73% |
| **Union (the one used)** | **4,190** | **67.42%** |

`VERIFIED` — pfr-only 167, name-only 2, both 4,021, neither 2,025. On all 4,021 rows matched by
**both** keys, `offense_snaps` agreed **4,021 / 4,021**. Name normalisation was
NFKD → ASCII → lowercase → strip non-alpha.

**Is the 32.6% non-match a join failure or a genuine "did not play"?** This is the Class A trap
(absence read as a result), and it has to be answered before any number below means anything.
Two checks:

1. `VERIFIED` — **bye weeks are not the cause.** Every one of the 6,215 injury rows names a
   team that actually played a game that week (checked against `schedules_games.csv`; count of
   rows whose team had no game = **0**).
2. `VERIFIED` — **the crosswalk is proven for 97.4% of the non-matches.** Of the 2,025
   unmatched rows, 1,973 belong to a player who appears in `snaps2024.csv` *somewhere else in
   the season*, which proves the identifier resolves and the non-match is a genuine absence
   from that week's snap counts. Only **52 rows (0.84% of the file), covering 20 distinct
   players**, are ambiguous between "never played all season" and "identifier defect".

`DERIVED` — maximum contamination of every P(play) figure below is **±0.84 percentage points**,
and the true figure is smaller because most of those 20 players are injury-report regulars who
genuinely never played. Three of the four cells are far from any decision boundary, so this
does not change a conclusion.

3. `VERIFIED` — a further sanity floor: among rows with **no designation and full practice
   participation** — a population that should be near-universally available — the match rate is
   **95.66%** (2,534/2,649). The residual 4.3% is healthy scratches, gameday actives who took
   zero snaps, and the ≤0.84% join noise.

`VERIFIED` — "played" is defined throughout as *appears in `snap_counts` for that
season-week-team with at least one snap*. Exactly **1 row in 26,615** in the whole snap file has
offense+defense+ST snaps = 0, so `snap_counts` membership and "took a snap" are the same
predicate. **0 of 4,190** matched injury rows had zero total snaps.

### 0.3 Clustering

`VERIFIED` — every confidence interval below is a **non-parametric bootstrap resampling
`(team, week)` clusters**, 1,500–2,000 replicates, `numpy.random.default_rng` seeded
(20260906 / 7 / 3 / 42 / 11 as noted in the scripts). This follows `CLAUDE.md` rule 9 and the
grounding brief's finding that naive binomial SEs understated MLB prop uncertainty ~3×. Players
within a team-game share an opponent, a game script, a coaching staff and a single inactives
decision, so a naive binomial SE here is not merely optimistic, it is measuring the wrong
population. **No naive SE appears anywhere in this document.**

---

## 1. The designation-to-participation mapping — the primary deliverable

### 1.1 P(played | report_status)

`VERIFIED`. 2024, all game types (REG + postseason), all positions. Denominator = rows on the
official injury report carrying that designation.

| `report_status` | n | played | **P(play)** | 95% CI (cluster = team-week) | clusters |
|---|---:|---:|---:|---|---:|
| `Out` | 1,116 | 1 | **0.0009** | [0.0000, 0.0028] | 492 |
| `Doubtful` | 194 | 0 | **0.0000** | [0.0000, 0.0000] | 133 |
| `Questionable` | 1,513 | 991 | **0.6550** | [0.6297, 0.6786] | 479 |
| *(no designation, but on the report)* | 3,386 | 3,193 | **0.9430** | [0.9336, 0.9520] | 558 |
| `Note` | 6 | 5 | 0.8333 | [0.2500, 1.0000] | 4 |

`VERIFIED` — **the single `Out` player who played is not a counter-example.** It is Kyle Van
Noy, LB, BAL, week 1, `report_primary_injury = "gameday concussion protocol evaluation"`,
`date_modified = 2024-09-06T03:11:40Z`. BAL's week-1 kickoff was 2024-09-06T00:20Z, so that row
was stamped **2.86 hours after kickoff** — it is an in-game downgrade written back into the
archive, not a pre-game `Out` who suited up. It is the only row in the entire file stamped after
kickoff (**0.02%**). Excluding it, pre-game `Out` played **0 / 1,115**.

`VERIFIED` — **out-of-sample replication on 2025**, same code, a season never inspected while
forming these numbers:

| `report_status` | 2024 P(play) | 2025 P(play) | 2025 n | 2025 95% CI |
|---|---:|---:|---:|---|
| `Out` | 0.0009 | **0.0000** | 1,396 | [0.0000, 0.0000] |
| `Doubtful` | 0.0000 | **0.0000** | 106 | [0.0000, 0.0000] |
| `Questionable` | 0.6550 | **0.6518** | 1,281 | [0.6230, 0.6815] |
| *(none)* | 0.9430 | **0.9385** | 3,285 | [0.9288, 0.9474] |

`DERIVED` — the `Questionable` rate moved 0.0032 across two independent seasons totalling 2,794
observations, well inside either CI. This mapping is stable at the season level. That is not the
same as saying it is stable *within* a season, by team, or by injury type — see §1.5 and §6.

`UNVERIFIED-RECALL` — the NFL's own rule book defines `Out` as "will not play", `Doubtful` as
"unlikely to play, approximately 25%", `Questionable` as "uncertain, approximately 50%". **The
measured `Doubtful` rate is 0.0000 on n = 300 across two seasons, not 0.25, and the measured
`Questionable` rate is 0.655, not 0.50.** If a design ever uses the league's nominal
percentages, it will be wrong by 25 points on `Doubtful` and 15 points on `Questionable`. Do
not use them. This recalled definition is stated only to name what the measurement contradicts.

### 1.2 P(played | report_status × practice_status)

`VERIFIED`.

| report | practice | n | played | P(play) | 95% CI (cluster) |
|---|---|---:|---:|---:|---|
| `Out` | Did Not Participate | 938 | 0 | 0.0000 | [0.0000, 0.0000] |
| `Out` | Limited | 96 | 0 | 0.0000 | [0.0000, 0.0000] |
| `Out` | Full | 70 | 0 | 0.0000 | [0.0000, 0.0000] |
| `Doubtful` | Did Not Participate | 101 | 0 | 0.0000 | [0.0000, 0.0000] |
| `Doubtful` | Limited | 65 | 0 | 0.0000 | [0.0000, 0.0000] |
| `Doubtful` | Full | 28 | 0 | 0.0000 | [0.0000, 0.0000] |
| **`Questionable`** | **Did Not Participate** | **248** | 129 | **0.5202** | **[0.4537, 0.5844]** |
| **`Questionable`** | **Limited** | **848** | 572 | **0.6745** | **[0.6398, 0.7065]** |
| **`Questionable`** | **Full** | **394** | 277 | **0.7030** | **[0.6581, 0.7482]** |
| *(none)* | Did Not Participate | 250 | 198 | 0.7920 | [0.7338, 0.8473] |
| *(none)* | Limited | 487 | 461 | 0.9466 | [0.9050, 0.9774] |
| *(none)* | Full | 2,649 | 2,534 | 0.9566 | [0.9480, 0.9646] |

`VERIFIED` — 2025 replication of the `Questionable` row: DNP 0.5906 (n = 171), Limited 0.6491
(n = 758), Full 0.6947 (n = 321). The monotone ordering DNP < Limited < Full holds in both
seasons; the DNP level moved +0.07 between them.

`VERIFIED` — 70 players were listed `Out` **while practising in full**, and every one of them
sat. 28 `Doubtful` players practised in full and every one sat. Practice participation therefore
**cannot override** an `Out` or `Doubtful` designation. This is a hard structural fact and it
should be encoded as a constraint, not learned.

### 1.3 A second denominator: the depth chart

`VERIFIED` — §1.1's denominator is "on the injury report", which conditions on being injured.
Joining the 2024 depth chart (31,888 distinct week-team-player entries) gives an unconditional
denominator:

| status | n | P(recorded a snap) | 95% CI (cluster) |
|---|---:|---:|---|
| **not on the injury report at all** | 26,413 | **0.7794** | [0.7550, 0.8032] |
| on report, no designation | 3,203 | 0.9491 | [0.9393, 0.9584] |
| `Questionable` | 1,198 | 0.6861 | [0.6582, 0.7131] |
| `Doubtful` | 165 | 0.0000 | [0.0000, 0.0000] |
| `Out` | 903 | 0.0011 | [0.0000, 0.0034] |

`DERIVED` — **"not on the report" scores *lower* (0.779) than "on the report with no
designation" (0.949), and that is not a paradox.** The depth chart carries third-string players
who are healthy and simply never dress; the injury report carries rotation regulars. The
denominators describe different populations. Holding depth position fixed removes the artefact:

| depth_team | not on report | `Questionable` |
|---|---|---|
| 1 (starter) | **0.8569** [0.8268, 0.8859] (n=12,258) | **0.7060** [0.6718, 0.7395] (n=738) |
| 2 | 0.7396 [0.7166, 0.7606] (n=10,403) | 0.6805 [0.6288, 0.7331] (n=338) |
| 3 | 0.6367 [0.6152, 0.6589] (n=3,752) | 0.5820 [0.4959, 0.6641] (n=122) |

`DERIVED` — the practical lesson: **P(active) is not a function of the designation alone.** A
`Questionable` starter is more likely to play (0.706) than a *healthy* third-stringer (0.637).
Any availability model must condition on depth/role as well as designation, and any evaluation
that pools them is measuring roster construction, not injury.

`VERIFIED` — the 0.856 figure for healthy depth-chart starters is itself well below 1.0, which
means the 2024 depth chart is a noisy roster proxy, not a gameday-active list. It is a
substitute for the weekly-roster `status` field, which I did not download. See assignment N7-A1.

### 1.4 Snap share **given played** — the half of the problem the designation ignores

This is the part my brief singles out: a `Questionable` WR who runs 35% of snaps is a different
object from one who runs 90%.

Two measures are reported, because the absolute one is misleading on its own. A 60% snap share
is routine for an RB2 and catastrophic for a WR1, so the informative quantity is the ratio to
the player's **own** healthy baseline.

`VERIFIED` — baseline construction: for each skill-position player (QB/RB/WR/TE/FB), the
**median `offense_pct` across weeks in which he appears in `snap_counts` and has no injury-report
row at all**, requiring ≥ 4 such weeks and a baseline ≥ 0.15 to avoid dividing by a
deep-reserve denominator. 388 players qualify. The reference distribution is those same players
in those same off-report weeks (n = 4,691 player-weeks).

**Relative snap share (actual ÷ own healthy baseline), skill positions, given played:**

| cell | n | p10 | p25 | **median** | p75 | p90 | P(<0.75×) | P(<0.50×) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **not on report (reference)** | 4,691 | 0.56 | 0.84 | **1.00** | 1.14 | 1.44 | 0.181 | 0.077 |
| on report, no designation | 718 | 0.61 | 0.84 | **1.00** | 1.15 | 1.36 | 0.181 | 0.071 |
| **`Questionable` (all)** | 225 | 0.36 | 0.62 | **0.90** | 1.08 | 1.24 | **0.342** | **0.178** |
| `Questionable` / Full | 68 | 0.30 | 0.62 | 0.85 | 1.02 | 1.30 | 0.338 | 0.206 |
| `Questionable` / Limited | 125 | 0.43 | 0.63 | 0.93 | 1.10 | 1.23 | 0.312 | 0.144 |
| `Questionable` / DNP | 29 | 0.22 | 0.44 | 0.78 | 1.04 | 1.23 | 0.483 | 0.276 |

**Absolute `offense_pct`, same pool, given played:**

| cell | n | p10 | p25 | median | p75 | p90 |
|---|---:|---:|---:|---:|---:|---:|
| not on report (reference) | 4,691 | 0.16 | 0.30 | 0.53 | 0.80 | 0.97 |
| on report, no designation | 718 | 0.24 | 0.46 | 0.69 | 0.88 | 0.99 |
| `Questionable` (all) | 225 | 0.12 | 0.27 | 0.53 | 0.78 | 0.90 |
| `Questionable` / DNP | 29 | 0.07 | 0.19 | 0.39 | 0.81 | 0.88 |

**By position, `Questionable` and played, relative measure:**

| position | n | median | p10 | p90 | P(<0.75×) | reference median | reference P(<0.75×) |
|---|---:|---:|---:|---:|---:|---:|---:|
| QB | 10 | 1.00 | 0.25 | 1.00 | 0.200 | 1.00 | 0.122 |
| **RB** | 58 | **0.82** | 0.39 | 1.22 | **0.466** | 1.00 | 0.211 |
| **WR** | 118 | **0.95** | 0.41 | 1.41 | **0.288** | 1.00 | 0.177 |
| **TE** | 36 | **0.83** | 0.33 | 1.20 | **0.361** | 1.00 | 0.187 |

`DERIVED` — three conclusions, all of which bear directly on prop pricing:

1. **The median is nearly uninformative; the left tail is where the information is.** A
   `Questionable` WR who plays has a median 0.95× his normal share — a 5% haircut, invisible in
   a point projection — but a 28.8% chance of falling below 0.75× and a 14.4% chance of falling
   below 0.50×, against 17.7% and 7.4% for a healthy player. **Playing a `Questionable` player
   at his normal role is right most of the time and catastrophically wrong 15% of the time.** A
   point estimate cannot express this. A distribution can. This is the single strongest
   argument in my scope for the joint-draw storage the grounding brief already requires.
2. **RB is the most affected position and QB the least.** RB `Questionable`-and-played sits at
   0.82× with a 46.6% chance of dropping under 0.75× — more than double the healthy rate. QB is
   effectively binary: he plays every snap or he does not play.
3. `VERIFIED` — the **"no designation" cell is statistically indistinguishable from a healthy
   player on the relative measure** (median 1.00 vs 1.00; P(<0.75×) 0.181 vs 0.181). Being
   *named* on the injury report without a game designation carries **no role penalty at all**
   once you condition on playing, even though it carries a small activity penalty
   (0.943 vs the depth-chart-conditioned reference). Treating "appears on the injury report" as
   a risk flag, as many naive systems do, would be a pure false positive here.

### 1.5 What the designation hides that the injury *reason* reveals

`VERIFIED` — `P(play | Questionable, primary injury)`, 2024, cells with n ≥ 30:

| injury | n | P(play) | | injury | n | P(play) |
|---|---:|---:|---|---|---:|---:|
| Foot | 59 | 0.881 | | Illness | 62 | 0.661 |
| Hip | 55 | 0.855 | | Ankle | 208 | 0.659 |
| Shoulder | 105 | 0.724 | | Concussion | 42 | 0.619 |
| Back | 74 | 0.703 | | Groin | 77 | 0.584 |
| Toe | 34 | 0.677 | | Quadricep | 32 | 0.594 |
| Knee | 277 | 0.672 | | **Hamstring** | **139** | **0.554** |
| Neck | 37 | 0.649 | | **Calf** | **66** | **0.545** |

`DERIVED` — the spread from Hamstring (0.554) to Foot (0.881) is **0.327**, larger than the
entire practice-status spread within `Questionable` (0.183, §2). Injury type is a stronger
signal than practice participation. n per cell is small and no multiplicity correction has been
applied, so this is a **hypothesis for pre-registration, not an established effect** — but it
is the right hypothesis to register first.

### 1.6 The `Not injury related — resting player` trap

`VERIFIED` — 583 rows in 2024 carry `practice_primary_injury = "Not injury related - resting
player"` (679 rows match "Not injury related" in any form). These are veteran rest days, not
injuries, and they invert the DNP signal completely:

| cell | n | P(play) |
|---|---:|---:|
| Did Not Participate, **rest day** | 193 | **0.8756** |
| Did Not Participate, **genuine injury** | 1,344 | **0.1176** |
| *(no designation)* + DNP, rest day | 170 | **0.9471** |
| *(no designation)* + DNP, genuine injury | 80 | **0.4625** |

`DERIVED` — the risk difference inside the *same* `(none) × DNP` cell is **+0.485**, more than
2.6× the entire DNP-vs-Full practice effect. **A model that reads `practice_status` without
reading the reason field will be badly wrong on exactly the highest-value players**, because
rest days are given disproportionately to established veterans. This is the most actionable
finding in §1 after the headline table, and it costs nothing to implement: it is a string match
on a field already present.

---

## 2. Does practice participation add information beyond the designation? — measured

My brief asks for the lift to be quantified rather than asserted. It was, twice, honestly, and
**the answer is different for the two questions.**

### 2.1 Lift on P(active)

`VERIFIED` — leave-one-week-out cross-fitted cell means with shrinkage k = 5 toward the
training-fold global rate, so no row is scored by a model fitted on itself. Full report
population (n = 6,209 in the four real statuses):

| model | log loss | Brier |
|---|---:|---:|
| intercept only | 0.6317 | 0.2199 |
| `report_status` | 0.2791 | 0.0847 |
| `report_status × practice_status` | **0.2745** | **0.0834** |

`DERIVED` — the designation alone removes **0.3526 nats (55.8%)** of the log loss. Adding
practice status removes a further **0.0046 nats — 1.3% of what the designation already
achieved.** The overwhelming majority of the signal is in the designation.

`VERIFIED` — restricted to `Questionable` (n = 1,513), where the designation has already been
conditioned on and practice status could matter most:

```
intercept only     logloss=0.6450  brier=0.2263
+ practice_status  logloss=0.6386  brier=0.2233
reduction          0.0065 nats (1.00%)   Brier skill score 0.0134
cluster(team-week) bootstrap 95% CI on the reduction: [-0.0000, +0.0129]
```

`VERIFIED` — but the two-cell contrast is unambiguous:

```
Q / Did Not Participate  P(play) = 0.5202  (n=248)
Q / Full Participation   P(play) = 0.7030  (n=394)
risk difference          +0.1829,  cluster 95% CI [+0.1059, +0.2589]
```

`DERIVED` — **these two results are not in conflict and both must be reported.** The
DNP-vs-Full contrast is real and large (CI excludes zero comfortably). The *aggregate* log-loss
gain is small and its CI touches zero because the majority cell — `Limited`, 848 of 1,513 rows
— sits at 0.6745, almost exactly the pooled `Questionable` rate of 0.6550. Practice status
usefully separates the tails and says nothing about the middle, and 56% of `Questionable`
players are in the middle. Under Rule 005, quoting only the +0.183 would be the cherry-pick.

**Verdict:** `practice_status` is worth carrying as a feature and is worth **capturing** live,
but it is not the lever. On the evidence here, ranked by measured lift on P(active):
designation (0.353 nats) ≫ injury reason and the rest-day flag (§1.5, +0.485 risk difference in
one cell) > practice status (0.0065 nats).

### 2.2 Lift on snap share given active — **none detected**

`VERIFIED` — n = 222 skill-position `Questionable`-and-played rows with a usable baseline.
Leave-one-week-out cross-fitted median predictions, MAE on the relative snap-share ratio:

```
MAE, pooled median            = 0.3152
MAE, practice-status medians  = 0.3183
reduction                     = -0.0031   cluster(team-week) 95% CI [-0.0107, +0.0042]
```

`DERIVED` — **practice status does not improve prediction of role given active.** The point
estimate is negative (worse) and the interval contains zero. Per Rule 001 and `CLAUDE.md` rule
8, this is `DEFERRED / UNDERPOWERED` at n = 222, **not** a demonstration that no effect exists —
the interval is wide enough to hide an effect of ±0.01 MAE. It is stated as a refusal to claim
the lift, not a claim of no lift. A confirmatory answer needs roughly an order of magnitude more
`Questionable`-and-played skill-position rows than one season provides. (Scipy is not installed
in this container, so no parametric test was run; the cluster bootstrap is the whole inference.)

---

## 3. The vintage problem

### 3.1 Independent confirmation of the grounding brief's finding

`VERIFIED`, reproduced from the raw file rather than taken on trust:

```
python3.12 - <<'EOF'
import pandas as pd
inj=pd.read_csv('inj2024.csv',dtype=str)
print(len(inj), inj.groupby(['season','week','gsis_id']).ngroups)
print(pd.to_datetime(inj.date_modified,utc=True).dt.day_name().value_counts().to_dict())
EOF
```

- 6,215 rows, **6,213 distinct `(season, week, gsis_id)`**. Only 2 player-weeks carry >1 row.
  **Confirmed.**
- `date_modified` weekday distribution across the whole season: **Friday 4,818 · Saturday 509 ·
  Wednesday 461 · Thursday 351 · Tuesday 51 · Sunday 22 · Monday 3.** 77.5% of all rows are
  stamped Friday. **Confirmed: the archive holds the final report, not the cascade.**
- `VERIFIED`, and this is new: measured against actual kickoff (`schedules_games.csv`
  `gameday` + `gametime`, localised America/New_York → UTC), the median row is stamped
  **47.2 hours before kickoff**, p5 = 28.8 h, p95 = 54.8 h. **99.98% of rows precede kickoff.**
  So the archive is not merely "one row per player-week" — it is one row per player-week
  **located tightly around Friday afternoon**, roughly two days before a Sunday game.

`VERIFIED` — the two duplicated player-weeks are the entire visible evidence of the cascade in
the whole season, and both are the same event:

| week | team | player | status | `date_modified` |
|---|---|---|---|---|
| 15 | HOU | Cade Stover, TE | `Questionable` | 2024-12-15T03:34:33Z |
| 15 | HOU | Cade Stover, TE | **`Out`** | 2024-12-15T14:17:06Z |
| 15 | NYJ | Tyler Conklin, TE | `Questionable` | 2024-12-14T20:55:19Z |
| 15 | NYJ | Tyler Conklin, TE | **`Out`** | 2024-12-15T13:57:00Z |

`DERIVED` — both are `Questionable` → `Out` downgrades on the morning of the game, 10.7 and
17.0 hours apart. This is precisely the transition worth the most money and it survives in the
archive **twice in 6,215 rows**, evidently by accident. Everywhere else, the earlier vintage was
overwritten.

### 3.2 A second, worse problem the brief did not have: the 2025 schema dropped the clock

`VERIFIED`:

```
2024 header: season,game_type,team,week,gsis_id,...,practice_status,date_modified
2025 header: season,season_type,game_type,team,week,gsis_id,...,practice_status
```

`injuries_2025.csv` **has no `date_modified` column at all** and adds `season_type`. 6,068 rows,
6,068 distinct player-weeks — still exactly one row per player-week.

`DERIVED` — this is a Constitution Rule 002 violation baked into the upstream source: for 2025
onward the archive delivers a status with **no retrieval timestamp, no source timestamp and no
effective date beyond the week integer**. Under Rule 002 as written ("a field without them does
not enter the model"), 2025 injury rows are not admissible as a dated feature without the
consumer supplying its own clock. It is also a Class C hazard (declaration drift: the same
dataset, two incompatible shapes, nothing comparing them) and a Class D hazard (an ingest that
silently `KeyError`s or, worse, silently fills `None`, depending on the reader).

`DERIVED` — **corollary that matters more than the inconvenience:** the argument "we can
backfill vintages later from the archive" is now false in two independent ways. The 2024 archive
lost the cascade by overwriting; the 2025 archive additionally lost the ability to tell you
*when* the surviving row was written.

### 3.3 What the depth-chart feed proves is possible — and already happening

`VERIFIED` — an unexpected and materially useful discovery. The `depth_charts` release changed
schema between 2024 and 2025:

```
depth_charts_2023: season,club_code,week,game_type,depth_team,...   (weekly)
depth_charts_2024: season,club_code,week,game_type,depth_team,...   (weekly)
depth_charts_2025: dt,team,player_name,espn_id,gsis_id,pos_grp_id,pos_grp,pos_id,pos_name,pos_abb,pos_slot,pos_rank
depth_charts_2026: dt,team,player_name,espn_id,gsis_id,pos_grp_id,pos_grp,pos_id,pos_name,pos_abb,pos_slot,pos_rank
```

`VERIFIED` — `depth_charts_2026.csv` (47,641,094 B, 501,068 rows, fetched and then deleted)
contains **170 distinct `dt` values across 168 distinct dates, running 2026-03-22T06:38:42Z →
2026-09-06T11:29:30Z** — i.e. up to and including this morning. It is a **daily vintage series**
for all 32 teams, keyed `(dt, team, gsis_id, pos_abb)`, carrying `pos_rank` and `pos_slot`.

`DERIVED` — three consequences:

1. **The vintage architecture this project needs already exists upstream for role, and only for
   role.** Injuries are the gap. Any proposal that says "vintaged data is impractical" is
   contradicted by a feed that is doing it daily right now.
2. **Daily role vintages for 2025 and 2026 are retrievable from this container today** and are
   *not* subject to the "capture it live or lose it" clock. That is a genuine reprieve on one of
   the two axes.
3. `VERIFIED` — measured daily churn in offensive skill depth ranks (`pos_grp = "3WR 1TE"`,
   `pos_abb ∈ {QB, RB, WR, TE}`), last 20 daily transitions to 2026-09-06:

   | date | entries | `pos_rank` changed | % | added | dropped |
   |---|---:|---:|---:|---:|---:|
   | 2026-08-29 | 843 | 8 | 0.95 | 0 | 6 |
   | **2026-08-30** | 804 | 54 | **6.73** | 2 | 41 |
   | **2026-08-31** | 676 | 153 | **22.77** | 4 | **132** |
   | **2026-09-01** | 567 | 77 | **13.87** | 12 | 121 |
   | 2026-09-02 | 570 | 7 | 1.24 | 4 | 1 |
   | 2026-09-06 | 563 | 0 | 0.00 | 0 | 1 |

   Mean over the 20 transitions: **3.86% of ranks change per day**, 3.1 entries added and 17.4
   dropped. The 22.77% spike on 2026-08-31 is the 53-man cutdown. `DERIVED` — a weekly snapshot
   of this feed would have compressed a 132-player roster purge and a 23% rank churn into a
   single row per player, exactly as the injury archive does. The daily series is not
   decoration.

### 3.4 Specification for a live weekly capture

`DERIVED` throughout — this is design, built on the measurements above. Written so the networked
agent can implement it without a second conversation.

**Principle.** The capture is an **append-only vintage log**. It never updates a row. Two
captures of the same player-week with the same content produce two rows differing only in
`retrieved_at`, and that is correct and required, because "unchanged at 14:00" is a
measurement, not a duplicate. `CLAUDE.md`'s "never overwrite Tuesday with Sunday" is enforced
by making update physically unavailable, not by remembering not to do it.

**Cadence.** `VERIFIED` inputs to this: 2026 REG week 1 contains games on Wednesday
2026-09-09, Thursday 2026-09-10, Sunday 2026-09-13 and Monday 2026-09-14
(`schedules_games.csv`, season 2026, game_type REG, week 1). `DERIVED` — the cadence must
therefore be anchored to **each game's kickoff**, not to a nominal Sunday, because a Thursday
game's Friday-equivalent report is Tuesday. Minimum viable schedule, per team, per game:

| capture | when | what it pins down |
|---|---|---|
| `T-6d` | first practice-report day for that game (Mon for a TNF game, Wed for Sun/Mon) | the opening practice vintage; the one the archive never keeps |
| `T-5d`, `T-4d` | each subsequent practice day | the mid-week trajectory (improving vs deteriorating) |
| `T-2d` | final report publication (Friday for a Sunday game) | **the vintage the archive already has** — capture it anyway, as the reconciliation key |
| `T-1d` | Saturday | Saturday designations and elevations |
| `T-3h` | ~90 min before the inactives deadline, then at it | the inactives list — resolves `Questionable` to 0/1 |
| `T+0` | kickoff | seals the vintage log for that game |

Hourly polling between `T-6d` and `T+0` is better and costs little; the table is the floor. Any
capture that runs only once per week reproduces the defect being fixed.

**Keys.** Natural key of a vintage row:
`(season, season_type, week, team, gsis_id, source_id, retrieved_at)`. `gsis_id` is the join
spine — `VERIFIED` at 99.97% coverage against `players.csv` in §0.2 — and every row must also
carry the raw source-native identifier so a crosswalk failure is visible rather than silent.
The **game** must be an explicit column (`nflverse_game_id` or `(week, team, opponent)`), never
inferred from the week, because week ≠ game for teams with a bye or a flexed slot.

**Timestamps.** Five clocks kept apart exactly as `sportsplatform/governance/provenance.py` requires
(Rule 002), with no unqualified age anywhere:

| clock | for an injury report |
|---|---|
| `source_timestamp` | the publisher's own stamp — the `date_modified` equivalent; **null for the 2025+ nflverse schema, and that must be recorded as null, not backfilled** |
| `retrieved_at` | when the bytes arrived at our process |
| `cache_timestamp` | if served from cache, the age of the cache entry — never rewritten on re-read (this is the exact V7 weather defect) |
| `generated_at` | when we parsed and wrote the vintage row |
| `effective_for_date` | the game date the report governs |

Every raw response is written to disk **before parsing**, with its HTTP status, byte count and
headers — the `oddsclient.py` discipline `CLAUDE.md` explicitly says is worth keeping.

**The five-state vocabulary. This is the part that has already cost this project a live batch.**
`v8/V8_FAILURE_TAXONOMY.md` Class B, instance B1: *"lineups have not posted yet" filed as
`fatal_bug` because there was no `DEFERRED` — the expected state of most of a slate aborted the
first live batch.* The NFL analogue is not a hypothetical: **on Tuesday there is no injury
report, and there is not supposed to be one.**

| condition | state | code | reason / closes when |
|---|---|---|---|
| report fetched, parsed, ≥1 row | `PASS` | — | value returned |
| report not yet published for this game-week | **`DEFERRED`** | `REPORT_NOT_YET_PUBLISHED` | **stays owed**; closed by the next successful capture, or by `T+0` after which it converts to `FAIL` |
| team has published, this player is not on it | `NOT_APPLICABLE` | `PLAYER_NOT_ON_REPORT` | reason mandatory: absence from a *published* report is the informative state "no designation" and must be stored as such, **not as a missing row** |
| team is on a bye this week | `NOT_APPLICABLE` | `TEAM_ON_BYE` | reason mandatory |
| source returned 200 with zero rows | **`FAIL`** | `EMPTY_PAYLOAD_200` | never `NOT_APPLICABLE`; this is Class A |
| source returned non-200 / timeout | `FAIL` | `SOURCE_HTTP_<code>` | |
| network unavailable to this agent | `BLOCKED` | `NO_EGRESS` | names what is missing; per DEC-029, **assigned** if another agent has egress |
| `gsis_id` unresolvable | `FAIL` | `IDENTIFIER_UNMAPPED` | never drop the row (Class C2: the alias table existed and was never applied) |
| inactives deadline passed, list absent | `FAIL` | `INACTIVES_MISSING` | |

`DERIVED` — the two states that will actually be got wrong are `DEFERRED` and
`NOT_APPLICABLE`. Tuesday's empty report is `DEFERRED` and must remain **owed** until Wednesday
closes it; a player absent from a report that *did* publish is `NOT_APPLICABLE` with the reason
`PLAYER_NOT_ON_REPORT`, and it is a **positive observation worth 0.943 P(play)** (§1.1), so
storing it as a missing row destroys the largest cell in the table. Those two look identical to
a naive reader — both are "no row for this player" — and they mean opposite things.

**Reconciliation, which is the only way to know the capture works.** At the end of each week,
join our captured `T-2d` vintage against the nflverse weekly archive when it publishes. Every
mismatch is a defect in one of the two and must be resolved, not averaged. Report the match rate
as a first-class metric. `DERIVED` — this is cheap, because §3.1 establishes that the archive
row *is* the `T-2d` vintage: median 47.2 hours before kickoff. We already know what it should
equal.

---

## 4. Proposed availability model structure

`DERIVED` throughout. Structure only; no model was fitted and none should be until the data
above is captured prospectively.

### 4.1 Shape

Two stages, both distributional, never collapsed to a point:

**Stage A — P(active).** A binary probability per player-game. Conditioning set, ordered by the
lift measured in §1 and §2:

1. `report_status` — the dominant term (0.353 nats of 0.632, §2.1)
2. depth/role rank at prediction time — `VERIFIED` §1.3, a `Questionable` starter (0.706) beats
   a healthy third-stringer (0.637); the 2026 daily depth feed supplies this at daily vintage
3. the **rest-day flag** — `VERIFIED` §1.6, a +0.485 risk difference inside one cell
4. injury body part — `VERIFIED` §1.5, 0.554→0.881 spread, registered as a hypothesis
5. `practice_status` — real at the tails, near-useless in the middle (§2.1)
6. practice **trajectory** — DNP→Limited→Full across the week. **Not measurable from the
   archive at all.** This is the single feature the live capture exists to create.

Hard constraints encoded rather than learned, on the strength of §1.2: `Out` ⇒ P(active) is
pinned at the measured 0.0009 with the one after-kickoff artefact removed, i.e. effectively 0;
`Doubtful` ⇒ 0 on n = 300 across two seasons. Practice participation may not override either.

**Stage B — P(role | active), as a distribution.** The output is **not** an expected snap share.
It is a distribution over the ratio `r = snap_share / own_healthy_baseline`, because §1.4 shows
the median is nearly flat across designations (0.90 vs 1.00) while the tail is not (P(<0.50×)
0.178 vs 0.077). A point estimate destroys the entire signal.

Concretely: a Beta-like density on `r` truncated at a plausible ceiling, whose shape parameters
are conditioned on position (RB most affected, QB least — §1.4), designation, and injury type.
The empirical quantiles in §1.4 are the calibration target: for `Questionable` skill players,
p10 = 0.36, p25 = 0.62, p50 = 0.90, p75 = 1.08, p90 = 1.24.

### 4.2 How the RB/WR redistribution mechanism consumes it — measured, not assumed

`VERIFIED` — the redistribution effect was measured directly, because a mechanism nobody has
measured is a silent constant under `CLAUDE.md` rule 3. Method: identify team-weeks in which
`Out`/`Doubtful` players at one position group carried ≥ 0.50 of baseline snap share in
aggregate; for every surviving teammate at that position with baseline ≥ 0.10, compute
`actual − own baseline`; compare against a control of the same players in team-weeks with no
positional absence; bootstrap by team-week.

| position | treated team-weeks | teammate obs | mean Δ (treated) | mean Δ (control) | **net effect** | cluster 95% CI | share recovered |
|---|---:|---:|---:|---:|---:|---|---:|
| **RB** | 28 | 44 | +0.2098 | −0.0110 (n=1,135) | **+0.2208** | [+0.1790, +0.2739] | 0.47 |
| **WR** | 77 | 290 | +0.1077 | −0.0139 (n=1,903) | **+0.1216** | [+0.0975, +0.1504] | 0.49 |
| **TE** | 37 | 68 | +0.1933 | −0.0071 (n=1,321) | **+0.2004** | [+0.1682, +0.2412] | 0.46 |

`DERIVED` — three design facts fall straight out:

1. **Redistribution is large and it is measurable.** Losing a starting RB moves each surviving
   rotation RB's snap share by **+22 percentage points**, with a cluster-robust CI nowhere near
   zero. This is not a second-order correction.
2. **Snap share does not conserve within the position group. Only about half of it returns.**
   Median recovered ÷ removed is **0.47 (RB), 0.49 (WR), 0.46 (TE)**. `DERIVED` — the rest
   leaves the group: it goes to players below the 0.10 baseline threshold (practice-squad
   elevations, players with no baseline at all) and to *personnel change* — a team missing its
   WR2 runs less 11 personnel and more 12, moving snaps from WR to TE. **A redistribution model
   that renormalises the position group to a constant total is therefore wrong by roughly a
   factor of two**, and wrong in the direction that systematically over-projects the backup —
   which is precisely the player a prop market prices loosely. This is the most important
   modelling consequence in §4 and it is measured, not assumed.
3. The mechanism must run **inside** the simulation draw, not before it. Redistribution is a
   consequence of a realised availability draw, so it cannot be applied to an expected value.

### 4.3 What the simulator receives

Per player-game, per Monte Carlo draw `d`:

```
active[d]        ∈ {0, 1}            ~ Bernoulli(P_active)   -- correlated within team-game
role_ratio[d]    ∈ [0, ~1.6]         ~ Stage B | active[d]=1
snap_share[d]    = baseline * role_ratio[d], renormalised at the TEAM level (not the position level)
```

**Correlation is mandatory, not optional.** Availability draws inside a team-game must be drawn
jointly: the inactives decision is one decision, game script is shared, and — as §4.2 shows —
one player's absence mechanically changes another's role. `CLAUDE.md` rule 9 and the grounding
brief's threefold-clustering finding both say the same thing from the evaluation side; here it
also holds on the generative side. Independent per-player draws would understate the variance
of team-level outcomes and, worse, would make the redistribution term incoherent.

**Storage.** Full joint draws, per the grounding brief's MLB lesson. Storing quantiles of
`role_ratio` would reproduce the nine-percentile mistake exactly: it would make CRPS, log score
and tail calibration uncomputable on the one quantity (§1.4) whose whole information content is
in its tail.

**Feature registry status.** Nothing in §4 is above `EXPERIMENTAL` under
`v8/FEATURE_REGISTRY.md`. §1's mapping and §4.2's redistribution effect are `DESCRIPTIVE`
measurements on 2024 with a 2025 replication of §1 only. No experiment has earned any of it a
higher status, and none should be claimed.

---

## 5. Sources not reachable from this container — assignment, not blockage

`VERIFIED` — reachability probed here on 2026-09-06 with
`curl -sS -o /dev/null -m 12 -w "%{http_code}" -L <url>`:

| URL | code |
|---|---|
| `https://www.nfl.com/injuries/` | **000** |
| `https://static.nfl.com/liveupdate/gamecenter.json` | **000** |
| `https://www.espn.com/nfl/injuries` | **000** |
| `https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams` | **000** |
| `https://api.sleeper.app/v1/players/nfl` | **000** |
| `https://api.sportsdata.io/v3/nfl/scores/json/Injuries/2026REG1` | **000** |
| `https://operations.nfl.com/` | **000** |
| `https://www.pro-football-reference.com/years/2024/injuries.htm` | **000** |
| `https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv` | **404** |
| `https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2026.csv` | **200** |
| `.../snap_counts/snap_counts_2026.csv` | 404 |
| `.../weekly_rosters/roster_weekly_2026.csv` | **206** (range probe) |
| `.../rosters/roster_2026.csv` | **206** |
| `.../pbp/play_by_play_2026.csv` | 404 |

`DERIVED` — **the 2026 injury archive does not exist yet.** It will be created during week 1.
Everything before its first terminal row is available only to whoever captures it.

Per `docs/AGENT_PROTOCOL.md` Rule 5 and DEC-029 — *not blocked, assigned* — nothing below is
marked blocked. Each names exactly what is wanted. **My brief forbids me to modify any other
file, so this block is written here in outbox form for the lead to paste into
`docs/AGENT_OUTBOX.md` as a numbered section.** It is not stubbed, not mocked, and no fallback
was written that would let a test pass without it.

### Assignment block — for `docs/AGENT_OUTBOX.md`

> **N7 — NFL availability capture. From: W7 (repository agent, no egress) · To: the agent with
> network access.** Urgency: 2026 REG week 1 opens **Wednesday 2026-09-09**
> (`schedules_games.csv`, season 2026). `injuries_2026.csv` returns 404 today. Every capture
> listed below is permanently unavailable if it is not taken before the game it describes.
>
> **N7-A1 — `weekly_rosters/roster_weekly_2026.csv`, weekly, all season.** Reachable
> (HTTP 206 on a range probe) and I did not download it to respect a disk budget. It carries a
> per-week roster `status` field, which is the correct denominator for P(active). Everything in
> §1.3 currently uses the depth chart as a proxy and that proxy scores healthy depth-chart
> starters at 0.857, not ~1.0, so the proxy is measurably wrong. **What it adds:** turns
> P(active) from a conditional-on-being-injured quantity into an unconditional one.
>
> **N7-A2 — Official NFL injury report, captured on the §3.4 cadence.** `www.nfl.com/injuries/`
> and the per-club report pages return 000 here. **Cadence:** per team per game at T-6d, T-5d,
> T-4d, T-2d, T-1d, and hourly from T-6h to kickoff. **Keys:**
> `(season, season_type, week, team, gsis_id or source-native id, source_id, retrieved_at)`.
> **Must record:** the five clocks of §3.4, the raw response bytes before parsing, HTTP status,
> byte count. **Append-only — never update a row.** **What it adds:** the Wed→Thu→Fri practice
> trajectory, which is the only feature in §4.1 that cannot be built from any archive.
>
> **N7-A3 — The official inactives list, ~90 minutes before each kickoff.** Not present in any
> nflverse dataset I can reach. **What it adds:** it resolves `Questionable` from P = 0.655 to
> 0 or 1. **Measured value: 75.6 bits of availability entropy per league-week (§6)** — the
> largest single information gain available anywhere in my scope, and it is a scheduled,
> deterministic publication.
>
> **N7-A4 — Transactions: IR placements and returns, practice-squad elevations, activations,
> suspensions.** Cadence: daily, with an effective date per event. **What it adds:** §4.2 shows
> only ~47% of a departed starter's snap share returns to his position group; elevations are a
> large part of where the rest goes, and they are invisible in the depth chart until after the
> fact.
>
> **N7-A5 — Coach press-conference availability statements and beat-reporter status reports,
> Wed/Thu/Fri, plus Sunday-morning reporting.** Free text, timestamped, attributed to a named
> source. **What it adds:** the informational content of the gap between `Questionable` and the
> inactives list. Do **not** attempt to price it before it is captured; capture first, then test
> whether it beats the report. **Escalation note:** ingesting named reporters' output raises a
> source-reliability question that is a value judgement, not a measurement, so it is the
> owner's under Rule 1 if anyone proposes weighting sources differently.
>
> **N7-A6 — Confirm whether `date_modified` returns in `injuries_2026.csv`.** It exists in 2024
> and was **dropped in 2025** (§3.2). If it does not return, every 2025+ archive row is
> inadmissible as a dated feature under Constitution Rule 002 without a consumer-supplied clock,
> and our own capture becomes the only source of vintage. One HTTP header check answers it once
> the file appears.
>
> **N7-A7 — Depth charts: no action needed, and this is good news.** `depth_charts_2026.csv` is
> reachable from *here* (HTTP 200) and is already a **daily vintage series** — 170 `dt` values,
> 2026-03-22 → 2026-09-06 (§3.3). Role vintages are not on the losing clock. Please do not
> duplicate this capture.

`VERIFIED` — I have not marked any of A1–A7 blocked, have not stubbed them, and have written no
fixture that would let a test pass in their absence.

---

## 6. What is lost per week not captured

`DERIVED` from `VERIFIED` inputs. 2024 REG, 18 weeks, mean per league-week:

| `report_status` | rows/week | rows/week, skill (QB/RB/WR/TE/FB) |
|---|---:|---:|
| no designation | 177.9 | 52.7 |
| `Questionable` | **81.3** | **23.3** |
| `Out` | 60.6 | 16.7 |
| `Doubtful` | 10.6 | 4.1 |
| **total** | **330.8** | **96.8** |

`DERIVED` — availability entropy remaining **after** the Friday report, using the §1.1 rates and
`H(p) = −p·log₂p − (1−p)·log₂(1−p)`:

| cell | n/wk | P(play) | H (bits) | bits/week |
|---|---:|---:|---:|---:|
| `Questionable` | 81.3 | 0.6550 | 0.9295 | **75.6** |
| no designation | 177.9 | 0.9430 | 0.3154 | 56.1 |
| `Out` | 60.6 | 0.0009 | 0.0104 | 0.6 |
| `Doubtful` | 10.6 | 0.0000 | 0.0000 | 0.0 |
| **total** | | | | **132.3** |
| *of which skill positions* | | | | **38.5** |

**Per league-week not captured, the following is permanently lost:**

1. `DERIVED` — **~132 bits of availability uncertainty that the inactives list would have
   resolved to zero**, 75.6 of them concentrated in the ~81 `Questionable` player-weeks and 38.5
   of them on the skill players who carry the props.
2. `DERIVED` — **~331 player-week practice trajectories** (Wed→Thu→Fri), of which ~97 are skill
   positions. The archive preserves the endpoint only. Measured evidence that the trajectory
   exists and is being destroyed: the two week-15 rows in §3.1 are `Questionable`→`Out`
   downgrades captured 10.7 and 17.0 hours apart, and they survive **twice in 6,215 rows**,
   apparently by accident.
3. `DERIVED` — **~81 `Questionable` resolutions** and the gap between the Friday designation and
   the Sunday truth, which is where every news source in §5 lives.
4. `DERIVED` — for 2025-schema data, **the timestamp of the surviving row itself** (§3.2).

`DERIVED` — cumulative exposure. `VERIFIED` — 2026 has **272 REG games across 18 weeks**
(`schedules_games.csv`, season 2026, game_type REG). This also **upgrades the grounding brief's
`UNVERIFIED-RECALL` "~272 regular-season games per season" to `VERIFIED`** for 2026 and 2025
(2025 REG = 272 likewise). One missed week costs ~132 bits and ~331 trajectories; a missed
season costs ~2,380 bits and ~5,950 trajectories, and no later work recovers any of it.

**The clock, stated precisely.** `VERIFIED` — today is **2026-09-06**. 2026 REG week 1 kicks
off **Wednesday 2026-09-09 at 20:20 ET (NE @ SEA)**, with a Thursday game 2026-09-10 and the
main Sunday slate 2026-09-13. `DERIVED` — the first practice-report vintage for the Wednesday
opener is due **Monday 2026-09-07 or Tuesday 2026-09-08 — that is tomorrow or the day after** —
and `injuries_2026.csv` returns 404 today, so nothing is capturing it. **Assignment N7-A2 and
N7-A3 have a deadline of days, not weeks.** Under Rule 006a this is the difference between a
`DEFERRED` candidate accumulating evidence and a `BLOCKED` one that cannot.

`DERIVED` — a cheap partial hedge, if the full cadence cannot be stood up in time: a
**once-daily** capture of the official report, even unparsed raw HTML written to disk with the
five clocks, preserves the Wed/Thu/Fri distinction and therefore ~80% of item 2 above. It costs
one cron entry. Doing nothing because the full specification is not ready would be the worst
available outcome, and it is the outcome this project has previously reached by writing
something off as unrecoverable before checking (`CLAUDE.md`, the 2026-08-30 slate snapshot).

---

## 7. Limitations, and what would falsify the above

Stated because Rule 005 and `CLAUDE.md` rule 8 both forbid presenting this as settled.

1. `VERIFIED` — **§1 is a one-season measurement with a one-season replication.** 2024 and 2025
   agree closely on §1.1 and on the direction of §1.2. §1.4 (snap share), §1.5 (injury type),
   §1.6 (rest days) and §4.2 (redistribution) were measured on **2024 only** and are **not**
   replicated. They should be treated as `DESCRIPTIVE` until they are.
2. `VERIFIED` — **"played" means "recorded ≥1 snap".** A player active but never used counts as
   not-played. In `snap_counts` this affects at most 1 row in 26,615, so it is negligible for
   the aggregate, but it is not the same predicate as "was on the gameday 46/48", which is what
   N7-A1 would supply.
3. `VERIFIED` — **the 52 ambiguous join rows (0.84%)** cap the precision of every P(play) figure
   at roughly ±0.008. No conclusion here turns on less than that.
4. `VERIFIED` — **§1.5 has no multiplicity correction** across 14 injury-type cells, and §1.4's
   position split has none across 4 positions. Both are exploratory. Under Rule 004a the metric
   set and correction must be frozen in an experiment ticket *before* any confirmatory rerun.
5. `VERIFIED` — **§2.2 is `DEFERRED / UNDERPOWERED` at n = 222**, not a null result. I have not
   written "no effect" anywhere and the phrasing should not be softened to it.
6. `VERIFIED` — **the healthy baseline in §1.4 is built from the same season being scored.** It
   is a within-season median over off-report weeks and is therefore contemporaneous, not
   strictly prior. **This is a leakage hazard under Constitution Rule 003** and would be
   inadmissible in a forward-chained backtest, where the baseline must be built from weeks
   strictly before the game date. It is acceptable for the descriptive purpose here — the
   quantity being described is "how far from normal did this player deviate", which is a
   retrospective question — but the number would change under a Rule-003-compliant construction
   and **must be rebuilt before it enters any model.** Flagging it explicitly rather than
   letting it be discovered later.
7. `VERIFIED` — 36 rows in `inj2024.csv` carry a `practice_status` of `'\n    '` (whitespace
   only, `repr` shown) and 6 carry `report_status = "Note"`. Small, but a reader that treats
   whitespace as a category will silently create a fourth practice level. Class A adjacent;
   named so an ingest can refuse it.
8. `VERIFIED` — **all of this is exploratory with respect to any future model.** Nothing here
   has been compared against a baseline under Rule 004, nothing has been promoted under Rule
   006, and the 2024/2025 seasons used to derive it are now development data for anything built
   on it. A confirmatory claim requires weeks that have not yet been played — which is another
   reason the capture in §5 has to start now.

---

## Reproduction

`VERIFIED` — every number above came from one of seven throwaway scripts in the scratchpad,
listed here so the work can be repeated. Per the grounding brief's scope limit these are
evidence, not deliverables, and none is committed to `nfl/`.

| script | produces |
|---|---|
| `w7_join.py` | §0.2 crosswalk and join rates; writes `w7_joined.pkl` |
| `w7_time.py` | §3.1 vintage analysis, kickoff offsets, the Van Noy row |
| `w7_main.py` | §1.1, §1.2 with cluster bootstrap |
| `w7_share.py`, `w7_share2.py` | §1.4 snap-share distributions |
| `w7_lift.py`, `w7_lift2.py` | §2.1, §2.2 cross-fitted lift |
| `w7_dc.py` | §1.3 depth-chart denominator |
| `w7_redis.py` | §4.2 redistribution |
| `w7_2025.py` | §1.1/§1.2 out-of-sample replication on 2025 |

Interpreter: `python3.12` (`CLAUDE.md` floor). pandas and numpy present; **scipy is not
installed**, which is why every interval here is a bootstrap rather than a parametric test.
Seeds are fixed in each script and stated in §0.3.
