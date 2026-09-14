"""The determinism harness, tested on its own terms rather than on tonight's game.

WHY THIS FILE DOES NOT RUN A FORECAST

`determinism_proof.prove` takes about ninety seconds per forecast, and the
property it measures is a property of the ENGINE. This file measures a different
property: whether the HARNESS reports the right thing when the engine does each
of the things it can do. Those have to be separated, because a harness validated
only by a green run on a quiescent tree has been tested on exactly one of the
four outcomes it exists to distinguish -- and the three it was not tested on are
the three that matter at 00:10Z.

So the comparator and the classifier are driven with constructed inputs that
stand in for each outcome, and `prove` itself is exercised only for the
preconditions it refuses on.

THE FOUR OUTCOMES, AND THE ONE THE HARNESS MUST NOT GUESS

    inputs moved            -> CAUSE_0, and nothing downstream is evidence
    in-scope source moved   -> CAUSE_1, which is what a live night looks like
    identity moved alone    -> CAUSE_2, the dF/dD != 0 defect class
    draws moved alone       -> CAUSE_3, never observed in this repository

The ordering test below is the one worth reading. A harness that reports CAUSE_3
while `pool_audit.py` was being written underneath it has produced a confident
wrong answer, and a confident wrong answer about determinism on the night of a
live forecast is worse than no answer at all.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys
import tempfile

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.tools import determinism_proof as DP                        # noqa: E402

PASSED = 0
FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  PASS  {label}')
    else:
        FAILED += 1
        print(f'  FAIL  {label}' + (f' -- {detail}' if detail else ''))
    return cond


# ------------------------------------------------------------- constructors
def _run(*, arrays, row_ids, run_id='r0', code_version='C0',
         scope_sha='S0', spec_hash='SP0', model_configuration='V1_CANDIDATE',
         captures=None, n_draws=4):
    """A stand-in for `run_once`'s value: only the fields the comparators read."""
    layers = {}
    for layer, ids in row_ids.items():
        layers[layer] = {
            'row_axis': 'team' if layer == 'team_volume' else 'gsis_id',
            'row_ids': list(ids)}
    manifest = {'layers': layers, 'n_draws': n_draws,
                'rng': {'seed': 1, 'seed_protocol': 'per-row seed 1'},
                'content_digest': 'D-' + run_id}
    caps = captures if captures is not None else [
        {'source': 'weekly_rosters', 'sha256': 'a' * 64,
         'retrieved_at': '2026-09-10T12:00:00Z'}]
    return {
        'label': run_id, 'run_dir': f'/tmp/{run_id}', 'out_root': '/tmp',
        'elapsed_s': 1.0, 'kickoff_utc': '2026-09-11T00:20:00Z',
        'manifest': manifest,
        'arrays': {k: np.asarray(v, dtype=np.float64)
                   for k, v in arrays.items()},
        'summary': {'run_id': run_id, 'execution_identity': 'E-' + run_id,
                    'code_commit': code_version, 'written_at': 'W',
                    'arm': 'A', 'pipeline_version': 'P',
                    'code_identity': {'commit': 'HEAD', 'code_version':
                                      code_version,
                                      'source_scope_sha256': scope_sha,
                                      'runtime_token': 'RT'}},
        'artifact': {'spec_hash': spec_hash, 'feature_set_hash': 'F',
                     'model_arm': 'A', 'seed_protocol': 'per-row seed 1',
                     'candidate_components': ['A1'],
                     'candidate_components_applied': ['A1'],
                     'cold_start_freeze_identity': None,
                     'model_configuration': model_configuration,
                     'completeness': 'PARTIAL_PLAYER_COVERAGE',
                     'eligibility_verdict': 'OK',
                     'code_commit': code_version,
                     'source_captures': caps},
        'board': {'component_manifest': {'applied': ['A1']},
                  'model_configuration': model_configuration, 'n_draws':
                  n_draws},
    }


