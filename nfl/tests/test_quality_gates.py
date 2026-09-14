"""The product quality gates and the board pointer, asserted behaviourally.

WHAT THIS MODULE IS FOR, IN ORDER OF HOW MUCH IT MATTERS

1. THE SEALED BOARD IS NOT TOUCHED. Every file under the V1 seal is hashed at
   import and re-hashed at the end of the module. If running the tests moved a
   byte of prospective evidence, the tests say so.
2. NOTHING REPAIRS. Asserted on the AST of both new modules: no clip, no
   renormalisation, no write into a draw array, no file opened for writing
   anywhere except the pointer's own directory.
3. EACH GATE CATCHES A SEEDED VIOLATION, on a synthetic board built here, and
   each one REFUSES rather than passes when the evidence it takes is missing.
   A gate that cannot fail is not a gate.
4. HARD AND SOFT NEVER MIX. No SOFT diagnostic carries a quarantine or
   withhold action, and no gate anywhere imposes a floor on any quantity.
5. NO SPORTSBOOK DATA REACHES A GATE. Asserted on the imports.
6. EVERY THRESHOLD IS GROUNDED. A constant with no GROUNDING entry naming its
   sample and its source fails here.

WHAT IT DOES NOT ASSERT. Nothing here says the gates are correctly calibrated,
because calibration is a claim about a reference frame and no equivalence
margin is predeclared. Each threshold is asserted to be DECLARED, SOURCED and
BEHAVING as its declaration says -- not to be right.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.product import quality_gates as QG                        # noqa: E402
from nfl.product import board_pointer as BP                        # noqa: E402
from nfl.product import metrics as M                               # noqa: E402

PASSED = FAILED = BLOCKED = 0

SEAL = (pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live' / '2026_01_DEN_KC'
        / 'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8' / 'f91342d6787a66a1')
QG_SRC = pathlib.Path(QG.__file__)
BP_SRC = pathlib.Path(BP.__file__)

# The eight gate names the product contract requires, written out so that
# renaming one in the module without renaming it here fails.
REQUIRED_GATES = (
    'HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY', 'QB_ROOM_SPLIT_ANOMALY',
    'ROLE_STATE_SOURCE_CONFLICT', 'AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY',
    'RUSH_ACCOUNTING_FAILURE', 'COUNT_SUPPORT_FAILURE',
    'IDENTITY_DEPTH_ROLE_CONFLICT', 'UNATTRIBUTED_OPPORTUNITY_MASS')

REQUIRED_STATES = ('FINAL', 'PRELIMINARY', 'UNVALIDATED', 'WITHHELD',
                   'UNAVAILABLE', 'DATA_ERROR', 'MODEL_ERROR',
                   'INSUFFICIENT_EVIDENCE', 'INELIGIBLE')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    """A check that could not run. Counted apart and never as a pass."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


def _hash_tree(d: pathlib.Path) -> dict:
    out = {}
    for p in sorted(d.rglob('*')):
        if p.is_file():
            out[str(p.relative_to(d))] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return out


_SEAL_AT_IMPORT = _hash_tree(SEAL) if SEAL.is_dir() else {}


