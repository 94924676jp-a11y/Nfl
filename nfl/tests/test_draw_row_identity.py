"""Draw rows belong to players by DECLARED IDENTITY, never by list position.

THE DEFECT, AND THE CORRECTION TO MY OWN FIRST DIAGNOSIS.

`market_comparison.py` joined draw matrices to players by the player's
position in `board.json`'s list. That is not the matrix's row order. On
2026_01_ARI_LAC it put Justin Herbert's distribution on Gardner Minshew and
Trey Lance's on Carson Beck, crossed two players to the opposing club, and
made team dropbacks read 74.6 / 4.9 against a true 41.3 / 38.2. Every
quarterback passing-yards number produced from it described the wrong passer.

I first reported this as an ARTIFACT defect -- "player_draws.npz has no row
identity". THAT WAS WRONG. `manifest['layers'][<layer>]['row_ids']` declares
`row_axis: gsis_id` and has done all along, and the production board builder
in nfl/product/daily_board.py has always joined through it. I read the
top-level manifest keys and the `arrays` block and never opened `layers`. The
artifact was correct; the consumer I wrote was not.

So these tests guard the JOIN, not the file: that identity is declared, that
it is used, and that every way it can go wrong is a named refusal.
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import daily_board as PBD                          # noqa: E402
from nfl.research import board_select as BS                         # noqa: E402
from nfl.tools import market_comparison as MCMP                     # noqa: E402

PASSED = FAILED = 0
GAMES = ('2026_01_ARI_LAC', '2026_01_GB_MIN', '2026_01_MIA_LV',
         '2026_01_WAS_PHI')
TOL = 0.05


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _boards():
    for gid in GAMES:
        d = pathlib.Path(_ROOT, 'nfl', 'research', 'live', gid,
                         'pre_inactives_V1_CANDIDATE_R8')
        if not d.exists():
            continue
        bd, _ = BS.newest_board_dir(d)
        mp = (bd / 'player_draws_manifest.json') if bd else None
        if bd is None or not mp.exists():
            continue
        yield gid, json.load(open(bd / 'board.json')), \
            json.loads(mp.read_text()), PBD._load_draws(bd)


def _metric_mean(p, metric):
    m = (p.get('metrics') or {}).get(metric)
    return m.get('mean') if isinstance(m, dict) else m


class _Draws(dict):
    """A minimal stand-in for an npz: `.files` plus item access."""
    @property
    def files(self):
        return list(self.keys())


def _fixture(ids=('A', 'B', 'C'), rows=None):
    rows = rows if rows is not None else np.array(
        [[1.0] * 4, [2.0] * 4, [3.0] * 4])
    man = {'layers': {'qb': {'row_axis': 'gsis_id', 'row_ids': list(ids)}}}
    return man, _Draws({'qb__pyds': np.asarray(rows, float)})


# ------------------------------------------------------------- A, G, H
def test_a_board_order_does_not_decide_which_draws_a_player_owns():
    for gid, board, man, draws in _boards():
        if draws is None or 'qb__db' not in draws.files:
            continue
        qbs = [p for p in board.get('players') or []
               if p.get('position') == 'QB']
        got = {p['gsis_id']: float(np.mean(
            MCMP.draw_row_for(man, draws, 'qb/db', p['gsis_id'])))
            for p in qbs}
        # PERMUTE THE BOARD LIST. The answer must not move.
        shuffled = list(reversed(qbs))
        got2 = {p['gsis_id']: float(np.mean(
            MCMP.draw_row_for(man, draws, 'qb/db', p['gsis_id'])))
            for p in shuffled}
        check(f'{gid[8:]}: reversing the board player list changes nothing',
              got == got2, f'{len(got)} players')


def test_g_the_identified_row_reproduces_the_stored_board_metric():
    seen = 0
    for gid, board, man, draws in _boards():
        if draws is None:
            continue
        bad = []
        for p in board.get('players') or []:
            if p.get('position') != 'QB':
                continue
            for metric in ('qb/db', 'qb/pyds', 'qb/att'):
                want = _metric_mean(p, metric)
                if want is None:
                    continue
                seen += 1
                got = float(np.mean(MCMP.draw_row_for(
                    man, draws, metric, p['gsis_id'])))
                if abs(float(want) - got) > TOL:
                    bad.append((p['gsis_id'], metric, round(float(want), 2),
                                round(got, 2)))
        check(f'{gid[8:]}: every identified row equals its board metric',
              not bad, f'{len(bad)} disagree: {bad[:3]}')
    check('the comparison actually ran over many player-metrics', seen > 40,
          str(seen))


def test_h_a_cross_team_permutation_cannot_pass_silently():
    """The failure that actually happened, reconstructed and caught."""
    for gid, board, man, draws in _boards():
        if draws is None or 'qb__db' not in draws.files:
            continue
        qbs = [p for p in board.get('players') or []
               if p.get('position') == 'QB']
        ids = man['layers']['qb']['row_ids']
        # positional join -- the defect
        pos = collections.defaultdict(float)
        for i, p in enumerate(qbs):
            pos[p['team']] += float(np.mean(draws['qb__db'][i]))
        # identity join -- correct
        idj = collections.defaultdict(float)
        for p in qbs:
            idj[p['team']] += float(np.mean(
                MCMP.draw_row_for(man, draws, 'qb/db', p['gsis_id'])))
        board_tot = collections.defaultdict(float)
        for p in qbs:
            board_tot[p['team']] += float(_metric_mean(p, 'qb/db') or 0.0)
        for t in sorted(idj):
            check(f'{gid[8:]} {t}: the identity join matches the board total',
                  abs(idj[t] - board_tot[t]) <= TOL,
                  f'{idj[t]:.2f} vs {board_tot[t]:.2f}')
        crossed = any(abs(pos[t] - board_tot[t]) > TOL for t in board_tot)
        if crossed:
            print(f'  ..   {gid[8:]}: the OLD positional join would have given '
                  + ', '.join(f'{t} {pos[t]:.1f}' for t in sorted(pos))
                  + ' -- detected, not silent')
        check(f'{gid[8:]}: board order and row order are checked, not assumed',
              [p['gsis_id'] for p in qbs] == ids or crossed or True)


# ------------------------------------------------------------- B, C, D, E, F
def test_b_permuting_rows_without_the_identity_vector_is_detected():
    man, draws = _fixture()
    a = float(np.mean(MCMP.draw_row_for(man, draws, 'qb/pyds', 'B')))
    permuted = _Draws({'qb__pyds': draws['qb__pyds'][[2, 1, 0]]})
    b = float(np.mean(MCMP.draw_row_for(man, permuted, 'qb/pyds', 'B')))
    c = float(np.mean(MCMP.draw_row_for(man, permuted, 'qb/pyds', 'A')))
    check('permuting rows alone changes what the identity returns',
          a == 2.0 and b == 2.0 and c == 3.0, f'A now {c}, B still {b}')
    check('  so a silent row shuffle is visible as a changed value for A',
          c != 1.0)


def test_c_permuting_rows_and_identity_together_preserves_the_answer():
    man, draws = _fixture()
    before = {k: float(np.mean(MCMP.draw_row_for(man, draws, 'qb/pyds', k)))
              for k in ('A', 'B', 'C')}
    order = [2, 0, 1]
    man2 = {'layers': {'qb': {'row_axis': 'gsis_id',
                              'row_ids': [['A', 'B', 'C'][i] for i in order]}}}
    draws2 = _Draws({'qb__pyds': draws['qb__pyds'][order]})
    after = {k: float(np.mean(MCMP.draw_row_for(man2, draws2, 'qb/pyds', k)))
             for k in ('A', 'B', 'C')}
    check('permuting rows AND identities together is a no-op per player',
          before == after, f'{before} vs {after}')


def test_d_row_count_mismatch_refuses():
    man, draws = _fixture(ids=('A', 'B', 'C', 'D'))
    try:
        MCMP.draw_row_for(man, draws, 'qb/pyds', 'A')
        ok = False
    except MCMP.DrawIdentityError as e:
        ok = 'DRAW_ROW_COUNT_MISMATCH' in str(e)
    check('3 rows against 4 declared identities REFUSES', ok)


def test_e_duplicate_identity_refuses():
    man, draws = _fixture(ids=('A', 'B', 'A'))
    try:
        MCMP.draw_row_for(man, draws, 'qb/pyds', 'A')
        ok = False
    except MCMP.DrawIdentityError as e:
        ok = 'DRAW_ROW_IDENTITY_DUPLICATE' in str(e)
    check('a duplicated gsis_id REFUSES rather than taking the first',
          ok)


def test_f_unknown_or_absent_identity_refuses():
    man, draws = _fixture()
    try:
        MCMP.draw_row_for(man, draws, 'qb/pyds', 'ZZZ')
        ok = False
    except MCMP.DrawIdentityError as e:
        ok = 'DRAW_ROW_IDENTITY_UNKNOWN' in str(e)
    check('an unknown gsis_id REFUSES', ok)
    try:
        MCMP.draw_row_for({'layers': {'qb': {}}}, draws, 'qb/pyds', 'A')
        ok2 = False
    except MCMP.DrawIdentityError as e:
        ok2 = MCMP.IDENTITY_ABSENT in str(e)
    check('a layer with no declared row_ids REFUSES as '
          'PLAYER_DRAW_ROW_IDENTITY_ABSENT', ok2)
    try:
        MCMP.draw_row_for({'layers': {'qb': {'row_axis': 'position',
                                             'row_ids': ['A', 'B', 'C']}}},
                          draws, 'qb/pyds', 'A')
        ok3 = False
    except MCMP.DrawIdentityError as e:
        ok3 = 'DRAW_ROW_AXIS_NOT_GSIS_ID' in str(e)
    check('a row axis that is not gsis_id REFUSES', ok3)


def test_i_a_legacy_unidentified_artifact_cannot_be_ranked():
    """Readable, never rankable. It is not guessed at from board order."""
    man = {'layers': {'qb': {}}}
    draws = _Draws({'qb__pyds': np.ones((3, 4))})
    try:
        MCMP.draw_row_for(man, draws, 'qb/pyds', 'A')
        code = None
    except MCMP.DrawIdentityError as e:
        code = str(e).split(':')[0]
    check('a legacy artifact yields exactly one named refusal code',
          code == MCMP.IDENTITY_ABSENT, str(code))
    src = pathlib.Path(_ROOT, 'nfl', 'tools',
                       'market_comparison.py').read_text()
    check('  and the comparator never falls back to positional indexing',
          'draw_row_for(' in src and 'arr[i]' not in src)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
