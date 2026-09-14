# D2 — Low-projection attribution

**Diagnostics only.** Nothing in this work changes an estimator, a parameter, a
draw or a projection. No floor, no adjustment, no tuning. External research is
pending and this is built so as not to prejudice it: it is machinery for saying
*which mechanism* produced a number, not machinery for changing the number.

| | |
|---|---|
| Board | `nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1` |
| Game | 2026_01_DEN_KC, kickoff 2026-09-15T00:15:00Z |
| Draws | 1000, seed 20260908, digest `86e3707db48ce5ac3adf359878caca5b1a9bae18ef7c0a8a3165194c3c46b26a` |
| Code | `nfl/product/attribution.py`, spec `nfl-low-projection-attribution-1` |
| Tests | `nfl/tests/test_product_attribution.py` — 17 functions, 71 checks, SUITE PASS |
| Data | `nfl/research/v2/d2/D2_ATTRIBUTION_2026_01_DEN_KC.json` |

A naming note, because it is a deviation from the brief. The file I was told to
create, `nfl/tests/test_attribution.py`, **already exists** and guards the
retirement of `nfl.capture.attribution`'s post-hoc claims path (Directive 7 §6).
Writing over it would have deleted a live guard whose entire job is to notice a
retired mechanism coming back. The new test module is
`test_product_attribution.py`; both run and both pass.

---

## 1. The algebra, and why the parts sum

For a metric `Y` over `m` draws with `p0 = P(Y = 0)`:

```
U = E[Y]                     the board's unconditional projection
C = E[Y | Y > 0]             the conditional projection
U = (1 - p0) * C             identity, by definition of a conditional mean
G = C - U = p0 * C           the gap
```

**`C / U = 1 / (1 - p0)` always.** It is an identity and it carries no
information about mechanism whatever. The hand-worked case on 2026-09-14 quoted
"ratio 1.70 = exactly 1/(1−0.413)" as if it confirmed something; it confirms
only that the arithmetic is arithmetic. What the identity *does* establish is
the thing this whole diagnostic rests on: **the entire unconditional /
conditional gap is carried by the zero mass.** Attributing the gap is exactly
attributing `p0`.

The per-draw form is what makes the parts sum with no interaction term to argue
about:

```
G = (1/m) * SUM_j (C - Y_j)
  = (1/m) * SUM_{j : Y_j = 0} C        because SUM over non-zero draws is 0 exactly
```

So **every zero draw contributes exactly `C/m` to the gap**. Label the zero
draws and the mechanism contributions sum to `G` by construction. Verified on
this board to 1e-9 on all 124 metrics, and on the 67 material volume metrics the
contributions sum to 630.9539 against a measured total gap of 630.9539.

The second half of the diagnostic, the **conditional level**, is a separate
exact factorisation on the non-zero subsample with the interaction carried
rather than dropped:

```
C = Tbar * sbar * (unit/opportunity) * ebar * K ,  K defined as the residual factor
```

so in logs the parts sum to `log C` exactly. `K` is reported, never discarded.
For Mahomes `K = 0.99979`; for Nix `K = 0.99999`.

### Which mechanisms can fire at all: the channel map

A mechanism with no layer cannot produce a zero, and pretending otherwise is how
a residual acquires a confident name. Read off the `spec_version` strings the
sealed artifact carries:

| layer | spec | eligibility | participation | role allocation |
|---|---|---|---|---|
| `qb` | `qb-v1-aggregate-then-allocate-1` | roster status R5 + inactive exclusion | **ABSENT** | rivalrous room |
| `receiving` | `nfl-nonqb-receiving-1` | appearance team scope | appearance_r8 | non-rivalrous simplex |
| `rushing` | `nfl-nonqb-rushing-1` | appearance team scope | *the same* indicator | non-rivalrous simplex |

Two consequences do real work. **No quarterback zero can be `PARTICIPATION`** —
`football_engine.py:501` builds the appearance population from
`RECEIVING_POS = ('WR','TE','RB')`, so no quarterback carries an appearance
draw. And **a running back is modelled in two rooms**, which is the only reason
his participation mass is identifiable at all. A board whose `spec_version` is
not in the map is **refused** (`LAYER_SPEC_UNKNOWN`), not guessed.

