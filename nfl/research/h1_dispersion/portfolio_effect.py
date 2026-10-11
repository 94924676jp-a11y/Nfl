"""H1 portfolio effect, week-4 early Classic (descriptive; already-seen slate). Paired: same inputs, same seed,
same builder (nfl/opt/classic_portfolio.py, unmodified); the only difference is the candidate's top-quartile
rescaling of each player's simulated draws (O1 factors). Writes nothing in the repository."""
import json, csv, collections, statistics as st, copy, sys
import numpy as np
from nfl.opt import classic_portfolio as CP
C = {'QB': 0.9517, 'RB': 0.8440, 'WR': 0.7771, 'TE': 0.7652}     # addendum v1.1 O1
SLATE = '2026W4'
L0 = CP.load(SLATE); assert L0.state.value == 'PASS', L0
base = L0.value
ids, M, meta = base['ids'], base['M'], base['meta']
mean = M.mean(axis=1)
f = np.ones(len(ids))
for pos, c in C.items():
    ix = [i for i, d in enumerate(ids) if meta[d]['pos'] == pos]
    q75 = sorted(mean[i] for i in ix)[int(0.75 * len(ix))]
    for i in ix:
        if mean[i] >= q75:
            cand = min(mean[i], max(q75, c * mean[i]))
            f[i] = cand / mean[i] if mean[i] > 0 else 1.0
Mc = M * f[:, None]
print('players rescaled', int((f < 1).sum()), 'of', len(ids), 'mean factor among them', round(float(f[f < 1].mean()), 4))
chosen = {}
_select = CP.select
def rec(tag):
    def s(cands, ids_, M_, meta_, n, prof):
        out = _select(cands, ids_, M_, meta_, n, prof)
        chosen.setdefault(tag, []).append((n, [cands[j] for j in out[0]]))
        return out
    return s
def run(tag, Mx):
    L = dict(base, M=Mx)
    CP.load = lambda slate_id: CP.Outcome.ok('X', L, '')
    CP.select = rec(tag)
    r = CP.build(SLATE, write=False)
    return r
import pickle, os
PK = '/tmp/claude-0/trackb/W4_portfolios.pkl'
if os.path.exists(PK):
    chosen = pickle.load(open(PK, 'rb'))
else:
    r0 = run('incumbent', M); r1 = run('candidate', Mc)
    print('build', r0.state.value, r1.state.value)
    pickle.dump(chosen, open(PK, 'wb'))
arch = json.load(open('nfl/dfs/salaries/DK_2026W4_EARLY_PORTFOLIOS.json'))
for c in arch['contests']:
    a = {tuple(sorted(s['dk_id'] for s in lu['slots'])) for lu in c['lineups']}
    mine = [set(tuple(sorted(x)) for x in lus) for n, lus in chosen['incumbent'] if n == c['n_entries']][0]
    print('reproducibility', c['profile'], 'archived lineups reproduced by the incumbent rebuild:', len(a & mine), '/', len(a))
act = {}
for r in csv.DictReader(open('nfl/dfs/salaries/postgame/DK_2026W4_EARLY_POSTGAME_PLAYER_TABLE.csv')):
    act[r['dk_id']] = float(r['actual_dk']) if r['actual_dk'] else 0.0
FILES = {150: 'nfl/postgame/raw/2026W4_standings/DK_STANDINGS.733e8fd74611e380.csv',
         20: 'nfl/postgame/raw/2026W4_standings_addendum_2/DK_STANDINGS.e7212baf9e8612de.csv',
         3: 'nfl/postgame/raw/2026W4_standings_addendum_2/DK_STANDINGS.ac54fe2a6483efbc.csv'}
FIELDS = {}
for n_, fp in FILES.items():
    v = []
    for r in csv.DictReader(open(fp, encoding='utf-8-sig')):
        try:
            if r.get('EntryId'):
                v.append(float(r['Points']))
        except (TypeError, ValueError, KeyError):
            pass
    FIELDS[n_] = sorted(v)
import bisect
def pct_in(n_, x):
    f_ = FIELDS[n_]
    return 1 - bisect.bisect_right(f_, x) / len(f_)
res = {}
for tag in ('incumbent', 'candidate'):
    for n, lus in chosen[tag]:
        pts = [sum(act.get(d, 0.0) for d in lu) for lu in lus]
        exp = collections.Counter(d for lu in lus for d in lu)
        res[(tag, n)] = {'n': len(lus), 'mean_pts': round(st.fmean(pts), 2), 'best': round(max(pts), 2),
                         'top1pct_vs_field': sum(pct_in(n, p) <= 0.01 for p in pts), 'top10pct_vs_field': sum(pct_in(n, p) <= 0.10 for p in pts),
                         'median_field_pct': round(st.median(pct_in(n, p) for p in pts), 4), 'exp': exp,
                         'set': {tuple(sorted(lu)) for lu in lus}}
print('field sizes', {k: len(v) for k, v in FIELDS.items()})
for n in sorted({n for (_, n) in res}):
    a, b = res[('incumbent', n)], res[('candidate', n)]
    shared = len(a['set'] & b['set'])
    keys = set(a['exp']) | set(b['exp'])
    moves = sorted(((b['exp'][k] - a['exp'][k]) / n * 100, meta[k]['name'], meta[k]['pos']) for k in keys)
    print(f'\n{n}-entry portfolio: lineups shared {shared}/{n}')
    for t, x in (('incumbent', a), ('candidate', b)):
        print(f'  {t:9} mean {x["mean_pts"]} best {x["best"]} top1% {x["top1pct_vs_field"]} top10% {x["top10pct_vs_field"]} median field percentile {x["median_field_pct"]}')
    print('  largest exposure cuts (pp):', [(round(m, 1), nm, p) for m, nm, p in moves[:6]])
    print('  largest exposure gains (pp):', [(round(m, 1), nm, p) for m, nm, p in moves[-6:]])
