"""NFL-V1-R4 adversarial tests: the complete engine, and what it refuses."""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import (Cause, Outcome,   # noqa: E402
                                               State)
from nfl.production import derived as DV                          # noqa: E402
from nfl.production import qb_accounting as QBACC                 # noqa: E402
from nfl.production.nonqb import accounting as ACC                # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402
from nfl.production.nonqb import player_record as PR              # noqa: E402
from nfl.production.nonqb import readiness as RD                  # noqa: E402

PASSED = FAILED = 0
IDS = ['p1', 'p2', 'p3']
ORD = 202601


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


# ================================================= rushing conversion
def test_A_rushing_conversion_refuses_and_names_the_decisions():
    print('\nA. rushing yards have no governed control, and say so')
    o = LY.rushing_conversion(Outcome.ok('CARRIES_OK', value={}))
    check('the layer defers rather than producing rushing yards',
          o.state is State.DEFERRED
          and o.code == 'RUSHING_CONVERSION_CONTROL_UNDEFINED',
          f'{o.state.value}[{o.code}]')
    dec = o.evidence['owed']['decisions']
    check('  it names three open scientific decisions', len(dec) == 3, len(dec))
    for tag in ('RUSH-DECISION-1', 'RUSH-DECISION-2', 'RUSH-DECISION-3'):
        check(f'  {tag} is named', any(d.startswith(tag) for d in dec))
    check('  and it emits no value at all', o.value is None)
    inv = json.load(open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                                      'rushing_inventory.json')))
    check('  the inventory records the same verdict',
          inv['verdict'] == 'RUSHING_CONVERSION_CONTROL_UNDEFINED')
    check('  and names the chronology defect in P5A explicitly',
          'INNER VALIDATION' in inv['9_chronology_rule']
          ['family_selection_defect'].upper())
    check('  the inventory does not claim P5A is accepted',
          inv['3_owner_action']['decision_artifact'] is None
          and inv['3_owner_action']['decision_field_present'] is False)


def test_A_caller_supplied_rushing_prior_is_refused():
    o = LY.rushing_conversion(Outcome.ok('CARRIES_OK', value={}),
                              priors={'yards_per_carry': 4.3})
    check('a caller-supplied rushing efficiency prior is refused',
          o.state is State.FAIL
          and o.code == 'RUSHING_PRIOR_NOT_OWNED_BY_CALLER',
          f'{o.state.value}[{o.code}]')


def test_A_no_point_ypc_anywhere_in_production():
    """The forbidden implementation, checked at the source level.

    A point yards-per-carry is the obvious way to make the layer 'work' and it
    is exactly the defect class this project has hit four times. The scan is
    crude on purpose: it is cheap, and a seeded violation proves it bites.
    """
    import re
    bad = re.compile(r'(carries|carry_draws|rush_opp)\s*\*\s*'
                     r'(ypc|yards_per_carry|point)', re.I)
    prod = os.path.join(_ROOT, 'nfl', 'production')
    hits = []
    for root, _d, files in os.walk(prod):
        for f in files:
            if not f.endswith('.py'):
                continue
            p = os.path.join(root, f)
            for i, line in enumerate(open(p).read().splitlines(), 1):
                if line.strip().startswith('#'):
                    continue
                if bad.search(line):
                    hits.append(f'{f}:{i}')
    check('no production line multiplies carries by a point yards-per-carry',
          not hits, hits[:3])
    check('  and the scan would catch one if it existed',
          bool(bad.search('rushing = carries * ypc')))


