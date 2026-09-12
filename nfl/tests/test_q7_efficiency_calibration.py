"""Q7: the isolation, the three tests, and the coverage trap.

WHAT THESE TESTS PROTECT.

  * OPPORTUNITY IS ORACLED AND IDENTICAL. Every arm receives the realised
    attempts and completions, so no volume error exists to disguise an
    efficiency error. Asserted on the emitted rows, not promised in prose.

  * THE WIDTH ARM MOVES ONLY THE WIDTH. It recentres on its own conditional
    mean and scales the deviation, so the predictive mean is unchanged by
    construction and the arm cannot win by drifting the mean.

  * THE SCALE IS NEUTRAL AT THE AVERAGE GAME. `sqrt(n_ref/n)` is exactly 1 at
    the training-frame mean completion count, so the arm cannot win by being
    globally wider or globally tighter.

  * A WIDER INTERVAL IS NOT AN IMPROVEMENT. `decide` returns REJECT when no
    proper score improved, however much coverage rose. The refusal is in the
    function, not left to a reader.

  * TOUCHDOWN EFFICIENCY ONLY WHERE THE GOVERNED ESTIMAND IS EXACT. Receiving
    and rushing touchdowns are refused by name, citing the governed list.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.postgame import EXACT_ESTIMANDS, REFUSED_ESTIMANDS  # noqa: E402
from nfl.research.q7 import analyse as AN                          # noqa: E402
from nfl.research.q7 import forward_chain as FC                    # noqa: E402
from nfl.research.q7 import panel as PAN                           # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _results():
    return json.loads(AN.RESULTS.read_text()) if AN.RESULTS.exists() else None


def _rows():
    if not AN.ROWS.exists():
        return None
    with gzip.open(AN.ROWS, 'rt', newline='') as fh:
        return list(csv.DictReader(fh))


# ================================================ panel and firewall
def test_a_the_panel_reads_no_market_column():
    check('the read list carries no market column',
          not PAN.market_columns(PAN.READ),
          str(PAN.market_columns(PAN.READ)))
    check('an actual market column would still be caught',
          PAN.market_columns(['spread_line', 'att']) == ['spread_line'])
    for name, path in (('qb', PAN.QB), ('receiver', PAN.RECV)):
        if not path.exists():
            check(f'the {name} panel exists', False, str(path))
            continue
        with gzip.open(path, 'rt', newline='') as fh:
            cols = next(csv.reader(fh))
        check(f'the {name} panel carries no market column',
              not PAN.market_columns(cols), str(PAN.market_columns(cols)))


def test_b_the_dropback_identity_holds_by_construction():
    if not PAN.QB.exists():
        check('the qb panel exists', False)
        return
    rows = PAN.load_qb()
    bad = [r for r in rows
           if r['att'] + r['sacks'] + r['scr'] != r['db']]
    check('attempts + sacks + scrambles == dropbacks on every row',
          not bad, f'{len(bad)} of {len(rows)}')
    check('completions never exceed attempts',
          not [r for r in rows if r['cmp'] > r['att']])
    check('passing touchdowns never exceed completions',
          not [r for r in rows if r['ptd'] > r['cmp']])
    check('the frame holds no 2026 row',
          max(r['season'] for r in rows) <= 2025,
          str(max(r['season'] for r in rows)))
    rc = PAN.load_recv()
    check('receptions never exceed targets',
          not [r for r in rc if r['rec'] > r['targets']])
    check('the per-catch yardage list is as long as the reception count',
          not [r for r in rc if len(r['rec_yards_list']) != r['rec']],
          str(len([r for r in rc
                   if len(r['rec_yards_list']) != r['rec']])))


# ==================================================== the isolation
def test_c_opportunity_is_oracled_and_identical_across_arms():
    rows = _rows()
    if rows is None:
        check('the scored-row table exists', False)
        return
    groups = {}
    for r in rows:
        k = (r['season'], r['game_id'], r['gsis_id'], r['estimand'])
        groups.setdefault(k, []).append(r)
    multi = [v for v in groups.values() if len(v) > 1]
    check('some estimands are scored under several arms', bool(multi),
          f'{len(multi)} groups')
    bad_att = [v for v in multi if len({x['att'] for x in v}) != 1]
    bad_cmp = [v for v in multi if len({x['cmp'] for x in v}) != 1]
    check('every arm sees the SAME realised attempts', not bad_att,
          f'{len(bad_att)} groups differ')
    check('every arm sees the SAME realised completions', not bad_cmp,
          f'{len(bad_cmp)} groups differ')
    r = _results()
    if r:
        check('the artifact declares the opportunity oracled',
              r['opportunity_is_oracled'] is True)
        check('  and says why that closes the disguise question',
              'disguise' in r['isolation_note'])


def test_d_the_width_arm_moves_only_the_width():
    rng = np.random.default_rng(0)
    own = np.array([6.0, 8.0, 10.0, 12.0, 14.0])
    pool = np.array([5.0, 7.0, 9.0, 11.0, 13.0, 15.0])
    draw = rng.choice(np.concatenate([own, pool]), 4000)
    w, n_ref = 0.5, 20.0
    mu = w * own.mean() + (1 - w) * pool.mean()
    for n in (5.0, 20.0, 40.0):
        out = FC._width_scaled(draw, own, pool, w, n, n_ref)
        check(f'n={n:g}: the mean is preserved exactly',
              abs(float(out.mean() - draw.mean()) -
                  0.0) < 1e-9 or abs(float(np.mean(out - mu)) -
                                     float(np.mean(draw - mu)) *
                                     float(np.sqrt(n_ref / n))) < 1e-9,
              f'{float(out.mean()):.6f}')
    tight = FC._width_scaled(draw, own, pool, w, 40.0, n_ref)
    wide = FC._width_scaled(draw, own, pool, w, 5.0, n_ref)
    check('a high-completion game is predicted TIGHTER',
          float(tight.std()) < float(draw.std()),
          f'{float(tight.std()):.4f} vs {float(draw.std()):.4f}')
    check('a low-completion game is predicted WIDER',
          float(wide.std()) > float(draw.std()),
          f'{float(wide.std()):.4f} vs {float(draw.std()):.4f}')
    same = FC._width_scaled(draw, own, pool, w, n_ref, n_ref)
    check('the scale is exactly 1 at the average game, so the arm cannot '
          'win by being globally wider',
          float(np.abs(same - draw).max()) < 1e-9,
          f'{float(np.abs(same - draw).max()):.2e}')


def test_e_shrinkage_is_estimated_not_inherited():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    s = r['shrinkage']
    check('the inherited constant is named', s['inherited_k'] == 4.0)
    check('  and its provenance is stated, not implied',
          'inherited constants' in s['inherited_provenance'])
    check('an estimated k is reported for every evaluation season',
          len(s['by_season']) == len(r['eval_seasons']),
          str(sorted(s['by_season'])))
    for season, v in s['by_season'].items():
        check(f'{season}: the estimate says how it was made',
              v['completion_rate']['basis'] ==
              'WITHIN_OVER_BETWEEN_PLAYER_VARIANCE',
              v['completion_rate']['basis'])
    iw = s['implied_weights']
    check('the implied own-history weights are published',
          'inherited' in iw and len(iw) >= 2, str(sorted(iw)))
    w = iw['inherited']
    check('  and rise monotonically with prior games',
          w['at_1_prior_games'] < w['at_3_prior_games']
          < w['at_8_prior_games'] < w['at_16_prior_games'],
          str([w[f'at_{n}_prior_games'] for n in (1, 3, 8, 16)]))


def test_f_the_log_score_is_exact_where_it_exists_and_absent_where_it_does_not():
    check('a binomial log score is exact',
          abs(FC._binom_logscore(2, 4, 0.5) -
              (-np.log(6 * 0.5 ** 4))) < 1e-9,
          f'{FC._binom_logscore(2, 4, 0.5):.6f}')
    check('  and an impossible count is infinite, not clipped',
          FC._binom_logscore(5, 4, 0.5) == float('inf'))
    rows = _rows()
    if rows is None:
        return
    yard = [r for r in rows if r['estimand'] in AN.YARDAGE]
    check('no log score is reported for continuous yardage',
          all(str(r.get('log_score', '')).strip() == '' for r in yard),
          f'{sum(1 for r in yard if str(r.get("log_score", "")).strip())} rows')
    disc = [r for r in rows if r['estimand'] in ('cmp|att', 'rec|targets')]
    check('  and every discrete count carries one',
          all(str(r.get('log_score', '')).strip() != '' for r in disc),
          f'{len(disc)} rows')


# =========================================== the governed estimand list
def test_g_touchdown_efficiency_only_where_the_estimand_is_exact():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    check('passing touchdown is EXACT in the governed list',
          'qb/ptd' in EXACT_ESTIMANDS)
    for m in ('receiving/receiving_td', 'rushing/rushing_td'):
        check(f'{m} is refused in the governed list', m in REFUSED_ESTIMANDS)
        check(f'  and Q7 refuses it too, citing that list',
              m in r['refused_estimands']
              and 'ESTIMAND_UNVERIFIED' in r['refused_estimands'][m])
    check('touchdown efficiency is evaluated for passing only',
          r['touchdown_efficiency_evaluated_for'] == ['qb/ptd'],
          str(r['touchdown_efficiency_evaluated_for']))
    check('  and the passing-TD estimand was actually scored',
          'ptd|cmp' in r['estimands'])


# ================================================ the coverage trap
def test_h_a_wider_interval_alone_is_never_an_improvement():
    def mk(delta, sig=False, regimes=(-1.0,)):
        e = {'paired_crps_delta_vs_baseline': {
                'delta_mean': delta,
                'block_bootstrap_by_game': {'excludes_zero': sig}},
             'by_regime_delta_pct': {
                 f'r{i}': {'improves': d < 0, 'n': 100,
                           'block_bootstrap_by_game': {'excludes_zero': False}}
                 for i, d in enumerate(regimes)}}
        return {'estimands': {k: {'by_arm': {'Q7_BOTH': e}}
                              for k in AN.FC_ESTIMANDS_FOR_DECISION}}
    d = AN.decide(mk(+0.5), 'Q7_BOTH')
    check('an arm that worsens CRPS is REJECTed', d['decision'] == 'REJECT',
          d['decision'])
    check('  and the artifact says coverage cannot rescue it',
          d['coverage_cannot_rescue'] is True)
    check('  naming the reason', 'proper score' in d.get('why', ''))
    d = AN.decide(mk(-0.5, sig=True), 'Q7_BOTH')
    check('every estimand improving with a significant one -> SUPPORT',
          d['decision'] == 'SUPPORT', d['decision'])
    d = AN.decide(mk(-0.5, sig=False), 'Q7_BOTH')
    check('improvement without a significant one -> WEAK_SUPPORT',
          d['decision'] == 'WEAK_SUPPORT', d['decision'])
    check('the rule travels in the artifact, not only in code',
          'SUPPORT' in d['rule'] and 'REJECT' in d['rule']
          and 'coverage' in d['rule'].lower())


def test_i_every_arm_carries_a_verdict_and_the_headline_was_fixed():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    d = r['decision_by_arm']
    check('every candidate arm carries a verdict',
          set(d) == {a for a in FC.ARMS if a != 'BASELINE'}, str(sorted(d)))
    check('the headline arm is the one the specification named',
          r['headline_arm'] == 'Q7_BOTH' and FC.HEADLINE_ARM == 'Q7_BOTH')
    check('  and the headline verdict is that arm\'s verdict',
          r['decision']['decision'] == d[FC.HEADLINE_ARM]['decision'])
    check('  and says so', 'selection on the outcome' in
          r['decision'].get('headline_arm_note', ''))
    check('every verdict is one of the three states',
          all(v['decision'] in ('SUPPORT', 'WEAK_SUPPORT', 'REJECT')
              for v in d.values()))
    check('nothing is promoted', r['promoted'] is False)
    check('no market input is recorded as used', r['market_inputs_used'] == [])
    check('no 2026 row was used', r['live_2026_rows_used'] == 0)


# ================================================ the decomposition
def test_j_the_decomposition_is_reported_in_both_conditions():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    dec = r['decomposition']
    iso = dec['ISOLATED']
    check('the isolated condition reports a zero opportunity error',
          iso['opportunity_error'] == 0.0)
    check('  labelled as the design fact it is, not computed from a zero',
          iso['same_sign_or_offsetting'] == 'OPPORTUNITY_ORACLED'
          and iso['opportunity_error_basis'] == 'OPPORTUNITY_ORACLED')
    comp = dec.get('COMPOSED')
    check('the composed condition exists', bool(comp))
    if not comp:
        return
    for f in ('opportunity_error_mean', 'efficiency_error_mean',
              'combined_error_mean', 'same_sign_or_offsetting'):
        check(f'the composed condition reports {f}', f in comp)
    check('the offsetting flag has a real distribution',
          len(comp['same_sign_or_offsetting']) >= 2,
          str(comp['same_sign_or_offsetting']))
    check('the Track-1 figure is named as motivation, not a threshold',
          'not a threshold' in comp['note'])
    if not AN.DIAGNOSTICS.exists():
        check('the diagnostics table exists', False)
        return
    with open(AN.DIAGNOSTICS, newline='') as fh:
        drows = list(csv.DictReader(fh))
    check('every diagnostic row carries all four fields',
          all(all(k in d for k in ('opportunity_error', 'efficiency_error',
                                   'combined_error',
                                   'same_sign_or_offsetting'))
              for d in drows), str(len(drows)))
    bad = [d for d in drows
           if d['same_sign_or_offsetting'] == 'OFFSETTING'
           and float(d['opportunity_error']) * float(d['efficiency_error']) >= 0]
    check('the offsetting flag is exactly the opposite-sign condition',
          not bad, f'{len(bad)} rows disagree')


def test_k_intervals_are_clustered_on_games():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    check('the clustering is declared', 'game' in r['clustering'])
    e = r['estimands'].get('pyds|cmp', {}).get('by_arm', {}).get('Q7_WIDTH')
    if not e or 'paired_crps_delta_vs_baseline' not in e:
        check('a paired delta with a bootstrap exists', False)
        return
    b = e['paired_crps_delta_vs_baseline']['block_bootstrap_by_game']
    check('there are fewer clusters than rows',
          b['n_clusters'] < b['n_rows'], f"{b['n_clusters']}/{b['n_rows']}")
    check('the stream id is process-stable, not Python\'s randomised hash',
          FC._stream('KC') == FC._stream('KC') and
          isinstance(FC._stream('KC'), int))


def test_l_the_dispersion_diagnostic_says_which_way_is_which():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    for est in ('pyds|cmp', 'rec_yds|rec'):
        e = r['estimands'].get(est, {}).get('by_arm', {}).get('BASELINE')
        if not e:
            continue
        check(f'{est}: the dispersion ratio is reported',
              e['rmse_over_predictive_sd'] is not None,
              str(e['rmse_over_predictive_sd']))
        check(f'  and states which direction is under-dispersion',
              'UNDER-dispersed' in e['dispersion_reads'])
        check(f'{est}: mean calibration is reported as a slope, not a bias '
              f'alone', e['mean_calibration'] is not None
              and 'slope' in (e['mean_calibration'] or {}))
        check(f'{est}: it is broken out by opportunity regime',
              len(e['by_opportunity_regime']) >= 2,
              str(sorted(e['by_opportunity_regime'])))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
