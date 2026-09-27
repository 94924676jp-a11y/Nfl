# Why today's 9-game slate produces no board — traced, and it is not `feature_build`

Established 2026-09-27 by running the production path on `2026_03_CIN_PIT` and
reading its stage table, not by reading the work queue's description of it.

## The headline: the reported blocker is a mislabel

`refresh_boards.py` prints

    2026_03_CIN_PIT    REFUSED  feature_build: STAGE_DECLARED_UNIMPLEMENTED

and that string has been carried into `SYSTEM_STATE.json`'s work-queue item 14,
into my own summaries, and into the brief for today's work. **It names a
bystander.**

`nfl/product/orchestrator.py` labels the refusal with *the first stage whose
state is not `PASS` or `NOT_APPLICABLE`*. `DEFERRED` satisfies that, so
`feature_build` is reported. The same summary's own `first_failure` field says
something else, and it is right.

**`feature_build`'s DEFERRED does not halt anything.** `pipeline.py:284` halts
only on `FAIL` or `BLOCKED`. The run proceeds past it.

## The actual stage table for today's game

| stage | state | code |
|---|---|---|
| capture_validation | PASS | INPUTS_VALIDATED |
| identity_resolution | PASS | IDENTITY_RESOLVED |
| feature_build | DEFERRED | STAGE_DECLARED_UNIMPLEMENTED |
| team_environment | PASS | TEAM_ENVIRONMENT_OK |
| appearance | NOT_APPLICABLE | SLATE_FITS_UNAVAILABLE |
| participation | NOT_APPLICABLE | SLATE_FITS_UNAVAILABLE |
| targets_carries | NOT_APPLICABLE | SLATE_FITS_UNAVAILABLE |
| conversion | NOT_APPLICABLE | SLATE_FITS_UNAVAILABLE |
| td_layer | NOT_APPLICABLE | SLATE_FITS_UNAVAILABLE |
| **qb_layer** | **PASS** | **QB_LAYER_OK** |
| joint_reconciliation | PASS | JOINT_RECONCILED |
| **player_draws** | **FAIL** | **DECLARED_DRAW_ARTIFACT_INCOMPLETE** |
| scoring | NOT_APPLICABLE | STAGE_NOT_REACHED |
| artifact_sealing | NOT_APPLICABLE | STAGE_NOT_REACHED |

`first_failure: player_draws FAIL DECLARED_DRAW_ARTIFACT_INCOMPLETE`.

**The QB layer passes for today's games.** So does capture validation, identity
resolution, team environment and joint reconciliation.

## The chain, each link measured

1. **No board** ← `player_draws` FAIL: *2 contract offence(s) against
   player_draws (nfl-player-draws-contract-1) at scope `'football'`:
   CONTRACT_DECLARED_LAYER_ABSENT*.
2. **Which two layers** ← `contracts/registry.py` declares `receiving` and
   `rushing` `required=True`, each with
   `zero_rows_legal_when='NEVER. Every NFL game is played by …'`. `qb` is the
   third required layer at this scope and it is present. (`dk_scoring` is
   `required=True` but scoped `dfs_product`, so it is not one of these two.)
3. **Why they are absent** ← the five non-QB stages returned `NOT_APPLICABLE`
   with `SLATE_FITS_UNAVAILABLE`. By design a non-QB layer that cannot run does
   not refuse the game — it is a completeness dimension — so nothing halted, and
   the absence surfaced only at the draw contract.
4. **Why the fits are unavailable** ←
   `appearance: participation_prior returned BLOCKED[PARTICIPATION_HISTORY_STALE]:
   the newest participation history is ordinal 202518 and the forecast is 2026
   week 3. ewma_hl2 weights the most recent games hardest…`
   Ordinal 202518 is **2025 week 18**.
5. **Root cause** ← `nfl/production/nonqb/panel_2026w1.py` names it outright:
   *"The named missing input is `pbp_participation_2026`, which has never been
   captured."*

## What genuinely exists, and the one thing that does not

A field-by-field audit already in the tree found **exactly one** non-derivable
field, not a missing dataset:

| panel field | source | status |
|---|---|---|
| season, week | pbp_2026 / snap_counts_2026 | EXACT |
| gsis_id | roster pfr_id → gsis_id | EXACT |
| position | weekly_rosters | EXACT |
| team_dropbacks_part | pbp qb_dropback per team-game | EXACT |
| offense_pct (appeared) | snap_counts_2026 | EXACT |
| targets | pbp receiver_player_id | EXACT |
| carries | pbp rusher_player_id | EXACT |
| **pass_snaps** | needs per-play on-field presence | **MISSING** |

I confirmed the 2026 snap evidence is on disk and non-empty:
`nfl/availability_raw/snap_counts_2026.271167b454534d6e.csv.gz` holds **1,492
rows for 2026 week 1 and 93 rows for week 2**. `offense_players`,
`offense_personnel`, `defense_players` and `n_offense` are absent from the
play-by-play, so per-play presence exists **only** in `pbp_participation`.

## So the work is a re-probe and a revived watch — corrected

**First framing, and it was wrong:** I wrote this as "a DATA ACQUISITION item —
`pbp_participation_2026` has never been captured". The tree already holds the
measurement that corrects it. `nfl/INFORMATION_GAP_REGISTRY.json`'s
`GAP-2026-PARTICIPATION`:

