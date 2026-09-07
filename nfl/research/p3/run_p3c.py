"""P3 §9 selective mixture, §12 information quality, §14 zero-history.

Policies and the tuning grid were fixed in predeclaration_p3.md BEFORE any of
these numbers existed. Thresholds are tuned on 2022-2023 and evaluated on
2024-2025; nothing is chosen after seeing the evaluation seasons.
"""
import collections, json, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_features as F
import stage_a as A
from run_p3a import load_enriched

HERE = os.path.dirname(os.path.abspath(__file__))
TUNE = [2022, 2023]
TEST = [2024, 2025]
TARGETS = {'snap_share': ('WR', 'TE', 'RB'), 'rpr': ('WR', 'TE', 'RB'),
           'target_share': ('WR', 'TE', 'RB'), 'carry_share': ('RB',)}
P1_INC = {'snap_share': 'lag1', 'rpr': 'lag1', 'target_share': 'ewma3',
          'carry_share': 'lag1'}
SMALL_SCALE = {'target_share', 'carry_share'}
GRID_LO = [0.05, 0.10, 0.20, 0.30]
GRID_HI = [0.70, 0.80, 0.90, 0.95]


def ewma(v, hl=3.0):
    if not v:
        return None
    lam = 0.5 ** (1 / hl); n = d = 0.0; w = 1.0
    for x in reversed(v):
        n += w * x; d += w; w *= lam
    return n / d


def mae(recs, key):
    return float(np.mean([abs(r['y'] - r[key]) for r in recs]))


def boot(recs, ka, kb, n=400, seed=20260907):
    rng = random.Random(seed)
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for r in recs:
        g = agg[r['pid']]
        g[0] += abs(r['y'] - r[ka]); g[1] += abs(r['y'] - r[kb]); g[2] += 1
    vals = list(agg.values()); m = len(vals)
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
            'hi': d[int(.975 * len(d))]}


def policies(r, target, lo, hi):
    """Every decision uses only pregame quantities. Returns dict name -> use_AC."""
    p = r['p_app']
    return {
        'P0_always_U': False,
        'P1_always_AC': True,
        'P2_info_quality': r['row']['info_quality'] == 'HIGH',
        'P3_uncertain_band': lo <= p <= hi,
        'P4_zero_persistence': bool(r['row'].get('f_prev_appeared')),
        'P5_scale': target in SMALL_SCALE,
        'P6_combined': (r['row']['info_quality'] == 'HIGH'
                        and bool(r['row'].get('f_prev_appeared'))),
    }


