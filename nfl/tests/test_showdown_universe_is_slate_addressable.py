"""`showdown.universe` runs a game it is given, not the one it was written for.

Three postgame graders import this module, so its module-level pin bound all
of them: `grade_projections`, `grade_props` and `grade_portfolios` could only
ever have run DET@BUF whatever game they were handed. DEF-062.

THE PINS WERE NOT ONLY PATHS, and that is the part worth testing hardest.
`OFFICIAL_INACTIVE` is who was ruled out on 2026-09-17 and `BUF_ROLE_CONCERN`
is a Buffalo roster. A parameterisation that moved the DIRECTORY and left
those two behind would tag the wrong players in the wrong game and still look
parameterised, so the second slate here changes a player's salary AND checks
that the default slate's inactive list does not follow it across.

The distinction the owner asked to keep, stated for this module:

  mechanically parameterised            YES -- slate() / load(sl) / build(sl)
  executed on two different fixtures    YES -- below, materially different
  executed on two real NFL slates       NO. One real sealed Showdown artifact
                                        exists in this repository. The second
                                        slate here is a mutated copy: it proves
                                        the wiring and proves nothing about
                                        football.
"""
import csv
import shutil
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.showdown import universe as U  # noqa: E402

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


def _second_slate(tmp):
    """A copy with a MATERIALLY different salary file.

    A byte-identical copy would pass a fake parameterisation that still
    resolved the original directory underneath, so one playable player's
    salary is changed and the new value is returned to be asserted on.
    """
    root = Path(tmp) / 'frozen'
    shutil.copytree(U.DEFAULT_FROZEN, root)
    # frozen_board_names.json sits BESIDE the frozen dir, not in it, so a
    # copy of the directory alone is not a slate. Copying it is what makes
    # this a second slate rather than half of one.
    shutil.copy2(U.DEFAULT_FROZEN.parent / 'frozen_board_names.json',
                 root.parent / 'frozen_board_names.json')
    sp = root / 'DKSalaries_showdown.csv'
    # PARSE IT THE WAY PRODUCTION DOES. My first cut split on ',' and wrote
    # the new salary into the wrong column, because the DK file quotes fields
    # that contain commas -- the test then read 18000 where it expected
    # 12700. A fixture that mutates a file differently from the way the code
    # under test reads it is not testing that code.
    rows = list(csv.reader(sp.read_text().splitlines()))
    target, newsal = None, None
    for r in rows:
        if len(r) > 19 and r[11] in ('QB', 'RB', 'WR', 'TE') and r[15] == 'FLEX':
            target, newsal = r[13].strip(), int(r[16]) + 700
            r[16] = str(newsal)
            break
    with sp.open('w', newline='') as fh:
        csv.writer(fh).writerows(rows)
    return root, target, newsal


def test_the_default_slate_is_exactly_what_it_was():
    print('\n[1] the default is unchanged')
    check('default game id', U.GAME_ID == '2026_02_DET_BUF', U.GAME_ID)
    check('GAME_ID and the slate agree', U.GAME_ID == U._DEFAULT.game_id,
          'one value, not two that can drift')
    check('FROZEN and the slate agree', U.FROZEN == U._DEFAULT.frozen)
    check('the default carries its slate data',
          len(U._DEFAULT.official_inactive) == 2
          and len(U._DEFAULT.role_concern) == 12,
          f'{len(U._DEFAULT.official_inactive)} inactive, '
          f'{len(U._DEFAULT.role_concern)} role-concern')
    b = U.build()
    check('it still builds', b.state.name == 'PASS', b.detail)
    check('and reports its own game id',
          b.as_dict()['evidence'].get('game_id') == '2026_02_DET_BUF')


def test_a_game_id_alone_is_refused_rather_than_guessed():
    print('\n[2] a game id does not imply a directory')
    try:
        U.slate(game_id='2026_05_KC_BUF')
        check('an unknown game id is refused', False,
              'it returned a slate -- it would have read DET@BUF and called '
              'it KC@BUF')
    except ValueError as e:
        check('an unknown game id is refused', True, str(e)[:60])
    sl = U.slate(game_id='2026_02_DET_BUF')
    check('the default game id alone still resolves',
          sl.frozen == U.DEFAULT_FROZEN)


