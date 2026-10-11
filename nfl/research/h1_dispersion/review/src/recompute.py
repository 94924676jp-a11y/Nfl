"""Task 1: recompute every number in CHECKA_RESULT.json / DEV_H2_IN_SAMPLE.json / RESULTS table."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/tmp/claude-0/h1review/src')
from lib import *

out = {}
for name, path in (('CHECKA', f'{R}/repro_2022_2023.csv.gz'), ('DEV', f'{R}/repro_2024_2025.csv.gz')):
    df, weeks = load(path)
    res = {'n_weeks': len(weeks), 'n_pool': len(df), 'n_played': int(df.appeared.sum())}
    top, thr = mark_top(df)
    df['top'] = top; df['thr'] = thr
    cand, c, fitted = candidate(df, top, thr)
    df['cand'] = cand; df['c'] = c; df['fitted'] = fitted
    df['prod_err'] = (df.proj - df.actual_dk).abs(); df['cand_err'] = (df.cand - df.actual_dk).abs()
    pl = df[df.appeared == 1]
    # slope of actual on proj (OLS), week-blocked
    def slope(s, col='proj'):
        x, y = s[col].to_numpy(), s.actual_dk.to_numpy()
        return np.cov(x, y, ddof=0)[0, 1] / x.var()
    res['H1_slope'] = boot_stat(pl, slope, B=1000)[:3]
    tq = pl[pl.top]
    res['H1_top_quartile_ratio'] = fast_ratio_boot(tq)
    s = pl.sort_values('proj', kind='stable'); n = len(s)
    td = s.iloc[9 * n // 10:]
    res['H1_top_decile_ratio'] = td.proj.sum() / td.actual_dk.sum()
    r = res['H1_top_quartile_ratio']
    res['H1_CONFIRMED_rule'] = bool(r[0] > 1.05 and r[1] > 1.0)
    res['weeks_tq_over'] = int((tq.groupby('widx').proj.sum() > tq.groupby('widx').actual_dk.sum()).sum())
    # H2 on fitted weeks, played
    f = pl[pl.fitted]
    res['H2_weeks_fitted'] = int(f.widx.nunique())
    res['H2_mae_prod'] = f.prod_err.mean(); res['H2_mae_cand'] = f.cand_err.mean()
    res['H2_mae_diff_weekly_paired'] = weekly_paired(f)
    res['H2_mae_diff_pooled_boot'] = fast_diff_boot(f)
    res['H2_pos_mae_change_pct'] = {p: (f[f.pos == p].cand_err.mean() / f[f.pos == p].prod_err.mean() - 1) * 100 for p in POS}
    lab = deciles(f)
    f = f.assign(dec=lab)
    res['H2_decile_mae_change_pct'] = [(f[f.dec == k].cand_err.mean() / f[f.dec == k].prod_err.mean() - 1) * 100 for k in range(10)]
    tdf = f[f.dec == 9]
    res['H2_top_decile_ratio'] = {'prod': tdf.proj.sum() / tdf.actual_dk.sum(), 'cand': tdf.cand.sum() / tdf.actual_dk.sum()}
    res['H2_slope'] = {'prod': slope(f), 'cand': slope(f, 'cand')}
    tqf = f[f.top]
    res['H2_top_quartile_ratio'] = {'prod': tqf.proj.sum() / tqf.actual_dk.sum(), 'cand': tqf.cand.sum() / tqf.actual_dk.sum(), 'n': len(tqf)}
    res['H2_top_quartile_mae_diff_weekly_paired'] = weekly_paired(tqf)
    res['H2_top_quartile_mae_diff_pooled_boot'] = fast_diff_boot(tqf)
    res['H2_overall_mae_diff_incl_unfitted_weeks'] = fast_diff_boot(pl)
    res['H2_ACCEPT_rule'] = bool(res['H2_top_quartile_mae_diff_weekly_paired'][2] < 0 and res['H2_mae_diff_weekly_paired'][2] <= 0
                                 and max(res['H2_pos_mae_change_pct'].values()) <= 1 and max(res['H2_decile_mae_change_pct']) <= 2
                                 and abs(res['H2_top_quartile_ratio']['cand'] - 1) < abs(res['H2_top_quartile_ratio']['prod'] - 1))
    res['H2_ACCEPT_rule_with_boot_intervals'] = bool(res['H2_top_quartile_mae_diff_pooled_boot'][2] < 0 and res['H2_mae_diff_pooled_boot'][2] <= 0
                                 and max(res['H2_pos_mae_change_pct'].values()) <= 1 and max(res['H2_decile_mae_change_pct']) <= 2)
    last = df[df.widx == df.widx.max()]
    res['c_last_week'] = {p: float(last[last.pos == p].c.iloc[0]) for p in POS}
    # c at the final week computed INCLUDING the last week (what a reader would carry forward)
    res['c_through_end'] = {p: min(1.0, df[(df.pos == p) & df.top & (df.appeared == 1)].actual_dk.sum() /
                                    df[(df.pos == p) & df.top & (df.appeared == 1)].proj.sum()) for p in POS}
    res['top_share_of_pool'] = float(df.top.mean())
    res['tie_rows_at_threshold'] = int((df.proj == df.thr).sum())
    # alt percentile convention (numpy linear)
    top2, thr2 = mark_top(df, qfun=q75_linear)
    res['alt_linear_q75_top_quartile_ratio'] = fast_ratio_boot(df[(df.appeared == 1) & top2])
    res['alt_linear_q75_n_rows_changed_membership'] = int((top2 != top).sum())
    out[name] = res
    df.drop(columns=['wk']).to_csv(f'{R}/scored_{name}.csv.gz', index=False)


def conv(o):
    if isinstance(o, dict): return {k: conv(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [conv(v) for v in o]
    if isinstance(o, (np.floating, float)): return round(float(o), 4)
    if isinstance(o, (np.integer,)): return int(o)
    return o
json.dump(conv(out), open(f'{R}/recompute.json', 'w'), indent=1)
print(json.dumps(conv(out), indent=1))
