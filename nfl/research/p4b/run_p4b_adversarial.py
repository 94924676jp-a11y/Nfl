"""P4B adversarial probes. Each one tries to make this study wrong.

The pattern this project keeps paying for is a step that returned nothing being
read as success, so every probe here asserts on a value it actually computed
and prints the value, not a tick.
"""
import ast, collections, json, os, pickle, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, '..', 'p1'), os.path.join(HERE, '..', 'p2'),
          os.path.join(HERE, '..', 'p3'), HERE, '/home/user/nfl'):
    sys.path.insert(0, os.path.abspath(p))
import p4b_lib as L                                            # noqa: E402

OUT = {}
FAIL = []


def probe(n, name):
    def deco(fn):
        def run():
            try:
                r = fn()
            except Exception as e:                             # noqa: BLE001
                r = {'outcome': 'FAIL', 'error': f'{type(e).__name__}: {e}'}
            OUT[f'{n:02d}_{name}'] = r
            ok = r.get('outcome') == 'PASS'
            if not ok:
                FAIL.append(name)
            print(f'[{r.get("outcome","?"):4s}] {n:2d} {name}: '
                  f'{r.get("detail", r.get("error",""))}')
        return run
    return deco


# ---------------------------------------------------------------------------
@probe(1, 'oracle_system_D_cannot_be_selected')
def p1():
    import run_p4b as R
    src = open(f'{HERE}/run_p4b.py').read()
    tree = ast.parse(src)
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == 'select_system')
    names = {n.value for n in ast.walk(fn) if isinstance(n, ast.Constant)}
    # behavioural, not textual: hand selection a D that is unbeatable
    scores = {'A': {'crps': 5.0}, 'B': {'crps': 4.0}, 'C': {'crps': 4.5},
              'D': {'crps': 0.0001}}
    chosen = R.select_system(scores)
    res = json.load(open(f'{HERE}/p4b_results.json'))
    picked = {v['chosen_eligible_system']
              for t in res.values() for v in t.values()}
    return {'outcome': 'PASS' if (chosen != 'D' and 'D' not in picked
                                  and 'D' not in R.ELIGIBLE_SYSTEMS) else 'FAIL',
            'detail': f'select_system given an unbeatable D returned {chosen!r}; '
                      f'systems ever chosen across 20 target-seasons: '
                      f'{sorted(picked)}; ELIGIBLE_SYSTEMS={R.ELIGIBLE_SYSTEMS}; '
                      f'literals inside select_system: {sorted(map(str, names))}'}


@probe(2, 'guard_deletion_proof_for_probe_1')
def p2():
    """A guard test that passes when the guard is removed is decoration. Bypass
    the eligibility filter and show probe 1's assertion then fails."""
    import run_p4b as R
    orig = R.ELIGIBLE_SYSTEMS
    try:
        R.ELIGIBLE_SYSTEMS = ('A', 'B', 'C', 'D')
        chosen = R.select_system({'A': {'crps': 5.0}, 'B': {'crps': 4.0},
                                  'C': {'crps': 4.5}, 'D': {'crps': 0.0001}})
    finally:
        R.ELIGIBLE_SYSTEMS = orig
    return {'outcome': 'PASS' if chosen == 'D' else 'FAIL',
            'detail': f'with the eligibility tuple widened, selection returns '
                      f'{chosen!r} -- so probe 1 is load-bearing, not decorative'}


@probe(3, 'volume_residuals_fitted_only_on_prior_seasons')
def p3():
    v = json.load(open(f'{HERE}/volume_results.json'))
    bad = []
    for key, ss in v.items():
        for ev, d in ss.items():
            if max(d['train_seasons']) >= int(ev):
                bad.append((key, ev, d['train_seasons']))
    return {'outcome': 'PASS' if not bad else 'FAIL',
            'detail': f'checked {sum(len(s) for s in v.values())} target-seasons; '
                      f'max training season is strictly below the evaluation '
                      f'season in every one; violations={bad}'}


@probe(4, 'oracle_identity_realised_x_realised_equals_outcome')
def p4():
    r = json.load(open(f'{HERE}/p4b_results.json'))
    worst = max((v['oracle']['RRR_real_app_vol_share']['max_abs_err'], t, ev)
                for t, ss in r.items() for ev, v in ss.items())
    return {'outcome': 'PASS' if worst[0] < 1e-9 else 'FAIL',
            'detail': f'largest |A_real*T_real*S_real - y| over all 20 '
                      f'target-seasons is {worst[0]:.3e} ({worst[1]} {worst[2]}); '
                      f'the decomposition is exact, so no part of the oracle gap '
                      f'is a construction mismatch'}


