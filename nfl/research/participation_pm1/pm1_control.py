#!/usr/bin/env python3.12
"""PM-1 control: the workload-share distribution r/r0 of UNDESIGNATED player-games, fit seasons only.

    python3.12 nfl/research/participation_pm1/pm1_control.py      -> PM1_CONTROL.json

WHY. PM-1's r_rel distribution for a designated player mixes two things: the injury's effect and the ordinary
week-to-week swing of any player's share around his own baseline. The game simulator already draws that ordinary
swing (Dirichlet share dispersion, nfl/sim/game.py), so feeding it the designated distribution as-is would count the
ordinary swing twice. The per-world participation factor is therefore the QUANTILE RATIO
    phi(u) = q_designated(u) / q_control(u),  clipped to [0, 1]
at each level u of a 101-point grid, with q_control measured here on the same definition (same baseline rule, same
seasons, same position groups) for player-games with no game designation. This is a derivation, declared in
nfl/sim/participation.py, not a fitted constant. Fit seasons only (2016-2023); the held-out seasons are not read.
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pm1  # noqa: E402

HERE = pathlib.Path(__file__).parent


def control_units(seasons):
    pg = {s: pm1.player_games(s) for s in seasons}
    inj = {s: pm1.injury_rows(s) for s in seasons}
    hist = collections.defaultdict(list)
    for s, games in pg.items():
        for (week, club), g in games.items():
            for p, (n_on, _l) in g['on'].items():
                d = (inj[s].get((week, club, p)) or {}).get('report_status') in ('Questionable', 'Doubtful', 'Out')
                hist[p].append((s, week, club, n_on / g['n_team'] if g['n_team'] else 0.0, d))
    for v in hist.values():
        v.sort()
    # position from the injury files (the only position source for these seasons): a player's most common listing
    pos_of = collections.Counter()
    pos_votes = collections.defaultdict(collections.Counter)
    for s in seasons:
        for (_w, _c, p), r in inj[s].items():
            g = pm1.SKILL.get(r.get('position'))
            if g:
                pos_votes[p][g] += 1
    pos = {p: c.most_common(1)[0][0] for p, c in pos_votes.items()}
    out = collections.defaultdict(list)
    n_by = collections.Counter()
    for p, h in hist.items():
        if p not in pos:
            n_by['NO_POSITION_SOURCE'] += 1
            continue
        for i, (s, week, club, r, d) in enumerate(h):
            if d or r <= 0:
                continue
            prior = [x for x in h[:i] if x[0] == s and x[2] == club and not x[4] and x[3] > 0][-4:]
            if len(prior) < 2:
                continue
            r0 = statistics.median(x[3] for x in prior)
            if r0 > 0:
                out[pos[p]].append(r / r0)
                n_by[pos[p]] += 1
    return out, dict(n_by)


def main() -> int:
    vals, n_by = control_units(pm1.FIT)
    doc = {'ARTIFACT': 'PM1_CONTROL', 'fit_seasons': list(pm1.FIT), 'grid': pm1.GRID,
           'MEANING': 'r/r0 for undesignated player-games that played, same baseline rule as PM-1, by position group',
           'POSITION_SOURCE': 'most common position listing in the injury files (players never on a report are not '
                              'in this control; counted under NO_POSITION_SOURCE)',
           'n': n_by, 'quantiles': {g: pm1._quantiles(v) for g, v in vals.items()}}
    (HERE / 'PM1_CONTROL.json').write_text(json.dumps(doc, indent=1) + '\n')
    for g, q in doc['quantiles'].items():
        print(g, n_by[g], 'p10/p50/p90', q[10], q[50], q[90])
    print('NO_POSITION_SOURCE', n_by.get('NO_POSITION_SOURCE'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
