# WS-O — classification of the proposed draw invariants

**CODE CHANGED: NO.** Nothing outside `nfl/research/remediation/ws_o/` was
written. `football_engine.py`, `artifact.py` and `nfl/tests/test_draw_coherence.py`
were read and not touched; they are WS-B's. `run_forecast.py` (WS-D),
`layers.py` (Q9-hashed) and the WS-C/E/F/G files were read only.

**Independence.** Every number below was re-derived from the sealed artifacts
with `python3.12` at HEAD `837d52f`, not copied from `WAVE0_BASELINE.json` or
from WS10. WS-B's in-progress `nfl/tests/test_draw_coherence.py` was
deliberately **not read**: the point of running WS-O concurrently is that the
classification and the wiring are produced from the same evidence and not from
each other.

---

## 0. The rule applied, stated before the verdicts

An invariant asserts an **impossible state**. A violation is then a proof that
the producing code is wrong, and refusing is the only coherent response.

Four buckets:

| Bucket | Test it must pass |
|---|---|
| **HARD_IMPOSSIBLE** | The state cannot occur in a football game under the rules and the scoring conventions. No appeal to this model is needed. |
| **CONTRACT_DEPENDENT** | The state is possible in the world, and impossible only because this system declares a definition, an ownership graph or an information set. Enforceable **where that contract is stated and cited**; it moves the moment the contract moves. |
| **DIAGNOSTIC_ONLY** | Worth measuring. Extraordinarily improbable, undesirable, or a known limitation. Never a refusal. |
| **REJECTED** | A preference, a football intuition, or an assumption wearing an invariant's clothes. |

Two corollaries used repeatedly below:

1. **Extraordinarily improbable is not impossible.** A model that produces a
   five-quarterback game is badly calibrated, not incoherent.
2. **A check that had to round, clip or `rint` its way to a verdict has not
   established that verdict.** An undeclared rounding inside an invariant is
   the invariant being shaped to pass. This disposes of I9 below.

---

## 1. Baseline re-derivation

Independent scan of all 101 sealed `player_draws.npz` under
`nfl/research/live/2026_01_*/`, rows joined through
`manifest['layers'][<layer>]['row_ids']` and `board.json['players'][].team`,
never positionally.

101 runs · 115,000 draws · 33 runs carry all four layers · 68 carry `qb` +
`team_volume` only.

| Check | WAVE0 | WS-O | Agrees |
|---|---|---|---|
| I1 `cmp > att` | 5,278 | **5,278** (33 runs) | yes |
| I2 `ptd > cmp` | 731 | **731** | yes |
| I3 `pyds != 0` with `cmp == 0` | 11,616 | **11,616** | yes |
| I4 `db != att + sacks + scr` | 0 | **0 / 838,000** | yes |
| I5 any count matrix negative | 0 | **0 / 7,542,000 QB count cells** | yes |
| I6 `receptions > targets` | 0 | **0 / 1,396,000** | yes |
| I7 `receiving TD > receptions` | 0 | **0 / 1,396,000** | yes |
| I8 `rec yards != 0` with 0 receptions | 0 | **0 / 1,396,000** | yes |
| I9 `rushing TD > rint(carries)` | 0 | **0 / 381,000** — *and this is the artefact, see §4* | yes, and misleading |
| I10 Σ targets > Σ QB attempts | 0 | **0 / 94,000 team-draws** | yes |
| I11 Σ db != rint(budget) | — | **0 / 230,000 team-draws** | — |
| I12 Σ scrambles > team carries | — | **9 / 230,000**, 9 runs | yes |
| I13 Σ RB carries + Σ QB rush > team carries | — | **6,186 / 94,000**, 33 runs | yes |
| I14 inactive non-QB with volume | — | **0 / 75,000**, 75 rows, non-vacuous | yes |
| negatives `qb__pyds` | 2,261 | **2,261** | yes |
| negatives `qb__ryds` | 2,821 | 2,821 | yes |
| negatives `receiving__receiving_yards` | 8,213 | **8,213** | yes |

