# I1 — why the sealed Q9 candidate identity stopped reproducing

Measured 2026-09-14 on branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD `2dc44ab`, `python3.12`, numpy 2.5.3. Nothing outside
`nfl/research/v2/i1/` was written, moved or staged.

## Answer in one paragraph

The fit is **not** non-deterministic, and the cause is **not** in
`fit_hurdle`. `nfl/research/p2/stage_a.py::fit_logistic` is a fixed-step
gradient descent from a zero initialisation over exactly 300 iterations with
no RNG anywhere, and it reproduces bit for bit across processes and across
BLAS thread counts. The cause is R3's uncommitted edit to
**`nfl/production/nonqb/depth_vintage.py`**, which is in the Q9 fit's import
closure through `q6.frame -> appearance_r8 -> appearance_r7 -> depth_vintage`.
It changes the depth-chart ordinal into a depth **group**, which moves the
`rank_r1 / rank_r23 / rank_r4plus_or_unlisted` features on **52.2%** of the
appeared training rows, and through `attach_role_class` it moves
`role_starter / role_rotational / role_fringe` as well. Restoring HEAD's
`depth_vintage.py` and changing nothing else reproduces the sealed identity
`82c8b52699bbeb00...` exactly.

## 1. Determinism, measured

`FRZ.fitted_parameter_hashes(2024)` called twice in one process, and once each
in four separate processes with `OMP_NUM_THREADS` /
`OPENBLAS_NUM_THREADS` / `MKL_NUM_THREADS` set to 1, 2, 4 and left at the
default:

| run | coefficients | standardiser mu | standardiser sd |
|---|---|---|---|
| in-process #1 | `ef28b13db8612cb0` | `d3d534bc89a30cb2` | `3b60ac302bf8ea94` |
| in-process #2 | `ef28b13db8612cb0` | `d3d534bc89a30cb2` | `3b60ac302bf8ea94` |
| separate proc, threads=1 | `ef28b13db8612cb0` | `d3d534bc89a30cb2` | `3b60ac302bf8ea94` |
| separate proc, threads=2 | `ef28b13db8612cb0` | `d3d534bc89a30cb2` | `3b60ac302bf8ea94` |
| separate proc, threads=4 | `ef28b13db8612cb0` | `d3d534bc89a30cb2` | `3b60ac302bf8ea94` |

Identical every time. The estimator is

    w = zeros(n_features)
    for _ in range(300):
        p = sigmoid(clip(Xs @ w, -30, 30))
        g = Xs.T @ (p - y) / n + l2 * w / n;  g[0] -= l2 * w[0] / n
        w -= 0.5 * g

— no seed, no initialisation draw, no convergence test, no iteration-order
dependence. There is nothing in it that could vary. **The non-determinism
hypothesis is withdrawn.**

## 2. The "exactly one field differs" claim is an artifact of the seal

`SEALED_FORECAST.json`'s `candidate` block exposes only 10 of the 17
`IDENTITY_FIELDS`. `standardiser_sha16`, `class_prior_sha16`,
`share_shrinkage_k`, `mechanism_spec_version`, `n_features` and
`module_source_sha16` are **not in it**, so they could not have been checked
against it — and `grep -rn` finds the sealed coefficient value
`dee95526cf43e869` in exactly three places, none of which carries a
standardiser hash.

`nfl/prospective/q9shadow/Q9_PROSPECTIVE_CANDIDATE.json` is a committed,
unmodified artifact that **does** record all 17 fields, at season 2026. Live
identity against it:

| field | sealed | live (working tree) |
|---|---|---|
| `coefficient_sha16` | `9491bb9f4b09b6a2` | `a4e85c5a3f53bed2` |
| `standardiser_sha16` | `9bc34ec6da42b07f:69307c2004799e0a` | `5065d25a39071fb3:b147d1f914fa1c1d` |
| `class_prior_sha16` | `171212d5426ea16a` | `825fcad0e0bda0a7` |
| `n_training_rows` (recorded, not an identity field) | 50965 | 50924 |

The other 14 identity fields reproduce, including all seven
`module_source_sha16` entries and `production_interface_sha16`
(`481f005f682cd721`).

**Three fitted blocks moved, not one, and the training frame lost 41 rows.**
Only the coefficient block is visible in the seal, which is why it looked like
a lone field. The design matrix is *not* identical, so the inference "identical
inputs are producing different `w`" does not hold.

## 3. The import closure, checked

36 repository modules are imported while computing `identity()`. The full list
was captured from `sys.modules`. Of the seven files with uncommitted edits:

| file | in the Q9 fit's closure? |
|---|---|
| `nfl/production/nonqb/depth_vintage.py` | **YES** — `q6.frame` → `appearance_r7`/`appearance_r8` → `DV.weekly` / `DV.daily` |
| `nfl/production/nonqb/qb_allocation.py` | no |
| `nfl/production/nonqb/role_prior.py` | no |
| `nfl/production/nonqb/football_engine.py` | no |
| `nfl/production/nonqb/rushing_a1.py` | no |
| `nfl/production/run_forecast.py` | no |
| `nfl/product/board.py` | no |

