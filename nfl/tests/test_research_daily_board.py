"""The research slate export: a second board that must stay a second board.

WHAT THESE TESTS PROTECT.

  * THE SEPARATION. production = promoted model only, research = sealed
    candidates only. The research export writes under nfl/research/ and a
    destination inside nfl/product is refused BEFORE a byte is written.
  * PROMOTED STAYS FALSE. Not read from anywhere, not inferrable, not
    settable by a flag.
  * ONE SCHEMA, TWO BOARDS. The research columns are the product columns plus
    research identity. If the product board grows a column and this does not,
    the test fails rather than the two drifting apart quietly.
  * VOCABULARY. Nothing is a bet, an edge or an EV -- not in the module, not
    in a column name, not in an emitted value.
  * SAME-CUTOFF COMPARISON. A pre-inactives candidate and a post-inactives
    candidate differ by the official inactive list as well as by
    architecture, so the cutoff is part of the comparison key.
  * THE REDUCED SET IS NOT A TIER LIST. Four deterministic gates, no
    threshold, no ordering, no score.
"""
from __future__ import annotations

import csv
import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.product import daily_board as PB                            # noqa: E402
from nfl.research import daily_board as RB                           # noqa: E402

PASSED = FAILED = 0
DATE = '2026-09-11'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def test_a_it_refuses_to_write_into_the_production_namespace():
    bad = pathlib.Path(_ROOT) / 'nfl' / 'product' / 'daily' / 'sneaky'
    o = RB.assert_never_writes_into_product(bad)
    check('a destination inside nfl/product is REFUSED',
          o.state is State.FAIL and o.code == 'RESEARCH_WRITE_INTO_PRODUCT',
          f'{o.state.name}[{o.code}]')
    check('  and the product directory itself is refused too',
          RB.assert_never_writes_into_product(
              pathlib.Path(_ROOT) / 'nfl' / 'product').state is State.FAIL)
    ok = RB.assert_never_writes_into_product(
        pathlib.Path(_ROOT) / 'nfl' / 'research' / 'daily' / DATE)
    check('  while the research tree is allowed', ok.state is State.PASS)
    o2 = RB.build(DATE, candidate='R8', out_dir=str(bad))
    check('  and build() refuses BEFORE creating anything',
          o2.state is State.FAIL and o2.code == 'RESEARCH_WRITE_INTO_PRODUCT',
          f'{o2.state.name}[{o2.code}]')
    check('  leaving no directory behind', not bad.exists())


def test_b_labels_parse_into_cutoff_and_candidate():
    for name, want in (
            ('post_inactives_V1_CANDIDATE_R8', ('post_inactives', 'R8')),
            ('pre_inactives_V1_CANDIDATE', ('pre_inactives', 'V1')),
            ('post_inactives_V1_CANDIDATE_R5', ('post_inactives', 'R5'))):
        check(f'  {name} -> {want}', RB.parse_label(name) == want,
              str(RB.parse_label(name)))
    check('  an unrelated directory is not a board',
          RB.parse_label('BOARD_STATE.json') == (None, None))


def test_c_an_unknown_candidate_refuses_rather_than_emitting_nothing():
    o = RB.build(DATE, candidate='R99',
                 out_dir=tempfile.mkdtemp(prefix='rb-'))
    check('an unsealed candidate is a named refusal, not an empty file',
          o.state is State.FAIL and o.code == 'RESEARCH_UNKNOWN_CANDIDATE',
          f'{o.state.name}[{o.code}]')
    o2 = RB.build('1999-01-01', candidate='R8',
                  out_dir=tempfile.mkdtemp(prefix='rb-'))
    check('a date with no sealed board BLOCKS and does not run a forecast',
          o2.state is State.BLOCKED
          and o2.code == 'RESEARCH_NO_SEALED_BOARDS',
          f'{o2.state.name}[{o2.code}]')


def _build(**kw):
    d = tempfile.mkdtemp(prefix='rb-')
    o = RB.build(DATE, out_dir=d, **kw)
    return o, pathlib.Path(d)