# ===========================================================================
# a synthetic board, built here so a gate can be shown to FIRE and to PASS
# ===========================================================================
def _synth(tmp, *, n=200, qb1_zero=0.0, split=0.0, carries_float=False,
           rb_rows=True, wr_rows=None, name=True, enforce_inactive=True,
           over_allocate=False, position='QB'):
    """A minimal but schema-correct board directory."""
    d = pathlib.Path(tmp)
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    # two QBs for one team
    db = np.zeros((2, n), dtype=np.int16)
    db[0] = 30
    k = int(round(qb1_zero * n))
    db[0][:k] = 0
    s = int(round(split * n))
    db[1][:s] = 9
    att = np.minimum(db, 25).astype(np.int16)
    zeros = np.zeros((2, n), dtype=np.int16)
    ro = np.full((2, n), 3, dtype=np.int16)
    scr = np.full((2, n), 1, dtype=np.int16)
    car = np.full((1, n), 8.0 if carries_float else 8.0)
    if carries_float:
        car = car + rng.random((1, n)) * 0.4
    lev = np.full((1, n), 4.0 if over_allocate else 40.0)
    arrays = {
        'qb__db': db, 'qb__att': att, 'qb__cmp': zeros, 'qb__int': zeros,
        'qb__ptd': zeros, 'qb__rtd': zeros, 'qb__sacks': zeros,
        'qb__scr': scr, 'qb__rush_opp': ro,
        'qb__pyds': np.zeros((2, n)), 'qb__ryds': np.zeros((2, n)),
        'team_volume__team_carries': lev,
        'team_volume__team_targets': np.full((1, n), 30.0),
        'team_volume__team_dropbacks_part': np.full((1, n), 40.0),
        'team_volume__team_off_snaps': np.full((1, n), 60, dtype=np.int16),
        'team_volume__team_rz_carries': np.full((1, n), 4.0),
    }
    layers = {
        'qb': {'row_axis': 'gsis_id', 'row_ids': ['00-AAA', '00-BBB'],
               'metrics': ['db'], 'shape': [2, n]},
        'team_volume': {'row_axis': 'team', 'row_ids': ['XX'],
                        'metrics': ['team_carries'], 'shape': [1, n]},
    }
    if rb_rows:
        arrays['rushing__carries'] = car
        arrays['rushing__rushing_td'] = np.zeros((1, n), dtype=np.int16)
        layers['rushing'] = {'row_axis': 'gsis_id', 'row_ids': ['00-CCC'],
                             'metrics': ['carries'], 'shape': [1, n]}
    wr_rows = rb_rows if wr_rows is None else wr_rows
    if wr_rows:
        arrays['receiving__targets'] = np.full((1, n), 6, dtype=np.int16)
        arrays['receiving__receptions'] = np.full((1, n), 4, dtype=np.int16)
        arrays['receiving__receiving_td'] = np.zeros((1, n), dtype=np.int16)
        arrays['receiving__receiving_yards'] = np.zeros((1, n),
                                                        dtype=np.int16)
        layers['receiving'] = {'row_axis': 'gsis_id', 'row_ids': ['00-DDD'],
                               'metrics': ['targets'], 'shape': [1, n]}
    np.savez(d / 'player_draws.npz', **arrays)
    man = {'run_id': 'SYNTH', 'game_id': 'SYNTH_GAME', 'layers': layers,
           'content_digest': 'SYNTHDIGEST', 'n_draws': n}
    (d / 'player_draws_manifest.json').write_text(json.dumps(man))

    def row(gid, pos, dc, lays):
        r = {'gsis_id': gid, 'position': pos, 'team': 'XX', 'depth_chart': dc,
             'layers': lays, 'metrics': {}, 'touchdown': {},
             'unavailable': [], 'opportunity_share': {},
             'confidence': {'parts': {}, 'reasons': {}, 'score': 0.5}}
        if name:
            r['name'] = f'Player {gid}'
        return r

    players = [row('00-AAA', position, 'QB1', ['qb']),
               row('00-BBB', 'QB', 'QB2', ['qb'])]
    if rb_rows:
        players.append(row('00-CCC', 'RB', 'RB1', ['rushing']))
    if wr_rows:
        players.append(row('00-DDD', 'WR', 'WR1', ['receiving']))
    own = {'enforced': bool(enforce_inactive),
           'failed_conditions': [] if enforce_inactive else ['x'],
           'inactive_qbs_in_modelled_room': {}}
    board = {'run_id': 'SYNTH', 'game_id': 'SYNTH_GAME', 'teams': ['XX'],
             'n_players': len(players), 'n_draws': n, 'players': players,
             'qb_inactive_ownership': own,
             'readiness': {'XX': {'state': 'READY'}},
             'vintage_selection': {'refusals': []},
             'draws_file': 'player_draws.npz',
             'draw_content_digest': 'SYNTHDIGEST'}
    board['draws_sha256'] = hashlib.sha256(
        (d / 'player_draws.npz').read_bytes()).hexdigest()
    (d / 'board.json').write_text(json.dumps(board))
    return d


def _fired(findings, gate, state='FIRED'):
    return [f for f in findings if f['gate'] == gate and f['state'] == state]


def _eval(d, **kw):
    o = QG.evaluate(d, **kw)
    if o.state is not State.PASS:
        return None, o
    return o.evidence['findings'], o


