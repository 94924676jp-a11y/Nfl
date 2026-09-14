"""WS08 part 7: COLD START -- where the positional pool dominates, does a
depth-banded pool help? Plus PIT on the 5-game prospective set."""
from __future__ import annotations
import pickle, collections, numpy as np
rows=pickle.load(open('/tmp/ws08_hist.pkl','rb')); K=4.0
RNG=np.random.default_rng(20260914)
hist=collections.defaultdict(lambda: dict(n=0,T=0,R=0,AYt=0.0,catches=[]))
for r in rows:
    h=hist[r['pid']]
    r['ph_n']=h['n']; r['ph_at']=(h['AYt']/h['T']) if h['T'] else None
    r['ph_catches']=list(h['catches'])
    h['n']+=1; h['T']+=r['T']; h['R']+=r['R']; h['AYt']+=r['AYt']; h['catches'].extend(r['catches'])
fit=[r for r in rows if r['season']<=2023]; ev=[r for r in rows if r['season']==2024]
pool_all=np.array([y for r in fit for y in r['catches']],float)
at=[r['ph_at'] for r in fit if r['ph_at'] is not None and r['ph_n']>=4]
q1,q2=np.percentile(at,[33.33,66.67])
band=lambda a: 0 if a is None else (0 if a<q1 else (1 if a<q2 else 2))
pool_b={k:[] for k in (0,1,2)}
for r in fit:
    if r['ph_n']>=4 and r['ph_at'] is not None: pool_b[band(r['ph_at'])].extend(r['catches'])
pool_b={k:np.array(v,float) for k,v in pool_b.items()}
def crps(d,y):
    d=np.sort(np.asarray(d,float));n=d.size;i=np.arange(1,n+1)
    return float(np.mean(np.abs(d-y)))-float(np.sum((2*i-n-1)*d))/(n*n)
M=1500
for lab,cond in (('COLD START h_n<4', lambda r: r['ph_n']<4),
                 ('h_n 1-3 with any prior aDOT', lambda r: 1<=r['ph_n']<4)):
    sel=[r for r in ev if r['R']>0 and cond(r) and r['ph_at'] is not None]
    if len(sel)<30: print(lab,'n too small',len(sel)); continue
    cb,cd=[],[]
    for r in sel:
        w=r['ph_n']/(r['ph_n']+K); own=np.asarray(r['ph_catches'],float); R=int(r['R'])
        use=RNG.random((M,R))<w if len(own) else np.zeros((M,R),bool)
        oi=own[RNG.integers(0,max(len(own),1),(M,R))] if len(own) else np.zeros((M,R))
        pb=pool_b[band(r['ph_at'])]
        cb.append(crps(np.where(use,oi,pool_all[RNG.integers(0,len(pool_all),(M,R))]).sum(1),r['Y']))
        cd.append(crps(np.where(use,oi,pb[RNG.integers(0,len(pb),(M,R))]).sum(1),r['Y']))
    cb=np.array(cb);cd=np.array(cd);d=cd-cb
    gg=collections.defaultdict(list)
    for r,x in zip(sel,d): gg[r['game']].append(x)
    gm=np.array([np.mean(z) for z in gg.values()]); se=gm.std(ddof=1)/np.sqrt(len(gm))
    print(f'{lab:<30} n={len(sel):4d}  baseline CRPS {cb.mean():7.4f}  depth-banded {cd.mean():7.4f}  '
          f'({(cd.mean()/cb.mean()-1)*100:+.2f}%)  t={d.mean()/se:+.2f} over {len(gm)} games')

# ---- PIT on the 5-game prospective set
print('\n=== PIT, 5-game prospective set (randomised PIT, 10 bins) ===')
pr=pickle.load(open('/tmp/ws08_rows.pkl','rb'))
def pit(d,y):
    d=np.asarray(d,float); return float(np.mean(d<y))+RNG.random()*float(np.mean(d==y))
for nm,kd,ka in (('targets','T','aT'),('receptions','R','aR'),
                 ('rec_yds','Y','aY'),('rec_td','D','aD')):
    p=np.array([pit(r[kd],r[ka]) for r in pr])
    h,_=np.histogram(p,bins=10,range=(0,1))
    exp=len(p)/10
    chi=float(((h-exp)**2/exp).sum())
    print(f'{nm:<12} n={len(p)} bins={list(h)} chi2(9)={chi:.2f} '
          f'mean={p.mean():.3f} (0.5 nominal)  KS-ish max|F-U|={np.max(np.abs(np.sort(p)-np.arange(1,len(p)+1)/len(p))):.3f}')
    print(f'             NOTE: 132 rows are 5 clusters; chi2 assumes independence and OVERSTATES precision.')
