"""The audit challenges canonical football truth; it does not reinterpret it.

`review/audit_reference.py` is the frozen builder at 5edfc6b. This suite runs
it and the migrated audit over the same fixtures and compares the whole
conflict set -- player ids, codes, severities, and the attribution metadata
carried on each conflict.

ONE CLASS OF DIFFERENCE IS EXPECTED AND IT IS NAMED. Every availability test
in the reference read `!= 'INACTIVE'`, which treated a player his club had
designated OUT as available. That defect predates the availability slice;
what the slice did was make OUT visible, because before it the dossier
collapsed an OUT player into ACTIVE. Every conflict the correction adds is
enumerated below.
"""
from __future__ import annotations

import ast
import collections
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / 'nfl' / 'tests') not in sys.path:
    sys.path.insert(0, str(_REPO / 'nfl' / 'tests'))

from nfl.production.review import audit as A                          # noqa: E402
from nfl.production.review import audit_reference as AR               # noqa: E402
from nfl.production.review import dossier as D                        # noqa: E402
from nfl.production.review import evidence as EV                      # noqa: E402
from nfl.production.state import availability as AV                   # noqa: E402
from nfl.production.state import slate_state as SS                    # noqa: E402
from nfl.production.universe import player_universe as PU             # noqa: E402

import test_dossier_migration as T                                    # noqa: E402

PASSED = FAILED = 0
GAME, CUT = '2026_02_CAR_ATL', '2026-09-22T23:00:00Z'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _val(o):
    return o.value or (getattr(o, 'evidence', {}) or {}).get('value') or {}


def key(c):
    return (c['gsis_id'], c['code'], c['severity'])


def run_both(dossiers, **kw):
    a = AR.audit(dossiers, **kw)
    b = A.audit(dossiers, **kw)
    return _val(a), _val(b)


def compare(name, dossiers, **kw):
    """Whole conflict set, both directions. Returns (added, dropped, shared)."""
    va, vb = run_both(dossiers, **kw)
    ka = {key(c): c for c in va['conflicts']}
    kb = {key(c): c for c in vb['conflicts']}
    added = sorted(set(kb) - set(ka))
    dropped = sorted(set(ka) - set(kb))
    shared = sorted(set(ka) & set(kb))
    print(f'  ---- {name}: ref {va["n_conflicts"]} / new {vb["n_conflicts"]}; '
          f'{len(shared)} shared, {len(added)} added, '
          f'{len(dropped)} dropped ----')
    return ka, kb, added, dropped, shared


# -- 1. equivalence on the migration fixture -------------------------------
def test_the_conflict_set_is_unchanged_except_for_the_out_correction():
    kw = T.fixture()
    ds = D.build_dossiers(**kw).value['dossiers']
    pub = set(kw['projection']['per_player'])
    ka, kb, added, dropped, shared = compare('migration fixture', ds,
                                             publishable_ids=pub)
    ok(not dropped,
       f'no conflict the reference raised has disappeared: {dropped}')
    ok(shared, f'{len(shared)} conflicts are identical in id, code and '
               f'severity')
    ok(all(c[1] == A.C_INACTIVE_OWNS_OPPORTUNITY for c in added),
       f'every added conflict is the OUT correction: '
       f'{sorted({c[1] for c in added})}')
    for gid, code, sev in added:
        c = kb[(gid, code, sev)]
        ok(c['evidence'].get('availability') == AV.INJURY_OUT,
           f'ADDED  {c["display_name"]}: {code} because the club designated '
           f'him {c["evidence"]["availability"]} and the model still gives '
           f'him {c["evidence"]["opportunity"]:.3f} opportunities')
    ok(len(added) == 2,
       f'two players on this fixture: {len(added)}')