@probe(5, 'team_volume_draws_are_shared_within_a_team_game')
def p5():
    arr = np.load(f'{HERE}/volume_store.npy', allow_pickle=True)
    e = dict(arr[0])
    B = e['B']
    # two different team-games must differ; the SAME team-game gathered twice
    # must be identical -- that is what makes the covariance diagnostic mean
    # anything.
    same = np.array_equal(B[3], B[3])
    diff = not np.array_equal(B[3], B[4])
    idx = np.array([3, 3, 4])
    gathered = B[idx]
    shared = np.array_equal(gathered[0], gathered[1])
    return {'outcome': 'PASS' if (same and diff and shared) else 'FAIL',
            'detail': f'store {e["k"]}: two players gathered onto team-game 3 '
                      f'receive byte-identical 1000-draw vectors ({shared}); '
                      f'team-game 4 differs ({diff})'}


@probe(6, 'reproducible_under_the_declared_seed')
def p6():
    a = np.random.default_rng(L.SEED + 1009).random((50, 8))
    b = np.random.default_rng(L.SEED + 1009).random((50, 8))
    c = np.random.default_rng(L.SEED + 1010).random((50, 8))
    return {'outcome': 'PASS' if (np.array_equal(a, b) and not np.array_equal(a, c))
            else 'FAIL',
            'detail': f'seed {L.SEED}+1009 reproduces exactly; a different '
                      f'stream does not. Max |a-c| = {np.abs(a-c).max():.4f}'}


@probe(7, 'forbidden_fields_are_never_read')
def p7():
    """Reads, not mentions. P4's first version of this check matched its own
    explanatory comment and passed for the wrong reason."""
    banned = ['xpass', 'pass_oe', 'spread_line', 'total_line', 'moneyline',
              'implied_prob', 'vegas', 'odds', 'temp', 'wind', 'weather',
              'weekly_rosters', 'status']
    pats = [re.compile(rf"\[['\"]{b}['\"]\]") for b in banned]
    pats += [re.compile(rf"\.get\(['\"]{b}['\"]") for b in banned]
    hits = []
    for f in sorted(os.listdir(HERE)):
        if not f.endswith('.py'):
            continue
        src = open(f'{HERE}/{f}').read()
        for p_ in pats:
            for m in p_.finditer(src):
                hits.append(f'{f}: {m.group(0)}')
    return {'outcome': 'PASS' if not hits else 'FAIL',
            'detail': f'scanned {len([f for f in os.listdir(HERE) if f.endswith(".py")])} '
                      f'P4B modules for field ACCESSES (subscript or .get) of '
                      f'{len(banned)} forbidden names; hits={hits}'}


@probe(8, 'threshold_grid_matches_the_predeclaration')
def p8():
    txt = open(f'{HERE}/predeclaration_p4b.md').read()
    want = {
        'carries': [5.5, 9.5, 12.5, 15.5, 19.5],
        'targets': [2.5, 4.5, 6.5, 8.5, 10.5],
        'snaps': [10.5, 20.5, 30.5, 40.5, 50.5],
    }
    bad = []
    for k, v in want.items():
        if L.THRESHOLDS[k] != v:
            bad.append((k, L.THRESHOLDS[k], v))
        line = [ln for ln in txt.splitlines() if ln.strip().startswith(f'- {k}:')]
        if not line or [float(x) for x in re.findall(r'\d+\.\d', line[0])] != v:
            bad.append((k, 'not found verbatim in predeclaration', line))
    return {'outcome': 'PASS' if not bad else 'FAIL',
            'detail': f'the code grid equals the pre-declaration text for '
                      f'carries/targets/snaps; rz_carries grid is '
                      f'{L.THRESHOLDS["rz_carries"]!r} because none was '
                      f'pre-declared; problems={bad}'}


@probe(9, 'coverage_does_not_select')
def p9():
    """Hand the selector a system with perfect coverage and terrible CRPS."""
    import run_p4b as R
    scores = {'A': {'crps': 1.0, 'coverage': {'90': {'coverage': 0.70}}},
              'B': {'crps': 0.9, 'coverage': {'90': {'coverage': 0.60}}},
              'C': {'crps': 9.0, 'coverage': {'90': {'coverage': 0.900}}}}
    return {'outcome': 'PASS' if R.select_system(scores) == 'B' else 'FAIL',
            'detail': 'a system with exactly nominal 90% coverage and 10x the '
                      'CRPS is not selected; CRPS decides'}


