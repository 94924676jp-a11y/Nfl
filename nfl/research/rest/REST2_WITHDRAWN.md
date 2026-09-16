# REST2 is WITHDRAWN. The rest-state limitation is ACCEPTED as unresolved.

Built exactly as pre-registered, forward-chained 2022-2025, same frame, same
`is_unsupported` exclusion, same `l2`, same reliability `k` in both arms. Gates
unchanged from `predeclaration_rest2.md`. Raw numbers in `REST2_RESULT.json`.

## Coefficients, all four, with standard errors, whatever their signs

| fit for | column | coefficient | SE | z |
|---|---|---|---|---|
| 2022 | `L` | −0.187174 | 0.456334 | −0.41 |
| | `L × prev_appeared` | +0.070297 | 0.617180 | +0.11 |
| | `L × prev_snap` | −0.079411 | 0.496216 | −0.16 |
| | `L × prev_snap_missing` | +0.074467 | 0.510566 | +0.15 |
| 2023 | `L` | −0.228012 | 0.344269 | −0.66 |
| | `L × prev_appeared` | +0.115740 | 0.547014 | +0.21 |
| | `L × prev_snap` | −0.109644 | 0.382045 | −0.29 |
| | `L × prev_snap_missing` | +0.091024 | 0.387584 | +0.24 |
| 2024 | `L` | −0.251479 | 0.299800 | −0.84 |
| | `L × prev_appeared` | +0.114830 | 0.538366 | +0.21 |
| | `L × prev_snap` | −0.097062 | 0.329439 | −0.30 |
| | `L × prev_snap_missing` | +0.090517 | 0.339661 | +0.27 |
| 2025 | `L` | −0.261436 | 0.273831 | −0.96 |
| | `L × prev_appeared` | +0.090624 | 0.534217 | +0.17 |
| | `L × prev_snap` | −0.086378 | 0.292879 | −0.30 |
| | `L × prev_snap_missing` | +0.085836 | 0.310868 | +0.28 |

**No interaction term reaches |z| = 0.31 in any fit**, on up to 48,298 training
rows with 2,152 carrying the flag.

## SAT vs PLAYED, weeks 1-4 pooled, n_SAT = 292 / n_PLAYED = 1,994

| arm | group | predicted | realised | gap |
|---|---|---|---|---|
| R8 | SAT | 0.693487 | 0.736301 | **−0.042814** |
| R8 | PLAYED | 0.740857 | 0.712136 | **+0.028721** |
| REST2 | SAT | 0.690061 | 0.736301 | **−0.046241** |
| REST2 | PLAYED | 0.739397 | 0.712136 | **+0.027261** |

| | differential |
|---|---|
| R8 | **−0.071535** |
| REST2 | **−0.073502** |
| change | **−0.001967** |

**Team-blocked 95% CI on the change: [−0.003777, −0.000252]** — excludes zero
**in the wrong direction** again. Required: `|new| ≤ 0.035768`. Actual
`|new| = 0.073502`.

## The other gates

| | R8 | REST2 | Δ | team-blocked 95% CI |
|---|---|---|---|---|
| weeks 1-4 Brier | 0.080557 | 0.079979 | −0.000578 | [−0.000806, −0.000349] |
| weeks 5-18 Brier | 0.092770 | 0.092719 | −0.000051 | [−0.000078, −0.000026] |
| PLAYED gap, absolute | 0.028721 | 0.027261 | **−0.001460** | [−0.002071, −0.000866] |
| weeks 1-4 log loss | 0.265092 | 0.263686 | −0.001406 | — |
| weeks 5-18 log loss | 0.296077 | 0.295877 | −0.000200 | — |

Per season weeks 1-4 Brier improves in all four: 0.080642 → 0.079677,
0.078726 → 0.078036, 0.072458 → 0.072066, 0.089585 → 0.089317.

### Complexity

    bar  = k·ln(n)/(2n) = 4 × 9.3487 / 22,968 = 0.001628
    gain = 0.265092 − 0.263686                = 0.001406      (fix B: 0.000579)

**0.001406 < 0.001628.** Four columns do not earn their place. Closer than fix
B, and still under a bar computed from `k` and `n` alone.

## Verdict

| gate | verdict |
|---|---|
| **G1** differential halves AND blocked CI excludes zero correctly | **FAIL** |
| G2 weeks 1-4 Brier not worse | PASS |
| G3 weeks 5-18 Brier not worse | PASS |
| G4 PLAYED population not degraded | PASS |
| G5 coefficients with SEs | PASS |
| **G6** BIC complexity bar | **FAIL** |
| **ALL** | **FAIL** |

**REST2 is withdrawn. R8 stands unchanged.**

## Why it failed, and this one is more interesting than fix B's

The interaction coefficients are not merely small, they are **self-cancelling**.
Take the 2025 fit and evaluate the four columns for two players who both cross
the boundary:

- a full-snap starter who played: `−0.261 + 0.091 − 0.086 × 1.0 + 0 = −0.257`
- an established starter who sat: `−0.261 + 0 − 0 + 0 = −0.261`

**A difference of 0.004 in logit.** The interaction gives the sitter and the
full-snap player essentially the same adjustment — which is precisely the
failure it was designed to repair.

The reason is redundancy, not noise. **R8 already carries `prev_appeared`**, and
the whole reliability-weighted current-season block already encodes what the
player has been doing. By the time the interaction columns are offered, the
information they carry about "what he did in that final game" is already in the
design under other names. There is nothing left for them to explain, which is
what |z| < 0.31 on 48,298 rows is telling us.

So the hypothesis is not just unsupported — it is **largely redundant with
features R8 already has**. That is a stronger negative result than fix B's and
it argues against a third variation on the same idea.

## What is ACCEPTED, and what that means

> **The rest-state limitation is UNRESOLVED and quantified.** An established
> starter who sat the last regular week is under-predicted relative to a
> comparable starter who played, by **−0.0715** in weeks 1-4 (team-blocked 95%
> CI on the R8 differential itself: [−0.1133, −0.0256]).

On DET-BUF it affects **Josh Allen** (appearance limb) and **James Cook** (snap
limb) and **no other player on the board**. The direction is known: both are
under-predicted, so their opportunity and DK lines are, if anything,
conservative.

Two pre-registered fixes have now been built, run and withdrawn on their own
declared rules. **No third fix is invented in this pass**, per
`predeclaration_rest2.md` §8.

V2 NOT YET EARNED.
