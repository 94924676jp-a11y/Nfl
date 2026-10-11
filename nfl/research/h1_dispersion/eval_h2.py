"""H1/H2 evaluation exactly as PREREG_H1_DISPERSION.md section 4-5 freeze it. Reads captured rows only.

    python3.12 eval_h2.py ROWS.csv [ARM]   (ARM default '1.0|2.0' = production)
"""
import csv, sys, random, statistics as st, collections, json
ARM = sys.argv[2] if len(sys.argv) > 2 else '1.0|2.0'
MIN_PRIOR_WEEKS_FIT = 8
rows = [dict(r, proj=float(r['proj']), actual=float(r['actual_dk']), appeared=int(r['appeared']),
             season=int(r['season']), week=int(r['week']))
        for r in csv.DictReader(open(sys.argv[1])) if r['arm'] == ARM]
weeks = sorted({(r['season'], r['week']) for r in rows})
by_wk = collections.defaultdict(list)
for r in rows:
    by_wk[(r['season'], r['week'])].append(r)

def ols(xs, ys):
    mx, my = st.fmean(xs), st.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    return (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx) if sxx > 0 else 1.0

# candidate (frozen in PREREG section 4): top-quartile level correction. For each position and week, q75 is the
# 75th percentile of that week's pool projections. c is sum(actual)/sum(projection) over strictly earlier weeks'
# top-quartile players who played (minimum 8 prior weeks, else c = 1). A player at or above q75 gets
# p' = min(p, max(q75, c * p)); everyone else is unchanged. Monotone within a position; ties possible near q75.
for i, wk in enumerate(weeks):
    for pos in ('QB', 'RB', 'WR', 'TE'):
        cur = [r for r in by_wk[wk] if r['pos'] == pos]
        if not cur:
            continue
        q75 = sorted(r['proj'] for r in cur)[int(0.75 * len(cur))]
        for r in cur:
            r['top_q'] = r['proj'] >= q75
            r['q75'] = q75
for i, wk in enumerate(weeks):
    for pos in ('QB', 'RB', 'WR', 'TE'):
        cur = [r for r in by_wk[wk] if r['pos'] == pos]
        pr = [r for w in weeks[:i] for r in by_wk[w] if r['pos'] == pos and r['appeared'] and r['top_q']]
        c = (sum(r['actual'] for r in pr) / sum(r['proj'] for r in pr)) if i >= MIN_PRIOR_WEEKS_FIT and pr else 1.0
        c = min(c, 1.0)                     # a correction only ever lowers; it never raises a projection
        for r in cur:
            r['cand'] = min(r['proj'], max(r['q75'], c * r['proj'])) if r['top_q'] else r['proj']
            r['beta'] = c
            r['fitted'] = i >= MIN_PRIOR_WEEKS_FIT


def slope(rs, key):
    return ols([r[key] for r in rs], [r['actual'] for r in rs])

def boot(f, rs_by_week, B=400, seed=11):
    ws = list(rs_by_week); rnd = random.Random(seed); out = []
    for _ in range(B):
        samp = [r for w in (rnd.choice(ws) for _ in ws) for r in rs_by_week[w]]
        out.append(f(samp))
    out.sort(); return out[int(.025 * B)], out[int(.975 * B)]

played = [r for r in rows if r['appeared']]
pw = collections.defaultdict(list)
for r in played:
    pw[(r['season'], r['week'])].append(r)
res = {'arm': ARM, 'n_weeks': len(weeks), 'n_played': len(played)}
lo, hi = boot(lambda s: slope(s, 'proj'), pw)
res['H1_slope'] = [round(slope(played, 'proj'), 4), round(lo, 4), round(hi, 4)]
tq = [r for r in played if r['top_q']]
tqw = collections.defaultdict(list)
for r in tq:
    tqw[(r['season'], r['week'])].append(r)
