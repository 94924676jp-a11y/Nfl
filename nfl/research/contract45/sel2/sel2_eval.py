"""SEL-1 evaluation (PREREG_SEL1_FILL_REPAIR.md @de47858f). Identical pool and policy (GLOBAL) for GREEDY and
FILL_REPAIR_V1; select on even worlds S, score on odd worlds H against the exact per-world optimum; 5 random 90% pool
subsamples for stability. usage: sel1_eval.py SLATE_DIR SCENARIO PREFIX [check_identity]  (run from the repo root)"""
import csv, json, os, sys, time
import numpy as np
sys.path.insert(0, '.')
os.environ['NFL_SHOWDOWN_OVERLAP_POLICY'] = 'GLOBAL'
from nfl.tools import showdown_portfolio as SPF
import collections
sd, scen_name, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
check = len(sys.argv) > 4
d = f'nfl/dfs/salaries/{sd}/{scen_name}'
scen = json.load(open(f'{d}/SCENARIO.json'))
export = scen['export']
if not os.path.isfile(export):
    export = export.split('/m/', 1)[-1] if '/m/' in export else export
draws_p = [f for f in os.listdir(d) if f.endswith('_DRAWS.json')][0]
L = SPF.load(export, f'{d}/{draws_p}', scen['absent_in_state']); assert L.state.value == 'PASS', L
V = L.value
rows = SPF.players_table(V['slate'], V['absent'], V['draws'])
by = {r['key']: r for r in rows}
name2key = {}
for r in rows:
    name2key.setdefault(r['name'], r['key'])
OPT = SPF.world_optimum(rows); assert OPT.state.value == 'PASS'
opt = np.asarray(OPT.value['opt'], float)
cands, dup = [], []
for x in csv.DictReader(open(f'{d}/{prefix}_CANDIDATES.csv')):
    cands.append((name2key[x['captain']], tuple(sorted(name2key[f] for f in x['flex'].split(' / ')))))
    dup.append(float(x['structural_duplication_index']))
D = {k: np.asarray(r['draws'], np.float32) for k, r in by.items() if r['has_draws']}
M = np.array([1.5 * D[c] + sum(D[f] for f in fl) for c, fl in cands], dtype=np.float32)
seats_of = [[c] + list(fl) for c, fl in cands]
contests = collections.OrderedDict()
for e in V['entries']:
    contests.setdefault(e['contest_id'], {'name': e['contest_name'], 'fee': e['entry_fee'], 'entries': []})['entries'].append(e)
nw = M.shape[1]; S = np.arange(0, nw, 2); H = np.arange(1, nw, 2)
def rows_for(hit, idx):
    return [{'first_place_proxy': float(hit[i].mean()), 'structural_duplication_index': dup[i]} for i in idx]
def build(sel, idx, worlds):
    os.environ['NFL_SHOWDOWN_SELECTOR'] = sel
    hit = M[idx][:, worlds] >= (0.9 * opt[worlds])[None, :]
    t = time.time()
    P = SPF.build_contests(hit, rows_for(hit, range(len(idx))), [seats_of[i] for i in idx], contests, len(worlds))
    return P, round(time.time() - t, 1)
def score(P, idx, worlds):
    hitH = M[idx][:, worlds] >= (0.9 * opt[worlds])[None, :]
    out = {}
    for cid, p in P.items():
        dep = hitH[p['chosen']].sum(axis=0); m = p['objective']['m']
        out[cid] = {'n': len(p['chosen']), 'level': p['relaxation_level'], 'H_objective': round(float(np.minimum(dep, m).mean()), 4),
                    'H_coverage': round(float((dep > 0).mean()), 4), 'm': m, 'repaired': bool(p.get('repair')), 'unfillable': bool(p.get('POLICY_UNFILLABLE'))}
    return out
res = {'slate': f'{sd}/{scen_name}', 'n_candidates': len(cands), 'n_worlds': nw, 'contests': {c: len(v['entries']) for c, v in contests.items()}}
if check:
    os.environ['NFL_SHOWDOWN_SELECTOR'] = 'GREEDY'
    hit = M >= (0.9 * opt)[None, :]
    P = SPF.build_contests(hit, rows_for(hit, range(len(cands))), seats_of, contests, nw)
    prod = collections.defaultdict(set)
    for x in csv.DictReader(open(f'{d}/{prefix}_FINAL_LINEUPS.csv')):
        prod[x['contest_id']].add((name2key[x['CPT']], tuple(sorted(name2key[x[f'FLEX{i}']] for i in range(1, 6)))))
    res['default_reproduces_production_all_worlds'] = {cid: {cands[i] for i in p['chosen']} == prod[cid] for cid, p in P.items()}
SELS = ('GREEDY', 'FIXED_POLICY_V1')
full = np.arange(len(cands))
for sel in SELS:
    P, sec = build(sel, full, S)
    res[sel] = {'full_pool': score(P, full, H), 'seconds': sec, 'subsamples': []}
rng = np.random.default_rng(1)
subs = [np.sort(rng.choice(len(cands), int(0.9 * len(cands)), replace=False)) for _ in range(5)]
for sel in SELS:
    for idx in subs:
        P, sec = build(sel, idx, S)
        res[sel]['subsamples'].append(score(P, idx, H))
for sel in SELS:
    sp = {}
    for cid in contests:
        v = [s[cid]['H_objective'] for s in res[sel]['subsamples']]; lv = [s[cid]['level'] for s in res[sel]['subsamples']]
        sp[cid] = {'H_obj_min': min(v), 'H_obj_max': max(v), 'spread': round(max(v) - min(v), 4), 'levels': lv}
    res[sel]['stability'] = sp
print(json.dumps(res, indent=1))
