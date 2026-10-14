#!/usr/bin/env python3.12
"""PIT-D1 (owner D-12, 2026-10-14): a historical build may not silently read the future.

  LIVE   without a manifest, a cutoff that predates guarded captures or fixed-path content on disk REFUSES
         (PIT_LIVE_READ_AFTER_CUTOFF); a cutoff of now passes (negative control)
  E2E    the two production state builders refuse a past cutoff end to end: classic_slate_state.build(as_of=...) and
         showdown_slate_state.build (cutoff = min(now, kickoff))
  SEAL   an active manifest sealed LATER than the run's cutoff refuses (PIT_MANIFEST_CUTOFF_AFTER_RUN_CUTOFF); one at
         the run's cutoff governs (MANIFEST mode)
  EXEMPT an explicit pit_exempt (stated reason, keyword only) is stamped NOT_POINT_IN_TIME / RELEASABLE False, the Classic
         state is never written, and a Showdown state aimed at the production path refuses"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests._pit import at_cutoff  # noqa: E402
from nfl.tools import classic_slate_state as C  # noqa: E402
from nfl.tools import showdown_slate_state as SSS  # noqa: E402
from nfl.warehouse import point_in_time as PIT  # noqa: E402

PASSED = FAILED = 0
W4_AS_OF = '2026-10-04T05:00:00Z'
ATL_EXPORT = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv'


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def _now():
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def test_live_mode_refuses_a_past_cutoff_and_passes_now():
    r = PIT.live_reads_after_cutoff(W4_AS_OF)
    check(r['n'] > 0, f'fixture: the tree holds data that did not exist at {W4_AS_OF} ({r["n"]} files)')
    try:
        PIT.require_point_in_time(W4_AS_OF, 'test')
        check(False, 'positive control: a past cutoff in live mode refuses')
    except PIT.PITLiveReadAfterCutoff as e:
        check(str(e).startswith('PIT_LIVE_READ_AFTER_CUTOFF'), f'positive control: a past cutoff in live mode refuses ({str(e)[:70]})')
    ok = PIT.require_point_in_time(_now(), 'test')
    check(ok['mode'] == 'LIVE_VERIFIED' and ok['n'] == 0, f'negative control: a cutoff of now passes ({ok["mode"]}, {ok["n"]})')


def test_production_builders_refuse_a_past_cutoff_end_to_end():
    o = C.build('2026W4', as_of=W4_AS_OF, write=False)
    check(o.state.value == 'BLOCKED' and o.code == 'PIT_LIVE_READ_AFTER_CUTOFF', f'classic_slate_state.build refuses ({o.state.value} {o.code})')
    saved = SSS.OUT
    SSS.OUT = pathlib.Path(tempfile.mkdtemp(prefix='pit_fc_')) / saved.name
    try:
        o = SSS.build(ATL_EXPORT)
    finally:
        SSS.OUT = saved
    check(o.state.value == 'BLOCKED' and o.code == 'PIT_LIVE_READ_AFTER_CUTOFF', f'showdown_slate_state.build refuses ({o.state.value} {o.code})')


def test_a_manifest_later_than_the_run_cutoff_refuses_and_one_at_the_cutoff_governs():
    with at_cutoff('2026-10-12T20:00:00Z', 'PIT_FC_LATE'):
        try:
            PIT.require_point_in_time(W4_AS_OF, 'test')
            check(False, 'a manifest sealed after the run cutoff refuses')
        except PIT.PITLiveReadAfterCutoff as e:
            check('PIT_MANIFEST_CUTOFF_AFTER_RUN_CUTOFF' in str(e), 'a manifest sealed after the run cutoff refuses')
    with at_cutoff(W4_AS_OF, 'PIT_FC_EXACT'):
        r = PIT.require_point_in_time(W4_AS_OF, 'test')
        check(r['mode'] == 'MANIFEST' and r['cutoff_utc'] == W4_AS_OF, f'a manifest at the run cutoff governs ({r["mode"]})')
    check(PIT.active() is None, 'the manifest is deactivated after the block')


def test_exemption_is_stamped_never_written_and_never_production():
    from nfl.tests._pit import vintage_team_game
    with vintage_team_game('8feac0f3'):
        o = C.build('2026W4', as_of=W4_AS_OF, write=True, pit_exempt='TEST: exemption contract')
    pit = (o.value or {}).get('point_in_time') or {}
    check(o.state.value == 'PASS' and pit.get('mode') == 'NOT_POINT_IN_TIME' and pit.get('RELEASABLE') is False
          and pit.get('n_live_reads_after_cutoff', 0) > 0, f'classic exempt state is stamped ({o.state.value} {pit})')
    check('path' not in (o.evidence or {}) or not (o.evidence or {}).get('path'), 'and it is not written even when write=True was asked')
    o = SSS.build(ATL_EXPORT, pit_exempt='TEST: exemption contract')        # OUT is the production path here
    check(o.state.value == 'BLOCKED' and o.code == 'PIT_EXEMPT_STATE_NOT_WRITABLE_TO_PRODUCTION',
          f'a showdown exempt state aimed at the production path refuses ({o.state.value} {o.code})')



def test_fitted_models_need_a_pin_and_world_clock_resolves_in_a_sealed_run():
    """Two holes inside manifest mode (PIT-D1 audit): nfl/sim fitted models were UNGUARDED, and world_clock read the
    live TEAM_GAME directly, so a sealed Classic replay could not run at all."""
    with at_cutoff(W4_AS_OF, 'PIT_FC_FITTED') as man:
        try:
            (_REPO / 'nfl/sim/DST_MODEL.json').read_bytes()
            check(False, 'positive control: a fitted model read in a sealed run without a pin refuses')
        except PIT.PITUnauthorizedRead as e:
            check('PIT_FITTED_UNPINNED' in str(e), f'positive control: a fitted model read in a sealed run without a pin refuses ({str(e)[:60]})')
    import os
    import subprocess
    env = {**os.environ, PIT.ENV: str(man)}
    r = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, %r); from nfl.production import world_clock as W; '
                        'print(W.TEAM_GAME)' % str(_REPO)], capture_output=True, text=True, env=env, cwd=_REPO)
    out = r.stdout.strip()
    check(r.returncode == 0 and bool(out) and out != str(_REPO / 'nfl/warehouse/TEAM_GAME.json'),
          f'world_clock.TEAM_GAME resolves to the vintage under a manifest set at process start ({out[-60:] or r.stderr[-200:]})')
    r = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, %r); from nfl.production import world_clock as W; '
                        'print(W.TEAM_GAME)' % str(_REPO)], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != PIT.ENV}, cwd=_REPO)
    check(r.stdout.strip().endswith('nfl/warehouse/TEAM_GAME.json'), 'negative control: live mode reads the live file unchanged')

def test_live_gate_covers_derived_caches_and_fitted_models():
    # PIT audit 2026-10-14 (highest risk): the live check covered captures and TEAM_GAME only
    r = PIT.live_reads_after_cutoff(W4_AS_OF)
    kinds = {v.split('_CONTENT')[0].split('_UNCLOCKED')[0] for v in r['items'].values()}
    check(any(k.startswith('nfl/derived/') for k in r['fixed_paths']) and any(k.startswith('nfl/sim/') for k in r['fixed_paths']),
          'the live check now clocks nfl/derived and nfl/sim files')
    check('DERIVED' in kinds, f'at the W4 cutoff, derived caches whose content post-dates it are refused ({sorted(kinds)})')
    now = dt.datetime.now(dt.timezone.utc)
    real = PIT._content_clock
    target = sorted(k for k in r['fixed_paths'] if k.startswith('nfl/sim/'))[0]
    try:   # NEGATIVE CONTROL: a fitted model whose content appeared after the cutoff refuses a run at that cutoff
        PIT._content_clock = lambda root, rel: ((now + dt.timedelta(hours=1), 'TEST_INJECTED') if rel == target
                                                else real(root, rel))
        r2 = PIT.live_reads_after_cutoff(now.isoformat())
        check(r2['items'].get(target) == 'FITTED_CONTENT_AFTER_CUTOFF',
              f'an injected post-cutoff fitted model is refused ({target}: {r2["items"].get(target)})')
    finally:
        PIT._content_clock = real
    r3 = PIT.live_reads_after_cutoff(now.isoformat())
    check(r3['items'].get(target) is None, 'and the same model at its real clock is admitted at now')


def test_a_refusal_never_becomes_a_degraded_projection():
    from nfl.tools import proj_v1 as PV, kicker_model as KM
    real, saved = KM.measure, PV._KM
    try:
        PV._KM = None
        KM.measure = lambda *a, **k: (_ for _ in ()).throw(PIT.PITLiveReadAfterCutoff('PIT_LIVE_READ_AFTER_CUTOFF: test'))
        try:
            PV._kicker_rates()
            raised = False
        except PIT.PITError:
            raised = True
        check(raised, 'a point-in-time refusal inside kicker_model.measure propagates (not KICKER_RATES_ABSENT)')
        PV._KM = None
        KM.measure = lambda *a, **k: (_ for _ in ()).throw(ValueError('no table'))
        check(PV._kicker_rates() is None, 'an ordinary failure still reads as an absent table (behaviour unchanged)')
    finally:
        KM.measure, PV._KM = real, saved


def test_classic_as_of_at_or_after_kickoff_is_never_releasable():
    o = C.build('2026W5', as_of=dt.datetime.now(dt.timezone.utc).isoformat(), write=False)
    pit = (o.value or {}).get('point_in_time') or {}
    check(o.state.value == 'PASS' and pit.get('mode') == 'LIVE_VERIFIED' and pit.get('RELEASABLE') is False
          and str(pit.get('not_releasable_reason', '')).startswith('AS_OF_AT_OR_AFTER_KICKOFF'),
          f'a W5 Classic state built now (after its kickoff) is LIVE_VERIFIED but RELEASABLE False ({o.state.value} {pit})')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    check(PASSED > 0, 'the module counted at least one check')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
