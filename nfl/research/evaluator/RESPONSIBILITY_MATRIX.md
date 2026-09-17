# Evaluator responsibility matrix, and the canonicalisation plan

Both modules read at HEAD `340d581`. Every cell below is what the source does,
not what its name suggests.

| capability | `nfl/product/evaluator.py` (325 ln, **WIRED**) | `nfl/production/evaluator.py` (mine, test-only) | duplicate / conflict | canonical owner |
|---|---|---|---|---|
| **CRPS** | `crps(x, y)` — exact empirical, sorted-sample form | **absent** — `SCORERS` holds brier and log_loss only | none today; **would become the 13th private CRPS if I add one** | **product** |
| **Brier** | absent | `brier(y, p)` with full input validation | none | **production** |
| **log loss** | absent | `log_loss(y, p)` → `(score, n_clipped)`, `LOG_EPS = 1e-6` declared | none | **production** |
| **PIT** | `pit(x, y)` — non-randomised, returns `F_below`, `F_at_or_below`, `mid_pit`, `p_mass_at_actual` | absent | none | **product** — and its refusal to emit one number for a discrete forecast is the right call |
| **interval coverage** | `score_metric` → per-row `covered` per level; `summarise` → `coverage_pct` | `interval_coverage(draws, y, levels)` → empirical vs nominal | **DUPLICATE.** Same four `LEVELS = (0.50, 0.80, 0.90, 0.95)`, arrived at independently | **product** for postgame rows; production's form is the panel-level one |
| **sharpness** | absent | `sharpness(draws, levels)` — needs no outcome | none | **production** |
| **matched-coverage sharpness** | absent | absent | — | **production**, to build |
| **calibration slope** | absent | absent | — | **production**, to build |
| **within-slate rank correlation** | absent | absent | — | **production**, to build |
| **between-player variance calibration** | absent | absent | — | **production**, to build |
| **clustered candidate-vs-baseline delta** | `CLUSTER_UNIT = 'game'`, `MIN_GAMES_FOR_CANDIDATE = 4`, `summarise` carries `n_games` beside every rate — but **no candidate-vs-baseline difference** | `clustered_delta(...)` with `clusters` a **required positional**, `R_BOOT = 2000`; `against_baseline` returns both arms plus `constant_brier` | **partial overlap on the clustering PRINCIPLE, none on the statistic** | **production** |
| **seal verification** | `verify_seal(directory)` — refuses unless every sealed file still hashes to its seal-time value | absent | none | **product** |
| **prospective ledger** | `LEDGER = 'nfl/product/EVALUATION_LEDGER.jsonl'`, `append`, `load`, `cumulative`, `candidates` | absent | none | **product** |
| *(extra)* miss classification | `classify` → `OUTSIDE_DISTRIBUTION` / `CENTRAL` / `WITHIN_DISTRIBUTION` / `TAIL_MISS` | absent | none | **product** |

## What the matrix actually shows

**One true duplicate: interval coverage.** Two independent implementations over
the same four levels. Nothing else collides.

**The two modules are not competitors; they answer different questions.**
`product/evaluator.py` scores **one sealed forecast against one finished game**
and accumulates a ledger. `production/evaluator.py` scores **a panel of
predictions against a baseline** with a clustered interval. Postgame grading
versus candidate comparison.

**But I built the second without checking for the first**, and the guidance's
"add CRPS to `SCORERS`" would have compounded that into a thirteenth CRPS.

## Canonicalisation plan — reuse by import, no formula copied

**Decision: two modules, one direction of dependency, zero duplicated formulas.**

```
nfl/product/evaluator.py        SCORING PRIMITIVES + POSTGAME LEDGER
    crps, pit, verify_seal, score, summarise, append/load/cumulative
                    |
                    |  imported by
                    v
nfl/production/evaluator.py     CANDIDATE COMPARISON
    brier, log_loss, sharpness, matched-coverage sharpness,
    calibration slope, rank correlation, variance calibration,
    clustered_delta, against_baseline
```

Concretely:

1. **`production/evaluator.py` imports `crps` and `pit` from `product/evaluator`**
   and registers `crps` in `SCORERS`, so `clustered_delta` works on count and
   continuous outputs. **No CRPS is written.** If the import direction turns out
   to create a cycle, the primitives move to a third leaf module that both
   import — they are still written once.
2. **`interval_coverage` is de-duplicated**: `production` keeps the panel-level
   function, and it is asserted in test against `product.score_metric`'s
   per-row `covered` on the same input, so the two can never drift. The
   duplicate becomes a cross-check instead of a fork.
3. **The five missing diagnostics land in `production/evaluator.py`** — matched
   coverage sharpness, calibration slope, within-slate rank correlation,
   between-player variance calibration, and tier discrimination.
4. **Nothing in `product/evaluator.py` changes behaviour.** `verify_seal`,
   `score`, `summarise`, the ledger and every scored artifact are untouched.
   `EVALUATION_LEDGER.jsonl` keeps every row it has.
5. **No module is deleted.** Deleting a public name is a separate decision from
   marking one, and the wired module has scored artifacts behind it.

## What is NOT decided here

Whether the panel-level and row-level coverage functions should eventually be
one function. They compute the same thing over different shapes, and merging
them touches the wired path. Left open, and the drift test above is what makes
leaving it open safe.

**V2 NOT YET EARNED**
