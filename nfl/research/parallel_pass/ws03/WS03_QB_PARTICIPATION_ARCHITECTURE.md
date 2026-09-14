# WS03 — QB participation architecture: incumbent failure map and next-step design

**RESEARCH ONLY. CODE CHANGED: NO.** No repository file outside
`nfl/research/parallel_pass/ws03/` was written. No candidate was promoted, no
governance file touched, NFL-1 not authorised, no sportsbook data opened, the
suite was not run.

Everything below was re-derived from code and data in this checkout at
HEAD `57d38ad` under `python3.12`. Where a prior artifact already states a
number, this document says so and reports its own independent value beside it.

---

## 0. The mechanism, traced

### 0.1 Who enters the room

| step | file:line | what happens |
|---|---|---|
| roster pool | `nfl/production/run_forecast.py:270-271` | `qbp = [q for q in fx['players'] if q['position'] == 'QB' and q['gsis_id']]` — every rostered QB with an id |
| **R5 eligibility filter** | `nfl/production/run_forecast.py:638-644` | `nonqb = [...position != 'QB']`; `qbs = [...position == 'QB']`; `players = qbs + pool.value`. **The active-roster filter is applied to `nonqb` only.** Comment at `:625-628`: *"The QB pool is untouched"* |
| call site | `nfl/production/run_forecast.py:293-297` | `FE.QA.allocate(season, week, teams, qbp, m, seed, inactive_ids=..., inactive_provenance=...)` |
| depth chart | `nfl/production/nonqb/qb_allocation.py:86-114` | newest leaf `nfl/vintage/depth_charts.f57ef0724d907160.reduced.csv.gz`, `dt` **2026-09-08T11:56:57Z**, 2177 rows, **92 QB rows, 32 teams** |
| room assembly | `qb_allocation.py:463-478` | per team, for each **rostered** QB, look up his chart rank |

Measured on that leaf: chart `pos_rank` distribution `{1:32, 2:32, 3:22, 4:6}`;
room-size distribution `{2 QB: 10 teams, 3 QB: 16, 4 QB: 6}`.

So the QB room is the **roster** pool, ranked by the **depth chart**, with no
active-53 / practice-squad / reserve gate anywhere. The only game-day
eligibility evidence that reaches it is the official inactive list
(`qb_allocation.py:459, 480-481, 522`).

### 0.2 Depth rank and the `min(rank, 3)` clip

```
qb_allocation.py:471-476
    r = room.get(pid)
    if r is None:
        ev['unranked_players'] += 1
        r = 3                                     # <-- UNRANKED DEFAULTS TO 3
    trip.append((pid, min(int(r), 3), int(prev.get(t) == pid)))
```

Two distinct collapses, and the second is the damaging one:

1. `min(int(r), 3)` folds chart rank 4 into rank 3. **6 QB rows** on the
   2026-09-08 leaf are rank 4 and are collapsed this way.
