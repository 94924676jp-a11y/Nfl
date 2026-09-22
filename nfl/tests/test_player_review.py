"""The mandatory player review: coverage, conflicts, escalation, and the gate.

ALL EVIDENCE HERE IS PRE-KICKOFF. The live cases read depth charts, rosters
and week-1 usage at cuts strictly before 2026-09-22T00:15Z. Nothing from the
NYG@LAR game itself is admitted, and nothing here was tuned against a result.

WHAT THIS SUITE PINS

1. The collapse defect cannot come back. A club lists one man in several
   depth groups at the SAME `dt`; the old newest-wins rule never fired and
   file order chose the survivor. Kyren Williams (RB1/PR2) became PR2, Tyrone
   Tracy Jr. (RB4/KR2) became KR2. Both axes are now selected independently
   and the test shuffles the rows to prove the choice does not depend on order.

2. A missing source is never a zero. Routes, pass-block snaps and personnel
   groupings are UNAVAILABLE for 2026 and every dossier says so on every
   player.

3. Availability is never inferred from omission. Without a board the axis
   reads NOT_DECLARED; it never reads ACTIVE.

4. A market or external projection can raise a review priority and can do
   nothing else. It reaches no axis, no projection and no draw.

5. The gate refuses. An unreviewed publishable player, an unresolved blocking
   conflict, or a review of a different draw artifact each stop the slate.
"""
from __future__ import annotations

import copy
import json
import pathlib
import random
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import audit as AUD                      # noqa: E402
from nfl.production.review import dossier as DOS                    # noqa: E402
from nfl.production.review import escalation as ESC                 # noqa: E402
from nfl.production.review import evidence as EV                    # noqa: E402
from nfl.production.review import slate_report as SR                # noqa: E402
from nfl.production.universe import depth_role as DR                # noqa: E402
from nfl.production.universe import player_universe as PU           # noqa: E402
from nfl.production.universe import role_state as RS                # noqa: E402
from nfl.production.universe import usage_vintage as UV             # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T23:05:00Z'
GAME = '2026_02_NYG_LA'
DRAWS = 'nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e'
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
        o = PU.build(2026, 2, GAME, CUT)
        _C['u'] = (o.value['rows'] if isinstance(o.value, dict) else o.value)
    return _C['u']


def urow(name):
    return next((r for r in uni() if r['display_name'] == name), None)


def mk(gsis_id='P1', **kw):
    """A minimal universe row, so a unit case does not need a vintage."""
    r = {'game_id': GAME, 'season': 2026, 'week': 2, 'team': 'NYG',
         'opponent': 'LA', 'gsis_id': gsis_id, 'display_name': gsis_id,
         'roster_position': 'RB', 'roster_status': 'ACT',
         'officially_inactive': False, 'support_state': 'MODEL_SUPPORTED',
         'information_cut': CUT, 'offensive_depth_rank': 1,
         'offensive_depth_state': 'OFFENSIVE_DEPTH_RANK:RB1',
         'special_teams_role': None, 'pfr_id': None,
         'injury_report_status': None, 'injury_practice_status': None}
    r.update(kw)
    return r


def dossiers_from(rows, **kw):
    o = DOS.build_dossiers(universe_rows=rows, information_cut=CUT, **kw)
    assert o.state.name == 'PASS', (o.code, o.detail)
    return o.value['dossiers']


def with_projection(d, **means):
    for k, v in means.items():
        d.projection[k] = EV.ProjectionComponent(k, v, EV.MEASURED)
    return d


# -- 1. the collapse defect --------------------------------------------------
def test_both_listings_survive_a_dt_tie():
    rows = [{'pos_abb': 'PR', 'pos_rank': '2', 'dt': 'T'},
            {'pos_abb': 'RB', 'pos_rank': '1', 'dt': 'T'}]
    s = DR.select_listings(rows, 'RB')
    ok(s['offensive_row']['pos_abb'] == 'RB',
       'an RB1/PR2 listing keeps RB1 on the offensive axis')
    ok(s['special_teams_row']['pos_abb'] == 'PR',
       'and keeps PR2 on the special-teams axis, not instead of it')
    ok(s['listings'] == ['PR2', 'RB1'],
       'every listing is recorded, so nothing is discarded silently')


