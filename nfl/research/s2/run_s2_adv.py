"""Stage 2: PA-5 chronology masking, and the seeded participation leaks.

Materiality for a seeded leak is 10% relative MAE improvement, fixed in
predeclaration_s2.md section 9 and not lowered here.
"""
import collections, copy, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s2_lib as L                                             # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..', 'p4c'))
import p4c_build as CB                                         # noqa: E402

MATERIAL = 0.10
OUTCOME_FIELDS = ('s_pass_snaps', 'y_pass_snaps', 'pass_snaps', 's_snaps',
                  'y_snaps', 'offense_snaps', 'offense_pct', 'appeared',
                  'did_not_appear', 's_targets', 'y_targets', 'targets',
                  'target_share', 'rpr')
RESULTS = []


def record(name, state, **kw):
    RESULTS.append(dict(probe=name, state=state, **kw))
    print(f'  {state:11s} {name:38s} ' +
          ' '.join(f'{k}={v}' for k, v in kw.items() if k != 'note'))


def score(sub, pa, predictor, positions=L.POS):
    p, y = [], []
    for ev in L.EVAL:
        for r in sub:
            if not L.eligible(r, ev) or r['position'] not in positions:
                continue
            v = predictor(r)
            if v is None:
                continue
            p.append(min(max(float(v), 0.0), 1.0))
            y.append(float(r[L.TARGET]))
    return L.metrics(p, y)


