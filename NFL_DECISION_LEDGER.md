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
