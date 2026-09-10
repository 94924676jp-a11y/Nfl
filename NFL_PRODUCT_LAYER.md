# The game-day product layer

**Built.** Read-only over the frozen V1 engine. `nfl/product/` imports no model
layer, holds no estimator, prior or parameter, and computes no projection —
every number it shows is read from a sealed artifact and its draw sidecar, or
is a function of those draws alone.

## What it is

| module | job |
|---|---|
| `metrics.py` | the declared inventory of what V1 forecasts — and what it does not |
| `distributions.py` | reads a sealed forecast + draws; refuses a mismatched pair |
| `thresholds.py` | threshold probabilities from draws; no market number can enter |
| `confidence.py` | five-dimension model-confidence ranking |
| `board.py` | assembles the board, joining identity, freshness, governance |
| `render.py` | the readable artifact |
| `names.py` | gsis_id → name, display only, resolved under the same vintage cut |
| `evaluator.py` | postgame scoring and the permanent cumulative ledger |
| `nfl/tools/make_board.py` | seal a chronology-valid forecast, then render its board |
| `nfl/tools/score_game.py` | score a sealed forecast against a final game |

## The anti-fabrication spine

A report is where a missing number is most tempting to invent, because a blank
cell looks like a bug and a plausible number looks like a feature. So the
supported set is declared once and the renderer can only show what that
declaration admits. Three checks in `test_product_layer.py` pin it: every
rendered column, and every threshold ladder, must name a declared V1 output.

**The one that matters most.** RB/WR/TE **rushing yards do not exist in V1**.
`layers.rushing_conversion` refuses with `RUSHING_CONVERSION_CONTROL_UNDEFINED`
on three open owner decisions, and names `carries × yards_per_carry` as the
prohibited implementation — which is exactly the number a product layer would
otherwise be expected to print. It is not printed. The board shows the metric
as UNAVAILABLE with that reason. Quarterback rushing yards **are** supported,
through a different and adjudicated mechanism inside QB V1, and that asymmetry
is real rather than an oversight.

Also named absent: air yards / aDOT, and passer rating — a composite of
forecast components is not itself a forecast distribution and would misstate
its own uncertainty.

## Thresholds

Ladders are **fixed in advance per metric**, identical for every player, so a
threshold can never be chosen after seeing where a projection landed. Counts
use `>= k`; yardage uses half-point lines so no draw can land exactly on one.

`test_no_sportsbook_number_can_enter_the_product` greps the whole product layer
for `odds`, `vig`, `moneyline`, `implied_prob`, `closing_line`, `kelly` and
five more. There is no market feed in this system, so there is no line, no
implied probability, no edge and no recommendation — and nothing to compute one
from.

**Anytime touchdown is a joint, not a product of marginals.** A back's rushing
TD and his receiving TD are two columns of the same draw index — the same
simulated game. Multiplying the marginals would invent an independence the
draws do not have, so `anytime` is the share of draws in which the player
scored at all. A passing touchdown is not a touchdown the passer scored; it is
excluded from `anytime` and reported separately. Both are tested.

## Confidence

Five equally weighted dimensions: input completeness, role certainty,
distribution width, status certainty, layer completeness. **Flat by design** —
no evidence yet says which dimension predicts a miss, and a fitted weighting
with nothing behind it would be a silent constant. When the ledger can say, that
is a research ruling, not a product change.

The board states in its own text that high confidence means confidence in the
model and its inputs, **never** in the outcome.

**A defect I built and caught.** The first version ranked four backup
quarterbacks and two fifth receivers *above both starters*. Their metrics are
zero in three quarters of their draws, so the interquartile range was zero,
which scored as perfect narrowness — and a role certainty of 1% could not
outvote it. A zero IQR is mass at a point, not precision. `dispersion` now
returns None for a degenerate distribution and it scores zero, with the reason
shown. A second pass fixed the running backs: iterating receiving-first
described Christian McCaffrey as "5% of the game's targets", which is true and
is not what makes him the starter. Both are pinned by tests.

## The postgame evaluator

`score()` **refuses unless every sealed file still hashes to the value recorded
at seal time.** Scoring a forecast that may have been edited after the outcome
was known is not scoring; it is a description of the outcome.

**A second defect my own test caught.** `verify_seal` resolved the seal file's
repo-relative paths first, so scoring a *copy* verified the *original*: the copy
could be edited freely and the seal still passed. A guard that verifies
something other than the thing it guards is worse than no guard, because it
reports success. It now resolves inside the directory being scored and records
which path on disk it actually hashed.

Per player and metric: actual percentile, CRPS, non-randomised PIT bracket,
median error, interval coverage at 50/80/90/95, bias, and a miss class from a
stated rule — `CENTRAL`, `WITHIN_DISTRIBUTION`, `TAIL_MISS`,
`OUTSIDE_DISTRIBUTION`. Cumulative by position, metric, team, layer, model
component and week.

**One game creates a hypothesis; repeated independent misses create a
refinement candidate.** The bar is declared before any data arrives: the same
directional miss in **at least 4 distinct games**. Forty rows inside one game
raise nothing — attempts, completions and yards for one passer are
near-deterministic functions of each other, and both teams share one game
script. Every aggregate carries `n_games` beside `n_rows` and a caution saying
which one is the sample size. A candidate is a request for a research ruling,
never a licence to change the model.

## NE@SEA, recorded not acted on

Run A was scored through the new pipeline and **33 rows are now in the permanent
ledger** (`nfl/product/EVALUATION_LEDGER.jsonl`). Seal verified first; the
outcome hash was checked against the value recorded when it was downloaded.

Only QB rows exist, because Run A produced no receiving or rushing layer.
Overall: mean CRPS 13.94, median absolute error 3.00, bias +1.33, coverage
33.3 / 60.6 / 81.8 / 81.8 %, miss classes 11 CENTRAL, 16 WITHIN_DISTRIBUTION,
6 TAIL_MISS.

**Refinement candidates: zero.** Six metrics sit on the watchlist at one game
each — `qb/att`, `qb/cmp`, `qb/db` and three more, all `actual_above_interval`.
That is the bar working as designed. Nothing about V1 was changed.

## SF@LA protocol

A chronology-valid forecast is sealed at
`nfl/research/shadow/sf_la_pregame/`, with `PROTOCOL_RECORD.json` carrying the
exact `written_at`, input vintages, run id, draw digest, model configuration,
component manifest and authorization state.

It is labelled **SHADOW / NOT AUTHORIZED** in the header of the board and in the
machine-readable payload, with `promoted=false` and `prospective_eligible=false`.

**If G0A clears before kickoff, this artifact stays SHADOW.** Authorization is a
property of the moment a forecast is written, not a label applied afterwards.
Relabelling this run once the gate opens would make an unauthorized forecast
look like an authorized one — the exact mislabelling the directive forbids. A
new forecast would be written under the open gate and marked as the first live
NFL-1 forecast.

## What is NOT built

- **No automatic refresh.** Nothing re-runs itself before kickoff. `make_board.py`
  is a command; the capture routine that would feed it a newer vintage is
  separate infrastructure this mission was told not to touch.
- **No market anything**, by rule and by test.
- **No RB rushing yards**, and no substitute for them.

## Engineering untouched

`nfl/production/` and `nfl/research/PATH_C_STATE.json` are byte-identical to the
V1 freeze at `638080c`. No estimator, parameter, component or G0A rule was
altered, and the capture infrastructure was not touched.
