# Results: PORT-D3 candidate recall (BUF@LAR W5, diagnostic) and the WR1-out / RB2-tail history study

- **Pre-registrations:** `PREREG_PORT_D3_CANDIDATE_RECALL.md` (`b1945cd5`) and `PREREG_WR1_OUT_AND_RB2_TAILS.md`
  (`d8a7d5eb`).
- **Code:** `9291223e`.
- **Status:** **DIAGNOSTIC.** The W5 outcome has been inspected, so nothing here confirms a challenger. Every number
  below comes from model worlds or from 2021-2025 history; **owner contest results are kept out of this repository.**

## 1. PORT-D3: candidate recall on the frozen pre-lock worlds

**Universe U** (brute force, `d3_brute.py`):

- 31 eligible players; **4,299,598 legal lineups** (CPT 1.5×, cap $50,000, both clubs).
- **The production solver's world optimum equals the brute-force optimum in all 2,000 worlds** (largest difference
  3e-5). The solver is correct.

**Persistence h(L)** = the number of primary worlds in which L is within 10% of the exact world optimum. The production
pool has 5,946 lineups (3,376 from the generator, 2,570 forced-captain); its h quantiles are p10 0, p25 3, p50 13, p75 33,
p90 60.

| lineups of U with h ≥ … | n in U | in pool | **recall** |
|---|---|---|---|
| 13 (pool median) | 15,540 | 3,012 | **19.4%** |
| 33 (pool p75) | 3,839 | 1,523 | 39.7% |
| 60 (pool p90) | 972 | 612 | 63.0% |
| top 5,946 by h | 5,946 | 1,940 | 32.6% |

- **The miss is not RB-specific.** Recall (h ≥ 13) is 18.4% / 20.7% / 18.9% / 15.3% for lineups with 0 / 1 / 2 / 3 RBs.
- **It is lowest for QB captains:** Allen 10.9%, Stafford 13.0%; against Adams 15.6% and Kyren Williams 18.0%.
- **Mechanism** (`showdown_to_portfolio.near_optimal_candidates`, lines 464-485). Each solver round contributes only
  the **single best lineup per world** under its constraints (captains forbidden, or a core player dropped).
  - A lineup that is consistently near the top without being the single best in some constrained world is never
    generated.
  - The forced-captain step adds 2,570 lineups, many with h = 0.

**Stage attribution** (`d3_stage.py`, `d3_eval.py`):

- **The same selector throughout:** `build_contests` with the same caps, ladder, polish and GLOBAL overlap.
- **The arms:**
  - **A:** the production pool;
  - **B:** the top 5,946 lineups of U by h (same size);
  - **C:** the union of A and B (9,952 lineups).
- **Scoring:** on the **independent seed + 1 panel** against its exact optimum. Paired bootstrap over its 2,000 worlds.
  These intervals are over worlds of **one** model and slate, not over games.

| contest (objective) | A | B − A [95%] | C − A [95%] |
|---|---|---|---|
| 150-max coverage (m = 1) | 0.952 | **+0.0115 [+0.001, +0.0215]** | +0.0025 [−0.007, +0.0115] |
| $10K 20, E[min(depth, 2)] | 1.0325 | −0.0175 [−0.045, +0.0085] | **−0.1485 [−0.1735, −0.1235]** |
| $5K 20, E[min(depth, 2)] | 0.985 | +0.0095 [−0.017, +0.0345] | **+0.057 [+0.0345, +0.0805]** |

- **On the primary worlds (in-sample)** the production pool is equal or best. That is the selection worlds rewarding
  their own optima.
- **Arm B** needed relaxation level 2 in the 150 (player cap 98 of 150): a persistence-only pool is more concentrated.
- **Selector runtime:** 302 s (B) and 617 s (C), against about 300 s in production.

**Reading.**

1. **Recall is a VERIFIED defect.** Only 19% of lineups at or above the pool's own median persistence were ever offered
   to the selector.
2. **Its measured cost on this slate's own independent worlds is small:** +1.2 points of 150-max coverage from a
   same-size enriched pool, and nothing clear in the 20s.
3. **Selector instability is a SEPARATE, larger effect.**
   - Enlarging the pool (C) moved the two 20-entry objectives by −15 and +6 points.
   - Under GLOBAL exclusion the 20s depend on which lineups the 150 took, and the greedy, polished selection is
     order-sensitive.
   - Candidate failure and selector failure must be fixed and tested separately; a bigger pool alone is not a fix.
4. **HINDSIGHT (labelled):** the actual winning lineup had h = 16 and ranks **11,202nd** of 4.3 million by
   persistence. A same-size pool built on persistence would not have contained it either.

