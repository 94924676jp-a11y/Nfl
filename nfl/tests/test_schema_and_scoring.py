"""Tests for the canonical draw schema and the deterministic scoring engine.

THE STRUCTURAL CLAIM UNDER TEST: fantasy scoring is computed FROM football, and
football never depends on scoring. That is asserted here as a refusal, not
stated as an intention.
"""
import os, pathlib, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.schema import player_draw as PD                          # noqa: E402
from nfl.scoring import engine as SC                              # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing         # noqa: E402

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1; print(f'  ok   {label}')
    else:
        FAILED += 1; print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


def trace(**kw):
    t = {'execution_id': 'e1', 'model_arm': 'A', 'spec_hash': 'a' * 8,
         'code_commit': 'c' * 8, 'input_capture_hashes': ['h1'],
         'written_at': '2026-09-08T00:00:00+00:00', 'game_id': 'g1',
         'player_id': 'p1', 'seed': 1, 'schema_version': PD.SCHEMA_VERSION}
    t.update(kw)
    return t


def wr(n=5, **over):
    s = {'appeared': np.ones(n), 'pass_snaps': np.full(n, 30.0),
         'targets': np.array([5, 6, 4, 7, 5], float),
         'receptions': np.array([3, 4, 2, 5, 3], float),
         'rec_yards': np.array([40, 55, 12, 88, 31], float),
         'rec_td': np.array([0, 1, 0, 1, 0], float)}
    s.update(over)
    return PD.DrawSet('p1', 'WR', 'g1', n, s, trace())


def test_a_schema_accepts_a_complete_draw():
    print('\nA. a complete, traceable, coherent draw set')
    o = PD.validate(wr())
    check('a well-formed WR draw set validates', o.state is State.PASS, o.code)
    check('  and reports its fields and trace', 'trace' in o.value)


def test_b_schema_refuses_incompleteness():
    print('\nB. partial and untraceable draws are refused')
    d = wr(); s = dict(d.stats); s.pop('receptions')
    o = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s, trace()))
    check('a missing field FAILS rather than defaulting to zero',
          o.state is State.FAIL and o.code == 'DRAW_FIELDS_MISSING', o.code)
    for f in ('spec_hash', 'input_capture_hashes', 'written_at', 'seed'):
        t = trace(); t[f] = None
        o = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, wr().stats, t))
        check(f'  a draw missing {f} is not evidence and is refused',
              o.state is State.FAIL and o.code == 'DRAW_TRACE_INCOMPLETE', o.code)
    o = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, wr().stats, trace(model_arm='Z')))
    check('an unlabelled/unknown model arm is refused -- arms may never pool',
          o.state is State.FAIL and o.code == 'UNKNOWN_MODEL_ARM', o.code)
    o = PD.validate(PD.DrawSet('p1', 'K', 'g1', 5, wr().stats, trace()))
    check('an undeclared position is BLOCKED, not silently accepted',
          o.state is State.BLOCKED, o.code)


def test_c_orderings_are_checked_per_draw_not_on_the_mean():
    print('\nC. impossible draws are caught per draw index')
    s = dict(wr().stats)
    s['receptions'] = np.array([3, 9, 2, 5, 3], float)   # 9 > 6 targets
    o = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s, trace()))
    check('receptions exceeding targets on ONE draw FAILS',
          o.state is State.FAIL and o.code == 'DRAW_ORDERING_VIOLATED', o.code)
    # the case a mean-level check would miss
    s2 = dict(wr().stats)
    s2['receptions'] = np.array([7, 1, 2, 5, 3], float)  # 7>5 on draw 0
    m_ok = s2['receptions'].mean() <= s2['targets'].mean()
    check('  the MEAN would pass this set', bool(m_ok))
    o2 = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s2, trace()))
    check('  but the per-draw check catches it, which is the point',
          o2.state is State.FAIL, o2.code)
    s3 = dict(wr().stats); s3['targets'] = np.array([5, 6, -1, 7, 5], float)
    o3 = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s3, trace()))
    check('a negative count is refused', o3.state is State.FAIL
          and o3.code == 'NEGATIVE_COUNT', o3.code)
    s4 = dict(wr().stats); s4['rec_yards'] = np.array([-9, 55, 12, 88, 31], float)
    o4 = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s4, trace()))
    check('  but NEGATIVE YARDAGE is legal and is not refused',
          o4.state is State.PASS, o4.code)


def test_d_fantasy_may_not_enter_the_football_schema():
    print('\nD. the structural separation')
    s = dict(wr().stats); s['fantasy_points'] = np.zeros(5)
    o = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s, trace()))
    check('a fantasy score stored in the football schema is REFUSED',
          o.state is State.FAIL and o.code == 'FANTASY_IN_FOOTBALL_SCHEMA', o.code)
    src = pathlib.Path(PD.__file__).read_text()
    check('  and the schema module does not import the scoring engine',
          'nfl.scoring' not in src and 'from nfl import scoring' not in src)
    for m in ('nfl/research/rc1/rc1_sim.py', 'nfl/research/rc1/rc1_lib.py',
              'nfl/research/td1/run_td1.py'):
        t = pathlib.Path(__file__).parents[2].joinpath(m)
        if t.exists():
            check(f'  and {m} does not import scoring',
                  'nfl.scoring' not in t.read_text())


