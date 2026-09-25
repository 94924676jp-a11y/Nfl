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
    # MUTATE A PLAYER WHO IS ON THE BOARD.
    #
    # sorted(players)[0] is the EMPTY-STRING key -- the outcome carries one row
    # with no name and no position -- so the mutation landed somewhere no board
    # row could ever join to, 4242 appeared in neither grade, and the test
    # reported them equal. A test that mutates an unreachable row proves
    # nothing and says it proved something, which is worse than no test.
    #
    # Two wrong targets were tried before this one, and both produced a test
    # that passed while proving nothing. First `sorted(players)[0]`, which is
    # the EMPTY-NAME row the outcome carries -- unjoinable to any board row.
    # Then the first named player with a rush_yards figure, which turned out to
    # be Aidan Hutchinson, a DEFENSIVE END: he is in the outcome and not on the
    # DFS board, so no grade row exists for him either.
    #
    # The target has to come from the BOARD universe, which is the union of the
    # DK-bearing layers in the slate's own manifest. Anyone outside it is
    # invisible to the grader by design.
    import json as _json
    man = _json.loads(
        (root / 'frozen' / 'sealed_player_draws_manifest.json').read_text())
    board = set()
    for _lay in (man.get('layers') or {}).values():
        if (_lay or {}).get('row_axis') == 'gsis_id' \
                and 'dk_points' in ((_lay or {}).get('metrics') or ()):
            board |= set(_lay.get('row_ids') or [])
    target = None
    for nm, v in sorted((d.get('players') or {}).items()):
        if nm and isinstance(v, dict) and v.get('player_id') in board \
                and v.get('rush_yards') is not None:
            target = nm
            break
    if target:
        d['players'][target]['rush_yards'] = 4242.0
        d['_mutated_player'] = target
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


def test_the_grader_actually_runs_on_the_second_slate():
    """END TO END, and the only version of this claim worth making.

    Resolving paths proves the resolver. It does not prove the GRADER follows
    them -- grade() read OC.PREGAME_FROZEN directly, so whatever outcome_path
    it was handed, the board it graded was DET_BUF's. A grader that accepts one
    game's RESULT while reading another game's BOARD does not fail; it reports
    a catastrophically bad model, and the error looks like the thing we are
    trying to measure.

    So this runs the real grader against the mutated copy and asserts it
    returns THAT slate's rows, then asserts the default slate still grades as
    before.
    """
    from nfl.postgame import grade_projections as GP
    with tempfile.TemporaryDirectory() as tmp:
        root, mutated = _second_slate(tmp)
        if root is None:
            check('the real slate exists to copy', False, '')
            return
        sl = OC.slate(root=root)
        got = GP.grade(outcome_path=str(sl.artifact), sl=sl)
        check('the grader runs on the second slate',
              got.state.name == 'PASS', f'{got.code}: {str(got.detail)[:110]}')
        if got.state.name != 'PASS':
            return
        rows = got.value.get('rows') or []
        check('it graded a non-empty set of players', bool(rows), len(rows))

        base = GP.grade()
        check('the default slate still grades', base.state.name == 'PASS',
              f'{base.code}')
        if base.state.name == 'PASS':
            nb = len(base.value.get('rows') or [])
            check('both slates graded the same player count '
                  '(the copy has the same board)', len(rows) == nb,
                  f'{len(rows)} vs {nb}')

        # The mutation must be visible in the SECOND slate's grade and absent
        # from the default's. Same board, different result: the actual moves,
        # the projection does not.
        #
        # Compared as a MULTISET across every row rather than by looking up one
        # player. A first version of this check indexed rows by 'gsis_id' and
        # read 'per_stat', neither of which a row carries -- it got None from
        # both grades and reported them equal, which is a test that would pass
        # whether or not the grader followed the slate. The shape is
        # {'player', 'position', 'stats', 'team'}.
        def _actuals(g, stat):
            out = []
            for r in g.value.get('rows') or []:
                st = (r.get('stats') or {}).get(stat) or {}
                if st.get('actual') is not None:
                    out.append(float(st['actual']))
            return sorted(out)

        second, default = _actuals(got, 'rush_yards'), _actuals(base, 'rush_yards')
        check('both grades produced rush_yards actuals',
              bool(second) and bool(default),
              f'second={len(second)} default={len(default)}')
        check('the two slates do NOT grade against identical actuals',
              second != default,
              'identical actuals from a MUTATED copy means the grader is still '
              'reading the default outcome, whatever path it was handed')
        check('and the mutated value is in the second slate only',
              (4242.0 in second) and (4242.0 not in default),
              f'4242 in second={4242.0 in second}, in default='
              f'{4242.0 in default}')
        print(f'       rush_yards actuals: second slate {len(second)} values, '
              f'default {len(default)}; mutation present only in the second')
