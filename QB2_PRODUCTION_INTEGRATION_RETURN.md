# QB2 — PRODUCTION PACKET P2 RETURN

**Date** 2026-09-08 · **Repo** `94924676jp-a11y/Nfl` · **Branch** `main`
**Pre-registration** `nfl/research/qb2/predeclaration_qb2.md`, sha256
`e69bd331bb72a3f869b8469c27f0d9782ff49c7c69874ea79585f55a9eb84ff1`, committed
`3241e54` **before** any result existed and unchanged since.
**Addendum** `nfl/research/qb2/addendum_qb2_coherence.md`, committed `6143030`,
also **before** the corrected run.

**Production decision: `QB_V1_BASELINE_ACCEPTED`.**
This is a **production baseline selection**, not a model promotion. Nothing is
promoted. **G0A remains 11/12. NFL-1 remains NOT AUTHORIZED.** No 2026
outcomes, no market data, no FTN, no DFS, no PFR-restricted fields.

---

## 1. What was asked, and the one-line answer

Replace the QB audit placeholder with the simplest causally coherent,
chronology-safe QB V1 distribution layer, run it through the real production
path, and stop. **Done.** A normal historical fixture now executes the QB layer
as actual model logic — 36 QB-games over a full 16-game slate, 2,000 draws,
792,000 draw cells — through `python -m nfl.production.run_forecast`, sealing a
byte-reproducible artifact while publication stays refused.

**The most useful thing this packet produced is not the model.** It is that
three checks predeclared in advance each caught something that was actually
wrong, including two defects in work I had already reported as finished.

---

## 2. The headline finding: three impossible-draw defects, found by the
##    predeclared check rather than by inspecting results

Predeclaration §8 required the QB layer to reconcile **per draw**. Run on the
first candidate draw set (2024, n=625 QB-games, m=200, 125,000 cells per
statistic):

| constraint | violating cells, before | after |
|---|---|---|
| `dropbacks == attempts + sacks + scrambles` | 0 | 0 |
| `completions <= attempts` | 0 | 0 |
| `passing TD <= completions` | **84** (0.067%) | **0** |
| `interceptions <= attempts − completions` | **189** (0.151%) | **0** |
| `scrambles <= rush opportunities` | **22,749** (18.2%) | **0** |
| `rush TD <= rush opportunities` | 0 | 0 |
| `rush opportunities == scrambles + designed` | n/a — not composed | **0** |

**These are impossible states, not mis-calibrated ones.** Measured on the real
frame, 2,645 QB player-games 2022–2025: `pass_td > completions` occurs **0
times**, `interceptions > attempts − completions` **0 times**, `completions >
attempts` **0 times**. `rush_opp` is `designed + scrambles` by construction.

**An aggregate check would have passed all three.** Averaged over 125,000
cells the first draw set reconciled to three decimals. That is why the check
was specified per draw.

### Cause, in each case mine, and each the same error

The predeclared factorization is

    ... -> completion -> pass yards -> pass TD / INT
        -> designed rush / scramble -> rush yards / rush TD

and the simulator drew three nodes off the wrong parent:

1. **Passing TD** from `Binomial(ATT, td_per_attempt)` — skipping completion.
2. **Interceptions** from `Binomial(ATT, int_per_attempt)` — independent of
   completions, so a draw could charge an interception to a pass it had
   completed.
3. **Rush opportunity** drawn whole from `Binomial(DB, rate)`, uncoupled from
   the scramble count the mix had already produced — contradicting the
   predeclaration's own sentence, *"Designed rush and scramble stay distinct."*

### Repair, at the causal node, not by clipping

    PTD ~ Binomial(CMP,        td_per_completion)
    INT ~ Binomial(ATT - CMP,  int_per_incompletion)
    DES ~ Binomial(DB,         designed_per_dropback);  RO = SCR + DES

Re-basing a rate to its causal parent is not tuning: the expected count is
unchanged when conversion matches history, and no rate was chosen by looking at
a score. `K = 4` and half-life 2 are untouched inherited constants. Clipping
was rejected outright — it converts a measurable defect into an invisible one.