### The cascade

Each zero draw is assigned once, in a declared order.

1. **`ELIGIBILITY`** — row-level; the player had no support before the draw.
2. **`TEAM_VOLUME`** — per draw; his side's own volume was zero in that world.
3. **`EFFICIENCY`** — per draw; he *held opportunity* and the metric was still
   zero. This is a conversion event, not an access one, and it is the whole
   story for a touchdown market.
4. **`PARTICIPATION`** — mass split by the dual-room estimator (§2).
5. **`ROLE_STATE`** — per draw; the allocator is rivalrous and a named
   team-mate held a majority of the room in that draw.
6. **`PLAYER_ALLOCATION`** — what is left, when participation was identified.
7. **`UNKNOWN`** — what is left, when it was not. Never folded into a neighbour.
8. **`OTHER_RESIDUAL`** — a named closing term, 0.0000 everywhere on this board.

**The order is load-bearing and is argued, not asserted.** Participation is
resolved *before* role displacement because a player who is not on the field
necessarily has his room reallocated, so "a team-mate holds the role" is
*entailed* by absence and is not evidence against it. Measured here:
`P(a team-mate holds a carry majority | RB1 has zero carries) = 0.973`, while
his identified participation mass is 0.1453 of a 0.150 zero mass.
Displacement-first would have called RB1 `ROLE_STATE` and been exactly wrong.

**Rivalrousness is a property of the allocator, not of the player.** An earlier
draft keyed it on the player's own share-given-present, which sent every
*backup* quarterback's zeros to `PLAYER_ALLOCATION` — because a backup's share
when he plays is small, which describes his role and not the mechanism of his
zero. `qb_allocation` samples the primary's share from an empirical pool whose
modal value is exactly 1.0; the p4c simplex exists to spread a budget over many
players. That is a structural difference between allocators and it is where the
flag belongs. On this board a team-mate held a dropback majority in **100% of
every quarterback's zero draws**, backups included.

---

## 2. The one estimator: separating PARTICIPATION from PLAYER_ALLOCATION

This boundary is most of the value and it is the only place anything is
*estimated* rather than counted.

The engine multiplies **one** appearance indicator into both of a back's rooms
(`layers.participation`), then allocates the two rooms on separate streams. So
with `a = P(A=0)`:

```
p_a = a + (1-a)u ,  p_b = a + (1-a)v ,  p_j = a + (1-a)uv
  =>  a = (p_j - p_a*p_b) / (1 + p_j - p_a - p_b)
```

Three equations, three unknowns, one closed form, **nothing fitted**. It is
falsifiable — `a` must lie in `[0, min(p_a,p_b)]` — and it is not falsified:

| back | p(carries=0) | p(targets=0) | joint | independence | **â** | bound |
|---|---|---|---|---|---|---|
| RB1 | 0.150 | 0.275 | 0.1460 | 0.0413 | **0.1453** | ≤0.150 |
| RB3 | 0.382 | 0.365 | 0.2670 | 0.1394 | **0.2453** | ≤0.365 |
| RB2 | 0.169 | 0.518 | 0.0910 | 0.0875 | **0.0086** | ≤0.169 |

**The control is run, not written as a caveat.** The one confound that could
masquerade as a shared appearance indicator is team-volume co-movement. Re-run
inside terciles of team volume: RB1 pooled 0.14528 against stratified mean
0.14539; RB3 0.24533 against 0.24525; RB2 0.00856 against 0.00780. Deviations
of 1e-4 against a declared tolerance of 0.02. The confound is not driving it.
A verdict requires **at least two usable strata** — one stratum cannot disagree
with itself — and where fewer are available the estimate is withdrawn to
`UNKNOWN` with reason `CONTROL_NOT_RUN`.

### Two identification strategies were tried and both fail

Recorded so nobody pays for them twice. Both are asserted as *failing* in the
test suite, so they cannot come back quietly.

