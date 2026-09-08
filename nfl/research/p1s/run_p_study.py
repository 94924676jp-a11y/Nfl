"""P recoverability: simple baselines, ladder, cohorts."""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ('s2', 'p4c', 'p4e', 's4'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import p_lib as L, p_fit as F                                  # noqa: E402
import s2_lib as SL                                            # noqa: E402
import p4c_build as CB                                         # noqa: E402

SHRINK_GRID = (0.5, 1, 2, 3, 5, 8, 12, 20, 35, 60, 100)
LADDER = [('CONTROL_hl2', None), ('P0', None), ('P_iso', None),
          ('P_base', []), ('P_A', ['A']), ('P_B', ['B']), ('P_C', ['C']),
          ('P_D', ['D']), ('P_E', ['E']), ('P_AB', ['A', 'B']),
          ('P_ABC', ['A', 'B', 'C']), ('P_ABCD', ['A', 'B', 'C', 'D']),
          ('P_ABCDE', ['A', 'B', 'C', 'D', 'E'])]


def fit_shrink(sub, ev, basis):
    tr = [r for r in sub if r['season'] < ev and L.eligible(r)
          and r.get(basis) is not None and r.get('q_pos_mean') is not None]
    if len(tr) < 500:
        return 5.0
    best, bk = None, SHRINK_GRID[0]
    for k in SHRINK_GRID:
        e = sum(((r['p_n'] * r[basis] + k * r['q_pos_mean'])
                 / (r['p_n'] + k) - r[L.TARGET]) ** 2 for r in tr)
        if best is None or e < best:
            best, bk = e, k
    return bk


def role_persist(sub, ev):
    """Role-transition-conditioned persistence: a separate multiplicative
    correction per transition state, fitted on prior seasons only."""
    num = collections.defaultdict(float)
    den = collections.defaultdict(float)
    for r in sub:
        if r['season'] >= ev or not L.eligible(r):
            continue
        b = r.get('p_ewma2')
        if b is None or b <= 1e-9:
            continue
        num[r['p_role']] += r[L.TARGET]
        den[r['p_role']] += b
    return {k: (num[k] / den[k] if den[k] > 0 else 1.0) for k in den}


def main():
    t0 = time.time()
    rows, sub = L.load()
    pa = CB.appearance(rows)
    L.attach(sub, pa)
    OUT = {'note': 'P is PASS-SNAP PARTICIPATION, an upper bound on route '
                   'participation, not routes run'}
    K, RP, ISO = {}, {}, {}
    for ev in L.EVAL:
        K[ev] = fit_shrink(sub, ev, 'p_ewma2')
        RP[ev] = role_persist(sub, ev)
        ISO[ev] = F.fit_isotonic(sub, ev, lambda r: SL.predict('ewma_hl2', r))
    OUT['shrinkage_k'] = {str(e): K[e] for e in L.EVAL}
    OUT['role_persistence_factors'] = {str(e): RP[e] for e in L.EVAL}
    print('== fitted on prior seasons only ==')
    for ev in L.EVAL:
        print(f'  {ev}: EB k={K[ev]}  role factors ' +
              ' '.join(f'{k}={v:.4f}' for k, v in sorted(RP[ev].items())))

    def simple(name, r, ev):
        if name == 'pos_mean':
            return r.get('q_pos_mean')
        if name == 'last_obs':
            return r.get('p_last')
        if name == 'expanding':
            return r.get('p_expanding')
        if name.startswith('ewma_hl'):
            return r.get('p_ewma' + name[7:])
        if name == 'prev_season':
            return r.get('p_prev_season')
        if name == 'career_prior':
            return r.get('p_expanding')
        if name == 'eb_shrink':
            b, pr = r.get('p_ewma2'), r.get('q_pos_mean')
            if pr is None:
                return None
            if b is None:
                return pr
            return (r['p_n'] * b + K[ev] * pr) / (r['p_n'] + K[ev])
        if name == 'role_persist':
            b = r.get('p_ewma2')
            if b is None:
                return r.get('q_pos_mean')
            return b * RP[ev].get(r.get('p_role') or 'stable', 1.0)
        raise ValueError(name)

    SIMPLE = ['pos_mean', 'last_obs', 'expanding', 'ewma_hl1', 'ewma_hl2',
              'ewma_hl3', 'ewma_hl5', 'ewma_hl8', 'eb_shrink', 'prev_season',
              'career_prior', 'role_persist']
    pool = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    per = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    for ev in L.EVAL:
        for r in sub:
            if not L.eligible(r, ev):
                continue
            y = float(r[L.TARGET])
            for nm in SIMPLE:
                v = simple(nm, r, ev)
                if v is None:
                    v = r.get('q_pos_mean')
                if v is None:
                    continue
                v = float(min(max(v, 0.0), 1.0))
                pool[nm][r['position']][0].append(v)
                pool[nm][r['position']][1].append(y)
                pool[nm]['ALL'][0].append(v)
                pool[nm]['ALL'][1].append(y)
                per[nm][ev][0].append(v)
                per[nm][ev][1].append(y)
    print('\n== simple baselines (control = ewma_hl2) ==')
    OUT['simple'] = {}
    for pos in ('ALL', 'WR', 'TE', 'RB'):
        print(f'\n  --- {pos} ---')
        print(f"    {'method':14s} {'MAE':>7s} {'RMSE':>7s} {'r':>7s} {'R2':>7s} "
              f"{'sdrat':>7s} {'bias':>8s}  vs control")
        ctrl = L.metrics(*pool['ewma_hl2'][pos])['mae']
        for nm in SIMPLE:
            m = L.metrics(*pool[nm][pos])
            OUT['simple'].setdefault(pos, {})[nm] = m
            print(f"    {nm:14s} {m['mae']:7.4f} {m['rmse']:7.4f} "
                  f"{m['r']:7.3f} {m['r2']:7.3f} {m['sd_ratio']:7.3f} "
                  f"{m['bias']:+8.4f}  {100*(ctrl-m['mae'])/ctrl:+6.2f}%")
    best_simple = min(SIMPLE, key=lambda n: L.metrics(*pool[n]['ALL'])['mae'])
    OUT['best_simple'] = best_simple
    print(f'\n  best simple: {best_simple}')

    # ---- ladder ----------------------------------------------------------
    print('\n== ladder ==')
    rowpred = collections.defaultdict(dict)
    lp = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    lper = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    OUT['fits'] = {}
    for ev in L.EVAL:
        te = [r for r in sub if L.eligible(r, ev)]
        y = np.array([float(r[L.TARGET]) for r in te])
        for name, blocks in LADDER:
            if name == 'CONTROL_hl2':
                p = np.array([SL.predict('ewma_hl2', r) for r in te], float)
            elif name == 'P0':
                p = np.array([simple(best_simple, r, ev) or
                              r.get('q_pos_mean') for r in te], float)
            elif name == 'P_iso':
                p = np.array([F.apply_isotonic(
                    ISO[ev], SL.predict('ewma_hl2', r)) for r in te], float)
            else:
                fit, fd = F.fit_rung(sub, ev, blocks, pa)
                p = F.predict_rung(fit, te, blocks, pa)
                OUT['fits'].setdefault(name, {})[str(ev)] = {
                    k: v for k, v in fd.items() if k != 'features'}
                if ev == L.EVAL[0]:
                    OUT['fits'][name]['features'] = fd['features']
            p = np.clip(p, 0.0, 1.0)
            rowpred[ev][name] = p
            lper[name][ev] = (p.tolist(), y.tolist())
            for pos in L.POS:
                m = np.array([r['position'] == pos for r in te])
                lp[name][pos][0].extend(p[m].tolist())
                lp[name][pos][1].extend(y[m].tolist())
            lp[name]['ALL'][0].extend(p.tolist())
            lp[name]['ALL'][1].extend(y.tolist())
    OUT['rung_metrics'] = {}
    for pos in ('ALL', 'WR', 'TE', 'RB'):
        print(f'\n  --- {pos} ---')
        ctrl = L.metrics(*lp['CONTROL_hl2'][pos])['mae']
        print(f"    {'rung':12s} {'MAE':>7s} {'RMSE':>7s} {'r':>7s} {'R2':>7s} "
              f"{'sdrat':>7s}  vs control")
        for name, _b in LADDER:
            m = L.metrics(*lp[name][pos])
            OUT['rung_metrics'].setdefault(pos, {})[name] = m
            print(f"    {name:12s} {m['mae']:7.4f} {m['rmse']:7.4f} "
                  f"{m['r']:7.3f} {m['r2']:7.3f} {m['sd_ratio']:7.3f}  "
                  f"{100*(ctrl-m['mae'])/ctrl:+6.2f}%")
    best = min((n for n, _b in LADDER if n != 'CONTROL_hl2'),
               key=lambda n: L.metrics(*lp[n]['ALL'])['mae'])
    OUT['best_rung'] = best
    ctrl_all = L.metrics(*lp['CONTROL_hl2']['ALL'])['mae']
    print(f'\n  best rung: {best}  '
          f'({100*(ctrl_all - L.metrics(*lp[best]["ALL"])["mae"])/ctrl_all:+.2f}% vs control)')
    seas = {}
    n_ok = 0
    for ev in L.EVAL:
        c = L.metrics(*lper['CONTROL_hl2'][ev])['mae']
        b = L.metrics(*lper[best][ev])['mae']
        rel = (c - b) / c
        seas[str(ev)] = {'control': c, 'best': b, 'relative': rel}
        n_ok += 1 if rel >= 0.05 else 0
        print(f'    {ev}: control {c:.4f}  best {b:.4f}  {100*rel:+.2f}%')
    OUT['per_season_vs_control'] = seas
    OUT['seasons_ge_5pct'] = n_ok
    pos_ok = sum(1 for pos in L.POS
                 if (L.metrics(*lp['CONTROL_hl2'][pos])['mae']
                     - L.metrics(*lp[best][pos])['mae'])
                 / L.metrics(*lp['CONTROL_hl2'][pos])['mae'] >= 0.05)
    OUT['positions_ge_5pct'] = pos_ok
    print(f'  seasons >= 5%: {n_ok}/4   positions >= 5%: {pos_ok}/3')

    # ---- cohorts ---------------------------------------------------------
    print('\n== cohorts: control vs best rung ==')
    coh = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {'c': ([], []), 'b': ([], [])}))
    for ev in L.EVAL:
        te = [r for r in sub if L.eligible(r, ev)]
        for i, r in enumerate(te):
            pa_ = pa.get(id(r))
            pe = r.get('p_ewma2')
            y = float(r[L.TARGET])
            bands = [
                ('position', r['position']),
                ('history', '<4' if r['p_n'] < 4 else '4-9' if r['p_n'] < 10
                 else '10-24' if r['p_n'] < 25 else '25+'),
                ('appearance', 'unknown' if pa_ is None else
                 '<0.25' if pa_ < .25 else '0.25-0.50' if pa_ < .50 else
                 '0.50-0.80' if pa_ < .80 else '0.80-0.95' if pa_ < .95
                 else '>=0.95'),
                ('prior_P', 'low' if (pe or 0) < 0.25 else 'medium'
                 if (pe or 0) < 0.60 else 'high'),
                ('role_transition', r.get('p_role') or 'stable'),
                ('prior_role', r.get('p_prior_role') or 'fringe'),
                ('teammate_change', r.get('p_teammate_change') or 'stable')]
            for dim, lvl in bands:
                coh[dim][lvl]['c'][0].append(float(rowpred[ev]['CONTROL_hl2'][i]))
                coh[dim][lvl]['c'][1].append(y)
                coh[dim][lvl]['b'][0].append(float(rowpred[ev][best][i]))
                coh[dim][lvl]['b'][1].append(y)
    OUT['cohorts'] = {}
    for dim, d in coh.items():
        print(f'  --- {dim} ---')
        OUT['cohorts'][dim] = {}
        for lvl, v in sorted(d.items()):
            if len(v['c'][1]) < 50:
                continue
            mc = L.metrics(*v['c']); mb = L.metrics(*v['b'])
            OUT['cohorts'][dim][lvl] = {'control': mc, 'best': mb,
                                        'relative': (mc['mae'] - mb['mae'])
                                        / mc['mae']}
            print(f"    {lvl:20s} n={mc['n']:5d}  control {mc['mae']:.4f} "
                  f"-> best {mb['mae']:.4f}  "
                  f"{100*(mc['mae']-mb['mae'])/mc['mae']:+6.2f}%  "
                  f"bias {mc['bias']:+.4f} -> {mb['bias']:+.4f}")
    json.dump(OUT, open(f'{HERE}/p_study.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p_study.json')


if __name__ == '__main__':
    main()
