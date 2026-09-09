# OWN-8 — single-owner rushing mass

**Decision: `OWN8_RUSHING_ARCHITECTURE_IDENTIFIED_NOT_IMPLEMENTED`**

The ownership order is now **proven rather than assumed**, and the ruling's
warning was right: *"carve QB carries first" is not the answer.* Ownership is
**component-specific**, and the mechanism behind the 33.83% collision is a sign
error, not a capacity shortfall.

**The architecture cannot be built without a P4C refit, which is not
authorized.** It is specified, pre-registered and left unimplemented.

---

## 1. Part A — the ownership order, proven

Two independent tests over **3,230 team-games**, REG 2020–2025. They agree on
every component.

**Test 1 — which denominator makes the component's rate stable?**

| component | CV per dropback | CV per carry | owner |
|---|---|---|---|
| **scramble** | **0.932** | 0.960 | **dropback** |
| designed QB rush | 1.642 | **1.435** | **carry** |
| kneel | 1.531 | **1.353** | **carry** |
| RB / WR / TE | 0.604 | **0.141** | **carry**, by 4.3× |

**Test 2 — co-movement, which is what per-draw coherence actually needs.**

| component | corr with dropbacks | corr with carries |
|---|---|---|
| scramble | **+0.1824** | +0.1802 |
| designed QB rush | **−0.1174** | **+0.2921** |
| kneel | −0.2402 | **+0.3349** |
| RB / WR / TE | −0.4041 | **+0.8831** |

The categorisation closes exactly: every carry lands in exactly one category in
**3,230 of 3,230** team-games, max residual **0**.

### The mechanism, and it is a sign error

> **Team carries and team dropbacks correlate −0.4046.**

The two budgets move in **opposite** directions — a team that passes more, runs
less. `qb2_lib` draws designed QB rushes as
`Binom(dropbacks, drush_per_dropback)`. Historically designed rushes correlate
**+0.2921 with carries and −0.1174 with dropbacks**.

**The simulator has the sign backwards.** In a draw with many dropbacks the
quarterback is allocated *more* carries at exactly the moment the carry budget
is *smaller*. The 33.83% collision rate is structural, not incidental, and no
amount of extra container would fix it — OWN-7 already enlarged the container
from 0.1085 to 0.1988 and the collisions remained.

This is the OWN-4 finding on the rushing side: **a layer generating a level it
does not own.**

**Scrambles are the exception and stay put.** Both tests are essentially tied
(CV 0.932 vs 0.960; corr 0.1824 vs 0.1802) and a scramble *is* a dropback that
ran. Their claim on the carry ledger is real but generated upstream.

### The ownership graph

```
team_carries                    D1 — ONE level, exactly one owner
  ├─ scrambles                  QB V1 dropback multinomial — PRIOR CLAIM,
  │                             subtracted from the budget          [option 2]
  └─ rush-play budget = team_carries − scrambles                    [option 1]
       ├─ kneels                named, unmodelled
       ├─ designed QB rush      carry-owned; today mis-denominated
       ├─ RB                    P4C simplex
       ├─ WR / TE               today inside `other`
       └─ fringe other          named residual
```

**Answer to the ruling's four options: (2) for scrambles, (1) for designed
rushes. Neither alone** — which is exactly why "carve QB first" had to be
tested rather than adopted.

QB V1 keeps every conditional rate it legitimately owns: the scramble/designed
split, sack and attempt rates, per-rush yardage. What it must stop owning is the
designed-rush **level**.

---

## 2. Part B — kneels do not block exact ownership

Kneels are carry-owned (CV 1.353, corr **+0.3349**), **0.7746 per team-game**,
**0.0288 of team carries**. **No governed control exists** and none was invented.

**They do not block it**, provided the architecture keeps them a **named
category that consumes carry mass** rather than an anonymous remainder. An
unmodelled *level* inside a named category still closes: the category exists,
its mass is accounted, and nothing else may draw on it. What would block
ownership is leaving them in a residual that other quantities also use.

So `KNEEL_MASS_EXPLICIT_UNMODELED` stands from OWN-7, and
`OWN8_KNEEL_CONTROL_REQUIRED` is **not** the verdict.

---

## 3. Part C — candidates, pre-registered

`nfl/research/own8/predeclaration_own8.md`, sha256 `90f6ecc3…`.

- **A0** incumbent — collides in 33.83% of draws, worst 44.24 carries.
- **A1** prior-claim subtraction + designed rush re-denominated — the graph
  above; one per-draw partition, so every carry has exactly one owner in every
  simulated world.
- **A2** common latent — reproduces the −0.4046 budget correlation but **does
  not** guarantee per-draw closure, since two conditionally independent draws
  can still overrun. **Rejected as a closure mechanism**, retained as a possible
  refinement of A1's marginals.

Declared order **A1 < A2**. Forbidden in every candidate, per the ruling:
clipping, post-hoc renormalisation, survivor scaling, dumping excess into
`other`, deleting violating draws, or fitting toward 0.1568.

---

## 4. Why A1 is not implemented

A1 needs a **P4C refit**, and no refit is authorized:

1. The RB simplex is fitted as `carries / team_carries` where the denominator
   **includes** scrambles, kneels and designed QB runs. Applying those shares to
   a **scramble-reduced** budget changes the denominator they were fitted
   against — a semantic change, not the rescale OWN-6/OWN-7 performed.
2. A1 needs **designed QB rush** and **kneels** as modelled categories. P4C's
   carry class declares `pos: ('RB',)`. Neither exists in the fit.

OWN-6 established that the *units* fix needed no refit; that finding does not
extend to adding modelled categories, which is a different question. Building A1
on the current fit would be applying shares under a denominator they were never
estimated against — the exact error OWN-6 was written to stop.

**So the honest boundary is here.** Parts D, E, F and the stochastic
before/after in Part F have nothing to measure until A1 exists, and reporting
them against an unbuilt candidate would be inventing evidence.

---

## 5. Parts E and H — nothing regressed, because nothing was changed

**No production file was modified in this task** (`git status --porcelain
nfl/production` → 0). The passing architecture therefore stands exactly as
OWN-7 left it, re-verified there: D1 and allocator reproducibility across five
processes, QB dropback closure max abs diff 0.0, C3 completions / passing yards
/ passing TDs **0 of 2,400** each, receiving accounting **PASS 6/6**,
terminal-state closure **0 of 4,500**, OWN-4 mass conservation with maximum
per-draw shortfall **0.0000000000**.

Re-running C3 was pointless without a rushing change and is not reported as if
it were evidence.

| | |
|---|---|
| suite | **42 modules, 451 test functions, 2,638 checks, 0 failing** |
| production files changed | **0** |
| files added | `nfl/research/own8/predeclaration_own8.md`, `audit_rush_ownership_graph.py`, `own8_ownership.json`, this return |

---

## 6. Governance

No PATH_C promotion · no 2026 outcomes · no market/DFS · no T-90 change · G0A
**11/12** · NFL-1 **NOT AUTHORIZED** · R2 preregistered and unimplemented ·
`RUSHING_CONVERSION_CONTROL_UNDEFINED` respected · no feature search, no
efficiency model, no tuning toward any historical share.

## 8. What authorization A1 needs

A P4C carry-class refit with **designed QB rush** and **kneels** as modelled
categories, on a **scramble-reduced** budget, under the same chronology and
objective as the original fit. That is the one decision blocking a rushing
ledger in which every carry has exactly one causal owner in every simulated
world.
