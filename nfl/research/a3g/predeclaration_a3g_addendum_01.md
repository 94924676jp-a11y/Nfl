# A3G addendum 01 — two defective clauses in the original decision rule

Written **2026-09-09, AFTER `a3g_results.json` was produced and read.**

**This document carries none of the pre-registration's standing.** It is a
post-hoc amendment and is labelled as one everywhere it is used. The original
`predeclaration_a3g.md` is unedited, its sha256 is unchanged, and the verdict it
produced — *no candidate clears; the incumbent `none` is retained* — stands
recorded in `a3g_results.json` exactly as it fell.

---

## 1. What happened

Under the pre-registered rule, `off_snaps` cleared clauses 1, 2, 3 and 4 and
failed 5 and 6:

| clause | as written | `off_snaps` |
|---|---|---|
| 1 | `D` improves by >= 0.05 | **pass** (0.2717 -> 0.1239) |
| 2 | `|R - 1| <= 0.15` | **pass** (R = 1.0004) |
| 3 | outside-range fraction at most halves | **pass** (1.520% -> 0.188%) |
| 4 | every within-game correlation carries the historical sign | **pass** (5/5) |
| 5 | no per-team marginal statistic moves by more than 1% relative | **fail** (max move 1.00) |
| 6 | zero-floor draw count does not exceed the incumbent's | **fail** (1474 vs 1436) |

Both failures are in the two clauses that were supposed to be free passes,
because §3 of the pre-registration proves the marginal is preserved *by
construction*. That is the tell: a clause that rejects a mechanism its own
document proves cannot move a marginal is measuring something else.

## 2. Why each clause is defective, demonstrated rather than asserted

`nfl/research/a3g/run_a3g_marginal_noise.py` re-runs **the incumbent against
itself** under six seeds and applies the same two clauses. Results in
`a3g_marginal_noise.json`.

**Clause 5.** It divides by the incumbent's own value, and the statistic that
decides it is `p05` of `team_rz_carries` — a metric whose fifth percentile sits
at or near zero. A move of a fraction of one red-zone carry is then an unbounded
relative move. Measured: the incumbent fails its own 1% clause against itself in
**15 of 15 seed pairs**, with a worst relative move of **5.49e8** at
`NE|team_rz_carries|p05`. A clause that rejects the incumbent for being itself
cannot be evidence about a candidate.

**Clause 6.** It is a strict inequality between two Monte Carlo realisations of
the same quantity. Zero-floor draw counts for the incumbent across six seeds:
1451, 1409, 1375, 1416, 1450, 1396. For the candidate: 1452, 1411, 1488, 1418,
1405, 1424. The difference of means is **+16.8 against a seed-noise SE of
17.8** — under one SE. Within the incumbent alone, **6 of 15** seed pairs have
the later seed exceeding the earlier one, so the clause rejects the incumbent
against itself roughly forty percent of the time.

Neither of these is a discovery about the model. Both are a defect in how I
wrote the acceptance rule, and the cost of it is that a pre-registered
experiment produced a verdict its own evidence contradicts.

## 3. The corrected clauses

**Clause 5'.** Marginal preservation is judged against the incumbent's own
seed-to-seed noise, not against a fixed relative threshold. For every
(team, metric) and every statistic in {mean, sd, p05, p50, p95}: take the mean
across six seeds under each arm, standardise the arm difference by the
seed-to-seed standard error, and require that the share of cells exceeding
|z| = 2 is no larger than what a six-seed standard error produces by chance.
With five degrees of freedom the reference is t-like, so P(|t| > 2) is roughly
7-10%, not 5%.

Measured share above |z| = 2: mean 5.6%, sd 9.4%, p05 0.6%, p50 3.8%, p95 5.0%,
over 160 team-metric cells each. Worst single cell z = 4.20 out of 800
comparisons. **Clause 5' passes.**

**Clause 6'.** The zero-floor draw count must lie within the incumbent's own
across-seed range, or differ by less than one seed-noise standard error.
Measured: **+16.8 against SE 17.8. Clause 6' passes.**

## 4. Amended verdict, and what it is worth

Under clauses 1, 2, 3, 4, 5' and 6', **`off_snaps` clears every clause and is
the simplest candidate that does**, so the simplest-wins ordering of §8 selects
it.

**This is an amended verdict produced under a rule written after the result was
seen, and it is worth less than a pre-registered one.** It is recorded so that
the lead can see what the evidence says, not so that the experiment can be
reported as having succeeded on its own terms. It did not.

What the amendment does not touch: nothing is promoted, `game_coupling` remains
opt-in with default `'none'`, `JOINT_RESIDUALS_DEFAULT` remains `False`, and the
decision to change any default remains the lead's.

**If this were to be established rather than indicated**, it needs a fresh
pre-registration with the corrected clauses fixed in advance, evaluated on a
slate whose measurement did not inform the rule.

## 5. Also recorded: a predeclared expectation that held, and one that did not

§8 predeclared that S1 (`off_snaps`) would fix `team_off_snaps` and the game
total close to exactly and would under-recover `team_carries`. It did: snaps
-0.443 against a historical -0.4647, carries -0.103 against -0.5347.

§8 predeclared that S3 (`pc1`) would spread the coupling. It did something
else. The first principal component of the five residuals is not a volume axis
at all — its loadings are dropbacks +0.617, targets +0.600, snaps +0.383,
carries **-0.275**, red-zone carries **-0.194**. It is the pass-versus-run tilt,
which is the *within-team* structure A3 already captures, and it loads carries
against snaps. Coupling on it therefore barely moved the game total (R = 1.291,
outside-range fraction 1.245% against the incumbent's 1.520%). That is a real
finding and not a tuning failure: **the dominant axis of within-team variation
is not the axis on which two opponents trade with each other.**
