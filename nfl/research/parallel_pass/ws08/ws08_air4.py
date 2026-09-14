"""WS08 part 6: (a) does depth help the CATCH-RATE channel?
(b) does a depth-stratified per-catch yardage DISTRIBUTION improve CRPS|R?"""
from __future__ import annotations
import pickle, collections, numpy as np
rows=pickle.load(open('/tmp/ws08_hist.pkl','rb')); K=4.0
RNG=np.random.default_rng(20260914)

# ---------- rebuild strictly-prior per-catch yardage lists + prior catch rate
hist=collections.defaultdict(lambda: dict(n=0,T=0,R=0,Y=0.0,AYt=0.0,catches=[]))
for r in rows:
    h=hist[r['pid']]
    r['ph_n']=h['n']; r['ph_T']=h['T']; r['ph_R']=h['R']
    r['ph_c']=(h['R']/h['T']) if h['T'] else None
    r['ph_at']=(h['AYt']/h['T']) if h['T'] else None
    r['ph_catches']=list(h['catches'])
    h['n']+=1; h['T']+=r['T']; h['R']+=r['R']; h['Y']+=r['Y']; h['AYt']+=r['AYt']
    h['catches'].extend(r['catches'])

fit=[r for r in rows if r['season']<=2023]
ev =[r for r in rows if r['season']==2024]
Lc=sum(r['R'] for r in fit)/sum(r['T'] for r in fit)
Lat=float(np.mean([r['aDOTt'] for r in fit if r['aDOTt'] is not None]))

# ---------- (a) CATCH RATE ------------------------------------------------
print('=== (a) does prior aDOT add to prior catch rate for predicting C? ===')
sel=[r for r in ev if r['T']>0 and r['ph_T'] and r['ph_n']>=4]
w=np.array([r['ph_n']/(r['ph_n']+K) for r in sel])
pc=w*np.array([r['ph_c'] for r in sel])+(1-w)*Lc
pa=w*np.array([r['ph_at'] for r in sel])+(1-w)*Lat
C=np.array([r['R']/r['T'] for r in sel]); T=np.array([r['T'] for r in sel],float)
print(f'n={len(sel)} eval player-games with >=1 target and >=4 prior games')
print(f'r(shrunk prior catch rate, realised C) = {np.corrcoef(pc,C)[0,1]:+.3f}')
print(f'r(shrunk prior aDOT/target, realised C)= {np.corrcoef(pa,C)[0,1]:+.3f}')
Xf=[];yf=[];wf=[]
for r in fit:
    if r['T']<=0 or not r['ph_T'] or r['ph_n']<4: continue
    ww=r['ph_n']/(r['ph_n']+K)
    Xf.append([1.0, ww*r['ph_c']+(1-ww)*Lc, ww*r['ph_at']+(1-ww)*Lat])
    yf.append(r['R']/r['T']); wf.append(r['T'])
Xf=np.array(Xf);yf=np.array(yf);wf=np.array(wf,float)
for ks,lab in (([0,1],'C1 prior catch rate only'),([0,1,2],'C2 + prior aDOT/target')):
    b=np.linalg.lstsq(Xf[:,ks]*np.sqrt(wf)[:,None], yf*np.sqrt(wf), rcond=None)[0]
    Xe=np.column_stack([np.ones(len(sel)),pc,pa])[:,ks]
    p=np.clip(Xe@b,0,1)
    e=T*np.abs(p-C)           # error in RECEPTIONS, the quantity that matters
    print(f'{lab:<30} MAE_receptions={e.mean():.4f}  beta={np.round(b,4)}')
    if ks==[0,1]: e1=e
    else:
        d=e-e1; gg=collections.defaultdict(list)
        for r,x in zip(sel,d): gg[r['game']].append(x)
        gm=np.array([np.mean(z) for z in gg.values()]); se=gm.std(ddof=1)/np.sqrt(len(gm))
        print(f'   C2-C1 = {d.mean():+.4f} receptions/player-game, game-clustered SE {se:.4f}, '
              f't={d.mean()/se:+.2f} over {len(gm)} games')

