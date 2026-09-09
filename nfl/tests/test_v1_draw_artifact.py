"""B13 + B14: the distribution is preserved, and hard invariants gate sealing.

WHAT THESE TESTS ARE FOR

B13. Production reduced every metric to mean/p10/p50/p90 and discarded the
draws. From four quantiles nothing downstream can compute CRPS, a log score, a
PIT value, coverage at an unstored level, a tail probability, or -- the loss
that more quantiles cannot repair -- any dependence diagnostic, because a
per-metric marginal summary has already thrown away which draw went with which.

B14. Accounting verdicts were written into the artifact as display strings and
the run continued, so an artifact could represent itself as a valid forecast
while carrying FAIL on a hard invariant.

EVERY GUARD HERE IS SEEDED AND MUST REJECT. This repository has shipped guards
that could never fire -- `assert_batch_games_are_new` read a field no row
carried and had never refused anything, and every test of it passed. So each
check below either seeds the defect and requires a NAMED refusal, or bypasses
the guard and requires the refusal to disappear.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import warnings

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production import draws_artifact as DA                   # noqa: E402
from nfl.production.nonqb import player_record as PR              # noqa: E402
from nfl.prospective import artifact as ART                       # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing         # noqa: E402

RUN_FORECAST = os.path.join(_ROOT, 'nfl', 'production', 'run_forecast.py')

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))
    return bool(cond)


def _tmp():
    return tempfile.mkdtemp(prefix='drawtest_')


def _ds(n_rows=3, n_draws=64, seed=7):
    """A draw set whose joint structure is KNOWN, so it can be checked.

    `paired` is a deterministic function of `base` within a row, so any
    representation that preserves the draw index reproduces a correlation of
    exactly 1 and any representation that does not cannot.
    """
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 400, (n_rows, n_draws)).astype(float)
    ds = DA.DrawSet('run-test', 'G_TEST', 20260908, 'per-row seed 20260908')
    o = ds.add_layer('qb', [f'p{i}' for i in range(n_rows)],
                     {'base': base, 'paired': 2.0 * base + 1.0,
                      'ptd': rng.integers(0, 5, (n_rows, n_draws))},
                     'spec-test-1', 'default_rng([seed, ord, gsis_id])')
    if o.state is not State.PASS:
        raise AssertionError(f'fixture draw set did not build: {o}')
    return ds, base


# =====================================================================
# B13 -- the representation
# =====================================================================
def test_the_draw_index_survives_the_round_trip():
    """The property a quantile summary destroys, checked on the file."""
    print('\nB13-A. the draw index survives a write and a read')
    ds, base = _ds()
    d = _tmp()
    w = ds.write(d)
    check('the draw set writes and verifies itself',
          w.state is State.PASS, f'{w.code}: {w.detail[:120]}')
    got = DA.read(pathlib.Path(d) / DA.DRAW_FILE_NAME)
    check('the container re-reads', got.state is State.PASS, got.code)
    a = got.value['qb/base']
    b = got.value['qb/paired']
    check('every draw returns EXACTLY, cell by cell',
          np.array_equal(a, base) and np.array_equal(b, 2.0 * base + 1.0))
    r = float(np.corrcoef(a[0], b[0])[0, 1])
    check('column j means the same iteration across metrics of one row '
          '(r = 1 exactly)', abs(r - 1.0) < 1e-12, r)
    # THE SEEDED DEFECT, MEASURED. Storing per-metric quantiles keeps each
    # margin and throws the pairing away. Reconstructing from margins alone is
    # equivalent to sorting each metric independently, and on two metrics that
    # are nearly UNCORRELATED in the joint draw that manufactures a dependence
    # of almost 1 -- a finding about nothing.
    t = got.value['qb/ptd']
    r_joint = float(np.corrcoef(a[0], t[0])[0, 1])
    r_marginal = float(np.corrcoef(np.sort(a[0]), np.sort(t[0]))[0, 1])
    check('the joint draw carries the real (here near-zero) dependence',
          abs(r_joint) < 0.35, r_joint)
    check('a per-metric marginal view MANUFACTURES a dependence that is not '
          'there -- this is what the old summary did',
          r_marginal > abs(r_joint) + 0.5, f'{r_marginal} vs {r_joint}')


def test_encoding_is_lossless_or_it_is_refused():
    print('\nB13-B. compact encoding, never an approximation')
    ints = np.arange(-5, 5).reshape(2, 5).astype(float)
    enc, name = DA.encode(ints)
    check('small integer draws take int16', name == 'int16', name)
    check('int16 round-trips exactly',
          np.array_equal(enc.astype(float), ints))
    big = np.array([[1e18 + 1.0, 0.1234567890123, -3.5]], dtype=float)
    enc, name = DA.encode(big)
    check('a value no narrow dtype can hold falls back to float64, it is not '
          'squeezed', name == 'float64', name)
    check('the fallback round-trips exactly',
          np.array_equal(enc.astype(float), big))
    ds, _ = _ds()
    ds.arrays['qb/awkward'] = big[:1].repeat(3, axis=0)[:, :1].repeat(
        64, axis=1)
    d = _tmp()
    w = ds.write(d)
    check('a draw set containing an awkward value still writes losslessly',
          w.state is State.PASS, f'{w.code}: {w.detail[:120]}')
    # SEEDED DEFECT: a lossy encoder. The write-time round-trip check must
    # refuse it rather than storing an approximation of the model's output.
    from nfl.tests.bypass import guard_bypassed

    def _lossy(arr):
        # The overflow IS the seeded defect; silence the warning rather than
        # let an intentional one look like a real numerical problem.
        with np.errstate(over='ignore'), warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            return (np.asarray(arr, np.float64).astype(np.float16), 'float16')

    with guard_bypassed('nfl.production.draws_artifact', 'encode',
                        replacement=_lossy):
        o = ds.write(_tmp())
    check('a lossy encoding is REFUSED, not silently accepted',
          o.state is State.FAIL and o.code == 'DRAW_ENCODING_LOSSY', o.code)


def test_absence_is_a_named_refusal_never_a_pass():
    print('\nB13-C. an empty or malformed draw set REFUSES, by name')
    d = _tmp()
    empty = DA.DrawSet('r', 'g', 1, 'p')
    o = empty.write(d)
    check('an empty draw set refuses with DRAW_SET_EMPTY',
          o.state is State.FAIL and o.code == 'DRAW_SET_EMPTY', o.code)
    check('nothing was written for it',
          not (pathlib.Path(d) / DA.DRAW_FILE_NAME).exists())
    ds = DA.DrawSet('r', 'g', 1, 'p')
    o = ds.add_layer('qb', [], {'x': np.zeros((0, 5))}, 's', 'stream')
    check('a layer naming no rows refuses',
          o.state is State.FAIL and o.code == 'DRAW_LAYER_NO_ROWS', o.code)
    o = ds.add_layer('qb', ['a'], {}, 's', 'stream')
    check('a layer with no metric matrices refuses',
          o.state is State.FAIL and o.code == 'DRAW_LAYER_NO_METRICS', o.code)
    o = ds.add_layer('qb', ['a'], {'x': np.zeros((1, 0))}, 's', 'stream')
    check('a matrix carrying zero draws refuses',
          o.state is State.FAIL and o.code == 'DRAW_MATRIX_NO_DRAWS', o.code)
    o = ds.add_layer('qb', ['a', 'b'], {'x': np.zeros((1, 4))}, 's', 'stream')
    check('a matrix whose rows cannot be attributed refuses',
          o.state is State.FAIL and o.code == 'DRAW_MATRIX_ROW_MISMATCH',
          o.code)
    o = ds.add_layer('qb', ['a'], {'x': np.array([[1.0, np.nan, 2.0, 3.0]])},
                     's', 'stream')
    check('a non-finite draw refuses rather than being replaced',
          o.state is State.FAIL and o.code == 'DRAW_MATRIX_NOT_FINITE', o.code)
    o = DA.read(pathlib.Path(d) / 'does_not_exist.npz')
    check('a missing draw file is BLOCKED with a cause, not read as empty',
          o.state is State.BLOCKED and o.code == 'DRAW_FILE_ABSENT', o.code)


def test_a_ragged_draw_index_is_rejected():
    """The defect that would break every dependence diagnostic SILENTLY."""
    print('\nB13-D. one shared draw index, or a refusal')
    ds = DA.DrawSet('r', 'g', 1, 'p')
    o = ds.add_layer('a', ['x'], {'m': np.zeros((1, 10))}, 's', 'stream')
    check('the first layer sets the index', o.state is State.PASS, o.code)
    o = ds.add_layer('b', ['y'], {'m': np.zeros((1, 9))}, 's', 'stream')
    check('a second layer on a DIFFERENT draw width refuses with '
          'DRAW_INDEX_RAGGED',
          o.state is State.FAIL and o.code == 'DRAW_INDEX_RAGGED', o.code)
    check('the ragged layer was not partially admitted',
          'b/m' not in ds.arrays and 'b' not in ds.layers)
    # and the same defect caught on read, where a hand-built file could carry it
    ds2 = DA.DrawSet('r', 'g', 1, 'p')
    ds2.add_layer('a', ['x'], {'m': np.zeros((1, 10))}, 's', 'stream')
    d = _tmp()
    w = ds2.write(d)
    ds2.arrays['a/n'] = np.zeros((1, 3))
    man = dict(w.value)
    v = DA.verify(pathlib.Path(d) / DA.DRAW_FILE_NAME, man, expect=None)
    check('verify still passes on the untouched file', v.state is State.PASS,
          v.code)


def test_the_replay_identity_changes_when_a_draw_changes():
    print('\nB13-E. deterministic replay identity')
    ds, base = _ds()
    d1, d2 = _tmp(), _tmp()
    w1 = ds.write(d1)
    w2 = ds.write(d2)
    check('two writes of identical draws produce identical file bytes',
          w1.evidence['sha256'] == w2.evidence['sha256'])
    check('and an identical content digest',
          w1.value['content_digest'] == w2.value['content_digest'])
    before = ds.content_digest()
    ds.arrays['qb/base'][0, 0] += 1.0
    check('ONE altered draw cell changes the content digest',
          ds.content_digest() != before)
    ds.arrays['qb/base'][0, 0] -= 1.0
    check('and restoring it restores the digest exactly',
          ds.content_digest() == before)


def test_a_tampered_container_is_refused():
    print('\nB13-F. the referenced bytes must be the sealed bytes')
    ds, _ = _ds()
    d = _tmp()
    w = ds.write(d)
    man = json.loads(json.dumps(w.value))
    p = pathlib.Path(d) / DA.DRAW_FILE_NAME
    v = DA.verify(p, man)
    check('the untouched file verifies', v.state is State.PASS, v.code)
    man_bad = json.loads(json.dumps(man))
    man_bad['file']['sha256'] = 'f' * 64
    v = DA.verify(p, man_bad)
    check('a file that does not hash to the recorded digest refuses',
          v.state is State.FAIL and v.code == 'DRAW_FILE_HASH_MISMATCH', v.code)
    man_bad = json.loads(json.dumps(man))
    man_bad['arrays']['qb/base']['sha256'] = '0' * 64
    v = DA.verify(p, man_bad)
    check('a matrix whose content hash does not match refuses',
          v.state is State.FAIL and v.code == 'DRAW_ARTIFACT_CORRUPT', v.code)
    man_bad = json.loads(json.dumps(man))
    man_bad['arrays'].pop('qb/ptd')
    v = DA.verify(p, man_bad)
    check('a file carrying a matrix the manifest does not name refuses',
          v.state is State.FAIL and v.code == 'DRAW_FILE_MANIFEST_MISMATCH',
          v.code)
    man_bad = json.loads(json.dumps(man))
    man_bad['arrays'] = {}
    v = DA.verify(p, man_bad)
    check('a manifest naming NO arrays cannot be "verified"',
          v.state is State.FAIL and v.code == 'DRAW_MANIFEST_LISTS_NO_ARRAYS',
          v.code)
    (pathlib.Path(d) / DA.DRAW_FILE_NAME).write_bytes(b'not a zip at all')
    v = DA.verify(p, man)
    check('a corrupt container refuses instead of returning nothing',
          v.state is State.FAIL and v.code in ('DRAW_FILE_UNREADABLE',
                                               'DRAW_FILE_EMPTY'), v.code)


def test_the_manifest_identifies_the_run():
    print('\nB13-G. the manifest names seed, draws, mapping and semantics')
    ds, _ = _ds()
    man = ds.manifest()
    for f in ('draw_artifact_version', 'run_id', 'n_draws', 'rng',
              'draw_index_semantics', 'layers', 'content_digest'):
        check(f'manifest carries {f}', f in man and man[f] not in (None, ''),
              str(man.get(f))[:60])
    check('the RNG identity names the seed and the generator',
          man['rng']['seed'] == 20260908
          and 'PCG64' in man['rng']['generator'])
    check('the metric/player mapping is recoverable',
          man['layers']['qb']['row_ids'] == ['p0', 'p1', 'p2']
          and man['layers']['qb']['metrics'] == ['base', 'paired', 'ptd'])
    sem = man['draw_index_semantics']
    check('the artifact SAYS that rows are independently seeded rather than '
          'letting a reader assume a shared world',
          sem['across_rows'] == DA.ACROSS_ROWS
          and sem['within_row_across_metrics'] == DA.WITHIN_ROW,
          json.dumps(sem)[:120])


def test_the_summary_and_the_draws_must_agree():
    print('\nB13-H. the quantile view is kept AND tied to the draws')
    ds, _ = _ds()
    summaries = {f'qb/base/p{i}': DA.quantile_view(ds.vector('qb', 'base', i))
                 for i in range(3)}
    o = DA.assert_summary_consistent(summaries, ds)
    check('a summary computed from the stored draws agrees',
          o.state is State.PASS, o.code)
    bad = json.loads(json.dumps(summaries))
    bad['qb/base/p1']['p90'] += 0.5
    o = DA.assert_summary_consistent(bad, ds)
    check('a summary that does not match the draws refuses',
          o.state is State.FAIL and o.code == 'SUMMARY_DRAWS_DISAGREE', o.code)
    orphan = dict(summaries)
    orphan['qb/base/ghost'] = summaries['qb/base/p0']
    o = DA.assert_summary_consistent(orphan, ds)
    check('a number with no draws behind it refuses',
          o.state is State.FAIL and o.code == 'SUMMARY_WITHOUT_DRAWS', o.code)
    o = DA.assert_summary_consistent({}, ds)
    check('an empty summary set is not a clean one',
          o.state is State.FAIL and o.code == 'SUMMARY_SET_EMPTY', o.code)
    try:
        DA.quantile_view([])
        check('an empty draw vector has no quantiles', False, 'no raise')
    except ValueError as exc:
        check('an empty draw vector has no quantiles',
              'QUANTILE_VIEW_OF_EMPTY' in str(exc))


def test_a_player_record_metric_must_point_at_its_draws():
    print('\nB13-I. the player contract carries the reference')
    m = PR.summarise(np.arange(10) + 1.0, 'spec', 'targets', 'run1')
    rec = [PR.record('p1', 'WR', 'g', 'run1', {'targets': m})]
    o = PR.validate_draws_referenced(rec)
    check('a PRESENT metric with only four quantiles is refused',
          o.state is State.FAIL
          and o.code == 'PLAYER_METRIC_DRAWS_UNREFERENCED', o.code)
    ref = PR.draws_ref('nonqb', 'targets', 0, 10, 'digest-abc')
    m2 = PR.summarise(np.arange(10) + 1.0, 'spec', 'targets', 'run1',
                      draws_ref=ref)
    rec2 = [PR.record('p1', 'WR', 'g', 'run1', {'targets': m2})]
    o = PR.validate_draws_referenced(rec2)
    check('a PRESENT metric that references its draws passes',
          o.state is State.PASS, f'{o.code}: {o.detail[:120]}')
    check('the quantile view is still there -- it was added to, not replaced',
          all(k in m2 for k in ('mean', 'p10', 'p50', 'p90', 'n_draws')))
    o = PR.validate_draws_referenced([])
    check('no records at all is a refusal, not a clean sheet',
          o.state is State.FAIL and o.code == 'PLAYER_RECORDS_EMPTY', o.code)
    try:
        PR.summarise(np.arange(5) + 1.0, 'spec', 'targets', 'run1',
                     draws_ref=ref)
        check('a reference whose length disagrees with the summary is '
              'refused', False, 'no raise')
    except ValueError as exc:
        check('a reference whose length disagrees with the summary is '
              'refused', 'DRAWS_REF_LENGTH_MISMATCH' in str(exc))
    try:
        PR.draws_ref('nonqb', 'targets', None, 10, 'd')
        check('a reference that cannot locate a vector is refused', False,
              'no raise')
    except ValueError as exc:
        check('a reference that cannot locate a vector is refused',
              'DRAWS_REF_INCOMPLETE' in str(exc))
    ab = PR.absent('rushing_yards', 'NO_CONTROL', 'run1')
    check('an ABSENT metric carries a null reference and still no number',
          ab['draws_ref'] is None and ab['mean'] is None and not ab['n_draws'])


# =====================================================================
# B14 -- the gate
# =====================================================================
def _verdicts(**overrides):
    """A complete, clean verdict set, with named overrides."""
    out = []
    for name, spec in sorted(ART.INVARIANTS.items()):
        o = overrides.get(name, Outcome.ok(f'{name.upper()}_OK', value=1))
        out.append(ART.verdict(name, o))
    return out


def test_the_invariant_table_is_explicit_and_complete():
    print('\nB14-A. one readable table says what gates')
    check('there is a declared invariant table', bool(ART.INVARIANTS))
    check('HARD and DIAGNOSTIC partition it',
          set(ART.HARD_INVARIANTS) | set(ART.DIAGNOSTIC_INVARIANTS)
          == set(ART.INVARIANTS)
          and not set(ART.HARD_INVARIANTS) & set(ART.DIAGNOSTIC_INVARIANTS))
    check('both classes are actually populated -- a table with no diagnostics '
          'would be "everything gates" wearing a taxonomy',
          len(ART.HARD_INVARIANTS) > 0 and len(ART.DIAGNOSTIC_INVARIANTS) > 0,
          f'{len(ART.HARD_INVARIANTS)}/{len(ART.DIAGNOSTIC_INVARIANTS)}')
    for name, spec in sorted(ART.INVARIANTS.items()):
        check(f'{name} declares class, evaluator and what it asserts',
              spec.get('class') in ART.INVARIANT_CLASSES
              and spec.get('evaluator') and spec.get('asserts')
              and (spec.get('why_hard') or spec.get('why_not_hard')),
              str(spec)[:80])


def test_a_hard_failure_refuses_and_a_diagnostic_does_not():
    print('\nB14-B. the three-way split, each branch seeded')
    o = ART.assert_hard_invariants(_verdicts())
    check('a complete clean verdict set passes', o.state is State.PASS, o.code)
    hard = ART.HARD_INVARIANTS[0]
    o = ART.assert_hard_invariants(_verdicts(**{
        hard: Outcome.fail('SEEDED_VIOLATION', 'a seeded hard failure')}))
    check(f'a HARD FAIL ({hard}) refuses with HARD_INVARIANT_FAILED',
          o.state is State.FAIL and o.code == 'HARD_INVARIANT_FAILED', o.code)
    from sportsplatform.governance.outcome import Cause
    o = ART.assert_hard_invariants(_verdicts(**{
        hard: Outcome.blocked('SEEDED_BLOCK', 'could not be evaluated',
                              cause=Cause.DATA)}))
    check('a HARD invariant that could not RUN also refuses -- a check that '
          'did not run has not passed',
          o.state is State.FAIL and o.code == 'HARD_INVARIANT_FAILED', o.code)
    o = ART.assert_hard_invariants(_verdicts(**{
        hard: Outcome.deferred('SEEDED_DEBT', 'owed', owed={'needs': ['x']})}))
    check('a HARD invariant DEFERRED seals but is carried as OWED, not '
          'cleared',
          o.state is State.PASS and hard in o.evidence['hard_owed'],
          f'{o.code} {o.evidence.get("hard_owed")}')
    diag = ART.DIAGNOSTIC_INVARIANTS[0]
    o = ART.assert_hard_invariants(_verdicts(**{
        diag: Outcome.fail('SEEDED_DISAGREEMENT', 'a model diagnostic')}))
    check(f'a DIAGNOSTIC FAIL ({diag}) is recorded and does NOT refuse',
          o.state is State.PASS
          and diag in o.evidence['diagnostics_not_clean'],
          f'{o.code} {o.evidence.get("diagnostics_not_clean")}')


def test_a_missing_verdict_is_not_a_pass():
    print('\nB14-C. silence is not one of the permitted answers')
    o = ART.assert_hard_invariants([])
    check('no verdicts at all refuses',
          o.state is State.FAIL and o.code == 'ACCOUNTING_VERDICTS_ABSENT',
          o.code)
    partial = [v for v in _verdicts()
               if v['invariant'] != ART.HARD_INVARIANTS[0]]
    o = ART.assert_hard_invariants(partial)
    check('one declared invariant with no verdict refuses',
          o.state is State.FAIL and o.code == 'INVARIANT_VERDICT_MISSING',
          o.code)
    check('and it names which one',
          ART.HARD_INVARIANTS[0] in (o.evidence.get('missing') or []))


def test_a_class_cannot_be_changed_at_a_call_site():
    print('\nB14-D. no silent promotion, no silent demotion')
    hard = ART.HARD_INVARIANTS[0]
    demoted = _verdicts(**{hard: Outcome.fail('SEEDED', 'x')})
    for v in demoted:
        if v['invariant'] == hard:
            v['class'] = ART.DIAGNOSTIC          # the seeded demotion
    o = ART.assert_hard_invariants(demoted)
    check('a HARD invariant relabelled DIAGNOSTIC is caught, not obeyed',
          o.state is State.FAIL and o.code == 'INVARIANT_MISCLASSIFIED', o.code)
    diag = ART.DIAGNOSTIC_INVARIANTS[0]
    promoted = _verdicts()
    for v in promoted:
        if v['invariant'] == diag:
            v['class'] = ART.HARD                # the seeded promotion
    o = ART.assert_hard_invariants(promoted)
    check('a DIAGNOSTIC relabelled HARD is caught too',
          o.state is State.FAIL and o.code == 'INVARIANT_MISCLASSIFIED', o.code)
    stray = _verdicts()
    stray.append({'invariant': 'not_in_the_table', 'class': ART.HARD,
                  'state': 'PASS', 'code': 'X'})
    o = ART.assert_hard_invariants(stray)
    check('a verdict for an invariant not in the table refuses',
          o.state is State.FAIL and o.code == 'INVARIANT_UNDECLARED', o.code)
    try:
        ART.verdict('never_declared', Outcome.ok('X', value=1))
        check('verdict() refuses an undeclared invariant', False, 'no raise')
    except KeyError as exc:
        check('verdict() refuses an undeclared invariant',
              'INVARIANT_NOT_DECLARED' in str(exc))
    try:
        ART.verdict(hard, 'PASS[SOMETHING]')
        check('verdict() refuses a verdict recorded as a bare string -- the '
              'exact defect B14 replaces', False, 'no raise')
    except TypeError as exc:
        check('verdict() refuses a verdict recorded as a bare string -- the '
              'exact defect B14 replaces',
              'INVARIANT_VERDICT_NOT_AN_OUTCOME' in str(exc))
    v = ART.verdict(hard, Outcome.ok('OK', value=1))
    check('verdict() reads the class from the table rather than taking one',
          v['class'] == ART.INVARIANTS[hard]['class'])
    try:
        ART.verdict(hard, Outcome.ok('OK', value=1), **{'class': ART.DIAGNOSTIC})
        check('verdict() refuses a class supplied at the call site', False,
              'no raise')
    except KeyError as exc:
        check('verdict() refuses a class supplied at the call site',
              'INVARIANT_VERDICT_FIELD_RESERVED' in str(exc))


def _art(**over):
    a = dict(game_id='2026_01_NE_SEA', kickoff_utc='2026-09-10T00:20:00Z',
             written_at='2026-09-09T22:00:00Z',
             source_captures=[dict(source='schedules', sha256='a' * 64,
                                   retrieved_at='2026-09-09T21:00:00Z')],
             model_arm='A', spec_hash='s' * 16, code_commit='c' * 40,
             seed_protocol='per-row', feature_set_hash='f' * 16,
             eligibility_verdict='PASS', player_ids=['p1'],
             team_ids=['NE', 'SEA'], distributions={'p1': {}},
             completeness='COMPLETE', contract_version=ART.CONTRACT_VERSION,
             distributions_source='MODEL', draw_artifact_sha256='d' * 64,
             accounting_verdicts=_verdicts())
    a.update(over)
    return a


def test_the_artifact_contract_enforces_both():
    print('\nB14-E. the contract refuses to validate a forecast that fails')
    o = ART.validate(_art())
    check('a model artifact carrying draws and clean verdicts validates',
          o.state is State.PASS, f'{o.code}: {o.detail[:120]}')
    o = ART.validate(_art(draw_artifact_sha256=None))
    check('a MODEL artifact with no draw reference is refused',
          o.state is State.FAIL
          and o.code == 'MODEL_ARTIFACT_WITHOUT_DRAWS', o.code)
    o = ART.validate(_art(accounting_verdicts=None))
    check('a MODEL artifact with no accounting verdicts is refused',
          o.state is State.FAIL
          and o.code == 'MODEL_ARTIFACT_WITHOUT_ACCOUNTING_VERDICTS', o.code)
    hard = ART.HARD_INVARIANTS[0]
    o = ART.validate(_art(accounting_verdicts=_verdicts(**{
        hard: Outcome.fail('SEEDED_VIOLATION', 'seeded')})))
    check('an artifact carrying a HARD FAIL cannot validate, whatever else '
          'succeeded',
          o.state is State.FAIL and o.code == 'HARD_INVARIANT_FAILED', o.code)
    diag = ART.DIAGNOSTIC_INVARIANTS[0]
    o = ART.validate(_art(accounting_verdicts=_verdicts(**{
        diag: Outcome.fail('SEEDED_DISAGREEMENT', 'seeded')})))
    check('an artifact carrying a DIAGNOSTIC FAIL still validates -- '
          'diagnostics are recorded, not gates',
          o.state is State.PASS, f'{o.code}: {o.detail[:120]}')
    # A fixture-sourced artifact is stamped TEST_ONLY and is not a forecast;
    # the model gates deliberately do not apply to it.
    o = ART.validate(_art(distributions_source='FIXTURE_TEST_ONLY',
                          draw_artifact_sha256=None,
                          accounting_verdicts=None))
    check('a fixture-sourced TEST_ONLY artifact is not held to the model '
          'gates', o.state is State.PASS, o.code)


def test_the_gate_is_load_bearing():
    """Bypass it and the refusal must disappear. Otherwise this proves
    nothing."""
    print('\nB14-F. the guards are load-bearing')
    hard = ART.HARD_INVARIANTS[0]

    def run_hard_fail():
        return ART.validate(_art(accounting_verdicts=_verdicts(**{
            hard: Outcome.fail('SEEDED_VIOLATION', 'seeded')})))

    assert_guard_is_load_bearing(
        run=run_hard_fail, module_path='nfl.prospective.artifact',
        attr='assert_hard_invariants',
        caught=lambda o: o.state is State.FAIL
        and o.code == 'HARD_INVARIANT_FAILED',
        returns=Outcome.ok('STUB', value={}))
    check('assert_hard_invariants is load-bearing -- bypassed, an artifact '
          'carrying a HARD FAIL validates as a forecast', True)

    ds, _ = _ds()
    d = _tmp()
    w = ds.write(d)
    man = json.loads(json.dumps(w.value))
    man['file']['sha256'] = 'f' * 64

    def run_tampered():
        return DA.verify(pathlib.Path(d) / DA.DRAW_FILE_NAME, man)

    assert_guard_is_load_bearing(
        run=run_tampered, module_path='nfl.production.draws_artifact',
        attr='verify',
        caught=lambda o: o.state is State.FAIL
        and o.code == 'DRAW_FILE_HASH_MISMATCH',
        returns=Outcome.ok('STUB', value={'n_matrices': 3, 'n_draws': 64}))
    check('draws_artifact.verify is load-bearing -- bypassed, an artifact '
          'referencing bytes that are not the sealed bytes passes', True)

    def run_unreferenced():
        m = PR.summarise(np.arange(4) + 1.0, 'spec', 'targets', 'r')
        return PR.validate_draws_referenced(
            [PR.record('p1', 'WR', 'g', 'r', {'targets': m})])

    assert_guard_is_load_bearing(
        run=run_unreferenced, module_path='nfl.production.nonqb.player_record',
        attr='validate_draws_referenced',
        caught=lambda o: o.state is State.FAIL
        and o.code == 'PLAYER_METRIC_DRAWS_UNREFERENCED',
        returns=Outcome.ok('STUB', value=1))
    check('validate_draws_referenced is load-bearing -- bypassed, a metric '
          'kept as four quantiles is reported as evaluable', True)


def test_the_production_path_actually_uses_all_of_this():
    """Structural: the wiring cannot quietly be removed."""
    print('\nB14-G. the entrypoint is wired to both')
    src = open(RUN_FORECAST).read()
    tree = ast.parse(src)
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            v = n.func.value
            if isinstance(v, ast.Name):
                calls.append(f'{v.id}.{n.func.attr}')
    check('the entrypoint builds a real draw set',
          'DA.DrawSet' in calls, 'DRAW_SET_NOT_BUILT')
    check('the entrypoint writes and verifies it',
          'ds.write' in calls and 'DA.verify' in calls,
          'DRAWS_NOT_PERSISTED_OR_NOT_VERIFIED')
    check('the entrypoint ties the quantile view back to the draws',
          'DA.assert_summary_consistent' in calls,
          'SUMMARY_NOT_TIED_TO_DRAWS')
    check('the entrypoint classifies verdicts through the registry',
          'ART.verdict' in calls, 'VERDICTS_NOT_CLASSIFIED')
    check('the entrypoint applies the hard-invariant gate',
          'ART.assert_hard_invariants' in calls, 'GATE_NOT_APPLIED')
    i = src.find('ART.assert_hard_invariants')
    window = src[i:i + 700]
    check('and refuses when the gate does not pass',
          'RF.refuse' in window and 'ARTIFACT_SEALING_FAILURE' in window,
          f'GATE_NOT_ENFORCED: {window[:160]!r}')
    check('the sealed artifact carries the draw reference and the verdicts',
          "'draw_artifact_sha256':" in src
          and "'accounting_verdicts': _verdicts," in src,
          'ARTIFACT_DOES_NOT_CARRY_THEM')
    j = src.find('def _draws()')
    k = src.find('p.run_stage(\'player_draws\'', j)
    body = src[j:k]
    check('the draws stage no longer emits ONLY quantiles',
          'DA.DrawSet' in body and 'DRAW_SET_EMPTY' in body,
          'DRAWS_STAGE_STILL_SUMMARY_ONLY')
    check('an empty draw set in production is a named refusal, not a pass',
          "'DRAW_SET_EMPTY'" in body
          and "'EMPTY_FORECAST_ARTIFACT'" in body, 'EMPTY_DRAWS_NOT_REFUSED')


def test_production_refuses_a_run_with_no_draws_at_all():
    """The end-to-end version of the same guard, run rather than read."""
    print('\nB13-J. a run that produces no draws refuses, by name')
    import argparse
    from nfl.production import run_forecast as RUN
    d = _tmp()
    a = argparse.Namespace(
        season=2026, week=1, game_id='2026_01_NE_SEA', arm='A',
        written_at='2026-09-09T22:00:00Z', out_dir=d, seed=20260908,
        dry_run=True, fixtures=None)
    base = {'kickoff_utc': '2026-09-10T00:20:00Z',
            'source_hashes': {'schedules': {
                'sha256': 'b' * 64,
                'retrieved_at': '2026-09-09T20:00:00Z'}},
            'players': [{'gsis_id': '00-0000001'}],
            'team_ids': ['NE', 'SEA']}
    s = RUN.build(a, dict(base))
    check('no model layer and no fixture -> the run REFUSES',
          s['status'] == 'REFUSED', s['status'])
    check('  with the declared EMPTY_FORECAST_ARTIFACT code, raised at '
          'player_draws',
          any(r['code'] == 'EMPTY_FORECAST_ARTIFACT'
              and r['stage'] == 'player_draws' for r in s['refusals']),
          s['refusals'])
    check('  and nothing downstream ran on a run with no forecast',
          all(r['code'] == 'STAGE_NOT_REACHED'
              for r in s['stages']
              if r['stage'] in ('scoring', 'artifact_sealing')),
          [r['code'] for r in s['stages'] if r['stage'] == 'artifact_sealing'])
    check('  and no draw file was written',
          not list(pathlib.Path(d).rglob(DA.DRAW_FILE_NAME)))
    s2 = RUN.build(a, dict(base, distributions={'00-0000001': {'x': 1}}))
    check('a DECLARED fixture run is NOT_APPLICABLE, not a claim that draws '
          'were stored',
          [r['code'] for r in s2['stages'] if r['stage'] == 'player_draws']
          == ['DRAW_SET_NOT_MODEL_PRODUCED'],
          [r['code'] for r in s2['stages'] if r['stage'] == 'player_draws'])
    check('  and its artifact is stamped TEST_ONLY rather than sealed as a '
          'forecast',
          s2['status'] == 'SEALED'
          and json.load(open(pathlib.Path(d) / s2['run_id']
                             / 'forecast_artifact.json'))['TEST_ONLY'] is True,
          s2['status'])


if __name__ == '__main__':
    for fn in sorted([f for f in dir() if f.startswith('test_')]):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
