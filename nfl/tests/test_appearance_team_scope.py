"""L6: an evidence gap about ONE team is scoped to that team, and nothing else.

WHAT IS BEING GUARDED

`layers.appearance` resolves readiness per team and then defers the WHOLE GAME
on the worst of them. On 2026_01_DEN_KC that cost Kansas City's thirteen
eligible skill players for a defect in Denver's injury filing: DEN carries one
injury row whose `report_status` is blank, KC carries eleven rows with two
designations, and the board reached quarterbacks only.

`football_engine.run_game` now resolves readiness at the CALL SITE and hands
`layers.appearance` the READY teams together with only those teams' players.
`layers.py` is hashed by Q9's frozen candidate identity `481f005f682cd721` and
is NOT edited -- that hash is asserted below.

THE TWO PROPERTIES THAT MAKE THIS SAFE, AND WHY BOTH ARE HERE

  1. THE GUARD STILL FIRES. Denver is still refused, with the same state and
     the same reason `readiness.team_readiness` produces, and not one Denver
     player reaches a modelled quantity. A missing designation is still not
     read as an absence of injury.

  2. WHEN EVERY TEAM IS READY, NOTHING CHANGES. `ateams` is initialised to
     `tuple(teams)` and reassigned in exactly ONE branch -- the mixed case --
     so on an all-READY game every downstream expression is textually the one
     that was there before. That is asserted structurally here AND behaviourally
     on a real both-READY game (2026_01_DAL_NYG under a 2026-09-13T20:00Z
     clock, both clubs READY against the captured feed).

     The BYTE-LEVEL version of property 2 -- replaying one captured set of
     `run_game` arguments through a pristine pre-repair copy of the engine and
     through this one and comparing every draw and every verdict -- needs a
     copy of the old file, which is not in the tree. It is therefore run on
     demand: set `L6_BASELINE_ENGINE` to a pre-repair `football_engine.py` and
     `test_i` executes it. Unset, it records a blocked() check and says so.
     It was run once during the repair and reported IDENTICAL; see
     nfl/research/remediation/l6/L6_APPEARANCE_TEAM_SCOPE.md.

WHAT IS DELIBERATELY NOT CLAIMED. This is not a draw-preserving change in the
mixed case and the tests do not pretend otherwise. Appearance consumes ONE
shared RNG stream across the player dict, so running it over Kansas City's
players alone produces different draws than a hypothetical both-teams run
would have. `test_h` asserts that this is stated in the artifact rather than
left for a reader to discover.
"""
from __future__ import annotations

import ast
import csv
import gzip
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import hashlib                                                    # noqa: E402

from sportsplatform.governance.outcome import State               # noqa: E402
from nfl.capture import coverage as COV                           # noqa: E402
from nfl.production.nonqb import football_engine as FE            # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402
from nfl.production.nonqb import readiness as RD                  # noqa: E402
from nfl.production.nonqb import vintage_selector as VS           # noqa: E402
from nfl.research.shadow import information_set as IS             # noqa: E402

PASSED = FAILED = BLOCKED = 0

# The Q9 prospective freeze pins this file. Recorded as the full digest, not a
# prefix: a prefix comparison is a weaker assertion for no benefit.
Q9_LAYERS_SHA256 = (
    '481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108')

# Both clubs READY against the captured injuries feed under this clock.
READY_GAME = ('2026_01_DAL_NYG', '2026-09-13T20:00:00Z')
# DEN INJURY_REPORT_INCOMPLETE (one row, report_status blank), KC READY.
SCOPED_GAME = ('2026_01_DEN_KC', '2026-09-14T16:30:00Z')
# BOTH clubs INJURY_REPORT_INCOMPLETE under this clock -- NE on 3 rows, SEA on
# 8, neither carrying a filed designation. There is nothing to scope TO.
NONE_READY_GAME = ('2026_01_NE_SEA', '2026-09-09T20:00:00Z')

ENGINE_SRC = pathlib.Path(_ROOT) / 'nfl' / 'production' / 'nonqb' / \
    'football_engine.py'