def _point(label, scope_sha, files, commit='HEAD'):
    return {'label': label, 'resolved': True, 'commit': commit,
            'code_version': f'{commit}+src1[{scope_sha[:16]}]',
            'source_scope_sha256': scope_sha, 'source_scope_clean': not files,
            'runtime_token': 'RT',
            'dirty_source_files': [{'path': p, 'state': 'PRESENT',
                                    'sha256': s} for p, s in files],
            'legacy': {'available': True, 'n_dirty_tree_entries': len(files),
                       'withdrawn_code_version': f'{commit}+dirty[{len(files)}]'}}


BASE_ARRAYS = {'qb/pyds': [[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]],
               'team_volume/team_targets': [[9.0, 9.0, 9.0, 9.0],
                                            [8.0, 8.0, 8.0, 8.0]]}
BASE_ROWS = {'qb': ['00-0001', '00-0002'], 'team_volume': ['SF', 'LA']}


# ------------------------------------------------------- the array comparator
def test_a_identical_runs_compare_identical():
    a = _run(arrays=BASE_ARRAYS, row_ids=BASE_ROWS, run_id='A')
    b = _run(arrays=BASE_ARRAYS, row_ids=BASE_ROWS, run_id='A')
    rep = DP.compare_arrays(a, b)
    check('two identical draw sets compare identical', rep['identical'])
    check('  and something was actually compared',
          rep['n_cells_compared'] == 16, str(rep['n_cells_compared']))


def test_b_one_changed_cell_is_caught():
    mut = json.loads(json.dumps(BASE_ARRAYS))
    mut['qb/pyds'][1][2] = 7.000000000000001
    a = _run(arrays=BASE_ARRAYS, row_ids=BASE_ROWS, run_id='A')
    b = _run(arrays=mut, row_ids=BASE_ROWS, run_id='A')
    rep = DP.compare_arrays(a, b)
    check('a one-ulp change in a single cell is a difference',
          not rep['identical'])
    d = [x for x in rep['array_differences'] if x['array'] == 'qb/pyds']
    check('  the differing array is named', len(d) == 1)
    check('  and the differing ROW is named by id',
          bool(d) and d[0]['rows'][0]['row_id'] == '00-0002',
          str(d[0]['rows'] if d else None))


def test_c_rows_are_addressed_by_id_not_position():
    """The test that would fail on a positional comparator.

    Run B holds the same two players' draws with the rows in the opposite
    ORDER. Positionally every cell differs; by id nothing does. A positional
    harness would report a determinism failure on a roster read that sorted
    differently, which is a false alarm with the worst possible name on it.
    """
    swapped = {'qb/pyds': [BASE_ARRAYS['qb/pyds'][1],
                           BASE_ARRAYS['qb/pyds'][0]],
               'team_volume/team_targets':
                   BASE_ARRAYS['team_volume/team_targets']}
    a = _run(arrays=BASE_ARRAYS, row_ids=BASE_ROWS, run_id='A')
    b = _run(arrays=swapped,
             row_ids={'qb': ['00-0002', '00-0001'],
                      'team_volume': ['SF', 'LA']}, run_id='A')
    rep = DP.compare_arrays(a, b)
    check('a reordered row set produces no ARRAY difference',
          not rep['array_differences'], str(rep['array_differences']))
    check('  the reorder is still reported, not swallowed',
          any('different row ORDER' in (x.get('note') or '')
              for x in rep['row_set_differences']))
    # A positional comparison of the same two runs must disagree, or this test
    # is proving nothing about the addressing.
    pos = (np.asarray(BASE_ARRAYS['qb/pyds'])
           == np.asarray(swapped['qb/pyds'])).all()
    check('  and a positional comparison WOULD have called them different',
          not pos)


