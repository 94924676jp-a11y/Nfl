# KC backfield: a falsification test of the role-allocation layer

Label: **DIAGNOSTIC ONLY.** No coefficient, flag, governance rule or candidate
identity was changed. `POSTINACTIVES_CURRENT` stands exactly as delivered.
The external nflverse baseline is a **benchmark, not ground truth**, and
nothing in it was fed into the forecast. V2 NOT YET EARNED.

## What was tested

`POSTINACTIVES_CURRENT` (run `12eda64603a377d7`) projects KC's listed
FULLBACK as the lead rusher. The question is not whether the external
baseline is right. It is whether our own inputs support our own output.

## 1–3. The observable evidence, all of it pointing one way

| KC back | gsis_id | roster pos | depth chart | W1 2026 carries | W1 snaps | W1 snap % |
|---|---|---|---|---|---|---|
| Kenneth Walker III | 00-0038134 | RB | **RB** | **23** | 47 | **0.68** |
| Emmett Johnson | 00-0041013 | RB | RB | 8 | 25 | 0.36 |
| Ben VanSumeren | 00-0038489 | RB | **FB** | **0** | 3 | **0.04** |
| Brashard Smith | 00-0040078 | RB | RB | 0 | 0 | 0.00 |

Week-1 carries counted from `play_by_play_2026` (`play_type == "run"`, REG,
`posteam == KC`); snaps from `snap_counts_2026`. Walker also took 173 rushing
yards in that game.

Against that, the model's post-inactives output:

| KC back | model carries | model rush yds | model targets | model DK mean |
|---|---|---|---|---|
| **Ben VanSumeren** | **9.410** | 40.578 | 2.953 | 10.53 |
| Kenneth Walker III | 6.612 | 28.299 | 2.411 | 8.05 |
| Emmett Johnson | 2.641 | 11.388 | 1.130 | 3.39 |
| Brashard Smith | 1.236 | 5.217 | 1.030 | 2.21 |

**Every observable available to the engine — depth chart, Week-1 carries,
Week-1 snap share — orders Walker far above VanSumeren. The output inverts
all three.** This is not a data gap. The data says the opposite of the
output, which is what makes it a falsification rather than an uncertainty.

## 4. How team rushing opportunity is allocated

`rushing_a1` (OWN-9 A1, single-owner) partitions `rush_play_budget =
team_carries − scrambles` across six CATEGORIES — kneel, designed_qb, rb, wr,
te, fringe — with one multinomial per draw. It is closed by construction and
it does **not** split the `rb` category among individual backs. The
within-room split happens upstream, in the class point forecast
(`p4c-system-C-frozen`) with the R6 tier-conditional role prior
(`role-prior-tier-conditional-r6`).

## 5–6. Why VanSumeren receives 9.41 carries

The carry class is defined as `CLASSES['carries']['pos'] == ('RB',)`. The
prior is tier-conditional, and a player's history enters it only through
panel rows whose **panel position** is in that class.

| player | panel rows | positions in panel | rows INSIDE the carries class | measured carry share |
|---|---|---|---|---|
| Kenneth Walker III | 67 | RB × 67 | **67 of 67** | ~0.41 (SEA, late 2025) |
| Ben VanSumeren | 10 | **LB × 10** | **0 of 10** | 0.0 on every row |
| Brashard Smith | 17 | RB × 17 | 17 of 17 | up to 0.52 (W18) |
| Emmett Johnson | 0 | — | 0 | none (rookie) |

**VanSumeren is a COLD-START player for carries.** He is carried on the 2026
roster as `position RB`, so he enters the rush pool; his entire panel history
is labelled `LB`, so none of it is in the carries class; and the ten rows he
does have carry a measured carry share of **0.0**.

So a back with a **measured** 0.41 carry share is beaten by a player with
**no in-class history at all**. That locates the defect: the cold-start
default for the carry class sits near a lead-back workload rather than near
the bottom of the room, and **nothing in the path uses the depth chart to
stop a roster-RB-listed fullback from drawing it**. The depth-chart field
exists and is read (`depth_chart_position == 'FB'` is what the Showdown gate
flags him on), but it is not an input to the carry allocation.

