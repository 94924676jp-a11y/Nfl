# Pre-registration: SEL-1, a fill-repair selector (stability before relaxation)

- **Written:** 2026-10-13, before the challenger was run on any slate. The commit time is authoritative.
- **Status:** DIAGNOSTIC on the frozen slates (BUF@LAR W5, TB@DAL W5, ATL@NO W4). Their outcomes are known.
  **Confirmation is prospective, on week 6 onward.** The production default stays unchanged until the owner promotes.

## The defect (from `RESULT_PORT_D3_AND_WR1OUT_RB2.md`, correction `47e14110`)

`showdown_portfolio.ladder` relaxes to looser caps whenever the **greedy** `select` comes up short:

- 19 of 20, or 140 of 150, at level 0;
- even though a legal portfolio may exist at that level.

So the cap level, and with it the objective, jumps with the pool's composition.

## The challenger SEL-1 (`NFL_SHOWDOWN_SELECTOR=FILL_REPAIR_V1`, opt-in; default unchanged)

At each rung, when greedy is short:

1. **Exchange repair.** For each chosen lineup j, in increasing order of its marginal objective contribution: remove
   j, then re-fill greedily (the same gain order, caps, overlap and exclusions).
2. If any exchange completes the portfolio, take the completed portfolio with the highest objective, and stay at this
   rung.
3. **Only if no exchange completes it**, go to the next rung, as now.

The swap polish then runs unchanged. No new constant; the exchange budget is all chosen lineups, once each.

## Test design (fixed now)

**Same pool, same policy for both selectors.**

- The production candidate pool of each frozen slate's final scenario.
- The same GLOBAL overlap policy, caps, ladder and polish.

**Held-out worlds, not new simulations.** Each slate's worlds are split by parity:

- **Selection worlds S:** even indices.
- **Evaluation worlds H:** odd indices.
- `hit` is computed on S against the pool's own per-world best, and the portfolios are scored on H.

**Metrics per contest, on H:**

- the objective E[min(depth, m)], where m is the selector's own;
- coverage;
- the relaxation level reached;
- runtime.

**Stability.** Each selector on 5 random 90% subsamples of the pool (seeds 1-5). The spread (max − min) of the H
objective and of the relaxation level, per contest.

**Pre-declared reading.** SEL-1 is **better** on a slate and contest if both hold:

1. its H objective is at least the default's on the full pool;
2. its H-objective spread across subsamples is no larger than the default's.

The prospective gate (W6 onward) re-uses exactly these metrics.
