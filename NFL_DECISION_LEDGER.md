# NFL decision ledger

A running record of what was investigated, what it changed, and what is next.
Newest entry last. Every number here was measured in this repository.

---

## 2026-09-09 — R4 / owner-mode session

### What I was asked

Two things, in order. First a checklist packet (R4) to finish the football
engine. Then, mid-session, a standing instruction to stop executing tickets and
act as principal engineer: investigate, diagnose, quantify, then act, and
reject the proposed path if the evidence points elsewhere.

The R4 checklist turned out to point at the right area and the wrong item. It
assumed the missing piece was rushing conversion. Rushing conversion **is**
missing, and it is genuinely blocked. But the larger defect was somewhere the
checklist did not look.

### Investigated: is there a governed rushing-conversion control?

**No.** `nfl/production/nonqb/rushing_inventory.json` records the full
inventory. Three things are missing and each is an owner decision:

1. **The family is not chronology-legal.** `predeclaration_p5a.md` §9 says the
   distributional family is chosen by CRPS on an **inner validation season
   (Y−1)**. `run_p5a.py` instead scores each family against the **evaluation
   season's own realised rushing yards** and keeps the minimum. No
   inner-validation code exists anywhere in `nfl/research/p5a/`. So there is no
   rule that names a family for an unplayed season, and every reported P5A CRPS
   is a best-of-four minimum taken on the test season.
2. **The promotion bar was never adjudicated.** Applying §14 for the first
   time: system B beats the control A on criteria 1, 2, 3 and 5 in all four
   seasons, and breaches criterion 4 (randomised PIT within 25%) in 2024 only
   (+31.5%). The predeclaration does not say whether criterion 4 is per season
   or pooled. Read one way the control is A; read the other, a player-shrunk
   system is promoted.
3. **The implemented control is not the predeclared control.** §5 specifies a
   pool stratified by RB versus non-RB; `p5a_lib.Pool` is unstratified.

**Action taken:** implemented the interface as a named refusal
(`RUSHING_CONVERSION_CONTROL_UNDEFINED`) carrying all three decisions, plus the
structural prohibitions — a caller-supplied efficiency prior is refused, and
`rushing_yards = carries × point_estimate` is impossible because no control
emits rushing yards at all. **No control was invented.**

### Investigated: does rushing TD share the block? No.

TD2 carries `rush|carry` as a primary estimand with the same `B_pos` baseline
the receiving side already uses in production. Fitted on seasons before 2026:
RB 0.031611, QB 0.058481, WR 0.043224, TE 0.086154. Wired to the same carry
draw. Rushing touchdowns are supported; rushing yards are not. That asymmetry
is real, not an oversight.

### Then the causal chain led somewhere else

Wiring the carry allocation into the joint accounting raised
`qb_rush_contained_in_other`. Chasing it produced the session's largest finding.

**Measured, real 2026 week-1 roster, 32 teams × 200 draws:**

| | |
|---|---|
| D1 team dropbacks | 36.75 |
| QB-summed dropbacks | **79.76** (ratio **2.17**) |
| cells where a team's QBs collectively out-drop their own team | **5,930 of 6,400 (92.7%)** |
| QB rows per team | **2.62** |
| teams with exactly one QB row | **1 of 32** |
| QB rush opportunity as a share of team carries | 0.284 drawn against **0.157** measured historically |

**Diagnosis — and it is not a bug in QB V1.** The QB layer models a passer's
line *conditional on being the team's primary passer*. Nothing selects which of
a team's 2.62 rostered quarterbacks that is. Every other position passes
through the appearance layer; the quarterback does not. On a prospective slate
the engine therefore forecasts 2.62 starters per team.

**Why nothing caught it.** `qb_accounting.reconcile_team` has carried a hard
check of QB rush opportunity against a same-draw team rush budget since R2 — and
it has never refused anything, because no production caller ever passed
`team_rush_draws`. A guard that has never been given its input is not a guard.
There was no dropback counterpart at all, and the dropback half is where the
2.17× lives.

**Action taken:** fed the dormant guard its budget from D1, and added
`reconcile_team_volume` with two new identities
(`qb_dropback_within_team_volume`, `qb_rush_within_team_carries`). The engine
now returns `FAIL[QB_TEAM_VOLUME_INCOHERENT]` naming the gap, instead of
silently producing a 2.17× team. **No model was changed and no draw was
clipped.** Making the defect visible is the deliverable; fixing it requires
research that has not been done.

### Investigated: was production really leaving the research tree alone?

R3 reported a production run rewriting a research report, and fixed it by
snapshotting and restoring the file. **That fix concealed a larger mutation.**
`regenerate.stage_inputs` symlinks every file in the research code directories
into its work tree. When a previous build has left `panel_enriched.pkl` and
`volume_store.npy` in `nfl/research/p4b` — both gitignored, so `git status` says
nothing — the builders open those names for writing and write **138 MB straight
through the symlinks** into the research tree. R3 restored the small JSON and
never saw it.

**Action taken:** `nfl/production/derived.py` — production imports the
regeneration module's pure functions, never its command line, breaks the two
output symlinks before building, and caches into `nfl/derived/` outside the
research tree. `assert_research_tree_unchanged` hashes every file under
`nfl/research` around a production run: **340 files byte-identical**.

A second defect fell out of it: the QB layer read `panel_enriched.pkl` through
`p4c_build.P4B`, which defaults into the research tree, so it had been
depending on a copy someone else happened to leave there. `derived.artifacts()`
now points the research loaders at the cache in one place.

### Current priority ranking of remaining gaps

1. **QB primary-passer selection.** A 2.17× error on team dropbacks dwarfs any
   conversion-layer refinement. Highest value by a wide margin.
2. **Rushing conversion adjudication.** Blocked on three owner decisions, two of
   which are corrections rather than judgements and could be executed.
3. **Receiving calibration.** RC2 confirmed the defect and its predeclared
   repair family does not fix it inside the bounds.

### What is blocked and on what

- Real week-1 non-QB execution: injury reports. 16 games, 0 executable.
- Rushing yards: the three decisions above.
- NFL-1 publication: not authorized, and nothing here requests it.

---

## 2026-09-09 — FTN-M10, the "better matchup endpoint"

### What was investigated

Ten 2025 NFL JSON files supplied by the owner from FTN, described as coming
from a better endpoint for matchups. Every raw byte hashed and sealed in
`nfl/research/ftnm10/ftnm10_provenance.json`; raw bytes NOT committed, on the
FTN-S1 precedent (unsigned draft contract, §5.2 restricts data to Client
property, no evaluation clause).

### Every figure in the brief was verified independently, and all confirmed

10 games, 1,624 plays, 6,181 matchup records, 676 pass plays, 673 with matchup
coverage (99.6%), the stated offensive alignment and defender position
vocabularies.

### The first finding contradicts the premise

**The "better endpoint" is a strict subset of the one we already had.** Game
30351 (DAL@PHI) appears in both this packet and the earlier
`participation_1.json` sample. The matchup payload is identical — 596 records,
all 156 plays. What the OLD endpoint carried and this one does not:
`on_field` personnel, `conditions` (30 charting types: pre-snap box count,
db_count, formation alignment, hash, OL count, backs, coverage shell, motion;
post-snap pass rushers, time to pressure, concept, QB pressure, blitz, stunt,
play-action, RPO) and `advanced_stats` (3,011 records per game).

What is genuinely new is **nine more games**. No new primitive. And motion,
coverage shell and box count — the fields most likely to carry pre-snap
predictive structure — are absent from nine tenths of the sample.

### What the ten games settled about matchup

**FTN-S2's one-game rate ratios do not replicate.** TE_INLINE 1.43 → 0.70,
BACK 0.82 → 1.19, SLOT 0.79 → 0.99, and the eye-catching SCB 0.39 → 0.84.

**The defender class is close to a function of alignment.** Mutual information
1.055 of 1.826 bits (57.8%). WIDE→CB 97.8%, BACK→LB 94.4%. For WIDE, BACK and
TE_INLINE there is effectively only one defender class, so "matchup" and
"alignment" are the same variable. Where they differ (SLOT, TE_FLEX) the
largest contrast has a game-clustered CI including zero.

**The individual-defender (shadow) effect does not survive clustering.** Across
13 CBs with ≥30 charted route snaps, the excess variance over binomial is
+0.00455 — looks like a 6.75pp between-CB SD — but the game-clustered CI is
[−0.00304, +0.00875]. The naive version is the same failure mode the sibling
MLB project records as naive SEs understating by ~3×.

**The decisive downstream bound.** The one forecastable alignment primitive is
a WR's wide/slot mix (persistence r = +0.70, CI [+0.30, +0.96], n = 15, which
survives the position control). Within WRs, the target rate is 0.1835 wide
against 0.1894 slot — **0.6 of a percentage point**. That bounds every
downstream gain, and it explains why FTN-S2 found alignment *worse* than
control: the feature costs degrees of freedom and returns almost nothing.

### The interesting primitive is not matchup

The per-snap **role** label is a direct route-participation observation — the
quantity ROUTE-BB1 was built around and the one nflverse cannot supply. On ten
games: WR 0.936, TE 0.849, RB 0.768 (FTN-S1's single game read 0.989 / 0.882 /
0.818, systematically high at every position). It persists: WR r = +0.797,
CI [+0.43, +0.96].

**But it persists where it is worth least.** RBB1's frozen ceiling puts the
addressable share at RB 0.969 > TE 0.813 > WR 0.636. RB route persistence here
is r = +0.62 on **five pairs**, CI [−1.00, +1.00] — not estimable at all.

### The structural sample limit, and it is the actionable part

190 offensive players charted; **38 in two games; ZERO in three or more.** Only
DET, HOU, KC and IND appear twice. Every persistence question is a single
lag-1 pair from four teams, so no split-half or lag structure exists.

Resolving RB route persistence to ±0.15 needs ~68 RB player-pairs against the
5 available — on the order of 110+ charted games, **and only if teams are
deliberately repeated**. Ten scattered games is close to the worst possible
sampling design for every question the owner asked.

### Verdict

`FTN_MATCHUP_NO_DETECTABLE_INCREMENTAL_VALUE` — a real negative with 9.3× the
FTN-S2 route-play count and a structural explanation, not a null from a thin
sample. Scoped to matchup: the individual-defender question is
SAMPLE_TOO_SMALL, and the role/route-participation primitive is a separate
question this sample cannot close.

### What changed my priority

Nothing about the NFL engine. This does not displace the QB primary-passer gap,
which remains the highest-value open item: a 2.17× team dropback error is worth
more than any receiving-side feature this endpoint could supply.

---

## 2026-09-09 — QB3: the primary-passer defect, followed to its next link

### Owner ruling received

R4 accepted as `RUSHING_CONVERSION_CONTROL_UNDEFINED`; no rushing control to be
adjudicated from contaminated P5A results. FTN-M10 accepted, not generalised.
Priority approved: follow the 2.17× QB/team dropback incoherence.

### The estimand was already specified and never built

`W2_QB_PASSING.md` §7.2 names **"dropback share of team dropbacks"**, gives its
denominator, says shrink toward 1.0 for a listed starter, and records it as
*not measured here*. §7.1 gives the composition:
`QB dropbacks = team dropbacks × QB dropback share`. So this was never a
missing model — it was a specified layer nobody built, and the engine had been
running without the conditioning its own architecture document requires.

**It is not "pick the starter".** Measured on 3,230 team-games: 83.9% have
exactly one QB taking a dropback, 72.1% of QB-games are exactly share 1.0 — but
last game's primary takes **no snap at all in 11.9%** of games. A point
forecast of 1.0 for the incumbent has MAE 0.155 and assigns probability zero to
that 11.9%.

### The depth chart: probed for leakage before it was used

Depth charts are a lagging-file risk. Three probes, run before the design was
fixed:

| probe | result |
|---|---|
| week *w+1* chart predicts week *w* primary | 0.907 |
| week *w* chart | 0.855 |
| week *w* chart on **planned** primary changes (n=324) | **0.377** |
| week *w* chart on **midgame** replacements (n=45) | **0.089** |

A post-hoc file would be near 1.0 on the last two. It is genuinely pregame, and
`w+1 > w` is just next week's chart knowing what happened. Incidental finding:
`stage_a.build` computes `f_depth` and **no feature vector consumes it**.

### Pre-registration first, then the estimator

`predeclaration_qb3.md`, sha256 `be613926…`, committed before anything was
built. Cells, mechanism, three baselines (including current production, so the
size of the defect gets scored), CRPS with team-game clustered intervals, and
the selection rule all fixed in advance.

### Result — every declared baseline beaten, and closure exact

3,851 QB-games, 3 walk-forward folds:

| arm | CRPS | closure violation rate |
|---|---|---|
| **QB3** | **0.0945** | **0.0000** |
| B0 incumbent at 1.0 | 0.1135 | 0.0288 |
| B1 depth-chart QB1 at 1.0 | 0.1347 | 0.0080 |
| B2 **current production** | 0.5842 | **0.9853** |

