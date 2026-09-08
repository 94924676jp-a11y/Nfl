# NFL OVERNIGHT RETURN

## Executive state

| | |
|---|---|
| Canonical repo | `94924676jp-a11y/Nfl` (remote normalised from `/nfl`) |
| Canonical HEAD | `e2e046a` |
| Start HEAD | `bff9fe7` |
| Commits created | **7** (plus 2 append-only vintage captures by the runner, preserved) |
| Full suite | **23 modules, 1,425 assertions, 0 failed, 0 non-zero exits** |
| G0A | **11/12 — unchanged** |
| NFL-1 | **NOT AUTHORIZED — untouched** |
| T−90 readiness | **READY_FOR_REAL_WINDOW** (50/50 items, 0 blocked) |

All five authorised stages completed. Stage 4 was gated on Stage 2 and was
authorised by it. No stage was skipped and no gate was weakened.

---

## Stage 1 — Reproducibility

**`panel_enriched.pkl`**
- status: **EXACT_REPRODUCIBLE**
- hash: `7bbc8cb255dc0c0e9545f3ffb01bfe9b7416aecd3707f70dcf420c43f74c50e9` — matches the directive's expected value
- generation: `nfl/research/repro/regenerate.py`, byte-identical, 33s
- remaining debt: its thirteen leaf CSVs are hash-pinned inputs, not themselves rebuilt from raw nflverse. That is the declared cut.

**`volume_store.npy`**
- status: **EXACT_REPRODUCIBLE**
- hash: `c47a52903bb038cec0088f243fb431623c4c8a093a62020e8e3f11caf7633365` — matches
- generation: same mechanism; depends on exactly one leaf, `denom_panel.csv`
- remaining debt: as above.

Because both regenerate byte-for-byte, **the binaries are not committed**. What
is committed is the smaller and more auditable artifact: the 13 leaf CSVs
(28MB raw, **3.3MB gzipped**) under `nfl/research/inputs/`, matching this
repository's existing convention for durable evidence. The generation code was
already here. This is the failure the sibling MLB project did not survive — its
`v7/corpus` was never committed and its M0 baseline is permanently
non-reproducible.

**ABC_MPR identity gate**: built and enforced. A run may claim
`ABC_MPR PROSPECTIVE CONFIRMATION` only on a full match of leaf inputs, derived
artifacts, source hashes, row ordering, dtypes, seeds, draw protocol, solver
settings and feature set. Anything else returns `DIFFERENT_INPUT_GENERATION`. A
run that consumed 2026 outcomes is **refused outright**, not relabelled. An
undeclared component is refused — silence is not agreement.

**Remote normalization**: done, `origin` now points at `.../Nfl`.

**Path C state registry**: `nfl/research/PATH_C_STATE.json`, registering every
subsystem the directive listed, plus the 2024 RB1↔RB2 anomaly as open question
`OQ-2024-RB1RB2` with its reopen conditions. Not researched tonight.

---

## Stage 2 — Participation adequacy

**Fields audited**: 9, each with the fourteen required attributes —
`offense_players`, derived `pass_snaps`, `route`, true routes run,
`offense_snaps`/`offense_pct`, formation/personnel, NGS receiving,
`weekly_rosters.status`, present-week depth chart.

**True routes available?** **NO.** The nflverse `route` column is the *targeted
receiver's* route classification, present on 36–42% of plays. It is not routes
run per player and is not called that anywhere. Routes run are not manufactured.

**Best defensible participation representation**: pass-snap participation —
plays with the player on the field during a dropback, over team dropbacks. It is
an **upper bound** on route participation, because a player on the field for a
dropback may block.

**Chronology status**: lawful as prior-game history only. Masking audit CLEAN at
four ordinals.

**Coverage**: `offense_players` on 91.4% of plays 2020–2022 and 100.0%
2023–2025; the derived representation on **99.807%** of appeared WR/TE/RB
player-games, minimum season. Real zeros distinguished from not-applicable.

**Baseline results** (next-game, walk-forward, appeared rows):

| position | best | pooled MAE | vs position mean | r | sd ratio |
|---|---|---|---|---|---|
| WR | EWMA hl2 | 0.1423 | **−52.1%** | 0.795 | 0.868 |
| TE | EWMA hl2 | 0.1181 | **−54.2%** | 0.836 | 0.897 |
| RB | EWMA hl2 | 0.1196 | **−42.9%** | 0.772 | 0.854 |

**Role-change results**: worst cohort everywhere, and never catastrophic — WR
1.34×, TE 1.29×, RB 1.19× pooled MAE against a 2.5× limit.

**Calibration**: point forecasts only at this stage; discrimination and spread
reported instead (r and sd ratio above).