So R4's attribution is **half right and half wrong**, and I1's reading is also
half wrong: `qb_allocation.py` and `role_prior.py` are genuinely not in the
closure, but `depth_vintage.py` is, and it is the one that matters.

Note what this exposes: `module_source_sha16` hashes seven modules and calls
them "every module the mechanism executes". The closure is 36. `depth_vintage`,
`appearance_r7`, `appearance_r8`, `appearance_model`, `q7.panel`,
`p3_features`, `p4b_volume`, `p4c_lib` and **`stage_a` — the estimator
itself** — are all unhashed. A change to any of them moves the fitted blocks
without moving a single module hash, which is exactly what happened.

## 4. Proof by substitution

The HEAD blob of `depth_vintage.py` was loaded into `sys.modules` before the
closure imported it; nothing else was changed, and no file in the repository
was touched.

    subs      : ['depth_vintage']
    season    : 2024
    sealed sha: 82c8b52699bbeb00e656a3d543f995bac7034e9a89ff2a8d783e27b6fdc8422e
    live sha  : 82c8b52699bbeb00e656a3d543f995bac7034e9a89ff2a8d783e27b6fdc8422e
    MATCH     : True
    coef      : dee95526cf43e869   sealed dee95526cf43e869
    n_training_rows: 33147   (working tree: 33108)

At season 2026 the same substitution restores all 17 fields — `differing_fields=[]`,
`coefficient_sha16=9491bb9f4b09b6a2`, `n_training_rows=50965`.

Single cause, fully accounted for. No second contributor.

## 5. Magnitude

Season 2024 (`train = s < 2024`), 22,815 appeared rows in both fits, matched
row-for-row on `(season, week, team, pid)`.

**Features.** The only columns that move are the three depth columns and, via
`attach_role_class`, the three role columns — `mu` and `sd` differ on exactly
`role_starter, role_rotational, role_fringe, rank_r1, rank_r23,
rank_r4plus_or_unlisted` and on nothing else.

| feature | mean, HEAD | mean, working tree | rows changed |
|---|---|---|---|
| `rank_r1` | 0.2388 | 0.4291 | 7,071 (30.99%) |
| `rank_r23` | 0.4436 | 0.4926 | 11,225 (49.20%) |
| `rank_r4plus_or_unlisted` | 0.3176 | 0.0783 | 5,526 (24.22%) |
| any of the three | — | — | **11,911 (52.21%)** |

`y` (targets > 0) is **identical on every one of the 22,815 rows** — zero
disagreements. This is a feature change, not an outcome change, which is the
right way round: no realised quantity moved.

The 39 rows the frame loses at season 2024 (33,147 → 33,108) are all
non-appeared rows, so the fit's row count is unchanged; they are players the
repaired chart no longer ranks.

**Coefficients.** `max|dw| = 0.0914`, `||dw|| / ||w|| = 0.0664`.

| coefficient | HEAD | working tree | delta | relative |
|---|---|---|---|---|
| `rank_r23` | +0.03608 | −0.05535 | −0.09143 | 2.53 |
| `rank_r1` | +0.02476 | +0.10586 | +0.08110 | 3.28 |
| `prior_share_given_positive` | +1.03866 | +0.99278 | −0.04588 | 0.044 |
| `rank_r4plus_or_unlisted` | −0.06118 | −0.09205 | −0.03087 | 0.505 |
| `pos_TE` | −0.11033 | −0.09043 | +0.01989 | 0.180 |
| `intercept` | +1.70265 | +1.72119 | +0.01854 | 0.011 |

`rank_r23` **changes sign**. That is not rounding noise; it is the coefficient
being re-estimated against a differently-defined regressor.

**Predictions.** Fitted `P(targeted | appears)` on the 22,815 training rows:

    max |dp|  0.3045
    mean |dp| 0.01908
    p99 |dp|  0.0836
    corr      0.991555
    mean p    0.75575 (HEAD) vs 0.75574 (working tree)

So the marginal is untouched to five decimals and the correlation is 0.9916,
but individual players move by up to **30 percentage points** of hurdle
probability. This is materially different for a per-player forecast and
immaterial for a team aggregate — which is the signature of a role-ordering
change, and is consistent with what R3 says the repair is for.

## 6. Does it block tonight's board (`2026_01_DEN_KC`, kickoff 00:15Z)?

**The failing check does not block it. The change underneath it might.**

- Nothing in `nfl/production/` or `nfl/product/` imports `nfl.prospective.q9shadow`,
  `nfl.research.q9`, or anything named `hurdle`. `grep -rn` over both trees
  returns zero matches. Q9 is shadow-only in fact, not just in declaration, and
  the three hashes that moved are Q9 candidate-identity hashes that only the
  shadow ledger consumes.