This is the same class as R1's point-substitution and as my own dispersion
defect earlier in this packet: **a node modelled off the wrong parent.**

---

## 3. Two predeclared analyses the first run never executed

Both were in the pre-registration and both were simply missing. They are run
now.

### 3a. Rushing-yards decomposition (secondary estimand, 3 components, 2³ = 8)

n = 2,494. Baseline CRPS **8.1827**. Shapley efficiency gap **0**.

| component | CRPS gain | share | 95% CI |
|---|---|---|---|
| `V·S` shared volume | 0.4709 | 11.01% | [0.3554, 0.5853] |
| `RO` rush opportunity | 1.2429 | 29.06% | [1.0606, 1.4474] |
| `RY` yards per rush | **2.5638** | **59.93%** | [2.3523, 2.7720] |

**The rushing side inverts the passing side.** For passing yards, opportunity
(V+S+M) carries 61.3% and efficiency (C+Y) 38.7%. For rushing yards, efficiency
alone carries 59.9%. Any claim that "opportunity dominates" is a claim about
the passing chain and does not transfer.

**Its full-oracle arm is NOT exact (CRPS 3.9051, not 0), and that was stated in
advance.** The scramble half of a QB's rushing opportunity comes from the
dropback mix `M`, which §5 did not make one of the three rush components. The
residual is **named as scramble volume** rather than closed by adding a fourth
component after seeing the result.

### 3b. The closed four-rung ladder (§6)

Pass-yards CRPS, 2022–2025, n = 2,494 over 1,087 games, game-clustered
bootstrap, 400 resamples, L1 as reference.

| rung | CRPS | Δ vs L1 | 95% CI | separates? |
|---|---|---|---|---|
| `L0` pooled | 54.9452 | +6.3021 | [+5.3420, +7.2837] | yes, worse |
| `L1` shrunk | **48.6431** | — | — | reference |
| `L2` EWMA hl2 | 51.0475 | +2.4044 | [+1.1912, +3.4598] | yes, worse |
| `L3` shrunk EWMA | 49.0105 | +0.3674 | [−0.4738, +1.1892] | **NO** |

**L3 does not separate from L1.** The honest reading is that the ladder does
not establish either as better; **L1 is retained as the simpler of two
indistinguishable rungs.** That is a baseline selection, not a finding that L1
is superior. L0 and L2 are worse and their intervals exclude zero.

---

## 4. Primary decomposition — passing yards

n = 2,494 QB-games over 1,087 games, 2022–2025. Baseline CRPS **48.6431**.
Full-oracle identity error **5.68e-14** in every season (VALID). Shapley
efficiency gap **0.00e+00**. Exact Shapley over 2⁵ = 32 coalitions,
order-invariant. Game-clustered bootstrap, 400 resamples.

| component | CRPS gain | share | 95% CI |
|---|---|---|---|
| `V` team dropbacks | 12.1997 | 25.08% | [11.4598, 12.8971] |
| `S` QB share | **14.6425** | **30.10%** | [13.4264, 15.8641] |
| `M` dropback mix | 2.9928 | 6.15% | [2.7515, 3.2785] |
| `C` completion conversion | 6.7616 | 13.90% | [6.2169, 7.2908] |
| `Y` yards per completion | 12.0465 | 24.77% | [11.1955, 12.8862] |

Opportunity (V+S+M) **61.33%**, efficiency (C+Y) **38.67%**.
**`S`, the QB's share of team dropbacks, is the single largest component** —
which is what makes the aggregate-then-allocate policy the right shape, and
also what makes its failure mode (§7) the dominant one.

**Do not equate oracle attribution with recoverability.** A component's oracle
share is what perfect knowledge of it would buy. It says nothing about whether
any estimator can approach that. This is stated as a rule, and it is the reason
none of the shares above appears anywhere as a predictability claim.

---

## 5. Persistence — the hypothesis was TESTED, and it does not hold uniformly

Predeclaration §6 required opportunity-persists-more-than-efficiency to be
tested rather than assumed. Prior-mean against realised, weighted identically
on both sides.

