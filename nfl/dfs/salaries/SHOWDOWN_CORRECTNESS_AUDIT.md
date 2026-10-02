# PIT @ CLE Showdown — correctness audit and repair

2026 week 4, game `2026_04_PIT_CLE`. Audit opened against working baseline `6e6c82dd`.

`PROJECTION_SYSTEM_STATE` remains **NOT_VALIDATED**. Nothing below is a claim of predictive edge,
of promotion, or of superiority over any external model. No wager is recommended.

FantasyCruncher is used here as **external diagnostic evidence only**. It is not blended into any
projection, not used as a fallback, not averaged against, and no coefficient was tuned toward it.
Where our number moved, it moved because a state defect was repaired, and it is a separate fact
that the repaired number happens to sit closer to FC.

---

## 1. Root cause: starter evidence had no ingestion path, and its absence was read as a denial

**Old starter state.** Every quarterback on the slate, all eight of them, carried
`is_predicted_starter = false`. Watson and Rodgers additionally carried
`appearance_adjustment.reason = NOT_PREDICTED_STARTER` with `appearance_rate = 0.13789` and
`measured_rank2_unconditional_share = 0.01939`, which are **rank-2 backup quarterback** quantities.

**Corrected starter state.** Watson and Rodgers now carry
`appearance_adjustment.reason = DEPTH_RANK_1_IS_THE_STARTER`, `applied: false`, and keep their full
pass-attempt claim. Mason Rudolph and Shedeur Sanders, both genuinely rank 2, now carry
`DEPTH_RANK_2` and are charged the rank-2 curve — the protection that gate exists for is intact.

**Exact root cause, three links:**

| Layer | What happened |
|---|---|
| starter-source ingestion | `showdown_slate_state.py:311` hard-coded `'predicted_lineup_context': {}`. **There was no ingestion path for starter evidence into a showdown slate state at all.** The confirmed-starter information existed in conversation, never as a machine-readable artifact for this game. The only availability artifact supplied for tonight is `OFFICIAL_INACTIVES_PIT_CLE_2026W4.json`, which names players who are OUT and says nothing about who starts. |
| role-state propagation | `role_state.assign` computes `pred = bool((row.get('predicted_lineup_context') or {}).get('in_predicted_starting_group'))`. `bool(None)` is `False`, so an empty context became a definite negative, written to the artifact as `in_predicted_group: false`. |
| appearance adjustment | `proj_v1.project_player` gated on `is_predicted_starter is False` and then reached for `by_rank['rank_2']` **unconditionally, whatever the player's own rank**. So a rank-1 starter was charged a backup's appearance probability, and a rank-3 quarterback would have been charged a rank-2 one. |

This is the project's oldest defect class: **a step that returned nothing was read as an answer.**
UNKNOWN became NO. It is the same shape as the Git-LFS pointer read as a corrupt log and the
export that wrote 7,926 rows of blank columns.

**Layers that were NOT the cause**, each checked rather than assumed:

- **Identity matching — not the cause.** Both quarterbacks resolved correctly:
  Rodgers `00-0023459`, Watson `00-0033537`, both with `depth_rank` present and correct.
- **Weekly roster / depth-state freshness — not the cause.** The Sept 24 roster blob produced
  `depth_rank` 1 for Watson, 1 for Rodgers, 2 for Shedeur Sanders, 2 for Mason Rudolph. FC's own
  `pDepth` column independently reads QB1, QB1, QB2, QB2. **The depth state was already correct and
  externally corroborated; only the code reading it was wrong.** A roster refresh would not have
  fixed this defect.
- **Team mapping — not the cause.** Club membership was correct throughout.

So the contradiction you identified — `depth_rank=1` + ALPHA + starter-level volume +
`NOT_PREDICTED_STARTER` — was real, and it was the gate ignoring the first three facts in favour of
a fourth that was never evidence.

---

## 2. Code and state fixes

1. **`nfl/tools/proj_v1.py` — the appearance gate now requires positive evidence of backup status.**
   - `depth_rank == 1` → never penalised, reason `DEPTH_RANK_1_IS_THE_STARTER`.
   - `depth_rank >= 2` → penalised, **indexed by his own rank** (`rank_3` for a third-stringer),
     reason `DEPTH_RANK_{n}`.
   - no rank, but a predicted-lineup feed covered his club and omitted him → penalised, reason
     `NOT_IN_PREDICTED_LINEUP_FEED_THAT_COVERED_HIS_CLUB`. That omission *is* positive evidence.
   - no rank and no feed → **not penalised**, reason `NO_EVIDENCE_OF_BACKUP_STATUS`, and the
     resulting unguarded volume is declared in the artifact as `UNMODELLED_RISK` rather than
     passed off as a clean number.
   - absent rank curve → recorded as `DEPTH_RANK_CURVE_ABSENT`, never silently skipped.
   - `project_player` now receives `depth_rank` and `predicted_feed_covers_club`; `build()` computes
     per-club feed coverage so that `False` can be distinguished from "nobody asked".

2. **`nfl/tools/showdown_slate_state.py` — starter evidence now has an ingestion path.**
   `--confirmed-starters` accepts `{name: CLUB}` or a bare list. A **club mismatch fails closed**
   (`STARTER_EVIDENCE_REJECTED_CLUB_MISMATCH`) rather than being applied, and a player absent from
   the list gets `{}` — unknown, not denied.