def test_d_a_missing_row_is_a_row_set_defect_not_an_array_defect():
    a = _run(arrays=BASE_ARRAYS, row_ids=BASE_ROWS, run_id='A')
    b = _run(arrays={'qb/pyds': [BASE_ARRAYS['qb/pyds'][0]],
                     'team_volume/team_targets':
                         BASE_ARRAYS['team_volume/team_targets']},
             row_ids={'qb': ['00-0001'], 'team_volume': ['SF', 'LA']},
             run_id='A')
    rep = DP.compare_arrays(a, b)
    check('a row present in only one run fails the comparison',
          not rep['identical'])
    rs = [x for x in rep['row_set_differences'] if x['layer'] == 'qb']
    check('  and is reported as a ROW SET difference naming the id',
          bool(rs) and rs[0]['only_in_a'] == ['00-0002'], str(rs))
    check('  the shared row is still compared and still equal',
          not rep['array_differences'], str(rep['array_differences']))


def test_e_nothing_compared_is_not_a_pass():
    """Zero compared cells must never render as `identical: True`.

    This is `run_suite`'s rule about a test function that ran zero checks,
    applied one level down: an equality over an empty set is not a result.
    """
    a = _run(arrays={}, row_ids={}, run_id='A')
    b = _run(arrays={}, row_ids={}, run_id='A')
    rep = DP.compare_arrays(a, b)
    check('two empty draw sets are NOT identical', not rep['identical'])
    check('  and the reason is named',
          any(x['kind'] == 'NOTHING_WAS_COMPARED'
              for x in rep['array_differences']))


def test_f_nan_and_signed_zero_are_compared_by_BITS():
    """`==` gets both of these wrong, in opposite directions."""
    a = _run(arrays={'qb/pyds': [[float('nan'), 0.0, 1.0, 2.0],
                                 [5.0, 6.0, 7.0, 8.0]]},
             row_ids={'qb': BASE_ROWS['qb']}, run_id='A')
    b = _run(arrays={'qb/pyds': [[float('nan'), 0.0, 1.0, 2.0],
                                 [5.0, 6.0, 7.0, 8.0]]},
             row_ids={'qb': BASE_ROWS['qb']}, run_id='A')
    rep = DP.compare_arrays(a, b)
    check('two identical NaN-carrying rows compare identical '
          '(`==` would not)', rep['identical'], str(rep['array_differences']))
    c = _run(arrays={'qb/pyds': [[float('nan'), -0.0, 1.0, 2.0],
                                 [5.0, 6.0, 7.0, 8.0]]},
             row_ids={'qb': BASE_ROWS['qb']}, run_id='A')
    rep2 = DP.compare_arrays(a, c)
    check('  and +0.0 against -0.0 IS a difference (`==` would not say so)',
          not rep2['identical'])


# --------------------------------------------------------- the classifier
FROZEN = {'manifest_version': 'nfl-frozen-input-manifest-1',
          'sources': {'weekly_rosters': {'sha256': 'a' * 64}}}
OBS_OK = {'weekly_rosters': {'sha256': 'a' * 64}}
P_STABLE = [_point('before_run_a', 'S0', [('nfl/production/x.py', 'h1')]),
            _point('between_runs', 'S0', [('nfl/production/x.py', 'h1')]),
            _point('after_run_b', 'S0', [('nfl/production/x.py', 'h1')])]


def _classify(points, frozen=FROZEN, obs_a=None, obs_b=None,
              arrays_rep=None, diffs=None):
    return DP.classify(before=points[0], between=points[1], after=points[2],
                       frozen=frozen,
                       obs_a=OBS_OK if obs_a is None else obs_a,
                       obs_b=OBS_OK if obs_b is None else obs_b,
                       arrays_rep=(arrays_rep or {'identical': True,
                                                  'array_differences': [],
                                                  'row_set_differences': []}),
                       identity_diffs=diffs or [])


def test_g_a_clean_comparison_names_no_cause():
    c = _classify(P_STABLE)
    check('everything equal produces no finding and no primary cause',
          c['primary_cause'] is None and not c['findings'], str(c))


def test_h_moved_inputs_are_cause_0():
    c = _classify(P_STABLE, obs_b={'weekly_rosters': {'sha256': 'b' * 64}})
    check('a changed input hash is CAUSE_0',
          c['primary_cause'] == 'CAUSE_0_INPUTS_NOT_FROZEN', str(c))