1. **Volume-limit.** "Thinness vanishes as team volume rises, availability does
   not, so `p0` in the top volume tercile estimates `P(not available)`."
   **Refuted.** `p0` is near volume-invariant because the allocator draws a
   *share*, and a share does not improve with the size of the budget. WR6's
   `p0` by team-target tercile: **0.667 / 0.670 / 0.662**.
2. **Binomial thinness bound.** "`P(zero | present) ≤ (1-share)^volume`, so
   `P(not available) ≥ p0 − that`." **Refuted.** A p4c/A1 share draw can be
   *exactly* zero (the named share floor binds), so zeros are not multinomial
   sampling events. The bound claims RB2 is absent in ≥16.8% of draws where the
   identified value is 0.86%.

### What is therefore honestly not identified

For a player modelled in **one** room, `PARTICIPATION` and `PLAYER_ALLOCATION`
are **not separable from the sealed draws**, because the appearance indicator is
not stored — only its products are. Those metrics resolve to `UNKNOWN` with
`unresolved_between = (PARTICIPATION, PLAYER_ALLOCATION)` and the bound
`P(A=0) ≤ p0`. That is 26 of the 67 material volume metrics and **18.2% of the
board's total gap**.

**The fix is instrumentation, not estimation.** Storing the appearance indicator
in the sealed draw set — one bit per player per draw, 13 × 1000 bits on this
board — closes the cell outright for every receiver and every tight end.

---

## 3. Acceptance test

The method had to reproduce the case it was designed from. It does.

### Mahomes — `ROLE_STATE`, and it is the whole gap

| | |
|---|---|
| unconditional | **144.02** |
| P(zero) | **0.413** |
| conditional | **245.34** |
| gap | **101.33** |
| dominant | **ROLE_STATE, 99.8% of the zero mass, 101.08 of the 101.33 yards** |

Everything else is **ruled out by measurement**, which is the point — each of
these is a number, not a narrative:

- `PARTICIPATION` — **structurally impossible**, not merely absent. The
  quarterback layer has no appearance channel, and the board's own
  `qb_inactive_ownership` shows `enforced: false` with
  `inactive_qbs_excluded: {}`, so no availability mechanism touched any QB row.
- `TEAM_VOLUME` — 0 of 413 zero draws. KC dropbacks 41.47, DEN 37.19.
- `EFFICIENCY` — 1 of 413 zero draws (0.245 yards). Conditional level
  **245.34 yards on 34.41 attempts = 7.1298 per attempt**, against Nix's 6.6254
  in the same game.
- `PLAYER_ALLOCATION` / `OTHER_RESIDUAL` — Σ receptions == Σ KC completions
  **exactly** (max deviation 0.0 across 1000 draws); Σ receiving yards == Σ
  passing yards to 5.7e-14; KC carries 25.2449 = RB 19.5193 + QB rush 5.5700 +
  **0.1555 unowned (0.62%)**.
- `ELIGIBILITY` — the reserve-list quarterback was already removed
  (`qb_pool_eligibility`: 7 in, 6 kept, `dropped_by_status {RES: 1}`) and the
  pathology persists.

The mechanism, named by the artifact rather than inferred: KC's room is
`NO_PREV_PRIMARY_IN_ROOM` with `prev_primary_ordinal 202518` and
`week1_specification_defect: true`. **The on-board control localises it** — DEN's
room, same code, same slate, same seed, resolves `AGREE` and gives its QB1
`p0 = 0.048` against Kansas City's 0.412, a factor of 8.6.

### Nix — not flagged

| metric | U | p0 | C | ratio | material? |
|---|---|---|---|---|---|
| `qb/pyds` | 202.35 | 0.049 | 212.78 | 1.052 | **no** |
| `qb/att` | 30.54 | 0.048 | 32.08 | 1.050 | **no** |
| `qb/db` | 34.06 | 0.048 | 35.78 | 1.050 | **no** |

He is not flagged because the gap is 5%, below the declared materiality gate of
1.10. Two things are worth saying plainly rather than glossed:

- **His mechanism is the same label, ROLE_STATE.** The gate is *materiality*,
  not a different mechanism. A method that gave him a different label would be
  inventing a distinction the engine does not make, and the test asserts he
  still reads `ROLE_STATE` so that nobody later "fixes" this into a false
  contrast.
