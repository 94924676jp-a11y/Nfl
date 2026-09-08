"""Stage 2: participation representation, prior-only features, and baselines.

The estimand is `s_pass_snaps` -- the player's share of his team's dropbacks on
which he was on the field -- conditional on appearance. It is an UPPER BOUND on
route participation, because a player on the field for a dropback may block. It
is never called routes run.
"""
import bisect, collections, math, os, sys
import numpy as np

S = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
for p in (f'{S}/p4e', f'{S}/p4c', f'{S}/p3', f'{S}/p2', f'{S}/p1'):
    sys.path.insert(0, p)
import p4c_build as CB                                         # noqa: E402

POS = ('WR', 'TE', 'RB')
EVAL = [2022, 2023, 2024, 2025]
TARGET = 's_pass_snaps'
HALFLIVES = (2.0, 3.0, 5.0)
ROLE_STEP = 0.15


def load():
    rows = CB.load_panel()
    sub = [r for r in rows if r.get('position') in POS]
    sub.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    return rows, sub


def ewma(vals, hl):
    lam = 0.5 ** (1.0 / hl)
    num = den = 0.0
    w = 1.0
    for v in reversed(vals):
        num += w * v
        den += w
        w *= lam
    return num / den if den > 0 else None


def attach(sub):
    """Prior-only participation history. Strictly earlier ORDINALS, the same
    prefix cut P4E needed: 343 player-ordinal pairs in this panel carry two
    rows because a player changed team mid-week, and 'everything appended so
    far' would let the second read the first."""
    hist = collections.defaultdict(list)
    hist_ord = collections.defaultdict(list)
    # league-and-position running mean, from strictly earlier ordinals only
    pos_sum = collections.defaultdict(float)
    pos_n = collections.defaultdict(int)
    pending = collections.defaultdict(list)
    last_ord = None
    for r in sub:
        if last_ord is not None and r['ord'] != last_ord:
            for p_, vals in pending.items():
                for v in vals:
                    pos_sum[p_] += v
                    pos_n[p_] += 1
            pending.clear()
        last_ord = r['ord']
        pid = r['gsis_id']
        k = bisect.bisect_left(hist_ord[pid], r['ord'])
        past = hist[pid][:k]
        app = [x for x in past if x['appeared'] and x.get(TARGET) is not None]
        vals = [x[TARGET] for x in app]
        r['q_n_prior_app'] = len(app)
        r['q_last'] = vals[-1] if vals else None
        for hl in HALFLIVES:
            r[f'q_ewma{hl:g}'] = ewma(vals, hl) if vals else None
        r['q_expanding'] = float(np.mean(vals)) if vals else None
        pv = [x[TARGET] for x in app if x['season'] == r['season'] - 1]
        r['q_prev_season'] = float(np.mean(pv)) if pv else None
        r['q_pos_mean'] = (pos_sum[r['position']] / pos_n[r['position']]
                           if pos_n[r['position']] else None)
        r['q_sd'] = float(np.std(vals[-8:])) if len(vals) >= 3 else None
        # role change, from prior games only
        if len(vals) >= 4:
            r['q_step'] = float(np.mean(vals[-2:]) - np.mean(vals[-4:-2]))
        else:
            r['q_step'] = None
        r['q_role_change'] = (1.0 if (r['q_step'] is not None
                                      and abs(r['q_step']) >= ROLE_STEP) else 0.0)
        r['q_snap_prior'] = (float(np.mean([x['s_snaps'] for x in app[-8:]
                                            if x.get('s_snaps') is not None]))
                             if any(x.get('s_snaps') is not None for x in app[-8:])
                             else None)
        hist[pid].append(r)
        hist_ord[pid].append(r['ord'])
        if r['appeared'] and r.get(TARGET) is not None:
            pending[r['position']].append(r[TARGET])
    return sub


# ---- baselines, all prior-only -------------------------------------------
BASELINES = {
    'position_mean': lambda r: r['q_pos_mean'],
    'last_observation': lambda r: r['q_last'],
    'ewma_hl2': lambda r: r['q_ewma2'],
    'ewma_hl3': lambda r: r['q_ewma3'],
    'ewma_hl5': lambda r: r['q_ewma5'],
    'expanding_mean': lambda r: r['q_expanding'],
    'prev_season_mean': lambda r: r['q_prev_season'],
}


def predict(name, r):
    v = BASELINES[name](r)
    if v is None:
        v = r['q_pos_mean']          # declared fallback, never a silent zero
    return None if v is None else float(min(max(v, 0.0), 1.0))


def eligible(r, ev=None):
    if ev is not None and r['season'] != ev:
        return False
    return (r['appeared'] and r.get(TARGET) is not None
            and (r.get('q_n_prior_app') or 0) >= 1
            and r.get('q_pos_mean') is not None)


def metrics(pred, real):
    p = np.asarray(pred, float)
    y = np.asarray(real, float)
    e = p - y
    sst = ((y - y.mean()) ** 2).sum()
    return {'n': int(len(y)), 'mae': float(np.abs(e).mean()),
            'rmse': float(math.sqrt((e * e).mean())), 'bias': float(e.mean()),
            'r': (float(np.corrcoef(p, y)[0, 1]) if p.std() > 1e-12
                  and y.std() > 1e-12 else None),
            'r2': float(1 - (e * e).sum() / sst) if sst > 0 else None,
            'sd_pred': float(p.std(ddof=1)) if len(p) > 1 else None,
            'sd_actual': float(y.std(ddof=1)) if len(y) > 1 else None,
            'sd_ratio': (float(p.std(ddof=1) / y.std(ddof=1))
                         if len(y) > 1 and y.std(ddof=1) > 1e-12 else None),
            'mean_real': float(y.mean()), 'mean_pred': float(p.mean())}


def cohort_of(r, dim):
    if dim == 'prior_appeared_games':
        n = r.get('q_n_prior_app') or 0
        return '<4' if n < 4 else '4-9' if n < 10 else '10-24' if n < 25 else '25+'
    if dim == 'appearance_probability':
        return None            # filled by the runner, which holds p_app
    if dim == 'role':
        return 'role_change' if r.get('q_role_change') else 'stable'
    raise ValueError(dim)
