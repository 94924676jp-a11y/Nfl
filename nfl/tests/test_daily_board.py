"""The daily decision feed: a consumer that must not become a strategy.

WHAT THESE TESTS PROTECT.

  * THE ONE-WAY RULE. Prices enter the feed and stop. No column derived from
    a line, a price or a market probability may appear on the football side of
    a row, and nothing here may write into nfl/production.
  * VISIBILITY OF THE UNRANKABLE. A row that cannot be ranked stays in the
    artifact with a NAMED reason. Dropping it would make the slate look better
    covered than it is -- the same defect as an empty result read as success.
  * DISAGREEMENT IS NOT EDGE. model_minus_market_probability ships with a
    label saying so, and no tier is assigned in the engine.
  * CORRELATION. Two markets driven by one quantity carry one group id, so a
    decision layer cannot count one game script as two independent signals.
"""
from __future__ import annotations

import csv
import json
import os
import pathlib
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.product import daily_board as DB                            # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def test_a_devig_needs_both_sides():
    """A one-sided quote cannot be de-vigged, and is not pretended otherwise."""
    fo, fu, hold = DB.devig(DB.american_to_prob(-110),
                            DB.american_to_prob(-110))
    check('a two-sided -110/-110 market de-vigs to 0.5 / 0.5',
          abs(fo - 0.5) < 1e-9 and abs(fu - 0.5) < 1e-9, f'{fo} / {fu}')
    # -110 implies 0.5238 a side; the two sum to 1.0476, so the hold is
    # 0.0476. (An earlier version of this test asserted 0.0909, which is the
    # vig quoted a different way and not what `devig` returns.)
    check('  and the hold is reported, not absorbed',
          abs(hold - 0.0476) < 1e-3, f'{hold:.4f}')
    check('one-sided returns None rather than half a guessed margin',
          DB.devig(DB.american_to_prob(-110), None) == (None, None, None))
    check('  and a nonsense price is None, not zero',
          DB.american_to_prob('n/a') is None)


def test_b_correlation_groups_bind_one_driver():
    """Stafford under attempts and under yards are ONE signal, not two."""
    pid = '00-0026498'
    att = DB.correlation_group(pid, 'qb/att')
    yds = DB.correlation_group(pid, 'qb/pyds')
    rec = DB.correlation_group(pid, 'receiving/receptions')
    check('attempts and passing yards share one correlation group',
          att == yds, f'{att} vs {yds}')
    check('  and a different driver is a different group', att != rec)
    check('  and two players never share a group',
          DB.correlation_group('X', 'qb/att')
          != DB.correlation_group('Y', 'qb/att'))
    check('receptions and receiving yards are one target-volume group',
          DB.correlation_group(pid, 'receiving/receptions')
          == DB.correlation_group(pid, 'receiving/receiving_yards'))


def test_c_every_ineligibility_reason_is_named_and_the_row_survives():
    base = {'forecast_predates_kickoff': True, 'market_line': 1.5,
            'market_predates_kickoff': True, 'metric_status': 'MODELED',
            'official_inactive': False, 'identity_unresolved': False,
            'known_defect_flags': [], 'has_distribution': True}
    ok, why = DB.eligibility(dict(base))
    check('a complete row is rankable', ok and not why, str(why))
    for field, value, expect in (
            ('forecast_predates_kickoff', False, 'FORECAST_NOT_BEFORE_KICKOFF'),
            ('market_line', None, 'MARKET_QUOTE_ABSENT'),
            ('market_predates_kickoff', False,
             'MARKET_QUOTE_NOT_BEFORE_KICKOFF'),
            ('official_inactive', True, 'PLAYER_OFFICIALLY_INACTIVE'),
            ('identity_unresolved', True, 'IDENTITY_UNRESOLVED'),
            ('has_distribution', False, 'NO_DISTRIBUTION_ONLY_A_POINT_MEAN')):
        r = dict(base)
        r[field] = value
        ok, why = DB.eligibility(r)
        check(f'  {field}={value} -> ineligible, named {expect}',
              (not ok) and expect in why, str(why))
    r = dict(base)
    r['metric_status'] = 'ABSENT'
    ok, why = DB.eligibility(r)
    check('  an incomplete layer names the status it saw',
          (not ok) and any(w.startswith('LAYER_INCOMPLETE:') for w in why),
          str(why))
    r = dict(base)
    r['known_defect_flags'] = [{'id': 'X', 'contaminates_this_metric': True}]
    ok, why = DB.eligibility(r)
    check('  a defect that touches THIS metric blocks ranking',
          (not ok) and 'KNOWN_DEFECT:X' in why, str(why))
    r['known_defect_flags'] = [{'id': 'X', 'contaminates_this_metric': False}]
    ok, why = DB.eligibility(r)
    check('  a defect that does NOT touch it does not',
          ok, str(why))


