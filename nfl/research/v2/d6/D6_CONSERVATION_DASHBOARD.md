# D6 — team-level conservation dashboard

**Diagnostics only.** Nothing in this pass repairs, clips, renormalises or
adjusts anything. No estimator was touched, no HARD invariant in
`nfl/production/draw_coherence.py` was weakened, duplicated or re-gated, and no
sealed artifact was modified.

Deliverables:

* `nfl/product/conservation.py` — the reusable dashboard. Pure functions over
  draw matrices, plus one file-reading entry point and a renderer.
* `nfl/tests/test_conservation.py` — 21 test functions, 220 checks, `SUITE PASS`
  under `python3.12 nfl/tests/run_suite.py --only test_conservation`.
* This report.

Run across **tonight's board and all 102 sealed runs** under
`nfl/research/live/2026_01_*` (204 team-runs, 15 games).

---

## 1. What this object is, and why it is not `draw_coherence`

`draw_coherence` asks of one cell: *is this state impossible?* It answers in
violating-cell counts and it gates. That is per-cell impossibility.

This asks a conservation question: *a team had some quantity of opportunity in
a draw, the model dealt it out to named owners — did the pieces add up, and if
not, how much mass is unaccounted for and whose is it?*

Three differences make it a separate object rather than a restatement:

1. **A containment check passes on lost mass.** `sum(targets) <= sum(attempts)`
   is satisfied by a team that deals *zero* targets. All 35 throws have gone
   somewhere unnamed and the inequality is perfectly happy. Only a conservation
   view sees the hole, because only a conservation view asks what the rest was.
2. **A violation count discards the size.** 464 cells over a bound, and 464
   cells over it by 9.96 carries, read identically in a tally. The magnitude is
   the finding.
3. **The owner is the point.** Unowned mass is not automatically a defect. The
   job is to make it *visible and named* — its size and whose it is.

Where a rule is already HARD in `draw_coherence`, this module classes it
`CONTAINMENT`, sets `gates_here: False`, and points at the owning check by
name. A test asserts every such pointer resolves to a check that actually
exists in `DC.COHERENCE`, so the two files cannot come to two verdicts about
one rule.

---

## 2. The check set, with its contracts

16 contracts in four classes, across five views. Every one declares what it
asserts, the contract it is asserting, who owns any residual, and whether that
owner is in the artifact.

| check | class | contract it asserts | residual owner | owner sealed? |
|---|---|---|---|---|
| `team_dropback_partition` | CLOSURE | `qb_accounting.dropback_identity` at room level: Σ db == Σ (att+sacks+scr) | — | — |
| `qb_room_closes_on_team_dropbacks` | CLOSURE | R2 largest-remainder: Σ db == `max(rint(team_dropbacks_part), 0)`, exact | — | — |
| `team_dropback_level_rounding_residual` | RESIDUAL | Σ db − the *continuous* level; bounded by 0.5 by the rint above | R2 level rounding | yes |
| `target_opportunity_closes` | RESIDUAL | C3: `rint(Σ att) − Σ targets` = untargeted + `other` pool | untargeted throws + unmodelled-receiver pool | **no** |
| `targets_within_throw_budget` | CONTAINMENT | Σ targets ≤ `rint(Σ att)` | — (gated by `DC.team_targets_within_team_attempts`) | — |
| `stored_team_targets_is_not_the_denominator` | RESIDUAL | `team_volume/team_targets` − the C3 budget: the trap, as a number | D1's second, unused owner of one quantity | yes (but unused) |
| `receptions_close_on_completions` | CLOSURE | C3 shared event: Σ receptions == Σ cmp | — (gated by `DC.team_passing_line_closes_on_receiving`) | — |
| `receiving_yards_close_on_passing_yards` | CLOSURE | C3 shared event: Σ receiving_yards == Σ pyds | — (same) | — |
| `receiving_td_closes_on_passing_td` | CLOSURE | C3 shared event: Σ receiving_td == Σ ptd | — (same) | — |
| `qb_designed_rush_non_negative` | CONTAINMENT | `qb_accounting.rush_opportunity_composition`: rush_opp = scr + drush, so rush_opp − scr ≥ 0 | — | — |
| `rush_opportunity_closes` | RESIDUAL | A1 ownership graph: team_carries − (RB + QB-scramble + QB-designed) | A1 `kneel`+`wr`+`te`+`fringe`, **plus** the J-13 wrong-vector defect | **no** |
| `qb_rush_opportunity_within_team_carries` | CONTAINMENT | Σ rush_opp ≤ team_carries | — (gated as DIAGNOSTIC in `DC`) | — |
| `team_rushing_td_closes` | ABSENT | would close QB rtd + RB rushing_td on a team rushing-TD total | — | **no such quantity exists** |
| `team_touchdowns_close` | ABSENT | would close the team's offensive touchdowns without double counting | — | **no such quantity exists** |
| `team_target_pool_membership` | ABSENT | would split the target residual into untargeted vs `other` | — | **neither vector is sealed** |
| `team_carry_category_membership` | ABSENT | would split the rush residual into kneel / wr / te / fringe | — | **only `rb` reaches the artifact** |