def test_d_every_row_carries_its_candidate_and_promoted_stays_false():
    o, d = _build(candidate='all', cutoff='post_inactives')
    if o.state is not State.PASS:
        print(f'  ..   no sealed boards for {DATE}; skipped ({o.code})')
        return
    rows = list(csv.DictReader(open(d / 'RESEARCH_DAILY_BOARD.csv')))
    check('the export produced rows', rows, str(len(rows)))
    check('  every row names its candidate',
          all(r['candidate'] in RB.CANDIDATES for r in rows),
          str(sorted({r['candidate'] for r in rows})))
    check('  every row names its cutoff',
          all(r['cutoff'] == 'post_inactives' for r in rows))
    check('  every row is marked research, not production',
          all(r['namespace'] == 'research' for r in rows))
    check('  and promoted is False on every single row',
          all(str(r['promoted']).lower() in ('false', '0') for r in rows),
          str(sorted({r['promoted'] for r in rows})))
    doc = json.load(open(d / 'RESEARCH_DAILY_BOARD.json'))
    check('  the artifact itself says promoted false',
          doc['promoted'] is False)
    check('  and declares the research namespace',
          doc['namespace'] == 'research')


def test_e_the_schema_matches_the_product_board():
    """One schema, two boards. Drift fails here rather than downstream."""
    missing = [c for c in PB._CSV_COLS if c not in RB.RESEARCH_COLS]
    check('the research board carries EVERY product column',
          not missing, str(missing))
    for extra in ('candidate', 'cutoff', 'research_label', 'namespace'):
        check(f'  plus the research identity column {extra!r}',
              extra in RB.RESEARCH_COLS)
    for prim in ('correlation_group', 'RANKING_ELIGIBLE',
                 'ranking_ineligible_reasons',
                 'abs_probability_disagreement',
                 'line_minus_mean_in_model_sds'):
        check(f'  and the shared primitive {prim!r} survives',
              prim in RB.RESEARCH_COLS)


def test_f_nothing_is_called_a_bet_an_edge_or_an_ev():
    # ASSERT ON WHAT IS EMITTED, NOT ON THE SOURCE PROSE.
    #
    # A source grep for 'expected value' fails on the sentence "No row here is
    # a bet, an edge or an expected value" -- catching the DISCLAIMER instead
    # of the thing it disclaims. That is the same mistake the product board's
    # tier test made, so this checks the artifact: no column name and no
    # emitted value uses the vocabulary, and the disclaimer must be PRESENT.
    o, d = _build(candidate='R8')
    if o.state is State.PASS:
        doc = json.load(open(d / 'RESEARCH_DAILY_BOARD.json'))
        check('the artifact states plainly that nothing here is a bet or EV',
              'not a bet' in doc['what_this_is_not'].lower()
              or 'bet, an edge' in doc['what_this_is_not'].lower(),
              doc['what_this_is_not'][:60])
        disclaimers = {'what_this_is_not', 'separation'}
        rows = list(csv.DictReader(open(d / 'RESEARCH_DAILY_BOARD.csv')))
        dirty = [(r['player'], k, v) for r in rows for k, v in r.items()
                 if k not in disclaimers and isinstance(v, str)
                 and any(w in v.lower()
                         for w in ('wager', 'bettor', 'expected value'))]
        check('  and no EMITTED VALUE anywhere uses that vocabulary',
              not dirty, str(dirty[:2]))
    for col in RB.RESEARCH_COLS + RB.COMPARISON_COLS + RB.PRIORITY_COLS:
        c = col.lower()
        check(f'  column {col!r} is not bet/edge/EV language',
              not any(w in c for w in ('bet', 'edge', '_ev', 'ev_', 'wager')),
              col)
    check('the disagreement carries its non-EV label',
          'NOT PROVEN EV' in PB.DISAGREEMENT_LABEL, PB.DISAGREEMENT_LABEL)


