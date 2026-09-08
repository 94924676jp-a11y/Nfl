# Addendum — the pre-declared probe is VOID, and what replaces it

Written 2026-09-08, **after** the pre-declared probe was run and **before** the
repaired comparison below was run. HEAD at writing: `f2a73a3`.

## 1. What the pre-declared probe returned

Run exactly as specified in `predeclaration_proxy_probe.md`: one ridge, penalty
fixed at 1.0, `[p_ewma1, p_ewma2]` versus the same plus the five prior-only
personnel/formation EWMA(hl=2) features, same rows, walk-forward, fitted on
strictly prior seasons only.

| | n eval | MAE control | MAE treatment | relative |
|---|---|---|---|---|
| pooled 2022-2025 | 22,483 | 0.149545 | 0.136371 | **+8.8095%** |

Against a 1% bar that reads as "contains incremental signal". **It does not.**

## 2. Why it is void

Three placebos, all on the identical rows and identical specification, with only
the *content* of the five probe columns replaced:

| five probe columns replaced by | correlation with the real features | relative MAE gain |
|---|---|---|
| the real features | 1.000 | +8.8095% |
| a permutation within the same team-game | +0.36 to +0.70 | +8.9788% |
| a permutation across the whole league | +0.006 to +0.013 | +9.0253% |
| five columns of pure Gaussian noise | 0 by construction | **+9.0114%** |

Five columns of pure noise reproduce the entire effect, and slightly exceed it.

## 3. The mechanism, identified

`p_fit._fit` forms the ridge as

    A = Z.T @ Z + lam * n / max(p, 1) * eye(p)

so the penalty is divided by the column count. The control has p=2 and is
penalised at `1.0*n/2`; the treatment has p=7 and is penalised at `1.0*n/7`.
Adding *any* five columns therefore relaxes the penalty on `p_ewma1` and
`p_ewma2` by a factor of 3.5, and the measured gain is that relaxation. The
control was not a control; it was the same two features fitted 3.5x harder.

Measured directly: the control padded with five pure-noise columns, nothing
else changed, moves MAE from 0.149587 to 0.136107, **+9.0114%**.

This is not a defect in `p_fit`. The P ladder selects `lam` in an inner
validation loop per rung, which absorbs the scaling. Fixing `lam = 1.0` across
two different column counts, as the pre-declaration did, exposes it. **The
defect is mine and it is in the pre-declaration.**

The result stands as recorded and is not deleted. It is reported as **VOID —
measured the estimator, not the features**, and it may not be quoted as
evidence for or against the proxy.

## 4. The repair, fixed now, before it is run

The confound is a column-count difference. Removing the difference removes the
confound, and it requires no change to the estimator and no free choice:

**Primary comparison — column-count matched.** Treatment `[p_ewma1, p_ewma2] +
five probe features` versus reference `[p_ewma1, p_ewma2] + five pure Gaussian
noise columns`, seed 20260908. Both have p=7 and are penalised identically at
`1.0*n/7`. Same rows, same walk-forward, penalty still fixed at 1.0. Nothing is
searched and nothing is selected.

**Secondary comparison — penalty matched.** The same control-versus-treatment
contrast as originally declared, but with the penalty formed as `lam * n`
instead of `lam * n / p`, so that per-column penalty does not move with width.

**Materiality, unchanged and fixed now:** an improvement of **>= 1% relative
pooled MAE** on the primary comparison is "contains incremental signal". Below
that is "no detectable incremental signal". The primary comparison governs; the
secondary is reported for agreement or disagreement, not as a second chance.

## 5. What the repair still cannot do

Unchanged from the original pre-declaration and restated because the estimator
defect does not enlarge the probe's authority:

- It cannot promote anything, and nothing here is a candidate.
- A weak result **does not** mean true routes are weak. Personnel is not routes.
- A strong result would not be a model. It would be grounds for a *separately
  authorised* study.

One further limit, specific to this addendum: the repaired comparison is
**post-hoc**. It was specified after the void result was seen. It is written
down before it is run and its bar is unchanged, but it does not carry the
evidential standing of a genuine pre-registration, and it is labelled
`POST_HOC_REPAIR` wherever it appears.