- Nix's `p0 = 0.048` sits *inside* the clean-cell reference the artifact itself
  carries for a (rank 1, is previous primary) room, `P(share=0) = 0.0736`. So
  there are two independent reasons not to flag him.

---

## 4. Tonight's board: every material gap

Materiality gate: `C/U ≥ 1.10`, i.e. `p0 ≥ 1/11`. Declared as a ratio because
the gap identity is multiplicative, so one threshold covers every metric in
every unit with no per-metric constant. It is a *reporting* threshold and moves
no number.

**113 material metrics on 19 players**, of which **67 are volume metrics**
(the ones a market would price). Aggregate attribution of the 630.95 units of
volume gap:

| mechanism | gap carried | share | metrics where dominant |
|---|---|---|---|
| `ROLE_STATE` | 445.92 | **70.7%** | 30 |
| `UNKNOWN` (participation \| allocation) | 114.64 | **18.2%** | 26 |
| `EFFICIENCY` | 39.29 | 6.2% | 1 |
| `PLAYER_ALLOCATION` | 18.08 | 2.9% | 4 |
| `PARTICIPATION` | 13.03 | 2.1% | 6 |
| `TEAM_VOLUME` | 0.00 | 0.0% | 0 |
| `OTHER_RESIDUAL` | 0.00 | 0.0% | 0 |

Split by layer, which is the more useful cut:

- **Quarterbacks, 465.57 units of gap: `ROLE_STATE` 95.8%, `EFFICIENCY` 4.2%.**
  Every one of the six quarterbacks on the board, both clubs, starters and
  backups.
- **Non-quarterbacks, 165.39 units: `UNKNOWN` 69.3%, `EFFICIENCY` 11.9%,
  `PLAYER_ALLOCATION` 10.9%, `PARTICIPATION` 7.9%, `ROLE_STATE` 0.0%.**

### The material volume metrics, largest gap first