**Adequacy pre-rule**: PA-1 skill ≥10% in ≥3/4 seasons for WR and TE; PA-2
r ≥ 0.70 and sd ratio ≥ 0.50; PA-3 no cohort above 2.5× pooled MAE; PA-4
coverage ≥ 90% with zero distinguishable from N/A; PA-5 masking audit clean.
Fixed before any comparative result existed.

**FINAL ADEQUACY STATE: `ADEQUATE_FOR_TARGET_DECOMPOSITION`** — all five pass.

Carried forward as a **mandatory labelling constraint**: the participation
component is pass-snap participation, not routes run; Stage 4 may conclude
nothing about the value of route information as such; and the gap between the
two is directional but **unbounded in magnitude** from available data, and is
not assumed to be small.

---

## Stage 3 — Joint diagnostic scaffold

**Implemented**: `nfl/research/s3/`. A `JointDraws` schema, a three-block
diagnostic battery, and a builder that assembles the accepted P4C system C for
carries, targets and snaps without improving any of them.

**Pre/post reconciliation**: reported side by side for every quantity, and it
earned itself on the first run.

| class | pre-reconciliation group sum over physical max | peak | post | realised max |
|---|---|---|---|---|
| carries | 27.7% of draws | 3.22× | ~0% | 1.000 |
| targets | 54–57% of draws | 2.77× | ~0% | 1.000 |
| snaps | 42–43% of draws | 2.17× | 6.8% | 5.013 |

None of that is visible in a post-only report. Reconciliation also **introduces**
individual cap violations (0.64–0.75% where pre had none) and makes marginal
calibration **worse** in every cell — randomised PIT 82.0 → 111.5 for snaps 2024.
Accounting coherence is being bought with calibration; a single combined score
would have reported an improvement.

**Physical invariant tests**: non-negativity, individual caps, boolean
appearance, team volume shared within a team-game, no allocation to a
non-appearing draw. The group-sum-versus-physics check is a **measurement, not
an assertion**, because the accepted model violates it and Stage 3 is forbidden
to fix a marginal.

**Marginal preservation**: draws carry a hashed marginal identity; a swap
changes the identity *and* the pre-reconciliation numbers, so it cannot hide
behind the normaliser.

**Dependence diagnostics**: matched-estimand posterior predictive checks on
rank pairs, same-position pairs, cross-position pairs and top1↔remainder, plus
concentration and entropy.

**New defects discovered** — 21 flags, none rejected or promoted:
1. Pre-reconciliation physical incoherence in all three classes (above).
2. Reconciliation introduces impossible individual shares in snaps.
3. Reconciliation degrades marginal PIT in every cell measured.
4. **Cross-position dependence is real and unmodelled**: realised WR1↔RB1 snap
   correlation +0.142 and TE1↔RB1 +0.104 against model bands centred on zero.
5. The carries/2024 rank1↔rank2 anomaly (−0.667) reproduces here independently.

---

## Stage 4 — Target oracle decomposition

**AUTHORIZED: YES** — Stage 2 returned `ADEQUATE_FOR_TARGET_DECOMPOSITION`.

**Baseline reproduction**: all-projected corner equals `p4c_results.json`
targets system C at **|diff| 0.00e+00** in all four seasons, through Rule 006 at
tolerance 0.0.

**All-oracle reproduction**: **5.17e-08** against a pre-declared 1e-4.

**Oracle opportunity** (pooled Shapley share of total CRPS reduction, 2⁴
factorial, season range in brackets):

| component | share | range | opportunity | recoverability |
|---|---|---|---|---|
| **R** allocation given participation | **46.0%** | [43.9, 48.0] | **LARGE** | **UNTESTED** |
| **P** participation | 28.5% | [27.6, 30.2] | MEDIUM | ONE_NARROW_TEST |
| **T** team passing volume | 13.8% | [13.2, 14.5] | MEDIUM | MULTIPLE_INDEPENDENT_TESTS |
| **A** appearance | 11.7% | [9.9, 14.6] | MEDIUM | MULTIPLE_INDEPENDENT_TESTS |

**Interactions**: reported per season on the reduction scale in
`s4_results.json`.

The split is not cosmetic. P and R together are 74.5% of total error and more
than a third of that is participation; participation alone is twice team
passing volume. An unsplit target-share model cannot tell them apart.

Cohorts locate the components: appearance dominates for fringe players (0.173 of
a 0.473 baseline at p_app 0.25–0.50) and nearly vanishes for locked-in starters;
R dominates for starters (0.501 of 1.583 at p_app ≥ 0.95).