3. **`nfl/tools/showdown_draws.py` — identity provenance was recording nothing.**
   `o.evidence.get('identities')` was wrong twice over: the payload is on `.value`, and the key is
   `club_checks`. Every draws artifact ever written recorded `None` for identity verification while
   looking like it had checked. It now records the real figure — **4,000 club-game identity checks**
   across the five named identity classes, with allocation mode and share family.

Both QBs were recomputed naturally from the repaired state. **No fantasy points were hand-set, and
no market input was edited.**

---

## 3. Tests added — `nfl/tests/test_starter_state.py`, 11 checks, 11 passing

The gate checks **execute the real gate source**, sliced out of `proj_v1.py` by AST and run in a
wrapper, so they cannot pass against a stale copy of the logic.

| Check | Proves |
|---|---|
| confirmed starter reaches state as `in_predicted_starting_group True` | ingestion works |
| bare list form accepted | relay shape tolerance |
| **wrong-club starter evidence fails closed** | stale/mismatched evidence rejected, not applied |
| **missing starter evidence stays missing** | `{}` for absent and for no-list-at-all |
| **a `DEPTH_RANK_1` QB is never charged a penalty** | forced across all four flag combinations |
| **a confirmed starter cannot emerge `NOT_PREDICTED_STARTER`** | the owner's stated invariant |
| **missing evidence does not trigger the penalty** | the exact 2026 W4 regression |
| a `DEPTH_RANK_2` QB *is* charged | the Fields protection still holds |
| penalty indexed by own rank | rank 3 uses `rank_3`, not `rank_2` |
| feed covered his club and omitted him → charged | absence-of-mention as real evidence |
| absent rank curve recorded | no silent skip |

---

## 4. Watson and Rodgers — before and after, as football quantities

Recomputed from the repaired state. Nothing here was set by hand.

| Quantity | Watson before | Watson after | Rodgers before | Rodgers after |
|---|--:|--:|--:|--:|
| pass attempts | 29.01 | **33.16** | 30.91 | **35.58** |
| pass yards | 173.90 | **198.82** | 187.99 | **216.39** |
| carries | 1.08 | **6.17** | 0.40 | **2.65** |
| rush yards | 5.14 | **29.43** | 0.96 | **6.32** |
| red-zone rush opportunities | 0.205 | **1.173** | 0.011 | **0.074** |
| DK points (unconditional) | 11.1919 | **16.3276** | 11.9077 | **14.3673** |
| DK points if he plays | 11.7196 | **16.3392** | 12.5478 | **14.3818** |
| FC, benchmark only | — | 20.81 | — | 16.90 |

**The dominant mechanism was rushing, not passing.** The gate multiplied `carries` by the appearance
rate directly (`claims['carries'] *= 0.13789`), taking Watson from 6.17 carries to 1.08 and his rush
yards from 29.4 to 5.1. The pass-attempt cap also bound — his claim was capped from 0.99166 to
0.01939 — but the club allocator satisfies CLE's pass-attempt total by construction and still gave
him 29.0 of 33.26, so most of the passing damage was absorbed there and only 4.16 attempts were
lost. That is why Watson, a quarterback who runs, lost 5.14 points while Rodgers lost 2.46.

**Remaining gap to FC after the repair: Watson −4.48, Rodgers −2.53.** Both are now explainable
from declared missing components rather than from broken state — see §7.

---

## 5. Governance finding: sportsbook data DOES enter the proprietary projection

You are right, and it is confirmed by reading the code and measuring the magnitude. **Three** distinct entry points, not the four I first reported — the kicker claim was wrong and is
corrected below:

| Path | How the market enters | Magnitude on tonight's game |
|---|---|---|
| `team_volume` → `market_response.adjust` | measured regression of volume on the **deviation** of this week's line from the baseline line, betas 0.1516 (total) and 0.1767 (favoured-by) at 6.0 and 5.5 standard errors, capped at 20% (cap not binding) | **small**: PIT plays 79.6471 → 79.4633 (−0.18, −0.23%); CLE 79.6639 → 79.9294 (+0.27, +0.33%) |
| club **touchdown pool** | expected club touchdowns regressed on the implied total; the module's own note says "the market enters once, in the touchdown pool" | **material** — this is the load-bearing dependence |
| ~~`kicker_model.project`~~ | **NOT market-dependent — I was wrong about this.** The function *accepts* `club_implied` and `opponent_implied` and **never references either one in its body** (verified by AST: neither name appears among the Names used). Kicker points come entirely from measured per-club attempt rates by distance band plus league make rates. These are dead parameters that advertise a dependence which does not exist — which is exactly how I got it wrong, by reading the signature instead of the body. | **none** |
| `dst_model` `centre_implied_allowed` | points-allowed distribution centred on the opponent's implied total | **material** |

Our implied totals are PIT 20.75 / CLE 17.75 (total 38.5, our captured environment). FC uses
PIT 20.25 / CLE 17.75 (total 38.0). The half-point difference is the known staleness, on the PIT
side only.

**I have not removed this, and that is deliberate.** Removing the market from team volume, the
touchdown pool and the DST would change every projection in the system, including every
number validated in earlier work. It is not a defect repair — the code contains an explicit,
documented design argument for why the market enters exactly once — it is a change to what the model
*is*, it cannot be validated in the time before lock, and it conflicts with a documented prior
decision. Under the escalation rule that makes it **owner-only**: it changes what counts as
evidence and it is irreversible for every downstream baseline.

