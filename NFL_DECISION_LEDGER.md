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