**Recommended next research target**: **INVEST in R**, target rate conditional
on participation. **Reason**: it is the only LARGE component and the only
UNTESTED one — 46% of target error sits in a quantity this project has never
modelled. Second: **CHEAP_PROBE on P** (MEDIUM, one narrow test behind it).
**HOLD** on T and A, both already carrying multiple independent tests.

**NO FEATURE LADDER EXECUTED: confirmed.** And oracle opportunity is not
recoverability — R being LARGE and UNTESTED makes it the best *question*, not a
known opportunity. It may prove information-constrained the way appearance did.

---

## Stage 5 — T−90

**Target**: NE @ SEA.
**Window**: Sep 9 18:50–20:10 ET (2026-09-09 22:50Z → 2026-09-10 00:10Z).
**Readiness**: **READY** — 50 items, 50 READY, 0 PARTIAL, 0 BLOCKED.

Three cron lines cover exactly that window; 16 firing opportunities at a
5-minute step. Target identity complete: game_id, kind, window bounds, kickoff
carried on the target, cadence flag, 9-field serialisation. Season and week are
carried by the game_id and the per-week plan rather than as separate fields —
recorded as the design it is.

Discharge semantics hold against every way timing could be mistaken for
attribution: another game, no declared target, wrong kind, one minute early, one
minute late — none discharges. Only the anchored workflow on a schedule event
discharges; a sweep, an unknown workflow, a **manual dispatch of the anchored
workflow itself**, and a local run all do not. Exactly one source
(`official_inactives`) may discharge inactives; the other seven are refused.

Evidence integrity: 372 capture rows carry a raw sha256, the last 60 blob paths
all resolve, all five clocks are present and separate, `requested_at` is
recorded apart from the source clock, and a cache hit records
`content_unchanged` rather than manufacturing a retrieval time.

**Blocking defects**: none.
**Repairs**: none needed to the capture machinery. Three false blockers in my
own audit script were found and fixed (it read `REG.SOURCES` when the attribute
is `BY_NAME`; passed `event` to `declaration_basis`, which reads `event_name`
and `is_github_actions`; and looked for a `path` key when the field is `blob`).
Each would have reported a defect that does not exist.
**Tests**: no regression from tonight's work — `test_t90_workflow` 41,
`test_discharge_identity` 50, `test_coverage` 52, `test_execution_target` 84,
`test_capture_schedule` 99, all 0 failed.

**G0A remains 11/12.** No real qualifying capture has occurred; this audit used
non-dischargeable test targets throughout and cannot satisfy Item 1. NFL-1 is
not self-authorized.

---

## Scientific negatives

1. **Pre-reconciliation, the accepted marginals are not physically legal** —
   27.7% (carries), 54–57% (targets) and 42–43% (snaps) of draws exceed the
   physical maximum, peaking at 3.22×.
2. **Reconciliation degrades marginal calibration in every cell measured** and
   introduces individual cap violations in snaps where none existed.
3. **Cross-position dependence is real and the models produce none** — realised
   WR1↔RB1 +0.142, TE1↔RB1 +0.104 against bands centred on zero.
4. **True routes run are not available** and cannot be recovered from any source
   in this project.
5. **The participation proxy gap is unbounded** — directional (pass snaps ≥
   routes), magnitude unknowable from available data.
6. **`position_mean` is worthless for participation** (r ≈ 0.00–0.01,
   R² ≈ 0), which is why the ≥10% skill bar was cleared so widely: the trivial
   baseline is not merely weak, it is uninformative.
7. **The zero/N-A conflation has almost nothing to bite on** — forcing it into
   the participation history moves MAE by 0.1%, because coverage among appeared
   rows is near-total.
8. **Eight Stage 2 adversarial probes could not fire** and are UNRESOLVED.

---

## Unresolved

- 8 Stage 2 adversarial probes UNRESOLVED (leaked field on a different scale to
  the estimand; the blend degrades rather than improves).
- The Stage 2 identifier-leakage probe cannot fire — a bare identifier carries no
  participation signal. Reported UNRESOLVED, not PASS.
- P4F's GD-B and GD4 remain UNRESOLVED from the previous session; not revisited
  tonight.
- `OQ-2024-RB1RB2` registered, not researched, per directive.
- Leaf inputs are hash-pinned but not themselves rebuilt from raw nflverse.
- `route` semantics beyond "targeted receiver's route" are not audited; ESPN and
  NGS material remains outside Stage 2's usable set.

---

## Guard deletion proofs