| team | slot | metric | U | p0 | C | gap | dominant mechanism |
|---|---|---|---|---|---|---|---|
| KC | QB1 | pass yards | 144.02 | 0.413 | 245.34 | 101.33 | ROLE_STATE 0.998 |
| DEN | QB2 | pass yards | 14.06 | 0.837 | 86.24 | 72.19 | ROLE_STATE 0.959 |
| KC | QB2 | pass yards | 72.59 | 0.472 | 137.49 | 64.90 | ROLE_STATE 0.966 |
| KC | QB3 | pass yards | 34.57 | 0.451 | 62.96 | 28.40 | ROLE_STATE 0.929 |
| KC | WR6 | rec yards | 8.26 | 0.753 | 33.42 | 25.17 | UNKNOWN 0.884 |
| DEN | QB3 | pass yards | 4.54 | 0.841 | 28.55 | 24.01 | ROLE_STATE 0.941 |
| KC | QB2 | rush yards | 21.49 | 0.496 | 42.64 | 21.15 | ROLE_STATE 0.919 |
| KC | WR3 | rec yards | 13.88 | 0.544 | 30.44 | 16.56 | UNKNOWN 0.754 |
| KC | QB1 | dropbacks | 22.82 | 0.412 | 38.82 | 15.99 | ROLE_STATE 1.000 |
| KC | QB1 | attempts | 20.20 | 0.412 | 34.36 | 14.15 | ROLE_STATE 1.000 |
| KC | TE4 | rec yards | 7.47 | 0.639 | 20.69 | 13.22 | UNKNOWN 0.898 |
| KC | WR4 | rec yards | 14.54 | 0.474 | 27.64 | 13.10 | UNKNOWN 0.833 |
| KC | TE3 | rec yards | 2.83 | 0.816 | 15.41 | 12.57 | UNKNOWN 0.993 |
| KC | QB2 | dropbacks | 13.20 | 0.456 | 24.26 | 11.06 | ROLE_STATE 1.000 |
| KC | WR5 | rec yards | 5.72 | 0.656 | 16.62 | 10.90 | UNKNOWN 0.916 |
| KC | QB1 | rush yards | 12.91 | 0.450 | 23.48 | 10.57 | ROLE_STATE 0.916 |
| KC | QB1 | completions | 13.29 | 0.413 | 22.64 | 9.35 | ROLE_STATE 0.998 |
| KC | TE2 | rec yards | 12.33 | 0.428 | 21.55 | 9.23 | UNKNOWN 0.860 |
| DEN | QB2 | dropbacks | 2.26 | 0.803 | 11.47 | 9.21 | ROLE_STATE 1.000 |
| DEN | QB2 | rush yards | 0.97 | 0.902 | 9.94 | 8.97 | ROLE_STATE 0.890 |
| KC | QB2 | attempts | 10.34 | 0.462 | 19.21 | 8.88 | ROLE_STATE 0.987 |
| KC | WR2 | rec yards | 27.17 | 0.245 | 35.99 | 8.82 | UNKNOWN 0.759 |
| KC | RB2 | rec yards | 6.26 | 0.582 | 14.99 | 8.72 | PLAYER_ALLOCATION 0.875 |
| DEN | QB2 | attempts | 1.92 | 0.817 | 10.50 | 8.58 | ROLE_STATE 0.983 |
| DEN | QB3 | rush yards | 0.61 | 0.928 | 8.46 | 7.85 | ROLE_STATE 0.852 |
| KC | RB3 | rec yards | 9.56 | 0.438 | 17.01 | 7.45 | PARTICIPATION 0.559 |
| KC | RB1 | rec yards | 15.28 | 0.318 | 22.40 | 7.12 | UNKNOWN 0.456 |
| DEN | QB2 | completions | 1.19 | 0.837 | 7.32 | 6.13 | ROLE_STATE 0.959 |
| KC | QB2 | completions | 6.76 | 0.472 | 12.80 | 6.04 | ROLE_STATE 0.966 |
| KC | QB3 | rush yards | 2.50 | 0.698 | 8.27 | 5.77 | ROLE_STATE 0.600 |
| KC | QB3 | dropbacks | 5.47 | 0.419 | 9.41 | 3.94 | ROLE_STATE 1.000 |
| KC | QB3 | attempts | 4.87 | 0.421 | 8.41 | 3.54 | ROLE_STATE 0.995 |
| DEN | QB3 | dropbacks | 0.90 | 0.791 | 4.31 | 3.41 | ROLE_STATE 1.000 |
| KC | QB2 | rush att | 3.36 | 0.496 | 6.67 | 3.31 | ROLE_STATE 0.919 |
| DEN | QB3 | attempts | 0.77 | 0.804 | 3.94 | 3.17 | ROLE_STATE 0.984 |
| KC | QB3 | completions | 3.23 | 0.451 | 5.88 | 2.65 | ROLE_STATE 0.929 |
| DEN | QB3 | completions | 0.48 | 0.840 | 3.03 | 2.55 | ROLE_STATE 0.942 |
| DEN | QB1 | rush yards | 20.10 | 0.110 | 22.58 | 2.48 | EFFICIENCY 0.564 |
| DEN | QB2 | rush att | 0.24 | 0.901 | 2.47 | 2.23 | ROLE_STATE 0.891 |
| KC | RB3 | carries | 3.31 | 0.382 | 5.36 | 2.05 | PARTICIPATION 0.641 |
| KC | TE3 | targets | 0.46 | 0.810 | 2.41 | 1.95 | UNKNOWN 1.000 |
| KC | RB1 | carries | 10.92 | 0.150 | 12.85 | 1.93 | **PARTICIPATION 0.967** |
| KC | TE3 | receptions | 0.42 | 0.816 | 2.29 | 1.87 | UNKNOWN 0.993 |
| KC | WR6 | targets | 0.89 | 0.666 | 2.67 | 1.78 | UNKNOWN 1.000 |
| KC | WR5 | targets | 1.18 | 0.601 | 2.95 | 1.77 | UNKNOWN 1.000 |
| KC | TE4 | targets | 1.09 | 0.574 | 2.55 | 1.47 | UNKNOWN 1.000 |
| KC | WR5 | receptions | 0.77 | 0.654 | 2.23 | 1.46 | UNKNOWN 0.919 |
| KC | QB1 | rush att | 1.73 | 0.449 | 3.13 | 1.41 | ROLE_STATE 0.918 |
| KC | TE4 | receptions | 0.75 | 0.636 | 2.06 | 1.31 | UNKNOWN 0.903 |
| KC | WR6 | receptions | 0.42 | 0.753 | 1.72 | 1.29 | UNKNOWN 0.884 |
| DEN | QB3 | rush att | 0.10 | 0.928 | 1.39 | 1.29 | ROLE_STATE 0.852 |
| KC | WR3 | targets | 1.82 | 0.410 | 3.08 | 1.26 | UNKNOWN 1.000 |
| KC | RB2 | targets | 1.14 | 0.518 | 2.36 | 1.22 | PLAYER_ALLOCATION 0.983 |
| KC | WR4 | targets | 1.85 | 0.395 | 3.05 | 1.21 | UNKNOWN 1.000 |
| KC | RB2 | receptions | 0.86 | 0.573 | 2.03 | 1.16 | PLAYER_ALLOCATION 0.888 |
| KC | WR3 | receptions | 0.96 | 0.544 | 2.10 | 1.14 | UNKNOWN 0.754 |
| KC | RB2 | carries | 5.29 | 0.169 | 6.36 | 1.08 | PLAYER_ALLOCATION 0.947 |
| KC | QB3 | rush att | 0.48 | 0.690 | 1.55 | 1.07 | ROLE_STATE 0.607 |
| KC | RB3 | targets | 1.85 | 0.365 | 2.91 | 1.06 | PARTICIPATION 0.671 |
| KC | WR4 | receptions | 1.17 | 0.471 | 2.22 | 1.04 | UNKNOWN 0.839 |
| KC | TE2 | targets | 1.77 | 0.368 | 2.81 | 1.03 | UNKNOWN 1.000 |
| KC | RB3 | receptions | 1.35 | 0.433 | 2.38 | 1.03 | PARTICIPATION 0.566 |
| KC | TE2 | receptions | 1.28 | 0.428 | 2.24 | 0.96 | UNKNOWN 0.860 |
| KC | RB1 | targets | 2.45 | 0.275 | 3.38 | 0.93 | PARTICIPATION 0.527 |
| KC | WR2 | targets | 3.90 | 0.186 | 4.79 | 0.89 | UNKNOWN 1.000 |
| KC | RB1 | receptions | 2.00 | 0.306 | 2.88 | 0.88 | UNKNOWN 0.474 |
| KC | WR2 | receptions | 2.30 | 0.245 | 3.04 | 0.75 | UNKNOWN 0.759 |

