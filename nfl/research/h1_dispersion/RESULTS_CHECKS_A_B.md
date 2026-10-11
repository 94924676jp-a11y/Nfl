# H1 results after pre-registration `011fb4c5` (checks A and B; the confirmatory test has not happened yet)

Rules: `PREREG_H1_DISPERSION.md`, section 5. Check A can only refute. Check B is descriptive. The confirmatory
verdict needs at least 6 graded prospective weeks, 2026 week 6 onward, in shadow.

## Check A: forward chain 2022-2023, production arm, computed once after the freeze

28 weeks, 16,568 pool player-weeks, 5,207 of whom played. Raw rows: `CHECKA_2022_2023_rows.csv.gz`; output:
`CHECKA_RESULT.json`.

| measure | production | candidate | rule | result |
|---|---|---|---|---|
| top-quartile ratio, players who played | **1.315 [1.282, 1.363]**, n = 1,680 | 1.023 (fitted weeks) | H1 is refuted if the interval contains 1.00 | **not refuted** |
| top-quartile MAE, paired by week | | **-1.506 [-1.768, -1.243] pts per player** | interval excludes zero | pass |
| overall MAE, paired by week | 6.616 | 6.135, diff -0.487 [-0.571, -0.402] | upper end <= 0 | pass |
| position MAE change | | QB -1.6 %, RB -4.4 %, WR -9.8 %, TE -10.3 % | none worse than +1 % | pass |
| projection-decile MAE change | | deciles 1-6: 0.0; deciles 7-10: -3.2, -9.2, -13.4, -26.8 % | none worse than +2 % | pass |

**The defect is larger in 2022-2023 (1.32) than in development (1.14).** One plausible reason is that the
multi-season prior there rests on fewer seasons. That is a hypothesis, not a measurement.

**Check A is not clean data.** These seasons were read by earlier studies, so check A does not confirm anything.
It failed to refute H1, and the candidate passed every predeclared harm test on it.

## Check B: archived pre-kickoff production projections, 2026 (descriptive)

Development-fitted factors, end of 2025: QB 0.991, RB 0.885, WR 0.844, TE 0.848.

| slate | status | top-quartile n | production ratio | candidate ratio | MAE production -> candidate |
|---|---|---|---|---|---|
| week-4 early Classic | seen in development | 48 | **1.105** (TE 1.444, RB 1.113, WR 1.017, QB 1.035) | 0.992 | 8.49 -> 8.16 |
| ATL@NO showdown | seen | 8 | **0.975** | 0.888 | 5.25 -> 4.66 |
| TB@DAL showdown | the clean slate | 13 | **0.991** | 0.890 | 7.63 -> 7.18 |

**Production is not obviously over-projected at the top on the two showdown slates.** On them the candidate would
push the level to 0.89. The live engine has inputs the research chain lacks (market totals, injury information,
appearance), so the harness's defect may be partly or wholly absent in production.

That is exactly why the confirmatory test is prospective, on production's own locked projections, and not on the
harness.