ratio = lambda s: st.fmean(r['proj'] for r in s) / st.fmean(r['actual'] for r in s)
lo_r, hi_r = boot(ratio, tqw)
res['H1_top_quartile_ratio'] = [round(ratio(tq), 4), round(lo_r, 4), round(hi_r, 4), len(tq)]
srt = sorted(played, key=lambda r: r['proj']); n = len(srt); top = srt[9 * n // 10:]
res['H1_top_decile_ratio'] = round(st.fmean(r['proj'] for r in top) / st.fmean(r['actual'] for r in top), 4)
res['H1_CONFIRMED'] = res['H1_top_quartile_ratio'][0] > 1.05 and res['H1_top_quartile_ratio'][1] > 1.0
# H2, evaluated only on weeks where the candidate is fitted (beta estimated), paired by week
fw = [w for w in pw if all(r['fitted'] for r in pw[w])]
d = [st.fmean(abs(r['cand'] - r['actual']) for r in pw[w]) - st.fmean(abs(r['proj'] - r['actual']) for r in pw[w]) for w in fw]
mdiff = st.fmean(d); se = st.stdev(d) / len(d) ** .5
res['H2_weeks_fitted'] = len(fw)
res['H2_mae_prod'] = round(st.fmean(abs(r['proj'] - r['actual']) for w in fw for r in pw[w]), 4)
res['H2_mae_cand'] = round(st.fmean(abs(r['cand'] - r['actual']) for w in fw for r in pw[w]), 4)
res['H2_mae_diff_weekly'] = [round(mdiff, 4), round(mdiff - 1.96 * se, 4), round(mdiff + 1.96 * se, 4)]
fitted_rows = [r for w in fw for r in pw[w]]
per_pos = {}
for pos in ('QB', 'RB', 'WR', 'TE'):
    s = [r for r in fitted_rows if r['pos'] == pos]
    a, b = st.fmean(abs(r['proj'] - r['actual']) for r in s), st.fmean(abs(r['cand'] - r['actual']) for r in s)
    per_pos[pos] = round((b - a) / a * 100, 3)
res['H2_pos_mae_change_pct'] = per_pos
srt = sorted(fitted_rows, key=lambda r: r['proj']); n = len(srt)
dec = []
for k in range(10):
    s = srt[k * n // 10:(k + 1) * n // 10]
    a, b = st.fmean(abs(r['proj'] - r['actual']) for r in s), st.fmean(abs(r['cand'] - r['actual']) for r in s)
    dec.append(round((b - a) / a * 100, 3))
res['H2_decile_mae_change_pct'] = dec
top = srt[9 * n // 10:]
res['H2_top_decile_ratio'] = {'prod': round(st.fmean(r['proj'] for r in top) / st.fmean(r['actual'] for r in top), 4),
                              'cand': round(st.fmean(r['cand'] for r in top) / st.fmean(r['actual'] for r in top), 4)}
res['H2_slope'] = {'prod': round(slope(fitted_rows, 'proj'), 4), 'cand': round(slope(fitted_rows, 'cand'), 4)}
tqf = [r for r in fitted_rows if r['top_q']]
res['H2_top_quartile_ratio'] = {'prod': round(ratio(tqf), 4), 'cand': round(st.fmean(r['cand'] for r in tqf) / st.fmean(r['actual'] for r in tqf), 4)}
tqa = collections.defaultdict(list)
for r in tqf:
    tqa[(r['season'], r['week'])].append(r)
dq = [st.fmean(abs(r['cand'] - r['actual']) for r in v) - st.fmean(abs(r['proj'] - r['actual']) for r in v) for v in tqa.values()]
res['H2_top_quartile_mae_diff_weekly'] = [round(st.fmean(dq), 4), round(st.fmean(dq) - 1.96 * st.stdev(dq) / len(dq) ** .5, 4),
                                          round(st.fmean(dq) + 1.96 * st.stdev(dq) / len(dq) ** .5, 4)]
res['H2_ACCEPT_FOR_SHADOW'] = (res['H2_top_quartile_mae_diff_weekly'][2] < 0 and res['H2_mae_diff_weekly'][2] <= 0
                               and max(per_pos.values()) <= 1.0 and max(dec) <= 2.0
                               and abs(res['H2_top_quartile_ratio']['cand'] - 1) < abs(res['H2_top_quartile_ratio']['prod'] - 1))
res['betas_last_week'] = {pos: round(next(r['beta'] for r in by_wk[weeks[-1]] if r['pos'] == pos), 4) for pos in ('QB', 'RB', 'WR', 'TE')}
print(json.dumps(res, indent=1))
