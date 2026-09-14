# R4 — counts, the stat contract, and explicit rush category ownership

**Owner:** R4 (engine). **Repo** `/home/user/nfl`, branch
`claude/nfl-greenfield-architecture-stsxmk`, parent HEAD `2dc44ab`.
**Interpreter** `python3.12`. Written 2026-09-14, kickoff 2026-09-15T00:15:00Z.

Three repairs were asked for. All three are done, all three are measured, and
every number below was re-derived on this tree rather than copied from the
brief. Where my re-derivation differs from a figure I was given, mine is
printed and the difference is named.

**`nfl/production/nonqb/layers.py` is unchanged.**
`sha256 481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`,
sha16 `481f005f682cd721`, verified at the start of this work and again at the
end. Q9's frozen candidate identity is not disturbed; both repairs that would
naturally have been written into that module are at the engine call site
instead, which is where C1 and the appearance team-scope repair already live
for the same reason.

---

## 0. What changed, in files

| file | state | what |
|---|---|---|
| `nfl/production/stat_contract.py` | **NEW** | the versioned contract: the play taxonomy, the identities, the two false friends, count support, and `deal_counts` |
| `nfl/tests/test_stat_contract.py` | **NEW** | 15 test functions, 94 checks, `SUITE PASS` |
| `nfl/production/nonqb/football_engine.py` | modified | counts are dealt not multiplied; the ownership ledger; the two new final-value gates |
| `nfl/production/nonqb/rushing_a1.py` | modified | `ownership_ledger` and `_dist` appended; **nothing in `allocate`, `_partition`, `_shares` or `verify_allocation` was touched** |
| `nfl/production/run_forecast.py` | modified, **NOT mine exclusively** | hands A1's whole partition to the engine, seals two new draw layers, maps four new engine layers to their reporting stage |

`run_forecast.py` is in neither my exclusive-ownership list nor the do-not-touch
list. I edited it because "seal the full category matrix" cannot be done from
inside the engine — `_draws()` is where `ds.add_layer` is called — and because a
new `g['layers']` key raises `ENGINE_LAYER_NOT_REPORTED` until `STAGE_LAYERS`
answers for it. The change is four additive hunks and no existing line was
removed. **Flagging it for reconciliation at integration.**

---

## 1. COUNTS MUST BE COUNTS

### 1.1 The defect, re-measured

Over the 102 sealed runs under `nfl/research/live/2026_01_*`:

| array | non-integer cells | total | share |
|---|--:|--:|--:|
| `rushing/carries` | **243,766** | 384,000 | **63.48%** |
| `qb/*` counts, `receiving/*` counts | 0 | — | 0% |
| `team_volume/team_carries` (a LEVEL, not a count) | 251,142 | 256,000 | 98.10% |

The brief's figure was 241,584 / 381,000 (63.4%). Mine is 243,766 / 384,000
(63.48%) on the frame `2026_01_*/*/*/player_draws.npz`, 258 rushing rows across
102 runs. Same magnitude, same conclusion; the small gap is a frame difference
and I have quoted the one I can reproduce.

Tonight's previous sealed board `f91342d6787a66a1`, per running back:

| gsis_id | mean | non-integer cells |
|---|--:|--:|
| 00-0038134 | 10.9183 | **795 / 1000** |
| 00-0040078 | 3.3137 | 604 / 1000 |
| 00-0041013 | 5.2873 | 783 / 1000 |

795/1000 reproduces the brief exactly.

It was never only a display problem. `nfl/product/metrics.py` declares
`('rushing','carries')` `kind: 'count'` and `render.py` formats counts `:.0f`,
so a 10.4183 printed as "10"; **and** `layers.rushing_td` draws its touchdown
binomial on `rint(C)`. The sealed carry column and the denominator the
touchdown layer used were already two different numbers before any threshold
reader arrived.

### 1.2 The method — generated as counts, inside the draw

`C = share x budget` is gone. In its place, per team, per draw:

```
(C_1, ..., C_k, C_other) ~ Multinomial(budget, (s_1, ..., s_k, other_share))
```

* The probability vector **is** the simplex `layers.targets_carries` produced.
  Receiver and back competition is untouched; only the support changes.
* `E[C_i] = budget x s_i` — exactly the continuous product it replaces, so no
  mass moves on average and nothing is fitted.
* `sum_i C_i + C_other == budget`, exactly, in integers, in every draw.
* This is not a new mechanism. It is `shared_pass.deal_targets`, which XL1 C3
  has used for targets since it was written, generalised as
  `stat_contract.deal_counts` and given a name that says what it does.

