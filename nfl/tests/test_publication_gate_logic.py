"""The two publication gates' OWN logic. Closing a gap I left yesterday.

`test_publication_refusal_is_load_bearing` proves that when these gates report
FAIL, `emit_package.main()` writes nothing. It does NOT prove they report FAIL
on a bad input, so between the two suites a gate that returned PASS for
everything would have looked fully covered:

    the caller stops when the gate says FAIL     proven
    the gate says FAIL when the input is bad     NOT proven   <- this file

The guard census records both of these as STOP with zero test coverage, which
is a lever wired to something real and never pulled.

Both return a plain dict rather than a governance Outcome, so `state` is read
by string. That is deliberate in the source, and it means a typo in a state
name would silently never match `'FAIL'` -- so the state strings are asserted
here as values, not just compared.
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import build_postinactives_package as B  # noqa: E402

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


BUF, DET = '00-0000001', '00-0000002'


def _run(stats, game_id='2026_02_DET_BUF', manifest=None):
    return {'game_id': game_id, 'stats': dict.fromkeys(stats, {}),
            'manifest': manifest or {'layers': {}}}


# ------------------------------------------------- assert_no_inactive_in_playable
def test_an_inactive_player_in_the_emitted_rows_is_a_FAIL():
    print('\n[1] the inactive gate says FAIL on a bad input')
    runs = [_run([BUF, DET])]
    g = B.assert_no_inactive_in_playable(runs, {'BUF': [BUF]}, {})
    check('state is FAIL', g['state'] == 'FAIL', str(g['state']))
    check('with the named code',
          g['code'] == 'OFFICIALLY_INACTIVE_PLAYER_IN_PLAYABLE_BOARD',
          str(g['code']))
    check('and it names the survivor',
          [s['gsis_id'] for s in g['survivors']] == [BUF],
          str(g['survivors']))
    check('and counts what it checked', g['n_inactive_ids_checked'] == 1,
          str(g['n_inactive_ids_checked']))


def test_a_clean_slate_is_a_PASS():
    print('\n[2] and PASS when the inactive is genuinely absent')
    runs = [_run([DET])]
    g = B.assert_no_inactive_in_playable(runs, {'BUF': [BUF]}, {})
    check('state is PASS', g['state'] == 'PASS', str(g['state']))
    check('with the clean code',
          g['code'] == '0_OFFICIALLY_INACTIVE_PLAYERS_IN_PLAYABLE_BOARD',
          str(g['code']))
    check('no survivors', g['survivors'] == [])
    check('and it still says it checked one id',
          g['n_inactive_ids_checked'] == 1,
          'a clean result with nothing checked is the collapse this refuses')


def test_no_declarations_is_NOT_CERTIFIED_not_PASS():
    print('\n[3] an empty list and a verified-empty list are different facts')
    runs = [_run([BUF, DET])]
    g = B.assert_no_inactive_in_playable(runs, {}, {})
    check('state is NOT_CERTIFIED', g['state'] == 'NOT_CERTIFIED',
          str(g['state']))
    check('NOT PASS', g['state'] != 'PASS',
          'returning PASS here would certify an unchecked board')
    check('and it counted zero ids', g['n_inactive_ids_checked'] == 0)
    check('and says no intersection was computed',
          'no intersection was computed' in g['method'], g['method'][:60])


def test_the_club_parse_decides_which_ids_are_even_considered():
    print('\n[4] clubs come from the game_id, so a malformed id checks nothing')
    runs = [_run([BUF]), ]
    # An inactive declared for a club NOT in this game must not be counted.
    g = B.assert_no_inactive_in_playable(runs, {'KC': [BUF]}, {})
    check('an inactive from another club is not a survivor',
          g['state'] == 'PASS' and g['survivors'] == [],
          f"{g['state']} {g['survivors']}")
    check('and that club\'s ids were not checked',
          g['n_inactive_ids_checked'] == 0,
          'the count makes the narrow scope visible instead of implicit')
    # A game_id that does not split into four parts yields NO clubs, so the
    # intersection is empty and the gate reports PASS while checking nothing.
    # RECORDED, NOT ENDORSED: the count is what reveals it.
    bad = [_run([BUF], game_id='garbage')]
    gb = B.assert_no_inactive_in_playable(bad, {'BUF': [BUF]}, {})
    check('a malformed game_id checks zero ids',
          gb['n_inactive_ids_checked'] == 0, str(gb['n_inactive_ids_checked']))
    check('...and still reports PASS, which the count is the only warning of',
          gb['state'] == 'PASS',
          'a PASS over an empty intersection is not a clean board; the '
          'n_inactive_ids_checked field is what distinguishes them')


# --------------------------------------------------------- assert_shared_draws
def _man(dk_rows, foot_rows):
    """A manifest the DK-layer DISCOVERY will accept.

    registry.dk_bearing_layers requires each layer to declare
    `row_axis: gsis_id` and a `dk_points` metric -- it refuses
    NoDkBearingLayer rather than inferring one, because 'a DK universe cannot
    be built from this artifact and must not be faked'. My first fixture
    carried row_ids alone and was refused, which is the discovery guard doing
    its job on a test.
    """
    layers = {'dk_scoring': {'row_ids': list(dk_rows), 'row_axis': 'gsis_id',
                             'metrics': ['dk_points']}}
    for ln in B.PLAYER_LAYERS:
        layers.setdefault(ln, {'row_ids': list(foot_rows),
                               'row_axis': 'gsis_id', 'metrics': ['yards']})
    return {'layers': layers}


def test_a_dk_row_with_no_football_layer_is_a_FAIL():
    print('\n[5] the shared-draws gate says FAIL on an unbacked DK row')
    runs = [_run([], manifest=_man([BUF, DET], [DET]))]
    g = B.assert_shared_draws(runs)
    check('state is FAIL', g['state'] == 'FAIL', str(g['state']))
    check('with the named code',
          g['code'] == 'DK_ROWS_NOT_BACKED_BY_FOOTBALL_DRAWS', str(g['code']))
    check('and it names the unbacked row',
          g['offenders'] and g['offenders'][0]['dk_only_rows'] == [BUF],
          str(g['offenders']))


def test_fully_backed_dk_rows_PASS():
    print('\n[6] and PASS when every DK row has a football layer')
    runs = [_run([], manifest=_man([BUF, DET], [BUF, DET]))]
    g = B.assert_shared_draws(runs)
    check('state is PASS', g['state'] == 'PASS', str(g['state']))
    check('no offenders', g['offenders'] == [])


def test_what_the_shared_draws_gate_cannot_catch():
    """A kicker's DK row backs ITSELF, so this check is vacuous for kickers.

    I first wrote this expecting a kicking-only DK row to FAIL, on the strength
    of the source comment about the union discovery. It reports PASS, and PASS
    is CORRECT: `kicking` appears in BOTH sets --

        PLAYER_LAYERS       = (qb, receiving, rushing, rushing_total, kicking, ...)
        dk_bearing_layers() = (dk_scoring, kicking)

    -- so `dk - foot` subtracts the kicker's row from itself. The check asks
    "is every DK-scored player a player the football layers emitted", and a
    kicker emitted in `kicking` is, trivially, because `kicking` IS a football
    layer.

    So the union discovery fixed the ENUMERATION (six modules named dk_scoring
    alone and never saw a kicker at all) without giving this particular check
    any purchase on kickers. Both things are true and they are easy to conflate,
    which is what my first version of this test did. Recorded rather than
    asserted away: the gate is sound, and its coverage of kickers is empty.
    """
    print('\n[7] the limit: a kicker row backs itself')
    check('kicking is BOTH a football layer and DK-bearing',
          'kicking' in B.PLAYER_LAYERS, str(B.PLAYER_LAYERS))
    man = _man([DET], [DET])
    man['layers']['kicking'] = {'row_ids': [BUF], 'row_axis': 'gsis_id',
                                'metrics': ['dk_points']}
    g = B.assert_shared_draws([_run([], manifest=man)])
    check('so a kicking-only DK row PASSES, and that is correct',
          g['state'] == 'PASS' and g['offenders'] == [],
          f"{g['state']} -- dk - foot subtracts the row from itself")
    # What the gate DOES catch is a dk_scoring row with no football backing,
    # which is test [5]. Asserted here too so the contrast is in one place.
    man2 = _man([BUF, DET], [DET])
    g2 = B.assert_shared_draws([_run([], manifest=man2)])
    check('while an unbacked dk_scoring row still FAILS',
          g2['state'] == 'FAIL', str(g2['state']))
    check('the gate is sound; its kicker coverage is empty', True,
          'a check that cannot fail for a population is not protecting it')


def main():
    print(__doc__.strip().splitlines()[0])
    test_an_inactive_player_in_the_emitted_rows_is_a_FAIL()
    test_a_clean_slate_is_a_PASS()
    test_no_declarations_is_NOT_CERTIFIED_not_PASS()
    test_the_club_parse_decides_which_ids_are_even_considered()
    test_a_dk_row_with_no_football_layer_is_a_FAIL()
    test_fully_backed_dk_rows_PASS()
    test_what_the_shared_draws_gate_cannot_catch()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
