# NFL-V1-R4 + FTN-M10 — return

Two missions, one session. Both are answered below, and both ended somewhere
other than where the brief pointed.

| | |
|---|---|
| **R4 verdict** | **`RUSHING_CONVERSION_CONTROL_UNDEFINED`** |
| **FTN-M10 verdict** | **`FTN_MATCHUP_NO_DETECTABLE_INCREMENTAL_VALUE`** |
| Starting HEAD | `a22d3fc0d6127f6e3a5f0b91624da37192f67621` |
| Ending HEAD | `731e1f8` (on `main` and `claude/nfl-greenfield-architecture-stsxmk`) |
| Canonical suite | 39 modules, 418 test functions, **2,445 checks, 0 failing** |
| G0A | **11/12**, untouched |
| NFL-1 | **NOT AUTHORIZED**, untouched |

The single most important thing in this document is not either verdict. It is
§4: **the engine forecasts 2.62 starting quarterbacks per team**, and nothing
had ever measured it.

---

# Part 1 — R4: complete the football engine

## 1. The rushing-conversion answer, and why it is not "P5A is missing"

P5A exists, ran, and is the canonical research module for carry → rushing
yards. What does not exist is an **adjudication**. There is no `*_FINDING.md`
(rc1, rc2 and td1 each have one), no decision artifact, and `PATH_C_STATE`'s
`rushing_conversion` entry carries no `decision` field — unlike
`receiving_conversion`, which names `RC1-ACCEPT-001`.

Three things are open. Full inventory in
`nfl/production/nonqb/rushing_inventory.json`.

**RUSH-DECISION-1 — the family is not chronology-legal as implemented.**
`predeclaration_p5a.md` §9 says the distributional family is chosen by CRPS on
an **inner validation season (Y−1)**, fitted on seasons before that.
`run_p5a.py` instead scores each family against the **evaluation season's own
realised rushing yards** and keeps the minimum. There is no inner-validation
code anywhere in `nfl/research/p5a/`. Two consequences: no rule names a family
for an unplayed season, and every reported P5A CRPS is a best-of-four minimum
taken on the test season. The chosen family is not even stable — `emp_tilt`,
`mix3`, `mix3`, `emp_tilt` across 2022–2025.

**RUSH-DECISION-2 — the promotion bar was never adjudicated.** Applying §14 for
the first time, system B against the control A:

| criterion | result |
|---|---|
| 1. pooled CRPS improves | MET, 4 of 4 seasons |
| 2. block-bootstrap CI excludes zero | MET, 4 of 4 |
| 3. direction consistent in ≥3 of 4 | MET, 4 of 4 |
| 4. randomised PIT within 25% | **BREACHED in 2024** (+31.5%); 2022 −6.8%, 2023 +13.6%, 2025 +17.9% |
| 5. tail calibration not worse | MET, 4 of 4 |

The predeclaration does not say whether criterion 4 is read per season or
pooled, and criterion 3 is the only one that names a per-season rule. Read one
way the control is the opportunity-only pool A; read the other, a player-shrunk
system is promoted. **That is the decision that names the control, and it is
yours.**

**RUSH-DECISION-3 — the implemented control is not the predeclared control.**
§5 specifies a pool stratified by position group (RB versus non-RB rusher).
`p5a_lib.Pool` is built from all prior-season carries, unstratified.

**What I built instead of a control.** The layer refuses by name
(`RUSHING_CONVERSION_CONTROL_UNDEFINED`) carrying all three decisions, and the
prohibitions §C asked for are structural: a caller-supplied efficiency prior is
refused (`RUSHING_PRIOR_NOT_OWNED_BY_CALLER`), and
`rushing_yards = carries × point_estimate` is impossible because no control
emits rushing yards at all. A source-level scan of `nfl/production/` for that
pattern is in the suite, with a seeded violation proving it bites.

Two of the three are arguably corrections rather than judgements — the
predeclaration is authoritative on both the nesting and the stratification — so
if you want, the fastest route to a defined control is a P5A correction run I
can specify and execute. I did not do it tonight because it changes what a
research result *is*, and that is a call you should make knowingly.

## 2. Rushing touchdowns are NOT blocked

TD2 carries `rush|carry` as a primary estimand with the same `B_pos` baseline
already in production for receiving. Fitted on seasons before 2026:

```
B_league 0.035715
B_pos    RB 0.031611 (2,173 TD / 68,742 carries)
         QB 0.058481 (  633 / 10,824)
         WR 0.043224 (  111 /  2,568)
         TE 0.086154 (   28 /    325)
```