def test_shared_conflicts_differ_only_in_declared_attribution():
    kw = T.fixture()
    ds = D.build_dossiers(**kw).value['dossiers']
    pub = set(kw['projection']['per_player'])
    ka, kb, _a, _d, shared = compare('shared-field check', ds,
                                     publishable_ids=pub)
    changed = collections.Counter()
    codes = collections.Counter()
    for k in shared:
        for fld in ('team', 'display_name', 'gsis_id'):
            if ka[k].get(fld) != kb[k].get(fld):
                changed[fld] += 1
        if ka[k]['evidence'] != kb[k]['evidence']:
            changed['evidence'] += 1
            codes[k[1]] += 1
        if ka[k]['detail'] != kb[k]['detail']:
            changed['detail'] += 1
    ok(not any(changed[f] for f in ('team', 'display_name', 'gsis_id')),
       'identity fields are identical on every shared conflict')
    ok(set(codes) <= {A.C_INACTIVE_OWNS_OPPORTUNITY},
       f'only the availability conflict changed its attribution metadata: '
       f'{dict(codes)}')
    for k in shared:
        if k[1] == A.C_INACTIVE_OWNS_OPPORTUNITY:
            ok(set(kb[k]['evidence']) - set(ka[k]['evidence'])
               == {'availability'},
               f'and the change is one ADDED key naming the state: '
               f'{sorted(set(kb[k]["evidence"]) - set(ka[k]["evidence"]))}')
            ok(ka[k]['evidence']['opportunity']
               == kb[k]['evidence']['opportunity'],
               'with the opportunity figure unchanged')
            break


# -- 2. a fixture built to exercise room order -----------------------------
def room_fixture(*, stale=False):
    """Two backs in one room with the listing inverted, plus a receiver.

    Built by hand because the real slate does not contain an inversion at
    this cut, and a check nobody exercises is a check nobody has tested.
    """
    def row(gid, rank, pos='RB', **kw):
        r = {'game_id': GAME, 'season': 2026, 'week': 2, 'team': 'CAR',
             'opponent': 'ATL', 'gsis_id': gid, 'display_name': gid,
             'roster_position': pos, 'roster_status': 'ACT',
             'officially_inactive': False, 'support_state': 'MODEL_SUPPORTED',
             'information_cut': CUT, 'offensive_depth_rank': rank,
             'offensive_depth_state': f'OFFENSIVE_DEPTH_RANK:{pos}{rank}',
             'special_teams_role': None, 'pfr_id': gid,
             'depth_listings': [], 'support_state_why': 'x',
             'evidence_tier': 3, 'depth_dt': CUT,
             'injury_report_status': None, 'injury_practice_status': None}
        r.update(kw)
        return r

    rows = [row('RB1', 1), row('RB4', 4), row('WR1', 1, pos='WR')]
    role_rows = [{'gsis_id': 'RB1', 'room': 'carries', 'role': 'STARTER',
                  'role_support': 'ROLE_SUPPORTED',
                  'evidence': {'current_season_usage': {
                      'carries': 12.0, 'targets': 2.0,
                      'club_of_record': 'CAR'}}},
                 {'gsis_id': 'RB4', 'room': 'carries', 'role': 'ROTATIONAL',
                  'role_support': 'ROLE_SUPPORTED',
                  'evidence': {'current_season_usage': {
                      'carries': 3.0, 'targets': 1.0,
                      'club_of_record': 'CAR'}}},
                 {'gsis_id': 'WR1', 'room': 'targets', 'role': 'STARTER',
                  'role_support': 'ROLE_SUPPORTED',
                  'evidence': {'current_season_usage': {
                      'carries': 0.0, 'targets': 9.0,
                      'club_of_record': 'CAR'}}}]
    snap_rows = [{'pfr_player_id': 'RB1', 'offense_pct': 0.70, 'st_pct': 0.1},
                 {'pfr_player_id': 'RB4', 'offense_pct': 0.20, 'st_pct': 0.3},
                 {'pfr_player_id': 'WR1', 'offense_pct': 0.80, 'st_pct': 0.0}]
    summ = {'sd': 1.0, 'p05': 0.0, 'p25': 1.0, 'p50': 2.0, 'p75': 3.0,
            'p95': 4.0, 'p_zero': 0.05, 'n_draws': 100}
    proj = {'per_player': {
        'RB1': {'carries': dict(summ, mean=5.0),
                'dk_points': dict(summ, mean=8.0)},
        # the deeper-listed back out-carries the starter: the inversion
        'RB4': {'carries': dict(summ, mean=11.0),
                'dk_points': dict(summ, mean=13.0)},
        'WR1': {'targets': dict(summ, mean=7.0),
                'dk_points': dict(summ, mean=11.0)}},
        'run_id': 'RUN-ROOM', 'digests': {}, 'n_draws': 100,
        'metrics_absent': []}
    att = {'RB4': {'contributions': (
        {'PRIOR_SEASON_MEASURED': 0.7, 'CURRENT_SEASON_MEASURED': 0.2}
        if stale else
        {'CURRENT_SEASON_MEASURED': 0.8, 'PRIOR_SEASON_MEASURED': 0.1})}}
    return dict(universe_rows=rows, role_rows=role_rows, snap_rows=snap_rows,
                usage_rows=[], projection=proj,
                opportunity_attribution=att, information_cut=CUT)