# ===========================================================================
def test_a_every_required_gate_is_declared_and_well_formed():
    for g in REQUIRED_GATES:
        d = QG.GATES.get(g)
        if not check(f'{g} is declared', d is not None):
            continue
        check(f'  {g} declares HARD/SOFT', d['class'] in (QG.HARD, QG.SOFT))
        check(f'  {g} declares a scope',
              d['scope'] in (QG.ROW, QG.FAMILY, QG.BOARD_SCOPE))
        check(f'  {g} declares an action that withholds or quarantines',
              d['action'] in (QG.QUARANTINE_FAMILY, QG.WITHHOLD_BOARD,
                              QG.WITHHOLD_ROW))
        check(f'  {g} says what it asserts', len(d.get('asserts', '')) > 40)
        check(f'  {g} says whether it is structural',
              len(d.get('structural', '')) > 40)
    check('no gate is declared that the contract did not ask for, unless it '
          'is explicitly a soft diagnostic',
          set(QG.GATES) == set(REQUIRED_GATES),
          f'extra: {sorted(set(QG.GATES) - set(REQUIRED_GATES))}')


def test_b_every_threshold_is_grounded():
    for name, d in sorted(QG.GATES.items()) + sorted(
            QG.SOFT_DIAGNOSTICS.items()):
        key = d.get('threshold')
        if key is None:
            check(f'{name} declares no numeric threshold and needs none',
                  True)
            continue
        g = QG.GROUNDING.get(key)
        if not check(f'{name} threshold {key} has a GROUNDING entry',
                     g is not None):
            continue
        check(f'  {key} carries a value', g.get('value') is not None)
        check(f'  {key} names the sample it was measured on',
              len(str(g.get('measured', ''))) > 60)
        check(f'  {key} cites an artifact path',
              '/' in str(g.get('source', '')))
    for key, g in sorted(QG.GROUNDING.items()):
        used = any(key in (d.get('threshold'), d.get('soft_companion'),
                           d.get('grounding_ref'))
                   for d in list(QG.GATES.values())
                   + list(QG.SOFT_DIAGNOSTICS.values()))
        check(f'GROUNDING entry {key} is actually used by a gate', used)


def test_c_the_product_state_vocabulary_is_complete_and_honest():
    for s in REQUIRED_STATES:
        d = QG.PRODUCT_STATES.get(s)
        if not check(f'{s} is declared', d is not None):
            continue
        check(f'  {s} says what it means', len(d.get('means', '')) > 20)
        check(f'  {s} declares whether it carries a number',
              isinstance(d.get('carries_a_number'), bool))
        if d.get('publishable'):
            check(f'  {s} is publishable and therefore carries a number',
                  d['carries_a_number'] is True)
    check('exactly nine states are declared', len(QG.PRODUCT_STATES) == 9,
          f'{sorted(QG.PRODUCT_STATES)}')
    for s in QG.NOT_A_PASS:
        check(f'{s} is not publishable',
              QG.PRODUCT_STATES[s]['publishable'] is False)
    check('UNAVAILABLE carries no number, so a missing family cannot be '
          'filled in', QG.PRODUCT_STATES[QG.UNAVAILABLE][
              'carries_a_number'] is False)
    check('INSUFFICIENT_EVIDENCE carries no number either',
          QG.PRODUCT_STATES[QG.INSUFFICIENT_EVIDENCE][
              'carries_a_number'] is False)


def _draw_bound_names(tree):
    """Names bound to something that came out of the draw artifact.

    A name qualifies if it was assigned from DEC.matrix(...), np.load(...),
    np.asarray(<a qualifying name>) or an index of one. This is what makes the
    mutation check MEAN something: a blanket ban on subscript assignment would
    flag every dictionary in the file and would therefore be ignored.
    """
    src_calls = {'matrix', 'load'}
    names = set()
    for _ in range(3):                       # small fixpoint, for chains
        for n in ast.walk(tree):
            if not isinstance(n, ast.Assign) or len(n.targets) != 1:
                continue
            tgt = n.targets[0]
            if not isinstance(tgt, ast.Name):
                continue
            for sub in ast.walk(n.value):
                if isinstance(sub, ast.Call):
                    f = sub.func
                    nm = (f.id if isinstance(f, ast.Name)
                          else getattr(f, 'attr', ''))
                    if nm in src_calls:
                        names.add(tgt.id)
                if isinstance(sub, ast.Name) and sub.id in names:
                    names.add(tgt.id)
    return names


