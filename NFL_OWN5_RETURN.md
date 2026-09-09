# OWN-5 — C3 re-verified, and the rushing defect is an accounting one

**Verdict: `OWN5_C3_CLEAR_RUSH_DEFECT_IDENTIFIED`**

C3 is clear under OWN-4. The rushing gate failure is **not** a modelling problem
and **not** the defect R4 recorded. It is a **units mismatch**: a fitted *share*
is consumed as an unnormalised *weight*, which shrinks the carry space the
quarterback must fit into. And the premise the ruling carried forward — QB rush
opportunity at 0.284 of team carries — is **stale**: it is now **0.1369**
against a historical **0.1333** ex-kneels. QB3's allocation already fixed that.

---

## Part A — `C3_REVERIFIED_UNDER_OWN4`

Full XL1/C3 arm re-run under current OWN-4. 12 team-games, 200 draws, A3 on.

| identity | B0 | C1 | **C3** |
|---|---|---|---|
| team completions vs receiver receptions | 2,400 / 2,400 violate | 0 | **0 / 2,400** |
| team passing yards vs receiving yards | 2,400 / 2,400 violate | 0 | **0 / 2,400** |
| team passing TD vs receiving TD | 2,243 / 2,400 violate | 0 | **0 / 2,400** |

- **Orchestration equivalence 18 / 18** — the study path still reproduces B0
  byte-for-byte on B0's own target vector, so C3 numbers remain attributable.
- **QB attribution / no silent residual** — team dropback closure is exact under
  OWN-4 (max abs diff 0.0), and the identity report carries no residual term.
- **No duplicate construction** — C3 generates completions, yards and touchdowns
  once; the identity holding at zero violations is that property.
- **No cross-player donor contamination** — the OWN-4-specific risk, tested
  directly: **13,278** post-composition per-dropback ratios traced, and
  **0** failed to appear in that quarterback's *own* pre-composition draws.
  Every composed ratio traces to its own row. 3 cells were repaired in the run.

Nothing moved. Proceeding to Part B.

---

## Part B — carry ownership

### The historical ledger closes exactly

REG 2020–2025, **3,230 team-games**, from play-by-play:

```
team_rush_attempts 26.9192 = qb_rushes 4.3635 + nonqb_rushes 22.5557
                             EXACT in 3,230 / 3,230, max residual 0

qb_rushes 4.3635 = scrambles 1.8155 + kneels 0.7746 + designed 1.7734
```

Through the panel the model actually fits on, the same decomposition closes to
**1.0000 with zero unattributed**:

| owner | share of team carries |
|---|---|
| **RB** | **0.8082** |
| **QB** | **0.1568** ← this is R4's "0.157" |
| WR | 0.0302 |
| TE | 0.0038 |
| **non-RB mass** | **0.1918** |

### The ownership table

| quantity | owner | denominator it is generated on |
|---|---|---|
| team carries | **D1** `team_carries` | — (it is the pbp `rush_attempt` count, and it **includes** QB scrambles, designed QB runs and kneels) |
| RB per-player carries | **P4C simplex** × team carries | team carries |
| `other` mass | **P4C `mass_pool`**, fitted | team carries |
| QB scramble | **QB V1**, from the dropback multinomial | **dropbacks** |
| QB designed rush | **QB V1**, `Binom(db, dpd)` | **dropbacks** |
| QB rush opportunity | **QB V1**, `scr + designed` | **dropbacks** |
| kneels | **nobody** — 0.7746 per team-game, inside D1's budget, modelled nowhere |
| rushing yards | RB: **refused** (`RUSHING_CONVERSION_CONTROL_UNDEFINED`); QB: `rush_opp × ypr` |

### What the simulator actually does now

12 team-games, 200 draws, current code:

| | simulator | historical |
|---|---|---|
| QB rush opportunity / team carries | **0.1369** | 0.1333 ex-kneels, 0.1568 incl. |
| RB allocated / team carries | **0.8750** | **0.8082** |
| `other` mass / team carries | **0.1250** | **0.1918** |
| QB rush as a share of the space available to it | **1.0957** | — |

**The quarterback's rushing is right. The space left for him is not.** He needs
0.1369 and `other` holds 0.1250, so `qb_rush_contained_in_other` correctly
refuses — 1,178 violating cells, worst 47.07.

