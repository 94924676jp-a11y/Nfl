"""Capture freshness: it names its tree, and it refuses rather than guessing.

WHAT THIS GUARDS, AND WHY IT IS NOT A HYPOTHETICAL

On 2026-09-19 a freshness reading taken from this branch's working tree
reported every source between 39.7 and 141.3 hours old and was about to be
written up as a Sunday-readiness blocker. The scheduled capture was healthy the
whole time, writing to `capture-prod`, with the six core sources half an hour
old. The number was real; the tree was wrong.

So the property under test is not "are the sources fresh today" -- that changes
hourly and a test asserting it would be a clock, not a test. It is:

  * an age is never reported without the tree it was measured in;
  * a tree that cannot be SHOWN current with the capture surface cannot
    produce a PASS, whatever the ages say;
  * ABSENT, ASSIGNED and out-of-window are distinct from STALE, because they
    need different actions and a single flag would send an operator to the
    wrong one;
  * the pregame clock replaces the standing expiry, and says which it used.

Every case below is driven by synthetic manifest rows, so the file holds when
the day changes.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import capture_freshness as CF                # noqa: E402
from sportsplatform.governance.outcome import State               # noqa: E402

PASSED = FAILED = 0
NOW = dt.datetime(2026, 9, 20, 12, 0, 0, tzinfo=dt.timezone.utc)


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _row(source, ago_hours, **v):
    t = NOW - dt.timedelta(hours=ago_hours)
    val = {'retrieved_at': t.isoformat(), 'blob': f'nfl/vintage/{source}.x.gz',
           'sha256': 'a' * 64}
    val.update(v)
    return {'source': source, 'state': 'PASS', 'code': 'CAPTURED',
            'capture_id': t.strftime('%Y%m%dT%H%M%SZ'), 'value': val}


def _all_fresh_rows():
    """Every REQUIRED source captured one hour ago."""
    return [_row(s, 1.0) for s, spec in CF.REGISTRY.items()
            if spec.get('required_for')]


def _surface(state, behind=None):
    return {'repo': _ROOT, 'branch': 'b', 'head': 'h' * 40,
            'capture_surface': CF.CAPTURE_SURFACE, 'surface_head': 's' * 40,
            'surface_state': state, 'behind_surface_commits': behind,
            'why': 'test'}


# ================================================== the tree is not optional

def test_an_age_is_never_reported_without_the_tree_it_came_from():
    m = CF.measure(rows=_all_fresh_rows(), now=NOW)
    check('measure carries a tree_identity', 'tree_identity' in m)
    ti = m['tree_identity']
    for k in ('repo', 'branch', 'head', 'capture_surface', 'surface_state'):
        check(f'the tree identity names {k}', k in ti)
    check('and without --verify-surface it says UNVERIFIED rather than '
          'implying current',
          ti['surface_state'] == CF.CODE_TREE_UNVERIFIED, ti['surface_state'])
    check('the declared capture surface is not the forecast branch',
          CF.CAPTURE_SURFACE == 'capture-prod', CF.CAPTURE_SURFACE)


def test_an_unplaceable_tree_cannot_pass_however_fresh_the_sources_are():
    """The 2026-09-19 error, inverted and made impossible.

    Every required source one hour old -- as fresh as this system ever gets --
    and the verdict is still BLOCKED, because nothing has shown that this tree
    is the tree the capture writes to.
    """
    m = CF.measure(rows=_all_fresh_rows(), now=NOW)
    req = [r for r in m['sources'].values() if r['required_for']]
    check('every required source measures FRESH',
          all(r['status'] == CF.CODE_FRESH for r in req),
          str([(r['source'], r['status']) for r in req]))
    o = CF.assess(m)
    check('and the overall verdict is still BLOCKED',
          o.state is State.BLOCKED, f'{o.state} {o.code}')
    check('under the tree code, not the source code',
          o.code == CF.CODE_TREE_UNVERIFIED, o.code)


def test_a_tree_behind_the_surface_is_blocked_and_says_by_how_much():
    m = CF.measure(rows=_all_fresh_rows(), now=NOW)
    m['tree_identity'] = _surface(CF.CODE_TREE_BEHIND, behind=7)
    o = CF.assess(m)
    check('a tree behind the surface blocks', o.state is State.BLOCKED)
    check('under CAPTURE_TREE_BEHIND_SURFACE', o.code == CF.CODE_TREE_BEHIND)
    check('and the distance is a measured number, not a word',
          o.evidence['tree_identity']['behind_surface_commits'] == 7)


def test_a_tree_current_with_the_surface_and_fresh_sources_passes():
    m = CF.measure(rows=_all_fresh_rows(), now=NOW)
    m['tree_identity'] = _surface('CAPTURE_TREE_CURRENT_WITH_SURFACE', 0)
    o = CF.assess(m)
    check('a placed tree with fresh required sources PASSES',
          o.state is State.PASS, f'{o.state} {o.code} {o.detail}')
    check('and it says which tree it passed in',
          'branch' in o.evidence['tree_identity'])


# =========================================== four statuses, not one flag

def test_absent_assigned_and_out_of_window_are_not_stale():
    rows = _all_fresh_rows()
    # official_inactives: captured, but 40 hours ago and no slate clock given.
    rows.append(_row('official_inactives', 40.0))
    m = CF.measure(rows=rows, now=NOW)
    s = m['sources']
    check('a source with no successful capture is ABSENT, not STALE',
          s['official_injury_report']['status'] == CF.CODE_ABSENT,
          s['official_injury_report']['status'])
    check('a source nobody here can capture is ASSIGNED, and names who owes it',
          s['official_transactions']['status'] == CF.CODE_ASSIGNED
          and 'OUT-' in (s['official_transactions']['assigned'] or ''),
          str(s['official_transactions']['assigned']))
    check('a game-anchored source outside its window is OUT_OF_WINDOW, '
          'because its age means nothing there',
          s['official_inactives']['status'] == 'CAPTURE_OUT_OF_WINDOW',
          s['official_inactives']['status'])
    check('and it still reports the age it has',
          s['official_inactives']['age_hours'] == 40.0)


def test_the_same_inactives_capture_is_stale_inside_the_window():
    """Identical bytes, identical age, opposite verdict -- and that is right.

    The final declaration is worthless ninety minutes before kickoff if it is
    forty hours old. Outside the window it is not evidence about this slate at
    all. One expiry constant cannot express both.
    """
    rows = _all_fresh_rows() + [_row('official_inactives', 40.0)]
    out = CF.measure(rows=rows, now=NOW)['sources']['official_inactives']
    inw = CF.measure(rows=rows, now=NOW,
                     hours_to_kickoff=1.0)['sources']['official_inactives']
    check('outside the window: not stale', out['status']
          == 'CAPTURE_OUT_OF_WINDOW', out['status'])
    check('inside the window: STALE', inw['status'] == CF.CODE_STALE,
          inw['status'])
    check('and the age is the same number in both', out['age_hours']
          == inw['age_hours'] == 40.0)
    check('the expiry in force is reported, not just applied',
          inw['expiry_hours'] == 1.5 and inw['expiry_rule'] == 'pregame',
          f"{inw['expiry_hours']} {inw['expiry_rule']}")


def test_the_pregame_clock_replaces_the_standing_expiry_and_says_so():
    rows = _all_fresh_rows() + [_row('injuries', 20.0)]
    std = CF.measure(rows=rows, now=NOW)['sources']['injuries']
    pre = CF.measure(rows=rows, now=NOW,
                     hours_to_kickoff=2.0)['sources']['injuries']
    check('20 hours old is fresh against the 48-hour standing expiry',
          std['status'] == CF.CODE_FRESH and std['expiry_rule'] == 'standing',
          f"{std['status']} {std['expiry_rule']}")
    check('and stale against the 12-hour pregame expiry',
          pre['status'] == CF.CODE_STALE and pre['expiry_rule'] == 'pregame',
          f"{pre['status']} {pre['expiry_rule']}")
    check('a source with no pregame expiry keeps its standing one',
          CF.measure(rows=rows, now=NOW, hours_to_kickoff=2.0)
          ['sources']['schedules']['expiry_rule'] == 'standing')


def test_every_expiry_states_why_it_is_what_it_is():
    """No silent constants. A number with no reason is a guess with a decimal."""
    for sid, spec in CF.REGISTRY.items():
        check(f'{sid} states its expiry basis',
              len((spec.get('expiry_basis') or '').strip()) > 30)
        check(f'{sid} declares a scope', spec.get('scope') in
              (CF.LEAGUE_WIDE, CF.GAME_ANCHORED))
        has = (spec.get('expiry_hours') is not None
               or spec.get('pregame_expiry_hours') is not None)
        check(f'{sid} has at least one expiry', has)
    check('the registry version is declared so it cannot change silently',
          isinstance(CF.REGISTRY_VERSION, int))


def test_a_source_in_the_manifest_and_not_in_the_registry_is_named():
    rows = _all_fresh_rows() + [_row('some_new_feed', 1.0)]
    m = CF.measure(rows=rows, now=NOW)
    check('an undeclared source is surfaced rather than ignored',
          m['undeclared_sources_present'] == ['some_new_feed'],
          str(m['undeclared_sources_present']))
    check('and it does not silently become a required input',
          'some_new_feed' not in m['sources'])


def test_a_required_source_that_is_stale_blocks_under_its_own_code():
    rows = [r for r in _all_fresh_rows() if r['source'] != 'schedules']
    rows.append(_row('schedules', 500.0))
    m = CF.measure(rows=rows, now=NOW)
    m['tree_identity'] = _surface('CAPTURE_TREE_CURRENT_WITH_SURFACE', 0)
    o = CF.assess(m)
    check('a stale REQUIRED source blocks', o.state is State.BLOCKED)
    check('under the source code, not the tree code',
          o.code == CF.CODE_REFUSE, o.code)
    check('and the refusal names the source, its age and its expiry',
          o.evidence['not_fresh'] and
          o.evidence['not_fresh'][0]['source'] == 'schedules' and
          o.evidence['not_fresh'][0]['age_hours'] == 500.0,
          json.dumps(o.evidence['not_fresh']))


def test_a_stale_source_nothing_requires_does_not_block_and_is_still_reported():
    """Visible is not the same as blocking. Both are needed."""
    rows = _all_fresh_rows() + [_row('espn_injuries_json', 500.0)]
    m = CF.measure(rows=rows, now=NOW)
    m['tree_identity'] = _surface('CAPTURE_TREE_CURRENT_WITH_SURFACE', 0)
    o = CF.assess(m)
    check('it is reported STALE',
          m['sources']['espn_injuries_json']['status'] == CF.CODE_STALE)
    check('and the run is not blocked by it, because nothing requires it',
          o.state is State.PASS, f'{o.state} {o.code}')
    check('the required set is named in the evidence either way',
          'espn_injuries_json' not in o.evidence['required_sources'])


def test_the_newest_evidence_carries_hash_and_provenance_not_just_a_time():
    rows = _all_fresh_rows() + [
        _row('schedules', 0.5, sha256='b' * 64, http_status=200,
             source_timestamp_header='2026-09-20T11:00:00Z', n_bytes=12345)]
    r = CF.measure(rows=rows, now=NOW)['sources']['schedules']
    e = r['newest_evidence']
    check('the newest capture carries its hash', e['sha256'] == 'b' * 64)
    check('its source timestamp where the source gives one',
          e['source_timestamp'] == '2026-09-20T11:00:00Z')
    check('its http status', e['http_status'] == 200)
    check('and its blob', bool(e['blob']))


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
