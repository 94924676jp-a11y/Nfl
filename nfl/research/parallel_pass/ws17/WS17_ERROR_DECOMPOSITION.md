# WS17 — Where the forecast error actually comes from

**CODE CHANGED: NO.** Nothing in the repository was modified. Every file this
workstream wrote lives under `nfl/research/parallel_pass/ws17/`.

**GOVERNANCE.** Diagnostic only. Not prospective evidence, not a ledger row,
counts toward no sample floor, clears no blocker. One week of football is not a
sample and nothing below is a test. No market data was consulted.

**Scope.** 9 gradable games / 18 team-games, from
`nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz`
(sha `1415dd98ba7f701a…`, 1,738 rows, 10 games; `2026_01_NE_SEA` has no seal in
`nfl/research/live/` and is excluded, as in the existing audit). The five late
games are not published. Chronology was re-verified per seal: every board used
has `freshness.written_at` strictly before its kickoff from
`nfl.capture.coverage.load_week_plan(2026, 1)` — the tightest margin is
`2026_01_SF_LA`, sealed 00:13:09Z against a 00:35:00Z kickoff.

---

## 0. Verification of the existing scoring pass, before reusing it

`nfl/research/same_day_retrospective.py` was read line by line and re-executed
independently. Three things check out and one does not.

**Correct.** (a) Chronology is enforced, not assumed. (b) Player strata come
from the *forecast's* own ordering of projected volume (`role_tiers`), never
from realised production. (c) CRPS and PIT come from the 1,000 stored draws,
with the randomised-PIT correction for discrete counts, not from percentiles.
An independent rebuild reproduces its output exactly: **415 scored rows**, and
every published anchor lands on the number (team_carries bias +0.037 → z +0.02;
team_targets +0.128 → z +0.07; carries −3.124 → z −3.14; targets −0.689 →
−2.72; receptions −0.483 → −2.39; receiving yards −3.037 → −1.10; receiver
coverage 99.69%, rusher coverage 84.98%).

**The defect: the scored set is selected on a postgame quantity.** `score_seal`
refuses a row when `src.get(field) is None`, and
`actuals.receiving_rushing_actuals` / `qb_actuals` only emit a player who
recorded a target, a carry or a dropback. So a forecast row is dropped exactly
when the realised count was **zero**. That is not a missing value; for a count
estimand the realised count of a player with no play-by-play row **is zero**.
Reading it as zero is a read, not an imputation — the player was on the week's
roster vintage the board was built from, and the identity join is complete
(0 unmapped in every `INACTIVES_INGESTION.json`).

The size of the selection: **510 of 925 forecast rows in the eleven exact
estimands — 55% — were dropped, and every one of them had a zero outcome.**
The consequence is not marginal. It reverses most of the audit's headline
signs:

| metric | n | bias (scored set) | z_naive | z_game | n | bias (zero-completed) | z_naive | z_game |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qb/att | 21 | −6.360 | −3.38 | −3.36 | 71 | **+0.191** | +0.22 | +0.31 |
| qb/db | 21 | −7.203 | −3.37 | −3.59 | 71 | **+0.195** | +0.20 | +0.30 |
| qb/cmp | 21 | −4.764 | −4.45 | −4.90 | 71 | **−0.095** | −0.17 | −0.32 |
| qb/pyds | 21 | −56.095 | −3.31 | −3.98 | 71 | **−1.718** | −0.24 | −0.33 |
| receiving/targets | 82 | −0.690 | −2.72 | −1.73 | 132 | **−0.075** | −0.42 | −0.27 |
| receiving/receptions | 82 | −0.483 | −2.39 | −2.04 | 132 | **−0.065** | −0.48 | −0.36 |
| receiving/receiving_yards | 82 | −3.037 | −1.10 | −1.19 | 132 | **+0.852** | +0.48 | +0.50 |
| rushing/carries | 22 | −3.124 | −3.14 | −5.39 | 32 | **−1.777** | −2.29 | −3.73 |

Interval calibration moves the same way: on the scored set coverage is
0.643 / 0.889 / 0.940 at 50 / 80 / 90 with PIT mean 0.619; zero-completed it is
0.837 / 0.950 / 0.973 with PIT mean 0.489.

**Reading.** The model does not systematically under-forecast volume. It
forecasts roughly the right *total* and puts too much of it on players who then
record nothing — which the audit's refusal rule hides by deleting precisely
those rows. **Carries are the one metric that survives zero-completion**
(−1.777, game-clustered z −3.73), and that is the C1 double-subtraction already
diagnosed in commit `3f5fc82`.

