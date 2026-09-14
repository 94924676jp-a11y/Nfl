# WS-C — call-site patches, REVIEWED AND NOT APPLIED

Every hunk below falls in a file WS-C does not own. **None of it has been
written to the tree.** Each carries the acceptance proof that shows what it
buys, measured on this checkout with `python3.12`.

`nfl/production/nonqb/layers.py` is **not** patched here and must not be: it is
hashed by Q9's frozen candidate identity `481f005f682cd721`. The whole design
below exists so that it does not have to be.

---

## P1 — `nfl/production/nonqb/football_engine.py` (WS-B). THE PERMANENT L1/L2 REPAIR.

`run_game` already receives `observed_before` (which is `args.written_at`) and
`kickoff_utc`. It passes both into `LY.appearance`, and `layers.py` then uses
`observed_before` for the DEPTH chart and ignores it for the injury feed, and
passes `kickoff_utc` to the readiness gate without `written_at`. Declaring the
cut around the call fixes both without touching the frozen module.

At `nfl/production/nonqb/football_engine.py:314`, replace:

```python
    ap = LY.appearance(season, week, recv, fixture=fixture, m=m, seed=seed,
                       teams=teams, kickoff_utc=kickoff_utc,
                       game_id=game_id, appearance_spec=appearance_spec,
                       observed_before=observed_before,
                       inactive_ids=inactive_ids)
```

with:

```python
    # THE CONSUMED CLOCK, DECLARED ONCE FOR THE WHOLE LAYER CHAIN.
    #
    # layers.py is hashed by Q9's frozen candidate identity, so the cut cannot
    # be threaded through it as an argument -- the same wall the C1 repair hit,
    # and the same answer: the corrected behaviour goes upstream. Inside this
    # block `readiness.latest_injuries_rows` (layers.py:145) and
    # `readiness.team_readiness` (layers.py:117) both select against
    # min(written_at, kickoff), which is the contract `readiness.as_of_cut`
    # already writes down and which neither call site could express.
    from nfl.production.nonqb import vintage_selector as _VS
    with _VS.clock(written_at=observed_before, kickoff_utc=kickoff_utc,
                   origin=f'football_engine.run_game:{game_id}'):
        ap = LY.appearance(season, week, recv, fixture=fixture, m=m, seed=seed,
                           teams=teams, kickoff_utc=kickoff_utc,
                           game_id=game_id, appearance_spec=appearance_spec,
                           observed_before=observed_before,
                           inactive_ids=inactive_ids)
```

**Acceptance proof.** Measured on this checkout:

```
production arity, no declared clock   -> PASS  (via GATE_HANDOFF, cut = kickoff - 1us)
same call inside the declared clock   -> PASS  (clock_basis DECLARED_CONTEXT,
                                                cut = written_at)
```

Without the patch the feed still refuses to be unbounded, but it inherits the
GATE's cut, which is `kickoff - 1us` when `layers.py:117` supplies no
`written_at`. With the patch the cut is `min(written_at, kickoff - 1us)` and
`clock_basis` reads `DECLARED_CONTEXT` in the layer evidence. On the 20 teams
of the 10 executable week-1 games at a `written_at` of kickoff minus 24 hours,
that is the difference between reading and not reading **85 player-rows** of
Friday game-status filings.

**This patch also retires the transitional handoff** in `readiness.py`: a
declared context beats it and consumes it. Nothing needs removing.

---

## P2 — `nfl/production/run_forecast.py` (WS-D). L3, AND THE FAILURE-OPEN WRAPPER.

At `nfl/production/run_forecast.py:679-684`, replace:

```python
            dr = {}
            try:
                from nfl.product import board as _PBRD
                for k, v in _PBRD.depth_rank(args.season, args.week,
                                             teams).items():
                    dr[k] = v[1]
            except Exception:                                 # noqa: BLE001
                dr = {}
```

with:

