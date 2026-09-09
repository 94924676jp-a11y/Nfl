# A3G — the two teams in a game are no longer drawn independently

Owner ruling **B10**. Pre-registration `predeclaration_a3g.md`, sha256
`d3620883e52fd6d2da9b56403a219210e82e52d5a65bf73cbd23f1d13d4e78ea`, pinned in
`run_a3g.py` and re-verified at run time. Results `a3g_results.json`.
Post-hoc diagnostic `a3g_marginal_noise.json`, amendment
`predeclaration_a3g_addendum_01.md`.

**EXPLORATORY.** 2020-2025 are development data and 2026 week 1 has no outcomes.
Nothing is promoted. No production default changed.

---

## 1. The mechanism

A rank copula on the shared draw index. A3 already gives one team all five of
its residuals from **one** historical team-game. A3G changes only **which**
historical team-game each side of a game receives.

Per game, per draw: draw `(z_A, z_B)` bivariate normal with correlation `rho`;
map to uniforms `u = Phi(z)`; order each side's own coach pool ascending by a
**coupling score**; give side `s` the pool key at position `floor(u_s * n_s)`.

`u_s` is exactly Uniform(0,1), so `floor(u_s * n_s)` is exactly uniform over the
`n_s` pool keys — the same law as the incumbent `rng.integers(0, n_s, m)`. The
pool is unchanged, the residual vector attached to a key is unchanged, and
**no marginal moves, by construction**. Nothing is clipped, truncated or
renormalised anywhere in this mechanism.

Verified as arithmetic rather than as a sample statistic: over an exactly
uniform grid, `coupled_index` hits every one of 37 pool slots exactly 11 times
(`index_map_uniformity_proof` in the results, and again in the test module).

## 2. The parameter, and where its value comes from

One parameter, `rho`, estimated at forecast time from historical **paired**
games with `ord < ordinal`, never chosen:

```
rho_spearman = Spearman(score_A, score_B) on the symmetrised paired sample
rho          = 2 * sin(pi * rho_spearman / 6)      Gaussian-copula inversion
```

For the selected coupling `off_snaps`, on 2020-2025:

| | value |
|---|---|
| paired historical games in the residual pool | **1,399** (of 1,615 paired games; the rest lack a residual for all five metrics) |
| `rho_spearman` | **-0.476804** |
| `rho` | **-0.494137** |

`nfl/tests/test_v1_game_dependence.py` recomputes both from
`denom_panel.csv.gz` without touching the production path and requires equality
to 1e-9, so the reported parameter is demonstrably read out of the data rather
than typed in.

The `zmean` and `pc1` candidates estimate the same way; `pc1` additionally
estimates its five loadings by eigendecomposition of the residual correlation
matrix over the same pool.

## 3. Chronology

Every pool, residual, z-score, loading and `rho` is computed inside `forecast`
from `hist`, already defined as panel rows with `ord < ordinal`, and production
already refuses a run whose panel reaches the slate
(`TEAM_VOLUME_HISTORY_NOT_STRICTLY_EARLIER`). Evaluation slate 2026 week 1; fit
seasons 2020-2025. **No 2026 outcome is consumed and none exists in the panel.**

## 4. Dependence, before and after

Like-for-like, as §7 of the pre-registration fixed it: **one draw per game, over
the 16 games of the slate, reported as a distribution over 4,000 draws**, with
the historical comparator recomputed on 16-game subsets so a 16-point statistic
is never compared against a 1,615-point one. Per-game predictive means are never
correlated against anything.

Within-game Pearson corr(home, away), mean over draws [5th, 95th]:

| metric | historical (1,615 games) | historical, 16-game band | **before** (A3, per team) | **after** (A3G, `off_snaps`) |
|---|---|---|---|---|
| `team_off_snaps` | **-0.4647** | [-0.758, -0.107] | -0.032 [-0.43, +0.37] | **-0.443** [-0.73, -0.10] |
| `team_carries` | **-0.5347** | [-0.779, -0.213] | -0.036 [-0.44, +0.37] | **-0.103** [-0.49, +0.31] |
| `team_dropbacks_part` | -0.1921 | [-0.574, +0.179] | -0.033 | **-0.181** |
| `team_targets` | -0.1178 | [-0.529, +0.264] | -0.015 | **-0.123** |
| `team_rz_carries` | -0.1870 | [-0.537, +0.189] | -0.021 | **-0.037** |

Mean absolute correlation error across the five metrics: **0.2717 -> 0.1239**.

`team_carries` is the honest weak spot and it was **predeclared as one**: a
single `off_snaps` axis reaches carries only through the within-team-game
correlation between the two residuals, so it recovers about a fifth of the
historical carries coupling. Directionally right, materially better than zero,
not a match. The alternative candidates did not fix it either — `zmean` -0.098,
`pc1` -0.067 — so this is a limit of one shared index per team, not of the score
choice.

## 5. Game totals, before and after

