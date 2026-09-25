"""Folk and Smack, end to end, through every consumer that lost them.

DEF-060's closure condition, written as the owner stated it: 32 modelled
players on the sealed ATL@GB artifact, both kickers present, no silent
overwrite, no duplicate normalised identity, and the kicker reaching the slate
board, grading, the dossier, the dual board and the projection audit.

Why this file exists separately from the rule test: the rule
(test_dfs_universe_completeness) proves no production module SELECTS one
scoring layer. This one proves the two specific players actually arrive. A
module can take the union path and still drop a kicker one layer down -- the
array could be absent, the row index could be out of range, the name could be
missing -- and the rule would pass while the board stayed empty. Structure and
outcome are different claims.

One case is deliberately NOT "kicker is graded": postgame grading now
ENUMERATES kickers and marks their DK points KICKER_ACTUALS_INSUFFICIENT,
because `actuals` pulls fg_made and fg_att only -- no xp_made, no field-goal
distance buckets. Scoring a kicker from that charges every make at the
under-40 rate and ignores extra points, so a kicker with two field goals (one
from 45) and three extra points grades 6 against a true 10. Grading him
against that number would replace a silent omission with a confident wrong
one, which is worse. The named state makes it countable. That gap is DEF-061.
"""
import json
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs import player_universe as PU                        # noqa: E402

SEALED_DIR = _REPO / 'nfl/research/unsealed/2026_03_ATL_GB/2fc4e9599f0889f1'
MANIFEST = SEALED_DIR / 'player_draws_manifest.json'
NPZ = SEALED_DIR / 'player_draws.npz'

FOLK, SMACK = '00-0025565', '00-0040899'
EXPECTED_MODELLED = 32

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _artifact():
    if not (MANIFEST.exists() and NPZ.exists()):
        return None, None
    return (json.loads(MANIFEST.read_text()),
            np.load(NPZ, allow_pickle=True))


def test_the_union_is_thirty_two_and_holds_both_kickers():
    man, _ = _artifact()
    if man is None:
        check('sealed artifact present', False, f'{SEALED_DIR}')
        return
    uni = PU.dk_universe(man, consumer='test')
    check(f'modelled universe is {EXPECTED_MODELLED}',
          len(uni['ids']) == EXPECTED_MODELLED, len(uni['ids']))
    check('Folk present', FOLK in uni['ids'])
    check('Smack present', SMACK in uni['ids'])
    check('both are owned by the kicking layer',
          uni['layer_by_id'].get(FOLK) == 'kicking'
          and uni['layer_by_id'].get(SMACK) == 'kicking',
          {k: uni['layer_by_id'].get(k) for k in (FOLK, SMACK)})
    check('no duplicate layer ownership', not uni['report']['duplicate_owners'],
          uni['report']['duplicate_owners'])
    check('coverage is complete', uni['report']['coverage'] == 1.0,
          uni['report']['coverage'])


def test_a_duplicate_across_layers_refuses_rather_than_overwriting():
    """The silent-overwrite guard, exercised on a constructed artifact. The
    real one is disjoint, so this is the only way to prove the refusal fires."""
    man = {'layers': {
        'dk_scoring': {'row_axis': 'gsis_id', 'metrics': ['dk_points'],
                       'row_ids': ['00-0000001', FOLK]},
        'kicking': {'row_axis': 'gsis_id', 'metrics': ['dk_points'],
                    'row_ids': [FOLK]}}}
    try:
        PU.dk_universe(man, consumer='test')
        check('a player in two layers refuses', False,
              'returned a universe with one of the two layers silently dropped')
    except PU.DuplicateLayerOwnership as e:
        check('a player in two layers refuses', True)
        check('and the refusal names the player', FOLK in str(e), str(e)[:120])
    u = PU.dk_universe(man, consumer='test', merge_policy=PU.LAST_LAYER_WINS)
    check('an explicit merge policy resolves it',
          u['layer_by_id'][FOLK] == 'kicking', u['layer_by_id'][FOLK])
    check('and the duplicate is still reported, not hidden',
          FOLK in u['report']['duplicate_owners'],
          u['report']['duplicate_owners'])


def test_the_draws_are_real_for_both_kickers():
    man, npz = _artifact()
    if man is None:
        check('sealed artifact present', False, '')
        return
    draws, rep = PU.dk_points_by_id(man, npz, consumer='test')
    check('every universe row has draws',
          rep['n_with_draws'] == EXPECTED_MODELLED, rep['n_with_draws'])
    check('no row lacks an array', not rep['ids_without_draws'],
          rep['ids_without_draws'])
    for who, gid in (('Folk', FOLK), ('Smack', SMACK)):
        arr = draws.get(gid)
        check(f'{who} has a draw vector', arr is not None and arr.size > 0)
        if arr is not None:
            check(f'{who} has non-zero DK mass', float(arr.mean()) > 0,
                  float(arr.mean()))
            print(f'       {who}: mean {float(arr.mean()):.2f} '
                  f'over {arr.size} draws')


