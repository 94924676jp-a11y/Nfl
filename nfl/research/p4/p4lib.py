"""P4 shared: panel loading, baselines, xPass reconstruction, metrics."""
import collections, csv, math, os, random
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = [2022, 2023, 2024, 2025]
NUM = ('plays', 'dropbacks', 'pass_att_ex_sacks', 'sacks', 'scrambles',
       'rush_att', 'designed_qb_rush', 'nonqb_rush_att', 'neutral_plays',
       'neutral_dropbacks', 'early_plays', 'early_dropbacks', 'h1_plays',
       'h1_dropbacks', 'n_pace_obs', 'rest', 'home', 'div_game')
FLT = ('pass_rate', 'neutral_pass_rate', 'early_down_pass_rate', 'sec_per_play')


def load():
    rows = []
    for r in csv.DictReader(open(f'{HERE}/team_panel.csv')):
        for k in ('season', 'week', 'ord'):
            r[k] = int(r[k])
        for k in NUM:
            r[k] = int(float(r[k] or 0))
        for k in FLT:
            r[k] = float(r[k]) if r[k] not in ('', None) else None
        rows.append(r)
    rows.sort(key=lambda x: (x['ord'], x['team']))
    return rows


def attach_history(rows, keys):
    """For each row, the list of PRIOR values of each key for that team, and for
    that team's coach. Strictly earlier (season, week)."""
    hist = collections.defaultdict(lambda: collections.defaultdict(list))
    coach_hist = collections.defaultdict(lambda: collections.defaultdict(list))
    season_prev = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        t, c = r['team'], r.get('coach') or '?'
        r['_h'] = {k: list(hist[t][k]) for k in keys}
        r['_ch'] = {k: list(coach_hist[c][k]) for k in keys}
        r['_prev_season'] = {
            k: (float(np.mean(season_prev[(t, r['season'] - 1)][k]))
                if season_prev[(t, r['season'] - 1)][k] else None)
            for k in keys}
        prev = hist[t]['_row']
        r['_prev_row'] = prev[-1] if prev else None
        for k in keys:
            v = r.get(k)
            if v is not None:
                hist[t][k].append(v)
                coach_hist[c][k].append(v)
                season_prev[(t, r['season'])][k].append(v)
        hist[t]['_row'].append(r)
    return rows


def ewma(v, hl=3.0):
    if not v:
        return None
    lam = 0.5 ** (1 / hl)
    n = d = 0.0
    w = 1.0
    for x in reversed(v):
        n += w * x
        d += w
        w *= lam
    return n / d


def baselines(r, key, league_mean, coach_prior=None):
    h = r['_h'][key]
    ch = r['_ch'][key]
    out = {
        'league_mean': league_mean,
        'team_expanding': float(np.mean(h)) if h else league_mean,
        'last_game': h[-1] if h else league_mean,
        'roll3': float(np.mean(h[-3:])) if h else league_mean,
        'roll5': float(np.mean(h[-5:])) if h else league_mean,
        'ewma': ewma(h) if h else league_mean,
        'prev_season': (r['_prev_season'][key]
                        if r['_prev_season'][key] is not None else league_mean),
        'coach_prior': (float(np.mean(ch)) if len(ch) >= 8
                        else (coach_prior if coach_prior is not None
                              else league_mean)),
    }
    return out


BASE_NAMES = ['league_mean', 'team_expanding', 'last_game', 'roll3', 'roll5',
              'ewma', 'prev_season', 'coach_prior']


def metrics(pairs):
    y = np.array([p[0] for p in pairs], float)
    p = np.array([p[1] for p in pairs], float)
    e = y - p
    ybar = y.mean()
    sst = ((y - ybar) ** 2).sum()
    # calibration slope/intercept from OLS of y on p
    if p.std() > 0:
        slope = float(np.cov(p, y, bias=True)[0, 1] / p.var())
        inter = float(y.mean() - slope * p.mean())
        r = float(np.corrcoef(y, p)[0, 1])
    else:
        slope = inter = r = float('nan')
    return {'mae': float(np.abs(e).mean()),
            'rmse': float(np.sqrt((e * e).mean())),
            'r': r, 'r2': float(1 - (e * e).sum() / sst) if sst > 0 else float('nan'),
            'bias': float(e.mean()), 'cal_slope': slope, 'cal_intercept': inter,
            'n': len(pairs)}


def team_block_boot(recs, ka, kb, n=400, seed=20260907):
    """Difference in MAE, resampling TEAMS. A team's games are not independent."""
    rng = random.Random(seed)
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for r in recs:
        g = agg[r['team']]
        g[0] += abs(r['y'] - r[ka])
        g[1] += abs(r['y'] - r[kb])
        g[2] += 1
    vals = list(agg.values())
    m = len(vals)
    if m < 5:
        return None
    d = []
    for _ in range(n):
        ea = eb = c = 0.0
        for _i in range(m):
            v = vals[rng.randrange(m)]
            ea += v[0]; eb += v[1]; c += v[2]
        if c:
            d.append(ea / c - eb / c)
    d.sort()
    return {'mean': float(np.mean(d)), 'lo': d[int(.025 * len(d))],
            'hi': d[int(.975 * len(d))], 'n_teams': m}


# ---------------------------------------------------------------------------
def fit_ridge(X, y, l2=1.0):
    X = np.asarray(X, float); y = np.asarray(y, float)
    mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1.0
    Xs = (X - mu) / sd
    Xs = np.hstack([np.ones((len(Xs), 1)), Xs])
    A = Xs.T @ Xs + l2 * np.eye(Xs.shape[1])
    A[0, 0] -= l2
    w = np.linalg.solve(A, Xs.T @ y)
    return {'w': w, 'mu': mu, 'sd': sd}


def pred_ridge(m, X):
    X = np.asarray(X, float)
    Xs = (X - m['mu']) / m['sd']
    Xs = np.hstack([np.ones((len(Xs), 1)), Xs])
    return Xs @ m['w']


def fit_logistic(X, y, l2=1.0, iters=250, lr=0.5):
    X = np.asarray(X, float); y = np.asarray(y, float)
    mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1.0
    Xs = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    w = np.zeros(Xs.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Xs @ w, -30, 30)))
        g = Xs.T @ (p - y) / len(y) + l2 * w / len(y)
        g[0] -= l2 * w[0] / len(y)
        w -= lr * g
    return {'w': w, 'mu': mu, 'sd': sd}


def pred_logistic(m, X):
    X = np.asarray(X, float)
    Xs = np.hstack([np.ones((len(X), 1)), (X - m['mu']) / m['sd']])
    return 1 / (1 + np.exp(-np.clip(Xs @ m['w'], -30, 30)))


def xpass_features(down, ydstogo, yardline, sd, gsr, h1, to):
    """Play-state design row. All observed at the snap; nothing from the outcome."""
    return [1.0 if down == d else 0.0 for d in (1, 2, 3, 4)] + [
        min(ydstogo, 25) / 25.0, yardline / 100.0,
        max(min(sd, 28), -28) / 28.0, (max(min(sd, 28), -28) / 28.0) ** 2,
        gsr / 3600.0, float(h1), min(to, 3) / 3.0,
        (min(ydstogo, 25) / 25.0) * (1.0 if down == 3 else 0.0),
        (gsr / 3600.0) * (max(min(sd, 28), -28) / 28.0),
    ]