- **But** `nfl/product/board.py` imports `depth_vintage` directly (line 29),
  `run_forecast.py` feeds `depth_rank` into `role_prior` (line 974) and calls
  `appearance_r8` (line 999), and `appearance_r8`/`appearance_r7` both import
  `depth_vintage`. So the board's appearance and role inputs move with R3's
  edit. The Q9 test is the first thing that noticed, because it is the only
  thing in the tree holding a sealed hash of a fit built on those features.
- Read that way the check did its job: it detected a production-path input
  change. The thing to settle before kickoff is R3's repair, not Q9.

## 7. What the repair is — and what it is not

It is **not** "make the fit deterministic": the fit is already deterministic,
and a seed would change nothing. It is **not** re-sealing, loosening, or
pinning the hash to the current tree.

The mechanism's own rule already answers it. `candidate.py`:

> any such change is a NEW candidate requiring a NEW freeze; it cannot inherit
> this standing

R3's repair changes the features the frozen Q9 candidate consumes. By that
rule the Q9 shadow candidate frozen on the old depth ordering is **superseded**
the moment the repair lands, and needs a new freeze, a new
`Q9_PROSPECTIVE_CANDIDATE.json` and new dry-run seals, explicitly recorded as a
new candidate rather than the old one continuing. That is a governance call for
the owner and for R3, not something to be patched green.

### Patch A — diagnostic only, hand to whoever owns `nfl/tests/test_c1_denominator.py`

Costs nothing, changes no identity, and would have turned this investigation
into a one-line read. In `test_c_the_frozen_q9_identity_is_not_disturbed`,
replace the single `check(...)` with a named-field comparison:

```python
    a = json.loads(sealed.read_text())
    live = CAND.identity(a['season'])
    got = CAND.identity_sha256(live)
    want = a['candidate']['identity_sha256']
    visible = [f for f in CAND.IDENTITY_FIELDS if f in a['candidate']]
    moved = [f for f in visible
             if json.dumps(live.get(f), sort_keys=True, default=str)
             != json.dumps(a['candidate'][f], sort_keys=True, default=str)]
    if got == want:
        detail = want[:16]
    elif moved:
        detail = f'{want[:16]} -> {got[:16]}; moved: ' + ', '.join(moved)
    else:
        # THE SEAL CANNOT SEE EVERY IDENTITY FIELD, AND SAYS SO. Reading
        # "only the coefficient moved" off a seal that records 10 of 17
        # fields is how this cost a day.
        detail = (f'{want[:16]} -> {got[:16]}; no VISIBLE field moved -- the '
                  f'seal records only {len(visible)} of '
                  f'{len(CAND.IDENTITY_FIELDS)} identity fields, so compare '
                  f'against Q9_PROSPECTIVE_CANDIDATE.json, which records all '
                  f'of them')
    check('  so the sealed Q9 candidate identity still reproduces',
          got == want, detail)
```

The `else` branch is the load-bearing half: it says out loud that the seal
carries only 10 of 17 fields, so "only the coefficient moved" is never again
inferred from a seal that cannot show the other seven.

### Patch B — structural, and NOT to be applied on its own

`identity()`'s `module_source_sha16` should cover the closure it claims to:
add `nfl.production.nonqb.depth_vintage`, `appearance_r7`, `appearance_r8`,
`appearance_model`, `nfl.research.q7.panel`, and `stage_a` (the estimator).
`assert_identical_to_freeze` already treats the freeze's module set as a
required subset and explicitly permits additions, so the freeze comparison
survives — **but `identity_sha256` changes**, which invalidates the four sealed
dry-run artifacts. So Patch B is only coherent as part of issuing the new
freeze that R3's repair requires anyway. Applying it to make a test pass would
be pinning a hash to the current tree with extra steps.

## 8. Unrelated, and blocking everyone: a 20 GB temp leak

`nfl/production/nonqb/appearance_model.py::stage_inputs` calls
`tempfile.mkdtemp(prefix='nfl-appearance-')` **once per process** and never
removes the directory. Each one is 33 MB. There were **619** of them on this
machine, and `/` reached 100% full (1.7 MB free) partway through this
investigation. That is why the suite was not re-run here — a suite run stages
another 33 MB and cannot.

Two things follow. First, the measurement in section 4 was obtained by
verifying an existing staged directory against `INPUT_MANIFEST.json`
(every `sha256_decompressed` checked, including `panel.csv` against
`panel_p3.csv`) and assigning it to `_STAGE`, so no new directory was created.
Second, `stage_inputs` should either stage into one content-addressed
directory keyed by the manifest hash, or register an `atexit` cleanup. Until
then every suite run on this machine costs 33 MB permanently, and the
filesystem is already at 100%.

I removed only the incomplete, crashed staging directories (a partial one of my
own included). I did not touch the complete ones: other agents may be running
against them, and a sweep of a shared scratch area is not mine to make.

## Reproduce

Working files are under `nfl/research/v2/i1/` and the probe scripts in the
session scratchpad. The one command that settles it, with `<i1>` the scratchpad:

    python3.12 <i1>/probe7.py depth_vintage     # -> MATCH : True
    python3.12 <i1>/probe7.py                   # -> MATCH : False
