# P2 pre-declaration — written before any P2 result was computed

Written 2026-09-07 after the data audit in §0 and before Stage A was fitted.
Departures from this are labelled where they occur; the original text stays.

## 0. Data facts established before any modelling

- `injuries` carries `date_modified` for 2020–2024 at 100% non-null, and
  **not at all in 2025**.
- Of 27,617 REG injury rows 2020–2024 with a matched kickoff, **27,583
  (99.88%) have `date_modified` strictly before kickoff**; 17 are after and 17
  have no kickoff match.
- `depth_charts` changes schema in 2025 (daily `dt` snapshots, `pos_rank`)
  versus weekly `depth_team`/`depth_position` in 2020–2024.

**Consequences fixed now, not after seeing results.** Injury features are used
only for rows whose own `date_modified` is strictly before that game's kickoff.
2025 therefore carries no injury feature at all, and every Stage A result is
reported twice — with and without injuries — so the cost of that exclusion is
visible rather than absorbed.

## 1. Stage A targets and thresholds

`appeared` is the primary target: at least one offensive snap. Sensitivity is
reported at snap-share thresholds 0.00 (any snap), 0.10, 0.25, 0.50 rather than
one threshold being chosen and the rest suppressed.

Population: the pregame candidate set — every player who appeared for that team
in any of the previous 4 team-games. This is knowable before kickoff and does
not use `weekly_rosters.status`.

## 2. Stage A models

base rate · previous-game appearance · trailing-3 and trailing-5 appearance
rate · EWMA appearance rate (half-life 3) · logistic regression on pregame
features · the same logistic plus injury designation.

Scored by Brier, log loss, AUC and a 10-bin calibration table. A model that
improves Brier while worsening calibration is reported as such.

## 3. Combination

Estimand declared now: **expected unconditional share**,
`E[Y] = P(appear) · E[Y | appear]`, with the forecast distribution understood
as a mixture — point mass `1 − P(appear)` at zero plus the conditional
distribution. Shares are bounded in [0,1] and the product of a probability and a
conditional share is itself a valid share, so the multiplication is coherent
here; that is asserted because the directive requires it to be checked rather
than assumed.

Three models compared on the SAME population (all candidate player-games):
U = unconditional forecast; C = conditional forecast applied to everyone;
A×C = mixture.

## 4. Acceptance rule, declared before results

P2 is accepted only if A×C beats the P1 incumbent on the same population, on a
majority of evaluation seasons, with a player-block-bootstrap interval excluding
zero — **and** the improvement is not confined to the easy cohort. If pooled
metrics improve while role-change weeks do not, the finding is reported as
"improves the easy cases only" in those words.

## 5. Role change

The label stays P1's: `|snap_share(t−1) − mean snap_share(t−2..t−4)| > 0.20`.
Stage A's question is whether role change is predictable *pregame*; false
positives and false negatives are both reported, with the base rate.

## 6. Bootstrap

Player-block bootstrap, 400 resamples, seed 20260907. **Deviation from P1
declared here:** P1 used 1,000. 400 is a computational choice made to fit the
run budget, taken before seeing any P2 result, and it widens intervals slightly
rather than narrowing them.
