# Showdown readiness audit, and everything new since Sunday

Measured 2026-10-01 at HEAD `8fa5cdfe` on `claude/nfl-greenfield-architecture-stsxmk`.
Every number below was read out of the repository or produced by a run whose
output is quoted. Where something was not run, it says so.

---

## Part 1 — Could we run a showdown slate tonight?

**No, and the binding reason is an input, not the code.**

### The decisive blocker: there is no slate file for tonight

| What a showdown run needs | Newest thing in the repo | Age |
|---|---|---|
| DK showdown salary / entries export | `DKEntries_IND_KC_SHOWDOWN_2026W2.csv`, `DKEntries_NYG_LAR_SHOWDOWN_2026W2.csv` | **Week 2**, 09-23 |
| Any DK slate export at all | `DKEntries_EARLY_ONLY_2026W3_62.csv` | Week 3, 09-27 |
| Official inactives for tonight | none | — |

No file for tonight's game exists on disk, and I have no network — every
outbound request returns 403. Acquiring it is the other agent's, not mine.

### The second blocker: our 2026 evidence stops at Week 2

`nfl/warehouse/TEAM_GAME.json` holds 544 club-game rows for 2026, of which
**64 have a score — Weeks 1 and 2 only.** Weeks 3 through 18 are schedule rows
with `points` absent and stats marked `UNKNOWN_PENDING_ACQUISITION`.

That means **Week 3 was played and never ingested.** Any projection produced
tonight would rest on two games of current-season evidence, with the most
recent played week missing. This is the largest accuracy problem on the list and
it is invisible from the readiness board, because the board checks lineage
freshness, not whether the world moved on.

It is also worth stating plainly that having all 18 weeks present as rows is a
leakage surface. It is currently benign — the unplayed rows carry no outcome
columns — but "benign because the columns happen to be empty" is not the same as
"guarded", and nothing asserts it.

### The third blocker: there is no showdown product path

The one-command path, `nfl/tools/slate_to_portfolio.py` (slate file in, legal
48-lineup DK portfolio out), contains **no occurrence of "showdown", "captain" or
"classic"**. It is a classic full-slate path.

The showdown *components* exist and are governed, under `nfl/dfs/showdown/`:
`universe`, `universe_contract`, `candidates`, `captain_metrics`, `correlation`,
`scenarios`, `optimal_worlds`, `portfolio_report`, `kicker_identity`. The DK
rules are encoded correctly — `SALARY_CAP = 50000`, `N_FLEX = 5`,
`CPT_MULTIPLIER = 1.5`.

But the only thing that *drives* them end to end is
`nfl/research/showdown_fixture/code/run_research_fixture.py`, which hardcodes:

```
GAME = '2026_02_NYG_LA'
KICK = '2026-09-22T00:15:00Z'
SAL  = 'nfl/dfs/salaries/raw/DKEntries_NYG_LAR_SHOWDOWN_2026W2.csv'
DRAWS= 'nfl/research/mnf/run_nyg_la/9f2e3d1ae24fc05b/player_draws_manifest.json'
```

and declares its own status as
`'RESEARCH FIXTURE. CANDIDATE_NOT_ACCEPTED_BASELINE. No gate promoted.'`

So showdown is research-grade with a fixture driver, not a product with a
runner. Pointing it at a new game is a coding task, not a parameter change.

### What *would* work, measured not assumed

I ran the showdown-relevant modules through the authoritative runner just now:

```
test_showdown_site_legality                  6 fn, 12 check(s), 0 failing
test_showdown_universe_is_slate_addressable   6 fn, 25 check(s), 0 failing
test_dfs_showdown_research                    9 fn, 46 check(s), 0 failing
test_kicker_resolution                        6 fn, 20 check(s), 1 failing
```

Genuinely working:

- **The exact solver returns a lawful optimum.** `optimal_worlds.solve` used to
  optimise over flex slots, captain and salary without knowing DK Showdown
  requires both clubs, so every `p_optimal` it published was a frequency over
  lineups that could not necessarily be entered. Team coverage is now carried in
  the DP state, and the test proving it uses a toy slate where the unconstrained
  optimum is single-team in every world.
- **The showdown universe is genuinely parameterised by slate** (DEF-062). The
  old pins were not only paths — an inactive list and a Buffalo roster were
  baked in, so a half-fix would have tagged the wrong players in the wrong game
  and still looked parameterised. The test changes a salary in a second slate
  and checks the first slate's inactive list does not follow it across.
- **10 of 15 readiness stages are FRESH**: team_game, player_game, role_history,
  coverage, sim.shared_state, sim.efficiency, sim.variance_components, sim.dst,
  sim.pair_correlations, sim.correlation_check.
