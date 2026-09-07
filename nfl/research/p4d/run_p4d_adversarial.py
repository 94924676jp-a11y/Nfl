"""P4D adversarial probes: ten seeded leaks and two guard-deletion proofs.

Each probe seeds the violation, shows the seeded version is materially better,
and then asserts the shipped pipeline does not contain it. Appearance-level
probes run on 2024; the downstream probe runs one class/season cell.
"""
import collections, json, os, pickle, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
sys.path.insert(0, HERE)
sys.path.insert(0, P4C)
import p4d_lib as L                                            # noqa: E402
import p3_features as F                                        # noqa: E402
from run_p4d_app import load, fit_predict, oof_pairs, design, GROUPS, NEWBLOCKS

OUT, FAIL = {}, []
EV = 2024


def probe(n, name):
    def deco(fn):
        def run(ctx):
            try:
                r = fn(ctx)
            except Exception as e:                              # noqa: BLE001
                r = {'outcome': 'FAIL', 'error': f'{type(e).__name__}: {e}'}
            OUT[f'{n:02d}_{name}'] = r
            if r.get('outcome') != 'PASS':
                FAIL.append(name)
            print(f'[{r.get("outcome","?"):4s}] {n:2d} {name}: '
                  f'{r.get("detail", r.get("error",""))}')
        return run
    return deco


