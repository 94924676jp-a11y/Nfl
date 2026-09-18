"""Four universes, and a metric may not be compared across two of them.

THE DEFECT. The 2026-09-17 postmortem set a delivered exposure beside a
`P(optimal)` for Tyler Bass and Jake Bates. The two numbers were computed over
different sets of players: the portfolio could roster a kicker and the
optimal-world solve could not. "22.5% exposure against P(optimal) 0.0" reads
as an indictment and is an artefact. The kicker's P(optimal) was not low, it
was UNDEFINED.

AND THE REVIEW'S DIAGNOSIS OF WHY WAS WRONG, which these checks pin. The
kicking layer was never team-keyed: `row_ids` are gsis_ids and `row_teams` is
a column beside the key. What was missing was a name in
`frozen_board_names.json`. `test_E` asserts the id resolution directly, and
`test_F` asserts that a (team, position) join is still refused afterwards --
closing the gap does not make the positional join acceptable.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.showdown import kicker_identity as KI                    # noqa: E402
from nfl.dfs.showdown import universe as U                            # noqa: E402
from nfl.dfs.showdown import universe_contract as UC                  # noqa: E402
from sportsplatform.governance.outcome import State                   # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

FIX = _REPO/'nfl/research/dfs/DET_BUF_2026W2'
PORTFOLIOS = (('CLAUDE', FIX/'PORTFOLIO_CLAUDE_40.csv'),
              ('ALTERNATE', FIX/'PORTFOLIO_ALTERNATE_40.csv'))

#: The two gsis_ids the sealed kicking layer carries, and the men they are.
#: Confirmed independently against the nflverse player ids in the postgame
#: capture. Matching is by ID here and everywhere.
BASS = '00-0036162'
BATES = '00-0039172'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _contract():
    return UC.build(portfolios=PORTFOLIOS)


def test_A_the_four_universes_are_counted_separately():
    o = _contract()
    check('A the contract builds', o.state is State.PASS,
          f'{o.state}[{o.code}]')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('A-D contract assertions')
        return
    c = o.evidence['counts']
    check('A all four universes are reported',
          set(c) == set(UC.UNIVERSES), str(sorted(c)))
    check('A site is the outer bound',
          c[UC.SITE] >= c[UC.SIMULATED] >= c[UC.OPTIMIZATION], str(c))
    check('A every excluded row carries a reason',
          all(r['excluded_because'] is None or r['excluded_detail']
              for r in o.value['rows']))
    check('A and every reason is one of the declared ones',
          all(r['excluded_because'] in (None,) + tuple(UC.REASONS)
              for r in o.value['rows']),
          str({r['excluded_because'] for r in o.value['rows']}))


def test_B_a_delivered_player_outside_the_optimization_set_is_named():
    o = _contract()
    if o.state is not State.PASS:
        NOT_EXECUTED.append('B delivered mismatch')
        return
    out = o.evidence['delivered_but_not_in_optimization']
    check('A mismatch is listed by NAME, not merely counted',
          isinstance(out, list), str(out))
    check('B no delivered player is missing from the site board entirely',
          o.evidence['delivered_names_not_on_the_site_board'] == [],
          str(o.evidence['delivered_names_not_on_the_site_board']))


def test_C_comparing_across_universes_is_refused():
    o = _contract()
    if o.state is not State.PASS:
        NOT_EXECUTED.append('C comparability')
        return
    inside = [r['name'] for r in o.value['rows'] if r[UC.OPTIMIZATION]][:3]
    good = UC.assert_comparable(inside, o)
    check('C players inside the optimization universe compare lawfully',
          good.state is State.PASS, f'{good.state}[{good.code}]')
    ghost = UC.assert_comparable(inside + ['Nobody At All'], o)
    check('C a name not on the board is refused',
          ghost.state is State.FAIL and ghost.code == UC.CODE_MISMATCH,
          f'{ghost.state}[{ghost.code}]')
    check('C and the refusal names who, not just how many',
          'Nobody At All' in str(ghost.evidence['not_on_the_board']),
          str(ghost.evidence['not_on_the_board']))
    outside = [r['name'] for r in o.value['rows'] if not r[UC.OPTIMIZATION]]
    if outside:
        bad = UC.assert_comparable([inside[0], outside[0]], o)
        check('C a player outside the optimization universe is refused',
              bad.state is State.FAIL and bad.code == UC.CODE_MISMATCH,
              f'{bad.state}[{bad.code}]')
        check('C and the refusal says UNDEFINED, not low',
              'UNDEFINED' in bad.detail, bad.detail[:80])
    else:
        NOT_EXECUTED.append('C outside-universe refusal (nothing excluded)')


def test_D_dst_is_explicit_and_stays_unsupported():
    o = _contract()
    if o.state is not State.PASS:
        NOT_EXECUTED.append('D dst')
        return
    dst = [r for r in o.value['rows'] if r['position'] == 'DST']
    check('D DST rows exist on the site board', bool(dst), str(len(dst)))
    check('D and none of them is optimization-eligible',
          all(not r[UC.OPTIMIZATION] for r in dst))
    check('D each says why, in the declared vocabulary',
          all(r['excluded_because'] == 'UNSUPPORTED_POSITION' for r in dst),
          str({r['excluded_because'] for r in dst}))


def test_E_kicker_identity_resolves_by_player_id():
    o = KI.resolve()
    check('E the kicking layer resolves', o.state is State.PASS,
          f'{o.state}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('E kicker identity')
        return
    check('E both ids resolve to named men',
          set(o.value) == {BASS, BATES}, str(sorted(o.value)))
    check('E Bass is 00-0036162 and Bates is 00-0039172',
          o.value[BASS]['name'] == 'Tyler Bass'
          and o.value[BATES]['name'] == 'Jake Bates',
          str({k: v['name'] for k, v in o.value.items()}))
    check('E resolved by gsis_id, and the artifact says so',
          o.evidence['resolved_by'] == 'gsis_id'
          and o.evidence['never_by'] == '(team, position)')
    check('E the layer was player-keyed all along',
          o.evidence['the_layer_was_always_player_keyed'] is True)
    check('E the club column beside the key agrees with the roster',
          o.evidence['club_column_disagreements'] == [],
          str(o.evidence['club_column_disagreements']))


def test_F_a_positional_join_is_still_refused():
    """Closing the name gap does not make (team, position) acceptable."""
    bad = KI.assert_not_positional(('team', 'position'))
    check('F a (team, position) join is refused',
          bad.state is State.FAIL and bad.code == KI.CODE_POSITIONAL,
          f'{bad.state}[{bad.code}]')
    check('F and the refusal explains what breaks',
          'two' in bad.detail.lower() or 'signing' in bad.detail.lower(),
          bad.detail[:80])
    good = KI.assert_not_positional(('gsis_id',))
    check('F a player-id join passes', good.state is State.PASS,
          f'{good.state}[{good.code}]')
    none = KI.assert_not_positional(('name',))
    check('F a join with no id at all is refused too',
          none.state is State.FAIL and none.code == KI.CODE_UNRESOLVED,
          f'{none.state}[{none.code}]')


def test_G_the_kickers_are_now_in_the_optimization_universe():
    u = U.build()
    check('G the universe builds', u.state is State.PASS,
          f'{u.state}[{u.code}]')
    if u.state is not State.PASS:
        NOT_EXECUTED.append('G kickers playable')
        return
    ks = [p for p in u.value['playable'] if p['pos'] == 'K']
    check('G both kickers are playable', len(ks) == 2,
          str([p['name'] for p in ks]))
    check('G each carries his own draws, not a shared team row',
          len(ks) == 2 and ks[0]['draws'].shape == ks[1]['draws'].shape
          and not (ks[0]['draws'] == ks[1]['draws']).all(),
          'identical draw arrays would mean a team row served two men')
    check('G and each carries the gsis_id he was resolved by',
          all(p.get('gsis_id') in (BASS, BATES) for p in ks),
          str([p.get('gsis_id') for p in ks]))
    o = _contract()
    if o.state is State.PASS:
        check('G so the delivered/optimization mismatch is now empty',
              o.evidence['delivered_but_not_in_optimization'] == [],
              str(o.evidence['delivered_but_not_in_optimization']))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_four_universes_are_counted_separately,
               test_B_a_delivered_player_outside_the_optimization_set_is_named,
               test_C_comparing_across_universes_is_refused,
               test_D_dst_is_explicit_and_stays_unsupported,
               test_E_kicker_identity_resolves_by_player_id,
               test_F_a_positional_join_is_still_refused,
               test_G_the_kickers_are_now_in_the_optimization_universe):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
