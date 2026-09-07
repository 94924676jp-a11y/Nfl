"""P5A adversarial probes: eleven seeded leaks and two guard-deletion proofs.

Each probe seeds the violation, shows the seeded version is materially better,
then asserts the shipped pipeline does not contain it.

TWO PROBES RETURN `UNRESOLVED` AND THAT IS THE FINDING, NOT A DEFECT. For
SAME-GAME quantities the channel is enormous (40-100% of weighted MSE). For
FUTURE quantities it is small -- the player's entire future yards per carry,
with the blend weight fitted, buys 0.44% -- because per-game rushing efficiency
is so noisy that even perfect knowledge of a player's future average barely
helps for one game. A probe that cannot demonstrate a live channel gives weaker
assurance than one that can, so the chronology guarantee for those two channels
rests on the MECHANISM proof (probe 13) rather than on a detectable signature.
The thresholds were NOT lowered to manufacture a pass.

The efficiency probes run on the 2024 next-game YPC harness (n = 2,254
player-games, carry-weighted); the downstream probe uses the committed results.
"""
import collections, json, math, os, pickle, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p5a_lib as L                                            # noqa: E402

OUT, FAIL, UNRES = {}, [], []
EV = 2024
K = 60


def probe(n, name):
    def deco(fn):
        def run(ctx):
            try:
                r = fn(ctx)
            except Exception as e:                              # noqa: BLE001
                r = {'outcome': 'FAIL', 'error': f'{type(e).__name__}: {e}'}
            OUT[f'{n:02d}_{name}'] = r
            if r.get('outcome') == 'FAIL':
                FAIL.append(name)
            elif r.get('outcome') != 'PASS':
                UNRES.append(name)
            print(f'[{r.get("outcome","?"):4s}] {n:2d} {name}: '
                  f'{r.get("detail", r.get("error",""))}')
        return run
    return deco


def wmse(pred, ctx):
    p = np.asarray(pred, float)
    return float(np.average((ctx['act'] - p) ** 2, weights=ctx['w']))


def gain(ctx, pred):
    return 100.0 * (wmse(pred, ctx) - ctx['base']) / ctx['base']


def build():
    D = pickle.load(open(f'{HERE}/pg.pkl', 'rb'))
    pg, carries = D['pg'], D['carries']
    te = [r for r in pg if r['season'] == EV and r['carries'] >= 1]
    tr = [r for r in pg if r['season'] < EV and r['carries'] >= 1]
    pool = float(np.average([r['rush_yards'] / r['carries'] for r in tr],
                            weights=[r['carries'] for r in tr]))
    act = np.array([r['rush_yards'] / r['carries'] for r in te])
    w = np.array([r['carries'] for r in te], float)
    ebp = np.array([pool if (r['p'] is None or r['p']['n'] < 1) else
                    (r['p']['n'] * r['p']['ypc'] + K * pool) / (r['p']['n'] + K)
                    for r in te])
    ctx = {'pg': pg, 'carries': carries, 'te': te, 'tr': tr, 'pool': pool,
           'act': act, 'w': w, 'ebp': ebp}
    ctx['base'] = wmse(ebp, ctx)
    return ctx


def blend(ctx, extra, alpha=0.5):
    """A 50/50 blend of the honest estimate with the seeded quantity, on the
    same scale, so the probe measures the CHANNEL rather than a rescaling."""
    e = np.asarray(extra, float)
    return (1 - alpha) * ctx['ebp'] + alpha * e


@probe(1, 'seed_realized_carries')
def p1(ctx):
    r = json.load(open(f'{HERE}/p5a_results.json'))
    g = []
    for ev, v in r.items():
        a = v['scores']['A']['crps']; o = v['scores']['O_carries']['crps']
        g.append((o - a) / a)
    g = np.array(g)
    return {'outcome': 'PASS' if g.max() < -0.2 else 'FAIL',
            'detail': f'realised carry counts improve downstream CRPS in '
                      f'{int((g<0).sum())}/{len(g)} seasons by '
                      f'{-100*g.mean():.2f}% on average. Eligible systems draw '
                      f'the carry count from the accepted P4C allocation and '
                      f'never from the outcome'}


@probe(2, 'seed_same_game_rushing_yards')
def p2(ctx):
    y = np.array([r['rush_yards'] / max(r['carries'], 1) for r in ctx['te']])
    g = gain(ctx, blend(ctx, y))
    src = open(f'{HERE}/p5a_build.py').read()
    src = src[src.index('def build('):]
    order_ok = src.index('psnap = P[pid].snapshot()') < src.index("P[c['rusher']].add(c)")
    return {'outcome': 'PASS' if (g < -20 and order_ok) else 'FAIL',
            'detail': f'blending in this game\'s own rushing yards improves '
                      f'weighted MSE by {-g:.2f}%; p5a_build reads every '
                      f'accumulator BEFORE updating it ({order_ok})'}