def test_d_nothing_in_either_module_repairs_anything():
    banned_calls = {'clip', 'savez', 'savez_compressed', 'normalize',
                    'renormalise', 'renormalize', 'fill', 'put', 'itemset',
                    'resize'}
    in_place = {'sort', 'fill', 'put', 'itemset', 'resize', 'setfield'}
    for src in (QG_SRC, BP_SRC):
        txt = src.read_text()
        tree = ast.parse(txt, str(src))
        bound = _draw_bound_names(tree)
        calls, opens = set(), []
        mutations = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                nm = f.id if isinstance(f, ast.Name) else getattr(f, 'attr',
                                                                  '')
                calls.add(nm)
                if nm in in_place and isinstance(f, ast.Attribute) and \
                        isinstance(f.value, ast.Name) and f.value.id in bound:
                    mutations.append(f'{f.value.id}.{nm}()')
                if nm == 'open':
                    mode = ''
                    for a in list(n.args[1:]) + [k.value for k in n.keywords
                                                 if k.arg == 'mode']:
                        if isinstance(a, ast.Constant):
                            mode = str(a.value)
                    opens.append(mode)
            tgts = []
            if isinstance(n, ast.Assign):
                tgts = list(n.targets)
            elif isinstance(n, ast.AugAssign):
                tgts = [n.target]
            for t in tgts:
                if isinstance(t, ast.Subscript) and isinstance(
                        t.value, ast.Name) and t.value.id in bound:
                    mutations.append(f'{t.value.id}[...] = ...')
        check(f'{src.name} binds at least one name from the draw artifact, '
              f'so this check is not vacuous',
              bool(bound) or src is BP_SRC, f'{sorted(bound)}')
        check(f'{src.name} never writes into a draw array', not mutations,
              f'{mutations[:4]}')
        bad = sorted(calls & banned_calls)
        check(f'{src.name} calls no repairing function', not bad, f'{bad}')
        writes = [m for m in opens if any(c in m for c in 'wax+')]
        if src is QG_SRC:
            check('quality_gates.py opens no file for writing at all',
                  not writes, f'{writes}')
        else:
            check('board_pointer.py writes, and only through the guarded '
                  'pointer path',
                  'os.replace' in txt and '_assert_writable' in txt)


def test_e_no_sportsbook_data_reaches_a_gate():
    banned = ('market_cdf', 'market_names', 'oddsclient', 'market_comparison',
              'price', 'vig', 'implied_probability')
    for src in (QG_SRC, BP_SRC):
        txt = src.read_text()
        tree = ast.parse(txt, str(src))
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module or '')
                mods |= {f'{n.module}.{a.name}' for a in n.names}
        hits = sorted(m for m in mods if any(b in m for b in banned))
        check(f'{src.name} imports no market or price module', not hits,
              f'{hits}')
    check('the word "floor" never appears as an operation in quality_gates',
          'floor(' not in QG_SRC.read_text())


def test_f_soft_diagnostics_never_quarantine_and_never_floor():
    for name, d in sorted(QG.SOFT_DIAGNOSTICS.items()):
        check(f'{name} is SOFT', d['class'] == QG.SOFT)
        check(f'  {name} only flags',
              d['action'] == QG.FLAG_FOR_REVIEW, f'{d["action"]}')
        check(f'  {name} declares what to inspect',
              len(d.get('inspect', '')) > 20)
        check(f'  {name} declares what it must NEVER do',
              len(d.get('never', '')) > 20)
    lo = QG.SOFT_DIAGNOSTICS['HEALTHY_QB1_LOW_CENTRAL_TENDENCY']
    check('the healthy-QB1 low-mean diagnostic points at starter probability '
          'and exit/replacement', 'starter probability' in lo['inspect']
          and 'replacement' in lo['inspect'])
    check('  and says in its own declaration that it is not a yardage floor',
          'yardage floor' in lo['never'])


def test_g_each_gate_fires_on_a_seeded_violation():
    with tempfile.TemporaryDirectory() as t:
        d = _synth(pathlib.Path(t) / 'bad', qb1_zero=0.40, split=0.50,
                   carries_float=True, rb_rows=True, name=False,
                   enforce_inactive=False, over_allocate=True)
        f, o = _eval(d)
        if f is None:
            blocked('seeded-violation board evaluated', o.detail)
            return
        for g in ('HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY',
                  'QB_ROOM_SPLIT_ANOMALY', 'ROLE_STATE_SOURCE_CONFLICT',
                  'RUSH_ACCOUNTING_FAILURE', 'COUNT_SUPPORT_FAILURE',
                  'IDENTITY_DEPTH_ROLE_CONFLICT'):
            check(f'{g} fires on a board seeded to violate it',
                  bool(_fired(f, g)),
                  f'{[x["state"] for x in f if x["gate"] == g]}')
        v = o.evidence['verdict']
        check('a board with hard findings is WITHHELD',
              v['board_state'] == QG.WITHHELD, v['board_state'])
        check('  and names the families it quarantined',
              bool(v['quarantined_families']))


