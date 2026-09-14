"""Team-level conservation: the contract table, the evaluators, and a fence
across every sealed board.

WHAT THIS MODULE ASSERTS
========================
1. The declaration in `nfl.product.conservation` is well formed: every check
   carries a class, what it asserts, and the contract it is asserting; every
   RESIDUAL names who owns the mass and whether that owner is in the artifact;
   every CONTAINMENT names where it is gated so that two files cannot come to
   two verdicts about one rule; every ABSENT contract says why no quantity can
   express it.
2. The evaluators BEHAVE. Each catches a seeded violation, each refuses rather
   than passes when fed nothing, and a team with no modelled layer produces a
   STATED ABSENCE rather than a zero.
3. THE DENOMINATOR TRAP CANNOT REACH THE TARGET CHECK. `team_volume/
   team_targets` is perturbed by an arbitrary amount and the target
   conservation records must be bit-identical. This is tested BEHAVIOURALLY
   rather than by reading the code, because "we do not use that array" is the
   kind of claim that survives a refactor in a comment and dies in the code.
4. ROWS ARE RESOLVED BY IDENTITY. Permuting a layer's rows together with its
   declared `row_ids` must not change a single number; a manifest whose row
   axis this module does not understand must be refused, not guessed.
5. NOTHING REPAIRS. Asserted on the AST: no clip, no renormalisation, no write
   into a draw array, no file opened for writing anywhere in the module.
6. Every sealed run under `nfl/research/live/2026_01_*` is re-scanned and the
   numbers are asserted against a frozen baseline. This is a REGRESSION FENCE
   on history. The residuals it fences are NOT expected to be zero and are not
   a target: a quarter of the team carry level has no modelled owner, and the
   fence exists so that a silent rewrite of a sealed artifact, or a change in
   this module's arithmetic, fails here instead of quietly moving a published
   number.

WHAT IT DOES NOT ASSERT
=======================
Nothing here says any projection is good, and nothing here says mass is
conserved. A residual is a measurement of where opportunity went, not a
verdict on the forecast. No equivalence margin is predeclared and no TOST is
run, so no check is written as "closed", "stable" or "correct": each is
"N of M draws, residual mean X, sd Y".
"""
from __future__ import annotations

import ast
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.product import conservation as CN                         # noqa: E402
from nfl.production import draw_coherence as DC                    # noqa: E402

PASSED = FAILED = 0

LIVE = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live'
GLOB = '2026_01_*/*/*/player_draws.npz'
TONIGHT = (LIVE / '2026_01_DEN_KC' / 'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8'
           / 'f91342d6787a66a1')

# The numbers the SEALED boards carry, re-derived below and asserted here.
# NOT a target and NOT expected to be zero -- see the module docstring.
SEALED = {
    'runs': 102,
    'team_runs': 204,
    'c3_runs': 34,                       # runs declaring C3 applied
    'closure_failures': 0,
    'qb_room_cells': 232000,
    'passing_line_cells': 95000,
    'containment_breaching_team_runs': 60,
    'containment_breaching_cells': 371,
    'containment_breaching_games': 9,
    'rush_residual_team_runs': 67,
    'rush_residual_sign_changing_team_runs': 67,
    'stored_target_exact_agreement_cells': 0,
    'stored_target_cells': 96000,
}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _runs():
    return sorted(LIVE.glob(GLOB))


def _load(d):
    man = json.load(open(d / 'player_draws_manifest.json'))
    board = json.load(open(d / 'board.json'))
    art = json.load(open(d / 'forecast_artifact.json'))
    z = np.load(d / 'player_draws.npz')
    arrays = {k.replace('__', '/', 1): z[k].astype(float) for k in z.files}
    return man, board, art, arrays


