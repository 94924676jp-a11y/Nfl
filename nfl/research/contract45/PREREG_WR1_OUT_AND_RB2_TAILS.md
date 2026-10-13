# Pre-registration: where an absent WR1's volume goes, and backup-RB upper tails (2021-2025 history)

- **Written:** 2026-10-13, before any number below was computed. The commit time is authoritative.
- **Why now.** The BUF@LAR postmortem raised two hypotheses: Moore's share went to the run game rather than the pass
  catchers, and backup RB tails are too thin. **One game establishes neither.** This tests both on history the W5
  outcome never touched.
- **Status:** research. No production change follows. A failed result stays failed.

## Data, point in time

| source | sha256 | role |
|---|---|---|
| `nfl/warehouse/PLAYER_GAME.json` | recorded in the result | per player-game opportunity rows, 2021-2025; a player with no opportunity has **no row** |
| local nflverse injury captures `hist_injuries_2021..2025` | recorded in the result | the final game status for that week; already on disk, no new acquisition, not published |

Every pre-game quantity is **season-to-date through the previous week only**. Nothing from the game itself or later
enters a prediction.

## H1. The WR1-out redistribution

**Case.** A regular-season team-game where both of these hold:

- The team's season-to-date target leader is a WR with at least 3 prior games played and at least 20% of team targets
  in those games.
- That player has final game status **Out** for that week, and no opportunity row in that game.

**Baseline.** The same team and season, games where the leader played, before the case week.

**The rule under test: proportional.** This is the engine's absent-player rule in its simplest form. Each remaining
player's predicted share of team targets is his season-to-date share divided by (1 − the leader's share).

**Measured per case**, each the actual minus the proportional prediction, aggregated **by position group (WR / TE / RB)**:

- target share of the remaining WRs, TEs and RBs;
- the team's pass attempts and rush attempts against the baseline mean;
- RB carries share.

**Uncertainty.** 95% intervals with resampling **clustered by team-season**. Cases from one team-season are not
independent.

**Pre-declared reading.**

- If the RB group's actual share exceeds the proportional prediction with a clustered interval excluding 0, the
  proportional rule **under-allocates to backs** when a WR1 is out.
- If the TE or WR group's interval excludes 0 on the other side, it **over-allocates to them**.
- Otherwise: **no detectable bias**, and the Moore case is not evidence of a systematic rule error.

## H2. Backup-RB upper tails

**Population.** RB2 by season-to-date carries rank, at least 3 prior games, in games where the RB1 played. Stratified
by whether the club's RB3 was Out (the Rivers / Corum situation).

**Measured.** The empirical distribution of RB2 DK points (p50, p90, p95, p99), and the share of RB2 games scoring at
least 3 × the player's own season-to-date mean.

**Reading.** Descriptive. It is the reference distribution that the engine's simulated RB2 tails must be checked
against on frozen slates. That comparison (simulated against empirical tail quantiles) is the follow-up and is reported
separately, never tuned on W5.

## Not allowed

- No coefficient from this study enters production without its own registered change and an out-of-sample check on
  week 6 or later.
- W5 BUF@LAR is excluded from both populations (2026 is not in the history range).
