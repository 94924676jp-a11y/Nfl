"""End to end for ONE market: qb/pyds from official inactives to a ranked row.

WHAT THIS PROVES, AND WHAT IT DOES NOT

It walks the whole governed chain for quarterback passing yards --

    official inactives -> eligible QB room -> qb allocation ->
    dropback distribution -> passing-yards draws ->
    qb_inactive_ownership_enforced -> no contaminating QB defect ->
    exact empirical market CDF -> ranking eligible

-- on REAL sealed draws and the REAL frozen Hard Rock line, with the ownership
verdict produced by the REAL writer rather than set by hand. It proves the
CODE PATH reaches eligibility.

It does NOT claim any afternoon game satisfies it today. At the time of
writing no 4:25 official inactive list had published, so the live boards carry
`enforced == False` and every passing-yards row is correctly refused. The
positive case below supplies a complete provenance to the governed writer; the
negative cases supply a broken one. Neither hand-sets the flag, and there is
no code path that could.
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
_Q3 = os.path.join(_ROOT, 'nfl', 'research', 'qb3')
if _Q3 not in sys.path:
    sys.path.insert(0, _Q3)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production.nonqb import qb_allocation as QA                 # noqa: E402
from nfl.product import daily_board as PBD                           # noqa: E402
from nfl.product import market_cdf as MC                             # noqa: E402
from nfl.product import market_names as MN                           # noqa: E402
from nfl.research import board_select as BS                          # noqa: E402

PASSED = FAILED = 0
METRIC = 'qb/pyds'
SNAPSHOT = pathlib.Path(_ROOT, 'nfl', 'vintage',
                        'hardrock_market_snapshot.3d9b22dc39e12e54.csv.gz')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


ROOM = [{'gsis_id': 'QB1', 'team': 'ZZ', 'position': 'QB'},
        {'gsis_id': 'QB2', 'team': 'ZZ', 'position': 'QB'},
        {'gsis_id': 'QB3', 'team': 'ZZ', 'position': 'QB'}]
COMPLETE_PROV = {'game_id': '2026_01_YY_ZZ', 'teams': ['ZZ'],
                 'post_inactives_complete': True, 'n_unmapped': 0}


def _real_pyds_draws():
    """Real stored qb/pyds draws and the real frozen line for that passer."""
    import csv
    import gzip
    from nfl.product import names as NM
    d = pathlib.Path(_ROOT, 'nfl', 'research', 'live',
                     '2026_01_ARI_LAC', 'pre_inactives_V1_CANDIDATE_R8')
    if not d.exists() or not SNAPSHOT.exists():
        return None
    bd, _ = BS.newest_board_dir(d)
    if bd is None:
        return None
    board = json.load(open(bd / 'board.json'))
    draws = PBD._load_draws(bd)
    if draws is None or 'qb__pyds' not in draws.files:
        return None
    quotes = {}
    for r in csv.DictReader(gzip.open(SNAPSHOT, 'rt')):
        quotes[(r['player'], r['team'], r['market'])] = r
    names = NM.lookup(None)
    for i, p in enumerate(board.get('players') or []):
        if p.get('position') != 'QB':
            continue
        nm = names.get(p.get('gsis_id'), p.get('gsis_id'))
        q = quotes.get((nm, p.get('team'), 'Passing Yards'))
        if q:
            arr = draws['qb__pyds']
            return {'player': nm, 'board': board,
                    'draws': arr[i] if arr.ndim == 2 else arr, 'quote': q}
    return None


def test_a_the_market_name_resolves_to_the_modelled_metric():
    m, basis = MN.metric_for('Passing Yards', 'QB')
    check('the book\'s "Passing Yards" is qb/pyds', m == METRIC, str(m))
    check('  by a declared basis, not a similar string',
          'same quantity' in basis)


def test_b_the_chain_reaches_ranking_eligible_for_qb_pyds():
    """The POSITIVE case, link by link, with nothing hand-set."""
    # 1-3. official inactives -> eligible room -> allocation
    o = QA.allocate(2026, 1, ['ZZ'], ROOM, m=400, seed=20260908,
                    inactive_ids=['QB3'], inactive_provenance=COMPLETE_PROV)
    check('1. the allocation consumes a complete official inactive set',
          o.state is State.PASS, o.code)
    own = o.evidence['qb_inactive_ownership']
    check('2. the eligible QB room excluded the inactive quarterback',
          own['inactive_qbs_excluded'].get('ZZ') == ['QB3'])
    S = o.value['ZZ']['shares']
    pids = o.value['ZZ']['pids']
    check('3. the inactive quarterback holds zero share in EVERY draw',
          float(S[pids.index('QB3')].max()) == 0.0)
    check('   and the dropback shares still close to 1 in every draw',
          float(np.abs(S.sum(0) - 1.0).max()) <= 1e-9)
    # 4. ownership enforced, by the governed writer
    check('4. qb_inactive_ownership_enforced is TRUE',
          own['enforced'] is True, str(own['failed_conditions']))
    check('   and all six conditions are recorded as holding',
          all(own['conditions'][k] for k in QA.OWNERSHIP_CONDITIONS))
    # 5. passing-yards draws present, from the real sealed board
    real = _real_pyds_draws()
    if real is None:
        print('  ..   no real board or frozen snapshot here; chain stops at 4')
        return
    d = np.asarray(real['draws'], float)
    check('5. real stored passing-yards draws are present',
          d.size > 0 and np.isfinite(d).all(), f'{d.size} draws')
    # 6. no contaminating defect, once ownership is enforced
    board = dict(real['board'], qb_inactive_ownership_enforced=own['enforced'],
                 qb_inactive_ownership=own)
    flags = PBD._defect_flags(board, METRIC)
    bad = [f['id'] for f in flags if f.get('contaminates_this_metric')]
    check('6. no defect contaminates qb/pyds once ownership is enforced',
          not bad, str(bad))
    check('   and the historical sentinel is specifically gone',
          not any(f['id'] == 'QB_INACTIVE_NOT_CONSUMED' for f in flags))
    # 7. exact empirical CDF at the REAL frozen line
    q = real['quote']
    c = MC.compare(d, METRIC, {
        'line': float(q['line']), 'over_price': q['over_price'],
        'under_price': q['under_price'],
        'retrieved_at': q['retrieval_time_utc'],
        'source': q['sportsbook'],
        'market_timestamp': q['retrieval_time_utc']})
    e = c['exact_probability']
    check('7. the probability is COUNTED from the draws',
          e['method'] == 'EMPIRICAL_COUNT_OVER_STORED_DRAWS')
    check('   over + under + on-the-line is exactly 1',
          e['p_over'] + e['p_under'] + e['p_model_equals_line'] == 1.0)
    check('   the counts reconcile to the draw total',
          e['n_over'] + e['n_under'] + e['n_model_equals_line']
          == e['n_draws'])
    check('   the de-vigged market pair sums to exactly 1',
          c['no_vig']['no_vig_over'] + c['no_vig']['no_vig_under'] == 1.0)
    check('   the model draws were not touched',
          c['model_draws_sha256'] == c['model_draws_sha256_after'])
    # 8. ranking eligible
    check('8. the row is RANKING ELIGIBLE',
          bool(own['enforced'] and not bad))
    print(f"       [{real['player']} line {q['line']} "
          f"P(Over)={e['p_over']:.3f} P(Under)={e['p_under']:.3f}]")


def test_c_the_negative_cases_keep_qb_pyds_refused():
    """Every way the chain can fail must leave the row refused."""
    cases = [
        ('no inactive evidence at all', {}, None),
        ('incomplete provenance: no game or clubs',
         {'inactive_ids': ['QB3']}, None),
        ('the club\'s list is not POST_INACTIVES_COMPLETE',
         {'inactive_ids': ['QB3']},
         dict(COMPLETE_PROV, post_inactives_complete=False,
              game_id=None, teams=None)),
        ('an unresolved identity that IS a quarterback',
         {'inactive_ids': ['QB3']},
         dict(COMPLETE_PROV, n_unmapped=1, unmapped=['ZZ:Some Passer'],
              unmapped_detail=[{'team': 'ZZ', 'name': 'Some Passer',
                                'source_position': 'QB'}])),
        ('an unresolved identity of UNKNOWN position',
         {'inactive_ids': ['QB3']},
         dict(COMPLETE_PROV, n_unmapped=1, unmapped=['ZZ:Someone'],
              unmapped_detail=[{'team': 'ZZ', 'name': 'Someone',
                                'source_position': None}])),
    ]
    for label, kw, prov in cases:
        o = QA.allocate(2026, 1, ['ZZ'], ROOM, m=200, seed=20260908,
                        inactive_provenance=prov, **kw)
        own = o.evidence['qb_inactive_ownership']
        check(f'{label} -> ownership NOT enforced',
              own['enforced'] is False, str(own['failed_conditions']))
        flags = PBD._defect_flags(
            {'component_manifest': {'applied': ['R2']},
             'qb_inactive_ownership_enforced': own['enforced']}, METRIC)
        bad = [f['id'] for f in flags if f.get('contaminates_this_metric')]
        check('   qb/pyds still carries the contaminating defect',
              'QB_INACTIVE_NOT_CONSUMED' in bad, str(bad))
        check('   so the row is NOT ranking eligible',
              not (own['enforced'] and not bad))


def test_d_todays_live_boards_are_refused_and_that_is_correct():
    """Measured, so the report and the code cannot drift apart."""
    seen = 0
    for gid in ('2026_01_ARI_LAC', '2026_01_GB_MIN', '2026_01_MIA_LV',
                '2026_01_WAS_PHI'):
        d = pathlib.Path(_ROOT, 'nfl', 'research', 'live', gid,
                         'pre_inactives_V1_CANDIDATE_R8')
        if not d.exists():
            continue
        bd, _ = BS.newest_board_dir(d)
        if bd is None:
            continue
        b = json.load(open(bd / 'board.json'))
        seen += 1
        check(f'{gid[8:]}: a pre-inactives board does not claim ownership',
              b.get('qb_inactive_ownership_enforced') is not True,
              str(b.get('qb_inactive_ownership_enforced')))
        bad = [f['id'] for f in PBD._defect_flags(b, METRIC)
               if f.get('contaminates_this_metric')]
        check('   and qb/pyds is therefore refused',
              'QB_INACTIVE_NOT_CONSUMED' in bad, str(bad))
    check('all four afternoon boards were examined', seen == 4, str(seen))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
