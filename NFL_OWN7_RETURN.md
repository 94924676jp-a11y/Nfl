# OWN-7 — reproducibility restored, then the authorized P4C units repair

**Decision: `OWN7_REPRODUCIBLE_P4C_UNITS_REPAIRED`**

- **Part A: `TARGETS_CARRIES_RNG_REPRODUCIBLE`** — and the audit found a
  **second** production layer with the same defect, D1's team volume.
- **Part B** — the authorized simplex contract applied to both branches, no
  refit, with a named refusal.
- **Part C** — targets and carries land on their fitted and historical
  comparators; C3 clean; receiving accounting clean; no regression.
- **Part D: `KNEEL_MASS_EXPLICIT_UNMODELED`.**
- **Part E** — suite **42 modules, 451 test functions, 2,638 checks, 0
  failing**.

**One thing did not become clean, and it is a finding rather than a
disappointment.** The rushing containment gate still fails — but for a
different, now-isolated reason. The container is the right *size*; the failure
is **per draw**. §5.

---

## Part A — the seed that is not a seed

The audit found **two** production instances, not one:

| layer | was | why it mattered |
|---|---|---|
| `layers.targets_carries` | `default_rng([seed, hash(cls) % 9973])` | targets and carries allocation |
| **`team_volume_v1.forecast`** | `default_rng([seed, ordinal, hash(metric) % 9973])` | **D1 — every team volume: dropbacks, targets, carries, snaps** |

D1 is upstream of everything, so the whole predictive path was
process-dependent, not just the allocator.

**The repair — `nfl/production/seeds.py`.** An explicit integer per named
stream. No hashing of any kind, builtin or cryptographic: a table this small
should be readable, and a reader should be able to see which integer a stream
got without running anything.

```
SEED_CONTRACT = 'nfl-stream-seed-v1'
p4c_alloc   : snaps 1, pass_snaps 2, targets 3, carries 4, rz_carries 5
team_volume : team_off_snaps 1, team_dropbacks_part 2, team_targets 3,
              team_carries 4, team_rz_carries 5
```

Unknown keys are **refused, never defaulted** — `SEED_STREAM_UNDECLARED` /
`SEED_NAMESPACE_UNKNOWN` — so a new metric cannot silently share a stream with
an existing one. Ids are frozen and append-only. The contract travels in the
allocation layer's evidence.

### Adversarial checks — five independent processes

| process | `PYTHONHASHSEED` | order | `pyhash('targets')` | targets | carries | team_volume |
|---|---|---|---|---|---|---|
| 1 | unset | fwd | 1012 | `40ef93b4…` | `2a64067c…` | `f56e7526…` |
| 2 | 0 | fwd | 7217 | `40ef93b4…` | `2a64067c…` | `f56e7526…` |
| 3 | 1 | fwd | 2531 | `40ef93b4…` | `2a64067c…` | `f56e7526…` |
| 4 | 987654 | fwd | 7792 | `40ef93b4…` | `2a64067c…` | `f56e7526…` |
| 5 | unset | **reversed** | 3907 | `40ef93b4…` | `2a64067c…` | `f56e7526…` |

`pyhash` varies across all five, proving the processes genuinely differ; every
output hash is **identical**. Re-verified after Part B: hashes changed (a
different allocator) and remained **stable across process, hash seed and
invocation order**, while `team_volume`'s hash was unchanged by the units
repair — which is the right answer, since D1 is not a simplex.

**Regression guard.** A test walks the **AST** of both functions and fails on
any live call to `hash`. Its first version was a substring test and failed on
the comment explaining why the call was removed; a text match cannot tell a live
call from its own explanation.

### Reported, not fixed

`hash()` also appears in the seed construction of two **research** modules —
`nfl/research/rbb1/rbb1_lib.py:152` and `nfl/research/j1/run_j1.py:58-59`. Those
studies are complete and their results are therefore not reproducible draw-for-draw.
Reported per the instruction not to broaden refactoring; neither is in the
predictive path.

---

## Part B — the authorized contract

`p4c_lib.allocate`, simplex branch:

```python
S_i   = (1 - w_other) * W_i A_i / sum_g(W A)
other = w_other
```

Applied to **both** targets and carries. **No refit** — and none is needed:
OWN-6 established that `fit_params` never calls the allocator and that `alpha0`
is already fitted under `scale = (1 - mass_mean)/Σ_C`, which is this contract.
`mass_pool`, `W`, `A` and every frozen parameter are untouched.

**Named refusals, not silent arithmetic:**

- `SIMPLEX_OTHER_MASS_NOT_BELOW_ONE` — a non-modelled mass ≥ 1 leaves the
  modelled block no share. Raised, converted to a named `Outcome.fail` by the
  caller. Never clipped.
- A group where **no** modelled player has weight in a draw gives the whole mass
  to the non-modelled block and **closes**. That is the definition, not a
  fallback, and the affected groups are **counted** and returned rather than
  passing silently.

---

## Part C — evidence under the stable RNG

