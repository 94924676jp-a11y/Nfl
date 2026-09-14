"""WS08 receiving-error decomposition. READ-ONLY over sealed boards + pbp."""
from __future__ import annotations
import json, os, sys, pathlib, collections
import numpy as np

REPO = pathlib.Path('/home/user/nfl')
sys.path.insert(0, str(REPO))
from nfl.research.shadow import actuals as AC

PBP = REPO / 'nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz'
RUNS = [
    ('2026_01_ATL_PIT', 'pre_inactives_V1_CANDIDATE_R8',  'f67d72ab0701d211'),
    ('2026_01_BAL_IND', 'pre_inactives_V1_CANDIDATE_R8',  'bee85f326a3fde5c'),
    ('2026_01_NO_DET',  'post_inactives_V1_CANDIDATE_R8', 'b5b02f6365ead28f'),
    ('2026_01_TB_CIN',  'post_inactives_V1_CANDIDATE_R8', 'e92b9e19466d27bd'),
    ('2026_01_SF_LA',   'post_inactives_V1_CANDIDATE_R8', '5e70d8847e32c7ae'),
]
RNG = np.random.default_rng(20260914)


def crps(draws, y):
    d = np.sort(np.asarray(draws, float)); n = d.size
    t1 = float(np.mean(np.abs(d - y)))
    # E|X-X'| via sorted-order identity
    i = np.arange(1, n + 1)
    t2 = 2.0 * float(np.sum((2 * i - n - 1) * d)) / (n * n)
    return t1 - 0.5 * t2


def pit(draws, y):
    d = np.asarray(draws, float)
    lo = float(np.mean(d < y)); eq = float(np.mean(d == y))
    return lo + RNG.random() * eq


def cover(draws, y, lvl):
    a = (1 - lvl) / 2 * 100
    lo, hi = np.percentile(draws, [a, 100 - a])
    return int(lo <= y <= hi)


def load_run(game, stage, run):
    base = REPO / 'nfl/research/live' / game / stage / run
    mf = json.load(open(base / 'player_draws_manifest.json'))
    z = np.load(base / 'player_draws.npz')
    b = json.load(open(base / 'board.json'))
    ids = mf['layers']['receiving']['row_ids']
    meta = {p['gsis_id']: p for p in b['players']}
    A = {k: z['receiving__' + k] for k in
         ('targets', 'receptions', 'receiving_yards', 'receiving_td')}
    assert all(A[k].shape[0] == len(ids) for k in A), 'row mismatch'
    return mf, b, ids, meta, A, z


rows = []
game_meta = {}
for game, stage, run in RUNS:
    mf, b, ids, meta, A, z = load_run(game, stage, run)
    act = AC.receiving_rushing_actuals(AC.load(PBP, game))
    game_meta[game] = dict(stage=stage, run=run, n_draws=mf['n_draws'],
                           n_rows=len(ids), commit=b['code_commit'],
                           sha=b['draws_sha256'])
    # forecast-only target rank within team
    byteam = collections.defaultdict(list)
    for i, pid in enumerate(ids):
        byteam[meta[pid]['team']].append((float(A['targets'][i].mean()), pid))
    rank = {}
    for t, lst in byteam.items():
        for k, (_, pid) in enumerate(sorted(lst, key=lambda x: -x[0]), 1):
            rank[pid] = k
    for i, pid in enumerate(ids):
        a = act.get(pid, {})
        m = meta[pid]
        rows.append(dict(
            game=game, pid=pid, pos=m['position'], team=m['team'],
            depth=m.get('depth_chart'), rank=rank[pid],
            T=A['targets'][i].astype(float), R=A['receptions'][i].astype(float),
            Y=A['receiving_yards'][i].astype(float),
            D=A['receiving_td'][i].astype(float),
            aT=float(a.get('targets', 0)), aR=float(a.get('receptions', 0)),
            aY=float(a.get('rec_yds', 0.0)), aD=float(a.get('rec_td', 0)),
            name=a.get('name', '')))

print(f'n_rows={len(rows)} n_games={len(RUNS)}')

# ---- sanity: every actual receiver in these games is in a forecast row?
miss = []
for game, stage, run in RUNS:
    act = AC.receiving_rushing_actuals(AC.load(PBP, game))
    have = {r['pid'] for r in rows if r['game'] == game}
    for pid, a in act.items():
        if a['targets'] > 0 and pid not in have:
            miss.append((game, pid, a['name'], a['targets'], a['rec_yds']))
print(f'ACTUAL TARGETED PLAYERS WITH NO FORECAST ROW: {len(miss)}')
for x in sorted(miss, key=lambda z: -z[3])[:15]:
    print('  ', x)


def metrics(rs, key_draw, key_act):
    y = np.array([r[key_act] for r in rs], float)
    mu = np.array([r[key_draw].mean() for r in rs], float)
    med = np.array([np.median(r[key_draw]) for r in rs], float)
    cr = np.array([crps(r[key_draw], r[key_act]) for r in rs])
    pi = np.array([pit(r[key_draw], r[key_act]) for r in rs])
    out = dict(n=len(rs), mean_pred=mu.mean(), mean_act=y.mean(),
               bias=(mu - y).mean(), mae=np.abs(mu - y).mean(),
               mae_med=np.abs(med - y).mean(),
               rmse=float(np.sqrt(((mu - y) ** 2).mean())),
               crps=cr.mean(), sd_pred=mu.std(ddof=1), sd_act=y.std(ddof=1),
               r=(float(np.corrcoef(mu, y)[0, 1]) if len(rs) > 2
                  and mu.std() > 0 and y.std() > 0 else float('nan')))
    for lv in (0.5, 0.8, 0.9, 0.95):
        out[f'cov{int(lv*100)}'] = np.mean([cover(r[key_draw], r[key_act], lv)
                                            for r in rs])
    out['pit'] = pi
    out['sd_ratio'] = out['sd_pred'] / out['sd_act'] if out['sd_act'] else float('nan')
    return out


def show(tag, m):
    print(f"{tag:<26} n={m['n']:3d} pred={m['mean_pred']:7.2f} act={m['mean_act']:7.2f} "
          f"bias={m['bias']:+7.2f} MAE={m['mae']:6.2f} RMSE={m['rmse']:6.2f} "
          f"CRPS={m['crps']:6.2f} r={m['r']:+.3f} sdratio={m['sd_ratio']:.3f} "
          f"cov={m['cov50']:.2f}/{m['cov80']:.2f}/{m['cov90']:.2f}/{m['cov95']:.2f}")


print('\n=== MARGINAL FORECAST QUALITY (5 games, prospective) ===')
for nm, kd, ka in (('targets', 'T', 'aT'), ('receptions', 'R', 'aR'),
                   ('rec_yds', 'Y', 'aY'), ('rec_td', 'D', 'aD')):
    show(nm, metrics(rows, kd, ka))

np.save('/tmp/ws08_rows.npy', np.array([0]))
import pickle
pickle.dump(rows, open('/tmp/ws08_rows.pkl', 'wb'))
