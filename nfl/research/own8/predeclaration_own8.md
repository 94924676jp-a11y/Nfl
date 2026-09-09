# OWN-8 pre-registration — single-owner rushing mass

**Written before any candidate is built or scored.** Nothing in this task
implements it; the ownership evidence in §1 is measurement, not fitting.

---

## 1. The ownership order, proven rather than assumed

The ruling warned against assuming "carve QB carries first". It is not the
answer. **Ownership is component-specific**, and two independent tests agree.

**Test 1 — which denominator is each component stable on?** Coefficient of
variation over 3,230 team-games, REG 2020–2025. Lower CV = the denominator the
component actually scales with.

| component | CV per dropback | CV per carry | owner |
|---|---|---|---|
| **scramble** | **0.932** | 0.960 | **dropback** |
| designed QB rush | 1.642 | **1.435** | **carry** |
| kneel | 1.531 | **1.353** | **carry** |
| RB / WR / TE | 0.604 | **0.141** | **carry**, by 4.3× |

**Test 2 — co-movement, which is what per-draw coherence needs.**

| component | corr with dropbacks | corr with carries |
|---|---|---|
| scramble | **0.1824** | 0.1802 |
| designed QB rush | **−0.1174** | **+0.2921** |
| kneel | −0.2402 | **+0.3349** |
| RB / WR / TE | −0.4041 | **+0.8831** |

And the fact that makes the current architecture collide:

> **team carries and team dropbacks correlate −0.4046.**

The two budgets move in **opposite** directions. So generating designed QB
rushes on the dropback axis gives them the **wrong sign** against the carry
budget they must fit inside: in a draw with many dropbacks the quarterback is
allocated *more* carries exactly when the carry budget is *smaller*. The 33.83%
collision rate is structural, not incidental.

**Conclusion.** `qb2_lib` draws designed QB rushes as
`Binom(dropbacks, drush_per_dropback)`. Historically designed rushes correlate
**+0.2921** with carries and **−0.1174** with dropbacks. **The simulator has the
sign backwards.** This is the OWN-4 finding again — a layer generating a level
it does not own — this time on the rushing side.

Scrambles are the exception and stay where they are: the two tests are
essentially tied (CV 0.932 vs 0.960, corr 0.1824 vs 0.1802) and a scramble
*is* a dropback that ran. Their claim on the carry ledger is real but
**generated upstream**.

### The ownership graph

```
team_carries                       D1 — ONE level, exactly one owner
  ├─ scrambles                     QB V1 dropback multinomial — a PRIOR CLAIM,
  │                                subtracted from the budget
  └─ rush-play budget = team_carries − scrambles
       ├─ kneels                   named, unmodelled (Part B)
       ├─ designed QB rush         CARRY-owned; today mis-denominated
       ├─ RB                       P4C simplex
       ├─ WR / TE                  today inside `other`
       └─ fringe other             named residual
```

**So the answer to the ruling's four options is (2) for scrambles and (1) for
designed rushes — neither alone.** Conditional rates QB V1 keeps: the
scramble/designed split, sack and attempt rates, per-rush yardage. What it must
stop owning is the designed-rush **level**.

---

## 2. Part B — do kneels block exact ownership? No.

Kneels are carry-owned (CV 1.353, corr +0.3349), **0.7746 per team-game**,
**0.0288 of team carries**. No governed control exists and none is invented
here.

They do **not** block exact ownership, provided the architecture keeps them a
**named category that consumes carry mass** rather than an unnamed remainder.
An unmodelled level inside a named category still closes: the category exists,
its mass is accounted, and nothing else may use it. What would block ownership
is leaving them in an anonymous residual that other quantities also draw on.

Any architecture must guarantee, and these are gates:

- kneels consume team carry mass;
- kneels never enter `qb_rush_opportunity`, which is `scramble + designed` by
  construction;
- kneels never become RB, WR or TE carries;
- no carry is counted twice;
- no team carry mass appears from nowhere.

---

## 3. Candidates

**A0 — incumbent.** QB rush drawn on dropbacks; RB block on carries; no
coupling. Collides in 33.83% of draws, worst 44.24 carries.

**A1 — prior-claim subtraction, designed rush re-denominated.** The graph in
§1. Scrambles subtracted from the budget; the remainder partitioned across
kneels, designed QB, RB, WR/TE and fringe in one per-draw multinomial, so every
carry has exactly one owner in every simulated world.

**A2 — common latent.** Draw a team pass/run tendency once and condition both
budgets on it. Reproduces the −0.4046 budget correlation but does **not** by
itself guarantee per-draw closure — two conditionally independent draws can
still overrun. Rejected as a closure mechanism; retained as a possible
*refinement* of A1's marginals.

**Declared order: A1 < A2.** A1 is the closure architecture; A2 is an
enhancement that cannot substitute for it.

**Forbidden in every candidate:** clipping QB rushing to the remaining mass;
post-hoc renormalisation; survivor scaling; dumping the excess into `other`;
deleting violating draws; using the historical 0.1568 as a fitting target.

---

## 4. What A1 requires that is not authorized today

A1 cannot be built without a **P4C refit**, and no refit is authorized:

1. The RB simplex is fitted as `carries / team_carries` where `team_carries`
   **includes** scrambles, kneels and designed QB runs. Applying those shares to
   a **scramble-reduced** budget changes the denominator they were fitted
   against — a semantic change, not a rescale.
2. A1 needs **designed QB rush** and **kneels** as modelled categories. P4C's
   carry class declares `pos: ('RB',)`; neither category exists in the fit.

Both are refits with new modelled categories — a different matter from OWN-6's
units correction, which explicitly required none. **So A1 is specified and not
implemented.**

## 5. Gates when A1 is authorized

Per team, per draw:
`team_carries = scrambles + kneels + designed_qb + rb + wr + te + explicit_other`

- zero negative allocation; zero duplicate carries; zero silent residual
- scramble exactly once; designed rush exactly once;
  `qb_rush_opportunity = scramble + designed`
- no modelled category exceeds the budget; player sums close to their category
- zero carries → zero rushing yards; negative rushing yards remain allowed
- no clipping; **named refusal** when `scrambles > team_carries`
- and Part E's whole passing side unregressed: D1 and allocator reproducibility,
  QB dropback closure, C3 completions / yards / TDs, receiving accounting,
  terminal-state closure, OWN-4 mass conservation.

## 6. Stochastic requirement

Closure must not be bought with dispersion. Before/after on mean, SD, p05/p50/p95,
zero mass, tail mass for QB rush opportunity, RB carries and team carries, plus
the cross-category correlations above. **If exact closure materially distorts a
marginal, that is a finding to diagnose, not a cost to accept.**
