"""Owner decision RET-001 -- participation retention -- as executable guards.

THE DECISION, 2026-09-08: policy `commit_raw`. Preserve every distinct
PROSPECTIVELY OBSERVED raw version of `pbp_participation` and `snap_counts`.

WHY THIS FILE EXISTS RATHER THAN A PARAGRAPH

A retention policy recorded only in prose is one refactor away from being a
different policy that nobody noticed changing, and the change is invisible
precisely because the bytes it discards are the evidence that would have shown
it. Every clause of the decision is tested here as a refusal, and the three new
guards each carry a deletion proof.

The asymmetry that makes this worth the trouble: keeping too much costs disk,
which is recoverable. Dropping a vintage is not recoverable at any price,
because upstream OVERWRITES these files -- that is the whole reason the watch
exists.

Run standalone:  python3.12 nfl/tests/test_availability_retention.py
"""
import contextlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Outcome, State        # noqa: E402
from nfl.capture import availability as AV                          # noqa: E402
from nfl.capture import registry as REG                             # noqa: E402
from nfl.tools import watch_availability as W                       # noqa: E402
from nfl.tests.bypass import (assert_guard_is_load_bearing,         # noqa: E402
                              guard_bypassed)
from nfl.tests.test_availability_watch import seeded, GOOD_PART     # noqa: E402

PASSED = FAILED = 0
DECISION = pathlib.Path(AV.RETENTION_DECISION)


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


# ==========================================================================
def test_decision_artifact_is_present_and_says_what_the_code_enforces():
    print('\nRET-001. the artifact and the running system must agree')
    check('the decision artifact exists', DECISION.exists(), str(DECISION))
    doc = json.loads(DECISION.read_text())
    check('  it records policy commit_raw', doc['policy'] == 'commit_raw',
          doc.get('policy'))
    check('  the code enforces the same value',
          AV.RETENTION_POLICY == doc['policy'])
    check('  both watched sources are in scope',
          set(doc['scope']['sources']) == set(AV.WATCHED),
          doc['scope']['sources'])
    check('  it states it does NOT authorize predictive use',
          any('predictive use' in x for x in doc['what_this_decision_does_NOT_do']))
    check('  it states G0A is unchanged',
          any('G0A' in x for x in doc['what_this_decision_does_NOT_do']))
    check('  every requirement names an enforcing guard AND a test',
          all(r.get('enforced_by') and r.get('test') for r in doc['requirements']),
          [r['id'] for r in doc['requirements']
           if not (r.get('enforced_by') and r.get('test'))])
    # A named test that does not exist would make the artifact a work of
    # fiction, which is worse than an artifact that claims nothing.
    named = {r['test'].split('.')[0] for r in doc['requirements']}
    for mod in sorted(named):
        check(f'  the test module {mod} it names actually exists',
              (pathlib.Path(__file__).parent / f'{mod}.py').exists(), mod)


# ==========================================================================
def test_r1_r7_only_commit_raw_is_permitted():
    print('\nR1/R7. content-addressed commit_raw, and nothing else')
    for src in AV.WATCHED:
        o = AV.assert_retention_policy(src)
        check(f'{src} passes the retention check', o.state is State.PASS, o.code)
        check(f'  {src} declares durability commit_raw',
              REG.BY_NAME[src].durability == 'commit_raw',
              REG.BY_NAME[src].durability)
    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
        blob = pathlib.Path(rec['blob']).name
    check('the blob filename is content-addressed by its sha256',
          rec['sha256'][:16] in blob, blob)
    check('  and the row records which decision governs it',
          rec['retention_policy'] == 'commit_raw'
          and rec['retention_decision_id'] == 'RET-001')


