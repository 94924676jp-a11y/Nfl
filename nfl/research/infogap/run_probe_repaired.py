"""POST_HOC_REPAIR of the voided probe. Specification fixed in
nfl/research/infogap/addendum_probe_void.md, committed at 90585aa BEFORE this
ran.

  primary   : [ewma1,ewma2]+five probe features  vs  [ewma1,ewma2]+five noise
              columns (seed 20260908). Identical p=7, identical penalty.
  secondary : the original control-vs-treatment contrast with the penalty
              formed as lam*n instead of lam*n/p.
  bar       : >= 1% relative pooled MAE on the PRIMARY.
"""
import bisect, collections, json, os, pickle, sys
import numpy as np
S = os.path.dirname(os.path.abspath(__file__))
R = '/home/user/nfl/nfl/research'
for p in (f'{R}/p1s', f'{R}/s2', f'{R}/p4c', f'{R}/p4e', f'{R}/s4'):
    sys.path.insert(0, p)
sys.path.insert(0, '/home/user/nfl/sportsplatform')
import p_lib as L, p_fit as PF, p4c_build as CB

PROBE = ['pers_3wr', 'pers_2te', 'pers_2rb', 'form_shotgun', 'form_empty']
ZS = ['z_' + f for f in PROBE]
CTRL = ['p_ewma1', 'p_ewma2']
pers = pickle.load(open(f'{S}/personnel.pkl', 'rb'))
rows, sub = L.load(); pa = CB.appearance(rows); L.attach(sub, pa)

hist = collections.defaultdict(list); ho = collections.defaultdict(list)
for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
    pid = r['gsis_id']; k = bisect.bisect_left(ho[pid], r['ord'])
    past = hist[pid][:k]
    for f in PROBE:
        v = [x[f] for x in past if x.get(f) is not None]
        r['z_' + f] = L.ewma(v, 2.0) if v else None
    pf = pers.get((r['season'], r['week'], r['team'], pid))
    hist[pid].append(pf if (r['appeared'] and pf and pf['n_pass_snaps'] > 0) else {})
    ho[pid].append(r['ord'])

NEED = CTRL + ZS
def ok(r, ev): return L.eligible(r, ev) and all(r.get(f) is not None for f in NEED)

rng = np.random.default_rng(20260908)
noise = {}
for r in sub:
    noise[id(r)] = rng.standard_normal(5)

def X(rs, feats, pad_noise=False):
    A = np.array([[float(r[f]) for f in feats] for r in rs], np.float64)
    if pad_noise:
        A = np.hstack([A, np.array([noise[id(r)] for r in rs])])
    return A

def fit_abs(Xm, y, lam):                       # penalty lam*n, width-invariant
    mu, sd = Xm.mean(0), Xm.std(0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    Z = (Xm - mu) / sd
    A = Z.T @ Z + lam * len(Z) * np.eye(Z.shape[1])
    return {'mu': mu, 'sd': sd, 'b': np.linalg.solve(A, Z.T @ (y - y.mean())),
            'y0': float(y.mean())}

def walk(spec_a, spec_b, fitter, tag):
    pa_, pb_, yy, per = [], [], [], {}
    for ev in L.EVAL:
        tr = [r for r in sub if r['season'] < ev and ok(r, None)]
        te = [r for r in sub if ok(r, ev) and r['season'] == ev]
        y = np.array([r[L.TARGET] for r in tr]); yt = np.array([r[L.TARGET] for r in te])
        fa = fitter(X(tr, *spec_a), y, 1.0); fb = fitter(X(tr, *spec_b), y, 1.0)
        qa = np.clip(PF._pred(fa, X(te, *spec_a)), 0, 1)
        qb = np.clip(PF._pred(fb, X(te, *spec_b)), 0, 1)
        ma = float(np.mean(np.abs(qa-yt))); mb = float(np.mean(np.abs(qb-yt)))
        per[ev] = {'n_eval': len(te), 'mae_reference': ma, 'mae_treatment': mb,
                   'rel_pct': 100*(ma-mb)/ma}
        print(f'    {ev}: n {len(te):5d}  ref {ma:.6f}  trt {mb:.6f}  '
              f'rel {100*(ma-mb)/ma:+.4f}%')
        pa_.append(qa); pb_.append(qb); yy.append(yt)
    qa = np.concatenate(pa_); qb = np.concatenate(pb_); yy = np.concatenate(yy)
    ma = float(np.mean(np.abs(qa-yy))); mb = float(np.mean(np.abs(qb-yy)))
    rel = 100*(ma-mb)/ma
    print(f'  {tag} pooled: n {len(yy)}  ref {ma:.6f}  trt {mb:.6f}  rel {rel:+.4f}%')
    return {'by_season': per, 'pooled': {'n': int(len(yy)), 'mae_reference': ma,
                                         'mae_treatment': mb, 'rel_pct': rel}}

out = {'label': 'POST_HOC_REPAIR', 'declared_in': 'addendum_probe_void.md',
       'declared_at_commit': '90585aa', 'materiality_pct': 1.0}
print('PRIMARY  column-count matched, p=7 both sides, penalty 1.0*n/7:')
out['primary'] = walk((CTRL, True), (CTRL + ZS, False), PF._fit, 'PRIMARY')
print('SECONDARY  penalty lam*n, width-invariant, p=2 vs p=7:')
out['secondary'] = walk((CTRL, False), (CTRL + ZS, False), fit_abs, 'SECONDARY')

rel = out['primary']['pooled']['rel_pct']
out['verdict'] = ('CONTAINS_INCREMENTAL_SIGNAL' if rel >= 1.0
                  else 'NO_DETECTABLE_INCREMENTAL_SIGNAL')
sec = out['secondary']['pooled']['rel_pct']
out['secondary_agrees'] = (sec >= 1.0) == (rel >= 1.0)
print(f"\nPRIMARY governs: {rel:+.4f}% vs 1.0% bar -> {out['verdict']}")
print(f"SECONDARY {sec:+.4f}%  agrees: {out['secondary_agrees']}")
json.dump(out, open(f'{S}/probe_repaired.json', 'w'), indent=1)