def test_i_moved_source_is_cause_1_and_names_the_file():
    moved = [P_STABLE[0],
             _point('between_runs', 'S1', [('nfl/production/pool_audit.py',
                                            'h2')]),
             _point('after_run_b', 'S1', [('nfl/production/pool_audit.py',
                                           'h2')])]
    c = _classify(moved, diffs=[{'group': 'execution_identity',
                                 'field': 'code_commit', 'a': 1, 'b': 2}])
    check('in-scope source moving is CAUSE_1',
          c['primary_cause'] == 'CAUSE_1_IN_SCOPE_SOURCE_CHANGED', str(c))
    ev = c['findings'][0]['evidence']
    check('  and the per-point scope digests are recorded',
          len(set(ev['source_scope_sha256_by_point'].values())) == 2)
    check('  and the file that appeared is named',
          'nfl/production/pool_audit.py'
          in ev['files_not_dirty_at_every_point'], str(ev))


def test_j_identity_moving_with_equal_draws_is_cause_2():
    c = _classify(P_STABLE, diffs=[{'group': 'execution_identity',
                                    'field': 'execution_identity',
                                    'a': 'x', 'b': 'y'}])
    check('equal draws with a moved identity is CAUSE_2',
          c['primary_cause'] == 'CAUSE_2_SEALED_BODY_READS_D', str(c))


def test_k_draws_moving_with_everything_else_equal_is_cause_3():
    c = _classify(P_STABLE, arrays_rep={
        'identical': False,
        'array_differences': [{'array': 'qb/pyds', 'kind': 'CELLS_DIFFER'}],
        'row_set_differences': []})
    check('moved draws with everything else equal is CAUSE_3',
          c['primary_cause'] == 'CAUSE_3_PREDICTIVE_NONDETERMINISM', str(c))


def test_l_cause_1_OUTRANKS_cause_3():
    """The test this harness exists for.

    Source moved AND the draws differ. Both are true. The harness must report
    the source change, because a source change explains a draw change and a
    draw change does not explain a source change. Reporting CAUSE_3 here would
    be a confident wrong answer on the one night it is read under time
    pressure.
    """
    moved = [P_STABLE[0],
             _point('between_runs', 'S1', [('nfl/production/pipeline.py',
                                            'h2')]),
             _point('after_run_b', 'S1', [('nfl/production/pipeline.py',
                                           'h2')])]
    c = _classify(moved, arrays_rep={
        'identical': False,
        'array_differences': [{'array': 'qb/pyds', 'kind': 'CELLS_DIFFER'}],
        'row_set_differences': []})
    check('source change outranks a simultaneous draw difference',
          c['primary_cause'] == 'CAUSE_1_IN_SCOPE_SOURCE_CHANGED', str(c))
    check('  and CAUSE_3 is not among the findings at all',
          not any(f['cause'] == 'CAUSE_3_PREDICTIVE_NONDETERMINISM'
                  for f in c['findings']), str(c))


def test_m_cause_0_outranks_cause_1():
    moved = [P_STABLE[0],
             _point('between_runs', 'S1', [('nfl/production/x.py', 'h2')]),
             _point('after_run_b', 'S1', [('nfl/production/x.py', 'h2')])]
    c = _classify(moved, obs_b={'weekly_rosters': {'sha256': 'b' * 64}})
    check('a broken premise outranks a source change',
          c['primary_cause'] == 'CAUSE_0_INPUTS_NOT_FROZEN', str(c))


def test_n_an_unresolvable_identity_is_not_silence():
    pts = [dict(P_STABLE[0]), dict(P_STABLE[1]),
           {'label': 'after_run_b', 'resolved': False, 'state': 'BLOCKED',
            'code': 'CODE_IDENTITY_NO_WORKTREE_STATE',
            'legacy': {'available': False}}]
    c = _classify(pts)
    check('an unresolved identity observation is reported, not assumed clean',
          c['primary_cause'] == 'CAUSE_1_IN_SCOPE_SOURCE_CHANGED', str(c))