LAYERS_SRC = pathlib.Path(_ROOT) / 'nfl' / 'production' / 'nonqb' / 'layers.py'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def blocked(label, why):
    """Counted apart and never as a pass."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


# ------------------------------------------------------------------ helpers
_RUNS = {}


def _kickoff(game_id):
    p = COV.load_week_plan(2026, 1)
    if p.state is not State.PASS:
        return None
    for c in p.value:
        if c.game_id == game_id:
            k = c.kickoff_utc
            return (k.isoformat().replace('+00:00', 'Z')
                    if hasattr(k, 'isoformat') else k)
    return None


def _roster(game_id, kickoff_utc, written_at):
    """The same roster frame `make_board` builds, under the same clock."""
    away, home = game_id.split('_')[2:4]
    info = IS.build(kickoff_utc, observed_before=written_at)
    blob = info['sources']['weekly_rosters']['blob']
    rows = [r for r in csv.DictReader(
        gzip.open(pathlib.Path(_ROOT) / blob, 'rt'))
        if r['season'] == '2026' and r['week'] == '1'
        and r['team'] in (away, home)]
    return [{'gsis_id': r['gsis_id'], 'position': r['position'],
             'team': r['team']} for r in rows]


def engine_run(game_id, written_at, m=64):
    """One real `run_game` on real captured inputs. Cached, and read-only.

    `qb=None`, `tv=None`, `rushing_budget=None`: the quarterback composition is
    not what changed here and running it would make this test depend on layers
    it is not about. Everything the repair touches -- the receiver frame, the
    appearance call, the target and carry allocation frames, the rushing
    accounting frame -- executes.
    """
    key = (game_id, written_at, m)
    if key in _RUNS:
        return _RUNS[key]
    ko = _kickoff(game_id)
    if ko is None:
        _RUNS[key] = None
        return None
    try:
        players = _roster(game_id, ko, written_at)
    except (OSError, KeyError, ValueError):
        _RUNS[key] = None
        return None
    if not players:
        _RUNS[key] = None
        return None
    RD.cache_clear()
    with VS.clock(written_at=written_at, kickoff_utc=ko,
                  origin='test_appearance_team_scope'):
        fits = FE.slate_fits(2026, 1, players)
        if fits.state is not State.PASS:
            _RUNS[key] = None
            return None
        g, pay = FE.run_game(2026, 1, game_id, players, fits.value, m=m,
                             kickoff_utc=ko, run_id='l6-team-scope-test',
                             observed_before=written_at)
    _RUNS[key] = (g, pay, players, ko)
    return _RUNS[key]


def _run_game_ast():
    tree = ast.parse(ENGINE_SRC.read_text(encoding='utf-8'), str(ENGINE_SRC))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'run_game':
            return n
    return None


# =============================================== A. the frozen module holds
def test_a_the_frozen_layers_module_is_not_edited():
    """The whole design depends on this: the repair is at the CALL SITE."""
    print('\nA. layers.py is untouched')
    got = hashlib.sha256(LAYERS_SRC.read_bytes()).hexdigest()
    check('layers.py still hashes to the Q9 frozen candidate identity',
          got == Q9_LAYERS_SHA256, f'{got} != {Q9_LAYERS_SHA256}')
    src = LAYERS_SRC.read_text(encoding='utf-8')
    check('  and carries no trace of the call-site scoping',
          'ateams' not in src and 'team_scope' not in src)


# =============================== B. the readiness guard still fires for DEN
def test_b_the_readiness_guard_still_refuses_denver():
    """Scoping a refusal is not the same as removing it."""
    print('\nB. Denver is still refused, with the same code')
    ko = _kickoff(SCOPED_GAME[0])
    if ko is None:
        blocked('the week plan could not be loaded', 'WEEK_PLAN_UNAVAILABLE')
        return
    wa = SCOPED_GAME[1]
    RD.cache_clear()
    den = RD.team_readiness(2026, 1, 'DEN', kickoff_utc=ko, written_at=wa)
    kc = RD.team_readiness(2026, 1, 'KC', kickoff_utc=ko, written_at=wa)
    check('DEN is INJURY_REPORT_INCOMPLETE',
          den['state'] == 'INJURY_REPORT_INCOMPLETE', den['state'])
    check('  on exactly one injury row', den.get('n_rows') == 1,
          den.get('n_rows'))
    check('KC is READY', str(kc['state']).startswith('READY'), kc['state'])
    # The frozen layer, called the way it was called before this repair,
    # still defers the whole game. Nothing about the contract was loosened.
    with VS.clock(written_at=wa, kickoff_utc=ko, origin='l6-guard-test'):
        o = LY.appearance(2026, 1, [], teams=('DEN', 'KC'), kickoff_utc=ko,
                          m=8)
    check('layers.appearance on the unscoped pair still DEFERS',
          o.state is State.DEFERRED, f'{o.state.value}[{o.code}]')
    check('  with the same code', o.code == 'INJURY_REPORT_INCOMPLETE', o.code)


# ====================== C. all READY -> the unscoped frame, behaviourally
def test_c_both_teams_ready_leaves_the_frame_untouched():
    print('\nC. a both-READY game runs on the full frame, unscoped')
    r = engine_run(*READY_GAME)
    if r is None:
        blocked('the both-READY fixture could not be built',
                'captures or fitted artifacts unavailable')
        return
    g, pay, players, _ko = r
    away, home = READY_GAME[0].split('_')[2:4]
    check('the engine did not halt', g.get('halted_at') is None,
          g.get('halted_at'))
    check('no team-scope record was written',
          'appearance_team_scope' not in g and 'deferred_teams' not in g,
          sorted(k for k in g if 'scope' in k or 'defer' in k))
    ap = g['layer_outcomes']['appearance']
    check('  the appearance outcome carries no team_scope evidence',
          'team_scope' not in (ap.evidence or {}))
    check('  and raises no APPEARANCE_TEAM_DEFERRED warning',
          not any('APPEARANCE_TEAM_DEFERRED' in str(w)
                  for w in (ap.evidence.get('warnings') or [])))
    check('the allocation frame is both clubs',
          pay is not None and pay['index']['teams'] == [away, home],
          None if pay is None else pay['index']['teams'])
    want = [q['gsis_id'] for q in players
            if q['position'] in FE.RECEIVING_POS]
    check('  and every modelled-position player is in it',
          pay is not None and sorted(pay['index']['recv_ids']) == sorted(want),
          f'{0 if pay is None else len(pay["index"]["recv_ids"])} vs '
          f'{len(want)}')


# ====== D. the structural reason C implies byte-identity on an all-READY run
def test_d_ateams_is_reassigned_in_exactly_one_branch():
    """`ateams` differs from `teams` ONLY in the mixed case.

    This is the property that turns the behavioural check in C into a
    statement about every downstream expression: if `ateams == tuple(teams)`
    then each rewritten line is the line that was there before.
    """
    print('\nD. the scoping is confined to one branch')
    fn = _run_game_ast()
    if fn is None:
        check('run_game could not be parsed', False, 'RUN_GAME_NOT_FOUND')
        return
    parents = {}
    for node in ast.walk(fn):
        for kid in ast.iter_child_nodes(node):
            parents[kid] = node

    def ancestors(node):
        out = []
        while node in parents:
            node = parents[node]
            out.append(node)
        return out

    assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'ateams'
                       for t in n.targets)]
    check('`ateams` is assigned exactly twice', len(assigns) == 2,
          len(assigns))
    if len(assigns) != 2:
        return
    init, scoped = assigns
    check('  the initialiser is `tuple(teams)`',
          isinstance(init.value, ast.Call)
          and getattr(init.value.func, 'id', None) == 'tuple'
          and getattr(init.value.args[0], 'id', None) == 'teams',
          ast.dump(init.value)[:120])
    mixed = [a for a in ancestors(scoped) if isinstance(a, ast.If)
             and isinstance(a.test, ast.BoolOp)
             and isinstance(a.test.op, ast.And)
             and {getattr(v, 'id', None) for v in a.test.values}
             == {'_ready', '_notready'}]
    check('  the reassignment is inside `if _ready and _notready:`',
          len(mixed) == 1, len(mixed))
    real = [a for a in ancestors(scoped) if isinstance(a, ast.If)
            and isinstance(a.test, ast.Compare)
            and getattr(a.test.left, 'id', None) == 'injuries_rows'
            and isinstance(a.test.ops[0], ast.Is)]
    check('  and inside `if injuries_rows is None:`, so a TEST-ONLY fixture '
          'never reaches it', len(real) == 1, len(real))
    probes = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
              and getattr(n.func, 'attr', None) == 'team_readiness']
    check('  readiness is probed exactly once in run_game', len(probes) == 1,
          len(probes))
    check('  and that probe is on the real path only',
          bool(probes) and any(
              isinstance(a, ast.If) and isinstance(a.test, ast.Compare)
              and getattr(a.test.left, 'id', None) == 'injuries_rows'
              for a in ancestors(probes[0])))


# ===================== E. the mixed case: DEN deferred by name, KC modelled
def test_e_denver_is_deferred_by_name_and_kansas_city_is_modelled():
    print('\nE. DEN@KC: the refusal is scoped to Denver')
    r = engine_run(*SCOPED_GAME)
    if r is None:
        blocked('the DEN@KC fixture could not be built',
                'captures or fitted artifacts unavailable')
        return
    g, pay, players, ko = r
    check('the engine did not halt', g.get('halted_at') is None,
          g.get('halted_at'))
    ap = g['layer_outcomes']['appearance']
    check('the appearance layer PASSES for the ready club',
          ap.state is State.PASS, f'{ap.state.value}[{ap.code}]')
    sc = g.get('appearance_team_scope')
    check('a team-scope record exists', isinstance(sc, dict))
    if not isinstance(sc, dict):
        return
    check('  it is named', sc.get('code') == 'APPEARANCE_TEAM_DEFERRED',
          sc.get('code'))
    check('  the ready frame is KC only', sc.get('ready_teams') == ['KC'],
          sc.get('ready_teams'))
    d = {x['team']: x for x in sc['deferred_teams']}
    check('  Denver is the deferred club', list(d) == ['DEN'], list(d))
    if 'DEN' not in d:
        return
    RD.cache_clear()
    live = RD.team_readiness(2026, 1, 'DEN', kickoff_utc=ko,
                             written_at=SCOPED_GAME[1])
    check('  carrying the state readiness produces',
          d['DEN']['state'] == live['state'],
          f"{d['DEN']['state']} != {live['state']}")
    check('  and the reason readiness produces, verbatim',
          d['DEN']['reason'] == live['reason'])
    check('  every excluded player is named by gsis_id',
          len(d['DEN']['gsis_ids']) == d['DEN']['n_players_excluded']
          and d['DEN']['n_players_excluded'] > 0,
          d['DEN']['n_players_excluded'])
    # NOT ONE DENVER PLAYER REACHES A MODELLED QUANTITY.
    den_ids = {q['gsis_id'] for q in players if q['team'] == 'DEN'}
    check('no Denver player is in the allocation frame',
          pay is not None and not (set(pay['index']['recv_ids']) & den_ids),
          None if pay is None else
          sorted(set(pay['index']['recv_ids']) & den_ids)[:5])
    check('  nor in the carry frame',
          pay is not None and not (set(pay['index']['rb_ids']) & den_ids))
    check('  nor in the player records',
          not (den_ids & {rec['gsis_id'] for rec in (pay or {}).get(
              'records', []) if 'gsis_id' in rec}))
    kc_ids = {q['gsis_id'] for q in players if q['team'] == 'KC'
              and q['position'] in FE.RECEIVING_POS}
    got = set(pay['index']['recv_ids']) if pay else set()
    check('every eligible Kansas City player IS modelled',
          got == kc_ids and len(got) > 0, f'{len(got)} of {len(kc_ids)}')


# ========================= F. the scoping introduces no new engine layer key
def test_f_no_new_engine_layer_is_introduced():
    """A new `g['layers']` key would raise ENGINE_LAYER_NOT_REPORTED in
    `run_forecast._assert_every_layer_is_reported`, which is that guard
    working. The record lives on `g` and on the appearance evidence instead."""
    print('\nF. no engine layer nobody reports')
    a = engine_run(*READY_GAME)
    b = engine_run(*SCOPED_GAME)
    if a is None or b is None:
        blocked('both fixtures are needed to compare layer key sets',
                'a fixture could not be built')
        return
    ga, gb = a[0], b[0]
    check('the scoped run declares no layer the unscoped run does not',
          set(gb['layers']) <= set(ga['layers']),
          sorted(set(gb['layers']) - set(ga['layers'])))
    # `_lay` writes both forms from one source, so every real Outcome must
    # also be a declared layer. The reverse does not hold and never did:
    # `game_coupling`, `shared_pass`, `rushing_budget_owner` and
    # `carry_other_denominator` are written straight into `g['layers']` as
    # labels. That asymmetry predates this repair and is not what is being
    # guarded here; what is guarded is that the scoping adds to neither side.
    for name, g in (('unscoped', ga), ('scoped', gb)):
        check(f'  {name}: every recorded Outcome is a declared layer',
              set(g['layer_outcomes']) <= set(g['layers']),
              sorted(set(g['layer_outcomes']) - set(g['layers'])))
    check('  the two runs declare the same layer_outcome keys',
          set(ga['layer_outcomes']) == set(gb['layer_outcomes']),
          sorted(set(ga['layer_outcomes']) ^ set(gb['layer_outcomes'])))
    check('  the scope record is not a layer',
          'appearance_team_scope' not in gb['layers'])


# ================ G. every modelled player belongs to a team we have evidence on
def test_g_every_modelled_player_belongs_to_a_ready_team():
    print('\nG. nothing is modelled for a team whose report is unfiled')
    r = engine_run(*SCOPED_GAME)
    if r is None:
        blocked('the DEN@KC fixture could not be built', 'unavailable')
        return
    g, pay, players, _ko = r
    if pay is None:
        check('a payload was produced', False, 'NO_PAYLOAD')
        return
    ready = set((g.get('appearance_team_scope') or {}).get('ready_teams') or
                g['teams'])
    team_of = {q['gsis_id']: q['team'] for q in players}
    off = sorted({team_of.get(p) for p in pay['index']['recv_ids']} - ready)
    check('every receiving row is a ready club', not off, off)
    offr = sorted({team_of.get(p) for p in pay['index']['rb_ids']} - ready)
    check('every carry row is a ready club', not offr, offr)


# ============================ H. the RNG consequence is stated, not implied
def test_h_the_shared_stream_consequence_is_recorded():
    """`_game_stream` gives the game ONE appearance stream, consumed
    sequentially across the player dict. Narrowing the dict therefore changes
    the draws. There is no both-teams run tonight to perturb -- the unscoped
    code produces nothing for this game -- but the claim "KC's draws are the
    same either way" is FALSE and the artifact has to say so."""
    print('\nH. the mixed case does not claim to preserve draws')
    r = engine_run(*SCOPED_GAME)
    if r is None:
        blocked('the DEN@KC fixture could not be built', 'unavailable')
        return
    sc = (r[0].get('appearance_team_scope') or {})
    note = str(sc.get('rng_note') or '')
    check('the scope record carries an RNG note', bool(note))
    check('  and it says the draws are not the both-teams draws',
          'not the draws' in note or 'not be the draws' in note, note[:120])
    warn = [w for w in
            (r[0]['layer_outcomes']['appearance'].evidence.get('warnings')
             or []) if 'APPEARANCE_TEAM_DEFERRED' in str(w)]
    check('the deferral reaches the layer warnings, which run_forecast seals',
          len(warn) == 1, len(warn))
    check('  and names the club and its state',
          bool(warn) and 'DEN' in warn[0]
          and 'INJURY_REPORT_INCOMPLETE' in warn[0])


