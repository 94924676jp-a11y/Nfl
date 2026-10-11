import csv, sys, random, statistics as st, collections, json
rows = [r for r in csv.DictReader(open(sys.argv[1]))]
ARM = sys.argv[2] if len(sys.argv) > 2 else 'PROD_blend1.0_cap2.0'
rows = [dict(r, proj=float(r['proj']), actual=float(r['actual_dk']), appeared=int(r['appeared']),
             season=int(r['season']), week=int(r['week'])) for r in rows if r['arm'].startswith(ARM)]
def ols(xs, ys):
    mx, my = st.fmean(xs), st.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return b, my - b * mx
def blocked(rs, f, B=400, seed=7):
    weeks = sorted({(r['season'], r['week']) for r in rs})
    by = collections.defaultdict(list)
    for r in rs: by[(r['season'], r['week'])].append(r)
    rnd = random.Random(seed); vals = []
    for _ in range(B):
        samp = [r for wk in (rnd.choice(weeks) for _ in weeks) for r in by[wk]]
        vals.append(f(samp))
    vals.sort(); return vals[int(0.025 * B)], vals[int(0.975 * B)]
out = {}
for scoring in ('conditional', 'unconditional'):
    base = [r for r in rows if r['appeared']] if scoring == 'conditional' else rows
    for pos in ('ALL', 'QB', 'RB', 'WR', 'TE'):
        rs = base if pos == 'ALL' else [r for r in base if r['pos'] == pos]
        f = lambda s: ols([r['proj'] for r in s], [r['actual'] for r in s])[0]
        b, a = ols([r['proj'] for r in rs], [r['actual'] for r in rs])
        lo, hi = blocked(rs, f)
        out[(scoring, pos)] = (len(rs), b, a, lo, hi, st.fmean(r['proj'] for r in rs), st.fmean(r['actual'] for r in rs))
        print(f'{scoring:13} {pos:3} n={len(rs):6} slope {b:.3f} [{lo:.3f},{hi:.3f}] intercept {a:+.2f} mean proj {out[(scoring,pos)][5]:.2f} actual {out[(scoring,pos)][6]:.2f}')
print('\nreliability (unconditional, production arm): proj decile -> mean proj, mean actual, ratio')
rs = sorted(rows, key=lambda r: r['proj']); n = len(rs)
for d in range(10):
    s = rs[d * n // 10:(d + 1) * n // 10]
    mp, ma = st.fmean(r['proj'] for r in s), st.fmean(r['actual'] for r in s)
    print(f'  d{d+1:2} proj {mp:6.2f} actual {ma:6.2f} ratio {mp/max(ma,1e-9):.3f} appear {st.fmean(r["appeared"] for r in s):.2f}')
print('\nper-week top-N by position (unconditional): proj - actual, weeks over')
TOPN = {'QB': 12, 'RB': 24, 'WR': 36, 'TE': 12}
for pos, k in TOPN.items():
    diffs = []
    for wk in sorted({(r['season'], r['week']) for r in rows}):
        s = sorted([r for r in rows if (r['season'], r['week']) == wk and r['pos'] == pos], key=lambda r: -r['proj'])[:k]
        if len(s) == k:
            diffs.append(st.fmean(r['proj'] for r in s) - st.fmean(r['actual'] for r in s))
    m = st.fmean(diffs); se = st.stdev(diffs) / len(diffs) ** 0.5
    print(f'  {pos} top{k}: {m:+.2f} pts (SE {se:.2f}), over-projected {sum(d>0 for d in diffs)}/{len(diffs)} weeks; by season ' +
          str({s: round(st.fmean(d for d, wk in zip(diffs, sorted({(r["season"], r["week"]) for r in rows})) if wk[0] == s), 2) for s in sorted({r['season'] for r in rows})}))
