# R1 — THE QB ROOM, REBUILT

**What was asked.** Replace the mechanism that put a 0.412 zero-dropback mass on
Patrick Mahomes on the sealed DEN@KC board, with the simplest lawful structure:
legal room → pregame starter scenario → starter-**conditioned** share →
**separate** exit/replacement hazard → integer assignment of team dropbacks →
sack/scramble/attempt branch. Acceptance is structural, on the historical
week-1 depth-chart QB1 cohort. No floors, no clips, no hand-set probabilities,
no tuning toward any external number.

Written 2026-09-14, branch `claude/nfl-greenfield-architecture-stsxmk`,
`python3.12`. Artifacts under `nfl/research/v2/r1/`.

**Governance.** This is a CANDIDATE and a **successor lineage** to QB3. QB3 and
`nfl/research/qb3/` are untouched and unamended; `qb3_lib` is imported read-only
by the replay scripts so the "before" column is V1's own code, not a
reconstruction of it. Nothing here is promoted, nothing is wired into a board by
default, and no prospective evidence exists.

---

## 0. THE ANSWER, FIRST

| | V1 sealed | V2 |
|---|--:|--:|
| **Mahomes P(zero dropbacks)** | **0.4120** | **0.0090** |
| week-1 chart-QB1 cohort, mean assigned zero mass (forward-chained) | **0.1982** (n=128) / 0.2075 (n=96) | **0.0278** (n=96) |
| cohort rows at ≥ 0.25 zero mass | 39.8% | **0.0%** |
| cohort max | 0.456 | **0.137** |
| realised zero-dropback games in the cohort | 0 of 128 | — |

**The repair is structural, and here is exactly which part of it is.** The
starter is *defined* as the quarterback who takes his team's first dropback, so
a team with N ≥ 1 dropbacks has a starter holding at least one of them.
`P(dropbacks = 0 | started) = 0` is therefore an identity of the definition —
not a floor, a clip or a minimum — and the test suite attacks it directly, with
a deliberately poisoned parameter set carrying the arithmetic form of the V1
defect. It cannot be broken.

What is **not** structural, and must not be read as though it were: `P(he
starts)`. That is estimated from the record, and if the record changed the
number would change. A player's zero mass is now exactly

```
P(dropbacks = 0) = P(not the starter) x P(never relieves | not the starter)
```

and Mahomes' 0.0090 is entirely the first factor.

---

## 1. THE STRUCTURE

`nfl/production/nonqb/qb_room_v2.py`, spec `qb-room-v2-starter-scenario-1`.

```
stage 0   legal QB room          eligibility_gate.snapshot() -> choice_set()
stage 1   starter scenario       P(takes dropback #1 | rank, prev-primary, opener)
stage 2   starter-CONDITIONED    the starter keeps N - post; the pool he draws
          share                  from is never the unconditional one
stage 3   exit / replacement     pooled empirical hazard, fitted on every
          hazard                 team-game of pbp, needs no depth chart
stage 4   integer assignment     counts generated inside the draw; the room
                                 sums EXACTLY to rint(team dropbacks)
stage 5   sack/scramble/attempt  two-stage donor resample, then completions
          branch                 and yards
```

**What changed against V1, precisely.** V1 drew the primary passer's *identity*
and then resampled that player's share from his cell's **unconditional** pool —
a pool built over every depth-charted quarterback in the cell including the ones
who never took a dropback. The model's own frame says
`P(share = 0 | is the primary) = 0.0000` in all five cells, so the zero was
counted twice: once in the categorical draw of *who*, and again inside the pool
the winner then resampled from. In the (rank 1, not previous primary) cell that
pool is 47.35% exactly zero.

V2 never forms that quantity. The starter's dropbacks are `N - post`, and `post`
comes from a **separate** mechanism.

**The exit/replacement hazard, measured** (pooled, 2,718 team-games,
2021–2025, no depth chart required):