def _synthetic(n_draws=8):
    """A two-team draw set that closes on every contract, built by hand.

    Every number here is CONSTRUCTED to satisfy the identities, so a test that
    seeds a violation is changing one thing against a known-good background.
    """
    m = n_draws
    att = np.array([[10.] * m, [4.] * m, [12.] * m, [3.] * m])
    sacks = np.array([[1.] * m, [0.] * m, [2.] * m, [1.] * m])
    scr = np.array([[2.] * m, [1.] * m, [1.] * m, [0.] * m])
    db = att + sacks + scr
    ro = scr + np.array([[3.] * m, [0.] * m, [2.] * m, [1.] * m])
    cmp_ = np.array([[6.] * m, [2.] * m, [7.] * m, [2.] * m])
    ptd = np.array([[1.] * m, [0.] * m, [1.] * m, [0.] * m])
    pyds = np.array([[70.] * m, [20.] * m, [80.] * m, [15.] * m])
    # receivers: two per team, receptions/yards/td summing to the QB room
    rec = np.array([[5.] * m, [3.] * m, [6.] * m, [3.] * m])
    ryd = np.array([[60.] * m, [30.] * m, [65.] * m, [30.] * m])
    rtd = np.array([[1.] * m, [0.] * m, [1.] * m, [0.] * m])
    tgt = np.array([[7.] * m, [5.] * m, [8.] * m, [5.] * m])
    car = np.array([[9.] * m, [10.] * m])
    arrays = {
        'qb/att': att, 'qb/sacks': sacks, 'qb/scr': scr, 'qb/db': db,
        'qb/cmp': cmp_, 'qb/ptd': ptd, 'qb/pyds': pyds, 'qb/rush_opp': ro,
        'receiving/targets': tgt, 'receiving/receptions': rec,
        'receiving/receiving_yards': ryd, 'receiving/receiving_td': rtd,
        'rushing/carries': car,
        'team_volume/team_dropbacks_part': np.array([[18.] * m, [19.] * m]),
        'team_volume/team_carries': np.array([[26.] * m, [24.] * m]),
        'team_volume/team_targets': np.array([[31.] * m, [29.] * m]),
    }
    rows = {'AA': {'qb': [0, 1], 'receiving': [0, 1], 'rushing': [0],
                   'team_volume': 0},
            'BB': {'qb': [2, 3], 'receiving': [2, 3], 'rushing': [1],
                   'team_volume': 1}}
    regime = {'A1': True, 'C3': True, 'R2': True}
    return arrays, rows, regime


def _rec(outcome, check_name, team):
    for r in outcome.evidence['records']:
        if r['check'] == check_name and r['team'] == team:
            return r
    return None


# ================================================== 1: the declaration
def test_every_contract_is_declared_with_a_class_and_a_source():
    """A check with no declared class cannot be said to gate or not gate, and
    a residual with no named owner is a number nobody can act on."""
    check('there is a declared contract table', bool(CN.CONTRACTS))
    classes = {CN.CLOSURE, CN.RESIDUAL, CN.CONTAINMENT, CN.ABSENT}
    check('every contract carries one of the four declared classes',
          all(v['class'] in classes for v in CN.CONTRACTS.values()))
    parts = (set(CN.CLOSURES) | set(CN.RESIDUALS) | set(CN.CONTAINMENTS)
             | set(CN.ABSENT_CONTRACTS))
    check('the four classes partition the table',
          parts == set(CN.CONTRACTS)
          and sum(len(x) for x in (CN.CLOSURES, CN.RESIDUALS,
                                   CN.CONTAINMENTS, CN.ABSENT_CONTRACTS))
          == len(CN.CONTRACTS))
    check('all four classes are populated -- a table that is all CLOSURE has '
          'not thought about unowned mass',
          all((CN.CLOSURES, CN.RESIDUALS, CN.CONTAINMENTS,
               CN.ABSENT_CONTRACTS)),
          f'{len(CN.CLOSURES)}/{len(CN.RESIDUALS)}/{len(CN.CONTAINMENTS)}/'
          f'{len(CN.ABSENT_CONTRACTS)}')
    for name, spec in sorted(CN.CONTRACTS.items()):
        check(f'  {name} states what it asserts',
              len((spec.get('asserts') or '').strip()) > 40)
        check(f'  {name} names the contract it is asserting',
              len((spec.get('contract') or '').strip()) > 40)
        check(f'  {name} declares a view and a unit',
              spec.get('view') in CN.VIEWS and spec.get('unit') == 'team-draw')
        if spec['class'] == CN.RESIDUAL:
            check(f'  {name} names who owns the residual',
                  len((spec.get('residual_owner') or '').strip()) > 20)
            check(f'  {name} declares whether that owner is in the artifact',
                  isinstance(spec.get('owner_stored'), bool))
        if spec['class'] == CN.CONTAINMENT:
            check(f'  {name} names where it is gated, so two files cannot '
                  f'disagree about one rule',
                  len((spec.get('gated_elsewhere') or '').strip()) > 20)
        if spec['class'] == CN.ABSENT:
            check(f'  {name} says why no quantity can express it',
                  len((spec.get('why_absent') or '').strip()) > 40)
        if spec['class'] in (CN.CLOSURE, CN.CONTAINMENT):
            check(f'  {name} carries a tolerance', spec.get('tol') is not None)


def test_gating_is_deferred_to_draw_coherence_by_real_name():
    """A CONTAINMENT here must point at a check that actually exists there.
    A pointer to a check that was renamed is worse than no pointer."""
    n = 0
    for name in CN.CONTAINMENTS + CN.CLOSURES:
        where = CN.CONTRACTS[name].get('gated_elsewhere') or ''
        if 'draw_coherence.' not in where:
            continue
        n += 1
        named = where.split('draw_coherence.', 1)[1]
        named = named.split(' ')[0].strip('.,()').replace('_\n', '')
        # the declaration wraps long names across lines; rejoin and match on
        # the prefix so a rename still fails but a wrap does not.
        hit = [k for k in DC.COHERENCE if named.startswith(k) or
               k.startswith(named.replace("'", ''))]
        check(f'  {name} points at a real draw_coherence check', bool(hit),
              f'no COHERENCE entry matches {named!r}')
    check('at least one contract defers its gate to draw_coherence by name',
          n >= 3, f'{n}')