def test_r7_reduction_and_newest_n_are_refused():
    print('\nR7. a reduction or newest-N policy is refused, not silently applied')
    import dataclasses
    for bad in ('reduce', 'ephemeral', 'newest_n'):
        spec = dataclasses.replace(REG.BY_NAME['pbp_participation'],
                                   durability=bad)
        orig = REG.BY_NAME['pbp_participation']
        REG.BY_NAME['pbp_participation'] = spec
        try:
            o = AV.assert_retention_policy('pbp_participation')
            check(f'durability={bad!r} -> FAIL RETENTION_POLICY_VIOLATED',
                  o.state is State.FAIL
                  and o.code == 'RETENTION_POLICY_VIOLATED', o.code)
            # and the probe refuses BEFORE requesting bytes
            with seeded(body=GOOD_PART) as (root, tmp):
                out = W.probe('pbp_participation', 2026, root, tmp)
            check(f'  the probe refuses to fetch under durability={bad!r}',
                  out.state is State.FAIL
                  and out.code == 'RETENTION_POLICY_VIOLATED', out.code)
            check('  and stored nothing',
                  not out.evidence.get('blob') and not out.evidence.get('sha256'))
        finally:
            REG.BY_NAME['pbp_participation'] = orig
    check('the registry is restored',
          REG.BY_NAME['pbp_participation'].durability == 'commit_raw')


def test_r7b_the_artifact_and_the_code_cannot_drift_apart():
    print('\nR7b. a record that disagrees with the running system is caught')
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'dec.json'
        doc = json.loads(DECISION.read_text())
        p.write_text(json.dumps({**doc, 'policy': 'reduce'}))
        o = AV.assert_retention_policy('pbp_participation', decision_path=p)
        check('artifact says reduce, code enforces commit_raw -> FAIL',
              o.state is State.FAIL
              and o.code == 'RETENTION_DECISION_DISAGREES_WITH_CODE', o.code)
        p.write_text(json.dumps({**doc, 'scope': {**doc['scope'],
                                                  'sources': ['snap_counts']}}))
        o2 = AV.assert_retention_policy('pbp_participation', decision_path=p)
        check('a watched source outside the decision scope -> FAIL',
              o2.state is State.FAIL
              and o2.code == 'SOURCE_OUTSIDE_RETENTION_DECISION', o2.code)
        o3 = AV.assert_retention_policy('pbp_participation',
                                        decision_path=pathlib.Path(d) / 'gone')
        check('an enforced policy with no recorded decision -> BLOCKED',
              o3.state is State.BLOCKED
              and o3.code == 'RETENTION_DECISION_ARTIFACT_MISSING', o3.code)


# ==========================================================================
def test_r2_r3_identical_bytes_reuse_changed_bytes_add():
    print('\nR2/R3. identical bytes add no blob; changed bytes add one')
    with seeded(body=GOOD_PART) as (root, tmp):
        W.probe('pbp_participation', 2026, root, tmp)
        W.probe('pbp_participation', 2026, root, tmp)
        check('two identical observations -> one blob',
              len(list(root.glob('*.csv.gz'))) == 1)
        v1 = {p.name for p in root.glob('*.csv.gz')}
        changed = GOOD_PART + b'z\n'
        with seeded(body=changed) as (_r, tmp2):
            W.probe('pbp_participation', 2026, root, tmp2)
        v2 = {p.name for p in root.glob('*.csv.gz')}
        check('  changed bytes -> a second blob', len(v2) == 2)
        check('  and the first is still there (R4 holds across the change)',
              AV.assert_no_vintage_deleted(v1, v2).state is State.PASS)


def test_r4_no_vintage_may_be_deleted():
    print('\nR4. an earlier vintage may never be dropped for a later one')
    o = AV.assert_no_vintage_deleted({'a.gz', 'b.gz'}, {'a.gz', 'b.gz', 'c.gz'})
    check('adding a vintage is fine', o.state is State.PASS, o.code)
    o2 = AV.assert_no_vintage_deleted({'a.gz', 'b.gz'}, {'b.gz', 'c.gz'})
    check('dropping the oldest for a newer one -> FAIL VINTAGE_DELETED',
          o2.state is State.FAIL and o2.code == 'VINTAGE_DELETED', o2.code)
    check('  and it names what was lost', o2.evidence['lost'] == ['a.gz'])
    # The case a count would miss: swap one for another, count unchanged.
    o3 = AV.assert_no_vintage_deleted({'a.gz', 'b.gz'}, {'a.gz', 'c.gz'})
    check('a newest-N swap keeps the COUNT identical and is still caught',
          o3.state is State.FAIL and o3.evidence['lost'] == ['b.gz'], o3.code)
    o4 = AV.assert_no_vintage_deleted({'a.gz'}, set())
    check('emptying the store is caught', o4.state is State.FAIL)