def test_selection_does_not_depend_on_row_order():
    rows = [{'pos_abb': 'KR', 'pos_rank': '2', 'dt': 'T'},
            {'pos_abb': 'RB', 'pos_rank': '4', 'dt': 'T'},
            {'pos_abb': 'PR', 'pos_rank': '1', 'dt': 'T'}]
    seen = set()
    rnd = random.Random(20260922)
    for _ in range(40):
        shuffled = rows[:]
        rnd.shuffle(shuffled)
        s = DR.select_listings(shuffled, 'RB')
        seen.add((s['offensive_row']['pos_abb'], s['offensive_row']['pos_rank'],
                  s['special_teams_row']['pos_abb'],
                  s['special_teams_row']['pos_rank']))
    ok(seen == {('RB', '4', 'PR', '1')},
       f'40 shuffles give one answer, not {len(seen)} -- file order cannot '
       f'decide a listing any more')


def test_special_teams_only_player_gets_no_offensive_rank():
    s = DR.select_listings([{'pos_abb': 'KR', 'pos_rank': '1', 'dt': 'T'}],
                           'WR')
    ok(s['offensive_row'] is None,
       'a KR1-only listing yields no offensive row at all')
    ok(DR.special_teams_role('KR', '1') == 'KR1',
       'and the special-teams standing is still reported, on its own axis')


def test_the_named_players_recover_their_offensive_listing():
    for name, want in (('Kyren Williams', 1), ('Tyrone Tracy Jr.', 4),
                       ('Blake Corum', 2), ('Devin Singletary', 3)):
        r = urow(name)
        if r is None:
            ok(False, f'{name} is absent from the universe')
            continue
        ok(r.get('offensive_depth_rank') == want,
           f'{name} reads offensive rank {r.get("offensive_depth_rank")} '
           f'(want {want}); before the fix this was None and he read as a '
           f'return man only')
        ok(r.get('special_teams_role') is not None,
           f'{name} still carries his special-teams standing '
           f'({r.get("special_teams_role")}) on the separate axis')


def test_an_offensive_lineman_listed_twice_still_has_no_room_rank():
    s = DR.select_listings([{'pos_abb': 'LG', 'pos_rank': '2', 'dt': 'T'},
                            {'pos_abb': 'RG', 'pos_rank': '2', 'dt': 'T'}], 'G')
    ok(s['offensive_row'] is None,
       'LG2/RG2 is not a modelled room, so no rank is borrowed from it')


# -- 2. missing sources are named, never zeroed ------------------------------
def test_unavailable_sources_are_on_every_dossier():
    d = dossiers_from([mk()])[0]
    for name in ('routes', 'pass_block_snaps', 'personnel_11', 'coach_news'):
        a = d.axis(name)
        ok(a.grade == EV.UNAVAILABLE and a.value is None,
           f'{name} reads UNAVAILABLE with value None, not 0')
    blob = json.dumps(d.as_dict())
    ok('why_unavailable' in blob,
       'and the saved dossier states why each one is unavailable')


def test_a_cold_start_player_is_not_reported_as_measured_zero():
    d = dossiers_from([mk()])[0]
    ok(d.axis('current_season_snap_share').grade == EV.COLD_START,
       'no snap file supplied reads COLD_START, not MEASURED 0.0')
    ok(d.axis('current_season_snap_share').value is None,
       'and carries no number a reader could average')


# -- 3. availability is never inferred from omission -------------------------
def test_availability_without_a_board_is_not_active():
    d = dossiers_from([mk()])[0]
    a = d.axis('official_availability')
    ok(a.value == 'NOT_DECLARED' and a.grade == EV.UNAVAILABLE,
       'with no inactive board the axis reads NOT_DECLARED/UNAVAILABLE')


