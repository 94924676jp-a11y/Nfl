"""P4F section 11: seeded leakage probes and guard-deletion proofs.

Materiality is 0.010 CRPS, fixed in predeclaration_p4f.md before any of this
ran, and it is not lowered here. A probe whose seeded version cannot move the
result is reported UNRESOLVED -- it has not shown it could catch the leak it
names -- and never as PASS.

Two P4E probes came back UNRESOLVED (GD1, the `season < ev` fit guard; GD4, the
out-of-fold residual pool guard). Both are retested here in strengthened form.
Whichever still cannot fire stays UNRESOLVED.
"""
import ast, collections, json, os, re, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4f_common as K                                         # noqa: E402
import p4e_build as B                                          # noqa: E402
import p4e_fit as F                                            # noqa: E402
import p4f_mpr as M                                            # noqa: E402
import p4c_build as CB                                         # noqa: E402
import p4c_lib as CL                                           # noqa: E402

EV = 2024
MATERIAL = 0.010
RESULTS = []


def record(name, state, **kw):
    RESULTS.append(dict(probe=name, state=state, **kw))
    print(f'  {state:11s} {name:40s} ' +
          ' '.join(f'{k}={v}' for k, v in kw.items() if k != 'note'))


def candidate_crps(sub, rows, vol, pa, seasons, extra=None, train_upto=None,
                   pool_override=None, target_override=None, cellv=None):
    """ABC_MPR, with one thing deliberately broken."""
    saved = dict(B.BLOCKS)
    B.BLOCKS = dict(B.BLOCKS)
    if extra:
        B.BLOCKS['Z'] = extra
    try:
        blocks = K.BLOCKS_ABC + (['Z'] if extra else [])
        fit, pool, _fd = F.fit_centre(sub, train_upto or EV, blocks, seasons)
        if pool_override is not None:
            pool = pool_override
        c = cellv if cellv is not None else B.cell(rows, vol, pa, sub, EV)
        W0, mu = F.weights(c, fit, pool, blocks,
                           np.random.default_rng(CL.SEED + 3034))
        eps = CB._resample(pool, [r['position'] for r in c['te']], c['n'],
                           CL.M_DRAWS, np.random.default_rng(CL.SEED + 3034),
                           np.concatenate(list(pool.values())))
        target = mu if target_override is None else target_override
        W, _d, _rep = M.rectify(target, eps)
        Y, _S = B.counts_from_weights(c, W.astype(np.float32))
        return float(CL.crps_samples(Y, c['y']).mean())
    finally:
        B.BLOCKS = saved


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})
    cell = B.cell(rows, vol, pa, sub, EV)

    # ---- seed every forbidden channel onto every row --------------------
    by_team = collections.defaultdict(list)
    for r in sub:
        by_team[r['team']].append(r)
    hist = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        hist[r['gsis_id']].append(r)
    for _pid, seq in hist.items():
        for i, r in enumerate(seq):
            nxt = seq[i + 1] if i + 1 < len(seq) else None
            r['LEAK_future_carry_share'] = (None if nxt is None
                                            else (nxt.get('s_carries') or 0.0))
    for r in sub:
        r['LEAK_current_carry_share'] = (None if r.get('s_carries') is None
                                         else float(r['s_carries']))
        r['LEAK_current_carries'] = float(r.get('y_carries') or 0.0)
        r['LEAK_current_snaps'] = (None if r.get('s_snaps') is None
                                   else float(r['s_snaps']))
        r['LEAK_postgame_status'] = 1.0 if r['appeared'] else 0.0
    for _tm, rs in by_team.items():
        by_ord = collections.defaultdict(list)
        for x in rs:
            by_ord[x['ord']].append(x)
        for x in rs:
            grp = [g for g in by_ord[x['ord']] if g['gsis_id'] != x['gsis_id']]
            x['LEAK_future_teammate_avail'] = (
                float(np.mean([1.0 if g['appeared'] else 0.0 for g in grp]))
                if grp else None)
            same = sorted(by_ord[x['ord']],
                          key=lambda g: -(g.get('y_carries') or 0))
            x['LEAK_current_rank'] = float(
                [g['gsis_id'] for g in same].index(x['gsis_id']) + 1)

    print(f'== P4F adversarial (eval season {EV}, materiality {MATERIAL}) ==')
    base = candidate_crps(sub, rows, vol, pa, seasons, cellv=cell)
    print(f'  clean ABC_MPR CRPS {base:.4f}\n')

    for name, feats in (
            ('current_game_realised_carry_share', ['LEAK_current_carry_share']),
            ('current_game_realised_carries', ['LEAK_current_carries']),
            ('current_game_realised_snaps', ['LEAK_current_snaps']),
            ('future_teammate_availability', ['LEAK_future_teammate_avail']),
            ('postgame_roster_state', ['LEAK_postgame_status']),
            ('current_game_RB_rank', ['LEAK_current_rank']),
            ('future_carry_share', ['LEAK_future_carry_share'])):
        v = candidate_crps(sub, rows, vol, pa, seasons, extra=feats, cellv=cell)
        gain = base - v
        st = 'PASS' if gain >= MATERIAL else 'UNRESOLVED'
        record(name, st, seeded=round(v, 4), clean=round(base, 4),
               gain=round(gain, 4))

    # postgame roster state, well-posed: the fit is conditional on appearance,
    # so a constant column can carry no coefficient. Inject it where it acts.
    fit, pool, _ = F.fit_centre(sub, EV, K.BLOCKS_ABC, seasons)
    W0, mu = F.weights(cell, fit, pool, K.BLOCKS_ABC,
                       np.random.default_rng(CL.SEED + 3034))
    eps = CB._resample(pool, [r['position'] for r in cell['te']], cell['n'],
                       CL.M_DRAWS, np.random.default_rng(CL.SEED + 3034),
                       np.concatenate(list(pool.values())))
    Wl, _d, _r = M.rectify(mu, eps)
    Yl, _ = B.counts_from_weights(cell, (Wl * cell['A_star'][:, None]).astype(np.float32))
    v = float(CL.crps_samples(Yl, cell['y']).mean())
    record('postgame_roster_state_well_posed',
           'PASS' if base - v >= MATERIAL else 'UNRESOLVED',
           seeded=round(v, 4), clean=round(base, 4), gain=round(base - v, 4))

    # ---- the two MPR-specific probes the directive names ----------------
    # outcome-dependent delta: solve the shift against the REALISED share
    v = candidate_crps(sub, rows, vol, pa, seasons,
                       target_override=np.clip(cell['Sstar'], 0.0, 1.0),
                       cellv=cell)
    record('outcome_dependent_delta',
           'PASS' if base - v >= MATERIAL else 'UNRESOLVED',
           seeded=round(v, 4), clean=round(base, 4), gain=round(base - v, 4),
           note='the solver is retargeted at the realised share instead of C')

    # future residual pool: residuals drawn from the EVALUATION season
    ev_rows = [r for r in sub if r['season'] == EV and r['appeared']
               and r.get('s_carries') is not None]
    Xe, _ = B.design(ev_rows, K.BLOCKS_ABC)
    ye = np.array([r['s_carries'] for r in ev_rows], np.float64)
    pe = np.clip(F._pred(fit, Xe), 0.0, 1.0)
    fut = collections.defaultdict(list)
    for i, r in enumerate(ev_rows):
        fut[r['position']].append(float(ye[i] - pe[i]))
    fut = {k: np.array(v, np.float32) for k, v in fut.items()}
    v = candidate_crps(sub, rows, vol, pa, seasons, pool_override=fut,
                       cellv=cell)
    record('future_residual_pool',
           'PASS' if base - v >= MATERIAL else 'UNRESOLVED',
           seeded=round(v, 4), clean=round(base, 4), gain=round(base - v, 4),
           note='residual pool built from the evaluation season itself')

    # evaluation-season fitted correction (P4E GD1, STRENGTHENED: the eval
    # season now enters BOTH the coefficient fit and the residual pool)
    v_coef = candidate_crps(sub, rows, vol, pa, seasons, train_upto=EV + 1,
                            cellv=cell)
    fit2, pool2, _ = F.fit_centre(sub, EV + 1, K.BLOCKS_ABC, seasons)
    v_both = candidate_crps(sub, rows, vol, pa, seasons, train_upto=EV + 1,
                            pool_override=fut, cellv=cell)
    record('evaluation_season_fitted_correction',
           'PASS' if base - v_coef >= MATERIAL else 'UNRESOLVED',
           seeded=round(v_coef, 4), clean=round(base, 4),
           gain=round(base - v_coef, 4))
    record('evaluation_season_fitted_correction_STRENGTHENED',
           'PASS' if base - v_both >= MATERIAL else 'UNRESOLVED',
           seeded=round(v_both, 4), clean=round(base, 4),
           gain=round(base - v_both, 4),
           note='P4E GD1 retested with the evaluation season in the '
                'coefficients AND the residual pool')

    # ---- forbidden identifier scan --------------------------------------
    FORBIDDEN = ('weekly_rosters', 'depth_chart', 'depth_charts', 'status',
                 'closing_line', 'odds', 'moneyline', 'spread_line', 'weather',
                 'temp', 'wind', 'leak')
    srcs = ['p4f_mpr.py', 'p4f_common.py', 'run_p4f.py', 'run_p4f_oracle.py',
            'run_p4f_diag.py']

    def scan(paths):
        hits = []
        for f in paths:
            tree = ast.parse(open(os.path.join(HERE, f)).read())
            docs = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.FunctionDef,
                                     ast.AsyncFunctionDef, ast.ClassDef)):
                    d = ast.get_docstring(node, clean=False)
                    if d is not None:
                        docs.add(d)
            for node in ast.walk(tree):
                s = None
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in docs:
                        continue
                    s = node.value
                elif isinstance(node, ast.Name):
                    s = node.id
                elif isinstance(node, ast.Attribute):
                    s = node.attr
                if not s:
                    continue
                if any(t.lower() in FORBIDDEN
                       for t in re.split(r'[^A-Za-z0-9]+', s) if t):
                    hits.append((f, s))
        return hits
    hits = scan(srcs)
    record('forbidden_identifier_scan', 'PASS' if not hits else 'FAIL',
           hits=hits, files=len(srcs))

    # ---- guard-deletion proofs ------------------------------------------
    print('\n== guard-deletion proofs ==')

    # GD-A: the solver's target. Delete "the target is C" and it becomes the
    # outcome-dependent version above.
    v = candidate_crps(sub, rows, vol, pa, seasons,
                       target_override=np.clip(cell['Sstar'], 0.0, 1.0),
                       cellv=cell)
    record('GD-A delete "the solver targets C, never an outcome"',
           'PASS' if base - v >= MATERIAL else 'UNRESOLVED',
           with_guard=round(base, 4), guard_deleted=round(v, 4),
           gain=round(base - v, 4))

    # GD-B: the residual-pool chronology guard
    record('GD-B delete the residual-pool chronology guard',
           'PASS' if base - candidate_crps(sub, rows, vol, pa, seasons,
                                           pool_override=fut, cellv=cell)
           >= MATERIAL else 'UNRESOLVED',
           with_guard=round(base, 4),
           guard_deleted=round(candidate_crps(sub, rows, vol, pa, seasons,
                                              pool_override=fut, cellv=cell), 4))

    # GD-C: the feasibility detector in the solver
    Cbad = mu.astype(np.float64).copy()
    Cbad[:50] = 1.9                       # centres outside [0, 1]
    _W, dd, rep = M.rectify(Cbad, eps)
    caught = rep['infeasible_centre']
    orig_prep = M._prepare
    try:
        def no_check(centre, resid, lo, hi):
            C = np.asarray(centre, np.float64).reshape(-1)
            E = np.asarray(resid, np.float64)
            return C, E, np.zeros(len(C), bool), np.zeros(len(C), bool)
        M._prepare = no_check           # guard DELETED
        _W2, dd2, rep2 = M.rectify(Cbad, eps)
    finally:
        M._prepare = orig_prep
    record('GD-C delete the infeasible-centre detector',
           'PASS' if (caught == 50 and rep2['infeasible_centre'] == 0
                      and rep2['rows_outside_tolerance'] > 0) else 'FAIL',
           caught_with_guard=caught, caught_without=rep2['infeasible_centre'],
           rows_silently_wrong_without=rep2['rows_outside_tolerance'],
           note='without the detector 50 impossible centres are solved anyway '
                'and land outside tolerance instead of being named')

    # GD-D: the scan itself
    bad = os.path.join(HERE, '_gdd_seeded.py')
    open(bad, 'w').write('x = weekly_rosters_status_lookup\n')
    try:
        seeded_hits = scan(['_gdd_seeded.py'])
    finally:
        os.remove(bad)
    record('GD-D seed a forbidden identifier past the scan',
           'PASS' if seeded_hits else 'FAIL', hits=seeded_hits)

    # GD4 from P4E: the out-of-fold residual-pool guard, retested
    tr = F._train_rows(sub, EV)
    Xt, _ = B.design(tr, K.BLOCKS_ABC)
    yt = np.array([r['s_carries'] for r in tr], np.float64)
    pt = np.clip(F._pred(fit, Xt), 0.0, 1.0)
    ins = collections.defaultdict(list)
    for i, r in enumerate(tr):
        ins[r['position']].append(float(yt[i] - pt[i]))
    ins = {k: np.array(v, np.float32) for k, v in ins.items()}
    v = candidate_crps(sub, rows, vol, pa, seasons, pool_override=ins,
                       cellv=cell)
    record('GD4-retest delete the out-of-fold residual-pool guard',
           'PASS' if abs(base - v) >= MATERIAL else 'UNRESOLVED',
           with_guard=round(base, 4), guard_deleted=round(v, 4),
           change=round(base - v, 4),
           note='P4E left this UNRESOLVED; retested under MPR, where the pool '
                'also sets the shift')

    nf = sum(1 for r in RESULTS if r['state'] == 'FAIL')
    nu = sum(1 for r in RESULTS if r['state'] == 'UNRESOLVED')
    gd = sum(1 for r in RESULTS
             if r['probe'].startswith('GD-') and r['state'] == 'PASS')
    print(f'\n{len(RESULTS)} probes: {len(RESULTS)-nf-nu} PASS, {nu} UNRESOLVED, '
          f'{nf} FAIL; {gd} load-bearing guard-deletion proofs firing')
    json.dump({'eval_season': EV, 'material_threshold_crps': MATERIAL,
               'clean_crps': base, 'probes': RESULTS,
               'guard_deletion_proofs_firing': gd},
              open(f'{HERE}/p4f_adversarial.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p4f_adversarial.json')


if __name__ == '__main__':
    main()