| guard | deletion | effect | verdict |
|---|---|---|---|
| S1 `FORBIDDEN_SEASONS` | emptied | a 2026-consuming run claims the frozen label | **PASS** |
| S1 identity comparator | stubbed empty | an altered generation claims the frozen label | **PASS** |
| S1 leaf hash checks (both) | stubbed | a truncated leaf reaches the build | **PASS** |
| S1 archive hash only | stubbed | content check still catches it (defence in depth) | **PASS** |
| S1 descriptor completeness | emptied | incomplete descriptor relabelled, not confirmed | **UNRESOLVED — precision guard, reported as such** |
| S2 strictly-earlier-ordinal cut | removed | 625 rows' history changes; 1,318 same-week duplicate player-ordinals | **PASS** |
| S2 appeared-only history filter | removed | MAE degrades 12.6% | **PASS** |
| S3 `FORBIDDEN_USES` | emptied | a DFS purpose is accepted | **PASS** |
| S3 pre/post stage argument | ignored | the pre-reconciliation defect vanishes from the report | **PASS** |

---

## Canonical commits

| SHA | purpose | tests |
|---|---|---|
| `0b8b5d1` | Stage 1 — reproducibility closure, identity gate, Path C registry | 63 new; suite 1,425 |
| `909385b` | Stage 2 pre-declaration | — |
| `de3b127` | Stage 2 — participation adequacy | 14 probes, 2 guard deletions |
| `bd8c828` | Stage 3 — joint diagnostic scaffold | 53 |
| `72d3869` | Stage 4 pre-declaration | — |
| `9d4f293` | Stage 4 — target oracle decomposition | 2 identity gates |
| `e2e046a` | Stage 5 — T−90 readiness | 50 audit items |

Two append-only vintage-capture commits by `nfl-capture[bot]` (`2b8429a`,
`94e5dc7`) landed between mine and were preserved through rebase. **Every one of
my seven commits touches zero `nfl_vintage/` and zero `nfl/vintage/` paths**,
verified per commit.

## Full-suite result

| | |
|---|---|
| modules | 23 |
| assertions | 1,425 |
| passed | **1,425** |
| failed | **0** |

Plus, outside the suite: P4F mechanistic 66/0; Stage 3 scaffold 53/0 (after
staging the derived artifacts via `regenerate.py --emit`, which is now a named
`BLOCKED(cause=DEPENDENCY)` state rather than a crash when they are absent).

## Forbidden-input audit

Method: AST scan of all 14 files changed tonight, checking **data access** —
row subscripts, `.get()` keys, file opens and season comparisons — not mere
mentions.

| | |
|---|---|
| 2026 outcomes | **ABSENT** — zero comparisons against season 2026 anywhere |
| markets | **ABSENT** — no market field read; the only occurrences are Stage 3's refusal list |
| DFS | **ABSENT** — same, the `FORBIDDEN_USES` tuple and its tests |
| `weekly_rosters.status` | **ABSENT from every study path** — the only occurrence is the Stage 2 inventory entry declaring it forbidden |
| present-week depth charts | **ABSENT** |
| observed weather | **ABSENT** |
| future information | **ABSENT** |
| fuzzy matching | **ABSENT** |

Two forbidden-field reads exist in the whole night's code, both at
`run_s2_adv.py:109–110`, constructing the seeded `LEAK_status` probe. Verified
contained: `f_inj_status` and `LEAK_` appear **0 times** in `s2_lib.py`,
`run_s2.py` and `run_s2_verdict.py`. Every file opened by tonight's code is a
JSON artifact of this project's own making.

## FINAL STATE

| | |
|---|---|
| **P4C SYSTEM C** | ACCEPTED / UNCHANGED |
| **ABC_MPR** | FROZEN PROSPECTIVE CANDIDATE / NOT PROMOTED |
| **MPR_ONLY** | REJECTED |
| **G0A** | **11/12** — no real qualifying capture has occurred |
| **NFL-1** | **NOT AUTHORIZED** |

## NEXT OWNER DECISION REQUIRED

**Authorise a pre-registration for R — target rate conditional on
participation — or decline it.**

It is the single highest-value decision because it is the only place tonight
found a LARGE oracle opportunity that nobody has ever tested: 46.0% of target
error, stable across all four seasons, in a quantity this project has never
modelled. Everything else the queue touched is either already characterised (T,
A), had exactly one narrow test tonight (P), or is infrastructure now closed
(Stage 1).

The decision is not obvious and that is why it is yours. Appearance looked like
a large opportunity too and turned out to be information-constrained; R may go
the same way. What makes it worth asking now is that Stage 4 measured it under a
decomposition whose two validity identities both hold exactly, so the 46% is not
an artefact of how the question was posed.

Second, and much cheaper: Stage 3 raised 21 flags against accepted marginals,
including **pre-reconciliation physical incoherence in every class**. None is
actionable without your say-so, since a scaffold may flag but not decide.