def test_no_two_players_collapse_into_one_normalised_name():
    man, npz = _artifact()
    if man is None:
        check('sealed artifact present', False, '')
        return
    names = {g: f'name {g}' for lay in man['layers'].values()
             for g in (lay.get('row_ids') or [])}
    sup = PU.modelled(man, npz, names, consumer='test')
    check('no normalised-name collision', not sup.name_collisions,
          sup.name_collisions)
    check('every row carries an identity', not sup.ids_without_a_name,
          sup.ids_without_a_name)
    check('the mapping carries its own coverage',
          sup.report.get('coverage') == 1.0, sup.report.get('coverage'))
    check('and it is still a plain mapping for existing callers',
          isinstance(sup, dict) and len(sup) == EXPECTED_MODELLED, len(sup))


def test_the_slate_board_gives_a_kicker_a_dk_column():
    from nfl.production.board import player_board as B
    man, _ = _artifact()
    if man is None:
        check('sealed artifact present', False, '')
        return
    m = B._dk_extended_map(man['layers'])
    dk_keys = sorted(k for k, v in m.items() if v == 'dk')
    check('the board maps every dk-bearing layer to its dk column',
          'kicking/dk_points' in dk_keys, dk_keys)
    check('and still maps the original one', 'dk_scoring/dk_points' in dk_keys)


def test_the_dossier_declares_a_headline_metric_for_a_kicker():
    from nfl.production.review import dossier as D
    man, _ = _artifact()
    if man is None:
        check('sealed artifact present', False, '')
        return
    pairs = [(f'{l}/{PU.DK_METRIC}', D.HEADLINE_METRIC)
             for l in PU.dk_bearing_layers(man)]
    check('kicking maps to the headline metric',
          ('kicking/dk_points', D.HEADLINE_METRIC) in pairs, pairs)


def test_the_projection_audit_counts_a_kicker_as_projected():
    from nfl.dfs.salaries import early_projection_audit as A
    verified = {'by_gsis_id': {
        FOLK: {'metrics': {'kicking/dk_points': {'mean': 8.26}}},
        '00-0000001': {'metrics': {'dk_scoring/dk_points': {'mean': 14.1}}},
        '00-0000002': {'metrics': {'rushing/carries': {'mean': 9.0}}}}}
    r = A.dk_points_available(verified)
    check('the kicker counts as having a DK projection', FOLK in r['gsis_ids'],
          'the audit would report a real projection as absent, which closes '
          'the question instead of raising it')
    check('a player with genuinely no DK metric still does not count',
          '00-0000002' not in r['gsis_ids'])
    check('the metric key is reported per layer',
          r['by_metric_key'].get('kicking/dk_points') == 1, r['by_metric_key'])


def test_grading_enumerates_kickers_and_refuses_to_invent_their_actuals():
    """Enumerated, and honestly ungraded. See DEF-061."""
    src = (_REPO / 'nfl/postgame/grade_projections.py').read_text()
    check('grading takes the union path', 'dk_points_by_id' in src)
    # AST, NOT TEXT. The first version of this check searched the source and
    # matched the EXPLANATORY COMMENT in the repaired code, which quotes the
    # old expression to say what it used to do. A test that cannot tell code
    # from prose about code fails on correct work -- the third time that shape
    # has appeared today.
    import ast as _ast
    subscripts = [n for n in _ast.walk(_ast.parse(src))
                  if isinstance(n, _ast.Subscript)
                  and isinstance(getattr(n, 'slice', None), _ast.Constant)
                  and n.slice.value == 'dk_scoring']
    check('grading no longer subscripts the dk_scoring layer in code',
          not subscripts,
          f'{len(subscripts)} live subscript(s) of dk_scoring remain')
    check('a kicker is named as insufficient rather than graded wrong',
          'KICKER_ACTUALS_INSUFFICIENT' in src)
    actuals = (_REPO / 'nfl/postgame/actuals.py').read_text()
    check('the gap is real: the outcome feed carries no xp_made',
          'xp_made' not in actuals,
          'if xp_made now exists, kicker DK points may be computable and '
          'DEF-061 should be re-derived rather than assumed')


def test_live_production_does_not_read_the_frozen_defect():
    """dossier_reference.py keeps the single-layer behaviour ON PURPOSE. It is
    only safe while nothing live consumes it."""
    offenders = []
    for p in sorted(_REPO.rglob('*.py')):
        rel = str(p.relative_to(_REPO))
        if not rel.startswith(('nfl/production', 'nfl/product', 'nfl/dfs',
                               'nfl/postgame', 'nfl/prospective')):
            continue
        if rel.endswith('dossier_reference.py') or '/tests/' in rel:
            continue
        src = p.read_text()
        if 'import dossier_reference' in src or 'from nfl.production.review import dossier_reference' in src:
            offenders.append(rel)
    check('no live production module imports the frozen dossier', not offenders,
          f'{offenders} read the frozen single-layer behaviour')