Two further facts belong here because they bound the explanation:

* The panel ends at **2025 week 18**. Walker's 23-carry Week 1 and
  VanSumeren's zero are NOT in it. `include_2026w1_participation` and
  `current_season_state` are separate mechanisms and did not reverse the
  ordering.
* `targets_carries` reports `governance DATA_BLOCKED` on both classes and
  elapses in 4e-05 s, so the stage is reading an upstream product rather than
  computing there.

## 7. Is Walker suppressed by a normalisation bug?

**No evidence of one, and the hypothesis is not needed.** A1 is closed by
construction with no clipping, no survivor renormalisation and no overflow
dumping, and the room's carries sum sensibly (9.41 + 6.61 + 2.64 + 1.24 ≈
19.9 plus scrambles). Walker is not being scaled down; VanSumeren is being
scaled **up** from a cold start. Those are different defects and the fix for
one would not address the other.

A hypothesis I held and now withdraw: that Walker was penalised as a
cross-team acquisition (SEA → KC). His `f_team_change` is set, but his
in-class history is complete and his measured share is high, and the
cold-start account explains the inversion without it.

## What this does NOT establish

OBSERVED: the ordering contradicts depth chart, Week-1 carries and Week-1
snaps; VanSumeren has zero in-class history; Walker has 67 rows at ~0.41.

INFERRED: the cold-start default for the carry class is too generous and
there is no positional/depth guard on entry to the rush pool.

HYPOTHESIS, NOT SHOWN: that fixing either would improve forecast accuracy.
One game cannot show that. The external baseline agreeing with the depth
chart is **not** evidence that its 14.8 carries is the right number.

## Proposed experiment (NOT run tonight, NOT a production change)

**KCB-1 — depth-chart-conditional cold start.** Hypothesis: for the carry
class, a player with zero in-class panel rows should draw a prior conditioned
on his captured `depth_chart_position`, not a position-blind default; and
`FB` should not be eligible for the lead-back tier.

Design, to be pre-registered before any run:

1. Arm A = current candidate, untouched. Arm B = A plus the
   depth-chart-conditional cold start. One declared treatment; everything
   else in the execution identity identical.
2. Forward-chained: select any shrinkage on weeks strictly before the
   evaluation week. No random split.
3. Population: every team-game with at least one cold-start player in the
   rush pool — not just this room, which would be selecting on the finding.
4. Score: MAE, RMSE and log score on per-back carries and rushing yards,
   with standard errors **clustered by game**. Week-2 grading measured a 1.36×
   SE inflation from clustering; a naive SE here would overstate the result.
5. Regression guard: rooms with no cold-start player must not move.
6. Report failure to improve as failure to improve. No promotion is implied
   by running this.

## Data-engineering findings adopted for future research

Recorded as standing practice; none implemented during the slate.

* **Join on `gsis_id`, never on displayed name.** Already enforced in the
  Showdown identity path (Drew/Andrew Ogletree was left unresolved rather
  than matched by resemblance).
* **nflverse scramble handling.** The `pass` flag is a DROPBACK flag: it is 1
  on sacks and on QB scrambles, and `rush` is 0 on scrambles. A carry count
  built from the `rush` flag silently loses every scramble. Count carries as
  `play_type == "run"`, as this diagnostic did.
* **Pre-aggregated `player_stats` assets 404 on that URL pattern.** The
  working weekly asset is
  `releases/download/stats_player/stats_player_week_2026.csv`; verify with a
  HEAD request rather than assuming an asset exists.
* **Filter `season_type == "REG"` and drop `no_play` rows** before counting;
  penalty rows carry player names and inflate usage.
* **Archive raw source bytes with sha256 before parsing**, and pin asset
  hashes in a manifest — the pbp files are rewritten in place as games
  finish, so an unpinned re-download is a different input.
* **Ingest rosters and depth charts as first-class inputs**, which is exactly
  what this diagnostic shows the carry allocation is missing.
* **Select blend and shrinkage weights in a forward chain**, never by hand
  and never on a random split.
