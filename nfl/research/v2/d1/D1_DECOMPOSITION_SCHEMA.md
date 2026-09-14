# D1 — PER-PLAYER OPPORTUNITY DECOMPOSITION: SCHEMA

Diagnostics only. Written 2026-09-14 against branch
`claude/nfl-greenfield-architecture-stsxmk`, HEAD `afefd39`, interpreter
python3.12.

**This pass changes no model.** `nfl/product/decomposition.py` is a reader. It
opens a sealed board, joins draw rows to players by declared identity, and
writes down how each final number was reached. It adjusts nothing, adds no
floor, fits nothing and selects no estimator. Where the engine has no link, the
schema records an absence — it never substitutes a number to keep a chain
looking complete.

Implementation `nfl/product/decomposition.py`; tests
`nfl/tests/test_decomposition.py` (13 functions, 86 checks, PASS under
`python3.12 nfl/tests/run_suite.py --only test_decomposition`); worked artifact
`nfl/research/v2/d1/D1_DEN_KC_DECOMPOSITION.json`.

---

## 1. THE EVIDENCE GRADE IS THE POINT OF THE SCHEMA

Every link carries `evidence`. Without it a decomposition confirms whatever
produced it, because most of its links are ratios of two engine outputs and a
ratio computed backwards reproduces itself no matter what the engine did.

| grade | meaning |
|---|---|
| `MEASURED_DRAWS` | both sides are stored draw matrices, **and the stated relation was checked on every draw cell** |
| `DERIVED_BY_SUM` | a total formed by summing stored matrices |
| `DERIVED_BY_DIFFERENCE` | formed by subtracting stored matrices |
| `DERIVED_BY_DIVISION` | a rate obtained by dividing two of the above. **Not independent evidence about the rate.** |
| `ABSENT` | the engine has no such quantity. A substitute, if one exists, is named together with the direction in which it is wrong. |

A test asserts that no link whose step names a share, a rate, a probability or
a "per" is ever graded anything but `DERIVED_BY_DIVISION`.

## 2. TOP-LEVEL SHAPE

```
contract_version: "nfl-decomposition-1"
board_dir, game_id, run_id, n_draws, code_commit, model_configuration
changes_no_model: true
teams: [...]
team_layer_states: {team: {qb|receiving|rushing: {state, n_rows, code, detail}}}
team_chains:       {team: {links[], conservation[], means{}}}
players:           [{gsis_id, team, position, depth_chart, chains[]}]
evidence_grades:   {grade: prose}
```

### 2.1 `team_layer_states` — absence is a state, never a zero

```
state ∈ { MODELLED, ABSENT_TEAM_DEFERRED, ABSENT_UNEXPLAINED }
```

`ABSENT_TEAM_DEFERRED` carries the governance code and the full warning that
caused it. DEN on this board is `APPEARANCE_TEAM_DEFERRED`: the appearance
layer ran on KC only, so no DEN skill player has an appearance probability, an
allocation or a projection. Rendering that as `targets = 0.0` would be a
forecast of zero, which is a far stronger and quite false claim than "no layer".
`ABSENT_UNEXPLAINED` exists so that a missing layer with no governance warning
naming it cannot quietly borrow the deferred team's excuse.

### 2.2 `chains[]` — one per (player, chain)

```
chain ∈ { QB_PASSING, QB_RUSHING, RB_RUSHING, RECEIVING, NONE }
links[]        ordered, one per chain step, each with an evidence grade
participation{}
views{}
absences[]     {code, step} for every ABSENT link in this chain
```

### 2.3 `participation{}`

```
mask                         the boolean expression over draw arrays
basis ∈ { IDENTIFIED_IN_DRAWS, LOWER_BOUND_ONLY }
basis_detail                 why it is one and not the other
verified_cells_violating     for QBs: the count that was checked, not assumed
p_participates               float, or null when not identified
p_participates_lower_bound   always a float
p_participates_is_a_bound    bool
```

