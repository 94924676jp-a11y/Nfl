"""SC-APPEAR-1 propagation: the research appearance gate against the production simulator.

What is guarded here, and why each one matters:

  * GATE OFF == PRODUCTION, BYTE FOR BYTE. The gated simulator is the production nfl/sim/game.py source with two
    substituted lines. With no gate keys, or with every pi = 1, its draws, stat lines and club worlds must equal the
    production simulate_game (and simulate_game_centred) exactly, on a synthetic game and on the frozen ATL@NO spec.
  * CLUB TOTALS CONSERVED. Under a gate that closes players, every world's player targets / carries / pass attempts
    still sum to that world's club totals, and the simulator's own seven identities still hold.
  * ELIGIBILITY IS NOT TOUCHED BY THE GATE. An inactive row never enters the pool even if it carries volume; a player
    whose gate is 0 never receives a target, carry, attempt or touchdown; no frozen ATL@NO inactive has worlds.
  * EMPTY OR MALFORMED INPUT IS REFUSED with a named error, never an empty success.
  * NO 2025 IN THE FIT, AND NO FUTURE IN A WEEK-W DRAW. Removing 2025 leaves every fitted object identical;
    perturbing week >= W outcomes leaves week-W draw-implied P(0) identical while the outcomes do change.
  * PRODUCTION IS NOT TOUCHED: production files hash the same, the research module assigns no production attribute.

Run standalone:  python3.12 nfl/tests/test_sc_appear_1_propagation.py
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_MOD = _REPO / 'nfl/research/appearance/sc_appear_1_propagation.py'
_spec = importlib.util.spec_from_file_location('sc_appear_1_propagation', _MOD)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
SIM, SD = M.SIM, M.SD

PASSED = FAILED = 0
_CACHE = {}
WEEK = 7


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')
    return bool(ok)


def _refused(fn, code):
    try:
        fn()
    except M.PropagationError as e:
        return e.code == code
    return False


def _model():
    if 'model' not in _CACHE:
        _CACHE['model'] = M.load_model()
    return _CACHE['model']


def _player(nm, club, pos, tg=0.0, car=0.0, pa=0.0, ptd=0.0, rtd=0.0):
    return {'id': f'{nm}|{club}', 'position': pos, 'target_share': tg, 'carry_share': car, 'pass_att_share': pa,
            'pass_td_share': ptd, 'rush_td_share': rtd, 'catch_rate': 0.65, 'slot': 'OTHER'}


def _fixture():
    """Two clubs whose shares are dyadic and sum to exactly 1.0, so no unit can fall into the ghost bucket."""
    clubs = []
    for c in ('HOM', 'AWY'):
        clubs.append({'club': c, 'dst_id': None, 'players': [
            _player('QB1', c, 'QB', pa=0.75, car=0.125, rtd=0.125),
            _player('QB2', c, 'QB', pa=0.25),
            _player('RB1', c, 'RB', tg=0.125, car=0.5, ptd=0.125, rtd=0.5),
            _player('RB2', c, 'RB', tg=0.125, car=0.25, ptd=0.125, rtd=0.25),
            _player('WR1', c, 'WR', tg=0.5, car=0.125, ptd=0.5, rtd=0.125),
            _player('WR2', c, 'WR', tg=0.25, ptd=0.25)]})
    return {'total_line': 44.0, 'home_spread': 1.5, 'clubs': clubs}


def _dump(v):
    return json.dumps({k: v.get(k) for k in ('draws', 'stat_draws', 'club_worlds', 'world_points',
                                              'club_scoring_worlds', 'unallocated_fraction')},
                      sort_keys=True, default=str)


def _atl():
    if 'atl' not in _CACHE:
        proj = json.loads((M.ATL_DIR / f'SHOWDOWN_{M.ATL_TAG}_PROJ.json').read_text())
        state = json.loads((M.ATL_DIR / f'SHOWDOWN_{M.ATL_TAG}_STATE.json').read_text())
        spec, centre = M.atl_spec(proj, state)
        _CACHE['atl'] = (proj, state, spec, centre)
    return _CACHE['atl']


# ----------------------------------------------------------------------------------------- identity
def test_gate_all_p1_is_byte_identical_to_production():
    m, G = _model(), M.gated()
    fx = _fixture()
    ones = {p['id']: {'targets': 1.0, 'carries': 1.0, 'pass_attempts': 1.0} for c in fx['clubs'] for p in c['players']}
    prod = SIM.simulate_game(m, fx, n_sims=400, seed=11, retain_stats=True)
    nog = G.simulate_game(m, copy.deepcopy(fx), n_sims=400, seed=11, retain_stats=True)
    one = G.simulate_game(m, M.with_gates(fx, ones), n_sims=400, seed=11, retain_stats=True)
    check(prod.state.value == 'PASS' and nog.state.value == 'PASS' and one.state.value == 'PASS',
          'production and gated simulators both PASS their identities on the fixture')
    check(_dump(prod.value) == _dump(nog.value), 'no gate keys: draws, stat lines and club worlds byte-identical')
    check(_dump(prod.value) == _dump(one.value), 'every pi = 1: draws, stat lines and club worlds byte-identical')
    proj, state, spec, centre = _atl()
    ones = {p['id']: {'targets': 1.0, 'carries': 1.0, 'pass_attempts': 1.0} for c in spec['clubs'] for p in c['players']}
    a = SIM.simulate_game_centred(m, spec, centre, n_sims=300, seed=M.ATL_SEED, n_calib=300)
    b = G.simulate_game_centred(m, M.with_gates(spec, ones), centre, n_sims=300, seed=M.ATL_SEED, n_calib=300)
    check(a.state.value == 'PASS' and _dump(a.value) == _dump(b.value)
          and json.dumps(a.value['volume_centre'], sort_keys=True) == json.dumps(b.value['volume_centre'], sort_keys=True),
          'frozen ATL@NO spec, centred arm: all-pi=1 gated draws byte-identical to production (incl. centring)')
    check(len(a.value['draws']) == len(b.value['draws']) > 20, f'  ({len(a.value["draws"])} players compared)')


def test_frozen_atl_no_counts_reproduced_by_the_production_spec():
    proj, state, spec, centre = _atl()
    stats, _pts, meta = M.CR.load_worlds(M.ATL_DIR / f'SHOWDOWN_{M.ATL_TAG}_WORLDS.npz')
    o = SIM.simulate_game_centred(_model(), spec, centre, n_sims=M.ATL_N_SIMS, seed=M.ATL_SEED, n_calib=M.ATL_N_SIMS)
    fx = {f: i for i, f in enumerate(meta['fields'])}
    bad = []
    for i, k in enumerate(meta['keys']):
        a = np.asarray(o.value['stat_draws'][k], float)
        for s in ('pass_att', 'carries', 'targets', 'receptions'):
            if not np.array_equal(a[:, M.SIM_IX[s]], stats[i, :, fx[s]].astype(float)):
                bad.append(f'{k}:{s}')
    check(not bad, f'every per-world count in the frozen WORLDS.npz reproduced exactly ({len(meta["keys"])} players) {bad[:3]}')


# ------------------------------------------------------------------------------------- conservation
def test_team_totals_conserved_under_the_gate():
    m, G = _model(), M.gated()
    fx = _fixture()
    gates = {f'{n}|{c}': {'targets': p, 'carries': p, 'pass_attempts': p}
             for c in ('HOM', 'AWY') for n, p in (('QB2', 0.2), ('RB2', 0.4), ('WR2', 0.5), ('RB1', 0.9))}
    o = G.simulate_game(m, M.with_gates(fx, gates), n_sims=600, seed=3, retain_stats=True)
    check(o.state.value == 'PASS', 'gated simulator PASSES all seven simulator identities (VOLUME, YARDS, TD, ...)')
    worst = 0
    for c in fx['clubs']:
        cw = np.asarray(o.value['club_worlds'][c['club']], float)
        st = np.asarray([o.value['stat_draws'][p['id']] for p in c['players']], float)
        for col, j in (('pass_att', 0), ('carries', 1), ('targets', 2)):
            worst = max(worst, float(np.abs(st[:, :, M.SIM_IX[col]].sum(0) - cw[:, j]).max()))
    check(worst == 0.0, f'every world: player pass attempts, carries and targets sum EXACTLY to the club totals (max dev {worst})')
    prod = SIM.simulate_game(m, fx, n_sims=600, seed=3, retain_stats=True)
    z_g = np.mean(np.asarray(o.value['stat_draws']['WR2|HOM'], float)[:, M.SIM_IX['targets']] == 0)
    z_p = np.mean(np.asarray(prod.value['stat_draws']['WR2|HOM'], float)[:, M.SIM_IX['targets']] == 0)
    check(z_g > z_p + 0.3, f'the gate is live: WR2 zero-target worlds {z_p:.3f} ungated -> {z_g:.3f} gated (pi = 0.5)')
    se = (0.5 * 0.5 / 600) ** 0.5
    check(abs(z_g - 0.5) < 4 * se + 0.05, f'  and it lands near 1 - pi = 0.5 (allowing P(M=0|open) and 4 MC SE)')


# --------------------------------------------------------------------------------------- eligibility
def test_inactive_players_never_receive_volume():
    rows = [{'name': 'Starter', 'team': 'HOM', 'position': 'WR', 'dk_points': 12.0, 'targets': 8.0, 'receptions': 5.0},
            {'name': 'Quarter', 'team': 'HOM', 'position': 'QB', 'dk_points': 18.0, 'pass_attempts': 34.0, 'carries': 3.0},
            {'name': 'RuledOut', 'team': 'HOM', 'position': 'WR', 'dk_points': None, 'targets': 10.0,
             'projection_state': 'NOT_PLAYING_REPORTED_INACTIVE'}]
    pool = SD._shares(rows, 'HOM')
    check([p['id'] for p in pool] == ['Starter|HOM', 'Quarter|HOM'],
          'an inactive row carrying volume (adversarial) is outside the production share pool')
    check(abs(sum(p['target_share'] for p in pool) - 1.0) < 1e-12, '  and outside the share denominator')
    m, G = _model(), M.gated()
    fx = _fixture()
    gates = {'WR2|HOM': {'targets': 0.0, 'carries': 0.0, 'pass_attempts': 0.0},
             'RB2|AWY': {'targets': 0.0, 'carries': 0.0, 'pass_attempts': 0.0}}
    o = G.simulate_game(m, M.with_gates(fx, gates), n_sims=500, seed=9, retain_stats=True)
    for k in gates:
        a = np.asarray(o.value['stat_draws'][k], float)
        tot = a[:, [M.SIM_IX[f] for f in ('pass_att', 'carries', 'targets', 'rec_td', 'rush_td', 'pass_td')]].sum()
        check(tot == 0.0, f'{k} with pi = 0 receives no attempt, carry, target or touchdown in any of 500 worlds')
    atl = M.atl_no(resimulate=False)
    check(atl['inactive_rows_in_projection'] > 0 and atl['inactive_rows_with_draws_or_worlds'] == [],
          f'frozen ATL@NO: none of {atl["inactive_rows_in_projection"]} NOT_PLAYING rows has draws or worlds')


# ---------------------------------------------------------------------------------------- refusals
def test_empty_or_malformed_input_refused_with_named_error():
    m = _model()
    check(_refused(lambda: M.run_sim(m, {'clubs': []}, {}, 10, 1, False), 'EMPTY_GAME'), 'no clubs refused EMPTY_GAME')
    fx = _fixture()
    fx['clubs'][1]['players'] = []
    check(_refused(lambda: M.run_sim(m, fx, {}, 10, 1, True), 'EMPTY_GAME'), 'a club with no players refused EMPTY_GAME')
    src = M.SIM_FILE.read_text().replace("            ps = c['players']\n", "            ps = list(c['players'])\n")
    check(_refused(lambda: M.gated_simulator(src), 'GATE_ANCHOR_NOT_FOUND'),
          'a simulator source without the gate anchor refused GATE_ANCHOR_NOT_FOUND (no silent ungated run)')
    bad = M.with_gates(_fixture(), {'WR1|HOM': {'targets': 1.5}})
    check(_refused(lambda: M.gate_players(bad['clubs'][0]['players'], M.random.Random(1)),
                   'GATE_PROBABILITY_OUT_OF_RANGE'), 'pi = 1.5 refused GATE_PROBABILITY_OUT_OF_RANGE')
    proj, state, _s, _c = _atl()
    p2 = dict(proj, football_centre={})
    check(_refused(lambda: M.atl_spec(p2, state), 'ATL_NOT_FOOTBALL_ONLY'), 'projection with no football centre refused')
    check(_refused(lambda: M.find_line('nfl/sim/game.py', r'this_line_does_not_exist_anywhere'), 'TRACE_ANCHOR_MISSING'),
          'a trace anchor that production no longer carries refused TRACE_ANCHOR_MISSING')
    check(M.cohort_scores(M.pd.DataFrame({'actual': []})).get('state') == 'EMPTY_COHORT', 'empty cohort labelled, not scored')
    S = _setup()
    check(_refused(lambda: M.replay(S['ctx'], S['fitted'], m, weeks=[1, 2, 3], n_sims=50), 'NO_SCORED_UNITS'),
          'a replay that scores nothing refused NO_SCORED_UNITS, not returned empty')


# -------------------------------------------------------------------------------------------- leakage
def _setup():
    if 'ctx' in _CACHE:
        return _CACHE
    P2, F1 = M.P2, M.F1
    po = P2.PP.load_panel()
    panel, pos_of = po.value, P2.PP.position_index()
    d24 = F1._dressed(2024)
    fitted = P2.fit(panel, pos_of, d24)
    ctx = P2.context(panel, pos_of, 2025, F1._dressed(2025), snap_pos=P2._snap_positions(2025))
    ctx['snaps'], ctx['games'] = M._snaps(2025)
    _CACHE.update(panel=panel, pos_of=pos_of, d24=d24, fitted=fitted, ctx=ctx)
    return _CACHE


def _truncate(panel, last):
    return {'players': {g: {s: w for s, w in ss.items() if int(s) <= last} for g, ss in panel['players'].items()},
            'teams': {c: {s: w for s, w in ss.items() if int(s) <= last} for c, ss in panel['teams'].items()}}


def test_leakage_guard():
    S = _setup()
    f2 = M.P2.fit(_truncate(S['panel'], 2024), S['pos_of'], S['d24'])
    for k in ('depth', 'groups', 'rates', 'n_fit_rows'):
        check(f2[k] == S['fitted'][k], f'fitted {k} identical with every 2025+ row removed (the gate pi come from these)')
    ctx = S['ctx']
    pert = copy.deepcopy({'players': ctx['panel']['players'], 'teams': ctx['panel']['teams']})
    for g, ss in pert['players'].items():
        for w, d in (ss.get('2025') or {}).items():
            if int(w) >= WEEK:
                for f in ('targets', 'carries', 'pass_attempts'):
                    d[f] = (d.get(f) or 0) + 5
    for c, ss in pert['teams'].items():
        for w, d in (ss.get('2025') or {}).items():
            if int(w) >= WEEK:
                for f in ('targets', 'rush_attempts', 'pass_attempts', 'plays'):
                    d[f] = (d.get(f) or 0) * 3 + 7
    ctx2 = dict(ctx, panel=pert)
    a = M.replay(ctx, S['fitted'], _model(), weeks=[WEEK], n_sims=150, max_games=1)[0]
    b = M.replay(ctx2, S['fitted'], _model(), weeks=[WEEK], n_sims=150, max_games=1)[0]
    cols = ['gsis', 'field', 'p_cur', 'p_cand'] + [f'p0_{x}' for x in M.ARMS] + [f'mean_{x}' for x in M.ARMS]
    check(len(a) > 10 and a[cols].equals(b[cols]),
          f'week-{WEEK} projection and draw-implied P(0) identical after perturbing weeks >= {WEEK} ({len(a)} units)')
    check(not a.actual.equals(b.actual), '  while the perturbation did reach the realised outcomes (the test can fail)')


# --------------------------------------------------------------------------------- production untouched
def test_trace_grep_and_production_untouched():
    before = M.production_hashes()
    tr = M.trace()
    check(len(tr) == len(M.TRACE_ANCHORS) and all(re.match(r'nfl/.+\.py:\d+$', r['at']) for r in tr),
          f'all {len(tr)} five-state trace anchors located in production at file:line')
    states = {r['state'] for r in tr}
    check(states == {'ELIGIBILITY', 'OFFENSIVE_APPEARANCE', 'SPECIAL_TEAMS_ONLY_APPEARANCE', 'POSITIVE_OPPORTUNITY',
                     'POSITIVE_COUNT'}, 'the trace covers all five states')
    g = M.p_plays_grep()
    check(g['n_hits_on_draw_path'] == 0 and g['VERDICT'].startswith('CONFIRMED'),
          f'grep: no p_plays / appearance_rate read on the draw path ({len(g["files_searched"])} files searched)')
    G = M.gated_simulator()
    check(G.N_LINES_ADDED == 1 and G.SOURCE_SHA256 == hashlib.sha256(M.SIM_FILE.read_bytes()).hexdigest(),
          'gated simulator = production source + one added line + one substituted line, built from the file on disk')
    check(M.production_hashes() == before, 'no production file changed by building the gated simulator or the trace')
    tree = ast.parse(_MOD.read_text())
    bad = []
    prod_names = ('SIM', 'SD', 'CR', 'V', 'FP', 'S', 'P2', 'F1')
    for node in ast.walk(tree):
        tg = node.targets if isinstance(node, ast.Assign) else ([node.target] if isinstance(node, ast.AugAssign) else [])
        for t in tg:
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in prod_names:
                bad.append(f'{t.value.id}.{t.attr}')
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'setattr':
            bad.append('setattr')
    check(not bad, f'research module assigns no attribute on a production module {bad}')
    src = _MOD.read_text()
    check("'nfl/dfs" not in src.replace("'nfl/dfs/salaries/showdown_atl_no", '') and 'write_text' in src
          and all(('OUT.write_text' in ln) for ln in src.splitlines() if '.write_text(' in ln),
          'the only file the research module writes is its own JSON under nfl/research/appearance/')


def test_artifact_declared_before_scoring_and_shadow_only():
    p = M.OUT
    if not check(p.exists(), f'{p.name} exists (declaration is written before any score)'):
        return
    d = json.loads(p.read_text())
    check(d.get('STATUS') == 'SHADOW_ONLY', 'STATUS SHADOW_ONLY')
    check(d.get('declaration_sha256') == M._declaration_sha(M.DECLARATION) and d.get('DECLARATION') == M.DECLARATION,
          'the declaration on disk is the one in the module, hash-matched')
    check(d['DECLARATION']['PRIMARY']['comparison'] in M.COMPARISONS, 'the declared primary is a computed comparison')
    if str(d.get('PHASE', '')).startswith('SCORED'):
        check(d['scored_at'] > d['declared_at'], 'scored_at is after declared_at')
        check(d['production_files']['any_production_file_changed'] is False, 'no production file changed during the run')
        check(d['ACTIVE_ZERO_SNAP_COHORT'] == 'NOT_IDENTIFIABLE_FROM_CURRENT_DATA', 'active zero-snap cohort not imputed')
        txt = p.read_text().replace('PROSPECTIVELY_VALIDATED', '')
        hits = re.findall(r'\b(validated|unbiased|correct)\b', txt, flags=re.I)
        check(not hits, f'no unmargined adequacy words in the artifact {hits}')
    else:
        check(d.get('PHASE') == 'DECLARED_NOT_SCORED', 'not yet scored: phase says so')


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            print(name)
            fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
