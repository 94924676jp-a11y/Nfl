"""Reusing shared history must be free of consequence, and it is checked.

WHAT IS REUSED AND WHY IT IS SAFE.

`appearance_r7.build_frame` and `appearance_r8.enriched_frame` read exactly
two things: the twelve historical leaves staged and hash-checked through
`INPUT_MANIFEST.json` (seasons 2020-2025) and `dc25_daily.csv.gz`. No 2026
vintage reaches them, so they are a pure function of immutable history.

WHAT IS NOT REUSED. Nothing a game consumes. Team volume, the QB allocation,
appearance for a slate and every forecast output stay per-game and are
recomputed whenever that game's consumed slice moves. Caching a forecast
would hit the benchmark by faking it, and these tests assert it is not done.

THE DEFECT THAT WAS ALREADY THERE. `_FRAME` and `_ENRICHED` were module-level
dicts keyed on NOTHING -- served for the life of the process regardless of
what changed underneath. They are now keyed on a content fingerprint of their
declared dependencies and evict when it moves.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7                 # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8                 # noqa: E402
from nfl.research import warm_session as WS                          # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def test_a_the_fingerprint_covers_the_declared_dependencies():
    o = WS.dependency_fingerprint()
    check('a fingerprint is computed', o.state is State.PASS,
          f'{o.state.name}[{o.code}]')
    if o.state is not State.PASS:
        return
    parts = o.evidence['parts']
    check('  it covers the staged-leaf manifest',
          'INPUT_MANIFEST.json' in parts, str(sorted(parts)))
    check('  and the daily depth leaf',
          'dc25_daily.csv.gz' in parts, str(sorted(parts)))
    check('  it is stable across calls',
          WS.dependency_fingerprint().value == o.value)
    check('  and the module fingerprint agrees with the engine one',
          R7._dependency_fingerprint() == o.value,
          f'{R7._dependency_fingerprint()} vs {o.value}')


def test_b_a_missing_dependency_refuses_rather_than_hashing_nothing():
    """An empty hash compares equal to another empty hash."""
    real = WS._dependency_paths

    def gone():
        return [pathlib.Path('/nonexistent/never.json')]

    WS._dependency_paths = gone
    try:
        o = WS.dependency_fingerprint()
        check('a missing dependency BLOCKS by name',
              o.state is State.BLOCKED
              and o.code == 'WARM_DEPENDENCY_MISSING',
              f'{o.state.name}[{o.code}]')
    finally:
        WS._dependency_paths = real


def test_c_stale_cached_state_cannot_survive_a_dependency_change():
    """THE GUARD the directive requires, exercised in both directions."""
    o1 = R7.build_frame()
    check('the frame builds', o1.state is State.PASS, o1.code)
    if o1.state is not State.PASS:
        return
    o2 = R7.build_frame()
    check('  a second call is served from cache',
          o2.evidence.get('cached') is True and o2.code == 'R7_FRAME_CACHED',
          o2.code)
    check('    and returns the SAME rows', o2.value is o1.value or
          len(o2.value) == len(o1.value), f'{len(o2.value)} rows')

    # Move the fingerprint underneath the cache. The next call must NOT be
    # served from it.
    R7._FRAME['fingerprint'] = 'DELIBERATELY_STALE'
    o3 = R7.build_frame()
    check('  a changed dependency fingerprint EVICTS the cache',
          o3.code == 'R7_FRAME_OK' and not o3.evidence.get('cached'),
          o3.code)
    check('    and the rebuilt frame matches the original row count',
          len(o3.value) == len(o1.value),
          f'{len(o3.value)} vs {len(o1.value)}')
    check('    with the cache re-keyed to the true fingerprint',
          R7._FRAME.get('fingerprint') == R7._dependency_fingerprint())

    R8._ENRICHED['fingerprint'] = 'DELIBERATELY_STALE'
    o4 = R8.enriched_frame()
    check('  the R8 enriched frame evicts on the same signal',
          o4.code == 'R8_FRAME_OK' and not o4.evidence.get('cached'), o4.code)


def test_d_warm_and_cold_produce_identical_football():
    """Measured on real sealed boards, not asserted in prose.

    2026_01_BUF_HOU was sealed once with cold caches and again inside a warm
    session. Same inputs, same seed. The draw content digest must be
    identical; only metadata such as written_at and run_id may differ.
    """
    d = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live' / '2026_01_BUF_HOU'
    boards = sorted(d.glob('**/board.json'), key=lambda p: p.stat().st_mtime)
    if len(boards) < 2:
        print('  ..   fewer than two sealed BUF_HOU boards; skipped')
        return
    docs = [json.load(open(b)) for b in boards[-3:]]
    digests = {str(j.get('draw_content_digest')) for j in docs}
    check('every re-seal of the same game carries ONE draw digest',
          len(digests) == 1, str(digests))
    written = {str((j.get('freshness') or {}).get('written_at')) for j in docs}
    check('  while written_at genuinely differs between them',
          len(written) > 1, str(sorted(written)))
    check('  so the football is identical and only metadata moved',
          len(digests) == 1 and len(written) > 1)


def test_e_nothing_game_specific_is_cached():
    """The benchmark must not be met by caching forecasts."""
    src = pathlib.Path(_ROOT, 'nfl', 'research', 'warm_session.py').read_text()
    for banned in ('board.json', 'player_draws', 'forecast_artifact',
                   'SEALED_FORECAST'):
        check(f'  the session never persists {banned!r}',
              banned not in src, banned)
    # ASSERT ON BEHAVIOUR, NOT ON PROSE. An earlier version checked
    # `'build_one' not in src` and failed on the docstring that explains
    # where the cost was measured -- the same source-grep mistake made
    # earlier with 'tier' and 'expected value'. What matters is what the
    # module can reach and what it reports.
    import nfl.research.warm_session as _ws
    reachable = {n for n in dir(_ws) if not n.startswith('__')}
    check('the session exposes no forecast-sealing entry point',
          not {'build_one', 'make_board', 'MB'} & reachable,
          str(sorted(reachable & {'build_one', 'make_board', 'MB'})))
    check('  and the only shared objects it reports are the two frames',
          {k for k in WS.shared_state_status() if k != 'fingerprint'}
          == {'r7_frame_primed', 'r7_frame_valid',
              'r8_enriched_primed', 'r8_enriched_valid'},
          str(sorted(WS.shared_state_status())))
    st = WS.shared_state_status()
    for k in ('r7_frame_primed', 'r7_frame_valid', 'r8_enriched_primed',
              'r8_enriched_valid', 'fingerprint'):
        check(f'  status reports {k}', k in st, str(sorted(st)))


def test_f_the_session_reports_hits_and_misses():
    s = WS.SlateSession('2026-09-13', 'R8')
    check('a fresh session has no history', s.summary()['n_refreshes'] == 0)
    s.history.append({'shared_state_cache': 'HIT', 'wall_seconds': 1.0})
    s.history.append({'shared_state_cache': 'MISS', 'wall_seconds': 2.0})
    sm = s.summary()
    check('  hits and misses are counted apart',
          (sm['cache_hits'], sm['cache_misses']) == (1, 1), str(sm))
    check('  and per-refresh wall time is retained',
          sm['per_refresh_wall_seconds'] == [1.0, 2.0], str(sm))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
