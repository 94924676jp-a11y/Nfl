"""Can postgame grade a game other than the one it was written for?

Until now: no. GAME_ID, DIR, ARTIFACT and PREGAME_FROZEN were module constants
naming DET_BUF_2026W2, read by seven postgame modules, one of which is called
run_week2.py. Grading a second game meant editing source. That is DEF-062, and
across all 35 fixture-pinned production modules not one accepted a game, week
or slate argument while 18 of them were runnable.

TWO CLAIMS, AND THIS FILE ONLY SUPPORTS ONE OF THEM.

The MECHANICAL claim -- the code resolves whichever slate it is given, and
does not secretly read the original underneath -- is what these tests prove,
and they prove it the only way that means anything: against a SECOND slate
whose contents DIFFER from the first. A copy with identical bytes would pass
whether the parameterisation worked or not, which is precisely the fake the
owner asked to be ruled out. So the fixture mutates the final score and a
player's line, and the tests assert the MUTATED values come back.

The EVIDENCE claim -- that the grader has been exercised on two real games --
is NOT supported, and cannot be today. Exactly one OUTCOME.json exists in this
repository, for DET_BUF_2026W2; the sealed 2026_03_ATL_GB run has no outcome
at all. A synthetic slate proves the wiring and proves nothing about football.
Saying otherwise would turn a mechanical check into a claim about measurement,
which is the failure this project keeps paying for.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import outcome as OC                           # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _second_slate(tmp):
    """A real copy of the real slate, with its CONTENT CHANGED.

    Identical bytes would pass whether or not the parameterisation works.
    The mutation is what makes this a test.
    """
    root = Path(tmp) / 'DIFFERENT_GAME_2026W9'
    src = OC._DEFAULT.root
    if not src.exists():
        return None, None
    shutil.copytree(src, root)
    art = root / 'POSTGAME_OUTCOME' / 'OUTCOME.json'
    d = json.loads(art.read_text())
    d['game_id'] = '2026_09_XXX_YYY'
    d['final_score'] = {'home': 99, 'away': 3}
    if isinstance(d.get('players'), dict) and d['players']:
        first = sorted(d['players'])[0]
        if isinstance(d['players'][first], dict):
            d['players'][first]['rush_yards'] = 4242.0
    art.write_text(json.dumps(d))
    return root, d


def test_the_default_slate_is_unchanged():
    """Additive, or it is a migration nobody asked for."""
    check('default game id preserved', OC.GAME_ID == '2026_02_DET_BUF', OC.GAME_ID)
    check('default frozen dir preserved',
          OC.PREGAME_FROZEN.name == 'frozen'
          and 'DET_BUF_2026W2' in str(OC.PREGAME_FROZEN), str(OC.PREGAME_FROZEN))
    check('the one real outcome still resolves', OC.ARTIFACT.exists(),
          str(OC.ARTIFACT))


def test_a_second_slate_is_read_and_it_is_not_the_first():
    with tempfile.TemporaryDirectory() as tmp:
        root, mutated = _second_slate(tmp)
        if root is None:
            check('the real slate exists to copy', False, str(OC._DEFAULT.root))
            return
        sl = OC.slate(root=root)
        check('the second slate resolves to its own paths',
              str(sl.root) == str(root), str(sl.root))
        got = OC.require(path=sl.artifact)
        check('the second slate passes the outcome gate',
              got.state.name == 'PASS', f'{got.code}: {got.detail[:90]}')
        if got.state.name == 'PASS':
            d = json.loads(sl.artifact.read_text())
            check('the MUTATED score came back, not the original',
                  d['final_score'] == {'home': 99, 'away': 3}, d['final_score'])
            real = json.loads(OC.ARTIFACT.read_text())
            check('and it differs from the real slate',
                  d['final_score'] != real.get('final_score'),
                  'the copy was not actually different, so this proves nothing')


def test_the_frozen_guard_follows_the_slate_it_is_given():
    """The guard reading the module constant while the paths moved would be a
    parameterisation in name only."""
    with tempfile.TemporaryDirectory() as tmp:
        root, _ = _second_slate(tmp)
        if root is None:
            check('the real slate exists to copy', False, '')
            return
        sl = OC.slate(root=root)
        ok = OC.assert_pregame_untouched(sl)
        check('the second slate reports its own frozen set intact',
              ok.state.name == 'PASS', f'{ok.code}: {ok.detail[:80]}')
        (sl.pregame_frozen / 'STRAY.txt').write_text('x')
        bad = OC.assert_pregame_untouched(sl)
        check('mutating the SECOND slate is detected',
              bad.state.name != 'PASS' and bad.code == 'PREGAME_FROZEN_SET_MUTATED',
              f'{bad.state.name}/{bad.code} -- if this passed, the guard is '
              f'still looking at DET_BUF')
        still = OC.assert_pregame_untouched()
        check('and the DEFAULT slate is unaffected by that mutation',
              still.state.name == 'PASS', still.code)


def test_the_environment_can_select_a_slate_without_editing_source():
    """The owner's actual question: can a different game run without a commit?"""
    with tempfile.TemporaryDirectory() as tmp:
        root, _ = _second_slate(tmp)
        if root is None:
            check('the real slate exists to copy', False, '')
            return
        prev = os.environ.get(OC.SLATE_ENV)
        try:
            os.environ[OC.SLATE_ENV] = str(root)
            sl = OC.slate()
            check('the environment selects the slate',
                  str(sl.root) == str(root), str(sl.root))
            check('and it is not the default',
                  str(sl.root) != str(OC._DEFAULT.root))
        finally:
            if prev is None:
                os.environ.pop(OC.SLATE_ENV, None)
            else:
                os.environ[OC.SLATE_ENV] = prev
        check('unsetting it restores the default',
              str(OC.slate().root) == str(OC._DEFAULT.root))


def test_a_game_id_with_no_known_root_refuses_rather_than_guessing():
    try:
        OC.slate('2026_09_XXX_YYY')
        check('an unknown game id refuses', False, 'it guessed a directory')
    except ValueError as e:
        check('an unknown game id refuses', True)
        check('and says how to supply the root', 'root=' in str(e), str(e)[:90])


def test_only_one_real_graded_slate_exists_and_that_is_stated():
    """The EVIDENCE claim, kept honest. If a second real outcome ever lands,
    this fails and the two-game evidence claim can be re-derived rather than
    assumed."""
    found = sorted(p for p in _REPO.glob('nfl/research/**/OUTCOME.json'))
    check('exactly one real outcome artifact exists in the repository',
          len(found) == 1,
          f'{len(found)} found: {[str(p.relative_to(_REPO)) for p in found]} -- '
          f'if this grew, a second REAL slate is now gradeable and the '
          f'mechanical proof below can be upgraded to an evidence one')
    print(f'       {[str(p.relative_to(_REPO)) for p in found]}')