# ================================================= rushing TD
def test_B_rushing_td_is_supported_and_bounded():
    print('\nB. rushing touchdowns are supported, and require a carry')
    m = 40
    C = np.array([[3] * m, [0] * m, [5] * m], float)
    car = Outcome.ok('TARGETS_CARRIES_OK', value={'share': None},
                     test_only=True)
    pri = {'B_pos': {'RB': 0.03}, 'B_league': 0.035, 'kind': 'rush'}
    o = LY.rushing_td(car, C, pri, IDS, ['RB'] * 3, ORD, m=m)
    check('the layer runs on a carry draw', o.state is State.PASS,
          f'{o.state.value}[{o.code}]')
    TD = o.value['rush_td']
    check('  a player with zero carries scores zero rushing TDs',
          int(TD[1].sum()) == 0)
    check('  no draw scores more TDs than it had carries',
          bool((TD <= np.rint(C)).all()))
    check('  the TEST_ONLY mark propagates', o.evidence['test_only'] is True)
    bad = LY.rushing_td(car, C, {'td_per_opportunity': 0.05}, IDS,
                        ['RB'] * 3, ORD, m=m)
    check('  a caller-supplied rate is refused',
          bad.state is State.FAIL and bad.code == 'TD_PRIOR_NOT_FROZEN',
          f'{bad.state.value}[{bad.code}]')
    up = LY.rushing_td(Outcome.blocked('X', 'y', cause=Cause.DATA), C, pri, IDS,
                       ['RB'] * 3, ORD, m=m)
    check('  and without a carry allocation it blocks upstream',
          up.code == 'BLOCKED_UPSTREAM_RUSH_OPPORTUNITY', up.code)


# ================================================= joint accounting
def _rush_case(n=4, m=20):
    rng = np.random.default_rng(3)
    starts, counts = [0, 2], [2, 2]
    S = rng.dirichlet(np.ones(3), size=(2, m))
    share = np.zeros((n, m)); other = np.zeros((2, m))
    for k, (a, c) in enumerate(zip(starts, counts)):
        share[a:a + c] = S[k][:, :c].T
        other[k] = S[k][:, c]
    V = np.full((2, m), 27.0)
    C = share * np.repeat(V, counts, axis=0)
    return dict(carry_share=share, carry_other=other, team_carries=V,
                player_carries=C, starts=starts, counts=counts,
                rushing_td=np.minimum(np.rint(C), 1.0))


def test_C_rushing_accounting_identities_are_load_bearing():
    print('\nC. the rushing half of the joint accounting')
    base = _rush_case()
    o = ACC.reconcile_rushing(**base)
    check('a clean rushing draw set reconciles', o.state is State.PASS,
          f'{o.state.value}[{o.code}] {o.detail[:120]}')
    check('  rushing yards are NOT_APPLICABLE, never satisfied',
          o.evidence['zero_carries_implies_zero_rushing_yards']
          == 'NOT_APPLICABLE')
    check('  and the reason names the missing control',
          'RUSHING_CONVERSION_CONTROL_UNDEFINED'
          in o.evidence['rushing_yards_reason'])

    b = dict(base); b['carry_other'] = base['carry_other'] + 0.05
    check('a broken team carry closure is caught',
          ACC.reconcile_rushing(**b).state is State.FAIL)

    b = dict(base); b['rushing_td'] = np.rint(base['player_carries']) + 1
    r = ACC.reconcile_rushing(**b)
    check('a rushing TD without a carry is caught',
          r.state is State.FAIL
          and any(v['identity'] == 'rushing_td_within_carries'
                  for v in r.evidence['violations']),
          f'{r.state.value}[{r.code}]')

    b = dict(base)
    b['rushing_yards'] = np.where(np.rint(base['player_carries']) <= 0, 11.0,
                                  40.0)
    r = ACC.reconcile_rushing(**b)
    check('nonzero rushing yards on zero carries is caught',
          r.state is State.FAIL
          and any(v['identity'] == 'zero_carries_implies_zero_rushing_yards'
                  for v in r.evidence['violations']),
          f'{r.state.value}[{r.code}]')

    b = dict(base)
    b['qb_rush_opportunity'] = base['carry_other'] * base['team_carries'] + 5.0
    r = ACC.reconcile_rushing(**b)
    check('a QB rush draw exceeding the OTHER mass it sits inside is caught',
          r.state is State.FAIL
          and any(v['identity'] == 'qb_rush_contained_in_other'
                  for v in r.evidence['violations']),
          f'{r.state.value}[{r.code}]')

    e = ACC.reconcile_rushing(np.zeros((0, 0)), np.zeros((0, 0)),
                              np.zeros((0, 0)), np.zeros((0, 0)), [], [])
    check('an empty rushing draw set FAILS rather than passing vacuously',
          e.state is State.FAIL and e.code == 'NONQB_ACCOUNTING_VACUOUS',
          f'{e.state.value}[{e.code}]')


