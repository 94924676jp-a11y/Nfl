"""P0-A: a stage may not return PASS while its own output is incomplete.

WHAT THESE TESTS PROVE

1. The OLD failure mode is reproduced from the real PHI@TEN artifact, not
   from a hand-written fixture: the stage had enough information to identify
   `receiving` and `rushing` as absent, and the old path returned PASS
   carrying that fact as decoration.
2. The NEW path returns a named refusal on the same bytes, before anything
   downstream can package it.
3. The seven sound Week-2 artifacts still pass, so the contract discriminates
   rather than just refusing everything.
4. Each named refusal fires on a seeded violation of its own kind.
5. The guard is LOAD-BEARING: bypassed, the refusal disappears.

WHAT THESE TESTS DELIBERATELY DO NOT PROVE

MIN@CHI. Its malformation is that one club got `receiving` rows and the other
did not, and the artifact is well formed at the level a contract can see: the
layer is present, its metrics have bytes, its rows are unique and finite. To
catch it here a contract would need a point-in-time roster and a per-club
expectation, and the artifact schema would then move every time a roster did.
That is the coverage layer's job (blueprint 6) and it is P0-B. The test below
asserts MIN@CHI PASSES P0-A, so that when P0-B lands there is a recorded
statement of which layer was supposed to catch it.
"""
from __future__ import annotations

import copy
import glob
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.contracts import registry as REG            # noqa: E402
from nfl.production.contracts import validate as V              # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing       # noqa: E402
from sportsplatform.governance.outcome import Outcome, State    # noqa: E402

_P, _F = 0, 0
RUNS = '/tmp/claude-0/postinact/*/'


def ok(cond, what):
    global _P, _F
    if cond:
        _P += 1
        print(f'  ok     {what}')
    else:
        _F += 1
        print(f'  FAIL   {what}')


def _real_runs():
    """The eight Week-2 artifacts, if this checkout still has them."""
    out = {}
    for d in sorted(glob.glob(RUNS)):
        p = pathlib.Path(d)
        mf = p / 'player_draws_manifest.json'
        if not mf.exists():
            continue
        m = json.loads(mf.read_text())
        out[m.get('game_id')] = (m, p / 'player_draws.npz')
    return out


def _synthetic(n_rows=2, n_draws=8, layers=None):
    """A minimal well-formed player_draws manifest plus arrays.

    Built from the CONTRACT rather than copied from a file, so a change to
    the contract cannot leave this fixture silently describing the old shape.
    """
    c = REG.get('player_draws')
    want = (layers if layers is not None
            else list(c.required_layers('football')))
    man = {'game_id': '2026_02_AAA_BBB', 'run_id': 'deadbeefdeadbeef',
           'content_digest': 'c0ffee' * 10, 'n_draws': n_draws, 'layers': {}}
    arrays = {}
    for name in want:
        ls = c.layer(name)
        ids = ([f'00-00{i:05d}' for i in range(n_rows)] if ls.row_axis
               == 'gsis_id' else ['AAA', 'BBB'][:n_rows])
        man['layers'][name] = {'row_axis': ls.row_axis, 'row_ids': ids,
                               'metrics': list(ls.metrics)}
        for m in ls.metrics:
            arrays[f'{name}__{m}'] = np.ones((len(ids), n_draws), dtype=float)
    return man, arrays


# ------------------------------------------------------------------ PHI@TEN
def test_phi_ten_old_path_would_have_passed():
    """The stage HAD the information. The old path used it as decoration."""
    runs = _real_runs()
    if '2026_02_PHI_TEN' not in runs:
        ok(True, 'PHI@TEN artifact not in this checkout; nothing to replay')
        return
    man, _ = runs['2026_02_PHI_TEN']
    produced = set(man.get('layers') or {})
    required = set(REG.get('player_draws').required_layers('football'))
    absent = sorted(required - produced)

    ok(absent, f'the stage could identify absent required layers: {absent}')
    ok('receiving' in absent and 'rushing' in absent,
       'both receiving and rushing were identifiable as absent')

    # The OLD predicate, reproduced exactly: absence was recorded in evidence
    # and the outcome was ok() regardless.
    old = Outcome.ok('DRAWS_BUILT', value={},
                     layers_absent=[k for k in
                                    ('receiving', 'rushing', 'td',
                                     'team_volume')
                                    if k not in produced])
    ok(old.state is State.PASS,
       'OLD path: returns PASS on the real PHI@TEN manifest')
    ok(old.evidence.get('layers_absent'),
       f'OLD path: and carried the absence as evidence on that PASS: '
       f'{old.evidence["layers_absent"]}')


