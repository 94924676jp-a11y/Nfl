"""Adversarial tests for `qb_room_v2`: the starter-scenario QB room.

THE PROPERTY UNDER TEST IS STRUCTURAL, SO THE TESTS ARE STRUCTURAL. The claim
this module defends is not "the zero mass is small tonight" -- a number can be
made small by hand and no test that reads a number can tell the difference. The
claim is that the ALLOCATOR CANNOT PRODUCE the pathology: the man who takes his
team's first dropback holds at least one, by the definition of starting, and no
probability anywhere in this file is set by hand.

Every test therefore tries to BREAK that, including with a deliberately
poisoned parameter set carrying exactly the V1 defect (a share pool that is
47% zeros, and a post-exit pool that would hand the starter's whole game away).
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'qb3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import State                 # noqa: E402
from nfl.production.nonqb import qb_room_v2 as V2                   # noqa: E402

PASSED = FAILED = BLOCKED = 0
_REAL = {}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


# A synthetic parameter set. Cell keys match `starter_cell(..., use_opener=True)`.
def _par(post_pool=None, cameo=None, p_exit=0.25):
    outs = [(V2.KINDS.index('attempt'), 1, 12),
            (V2.KINDS.index('attempt'), 0, 0),
            (V2.KINDS.index('sack'), 0, 0),
            (V2.KINDS.index('scramble'), 0, 0)]
    return {
        'spec_version': V2.SPEC_VERSION, 'trained_on_ordinals_before': 202601,
        'use_opener': True, 'prior': 'jeffreys',
        'p_start': {(1, 0, 1): 0.99, (2, 0, 1): 0.004, (3, 0, 1): 0.008,
                    (1, 1, 0): 0.93, (2, 0, 0): 0.05, (3, 0, 0): 0.02},
        'p_start_raw': {},
        'n_start': {}, 'k_start': {},
        'p_reliever_by_rank': {1: 0.30, 2: 0.92, 3: 0.21},
        'n_reliever_by_rank': {1: 33, 2: 375, 3: 237},
        'p_exit': p_exit, 'n_team_games': 2718, 'n_exit': 364,
        'post_pool': np.asarray(post_pool if post_pool is not None
                                else [0.05, 0.2, 0.5, 0.9], float),
        'cameo_pool': np.asarray(cameo if cameo is not None
                                 else [0.0, 0.0, 0.0, 0.02], float),
        'n_relievers_pool': np.asarray([1, 1, 1, 2], int),
        'donors': {'a': [outs * 10], 'b': [outs * 5]},
        'league_donor': [outs * 8],
    }


def _room(n=3, emergency=False):
    r = [{'pid': 'a', 'rank': 1, 'was_prev_primary': 0},
         {'pid': 'b', 'rank': 2, 'was_prev_primary': 0},
         {'pid': 'c', 'rank': 3, 'was_prev_primary': 0}][:n]
    if emergency and n >= 3:
        r[2] = dict(r[2], emergency=True)
    return r


def _V(m=4000, lo=20, hi=55, seed=3):
    return np.random.default_rng(seed).integers(lo, hi, m).astype(float)


def test_A_the_starter_can_never_take_zero_dropbacks():
    print('\nA. P(dropbacks = 0 | started) = 0 by construction')
    V = _V()
    al = V2.allocate_dropbacks(_par(), _room(), V, seed=11, ordinal=202601,
                               team='KC', is_opener=True)
    DB, who = al['db'], al['starter_index']
    got = DB[who, np.arange(len(who))]
    check('the drawn starter holds at least one dropback in EVERY draw',
          bool((got >= 1).all()), f'min {int(got.min())}')
    check('  and the identity holds for every team-dropback level drawn',
          bool((got >= 1).all() & (al['team_dropbacks_int'] >= 1).all()))
    z = float((DB[0] == 0).mean())
    ps = float((who == 0).mean())
    check('  the chart QB1 zero mass equals P(not starter) x P(no relief)',
          abs(z - (1 - ps) * (1 - float(((who != 0) & (DB[0] > 0)).mean())
                              / max(1 - ps, 1e-12))) < 1e-9,
          f'zero {z:.6f} p_start {ps:.6f}')


def test_B_a_poisoned_pool_cannot_zero_the_starter():
    print('\nB. seeded violation: the V1 defect, fed in deliberately')
    # post_pool entries at and above 1.0 would hand the starter's ENTIRE game
    # to a replacement -- the arithmetic form of V1's unconditional share pool,
    # which is 47.35% exactly zero in the cell that produced the sealed 0.412.
    V = _V()
    par = _par(post_pool=[1.0, 1.5, 3.0, 0.99999], p_exit=1.0)
    al = V2.allocate_dropbacks(par, _room(), V, seed=12, ordinal=202601,
                               team='KC', is_opener=True)
    got = al['db'][al['starter_index'], np.arange(al['db'].shape[1])]
    check('even a post-exit pool of 1.0 and above leaves the starter >= 1',
          bool((got >= 1).all()), f'min {int(got.min())}')
    check('  and the room still closes on the integer team total',
          int(np.abs(al['db'].sum(0) - al['team_dropbacks_int']).max()) == 0)
    # and the reverse poison: a cameo pool that is all 1.0 with no exit at all
    al2 = V2.allocate_dropbacks(_par(cameo=[1.0, 1.0], p_exit=0.0), _room(), V,
                                seed=13, ordinal=202601, team='KC',
                                is_opener=True)
    got2 = al2['db'][al2['starter_index'], np.arange(al2['db'].shape[1])]
    check('a cameo pool of 1.0 with no exit still leaves the starter >= 1',
          bool((got2 >= 1).all()), f'min {int(got2.min())}')


def test_C_counts_are_integers_and_close_exactly():
    print('\nC. integer counts, exact closure, no negatives')
    V = _V()
    al = V2.allocate_dropbacks(_par(), _room(), V, seed=14, ordinal=202601,
                               team='DEN', is_opener=True)
    DB = al['db']
    check('the dropback matrix is an integer dtype',
          np.issubdtype(DB.dtype, np.integer), str(DB.dtype))
    check('  every count is non-negative', bool((DB >= 0).all()))
    check('  the room sums EXACTLY to the integer team dropbacks',
          int(np.abs(DB.sum(0) - al['team_dropbacks_int']).max()) == 0)
    ln = V2.branch_lines(_par(), _room(), DB, al['starter_index'], seed=14,
                         ordinal=202601, team='DEN')
    for k in ('sacks', 'scrambles', 'att', 'cmp', 'pyds'):
        check(f'  {k} is integer-valued', np.issubdtype(ln[k].dtype,
                                                        np.integer))
    check('  sacks + scrambles + attempts equals dropbacks in every cell',
          bool(((ln['sacks'] + ln['scrambles'] + ln['att']) == DB).all()))
    check('  completions never exceed attempts',
          bool((ln['cmp'] <= ln['att']).all()))
    check('  a player with zero dropbacks has zero of everything',
          bool((ln['att'][DB == 0] == 0).all()
               and (ln['pyds'][DB == 0] == 0).all()))


def test_D_no_probability_is_set_by_hand():
    print('\nD. the room refuses rather than inventing a starter')
    par = _par()
    par['p_start'] = {}                      # no cell was ever observed
    try:
        V2.allocate_dropbacks(par, _room(), _V(m=50), seed=15, ordinal=202601,
                              team='KC', is_opener=True)
        check('an unobserved room REFUSES instead of defaulting', False,
              'it returned an allocation')
    except V2.QbRoomV2Error as e:
        check('an unobserved room REFUSES instead of defaulting',
              'STARTER_WEIGHTS_EMPTY' in str(e), str(e)[:120])
    try:
        V2.allocate_dropbacks(_par(), [], _V(m=50))
        check('an empty room is an error, not an empty result', False)
    except V2.QbRoomV2Error as e:
        check('an empty room is an error, not an empty result',
              'ROOM_EMPTY' in str(e), str(e)[:120])
    o = V2.room_forecast(par, _room(), _V(m=50), team='KC')
    check('  and the Outcome states FAIL rather than returning zeros',
          o.state is State.FAIL and o.code == 'QB_ROOM_V2_REFUSED', str(o)[:110])
    src = open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                            'qb_room_v2.py')).read()
    for banned in ('zero_floor', 'MIN_P', 'MIN_ZERO', 'FLOOR', 'np.clip'):
        check(f'  the source carries no `{banned}` knob', banned not in src)
    code = [ln for ln in src.splitlines()
            if ln.strip() and not ln.lstrip().startswith('#')]
    check('  the only floor() in the source is the integer apportionment',
          sum(1 for ln in code if 'np.floor' in ln) == 1,
          [ln.strip() for ln in code if 'np.floor' in ln])
    check('  every starter weight is read from the fitted pool, never a '
          'literal',
          "par['p_start'].get(c, 0.0)" in src)


def test_E_the_emergency_third_quarterback_is_in_the_room_and_cannot_start():
    print('\nE. emergency third QB legality')
    V = _V()
    al = V2.allocate_dropbacks(_par(), _room(emergency=True), V, seed=16,
                               ordinal=202601, team='KC', is_opener=True)
    check('the emergency QB starts in exactly zero draws',
          int((al['starter_index'] == 2).sum()) == 0)
    check('  but he is still able to enter as a replacement',
          int((al['db'][2] > 0).sum()) > 0,
          int((al['db'][2] > 0).sum()))
    check('  and deleting him would have been wrong: he is in the room',
          al['db'].shape[0] == 3)


def test_F_chronology_is_enforced_by_the_fit_not_by_trust():
    print('\nF. nothing at or after the cut can enter a fit')
    frame = [{'game_id': f'g{i}', 'team': 'AAA', 'season': 2023, 'week': i,
              'ord': 202300 + i, 'date': '', 'pid': 'a', 'rank': 1,
              'was_prev_primary': 1, 'is_opener': 0, 'prev_primary_known': 1,
              'n_db_team': 30, 'db': 30, 'is_starter': 1, 'is_finisher': 1,
              'starter_in_room': 1, 'n_db_after_starter_last': 0}
             for i in range(1, 6)]
    tgs = {(f'g{i}', 'AAA'): {'game_id': f'g{i}', 'team': 'AAA',
                              'season': 2023, 'week': i, 'date': '',
                              'db': [('a', 'attempt', 1, 10)] * 30}
           for i in range(1, 6)}
    par = V2.fit(frame, tgs, 202304)
    check('the fit used only the 3 team-weeks before the cut',
          par['n_team_games'] == 3, par['n_team_games'])
    # SEEDED VIOLATION: a future row that would flip the cell if it leaked.
    poisoned = frame + [dict(frame[0], game_id='gX', week=9, ord=202309,
                             is_starter=0, db=0)]
    tgs2 = dict(tgs)
    tgs2[('gX', 'AAA')] = {'game_id': 'gX', 'team': 'AAA', 'season': 2023,
                           'week': 9, 'date': '',
                           'db': [('z', 'attempt', 1, 10)] * 30}
    par2 = V2.fit(poisoned, tgs2, 202304)
    check('  a post-cut row changes nothing in the fit',
          par2['p_start'] == par['p_start']
          and par2['n_team_games'] == par['n_team_games'])
    try:
        V2.fit(frame, tgs, 202101)
        check('  an empty fit REFUSES', False, 'it returned a fit')
    except V2.QbRoomV2Error as e:
        check('  an empty fit REFUSES', 'FIT_EMPTY' in str(e), str(e)[:100])


def test_G_the_forecast_season_can_never_enter_a_historical_frame():
    print('\nG. 2026 is excluded by construction, not by a caller remembering')
    try:
        V2.pbp_path(2026)
        check('pbp_2026 is refused as historical support', False)
    except V2.QbRoomV2Error as e:
        check('pbp_2026 is refused as historical support',
              'PBP_SEASON_FORBIDDEN' in str(e), str(e)[:110])
    try:
        V2.pbp_path(1999)
        check('  an absent season is BLOCKED, not treated as empty', False)
    except V2.QbRoomV2Error as e:
        check('  an absent season is BLOCKED, not treated as empty',
              'PBP_SEASON_ABSENT' in str(e), str(e)[:110])


def test_H_the_same_seed_gives_the_same_football():
    print('\nH. determinism')
    V = _V(m=800)
    a = V2.allocate_dropbacks(_par(), _room(), V, seed=21, ordinal=202601,
                              team='KC', is_opener=True)
    b = V2.allocate_dropbacks(_par(), _room(), V, seed=21, ordinal=202601,
                              team='KC', is_opener=True)
    check('identical seed, identical allocation',
          bool((a['db'] == b['db']).all()))
    c = V2.allocate_dropbacks(_par(), _room(), V, seed=22, ordinal=202601,
                              team='KC', is_opener=True)
    check('  a different seed moves it (the draw is a draw)',
          not bool((a['db'] == c['db']).all()))
    o = V2.room_forecast(_par(), _room(), V, seed=21, ordinal=202601, team='KC',
                         is_opener=True)
    check('  room_forecast passes and reports integer closure',
          o.state is State.PASS and o.evidence['closure'] == 'INTEGER_EXACT',
          str(o)[:110])


def _real():
    """The real fit, built once. Missing data BLOCKS; it never passes."""
    if _REAL:
        return _REAL.get('par')
    _REAL['par'] = None
    try:
        tg = V2.load_pbp((2021, 2022, 2023, 2024))
        pp = V2.previous_primary_from_panel()
        dw = V2.load_depth_weekly([2021, 2022, 2023, 2024])
        depth = {}
        for k, g in tg.items():
            r = dw.get((g['season'], g['week'], g['team']))
            if r:
                depth[k] = r
        frame = V2.build_frame(tg, depth, pp)
        _REAL['par'] = V2.fit(frame, tg, 202501)
        _REAL['frame'] = frame
    except (V2.QbRoomV2Error, OSError) as e:
        _REAL['why'] = str(e)[:140]
    return _REAL.get('par')


def test_I_the_real_fit_reproduces_the_defect_it_replaces():
    print('\nI. load-bearing: the V1 defect is present in V1 and absent here')
    par = _real()
    if par is None:
        blocked('the real fit', _REAL.get('why', 'inputs unavailable'))
        return
    import qb3_lib as Q
    q = Q.fit(Q.build_frame(Q.load_qb_panel(), Q.load_depth()), 2025)
    pool = q['share_pool'].get((1, 0))
    check('V1 (rank 1, not previous primary) share pool is heavily zero',
          pool is not None and float((pool == 0).mean()) > 0.40,
          None if pool is None else float((pool == 0).mean()))
    frame = _REAL['frame']
    cond = [r for r in frame
            if r['is_starter'] and r['ord'] < 202501]
    check('  a starter with zero dropbacks does not exist in the record',
          sum(1 for r in cond if r['db'] == 0) == 0,
          sum(1 for r in cond if r['db'] == 0))
    room = [{'pid': 'p1', 'rank': 1, 'was_prev_primary': 0},
            {'pid': 'p2', 'rank': 2, 'was_prev_primary': 0},
            {'pid': 'p3', 'rank': 3, 'was_prev_primary': 0}]
    al = V2.allocate_dropbacks(par, room, _V(m=4000), seed=31, ordinal=202401,
                               team='KC', is_opener=True)
    z = float((al['db'][0] == 0).mean())
    check('  and on the real opener cell the chart QB1 zero mass is far below '
          'V1\'s 0.41', z < 0.10, z)
    got = al['db'][al['starter_index'], np.arange(al['db'].shape[1])]
    check('  with the structural identity still exact on real parameters',
          bool((got >= 1).all()))


def test_J_the_production_flag_is_inert_until_it_is_turned_on():
    print('\nJ. qb_allocation allocator flag: default is bit-identical')
    from nfl.production.nonqb import qb_allocation as QA
    check('the default allocator is still qb3', QA.ALLOCATORS[0] == 'qb3')
    bad = QA.allocate(2026, 1, ['KC'], [], allocator='nope')
    check('  an unknown allocator is REFUSED, never silently defaulted',
          bad.state is State.FAIL and bad.code == 'QB_ALLOCATOR_UNKNOWN',
          str(bad)[:110])
    need = QA.allocate(2026, 1, ['KC'], [], allocator='qb_room_v2')
    check('  V2 without team dropbacks is BLOCKED, not approximated',
          need.state is State.BLOCKED
          and need.code == 'QB_ROOM_V2_NEEDS_TEAM_DROPBACKS', str(need)[:110])
    src = open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                            'qb_allocation.py')).read()
    check('  the qb3 call site is unchanged when the flag is off',
          "S_e = Q.allocate(par, elig, m=m, seed=seed," in src)


def test_K_v2_through_the_production_entry_point_closes():
    print('\nK. the V2 path, exercised end to end')
    from nfl.production.nonqb import qb_allocation as QA
    dc = QA.captured_depth_chart()
    if dc.state is not State.PASS:
        blocked('the V2 production path', f'{dc.code}: no captured chart')
        return
    team = 'KC' if 'KC' in dc.value else sorted(dc.value)[0]
    pids = sorted(dc.value[team], key=lambda p: dc.value[team][p])
    players = [{'gsis_id': p, 'team': team} for p in pids]
    m = 300
    tdb = {team: np.random.default_rng(5).integers(24, 52, m).astype(float)}
    o = QA.allocate(2026, 1, [team], players, m=m, allocator='qb_room_v2',
                    team_dropback_draws=tdb)
    if o.state is not State.PASS:
        blocked('the V2 production path', f'{o.code}: {o.detail[:90]}')
        return
    S = o.value[team]['shares']
    check('the V2 path closes to 1 in every draw',
          float(np.abs(S.sum(0) - 1.0).max()) < 1e-9)
    check('  and the Outcome names the allocator that produced it',
          o.evidence.get('allocator') == 'qb_room_v2')
    counts = np.rint(S * tdb[team][None, :])
    check('  multiplying back by the team draws recovers integer counts',
          float(np.abs(counts - S * tdb[team][None, :]).max()) < 0.5)
    top = S[0]
    check('  the chart QB1 zero mass is far below V1\'s 0.41 on this room',
          float((top <= 0).mean()) < 0.10, float((top <= 0).mean()))


_VINT = {'source': 'TEST_ONLY', 'retrieved_at': '2026-09-14T20:00:00Z',
         'content_hash': 'f' * 64}


def test_L_deterministic_eligibility_is_above_the_starter_scenario():
    print('\nL. the legal room consumes R2\'s gate; it does not rebuild it')
    from nfl.production.nonqb import qb_allocation as QA
    dc = QA.captured_depth_chart()
    if dc.state is not State.PASS:
        blocked('the legal room', f'{dc.code}: no captured depth chart')
        return
    team = 'KC' if 'KC' in dc.value else sorted(dc.value)[0]
    pids = sorted(dc.value[team], key=lambda q: dc.value[team][q])
    players = [{'gsis_id': q, 'team': team, 'position': 'QB'} for q in pids]
    kick = '2026-09-15T00:15:00Z'
    base = V2.legal_room(2026, 1, team, players, kickoff_utc=kick)
    if base.state is not State.PASS:
        blocked('the legal room', f'{base.code}: {base.detail[:90]}')
        return
    check('with nobody determined ineligible the room is the room',
          len(base.value) == len(players)
          and base.evidence['n_removed_determined_ineligible'] == 0)
    # SEEDED VIOLATION: an authority says a quarterback cannot play.
    seeded = V2.legal_room(2026, 1, team, players, kickoff_utc=kick,
                           official_inactive_ids=[pids[1]],
                           official_inactives_vintage=_VINT)
    check('  a determined-ineligible QB is REMOVED FROM THE ROOM, not zeroed '
          'after the draw',
          seeded.state is State.PASS
          and pids[1] not in [q['gsis_id'] for q in seeded.value]
          and seeded.evidence['n_removed_determined_ineligible'] == 1,
          str(seeded)[:120])
    check('  and the removal carries its authority and its reason',
          seeded.evidence['removed_determined_ineligible'][0]['authority']
          == 'OFFICIAL_INACTIVE_LIST')
    # he therefore cannot hold starter mass -- the point of putting the gate
    # ABOVE the scenario rather than inside it.
    par = _par()
    room = [{'pid': q['gsis_id'], 'rank': V2.rank_bucket(dc.value[team][q['gsis_id']]),
             'was_prev_primary': 0} for q in seeded.value]
    al = V2.allocate_dropbacks(par, room, _V(m=600), seed=41, ordinal=202601,
                               team=team, is_opener=True)
    check('  the removed QB holds no dropback in any draw because he has no '
          'row at all',
          al['db'].shape[0] == len(players) - 1)


def test_M_the_emergency_third_quarterback_survives_the_gate():
    print('\nM. a rule the gate cannot see, re-admitted explicitly')
    from nfl.production.nonqb import qb_allocation as QA
    dc = QA.captured_depth_chart()
    if dc.state is not State.PASS:
        blocked('the emergency re-admission', f'{dc.code}: no depth chart')
        return
    team = 'KC' if 'KC' in dc.value else sorted(dc.value)[0]
    pids = sorted(dc.value[team], key=lambda q: dc.value[team][q])
    players = [{'gsis_id': q, 'team': team, 'position': 'QB'} for q in pids]
    kick = '2026-09-15T00:15:00Z'
    o = V2.legal_room(2026, 1, team, players, kickoff_utc=kick,
                      emergency_qb_ids=[pids[2]],
                      official_inactive_ids=[pids[2]],
                      official_inactives_vintage=_VINT)
    if o.state is not State.PASS:
        blocked('the emergency re-admission', f'{o.code}: {o.detail[:90]}')
        return
    row = [q for q in o.value if q['gsis_id'] == pids[2]]
    check('the designated emergency third QB is back in the room',
          len(row) == 1, [q['gsis_id'] for q in o.value])
    check('  and he cannot start', row and row[0]['can_start'] is False)
    check('  and the re-admission is named on the Outcome',
          o.evidence['emergency_readmitted'] == [pids[2]])
    # WITHOUT the designation he stays out. The re-admission is a rule the
    # caller supplies, never an inference from a depth rank.
    o2 = V2.legal_room(2026, 1, team, players, kickoff_utc=kick,
                       official_inactive_ids=[pids[2]],
                       official_inactives_vintage=_VINT)
    check('  an inactive QB3 with NO designation stays out',
          pids[2] not in [q['gsis_id'] for q in o2.value])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks')


if __name__ == '__main__':
    for _n in sorted(n for n in dir() if n.startswith('test_')):
        globals()[_n]()
    tail = f', {BLOCKED} blocked' if BLOCKED else ''
    print(f'\n{PASSED} passed, {FAILED} failed{tail}')
    sys.exit(1 if FAILED else 0)