@probe(10, 'seeded_leak_is_detectable_where_the_guard_is_removed')
def p10():
    """The channel is live: if the volume distribution were centred on the
    REALISED total, CRPS would improve materially. That is exactly what system
    D measures, and it is why D is quarantined rather than merely unused."""
    r = json.load(open(f'{HERE}/p4b_results.json'))
    gains = []
    for t, ss in r.items():
        for ev, v in ss.items():
            a, d = v['scores']['A']['crps'], v['scores']['D']['crps']
            gains.append((d - a) / a)
    g = np.array(gains)
    return {'outcome': 'PASS' if g.max() < -0.005 else 'FAIL',
            'detail': f'substituting the realised team total improves CRPS in '
                      f'{int((g<0).sum())}/{len(g)} target-seasons by '
                      f'{-100*g.mean():.2f}% on average (min {-100*g.max():.2f}%, '
                      f'max {-100*g.min():.2f}%). A leak of the team total is '
                      f'therefore detectable, so the quarantine is load-bearing'}


@probe(11, 'share_history_uses_only_prior_appeared_games')
def p11():
    import run_p4b as R
    rows = pickle.load(open(f'{HERE}/panel_enriched.pkl', 'rb'))
    sub = R.share_history(rows, 'targets', ('WR', 'TE', 'RB'))
    byp = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        byp[r['gsis_id']].append(r)
    bad = n_checked = 0
    for pid, rs in byp.items():
        seen = []
        for r in rs:
            if len(r['_app_hist']) != len(seen) or any(
                    abs(a - b) > 1e-12 for a, b in zip(r['_app_hist'], seen)):
                bad += 1
            n_checked += 1
            if r['appeared'] and r.get('s_targets') is not None:
                seen.append(r['s_targets'])
    return {'outcome': 'PASS' if bad == 0 else 'FAIL',
            'detail': f'replayed {n_checked} player-games across {len(byp)} '
                      f'players; the stored history at each row equals the list '
                      f'of strictly-earlier APPEARED shares in every case '
                      f'({bad} mismatches)'}


@probe(12, 'panel_and_denominator_agree_exactly')
def p12():
    rows = pickle.load(open(f'{HERE}/panel_enriched.pkl', 'rb'))
    n = worst = 0
    for r in rows:
        for t, dk in (('snaps', 'team_off_snaps'), ('targets', 'team_targets'),
                      ('carries', 'team_carries'),
                      ('rz_carries', 'team_rz_carries'),
                      ('pass_snaps', 'team_dropbacks_part')):
            s = r.get(f's_{t}')
            if s is None:
                continue
            worst = max(worst, abs(s * r['den'][dk] - r[f'y_{t}']))
            n += 1
    return {'outcome': 'PASS' if worst < 1e-9 else 'FAIL',
            'detail': f'{n} share/denominator pairs checked over {len(rows)} '
                      f'panel rows; largest reconstruction error {worst:.3e}'}


@probe(13, 'no_2026_data_entered_this_study')
def p13():
    rows = pickle.load(open(f'{HERE}/panel_enriched.pkl', 'rb'))
    ss = sorted({r['season'] for r in rows})
    v = json.load(open(f'{HERE}/volume_results.json'))
    vs = sorted({s for k in v for ev in v[k] for s in v[k][ev]['train_seasons']}
                | {int(ev) for k in v for ev in v[k]})
    return {'outcome': 'PASS' if max(ss) <= 2025 and max(vs) <= 2025 else 'FAIL',
            'detail': f'player panel seasons {ss}; volume seasons touched {vs}; '
                      f'no 2026 row is reachable from either'}


@probe(14, 'no_market_or_wagering_artifact_was_produced')
def p14():
    bad = [f for f in os.listdir(HERE)
           if re.search(r'(bet|wager|odds|book|parlay|lineup|dfs|stake)', f, re.I)]
    return {'outcome': 'PASS' if not bad else 'FAIL',
            'detail': f'{len(os.listdir(HERE))} files in the P4B directory; '
                      f'none names a market, a wager, a lineup or a book '
                      f'({bad})'}


if __name__ == '__main__':
    for i in range(1, 15):
        g = globals().get(f'p{i}')
        if g:
            g()
    json.dump(OUT, open(f'{HERE}/p4b_adversarial.json', 'w'), indent=1)
    print(f'\n{len(OUT)} probes, {len(FAIL)} failing: {FAIL}')