# ------------------------------------------------------ preconditions of prove
def test_o_one_output_root_is_refused():
    with tempfile.TemporaryDirectory() as d:
        o = DP.prove(season=2026, week=1, game_id='2026_01_SF_LA',
                     cutoff='2026-09-10T21:18:56Z',
                     out_root_a=d, out_root_b=d, draws=2)
    check('two runs into ONE root is refused before anything runs',
          o.state is State.BLOCKED
          and o.code == 'DP_OUTPUT_ROOTS_NOT_SEPARATE', f'{o.state}[{o.code}]')


def test_p_a_nested_output_root_is_refused():
    with tempfile.TemporaryDirectory() as d:
        o = DP.prove(season=2026, week=1, game_id='2026_01_SF_LA',
                     cutoff='2026-09-10T21:18:56Z',
                     out_root_a=d, out_root_b=str(pathlib.Path(d) / 'b'),
                     draws=2)
    check('a root nested inside the other root is refused too',
          o.state is State.BLOCKED
          and o.code == 'DP_OUTPUT_ROOTS_NOT_SEPARATE', f'{o.state}[{o.code}]')


def test_q_a_self_inconsistent_input_manifest_is_refused():
    with tempfile.TemporaryDirectory() as d:
        o = DP.prove(season=2026, week=1, game_id='2026_01_SF_LA',
                     cutoff='2026-09-10T21:18:56Z',
                     out_root_a=str(pathlib.Path(d) / 'a'),
                     out_root_b=str(pathlib.Path(d) / 'b'), draws=2,
                     input_manifest={'manifest_version': 'x',
                                     'sources': {'weekly_rosters':
                                                 {'sha256': 'a' * 64}},
                                     'manifest_sha256': 'deadbeef'})
    check('a manifest that does not hash to its own content is refused',
          o.state is State.FAIL
          and o.code == 'DP_INPUT_MANIFEST_SELF_INCONSISTENT',
          f'{o.state}[{o.code}]')


# -------------------------------------------------- the proof artifact itself
def test_r_the_proof_body_excludes_everything_that_reads_D():
    """The recurrence guard, applied to this tool's OWN artifact.

    The identity contract's rule is that nothing reading generated artifact
    state may enter a sealed body, hashed or not, because the body is hashed
    into an identity of its own. This tool computes a working-tree COUNT on
    purpose -- as the counterfactual -- so it is the obvious next place for
    that defect to reappear. The test asserts the count is outside the hashed
    body, by hashing a body that differs ONLY in the excluded keys.
    """
    base = {'proof_version': DP.PROOF_VERSION, 'verdict': 'PASS',
            'game_id': 'G', 'equalities': {'x': True},
            'diagnostics': {'generated_at': 'T1',
                            'legacy_counterfactual_by_point':
                                {'before_run_a': {'n_dirty_tree_entries': 27}}},
            'proof_body_sha256': 'X', 'proof_signature': 'Y',
            'proof_body_excludes': list(DP.PROOF_BODY_EXCLUDED),
            'proof_body_excludes_why': 'w'}
    other = json.loads(json.dumps(base))
    other['diagnostics'] = {'generated_at': 'T2',
                            'legacy_counterfactual_by_point':
                                {'before_run_a': {'n_dirty_tree_entries': 999}}}
    other['proof_body_sha256'] = 'Z'
    h1 = DP._sha({k: v for k, v in base.items()
                  if k not in DP.PROOF_BODY_EXCLUDED})
    h2 = DP._sha({k: v for k, v in other.items()
                  if k not in DP.PROOF_BODY_EXCLUDED})
    check('the working-tree count is named in PROOF_BODY_EXCLUDED',
          'diagnostics' in DP.PROOF_BODY_EXCLUDED)
    check('  and a proof body differing only in it hashes the same', h1 == h2,
          f'{h1[:12]} != {h2[:12]}')
    check('  while a body differing in a REAL field does not',
          DP._sha({**{k: v for k, v in base.items()
                      if k not in DP.PROOF_BODY_EXCLUDED},
                   'verdict': 'FAIL'}) != h1)