### 2.4 `views{}` — the five required fields, plus the two zeros kept apart

Required by the brief and always present on every chain row:

| field | note |
|---|---|
| `p_participates` | null for every non-QB — see §4.3 |
| `p_zero_opportunity` | P(opportunity draw == 0) |
| `e_opportunity_given_participates` | conditioned on the participation mask |
| `e_outcome_given_participates` | conditioned on the participation mask |
| `e_outcome` | unconditional |

Also persisted: `e_opportunity`, `e_opportunity_given_nonzero_opportunity`,
`e_outcome_given_nonzero_opportunity`, `p_zero_outcome`,
`zero_opportunity_and_zero_outcome_agree`,
`cond_over_uncond_on_participation`, `one_over_p_participates`,
`one_over_one_minus_p_zero_opportunity`, `one_over_one_minus_p_zero_outcome`,
`ratio_identity_holds_against_p_participates`,
`p_zero_opportunity_equals_non_participation`,
`participating_draws_with_zero_opportunity`, `conditional_is_identified`,
`conditional_caveat`.

**Three different zeros, and the schema refuses to merge them.**

* *did not participate* — the player was not on the field for the play type
* *participated, drew no opportunity* — on the field, no target / no carry / no
  attempt (a sacked-or-scrambled dropback for a QB)
* *had opportunity, produced a zero outcome* — a target caught for no gain, a
  completion for zero yards

`E[Y] = P(participates) · E[Y | participates]` closes **exactly** against the
first probability and against no other. Both of the near-misses are persisted
so the size of each is visible rather than inferred.

---

## 3. THE CHAINS AS IMPLEMENTED

### 3.1 QB_PASSING — team plays → dropbacks → share → attempts → completions → yards

| step | evidence |
|---|---|
| team plays (`team_volume__team_off_snaps`) | MEASURED |
| team dropbacks (`team_volume__team_dropbacks_part`) | MEASURED |
| dropback rate = dropbacks / plays | DIVIDED |
| residual = plays − (dropbacks + carries) | DIFFERENCED |
| QB share of team dropbacks | DIVIDED |
| QB dropbacks; `Σ qb__db == rint(team dropbacks)` | **MEASURED**, checked per draw |
| dropbacks → attempts; `db == att + sacks + scr` | **MEASURED**, checked per draw |
| completions | MEASURED |
| completion rate = cmp / att | DIVIDED |
| passing yards | MEASURED |
| yards per completion = pyds / cmp | DIVIDED |

Opportunity `qb__att`; outcome `qb__pyds`; participation mask `qb__db > 0`.

### 3.2 RB_RUSHING — team plays → designed rushes → RB budget → carries → (yards ABSENT)

| step | evidence |
|---|---|
| team plays, team carries | MEASURED |
| `designed_rush_budget = rint(team_carries) − Σ QB scrambles` | DIFFERENCED |
| designed budget → **RB category budget** | **ABSENT** `RB_CATEGORY_BUDGET_NOT_PERSISTED`; substitute = Σ modelled RB carries, a **lower bound** |
| RB share of the modelled RB pool | DIVIDED |
| RB share of team carries (the second denominator) | DIVIDED |
| carries | MEASURED, with the count of non-integer draw cells |
| carries → **rushing yards** | **ABSENT** `RUSHING_CONVERSION_CONTROL_UNDEFINED`; **no substitute offered** |

Outcome is `null`. The board names `carries × yards-per-carry` as the
**prohibited** implementation, so this module does not compute it, not even
"as a diagnostic". A test asserts no yards-per-carry link exists anywhere in
the artifact.

### 3.3 RECEIVING — dropbacks → routes(ABSENT) → target share → targets → catch → receptions → yards

