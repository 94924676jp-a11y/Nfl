"""R1 adversarial probes and guard-deletion proofs.

Materiality is 10% relative R MAE improvement, fixed in predeclaration_r1.md
section 16 and not lowered here. A probe that cannot fire is UNRESOLVED, never
PASS.
"""
import ast, collections, copy, json, os, re, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, '/home/user/nfl/sportsplatform')
for p in ('p4c', 'p4e', 's2', 's4'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import r1_lib as L, r1_fit as F                                # noqa: E402
import p4c_build as CB                                         # noqa: E402

MATERIAL = 0.10
EV = 2024
BLOCKS = ['A', 'B', 'C', 'D']
RESULTS = []


def record(name, state, **kw):
    RESULTS.append(dict(probe=name, state=state, **kw))
    print(f'  {state:11s} {name:40s} ' +
          ' '.join(f'{k}={v}' for k, v in kw.items() if k != 'note'))


def score(sub, pa, seasons, extra=None, train_upto=None, ev=EV):
    saved = dict(F.BLOCKS)
    F.BLOCKS = dict(F.BLOCKS)
    if extra:
        F.BLOCKS['Z'] = extra
    try:
        bl = BLOCKS + (['Z'] if extra else [])
        fit, _fd = F.fit_rung(sub, train_upto or ev, bl, pa, seasons)
        te = [r for r in sub if L.eligible(r, ev)]
        p = F.predict_rung(fit, te, bl, pa)
        y = np.array([r['R_star'] for r in te], float)
        return L.metrics(p, y)
    finally:
        F.BLOCKS = saved


def main():
    t0 = time.time()
    rows, sub = L.load(); L.attach(sub, rows)
    pa = CB.appearance(rows)
    seasons = sorted({r['season'] for r in sub})
    base = score(sub, pa, seasons)
    print(f'== R1 adversarial (season {EV}, materiality {MATERIAL:.0%} rel MAE) ==')
    print(f'  clean R_ABCD MAE {base["mae"]:.4f}\n')

    # seed every forbidden channel
    byp = collections.defaultdict(list)
    for r in sub:
        byp[r['gsis_id']].append(r)
    for _p, seq in byp.items():
        seq.sort(key=lambda x: x['ord'])
        for i, r in enumerate(seq):
            nx = seq[i + 1] if i + 1 < len(seq) else None
            r['Z_future_R'] = None if nx is None else nx.get('R_star')
            r['Z_future_targets'] = None if nx is None else (
                nx.get('y_targets') or 0.0)
            r['Z_future_P'] = None if nx is None else nx.get('P_star')
    byteam = collections.defaultdict(list)
    for r in sub:
        byteam[(r['team'], r['ord'])].append(r)
    for _k, grp in byteam.items():
        tot = float(sum((g.get('y_targets') or 0) for g in grp))
        for r in grp:
            o = [g for g in grp if g['gsis_id'] != r['gsis_id']]
            r['Z_team_target_total'] = tot
            r['Z_future_mate'] = (float(np.mean([1.0 if g['appeared'] else 0.0
                                                 for g in o])) if o else None)
    ids = {p: i for i, p in enumerate(sorted(byp))}
    for r in sub:
        r['Z_cur_targets'] = float(r.get('y_targets') or 0.0)
        r['Z_cur_R'] = r.get('R_star')
        r['Z_cur_P'] = r.get('P_star')
        r['Z_postgame'] = 1.0 if r['appeared'] else 0.0
        r['Z_status'] = {'Out': 0.0, 'Doubtful': .25, 'Questionable': .6,
                         'Probable': .9}.get(r.get('f_inj_status'), 1.0)
        r['Z_depth'] = float(r.get('f_depth') or 0.0)
        r['Z_ident'] = ids[r['gsis_id']] / max(len(ids), 1)
        r['Z_market'] = 0.0        # no market field exists in this project
        r['Z_weather'] = 0.0       # no observed-weather field exists either

    for name, feats in (
            ('current_game_targets', ['Z_cur_targets']),
            ('current_game_R', ['Z_cur_R']),
            ('current_game_participation', ['Z_cur_P']),
            ('future_targets', ['Z_future_targets']),
            ('future_R', ['Z_future_R']),
            ('future_participation', ['Z_future_P']),
            ('future_team_target_total', ['Z_team_target_total']),
            ('postgame_roster_state', ['Z_postgame']),
            ('weekly_rosters_status_proxy', ['Z_status']),
            ('present_week_depth_chart', ['Z_depth']),
            ('future_teammate_state', ['Z_future_mate']),
            ('identifier_leakage', ['Z_ident']),
            ('forbidden_market_field', ['Z_market']),
            ('observed_weather', ['Z_weather'])):
        m = score(sub, pa, seasons, extra=feats)
        g = (base['mae'] - m['mae']) / base['mae']
        st = 'PASS' if g >= MATERIAL else 'UNRESOLVED'
        note = ('' if st == 'PASS' else
                'seeded leak did not move MAE materially; this probe has not '
                'shown it could catch such a leak. Threshold NOT lowered.')
        record(name, st, seeded=round(m['mae'], 4), clean=round(base['mae'], 4),
               rel_gain=f'{g:+.1%}', note=note)

    # evaluation-season fit leakage
    m = score(sub, pa, seasons, train_upto=EV + 1)
    g = (base['mae'] - m['mae']) / base['mae']
    record('evaluation_season_fit_leakage',
           'PASS' if g >= MATERIAL else 'UNRESOLVED',
           seeded=round(m['mae'], 4), rel_gain=f'{g:+.1%}')

    # post-hoc hyperparameter selection: pick lambda on the EVAL season
    te = [r for r in sub if L.eligible(r, EV)]
    y = np.array([r['R_star'] for r in te], float)
    trr = [r for r in sub if r['season'] < EV and L.eligible(r)]
    Xtr, _f, _n = F.design(trr, BLOCKS, pa)
    ytr = np.array([r['R_star'] for r in trr], float)
    Xte, _f2, _n2 = F.design(te, BLOCKS, pa)
    bestm = None
    for lm in F.LAMBDAS:
        fit = F._fit(Xtr, ytr, lm)
        p = np.clip(F._pred(fit, Xte), 0, 2)
        mm = L.metrics(p, y)['mae']
        bestm = mm if bestm is None else min(bestm, mm)
    g = (base['mae'] - bestm) / base['mae']
    record('posthoc_hyperparameter_selection',
           'PASS' if g >= MATERIAL else 'UNRESOLVED',
           best_on_eval=round(bestm, 4), honest=round(base['mae'], 4),
           rel_gain=f'{g:+.1%}',
           note='choosing lambda on the evaluation season instead of the inner '
                'validation season')

    # wrong denominator: divide by team targets instead of team dropbacks
    for r in sub:
        den = (r.get('den') or {})
        tt = den.get('team_targets') or 0
        ps = r.get('pass_snaps')
        r['Z_wrongden'] = (float(ps) / tt) if (ps is not None and tt) else None
    sub_w = copy.deepcopy(sub)
    for r in sub_w:
        if r['Z_wrongden'] is not None and r['Z_wrongden'] > 0 and r['appeared']:
            r['P_star'] = r['Z_wrongden']
            r['R_star'] = r['W_star'] / r['Z_wrongden']
            r['R_defined'] = True
        for g_ in [g_ for g_ in r if g_.startswith('h_')]:
            del r[g_]
    L.attach(sub_w, rows)
    mw = score(sub_w, pa, seasons)
    ch = abs(mw['mae'] - base['mae']) / base['mae']
    record('wrong_denominator', 'PASS' if ch >= MATERIAL else 'UNRESOLVED',
           wrong_den_mae=round(mw['mae'], 4), correct=round(base['mae'], 4),
           rel_change=f'{ch:+.1%}',
           note='team_targets substituted for team_dropbacks as the '
                'participation denominator')

    # zero / N-A conflation: score non-appearances as rate zero
    sub_z = copy.deepcopy(sub)
    n_conf = 0
    for r in sub_z:
        if not r['appeared'] or r['P_star'] in (None, 0):
            r['R_star'] = 0.0
            r['R_defined'] = True
            r['P_star'] = r['P_star'] if r['P_star'] else 0.0
            n_conf += 1
        for g_ in [g_ for g_ in r if g_.startswith('h_')]:
            del r[g_]
    L.attach(sub_z, rows)
    mz = score(sub_z, pa, seasons)
    ch = abs(mz['mae'] - base['mae']) / base['mae']
    record('zero_NA_conflation', 'PASS' if ch >= MATERIAL else 'UNRESOLVED',
           conflated_mae=round(mz['mae'], 4), correct=round(base['mae'], 4),
           rel_change=f'{ch:+.1%}', rows_conflated=n_conf)

    # target-rate division instability: no participation weighting anywhere
    sub_u = copy.deepcopy(sub)
    for r in sub_u:
        for g_ in [g_ for g_ in r if g_.startswith('h_')]:
            del r[g_]
    orig_w = L.wmean
    try:
        L.wmean = lambda v, w=None: orig_w(v, None)
        orig_e = L.ewma
        L.ewma = lambda v, hl, w=None: orig_e(v, hl, None)
        L.attach(sub_u, rows)
        mu_ = score(sub_u, pa, seasons)
    finally:
        L.wmean = orig_w
        L.ewma = orig_e
    ch = (mu_['mae'] - base['mae']) / base['mae']
    record('target_rate_division_instability',
           'PASS' if abs(ch) >= MATERIAL else 'UNRESOLVED',
           unweighted_mae=round(mu_['mae'], 4), weighted=round(base['mae'], 4),
           rel_change=f'{ch:+.1%}',
           note='participation weighting removed from every history estimator; '
                'a rate from one pass snap then counts as much as one from '
                'thirty')

    # manually rounded artifact reference
    from governance import artifact_reference as AR
    P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c', 'p4c_results.json'))
    real = json.load(open(P4C))['targets']['2024']['scores']['C']['crps']
    o = AR.assert_gate(round(real, 4), P4C,
                       ('targets', '2024', 'scores', 'C', 'crps'),
                       tolerance=0.0, code='R1_ROUNDED')
    record('manual_rounded_artifact_reference',
           'PASS' if o.state.value == 'FAIL' else 'FAIL',
           refused=o.state.value, code=o.code,
           note='a 4-decimal rounding of the true value is refused by Rule 006')

    # same-week duplicate chronology
    seen = collections.Counter()
    for r in sub:
        seen[(r['gsis_id'], r['ord'])] += 1
    dup = sum(1 for k, v in seen.items() if v > 1)
    import bisect as _b
    sub_d = copy.deepcopy(sub)
    for r in sub_d:
        for g_ in [g_ for g_ in r if g_.startswith('h_')]:
            del r[g_]
    orig = _b.bisect_left
    try:
        _b.bisect_left = lambda a, x: len(a)
        L.attach(sub_d, rows)
    finally:
        _b.bisect_left = orig
    diff = 0
    m2 = {(r['team'], r['gsis_id'], r['ord']): r for r in sub_d}
    for r in sub:
        o2 = m2.get((r['team'], r['gsis_id'], r['ord']))
        if o2 and (r.get('h_last') != o2.get('h_last')
                   or r.get('h_n') != o2.get('h_n')):
            diff += 1
    record('same_week_duplicate_chronology',
           'PASS' if diff > 0 else 'UNRESOLVED',
           duplicate_player_ordinals=dup, rows_history_changed=diff)

    # forbidden identifier scan
    FORB = ('weekly_rosters', 'depth_chart', 'depth_charts', 'odds',
            'moneyline', 'spread_line', 'closing_line', 'weather', 'wind',
            'salary', 'ownership', 'lineup')
    srcs = ['r1_lib.py', 'r1_fit.py', 'run_r1_block0.py', 'run_r1_ladder.py',
            'run_r1_diag.py']
    hits = []
    for f in srcs:
        tree = ast.parse(open(os.path.join(HERE, f)).read())
        docs = set()
        for nd in ast.walk(tree):
            if isinstance(nd, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                dd = ast.get_docstring(nd, clean=False)
                if dd:
                    docs.add(dd)
        for nd in ast.walk(tree):
            s = None
            if isinstance(nd, ast.Constant) and isinstance(nd.value, str):
                if nd.value in docs:
                    continue
                s = nd.value
            elif isinstance(nd, ast.Name):
                s = nd.id
            elif isinstance(nd, ast.Attribute):
                s = nd.attr
            if s and any(t.lower() in FORB
                         for t in re.split(r'[^A-Za-z0-9]+', s) if t):
                hits.append((f, s))
    record('forbidden_identifier_scan', 'PASS' if not hits else 'FAIL',
           hits=hits, files=len(srcs))

    # ---- guard-deletion proofs ------------------------------------------
    print('\n== guard-deletion proofs ==')
    # GD-1: the strictly-earlier-ordinal prefix cut
    record('GD-1 delete the strictly-earlier-ordinal cut',
           'PASS' if diff > 0 else 'UNRESOLVED',
           rows_history_changed=diff, duplicate_player_ordinals=dup,
           note='replayed from the same-week probe above; without the cut a '
                'mid-week team change lets a player read his own same-week row')
    # GD-2: the complexity ceiling
    try:
        F.design([r for r in sub if L.eligible(r, EV)][:10],
                 ['A', 'B', 'C', 'D', 'E'], pa)
        ceil_holds = 'not triggered at ABCDE'
    except ValueError as exc:
        ceil_holds = str(exc)[:60]
    orig_max = F.MAX_COLS
    try:
        F.MAX_COLS = 4
        try:
            F.design([r for r in sub if L.eligible(r, EV)][:10], BLOCKS, pa)
            fired = False
        except ValueError:
            fired = True
    finally:
        F.MAX_COLS = orig_max
    record('GD-2 the complexity ceiling refuses an over-wide design',
           'PASS' if fired else 'FAIL',
           at_ceiling_4=fired, at_real_ceiling=ceil_holds)
    # GD-3: the chronology guard in fit_rung's training filter
    orig_el = L.eligible
    try:
        L.eligible = lambda r, ev=None: (
            bool(r['R_defined'] and (r.get('h_n') or 0) >= 0
                 and r.get('h_pos_mean') is not None)
            if ev is None else orig_el(r, ev))
        m = score(sub, pa, seasons)
        g = (base['mae'] - m['mae']) / base['mae']
    finally:
        L.eligible = orig_el
    record('GD-3 relax the >=1-prior-game training filter',
           'PASS' if abs(g) >= MATERIAL else 'UNRESOLVED',
           relaxed_mae=round(m['mae'], 4), rel_change=f'{g:+.1%}')

    nf = sum(1 for r in RESULTS if r['state'] == 'FAIL')
    nu = sum(1 for r in RESULTS if r['state'] == 'UNRESOLVED')
    gd = sum(1 for r in RESULTS
             if r['probe'].startswith('GD-') and r['state'] == 'PASS')
    print(f'\n{len(RESULTS)} probes: {len(RESULTS)-nf-nu} PASS, {nu} UNRESOLVED, '
          f'{nf} FAIL; {gd} guard-deletion proofs firing')
    json.dump({'eval_season': EV, 'material_threshold': MATERIAL,
               'clean_mae': base['mae'], 'probes': RESULTS,
               'guard_deletion_proofs_firing': gd},
              open(f'{HERE}/r1_adversarial.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> r1_adversarial.json')


if __name__ == '__main__':
    main()