def test_phi_ten_new_path_refuses_by_name():
    runs = _real_runs()
    if '2026_02_PHI_TEN' not in runs:
        ok(True, 'PHI@TEN artifact not in this checkout; nothing to replay')
        return
    man, npz = runs['2026_02_PHI_TEN']
    o = V.validate_draw_manifest(man, np.load(npz))
    ok(o.state is State.FAIL, f'NEW path: refuses, state={o.state.name}')
    ok(o.code == 'DECLARED_DRAW_ARTIFACT_INCOMPLETE',
       f'NEW path: named refusal {o.code}')
    codes = set(o.evidence.get('offence_codes') or [])
    ok('CONTRACT_DECLARED_LAYER_ABSENT' in codes,
       f'NEW path: the discriminating code is present: {sorted(codes)}')
    layers = {x.get('layer') for x in o.evidence.get('offences') or []}
    ok({'receiving', 'rushing'} <= layers,
       f'NEW path: names both missing layers: {sorted(x for x in layers if x)}')


def test_the_seven_sound_artifacts_still_pass():
    """A contract that refuses everything discriminates nothing."""
    runs = _real_runs()
    if not runs:
        ok(True, 'no Week-2 artifacts in this checkout')
        return
    passed, failed = [], []
    for gid, (man, npz) in sorted(runs.items()):
        o = V.validate_draw_manifest(man, np.load(npz))
        (passed if o.state is State.PASS else failed).append(gid)
    ok('2026_02_PHI_TEN' in failed, 'PHI@TEN is the failing one')
    ok(len(passed) == len(runs) - 1,
       f'{len(passed)} of {len(runs)} real artifacts satisfy the contract')


def test_scopes_are_cumulative_not_independent():
    """Upstream validity flows DOWN; downstream invalidity does NOT flow UP.

    The first implementation filtered `ls.scope == scope`, which made the
    scopes independent: `dfs_product` required only `dk_scoring`, so PHI@TEN
    returned football FAIL and dfs_product PASS. That is the Week-2 defect
    one layer higher -- a downstream artifact calling itself valid while the
    model beneath it is broken. These checks pin the corrected semantics.
    """
    c = REG.get('player_draws')
    fb = set(c.required_layers('football'))
    dfs = set(c.required_layers('dfs_product'))
    ok(c.ancestors('football') == ('football',),
       'football is a root scope')
    ok(c.ancestors('dfs_product') == ('football', 'dfs_product'),
       f'dfs_product depends on football: {c.ancestors("dfs_product")}')
    ok(fb < dfs, f'dfs_product requirements STRICTLY contain football: '
                 f'{sorted(fb)} < {sorted(dfs)}')
    ok('dk_scoring' not in fb, 'dk_scoring is not a football requirement')
    ok('dk_scoring' in dfs, 'dk_scoring IS a dfs_product requirement')
    ok({'receiving', 'rushing', 'qb'} <= dfs,
       'and dfs_product still requires every football layer')

    # A future prop scope must drop in with no change to the abstraction.
    ok(isinstance(c.SCOPE_PARENTS, dict) and c.SCOPE_PARENTS['football'] == (),
       'the scope graph is a dependency map, not a flat list')


def test_valid_football_with_no_dk_layer():
    """football PASS, dfs FAIL -- and the football verdict is untouched."""
    man, arr = _synthetic()                       # football layers only
    f = V.validate_draw_manifest(man, arr, scope='football')
    ok(f.state is State.PASS,
       'a football artifact with no DK layer is VALID football')
    blocks = [b['layer'] for b in (f.evidence or {}).get(
        'blocks_other_scope') or []]
    ok('dk_scoring' in blocks,
       f'and it names which product that absence blocks: {blocks}')

    d = V.validate_draw_manifest(man, arr, scope='dfs_product')
    ok(d.state is State.FAIL, 'the same artifact is REFUSED for DFS')
    ok('CONTRACT_DECLARED_LAYER_ABSENT' in set(
        (d.evidence or {}).get('offence_codes') or []),
       'refused by name')
    up = (d.evidence or {}).get('blocked_by_upstream_scopes') or []
    ok(not up,
       f'and NOT attributed upstream -- the missing layer is DFS\'s own: '
       f'{up}')

    # THE ISOLATION PROPERTY. Asking the DFS question must not change the
    # football answer.
    f2 = V.validate_draw_manifest(man, arr, scope='football')
    ok(f2.state is State.PASS and f2.code == f.code,
       'the football verdict is identical before and after the DFS check')