| quantity | value |
|---|--:|
| P(the starter does not take his team's last dropback) | **0.1339** (364 / 2,718) |
| post-exit fraction of team dropbacks, mean / median | 0.2841 / 0.1919 |
| exits with exactly one reliever / two | 334 / 30 |
| no exit, yet a non-starter took a dropback ("cameo") | 11.60% of team-games, mean 0.0045 |
| reliever identity given a change of hands: rank 2 / rank 3 / rank 1 | 0.9173 (n=375) / 0.2110 (n=237) / 0.3030 (n=33) |

**Two bounds in the code are definitional, not tuned**, and the report says so
rather than leaving a reader to find them: `post ≤ N − 1`, because the starter
took dropback #1; and `post ≥ 1` when the role changed hands, because that is
what changing hands means.

**The per-dropback branch** is a two-stage donor resample. Stage one draws one
of the quarterback's own historical games with probability proportional to its
dropbacks; stage two draws this draw's dropbacks with replacement from that
game's own outcome list. Game-level correlation survives stage one; nothing is
fitted in either stage; every output is an integer count. A quarterback with no
prior dropback falls back to the league donor pool and **the fallback is counted
on the artifact, never hidden** — tonight that is one player, KC's QB3.

**Stat contract.** A dropback is `qb_dropback == '1'` and decomposes *exactly*
into sack + scramble + board attempt: measured on 2024 REG, 1,314 + 1,062 +
17,839 = 20,215, no remainder. The board's attempt is
`pass_attempt & !sack & !qb_spike`; nflverse's `pass_attempt` includes sacks,
and spikes are not dropbacks at all. `panel_p3.dropbacks_as_passer` is **not**
used as a dropback column anywhere in V2.

---

## 2. STAGE 0 — THE LEGAL ROOM (R2's gate, consumed not rebuilt)

The coordinator's mid-task correction is in: the pool filter at
`run_forecast.py:439` reads roster status only, so a quarterback listed `Out`
but still `ACT` walks through — R2's phrasing, *"it would have kept Tua"*. That
sits directly on stage 1: an ineligible quarterback in the room draws starter
mass, and the exit mechanism is then asked to explain participation that was
never possible — a determination laundered into a probability.

`qb_room_v2.legal_room()` calls `eligibility_gate.snapshot()` → `choice_set()`
and removes at **choice-set construction**, so a removed quarterback has no row
in the allocation at all and there is no mass to renormalise away afterwards.
The gate is not reimplemented here.

**A learned feature is not a gate, and this room does not treat one as such.**
`appearance_r8.predict` does take `injuries_rows` and `Out` does reach it as a
one-hot — as a soft feature, which is how a governing-inactive player carried
`p_app = 0.9920`. Nothing in V2 reads a learned probability as a determination.
No fixture branch is used by any test in this workstream, so `layers.py:165-178`
cannot give this module a false green.

**The one re-admission, and it is a rule rather than a judgement.** A designated
emergency third quarterback appears on the inactive list and may nonetheless
enter. Deleting him would make an event the rulebook permits impossible, so he
is re-admitted with `can_start = False` — the rule admits him to the game, not
to the opening snap — and every re-admission is named on the Outcome. He is only
re-admitted when a **caller supplies the designation**; V2 never infers it from
a depth rank.

**Tonight:** both rooms pass the gate with **0 quarterbacks determined
ineligible and 0 removed by the pool rule**, so this closes a structural hole
that does not bite this game. That matches the coordinator's note that both of
tonight's `Out` players are non-skill. Seeded violations are tested: an official
inactive quarterback is removed and carries his authority and reason; an
inactive QB3 *with* the designation comes back unable to start; an inactive QB3
*without* it stays out.

---

## 3. THE ACCEPTANCE TEST — COHORT BEFORE AND AFTER

Cohort: every depth-chart rank-1 quarterback in **week 1 of 2021–2024**,
n = **128** team-games — the population D5 measured. **Realised zero-dropback
games: 0 of 128.** Team dropback volume in the replay is drawn from the
empirical pool of team dropbacks in seasons strictly earlier than the season
being scored, so no realised outcome of the game being scored enters.
`nfl/research/v2/r1/R1_COHORT_ACCEPTANCE.json`.

| arm | n | mean | p50 | p90 | max | ≥0.25 | ≥0.41 |
|---|--:|--:|--:|--:|--:|--:|--:|
| **V1 (`qb3_lib`), forward-chained** | 128 | **0.1982** | 0.085 | 0.403 | 0.456 | 39.8% | 7.8% |
| V1, forward-chained, 2022–24 only | 96 | 0.2075 | 0.082 | 0.410 | 0.456 | 45.8% | 10.4% |
| V2 **structure only**, pooled cells, fwd-chained | 96 | 0.1203 | 0.068 | 0.423 | 0.508 | 14.6% | 11.5% |
| **V2 full, forward-chained** | 96 | **0.0278** | 0.014 | 0.073 | **0.137** | **0.0%** | **0.0%** |
| V2 full, fit through 2025 (in-sample) | 128 | 0.0095 | 0.005 | 0.018 | 0.063 | 0.0% | 0.0% |

The 0.1982 reproduces D5's 0.1973 to within Monte-Carlo noise at m = 2,000,
which is the check that the "before" column is really V1.

**The forward-chained row is the one that counts.** For evaluation season Y the
fit sees only seasons < Y, so 2022–2024 week 1 is genuinely unseen by the
parameters scoring it. 2021 has no prior play-by-play in this repository and is
therefore excluded from the forward-chained arm and reported separately.

### 3.1 The decomposition, and it is not what the brief assumed

The brief states that moving the replacement probability out of the
unconditional share pool "is the repair". **Measured, it is about two-thirds of
it and the other third is the cell specification.**

```
V1                          0.1982      the unconditional pool, pooled cells
V2, conditional + exit      0.1203      the structural change alone
V2, + season-boundary cell  0.0278      the full repair
```

The middle row still has a **fatter tail than V1** — max 0.508 against 0.456,
11.5% of rows at ≥ 0.41 against 10.4% — because with the opener and in-season
populations pooled, the (rank 1, not previous primary) cell estimates neither.
D5 already measured why: the same cell means "an injured or benched starter is
still listed first" in weeks 2–18, realised zero 0.7174, and "a club changed
starters over the offseason" at a boundary, realised zero 0.0000.

So `is_season_opener` is in the starter cell. It is a **pregame-observable
mixture indicator that production already computes and already flags**
(`qb_allocation.qb3_configuration.week1_specification_defect` /
`QB3_WEEK1_SEASON_BOUNDARY`), not a fitted constant and not a knob. But it
should be recorded plainly that the headline cohort number depends on it.

### 3.2 The prior, stated rather than buried

Three opener cells are 0 of n and two are n of n:

| cell (rank, was-prev-primary, opener) | n | starts | raw | Jeffreys |
|---|--:|--:|--:|--:|
| (1, 0, **1**) | 90 | 90 | 1.0000 | 0.9945 |
| (1, 1, **1**) | 70 | 70 | 1.0000 | 0.9930 |
| (2, 0, **1**) | 133 | 0 | 0.0000 | 0.0037 |
| (3, 0, **1**) | 63 | 0 | 0.0000 | 0.0078 |
| (1, 0, 0) | 252 | 78 | 0.3095 | 0.3103 |
| (1, 1, 0) | 2,290 | 2,126 | 0.9284 | 0.9282 |
| (2, 0, 0) | 2,301 | 125 | 0.0543 | 0.0545 |
| (3, 0, 0) | 1,192 | 22 | 0.0185 | 0.0189 |

**In 160 season-opener team-games the depth chart's QB1 started every one.**

A raw rate of exactly 0.0000 asserts that Justin Fields *cannot* start tonight,
and a raw 1.0000 asserts that Mahomes cannot fail to. Sixty-three and ninety
observations do not support either, and "zeros are errors, not results" is a
rule here. Jeffreys' Beta(½, ½) is the standard non-informative prior for a
binomial proportion — **a documented prior**, one of the four admissible
provenances in this project, applied uniformly to every starter cell and
reported beside the raw rates.

**The repair does not depend on it.** Under the raw empirical rates the cohort's
mean zero mass is **exactly 0.0000** and Mahomes' is exactly 0.0000. That number
is *worse* despite being smaller, because it asserts impossibility from an
absence, and I am not reporting it as the result.

---

## 4. THE CHECK THAT COULD HAVE FAILED, AND DID NOT

A repair that removes week-1 zero mass by removing zero mass **everywhere** is
not a repair, it is a second defect pointing the other way. D5 measured the same
cell mis-specified in **opposite directions** either side of the boundary, so
V2 was scored on both. Forward-chained 2022–2024, 3,851 charted-QB rows over
1,629 team-games, m = 500, game-clustered 95% intervals.
`nfl/research/v2/r1/R1_DIAGNOSTICS.json`.

| population | n | realised zero | V1 mean (gap) | V2 mean (gap) | V1 Brier | V2 Brier |
|---|--:|--:|---|---|--:|--:|
| rank-1, **season opener, not prev primary** — the cell that produced 0.412 | 51 | **0.0000** | 0.3269 (**+0.3269** [+0.291, +0.360]) | 0.0332 (**+0.0332** [+0.023, +0.044]) | 0.1255 | **0.0024** |
| rank-1, season opener (all) | 96 | 0.0000 | 0.2072 (+0.2072) | 0.0273 (+0.0273) | 0.0692 | **0.0017** |
| rank-1, **in-season, not prev primary** — where V1 *under*-assigns | 149 | **0.7315** | 0.3946 (**−0.3370** [−0.412, −0.263]) | 0.5441 (**−0.1874** [−0.263, −0.112]) | 0.3171 | **0.2381** |
| rank-1, in-season (all) | 1,520 | 0.1388 | 0.0969 (−0.0419) | 0.0988 (−0.0401) | 0.0939 | **0.0857** |
| rank-2, all | 1,595 | 0.7618 | 0.7284 (−0.0334) | 0.6909 (−0.0708) | 0.1673 | **0.1647** |
| rank-3, all | 640 | 0.8891 | 0.6881 (**−0.2010**) | 0.8872 (**−0.0019** [−0.021, +0.020]) | 0.1349 | **0.0769** |
| every charted QB | 3,851 | 0.5180 | 0.4594 (−0.0586) | 0.4733 (−0.0448) | 0.1305 | **0.1148** |

**Read the third row, because it is the one that mattered.** Where the record
demands *more* zero mass, V2 supplies more — 0.5441 against V1's 0.3946 — and
its Brier score improves there too. V2 did not fix week 1 by shrinking
everything; it moved the estimate toward the record in both directions. The
rank-3 row is the same story: V1 under-assigned by 0.2010, V2 by 0.0019 with an
interval spanning zero.

**Where V2 is worse, stated.** Rank-2 quarterbacks: V2's gap is −0.0708 against
V1's −0.0334, both under-assignments, and V2's interval excludes zero. Its Brier
is marginally better (0.1647 vs 0.1673), so this is a trade, not a strict
improvement. And the in-season not-previous-primary cell is still under-assigned
by **0.187 with an interval excluding zero** — much better than V1's 0.337 and
still an open defect, named here rather than left for a reader to find.

### 4.1 The room-level symptoms

| stratum | quantity | realised | V1 | V2 |
|---|---|--:|--:|--:|
| season opener (n=96) | top-passer share | 0.9860 | 0.9570 | 0.9698 |
| season opener | two QBs at ≥5 dropbacks | **0.0312** | **0.1258** | **0.0762** |
| in-season (n=1,533) | top-passer share | 0.9669 | 0.9656 | 0.9702 |
| in-season | two QBs at ≥5 dropbacks | 0.0855 | 0.0943 | 0.0755 |

**Tonight's two rooms**, V1 sealed against V2:

| | KC V1 | KC V2 | DEN V1 | DEN V2 |
|---|--:|--:|--:|--:|
| top-passer share | 0.849 | **0.964** | 0.957 | 0.967 |
| **chart QB1's share** | **0.547** | **0.945** | 0.915 | 0.949 |
| draws with two QBs at ≥5 dropbacks | **0.480** | **0.098** | 0.102 | 0.086 |

V1 gave KC's chart QB1 54.7% of his own team's dropbacks and put two Kansas City
quarterbacks at five or more dropbacks in **48% of draws**, against a realised
season-opener rate of 3.12%. V2 gives 9.8% — better by a factor of five and
**still about 2.5x the realised rate**, which is an open item, not a closed one.

---

## 5. TONIGHT — KC AND DEN

`nfl/research/v2/r1/R1_TONIGHT_DEN_KC.json`, m = 1,000, seed 20260908,
ordinal 202601.

**Team volume is held fixed at V1's own draws.** The team-dropback vectors are
read straight out of the sealed board's `player_draws.npz`
(`team_volume/team_dropbacks_part`), so the only thing that differs between the
two columns below is the allocator. Rebuilding the volume model would have
changed two things at once. KC's team dropbacks mean 41.47, DEN's 37.19 — both
V1's numbers, untouched.

Rooms from the captured depth chart `depth_charts.f66f0c2583dba463.reduced.csv.gz`
(retrieved 2026-09-14T13:53:31Z, strictly before kickoff). KC is
`NO_PREV_PRIMARY_IN_ROOM` — the 2025 week-18 primary `00-0037324` is not in
tonight's room. DEN is `AGREE`. **Both clubs cross the season boundary.** No
official inactive list exists at the time this ran, so every rostered
quarterback is legally eligible and no emergency third-QB designation is
available to consume.

### 5.1 Mahomes, against the sealed V1 values

| | **V1 sealed** | **V2** |
|---|--:|--:|
| P(starts) | *not modelled as such* | **0.9890** |
| **P(zero dropbacks)** | **0.4120** | **0.0090** |
| P(replacement state) | — | 0.0020 |
| P(exits while starting) | — | 0.1470 |
| dropbacks | 22.82 | **39.17** |
| attempts | 20.20 | **34.76** |
| completions | 13.29 | **23.03** |
| passing yards | 144.02 | **253.09** |
| **conditional passing yards** (given he plays) | **244.92** | **255.39** |
| sacks / scrambles | 1.07 / 1.55 | 1.80 / 2.61 |
| dropbacks P10 / P50 / P90 | **0** / 30 / 48 | **28** / 40 / 51 |
| attempts P10 / P50 / P90 | 0 / 26 / 42 | 24 / 35 / 46 |
| completions P10 / P50 / P90 | 0 / 16 / 28 | 14 / 23 / 32 |
| passing yards P10 / P50 / P90 | 0 / 160 / 320 | 129 / 247 / 389 |

**The single most informative line in this report.** V1's *conditional*
dropbacks were 22.82 / (1 − 0.412) = **38.8**. V2 gives **39.17**. The two
allocators agree almost exactly on how much football Mahomes plays *if he
plays*; the entire 22.82-to-39.17 difference in the mean is the spurious zero
mass being removed. V2 did not decide Mahomes is better. It removed a
probability that the record does not support, and the mean moved as arithmetic.

The same holds on yards: 244.92 conditional against 255.39, a 4.3% difference
attributable to the branch model rather than to the allocation.

**This number was not targeted.** Nothing in the code or the fit refers to
0.412, to 22.82 or to any board value; the inputs are the depth chart, the
previous-primary feature and play-by-play, and the output is what they produce.

### 5.2 Both rooms in full

**Kansas City** — `NO_PREV_PRIMARY_IN_ROOM`, season opener, P(an exit) 0.150,
integer closure deviation 0.

| player | rk | prior games | P(start) | **P(0 db)** V2 / V1 | P(repl) | db V2/V1 | att V2/V1 | cmp V2/V1 | pyds V2/V1 | db P10/50/90 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **Patrick Mahomes** | 1 | 80 | **0.9890** | **0.0090** / 0.4120 | 0.0020 | 39.17 / 22.82 | 34.76 / 20.20 | 23.03 / 13.29 | 253.1 / 144.0 | 28 / 40 / 51 |
| Justin Fields | 2 | 56 | 0.0040 | 0.7920 / 0.4560 | 0.2040 | 1.72 / 13.20 | 1.40 / 10.34 | 0.83 / 6.76 | 9.2 / 72.6 | 0 / 0 / 3 |
| KC QB3 (`00-0040906`) | 3 | **0** | 0.0070 | 0.9450 / 0.4190 | 0.0480 | 0.61 / 5.47 | 0.55 / 4.87 | 0.35 / 3.23 | 3.9 / 34.6 | 0 / 0 / 0 |

**Denver** — `AGREE`, season opener, P(an exit) 0.142, integer closure
deviation 0.

| player | rk | prior games | P(start) | **P(0 db)** V2 / V1 | P(repl) | db V2/V1 | att V2/V1 | cmp V2/V1 | pyds V2/V1 | db P10/50/90 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **Bo Nix** | 1 | 34 | **0.9920** | **0.0080** / 0.0480 | 0.0000 | 35.34 / 34.06 | 31.69 / 30.54 | 20.34 / 19.92 | 204.0 / 202.4 | 26 / 36 / 45 |
| Jarrett Stidham | 2 | 6 | 0.0050 | 0.8040 / 0.8030 | 0.1910 | 1.46 / 2.26 | 1.20 / 1.92 | 0.78 / 1.19 | 9.7 / 14.1 | 0 / 0 / 3 |
| Sam Ehlinger | 3 | 4 | 0.0030 | 0.9450 / 0.7910 | 0.0520 | 0.42 / 0.90 | 0.37 / 0.77 | 0.24 / 0.49 | 2.2 / 4.5 | 0 / 0 / 0 |

Nix moves 34.06 → 35.34 dropbacks and 202.4 → 204.0 passing yards. **DEN barely
moves, and that is the control.** The V1 defect needed the chart's QB1 to differ
from the previous primary, DEN's does not, and V2 accordingly leaves that room
almost where it found it. One binary feature separated the two clubs on the
sealed board and it no longer does.

KC's QB3 has **zero prior dropbacks** and draws his branch rates from the league
donor pool. That is on the artifact; his 0.61 expected dropbacks are almost
entirely relief mass.

---

## 6. DATA VINTAGE — AND IT IS NOT UNIFORM

`pbp_2025` landed during this task and was verified before use: sha256
`2f135887790a013f…8961978` matching the coordinator's value,
**272 REG games**, 48,771 rows, provenance `ARCHIVE`. It is in the fit. So this
rebuild uses the **nearest lawful season**, not 2021–2024 only.

| component | seasons | note |
|---|---|---|
| exit hazard, post-exit pool, cameo pool, reliever counts | **2021–2025** | needs no depth chart; 2,718 team-games |
| per-dropback donor pools (sack/scramble/attempt, completions, yards) | **2021–2025** | Mahomes 80 prior games, Nix 34 |
| starter-scenario cells | **2021–2025** | 2,717 charted team-games |
| depth chart, 2021–2024 | nflverse **weekly** vendor | 2,173 team-games |
| depth chart, **2025** | **daily** vendor, read strictly as-of | 544 team-games — this is the vendor that serves 2026, so the 2025 fold is vendor-matched to serve time and the earlier ones are not |
| previous-primary feature | `panel_p3`, as production | see below |
| 2026 play-by-play | **excluded by construction** | `pbp_path()` refuses season 2026 and the suite asserts the refusal |

**The previous-primary feature is taken from production unchanged,
deliberately.** `panel_p3.dropbacks_as_passer` equals `pass_att_as_passer` in
every row and is an attempt count, not a dropback count — the brief's warning.
Rebuilding the feature on true dropbacks would have changed the treatment and
the comparison in one step, so instead the disagreement was **measured**: over
2,718 team-games the attempt-based primary differs from the true-dropback
primary in **6, a rate of 0.0022**. The feature is kept identical and the
measurement is why that is safe, rather than an assumption that it is.

**Vendor mismatch is a live limitation, not a solved problem.** The starter
cells are fitted mostly on the weekly vendor and served on the daily one. D5
measured that for WR the weekly vendor's rank 1 is a special-teams slot 68.5% of
the time; for QB it is a genuine QB slot 99.2% of the time, which is why this is
tolerable here and would not be tolerable for a receiver.

---

## 7. THE Q9 HASH CHECK, AND WHAT WAS TOUCHED

```
sha256(nfl/production/nonqb/layers.py)
  = 481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108
```

Verified at the start of this task and again at the end: **unchanged**, matching
the frozen `481f005f682cd721`. `layers.py` was never opened for writing.

`nfl/research/qb3/` is byte-unchanged; `football_engine.py`, `rushing_a1.py`,
`depth_vintage.py`, `role_prior.py`, the eligibility modules and `nfl/product/**`
were not written to by this workstream.

**Files created:** `nfl/production/nonqb/qb_room_v2.py`,
`nfl/tests/test_qb_room_v2.py`, `nfl/research/v2/r1/` (this report,
`r1_cohort.py`, `r1_tonight.py`, `r1_diagnostics.py`,
`R1_COHORT_ACCEPTANCE.json`, `R1_TONIGHT_DEN_KC.json`, `R1_DIAGNOSTICS.json`).

**File modified:** `nfl/production/nonqb/qb_allocation.py` — an **opt-in,
default-inert** allocator flag, described in section 9. No commit, add, stash or
push was performed.

**Tests:** `python3.12 nfl/tests/run_suite.py --only test_qb_room_v2` →
**14 test functions, 58 checks, 0 failing, 0 raised, 0 zero-check functions,
0 blocked. SUITE PASS.** `--only test_qb3_allocation` (43 checks) and
`--only test_qb_inactive_ownership` (71 checks) both still PASS.

---

## 8. FOUR THINGS THE CORRECTED STRUCTURE PRODUCED THAT I DID NOT EXPECT

**1. The conditional-pool fix is not the whole repair.** Section 3.1. Moving the
replacement probability out of the unconditional pool takes the cohort from
0.1982 to 0.1203; the season-boundary cell takes it from 0.1203 to 0.0278. The
structural change alone leaves a **fatter maximum than V1** (0.508 against
0.456). If only the pool had been changed, tonight's Mahomes number would have
been roughly 0.12 and would still have been wrong.

**2. V1 and V2 agree almost exactly on conditional dropbacks.** 38.8 against
39.17. The sealed board's central quantity was never the disagreement; the zero
mass was doing all of the damage, and that is a cleaner diagnosis than expected.

**3. I could not reproduce the "top-passer share 0.7767 against a realised
0.9898" figure from the allocator.** Replaying V1's own `qb3_lib.allocate` over
1,629 team-games gives a top-passer share of **0.9651** against a realised
0.9680, and 0.9570 against 0.9860 on openers — a mild defect, not the one
quoted. The reason is that top-passer share measures **concentration, not
identity**: when V1 draws the chart QB1's share as zero, the whole 1.0 flows to
the rest of the room, so the room still looks concentrated — on the wrong man.
On tonight's KC room the quantity that exposes it is the **chart QB1's own
share, 0.547**. Whatever produced 0.7767 is either downstream of the allocator
or a different statistic, and this report cannot confirm it. Flagging rather
than adopting it.

**4. The 2025 depth chart is not missing after all.** `qb_allocation`'s
`KNOWN_LIMITATIONS` records `depth_chart_2025_absent`, and the committed weekly
leaves do stop at 2024 — but `dc25_daily.csv.gz` carries in-season captures from
2025-08 through 2026-03, and read strictly as-of each game date it yields a
complete 544-team-game 2025 fold on the vendor that serves 2026. That
limitation line is stale. I have not edited it, because the note belongs to a
frozen candidate's documentation and changing it is an integration decision.

---

## 9. WHAT IS OPEN, AND WHAT NEEDS THE COORDINATOR

**V2 is NOT wired into any board, and the flag that would wire it is off.**
`qb_allocation.allocate` now takes `allocator='qb3'` (default, **bit-identical
to today**, and the suite asserts the qb3 call site is unchanged) or
`allocator='qb_room_v2'`. The V2 path also needs `team_dropback_draws`, and
without them it returns `BLOCKED[QB_ROOM_V2_NEEDS_TEAM_DROPBACKS]` rather than
approximating. An unknown allocator name is `FAIL[QB_ALLOCATOR_UNKNOWN]`, never
a silent fallback.

**Why it needs them, and why that is the coordinator's call.** V2's estimand is
an **integer dropback count**, so it needs the team's dropback draws —
and `qb_allocation.allocate` is called *before* team volume is drawn. The only
place that holds both is `football_engine` (`team_dropbacks_part` at lines 409
and 1069), which belongs to R4. So integration is: pass the team dropback draws
into the allocation, flip the flag. One argument and one plumbing change; no
rewrite. I have not made the plumbing change because the file is not mine.

**Five open items, none of them hidden:**

1. **In-season rank-1 not-previous-primary is still under-assigned by 0.187**
   (interval excludes zero). Better than V1's 0.337, not fixed.
2. **Rank-2 zero mass is a trade**: V2's gap −0.0708 against V1's −0.0334,
   Brier marginally better. Not a strict improvement.
3. **Two QBs at ≥5 dropbacks on tonight's KC room is 9.8%** against a realised
   season-opener rate of 3.12%. Five times better than V1's 48%, still high.
4. **Every result here is EXPLORATORY.** The historical panel selected the
   season-boundary hypothesis in this repository — D5 measured it before this
   module existed. The forward-chained arm is honest about *parameter* leakage
   and says nothing about *specification* leakage, and freezing the cohort does
   not make it a holdout. A confirmatory result needs untouched games.
5. **A starter is defined as the taker of dropback #1.** A quarterback who is
   dressed, is announced as the starter, and is injured on the opening kickoff
   would be scored a non-starter. That is a definitional edge, it is rare, and
   it is stated rather than papered over.

**Nothing here is a wager, a price, or a recommendation, and no sportsbook data
entered this workstream.**
