# Pre-registration: CG-1, the candidate generator at a fixed pool size, a fixed rung and disjoint worlds

- **Written:** 2026-10-13, before the CG-1 harness exists and before any CG-1 number has been computed. The commit time
  is authoritative.
- **Ledger:** CAND-D1 (recall 19.4% at the pool-median persistence) and CAND-D2 (candidates are generated from, and
  selected on, the same worlds). Queue item ENG-015.
- **Status:**
  - The frozen W4/W5 slates (ATL@NO, TB@DAL, BUF@LAR) are **DIAGNOSTIC**: model worlds only, no realised outcome used.
  - **Confirmation is prospective, on W6 and later Showdown slates.**
  - Nothing is promoted without the owner.

## Question

At an **identical pool size, selector, rung and objective**, does a persistence-ranked generator built on generation
worlds give a better held-out portfolio than the production generator built on the **same** generation worlds?

## Worlds: three disjoint thirds of each slate's frozen panel, by world index mod 3

| set | indices | used for |
|---|---|---|
| G (generation) | 0 mod 3 | building the candidates |
| S (selection) | 1 mod 3 | `hit` and the selector |
| H (evaluation) | 2 mod 3 | scoring only |

No candidate, threshold or tie-break may read S or H during generation, and no selection step may read H. This removes
the leak recorded in CAND-D2 and in Amendment 1 of `PREREG_SEL2_PROSPECTIVE_W6.md`.

## Arms (identical pool size N)

**A, the incumbent.**

- `showdown_to_portfolio.near_optimal_candidates` plus `showdown_portfolio.forced_captain_candidates`, called with the
  draws restricted to G.
- N = |A| after deduplication.

**B, the challenger.**

- The N legal lineups of the exhaustive universe U with the highest persistence h_G(L), where h_G(L) is the number of G
  worlds in which L is within 10% (`NEAR_OPTIMAL_LOSS_BAND`, the production constant) of the G-world exact optimum.
- Ties are broken by mean G score, then by the lineup key.
- U is the existing PORT-D3 enumerator (`port_d3/d3_brute.py`: CPT 1.5×, cap 50,000, both clubs).

**C, union control.**

- A ∪ B, truncated to N by the same h_G order.
- This separates "a different pool" from "a bigger pool".

## Selector, held fixed

- For every contest, each built **separately** (no cross-contest exclusion, so exclusion coupling cannot enter):
  - `NFL_SHOWDOWN_SELECTOR=FIXED_POLICY_V1` for 3 ≤ n < 100, which is level 2 by the owner's policy;
  - level 0 only for the 150-entry contest, with no relaxation.
- A contest that cannot fill at its rung is recorded `POLICY_UNFILLABLE` for that arm. The arm loses that contest; it is
  never re-run at a looser rung.
- Objective: E[min(depth, m)] for the 20s, coverage for the 150, as in production.
- Paired comparisons are made only where both arms ran with the same m.

## Compute budget (declared operational constant)

- Generation wall-clock is recorded per arm.
- A challenger arm whose generation exceeds **10 minutes per slate** on this machine is recorded `OVER_BUDGET` and fails
  that slate, whatever its objective.
- This is an operational ceiling for a pre-lock rebuild, not a fitted value.

## Metrics, per slate and contest

1. The H objective, with the paired difference B − A and C − A.
2. Recall of H-persistent lineups at h_H ≥ the pool-median h_H, per arm. This is diagnostic only.
3. The relaxation level. It must equal the declared rung, otherwise the result is `UNFILLABLE`.
4. Generation and selection runtime.
5. Violations from an independent checker (the SEL-2 paired harness's checker).

## Decision rule

**Hard gates:** any failure on any slate fails CG-1 for promotion.

- zero checker violations;
- no `OVER_BUDGET`;
- identical N between the arms.

**Diagnostic reading (W4/W5).** Reported per contest. No pass or fail is drawn from it.

**Prospective reading (W6 onward).**

- B is **promote-eligible** if the one-sided exact sign test of (B − A) over non-tied contests reaches p ≤ 0.05. That
  requires at least 5 of 5, or 6 of 7, and so on.
- C must not beat B by the same test; otherwise the gain is "union", not "persistence".
- There is **one analysis**, when the number of non-tied contests reaches 6. If that has not happened by the end of W10,
  the result is INCONCLUSIVE.

## What this does not test

- Payout, ROI or duplication: there is no lawful field or prize model (FIELD-D1).
- Classic, where full enumeration is not tractable; that needs bounds, per the mandate.
- Whether a winning lineup would have been included. Monday's winner (h = 16, ranked 11,202nd) is not used, and no
  threshold is chosen by looking at it.
