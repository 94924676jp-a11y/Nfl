"""Stage-0 eligibility gate: the ineligible never enter the choice set.

THE INVARIANT IS READ OFF THE DRAWS, NOT OFF A FLAG

A test that asserts `snapshot.evidence['n_determined_ineligible'] == 14` proves
the gate can count. It proves nothing about opportunity, because the number and
the matrices are produced by different code and only one of them reaches a
board. Every claim here that a player holds zero is made by reading his cells,
or by proving he has no cells to read.

AND THE CHECKER HAS TO BITE

`assert_zero_opportunity_over_draws` is run against draws that DO carry a
positive row for the player it is told is ineligible, and it must FAIL. A guard
that only ever sees compliant data is not a demonstrated guard (repo rule 4).
"""
from __future__ import annotations

import csv
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_P4C = os.path.join(_ROOT, 'nfl', 'research', 'p4c')
if _P4C not in sys.path:
    sys.path.insert(0, _P4C)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import eligibility_gate as EG                    # noqa: E402
from nfl.production.nonqb import layers as LY                        # noqa: E402

PASSED = FAILED = 0

KICKOFF = '2026-09-15T00:15:00Z'
CUTOFF = '2026-09-14T18:00:00Z'
TEAMS = ('DEN', 'KC')
SEASON, WEEK = 2026, 1
SKILL = {'QB', 'RB', 'WR', 'TE', 'FB'}

ROSTER_PREKICK = pathlib.Path(_ROOT) / 'nfl_vintage' / 'raw' / \
    'weekly_rosters.bdab6ecee12d44a4.csv'
# The last roster capture taken before the 1 PM week-1 kickoffs. ATL and PIT
# have played since, and `roster_status` REFUSES the newer file for them
# (ROSTER_STATUS_POSTHOC_CONTAMINATION) because the vendor re-partitions ACT
# after a game. The historical replay therefore has to use the pre-kickoff
# capture, which is the guard working rather than an inconvenience.
ROSTER_W1_AM = pathlib.Path(_ROOT) / 'nfl_vintage' / 'raw' / \
    'weekly_rosters.cef497eaeddef07b.csv'

SEALED = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live' / \
    '2026_01_DEN_KC' / 'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8' / \
    'f91342d6787a66a1'

ATL_QB1 = '00-0036212'          # listed Out on the week-1 injury report
KELCE = '00-0030506'            # in the sealed receiving draws, positive mass


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _pool(path, teams, positions=SKILL):
    out = []
    with open(path, 'rt') as fh:
        for r in csv.DictReader(fh):
            if (r.get('season') == str(SEASON) and r.get('week') == str(WEEK)
                    and r.get('team') in teams
                    and r.get('position') in positions
                    and r.get('gsis_id')):
                out.append({'gsis_id': r['gsis_id'], 'team': r['team'],
                            'position': r['position'],
                            'name': (r.get('full_name') or '').strip()})
    return out


