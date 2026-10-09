"""Compare the incumbent R1 TB@DAL portfolio with the portfolio rebuilt on repaired worlds; cross-evaluate both on
both world sets and on the realised actuals (one game: hindsight).
argv: repaired_pf_dir control_pf_dir out_json [hybrid_pf_dir]  (hybrid = repaired worlds with incumbent DST draws; attribution only)"""
import csv, json, sys, pathlib, collections
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[4]
SCR = pathlib.Path(__import__('os').environ['EVAL_WORK'])   # scratch work dir (intermediates); required
def _tb_actuals(work):
    """The TB@DAL postgame grading, read from the commit that added it (not on this branch)."""
    p = work / 'tbdal_post.json'
    if not p.exists():
        import subprocess
        p.write_bytes(subprocess.run(['git', 'show', 'be87cb0d:nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json'],
                                     cwd=REPO, capture_output=True, check=True).stdout)
    return p

R1 = REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL_ELIGIBILITY_FIX_R1'
REP, CTL = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
W = {'incumbent': json.loads((REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json').read_text())['draws'],
     'repaired_qb_anchor': json.loads((REPO / 'nfl/research/accounting_repair/TB_DAL_2026W5/EVENT_CONSISTENT/SHOWDOWN_TB_DAL_2026W5_DRAWS.json').read_text())['draws'],
     'repaired_receiver_anchor': json.loads((REPO / 'nfl/research/accounting_repair/TB_DAL_2026W5/EVENT_CONSISTENT_RECEIVER_ANCHOR/SHOWDOWN_TB_DAL_2026W5_DRAWS.json').read_text())['draws']}
W = {a: {k: np.asarray(v, float) for k, v in d.items()} for a, d in W.items()}
acts = json.loads((_tb_actuals(SCR)).read_text())['player_actuals']
name2key = {}
for k in list(W['incumbent']) + list(acts):
    name2key.setdefault(k.rsplit('|', 1)[0], set()).add(k)
amb = {n: v for n, v in name2key.items() if len(v) > 1}
assert not amb, amb
name2key = {n: next(iter(v)) for n, v in name2key.items()}

def read(d):
    out = []
    with open(d / 'SHOWDOWN_TB_DAL_FINAL_LINEUPS.csv', newline='') as fh:
        for r in csv.DictReader(fh):
            out.append({'contest': r['contest_id'], 'name': r['contest'], 'cpt': name2key[r['CPT']],
                        'flex': tuple(sorted(name2key[r[f'FLEX{i}']] for i in range(1, 6)))})
    return out

def score(lu, draws):
    return 1.5 * draws[lu['cpt']] + sum(draws[f] for f in lu['flex'])

def act_score(lu):
    a = lambda k: float(acts[k]['dk_A'])
    return 1.5 * a(lu['cpt']) + sum(a(f) for f in lu['flex'])

def portfolio_eval(lus, draws):
    M = np.array([score(l, draws) for l in lus])           # (L, n_worlds)
    best = M.max(0)
    return {'n_lineups': len(lus), 'mean_lineup_mean': round(float(M.mean()), 3),
            'mean_lineup_p95': round(float(np.mean(np.quantile(M, .95, axis=1))), 3),
            'mean_lineup_p99': round(float(np.mean(np.quantile(M, .99, axis=1))), 3),
            'expected_best_lineup_per_world': round(float(best.mean()), 3),
            'p90_best_lineup_per_world': round(float(np.quantile(best, .9)), 3)}

pf = {'R1_incumbent': read(R1), 'REBUILT_on_repaired_qb_anchor': read(REP)}
HYB = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else None
if HYB is not None:
    pf['DIAGNOSTIC_rebuilt_on_repaired_with_incumbent_DST'] = read(HYB)
ctl_ok = None
if (CTL / 'SHOWDOWN_TB_DAL_FINAL_LINEUPS.csv').exists():
    ctl_ok = {f: (CTL / f).read_bytes() == (R1 / f).read_bytes() for f in
              ('SHOWDOWN_TB_DAL_DK_UPLOAD.csv', 'SHOWDOWN_TB_DAL_DK_UPLOAD_196438543.csv', 'SHOWDOWN_TB_DAL_DK_UPLOAD_196438555.csv',
               'SHOWDOWN_TB_DAL_DK_UPLOAD_196438556.csv', 'SHOWDOWN_TB_DAL_FINAL_LINEUPS.csv', 'SHOWDOWN_TB_DAL_EXPOSURES.csv',
               'SHOWDOWN_TB_DAL_CPT_EXPOSURES.csv')}
res = {'ARTIFACT': 'TB_DAL_LINEUP_SELECTION_COMPARISON', 'control_rebuild_on_incumbent_draws_byte_identical_to_R1': ctl_ok, 'contests': {}}
contests = sorted({l['contest'] for l in pf['R1_incumbent']})
for c in contests + ['ALL']:
    sel = {p: [l for l in v if c == 'ALL' or l['contest'] == c] for p, v in pf.items()}
    a = collections.Counter((l['cpt'], l['flex']) for l in sel['R1_incumbent'])
    b = collections.Counter((l['cpt'], l['flex']) for l in sel['REBUILT_on_repaired_qb_anchor'])
    shared = sum((a & b).values())
    shared_h = None
    if HYB is not None:
        h = collections.Counter((l['cpt'], l['flex']) for l in sel['DIAGNOSTIC_rebuilt_on_repaired_with_incumbent_DST'])
        shared_h = {'hybrid_vs_R1': sum((a & h).values()), 'hybrid_vs_rebuilt': sum((b & h).values()),
                    'dst_exposure_hybrid': {k: round(sum(1 for l in sel['DIAGNOSTIC_rebuilt_on_repaired_with_incumbent_DST'] if k in (l['cpt'],) + l['flex']) / len(h and sel['DIAGNOSTIC_rebuilt_on_repaired_with_incumbent_DST']), 3) for k in ('Cowboys|DAL', 'Buccaneers|TB')}}
    expo = {}
    for p, v in sel.items():
        cnt = collections.Counter(); cc = collections.Counter()
        for l in v:
            cc[l['cpt']] += 1
            for k in (l['cpt'],) + l['flex']: cnt[k] += 1
        expo[p] = ({k: n / len(v) for k, n in cnt.items()}, {k: n / len(v) for k, n in cc.items()})
    players = sorted(set(expo['R1_incumbent'][0]) | set(expo['REBUILT_on_repaired_qb_anchor'][0]))
    ex = sorted(({'player': k, 'R1': round(expo['R1_incumbent'][0].get(k, 0), 3),
                  'rebuilt': round(expo['REBUILT_on_repaired_qb_anchor'][0].get(k, 0), 3),
                  'change': round(expo['REBUILT_on_repaired_qb_anchor'][0].get(k, 0) - expo['R1_incumbent'][0].get(k, 0), 3)}
                 for k in players), key=lambda r: -abs(r['change']))
    cpts = sorted(set(expo['R1_incumbent'][1]) | set(expo['REBUILT_on_repaired_qb_anchor'][1]))
    cx = sorted(({'captain': k, 'R1': round(expo['R1_incumbent'][1].get(k, 0), 3),
                  'rebuilt': round(expo['REBUILT_on_repaired_qb_anchor'][1].get(k, 0), 3),
                  'change': round(expo['REBUILT_on_repaired_qb_anchor'][1].get(k, 0) - expo['R1_incumbent'][1].get(k, 0), 3)}
                 for k in cpts), key=lambda r: -abs(r['change']))
    cross = {p: {w: portfolio_eval(v, W[w]) for w in W} for p, v in sel.items()}
    real = {p: {'best': round(max(act_score(l) for l in v), 2), 'mean': round(float(np.mean([act_score(l) for l in v])), 2),
                'median': round(float(np.median([act_score(l) for l in v])), 2)} for p, v in sel.items()}
    res['contests'][c] = {'name': sel['R1_incumbent'][0]['name'] if c != 'ALL' else 'ALL CONTESTS',
                          'n_R1': len(sel['R1_incumbent']), 'n_rebuilt': len(sel['REBUILT_on_repaired_qb_anchor']),
                          'identical_lineups_shared': shared, 'attribution_hybrid': shared_h, 'share_of_R1_kept': round(shared / len(sel['R1_incumbent']), 3),
                          'sum_abs_exposure_change_over_players': round(sum(abs(r['change']) for r in ex), 3),
                          'max_abs_player_exposure_change': ex[0] if ex else None,
                          'player_exposure_changes_top10': ex[:10], 'captain_exposure_changes_top8': cx[:8],
                          'cross_evaluation': cross, 'realised_actuals_HINDSIGHT_ONE_GAME': real}
pathlib.Path(sys.argv[3]).write_text(json.dumps(res, indent=1))
print(json.dumps({c: {k: v for k, v in r.items() if k in ('identical_lineups_shared', 'share_of_R1_kept', 'sum_abs_exposure_change_over_players')}
                  for c, r in res['contests'].items()}))
print('control identical:', ctl_ok)