def test_availability_with_a_board_is_declared_both_ways():
    ds = dossiers_from([mk('A'), mk('B')], inactive_ids={'B'})
    a = {d.gsis_id: d.axis('official_availability') for d in ds}
    ok(a['B'].value == 'INACTIVE' and a['B'].grade == EV.DECLARED,
       'a listed player reads INACTIVE/DECLARED')
    ok(a['A'].value == 'ACTIVE' and a['A'].grade == EV.DECLARED,
       'and an unlisted one reads ACTIVE only because the board is complete')


# -- 4. the audit ------------------------------------------------------------
def test_inactive_player_owning_opportunity_is_blocking():
    ds = dossiers_from([mk('A'), mk('B')], inactive_ids={'B'})
    with_projection(ds[1], carries=4.0, dk_points=6.0)
    o = AUD.audit(ds)
    codes = {c['code'] for c in o.value['conflicts']} if o.value else \
        {c['code'] for c in o.evidence['value']['conflicts']}
    ok(AUD.C_INACTIVE_OWNS_OPPORTUNITY in codes,
       'an inactive player with carries raises the blocking conflict')
    ok(o.state.name == 'FAIL',
       'and the audit itself FAILs rather than reporting a clean slate')


def test_special_teams_only_offensive_load_is_blocking():
    r = mk('A', offensive_depth_rank=None,
           offensive_depth_state='OFFENSIVE_DEPTH_UNKNOWN:SPECIAL_TEAMS_GROUP',
           special_teams_role='KR2')
    ds = dossiers_from([r])
    with_projection(ds[0], carries=9.0, dk_points=11.0)
    o = AUD.audit(ds)
    res = o.value or o.evidence['value']
    ok(AUD.C_ST_ONLY_OFFENSIVE_LOAD in {c['code'] for c in res['conflicts']},
       'a return-only listing carrying offensive work is blocking')


def test_inversion_is_not_raised_when_measured_usage_supports_it():
    """The check must not simply enforce the depth chart. A deeper-listed
    player who actually out-played the starter last week is the normal case
    and raising it would make the audit noise."""
    hi = mk('HI', offensive_depth_rank=4, display_name='HI')
    lo = mk('LO', offensive_depth_rank=1, display_name='LO')
    role = [{'gsis_id': 'HI', 'room': 'carries', 'role': 'PRIMARY_ROTATION',
             'role_support': 'ROLE_SUPPORTED', 'team': 'NYG',
             'evidence': {'current_season_usage': {'carries': 20.0,
                                                   'targets': 0.0}}},
            {'gsis_id': 'LO', 'room': 'carries', 'role': 'STARTER',
             'role_support': 'ROLE_SUPPORTED', 'team': 'NYG',
             'evidence': {'current_season_usage': {'carries': 3.0,
                                                   'targets': 0.0}}}]
    ds = dossiers_from([hi, lo], role_rows=role)
    with_projection(ds[0], carries=12.0, dk_points=14.0)
    with_projection(ds[1], carries=5.0, dk_points=7.0)
    res = AUD.audit(ds).value
    ok(AUD.C_ROOM_ORDER_INVERTED not in {c['code'] for c in res['conflicts']},
       'no conflict when the deeper-listed man measured 20 carries to 3')

    # Same shape, evidence reversed: now nothing supports the inversion.
    role[0]['evidence']['current_season_usage']['carries'] = 2.0
    role[1]['evidence']['current_season_usage']['carries'] = 18.0
    ds2 = dossiers_from([hi, lo], role_rows=role)
    with_projection(ds2[0], carries=12.0, dk_points=14.0)
    with_projection(ds2[1], carries=5.0, dk_points=7.0)
    res2 = AUD.audit(ds2).value
    ok(AUD.C_ROOM_ORDER_INVERTED in {c['code'] for c in res2['conflicts']},
       'and the conflict IS raised when the measured order agrees with the '
       'listing and only the projection disagrees')