All three contrasts meet the predeclared rule with clustered CIs excluding zero.

In production, on the real 2026 week-1 slate: **QB-summed ÷ team dropbacks
2.170 → 0.947**, and **5,930 → 0** violating cells out of 6,400. Across the
full 16-game engine run, dropback violations are **0 in every game** and 11 of
16 games now pass the QB team-volume identity outright.

### Two mistakes of mine, both caught by the work

1. **The first fit conditioned on having played.** I built the frame from
   `panel_p3`, which holds only QBs who took a snap, and it reported
   P(primary | rank 1, incumbent) = 0.976 against a true 0.905 and drove
   P(share=0) to nearly zero. The frame has to be the **QB room** — the depth
   chart — with zeros filled in. Production faces a room, not a list of men who
   played.
2. **An empty fold emitted `nan`.** The 2025 evaluation fold has no
   depth-chart leaf (committed leaves stop at 2024; nflverse moved to daily
   snapshots for 2025). The runner averaged it in as `nan`. It now refuses the
   fold by name and the "3 of 4 seasons" the pre-registration asked for is
   **not claimed** anywhere — it is 3 of 3 folds that exist.

### Recorded but deliberately NOT fixed

**Week 1 is structurally different.** The "previous game" is the prior season's
week 18, when starters rest, so the incumbency feature disagrees with the depth
chart on 46.9% of historical week-1 teams and 53.1% of the live 2026 slate,
against 96.5% in weeks 2–4. Week-1 CRPS is not worse — the layer responds by
being honestly uncertain — but the uncertainty is partly an artifact of the
feature definition.

The obvious repair (define the incumbent as the last game QB1 actually started)
was **not implemented**: changing a feature after seeing results is tuning. It
is the first candidate for a QB3b pre-registration.

### The next link, and why I stopped at it

**QB rushing opportunity is still not carved out of the team carry budget.**
The P4C `carries` class allocates RB shares and its OTHER mass is drawn
independently of the QB layer's rush opportunity. Scaling rush opportunity by
the dropback factor moved the slate mean from 0.284 to **0.127** against a
historical **0.157** — closer, but by a different route than the truth, and
24 cells across 5 of 16 games still have the quarterbacks out-rushing their
team.

The fix is an **architecture** question, not an estimator one: whether QB rush
opportunity should be carved out of team carries *before* the RB allocation
runs, so the RB simplex is over the remaining budget. That changes the carries
layer, and it is not something to half-implement.

### Priority now

1. **QB rush / team carry coupling** — the next link, above.
2. **P5A rectification** to the predeclared experiment (owner-authorised as an
   independent task when it becomes highest-value).
3. **QB3b**: the week-1 incumbency definition.

### The boundary, diagnosed rather than merely named

Team carries decompose, 3,230 team-games 2020–2025:

| | mean | share |
|---|---|---|
| team_carries | 26.919 | — |
| RB/FB | 21.757 | 0.8082 |
| **QB** | 4.221 | **0.1568** |
| WR/TE | 0.915 | 0.0340 |
| unattributed | 0.026 | 0.0010 |

P4C's `carries` class is RB-only, so its OTHER mass must cover QB + WR/TE:
required **0.1918** against a fitted `mass_mean` of **0.1989**. The fitted mass
is well calibrated *on average*, and the two quantities track through the tail
(QB p90 0.303 against OTHER p90 0.333). Historically the quarterbacks never
out-rush `team − RB` — 0 of 3,230, arithmetically impossible in the data.

**So the identity is right and the mean is right. What is wrong is that OTHER
and the QB rush draw are independent draws of coupled quantities** — the
owner's own named permanent constraint, one level below the defect just fixed.

The carve-out design (draw QB rush first, allocate the RB simplex over
`team_carries − QB_rush`) changes the **denominator the frozen P4C carries
mass_pool was fitted against**. It cannot be done without either refitting that
accepted artifact or a new pre-registration, and no authorisation covers either.

**This is the boundary. Stopping here.**

---

## 2026-09-09 — J1: the joint rushing-opportunity architecture

### Owner authorisation

A preregistered experiment on the correct joint factorization of
`team carries → QB rush + RB/FB + WR/TE`, with an explicit instruction not to
assume the answer is "carve QB first."

### Scoping surfaced a root defect that widened the question

`team_volume_v1.forecast` draws its five team metrics **independently** — a
separate RNG stream per metric. Measured on 3,230 team-games:

| within-team correlation | historical | D1 draws |
|---|---|---|
| carries vs dropbacks | **−0.393** | **−0.004** |
| carries vs targets | **−0.388** | **+0.007** |

The dominant joint structure in team football is absent from the draws. A single
draw can put a team at the 90th percentile of both dropbacks and carries. The
QB-rush/OTHER incoherence that started this line of work is one symptom of it.

Two structural facts made the widening necessary rather than optional: QB rush
decomposes **exactly** into scrambles + designed (3,230 of 3,230), and
**scrambles are a passing by-product that lands in the rushing column**, so
`team_carries` is partly generated by the dropback process. You cannot evaluate
a carries factorization while carries and dropbacks are drawn independently.

### Result — and the obvious answer lost

| arm | energy score | reproduced corr(tc, db) | acceptance rule |
|---|---|---|---|
| A0 control (status quo) | 8.5749 | +0.0005 | — |
| A1 carve QB first | 8.5689 | −0.0019 | **NOT MET** (CI includes zero) |
| A2 causal split | 8.5682 | −0.4231 | **NOT MET** (a marginal 10.1% worse) |
| **A3 joint residual resampling** | **8.4924** | **−0.4062** | **MET** |

**A1 is the lesson.** Carving the QB out first fixes the accounting invariants
and does *nothing* for the joint structure — the reproduced correlation stays at
−0.002. The visible symptom was an accounting violation, so the obvious repair
was an accounting repair, and it leaves the actual defect untouched.

**A2 reproduces the coupling but compounds error** through
snaps → split → scramble rate → allocation, breaching the 2% marginal bound.

**A3 — the cheapest arm — won.** It changes only the draw: one historical
team-game index per simulation draw, every residual from that game. No fit
moves. Accounting violations and clipping both go to zero, because the
components now come from a single real team-game that is internally consistent
by construction.

**P4C does not need replacing.** The pre-registration said that if A2 won, the
frozen carries mass pool would need refitting against a denominator it no longer
draws. A2 did not win.

### A defect in my own implementation, caught by my own test

The first production version drew the shared index from the **global** residual
pool, while all five metrics use `coach_empirical` and resample from *that
coach's* residuals. It shifted `team_rz_carries` by −5.2% and put 0.49% of draws
on the zero floor while the finding claimed no marginal had moved. Corrected to
draw the shared index from the coach's own pool: worst marginal shift 1.1%, zero
floor draws, coupling −0.359/−0.349 against historical −0.393/−0.388.

Sharing an index across metrics is only legitimate if each metric still draws
from its own fitted pool.

### Shipped as opt-in, and that is the boundary

`joint_residuals=True`, **defaulting off**. No fit changes, but every drawn
number in the simulator changes, so switching it on is an owner decision. The R2
cache-equivalence property is preserved and now tested under both modes.

### Queue

1. **Owner decision:** turn `joint_residuals` on by default.
2. P5A rectification (retained).
3. QB3b week-1 incumbency (retained).

---

## 2026-09-09 — J1 downstream: A3 on inside the full engine

### Owner ruling

J1 accepted as an EXPLORATORY REHEARSAL candidate; A3 preferred; authorised to
turn `joint_residuals=True` on in rehearsal and inspect the downstream system as
a joint object. Explicitly: do not stop at "A3 integrates successfully."

### It integrates, and the marginals held

Full engine, 16 games, 400 draws, identical seeds. Team carries↔dropbacks moved
+0.002 → **−0.373** (historical −0.393) and carries↔targets +0.002 → **−0.352**
(−0.388), *through the full non-linear composition*. Every player marginal moved
by ≤2.5%, the p99 receiving-yard tail by **0.1%**, accounting unchanged, no
clipping. The owner's warning was the right check and the answer was that the
marginals survive.

### What it exposed is the actual result

Restoring one dependence made the absence of the others measurable. Benchmarks
from 3,230 historical team-games:

| dependence | simulator (A3) | historical |
|---|---|---|
| **team passing TD ↔ receiving TD** | **+0.055** | **1.000000, exact 3,230/3,230** |
| team passing yards ↔ receiving yards | +0.334 | **0.9996**, mean diff **0.26 yd** |
| opposing teams' carries | +0.001 | **−0.535** |
| opposing teams' snaps | +0.012 | **−0.464** |
| RB carries ↔ own targets | +0.053 | +0.308 |
| competing receivers' targets | +0.207 | +0.584 |

**Passing and receiving yards are the same quantity.** The simulator draws them
in two independent layers and they disagree by ~100 yards on ~230 — about 45% —
in **every** draw, while the touchdown identity, which has no lateral exception
at all, fails in 89–99% of draws.

### A third dormant guard

`qb_accounting.reconcile_cross_layer` has been written, correct and `DEFERRED`
since R3 because no caller ever handed it the receiving draws. They were in the
same run the whole time. Now fed, and it fails loudly. That is three dormant
guards in this project — after `assert_batch_games_are_new` and
`reconcile_team`'s rush check. **A guard that has never been given its input is
not a guard**, and this project keeps writing them and not wiring them.

Fed honestly: the guard enforces row alignment while comparing team totals, so
each side is summed to `(1, m)` first — mathematically identical to the
`py.sum(0) - ry.sum(0)` it computes internally. The guard was not loosened.

### A3's own verdict

It moved passing↔receiving from +0.005 to +0.334 because both layers now inherit
the same team draws. It gets nowhere near 0.9996 because the two layers still
draw the shared quantity independently. **A3 is a partial mitigation of a bigger
defect**, and it earned its place mostly by making that defect visible.

Opposing-team dependence is structurally out of A3's reach: it couples metrics
within a team, and D1 draws each team independently.

### Revised priority — this supersedes the queue

1. **Cross-layer passing ↔ receiving.** An exact identity, violated in ~100% of
   draws by ~45% of the quantity, with a written guard already waiting.
2. **Opposing-team dependence.** Needs a game-level play-budget object that does
   not exist.
3. **Within-team player dependence.** RB carries↔targets understated 5.8×.
4. P5A rectification (retained).
5. QB3b week-1 incumbency (retained).

---

## 2026-09-09 — NFL-INTEL-1: reconciling an external capability audit

### What was asked

Classify every material capability in a supplied Perplexity report against the
real system, **trying to falsify it rather than agree with it**, then say
whether anything in it displaces cross-layer passing ↔ receiving.

Report: `c43a40fb-nflintel1frontiercapabilityaudit.pplx.md`, sha256
`8d9d1945…`, 484 lines, read in full.

### Nothing displaces cross-layer

The report ranks route/block/release participation **first** and predictive
dependence structure **ninth**. Route participation is blocked on
`pbp_participation`, which **404s for 2026** — verified twice daily by our own
watcher — and its oracle ceiling was already measured by ROUTE-BB1 (pooled
ρ_max **0.756**, 23.9% of rows unreachable even at routes = pass_snaps).
Dependence structure is where an exact identity is violated in **93–100% of
draws by ~45% of the quantity**. The report labels its own table "analyst
judgments about research order, not measured expected value," which is the
correct disclaimer and the reason it does not reorder the queue.

### The clearest falsification: H4's baseline does not exist here

The report proposes testing a disjoint multinomial over dropback terminal
states against "separate marginal models". `qb2_lib.simulate` already draws
`SACK ~ Binom(DB, ps)` then `SCR ~ Binom(DB−SACK, psc/(pa+psc))` with the rates
normalised to the simplex first — algebraically a `Multinomial(DB; pa, ps, psc)`
— and closes it hard in two places (`QB_V1_INCOHERENT_DRAWS`,
`QB_DROPBACK_IDENTITY_VIOLATED`). The separate-marginal alternative was tried
and rejected: it broke coverage to **0.715** (sacks) and **0.724** (rush
opportunities) at nominal 90.

### Where the report caught me, and how I nearly published the wrong refutation

It says receiving yards can accrue without a reception. I added
`zero_receptions_implies_zero_yards` as a hard identity last session.

Measured in RC1's own frame: **0 of 25,934** player-games violate it. That
refutation is worthless — `build_recv.py` keys on `receiver_player_id`, so a
lateral-only receiver is **absent from the frame, not present with zero**.
Reading it as evidence would have been this project's own worst defect class,
committed while auditing someone else for it.

Measured on raw pbp, 2020–2025 REG, 25,947 player-games: **82** lateral
receptions, **13** recipients never targeted themselves, **16 player-games with
zero receptions and nonzero receiving yards** — **6.17 per 10,000**. The report
is right. The identity is exact for our generator, which cannot lateral, and
false of realised football. It matters when the identity is used against
realised outcomes, which CLAUDE.md rule 6 already forbids. Queued as a small
separate commit: a named exception mirroring `LATERAL_EXCEPTION`, not a
loosening.