```python
            # `except Exception: dr = {}` made a total failure to load any
            # chart indistinguishable from every player lacking a rank, and
            # the chart it loaded came from the last blob in content-hash
            # order. Both are named now: the selector takes the forecast's own
            # cut, and a refusal is recorded rather than swallowed.
            dr = {}
            from nfl.product import board as _PBRD
            _dro = _PBRD.depth_rank_outcome(
                args.season, args.week, teams,
                as_of=_VSEL.as_of_cut(fx.get('kickoff_utc'),
                                      args.written_at))
            if _dro.state is State.PASS:
                dr = {k: v[1] for k, v in _dro.value.items()}
                fx.setdefault('_r6', {})['depth_vintage'] = {
                    'as_of': _dro.evidence['as_of'],
                    'chosen': _dro.evidence['chosen'],
                    'composite_sha256': _dro.evidence['composite_sha256']}
            else:
                fx.setdefault('_r6', {})['depth_vintage'] = {
                    'refused': _dro.code, 'detail': _dro.detail[:300],
                    'evidence_ceiling': _dro.evidence.get('evidence_ceiling')}
```

with `from nfl.production.nonqb import vintage_selector as _VSEL` added to the
imports.

**Acceptance proof.** `board.depth_rank_outcome` on DAL/NYG at three cuts:

```
as_of 2026-09-07T12:00:00Z  -> dt 2026-09-06T11:29:30Z   (24.5h before the cut)
as_of 2026-09-13T20:00:00Z  -> dt 2026-09-13T12:42:08Z   ( 7.3h before the cut)
as_of 2026-08-01T00:00:00Z  -> BLOCKED[DEPTH_RANK_CAPTURE_ABSENT]
```

Today, unpatched, all three resolve to the 2026-09-08 chart from
`depth_charts.f57ef0724d907160`, which is 24 hours AFTER the first cut and five
days STALE for the last. `depth_rank` (the dict form) now raises rather than
returning a chart chosen by glob order, so leaving this call site unpatched
turns L3 into a recorded `dr = {}` instead of a wrong chart — a coverage loss,
not a leak. **It is not left that way on purpose; this patch is the fix.**

---

## P3 — `nfl/tools/score_game.py`. One line.

At `nfl/tools/score_game.py:83`, replace:

```python
    roster = B.roster_identity(a.season, a.week, art.get('team_ids') or [])
```

with:

```python
    from nfl.production.nonqb import vintage_selector as VS
    roster = B.roster_identity(
        a.season, a.week, art.get('team_ids') or [],
        as_of=VS.as_of_cut(art.get('kickoff_utc'), art.get('written_at')))
```

`art` is already loaded three lines above and carries both clocks. Without
this, `roster_identity` raises `VintageClockUnresolved`.

---

## P4 — `nfl/production/nonqb/slate_rehearsal.py` and `nfl/tests/test_nonqb_r3.py`.

Both reach `layers.appearance` with `teams=None`, which is the slate-wide
branch. It resolves today through the gate handoff at the **earliest kickoff
on the slate**, which is the only cut lawful for every game it judged. The
patch makes the cut explicit rather than inherited:

`nfl/production/nonqb/slate_rehearsal.py:40`:

```python
    from nfl.production.nonqb import vintage_selector as VS
    _ko = RD.team_kickoff(season, week, (players[0] or {}).get('team')) \
        if players else None
    with VS.clock(kickoff_utc=_ko, written_at=None,
                  origin='slate_rehearsal.nonqb_chain') if _ko else \
            contextlib.nullcontext():
        ap = LY.appearance(season, week, players, fixture=None,
                           game_id=game_id)
```

This is **optional**: the suite passes without it. It is listed so the
inherited cut is a choice on the record rather than an accident.

---

## P5 — RL-11, `nfl/tools/ingest_inactives.py`. A DECLARED COLUMN THAT IS NOT THERE.