- **The DST scoring tail is now measured from play-by-play**, which matters more
  in showdown than anywhere else because a DST is 1 of 6 roster slots rather
  than 1 of 9.

### One live defect that lands directly on showdown

`test_kicker_resolution` fails one check:

```
FAIL all 32 clubs resolve a kicker at 2026 week 2
     31/32 refused={'KICKER_ELIGIBILITY_DISAGREES_ACROSS_VINTAGES': ['NYJ']}
```

31 of 32 clubs resolve a kicker; **NYJ does not**, because its kicker
eligibility disagrees across vintages. In showdown a kicker is one of six slots,
so for a game involving the Jets the K slot would refuse rather than fill.
`2026_04_NYJ_CHI` is on the Week 4 schedule. I am not asserting that is tonight's
game — the repository has no kickoff-time artifact for Week 4, so it cannot tell
me which of the 16 Week 4 games is the Thursday game, and I will not guess.

### Governance state, which gates this regardless

- `PROJECTION_SYSTEM_STATE` is **`NOT_VALIDATED`**. Unchanged, and correctly so.
- `READINESS.PRODUCT_MODE` is **`PARTIAL`**: 10 FRESH, 5 STALE
  (`derived.role_state`, `slate.projection`, `slate.post_inactives`,
  `field.model`, `portfolio.contest` — all the slate-facing stages).
- `coordination/AUTOMATION_POLICY.json` is still
  `autonomous_operation_enabled: false`, `execution_mode: "MOCK"`. Untouched.
- The permanent rule — *"if the system cannot autonomously produce a complete
  legal lineup portfolio from a slate file by Saturday, it is not
  production-ready for Sunday"* — currently **passes for classic**:
  `saturday_rule.state = PASS`, 48 entries, all legal, all distinct, from a
  442-player pool. There is no showdown equivalent of that test.

### What is missing, in the order it blocks

1. **Tonight's DK showdown salary/entries export.** Other agent. Nothing
   downstream can start without it.
2. **2026 results for Week 3 onward.** Other agent. Without it, projections rest
   on two games.
3. **Official inactives for tonight.** Other agent for the bytes; A7 (the
   event-driven inactives pipeline) is still pending in-repo.
4. **A showdown runner** with the four clauses `slate_to_portfolio` has — stage
   refusals, a status board that always emits, legality validation, DK upload
   CSV. Mine, and it is the largest piece of in-repo work here.
5. **The NYJ kicker vintage disagreement.** Mine, small, and it is a real
   refusal rather than a wrong number.
6. **A showdown Saturday-rule test**, so "can it produce a legal showdown
   portfolio autonomously" is tested rather than assumed.

I am not recommending a wager, and nothing here should be read as one.

---

## Part 2 — Everything new since Sunday

**82 commits** between 2026-09-27 00:00 and now. Grouped by what they changed.

### The verification layer — this is where the week actually went

- **23 test modules were invisible to the authoritative runner** and ran zero
  checks (~217 checks). They had been reported as passing for weeks. The runner
  discovers `test_*` functions and reads module-level `PASSED`/`FAILED`; those
  modules exposed neither. Fixed by `nfl/tests/_registry.py:emit()`.
- **Connecting them exposed order dependence**: 8 modules passed alone and
  failed in sequence. Declared Priority Zero.
- **4 of the 8 are now closed** and were the FantasyCruncher firewall working as
  designed — `test_fc_firewall_and_projection_source`,
  `test_projection_guards_catch_v0`, `test_search_quality_gate`,
  `test_slate_to_portfolio`. The firewall refuses if any proprietary module is
  imported anywhere in the interpreter, so those tests cannot share a process
  with one. They now declare `REQUIRES_OWN_PROCESS` and the runner gives each a
  fresh interpreter.
- **The suite can now vary its own order**: `--reverse`, `--shuffle [SEED]` with
  the seed always printed, `--modules a,b` for an exact ordered pair, and
  `--watch p1,p2` which hashes named paths after every module and names the
  module that changed one.
- **Two repository principles recorded** in `CLAUDE.md`: *a test that is not
  executed by the authoritative harness does not exist*, and *a test that
  depends on suite order is not a reliable test* — with the one carve-out named,
  a **declared** process-scoped guarantee.
- **The "911 assertions, 0 failing" line is withdrawn**, not edited away. It
  predated the discovery that 23 modules were being skipped, so it counted
  neither their checks nor their failures.
- **Archiving was opt-in the wrong way round**: every suite run called
  `sunday.run()` and sealed a new directory into the permanent record, so the
  archive filled with test artifacts indistinguishable from delivered slates.

### Two claims of mine withdrawn this week, with cause