| quantity | kind | n | r |
|---|---|---|---|
| dropbacks | opportunity | 2,494 | **+0.4327** |
| QB share of team dropbacks | opportunity | 2,494 | **+0.3491** |
| sack rate | efficiency | 2,384 | +0.2366 |
| team dropbacks | opportunity | 2,494 | +0.1851 |
| completion rate | efficiency | 2,427 | +0.1850 |
| yards per completion | efficiency | 2,356 | +0.1848 |
| pass TD rate | efficiency | 2,357 | +0.1401 |
| INT rate | efficiency | 2,357 | +0.0662 |

**The blanket statement is false and I am not making it.** The two
*player-level* opportunity measures persist more than every efficiency measure.
But **team dropbacks (+0.1851) persists no better than completion rate
(+0.1850) or yards per completion (+0.1848)** — three effectively identical
numbers. And sack rate, an efficiency measure, out-persists team volume.

What survives: **a quarterback's own workload and his share of it are the most
persistent things here.** Team passing volume is not.

---

## 6. Downstream distributions

Walk-forward, prior-only, 2022–2025, n = 2,494, m = 1,000.

| field | CRPS | MAE | RMSE | bias | r | cov50 | cov80 | cov90 | cov95 |
|---|---|---|---|---|---|---|---|---|---|
| `db` | 6.514 | 9.173 | 12.017 | +1.471 | 0.4330 | 0.553 | 0.828 | 0.913 | 0.950 |
| `att` | 5.936 | 8.389 | 10.909 | +1.375 | 0.4437 | 0.553 | 0.825 | 0.911 | 0.951 |
| `cmp` | 4.062 | 5.752 | 7.374 | +0.885 | 0.4680 | 0.567 | 0.832 | 0.915 | 0.959 |
| `sacks` | 0.927 | 1.363 | 1.717 | +0.022 | 0.2428 | 0.665 | 0.899 | 0.951 | 0.976 |
| `scr` | 0.760 | 1.146 | 1.482 | +0.074 | 0.4610 | 0.747 | 0.924 | 0.961 | 0.982 |
| `pyds` | 48.643 | 69.520 | 87.626 | +12.453 | 0.4467 | 0.545 | 0.826 | 0.914 | 0.961 |
| `ptd` | 0.576 | 0.887 | 1.088 | +0.087 | 0.3078 | 0.801 | 0.960 | 0.984 | 0.994 |
| `int` | 0.414 | 0.694 | 0.837 | +0.030 | **0.0348** | 0.858 | 0.949 | 0.970 | 0.988 |
| `drush` | 0.698 | 1.077 | 1.539 | +0.137 | 0.6280 | 0.794 | 0.922 | 0.963 | 0.979 |
| `rush_opp` | 1.147 | 1.678 | 2.212 | +0.211 | **0.6430** | 0.674 | 0.899 | 0.961 | 0.980 |
| `ryds` | 8.183 | 12.235 | 16.863 | +0.999 | 0.5782 | 0.561 | 0.848 | 0.936 | 0.971 |
| `rtd` | 0.135 | 0.270 | 0.417 | +0.021 | 0.3145 | 0.902 | 0.962 | 0.982 | 0.990 |

`drush` and `scr` are reported separately, as §7 required and the first run did
not do.

**Reading the coverage honestly.** For the continuous-ish fields the intervals
sit close to nominal at 90 and 95. The high `cov50` on `ptd` (0.801), `int`
(0.858) and `rtd` (0.902) is **discreteness, not over-wide intervals**: these
counts are zero in most games, so the distribution has an atom at zero and a
central 50% interval necessarily covers far more than 50%. Recorded in
`KNOWN_LIMITATIONS` so the table is not misread as a calibration defect.

**Interceptions carry essentially no game-level discrimination (r = 0.0348).**
Recorded, not dressed up. It matches the persistence table, where INT rate is
the least persistent quantity measured (+0.0662).

Season by season, passing yards:

