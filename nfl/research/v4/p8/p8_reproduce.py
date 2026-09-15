"""P8: the failing reproduction, as one criterion against one arm.

    python3.12 nfl/research/v4/p8/p8_reproduce.py incumbent   -> exit 1
    python3.12 nfl/research/v4/p8/p8_reproduce.py candidate    -> exit 0

THE CRITERION, WRITTEN BEFORE THE REPAIR AND UNCHANGED BY IT. The rate of
simulated quarterback games above the all-time NFL single-game passing record
of 554 yards must lie inside the one-sided 95% upper bound implied by zero such
games in the 3,787 realised QB game-lines the engine resamples,
1 - 0.05^(1/3787) = 7.907e-04. The bound is DERIVED from the donor pool, not
chosen, and it is recomputed here on every run rather than written down.

This is a rate criterion, not a fence on a cell. Nothing is clipped, truncated
or rejected anywhere on this path, and a repair that passed this by narrowing
the support would be the defect this project pays most for wearing a green
tick.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
_REPO = HERE.parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb2'),
           str(_REPO / 'nfl' / 'research' / 'v3' / 'h1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import h1_frame as FR                                             # noqa: E402
import qb2_lib as Q                                               # noqa: E402

RECORD = 554.0
ALPHA = 0.05
ARM = {'incumbent': Q.YPC_SPEC_GAME_RATIO,
       'candidate': Q.YPC_SPEC_COMPLETION_BLOCKS}


def main(arm):
    if arm not in ARM:
        print(f'P8_ARM_UNKNOWN: {arm!r}; declared {sorted(ARM)}')
        return 2
    rows, _ = FR.build()
    Q.attach(rows)
    n = np.array([r['cmp'] for r in rows if r['cmp'] > 0], float)
    y = np.array([r['pyds'] for r in rows if r['cmp'] > 0], float)
    if int((y > RECORD).sum()):
        print('P8_POOL_ALREADY_ABOVE_RECORD: the bound is not derivable')
        return 2
    bound = 1.0 - ALPHA ** (1.0 / len(y))
    keep = [r for r in rows if r['season'] == 2025 and Q.eligible(r)]
    P = Q.simulate(keep, 2025, rows, seed=20260908, m=1000, rung='L1',
                   ypc_spec=ARM[arm])['pyds']
    k = int((P > RECORD).sum())
    rate = k / P.size
    print(f'arm                {arm}')
    print(f'donor pool         {len(y)} realised QB game-lines, maximum '
          f'{y.max():.0f} yards, {int((y > RECORD).sum())} above {RECORD:.0f}')
    print(f'derived bound      {bound:.6e}  (one-sided 95%, zero of '
          f'{len(y)})')
    print(f'cohort             {len(keep)} rows x 1000 draws = {P.size} cells')
    print(f'cells above {RECORD:.0f}    {k}')
    print(f'rate               {rate:.6e}  ({rate / bound:.2f}x the bound)')
    print(f'maximum            {P.max():.0f} yards')
    print(f'minimum            {P.min():.0f} yards')
    print(f'cells below -30    {int((P < -30).sum())}')
    if rate > bound:
        print(f'\nFAIL P8_UPPER_TAIL_OUTSIDE_DERIVED_BOUND: {rate:.6e} > '
              f'{bound:.6e}')
        return 1
    print('\nPASS P8_UPPER_TAIL_INSIDE_DERIVED_BOUND')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else 'incumbent'))
