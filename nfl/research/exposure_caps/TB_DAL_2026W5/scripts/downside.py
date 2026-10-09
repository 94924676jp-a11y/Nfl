"""Conditional downside on identical worlds: portfolio outcomes in the worlds where the arm's top-exposed player
lands in his own bottom decile. Research only; in-simulation, no realised outcome used."""
import json, sys, pathlib, collections
import numpy as np
sys.path.insert(0, '/home/user/nfl')
from nfl.postgame import showdown_postgame as SP
R = pathlib.Path('/home/user/nfl'); S = R/'nfl/dfs/salaries/showdown_tb_dal'; X = pathlib.Path(sys.argv[1])
d = json.loads((S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json').read_text())
W = {k.rsplit('|', 1)[0]: np.asarray(v, float) for k, v in d['draws'].items()}
def score(L): return np.stack([1.5*W[c] + sum(W[f] for f in fl) for c, fl in L])
out = {}
for arm in ('0.50', '0.60', '1.00'):
    L = SP.lineups_from_final(X/f'cap_{arm}'/'SHOWDOWN_TB_DAL_FINAL_LINEUPS.csv')
    o = {}
    for cid, lab in (('196438543', '150max'), ('196438555', '20max')):
        LL = [(c, f) for x, _, c, f in L if x == cid]
        M = score(LL)
        for star in ('CeeDee Lamb', 'Bucky Irving', 'Dak Prescott'):
            dud = W[star] <= np.percentile(W[star], 10)
            e = sum(1 for c, f in LL if star in (c, *f)) / len(LL)
            o.setdefault(lab, {})[star] = {'exposure': round(e, 2), 'n_dud_worlds': int(dud.sum()),
                'portfolio_mean_in_dud_worlds': round(float(M[:, dud].mean()), 2),
                'best_lineup_in_dud_worlds_mean': round(float(M[:, dud].max(0).mean()), 2),
                'portfolio_mean_other_worlds': round(float(M[:, ~dud].mean()), 2)}
        pm = M.mean(0)
        o[lab]['portfolio_mean_p05_p50'] = [round(float(np.percentile(pm, 5)), 2), round(float(np.percentile(pm, 50)), 2)]
        o[lab]['best_lineup_p05'] = round(float(np.percentile(M.max(0), 5)), 2)
    out[arm] = o
(X/'CAP_SENSITIVITY_DOWNSIDE.json').write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