def test_g_the_comparison_is_same_cutoff_and_actuals_only_when_known():
    o, d = _build(candidate='all')
    if o.state is not State.PASS:
        print(f'  ..   no sealed boards for {DATE}; skipped ({o.code})')
        return
    rows = list(csv.DictReader(open(d / 'RESEARCH_CANDIDATE_COMPARISON.csv')))
    check('the comparison produced rows', rows, str(len(rows)))
    check('  every row declares which cutoff it compares within',
          all(r['cutoff'] in ('pre_inactives', 'post_inactives')
              for r in rows))
    keys = [(r['game_id'], r['cutoff'], r['player'], r['metric'])
            for r in rows]
    check('  and one row per (game, cutoff, player, metric) -- cutoffs are '
          'never merged',
          len(keys) == len(set(keys)), f'{len(keys)} rows, {len(set(keys))} keys')
    check('  the candidate columns are exactly V1..R8',
          all(c in rows[0] for c in RB.CANDIDATES))
    filled = [r for r in rows if r['actual_if_known']]
    for r in filled:
        check(f"  a populated actual names its source ({r['player'][:14]})",
              bool(r['actual_source']), str(r['actual_source']))
        break
    blank = [r for r in rows if not r['actual_if_known']]
    check('  an unknown actual is BLANK, never zero',
          all(r['actual_if_known'] == '' for r in blank),
          str(len(blank)))
    check('  and an unknown actual carries no source either',
          all(not r['actual_source'] for r in blank))


def test_h_the_reduced_set_applies_gates_and_no_threshold():
    base = {'RANKING_ELIGIBLE': True, 'has_distribution': True,
            'known_defect_flags': [], 'source_freshness': 5.0,
            'abs_probability_disagreement': 0.001}
    keep, dropped = RB.priority_rows([dict(base)])
    check('a row passing every gate is kept',
          len(keep) == 1 and not dropped, str(dropped))
    check('  even with a TINY disagreement -- no minimum is imposed',
          keep[0]['abs_probability_disagreement'] == 0.001)
    for field, value, reason in (
            ('RANKING_ELIGIBLE', False, 'not_ranking_eligible'),
            ('has_distribution', False, 'no_distribution')):
        r = dict(base)
        r[field] = value
        k, dr = RB.priority_rows([r])
        check(f'  {field}={value} excluded as {reason}',
              not k and dr.get(reason) == 1, str(dr))
    r = dict(base)
    r['known_defect_flags'] = [{'id': 'X', 'contaminates_this_metric': True}]
    k, dr = RB.priority_rows([r])
    check('  a defect touching THIS metric excludes the row',
          not k and dr.get('known_defect_contaminates_metric') == 1, str(dr))
    r['known_defect_flags'] = [{'id': 'X', 'contaminates_this_metric': False}]
    k, _ = RB.priority_rows([r])
    check('  a defect elsewhere does not', len(k) == 1)
    r = dict(base)
    r['source_freshness'] = 40.0
    k, _ = RB.priority_rows([r])
    check('  with NO declared bound, age drops nothing', len(k) == 1)
    k, dr = RB.priority_rows([r], max_input_age_hours=12)
    check('  with a caller-declared bound it is applied and named',
          not k and dr.get('inputs_older_than_declared_bound') == 1, str(dr))
    check('  and the reduced set imposes no ordering',
          RB.priority_rows([dict(base), dict(base)])[0] ==
          [dict(base), dict(base)])


def test_i_it_reads_sealed_artifacts_and_runs_nothing():
    """No training, no forecasting, no parameter touched."""
    src = pathlib.Path(_ROOT, 'nfl', 'research', 'daily_board.py').read_text()
    for banned in ('run_forecast', 'fit(', 'train(', 'apply_r2_level',
                   'qb_slate'):
        check(f'  the module never calls {banned!r}', banned not in src)
    found = RB.discover(DATE)
    if not found:
        print('  ..   no sealed boards; skipped')
        return
    check('discovery returns sealed boards keyed by (game, cutoff, candidate)',
          all(len(k) == 3 for k in found), str(list(found)[:2]))
    check('  and each carries a board read from disk',
          all(v['board'].get('game_id') for v in found.values()))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