def test_a_second_slate_executes_and_is_not_the_first():
    print('\n[3] two materially different fixtures, both executed')
    with tempfile.TemporaryDirectory() as tmp:
        root, target, newsal = _second_slate(tmp)
        check('the second fixture differs from the first',
              (root / 'DKSalaries_showdown.csv').read_bytes()
              != (U.DEFAULT_FROZEN / 'DKSalaries_showdown.csv').read_bytes(),
              f'{target} salary -> {newsal}')
        sl = U.slate(game_id='2026_02_SECOND', frozen=root)
        b = U.build(sl)
        check('the second slate builds', b.state.name == 'PASS', b.detail)
        if b.state.name != 'PASS':
            return
        ev = b.as_dict()['evidence']
        check('it reports the SECOND game id', ev.get('game_id')
              == '2026_02_SECOND', str(ev.get('game_id')))
        # BY SLOT, not by name. DK lists every player twice -- once CPT at
        # 1.5x and once FLEX -- so matching on the name alone picked Gibbs's
        # CPT row and read 18000 where 12700 was written. The test was wrong,
        # not the code, and it is the kind of wrong that reads as a leak.
        def _flex(out):
            return [q for q in out.value['players']
                    if q['name'] == target and q['slot'] == 'FLEX']

        got = _flex(b)
        check('the changed salary is what was read',
              bool(got) and got[0]['salary'] == newsal,
              f'{target} FLEX: {got[0]["salary"] if got else "absent"} '
              f'(expected {newsal})')
        first = U.build()
        f0 = _flex(first)
        check('the FIRST slate still reads the original salary',
              bool(f0) and f0[0]['salary'] == newsal - 700,
              f'{f0[0]["salary"] if f0 else "absent"} -- the second slate did '
              f'not leak into the first')


def test_the_slate_data_does_not_follow_the_directory():
    print('\n[4] the football travels with the slate, not with the code')
    with tempfile.TemporaryDirectory() as tmp:
        root, _, _ = _second_slate(tmp)
        sl = U.slate(game_id='2026_02_SECOND', frozen=root)
        check('a non-default slate starts with NO inactive list',
              sl.official_inactive == (),
              "this module does not know who was ruled out in a game it has "
              "never seen")
        check('...and NO role-concern list', sl.role_concern == ())
        # Skyler Bell is blocked on the default slate. He must NOT be blocked
        # on a slate that never said he was out.
        check('the default still blocks Skyler Bell',
              U._tag('Skyler Bell') != U._tag('Skyler Bell', sl),
              f'default={U._tag("Skyler Bell")}, '
              f'second={U._tag("Skyler Bell", sl)}')
        check('and James Cook is role-concern only on the default',
              U._tag('James Cook') != U._tag('James Cook', sl),
              f'default={U._tag("James Cook")}, '
              f'second={U._tag("James Cook", sl)}')
        # An explicit list is honoured, so a real second game can carry its own.
        sl2 = U.slate(game_id='2026_02_SECOND', frozen=root,
                      official_inactive=('James Cook',))
        check('an explicit inactive list is used',
              U._tag('James Cook', sl2) != U._tag('James Cook', sl),
              f'{U._tag("James Cook", sl2)}')


def test_a_slate_missing_its_board_names_refuses_rather_than_raising():
    print('\n[5] an incomplete slate is refused by name')
    with tempfile.TemporaryDirectory() as tmp:
        root, _, _ = _second_slate(tmp)
        (root.parent / 'frozen_board_names.json').unlink()
        sl = U.slate(game_id='2026_02_HALF', frozen=root)
        try:
            b = U.build(sl)
        except Exception as e:                                   # noqa: BLE001
            check('build refuses instead of raising', False,
                  f'{type(e).__name__}: {e}')
            return
        check('build refuses instead of raising', True)
        check('...with a named code',
              b.code == 'SHOWDOWN_BOARD_NAMES_MISSING', str(b.code))
        check('...and the state is not PASS', b.state.name != 'PASS',
              b.state.name)


def test_the_dk_rules_were_not_turned_into_knobs():
    print('\n[6] what must NOT be parameterised')
    check('SALARY_CAP is still a module constant', U.SALARY_CAP == 50000)
    check('N_FLEX is still a module constant', U.N_FLEX == 5)
    check('CPT_MULTIPLIER is still a module constant', U.CPT_MULTIPLIER == 1.5)
    check('and none of them is on the slate',
          not any(hasattr(U._DEFAULT, a) for a in
                  ('salary_cap', 'n_flex', 'cpt_multiplier')),
          'these are DraftKings rules, identical for every game; a knob here '
          'would model nothing')


def main():
    print(__doc__.strip().splitlines()[0])
    test_the_default_slate_is_exactly_what_it_was()
    test_a_game_id_alone_is_refused_rather_than_guessed()
    test_a_second_slate_executes_and_is_not_the_first()
    test_the_slate_data_does_not_follow_the_directory()
    test_a_slate_missing_its_board_names_refuses_rather_than_raising()
    test_the_dk_rules_were_not_turned_into_knobs()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