def test_the_denominator_traps_are_declared_as_data():
    check('the arrays that must never be a denominator are held as data, not '
          'as a comment', set(CN.NOT_A_DENOMINATOR) ==
          {'team_volume/team_targets', 'team_volume/team_carries'})
    for k, why in sorted(CN.NOT_A_DENOMINATOR.items()):
        check(f'  {k} says why', len(why) > 60 and 'J-1' in why)


# ================================================ 2: the evaluators behave
def test_a_clean_synthetic_board_measures_and_holds():
    arrays, rows, regime = _synthetic()
    o = CN.dashboard(arrays, rows, regime, game_id='SYNTH', run_id='synth')
    check('a hand-built closing board measures', o.state is State.PASS,
          f'{o.code}: {o.detail[:200]}')
    for name in ('team_dropback_partition', 'qb_room_closes_on_team_dropbacks',
                 'receptions_close_on_completions',
                 'receiving_yards_close_on_passing_yards',
                 'receiving_td_closes_on_passing_td'):
        r = _rec(o, name, 'AA')
        check(f'  {name} holds on the synthetic board',
              r is not None and r['state'] == 'PASS',
              f'{r and r["state"]}')
    r = _rec(o, 'target_opportunity_closes', 'AA')
    check('  the unowned target mass is reported with its size',
          r is not None and abs(r['residual']['mean'] - 2.0) < 1e-9,
          f'{r and r["residual"]["mean"]}')
    check('  and it is not called a violation',
          r['state'] == 'MEASURED' and r['violating_cells'] is None)
    r = _rec(o, 'rush_opportunity_closes', 'AA')
    # level 26 = rb 9 + scr 3 + designed 3 -> 11 unowned
    check('  the unowned rush mass is reported with its size',
          r is not None and abs(r['residual']['mean'] - 11.0) < 1e-9,
          f'{r and r["residual"]["mean"]}')
    check('  and its four owners are named as parts',
          set(r['parts']) == {'rb', 'qb_scramble', 'qb_designed',
                              'wr_te_kneel_fringe_OTHER'})


def test_each_closure_catches_a_seeded_violation():
    """One array moved, one closure fails, and the rest do not."""
    seeds = (
        ('team_dropback_partition', 'qb/db', 0),
        ('receptions_close_on_completions', 'receiving/receptions', 0),
        ('receiving_yards_close_on_passing_yards',
         'receiving/receiving_yards', 0),
        ('receiving_td_closes_on_passing_td', 'receiving/receiving_td', 0),
    )
    for name, key, row in seeds:
        arrays, rows, regime = _synthetic()
        arrays = dict(arrays)
        a = arrays[key].copy()
        a[row, 0] += 1.0
        arrays[key] = a
        o = CN.dashboard(arrays, rows, regime)
        check(f'  moving {key} by one is caught by {name}',
              o.state is State.FAIL and name in
              [x['check'] for x in o.evidence['records']
               if x['state'] == 'FAIL'],
              f'{o.code}')
    arrays, rows, regime = _synthetic()
    a = arrays['qb/db'].copy()
    a[0, 0] += 1.0
    arrays = dict(arrays, **{'qb/db': a})
    o = CN.dashboard(arrays, rows, regime)
    r = _rec(o, 'qb_room_closes_on_team_dropbacks', 'AA')
    check('  a dropback that breaks the room total also breaks the room '
          'closure on the team level', r['state'] == 'FAIL')
    check('  and the other team is untouched',
          _rec(o, 'qb_room_closes_on_team_dropbacks', 'BB')['state'] == 'PASS')


def test_containment_breaches_are_recorded_and_do_not_gate_here():
    arrays, rows, regime = _synthetic()
    tc = arrays['team_volume/team_carries'].copy()
    tc[0, 0] = 1.0                       # below this team's QB rush opp
    arrays = dict(arrays, **{'team_volume/team_carries': tc})
    o = CN.dashboard(arrays, rows, regime)
    r = _rec(o, 'qb_rush_opportunity_within_team_carries', 'AA')
    check('a QB rush pool above the team carry level is recorded',
          r['state'] == 'BREACHED' and r['violating_cells'] == 1,
          f'{r["state"]}/{r["violating_cells"]}')
    check('  with its SIZE, which a violation count discards',
          r['residual']['min'] < -1.0)
    check('  and it does not gate here', r['gates_here'] is False
          and o.state is State.PASS)
    check('  it points at the file that does own the gate',
          'draw_coherence' in (r.get('gated_elsewhere') or ''))


