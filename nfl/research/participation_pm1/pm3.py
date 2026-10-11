#!/usr/bin/env python3.12
"""PM-3: the participation factor phi by role band (PREREG_PM3, fd0c1633). P(no participation) stays PM-1's.

    python3.12 nfl/research/participation_pm1/pm3.py      -> PM3_PHI.json

Reads PM-2's fitted r/r0 quantiles (PM2_TABLE.json, fit seasons only) and recomputes the controls by (position group,
role band) from the same fit seasons. phi(u): interior grid u in [0.05, 0.95], the ratio q_des/q_ctl made
non-decreasing by pool-adjacent-violators (equal weights), clipped to [0, 1], levels outside the interior taking the
nearest interior value. No held-out season is read.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pm1  # noqa: E402
import pm2  # noqa: E402

HERE = pathlib.Path(__file__).parent
LO, HI = 5, 95                       # interior grid indices (u = 0.05 .. 0.95)
MIN_N = 30


def pava(xs):
    """Isotonic (non-decreasing) least-squares fit, equal weights."""
    blocks = []                       # [sum, count]
    for x in xs:
        blocks.append([x, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c
    out = []
    for s, c in blocks:
        out += [s / c] * c
    return out


def phi(q_des, q_ctl):
    if not q_des or not q_ctl:
        return None
    raw = [min(1.0, max(0.0, q_des[i] / q_ctl[i])) if q_ctl[i] > 0 else 1.0 for i in range(LO, HI + 1)]
    iso = [min(1.0, max(0.0, v)) for v in pava(raw)]
    return [round(v, 5) for v in [iso[0]] * LO + iso + [iso[-1]] * (len(q_des) - 1 - HI)]


def main() -> int:
    t2 = json.loads((HERE / 'PM2_TABLE.json').read_text())
    ctl, ctl_n = pm2.control_by_band(pm1.FIT)
    cells = {}
    for key, c in t2['cells'].items():
        parts = dict(zip(c['level'].split('|'), key.split('|')))
        pos, band = parts.get('pos'), parts.get('role')
        if not (pos and band) or c['n_r'] < MIN_N or not c.get('r_rel_quantiles'):
            continue
        f = phi(c['r_rel_quantiles'], ctl.get((pos, band)))
        if f:
            cells[key] = {'level': c['level'], 'n_r': c['n_r'], 'phi_quantiles': f, 'control': f'{pos}|{band}',
                          'p_early_exit_given_played': c['p_early_exit']}
    doc = {'ARTIFACT': 'PM3_PHI', 'prereg': 'PREREG_PM3_PARTICIPATION.md (fd0c1633)', 'fit_seasons': list(pm1.FIT),
           'levels': t2['levels'][:4], 'grid': pm1.GRID, 'interior': [pm1.GRID[LO], pm1.GRID[HI]], 'min_n': MIN_N,
           'control_n': ctl_n,
           'P_NO_PARTICIPATION': 'PM1_TABLE.json, unchanged, and only while game-day status is unresolved',
           'cells': cells}
    (HERE / 'PM3_PHI.json').write_text(json.dumps(doc, indent=1) + '\n')
    for k in ('R_GE_070|QUESTIONABLE|LIMITED|WR_TE|SOFT_TISSUE_LOWER', 'R_GE_070|QUESTIONABLE|LIMITED|WR_TE',
              'R_GE_070|QUESTIONABLE|FULL|WR_TE', 'R_GE_070|QUESTIONABLE|WR_TE', 'R_GE_070|QUESTIONABLE|RB',
              'R_GE_070|NONE_WITH_LIMITED_OR_DNP_PRACTICE|WR_TE', 'R_GE_070|QUESTIONABLE|QB'):
        c = cells.get(k)
        if c:
            q = c['phi_quantiles']
            print(f"{k:58s} n_r={c['n_r']:4d} phi p10/p25/p50/p75/p90 = {q[10]}, {q[25]}, {q[50]}, {q[75]}, {q[90]}")
        else:
            print(f'{k:58s} (no cell with n_r >= {MIN_N})')
    print('cells with phi:', len(cells))
    return 0


if __name__ == '__main__':
    sys.exit(main())
