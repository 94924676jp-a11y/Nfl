"""WS08 part 4: FORWARD-CHAINED test -- does depth information reduce the
conditional-on-receptions receiving-yard error? Fit 2021-2023, evaluate 2024."""
from __future__ import annotations
import pickle, numpy as np
rows = pickle.load(open('/tmp/ws08_hist.pkl', 'rb'))
K = 4.0   # inherited from RC1 (Stage-2 history-cohort boundary). Not searched.

fit = [r for r in rows if r['season'] <= 2023 and r['R'] > 0]
ev  = [r for r in rows if r['season'] == 2024 and r['R'] > 0]
LV   = float(np.mean([r['V'] for r in fit]))
LAY  = float(np.mean([r['aDOTt'] for r in fit if r['aDOTt'] is not None]))
LYAC = float(np.mean([r['YACc'] for r in fit]))
print(f'league pool from 2021-2023: V={LV:.3f}  aDOT/target={LAY:.3f}  YAC/catch={LYAC:.3f}')
print(f'fit rows {len(fit)}   eval rows (2024, R>0) {len(ev)}')

def w_(r): return r['h_n'] / (r['h_n'] + K)

def feats(r):
    w = w_(r)
    pv  = r['p_V']     if r['p_V']     is not None else LV
    pa  = r['p_aDOTt'] if r['p_aDOTt'] is not None else LAY
    py  = r['p_YACc']  if r['p_YACc']  is not None else LYAC
    return (w*pv + (1-w)*LV, w*pa + (1-w)*LAY, w*py + (1-w)*LYAC)

# P3: OLS on 2021-2023, applied to 2024. Weighted by receptions (the
# denominator the error is actually measured on).
Xf = np.array([[1.0, *feats(r)] for r in fit]); yf = np.array([r['V'] for r in fit])
wf = np.array([r['R'] for r in fit], float)
W = np.diag(wf) if False else None
beta = np.linalg.lstsq(Xf * np.sqrt(wf)[:, None], yf * np.sqrt(wf), rcond=None)[0]
print('OLS beta [const, shrunk_prior_V, shrunk_prior_aDOT_t, shrunk_prior_YAC]:',
      np.round(beta, 4))

Xe = np.array([[1.0, *feats(r)] for r in ev])
Ve = np.array([r['V'] for r in ev]); Re = np.array([r['R'] for r in ev], float)
Ye = np.array([r['Y'] for r in ev])

P = {
 'P0 league constant V':            np.full(len(ev), LV),
 'P1 RC1-like shrunk own V':        Xe[:, 1],
 'P2 shrunk aDOT + shrunk YAC':     Xe[:, 2] + Xe[:, 3],
 'P3 OLS(prior V, aDOT, YAC)':      Xe @ beta,
 'ORACLE realised V':               Ve,
}
print('\n=== conditional on REALISED receptions: Y_hat = R * V_hat, 2024 holdout ===')
base = None
for k, v in P.items():
    err = Re * (v - Ve)
    mae = np.abs(err).mean(); rmse = float(np.sqrt((err**2).mean())); bias = err.mean()
    if base is None: base = mae
    print(f'{k:<32} MAE={mae:7.3f}  RMSE={rmse:7.3f}  bias={bias:+7.3f}  '
          f'vs P1 {"" if k.startswith("P1") else f"{(mae/mae_p1-1)*100:+.2f}%" if "mae_p1" in dir() else ""}')
    if k.startswith('P1'): mae_p1, rmse_p1 = mae, rmse
print()
for k, v in P.items():
    err = Re * (v - Ve); mae = np.abs(err).mean(); rmse = float(np.sqrt((err**2).mean()))
    print(f'{k:<32} MAE {mae/mae_p1*100:6.2f}% of P1   RMSE {rmse/rmse_p1*100:6.2f}% of P1')

# how much of the P1 residual does the oracle remove -> the ceiling
o = np.abs(Re*(Ve-Ve)).mean()
print(f'\nORACLE V removes 100% of the conditional residual by construction.')
print(f'P2 (depth-informed, no fitting) removes '
      f'{(1-np.abs(Re*(P["P2 shrunk aDOT + shrunk YAC"]-Ve)).mean()/mae_p1)*100:.2f}% of it.')
print(f'P3 (OLS, forward-chained)      removes '
      f'{(1-np.abs(Re*(P["P3 OLS(prior V, aDOT, YAC)"]-Ve)).mean()/mae_p1)*100:.2f}% of it.')

# cluster by game for the P3-vs-P1 difference
import collections
d = np.abs(Re*(P['P3 OLS(prior V, aDOT, YAC)']-Ve)) - np.abs(Re*(P['P1 RC1-like shrunk own V']-Ve))
g = collections.defaultdict(list)
for r, x in zip(ev, d): g[r['game']].append(x)
gm = np.array([np.mean(v) for v in g.values()]); ng = len(gm)
se = gm.std(ddof=1)/np.sqrt(ng)
print(f'\nP3 - P1 paired MAE difference = {d.mean():+.4f} yd/player-game; '
      f'game-clustered SE {se:.4f} over {ng} games; t = {d.mean()/se:+.2f}')

# same test restricted to volume receivers
for thr in (3, 5):
    m = Re >= thr
    a = np.abs(Re[m]*(P['P1 RC1-like shrunk own V'][m]-Ve[m])).mean()
    b = np.abs(Re[m]*(P['P3 OLS(prior V, aDOT, YAC)'][m]-Ve[m])).mean()
    c = np.abs(Re[m]*(P['P2 shrunk aDOT + shrunk YAC'][m]-Ve[m])).mean()
    print(f'R>={thr} (n={m.sum()}): P1 MAE {a:.2f}  P2 {c:.2f} ({(b/a-1)*0+((c/a-1)*100):+.2f}%)  '
          f'P3 {b:.2f} ({(b/a-1)*100:+.2f}%)')
