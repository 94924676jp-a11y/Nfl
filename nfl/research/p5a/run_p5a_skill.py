"""P5A items 10-12: does player rushing efficiency contain reproducible
next-game information, and how hard must it be shrunk?

Three questions kept apart, because conflating them is the standard way to
report a signal that is not there:

  PERSISTENCE   does the metric correlate with ITSELF later?
  PREDICTION    does the prior estimate predict the NEXT GAME's outcome?
  INCREMENT     does it beat a POOLED PRIOR on that next game?

A metric can pass the first and fail the third. Self-correlation is not
predictive value.
"""
import collections, json, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = [2022, 2023, 2024, 2025]
METRICS = {
    'ypc':   ('ypc', 'ew_ypc', lambda c: c['yards']),
    'epa':   ('epa', 'ew_epa', lambda c: c['epa']),
    'succ':  ('succ', 'ew_succ', lambda c: float(c['success'])),
    'exp':   ('exp', 'ew_exp', lambda c: 1.0 if c['yards'] >= 10 else 0.0),
    'stuff': ('stuff', 'ew_stuff', lambda c: 1.0 if c['yards'] <= 0 else 0.0),
}
MINC = 25          # minimum prior carries for a player estimate to be quoted


def wcorr(x, y, w=None):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if w is None:
        w = np.ones(len(x))
    w = np.asarray(w, float)
    mx = np.average(x, weights=w); my = np.average(y, weights=w)
    cx = x - mx; cy = y - my
    num = np.average(cx * cy, weights=w)
    den = math.sqrt(np.average(cx * cx, weights=w) * np.average(cy * cy, weights=w))
    return float(num / den) if den > 0 else None