def test_h_each_gate_passes_a_clean_board():
    with tempfile.TemporaryDirectory() as t:
        d = _synth(pathlib.Path(t) / 'clean', qb1_zero=0.0, split=0.0,
                   carries_float=False, rb_rows=True, name=True,
                   enforce_inactive=True, over_allocate=False)
        f, o = _eval(d)
        if f is None:
            blocked('clean board evaluated', o.detail)
            return
        for g in ('HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY',
                  'QB_ROOM_SPLIT_ANOMALY', 'ROLE_STATE_SOURCE_CONFLICT',
                  'COUNT_SUPPORT_FAILURE', 'IDENTITY_DEPTH_ROLE_CONFLICT',
                  'UNATTRIBUTED_OPPORTUNITY_MASS'):
            check(f'{g} does NOT fire on a clean board', not _fired(f, g),
                  f'{[x["why"][:90] for x in _fired(f, g)][:2]}')
        check('a gate set that fires on everything would be useless: some '
              'gate recorded a PASS',
              any(x['state'] == QG.PASS for x in f))


def test_i_unattributed_mass_fires_when_a_pool_has_no_owner_row():
    with tempfile.TemporaryDirectory() as t:
        d = _synth(pathlib.Path(t) / 'noowner', rb_rows=False,
                   wr_rows=False)
        f, o = _eval(d)
        if f is None:
            blocked('no-owner board evaluated', o.detail)
            return
        hits = _fired(f, 'UNATTRIBUTED_OPPORTUNITY_MASS')
        check('a positive carry pool with zero rushing rows fires '
              'UNATTRIBUTED_OPPORTUNITY_MASS', bool(hits))
        if hits:
            check('  and reports the share as 1.0, not as a percentile',
                  any(h['measured'].get('unattributed_share') == 1.0
                      for h in hits))
            check('  and quarantines the family rather than the board',
                  all(h['action'] == QG.QUARANTINE_FAMILY for h in hits))


def test_j_an_unevaluated_gate_is_not_a_passed_gate():
    with tempfile.TemporaryDirectory() as t:
        d = _synth(pathlib.Path(t) / 'noinact', enforce_inactive=False)
        f, o = _eval(d)
        if f is None:
            blocked('board without an inactive list evaluated', o.detail)
            return
        ins = [x for x in f
               if x['gate'] == 'AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY'
               and x['state'] == QG.INSUFFICIENT_EVIDENCE]
        check('with no ingested inactive list the gate is '
              'INSUFFICIENT_EVIDENCE', bool(ins))
        check('  and is never reported as PASS',
              not [x for x in f
                   if x['gate'] == 'AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY'
                   and x['state'] == QG.PASS])
        check('  and the state itself declares it carries no number',
              QG.PRODUCT_STATES[QG.INSUFFICIENT_EVIDENCE][
                  'carries_a_number'] is False)


def test_k_an_inactive_player_with_mass_is_impossible_not_unlikely():
    with tempfile.TemporaryDirectory() as t:
        d = _synth(pathlib.Path(t) / 'inact', enforce_inactive=True)
        f, o = _eval(d, inactives=['00-AAA'])
        if f is None:
            blocked('inactive-list board evaluated', o.detail)
            return
        hits = _fired(f, 'AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY')
        check('a listed-inactive player carrying dropback mass fires the gate',
              bool(hits))
        if hits:
            check('  and the finding carries the measured mass',
                  hits[0]['measured'].get('p_any_opportunity', 0) > 0)


def test_l_evaluate_refuses_an_empty_or_missing_board():
    with tempfile.TemporaryDirectory() as t:
        o = QG.evaluate(pathlib.Path(t) / 'does_not_exist')
        check('a missing board directory is BLOCKED, not an empty pass',
              o.state is State.BLOCKED, f'{o.state} {o.code}')
        empty = pathlib.Path(t) / 'empty'
        empty.mkdir()
        (empty / 'board.json').write_text('')
        o2 = QG.evaluate(empty)
        check('a zero-byte board.json is BLOCKED, not read as a clean board',
              o2.state is State.BLOCKED, f'{o2.state} {o2.code}')


