"""Phase 1 regressions: a depth rank may only inform the room it was ranked in.

EVERY CASE HERE IS PRE-KICKOFF EVIDENCE. The measurements are week-1 usage,
week-1 snap shares, and depth charts and rosters read at cuts strictly before
the 2026-09-22T00:15Z kickoff. Nothing from the game itself is admitted.

THE CLAIM THIS SUITE RETRACTS. Commit c182e68 asserted that `role_prior` reads
Tracy's KR2 as RB2 and that this caused the Skattebo/Tracy inversion. It does
not: `depth_vintage.daily` drops the return groups before ranking, and the
live production map returns Tracy as ('RB', 4). The KR2 was in the candidate
universe layer. Both facts are pinned below so the wrong claim cannot be
restated and the real leak cannot come back.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import depth_role as DR                # noqa: E402
from nfl.production.universe import player_universe as PU           # noqa: E402
from nfl.production.universe import role_state as RS                # noqa: E402
from sportsplatform.governance.outcome import State                 # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T23:20:00Z'
GAME = '2026_02_NYG_LA'
_C = {}


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def uni():
    if 'u' not in _C:
        _C['u'] = PU.build(2026, 2, GAME, CUT)
    return _C['u']


def row(name):
    for r in uni().value:
        if (r.get('display_name') or '') == name:
            return r
    return None


# --- 1. KR depth cannot contaminate RB depth ------------------------------
def test_kr_depth_cannot_become_rb_depth():
    r, why = DR.offensive_depth_rank('RB', 'KR', 2)
    ok(r is None, f'KR2 yields no RB rank: {r}')
    ok('SPECIAL_TEAMS_GROUP' in why and 'KR2' in why,
       f'and says so by name rather than going silently absent: {why}')
    ok(DR.special_teams_role('KR', 2) == 'KR2',
       'while the special-teams standing survives on its own axis')

    t = row('Tyrone Tracy Jr.')
    ok(t is not None, 'Tracy is in the universe')
    if t:
        ok(t.get('depth_pos_abb') == 'KR',
           f"the candidate layer still reads his raw listing: "
           f"{t.get('depth_pos_abb')}{t.get('depth_rank')}")
        ok(t.get('offensive_depth_rank') is None,
           f'but his offensive depth rank is refused: '
           f'{t.get("offensive_depth_rank")}')
        ok(t.get('special_teams_role') == 'KR2',
           f'and his return role is preserved separately: '
           f'{t.get("special_teams_role")}')
        ok(DR.OFFENSIVE_DEPTH_UNKNOWN in (t.get('offensive_depth_state') or ''),
           f'with the explicit state, not a missing field: '
           f'{t.get("offensive_depth_state")}')


# --- 2. PR depth cannot contaminate WR depth ------------------------------
def test_pr_depth_cannot_become_wr_depth():
    r, why = DR.offensive_depth_rank('WR', 'PR', 1)
    ok(r is None and 'SPECIAL_TEAMS_GROUP' in why,
       f'PR1 yields no WR rank: {r} {why}')
    ok(DR.special_teams_role('PR', 1) == 'PR1',
       'and the punt-return standing is kept on its own axis')
    for g in ('KOR', 'LS', 'P', 'ST', 'H'):
        ok(DR.offensive_depth_rank('WR', g, 1)[0] is None,
           f'{g}1 informs no offensive room')


# --- 3. Singletary KR3 does not become RB3 --------------------------------
def test_singletary_kr3_does_not_become_rb3():
    s = row('Devin Singletary')
    ok(s is not None, 'Singletary is in the universe')
    if s:
        ok(s.get('offensive_depth_rank') is None,
           f'his KR3 does not enter the backfield: '
           f'{s.get("offensive_depth_rank")}')
        ok(s.get('special_teams_role') == 'KR3',
           f'and is kept as return standing: {s.get("special_teams_role")}')


# --- 4. Real offensive depth still works ----------------------------------
def test_genuine_offensive_depth_still_informs_its_own_room():
    ok(DR.offensive_depth_rank('RB', 'RB', 4) == (4, 'OFFENSIVE_DEPTH_RANK:RB4'),
       'RB4 informs the RB room')
    ok(DR.offensive_depth_rank('WR', 'WR', 3)[0] == 3, 'WR3 informs the WR room')
    ok(DR.offensive_depth_rank('TE', 'TE', 2)[0] == 2, 'TE2 informs the TE room')
    ok(DR.offensive_depth_rank('QB', 'QB', 1)[0] == 1, 'QB1 informs the QB room')
    ok(DR.offensive_depth_rank('K', 'PK', 1)[0] == 1,
       'PK1 informs the kicking room, since PK and K are the same room')

    sk = row('Cam Skattebo')
    if sk:
        ok(sk.get('offensive_depth_rank') == 1,
           f'Skattebo RB1 survives intact: {sk.get("offensive_depth_rank")}')


# --- 5. The cross-group leak that is actually real ------------------------
def test_fullback_rank_does_not_become_a_running_back_rank():
    """Patrick Ricard, model RB, depth group FB, rank 1.

    This is the leak that IS in the production shape: `dr[k] = v[1]` keeps the
    rank and discards the group, so FB1 becomes a rank-1 anchor inside the
    running back room -- the lead back's anchor, for a blocking fullback who
    took zero week-1 carries.
    """
    r, why = DR.offensive_depth_rank('RB', 'FB', 1)
    ok(r is None, f'FB1 does not inform the RB room: {r}')
    ok('GROUP_MISMATCH' in why, f'and is named a group mismatch: {why}')
    ok(DR.offensive_depth_rank('FB', 'FB', 1)[0] == 1,
       'while a fullback keeps his own FB room rank')

    ric = row('Patrick Ricard')
    if ric:
        ok(ric.get('offensive_depth_rank') is None,
           f'Ricard carries no backfield rank: '
           f'{ric.get("offensive_depth_rank")}')


# --- 6. The guard over the production-shaped map --------------------------
def test_guard_filters_the_production_rank_map_and_names_refusals():
    rank_map = {'p_rb': ('RB', 1), 'p_fb': ('FB', 1), 'p_kr': ('KR', 2),
                'p_wr': ('WR', 3), 'p_pk': ('PK', 1)}
    model = {'p_rb': 'RB', 'p_fb': 'RB', 'p_kr': 'RB', 'p_wr': 'WR',
             'p_pk': 'K'}
    g = DR.guard_rank_map(rank_map, model)
    ok(set(g['rank']) == {'p_rb', 'p_wr', 'p_pk'},
       f'only same-room ranks survive: {sorted(g["rank"])}')
    ok(g['rank']['p_rb'] == 1 and g['rank']['p_wr'] == 3,
       'and they keep their values')
    ok(g['n_refused'] == 2,
       f'the two cross-room ranks are refused: {g["n_refused"]}')
    whys = {x['why'].split(':')[1] for x in g['refused']}
    ok('GROUP_MISMATCH' in whys and 'SPECIAL_TEAMS_GROUP' in whys,
       f'each refusal is named: {sorted(whys)}')
    ok(g['special_teams_role'].get('p_kr') == 'KR2',
       'and special-teams standing is returned rather than destroyed')
    ok(DR.guard_rank_map({}, {})['n_kept'] == 0,
       'an empty map is an empty result, not an error')


# --- 7. The production path's own depth view is correct -------------------
def test_the_production_depth_view_of_the_backfield_is_correct():
    """The retraction, pinned. Production does NOT see Tracy as RB2."""
    try:
        from nfl.product import board as PBRD
        from nfl.production.nonqb import vintage_selector as VS
    except Exception as exc:                                  # noqa: BLE001
        ok(False, f'could not import the production depth path: {exc}')
        return
    o = PBRD.depth_rank_outcome(
        2026, 2, ['NYG', 'LA'],
        as_of=VS.as_of_cut('2026-09-22T00:15:00Z', '2026-09-21T23:59:00Z'))
    ok(o.state is State.PASS, f'the production rank map builds: {o.code}')
    if o.state is not State.PASS:
        return
    name = {r['gsis_id']: r['display_name'] for r in uni().value}
    got = {name.get(p): v for p, v in o.value.items() if name.get(p) in
           ('Cam Skattebo', 'Tyrone Tracy Jr.', 'Devin Singletary',
            'Najee Harris')}
    ok(got.get('Cam Skattebo') == ('RB', 1),
       f'Skattebo is RB1 in production: {got.get("Cam Skattebo")}')
    ok(got.get('Tyrone Tracy Jr.') == ('RB', 4),
       f'Tracy is RB4 in production, NOT RB2 and NOT KR2: '
       f'{got.get("Tyrone Tracy Jr.")}')
    ok(got.get('Devin Singletary') == ('RB', 3),
       f'Singletary is RB3: {got.get("Devin Singletary")}')
    # The accurate invariant, corrected after measuring. The production map
    # is offence-wide AND defence-wide -- 119 players including SLB, RCB, NT
    # and the offensive line -- so special-teams groups DO appear in it: H1
    # for the two punters and LS1 for the two long snappers. What matters is
    # that none of them reaches a SKILL room, because `assign_tiers` groups
    # by model position and a punter is not in one.
    pos = {r['gsis_id']: r['roster_position'] for r in uni().value}
    SKILL = {'QB', 'RB', 'HB', 'FB', 'WR', 'TE', 'K'}
    leaks = [(name.get(p), v, pos.get(p)) for p, v in o.value.items()
             if v[0] in DR.SPECIAL_TEAMS_GROUPS and pos.get(p) in SKILL]
    ok(not leaks,
       f'no special-teams group reaches a SKILL room: {leaks}')
    st_seen = sorted({v[0] for v in o.value.values()
                      if v[0] in DR.SPECIAL_TEAMS_GROUPS})
    ok(st_seen == ['H', 'LS'],
       f'the only special-teams groups present are holder and long snapper, '
       f'whose model positions are P and LS: {st_seen}')
    ok(not any(v[0] in ('KR', 'PR', 'KOR') for v in o.value.values()),
       'and the return groups, the ones I wrongly blamed, are absent '
       'entirely')


# --- 8. Measured participation must not be silently outranked -------------
def test_measured_participation_survives_the_change():
    """Skattebo led the room on both measured axes before kickoff."""
    ro = RS.assign(uni().value, season=2026, week=2, usage_rows=None)
    ok(ro.state is State.PASS, f'roles still assign: {ro.code}')
    by = {r['display_name']: r for r in ro.value}
    sk, tr = by.get('Cam Skattebo'), by.get('Tyrone Tracy Jr.')
    if sk and tr:
        s_sn = sk['evidence']['current_season_snaps']['mean_offense_pct']
        t_sn = tr['evidence']['current_season_snaps']['mean_offense_pct']
        ok(s_sn is not None and t_sn is not None and s_sn > t_sn,
           f'Skattebo outsnapped Tracy in the measured week: {s_sn} vs {t_sn}')
        ok(sk['role'] in RS.WORKLOAD_BEARING,
           f'and carries a workload-bearing role: {sk["role"]}')
        ok(tr['role'] not in RS.WORKLOAD_BEARING,
           f'while Tracy does not: {tr["role"]}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_kr_depth_cannot_become_rb_depth,
              test_pr_depth_cannot_become_wr_depth,
              test_singletary_kr3_does_not_become_rb3,
              test_genuine_offensive_depth_still_informs_its_own_room,
              test_fullback_rank_does_not_become_a_running_back_rank,
              test_guard_filters_the_production_rank_map_and_names_refusals,
              test_the_production_depth_view_of_the_backfield_is_correct,
              test_measured_participation_survives_the_change):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