**Regime is declared, never inferred.** Three views hold only under C3 and the
room closure only under R2. Which components were live is read from the
artifact's own `candidate_components_applied` — a declaration the run wrote
about itself. Guessing "C3 must have been on, look how well the yards agree"
would be asserting the conclusion from the evidence meant to test it. A run
without C3 gets `NOT_APPLICABLE` with the regime named, not a `PASS`.

### The three traps, and how each is handled

**Trap 1 — the stored team total is not the allocation denominator.** Under C3
the target budget is the quarterbacks' attempts; `team_volume/team_targets` is
a separate unused D1 draw that `football_engine` itself marks
`d1_team_targets_unused: True` and `run_forecast` seals anyway under a name
that says it is the team's targets (WS09 J-12). A dashboard that used it as
the denominator would report a false violation on every board. This module
never does, and that is asserted **behaviourally**, not by comment: the test
triples `team_volume/team_targets` and requires every target-conservation
record to be bit-identical. The gap is measured instead, as its own row.

**Trap 2 — a team can have no modelled layer at all.** DEN has no receiving and
no rushing rows tonight (`APPEARANCE_TEAM_DEFERRED`). Every such cell is
`NOT_APPLICABLE` with the reason stated, carries `residual: None` and a
`is_not_zero_mass: True` marker, so it cannot be summed into a slate total as
though the team had dealt nothing.

**Trap 3 — a residual reported as a mean is a residual hidden.** Every residual
reports mean, sd, p05/p50/p95, min, max and the count of draws in which it is
negative. `sign_changes` flags a residual with cells on both sides — a *fact
about the sample*, not a threshold anybody chose. It is the flag that says the
mean cannot stand in for the quantity. This is not decorative; see §5.

---

## 3. Tonight's board — `2026_01_DEN_KC` / `f91342d6787a66a1`

`PASS[CONSERVATION_MEASURED]` — 18 checks evaluated over 2 teams; 6 residuals
measured, 2 with an owner not in the artifact; 5 residuals change sign across
draws; 1 containment breach recorded and not gated here; 6 checks not
applicable; 8 declared contracts have no quantity to check against.

Declared regime: `A1=on, C3=on, R2=on`.

