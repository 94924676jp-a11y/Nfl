"""Score the cap-sensitivity research portfolios on IDENTICAL worlds (the OFFICIAL TB@DAL draws). Research only."""
import json, csv, sys, pathlib, hashlib, collections
import numpy as np
sys.path.insert(0, '/home/user/nfl')
from nfl.postgame import showdown_postgame as SP
R = pathlib.Path('/home/user/nfl'); S = R/'nfl/dfs/salaries/showdown_tb_dal'; X = pathlib.Path(sys.argv[1])
d = json.loads((S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json').read_text())
W = {k.rsplit('|', 1)[0]: np.asarray(v, float) for k, v in d['draws'].items()}
st = json.loads((S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_STATE.json').read_text()); nk = SP._name_key(st)
pg = json.loads((R/'nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json').read_text())
act = {k: float(v['dk_A']) for k, v in pg['player_actuals'].items()}
cands = list(csv.DictReader(open(S/'OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_CANDIDATES.csv')))
def score(L): return np.stack([1.5*W[c] + sum(W[f] for f in fl) for c, fl in L])
U = [(c['captain'], [x.strip() for x in c['flex'].split(' / ')]) for c in cands]
opt = score(U).max(0)                                   # best candidate per world (same pool for every arm)
r1_sha = hashlib.sha256((S/'OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_DK_UPLOAD.csv').read_bytes()).hexdigest()
out = {}
for arm in ('0.40', '0.50', '0.60', '1.00'):
    D = X/f'cap_{arm}'
    up = D/'SHOWDOWN_TB_DAL_DK_UPLOAD.csv'
    if not up.exists():
        out[arm] = {'STATUS': 'NOT_BUILT', 'log_tail': (X/f'log_{arm}.txt').read_text()[-300:]}; continue
    L = SP.lineups_from_final(D/'SHOWDOWN_TB_DAL_FINAL_LINEUPS.csv')
    aud = json.loads(next(D.glob('*_AUDIT.json')).read_text())
    o = {'upload_sha256': hashlib.sha256(up.read_bytes()).hexdigest()[:16],
         'identical_to_entered_R1': hashlib.sha256(up.read_bytes()).hexdigest() == r1_sha}
    for cid, lab, m in (('196438543', '150max', 1), ('196438555', '20max', 2)):
        LL = [(c, f) for x, _, c, f in L if x == cid]
        M = score(LL); hit = M >= 0.9*opt; best = M.max(0)
        expo = collections.Counter(p for c, f in LL for p in (c, *f)); cap = collections.Counter(c for c, f in LL)
        n = len(LL); sh = np.array([v/n for v in expo.values()])
        A = np.array([SP.score_lineup(c, f, act, nk) for c, f in LL])
        P = aud['portfolios'][cid]
        o[lab] = {'n': n, 'relaxation_level': P['relaxation_level'], 'final_caps': P['relaxation_log'][-1]['caps'],
                  'objective_E_min_hits_m': round(float(np.minimum(hit.sum(0), m).mean()), 4),
                  'proxy_coverage_any': round(float((hit.sum(0) >= 1).mean()), 4),
                  'best_per_world_mean': round(float(best.mean()), 2), 'best_per_world_p10': round(float(np.percentile(best, 10)), 1),
                  'mean_lineup': round(float(M.mean()), 2), 'portfolio_mean_p10_world': round(float(np.percentile(M.mean(0), 10)), 2),
                  'max_player_exposure': round(float(sh.max()), 3), 'top3_exposures': [(p, round(v/n, 2)) for p, v in expo.most_common(3)],
                  'exposure_hhi': round(float((sh**2).sum()), 3), 'distinct_captains': len(cap),
                  'top_captain_share': round(cap.most_common(1)[0][1]/n, 3), 'mean_pairwise_shared': round(float(np.mean(
                      [len({a[0], *a[1]} & {b[0], *b[1]}) for i, a in enumerate(LL) for b in LL[i+1:]])), 2),
                  'HINDSIGHT_actual_best': round(float(A.max()), 2), 'HINDSIGHT_actual_mean': round(float(A.mean()), 2)}
    out[arm] = o
(X/'CAP_SENSITIVITY_TB_DAL.json').write_text(json.dumps({'ARTIFACT': 'CAP_SENSITIVITY_RESEARCH', 'worlds': 'OFFICIAL TB@DAL draws (2,000), identical for every arm',
    'candidate_pool_for_proxy': 'corrected R1 candidates (5,387)', 'arms': out,
    'READING': 'in-simulation metrics are the objective the optimizer optimizes on our own worlds; HINDSIGHT_* is one realised game and is not evidence'}, indent=1))
print(json.dumps(out, indent=1)[:6000])