def test_s_the_proof_names_the_code_that_produced_it():
    sha = DP.tool_source_sha256()
    check('the tool hashes its own source', len(sha) == 64)
    check('  and the hash is of the file on disk',
          sha == __import__('hashlib').sha256(
              pathlib.Path(DP.__file__).read_bytes()).hexdigest())


def test_t_a_proof_is_not_overwritten_by_a_different_proof():
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'PROOF.json'
        a = {'verdict': 'PASS', 'proof_body_sha256': '1' * 64}
        b = {'verdict': 'FAIL', 'proof_body_sha256': '2' * 64}
        o1 = DP.write_proof(a, p)
        check('the first proof is written', o1.state is State.PASS)
        o2 = DP.write_proof(b, p)
        check('  a DIFFERENT proof at the same path is refused',
              o2.state is State.FAIL
              and o2.code == 'DP_PROOF_WOULD_OVERWRITE_DIFFERENT_PROOF',
              f'{o2.state}[{o2.code}]')
        o3 = DP.write_proof(a, p)
        check('  and rewriting the SAME proof is allowed',
              o3.state is State.PASS)


def test_u_the_frozen_manifest_hashes_its_own_content():
    o = DP.resolve_input_manifest('2026-09-11T00:20:00Z',
                                  '2026-09-10T21:18:56Z')
    if o.state is not State.PASS:
        check('the information set resolves for a committed historical cutoff',
              False, f'{o.state}[{o.code}] {o.detail[:160]}')
        return
    m = o.value
    check('the frozen manifest names at least one source',
          bool(m['sources']))
    check('  and hashes to its own content',
          m['manifest_sha256'] == DP._sha(
              {k: v for k, v in m.items() if k != 'manifest_sha256'}))
    check('  and carries a content hash for every source it names',
          all(v.get('sha256') for v in m['sources'].values()))


# ======================================================================
# THE STANDING SWEEP: no SECOND legacy `+dirty[n]` implementation
# ======================================================================
#
# L5's Job 1 was a one-off audit: read the repository and establish that the
# two known count-keyed implementations were the only two. An audit is a
# statement about a moment. These two tests are the same statement made
# durable, and they are here rather than in a report because the next person
# to need a code version will write one from scratch unless something objects.
#
# THE RULES ARE ABOUT SHAPE, NOT ABOUT A LIST OF FILENAMES. An allow-list of
# exempted modules is how a silent skip comes back wearing a permit
# (`run_suite`'s own docstring makes the point). So:
#
#   RULE 1  only `nfl/identity/**` may ask git for working-tree state at all.
#           `--porcelain` is where a count comes from; centralising the call
#           is what makes there be exactly one implementation to be right.
#           Scoped by SUBTREE, which is a declaration, not an exemption list.
#
#   RULE 2  nobody, anywhere, may BUILD the count-keyed string. Detected on
#           the AST rather than on the text, so that DECLARING the marker --
#           `KEYS_ON_COUNT_MARKER = '+dirty['`, which is how the refusal in
#           `ExecutionIdentity.validate` names what it refuses -- is
#           distinguishable from CONSTRUCTING it in an f-string, a `%`, a
#           `.format()` or a concatenation. A rule that could not tell those
#           apart would have to exempt the identity module by name, and then
#           it would not be checking the identity module.
#
# What these two cannot catch is stated where it belongs, in the L5 return:
# a field that reads generated artifact state into a sealed body is not
# statically decidable, and was established by reading rather than by test.

IDENTITY_SUBTREE = 'nfl/identity/'


def _scoped_source_files():
    """Every `.py` the identity contract calls SOURCE, from the contract."""
    out = []
    for root in DP.CI.SOURCE_ROOTS:
        for f in sorted((ROOT / root).rglob('*.py')):
            rel = str(f.relative_to(ROOT))
            if DP.CI.in_source_scope(rel):
                out.append((rel, f))
    return out


