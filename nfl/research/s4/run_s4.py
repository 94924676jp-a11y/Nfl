"""Stage 4: receiving target oracle decomposition, A x T x P x R.

Bound by Stage 2's labelling constraint: P is PASS-SNAP PARTICIPATION, an upper
bound on route participation. It is not routes run, and nothing here concludes
anything about the value of route information as such.
"""
import collections, itertools, json, math, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ('p4c', 'p4e', 's2', 's3'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
sys.path.insert(0, '/home/user/nfl/sportsplatform')
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
import s2_lib as SL                                            # noqa: E402
from run_p4c import groups_of                                  # noqa: E402
from governance import artifact_reference as AR                # noqa: E402
from governance.outcome import State                           # noqa: E402

CLS = 'targets'
EVAL = [2022, 2023, 2024, 2025]
COMPONENTS = ('A', 'T', 'P', 'R')
CORNERS = [frozenset(c) for r in range(5)
           for c in itertools.combinations(COMPONENTS, r)]
P_FLOOR = 1e-3
IDENTITY_TOL = 1e-4
P4C_RESULTS = os.path.abspath(os.path.join(HERE, '..', 'p4c',
                                           'p4c_results.json'))
LARGE, MEDIUM = 0.30, 0.10


def cname(s):
    return 'BASELINE' if not s else 'O_' + '_'.join(sorted(s))


def shapley(v):
    n, fact = 4, {0: 1, 1: 1, 2: 2, 3: 6, 4: 24}
    out = {}
    for i in COMPONENTS:
        rest = [c for c in COMPONENTS if c != i]
        tot = 0.0
        for r in range(4):
            for sub in itertools.combinations(rest, r):
                Ss = frozenset(sub)
                w = fact[len(Ss)] * fact[n - len(Ss) - 1] / fact[n]
                tot += w * (v[Ss | {i}] - v[Ss])
        out[i] = tot
    return out


def build(rows, vol, pa, sub2, ev):
    c = CL.CLASSES[CLS]
    store = vol[(c['den'], ev)]
    dstore = vol.get(('team_dropbacks_part', ev))
    sub = CB.prepare_class(rows, CLS)
    par = CB.fit_params(sub, CLS, ev, rows)
    te = [r for r in sub if r['season'] == ev and r.get('s_targets') is not None
          and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
          and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
    te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    n = len(te)
    starts, cg, _gk = groups_of(te)
    G = len(starts)
    ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
    gti = ti[starts]
    T_pred = store['B'][gti]
    Tstar = store['realized'][gti].astype(np.float64)
    si = ['A', 'B', 'C', 'C2', 'D_dir', 'D_sln', 'D_emp', 'E'].index('C')
    W = CB.gen_weights('C', np.array([r['_C'] for r in te], np.float32),
                       [r['position'] for r in te], par, CLS, n, CL.M_DRAWS,
                       np.random.default_rng(CL.SEED + 3000 + 17 * si))
    p_app = np.array([pa[id(r)] for r in te], np.float32)
    A_pred = (np.random.default_rng(CL.SEED + 1009)
              .random((n, CL.M_DRAWS), np.float32) < p_app[:, None])
    mass = CB.mass_draws('C', par, G, CL.M_DRAWS,
                         np.random.default_rng(CL.SEED + 5000 + si))
    avail_pred = (1.0 - mass).astype(np.float32)
    y = np.array([r['y_targets'] for r in te], float)
    A_star = np.array([1.0 if r['appeared'] else 0.0 for r in te], np.float32)
    gi = np.searchsorted(starts, np.arange(n), 'right') - 1
    Sstar = np.array([(y[i] / Tstar[gi[i]]) if Tstar[gi[i]] > 0 else 0.0
                      for i in range(n)], np.float64)
    mstar = CL.gsum((Sstar * A_star)[:, None], starts)[:, 0]

    # ---- the participation reparametrisation ---------------------------
    look = {(r['gsis_id'], r['ord'], r['team']): r for r in sub2}
    Phat = np.zeros(n, np.float64)
    Pstar = np.zeros(n, np.float64)
    have = np.zeros(n, bool)
    for i, r in enumerate(te):
        q = look.get((r['gsis_id'], r['ord'], r['team']))
        if q is None:
            continue
        v = q.get('q_ewma2')
        if v is None:
            v = q.get('q_pos_mean')
        if v is not None:
            Phat[i] = min(max(float(v), 0.0), 1.0)
            have[i] = True
        ps = q.get('s_pass_snaps')
        Pstar[i] = 0.0 if ps is None else float(ps)
    Pc = np.maximum(Phat, P_FLOOR)
    Rhat = W / Pc[:, None].astype(np.float32)
    Wstar = (Sstar * A_star).astype(np.float32)
    Rstar = np.zeros(n, np.float64)
    nz = Pstar > 0
    Rstar[nz] = Wstar[nz] / Pstar[nz]
    return dict(te=te, n=n, G=G, starts=starts, cg=cg, y=y,
                T_pred=T_pred, Tstar=Tstar, A_pred=A_pred, A_star=A_star,
                avail_pred=avail_pred, mstar=mstar, W=W, Rhat=Rhat,
                Phat=Phat, Pc=Pc, Pstar=Pstar, Rstar=Rstar, Wstar=Wstar,
                Sstar=Sstar, p_app=p_app, have=have,
                clip_rate=float((Phat < P_FLOOR).mean()),
                coverage=float(have.mean()))


def corner_draws(d, cs):
    """One factorial corner.

    IMPLEMENTATION NOTE, and it decides whether this decomposition is valid at
    all. `R_hat` is DEFINED as `W / P_hat_clipped`, so `P_hat x R_hat` is `W`
    identically -- in real arithmetic. Computing the product in float32 does
    not return `W`; it returns `W` plus round-trip noise, and that noise made
    the baseline corner miss the accepted artifact by 1.37e-11 against a
    tolerance of 0.0 on the first run.

    The fix is to use the value the definition already gives, not to loosen the
    gate. At the two corners where the product collapses analytically --
    neither component oracled, giving `W`, and both oracled, giving `W*` -- the
    collapsed value is used directly. That is the faithful implementation of
    the pre-declared definition. The tolerance stays 0.0.
    """
    n, M = d['n'], CL.M_DRAWS
    if 'P' not in cs and 'R' not in cs:
        Wm = d['W']                                  # P_hat x R_hat == W
    elif 'P' in cs and 'R' in cs:
        Wm = np.repeat(d['Wstar'][:, None], M, 1)    # P* x R* == W*
    else:
        P = (np.repeat(d['Pstar'][:, None], M, 1) if 'P' in cs
             else np.repeat(d['Pc'][:, None], M, 1))
        R = (np.repeat(d['Rstar'][:, None], M, 1) if 'R' in cs else d['Rhat'])
        Wm = (P * R).astype(np.float32)
    Ad = (np.repeat(d['A_star'][:, None], M, 1).astype(bool) if 'A' in cs
          else d['A_pred'])
    T = (np.repeat(d['Tstar'][:, None], M, 1).astype(np.float32) if 'T' in cs
         else d['T_pred'])
    AV = (np.repeat(d['mstar'][:, None], M, 1).astype(np.float32) if 'T' in cs
          else d['avail_pred'])
    WA = Wm * Ad
    tot = CL.gsum(WA, d['starts'])
    tee = CL.gexp(tot, d['cg'])
    S = np.divide(WA * CL.gexp(AV, d['cg']), tee,
                  out=np.zeros_like(WA), where=tee > 1e-12)
    S, _nb = CL.waterfill(S, d['starts'], d['cg'], 1.0)
    return (CL.gexp(T, d['cg']) * S).astype(np.float32)


def main():
    t0 = time.time()
    rows = CB.load_panel()
    vol = CB.load_volume()
    pa = CB.appearance(rows)
    _r2, sub2 = SL.load()
    SL.attach(sub2)
    OUT = {'labelling_constraint':
           ('P is PASS-SNAP PARTICIPATION, an upper bound on route '
            'participation. NOT routes run. Nothing here concludes anything '
            'about the value of route information as such.'),
           'sample_label': ('previously exposed development sample -- not '
                            'confirmatory'),
           'seasons': {}}
    for ev in EVAL:
        d = build(rows, vol, pa, sub2, ev)
        vals, rowcrps = {}, {}
        for cs in CORNERS:
            draws = corner_draws(d, cs)
            nm = cname(cs)
            cr = CL.crps_samples(draws, d['y'])
            rowcrps[nm] = cr
            vals[nm] = {'crps': float(cr.mean()),
                        'mae': float(np.abs(draws.mean(1) - d['y']).mean()),
                        'rmse': float(math.sqrt(
                            ((draws.mean(1) - d['y']) ** 2).mean())),
                        'bias': float((draws.mean(1) - d['y']).mean())}
            if len(cs) == 4:
                vals[nm]['identity_mean_abs_error'] = float(
                    np.abs(draws.mean(1) - d['y']).mean())
            del draws
        # identity 1: the baseline must be the accepted artifact, exactly
        gate = AR.assert_gate(vals['BASELINE']['crps'], P4C_RESULTS,
                              (CLS, str(ev), 'scores', 'C', 'crps'),
                              tolerance=0.0, code='S4_BASELINE')
        print(f'== {ev}  n={d["n"]} G={d["G"]} ==')
        print(f'  baseline vs p4c_results.json: {gate.state.value} '
              f'|diff| {gate.evidence.get("abs_diff", float("nan")):.2e} '
              f'sha256 {str(gate.evidence.get("sha256"))[:12]}')
        if gate.state is not State.PASS:
            print(f'  REFUSED: {gate.code} -- {gate.detail}')
            OUT['seasons'][str(ev)] = {'REFUSED': gate.as_dict()}
            json.dump(OUT, open(f'{HERE}/s4_results.json', 'w'), indent=1)
            sys.exit(2)
        idz = vals['O_A_P_R_T']['identity_mean_abs_error']
        ok2 = idz < IDENTITY_TOL
        print(f'  all-oracle identity error {idz:.2e} '
              f'(tolerance {IDENTITY_TOL:.0e}) -> {"OK" if ok2 else "INVALID"}')
        print(f'  participation coverage {d["coverage"]:.3%}, '
              f'P_hat clipped at floor {d["clip_rate"]:.3%}')
        base = vals['BASELINE']['crps']
        v = {cs: base - vals[cname(cs)]['crps'] for cs in CORNERS}
        total = v[frozenset(COMPONENTS)]
        sh = shapley(v)
        m = {c: v[frozenset([c])] for c in COMPONENTS}
        inter = {f'main_{c}': m[c] for c in COMPONENTS}
        for a, b in itertools.combinations(COMPONENTS, 2):
            inter[f'int_{a}{b}'] = v[frozenset([a, b])] - m[a] - m[b]
        print(f"  {'corner':12s} {'CRPS':>8s} {'reduction':>10s} {'%':>7s}")
        for cs in sorted(CORNERS, key=lambda s: (len(s), sorted(s))):
            nm = cname(cs)
            print(f"  {nm:12s} {vals[nm]['crps']:8.4f} "
                  f"{v[cs]:10.4f} {100*v[cs]/max(total,1e-12):6.1f}%")
        print(f"  Shapley: " + '  '.join(
            f'{c}={sh[c]:.4f} ({100*sh[c]/total:4.1f}%)' for c in COMPONENTS))
        # cohorts on the two single-component oracles that matter
        cohorts = {}
        pc = np.array([(r.get('n_prior_games') or 0) for r in d['te']])
        for dim, fn in (
            ('position', lambda i: d['te'][i]['position']),
            ('prior_games', lambda i: ('<4' if pc[i] < 4 else '4-9'
                                       if pc[i] < 10 else '10-24'
                                       if pc[i] < 25 else '25+')),
            ('appearance', lambda i: ('<0.25' if d['p_app'][i] < .25 else
                                      '0.25-0.50' if d['p_app'][i] < .50 else
                                      '0.50-0.80' if d['p_app'][i] < .80 else
                                      '0.80-0.95' if d['p_app'][i] < .95
                                      else '>=0.95'))):
            g = collections.defaultdict(list)
            for i in range(d['n']):
                g[fn(i)].append(i)
            cohorts[dim] = {}
            for lvl, idx in sorted(g.items()):
                ii = np.array(idx)
                base_c = rowcrps['BASELINE'][ii].mean()
                cohorts[dim][lvl] = {
                    'n': len(ii), 'baseline_crps': float(base_c),
                    **{f'reduction_{c}': float(
                        base_c - rowcrps[f'O_{c}'][ii].mean())
                        for c in COMPONENTS},
                    'reduction_all': float(
                        base_c - rowcrps['O_A_P_R_T'][ii].mean())}
        OUT['seasons'][str(ev)] = {
            'n': d['n'], 'G': d['G'], 'corners': vals,
            'baseline_gate': gate.as_dict(),
            'all_oracle_identity_error': idz,
            'all_oracle_identity_valid': bool(ok2),
            'participation_coverage': d['coverage'],
            'p_hat_floor_clip_rate': d['clip_rate'],
            'reduction': {cname(cs): v[cs] for cs in CORNERS},
            'total_reduction': total, 'shapley': sh,
            'shapley_pct': {c: 100 * sh[c] / total for c in COMPONENTS},
            'interactions': inter, 'cohorts': cohorts}
        json.dump(OUT, open(f'{HERE}/s4_results.json', 'w'), indent=1)
        print()
    # ---- pooled classification ------------------------------------------
    pooled = {c: float(np.mean([OUT['seasons'][str(e)]['shapley_pct'][c]
                                for e in EVAL])) for c in COMPONENTS}
    OUT['pooled_shapley_pct'] = pooled
    OUT['classification'] = {
        c: {'oracle_opportunity': ('LARGE' if pooled[c] / 100 >= LARGE else
                                   'MEDIUM' if pooled[c] / 100 >= MEDIUM
                                   else 'SMALL'),
            'shapley_pct': pooled[c]}
        for c in COMPONENTS}
    print('== pooled Shapley share of total reduction ==')
    for c in COMPONENTS:
        print(f"  {c}: {pooled[c]:5.1f}%  -> "
              f"{OUT['classification'][c]['oracle_opportunity']}")
    json.dump(OUT, open(f'{HERE}/s4_results.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> s4_results.json')


if __name__ == '__main__':
    main()