def test_r5_manifest_is_append_only():
    print('\nR5. every observation row is preserved, unedited and in order')
    a, b, c = '{"i":1}', '{"i":2}', '{"i":3}'
    o = AV.assert_manifest_append_only([a, b], [a, b, c])
    check('appending is fine', o.state is State.PASS and o.value == 1, o.code)
    o2 = AV.assert_manifest_append_only([a, b], [a])
    check('losing a row -> FAIL MANIFEST_ROWS_LOST',
          o2.state is State.FAIL and o2.code == 'MANIFEST_ROWS_LOST', o2.code)
    o3 = AV.assert_manifest_append_only([a, b], [a, '{"i":9}', c])
    check('EDITING a row in place -> FAIL MANIFEST_ROW_REWRITTEN '
          '(the row count is unchanged, so a count check would miss it)',
          o3.state is State.FAIL and o3.code == 'MANIFEST_ROW_REWRITTEN', o3.code)
    check('  and it names the row', o3.evidence['row'] == 2)
    o4 = AV.assert_manifest_append_only([a, b], [b, a])
    check('reordering is caught too', o4.state is State.FAIL, o4.code)

    # first-seen is the other half of R5
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'fs.json'
        AV.record_first_seen('k', {'first_retrieved_at': 'T1'}, path=p)
        r = AV.record_first_seen('k', {'first_retrieved_at': 'T2'}, path=p)
        check('first-seen survives a later observation',
              r.state is State.NOT_APPLICABLE
              and AV.load_first_seen(p)['k']['first_retrieved_at'] == 'T1')


def test_r6_raw_sha_remains_authoritative():
    print('\nR6. the raw SHA decides, and the blob is re-checkable against it')
    import gzip
    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
        blob = pathlib.Path(rec['blob'])
        raw = gzip.open(blob, 'rb').read()
        check('the stored blob decompresses to the original bytes',
              raw == GOOD_PART)
        import hashlib
        check('  and its sha256 is the recorded one',
              hashlib.sha256(raw).hexdigest() == rec['sha256'])
        check('  the row says the digest is of the UNCOMPRESSED bytes',
              rec['sha256_is_of'] == 'uncompressed_bytes')
        check('  verification passes', AV.verify_record(rec).state is State.PASS)
        # A rewritten blob must not keep passing.
        with gzip.open(blob, 'wb') as fh:
            fh.write(GOOD_PART + b'tampered\n')
        check('  a tampered blob is caught by the digest, not trusted',
              AV.verify_record(rec).code == 'RECORD_DIGEST_MISMATCH')


def test_r8_a_dropped_in_blob_is_not_vintage_evidence():
    print('\nR8. a historical file dropped into the store is not a vintage')
    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
        lines = [json.dumps(rec)]
        names = {p.name for p in root.glob('*')}
        o = AV.assert_no_orphan_blobs(names, lines)
        check('every observed blob is named by its manifest row',
              o.state is State.PASS, o.code)
        # Now backfill a historical file by hand.
        (root / 'pbp_participation_2019.deadbeefdeadbeef.csv.gz').write_bytes(b'x')
        names2 = {p.name for p in root.glob('*')}
        o2 = AV.assert_no_orphan_blobs(names2, lines)
        check('a hand-dropped 2019 file -> FAIL '
              'ORPHAN_BLOB_NOT_FROM_AN_OBSERVATION',
              o2.state is State.FAIL
              and o2.code == 'ORPHAN_BLOB_NOT_FROM_AN_OBSERVATION', o2.code)
        check('  and it names the orphan',
              'pbp_participation_2019.deadbeefdeadbeef.csv.gz'
              in o2.evidence['orphans'])
    # The other half of R8: the decision itself says historical files are
    # schema references, never prospective evidence.
    doc = json.loads(DECISION.read_text())
    check('the decision scopes itself to PROSPECTIVELY observed versions',
          'PROSPECTIVELY' in doc['scope']['applies_to'].upper(),
          doc['scope']['applies_to'])
    check('  and excludes historical final files explicitly',
          'historical final files' in doc['scope']['does_not_apply_to'])
    for src in AV.WATCHED:
        check(f'  {src} still derives no as-of window from Last-Modified',
              REG.BY_NAME[src].narrow_to_kind is None)