What I can say with measurement: on tonight's game the *volume* dependence is under 0.35% of plays,
so removing that one path alone would move tonight's board negligibly. The **touchdown pool**
(`td_rates.expected_team_td(implied_total, …)`) and the **DST points-allowed centre**
(`pa_expectation`, which forms the whole distribution as `implied_allowed + residual` over measured
residuals) are the two that would move numbers materially. The kicker needs no change at all.

**Correction, stated plainly because it changes your conclusion.** My first report to you named four
market entry points and called the kicker "material". That was wrong: I read `project`'s signature
and inferred a dependence that its body does not have. There are three, and the kicker is not one of
them. The consequence is that one fewer layer needs rebuilding if you decide to go football-only,
and the Boswell gap to FC has a different explanation — see §7.

Recommended sequencing when you decide: build the football-only variant as a **declared second arm**,
compare it against the current arm on the same slate, and promote only on evidence — not as a
last-minute swap.

---

## 6. Remaining NOT_MODELLED limitations, stated rather than hidden

- **Opponent adjustment — NOT_MODELLED.** No offensive projection is adjusted for opponent strength.
  Every pass/rush efficiency figure above is opponent-neutral. The DST model *does* use opponent
  information (it is centred on the opponent's implied points), so offence and defence are
  asymmetric in this respect. FC carries an explicit `Def v Pos` column, so part of every
  disagreement on an individual player is this missing component.
- **Teammate-absence redistribution — mechanically renormalised, not behaviourally modelled.**
  This distinction matters and the artifact's bare `NOT_MODELLED` understates what happens. Absent
  players are removed from the claim pool, and `allocate_opportunity` then satisfies the club total
  from the remaining players, so opportunity *is* redistributed — **proportionally**. What is not
  modelled is any behavioural change: that a specific backup inherits a specific role rather than
  the room sharing proportionally, or that a club's pass/run balance shifts because its lead back is
  out. With Rico Dowdle inactive, Jaylen Warren's 20.38 comes from proportional renormalisation, not
  from a measured absence-redistribution curve.
- **Weather — carried, not projected.** No weather coefficient exists and none was invented.
- **Interception expectation** is not separately surfaced in the artifact for either quarterback, so
  the FC gap cannot be attributed to it either way from what is stored.

---

## 7. Every material FC gap, attributed after the state repair

Depth ordering was compared against FC's own `pDepth` column. **Where we and FC agree on depth, we
now largely agree on the number**, which is the strongest evidence that the repair was real.

| Player | Ours | FC | Gap | Our rank / FC pDepth | Attribution |
|---|--:|--:|--:|:--:|---|
| Quinshon Judkins | 10.45 | 10.62 | −0.17 | 1 / RB1 | agree on depth, agree on number |
| Browns DST | 6.18 | 6.21 | −0.03 | — / DST1 | agree |
| Roman Wilson | 6.90 | 6.41 | +0.49 | 2 / WR3 | minor |
| Steelers DST | 9.37 | 8.61 | +0.76 | — / DST1 | DST event rates; ours is market-centred on implied allowed |
| Andre Szmyt | 6.54 | 5.73 | +0.81 | — / K1 | kicker attempt assumptions |
| DK Metcalf | 11.52 | 13.38 | −1.86 | 1 / WR1 | agree on depth. Missing opponent adjustment; TD expectation |
| Chris Boswell | 8.65 | 6.25 | +2.40 | — / K1 | **kicker attempt assumptions, and NOT market-driven** (corrected): our attempts come from PIT's measured per-club attempt rates by distance band blended across 2025/2026, plus league make rates. The gap is a genuine disagreement about how often Pittsburgh kicks, not a market artefact |
| Rodgers | 14.37 | 16.90 | −2.53 | 1 / QB1 | residual after repair: no opponent adjustment, interception/TD expectation |
| Darnell Washington | 3.49 | 6.08 | −2.59 | 2 / **TE1** | **depth disagreement** — FC has him TE1, we have him TE2 behind Freiermuth |
| Denzel Boston | 7.39 | 10.41 | −3.02 | 2 / **WR1** | **depth disagreement on the CLE receiver room** |
| Isaiah Bond | 0.01 | 3.05 | −3.04 | 4 / WR4 | role/usage: we give the CLE WR4 essentially nothing |
| Harold Fannin Jr. | 10.07 | 13.19 | −3.12 | 1 / TE1 | agree on depth. Missing opponent adjustment; TD expectation |
| Germie Bernard | 3.24 | 6.39 | −3.15 | 3 / WR4 | role/usage |
| Pat Freiermuth | 11.10 | 7.85 | +3.25 | 1 / **TE2** | **depth disagreement** — the mirror of Washington. Note FC's own pDepth and projection disagree here too |
| Jaylen Warren | 20.38 | 17.15 | +3.23 | 1 / RB1 | agree on depth. **Proportional absence renormalisation** after Dowdle's inactive, with no measured redistribution curve — the most likely place we are too concentrated |
| Watson | 16.33 | 20.81 | −4.48 | 1 / QB1 | residual after repair: no opponent adjustment, TD/interception expectation |
| Travis Homer | 4.99 | 0.26 | +4.73 | 3 / RB2 | **role/usage** — we give the PIT RB2/3 real volume post-Dowdle; FC gives him almost none |
| Jerry Jeudy | 2.83 | 7.86 | −5.03 | 3 / WR3 | **depth/role** on the CLE receiver room |

**The one structural disagreement worth naming.** Our depth capture ranks **KC Concepcion Jr. as the
CLE WR1 (ALPHA, 8.76)**. FC's `pDepth` column has **no entry for him at all**. That single difference
drives the Jeudy (−5.03), Boston (−3.02) and Bond (−3.04) gaps: we concentrate CLE receiving work on
a player FC does not have in its receiver depth chart. This is the disagreement most likely to be a
roster/depth-freshness issue on our side, and it is the one I would want the refreshed weekly roster
to settle — see §8.

**On your item 14, the projection object.** Both the draws builder and the selector consume
`dk_points`, the **unconditional** number. Before the repair that was genuinely wrong in effect,
because the embedded appearance probability was wrong. After the repair, for a rank-1 starter
`dk_points` and `dk_points_if_plays` differ by about 0.01 (Watson 16.3276 vs 16.3392), so the
distinction no longer bites. Architecturally, consuming the unconditional number is the defensible
choice for DFS — you want expected points including the chance a player does not appear — **provided
the appearance probability is correct**. The defect was the probability, not the object.

---

## 8. Your 20 items — what I reached and what I did not

I am not going to represent this audit as complete. It is not. Honest status:

| # | Item | Status |
|--:|---|---|
| 1 | Fix the starter-state pipeline completely | **DONE** — root-caused, repaired, 11 tests |
| 2 | Active / inactive / starter semantics | **PARTIAL** — the starter half is fixed and the vocabulary distinctions hold. `UNKNOWN_ACTIVE_STATE` on players omitted from the inactive list is **correct and deliberate**: absence from an out-list is not positive evidence of being active. Not re-audited end to end |
| 3 | Full QB model audit beyond the flag | **DONE for volume/yards/carries/red-zone** (§4). Interception expectation and the 300-yard bonus are **not separately stored**, so I could not decompose them |
| 4 | Sportsbook data in proprietary prediction | **AUDITED, NOT REMOVED** — confirmed in four paths with magnitudes (§5). Removal is owner-only |
| 5 | Game/team binding | **PARTIAL** — verified PIT/CLE team volume is unchanged by the repair and that all 78 lineups contain only PIT/CLE players. The behavioural cross-team seeding test is **not written** |
| 6 | Refresh weekly rosters | **NOT DONE — BLOCKED.** No network (egress 403) and no roster file was attached to any message. Newest installed blob remains `weekly_rosters.0efeaede1505ab6e` dated Sept 24. Request is in `docs/AGENT_OUTBOX.md`. This is the one item I cannot execute myself |
| 7 | Depth / role logic separation | **PARTIAL** — the specific contradiction you named is now impossible (tests force it). The broader separation of depth rank vs usage rank vs starter evidence vs appearance probability is **not refactored** |
| 8 | Teammate-absence redistribution | **AUDITED** — it is proportional renormalisation, not a measured redistribution curve, and §6 says so precisely. I did not look for `REDISTRIBUTION_STUDY.json` |
| 9 | Opponent adjustment | **AUDITED** — confirmed NOT_MODELLED for offence, and confirmed DST is asymmetric (it does use opponent info). Nothing invented |
| 10 | Weather | **AUDITED** — carried, not projected. Nothing invented |
| 11 | Kicker model | **PARTIAL** — established the kicker is **not** market-dependent (dead parameters; see §5 correction), so no rebuild is needed. The per-distance-band attempt/make decomposition is **not extracted** |
| 12 | DST model | **PARTIAL** — confirmed `centre_implied_allowed` is market-derived. **Not rebuilt** (same owner-only reason as item 4) |
| 13 | Decomposition for every material FC gap | **DONE** (§7) |
| 14 | Projection units, conditional vs unconditional | **DONE** (§7 final paragraph). The four-state test is **not written** |
| 15 | Simulation consistency at 2,000 draws | **PARTIAL** — 2,000 genuine joint draws complete, 4,000 club-game identity checks recorded, absent players receive no draws, kickers from their measured model. Full reconciliation table **not produced** |
| 16 | Optimizer inputs | **DONE** — validated independently, 0 violations |
| 17 | Full exposure board | **DONE** — see §9 |
| 18 | Preserve the first run as baseline | **DONE** — `BASELINE_A_PRE_CORRECTNESS_AUDIT_400_DRAWS` |
| 19 | System-level regression tests | **PARTIAL** — 11 starter-state checks added. The market-input, cross-team, kicker/DST-coverage and optimizer-semantics tests are **not written** |
| 20 | Final acceptance conditions | **NOT MET** — items 4, 6 and 12 are open. See below |

**Acceptance verdict.** Of your twenty acceptance conditions, the mechanical and selection ones all
pass. Three do not: the current weekly roster is not selected (blocked on bytes I cannot obtain),
sportsbook data remains in the proprietary prediction (team volume and the touchdown pool), and
the DST points-allowed centre remains market-derived. **By your own stated conditions this slate is therefore not "final".** The portfolio
is legal, validated, internally coherent and built from repaired state — but it is not built from a
system that satisfies condition 20, and I am not going to call it final when you defined the word.

---

## 9. Full exposure board — corrected run, 2,000 draws, 78 entries

`proj` is the point projection, `draw mean` the mean of the 2,000 joint draws (what the selector uses). Exposure columns are out of 78 entries. BASE-A is the preserved 400-draw pre-audit baseline.

| Player | Pos | Tm | Salary | proj | draw mean | total exp | CPT exp | FLEX exp | BASE-A total | BASE-A CPT |
|---|:--:|:--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Jaylen Warren | RB | PIT | 9600 | 20.38 | 20.41 | 39/78 | 20/78 | 19/78 | 39/78 | 6/78 |
| Deshaun Watson | QB | CLE | 9400 | 16.33 | 16.16 | 39/78 | 7/78 | 32/78 | 39/78 | 3/78 |
| Aaron Rodgers | QB | PIT | 9800 | 14.37 | 15.72 | 39/78 | 2/78 | 37/78 | 35/78 | 6/78 |
| DK Metcalf | WR | PIT | 9000 | 11.52 | 13.94 | 39/78 | 12/78 | 27/78 | 39/78 | 12/78 |
| Quinshon Judkins | RB | CLE | 8800 | 10.45 | 13.85 | 39/78 | 12/78 | 27/78 | 39/78 | 6/78 |
| Harold Fannin Jr. | TE | CLE | 7400 | 10.07 | 12.14 | 39/78 | 5/78 | 34/78 | 35/78 | 9/78 |
| Pat Freiermuth | TE | PIT | 5600 | 11.10 | 11.80 | 33/78 | 5/78 | 28/78 | 35/78 | 2/78 |
| KC Concepcion Jr. | WR | CLE | 6400 | 8.76 | 11.69 | 29/78 | 3/78 | 26/78 | 37/78 | 13/78 |
| Steelers | DST | PIT | 5000 | 9.37 | 7.96 | 29/78 | 2/78 | 27/78 | 25/78 | 2/78 |
| Chris Boswell | K | PIT | 5200 | 8.65 | 8.98 | 28/78 | 2/78 | 26/78 | 22/78 | 6/78 |
| Browns | DST | CLE | 4800 | 6.18 | 6.80 | 27/78 | 4/78 | 23/78 | 24/78 | 8/78 |
| Andre Szmyt | K | CLE | 4600 | 6.54 | 6.90 | 23/78 | 2/78 | 21/78 | 23/78 | 0/78 |
| Roman Wilson | WR | PIT | 4000 | 6.90 | 7.72 | 19/78 | 1/78 | 18/78 | 18/78 | 2/78 |
| Denzel Boston | WR | CLE | 8000 | 7.39 | 6.92 | 15/78 | 0/78 | 15/78 | 14/78 | 2/78 |
| Travis Homer | RB | PIT | 2600 | 4.99 | 5.62 | 15/78 | 0/78 | 15/78 | 12/78 | 0/78 |
| Germie Bernard | WR | PIT | 3200 | 3.24 | 3.73 | 4/78 | 1/78 | 3/78 | 4/78 | 0/78 |
| Raheim Sanders | RB | CLE | 4400 | 4.35 | 4.86 | 3/78 | 0/78 | 3/78 | 10/78 | 0/78 |
| Michael Pittman Jr. | WR | PIT | 7000 | 2.35 | 2.43 | 3/78 | 0/78 | 3/78 | 1/78 | 0/78 |
| Blake Whiteheart | TE | CLE | 1600 | 2.01 | 2.15 | 3/78 | 0/78 | 3/78 | 3/78 | 0/78 |
| Jerry Jeudy | WR | CLE | 3000 | 2.83 | 3.48 | 2/78 | 0/78 | 2/78 | 4/78 | 0/78 |
| Riley Nowakowski | RB | PIT | 200 | 1.23 | 1.63 | 1/78 | 0/78 | 1/78 | 0/78 | 0/78 |
| Darnell Washington | TE | PIT | 3600 | 3.49 | 3.07 | 0/78 | 0/78 | 0/78 | 5/78 | 1/78 |

### Turnover and distribution versus BASELINE_A (400 draws, pre-audit)

- identical lineups retained: **1 of 78** (1.3%) — 77 new, 77 dropped
- distinct captains: 14 -> 14; peak captain 13/78 = 16.7% -> 20/78 = 25.6%
- peak player exposure: 39/78 = 50.0% -> 39/78 = 50.0% (cap 50%)
- people used: 25 -> 21; entered ['Riley Nowakowski']; dropped ['Darnell Washington', 'Jaleel McLaughlin', 'Jimmy Horn Jr.', 'Mason Rudolph', 'Shedeur Sanders']
- salary BASE-A: min 33600 median 47000 max 49800 mean 45508, 0 at cap
- salary corrected: min 32500 median 49100 max 50000 mean 46295, 7 at cap

### Projection changes versus BASELINE_A: 9 players moved by >= 0.10 DK points

| Player | BASE-A | corrected | delta |
|---|--:|--:|--:|
| Deshaun Watson | 11.19 | 16.33 | +5.14 |
| Aaron Rodgers | 11.91 | 14.37 | +2.46 |
| Quinshon Judkins | 12.74 | 10.45 | -2.29 |
| Mason Rudolph | 1.75 | 0.06 | -1.69 |
| Jaylen Warren | 21.85 | 20.38 | -1.48 |
| Shedeur Sanders | 1.26 | 0.04 | -1.22 |
| Raheim Sanders | 4.84 | 4.35 | -0.50 |
| Travis Homer | 5.22 | 4.99 | -0.23 |
| Jaleel McLaughlin | 1.09 | 0.93 | -0.16 |

Every other player is unchanged, which is the point: the repair was scoped to the quarterback appearance gate and its mechanical consequences for club rushing allocation, not a general retune. Receivers barely move because receiver targets are allocated from the club target total, not from the quarterback's pass-attempt claim.

---

## 10. Item 8 answered: `REDISTRIBUTION_STUDY.json` exists, and it must NOT be wired

**It exists**, at `nfl/warehouse/REDISTRIBUTION_STUDY.json`, built by
`nfl/warehouse/redistribution_study.py`, alongside a `nfl/tools/redistribution.py` module.

**It is not in the projection path.** `proj_v1.py` contains **zero** references to redistribution.
The study and the tool are consumed only by `post_inactives_report.py` and
`post_inactives_state.py` — a reporting path. So the artifact's bare `teammate_absence = NOT_MODELLED`
is accurate about the projection.

**It cannot be validly wired, and the study says so itself**, in a field its own authors put there:

> `ASSOCIATION_NOT_CAUSE`: "a leader missing and a club trailing are correlated, so the pass-rate
> movement is an association. Nothing here identifies a causal effect."

> `NOT_ONE_FOR_ONE`: "the next man does NOT absorb the leader share. Read the mean against
> leader_share_when_present: the difference is what goes elsewhere, to deeper backs, to other
> positions, or is simply not run."

Using `to_next_man_r1` as a redistribution coefficient would be fitting a constant from
associational data and calling it causal — which is exactly what the governance rule on silent
constants forbids. **It stays NOT_MODELLED.** The limitation is quantified instead:

| Position | measure | leader share when present | next man absorbs | as % of vacated | n events |
|---|---|--:|--:|--:|--:|
| RB | carries | 0.45136 | 0.25385 (se 0.0205) | **56.2%** | 158 |
| WR | targets | 0.24652 | 0.06140 (se 0.0087) | 24.9% | 111 |
| TE | targets | 0.15812 | 0.06014 (se 0.0070) | 38.0% | 159 |

Club volume totals barely move on an absence — RB carries −0.28 (se 0.58), indistinguishable from
zero — so an absence reshuffles who gets the work rather than changing how much there is. That is
consistent with what `allocate_opportunity` does, and it is the part of the picture our proportional
renormalisation gets right.

### Does this say our Jaylen Warren 20.38 is too high? Suggestive, not conclusive — and I checked

Our allocation gives Warren **15.97 of PIT's 24.53 rush attempts, a 0.651 share**, against a
historical lead-back norm of **0.451 when his backup is present**. Homer 3.86, Nowakowski 0.95,
Nichols 0.10.

**But the study's frame does not match tonight's event.** `REDISTRIBUTION_STUDY` measures a *leader*
being absent and the next man stepping up. Rico Dowdle's `depth_rank` is **2** and Warren's is **1**,
so what happened tonight is a **rank-2 back being ruled out while the leader plays** — the opposite
direction. The `to_next_man_r1` coefficient therefore does **not** bound Warren, and I am not going to
use it as though it did.

What does carry over, and is worth stating: absorption is not one-for-one in any position measured,
so some of Dowdle's vacated carries should land on Homer and the deeper backs rather than
concentrating on the leader. A 0.651 share is high against the 0.451 norm, though a lead back whose
primary backup is out would legitimately sit above that norm. So this remains the **most likely place
tonight's board is over-concentrated**, the direction agrees with FC's 17.15, and it is not
demonstrated. Establishing it would need a study framed on rank-2 absences, which does not exist.

---

## 11. Two projection/simulation inconsistencies, exposed by retaining per-world stat lines

The simulator now keeps each world's stat line (`simulate_game(retain_stats=True)`, written to a
hashed numpy sidecar beside the draws). Comparing those worlds with the projection that fed them
found two separate inconsistencies.

