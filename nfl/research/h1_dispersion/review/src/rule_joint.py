import sys, json; sys.path.insert(0,'/tmp/claude-0/h1review/src')
from lib import *
from rule_sim_core import strata_changes
out={}
for name in ('CHECKA','DEV'):
    df = pd.read_csv(f'{R}/scored_{name}.csv.gz', dtype={'gsis': str})
    f = df[(df.appeared == 1) & df.fitted].reset_index(drop=True)
    proj, cand, act, pos = f.proj.to_numpy(), f.cand.to_numpy(), f.actual_dk.to_numpy(), f.pos.to_numpy()
    wk = [np.flatnonzero(f.widx.to_numpy() == w) for w in sorted(f.widx.unique())]
    for nw in (20, 6):
        rng = np.random.default_rng(5); D=[];P=[]
        for b in range(4000):
            idx = np.concatenate([wk[i] for i in rng.integers(0, len(wk), nw)])
            d,p = strata_changes(proj,cand,act,pos,idx); D.append(d); P.append(p)
        D,P=np.array(D),np.array(P)
        Dc, Pc = D - D.mean(0), P - P.mean(0)   # every stratum's true change set to exactly 0, correlation kept
        out[f'{name}_{nw}wk'] = {'P_null_fails_decile_rule': round(float((Dc.max(1)>2).mean()),4),
                                 'P_null_fails_position_rule': round(float((Pc.max(1)>1).mean()),4),
                                 'P_null_fails_either': round(float(((Dc.max(1)>2)|(Pc.max(1)>1)).mean()),4)}
        print(name, nw, out[f'{name}_{nw}wk'])
json.dump(out, open(f'{R}/rule_joint.json','w'), indent=1)
