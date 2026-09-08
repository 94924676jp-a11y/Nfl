"""The single pre-declared cheap-proxy probe.

Specification is fixed in nfl/research/infogap/predeclaration_proxy_probe.md,
committed at f2a73a3 BEFORE this ran. Nothing here may deviate from it.

  control   : [p_ewma1, p_ewma2]
  treatment : control + five prior-only personnel/formation EWMA(hl=2) features
  one ridge, penalty fixed at 1.0, no search, no selection
  same rows, walk-forward 2022-2025, fitted on strictly prior seasons only
  materiality: >= 1% relative pooled MAE
"""
import bisect, collections, json, math, os, pickle, sys
import numpy as np

R = '/home/user/nfl/nfl/research'
for p in (f'{R}/p1s', f'{R}/s2', f'{R}/p4c', f'{R}/p4e', f'{R}/s4'):
    sys.path.insert(0, p)
sys.path.insert(0, '/home/user/nfl/sportsplatform')
import p_lib as L
import p_fit as PF
import p4c_build as CB

S = os.path.dirname(os.path.abspath(__file__))
PROBE = ['pers_3wr', 'pers_2te', 'pers_2rb', 'form_shotgun', 'form_empty']
HL = 2.0

pers = pickle.load(open(f'{S}/personnel.pkl', 'rb'))
print(f'personnel profiles loaded: {len(pers)}')

rows, sub = L.load()
pa = CB.appearance(rows)
L.attach(sub, pa)
print(f'frame: {len(sub)} WR/TE/RB player-games')

# ---- attach prior-only EWMA(hl=2) probe features -------------------------
# Same strictly-earlier-ordinal prefix cut the rest of this project uses:
# player-ordinal pairs can carry two rows (mid-week team change).
hist = collections.defaultdict(list)
hist_ord = collections.defaultdict(list)
n_have = 0
for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
    pid = r['gsis_id']
    k = bisect.bisect_left(hist_ord[pid], r['ord'])
    past = hist[pid][:k]
    for f in PROBE:
        v = [x[f] for x in past if x is not None and x.get(f) is not None]
        r['z_' + f] = L.ewma(v, HL) if v else None
    prof = pers.get((r['season'], r['week'], r['team'], pid))
    if r['appeared'] and prof is not None and prof['n_pass_snaps'] > 0:
        hist[pid].append(prof)
        n_have += 1
    else:
        hist[pid].append({})
    hist_ord[pid].append(r['ord'])
print(f'player-games with an own personnel profile: {n_have}')

# ---- the shared row set --------------------------------------------------
NEED = ['p_ewma1', 'p_ewma2'] + ['z_' + f for f in PROBE]


def ok(r, ev):
    return L.eligible(r, ev) and all(r.get(f) is not None for f in NEED)


CTRL = ['p_ewma1', 'p_ewma2']
TRT = CTRL + ['z_' + f for f in PROBE]


def design(rs, feats):
    return np.array([[float(r[f]) for f in feats] for r in rs], np.float64)


out = {'features': PROBE, 'halflife': HL, 'penalty': 1.0,
       'control': CTRL, 'treatment': TRT, 'by_season': {}}
poolc, poolt, pooly = [], [], []
for ev in L.EVAL:
    tr = [r for r in sub if r['season'] < ev and ok(r, None)]
    te = [r for r in sub if ok(r, ev) and r['season'] == ev]
    y = np.array([r[L.TARGET] for r in tr], np.float64)
    yt = np.array([r[L.TARGET] for r in te], np.float64)
    fc = PF._fit(design(tr, CTRL), y, 1.0)
    ft = PF._fit(design(tr, TRT), y, 1.0)
    pc = np.clip(PF._pred(fc, design(te, CTRL)), 0.0, 1.0)
    pt = np.clip(PF._pred(ft, design(te, TRT)), 0.0, 1.0)
    mc = float(np.mean(np.abs(pc - yt)))
    mt = float(np.mean(np.abs(pt - yt)))
    out['by_season'][ev] = {'n_train': len(tr), 'n_eval': len(te),
                            'mae_control': mc, 'mae_treatment': mt,
                            'rel_pct': 100.0 * (mc - mt) / mc}
    print(f'  {ev}: n_train {len(tr):6d} n_eval {len(te):5d}  '
          f'MAE ctrl {mc:.6f}  trt {mt:.6f}  rel {100*(mc-mt)/mc:+.3f}%')
    poolc.append(pc); poolt.append(pt); pooly.append(yt)

pc = np.concatenate(poolc); pt = np.concatenate(poolt); yy = np.concatenate(pooly)
mc = float(np.mean(np.abs(pc - yy))); mt = float(np.mean(np.abs(pt - yy)))
rel = 100.0 * (mc - mt) / mc
out['pooled'] = {'n': int(len(yy)), 'mae_control': mc, 'mae_treatment': mt,
                 'rel_pct': rel, 'materiality_pct': 1.0,
                 'verdict': ('CONTAINS_INCREMENTAL_SIGNAL' if rel >= 1.0
                             else 'NO_DETECTABLE_INCREMENTAL_SIGNAL')}
print(f'\npooled n {len(yy)}  MAE ctrl {mc:.6f}  trt {mt:.6f}  '
      f'rel {rel:+.4f}%  bar 1.0%  -> {out["pooled"]["verdict"]}')
json.dump(out, open(f'{S}/probe_result.json', 'w'), indent=1)
