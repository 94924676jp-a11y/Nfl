"""The market comparator: exact, downstream, and provably unable to reach back.

WHAT THESE TESTS PROTECT.

  * EXACT, NOT FITTED. The export used to fill
    `model_probability_over_market_line` from a Normal or an interpolation
    between stored percentiles while the Monte Carlo draws sat beside it. A
    receiving distribution with 40% of its mass at exactly zero is not Normal
    in any useful sense and a percentile interpolation cannot see the atom.

  * THE LINE MOVES THE ANSWER AND NOTHING ELSE. A market value that could
    reach a model input would make every downstream number circular. The test
    is not a promise: the draw digest is taken before and after and compared.

  * A PUSH IS AN ATOM. On a whole-number line a discrete metric can land
    exactly on it. That outcome is neither a win nor a loss and is never
    folded into a side.
"""
from __future__ import annotations

import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import market_cdf as MC                             # noqa: E402
from nfl.production.nonqb import inputs as PIN                       # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


# A SYNTHETIC quote. There is no Hard Rock snapshot in this repository -- the
# only market artifact from 2026-09-13 is market_comparators.json with
# status ACCESS_BLOCKED and zero rows -- so none is used and none is invented.
QUOTE = {'line': 3.5, 'over_price': -130, 'under_price': +110,
         'retrieved_at': '2026-09-13T15:02:11Z', 'source': 'SYNTHETIC_TEST',
         'market_timestamp': '2026-09-13T15:00:00Z'}
DRAWS = np.array([0, 0, 0, 1, 2, 3, 3, 4, 5, 9], dtype=float)


def test_a_probabilities_are_counted_not_fitted():
    r = MC.compare(DRAWS, 'receiving/receptions', QUOTE)
    e = r['exact_probability']
    check('P(over) is the fraction of draws above the line',
          e['p_over'] == 0.3 and e['n_over'] == 3, str(e['n_over']))
    check('P(under) is the fraction below', e['p_under'] == 0.7,
          str(e['n_under']))
    check('the three parts partition the draws exactly',
          e['n_over'] + e['n_under'] + e['n_push'] == e['n_draws'])
    check('  and the probabilities sum to exactly 1',
          e['p_over'] + e['p_under'] + e['p_push'] == 1.0)
    check('the CDF at the line is P(X <= line)',
          e['model_cdf_at_line'] == 0.7)
    check('the method says what it is',
          e['method'] == 'EMPIRICAL_COUNT_OVER_STORED_DRAWS')
    check('  and what it is not',
          'no Normal was fitted' in e['not_method'])
    # a Normal would be materially wrong here, which is the point
    from math import erf, sqrt
    mu, sd = float(DRAWS.mean()), float(DRAWS.std(ddof=0))
    normal_over = 0.5 * (1 - erf((3.5 - mu) / (sd * sqrt(2))))
    check('a fitted Normal would give a different answer',
          abs(normal_over - e['p_over']) > 0.05,
          f'normal {normal_over:.3f} vs exact {e["p_over"]:.3f}')


def test_b_the_market_cannot_change_the_model_draws():
    before = MC.draws_digest(DRAWS)
    snapshot = DRAWS.copy()
    for line in (0.5, 3.5, 100.0):
        MC.compare(DRAWS, 'receiving/receptions', dict(QUOTE, line=line))
    check('the draw array is untouched after three comparisons',
          np.array_equal(DRAWS, snapshot))
    check('  and its content digest is unchanged',
          MC.draws_digest(DRAWS) == before, before[:16])
    r = MC.compare(DRAWS, 'receiving/receptions', QUOTE)
    check('the comparator records the digest either side of itself',
          r['model_draws_sha256'] == r['model_draws_sha256_after'] == before)
    check('  and says so explicitly', r['draws_unchanged'] is True)


def test_c_changing_only_the_line_changes_only_the_cdf():
    a = MC.compare(DRAWS, 'receiving/receptions', QUOTE)
    b = MC.compare(DRAWS, 'receiving/receptions', dict(QUOTE, line=0.5))
    check('the model summary is identical', a['model'] == b['model'])
    check('  including mean and median',
          a['model']['mean'] == b['model']['mean'] and
          a['model']['median'] == b['model']['median'])
    check('the implied prices are identical',
          a['implied_over'] == b['implied_over'] and
          a['implied_under'] == b['implied_under'])
    check('the de-vigged probabilities are identical',
          a['no_vig'] == b['no_vig'])
    check('ONLY the exact probability block moved',
          a['exact_probability'] != b['exact_probability'])
    check('  and it moved in the right direction',
          b['exact_probability']['p_over'] > a['exact_probability']['p_over'],
          f"{a['exact_probability']['p_over']} -> "
          f"{b['exact_probability']['p_over']}")


