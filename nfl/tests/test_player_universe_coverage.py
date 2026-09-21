"""P0-B: no expected player silently disappears, and no club hides behind another.

THE FIVE CASES THIS PINS, ALL FROM REAL WEEK-2 ARTIFACTS

1. MIN@CHI -- one club vanishes INSIDE an otherwise valid layer. P0-A passes
   it correctly: the receiving layer is present, its metrics have bytes, its
   ids are unique and finite. Coverage must still fail it, because CHI has
   zero rows in `receiving` and zero in `rushing` while MIN has 14 and 5.
2. PHI@TEN -- both clubs lose every skill layer. Caught by P0-A too; caught
   here as well, per club, which is the level that says WHO is missing.
3. Davon Booth -- a DraftKings salary row with no football row. He must carry
   a named state, not be absent.
4. Ogletree -- football identity and DK salary identity are separate axes and
   a failure on one must not move the other.
5. Walker and VanSumeren -- both present with their depth evidence attached.
   P0-B says nothing about their workload; that is the role model's job and
   this test asserts the SILENCE as well as the presence.
"""
from __future__ import annotations

import glob
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import coverage as CV               # noqa: E402
from nfl.production.universe import player_universe as PU        # noqa: E402
from nfl.production.universe import support_state as S           # noqa: E402
from sportsplatform.governance.outcome import State              # noqa: E402

PASSED = FAILED = 0
CUT_1PM = '2026-09-20T16:22:00Z'
CUT_SNF = '2026-09-20T23:05:00Z'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _runs(pattern):
    out = {}
    for d in sorted(glob.glob(pattern)):
        p = pathlib.Path(d) / 'player_draws_manifest.json'
        if not p.exists():
            continue
        m = json.loads(p.read_text())
        layers = {k: (v.get('row_ids') or [])
                  for k, v in (m.get('layers') or {}).items()
                  if v.get('row_axis') == 'gsis_id'}
        ids = set().union(*[set(v) for v in layers.values()]) if layers else set()
        out[m.get('game_id')] = {'by_layer': layers, 'ids': ids}
    return out


def _assess(game_id, cut, run, inactive_ids=()):
    u = PU.build(2026, 2, game_id, cut, emitted_ids=run['ids'],
                 inactive_ids=inactive_ids)
    if u.state is not State.PASS:
        return None, None
    return u.value, CV.assess(u.value, emitted_ids=run['ids'],
                              emitted_by_layer=run['by_layer'])


def test_every_player_lands_in_exactly_one_declared_state():
    runs = _runs('/tmp/claude-0/postinact/*/')
    if not runs:
        ok(True, 'no Week-2 1pm artifacts in this checkout')
        return
    gid = sorted(runs)[0]
    u = PU.build(2026, 2, gid, CUT_1PM, emitted_ids=runs[gid]['ids'])
    ok(u.state is State.PASS, f'the universe builds for {gid}: {u.code}')
    rows = u.value
    ok(rows, f'{len(rows)} player(s) in the point-in-time universe')
    bad = [r for r in rows if r['support_state'] not in S.FOOTBALL_STATES]
    ok(not bad, f'every row carries a declared state; undeclared: {len(bad)}')
    ok(u.evidence['n_unaccounted'] == 0,
       'no player is unaccounted for')
    ok(all(r['support_state_why'] for r in rows),
       'and every state carries a reason in prose')


def test_min_chi_one_club_vanishes_inside_a_valid_layer():
    runs = _runs('/tmp/claude-0/postinact/*/')
    if '2026_02_MIN_CHI' not in runs:
        ok(True, 'MIN@CHI artifact not in this checkout')
        return
    run = runs['2026_02_MIN_CHI']
    ok(len(run['by_layer'].get('receiving') or []) > 0,
       'the receiving LAYER is present -- P0-A has nothing to refuse')
    _, c = _assess('2026_02_MIN_CHI', CUT_1PM, run)
    ok(c.state is State.FAIL, f'coverage REFUSES the game: {c.code}')
    offs = (c.evidence or {}).get('offences') or []
    layers = {o['layer'] for o in offs if o.get('layer')}
    clubs = {o['club'] for o in offs}
    ok('receiving' in layers,
       f'and names the layer the club is missing from: {sorted(layers)}')
    ok(clubs == {'CHI'},
       f'and names ONLY the club that vanished: {sorted(clubs)}')
    ok((c.evidence or {}).get('PER_CLUB_LAYER_COVERAGE')
       == 'PER_CLUB_LAYER_COVERAGE_INCOMPLETE',
       'the per-club-layer gate is the one that fails')