# ==========================================================================
def test_the_decision_changes_retention_and_nothing_else():
    print('\nSCOPE. retention only -- everything else is unchanged')
    for src in AV.WATCHED:
        for kind in ('practice', 'final_status', 'inactives'):
            check(f'{src} still cannot discharge {kind}',
                  REG.can_discharge(src, kind) is False)
        check(f'{src} is still watch_only', REG.BY_NAME[src].watch_only is True)
    from nfl.tools import capture_vintage as CV
    fetched = [s.name for s in CV._sources(2026)]
    for src in AV.WATCHED:
        check(f'{src} is still absent from the vintage capture path',
              src not in fetched)
    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
        el = AV.eligibility_record(rec)
    check('predictive use is STILL not authorized',
          el['authorized'] is False
          and el['authorization_code'] == 'NOT_AUTHORIZED_BY_OWNER')
    check('  and the row still claims no discharge', rec['discharges'] == [])


# ==========================================================================
def test_guard_deletions():
    print('\nGUARD DELETIONS: bypass each new guard, lose the refusal')

    import dataclasses
    orig = REG.BY_NAME['pbp_participation']

    def run_retention():
        REG.BY_NAME['pbp_participation'] = dataclasses.replace(
            orig, durability='reduce')
        try:
            with seeded(body=GOOD_PART) as (root, tmp):
                return W.probe('pbp_participation', 2026, root, tmp)
        finally:
            REG.BY_NAME['pbp_participation'] = orig
    assert_guard_is_load_bearing(
        run=run_retention, module_path='nfl.capture.availability',
        attr='assert_retention_policy',
        caught=lambda o: o.state is State.FAIL
        and o.code == 'RETENTION_POLICY_VIOLATED',
        returns=Outcome.ok('STUB', value='commit_raw'))
    check('assert_retention_policy is load-bearing '
          '(bypassed, a reduce policy fetches and stores anyway)', True)

    def run_deleted():
        return AV.assert_no_vintage_deleted({'a.gz', 'b.gz'}, {'b.gz'})
    assert_guard_is_load_bearing(
        run=run_deleted, module_path='nfl.capture.availability',
        attr='assert_no_vintage_deleted',
        caught=lambda o: o.state is State.FAIL and o.code == 'VINTAGE_DELETED',
        returns=Outcome.ok('STUB', value=0))
    check('assert_no_vintage_deleted is load-bearing', True)

    def run_manifest():
        return AV.assert_manifest_append_only(['{"i":1}'], ['{"i":9}'])
    assert_guard_is_load_bearing(
        run=run_manifest, module_path='nfl.capture.availability',
        attr='assert_manifest_append_only',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value=0))
    check('assert_manifest_append_only is load-bearing', True)

    def run_orphan():
        return AV.assert_no_orphan_blobs({'ghost.csv.gz'}, [])
    assert_guard_is_load_bearing(
        run=run_orphan, module_path='nfl.capture.availability',
        attr='assert_no_orphan_blobs',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value=0))
    check('assert_no_orphan_blobs is load-bearing', True)


if __name__ == '__main__':
    test_decision_artifact_is_present_and_says_what_the_code_enforces()
    test_r1_r7_only_commit_raw_is_permitted()
    test_r7_reduction_and_newest_n_are_refused()
    test_r7b_the_artifact_and_the_code_cannot_drift_apart()
    test_r2_r3_identical_bytes_reuse_changed_bytes_add()
    test_r4_no_vintage_may_be_deleted()
    test_r5_manifest_is_append_only()
    test_r6_raw_sha_remains_authoritative()
    test_r8_a_dropped_in_blob_is_not_vintage_evidence()
    test_the_decision_changes_retention_and_nothing_else()
    test_guard_deletions()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