def test_a_publishable_player_the_model_skipped_is_blocking():
    ds = dossiers_from([mk('A')])
    o = AUD.audit(ds, publishable_ids={'A'})
    res = o.value or o.evidence['value']
    ok(AUD.C_NOT_EMITTED in {c['code'] for c in res['conflicts']},
       'silence on a publishable player is a conflict, not a zero')


def test_audit_refuses_an_empty_population():
    o = AUD.audit([])
    ok(o.state.name == 'BLOCKED' and o.code == 'NOTHING_TO_AUDIT',
       'an audit over nobody is BLOCKED, never a clean PASS')


# -- 5. escalation -----------------------------------------------------------
def test_priority_is_a_product_so_any_zero_factor_zeroes_it():
    ds = dossiers_from([mk('A'), mk('B')])
    with_projection(ds[0], carries=0.0, dk_points=0.0)   # no impact
    with_projection(ds[1], carries=9.0, dk_points=30.0)
    res = AUD.audit(ds).value
    o = ESC.escalate(ds, res, deep_research_capacity=0)
    v = {x.gsis_id: x for x in o.value['verdicts']}
    ok(v['A'].impact == 0.0 and v['A'].priority == 0.0,
       'a player who cannot move a lineup gets priority 0 however uncertain')
    ok(v['B'].priority > 0.0,
       'and a player who can, with a conflict and thin evidence, does not')


def test_a_blocking_conflict_escalates_at_zero_capacity():
    ds = dossiers_from([mk('A'), mk('B')], inactive_ids={'B'})
    with_projection(ds[1], carries=4.0, dk_points=6.0)
    a = AUD.audit(ds)
    res = a.value or a.evidence['value']
    o = ESC.escalate(ds, res, deep_research_capacity=0)
    v = {x.gsis_id: x for x in o.value['verdicts']}
    ok(v['B'].tier == ESC.DEEP_RESEARCH and v['B'].forced_by_blocking,
       'a blocking conflict reaches DEEP_RESEARCH even with no capacity')


def test_external_numbers_raise_priority_and_touch_nothing_else():
    ds = dossiers_from([mk('A')])
    with_projection(ds[0], carries=5.0, dk_points=12.0)
    before = copy.deepcopy(ds[0].as_dict())
    res = AUD.audit(ds).value
    o = ESC.escalate(ds, res, deep_research_capacity=1,
                     external_disagreement={'A': {'hardrock_gap': 0.9}})
    v = o.value['verdicts'][0]
    ok(v.disagreement > 0.0, 'an external gap raises the disagreement factor')
    ok(ds[0].as_dict() == before,
       'and the dossier is byte-identical afterwards: no axis, no projection '
       'and no draw was touched')
    ok('NEVER_A_MODEL_INPUT' in o.value['external_disagreement_quarantine'],
       'the report says on its face that this may never be a model input')


def test_capacity_is_a_budget_not_a_threshold():
    ds = dossiers_from([mk(f'P{i}') for i in range(10)])
    for i, d in enumerate(ds):
        with_projection(d, carries=float(i), dk_points=float(i))
    res = AUD.audit(ds).value
    a = ESC.escalate(ds, res, deep_research_capacity=3).value
    b = ESC.escalate(ds, res, deep_research_capacity=6).value
    ok(a['by_tier'][ESC.DEEP_RESEARCH] == 3 and
       b['by_tier'][ESC.DEEP_RESEARCH] == 6,
       'the deep tier is exactly the stated capacity, not a score cut')
    ra = [v.gsis_id for v in
          ESC.escalate(ds, res, deep_research_capacity=3).value['verdicts']]
    rb = [v.gsis_id for v in b['verdicts']]
    ok(ra == rb, 'and the ordering does not change when capacity does')