`CONSUMED['weekly_rosters']` declares `('gsis_id', 'position', 'team',
'status')` and `consumed_slice` reads the REDUCED blob, whose header is
`season,week,team,gsis_id,position`. Reproduced independently here against
every `CONSUMED` entry:

```
schedules:       declared 8 cols, missing []
weekly_rosters:  declared 4 cols, missing ['status']      <-
injuries:        declared 4 cols, missing []
depth_charts:    declared 5 cols, missing []
```

So every `weekly_rosters` keep-string ends `|None` — WS-L measured 181 of 181 —
and the consumed-slice hash has been hashing a constant. It still detects a
move in the other three columns, so the artifact is not worthless; it is
silently narrower than it says it is.

At `nfl/tools/ingest_inactives.py:73`, replace the body of `consumed_slice`
from `cols = CONSUMED.get(src)` with:

```python
    cols = CONSUMED.get(src)
    if cols is None:
        return None, 0
    reader = csv.DictReader(op(p, 'rt'))
    # A DECLARED COLUMN THAT IS NOT IN THE BYTES IS NOT A COLUMN OF Nones.
    # The reduction drops `weekly_rosters.status`, so every keep-string ended
    # `|None` and the slice hash was hashing a constant while claiming to
    # cover four fields. Same shape as RL-10's `int(pos_slot or 0)`.
    absent = [c for c in cols if c not in (reader.fieldnames or ())]
    if absent:
        raise ConsumedSliceColumnMissing(
            f'CONSUMED_SLICE_COLUMN_ABSENT: {src} declares {list(cols)} and '
            f'{p.name} carries {list(reader.fieldnames or ())}. {absent} is '
            f'not in the bytes, so every keep-string would carry None there '
            f'and the slice hash would not cover it. Either narrow CONSUMED '
            f'for this source or retain the column in the capture reduction.')
    keep = []
    for r in reader:
        ...
```

plus, near the top of the module:

```python
class ConsumedSliceColumnMissing(RuntimeError):
    """A consumed-slice declaration names a column the blob does not carry."""
```

**Choose one remedy, do not do both silently.** Either drop `status` from
`CONSUMED['weekly_rosters']` — the honest description of what the reduced blob
can support — or retain `status` in the capture reduction, which is a
capture-layer change and would also let `roster_status` stop reading
`nfl_vintage/raw/`. WS-C recommends the first now and the second as WS-K's
retention work, but it is not WS-C's call.

The same check is available as a library call: `vintage_selector.column_check`
and `vintage_selector.select(..., require_columns=...)`, which is where it
belongs for anything selecting through the canonical path.

---

## P6 — L4, `nfl/capture/coverage.py:251` and `nfl/production/team_volume_v1.py:92`. DESIGN ONLY.

**No leak is claimed and none was measured.** WS12 scored this UNPROVABLE and
WS-C does not upgrade that verdict. What is measured is that neither selector
takes a clock: one sorts by filesystem `st_mtime`, which git does not preserve,
and the other lexicographically by content hash.

The selector exists — `vintage_selector.select('schedules', as_of=...)`
resolves on this checkout — so the patch is mechanical:

```python
# coverage.load_week_plan
from nfl.production.nonqb import vintage_selector as VS
sel = VS.select('schedules', as_of=as_of)          # as_of becomes a parameter
if sel.state is not State.PASS:
    return sel
latest = sel.value.path()
```

```python
# team_volume_v1.coaches
sel = VS.select('schedules', as_of=as_of)
...
```

**It is not free and that is why it is not written here.** `load_week_plan` is
called by `readiness.team_kickoff`, `readiness._slate_teams` and
`game_readiness` to *discover* kickoff times — which is what an `as_of` would
be derived from. Threading a clock through it without creating that circularity
is a design decision that belongs to whoever owns the capture layer, and
`coverage.py` is being edited by another workstream in this pass. The declared
family and its ceiling are in `vintage_selector.FAMILIES['schedules']` so the
next pass starts from a written-down contract rather than from a glob.