def _builds_count_keyed(tree: ast.AST) -> bool:
    """True if the marker is CONSTRUCTED, as opposed to merely named."""
    m = DP.CI.KEYS_ON_COUNT_MARKER

    def _has(node):
        return isinstance(node, ast.Constant) and isinstance(node.value, str) \
            and m in node.value

    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            if any(_has(v) for v in n.values):
                return True
        elif isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Mod)):
            if _has(n.left) or _has(n.right):
                return True
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == 'format' and _has(f.value):
                return True
    return False


def _calls_porcelain(tree: ast.AST) -> bool:
    """A CALL carrying `--porcelain`, not the word in a docstring.

    The distinction is the whole test. `run_forecast.code_commit` and
    `q9shadow.seal` both PRINT the withdrawn implementation in prose, as the
    record of what they replaced -- deleting that prose to satisfy a text
    search would delete the only place the defect is explained. A text search
    flagged both on the first draft of this sweep; the AST does not, and it
    still flags an actual `subprocess.run([... '--porcelain' ...])`.
    """
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        for a in list(n.args) + [k.value for k in n.keywords]:
            for sub in ast.walk(a):
                if isinstance(sub, ast.Constant) \
                        and isinstance(sub.value, str) \
                        and '--porcelain' in sub.value:
                    return True
    return False


def test_v_only_the_identity_module_reads_working_tree_state():
    files = _scoped_source_files()
    if not check('there are in-scope source files to sweep', len(files) > 50,
                 f'{len(files)} files'):
        return
    offenders = []
    for rel, f in files:
        if rel.replace('\\', '/').startswith(IDENTITY_SUBTREE):
            continue
        try:
            tree = ast.parse(f.read_text(errors='replace'))
        except SyntaxError as exc:
            offenders.append(f'{rel}: UNPARSEABLE {exc}')
            continue
        if _calls_porcelain(tree):
            offenders.append(rel)
    check('no module outside nfl/identity/ CALLS git for working-tree state',
          not offenders, str(offenders))
    check('  the detector fires on a real call',
          _calls_porcelain(ast.parse(
              "subprocess.run(['git', 'status', '--porcelain'])")))
    check('  and not on prose that merely names it',
          not _calls_porcelain(ast.parse(
              '"""n = len(git status --porcelain)"""')))
    # The rule is only worth anything if the one declared implementation is
    # actually there. A sweep that passes because NOBODY reads the tree would
    # mean identity B had stopped being computed at all.
    ci = (ROOT / 'nfl' / 'identity' / 'code_identity.py').read_text()
    check('  and the one declared implementation still reads it',
          "'--porcelain'" in ci)


def test_w_nothing_in_scope_constructs_the_count_keyed_identity():
    files = _scoped_source_files()
    offenders, declared = [], []
    for rel, f in files:
        try:
            tree = ast.parse(f.read_text(errors='replace'))
        except SyntaxError as exc:
            offenders.append(f'{rel}: UNPARSEABLE {exc}')
            continue
        if _builds_count_keyed(tree):
            offenders.append(rel)
        elif DP.CI.KEYS_ON_COUNT_MARKER in f.read_text(errors='replace'):
            declared.append(rel)
    check('no in-scope module CONSTRUCTS the withdrawn count-keyed form',
          not offenders, str(offenders))
    check('  and the module that NAMES the marker so it can be refused is '
          'not mistaken for one that builds it',
          'nfl/identity/code_identity.py' in declared, str(declared))
    # Proof the detector is load-bearing: the construction it is looking for
    # must actually trip it. Without this the test could be passing because
    # `_builds_count_keyed` never returns True for anything.
    check('  the detector fires on an f-string construction',
          _builds_count_keyed(ast.parse("x = f'{rev}+dirty[{n}]'")))
    check('  on a concatenation',
          _builds_count_keyed(ast.parse("x = rev + '+dirty[' + str(n) + ']'")))
    check('  on a percent format',
          _builds_count_keyed(ast.parse("x = '%s+dirty[%d]' % (rev, n)")))
    check('  and NOT on a bare declaration of the marker',
          not _builds_count_keyed(ast.parse("KEYS_ON_COUNT_MARKER = '+dirty['")))