def test_e_scoring_is_exact_against_hand_calculation():
    print('\nE. hand-calculated fixtures')
    cases = [
        ({'receptions': 8, 'rec_yards': 100, 'rec_td': 1},
         SC.DRAFTKINGS_STYLE, 8 * 1.0 + 100 * 0.1 + 6 + 3),
        ({'receptions': 8, 'rec_yards': 100, 'rec_td': 1},
         SC.FANDUEL_STYLE, 8 * 0.5 + 100 * 0.1 + 6),
        ({'receptions': 8, 'rec_yards': 100, 'rec_td': 1},
         SC.STANDARD_NON_PPR, 100 * 0.1 + 6),
        ({'pass_yards': 300, 'pass_td': 3, 'interceptions': 1},
         SC.DRAFTKINGS_STYLE, 300 * 0.04 + 12 - 1 + 3),
        ({'pass_yards': 299, 'pass_td': 3, 'interceptions': 1},
         SC.DRAFTKINGS_STYLE, 299 * 0.04 + 12 - 1),
        ({'rush_yards': 99, 'rush_td': 2}, SC.DRAFTKINGS_STYLE, 9.9 + 12),
        ({'rush_yards': 100, 'rush_td': 2}, SC.DRAFTKINGS_STYLE, 10 + 12 + 3),
    ]
    for stats, prof, want in cases:
        got = SC.score_line(stats, prof).value
        check(f'{prof.name}: {stats} -> {want}', abs(got - want) < 1e-9,
              f'got {got}')


def test_f_edge_cases():
    print('\nF. zero lines, negatives, fractions, multi-TD')
    check('an all-zero line scores exactly 0',
          SC.score_line({}, SC.DRAFTKINGS_STYLE).value == 0.0)
    o = SC.score_line({'interceptions': 3, 'fumbles_lost': 2},
                      SC.STANDARD_NON_PPR)
    check(f'negative scoring works: 3 INT + 2 FL = {o.value} (hand -10.0)',
          abs(o.value - (-10.0)) < 1e-9, o.value)
    o = SC.score_line({'rec_yards': 37}, SC.DRAFTKINGS_STYLE)
    check(f'fractional points are exact: 37 yds -> {o.value} (hand 3.7)',
          abs(o.value - 3.7) < 1e-9, o.value)
    o = SC.score_line({'rec_td': 4, 'rush_td': 1}, SC.DRAFTKINGS_STYLE)
    check(f'multi-TD: 4 rec + 1 rush TD -> {o.value} (hand 30.0)',
          abs(o.value - 30.0) < 1e-9, o.value)
    o = SC.score_line({'rush_yards': -7}, SC.DRAFTKINGS_STYLE)
    check(f'negative yardage: -7 -> {o.value} (hand -0.7)',
          abs(o.value - (-0.7)) < 1e-9, o.value)


def test_g_profile_isolation_and_config_not_code():
    print('\nG. profiles are configuration and are isolated')
    stats = {'receptions': 10, 'rec_yards': 120, 'rec_td': 2}
    vals = {p: SC.score_line(stats, SC.PROFILES[p]).value for p in SC.PROFILES}
    check(f'the three profiles disagree, so none is hard-coded: {vals}',
          len(set(vals.values())) == 3, vals)
    import dataclasses as dc
    custom = dc.replace(SC.DRAFTKINGS_STYLE, name='custom', version='1',
                        per_reception=2.0)
    check('a new profile is a config value, not a code change',
          abs(SC.score_line({'receptions': 3}, custom).value - 6.0) < 1e-9)
    check('  and it does not mutate the shipped profile',
          SC.DRAFTKINGS_STYLE.per_reception == 1.0)
    o = SC.score_draws({'receptions': np.array([1, 2]),
                        'rec_yards': np.array([10, 20])}, SC.DRAFTKINGS_STYLE)
    check('draw scoring preserves the draw index',
          o.state is State.PASS and list(np.round(o.value, 6)) == [2.0, 4.0],
          o.value if o.state is State.PASS else o.code)
    o2 = SC.score_draws({'receptions': np.array([1, 2]),
                         'rec_yards': np.array([10])}, SC.DRAFTKINGS_STYLE)
    check('  and a ragged draw set is refused, never zip-truncated',
          o2.state is State.FAIL and o2.code == 'DRAW_LENGTH_MISMATCH', o2.code)


def test_h_guard_deletions():
    print('\nH. guard-deletion proofs')

    def run_bad_order():
        s = dict(wr().stats)
        s['receptions'] = np.array([9, 9, 9, 9, 9], float)
        return PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s, trace()))
    assert_guard_is_load_bearing(
        run=run_bad_order, module_path='nfl.schema.player_draw', attr='validate',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value={}))
    check('H1 player_draw.validate is load-bearing -- bypassed, 9 receptions '
          'on 5 targets validates', True)

    def run_unknown_field():
        return SC.score_line({'rushing_yards': 100}, SC.DRAFTKINGS_STYLE)
    assert_guard_is_load_bearing(
        run=run_unknown_field, module_path='nfl.scoring.engine',
        attr='score_line',
        caught=lambda o: o.state is State.FAIL
        and o.code == 'UNKNOWN_STAT_FIELD',
        returns=Outcome.ok('STUB', value=0.0))
    check('H2 scoring.score_line is load-bearing -- bypassed, a misspelled '
          'stat field scores silently as zero', True)


if __name__ == '__main__':
    test_a_schema_accepts_a_complete_draw()
    test_b_schema_refuses_incompleteness()
    test_c_orderings_are_checked_per_draw_not_on_the_mean()
    test_d_fantasy_may_not_enter_the_football_schema()
    test_e_scoring_is_exact_against_hand_calculation()
    test_f_edge_cases()
    test_g_profile_isolation_and_config_not_code()
    test_h_guard_deletions()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