The remaining 46 material metrics are conversion markets — touchdowns,
interceptions, sacks, scrambles — where the split is `ROLE_STATE` 22,
`EFFICIENCY` 19, `UNKNOWN` 4, `PLAYER_ALLOCATION` 1. `EFFICIENCY` dominating a
touchdown market is the correct reading and is why step 3 of the cascade exists:
a back with carries who does not score is a conversion zero, not an access one.

**Three readings worth pulling out.**

1. The diagnostic is **direction-agnostic**. DEN's QB2 shows the mirror image of
   Mahomes: an unconditional 14.06 passing yards against a conditional 86.24, a
   ratio of 6.14, `ROLE_STATE` 95.9%. A backup's low projection and a contaminated
   starter's low projection are the *same mechanism* at different magnitudes, and
   the method says so.
2. **`TEAM_VOLUME` is 0.0% of the board.** Not "small" — zero draws, on every
   metric. Whatever is wrong with tonight's numbers, it is not that either side
   is forecast to run no plays.
3. **`ROLE_STATE` carries 70.7% of the board's gap and 95.8% of the quarterback
   gap.** The board's own `qb_participation_limitation` already says quarterback
   markets are contaminated and inadmissible on a season opener. This puts a
   number on how much of the board that statement is about.

---

## 5. D4's second boundary pathology, and the label this taxonomy lacks