# ========================== I. byte identity against a pre-repair engine
def test_i_byte_identity_against_a_pristine_baseline():
    """Run on demand: `L6_BASELINE_ENGINE=<pre-repair football_engine.py>`.

    The captured-argument replay is the strongest form of the all-READY
    property, and it needs a copy of the file as it stood before the repair,
    which the tree does not carry. Rather than assert nothing, this records a
    blocked() check naming exactly what would make it run.
    """
    print('\nI. byte identity against the pre-repair engine')
    base = os.environ.get('L6_BASELINE_ENGINE')
    if not base or not os.path.exists(base):
        blocked('no pre-repair engine supplied',
                'set L6_BASELINE_ENGINE=<path to the pre-repair '
                'football_engine.py> to execute this replay')
        return
    import copy as _copy
    import importlib.util
    import json as _json
    import numpy as _np
    spec = importlib.util.spec_from_file_location('l6_baseline_engine', base)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['l6_baseline_engine'] = mod
    spec.loader.exec_module(mod)
    r = engine_run(*READY_GAME)
    if r is None:
        blocked('the both-READY fixture could not be built', 'unavailable')
        return
    _g, _pay, players, ko = r

    def canon(o):
        from sportsplatform.governance.outcome import Outcome as _O
        if isinstance(o, _O):
            return {'s': o.state.value, 'c': o.code, 'd': o.detail,
                    'e': canon(dict(o.evidence)), 'v': canon(o.value)}
        if isinstance(o, _np.ndarray):
            return [list(o.shape), str(o.dtype), hashlib.sha256(
                _np.ascontiguousarray(o).tobytes()).hexdigest()]
        if isinstance(o, _np.generic):
            return o.item()
        if isinstance(o, dict):
            return {str(k): canon(v)
                    for k, v in sorted(o.items(), key=lambda x: str(x[0]))}
        if isinstance(o, (list, tuple)):
            return [canon(x) for x in o]
        if isinstance(o, (str, int, float, bool)) or o is None:
            return o
        return repr(o)

    def once(engine):
        RD.cache_clear()
        with VS.clock(written_at=READY_GAME[1], kickoff_utc=ko,
                      origin='test_appearance_team_scope'):
            fits = engine.slate_fits(2026, 1, _copy.deepcopy(players))
            gg, pp = engine.run_game(
                2026, 1, READY_GAME[0], _copy.deepcopy(players), fits.value,
                m=64, kickoff_utc=ko, run_id='l6-team-scope-test',
                observed_before=READY_GAME[1])
        return _json.dumps([canon(gg), canon(pp)], sort_keys=True)

    old, new = once(mod), once(FE)
    check('a both-READY game is bit-identical to the pre-repair engine',
          old == new,
          f'{hashlib.sha256(old.encode()).hexdigest()[:16]} != '
          f'{hashlib.sha256(new.encode()).hexdigest()[:16]}')