- **The chunk bisect was searching 80 of the 303 modules** that actually precede
  `test_v1_projection`. It built its candidate list from a filtered set instead
  of from the runner's own discovery order, so it omitted every module that
  invokes the production pipeline. Its four "clean" chunks narrow nothing.
- **"`test_sunday_run` rewrites the artifacts `test_v1_projection` asserts on"**
  is true in every step and false in its conclusion. Measured: v1 alone is 16
  checks 0 failing; the ordered pair is 23 checks 0 failing; and `--watch`
  reports 0 changes, because `sunday.run()` regenerates those artifacts
  **byte-identically**.
- Also withdrawn: I suspected the orchestrator of destroying uncommitted edits.
  It did not. My own bisect script ran `git checkout -- .` before every chunk.

### Projection and model work

- **Two unit mismatches that crushed established players**: a club-wide depth
  rank where a group-scoped one was meant, and a mis-scoped prior weight. A
  share-of-group was being fed in as a share-of-club; fixing it took reproduced
  correlations from 7 of 16 to 11 of 16.
- **#99 answered**: the *cohort* prior carries the ranking loss, not the
  player's own history. Turning the cohort prior off is worth **+0.0256 ρ**;
  turning the player's own-history prior off is worth **+0.0000**. Separation
  rises 7.32 → 9.21 against a realised 15.33, about a quarter of the gap.
- **The negative forward-chain verdict was reversed on its central claim.** A
  season-constant band is −0.0364 against baseline, reproducing the original
  finding; a **weekly capped** band is **+0.0151 (z 3.2)** on selection and
  **+0.0336 (z 3.7)** on confirmation.
- **The oracle-availability gap is large**: +0.067 to +0.072 ρ and −0.33 MAE.
  That is why official inactives are a predictive feature, not operational
  metadata.
- **Logistic-normal shares: REJECTED** on the acceptance criterion, with the
  diagnosis of why rather than a quiet retry.
- **DST**: defensive and return touchdown tail measured from play-by-play,
  closing OUT-041 in repo — 0.1197 defensive/return TD per club-game, 0.0237
  safeties.

### Product and infrastructure

- `slate_to_portfolio`: one command, slate file in, legal 48-lineup DK portfolio
  out — the classic path.
- Contest-aware portfolio: 48 entries chosen as a set.
- An exact optimiser proven against brute force; it had been accepting
  `required_players` and silently ignoring them.
- Readiness that can say no: per-stage freshness, and the Saturday rule as a
  test rather than an assertion.
- Artifact lineage: a correct module behind a stale artifact is now mechanically
  detectable as `STALE_DEPENDENCY`.
- Versioned run directories — a run the next run destroys is not a record.
- Hard Rock price history with seal-before-price discipline: one board is not a
  line, and a price may not predate the seal.
- Constraint manifest: a dropped constraint is now impossible rather than
  unlikely.
- OUT-040 ownership turned into an exact expiring list behind one governed door.

### Written in the last day, and not yet run

- `nfl/research/dst/validate.py` — DST validation split into the six components
  requested: mean scoring, sack rate, turnover rate, defensive TD frequency,
  return TD frequency, tail calibration. **Not executed.** Two facts shaped it:
  `DstModel.draw` resamples its own band pool, so an in-sample check of five of
  six components passes by construction and every fold is forward-chained by
  season; and `return_td` is counted from play-by-play and then **discarded**, so
  the model cannot distinguish a pick-six from a punt return and that component
  reports REFUSED with the realised rates attached.
- `nfl/production/suite/taxonomy.py` — the six-category failure taxonomy. Its
  reader was anchored to `nfl/tests/`, so a failing `sportsplatform/` module
  parsed as no module at all, and it could not read the `OWN PROCESS` line,
  making the four process-scoped modules unclassifiable by construction. Both
  fixed and demonstrated against seeded inputs.

### What is still open on Priority Zero

The acceptance criterion is: fresh process = normal order = `--reverse` =
`--shuffle`, for the same commit and seed. We are not there.

Four reported victims remain unexplained: `test_v1_projection` (5),
`test_role_state_history` (7), `test_sunday_run` (3),
`test_role_and_prior_units` (1). The honest first question is not which module
poisons which — it is **whether they fail in the real checkout at all**, because
they were identified in git worktrees, which contain only tracked files and
therefore lack the gitignored raw store. That environment already inflated the
failure count once: 5 of 6 modules retested in the real checkout passed, and two
of these four have now been shown passing there in an ordered pair.

The instrumented full-suite run that would settle it **did not complete**. It
reached module 48 of 317 and died when the container restarted; there is no
completion marker and no final problems block, so there is no current
full-suite failing set and the P1 taxonomy still has nothing trustworthy to
classify. Restarting that run is the next thing I do.
