"""Second diagnostic: how much did the within-team-game permutation actually
move the feature values, and does a GLOBAL permutation also reproduce the gain?"""
import bisect, collections, json, os, pickle, random, sys
import numpy as np

R = '/home/user/nfl/nfl/research'
for p in (f'{R}/p1s', f'{R}/s2', f'{R}/p4c', f'{R}/p4e', f'{R}/s4'):
    sys.path.insert(0, p)
sys.path.insert(0, '/home/user/nfl/sportsplatform')
import p_lib as L, p_fit as PF, p4c_build as CB

S = os.path.dirname(os.path.abspath(__file__))
PROBE = ['pers_3wr', 'pers_2te', 'pers_2rb', 'form_shotgun', 'form_empty']
ZS = ['z_' + f for f in PROBE]
CTRL = ['p_ewma1', 'p_ewma2']
pers = pickle.load(open(f'{S}/personnel.pkl', 'rb'))
rows, sub = L.load(); pa = CB.appearance(rows); L.attach(sub, pa)


def build(profiles):
    hist = collections.defaultdict(list); ho = collections.defaultdict(list); out = {}
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']; k = bisect.bisect_left(ho[pid], r['ord'])
        past = hist[pid][:k]
        out[id(r)] = {'z_'+f: (L.ewma([x[f] for x in past if x.get(f) is not None], 2.0)
                               if any(x.get(f) is not None for x in past) else None)
                      for f in PROBE}
        p_ = profiles.get((r['season'], r['week'], r['team'], pid))
        hist[pid].append(p_ if (r['appeared'] and p_ and p_['n_pass_snaps'] > 0) else {})
        ho[pid].append(r['ord'])
    return out


def permute(groupkey, seed):
    random.seed(seed)
    g = collections.defaultdict(list)
    for k in pers:
        g[groupkey(k)].append(k)
    out = {}
    for _gk, ks in g.items():
        vs = [pers[k] for k in ks]; random.shuffle(vs)
        out.update(dict(zip(ks, vs)))
    return out


def run(fm, tag):
    def ok(r, ev):
        d = fm[id(r)]
        return (L.eligible(r, ev) and r.get('p_ewma1') is not None
                and r.get('p_ewma2') is not None and all(d[z] is not None for z in ZS))
    def X(rs, fs):
        return np.array([[float(r[f]) if f in r else float(fm[id(r)][f]) for f in fs]
                         for r in rs], np.float64)
    pc, pt, yy = [], [], []
    for ev in L.EVAL:
        tr = [r for r in sub if r['season'] < ev and ok(r, None)]
        te = [r for r in sub if ok(r, ev) and r['season'] == ev]
        y = np.array([r[L.TARGET] for r in tr]); yt = np.array([r[L.TARGET] for r in te])
        fc = PF._fit(X(tr, CTRL), y, 1.0); ft = PF._fit(X(tr, CTRL+ZS), y, 1.0)
        pc.append(np.clip(PF._pred(fc, X(te, CTRL)), 0, 1))
        pt.append(np.clip(PF._pred(ft, X(te, CTRL+ZS)), 0, 1)); yy.append(yt)
    pc = np.concatenate(pc); pt = np.concatenate(pt); yy = np.concatenate(yy)
    a = float(np.mean(np.abs(pc-yy))); b = float(np.mean(np.abs(pt-yy)))
    print(f'  {tag:22s} n {len(yy)}  ctrl {a:.6f}  trt {b:.6f}  rel {100*(a-b)/a:+.4f}%')
    return {'n': int(len(yy)), 'ctrl': a, 'trt': b, 'rel_pct': 100*(a-b)/a}


full = build(pers)
within = build(permute(lambda k: (k[0], k[1], k[2]), 20260908))
glob = build(permute(lambda k: 0, 20260908))
rep = {}
# how far did each permutation move the values?
com = [r for r in sub if all(full[id(r)][z] is not None for z in ZS)]
for tag, fm in (('within_team_game', within), ('global', glob)):
    d = {}
    for z in ZS:
        a = np.array([full[id(r)][z] for r in com])
        b = np.array([fm[id(r)][z] if fm[id(r)][z] is not None else np.nan for r in com])
        m = ~np.isnan(b)
        d[z] = {'pearson_vs_real': float(np.corrcoef(a[m], b[m])[0, 1]),
                'mean_abs_shift': float(np.mean(np.abs(a[m]-b[m])))}
    rep[tag+'_feature_shift'] = d
    print(f'{tag}: ' + '  '.join(f"{z.split('_',1)[1]} r={d[z]['pearson_vs_real']:+.3f}"
                                 for z in ZS))
print()
rep['real'] = run(full, 'real')
rep['placebo_within'] = run(within, 'placebo within-team-game')
rep['placebo_global'] = run(glob, 'placebo global')
json.dump(rep, open(f'{S}/probe_leakcheck2.json', 'w'), indent=1)
