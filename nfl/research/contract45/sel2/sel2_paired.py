"""SEL-2 paired harness (PREREG_SEL2_PROSPECTIVE_W6.md @2f510449). Incumbent GREEDY against FIXED_POLICY_V1 on identical
inputs: select on even worlds S, score on odd worlds H; 5 x 90% pool subsamples (default_rng(1)); order reversal of
equal-size contests; nested-pool monotonicity; runtime; an independent constraint checker. Writes nothing; prints JSON.
usage (from a repo root, ideally an isolated overlay):
  python3.12 sel2_paired.py SLATE_DIR SCENARIO PREFIX [OVERLAP_POLICY]   (OVERLAP_POLICY default GLOBAL)"""
import collections
import csv
import hashlib
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, '.')
sd, scen_name, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ['NFL_SHOWDOWN_OVERLAP_POLICY'] = sys.argv[4] if len(sys.argv) > 4 else 'GLOBAL'
from nfl.tools import showdown_portfolio as SPF  # noqa: E402

SELS = ('GREEDY', 'FIXED_POLICY_V1')
d = f'nfl/dfs/salaries/{sd}/{scen_name}'
scen = json.load(open(f'{d}/SCENARIO.json'))
export = scen['export']
if not os.path.isfile(export):
    export = export.split('/m/', 1)[-1] if '/m/' in export else export
draws_p = f"{d}/{[f for f in os.listdir(d) if f.endswith('_DRAWS.json')][0]}"
cand_p = f'{d}/{prefix}_CANDIDATES.csv'
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
L = SPF.load(export, draws_p, scen['absent_in_state']); assert L.state.value == 'PASS', L
V = L.value
rows = SPF.players_table(V['slate'], V['absent'], V['draws'])
by = {r['key']: r for r in rows}
name2key = {}
for r in rows:
    name2key.setdefault(r['name'], r['key'])
OPT = SPF.world_optimum(rows); assert OPT.state.value == 'PASS'
opt = np.asarray(OPT.value['opt'], float)
cands, dup = [], []
for x in csv.DictReader(open(cand_p)):
    cands.append((name2key[x['captain']], tuple(sorted(name2key[f] for f in x['flex'].split(' / ')))))
    dup.append(float(x['structural_duplication_index']))
assert cands, 'EMPTY_CANDIDATE_POOL'
D = {k: np.asarray(r['draws'], np.float32) for k, r in by.items() if r['has_draws']}
M = np.array([1.5 * D[c] + sum(D[f] for f in fl) for c, fl in cands], dtype=np.float32)
seats_of = [[c] + list(fl) for c, fl in cands]
contests = collections.OrderedDict()
for e in V['entries']:
    contests.setdefault(e['contest_id'], {'name': e['contest_name'], 'fee': e['entry_fee'], 'entries': []})['entries'].append(e)
nw = M.shape[1]; S = np.arange(0, nw, 2); H = np.arange(1, nw, 2)


def reversed_contests():
    """A copy whose prize-pool labels reverse the build order inside every group of equal-size contests."""
    import re
    pool = lambda c: float((re.search(r'\$([0-9.]+)K', contests[c]['name']) or [None, '0'])[1]) * 1000
    order = sorted(contests, key=lambda c: (-len(contests[c]['entries']), -pool(c), c))
    out = collections.OrderedDict((c, dict(v)) for c, v in contests.items())
    groups = collections.defaultdict(list)
    for c in order:
        groups[len(contests[c]['entries'])].append(c)
    swapped = []
    for n, g in groups.items():
        if len(g) > 1:
            for i, c in enumerate(g):            # first-built gets the smallest label, so it is built last
                out[c]['name'] = f'ORDER_REVERSED ${i + 1}K'
            swapped += g
    return out, swapped


def rows_for(hit, idx):
    return [{'first_place_proxy': float(hit[i].mean()), 'structural_duplication_index': dup[i]} for i in idx]


def build(sel, idx, cdefs):
    os.environ['NFL_SHOWDOWN_SELECTOR'] = sel
    hit = M[idx][:, S] >= (0.9 * opt[S])[None, :]
    t = time.time()
    P = SPF.build_contests(hit, rows_for(hit, range(len(idx))), [seats_of[i] for i in idx], cdefs, len(S))
    return P, round(time.time() - t, 2)


def score(P, idx, worlds):
    h = M[idx][:, worlds] >= (0.9 * opt[worlds])[None, :]
    out = {}
    for cid, p in P.items():
        dep = h[p['chosen']].sum(axis=0); m = p['objective']['m']
        out[cid] = {'n': len(p['chosen']), 'level': p['relaxation_level'], 'objective': round(float(np.minimum(dep, m).mean()), 4),
                    'coverage': round(float((dep > 0).mean()), 4), 'm': m, 'unfillable': bool(p.get('POLICY_UNFILLABLE'))}
    return out


def caps_for(level, n):
    """Recomputed from LADDER, independently of select(): floor at level 0, ceil at 1-3, n for n <= 2."""
    r = SPF.LADDER[level]
    if n <= 2:
        return n, n, r['overlap']
    if level == 0:
        return max(1, int(r['player'] * n)), max(1, int(r['captain'] * n)), r['overlap']
    return max(1, int(np.ceil(r['player'] * n))), max(1, int(np.ceil(r['captain'] * n))), r['overlap']