**R4's 0.284 is stale and must not be carried forward.** It predates QB3's
allocation, which already fixed it.

### The mechanism, identified at the source

`other` is **not** a residual — it is fitted, and fitted **correctly**:

```
p4c_build.py:151   pool = max(0, min(0.95, mall[k] - ms[k]))
```

`mall` is the sum of **all** players' realised shares for that team-game, which
is exactly 1.0 because the panel closes; `ms` is the modelled subset. So
`mass_pool` is a **share on [0,1]**. Its fitted mean is **0.1989**, against a
historical non-RB mass of **0.1918**. The fit is sound.

It is then **consumed as a weight**:

```
p4c_lib.py:110-113   tot = sum(W*A) + w_other
                     S   = W*A / tot
                     other = w_other / tot
```

`sum(W*A)` is on the relative-weight scale and is **not normalised to 1**.
Measured, it is ≈ **1.286**. So a drawn share of **0.1837** is diluted to
`0.1837 / (1.286 + 0.1837)` = **0.1250**. Had `sum(W*A)` been normalised to
`1 − w_other`, the realised mass would be **0.1866** — essentially the
historical 0.1918.

**Classification, against the ruling's list:** not duplicate ownership, not
double counting of scrambles and designed runs, not a team-carry residual
construction, not QB V1/QB3 overlap, not an estimator defect. It is a
**denominator/units mismatch — a fitted share consumed as an unnormalised
weight** — and it under-sizes the only space the quarterback's carries can
occupy.

### The deterministic repair, specified and not applied

```
S_i   = (1 - w_other) * W_i A_i / sum(W*A)
other = w_other
```

A pure rescale of the modelled block. Nothing fitted, no clipping, no survivor
renormalisation, relative ordering among running backs exactly preserved, and
the fitted share lands where it was fitted to land. Predicted effect: RB share
0.8750 → **≈ 0.8163**, `other` 0.1250 → **≈ 0.1837**, which is more than the
0.1369 the quarterback needs.

**I did not apply it, and the reason is specific rather than caution.**

1. `p4c_lib.allocate` is a **frozen P4C module**, and the same formula serves the
   **targets** simplex, which currently **passes**. A rushing diagnosis must not
   silently change the receiving layer.
2. The P4C weights `W` were fitted with this `allocate` in the loop. Correcting
   the normalisation without establishing whether `W` absorbed the dilution
   would be applying fitted weights under a different normalisation. The
   evidence says the current combination is **not** calibrated — it produces
   0.8750 against a historical 0.8082 — which supports the repair but does not
   settle whether `W` needs refitting.

That is an owner decision about a frozen fitted artifact, and it needs its own
gate run across **both** simplexes. Reported rather than taken.

---

## Part C — `QB_LEVEL_OWNERSHIP_R2` pre-registration

Written, committed, **not implemented and not scored**, per the ruling.
`nfl/research/r2/predeclaration_qb_level_ownership_r2.md`, sha256
`3d7beeb3…`. It fixes: D1 owns team dropbacks; QB3 owns per-QB allocation; QB V1
owns **conditional rates only and never a level**; integerisation happens
**after** allocation by largest-remainder apportionment so `Σ_j n_j == N_t`
exactly by construction; the invariant changes from float-exact to
integer-exact and that trade is declared rather than discovered; the OWN-4 donor
mechanism must become **unreachable and be removed**, because a guard that can
never fire is not a guard; and R2 is preferred only if it holds every invariant
and widens no terminal-state interval, since OWN-4 already conserves mass.

---

## Governance

No PATH_C promotion · no 2026 outcomes · no market/DFS data · no T-90 change ·
G0A **11/12** · NFL-1 **NOT AUTHORIZED** · QB3/A3/C3 rehearsal-only ·
`include_cold_start` still **False** by default.

Suite **42 modules, 448 test functions, 2,607 checks, 0 failing**.

## Files

| File | Role |
|---|---|
| `nfl/research/own5/audit_rush_ownership.py`, `own5_rush_ownership.json` | Part B, every number |
| `nfl/research/r2/predeclaration_qb_level_ownership_r2.md` | Part C |
| `nfl/research/xl1/xl1_results.json` | Part A, re-run under OWN-4 |