# -- 6. the gate -------------------------------------------------------------
def _report(ds, publishable=None, digests=None):
    res = AUD.audit(ds, publishable_ids=publishable)
    ares = res.value or res.evidence['value']
    esc = ESC.escalate(ds, ares, deep_research_capacity=2).value
    rep = SR.build_report(slate_key='T', dossiers=ds, audit_result=ares,
                          escalation_result=esc, publishable_ids=publishable,
                          projection_source={'digests': digests or {}})
    rep['player_files'] = {f'players/{d.gsis_id}.json': 'x' for d in ds}
    return rep


def test_gate_fails_on_a_publishable_player_with_no_dossier():
    ds = dossiers_from([mk('A')])
    with_projection(ds[0], carries=3.0, dk_points=5.0)
    rep = _report(ds, publishable={'A', 'GHOST'})
    g = SR.assert_player_review_complete(rep, publishable_ids={'A', 'GHOST'})
    ok(g.state.name == 'FAIL' and g.code == 'PLAYER_REVIEW_INCOMPLETE',
       'a publishable player with no dossier stops the slate')


def test_gate_fails_on_an_unresolved_blocking_conflict_and_clears_by_name():
    ds = dossiers_from([mk('A'), mk('B')], inactive_ids={'B'})
    with_projection(ds[0], carries=3.0, dk_points=5.0)
    with_projection(ds[1], carries=4.0, dk_points=6.0)
    rep = _report(ds)
    g = SR.assert_player_review_complete(rep)
    ok(g.state.name == 'FAIL' and
       g.code == 'PLAYER_REVIEW_BLOCKING_CONFLICTS_UNRESOLVED',
       'an unresolved blocking conflict stops the slate')
    g2 = SR.assert_player_review_complete(
        rep, resolved_conflict_codes={AUD.C_INACTIVE_OWNS_OPPORTUNITY})
    ok(g2.state.name == 'PASS',
       'and clears only when the code is named on the record')


def test_gate_refuses_a_review_of_a_different_draw_artifact():
    ds = dossiers_from([mk('A')])
    with_projection(ds[0], carries=3.0, dk_points=5.0)
    rep = _report(ds, digests={'player_draws.npz': 'aaaa'})
    g = SR.assert_player_review_complete(rep, consumed_draw_digest='bbbb')
    ok(g.state.name == 'FAIL' and g.code == 'REVIEW_READ_A_DIFFERENT_ARTIFACT',
       'reviewing one run and optimizing another is refused')
    g2 = SR.assert_player_review_complete(rep, consumed_draw_digest='aaaa')
    ok(g2.state.name == 'PASS', 'and the matching digest passes')


def test_writing_an_empty_review_is_refused():
    o = SR.write_report({'slate_key': 'T'}, [])
    ok(o.state.name == 'BLOCKED' and o.code == 'NO_DOSSIERS_TO_WRITE',
       'an empty review is never recorded as a completed one')


# -- 7. the live slate -------------------------------------------------------
def test_the_live_slate_reviews_every_publishable_player():
    if not (_REPO / DRAWS / 'player_draws.npz').exists():
        ok(True, f'{DRAWS} absent in this checkout; live case skipped')
        return
    po = DOS.read_projection(_REPO / DRAWS)
    ok(po.state.name == 'PASS', f'the sealed draw artifact reads: {po.code}')
    emitted = set(po.value['per_player'])
    with tempfile.TemporaryDirectory() as td:
        o = SR.review_slate(
            slate_key=GAME, universe_rows=uni(), draws_dir=_REPO / DRAWS,
            publishable_ids=emitted, information_cut=CUT, root=td,
            deep_research_capacity=12)
        ok(o.state.name == 'PASS', f'the review runs end to end: {o.code}')
        cov = o.value['report']['coverage']
        ok(cov['publishable_coverage'] == 1.0,
           f'every one of {len(emitted)} publishable players has a dossier '
           f'(coverage {cov["publishable_coverage"]})')
        ok(cov['n_universe'] > len(emitted),
           f'and the review covers the wider universe too '
           f'({cov["n_universe"]} dossiers)')
        n = len(list(pathlib.Path(td).glob(f'{GAME}/player_dossiers/*.json')))
        ok(n == cov['n_universe'],
           f'{n} dossier files are on disk, matching the {cov["n_universe"]} '
           f'built')