**One rounding exists and it is declared.** A multinomial has no meaning on a
fractional budget, and D1's team levels are continuous by design. Where the
budget is a level rather than an already-integer A1 category, it goes through
`stat_contract.integerise_level`, which accepts only `round_half_even` — the
same convention `rushing_a1.allocate` already requires its caller to declare —
and reports the cells it moved and the mean shift it caused.
`deal_counts` itself **refuses** a fractional budget rather than rounding one:
turning a level into a count is the level owner's decision.

Nothing is clipped, no survivor is renormalised, no draw is deleted, and no
mean is rounded anywhere.

### 1.3 Effect on every closure identity — stated one by one

Measured on tonight's re-run (§3), and on the seeded tests in
`test_stat_contract.py`.

| identity | owner | before | after |
|---|---|---|---|
| `sum_i share_i + other_share == 1` (carry simplex) | `accounting.reconcile_rushing` | exact | **exact, untouched** — the deal reads the shares and does not write them |
| `sum_i share_i + other_share == 1` (target simplex) | `accounting.reconcile_nonqb` | exact | **exact, untouched** |
| `sum_i C_i + C_other == rb budget` | nobody — did not exist | not checkable | **exact in every draw, and now checked**; KC 0/1000 violating cells |
| `sum_i T_i + other == targeted budget` | C3, `football_engine` | exact under C3 only | exact under C3 **and now under B0 too**, by the same construction |
| opportunity identity in `reconcile_nonqb` | `accounting` | share form under B0, exact-count form under C3 | **exact-count form on every configuration** — the stricter of the two |
| `rushing_td <= carries` | `accounting.reconcile_rushing` | held against `rint(C)`, which was not the sealed C | **holds against the sealed C, because they are now the same array**; 0 violating cells |
| `receptions <= targets` | `accounting.reconcile_nonqb` | held | holds, 0 cells |
| `sum receptions == sum cmp` (C3) | `football_engine` final gate | exact | **exact, 0.0 max deviation** |
| `sum receiving_yards == sum pyds` (C3) | same | exact to float | exact, max deviation 1.14e-13 |
| `sum receiving_td == sum ptd` (C3) | same | exact | **exact, 0.0** |
| `cmp <= att`, `ptd <= cmp` | `qb_v1.identity_check` | exact | exact, 0 cells |
| `db == att + sacks + scr` | `qb_v1` + now the contract | exact | **exact — see §4** |
| A1 `team_carries - scr == sum(6 categories)` | `rushing_a1.verify_allocation` | exact | **exact, and now visible in the artifact** |

**The one thing that does change, and it is not cosmetic.** The dealt count has
*more* spread than the continuous product, by exactly the multinomial term
`budget x p x (1-p)` that a share-times-level product silently omitted. That
dispersion is a real property of dealing a finite number of carries to a finite
number of backs; it was missing, not absent. `test_stat_contract` asserts both
halves at 40,000 draws: the mean agrees with `share x budget` to within 0.05,
the sd is strictly larger, and it matches `sqrt(n p (1-p))` to within 2%. Any
threshold probability computed off the old column was computed off a
distribution that was too narrow *and* off the wrong support.

### 1.4 What the engine now refuses

Two new final-value gates, placed **after the last write** to the arrays that
seal — the same placement discipline that the C3 credit gate exists to enforce,
because `QB_DRAW_ACCOUNTING_HOLDS` was stamped on 101 artifacts by checking an
intermediate value.

* `counts_are_counts` — `stat_contract.assert_counts_are_counts` over all
  fourteen declared count metrics on the returned arrays. It **asserts**; it
  rounds nothing. A non-integer or negative declared count halts the run with
  `COUNT_SUPPORT_VIOLATED` naming the metric and the cell count.
* `stat_contract` — the dropback identity, re-checked through the versioned
  contract so the artifact carries the contract version beside the number.

---

## 2. ONE VERSIONED PASSING STAT CONTRACT

`nfl/production/stat_contract.py`, `CONTRACT_VERSION = 'nfl-stat-contract-1'`.

### 2.1 The taxonomy, defined as predicates and measured on real plays

Six mutually exclusive classes over nflverse play-by-play flags. Every term
carries its predicate, the id field that attributes it, and whether it is a
dropback.