def test_C_qb_double_count_is_measured_not_reconciled():
    m = 20
    rb = np.full((2, m), 9.0)
    team = np.full((1, m), 27.0)
    other = 0.20 * team          # OTHER *carries*, not the share

    qb = np.full((1, m), 5.0)
    o = ACC.assert_no_double_counted_qb_carries(rb, other, team, qb)
    check('the double-count is reported as a measured excess',
          o.state is State.PASS and o.value['mean_excess_if_summed'] > 0,
          o.value)
    check('  and the measurement that motivates it is carried',
          '15.68%' in o.evidence['measurement'])


# ================================================= QB vs team volume
def test_D_qb_team_volume_guard_bites():
    print('\nD. the QB layer against team volume, on one draw index')
    m = 50
    rows = [{'team': 'AAA', 'season': 2026, 'week': 1, 'gsis_id': 'q1'},
            {'team': 'AAA', 'season': 2026, 'week': 1, 'gsis_id': 'q2'}]
    D = {'db': np.full((2, m), 30.0), 'rush_opp': np.full((2, m), 4.0)}
    ok = QBACC.reconcile_team_volume(
        D, rows, team_dropback_draws={'AAA': np.full(m, 70.0)},
        team_carry_draws={'AAA': np.full(m, 27.0)})
    check('two QBs inside a 70-dropback team reconcile',
          ok.state is State.PASS, f'{ok.state.value}[{ok.code}]')
    bad = QBACC.reconcile_team_volume(
        D, rows, team_dropback_draws={'AAA': np.full(m, 36.0)},
        team_carry_draws={'AAA': np.full(m, 27.0)})
    check('  two 30-dropback QBs inside a 36-dropback team do NOT',
          bad.state is State.FAIL and bad.code == 'QB_TEAM_VOLUME_INCOHERENT',
          f'{bad.state.value}[{bad.code}]')
    check('  and the failure names the research gap',
          'QB_PRIMARY_PASSER_SELECTION' in bad.evidence['research_gap'])
    check('  the drawn/budget ratio is reported',
          abs(bad.evidence['qb_dropback_within_team_volume_ratio']
              - 60.0 / 36.0) < 1e-3,       # the evidence rounds to 4 dp
          bad.evidence.get('qb_dropback_within_team_volume_ratio'))
    na = QBACC.reconcile_team_volume(D, rows)
    check('  no budget supplied is NOT_APPLICABLE, never a pass',
          na.state is State.NOT_APPLICABLE
          and na.code == 'QB_TEAM_VOLUME_NOT_SUPPLIED',
          f'{na.state.value}[{na.code}]')
    mm = QBACC.reconcile_team_volume(
        D, rows, team_dropback_draws={'AAA': np.full(m - 1, 70.0)})
    check('  a mismatched draw width is a named refusal',
          mm.state is State.FAIL and mm.code == 'CROSS_DRAW_INDEX_MISMATCH',
          f'{mm.state.value}[{mm.code}]')


# ================================================= player output contract
def _mets(run_id='r'):
    return {k: PR.summarise(np.arange(10) + 1, 'spec', k, run_id)
            for k in ('appearance', 'participation', 'targets', 'receptions',
                      'receiving_yards', 'receiving_td', 'carries',
                      'rushing_td')}