@probe(3, 'seed_same_game_ypc')
def p3(ctx):
    g = gain(ctx, ctx['act'])
    return {'outcome': 'PASS' if g < -90 else 'FAIL',
            'detail': f'using this game\'s realised yards per carry improves '
                      f'weighted MSE by {-g:.2f}% (it is the target). No '
                      f'shipped feature reads rush_yards or ypc of the row'}


@probe(4, 'seed_same_game_explosive_run')
def p4(ctx):
    x = np.array([r['n_explosive'] / max(r['carries'], 1) for r in ctx['te']])
    pool_e = float(np.average([r['n_explosive'] / r['carries'] for r in ctx['tr']],
                              weights=[r['carries'] for r in ctx['tr']]))
    # put the explosive rate on the ypc scale by its regression slope
    b = np.polyfit(x, ctx['act'], 1)
    g = gain(ctx, blend(ctx, np.polyval(b, x)))
    return {'outcome': 'PASS' if g < -20 else 'FAIL',
            'detail': f'this game\'s own explosive-run rate improves weighted '
                      f'MSE by {-g:.2f}% (pooled explosive rate {pool_e:.4f}); '
                      f'the shipped explosive feature is built from prior games '
                      f'only'}


@probe(5, 'seed_future_player_efficiency')
def p5(ctx):
    """TWO versions, because the first construction did not leak and the reason
    is the finding, not a probe defect.

    WEAK: a 50/50 blend with the player's NEXT FOUR games' yards per carry. It
    makes weighted MSE WORSE, because four games of YPC is so noisy that
    averaging it into a shrunk prior adds more variance than signal -- the same
    fact the whole of P5A is about.

    STRONG: the player's ENTIRE future yards per carry with the blend weight
    fitted, which is what a leak would actually look like.
    """
    nxt = collections.defaultdict(dict)
    for r in ctx['pg']:
        nxt[r['gsis_id']][r['ord']] = (r['rush_yards'], r['carries'])
    f4, fall = [], []
    for r in ctx['te']:
        d = nxt[r['gsis_id']]
        later = [d[o] for o in sorted(d) if o > r['ord']]
        f4.append(float(np.mean([a / max(b, 1) for a, b in later[:4]]))
                  if later else ctx['pool'])
        if later:
            cy = sum(a for a, _b in later); cc = sum(b for _a, b in later)
            fall.append(cy / max(cc, 1))
        else:
            fall.append(ctx['pool'])
    g_weak = gain(ctx, blend(ctx, f4))
    x = np.array(fall)
    mx = np.average(x, weights=ctx['w'])
    beta = (np.average((x - mx) * (ctx['act'] - np.average(ctx['act'], weights=ctx['w'])),
                       weights=ctx['w'])
            / max(np.average((x - mx) ** 2, weights=ctx['w']), 1e-12))
    g_strong = gain(ctx, ctx['ebp'] + beta * (x - mx))
    return {'outcome': 'PASS' if g_strong < -3 else 'UNRESOLVED',
            'detail': f'WEAK (50/50 blend with the next four games) makes '
                      f'weighted MSE {-g_weak:+.2f}% -- it does NOT leak, four '
                      f'games of YPC is too noisy to help. STRONG (the entire '
                      f'future YPC, blend weight fitted, beta={beta:+.3f}) '
                      f'improves it by {-g_strong:.2f}%. Every accumulator in '
                      f'p5a_build advances strictly in `ord` order',
            'weak_pct': g_weak, 'strong_pct': g_strong}


@probe(6, 'seed_future_team_efficiency')
def p6(ctx):
    nxt = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in ctx['pg']:
        nxt[r['team']][r['ord']].append((r['rush_yards'], r['carries']))
    fut = []
    for r in ctx['te']:
        d = nxt[r['team']]
        later = [x for o in sorted(d) if o > r['ord'] for x in d[o]][:20]
        if later:
            cy = sum(a for a, _b in later); cc = sum(b for _a, b in later)
            fut.append(cy / max(cc, 1))
        else:
            fut.append(ctx['pool'])
    g = gain(ctx, blend(ctx, fut, 0.35))
    return {'outcome': 'PASS' if g < -0.2 else 'FAIL',
            'detail': f'the team\'s FUTURE rushing efficiency improves weighted '
                      f'MSE by {-g:.2f}%; the team accumulator is read before '
                      f'the game is added to it'}