2. A rostered QB **with no chart rank at all** is assigned rank 3 — not
   dropped. The docstring at `:468-469` defends this ("dropping him would
   quietly shrink the room"), and for a rank-3 non-incumbent it is nearly
   harmless (cell `(3,0)`, `p_primary` 0.0282). But combined with the incumbent
   bit it routes an **unlisted** quarterback into cell `('2+', 1)` at
   `p_primary` **0.6167**. That is exactly what happened to Joe Milton III:
   not on Dallas's captured chart, `was_prev_primary = 1`, therefore
   `(3, 1) -> ('2+', 1)` and 53% of Dallas's dropbacks.

`qb3_lib.cell_of` re-clips at `:131` (`r = 1 if rank == 1 else (2 if rank == 2
else 3)`), so the clip is applied twice. Line `:135`,
`return (r if r == 1 else r, int(was_prev))`, is a **dead conditional** — both
branches are `r`. Cosmetic; noted so nobody reads meaning into it.

### 0.3 `was_prev_primary` and the season boundary

Derivation, production path:

```
qb_allocation.py:452-453   prev_detail = previous_primary_detail(season, week)
                           prev = {k: v['pid'] for k, v in prev_detail.items()}
qb_allocation.py:117-152   previous_primary_detail: bisect_left on the team's
                           sorted ordinals, cut = season*100 + week,
                           STRICTLY EARLIER, SPANNING SEASONS
qb_allocation.py:476       int(prev.get(t) == pid)
```

`primary_of` (`qb3_lib.py:79-81`) = the QB with the most dropbacks in that
team-game, ties by sort order, `None` if nobody threw.

**Season-boundary behaviour, measured.** For 2026 week 1 the cut is `202601`
and every club's previous ordinal is `202518`. All **32 of 32** rooms return
`is_season_opener: True`. Configuration split over charted rooms:
**AGREE 17, NO_PREV_PRIMARY_IN_ROOM 9, DISAGREE 6.**

Historical signal quality of the bit itself (frame 2020-2024, my own
measurement):

| | n | P(prev primary IS this week's primary) | P(prev primary is even in the charted room) |
|---|--:|--:|--:|
| week 1 | 128 | **0.4609** | **0.6250** |
| weeks 2+ | 2525 | **0.8768** | **0.9937** |

The bit is close to a coin flip at the boundary and is worth ~0.88 mid-season,
and **`cell_of` has no week or boundary term**, so both populations are pooled.

*Correction to the prior audit.* `DAL_NYG_PARTICIPATION_ROOT_CAUSE_AUDIT.md`
cites the path as `qb_allocation.py:193`. Line 193 is `previous_primary()`,
which has **zero callers anywhere in the repository** — an orphaned duplicate.
The live derivation is `previous_primary_detail` at `:117`, called from `:452`.
The audit's *finding* is unaffected; the line number is.

### 0.4 Cells and fitted pools

`cell_of(rank, was_prev)` (`qb3_lib.py:130-135`) yields exactly **five** cells;
rank 2 and rank 3 are pooled when `was_prev = 1`. Fitted by `qb3_lib.fit`
(`:138-154`) on seasons `< eval`. Re-derived here on seasons `< 2026`
(frame 6,446 rows over 2,685 team-games, 2020-2024):

| cell | n | p_primary | mean_share | P(share=0) | P(share=1) | P(0<s<1) |
|---|--:|--:|--:|--:|--:|--:|
| (1, 1) | 2349 | 0.9046 | 0.8919 | 0.0736 | 0.7765 | 0.1499 |
| (1, 0) | 321 | 0.4922 | 0.4946 | **0.4735** | 0.4424 | 0.0841 |
| ('2+', 1) | 240 | 0.6167 | 0.5979 | 0.3458 | 0.5083 | 0.1458 |
| (2, 0) | 2436 | 0.0686 | 0.0794 | 0.8120 | 0.0435 | 0.1445 |
| (3, 0) | 1100 | 0.0282 | 0.0323 | 0.9318 | 0.0173 | 0.0509 |

Reproduces `QB3_WEEK1_INCUMBENT_AUDIT.json["cells"]` to 4 dp on all 5 cells.

**New here: the within-cell split by season boundary.** This is where the
pooled numbers come from and it has not been reported before.

| cell | week-1 subpopulation | weeks 2+ subpopulation |
|---|---|---|
| **(1, 0)** | n=**101**, P(is_primary)=**0.9802**, mean share **0.9783**, P(=0)=**0.0000** | n=**220**, P(is_primary)=**0.2682**, mean share **0.2726**, P(=0)=**0.6909** |
| **(1, 1)** | n=59, P(is_primary)=**1.0000**, mean share 0.9839, P(=0)=0.0000 | n=2290, P(is_primary)=0.9022, mean share 0.8896, P(=0)=0.0755 |
| **('2+', 1)** | n=**21**, P(is_primary)=**0.0000**, mean share **0.0000**, P(=0)=**1.0000** | n=219, P(is_primary)=0.6758, mean share 0.6552, P(=0)=0.2831 |

Cell `(1,0)` is 31.5% week-1 rows whose mean share is 0.9783 and 68.5%
mid-season rows whose mean share is 0.2726. **One cell, two populations,
3.6x apart in the mean and opposite in the mode.** The pooled 0.4946 describes
neither.

Cell `('2+', 1)` is the decisive one. In the 21 historical week-1 rooms where
the prior-season incumbent sits **below** rank 1 on the current chart, he took
**zero dropbacks in 21 of 21 team-games**, and the charted QB1 took mean share
**0.9978** (P(share=1) = 0.9524, P(share=0) = 0.0000). The model gives that man
`p_primary = 0.6167`. A rule-of-three upper bound on 0/21 is ~0.133; the model's
0.6167 is outside it by a factor of 4.6, on 21 team-games across 16 team
clusters.

### 0.5 The sampling distribution and dropback allocation

`qb3_lib.allocate(par, team_qbs, m, seed, ordinal, team)` at `:157-198`:

**Step 1, identity** (`:169-171`)
```
pp  = [max(p_primary[cell_i], 1e-9) for i]      # MARGINAL cell rates
who = rng.choice(n, size=m, p=pp / pp.sum())    # renormalised in-room
```
These are **marginal** rates, not a multinomial fitted over rooms. Measured
over the 32 charted rooms of 2026 week 1, `sum(pp)` before renormalisation runs
**0.5608 (min) / 1.0014 (median) / 1.2056 (max)**. Renormalisation silently
rescales by up to 1/0.56 = 1.78x in one direction and 1/1.21 = 0.83x in the
other, and nothing records that it happened.

**Step 2, the primary's share** (`:173-182`) — resampled from his cell's
empirical pool, `S[i, sel] = pool[rng.integers(...)]`. Empty pool falls back to
`1.0` (`:180`).

**Step 3, the remainder** (`:183-192`) — `rem = 1 - S.sum(0)` distributed to the
**other** QBs *in proportion to their `p_primary`*. Closure residual is pushed
onto the drawn primary at `:196-197`.

Step 3 is the part with no evidential basis at all. `p_primary` is *"how often
does a man in this cell start"*. It is used here as *"given somebody else
started, what fraction of the leftover snaps does this man take"*. Those are
different quantities and no artifact estimates the second.

### 0.6 Starter / backup dependence structure

**In a 2-QB room the shares are perfectly, deterministically anti-correlated.**
Step 3 with `n = 2` leaves `S[other] = 1 - S[primary]` exactly. Measured over
8,000 draws on an `(1,1)+(2,0)` room: **corr = -1.0000** (to machine precision).
Conditional on the starter's share there is **zero** residual uncertainty about
the backup's.

The prior audit's -0.9240 is the correlation of *dropback counts*, attenuated
by team-dropback variation. In share space, which is what this layer forecasts,
the dependence is degenerate.

In a 3-QB room the structure is stranger, not better: DAL `corr(top two) =
+0.0226`; NYG `corr(top two) = -0.9933`. The sign and magnitude are an artifact
of the room's `pp` vector, not of anything estimated.

### 0.7 P(zero dropbacks) for a starter

| quantity | value | source |
|---|--:|---|
| model, charted QB1, cell (1,1) draw | **0.0680** (NYG Dart, 8,000 draws) | reproduced here |
| model, charted QB1, cell (1,0) draw | **0.4700** (DAL Prescott, sealed PRE room) | reproduced here; sealed value 0.4700 |
| model, all 32 charted rooms, week 1 2026 | min **0.0612**, median **0.0732**, max **0.4933** | this document |
| **teams whose charted QB1 carries P(zero) > 0.20** | **15 of 32** | this document |
| reality, established incumbent, no planned rotation, **given he started** | **0.0000** on n=1700 | `QB_PARTICIPATION_CAUSAL_AUDIT.json` |
| reality, charted QB1 takes zero, week 1, DISAGREE room | **0.0000** on n=21 | this document |

The 15-of-32 figure is a **lower bound** on the production defect: it is
computed on charted rooms only. Production adds unranked rostered QBs at rank 3,
which is precisely what turned Dallas from a 2-man `NO_PREV` room into a 3-man
`DISAGREE` room and pushed Prescott to 0.4123 mean share.

### 0.8 P(both QBs receive meaningful work)

Reality, 2,685 depth-charted team-games 2020-2024, second-highest QB share:

| | P(=0) | P(0, 0.10) | P[0.10, 0.25) | P(>=0.25) |
|---|--:|--:|--:|--:|
| **REALITY** | 0.8559 | 0.0615 | 0.0369 | 0.0458 |
| MODEL, AGREE 2-QB room | 0.8434 | 0.0671 | 0.0405 | 0.0490 |
| MODEL, NYG 3-QB room | 0.6966 | 0.1566 | 0.0390 | 0.1077 |
| MODEL, DAL 3-QB room (DISAGREE) | 0.4562 | 0.0291 | **0.4150** | 0.0996 |

**This is the most important single table in the document and it cuts both
ways.** In an AGREE room the model reproduces the league marginal almost
exactly. In the DISAGREE room the `[0.10, 0.25)` bin is inflated **11.2x**.
Slate-wide for 2026 week 1, `P(>=2 QB with share >= 0.10)` averages **0.1877**
against a realised base rate of **0.0826** — 2.3x, again a lower bound because
it omits unranked roster QBs.

The AGREE match is **not** independent validation: 90.7% of the mid-season
frame is AGREE, so the AGREE cell and the league marginal are nearly the same
estimate. What it does establish is that the layer is a marginal-matching
device that degrades exactly where pregame evidence is most informative.

### 0.9 Is a replacement state representable at all?

**No, not as a state.** Only its share footprint, and only as a by-product.

- There is no notion of *who took the first snap*. `primary_of` is
  arg-max-dropbacks, so "started and was pulled at half" and "came off the
  bench and out-threw the starter" are the same row.
- There is no time, no exit hazard, no ordering, no game state. The audit's
  three mechanisms — `PLANNED_ROTATION_OR_PACKAGE` (250),
  `REPLACEMENT_NO_RETURN` (142), `BLOWOUT_RELIEF` (149) — are all pooled into
  one unconditional share pool.
- Interior mass exists but is mis-sourced. Cell (1,1)'s pool has 14.99% of mass
  strictly between 0 and 1 against a realised in-game non-completion rate of
  ~13.2% (1 - 0.8688), so **the amount of "he did not finish" mass is roughly
  right**; what is wrong is that 7.36 points of *zero* mass sit beside it that
  belong to a pregame event. The fix is not "more interior mass".
- In a 2-QB room, once the primary's pool draw is made, the replacement share
  is determined. There is nothing left to be uncertain about.

`qb3_lib.py` docstring lines 1-12 are accurate about what it does: it resamples
a share. It never claims to model a replacement, and it does not.

### 0.10 Season-boundary contamination

Contamination is **declared, diagnosed, carried onto the artifact, and not
repaired**:

- `qb_allocation.py:143-150` sets `week1_specification_defect` /
  `defect_id: QB3_WEEK1_SEASON_BOUNDARY`;
- `nfl/product/forecast_stage.py:105-127` refuses to let stage 2 clear it;
- `KNOWN_LIMITATIONS['week_1_incumbent']` (`qb_allocation.py:56-59`) states it.

`QB3_WEEK1_INCUMBENT_AUDIT.json` already measures the size, week-1 stratum,
team-clustered:

| configuration | n (clean) | clusters | bias pred - actual | 95% CI |
|---|--:|--:|--:|---|
| AGREE | 50 | 25 | **-0.1098** | [-0.1144, -0.1054] |
| DISAGREE | 20 | 16 | **-0.4420** | [-0.4711, -0.4128] |
| NO_PREV | 41 | 27 | **-0.3611** | [-0.3846, -0.3347] |

and the direction **reverses** between week 1 and weeks 2+ in DISAGREE
(+0.2979 [0.2264, 0.3413], n=184). My independent frame measurement agrees in
sign and magnitude on all three.

The mechanism is physical, not statistical: week-18 is the game a playoff-bound
club is most likely to rest its starter in. The audit's `week18_rest_evidence`
records that **seven of eight** clubs on the 2026-09-13 4:25 slate had a
week-18 rest-game backup as their resolved incumbent (LAC Herbert 0 dropbacks,
PHI Hurts 0, WAS Daniels 0). Only Arizona played its 2026 starter in week 18,
and Arizona is the only one of the eight whose modelled starter share is
plausible.

### 0.11 Two dead guards (incidental)

- `DEPTH_CHART_CHRONOLOGY_FAILURE` (`qb_allocation.py:445-450`) fires only when
  `kickoff_utc` or `written_at` is passed. **No caller in the repository passes
  either** — `run_forecast.py:293`, `engine_rehearsal.py:121`, and all seven
  research callers pass neither. The guard is unreachable. (On the current leaf,
  `dt` 2026-09-08 precedes week-1 kickoff, so there is no actual leak; the guard
  simply cannot detect one.)
- `previous_primary()` (`qb_allocation.py:193-209`): zero callers.

---

## 1. INCUMBENT FAILURE MAP

| # | failure | status | code path | data evidence (re-derived here unless noted) | earliest failure point |
|---|---|---|---|---|---|
| F1 | The QB split is decided by ONE bit, `was_prev_primary` | **CONFIRMED** | `qb_allocation.py:476` -> `qb3_lib.py:130 cell_of` -> `:171 allocate` | Flipping only that bit on Dallas's 2-QB room: Prescott mean share **0.5462 -> 0.8902**, P(zero) **0.4218 -> 0.0755**. Nothing else changed | `previous_primary_detail` (`:117`, called `:452`) resolves the incumbent by ordinal across the season boundary |
| F2 | `Stage2 ewma_hl2` is on the QB path | **FALSIFIED** | — | `participation_prior.py:45 POSITIONS = ('WR','TE','RB')`; `s2_lib.py:16 POS = ('WR','TE','RB')`. `qb3_lib` imports neither; `football_engine.py:71,331` routes `share_prior` to `LY.participation` for non-QB only. `qb3_lib.py` imports `bisect, collections, csv, gzip, os, numpy` and nothing else | n/a — two separate participation mechanisms, both defective, for unrelated reasons |
| F3 | Cell (1,0) pools two populations 3.6x apart | **CONFIRMED (new)** | `qb3_lib.py:130-135` (no week/boundary term), `:138-154 fit` | (1,0) = 101 week-1 rows at mean share **0.9783**, P(0)=**0.0000** + 220 mid-season rows at mean **0.2726**, P(0)=**0.6909**. Pooled value 0.4946 describes neither | the cell definition, `predeclaration_qb3.md` s.4 |
| F4 | Cell ('2+',1) assigns 0.6167 to an event realised 0 of 21 times | **CONFIRMED (new)** | `qb3_lib.py:133` pools rank>=2 with `was_prev=1` | week-1 subpopulation of ('2+',1): n=**21**, P(is_primary)=**0.0000**, share **0.0000** in all 21, 16 team clusters. Rule-of-three upper bound ~0.133 vs model 0.6167 | same as F3 |
| F5 | The starter carries P(zero dropbacks) that reality assigns 0 | **CONFIRMED** | `qb3_lib.py:182` resamples a pool whose zero mass is a pregame event | model median **0.0732**, max **0.4933**; **15 of 32** charted QB1s above 0.20. Reality, given he started: **0/1700** (`QB_PARTICIPATION_CAUSAL_AUDIT.json`) | `build_frame` (`qb3_lib.py:84-124`) builds from the chart, so `share=0` conflates "never started" with "started, threw nothing" |
| F6 | The incumbent bit is near-uninformative at the boundary yet is weighted as if mid-season | **CONFIRMED** | `qb_allocation.py:117-152`; no week term in `cell_of` | P(prev primary is this week's primary): week 1 **0.4609** (n=128) vs weeks 2+ **0.8768** (n=2525). Prev primary not even in the room: week 1 **0.3750** vs weeks 2+ **0.0063** | `predeclaration_qb3.md` s.3B: "last game's primary passer" with no boundary term |
| F7 | Remainder allocation uses `p_primary` as a relief-share weight | **CONFIRMED (new)** | `qb3_lib.py:183-192` | DAL 3-QB room `P(2nd QB share in [0.10,0.25))` = **0.4150** vs realised base rate **0.0369** (11.2x). Slate `P(>=2 QB >= 0.10)` = **0.1877** vs **0.0826** | no artifact estimates a conditional relief share; `p_primary` is a starting rate |
| F8 | In-room renormalisation of marginal rates is unrecorded and large | **CONFIRMED (new)** | `qb3_lib.py:169-171` | `sum(p_primary)` over the 32 week-1 rooms: **0.5608 / 1.0014 / 1.2056** (min/med/max). Rescaling up to 1.78x, nothing logged | marginal cell rates are used where a room-conditional multinomial is needed |
| F9 | Backup share is a deterministic function of the starter's | **CONFIRMED (new)** | `qb3_lib.py:184-192` with `n=2` | `corr(S1,S2) = -1.0000` exactly, 8,000 draws. Zero conditional variance | step 3 allocates the residual, it does not model it |
| F10 | A replacement/exit event is not representable | **CONFIRMED** | `qb3_lib.py:79-81 primary_of`; `:157-198` | No first-snap, no exit time, no game state. 250 rotation + 142 replacement + 149 blowout team-games collapsed into one pool. Interior mass 0.1499 vs realised ~0.132 — **right size, wrong provenance** | the estimand: one unconditional `s_dropbacks` distribution |
| F11 | The QB pool is exempt from R5, the only eligibility filter that exists | **CONFIRMED** (prior audit; re-verified) | `run_forecast.py:638-644` | `nonqb = [...!= 'QB']`; `players = qbs + pool.value`. Unranked roster QBs enter at rank 3 (`qb_allocation.py:474-475`) | the declared R5 exemption |
| F12 | No pregame active-53 / PS / reserve signal exists at all | **CONFIRMED** (prior audit; not re-measured) | `nfl/vintage/weekly_rosters.*.reduced.csv.gz`; `ingest/allowlist.py` | vintage carries `season, week, team, gsis_id, position` only; `weekly_rosters.status` quarantined POSTHOC, correctly | DATA GAP, not a code defect |
| F13 | `DEPTH_CHART_CHRONOLOGY_FAILURE` is unreachable | **CONFIRMED (new)** | `qb_allocation.py:412-413, 445-450` | No call site in the repository passes `kickoff_utc` or `written_at` (10 call sites checked) | the guard's parameters default to `None` and nobody sets them |
| F14 | `previous_primary()` is an orphaned duplicate; prior audit cites it as the path | **PARTIAL** | `qb_allocation.py:193-209` | zero callers repo-wide. Live path is `previous_primary_detail` at `:117` / `:452` | documentation drift; the finding it supports is unaffected |
| F15 | The defect is in the specification, not the implementation | **CONFIRMED** | `predeclaration_qb3.md` sha256 `be61392619d4...` | `QB3_WEEK1_INCUMBENT_AUDIT.json.implementation_conformance` = CONFORMS, clause by clause; contract sha256 measured == cited | s.4 (cells) and s.3B (incumbent) of the frozen contract |
| F16 | Whether a boundary-aware cell would forecast *better* | **UNRESOLVED** | — | Nothing in this repository tests it. The evidence shows only that the current pooled cell forecasts badly at the boundary | requires a new pre-registration and a fold that has not been run |
| F17 | Whether the 0/21 week-1 DISAGREE result generalises | **UNRESOLVED** | — | n=21 over 16 clusters, and 2020-2024 selected the finding. Decisive against 0.6167; not decisive about the right value | development data |

---

## 2. What `predeclaration_qb3_ab.md` covers (sha256 `07b36d0e1e608cef...`, verified)

The frozen QB3-AB contract proposes `P(share) = P(starts) x P(share | starts)`.
Mapped onto the six-stage separation:

| stage | QB3-AB | evidence |
|---|---|---|
| **0 — eligibility** | **PARTIAL** | s.2: *"A player ruled officially inactive has Stage A probability exactly zero"*. That is game-day inactives only, arriving ~90 min out. It says nothing about active-53 / practice squad / reserve, which F12 shows has **no pregame signal at all**, and it does not name Stage 0 as a stage |
| **1 — starter probability** | **COVERED** | s.2 Stage A, features: depth rank, incumbent signal, official inactives |
| **2 — planned / package use** | **NOT COVERED** | s.3 fits Stage B on *"team-games where the quarterback took the first snap"*, which folds `PLANNED_ROTATION_OR_PACKAGE` (**250 team-games, the largest of the three backup classes**) into the same pool as replacement and blowout |
| **3 — replacement / exit hazard** | **PARTIAL** | s.2 names it and quotes anchors (P(finished) 0.8688, P(replacement no return) 0.0576) but the object estimated is a **marginal conditional share pool**, not a hazard. No exit time, no game state, no ordering |
| **4 — conditional post-exit allocation** | **NOT COVERED** | Nothing states who receives the remainder once the starter exits. F7 shows the incumbent mechanism uses `p_primary` for this and is 11.2x off in a DISAGREE room. QB3-AB does not touch step 3 |
| **5 — blowout tail** | **NOT COVERED** | P(blowout relief) 0.0718 appears as an anchor in s.2. No stage models it and nothing couples it to margin or clock, though `blowout_margin: 17` and `late_seconds_remaining: 900` are already predeclared thresholds in the causal audit |
| **6 — kneels / designed package snaps without exit** | **NOT COVERED** | Not mentioned. The causal audit's `KNEEL_OR_SPECIAL` class holds **1** team-game, so its own classifier does not separate this either. Realised size: second-QB share in (0, 0.10) occurs in **6.15%** of team-games |
| **season boundary** | **NOT COVERED, and explicitly ruled out** | s.0: *"the audit showed the season boundary is a symptom of the mixing, not the disease"*, and QB3-SB is to be withdrawn |

**I disagree with that last clause and the data is the reason.** Splitting
`P(starts) x P(share | starts)` does not repair the boundary, because Stage A's
declared feature set (rank, incumbent, inactives) still contains
`was_prev_primary` with no boundary term. At the boundary that feature is
**0.4609** accurate against **0.8768** mid-season, and in the DISAGREE stratum
its sign **reverses**. A Stage A fitted on the pooled frame inherits F3, F4 and
F6 unchanged. The boundary is a second, separable identification problem, not a
symptom of the first — and it is the one that governs every week-1 board.

This is a disagreement about a frozen artifact's reasoning, not about anything
irreversible. It is recorded here and needs no escalation; the proposal below
is designed so that whichever reading is right, the experiment answers it.

---

## 3. PROPOSAL — pre-registration for the smallest next step

### QB3-S1: boundary-aware starter identity, share machinery frozen

**Not authorised. Not built. Not fitted. Not applied. This is a proposal for an
owner decision, and it changes s.4 of a frozen contract, so it needs a new
pre-registration of its own before any estimator exists.**

#### 3.1 Why this and not QB3-AB

QB3-AB is two stages at once and leaves the boundary in place. The measured
evidence points at **step 1 of `qb3_lib.allocate` alone**: who starts. F3, F4,
F6 and F8 are all step-1 failures. F5 and F7 are downstream of it. The smallest
change that could move any of them is to make the **identity draw** use a cell
that distinguishes a season-opening room from a mid-season one, and to change
**nothing else**.

#### 3.2 The candidate, exactly

`cell_of(rank, was_prev)` gains one argument, `is_season_opener`, taken from
`previous_primary_detail(...)['is_season_opener']` — a fact about the gap
between ordinals, already computed and already carried onto every artifact
(`qb_allocation.py:110`). Cells become `(rank_clip, was_prev, opener)`.

`qb3_lib.allocate` steps 2 and 3 are **byte-identical**. The share pool is still
resampled, the remainder is still allocated the same way, closure still holds by
construction. Only `pp` changes.

Two arms, one treatment, everything else equal:

- **A0 (baseline)** — `cell_of` as frozen, 5 cells.
- **A1 (candidate)** — `cell_of` with the opener term, 10 cells max.

Same rows, same prefix cut, same seed, same `M_DRAWS`, same frame builder.

#### 3.3 Walk-forward design

Identical in shape to `predeclaration_qb3.md` s.7 and `predeclaration_qb3_ab.md`
s.3. For evaluation season *Y*, every rate in both arms is estimated on seasons
`< Y` only, and the incumbent feature uses a strictly-earlier **ordinal** prefix
cut (`bisect`, not "everything so far" — a team can carry two rows at one
ordinal).

- **Evaluation folds: 2022, 2023, 2024.** 2021 and 2020 are fit-only.
- **2025 is declared unavailable** unless the dt->game-week join in §4 is built
  first, and if it is built it is built and frozen *before* any A1 result is
  looked at.
- Both arms see the same folds. No fold is dropped after the fact; a fold that
  cannot run is reported with a named cause, never averaged in as `nan`.

#### 3.4 Primary and secondary metrics

**Primary (pre-specified, in this order):**

1. **Brier score on `is_primary`**, per QB-game, pooled over folds. This is the
   quantity the treatment changes and it must be scored directly.
2. **CRPS of `s_dropbacks`** against the realised share, per QB-game, pooled —
   the baseline's own metric, so the comparison is like for like.

**Reported beside, never in place of:**

- both metrics **stratified by `is_season_opener`** and by room configuration
  (AGREE / DISAGREE / NO_PREV), with n and cluster counts on every row;
- `P(share = 0)` for the charted QB1 against realised, in each stratum;
- team-closure violation rate, which must remain **exactly zero**;
- the week-1 DISAGREE stratum reported on its own, since it is F4.

#### 3.5 Clustered uncertainty

`qb3_lib.clustered_ci` (`:218-230`) — **team-game** clustered bootstrap,
B = 2000, on the paired per-observation metric difference. Cluster count printed
beside every interval. Additionally, because the boundary strata are small and
one team contributes one row per season:

- week-1 strata are additionally clustered **by team** (32 clusters max), and
  the interval reported is the **wider** of the two;
- **no interval is quoted without its cluster count**, and where the cluster
  count is below 20, results are reported to two significant figures only;
- no naive binomial SE is emitted anywhere.

#### 3.6 Acceptance criteria, fixed before any result

QB3-S1 (A1) is preferred over A0 only if **all** of:

1. pooled Brier on `is_primary` improves; **and**
2. the team-game clustered 95% interval on the Brier difference excludes zero;
   **and**
3. pooled CRPS on `s_dropbacks` does **not** worsen — the clustered 95% interval
   on the CRPS difference must lie **entirely at or below +0.0000**; **and**
4. the direction of (1) is consistent in **all 3** evaluation folds; **and**
5. closure violation rate is exactly **0.0000** in every fold; **and**
6. **no mid-season stratum is degraded**: AGREE weeks-2+ Brier and CRPS must not
   worsen by more than a predeclared equivalence margin of **0.002** Brier and
   **0.002** CRPS, judged by TOST at the 95% level, clustered by team-game.

**Rejection is the default.** If (1) holds but (3) or (6) fails, the return says
*the boundary term improves starter identification at the cost of the share
distribution, and is not adopted.* If the week-1 stratum improves but the pooled
metric does not, the return says *the treatment is confined to 160 team-games
across five seasons and the pooled evidence does not support it.*

#### 3.7 What QB3-S1 may NOT do

Stated now so no later result can be reinterpreted.

- It may **not** clip, floor, bound, cap or manually rebalance any share, and
  may not assign any QB a share of 1.0 by rule.
- It may **not** introduce a fitted constant. `is_season_opener` is a boolean
  read off an ordinal gap; both arms stay empirical frequencies and resampled
  pools. A cell with `n` below a **predeclared floor of 30** backs off to its
  boundary-agnostic parent cell, and the floor is declared here, not chosen
  after seeing which cells are thin.
- It may **not** touch `qb3_lib.allocate` steps 2 or 3, `build_frame`,
  `primary_of`, `fit`'s pool construction, or any R8 / P4C / Q9 parameter.
- It may **not** address Stages 2, 3, 4, 5 or 6. Those stay open. In particular
  it does **not** repair F5 (the starter's zero mass), which is a `build_frame`
  conditioning defect and needs its own step.
- It may **not** consume any sportsbook price, backup-QB availability market,
  or any other market signal, as a feature, rule, filter or conditioning
  variable — not even as a diagnostic in this document.
- It may **not** consume any forecast-season outcome, and **no 2026 game may be
  scored under it.**
- It may **not** be promoted, wired into production, or allowed to change
  `PATH_C_STATE` on the strength of this result. The proposed role if §3.6 is
  met is **prospective shadow only**: both arms computed and recorded per
  team-game, neither published.
- Every artifact it produces must be labelled **EXPLORATORY** — see §4.

#### 3.8 Governance

New component. `predeclaration_qb3.md` (`be61392619d4...`) is not modified and
remains the baseline. `predeclaration_qb3_ab.md` (`07b36d0e1e60...`) is not
modified and is not superseded; QB3-S1 is **narrower than** QB3-AB and does not
subsume it. `predeclaration_qb3_seasonboundary.md` (`6cb5c522e3fb...`) proposes
the same treatment and should be **reconciled with or withdrawn in favour of**
this document by owner decision — the two must not run in parallel.

---

## 4. Evidence ceiling

**What the data in this checkout can and cannot settle. Read this before
reading any result.**

1. **Everything here is EXPLORATORY and cannot be made confirmatory by this
   repository.** 2020-2024 selected the finding, the strata, the classification
   rules and the cell structure. A pre-registration written afterwards does not
   restore independence. No 2026 game has been scored anywhere in this work.

2. **The binding ceiling is the week-1 sample, and it is severe.** Season-opening
   rooms accrue at **32 team-games per season**. The entire historical frame
   holds **160** week-1 team-games, of which 128 have a resolvable incumbent, of
   which the DISAGREE stratum — the one carrying the largest effect — is
   **21 team-games across 16 team clusters**. The 2026 season will add 32.
   **No amount of compute raises this.** A confirmatory week-1 result is roughly
   a decade away at one season per year, and that is the honest answer.

3. **Some questions are nonetheless already settled, because the realised rate
   is exactly zero.** P(starter takes zero dropbacks | he started) = 0/1700 and
   P(week-1 lower-ranked incumbent is primary) = 0/21 bound the truth at
   ~0.0018 and ~0.133 by rule of three. Against model values of 0.0736 and
   0.6167 those are decisive **as refutations**. They are **not** informative
   about what the right value is, and the difference matters: refuting 0.6167
   is not the same as establishing 0.05.

4. **The 2025 fold is recoverable and is the single highest-value ceiling
   raiser.** `nfl/research/inputs/dc25_daily.csv.gz` (146,246 rows, 219 distinct
   dates spanning **2025-08-03 to 2026-03-14**) covers the 2025 season as daily
   snapshots in schema `dt, team, gsis_id, pos_abb, pos_rank` — no `season`,
   `week` or `game_type`. `QB3_FINDING.md` records the 2025 fold as
   `NO_DEPTH_CHART_LEAF_FOR_SEASON` because `stage_a.depth()` declines to
   half-adapt it, which was the right call. Building a governed dt -> (season,
   week) join would add **~544 team-games and 32 week-1 rooms**. It cuts both
   ways: a daily snapshot cut at the pregame instant is *stronger* provenance
   than a season leaf, which may be post-hoc. **This is a data-engineering task
   with a clean acceptance test and it should be done before, not after, any
   further QB3 arm is scored.** It needs a schedule join, which is outside this
   checkout — that is an outbox item, not a blocker.

5. **Play-by-play cannot separate an injury from a benching.** Declared in
   `QB_PARTICIPATION_CAUSAL_AUDIT.json`. `REPLACEMENT_NO_RETURN` (142 team-games)
   is not an injury rate and must never be quoted as one. Any Stage 3 built on
   it inherits that limit permanently.

6. **The classification thresholds are rules, not ground truth**
   (`blowout_margin: 17`, `late_seconds_remaining: 900`,
   `rotation_max_share: 0.35`). They are predeclared, which is what makes them
   usable, but a Stage 5 fitted against them measures agreement with a rule.

7. **`KNEEL_OR_SPECIAL` = 1 team-game.** Stage 6 has essentially **no labelled
   data** in this repository. The realised footprint (second-QB share in
   (0, 0.10) in 6.15% of team-games, ~165 team-games) exists but is unlabelled.
   Stage 6 is not designable from what is here.

8. **F12 is a data gap, not a modelling gap, and it caps Stage 0 absolutely.**
   With no pregame active-53 / practice-squad / reserve signal, Stage 0 can only
   ever be "official inactives, ~90 minutes out". Every PRE-stage board is
   therefore structurally unable to know who is dressed. No estimator repairs
   that; only an ingestion does.

9. **The AGREE agreement in §0.8 is not validation.** 90.7% of the mid-season
   frame is AGREE, so the AGREE cell and the league marginal are nearly the same
   estimate. Do not cite "the model matches reality in AGREE rooms" as evidence
   that the model is sound.

10. **Nothing in this document is adequacy.** No quantity here is called
    unbiased, stable, closed or correct. Where a difference is not rejected,
    that is a failure to reject, not evidence of equivalence; §3.6 clause 6 is
    the only place an equivalence claim is even proposed, and it carries a
    predeclared margin and a TOST because of that.

---

## 5. Handoff

Outbox-shaped items (outside this checkout, not blockers for this workstream):
a 2025 schedule feed to build the `dt -> (season, week)` join in §4.4; and a
pregame roster-status source that distinguishes active-53 from practice squad,
which is the only thing that can lift the Stage 0 ceiling in §4.8.

**CODE CHANGED: NO**