# ============================================================ the snapshot
def test_snapshot_is_audited_row_by_row():
    players = _pool(ROSTER_PREKICK, TEAMS)
    if not check('the DEN/KC skill pool is non-empty', len(players) > 20,
                 f'n={len(players)}'):
        return
    snap = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                       kickoff_utc=KICKOFF, observed_before=CUTOFF,
                       game_id='2026_01_DEN_KC')
    if not check('the snapshot builds', snap.state is State.PASS,
                 f'{snap.code}: {snap.detail[:200]}'):
        return
    need = ('status', 'determination', 'authority', 'source_vintage',
            'content_hash', 'known_from', 'reason', 'simulation_eligibility')
    missing = {k for r in snap.value.values() for k in need if k not in r}
    check('every row carries the full schema', not missing, str(sorted(missing)))
    check('  one row per player, none dropped',
          len(snap.value) == len(players),
          f'{len(snap.value)} vs {len(players)}')
    # THE THREE STATES STAY THREE.
    dets = {r['determination'] for r in snap.value.values()}
    check('  determination is only determined/uncertain',
          dets <= {EG.DETERMINED, EG.UNCERTAIN}, str(sorted(dets)))
    check('  a determined row is never left in the choice set',
          all(r['simulation_eligibility'] == EG.EXCLUDED_DETERMINISTIC
              for r in snap.value.values()
              if r['determination'] == EG.DETERMINED))
    # DEV IS NOT A DETERMINATION OF INELIGIBILITY.
    dev = [r for r in snap.value.values() if r['status'] == 'ROSTER_DEV']
    if check('  practice-squad rows exist to test', bool(dev), 'none'):
        check('  DEV is uncertain, not determined',
              all(r['determination'] == EG.UNCERTAIN for r in dev))
        check('  and is removed under its own named pool rule',
              all(r['simulation_eligibility'] == EG.EXCLUDED_BY_POOL_RULE
                  for r in dev))
    # Provenance, not adjectives.
    det = [r for r in snap.value.values()
           if r['simulation_eligibility'] == EG.EXCLUDED_DETERMINISTIC]
    check('  every determined exclusion carries a content hash',
          all(r['content_hash'] for r in det))
    check('  and an authority with a rank',
          all(r['authority'] and r['authority_rank'] for r in det))


def test_no_inactive_list_is_recorded_as_ignorance_not_as_nobody_out():
    """`official_inactive_ids=None` and `()` are different facts."""
    players = _pool(ROSTER_PREKICK, TEAMS)
    a = EG.snapshot(SEASON, WEEK, list(TEAMS), players, kickoff_utc=KICKOFF,
                    observed_before=CUTOFF, official_inactive_ids=None)
    b = EG.snapshot(SEASON, WEEK, list(TEAMS), players, kickoff_utc=KICKOFF,
                    observed_before=CUTOFF, official_inactive_ids=())
    if not check('both snapshots build',
                 a.state is State.PASS and b.state is State.PASS,
                 f'{a.code}/{b.code}'):
        return
    check('no list -> gameday activity UNRESOLVED',
          a.evidence['gameday_activity'] == 'UNRESOLVED',
          a.evidence['gameday_activity'])
    check('an empty list that was READ -> RESOLVED',
          b.evidence['gameday_activity'] == 'RESOLVED',
          b.evidence['gameday_activity'])
    check('  and only the first refuses to call the board final',
          a.evidence['board_finality'].startswith('PRELIMINARY_PROVISIONAL')
          and not b.evidence['board_finality'].startswith('PRELIM'))
    check('  the unresolved note is written on the rows themselves',
          any('unresolved_note' in r for r in a.value.values())
          and not any('unresolved_note' in r for r in b.value.values()))


def test_a_posthoc_roster_status_is_refused_not_used():
    """Seeded violation: INA is a gameday OUTCOME and must never govern."""
    players = _pool(ROSTER_PREKICK, TEAMS)[:5]
    import nfl.production.nonqb.roster_status as RS
    real = RS.status_map

    def poisoned(*a, **k):
        o = real(*a, **k)
        if o.state is State.PASS:
            o.value[players[0]['gsis_id']] = 'INA'
        return o
    RS.status_map = poisoned
    try:
        o = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                        kickoff_utc=KICKOFF, observed_before=CUTOFF)
    finally:
        RS.status_map = real
    check('an INA status is refused by name',
          o.state is State.FAIL and o.code == 'ELIGIBILITY_POSTHOC_STATUS',
          f'{o.state.value}[{o.code}]')


def test_equal_rank_disagreement_refuses():
    """Two rank-2 statements that disagree have no declared tiebreak."""
    players = _pool(ROSTER_PREKICK, TEAMS)[:6]
    pid = players[0]['gsis_id']
    real = EG.injury_designations

    def designate(*a, **k):
        o = real(*a, **k)
        if o.state is State.PASS:
            o.value[pid] = {'report_status': 'Questionable', 'team': 'KC',
                            'practice_status': '', 'full_name': 'x',
                            'report_primary_injury': ''}
        return o
    EG.injury_designations = designate
    try:
        o = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                        kickoff_utc=KICKOFF, observed_before=CUTOFF,
                        suspensions={pid: 'seeded conflict'})
    finally:
        EG.injury_designations = real
    check('equal-rank conflict is a refusal, not a silent precedence',
          o.state is State.FAIL
          and o.code == 'ELIGIBILITY_AUTHORITY_CONFLICT',
          f'{o.state.value}[{o.code}]')


