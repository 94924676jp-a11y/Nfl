# Amendment A1 to the OAS1 Week-2 pre-registration

**Declared before any Week-2 fit. The pre-registration itself is not
rewritten — this document and `WEEK2_PREREG_AMENDMENT_A1.json` are additive,
and `preregistration.py` keeps both grids on disk exactly as declared.**

## The blocker

`WEEK2_FIT_CONFIG.json` carries `half_life` and `min_plays` in the search
space. The pre-registration declares **no mechanism by which either enters the
Week-2 objective**. The runner refused rather than fit, which was right:
running would have selected over axes that cannot change a score, and
afterwards nobody could have said which reading of them had been assumed.

## `min_plays` — reporting only, so it cannot move a score

The pre-registration's only statement about it is `MIN_SAMPLE_RULES`, a
**reporting** rule: a unit with fewer than `min_plays` current-season plays is
reported with `n_plays_current_season` and `prior_weight_effective` attached.
Reporting does not enter the inner-fold objective, so all three grid values —
0, 20, 50 — give an identical score at every configuration.

**Resolution:** removed from the search space; **retained as a reporting
parameter fixed at 0**, so every unit is reported with its play count
attached. It is not deleted from the model, only from the search.

## `half_life` — two readings, and the pre-registration picks neither

| reading | status |
|---|---|
| (i) decay **within the current season** | **exactly degenerate at week 2** |
| (ii) decay over **all training games**, prior season included | not degenerate, but it double-parameterises `rho` and `kappa`, and borrows B3's `games_back` formula |

**(i) is degenerate, and this was measured rather than argued.** The Week-2
training set carries exactly **one** current-season ordinal — 202601, 1,888
plays — so every current-season play is zero games back and
`0.5 ** (0 / h) = 1` for all five values of `h`. The five grid points produce
identical designs.

**(ii) is not available.** The prior already enters as weighted
pseudo-observations with response `rho * theta_prev[u]` and weight `kappa`;
that *is* the prior-versus-current trade-off. A decay across all training
games would parameterise the same quantity a second time. It would also be
borrowing B3's `games_back` formula, which the owner ruled may not be borrowed
without independent justification, and there is none.

Choosing between (i) and (ii) **after** seeing which fits better is exactly
what a pre-registration exists to prevent.

**Resolution:** removed from the Week-2 search space. Reinstatement requires a
further amendment declaring its **scope**, written before any fit whose
training set carries two or more current-season weeks. The runner enforces
this: preflight check `amendment_a1_degeneracy_still_holds` fails the moment a
second current-season ordinal appears.

## What changes, in numbers

| | declared | after A1 |
|---|---:|---:|
| search axes | 6 | 4 |
| configurations | 12,960 | **864** |
| tie-break keys | 5 | 3 |

**The 15× is not a compute saving, it is a selection problem.** Fifteen exact
copies of every distinct configuration means "within one standard error of the
best mean score" was a tie-break among duplicates, and the most-shrunken rule
would have been resolving those ties on `max half_life` and `max min_plays` —
two axes that do nothing.

Amended tie-break order: **max lambda, max kappa, min rho**. The surviving
keys keep their declared order; nothing is reordered.

## What an amendment may not do

Add a search value. Widen a grid. Move a threshold. Change a comparator. Alter
a promotion rule. Be written after a Week-2 fit has been run.
`amendment.validate()` enforces the first two against the frozen
pre-registration and `test_oas1_amendment_a1.py::test_E` proves both refusals
fire.

## Status after this amendment

`WEEK2_OAS1_FIT_SPEC_READY` = **YES**
`WEEK2_OAS1_PREFLIGHT_READY` = **YES** — 15 checks pass
`WEEK2_OAS1_FIT_EXECUTABLE` = **NO** — the fitting body is still not written
`WEEK2_OAS1_DOWNSTREAM_LAWFUL` = **NO** — both OAS1 ids are `RESEARCH_ONLY`

Nothing was fitted. `OAS1_BASELINE_CHAIN.json` still carries
`candidate_fitted: false` and no `OAS1_WEEK2_RESULT.json` exists.

**V2 NOT YET EARNED**
