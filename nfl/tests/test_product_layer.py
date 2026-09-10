"""The product layer's guards: no fabrication, no market, no broken seal.

The product layer is where an invented number is most tempting, because a
blank cell looks like a bug. These checks pin the three ways it could lie:
showing a metric the model does not produce, showing a betting number no feed
supplies, and scoring a forecast that may have changed after the outcome.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import confidence as CONF                      # noqa: E402
from nfl.product import distributions as D                      # noqa: E402
from nfl.product import evaluator as EV                         # noqa: E402
from nfl.product import metrics as M                            # noqa: E402
from nfl.product import render as R                             # noqa: E402
from nfl.product import thresholds as TH                        # noqa: E402

PASSED = FAILED = 0
RUN_A = pathlib.Path(_ROOT) / 'nfl/research/shadow/g1_ne_sea'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


# ------------------------------------------------- no fabricated metrics
def test_rb_rushing_yards_are_never_shown():
    """The single most tempting fabrication in the whole product.

    `carries x yards_per_carry` is named in layers.py as the PROHIBITED
    implementation. A product layer is exactly where it would reappear,
    because a rushing projection with no yards looks broken to a reader.
    """
    st, why = M.status_of('rushing', 'rushing_yards')
    check('RB rushing yards are UNAVAILABLE', st == M.UNAVAILABLE, st)
    check('  and the reason names the open control',
          'RUSHING_CONVERSION_CONTROL_UNDEFINED' in
          M.UNSUPPORTED[('rushing', 'rushing_yards')]['code'], why[:60])
    check('  it is not in the supported set',
          ('rushing', 'rushing_yards') not in M.SUPPORTED)
    check('  and no threshold ladder exists for it',
          not TH.ladder('rushing', 'rushing_yards'))
    check('  a back is told the metric is missing, not shown a blank',
          any(u['metric'] == 'rushing/rushing_yards'
              for u in M.unavailable_for('RB')))


def test_every_ladder_names_a_supported_metric():
    """A threshold on a metric the model does not produce would be a number
    with nothing behind it."""
    unsupported = [k for k in TH.LADDERS if k not in M.SUPPORTED]
    check('every threshold ladder is on a supported metric',
          not unsupported, str(unsupported))


def test_renderer_can_only_show_declared_metrics():
    cols = {c for v in R.COLUMNS.values() for c in v}
    bad = [c for c in cols if c not in M.SUPPORTED]
    check('every rendered column is a declared V1 output', not bad, str(bad))


# ------------------------------------------------------- no market feed
def test_no_sportsbook_number_can_enter_the_product():
    src = ''
    for f in ('thresholds.py', 'board.py', 'render.py', 'confidence.py'):
        src += (pathlib.Path(_ROOT) / 'nfl/product' / f).read_text().lower()
    for word in ('odds', 'vig', 'juice', 'moneyline', 'sportsbook_line',
                 'implied_prob', 'closing_line', 'bet_size', 'kelly'):
        check(f'  no {word} in the product layer', word not in src, word)
    check('the disclaimer says these are model probabilities',
          'not a wager recommendation' in TH.DISCLAIMER.lower(),
          TH.DISCLAIMER)
    check('confidence cannot be ranked by edge',
          'no price exists' in CONF.board([])['no_market_feed'])


# ------------------------------------------- probabilities from draws only
def test_threshold_probabilities_are_read_off_the_draws():
    x = np.array([0, 0, 1, 1, 1, 2, 2, 3, 5, 10], float)
    check('P(>= 1) counts the draws at or above 1',
          abs(D.p_at_least(x, 1) - 0.8) < 1e-12, str(D.p_at_least(x, 1)))
    check('P(> 2.5) counts the draws strictly above',
          abs(D.p_over(x, 2.5) - 0.3) < 1e-12, str(D.p_over(x, 2.5)))
    s = D.summary(x)
    check('  the summary reports the draw count it used',
          s['n_draws'] == 10, str(s['n_draws']))
    check('  and every declared percentile', all(f'p{p}' in s
                                                 for p in D.PCTS))


def test_anytime_td_is_a_joint_not_a_product_of_marginals():
    """Two TD columns of the same draw index are the same simulated game."""
    class Fake:
        arrays = {}
        def vector(self, layer, key, pid):
            return {('receiving', 'receiving_td'): np.array([1., 0, 0, 0]),
                    ('rushing', 'rushing_td'): np.array([1., 1, 0, 0])
                    }.get((layer, key))
    got = TH.td_probability(Fake(), 'x', ['receiving', 'rushing'])
    # Draws: (1,1) (0,1) (0,0) (0,0) -> scored in 2 of 4.
    check('anytime is the share of draws with any score',
          abs(got['anytime'] - 0.5) < 1e-12, str(got['anytime']))
    marginal = 1 - (1 - 0.25) * (1 - 0.5)
    check('  and it is NOT the independence product',
          abs(got['anytime'] - marginal) > 1e-9,
          f'{got["anytime"]} == {marginal}')
    check('  2+ is available from the same joint',
          abs(got['two_plus'] - 0.25) < 1e-12, str(got['two_plus']))


def test_a_passing_td_is_not_a_td_the_passer_scored():
    class Fake:
        arrays = {}
        def vector(self, layer, key, pid):
            return {('qb', 'ptd'): np.array([3., 2, 1, 0]),
                    ('qb', 'rtd'): np.array([0., 0, 0, 0])}.get((layer, key))
    got = TH.td_probability(Fake(), 'x', ['qb'])
    check('a passer with 3 passing TD and no rushing TD has anytime 0',
          got['anytime'] == 0.0, str(got['anytime']))
    check('  and the passing TD is still reported separately',
          got['components'].get('qb/ptd') == 0.75,
          str(got['components']))


# --------------------------------------------------- confidence semantics
def test_confidence_means_model_confidence_not_certainty():
    b = CONF.board([])
    check('the board says what its score means',
          'never outcome certainty' in b['means'], b['means'])
    check('  the weights are flat and say why',
          len(set(CONF.WEIGHTS.values())) == 1 and CONF.WEIGHTS_NOTE)
    check('  all five declared dimensions are weighted',
          set(CONF.WEIGHTS) == set(CONF.DIMENSIONS))
    check('  dispersion is defined when the median is zero but spread exists',
          CONF.dispersion(np.array([0., 0, 4, 9])) is not None)
    check('  a zero IQR is DEGENERATE, never perfect precision',
          CONF.dispersion(np.array([0., 0, 0, 0, 0, 0, 0, 5])) is None)
    check('  and it scores zero, not one',
          CONF._score_width(None)[0] == 0.0)


def test_a_bench_player_cannot_outrank_a_starter_on_degeneracy():
    """THE FIRST VERSION OF THIS BOARD DID EXACTLY THAT. Four backup
    quarterbacks and two fifth receivers ranked above both starters, because
    a distribution that is zero in three quarters of its draws has an IQR of
    zero, which scored as a perfect 1.0 for narrowness."""
    starter = np.array([15., 18, 20, 22, 25, 28, 30, 33])
    bench = np.zeros(8)
    bench[-1] = 4.0
    ws, _ = CONF._score_width(CONF.dispersion(starter))
    wb, why = CONF._score_width(CONF.dispersion(bench))
    check('the starter scores higher on width than the bench player',
          ws > wb, f'starter {ws:.2f} vs bench {wb:.2f}')
    check('  and the bench player is told why', 'degenerate' in why, why[:40])


# ------------------------------------------------------------ the seal
def test_scoring_refuses_a_broken_seal():
    rec = EV.verify_seal(RUN_A)
    check('Run A still hashes to its sealed values',
          len(rec['files']) >= 5, str(sorted(rec['files'])))
    check('  and it says which file on disk it actually hashed',
          all(str(RUN_A) in v for v in rec['verified_paths'].values()),
          str(rec['verified_paths']))
    import shutil
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp())
    shutil.copytree(RUN_A, tmp / 'g', dirs_exist_ok=True)
    art = tmp / 'g' / 'forecast_artifact.json'
    d = json.loads(art.read_text())
    d['tampered'] = True
    art.write_text(json.dumps(d))
    try:
        EV.verify_seal(tmp / 'g')
        check('a tampered forecast is refused', False, 'NO_REFUSAL')
    except EV.SealBroken:
        check('a tampered forecast is refused', True)
    # AND THE GUARD MUST BE LOAD-BEARING: without the check the tampered
    # artifact scores happily, so the refusal is doing the work.
    fc = D.Forecast(tmp / 'g')
    check('  the tampered artifact is otherwise perfectly readable',
          fc.game_id == '2026_01_NE_SEA', str(fc.game_id))


def test_a_missing_draw_sidecar_refuses_rather_than_using_quantiles():
    import shutil
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp())
    shutil.copytree(RUN_A, tmp / 'g', dirs_exist_ok=True)
    for n in ('player_draws.npz.gz', 'player_draws.npz'):
        if (tmp / 'g' / n).exists():
            (tmp / 'g' / n).unlink()
    try:
        D.Forecast(tmp / 'g')
        check('no draws -> refusal', False, 'READ_WITHOUT_DRAWS')
    except D.ForecastUnreadable as e:
        check('no draws -> refusal', 'DRAWS_ABSENT' in str(e), str(e)[:60])


# -------------------------------------------------------- the evaluator
def test_scores_match_their_definitions():
    x = np.full(400, 7.0)
    check('CRPS of a point mass is the absolute error',
          abs(EV.crps(x, 3.0) - 4.0) < 1e-12, str(EV.crps(x, 3.0)))
    rng = np.random.default_rng(4)
    s = rng.normal(10.0, 3.0, 300)
    slow = float(np.abs(s - 12.0).mean()
                 - 0.5 * np.abs(s[:, None] - s[None, :]).mean())
    check('  and equals the O(n^2) definition elsewhere',
          abs(EV.crps(s, 12.0) - slow) < 1e-9)
    p = EV.pit(np.array([0., 0, 0, 1, 1, 2, 2, 2, 2, 2]), 1.0)
    check('PIT reports the discrete bracket, not one number',
          abs(p['F_below'] - 0.3) < 1e-12 and abs(p['F_at_or_below'] - 0.5)
          < 1e-12, str(p))


def test_miss_classification_is_a_stated_rule():
    x = np.arange(0, 100, dtype=float)
    check('an actual at the centre is CENTRAL',
          EV.score_metric(x, 50)['miss_class'] == 'CENTRAL')
    check('  one outside 90% but inside support is a TAIL_MISS',
          EV.score_metric(x, 97)['miss_class'] == 'TAIL_MISS',
          EV.score_metric(x, 97)['miss_class'])
    check('  one beyond every draw is OUTSIDE_DISTRIBUTION',
          EV.score_metric(x, 500)['miss_class'] == 'OUTSIDE_DISTRIBUTION')


def test_one_game_can_never_raise_a_refinement_candidate():
    """The bar exists so a single game cannot license a model change."""
    rows = []
    for i in range(40):
        rows.append({'layer': 'qb', 'metric': 'att',
                     'game_id': '2026_01_NE_SEA',
                     'coverage': {'90%': {'covered': False}},
                     'pit': {'mid_pit': 0.99}})
    c = EV.candidates(rows)
    check('40 rows in ONE game raise no candidate', not c['candidates'],
          str(c['candidates']))
    check('  they are held on the watchlist instead',
          'qb/att' in c['below_the_bar_watchlist'])
    spread = [dict(r, game_id=f'2026_01_G{i}') for i, r in enumerate(rows)]
    c2 = EV.candidates(spread)
    check('  the same misses across 40 games do raise one',
          'qb/att' in c2['candidates'], str(c2['candidates'])[:80])
    check('  and the bar is stated in the output',
          str(EV.MIN_GAMES_FOR_CANDIDATE) in c2['bar'], c2['bar'])
    check('  a candidate is a request for a ruling, not a licence',
          'never a licence' in c2['note'])


def test_the_ledger_refuses_an_empty_append():
    try:
        EV.append({'game_id': 'x', 'kickoff_utc': None, 'written_at': None,
                   'run_id': None, 'model_configuration': None,
                   'draw_content_digest': None, 'rows': []},
                  path='nfl/product/_test_empty.jsonl')
        check('an evaluation that scored nothing is refused', False)
    except RuntimeError as e:
        check('an evaluation that scored nothing is refused',
              'WROTE_NO_ROWS' in str(e), str(e)[:60])


def test_aggregates_always_carry_the_cluster_caution():
    s = EV.summarise([{'layer': 'qb', 'metric': 'att', 'crps': 1.0,
                       'median_error': 1.0, 'mean_error': 1.0,
                       'game_id': 'g', 'position': 'QB', 'team': 'NE',
                       'pit': {'mid_pit': 0.5},
                       'coverage': {f'{int(l*100)}%': {'covered': True}
                                    for l in EV.LEVELS},
                       'miss_class': 'CENTRAL'}])
    check('the summary warns that rows are not independent',
          'NOT independent' in s['caution'], s['caution'][:60])
    check('  and tells the reader to read n_games',
          'n_games' in s['caution'])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