def main():
    t0 = time.time()
    rows, sub = L.load()
    L.attach(sub)
    pa = CB.appearance(rows)
    base = score(sub, pa, lambda r: r['q_ewma2'] if r['q_ewma2'] is not None
                 else r['q_pos_mean'])
    print(f"== PA-5 chronology masking audit ==")
    OUT = {'material_threshold_relative_mae': MATERIAL,
           'clean_mae': base['mae'], 'masking': {}}

    QF = sorted({k for r in sub for k in r if k.startswith('q_')})
    ords = sorted({r['ord'] for r in sub})
    probes = [ords[len(ords) // 4], ords[len(ords) // 2],
              ords[3 * len(ords) // 4], ords[-3]]
    allbad = collections.Counter()
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
            for g in [g for g in r if g.startswith('q_')]:
                del r[g]
        L.attach(masked)
        mm = {(r['team'], r['gsis_id']): r for r in masked if r['ord'] == k}
        bad = collections.Counter()
        n_cmp = 0
        for r in [x for x in sub if x['ord'] == k]:
            m = mm.get((r['team'], r['gsis_id']))
            if m is None:
                continue
            for f in QF:
                a, b = r.get(f), m.get(f)
                n_cmp += 1
                if a is None and b is None:
                    continue
                if a is None or b is None or abs(float(a) - float(b)) > 1e-12:
                    bad[f] += 1
        allbad.update(bad)
        OUT['masking'][str(k)] = {'rows_blanked': nb, 'values_compared': n_cmp,
                                  'leaking': dict(bad)}
        print(f'  ord >= {k}: {nb} blanked, {n_cmp} values compared, '
              f'{"CLEAN" if not bad else "LEAKING " + str(dict(bad))}')
    OUT['PA_5'] = 'PASS' if not allbad else f'FAIL {dict(allbad)}'
    print(f"  PA-5: {OUT['PA_5']}")

    # ---- seeded leaks ---------------------------------------------------
    print(f'\n== seeded participation leaks (clean MAE {base["mae"]:.4f}) ==')
    for r in sub:
        r['LEAK_current_participation'] = r.get(L.TARGET)
        r['LEAK_current_snapshare'] = r.get('s_snaps')
        r['LEAK_current_targetshare'] = r.get('s_targets')
        r['LEAK_postgame_state'] = 1.0 if r['appeared'] else 0.0
        # ordinal, because the raw field is a string and a probe that dies on
        # a type error has not tested anything
        r['LEAK_status'] = {'Out': 0.0, 'Doubtful': 0.25, 'Questionable': 0.6,
                            'Probable': 0.9}.get(r.get('f_inj_status'), 1.0)
    byp = collections.defaultdict(list)
    for r in sub:
        byp[r['gsis_id']].append(r)
    for _pid, seq in byp.items():
        seq.sort(key=lambda x: x['ord'])
        for i, r in enumerate(seq):
            nx = seq[i + 1] if i + 1 < len(seq) else None
            r['LEAK_future_participation'] = (None if nx is None
                                              else nx.get(L.TARGET))
    byteam = collections.defaultdict(list)
    for r in sub:
        byteam[(r['team'], r['ord'])].append(r)
    for _k, grp in byteam.items():
        for r in grp:
            o = [x for x in grp if x['gsis_id'] != r['gsis_id']]
            r['LEAK_future_teammate_state'] = (
                float(np.mean([1.0 if x['appeared'] else 0.0 for x in o]))
                if o else None)
            r['LEAK_teammate_participation'] = (
                float(np.mean([x[L.TARGET] for x in o
                               if x.get(L.TARGET) is not None]))
                if any(x.get(L.TARGET) is not None for x in o) else None)

    def blended(field, w=0.7):
        def f(r):
            v = r.get(field)
            b = r['q_ewma2'] if r['q_ewma2'] is not None else r['q_pos_mean']
            if v is None:
                return b
            return w * float(v) + (1 - w) * (b if b is not None else 0.0)
        return f

    for name, field in (
            ('current_game_participation', 'LEAK_current_participation'),
            ('current_game_snap_share', 'LEAK_current_snapshare'),
            ('current_game_target_data', 'LEAK_current_targetshare'),
            ('future_participation', 'LEAK_future_participation'),
            ('postgame_roster_state', 'LEAK_postgame_state'),
            ('forbidden_status_field', 'LEAK_status'),
            ('future_teammate_state', 'LEAK_future_teammate_state'),
            ('teammate_current_participation', 'LEAK_teammate_participation')):
        try:
            m = score(sub, pa, blended(field))
        except (TypeError, ValueError) as exc:
            record(name, 'UNRESOLVED', why=str(exc)[:50])
            continue
        gain = (base['mae'] - m['mae']) / base['mae']
        record(name, 'PASS' if gain >= MATERIAL else 'UNRESOLVED',
               seeded_mae=round(m['mae'], 4), clean=round(base['mae'], 4),
               rel_gain=f'{gain:+.1%}')

    # identifier leakage: a per-player identity code as a "feature"
    ids = {p: i for i, p in enumerate(sorted(byp))}
    for r in sub:
        r['LEAK_identifier'] = ids[r['gsis_id']] / max(len(ids), 1)
    m = score(sub, pa, blended('LEAK_identifier'))
    g = (base['mae'] - m['mae']) / base['mae']
    record('identifier_leakage', 'PASS' if g >= MATERIAL else 'UNRESOLVED',
           seeded_mae=round(m['mae'], 4), rel_gain=f'{g:+.1%}',
           note='a bare identifier carries no participation signal, so this '
                'probe is expected not to fire; reported UNRESOLVED, not PASS')

    # Ambiguous zero treated as a real zero. The weak form -- substituting on
    # the EVALUATION rows -- is degenerate, because eligibility already
    # requires the target to be present, so there is nothing to substitute. The
    # well-posed form injects the conflation into the HISTORY, which is where
    # it would actually happen.
    m_weak = score(sub, pa, lambda r: 0.0 if r.get(L.TARGET) is None else
                   (r['q_ewma2'] if r['q_ewma2'] is not None else r['q_pos_mean']))
    record('ambiguous_zero_as_real_zero_weak', 'UNRESOLVED',
           degraded_mae=round(m_weak['mae'], 4), clean=round(base['mae'], 4),
           note='degenerate: eligibility requires the target to be present, so '
                'this probe has nothing to substitute and cannot fire')
    hist0 = collections.defaultdict(list)
    hist0o = collections.defaultdict(list)
    import bisect as _bz
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        k = _bz.bisect_left(hist0o[r['gsis_id']], r['ord'])
        past = hist0[r['gsis_id']][:k]
        vals = [(x[L.TARGET] if x.get(L.TARGET) is not None else 0.0)
                for x in past if x['appeared']]
        r['q_ewma2_zeroed'] = L.ewma(vals, 2.0) if vals else None
        hist0[r['gsis_id']].append(r)
        hist0o[r['gsis_id']].append(r['ord'])
    m = score(sub, pa, lambda r: (r['q_ewma2_zeroed']
                                  if r['q_ewma2_zeroed'] is not None
                                  else r['q_pos_mean']))
    ch = (m['mae'] - base['mae']) / base['mae']
    record('ambiguous_zero_as_real_zero_in_history',
           'PASS' if abs(ch) >= MATERIAL else 'UNRESOLVED',
           degraded_mae=round(m['mae'], 4), clean=round(base['mae'], 4),
           rel_change=f'{ch:+.1%}')

    # denominator corruption
    def corrupt(r):
        b = r['q_ewma2'] if r['q_ewma2'] is not None else r['q_pos_mean']
        return None if b is None else b * 1.5
    m = score(sub, pa, corrupt)
    record('denominator_corruption', 'PASS' if
           (m['mae'] - base['mae']) / base['mae'] >= MATERIAL else 'UNRESOLVED',
           corrupted_mae=round(m['mae'], 4), clean=round(base['mae'], 4),
           rel_change=f'{(m["mae"]-base["mae"])/base["mae"]:+.1%}')

    # ---- guard-deletion proofs ------------------------------------------
    print('\n== guard-deletion proofs ==')
    # GD-1: the strictly-earlier-ordinal prefix cut in L.attach
    import bisect as _b
    orig = _b.bisect_left
    try:
        _b.bisect_left = lambda a, x: len(a)      # guard DELETED
        sub2 = copy.deepcopy(sub)
        for r in sub2:
            for g in [g for g in r if g.startswith('q_')]:
                del r[g]
        L.attach(sub2)
    finally:
        _b.bisect_left = orig
    dup = 0
    seen = collections.Counter()
    for r in sub:
        seen[(r['gsis_id'], r['ord'])] += 1
    dup = sum(1 for k, v in seen.items() if v > 1)
    diff = 0
    m2 = {(r['team'], r['gsis_id'], r['ord']): r for r in sub2}
    for r in sub:
        o = m2.get((r['team'], r['gsis_id'], r['ord']))
        if o and (r.get('q_last') != o.get('q_last')
                  or r.get('q_n_prior_app') != o.get('q_n_prior_app')):
            diff += 1
    record('GD-1 delete the strictly-earlier-ordinal cut',
           'PASS' if diff > 0 else 'UNRESOLVED',
           same_week_duplicate_player_ordinals=dup,
           rows_whose_history_changed=diff,
           note='without the cut, a player who changed team mid-week reads his '
                'own same-week row as history')

    # GD-2: the appearance condition on the history
    def no_app_filter(r):
        return r.get('q_ewma2_all')
    for r in sub:
        pass
    hist = collections.defaultdict(list)
    hist_ord = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        k = _b.bisect_left(hist_ord[r['gsis_id']], r['ord'])
        past = hist[r['gsis_id']][:k]
        vals = [x[L.TARGET] for x in past if x.get(L.TARGET) is not None]
        r['q_ewma2_all'] = L.ewma(vals, 2.0) if vals else None
        hist[r['gsis_id']].append(r)
        hist_ord[r['gsis_id']].append(r['ord'])
    m = score(sub, pa, lambda r: (r['q_ewma2_all'] if r['q_ewma2_all'] is not None
                                  else r['q_pos_mean']))
    ch = (m['mae'] - base['mae']) / base['mae']
    record('GD-2 delete the appeared-only condition on history',
           'PASS' if abs(ch) >= MATERIAL else 'UNRESOLVED',
           without_guard_mae=round(m['mae'], 4), clean=round(base['mae'], 4),
           rel_change=f'{ch:+.1%}',
           note='a did-not-appear game has participation share 0 by definition; '
                'letting it into the history is the classic zero/N-A conflation')

    nf = sum(1 for r in RESULTS if r['state'] == 'FAIL')
    nu = sum(1 for r in RESULTS if r['state'] == 'UNRESOLVED')
    gd = sum(1 for r in RESULTS
             if r['probe'].startswith('GD-') and r['state'] == 'PASS')
    print(f'\n{len(RESULTS)} probes: {len(RESULTS)-nf-nu} PASS, {nu} UNRESOLVED, '
          f'{nf} FAIL; {gd} guard-deletion proofs firing')
    OUT['probes'] = RESULTS
    OUT['guard_deletion_proofs_firing'] = gd
    json.dump(OUT, open(f'{HERE}/s2_adversarial.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> s2_adversarial.json')


if __name__ == '__main__':
    main()