def test_an_empty_injury_slice_is_an_error_not_a_clean_bill():
    o = EG.injury_designations(SEASON, WEEK, ['XXX'], kickoff_utc=KICKOFF,
                               observed_before=CUTOFF)
    check('zero rows in scope refuses rather than returning {}',
          o.state is State.BLOCKED
          and o.code == 'ELIGIBILITY_INJURY_SLICE_EMPTY',
          f'{o.state.value}[{o.code}]')


def test_a_blank_designation_is_not_a_clearance():
    o = EG.injury_designations(SEASON, WEEK, list(TEAMS), kickoff_utc=KICKOFF,
                               observed_before=CUTOFF)
    if not check('designations read', o.state is State.PASS, o.code):
        return
    scan = o.evidence['non_vocabulary_or_blank']
    check('blank rows are counted, not silently dropped',
          scan.get('BLANK', 0) > 0, str(scan))
    check('  and no blank row became a status',
          all(v['report_status'] in ('Out', 'Doubtful', 'Questionable')
              for v in o.value.values()))


# ========================================================== the choice set
def test_choice_set_removes_the_determined_and_names_every_removal():
    players = _pool(ROSTER_PREKICK, TEAMS)
    snap = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                       kickoff_utc=KICKOFF, observed_before=CUTOFF)
    cs = EG.choice_set(players, snap)
    if not check('the choice set builds', cs.state is State.PASS,
                 f'{cs.code}: {cs.detail[:200]}'):
        return
    kept = {q['gsis_id'] for q in cs.value}
    det = set(snap.evidence['determined_ineligible'])
    check('no determined-ineligible player is in the choice set',
          not (kept & det), str(sorted(kept & det)[:5]))
    check('  every removal is itemised with its authority',
          all(r['authority'] and r['reason']
              for r in cs.evidence['removed_determined_ineligible']))
    check('  the two kinds of removal are reported apart',
          (cs.evidence['n_removed_determined_ineligible']
           + cs.evidence['n_removed_by_pool_rule']
           + cs.evidence['n_kept']) == len(players))


def test_a_player_the_snapshot_never_saw_is_refused():
    players = _pool(ROSTER_PREKICK, TEAMS)
    snap = EG.snapshot(SEASON, WEEK, list(TEAMS), players[:10],
                       kickoff_utc=KICKOFF, observed_before=CUTOFF)
    cs = EG.choice_set(players, snap)
    check('a partly-governed pool is refused, not partly governed',
          cs.state is State.FAIL
          and cs.code == 'CHOICE_SET_PLAYER_NOT_IN_SNAPSHOT',
          f'{cs.state.value}[{cs.code}]')


# ======================================== the invariant, over REAL draws
def _sealed():
    man = json.loads((SEALED / 'player_draws_manifest.json').read_text())
    arrays = EG.load_draw_arrays(str(SEALED / 'player_draws.npz'))
    return man, arrays


def test_tonights_determined_ineligible_hold_zero_in_every_stored_draw():
    if not check('the sealed draw artifact exists',
                 (SEALED / 'player_draws.npz').exists(), str(SEALED)):
        return
    man, arrays = _sealed()
    players = _pool(ROSTER_PREKICK, TEAMS)
    snap = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                       kickoff_utc=KICKOFF, observed_before=CUTOFF)
    det = snap.evidence['determined_ineligible']
    if not check('there is a determined-ineligible set to check', bool(det)):
        return
    o = EG.assert_zero_opportunity_over_draws(man['layers'], arrays, det)
    if not check('the invariant holds on the sealed board',
                 o.state is State.PASS, f'{o.code}: {o.detail[:300]}'):
        return
    check(f'  {o.evidence["n_players_checked"]} player(s), '
          f'{o.evidence["n_row_slots_scanned"]} row slot(s) scanned',
          o.evidence['n_row_slots_scanned'] > 0)
    check('  every one is ABSENT from every player-axis layer',
          o.evidence['n_absent_from_every_layer']
          == o.evidence['n_players_checked'],
          str(o.evidence['n_absent_from_every_layer']))
    check('  so zero cells were read, and that number is reported',
          o.evidence['n_cells_read'] == 0
          and 'zero_cells_read_means' in o.evidence)


