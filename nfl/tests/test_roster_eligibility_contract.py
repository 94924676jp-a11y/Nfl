#!/usr/bin/env python3.12
"""The shared three-state roster-eligibility contract, Classic AND Showdown (owner OD-001 decision 1, 2026-10-14; P1-A).

  STATES   CONFIRMED_ELIGIBLE / CONFIRMED_INELIGIBLE / ELIGIBILITY_UNRESOLVED. A practice-squad (DEV) player is confirmed
           ineligible only when elevation evidence for the game was SUPPLIED and does not name him; with no elevation
           evidence he is unresolved. Before this, `elevations or ()` turned "no evidence" into "evidence of none".
  RULE     (OD-002, 2026-10-14) roster_eligibility.opportunity_withheld is the one function both pipelines apply before
           projection: CONFIRMED-ineligible players get no opportunity. UNRESOLVED players are kept in the forecast as the
           incumbent had him, labelled with the missing evidence, never selectable, and block a certified release while
           they carry material opportunity. Missing evidence is not evidence of absence.
  ZERO     an ineligible player's simulated usage is zero BEFORE lineup selection: Classic through role state ->
           proj_v1 -> the simulator's club shares; Showdown through role state -> proj_v1 -> the joint simulator's draws.
           Each has a control run with the withholding removed, which must give the same players nonzero usage (the test
           has power), and every other player must keep his status (nothing else moved).
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import roster_eligibility as E  # noqa: E402

PASSED = FAILED = 0
EXEMPT = 'LOGIC_TEST: frozen-slate fixture on today\'s tree; not a forecast (PIT-D1)'


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def _pool(*players):
    return {(n, c): {'pos': p, 'ids': [str(i)]} for i, (n, c, p) in enumerate(players)}


def _rosters(*rows):
    return [{'full_name': n, 'team': c, 'status': s} for n, c, s in rows]


POOL = _pool(('Act One', 'BUF', 'WR'), ('Dev Elevated', 'BUF', 'RB'), ('Dev Plain', 'BUF', 'WR'),
             ('Res Man', 'BUF', 'TE'), ('Exe Man', 'BUF', 'WR'), ('Cut Man', 'BUF', 'RB'), ('Ghost', 'BUF', 'WR'),
             ('Waived', 'BUF', 'RB'), ('Inactive', 'BUF', 'WR'), ('Bills', 'BUF', 'DST'))
ROST = _rosters(('Act One', 'BUF', 'ACT'), ('Dev Elevated', 'BUF', 'DEV'), ('Dev Plain', 'BUF', 'DEV'),
                ('Res Man', 'BUF', 'RES'), ('Exe Man', 'BUF', 'EXE'), ('Cut Man', 'BUF', 'CUT'),
                ('Waived', 'BUF', 'ACT'), ('Inactive', 'BUF', 'ACT'))
TX = {'Waived': 'waived 2026-10-13'}


def test_01_three_states_and_missing_evidence_is_unresolved():
    no_ev = E.classify(POOL, ROST, ['Inactive'], TX, None)
    ev = E.classify(POOL, ROST, ['Inactive'], TX, ['Dev Elevated'])
    empty_ev = E.classify(POOL, ROST, ['Inactive'], TX, [])
    S = lambda r, n: r[(n, 'BUF')]['eligibility_state']  # noqa: E731
    check(S(no_ev, 'Dev Plain') == E.ELIGIBILITY_UNRESOLVED,
          'DEV with NO elevation evidence supplied is ELIGIBILITY_UNRESOLVED, not confirmed ineligible')
    check(S(ev, 'Dev Plain') == E.CONFIRMED_INELIGIBLE,
          'DEV not named by SUPPLIED elevation evidence is CONFIRMED_INELIGIBLE')
    check(S(empty_ev, 'Dev Plain') == E.CONFIRMED_INELIGIBLE,
          'an empty elevation list is evidence (nobody elevated): CONFIRMED_INELIGIBLE')
    check(S(ev, 'Dev Elevated') == E.CONFIRMED_ELIGIBLE and ev[('Dev Elevated', 'BUF')]['eligible'],
          'DEV named by an elevation record is CONFIRMED_ELIGIBLE')
    check(S(no_ev, 'Act One') == E.CONFIRMED_ELIGIBLE and S(no_ev, 'Bills') == E.CONFIRMED_ELIGIBLE,
          'ACT and the team defence are CONFIRMED_ELIGIBLE')
    for n, why in (('Res Man', 'RESERVE'), ('Exe Man', 'EXEMPT_LIST'), ('Cut Man', 'RELEASED'), ('Waived', 'RELEASED'),
                   ('Inactive', 'GAME_DAY_INACTIVE')):
        check(S(no_ev, n) == E.CONFIRMED_INELIGIBLE and no_ev[(n, 'BUF')]['reason'] == why,
              f'{n}: CONFIRMED_INELIGIBLE ({no_ev[(n, "BUF")]["reason"]})')
    check(S(no_ev, 'Ghost') == E.ELIGIBILITY_UNRESOLVED, 'absent from the week capture is ELIGIBILITY_UNRESOLVED')
    # backward compatibility: the selection boolean is unchanged and stays fail-closed for every non-confirmed player
    check(all(v['eligible'] == (v['eligibility_state'] == E.CONFIRMED_ELIGIBLE) for v in no_ev.values()),
          'eligible is True exactly for CONFIRMED_ELIGIBLE: unresolved is never selectable')


def test_02_shared_rule_withholds_only_confirmed_ineligible():
    res = E.classify(POOL, ROST, ['Inactive'], TX, None)
    w = {n for n, _c in E.opportunity_withheld(res)}
    u = E.unresolved(res)
    check(w == {'Res Man', 'Exe Man', 'Cut Man', 'Waived'},
          f'no elevation evidence: only the CONFIRMED-ineligible are withheld; the inactive list keeps its own path ({sorted(w)})')
    check({n for n, _c in u} == {'Dev Elevated', 'Dev Plain', 'Ghost'},
          'missing evidence is not evidence of absence: DEV players without elevation records and a player absent '
          'from the capture are UNRESOLVED and NOT withheld (OD-002)')
    check(u[('Dev Plain', 'BUF')]['missing_evidence'].startswith('GAME_DAY_ELEVATION_RECORDS')
          and u[('Ghost', 'BUF')]['missing_evidence'].startswith('WEEK_ROSTER_ENTRY'),
          'each unresolved player names exactly which evidence is missing')
    w_ev = {n for n, _c in E.opportunity_withheld(E.classify(POOL, ROST, ['Inactive'], TX, ['Dev Elevated']))}
    check(w_ev == w | {'Dev Plain'} and not w_ev & {'Act One', 'Bills', 'Dev Elevated'},
          'with elevation records supplied, the non-elevated DEV player is confirmed ineligible and withheld; the '
          'elevated one and every confirmed-eligible player are not')
    for k, v in E.opportunity_withheld(res).items():
        st, _tier = E.withheld_status(v['eligibility_state'], v['reason'])
        check(st in AV.ABSENT_STATUSES and st not in AV.PRESENT_STATUSES, f'{k[0]}: {st} is an absence (zero opportunity)')
    try:
        E.withheld_status(E.ELIGIBILITY_UNRESOLVED, 'PRACTICE_SQUAD_NOT_ELEVATED')
        refused = False
    except ValueError:
        refused = True
    check(refused, 'asking for a withheld label for an UNRESOLVED player is an error: he is never withheld')
    check(E.withheld_status(E.CONFIRMED_INELIGIBLE, 'PRACTICE_SQUAD_NOT_ELEVATED')[0]
          == AV.PRACTICE_SQUAD_NOT_ELEVATED_CONFIRMED, 'a confirmed non-elevation has its own label')
    check(not hasattr(AV, 'ELIGIBILITY_UNRESOLVED_WITHHELD'), 'no "unresolved but withheld" absence status exists')


def test_03_no_caller_turns_missing_evidence_into_evidence():
    from nfl.tools import showdown_run_guards as G, showdown_tonight as T
    check(inspect.signature(G.upload_roster_eligibility).parameters['elevations'].default is None,
          'the release gate defaults elevations to None (no evidence), not ()')
    check(inspect.signature(T.roster_blocked).parameters['elevations'].default is None, 'roster_blocked defaults to None')
    bad = []
    for f in ('nfl/tools/showdown_tonight.py', 'nfl/tools/showdown_run_guards.py', 'nfl/tools/showdown_next_slate.py',
              'nfl/tools/classic_upload_verify.py', 'nfl/tools/classic_slate_state.py', 'nfl/tools/roster_eligibility.py'):
        src = (_REPO / f).read_text()
        for node in ast.walk(ast.parse(src)):
            # `elevations or ()` / `or []`, and `_ld('elevations', [])`, each turn "not supplied" into "nobody elevated"
            if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and len(node.values) == 2 \
                    and isinstance(node.values[0], ast.Name) and node.values[0].id == 'elevations' \
                    and isinstance(node.values[1], (ast.Tuple, ast.List)) and not node.values[1].elts:
                bad.append(f'{f}:{node.lineno}')
            if isinstance(node, ast.Call) and len(node.args) == 2 and isinstance(node.args[0], ast.Constant) \
                    and node.args[0].value == 'elevations' and isinstance(node.args[1], (ast.List, ast.Tuple)):
                bad.append(f'{f}:{node.lineno}')
    # the one legitimate `elevations or ()` is inside classify itself, AFTER elevation_evidence is recorded
    bad = [b for b in bad if not b.startswith('nfl/tools/roster_eligibility.py')]
    check(not bad, f'no production caller converts missing elevation evidence into an empty list ({bad})')
    src = inspect.getsource(T.run)
    check('withheld=True' in src and 'roster_eligibility_state=rbs' in src,
          'showdown_tonight applies the shared rule (opportunity_withheld) and passes the eligibility state to the state')


def _project(state, *, draws=False):
    """role_state -> proj_v1 (FOOTBALL_ONLY) -> optionally the joint simulator, all on temporary files inside the
    repository (the lineage stamp requires it), removed afterwards. Returns (proj rows, draws or None)."""
    from nfl.tools import proj_v1 as PV, role_state as RS, showdown_draws as SD
    (_REPO / 'runs').mkdir(exist_ok=True)
    d = pathlib.Path(tempfile.mkdtemp(prefix='elig_contract_', dir=_REPO / 'runs'))
    sp, rp, pp = d / 'S.json', d / 'R.json', d / 'P.json'
    sp.write_text(json.dumps(state, default=str))
    saved = (RS.POST, RS.OUT, PV.POST, PV.OUT, PV.ROLE, PV.SLATE_WEEK, PV.MARKET_ARM, SD.OUT)
    try:
        RS.POST, RS.OUT = sp, rp
        o = RS.run()
        if o.state.value != 'PASS':
            raise RuntimeError(f'role state {o.code} {o.detail}')
        PV.POST, PV.OUT, PV.ROLE, PV.SLATE_WEEK, PV.MARKET_ARM = sp, pp, rp, int(state['week']), 'FOOTBALL_ONLY'
        if PV.main() != 0:
            raise RuntimeError('proj_v1 refused')
        rows = json.loads(pp.read_text())['rows']
        dr = None
        if draws:
            SD.OUT = d / 'D.json'
            o = SD.build(str(pp), str(sp), n_sims=200)
            if o.state.value != 'PASS':
                raise RuntimeError(f'draws {o.code} {o.detail}')
            dr = o.value['draws']
        return rows, dr
    finally:
        RS.POST, RS.OUT, PV.POST, PV.OUT, PV.ROLE, PV.SLATE_WEEK, PV.MARKET_ARM, SD.OUT = saved
        shutil.rmtree(d, ignore_errors=True)


def _club_shares(rows):
    from nfl.tools import showdown_draws as SD
    from nfl.tools import showdown_to_portfolio as S
    vals = list(rows.values())
    return {s['id']: s for c in {r.get('team') for r in vals} for s in SD._shares(vals, c)}, S.player_key


def _classic_w5(elevations=None):
    """The W5 Classic state, optionally with an elevation-evidence file supplied (a temporary JSON list)."""
    from nfl.dfs.salaries import early_only as EO
    from nfl.tools import classic_slate_state as CS
    real = EO.slate_files
    tmp = None
    if elevations is not None:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='elev_')) / 'ELEVATIONS.json'
        tmp.write_text(json.dumps(elevations))
        EO.slate_files = lambda sid: {**real(sid), 'elevations': str(tmp)}
    try:
        return CS.build('2026W5', as_of='2026-10-11T14:30:00Z', write=False, pit_exempt=EXEMPT)
    finally:
        EO.slate_files = real
        if tmp:
            shutil.rmtree(tmp.parent, ignore_errors=True)


def test_04_classic_confirmed_ineligible_zero_unresolved_kept():
    from nfl.dfs.salaries import early_only as EO
    files = EO.slate_files('2026W5')
    if not files.get('roster_capture') or not (_REPO / files['roster_capture']).is_file():
        check(False, 'BLOCKED: the W5 roster capture is not in this checkout (the fixture is required)')
        return
    o = _classic_w5()
    if not check(o.state.value == 'PASS', f'fixture: the W5 Classic state builds ({o.state.value} {o.code})'):
        return
    st, doc = o.value, o.value['roster_eligibility']
    U, W = doc['unresolved'], doc['withheld']
    check(doc['applied'] and doc['elevation_evidence_supplied'] is False, 'W5 declares no elevation evidence')
    check(len(U) > 0 and all(st['players'][dk]['current_availability']['status'] not in AV.ABSENT_STATUSES for dk in U),
          f'its practice-squad players are UNRESOLVED and kept in the forecast, not withheld ({len(U)})')
    check(all(st['players'][dk]['current_availability']['eligibility_state'] == E.ELIGIBILITY_UNRESOLVED
              and st['players'][dk]['current_availability']['eligibility_missing_evidence'] for dk in U),
          'each carries the unresolved state and the missing evidence on the player record')
    # RES / EXE / CUT on the capture, with no corroboration filter (OD-002): confirmed ineligible, absent
    res_ids = [dk for dk, v in st['players'].items()
               if v['current_availability'].get('roster_status_captured') in AV.ROSTER_STATUSES_NOT_ACTIVE]
    absent_res = [dk for dk in res_ids if st['players'][dk]['current_availability']['status'] in AV.ABSENT_STATUSES]
    conflict = [dk for dk in res_ids if st['players'][dk]['current_availability']['eligibility_state'] == 'ELIGIBILITY_CONFLICT']
    check(len(absent_res) + len(conflict) == len(res_ids) and len(absent_res) > 5,
          f'every RES/EXE/CUT player is absent ({len(absent_res)}) or a recorded conflict ({len(conflict)}); '
          f'the corroboration list no longer filters ({len(res_ids)})')
    check(len(conflict) == len(doc['conflicts']) > 0 and all(st['players'][dk]['current_availability']['status']
                                                            not in AV.ABSENT_STATUSES for dk in conflict),
          f'a reported activation against a RES capture is an ELIGIBILITY_CONFLICT, left as the incumbent had him '
          f'({[st["players"][dk]["name"] for dk in conflict]})')
    rows, _ = _project(st)
    sh, pk = _club_shares(rows)
    leak = [st['players'][dk]['name'] for dk in absent_res if isinstance((rows.get(dk) or {}).get('dk_points'), (int, float))]
    check(not leak, f'no confirmed-ineligible player is projected ({leak[:5]})')
    used = [st['players'][dk]['name'] for dk in absent_res if pk(st['players'][dk]['name'], st['players'][dk]['team']) in sh]
    check(not used, f'and none receives a share of club volume in the simulator ({used[:5]})')
    kept = [dk for dk in U if ((rows.get(dk) or {}).get('dk_points') or 0) > 0]
    check(len(kept) > 0, f'unresolved players keep their incumbent projection ({len(kept)} of {len(U)} projected)')
    # CONTROL: the confirmed-ineligible put back. The zero must be the rule's doing.
    ctl = copy.deepcopy(st)
    for dk in absent_res:
        ctl['players'][dk]['current_availability'].update(status=AV.UNKNOWN_ACTIVE_STATE, tier=AV.TIER_NONE)
    crows, _ = _project(ctl)
    powered = [st['players'][dk]['name'] for dk in absent_res if ((crows.get(dk) or {}).get('dk_points') or 0) > 0]
    check(len(powered) > 0, f'power: without the rule {len(powered)} of them would be projected ({powered[:4]})')
    # WITH elevation evidence (nobody elevated): the same practice-squad players become CONFIRMED_INELIGIBLE
    o2 = _classic_w5(elevations=[])
    d2 = o2.value['roster_eligibility']
    dev = [dk for dk, u in U.items() if u['reason'] == 'PRACTICE_SQUAD_NOT_ELEVATED']
    check(o2.state.value == 'PASS' and d2['elevation_evidence_supplied'] is True
          and all(dk in d2['withheld'] and o2.value['players'][dk]['current_availability']['status']
                  == AV.PRACTICE_SQUAD_NOT_ELEVATED_CONFIRMED for dk in dev if dk not in (d2.get('unresolved') or {})),
          'with elevation records supplied, non-elevated practice-squad players are confirmed ineligible and withheld')
    check(not [dk for dk in dev if dk in d2['unresolved']], 'and none of them remains unresolved')


def test_05_showdown_confirmed_ineligible_zero_unresolved_kept():
    from nfl.tests._pit import vintage_team_game
    from nfl.tools import showdown_slate_state as SSS, showdown_tonight as T
    R = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4'

    def build(rb=None, rbs=None):
        saved = SSS.OUT
        SSS.OUT = pathlib.Path(tempfile.mkdtemp(prefix='sss_elig_')) / saved.name
        try:
            with vintage_team_game('8feac0f3'):
                return SSS.build(R / 'DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv', roster_blocked=rb,
                                 roster_eligibility_state=rbs, pit_exempt=EXEMPT)
        finally:
            shutil.rmtree(SSS.OUT.parent, ignore_errors=True)
            SSS.OUT = saved
    base = build()
    if not check(base.state.value == 'PASS', f'fixture: the ATL@NO state builds ({base.state.value})'):
        return
    with vintage_team_game('8feac0f3'):
        brows, bdraws = _project(base.value, draws=True)
    ranked = sorted((r for r in brows.values() if r.get('position') in ('RB', 'WR', 'TE')
                     and isinstance(r.get('dk_points'), (int, float))), key=lambda r: -r['dk_points'])
    a, b = ranked[1], ranked[2]
    key = lambda r: f"{r['name']}|{r['team']}"  # noqa: E731
    rb = {a['name']: 'PRACTICE_SQUAD_NOT_ELEVATED'}
    rbs = {a['name']: E.CONFIRMED_INELIGIBLE, b['name']: E.ELIGIBILITY_UNRESOLVED}
    blk = build(rb, rbs)
    P = {v['name']: v for v in blk.value['players'].values()}
    check(P[a['name']]['current_availability']['status'] == AV.PRACTICE_SQUAD_NOT_ELEVATED_CONFIRMED,
          f'{a["name"]}: CONFIRMED_INELIGIBLE -> withheld before projection')
    check(P[b['name']]['current_availability']['status'] == base.value['players'][b['dk_id']]['current_availability']['status']
          and P[b['name']]['current_availability']['eligibility_state'] == E.ELIGIBILITY_UNRESOLVED,
          f'{b["name"]}: UNRESOLVED -> status unchanged, the state carried on the record')
    with vintage_team_game('8feac0f3'):
        rows, draws = _project(blk.value, draws=True)
    check(max(draws.get(key(a)) or [0]) == 0, f'{a["name"]}: zero simulated DK points in every world')
    check(max(bdraws.get(key(a)) or [0]) > 0, f'power: in the control {a["name"]} has nonzero draws')
    check(max(draws.get(key(b)) or [0]) > 0, f'{b["name"]}: the unresolved player keeps nonzero draws (not a false exclusion)')
    mat = T.unresolved_material({b['name']: {}}, draws)
    check(mat == [b['name']], f'the release gate names him as material ({mat})')
    check(T.unresolved_material({b['name']: {}}, {key(b): [0.0, 0.0]}) == [],
          'negative control: an unresolved player with all-zero draws is not material')
    src = inspect.getsource(T.run)
    check('ELIGIBILITY_UNRESOLVED_MATERIAL' in src and 'unresolved_material(' in src and 'NOT_POINT_IN_TIME_STATE' in src,
          'showdown_tonight.run applies the materiality gate and refuses a NOT_POINT_IN_TIME state')
    bp = {v['name']: v['current_availability']['status'] for v in base.value['players'].values()}
    moved = [n for n, s_ in bp.items() if n != a['name'] and P[n]['current_availability']['status'] != s_]
    check(not moved, f'negative control: no other player changes status ({moved[:5]})')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_') and callable(f):
            print(n)
            f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