def test_a_scramble_above_rush_opportunity_is_caught():
    arrays, rows, regime = _synthetic()
    scr = arrays['qb/scr'].copy()
    scr[0, 0] = arrays['qb/rush_opp'][0, 0] + 1.0
    arrays = dict(arrays, **{'qb/scr': scr})
    o = CN.dashboard(arrays, rows, regime)
    r = _rec(o, 'qb_designed_rush_non_negative', 'AA')
    check('a scramble count above rush opportunity is recorded, because the '
          'designed component is recovered by subtracting the two',
          r['state'] == 'BREACHED', f'{r["state"]}')


def test_emptiness_is_refused_and_never_reported_as_conserved():
    o = CN.dashboard({}, {'AA': {'qb': [0], 'team_volume': 0}}, {})
    check('no arrays is BLOCKED, not a conserved board',
          o.state is State.BLOCKED and o.code == 'CONSERVATION_NO_ARRAYS',
          f'{o.code}')
    arrays, rows, regime = _synthetic()
    o = CN.dashboard(arrays, {}, regime)
    check('no teams is BLOCKED, not a conserved board',
          o.state is State.BLOCKED and o.code == 'CONSERVATION_NO_TEAMS',
          f'{o.code}')
    o = CN.dashboard({'qb/att': np.zeros((1, 3))},
                     {'AA': {'qb': [0], 'team_volume': 0}}, {})
    check('a board on which nothing could be evaluated is BLOCKED VACUOUS, '
          'never PASS', o.state is State.BLOCKED
          and o.code == 'CONSERVATION_VACUOUS', f'{o.code}')
    o = CN.from_run_dir(pathlib.Path(_ROOT) / 'nfl' / 'tests')
    check('a directory that is not a sealed run is refused by name',
          o.state is State.BLOCKED
          and o.code == 'CONSERVATION_RUN_INCOMPLETE', f'{o.code}')


# ============================== 3: an absent layer is an absence, not a zero
def test_a_team_with_no_modelled_layer_reports_absence_not_zero_mass():
    arrays, rows, regime = _synthetic()
    rows = {'AA': dict(rows['AA'], receiving=[], rushing=[]), 'BB': rows['BB']}
    o = CN.dashboard(arrays, rows, regime)
    for name in ('target_opportunity_closes', 'receptions_close_on_completions',
                 'receiving_yards_close_on_passing_yards',
                 'receiving_td_closes_on_passing_td',
                 'rush_opportunity_closes'):
        r = _rec(o, name, 'AA')
        check(f'  {name} on a team with no rows is NOT_APPLICABLE',
              r['state'] == 'NOT_APPLICABLE', f'{r["state"]}')
        check(f'    and carries no residual at all, so it cannot be summed '
              f'as zero', r['residual'] is None
              and r.get('is_not_zero_mass') is True)
        check(f'    and says why', len((r.get('why') or '')) > 40)
    check('  the other team is still measured',
          _rec(o, 'rush_opportunity_closes', 'BB')['state'] == 'MEASURED')
    check('  and the board as a whole is not a failure',
          o.state is State.PASS, f'{o.code}')


def test_a_run_without_c3_does_not_get_the_c3_contracts():
    arrays, rows, _ = _synthetic()
    o = CN.dashboard(arrays, rows, {'A1': True, 'C3': False, 'R2': True})
    for name in ('receptions_close_on_completions',
                 'target_opportunity_closes',
                 'stored_team_targets_is_not_the_denominator'):
        r = _rec(o, name, 'AA')
        check(f'  {name} is NOT_APPLICABLE when C3 was not declared applied',
              r['state'] == 'NOT_APPLICABLE', f'{r["state"]}')
    check('  the reason names the regime, not the data',
          'C3' in _rec(o, 'receptions_close_on_completions', 'AA')['why'])
    o2 = CN.dashboard(arrays, rows, {'A1': False, 'C3': True, 'R2': False})
    check('  without R2 the room closure is not asserted',
          _rec(o2, 'qb_room_closes_on_team_dropbacks', 'AA')['state']
          == 'NOT_APPLICABLE')
    check('  without A1 the rush partition has no declared owner',
          _rec(o2, 'rush_opportunity_closes', 'AA')['state']
          == 'NOT_APPLICABLE')
    check('the regime map is read from a declaration and is all-off for an '
          'empty one',
          CN.regime_from_components([]) == {r: False for r in CN.REGIMES})
    check('  and turns on exactly what the run declared',
          CN.regime_from_components(['A1', 'C3'])['C3'] is True
          and CN.regime_from_components(['A1', 'C3'])['R2'] is False)