def test_d_vig_removal_reconciles_to_one():
    r = MC.compare(DRAWS, 'receiving/receptions', QUOTE)
    check('the raw implied probabilities sum to MORE than 1',
          r['implied_sum_with_vig'] > 1.0,
          f"{r['implied_sum_with_vig']:.4f}")
    nv = r['no_vig']
    check('the de-vigged pair sums to exactly 1',
          nv['no_vig_over'] + nv['no_vig_under'] == 1.0)
    check('  and the module asserts it itself',
          nv['reconciles_to_one'] is True)
    check('the hold is reported, not absorbed',
          abs(nv['hold'] - (r['implied_sum_with_vig'] - 1.0)) < 1e-12,
          f"{nv['hold']:.4f}")
    check('the method is named rather than assumed',
          nv['method'] == 'proportional')
    check('a missing price yields no de-vig rather than a guess',
          MC.devig_proportional(0.5, None)['no_vig_over'] is None)
    check('american odds convert correctly on both signs',
          abs(MC.american_to_implied(-110) - 110 / 210) < 1e-12 and
          abs(MC.american_to_implied(+150) - 100 / 250) < 1e-12)


def test_e_discrete_push_is_explicit():
    r = MC.compare(DRAWS, 'receiving/receptions', dict(QUOTE, line=3))
    e = r['exact_probability']
    check('a whole line on a discrete metric can push',
          e['push_possible'] is True)
    check('  and the pushing draws are counted', e['n_push'] == 2,
          str(e['n_push']))
    check('  the push is its own probability', e['p_push'] == 0.2)
    check('  it is NOT folded into either side',
          e['p_over'] == 0.3 and e['p_under'] == 0.5)
    check('  and the three still sum to 1',
          e['p_over'] + e['p_under'] + e['p_push'] == 1.0)
    h = MC.compare(DRAWS, 'receiving/receptions', QUOTE)['exact_probability']
    check('a half line cannot push', h['p_push'] == 0.0 and
          h['push_possible'] is False)
    y = MC.compare(DRAWS, 'receiving/receiving_yards',
                   dict(QUOTE, line=3))['exact_probability']
    check('a continuous metric on a whole line is not marked pushable',
          y['push_possible'] is False and y['metric_is_discrete'] is False)


def test_f_the_frozen_market_timestamp_is_carried_unchanged():
    r = MC.compare(DRAWS, 'receiving/receptions', QUOTE)
    check('retrieved_at is echoed verbatim',
          r['market']['retrieved_at'] == QUOTE['retrieved_at'])
    check('market_timestamp is echoed verbatim and kept apart from it',
          r['market']['market_timestamp'] == QUOTE['market_timestamp'] and
          r['market']['market_timestamp'] != r['market']['retrieved_at'])
    check('the source is carried', r['market']['source'] == 'SYNTHETIC_TEST')
    check('the comparison clock is a THIRD field, not a restamp',
          r['computed_at'] not in (QUOTE['retrieved_at'],
                                   QUOTE['market_timestamp']))


def test_g_no_sportsbook_field_can_enter_a_model_input():
    # EXACT MATCH AGAINST A FROZENSET, never a substring. 'line' is a
    # substring of 'yardline_100' and of 'baseline', and this repository has
    # been bitten three times by a guard that matched the middle of a word.
    feature_fields = set()
    for spec in PIN.APPEARANCE_CONTRACT.values():
        feature_fields.update(spec.get('fields') or ())
    check('the appearance contract declares its fields', bool(feature_fields),
          str(sorted(feature_fields)))
    overlap = feature_fields & set(MC.MARKET_FIELDS)
    check('NO market field appears in any model feature input',
          not overlap, str(sorted(overlap)))
    check('  and the check is exact, not substring',
          'line' not in feature_fields and
          any('line' in f for f in {'yardline_100', 'baseline'}))
    check('the comparator declares the only fields it may read',
          set(MC.MARKET_FIELDS) == {'line', 'over_price', 'under_price',
                                    'retrieved_at', 'source',
                                    'market_timestamp'})
    try:
        MC.compare(DRAWS, 'receiving/receptions',
                   dict(QUOTE, sharp_money_pct=0.8))
        ok = False
    except MC.MarketLeak as e:
        ok = 'UNDECLARED_MARKET_FIELD' in str(e)
    check('an undeclared market field is REFUSED, not silently ignored', ok)
    src = open(os.path.join(_ROOT, 'nfl', 'product', 'market_cdf.py')).read()
    check('the comparator imports nothing from the model layer',
          'import model' not in src and 'run_forecast' not in src)


def test_h_an_empty_draw_set_is_an_error_not_a_probability():
    try:
        MC.empirical_cdf_at(np.array([]), 3.5, 'receiving/receptions')
        ok = False
    except ValueError as e:
        ok = 'EMPTY_DRAW_SET' in str(e)
    check('an empty draw set refuses rather than returning 0.0', ok)