Wired to the same carry draw, so a player with no carry in draw *j* scores no
rushing touchdown in draw *j* by construction rather than by a check applied
afterwards.

**Correction to the R3 freeze record:** it listed `td2_results.json` as absent.
That filename never existed; TD2's artifacts are `td2_ladder.json`,
`td2_composition.json`, `td2_persistence.json` and `td2.pkl`. TD2 was never
blocked.

## 3. The complete engine, end to end

`nfl/production/nonqb/football_engine.py` runs one game through every
implemented layer on one draw index. Both rehearsals are thin callers of it — a
rehearsal that reimplemented the chain would be testing itself.

**§K, TEST-ONLY, all 16 games, 200 draws, 418.9 s.** Only the 2026 injuries
rows are stubbed; everything else is captured input and frozen fits.

```
team_environment PASS   appearance PASS      participation PASS
targets_carries  PASS   carries    PASS      receiving_conversion PASS
receiving_td     PASS   rushing_td PASS      qb_layer PASS
rushing_conversion  DEFERRED[RUSHING_CONVERSION_CONTROL_UNDEFINED]  16/16
publication gate    FAIL[TEST_ONLY_DATA_IN_PRODUCTION_PATH]         16/16
```

**885 player records**: WR 381, RB 213, TE 207, QB 84. Every RB carries
appearance, participation, targets, receptions, receiving yards, receiving TD,
carries and rushing TD — and `rushing_yards` as an explicit **ABSENT** entry
naming the three open decisions. Every QB carries all ten of its metrics
including rushing yards.

**§L, real inputs, nothing stubbed, 16 games, 47.6 s.** `team_environment`
executes on all 16; every non-QB layer defers by name; **0 player records**;
publication `BLOCKED[NFL1_NOT_AUTHORIZED]`.

## 4. The finding that matters most

Wiring carries into the joint accounting raised the QB carry containment
identity. Following it produced this, measured on the real 2026 week-1 roster,
32 teams × 200 draws:

| | |
|---|---|
| D1 team dropbacks | 36.75 |
| QB-summed dropbacks | **79.76** — ratio **2.17** |
| cells where a team's QBs collectively out-drop their own team | **5,930 of 6,400 (92.7%)** |
| QB rows per team | **2.62** |
| teams with exactly one QB row | **1 of 32** |
| QB rush opportunity as a share of team carries | 0.284 drawn against **0.157** measured historically |

**Diagnosis, and it is not a bug in QB V1.** The QB layer models a passer's
line *conditional on being the team's primary passer*. Nothing selects which of
a team's 2.62 rostered quarterbacks that is. Every other position passes
through the appearance layer; the quarterback does not. Appearance would not
fix it either — a backup can appear without taking a snap at quarterback.

**Why nothing caught it.** `qb_accounting.reconcile_team` has carried a hard
check of QB rush opportunity against a same-draw team rush budget since R2, and
**it has never refused anything**, because no production caller ever passed
`team_rush_draws`. A guard that has never been given its input is not a guard —
this repository already records that lesson about `assert_batch_games_are_new`.
There was no dropback counterpart at all, and the dropback half is where the
2.17× lives.

**What I did:** fed the dormant guard its budget from D1, and added
`reconcile_team_volume` with two new identities. The engine now returns
`FAIL[QB_TEAM_VOLUME_INCOHERENT]` naming `QB_PRIMARY_PASSER_SELECTION` as the
research gap. **No model changed and no draw was clipped.** Making the defect
visible is the deliverable; closing it is research that has not been done.

This is also why the §K rushing accounting reads `rushing_ok 0/16`: not an
unexplained failure, but the new guard correctly refusing on the named gap.
Receiving accounting reconciles **16 of 16** across **202,800 cells** with zero
violations on every identity.

## 5. Research-tree immutability — R3's fix concealed a larger mutation

R3 found a production run rewriting a research report and fixed it by
snapshotting and restoring the file. That fix was cosmetic.

`regenerate.stage_inputs` symlinks every file in the research code directories
into its work tree. When a previous build has left `panel_enriched.pkl` and
`volume_store.npy` in `nfl/research/p4b` — both gitignored, so `git status` says
nothing — the builders open those names for writing and write **138 MB straight
through the symlinks into the research tree**. R3 restored the small JSON and
never saw it.

`nfl/production/derived.py` corrects it structurally: production imports the
regeneration module's **pure functions**, never its command line, breaks the two
output symlinks before building, and caches into `nfl/derived/` outside the
research tree. Every read is re-verified against `ABC_MPR_IDENTITY.json`
independently of the script's own check.

