"""Per-draw accounting for the DET-BUF board. Rows mapped by manifest ID only.

WHY THE ROW MAPPING RULE IS THE FIRST THING HERE. I indexed these arrays by the
BOARD's player order and reported that passing and receiving yards diverge by
381 yards per draw, concluding the engine had no joint game world. The arrays
are ordered by the manifest's `row_ids`, and the two differ -- the QB layer is
[00-0034577, 00-0034857, 00-0033106, 00-0033949], which is BUF, BUF, DET, DET,
while the board lists Goff, Allen, Dobbs, Allen. I summed a Buffalo
quarterback into Detroit and read the result as an architectural defect.

So every check below resolves rows through `layers[*].row_ids` and never
through board order.

THE SECOND RULE: FLOAT SUMS NEED A TOLERANCE. I also reported passing yards
failing conservation in 21 of 1000 draws. They do not -- the differences are
5.7e-14, float summation artifacts of adding 12 arrays in a different order
from 2. An exact `==` on a sum of float arrays is the wrong test and I wrote it
twice before catching it.

THE THIRD: A SUM THAT DOES NOT CLOSE MAY BE A TERM YOU FORGOT. The carry
residual -- 0.16 DET and 0.43 BUF -- was QB SCRAMBLES. `rush_category` carries
`designed_qb`, which is designed runs ONLY; scrambles are a separate QB
quantity and a lawful rush owner. rushing_a1 states the identity in its own
docstring: rb = published - scr - designed - kneel - wr - te - fringe. Adding
the term closes it exactly, 1000/1000 on both clubs. The engine was right and
my accounting was short a column.

Run standalone:  python3.12 nfl/tests/test_detbuf_conservation.py <run_dir>
"""
import json
import os
import pathlib
import sys

import numpy as np

PASSED = FAILED = 0
NOT_EXECUTED = []
TOL = 1e-6          # float sums of ~10 arrays; observed worst case 5.7e-14


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  ..   NOT_EXECUTED {label} -- {why}')


def load(run_dir):
    man = json.load(open(os.path.join(run_dir, 'player_draws_manifest.json')))
    z = np.load(os.path.join(run_dir, 'player_draws.npz'), allow_pickle=True)
    board = json.load(open(os.path.join(run_dir, 'board.json')))
    team = {p['gsis_id']: p['team'] for p in board['players']}
    rid = {k: v['row_ids'] for k, v in man['layers'].items()}
    return z, rid, team, board


def rows(rid, layer, tm, team):
    """Row indices for a team, resolved through the MANIFEST, never the board."""
    return [i for i, g in enumerate(rid.get(layer) or [])
            if (g == tm or team.get(g) == tm)]


def audit(run_dir):
    z, rid, team, board = load(run_dir)
    teams = sorted({p['team'] for p in board['players']})
    for tm in teams:
        print(f'\n--- {tm} ---')
        q = rows(rid, 'qb', tm, team)
        r = rows(rid, 'receiving', tm, team)
        ru = rows(rid, 'rushing', tm, team)
        tvi = rows(rid, 'team_volume', tm, team)
        rci = rows(rid, 'rush_category', tm, team)
        if not (q and r and tvi and rci):
            not_executed(f'{tm} layers present', 'a layer carries no row')
            continue

        att = z['qb__att'][q].sum(0)
        tgt = z['receiving__targets'][r].sum(0)
        py = z['qb__pyds'][q].sum(0)
        ry = z['receiving__receiving_yards'][r].sum(0)
        ptd = z['qb__ptd'][q].sum(0)
        rtd = z['receiving__receiving_td'][r].sum(0)
        budget = np.rint(z['team_volume__team_targets'][tvi[0]])
        tc = z['team_volume__team_carries'][tvi[0]]
        cats = sum(z[f'rush_category__{c}'][rci[0]]
                   for c in ('rb', 'te', 'wr', 'designed_qb', 'kneel',
                             'fringe'))
        scr = z['qb__scr'][q].sum(0)
        pc = z['rushing__carries'][ru].sum(0) if ru else 0
        pool = z['rush_player_pool__unmodelled_back_pool'][rci[0]]
        n = att.shape[0]

        check(f'{tm} 5  passing yards == receiving yards',
              int((np.abs(py - ry) < TOL).sum()) == n,
              f'{int((np.abs(py - ry) < TOL).sum())}/{n}, '
              f'worst {np.abs(py - ry).max():.2e}')
        check(f'{tm} 6  passing TD == receiving TD',
              int((ptd == rtd).sum()) == n,
              f'{int((ptd == rtd).sum())}/{n}')
        check(f'{tm} 2  targets <= attempts',
              int((tgt <= att).sum()) == n, f'{int((tgt <= att).sum())}/{n}')
        check(f'{tm} 3  targets <= published team budget',
              int((tgt <= budget).sum()) == n,
              f'{int((tgt <= budget).sum())}/{n} -- the budget must be the '
              f'level the multinomial dealt from, not D1\'s unconsumed draw')
        # THE ONE THAT NEEDED THE MISSING TERM.
        check(f'{tm} 7  team carries == six categories + QB scrambles',
              int(((cats + scr) == tc).sum()) == n,
              f'{int(((cats + scr) == tc).sum())}/{n}; scrambles are a rush '
              f'owner and are NOT inside designed_qb')
        check(f'{tm} 8  rb category == named players + unmodelled pool',
              int((z['rush_category__rb'][rci[0]] == pc + pool).sum()) == n,
              f'every carry dealt to the backs has an owner, named or pooled')
        check(f'{tm}    team carries are integral, not D1\'s continuous draw',
              bool(np.allclose(tc, np.rint(tc))),
              'a continuous level is not the level a partition consumed')



# ---------------------------------------------------------------- the runner
# THIS MODULE'S CHECKS WERE NEVER EXECUTED BY `run_suite`. It takes a run
# directory as a command-line argument and exposes no `test_*` function, so
# the runner discovered nothing to call. Found 2026-09-23 by the
# TEST_MODULE_NOT_EXECUTED guard added the same day -- which is the guard
# finding a module nobody knew was silent, one hour after it was written.
#
# The repair keeps the module usable as a targeted tool (`python3.12
# test_detbuf_conservation.py <run_dir>` still works) and adds a `test_*`
# that SELECTS a sealed DET-BUF run itself, so the checks run unattended.
# When no such run exists it records BLOCKED -- "could not measure" is not
# "measured and passed".
def _newest_detbuf_run():
    """A sealed DET-BUF run carrying the layers these checks read."""
    # SEALED BOARDS ONLY. The newest DET-BUF manifest is the REFUSED run
    # `fced077d0db6ab41`, which never produced a board -- picking it by
    # mtime is how this landed on R1 the moment it became visible.
    # `sealed_boards()` reads each directory's own declaration.
    from nfl.research import sealed_index as _SI
    cands = [p for p in _SI.sealed_boards()
             if '2026_02_DET_BUF' in str(p)]
    if not cands:
        return None
    cands.sort(key=lambda q: q.stat().st_mtime, reverse=True)
    return str(cands[0].parent)


def test_the_detbuf_board_conserves():
    global PASSED, FAILED
    d = _newest_detbuf_run()
    if d is None:
        not_executed('detbuf conservation',
                     'no sealed DET-BUF run carrying a draw manifest exists '
                     'in this checkout, so the accounting has nothing to be '
                     'audited on')
        return
    audit(d)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: test_detbuf_conservation.py <run_dir>')
        raise SystemExit(2)
    audit(sys.argv[1])
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
