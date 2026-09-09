"""A3G tests: the two teams in a game, and what coupling them must NOT change.

Owner ruling B10. Pre-registration nfl/research/a3g/predeclaration_a3g.md.

The three things these tests are for, in order of how much they would cost if
they were wrong:

  1. `game_coupling='none'` must be BIT-IDENTICAL to the draws that existed
     before A3G. A new mode that quietly moves the default draw is a silent
     change to every number downstream.
  2. The coupling must move no marginal. That is claimed by construction, so
     the test checks the construction -- the index map is exactly uniform and
     the drawn support is unchanged -- rather than only checking a sample
     statistic that noise could hide a real move behind.
  3. Every refusal must be load-bearing. Each of the three new guards is
     bypassed and the refusal must disappear, which is the only way to know the
     refusal came from the guard.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.production import team_volume_v1 as TV                    # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing          # noqa: E402

PASSED = FAILED = 0
TEAMS = ['NE', 'SEA', 'SF', 'LA']
PAIRS = [('NE', 'SEA'), ('SF', 'LA')]
A3G = os.path.join(_ROOT, 'nfl', 'research', 'a3g')
PANEL = os.path.join(_ROOT, 'nfl', 'research', 'inputs', 'denom_panel.csv.gz')
HIST_SNAPS_CORR = -0.4647          # within-game corr(home, away), 1,615 games


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _fc(coupling='none', pairs=None, m=800, seed=31, joint=True, teams=None):
    return TV.forecast(2026, 1, teams or TEAMS, m=m, seed=seed,
                       joint_residuals=joint, game_pairs=pairs,
                       game_coupling=coupling)


def _arr(o, met, t):
    return np.asarray(o.value[(met, t)], float)


# ---------------------------------------------------------------------------
def test_A_the_default_does_not_change():
    print('\nA. A3G is opt-in')
    check('the module default coupling is none',
          TV.GAME_COUPLING_DEFAULT == 'none')
    check('  and JOINT_RESIDUALS_DEFAULT is still False',
          TV.JOINT_RESIDUALS_DEFAULT is False)
    o = TV.forecast(2026, 1, TEAMS, m=200, seed=31)
    check('  a call with no new argument reports coupling none',
          o.state is State.PASS and o.evidence['game_coupling'] == 'none',
          o.evidence.get('game_coupling'))
    check('  and still reports the J1 draw mode it always did',
          o.evidence['draw_mode'] == 'independent_per_metric')


def test_B_none_is_bit_identical_to_the_draws_that_existed_before():
    print('\nB. game_coupling=none changes nothing')
    for joint in (False, True):
        old = TV.forecast(2026, 1, TEAMS, m=400, seed=77,
                          joint_residuals=joint)          # pre-A3G call shape
        new = _fc('none', None, m=400, seed=77, joint=joint)
        same = (old.state is State.PASS and new.state is State.PASS
                and all(np.array_equal(np.asarray(old.value[k], float),
                                       np.asarray(new.value[k], float))
                        for k in old.value))
        check(f'  joint={joint}: identical to the last float', same)
    # and supplying pairs without asking for a coupling must also change nothing
    withp = _fc('none', PAIRS, m=400, seed=77)
    base = _fc('none', None, m=400, seed=77)
    check('  pairs supplied but coupling none: still identical',
          all(np.array_equal(np.asarray(base.value[k], float),
                             np.asarray(withp.value[k], float))
              for k in base.value))


def test_C_the_coupling_is_recovered_only_when_asked_for():
    print('\nC. the within-game dependence')
    ind = _fc('none', None, m=3000)
    cpl = _fc('off_snaps', PAIRS, m=3000)
    check('the coupled run reports the mode it ran',
          cpl.state is State.PASS and cpl.evidence['game_coupling']
          == 'off_snaps', cpl.code)
    for met, target in (('team_off_snaps', HIST_SNAPS_CORR),):
        ci = np.mean([np.corrcoef(_arr(ind, met, a), _arr(ind, met, b))[0, 1]
                      for a, b in PAIRS])
        cj = np.mean([np.corrcoef(_arr(cpl, met, a), _arr(cpl, met, b))[0, 1]
                      for a, b in PAIRS])
        check(f'  {met}: independent draws reproduce essentially nothing',
              abs(ci) < 0.08, ci)
        check(f'  {met}: coupled draws land near the historical {target}',
              abs(cj - target) < 0.10, cj)
        check('  and the sign is right, which independence cannot promise',
              cj < 0, cj)
    # every metric must at least carry the historical sign
    for met, hsign in (('team_dropbacks_part', -1), ('team_targets', -1),
                       ('team_carries', -1), ('team_rz_carries', -1)):
        cj = np.mean([np.corrcoef(_arr(cpl, met, a), _arr(cpl, met, b))[0, 1]
                      for a, b in PAIRS])
        check(f'  {met}: coupled sign matches history', np.sign(cj) == hsign,
              cj)
    # NOTE. These are across-draw correlations for one pair, which is a
    # mechanism check. The like-for-like statistic reality can be compared
    # against -- one draw per game, over the games of a slate, reported as a
    # distribution over draws -- is in nfl/research/a3g/a3g_results.json.


def test_D_the_game_total_stops_being_impossible():
    print('\nD. total game plays')
    lo, hi = 106.0, 173.0                       # the 2020-2025 observed range
    ind = _fc('none', None, m=3000)
    cpl = _fc('off_snaps', PAIRS, m=3000)
    for lbl, o in (('independent', ind), ('coupled', cpl)):
        tot = np.concatenate([_arr(o, 'team_off_snaps', a)
                              + _arr(o, 'team_off_snaps', b)
                              for a, b in PAIRS])
        frac = float(((tot < lo) | (tot > hi)).mean())
        sd = float(tot.std(ddof=1))
        if lbl == 'independent':
            i_frac, i_sd = frac, sd
            check(f'  independent: {frac*100:.2f}% of drawn games are outside '
                  f'the entire observed range, and that is the defect',
                  frac > 0.005, frac)
        else:
            check(f'  coupled: the outside-range fraction at most halves '
                  f'({i_frac*100:.2f}% -> {frac*100:.2f}%)',
                  frac <= i_frac / 2.0, (i_frac, frac))
            check(f'  coupled: SD(total plays) moves toward the historical '
                  f'9.265 ({i_sd:.2f} -> {sd:.2f})',
                  abs(sd - 9.265) < abs(i_sd - 9.265), (i_sd, sd))


def test_E_no_marginal_moves():
    print('\nE. the marginal is preserved by construction')
    # 1. the index map itself, as arithmetic rather than as a sample statistic
    n, k = 41, 13
    u = (np.arange(n * k) + 0.5) / (n * k)
    keys = [('T', i) for i in range(n)]
    score = {kk: float((i * 7) % n) for i, kk in enumerate(keys)}
    counts = np.bincount(TV.coupled_index(u, keys, score), minlength=n)
    check('  floor(u*n) over a uniform grid hits every pool slot equally',
          bool((counts == k).all()), (counts.min(), counts.max()))
    check('  and it never runs off the end of the pool',
          int(TV.coupled_index(np.array([1.0 - 1e-16, 0.0]), keys,
                               score).max()) <= n - 1)
    # 2. the drawn support: both modes resample the SAME finite pool, so with
    #    enough draws the set of attainable values is identical. A mode that
    #    reweighted, clipped or renormalised could not pass this.
    ind = _fc('none', None, m=4000)
    cpl = _fc('off_snaps', PAIRS, m=4000)
    for met in TV.METRICS:
        for t in TEAMS:
            a = set(np.round(_arr(ind, met, t), 9))
            b = set(np.round(_arr(cpl, met, t), 9))
            check(f'  {met}/{t}: identical drawn support ({len(a)} values)',
                  a == b, (len(a), len(b), len(a ^ b)))
            break                       # one team per metric keeps this quick
    # 3. and the summary statistics agree
    for met in TV.METRICS:
        a = np.mean([_arr(ind, met, t).mean() for t in TEAMS])
        b = np.mean([_arr(cpl, met, t).mean() for t in TEAMS])
        check(f'  {met}: slate mean within 3% ({a:.2f} vs {b:.2f})',
              abs(b - a) / max(abs(a), 1e-9) < 0.03)


def test_F_rho_is_read_out_of_history_not_chosen():
    print('\nF. the coupling parameter')
    o = _fc('off_snaps', PAIRS, m=200)
    sel = o.evidence['selections']['team_off_snaps']
    # Recompute it here, from the panel, without touching the production path.
    rows = []
    with gzip.open(PANEL, 'rt') as fh:
        for r in csv.DictReader(fh):
            r['ord'] = int(r['ord'])
            for m2 in TV.METRICS:
                r[m2] = int(r[m2])
            rows.append(r)
    pool = {(r['team'], r['ord']): r for r in rows
            if all(r[m2] > 0 for m2 in TV.METRICS)}
    x, y = [], []
    for (t, od), r in pool.items():
        k2 = (r['opponent'], od)
        if k2 in pool:
            x.append(r['team_off_snaps'])
            y.append(pool[k2]['team_off_snaps'])
    rs = float(np.corrcoef(TV._rank_avg(x), TV._rank_avg(y))[0, 1])
    check('  the reported rho_spearman is the panel value, recomputed here',
          abs(sel['rho_spearman'] - rs) < 1e-9,
          (sel['rho_spearman'], rs))
    check('  the reported rho is its Gaussian-copula inversion',
          abs(sel['rho_gaussian']
              - 2.0 * np.sin(np.pi * sel['rho_spearman'] / 6.0)) < 1e-12)
    check('  it is negative, as six seasons of NFL games say it must be',
          sel['rho_gaussian'] < 0, sel['rho_gaussian'])
    check('  and the paired-game count it was estimated on is reported',
          sel['coupling_paired_games'] == len(x) // 2,
          (sel['coupling_paired_games'], len(x) // 2))
    check('  no team row was left uncoupled on a fully paired slate',
          sel['rows_not_game_coupled'] == 0, sel['rows_not_game_coupled'])


def test_G_determinism_and_per_game_streams():
    print('\nG. draw semantics')
    a = _fc('off_snaps', PAIRS, m=300, seed=5)
    b = _fc('off_snaps', PAIRS, m=300, seed=5)
    c = _fc('off_snaps', PAIRS, m=300, seed=6)
    check('  same seed reproduces exactly',
          all(np.array_equal(np.asarray(a.value[k], float),
                             np.asarray(b.value[k], float)) for k in a.value))
    check('  a different seed does not',
          any(not np.array_equal(np.asarray(a.value[k], float),
                                 np.asarray(c.value[k], float))
              for k in a.value))
    p = _fc('off_snaps', [('SEA', 'NE'), ('LA', 'SF')], m=300, seed=5)
    check('  pair order does not change the game: (NE,SEA) and (SEA,NE) are '
          'the same game',
          all(np.array_equal(np.asarray(a.value[k], float),
                             np.asarray(p.value[k], float))
              for k in a.value if k[1] in ('NE', 'SEA')))
    check('  two different games get different substreams',
          TV._pair_stream('NE', 'SEA') != TV._pair_stream('SF', 'LA'))
    # The whole point of nfl/production/seeds.py: builtin hash() is randomised
    # per process, so a substream derived from it is a different stream on
    # every run. This one must not be.
    code = ('import sys; sys.path.insert(0, %r); '
            'from nfl.production import team_volume_v1 as TV; '
            'print(TV._pair_stream("NE", "SEA"))' % _ROOT)
    outs = set()
    for hs in ('0', '1', '2'):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        outs.add(subprocess.run([sys.executable, '-c', code], env=env,
                                capture_output=True, text=True).stdout.strip())
    check('  and the substream is the same under every PYTHONHASHSEED',
          len(outs) == 1 and outs != {''}, outs)


def test_H_every_guard_refuses_and_is_load_bearing():
    print('\nH. the refusals')

    def runner(**kw):
        def go():
            try:
                o = TV.forecast(2026, 1, TEAMS, m=50, **kw)
            except Exception as e:                            # noqa: BLE001
                return f'RAISED:{type(e).__name__}'
            return o.code
        return go

    cases = [
        ('assert_coupling_is_declared', 'GAME_COUPLING_UNKNOWN',
         dict(joint_residuals=True, game_coupling='sideways',
              game_pairs=PAIRS)),
        ('assert_coupling_has_joint_index', 'GAME_COUPLING_WITHOUT_JOINT_INDEX',
         dict(joint_residuals=False, game_coupling='off_snaps',
              game_pairs=PAIRS)),
        ('assert_pairs_are_usable', 'GAME_COUPLING_WITHOUT_PAIRS',
         dict(joint_residuals=True, game_coupling='off_snaps')),
    ]
    for attr, code, kw in cases:
        got = runner(**kw)()
        check(f'  {code} is returned', got == code, got)
        try:
            assert_guard_is_load_bearing(
                run=runner(**kw),
                module_path='nfl.production.team_volume_v1', attr=attr,
                caught=lambda r, c=code: r == c, returns=None)
            check(f'    and {attr} is load-bearing (bypassed, the refusal '
                  f'disappears)', True)
        except AssertionError as e:
            check(f'    and {attr} is load-bearing', False, str(e)[:200])
    # the pair-shape refusals, which share one guard
    for code, pairs in (
            ('GAME_PAIR_TEAM_NOT_ON_SLATE', [('NE', 'KC')]),
            ('GAME_PAIR_TEAM_REPEATED', [('NE', 'SEA'), ('NE', 'SF')]),
            ('GAME_PAIR_SELF', [('NE', 'NE')]),
            ('GAME_PAIR_MALFORMED', [('NE', 'SEA', 'SF')])):
        got = runner(joint_residuals=True, game_coupling='off_snaps',
                     game_pairs=pairs)()
        check(f'  {code} is returned', got == code, got)


def test_I_the_recorded_experiment():
    print('\nI. the recorded A3G experiment')
    prereg = os.path.join(A3G, 'predeclaration_a3g.md')
    runner = os.path.join(A3G, 'run_a3g.py')
    res = os.path.join(A3G, 'a3g_results.json')
    for f in (prereg, runner, res):
        if not os.path.exists(f):
            check(f'{os.path.basename(f)} exists', False, f)
            return
    sha = hashlib.sha256(open(prereg, 'rb').read()).hexdigest()
    pinned = re.search(r"PREREG = '([0-9a-f]{64})'",
                       open(runner).read()).group(1)
    check('  the runner pins the pre-registration it actually ran under',
          pinned == sha, (pinned, sha))
    r = json.load(open(res))
    check('  the result cites that same hash', r.get('prereg_sha256') == sha)
    check('  it is labelled EXPLORATORY', 'EXPLORATORY' in r['label'])
    check('  it names the owner ruling it was authorised by',
          r.get('owner_ruling') == 'B10')
    check('  the index map uniformity proof passed in the run',
          r['index_map_uniformity_proof']['every_slot_exactly_k_times'] is True)
    check('  every historical game paired; none was half-used',
          r['historical']['n_unpaired_dropped'] == 0
          and r['historical']['n_paired_games'] == 1615,
          (r['historical']['n_paired_games'],
           r['historical']['n_unpaired_dropped']))
    check('  no production default was changed by the run',
          r['decision']['production_default_unchanged'] is True)
    inc = r['decision']['incumbent']
    off = r['decision']['off_snaps']
    check('  the incumbent draws game totals outside the observed range',
          inc['outside_range_fraction'] > 0.005,
          inc['outside_range_fraction'])
    check('  off_snaps coupling cuts that by at least half',
          off['clauses']['3_outside_range_at_most_half'] is True,
          off['outside_range_fraction'])
    check('  and brings SD(total plays) inside the 15% band',
          off['clauses']['2_R_within_0.15'] is True, off['R'])
    check('  every metric carries the historical sign under it',
          all(off['sign_matches_history'].values()))
    check('  the pre-registered verdict is recorded as it fell, not as hoped',
          r['decision']['recommended_mode'] == 'none'
          and r['decision']['candidates_clearing_all_clauses'] == [],
          r['decision']['recommended_mode'])


def test_J_the_two_defective_clauses_are_demonstrated_not_asserted():
    """Clauses 5 and 6 of the pre-registration failed the winning candidate.

    Claiming afterwards that a clause was wrong is worth nothing on its own, so
    the claim is tested: the INCUMBENT is re-run against ITSELF under different
    seeds and judged by the same two clauses. If it fails its own clause
    against itself, the clause is measuring Monte Carlo noise.
    """
    print('\nJ. the clauses that failed, judged against the incumbent itself')
    f = os.path.join(A3G, 'a3g_marginal_noise.json')
    if not os.path.exists(f):
        check('a3g_marginal_noise.json exists', False, f)
        return
    r = json.load(open(f))
    check('  it is labelled POST-HOC and claims no pre-registered standing',
          'POST-HOC' in r['label'])
    c5 = r['clause5_incumbent_against_itself']
    check('  clause 5 rejects the incumbent against itself, in every seed pair',
          c5['seed_pairs_failing_the_1pct_clause'] == c5['n_seed_pairs'],
          (c5['seed_pairs_failing_the_1pct_clause'], c5['n_seed_pairs']))
    check('    and the blow-up is a near-zero denominator on a low-count '
          'quantile, not a moved marginal',
          c5['worst_example']['statistic'] == 'p05'
          and 'rz_carries' in c5['worst_example']['at'],
          c5['worst_example'])
    c6 = r['clause6_zero_floor_draws']
    check('  clause 6 fails the incumbent against itself too',
          c6['incumbent_seed_pairs_where_a_later_seed_exceeds_an_earlier_one']
          > 0, c6['incumbent_by_seed'])
    check('    and the arms differ by less than one seed-noise SE',
          abs(c6['candidate_mean_minus_incumbent_mean'])
          < c6['seed_se_of_the_difference'],
          (c6['candidate_mean_minus_incumbent_mean'],
           c6['seed_se_of_the_difference']))
    z = r['across_seed_z_test']['per_statistic']
    check('  on a noise-referenced test no marginal statistic moves: the share '
          'above z=2 stays inside what a 6-seed SE produces by chance',
          all(v['share_above_2'] <= 0.12 for v in z.values()),
          {k: v['share_above_2'] for k, v in z.items()})


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks')


if __name__ == '__main__':
    for _n in sorted(n for n in dir() if n.startswith('test_')):
        globals()[_n]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
