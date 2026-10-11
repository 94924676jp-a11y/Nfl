# PM-2 pre-registration: PM-1 with the player's role, and a participation factor the simulator can use

- **Written:** 2026-10-11 at about 19:30 UTC, after PM-1's verdict and after exploratory reads of the fit seasons only
  (`PM1_RESULT.md`). The commit time is authoritative.
- **Status:** PRE-REGISTERED, SHADOW ONLY. Its table is what the corrected forecast arm consumes. Under owner decision
  E2 that arm runs beside the incumbent from week 6, the owner chooses which file to upload, and promotion follows
  only if this protocol's bars pass prospectively.

## 1. What changes from PM-1, and why

PM-1 is not edited; it stands as registered. PM-2 changes three things:

1. **Role band as the first stratum.** The player's baseline share of offensive plays, r0, as defined in PM-1:
   ≥ 0.70, 0.40-0.70, < 0.40, or NO_BASELINE.
   - *Why:* PM-1's P(no participation) mixes role. Questionable WR/TE starters recorded no play 22.3% of the time,
     against the 36.1% of McLaurin's PM-1 cell (fit seasons, exploratory).
2. **Pooling order.** Drop injury class, then practice status, then position, then role. Otherwise PM-1's rule:
   n < 30 shrinks toward the parent, prior 20 pseudo-observations, sensitivity at 5 and 80.
3. **Participation factor φ for the simulator,** in every cell:
   - φ(u) = q_designated(u) / q_control(u) on PM-1's 101-point grid, clipped to [0, 1];
   - then made non-decreasing in u by a running maximum, so φ is a valid quantile function;
   - q_control is the undesignated player-games of the same position group and role band in the fit seasons
     (`PM1_CONTROL`, by band).
   - *Why:* the simulator already draws ordinary share dispersion, so the designated distribution cannot be used
     as-is.
   - For starters it is monotone and small (exploratory: p10 0.69, p50 0.94).

## 2. Game-day status, stated and not solved

- The data cannot tell "ruled inactive" from "active, zero snaps".
- PM-2's P(no participation) is therefore the probability **before game-day status is known**.
- When the evidence resolves a player ACTIVE, the arm uses P(no participation) = 0 and φ from the played
  distribution.
  - This is a declared assumption. It is untestable here.
  - It is printed in every artifact that uses it.
  - Testing it needs historical weekly rosters. That is a new acquisition, which the owner has not approved.

## 3. Data roles

| role | seasons | status |
|---|---|---|
| fit | 2016-2023 | read for PM-1, and exploratory reads for this design |
| **REUSED** check | 2024-2025 | read once in aggregate, for PM-1's bars. Any score here is labelled REUSED and cannot pass PM-2 alone |
| **primary, prospective** | 2026 weeks 6-11 | untouched. Requires that weekly 2026 participation data be published, which nflverse does after the season. **The prospective verdict is therefore available only after the 2026 season.** It is stated now so nobody reads a REUSED score as a confirmation. |

Because of that last row, PM-2 also carries an **in-season proxy check**: weeks 6-11, P(no participation) for
designated players against the official game-day inactive lists the slate pipeline already captures.

- **Outcome for the proxy check:** inactive = 1.
- **Scope:** QUESTIONABLE and DOUBTFUL players not yet resolved.
- **Bar:** Brier improvement over 0, with a lower 95% bound > 0, clustered by club-week. A sample floor of
  100 designated player-weeks applies; below it the result is NOT_YET_EVALUABLE.

## 4. Endpoints

PM-1's H-a, H-b and H-c apply, with the same bars, computed per role band and pooled, with the same bootstrap.
REUSED 2024-2025 scores are reported, never decisive.

## 5. What voids this

- Changing the strata, pooling, φ construction or bars after this commit.
- Using any 2026 week-6-or-later outcome in the table.
- A changed protocol becomes PM-3.