Recommendation (reporting layer only, not attempted here): keep
`NO_REALISED_VALUE_FOR_THIS_PLAYER` for estimands where zero is genuinely
undefined, and carry a zero-completed stratum beside the scored one for counts,
so both numbers are visible and neither is the only one.

**SE convention matters and does not move in one direction.** For the same
estimate, clustering *widens* the interval for targets (z −2.72 naive → −1.73
by game) and *narrows* it for carries (−3.14 → −5.39), because the carries
error is the same sign in every game so the cluster means are more consistent
than the rows. Every z below is stated with its convention. Non-independence is
handled by clustering on `game_id` (n = 9, or 5 where only non-QB layers
exist); no player-row is treated as independent anywhere.

---

## 1. Per-bucket quantification

The decomposition is algebraic and exact, with residual ≤ 1.4e−14 on every
identity. For a quantity `num = den × rate` and `den = T × share`:

```
err = rate_hat · share_hat · (T_hat − T_act)      TEAM OPPORTUNITY
    + rate_hat · T_act · (share_hat − share_act)  PLAYER ALLOCATION
    + den_act · (rate_hat − rate_act)             EFFICIENCY
```

Realised counts are the true counts (zero for a player who recorded nothing);
no row is dropped for a zero outcome. Shares are per team-game. Uncertainty is
the game-clustered standard error of the per-game component share.

### Bucket summary

| bucket | best available quantification | uncertainty |
|---|---|---|
| **Eligibility** | 5.3% of all forecast opportunity mass sat on officially inactive players (61.8 of 1,151 opportunities). Split: **5.2 pp at pre-inactives seals** where the list did not yet exist, **0.1 pp at post-inactives seals** | 4 pre / 5 post games |
| **Participation** | **14.8%** of forecast opportunity mass (170.4) sat on players who were *not* on the inactive list and still recorded zero. QB 25.0% of dropback mass, receiving 16.3% of target mass, rushing 8.6% of carry mass | per-game zero-mass share 0.223 ± 0.043, range 0.081–0.441 |
| **Team opportunity** | Bias +0.04 carries, +0.13 targets, +0.94 dropbacks per team-game (naive z +0.02 / +0.07 / +0.46; game-clustered +0.05 / +0.06 / +0.40). MAE 5.76 / 6.03 / 6.21 against a 2024 oracle-season-mean floor of **5.45 / 5.60 / 6.09** | n = 18 team-games |
| **Player allocation** | 46–76% of all |error| in every layer: targets 0.75 ± 0.04, carries 0.76 ± 0.06, receptions 0.56 ± 0.03, receiving yards 0.46 ± 0.03, QB dropbacks 0.71 ± 0.05, QB passing yards 0.52 ± 0.05 | per-game share ± clustered SE |
| **Efficiency** | 26–38% of |error| where a rate is modelled (receiving yards 0.38 ± 0.03, receptions 0.26 ± 0.03, QB passing yards 0.28 ± 0.05). **No rate is distinguishable from unbiased:** yards/target +0.59 (z +0.88), catch rate −0.006 (z −0.32), yards/attempt −0.38 (z −0.83), completion rate −0.027 (z −1.68), yards/dropback −0.32 (z −0.77) | n = 5 or 9 games |
| **TD / event variance** | All small and all unbiased: receiving TD +0.014/row (z +0.55), rushing TD −0.173 (z −1.10), pass TD −0.035 (z −0.40), INT +0.036 (z +1.11), sacks +0.050 (z +0.69) | game-clustered, n = 5–9 |
| **Injury / in-game event** | **Essentially absent from this slate's forecast population.** 32 in-game injury notices in the play-by-play text, 10 with no "has returned"; only **3** name a board player (C. Olave, D. Allen, K. Mumpfield) and **all three returned** | n = 9 games |
| **Irreducible variance** | Level-matched 2024 oracle-season-mean floor vs model MAE: receiving yards 13.24 → 14.57 (**+9.2%**), QB dropbacks 7.41 → 8.70 (+14.9%), targets 1.27 → 1.61 (+21.0%), carries 2.52 → 3.65 (+31.1%). Team volume is within 2–8% of its own floor | floor pooled over 1,809–3,954 2024 player-games |
| **Missing-data limitation** | Non-QB layers produced **nothing for 8 of 18 team-games** (4 of 9 games): 220 of 543 realised targets (40.5%) and 221 of 494 realised carries (44.7%) had no player forecast at all. `rushing/rushing_yards` is not modelled anywhere — 1,229 realised rushing yards in the ten *covered* team-games have no forecast. `team_off_snaps` and `team_dropbacks_part` are unscoreable because the participation feed is blocked | counts, not estimates |