def test_phi_ten_both_clubs_lose_the_skill_layers():
    runs = _runs('/tmp/claude-0/postinact/*/')
    if '2026_02_PHI_TEN' not in runs:
        ok(True, 'PHI@TEN artifact not in this checkout')
        return
    _, c = _assess('2026_02_PHI_TEN', CUT_1PM, runs['2026_02_PHI_TEN'])
    ok(c.state is State.FAIL, f'coverage REFUSES the game: {c.code}')
    offs = (c.evidence or {}).get('offences') or []
    ok({o['club'] for o in offs} == {'PHI', 'TEN'},
       'both clubs are named, not just the game')


def test_the_sound_games_still_pass():
    """A coverage gate that refuses everything discriminates nothing."""
    runs = _runs('/tmp/claude-0/postinact/*/')
    if not runs:
        ok(True, 'no Week-2 1pm artifacts in this checkout')
        return
    verdicts = {}
    for gid, run in runs.items():
        _, c = _assess(gid, CUT_1PM, run)
        verdicts[gid] = c.state.name
    failed = sorted(g for g, v in verdicts.items() if v == 'FAIL')
    ok(failed == ['2026_02_MIN_CHI', '2026_02_PHI_TEN'],
       f'exactly the two known-bad games fail: {failed}')
    ok(len(verdicts) - len(failed) == len(verdicts) - 2,
       f'{len(verdicts) - len(failed)} of {len(verdicts)} games pass coverage')


def test_a_salary_row_player_with_no_football_row_is_named():
    """Davon Booth. He must not be absent; he must be a state."""
    runs = _runs('/tmp/claude-0/indkc_pi/*/')
    if not runs:
        ok(True, 'IND@KC post-inactives artifact not in this checkout')
        return
    run = next(iter(runs.values()))
    u = PU.build(2026, 2, '2026_02_IND_KC', CUT_SNF, emitted_ids=run['ids'])
    booth = [r for r in u.value if r['display_name'] == 'Davon Booth']
    ok(len(booth) == 1, 'Davon Booth appears in the universe exactly once')
    if not booth:
        return
    b = booth[0]
    ok(b['gsis_id'] not in run['ids'],
       'the model emitted NO football row for him')
    ok(b['support_state'] in S.FOOTBALL_STATES,
       f'and he carries a named state rather than absence: '
       f'{b["support_state"]}')
    ok(b['support_state'] == S.ROSTERED_BUT_NOT_EXPECTED_TO_PARTICIPATE
       and b['roster_status'] == 'DEV',
       f'which the roster vintage justifies: status={b["roster_status"]!r} '
       f'(practice squad), NOT an inference from his absence from the '
       f'inactive list')
    ok(b['support_state'] != S.OFFICIALLY_INACTIVE,
       'and he is not mislabelled inactive -- he was on neither club list')


def test_football_identity_and_salary_identity_are_separate_axes():
    """Ogletree. A DK name that will not resolve is not a missing forecast."""
    runs = _runs('/tmp/claude-0/indkc_pi/*/')
    if not runs:
        ok(True, 'IND@KC post-inactives artifact not in this checkout')
        return
    run = next(iter(runs.values()))
    # Salary resolution deliberately EXCLUDES him, as DraftKings' "Drew
    # Ogletree" failed to resolve against the club-declared "Andrew".
    resolved = {r for r in run['ids']} - {'00-0037292'}
    u = PU.build(2026, 2, '2026_02_IND_KC', CUT_SNF, emitted_ids=run['ids'],
                 salary_resolved_ids=resolved)
    og = [r for r in u.value if r['gsis_id'] == '00-0037292']
    ok(len(og) == 1, 'Andrew Ogletree appears in the football universe')
    if not og:
        return
    o = og[0]
    ok(o['support_state'] == S.PROJECTED,
       f'his FOOTBALL state is {o["support_state"]} -- the model has him')
    ok(o.get('salary_identity_state') == S.SALARY_IDENTITY_UNRESOLVED,
       f'his SALARY identity is {o.get("salary_identity_state")}')
    ok('salary' not in o['support_state'].lower(),
       'the salary failure did not become the football state')
    others = [r for r in u.value if r['gsis_id'] in resolved
              and r['support_state'] == S.PROJECTED]
    ok(others, 'and resolved-salary players keep their own football states')


