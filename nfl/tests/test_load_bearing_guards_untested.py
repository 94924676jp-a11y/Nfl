"""Two guards that STOP production and had no test at all.

The census listed both as `EXTERNALLY_CALLED` with effect `STOP` and
`callers_test: 0` -- load-bearing in production, with nothing verifying that
they fire on the input they exist to catch. That is the reverse of DEF-065 and
just as bad: there, a correct control protected nothing; here, something real
depends on logic nobody has checked.

  assert_inactive_qbs_own_nothing   run_forecast.py:969        STOP
  assert_every_player_tagged        dfs/portfolio_guard.py:72  STOP

Both are pure functions over data, so both can be tested honestly without
inventing a fixture that stands in for the thing under test.
"""
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State            # noqa: E402
from nfl.production import qb_accounting as QA                 # noqa: E402
from nfl.production.dfs import projection_confidence as PC     # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  PASS {label}' + (f' -- {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f' -- {detail}' if detail else ''))


QB1, QB2 = '00-0000011', '00-0000022'
ROWS = [{'gsis_id': QB1}, {'gsis_id': QB2}]


def _draws(db, att):
    return {'db': np.asarray(db, float), 'att': np.asarray(att, float)}


def test_an_inactive_qb_holding_a_single_dropback_is_a_FAIL():
    print('\n[1] the max, not the mean -- one draw is enough')
    # QB1 is inactive and holds a dropback in exactly ONE of 1000 draws. The
    # docstring is explicit that a mean of 0.0004 is one draw holding a
    # dropback, "and that is still a quarterback who was not dressed taking a
    # snap in a simulated world". So the check must be on the max.
    db = np.zeros((2, 1000))
    db[0, 417] = 1.0
    r = QA.assert_inactive_qbs_own_nothing(_draws(db, np.zeros((2, 1000))),
                                           ROWS, [QB1])
    check('one draw out of a thousand FAILS', r.state is State.FAIL,
          f'{r.state.name}[{r.code}]')
    check('with the named code', r.code == 'QB_INACTIVE_STILL_OWNS_DROPBACKS',
          str(r.code))
    ev = r.as_dict()['evidence']
    check('and it names the offender and the metric',
          QB1 in (ev.get('offenders') or {})
          and 'db' in ev['offenders'][QB1], str(ev.get('offenders')))
    check('the mean would have hidden it',
          abs(float(db[0].mean()) - 0.001) < 1e-9,
          f'mean={float(db[0].mean())} -- a tolerance on the mean passes this')


def test_a_clean_allocation_PASSES_and_says_what_it_checked():
    print('\n[2] and PASS when the inactive QB holds exactly zero')
    z = np.zeros((2, 50))
    act = np.zeros((2, 50))
    act[1] = 3.0                      # QB2 is dressed and owns dropbacks
    r = QA.assert_inactive_qbs_own_nothing(_draws(act, z), ROWS, [QB1])
    check('it passes', r.state is State.PASS, f'{r.state.name}[{r.code}]')
    check('and reports how many inactive rows it checked',
          r.as_dict()['evidence'].get('n_inactive_rows_checked') == 1,
          str(r.as_dict()['evidence'].get('n_inactive_rows_checked')))
    check('an active QB owning dropbacks is not an offence',
          r.state is State.PASS, 'only the inactive list is examined')


def test_no_inactive_list_is_DEFERRED_never_PASS():
    print('\n[3] the absence of the question is not an answer to it')
    z = np.zeros((2, 10))
    r = QA.assert_inactive_qbs_own_nothing(_draws(z, z), ROWS, [])
    check('state is DEFERRED', r.state is State.DEFERRED,
          f'{r.state.name}[{r.code}]')
    check('NOT PASS', r.state is not State.PASS,
          'a pass here would record a check that never ran')
    check('with the named code',
          r.code == 'QB_INACTIVE_OWNERSHIP_NOT_ESTABLISHED', str(r.code))
    check('and it says what it is owed',
          'official_inactive_ids' in str(r.as_dict()['evidence'].get('owed')),
          str(r.as_dict()['evidence'].get('owed')))


def test_an_untagged_player_is_a_refusal_not_a_default():
    print('\n[4] absence of a warning is not a statement of confidence')
    good = next(iter(PC.TAGS))
    r = PC.assert_every_player_tagged([QB1, QB2], {QB1: good})
    check('an untagged player FAILS', r.state is State.FAIL,
          f'{r.state.name}[{r.code}]')
    check('with the named code', r.code == 'PROJECTION_UNTAGGED', str(r.code))
    check('and names who was untagged',
          r.as_dict()['evidence'].get('untagged') == [QB2],
          str(r.as_dict()['evidence'].get('untagged')))
    bad = PC.assert_every_player_tagged([QB1], {QB1: 'NOT_A_REAL_TAG'})
    check('an invalid tag also FAILS', bad.state is State.FAIL,
          f'{bad.state.name}[{bad.code}]')
    check('and is reported separately from untagged',
          bad.as_dict()['evidence'].get('invalid_tag') == [QB1]
          and bad.as_dict()['evidence'].get('untagged') == [],
          'an unknown tag and a missing tag are different defects')
    ok = PC.assert_every_player_tagged([QB1, QB2], {QB1: good, QB2: good})
    check('a fully tagged pool passes', ok.state is State.PASS,
          f'{ok.state.name}[{ok.code}]')


def test_the_generator_trap_in_the_evidence_count():
    """`player_ids` is iterated twice, so a generator loses the count.

    The function walks `player_ids` in a genexp to find the untagged, and then
    reports `'n_players': len(list(player_ids))`. For a list both work. For a
    GENERATOR the first pass exhausts it, so the evidence says zero players
    were considered while the verdict is computed from all of them.

    Recorded rather than fixed: every production caller today passes a list or
    a set, so this is latent, and changing a signature's iteration contract is
    not a change to make on the way past. What the check must not do is report
    a count it did not measure.
    """
    print('\n[5] the evidence count under a generator')
    good = next(iter(PC.TAGS))
    lst = PC.assert_every_player_tagged([QB1, QB2], {QB1: good})
    gen = PC.assert_every_player_tagged((p for p in (QB1, QB2)), {QB1: good})
    ln = lst.as_dict()['evidence'].get('n_players')
    gn = gen.as_dict()['evidence'].get('n_players')
    check('a list reports the real count', ln == 2, str(ln))
    check('the VERDICT is identical either way',
          lst.state is gen.state and lst.code == gen.code,
          f'{lst.state.name} vs {gen.state.name}')
    check('but a generator reports n_players = 0', gn == 0,
          f'list={ln} generator={gn} -- latent: every production caller passes '
          f'a list or set today')
    check('and the untagged list is still right under a generator',
          gen.as_dict()['evidence'].get('untagged') == [QB2],
          'so the defect is in the reported evidence, not the decision')


def main():
    print(__doc__.strip().splitlines()[0])
    test_an_inactive_qb_holding_a_single_dropback_is_a_FAIL()
    test_a_clean_allocation_PASSES_and_says_what_it_checked()
    test_no_inactive_list_is_DEFERRED_never_PASS()
    test_an_untagged_player_is_a_refusal_not_a_default()
    test_the_generator_trap_in_the_evidence_count()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
