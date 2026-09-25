"""Source liveness: one dark feed, all feeds dark, and a feed that never was.

The case the whole module exists for is section C. On 2026-09-24
`official_inactives` had been silent for nine days while six peer feeds polled
every thirty minutes, every failure was recorded honestly by name, and a slate
was forecast anyway. Peer comparison was available and nothing performed it.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import capture_cadence as C                # noqa: E402

PASSED = 0
FAILED = 0

NOW = dt.datetime(2026, 9, 25, 12, 0, tzinfo=dt.timezone.utc)


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def raised(exc, fn, needle=None):
    try:
        fn()
    except exc as e:
        if needle is not None and needle not in str(e):
            return False, f'raised without {needle!r}: {e}'
        return True, ''
    except Exception as e:                                      # noqa: BLE001
        return False, f'raised {type(e).__name__} instead: {e}'
    return False, f'did not raise {exc.__name__}'


def _manifest(spec: dict) -> pathlib.Path:
    """spec: source -> (age_hours_of_last_capture, n_captures, succeeds)."""
    fh = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    for src, (age_h, n, ok) in spec.items():
        for i in range(n):
            t = NOW - dt.timedelta(hours=age_h + 0.5 * (n - 1 - i))
            rec = {'capture_id': t.strftime('%Y%m%dT%H%M%SZ'), 'source': src,
                   'state': 'PASS' if ok else 'BLOCKED',
                   'code': 'CAPTURED' if ok else 'NO_EGRESS',
                   'value': ({'n_data_rows': 100} if ok else {})}
            fh.write(json.dumps(rec) + '\n')
    fh.close()
    return pathlib.Path(fh.name)


_HEALTHY = {s: (1.0, 20, True) for s in
            ('injuries', 'depth_charts', 'schedules', 'weekly_rosters',
             'official_injury_report', 'espn_injuries_json')}


def test_A_a_polled_source_within_cadence_is_current():
    print('\nA. the quiet case')
    p = _manifest(dict(_HEALTHY, official_inactives=(1.0, 20, True)))
    try:
        rep = C.assess(p, now=NOW)
        check('all polled sources CURRENT',
              all(r['verdicts'] == [C.CURRENT] for s, r in
                  rep['sources'].items() if r['polled']),
              {s: r['verdicts'] for s, r in rep['sources'].items()})
        check('no global stall', rep['global_stall'] is False)
        rep2 = C.assert_ready_for_slate(['official_inactives'], report=rep)
        check('a slate is allowed to proceed', rep2 is rep)
    finally:
        p.unlink()


def test_B_one_source_past_its_own_cadence():
    print('\nB. one feed broke')
    p = _manifest(dict(_HEALTHY, official_inactives=(30.0, 20, True)))
    try:
        rep = C.assess(p, now=NOW)
        v = rep['sources']['official_inactives']['verdicts']
        check('CADENCE_VIOLATION is raised', C.CADENCE_VIOLATION in v, v)
        check('and it is NOT a global stall', rep['global_stall'] is False,
              rep['global_stall'])
    finally:
        p.unlink()


def test_C_asymmetric_silence_is_the_2026_09_24_case():
    print('\nC. dark among current peers -- the case that was missed')
    p = _manifest(dict(_HEALTHY, official_inactives=(236.0, 20, True)))
    try:
        rep = C.assess(p, now=NOW)
        v = rep['sources']['official_inactives']['verdicts']
        check('ASYMMETRIC_SOURCE_SILENCE is raised',
              C.ASYMMETRIC_SILENCE in v, v)
        check('peers stay CURRENT',
              rep['sources']['injuries']['verdicts'] == [C.CURRENT],
              rep['sources']['injuries']['verdicts'])
        check('the peer median is the healthy one, not the outlier',
              rep['peer_median_age_h'] < 12.0, rep['peer_median_age_h'])
        ok, d = raised(C.CadenceError,
                       lambda: C.assert_ready_for_slate(['official_inactives'],
                                                        report=rep),
                       'ASYMMETRIC_SOURCE_SILENCE')
        check('and the slate is refused before simulating', ok, d)
    finally:
        p.unlink()


def test_D_everything_dark_is_our_outage_not_a_websites():
    print('\nD. a different incident with a different response')
    p = _manifest({s: (30.0, 20, True) for s in _HEALTHY})
    try:
        rep = C.assess(p, now=NOW)
        check('global_stall is set', rep['global_stall'] is True, rep)
        ok, d = raised(C.CadenceError,
                       lambda: C.assert_ready_for_slate(['injuries'],
                                                        report=rep),
                       C.GLOBAL_STALL)
        check('the refusal says the runner stopped, not the feed', ok, d)
        check('no source is called asymmetric when all are equally stale',
              not any(C.ASYMMETRIC_SILENCE in r['verdicts']
                      for r in rep['sources'].values()),
              {s: r['verdicts'] for s, r in rep['sources'].items()})
    finally:
        p.unlink()


def test_E_never_succeeded_is_not_staleness():
    print('\nE. official_transactions: 684 attempts, zero successes')
    p = _manifest(dict(_HEALTHY, official_inactives=(1.0, 20, True)))
    with p.open('a') as fh:
        for i in range(30):
            t = NOW - dt.timedelta(hours=91 + i)
            fh.write(json.dumps(
                {'capture_id': t.strftime('%Y%m%dT%H%M%SZ'),
                 'source': 'official_transactions', 'state': 'BLOCKED',
                 'code': 'ENDPOINT_NOT_YET_VERIFIED', 'value': {}}) + '\n')
    try:
        rep = C.assess(p, now=NOW)
        r = rep['sources']['official_transactions']
        check('NEVER_SUCCEEDED, not a cadence violation',
              C.NEVER_SUCCEEDED in r['verdicts']
              and C.CADENCE_VIOLATION not in r['verdicts'], r['verdicts'])
        check('attempts are still counted', r['n_attempts'] == 30,
              r['n_attempts'])
        check('and there is no age to report', r['age_h'] is None, r['age_h'])
    finally:
        p.unlink()


def test_F_an_undeclared_source_is_not_assumed_fine():
    print('\nF. a cadence nobody declared cannot be violated')
    p = _manifest(dict(_HEALTHY, some_new_feed=(500.0, 3, True)))
    try:
        rep = C.assess(p, now=NOW)
        check('it reads NOT_ESTABLISHED',
              C.NOT_ESTABLISHED in rep['sources']['some_new_feed']['verdicts'],
              rep['sources']['some_new_feed']['verdicts'])
        ok, d = raised(C.CadenceError,
                       lambda: C.assert_ready_for_slate(['some_new_feed'],
                                                        report=rep),
                       'NOT_ESTABLISHED')
        check('and requiring it still refuses, rather than passing silently',
              ok, d)
        ok2, d2 = raised(C.CadenceError,
                         lambda: C.assert_ready_for_slate(['not_a_source'],
                                                          report=rep),
                         'ABSENT_FROM_CAPTURE_RECORD')
        check('a source absent from the record refuses too', ok2, d2)
    finally:
        p.unlink()


def test_G_the_live_manifest_today():
    print('\nG. what the real capture record says right now')
    rep = C.assess()
    if not rep['sources']:
        check('manifest readable', False, 'no sources parsed')
        return
    inact = rep['sources'].get('official_inactives', {})
    check('official_inactives is flagged',
          any(v != C.CURRENT for v in inact.get('verdicts', [])),
          inact.get('verdicts'))
    check('official_transactions has never succeeded',
          C.NEVER_SUCCEEDED in rep['sources'].get(
              'official_transactions', {}).get('verdicts', []),
          rep['sources'].get('official_transactions', {}).get('verdicts'))