def test_invalid_football_blocks_dfs_even_when_dk_bytes_exist():
    """PHI@TEN: football FAIL, dfs FAIL BY UPSTREAM. DK bytes prove nothing."""
    runs = _real_runs()
    if '2026_02_PHI_TEN' not in runs:
        ok(True, 'PHI@TEN artifact not in this checkout')
        return
    man, npz = runs['2026_02_PHI_TEN']
    z = np.load(npz)
    ok('dk_scoring' in (man.get('layers') or {}),
       'PHI@TEN DID compute DK points -- the transform ran')

    f = V.validate_draw_manifest(man, z, scope='football')
    ok(f.state is State.FAIL, 'football is INVALID')

    d = V.validate_draw_manifest(man, z, scope='dfs_product')
    ok(d.state is State.FAIL,
       'and DFS is BLOCKED despite the DK bytes existing')
    codes = set((d.evidence or {}).get('offence_codes') or [])
    ok('CONTRACT_BLOCKED_BY_UPSTREAM_SCOPE' in codes,
       f'attributed to the upstream scope: {sorted(codes)}')
    ok((d.evidence or {}).get('blocked_by_upstream_scopes') == ['football'],
       f'named: {(d.evidence or {}).get("blocked_by_upstream_scopes")}')
    upstream_layers = sorted({o['layer'] for o in
                              (d.evidence or {}).get('offences') or []
                              if o.get('is_upstream')})
    ok({'receiving', 'rushing'} <= set(upstream_layers),
       f'and points at the real cause, not the transform: {upstream_layers}')


def test_dfs_product_pass_is_not_dfs_deployable():
    """A transform certificate is not a deployment certificate."""
    man, arr = _synthetic(layers=['receiving', 'rushing', 'qb', 'dk_scoring'])
    d = V.validate_draw_manifest(man, arr, scope='dfs_product')
    ok(d.state is State.PASS,
       'football plus a DK transform satisfies the dfs_product scope')
    cert = (d.value or {}).get('certifies', '')
    ok('NOT a deployment verdict' in cert,
       'and the artifact says so: field, ownership, duplication, payout, '
       'market freshness and calibration are later gates')


def test_min_chi_passes_p0a_and_that_is_correct():
    """Recorded on purpose: its defect belongs to the coverage layer."""
    runs = _real_runs()
    if '2026_02_MIN_CHI' not in runs:
        ok(True, 'MIN@CHI artifact not in this checkout')
        return
    man, npz = runs['2026_02_MIN_CHI']
    o = V.validate_draw_manifest(man, np.load(npz))
    ok(o.state is State.PASS,
       'MIN@CHI satisfies P0-A: its layers are present and well formed')
    ok('receiving' in (man.get('layers') or {}),
       'the receiving layer IS present -- the loss is one club inside it, '
       'which needs a roster expectation and is P0-B')


# ------------------------------------------------- one seeded case per code
def test_each_named_refusal_fires_on_its_own_violation():
    base_man, base_arr = _synthetic()
    o = V.validate_draw_manifest(base_man, base_arr)
    ok(o.state is State.PASS,
       f'the synthetic well-formed artifact passes ({o.code})')

    def seed(mut):
        m, a = copy.deepcopy(base_man), dict(base_arr)
        mut(m, a)
        return V.validate_draw_manifest(m, a)

    def codes(res):
        return set((res.evidence or {}).get('offence_codes') or [])

    cases = [
        ('CONTRACT_DECLARED_LAYER_ABSENT',
         lambda m, a: m['layers'].pop('receiving')),
        ('CONTRACT_DECLARED_METRIC_BYTES_ABSENT',
         lambda m, a: a.pop('receiving__targets')),
        ('CONTRACT_REQUIRED_ROW_AXIS_EMPTY',
         lambda m, a: m['layers']['qb'].__setitem__('row_ids', [])),
        ('CONTRACT_DUPLICATE_ROW_IDS',
         lambda m, a: m['layers']['qb'].__setitem__(
             'row_ids', ['00-0000001', '00-0000001'])),
        ('CONTRACT_DRAW_VALUES_NOT_FINITE',
         lambda m, a: a.__setitem__(
             'qb__att', np.full((2, 8), np.nan))),
        ('CONTRACT_ROW_COUNT_MISMATCH',
         lambda m, a: a.__setitem__('qb__att', np.ones((5, 8)))),
        ('CONTRACT_DRAW_WIDTH_MISMATCH',
         lambda m, a: a.__setitem__('qb__att', np.ones((2, 3)))),
        ('CONTRACT_ROW_AXIS_MISMATCH',
         lambda m, a: m['layers']['qb'].__setitem__('row_axis', 'team')),
        ('CONTRACT_UNDECLARED_LAYER',
         lambda m, a: m['layers'].__setitem__('mystery', {
             'row_axis': 'gsis_id', 'row_ids': ['x'], 'metrics': ['y']})),
        ('CONTRACT_MISSING_RUN_IDENTITY',
         lambda m, a: m.__setitem__('run_id', '')),
    ]
    for code, mut in cases:
        res = seed(mut)
        ok(res.state is State.FAIL and code in codes(res),
           f'{code} fires on its seeded violation')


