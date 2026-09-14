"""WS08 part 2: decomposition of receiving-yard error."""
from __future__ import annotations
import pickle, collections, json
import numpy as np
rows = pickle.load(open('/tmp/ws08_rows.pkl', 'rb'))
RNG = np.random.default_rng(20260914)

def crps(d, y):
    d = np.sort(np.asarray(d, float)); n = d.size
    i = np.arange(1, n + 1)
    return float(np.mean(np.abs(d - y))) - float(np.sum((2*i-n-1)*d))/(n*n)

def cover(d, y, lvl):
    a = (1-lvl)/2*100; lo, hi = np.percentile(d, [a, 100-a]); return int(lo<=y<=hi)

def pit(d, y):
    d = np.asarray(d, float)
    return float(np.mean(d < y)) + RNG.random()*float(np.mean(d == y))

# ---------------------------------------------------------------- (A) exact additive mean decomposition
print('=== (A) EXACT ADDITIVE MEAN DECOMPOSITION OF rec_yds ERROR ===')
print('Y_pred_mean - Y_actual  ==  dT + dC + dV,  where')
print('  dT = (That - Ta) * chat * vhat')
print('  dC = Ta * (chat - ca) * vhat')
print('  dV = Ra * (vhat - va)')
comp = []
for r in rows:
    That = r['T'].mean(); ER = r['R'].mean(); EY = r['Y'].mean()
    chat = ER/That if That > 0 else 0.0
    vhat = EY/ER if ER > 0 else 0.0
    Ta, Ra, Ya = r['aT'], r['aR'], r['aY']
    ca = Ra/Ta if Ta > 0 else 0.0
    va = Ya/Ra if Ra > 0 else 0.0
    dT = (That - Ta)*chat*vhat
    dC = Ta*(chat - ca)*vhat
    dV = Ra*(vhat - va)
    comp.append(dict(r=r, dT=dT, dC=dC, dV=dV, tot=EY-Ya,
                     chat=chat, vhat=vhat, ca=ca, va=va, That=That))
resid = max(abs(c['dT']+c['dC']+c['dV']-c['tot']) for c in comp)
print(f'max additive residual = {resid:.2e} (identity check)')

def dec(cs, tag):
    dT = np.array([c['dT'] for c in cs]); dC = np.array([c['dC'] for c in cs])
    dV = np.array([c['dV'] for c in cs]); tot = np.array([c['tot'] for c in cs])
    print(f"{tag:<22} n={len(cs):3d} | signed bias  dT={dT.mean():+7.2f} dC={dC.mean():+7.2f} "
          f"dV={dV.mean():+7.2f} tot={tot.mean():+7.2f} | mean|.|  "
          f"dT={np.abs(dT).mean():6.2f} dC={np.abs(dC).mean():6.2f} dV={np.abs(dV).mean():6.2f} "
          f"tot={np.abs(tot).mean():6.2f} | share of mean|.| "
          f"T={np.abs(dT).mean()/(np.abs(dT).mean()+np.abs(dC).mean()+np.abs(dV).mean())*100:.1f}% "
          f"C={np.abs(dC).mean()/(np.abs(dT).mean()+np.abs(dC).mean()+np.abs(dV).mean())*100:.1f}% "
          f"V={np.abs(dV).mean()/(np.abs(dT).mean()+np.abs(dC).mean()+np.abs(dV).mean())*100:.1f}%")

dec(comp, 'ALL')
for p in ('WR','TE','RB'):
    dec([c for c in comp if c['r']['pos']==p], f'pos={p}')
for k in (1,2,3,4):
    sel=[c for c in comp if c['r']['rank']==k]
    if sel: dec(sel, f'fcst target rank {k}')
sel=[c for c in comp if c['r']['rank']>=5]
dec(sel, 'fcst target rank 5+')
hi=[c for c in comp if c['That']>=2.36]; lo=[c for c in comp if c['That']<2.36]
dec(hi,'high vol (That>=2.36)'); dec(lo,'low vol (That<2.36)')

# ---------------------------------------------------------------- (B) oracle arms on the model's own draws
print()
print('=== (B) ORACLE ARMS FROM THE MODEL OWN JOINT DRAWS ===')
print('In RC1/production, Y depends on the draw ONLY through R (per-catch iid resample),')
print('so Y | R=Ra is exactly the "targets AND receptions known" conditional.')

def per_catch_pool(r, nmin=40):
    """Exact per-catch sample: draws with R==1 have Y = one pick."""
    m = r['R'] == 1
    return r['Y'][m] if m.sum() >= nmin else None

arm_base, arm_T, arm_R = [], [], []
n_exactT, n_exactR, n_recon, n_fail = 0, 0, 0, 0
for r in rows:
    Ta, Ra, Ya = r['aT'], r['aR'], r['aY']
    arm_base.append((r['Y'], Ya, r))
    # T-oracle: draws where simulated targets == realised targets
    m = r['T'] == Ta
    if m.sum() >= 30:
        arm_T.append((r['Y'][m], Ya, r)); n_exactT += 1
    else:
        arm_T.append((None, Ya, r))
    # R-oracle
    if Ra == 0:
        arm_R.append((np.zeros(200), Ya, r)); n_exactR += 1
        continue
    m = r['R'] == Ra
    if m.sum() >= 30:
        arm_R.append((r['Y'][m], Ya, r)); n_exactR += 1
    else:
        pool = per_catch_pool(r)
        if pool is not None:
            draws = pool[RNG.integers(0, len(pool), (2000, int(Ra)))].sum(1)
            arm_R.append((draws, Ya, r)); n_recon += 1
        else:
            arm_R.append((None, Ya, r)); n_fail += 1
