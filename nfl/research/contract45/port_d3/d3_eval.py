"""PORT-D3 evaluation (PREREG @b1945cd5). Each arm's 150/20/20 portfolio on the INDEPENDENT panel (decision metric) and the
primary worlds (in-sample), against the EXACT brute-force world optima; then actual-points ranks, labelled HINDSIGHT.
Run in the corrected overlay."""
import csv, json, sys
import numpy as np
sys.path.insert(0, '.')
from nfl.tools import showdown_portfolio as SPF
B = 'nfl/dfs/salaries/showdown_buf_lar'
E = 'nfl/dfs/salaries/raw/showdown_buf_lar_2026W5/DKEntries_BUF_LAR_SHOWDOWN_2026W5.81b504dbc36395c4.csv'
P = '/tmp/claude-0/mnf_post'
_U = np.load(f'{P}/d3_universe.npz')
U = {k: _U[k] for k in ('opt_i', 'opt_p')}
scen = json.load(open(f'{B}/FINAL_CV1/SCENARIO.json'))
Dp = SPF.load(E, f'{B}/FINAL_CV1/SHOWDOWN_BUF_LAR_2026W5_DRAWS.json', scen['absent_in_state']).value['draws']
Di = SPF.load(E, f'{B}/SHADOW_S1SEED_FINAL_CV1/SHOWDOWN_BUF_LAR_2026W5_DRAWS.json', scen['absent_in_state']).value['draws']
idmap = {}
for r in list(csv.reader(open(E, encoding='utf-8-sig')))[8:]:
    if len(r) >= 20 and r[14]:
        idmap[r[14].strip()] = f'{r[13].strip()}|{r[18].strip()}'
pm = json.load(open(f'{P}/pm.json'))
fl = pm['actual_flex_points']
field = {}
for c in ('196537776', '196537799', '196537800'):
    pts = [float(r[4]) for r in list(csv.reader(open(f'{P}/contest-standings-{c}.csv', encoding='utf-8-sig')))[1:] if r and r[0].strip()]
    field[c] = np.sort(np.array(pts))
arms = {'A_production_corrected': f'{B}/FINAL_CV1', 'G1_played': f'{B}/SHADOW_S1_G1_FINAL_CV1',
        'B_enriched_same_size': f'{B}/SHADOW_D3_ARM_B', 'C_union': f'{B}/SHADOW_D3_ARM_C'}
M_OF = {'196537776': 1, '196537799': 2, '196537800': 2}
def S(D, c, f):
    return 1.5 * np.asarray(D[c], float) + sum(np.asarray(D[x], float) for x in f)
out = {}
for arm, d in arms.items():
    try:
        rows = [r for r in list(csv.reader(open(f'{d}/SHOWDOWN_BUF_LAR_DK_UPLOAD.csv')))[1:] if r and r[0].strip().isdigit()]
    except FileNotFoundError:
        out[arm] = 'NO UPLOAD'
        continue
    by = {}
    for r in rows:
        ks = [idmap[x.strip()] for x in r[4:10]]
        by.setdefault(r[2].strip(), []).append((ks[0], ks[1:]))
    out[arm] = {}
    for cid, L in by.items():
        m = M_OF[cid]
        res = {'n': len(L)}
        for lab, D, opt in (('independent', Di, U['opt_i']), ('primary_in_sample', Dp, U['opt_p'])):
            hit = np.array([S(D, c, f) >= 0.9 * opt for c, f in L])
            depth = hit.sum(axis=0)
            res[lab] = {'coverage': round(float((depth > 0).mean()), 4), 'objective': round(float(np.minimum(depth, m).mean()), 4)}
        act = sorted((1.5 * fl.get(c.split('|')[0], 0) + sum(fl.get(x.split('|')[0], 0) for x in f)) for c, f in L)[::-1]
        a = field[cid]
        res['HINDSIGHT_actual'] = {'best': round(act[0], 2), 'best_rank': int((a > act[0] + 1e-9).sum()) + 1,
                                   'median': round(float(np.median(act)), 2),
                                   'n_top_10pct': int(sum((a > s + 1e-9).sum() + 1 <= 0.1 * len(a) for s in act))}
        out[arm][cid] = res
print(json.dumps(out, indent=1))