def test_E_unsupported_metric_is_absent_never_zero():
    print('\nE. an unsupported metric is ABSENT with a reason')
    m = _mets()
    m['rushing_yards'] = PR.absent('rushing_yards',
                                   'RUSHING_CONVERSION_CONTROL_UNDEFINED', 'r')
    r = PR.record('p1', 'RB', 'g', 'r', m)
    o = PR.validate([r])
    check('a record with a properly absent metric validates',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')
    check('  and the absent metric carries no number',
          all(r['metrics']['rushing_yards'][f] is None
              for f in ('mean', 'p10', 'p50', 'p90')))

    z = dict(m)
    z['rushing_yards'] = dict(m['rushing_yards'], mean=0.0)
    bad = PR.validate([PR.record('p1', 'RB', 'g', 'r', z)])
    check('  ABSENT carrying a zero is REFUSED',
          bad.state is State.FAIL
          and bad.code == 'UNSUPPORTED_METRIC_EMITTED_AS_VALUE',
          f'{bad.state.value}[{bad.code}]')

    n = dict(m)
    n['rushing_yards'] = dict(m['rushing_yards'], reason='')
    bad2 = PR.validate([PR.record('p1', 'RB', 'g', 'r', n)])
    check('  ABSENT with no reason is REFUSED',
          bad2.state is State.FAIL, f'{bad2.state.value}[{bad2.code}]')

    silent = dict(m)
    silent.pop('rushing_td')
    bad3 = PR.validate([PR.record('p1', 'RB', 'g', 'r', silent)])
    check('  silence about an expected metric is REFUSED',
          bad3.state is State.FAIL
          and bad3.code == 'EXPECTED_METRIC_NOT_ADDRESSED',
          f'{bad3.state.value}[{bad3.code}]')

    thin = dict(m)
    thin['targets'] = dict(m['targets'], spec_version=None)
    bad4 = PR.validate([PR.record('p1', 'RB', 'g', 'r',
                                  dict(thin, rushing_yards=m['rushing_yards']))])
    check('  a metric without its audit fields is REFUSED',
          bad4.state is State.FAIL
          and bad4.code == 'PLAYER_METRIC_NOT_AUDITABLE',
          f'{bad4.state.value}[{bad4.code}]')

    check('  and an empty record set is REFUSED',
          PR.validate([]).code == 'PLAYER_RECORDS_EMPTY')


def test_E_every_present_metric_is_auditable():
    m = _mets()
    m['rushing_yards'] = PR.absent('rushing_yards', 'undefined', 'r')
    r = PR.record('p1', 'RB', 'g', 'run-xyz', m)
    for k, v in r['metrics'].items():
        if v['status'] != 'PRESENT':
            continue
        for f in ('n_draws', 'mean', 'p10', 'p50', 'p90', 'spec_version',
                  'run_id'):
            check(f'  {k} carries {f}', v.get(f) is not None, k)
        check(f'  {k} carries its governance state',
              bool(v['governance']['layer']), k)


# ================================================= per-game readiness
def test_F_readiness_is_per_game():
    print('\nF. readiness is a per-game property')
    r = RD.game_readiness(2026, 1)
    check('every game gets its own state', r['n_games'] == len(r['games']))
    check('  every state is one of the declared six',
          all(g['state'] in RD.GAME_STATES for g in r['games']),
          {g['state'] for g in r['games']} - set(RD.GAME_STATES))
    check('  a game executes only if BOTH teams are ready',
          all(g['may_execute_d2'] ==
              all(t['state'].startswith('READY') for t in g['teams'])
              for g in r['games']))
    unfiled = [g for g in r['games']
               if g['state'] == 'INJURY_REPORT_NOT_YET_FILED']
    if unfiled:
        check('  an unfiled report says ABSENCE OF A REPORT, not "no injuries"',
              'ABSENCE OF A REPORT' in unfiled[0]['reason'],
              unfiled[0]['reason'][:80])
    check('  the slate dashboard is still reported alongside',
          'n_executable' in r and 'state_counts' in r)


def test_F_one_missing_report_does_not_change_another_game():
    """A team's state must depend on its OWN report and nothing else."""
    a = RD.team_readiness(2026, 1, 'NE')
    b = RD.team_readiness(2026, 1, 'SEA')
    c = RD.team_readiness(2026, 1, 'ARI')
    check('a team that filed is not dragged down by one that did not',
          a['state'] != 'INJURY_REPORT_NOT_YET_FILED'
          and c['state'] == 'INJURY_REPORT_NOT_YET_FILED',
          f"{a['state']} / {c['state']}")
    check('  and both filed teams are judged on their own rows',
          a['n_rows'] > 0 and b['n_rows'] > 0)
    g = RD.game_readiness(2026, 1)
    ne = [x for x in g['games'] if 'NE' in x['game_id'].split('_')]
    check('  the NE game is blocked by NE/SEA, not by a third team',
          bool(ne) and ne[0]['blocking_team'] in ('NE', 'SEA'),
          ne[0]['blocking_team'] if ne else None)


def test_F_chronology_and_staleness_are_separate_states():
    """A capture retrieved after kickoff is a chronology failure, not late."""
    o = RD.team_readiness(2026, 1, 'NE',
                          kickoff_utc='2026-09-01T00:00:00Z')
    check('a capture retrieved after kickoff is a CHRONOLOGY failure',
          o['state'] == 'INJURY_REPORT_CHRONOLOGY_FAILURE', o['state'])
    o2 = RD.team_readiness(2026, 1, 'NE', written_at='2026-09-01T00:00:00Z')
    check('  and so is one retrieved after written_at', 
          o2['state'] == 'INJURY_REPORT_CHRONOLOGY_FAILURE', o2['state'])
    check('  staleness is a different state with a declared bound',
          RD.STALE_HOURS > 0 and 'INJURY_REPORT_STALE' in RD.GAME_STATES)


# ================================================= week 2
def test_G_both_future_requirements_are_named():
    print('\nG. the two future data requirements are separate')
    f = RD.future_requirements(2026, 1)
    req = f['requirements']
    check('injuries_2026 is named', 'injuries_2026' in req)
    check('  pbp_participation_2026 is named', 'pbp_participation_2026' in req)
    check('  they carry different refusals',
          req['injuries_2026']['refusal_if_absent']
          != req['pbp_participation_2026']['refusal_if_absent'])
    check('  neither offers a substitute',
          all('NONE' in v['substitute'] for v in req.values()))
    f2 = RD.future_requirements(2026, 2)
    check('  and at week 2 the participation requirement binds',
          f2['requirements']['pbp_participation_2026']['state']
          == 'NOT_SATISFIED',
          f2['requirements']['pbp_participation_2026'])
    check('  week 1 does not need it',
          f['requirements']['pbp_participation_2026']['state'] == 'SATISFIED')


# ================================================= research immutability
def test_H_production_does_not_write_into_the_research_tree():
    print('\nH. production leaves nfl/research byte-identical')
    from nfl.production.nonqb import p4c_params as P4
    o = DV.assert_research_tree_unchanged(
        lambda: P4.class_point_forecast('targets', 2026, 1,
                                        [{'gsis_id': 'x', 'position': 'WR'}]))
    check('a production call leaves the research tree unchanged',
          o.state is State.PASS,
          f'{o.state.value}[{o.code}] {o.detail[:200]}')
    check('  over a non-trivial number of files',
          int(o.evidence.get('n_files_watched') or 0) > 100,
          o.evidence.get('n_files_watched'))
    # THE GUARD MUST BITE. Seed a mutation and prove it is caught.
    import pathlib
    probe = DV.RESEARCH / '_r4_mutation_probe.tmp'
    def _mutate():
        probe.write_text('seeded')
        return 'seeded'
    try:
        bad = DV.assert_research_tree_unchanged(_mutate)
        check('  and a seeded mutation IS caught',
              bad.state is State.FAIL and bad.code == 'RESEARCH_TREE_MUTATED',
              f'{bad.state.value}[{bad.code}]')
    finally:
        if probe.exists():
            probe.unlink()
    check('  the derived cache lives outside nfl/research',
          'research' not in str(DV.cache_dir()),
          str(DV.cache_dir()))


# ================================================= determinism
def test_I_same_seed_reproduces_and_different_seed_does_not():
    print('\nI. draw semantics')
    m = 60
    C = np.full((3, m), 6.0)
    car = Outcome.ok('TARGETS_CARRIES_OK', value={}, test_only=True)
    pri = {'B_pos': {'RB': 0.05}, 'B_league': 0.05, 'kind': 'rush'}
    a = LY.rushing_td(car, C, pri, IDS, ['RB'] * 3, ORD, m=m, seed=1)
    b = LY.rushing_td(car, C, pri, IDS, ['RB'] * 3, ORD, m=m, seed=1)
    c = LY.rushing_td(car, C, pri, IDS, ['RB'] * 3, ORD, m=m, seed=2)
    check('the same seed reproduces the draws exactly',
          bool((a.value['rush_td'] == b.value['rush_td']).all()))
    check('  a different seed does not',
          not bool((a.value['rush_td'] == c.value['rush_td']).all()))


def test_J_cross_layer_identity_is_measured_and_currently_fails():
    """Passing yards and receiving yards are the SAME quantity.

    Measured on 3,230 historical team-games: correlation 0.9996, mean absolute
    difference 0.26 yards, and for touchdowns exact equality in 3,230 of 3,230
    with no lateral exception at all. The simulator draws them in two
    independent layers.

    This test PINS the defect. It asserts the check runs, is recorded, and
    currently fails -- so the failure cannot quietly become a pass without
    someone changing this test, and cannot be forgotten either.
    """
    print('\nJ. the cross-layer passing/receiving identity')
    f = os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                     'engine_rehearsal.json')
    if not os.path.exists(f):
        check('the recorded rehearsal exists', False, f)
        return
    r = json.load(open(f))
    xl = [v for g in r['games']
          for v in (g['accounting'].get('cross_layer') or {}).values()]
    check('the cross-layer check ran for every team on the slate',
          len(xl) == 2 * r['n_games'], len(xl))
    check('  it is no longer DEFERRED -- it was handed the receiving draws',
          all('CROSS_LAYER_RECONCILIATION_NOT_RUN' not in v['state']
              for v in xl))
    check('  and it is not a shape error either',
          all('SHAPE_MISMATCH' not in v['state'] for v in xl))
    fails = [v for v in xl if v['state'].startswith('FAIL')]
    check('  it currently FAILS, which is the honest state', len(fails) == len(xl),
          f'{len(fails)} of {len(xl)}')
    resid = np.mean([v['mean_abs_yard_residual'] for v in xl])
    pyds = np.mean([v['mean_team_passing_yards'] for v in xl])
    check(f'  the residual is large, not marginal ({resid:.1f} yd on {pyds:.1f})',
          resid > 0.3 * pyds, resid / pyds)
    td = sum(v.get('td_violating_draws', 0) for v in xl)
    nd = sum(v.get('n_draws', 0) for v in xl)
    check(f'  and the TD identity, which has NO exception, fails in most draws '
          f'({td} of {nd})', td > 0.5 * nd, td / max(nd, 1))
    check('  the historical truth is recorded in the finding',
          '0.9996' in open(os.path.join(
              _ROOT, 'nfl', 'research', 'j1',
              'J1_DOWNSTREAM_FINDING.md')).read())


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