def test_the_invariant_checker_fails_on_a_seeded_violation():
    """THE LOAD-BEARING TEST. Told a player with positive stored mass is
    ineligible, the checker must FAIL, and it must do so from the cells."""
    if not (SEALED / 'player_draws.npz').exists():
        return
    man, arrays = _sealed()
    o = EG.assert_zero_opportunity_over_draws(man['layers'], arrays, [KELCE])
    if not check('the checker refuses',
                 o.state is State.FAIL and o.code == 'ZERO_OPPORTUNITY_VIOLATED',
                 f'{o.state.value}[{o.code}]'):
        return
    check('  and it read real cells to do it',
          o.evidence['n_cells_read'] > 0, str(o.evidence['n_cells_read']))
    check('  naming the layer, metric and how many draws are non-zero',
          all({'layer', 'metric', 'n_nonzero_draws'} <= set(v)
              for v in o.evidence['violations']))


def test_a_check_with_no_player_axis_is_not_a_pass():
    man, arrays = _sealed()
    only_team = {k: v for k, v in man['layers'].items()
                 if v.get('row_axis') == 'team'}
    o = EG.assert_zero_opportunity_over_draws(only_team, arrays, [KELCE])
    check('team-axis-only layers refuse rather than return a vacuous green',
          o.state is State.FAIL
          and o.code == 'ZERO_OPPORTUNITY_NO_PLAYER_AXIS',
          f'{o.state.value}[{o.code}]')


def test_an_empty_ineligible_set_is_blocked_not_passed():
    man, arrays = _sealed()
    o = EG.assert_zero_opportunity_over_draws(man['layers'], arrays, [])
    check('nothing to check is BLOCKED, never PASS',
          o.state is State.BLOCKED
          and o.code == 'ZERO_OPPORTUNITY_NOTHING_TO_CHECK',
          f'{o.state.value}[{o.code}]')


# ============ the defect is live: allocate-then-zero vs never-allocate
_M = 128


def _chain(pool, inactive_ids=None):
    """appearance -> participation -> allocation, on a marked TEST-ONLY
    fixture. The P4C residual pools here are SYNTHETIC and labelled so: this
    proves wiring and ordering, not a fitted allocation."""
    rng = np.random.default_rng(11)
    par = {'add_pool': {p: rng.normal(0, 0.05, 400).astype(np.float32)
                        for p in ('WR', 'TE', 'RB')},
           'mass_pool': rng.uniform(0.05, 0.25, 500).astype(np.float32)}
    fx = {'_test_only': True, 'practice_progression': True,
          'teammate_availability': True,
          'p_appear': {q['gsis_id']: 0.9 for q in pool}}
    ap = LY.appearance(SEASON, WEEK, pool, fixture=fx, m=_M,
                       game_id='2026_01_DEN_KC')
    if ap.state is not State.PASS:
        return ap, None, None
    # ALLOCATE-THEN-ZERO, USING PRODUCTION'S OWN FUNCTION.
    #
    # `layers._run_real` (layers.py:234-239) applies the inactive list by
    # calling exactly this, on already-drawn appearance Bernoullis. Calling it
    # here is the same operation at the same point in the chain.
    #
    # It is called directly rather than through `layers.appearance(
    # inactive_ids=...)` because the SHAPE-ONLY fixture branch (layers.py:165-
    # 178) never reaches `_run_real` and therefore ignores `inactive_ids`
    # entirely -- measured here, and reported in R2_ELIGIBILITY_GATE.md. That
    # branch cannot reach an artifact, so it is a test-path gap and not a
    # production defect, but a test that used it would have been proving
    # nothing.
    if inactive_ids:
        from nfl.production.nonqb import inactives as INA
        zo = INA.apply_to_appearance(ap.value, inactive_ids)
        if zo.state is not State.PASS:
            return zo, None, None
        ap = ap.__class__.ok('APPEARANCE_OK', value=zo.value,
                             test_only=True,
                             detail='inactives applied after the draw')
    pa = LY.participation(ap, {q['gsis_id']: 0.2 for q in pool}, m=_M)
    if pa.state is not State.PASS:
        return ap, pa, None
    ids = [q['gsis_id'] for q in pool]
    pos = [q['position'] for q in pool]
    kc = [i for i, q in enumerate(pool) if q['team'] == 'KC']
    den = [i for i, q in enumerate(pool) if q['team'] == 'DEN']
    order = kc + den
    ids = [ids[i] for i in order]
    pos = [pos[i] for i in order]
    starts = np.array([0, len(kc)], np.int64)
    counts = np.array([len(kc), len(den)], np.int64)
    tc = LY.targets_carries(pa, 'targets', [0.15] * len(ids), pos,
                            (starts, counts), ids, par, m=_M,
                            game_id='2026_01_DEN_KC', ordinal=1)
    return ap, pa, (tc, ids)


