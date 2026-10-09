import json, csv, sys, pathlib, numpy as np, itertools, collections
S = pathlib.Path('/home/user/nfl/nfl/dfs/salaries/showdown_tb_dal')
SP = pathlib.Path('.')
base = json.loads((S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json').read_text())
name2key = {k.rsplit('|',1)[0]: k for k in base['draws']}
scen = {'OURS': {k: np.asarray(v, float) for k, v in base['draws'].items()}}
for t in ('FC_REF', 'MID_TB', 'REDIST'):
    scen[t] = {k: np.asarray(v, float) for k, v in json.loads((SP/f'DRAWS_{t}.json').read_text())['draws'].items()}
def lineups(d):
    out = []
    for r in csv.DictReader(open(pathlib.Path(d)/'SHOWDOWN_TB_DAL_FINAL_LINEUPS.csv')):
        out.append((r['contest_id'], r['CPT'], tuple(r[f'FLEX{i}'] for i in range(1, 6))))
    return out
def cands(d):
    return [(r['captain'], tuple(x.strip() for x in r['flex'].split(' / '))) for r in csv.DictReader(open(pathlib.Path(d)/'SHOWDOWN_TB_DAL_CANDIDATES.csv'))]
def score(L, W):
    return np.stack([1.5*W[name2key[c]] + sum(W[name2key[f]] for f in fl) for c, fl in L])
dirs = {'CORRECTED_R1': S/'OFFICIAL_ELIGIBILITY_FIX_R1'}
for t in ('FC_REF', 'MID_TB', 'REDIST'):
    if (SP/f'out_{t}/SHOWDOWN_TB_DAL_FINAL_LINEUPS.csv').is_file(): dirs['REOPT_'+t] = SP/f'out_{t}'
P = {k: lineups(v) for k, v in dirs.items()}
# world optimum proxy: best over the union of all builds' candidate pools (eligible only)
U = set()
for v in dirs.values(): U |= set(cands(v))
U = sorted(U)
res = {'portfolios': list(dirs), 'n_union_candidates': len(U), 'eval': {}}
for sn, W in scen.items():
    opt = score(U, W).max(0)
    for pn, L in P.items():
        for cid, lab, m in (('196438543', '150max', 1), ('196438555', '20max', 2)):
            LL = [(c, f) for x, c, f in L if x == cid]
            M = score(LL, W); hit = M >= 0.9*opt
            best = M.max(0)
            res['eval'].setdefault(sn, {}).setdefault(pn, {})[lab] = {
                'n': len(LL), 'mean_lineup': round(float(M.mean()), 2), 'best_per_world_mean': round(float(best.mean()), 2),
                'best_p10': round(float(np.percentile(best, 10)), 1), 'best_p90': round(float(np.percentile(best, 90)), 1),
                'coverage_0.9opt': round(float((hit.sum(0) >= m).mean()), 4)}
# concentration of corrected R1
def expo(L):
    c, f = collections.Counter(), collections.Counter()
    for _, cp, fl in L:
        c[cp] += 1; f[cp] += 1
        for x in fl: f[x] += 1
    return c, f
for pn, L in P.items():
    c, f = expo(L); n = len(L)
    tbr = ['Emeka Egbuka', 'Chris Godwin Jr.', 'Jalon Daniels', 'Cade Otton']
    trio = sum(1 for _, cp, fl in L if {'Emeka Egbuka', 'Chris Godwin Jr.', 'Jalon Daniels'} <= set((cp,)+fl))
    res.setdefault('exposure', {})[pn] = {'n': n, **{p: [f[p], c[p]] for p in tbr}, 'egbuka_godwin_daniels_together': trio,
        'top_captains': c.most_common(6)}
    L150 = [set((cp,)+fl) for x, cp, fl in L if x == '196438543']
    ov = collections.Counter(len(a & b) for a, b in itertools.combinations(L150, 2))
    res.setdefault('overlap_150', {})[pn] = dict(sorted(ov.items()))
json.dump(res, open('EVAL.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
