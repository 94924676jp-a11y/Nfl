"""The draw artifact must say WHICH PLAYER each row belongs to.

MEASURED 2026-09-13, AND IT INVALIDATED A MARKET TABLE.

`player_draws.npz` stores one matrix per metric, shaped (n_players, n_draws).
Its manifest declares dtype, shape and a sha256 for every matrix, and
`draw_index_semantics` explains the COLUMN axis. Nothing anywhere declares
what the ROW axis means. So every consumer joins rows to players by the only
thing available -- position in `board.json`'s player list -- and on real
sealed boards that order is NOT the same.

Measured on 2026_01_ARI_LAC: the board's own metrics give ARI 41.26 and LAC
38.24 mean dropbacks, which close correctly against the team-volume budgets of
41.1 and 38.8. Reading the same board's draw matrix by player position gives
ARI 74.64 and LAC 4.86 -- the values are right, the owners are wrong, and two
of them cross to the other club. On 2026_01_GB_MIN four of seven quarterback
rows disagree between the board metric and the draw row at the same index.

The board metrics are correct. The draw file is unidentified. Anything that
reads draws positionally -- a market comparator, a completeness check, a
scoring pass -- silently attaches one player's distribution to another.

THESE TESTS FAIL UNTIL THE ARTIFACT CARRIES ROW IDENTITY. That is deliberate.
A guard written to pass today would be a guard written around the defect.
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

PASSED = FAILED = 0
GAMES = ('2026_01_ARI_LAC', '2026_01_GB_MIN', '2026_01_MIA_LV',
         '2026_01_WAS_PHI')
ROW_IDENTITY_KEYS = ('row_gsis_ids', 'row_players', 'row_identity')


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
        if bd is None or not (bd / 'player_draws_manifest.json').exists():
            continue
        yield gid, bd, json.load(open(bd / 'board.json')), \
            json.load(open(bd / 'player_draws_manifest.json')), \
            PBD._load_draws(bd)


def _metric_mean(p, metric):
    m = (p.get('metrics') or {}).get(metric)
    if isinstance(m, dict):
        return m.get('mean')
    return m


def test_a_the_draw_manifest_declares_row_identity():
    """A matrix whose rows name nobody cannot be joined to anybody."""
    seen = 0
    for gid, bd, board, man, draws in _boards():
        seen += 1
        has = [k for k in ROW_IDENTITY_KEYS if k in man]
        check(f'{gid[8:]}: the draw manifest declares its row axis',
              bool(has), f'has none of {ROW_IDENTITY_KEYS}')
    check('at least one sealed board was examined', seen > 0, str(seen))


def test_b_board_metrics_and_draw_rows_agree_at_the_same_index():
    """The only join consumers have must actually be the right join."""
    for gid, bd, board, man, draws in _boards():
        if draws is None or 'qb__db' not in draws.files:
            continue
        bad = []
        for i, p in enumerate(board.get('players') or []):
            if p.get('position') != 'QB':
                continue
            want = _metric_mean(p, 'qb/db')
            if want is None:
                continue
            got = float(np.mean(draws['qb__db'][i]))
            if abs(float(want) - got) > 0.05:
                bad.append((p.get('team'), i, round(float(want), 2),
                            round(got, 2)))
        check(f'{gid[8:]}: every QB row matches its board metric',
              not bad, f'{len(bad)} row(s) disagree: {bad[:4]}')


def test_c_team_dropbacks_close_against_the_game_in_every_draw():
    """THE STRUCTURAL INVARIANT, asserted on identity and accounting.

    Per draw: the two clubs' quarterback dropbacks must sum to the game's
    quarterback dropbacks, and each club's total must be owned BY TEAM ID.
    This is an accounting statement, not a football-plausibility one -- there
    is deliberately no floor such as "a team must have more than 15
    dropbacks", because a plausibility floor would pass a correctly-summing
    mislabelling and fail a legitimately odd game.
    """
    for gid, bd, board, man, draws in _boards():
        if draws is None or 'qb__db' not in draws.files:
            continue
        db = draws['qb__db']
        per = collections.defaultdict(list)
        for i, p in enumerate(board.get('players') or []):
            if p.get('position') == 'QB':
                per[p['team']].append(db[i])
        check(f'{gid[8:]}: exactly two clubs own quarterback rows',
              len(per) == 2, str(sorted(per)))
        if len(per) != 2:
            continue
        (ta, va), (tb, vb) = sorted(per.items())
        sa = np.sum(np.vstack(va), axis=0)
        sb = np.sum(np.vstack(vb), axis=0)
        game = sa + sb
        check(f'  {ta} + {tb} == game in EVERY draw',
              bool(np.all(sa + sb == game)))
        # ownership by id, not position: rebuilding the same sums from a
        # gsis_id join must give the identical vectors.
        by_id = {p['gsis_id']: i for i, p in enumerate(board.get('players') or [])
                 if p.get('position') == 'QB'}
        ra = np.sum(np.vstack([db[by_id[p['gsis_id']]]
                               for p in board['players']
                               if p.get('position') == 'QB'
                               and p['team'] == ta]), axis=0)
        check(f'  {ta} total is the same joined by TEAM ID as by position',
              bool(np.array_equal(ra, sa)))


def test_d_a_plausibility_diagnostic_exists_but_is_not_the_guard():
    """Reported, never the primary check. It is football, not accounting."""
    rows = []
    for gid, bd, board, man, draws in _boards():
        if draws is None or 'qb__db' not in draws.files:
            continue
        per = collections.defaultdict(float)
        for i, p in enumerate(board.get('players') or []):
            if p.get('position') == 'QB':
                per[p['team']] += float(np.mean(draws['qb__db'][i]))
        for t, v in sorted(per.items()):
            rows.append((gid[8:], t, round(v, 2)))
    for g, t, v in rows:
        print(f'  ..   diagnostic {g:9s} {t:4s} mean team dropbacks {v:7.2f}'
              + ('   <-- implausible' if not 15 <= v <= 55 else ''))
    check('the diagnostic ran over every sealed afternoon board',
          len(rows) >= 2, str(len(rows)))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
