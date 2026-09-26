# Zero-consumer modules in the production namespaces

Track A item (1). Measured by AST: every `from`/`import` across the whole
repository, tests included, resolved against the 195 modules under
`nfl/production`, `nfl/dfs`, `nfl/postgame`, `nfl/product`, `nfl/governance`.

**13 of 195 have zero importers.** Twelve of those are CLI entry points with
`if __name__ == '__main__'`, which is a legitimate way to have no importer.
One is not, and it is the only true orphan.

## The one true orphan: `nfl/dfs/salaries/postinactives_board.py`

No importers, no `__main__`, 180 lines, six functions. **It cannot execute by
any path.** It is superseded by `build_postinactives_package.py`, which
`emit_package.py` actually calls.

Function-level comparison, so "superseded" is a measurement rather than an
impression:

| | orphan | live |
|---|---|---|
| shared | `position_support`, `read_run`, `summarise` (all differ in body) | |
| orphan only | `_open`, `_vec`, `assert_no_inactive_survived` | |
| live only | | `assert_no_inactive_in_playable`, `assert_shared_draws`, `dfs_rows`, `football_rows`, `prop_rows`, `_opp`, `_norm`, `_align` |

**The safety check survived the supersession**, which was the thing worth
checking: `assert_no_inactive_survived` → `assert_no_inactive_in_playable`.
The live version is stricter in scope — it intersects declared inactive ids
with the gsis_ids the runs **emitted**, where the orphan looked only at rows
carrying a non-null `dk_points_mean`, and emitted ⊇ playable. Both keep the
distinction that matters: an empty inactive list and a verified-empty one are
different facts, so neither returns PASS without evidence.

**But checking that led to DEF-065**, which is the real finding here and is
recorded separately: the live gate was computed, written into the output, and
never acted on.

## The twelve entry points, and which are invoked by anything

Referenced in a workflow, runbook, or other non-`.py` file:

| Invoked | Never referenced outside `.py` |
|---|---|
| `benchmark`, `build_artifacts` (×2), `correlation`, `ingest_outcome`, `run_review`, `run_chain` | `early_only`, `emit_package`, `scenarios`, `run_week2`, `write_findings`, `write_reports` |

Six entry points exist that nothing documents or schedules. That is not the
same as dead — a person can still run them — but it does mean **DEF-065's fix
has not executed and cannot execute on a schedule**, which is why that defect
is FIX_IMPLEMENTED and not VERIFIED.

## Not claimed

- That the six unreferenced entry points should be deleted. They were
  classified by reachability, not re-derived, and none was executed here.
- That 195 is the whole production surface. It is the five namespaces listed
  above; `nfl/research`, `nfl/tools`, `coordination` and `sportsplatform` were
  out of scope for this sweep.