def test_room_order_conflicts_are_identical():
    for stale in (False, True):
        kw = room_fixture(stale=stale)
        ds = D.build_dossiers(**kw).value['dossiers']
        ka, kb, added, dropped, shared = compare(
            f'room fixture stale={stale}', ds,
            publishable_ids=set(kw['projection']['per_player']))
        ok(not added and not dropped,
           f'stale={stale}: identical conflict set, {len(shared)} conflict(s)')
        want = (A.C_INVERSION_ON_STALE_SEASON if stale
                else A.C_ROOM_ORDER_INVERTED)
        ok(any(k[1] == want for k in shared),
           f'and the fixture does exercise {want}')
        for k in shared:
            ok(ka[k]['evidence'] == kb[k]['evidence']
               and ka[k]['detail'] == kb[k]['detail'],
               f'{k[1]} on {k[0]}: identical detail and evidence')


def test_the_receiving_note_still_fires_identically():
    kw = room_fixture()
    ds = D.build_dossiers(**kw).value['dossiers']
    ka, kb, added, dropped, shared = compare('receiving note', ds)
    ok(any(k[1] == A.C_RECEIVING_ROLE_ON_SNAPS_ONLY for k in shared),
       'the routes-unavailable note fires')
    ok(not added and not dropped,
       'and the whole set is identical without publishable_ids too')


# -- 3. the OUT correction, stated directly --------------------------------
def test_out_is_treated_as_will_not_play():
    ok(AV.INJURY_OUT in A.WILL_NOT_PLAY and AV.OFFICIAL_INACTIVE
       in A.WILL_NOT_PLAY,
       f'WILL_NOT_PLAY is {sorted(A.WILL_NOT_PLAY)}')
    ok('INACTIVE' in A.WILL_NOT_PLAY,
       "including the dossier's alias for OFFICIAL_INACTIVE")
    for st in (AV.NOT_ON_INACTIVE_LIST, AV.UNKNOWN, AV.INJURY_DOUBTFUL,
               AV.INJURY_QUESTIONABLE):
        ok(st not in A.WILL_NOT_PLAY,
           f'{st} is NOT treated as declared out, and is not positive '
           f'evidence of availability either')
    ok(set(A.WILL_NOT_PLAY) - {'INACTIVE'} == set(AV.WILL_NOT_PLAY),
       'and the set is taken from the canonical vocabulary rather than '
       'restated, so adding a state cannot leave the audit out of date')


def test_an_out_player_with_opportunity_blocks():
    kw = room_fixture()
    kw['universe_rows'][1]['injury_report_status'] = 'Out'
    ds = D.build_dossiers(**kw).value['dossiers']
    v = _val(A.audit(ds))
    hit = [c for c in v['conflicts']
           if c['gsis_id'] == 'RB4'
           and c['code'] == A.C_INACTIVE_OWNS_OPPORTUNITY]
    ok(hit, 'a player designated OUT who still owns opportunity blocks')
    ok(hit and hit[0]['severity'] == A.BLOCKING,
       f'at BLOCKING severity: {hit[0]["severity"] if hit else None}')
    ok(hit and hit[0]['evidence']['availability'] == AV.INJURY_OUT,
       'and the conflict names the state that made it one')
    ref = _val(AR.audit(ds))
    ok(not [c for c in ref['conflicts'] if c['gsis_id'] == 'RB4'
            and c['code'] == A.C_INACTIVE_OWNS_OPPORTUNITY],
       'while the frozen reference misses him entirely, which is the '
       'defect this slice corrects')