# ---------- (b) DEPTH-STRATIFIED PER-CATCH YARDAGE POOL --------------------
print('\n=== (b) depth-stratified per-catch yardage pool: CRPS of Y | realised R ===')
pool_all=np.array([y for r in fit for y in r['catches']],float)
# terciles of prior aDOT/target, cut on the FIT seasons only
at=[r['ph_at'] for r in fit if r['ph_at'] is not None and r['ph_n']>=4]
q1,q2=np.percentile(at,[33.33,66.67])
print(f'aDOT/target terciles from 2021-2023: <{q1:.2f} | {q1:.2f}-{q2:.2f} | >{q2:.2f}')
band=lambda a: 0 if a is None else (0 if a<q1 else (1 if a<q2 else 2))
pool_b={k:[] for k in (0,1,2)}
for r in fit:
    if r['ph_n']>=4 and r['ph_at'] is not None:
        pool_b[band(r['ph_at'])].extend(r['catches'])
for k in pool_b:
    pool_b[k]=np.array(pool_b[k],float)
    print(f'  band {k}: {len(pool_b[k])} catches, mean {pool_b[k].mean():.2f}, '
          f'P(gain>25) {np.mean(pool_b[k]>25):.4f}')
print(f'  pooled : {len(pool_all)} catches, mean {pool_all.mean():.2f}, '
      f'P(gain>25) {np.mean(pool_all>25):.4f}')

def crps(d,y):
    d=np.sort(np.asarray(d,float)); n=d.size; i=np.arange(1,n+1)
    return float(np.mean(np.abs(d-y)))-float(np.sum((2*i-n-1)*d))/(n*n)

M=1500
sel2=[r for r in ev if r['R']>0 and r['ph_n']>=4 and r['ph_at'] is not None]
cb,cd=[],[]
for r in sel2:
    ww=r['ph_n']/(r['ph_n']+K)
    own=np.asarray(r['ph_catches'],float); R=int(r['R'])
    use=RNG.random((M,R))<ww if len(own) else np.zeros((M,R),bool)
    oi=own[RNG.integers(0,max(len(own),1),(M,R))] if len(own) else np.zeros((M,R))
    pb=pool_b[band(r['ph_at'])]
    base=np.where(use,oi,pool_all[RNG.integers(0,len(pool_all),(M,R))]).sum(1)
    dep =np.where(use,oi,pb[RNG.integers(0,len(pb),(M,R))]).sum(1)
    cb.append(crps(base,r['Y'])); cd.append(crps(dep,r['Y']))
cb=np.array(cb); cd=np.array(cd)
print(f'\nn={len(sel2)}  CRPS baseline pool {cb.mean():.4f}  depth-banded pool {cd.mean():.4f}  '
      f'({(cd.mean()/cb.mean()-1)*100:+.2f}%)')
d=cd-cb; gg=collections.defaultdict(list)
for r,x in zip(sel2,d): gg[r['game']].append(x)
gm=np.array([np.mean(z) for z in gg.values()]); se=gm.std(ddof=1)/np.sqrt(len(gm))
print(f'difference {d.mean():+.4f} yd CRPS/player-game, game-clustered SE {se:.4f}, '
      f't={d.mean()/se:+.2f} over {len(gm)} games, 95% CI [{d.mean()-1.96*se:+.4f}, {d.mean()+1.96*se:+.4f}]')
# high-volume subset
for thr in (3,5):
    m=np.array([r['R']>=thr for r in sel2])
    print(f'  R>={thr} (n={m.sum()}): baseline {cb[m].mean():.3f} depth {cd[m].mean():.3f} '
          f'({(cd[m].mean()/cb[m].mean()-1)*100:+.2f}%)')