`assert_research_tree_unchanged` hashes every file under `nfl/research` around a
production run: **340 files byte-identical**, with a seeded mutation proving the
guard bites.

A second defect fell out: the QB layer read `panel_enriched.pkl` through
`p4c_build.P4B`, which defaults into the research tree, so it had been silently
depending on a copy someone happened to leave there. It surfaced the moment that
copy was removed. `derived.artifacts()` now points the research loaders at the
cache in one place.

## 6. Per-game injury readiness

The slate dashboard was the right thing to show and the wrong thing to gate on.
Readiness is now per game, with six declared states, and **a game executes D2
only when both its own teams satisfy the frozen input contract** — the feature
requirement is unchanged.

```
2026 week 1:  INJURY_REPORT_NOT_YET_FILED  15 games
              INJURY_REPORT_INCOMPLETE      1 game  (NE@SEA)
              executable                    0 of 16
```

NE has 3 rows and SEA 8, but `report_status` is unfilled on all 11, so the one
game where both teams have filed anything is still short of the contract.

A missing report is `INJURY_REPORT_NOT_YET_FILED` and its reason says
*absence of a report*, never absence of injury — `teammate_availability` is a
team-level feature and the two cannot be told apart from the data. The suite
checks that one team's missing report does not change another game's state.

## 7. Week-2 readiness

Both future requirements are now named separately, at every week, so neither is
forgotten because the other is live:

| source | needed from | refusal if absent | substitute |
|---|---|---|---|
| `injuries_2026` | week 1 | `INJURY_REPORT_NOT_YET_FILED` / `INCOMPLETE`, per game | none |
| `pbp_participation_2026` | week 2 | `PARTICIPATION_HISTORY_STALE` | none — `snap_counts` has no pass/run split |

Week 1 reports the participation requirement as satisfied; week 2 reports it
`NOT_SATISFIED` and names the missing source.

## 8. Performance

| step | time |
|---|---|
| derived artifact build (hash-verified, exact) | 25.7 s |
| P4C parameter fit | 30.4 s |
| RC1 receiving priors | 39.9 s |
| TD2 priors (rec / rush) | 9.0 / 38.5 s |
| appearance fit + predict, 920 players | 21.8 s |
| **full 16-game engine, 200 draws, all layers + QB** | **418.9 s** |

R3's comparable figure was 450.7 s for a chain without carries, rushing TD, the
QB layer or the player-record contract, so the engine got materially bigger and
slightly faster. No randomness semantics changed; same seed reproduces the same
draws, and the suite checks it.

---

# Part 2 — FTN-M10: the matchup endpoint

## 9. Every figure in your brief was verified independently, and all confirmed

10 games, 1,624 plays, 6,181 matchup records, 676 pass plays, 673 with matchup
coverage (99.6%), and the stated alignment and defender vocabularies. Raw bytes
hashed and sealed in `nfl/research/ftnm10/ftnm10_provenance.json`; not committed,
on the FTN-S1 precedent.

## 10. The premise does not hold

**The "better endpoint" is a strict subset of the one we already had.** Game
30351 (DAL@PHI) is in both this packet and the earlier `participation_1.json`
sample, and the matchup payload is **identical** — 596 records across all 156
plays.

What the OLD endpoint carried and this one does not:

- `on_field` — offense and defense personnel on every play
- `conditions` — 30 charting types: pre-snap box count, db_count, formation
  alignment, hash, OL count, backs, **coverage shell**, **motion**; post-snap
  pass rushers, time to pressure, concept, QB pressure/hit/hurry, blitz, stunt,
  play-action, RPO, first read
- `advanced_stats` — 3,011 participant/stat/value records per game

What is genuinely new is **nine more games**. No new primitive. And motion,
coverage shell and box count — the fields most likely to carry pre-snap
predictive structure — are absent from nine tenths of the sample.

Also: `defensive_player.role` is **null on all 6,181 records**.

## 11. What ten games settled

**FTN-S2's one-game ratios do not replicate.** TE_INLINE 1.43 → 0.70, BACK
0.82 → 1.19, SLOT 0.79 → 0.99, and the eye-catching SCB 0.39 → 0.84.

**The defender class is close to a function of alignment.** Mutual information
1.055 of 1.826 bits — **57.8%** of the defender-class entropy. WIDE→CB 97.8%,
BACK→LB 94.4%. For WIDE, BACK and TE_INLINE there is effectively only one
defender class, so matchup and alignment are the same variable. Where they
differ, the contrasts include zero: SLOT LB−SCB +0.067 CI [−0.044, +0.170];
TE_FLEX S−LB +0.077 CI [−0.047, +0.202].

