"""P4E section 13: seeded leakage probes and guard-deletion proofs.

A probe is only evidence if it can FIRE. Each probe therefore seeds the leak,
measures how large the resulting gain is, and only then checks that the real
pipeline contains no such channel. A probe whose seeded version does NOT
produce a detectable gain is reported UNRESOLVED -- it has not demonstrated
that the harness could catch that leak -- and is never reported as PASS.
"""
import ast, collections, json, os, re, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4e_build as B                                          # noqa: E402
import p4e_fit as F                                            # noqa: E402
import p4c_lib as CL                                           # noqa: E402

BLOCKS = ['A', 'B', 'C']
EV = 2024                       # one season; a leak that only shows in one is
                                # still a leak, and this keeps the probe cheap
MATERIAL = 0.010                # CRPS units; a seeded leak must move at least
                                # this much for the probe to count as sensitive
RESULTS = []


def record(name, state, **kw):
    RESULTS.append(dict(probe=name, state=state, **kw))
    extra = ' '.join(f'{k}={v}' for k, v in kw.items())
    print(f'  {state:11s} {name:34s} {extra}')


def run_with(sub, rows, vol, pa, seasons, extra_feats, train_upto=None):
    """CRPS of the E_ABC candidate with `extra_feats` appended to the design."""
    saved = dict(B.BLOCKS)
    B.BLOCKS = dict(B.BLOCKS)
    B.BLOCKS['Z'] = extra_feats
    try:
        blocks = BLOCKS + (['Z'] if extra_feats else [])
        ev = EV if train_upto is None else train_upto
        fit, pool, fd = F.fit_centre(sub, ev, blocks, seasons)
        c = B.cell(rows, vol, pa, sub, EV)
        W, _mu = F.weights(c, fit, pool, blocks,
                           np.random.default_rng(CL.SEED + 3034))
        Y, _S = B.counts_from_weights(c, W)
        return float(CL.crps_samples(Y, c['y']).mean())
    finally:
        B.BLOCKS = saved


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})

    # ---- seed the forbidden channels onto every row ---------------------
    by_team = collections.defaultdict(list)
    for r in sub:
        by_team[r['team']].append(r)
    hist = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        hist[r['gsis_id']].append(r)
    for pid, seq in hist.items():
        for i, r in enumerate(seq):
            nxt = seq[i + 1] if i + 1 < len(seq) else None
            r['LEAK_future_carry_share'] = (
                None if nxt is None else (nxt.get('s_carries') or 0.0))
    for r in sub:
        r['LEAK_current_carries'] = float(r.get('y_carries') or 0.0)
        r['LEAK_current_snaps'] = (None if r.get('s_snaps') is None
                                   else float(r['s_snaps']))
        r['LEAK_postgame_status'] = 1.0 if r['appeared'] else 0.0
    for tm, rs in by_team.items():
        by_ord = collections.defaultdict(list)
        for x in rs:
            by_ord[x['ord']].append(x)
        for x in rs:
            grp = [g for g in by_ord[x['ord']] if g['gsis_id'] != x['gsis_id']]
            x['LEAK_future_teammate_avail'] = (
                float(np.mean([1.0 if g['appeared'] else 0.0 for g in grp]))
                if grp else None)
            same = sorted(by_ord[x['ord']], key=lambda g: -(g.get('y_carries') or 0))
            x['LEAK_current_rank'] = float(
                [g['gsis_id'] for g in same].index(x['gsis_id']) + 1)

    print(f'== P4E adversarial probes (eval season {EV}) ==')
    base = run_with(sub, rows, vol, pa, seasons, [])
    print(f'  clean E_ABC CRPS {base:.4f}\n')

    probes = [
        ('future_carry_share', ['LEAK_future_carry_share']),
        ('current_game_realised_carries', ['LEAK_current_carries']),
        ('current_game_realised_snaps', ['LEAK_current_snaps']),
        ('postgame_roster_status', ['LEAK_postgame_status']),
        ('future_teammate_availability', ['LEAK_future_teammate_avail']),
        ('current_game_RB_rank', ['LEAK_current_rank']),
    ]
    for name, feats in probes:
        c = run_with(sub, rows, vol, pa, seasons, feats)
        gain = base - c
        state = 'PASS' if gain >= MATERIAL else 'UNRESOLVED'
        record(name, state, seeded_crps=round(c, 4), clean=round(base, 4),
               gain=round(gain, 4),
               note=('probe fires; the clean pipeline reads none of these '
                     'fields' if state == 'PASS' else
                     'seeded leak did NOT move CRPS materially, so this probe '
                     'has not shown it could catch such a leak. Threshold NOT '
                     'lowered.'))

    # The weak postgame-status probe above is DEGENERATE and its zero is not
    # evidence of safety: the fit is conditional on appearance, so the seeded
    # column is constant 1.0 across the whole training set and can carry no
    # coefficient. A well-posed version injects the same forbidden information
    # where it could actually act -- into the weight itself.
    c0 = B.cell(rows, vol, pa, sub, EV)
    fit0, pool0, _ = F.fit_centre(sub, EV, BLOCKS, seasons)
    W0, mu0 = F.weights(c0, fit0, pool0, BLOCKS,
                        np.random.default_rng(CL.SEED + 3034))
    W_leak = W0 * c0['A_star'][:, None]              # postgame appearance label
    Yl, _ = B.counts_from_weights(c0, W_leak)
    strong = float(CL.crps_samples(Yl, c0['y']).mean())
    record('postgame_roster_status_strong',
           'PASS' if base - strong >= MATERIAL else 'UNRESOLVED',
           seeded_crps=round(strong, 4), clean=round(base, 4),
           gain=round(base - strong, 4),
           note='the weak version cannot fire because the training set is '
                'conditioned on appearance; this is the well-posed form')

    # evaluation-season fitted prior: train through EV instead of before it
    c = run_with(sub, rows, vol, pa, seasons, [], train_upto=EV + 1)
    gain = base - c
    record('evaluation_season_fitted_prior',
           'PASS' if gain >= MATERIAL else 'UNRESOLVED',
           seeded_crps=round(c, 4), clean=round(base, 4), gain=round(gain, 4))

    # ---- static guard: no forbidden identifier in the P4E sources -------
    #
    # Matching is on IDENTIFIER TOKENS, not substrings. The first version of
    # this scan matched substrings and reported p4e_fit.py for the phrase
    # "expanding-window" -- 'wind' inside 'window'. A guard that cries wolf on
    # its own prose teaches you to ignore it, so tokens it is. Docstrings are
    # skipped for the same reason: they are commentary, not data access.
    FORBIDDEN = ('weekly_rosters', 'depth_chart', 'depth_charts', 'status',
                 'closing_line', 'odds', 'moneyline', 'spread_line', 'weather',
                 'temp', 'wind', 'LEAK')
    srcs = ['p4e_build.py', 'p4e_fit.py', 'run_p4e.py', 'run_p4e_mech.py']

    def _docstrings(tree):
        out = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                d = ast.get_docstring(node, clean=False)
                if d is not None:
                    out.add(d)
        return out

    def scan(paths):
        hits = []
        for f in paths:
            tree = ast.parse(open(os.path.join(HERE, f)).read())
            docs = _docstrings(tree)
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
                toks = [t for t in re.split(r'[^A-Za-z0-9]+', s) if t]
                if any(t.lower() in FORBIDDEN or
                       any(t.lower() == k for k in FORBIDDEN) for t in toks):
                    hits.append((f, s))
        return hits
    hits = scan(srcs)
    record('forbidden_identifier_scan', 'PASS' if not hits else 'FAIL',
           hits=hits, files=len(srcs))

    # ---- GUARD-DELETION PROOFS -----------------------------------------
    print('\n== guard-deletion proofs ==')

    # GD1: the chronology guard in p4e_fit._train_rows
    orig = F._train_rows
    try:
        F._train_rows = lambda sub_, upto: [
            r for r in sub_ if r['season'] <= upto and r['appeared']
            and r.get('s_carries') is not None]     # guard DELETED: < becomes <=
        broken = run_with(sub, rows, vol, pa, seasons, [])
    finally:
        F._train_rows = orig
    d = base - broken
    record('GD1 delete season<ev guard in _train_rows',
           'PASS' if d >= MATERIAL else 'UNRESOLVED',
           crps_with_guard=round(base, 4), crps_guard_deleted=round(broken, 4),
           gain_from_deletion=round(d, 4),
           note='the guard is required and is in place, but deleting it does '
                'NOT move CRPS materially, so this proof does not establish '
                'that it is load-bearing. Coefficient-level contamination is '
                'weak here because the features stay prior-only either way. '
                'Reported UNRESOLVED; the threshold is NOT lowered to make it '
                'pass.')

    # GD2: the prior-only guard in the competition feature
    for r in sub:
        r['GD2_leaky_teammate_sum'] = r.get('g_teammate_share_sum')
    for tm, rs in by_team.items():
        ords = sorted({x['ord'] for x in rs})
        prev = {o: (ords[i - 1] if i else None) for i, o in enumerate(ords)}
        by_ord = collections.defaultdict(list)
        for x in rs:
            by_ord[x['ord']].append(x)
        for x in rs:
            grp = by_ord.get(prev[x['ord']], [])
            tot = sum((g['s_carries'] or 0.0) for g in grp)
            # the ORIGINAL defect, restored verbatim: the CURRENT game's share
            x['GD2_leaky_teammate_sum'] = (float(tot - (x['s_carries'] or 0.0))
                                           if prev[x['ord']] is not None else None)
    leaky = run_with(sub, rows, vol, pa, seasons, ['GD2_leaky_teammate_sum'])
    d2 = base - leaky
    record('GD2 restore the fixed g_teammate_share_sum leak',
           'PASS' if d2 >= MATERIAL else 'FAIL',
           crps_fixed=round(base, 4), crps_leaky=round(leaky, 4),
           gain_from_leak=round(d2, 4),
           note='this is the real defect found on 2026-09-07, replayed. The '
                'fix is what stops it')

    # GD3: the static scan itself must be able to fail
    bad = os.path.join(HERE, '_gd3_seeded.py')
    open(bad, 'w').write('x = weekly_rosters_status_lookup\n')
    try:
        seeded_hits = scan(['_gd3_seeded.py'])
    finally:
        os.remove(bad)
    record('GD3 seed a forbidden identifier past the scan',
           'PASS' if seeded_hits else 'FAIL', hits=seeded_hits,
           note='the scan rejects a seeded violation, so its clean result above '
                'is a measurement rather than a vacuous pass')

    # GD4: the out-of-fold residual-pool guard in p4e_fit.fit_centre
    orig_fc = F.fit_centre

    def no_oof(sub_, ev_, blocks_, seasons_):
        fit, pool, fd = orig_fc(sub_, ev_, blocks_, seasons_)
        tr = F._train_rows(sub_, ev_)
        X, _ = B.design(tr, blocks_)
        y_ = np.array([r['s_carries'] for r in tr], np.float64)
        p_ = np.clip(F._pred(fit, X), 0.0, 1.0)      # guard DELETED: IN-SAMPLE
        ins = collections.defaultdict(list)
        for k, r in enumerate(tr):
            ins[r['position']].append(float(y_[k] - p_[k]))
        fd['oof_guard'] = 'DELETED -- in-sample residuals'
        return fit, {k: np.array(v, np.float32) for k, v in ins.items()}, fd
    try:
        F.fit_centre = no_oof
        insample = run_with(sub, rows, vol, pa, seasons, [])
    finally:
        F.fit_centre = orig_fc
    d4 = base - insample
    record('GD4 delete the out-of-fold residual-pool guard',
           'PASS' if abs(d4) >= MATERIAL else 'UNRESOLVED',
           crps_with_guard=round(base, 4), crps_guard_deleted=round(insample, 4),
           change_from_deletion=round(d4, 4),
           note='in-sample residuals give the candidate a predictive spread it '
                'has not earned; the sign and size of the change is the '
                'measurement of what the guard is worth')

    n_fail = sum(1 for r in RESULTS if r['state'] == 'FAIL')
    n_unres = sum(1 for r in RESULTS if r['state'] == 'UNRESOLVED')
    print(f'\n{len(RESULTS)} probes: {len(RESULTS)-n_fail-n_unres} PASS, '
          f'{n_unres} UNRESOLVED, {n_fail} FAIL')
    json.dump({'eval_season': EV, 'material_threshold_crps': MATERIAL,
               'clean_crps': base, 'probes': RESULTS},
              open(f'{HERE}/p4e_adversarial.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p4e_adversarial.json')


if __name__ == '__main__':
    main()