def main():
    D = pickle.load(open(f'{HERE}/pg.pkl', 'rb'))
    carries, pg = D['carries'], D['pg']
    OUT = {}

    # ---- 1. SEASON-TO-SEASON PERSISTENCE ---------------------------------
    seas = collections.defaultdict(lambda: collections.defaultdict(float))
    for c in carries:
        k = (c['rusher'], c['season'])
        s = seas[k]
        s['n'] += 1
        for m, (_a, _b, fn) in METRICS.items():
            s[m] += fn(c)
    pers = {}
    for m in METRICS:
        pairs = []
        for (pid, y), s in seas.items():
            t = seas.get((pid, y + 1))
            if t is None or s['n'] < 50 or t['n'] < 50:
                continue
            pairs.append((s[m] / s['n'], t[m] / t['n'], min(s['n'], t['n'])))
        if len(pairs) < 30:
            continue
        a = [p[0] for p in pairs]; b = [p[1] for p in pairs]
        pers[m] = {'n_pairs': len(pairs), 'r': wcorr(a, b),
                   'r_weighted': wcorr(a, b, [p[2] for p in pairs]),
                   'min_carries_each_season': 50}
    OUT['season_to_season_persistence'] = pers
    print('== season-to-season persistence (>=50 carries in both seasons) ==')
    for m, v in pers.items():
        print(f'  {m:6s} n={v["n_pairs"]:4d} r={v["r"]:+.4f} '
              f'r_weighted={v["r_weighted"]:+.4f}')

    # ---- 2. SPLIT-HALF PERSISTENCE (odd vs even carries, within season) ---
    half = collections.defaultdict(lambda: collections.defaultdict(float))
    cnt = collections.Counter()
    for c in carries:
        k = (c['rusher'], c['season'])
        h = cnt[k] % 2
        cnt[k] += 1
        s = half[(k, h)]
        s['n'] += 1
        for m, (_a, _b, fn) in METRICS.items():
            s[m] += fn(c)
    sh = {}
    for m in METRICS:
        a, b, w = [], [], []
        for (k, h) in list(half):
            if h != 0:
                continue
            o = half.get((k, 1))
            if o is None or half[(k, 0)]['n'] < 40 or o['n'] < 40:
                continue
            a.append(half[(k, 0)][m] / half[(k, 0)]['n'])
            b.append(o[m] / o['n']); w.append(min(half[(k, 0)]['n'], o['n']))
        if len(a) < 30:
            continue
        r = wcorr(a, b)
        sh[m] = {'n_players': len(a), 'r_half': r,
                 'spearman_brown_full': (2 * r / (1 + r)) if r is not None else None,
                 'min_carries_each_half': 40}
    OUT['split_half_persistence'] = sh
    print('\n== split-half persistence (odd/even carries, >=40 each half) ==')
    for m, v in sh.items():
        print(f'  {m:6s} n={v["n_players"]:4d} r_half={v["r_half"]:+.4f} '
              f'Spearman-Brown full-length={v["spearman_brown_full"]:+.4f}')

    # ---- 3. NEXT-GAME PREDICTION + SHRINKAGE -----------------------------
    # For evaluation season Y: pooled prior from seasons < Y; the EB constant k
    # is fitted on seasons < Y by minimising carry-weighted next-game squared
    # error. Nothing is fitted on Y.
    def eval_arm(rows, kind, k, pool):
        pred, act, w = [], [], []
        for r in rows:
            p = r['p']
            if p is None or p['n'] < 1:
                est = pool
            elif kind == 'pool':
                est = pool
            elif kind == 'raw':
                est = p['m']
            elif kind == 'ewma':
                est = p['ew'] if p['ew'] is not None else pool
            elif kind == 'eb':
                est = (p['n'] * p['m'] + k * pool) / (p['n'] + k)
            elif kind == 'eb_ewma':
                est = ((p['ew_n'] * p['ew'] + k * pool) / (p['ew_n'] + k)
                       if p['ew'] is not None else pool)
            pred.append(est); act.append(r['act']); w.append(r['carries'])
        pred = np.array(pred); act = np.array(act); w = np.array(w, float)
        return float(np.average((act - pred) ** 2, weights=w)), pred, act, w

    res = {}
    for m, (raw_k, ew_k, fn) in METRICS.items():
        res[m] = {}
        for ev in EVAL:
            def prep(seasons):
                rr = []
                for r in pg:
                    if r['season'] not in seasons or r['carries'] < 1:
                        continue
                    p = r['p']
                    pp = None
                    if p is not None and p['n'] >= 1 and p[ew_k] is not None:
                        pp = {'n': p['n'], 'm': p[raw_k], 'ew': p[ew_k],
                              'ew_n': p['ew_n']}
                    act = (r['rush_yards'] / r['carries'] if m == 'ypc' else
                           (r['n_explosive'] / r['carries'] if m == 'exp' else
                            (r['n_stuff'] / r['carries'] if m == 'stuff' else None)))
                    if act is None:
                        continue
                    rr.append({'p': pp, 'act': act, 'carries': r['carries'],
                               'row': r})
                return rr
            if m not in ('ypc', 'exp', 'stuff'):
                continue
            tr = prep(set(range(2016, ev)))
            te = prep({ev})
            if len(tr) < 500 or len(te) < 200:
                continue
            pool = float(np.average([x['act'] for x in tr],
                                    weights=[x['carries'] for x in tr]))
            grid = [0, 5, 10, 20, 40, 80, 160, 320, 640, 1280, 2560, 10240]
            kbest = min(grid, key=lambda k: eval_arm(tr, 'eb', k, pool)[0])
            kbest_ew = min(grid, key=lambda k: eval_arm(tr, 'eb_ewma', k, pool)[0])
            arms = {}
            for kind, kk in (('pool', 0), ('raw', 0), ('ewma', 0),
                             ('eb', kbest), ('eb_ewma', kbest_ew)):
                mse, pr, ac, ww = eval_arm(te, kind, kk, pool)
                arms[kind] = {'wmse': mse, 'r': wcorr(pr, ac, ww),
                              'k': kk if kind.startswith('eb') else None}
            base = arms['pool']['wmse']
            for kind in arms:
                arms[kind]['pct_vs_pool'] = 100 * (arms[kind]['wmse'] - base) / base
            res[m][ev] = {'n_eval': len(te), 'pool_prior': pool, 'arms': arms,
                          'k_eb_fitted_on_prior_seasons': kbest,
                          'k_eb_ewma': kbest_ew}
            print(f'\n  {m:6s} {ev} n={len(te):5d} pool={pool:.4f} '
                  f'k_EB={kbest} k_EB_ewma={kbest_ew}')
            for kind, a in arms.items():
                print(f'      {kind:9s} wMSE={a["wmse"]:.5f} '
                      f'({a["pct_vs_pool"]:+6.2f}% vs pool) r={(a["r"] or 0):+.4f}')
    OUT['next_game_prediction'] = res
    json.dump(OUT, open(f'{HERE}/p5a_skill.json', 'w'), indent=1)
    print('\nwrote p5a_skill.json')


if __name__ == '__main__':
    main()