| check | team | state | lhs mean | rhs mean | resid mean | resid sd | resid range | draws resid<0 |
|---|---|---|--:|--:|--:|--:|---|--:|
| `team_dropback_partition` | DEN | PASS | 37.2230 | 37.2230 | 0 | 0 | [0, 0] | 0/1000 |
| `team_dropback_partition` | KC | PASS | 41.4920 | 41.4920 | 0 | 0 | [0, 0] | 0/1000 |
| `qb_room_closes_on_team_dropbacks` | DEN | PASS | 37.2230 | 37.2230 | 0 | 0 | [0, 0] | 0/1000 |
| `qb_room_closes_on_team_dropbacks` | KC | PASS | 41.4920 | 41.4920 | 0 | 0 | [0, 0] | 0/1000 |
| `team_dropback_level_rounding_residual` | DEN | MEASURED | 37.2230 | 37.1858 | +0.0372 | 0.2923 | [−0.498, +0.495] | 422/1000 |
| `team_dropback_level_rounding_residual` | KC | MEASURED | 41.4920 | 41.4679 | +0.0241 | 0.3210 | [−0.498, +0.496] | 417/1000 |
| `target_opportunity_closes` | DEN | NOT_APPLICABLE | — | — | — | — | — | — |
| `target_opportunity_closes` | KC | MEASURED | 35.4060 | 33.4970 | **+1.9090** | 2.1593 | [0, +23] | 0/1000 |
| `receptions_close_on_completions` | KC | PASS | 23.2780 | 23.2780 | 0 | 0 | [0, 0] | 0/1000 |
| `receiving_yards_close_on_passing_yards` | KC | PASS | 251.1770 | 251.1770 | 0 | 0 | [0, 0] | 0/1000 |
| `receiving_td_closes_on_passing_td` | KC | PASS | 1.6260 | 1.6260 | 0 | 0 | [0, 0] | 0/1000 |
| `qb_designed_rush_non_negative` | DEN | HELD | 4.0840 | 2.4500 | +1.6340 | 1.3191 | [0, +10] | 0/1000 |
| `qb_designed_rush_non_negative` | KC | HELD | 5.5700 | 3.3060 | +2.2640 | 2.5172 | [0, +11] | 0/1000 |
| `qb_rush_opportunity_within_team_carries` | DEN | HELD | 27.5514 | 4.0840 | +23.4674 | 8.0465 | [+4.81, +44.30] | 0/1000 |
| `qb_rush_opportunity_within_team_carries` | KC | **BREACHED** | 25.2449 | 5.5700 | +19.6749 | 7.9328 | [−8.272, +43.31] | **6/1000** |
| `rush_opportunity_closes` | DEN | NOT_APPLICABLE | — | — | — | — | — | — |
| `rush_opportunity_closes` | KC | MEASURED | 25.2449 | 25.0893 | **+0.1555** | **3.9897** | **[−9.963, +28.077]** | **464/1000** |
| `stored_team_targets_is_not_the_denominator` | DEN | MEASURED | 33.7495 | 33.2360 | +0.5135 | 4.0265 | [−12.89, +12.51] | 464/1000 |
| `stored_team_targets_is_not_the_denominator` | KC | MEASURED | 28.7035 | 35.4060 | **−6.7025** | 4.4924 | [−21.01, +5.16] | 939/1000 |

Every hand-measured figure from the one-off reproduces exactly, and each is
asserted in the test module so the generalisation cannot drift from what it
generalised:

* DEN `team_dropbacks_part` 37.1858 vs QB room 37.2230, residual −0.0372.
* KC `team_dropbacks_part` 41.4679 vs QB room 41.4920, residual −0.0241.
* `db == att + sacks + scr`: max absolute deviation 0.000000, both teams.
* DEN receiving and rushing layers absent → `NOT_APPLICABLE`, not zero mass.
* KC targets 33.4970 vs attempts 35.4060, unowned +1.9090.
* KC receptions 23.2780 == completions, deviation 0.
* KC receiving yards 251.1770 == passing yards, deviation 0.
* KC carries 25.2449 = RB 19.5193 + QB scr 3.3060 + QB designed 2.2640 +
  0.1555 unowned.

**What the one-off did not show, and the dashboard does.** That +0.1555 rush
residual — 0.62% of the level — is an *average of a quantity that changes
sign*. Its sd is 3.99 (16% of the level), it runs from −9.96 to +28.08, and it
is **negative in 464 of 1000 draws**. Nearly half the draws over-allocate
carries; the other half under-allocate; the mean is what is left after they
cancel. Reported as a mean alone, KC reads as the most conserved rush
allocation on the frame. Reported as a distribution, it does not close and does
not contain, per draw, in either direction.

The `stored_team_targets` trap is board-dependent in exactly the way that makes
it dangerous: KC's mean gap is −6.70 and impossible to miss, DEN's is +0.51 and
would read as agreement — while DEN's per-draw range is [−12.89, +12.51] with
zero draws of exact agreement. The mean is not the trap; the joint is.

---

## 4. Historical results — 102 sealed runs, 204 team-runs

`from_run_dir` returned `PASS[CONSERVATION_MEASURED]` on all 102. Regimes as
declared: 34 runs `A1+C3+R2`, 68 runs `A1+R2` (QB layer only).