| | historical | **before** | **after** (`off_snaps`) | `zmean` | `pc1` |
|---|---|---|---|---|---|
| SD(total game plays), mean over draws | **9.265** | 12.271 | **9.269** | 9.977 | 11.962 |
| ratio to historical | 1.000 | 1.324 | **1.0004** | 1.077 | 1.291 |
| pooled min / max over 64,000 game-draws | [106, 173] observed | [86, 190] | **[91, 174]** | [94, 178] | [87, 190] |
| **fraction outside [106, 173]** | — | **1.520%** [1.121, 1.905] | **0.188%** [0.111, 0.278] | 0.372% | 1.245% |

Intervals are game-clustered bootstraps over the 16 games, never naive.

The impossible-game-total behaviour is reduced **eight-fold**, and the spread of
total game plays lands on the historical value to four decimal places without
anything being fitted to it — `rho` was estimated from a rank correlation, not
from the total-plays SD.

## 6. Marginals, before and after

Preserved by construction (§1). Three independent checks:

1. **Identical drawn support.** For every metric, the set of distinct values a
   team draws is identical under both modes — e.g. `NE|team_dropbacks_part`
   yields the same 81 distinct values. A mode that reweighted, clipped or
   renormalised could not pass this.
2. **Summary statistics.** Slate means, before -> after:
   `team_off_snaps` 64.67 -> 64.68, `team_dropbacks_part` 33.70 -> 33.67,
   `team_targets` 30.08 -> 30.05, `team_carries` 28.03 -> 28.06,
   `team_rz_carries` 5.12 -> 5.16. Full per-team mean/sd/p05/p50/p95 tables for
   all four arms are in `a3g_results.json` under `marginals`.
3. **Noise-referenced test** (`a3g_marginal_noise.json`): across six seeds per
   arm, the arm difference in each of 160 team-metric cells x five statistics,
   standardised by seed-to-seed SE. Share exceeding |z| = 2: mean 5.6%, sd 9.4%,
   p05 0.6%, p50 3.8%, p95 5.0% — inside what a six-seed SE produces by chance,
   whose reference is t-like with P(|t| > 2) around 7-10%.

## 7. What disagrees with the pre-registration

**The pre-registered verdict is that NO candidate cleared and the incumbent is
retained.** That is what `a3g_results.json` records and it is not being
rewritten.

`off_snaps` cleared clauses 1-4 and failed clauses 5 and 6 — the two clauses
that were meant to be free passes, because §3 proves the marginal cannot move.
Both clauses are defective as written, and the demonstration is that **the
incumbent fails both of them against itself**: clause 5 in 15 of 15 seed pairs
(worst relative move 5.49e8, on a `p05` of `team_rz_carries` sitting at
essentially zero — an unbounded relative move on a near-zero denominator), and
clause 6 in 6 of 15 seed pairs, with the two arms' zero-floor counts differing
by 16.8 against a seed-noise SE of 17.8.

`predeclaration_a3g_addendum_01.md` states corrected clauses 5' and 6', which
`off_snaps` passes, and an **amended verdict selecting `off_snaps`**. That
amendment was written after seeing the result and **is worth less than a
pre-registered verdict**. It is recorded so the lead can see what the evidence
says, not so the experiment can be reported as having succeeded on its own
terms. It did not.

One predeclared expectation was wrong in an interesting way. `pc1` was expected
to spread the coupling across metrics; instead its loadings are dropbacks
+0.617, targets +0.600, snaps +0.383, carries **-0.275**, red-zone carries
**-0.194**. The first principal component of the residuals is the
pass-versus-run tilt — the *within-team* structure A3 already carries — not a
volume axis, so coupling on it barely moved the game total. **The dominant axis
of within-team variation is not the axis on which two opponents trade with each
other.**

## 8. What is in production, and what is not

`nfl/production/team_volume_v1.py` gains `game_coupling` (default `'none'`) and
`game_pairs`. `game_coupling='none'` is **bit-identical** to the draws that
existed before, in both `joint_residuals` modes, and that is tested to the last
float. `JOINT_RESIDUALS_DEFAULT` is untouched.

Requesting a coupling is a declaration, and every way of getting it wrong is a
named refusal rather than a silent no-op: `GAME_COUPLING_UNKNOWN`,
`GAME_COUPLING_WITHOUT_JOINT_INDEX`, `GAME_COUPLING_WITHOUT_PAIRS`,
`GAME_PAIR_MALFORMED`, `GAME_PAIR_SELF`, `GAME_PAIR_TEAM_NOT_ON_SLATE`,
`GAME_PAIR_TEAM_REPEATED`. Each of the three guards is bypassed in the test
module and the refusal must disappear.

**Changing a default is the lead's decision, not this packet's.** To turn the
mode on, a caller passes `game_pairs=[(away, home)]` and
`game_coupling='off_snaps'` alongside `joint_residuals=True`.

## 9. What would establish this rather than indicate it

A fresh pre-registration with clauses 5' and 6' fixed in advance, on a slate
whose measurement did not inform the rule; and, for `team_carries`, a mechanism
question this experiment does not answer — whether the missing within-game
carries coupling needs a **second** shared axis, which one index per team cannot
provide.
