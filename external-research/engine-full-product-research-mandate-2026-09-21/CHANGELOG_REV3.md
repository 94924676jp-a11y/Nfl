# Revision 3: verdict-engine correction pass

Date 2026-09-21. Status unchanged: **CANDIDATE_NOT_ACCEPTED_BASELINE /
V2 NOT YET EARNED**. Nothing here promotes the model, evaluates a real gate,
changes governance or declares readiness. Synthetic gate statuses are not
deployment-gate evidence.

## Repository verification, first, because it changes what this document is

The instruction was to verify commits `0b63561` (revision) and `ae00937`
(change log) against the checkout before doing anything else.

**Neither commit exists in this checkout, and neither did the directory.**

```
$ git cat-file -t 0b63561   -> fatal: Not a valid object name
$ git cat-file -t ae00937   -> fatal: Not a valid object name
$ ls external-research/engine-full-product-research-mandate-2026-09-21/
  -> No such file or directory
```

Revision 2 was produced in a different tree. What is corrected here is the
**uploaded artifacts**, which were written into that path so the work has
somewhere to live; the Revision 2 engine is preserved verbatim beside the
corrected one as `verdict_engine_rev2.py` so the four failures stay
reproducible. The claimed commits in `CHANGELOG.md` are therefore unverified
from here and should not be cited as if they were.

## Reproduction, before any fix

All four reported failures reproduced exactly against `verdict_engine_rev2.py`
on the shipped CSVs:

| Case | Reported | Reproduced |
|---|---|---|
| `WEATHER_PROXY:game1` | F1 RESEARCH_ONLY, dependents DEPLOYABLE | F1 RESEARCH_ONLY; F2, F3, P1.*, D1, D5 all DEPLOYABLE |
| `ROUTES_PROXY:player1` | F2 blocked, dependents DEPLOYABLE | F2 RESEARCH_ONLY; F3, P1.*, D1, D5 all DEPLOYABLE |
| `CALIBRATION_INFEASIBLE:receiving_yards` | props blocked, DFS DEPLOYABLE | D1, D2, D5 DEPLOYABLE |
| `G-X-1 = PASS_INCLUDES_ZERO` | F1 DEPLOYABLE | F1, F2, F3, D1 all DEPLOYABLE |

**One additional defect found while reproducing case 3, not in the report.**
`CALIBRATION_INFEASIBLE:receiving_yards` also blocked `P1.rushing_yards` and
`P1.passing_yards`. Matching was by code prefix with the entity discarded, so
the same defect under-blocked DFS and over-blocked every unrelated prop family
at once. Both halves are fixed and both have regressions.

## Finding-by-finding resolution

### 1 and 2 — upstream blockers did not propagate. AGREED, FIXED.

Cause: `evaluate_scope` matched release codes against `scope.blocking_reason_codes`
— the scope's own list — and nothing else. `WEATHER_PROXY` appears only in
F1's list. Gates propagated transitively through `transitive_gates`; reason
codes did not.

Fix: `evaluate_release` is now two passes. The second walks
`dependency_closure` and demotes any scope resting on one that is not
DEPLOYABLE, carrying `UPSTREAM_NOT_DEPLOYABLE:<scope>:<root cause>` and the
affected entities with it. `_root_cause` walks to the first scope that
actually failed, so a marker names the real cause rather than nesting each hop
inside the next or degrading to `RESEARCH_ONLY`.

**Direction is one-way, and that is what preserves the identity separation.**
Upstream invalidity flows down; nothing flows up. `test_routes_proxy_...`
asserts F1 stays DEPLOYABLE under a blocked F2, and
`test_identity_failure_blocks_dfs_but_not_football` (supplied, unchanged) still
passes.

### 3 — calibration failure missed its consumers and hit non-consumers. AGREED, FIXED.

Fix, under-blocking: `Scope.consumes_weighted_worlds` is **derived** from
requiring `G-XVIII-1`, the gate asserting that props, SGP and DFS share one
world id set and one weight hash. A scope required to satisfy it reads those
weights by definition. Such scopes inherit `G-XIX-1..4` and are bitten by
`CALIBRATION_INFEASIBLE`. Derived rather than hand-listed so a new consumer
cannot be forgotten; the CSV is reconciled to match.

Fix, over-blocking: `FAMILY_SCOPED_CODES` carries the entity. The code bites
the named family, and any consumer of the shared weights, and nothing else.

### 4 — statuses were not validated by gate class. AGREED, FIXED.

Cause: the loop reacted to `FAIL`, `NOT_EVALUATED`, `INSUFFICIENT_DATA`; every
other string fell through as clearing.

Fix: `CLASS_PERMITTED` and `CLASS_CLEARING`. A status outside its class's
domain yields `GATE_STATUS_INVALID_FOR_CLASS:<gate>:<class>:<status>` — named
a category error rather than a failure, because `PASS_INCLUDES_ZERO` describes
an interval straddling zero and an exactness check does not have one. Exact,
provenance, statistical and diagnostic gates clear on `PASS` only; market
gates clear on `PASS_FAVORABLE` only.

`COMPONENT_INCLUSION` gates never fail a scope — the matrix's own pass rule
says so — but are now reported as `COMPONENT_NOT_INCLUDED` display codes, which
in Revision 2 were unreachable code.

### 5 — gate results keyed by gate ID alone. AGREED, FIXED.

