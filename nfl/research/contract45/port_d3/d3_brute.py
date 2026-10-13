"""PORT-D3 (PREREG_PORT_D3_CANDIDATE_RECALL.md @b1945cd5): enumerate the legal universe U on the frozen primary worlds,
persistence h(L) per lineup, and the exact world optimum on the primary AND independent panels (brute force), checked
against the production solver. Run in the corrected overlay (cwd = merged view). Writes /tmp/claude-0/mnf_post/d3_universe.npz"""
import itertools, json, sys, time
import numpy as np
sys.path.insert(0, '.')
from nfl.tools import showdown_portfolio as SPF, showdown_to_portfolio as S
t0 = time.time()
B = 'nfl/dfs/salaries/showdown_buf_lar'
E = 'nfl/dfs/salaries/raw/showdown_buf_lar_2026W5/DKEntries_BUF_LAR_SHOWDOWN_2026W5.81b504dbc36395c4.csv'
scen = json.load(open(f'{B}/FINAL_CV1/SCENARIO.json'))
Lp = SPF.load(E, f'{B}/FINAL_CV1/SHOWDOWN_BUF_LAR_2026W5_DRAWS.json', scen['absent_in_state']); assert Lp.state.value == 'PASS'
Li = SPF.load(E, f'{B}/SHADOW_S1SEED_FINAL_CV1/SHOWDOWN_BUF_LAR_2026W5_DRAWS.json', scen['absent_in_state']); assert Li.state.value == 'PASS'
V = Lp.value
rows = SPF.players_table(V['slate'], V['absent'], V['draws'])
el = [r for r in rows if not r['absent'] and r['has_draws']]
keys = [r['key'] for r in el]
n = len(keys)
sal = np.array([r['salary'] for r in el]); csal = np.array([r['cpt_salary'] for r in el])
team = np.array([r['team'] for r in el]); t0id = (team == team[0]).astype(np.int8)
Dp = np.stack([np.asarray(V['draws'][k], np.float32) for k in keys])
Di = np.stack([np.asarray(Li.value['draws'][k], np.float32) for k in keys])
nw = Dp.shape[1]
OPT = SPF.world_optimum(rows); assert OPT.state.value == 'PASS'
opt_solver = np.asarray(OPT.value['opt'], np.float32)
thr = (1 - S.NEAR_OPTIMAL_LOSS_BAND) * opt_solver
combos = np.array(list(itertools.combinations(range(n), 5)), dtype=np.int16)
csum_sal = sal[combos].sum(axis=1); cteam = t0id[combos].sum(axis=1)
L_all, H, MEAN = [], [], []
bmax_p = np.full(nw, -1e9, np.float32); bmax_i = np.full(nw, -1e9, np.float32)
for c in range(n):
    ok = ~(combos == c).any(axis=1) & (csum_sal + csal[c] <= S.SALARY_CAP)
    tc = cteam + t0id[c]
    ok &= (tc >= 1) & (tc <= 5)                    # both clubs among the six
    idx = combos[ok]
    for s in range(0, len(idx), 20000):
        ch = idx[s:s + 20000]
        sp = 1.5 * Dp[c][None, :] + Dp[ch[:, 0]] + Dp[ch[:, 1]] + Dp[ch[:, 2]] + Dp[ch[:, 3]] + Dp[ch[:, 4]]
        si = 1.5 * Di[c][None, :] + Di[ch[:, 0]] + Di[ch[:, 1]] + Di[ch[:, 2]] + Di[ch[:, 3]] + Di[ch[:, 4]]
        bmax_p = np.maximum(bmax_p, sp.max(axis=0)); bmax_i = np.maximum(bmax_i, si.max(axis=0))
        H.append((sp >= thr[None, :]).sum(axis=1).astype(np.int16)); MEAN.append(sp.mean(axis=1).astype(np.float32))
        L_all.append(np.column_stack([np.full(len(ch), c, np.int16), ch]))
L_all = np.concatenate(L_all); H = np.concatenate(H); MEAN = np.concatenate(MEAN)
mism = np.abs(bmax_p - opt_solver) > 1e-3 * np.maximum(1, np.abs(opt_solver))
print(json.dumps({'n_players': n, 'universe_size': int(len(L_all)), 'seconds': round(time.time() - t0, 1),
                  'solver_vs_brute_primary_mismatch_worlds': int(mism.sum()),
                  'max_abs_diff': float(np.abs(bmax_p - opt_solver).max())}))
np.savez_compressed('/tmp/claude-0/mnf_post/d3_universe.npz', L=L_all, H=H, MEAN=MEAN, keys=np.array(keys),
                    opt_p=bmax_p, opt_i=bmax_i, opt_solver=opt_solver)
