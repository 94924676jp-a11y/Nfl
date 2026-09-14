from __future__ import annotations
import pickle, collections, numpy as np, json
rows=pickle.load(open('/tmp/ws08_rows.pkl','rb'))
RNG=np.random.default_rng(20260914)
def crps(d,y):
    d=np.sort(np.asarray(d,float));n=d.size;i=np.arange(1,n+1)
    return float(np.mean(np.abs(d-y)))-float(np.sum((2*i-n-1)*d))/(n*n)
def clus(vals, keys):
    g=collections.defaultdict(list)
    for k,v in zip(keys,vals): g[k].append(v)
    gm=np.array([np.mean(v) for v in g.values()])
    return float(np.mean(vals)), float(gm.std(ddof=1)/np.sqrt(len(gm))), len(gm)
games=[r['game'] for r in rows]
print('=== game-clustered SEs, 5 clusters (PRECISION SUPPRESSED, see note) ===')
for nm,kd,ka in (('targets','T','aT'),('receptions','R','aR'),('rec_yds','Y','aY'),('rec_td','D','aD')):
    e=[r[kd].mean()-r[ka] for r in rows]
    m,se,ng=clus(e,games)
    print(f'{nm:<12} bias {m:+.2f}  game-clustered SE {se:.2f} (n_clusters={ng})  '
          f'naive SE {np.std(e,ddof=1)/np.sqrt(len(e)):.2f}  ratio {se/(np.std(e,ddof=1)/np.sqrt(len(e))):.2f}x')
print()
print('=== per-game receiving-yard summary ===')
for g in sorted(set(games)):
    rs=[r for r in rows if r['game']==g]
    mu=np.array([r['Y'].mean() for r in rs]); y=np.array([r['aY'] for r in rs])
    print(f'{g:<18} n={len(rs):3d} pred_tot={mu.sum():6.1f} act_tot={y.sum():6.1f} '
          f'bias/pl={np.mean(mu-y):+6.2f} MAE={np.abs(mu-y).mean():6.2f} '
          f'CRPS={np.mean([crps(r["Y"],r["aY"]) for r in rs]):6.2f}')
print()
print('=== biggest individual receiving-yard misses (forecast mean vs actual) ===')
sr=sorted(rows,key=lambda r:-abs(r['Y'].mean()-r['aY']))[:12]
for r in sr:
    print(f"  {r['name'] or r['pid']:<14} {r['pos']} {r['team']} rank{r['rank']:<2} "
          f"pred T {r['T'].mean():5.2f}/R {r['R'].mean():5.2f}/Y {r['Y'].mean():6.1f} | "
          f"act T {r['aT']:.0f}/R {r['aR']:.0f}/Y {r['aY']:6.1f} | err {r['Y'].mean()-r['aY']:+7.1f}")
