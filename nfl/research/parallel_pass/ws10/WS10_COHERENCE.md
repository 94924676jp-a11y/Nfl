# WS10 — impossible and incoherent outcomes in the stored draws

**CODE CHANGED: NO.** Nothing outside `nfl/research/parallel_pass/ws10/` was
written. The proposed invariants are a `.py.proposed` file so the suite does
not collect them. Every number below was read out of the sealed artifacts on
2026-09-14 at HEAD 57d38ad with `python3.12`.

Deliverables in this directory:

* `WS10_COHERENCE.md` — this file.
* `test_draw_coherence.py.proposed` — 14 proposed invariants, runnable by hand
  (`python3.12 nfl/research/parallel_pass/ws10/test_draw_coherence.py.proposed`),
  plus a `REJECTED_INVARIANTS` block naming what was considered and thrown out.

---

## 1. What was scanned

Every `player_draws.npz` under `nfl/research/live/2026_01_*/`. All of them are
`run_status.json: SEALED`; eight `REFUSED` runs carry no draws and are not in
the frame.

| | |
|---|---|
| Sealed runs with stored draws | **101** |
| Games | **14** (ARI_LAC, ATL_PIT, BAL_IND, BUF_HOU, CHI_CAR, CLE_JAX, DAL_NYG, GB_MIN, MIA_LV, NO_DET, NYJ_TEN, SF_LA, TB_CIN, WAS_PHI) |
| Draws | **115,000** |
| Draw cells (manifest `n_draw_cells`) | **16,714,000** |
| Runs carrying all four layers (C3 live) | **33** |
| Runs carrying `qb` + `team_volume` only | **68** |
| `pre_inactives` / `post_inactives` / other | 55 / 45 / 1 |
| Games with a resolved official inactive list | 13 of 14 (DAL_NYG's discovery is quarantined) |

Rows were joined by `manifest['layers'][<layer>]['row_ids']` and
`board.json['players'][].team`. **Nothing was indexed positionally**; the only
row accessor in the proposed test takes gsis ids.

The 68 QB-only runs are QB-only because of defect **D03** in
`nfl/research/live/OPEN_DEFECTS.json` (twelve clubs filed injury rows with
`report_status` unset, so the appearance layer deferred). Every receiving and
rushing check therefore rests on 33 runs, not 101.

---

## 2. Scan results

`cells` is per-player-per-draw except where the unit is a team-draw.

| # | Check | Unit | Violating | Checked | Runs | Verdict |
|---|---|---|---|---|---|---|
| I1 | completions > attempts, per QB per draw | cell | **5,278** | 838,000 | 33 | **FAIL** |
| I2 | passing TD > completions, per QB per draw | cell | **731** | 838,000 | 33 | **FAIL** |
| I3 | passing yards ≠ 0 with zero completions | cell | **11,616** | 838,000 | 33 | **FAIL** |
| I4 | dropbacks ≠ attempts + sacks + scrambles | cell | 0 | 838,000 | 0 | PASS |
| I5 | any count matrix negative | cell | 0 | 13,642,000 | 0 | PASS |
| I6 | receptions > targets | cell | 0 | 1,396,000 | 0 | PASS |
| I7 | receiving TD > receptions | cell | 0 | 1,396,000 | 0 | PASS |
| I8 | receiving yards ≠ 0 with zero receptions | cell | 0 | 1,396,000 | 0 | PASS |
| I9 | rushing TD > carries | cell | 0 | 381,000 | 0 | PASS |
| I10 | Σ player targets > Σ QB attempts, per team per draw | team-draw | 0 | 94,000 | 0 | PASS |
| I11 | Σ QB dropbacks ≠ rint(team dropback budget) | team-draw | 0 | 230,000 | 0 | PASS |
| I12 | Σ QB scrambles > team carries | team-draw | **9** | 230,000 | 9 | **FAIL** |
| I13 | Σ RB carries + Σ QB rush opportunity > team carries | team-draw | **6,186** | 94,000 | 33 | **FAIL** |
| I14 | officially inactive **non-QB** with positive volume, post-inactives runs | cell | 0 | 75,000 | 0 | PASS |

Checks the brief asked for that produced **zero** violations and are recorded
as clean rather than skipped: receiving yards with zero targets (0 of
1,396,000), receptions > targets, receiving TD > receptions, QB dropbacks == 0
with positive passing volume (0 — implied by I4 plus non-negativity), and
"backup and starter allocations inconsistent with the team dropback total"
(I11: exact integer closure on 230,000 team-draws, worst deviation 0).

Two further comparisons, **not** invariants, measured for the record:

* Σ team receptions vs Σ team completions: **equal in 94,000 of 94,000**
  team-draws.
* Σ team receiving yards vs Σ team passing yards: max absolute difference
  **1.14e-13** over 94,000 team-draws. The documented 75-in-3,230 lateral
  exception does not arise because the model generates one event and credits
  both sides from it.

### Per-game breakdown of the failing checks (33 four-layer runs)

| Game | I1 | I2 | I3 | I13 |
|---|---|---|---|---|
| 2026_01_ARI_LAC | 734 | 112 | 1,758 | 2,217 |
| 2026_01_ATL_PIT | 370 | 53 | 669 | 46 |
| 2026_01_BAL_IND | 170 | 19 | 369 | 446 |
| 2026_01_DAL_NYG | 1,410 | 198 | 2,767 | 2,526 |
| 2026_01_NO_DET | 788 | 98 | 1,667 | 182 |
| 2026_01_SF_LA | 821 | 107 | 1,904 | 190 |
| 2026_01_TB_CIN | 985 | 144 | 2,482 | 579 |

I1, I2 and I3 fire in **all 33** runs that have the C3 shared-pass layer live
and in **none** of the 68 runs that do not. That is the diagnosis, not a
coincidence — see F3.

---

## 3. Violations, with the mechanism read out of the code

### F3 — the passer's line is credited by a multinomial that ignores his own attempts

`nfl/production/nonqb/shared_pass.py:172` `credit_to_passers`:

```python
w = np.where(tot > 0, A / np.where(tot > 0, tot, 1.0), 1.0 / max(nq, 1))
for j in range(m):
    cmp_q[:, j] = rng.multinomial(int(round(float(team_cmp[j]))), w[:, j])
    ptd_q[:, j] = rng.multinomial(int(round(float(team_ptd[j]))), w[:, j])
pyds_q = w * np.asarray(team_pyds, float)[None, :]
```

`w` is the attempt **share**. The multinomial closes on the team total and that
closure is checked, but nothing caps a quarterback's credited completions at his
own attempts, his touchdowns at his own completions, or his yards at zero when
he has no completion. `nfl/production/nonqb/football_engine.py:903` then writes
the result straight over `qb['draws']['cmp' | 'pyds' | 'ptd']`, which is what
the artifact seals and what the board publishes as "Completions", "Passing
yards" and "Passing touchdowns".

`qb_v1.forecast` (`nfl/production/qb_v1.py:248`) **does** refuse `cmp > att`,
and `qb_v1.identity_check` does check the dropback identity — both run
*before* the C3 credit overwrites the columns. So `QB_DRAW_ACCOUNTING_HOLDS`
appears in all 101 sealed artifacts while 5,278 cells of the sealed draws
violate it.

Worst examples:

| Check | Run | Row | Draw | Values |
|---|---|---|---|---|
| I1 | `2026_01_ATL_PIT/pre_inactives_V1_CANDIDATE_R8/f67d72ab0701d211` | `00-0033662` | 956 | cmp=13, att=7, db=8, sacks=1, scr=0 |
| I2 | `2026_01_TB_CIN/post_inactives_V1_CANDIDATE_R5/819a8eba1596697d` | `00-0038391` | 935 | ptd=3, cmp=0, att=1 |
| I3 | `2026_01_TB_CIN/post_inactives_V1_CANDIDATE_R5/819a8eba1596697d` | `00-0035282` | 401 | cmp=0, pyds=93.0638, att=9 |

Rate conditioned on the event being possible at all: **4.06%** of QB draws with
at least one completion have cmp > att; **0.96%** of QB draws with at least one
passing TD have ptd > cmp. This is a per-player defect only — the team totals
close exactly (section 2), so it is invisible in every team-level check the
pipeline runs, and it lands squarely on the per-player numbers the board sells.

### F1 — the sealed artifact stores the carry vector the game did *not* use

`nfl/production/run_forecast.py:1242` builds the `team_volume` matrices from
`fx['_team_volume']`, which is D1's raw level. The SC1-coupled carry vector —
the one A1 actually partitioned — lives in `fx['_coupled_team_carries']`
(`run_forecast.py:773`) and reaches the engine only as `team_carries_override`.
`football_engine.py:1018` names this exact trap for its own payload:

> The level the GAME used, not the level D1 drew: with SC1 live they are
> different vectors and storing the unused one would make every downstream
> dependence diagnostic read the wrong carry index.

The draws artifact does the thing the comment warns against. The proof is I12:
SC1 returns a vector on which `carries >= scrambles` holds by construction, yet
the stored `team_volume/team_carries` is exceeded by the team's own QB-room
scramble total in 9 cells — all of them TEAM TB, draw index 915, scrambles 6
against team_carries 5.2573, reproducing across 9 different TB_CIN runs because
they share a seed.

**Consequence for I13.** The 6,186 cells where RB carries plus QB rush
opportunity exceed team carries are measured against the wrong denominator.
They cannot today be attributed between "the allocation double-counts a carry"
and "the artifact stored the wrong vector". Both are real candidates: A1
subtracts the QB *scramble* level from the budget and allocates `designed_qb`
as its own category, while `qb/rush_opp` is a separate QB-V1 draw of
`scrambles + designed runs` — two owners of designed quarterback runs. F1 must
be closed before I13 can be read as an allocation defect. The invariant is
still an invariant; what is unavailable is the attribution.

### F2 — an unconsumed team-target array is published beside the consumed one

Under C3 the target budget is the quarterbacks' attempts, and the engine says so
in the artifact it builds: `d1_team_targets_unused: True`
(`football_engine.py:485`). `team_volume/team_targets` is nevertheless sealed
into every npz on the same shared draw index, and it **disagrees with the dealt
targets in 38,464 of 94,000 team-draws (40.9%)**. Worst:
`2026_01_TB_CIN/post_inactives_V1_CANDIDATE/811718e6e7eca2a5`, TEAM CIN, draw
789 — 53 dealt player targets against a D1 team-target level of 29.79.

Nothing in `player_draws_manifest.json` marks the array unused. A consumer
reading the manifest at face value gets two answers to one football question and
no way to tell which one the run consumed. This is **not** an invariant
violation (see rejected list) — it is an artifact-hygiene defect.

### F5 — three written accounting guards never reach the sealed verdicts

Census of `accounting_verdicts[].code` over all 101 artifacts:

```
101 DRAW_ARTIFACT_VERIFIED        101 QB_DROPBACK_IDENTITY_HOLDS
101 DRAW_ENCODING_LOSSLESS        101 QB_LAYER_KNOWN_LIMITATIONS
101 DRAW_INDEX_SHARED             101 QB_DRAW_ACCOUNTING_HOLDS
101 DRAW_SET_PRESENT              101 QB_TEAM_ACCOUNTING_MEASURED
101 SUMMARY_MATCHES_DRAWS         101 A1_RUSH_ALLOCATION
101 NONQB_LAYERS_UNAVAILABLE      101 SC1_COHERENT
101 QB_ALLOCATION_RESIDUAL_NONE    55 QB_INACTIVE_OWNERSHIP_NOT_ESTABLISHED
101 CROSS_LAYER_RECONCILIATION_NOT_RUN
                                   41 QB_INACTIVE_OWNS_NOTHING
```

* `accounting.reconcile_rushing` — which contains `qb_rush_contained_in_other`,
  precisely the I13 identity — emits neither `RUSHING_DRAW_ACCOUNTING_OK` nor
  `RUSHING_DRAW_ACCOUNTING_VIOLATED` in **any** sealed artifact. It is computed
  into `g['accounting']['rushing']` and never surfaces.
* `accounting.reconcile_nonqb` likewise: no `NONQB_DRAW_ACCOUNTING_*` verdict
  anywhere.
* `CROSS_LAYER_RECONCILIATION_NOT_RUN` is present in **all 101** runs, including
  the 33 that *do* carry the receiving draw set it says was not supplied.

`SC1_COHERENT` is emitted unconditionally after `couple()` returns PASS
(`run_forecast.py:355`); it attests to the vector SC1 returned, not to the
vector that was sealed, which is why it reads PASS in the nine runs I12 fails.

### F6 — officially inactive quarterbacks holding dropbacks (already known)

Five sealed SF@LA `post_inactives` runs give positive dropbacks to two
officially inactive quarterbacks:

| Run | Row | Team | Depth | p(db > 0) | max db |
|---|---|---|---|---|---|
| `2026_01_SF_LA/post_inactives_V1_CANDIDATE{,_R5,_R6,_R7,_R8}` | `00-0040589` | SF | QB3 | 0.255 | 25 |
| same five | `00-0041568` | LA | QB3 | 0.226 | 12 |

This is **defect D04** in `nfl/research/live/OPEN_DEFECTS.json`, recorded as
repaired at commit 622fdd5. These five boards were sealed 2026-09-11T00:13:09Z
at `b5e5a43+dirty[13]`, before the repair, so they are the pre-repair
artifacts, not a regression. D04's open item reads "still needed: a post-repair
board for a game with an inactive QB to confirm end to end" — that is still
owed, and this scan cannot discharge it.

One detail worth adding to D04: these five runs are **exactly** the five of 101
that carry *neither* `QB_INACTIVE_OWNS_NOTHING` nor
`QB_INACTIVE_OWNERSHIP_NOT_ESTABLISHED`. The guard did not report a failure; it
reported nothing at all, and an absent verdict read as an untroubled run is the
same defect class the project already pays for most often.

No non-QB inactive receives volume anywhere (I14, 75,000 cells).

### F4 — per-QB passing yards are not integers

`pyds_q = w * team_pyds` is a continuous share of an integer team total, so
**22.75%** of the 324,000 stored `qb/pyds` cells are non-integer (e.g. 93.0638
yards). `receiving/receiving_yards` in the same artifact is `int16`. Two
representations of the same declared quantity. Reported, not enforced — see the
rejected list.

---

## 4. Proposed invariants

All fourteen are in `test_draw_coherence.py.proposed`, each carrying a
`why_impossible` string. Summarised here with the reason each is an
impossibility rather than a preference.

| # | Invariant | Why it is IMPOSSIBLE, not merely unlikely |
|---|---|---|
| **I1** | `cmp <= att` per QB per draw | A completion *is* an attempt. Every completed forward pass is scored as an attempt by the same passer. cmp > att is a completion that was never thrown. |
| **I2** | `ptd <= cmp` per QB per draw | A passing touchdown is a completed pass into the end zone, hence a completion. |
| **I3** | `cmp == 0 ⟹ pyds == 0` per QB per draw | Passing yards accrue only on completions. No completion in a draw means exactly zero passing yards in that draw. |
| **I4** | `db == att + sacks + scr` per QB per draw | The layer defines a dropback as ending in exactly one of the three. A partition, not an approximation. Already asserted by `qb_v1.identity_check`; the invariant matters because the C3 credit runs *after* that check. |
| **I5** | every count matrix ≥ 0 | A negative count of attempts, catches or carries is not a small count. |
| **I6** | `receptions <= targets` | A reception is a target. |
| **I7** | `receiving_td <= receptions` | A receiving touchdown is a reception. |
| **I8** | `receptions == 0 ⟹ receiving_yards == 0` | Receiving yards accrue on catches. **Deliberately the zero identity and not `yards >= 0`** — see rejected list. |
| **I9** | `rushing_td <= rint(carries)` | A rushing touchdown requires a carry in the same draw. |
| **I10** | `Σ player targets <= Σ QB attempts`, per team per draw | Every target is a pass that team threw in that draw. This is the budget C3 actually consumes, so it is the closure worth enforcing. |
| **I11** | `Σ QB dropbacks == rint(team dropback budget)`, per team per draw | Under R2 the level is an integer apportionment and every dropback has exactly one passer. |
| **I12** | `Σ QB scrambles <= team carries`, per team per draw | A scramble *is* a rush attempt — the repo's own measurement: `team_carries >= scrambles` in 3,230 of 3,230 historical team-games. A team cannot scramble more often than it ran the ball. |
| **I13** | `Σ RB carries + Σ QB rush opportunity <= team carries`, per team per draw | RB carries and QB rush attempts are disjoint subsets of the team rush-attempt count. Exceeding the total means one carry was credited twice. Conservative by construction: WR/TE carries and kneels sit on the right-hand side only, never the left. |
| **I14** | an officially inactive **non-QB** owns zero volume in every draw of a `post_inactives` run | A player on the official gameday inactive list cannot take a snap, and no rule creates an exception at any position other than quarterback. Conditional on the run's own declared information set — a `pre_inactives` run is explicitly out of scope. |

Three notes on how these are written so they cannot become vacuous or
positional:

1. **A check over zero cells is not a passing check.** `main()` returns exit
   code 2 if it scanned no run or no draw, and every invariant reports its own
   `cells_checked` so a silently empty check reads `VACUOUS`, never `PASS`.
   This mirrors `NONQB_ACCOUNTING_VACUOUS` in `accounting.py`.
2. **Rows are resolved through gsis ids only** (`_rows_for_team`). No integer
   row index crosses a layer boundary.
3. **I12 and I13 are gated on F1.** They are correct invariants, but until the
   artifact stores the carry vector the game used, a failure of either cannot be
   attributed. Adopting them today would correctly refuse the current artifacts;
   fixing F1 first is the cheaper order.

---

## 5. Rejected — checks that are preferences, not invariants

| Candidate | Rejected because |
|---|---|
| `Σ player targets <= rint(team_volume/team_targets)` | Fails in 38,464 of 94,000 team-draws, but C3 declares `d1_team_targets_unused: True`. The array is not the budget. The consumed closure is I10 and it holds. Recorded as artifact-hygiene defect F2, not as a broken identity. |
| `receiving_yards >= 0` | `accounting.py` already records that this identity **was** the defect: RC1 resamples real per-catch gains and a catch for a loss is ordinary football. 8,213 negative cells are legitimate; the rehearsal's worst was −8 yards. I8 is the correct form. |
| `qb/pyds` integer-valued | Realised passing yards are integers and 22.75% of stored cells are not, but a continuous predictive representation of an integer quantity is a legitimate modelling choice. Reported as F4, not enforced. |
| `team_carries` integer-valued | The D1 level is continuous by declaration and `rushing_a1` already *refuses* a non-integer budget unless the caller declares `level_rounding`. Rounding is a declared decision. |
| "a WR1 should rarely get zero targets" | A calibration preference. 72 receiving rows are identically zero across every draw; every one is WR3–WR7, TE3–TE4 or RB2–RB3. No depth rank makes a target compulsory. |
| `officially inactive QB owns zero dropbacks` | **Rejected as an absolute invariant**, kept as a diagnostic. The NFL emergency-third-QB rule lets a club designate a quarterback who is *on* the inactive list and may enter. Both observed violators are QB3, which is exactly the population the rule covers. `nfl/tools/inactives_segmentation.py` already preserves "(emergency third QB)" as an annotation, and WS05 records that no third-QB rule is modelled. Extraordinarily improbable is not impossible. I14 covers every other position. |
| `qb/rush_opp <= qb/scr + designed-run budget` | Not checkable from the artifact: the A1 category counts are not stored, so the designed-run budget is unavailable. Named as owed rather than approximated. |
| predicted totals agreeing with a sportsbook line | Named so it never gets added. A price is an external comparison, not a coherence constraint. |

---

## 6. Evidence ceiling

What this scan can and cannot support.

* **It is a coherence audit, not a forecast evaluation.** Nothing here says any
  projection is good or bad. An artifact can be perfectly coherent and worthless.
* **One week, one slate.** 14 games, all `2026_01_*`. The 101 runs are *not* 101
  independent observations: they are ~4–10 configuration variants per game over
  the same players and, in the four TB_CIN examples of I12, the same seed and
  the same draw index. Counting cells across runs counts correlated evidence.
  The honest unit for "does this defect exist" is **7 games** for I1/I2/I3/I13
  and **1 game** for I12.
* **The receiving and rushing layers exist in only 33 of 101 runs** (defect D03
  deferred the appearance layer for the twelve-game Sunday slate). Every
  non-QB check is therefore measured on a third of the frame, and a clean result
  on I6–I9 is a clean result on 33 runs, not on 101.
* **I13's 6,186 cells are not attributable.** F1 confounds them. The count is a
  count of artifact incoherence; it is not evidence of the size of any
  allocation defect.
* **F1 is inferred from a code read plus nine cells.** The coupled vector is not
  stored, so it cannot be differenced against the raw one. The nine cells prove
  the stored vector is not SC1-coherent; the code read explains why. Neither
  alone would be enough.
* **The inactive check is only as good as the list.** It uses
  `INACTIVES_INGESTION.json` `POST_INACTIVES_COMPLETE`. DAL_NYG has no usable
  list (quarantined discovery), so that game contributes nothing to I14, and 4
  runs were scanned without one.
* **No claim of adequacy is made anywhere.** The eight PASS results are "zero
  violations observed in N cells", not "correct", "stable" or "closed". No
  equivalence margin was predeclared and no TOST was run, and a check that has
  not failed yet is not a check that cannot fail.
* **Nothing here is scored against a realised outcome.** Every defect is defined
  against the draws themselves, so none of it is manufactured by conditioning on
  what actually happened in Week 1.

---

## 7. Recommended order of work (for whoever owns the fix)

1. **F1 first** — seal `fx['_coupled_team_carries']` as `team_volume/team_carries`
   (or seal both, named distinctly). It is a one-line ownership question, it
   unblocks the attribution of I13, and every carry diagnostic is reading the
   wrong vector until it is done.
2. **F3 next** — `credit_to_passers` needs a per-passer cap. A multinomial is
   the wrong tool for a constrained allocation; whatever replaces it must still
   close on the team total exactly, and it must not be a clip applied afterwards
   (the four repairs OWN-8 forbids). This is a modelling change and needs a
   pre-registration, not a patch.
3. **F5** — surface `reconcile_rushing` and `reconcile_nonqb` into
   `accounting_verdicts`, and make `CROSS_LAYER_RECONCILIATION_NOT_RUN` conditional
   on the receiving draws genuinely being absent. A guard that is computed and
   never reported is a guard that does not exist.
4. **F2** — either drop `team_volume/team_targets` from the C3 artifact or carry
   a manifest flag saying it was not consumed.
5. **F6** — produce the post-repair board D04 still owes.