def test_the_live_slate_still_raises_the_backfield_inversion():
    if not (_REPO / DRAWS / 'player_draws.npz').exists():
        ok(True, 'draw artifact absent; live case skipped')
        return
    with tempfile.TemporaryDirectory() as td:
        # The full chain, because the claim under test is about the
        # measured evidence the check reads, not about two absences.
        usage = UV.usage_season(2026, CUT, before_week=2)
        snaps = RS.load_snaps(2026, 2)
        roles = RS.assign(uni(), season=2026, week=2,
                          usage_rows=usage.value if
                          usage.state.name == 'PASS' else {})
        o = SR.review_slate(
            slate_key=GAME, universe_rows=uni(),
            role_rows=(roles.value['rows'] if isinstance(roles.value, dict)
                       else roles.value) if roles.state.name == 'PASS' else [],
            snap_rows=snaps.value if snaps.state.name == 'PASS' else [],
            usage_rows=usage.value if usage.state.name == 'PASS' else {},
            draws_dir=_REPO / DRAWS, information_cut=CUT,
            root=td, deep_research_capacity=12)
        cs = [c for c in o.value['report']['conflicts']
              if c['code'] == AUD.C_ROOM_ORDER_INVERTED
              and c['display_name'] == 'Tyrone Tracy Jr.']
    ok(bool(cs),
       'the audit independently raises Tracy over Skattebo -- the defect '
       'that reached a lineup last night is now caught before the optimizer')
    if cs:
        e = cs[0]['evidence']
        ok(e['higher']['carries'] > e['lower']['carries'] and
           e['higher']['prior_usage'] < e['lower']['prior_usage'],
           f'with the evidence attached: {e["higher"]["carries"]:.3f} carries '
           f'on {e["higher"]["prior_usage"]:.0f} prior, against '
           f'{e["lower"]["carries"]:.3f} on {e["lower"]["prior_usage"]:.0f}')


def main():
    for t in (test_both_listings_survive_a_dt_tie,
              test_selection_does_not_depend_on_row_order,
              test_special_teams_only_player_gets_no_offensive_rank,
              test_the_named_players_recover_their_offensive_listing,
              test_an_offensive_lineman_listed_twice_still_has_no_room_rank,
              test_unavailable_sources_are_on_every_dossier,
              test_a_cold_start_player_is_not_reported_as_measured_zero,
              test_availability_without_a_board_is_not_active,
              test_availability_with_a_board_is_declared_both_ways,
              test_inactive_player_owning_opportunity_is_blocking,
              test_special_teams_only_offensive_load_is_blocking,
              test_inversion_is_not_raised_when_measured_usage_supports_it,
              test_a_publishable_player_the_model_skipped_is_blocking,
              test_audit_refuses_an_empty_population,
              test_priority_is_a_product_so_any_zero_factor_zeroes_it,
              test_a_blocking_conflict_escalates_at_zero_capacity,
              test_external_numbers_raise_priority_and_touch_nothing_else,
              test_capacity_is_a_budget_not_a_threshold,
              test_gate_fails_on_a_publishable_player_with_no_dossier,
              test_gate_fails_on_an_unresolved_blocking_conflict_and_clears_by_name,
              test_gate_refuses_a_review_of_a_different_draw_artifact,
              test_writing_an_empty_review_is_refused,
              test_the_live_slate_reviews_every_publishable_player,
              test_the_live_slate_still_raises_the_backfield_inversion):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