### The QB room, separately, because it carries the most mass

Stratum is the board's own pregame `depth_chart`, never the outcome.

| pregame slot | n team-games | forecast dropbacks | realised | bias/row | mean abs allocation error |
|---|---:|---:|---:|---:|---:|
| QB1 | 18 | 510.5 | **618.0** | −5.97 | 7.98 |
| QB2 | 18 | 88.1 | **6.0** | +4.56 | 4.35 |
| QB3 | 12 | 28.5 | 26.0 | +0.21 | 4.00 |
| QB4 | 5 | 6.8 | 0.0 | +1.36 | 1.12 |
| unlisted | 18 | 30.0 | 0.0 | +1.67 | 1.58 |

The QB1-slot shortfall is −5.97 dropbacks per team-game, game-clustered
SE 2.60, **z = −2.30 (n = 9 games)**. Team dropbacks are unbiased over the same
18 team-games, so this is redistribution inside the room, not a volume miss:
**25.0% of all forecast dropback mass (166.1 of 663.8) went to quarterbacks who
took zero dropbacks.** The largest single instances are CLE QB2 (20.08 forecast,
0 actual), IND QB3 (17.27, 0), ATL QB1 (19.72, 0 — officially inactive), BUF QB2
(11.65, 0). All 21 gradable QB player-games are QB3-contaminated: week 1 is a
season opener for every club, so `previous_primary_detail` carries no incumbent
and the contamination cannot be switched off in this sample.

---

## 2. The five empirically supported sources of error, ranked

**1 — Quarterback-room allocation (participation-shaped), at a cold start.**
Evidence: 25.0% of forecast dropback mass on QBs who never played; QB1 slot
−5.97 dropbacks/team-game, game-clustered z −2.30 (n = 9); allocation is
0.71 ± 0.05 of |dropback error| and 0.52 ± 0.05 of |passing-yards error| while
team dropbacks are unbiased (z +0.40). Uncertainty: 9 games, and 100% of QB
rows are QB3-contaminated, so a general QB-allocation defect and a week-1
cold-start specification defect **cannot be separated in this sample**. What
would separate them is week 2, where an incumbent exists.

**2 — Running-back carry allocation (the C1 double subtraction).** Evidence:
the only bias that survives zero-completion — −1.777 carries/row, game-clustered
z −3.73 (n = 5 games); −3.124 on the audit's scored set, naive z −3.14.
Allocation is 0.76 ± 0.06 of |carry error| against an unbiased team budget
(+0.04, z +0.02). Root cause already measured in `3f5fc82`: `p4c_lib` fits
`other` on a `team_carries` denominator (0.1989) while production feeds it A1's
`rb` category, where the correct value is 0.0088 — 0.1901 of the back's budget
subtracted twice. Uncertainty: 5 games, 28 rows; **every seal predates the
repair** (boards built at commits `f9e4718` 15:28Z and `410daf5` 15:52Z on
09-13; the repair commit is 09-14 00:36Z), so this measures the pre-repair
allocator and nothing here scores the fix.

**3 — Whole layers absent: game-scoped refusals for player-scoped gaps.**
Evidence: 8 of 18 team-games (BUF_HOU, CHI_CAR, CLE_JAX, NYJ_TEN) got no non-QB
board at all, removing 40.5% of realised targets and 44.7% of realised carries
from the forecast entirely; plus `rushing/rushing_yards` modelled nowhere
(1,229 realised yards uncovered in the games that *did* get a carries board).
Where a board was produced, coverage is 99.7% of targets and 85.0% of carries —
so this is a refusal-blast-radius problem, not a player-pool problem.
Uncertainty: these are counts from the bytes, not estimates; the *causes*
(INJURY_REPORT_INCOMPLETE, ALLOCATION_PLAYER_WITHOUT_APPEARANCE,
NONQB_PLAYER_FRAME_INCOMPLETE) are read from `OPEN_DEFECTS.json`, not
re-derived here.

**4 — Irreducible game-to-game variance, which bounds how much of the rest is
worth chasing.** Evidence: a 2024 oracle forecaster that predicts every game
with the player's own full-season mean — a forecaster that uses the future and
is unavailable pregame — still has MAE 1.27 targets, 13.24 receiving yards,
2.52 carries, 7.41 QB dropbacks. Level-matched, the model's excess over that
floor is **+9.2% (receiving yards), +14.9% (QB dropbacks), +21.0% (targets),
+31.1% (carries)**. Team volume is within 2–8% of its own floor and should be
treated as finished. Uncertainty: the floor population is players who recorded
a game row, so it understates the zero-outcome cases and is a lower bound, never
a target; and 2024 need not transfer to 2026.