# ====================== 4: the stored team total can never be a denominator
def test_perturbing_stored_team_targets_changes_no_target_conservation():
    """TRAP 1, tested behaviourally. WS09 J-12: the stored vector is not the
    budget the game dealt from. If this module ever reached for it, the
    records below would move."""
    arrays, rows, regime = _synthetic()
    base = CN.dashboard(arrays, rows, regime)
    bad = dict(arrays)
    bad['team_volume/team_targets'] = (
        arrays['team_volume/team_targets'] * 3.0 + 17.0)
    moved = CN.dashboard(bad, rows, regime)
    for name in ('target_opportunity_closes', 'targets_within_throw_budget'):
        for t in ('AA', 'BB'):
            a, b = _rec(base, name, t), _rec(moved, name, t)
            check(f'  {name}/{t} is unchanged when the stored team target '
                  f'total is tripled',
                  a['residual'] == b['residual']
                  and a['lhs_mean'] == b['lhs_mean']
                  and a['rhs_mean'] == b['rhs_mean'])
    a = _rec(base, 'stored_team_targets_is_not_the_denominator', 'AA')
    b = _rec(moved, 'stored_team_targets_is_not_the_denominator', 'AA')
    check('  the trap row itself DOES move, because measuring the gap is its '
          'whole job', a['residual']['mean'] != b['residual']['mean'])
    check('  and the target budget is named as the throw process',
          'qb/att' in _rec(base, 'target_opportunity_closes', 'AA')['lhs'])


def test_perturbing_stored_team_carries_moves_only_the_carry_checks():
    """team_volume/team_carries IS the only carry level sealed, so it is used
    -- but only as a level to measure against, and the J-13 caveat travels
    with every residual computed from it."""
    arrays, rows, regime = _synthetic()
    base = CN.dashboard(arrays, rows, regime)
    bad = dict(arrays)
    bad['team_volume/team_carries'] = arrays['team_volume/team_carries'] + 5.0
    moved = CN.dashboard(bad, rows, regime)
    check('the rush residual moves with the carry level',
          _rec(base, 'rush_opportunity_closes', 'AA')['residual']['mean']
          != _rec(moved, 'rush_opportunity_closes', 'AA')['residual']['mean'])
    check('  and nothing in the target view moves with it',
          _rec(base, 'target_opportunity_closes', 'AA')['residual']
          == _rec(moved, 'target_opportunity_closes', 'AA')['residual'])
    owner = _rec(base, 'rush_opportunity_closes', 'AA')['residual_owner']
    check('  the J-13 caveat travels with the residual it affects',
          'J-13' in owner and 'SC1' in owner)


# ================================================= 5: rows, by identity only
def test_permuting_rows_with_their_ids_changes_nothing():
    man, board, art, arrays = _load(TONIGHT)
    rows = CN.team_rows(man, board['players'])
    check('rows resolve on the sealed board', rows.state is State.PASS,
          f'{rows.code}')
    regime = CN.regime_from_components(art['candidate_components_applied'])
    base = CN.dashboard(arrays, rows.value, regime)
    rng = np.random.default_rng(11)
    man2 = json.loads(json.dumps(man))
    arrays2 = dict(arrays)
    for lay in ('qb', 'receiving', 'rushing'):
        ids = man2['layers'][lay]['row_ids']
        p = rng.permutation(len(ids))
        man2['layers'][lay]['row_ids'] = [ids[i] for i in p]
        for k in list(arrays2):
            if k.startswith(lay + '/'):
                arrays2[k] = arrays2[k][p]
    rows2 = CN.team_rows(man2, board['players'])
    check('  rows still resolve after a permutation',
          rows2.state is State.PASS, f'{rows2.code}')
    moved = CN.dashboard(arrays2, rows2.value, regime)
    a = {(r['check'], r['team']): r.get('residual')
         for r in base.evidence['records']}
    b = {(r['check'], r['team']): r.get('residual')
         for r in moved.evidence['records']}
    check('  and not one number changes -- rows are joined by identity, never '
          'by position', a == b,
          f'{[k for k in a if a[k] != b.get(k)][:4]}')


def test_an_unjoinable_row_is_refused_rather_than_dropped():
    man, board, art, arrays = _load(TONIGHT)
    man2 = json.loads(json.dumps(man))
    man2['layers']['qb']['row_ids'] = (
        ['00-9999999'] + man2['layers']['qb']['row_ids'][1:])
    o = CN.team_rows(man2, board['players'])
    check('a draw row the board does not place on a team is refused',
          o.state is State.BLOCKED
          and o.code == 'CONSERVATION_ROWS_WITHOUT_A_TEAM', f'{o.code}')
    man3 = json.loads(json.dumps(man))
    man3['layers']['qb']['row_axis'] = 'jersey_number'
    o = CN.team_rows(man3, board['players'])
    check('a row axis this module does not understand is refused, not guessed',
          o.state is State.BLOCKED
          and o.code == 'CONSERVATION_ROW_AXIS_UNKNOWN', f'{o.code}')
    man4 = json.loads(json.dumps(man))
    man4['layers'].pop('team_volume')
    o = CN.team_rows(man4, board['players'])
    check('no team axis is refused', o.state is State.BLOCKED
          and o.code == 'CONSERVATION_NO_TEAM_AXIS', f'{o.code}')
    o = CN.team_rows(man, [])
    check('no player-to-team map is refused rather than falling back on row '
          'order', o.state is State.BLOCKED
          and o.code == 'CONSERVATION_NO_PLAYER_TEAM_MAP', f'{o.code}')