| check | team-runs evaluated | breaches / failures | mean of per-team-run residual means | worst per-team-run mean | draws with residual < 0 |
|---|--:|--:|--:|--:|---|
| `team_dropback_partition` | 204 | **0** | 0.0000 | 0.0000 | 0 / 232,000 |
| `qb_room_closes_on_team_dropbacks` | 204 | **0** | 0.0000 | 0.0000 | 0 / 232,000 |
| `team_dropback_level_rounding_residual` | 204 | — | −0.0135 | 0.2482 | 123,748 / 232,000 |
| `receptions_close_on_completions` | 67 | **0** | 0.0000 | 0.0000 | 0 / 95,000 |
| `receiving_yards_close_on_passing_yards` | 67 | **0** | −0.0000 | 0.0000 | 0 / 95,000 |
| `receiving_td_closes_on_passing_td` | 67 | **0** | 0.0000 | 0.0000 | 0 / 95,000 |
| `qb_designed_rush_non_negative` | 204 | **0** | +1.7424 | 5.4250 | 0 / 232,000 |
| `targets_within_throw_budget` | 67 | **0** | +1.7805 | 2.0570 | 0 / 95,000 |
| `target_opportunity_closes` | 67 | — | +1.7805 | 2.0570 | 0 / 95,000 |
| `stored_team_targets_is_not_the_denominator` | 68 | — | −1.3291 | −9.9032 | 57,890 / 96,000 |
| `rush_opportunity_closes` | 67 | — | **+6.5788** | **+13.1626** | **6,650 / 95,000** |
| `qb_rush_opportunity_within_team_carries` | 204 | **60 team-runs** | +23.8791 | — | **371 / 232,000** |

**No board fails a closure.** Every exact identity this dashboard can write
holds in every draw of every sealed run: the dropback partition and the R2 room
closure over 232,000 team-draw cells, and all three C3 passing-line closures
over 95,000. The dropback rounding residual reaches exactly 0.500000 at its
extreme, which is the rint bound and nothing else.

**The known open item is real, is spread, and is nobody's.**
`qb_rush_opportunity_within_team_carries` breaches on **60 of 204 team-runs**,
**371 of 232,000 cells**, across **9 of 15 games**:

| game | team-runs breaching | cells | worst residual |
|---|--:|--:|--:|
| ARI_LAC (LAC) | 10 | 130 | −8.068 |
| MIA_LV (MIA) | 9 | 86 | −8.676 |
| BAL_IND (BAL) | 4 | 64 | −4.789 |
| TB_CIN (TB) | 9 | 45 | −2.743 |
| WAS_PHI (PHI) | 9 | 22 | −9.922 |
| BUF_HOU (BUF) | 12 | 12 | −1.132 |
| DEN_KC (KC) | 1 | 6 | −8.272 |
| GB_MIN (MIN) | 4 | 4 | −0.918 |
| DAL_NYG (NYG) | 2 | 2 | −2.250 |

This confirms the brief's characterisation from the other side: it is present
on control boards, is not caused by any recent repair, and tonight's 6/2,000 is
the *small* end of the distribution — WAS_PHI's worst single draw puts the
quarterback room 9.922 carries above the team's entire carry level. It is
fenced at these exact counts in `test_conservation.py`, so it is now a standing
row in a dashboard rather than a line in a test log; and because
`draw_coherence` classes it DIAGNOSTIC pending the J-13 stored-vector defect,
this module records it and explicitly does not gate on it.

---

## 5. Where the residual mass lives, and how much

### Rush opportunity — the large one

Per game, most recent run, mean over 1,000 draws:

| game | team | carry level | RB | QB scr | QB designed | **OTHER** | OTHER share | sd | draws OTHER<0 |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| ARI_LAC | ARI | 24.64 | 16.34 | 1.95 | 1.24 | 5.116 | 20.8% | 4.04 | 80 |
| ARI_LAC | LAC | 28.89 | 16.86 | 2.93 | 4.27 | 4.836 | 16.7% | 6.66 | 212 |
| ATL_PIT | ATL | 29.39 | 20.04 | 1.19 | 0.72 | 7.443 | 25.3% | 5.31 | 17 |
| ATL_PIT | PIT | 27.97 | 17.35 | 1.23 | 0.45 | 8.936 | 31.9% | 4.44 | 6 |
| BAL_IND | BAL | 27.00 | 15.93 | 3.38 | 5.42 | 2.271 | 8.4% | 5.24 | 343 |
| BAL_IND | IND | 27.93 | 18.97 | 1.83 | 2.02 | 5.101 | 18.3% | 4.56 | 103 |
| DAL_NYG | DAL | 28.38 | 17.40 | 2.26 | 2.39 | 6.326 | 22.3% | 5.02 | 75 |
| DAL_NYG | NYG | 31.53 | 19.78 | 2.65 | 2.58 | 6.524 | 20.7% | 5.51 | 91 |
| **DEN_KC** | **KC** | **25.24** | **19.52** | **3.31** | **2.26** | **0.156** | **0.6%** | **3.99** | **464** |
| NO_DET | DET | 29.07 | 17.57 | 0.91 | 0.59 | 9.991 | 34.4% | 6.47 | 13 |
| NO_DET | NO | 25.87 | 14.46 | 2.00 | 1.71 | 7.697 | 29.8% | 4.70 | 23 |
| SF_LA | LA | 26.59 | 18.27 | 0.72 | 0.56 | 7.037 | 26.5% | 4.50 | 10 |
| SF_LA | SF | 28.35 | 18.08 | 1.80 | 1.04 | 7.426 | 26.2% | 4.74 | 26 |
| TB_CIN | CIN | 23.34 | 15.06 | 1.47 | 1.01 | 5.798 | 24.8% | 4.51 | 40 |
| TB_CIN | TB | 28.48 | 19.40 | 2.01 | 0.80 | 6.269 | 22.0% | 4.61 | 43 |