| season | CRPS | MAE | bias | r | cov90 |
|---|---|---|---|---|---|
| 2022 | 46.200 | 65.144 | +12.548 | 0.5053 | 0.931 |
| 2023 | 49.831 | 71.785 | +11.353 | 0.4528 | 0.910 |
| 2024 | 49.534 | 70.245 | +11.539 | 0.4118 | 0.904 |
| 2025 | 48.925 | 70.756 | +14.391 | 0.4093 | 0.912 |

Stable across seasons, with a persistent positive bias — explained in §7.

### Subgroups

| subgroup | n | CRPS | bias | r | cov90 |
|---|---|---|---|---|---|
| multi-QB team-game | 699 | 64.735 | **+79.89** | 0.4878 | **0.794** |
| single-QB team-game | 1,795 | 42.377 | −13.81 | 0.2494 | 0.961 |
| established (≥8 games) | 2,150 | 48.100 | +10.80 | 0.4060 | 0.915 |
| low history (<8 games) | 344 | 52.040 | +22.81 | 0.4309 | 0.907 |

---

## 7. The layer's dominant defect, its mechanism, and why it is NOT fixed

The +12.45 overall passing-yards bias is **almost entirely** the multi-QB
subgroup. Mechanism, measured on 2024 over 540 team-games at 200 draws:

| | n | drawn team dropbacks | realised | bias |
|---|---|---|---|---|
| single-QB team-games | 456 | 34.454 | 36.803 | −2.349 |
| multi-QB team-games | 84 | **62.510** | 36.607 | **+25.903** |

Each quarterback is allocated **his own prior-only share** of team dropbacks.
Two quarterbacks who have each historically taken most of their team's
dropbacks sum to nearly two teams' worth. 22.7% of team-games carry more than
one QB with a dropback, so this is not an edge case.

**It is not normalised, and the reason is leakage, not difficulty.**
Normalising shares within a team-game requires knowing which quarterbacks will
appear. The evaluation frame's QB set is built from **realised appearance** (a
dropback actually taken), so dividing by its total would feed the outcome back
into a pregame forecast. The prospective participation source that could supply
it is `CAPTURE_PATH_READY_SOURCE_UNPUBLISHED`, and §3 forbids depth-chart
guesswork as a substitute.

**The over-allocation is the honest price of not leaking.** It is carried in
`qb_accounting.ALLOCATION_RESIDUAL`, emitted as a run warning on every
execution, and its policy line reads *"reported on every run, never clipped and
never smoothed away."*

---

## 8. Whole-chain accounting, per draw

`nfl/production/qb_accounting.py`. Seven identities, asserted on every draw
cell of every evaluated season — 0 violations in 2022, 2023, 2024 and 2025.

**Team level, and the distinction that matters.** The module takes two
different team-rush inputs and treats them differently:

- `team_rush_draws` — a forecast from the carries layer on the **same draw
  indices**. Both sides are pregame, so a QB drawing more rushing
  opportunities than his team drew rushing plays is genuine incoherence →
  **FAIL**.
- `team_rushes_realised` — what the team actually ran. A pregame draw above it
  is forecast error in the right tail. Calling that a defect would be
  **defining a defect against a realised outcome**, which manufactures one for
  any forecaster including a correct one. Reported as a **named diagnostic**,
  never a failure. Measured 2024: 67 of 108,000 draw cells (0.062%) in 7 of
  540 team-games.

**Cross-layer reconciliation is OWED, not passed.** Team passing yards against
player receiving yards, and passing TD against receiving TD, need the receiving
layer's draws on the same indices. It is not in this run, so
`reconcile_cross_layer` returns **DEFERRED** with `owed` naming exactly what it
needs and preserving the documented exceptions: the **lateral exception, 75 of
76 team-games**, and the **one unexplained IND 2022 week 16 play** (13.0
passing against 12.0 receiving, no lateral), which stays visible rather than
folded into the lateral bucket. The DEFERRED state is carried into the
artifact as a debt. It is not reported as satisfied.

The QB1 identity is preserved intact, including the named upstream malformed
play: `dropbacks == pass_attempts + scrambles − spikes`, 80,753 against
80,754, residual **exactly one play** — `2025_03_LA_PHI` play 3600, a blocked
field goal carrying an attempt/scramble flag without a dropback flag. Not
absorbed, not widened. Sacks inside pass attempts 5,308 of 5,308; spikes 278
of 278; passer id on scrambles **0 of 4,091**. The naive form errs by 5,586
plays and is not used anywhere.

