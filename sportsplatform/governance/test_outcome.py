"""Rule 001 tested against the eight real defects it exists to prevent.

Each section names an actual V7 failure from 2026-09-01 and asserts the
primitive would have caught it. A constitution tested only against invented
cases is a constitution nobody has checked.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.outcome import (Cause, Outcome, State, SilentSuccess, OutcomeError,
                                explicit, neither_result_nor_error, require,
                                combine)

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def test_no_state_without_a_name():
    print('\nA. every outcome carries a named code')
    for bad in ('', None, 'a sentence with spaces', 'lowercase'):
        try:
            Outcome(State.FAIL, bad, 'x')
            check(f'code {bad!r} refused', False, 'accepted')
        except OutcomeError:
            check(f'code {bad!r} refused', True)
    check('a good code is accepted',
          Outcome.fail('RATE_CUTOFF_LEAKAGE', 'x').code == 'RATE_CUTOFF_LEAKAGE')


def test_pass_must_carry_a_value():
    print('\nB. PASS cannot mean "nothing, but fine"')
    try:
        Outcome.ok('DONE')
        check('PASS with no value refused', False, 'accepted')
    except OutcomeError as e:
        check('PASS with no value refused', 'PASS_WITHOUT_VALUE' in str(e))
    check('and NOT_APPLICABLE is the honest alternative',
          Outcome.not_applicable('NO_GAMES', 'no MLB games on this date'
                                 ).state is State.NOT_APPLICABLE)
    try:
        Outcome.not_applicable('NO_GAMES', '')
        check('NOT_APPLICABLE without a reason refused', False, 'accepted')
    except OutcomeError as e:
        check('NOT_APPLICABLE without a reason refused',
              'NOT_APPLICABLE_UNEXPLAINED' in str(e))


def test_truthiness_is_refused():
    print('\nC. `if result:` cannot silently swallow a FAIL')
    # This is the single most common way a failure becomes a success.
    for o in (Outcome.fail('X', 'y'), Outcome.ok('X', 1),
              Outcome.deferred('X', 'y')):
        try:
            if o:
                pass
            check(f'{o.state.value} truthiness refused', False, 'allowed')
        except OutcomeError:
            check(f'{o.state.value} truthiness refused', True)


def test_defect_1_the_inert_guard():
    print('\nD. DEFECT 1 — the duplicate guard that never refused anything')
    # assert_batch_games_are_new read r['game_pk'] over rows that never had
    # one, built an empty set, and passed on every input.
    rows_without_pk = [{'game_date': '2026-09-01'}, {'game_date': '2026-09-01'}]
    seen = {r['game_pk'] for r in rows_without_pk if r.get('game_pk')}
    o = explicit(seen, 'DUPLICATE_CHECK_INPUT', 'the set of recorded game_pks')
    check('an empty identity set reads as BLOCKED, not "no clash"',
          o.state is State.BLOCKED, str(o))
    check('and it says why an empty set is not an answer',
          'absence' in o.detail, o.detail[:60])


def test_defect_2_keys_nothing_wrote():
    print('\nE. DEFECT 2 — provenance read from keys no producer wrote')
    game = {'away': {'confirmed': True}, 'home': {'confirmed': True}}
    observed = game.get('_lineup_observed_at_utc') or game.get('observed_at_utc')
    o = explicit(observed, 'LINEUP_OBSERVED_AT', 'the lineup observation time')
    check('a None provenance field is BLOCKED', o.state is State.BLOCKED)
    try:
        require(o)
        check('and unwrapping it raises', False, 'it returned')
    except SilentSuccess as e:
        check('and unwrapping it raises', 'LINEUP_OBSERVED_AT' in str(e))


def test_defect_3_the_dropped_games():
    print('\nF. DEFECT 3 — three games dropped on an unmapped abbreviation')
    recorded = ['ATL@WSH', 'MIA@KC', 'ATH@TEX']
    priced = ['ATL@WAS', 'MIA@KAN', 'OAK@TEX']      # vendor spellings
    unmapped = [g for g in recorded if g not in priced]
    # Rule 010: unknown mapping BLOCKS, it never drops.
    o = (Outcome.blocked('UNMAPPED_FIXTURE_LABEL',
                         f'{len(unmapped)} recorded games matched no fixture',
                         cause=Cause.DATA, unmapped=unmapped)
         if unmapped else Outcome.ok('ALL_MAPPED', priced))
    check('unmapped games BLOCK rather than vanish', o.state is State.BLOCKED)
    check('and every dropped game is named',
          o.evidence['unmapped'] == recorded, str(o.evidence))


def test_defect_4_not_yet_is_not_a_bug():
    print('\nG. DEFECT 4 — "lineups not posted yet" is DEFERRED, not FAIL')
    o = Outcome.deferred('LINEUP_NOT_CONFIRMED',
                         'both lineups have not posted yet',
                         owed=['CWS@HOU', 'NYY@LAA', 'STL@LAD'])
    check('it is deferred', o.state is State.DEFERRED)
    check('it is NOT terminal — the work is still owed',
          o.state.is_terminal is False)
    check('and the debt is named, not just counted',
          o.evidence['owed'] == ['CWS@HOU', 'NYY@LAA', 'STL@LAD'])
    check('while a real terminal absence IS terminal',
          Outcome.not_applicable('GAME_POSTPONED', 'game postponed'
                                 ).state.is_terminal is True)


def test_defect_8_neither_result_nor_error():
    print('\nH. DEFECT 8 — 39 fetches saved with content:None AND error:None')
    dead = {'url': 'https://example.invalid', 'content': None, 'error': None}
    o = neither_result_nor_error(dead, 'RESEARCH_FETCH', 'the fetch')
    check('it is caught', o is not None and o.state is State.BLOCKED)
    check('and named as an unreported failure',
          'unreported failure' in o.detail, o.detail[:70])
    live = {'url': 'x', 'content': 'real text', 'error': None}
    check('a real result passes through',
          neither_result_nor_error(live, 'R', 'the fetch') is None)
    reported = {'url': 'x', 'content': None, 'error': 'HTTP 500'}
    check('an honestly reported error passes through',
          neither_result_nor_error(reported, 'R', 'the fetch') is None)


def test_a_bare_return_cannot_reach_a_consumer():
    print('\nI. a stage that returns a bare value is refused at the boundary')
    for bare in (None, [], 0, 'done', {'ok': True}):
        try:
            require(bare)
            check(f'bare {type(bare).__name__} refused', False, 'accepted')
        except SilentSuccess as e:
            check(f'bare {type(bare).__name__} refused',
                  'STAGE_RETURNED_BARE_VALUE' in str(e))


def test_rollup_never_averages_away_a_failure():
    print('\nJ. combining stages is worst-first, and nothing is summarised away')
    ok = {'a': Outcome.ok('A', 1), 'b': Outcome.ok('B', 2)}
    check('all-clear reads PASS', combine(ok, 'RUN').state is State.PASS)

    mixed = dict(ok); mixed['c'] = Outcome.deferred('C', 'not yet')
    r = combine(mixed, 'RUN')
    check('one deferral makes the run DEFERRED', r.state is State.DEFERRED)
    check('and the census survives', r.evidence['census']['a'] == 'PASS')

    broken = dict(mixed); broken['d'] = Outcome.fail('D', 'broke')
    r = combine(broken, 'RUN')
    check('a FAIL dominates a DEFERRED', r.state is State.FAIL)
    check('and the deferral is still visible in the census',
          r.evidence['census']['c'] == 'DEFERRED', str(r.evidence))

    check('an empty census is BLOCKED, not an all-clear',
          combine({}, 'RUN').state is State.BLOCKED)


def test_blocked_must_say_why():
    """Part 2 of the 2026-09-02 reconciliation: a subtype, not a sixth state.

    The distinction being bought is the one BLOCKED alone cannot make. A network
    refusal and a governance refusal both mean "did not run", but one says
    nothing about the model and the other is a decision about it. run_suite.py
    recovers that today by grepping stderr for 'fetch failed after 3 attempts',
    which holds until somebody rewords an error string.
    """
    print('\nJ. BLOCKED carries a declared cause')

    for bad in (None, 'NETWORK', 0, State.BLOCKED):
        try:
            Outcome.blocked('X', 'y', cause=bad)
            check(f'cause={bad!r} is refused', False, 'it was accepted')
        except OutcomeError as exc:
            check(f'cause={bad!r} is refused',
                  str(exc).startswith('BLOCKED_CAUSE_UNDECLARED'), str(exc)[:60])

    try:
        Outcome.blocked('X', 'y')
        check('omitting cause entirely is refused', False, 'it was accepted')
    except TypeError:
        check('omitting cause entirely is refused', True)

    o = Outcome.blocked('SAVANT_403', 'egress refused', cause=Cause.NETWORK)
    check('the cause rides in the evidence',
          o.evidence['cause'] == 'NETWORK', str(o.evidence))
    check('and the state is still BLOCKED -- no sixth state was invented',
          o.state is State.BLOCKED)
    check('State still has exactly five members', len(list(State)) == 5,
          str([s.value for s in State]))

    # The point of the subtype: these two are the same state and must remain
    # distinguishable without reading English.
    net = Outcome.blocked('A', 'proxy said no', cause=Cause.NETWORK)
    gov = Outcome.blocked('B', 'a rule said no', cause=Cause.GOVERNANCE)
    check('a network block and a governance block are told apart by field',
          net.evidence['cause'] != gov.evidence['cause'])
    check('while both remain BLOCKED',
          net.state is gov.state is State.BLOCKED)

    check('every cause is a plain string value, not an object, so it survives '
          'json.dumps',
          all(isinstance(c.value, str) for c in Cause))


if __name__ == '__main__':
    test_no_state_without_a_name()
    test_pass_must_carry_a_value()
    test_truthiness_is_refused()
    test_defect_1_the_inert_guard()
    test_defect_2_keys_nothing_wrote()
    test_defect_3_the_dropped_games()
    test_defect_4_not_yet_is_not_a_bug()
    test_defect_8_neither_result_nor_error()
    test_a_bare_return_cannot_reach_a_consumer()
    test_rollup_never_averages_away_a_failure()
    test_blocked_must_say_why()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