def test_uncertainty_designations_are_not_treated_as_out():
    for desig in ('Questionable', 'Doubtful'):
        kw = room_fixture()
        kw['universe_rows'][1]['injury_report_status'] = desig
        ds = D.build_dossiers(**kw).value['dossiers']
        v = _val(A.audit(ds))
        hit = [c for c in v['conflicts']
               if c['gsis_id'] == 'RB4'
               and c['code'] == A.C_INACTIVE_OWNS_OPPORTUNITY]
        ok(not hit,
           f'{desig} is a statement of uncertainty, not of absence, so it '
           f'raises no inactive-owns-opportunity conflict')


# -- 4. football truth comes from state ------------------------------------
def test_the_audit_reads_state_not_the_dossier_relabel():
    kw = room_fixture()
    ds = D.build_dossiers(**kw).value['dossiers']
    d = next(x for x in ds if x.gsis_id == 'RB4')
    f = A._facts(d)
    ps = d.player_state
    ok(f.room == ps.room.value == 'carries',
       f'room comes from PlayerState: {f.room}')
    ok(f.depth_rank == ps.offensive_depth.value == 4,
       f'offensive depth comes from PlayerState: {f.depth_rank}')
    ok(f.availability == ps.availability.value,
       f'availability comes from PlayerState: {f.availability}')
    ok(f.role == 'ROTATIONAL' and f.role_support == 'ROLE_SUPPORTED',
       f'role evidence comes from PlayerState: {f.role}/{f.role_support}')
    ok(f.snap_measured and abs(f.snap_share - 0.20) < 1e-9,
       f'measured participation comes from PlayerState: {f.snap_share}')
    ok(f.carries_measured and f.prior_carries == 3.0,
       f'and measured usage too: {f.prior_carries}')
    ok(not f.routes_available,
       'routes are UNAVAILABLE on the state axis, not asserted here')


def test_a_dossier_without_a_state_is_refused():
    d = D.PlayerPregameDossier(
        gsis_id='X', display_name='X', team='CAR', opponent='ATL',
        game_id=GAME, season=2026, week=2, information_cut=CUT,
        support_state='MODEL_SUPPORTED')
    try:
        A._facts(d)
        ok(False, 'a stateless dossier should not be auditable')
    except AssertionError as e:
        ok('no PlayerState' in str(e),
           'a dossier built outside build_from_state is refused by name, '
           'not silently audited against a relabelled copy')


def test_the_audit_reads_no_raw_football_source():
    src = (_REPO / 'nfl/production/review/audit.py').read_text()
    tree = ast.parse(src)
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                imported.add(a.name)
            if n.module:
                imported.add(n.module.split('.')[-1])
        elif isinstance(n, ast.Import):
            for a in n.names:
                imported.add(a.name.split('.')[-1])
    forbidden = {'vintage_selector', 'player_universe', 'depth_role',
                 'role_state', 'usage_vintage', 'depth_vintage', 'inactives',
                 'current_season_evidence', 'current_season_team_volume',
                 'snap_counts', 'csv', 'gzip'}
    hit = sorted(imported & forbidden)
    ok(not hit, f'the audit imports no football-source module or table '
                f'reader: {hit}')
    for token in ('.csv', '.gz', 'vintage/', 'vintage_manifest',
                  'weekly_rosters', 'depth_charts', 'official_inactives',
                  'snap_counts', 'open('):
        ok(token not in src, f'and names no raw source or file read: '
                             f'{token!r}')
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ('axis', 'value')]
    axes = sorted({n.args[0].value for n in calls
                   if n.args and isinstance(n.args[0], ast.Constant)})
    ok(set(axes) <= {'vacated_opportunity', 'opportunity_attribution'},
       f'the only dossier axes it still reads are the ones the dossier '
       f'owns -- the redistribution record and the Stage-6 attribution: '
       f'{axes}')
    ok('player_state' in src,
       'and it reaches the canonical state through the dossier reference')


def main():
    for t in (test_the_conflict_set_is_unchanged_except_for_the_out_correction,
              test_shared_conflicts_differ_only_in_declared_attribution,
              test_room_order_conflicts_are_identical,
              test_the_receiving_note_still_fires_identically,
              test_out_is_treated_as_will_not_play,
              test_an_out_player_with_opportunity_blocks,
              test_uncertainty_designations_are_not_treated_as_out,
              test_the_audit_reads_state_not_the_dossier_relabel,
              test_a_dossier_without_a_state_is_refused,
              test_the_audit_reads_no_raw_football_source):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