# ============ J. no team ready -> the whole-game deferral is the right answer
def test_j_a_game_with_no_ready_team_is_still_deferred_whole():
    """Scoping is not a licence to run on nothing.

    When NEITHER club has a filed report there is no unit left with evidence,
    so the correct answer is the refusal `layers.appearance` already produces
    -- in its own words, with its own code and its own `owed` block. The call
    site steps back rather than inventing a second vocabulary for it.
    """
    print('\nJ. no ready team: the whole game is still deferred')
    r = engine_run(*NONE_READY_GAME)
    if r is None:
        blocked('the NE@SEA fixture could not be built', 'unavailable')
        return
    g, pay, _players, _ko = r
    ap = g['layer_outcomes']['appearance']
    check('the appearance layer DEFERS', ap.state is State.DEFERRED,
          f'{ap.state.value}[{ap.code}]')
    check('  with the frozen layer\'s own code',
          ap.code == 'INJURY_REPORT_INCOMPLETE', ap.code)
    check('  the engine halts there', g.get('halted_at') == 'appearance',
          g.get('halted_at'))
    check('  and emits no payload', pay is None)
    check('no team-scope record is written',
          'appearance_team_scope' not in g)
    owed = (ap.evidence or {}).get('owed') or {}
    check('  the layer still names both clubs in `owed`',
          len(owed.get('teams') or []) == 2, owed.get('teams'))
    check('  and still says an unfiled report is not an absence of injury',
          'NOT a team with no injuries' in str(owed.get('note')))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
    print(f'\n{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    sys.exit(1 if FAILED else 0)
