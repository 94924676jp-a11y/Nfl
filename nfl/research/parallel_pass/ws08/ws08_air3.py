"""WS08 part 5: INCREMENTAL value of depth features over the prior-V feature."""
from __future__ import annotations
import pickle, collections, numpy as np
rows = pickle.load(open('/tmp/ws08_hist.pkl','rb'))
K = 4.0
fit=[r for r in rows if r['season']<=2023 and r['R']>0]
ev =[r for r in rows if r['season']==2024 and r['R']>0]
LV=float(np.mean([r['V'] for r in fit]))
LAYt=float(np.mean([r['aDOTt'] for r in fit if r['aDOTt'] is not None]))
LAYc=float(np.mean([r['aDOTc'] for r in fit]))
LYAC=float(np.mean([r['YACc'] for r in fit]))

def F(r):
    w=r['h_n']/(r['h_n']+K)
    g=lambda v,L: w*(v if v is not None else L)+(1-w)*L
    return dict(pv=g(r['p_V'],LV), pat=g(r['p_aDOTt'],LAYt),
                pac=g(r['p_aDOTc'],LAYc), pyac=g(r['p_YACc'],LYAC))

SETS={
 'M1  prior V only':                 ['pv'],
 'M2  prior V + aDOT/target':        ['pv','pat'],
 'M3  prior V + aDOT/catch':         ['pv','pac'],
 'M4  prior V + aDOT/catch + YAC':   ['pv','pac','pyac'],
 'M5  aDOT/catch + YAC (no prior V)':['pac','pyac'],
}
Vf=np.array([r['V'] for r in fit]); wf=np.array([r['R'] for r in fit],float)
Ve=np.array([r['V'] for r in ev]);  Re=np.array([r['R'] for r in ev],float)
Ff=[F(r) for r in fit]; Fe=[F(r) for r in ev]
res={}
for name,ks in SETS.items():
    Xf=np.array([[1.0]+[f[k] for k in ks] for f in Ff])
    Xe=np.array([[1.0]+[f[k] for k in ks] for f in Fe])
    b=np.linalg.lstsq(Xf*np.sqrt(wf)[:,None], Vf*np.sqrt(wf), rcond=None)[0]
    p=Xe@b
    err=Re*(p-Ve)
    res[name]=dict(mae=float(np.abs(err).mean()), rmse=float(np.sqrt((err**2).mean())),
                   bias=float(err.mean()), err=np.abs(err), beta=np.round(b,4))
b0=res['M1  prior V only']
print('=== conditional-on-receptions Y error, 2024 holdout, fit 2021-2023 ===')
for n,v in res.items():
    print(f"{n:<36} MAE={v['mae']:7.3f} ({v['mae']/b0['mae']*100:6.2f}% of M1)  "
          f"RMSE={v['rmse']:7.3f} ({v['rmse']/b0['rmse']*100:6.2f}%)  beta={v['beta']}")

g=collections.defaultdict(list)
for n,v in res.items():
    if n==list(res)[0]: continue
    d=v['err']-b0['err']
    gg=collections.defaultdict(list)
    for r,x in zip(ev,d): gg[r['game']].append(x)
    gm=np.array([np.mean(z) for z in gg.values()])
    se=gm.std(ddof=1)/np.sqrt(len(gm))
    print(f"{n:<36} vs M1: {d.mean():+.4f} yd/player-game, game-clustered SE {se:.4f}, "
          f"t={d.mean()/se:+.2f}, 95% CI [{d.mean()-1.96*se:+.3f}, {d.mean()+1.96*se:+.3f}]")

# ---- how large is the irreducible part? decompose Var(V | R) on the holdout
print()
print('=== where the conditional residual lives (2024, R>0) ===')
A=np.array([r['aDOTc'] for r in ev]); Y=np.array([r['YACc'] for r in ev])
print(f'Var(V)={Ve.var():.2f}; Var(aDOT/catch)={A.var():.2f}; Var(YAC/catch)={Y.var():.2f}; '
      f'corr(aDOT,YAC)={np.corrcoef(A,Y)[0,1]:+.3f}')
pac=np.array([f['pac'] for f in Fe]); pyac=np.array([f['pyac'] for f in Fe])
print(f'r(prior aDOT/catch, realised aDOT/catch) = {np.corrcoef(pac,A)[0,1]:+.3f}')
print(f'r(prior YAC/catch,  realised YAC/catch)  = {np.corrcoef(pyac,Y)[0,1]:+.3f}')
pv=np.array([f['pv'] for f in Fe])
print(f'r(prior V,          realised V)          = {np.corrcoef(pv,Ve)[0,1]:+.3f}')
# partial: does prior aDOT add to prior V for predicting V?
X=np.column_stack([np.ones(len(ev)),pv]); b=np.linalg.lstsq(X,Ve,rcond=None)[0]
rv=Ve-X@b; X2=np.column_stack([np.ones(len(ev)),pv]); b2=np.linalg.lstsq(X2,pac,rcond=None)[0]
ra=pac-X2@b2
print(f'PARTIAL r(prior aDOT/catch, V | prior V) = {np.corrcoef(ra,rv)[0,1]:+.3f}  '
      f'(partial r2 = {np.corrcoef(ra,rv)[0,1]**2:.4f})')
