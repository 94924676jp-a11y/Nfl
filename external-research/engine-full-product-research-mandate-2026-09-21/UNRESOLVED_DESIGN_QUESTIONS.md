# Unresolved design questions after Revision 3

These are open. None is resolved by the code in this folder, and none may be
treated as settled because a test passes around it.

## Q-1. Scope verdicts are per release; blockers are per entity

`WEATHER_PROXY:game1` names one game. The scope F1 speaks for the whole
release, so the engine blocks F1 and records `game1` in `blocked_entities`.
That is conservative and it is coarse: a thirteen-game slate with one
unproven weather run loses all thirteen.

The real fix is a verdict per (scope, entity) — per game for F1 and F4, per
player-game for F2 and F3, per market for P1, per slate for D. The engine
already carries `Context` and `GateResult` qualifiers to support it; what is
missing is the entity enumeration for a release and a decision about what the
release-level rollup then means. **Until that exists, a per-entity blocker
over-blocks, and the coarse answer is the safe direction.**

## Q-2. `CALIBRATION_INFEASIBLE` on any family blocks every weighted-worlds consumer

Block XIX fits ONE weight vector per release by raking across families. If one
family cannot be made feasible under the weight-ratio cap, the vector that was
fit is not the vector that satisfies the targets — so every consumer of it is
affected, which is why DFS is blocked here.

What is not established: whether a per-family infeasibility can be isolated by
refitting without that family's targets, and what that does to the other
families' calibration. If it can, DFS should be blocked only when the family
it actually consumes is infeasible. **Measurement needed, not argument.**

## Q-3. The fitted weight vector's own uncertainty is not in any interval

`weighted_nested_mc` conditions on the weights. They are fitted by raking to
targets estimated forward-chain from past PIT records, so the vector is an
estimate with sampling error, and the interval understates by an unknown
amount. Every result carries `weights_treated_as_fixed: True` so nothing can
mistake one for the other.

Proposed, not done: block-bootstrap the raking fit over calibration origins
clustered by week, refit per replicate, and propagate. Registered as backlog
**T-35**. Until it runs, the size of the understatement is unknown — it is not
known to be small.

## Q-4. The self-normalised block estimator is biased at finite M

`mu_hat_w = sum(w Y)/sum(w)` is a ratio, so it carries O(1/M) bias and the
linearised variance is first-order. With M in the tens that is probably minor
and "probably" is doing real work in that sentence. A jackknife over parameter
blocks would both de-bias and give a variance estimate that does not rely on
the linearisation. Not implemented.

## Q-5. An SGP is not carried by its legs, and its own comparison does not exist yet

Revision 3 makes P2 depend on its selected legs rather than on every prop
family. It also declines to let leg-level market results establish the joint:
correlation between legs is the entire reason the product exists, so P2
requires an SGP-level `G-XX-2` result keyed to the ticket.

**No such result can be produced today.** It needs captured SGP prices and a
settled ledger of SGP outcomes, and the project has neither. P2 will read
`RESEARCH_ONLY` with `GATE_NOT_EVALUATED:G-XX-2` until that exists, which is
the honest state.

## Q-6. Showdown ownership, field and duplication have no labels

`D3.showdown`, `D4.showdown` and `D5.showdown` now exist as a dependency path
separate from Classic. The gates they inherit (G-XXV-1, G-XXVI-1, G-XXVII-1,
G-XXVIII-1) are all calibrated against contest CSV labels, and the Showdown
contest label set available to this project is not characterised. The path is
correct; the evidence to evaluate it is not established.

## Q-7. Component-inclusion gates are release-level and attach to every scope

`G-XII-1` (matchup) and `G-XIII-1` (coaching) are reported as
`COMPONENT_NOT_INCLUDED` display codes on every scope, because the matrix says
a failed inclusion does not fail a scope. A component actually belongs to
specific blocks, so the exclusion should attach only to the scopes that would
have consumed it. The matrix's `component` column is the obvious key; the
mapping from component to consuming scope is not declared anywhere yet.

## Q-8. `INSUFFICIENT_DATA` and `NOT_EVALUATED` are treated alike

Both block, with distinct reason codes. Whether they should differ in the UX —
one says "we looked and there is not enough", the other says "nobody looked" —
is a product decision that has not been made.