def main():
    rows, _ = load_enriched()
    POSALL = ('WR', 'TE', 'RB', 'QB')
    cand = [r for r in rows if r['position'] in POSALL
            and (r.get('f_n_prior') or 0) >= 1]
    for r in cand:
        r['y_app'] = 1 if r['appeared'] else 0
    ALL = set(F.FEATURE_GROUPS) - {'p2_base'}
    pa = {}
    for ev in A.EVAL:
        tr = [r for r in cand if r['season'] < ev]
        te = [r for r in cand if r['season'] == ev]
        if len(tr) < 500:
            continue
        ui = ev <= 2024
        m = A.fit_logistic([F.featurise_p3(r, ui, ALL) for r in tr],
                           [r['y_app'] for r in tr])
        for r, v in zip(te, A.predict(m, [F.featurise_p3(r, ui, ALL) for r in te])):
            pa[id(r)] = float(v)

    # ---- zero-history cohort (§14) ----------------------------------------
    zero = [r for r in rows if r['position'] in POSALL
            and (r.get('f_n_prior') or 0) == 0]
    zc = collections.Counter((r['season'], r['position']) for r in zero)
    print(f'§14 zero-history cohort: {len(zero)} player-games '
          f'({len({r["gsis_id"] for r in zero})} distinct players)')
    print('   by position:', dict(collections.Counter(r['position'] for r in zero)))
    print('   NOTE: these have no prior game in the panel and are excluded from '
          'every model here, which requires f_n_prior >= 1.')

    out = {'zero_history': {'n_player_games': len(zero),
                            'n_players': len({r['gsis_id'] for r in zero}),
                            'by_position': dict(collections.Counter(
                                r['position'] for r in zero)),
                            'by_season': {f'{k[0]}_{k[1]}': v
                                          for k, v in zc.items()}},
           'targets': {}}

    for target, positions in TARGETS.items():
        sub = [r for r in cand if r['position'] in positions]
        allh = collections.defaultdict(list); apph = collections.defaultdict(list)
        for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
            pid = r['gsis_id']
            r['_all'] = list(allh[pid]); r['_app'] = list(apph[pid])
            y = r.get(target)
            if y is not None:
                allh[pid].append(y)
                if r['appeared']:
                    apph[pid].append(y)
        recs_by_season = {}
        for ev in A.EVAL:
            tr = [r for r in sub if r['season'] < ev]
            pri = {}; pria = {}
            for p_ in positions:
                v = [r[target] for r in tr if r['position'] == p_
                     and r.get(target) is not None]
                va = [r[target] for r in tr if r['position'] == p_
                      and r.get(target) is not None and r['appeared']]
                if v:
                    pri[p_] = float(np.mean(v))
                if va:
                    pria[p_] = float(np.mean(va))
            rr = []
            for r in sub:
                if r['season'] != ev or r.get(target) is None or id(r) not in pa:
                    continue
                if r['position'] not in pri or r['position'] not in pria:
                    continue
                a, b = r['_all'], r['_app']
                u_lag1 = a[-1] if a else pri[r['position']]
                u_ewma = ewma(a) if a else pri[r['position']]
                u = u_lag1 if P1_INC[target] == 'lag1' else u_ewma
                c = ewma(b) if b else pria[r['position']]
                p_app = pa[id(r)]
                rr.append({'pid': r['gsis_id'], 'row': r, 'y': r[target],
                           'p_app': p_app, 'U': u, 'C': c, 'AC': p_app * c})
            if len(rr) >= 200:
                recs_by_season[ev] = rr
        if not recs_by_season:
            continue

        # ---- tune the P3 band on 2022-2023 ONLY ---------------------------
        tune = [x for ev in TUNE for x in recs_by_season.get(ev, [])]
        best, best_mae = None, None
        grid = {}
        for lo in GRID_LO:
            for hi in GRID_HI:
                for x in tune:
                    x['SEL'] = x['AC'] if lo <= x['p_app'] <= hi else x['U']
                m_ = mae(tune, 'SEL')
                grid[f'{lo}-{hi}'] = m_
                if best_mae is None or m_ < best_mae:
                    best, best_mae = (lo, hi), m_
        lo, hi = best

        res = {'band_tuned_on': TUNE, 'band': [lo, hi],
                'band_tune_mae': best_mae, 'grid': grid, 'seasons': {}}
        # Apply every policy to every season first, so the CHOICE can be made
        # on the tuning seasons alone.
        for ev, rr in recs_by_season.items():
            names = None
            for x in rr:
                pol = policies(x, target, lo, hi)
                names = list(pol)
                for nme, use_ac in pol.items():
                    x[nme] = x['AC'] if use_ac else x['U']
            per = {n: mae(rr, n) for n in names}
            per['C'] = mae(rr, 'C')
            res.setdefault('_per_season_mae', {})[ev] = per
            res['seasons'][ev] = {
                'n': len(rr), 'mae': per, '_recs': rr,
            }

        # ---- CHOOSE THE POLICY ON THE TUNING SEASONS ONLY -----------------
        # The first version of this reported, for each evaluation season, the
        # policy that happened to score best ON that season. That is choosing
        # after seeing the outcome, which the directive forbids and its own
        # probe 12 tests for. The policy is now fixed on 2022-2023 and carried
        # unchanged into 2024-2025.
        cands = [n for n in ('P2_info_quality', 'P3_uncertain_band',
                             'P4_zero_persistence', 'P5_scale', 'P6_combined')]
        tune_mae = {n: float(np.mean([res['_per_season_mae'][ev][n]
                                      for ev in TUNE
                                      if ev in res['_per_season_mae']]))
                    for n in cands}
        chosen = min(tune_mae, key=tune_mae.get)
        res['policy_chosen_on_tuning'] = chosen
        res['policy_tuning_mae'] = tune_mae
        for ev, d in res['seasons'].items():
            rr = d.pop('_recs')
            d['chosen_policy'] = chosen
            # Breakdowns are computed AFTER the policy is fixed, so a cohort
            # cannot influence which policy was chosen.
            d['by_info_quality'] = {
                q: {'n': sum(1 for x in rr if x['row']['info_quality'] == q),
                    **{n: mae([x for x in rr if x['row']['info_quality'] == q], n)
                       for n in ('P0_always_U', 'P1_always_AC', chosen)}}
                for q in ('HIGH', 'MEDIUM', 'LOW')
                if sum(1 for x in rr if x['row']['info_quality'] == q) >= 60}
            d['by_cohort'] = {
                ck: {'n': sum(1 for x in rr if pred(x)),
                     **{n: mae([x for x in rr if pred(x)], n)
                        for n in ('P0_always_U', 'P1_always_AC', chosen)}}
                for ck, pred in (
                    ('role_change', lambda x: x['row'].get('role_change') == 1),
                    ('role_stable', lambda x: x['row'].get('role_change') == 0),
                    ('did_not_appear', lambda x: x['row']['appeared'] == 0),
                    ('returning', lambda x: (x['row'].get('f_consec_missed') or 0) >= 1),
                    ('low_history', lambda x: (x['row'].get('f_n_prior') or 0) < 4))
                if sum(1 for x in rr if pred(x)) >= 60}
            d['chosen_mae'] = d['mae'][chosen]
            d['vs_U'] = boot(rr, chosen, 'P0_always_U')
            d['vs_AC'] = boot(rr, chosen, 'P1_always_AC')
            d['ac_share'] = float(np.mean([1.0 if x[chosen] == x['AC'] else 0.0
                                           for x in rr]))
            d['oracle_best_this_season'] = min(cands, key=lambda n: d['mae'][n])
        out['targets'][target] = res
        print(f'\n=== {target}  band tuned on {TUNE}: [{lo}, {hi}]  '
              f'POLICY CHOSEN ON TUNING: {chosen}')
        for ev in sorted(res['seasons']):
            d = res['seasons'][ev]; p = d['mae']
            tag = 'TEST' if ev in TEST else 'tune'
            vu, va = d['vs_U'], d['vs_AC']
            oracle = d['oracle_best_this_season']
            note = '' if oracle == chosen else f'  [oracle would be {oracle}={p[oracle]:.4f}]'
            print(f' {ev}({tag}) n={d["n"]:5d} U={p["P0_always_U"]:.4f} '
                  f'AC={p["P1_always_AC"]:.4f} {chosen}={d["chosen_mae"]:.4f} '
                  f'(AC used {d["ac_share"]*100:.0f}%) '
                  f'| vsU {vu["mean"]:+.5f}[{vu["lo"]:+.5f},{vu["hi"]:+.5f}] '
                  f'vsAC {va["mean"]:+.5f}[{va["lo"]:+.5f},{va["hi"]:+.5f}]{note}')
    json.dump(out, open(f'{HERE}/p3_selective.json', 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
