import sys, pathlib, collections, json
W = pathlib.Path('/home/user/p0work/nfl-w5'); sys.path.insert(0, str(W))
from nfl.tools import player_prior as PP, role_state_history as RSH, proj_v1 as PV
panel = PP.load_panel().value; pos_of = PP.position_index()
ds = PV.depth_shares(panel, pos_of) if 'depth_shares' in dir(PV) else None
res = collections.defaultdict(lambda: [0, 0])
for s in range(2021, int(sys.argv[2]) + 1 if len(sys.argv) > 2 else 2027):
    weeks = sorted({int(w) for g in panel['players'].values() for w in (g.get(str(s)) or {})})
    for wk in weeks:
        if wk < 4: continue
        dep = RSH.pregame_depth(panel, pos_of, s, wk)
        for g, d in dep.items():
            r = d.get('pregame_rank'); pos = d['position']
            if r is None or pos not in ('RB', 'WR', 'TE'): continue
            ss = panel['players'][g].get(str(s)) or {}
            prior3 = all(str(wk - k) in ss and ss[str(wk - k)].get('team') == d['club'] for k in (1, 2, 3))
            key = f"{pos}|rank_{min(r, 6)}|{'played_prior3' if prior3 else 'not_all_prior3'}"
            res[key][1] += 1
            row = ss.get(str(wk))
            res[key][0] += 1 if (row and row.get('team') == d['club']) else 0
out = {k: {'n': v[1], 'appeared_rate': round(v[0] / v[1], 3)} for k, v in sorted(res.items())}
if ds:
    for pos in ('RB', 'WR', 'TE'):
        out[f'ENGINE_TABLE_{pos}'] = {k: v.get('appearance_rate') for k, v in (ds.get(pos) or {}).get('by_rank', {}).items()}
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
for k, v in out.items(): print(k, v)