| term | predicate | attributed to | dropback? |
|---|---|---|---|
| **official pass attempt** (board `qb/att`) | `pass_attempt & !sack & !qb_spike` | `passer_player_id` | yes |
| **sack** | `pass_attempt & sack` | `passer_player_id` | yes |
| **spike** | `pass_attempt & qb_spike` | `passer_player_id` | **no** |
| **scramble** | `rush_attempt & qb_scramble` | `rusher_player_id` | yes |
| **kneel** | `rush_attempt & qb_kneel` | `rusher_player_id` | no |
| **designed rush** | `rush_attempt & !qb_scramble & !qb_kneel` | `rusher_player_id` | no |

Aggregates, each a declared sum of classes:
`att_raw = att + sacks + spikes` · `dropbacks = att + sacks + scrambles` ·
`rush_attempts = scrambles + kneels + designed`.

**Measured** over all six pbp corpora in `nfl/research/postgame/`
(`pbp_2021`–`pbp_2026`), REG only, two-point attempts and `no_play` excluded,
`posteam` non-empty — **211,755 plays**:

| quantity | count |
|---|--:|
| `att_raw` (nflverse `pass_attempt`) | 97,696 |
| official attempts | 90,748 |
| sacks | 6,601 |
| spikes | 347 |
| scrambles | 5,054 |
| kneels | 2,104 |
| designed rushes | 66,657 |
| **dropbacks** | **102,403** |

`att_raw − att = 6,948 = sacks + spikes`, exactly. All three identities hold as
exact integer sums. **Zero** plays carry two classes: none is both a pass
attempt and a rush attempt, none is both a sack and a spike, none is both a
scramble and a kneel, and no event flag appears without its play flag. Every
one of those is a fenced assertion in `test_stat_contract.py`, so a feed whose
flags change meaning fails there rather than quietly moving a band.

`classify_play` **refuses** an impossible row by name rather than choosing
between two classes for it.

### 2.2 The two false friends, refused by code

**`panel_p3.dropbacks_as_passer` is not a dropback column.** Re-derived on
`nfl/research/inputs/panel_p3.csv.gz`: it equals `pass_att_as_passer` in
**57,670 of 57,670 rows** — the brief's figure exactly. Scrambles are charged to
the rusher so none ever reaches the passer's column, and sacks are already
inside `pass_attempt`; the leaf carries no true dropback column and a band built
on it is `att_raw` twice. `assert_not_a_dropback_column` is handed the real
column in the test suite and must return
`FAIL[DROPBACK_COLUMN_IS_ATT_RAW]`. The guard is also shown to **pass** a
genuinely different column, because a refusal that refuses everything is a
constant, not a guard.

**nflverse `pass_attempt` is not the board's `qb/att`.** The gap is 2.4356 per
QB1 team-game (`nfl/research/refbands/REFERENCE_BANDS.json`, n=2,174:
`att_raw` mean 35.0018 against `attempts` 32.5662). Under the two definitions
tonight's Bo Nix places at the 39.8th and the 51.6th percentile of the same
band and Patrick Mahomes at the 49.1st and the 60.9th — 11.8 points of pure
vocabulary in both cases.

### 2.3 What "versioned" buys

`CONTRACT_VERSION` travels with every outcome the module emits and is written
into `g['stat_contract']` on every run alongside the identity, its max absolute
deviation, the cell count, the predicate for `att`, and the names of both false
friends. "Which definition of attempts was that" is now answerable from the
artifact instead of from memory. Training, simulation, reference bands and
scoring can all address one module; nothing in it is fitted and nothing in it
repairs.

**The two count registries are reconciled, not duplicated.**
`nfl/product/metrics.py` is R5's and holds `kind: 'count'` for the product
layer; production declares `COUNT_METRICS` for itself.
`reconcile_with_product_registry` asserts the two name one set, and the test
calls it. A divergence is a failing test rather than two quiet answers to one
question — and production keeps no import of the product layer, so the layering
stays the right way round.

---

## 3. EXPLICIT RUSH CATEGORY OWNERSHIP

### 3.1 What was wrong, and it was never missing information

`rushing_a1.allocate` partitions the rush-play budget across six categories
with **one multinomial per team per draw**, so every carry already had exactly
one owner in every draw. `run_forecast` then filtered that to
`a1.value['carries'][(t, 'rb')]` and discarded the other five. D6 measured the
consequence from the outside; I re-derived it on this tree over the 102 sealed
runs:

* **67 team-runs** with a rushing layer.
* Unowned share `team_carries − (named RBs + QB rush opportunity)`:
  **frame mean 24.10%**, min **0.62%**, max **45.29%**.
* **All 67** change sign.
* **6,651 of 95,000 draws** deal *more* carries than the team's level.

(D6 reported 6,650; mine is 6,651 on a strict `< 0` test. Everything else
reproduces to four decimals.)

### 3.2 The repair

* `rushing_a1.ownership_ledger` composes team rush opportunity → category
  allocation → player allocation → named pools, per team, per draw. It reads;
  it writes nothing, rescales nothing and repairs nothing.
* `run_forecast` hands the engine `a1.value['carries']` **entire**.
* `football_engine` builds the ledger over **both clubs**, not only the ones the
  appearance layer ran for — the category partition needs the carry level and
  the scramble draw and nothing else, and omitting a deferred team would leave
  the club whose evidence is thinnest as the one with no rush ownership record
  at all.
* Two new sealed draw layers, both row-axis `team`:
  * `rush_category` — `kneel`, `designed_qb`, `rb`, `wr`, `te`, `fringe`.
  * `rush_player_pool` — `unmodelled_back_pool`, the part of the `rb` category
    the player deal gave to backs outside the modelled set. It is a **separate
    layer** because it exists only for a team whose appearance layer ran; a zero
    in a shared matrix would read as "no unmodelled backs" when the truth is
    "no player split was made".

**Two closures, kept separate, because they are different questions.** The A1
closure (`team_carries == scrambles + the six categories`) is exact for every
team whether or not any player layer ran. The player closure (`rb == named
backs + unmodelled pool`) is only askable of a team that has one. Collapsing
them would report an `APPEARANCE_TEAM_DEFERRED` deferral as a conservation
defect. `ownership_ledger` **FAILS** on either — a residual there is a wrong
level or a wrong draw index, not unowned mass.

Every residual leaves the module as a distribution — mean, sd, p05/p50/p95, min,
max, draws negative, draws positive, `sign_changes` — never as a scalar. D6's
lesson in one function: a mean alone ranks boards close to backwards.

### 3.3 Tonight's attributed rush ownership, both teams

Re-run of `2026_01_DEN_KC`, 1,000 draws, seed 20260908, `V1_CANDIDATE_R8`,
`written_at 2026-09-14T17:40:19Z`, sealed `c0440864f21198fc`. **See §6 for why
this is not a byte-replay of `f91342d6787a66a1`.**

**DEN** — team carries (integerised level) mean **27.5320**

| owner | mean | share |
|---|--:|--:|
| scrambles (QB, dropback-owned) | 2.4500 | 8.90% |
| kneel | 1.1650 | 4.23% |
| designed_qb | 2.2810 | 8.28% |
| **rb** | **20.6900** | **75.15%** |
| wr | 0.8170 | 2.97% |
| te | 0.0660 | 0.24% |
| fringe | 0.0630 | 0.23% |

`rb` split: **none** — Denver is `APPEARANCE_TEAM_DEFERRED`, so the category is
attributed and the players are not. Stated, not zeroed.

**KC** — team carries (integerised level) mean **25.1720**

| owner | mean | share |
|---|--:|--:|
| scrambles (QB, dropback-owned) | 3.3060 | 13.13% |
| kneel | 0.3890 | 1.55% |
| designed_qb | 0.7200 | 2.86% |
| **rb** | **19.8640** | **78.91%** |
| wr | 0.7670 | 3.05% |
| te | 0.0480 | 0.19% |
| fringe | 0.0780 | 0.31% |

`rb` split: named backs 19.4940 + unmodelled-back pool 0.3700 = 19.8640.
**Player-closure violating cells: 0 / 1000.**

| back | mean | sd | integer cells |
|---|--:|--:|--:|
| 00-0038134 | 8.2330 | 6.9194 | 1000 / 1000 |
| 00-0040078 | 3.0340 | 4.0815 | 1000 / 1000 |
| 00-0041013 | 8.2270 | 6.3929 | 1000 / 1000 |

### 3.4 Before and after on the 24.1%

| quantity | DEN | KC |
|---|--:|--:|
| unowned **before** (what the old artifact exposed), mean | 22.8010 | 1.6520 |
| — as a share of the team's carries | **82.82%** | **6.56%** |
| — sd / range / draws negative | 7.3171 / [7, 43] / 0 | 2.8037 / [0, 27] / 0 |
| unowned **after**, mean | **0.0000** | **0.0000** |
| — nonzero cells | **0 / 1000** | **0 / 1000** |

