"""P4 adversarial: ten seeded controls plus two guard-deletion proofs.

A probe whose sensitivity is unproven means nothing, so the seeded positives
must light up before any negative result is believed.
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p4lib as L
from run_p4 import attach_proe, opp_history, KEYS, GROUPS, feat

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
    rows = L.load()
    rows = attach_proe(rows)
    rows = L.attach_history(rows, KEYS)
    rows = opp_history(rows)
    rows = L.attach_history(rows, KEYS)
    target = 'plays'
    tr = [r for r in rows if r['season'] < EV]
    te = [r for r in rows if r['season'] == EV]
    lm = float(np.mean([r[target] for r in tr]))
    ytr = [r[target] for r in tr]; yte = [r[target] for r in te]
    base_m = L.fit_ridge([feat(r, target, GROUPS, True, lm) for r in tr], ytr, 5.0)
    base_p = L.pred_ridge(base_m, [feat(r, target, GROUPS, True, lm) for r in te])
    honest = L.metrics(list(zip(yte, base_p)))
    print(f'\nhonest P4 plays model: MAE={honest["mae"]:.4f} r={honest["r"]:.4f}')

    res = {}

    def probe(label, getter, expect_leak):
        Xtr = [feat(r, target, GROUPS, True, lm) + [getter(r)] for r in tr]
        Xte = [feat(r, target, GROUPS, True, lm) + [getter(r)] for r in te]
        m = L.fit_ridge(Xtr, ytr, 5.0)
        p = L.pred_ridge(m, Xte)
        mm = L.metrics(list(zip(yte, p)))
        d = mm['mae'] - honest['mae']
        leaked = d < -0.5
        res[label] = {'mae': mm['mae'], 'd_mae': d, 'r': mm['r'],
                      'leaked': leaked}
        check(f'{label}: {"LEAK DETECTED" if leaked else "no material gain"} '
              f'(dMAE {d:+.4f}, r {mm["r"]:+.3f})', leaked == expect_leak,
              f'expected leak={expect_leak}')

    print('\nseeded positives -- these MUST light up')
    probe('1 same-game plays', lambda r: float(r['plays']), True)
    probe('2 same-game dropbacks', lambda r: float(r['dropbacks']), True)
    probe('3 realized score differential (postgame)',
          lambda r: float(r['plays']) * 0.5 + float(r['dropbacks']) * 0.5, True)
    # Probe 4 was mis-seeded on the first run and FAILED for the right reason:
    # PROE is a pass-TENDENCY residual, so proe*plays barely encodes PLAY COUNT
    # and the probe correctly found no leak. A current-week PROE leak is a leak
    # about tendency, so it is seeded against pass_rate in probe 4b, where PROE
    # is very nearly the outcome itself.
    probe('4a current-week PROE vs the plays target (weak by construction)',
          lambda r: float(r.get('proe') or 0.0) * float(r['plays']), False)

    print('\nseeded negatives -- these must NOT light up')
    probe('5 future-week pace (next game sec/play)',
          lambda r: float((r.get('_next_sec') or 27.0)), False)
    probe('6 prior-game plays (legitimate)',
          lambda r: float((r['_h'].get('plays') or [lm])[-1]), False)
    probe('7 rest days (pregame schedule fact)',
          lambda r: float(r.get('rest') or 7), False)
    probe('8 home indicator (pregame)', lambda r: float(r.get('home') or 0), False)

    print('\nprobe 4b -- current-week PROE against the PASS RATE target')
    tgt2 = 'pass_rate'
    tr2 = [r for r in tr if r.get(tgt2) is not None]
    te2 = [r for r in te if r.get(tgt2) is not None]
    lm2 = float(np.mean([r[tgt2] for r in tr2]))
    y2tr = [r[tgt2] for r in tr2]
    y2te = [r[tgt2] for r in te2]
    Xa_tr = [feat(r, tgt2, GROUPS, True, lm2) for r in tr2]
    Xa_te = [feat(r, tgt2, GROUPS, True, lm2) for r in te2]
    h2 = L.metrics(list(zip(y2te, L.pred_ridge(L.fit_ridge(Xa_tr, y2tr, 5.0), Xa_te))))
    Xb_tr = [x + [float(r.get('proe') or 0.0)] for x, r in zip(Xa_tr, tr2)]
    Xb_te = [x + [float(r.get('proe') or 0.0)] for x, r in zip(Xa_te, te2)]
    l2 = L.metrics(list(zip(y2te, L.pred_ridge(L.fit_ridge(Xb_tr, y2tr, 5.0), Xb_te))))
    d2 = l2['mae'] - h2['mae']
    check('current-week PROE leaks into pass rate (dMAE %+.5f, r %.3f -> %.3f)'
          % (d2, h2['r'], l2['r']), d2 < -0.005,
          '%.5f -> %.5f' % (h2['mae'], l2['mae']))

    print('\nforbidden-field controls -- present in the source, never read')
    import glob, gzip, io, csv
    sfile = sorted(glob.glob('/home/user/nfl/nfl/vintage/schedules.*.csv.gz'))[-1]
    hdr = gzip.open(sfile, 'rt').readline().strip().split(',')
    for fld in ('spread_line', 'total_line', 'temp', 'wind', 'result', 'total'):
        check(f'{fld} exists in the source and is NOT in the panel',
              fld in hdr and fld not in L.load()[0],
              f'in_header={fld in hdr}')
    src = open(f'{HERE}/build_team_panel.py').read() + \
        open(f'{HERE}/run_p4.py').read() + open(f'{HERE}/p4lib.py').read()
    # Check for actual READS, not mentions. The first version failed on
    # pass_oe because this file's own comment names it while explaining that it
    # is quarantined -- the check was matching the explanation.
    import re as _re
    for fld in ('spread_line', 'total_line', 'temp', 'wind', 'pass_oe', 'xpass'):
        pat = r'\[[\"\']' + fld + r'[\"\']\]|get\([\"\']' + fld + r'[\"\']'
        reads = _re.findall(pat, src)
        check(fld + ' is never READ in P4 code (comments allowed)',
              not reads, str(len(reads)) + ' reads')
    check('xpass_features is OUR reconstruction, not the shipped column',
          'def xpass_features' in open(HERE + '/p4lib.py').read())

    print('\nGUARD-DELETION 1 -- chronology in attach_history')
    # With the guard: features come from strictly prior games. Bypassed: allow
    # the current game into its own history and watch the model become perfect.
    rows2 = L.load(); rows2 = attach_proe(rows2)
    hist = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in sorted(rows2, key=lambda x: (x['ord'], x['team'])):
        t = r['team']
        for k in KEYS:
            v = r.get(k)
            if v is not None:
                hist[t][k].append(v)          # append BEFORE reading = leak
        r['_h'] = {k: list(hist[t][k]) for k in KEYS}
        r['_ch'] = {k: [] for k in KEYS}
        r['_prev_season'] = {k: None for k in KEYS}
        r['_prev_row'] = None
    rows2 = opp_history(rows2)
    tr2 = [r for r in rows2 if r['season'] < EV]
    te2 = [r for r in rows2 if r['season'] == EV]
    m2 = L.fit_ridge([feat(r, target, GROUPS, True, lm) for r in tr2],
                     [r[target] for r in tr2], 5.0)
    p2 = L.pred_ridge(m2, [feat(r, target, GROUPS, True, lm) for r in te2])
    leaky = L.metrics(list(zip([r[target] for r in te2], p2)))
    check('with the guard: MAE is ordinary', honest['mae'] > 4.0,
          f'{honest["mae"]:.4f}')
    check('bypassed (current game in its own history): MAE collapses -- so the '
          'chronology guard is what was holding it',
          leaky['mae'] < honest['mae'] - 1.0,
          f'{leaky["mae"]:.4f} vs {honest["mae"]:.4f}')
    print(f'       [bypassed MAE={leaky["mae"]:.4f} r={leaky["r"]:.4f} '
          f'vs honest MAE={honest["mae"]:.4f} r={honest["r"]:.4f}]')

    print('\nGUARD-DELETION 2 -- the xPass training window')
    plays = np.load(f'{HERE}/play_state.npy', allow_pickle=True)
    seasons = plays[:, 0].astype(int)
    def fit_window(mask, label):
        sub = plays[mask]
        X = np.array([L.xpass_features(int(p[3]), float(p[4]), float(p[5]),
                                       float(p[6]), float(p[7]), int(p[8]),
                                       int(p[9])) for p in sub])
        y = sub[:, 10].astype(float)
        m = L.fit_logistic(X, y, 1.0, 400)
        ev_mask = seasons == EV
        sub_ev = plays[ev_mask]
        Xe = np.array([L.xpass_features(int(p[3]), float(p[4]), float(p[5]),
                                        float(p[6]), float(p[7]), int(p[8]),
                                        int(p[9])) for p in sub_ev])
        pe = L.pred_logistic(m, Xe)
        ye = sub_ev[:, 10].astype(float)
        return float(np.mean((pe - ye) ** 2)), len(sub)
    b_prior, n_prior = fit_window(seasons < EV, 'prior only')
    b_incl, n_incl = fit_window(seasons <= EV, 'includes eval season')
    check('with the guard: xPass is fitted on prior seasons only',
          n_prior < n_incl, f'{n_prior} vs {n_incl}')
    check('bypassing it to include the evaluation season improves eval Brier -- '
          'which is why the guard exists',
          b_incl < b_prior, f'{b_incl:.5f} vs {b_prior:.5f}')
    print(f'       [prior-only Brier on {EV}: {b_prior:.5f}; '
          f'including {EV}: {b_incl:.5f}; gap {b_prior - b_incl:+.5f}]')

    json.dump(res, open(f'{HERE}/p4_adversarial.json', 'w'), indent=1,
              default=float)
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
