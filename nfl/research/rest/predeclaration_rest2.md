# REST2 pre-registration — the interaction candidate

**Written before REST2 is built or scored.** Fix B is withdrawn and its result
(`REST_FIXB_WITHDRAWN.md`) is preserved unchanged. Nothing below was chosen
after seeing a REST2 number, because no REST2 number exists yet.

REST2 is a **successor identity**, not a modification of R8. `appearance_r8`'s
`featurise` / `fit` / `predict` stay byte-identical and are still what R8 and R9
serve.

---

## 1. The hypothesis, stated so it can be false

Fix B tested *"a row following the last regular-season game is different"* and
that is **false**: coefficient −0.15 to −0.22 with |z| < 1 on up to 48,298 rows,
and the SAT-vs-PLAYED differential moved from −0.071535 to −0.073363, away from
zero, CI [−0.002321, −0.001390].

It failed for a structural reason, not a numerical one. A **main effect** gives
every player who crossed that boundary the same nudge, whether he sat or
played, so it cannot move a gap **between** those two groups.

> **REST2's hypothesis:** the early-next-season distortion depends on the
> INTERACTION of the boundary with **how much the player participated in that
> final game** — not on the boundary alone.

If that is also false, the rest-state limitation is accepted as unresolved.

## 2. Exact interaction terms — three columns, no thresholds

All three are products of quantities **already on the training frame**.
`L` is the flag from fix B (previous frame row is the final regular-season week
of its own season, read from the frame, never hardcoded as 17 or 18).
`prev_appeared` is already an R8 input. `prev_snap` is the `snap` field of that
same previous row — the identical quantity `snap_ewma_cur` is built from, read
directly instead of aggregated.

| # | column | definition |
|---|---|---|
| 1 | `L` | the fix-B main effect, retained so the interaction is identified against it |
| 2 | `L × prev_appeared` | `L` times 1 if he appeared in that game, else 0 |
| 3 | `L × prev_snap` | `L` times his snap share in that game, **continuous in [0,1]**, 0 when missing |
| 4 | `L × prev_snap_is_missing` | the missingness companion, because a chart-added row has no snap and that is not a zero |

Four columns. **`k = 4`.**

**There is no threshold anywhere.** No rank cut, no 0.50, no 0.10, no player
list. The continuous `prev_snap` is precisely what makes the Allen/Cook cuts
unnecessary: the fit estimates what participation in that game is worth instead
of being told.

## 3. Exact eligible population

**The fit trains on every frame row R8 trains on** — seasons strictly earlier
than the evaluation season, minus the identical `is_unsupported` exclusion,
identical `l2 = 1.0`, identical reliability `k` handed to both arms. The four
columns are zero for every row where `L = 0`, so no row is added, removed or
reweighted relative to R8.

**No population restriction to "established starters" is applied to the fit.**
Defining that requires the very thresholds this candidate exists to avoid.

## 4. Exact forward-chained evaluation

Trained on seasons strictly earlier than the evaluation season; scored on that
season. **Evaluation seasons 2022, 2023, 2024, 2025** — the same four as fix B
and as R8's own evidence. Identical rows in both arms.

## 5. Exact SAT / PLAYED comparison

The measurement signature is **unchanged from `predeclaration_rest.md` and is
not touched**: listed rank 1–3 in the last regular week, appeared with snap
≥ 0.50 in each of the three prior weeks, then either did not appear or took
≤ 10% of snaps.

Its thresholds are post-hoc — I chose them while looking at Allen and Cook —
and that is tolerable **only** because it defines the evaluation subgroup and
**REST2 never sees it**. Changing it now to suit REST2 would make it a tuning
knob, so it is frozen at the values fix B was judged on: pooled weeks 1–4,
2022–2025, **n_SAT = 292, n_PLAYED = 1,994**.

## 6. Coefficient reporting

All four coefficients with observed-information standard errors and z, **per
evaluation season, whatever their signs**, including any indistinguishable from
zero. Reported before the gate verdicts, not after.

## 7. Gates — all must pass

**PRIMARY**

**G1.** The SAT-vs-PLAYED differential moves **materially** toward zero:
`|differential_REST2| ≤ 0.5 × |differential_R8|` — at least **half** of the
−0.071535 gap closed, so `|new| ≤ 0.035768` — **and** the team-blocked 95% CI
on the *change* excludes zero **in the correct direction**. 4,000 resamples,
blocked by `(season, team)`, same seed.

*The 50% is a judgement about materiality and is stated as one. It is set here
because a fix that closes a tenth of a declared defect is not worth a mechanism
change.*

**SECONDARY — all four**

**G2.** Weeks 1–4 Brier not worse: the CI on ΔBrier must not sit entirely above
zero.
**G3.** Weeks 5–18 Brier not worse, same rule.
**G4.** **No degradation in the non-SAT established-starter population.** The
PLAYED gap `|+0.028721|` must not grow, with its own blocked CI not sitting
entirely in the worsening direction.
**G5.** All four coefficients reported with SEs.

**COMPLEXITY PENALTY — G6**

Four columns must earn their place. On the weeks 1–4 evaluation rows
(**n = 11,484**), require the per-row log-loss improvement to clear the BIC
bar:

    mean_ll(R8) − mean_ll(REST2)  ≥  k·ln(n) / (2n)  =  4 × 9.3487 / 22,968
                                                     =  0.001628

For reference and as a sanity check on the bar: **fix B achieved 0.000579** and
would have failed it. The bar is computed from `k` and `n` alone — it is
arithmetic, not a chosen number.

## 8. Withdrawal rule

**If any of G1–G6 fails, REST2 is withdrawn**, R8 stands unchanged, and the
rest-state limitation is **accepted as unresolved and quantified** at
**−0.0715** in weeks 1–4, carried forward as a declared limitation on the
board. That is an acceptable terminal outcome and it is written here so it
cannot be renegotiated once a table exists.

**No third fix will be invented in the same pass.** If REST2 fails, the next
hypothesis needs its own pre-registration and the owner's instruction to run it.

## 9. What would make REST2 wrong

- **n is small where it matters.** 292 SAT rows. The interaction is estimated
  from ~2,152 flagged training rows of which only a fraction are sits.
- **`L` is near-collinear with `crossed`**, which R8 already carries. That
  limited fix B to |z| < 1 and will limit the main effect here too; the
  interaction terms are the ones that must carry any signal.
- **"SAT" conflates causes** — rest, an unreported knock, a benching are one
  row. Nothing available pregame separates them.
- **The evaluation frame is the one every earlier repair was selected on**, so
  this is **EXPLORATORY**. Forward chaining controls parameter leakage and says
  nothing about specification leakage.

V2 NOT YET EARNED.
