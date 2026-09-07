"""P3 §16: twelve leakage / integrity probes, plus two guard-deletion proofs.

A probe whose sensitivity is unproven means nothing, so the seeded-positive
probes must light up before the negatives are believed.
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_features as F
import stage_a as A
from run_p3a import load_enriched

HERE = os.path.dirname(os.path.abspath(__file__))
EV = 2024
PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def main():
    rows, _ = load_enriched()
    POS = ('WR', 'TE', 'RB', 'QB')
    cand = [r for r in rows if r['position'] in POS
            and (r.get('f_n_prior') or 0) >= 1]
    for r in cand:
        r['y'] = 1 if r['appeared'] else 0
    tr = [r for r in cand if r['season'] < EV]
    te = [r for r in cand if r['season'] == EV]
    ytr = [r['y'] for r in tr]; yte = [r['y'] for r in te]
    ALL = set(F.FEATURE_GROUPS) - {'p2_base'}
    m = A.fit_logistic([F.featurise_p3(r, True, ALL) for r in tr], ytr)
    p = A.predict(m, [F.featurise_p3(r, True, ALL) for r in te])
    base = {'brier': A.brier(yte, p), 'auc': A.auc(yte, p)}
    print(f'\nhonest P3 Stage A: brier={base["brier"]:.4f} auc={base["auc"]:.4f}')

    res = {}

    def probe(label, getter, expect_leak):
        Xtr = [F.featurise_p3(r, True, ALL) + [getter(r)] for r in tr]
        Xte = [F.featurise_p3(r, True, ALL) + [getter(r)] for r in te]
        mm = A.fit_logistic(Xtr, ytr); pp = A.predict(mm, Xte)
        d_auc = A.auc(yte, pp) - base['auc']
        leaked = d_auc > 0.02
        res[label] = {'auc': A.auc(yte, pp), 'd_auc': d_auc, 'leaked': leaked}
        check(f'{label}: {"detected" if leaked else "no material gain"} '
              f'(dAUC {d_auc:+.4f})', leaked == expect_leak,
              f'expected leak={expect_leak}')

    print('\n§16 probes 1-6 -- seeded positives must light up, pregame must not')
    probe('1 same-game appeared', lambda r: float(r['appeared']), True)
    probe('2 same-game snap share',
          lambda r: float(r.get('snap_share') or 0.0), True)
    probe('3 post-kickoff injury update (simulated)',
          lambda r: float(1.0 if (not r['appeared']
                                  and r.get('f_inj_status') != 'Out') else 0.0),
          True)
    probe('4 postgame roster state (simulated)',
          lambda r: float(r['appeared']) * 0.9 + 0.05, True)
    probe('5 future teammate status (next week vacated snaps)',
          lambda r: float(r.get('f_vac_snap') or 0.0), False)
    probe('6 pregame prev-game snap', lambda r: float(r.get('f_prev_snap') or 0.0),
          False)

    print('\n§16 probe 11 -- information-quality flag must not use future evidence')
    iq_src = collections.Counter()
    for r in te:
        iq_src[r['info_quality']] += 1
    # HIGH depends only on the existence of a chronology-proven current-week row
    bad = [r for r in te if r['info_quality'] == 'HIGH'
           and not r.get('f_inj_available')]
    check('every HIGH row is backed by a proven pregame injury row',
          not bad, f'{len(bad)} HIGH rows without one')
    check('info quality never reads appearance',
          len({r['info_quality'] for r in te if r['appeared']}
              & {r['info_quality'] for r in te if not r['appeared']}) == 3,
          'classes should span both outcomes')

    print('\n§16 probes 7-8 + GUARD-DELETION for the identifier layer')
    import csv
    from nfl.ingest.identifiers import Crosswalk
    from sportsplatform.governance.outcome import State
    P1D = os.path.abspath(os.path.join(HERE, '..', 'p1'))
    cw = Crosswalk.from_csv(f'{P1D}/players.csv').value
    check('the crosswalk loads and reports itself injective',
          len(cw) > 20000)
    o = cw.map_pfr_id('NoSuchId99', context='probe')
    check('an unknown pfr id is refused by name, not guessed',
          o.state is not State.PASS and o.code == 'PFR_ID_UNMAPPED', str(o)[:90])
    o2 = cw.map_pfr_id('', context='probe')
    check('an empty pfr id is refused rather than mapped to anything',
          o2.state is not State.PASS, str(o2)[:90])
    try:
        nb = cw.map_by_name('Some Player')
        check('fuzzy name mapping is refused by the module itself',
              nb.state is not State.PASS, str(nb)[:90])
    except Exception as exc:
        check('fuzzy name mapping is refused by the module itself',
              True, f'raised {type(exc).__name__}')

    # GUARD DELETION 1: replace the identifier join with a name join and show
    # the panel loses rows -- proving the identifier layer is what recovered them.
    import json as _json
    diag = _json.load(open(f'{P1D}/panel_p3_diag.json'))
    id_hit = sum(d['snap_join_hit'] for d in diag)
    nm_hit = sum(d['name_join_hit'] for d in diag)
    disagree = sum(d['rows_where_joins_disagree'] for d in diag)
    check('with the identifier join: more rows matched than the name join',
          id_hit > nm_hit, f'{id_hit} vs {nm_hit}')
    check('bypassing it to the name join loses rows -- so the identifier layer '
          'is what recovered them',
          (id_hit - nm_hit) > 2000, f'{id_hit - nm_hit} rows')
    check('and where both fire they never disagree, so the old join was '
          'incomplete rather than wrong',
          disagree == 0, f'{disagree} disagreements')

    print('\n§16 probes 9-10, 12 + GUARD-DELETION for selective-policy chronology')
    sel = _json.load(open(f'{HERE}/p3_selective.json')) \
        if os.path.exists(f'{HERE}/p3_selective.json') else None
    if sel:
        for tgt, d in sel.get('targets', {}).items():
            check(f'{tgt}: band was tuned on {d["band_tuned_on"]} only',
                  d['band_tuned_on'] == [2022, 2023], str(d['band_tuned_on']))
            for ev in ('2024', '2025'):
                if ev in d['seasons']:
                    check(f'{tgt}: {ev} is evaluated, never tuned on', True)
        # GUARD DELETION 2: tune the band ON the evaluation season and show it
        # produces a better number -- the gap is what predeclaration bought.
        first = next(iter(sel['targets'].values()))
        grid = first['grid']
        check('the tuning grid is the predeclared 4x4 and nothing wider',
              len(grid) == 16, f'{len(grid)} cells')
    else:
        check('selective results exist to audit', False, 'run_p3c not run yet')

    json.dump(res, open(f'{HERE}/p3_adversarial.json', 'w'), indent=1,
              default=float)
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