D4 found `role_prior.assign_tiers` (`nfl/production/nonqb/role_prior.py:147-176`)
ranking a room by prior-season trailing snap share and appending every
no-history player *after* every veteran who has any (`start = len(known)`, line
170); `role_prior.weight` returns the tier mean **exactly** at `n_own = 0`, so
for such a player the tier is the entire forecast. `R8_FLAGS` inherits
`role_prior=True`, so it is live on tonight's run.

**It does not fit any label in the given set, and I have not stretched one onto
it.** A third label is needed. It should be called **`ROLE_PRIOR`**.

| | `ROLE_STATE` | **`ROLE_PRIOR`** | `PLAYER_ALLOCATION` |
|---|---|---|---|
| what it is | which player holds a **rivalrous** role | the player's allocation **centre** in a non-rivalrous room, set by a prior-season ranking | the realised split, given that centre |
| varies across draws? | **yes** — a per-draw indicator | **no** — constant in every draw of the run | yes |
| identified within one run? | yes | **no** | yes |
| evidence needed | the room's per-draw share vector | an **external** statement of current role, plus prior-season history | the draws |
| tonight | Mahomes, 412 of 1000 draws | `assign_tiers` line 170 | receiver thinness |

The decisive point, and it is structural rather than a matter of taste:
**because `ROLE_PRIOR` does not vary across draws, no across-draw statistic can
separate it from `PLAYER_ALLOCATION`.** It is a bias in the *location* of an
allocation, not an event inside one. Separating them needs a different *kind* of
evidence — an external statement of the player's role compared against the
ordering the model delivered.

Note also the **shared upstream cause**: Mahomes and this defect both reach
across the season boundary for a prior. That is an *input contamination*
(`SEASON_BOUNDARY_PRIOR`) feeding two different channels. Naming the
contamination is useful. Collapsing the two channels into one label would not
be — they have different signatures, different detectability and different fixes.

### What is computable: a screen, and it is only a screen

`board.json` carries `depth_chart`, which is exactly such an external statement,
so `attribution.role_prior_screen` compares the chart's ordering of each
`(team, position)` room — `assign_tiers`'s own grouping key — against the
ordering the draws deliver, and puts a magnitude on any disagreement. The
magnitude is a **swap-equivalent delta**: what each of an inverted pair would
project if their room shares were exchanged. It is an arithmetic restatement of
this board and nothing else. No estimator is re-run. Nothing is applied.

**Result on tonight's board:**

| room | severity | inversions | rank-1 displaced |
|---|---|---|---|
| KC WR / targets | MILD_ADJACENT_INVERSIONS | 1 (WR3 ranked 4th) | **0** |
| KC TE / targets | MILD_ADJACENT_INVERSIONS | 1 (TE3 ranked 4th) | **0** |
| KC RB / targets | MILD_ADJACENT_INVERSIONS | 1 (RB2 ranked 3rd) | **0** |
| KC RB / carries | CHART_AND_MODEL_AGREE | 0 | **0** |

| player | chart | model rank | share given present | swap-equivalent delta |
|---|---|---|---|---|
| KC RB2 | RB2 | 3 | 0.4442 | **+0.147 targets** |
| KC TE3 | TE3 | 4 | 0.2149 | +0.052 targets |
| KC WR3 | WR3 | 4 | 0.1650 | +0.051 targets |

So: **the mechanism is active and its severe signature is absent from the
players on this board.** D4's 47-of-47 case is a chart-rank-1 player with no
trailing history; every KC rank-1 here holds model rank 1, because every KC
starter has history. The three inversions found are adjacent swaps worth at most
0.15 targets. That is the honest reading and it is not reassurance: the board
carries only **one club's** skill players, because DEN's are deferred, so the
screen has seen 13 of the ~27 it should have.

### What is not computable, and this is itself the finding

Whether any inversion **is** the `assign_tiers` defect, rather than a p4c weight
legitimately disagreeing with a club's published chart, is **unattributable from
the sealed artifact**. The run records neither the trailing-history input nor the
assigned tier. D4 also reports `board.json` has no role or tier field and that
`name` is `None` for every player because the roster `full_name` column does not
survive the reduce step; both are consistent with what I read.