| step | evidence |
|---|---|
| team dropbacks | MEASURED |
| dropbacks → **routes run** | **ABSENT** `NO_ROUTES_LAYER`; substitute named, value null |
| QB attempts (the real allocation pool) | MEASURED |
| Σ modelled player targets (the allocation **denominator**) | SUMMED |
| stored `team_volume__team_targets`, flagged **not** the denominator | MEASURED, `is_the_allocation_denominator: false` |
| target share of the modelled pool | DIVIDED |
| target share against the stored total, labelled WRONG | DIVIDED |
| targets, receptions, receiving yards | MEASURED |
| catch probability = rec / tgt | DIVIDED |
| yards per reception = yds / rec | DIVIDED |

The chain routes through **QB attempts**, never through a separately stored
team total, because C3 constructs the receiving layer out of QB completions.
Two team-level conservation identities are checked per draw and both hold
exactly on KC.

### 3.4 QB_RUSHING — beyond the three requested chains, recorded anyway

`qb__rush_opp → qb__ryds` is MEASURED and a yards-per-opportunity ratio is
DIVIDED. It is persisted because the asymmetry is the finding: the same board
converts carries to yards for a quarterback and declares the conversion
ungoverned for a running back.

---

## 4. WHAT THE ENGINE CANNOT SUPPLY, AND WHAT STANDS IN

### 4.1 Routes — `NO_ROUTES_LAYER`

V1 has no routes layer. The engine's own stand-in is pass-snap participation,
which `nfl/production/nonqb/layers.py:272` itself calls **"an upper bound on
routes run"** with a gap that is "directional and its magnitude is unbounded
from the available data". That proxy is not written into the sealed artifact
either, so the link is recorded ABSENT with the proxy **named** and its value
**null**.

Why that is the honest substitution: the alternative is to back out a route
count from targets, which would re-derive the target share the route link is
supposed to explain, and would then be quoted as if it explained it.

### 4.2 RB rushing yards — `RUSHING_CONVERSION_CONTROL_UNDEFINED`

No governed carry → yards control exists; three owner decisions are open in
`nfl/production/nonqb/rushing_inventory.json`. The chain terminates at carries
and the outcome view is null. Nothing stands in, deliberately.

### 4.3 P(participates) for every non-QB — bounded, not stated

The appearance layer runs, but its probability is not persisted, and the draws
cannot recover it: a player who appears and receives nothing is cell-for-cell
identical to one who did not appear. So

```
P(participates) ≥ 1 − P(no modelled opportunity of any kind)
```

is recorded as `p_participates_lower_bound`, `p_participates` is `null`, and
every `| participates` figure on that row is conditioned on the lower-bound
mask and flagged `conditional_is_identified: false`. It is an **upper bound**
on the true conditional mean, because it drops the appear-and-receive-nothing
draws that belong in the denominator.

For quarterbacks it *is* identified: zero dropbacks implies zero of every other
QB quantity on every draw cell. That implication is **verified at runtime**
(`verified_cells_violating`), not assumed, because it is exactly the kind of
fact that stops being true one engine version later and takes the conditional
means with it.

### 4.4 The RB category budget — `RB_CATEGORY_BUDGET_NOT_PERSISTED`

A1 partitions the rush-play budget across six named categories. The `rb`
category total is real and the engine computed it, but it is not in the
artifact. Σ modelled RB carries is a lower bound on it: any rb-category carry
that landed on an unmodelled back is missing from the sum and from nothing else.

---

## 5. REFUSALS

`decompose()` returns an `Outcome`. A missing board, an empty `board.json`, a
manifest with no `layers` block, an empty draw set, a board player with no
`gsis_id`, or an empty decomposition are each a **named** BLOCKED or FAIL —
never an empty row. `Outcome.__bool__` raises, and a test asserts it still does.

Row joins go through `manifest['layers'][<layer>]['row_ids']` with
`row_axis: gsis_id` (`team_volume` uses `team`). Nothing is ever joined
positionally; a layer that does not exist yields no rows rather than row 0, and
a missing array is a named raise.
