"""WS08 part 3: is the V (yards-per-catch) residual reachable by air yards?
Historical panel 2021-2024 from nflverse pbp. EXPLORATORY."""
from __future__ import annotations
import gzip, csv, glob, collections, pickle, math
import numpy as np

FILES = sorted(glob.glob('/home/user/nfl/nfl/research/postgame/pbp_202[1-4].*.csv.gz'))
print('files:', [f.split('/')[-1] for f in FILES])

def f(v, d=None):
    try: return float(v)
    except (TypeError, ValueError): return d

panel = {}     # (season,week,team,pid) -> dict
nulls = collections.Counter()
for path in FILES:
    with gzip.open(path, 'rt') as fh:
        for r in csv.DictReader(fh):
            if not (r.get('receiver_player_id') and r.get('pass_attempt') == '1'):
                continue
            k = (int(r['season']), int(r['week']), r.get('posteam') or '',
                 r['receiver_player_id'])
            d = panel.setdefault(k, dict(T=0, R=0, Y=0.0, AYt=0.0, AYc=0.0,
                                         YAC=0.0, ay_null_t=0, ay_null_c=0,
                                         catches=[], ay_catch=[], yac_catch=[],
                                         name=r.get('receiver_player_name') or '',
                                         game=r['game_id']))
            d['T'] += 1
            ay = f(r.get('air_yards'))
            if ay is None: d['ay_null_t'] += 1; nulls['t'] += 1
            else: d['AYt'] += ay
            if r.get('complete_pass') == '1':
                d['R'] += 1
                ry = f(r.get('receiving_yards'), 0.0)
                yc = f(r.get('yards_after_catch'))
                d['Y'] += ry
                d['catches'].append(ry)
                if ay is None: d['ay_null_c'] += 1; nulls['c'] += 1
                else:
                    d['AYc'] += ay; d['ay_catch'].append(ay)
                if yc is None: nulls['yac'] += 1
                else: d['YAC'] += yc; d['yac_catch'].append(yc)
print(f'player-games: {len(panel)}; null air_yards on targets {nulls["t"]}, '
      f'on catches {nulls["c"]}, null yac {nulls["yac"]}')

rows = []
for (s, w, t, pid), d in panel.items():
    d.update(season=s, week=w, team=t, pid=pid)
    d['V'] = d['Y'] / d['R'] if d['R'] else None
    d['aDOTc'] = d['AYc'] / d['R'] if d['R'] else None
    d['YACc'] = d['YAC'] / d['R'] if d['R'] else None
    d['aDOTt'] = d['AYt'] / d['T'] if d['T'] else None
    rows.append(d)
rows.sort(key=lambda r: (r['season'], r['week'], r['team'], r['pid']))

rec = [r for r in rows if r['R'] > 0]
V = np.array([r['V'] for r in rec]); A = np.array([r['aDOTc'] for r in rec])
Yc = np.array([r['YACc'] for r in rec])
print(f'\nrows with >=1 reception: {len(rec)}')
print(f'identity check  mean|V-(aDOTc+YACc)| = {np.abs(V-(A+Yc)).mean():.4f}')
print(f'Var(V)={V.var():.2f}  Var(aDOTc)={A.var():.2f}  Var(YACc)={Yc.var():.2f}  '
      f'2Cov={2*np.cov(A,Yc)[0,1]:.2f}')
print(f'share of Var(V):  aDOT {A.var()/V.var()*100:.1f}%  YAC {Yc.var()/V.var()*100:.1f}%  '
      f'cov {2*np.cov(A,Yc)[0,1]/V.var()*100:.1f}%')

# ---- strictly-prior history per player (ordinal prefix, never 'so far')
hist = collections.defaultdict(list)
for r in rows:
    h = hist[r['pid']]
    n = len(h)
    r['h_n'] = n
    if n:
        hT = sum(x['T'] for x in h); hR = sum(x['R'] for x in h)
        hY = sum(x['Y'] for x in h); hAY = sum(x['AYc'] for x in h)
        hAYt = sum(x['AYt'] for x in h); hYAC = sum(x['YAC'] for x in h)
        r['p_V'] = hY / hR if hR else None
        r['p_aDOTc'] = hAY / hR if hR else None
        r['p_aDOTt'] = hAYt / hT if hT else None
        r['p_YACc'] = hYAC / hR if hR else None
    else:
        r['p_V'] = r['p_aDOTc'] = r['p_aDOTt'] = r['p_YACc'] = None
    h.append(r)

def rr(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]), int(m.sum())

print('\n=== PERSISTENCE: can a STRICTLY PRIOR history predict this game? ===')
sub = [r for r in rec if r['h_n'] >= 4 and r['p_V'] is not None]
print(f'n (>=4 prior games, prior receptions exist) = {len(sub)}')
for nm, pk, ak in (('yards per catch V', 'p_V', 'V'),
                   ('aDOT per catch', 'p_aDOTc', 'aDOTc'),
                   ('aDOT per target', 'p_aDOTt', 'aDOTt'),
                   ('YAC per catch', 'p_YACc', 'YACc')):
    c, n = rr([r[pk] for r in sub], [r[ak] for r in sub])
    print(f'  prior {nm:<18} -> realised   r={c:+.3f}  r2={c*c:.3f}  n={n}')

# weight by receptions: a 1-catch game is a noisy V
wsub = [r for r in sub if r['R'] >= 3]
print(f'\n  restricted to games with >=3 receptions (n={len(wsub)}):')
for nm, pk, ak in (('yards per catch V', 'p_V', 'V'),
                   ('aDOT per catch', 'p_aDOTc', 'aDOTc'),
                   ('YAC per catch', 'p_YACc', 'YACc')):
    c, n = rr([r[pk] for r in wsub], [r[ak] for r in wsub])
    print(f'  prior {nm:<18} -> realised   r={c:+.3f}  r2={c*c:.3f}  n={n}')

pickle.dump(rows, open('/tmp/ws08_hist.pkl', 'wb'))
