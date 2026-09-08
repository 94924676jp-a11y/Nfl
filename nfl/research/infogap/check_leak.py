"""Chronology masking + placebo for the probe features. Diagnostic only:
no model is selected, no specification is altered."""
import bisect, collections, json, os, pickle, random, sys
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
rows, sub = L.load()
pa = CB.appearance(rows)
L.attach(sub, pa)


def build(frame, profiles):
    hist = collections.defaultdict(list)
    hist_ord = collections.defaultdict(list)
    out = {}
    for r in sorted(frame, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        k = bisect.bisect_left(hist_ord[pid], r['ord'])
        past = hist[pid][:k]
        d = {}
        for f in PROBE:
            v = [x[f] for x in past if x.get(f) is not None]
            d['z_' + f] = L.ewma(v, HL) if v else None
        out[id(r)] = d
        prof = profiles.get((r['season'], r['week'], r['team'], pid))
        hist[pid].append(prof if (r['appeared'] and prof
                                  and prof['n_pass_snaps'] > 0) else {})
        hist_ord[pid].append(r['ord'])
    return out


full = build(sub, pers)

# ---- 1. chronology masking: truncate the panel at four probe ordinals ----
ords = sorted({r['ord'] for r in sub})
report = {'masking': {}}
for K in (ords[len(ords)//4], ords[len(ords)//2], ords[3*len(ords)//4], ords[-3]):
    keep = [r for r in sub if r['ord'] < K]
    m = build(keep, pers)
    bad = sum(1 for r in keep
              if any(m[id(r)]['z_'+f] != full[id(r)]['z_'+f] for f in PROBE))
    report['masking'][K] = {'n_rows_before_cut': len(keep), 'n_changed': bad}
    print(f'  mask at ord {K}: {len(keep)} rows before cut, {bad} changed')

# ---- 2. placebo: permute profiles across players within each team-game ---
random.seed(20260908)
by_g = collections.defaultdict(list)
for k in pers:
    by_g[(k[0], k[1], k[2])].append(k)
shuf = {}
for g, ks in by_g.items():
    vs = [pers[k] for k in ks]
    random.shuffle(vs)
    for k, v in zip(ks, vs):
        shuf[k] = v
plac = build(sub, shuf)

CTRL = ['p_ewma1', 'p_ewma2']
ZS = ['z_' + f for f in PROBE]


def run(feat_map, tag):
    def ok(r, ev):
        d = feat_map[id(r)]
        return (L.eligible(r, ev) and r.get('p_ewma1') is not None
                and r.get('p_ewma2') is not None
                and all(d[z] is not None for z in ZS))

    def X(rs, feats):
        return np.array([[float(r[f]) if f in r else float(feat_map[id(r)][f])
                          for f in feats] for r in rs], np.float64)
    pc, pt, yy = [], [], []
    for ev in L.EVAL:
        tr = [r for r in sub if r['season'] < ev and ok(r, None)]
        te = [r for r in sub if ok(r, ev) and r['season'] == ev]
        y = np.array([r[L.TARGET] for r in tr]); yt = np.array([r[L.TARGET] for r in te])
        fc = PF._fit(X(tr, CTRL), y, 1.0); ft = PF._fit(X(tr, CTRL+ZS), y, 1.0)
        pc.append(np.clip(PF._pred(fc, X(te, CTRL)), 0, 1))
        pt.append(np.clip(PF._pred(ft, X(te, CTRL+ZS)), 0, 1))
        yy.append(yt)
    pc = np.concatenate(pc); pt = np.concatenate(pt); yy = np.concatenate(yy)
    a = float(np.mean(np.abs(pc-yy))); b = float(np.mean(np.abs(pt-yy)))
    rel = 100.0*(a-b)/a
    print(f'  {tag}: n {len(yy)}  ctrl {a:.6f}  trt {b:.6f}  rel {rel:+.4f}%')
    return {'n': int(len(yy)), 'mae_control': a, 'mae_treatment': b, 'rel_pct': rel}


print('\nplacebo (profiles permuted among players within the same team-game):')
report['placebo'] = run(plac, 'placebo')
print('real (for identity with the probe run):')
report['real'] = run(full, 'real')
json.dump(report, open(f'{S}/probe_leakcheck.json', 'w'), indent=1)
