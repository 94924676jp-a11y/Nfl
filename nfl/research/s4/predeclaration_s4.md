# Stage 4 pre-declaration — receiving target oracle decomposition

Written 2026-09-08 **before any Stage 4 number existed**. HEAD `bd8c828`.

Authorised by Stage 2's `ADEQUATE_FOR_TARGET_DECOMPOSITION`, and bound by its
**mandatory labelling constraint**.

## 0. The labelling constraint, carried forward verbatim

The participation component is **pass-snap participation**, an upper bound on
route participation, because a player on the field for a dropback may block. It
is **not routes run**. This study may not conclude anything about the value of
route information as such. The gap between the two is directional but its
magnitude is unbounded from available data and is not assumed to be small.

## 1. The question

Where does next-game receiving-target error come from, once participation is
represented explicitly rather than folded into target share?

This is an oracle decomposition. **No feature ladder is executed.** Its job is
to decide what deserves the next research unit, not to spend it.

## 2. The factorisation

For player *i* in team-game *g*, targets factor exactly:

```
targets_i = A_i x T_g x P_i x R_i
```

- **A** appearance
- **T** team passing opportunity (the team-targets volume draw)
- **P** participation: the player's share of team dropbacks on which he was on
  the field
- **R** allocation conditional on participation: target weight per unit of
  participation

The accepted P4C targets system C supplies the baseline allocation weight `W`.
It is **reparametrised, not replaced**: `P_hat` is Stage 2's accepted
participation forecast (EWMA half-life 2), clipped below at 1e-3, and
`R_hat := W / P_hat_clipped`, so that `P_hat x R_hat = W` **exactly**. The
realised counterparts are `P* = pass_snaps / team_dropbacks` and
`R* = W* / P*`, with `R* = 0` where `P* = 0` (no pass snaps means no targets).

## 3. The two identities that make the decomposition valid

1. **The baseline corner must reproduce the accepted artifact exactly.** The
   all-projected corner is P4C targets system C and must match
   `p4c_results.json` at `targets/<season>/scores/C/crps` through Rule 006,
   tolerance **0.0**. If it does not, the decomposition is refused.
2. **The all-oracle corner must reproduce the realised targets** within
   numerical tolerance. Pre-declared tolerance: mean absolute identity error
   **< 1e-4 targets**. If it does not, the decomposition is invalid and is
   reported as such rather than interpreted.

## 4. Design

Full 2^4 factorial, 16 corners, Shapley attribution over the four components so
ordering does not decide the conclusion, plus factorial interaction terms on
the reduction scale. Walk-forward seasons 2022–2025, each reported separately.

## 5. Reported

Absolute and relative CRPS improvement per corner; MAE and RMSE changes;
Shapley value and percentage per component; interactions; season stability; and
cohorts: position (WR/TE/RB), prior appeared games (<4 / 4–9 / 10–24 / 25+),
appearance probability (<0.25 / 0.25–0.50 / 0.50–0.80 / 0.80–0.95 / ≥0.95), and
role change (prior participation step ≥ 0.15 versus stable).

## 6. Classification — thresholds fixed now

**Oracle opportunity**, as a share of the total CRPS reduction from baseline to
all-oracle:

- **LARGE** ≥ 30%
- **MEDIUM** 10% to 30%
- **SMALL** < 10%

**Recoverability evidence**, independently of size:

- **UNTESTED** — no attempt has been made to recover it
- **ONE_NARROW_TEST** — one experiment, one design
- **MULTIPLE_INDEPENDENT_TESTS** — several, differing in design
- **PROSPECTIVE** — recovered on genuinely unseen data

**Oracle opportunity is not recoverability.** A LARGE oracle with UNTESTED
recoverability is a question, not an opportunity, and will be reported as one.

## 7. What is not done here

No feature ladder. No target-allocation model. No receiving-yard conversion. No
touchdown model. No promotion. The return **recommends** one of INVEST /
CHEAP_PROBE / HOLD / DATA_BLOCKED / INFRASTRUCTURE_FIX and **does not execute
it**.

## 8. What would count as a negative result

- If the all-oracle corner does not reproduce realised targets, the
  decomposition is reported invalid and nothing is inferred from it.
- If participation turns out to be a SMALL component, the return says the
  explicit participation layer does not buy attribution, in those words.
- If a component is large only because the reparametrisation put it there, the
  return says the split is an artefact of the construction rather than a
  finding.