### 11a. QB (and gadget) carries never reached the worlds — FIXED (`d85c1384`)

`showdown_draws._shares()` fed `carry_share` to running backs only. The projection had allocated
club carries across QB/RB/WR/TE; the simulator reallocated them to backs. Measured on W4: Deshaun
Watson drew **0.0 carries / 0.0 rush yards** against a 6.17 / 29.4 projection; Quinshon Judkins drew
13.85 DK against a 10.45 projection. One guard widened; Watson's worlds now carry 6.21 / 27.7,
Judkins 13.42, Warren 19.86 (from 20.41). The pinned W4 artifacts are untouched; this applies to the
next sealed slate as a declared treatment.

### 11b. The simulator draws its own club volume — OPEN, needs a ruling

With carries restored, QB draw means moved *above* projection (Watson 18.67 vs 16.33) because the
joint simulator draws club volume from its own market-response model, not the projection's
`team_volume` — and that surplus had been masking the missing rushing. Means over 2,000 worlds
against the projection's club totals:

| Club | pass attempts | carries | targets |
|---|--:|--:|--:|
| PIT | −2.8% | **+9.8%** | **+11.7%** |
| CLE | **+7.1%** | −0.8% | +1.1% |

The sanity gate validates the projection against its club totals; the optimizer ranks on the draws;
the two carry different club volumes. That is exactly the contradiction class the gate exists to
refuse — but refusing it blocks the pipeline on an unanswered design question, so for now it is
**measured on every run** (`football_sanity.measure_draws`, carried on the status board as
`draws_consistency`) rather than refused.