print(f'T-oracle exact-match rows: {n_exactT}/{len(rows)}')
print(f'R-oracle exact-match rows: {n_exactR}/{len(rows)}; iid-reconstructed: {n_recon}; unavailable: {n_fail}')

# validate reconstruction against exact match where both exist
vals = []
for r in rows:
    Ra = r['aR']
    if Ra <= 0: continue
    m = r['R'] == Ra
    pool = per_catch_pool(r)
    if m.sum() >= 100 and pool is not None:
        ex = r['Y'][m]
        rc = pool[RNG.integers(0, len(pool), (4000, int(Ra)))].sum(1)
        vals.append((abs(ex.mean()-rc.mean()), abs(np.median(ex)-np.median(rc))))
if vals:
    v = np.array(vals)
    print(f'reconstruction check on {len(vals)} rows: mean |Dmean| {v[:,0].mean():.2f} yd, '
          f'mean |Dmedian| {v[:,1].mean():.2f} yd')

def armstats(arm, tag):
    keep = [(d, y, r) for d, y, r in arm if d is not None]
    cr = np.array([crps(d, y) for d, y, r in keep])
    mu = np.array([d.mean() for d, y, r in keep])
    ya = np.array([y for d, y, r in keep])
    cov = {lv: np.mean([cover(d, y, lv) for d, y, r in keep]) for lv in (0.5,0.8,0.9,0.95)}
    print(f'{tag:<34} n={len(keep):3d} CRPS={cr.mean():6.3f} MAE={np.abs(mu-ya).mean():6.2f} '
          f'RMSE={np.sqrt(((mu-ya)**2).mean()):6.2f} bias={(mu-ya).mean():+6.2f} '
          f'r={np.corrcoef(mu,ya)[0,1]:+.3f} cov={cov[0.5]:.2f}/{cov[0.8]:.2f}/{cov[0.9]:.2f}/{cov[0.95]:.2f}')
    return {'n': len(keep), 'crps': float(cr.mean()), 'mae': float(np.abs(mu-ya).mean()),
            'rmse': float(np.sqrt(((mu-ya)**2).mean())), 'bias': float((mu-ya).mean()),
            'r': float(np.corrcoef(mu,ya)[0,1]),
            'cov': {str(k): float(v) for k, v in cov.items()},
            'rows': [r['pid'] for d, y, r in keep]}

# restrict all arms to the common set so the comparison is like for like
okT = {i for i, (d, y, r) in enumerate(arm_T) if d is not None}
okR = {i for i, (d, y, r) in enumerate(arm_R) if d is not None}
common = sorted(okT & okR)
print(f'\ncommon comparable rows: {len(common)} of {len(rows)}')
res = {}
for tag, arm in (('BASELINE (nothing known)', arm_base),
                 ('T-oracle (targets known)', arm_T),
                 ('T+C-oracle (receptions known)', arm_R)):
    res[tag] = armstats([arm[i] for i in common], tag)
b, t, rr = res['BASELINE (nothing known)']['crps'], res['T-oracle (targets known)']['crps'], res['T+C-oracle (receptions known)']['crps']
print(f'\nCRPS surviving after conditioning on realised TARGETS     : {t/b*100:.1f}% of baseline')
print(f'CRPS surviving after conditioning on realised RECEPTIONS  : {rr/b*100:.1f}% of baseline')
mb = res['BASELINE (nothing known)']['mae']; mr = res['T+C-oracle (receptions known)']['mae']
mt = res['T-oracle (targets known)']['mae']
print(f'MAE  surviving after targets  : {mt/mb*100:.1f}%   after receptions: {mr/mb*100:.1f}%')

# by position on the conditioned arm
print('\n--- residual after conditioning on receptions, by position ---')
for p in ('WR','TE','RB'):
    idx = [i for i in common if rows[i]['pos']==p]
    if len(idx) < 5: continue
    bb = armstats([arm_base[i] for i in idx], f'  {p} baseline')
    cc = armstats([arm_R[i] for i in idx], f'  {p} receptions-known')
    print(f'  -> {p}: {cc["crps"]/bb["crps"]*100:.1f}% of CRPS survives')
print('\n--- by forecast target rank ---')
for lab, f in (('rank1', lambda r: r['rank']==1), ('rank2', lambda r: r['rank']==2),
               ('rank3-4', lambda r: r['rank'] in (3,4)), ('rank5+', lambda r: r['rank']>=5)):
    idx=[i for i in common if f(rows[i])]
    if len(idx)<5: continue
    bb=armstats([arm_base[i] for i in idx], f'  {lab} baseline')
    cc=armstats([arm_R[i] for i in idx], f'  {lab} receptions-known')
    print(f'  -> {lab}: {cc["crps"]/bb["crps"]*100:.1f}% of CRPS survives')
print('\n--- by forecast volume (mean predicted targets) ---')
for lab, f in (('high >=2.36', lambda r: r['T'].mean()>=2.36),
               ('low  < 2.36', lambda r: r['T'].mean()<2.36)):
    idx=[i for i in common if f(rows[i])]
    bb=armstats([arm_base[i] for i in idx], f'  {lab} baseline')
    cc=armstats([arm_R[i] for i in idx], f'  {lab} receptions-known')
    print(f'  -> {lab}: {cc["crps"]/bb["crps"]*100:.1f}% of CRPS survives')
json.dump(res, open('/tmp/ws08_arms.json','w'), indent=1)