def test_zero_row_legality_must_be_declared():
    """Registration fails at import time, not on a Sunday."""
    try:
        REG.LayerSpec(name='x', row_axis='gsis_id', metrics=('a',),
                      required=True, min_rows=1, zero_rows_legal_when='')
        ok(False, 'a layer with no zero-row rule was accepted')
    except REG.ContractRegistrationError as e:
        ok('zero_rows_legal_when' in str(e),
           'a layer with no zero-row rule is refused at registration')
    for ls in REG.get('player_draws').layers:
        ok(bool(ls.zero_rows_legal_when),
           f'{ls.name} declares its zero-row rule')


def test_undeclared_emptiness_is_refused_for_a_generic_stage():
    r = V.validate_row_count('demo', n_rows=0, min_rows=1,
                             zero_rows_legal_when=None)
    ok(r.state is State.FAIL and r.code == 'CONTRACT_UNDECLARED_EMPTY_OUTPUT',
       f'a stage with no declared emptiness rule is refused: {r.code}')
    r2 = V.validate_row_count('demo', n_rows=0, min_rows=1,
                              zero_rows_legal_when='NEVER')
    ok(r2.state is State.FAIL,
       f'zero rows against min_rows=1 is still a failure: {r2.code}')
    r3 = V.validate_row_count('demo', n_rows=3, min_rows=1,
                              zero_rows_legal_when='NEVER')
    ok(r3.state is State.PASS, 'a populated stage passes')


# --------------------------------------------------------- load-bearing proof
def test_the_contract_guard_is_load_bearing():
    """Bypassed, the refusal must disappear. Otherwise it proves nothing."""
    runs = _real_runs()
    if '2026_02_PHI_TEN' in runs:
        man, _ = runs['2026_02_PHI_TEN']
        man = copy.deepcopy(man)
        arrays = None
    else:
        man, arrays = _synthetic()
        man['layers'].pop('receiving')

    def run():
        return V.validate_draw_manifest(man, arrays)

    try:
        assert_guard_is_load_bearing(
            run=run,
            module_path='nfl.production.contracts.validate',
            attr='validate_draw_manifest',
            caught=lambda o: getattr(o, 'state', None) is State.FAIL,
            returns=Outcome.ok('STUB_CONTRACT_NOT_CHECKED', value={}))
        ok(True, 'refusal is present with the guard and gone when bypassed')
    except AssertionError as e:
        ok(False, f'guard is not load-bearing: {e}')


def test_the_production_stage_returns_the_contract_verdict():
    """AST: the draws stage must RETURN the contract, not attach it."""
    import ast
    src = (_REPO / 'nfl' / 'production' / 'run_forecast.py').read_text()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Attribute)
             and n.attr == 'validate_draw_manifest']
    ok(calls, 'run_forecast calls validate_draw_manifest')
    ok('layers_absent=[k for k in' not in src,
       'the old layers_absent-on-PASS evidence block is gone')
    ok('_contract.state is not State.PASS' in src,
       'the stage returns on a failed contract before building its Outcome')


def main():
    for t in (test_phi_ten_old_path_would_have_passed,
              test_phi_ten_new_path_refuses_by_name,
              test_the_seven_sound_artifacts_still_pass,
              test_scopes_are_cumulative_not_independent,
              test_valid_football_with_no_dk_layer,
              test_invalid_football_blocks_dfs_even_when_dk_bytes_exist,
              test_dfs_product_pass_is_not_dfs_deployable,
              test_min_chi_passes_p0a_and_that_is_correct,
              test_each_named_refusal_fires_on_its_own_violation,
              test_zero_row_legality_must_be_declared,
              test_undeclared_emptiness_is_refused_for_a_generic_stage,
              test_the_contract_guard_is_load_bearing,
              test_the_production_stage_returns_the_contract_verdict):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {_P} FAILED {_F}')
    return 1 if _F else 0


if __name__ == '__main__':
    sys.exit(main())