**No individual-defender (shadow) effect survives clustering.** 13 CBs with ≥30
charted route snaps: excess variance over binomial +0.00455, implying a 6.75pp
between-CB SD — but the game-clustered CI is **[−0.00304, +0.00875]**. The naive
version is the same failure mode the sibling MLB project records as naive SEs
understating uncertainty roughly threefold.

**The decisive bound.** The one forecastable alignment primitive is a WR's
wide/slot mix — persistence r = **+0.70**, CI [+0.30, +0.96], n = 15, and it
survives the position control. Within WRs the target rate is **0.1835 wide
against 0.1894 slot**: six tenths of a percentage point. That bounds every
downstream gain, and it explains why FTN-S2 found alignment *worse* than
control — the feature costs degrees of freedom and returns almost nothing.

## 12. The interesting primitive is not matchup

The per-snap **role** label is a direct route-participation observation — the
quantity ROUTE-BB1 was built around and the one nflverse cannot supply.

| | WR | TE | RB | ALL |
|---|---|---|---|---|
| route participation, 10 games | 0.936 | 0.849 | 0.768 | 0.889 |
| FTN-S1, one game | 0.989 | 0.882 | 0.818 | 0.928 |
| persistence r | **+0.797** | +0.843 | +0.623 | — |
| CI | [+0.43, +0.96] | [+0.35, +1.00] | **[−1.00, +1.00]** | — |
| n pairs | 13 | 6 | **5** | — |

S1's single game read systematically high at every position.

**It persists where it is worth least.** RBB1's frozen ceiling puts the
addressable share at RB 0.969 > TE 0.813 > WR 0.636. The position where route
information is worth most is the one this sample cannot estimate at all; the
one it can estimate is where WRs already run routes on 94% of pass snaps.

## 13. The structural sample limit, and the actionable part

**190 offensive players charted. 38 in two games. ZERO in three or more.** Only
DET, HOU, KC and IND appear twice. Every persistence question is a single lag-1
pair from four teams — no split-half, no lag structure.

Resolving RB route persistence to ±0.15 needs roughly **68 RB player-pairs**
against the 5 available: on the order of **110+ charted games, and only if teams
are deliberately repeated**.

**Ten scattered games is close to the worst possible design for every question
you asked.** If there is a next sample, follow a small number of *teams* across
many weeks.

*One correction to my own working:* I first derived a "design effect" from the
marginal per-route target rate and got 0.16× — clustering apparently helping,
which cannot be right. It was meaningless: because exactly five receivers are
charted and at most one is targeted, the marginal rate is near-deterministic at
~1/5 in every game. The requirements above come from the observed CI widths of
the contrasts instead.

## 14. Verdict

**`FTN_MATCHUP_NO_DETECTABLE_INCREMENTAL_VALUE`** — a real negative, not a null
from a thin sample: 9.3× FTN-S2's route-play count, with a structural
explanation for why. Scoped precisely: the individual-defender question is
`SAMPLE_TOO_SMALL`, and route participation is a separate question this sample
cannot close.

**I do not recommend buying on this evidence.** The endpoint contains less than
the sample we already had, its headline primitive is largely alignment
re-encoded, and the one thing in it that does persist is bounded at ~0.6pp where
it is measurable.

---

# Part 3 — where this leaves the system

## Ranked open gaps

**1. QB primary-passer selection.** A 2.17× team dropback error dwarfs every
other item here, including anything the FTN endpoint could supply. It is now
named and guarded but not closed. This is where I would go next.

**2. Rushing conversion adjudication.** Three decisions, two of which are
corrections the predeclaration already settles. A P5A correction run would
resolve RUSH-DECISION-1 and RUSH-DECISION-3 and might dissolve
RUSH-DECISION-2 by changing the PIT numbers entirely.

**3. Receiving calibration.** RC2 confirmed the defect and its predeclared
repair family does not fix it inside the bounds that protect discrimination.

## Genuine blockers

- **Owner decision:** the three rushing-conversion decisions, and whether I
  should execute the P5A correction run.
- **External data:** 2026 injury reports (16 games, 0 executable);
  `pbp_participation_2026` from week 2; an FTN sample designed around repeated
  teams if that question is to be reopened.
- **Governance:** NFL-1 remains unauthorized and nothing here requests it.

## What did not change

No model was promoted, retuned or substituted. No 2026 outcome was consumed. No
market, DFS or wagering component was touched. `PATH_C_STATE` was not modified.
G0A is 11/12. FTN was not contacted and no FTN data reached production.