# ======================================== 6: a residual is a distribution
def test_a_residual_that_changes_sign_is_flagged_as_such():
    d = CN._dist(np.array([-2.0, 3.0, 0.0, 1.0]))
    check('a residual with cells on both sides is flagged',
          d['sign_changes'] is True and d['n_negative'] == 1
          and d['n_positive'] == 2 and d['n_zero'] == 1)
    d2 = CN._dist(np.array([1.0, 2.0, 3.0]))
    check('  a one-sided residual is not', d2['sign_changes'] is False)
    check('  the flag is a fact about the sample, so a residual whose mean is '
          'near zero is still flagged when it changes sign',
          CN._dist(np.array([-5.0, 5.0]))['sign_changes'] is True)
    for k in ('mean', 'sd', 'min', 'max', 'p05', 'p50', 'p95', 'mean_abs',
              'n_negative', 'n_positive', 'n_zero', 'cells'):
        check(f'  the residual carries {k}, so no caller has to settle for '
              f'the mean', k in d)


def test_the_renderer_prints_the_spread_not_only_the_mean():
    o = CN.from_run_dir(TONIGHT)
    text = CN.render(o)
    check('the dashboard renders', len(text) > 2000, f'{len(text)}')
    check('  it prints a standard deviation column', 'resid sd' in text)
    check('  it prints the count of over-allocated draws',
          'draws resid<0' in text)
    check('  it names the owner of every residual', 'owner of residual' in text)
    check('  it says out loud when an owner is not in the artifact',
          'NOT IN ARTIFACT' in text)
    check('  and it calls out residuals the mean does not describe',
          'change sign across draws' in text)


# ==================================== 7: diagnostics only, asserted on the AST
def test_nothing_in_the_module_repairs_clips_or_writes():
    src_path = pathlib.Path(CN.__file__)
    tree = ast.parse(src_path.read_text())
    banned_calls = {'clip', 'normalize', 'normalise', 'renormalise'}
    offences = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            nm = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else '')
            if nm in banned_calls:
                offences.append(f'{nm} at line {node.lineno}')
            if nm == 'open':
                mode = [a for a in node.args[1:]] + [
                    k.value for k in node.keywords if k.arg == 'mode']
                for a in mode:
                    if isinstance(a, ast.Constant) and 'r' not in str(a.value):
                        offences.append(f'open(mode={a.value!r}) line '
                                        f'{node.lineno}')
    check('no clip and no renormalisation anywhere in the module -- an '
          'invariant asserts, it does not repair', not offences,
          f'{offences}')
    # A subscript assignment is only legitimate here when it is building a
    # dict of results. Anything else is a write into a draw matrix, which is
    # the repair this module must never perform. The allow-set is stated by
    # NAME so that a new one has to be added deliberately.
    ACCUMULATORS = {'rec', 'team_of', 'e', 'out', 'ev'}
    writes = []
    for n in ast.walk(tree):
        targets = (n.targets if isinstance(n, ast.Assign)
                   else [n.target] if isinstance(n, ast.AugAssign) else [])
        for t in targets:
            if not isinstance(t, ast.Subscript):
                continue
            base = t.value
            nm = base.id if isinstance(base, ast.Name) else ast.dump(base)
            if nm not in ACCUMULATORS or isinstance(n, ast.AugAssign):
                writes.append(f'{nm} at line {n.lineno}')
    check('  the only subscript assignments are into result dictionaries -- '
          'nothing writes into a draw matrix, so no draw can be altered on '
          'the way through', not writes, f'{writes}')
    check('  and no in-place numpy mutator is called',
          not [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr in ('fill', 'put', 'itemset', 'resize',
                                   'sort', 'partition')])
    check('  the module names itself diagnostics-only in its own docstring',
          'DIAGNOSTICS ONLY' in (ast.get_docstring(tree) or '').upper())
    check('  there is exactly one function that touches a file, and it says '
          'so', (CN.from_run_dir.__doc__ or '').strip().startswith(
              'THE ONLY FUNCTION HERE THAT TOUCHES A FILE'))