def _synth_pool(n_kc=6, n_den=6):
    out = []
    for t, n, base in (('KC', n_kc, 1), ('DEN', n_den, 2)):
        for i in range(n):
            out.append({'gsis_id': f'00-00{base}90{i:02d}', 'team': t,
                        'position': ('WR', 'TE', 'RB')[i % 3]})
    return out


def test_allocate_then_zero_leaves_the_choice_set_unchanged():
    """The measured shape of the defect, reproduced on demand.

    D7 measured `n_pre_only_rows = 0` and `n_post_only_rows = 0` across the
    four games with both seals: applying the inactive list moves numbers and
    moves nobody out of the pool. This reproduces that directly.
    """
    pool = _synth_pool()
    out_pid = pool[0]['gsis_id']
    ap0, _, a0 = _chain(pool)
    ap1, _, a1 = _chain(pool, inactive_ids=[out_pid])
    if not check('both chains run',
                 a0 is not None and a1 is not None
                 and a0[0].state is State.PASS and a1[0].state is State.PASS,
                 f'{ap0.code}/{ap1.code}'):
        return
    S0, ids0 = a0[0].value['share'], a0[1]
    S1, ids1 = a1[0].value['share'], a1[1]
    check('the pool is identical with and without the inactive list',
          ids0 == ids1 and S0.shape == S1.shape,
          f'{S0.shape} vs {S1.shape}')
    i = ids1.index(out_pid)
    check('  the inactive player is still a ROW, merely zeroed',
          out_pid in ids1 and float(np.abs(S1[i]).max()) == 0.0,
          str(float(np.abs(S1[i]).max())))
    check('  and he held strictly positive mass before it was applied',
          int(np.count_nonzero(S0[i])) > 0,
          str(int(np.count_nonzero(S0[i]))))
    # THE RENORMALISATION THE GATE EXISTS TO AVOID: his mass reappears on the
    # survivors of his own team.
    team = [j for j, p in enumerate(ids1) if p.startswith('00-001')]
    others = [j for j in team if j != i]
    moved = float(S1[others].sum() - S0[others].sum())
    check('  his team-mates absorb the difference (a renormalisation)',
          abs(moved) > 1e-6, f'delta={moved:.6f}')