**5 — Eligibility, which is now almost entirely an information-set boundary
rather than a code defect.** Evidence: 5.3% of forecast opportunity mass sat on
officially inactive players, but **5.2 of those 5.3 points come from the four
pre-inactives seals**, where the league list was published 0.76 s *after* the
seal was written (`published_at` 15:46:51.760Z vs `written_at` 15:46:51Z). Only
0.1 pp remains at post-inactives seals — D04's repair holds. The biggest single
instance, ATL's QB1 at 19.72 forecast dropbacks and zero actual, is
unforecastable at that information set. Uncertainty: 4 pre / 5 post games; the
post-inactives residue is small enough that 5 games cannot distinguish "fixed"
from "nearly fixed", and no equivalence margin was predeclared.

---

## 3. What could NOT be attributed, and why

**Efficiency vs irreducible variance — UNRESOLVED.** Efficiency carries 26–38%
of the |error| magnitude, but every efficiency rate is statistically
indistinguishable from unbiased at this sample (largest |z| = 1.68, QB
completion rate, game-clustered n = 9), and the two signed efficiency totals
point in *opposite* directions — receiving yards +181.6 (model too generous per
target) against QB passing yards −220.0 (model too stingy per dropback). Nine
games cannot tell a real conversion defect from noise. Do not read the 26–38%
as a defect share; it is a magnitude share.

**TD and low-count events — UNRESOLVED, with no evidence of a defect.** All
five event metrics are unbiased at |z| ≤ 1.11. Rushing touchdowns look
arresting in ratio (5.5 forecast against 11.0 realised) but that is 32 rows over
5 games at z −1.10. It is a hypothesis for more data, not a finding.

**Participation vs allocation — NOT SEPARATELY IDENTIFIED.** A player who
dressed and took zero snaps and a player who took twenty snaps and was never
targeted are the same row in play-by-play. Splitting the 14.8% participation
mass from the allocation bucket requires snap counts or the participation feed,
both of which are blocked in this environment. The two are reported separately
above only because the *inactive list* gives a hard boundary at one edge; the
other edge is assumption-free only in the sense that it is unmeasured.

**Injury and in-game events — UNRESOLVED at the non-QB level, and empirically
near zero at the QB level.** Only 3 board players appear in an injury notice and
all 3 returned. The early-exit screen flags K. Pitts (6.93 forecast targets,
1 target, last touch Q1), Z. Flowers (8.91 / 6, all by Q2), G. Kittle
(5.40 / 5, all by Q2), E. Egbuka (5.56 / 6, all by Q2) and T. Lawrence (32.57
forecast dropbacks, 24 pass plays, Q1–Q3) — but "left the game" and "was not
targeted after half-time in a game that got out of hand" are indistinguishable
without snap counts. **No error in this slate is attributed to injury.**

**Game state — NOT MEASURED HERE.** `OPEN_DEFECTS.json` D09 records that the
engine has no game-state conditioning. It would express itself through the
team-opportunity and efficiency buckets, both of which are unbiased at this
sample, so this workstream can neither confirm nor rule it out.

**MODEL MISS vs EVENT SHOCK vs DATA LIMITATION.** Ranks 1 and 2 are model
misses: both are systematic, both survive clustering, both have a named
mechanism in code. Rank 3 is a data limitation (a refusal, correctly refusing to
invent, at the wrong scope). Rank 5 is a data limitation at the pre-inactives
stage and a resolved model miss at the post-inactives stage. **No rank is an
event shock** — the event-shock bucket is empirically empty on this slate.

---

## 4. Evidence ceiling

- 9 games, 18 team-games, 925 forecast rows across 11 exact estimands; only
  **5 games / 10 team-games** carry any non-QB layer, so every receiving and
  rushing figure rests on five clusters.
- One week, and that week is **every club's season opener**. QB3 contamination
  is therefore 100% of QB rows and cannot be turned off; nothing here separates
  a cold-start defect from a standing one.
- Nothing is pre-registered. No equivalence margin was declared for any
  quantity, so no bucket may be described as unbiased, adequate, closed or
  correct — only as not distinguishable from zero at this sample.
- Every seal predates the C1 repair and the `57d38ad` eligibility change, so
  these numbers describe the engine as it stood on 2026-09-13, not as it stands
  at HEAD. They are a **baseline**, and a re-run after either change is a
  different arm, not a continuation of this one.
- Five late games and `2026_01_NE_SEA` are outside the frame; adding them can
  move every figure here, and the late window is not a random sample of the
  slate.
- The oracle floors are 2024 quantities used as 2026 bounds. That transfer is
  an assumption, and a stated one.