**The applied repair is the authorized formula.** Recomputing the corrected
contract from production's captured inputs reproduces production's own output
to six decimals on both simplexes — C0 ≡ C1, exactly.

| | carries modelled | carries `other` | targets `other` |
|---|---|---|---|
| before both repairs | 0.891489 | 0.108511 | 0.005288 |
| contract only, old RNG *(OWN-6 C1)* | 0.811104 | 0.188896 | 0.012252 |
| **after both repairs (production now)** | **0.801160** | **0.198840** | **0.016308** |
| comparator | RB **0.8082** | non-RB **0.1918** | fitted `mass_mean` **0.0113** |

The middle row separates the two changes honestly: the contract moves the mass,
and the RNG repair shifts it slightly further because the draw itself changed.
Neither was fitted toward the comparator.

**Targets** — closure exact, zero-share fraction unchanged at 0.2098, p99 moves
by 0.0014, per-draw ordering preserved, **receiving accounting PASS in 6 of 6
games**. The receiving simplex was diluted by the same defect and is now on its
own fitted mass; it was not harmed.

**C3 — no regression.** 12 team-games, 200 draws: completions, passing yards and
passing touchdowns all **0 of 2,400** violating draws; orchestration equivalence
**18/18**.

**Engine gates** — allocation share closure PASS, team dropback closure max abs
diff **0.0**, terminal-state closure **0 of 4,500** cells, and **0 differences in
924 field comparisons** on forecastable quarterbacks.

---

## 5. The rushing gate still fails, and the reason has changed

OWN-5 said the container was too small. It is not any more. What remains is
that it is a **marginal** container, not a per-draw one.

| | |
|---|---|
| QB rush opportunity | 0.1526 of team carries |
| container after the repair | **0.198840** |
| **mean margin in the container's favour** | **+1.7945 carries** |
| **draws where QB rush still exceeds it** | **812 of 2,400 — 33.83%** |
| worst single-draw excess | **44.24 carries** |

The quarterback's carries are drawn from his dropback multinomial and the
running-back block from the carry simplex, and **neither draw knows about the
other**. On average they fit; in a third of draws they collide.

That is duplicate ownership one level below the units defect — the same shape as
the passing side before C3 — and repairing it means carving the quarterback's
carries out of the team budget **before** the simplex allocates the remainder.
That is a rushing architecture change and is **outside what OWN-7 authorized**,
so it is measured and reported, not attempted.

---

## Part D — `KNEEL_MASS_EXPLICIT_UNMODELED`

No governed mechanism exists. Kneels are now a **named** component in
`accounting.UNMODELLED_CARRY_COMPONENTS`, with eleven checks guarding it.

- **Where they are:** D1's `team_carries` is the pbp `rush_attempt` count and
  **includes kneels** — 0.7746 per team-game, **0.0288 of team carries**. In the
  *fitting* frame they sit inside the quarterback's realised carry share and so
  land inside `mass_pool`, hence inside `other`. In the *simulator* QB rush
  opportunity is `scrambles + designed` and contains no kneel at all, so the
  kneel mass sits in `other` **claimed by nobody**.
- **Never attributable to:** RB, WR, TE, `qb_scramble`, `qb_designed_rush` —
  asserted in the declaration and tested.
- **The invariant future modelling must satisfy:** a kneel is a team carry that
  consumes clock and produces no opportunity, so whatever models it must take
  its mass **from** the team carry budget rather than adding to it, never enter
  `qb_rush_opportunity`, never enter any receiver or back allocation, and leave
  the remaining containers smaller by exactly its size so team carries still
  close.

No estimator was invented.

---

## Part E — full gate

| | |
|---|---|
| HEAD | `f0009d544549ca6d77cecd308fe986fe8d91d556` |
| suite | **42 modules, 451 test functions, 2,638 checks, 0 failing** |
| cross-process hashes | identical across 5 processes, 4 hash seeds, both orders |
| C3 | **0 / 2,400** on all three identities |
| receiving accounting | **PASS 6/6** |
| allocation share closure | **PASS**, 0 teams leaking |
| team dropback closure | **PASS**, max abs diff 0.0 |
| terminal-state closure | **PASS**, 0 / 4,500 |
| **rushing containment** | **FAIL — per-draw, 33.83%; §5** |
| files changed | `seeds.py` (new), `layers.py`, `team_volume_v1.py`, `p4c_lib.py`, `accounting.py`, `test_xl1_shared_pass.py` (+128) |

**Governance:** no PATH_C promotion · no 2026 outcomes · no market/DFS · no
T-90 change · G0A **11/12** · NFL-1 **NOT AUTHORIZED** · R2 preregistered and
unimplemented · no parameter refitted · `include_cold_start` still False.

## 6. Queue

1. **Per-draw rushing coupling** (§5) — carve QB carries from the team budget
   before the simplex allocates the remainder. Needs authorization.
2. Kneel ownership, against the invariant in Part D.
3. Then the W1 rehearsal rerun and the passing-TD question.