def test_d_a_post_kickoff_board_never_leads_the_feed():
    rows = [{'written_at': '2026-09-11T01:00:00Z',
             'kickoff_utc': '2026-09-11T00:35:00Z', 'run_id': 'late'},
            {'written_at': '2026-09-10T20:00:00Z',
             'kickoff_utc': '2026-09-11T00:35:00Z', 'run_id': 'early'},
            {'written_at': '2026-09-11T00:25:00Z',
             'kickoff_utc': '2026-09-11T00:35:00Z', 'run_id': 'latest_lawful'}]
    pick, why = latest = DB.latest_lawful(rows)
    check('the newest LAWFUL board is chosen, not the newest board',
          pick['run_id'] == 'latest_lawful', str(pick))
    only_late = [rows[0]]
    pick2, why2 = DB.latest_lawful(only_late)
    check('a game with only post-kickoff boards is refused, not fudged',
          pick2 is None and 'NO_LAWFUL_BOARD' in why2, str(why2))


def test_e_the_market_columns_never_reach_the_football_columns():
    """The one-way rule, asserted on a real row rather than asserted in prose.

    A market quote is attached AFTER the football fields are built, and the
    football fields must be byte-identical before and after that join.
    """
    vec = np.array([10.0] * 500 + [20.0] * 500)
    row = {'model_mean': 15.0, 'p50': 15.0, 'metric': 'rushing/carries'}
    before = dict(row)
    market = {('Somebody', 'Carries'): [
        {'line': 12.5, 'over_price': -110, 'under_price': -110,
         'sportsbook': 'BookA', 'timestamp': '2026-09-10T20:00:00Z',
         'snapshot': 'capture1'}]}
    DB._attach_market(row, market, 'Somebody', 'rushing/carries', vec,
                      '2026-09-11T00:35:00Z')
    check('the join found the quote', row['market_line'] == 12.5)
    check('  and P(over) came from the draws, not from the price',
          row['model_probability_over_market_line'] == 0.5,
          str(row['model_probability_over_market_line']))
    check('  while every football field is untouched by it',
          all(row[k] == v for k, v in before.items()),
          str({k: (v, row[k]) for k, v in before.items() if row[k] != v}))
    check('  the disagreement carries its label',
          row['model_minus_market_label'] == DB.DISAGREEMENT_LABEL)
    check('  and a no-vig -110/-110 market makes it 0.5 - 0.5 = 0',
          abs(row['model_minus_market_probability']) < 1e-9,
          str(row['model_minus_market_probability']))


def test_f_a_one_sided_market_is_marked_not_devigged():
    vec = np.arange(1000, dtype=float)
    row = {}
    market = {('P', 'Carries'): [
        {'line': 500, 'over_price': -110, 'under_price': None,
         'sportsbook': 'B', 'timestamp': '2026-09-10T20:00:00Z',
         'snapshot': 'c1'}]}
    DB._attach_market(row, market, 'P', 'rushing/carries', vec,
                      '2026-09-11T00:35:00Z')
    check('a one-sided quote still yields a model probability',
          row['model_probability_over_market_line'] is not None)
    check('  but no_vig_available is false',
          row['no_vig_available'] is False)
    check('  and the disagreement is withheld rather than guessed',
          row['model_minus_market_probability'] is None)


def test_g_the_engine_assigns_no_tier():
    """The directive forbids A/B/C tiers in the engine. Prove none exists."""
    # ASSERT ON THE OUTPUT, NOT ON THE SOURCE TEXT. An earlier version of
    # this grepped the module for "tier" and failed on the sentence that says
    # no tiers are assigned -- catching the disclaimer instead of the thing.
    # What matters is that no emitted column grades a row.
    # 'rank' is NOT banned: RANKING_ELIGIBLE and its reasons are the
    # deterministic eligibility gate the directive requires. What is banned is
    # a SUBJECTIVE grade -- a tier, a letter, a star rating -- which is the
    # decision layer's to assign, not the engine's.
    banned = ('tier', 'grade', 'rating', 'stars', 'letter', 'score')
    allowed = {'RANKING_ELIGIBLE', 'ranking_ineligible_reasons'}
    for col in sorted(set(DB._CSV_COLS + DB._MARKET_COLS)):
        if col in allowed:
            continue
        low = col.lower()
        check(f'  emitted column {col!r} assigns no subjective grade',
              not any(b in low for b in banned), col)
    check('the eligibility gate itself is present and boolean-shaped',
          'RANKING_ELIGIBLE' in DB._CSV_COLS
          and 'ranking_ineligible_reasons' in DB._CSV_COLS)
    check('the primitives a ranking needs ARE exposed',
          all(c in DB._CSV_COLS for c in
              ('abs_probability_disagreement',
               'line_minus_mean_native_units',
               'line_minus_mean_in_model_sds',
               'line_percentile_in_model_distribution',
               'correlation_group', 'known_defect_flags',
               'source_freshness', 'candidate_version')))


def test_h_an_absent_market_still_produces_a_board():
    o = DB.load_market('/nonexistent/nope.csv')
    check('an absent snapshot BLOCKS with a named code rather than raising',
          o.state is State.BLOCKED and o.code == 'MARKET_SNAPSHOT_ABSENT',
          f'{o.state.name}[{o.code}]')
    with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False) as fh:
        fh.write('player,market,line\n')
        empty = fh.name
    o2 = DB.load_market(empty)
    check('an EMPTY snapshot is an error, not an absence of quotes',
          o2.state is State.FAIL and o2.code == 'MARKET_SNAPSHOT_EMPTY',
          f'{o2.state.name}[{o2.code}]')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
