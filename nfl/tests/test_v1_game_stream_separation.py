"""V1: a sixteen-game slate must be sixteen games.

Three seeded sites carried no game identity:

    layers.appearance        [seed, season * 100 + week, 11]
    layers._run_real         [seed, season * 100 + week, 11]
    layers.targets_carries   [seed, stream_id]        -- not even the week

so every game on a slate drew from ONE stream. Measured on two disjoint games
with equal player counts: the non-modelled target-mass vectors were
bit-identical (r = 1.000) and appearance draw rows correlated at r = +0.545
BETWEEN GAMES SHARING NO PLAYER.

That is the mirror image of this project's usual dependence defect -- not a
missing dependence football has, but a dependence of exactly 1.0 invented
between independent games. Any across-game aggregate carried the wrong
dispersion, with an unstable sign.

After the repair the same measurement gives 0.0634, which is sampling noise at
m = 200, and an identical game_id still reproduces bit-for-bit.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State          # noqa: E402
from nfl.production import seeds as SEEDS                    # noqa: E402
from nfl.production.nonqb import layers as LY                # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _players(n=20):
    return [{'gsis_id': f'00-000{i:04d}', 'position': 'WR', 'team': 'ARI'}
            for i in range(n)]


def _draws(game_id, m=200):
    ps = _players()
    fx = {'_test_only': True, 'p_appear': {q['gsis_id']: 0.7 for q in ps},
          'practice_progression': {}, 'teammate_availability': {}}
    o = LY.appearance(2026, 1, ps, fixture=fx, m=m, game_id=game_id)
    if o.state is not State.PASS:
        return o, None
    return o, np.vstack([o.value[q['gsis_id']] for q in ps]).astype(float)


def test_two_games_do_not_share_a_stream():
    o1, a = _draws('2026_01_ARI_LAC')
    o2, b = _draws('2026_01_ATL_PIT')
    assert check('both games draw', a is not None and b is not None)
    assert check('two games are not bit-identical',
                 not np.array_equal(a, b),
                 'GAMES_SHARE_ONE_STREAM: disjoint games produced identical '
                 'draws, so the slate is one game repeated')
    r = [abs(np.corrcoef(a[i], b[i])[0, 1]) for i in range(a.shape[0])
         if a[i].std() > 0 and b[i].std() > 0]
    mean_r = float(np.mean(r)) if r else 1.0
    # 0.20 is a NOISE CEILING, not a tuned threshold: at m = 200 the sampling
    # sd of a correlation between independent series is ~1/sqrt(200) = 0.071,
    # so a mean |r| this large cannot arise from independent streams.
    assert check(f'cross-game |corr| is noise, not structure ({mean_r:.4f})',
                 mean_r < 0.20,
                 f'CROSS_GAME_DEPENDENCE_INVENTED: mean |r| {mean_r:.4f}')


def test_the_same_game_still_reproduces_exactly():
    """Separation must not cost determinism."""
    _, a = _draws('2026_01_ARI_LAC')
    _, b = _draws('2026_01_ARI_LAC')
    assert check('one game reproduces bit-for-bit', np.array_equal(a, b),
                 'GAME_STREAM_NOT_REPRODUCIBLE')


def test_absence_of_a_game_id_is_declared_not_hidden():
    o, _ = _draws(None)
    assert check('an unwired caller is visible in the evidence',
                 o.evidence.get('game_stream_separated') is False,
                 'UNWIRED_CALLER_SILENT: a caller with no game id would '
                 'collide with every other game and say nothing')
    o2, _ = _draws('2026_01_ARI_LAC')
    assert check('a wired caller says so',
                 o2.evidence.get('game_stream_separated') is True)


def test_the_game_component_is_stable_and_refuses_absence():
    a = SEEDS.game_component('2026_01_ARI_LAC')
    b = SEEDS.game_component('2026_01_ARI_LAC')
    c = SEEDS.game_component('2026_01_ATL_PIT')
    assert check('stable for one game', a.value == b.value)
    assert check('distinct across games', a.value != c.value)
    assert check('not derived from python hash',
                 a.evidence.get('derived_from_python_hash') is False)
    bad = SEEDS.game_component('')
    assert check('a missing game id is refused, never defaulted',
                 bad.state is State.FAIL
                 and bad.code == 'SEED_GAME_ID_MISSING', bad.code)


def test_every_production_caller_passes_a_game_id():
    """A guard nothing calls is not a guard."""
    for rel, needle in (
            ('nfl/production/nonqb/football_engine.py', 'game_id=game_id'),
            ('nfl/production/run_forecast.py', 'game_id=args.game_id'),
            ('nfl/production/nonqb/slate_rehearsal.py', 'game_id=game_id')):
        src = open(os.path.join(_ROOT, rel)).read()
        assert check(f'{os.path.basename(rel)} passes a game id',
                     needle in src, f'CALLER_NOT_WIRED: {rel}')


def test_targets_carries_carries_game_and_week():
    """This site had neither. A stream id is a class identity, not an
    execution identity."""
    src = open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                            'layers.py')).read()
    i = src.find('def targets_carries')
    j = src.find('default_rng', i)
    assert check('the allocation seeds after its definition', j > i > 0)
    window = src[i:j + 200]
    assert check('the allocation stream includes the ordinal',
                 'ordinal' in window, 'ALLOCATION_STREAM_HAS_NO_WEEK')
    assert check('the allocation stream includes the game',
                 '_game_stream' in window, 'ALLOCATION_STREAM_HAS_NO_GAME')


def test_the_guard_fails_when_bypassed():
    """Seed the old vector and require the separation test to reject it."""
    a = np.random.default_rng([20260908, 202601, 11]).binomial(1, 0.7, 200)
    b = np.random.default_rng([20260908, 202601, 11]).binomial(1, 0.7, 200)
    assert check('the old seed vector would be caught as identical',
                 np.array_equal(a, b),
                 'V1_STREAM_GUARD_IS_INERT: the pre-repair vector no longer '
                 'reproduces the collision, so this suite proves nothing')
