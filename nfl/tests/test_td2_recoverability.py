"""Adversarial tests for TD2 touchdown recoverability.

The estimand is a rare-event conditional probability, so the attack surface is
different from RC1's: denominators, contamination of the TD numerator, and
metrics that can be gamed by shrinking toward a base rate.
"""
import collections, copy, hashlib, json, os, pathlib, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
_R = pathlib.Path(__file__).parents[1] / 'research'
sys.path.insert(0, str(_R / 'td2'))
sys.path.insert(0, str(_R / 'td1'))
sys.path.insert(0, str(_R / 'rc1'))

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
import td2_lib as T                                              # noqa: E402
import run_td2 as R2                                             # noqa: E402
from nfl.tests.bypass import (assert_guard_is_load_bearing,      # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0
_C = {}


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1; print(f'  ok   {label}')
    else:
        FAILED += 1; print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


def frame():
    if 'f' not in _C:
        _C['f'] = T.load('rec', 'targets', 'rec_td')
    return _C['f']


def test_a_chronology():
    print('\nA. leakage: current, future and same-week')
    rs = frame()
    v = next(r for r in rs if r['season'] == 2024 and r['n_opp'] >= 5
             and r['h_games'] >= 8)
    keys = [k for k in v if k.startswith('h_')]
    before = {k: copy.deepcopy(v[k]) for k in keys}
    rs2 = copy.deepcopy(rs)
    kk = (v['season'], v['week'], v['team'], v['gsis_id'])
    for r in rs2:
        if (r['season'], r['week'], r['team'], r['gsis_id']) == kk:
            r['n_td'], r['n_opp'], r['n_rz'] = 9, 9, 9
    T.attach(rs2)
    after = next(r for r in rs2
                 if (r['season'], r['week'], r['team'], r['gsis_id']) == kk)
    moved = [k for k in keys if before[k] != after[k]]
    check('inflating the CURRENT game moves no prior-only field', not moved, moved)
    check('  in particular the current TD does not enter historical conversion',
          before['h_k'] == after['h_k'] and before['h_n'] == after['h_n'])
    check('  and current red-zone opportunity does not enter the predictors',
          before['h_rz'] == after['h_rz'])

    pid = v['gsis_id']
    mine = sorted([r for r in rs if r['gsis_id'] == pid], key=lambda x: x['ord'])
    if len(mine) >= 4:
        early, late = mine[1], mine[-1]
        rs3 = copy.deepcopy(rs)
        for r in rs3:
            if r['gsis_id'] == pid and r['ord'] == late['ord']:
                r['n_td'], r['n_opp'] = 9, 9
        T.attach(rs3)
        e3 = [r for r in rs3 if r['gsis_id'] == pid and r['ord'] == early['ord']][0]
        check('a FUTURE game leaves an earlier row untouched',
              e3['h_k'] == early['h_k'] and e3['h_n'] == early['h_n'])

    c = collections.Counter((r['gsis_id'], r['ord']) for r in rs)
    dup = [k for k, n in c.items() if n > 1]
    check(f'same-week ordinal collisions exist in this frame ({len(dup)})',
          len(dup) > 0, len(dup))
    byk = collections.defaultdict(list)
    for r in rs:
        byk[(r['gsis_id'], r['ord'])].append(r)
    bad = sum(1 for k in dup if byk[k][0]['h_n'] != byk[k][1]['h_n'])
    check('  and neither row at a shared ordinal saw the other', bad == 0, bad)


def test_b_denominators_and_contamination():
    print('\nB. denominators and TD-numerator contamination')
    a2 = json.loads((_R / 'td2' / 'audit_td2.json').read_text())
    # A Counter omits keys it never incremented, so `.get(k, 0) == 0` would let
    # NEVER MEASURED pass as MEASURED ZERO. TD1's audit hit exactly that. Every
    # key here is written explicitly and presence is asserted before any zero
    # is believed.
    missing = [k for k in a2['_measured_keys'] if k not in a2]
    check('every audited key is present, so a 0 means measured-zero',
          not missing, missing)
    ex = a2['named_exclusions']
    check(f"two-point plays are excluded ({ex['two_point_excluded']})",
          ex['two_point_excluded'] > 0)
    check(f"defensive TDs are excluded ({ex['defensive_td_excluded']})",
          ex['defensive_td_excluded'] > 0)
    check(f"fumble/blocked-kick recovery TDs are excluded "
          f"({ex['recovery_or_blocked_kick_td_excluded']})",
          ex['recovery_or_blocked_kick_td_excluded'] > 0)
    check(f"no TD is both a pass TD and a rush TD -- no double attribution "
          f"(measured over {a2['reg_plays']} plays and {a2['td_any']} TDs, "
          f"not inferred from a missing key)",
          a2['td_BOTH_pass_and_rush'] == 0)
    src = (_R / 'td2' / 'build_td2.py').read_text()
    check('the builder EXCLUDES a null yardline rather than coercing it to 0 '
          '(0 would read as the 1-yard line)',
          "named['yardline_null_excluded'] += 1" in src and 'continue' in src)
    check('  and excludes no_play, kneels and spikes from every denominator',
          "no_play_excluded" in src and "kneel_or_spike_excluded" in src)
    check('  and scrambles are separated from designed rushes',
          "rush_td_scramble" in src and "rush_td_designed" in src)

    rs = frame()
    bad = [r for r in rs if r['n_td'] > r['n_opp']]
    check('no row has more TDs than opportunities', not bad, len(bad))
    bad2 = [r for r in rs if r['n_opp'] == 0 and r['n_td'] > 0]
    check('no row has a TD with zero opportunities', not bad2, len(bad2))
    check('every eligible row has at least one opportunity in ITS denominator',
          all(r['n_opp'] >= 1 for r in rs if T.eligible(r)))


def test_c_metrics_cannot_be_gamed_by_shrinkage():
    print('\nC. resolution is the discrimination test')
    n = np.full(400, 10.0)
    rng = np.random.default_rng(1)
    true = rng.beta(2, 40, 400)
    k = rng.binomial(10, true).astype(float)
    base = k.sum() / n.sum()
    flat = T.metrics(n, k, np.full(400, base))
    shrunk = T.metrics(n, k, base + 0.05 * (true - true.mean()))
    real = T.metrics(n, k, true)
    noise = T.metrics(n, k, rng.permutation(true))

    check('a constant-at-base predictor has ZERO resolution',
          flat['resolution'] < 1e-12, flat['resolution'])
    check('  and AUC exactly 0.5', abs(flat['auc'] - 0.5) < 1e-9)
    check('an informative predictor gains resolution over it',
          real['resolution'] > flat['resolution'], real['resolution'])

    # THE PROPERTY THAT MAKES RESOLUTION THE RIGHT TEST, and it is not the one
    # I first assumed. Quantile bins preserve RANKING, so shrinking every
    # prediction toward the base rate leaves resolution UNCHANGED while it
    # changes Brier and reliability. Resolution therefore isolates
    # discrimination from calibration scale -- a model cannot manufacture it
    # by shrinking.
    check('shrinking toward the base rate leaves resolution UNCHANGED -- so '
          'resolution cannot be gamed by shrinkage',
          abs(shrunk['resolution'] - real['resolution']) < 1e-12,
          f"{shrunk['resolution']} vs {real['resolution']}")
    check('  while Brier DOES move, so the pair separates the two effects',
          abs(shrunk['brier'] - real['brier']) > 1e-6)
    check('destroying the RANKING destroys resolution, which is what it '
          'measures',
          noise['resolution'] < real['resolution'] / 2,
          f"{noise['resolution']} vs {real['resolution']}")

    for nm, m in (('flat', flat), ('shrunk', shrunk), ('real', real)):
        check(f'  the EXACT decomposition closes for {nm}',
              abs(m['brier_check'] - m['brier']) < 1e-9,
              f"{m['brier_check']} vs {m['brier']}")
    check('  and the binned closure residual is reported rather than hidden, '
          'because quantile bins leave a within-bin variance term',
          'binned_closure_residual' in real)


def test_d_metric_correctness():
    print('\nD. the metrics themselves')
    n = np.array([10., 10., 10.]); k = np.array([1., 0., 2.])
    perf = T.metrics(n, k, k / n)
    check('AUC on a perfect per-row predictor matches hand calculation '
          '60.5/81 = 0.7469', abs(perf['auc'] - 60.5 / 81) < 1e-9, perf['auc'])
    inv = T.metrics(n, k, 1 - k / n)
    check('  an inverted predictor scores BELOW 0.5, so direction is right',
          inv['auc'] < 0.5, inv['auc'])
    check('base rate is opportunity-weighted, not row-averaged',
          abs(perf['base_rate'] - 3 / 30) < 1e-12)
    check('log loss is finite at p -> 0 and p -> 1 (clipped, not NaN)',
          np.isfinite(T.metrics(n, k, np.zeros(3))['log_loss'])
          and np.isfinite(T.metrics(n, k, np.ones(3))['log_loss']))


def test_e_no_postgame_field_and_no_oracle_in_the_candidate_arm():
    print('\nE. candidate arms read only prior-only information')
    rs = frame()
    r = rs[0]
    prior = [k for k in r if k.startswith('h_')]
    outcome = {'n_td', 'n_opp', 'n_rz', 'all_opp'}
    check('no prior-only field is named after a realised outcome',
          not (set(prior) & outcome), set(prior) & outcome)
    src = (_R / 'td2' / 'run_td2.py').read_text()
    for f in ("r['n_td']", "r['n_opp']", "r['n_rz']"):
        check(f'predict() never reads {f}',
              f not in src.split('def predict(')[1].split('def main(')[0])
    check('loc_bucket uses prior-only history, not the current game',
          "r['h_rz'] / r['h_all_opp']" in src)
    # corrupting the outcome must not move any candidate prediction
    rs2 = copy.deepcopy(rs)
    ev_rows = [r for r in rs2 if T.eligible(r, 2024)]
    last = {}
    for i, r in enumerate(ev_rows):
        last[r['gsis_id']] = i
    tail_idx = sorted(last.values())
    tail = [ev_rows[i] for i in tail_idx]
    for r in tail:
        r['n_td'], r['n_opp'] = 9, 9
    T.attach(rs2)
    B1 = R2.fit(rs, 2024); B2 = R2.fit(rs2, 2024)
    ok = True
    orig = {(r['season'], r['week'], r['team'], r['gsis_id']): r for r in rs}
    for r in tail[:200]:
        o = orig[(r['season'], r['week'], r['team'], r['gsis_id'])]
        for a in ('L0', 'L1', 'L4'):
            if abs(R2.predict(a, o, B1) - R2.predict(a, r, B2)) > 1e-12:
                ok = False
    check('corrupting the realised TD on rows nothing else uses as history '
          'moves NO candidate prediction', ok)


def test_f_training_never_sees_the_evaluation_season():
    print('\nF. fitting is walk-forward')
    rs = frame()
    for ev in T.EVAL:
        tr = [r for r in rs if r['season'] < ev and T.eligible(r)]
        check(f'{ev}: every training row precedes it',
              all(r['season'] < ev for r in tr) and len(tr) > 100, len(tr))
    B = R2.fit(rs, 2022)
    check('the empirical-Bayes prior is fitted, not hard-coded',
          1.0 <= B['_eb']['kappa'] <= 500.0, B['_eb']['kappa'])


def test_g_eligibility_is_not_result_driven():
    print('\nG. the specification is fixed')
    pre = _R / 'td2' / 'predeclaration_td2.md'
    h = hashlib.sha256(pre.read_bytes()).hexdigest()
    check('the pre-registration hash is unchanged',
          h == '31e75d823c0027a9a4f623670a2cf104de6a1eccde8adf4027ae3d2b0f250f83',
          h)
    check('the PRIMARY estimand is the unconditional rate, as predeclared',
          T.PRIMARY == {'rec': 'target', 'rush': 'carry'}, T.PRIMARY)
    check('EVAL seasons are the predeclared four', T.EVAL == [2022, 2023, 2024, 2025])
    check('the seed is a module constant', T.SEED == 20260908)
    # The document is hard-wrapped, so the needle must be searched against
    # whitespace-normalised text. Searching the raw file made this assertion
    # fail on a phrase that is actually present, split across a line break.
    txt = ' '.join(pre.read_text().split())
    check('the pre-registration forbids using TD1 75-77% to set thresholds',
          'may not be used to set, move or justify any threshold' in txt)
    check('  and lists the forbidden ceiling wording',
          'cannot establish an information ceiling' in txt)


def test_h_guard_deletions():
    print('\nH. guard-deletion proofs')

    def run_chrono():
        rs2 = copy.deepcopy(frame())
        T.attach(rs2)
        byk = collections.defaultdict(list)
        for r in rs2:
            byk[(r['gsis_id'], r['ord'])].append(r)
        return sum(1 for v in byk.values()
                   if len(v) > 1 and v[0]['h_n'] != v[1]['h_n'])

    clean = run_chrono()
    check(f'H1 with the prefix cut, 0 shared-ordinal pairs leak ({clean})',
          clean == 0, clean)

    class _Fake:
        @staticmethod
        def bisect_left(a, x):
            return len(a)
    orig = T.bisect
    T.bisect = _Fake
    try:
        leaked = run_chrono()
    finally:
        T.bisect = orig
    check(f'H1 bypassed, {leaked} shared-ordinal pairs DO leak -- the prefix '
          f'cut is load-bearing', leaked > 0, leaked)
    check('  and it is restored', run_chrono() == 0)

    n = np.full(300, 10.0)
    rng = np.random.default_rng(2)
    true = rng.beta(2, 40, 300)
    k = rng.binomial(10, true).astype(float)
    base = k.sum() / n.sum()

    def run_res():
        return T.metrics(n, k, np.full(300, base))
    assert_guard_is_load_bearing(
        run=run_res, module_path='td2_lib', attr='metrics',
        caught=lambda m: m['resolution'] < 1e-12,
        returns={'resolution': 1.0, 'brier': 0.0, 'brier_check': 0.0,
                 'auc': 0.99, 'log_loss': 0.0, 'base_rate': base,
                 'reliability': 0.0, 'uncertainty': 0.0, 'sd_pred': 0.0,
                 'mean_pred': base, 'n_opportunities': 3000, 'n_td': int(k.sum()),
                 'calibration_table': []})
    check('H2 td2_lib.metrics is load-bearing -- bypassed, a constant-at-base '
          'predictor reports resolution 1.0 and would read as signal', True)


if __name__ == '__main__':
    test_a_chronology()
    test_b_denominators_and_contamination()
    test_c_metrics_cannot_be_gamed_by_shrinkage()
    test_d_metric_correctness()
    test_e_no_postgame_field_and_no_oracle_in_the_candidate_arm()
    test_f_training_never_sees_the_evaluation_season()
    test_g_eligibility_is_not_result_driven()
    test_h_guard_deletions()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
