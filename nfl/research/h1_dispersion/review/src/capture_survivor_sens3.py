"""SENSITIVITY (reviewer): re-run the unmodified harness with the roster-derived position index
augmented by usage-inferred positions for players absent from the 2026 roster blobs, so cohort priors,
depth/group shares and TD/bonus fits are no longer restricted to players who survived to 2026.
Monkeypatch only, in this process; nothing in the repository is written."""
import csv, sys, gzip
from nfl.tools import forward_chain as FC, player_prior
seasons = [int(x) for x in sys.argv[1].split(',')]; out = sys.argv[2]
po = player_prior.load_panel(); panel = po.value
roster = player_prior.position_index()
aug = dict(roster)
for g, ss in panel['players'].items():
    if g in aug: continue
    pa = sum((w.get('pass_attempts') or 0) for s in ss.values() for w in s.values())
    ca = sum((w.get('carries') or 0) for s in ss.values() for w in s.values())
    tg = sum((w.get('targets') or 0) for s in ss.values() for w in s.values())
    if pa >= 10 and pa >= ca and pa >= tg: aug[g] = 'QB'
    elif ca > tg: aug[g] = 'RB'
    elif tg > 0: aug[g] = 'WR'
import os
if os.environ.get("PATCH_COHORT","1")=="1": player_prior.position_index = lambda: aug
player_prior._COHORT_CACHE.clear()

from nfl.tools import proj_v1 as V, td_rates as TR
_keep = os.environ.get("FIT_ROSTER","").split(",")
def _wrap(mod, name):
    f = getattr(mod, name)
    def g(panel, pos_of, *a, **k):
        return f(panel, roster, *a, **k)
    setattr(mod, name, g)
for key, mod, name in (("depth", V, "depth_shares"), ("group", V, "group_shares"), ("bonus", V, "bonus_rates"), ("int", V, "int_rate"), ("td", TR, "positional_rates")):
    if key in _keep: _wrap(mod, name)
captured = {}
_orig = FC.project_week
def wrapped(panel, season_pos, season, week, *a, **k):
    proj = _orig(panel, season_pos, season, week, *a, **k)
    captured[(season, week)] = (dict(proj), set(FC.POOL[0]))
    return proj
FC.project_week = wrapped
FC.evaluate(panel, aug if os.environ.get("PATCH_EVAL","1")=="1" else roster, seasons, [('PROD', 1.0, 2.0)])
with gzip.open(out, 'wt', newline='') as fh:
    w = csv.writer(fh); w.writerow(['season', 'week', 'gsis', 'proj_aug', 'in_roster'])
    for (s, wk), (proj, pool) in sorted(captured.items()):
        for g, p in proj.items():
            if p is not None and g in pool:
                w.writerow([s, wk, g, round(p, 4), int(g in roster)])
print('augmented', len(aug) - len(roster), 'players; weeks', len(captured))
