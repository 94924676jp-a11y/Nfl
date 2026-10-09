"""Grade replay arms against realised DK points of the replayed week (full panel; fumbles and 2-pt not in the panel, so
both arms omit them identically). Graded set: players with a realised panel row (they appeared and recorded a play
measure); a player with no row is reported separately, never scored as zero."""
import json, sys, pathlib, collections, math
import numpy as np
W = pathlib.Path('/home/user/p0work/nfl-w5'); sys.path.insert(0, str(W))
from nfl.tools import player_prior as PP
from nfl.product import dk_scoring as DK
panel = PP.load_panel().value
R = pathlib.Path(sys.argv[1]); wk = sys.argv[2]; arms = sys.argv[3].split(',')
def actual(g):
    r = ((panel['players'].get(g) or {}).get('2026') or {}).get(wk)
    if not r: return None, None
    v = DK.skill_points(1, pass_yds=r.get('pass_yards') or 0, pass_td=r.get('pass_td') or 0, ints=r.get('interceptions') or 0,
                        rush_yds=r.get('rush_yards') or 0, rush_td=r.get('rush_td') or 0, rec=r.get('receptions') or 0,
                        rec_yds=r.get('rec_yards') or 0, rec_td=r.get('rec_td') or 0)
    return float(np.asarray(v).ravel()[0]), r
P = {a: json.loads((R / f'W{wk}_{a}' / 'PROJ.json').read_text())['rows'] for a in arms}
base = P[arms[0]]
rows = []
for k, r in base.items():
    if r['position'] not in ('QB', 'RB', 'WR', 'TE') or not r.get('gsis_id'): continue
    act, ar = actual(r['gsis_id'])
    rec = {'name': r['name'], 'team': r.get('team'), 'pos': r['position'], 'actual': act,
           'targets_actual': (ar or {}).get('targets'), 'carries_actual': (ar or {}).get('carries')}
    for a in arms:
        q = P[a].get(k) or {}
        rec[a] = q.get('dk_points'); rec[a + '_ceiling'] = q.get('askable_ceiling'); rec[a + '_band'] = q.get('role_band')
        rec[a + '_targets'] = q.get('targets'); rec[a + '_carries'] = q.get('carries')
    rows.append(rec)
def stats(sub, a):
    e = [r[a] - r['actual'] for r in sub if isinstance(r[a], (int, float))]
    if not e: return None
    e = np.array(e); return {'n': len(e), 'MAE': round(float(np.abs(e).mean()), 3), 'RMSE': round(float(np.sqrt((e ** 2).mean())), 3), 'bias': round(float(e.mean()), 3)}
graded = [r for r in rows if r['actual'] is not None]
changed = [r for r in graded if any(abs((r[a] or 0) - (r[arms[0]] or 0)) > 0.05 for a in arms[1:])]
out = {'week': wk, 'n_rows': len(rows), 'n_graded': len(graded), 'n_no_panel_row': len(rows) - len(graded), 'all_graded': {}, 'changed_players': {}, 'by_pos': {}}
for a in arms:
    out['all_graded'][a] = stats(graded, a); out['changed_players'][a] = stats(changed, a)
    out['by_pos'][a] = {p: stats([r for r in graded if r['pos'] == p], a) for p in ('QB', 'RB', 'WR', 'TE')}
# paired difference on changed players with a game-cluster bootstrap
if changed:
    rng = np.random.default_rng(20261009)
    teams = sorted({r['team'] for r in changed})
    for a in arms[1:]:
        d_by = collections.defaultdict(list)
        for r in changed:
            d_by[r['team']].append(abs(r[a] - r['actual']) - abs(r[arms[0]] - r['actual']))
        boots = []
        for _ in range(4000):
            pick = rng.choice(teams, len(teams)); v = [x for t in pick for x in d_by[t]]; boots.append(np.mean(v))
        allv = [x for t in teams for x in d_by[t]]
        out[f'paired_absolute_error_change_{a}_minus_{arms[0]}'] = {'mean': round(float(np.mean(allv)), 3),
            'ci95_club_bootstrap': [round(float(np.percentile(boots, 2.5)), 3), round(float(np.percentile(boots, 97.5)), 3)],
            'n_players': len(allv), 'n_clubs': len(teams)}
out['changed_rows'] = sorted(changed, key=lambda r: (r['team'], r['pos'], -(r['actual'] or 0)))
pathlib.Path(sys.argv[4]).write_text(json.dumps(out, indent=1, default=str))
print(json.dumps({k: v for k, v in out.items() if k != 'changed_rows'}, indent=1))