---

## 9. Production integration

`nfl/production/qb_v1.py`, spec `qb-v1-aggregate-then-allocate-1`.

The `qb_layer` stage now executes real model logic — it loads its own frame
(`slate()`), hashes it (`artifact_hash()`, sha256
`e2de51d345502a2717a64e584f5e883a64eb3ed51ff97e5f42e406a0ddba0c54`), generates
draws, checks the dropback identity, runs the seven per-draw identities and the
team reconciliation, and attaches its known limitations as warnings. It is not
a dummy dictionary and its spec string is no longer `QB1 BASELINED -- audit
only`.

**Fail-closed behaviour is strengthened, never weakened.** Named refusals:
`STAGE_NOT_IMPLEMENTED` on an empty slate, `QB_SLATE_EMPTY`,
`QB_FRAME_MISSING`, `QB_V1_INCOMPLETE`, `QB_V1_INCOHERENT_DRAWS`,
`QB_V1_RAISED`, `QB_DROPBACK_IDENTITY_VIOLATED`,
`QB_DRAW_ACCOUNTING_VIOLATED`, `QB_ACCOUNTING_INPUT_INCOMPLETE`,
`QB_ACCOUNTING_EMPTY`, `QB_ACCOUNTING_SHAPE_MISMATCH`,
`QB_RUSHES_EXCEED_TEAM_RUSH_DRAWS`. A missing input is BLOCKED, never PASS.

### Two production defects found while wiring it, both fixed

1. **Artifact and hash checks ran AFTER the model.** My first integration put
   the QB branch above them, so a `MODEL_HASH_MISMATCH` would have produced a
   forecast and only then been noticed. Checks now run first, and there is a
   test for it.

2. **A refusal did not halt the pipeline.** Given a player with no `gsis_id`
   the run recorded `IDENTITY_UNRESOLVED` — and then ran the QB model on those
   unresolved players, reconciled, and **sealed an artifact**. Overall status
   was REFUSED so nothing published, but modelling on inputs that failed
   validation and sealing the result is the *"prefer NO FORECAST over an
   unverifiable forecast"* rule being broken. A refusal now halts: every later
   stage is recorded `NOT_APPLICABLE / STAGE_NOT_REACHED` naming what refused,
   the stage count is unchanged so the skip is visible rather than silent, and
   **no artifact is written**.

---

## 10. Live-equivalent historical dry run

    python -m nfl.production.run_forecast \
      --season 2024 --week 8 --game-id 2024_08_SLATE --arm A \
      --written-at 2024-10-27T13:00:00Z --out-dir <dir> \
      --dry-run --fixtures <fixture>

A **complete historical slate**: 16 games, 36 eligible QB-games, 2,000 draws.
Run `16cdc1ec46f7bc9e`, status **SEALED**, all 14 stages PASS, 0 refusals.
Tagged `dry_run: true`, `prospective_eligible: false`.
Publication: **`NFL1_NOT_AUTHORIZED`** on a completely clean run.

### Runtime — the actual draw-generation number, not orchestrator overhead

| | seconds |
|---|---|
| whole run, wall clock | 7.6088 |
| `qb_layer` stage, wall clock | 7.6077 |
| **draw generation alone** | **0.0898** |
| frame load + orchestration inside the stage | 7.5179 |

**Draw generation is 1.2% of the run.** 792,000 draw cells (36 QB-games ×
2,000 draws × 11 fields) in 0.0898s. The other 98.8% is input assembly —
loading the frame and building every player's prior-only history.

**This inverts the obvious assumption and it matters for the next packet.** If
full-slate rehearsal turns out slow, the target is frame loading, not the
Monte Carlo, and **no draw count should be reduced to hit a speed number**.
The 7.5s is also a one-time per-process cost that a full-slate run amortises
across every game, so it should shrink as a share, not grow.

### Reproducibility