**Recording `tier` and `basis` from `assign_tiers` on the sealed board would turn
the screen into an identification.** That is instrumentation, not estimation, and
together with storing the appearance indicator it is the cheapest pair of
changes available to this diagnostic. Neither touches an estimator.

### And a caveat that travels with every PARTICIPATION number

D4 reports R7/R8's carried appearance features **invert** across the season
boundary: `prev_appeared == 0` gives an in-season appearance rate of 0.2778
(n=19,499) against **0.5079 crossed** (n=1,134); `f_rate_ewma < 0.3` gives 0.3543
against **0.7036 crossed**. R8 carries these on one slope and the existing repair
moves an intercept only, and an intercept cannot correct a slope whose sign
flips.

The consequence for this report is precise and worth stating exactly. Every
`PARTICIPATION` mass here is **correctly attributed** — it *is* the mass the model
assigns to the player not taking the field, and the dual-room estimator recovers
it to 1e-4 under a volume control. Whether that mass is the **right size** is a
different question and D4's evidence says it is not, on a week-1 board. So
RB1's 0.1453 is a faithful measurement of the model and a suspect statement about
football. This report says that and changes nothing. The caveat is carried inside
the artifact (`participation_caveat`), not only in this prose.

---

## 6. Structurally unattributable today

| mechanism | status | why |
|---|---|---|
| `GAME_STATE` | **NOT_MODELLED_IN_V1** | No game-state conditioning at any layer, so no draw in this artifact can be moved by score, clock or win probability. `OPEN_DEFECTS` D09, unrepaired. |
| `INJURY_LIMITATION` | **NOT_MODELLED_IN_V1** | V1 models whether a player appears, never how much he is limited once he does, and has no in-game injury transition — `OPEN_DEFECTS` D17 records a starter injured early and replaced, which the engine cannot represent. |
| `ROLE_PRIOR` | **NO LABEL, SCREEN ONLY** | §5. Constant across draws, so no within-run statistic reaches it; the tier and its basis are not recorded. |
| `PARTICIPATION` vs `PLAYER_ALLOCATION`, single-room players | **UNIDENTIFIED** | The appearance indicator is not stored, only its products. 26 metrics, 18.2% of the board's gap. |
| `ELIGIBILITY` at row level | **COUNT ONLY** | 161 of 180 ids in the modelled pool carry no distribution. The run records the count and an aggregate reason, not a per-row cause, so this module cannot say which were dropped for roster status, which for DEN's team deferral, and which were never skill positions. |

**These carry `None`, never `0.0`.** A measured zero and an absent layer are
different facts and the module refuses to render them the same colour; residual
lands in `OTHER_RESIDUAL`, which is named and is 0.0000 everywhere here. The
test suite asserts that no residual ever reaches `GAME_STATE` or
`INJURY_LIMITATION`.

---

## 7. Notes for the coordinator

- **On merging with D1.** They should merge, in one direction only. D1's
  `decomposition.py` reads the same sealed run and grades every link
  (`MEASURED_DRAWS`, `DERIVED_BY_DIVISION`, `ABSENT`), which is strictly better
  than my §1 level factorisation — my `per_unit` is exactly a
  `DERIVED_BY_DIVISION` quantity and does not say so. **`attribution.level_factors`
  should be replaced by D1's graded chain.** The zero-mass cascade should *not*
  merge into it: a decomposition answers "what chain produced this number" and an
  attribution answers "which mechanism produced the gap", and folding the second
  into the first would bury the identification argument that is most of its value.
  I built my own reader rather than blocking on D1, so nothing is coupled yet.
- **On reference bands.** The conditional-level half currently uses only
  *within-game* references (the opposite club, the same room). Where D3's
  `refbands` become available, `level_factors` should take a band and report
  `RULED_OUT` / `OUTSIDE_BAND` instead of emitting bare factors. I have not
  touched `nfl/research/refbands/`.
- **Files touched:** `nfl/product/attribution.py` (new),
  `nfl/tests/test_product_attribution.py` (new),
  `nfl/research/v2/d2/` (new). Nothing else. No commit, no add, no stash, no push.
  `git status` shows only my three additions among the working tree's changes.