Across all 67 team-runs with a rushing layer: **mean unowned share 24.1%**,
range 0.6% to 45.3%. **All 67 have at least one over-allocated draw, and all 67
change sign.** 6,650 of 95,000 draws deal more carries than the team's level.

This is the finding the one-off could not have produced. **DEN@KC is the most
closed rush allocation of the fifteen, by an order of magnitude** — everywhere
else roughly a quarter of the team's carries have no modelled owner. Generalise
tonight's board alone and you conclude the rush partition essentially closes;
generalise across the frame and you find it routinely leaves 5–10 carries per
team-draw to owners that are computed and then discarded.

The residual's owner is declared: A1's `kneel`, `wr`, `te` and `fringe`
categories, which are real football and legitimately not modelled as rows.
**That makes a positive residual expected and lawful.** What it does not
explain is the negative tail, and attribution there is blocked by J-13: the
SC1-coupled carry vector the engine partitioned is not the vector
`run_forecast` seals, so a negative residual cannot today be split between a
carry dealt twice and a denominator that was never used. Both halves ride with
every record.

Note the anti-correlation in the table: the boards with the *smallest* mean
residual (KC 0.6%, BAL 8.4%, LAC 16.7%) carry the *largest* over-allocation
counts (464, 343, 212 of 1,000). A small mean here is cancellation, not
closure. Any future summary that ranks boards by mean residual will rank them
close to backwards.

### Target opportunity — the small, well-behaved one

Unowned target mass is **+1.78 per team-draw on average, 5.29% of the throw
budget**, with a strikingly tight range across all 67 team-runs: **5.03% to
5.56%**. It is never negative in any of 95,000 draws, so containment holds
everywhere.

Its declared owners are the untargeted-throw pool and the `other` unmodelled-
receiver pool. `shared_pass.untargeted_rate()` returns **0.042320**, estimated
from 3,230 team-games. Subtracting that from the observed 5.29% leaves roughly
**1.1% of the budget for the `other` pool** — an arithmetic difference of two
means, not a measurement, because neither vector is sealed. The brief's
characterisation is confirmed: **+1.91 unowned targets on KC is lawful**, it is
what a throwaway rate of 4.2% plus a small unmodelled-receiver share looks
like, and the dashboard's job is to print it, not to flag it.

### The stored-total trap, quantified across the frame

`team_volume/team_targets` agrees exactly with the C3 budget in **0 of 96,000
draws** across 68 team-runs — reproducing WS09 J-12 on an 8.5× larger sample
than the four games it was found on. Per-team-run mean gaps range **−9.903
(BAL) to +2.992 (LA)**. Six of sixteen team-sides have a mean gap under 1.0 in
absolute value and would pass casual inspection; none of them agrees on a
single draw.

### The dropback rounding residual — the one that is fully owned

−0.0135 on average, never outside ±0.500000, negative in 53% of draws. Both
sides are sealed, the owner is R2's `rint` of D1's continuous level, and there
is nothing unattributed in it. It is in the dashboard as the contrast case: this
is what a residual looks like when its owner *is* in the artifact.

---

## 6. Declared contracts that cannot be written, because the quantity does not exist

Four, reported on every board and every team rather than left silent. A
contract that cannot be checked is a standing gap in the conservation view, and
a gap that is not printed is a gap nobody closes.

