# R6-CLOCK — the depth rank the role prior is built around has never reached it

**Owner:** coordinator. **Found:** 2026-09-14, during R2/R3 patch integration.
**Files:** `nfl/production/run_forecast.py` (defect), `nfl/product/board.py`
(repaired here). **Status:** defect CONFIRMED, effect on tonight's board
MEASURED AND ZERO.

---

## 1. The defect, exactly

`run_forecast.py:888-895`:

```python
dr = {}
try:
    from nfl.product import board as _PBRD
    for k, v in _PBRD.depth_rank(args.season, args.week, teams).items():
        dr[k] = v[1]
except Exception:                                 # noqa: BLE001
    dr = {}
```

`board.depth_rank` is called with **no `as_of`**, and `run_forecast` never
enters a `vintage_selector.clock(...)` block — there is no such block anywhere
in `nfl/production`, `nfl/product` or `nfl/tools`; the only mentions are
comments in `readiness.py` saying `football_engine.run_game` *should* declare
one. So the call raises, every time:

```
VintageClockUnresolved: VINTAGE_CLOCK_UNRESOLVED: board.depth_rank was called
with no as_of and no declared vintage_selector.clock(...) context.
```

The bare `except Exception` catches it and `dr` stays `{}`. Reproduced
directly:

```
production form RAISES ->  dr={} -> VintageClockUnresolved VINTAGE_CLOCK_UNRESOLVED: ...
```

**`role_prior.assign_tiers` has therefore never received a depth rank in any
production run**, on any board in the corpus. This is the Phase-1 defect class
verbatim: a step that returned nothing was read as success. The refusal was
working exactly as designed — `vintage_selector` refuses to select without a
declared cut precisely so a post-kickoff capture cannot reach a pregame
forecast — and the call site swallowed the refusal and carried on.

It is worth naming what the `except` cost: the guard fired on every single run
and no operator ever saw it, because the one thing the handler does is destroy
the evidence that it fired.

## 2. What that does to the mechanism

With `dr = {}`, `has_d` is `False` for every player, so in `assign_tiers`
every player anchors at `MAX_TIER` — the deepest measured tier — and the
`depth_chart` and `shrunk_trailing_and_depth` bases become unreachable. The
basis counter proves it on tonight's pool:

| arm | basis counts |
|---|---|
| **production today (`dr={}`)** | `trailing_snap_share` 22, `no_information_lowest_tier` 5 |
| `dr` supplied | `shrunk_trailing_and_depth` 22, `depth_chart` 5 |

Both arms report `degraded=False`, which is correct — R3's repaired single-scale
ordering *did* run — and is also why nothing downstream noticed. `degraded`
answers "did the repaired ordering execute", not "did it have its evidence".

## 3. The effect on tonight's board: ZERO, and I am not dressing that up

27 skill players survive R2's choice set (DEN/KC: WR 12, TE 8, RB 7), and the
depth chart covers **27 of 27**. Running `assign_tiers` both ways:

```
tier changes: 0 of 27 players
  DEN RB (n=4) SAME     KC RB (n=3) SAME
  DEN TE (n=4) SAME     KC TE (n=4) SAME
  DEN WR (n=6) SAME     KC WR (n=6) SAME
```

Every room orders identically. The anchor moves every player's *score*, but
`assign_tiers` exports **rank**, and rank is what `role_prior.weight` consumes,
so the whole difference is absorbed. The 22 players with history are ordered by
their own trailing share under either anchor; the 5 without history sit at the
bottom of their rooms under either anchor.

**So: repair the plumbing because it is broken, not because it changes
tonight's number. It does not.** I expected this to be a material P0-2 finding
and it is not one. Whether it matters on a *different* slate — one with a
no-history player the chart ranks high, which is exactly the case R3's repair
was built for — is untested here and is not claimed either way.

## 4. What was repaired, and what was not

**Repaired now, in `nfl/product/board.py` (R3's patch 2, applied):** the
selector keyed `out[gsis_id]` without filtering return slots, so a player
listed at both an offensive position and `KR`/`PR`/`KOR` kept whichever row the
vendor wrote last. `depth_vintage.daily_point_in_time` has excluded these since
its line 129; this selector did not, so the two disagreed. On tonight's chart
this corrects exactly one player — `00-0038552`, `('PR', 2)` → `('RCB', 4)` —
a cornerback, not in the modelled pool, so again **no effect on tonight's
board**. `n_players` is 119 before and after. `test_vintage_selector`: 24
functions, 131 checks, PASS.

**NOT repaired yet:** the `run_forecast.py` call site. That file is held by R4
for the stat-contract work and a second writer would collide. The change is two
lines — pass the resolved cut as `as_of`, and let a refusal be reported rather
than swallowed — and it lands at integration, with the basis counter sealed
into the artifact so that the next time this mechanism runs without its
evidence, the board says so.

## 5. The rule this breaks, stated plainly

A bare `except Exception` around a governed refusal converts a designed guard
into silence. `board.depth_rank`'s own docstring already says this — it
documents that "the one production caller wrapped this in `except Exception: dr
= {}` -- so under the old code a refusal and a chart full of unranked players
were the same observation" — and the caller is still there. Documenting a
defect is not repairing it.