Second caution, also tested and also correct: targets must sum to **targeted**
attempts, never attempts. Measured over 3,230 team-games — mean gap **3.7997**,
median 4, max 13, equal in only **128 (3.96%)**, and targets never exceed
attempts. We never imposed the equality; it is now quantified, and it is
load-bearing for the cross-layer work.

### What else was already covered, with the artifact

- Provenance / as-of / definition versioning (report's item 10, ranked last):
  six separately named clocks, `schema_fingerprint`, two accepted
  `pbp_participation` schemas, content-addressed vintages. Built before the
  report was written; the report ranks it least football-relevant.
- Dynamic role state (item 3): Stage-2's accepted estimator is `ewma_hl2`, a
  two-game-half-life updating state, not the season-to-date aggregate H2 names
  as its baseline.
- Contextual efficiency (item 8): RC1 closed it, and
  `condition_to_reopen` = "materially new INFORMATION, not another same-input
  estimator ladder" — which is what the report recommends.
- Clustered dependence-unit validation (H6): settled practice since C2.

### One genuine new item

The report's three-way availability split — uncertainty about **participating**,
the distribution **conditional on playing**, and **in-game exit** — is three
channels, and this system carries one binary. Named here for the first time.
Not urgent; recorded.

### Queue, unchanged in order

1. Cross-layer passing ↔ receiving.
2. Opposing-team dependence.
3. Within-team dependence / role-aware reallocation — adopt the shape of the
   report's experiment 3, which is the best-designed item it contains.
4. Lateral exception on the receiving identity.
5. P5A rectification. 6. QB3b week-1 incumbency.

---

## 2026-09-09 — XL1: the shared passing event, generated once

### The defect was not the defect it was reported as

The previous entry recorded cross-layer passing ↔ receiving as violated "by ~45%
of the quantity". That figure was a **per-draw absolute difference read as a
level error**. Measured on the full slate, 32 team-games × 400 draws, against
3,230 historical team-games: the receiving side gives 212.90 team passing yards,
the QB side 218.75, history 237.88. The two sides are **within 2.7% of each
other**. Correcting my own number.

It is a **pure dependence defect**. For independent X, Y,
`E|X−Y| = sqrt(2/pi)*sqrt(sx^2+sy^2)` predicts 7.46 / 103.9 / 2.03 against
observed 5.42 / 85.4 / 1.52 — the shortfall being exactly the correlations
(0.522 / 0.343 / 0.060) that A3 and the shared team volume induce. The identity
held in **0 of 12,800 draws**.

That changed the design: a candidate repairing the identity by moving one side's
level onto the other trades a dependence defect for a level defect, so Gate 2
scored levels with margins fixed before the candidates ran.

### Pre-registered first

`nfl/research/xl1/predeclaration_xl1.md`, sha256 `60fe3fbc…`, committed before
any candidate existed. `run_xl1.py` refuses to run against a modified file.

### Ownership, and the interception that needed nothing

A completion is one event producing a completion, a reception, one gain credited
to both, and possibly one touchdown credited to both. The throw budget is the
passer's; the assignment is the competition's; the gain belongs to the
completion. Historical decomposition: 33.55 throws = 32.13 targeted + 1.42
untargeted, so the identity uses **targeted throws**, never attempts.

Interceptions need no separate handling and it looks like they should: an
intercepted pass carries a `receiver_player_id` with `complete_pass == 0`, so
RC1's catch rate already has them inside its incompletion mass. Modelling them
would double-count.

### Result

C3 deals the QB's targeted throws to receivers by the existing simplex and then
runs RC1 and TD2 **unmodified**. Gate 1, 12,800 draws per link:

| arm | completions | passing yards | passing TD |
|---|---|---|---|
| B0 | 12,800 violate | 12,800 violate | 11,948 violate |
| C1 | **0** | **0** | **0** |
| C3 | **0** | **0** | **0** |

Exact by construction, no clipping. Gate 2 team level: both inside the 5%
margin, and **C3 beats C1 on all three**, so the simplest-wins ordering resolves
to C3 — which also credits each completion to the passer who threw it, the thing
C1 can only approximate through an allocation.

C3's player displacement is **dispersion, not level**: median mean displacement
**+0.008** overall and **−0.001** for players with mean ≥ 3, against a median
p95 lift of **+0.171**. B0 computed `T = share × volume`, treating a count as
deterministic given the share; C3 deals them, restoring the multinomial term.
The arithmetic predicts a ~20% p95 lift against 17% observed. Whether the wider
tail is better calibrated is **not established** — no outcomes exist.

### The successor problem, localised

Every arm sits 8–10% below history on the whole passing chain, and neither
candidate touches it. Measured straight from D1:

| metric | sim | history | rel |
|---|---|---|---|
| team_carries | 27.70 | 26.92 | +2.9% |
| team_dropbacks_part | 36.53 | 37.61 | −2.9% |
| **team_targets** | **29.19** | **32.13** | **−9.2%** |

**One D1 metric is wrong, not the volume layer.** C3 does not consume
`team_targets` at all, so it routes around this — a consequence, not an
intention.

Second, stated as a **lead and not a diagnosis**: attempts over dropbacks is
0.833 in the simulator against 0.892 historically, so sacks plus scrambles take
6.10 dropbacks against 4.32. It compares a 2026 week-1 roster against a
2020–2025 realised mean, which are different populations.

### Governance

Nothing promoted. `SHARED_PASS_DEFAULT` is 'off'; production runs B0. One
additive production change: the engine payload now carries the allocation
layer's outputs, and an equivalence gate verifies B0 reproduces byte-identically
through the study path (48/48). Suite 42 modules, 445 functions, 2,577 checks,
0 failing. PATH_C_STATE untouched, G0A 11/12, NFL-1 NOT AUTHORIZED.

### Queue

1. **D1's team_targets, 9.2% low on its own.** Largest measured level defect.
2. Opposing-team dependence.
3. The dropback attempt share (a lead).
4. Role-aware reallocation — NFL-INTEL-1's experiment 3 is the right shape.
5. Lateral exception on the receiving identity. 6. P5A. 7. QB3b.

---

## 2026-09-09 — OWN-1: target-volume ownership audit

### Owner ruling received

XL1 accepted as `C3_SHARED_PASS_REHEARSAL_CANDIDATE`, not promoted. Explicit
instruction: **do not fit a better D1 team_targets model.** Settle ownership
first. Diagnose the throw share chronology-cleanly before calling it a defect.

### team_targets is not an independent quantity. It is targeted throws.

Exact in **3,230 of 3,230** team-games. So are the other two: D1's
`team_dropbacks_part` is the pbp `qb_dropback` count and `team_carries` is the
`rush_attempt` count, both exact 3,230/3,230. `mk_denom.py:75` builds
`team_targets` as `+= r['targets']` — a sum of the same player quantity the
receiving layer allocates.

And it is a deterministic function of the QB chain:

```
targeted == dropbacks - sacks - scrambles + excluded - untargeted
   EXACT in 3,229/3,230, worst residual 1
```

The `excluded` term is fully identified with nothing left over: 819 plays over
six seasons that are a throw, sack or scramble but carry `qb_dropback == 0` —
**429 spikes, 389 nullified plays, 1 field goal**. Every dropback is a throw, a
sack or a scramble; zero unclassified.

**No production component needs D1's drawn team_targets under C3.** The one
that could have killed C3 does not: the target shares were fitted as
`y_targets / team_targets`, and since that denominator IS targeted throws, the
fitted shares stay valid without refitting.

### I was wrong about the -9.2%, and about the level gap generally

Every quantity here is in monotonic decline — targets 33.81 → 30.53,
completions 22.96 → 20.62, passing yards 254.88 → 225.02. XL1 compared a 2026
forecast against the **six-season mean**. Against 2025:

| | XL1 said | vs 2025 |
|---|---|---|
| D1 team_targets | −9.2% | **−4.4%** |
| B0 passing yards | −8.0% | **−2.8%** |
| B0 completions | −9.0% | **−4.2%** |
| B0 passing TD | −9.0% | **−8.6%** |

**About half the "8–10% level gap" was a stale baseline.** `history_levels.json`
now carries per-season levels and states that a level comparison must use
`by_season[most_recent_season]`; only the identities, which do not trend, may
use the pooled mean. What survives is **passing TD at −8.6%**, the one metric
not in decline.

### The terminal-state mix is NOT a defect — the owner's warning was right

Chronology-clean, prior-only history of the **84 quarterbacks actually on the
2026 week-1 slate**, n = **97,761 dropbacks**: pooled sack+scramble share
**0.1153**, dropback-share-weighted **0.1253**, simulator **0.1215**. The model
reproduces the share-weighted prior rate of these exact passers to within
0.004. The population explains the gap to the league mean, not the model. Had I
inferred from the headline I would have repaired a model that is correct.

### OWN-1: what chasing it actually found, and it is mine

`0.8318 = 0.8785 x 0.9468`. The second factor is a leak.

`run_game` zeroes a forecast row the allocation does not name. It had **no
counterpart for the reverse**: a quarterback in the QB3 depth-chart allocation
whom QB V1 refused for having no prior appearance. His allocated dropback share
was applied to nobody and left the system with no refusal. Real 2026 week-1
slate, 400 draws:

| | |
|---|---|
| unforecastable QBs in the allocation | **35** |
| teams leaking | **23 of 32** |
| share reaching nobody | **1.7014 of 32.0000 = 5.3168%** |
| worst | MIA 33.1%, NYJ 30.4%, WAS 19.6% |

An absence read as success, in code I wrote in R4. It nearly accounts for the
whole remaining gap: C3's completions are −5.2% against 2025 and the leak is
−5.32%; removing it would put C3's targeted throws at ~30.8 against 30.53.

**Named, not repaired.** `reconcile_allocation_share` refuses
`QB_ALLOCATION_SHARE_UNCONSUMED` and is wired into `run_game` at the one place
holding both sides. It deliberately does **not** renormalise the survivors —
that would be generating a fallback allocation, and it would erase the number
that reveals the gap. Three defensible answers (refuse the team, a cold-start
passer prior, route to the positional pool) and all three are owner decisions.

### Queue

1. **OWN-1** — owner decision. It blocks both studies below, because a 5.3%
   leak in the throw budget would be scored as a C3 property.
2. Passing TD −8.6% against 2025 — the only surviving level gap.
3. **XL2** — derived vs independently forecast target budget. Pre-registration
   first; development data, so it can only reject.
4. C3 retrospective falsification (owner-authorized, run after OWN-1).
5. Opposing-team dependence. 6. Role-aware reallocation. 7. P5A. 8. QB3b.
9. Lateral realised-outcome exception.

### Addendum — I was wrong that OWN-1 blocks the retrospective

I asserted that the 5.32% leak would contaminate a C3 retrospective. That was an
assertion, not a measurement. Measured on the historical depth charts against
strictly-prior passer appearances:

| segment | n | no prior | rate |
|---|---|---|---|
| week 1, rank 1 | 162 | 41 | 25.31% |
| **week 2+, rank 1** | 2,851 | **2** | **0.07%** |
| week 2+, rank 2+ | 4,179 | 852 | 20.39% |

And the 25.31% is mostly the panel edge: `panel_p3` starts in 2020, so 2020
week 1 is **32/32 by construction**. Excluding it, 2021–2024 week-1 rank-1 is
**9/130 = 6.92%**. Reading that 2020 column as a defect rate would have been the
same error this audit exists to catch, committed inside the audit.

**So OWN-1 is a week-1 cold-start condition, not a general defect.** The 2026
figure of 5.32% sits inside the historical week-1 range rather than being
anomalous, and it nearly vanishes from week 2 — two rank-1 rows in 2,851.

**The C3 retrospective and XL2 are unblocked** on week 2 onward, excluding 2020,
which a strictly chronological forward-chained design excludes anyway. The guard
stays as written and does not become week-1-only.

OWN-1 still needs the owner decision, because week 1 is the slate the system is
pointed at. And two of its three options — a cold-start passer prior, or routing
the share to the positional pool — are **cold-start behaviour**, and the
cold-start freeze is not mine to alter. Flagged rather than walked into.

Reproduced by `audit_ownership.py` section E.

---

## 2026-09-09 — OWN-2: characterising the QB cold-start population

### Owner ruling received

OWN-1 accepted; the 5.3168% unconsumed allocation mass is the highest-priority
actionable defect. Do not renormalise survivors, do not permanently solve by
refusing teams. Develop a chronology-clean cold-start state. **Characterise
first, rule out data/identity defects before calling anything a cold start, and
preregister any estimator comparison.** Also: D1 disagreement with the
C3-derived budget must be exposed, not made a hard production refusal — an
estimator disagreement is not a football invariant violation. Recorded.

### There is no data or identity defect. Zero, on both populations.

| population | n | data/identity defects |
|---|---|---|
| 2026 wk1 live slate | 35 | **0** |
| historical rows 2022–2024 | 275 excluded of 4,414 | **0** |

Every excluded quarterback genuinely has no prior NFL dropback. This is a
cold-start problem and not an ingestion problem, measured rather than assumed.

### Depth rank carries the signal; the class label does not

| class \| rank | n | P(dropback) | mean db given played |
|---|---|---|---|
| ALL \| rank 1 | **6** | **1.0000** | **42.67** |
| ALL \| rank 2 | 87 | 0.1494 | 13.00 |
| ALL \| rank 3+ | 182 | 0.0604 | 23.36 |
| APPEARED_WITHOUT \| rank2 | 20 | 0.1500 | 13.00 |
| PRIOR_ENTRANT \| rank2 | 57 | 0.1579 | 14.33 |
| DEBUT_LIKE \| rank2 | 10 | 0.1000 | 1.00 |

Rank moves P(dropback) by **17×**; the class label moves it within noise. The
samples cannot reject a class difference — what they cannot do is support one.
**Week 2+, rank 1 is 0 of 1,731**: the starter is never unforecastable after
week 1.

The whole evidence base is **30 played weeks out of 275**, with **n = 6** in the
decisive rank-1 cell.

### Pre-game inputs are static career markers only

35/35 have depth rank, entry year, experience. **Only 18 of 35 have a draft
number**, and the 17 without hold 0.6313 of the 1.7014 lost share. Zero have
prior NFL performance, by definition. The real causal driver is team-level: the
injury and practice report for the whole quarterback room.

### Two defects in my own OWN-2 code, both caught before reporting

1. **A file's coverage limit read as an absent attribute.** `weekly_rosters` in
   this checkout holds only 2026, so a "was he rostered before" branch could
   never fire; fourteen QBs were bucketed as having no career marker when they
   had one. Now tested against `panel_p3`, which spans 2020–2025.
2. **A season-granular history answering a within-season question.** The first
   pbp scan aggregated to the season and placed each season's total at week 1,
   so a QB debuting in week 5 was credited with prior dropbacks in weeks 2–4.
   That version reported **172 of 275 as DATA_OR_IDENTITY_DEFECT (62.5%)**.
   Keyed by week it is **zero**. Had I reported it, the mission would have been
   redirected to hunting an ingestion defect that does not exist.

### Constraints on the estimator, fixed before one is built

Two margins (P(dropback) and the distribution given played); rank-conditioned
and aggressively shrunk; ~30 positive observations so complexity is
unsupportable; closure is the objective rather than accuracy; a week-1 and
backup instrument, never a general replacement for QB V1; and any use of draft
number must say by name what it does for the half that lacks one.

### Next

Pre-register OWN-3, the cold-start estimator comparison. Until it clears,
`QB_ALLOCATION_SHARE_UNCONSUMED` stays fail-closed.

---

## 2026-09-09 — OWN-3: the cold-start state, and a second leak

### Pre-registered first

`nfl/research/own3/predeclaration_own3.md`, sha256 `aedced9c…`, committed before
any candidate existed. `run_own3.py` refuses to run against a modified file.

### The ladder starts below a model

Verified by reading `qb2_lib` BEFORE writing the pre-registration, and declared
there so it could not be presented as a result: `rung_weight` returns 0 at
`h_games == 0`, `rung_rate` returns the pool value on an empty `h_seq`, `_mix`
returns a pure pool resample on an empty own-history array. **QB V1 already
runs on a zero-history row.** The `h_games >= 1` filter was the only exclusion.

So **C0** is a pool-path passthrough with **zero new parameters**.

### C0 closes the share-level leak and passes the equivalence gate

| gate | B0 | C0 |
|---|---|---|
| allocation closure (full slate, m=400) | FAIL 5.3168%, 23/32 teams | **PASS 0.000000%, 0 teams** |
| no survivor renormalisation | — | **PASS**, mass exactly 32.0000 |
| terminal-state closure (8 games) | PASS 0/4,300 | **PASS 0/5,800** |
| dispersion | n/a | **PASS**, 0 of 15 undispersed |
| no forecastable draw changed | — | **PASS**, 0 diffs in 924 comparisons |

### A second leak, which C0 does NOT fix

`run_game` sets `fac = 0` when a passer's raw QB V1 draw is zero dropbacks, so
his allocated target is dropped in exactly those draws. Full slate, m=200:
**14 of 119 rows affected, 0.6063 of 1171.3827 target dropbacks lost =
0.0518%** — but the **worst per-draw shortfall is PHI 37.71**, NE 33.64. In the
draws where a team's primary drew zero, the team's whole passing game vanishes
for that draw. Negligible in the mean, not in the tail.

Same class as OWN-1. **OWN-1's leak had two components**; C0 closes one. The
other is a composition fix, not a cold-start model, and is out of OWN-3's
pre-registered scope.

**Correction to my own earlier reading:** on one game I saw team-dropback
closure become exact under C0 and said so. Over 16 team-games it is not —
max abs diff **0.862**. One game was not general.

### C1 is not admissible, and the measurement that kills it is the useful part

| cell | n | observed | model | gap |
|---|---|---|---|---|
| cold \| rank 1 | 6 | 1.0000 | 0.5887 | −0.4113 |
| forecastable \| rank 1 | 1,610 | 0.8689 | 0.8863 | +0.0173 |
| cold \| rank 3+ | 167 | 0.0659 | 0.1930 | **+0.1272** |
| forecastable \| rank 3+ | 473 | 0.1226 | 0.2376 | **+0.1150** |

At rank 3+ the over-forecast is the same size for quarterbacks the system CAN
forecast. It is a **QB3 allocation property**, not a cold-start one, measured on
473 forecastable cases. And 6-of-6 at rank 1 is unremarkable against the general
0.8689 rate — `0.8689^6 = 0.43`.

Also: any participation correction moves share inside the room, changing a
forecastable teammate's draw, which pre-registration prohibition 8 rejects. The
correction belongs to **QB3b**, and now arrives with a number.

**C0 wins by the declared simplest-wins order**, as the pre-registration
predicted in advance.

### Outstanding

The full suite passes after the change: **42 modules, 447 functions, 2,593 checks, 0 failing** — including a new seven-check guard that `include_cold_start` defaults False in both functions.
The three affected modules pass (144 checks, 0 failures) but nine
`test_qb2_production` cases cannot execute outside the suite harness. Full-slate
Part A at m=400 also did not complete. Compute, not findings.

### Queue

1. Owner ruling on `include_cold_start`.
2. The draw-level leak (§3) — a composition fix.
3. Ruling on the rushing gate.
4. QB3b, with the participation table.
5. Then rerun the W1 rehearsal and remeasure.

---

## 2026-09-09 — OWN-4: draw-level mass conservation

### The ruling's first question answers itself: it is the same defect, a third time

`qb2_lib.simulate` draws **V, the team dropback volume, from the team-dropback
pool and S, the QB's share, from the share pool**, then `DB = rint(V*S)`. Those
are the two quantities **D1 and QB3 already own**. `run_game` reconciles the
duplicate by division, `fac = target/drawn`.

**The zero denominator is not an edge case — it is the signature of two layers
owning one level.** Third instance, after passing↔receiving yards and
team_targets↔targeted throws.

### The repair needs no estimator, because the rates are row-level scalars

Every rate below the level (`ps`, `psc_c`, `pc`, `ptd`, `pint`, `dpd`) is a
row-level scalar, so **any non-zero draw of a row carries the same rates**. A
zero cell borrows a **donor draw from the same row** and is scaled to the
allocated target — exactly what the composition would have done had the level
draw not been zero. `qb_accounting.conserve_allocated_mass` returns a per-draw
source index; unaffected cells map to themselves; a row with no donor anywhere
**refuses** by name.

Nothing fitted, nothing clipped, no survivor renormalised, QB3 shares untouched,
per-QB attribution preserved because the donor is that quarterback's own row.

### Result

| gate | before | after |
|---|---|---|
| team dropback closure per draw | max abs diff **0.862** | **0.0** |
| max per-draw shortfall | **37.71 dropbacks** | **0.0000000000** |
| allocation share closure | 5.3168% lost | **0.000000%** |
| unaffected draws altered | — | **0 of 924 comparisons** |

Repair fired on 3 cells in 8 games at m=200; 20 of 47,600 across the full slate.
Suite **42 modules, 448 functions, 2,607 checks, 0 failing**.

### What I did not do, and why it is not caution

**R2 — remove QB V1's level draw entirely** and generate the cascade at the
allocated level. That removes the cause rather than the symptom, but it changes
**every** quarterback's draws rather than the 20 affected cells, and it has a
real tension: the binomial cascade needs an integer level while exact team
closure currently relies on floats. More than one defensible answer, so it needs
its own pre-registration. Recorded as OWN-4's successor.

### Outstanding

C3 shared-pass closure not re-verified under the repair. The identities hold **by
construction** and the repair changes only which draw a QB composes from — a
reason to expect them to hold, not evidence that they do. Queued.

### Rushing gate

Classified per the ruling as
`PREEXISTING_SYSTEM_GATE_FAILURE_OUTSIDE_OWN3_CAUSAL_SCOPE`. Fails identically
under both arms; neither C0 nor OWN-4 causes or cures it; not waived.

---

## 2026-09-09 — OWN-5: C3 clear, and the rushing defect is a units mismatch

**Verdict: `OWN5_C3_CLEAR_RUSH_DEFECT_IDENTIFIED`**

### Part A — C3 re-verified under OWN-4

12 team-games, 200 draws. All three identities **0 of 2,400** violating draws.
Orchestration equivalence **18/18**. And the OWN-4-specific risk tested
directly: **13,278** post-composition per-dropback ratios traced, **0** failed
to appear in that quarterback's own pre-composition draws — no cross-player
donor contamination. 3 cells repaired in the run.

### Part B — the rushing gate is an accounting defect, and R4's premise is stale

Historical closure is exact, 3,230/3,230:
`team_rush_attempts 26.9192 = qb_rushes 4.3635 + nonqb_rushes 22.5557`, and
`qb_rushes = scrambles 1.8155 + kneels 0.7746 + designed 1.7734`. Through the
panel: RB **0.8082**, QB **0.1568** (this is R4's "0.157"), WR 0.0302, TE
0.0038, unattributed **0.0000**.

**The quarterback's rushing is now right.** Simulator QB rush / team carries is
**0.1369** against 0.1333 ex-kneels. **R4's 0.284 is stale — QB3's allocation
already fixed it and I should not have carried it forward unmeasured.**

**What is wrong is the space left for him.** RB allocated 0.8750 against a
historical 0.8082; `other` 0.1250 against 0.1918. He needs 0.1369 and has
0.1250, so the containment guard correctly refuses.

**Mechanism, identified at the source.** `mass_pool` is fitted CORRECTLY as a
share — `p4c_build:151 pool = mall - ms`, and `mall` is 1.0 because the panel
closes — with a fitted mean **0.1989** against a historical non-RB mass of
0.1918. But `p4c_lib.allocate` consumes it as an **unnormalised weight**:
`other = w_other/(sum(W*A) + w_other)` where `sum(W*A) ≈ 1.286` is on the
relative-weight scale. A drawn share of 0.1837 is diluted to **0.1250**.
Normalised, it would be 0.1866.

Not duplicate ownership, not double counting, not an estimator defect: a
**fitted share consumed as an unnormalised weight**.

**Repair specified, deliberately not applied.** `S_i = (1-w_other)*W_iA_i/ΣWA;
other = w_other`. Predicted RB 0.8750 → 0.8163, other → 0.1837. Not applied
because `allocate` is a frozen P4C module that also serves the **targets**
simplex, which currently passes, and because `W` was fitted with this
`allocate` in the loop — whether `W` absorbed the dilution is unsettled. An
owner decision about a frozen fitted artifact, needing gates across both
simplexes.

### Part C — R2 pre-registered, not implemented

`nfl/research/r2/predeclaration_qb_level_ownership_r2.md`, sha256 `3d7beeb3…`.
QB V1 owns conditional rates only and never a level; integerisation happens
AFTER allocation by largest-remainder so `Σ n_j == N_t` exactly by
construction; the invariant changes from float-exact to integer-exact and that
is declared rather than discovered; the OWN-4 donor mechanism must become
unreachable and be removed.

### Queue

1. Owner decision on the P4C normalisation repair (both simplexes).
2. Kneels are owned by nobody — 0.7746/team-game inside D1's carry budget.
3. Then the W1 rehearsal rerun and the passing-TD question.

---

## 2026-09-09 — OWN-6: P4C units, and a seed that is not a seed

**Verdict: `P4C_UNITS_FIX_NO_REFIT_REQUIRED`.** Production untouched (0 files).

### The fit was already written to the corrected contract

`allocate` appears in `p4c_build.py` **once, in a comment**. `fit_params`
estimates every parameter directly from realised shares — no loss, no
optimisation, no allocator in the path — so a refit under C1 returns
byte-identical parameters. **C2 is a formality, not an experiment.**

And `alpha0`, the one fitted quantity that references a normalisation at all, is
estimated with `scale = (1.0 - mass_mean) / Σ_C` — **that is C1 exactly**,
written into the frozen fit. The allocator is the piece that diverged.

**`W` did not absorb the dilution.** If it had, C1 would overshoot; it lands.

### Three arms on one captured draw

| carries | C0 | **C1** | historical |
|---|---|---|---|
| modelled (RB) mass | 0.891489 | **0.811104** | **0.8082** |
| other mass | 0.108511 | **0.188896** | **0.1918** |

| targets | C0 | **C1** | fitted mass_mean |
|---|---|---|---|
| other mass | 0.005288 | **0.012252** | **0.0113** |

Both arms close exactly; zero-share fractions identical; p99 essentially
unchanged; **per-draw ordering preserved**. The receiving simplex is diluted by
the same defect but only by **0.7pp of team targets**, and C1 moves it toward
its own fit rather than harming it.

QB rush needs **0.1526** of team carries; C0's container holds 0.1085 and cannot
fit it, C1's holds **0.1889** and does, leaving 0.0363 against a historical
WR+TE of 0.0340.

### A separate defect that blocks the Part A freeze

`layers.targets_carries:200` seeds with `[seed, hash(cls) % 9973]`. Python
randomises str hashing per process and `PYTHONHASHSEED` is unset. Three
processes, identical inputs and seed, gave three different share matrices and
other masses **0.005328 / 0.006891 / 0.004916**.

**The allocation layer is not reproducible across processes.** Current outputs
cannot be frozen as numbers, and any cross-process "same seed" comparison of
this layer compares RNG streams. Every arm here ran in one process for that
reason. Arguably more urgent than the units fix, because it makes before/after
evidence about the units fix unverifiable by anyone else.

### My own error, corrected before reporting

The first run split captures by modelled-row count and mislabelled 7 of 8 — a
game with few receivers can have fewer target rows than another has carry rows.
The class is now captured from `gen_weights`, which receives it, and paired by
call order.

### Recommended, not applied

`S = (W*A) * (1 - w_other) / Σ(W*A);  other = w_other`. Not applied: the
experiment captured production's inputs without modifying it, so the repair is
not mechanically unavoidable, and `p4c_lib` is frozen. Owner decision, together
with the RNG defect and the unowned kneels (0.7746/team-game).

---

## 2026-09-09 — OWN-7: reproducibility, then the units repair

**`OWN7_REPRODUCIBLE_P4C_UNITS_REPAIRED`**

### Part A — and the audit found a SECOND instance

Not just the allocator: **`team_volume_v1.forecast` seeded with
`hash(metric)` too**, so D1 — every team dropback, target, carry and snap —
was process-dependent. The whole predictive path, not one layer.

Repair: `nfl/production/seeds.py`, an explicit frozen integer per named stream,
no hashing of any kind, unknown keys refused rather than defaulted. Five
independent processes (PYTHONHASHSEED unset/0/1/987654, forward and reversed
order) produce **identical output hashes** while `pyhash` varies across all
five. `TARGETS_CARRIES_RNG_REPRODUCIBLE`.

The regression guard walks the **AST**; its first version was a substring test
and failed on the comment explaining why the call was removed.

Reported not fixed: `hash()` in the seeds of `rbb1_lib.py` and `run_j1.py` —
those studies' draws are not reproducible. Neither is in the predictive path.

### Part B/C — the contract applied, no refit

| | carries modelled | carries other | targets other |
|---|---|---|---|
| before both | 0.891489 | 0.108511 | 0.005288 |
| contract only, old RNG | 0.811104 | 0.188896 | 0.012252 |
| **after both** | **0.801160** | **0.198840** | **0.016308** |
| comparator | 0.8082 | 0.1918 | 0.0113 |

Production's output now reproduces the authorized formula to six decimals.
C3 **0/2,400** on all three identities; receiving accounting **PASS 6/6**;
team dropback closure max abs diff **0.0**; 0 of 924 forecastable draws changed.
Suite **42 modules, 451 functions, 2,638 checks, 0 failing**.

### The rushing gate still fails, for a NEW reason

The container is no longer too small — mean margin **+1.7945 carries** in its
favour — but **812 of 2,400 draws (33.83%)** still exceed it, worst **44.24**.
QB carries come from the dropback multinomial and the RB block from the carry
simplex, and **neither draw knows about the other**. Duplicate ownership one
level below the units defect, same shape as the passing side before C3. Fixing
it means carving QB carries from the team budget before the simplex allocates
the remainder — a rushing architecture change, outside OWN-7's authorization.

### Part D — `KNEEL_MASS_EXPLICIT_UNMODELED`

Named in `accounting.UNMODELLED_CARRY_COMPONENTS`: 0.7746 per team-game,
0.0288 of team carries, inside `other` and claimed by nobody, never
attributable to RB/WR/TE/scramble/designed, with the invariant future modelling
must satisfy. No estimator invented.

---

## 2026-09-09 — OWN-8: the rushing collision is a sign error

**`OWN8_RUSHING_ARCHITECTURE_IDENTIFIED_NOT_IMPLEMENTED`**

### The ownership order, proven — and "carve QB first" is NOT it

Two independent tests over 3,230 team-games agree on every component.

| component | CV per db | CV per carry | corr db | corr carry | owner |
|---|---|---|---|---|---|
| scramble | **0.932** | 0.960 | **+0.1824** | +0.1802 | **dropback** |
| designed QB | 1.642 | **1.435** | **−0.1174** | **+0.2921** | **carry** |
| kneel | 1.531 | **1.353** | −0.2402 | **+0.3349** | **carry** |
| RB/WR/TE | 0.604 | **0.141** | −0.4041 | **+0.8831** | **carry** |

Every carry lands in exactly one category in **3,230/3,230**, max residual 0.

**The mechanism is a sign error.** Team carries and dropbacks correlate
**−0.4046** — the budgets move in opposite directions. `qb2_lib` draws designed
QB rushes as `Binom(dropbacks, drush_per_dropback)`, while historically they
correlate **+0.2921 with carries and −0.1174 with dropbacks**. In a draw with
many dropbacks the QB gets *more* carries exactly when the carry budget is
*smaller*. That is why enlarging the container in OWN-7 (0.1085 → 0.1988) did
not stop the collisions. The OWN-4 finding again, on the rushing side.

Scrambles are the exception and stay dropback-owned — both tests essentially
tied, and a scramble is a dropback that ran. **So: option (2) for scrambles,
option (1) for designed rushes. Neither alone.**

### Kneels do not block it

Carry-owned, 0.7746/team-game, 0.0288 of carries, no governed control. An
unmodelled *level* inside a *named* category still closes. What would block
ownership is an anonymous residual others also draw on.
`KNEEL_MASS_EXPLICIT_UNMODELED` stands; `OWN8_KNEEL_CONTROL_REQUIRED` is not
the verdict.

### Why A1 is not implemented

It needs a P4C refit and none is authorized: the RB simplex is fitted against a
denominator that INCLUDES scrambles/kneels/designed runs, so applying it to a
scramble-reduced budget is a semantic change, not a rescale; and A1 needs
designed QB rush and kneels as modelled categories, which `pos: ('RB',)` does
not have. OWN-6's no-refit finding was about units, and does not extend to
adding categories.

Pre-registered: `nfl/research/own8/predeclaration_own8.md`, sha256 `90f6ecc3…`.
A2 (common latent) reproduces the budget correlation but cannot guarantee
per-draw closure, so it is rejected as a closure mechanism.

**0 production files changed.** Suite 42 modules, 451 functions, 2,638 checks,
0 failing.

---

## 2026-09-09 — OWN-9: A1 single-owner rushing is valid

**`OWN9_A1_SINGLE_OWNER_RUSHING_VALID`.** Research only, 0 production files
changed, not promoted.

### Part 0 — an engineering guard, not a convention

`nfl/tools/nflwrite.py` resolves the repo root from its OWN `__file__`, never
from the shell, requires the NFL markers, refuses a root carrying another
project's markers, resolves symlinks and `..` before the containment test, and
refuses a zero-byte payload. Verified from `/tmp`: every escape refused, a
legitimate write accepted. 21 checks. Every OWN-9 artifact went through it.

### A1 closes; A0 does not

652,000 draws per arm: **A0 violates closure in 535,354 (82.1%), A1 in 0.**
Zero negatives either arm; designed QB rush exceeds its budget 15 times under
A0 and 0 under A1. The frozen categories close in the DATA first: 3,230/3,230,
max residual 0.

### A1 wins CRPS on every category

designed QB rush **1.3790 → 1.0083 (−26.9%)**, RB **1.7227 → 1.3970 (−18.9%)**,
and small gains on fringe, WR, TE, kneel.

### The sign defect is repaired — the test that mattered

| designed QB rush vs | observed | A0 | A1 |
|---|---|---|---|
| team carries | **+0.3140** | **−0.4115** | **+0.5070** |
| dropbacks | **−0.1521** | **+0.9724** | **−0.2651** |

A0 backwards on both; A1 correct on both. **Caveat: A1 overshoots the
magnitude** (+0.507 vs +0.314) because it draws designed rushes as a share of
the budget, so the coupling is mechanical. Right direction, too confident about
strength — A2's territory.

### Closure did not cost dispersion, it improved it

designed QB rush: observed sd **2.7751**, A0 **1.3574** (half the truth, zero
mass 0.179 against 0.367), A1 **2.6516** with p95 exact and zero mass 0.398.

**A methodological correction made before reporting:** the first diagnostic
summarised per-team-game predictive MEANS and compared them to realised
outcomes — a distribution of means has almost no zero mass and far less spread,
which would have flattered both arms. Draws are now pooled.

### Part D — kneels are representable

Not `A1_KNEEL_MODEL_UNDEFINED`. The P4C-style mechanism represents them as an
explicit category: mean 0.8170 against 0.7706, zero mass 0.5971 against 0.5509,
over-dispersed tail (sd 1.33 against 1.04). No new estimator class.

### Limits that belong with the verdict

Budgets are oracled identically for both arms, so this validates the ALLOCATION
architecture, not a whole-forecast gain. A1 over-couples. Development evidence
rejects, never promotes.

Suite 43 modules, 457 functions, 2,659 checks, 0 failing.

---

## OWN-10 — A2 rejected; the premise it was chartered on is withdrawn

**2026-09-09.** Verdict `OWN10_A2_LATENT_DOES_NOT_EARN_ITS_COMPLEXITY`. A1
retained. Nothing promoted. 0 production files changed. No 2026 outcome read.
Pre-registration `59ea7fa4363b202899e76f7668d2d3f8e517e2c572e4afd040079dbb14de5954`,
committed before A2 existed, re-checked by the runner.

### The chartered defect is not in A1 — it was in my reporting code

OWN-10 was authorised on "A1: ≈ +0.507" against an observed +0.314. That +0.507
was a per-team-game predictive **mean** correlated against a **realised** series.
Averaging 400 draws strips the idiosyncratic noise reality carries and leaves the
budget-aligned component, inflating the ratio. Computed identically on model and
reality — one draw per team-game — A1 gives **+0.3065 [+0.2768, +0.3388]**
against observed **+0.3140** (z = +0.40), and vs dropbacks −0.1603 against
−0.1521 (z = +0.42). Inside the band in all three folds. Budget slope 0.1033
against 0.1039.

**Sixth appearance of the point-for-distribution defect class, and the first to
reach a headline number in an accepted return.** `run_own9.py` argued the point
correctly for CRPS eleven lines above the defect and asserted the opposite three
lines below it.

### A2 built and scored anyway, so the withdrawal is measured not argued

A2(τ) = A1 + `u ~ N(0, τ)` on the designed-QB share. τ = 0 reproduces A1 draw
for draw (verified exactly, 0 differences over 200 team-games × 400 draws × 6
categories). Dependence gap |model − observed| pooled: **0.0075** at τ = 0,
rising monotonically to 0.0136 at τ = 0.04. Per fold the best τ is 0.0025, 0 and
0.04 — three answers, no consistent sign. Rules 1, 2 and 3 all fire.

**Against my own interest:** designed-QB CRPS is consistently better at τ = 0.01
in all four folds (1.00826 → 1.00598 pooled, −0.23%). It fails the
pre-registered conjunction, which needs a dependence improvement too, and rule 4
resolves equivalence to the simpler arm. Recorded rather than dropped.

Gates, every arm, 652,000 draws: 0 closure violations, 0 negative, 0 overruns,
0 degenerate.

### What the corrected metric does expose: kneels, not designed QB rush

| statistic | observed | A1 per draw | 90% band | z |
|---|---|---|---|---|
| kneel vs team carries | **+0.3009** | +0.1688 | [+0.1302, +0.2040] | **+6.10** |
| kneel vs dropbacks | **−0.2430** | −0.0653 | [−0.1025, −0.0277] | **−7.49** |
| kneel vs RB | **+0.1733** | −0.0116 | [−0.0553, +0.0326] | outside |

Same sign in all three folds. A kneel is a game-state play; A1 draws it as an
exchangeable share, which has no channel for that.

### One mechanism behind the small-category over-dispersion

The additive share residual is resampled from a **league-wide pool per
category**, so a team with a near-zero centre gets residuals sized for teams
with a large share. It goes negative and the floor catches it **808,823 times
out of 3,912,000 share draws (20.68%)** — RB 0.07%, designed QB 19.45%, WR
23.36%, TE 24.73%, kneel 27.05%, fringe 29.40%. SD ratios track it exactly:
RB 1.01, WR 1.19, fringe 1.19, kneel 1.28, TE 1.75. The floor moves a
probability, never a carry, so no gate breaks; but a residual family needing a
floor one draw in five is mis-specified for every category except the large one.
Hypothesis with an obvious test, not an established cause.

### Record repaired

`run_own9.py` computes co-movement per draw; the mean-based figure is retained
under `..._MEAN_BASED_NOT_COMPARABLE`. `own9_results.json` re-recorded. A0's
OWN-9 headline −0.4115 / +0.9724 was the same artifact and is withdrawn with
A1's +0.5070; per draw A0 is **−0.1235** and **+0.2918** — still wrong-signed on
both budgets, so the OWN-9 verdict stands on weaker evidence than reported.

`nfl/tests/test_own10_dependence_metric.py` makes the metric contract
load-bearing: AST guard (a substring guard would match the comment explaining
the defect — that already happened once here), schema guard, a bypass test that
seeds the defect and requires rejection, τ = 0 ≡ A1, closure at every τ.

### Not done, and offered rather than started

Kneel game-state dependence and a multiplicative or logit-scale residual family
both touch P4C's estimator family, which is production. Pre-registration comes
before fitting.

**Suite 44 modules, 467 functions, 2,797 checks, 0 failing.** The OWN-10 module
initially contributed 0 counted checks: it used bare asserts, so `run_suite.py`
classified it NO TALLY and judged it on exceptions alone — weaker than this
project's standard, and the runner's own docstring says a module that measured
nothing has not passed. Converted to the `check()` convention, +138 checks. An
audit of all 44 modules found no other module in that state.

---

## V1 CONVERGENCE — 2026-09-09

**Verdict `V1_REHEARSAL_READY_WITH_NAMED_BLOCKERS`.** Full packet in
`NFL_V1_CONVERGENCE_RETURN.md`; status list in `NFL_V1_RESEARCH_LEDGER.md`.
Suite 47 modules, 489 functions, **2,863 checks, 0 failing, 0 raised**.
G0A 11/12. NFL-1 NOT AUTHORIZED. PATH_C_STATE untouched. Nothing promoted.

### The slate runs now, and this morning it did not

All 16 games refused with `STAGE_RAISED` — `FileNotFoundError` on
`panel_enriched.pkl`, which is deliberately uncommitted. `football_engine`
gated on `derived.artifacts()`; the production entrypoint never did. **16 of 16
now SEAL** with 84 QB forecasts. Found by running the thing, not by reading it.

### Six false greens repaired, each verified by execution

| defect | was | now |
|---|---|---|
| implemented layers called "unimplemented", counted PASS | 5 layers × 16 games | per-game `INJURY_REPORT_NOT_YET_FILED` ×15 / `INJURY_REPORT_INCOMPLETE` ×1, still sealing the valid QB forecast |
| a fixture could seal distributions no model made; `eligibility_verdict` hardcoded `'PASS'` | demonstrated live | `EMPTY_FORECAST_ARTIFACT`; artifact stamps `distributions_source` + `TEST_ONLY`; verdict computed |
| `code_commit` named code that did not run | clean hash, 125 modified lines | `…+dirty[16]`, inside execution identity |
| `invariants.check`/`le_check` PASS over zero groups | any zero-row read → green | `INVARIANT_NOT_MEASURED_*` |
| `reconcile_team` on a key-shape mismatch | checked nothing, PASS, `checked=True` | `QB_TEAM_RUSH_BUDGET_KEY_MISMATCH`; both shapes accepted |
| `test_nonqb_r3` RAISED on drifted schema | module tally still said 0 failing | schema checked by name; `check()` returns its result |

### Every game on the slate shared one RNG stream

`appearance` was keyed by week only; `targets_carries` by **neither game nor
week**. Two disjoint games with no player in common correlated at **r = +0.545**
and the target-mass vectors were bit-identical. That is the mirror of this
project's usual defect: a dependence of exactly 1.0 invented between independent
games, making a sixteen-game slate not sixteen games.

`seeds.py` gains a sha256 per-game component — deterministic across processes,
unlike the `hash()` this project removed in OWN-7, and hashed here only because
game ids are an open set where the frozen table `stream_id` uses is unavailable.
Measured after: **0.0634**, sampling noise at m=200; identical `game_id` still
reproduces bit-for-bit.

### The QB composition emits impossible football, and now says so

`conserve_allocated_mass` justifies itself with *"any non-zero draw of that row
carries the same rates"*. **That is false for a small draw.** A draw of one
dropback carries a Bernoulli realisation, not a rate, and `target/drawn`
multiplies the realisation.

Measured on the real slate: **4.50%** of raw dropback draws are exactly 1, the
factor reaches **59.85**, **55.8%** of live cells are stretched, and a passer
whose raw passing-TD draws max at 5 emerges with a composed maximum of
**49.14** — the NFL single-game record is 7.

The engine reported `PASS[QB_COMPOSITION_MASS_CONSERVED]`. Mass conservation was
never the property in doubt. The verdict is now
`FAIL[QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED]` on the parameter-free condition
`drawn < target`, with the mass statement kept beside it rather than standing in
for it. **The repair is R2, pre-registered and not authorised — not taken.**

### Four blockers left standing deliberately, with reasons

C3 (one passing event generated twice, identity fails 12,800/12,800 draws) and
A3-per-game (two teams drawn independently: model +0.015 against a realised
−0.534; **2.0% of drawn games fall outside the entire 2020–25 range** of total
plays) are **built candidates whose promotion is an owner decision**. RB1↔RB2 is
**wrong-signed** (+0.081 against −0.329) and its next step is an ablation, not a
change. Production emits four quantiles and **no draws**, so no proper score can
be computed from V1 output at all.

### Method note

Four parallel audits ran read-only; the lead verified every claim that changed
the plan before acting on one. Two agent findings were about code written
earlier in the same session, including a `Cause.CODE` that does not exist and
would have destroyed the named refusal it was meant to produce. One repair
(wiring the non-QB layers in) initially made all 16 games refuse and discard a
valid QB forecast; that was caught by re-running the slate, not by review.

---

## V1 FREEZE ATTEMPT — 2026-09-09

**Verdict `V1_REHEARSAL_READY_WITH_NAMED_BLOCKERS`.** Packet in
`NFL_V1_FREEZE_RETURN.md`. Suite 50 modules, 527 functions, **3,102 checks,
0 failing, 0 raised**. Entrypoint 16/16 SEALED. G0A 11/12. NFL-1 NOT
AUTHORIZED. PATH_C_STATE untouched. Nothing promoted.

### Six of seven authorized repairs landed

| blocker | before | after |
|---|---|---|
| B8 composition | passing TD max **49.14**, factor **59.85** | **9.00**, no ratio formed — R2 |
| B9 duplicate pass event | identity failed **12,800/12,800** draws | **32/32 PASS**, residual **5.9e-15**, corr **1.0000** — C3 |
| B10 independent teams | SD(total plays) 12.271; **1.520%** impossible | **9.269** (hist 9.265); **0.188%** — A3G |
| B12 share leak | 2.29% / 6.91% | **0.0%**, 16/16 consumed — C0 |
| B13 no draws | four quantiles | **216,800 draw cells**, lossless, shared index, sha256 replay id |
| B14 ungated FAILs | any FAIL could seal | **9 HARD** gate, **3 DIAGNOSTIC** never do |

### B11 was not a defect — its premise was an estimand mismatch

The quoted **+0.081** is a *within*-team-game correlation; the realised
**−0.329** is a *between*-team-game one. Like-for-like on the historical frame
with prior-week ranks the incumbent gives **−0.3559** [−0.389, −0.322],
P(r>0)=0.000, against realised **−0.3716**. The authorized minimal ablation was
run and **rejected**: at flat week-1 priors sharing one `add_pool` index makes
every back identical and flips the sign to **+0.1112**.

### R2 alone refuses, and that is the right answer

`APPORTION_SHARE_DOES_NOT_COVER_BUDGET` fires when the allocation names a
quarterback QB V1 never forecast — OWN-1's leak surfacing as a hard closure
failure instead of a silent 2.3–6.9% loss. C0 is the declared remedy; no
survivor is renormalised.

### Two invariants replaced by STRICTER ones, both declared before measurement

R2: `sum == rint(budget)` exactly, replacing `sum <= float budget`. C3:
`sum_i T_i + other == targeted` in exact integers, replacing a
relative-tolerance share form the architecture no longer uses. Neither is a
loosened guard; both refuse by name if they ever fail.

### The one blocker left, and why I stopped

`qb_rush_contained_in_other` FAILs **190 of 2,800** cells, worst **21.6**. That
is wrong causal ownership. The fix is **A1** — pre-registered in OWN-8,
validated in OWN-9, and **not authorized to implement**. I did not implement it
and did not route around it. The V1 candidate mode is also not yet reachable
from `run_forecast`; that is pure engineering and is the next step.

### Reported against my own interest

The A3G stream's **pre-registered verdict was that no candidate cleared**. Two
of its clauses reject the incumbent against itself — proved, not asserted — so
I integrated on the corrected clauses and am recording that the pre-registered
verdict failed on its own terms.

Three defects I introduced and caught by **re-running, not by review**: R2
apportioned against an uncoupled volume while games drew a coupled one
(383/400 cells); C3's integer other-pool count passed where a share was wanted
(moved the failure rather than removing it); my own composition test anchored a
`find` that R2's new branch shadowed.

---

## 2026-09-10 — Game 1 shadow evaluation, NE @ SEA (exploratory)

**Decision:** run the frozen `V1_CANDIDATE` against a strictly pre-kickoff
information set for `2026_01_NE_SEA`, seal the forecast to git before opening
the outcome, then score. Owner-directed, parallel to the SF@LA G0A wait.

**Order established, not asserted.** Outcome file downloaded and hashed
(`ca02541038a1519d28a862157b031b6bc98f1ebb0b5d21341ac40cfcc22a582b`) with only
an identity-level row count read; forecast sealed and committed at `bba6f0b`;
outcome opened after. `score.py` refuses unless every sealed file still hashes
to its recorded value.

**Information set:** latest content observed strictly before the
2026-09-10T00:20:00Z kickoff, selected by observation time. Newest is
2026-09-08T17:06:03Z — **T−31.2h**, not T−90m, because no capture exists
anywhere on 2026-09-09. No official inactives for this game.

**Result:** SEALED. Team-level QB aggregate 21/22 quantities inside 90%;
Seattle's whole QB room inside the 50% interval. Three `MODEL_MISS` rows over
two distinct events — New England's zero red-zone carries, and Maye's three
interceptions at a priced 2.4%. The Darnold/Lock individual errors are an
in-game injury recorded in the play-by-play text, classified by a tested
predicate rather than by judgement.

**Not forecast at all:** every player-level receiving and rushing quantity, and
C3. `readiness.team_report_history` has no vintage cut, so it took each team's
injury block from a post-kickoff capture and the chronology guard correctly
refused — while a legitimate pre-kickoff report for exactly these two teams sat
unused. 95 of 193 ledger rows are `NO_FORECAST_MISSING_PREGAME_INPUT`.

**Nothing changed in `nfl/production`.** V1 remains frozen, G0A remains 11/12,
NFL-1 remains NOT AUTHORIZED, `PATH_C_STATE` untouched. No threshold was
altered after the outcome was seen and nothing was promoted. All observations
classified `POST_V1_REFINEMENT`; they are listed in
`NFL_SHADOW_G1_NE_SEA_RETURN.md` §7 and none was acted on.

**Reversibility:** the whole evaluation lives under `nfl/research/shadow/` and
`NFL_SHADOW_G1_NE_SEA_RETURN.md`. Deleting that directory removes it entirely.

**Suite state at the end of this task: FAIL** — 55 modules, 591 test functions,
3322 checks, 3 failing, 2 raised. Both failing modules reproduce identically at
`34b59a2` in a clean worktree, before any shadow work; neither is caused by this
task and neither is repaired here, because the task forbids modifying V1. They
are (a) `targets_carries` raising `KeyError: 'add_pool'` because
`run_forecast.py:433` passes empty placeholder parameters to a chain that has
never executed, now reached for the first time as the injury feed became
complete — in substance a V1 blocker, owner call; and (b)
`test_football_engine_r4` hardcoding a transient ARI readiness state. Detail in
`NFL_SHADOW_G1_NE_SEA_RETURN.md`, appendix.

---

## 2026-09-10 — V1 product-path engineering closure (narrow, authorised)

**Decision:** owner reopened V1 for two named execution defects only, explicitly
not for model research. Both repaired; a third was found by the repair and
repaired with them.

1. **Non-QB production chain placeholders.** `run_forecast` called
   `targets_carries` / `receiving_conversion` / `td_layer` with `[]`,
   `([], [])` and `{}`. Repaired by delegating the chain to
   `football_engine.run_game`, which already owns the composition — filling the
   placeholders in the entrypoint would have given every input two owners. The
   QB half is memoised so it runs before C3 and A1, which depend on it; the
   declared stage order reported `qb_layer` last, which is why C3 could never be
   reached. A1 is now the sole rushing-opportunity partition owner via
   `rushing_budget`.
2. **Injury/readiness vintage cut.** `retrieved_at <= written_at < kickoff`
   applied at selection, part of the cache key, with a bare call bounded by the
   team's own kickoff instead of reading everything on disk.
3. **Team volume had two owners** (found during the repair): the
   `team_environment` stage drew uncoupled while the candidate path and engine
   drew coupled. Run A's artifact provably stored draws its own QB layer had not
   used. One memoised owner now.

**Closure test.** SF@LA, a real chronology-valid pre-kickoff game: the full
chain executes in both configurations, all six candidate components applied,
C3 closes with receiver targets ≤ QB attempts in every draw. Run A preserved
immutable; Run B from the identical cutoff has **bit-identical QB draws**, so
R2/C0/A3G/SC1 are unchanged. NE@SEA's chain still does not run — correctly, and
now for the true reason: no pre-kickoff capture carries a filled
`report_status`, because nothing was captured on 2026-09-09. That is the G0A
item-1 gap showing up as a product consequence.

**Suite:** 56 modules, 600 test functions, 3,362 checks, 0 failing, 0 raised.

**Verdict:** `V1_PRODUCT_PATH_ENGINEERING_READY`.

**Unchanged:** every estimator, every prior, every threshold. `PATH_C_STATE`,
G0A rules and capture infrastructure untouched. Nothing promoted; NFL-1 remains
NOT AUTHORIZED and G0A remains 11/12. No 2026 outcome entered any fit.

**Recorded, not acted on:** the baseline allocation's incoherence, measurable
for the first time now the chain runs — 1,453 of 9,000 cells with receptions
above targets (max excess exactly 0.500, the `rint` signature) and 14 of 200
draws dealing more targets than there were throws. C3 reduces both to zero.
Repairing the baseline is model work and was not authorised.

**Detail:** `NFL_V1_PRODUCT_PATH_CLOSURE.md`,
`nfl/research/shadow/V1_CLOSURE_EVIDENCE.json`.

---

## 2026-09-10 — game-day product layer built

**Decision:** productization and evaluation only, on top of the frozen V1
engine. `nfl/product/` is read-only over it: no estimator, no prior, no
parameter, no projection computed anywhere in the package.

**Built:** pregame player board (53 players, SF@LA) with mean/median/P10-P90
per metric, opportunity shares, data freshness, per-team status confidence and
per-layer modelled/provisional/unavailable state; threshold probabilities from
stored draws on ladders fixed in advance; a five-dimension model-confidence
ranking; and a permanent postgame evaluator with a cumulative ledger.

**Anti-fabrication is the spine.** RB/WR/TE rushing yards do not exist in V1
and are shown as UNAVAILABLE with the open-decision code, never estimated;
`carries x yards_per_carry` is the implementation `layers.py` prohibits and is
the number a product layer would otherwise print. Tests assert every rendered
column and every threshold ladder names a declared V1 output, and grep the
whole package for eleven market terms.

**Two defects found in my own product code, both by its own tests.** The first
confidence board ranked four backup quarterbacks and two fifth receivers above
both starters, because a distribution that is zero in three quarters of its
draws has a zero IQR, which scored as perfect narrowness. Second,
`verify_seal` resolved repo-relative paths first, so scoring a COPY verified
the ORIGINAL — a guard reporting success while checking the wrong file. Both
fixed and pinned.

**NE@SEA scored into the permanent ledger:** 33 QB rows, mean CRPS 13.94,
coverage 33.3/60.6/81.8/81.8%, 6 TAIL_MISS. **Zero refinement candidates** —
six metrics sit on the watchlist at one game each against a bar of four
distinct games, declared before any data arrived. Nothing about V1 changed.

**SF@LA sealed** at `nfl/research/shadow/sf_la_pregame/`, run
`e3e2bc8a1f043abf`, written 2026-09-10T16:07:43Z, 8.45h before kickoff, all six
candidate components applied, labelled SHADOW / NOT AUTHORIZED. If G0A clears
before kickoff this artifact stays SHADOW and a new forecast is written under
the open gate; authorization is a property of when a forecast was written, not
a label applied afterwards.

**Suite:** 57 modules, 617 test functions, 3,416 checks, 0 failing, 0 raised.

**Untouched:** all 18 frozen production files hash identical to
`FREEZE_V1_PRODUCT_PATH.json`; `PATH_C_STATE`, G0A rules and capture
infrastructure unchanged. NFL-1 remains NOT AUTHORIZED, G0A 11/12.

**Detail:** `NFL_PRODUCT_LAYER.md`.

---

## 2026-09-10 — pregame board refresh automated

**Decision:** product orchestration only. A scheduled pass consumes the latest
chronology-valid stored vintages, runs the frozen `V1_CANDIDATE`, renders the
accepted board format, and seals it immutably.

**Cadence, and an honest limit.** `.github/workflows/nfl-product-board.yml`
runs `7,27,47 * * * *` but is **inert until the branch merges to main** —
GitHub fires scheduled workflows from the default branch only, and main does
not carry the product layer. Routine `trig_01H9EQHMbCodyy8sFUyz4ukL` covers
tonight, hourly at `:41`. Stated rather than left to be discovered.

**Storage:** `nfl/product/boards/<game_id>/<written_at>__<run_id>/`, never
overwritten (`BoardExists` is a named refusal), with an append-only
`INDEX.jsonl` and a `LATEST.json` pointer that a test proves is rebuildable
from the index and therefore holds nothing unique.

**Refresh is decided by input fingerprint, never by the clock** — content hash
AND observation time per source — so a scheduler firing more often cannot
restamp stale inputs as fresh. Four outcomes; three write nothing; a pass that
writes nothing exits 0.

**Five proofs, all in `test_product_orchestration.py`:** identical inputs
reproduce identical draws (and did, in production: 22/22 arrays bit-identical
to the manually sealed board, same digest); only genuinely newer vintages
change a board; post-kickoff data cannot enter (checked twice, including
between plan and execution); SHADOW cannot masquerade as AUTHORIZED (both gate
branches driven); product failure cannot touch capture or G0A (every capture
and governance file hashed before and after a failing pass).

**Defect found and fixed:** `run()` caught `Exception`, but `SystemExit` is a
`BaseException`, so one bad game id killed the whole scheduled pass and every
later game went silently unchecked.

**Suite:** 58 modules, 631 test functions, 3,466 checks, 0 failing, 0 raised.

**Untouched:** all 18 frozen production hashes identical; `PATH_C_STATE`, G0A
rules and the capture workflows unchanged. NFL-1 NOT AUTHORIZED, G0A 11/12.

**Detail:** `NFL_BOARD_AUTOMATION.md`.

---

## 2026-09-10 — MKT1 market-disagreement diagnostic (no tuning)

**Decision:** compare the sealed SF@LA forecast against an independently
produced external market snapshot, as a diagnostic only. No price used as a
label, target or fit input. V1 unchanged; all 18 frozen production hashes
identical.

**Placed in `nfl/research/mkt1/`, never `nfl/product/`** — the product layer has
a tested boundary that no sportsbook number may cross.

**Result:** 19 of 23 markets comparable. Median disagreement **−25.3 pp**, model
below market in **18 of 19**. Ordered by metric: carries −44.9 pp (z +2.11),
receptions −33.0, receiving yards −30.1, QB attempts −22.1, passing yards −16.8,
passing TD −15.2, **interceptions −1.9 and split 1/1**. Opportunity markets
8 of 8 one-directional; conversion markets 10 of 11 and inherited.

**One mechanism explains most of it, and it is not team volume.** Team totals
are ordinary (SF 36.0 dropbacks / 36.2 targets / 26.6 carries). The internal
control is decisive: in the same run, the QB allocation mechanism gives the
starters 88–91% of their team's attempts while the P4C simplex gives the WR1
15.9% of targets and the lead back 38% of carries. Same data, same game,
different mechanism.

**Earliest causal layer:** `p4c_params.class_point_forecast` feeding the P4C
simplex. The weight vector does not sum to one over the players who will play —
23 LA pass-catchers carry weights summing to 2.04 — so normalisation roughly
halves every real share. Contributing upstream: `run_game` selects the pool on
position alone, with the captured depth-chart rank unused; and
`participation` weights by pass-snap participation, which the layer itself
declares is "an upper bound on routes run".

**Not repaired. `POST_V1_REFINEMENT`.** Not a new finding either — the ledger
already carries `RB1↔RB2 at flat week-1 priors` and the 20.68% share-residual
floor. The market sized the defect; it did not discover it.

**Pre-registered before kickoff** in `nfl/research/mkt1/predeclaration_mkt1.md`
(sha256 `3d298170a2a7da55…`) with falsifiable thresholds from the model's own
intervals, plus the declared uncontrolled factor that this game is at the
Melbourne Cricket Ground and V1 has no venue or travel feature.

**Bar unchanged:** four distinct games before any refinement candidate. One
game raises a hypothesis.

**Detail:** `NFL_MKT1_MARKET_DIAGNOSTIC.md`.

---

## 2026-09-10 — R5 root-cause audit and candidate repair

**Diagnosis.** The dominant defect is the ALLOCATION POOL, not team volume.
`class_point_forecast` returns a share conditional on appearing; the P4C
simplex consumes it as an unconditional weight over the roster it is handed
and normalises by the sum. Historical panel: 14.6 WR/TE/RB per team-game,
sum(C)=1.24. Prospective SF@LA: 22.5 players, sum(C)=2.14 — halving every
starter share. Of 45 SF/LA WR/TE/RB roster rows, 29 ACT, 10 DEV, 3 RES, 3 CUT;
released players were competing for targets. Enabled by the vintage reduction
dropping `status` and `depth_chart_position`, which the raw download carries.

Ranked: (1) pool contamination; (2) appearance anti-correlated with role
(Adams 0.538, Pearsall 0.395, unlisted players 0.998); (3) participation prior
too flat, 1.4:1 top-to-fringe; (4) QB dropback ownership closes at game level
but not per team (SF 0.942, LA 1.060); (5) team volume, backtested unbiased to
1-2% on 3,230 team-games and NOT a material cause.

**Evidence is realised football, not the market.** Historical rank-1 target
share 29.3% (V1 15.9%), top-3 65.5% (V1 30.8%), distinct targeted 8.0
(V1 11.9); rank-1 carry share 70.3% (V1 36.4%).

**Repair: `V1_CANDIDATE_R5`**, a new configuration identity differing from
`V1_CANDIDATE` by exactly one flag — restrict the non-QB pool to roster status
ACT. No constant introduced. Unknown status is KEPT. Missing status refuses by
name rather than running unfiltered. QB pool untouched.

**Result:** every concentration metric moves toward realised history; pool size
14/15 vs historical 14.6 and players-targeted 7.9/8.4 vs 8.0 land essentially
on it. **Team totals bit-identical (delta 0.000)** — the split changed, not the
pie. Closes roughly half the gap; causes 2-4 remain unbundled.

**Not claimed:** a per-game held-out CRPS/PIT comparison. The historical corpus
holds only players who appeared, so R5's counterfactual cannot be constructed
without historical roster vintages carrying `status` — filed as OUT-002.

**SF@LA outcome was not used:** the game is unplayed, no outcome file exists,
and the candidate is sealed with a pre-kickoff `written_at`.

**Suite:** 59 modules, 639 test functions, 3,487 checks, 0 failing, 0 raised.

**Integration:** product path merged to main at `7118a33` with a normal
non-force merge; 10 capture-bot commits and 7 product commits, disjoint paths,
all verified as ancestors. `nfl-product-board.yml` is now on default main.

**Detail:** `NFL_R5_ROOT_CAUSE_AUDIT.md`, `docs/AGENT_OUTBOX.md`.

---

## 2026-09-10 — R6 role/appearance refinement (evidence, not promotion)

**Appearance inversion, root cause.** The frozen P3 logistic reads absence
history and that history carries across the offseason. Adams shows
`f_consec_missed=3` — he missed the last three games of 2025 — and prices at
0.532 eight months later with no injury entry; Pearsall 0.384. Cold-start
players (`f_n_prior=0`) present as having no absences, so unknown reads as
near-certain: 0.998. Absence of evidence read as evidence of availability.
Third finding: `A.depth()` returns an EMPTY dict, so `f_depth` is null on every
row and the appearance model has never received the depth feature it carries.
The cold-start training bucket (94.8–98.0%) is survivorship-filtered: a camp
receiver who never dresses never enters the panel.

**Flat prior, root cause.** `share_prior` is a pass-snap participation rate
(top-to-fringe 1.39:1) used to weight target allocation, where realised spread
is 2.5:1 in snaps and 3.7:1 in targets. `class_point_forecast` then falls back
to the positional mean for no-history players — a 3.7:1 spread collapsed to
1:1.

**Historical calibration by point-in-time depth tier (2020-2025).** Appearance
falls monotonically with depth: WR1 88.6 / WR2 81.9 / WR3 80.1 / WR4+ 61.1;
RB1 84.6 / RB4+ 50.5; TE1 87.3 / TE4+ 49.2. The model runs the other way.
Target share by tier: WR1 22.7 / WR2 18.3 / WR3 13.3 / WR4+ 6.1. Carry share:
RB1 50.5 / RB2 26.4 / RB3 14.0.

**R6 = R5 + one flag.** The class weight becomes a player's own history shrunk
toward his point-in-time depth tier. Tier from trailing snap-share rank, the
captured depth chart as named fallback, lowest tier recorded where neither
exists. Shrinkage n/(n+k) with k ESTIMATED from within/between player variance
(WR 0.87, TE 0.78, RB-targets 1.54, RB-carries 0.74). A long history is never
overwritten; no player or team is named; both asserted by tests.

**Result.** Ten of twelve concentration metrics improve on R5. Largest: SF lead
back carry share 52.6% → 67.6% against a realised 70.3%. Two moved the wrong
way and are reported: SF players-targeted 7.9 → 7.4 overshoots 8.0, and SF
carries top-3 95.9% → 94.7% against 99.8%. **Team totals and the QB pool are
bit-identical across V1/R5/R6, delta 0.0000.**

**Not repaired:** the appearance inversion itself. R6 softens its consequence
(a cold-start player now prices at his tier mean) without touching the cause,
and that distinction is stated rather than allowed to pass as a fix.

**Not claimed:** per-game CRPS/PIT. Neither candidate's counterfactual exists
in a corpus that holds only players who appeared. Blocked on OUT-002.

**Suite:** 60 modules, 647 test functions, 3,511 checks, 0 failing, 0 raised.
Two of my own tests had hard-coded `V1_CANDIDATE_R6`/`R7` as the "unknown"
mode; R6 shipping made one real and it failed. Both now assert the property.

**Recommendation:** shadow-evaluate R5 and R6 beside V1 and let the four-game
bar decide. Nothing promoted.

**Detail:** `NFL_R6_ROLE_APPEARANCE_AUDIT.md`.

---

## 2026-09-11 — Track 1: game-state-conditioned offense. REJECT.

**The question.** Does a game state simulated from pregame information improve
team offensive volume and the quarterback distributions downstream of it.
Forward-chained 2022-2025, refit weekly on everything strictly earlier,
training from 2020. 10,727 scored team-games, 72 weekly refits, one change
between the arms, common random numbers across them.

**The response curve is real and was never in doubt.** Estimated on 13,093
team-quarters conditioned on the differential ENTERING the quarter -- a
within-quarter differential is partly caused by the plays being counted.
Fourth-quarter dropback rate is 1.305x the quarter mean entering two scores
down and 0.584x entering two scores up. Designed rush runs the other way,
0.537 to 1.640. Empirical-Bayes shrinkage does visible work: weight 0.04 where
there is no signal, 0.998 where there is.

**The result.** team_carries improves 0.611% of CRPS, game-clustered interval
[-0.0493, -0.0027], three seasons of four, r 0.181 -> 0.210, mechanism
coefficient 1.24 [0.84, 1.63]. team_dropbacks_part +0.821%, team_off_snaps
+0.526%, team_targets +1.518%, all significantly WORSE. Downstream QB-room
passing yards +2.42%. Predeclared rule gives REJECT, and it is REJECT.

**Why, and it is not the obvious reason.** A simulated pregame differential
conflates two channels. Within a game, trailing raises plays and pass rate.
Across games, a favourite is a BETTER TEAM and better teams sustain more
drives whatever the script. Correlation of a team's own expected margin with
what it actually did: carries +0.153, snaps +0.086, dropbacks -0.048, targets
-0.006. The multiplier points the trailing-team way in all four. For carries
the channels agree; for snaps they oppose and the quality channel is larger,
so the mechanism coefficient is -1.47 [-2.24, -0.70] -- significantly
wrong-signed out of sample from a curve that is correct in game.

**A hypothesis withdrawn.** I expected double counting -- the baseline already
encoding script. corr(baseline point, multiplier) is 0.14, 0.02, -0.10, 0.07.
It does not. That explanation is wrong and is withdrawn rather than kept
beside the one the data support.

**Mean versus width, separated.** A third diagnostic arm using the expected
multiplier shows team_dropbacks_part's mean shift alone is +0.315% with CI
[-0.015, +0.045], not distinguishable from zero; the per-draw arm's +0.821% is
added predictive width, and coverage says so (50% intervals cover 56.4%).

**Kept regardless.** 55.7% of team-games have volume error and efficiency
error of opposite sign, so a majority of good final passing-yardage numbers
are produced by cancellation. Now measured on every propagation row.

**Boundary, not averaged away.** The rushing-volume channel works. Nothing
promoted, R8 untouched, no market quantity an input at any layer, no threshold
moved.

**Suite:** 74 modules, 812 test functions, 4,410 checks, 0 failing, 0 raised.

**Detail:** `nfl/research/track1/TRACK1_SPEC.md`, `TRACK1_DECISION.md`,
`TRACK1_FORWARD_CHAIN_RESULTS.json`, `TRACK1_DIAGNOSTICS.csv`.

---

## 2026-09-11 — Q6: appearance probability and conditional role. WEAK_SUPPORT.

**The question.** Can pregame information improve player appearance
probability and conditional role allocation without leaking post-kickoff or
post-hoc roster status. Forward-chained 2022-2025 on R8's union frame,
34,621 player-games across 2,174 team-games, RB/WR/TE, 89 declined by name
into the unsupported cell. `weekly_rosters.status` never read.

**Two hypotheses died in the audit before anything was built.** The engine
does NOT collapse appearance into an unconditional share --
`layers.appearance` draws a Bernoulli per player per simulation draw and
`layers.participation` multiplies that 0/1 by the share. And the share is
already conditional on appearing: `participation_prior.share_prior` is an
EWMA of prior APPEARED shares. The directive's first requirement was already
satisfied structurally. R8 also already carries the game-status designation,
already restricted to rows timestamped before kickoff.

**What worked.** R8 carries the designation and the depth rank as separate
main effects, so it cannot say that a questionable starter and a questionable
fifth receiver are different events. Adding that interaction plus the
practice-status ordinal gives Brier -0.632%, team-game-clustered CI
[-0.000771, -0.000391], improving 8 of 9 position-by-role-class cells, five
significantly, none significantly worse. Downstream it is worth -0.256% target
CRPS and -0.553% carry CRPS, both significant, and the whole downstream gain
comes from the appearance layer.

**What did not.** Role-class Platt recalibration gives the best calibration of
any arm (ECE 0.0158 against R8's 0.0207) and a worse log loss, all of it in
2022 where the nested chain had one season to fit on. The boundary is training
depth, not the mechanism.

**What failed.** The vacancy correction is significantly WORSE on carry role
CRPS (+0.251%). The misallocation it aimed at is real -- on team-weeks whose
starter was absent, proportional renormalisation over-feeds the surviving
starter by 19% and under-feeds replacements by 7-12% -- but the correction was
estimated on share-among-present and applied to counts under simulated
appearance, and moves three to six times too little. Two estimator faults were
found and fixed first: a denominator that normalised within position against a
team-wide realised share, and a mean-of-ratios that let near-zero denominators
produce carry ratios of 4 to 8.

**Missing data.** On the 4,364 player-games that had a filed report, blanking
it more than doubles Brier. The model's own missing-block fallback is the
LESS honest answer: ECE 0.170 against the flat role-class rate's 0.081, and a
worse log loss. HARD_DEFER refuses 4,364 players across 1,496 team-weeks.
Recommendation for a later decision, not taken here: emit the role-class rate
under LOW_CONFIDENCE_ROLE_CLASS_ONLY when the report is unfiled, never without
the label.

**Headline arm fixed before the run.** Q6_CALIBRATED gives WEAK_SUPPORT;
Q6_FEATURES reaches SUPPORT under the same rule. Both verdicts are published;
adopting the better one afterwards would be selection on the outcome.

**Composition reconciles exactly** -- maximum team-total error 0.0 over every
draw, both metrics. Zero-inflation error is -2.68 points on targets and -1.24
on carries.

**Nothing promoted. R8 untouched.**

**Suite:** 75 modules, 826 test functions, 4,492 checks, 0 failing, 0 raised.

**Detail:** `nfl/research/q6/Q6_SPEC.md`, `Q6_DECISION.md`,
`Q6_FORWARD_CHAIN_RESULTS.json`.

---

## 2026-09-12 — Q7: efficiency calibration. REJECT the repairs; the diagnosis stands.

**The question.** Are the passing and receiving efficiency distributions
systematically biased or miscalibrated AFTER conditioning on opportunity.
Forward-chained 2022-2025, 93,961 scored rows over 2,653 QB-games and 17,323
receiver-games, intervals clustered on 1,087 games. Every arm received the
REALISED attempts, completions, targets and receptions, so no volume error
existed to disguise an efficiency error.

**Answer: yes, decisively, and the defect is in the MEAN not the width.**
`pyds|cmp` by attempt regime: bias +0.89 / -3.92 / +4.50 / **+19.80** and
calibration slope 1.029 / 0.990 / **0.755** / **0.728**. A twenty-yard
over-prediction at 40+ attempts with a slope a quarter below one.

**The width defect is real and was predicted from the mechanism before the
run.** A whole-game yards-per-completion is resampled and multiplied by the
completion count, so per-completion spread does not depend on completion
count. RMSE/SD by regime: 1.460 / 0.879 / 0.738 / 0.710 -- under-dispersed at
low volume (90% intervals cover 0.704), over-dispersed at high. The repair
collapses that 2.06-fold spread to 1.09 and lifts `<20` coverage to 0.945.

**And it buys nothing on a proper score.** Overall dCRPS -0.143% with the
interval spanning zero; `20-29` significantly WORSE. A wider interval is not
an improvement, the decision function refuses to treat it as one, and that is
what produced REJECT. All three arms REJECT.

**Shrinkage tested and left alone.** K=4.0 and half-life 2 are, in QB2's own
words, "inherited constants" with no grid search. Estimated forward-chained by
the repo's within/between-player estimator: 4.74 for the completion rate, 3.32
for yards per completion -- the inherited value sits between them, and
Q7_SHRINK is significantly worse on `pyds|cmp` (+0.300%). Missing provenance
is a documentation defect, not an accuracy one. Do not re-estimate it.

**Passing TD is the worst-calibrated QB quantity**: slope 0.812, PIT chi2 267,
50% intervals covering 0.794. The only estimand where a candidate improvement
survives the bootstrap. Receiving and rushing TD efficiency refused by name,
citing the governed list's ESTIMAND_UNVERIFIED.

**RC2's confirmed receiving defect is mostly NOT an efficiency error.** RC2
measured +2.1801 unconditional. Conditional on realised targets it is +0.779;
on realised receptions, **+0.602**. About 72% lives in the opportunity layer.
That is a better explanation of why three of RC2's four repair arms failed than
"the repairs were badly chosen", and it says where to look next. What
efficiency defect remains is concentrated at 10+ targets: bias +2.538, slope
0.855. No repair arm was run there -- RC2 closed that family.

**Decomposition, composed condition, n=2,653:** mean |opportunity error| 8.73
attempts, mean |efficiency error| 2.17 yards per attempt, mean |combined
error| 71.0 yards; 50.9% offsetting, 46.8% same sign. Track 1's 55.7% is a
different layer and a different quantity, motivated asking, and appears in no
fit.

**Nothing promoted.**

**Suite:** 76 modules, 839 test functions, 4,569 checks, 0 failing, 0 raised.

**Detail:** `nfl/research/q7/Q7_SPEC.md`, `Q7_DECISION.md`,
`Q7_FORWARD_CHAIN_RESULTS.json`.