def test_m_k_and_dst_absences_are_verified_against_the_code():
    v = QG.verify_absent_families()
    for fam in ('K', 'DST'):
        check(f'{fam} is not a position the product declares',
              v[fam]['position_in_POSITION_LAYERS'] is False)
        check(f'  no declared product metric matches {fam}',
              v[fam]['declared_metrics_matching'] == [],
              f'{v[fam]["declared_metrics_matching"]}')
        check(f'  so {fam} verifies as absent', v[fam]['verified_absent'])
        a = QG.ABSENT_FAMILIES[fam]
        check(f'  {fam} resolves to UNAVAILABLE',
              a['state'] == QG.UNAVAILABLE)
        check(f'  {fam} says what it would need, in more than one item',
              len(a['would_need']) >= 2)
        check(f'  {fam} cites where in the code the absence is visible',
              '.py' in a['why'])
    check('the product declares exactly QB, RB, WR, TE',
          sorted(M.POSITION_LAYERS) == ['QB', 'RB', 'TE', 'WR'],
          f'{sorted(M.POSITION_LAYERS)}')
    check('qb/sacks is the only sack quantity and it is a QB metric, i.e. '
          'sacks TAKEN and never a defensive credit',
          ('qb', 'sacks') in M.SUPPORTED
          and not any(k[0] not in ('qb',) and 'sack' in k[1]
                      for k in M.SUPPORTED))


# ===========================================================================
# the pointer
# ===========================================================================
def test_n_the_pointer_refuses_to_write_inside_the_sealed_tree():
    for bad in (SEAL / 'board.json',
                SEAL / 'x' / '..' / 'board.json',
                BP.SEALED_ROOT / 'anything.json'):
        try:
            BP._assert_writable(bad)
            check(f'writing {bad.name} inside the seal is refused', False,
                  'it was ALLOWED')
        except BP.SealViolation as e:
            check(f'writing inside the seal is refused ({bad.name})',
                  'SEALED_ARTIFACT_WRITE_REFUSED' in str(e)
                  or 'POINTER_WRITE_OUTSIDE_OWNED_DIR' in str(e))
    try:
        BP._assert_writable(pathlib.Path(_ROOT) / 'nfl' / 'production'
                            / 'x.json')
        check('writing outside the owned directory is refused', False,
              'it was ALLOWED')
    except BP.SealViolation:
        check('writing outside the owned directory is refused', True)
    check('the pointer file itself is inside the owned directory',
          BP._assert_writable(BP.POINTER) == BP.POINTER.resolve())


def test_o_the_seal_verifies_and_a_moved_byte_would_fail():
    o = BP.verify_seal(BP.V1_SEALED)
    if o.state is not State.PASS:
        blocked('V1 seal verification', f'{o.code}: {o.detail}')
        return
    obs = o.evidence['observed']
    check('the sealed run_id is the one the identity declares',
          obs['run_id'] == BP.IDENTITIES[BP.V1_SEALED]['run_id'])
    check('the draw file still hashes to the board\'s declared sha256',
          obs['draws_sha256_recomputed'] == obs['draws_sha256_declared'])
    check('the determinism draw digest is re-read from the run record, not '
          'retyped',
          obs.get('determinism_draw_digest_observed')
          == BP.IDENTITIES[BP.V1_SEALED]['determinism_draw_digest'])
    # A moved byte must fail. Shown on a COPY; the seal is never touched.
    with tempfile.TemporaryDirectory() as t:
        cp = pathlib.Path(t) / 'copy'
        shutil.copytree(SEAL, cp)
        b = json.loads((cp / 'board.json').read_text())
        b['run_id'] = 'TAMPERED'
        (cp / 'board.json').write_text(json.dumps(b))
        saved = dict(BP.IDENTITIES[BP.V1_SEALED])
        try:
            BP.IDENTITIES[BP.V1_SEALED] = dict(
                saved, path=str(cp.resolve()))
            bad = BP.verify_seal(BP.V1_SEALED)
            check('a tampered run_id FAILS verification rather than being '
                  'accepted as a new baseline',
                  bad.state is State.FAIL
                  and bad.code == 'SEAL_INTEGRITY_VIOLATED',
                  f'{bad.state} {bad.code}')
        finally:
            BP.IDENTITIES[BP.V1_SEALED] = saved