Two independent invocations produced the same run id `16cdc1ec46f7bc9e` and
**byte-identical artifacts** (sha256
`bb625b627c381e8df3a01d936c2ef27ca284af402d1df0deded61d246bf99159`). Repeated
`forecast()` calls give bit-identical draws; a different seed gives different
draws, so the determinism test is not vacuous. Per-row RNG seeded on
`[seed, ordinal, player-id bytes]`, so a change to one row cannot shift another.

---

## 11. Adversarial tests and guard-deletion proofs

`nfl/tests/test_qb2_production.py` — **80 checks, 0 failing**, 19 test
functions covering every attack the packet named: sack double counting, spike
double counting (against the real corpus, both directions), scramble double
attribution, impossible TD/INT conversions, missing passer id, QB change,
backup with no history, same-week leakage, current-game outcomes in priors,
passing/receiving yard mismatch, TD mismatch, QB rush against team rush,
incomplete QB player set, empty slate, shape mismatch, model hash mismatch,
missing artifact, unauthorized publication.

**Four guard-deletion proofs**, each run twice — once against the guard, once
with it bypassed, and the second run must let the violation through:

| guard | seeded violation | bypassed → |
|---|---|---|
| `qb_accounting.reconcile_draws` | a TD that is not a completion | flows to SEALED |
| `qb_accounting.reconcile_draws` | designed rushes outside the composed opportunity | flows to SEALED |
| `qb_v1.identity_check` + `reconcile_draws` | sacks outside the dropback budget | flows to SEALED |
| `qb_accounting.reconcile_team` | a QB drawing more rushes than his team drew | flows to SEALED |

Two leakage tests are worth calling out because one of them corrected me:

- **Current-game outcomes in priors.** Mangling *every* realised outcome of the
  game being forecast — yards, completions, attempts, dropbacks, TDs, INTs,
  sacks, scrambles, rush yards, rush opportunities — changes **nothing** in
  that game's own draws. The test also confirms the **oracle** path *does*
  change under the same mangling, so it is not passing vacuously.

- **Same-week leakage.** My first version of this test asserted the wrong
  thing. It compared history length against a naive list prefix and reported 60
  disagreements. Measuring the direction showed `attach` is **stricter in all
  60 cases and laxer in none**: 1,318 player-ordinal pairs carry two rows (a
  mid-week team change), and `bisect_left` correctly excludes same-ordinal
  siblings from each other, while my naive prefix handed the second row its
  same-week sibling. **The frame was right and my test was lax.** Rewritten to
  assert the real property — no history entry at the row's own ordinal or
  later, and none short of its strictly-earlier history — it passes at 0 and 0.

---

## 12. A defect in the measurement system itself

**The repository had no committed test runner**, and the ad-hoc one in use
counted only test functions that *raised*. Every test module reports through a
module-level `check()` that increments a counter and prints — it does not
raise.

**Proven, not assumed.** With one failing check deliberately seeded into
`test_coverage.py`, the old runner still printed:

    TESTS 302  FAILURES 0

That is this project's Class A failure mode — absence of an exception read as
success — occurring **inside the measurement system**, which is worse than a
bad model. The "302 tests, 0 failures" figure quoted in the previous packet's
return was measuring less than it appeared to.

`nfl/tests/run_suite.py` is now committed. It reads each module's own tally, so
a failing check is a failing suite; it refuses a module that ran test functions
and recorded **zero** checks; and it reports failing checks and raises
separately. `test_qb2_production.py` also carries a `test_zz_every_check_passed`
guard so its failures are visible to **any** runner.

### Repository-wide suite, on the honest runner

    modules 31   test functions 322   checks 1897
    FAILING CHECKS 4   RAISED 0
    SUITE FAIL

**Zero failures from QB2 and zero raises anywhere.** All four failing checks
are pre-existing and listed below. The suite is reported FAIL because it is
FAIL; calling it clean would be the same error this section is about.

### What the honest runner immediately exposed

Four **pre-existing failing checks** that were invisible before, none of them
QB2's and none of them fixed here:

| module | failing check |
|---|---|
| `test_coverage` | the refusal naming the source-level report — 2 of 63 targets had their window close with no authorised, in-window, game-attributed capture |
| `test_discharge_identity` | "no window has closed" — one has |
| `test_discharge_identity` | expected DEFERRED, got `FAIL[PERISHABLE_WINDOWS_MISSED]` |
| `test_discharge_identity` | the real future obligation, 61/63 |

These are **real perishable T-90 capture windows that have closed unfilled** as
time passed. They are the availability/T-90 workstream, explicitly outside this
packet's scope and on its DO-NOT list. **I have not loosened a single
assertion to make them green**, and I am not reporting the suite as clean. They
are reported here so the next packet starts from the true state.

One test I did change: `test_production_pipeline` asserted the QB stage spec
contained `BASELINED`, which was the placeholder string this packet replaced.
It now asserts the real `SPEC_VERSION`.

---

## 13. Explicit restatements

- **G0A remains 11/12.** Not touched, not claimed at 12/12.
- **NFL-1 remains NOT AUTHORIZED.** A clean sealed run still returns
  `NFL1_NOT_AUTHORIZED`, and there is a test that it does. No path exists
  where a green suite flips authorization.
- **Nothing is promoted.** `QB_V1_BASELINE_ACCEPTED` is an engineering choice
  of the simplest defensible implementation so the pipeline is not
  structurally incomplete. It carries **no** claim of superiority and is
  revisable without a retraction.
- **All QB2 evidence is EXPLORATORY.** 2022–2025 selected the definitions, the
  policy, the components and this ladder. A confirmatory result needs untouched
  games. Labelled as such in `qb2_results.json`.
- **No 2026 outcomes. No market or sportsbook data. No DFS. No FTN. No
  PFR-restricted fields. No `weekly_rosters.status` as prediction-time
  eligibility. No fuzzy name matching. No parlays. No wager recommended.**
- **The cold-start freeze is unaltered. Prospective arms A/B/C are not
  pooled.**

---

## 14. What is owed, and what I would not do without you

**Owed, named rather than quietly skipped:**

1. **Cross-layer reconciliation** — DEFERRED until the receiving layer's draws
   are in the same run on the same indices.
2. **The multi-QB allocation residual** — unfixable without prospective
   participation, which is `CAPTURE_PATH_READY_SOURCE_UNPUBLISHED`.
3. **Four pre-existing T-90 failing checks** (§12), outside this packet.
4. **`test_zz` tally guards on the other 26 test modules** — the committed
   runner already surfaces them, so this is belt-and-braces; it touches 26
   files and I did not do it inside a packet that says stop.

**I would not, without you:** normalise QB shares (it would leak), widen the
lateral exception, register the QB frame as a prospective capture source, or
reduce draw counts for speed.

---

## 15. Next

The packet's stated follow-up is a **full-slate production rehearsal**, not
another research branch. On this evidence that is the right call, and §10 says
where its cost actually lies: **input assembly, not Monte Carlo.**

**STOPPING HERE as instructed.**

---

### Files

| path | what |
|---|---|
| `nfl/research/qb2/predeclaration_qb2.md` | pre-registration, unchanged |
| `nfl/research/qb2/addendum_qb2_coherence.md` | the three defects, recorded before the corrected run |
| `nfl/research/qb2/build_qb.py` | frame build on the binding QB1 identity |
| `nfl/research/qb2/qb2_lib.py` | frame, ladder, simulator |
| `nfl/research/qb2/run_qb2.py` | decomposition, ladder, persistence, distributions |
| `nfl/research/qb2/qb2_results.json` | every number in this return |
| `nfl/production/qb_v1.py` | the V1 layer, limitations, frame hash, slate loader |
| `nfl/production/qb_accounting.py` | seven per-draw identities, named residual, cross-layer |
| `nfl/production/run_forecast.py` | QB stage executes real model logic |
| `nfl/production/pipeline.py` | halt on refusal; stage metrics |
| `nfl/tests/test_qb2_production.py` | 80 checks, 4 guard-deletion proofs |
| `nfl/tests/run_suite.py` | the committed runner |
