"""Adversarial tests for the six-part execution identity contract. WS-E.

    python3.12 nfl/tests/run_suite.py --only test_execution_identity
    python3.12 nfl/tests/test_execution_identity.py

THE DEFECT REPLAYED

`seal._code_commit()` appended `+dirty[N]` -- a COUNT OF THE LINES of
`git status --porcelain` -- to the commit sha. WS01, WS18 (F3) and WS19 found it
independently. Two consequences, in opposite directions:

  1  A run changed its own identity by writing its own outputs. Run 1 writes
     `dryrun/proof/run1/`, the count goes up, run 2 gets a different
     `code_commit` and therefore a different `forecast_id`,
     `seal_payload_sha256`, `artifact_id` and `identity_fingerprint`. WS18
     measured two different execution identities for two BIT-IDENTICAL draw
     sets, in one process, seconds apart.

  2  A count does not identify content. Any two working trees with the same
     NUMBER of dirty paths produce the same string, so an edited `layers.py` and
     an unrelated scratch note are indistinguishable in the sealed bytes.

BINDING TEST STANDARD (Owner Directive 3 section 8): a guard is not demonstrated
because compliant data passes it. Section A is therefore written as a PAIR --
the old function is reconstructed here and REQUIRED TO FAIL the same scenario
the new one passes. Without the failing half, every check below would pass
against a repair that did nothing.

WHAT THIS FILE DOES NOT DO. It never mutates a tracked file. Its write-a-file
scenarios create and delete paths under a temporary directory inside the repo,
and section E asserts the tree is restored.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Outcome, State       # noqa: E402
from sportsplatform.governance.provenance import Provenance        # noqa: E402
from nfl.identity import code_identity as CI                       # noqa: E402
from nfl.identity.execution_identity import (ConsumedPartition,    # noqa: E402
                                             ExecutionIdentity)

ROOT = pathlib.Path(CI._REPO)
PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  PASS  {label}')
    else:
        FAILED += 1
        print(f'  FAIL  {label}  {detail}')


# ---------------------------------------------------------------------------
# THE WITHDRAWN IMPLEMENTATION, reconstructed verbatim so the repair can be
# shown to differ from it rather than asserted to.
# ---------------------------------------------------------------------------
def withdrawn_code_commit():
    rev = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=20
                         ).stdout.strip() or 'UNKNOWN'
    st = subprocess.run(['git', 'status', '--porcelain'], cwd=str(ROOT),
                        capture_output=True, text=True, timeout=20)
    n = len([x for x in st.stdout.splitlines() if x.strip()])
    return rev + (f'+dirty[{n}]' if n else '')


class scratch:
    """A temporary GENERATED-artifact tree, created and removed inside the repo.

    Two separate top-level directories, because git collapses an untracked
    directory to ONE porcelain line: writing a second file into the same
    directory does not move the count, and a test that only did that would show
    a false green against the withdrawn implementation.
    """

    def __init__(self, *rel):
        self.paths = [ROOT / r for r in rel]

    def __enter__(self):
        for p in self.paths:
            p.mkdir(parents=True, exist_ok=True)
            (p / 'SEALED_FORECAST.json').write_text('{"generated": true}\n')
        return self

    def __exit__(self, *exc):
        for p in self.paths:
            if p.exists():
                shutil.rmtree(p)
        return False


def cv():
    o = CI.code_identity()
    assert o.state is State.PASS, o.code
    return o.value['code_version']


def block():
    """The WHOLE identity block, canonicalised.

    Comparing only `code_version` is not enough and this is not a hypothetical:
    the first version of this repair kept a whole-tree dirty COUNT in the block
    as a recorded-not-hashed diagnostic. It was outside the digest, outside
    `code_version` and outside the fingerprint -- and still reached
    `seal_payload_sha256` and `forecast_id`, because the block is written into
    the artifact and the artifact is the sealed payload. The Q9 dry-run proof
    caught it; this check is what would have caught it here first.
    """
    o = CI.code_identity()
    assert o.state is State.PASS, o.code
    return json.dumps(o.value, sort_keys=True, separators=(',', ':'))


# ===========================================================================
# SECTION A -- the invariant, and the load-bearing pair
# ===========================================================================
def test_a_writing_outputs_cannot_alter_identity():
    print('\nA  a run must not change its own identity by writing its outputs')
    before, before_b = cv(), block()
    with scratch('nfl/prospective/q9shadow/dryrun/ws_e_probe_run1',
                 'nfl/prospective/q9shadow/dryrun/ws_e_probe_run2'):
        during, during_b = cv(), block()
    after, after_b = cv(), block()
    check('code_version is unchanged while outputs exist',
          during == before, f'{before} -> {during}')
    check('code_version is unchanged after they are removed',
          after == before, f'{before} -> {after}')
    # The stronger form. Everything in this block reaches the sealed payload.
    check('the WHOLE identity block is unchanged while outputs exist',
          during_b == before_b, 'a field in the block reads the working tree')
    check('the WHOLE identity block is unchanged after removal',
          after_b == before_b, 'a field in the block reads the working tree')
    check('no field of the block is a whole-tree count',
          not any('tree_entries' in k for k in json.loads(before_b)),
          str([k for k in json.loads(before_b) if 'tree_entries' in k]))


def test_a2_the_guard_is_load_bearing():
    print('\nA2 the WITHDRAWN implementation must FAIL the same scenario')
    before = withdrawn_code_commit()
    with scratch('nfl/ws_e_probe_alpha', 'nfl/ws_e_probe_beta'):
        during = withdrawn_code_commit()
        new_during = cv()
    # If this passes, the scenario is not exercising the defect and every
    # other check in this file is vacuous.
    check('withdrawn +dirty[N] DOES move when outputs are written',
          during != before, f'{before} == {during} -- scenario is inert')
    check('the repaired identity does NOT move under the same scenario',
          new_during == cv(), 'repair moved where it must not')
    check('the withdrawn form is recognisable as such',
          CI.refuses_count_keyed(before) and
          not CI.refuses_count_keyed(cv()), before)


def test_a3_a_count_aliases_and_a_digest_does_not():
    print('\nA3 a count cannot distinguish two different trees; a digest can')
    a = [{'path': 'nfl/production/x.py', 'state': 'PRESENT',
          'sha256': 'a' * 64, 'bytes': 10}]
    b = [{'path': 'nfl/production/y.py', 'state': 'PRESENT',
          'sha256': 'b' * 64, 'bytes': 10}]
    check('equal counts, different content -> different digest',
          CI._digest_entries(a) != CI._digest_entries(b))
    check('the same content -> the same digest',
          CI._digest_entries(a) == CI._digest_entries(list(a)))
    check('order of discovery does not matter',
          CI._digest_entries(a + b) == CI._digest_entries(b + a))
    check('the clean sentinel is computed, not a literal',
          CI.clean_source_digest() == CI._digest_entries([]))
    check('a clean tree and a one-file-dirty tree differ',
          CI.clean_source_digest() != CI._digest_entries(a))


# ===========================================================================
# SECTION B -- determinism: same source, same inputs, same RNG, same identity
# ===========================================================================
def _identity(code_version, interpreter, seed, sha):
    p = ConsumedPartition(
        partition_id='schedules/2026', source='schedules',
        url='file://nfl/vintage/schedules.csv.gz', sha256=sha,
        provenance=Provenance(
            source='schedules', url='file://nfl/vintage/schedules.csv.gz',
            retrieved_at='2026-09-01T00:00:00Z',
            source_timestamp='2026-08-31T00:00:00Z',
            effective_for_date='2026-09-01', schema_version='v1',
            generated_at='2026-09-01T00:00:00Z'))
    return ExecutionIdentity(spec_id='ws-e', spec_sha256='c' * 64,
                             code_version=code_version, interpreter=interpreter,
                             seed=seed, partitions=(p,))


BASE = dict(code_version='0' * 40 + '+src1[' + '1' * 16 + ']',
            interpreter='implementation=CPython+python_version=3.12.3'
                        '+numpy_version=2.5.3',
            seed={'seed': 20260908, 'n_draws': 1000},
            sha='d' * 64)


def test_b_identical_everything_gives_identical_identity():
    print('\nB  identical source + inputs + RNG -> identical run identity')
    f1 = _identity(**BASE).fingerprint()
    f2 = _identity(**BASE).fingerprint()
    check('two constructions agree', f1 == f2, f'{f1} {f2}')
    check('the fingerprint is namespaced', f1.startswith('NFLFP-'), f1)
    for field, changed in (
            ('code_version', '0' * 40 + '+src1[' + '2' * 16 + ']'),
            ('interpreter', 'implementation=CPython+python_version=3.12.4'
                            '+numpy_version=2.5.3'),
            ('seed', {'seed': 20260909, 'n_draws': 1000}),
            ('sha', 'e' * 64)):
        alt = dict(BASE)
        alt[field] = changed
        check(f'changing {field} moves the fingerprint',
              _identity(**alt).fingerprint() != f1, field)


def test_b2_resolution_is_stable_within_a_process():
    print('\nB2 resolving the identity twice reads the same tree')
    a, b = CI.code_identity(), CI.code_identity()
    check('both resolve', a.state is State.PASS and b.state is State.PASS)
    check('code_version is stable',
          a.value['code_version'] == b.value['code_version'])
    check('the source digest is stable',
          a.value['source_scope_sha256'] == b.value['source_scope_sha256'])
    check('the runtime token is stable',
          a.value['runtime_token'] == b.value['runtime_token'])


# ===========================================================================
# SECTION C -- scope: source moves it, generated artifacts do not
# ===========================================================================
def test_c_a_production_source_byte_moves_the_identity():
    print('\nC  one byte of relevant production SOURCE changes identity')
    # No tracked file is edited. A new .py inside a source root IS dirty source
    # under the contract, which is the same observable a one-byte edit produces.
    target = ROOT / 'nfl' / 'production' / 'ws_e_probe_source.py'
    before = cv()
    try:
        target.write_text('WS_E_PROBE = 1\n')
        one = cv()
        target.write_text('WS_E_PROBE = 2\n')
        two = cv()
    finally:
        target.unlink(missing_ok=True)
    after = cv()
    check('adding relevant source moves the identity', one != before,
          f'{before} -> {one}')
    check('changing ONE BYTE of it moves the identity again', two != one,
          f'{one} -> {two}')
    check('removing it restores the identity', after == before,
          f'{before} -> {after}')


def test_c2_a_generated_artifact_does_not_move_the_identity():
    print('\nC2 a GENERATED artifact does not change identity')
    before = cv()
    made = []
    try:
        for rel in CI.GENERATED_SUBTREES:
            d = ROOT / rel / 'ws_e_probe'
            d.mkdir(parents=True, exist_ok=True)
            made.append(ROOT / rel / 'ws_e_probe')
            (d / 'SEALED_FORECAST.json').write_text('{}\n')
            (d / 'player_draws.npz').write_bytes(b'\x00' * 16)
            # The nastiest case: a .py that LANDS INSIDE a generated subtree.
            # The suffix rule alone would readmit it; EXCLUDED_SUBTREES is what
            # keeps it out, and this is the check that holds that line.
            (d / 'generated_module.py').write_text('X = 1\n')
        during = cv()
    finally:
        for d in made:
            if d.exists():
                shutil.rmtree(d)
    check('generated artifacts leave the identity untouched', during == before,
          f'{before} -> {during}')
    check('a .py inside a generated subtree is still excluded',
          not CI.in_source_scope(
              'nfl/prospective/q9shadow/dryrun/ws_e_probe/generated_module.py'))


def test_c3_unrelated_research_files_do_not_move_the_identity():
    print('\nC3 unrelated non-production research files do not move identity')
    # DECLARED, not incidental. nfl/research/** is out of scope because the
    # research modules that ARE causal are hashed BY CONTENT, individually, into
    # module_source_sha16 -> spec_sha256 -> the fingerprint (identity E). Adding
    # the whole tree to B would move every run id for thousands of non-causal
    # files, which is the dirty-count defect arriving more slowly.
    before = cv()
    d = ROOT / 'nfl' / 'research' / 'ws_e_probe'
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / 'NOTES.md').write_text('a write-up\n')
        (d / 'one_off_script.py').write_text('print(1)\n')
        during = cv()
    finally:
        shutil.rmtree(d, ignore_errors=True)
    check('a research note does not move the identity', during == before,
          f'{before} -> {during}')
    check('a research .py does not move it either (declared, see docstring)',
          not CI.in_source_scope('nfl/research/ws_e_probe/one_off_script.py'))
    check('but a CAUSAL research module still reaches F through E',
          _identity(**dict(BASE)).fingerprint()
          != ExecutionIdentity(
              spec_id='ws-e', spec_sha256='f' * 64,
              code_version=BASE['code_version'],
              interpreter=BASE['interpreter'], seed=BASE['seed'],
              partitions=_identity(**BASE).partitions).fingerprint())


def test_c4_tests_are_out_of_scope_and_that_is_declared():
    print('\nC4 nfl/tests/** is out of scope')
    check('a test file is not source for identity B',
          not CI.in_source_scope('nfl/tests/test_execution_identity.py'))
    check('a production module is', CI.in_source_scope('nfl/production/seeds.py'))
    check('a governance module is', CI.in_source_scope(
        'sportsplatform/governance/outcome.py'))
    check('a json beside a module is not',
          not CI.in_source_scope('nfl/production/FREEZE_V1_R8.json'))


# ===========================================================================
# SECTION D -- the refusal, and that it is reachable
# ===========================================================================
def test_d_count_keyed_code_version_is_refused():
    print('\nD  the withdrawn count-keyed form is refused by the identity')
    bad = dict(BASE)
    bad['code_version'] = '0' * 40 + '+dirty[31]'
    v = _identity(**bad).validate()
    check('validate() FAILs it', v.state is State.FAIL, f'{v.state} {v.code}')
    check('and names it', v.code == 'IDENTITY_CODE_VERSION_KEYS_ON_COUNT', v.code)
    ok = _identity(**BASE).validate()
    check('a contract-form code_version still passes',
          ok.state is State.PASS, f'{ok.state} {ok.code}')
    check('the live resolver produces the contract form',
          not CI.refuses_count_keyed(cv()), cv())


def test_d2_material_is_persisted_not_only_the_digest():
    print('\nD2 the digest MATERIAL is persisted, so the identity is auditable')
    v = CI.code_identity().value
    entries = v['dirty_source_files']
    check('the scope declaration is recorded', bool(v['scope']['source_roots']))
    check('the runtime block is recorded', bool(v['runtime']['python_version']))
    check('hashed vs recorded-only runtime keys are declared',
          set(v['runtime']['hashed_keys']) == set(CI.RUNTIME_HASHED_KEYS))
    check('the demoted whole-tree count is NOT in the sealed block',
          not any('tree_entries' in k for k in v),
          str([k for k in v if 'tree_entries' in k]))
    check('it survives as Outcome evidence instead',
          'n_dirty_tree_entries_observed' in dict(CI.code_identity().evidence))
    check('residual gaps are declared rather than implied',
          len(v['residual_gaps']) >= 3)
    # The digest recomputes from the stored material ALONE.
    check('source_scope_sha256 recomputes from the stored entries',
          CI._digest_entries(entries) == v['source_scope_sha256'])
    bad = 0
    for e in entries:
        if e['state'] != 'PRESENT':
            continue
        b = (ROOT / e['path']).read_bytes()
        if hashlib.sha256(b).hexdigest() != e['sha256'] or len(b) != e['bytes']:
            bad += 1
    check('every recorded dirty source file re-hashes to its stored sha256',
          bad == 0, f'{bad} mismatched')
    check('scope changes are inside the digest',
          CI._digest_entries([]) != hashlib.sha256(
              json.dumps({'entries': []}, sort_keys=True,
                         separators=(',', ':')).encode()).hexdigest())


# ===========================================================================
# SECTION E -- Q9 predictive identity is untouched, and the tree is restored
# ===========================================================================
Q9_BASELINE = {
    'mechanism_spec_version': 'q9-target-hurdle-1',
    'module_source_sha16': {
        'nfl.research.q9.hurdle': 'bb51133641338547',
        'nfl.research.q9b.family': '5b411b4f00e28e6f',
        'nfl.research.q9b.production_parity': '1f320b1ee3170e64',
        'nfl.production.nonqb.layers': '481f005f682cd721',
    },
    'freeze_file_sha16': 'a28e8832430b1420',
}


def test_e_q9_predictive_identity_is_unchanged():
    print('\nE  identity E (predictive candidate) is untouched by this repair')
    from nfl.prospective.q9shadow import candidate as CAND
    fz = ROOT / 'nfl' / 'research' / 'q9b' / 'Q9_PROSPECTIVE_FREEZE.json'
    got = hashlib.sha256(fz.read_bytes()).hexdigest()[:16]
    check('freeze file sha16 matches the Wave 0 baseline',
          got == Q9_BASELINE['freeze_file_sha16'],
          f'{got} != {Q9_BASELINE["freeze_file_sha16"]}')
    fi = CAND.freeze_identity()
    check('mechanism_spec_version matches',
          fi['mechanism_spec_version'] == Q9_BASELINE['mechanism_spec_version'],
          str(fi['mechanism_spec_version']))
    for mod, sha in Q9_BASELINE['module_source_sha16'].items():
        check(f'module_source_sha16 {mod} matches',
              fi['module_source_sha16'].get(mod) == sha,
              f'{fi["module_source_sha16"].get(mod)} != {sha}')


def test_e2_the_tree_is_as_it_was():
    print('\nE2 no probe path survived any section above')
    strays = sorted(
        str(p.relative_to(ROOT)) for p in ROOT.rglob('*ws_e_probe*'))
    check('no ws_e_probe path remains anywhere in the tree',
          not strays, str(strays[:5]))


if __name__ == '__main__':
    test_a_writing_outputs_cannot_alter_identity()
    test_a2_the_guard_is_load_bearing()
    test_a3_a_count_aliases_and_a_digest_does_not()
    test_b_identical_everything_gives_identical_identity()
    test_b2_resolution_is_stable_within_a_process()
    test_c_a_production_source_byte_moves_the_identity()
    test_c2_a_generated_artifact_does_not_move_the_identity()
    test_c3_unrelated_research_files_do_not_move_the_identity()
    test_c4_tests_are_out_of_scope_and_that_is_declared()
    test_d_count_keyed_code_version_is_refused()
    test_d2_material_is_persisted_not_only_the_digest()
    test_e_q9_predictive_identity_is_unchanged()
    test_e2_the_tree_is_as_it_was()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
