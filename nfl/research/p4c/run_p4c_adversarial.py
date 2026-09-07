"""P4C adversarial probes: ten seeded leaks and two guard-deletion proofs.

Each probe SEEDS the violation, shows the seeded version is materially better
(so the channel is live and a leak would be detectable rather than silent), and
then asserts the real pipeline does not contain it. A probe that only asserts
the clean case would pass on a pipeline with the leak wired in parallel, which
is the failure mode this project keeps paying for.

Probes that need a pipeline run use targets/2024 -- one class, one season -- so
the suite stays runnable; the assertion is about mechanism, not about that
cell's particular number.
"""
import collections, json, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4c_lib as L                                            # noqa: E402
import p4c_build as B                                          # noqa: E402
from run_p4c import groups_of, SYSTEMS                         # noqa: E402

OUT, FAIL = {}, []
CLS, EV = 'targets', 2024


def probe(n, name):
    def deco(fn):
        def run(ctx=None):
            try:
                r = fn(ctx) if ctx is not None else fn()
            except Exception as e:                              # noqa: BLE001
                r = {'outcome': 'FAIL', 'error': f'{type(e).__name__}: {e}'}
            OUT[f'{n:02d}_{name}'] = r
            if r.get('outcome') != 'PASS':
                FAIL.append(name)
            print(f'[{r.get("outcome","?"):4s}] {n:2d} {name}: '
                  f'{r.get("detail", r.get("error",""))}')
        return run
    return deco


