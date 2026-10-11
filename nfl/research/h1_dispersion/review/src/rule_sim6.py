import sys, json; sys.path.insert(0,'/tmp/claude-0/h1review/src')
from lib import *
from rule_sim_core import strata_changes
out={}
for name in ('CHECKA','DEV'):
    df = pd.read_csv(f'{R}/scored_{name}.csv.gz', dtype={'gsis': str})
    f = df[(df.appeared == 1) & df.fitted].reset_index(drop=True)
    proj, cand, act, pos = f.proj.to_numpy(), f.cand.to_numpy(), f.actual_dk.to_numpy(), f.pos.to_numpy()
    wk = [np.flatnonzero(f.widx.to_numpy() == w) for w in sorted(f.widx.unique())]
    rng = np.random.default_rng(3); D=[];P=[]
    for b in range(4000):
        idx = np.concatenate([wk[i] for i in rng.integers(0, len(wk), 6)])
        d,p = strata_changes(proj,cand,act,pos,idx); D.append(d); P.append(p)
    D,P=np.array(D),np.array(P)
    sdD, sdP = D.std(0,ddof=1), P.std(0,ddof=1)
    from math import erf,sqrt
    Phi=lambda z:0.5*(1+erf(z/sqrt(2)))
    out[name]={'sd_decile_6wk':sdD.round(2).tolist(),'sd_pos_6wk':dict(zip(POS,sdP.round(2).tolist())),
      'P_false_harm_if_true_zero_decile_6wk':[round(1-Phi(2/s),3) if s>0 else 0 for s in sdD],
      'P_false_harm_if_true_zero_pos_6wk':{q:round(1-Phi(1/s),3) for q,s in zip(POS,sdP)},
      'P_observed_candidate_fails_6wk': round(float(((D.max(1)>2)|(P.max(1)>1)).mean()),4)}
    print(name, out[name])
json.dump(out, open(f'{R}/rule_sim6.json','w'), indent=1)