def test_officially_inactive_players_own_nothing_playable():
    runs = _runs('/tmp/claude-0/indkc_pi/*/')
    if not runs:
        ok(True, 'IND@KC post-inactives artifact not in this checkout')
        return
    run = next(iter(runs.values()))
    state_path = pathlib.Path('/tmp/claude-0/indkc_inactives.json')
    if not state_path.exists():
        ok(True, 'no official inactive state file in this checkout')
        return
    inact = {r['gsis_id'] for r in
             json.loads(state_path.read_text())['resolved']}
    u = PU.build(2026, 2, '2026_02_IND_KC', CUT_SNF, emitted_ids=run['ids'],
                 inactive_ids=inact)
    g = CV.assert_no_inactive_survives(u.value, emitted_ids=run['ids'])
    ok(g.state is State.PASS and g.evidence.get('certified') is True,
       f'{g.code}: {len(inact)} declared, none survived')

    # ABSENT EVIDENCE IS NOT A CLEAN BOARD.
    u2 = PU.build(2026, 2, '2026_02_IND_KC', CUT_SNF, emitted_ids=run['ids'])
    g2 = CV.assert_no_inactive_survives(u2.value, emitted_ids=run['ids'])
    ok(g2.code == 'NO_OFFICIAL_INACTIVE_EVIDENCE'
       and g2.evidence.get('certified') is False,
       f'with no declarations the board is NOT certified: {g2.code}')

    # A SEEDED SURVIVOR MUST BE CAUGHT.
    seeded = set(run['ids'])
    one = sorted(seeded)[0]
    u3 = PU.build(2026, 2, '2026_02_IND_KC', CUT_SNF, emitted_ids=seeded,
                  inactive_ids={one})
    g3 = CV.assert_no_inactive_survives(u3.value, emitted_ids=seeded)
    ok(g3.state is State.FAIL
       and g3.code == 'OFFICIALLY_INACTIVE_PLAYER_IN_PLAYABLE_BOARD',
       f'an inactive player who owns a row is refused: {g3.code}')


def test_walker_and_vansumeren_are_present_and_workload_is_untouched():
    """P0-B states WHO exists. It must not state who should get the ball."""
    runs = _runs('/tmp/claude-0/indkc_pi/*/')
    if not runs:
        ok(True, 'IND@KC post-inactives artifact not in this checkout')
        return
    run = next(iter(runs.values()))
    u = PU.build(2026, 2, '2026_02_IND_KC', CUT_SNF, emitted_ids=run['ids'])
    by = {r['display_name']: r for r in u.value}
    for nm in ('Kenneth Walker III', 'Ben VanSumeren'):
        r = by.get(nm)
        ok(r is not None, f'{nm} is in the universe')
        if not r:
            continue
        ok(r['support_state'] == S.PROJECTED,
           f'{nm}: state {r["support_state"]}')
        ok(r['depth_pos_abb'] and r['depth_rank'],
           f'{nm}: depth evidence attached -- {r["depth_pos_abb"]} rank '
           f'{r["depth_rank"]} (dt {r["depth_dt"]})')
    w, v = by.get('Kenneth Walker III'), by.get('Ben VanSumeren')
    if w and v:
        ok(w['depth_pos_abb'] == 'RB' and v['depth_pos_abb'] == 'FB',
           'the club depth chart distinguishes them: Walker RB, '
           'VanSumeren FB')
        ok(not any(k for k in v
                   if any(t in k for t in ('carr', 'target', 'snap', 'share',
                                           'workload', 'fantasy', 'dk_'))),
           'and NO workload, target, snap, share or fantasy field exists on '
           'a universe row -- role allocation is not P0-B\'s to answer')


