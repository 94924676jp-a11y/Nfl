"""The frozen baseline must be comparable by program, not by eye.

WHAT THIS GUARDS

`DK_WEEK3_EARLY_BASELINE.json` exists to be compared against tomorrow morning.
A differ that quietly reports "no change" is the single most dangerous thing in
that sentence, so the tests that matter most here are the ones establishing that
it CANNOT report a clean comparison when it did not make one:

  * no pool rows on a side          -> NOTHING_TO_COMPARE, not an empty diff
  * rows present but with no dk_id  -> NOTHING_TO_COMPARE, because joining on
                                       name and team instead is DEF-082
  * a different contest             -> DIFFERENT_CONTEXT refuses before diffing,
                                       since a changed kickoff or game set is a
                                       different slate, not news within one
  * an identity that stopped        -> FAIL, so a regression in our own chain
    resolving                          cannot pass as an ordinary slate change

And the two symmetric properties a differ is worthless without: comparing a
snapshot with itself finds nothing, and comparing it with exactly one mutation
finds exactly that mutation and nothing else.

THE DST TRAP, WHICH IS WHY `_identity_applies` EXISTS

On the real baseline 24 rows carry no `gsis_id`: 18 are DST, which never have a
player id under any circumstances, and 6 are players the identity chain failed
on. A differ that reads a missing id as "unresolved" would report 24 unresolved
identities, and worse, would report every DST as having "stopped resolving" the
moment the other side was built by a different code path. That is a
manufactured defect of exactly the kind the project forbids -- a defect defined
against a conflation rather than against the data.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.dfs.salaries import baseline_diff as BD                # noqa: E402
from sportsplatform.governance.outcome import State            # noqa: E402

PASSED = FAILED = 0
BASELINE = pathlib.Path(_ROOT) / 'nfl/dfs/salaries/DK_WEEK3_EARLY_BASELINE.json'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _snap(rows, **slate):
    s = {'kickoff': '09/27/2026 01:00PM ET', 'n_games': 1,
         'games': [['PHI', 'DAL']]}
    s.update(slate)
    s['pool_rows'] = rows
    return {'slate': s}


def _r(dk_id='1', **kw):
    d = {'dk_id': dk_id, 'dk_name': 'A Player', 'dk_pos': 'WR', 'team': 'PHI',
         'salary': 5000, 'gsis_id': '00-0012345',
         'match_method': 'EXACT_NAME_TEAM'}
    d.update(kw)
    return d


# ======================================= it cannot fake a clean comparison

def test_no_rows_is_not_an_empty_diff():
    o = BD.diff(_snap([]), _snap([_r()]))
    check('an empty side refuses', o.state is not State.PASS, str(o.state))
    check('with NOTHING_TO_COMPARE', o.code == 'NOTHING_TO_COMPARE', str(o.code))
    check('and it does NOT say unchanged', o.code != 'SLATE_UNCHANGED',
          str(o.code))


def test_rows_without_dk_id_refuse_rather_than_join_on_name():
    rows = [{'dk_name': 'A Player', 'team': 'PHI', 'salary': 5000}]
    o = BD.diff(_snap(rows), _snap(rows))
    check('unkeyable rows refuse', o.state is not State.PASS, str(o.state))
    check('with NOTHING_TO_COMPARE', o.code == 'NOTHING_TO_COMPARE', str(o.code))


def test_a_different_contest_is_refused_before_diffing():
    a = _snap([_r()])
    b = _snap([_r()], kickoff='09/27/2026 04:25PM ET')
    o = BD.contest_identity(a, b)
    check('a different kickoff refuses', o.state is not State.PASS, str(o.state))
    check('with DIFFERENT_CONTEST', o.code == 'DIFFERENT_CONTEST', str(o.code))
    b2 = _snap([_r()], games=[['KC', 'MIA']])
    o2 = BD.contest_identity(a, b2)
    check('a different game set refuses too',
          o2.code == 'DIFFERENT_CONTEST', str(o2.code))


def test_an_unstated_contest_defers_rather_than_assuming_sameness():
    o = BD.contest_identity({'slate': {}}, _snap([_r()]))
    check('an unstated contest does not pass', o.state is not State.PASS,
          str(o.state))
    check('it defers', o.code == 'CONTEST_IDENTITY_NOT_STATED', str(o.code))


def test_same_contest_passes():
    o = BD.contest_identity(_snap([_r()]), _snap([_r()]))
    check('identical contest identity passes', o.state is State.PASS,
          f'{o.state} {o.code}')


# ================================================ the symmetric properties

def test_a_snapshot_against_itself_finds_nothing():
    s = _snap([_r('1'), _r('2', dk_name='B Player', salary=3000)])
    o = BD.diff(s, copy.deepcopy(s))
    check('self-comparison passes', o.state is State.PASS, f'{o.state} {o.code}')
    check('and reports SLATE_UNCHANGED', o.code == 'SLATE_UNCHANGED', str(o.code))
    check('with zero differences', o.value['n_differences'] == 0,
          str(o.value['n_differences']))


def test_one_salary_change_is_found_and_nothing_else_is():
    before = _snap([_r('1'), _r('2', dk_name='B Player')])
    after = copy.deepcopy(before)
    after['slate']['pool_rows'][1]['salary'] = 7777
    o = BD.diff(before, after)
    check('a changed price is a change', o.code == 'SLATE_CHANGED', str(o.code))
    check('exactly one difference', o.value['n_differences'] == 1,
          str(o.value['n_differences']))
    ch = o.value['changed'].get('salary') or []
    check('the salary change is reported', len(ch) == 1, str(ch))
    if ch:
        check('with both values', (ch[0]['before'], ch[0]['after'])
              == (5000, 7777), str(ch[0]))
    check('nothing was reported added', not o.value['added'], str(o.value['added']))
    check('nothing was reported removed', not o.value['removed'],
          str(o.value['removed']))


def test_added_and_removed_rows_are_reported_separately():
    before = _snap([_r('1'), _r('2', dk_name='Gone')])
    after = _snap([_r('1'), _r('3', dk_name='New')])
    o = BD.diff(before, after)
    check('one added', [x['dk_id'] for x in o.value['added']] == ['3'],
          str(o.value['added']))
    check('one removed', [x['dk_id'] for x in o.value['removed']] == ['2'],
          str(o.value['removed']))
    check('two differences total', o.value['n_differences'] == 2,
          str(o.value['n_differences']))


def test_a_field_absent_on_one_side_is_not_an_unchanged_field():
    before = _snap([_r('1')])
    after = copy.deepcopy(before)
    del after['slate']['pool_rows'][0]['salary']
    o = BD.diff(before, after)
    fa = o.value['field_absent_one_side'].get('salary') or []
    check('the absence is reported', len(fa) == 1, str(fa))
    check('and not counted as equal', o.value['n_differences'] >= 1,
          str(o.value['n_differences']))
    check('it is NOT reported as a changed value',
          'salary' not in o.value.get('changed', {}),
          str(o.value.get('changed')))


# ============================================ identity: the two None states

def test_identity_that_stopped_resolving_is_a_failure_not_news():
    before = _snap([_r('1')])
    after = copy.deepcopy(before)
    after['slate']['pool_rows'][0]['gsis_id'] = None
    o = BD.diff(before, after)
    check('it does not pass', o.state is not State.PASS, str(o.state))
    check('with IDENTITY_REGRESSED', o.code == 'IDENTITY_REGRESSED', str(o.code))
    check('and names the row',
          len(o.evidence.get('identity_stopped_resolving') or []) == 1,
          str(o.evidence.get('identity_stopped_resolving')))


def test_an_identity_resolving_since_baseline_is_reported_as_progress():
    before = _snap([_r('1', gsis_id=None, match_method=None)])
    after = copy.deepcopy(before)
    after['slate']['pool_rows'][0]['gsis_id'] = '00-0099999'
    after['slate']['pool_rows'][0]['match_method'] = 'EXACT_NAME_TEAM'
    o = BD.diff(before, after)
    res = o.value['identity_resolved_since_baseline']
    check('a newly resolved identity is reported', len(res) == 1, str(res))
    check('and it is not a failure', o.state is State.PASS, str(o.state))


def test_a_dst_is_never_an_unresolved_identity():
    """The conflation this module refuses: no id vs never has an id."""
    dst = _r('9', dk_name='Eagles', dk_pos='DST', gsis_id=None,
             match_method='NOT_A_PERSON')
    s = _snap([dst])
    o = BD.diff(s, copy.deepcopy(s))
    check('a DST pair is unchanged, not regressed',
          o.code == 'SLATE_UNCHANGED', str(o.code))
    check('the DST is excluded from the identity comparison',
          o.value['n_identity_not_applicable'] == 1,
          str(o.value['n_identity_not_applicable']))
    check('and is not listed as stopped resolving',
          not o.value['identity_stopped_resolving'],
          str(o.value['identity_stopped_resolving']))


def test_a_dst_is_excluded_even_without_the_match_method():
    """Position alone is enough; the marker is belt and braces."""
    dst = _r('9', dk_name='Eagles', dk_pos='DST', gsis_id=None,
             match_method=None)
    s = _snap([dst])
    o = BD.diff(s, copy.deepcopy(s))
    check('position DST alone excludes it', o.code == 'SLATE_UNCHANGED',
          str(o.code))


def test_availability_is_never_inferred_from_price():
    before = _snap([_r('1')])
    after = copy.deepcopy(before)
    after['slate']['pool_rows'][0]['salary'] = 2500
    o = BD.diff(before, after)
    ev = o.value
    check('a large price drop is reported as a price change only',
          list(ev.get('changed', {})) == ['salary'], str(list(ev.get('changed', {}))))
    check('the artifact says availability is not computed here',
          'AVAILABILITY_NOT_COMPUTED_HERE' in ev, str(sorted(ev)))
    joined = json.dumps(ev).lower()
    for word in ('inactive', 'is_out', 'not_playing'):
        check(f'no {word!r} claim is emitted from a price move',
              f'"{word}"' not in joined or 'not_computed' in joined, word)


# ======================================= the real baseline is comparable

def test_the_committed_baseline_carries_rows_and_compares_with_itself():
    if not BASELINE.exists():
        print('  skip  baseline artifact absent')
        return
    d = json.loads(BASELINE.read_text())
    rows = (d.get('slate') or {}).get('pool_rows')
    check('the baseline carries its pool rows', isinstance(rows, list)
          and len(rows) == 457, str(len(rows) if isinstance(rows, list) else rows))
    ident = BD.contest_identity(d, copy.deepcopy(d))
    check('it is the same contest as itself', ident.state is State.PASS,
          f'{ident.state} {ident.code}')
    checked = ident.value if isinstance(ident.value, dict) else {}
    check('a KICKOFF field is actually among those compared -- otherwise the '
          'check is decorative on the artifact it exists for',
          any(k in checked for k in BD.CONTEST_REQUIRED_ONE_OF),
          str(sorted(checked)))
    check('and the game set is compared too', 'games' in checked,
          str(sorted(checked)))


def test_a_snapshot_with_no_kickoff_defers_rather_than_comparing_games_alone():
    a = _snap([_r()])
    del a['slate']['kickoff']
    o = BD.contest_identity(a, _snap([_r()]))
    check('a stated game set without a kickoff does not pass',
          o.state is not State.PASS, str(o.state))
    check('it defers on the missing kickoff',
          o.code == 'CONTEST_KICKOFF_NOT_STATED', str(o.code))


def test_the_real_baseline_kickoff_change_is_caught():
    if not BASELINE.exists():
        print('  skip  baseline artifact absent')
        return
    d = json.loads(BASELINE.read_text())
    after = copy.deepcopy(d)
    after['slate']['kickoff_utc'] = '2026-09-27T20:25:00Z'
    o = BD.contest_identity(d, after)
    check('a moved kickoff on the real baseline refuses',
          o.code == 'DIFFERENT_CONTEST', str(o.code))
    o = BD.diff(d, copy.deepcopy(d))
    check('and diffs clean against itself', o.code == 'SLATE_UNCHANGED',
          f'{o.code} {o.detail}')
    if o.value:
        check('the 18 DST are excluded from identity, not called unresolved',
              o.value['n_identity_not_applicable'] == 18,
              str(o.value['n_identity_not_applicable']))


def test_a_mutated_copy_of_the_real_baseline_finds_exactly_the_mutation():
    if not BASELINE.exists():
        print('  skip  baseline artifact absent')
        return
    d = json.loads(BASELINE.read_text())
    after = copy.deepcopy(d)
    after['slate']['pool_rows'][0]['salary'] = 12345
    removed = after['slate']['pool_rows'].pop(5)
    o = BD.diff(d, after)
    check('the real baseline detects the mutation', o.code == 'SLATE_CHANGED',
          str(o.code))
    check('exactly two differences', o.value['n_differences'] == 2,
          str(o.value['n_differences']))
    check('the removed row is named',
          [x['dk_id'] for x in o.value['removed']] == [removed['dk_id']],
          str(o.value['removed']))


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