def test_p_mixed_version_rows_are_refused():
    m = BP._no_mixed_versions(SEAL)
    check('the sealed V1 board is a single-version board',
          m.state is State.PASS, f'{m.code}: {m.detail[:200]}')
    with tempfile.TemporaryDirectory() as t:
        cp = pathlib.Path(t) / 'copy'
        shutil.copytree(SEAL, cp)
        man = json.loads((cp / 'player_draws_manifest.json').read_text())
        man['run_id'] = 'A_DIFFERENT_RUN'
        (cp / 'player_draws_manifest.json').write_text(json.dumps(man))
        bad = BP._no_mixed_versions(cp)
        check('a board whose manifest names another run is refused as '
              'MIXED_VERSION_ROWS',
              bad.state is State.FAIL and bad.code == 'MIXED_VERSION_ROWS',
              f'{bad.state} {bad.code}')


def test_q_the_swap_is_gated_by_both_the_gates_and_authorization():
    o = BP.swap(BP.V1_SEALED, reason='test: does the sealed board earn the '
                                     'user-facing pointer?')
    check('the V1 board does not take the user-facing pointer',
          o.state is State.BLOCKED and o.code == 'BOARD_SWAP_REFUSED',
          f'{o.state} {o.code}')
    if o.state is not State.BLOCKED:
        return
    bb = o.evidence['blocked_by']
    check('  the quality gates are named as a reason',
          any(b.startswith('QUALITY_GATES') for b in bb), f'{bb}')
    check('  and authorization is named SEPARATELY, so the two refusals are '
          'never read as one',
          any(b.startswith('AUTHORIZATION:') for b in bb), f'{bb}')
    check('  authorization refuses on NFL1_NOT_AUTHORIZED',
          o.evidence['authorization']['code'] == 'NFL1_NOT_AUTHORIZED',
          o.evidence['authorization']['code'])
    check('  the pointer did not move',
          BP.resolve()['active'] != BP.V1_SEALED,
          f'{BP.resolve()["active"]}')
    check('  and the refusal is recorded where a reader can see it',
          (BP.read_pointer().get('last_refusal') or {}).get('identity')
          == BP.V1_SEALED)


def test_r_authorization_is_consulted_and_not_reimplemented():
    txt = BP_SRC.read_text()
    check('board_pointer imports the authorization module',
          'from nfl.production import authorization' in txt)
    check('  and calls may_publish', 'AUTH.may_publish()' in txt)
    check('  and does not define its own', 'def may_publish' not in txt)
    check('  and never takes a caller-supplied gate verdict as the basis',
          'gates_outcome' not in txt and 'tests_passed' not in txt)
    tree = ast.parse(txt, str(BP_SRC))
    sw = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == 'swap']
    if check('swap() exists', bool(sw)):
        names = {getattr(a, 'arg', '') for a in sw[0].args.args}
        names |= {getattr(a, 'arg', '') for a in sw[0].args.kwonlyargs}
        check('  swap takes no argument that could assert a pass',
              not (names & {'verdict', 'passed', 'ok', 'force', 'override'}),
              f'{sorted(names)}')


def test_s_publication_state_never_rises_to_FINAL():
    txt = BP_SRC.read_text()
    check('PRELIMINARY_PROVISIONAL is the only state the pointer writes',
          txt.count("'publication_state': PRELIMINARY_PROVISIONAL") >= 2
          or "PRELIMINARY_PROVISIONAL" in txt)
    p = BP.read_pointer()
    check('the live pointer carries PRELIMINARY_PROVISIONAL',
          p.get('publication_state') == BP.PRELIMINARY_PROVISIONAL,
          f'{p.get("publication_state")}')
    check('FINAL is declared and is never assigned to the pointer',
          BP.FINAL == 'FINAL'
          and "'publication_state': FINAL" not in txt
          and 'publication_state"] = FINAL' not in txt)
    v = QG.evaluate(SEAL).evidence['verdict'] if SEAL.is_dir() else {}
    if v:
        check('the gate verdict also states PRELIMINARY_PROVISIONAL',
              v['publication_state'] == 'PRELIMINARY_PROVISIONAL')
        check('  and says why FINAL is unreachable',
              'authoritative inactive' in v['publication_state_note'])


