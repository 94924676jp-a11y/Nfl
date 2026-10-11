"""Track B diagnostic (read-only): per-player forward-chained projections vs DK actuals.

    cd /home/user/nfl && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/user/p0work/pylib:. \
        python3.12 /tmp/claude-0/trackb/capture_rows.py 2024,2025 OUT.csv

Production arm = blend 1.0, PRIOR_WEIGHT_CAP 2.0 (nfl/tools/proj_v1.py:104). Two scorings per row:
  conditional   the player appeared (actual = his DK points)
  unconditional every pool candidate; one who did not appear scores 0 (the DFS payoff)
Writes only OUT.csv. Imports the repository's own harness (nfl/tools/forward_chain.py) unmodified.
"""
import csv, sys
from nfl.tools import forward_chain as FC, player_prior

seasons = [int(x) for x in sys.argv[1].split(',')]
out = sys.argv[2]
captured = {}
_orig = FC.project_week


def wrapped(panel, season_pos, season, week, *a, **k):
    proj = _orig(panel, season_pos, season, week, *a, **k)
    arm = a[5] if len(a) > 5 else k.get('arm')
    cap = k.get('prior_cap')
    captured[(season, week, f'{arm}|{cap}')] = (dict(proj), set(FC.POOL[0]))
    return proj


FC.project_week = wrapped
po = player_prior.load_panel()
assert po.state.name == 'PASS', po
panel = po.value
pos_of = player_prior.position_index()
arms = [('PROD_blend1.0_cap2.0', 1.0, 2.0), FC.BASELINE_ARM]
FC.evaluate(panel, pos_of, seasons, arms)
pos_map, inferred = FC.positions_for_chain(panel, pos_of)
n = 0
with open(out, 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['season', 'week', 'arm', 'gsis', 'pos', 'proj', 'appeared', 'actual_dk'])
    for (season, week, arm), (proj, pool) in sorted(captured.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        season_pos = FC._SeasonPos(pos_map, season, pos_of)
        excluded = {g for (g, s) in inferred if s == season}
        for g, p in proj.items():
            if p is None or g not in pool or g in excluded or season_pos.get(g) not in FC.SKILL:
                continue
            wk = ((panel['players'].get(g) or {}).get(str(season)) or {}).get(str(week))
            appeared = bool(wk and wk.get('team'))
            w.writerow([season, week, arm, g, season_pos.get(g), round(p, 4), int(appeared),
                        round(FC.actual_dk(wk), 4) if appeared else 0.0])
            n += 1
print('rows', n, 'weeks', len({(s, wk) for s, wk, _ in captured}))
