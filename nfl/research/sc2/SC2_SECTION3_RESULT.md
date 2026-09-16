# SC2 section 3 — the measurement, and what it decides

Run after `predeclaration_sc2.md` was written and before anything was built.
Raw numbers in `SC2_SECTION3_MEASUREMENT.json`. Source: `nfl/research/postgame/
pbp_2021..2025`, REG only, **2,718 team-games**. The predeclaration said
2020-2025; 2020 is not in this checkout, so the frame is 2021-2025 and this
sentence is the correction rather than a silent re-scoping.

| | mean per team-game |
|---|---|
| attempts (`complete + incomplete + interception`) | 33.2399 |
| interceptions | 0.7561 |
| receptions | 21.4790 |
| targets | 31.8135 |

## M3 — the inequality is a law

**Team-games where receptions exceed attempts minus interceptions: 0 of
2,718.** Exactly as predeclared, and the check was there to catch the case
where one of the three quantities is not what the design thinks it is. It is.

## M1 — SC2-B is WITHDRAWN

Predeclared rule: *"SC2-B is admissible only if the model is under-coupled,
i.e. if the permutation moves it toward history rather than away."*

| | corr(interceptions, attempts), team level |
|---|---|
| history, 2,718 team-games | **+0.2159** Pearson, +0.1982 Spearman |
| model, sealed 8,000-draw board, pooled | **+0.1973** |
| model, BUF | +0.2143 |
| model, DET | +0.1938 |

The model is at the historical coupling, not beneath it. SC1's defence — model
+0.0299 against history +0.1802, so the permutation moved a badly
under-coupled pair toward the truth — **does not transfer**. Permuting the
interception draw index here would destroy a dependence the model already has
about right, to fix an event that occurs in roughly 4 draws in 10,000.

SC2-B is withdrawn on the rule that was written before the number was seen.

## M2 — SC2-A is the construction, and the rate is measured, not chosen

| catch rate denominator | value |
|---|---|
| targets | 0.675155 |
| targets minus interceptions | 0.691591 |
| difference | **+1.6436 pp** |

Interceptions are **2.3766%** of targets.

This is exactly the objection the predeclaration raised against itself.
Re-basing RC1's conversion to a picks-removed denominator **while keeping the
old rate** would cut receptions by about 2.4% — roughly 0.51 receptions per
team-game — and that is a level change wearing a coherence fix's clothes.

With the rate re-estimated on the denominator it is actually applied to,
`0.691591` against the reduced pool reproduces the same expected receptions as
`0.675155` against the full one, by construction: `21.479 = 0.675155 x 31.8135
= 0.691591 x (31.8135 - 0.7561)`. **No free parameter is introduced.** The
rate is a measurement on 2,718 team-games, not a tuning knob, and the pair of
numbers above is what makes that checkable.

## The decision

**SC2-A, with the conversion rate re-estimated on the reduced denominator.**
It is also the construction `credit_passing_line`'s own refusal text names:
*"an SC1-style coupling that reserves intercepted throws out of the targeted
budget."*

What still has to be shown, and is NOT shown here:

- the violation rate falls to **exactly zero** on a 50,000-draw DET-BUF run;
- team receptions, team receiving yards and every receiver's mean targets move
  by no more than Monte Carlo error, **checked** rather than assumed;
- `published team targets == the consumed throw-process target budget`, per
  draw, both teams, keeps holding.

Those are section 4's acceptance conditions and they are unmet until SC2-A is
built and run. It will take its own candidate identity and will be
REHEARSAL_ONLY.

V2 NOT YET EARNED.