def test_this_module_does_not_restate_a_hard_gate_as_a_second_verdict():
    """draw_coherence owns per-cell impossibility. Where a contract here
    covers the same rule, it must be CONTAINMENT (non-gating) and point at
    the owner -- never a second CLOSURE that could return a different answer."""
    same_rule = ('targets_within_throw_budget',
                 'qb_rush_opportunity_within_team_carries')
    for n in same_rule:
        check(f'  {n} is non-gating here',
              CN.CONTRACTS[n]['class'] == CN.CONTAINMENT)
    hard_here = [n for n in CN.CLOSURES
                 if 'HARD' in (CN.CONTRACTS[n].get('gated_elsewhere') or '')]
    for n in hard_here:
        check(f'  {n} restates a HARD identity and says where it is gated',
              'draw_coherence' in CN.CONTRACTS[n]['gated_elsewhere'])
    check('at least one closure defers its gate rather than owning it',
          len(hard_here) >= 3, f'{len(hard_here)}')


# ========================================== 8: the fence across every board
def test_every_sealed_board_is_scanned_and_matches_the_frozen_baseline():
    runs = _runs()
    check('sealed runs were found -- a scan over zero boards is not a clean '
          'scan', len(runs) == SEALED['runs'], f'{len(runs)}')
    if not runs:
        return
    n_team_runs = n_c3 = 0
    closure_fail = 0
    qb_cells = pl_cells = 0
    breach_tr = breach_cells = 0
    breach_games = set()
    rush_tr = rush_sign = 0
    stored_zero = stored_cells = 0
    for f in runs:
        o = CN.from_run_dir(f.parent)
        if o.state not in (State.PASS, State.FAIL):
            check(f'  {f.parent.name} produced a state the fence cannot '
                  f'score', False, f'{o.code}')
            continue
        ev = o.evidence
        n_team_runs += ev['n_teams']
        n_c3 += 1 if ev['regime'].get('C3') else 0
        game = f.parent.parts[-3]
        for r in ev['records']:
            if r.get('residual') is None:
                continue
            c, d = r['check'], r['residual']
            if r['state'] == 'FAIL':
                closure_fail += 1
            if c == 'team_dropback_partition':
                qb_cells += d['cells']
            if c == 'receptions_close_on_completions':
                pl_cells += d['cells']
            if c == 'qb_rush_opportunity_within_team_carries' \
                    and r['state'] == 'BREACHED':
                breach_tr += 1
                breach_cells += r['violating_cells']
                breach_games.add(game)
            if c == 'rush_opportunity_closes':
                rush_tr += 1
                rush_sign += 1 if d['sign_changes'] else 0
            if c == 'stored_team_targets_is_not_the_denominator':
                stored_zero += d['n_zero']
                stored_cells += d['cells']
    check('every team-run was scanned', n_team_runs == SEALED['team_runs'],
          f'{n_team_runs}')
    check('the C3 run count matches the declaration', n_c3 == SEALED['c3_runs'],
          f'{n_c3}')
    check('NO exact closure fails on any sealed board',
          closure_fail == SEALED['closure_failures'], f'{closure_fail}')
    check('  and the closures were evaluated over real cells, not zero',
          qb_cells == SEALED['qb_room_cells']
          and pl_cells == SEALED['passing_line_cells'],
          f'{qb_cells}/{pl_cells}')
    check('the QB-rush containment breach is fenced at its baseline -- it is '
          'a standing open item, not a regression',
          breach_tr == SEALED['containment_breaching_team_runs']
          and breach_cells == SEALED['containment_breaching_cells'],
          f'{breach_tr} team-runs / {breach_cells} cells')
    check('  and it is spread across games, so it is not one board\'s defect',
          len(breach_games) == SEALED['containment_breaching_games'],
          f'{sorted(breach_games)}')
    check('every board with a rushing layer carries an unowned rush residual',
          rush_tr == SEALED['rush_residual_team_runs'], f'{rush_tr}')
    check('  and every one of them changes sign across draws, so not one of '
          'them is described by its mean',
          rush_sign == SEALED['rush_residual_sign_changing_team_runs'],
          f'{rush_sign}')
    check('the stored team target total agrees with the C3 budget in ZERO '
          'draws, reproducing WS09 J-12 on 68 team-runs',
          stored_zero == SEALED['stored_target_exact_agreement_cells']
          and stored_cells == SEALED['stored_target_cells'],
          f'{stored_zero}/{stored_cells}')


