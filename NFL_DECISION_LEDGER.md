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
