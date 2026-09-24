"""The pregame readiness matrix, and the freshness verdict it depends on.

WHAT THIS MODULE ASSERTS
========================
1. FRESH NO LONGER MEANS "NOBODY CHECKED". `run_input.verify` used to return
   FRESH whenever `required_max_age_h` was None, which was its default, so a
   family with no declared bound could never be STALE. Measured on the live
   ATL @ GB contract: official_inactives was pinned to a capture 214.41 hours
   old -- nine days -- and verified FRESH with ok=True. It now reports
   AGE_NOT_BOUNDED, and the four REQUIRED families are checked against the
   per-family bounds the project already declared in governed_thresholds.
2. A CALLER MAY TIGHTEN A GOVERNED BOUND BUT NEVER LOOSEN IT.
3. AGE_NOT_BOUNDED IS NOT A PASS IN THE MATRIX EITHER. It renders UNKNOWN,
   and UNKNOWN is listed as NOT CHECKED rather than coloured green.
4. EXECUTION AND SEALING BLOCKERS ARE NOT MERGED. A run blocked only on
   sealing is still worth executing -- that is what UNSEALED_RESEARCH_OUTPUT
   is for -- so collapsing them would tell an operator to abandon a run whose
   numbers are fine.
5. THE MATRIX IS A CLOSED DECLARED SET. An undeclared layer raises rather
   than quietly appearing, and every declared layer gets exactly one row.
6. IT REPRODUCES TONIGHT'S REAL STATE: execution ELIGIBLE, sealing REFUSED by
   team_volume and artifact_sealing.
"""
import datetime as dt
import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import pregame_readiness as PR  # noqa: E402
from nfl.truth import run_input as RI  # noqa: E402

PASSED = FAILED = BLOCKED = 0

RUN = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'unsealed' / \
    '2026_03_ATL_GB' / '2fc4e9599f0889f1'


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def _contract():
    return json.loads((RUN / 'RUN_INPUT_CONTRACT.json').read_text())


def test_fresh_no_longer_means_nobody_checked():
    if not RUN.is_dir():
        return blocked('freshness verdicts', f'{RUN} absent')
    rep = RI.verify(_contract(), root=pathlib.Path(_ROOT))
    pf = rep['per_family']

    oi = pf.get('official_inactives') or {}
    chk('the nine-day-old official_inactives is NOT reported FRESH',
        oi.get('verdict') == RI.AGE_NOT_BOUNDED, str(oi.get('verdict')))
    chk('and its real age is carried, not hidden',
        (oi.get('age_hours') or 0) > 200, str(oi.get('age_hours')))
    chk('because no max age is declared for that family',
        oi.get('max_age_hours') is None)

    for fam, expect in (('injuries', 6.0), ('depth_charts', 24.0),
                        ('weekly_rosters', 24.0), ('schedules', 168.0)):
        row = pf.get(fam) or {}
        chk(f'{fam} is checked against its governed bound of {expect}h',
            row.get('max_age_hours') == expect, str(row.get('max_age_hours')))
    chk('and every required family verifies FRESH on this contract',
        all((pf.get(f) or {}).get('verdict') == RI.FRESH
            for f in ('injuries', 'depth_charts', 'weekly_rosters',
                      'schedules')))
    chk('so the contract is still consumable and nothing broke today',
        rep['ok'] and not rep['required_failures'],
        json.dumps(rep['required_failures']))


def test_a_caller_may_tighten_a_governed_bound_but_never_loosen_it():
    if not RUN.is_dir():
        return blocked('bound arithmetic', f'{RUN} absent')
    c = _contract()
    tight = RI.verify(c, root=pathlib.Path(_ROOT), required_max_age_h=1.0)
    chk('a 1h caller bound makes a 3.37h injuries capture STALE',
        (tight['per_family']['injuries'] or {}).get('verdict') == RI.STALE,
        str(tight['per_family']['injuries'].get('verdict')))
    chk('and that makes the contract NOT consumable',
        not tight['ok'] and 'injuries' in tight['required_failures'])

    loose = RI.verify(c, root=pathlib.Path(_ROOT), required_max_age_h=10000.0)
    chk('a huge caller bound does NOT loosen the governed 6h on injuries',
        (loose['per_family']['injuries'] or {}).get('max_age_hours') == 6.0,
        str(loose['per_family']['injuries'].get('max_age_hours')))


def test_age_not_bounded_is_not_a_pass_in_the_matrix():
    contract = {'game_id': 'X', 'cutoff_utc': '2026-09-24T15:30:00Z',
                'entries': {'schedules': {'sha256': 'a', 'capture_id': 'c'},
                            'weekly_rosters': {'sha256': 'b'},
                            'depth_charts': {'sha256': 'c'},
                            'injuries': {'sha256': 'd'}}}
    rep = {'per_family': {'schedules': {'verdict': 'AGE_NOT_BOUNDED'},
                          'weekly_rosters': {'verdict': 'FRESH'},
                          'depth_charts': {'verdict': 'STALE'},
                          'injuries': {'verdict': 'MISSING'}}}
    m = PR.build(contract, verify_report=rep)
    by = {r['layer']: r for r in m['rows']}
    chk('AGE_NOT_BOUNDED renders UNKNOWN, not PASS',
        by['schedule']['state'] == PR.UNKNOWN, by['schedule']['state'])
    chk('and UNKNOWN is listed as not checked',
        'schedule' in m['unknown_layers'])
    chk('FRESH renders PASS', by['roster']['state'] == PR.PASS)
    chk('STALE renders PARTIAL', by['depth_chart']['state'] == PR.PARTIAL)
    chk('MISSING renders BLOCKED', by['injury_content']['state'] == PR.BLOCKED)
    chk('and a MISSING required family blocks EXECUTION',
        'injury_content' in m['blocks_execution'])