def test_tonight_board_reproduces_the_hand_measurement():
    """The one-off this dashboard generalises. Every number below was measured
    by hand before the module existed; they are asserted so the generalisation
    cannot drift from what it generalised."""
    o = CN.from_run_dir(TONIGHT)
    check('tonight\'s sealed board measures', o.state is State.PASS,
          f'{o.code}')
    r = _rec(o, 'team_dropback_level_rounding_residual', 'DEN')
    check('  DEN team dropback budget 37.1858 against a QB room of 37.2230',
          abs(r['rhs_mean'] - 37.185768) < 5e-5
          and abs(r['lhs_mean'] - 37.2230) < 5e-5,
          f'{r["rhs_mean"]}/{r["lhs_mean"]}')
    r = _rec(o, 'team_dropback_level_rounding_residual', 'KC')
    check('  KC team dropback budget 41.46789 against a QB room of 41.4920',
          abs(r['rhs_mean'] - 41.46789) < 5e-5
          and abs(r['lhs_mean'] - 41.4920) < 5e-5,
          f'{r["rhs_mean"]}/{r["lhs_mean"]}')
    for t in ('DEN', 'KC'):
        r = _rec(o, 'team_dropback_partition', t)
        check(f'  {t} db == att + sacks + scr with max deviation 0',
              r['state'] == 'PASS' and r['residual']['mean_abs'] == 0.0)
    for name in ('target_opportunity_closes', 'rush_opportunity_closes',
                 'receptions_close_on_completions'):
        r = _rec(o, name, 'DEN')
        check(f'  DEN {name} is NOT_APPLICABLE, not zero mass',
              r['state'] == 'NOT_APPLICABLE' and r['residual'] is None)
    r = _rec(o, 'target_opportunity_closes', 'KC')
    check('  KC 33.4970 player targets against 35.4060 QB attempts, 1.9090 '
          'unowned', abs(r['rhs_mean'] - 33.4970) < 5e-5
          and abs(r['lhs_mean'] - 35.4060) < 5e-5
          and abs(r['residual']['mean'] - 1.9090) < 5e-5,
          f'{r["rhs_mean"]}/{r["lhs_mean"]}/{r["residual"]["mean"]}')
    check('    and the unowned target mass is named, not flagged',
          r['owner_stored'] is False
          and 'untargeted' in r['residual_owner']
          and 'not_a_defect' in r)
    r = _rec(o, 'receptions_close_on_completions', 'KC')
    check('  KC receptions 23.2780 == completions, deviation 0',
          abs(r['lhs_mean'] - 23.2780) < 5e-5
          and r['residual']['mean_abs'] == 0.0)
    r = _rec(o, 'receiving_yards_close_on_passing_yards', 'KC')
    check('  KC receiving yards 251.1770 == passing yards, deviation 0',
          abs(r['lhs_mean'] - 251.1770) < 5e-4
          and r['residual']['mean_abs'] < 1e-9)
    r = _rec(o, 'rush_opportunity_closes', 'KC')
    check('  KC 25.2449 carries = RB 19.5193 + QB scr 3.3060 + QB designed '
          '2.2640 + 0.1555 unowned',
          abs(r['lhs_mean'] - 25.2449) < 5e-5
          and abs(r['parts']['rb'] - 19.5193) < 5e-5
          and abs(r['parts']['qb_scramble'] - 3.3060) < 5e-5
          and abs(r['parts']['qb_designed'] - 2.2640) < 5e-5
          and abs(r['residual']['mean'] - 0.1555) < 5e-5,
          f'{r["parts"]}')
    check('    AND the 0.1555 mean hides a residual that is an '
          'over-allocation in 464 of 1000 draws',
          r['residual']['n_negative'] == 464
          and r['residual']['sign_changes'] is True
          and abs(r['residual']['sd'] - 3.9897) < 5e-4,
          f'{r["residual"]["n_negative"]}/{r["residual"]["sd"]}')
    r = _rec(o, 'qb_rush_opportunity_within_team_carries', 'KC')
    check('  the open item is surfaced: 6 breaching draws on KC',
          r['state'] == 'BREACHED' and r['violating_cells'] == 6,
          f'{r["state"]}/{r["violating_cells"]}')
    check('  and DEN does not breach, so the 6 of 2,000 figure is KC\'s',
          _rec(o, 'qb_rush_opportunity_within_team_carries', 'DEN')['state']
          == 'HELD')
    r = _rec(o, 'stored_team_targets_is_not_the_denominator', 'KC')
    check('  the stored KC team target total is 28.7035 against a dealt '
          'budget of 35.4060 -- the trap, as a number',
          abs(r['lhs_mean'] - 28.7035) < 5e-5
          and abs(r['rhs_mean'] - 35.4060) < 5e-5)


def test_the_absent_contracts_are_reported_on_every_board():
    o = CN.from_run_dir(TONIGHT)
    absent = {r['check'] for r in o.evidence['records']
              if r['state'] == 'ABSENT_CONTRACT'}
    check('every declared-but-unwritable contract is reported, not omitted',
          absent == set(CN.ABSENT_CONTRACTS), f'{sorted(absent)}')
    check('  including the two touchdown closures the artifact cannot express',
          {'team_rushing_td_closes', 'team_touchdowns_close'} <= absent)
    check('  and the two pool memberships whose owners are never sealed',
          {'team_target_pool_membership',
           'team_carry_category_membership'} <= absent)
    for r in o.evidence['records']:
        if r['state'] == 'ABSENT_CONTRACT':
            check(f'  {r["check"]} says what it WOULD assert and why it '
                  f'cannot', len(r['would_assert']) > 40
                  and len(r['why']) > 40)


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    raise SystemExit(1 if FAILED else 0)