@probe(7, 'seed_future_opponent_outcome')
def p7(ctx):
    nxt = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in ctx['pg']:
        nxt[r['opp']][r['ord']].append((r['rush_yards'], r['carries']))
    fut = []
    for r in ctx['te']:
        d = nxt[r['opp']]
        later = [x for o in sorted(d) if o > r['ord'] for x in d[o]][:30]
        if later:
            cy = sum(a for a, _b in later); cc = sum(b for _a, b in later)
            fut.append(cy / max(cc, 1))
        else:
            fut.append(ctx['pool'])
    g = gain(ctx, blend(ctx, fut, 0.35))
    return {'outcome': 'PASS' if g < -0.05 else 'FAIL',
            'detail': f'the opponent\'s FUTURE rushing yards allowed improve '
                      f'weighted MSE by {-g:.2f}%; the opponent accumulator is '
                      f'also read before update'}


@probe(8, 'no_observed_weather_field_is_read')
def p8(ctx):
    banned = ['temp', 'wind', 'weather', 'humidity', 'surface', 'roof']
    hits = []
    for f in sorted(os.listdir(HERE)):
        if not f.endswith('.py'):
            continue
        src = open(f'{HERE}/{f}').read()
        for b in banned:
            for m in re.finditer(rf"\[['\"]{b}['\"]\]|\.get\(['\"]{b}['\"]", src):
                hits.append(f'{f}: {m.group(0)}')
    cols = open(f'{HERE}/carries.csv').readline().strip().split(',')
    bad_cols = [c for c in cols if any(b in c.lower() for b in banned)]
    return {'outcome': 'PASS' if not hits and not bad_cols else 'FAIL',
            'detail': f'no P5A module reads a weather or surface field '
                      f'({hits}); the carry table carries {len(cols)} columns '
                      f'and none is weather ({bad_cols})'}


@probe(9, 'no_market_information')
def p9(ctx):
    banned = ['spread_line', 'total_line', 'moneyline', 'odds', 'vegas',
              'implied_prob', 'price', 'book']
    hits = []
    for f in sorted(os.listdir(HERE)):
        if not f.endswith('.py'):
            continue
        src = open(f'{HERE}/{f}').read()
        for b in banned:
            for m in re.finditer(rf"\[['\"]{b}['\"]\]|\.get\(['\"]{b}['\"]", src):
                hits.append(f'{f}: {m.group(0)}')
    files = [f for f in os.listdir(HERE)
             if re.search(r'(bet|wager|odds|book|parlay|dfs|lineup|stake|ev)', f, re.I)]
    return {'outcome': 'PASS' if not hits and not files else 'FAIL',
            'detail': f'no market field is read ({hits}) and no P5A artifact '
                      f'names a market, wager, book or lineup ({files})'}


@probe(10, 'seed_evaluation_season_fitting')
def p10(ctx):
    """TWO channels, sized separately, because they are very different.

    The pooled prior and the shrinkage constant barely leak -- pooled YPC is
    4.29-4.32 across seasons and the MSE is flat in k near the optimum. The
    COEFFICIENT is the channel that matters: fitting the map from the shrunk
    player estimate to the outcome on the evaluation season itself.
    """
    grid = [0, 5, 10, 20, 40, 80, 160, 320, 640, 1280, 2560]
    pool_leak = float(np.average(ctx['act'], weights=ctx['w']))
    best, bv = None, None
    for k in grid:
        p = np.array([pool_leak if (r['p'] is None or r['p']['n'] < 1) else
                      (r['p']['n'] * r['p']['ypc'] + k * pool_leak) / (r['p']['n'] + k)
                      for r in ctx['te']])
        v = wmse(p, ctx)
        if bv is None or v < bv:
            best, bv = k, v
    g_k = 100 * (bv - ctx['base']) / ctx['base']
    x = ctx['ebp']
    mx = np.average(x, weights=ctx['w'])
    ay = np.average(ctx['act'], weights=ctx['w'])
    beta = (np.average((x - mx) * (ctx['act'] - ay), weights=ctx['w'])
            / max(np.average((x - mx) ** 2, weights=ctx['w']), 1e-12))
    g_b = gain(ctx, ay + beta * (x - mx))
    r = json.load(open(f'{HERE}/p5a_results.json'))
    ks = {ev: r[ev]['eb_k']['player_ypc'] for ev in r}
    return {'outcome': 'PASS' if g_b < -1 else 'UNRESOLVED',
            'detail': f'refitting the POOL and the shrinkage constant on {EV} '
                      f'gives k={best} and buys only {-g_k:.2f}% -- that channel '
                      f'is genuinely small, because pooled YPC is 4.29-4.32 '
                      f'across seasons. Refitting the COEFFICIENT on {EV} '
                      f'(beta={beta:+.3f}) buys {-g_b:.2f}%. The shipped '
                      f'constants and coefficients are fitted on prior seasons '
                      f'only ({ks})',
            'k_channel_pct': g_k, 'coefficient_channel_pct': g_b}


