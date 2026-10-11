import sys, json; sys.path.insert(0,'/tmp/claude-0/h1review/src')
from lib import *
out = {}
for name, f in (('CHECKA','sens_depthfix_2022_2023.csv.gz'),('DEV','sens_depthfix_2024_2025.csv.gz')):
    df = pd.read_csv(f'{R}/scored_{name}.csv.gz', dtype={'gsis': str})
    a = pd.read_csv(f'{R}/{f}', dtype={'gsis': str})
    m = df.merge(a, on=['season','week','gsis'], how='inner').reset_index(drop=True)
    assert len(m) == len(df)
    m['proj'] = m['proj_aug']; t, thr = mark_top(m); m['top'] = t; m['thr'] = thr
    pl = m[(m.appeared==1)&m.top]
    o = {'all': fast_ratio_boot(pl)[:3] + (len(pl),)}
    for s in sorted(m.season.unique()): o[f'season {s}'] = fast_ratio_boot(pl[pl.season==s])[:3]
    for p in POS: o[p] = fast_ratio_boot(pl[pl.pos==p])[:3]
    o['all_played_level'] = m[m.appeared==1].proj.sum()/m[m.appeared==1].actual_dk.sum()
    o['unconditional_topq'] = fast_ratio_boot(m[m.top])[:3]
    # candidate under this spec
    cand, c, fitted = candidate(m, m.top.to_numpy(), m.thr.to_numpy())
    m['cand']=cand; m['c']=c
    m['prod_err']=(m.proj-m.actual_dk).abs(); m['cand_err']=(m.cand-m.actual_dk).abs()
    f_ = m[(m.appeared==1)&fitted]
    o['cand_topq_mae_diff'] = weekly_paired(f_[f_.top])
    o['c_last'] = {p: float(m[(m.widx==m.widx.max())&(m.pos==p)].c.iloc[0]) for p in POS}
    o['spearman_proj_actual_played_orig_vs_fix'] = (float(df[df.appeared==1][['proj','actual_dk']].corr('spearman').iloc[0,1]), float(m[m.appeared==1][['proj','actual_dk']].corr('spearman').iloc[0,1]))
    o['mae_played_orig_vs_fix'] = (float((df[df.appeared==1].proj-df[df.appeared==1].actual_dk).abs().mean()), float((m[m.appeared==1].proj-m[m.appeared==1].actual_dk).abs().mean()))
    out[name] = o
    print(name, json.dumps(o, default=float))
json.dump(out, open(f'{R}/sens_depthfix.json','w'), default=float, indent=1)