**Decision needed:** which club volume is authoritative?
- *Projection's `team_volume`* (recommended): it is what the gate validates and what the board shows;
  the simulator would centre its club draws on it and contribute only dispersion and joint
  structure. This is a model change to the simulator's volume layer → a declared candidate arm,
  compared on the row ledger, not a swap.
- *Simulator's own volume*: then the projection's club totals are not the model's, the gate is
  validating the wrong object, and the board's point projections should be the draw means.

Until ruled, the board carries both numbers and names the gap.

---

## 12. Pre-existing fence-suite failures, measured as unrelated to this work

Adding the `showdown_live` namespace and sealing tonight into it was followed by a runner pass over
the six suites that enumerate sealed artifacts. Four reported failures: `test_stat_contract` 13,
`test_p6_false_greens` 18, `test_sealed_corpus_census` 1, `test_draw_coherence` 1
(`test_xl1_shared_pass` 0, `test_qb_room_composition` 0).

**Attributed by A/B, not assumed.** With the Showdown seal directory moved aside (and its namespace
root therefore absent to `discover_all()`), `test_sealed_corpus_census` still fails 1 and
`test_p6_false_greens` still fails 18 — identical counts. `live_draw_files()`, which
`test_stat_contract` and `test_draw_coherence` enumerate through, walks `nfl/research/live` only; the
new namespace is a sibling directory it never visits. The runner log contains no reference to any
artifact introduced here. These four are pre-existing failures at HEAD and belong to the suite
classification work (tasks #58 / #105), not to this program. They are recorded here so the next
reader does not re-derive the attribution.

---

## 13. Owner ruling 2026-10-02: the projection is the expected-value centre of the simulator

**Built as a declared arm, not a swap.** `nfl/sim/game.py:simulate_game_centred` keeps the incumbent
simulator intact and adds, per club, two level offsets (plays intercept, pass-share intercept) solved
in three calibration passes so that the Monte Carlo means of pass attempts, carries and targets land on
the projection's `team_volume`. Nothing else moves: the regression slopes on implied points and
margin, both residual SDs, the share families, the touchdown and yardage machinery are the measured
values. Throwaways are now explicit per world, with a new exact identity
`pass_attempts == targets + throwaways` checked in every club-world; the throwaway rate is
`1 - proj_targets / proj_pass_attempts`, not a constant. `proj_plays` is deliberately NOT reconciled: it
counts snaps including sacks, penalties and kneels, which is a different quantity from pass+rush
attempts, and the artifact says so.

**The tolerance is error propagation, not a margin.** The reconciliation gap carries two independent
Monte Carlo errors, the final pass's mean and the offsets estimated on the last calibration pass, so
the tolerance is `3 x sd x sqrt(1/n_sims + 1/n_calib)`. The first version counted only the first term
and refused a correct run; that was a defect in the gate, fixed before anything was measured.

**The hard gate is armed only for the arm.** A draws artifact declaring `volume_centre.mode ==
PROJECTION` whose sidecar means fall outside that tolerance is refused by `football_sanity.measure_draws`
with `DRAWS_NOT_RECONCILED_TO_PROJECTION`, and `showdown_to_portfolio.run` refuses the run. The
incumbent arm is measured and reported, never refused, because for it the divergence is the finding
that motivated the ruling. `showdown_draws.py --volume-centre projection` selects the arm; the default
is the incumbent and the artifact records which ran.

**Tests** (`nfl/tests/test_volume_centre_arm.py`, 6/6): the incumbent arm is byte-identical with no
offsets; the centred arm reconciles within tolerance; every identity holds in every world including
the new one; dispersion of club pass attempts is unchanged (ratio 0.98 / 1.10 on the fixture);
within-world pass-share spread survives under a 13-point favourite and a 13-point underdog; an
incoherent centre (targets above attempts) is refused by name.

### 13.1 What reconciling exposed: a quarterback with five projected targets

Reconciling CLE's targets succeeded at the club level (28.77 simulated against 28.85) and failed at the
player level: the slate players summed to 23.7. The missing 5.04 targets per world belonged to
**Deshaun Watson**, to whom the projection had assigned 5.04 targets. The simulator gives quarterbacks
a zero target share, so in every joint world, in the delivered portfolio as much as in the arm, those
targets reached nobody.

**Mechanism, read from the code.** Each position's depth table is measured on ONE field
(`DEPTH_TABLE_FIELD`: QB on pass attempts, RB on carries, WR/TE on targets) and
`allocate_opportunity` read that one share as the prior for EVERY field. A quarterback's 0.95 share of
pass attempts therefore stood in as his share of club targets; normalised against the receivers'
genuine target shares it came to 0.42, his measured target claim was exactly zero, and the
"one side has no evidence, take half the other" rule turned a measured zero into 0.17 of the club's
targets. Systemic: nine of sixty main-slate quarterbacks in `DK_WEEK3_PROJ_V1.json` carried 4.4 to 5.7
targets (Burrow, Watson, Lawrence, Young, Allen, Ward, Willis, Mariota, Darnold), exactly the nine whose
target claim was 0.0 rather than a trace. Logged as DEFECT-QBTGT.

**Repair.** When the table's field differs from the field being allocated, the prior is the measured
group split for that field times the within-group concentration the table gives; when they match, the
table's share is the club share as before. `CROSS_FIELD_PRIOR_SCOPE` fixes where this applies, and the
reason it is scoped is the measurement in 13.2. The gate now refuses a quarterback above one projected
target a game without a recorded reason (`QB_TARGETS_ABOVE_CEILING_WITHOUT_REASON`; measured basis: the
quarterback group takes 0.05 per cent of club targets, about 0.02 a game) and bounds non-quarterback
pass attempts the same way (`NON_QB_PASS_ATTEMPTS_ABOVE_CEILING`). Both the delivered artifact and the
pre-repair baseline-A artifact are now refused on exactly the classes that describe them, and the test
that asserted "the delivered artifact passes" says so instead of being deleted.

**A false mechanism withdrawn.** `test_football_sanity` asserted that the baseline-A artifact's club
pass attempts did not reconcile *because* the capped starters' attempts left the club total. Measured:
the residual (CLE 0.247, PIT 0.515) is the ordinary trick-play mass on receivers' rows, present in every
artifact, which a quarterbacks-only sum under a 0.1 per cent tolerance reads as unreconciled; the week-3
slate "failed" eight clubs the same way. The gate now sums the pool the allocator keeps and bounds where
the attempts sit. The real consequence of the cap was on the quarterback rows themselves: Shedeur Sanders
4.00 and Mason Rudolph 4.26 attempts.

### 13.2 The repair measured on held-out weeks, and what it says

Three forward-chained runs on the same 28 held-out weeks (seasons 2024 and 2025, identical week sets
asserted), paired by week with week-blocked SEs, in
`nfl/research/depth_prior_repair/PAIRED_DEPTH_PRIOR_REPAIR.json`. Exploratory, because the forward
chain is development data.

| Arm 1.0 | legacy | QB_ONLY | ALL |
|---|---|---|---|
| MAE | 5.861 | 5.938 (+0.076, SE 0.010) | 5.943 (+0.082, SE 0.010) |
| Spearman | 0.5166 | 0.5145 (−0.002, SE 0.001) | 0.5147 (−0.002, SE 0.001) |
| level ratio | 0.753 | 0.802 | 0.805 |
| QB MAE | 7.659 | 7.658 | 7.660 |
| WR MAE / level | 6.126 / 0.704 | 6.230 / 0.778 | 6.231 / 0.778 |
| TE MAE / level | 4.428 / 0.786 | 4.537 / 0.879 | 4.535 / 0.878 |
| RB MAE / level | 5.795 / 0.759 | 5.841 / 0.788 | 5.861 / 0.799 |

**Read that honestly.** Removing an impossible allocation made held-out absolute error *worse* at every
non-quarterback position, by more than two SEs, while the level ratio moved from about 0.70 toward 0.78
and ranking stayed flat. Quarterback error did not move. The arithmetic is simple: the ghost targets
were roughly a sixth of a club's targets, so removing them scales every other receiver on the club up by
about a fifth. That moves the level toward honest and lands mass on low-scoring rows too. **The legacy
ghost was acting as an undeclared shrinkage on receiver projections**, which is a fitted constant by
accident, and the project's rule on fitted constants is that they are logged as bugs. So:

- The quarterback repair ships (`CROSS_FIELD_PRIOR_SCOPE = 'QB_ONLY'`): a passer is not a receiving
  target, and the gate would refuse the artifact otherwise.
- The wider repair of backs' target priors and receivers' carry priors (`'ALL'`) is a declared
  candidate arm, not promoted: its form is right and its score is not better.
- The receiver mass the repair exposed is logged as DEFECT-RECVMASS (task #112): the next question is
  where the extra error sits (rows with zero actual, depth rank), and the candidate repairs are the
  appearance and zero-mass programs (B5, B8), not a return to the impossible allocation.
- **Escalated to the owner**, because it changes what counts as better: a correctness repair that
  worsens MAE on development data while improving level calibration. My decision is reversible in one
  line (`LEGACY_CROSS_FIELD_PRIOR`, measurement only), and nothing here is validation.

### 13.3 Delivered artifacts preserved; what the system now produces for PIT@CLE

The delivered projection and draws (`SHOWDOWN_TONIGHT_PROJ.json`, `SHOWDOWN_TONIGHT_DRAWS.json`) are
unchanged and sealed (retro seal `061b8b3bb7b651fa`, `prospective_evidence False`). Two things about
them are now on the record. The delivered draws were written at 23:39Z on 2026-10-01 and the
quarterback carry-share fix landed at 02:54Z, so **the delivered portfolio ran on draws in which
Watson carried 0.0 rushes** (the rerun under current code differs on 43 of 45 players for that reason).
And the delivered projection is refused by the gate on Watson's 5.04 targets.

The post-game, descriptive rebuild under the repaired allocator is
`SHOWDOWN_TONIGHT_PROJ_QBTGT_FIXED.json` (gate: PASS, identities 0 failures). Watson 5.04 → 0.01 targets;
the five targets return to Fannin (+1.26), Concepcion (+1.34), Boston (+0.77), Judkins (+0.53), Sanders,
Jeudy. The main-slate `DK_WEEK3_PROJ_V1.json` was likewise regenerated (delivered copy preserved in the
sealed run `DK_NFL_WEEK3_2026__20260928T233618Z__56a24b3d29d8`, sha 323bdf96…), and
`sunday.run()` now carries the football-sanity step and passes it.

### 13.4 Capture surface, done without waiting

`nfl-t90.yml` and `nfl-status.yml` regenerated for 2026 week 4 from snapshot `9d3644487c6021f2`
(the pins were September's). The drift test's "upcoming week" now also requires the week's final
kickoff to be ahead on the wall clock, because the snapshot stopped recording results after week 2 and
the old derivation pointed at week 3 eight days after it was played. `nfl-availability.yml` and the
status generator checked out the default branch and pushed `HEAD:main`; both now check out and push
`capture-prod` (D24-R2). The definitions still have to live on the default branch, which this branch is
not: **they take effect only once merged.**