def test_the_gate_removes_him_before_allocation_so_no_mass_is_created():
    pool = _synth_pool()
    out_pid = pool[0]['gsis_id']
    gated = [q for q in pool if q['gsis_id'] != out_pid]
    _, _, a = _chain(gated)
    if not check('the gated chain runs',
                 a is not None and a[0].state is State.PASS,
                 '' if a is None else a[0].code):
        return
    tc, ids = a
    check('the ineligible player has no row at all',
          out_pid not in ids, str(ids[:3]))
    layers = {'receiving': {'row_axis': 'gsis_id', 'row_ids': ids,
                            'metrics': ['targets']}}
    arrays = {'receiving/targets': tc.value['share']}
    o = EG.assert_zero_opportunity_over_draws(layers, arrays, [out_pid])
    check('  and the over-draws invariant records him ABSENT',
          o.state is State.PASS and o.value[out_pid] == 'ABSENT',
          f'{o.state.value}[{o.code}]')
    # The same check on the UNGATED draws must fail. Same code, same player.
    _, _, b = _chain(pool)
    tcb, idsb = b
    lb = {'receiving': {'row_axis': 'gsis_id', 'row_ids': idsb,
                        'metrics': ['targets']}}
    ob = EG.assert_zero_opportunity_over_draws(
        lb, {'receiving/targets': tcb.value['share']}, [out_pid])
    check('  while the ungated draws fail the same assertion',
          ob.state is State.FAIL
          and ob.code == 'ZERO_OPPORTUNITY_VIOLATED',
          f'{ob.state.value}[{ob.code}]')


# ============================================ the ATL case, replayed
def test_the_atl_case_is_caught_by_the_gate():
    """ATL's QB1 was Out on the injury report and was projected anyway."""
    if not check('the pre-kickoff week-1 roster capture is retained',
                 ROSTER_W1_AM.exists(), str(ROSTER_W1_AM)):
        return
    ko, cut = '2026-09-13T17:00:00Z', '2026-09-13T16:00:00Z'
    players = _pool(ROSTER_W1_AM, ('ATL', 'PIT'))
    if not check('ATL QB1 is in the ungated pool',
                 any(q['gsis_id'] == ATL_QB1 for q in players)):
        return
    snap = EG.snapshot(SEASON, WEEK, ['ATL', 'PIT'], players,
                       kickoff_utc=ko, observed_before=cut,
                       game_id='2026_01_ATL_PIT')
    if not check('the snapshot builds for ATL/PIT', snap.state is State.PASS,
                 f'{snap.code}: {snap.detail[:200]}'):
        return
    r = snap.value[ATL_QB1]
    check('  he is INJURY_OUT', r['status'] == 'INJURY_OUT', r['status'])
    check('  determined, not uncertain',
          r['determination'] == EG.DETERMINED, r['determination'])
    check('  on rank-2 authority', r['authority_rank'] == 2,
          str(r['authority_rank']))
    check('  with a content hash of the bytes that said so',
          bool(r['content_hash']))
    cs = EG.choice_set(players, snap)
    check('  and he never enters the choice set',
          cs.state is State.PASS
          and not any(q['gsis_id'] == ATL_QB1 for q in cs.value))
    fs = EG.first_seen(SEASON, WEEK, ['ATL', 'PIT'], kickoff_utc=ko,
                       observed_before=cut)
    if check('first_seen runs', fs.state is State.PASS, fs.code):
        f = fs.value.get(ATL_QB1)
        if check('  and dates the designation', bool(f)):
            check(f'  known from {f["known_from"]} '
                  f'({f["hours_known_before_kickoff"]}h before kickoff)',
                  (f['hours_known_before_kickoff'] or 0) > 24,
                  str(f['hours_known_before_kickoff']))
            check('  from a publication clock, not a retrieval clock',
                  f['clock_basis'] == 'PUBLICATION', f['clock_basis'])


# ==================================================== uncertainty stays uncertain
def test_unresolved_is_not_ineligible():
    players = _pool(ROSTER_PREKICK, TEAMS)
    snap = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                       kickoff_utc=KICKOFF, observed_before=CUTOFF)
    if not check('snapshot builds', snap.state is State.PASS, snap.code):
        return
    unresolved = [r for r in snap.value.values()
                  if r['determination'] == EG.UNCERTAIN
                  and r['simulation_eligibility'] == EG.IN_CHOICE_SET]
    check('uncertain players remain in the choice set', bool(unresolved))
    check('  and none was given a zero by default',
          all(r['status'] != 'OFFICIAL_INACTIVE' for r in unresolved))
    check('  ACT is worded as absence of evidence, not availability',
          'ABSENCE of evidence' in EG.STATUS['ROSTER_ACT'][3])