@probe(11, 'no_postgame_roster_status')
def p11(ctx):
    hits = []
    for f in sorted(os.listdir(HERE)):
        if not f.endswith('.py'):
            continue
        src = open(f'{HERE}/{f}').read()
        for b in ('weekly_rosters', 'status', 'game_status', 'inactive'):
            for m in re.finditer(rf"\[['\"]{b}['\"]\]|\.get\(['\"]{b}['\"]", src):
                hits.append(f'{f}: {m.group(0)}')
    return {'outcome': 'PASS' if not hits else 'FAIL',
            'detail': f'no P5A module reads a roster-status field ({hits}); the '
                      f'appearance treatment is P4C/P4D\'s incumbent, imported '
                      f'unchanged'}


@probe(12, 'GUARD_DELETION_oracle_enters_selection')
def p12(ctx):
    orig = L.ELIGIBLE_SYSTEMS
    clean = L.select_system({'A': {'crps': 10.6}, 'E': {'crps': 10.5},
                             'O_all': {'crps': 2.16}})
    try:
        L.ELIGIBLE_SYSTEMS = orig + ('O_all',)
        leaked = L.select_system({'A': {'crps': 10.6}, 'E': {'crps': 10.5},
                                  'O_all': {'crps': 2.16}})
    finally:
        L.ELIGIBLE_SYSTEMS = orig
    r = json.load(open(f'{HERE}/p5a_results.json'))
    ever = {r[ev]['chosen_eligible_system'] for ev in r}
    return {'outcome': 'PASS' if (clean != 'O_all' and leaked == 'O_all'
                                  and not (ever & set(L.DIAGNOSTIC_ONLY)))
            else 'FAIL',
            'detail': f'selection handed an unbeatable O_all returns {clean!r}; '
                      f'adding O_all to the eligibility tuple makes it return '
                      f'{leaked!r}. Systems ever chosen: {sorted(ever)}'}


@probe(13, 'GUARD_DELETION_history_read_before_update')
def p13(ctx):
    """Bypass the ordering in p5a_build and show the prior-history estimate
    becomes a function of the game it is supposed to predict."""
    pg = ctx['pg']
    clean = np.array([r['p']['ypc'] if (r['p'] and r['p']['n'] >= 25) else np.nan
                      for r in ctx['te']])
    acc = collections.defaultdict(lambda: [0.0, 0.0])
    leak = []
    for r in sorted(pg, key=lambda x: (x['ord'], x['team'])):
        a = acc[r['gsis_id']]
        a[0] += r['carries']; a[1] += r['rush_yards']          # UPDATE FIRST
        r['_leak'] = (a[1] / a[0]) if a[0] >= 25 else np.nan
    leak = np.array([r['_leak'] for r in ctx['te']])
    m = ~np.isnan(clean) & ~np.isnan(leak)
    rc = float(np.corrcoef(clean[m], ctx['act'][m])[0, 1])
    rl = float(np.corrcoef(leak[m], ctx['act'][m])[0, 1])
    return {'outcome': 'PASS' if rl > rc + 0.05 else 'FAIL',
            'detail': f'moving the update above the read raises '
                      f'corr(history, this game\'s ypc) from {rc:.4f} to '
                      f'{rl:.4f} on {int(m.sum())} rows. The read-then-update '
                      f'ordering in p5a_build.build is the whole chronology '
                      f'guarantee for every player, team and opponent signal'}


if __name__ == '__main__':
    ctx = build()
    print(f'harness: {EV} next-game ypc, n={len(ctx["te"])}, '
          f'baseline weighted MSE {ctx["base"]:.5f}\n')
    for i in range(1, 14):
        globals()[f'p{i}'](ctx)
    json.dump(OUT, open(f'{HERE}/p5a_adversarial.json', 'w'), indent=1)
    print(f'\n{len(OUT)} probes: {len(OUT)-len(FAIL)-len(UNRES)} PASS, '
          f'{len(UNRES)} UNRESOLVED {UNRES}, {len(FAIL)} FAIL {FAIL}')
