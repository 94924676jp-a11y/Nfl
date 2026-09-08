"""Baseline identity gate, chronology masking, and the residual anatomy."""
import collections, copy, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ('s2', 'p4c', 'p4e', 's4'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
sys.path.insert(0, '/home/user/nfl/sportsplatform')
import p_lib as L                                              # noqa: E402
import s2_lib as SL                                            # noqa: E402
import p4c_build as CB                                         # noqa: E402
from governance import artifact_reference as AR                # noqa: E402
from governance.outcome import State                           # noqa: E402

S2_RESULTS = os.path.abspath(os.path.join(HERE, '..', '..',
                                          'nfl/research/s2/s2_results.json'))
if not os.path.exists(S2_RESULTS):
    S2_RESULTS = '/home/user/nfl/nfl/research/s2/s2_results.json'
OUTCOME_FIELDS = ('s_pass_snaps', 'y_pass_snaps', 'pass_snaps', 's_snaps',
                  'y_snaps', 'offense_snaps', 'offense_pct', 'appeared',
                  'did_not_appear', 's_targets', 'y_targets', 'targets',
                  'target_share', 'rpr')


def main():
    t0 = time.time()
    rows, sub = L.load()
    pa = CB.appearance(rows)
    L.attach(sub, pa)
    OUT = {'estimand': 'P = pass snaps / team dropbacks, conditional on '
                       'appearance; PASS-SNAP PARTICIPATION, an UPPER BOUND '
                       'on route participation, not routes run'}

    # ---- 1. baseline identity, Rule 006, tolerance 0.0 -------------------
    print('== baseline identity: Stage 2 EWMA half-life 2, tolerance 0.0 ==')
    per = collections.defaultdict(lambda: ([], []))
    for ev in L.EVAL:
        for r in sub:
            if not L.eligible(r, ev):
                continue
            p = SL.predict('ewma_hl2', r)
            if p is None:
                continue
            per[r['position']][0].append(p)
            per[r['position']][1].append(float(r[L.TARGET]))
    gate = {}
    ok = True
    for pos in ('WR', 'TE', 'RB'):
        m = L.metrics(*per[pos])
        for k in ('mae', 'rmse', 'r', 'r2', 'sd_ratio'):
            o = AR.assert_gate(m[k], S2_RESULTS,
                               ('by_season', pos, 'ewma_hl2', 'pooled', k),
                               tolerance=0.0, code='P_BASELINE')
            gate[f'{pos}/{k}'] = o.as_dict()
            if o.state is not State.PASS:
                ok = False
        print(f"  {pos}: MAE {m['mae']:.6f}  r {m['r']:.6f}  R2 {m['r2']:.6f}  "
              f"sdratio {m['sd_ratio']:.6f}  -> "
              f"{'PASS' if all(gate[f'{pos}/{k}']['state']=='PASS' for k in ('mae','rmse','r','r2','sd_ratio')) else 'FAIL'}")
    OUT['baseline_gate'] = gate
    OUT['baseline_gate_sha256'] = list(gate.values())[0]['evidence'].get('sha256')
    print(f"  artifact sha256 {str(OUT['baseline_gate_sha256'])[:12]}  "
          f"-> {'ALL PASS at |diff| 0.0' if ok else 'FAILED'}")
    if not ok:
        print('\nSTOP: REPRODUCIBILITY_BLOCKED')
        json.dump(OUT, open(f'{HERE}/p_gate.json', 'w'), indent=1)
        sys.exit(2)

    # ---- 2. chronology masking ------------------------------------------
    print('\n== chronology masking audit ==')
    PF = sorted({k for r in sub for k in r if k.startswith('p_')})
    ords = sorted({r['ord'] for r in sub})
    probes = [ords[len(ords) // 4], ords[len(ords) // 2],
              ords[3 * len(ords) // 4], ords[-3]]
    allbad = collections.Counter()
    OUT['masking'] = {}
    for k in probes:
        masked = copy.deepcopy(sub)
        nb = 0
        for r in masked:
            if r['ord'] >= k:
                for f in OUTCOME_FIELDS:
                    if f not in r:
                        continue
                    if f in ('appeared', 'did_not_appear'):
                        r[f] = 0
                    elif f.startswith('s_') or f in ('offense_pct', 'rpr',
                                                     'target_share'):
                        r[f] = None
                    else:
                        r[f] = 0
                nb += 1
            for g in [g for g in r if g.startswith(('p_', 'q_'))]:
                del r[g]
        SL.attach(masked)
        L.attach(masked, pa)
        mm = {(r['team'], r['gsis_id']): r for r in masked if r['ord'] == k}
        bad = collections.Counter()
        n_cmp = 0
        for r in [x for x in sub if x['ord'] == k]:
            m = mm.get((r['team'], r['gsis_id']))
            if m is None:
                continue
            for f in PF:
                a, b = r.get(f), m.get(f)
                n_cmp += 1
                if a is None and b is None:
                    continue
                if isinstance(a, str) or isinstance(b, str):
                    if a != b:
                        bad[f] += 1
                    continue
                if a is None or b is None or abs(float(a) - float(b)) > 1e-12:
                    bad[f] += 1
        allbad.update(bad)
        OUT['masking'][str(k)] = {'rows_blanked': nb, 'values_compared': n_cmp,
                                  'leaking': dict(bad)}
        print(f'  ord >= {k}: {nb} blanked, {n_cmp} compared, '
              f'{"CLEAN" if not bad else "LEAKING " + str(dict(bad))}')
    OUT['chronology'] = 'PASS' if not allbad else f'FAIL {dict(allbad)}'
    print(f'  verdict: {OUT["chronology"]}')
    if allbad:
        print('\nSTOP: P_DATA_BLOCKED')
        json.dump(OUT, open(f'{HERE}/p_gate.json', 'w'), indent=1)
        sys.exit(2)

    # ---- 3. residual anatomy of the ACCEPTED baseline --------------------
    print('\n== residual anatomy of the accepted control ==')
    recs = []
    for ev in L.EVAL:
        for r in sub:
            if not L.eligible(r, ev):
                continue
            p = SL.predict('ewma_hl2', r)
            if p is None:
                continue
            y = float(r[L.TARGET])
            recs.append({'ev': ev, 'r': r, 'p': p, 'y': y, 'e': p - y,
                         'pa': pa.get(id(r))})
    OUT['n_eval'] = len(recs)
    byseason = {}
    for ev in L.EVAL:
        g = [x for x in recs if x['ev'] == ev]
        byseason[str(ev)] = L.metrics([x['p'] for x in g], [x['y'] for x in g])
    OUT['control_per_season'] = byseason
    print(f"  {'season':8s} {'n':>6s} {'MAE':>7s} {'RMSE':>7s} {'r':>7s} "
          f"{'R2':>7s} {'sdrat':>7s} {'bias':>8s}")
    for ev in L.EVAL:
        m = byseason[str(ev)]
        print(f"  {ev:<8} {m['n']:6d} {m['mae']:7.4f} {m['rmse']:7.4f} "
              f"{m['r']:7.3f} {m['r2']:7.3f} {m['sd_ratio']:7.3f} "
              f"{m['bias']:+8.4f}")

    def cohort_of(x):
        r = x['r']
        pe = r.get('p_ewma2')
        pa_ = x['pa']
        return {
            'position': r['position'],
            'history': ('<4' if r['p_n'] < 4 else '4-9' if r['p_n'] < 10
                        else '10-24' if r['p_n'] < 25 else '25+'),
            'appearance': ('unknown' if pa_ is None else
                           '<0.25' if pa_ < .25 else '0.25-0.50' if pa_ < .50
                           else '0.50-0.80' if pa_ < .80 else '0.80-0.95'
                           if pa_ < .95 else '>=0.95'),
            'prior_P': ('low' if (pe or 0) < 0.25 else 'medium'
                        if (pe or 0) < 0.60 else 'high'),
            'role_transition': r.get('p_role') or 'stable',
            'prior_role': r.get('p_prior_role') or 'fringe',
            'teammate_change': r.get('p_teammate_change') or 'stable'}

    coh = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    for x in recs:
        for dim, lvl in cohort_of(x).items():
            coh[dim][lvl][0].append(x['p'])
            coh[dim][lvl][1].append(x['y'])
    OUT['control_cohorts'] = {}
    for dim, d in coh.items():
        print(f'  --- {dim} ---')
        OUT['control_cohorts'][dim] = {}
        for lvl, (p, y) in sorted(d.items()):
            if len(y) < 50:
                continue
            m = L.metrics(p, y)
            OUT['control_cohorts'][dim][lvl] = m
            print(f"    {lvl:20s} n={m['n']:5d} MAE {m['mae']:.4f} "
                  f"r {(m['r'] or float('nan')):+.3f} R2 {m['r2']:+.3f} "
                  f"bias {m['bias']:+.4f} real {m['mean_real']:.3f}")

    # residual structure
    print('\n  residual structure (correlation of |error| and signed error)')
    struct = {}
    for name, fn in (
            ('prior_P', lambda x: x['r'].get('p_ewma2')),
            ('recent_P_change', lambda x: x['r'].get('p_step')),
            ('history_length', lambda x: float(x['r']['p_n'])),
            ('teammate_role_change', lambda x: x['r'].get('p_mate_step')),
            ('appearance_probability', lambda x: x['pa']),
            ('P_variance', lambda x: x['r'].get('p_var'))):
        v = np.array([fn(x) if fn(x) is not None else np.nan for x in recs])
        e = np.array([x['e'] for x in recs])
        m = np.isfinite(v) & np.isfinite(e)
        if m.sum() < 100:
            continue
        struct[name] = {
            'n': int(m.sum()),
            'corr_signed': float(np.corrcoef(v[m], e[m])[0, 1]),
            'corr_abs': float(np.corrcoef(v[m], np.abs(e[m]))[0, 1])}
        print(f"    {name:24s} n={struct[name]['n']:6d}  "
              f"corr(signed) {struct[name]['corr_signed']:+.4f}  "
              f"corr(|e|) {struct[name]['corr_abs']:+.4f}")
    # residual autocorrelation, per player
    byp = collections.defaultdict(list)
    for x in recs:
        byp[x['r']['gsis_id']].append((x['r']['ord'], x['e']))
    a, b = [], []
    for pid, seq in byp.items():
        seq.sort()
        for i in range(1, len(seq)):
            a.append(seq[i - 1][1])
            b.append(seq[i][1])
    struct['residual_autocorrelation_lag1'] = {
        'n': len(a), 'corr': float(np.corrcoef(a, b)[0, 1])}
    print(f"    {'residual autocorr lag-1':24s} n={len(a):6d}  "
          f"corr {struct['residual_autocorrelation_lag1']['corr']:+.4f}")
    for lbl, key in (('player', lambda x: x['r']['gsis_id']),
                     ('team', lambda x: x['r']['team']),
                     ('week', lambda x: x['r']['week'])):
        g = collections.defaultdict(list)
        for x in recs:
            g[key(x)].append(x['e'])
        means = [float(np.mean(v)) for v in g.values() if len(v) >= 5]
        struct[f'residual_by_{lbl}'] = {
            'n_groups': len(means), 'sd_of_group_means': float(np.std(means)),
            'overall_residual_sd': float(np.std([x['e'] for x in recs]))}
        print(f"    residual by {lbl:12s} {len(means):5d} groups, "
              f"sd of group means {np.std(means):.4f} against overall "
              f"residual sd {np.std([x['e'] for x in recs]):.4f}")
    OUT['residual_structure'] = struct
    json.dump(OUT, open(f'{HERE}/p_gate.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p_gate.json')


if __name__ == '__main__':
    main()