def test_the_two_club_gates_are_independent():
    """A layer-only failure must not make the POSITION gate read incomplete.

    Both verdicts read one shared `offences` list, so `club_gate` flipped on
    any offence at all. A fully covered position grid was reported incomplete
    whenever `receiving` or `rushing` failed, which sends a reader to the
    wrong defect.
    """
    rows = [{'game_id': 'G', 'team': 'AAA', 'gsis_id': f'p{i}',
             'display_name': 'X', 'roster_position': pos,
             'support_state': S.PROJECTED, 'support_state_why': 'seeded',
             'roster_status': 'ACT'}
            for i, pos in enumerate(('WR', 'QB', 'RB', 'TE'), 1)]
    ids = {'p1', 'p2', 'p3', 'p4'}

    # Every POSITION covered; only the receiving LAYER is empty.
    c = CV.assess(rows, emitted_ids=ids,
                  emitted_by_layer={'receiving': [], 'rushing': ['p3'],
                                    'qb': ['p2']})
    e = c.evidence or {}
    v = e.get('value') or {}
    ok(e.get('PER_CLUB_POSITION_COVERAGE')
       == 'PER_CLUB_POSITION_COVERAGE_COMPLETE',
       f'position gate unaffected by a layer-only failure: '
       f'{e.get("PER_CLUB_POSITION_COVERAGE")}')
    ok(e.get('PER_CLUB_LAYER_COVERAGE')
       == 'PER_CLUB_LAYER_COVERAGE_INCOMPLETE',
       f'layer gate reports the real failure: '
       f'{e.get("PER_CLUB_LAYER_COVERAGE")}')
    ok(not v.get('position_offences') and len(v.get('layer_offences') or []) == 1,
       f'offence sets are separate: position={len(v.get("position_offences") or [])} '
       f'layer={len(v.get("layer_offences") or [])}')

    # And the converse: a position-only failure must not blame the layer gate.
    c2 = CV.assess(rows, emitted_ids={'p1', 'p2', 'p4'},
                   emitted_by_layer={'receiving': ['p1', 'p4'],
                                     'rushing': ['p3'], 'qb': ['p2']})
    e2 = c2.evidence or {}
    ok(e2.get('PER_CLUB_POSITION_COVERAGE')
       == 'PER_CLUB_POSITION_COVERAGE_INCOMPLETE',
       'a position-only failure fails the position gate')
    ok(e2.get('PER_CLUB_LAYER_COVERAGE')
       == 'PER_CLUB_LAYER_COVERAGE_COMPLETE',
       f'and leaves the layer gate complete: '
       f'{e2.get("PER_CLUB_LAYER_COVERAGE")}')


def test_absent_inactive_evidence_is_not_a_pass():
    """A green state carrying certified=False is the shape we abolished."""
    rows = [{'game_id': 'G', 'team': 'AAA', 'gsis_id': 'p1',
             'display_name': 'X', 'roster_position': 'WR',
             'support_state': S.PROJECTED, 'support_state_why': 'seeded',
             'roster_status': 'ACT'}]
    g = CV.assert_no_inactive_survives(rows, emitted_ids={'p1'})
    ok(g.state is not State.PASS,
       f'no official inactive evidence does NOT return PASS: {g.state.name}')
    ok(g.code == 'NO_OFFICIAL_INACTIVE_EVIDENCE',
       f'and is named: {g.code}')
    ok(g.evidence.get('certified') is False,
       'and carries certified=False consistently with its state')

    # A certified board still passes, so the gate discriminates.
    rows2 = rows + [{'game_id': 'G', 'team': 'AAA', 'gsis_id': 'p9',
                     'display_name': 'Y', 'roster_position': 'TE',
                     'support_state': S.OFFICIALLY_INACTIVE,
                     'support_state_why': 'seeded', 'roster_status': 'ACT'}]
    g2 = CV.assert_no_inactive_survives(rows2, emitted_ids={'p1'})
    ok(g2.state is State.PASS and g2.evidence.get('certified') is True,
       f'a board with real declarations and no survivor passes: {g2.code}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_every_player_lands_in_exactly_one_declared_state,
              test_min_chi_one_club_vanishes_inside_a_valid_layer,
              test_phi_ten_both_clubs_lose_the_skill_layers,
              test_the_sound_games_still_pass,
              test_a_salary_row_player_with_no_football_row_is_named,
              test_football_identity_and_salary_identity_are_separate_axes,
              test_officially_inactive_players_own_nothing_playable,
              test_walker_and_vansumeren_are_present_and_workload_is_untouched,
              test_the_two_club_gates_are_independent,
              test_absent_inactive_evidence_is_not_a_pass):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