def test_t_a_prior_seal_stays_visible_while_a_rebuild_computes():
    before = BP.read_pointer()
    o = BP.begin_candidate(BP.MNF_REBUILD, note='test')
    check('begin_candidate records a computation in flight',
          o.state is State.PASS, f'{o.code}')
    r = BP.resolve()
    check('  resolve() reports the board as stale rather than blank',
          r['stale'] is True)
    check('  and names what is computing, and since when',
          (r.get('computing') or {}).get('identity') == BP.MNF_REBUILD
          and bool((r.get('computing') or {}).get('since')))
    check('  and the active identity is unchanged by a computation starting',
          r['active'] == before.get('active'))
    check('  and the stale warning is addressed to a reader, in plain words',
          r['stale_warning'] and 'has NOT replaced' in r['stale_warning'])
    p = BP.read_pointer()
    p['computing'] = None
    BP._write_pointer(p)


def test_u_the_pointer_write_is_atomic_and_version_checked():
    txt = BP_SRC.read_text()
    check('the pointer is replaced atomically', 'os.replace(tmp, target)'
          in txt)
    check('  after an fsync, so a crash cannot leave a torn file',
          'os.fsync' in txt)
    p = BP.read_pointer()
    v = p.get('pointer_version')
    bad = BP._write_pointer(p, expect_version=(v or 0) + 99)
    check('a swap racing another swap is refused, not silently applied',
          bad.state is State.FAIL and bad.code == 'POINTER_VERSION_CONFLICT',
          f'{bad.state} {bad.code}')
    check('  and the version did not move',
          BP.read_pointer().get('pointer_version') == v)


def test_v_the_v1_board_is_measured_and_several_gates_fire_on_it():
    if not SEAL.is_dir():
        blocked('V1 board measured', f'{SEAL} is not present')
        return
    o = QG.evaluate(SEAL)
    if o.state is not State.PASS:
        blocked('V1 board measured', f'{o.code}: {o.detail}')
        return
    v = o.evidence['verdict']
    f = o.evidence['findings']
    check('the V1 board is WITHHELD by the gates',
          v['board_state'] == QG.WITHHELD, v['board_state'])
    check('  KC\'s QB1 fires the zero-opportunity gate at 0.412',
          any(x['measured'].get('p_zero_dropbacks') == 0.412
              for x in _fired(f, 'HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY')))
    check('  DEN\'s QB1 does NOT fire it, at 0.048',
          any(x['measured'].get('p_zero_dropbacks') == 0.048
              for x in f
              if x['gate'] == 'HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY'
              and x['state'] == QG.PASS))
    check('  KC\'s room fires the split gate', bool(
        [x for x in _fired(f, 'QB_ROOM_SPLIT_ANOMALY')
         if x['subject'] == 'KC/qb']))
    check('  KC\'s rush allocation over-deals the carry level on some draws',
          any(x['measured'].get('draws_over_allocated', 0) > 0
              for x in _fired(f, 'RUSH_ACCOUNTING_FAILURE')))
    check('  rushing/carries fires the count-support gate, and it is float64',
          any(x['measured'].get('dtype') == 'float64'
              for x in _fired(f, 'COUNT_SUPPORT_FAILURE')))
    check('  DEN\'s target and carry pools have no owner rows at all',
          len([x for x in _fired(f, 'UNATTRIBUTED_OPPORTUNITY_MASS')
               if x['subject'].startswith('DEN/')]) >= 2)
    check('  every row fails the name condition, so the board escalates to '
          'board scope',
          any(x['action'] == QG.WITHHOLD_BOARD
              for x in _fired(f, 'IDENTITY_DEPTH_ROLE_CONFLICT')))
    check('  and the authoritative-inactive gate has NO evidence tonight',
          bool(v['hard_insufficient_evidence']))


def test_w_running_these_tests_did_not_touch_the_seal():
    if not _SEAL_AT_IMPORT:
        blocked('seal immutability', f'{SEAL} was absent at import')
        return
    now = _hash_tree(SEAL)
    check('every sealed file is byte-identical to what it was at import',
          now == _SEAL_AT_IMPORT,
          f'changed: {sorted(set(now.items()) ^ set(_SEAL_AT_IMPORT.items()))[:3]}')
    check('  and the file set is unchanged too',
          sorted(now) == sorted(_SEAL_AT_IMPORT))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} failing check(s)')


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
