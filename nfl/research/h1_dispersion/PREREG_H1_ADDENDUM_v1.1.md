# H1 pre-registration, addendum v1.1: how the frozen rule runs prospectively

Written **2026-10-11 ~03:40 UTC, before any 2026 week-6 Sunday game.** It changes nothing in v1.0 (`011fb4c5`):
- not the hypothesis;
- not the candidate formula;
- not the metrics;
- not the decision rules.

It states, before any prospective data exists, the operational choices v1.0 left open. Any alternative decision
criterion (for example a non-inferiority version of the no-group-worse rule) would be a separately versioned
protocol (v2) applied only to data collected after it is committed. It would never re-judge data this version
already covers.

## O1. Where the correction factor c comes from prospectively

v1.0 fits c on strictly earlier weeks, with a minimum of 8. Production has fewer than 8 graded weeks, so read
literally the candidate would do nothing in production for weeks.

**Operational choice:** prospectively, c is taken from the research chain, fitted on **every earlier chain week**,
which is 2022-2025: 56 weeks of top-quartile players who played.

- Values: **QB 0.9517, RB 0.8440, WR 0.7771, TE 0.7652**, capped at 1.
- It is recomputed only when new chain weeks are graded, and always from weeks strictly before the slate.

## O2. Two prospective streams, never pooled

| stream | incumbent | candidate | sealed |
|---|---|---|---|
| **P-chain** | research chain, production arm, data through 2026 week 4 | the same rows with O1's c | `PROSPECTIVE_2026W5W6_SEAL.csv`, sha256 `e099bc4bd9ef39dbc1d4d9cfb308135626af9519e58ba8b82cae73fe877a0619`, 862 rows (431 per week) |
| **P-prod** | production's own **locked pre-kickoff** projection file for each 2026 slate | that file with O1's c applied to each position's top quartile | each slate's shadow file, hashed and committed **before its lock** |

## O3. What counts as prospective

- **Week 5 (P-chain) is pseudo-prospective.** Its games have been played, but no week-5 data is in the inputs. It is
  graded and reported separately from week 6.
- **Week 6 is prospective only for games that kick off after this commit's push time.** Any game that started earlier
  (Thursday 2026-10-08) is excluded, using the kickoff time in the graded data source.
- Week 5 and week 6 projections are identical (inputs end at week 4). Each week is still graded against its own
  outcomes. A bye-week player counts as not playing.

## O4. Grading

- **Actuals:** DK points from the repository's own actuals path once the week's data is captured.
- **Reported as in v1.0:** played-only first; the unconditional view separately.
- **Counting:** the v1.0 confirmatory verdict needs at least 6 graded prospective weeks.
  - P-chain weeks count only for the research chain.
  - The production verdict comes from P-prod.

## O5. Out of scope for this protocol

**H-TAIL, AP-1 and RC-1 are not merged into H1 and their rules are untouched.** Should any of them be promoted
during the H1 window, its effect on production's top-quartile level is recorded beside each P-prod slate.
