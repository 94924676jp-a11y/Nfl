"""SENSITIVITY (reviewer): unmodified harness, except depth_shares() (rank shares AND appearance rates)
is measured over the same player universe the allocation pool uses: roster position where known, else
the harness's own usage-inferred position for seasons <= through (no seasons after `through`).
Monkeypatch in-process only; nothing in the repository is written."""
import csv, sys, gzip
from nfl.tools import forward_chain as FC, player_prior, proj_v1 as V
seasons = [int(x) for x in sys.argv[1].split(',')]; out = sys.argv[2]
panel = player_prior.load_panel().value
roster = player_prior.position_index()
pos_map, inferred = FC.positions_for_chain(panel, roster)
_ds = V.depth_shares
def depth_fixed(panel_, pos_of, through=None):
    aug = dict(roster)
    for (g, s), p in sorted(pos_map.items(), key=lambda x: x[0][1]):
        if g not in roster and s <= through:
            aug[g] = p
    return _ds(panel_, aug, through=through)
V.depth_shares = depth_fixed
captured = {}
_orig = FC.project_week
def wrapped(panel, season_pos, season, week, *a, **k):
    proj = _orig(panel, season_pos, season, week, *a, **k)
    captured[(season, week)] = (dict(proj), set(FC.POOL[0]))
    return proj
FC.project_week = wrapped
FC.evaluate(panel, roster, seasons, [('PROD', 1.0, 2.0)])
with gzip.open(out, 'wt', newline='') as fh:
    w = csv.writer(fh); w.writerow(['season', 'week', 'gsis', 'proj_aug'])
    for (s, wk), (proj, pool) in sorted(captured.items()):
        for g, p in proj.items():
            if p is not None and g in pool:
                w.writerow([s, wk, g, round(p, 4)])
print('weeks', len(captured))