`GateResult` carries `release_id`, `scope_id`, `family`, `game_id`,
`player_id`, `market_id`. A result matches a `Context` only when every
qualifier it sets agrees; the most specific applicable result wins; a tie at
equal specificity with different statuses yields `AMBIGUOUS_GATE_RESULT` and
clears nothing.

The legacy `{gate_id: status}` mapping still works — the nine supplied tests
pass unchanged — but an unscoped result on a per-entity gate always emits
`GATE_RESULT_UNSCOPED`, as a display code by default and as a **blocking**
code under `strict_scoping=True`.

### 6 — market outperformance confused with a betting edge. AGREED, SEPARATED.

`G-XX-2` stays what it is: a family-level, aggregate, historical proper-score
comparison against the de-vig market. A statement about the model.

Offer-level EV moves to `offer_edge.py`, downstream, with its own verdict
domain (`EV_POSITIVE` / `EV_INCLUDES_ZERO` / `EV_NEGATIVE`). It takes the
price, the line, the side, the settlement and push rule, the observation
timestamp and a staleness bound, and its EV interval inherits the
probability's Monte Carlo SE. It takes the scope verdict as an **input** and
can never be an output: an offer on a non-DEPLOYABLE scope is refused.

`test_offer_edge_...` pins the separation as a property: a DEPLOYABLE family
at a marginal price still returns `EV_INCLUDES_ZERO`.

**No sportsbook quantity flows upstream.** Price, line, hold and EV appear in
that module and nowhere else.

### 7 — Block XV double-counts. AGREED, DERIVED, FIXED, VALIDATED.

For the balanced nested model `Y_mkn = mu + a_m + b_mk + e_mkn`, the
parameter-level mean has

    Var(Y_bar_m) = sigma_M^2 + sigma_K^2/K + sigma_N^2/(K N),

and since the M parameter draws are iid,

    Var(Y_bar) = Var(Y_bar_m)/M,   which s_M^2/M estimates without bias.

The lower-level noise is not missing from the first term; it is inside it.
Adding the other two terms gives

    E[Var_hat_rev2] = sigma_M^2/M + 2 sigma_K^2/(M K) + 3 sigma_N^2/(M K N),

so the scenario component is counted **twice** and the world component **three
times**. Synthetic validation at 4,000 replicates: a scenario-only design
inflates **1.991x** and a world-only design **2.995x**, against the predicted
exactly 2 and 3.

The packet calls `s_M^2/M` "the conservative estimator". It is not
conservative; it is the exact one, and the "finer decomposition" preferred
over it is the inflated one. Consequence if left: `G-XV-2` fails releases that
are fine, and the T-34 draw-count controller buys worlds it does not need.

Also separated: **predictive variance** (how much the forecast spreads,
`G-XV-1`) from **Monte Carlo variance** (how precisely its mean was located,
`G-XV-2`/`G-XV-3`). Conflating them is the underlying error.

Post-reweighting: `weighted_nested_mc` uses the self-normalised block
estimator, collapsing exactly to `s_M^2/M` at equal weights, and reports
`ESS = (sum w)^2 / sum(w^2)` for `G-XIX-3`. It is **conditional on the fitted
weight vector** and says so on every result — see Q-3.

### 8 — SGP legs and the Showdown path. AGREED, FIXED.

`P1.*` now resolves to the **selected legs** passed as `sgp_legs`. With none
declared, P2 returns `SGP_LEGS_NOT_DECLARED` rather than silently depending on
all thirteen families.

**And the engine declines to let legs carry the joint.** P2 requires an
SGP-level `G-XX-2` keyed to the ticket, because correlation between legs is
the entire reason the product exists. My first regression test asserted P2
should be DEPLOYABLE off its legs; the engine disagreed and the engine was
right, so the test was corrected, not the engine. See Q-5 — no such result can
be produced today.

Showdown: `D3.showdown`, `D4.showdown`, `D5.showdown` descend from D2. In
Revision 2 the only contest-simulation path descended from D1, so Showdown had
none. A Showdown-only failure (`G-XXX-1`) now reaches the Showdown chain and
not Classic.

## Files changed

| File | Change |
|---|---|
| `verdict_engine.py` | corrected engine (findings 1–5, 8) |
| `verdict_engine_rev2.py` | Revision 2 preserved verbatim, so the failures stay reproducible |
| `test_verdict_engine.py` | the nine supplied tests, **unchanged** |
| `test_verdict_engine_rev3.py` | new, 261 checks |
| `nested_mc.py` | new, corrected Block XV (finding 7) |
| `test_nested_mc.py` | new, 27 checks incl. the 2x/3x validation |
| `offer_edge.py` | new, offer-level EV (finding 6) |
| `scope_gate_dependencies.csv` | 27 -> 30 scopes; Showdown chain; `CALIBRATION_INFEASIBLE` declared on D scopes |
| `gate_matrix.csv` | G-XV-1/2/3, G-XIX-3, G-XX-2 statistics corrected |
| `implementation_backlog.csv` | 34 -> 36 tasks; T-34 corrected; T-35, T-36 added |
| `UNRESOLVED_DESIGN_QUESTIONS.md` | new, Q-1 to Q-8 |

## Tests

| Suite | Result |
|---|---|
| `test_verdict_engine.py` (supplied, unchanged) | 9 / 9 pass |
| `test_verdict_engine_rev3.py` | 261 / 261 pass |
| `test_nested_mc.py` | 27 / 27 pass |

The supplied suite was deliberately not modified. A suite rewritten to
accommodate a fix is not evidence the fix was correct.