def check(P, idx, sel, cdefs):
    v, seen = [], {}
    for cid, p in P.items():
        n = len(cdefs[cid]['entries'])
        ln = [(seats_of[idx[j]][0], tuple(sorted(seats_of[idx[j]][1:]))) for j in p['chosen']]
        if len(ln) != n and not p.get('POLICY_UNFILLABLE'):
            v.append(f'{cid}: size {len(ln)} != {n}')
        if len(set(ln)) != len(ln):
            v.append(f'{cid}: repeated lineup')
        for x in ln:
            if os.environ['NFL_SHOWDOWN_OVERLAP_POLICY'] == 'GLOBAL' and x in seen:
                v.append(f'{cid}: lineup also in {seen[x]}')
            seen.setdefault(x, cid)
        cp, cc, ov = caps_for(p['relaxation_level'], n)
        exp = collections.Counter(k for c, f in ln for k in (c,) + f)
        cexp = collections.Counter(c for c, _ in ln)
        if exp and max(exp.values()) > cp:
            v.append(f'{cid}: player exposure {max(exp.values())} > {cp}')
        if cexp and max(cexp.values()) > cc:
            v.append(f'{cid}: captain exposure {max(cexp.values())} > {cc}')
        sets = [set((c,) + f) for c, f in ln]
        if any(len(a & b) > ov for i, a in enumerate(sets) for b in sets[i + 1:]):
            v.append(f'{cid}: pairwise overlap > {ov}')
        if sel == 'FIXED_POLICY_V1' and SPF.FIXED_POLICY_MIN_N <= n < SPF.FIXED_POLICY_MAX_N \
                and p['relaxation_level'] != SPF.FIXED_POLICY_LEVEL:
            v.append(f'{cid}: SEL-2 contest at level {p["relaxation_level"]}')
    return v


full = np.arange(len(cands))
rng = np.random.default_rng(1)
subs = [np.sort(rng.choice(len(cands), int(0.9 * len(cands)), replace=False)) for _ in range(5)]
rev, swapped = reversed_contests()
res = {'slate': f'{sd}/{scen_name}', 'overlap_policy': os.environ['NFL_SHOWDOWN_OVERLAP_POLICY'],
       'inputs': {'export': sha(export), 'draws': sha(draws_p), 'candidates': sha(cand_p)},
       'n_candidates': len(cands), 'n_worlds': nw, 'contests': {c: len(v['entries']) for c, v in contests.items()},
       'order_reversed_contests': swapped}
for sel in SELS:
    P, sec = build(sel, full, contests)
    r = {'full': score(P, full, H), 'full_S': score(P, full, S), 'seconds': sec, 'violations': check(P, full, sel, contests),
         'chosen_full': {c: sorted(map(int, p['chosen'])) for c, p in P.items()}, 'subsamples': [], 'subsamples_S': []}
    for idx in subs:
        Q, _ = build(sel, idx, contests)
        r['subsamples'].append(score(Q, idx, H)); r['subsamples_S'].append(score(Q, idx, S))
        r['violations'] += [f'subsample: {x}' for x in check(Q, idx, sel, contests)]
    if swapped:
        R, _ = build(sel, full, rev)
        r['order_reversed'] = score(R, full, H)
        r['violations'] += [f'reversed: {x}' for x in check(R, full, sel, rev)]
    res[sel] = r
# summary per contest
summ = {}
for c, n in res['contests'].items():
    key = 'objective' if SPF.FIXED_POLICY_MIN_N <= n < SPF.FIXED_POLICY_MAX_N else 'coverage'
    s = {'n': n, 'metric': key, 'confirmatory': key == 'objective'}
    for sel in SELS:
        r = res[sel]; sub = [x[c][key] for x in r['subsamples']]
        s[sel] = {'H_full': r['full'][c][key], 'level': r['full'][c]['level'], 'sub_min': min(sub), 'sub_max': max(sub),
                  'spread': round(max(sub) - min(sub), 4),
                  'order_abs_delta': (round(abs(r['order_reversed'][c][key] - r['full'][c][key]), 4) if c in swapped else None),
                  # AMENDMENT 2: compared only where full pool and subsample share the same m (the same objective)
                  'nested_violations': sum(r['full_S'][c][key] < x[c][key] - 1e-12 for x in r['subsamples_S']
                                           if x[c]['m'] == r['full_S'][c]['m'] or key == 'coverage'),
                  'nested_comparable': sum(x[c]['m'] == r['full_S'][c]['m'] or key == 'coverage' for x in r['subsamples_S']),
                  'unfillable': any(x[c]['unfillable'] for x in r['subsamples']) or r['full'][c]['unfillable']}
    if not s['confirmatory']:
        s['negative_control_identical'] = res['GREEDY']['chosen_full'][c] == res['FIXED_POLICY_V1']['chosen_full'][c]
    summ[c] = s
res['summary'] = summ
res['runtime_ratio'] = round(res['FIXED_POLICY_V1']['seconds'] / max(res['GREEDY']['seconds'], 1e-9), 3)
for sel in SELS:
    del res[sel]['chosen_full']
print(json.dumps(res, indent=1))