def test_execution_and_sealing_blockers_are_not_merged():
    contract = {'game_id': 'X', 'cutoff_utc': '2026-09-24T15:30:00Z',
                'entries': {'schedules': {'sha256': 'a'},
                            'weekly_rosters': {'sha256': 'b'},
                            'depth_charts': {'sha256': 'c'},
                            'injuries': {'sha256': 'd'}}}
    rep = {'verdicts': {'schedules': 'FRESH', 'weekly_rosters': 'FRESH',
                        'depth_charts': 'FRESH', 'injuries': 'FRESH'}}
    m = PR.build(contract, verify_report=rep,
                 team_volume={'state': 'BLOCKED', 'detail': 'stale'},
                 extra={'artifact_sealing': {'state': PR.BLOCKED,
                                             'detail': 'sealing refused'}})
    chk('a sealing-only blocker leaves execution ELIGIBLE',
        m['execution_verdict'] == 'ELIGIBLE', m['execution_verdict'])
    chk('while sealing is REFUSED', m['sealing_verdict'] == 'REFUSED')
    chk('and the two blocker lists are separate',
        m['blocks_sealing'] and not m['blocks_execution'],
        f"{m['blocks_sealing']} / {m['blocks_execution']}")


def test_the_matrix_is_a_closed_declared_set():
    contract = {'game_id': 'X', 'cutoff_utc': 'z',
                'entries': {'schedules': {'sha256': 'a'}}}
    m = PR.build(contract)
    chk('every declared layer gets exactly one row',
        sorted(r['layer'] for r in m['rows'])
        == sorted(n for n, _ in PR.LAYERS))
    try:
        PR.build(contract, extra={'invented_layer': {'state': PR.PASS}})
        chk('an undeclared layer raises', False, 'it was accepted')
    except PR.ReadinessError:
        chk('an undeclared layer raises', True)
    try:
        PR.build({'game_id': 'X', 'entries': {}})
        chk('an empty contract raises', False, 'it was accepted')
    except PR.ReadinessError:
        chk('an empty contract raises', True)


def test_truncated_injury_feed_is_partial_not_pass():
    row = PR.espn_completeness({'truncated': True, 'page_cap': 25,
                                'n_clubs': 32, 'n_clubs_at_cap': 32})
    chk('a fully capped feed is PARTIAL', row['state'] == PR.PARTIAL)
    chk('and says COVERAGE_NOT_ESTABLISHED / SUSPECTED_TRUNCATION',
        'SUSPECTED_TRUNCATION' in row['detail'])
    chk('and refuses the absence-is-health reading',
        'never health' in row['detail'])
    chk('no truncation report at all is UNKNOWN, not PASS',
        PR.espn_completeness(None)['state'] == PR.UNKNOWN)


def test_it_reproduces_tonights_real_state():
    if not RUN.is_dir():
        return blocked('live matrix', f'{RUN} absent')
    c = _contract()
    st = json.loads((RUN / 'run_status.json').read_text())
    rep = RI.verify(c, root=pathlib.Path(_ROOT))
    csf = st.get('current_season_input_freshness') or {}
    tv = {'state': 'BLOCKED'
          if csf.get('code') == 'CURRENT_SEASON_INPUT_STALE' else csf.get('state'),
          'detail': (csf.get('detail') or '')[:120]}
    m = PR.build(c, verify_report=rep, team_volume=tv,
                 truncation={'truncated': True, 'page_cap': 25,
                             'n_clubs': 32, 'n_clubs_at_cap': 32},
                 extra={'artifact_sealing': {
                     'state': PR.BLOCKED,
                     'detail': (st.get('first_failure') or {}).get('code', '')}},
                 now=dt.datetime(2026, 9, 24, 19, 0, tzinfo=dt.timezone.utc),
                 kickoff=dt.datetime(2026, 9, 25, 0, 15, tzinfo=dt.timezone.utc))
    chk('execution is ELIGIBLE', m['execution_verdict'] == 'ELIGIBLE',
        m['execution_verdict'])
    chk('sealing is REFUSED', m['sealing_verdict'] == 'REFUSED')
    chk('blocked by team_volume', 'team_volume' in m['blocks_sealing'])
    chk('and by artifact_sealing', 'artifact_sealing' in m['blocks_sealing'])
    chk('the four evidence layers pass',
        all(r['state'] == PR.PASS for r in m['rows']
            if r['layer'] in ('schedule', 'roster', 'depth_chart',
                              'injury_content')))
    chk('injury completeness is PARTIAL, separate from its content',
        {r['layer']: r['state'] for r in m['rows']}['injury_completeness']
        == PR.PARTIAL)
    chk('official inactives are DEFERRED this far from kickoff',
        {r['layer']: r['state'] for r in m['rows']}['official_inactives']
        == PR.DEFERRED)


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