League-wide: frame mean **24.10%** over 67 sealed team-runs **before**;
**identically zero, in every draw, by construction** for any board sealed with
the category matrix. The 24.1% was never a property of the allocation — the
allocation always closed — it was a property of what the artifact *exposed*.
That is the whole of the change: the residual moves from *measured* to
*attributed*.

Denver's 82.82% is not a regression. It is what "a team with a category ledger
and no player split" honestly looks like, and before this repair Denver had no
rush record of any kind on the board.

### 3.5 Tonight's +0.1555 was cancellation across OWNERS as well as across draws

The brief said tonight's small residual was cancellation rather than closure,
and gave the across-draws evidence (sd 3.99, range [−9.96, +28.08], negative in
464 of 1,000). Sealing the category matrix shows a second cancellation the
previous artifact could not express, and it is the more interesting one.

D6 had to recover designed quarterback rushing **by subtraction**, as
`qb/rush_opp − qb/scr`, because `drush` is not sealed. Both quantities are now
in the artifact side by side:

| team | A1 `designed_qb` category | QB layer `rush_opp − scr` | gap |
|---|--:|--:|--:|
| DEN | 2.2810 | 1.6340 | **A1 higher by 0.6470** |
| KC | 0.7200 | 2.2640 | **QB layer higher by 1.5440** |

Tonight's KC residual under D6's definition is `25.1720 − 19.4940 − 5.5700 =
+0.1080`, and the genuinely unowned mass is `kneel + wr + te + fringe + pool =
0.3890 + 0.7670 + 0.0480 + 0.0780 + 0.3700 = 1.6520`. The two nearly cancel
because the QB-layer recovery over-attributes designed rushing by 1.5440 on this
board. **On Denver the gap runs the other way**, so this is not a sign error —
it is two independent draws of one football quantity, which is the "two owners
of one number" pattern this project has paid for repeatedly.

**Surfaced, not repaired.** `qb_accounting` composes `rush_opp = scr + drush`
and A1 composes `qb_rush_opportunity = scr + designed_qb`; both are legitimate
and neither is authorised here to overwrite the other. Sealing `qb/drush` would
remove the inference on one side; reconciling the two is a pre-registration, not
an edit.

### 3.6 `qb_rush_opportunity_within_team_carries` — surfaced, not repaired

Carried on every team's ledger record with its counts, its headroom
distribution, and the reason it is not gated (J-13: the SC1-coupled carry vector
the engine partitioned is not the vector `run_forecast` seals, so a breach
cannot today be split between a carry dealt twice and a denominator that was
never used).

Tonight: DEN `HELD`, headroom mean 23.4480, min 5.000, 0 breaching cells.
KC **`BREACHED`**, headroom mean 19.6020, min −8.000, **4 / 1000 cells**.

The frame figures from the brief reproduce unchanged: **60 of 204 team-runs,
371 of 232,000 cells, 9 of 15 games**, fenced in `test_conservation.py`, which
is `SUITE PASS` on this tree. WAS_PHI's worst draw still puts the quarterback
room 9.922 carries above the team's entire level. Nothing here adjusts it.

---

## 4. `db == att + sacks + scr` — confirmed exact

* **Tonight's re-run**: max absolute deviation **0.000000** over 6,000
  quarterback cells; **0** violating cells.
* **Every sealed run on this tree**: 102 runs, **844,000** quarterback cells,
  **0** violating cells, max absolute deviation **0.000000**. Fenced in
  `test_stat_contract.py::test_c_the_identity_holds_on_every_sealed_quarterback_cell`.
* The identity is checked twice per run — once by `qb_v1.identity_check` where it
  always was, and once through the versioned contract on the final sealed values
  — and `assert_dropback_identity` defaults to `atol = 0.0`, because these are
  counts and a sum of integers holds exactly or it does not hold.
* The guard bites: a seeded one-cell violation is caught, a shape mismatch is
  refused rather than broadcast, and zero cells returns **BLOCKED**, never a
  satisfied identity.

---

## 5. Tests

Run with `python3.12 nfl/tests/run_suite.py --only <module>`, nothing else.