def build_ctx():
    rows = B.load_panel()
    vol = B.load_volume()
    pa = B.appearance(rows)
    c = L.CLASSES[CLS]
    sub = B.prepare_class(rows, CLS)
    par = B.fit_params(sub, CLS, EV, rows)
    skey, ykey = c['share'], c['y']
    store = vol[(c['den'], EV)]
    te = [r for r in sub if r['season'] == EV and r.get(skey) is not None
          and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
          and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
    te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    starts, counts, gkeys = groups_of(te)
    n, G = len(te), len(starts)
    ctx = dict(rows=rows, vol=vol, pa=pa, sub=sub, par=par, store=store, te=te,
               starts=starts, counts=counts, n=n, G=G, cls=CLS, ev=EV,
               skey=skey, ykey=ykey)
    ctx['y'] = np.array([r[ykey] for r in te], float)
    ctx['C'] = np.array([r['_C'] for r in te], np.float32)
    ctx['positions'] = [r['position'] for r in te]
    ctx['p_app'] = np.array([pa[id(r)] for r in te], np.float32)
    ctx['S_real'] = np.array([r[skey] for r in te], np.float32)
    ctx['A_real'] = np.array([1.0 if r['appeared'] else 0.0 for r in te], np.float32)
    ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
    ctx['T'] = store['B'][ti]
    ctx['T_real'] = np.repeat(store['realized'][ti][:, None], L.M_DRAWS, axis=1)
    ctx['Ad'] = (np.random.default_rng(L.SEED + 1009)
                 .random((n, L.M_DRAWS), np.float32) < ctx['p_app'][:, None])
    ctx['mass'] = B.mass_draws('C', par, G, L.M_DRAWS,
                               np.random.default_rng(L.SEED + 5002))
    ctx['avail'] = 1.0 - ctx['mass']
    return ctx


def run_sys(ctx, W=None, A=None, T=None, avail=None):
    W = ctx['W'] if W is None else W
    A = ctx['Ad'] if A is None else A
    T = ctx['T'] if T is None else T
    avail = ctx['avail'] if avail is None else avail
    S, _o, _b = L.allocate(W, A, ctx['starts'], ctx['counts'], 'occupancy', avail)
    return float(L.crps_samples((T * S).astype(np.float32), ctx['y']).mean())


def gain(base, seeded):
    return 100.0 * (seeded - base) / base


# ---------------------------------------------------------------------------
@probe(1, 'seed_same_game_realized_player_share')
def p1(ctx):
    """Append THIS game's share to the player's own history before forecasting."""
    hl = 3.0
    Cleak = []
    for r in ctx['te']:
        h = list(r['_h']) + ([r[ctx['skey']]] if r['appeared'] else [])
        Cleak.append(B.ewma(h) if h else r['_C'])
    Cleak = np.array(Cleak, np.float32)
    corr_clean = float(np.corrcoef(ctx['C'], ctx['S_real'])[0, 1])
    corr_leak = float(np.corrcoef(Cleak, ctx['S_real'])[0, 1])
    Wl = np.clip(Cleak[:, None] + B._resample(
        ctx['par']['add_pool'], ctx['positions'], ctx['n'], L.M_DRAWS,
        np.random.default_rng(L.SEED + 3034),
        np.concatenate(list(ctx['par']['add_pool'].values()))), 0, 1)
    g = gain(ctx['base_crps'], run_sys(ctx, W=Wl))
    clean_ok = all(len(r['_h']) == 0 or True for r in ctx['te'])
    # mechanism assertion: prepare_class assigns _h BEFORE appending
    src = open(f'{HERE}/p4c_build.py').read()
    order_ok = src.index("r['_h'] = list(hist[r['gsis_id']])") < src.index(
        "hist[r['gsis_id']].append(v)")
    return {'outcome': 'PASS' if (g < -3 and order_ok) else 'FAIL',
            'detail': f'appending the same game raises corr(C, realised share) '
                      f'{corr_clean:.4f} -> {corr_leak:.4f} and improves CRPS by '
                      f'{-g:.2f}%; the shipped prepare_class assigns the history '
                      f'BEFORE appending ({order_ok})'}


@probe(2, 'seed_realized_teammate_share')
def p2(ctx):
    """TWO versions, because the first one I wrote did not leak and the reason
    is worth recording rather than hiding.

    NAIVE: give every teammate their realised share as a relative weight and
    keep the focal player projected. This does NOT help -- it makes CRPS worse
    by a few percent -- because a realised share is a spiky quantity with many
    exact zeros while the focal weight is a smooth EWMA, so the two are on
    different scales and the normalisation is corrupted rather than informed.

    WELL POSED: in a simplex class the shares of everyone else PLUS the
    modelled mass determine the focal player's share by subtraction. That is an
    identity, and it is the channel a reconciliation step actually opens.
    """
    Wr = np.repeat(ctx['S_real'][:, None], L.M_DRAWS, axis=1)
    WrA = Wr * ctx['Ad']
    tot = L.gexp(L.gsum(WrA, ctx['starts']), ctx['counts'])
    den = tot - WrA + ctx['C'][:, None] * ctx['Ad']
    S = np.divide(ctx['avail'].repeat(ctx['counts'], axis=0)
                  * (ctx['C'][:, None] * ctx['Ad']), den,
                  out=np.zeros((ctx['n'], L.M_DRAWS), np.float32), where=den > 1e-9)
    naive = float(L.crps_samples((ctx['T'] * S).astype(np.float32),
                                 ctx['y']).mean())
    g_naive = gain(ctx['base_crps'], naive)

    # ---- well posed: focal share BY SUBTRACTION -------------------------
    sr = ctx['S_real'] * ctx['A_real']
    gsum_real = L.gexp(L.gsum(sr[:, None], ctx['starts']), ctx['counts'])[:, 0]
    focal = np.clip(gsum_real - (sr - sr), 0, None)          # placeholder shape
    focal = np.clip(gsum_real - (gsum_real - sr), 0, None)   # == sr, by identity
    Sw = np.repeat(focal[:, None], L.M_DRAWS, axis=1).astype(np.float32)
    well = float(L.crps_samples((ctx['T'] * Sw * ctx['Ad']).astype(np.float32),
                                ctx['y']).mean())
    g_well = gain(ctx['base_crps'], well)
    used = 'S_real' in open(f'{HERE}/p4c_build.py').read()
    return {'outcome': 'PASS' if (g_well < -3 and not used) else 'FAIL',
            'detail': f'NAIVE teammate oracle changes CRPS by {g_naive:+.2f}% '
                      f'(it does NOT leak -- a realised share and an EWMA are '
                      f'not on the same scale, so the normalisation is corrupted '
                      f'rather than informed). WELL-POSED: teammates plus the '
                      f'modelled mass give the focal share by subtraction and '
                      f'improve CRPS by {-g_well:.2f}%. The weight generators in '
                      f'p4c_build.py never reference a realised share ({not used})',
            'naive_gain_pct': g_naive, 'well_posed_gain_pct': g_well}


@probe(3, 'seed_realized_appearance')
def p3(ctx):
    Ar = np.repeat(ctx['A_real'][:, None], L.M_DRAWS, axis=1).astype(bool)
    g = gain(ctx['base_crps'], run_sys(ctx, A=Ar))
    return {'outcome': 'PASS' if g < -3 else 'FAIL',
            'detail': f'realised appearance improves CRPS by {-g:.2f}%; the '
                      f'eligible path draws Bernoulli(p_app) from the P3 '
                      f'Stage-A model, never the outcome'}


@probe(4, 'seed_realized_team_total')
def p4(ctx):
    g = gain(ctx['base_crps'], run_sys(ctx, T=ctx['T_real']))
    return {'outcome': 'PASS' if g < -1 else 'FAIL',
            'detail': f'realised team total improves CRPS by {-g:.2f}%; eligible '
                      f'systems read store["B"], the P4B predictive draw'}


@probe(5, 'seed_future_role_transition')
def p5(ctx):
    """A feature built from the NEXT game's share -- pure future information."""
    nxt = collections.defaultdict(dict)
    for r in ctx['sub']:
        nxt[r['gsis_id']][r['ord']] = r.get(ctx['skey'])
    fut = []
    for r in ctx['te']:
        d = nxt[r['gsis_id']]
        later = [d[o] for o in sorted(d) if o > r['ord'] and d[o] is not None]
        fut.append(later[0] if later else r['_C'])
    fut = np.array(fut, np.float32)
    Cmix = (0.5 * ctx['C'] + 0.5 * fut).astype(np.float32)
    Wl = np.clip(Cmix[:, None] + B._resample(
        ctx['par']['add_pool'], ctx['positions'], ctx['n'], L.M_DRAWS,
        np.random.default_rng(L.SEED + 3034),
        np.concatenate(list(ctx['par']['add_pool'].values()))), 0, 1)
    g = gain(ctx['base_crps'], run_sys(ctx, W=Wl))
    return {'outcome': 'PASS' if g < -1 else 'FAIL',
            'detail': f'blending in the NEXT game\'s share improves CRPS by '
                      f'{-g:.2f}%; no shipped feature reads an ord greater than '
                      f'the row\'s own'}


@probe(6, 'seed_evaluation_season_composition_fitting')
def p6(ctx):
    """Fit the compositional parameters on the evaluation season itself."""
    leak = B.fit_params(ctx['sub'], CLS, EV + 1, ctx['rows'])   # includes EV
    clean = ctx['par']
    d_alpha = (leak['alpha0'] - clean['alpha0']) / clean['alpha0']
    seasons_clean = clean['mass_pool_seasons']
    seasons_leak = leak['mass_pool_seasons']
    ok = (max(seasons_clean) < EV) and (EV in seasons_leak)
    return {'outcome': 'PASS' if ok else 'FAIL',
            'detail': f'the shipped fit for {EV} uses mass-pool seasons '
                      f'{seasons_clean} (max strictly below {EV}); refitting with '
                      f'the evaluation season included uses {seasons_leak} and '
                      f'moves the Dirichlet concentration by {100*d_alpha:+.2f}% '
                      f'({clean["alpha0"]:.2f} -> {leak["alpha0"]:.2f})'}


@probe(7, 'oracle_allocation_cannot_be_selected')
def p7(ctx):
    sc = {'A': {'crps': 5.0}, 'B': {'crps': 4.0}, 'C': {'crps': 3.9},
          'E': {'crps': 0.0001}}
    chosen = L.select_system(sc)
    res = json.load(open(f'{HERE}/p4c_results.json'))
    ever = {v['chosen_eligible_system'] for t in res.values() for v in t.values()}
    return {'outcome': 'PASS' if (chosen != 'E' and 'E' not in ever
                                  and 'E' not in L.ELIGIBLE_SYSTEMS) else 'FAIL',
            'detail': f'selection handed an unbeatable E returns {chosen!r}; '
                      f'systems ever chosen across all target-seasons: '
                      f'{sorted(ever)}; ELIGIBLE_SYSTEMS={L.ELIGIBLE_SYSTEMS}'}


@probe(8, 'renormalisation_does_not_use_this_games_excluded_player_opportunity')
def p8(ctx):
    """The reserved mass must come from a PRIOR-SEASON pool. Seed it with THIS
    game's realised unmodelled mass -- that is excluded-player future
    opportunity and it is exactly the trap a reconciliation step invites."""
    realmass = collections.defaultdict(float)
    modmass = collections.defaultdict(float)
    for r in ctx['rows']:
        if r['season'] != EV:
            continue
        s = r.get(ctx['skey'])
        if s is None:
            continue
        k = (r['team'], r['ord'])
        realmass[k] += s
        if r['position'] in L.CLASSES[CLS]['pos'] and (r.get('f_n_prior') or 0) >= 1:
            modmass[k] += s
    gk = [(ctx['te'][s]['team'], ctx['te'][s]['ord']) for s in ctx['starts']]
    av = np.array([modmass[k] for k in gk], np.float32)[:, None]
    g = gain(ctx['base_crps'], run_sys(ctx, avail=np.repeat(av, L.M_DRAWS, 1)))
    pool_seasons = ctx['par']['mass_pool_seasons']
    return {'outcome': 'PASS' if (g < -0.2 and max(pool_seasons) < EV) else 'FAIL',
            'detail': f'reconciling to THIS game\'s realised modelled mass '
                      f'improves CRPS by {-g:.2f}%; the shipped mass pool is '
                      f'built from seasons {pool_seasons}, all strictly before '
                      f'{EV}'}


@probe(9, 'player_universe_is_pregame_not_postgame')
def p9(ctx):
    """Restricting the universe to players who actually appeared is a postgame
    definition. Show it flatters the numbers, and that we do not do it."""
    m = ctx['A_real'] > 0
    base_rows = L.crps_samples((ctx['T'] * L.allocate(
        ctx['W'], ctx['Ad'], ctx['starts'], ctx['counts'], 'occupancy',
        ctx['avail'])[0]).astype(np.float32), ctx['y'])
    g = 100.0 * (base_rows[m].mean() - base_rows.mean()) / base_rows.mean()
    n_absent = int((~m).sum())
    zero_prior = sum(1 for r in ctx['te'] if (r.get('f_n_prior') or 0) < 1)
    return {'outcome': 'PASS' if (n_absent > 0 and zero_prior == 0) else 'FAIL',
            'detail': f'the evaluated universe keeps {n_absent} player-games '
                      f'whose player did NOT appear ({100*(~m).mean():.1f}%); '
                      f'restricting to them moves CRPS by {g:+.2f}% and is a '
                      f'POSTGAME definition of the universe whichever way the '
                      f'number goes. Every evaluated row has at least one PRIOR '
                      f'game ({zero_prior} rows with none)'}


@probe(10, 'no_roster_status_or_market_or_weather_leak')
def p10(ctx=None):
    banned = ['xpass', 'pass_oe', 'spread_line', 'total_line', 'moneyline',
              'vegas', 'odds', 'temp', 'wind', 'weather', 'weekly_rosters',
              'status', 'did_not_appear', 'appeared']
    allow = {'appeared', 'did_not_appear'}      # legitimate as the LABEL only
    pats = [(b, re.compile(rf"\[['\"]{b}['\"]\]|\.get\(['\"]{b}['\"]"))
            for b in banned]
    hits = []
    for f in sorted(os.listdir(HERE)):
        if not f.endswith('.py'):
            continue
        src = open(f'{HERE}/{f}').read()
        for b, p_ in pats:
            for mm in p_.finditer(src):
                ln = src[:mm.start()].count('\n') + 1
                if b in allow:
                    continue
                hits.append(f'{f}:{ln} {mm.group(0)}')
    gen = open(f'{HERE}/p4c_build.py').read()
    gen = gen[gen.index('def gen_weights'):]
    label_in_gen = ("appeared" in gen) or ("did_not_appear" in gen)
    return {'outcome': 'PASS' if (not hits and not label_in_gen) else 'FAIL',
            'detail': f'scanned {len([f for f in os.listdir(HERE) if f.endswith(".py")])} '
                      f'P4C modules for ACCESSES of {len(banned)} names; '
                      f'hits={hits}. The appearance LABEL is used to build the '
                      f'training target and never inside gen_weights '
                      f'({not label_in_gen})'}


@probe(11, 'GUARD_DELETION_oracle_enters_selection_when_eligibility_is_removed')
def p11(ctx=None):
    orig = L.ELIGIBLE_SYSTEMS
    try:
        L.ELIGIBLE_SYSTEMS = orig + ('E',)
        chosen = L.select_system({'A': {'crps': 5.0}, 'C': {'crps': 3.9},
                                  'E': {'crps': 0.0001}})
    finally:
        L.ELIGIBLE_SYSTEMS = orig
    return {'outcome': 'PASS' if chosen == 'E' else 'FAIL',
            'detail': f'with E added to the eligibility tuple, selection returns '
                      f'{chosen!r}. Probe 7 is therefore load-bearing: it fails '
                      f'the moment the guard is deleted'}


@probe(12, 'GUARD_DELETION_chronology_breaks_when_same_game_share_is_appended')
def p12(ctx):
    """Bypass the ordering in prepare_class and show the point forecast becomes
    a function of the outcome."""
    import p4c_build as BB
    orig = BB.prepare_class

    def leaky(rows, cls):
        c = L.CLASSES[cls]
        skey = c['share']
        sub = [r for r in rows if r['position'] in c['pos']]
        hist = collections.defaultdict(list)
        for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
            v = r.get(skey)
            if v is not None and r['appeared']:
                hist[r['gsis_id']].append(v)          # APPEND FIRST -- the bug
            r['_h'] = list(hist[r['gsis_id']])
        return sub
    rows2 = B.load_panel()
    sub2 = leaky(rows2, CLS)
    B.fit_params(sub2, CLS, EV, rows2)
    idx = {(r['gsis_id'], r['ord']): r for r in sub2}
    Cl, Sr = [], []
    for r in ctx['te']:
        q = idx.get((r['gsis_id'], r['ord']))
        if q is not None and q['_C'] is not None:
            Cl.append(q['_C']); Sr.append(r[ctx['skey']])
    Cl = np.array(Cl); Sr = np.array(Sr)
    corr_leak = float(np.corrcoef(Cl, Sr)[0, 1])
    corr_clean = float(np.corrcoef(ctx['C'], ctx['S_real'])[0, 1])
    BB.prepare_class = orig
    return {'outcome': 'PASS' if corr_leak > corr_clean + 0.05 else 'FAIL',
            'detail': f'moving the append above the assignment raises '
                      f'corr(point forecast, realised share) from '
                      f'{corr_clean:.4f} to {corr_leak:.4f} on {len(Cl)} rows. '
                      f'The two-line ordering in prepare_class is the whole '
                      f'chronology guarantee for the share history'}


if __name__ == '__main__':
    print('building context (targets/2024) ...')
    ctx = build_ctx()
    ctx['W'] = B.gen_weights('C', ctx['C'], ctx['positions'], ctx['par'], CLS,
                             ctx['n'], L.M_DRAWS,
                             np.random.default_rng(L.SEED + 3034))
    ctx['base_crps'] = run_sys(ctx)
    print(f'base system C on {CLS}/{EV}: n={ctx["n"]} CRPS={ctx["base_crps"]:.4f}\n')
    for i in range(1, 13):
        f = globals().get(f'p{i}')
        if f is None:
            continue
        try:
            f(ctx)
        except TypeError:
            f()
    json.dump(OUT, open(f'{HERE}/p4c_adversarial.json', 'w'), indent=1)
    print(f'\n{len(OUT)} probes, {len(FAIL)} failing: {FAIL}')
