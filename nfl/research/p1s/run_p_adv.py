"""P adversarial probes and guard-deletion proofs.

Materiality is 5% relative P MAE, fixed in the pre-registration and not lowered.

NOTE ON SURFACE. The selected candidate is P0 = EWMA half-life 1, a fixed-form
estimator with NO feature channel: nothing can be injected into it except
through the history construction itself. Feature-injection probes are therefore
run against the ridge rung P_ABCD, which is the only fittable model in this
study and the only place a seeded column could act. The history-construction
probes -- same-week chronology, wrong denominator, zero/N-A conflation -- apply
to the candidate directly, and are the ones that matter for it.
"""
import ast, collections, copy, json, os, re, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, '/home/user/nfl/sportsplatform')
for p in ('s2', 'p4c', 'p4e', 's4'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import p_lib as L, p_fit as F                                  # noqa: E402
import s2_lib as SL                                            # noqa: E402
import p4c_build as CB                                         # noqa: E402

MATERIAL = 0.05
EV = 2024
BLOCKS = ['A', 'B', 'C', 'D']
RESULTS = []


def record(name, state, **kw):
    RESULTS.append(dict(probe=name, state=state, **kw))
    print(f'  {state:11s} {name:40s} ' +
          ' '.join(f'{k}={v}' for k, v in kw.items() if k != 'note'))


def score(sub, pa, extra=None, train_upto=None, ev=EV):
    saved = dict(F.BLOCKS)
    F.BLOCKS = dict(F.BLOCKS)
    if extra:
        F.BLOCKS['Z'] = extra
    try:
        bl = BLOCKS + (['Z'] if extra else [])
        fit, _fd = F.fit_rung(sub, train_upto or ev, bl, pa)
        te = [r for r in sub if L.eligible(r, ev)]
        p = F.predict_rung(fit, te, bl, pa)
        y = np.array([float(r[L.TARGET]) for r in te])
        return L.metrics(p, y)
    finally:
        F.BLOCKS = saved


def score_simple(sub, ev=EV):
    te = [r for r in sub if L.eligible(r, ev)]
    p = np.array([(r.get('p_ewma1') if r.get('p_ewma1') is not None
                   else r.get('q_pos_mean')) for r in te], float)
    y = np.array([float(r[L.TARGET]) for r in te])
    return L.metrics(np.clip(p, 0, 1), y)


def main():
    t0 = time.time()
    rows, sub = L.load()
    pa = CB.appearance(rows)
    L.attach(sub, pa)
    base = score(sub, pa)
    base_s = score_simple(sub)
    print(f'== P adversarial (season {EV}, materiality {MATERIAL:.0%} rel MAE) ==')
    print(f'  ridge P_ABCD MAE {base["mae"]:.4f} | candidate P0 MAE '
          f'{base_s["mae"]:.4f}\n')

    byp = collections.defaultdict(list)
    for r in sub:
        byp[r['gsis_id']].append(r)
    for _p, seq in byp.items():
        seq.sort(key=lambda x: x['ord'])
        for i, r in enumerate(seq):
            nx = seq[i + 1] if i + 1 < len(seq) else None
            r['Z_future_P'] = None if nx is None else nx.get(L.TARGET)
            r['Z_future_targets'] = None if nx is None else (
                nx.get('y_targets') or 0.0)
    byteam = collections.defaultdict(list)
    for r in sub:
        byteam[(r['team'], r['ord'])].append(r)
    for _k, grp in byteam.items():
        for r in grp:
            o = [g for g in grp if g['gsis_id'] != r['gsis_id']]
            r['Z_future_mate_P'] = (float(np.mean([(g.get(L.TARGET) or 0.0)
                                                   for g in o])) if o else None)
    ids = {p: i for i, p in enumerate(sorted(byp))}
    for r in sub:
        den = r.get('den') or {}
        r['Z_cur_P'] = r.get(L.TARGET)
        r['Z_cur_pass_snaps'] = float(r.get('pass_snaps') or 0.0)
        r['Z_cur_dropbacks'] = float(den.get('team_dropbacks_part') or 0.0)
        r['Z_cur_targets'] = float(r.get('y_targets') or 0.0)
        r['Z_postgame'] = 1.0 if r['appeared'] else 0.0
        r['Z_status'] = {'Out': 0.0, 'Doubtful': .25, 'Questionable': .6,
                         'Probable': .9}.get(r.get('f_inj_status'), 1.0)
        r['Z_depth'] = float(r.get('f_depth') or 0.0)
        r['Z_ident'] = ids[r['gsis_id']] / max(len(ids), 1)
        r['Z_market'] = 0.0
        r['Z_weather'] = 0.0

    for name, feats in (
            ('current_game_P', ['Z_cur_P']),
            ('current_game_pass_snaps', ['Z_cur_pass_snaps']),
            ('current_game_team_dropbacks', ['Z_cur_dropbacks']),
            ('current_game_targets', ['Z_cur_targets']),
            ('future_P', ['Z_future_P']),
            ('future_target_data', ['Z_future_targets']),
            ('future_teammate_participation', ['Z_future_mate_P']),
            ('postgame_roster_state', ['Z_postgame']),
            ('weekly_rosters_status_proxy', ['Z_status']),
            ('present_week_depth_chart', ['Z_depth']),
            ('identifier_leakage', ['Z_ident']),
            ('market_data', ['Z_market']),
            ('observed_weather', ['Z_weather'])):
        m = score(sub, pa, extra=feats)
        g = (base['mae'] - m['mae']) / base['mae']
        st = 'PASS' if g >= MATERIAL else 'UNRESOLVED'
        record(name, st, seeded=round(m['mae'], 4), clean=round(base['mae'], 4),
               rel_gain=f'{g:+.1%}',
               note='' if st == 'PASS' else
                    'seeded leak did not move MAE materially; threshold NOT '
                    'lowered')

    m = score(sub, pa, train_upto=EV + 1)
    g = (base['mae'] - m['mae']) / base['mae']
    record('evaluation_season_fit_leakage',
           'PASS' if g >= MATERIAL else 'UNRESOLVED',
           seeded=round(m['mae'], 4), rel_gain=f'{g:+.1%}')

    te = [r for r in sub if L.eligible(r, EV)]
    y = np.array([float(r[L.TARGET]) for r in te])
    trr = [r for r in sub if r['season'] < EV and L.eligible(r)]
    Xtr, _f, _n = F.design(trr, BLOCKS, pa)
    ytr = np.array([float(r[L.TARGET]) for r in trr])
    Xte, _f2, _n2 = F.design(te, BLOCKS, pa)
    bestm = min(L.metrics(np.clip(F._pred(F._fit(Xtr, ytr, lm), Xte), 0, 1),
                          y)['mae'] for lm in F.LAMBDAS)
    g = (base['mae'] - bestm) / base['mae']
    record('posthoc_hyperparameter_selection',
           'PASS' if g >= MATERIAL else 'UNRESOLVED',
           best_on_eval=round(bestm, 4), honest=round(base['mae'], 4),
           rel_gain=f'{g:+.1%}')

    # ---- history-construction probes: these hit the CANDIDATE directly ----
    sub_w = copy.deepcopy(sub)
    for r in sub_w:
        den = r.get('den') or {}
        tt = den.get('team_targets') or 0
        ps = r.get('pass_snaps')
        r[L.TARGET] = (float(ps) / tt) if (ps is not None and tt) else None
        for g_ in [g_ for g_ in r if g_.startswith(('p_', 'q_'))]:
            del r[g_]
    SL.attach(sub_w); L.attach(sub_w, pa)
    mw = score_simple(sub_w)
    ch = abs(mw['mae'] - base_s['mae']) / base_s['mae']
    record('wrong_denominator', 'PASS' if ch >= MATERIAL else 'UNRESOLVED',
           wrong=round(mw['mae'], 4), correct=round(base_s['mae'], 4),
           rel_change=f'{ch:+.1%}',
           note='team_targets substituted for team_dropbacks; hits the '
                'candidate directly')

    sub_z = copy.deepcopy(sub)
    nz = 0
    for r in sub_z:
        if not r['appeared'] or r.get(L.TARGET) is None:
            r[L.TARGET] = 0.0
            r['appeared'] = 1
            nz += 1
        for g_ in [g_ for g_ in r if g_.startswith(('p_', 'q_'))]:
            del r[g_]
    SL.attach(sub_z); L.attach(sub_z, pa)
    mz = score_simple(sub_z)
    ch = abs(mz['mae'] - base_s['mae']) / base_s['mae']
    record('zero_NA_conflation', 'PASS' if ch >= MATERIAL else 'UNRESOLVED',
           conflated=round(mz['mae'], 4), correct=round(base_s['mae'], 4),
           rel_change=f'{ch:+.1%}', rows=nz)

    # future residual pool: fit the ridge's own residual scale on the eval season
    tr_all = [r for r in sub if L.eligible(r)]
    Xa, _f3, _n3 = F.design(tr_all, BLOCKS, pa)
    ya = np.array([float(r[L.TARGET]) for r in tr_all])
    fit_all = F._fit(Xa, ya, 1.0)
    p_all = np.clip(F._pred(fit_all, Xte), 0, 1)
    m = L.metrics(p_all, y)
    g = (base['mae'] - m['mae']) / base['mae']
    record('future_residual_pool', 'PASS' if g >= MATERIAL else 'UNRESOLVED',
           seeded=round(m['mae'], 4), rel_gain=f'{g:+.1%}',
           note='fit on ALL seasons including the evaluation season')

    from governance import artifact_reference as AR
    S2 = '/home/user/nfl/nfl/research/s2/s2_results.json'
    real = json.load(open(S2))['by_season']['WR']['ewma_hl2']['pooled']['mae']
    o = AR.assert_gate(round(real, 4), S2,
                       ('by_season', 'WR', 'ewma_hl2', 'pooled', 'mae'),
                       tolerance=0.0, code='P_ROUNDED')
    record('manual_rounded_artifact_reference',
           'PASS' if o.state.value == 'FAIL' else 'FAIL',
           refused=o.state.value, code=o.code)

    import bisect as _b
    seen = collections.Counter()
    for r in sub:
        seen[(r['gsis_id'], r['ord'])] += 1
    dup = sum(1 for k, v in seen.items() if v > 1)
    sub_d = copy.deepcopy(sub)
    for r in sub_d:
        for g_ in [g_ for g_ in r if g_.startswith(('p_', 'q_'))]:
            del r[g_]
    orig = _b.bisect_left
    try:
        _b.bisect_left = lambda a, x: len(a)
        SL.attach(sub_d); L.attach(sub_d, pa)
    finally:
        _b.bisect_left = orig
    m2 = {(r['team'], r['gsis_id'], r['ord']): r for r in sub_d}
    diff = sum(1 for r in sub
               if (o2 := m2.get((r['team'], r['gsis_id'], r['ord'])))
               and (r.get('p_last') != o2.get('p_last')
                    or r.get('p_n') != o2.get('p_n')))
    record('same_week_duplicate_chronology',
           'PASS' if diff > 0 else 'UNRESOLVED',
           duplicate_player_ordinals=dup, rows_history_changed=diff)

    FORB = ('weekly_rosters', 'depth_chart', 'depth_charts', 'odds',
            'moneyline', 'spread_line', 'closing_line', 'weather', 'wind',
            'salary', 'ownership', 'lineup')
    srcs = ['p_lib.py', 'p_fit.py', 'run_p_gate.py', 'run_p_study.py',
            'run_p_down.py', 'run_p_joint.py']
    hits = []
    for f in srcs:
        tree = ast.parse(open(os.path.join(HERE, f)).read())
        docs = {ast.get_docstring(nd, clean=False) for nd in ast.walk(tree)
                if isinstance(nd, (ast.Module, ast.FunctionDef, ast.ClassDef))}
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

    print('\n== guard-deletion proofs ==')
    record('GD-1 delete the strictly-earlier-ordinal cut',
           'PASS' if diff > 0 else 'UNRESOLVED',
           rows_history_changed=diff, duplicate_player_ordinals=dup,
           note='without the cut a mid-week team change lets a player read his '
                'own same-week row')
    orig_max = F.MAX_COLS
    try:
        F.MAX_COLS = 4
        try:
            F.design(te[:10], BLOCKS, pa)
            fired = False
        except ValueError:
            fired = True
    finally:
        F.MAX_COLS = orig_max
    record('GD-2 the complexity ceiling refuses an over-wide design',
           'PASS' if fired else 'FAIL', at_ceiling_4=fired)
    # GD-3: the appeared-only condition on P history
    sub_a = copy.deepcopy(sub)
    for r in sub_a:
        for g_ in [g_ for g_ in r if g_.startswith(('p_', 'q_'))]:
            del r[g_]
    orig_att = L.attach

    def no_app(sub_, pa_):
        for r in sub_:
            if not r['appeared'] and r.get(L.TARGET) is None:
                r[L.TARGET] = 0.0
                r['appeared'] = 1
        return orig_att(sub_, pa_)
    SL.attach(sub_a)
    no_app(sub_a, pa)
    ma = score_simple(sub_a)
    ch = (ma['mae'] - base_s['mae']) / base_s['mae']
    record('GD-3 delete the appeared-only condition on P history',
           'PASS' if abs(ch) >= MATERIAL else 'UNRESOLVED',
           without_guard=round(ma['mae'], 4), with_guard=round(base_s['mae'], 4),
           rel_change=f'{ch:+.1%}')

    nf = sum(1 for r in RESULTS if r['state'] == 'FAIL')
    nu = sum(1 for r in RESULTS if r['state'] == 'UNRESOLVED')
    gd = sum(1 for r in RESULTS
             if r['probe'].startswith('GD-') and r['state'] == 'PASS')
    print(f'\n{len(RESULTS)} probes: {len(RESULTS)-nf-nu} PASS, {nu} UNRESOLVED, '
          f'{nf} FAIL; {gd} guard-deletion proofs firing')
    json.dump({'eval_season': EV, 'material_threshold': MATERIAL,
               'ridge_clean_mae': base['mae'], 'candidate_clean_mae': base_s['mae'],
               'probes': RESULTS, 'guard_deletion_proofs_firing': gd},
              open(f'{HERE}/p_adversarial.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p_adversarial.json')


if __name__ == '__main__':
    main()
