import json, csv, statistics as st, random, collections
A = json.load(open('nfl/dfs/salaries/DK_2026W4_EARLY_PROJ.json'))['rows']
I = json.load(open('/tmp/claude-0/trackb/l4/PROJ_INCUMBENT.json'))['rows']
D = json.load(open('/tmp/claude-0/trackb/l4/PROJ_DEPTHFIX.json'))['rows']
def pts(r): return r.get('dk_points')
# reproduction
diffs = [abs((pts(A[k]) or 0) - (pts(I[k]) or 0)) for k in A if k in I]
print('reproduction: rows archived', len(A), 'rerun', len(I), 'common', len(diffs), 'max |diff|', round(max(diffs), 4),
      'n |diff|>0.01', sum(d > 0.01 for d in diffs))
act = {}
for r in csv.DictReader(open('nfl/dfs/salaries/postgame/DK_2026W4_EARLY_POSTGAME_PLAYER_TABLE.csv')):
    try: act[str(r['dk_id'])] = float(r['actual_dk'])
    except (ValueError, KeyError): pass
rows = []
for k, r in I.items():
    if r.get('position') not in ('QB', 'RB', 'WR', 'TE'): continue
    d = D.get(k); did = str(r.get('dk_id'))
    if d is None or did not in act or pts(r) is None or pts(d) is None: continue
    rows.append((r['position'], r.get('team'), pts(r), pts(d), act[did], r.get('name')))
print('scored skill rows', len(rows))
def summ(sel, lab):
    if not sel: return
    n = len(sel); pi = sum(x[2] for x in sel); pd = sum(x[3] for x in sel); a = sum(x[4] for x in sel)
    mi = st.mean(abs(x[2]-x[4]) for x in sel); md = st.mean(abs(x[3]-x[4]) for x in sel)
    print(f'{lab:28s} n={n:3d} proj/actual inc {pi/a:.3f} fix {pd/a:.3f} | MAE inc {mi:.3f} fix {md:.3f} diff {md-mi:+.3f}')
summ(rows, 'all skill')
for p in ('QB', 'RB', 'WR', 'TE'): summ([x for x in rows if x[0] == p], p)
for p in ('QB', 'RB', 'WR', 'TE'):
    s = sorted([x for x in rows if x[0] == p], key=lambda x: -x[2]); q = max(1, len(s)//4)
    summ(s[:q], f'{p} top quartile (by inc proj)')
s = sorted(rows, key=lambda x: -x[2]); summ(s[:30], 'top 30 by inc proj')
# club-clustered bootstrap of MAE difference
clubs = collections.defaultdict(list)
for x in rows: clubs[x[1]].append(abs(x[3]-x[4]) - abs(x[2]-x[4]))
ks = list(clubs); random.seed(1); bs = []
for _ in range(4000):
    smp = [v for c in (random.choice(ks) for _ in ks) for v in clubs[c]]
    bs.append(st.mean(smp))
bs.sort(); print('MAE diff (fix-inc) club-bootstrap 95%', round(bs[100], 3), round(bs[3899], 3), 'clubs', len(ks))
def rk(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0]*len(v); i = 0
    while i < len(o):
        j = i
        while j+1 < len(o) and v[o[j+1]] == v[o[i]]: j += 1
        for t in range(i, j+1): r[o[t]] = (i+j)/2
        i = j+1
    return r
def sp(a, b):
    ra, rb = rk(a), rk(b); return st.correlation(ra, rb)
print('spearman inc', round(sp([x[2] for x in rows], [x[4] for x in rows]), 4), 'fix', round(sp([x[3] for x in rows], [x[4] for x in rows]), 4))
tq = []
for p in ('QB','RB','WR','TE'):
    s_ = sorted([x for x in rows if x[0] == p], key=lambda x: -x[2]); tq += s_[:max(1, len(s_)//4)]
cl = collections.defaultdict(list)
for x in tq: cl[x[1]].append(x)
ks2 = list(cl); bs2 = []; br = []
for _ in range(4000):
    smp = [v for c in (random.choice(ks2) for _ in ks2) for v in cl[c]]
    bs2.append(st.mean(abs(v[3]-v[4]) - abs(v[2]-v[4]) for v in smp))
    a = sum(v[4] for v in smp); br.append((sum(v[2] for v in smp)/a, sum(v[3] for v in smp)/a))
bs2.sort(); print('top-quartile n', len(tq), 'MAE diff 95%', round(bs2[100],3), round(bs2[3899],3))
i_ = sorted(b[0] for b in br); d_ = sorted(b[1] for b in br)
print('top-quartile ratio inc 95%', round(i_[100],3), round(i_[3899],3), 'fix', round(d_[100],3), round(d_[3899],3))
print('RMSE inc', round(st.mean((x[2]-x[4])**2 for x in rows)**.5,3), 'fix', round(st.mean((x[3]-x[4])**2 for x in rows)**.5,3))
print('sum proj inc', round(sum(x[2] for x in rows),1), 'fix', round(sum(x[3] for x in rows),1), 'actual', round(sum(x[4] for x in rows),1))
ch = sorted(rows, key=lambda x: x[3]-x[2])
print('largest cuts', [(x[5], x[0], round(x[2],1), round(x[3],1), x[4]) for x in ch[:8]])
print('largest raises', [(x[5], x[0], round(x[2],1), round(x[3],1), x[4]) for x in ch[-8:]])