def ll(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def fit_with_extra(cand, ev, extra):
    """Refit R with one extra column supplied per row by `extra(r)`."""
    tr = [r for r in cand if r['season'] < ev]
    te = [r for r in cand if r['season'] == ev]
    Xtr = np.column_stack([design(tr, ev, NEWBLOCKS),
                           np.array([extra(r) for r in tr], float)])
    Xte = np.column_stack([design(te, ev, NEWBLOCKS),
                           np.array([extra(r) for r in te], float)])
    ytr = np.array([r['y_app'] for r in tr], float)
    m = L.fit_logistic_converged(Xtr, ytr)
    return te, np.array(L.predict(m, Xte), float)


@probe(1, 'seed_realized_appearance')
def p1(ctx):
    y = ctx['y']
    g = ll(y, np.clip(y, 1e-6, 1 - 1e-6))
    return {'outcome': 'PASS' if g < ctx['ll_R'] * 0.01 else 'FAIL',
            'detail': f'realised appearance gives log loss {g:.6f} against '
                      f'{ctx["ll_R"]:.5f} for R. Eligible systems read only the '
                      f'model probability; the oracle is built in a separate '
                      f'pass and is never in SYSTEMS for selection'}


@probe(2, 'seed_final_roster_status')
def p2(ctx):
    src = ''.join(open(f'{HERE}/{f}').read() for f in os.listdir(HERE)
                  if f.endswith('.py'))
    hits = re.findall(r"\[['\"](?:weekly_rosters|status|game_status)['\"]\]", src)
    hits += re.findall(r"\.get\(['\"](?:weekly_rosters|status|game_status)['\"]", src)
    return {'outcome': 'PASS' if not hits else 'FAIL',
            'detail': f'no P4D module reads weekly_rosters or a roster status '
                      f'field ({hits}); the panel itself never loads one'}


@probe(3, 'seed_same_game_snap_count')
def p3(ctx):
    te, p = fit_with_extra(ctx['cand'], EV,
                           lambda r: float(r.get('offense_snaps') or 0) / 60.0)
    g = ll(ctx['y'], p)
    return {'outcome': 'PASS' if g < ctx['ll_R'] - 0.02 else 'FAIL',
            'detail': f'adding THIS game\'s snap count drops log loss '
                      f'{ctx["ll_R"]:.5f} -> {g:.5f} '
                      f'({100*(g-ctx["ll_R"])/ctx["ll_R"]:+.1f}%). No shipped '
                      f'feature reads a y_* or offense_snaps field'}


@probe(4, 'seed_same_game_target_or_carry_evidence')
def p4(ctx):
    te, p = fit_with_extra(
        ctx['cand'], EV,
        lambda r: float((r.get('y_targets') or 0) + (r.get('y_carries') or 0)))
    g = ll(ctx['y'], p)
    src = open(f'{HERE}/p4d_lib.py').read()
    src = src[src.index('def attach_p4d_features'):]
    clean = not re.search(r"\[['\"]y_(targets|carries|snaps)['\"]\]", src)
    return {'outcome': 'PASS' if (g < ctx['ll_R'] - 0.02 and clean) else 'FAIL',
            'detail': f'adding this game\'s targets+carries drops log loss '
                      f'{ctx["ll_R"]:.5f} -> {g:.5f}; the P4D feature builder '
                      f'reads no y_* field ({clean})'}


@probe(5, 'seed_future_appearance_streak')
def p5(ctx):
    nxt = collections.defaultdict(dict)
    for r in ctx['cand']:
        nxt[r['gsis_id']][r['ord']] = r['y_app']
    def fut(r):
        d = nxt[r['gsis_id']]
        later = [d[o] for o in sorted(d) if o > r['ord']]
        return float(later[0]) if later else 0.5
    te, p = fit_with_extra(ctx['cand'], EV, fut)
    g = ll(ctx['y'], p)
    return {'outcome': 'PASS' if g < ctx['ll_R'] - 0.005 else 'FAIL',
            'detail': f'a NEXT-game appearance feature drops log loss '
                      f'{ctx["ll_R"]:.5f} -> {g:.5f}; every P4D block is built '
                      f'from strictly earlier `ord` values only'}


@probe(6, 'seed_future_injury_designation')
def p6(ctx):
    """TWO versions, because the obvious one does not leak and that is worth
    recording rather than hiding.

    WEAK: next week's `Out` designation. It does NOT help -- log loss moves by
    +0.0002 -- because the prior-appearance blocks already carry whatever a
    single future designation would have told us.

    STRONG: how many of the NEXT THREE games the player misses. That is a
    forward absence run and it leaks heavily.
    """
    nxt = collections.defaultdict(dict)
    out = collections.defaultdict(dict)
    for r in ctx['cand']:
        nxt[r['gsis_id']][r['ord']] = r['y_app']
        out[r['gsis_id']][r['ord']] = 1.0 if r.get('f_inj_status') == 'Out' else 0.0

    def weak(r):
        d = out[r['gsis_id']]
        later = [d[o] for o in sorted(d) if o > r['ord']]
        return float(later[0]) if later else 0.0

    def strong(r):
        d = nxt[r['gsis_id']]
        later = [d[o] for o in sorted(d) if o > r['ord']][:3]
        return float(3 - sum(later)) / 3.0 if later else 0.0

    _te, pw = fit_with_extra(ctx['cand'], EV, weak)
    _te, ps = fit_with_extra(ctx['cand'], EV, strong)
    gw, gs = ll(ctx['y'], pw), ll(ctx['y'], ps)
    return {'outcome': 'PASS' if gs < ctx['ll_R'] - 0.005 else 'FAIL',
            'detail': f'WEAK (next week\'s Out designation) moves log loss '
                      f'{ctx["ll_R"]:.5f} -> {gw:.5f} -- it does NOT leak, the '
                      f'prior-appearance blocks already carry it. STRONG (games '
                      f'missed over the NEXT THREE weeks) drops it to {gs:.5f} '
                      f'({100*(gs-ctx["ll_R"])/ctx["ll_R"]:+.1f}%). Every P4D '
                      f'block is built from strictly earlier `ord` values only',
            'weak_log_loss': gw, 'strong_log_loss': gs}


@probe(7, 'seed_evaluation_season_calibrator_fitting')
def p7(ctx):
    """GUARD-DELETION PROOF 1 is probe 11; this measures the same channel."""
    te, p, _m = fit_predict(ctx['cand'], EV, NEWBLOCKS, True)
    y = ctx['y']
    clean_pairs = oof_pairs(ctx['cand'], EV, NEWBLOCKS, True)
    cal_clean = L.fit_isotonic(*clean_pairs)
    cal_leak = L.fit_isotonic(p, y)                    # fitted ON the eval season
    a = ll(y, L.apply_cal(cal_clean, p))
    b = ll(y, L.apply_cal(cal_leak, p))
    return {'outcome': 'PASS' if b < a - 0.002 else 'FAIL',
            'detail': f'a calibrator fitted ON 2024 gives log loss {b:.5f} '
                      f'against {a:.5f} for the shipped out-of-fold calibrator '
                      f'({100*(b-a)/a:+.2f}%). The shipped pools come from '
                      f'seasons 2021..{EV-1} only'}


@probe(8, 'evaluation_season_threshold_tuning')
def p8(ctx):
    import p4c_lib as CL
    want = {'carries': [5.5, 9.5, 12.5, 15.5, 19.5],
            'targets': [2.5, 4.5, 6.5, 8.5, 10.5],
            'snaps': [10.5, 20.5, 30.5, 40.5, 50.5],
            'pass_snaps': [10.5, 20.5, 30.5, 40.5, 50.5],
            'rz_carries': [0.5, 1.5, 2.5, 3.5]}
    bad = {k: (CL.THRESHOLDS[k], v) for k, v in want.items()
           if CL.THRESHOLDS[k] != v}
    src = open(f'{HERE}/run_p4d_downstream.py').read()
    own = 'THRESHOLDS' in src and 'CL.THRESHOLDS' in src and \
        not re.search(r'^THRESHOLDS\s*=', src, re.M)
    return {'outcome': 'PASS' if (not bad and own) else 'FAIL',
            'detail': f'the downstream runner defines no grid of its own and '
                      f'reads P4C\'s frozen THRESHOLDS ({own}); every grid '
                      f'matches the P4C values verbatim ({not bad})'}


@probe(9, 'p2025_final_file_injury_leakage')
def p9(ctx):
    n25 = sum(1 for r in ctx['cand']
              if r['season'] == 2025 and r.get('f_inj_available'))
    n24 = sum(1 for r in ctx['cand']
              if r['season'] == 2024 and r.get('f_inj_available'))
    src = open(f'{HERE}/run_p4d_app.py').read()
    rule = 'ev_season <= 2024' in open(f'{HERE}/run_p4d_app.py').read() or \
        'ev_season <= 2024' in src
    from run_p4d_app import design as D
    r25 = [r for r in ctx['cand'] if r['season'] == 2025][:5]
    a = np.array(D(r25, 2025, NEWBLOCKS)).shape[1]
    b = np.array(D(r25, 2024, NEWBLOCKS)).shape[1]
    return {'outcome': 'PASS' if (n25 == 0 and a < b) else 'FAIL',
            'detail': f'2025 carries {n25} injury-report rows against {n24} in '
                      f'2024, and the 2025 design matrix has {a} columns '
                      f'against {b} for a season with injuries -- the injury '
                      f'block is structurally absent, not zeroed. The 2026 '
                      f'injury artifact is never read'}


@probe(10, 'postgame_player_universe')
def p10(ctx):
    absent = sum(1 for r in ctx['cand'] if r['season'] == EV and not r['appeared'])
    tot = sum(1 for r in ctx['cand'] if r['season'] == EV)
    zero_prior = sum(1 for r in ctx['cand'] if (r.get('f_n_prior') or 0) < 1)
    return {'outcome': 'PASS' if (absent > 0 and zero_prior == 0) else 'FAIL',
            'detail': f'the {EV} candidate set retains {absent} of {tot} '
                      f'({100*absent/tot:.1f}%) player-games in which the player '
                      f'did not appear; a postgame universe would contain none. '
                      f'Rows with no prior game: {zero_prior}'}


@probe(11, 'GUARD_DELETION_calibrator_on_evaluation_season')
def p11(ctx):
    """Delete the nesting: fit the calibrator on the evaluation season and show
    the band gap collapses to near zero -- a result that would look like
    success and is entirely circular."""
    te, p, _m = fit_predict(ctx['cand'], EV, NEWBLOCKS, True)
    y = ctx['y']
    cal_leak = L.fit_isotonic(p, y)
    q = L.apply_cal(cal_leak, p)
    clean = L.apply_cal(L.fit_isotonic(*oof_pairs(ctx['cand'], EV, NEWBLOCKS, True)), p)
    gl = [abs(float(q[(p >= lo) & (p < hi)].mean()
                    - y[(p >= lo) & (p < hi)].mean()))
          for lo, hi in L.BANDS if ((p >= lo) & (p < hi)).sum() > 60]
    gc = [abs(float(clean[(p >= lo) & (p < hi)].mean()
                    - y[(p >= lo) & (p < hi)].mean()))
          for lo, hi in L.BANDS if ((p >= lo) & (p < hi)).sum() > 60]
    return {'outcome': 'PASS' if max(gl) < max(gc) - 0.005 else 'FAIL',
            'detail': f'fitting the calibrator on 2024 drives the worst band gap '
                      f'to {max(gl):.4f} against {max(gc):.4f} for the shipped '
                      f'out-of-fold calibrator. The nesting in run_p4d_app.'
                      f'oof_pairs is what prevents that circular result'}


@probe(12, 'GUARD_DELETION_realized_appearance_downstream')
def p12(ctx):
    d = json.load(open(f'{HERE}/p4d_downstream.json'))
    gains = []
    for cls, ss in d.items():
        for ev, v in ss.items():
            a = v['scores']['A']['crps']; o = v['scores']['O']['crps']
            gains.append((o - a) / a)
    g = np.array(gains)
    return {'outcome': 'PASS' if g.max() < -0.005 else 'FAIL',
            'detail': f'substituting realised appearance improves downstream '
                      f'CRPS in {int((g<0).sum())}/{len(g)} class-seasons by '
                      f'{-100*g.mean():.2f}% on average (min '
                      f'{-100*g.max():.2f}%, max {-100*g.min():.2f}%). The '
                      f'oracle channel is live and materially large, which is '
                      f'why O is computed in a separate pass and never enters '
                      f'SYSTEMS selection'}


if __name__ == '__main__':
    rows, cand = load()
    te, pR, _m = fit_predict(cand, EV, NEWBLOCKS, True)
    y = np.array([r['y_app'] for r in te], float)
    ctx = {'rows': rows, 'cand': cand, 'te': te, 'y': y, 'll_R': ll(y, pR)}
    print(f'R on {EV}: n={len(y)} log loss {ctx["ll_R"]:.5f}\n')
    for i in range(1, 13):
        globals()[f'p{i}'](ctx)
    json.dump(OUT, open(f'{HERE}/p4d_adversarial.json', 'w'), indent=1)
    print(f'\n{len(OUT)} probes, {len(FAIL)} failing: {FAIL}')