> `pbp_participation` returned **404 at every one of its 12 probes**,
> 2026-09-08T13:28:42Z through 2026-09-15T06:37:05Z. … **THE WATCH HAS NOT RUN
> SINCE 2026-09-15T06:37:05Z**, so neither half of this sentence is current, and
> the horizon that would surface that is **two days**.

It is not a dataset we failed to capture. On twelve consecutive probes it **did
not exist upstream**. And the last look was 12 days ago against a 2-day horizon,
so even the 404 is formally not current.

**There is an already-authorized task for the watch: SUN-1, status QUEUED.**
`nfl-availability.yml` last ran 2026-09-15T06:37:05Z, and line 130 is still
`git push origin HEAD:main` while the four capture workflows moved to
`capture-prod` twenty-two minutes after its last successful run. So the
participation watch is broken in the same family as DEF-086 but for a different
reason — wrong push target rather than stale cron.

**Why the re-probe comes first.** The sibling source is the precedent:
`snap_counts_2026` was 404 on 2026-09-08 and **200 on 2026-09-10**, growing
93 → 187 → 1,397 rows. The registry states that the earlier combined claim "both
404" was "true when written and is now HALF FALSE". If participation has begun
publishing in the last 12 days, this blocker dissolves with no code written.

**And if it is still 404**, the honest conclusion is stronger than anything
currently in the queue: the accepted `ewma_hl2` arm cannot run for 2026 at all
until nflverse publishes participation, because true `pass_snaps` has no other
source. That is external data availability — not a code task and not a ruling.

Requested as OUT-034 plus its correction.

`feature_build` remains genuinely unimplemented — `fx['features']` has no
producer anywhere in production, which I checked — and that is correctly recorded
as declared debt. It is simply **not what is stopping today's board**, and
treating it as the blocker has been pointing effort at the wrong layer.

## The fallback that exists, and why it does not reach today

`panel_2026w1.py` derives the panel from held evidence and approximates the one
missing field as
`pass_snaps_approx = offense_snaps * (team_dropbacks / team_offense_plays)`,
carrying arithmetic bounds `lo = max(0, S-R)`, `hi = min(S, D)` on every row so a
consumer sees the width of the guess rather than a point value on trust. Every
row is stamped `pass_snaps_basis='APPROXIMATED_FROM_TEAM_DROPBACK_RATE'`.

It is explicitly fenced: *"THIS IS NOT THE ACCEPTED ESTIMATOR AND MUST NEVER BE
FED TO IT"* — rows are consumed only by the separately identified candidate
`V1_CANDIDATE_R9_W1P`.

**Three reasons it does not produce today's board**, and none of them is a rule I
could choose to relax:

- it is hard-coded `WEEK = 1`, built to unblock a **week-2** forecast; today is
  **week 3**, which needs weeks 1 **and** 2;
- its week-1 coverage is **10 of 16 games**, and its own docstring says the
  league-wide positional mean from those rows *"is NOT a league mean"*;
- week-2 snap evidence is **93 rows against week 1's 1,492**, so extending it to
  week 2 would rest on an input that is itself thin.

## What is lawful today, stated precisely

`authorization.may_compute()` returns **PASS/COMPUTE_ALLOWED**;
`may_publish()` returns **BLOCKED/NFL1_NOT_AUTHORIZED**. So computing and
sealing is permitted and publishing is not, independently of everything above.

The Q9 live pregame feature builder **works today**: all 18 slate clubs return
`Q9_LIVE_FEATURE_ROWS_OK`, **271 live feature rows**, 25 features, six prior
seasons of history, zero refusals. Joined to the frozen DK universe, **268 of the
457 DK rows** have Q9 features — 75 RB, 117 WR, 76 TE, or 71% of the 379 RB/WR/TE
rows. The 189 without features are **all 60 QB, all 18 DST**, and 111 RB/WR/TE
whose salaries sit entirely in the **$2,500–$4,000** band, median $3,000.

That last figure is the same shape as the FantasyCruncher finding and matters for
the same reason: the uncovered players are the cheap depth tail, which is exactly
who inactives promote into relevance.

Note also `Q9_G0A_REMAINING_ITEM.json`: G0A reads **11/12**, and *"no forecast
written before G0A is discharged counts toward promotion"* — a Q9 shadow forecast
may be computed and sealed but accrues no promotion evidence.

## Correcting one link I nearly drew

G0A item #1 is *"Kickoff-anchored vintage capture scheduled and demonstrably
running"*, and DEF-086 found the T-90 cron on `main` two weeks stale. **These are
not the same blocker.** The artifact names the root cause as **EGRESS** —
`CONNECT www.nfl.com:443 -> 403`, measured — and states that item 1 *"fails on
the endpoint, and would still fail with a perfect scheduler. More code here moves
nothing."* DEF-086 is real and independent; it is not what holds G0A.

## The decision this leaves

Nothing here needs a ruling to *proceed*: the capture is assignable work. What
would need an owner decision is only this — whether a candidate-identified,
partially-covered, approximation-based board is wanted for a live slate at all.
On the evidence above it could not cover today's week-3 games regardless, so that
decision is not urgent today.