def test_i_the_frozen_snapshot_is_read_and_never_rewritten():
    """The afternoon comparator is immutable by contract. Measure it."""
    import hashlib
    from nfl.tools import market_comparison as MCMP
    blob = pathlib.Path(_ROOT, 'nfl', 'vintage',
                        'hardrock_market_snapshot.3d9b22dc39e12e54.csv.gz')
    if not blob.exists():
        print('  ..   the frozen snapshot is not preserved here; skipped')
        return
    import gzip
    raw = gzip.open(blob, 'rb').read()
    check('the preserved snapshot hashes to its content-addressed name',
          hashlib.sha256(raw).hexdigest().startswith('3d9b22dc39e12e54'))
    tmp = pathlib.Path(_ROOT) / '.snapshot_readback.csv'
    try:
        tmp.write_bytes(raw)
        before = hashlib.sha256(tmp.read_bytes()).hexdigest()
        s1 = MCMP.load_frozen_snapshot(tmp)
        s2 = MCMP.load_frozen_snapshot(tmp)
        after = hashlib.sha256(tmp.read_bytes()).hexdigest()
        check('reading it twice changes not one byte', before == after)
        check('  and both reads agree on the digest',
              s1['sha256'] == s2['sha256'] == before)
        check('every row is a usable two-sided quote',
              s1['n_rows'] == s1['n_quotes'] == 166 and not s1['skipped'],
              f'{s1["n_rows"]} rows, {s1["n_quotes"]} quotes')
        stamps = {q['timestamp'] for q in s1['quotes'].values()}
        check('the retrieval clocks are carried through unchanged',
              len(stamps) == 19 and
              min(stamps) == '2026-09-13T18:11:57.608Z' and
              max(stamps) == '2026-09-13T18:13:12.712Z',
              f'{len(stamps)} distinct')
        lines = [q['line'] for q in s1['quotes'].values()]
        check('EVERY line is a half point, so no push is possible anywhere '
              'in this snapshot', not any(float(x).is_integer()
                                          for x in lines))
    finally:
        tmp.unlink(missing_ok=True)


def test_j_the_join_key_includes_the_club():
    """A name is not an identity. Measured on this very week.

    The Vikings' Justin Jefferson is a receiver; Cleveland listed a linebacker
    of the same name on their inactive report. A (player, market) key would
    have joined a receiving line onto whichever one it met first.
    """
    from nfl.tools import market_comparison as MCMP
    import hashlib
    tmp = pathlib.Path(_ROOT) / '.collide.csv'
    hdr = ','.join(MCMP.SNAPSHOT_COLUMNS)
    body = [
        "Justin Jefferson,MIN,GB,Receiving Yards,75.5,-115,-115,Book,"
        "2026-09-13T18:00:00Z,TWO_SIDED_OPEN,https://x.invalid",
        "Justin Jefferson,CLE,JAX,Receiving Yards,10.5,-115,-115,Book,"
        "2026-09-13T18:00:00Z,TWO_SIDED_OPEN,https://x.invalid",
    ]
    try:
        tmp.write_text(hdr + '\n' + '\n'.join(body) + '\n')
        s = MCMP.load_frozen_snapshot(tmp)
        check('two same-named players at different clubs are TWO quotes',
              s['n_quotes'] == 2, str(s['n_quotes']))
        check('  and each keeps its own line',
              s['quotes'][('Justin Jefferson', 'MIN', 'Receiving Yards')]
              ['line'] == 75.5 and
              s['quotes'][('Justin Jefferson', 'CLE', 'Receiving Yards')]
              ['line'] == 10.5)
        # a genuine duplicate is an ambiguity and is refused, not resolved
        tmp.write_text(hdr + '\n' + body[0] + '\n' + body[0] + '\n')
        try:
            MCMP.load_frozen_snapshot(tmp)
            ok = False
        except ValueError as e:
            ok = 'MARKET_SNAPSHOT_DUPLICATE' in str(e)
        check('a true duplicate quote is REFUSED, not silently deduplicated',
              ok)
    finally:
        tmp.unlink(missing_ok=True)


def test_k_market_names_are_declared_not_inferred():
    from nfl.product import market_names as MN
    m, basis = MN.metric_for('Passing Yards', 'QB')
    check('a quarterback passing-yards market maps', m == 'qb/pyds', str(m))
    m, basis = MN.metric_for('Rushing Yards', 'QB')
    check('a quarterback rushing-yards market maps', m == 'qb/ryds', str(m))
    m, basis = MN.metric_for('Rushing Yards', 'RB')
    check('a RUNNING BACK rushing-yards market does NOT map', m is None)
    check('  and says why, naming the gap',
          'NOT_MODELLED' in basis and 'Carries are not yards' in basis)
    m, basis = MN.metric_for('Rushing Attempts', 'RB')
    check('a running back rushing-attempts market maps to carries',
          m == 'rushing/carries')
    m, basis = MN.metric_for('Rushing Attempts', 'QB')
    check('a quarterback rushing-attempts market maps to rush_opp',
          m == 'qb/rush_opp')
    check('  and the definitional basis is stated, with its caveat',
          'scrambles + designed runs' in basis and 'kneel' in basis.lower())
    m, basis = MN.metric_for('Anytime Touchdown', 'WR')
    check('an undeclared market is REFUSED, not fuzzy-matched', m is None)
    check('  with a named reason',
          'MARKET_NOT_IN_DECLARED_MAPPING' in basis)
    check('the table is keyed by (market, is_quarterback), so one name can '
          'mean two metrics',
          MN.metric_for('Rushing Yards', 'QB')[0] !=
          MN.metric_for('Rushing Yards', 'RB')[0])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