def test_x_green_equalities_with_an_open_finding_are_not_a_pass():
    """The case that actually occurred, on 2026-09-14, on this repository.

    One execution on `2026_01_SF_LA` returned all five equalities green while
    `nfl/production/pool_audit.py` changed during the window: the two runs
    agreed with each other and the code underneath them moved. A verdict read
    off the equalities alone would have certified that, and the thing it would
    have certified is a coincidence rather than a property.
    """
    green = {'identical_predictive_arrays': True,
             'identical_candidate_identity': True,
             'identical_execution_identity': True,
             'identical_model_configuration': True,
             'identical_input_hashes': True,
             'generated_output_did_not_alter_second_run_identity': True}
    check('all green with no finding is a PASS',
          DP.verdict_is_pass(green, []))
    check('  all green with an open CAUSE_1 is NOT a pass',
          not DP.verdict_is_pass(
              green, [{'cause': 'CAUSE_1_IN_SCOPE_SOURCE_CHANGED'}]))
    check('  one red equality is not a pass either',
          not DP.verdict_is_pass({**green,
                                  'identical_predictive_arrays': False}, []))
    check('  and an EMPTY equality set is not a pass',
          not DP.verdict_is_pass({}, []))


def test_y_the_dfdd_line_does_not_go_red_for_tree_churn_alone():
    """`generated_output_did_not_alter_second_run_identity` must mean what it says.

    `run_forecast.build` resolves its code identity once, before writing
    anything, so both runs' identities are fixed in the interval
    before_run_a -> between_runs. A source edit landing WHILE run B executes
    cannot move B's recorded identity. It is still reported, and it still
    drives CAUSE_1 and the verdict -- but if it turned this particular line
    red, the proof would be printing a sentence that is false. The two
    questions are carried as two fields, and this asserts the separation is
    really there rather than asserted in a comment.
    """
    src = pathlib.Path(DP.__file__).read_text()
    check('the dF/dD equality reads the identity-resolution interval',
          "dfdd['source_scope_stable_at_identity_resolution']" in src)
    check('  and the through-run-B observation is a SEPARATE field',
          "'source_scope_stable_through_run_b'" in src)
    check('  and the classifier still sees all three points',
          'before=before, between=between, after=after' in src)


def main():
    for fn in (test_a_identical_runs_compare_identical,
               test_b_one_changed_cell_is_caught,
               test_c_rows_are_addressed_by_id_not_position,
               test_d_a_missing_row_is_a_row_set_defect_not_an_array_defect,
               test_e_nothing_compared_is_not_a_pass,
               test_f_nan_and_signed_zero_are_compared_by_BITS,
               test_g_a_clean_comparison_names_no_cause,
               test_h_moved_inputs_are_cause_0,
               test_i_moved_source_is_cause_1_and_names_the_file,
               test_j_identity_moving_with_equal_draws_is_cause_2,
               test_k_draws_moving_with_everything_else_equal_is_cause_3,
               test_l_cause_1_OUTRANKS_cause_3,
               test_m_cause_0_outranks_cause_1,
               test_n_an_unresolvable_identity_is_not_silence,
               test_o_one_output_root_is_refused,
               test_p_a_nested_output_root_is_refused,
               test_q_a_self_inconsistent_input_manifest_is_refused,
               test_r_the_proof_body_excludes_everything_that_reads_D,
               test_s_the_proof_names_the_code_that_produced_it,
               test_t_a_proof_is_not_overwritten_by_a_different_proof,
               test_u_the_frozen_manifest_hashes_its_own_content,
               test_v_only_the_identity_module_reads_working_tree_state,
               test_w_nothing_in_scope_constructs_the_count_keyed_identity,
               test_x_green_equalities_with_an_open_finding_are_not_a_pass,
               test_y_the_dfdd_line_does_not_go_red_for_tree_churn_alone):
        print(fn.__name__)
        fn()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
