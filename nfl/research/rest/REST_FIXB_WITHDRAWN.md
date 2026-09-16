# Fix B is WITHDRAWN. The rest-state defect is UNRESOLVED.

Built exactly as pre-registered, forward-chained 2022-2025 on the same frame,
same exclusion, same l2, same reliability `k` handed to both arms. Raw numbers
in `REST_FIXB_RESULT.json`. Acceptance rules unchanged from
`predeclaration_rest.md`; nothing was re-tuned after seeing the result.

## The coefficient, reported whatever its sign

| fit for | coefficient | standard error | z | n_train | rows carrying the flag |
|---|---|---|---|---|---|
| 2022 | −0.151633 | 0.411668 | −0.37 | 18,915 | 539 |
| 2023 | −0.185816 | 0.306921 | −0.61 | 28,915 | 1,108 |
| 2024 | −0.206440 | 0.262187 | −0.79 | 38,639 | 1,638 |
| 2025 | −0.224773 | 0.234925 | −0.96 | 48,298 | 2,152 |

**|z| never reaches 1 in any fit.** The flag fires on 4.46% of training rows.

## SAT vs PLAYED, weeks 1-4, pooled over 2022-2025

| | n | predicted | realised | gap |
|---|---|---|---|---|
| **R8** SAT | 292 | 0.693487 | 0.736301 | **−0.042814** |
| **R8** PLAYED | 1,994 | 0.740857 | 0.712136 | **+0.028721** |
| **B** SAT | 292 | 0.692072 | 0.736301 | **−0.044229** |
| **B** PLAYED | 1,994 | 0.741270 | 0.712136 | **+0.029134** |

| | differential |
|---|---|
| R8 | **−0.071535** |
| B | **−0.073363** |
| **change** | **−0.001829** |

**Team-blocked 95% CI on the change: [−0.002321, −0.001390]**, 4,000
resamples. The interval excludes zero **on the wrong side**: the differential
moved AWAY from zero, and reliably so.

## The other three quantities

| | R8 | B | Δ (B − R8) | team-blocked 95% CI |
|---|---|---|---|---|
| weeks 1-4 Brier | 0.080557 | 0.080342 | **−0.000215** | [−0.000327, −0.000121] |
| weeks 5-18 Brier | 0.092770 | 0.092741 | −0.000029 | [−0.000052, −0.000010] |
| weeks 1-4 log loss | 0.265092 | 0.264513 | −0.000579 | — |
| weeks 5-18 log loss | 0.296077 | 0.295968 | −0.000109 | — |

Per season, weeks 1-4 Brier R8 → B: 2022 0.080642 → 0.080515, 2023 0.078726 →
0.078365, 2024 0.072458 → 0.072186, 2025 0.089585 → 0.089472. Log loss improves
in all four. Weeks 5-18 improves in all four.

## The gates

| gate | verdict |
|---|---|
| **G1** differential moves toward zero, blocked CI on the change excludes zero | **FAIL** |
| G2 weeks 1-4 Brier not worse | PASS |
| G3 weeks 5-18 Brier not worse | PASS |
| G4 coefficient reported with its standard error | PASS |
| **ALL** | **FAIL** |

**B is withdrawn.** R8 stands unchanged. Its coefficients were never touched:
this was a successor lineage, and `fit`/`featurise`/`predict` are byte-identical
to what R8 and R9 have always served.

## Why it failed, and this is the useful part

A single main effect **cannot close a differential between two groups that both
carry the flag.** Every player whose previous row is the last regular week gets
the same −0.22 nudge, whether he sat or played. SAT was already
under-predicted, so the nudge made it marginally worse, and PLAYED was
over-predicted, so the same nudge helped there — which is why overall Brier
improves by a hair while the gap it was aimed at widens.

The feature is also close to collinear with `crossed`, which R8 already
carries: for most players the row before a week-1 row IS the last week of the
previous season. That is why |z| stays under 1 on 48,298 rows.

So the pre-registered fix tested a real hypothesis and the hypothesis is
**false as stated**. The quantity that distinguishes Allen from Goff is not
*that* the previous row was the last regular week; it is **what he did in it**.
Expressing that needs an interaction, which is a different design and therefore
a different pre-registration. **It is named here and deliberately not run**,
because running it now would be choosing the model after seeing this table --
the exact move this project forbids.

## Status

**The rest-state defect is UNRESOLVED and quantified:**

> An established starter who sat the last regular week is under-predicted
> relative to a comparable starter who played, by **−0.0715** in weeks 1-4
> (team-blocked 95% CI on the R8 differential itself: [−0.1133, −0.0256] on the
> five-transition measurement frame).

On DET-BUF it affects **Josh Allen** (appearance limb) and **James Cook** (snap
limb) and nobody else on the board.

Per the owner's standing instruction, no GSVU player projection is interpreted
and no board is sealed while this is open.

V2 NOT YET EARNED.
