# PM-3 pre-registration: PM-1's P(no participation) and a role-band participation factor

- **Written:** 2026-10-11 at about 19:27 UTC, after PM-2 was voided (`PM2_RESULT.md`). The commit time is
  authoritative.
- **Status:** PRE-REGISTERED, SHADOW ONLY. It feeds the corrected forecast arm, which runs beside the incumbent
  (owner decision E2).

## Components (frozen)

1. **P(no participation)** is PM-1's frozen table (`PM1_TABLE.json`), unchanged. It is used **only while game-day
   status is unresolved**. Its evidence is PM-1's held-out verdict. Its known limitation, role mixing, is printed
   wherever it is used.
2. **Game-day status.** A player the evidence resolves ACTIVE gets P(no participation) = 0. This is a declared,
   untestable-here assumption; see PM-2 section 2.
3. **Participation factor φ** for players who play, in PM-2's role-band strata. It reuses PM-2's fitted r/r0
   quantiles and controls, from the fit seasons only.
   - **Interior grid.** Ratios are computed only for u from 0.05 to 0.95. Levels outside that range take the
     nearest interior value.
   - **Monotone.** The interior ratios q_designated(u) / q_control(u) are made non-decreasing by pool-adjacent-
     violators (isotonic least squares, equal weights).
   - **Clipped** to [0, 1].
   - **Cell choice.** The deepest PM-2 cell with n ≥ 30 that has a φ. Otherwise its parent, with the same drop
     order as PM-2.

## Evaluation

| check | when | bar |
|---|---|---|
| **Primary** | prospective, 2026 weeks 6-11, once nflverse publishes 2026 participation (after the season) | CRPS of r/r0 for designated players who played, PM-3 against the point mass at 1, club-week cluster bootstrap B = 4,000, seed 20261011; lower 95% bound > 0 |
| **In-season proxy** | weeks 6-11 | PM-2's: P(no participation) against captured official inactive lists |

**No REUSED 2024-2025 score is claimed for PM-3.**

## Voids

- Any change to the components above after this commit.
- Any use of a 2026 week-6-or-later outcome.