| suite | result |
|---|---|
| `test_stat_contract` (**new**) | **SUITE PASS** — 15 functions, 94 checks |
| `test_football_engine_r4` | SUITE PASS — 17 / 142 |
| `test_draw_coherence` (19 declared checks) | SUITE PASS — 11 / 135 |
| `test_conservation` | SUITE PASS — 21 / 220 |
| `test_v1_rushing_a1` | SUITE PASS — 22 / 115 |
| `test_accounting_invariants` | SUITE PASS — 8 / 41 |
| `test_xl1_shared_pass` | SUITE PASS — 17 / 115 |
| `test_v1_draw_artifact` | SUITE PASS — 17 / 113 |
| `test_production_pipeline` | SUITE PASS — 9 / 69 |
| `test_v1_composition_fidelity` | SUITE PASS — 7 / 20 |
| `test_draw_row_identity` | SUITE PASS — 10 / 31 |
| `test_v1_nonqb_production` | SUITE PASS — 8 / 35 |
| `test_nonqb_r3` | SUITE PASS — 28 / 129 |
| `test_appearance_team_scope` | SUITE PASS — 11 / 50, 1 declared BLOCKED (pre-existing) |
| `test_slate_runner` | SUITE PASS — 10 / 44 |
| `test_inactives_propagation` | SUITE PASS — 19 / 43 |
| `test_v1_entrypoint_integration` | SUITE PASS — 8 / 26 |
| `test_r7_appearance_frame` | SUITE PASS — 20 / 67 |
| `test_c1_denominator` | **SUITE FAIL in the live tree — not mine**, see below |

**`test_c1_denominator`, attributed.** It fails in the working tree on one
check: the sealed Q9 candidate identity no longer reproduces, and the single
differing field is `coefficient_sha16` (live `ef28b13db8612cb0` against sealed
`dee95526cf43e869`) — a refit hurdle coefficient block.
`production_interface_sha16` is `481f005f682cd721`, i.e. `layers.py` is
untouched, and every other identity field matches.

I isolated it rather than asserting it: `git archive 2dc44ab` into a clean
directory, **my five files copied over it and nothing else**, `SUITE PASS`,
7 functions / 25 checks. The same suite also passes at pristine HEAD with and
without the untracked `pbp_2025` blob. The failure therefore comes from another
agent's concurrent edit in the shared checkout — `git status` currently shows
`qb_allocation.py` (R1), `role_prior.py` and `depth_vintage.py` (R3) and
`board.py` (R5) all modified. **I did not touch any of them.** R1 or R3 should
look at it.

All twelve of my core suites were also re-run in that isolated tree and pass
there; `test_nonqb_r3` is the only one that cannot run there, and it fails on
`DERIVED_BUILD_FAILED` because `git archive` does not carry the untracked
derived artifacts — an artefact of the copy, not a code defect. It passes in the
live tree.

---

## 6. Caveats, stated rather than buried

**This is not a byte-replay of the sealed board.** My re-run is
`c0440864f21198fc`; the sealed board is `f91342d6787a66a1`. The information set
moved between them independently of my work: the new run's
`capture_validation` carries `official_inactives` and `official_injury_report`
hashes that the sealed run did not have, and a newer `schedules` blob. So the
KC running-back means move for **two** reasons — the integerisation and a
changed eligibility picture — and I am not attributing that movement to the
repair. What I *do* attribute is what is provable within one run: 0/1000
non-integer cells, 0/1000 closure violations, and `unowned_after` identically
zero.

**The working tree is shared and in motion.** R1, R2, R3 and R5 have uncommitted
edits in this checkout right now. Every measurement above that came from a board
build was built against that moving tree. The suite results are reported both
ways — live tree and isolated tree — precisely so the attribution is not a claim
I am asking anyone to take on trust.

**The R1 interface.** The engine reads `qb['index_by_team']` and
`qb['draws'][f]` for `scr`, `att`, `int`, `db`, `sacks`. If R1's rebuilt QB room
changes either shape, three places need the same edit and no more: the scramble
sum in the ownership ledger call, the count-support matrix assembly, and the
`assert_dropback_identity` call. All three are in `run_game` within forty lines
of each other and all three read the same two keys. Nothing in
`stat_contract.py` depends on the QB object at all.

**Two things I did not do.** I did not fix the `drush` / `designed_qb`
disagreement (§3.5) — it needs a pre-registration and an owner ruling on which
layer owns designed quarterback rushing. I did not gate
`qb_rush_opportunity_within_team_carries` — it is `DIAGNOSTIC` in
`draw_coherence` pending J-13 and gating it would refuse nine of fifteen
sealed games on a defect nobody has attributed yet.

**No sportsbook data was read, no threshold was computed, and no wager is
recommended anywhere in this work.**