Every baseline figure reproduces exactly. Two decompositions the baseline does
not carry, and both change a classification:

* **All 2,261 negative `qb/pyds` cells are in the 68 QB-only runs**
  (0 of 324,000 four-layer cells, 2,261 of 514,000 QB-only cells), and **every
  one of them has `cmp >= 1`** (minimum 1, mean 5.95 completions). Worst cell
  −76.0 passing yards. Team Σ receiving yards is **never** negative
  (0 of 94,000 team-draws).
* **I1/I2/I3 are zero in all 68 QB-only runs and non-zero in all 33 C3 runs.**
  The QB layer's own joint draw is coherent; the C3 credit breaks it.

---

## 2. The classification

Twenty-one rows: WS10's fourteen, plus seven candidates WS10 did not propose
(N-prefixed). "Observed" is WS-O's own count over the 101 sealed runs.

| # | Invariant | Class | Observed | One-line impossibility argument |
|---|---|---|---|---|
| **I1** | `cmp <= att` per QB per draw | **HARD_IMPOSSIBLE** | 5,278 FAIL | Every completed forward pass is scored as an attempt by the same passer; completions are a subset of attempts, so `cmp > att` is a completion that was never thrown. |
| **I2** | `ptd <= cmp` per QB per draw | **HARD_IMPOSSIBLE** | 731 FAIL | A passing touchdown is a completed pass into the end zone; it is a completion, so the count cannot exceed the completions it is drawn from. |
| **I3** | `cmp == 0 ⟹ pyds == 0` | **HARD_IMPOSSIBLE** | 11,616 FAIL | Passing yards are the yards gained on completed passes. Over an empty set of completions that sum is exactly zero; there is no other mechanism that credits a passer yardage. (Sack yardage cannot supply one — it is not charged to a player's passing yards, and this system models no sack yardage at all: `qb_v1.FIELDS` has none.) |
| **N1** | `cmp + int <= att` per QB per draw | **HARD_IMPOSSIBLE** | **5,929 FAIL, 651 of them invisible to I1** | An interception is an incomplete attempt. Completions and interceptions are disjoint subsets of attempts, so their sum cannot exceed the attempts. Observed cell: `att=6, cmp=6, int=1` — every attempt completed and one of them intercepted. |
| **N2** | `ptd <= att` | **HARD_IMPOSSIBLE** | 22 FAIL | Implied by I1 ∧ I2 once both hold; listed because it fires on the current artifact independently and costs nothing. |
| **I4** | `db == att + sacks + scr` | **CONTRACT_DEPENDENT** | 0 / 838,000 | "Dropback" is not an official statistic. The three-way partition is **this layer's definition** (`qb_v1.identity_check`, `nfl/production/qb_v1.py:265`), declared HARD as `qb_dropback_identity` in `artifact.INVARIANTS`. In the world a dropback can also end in a spike, an aborted snap, or a play negated by penalty. See §6 for a contradiction in the module's own statement of it. |
| **I5** | every **count** matrix `>= 0` | **HARD_IMPOSSIBLE** | 0 | A negative count of a discrete football event is not a small count. The *scope* is contract-dependent and must be read from `nfl/product/metrics.py` `SUPPORTED[...]['kind'] == 'count'`, not from a hand-typed list or from dtype — see §5.1. |
| **I6** | `receptions <= targets` | **HARD_IMPOSSIBLE** | 0 / 1,396,000 | A reception is a target; the catcher of a tipped ball is credited both. Already the project's own written identity (`accounting.NONQB_IDENTITIES`, `receptions_within_targets`). |
| **I7** | `receiving_td <= receptions` | **HARD_IMPOSSIBLE** | 0 / 1,396,000 | A receiving touchdown is a reception. A score on a lateral or a recovery is not a receiving touchdown. |
| **I8** | `receptions == 0 ⟹ receiving_yards == 0` | **HARD_IMPOSSIBLE** | 0 / 1,396,000 | Receiving yards accrue on catches. This is the project's own identity, and `accounting.py:68-75` records that the **non-negativity** form was the defect it replaced. |
| **I9** | `rushing_td <= carries` | **HARD_IMPOSSIBLE in football; NOT EVALUABLE on this artifact** | 0 with `rint`, **323 without it** | A rushing touchdown requires a carry by that player in that draw — genuinely impossible to violate. But `rushing/carries` is stored continuously (241,584 of 381,000 cells non-integer), so the cell-level verdict is decided by a rounding rule the artifact does not declare. See §4. Correct state today: **DEFERRED with an `owed` payload**, never PASS. |
| **N4** | `qb/rtd <= qb/rush_opp` | **HARD_IMPOSSIBLE** | 0 / 838,000 | A quarterback's rushing touchdown requires one of his own rush attempts. Free to wire; `rush_opp` is an integer array so it has none of I9's problem. |
| **N7** | `qb/rush_opp == 0 ⟹ qb/ryds == 0` | **HARD_IMPOSSIBLE** | 0 / 838,000 | Rushing yards accrue on rush attempts. The QB-side mirror of I8, currently clean and currently unenforced. |
| **I10** | Σ player targets `<=` Σ QB attempts, per team-draw | **CONTRACT_DEPENDENT** | 0 / 94,000 | **Not** hard: a halfback or receiver pass is a team pass attempt that is not a QB attempt, so a team can have more targets than QB attempts in a real game. It is impossible only because C3 declares the targeted-throw budget to be the quarterbacks' attempts (`shared_pass.targeted_throws`, `shared_pass.py:107`, and `football_engine.py:485` `d1_team_targets_unused: True`). WS10's stated reason — "every target is a pass that team threw" — supports `Σ targets <= team attempts`, which is not what the check computes. |
| **I11** | Σ QB dropbacks `==` `rint(team dropback budget)` | **CONTRACT_DEPENDENT, and conditional** | 0 / 230,000 | A team's dropbacks are the sum of its passers' dropbacks by construction; the *budget* is a modelling object. The **equality** form is R2-specific: `football_engine.py:861-866` passes `integer_level=bool(qb.get('r2'))` and says so — outside R2 the declared identity is `<=` against a float level. Wiring the equality unconditionally would refuse a lawful non-R2 run. |
| **I12** | Σ QB scrambles `<=` team carries, per team-draw | **HARD_IMPOSSIBLE** | 9 / 230,000 | A scramble is a rush attempt, hence a subset of the team's rush attempts (repo measurement: 3,230 of 3,230 historical team-games). Already declared HARD as `scramble_carry_coherence`. The 9 violations exist because the guard attests to the vector SC1 **returned**, not the vector the artifact **sealed** — see §3. |
| **I13** | Σ RB carries + Σ QB rush opportunity `<=` team carries | **HARD_IMPOSSIBLE in football; NOT EVALUABLE on this artifact** | 6,186 / 94,000 | RB carries and QB rush attempts are disjoint subsets of the team rush-attempt count, so their sum cannot exceed it — impossible, not merely unlikely. But the artifact seals `fx['_team_volume']` (raw D1) while the engine partitioned `fx['_coupled_team_carries']` (`run_forecast.py:839` vs `:855`), so the two sides of the inequality come from different draws of one quantity. A failure today is not attributable. **DEFERRED at artifact level, enforceable in-engine now.** |
| **N5** | Σ QB rush opportunity `<=` team carries, per team-draw | **HARD_IMPOSSIBLE, same F1 caveat** | **365 / 230,000, 59 runs** | The QB-only half of I13. Strictly weaker, so strictly safer, and it needs no receiving or rushing layer — which is why it reaches **59** runs where I13 reaches 33. WS10 did not propose it. |
| **N3** | `qb/scr <= qb/rush_opp` per QB per draw | **CONTRACT_DEPENDENT** | 0 / 838,000 | A1 declares `qb_rush_opportunity = scrambles + designed_qb` with `designed_qb >= 0` (`rushing_a1.py:842`), so scrambles cannot exceed it. WS10 named the *other* direction as unavailable and stopped; this direction is available and free. |
| **I14a** | officially inactive **non-QB** owns zero volume, `post_inactives` runs | **HARD_IMPOSSIBLE** (conditional on a resolved list) | 0 / 75,000 over 75 rows | A player on the final gameday inactive list may not participate, and no rule creates an exception at any position other than quarterback. The data-dependence is in **applicability**, not in the impossibility: with no resolved list the answer is NOT_APPLICABLE or DEFERRED, never PASS. |
| **I14b** | officially inactive **QB** owns zero dropbacks | **CONTRACT_DEPENDENT — and already gating** | 2,405 cells, 5 runs | Not impossible: the emergency-third-QB rule lets a designated inactive quarterback enter. Impossible **under this system's declared contract**: WS05 records no third-QB rule is modelled, D04's repair zeroes inactive QB rows before R2/Hamilton, and `artifact.INVARIANTS['qb_inactive_owns_nothing']` already declares it HARD. See §7 — I partly overturn WS10 here. |

**Rejected outright — §5.**

---

## 3. Where each HARD invariant must execute

### 3.1 The defect that defines the requirement

`qb_v1.forecast` already refuses `cmp > att` (`nfl/production/qb_v1.py:248`) and
`qb_v1.identity_check` already checks the dropback partition. Both run on `D`,
the QB layer's own output. The C3 credit then **overwrites** `cmp`, `pyds` and
`ptd` at `football_engine.py:903-905`. So `QB_DRAW_ACCOUNTING_HOLDS` and
`QB_DROPBACK_IDENTITY_HOLDS` appear in 101 of 101 sealed artifacts while 5,278
sealed cells violate the first of them.

The live proof that classification alone does not save you:
`qb_cross_layer_reconciliation` is **HARD** and reads **PASS in all 101
artifacts**, because it compares *team totals*, which close exactly. A hard
invariant evaluated on the wrong aggregate, or before the last write, is
indistinguishable from no invariant at all.

### 3.2 The three candidate points

| | Point | What exists there |
|---|---|---|
| **P1** | `football_engine.py`, immediately after the credit loop ends (after line 905, before `g['c3'] = c3`) | `qb['draws']` post-credit. The four-layer payload is assembled later. |
| **P2** | `run_forecast._draws()`, on the matrices handed to `DrawSet.add_layer` (`run_forecast.py:1286-1345`) | **All four layers as the exact arrays that get encoded**, including `fx['_team_volume']`. |
| **P3** | after `DrawSet.write()` and `draws_artifact.verify()` re-read | the bytes that publish. |

`draws_artifact.encode` is exact-or-refuse, so P2 and P3 carry identical values;
P3 costs a re-read and buys proof rather than inference.

### 3.3 Required placement, per HARD invariant

| Invariant | Required point | Why earlier is insufficient |
|---|---|---|
| I1, I2, I3, N1, N2 | **P1 at the earliest, P2 preferred** | `cmp`, `pyds` and `ptd` do not reach their published values until `football_engine.py:903-905`. Any check on `D` (the qb_v1 output) is the guard that already produced 101 false PASSes. N1 additionally reads `int`, which C3 does **not** re-credit — so it must be evaluated on the *mixture* of post-credit `cmp` and original `int`, which exists only at P1/P2. |
| I5, I6, I7, I8, N4, N7, I14a | **P2** | These layers are not mutated after the engine returns, so P1 would also be correct for them — but only by an alias that no checkpoint enforces. P2 is the placement that stays true if a later stage ever touches an array. |
| I12, N5, I13 | **P2 or P3, never in the engine** | The engine reads the SC1-coupled carries (`_team_carries`, `football_engine.py:255-259`); the artifact seals the raw D1 vector (`run_forecast.py:1334`). An engine-side carry invariant would attest to a vector that is not published — the same mistake as `SC1_COHERENT`, which is emitted unconditionally after `couple()` returns (`run_forecast.py:355`) and reads PASS in all nine runs I12 fails. |

**The adversarial point for adjudication.** WS-B's declared file list is
`football_engine.py`, `artifact.py` and `nfl/tests/test_draw_coherence.py`;
`run_forecast.py` belongs to WS-D. Points P2 and P3 live in `run_forecast.py`.
If the wiring lands entirely inside `football_engine.py`, then:

* the per-QB invariants (I1-I3, N1-N2) are **correctly placed** — the engine
  mutates in place and `fx['_qb_draws_out']` is bound to the same dict
  (`run_forecast.py:435`), which is why the violations are visible in the
  sealed npz at all; but the correctness rests on an **alias**, not on a
  checkpoint, and nothing fails loudly if a future stage copies instead of
  mutating;
* the carry invariants (I12, N5, I13) are **incorrectly placed** and will read
  PASS on a vector the artifact does not contain. That is the defect being
  remediated, reproduced one layer along.

The clean resolution, which needs no ownership change: put the checker in a
**new module** (for example `nfl/production/draw_coherence.py`) that takes
matrices and returns `Outcome`s, call it from the engine for the QB rows, and
hand WS-D a one-line call site for P2. The test file then calls the same
function against sealed npz files, so the suite and the pipeline cannot drift.

### 3.4 Wiring into `artifact.INVARIANTS` — two traps

1. **Every declared invariant must carry a verdict in every model-sourced
   artifact** (`assert_hard_invariants` → `INVARIANT_VERDICT_MISSING`). 68 of
   101 runs have no receiving or rushing layer. I6, I7, I8, I9, I13, I14a must
   therefore emit `NOT_APPLICABLE` on those runs — which
   `assert_hard_invariants` already counts and names separately from PASS.
   Emitting PASS there would be the "vacuous check read as a clean check" error;
   omitting the verdict would refuse all 68 runs.
2. **A verdict may not claim a class the table does not give it**
   (`INVARIANT_MISCLASSIFIED`). So I14b cannot be recorded as a diagnostic while
   `qb_inactive_owns_nothing` is declared HARD — the artifact would refuse. This
   is the machinery doing its job, and it is why §7's disagreement matters.

---

## 4. I9, and the rounding that manufactured its PASS

WS10 reports I9 as HOLDS on 381,000 cells. The check is
`rushing_td > rint(carries)`.

| Form | Violating cells |
|---|---|
| `rushing_td > rint(carries)` (WS10's form) | **0** |
| `rushing_td > carries` (no rounding) | **323** |
| `rushing_td > 0` with `carries < 1.0` | **306** |
| `rushing_td > 0` with `carries < 0.5` | 0 |
| `carries` not integer-valued | **241,584 of 381,000 (63.4%)** |

Every violation is a whole touchdown sitting on a fractional carry between 0.5
and 1.0, and `rint` is what makes it disappear. WS10 rejected
`team_carries integer-valued` on the correct ground that *"rounding is a
declared decision"* — `rushing_a1.allocate` refuses a non-integer budget unless
the caller passes `level_rounding`. The same standard applied to I9 disqualifies
it: the rounding inside the check is **not declared anywhere**, and it is
load-bearing for the verdict.

Why the carries are fractional: A1 partitions the rush-play budget with one
multinomial, so its category counts are integers, but the artifact's
`rushing/carries` is the per-player P4C simplex share of the RB budget
(`run_forecast.py:1318`, "P4C simplex allocation over the A1 running-back
budget"), which is a share × level product.

And there is a contract violation underneath it:
`nfl/product/metrics.py:75` declares `('rushing', 'carries')` as
`{'label': 'Carries', 'kind': 'count', 'status': MODELED}`, and the board
publishes it with count thresholds (`9.5+`, `12.5+`). **A metric declared a
count whose draws are non-integer in 63% of cells is a violated contract on its
own**, independent of I9.

So: I9 is a true impossibility that this artifact cannot currently answer. It
must be recorded DEFERRED with an owed payload naming the integerisation
decision — not PASS, and not FAIL either, since the 323 cells are evidence about
the representation rather than about a touchdown without a carry.

---

## 5. Rejected

### 5.1 WS10's rejections — confirmed

| Candidate | WS-O verdict |
|---|---|
| `Σ player targets <= rint(team_volume/team_targets)` | **REJECTED, confirmed.** C3 declares `d1_team_targets_unused: True`; the array is not the consumed budget, so 38,464 "violations" measure nothing. But this leaves an unlabelled unused array in every sealed npz. Re-filed below as a manifest-hygiene invariant rather than dropped. |
| `receiving_yards >= 0` | **REJECTED, confirmed.** A catch for a loss is ordinary football, and `accounting.py:68-75` records that this exact identity **was** the defect. 8,213 negative cells are lawful. I8 is the correct form. |
| `qb/pyds` integer-valued | **REJECTED as an invariant, confirmed.** A continuous predictive representation of an integer quantity is a modelling choice. Note it is `kind: 'yards'`, so unlike `rushing/carries` it contradicts no declared kind. |
| `team_carries` integer-valued | **REJECTED, confirmed.** The D1 level is continuous by declaration and rounding is a declared decision. *Per-player* carries are a different question — §4. |
| "a WR1 should rarely get zero targets" | **REJECTED, confirmed.** A calibration preference. No depth rank makes a target compulsory. |
| `qb/rush_opp <= scr + designed-run budget` | **REJECTED as unavailable, confirmed** — A1's category counts are not sealed. The reverse containment `scr <= rush_opp` **is** available and is adopted as N3. |
| predicted totals agreeing with a sportsbook line | **REJECTED, and not negotiable.** A price is an external comparison, never a coherence constraint. Recorded so it is never added. |

### 5.2 Rejected by WS-O — candidates that look like invariants and are not

Each of these fires on the current artifact and each is lawful football:

| Candidate | Observed | Why REJECTED |
|---|---|---|
| `ptd > 0 ⟹ pyds > 0` | 627 cells, 48 runs | A touchdown pass gains at least one yard, but total passing yards is a **sum** that also contains completions for a loss. One 1-yard score plus two screens for −5 is a lawful negative line with a passing touchdown. |
| `receiving_td > 0 ⟹ receiving_yards >= 0` | 494 cells, 33 runs | Identical argument on the receiving side. |
| `qb/rtd > 0 ⟹ qb/ryds >= 0` | 467 cells, all 101 runs | Kneels are rushing attempts for negative yards and sack yardage is not charged to rushing. A 1-yard score plus three kneels is a lawful negative rushing line with a rushing touchdown. |
| `cmp > 0 ⟹ pyds != 0` | 236 cells | A completion for exactly zero yards is ordinary. |
| `receptions > 0 ⟹ receiving_yards != 0` | 4,400 cells | Same. |
| "no more than two quarterbacks take a dropback for one team" | ≥3 QBs in **22.0%** of 230,000 team-draws; **5 QBs in 632** | A five-quarterback game has, as far as the modern record goes, never happened. It is not impossible. **DIAGNOSTIC_ONLY** — and it is a sharp one, because it is the same mechanism as the `multi_qb_over_prediction` limitation `qb_v1` already declares. |
| "an inactive QB3 may hold dropbacks only in draws where QB1 and QB2 hold none" | QB1 also has dropbacks in **70.2%** (SF) / **76.5%** (LA) of the draws where the inactive QB3 does | Tempting, and wrong: an emergency QB3 enters after both are hurt, and the men he replaced may already have thrown. Possible in the world, so not an invariant. Keep the *number* as the diagnostic that shows D04's residue is a rotation, not an emergency. |

---

## 6. Negative passing yards — independent verdict

**Verdict: not an invariant. DIAGNOSTIC_ONLY, with the enforceable part already
covered by I3.**

Four legs, in order of weight.

1. **It is possible in football.** A player's official passing yards are the
   yards gained on his completed passes; sack yardage is not deducted from them,
   and this system models no sack yardage at all (`qb_v1.FIELDS` carries
   `sacks` as a count and no yardage field). A passer whose only completions are
   screens and checkdowns tackled behind the line finishes with negative gross
   passing yards. Rare; not impossible.

2. **The project's own contract already puts it in the lawful class.**
   `nfl/product/metrics.py` declares `qb/pyds` as `kind: 'yards'` — the same
   class as `receiving/receiving_yards`, for which `accounting.py:68-75` records
   that asserting non-negativity **was the defect**. Enforcing `pyds >= 0` would
   re-adopt, on the passing side, the identity the project already withdrew on
   the receiving side.

3. **It would contradict a HARD invariant already in the table.**
   `qb_cross_layer_reconciliation` asserts team passing yards == player
   receiving yards on the same draw index. Receiving yards are lawfully
   negative. A floor on the passing side is therefore not merely unsupported,
   it is **incoherent with a gate that is already wired**.

4. **The evidence says the negatives are not where the defect is.** All 2,261
   negative `qb/pyds` cells are in the 68 QB-only runs; the 33 C3 runs have
   zero, because `credit_to_passers` computes `w * team_pyds` with
   `team_pyds = Σ receiving yards`, which is non-negative in all 94,000
   team-draws. And every negative cell has `cmp >= 1` — so **not one of them is
   reachable by I3**, and I3's 11,616 violations are a disjoint problem.

What is left is a magnitude question, and it belongs in the diagnostic, not the
gate: the worst cell is **−76.0 passing yards on a mean of 5.95 completions**,
roughly −12.8 yards per completion sustained across a game. That is a tail the
QB layer's own yardage draw produces and no plausible game does. The honest
instrument is a recorded distribution — count, minimum, and yards-per-completion
at the extreme — reported on every run, with no refusal attached, and no
threshold invented to make one.

**What I would refuse to write:** `pyds >= 0`, `pyds >= -k` for any k, or a
clip. A clip would be a post-hoc correction of the model's own output, which is
one of the four repairs OWN-8 forbids.

---

## 7. Where I overturn or extend WS10

**1. `cmp + int <= att` is missing, and it is not implied by I1.** 5,929
violating cells, **651 of which satisfy `cmp <= att`**. Mechanism: C3 re-credits
`cmp` but leaves `int` as QB-V1 drew it, so the pair stops being jointly
coherent (`att=6, cmp=6, int=1`). **This is a direct instruction for WS-B: a
repair that caps completions at attempts still leaves 651 impossible cells.**
The credit must be a constrained allocation over `att` that respects the
interceptions already drawn, or it must re-credit `int` alongside `cmp`.

**2. I10's stated reason does not support the check it guards.** "Every target
is a pass that team threw" justifies `Σ targets <= team attempts`. The check
compares against **QB** attempts. Halfback and receiver passes are real, so the
statement is contract-dependent on C3's declaration, not hard. It holds today
and should be wired — but cited as C3's contract, so that a future non-QB
passing model does not inherit a gate it was never meant to satisfy.

**3. I11 is R2-conditional and is written unconditionally.** The engine itself
says the equality form exists *because* R2 makes the level an integer
apportionment (`football_engine.py:861-866`); outside R2 the declared identity
is an inequality. Wiring `== rint(budget)` as HARD would refuse a lawful non-R2
run. All 101 runs happen to be R2, which is exactly how this kind of defect
survives.

**4. I9's PASS is produced by the check's own undeclared `rint`.** §4. WS10's
own standard for rejecting `team_carries integer-valued` — "rounding is a
declared decision" — disqualifies its own I9 implementation. It also surfaces a
separate live contract violation: `rushing/carries` is declared `kind: 'count'`
and is non-integer in 63% of cells.

**5. I5's scope should be read from the declared metric kinds, not hand-typed.**
WS10 enumerates nineteen array names in a literal tuple. `nfl/product/metrics.py`
`SUPPORTED` already declares `kind: 'count' | 'yards' | 'rate'` for every
published metric. Deriving the scope from it means a metric added later is
covered automatically; a hand-typed list silently stops covering it, and a
dtype-based rule would misclassify `rushing/carries` (float64, declared a count)
and `qb/pyds` (float64, declared yards) in opposite directions.

**6. The inactive-QB rejection is right in substance and wrong in resting
place.** WS10 rejects "an inactive QB owns zero dropbacks" as an absolute
invariant and **keeps it as a diagnostic**. I confirm the football: both
violators are QB3 by the board's own `depth_chart` (SF `00-0040589`, LA
`00-0041568`), exactly the emergency-rule population, so it is not
HARD_IMPOSSIBLE. But it is **CONTRACT_DEPENDENT and already gating**: WS05
records no third-QB rule is modelled, D04's repair zeroes inactive QB rows, and
`artifact.INVARIANTS['qb_inactive_owns_nothing']` declares it **HARD** with an
explicit `why_hard`. Demoting it to a diagnostic would reopen D04, and
`assert_hard_invariants` would refuse the artifact for `INVARIANT_MISCLASSIFIED`
before it got the chance. The diagnostic WS10 wants is a *different* instrument:
the conditional co-occurrence in §5.2, which shows the residue is a QB rotation
rather than an emergency.

**7. I13 should be accompanied by its weaker sibling N5.** `Σ QB rush_opp <=
team carries` needs no rushing layer, so it covers **59** runs against I13's 33,
and it fires 365 times. WS10 has I12 (scrambles only, 9 cells, 1 game) and I13
(both, confounded); N5 sits between them and is the cheapest early warning.

**8. F2 deserves an invariant, not only a finding.** WS10 correctly refuses to
treat the unused `team_volume/team_targets` as a broken identity. The
enforceable form is one level up and is genuinely impossible-by-contract:
**every array sealed into `player_draws.npz` is either consumed by the run or
flagged unconsumed in the manifest.** An artifact that publishes two answers to
one football question with nothing marking which was used is incoherent as an
artifact, whatever the numbers say. Offered as CONTRACT_DEPENDENT, owner WS-B or
whoever owns the manifest.

---

## 8. Summary counts

| Class | Count | Members |
|---|---|---|
| **HARD_IMPOSSIBLE** | 12 | I1, I2, I3, N1, N2, I5, I6, I7, I8, N4, N7, I12, I14a — of which **I9 and I13 are HARD in football but not evaluable on today's artifact** and are carried as DEFERRED, and **N5** joins I12/I13 as the QB-side carry containment |
| **CONTRACT_DEPENDENT** | 6 | I4, I10, I11, N3, I14b, manifest-completeness (F2 form) |
| **DIAGNOSTIC_ONLY** | 4 | negative passing yards (magnitude), QB-room size per team-draw, inactive-QB3 co-occurrence, `qb/pyds` non-integrality |
| **REJECTED** | 13 | WS10's seven, confirmed; plus six of WS-O's own (§5.2) |

*(I9 and I13 are counted once, under HARD_IMPOSSIBLE, with their evaluability
caveat; I14 is split into I14a and I14b, which land in different classes.)*

---

## 9. Evidence ceiling

* **One week, one slate.** 14 games, all `2026_01_*`. The 101 runs are 4-10
  configuration variants per game over the same players and seeds — not 101
  independent observations. The honest unit for "does this defect exist" is
  **7 games** for I1/I2/I3/N1/I13, **1 game** for I12, **1 game** for I14b.
* **Non-QB checks rest on 33 runs**, not 101 (defect D03 deferred the appearance
  layer for the twelve-game Sunday slate).
* **Nothing here is scored against a realised outcome.** Every classification is
  defined against the draws and against the rules, so none of it is manufactured
  by conditioning on what Week 1 actually did.
* **No claim of adequacy.** The clean results are "zero violations observed in N
  cells", not "correct", "stable" or "closed". No equivalence margin was
  predeclared and no TOST was run. A check that has not failed yet is not a check
  that cannot fail — and I9 is the standing proof that a check can pass because
  of how it was written.
* **What a classification cannot do.** It says which states must never be
  sealed. It says nothing about whether the forecast is any good. An artifact
  can satisfy all twelve hard invariants and be worthless.