**`team_target_pool_membership`** — would split the target residual into its two
named owners. `shared_pass.targeted_throws` draws `untargeted` as a named pool;
`shared_pass.deal_targets` deals `other` as a named pool;
`football_engine` asserts `sum_i targets_i + other == targeted` exactly, per
team per draw, at run time — and then **seals neither vector**. A sealed board
can measure their sum and can never split it. *Sealing either one makes this
check writable.*

**`team_carry_category_membership`** — would split the rush residual into A1's
`kneel`, `wr`, `te` and `fringe`. `rushing_a1.allocate` partitions the rush-play
budget across six named categories with one multinomial per draw, so every
carry has exactly one owner by construction — and **only the `rb` category
reaches the artifact**, as `rushing/carries` rows. The other five are computed
and discarded. *Sealing the category matrix makes the entire rush partition
auditable from a sealed board, and would let the 24.1% residual be attributed
instead of merely measured.* This is the single highest-value artifact change
this pass found.

**`team_rushing_td_closes`** — would close QB `rtd` + RB `rushing_td` on a team
rushing-touchdown total. **No team rushing-touchdown quantity is drawn,
allocated or sealed anywhere.** `team_volume` carries `team_carries`,
`team_dropbacks_part`, `team_off_snaps`, `team_rz_carries` and `team_targets`,
and no touchdown quantity of any kind. Even the left-hand side is partial: WR
and TE rushing touchdowns are unmodelled.

**`team_touchdowns_close`** — would close the team's offensive touchdowns
without double counting a passing TD against its receiving TD. **V1 forecasts
no team scoring distribution**, and no drive or score layer exists. The only
touchdown conservation the artifact can express is
`receiving_td_closes_on_passing_td`, which holds exactly on all 95,000
C3 cells.

Two further contracts exist in code but are only *partly* checkable here, and
both are recorded on the affected rows rather than as separate entries:

* **The `drush` component is not sealed.** `qb_accounting` composes
  `rush_opp = scr + drush`, but only `rush_opp` and `scr` reach the artifact.
  The designed-rush owner in the rush partition is therefore *recovered by
  subtraction*. That recovery is only legitimate if it cannot go negative,
  which `qb_designed_rush_non_negative` measures: it holds on all 232,000
  cells, minimum 0.000. Sealing `qb/drush` would remove the inference.
* **J-13 rides on every carry residual.** `team_volume/team_carries` is the only
  carry level sealed, so it is used as a level to measure against — but the
  caveat that it is not the vector the engine partitioned travels with every
  number computed from it, and a test asserts that caveat is present in the
  record.

---

## 7. How to run it

```
python3.12 -c "
import sys; sys.path.insert(0,'/home/user/nfl')
from nfl.product import conservation as C
o = C.from_run_dir('<sealed run directory>')
print(C.render(o))
"
```

`from_run_dir` is the only function in the module that touches a file.
Everything else is a pure function over `{'layer/metric': (rows x draws)}`
plus a row map plus a declared regime, so the identical code runs on a sealed
board, on a rehearsal, and inside a test. It opens nothing for writing; that is
asserted on the AST, alongside the absence of any clip, renormalisation or
write into a draw matrix.

`nfl/tests/test_conservation.py`: 21 test functions, 220 checks, `SUITE PASS`.
The sealed-board fence asserts 102 runs, 204 team-runs, 34 C3 runs, 0 closure
failures over 232,000 + 95,000 cells, 60 breaching team-runs / 371 cells / 9
games, 67 sign-changing rush residuals, and 0 of 96,000 exact agreements on the
stored target total — so a silent rewrite of a sealed artifact, or a change in
this module's arithmetic, fails there rather than quietly moving a number.

---

## 8. One pre-existing failure, in a file D6 does not own

`python3.12 nfl/tests/run_suite.py --only test_draw_coherence` reports
`SUITE FAIL` with 4 failing checks. All four are its frozen `EXPECTED_SEALED`
baseline reading `runs: 101` / `qb_cells: 838000` against a repository that now
holds **102** runs and 844,000 cells, because tonight's DEN@KC board was sealed
at HEAD `afefd39`. The negative-yardage census has moved for the same reason.

This is baseline drift caused by the new sealed artifact, not by anything in
this pass: `nfl/production/draw_coherence.py` and
`nfl/tests/test_draw_coherence.py` are untouched and `test_draw_coherence` does
not import `conservation`. It is reported here rather than repaired, because
the file belongs to another owner and the fix is a deliberate baseline
re-freeze, not an edit.
