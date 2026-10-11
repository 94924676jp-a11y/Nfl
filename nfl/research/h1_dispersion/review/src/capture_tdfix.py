"""SENSITIVITY (reviewer): unmodified harness except the three fits that see future seasons are
restricted to seasons <= S-1: positional TD rates, league INT rate, and the 0.6156 pass share of TDs
(recomputed from td_rates.pass_rush_split restricted the same way). Monkeypatch only."""
import csv, sys, gzip
from nfl.tools import forward_chain as FC, player_prior, proj_v1 as V, td_rates as TR
seasons = [int(x) for x in sys.argv[1].split(',')]; out = sys.argv[2]
panel = player_prior.load_panel().value
roster = player_prior.position_index()
queue = list(seasons); cur = {}
_pr, _ir, _ps = TR.positional_rates, V.int_rate, TR.pass_rush_split
def pr(panel_, pos_of):
    s = queue.pop(0); cur['s'] = s
    TR.FIT_SEASONS = tuple(x for x in (2021, 2022, 2023, 2024, 2025) if x <= s - 1)
    r = _pr(panel_, pos_of)
    ps = _ps(panel_)
    cur['ps'] = ps.get('mean_pass_share_of_offensive_td')
    TR.FIT_SEASONS = (2021, 2022, 2023, 2024, 2025)
    return r
def ir(panel_, pos_of, through=None):
    return _ir(panel_, pos_of, through=cur['s'] - 1)
TR.positional_rates = pr; V.int_rate = ir
_act = V.allocate_club_td
def act(pool, pass_share, rows, rates):
    return _act(pool, cur['ps'], rows, rates)
V.allocate_club_td = act
captured = {}
_orig = FC.project_week
def wrapped(panel, season_pos, season, week, *a, **k):
    proj = _orig(panel, season_pos, season, week, *a, **k)
    captured[(season, week)] = (dict(proj), set(FC.POOL[0]))
    return proj
FC.project_week = wrapped
FC.evaluate(panel, roster, seasons, [('PROD', 1.0, 2.0)])
print('pass share used', cur.get('ps'))
with gzip.open(out, 'wt', newline='') as fh:
    w = csv.writer(fh); w.writerow(['season', 'week', 'gsis', 'proj_aug'])
    for (s, wk), (proj, pool) in sorted(captured.items()):
        for g, p in proj.items():
            if p is not None and g in pool:
                w.writerow([s, wk, g, round(p, 4)])