## 2. H1: where an absent WR1's volume goes (2021-2025)

**Population.** 56 cases in 36 team-seasons. The leader is a WR with at least 20% of team targets and at least 3 prior
games, has final status Out, and has no row in the game.

**Comparison.** Actual minus the proportional rule (each remaining player's share ÷ (1 − the leader's share)), clustered
by team-season.

| measure | mean | 95% interval |
|---|---|---|
| remaining **WR** target share | **+6.9 points** | [+4.1, +9.6] |
| **TE** target share | **−3.0 points** | [−6.0, −0.3] |
| **RB** target share | **−3.9 points** | [−5.7, −1.8] |
| team targets against baseline | −1.3 | [−2.9, +0.2] |
| team carries against baseline | +1.2 | [−0.4, +2.6] |

**Reading.** The proportional rule **under-allocates to the other WRs and over-allocates to TEs and RBs** when a WR1 is
out. The team's pass / run mix barely moves.

- The postmortem hypothesis "the volume went to the run game" is **not supported** as a general rule.
- In W5 the engine's Moore variant sent most of his share to the WRs (Coleman, Dortch), which is the historically
  supported direction.
- **Kincaid's projection was already about 15.2 with Moore active.** His miss is a base-projection question, not a
  redistribution one.

## 3. H2: backup-RB upper tails

| RB2 (season-to-date carries rank 2), RB1 played | n | p50 | p90 | p95 | p99 | share ≥ 3 × own mean |
|---|---|---|---|---|---|---|
| all | 1,862 | 3.5 | 14.7 | 19.6 | 27.7 | **4.0%** |
| RB3 Out | 50 | 4.0 | 12.4 | 14.9 | 17.7 | 4.0% |

**Engine, W5 final worlds**, share ≥ 3 × own simulated mean:

| player | simulated mean | share |
|---|---|---|
| Corum | 4.0 | **4.25%** |
| Ty Johnson | 4.9 | **3.1%** |

**Reading.** The engine's RB2 tail **shape relative to the mean matches history.** The "backup tails are too thin" claim
is **not supported**. Whether Corum's *mean* was too low is a separate question (ours 4.0, the vendor's 7.3), and it
needs his 2026 role data, not one game.

## 4. Defect register update

| id | status | evidence |
|---|---|---|
| **PORT-D3** candidate recall | **VERIFIED** | 19.4% recall at the pool median; a small out-of-sample cost on W5 worlds |
| **PORT-D4** selector instability under pool enlargement / GLOBAL exclusion | **VERIFIED (new)** | arm C's 20s moved −15 / +6 points on independent worlds |
| ALLOC-D1 proportional absent-WR rule | **VERIFIED direction, for the simple rule.** The engine's own blend must be tested on the same 56 cases. | H1 |
| RB2 tail shape | **NOT a defect on current evidence** | H2 |
| PROJ-D-TE-CARRIES, ECW-D-DST-PA, receiver spread C2 FAIL, QB / DST conditioning | unchanged, open | — |

## CORRECTION (2026-10-13 15:25 UTC): the stage attribution in section 1 is confounded by the relaxation ladder

The arms were **not built at the same cap level**. From each audit's `relaxation_log`:

| arm | 150-max | $10K 20 | $5K 20 |
|---|---|---|---|
| A (production) | level 0 (player 75 / 150, overlap 4) | level 2 (13 / 20) | level 2 |
| B (enriched, same size) | **level 2** (player 98 / 150, overlap 5) | level 2 | level 2 |
| C (union) | level 0 | **level 1** (10 / 20) | level 2 |

- **"B − A = +0.0115 in the 150" is CONFOUNDED.** B selected under looser caps. It is withdrawn as evidence that the
  enriched pool helps.
- **"C − A = −0.1485 in the $10K" is largely the stricter level-1 caps**, not pool quality. It is withdrawn as a
  measure of selector instability *at fixed policy*.
- **What remains VERIFIED:**
  - candidate recall (19.4% at the pool median);
  - solver exactness.
- **What replaces PORT-D4: the ladder is triggered by greedy fill failure, not by infeasibility.**
  - Every relaxation recorded here followed a greedy fill **1 to 10 lineups short** (19 of 20, 18 of 20, 140 of 150).
  - A greedy shortfall does not show that no legal portfolio exists at the stricter level.
  - So the cap level, and with it the objective, jumps with the pool's composition.
- **That is the instability.** The fix to test is a fill-repair at each rung before relaxing
  (`PREREG_SEL1_FILL_REPAIR.md`). The pool comparison must be re-run at **fixed rungs**.