def test_scenarios_refuse_to_invent_a_weight():
    players = _pool(ROSTER_PREKICK, TEAMS)
    snap = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                       kickoff_utc=KICKOFF, observed_before=CUTOFF)
    sc = EG.scenarios(snap)
    if not check('scenarios build', sc.state is State.PASS, sc.code):
        return
    check('with no supplied weights there is ONE world',
          sc.evidence['n_worlds'] == 1, str(sc.evidence['n_worlds']))
    check('  and it says so rather than implying a measurement',
          sc.evidence['weights_estimated'] is False)
    check('  the base world excludes exactly the determined set',
          sc.value[0]['excluded']
          == sorted(snap.evidence['determined_ineligible']))


def test_a_determination_cannot_be_given_a_scenario_weight():
    players = _pool(ROSTER_PREKICK, TEAMS)
    snap = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                       kickoff_utc=KICKOFF, observed_before=CUTOFF)
    det = snap.evidence['determined_ineligible']
    if not check('there is a determined player to try', bool(det)):
        return
    sc = EG.scenarios(snap, weights={det[0]: 0.5})
    check('weighting a determination is refused',
          sc.state is State.FAIL
          and sc.code == 'SCENARIO_WEIGHTS_A_DETERMINATION',
          f'{sc.state.value}[{sc.code}]')


def test_supplied_weights_build_discrete_worlds_that_sum_to_one():
    players = _pool(ROSTER_PREKICK, TEAMS)
    snap = EG.snapshot(SEASON, WEEK, list(TEAMS), players,
                       kickoff_utc=KICKOFF, observed_before=CUTOFF)
    live = [p for p, r in snap.value.items()
            if r['simulation_eligibility'] == EG.IN_CHOICE_SET][:2]
    if not check('two in-pool players exist', len(live) == 2):
        return
    sc = EG.scenarios(snap, weights={live[0]: 0.25, live[1]: 0.5})
    if not check('weighted scenarios build', sc.state is State.PASS, sc.code):
        return
    check('  four discrete worlds for two players',
          sc.evidence['n_worlds'] == 4, str(sc.evidence['n_worlds']))
    check('  the weights sum to one',
          abs(sc.evidence['weight_sum'] - 1.0) < 1e-9,
          str(sc.evidence['weight_sum']))
    check('  every world is a SET of excluded players, not a multiplier',
          all(isinstance(w['excluded'], list) for w in sc.value))
    check('  and the independence assumption is declared',
          'independence_assumed' in sc.evidence)


def test_no_clock_is_a_refusal():
    o = EG.injury_designations(SEASON, WEEK, list(TEAMS))
    check('selecting a vintage without a cutoff is refused',
          o.state is State.BLOCKED and o.code == 'ELIGIBILITY_NO_CLOCK',
          f'{o.state.value}[{o.code}]')


def test_an_unidentified_player_is_refused():
    o = EG.snapshot(SEASON, WEEK, list(TEAMS),
                    [{'gsis_id': '', 'team': 'KC', 'position': 'WR'}],
                    kickoff_utc=KICKOFF, observed_before=CUTOFF)
    check('a player with no gsis_id is refused, never name-matched',
          o.state is State.FAIL
          and o.code == 'ELIGIBILITY_IDENTITY_UNRESOLVED',
          f'{o.state.value}[{o.code}]')


def test_an_empty_pool_is_a_refusal():
    o = EG.snapshot(SEASON, WEEK, list(TEAMS), [], kickoff_utc=KICKOFF,
                    observed_before=CUTOFF)
    check('an empty pool is a refusal, not an eligibility finding',
          o.state is State.FAIL and o.code == 'ELIGIBILITY_NO_PLAYERS',
          f'{o.state.value}[{o.code}]')


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            print(_n)
            _f()
