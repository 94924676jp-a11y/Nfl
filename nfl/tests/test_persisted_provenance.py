"""A manifest row must describe the bytes it actually stored.

THE DEFECT THESE CHECKS CLOSE, measured on the manifest at HEAD 837d52f:

  368 of 1,061 PASS rows -- 34.7%, every `depth_charts` and `weekly_rosters`
  capture without exception -- fail their own manifest hash. The recorded
  `sha256`, `n_bytes` and `n_lines` describe the FULL UPSTREAM FILE; the file
  actually persisted is a column-reduced subset whose hash was never recorded
  anywhere. `coverage._blob_ok` re-hashes the blob and returns
  RAW_SHA256_MISMATCH on all of them, so every one self-excludes from
  discharge.

Nothing was corrupt. A claim was made about a different object from the one
stored -- a reduction step whose output was never checked against a claim made
about its input.

TWO PROPERTIES ARE UNDER TEST AND THEY ARE NOT THE SAME PROPERTY.

  SELF-VERIFICATION  a reader holding only the blob and its manifest row can
                     confirm the row describes the blob.
  FAITHFULNESS       the blob is the correct reduction of the attested upstream
                     bytes.

Hashing a blob on disk and writing the digest into its row buys the first and
proves nothing about the second, and a migration that did only that would make
all 368 rows look repaired while establishing nothing. So the historical half
of these checks is mostly about what the repair REFUSES to claim.

No network. No sportsbook data. Nothing here writes to the live vintage store
or the live manifest; every write goes to a temporary root.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.capture import persisted_provenance as PP  # noqa: E402
from nfl.capture import registry as REG  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

TOOL = pathlib.Path(_ROOT) / 'nfl' / 'tools' / 'capture_vintage.py'

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _load_cv():
    loader = importlib.machinery.SourceFileLoader('_cv_under_test', str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = mod
    loader.exec_module(mod)
    return mod


CV = _load_cv()

# A tiny dt-versioned frame, shaped like depth_charts: two snapshots, five of
# which columns survive the reduction and two of which do not.
_CSV = (b'dt,team,gsis_id,pos_abb,pos_rank,full_name,jersey\n'
        b'2026-09-01T00:00:00Z,BUF,00-1,QB,1,Old Guy,7\n'
        b'2026-09-08T00:00:00Z,BUF,00-2,QB,1,New Guy,9\n'
        b'2026-09-08T00:00:00Z,BUF,00-3,RB,1,Other,22\n')
_COLS = ('dt', 'team', 'gsis_id', 'pos_abb', 'pos_rank')


def _staged_pairs(stored):
    """The staged (pending, final) pairs of a `_persist` result.

    `_staged` was ONE pair until the Ruling 3 raw retention (2026-09-14) gave
    `reduce` a second staged blob: the reduction AND the full upstream file,
    both durable. Indexing `[0]` as a path silently measured half the change,
    so the shape is read through the tool's own normaliser.
    """
    return CV._normalise_staged(stored.get('_staged'))


def _reduced_staged(stored):
    """The staged path of the REDUCED blob specifically."""
    want = pathlib.PurePosixPath(stored['blob']).name
    for pend, _final in _staged_pairs(stored):
        if pathlib.PurePosixPath(pend).name == want:
            return pathlib.Path(pend)
    raise AssertionError(f'no staged entry for the reduced blob {want}')


def _src(name='depth_charts', durability='reduce'):
    return CV.Source(name=name, url='https://example.invalid/x.csv',
                     required=True, durability=durability,
                     reduce_cols=_COLS, content_kind='csv')


class _Sandbox:
    """A temporary durable root. The live store is never written by a test."""

    def __enter__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='ws_k_prov_'))
        self._old_durable = CV.DURABLE_ROOT
        CV.DURABLE_ROOT = self.tmp / 'vintage'
        CV.DURABLE_ROOT.mkdir(parents=True, exist_ok=True)
        self.store = self.tmp / 'ephemeral'
        (self.store / 'raw').mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *a):
        CV.DURABLE_ROOT = self._old_durable
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


# ----------------------------------------------------------------- forward

def test_reduce_row_carries_a_digest_of_the_bytes_it_stored():
    """The repair itself: two objects, two names, both written."""
    with _Sandbox() as sb:
        payload = _CSV
        up = hashlib.sha256(payload).hexdigest()
        stored = CV._persist(_src(), payload, up, sb.store)

        assert check('the row names the upstream digest explicitly',
                     stored['upstream_content_sha256'] == up)
        ps = stored.get('persisted_content_sha256')
        assert check('the row names a digest of the persisted bytes',
                     bool(ps) and len(ps) == 64, repr(ps))
        assert check('the two digests are different objects and differ',
                     ps != up,
                     'a reduction that hashes to its input is not a reduction')
        assert check('persisted_is_upstream_verbatim is false on a reduction',
                     stored['persisted_is_upstream_verbatim'] is False)
        # THE SENTENCE THAT WAS FALSE ON 366 ROWS.
        assert check('sha256_is_of no longer claims the blob\'s own bytes',
                     stored['sha256_is_of'] ==
                     'upstream_bytes_only__blob_is_a_reduction',
                     stored['sha256_is_of'])

        staged = _reduced_staged(stored)
        got = hashlib.sha256(gzip.open(staged, 'rb').read()).hexdigest()
        assert check('  and the digest matches the bytes on disk', got == ps)


def test_the_reduction_itself_is_auditable():
    """Transformation identity, input digest, output digest, schema, code id."""
    with _Sandbox() as sb:
        up = hashlib.sha256(_CSV).hexdigest()
        t = CV._persist(_src(), _CSV, up, sb.store)['transformation']
        for k in ('transform_id', 'transform_version', 'code_sha256',
                  'code_symbol', 'input_sha256', 'output_sha256',
                  'output_columns', 'row_filter'):
            assert check(f'  transformation records {k}', bool(t.get(k)))
        assert check('the input digest is the upstream file',
                     t['input_sha256'] == up)
        assert check('the output digest is the persisted blob',
                     t['output_sha256'] ==
                     CV._persist(_src(), _CSV, up, sb.store)
                     ['persisted_content_sha256'])
        assert check('the schema actually written is recorded',
                     t['output_columns'] == list(_COLS), t['output_columns'])
        assert check('the discarded columns are not silently absent',
                     'full_name' not in t['output_columns'])
        assert check('the row filter is named, not implied',
                     t['row_filter'] == 'newest_dt_slice'
                     and t['row_filter_value'] == '2026-09-08T00:00:00Z')
        assert check('  and it kept only the newest slice',
                     t['rows_kept'] == 2 and t['rows_in_file'] == 3)
        assert check('the code identity is a measurement of the code',
                     t['code_sha256'] == CV._transform_code_identity())
        assert check('irreversibility is stated, not left to be discovered',
                     t['reversible'] is False)


def test_commit_raw_records_the_two_digests_as_equal_rather_than_omitting_one():
    """Absence is not a statement. Equal is."""
    with _Sandbox() as sb:
        payload = b'a,b\n1,2\n'
        up = hashlib.sha256(payload).hexdigest()
        stored = CV._persist(_src(name='injuries', durability='commit_raw'),
                             payload, up, sb.store)
        assert check('commit_raw carries persisted_content_sha256 too',
                     stored['persisted_content_sha256'] == up)
        assert check('  and says the two are the same object',
                     stored['persisted_is_upstream_verbatim'] is True)
        assert check('  with sha256_is_of naming both',
                     'persisted_uncompressed_bytes' in stored['sha256_is_of'])


def test_a_blob_cannot_exist_in_the_store_without_its_manifest_row():
    """WS-J's invariant, seen from the capture side.

    Fifty GitHub-Actions runs committed a blob and appended zero manifest rows;
    48 orphan blobs survive and all of 2026-09-09 is absent from the manifest.
    The guard that existed raised AFTER the blobs were already in nfl/vintage,
    so it made the orphan loud without preventing it. Ordering prevents it.
    """
    with _Sandbox() as sb:
        up = hashlib.sha256(_CSV).hexdigest()
        stored = CV._persist(_src(), _CSV, up, sb.store)
        final = pathlib.Path(_ROOT) / stored['blob']
        final = CV.DURABLE_ROOT / pathlib.PurePosixPath(stored['blob']).name
        assert check('nothing is in the durable store before the row is written',
                     not final.exists(),
                     'a blob reached nfl/vintage before its manifest row')
        raw_final = CV.DURABLE_ROOT / pathlib.PurePosixPath(
            stored['raw_blob']).name
        assert check('  nor is the RAW blob, which is staged the same way',
                     not raw_final.exists())
        pairs = _staged_pairs(stored)
        assert check('  a reduce source stages BOTH the reduction and the raw '
                     'upstream file', len(pairs) == 2,
                     str([pathlib.PurePosixPath(q).name for q, _ in pairs]))
        for pend, _f in pairs:
            q = pathlib.Path(pend)
            assert check(f'  {q.name} is staged outside the tracked store',
                         q.exists() and 'vintage' not in str(q.parent))

        moved = CV._promote_staging([stored['_staged']])
        assert check('promotion after the row lands puts both in the store',
                     final.exists() and raw_final.exists() and len(moved) == 2,
                     str(moved))


def test_a_run_that_writes_no_row_leaves_no_blob_behind():
    with _Sandbox() as sb:
        up = hashlib.sha256(_CSV).hexdigest()
        stored = CV._persist(_src(), _CSV, up, sb.store)
        n = CV._purge_staging([stored['_staged']])
        final = CV.DURABLE_ROOT / pathlib.PurePosixPath(stored['blob']).name
        assert check('purged staging leaves the durable store empty',
                     n == 2 and not final.exists()
                     and not list(CV.DURABLE_ROOT.glob('*')),
                     f'purged {n}, store holds '
                     f'{sorted(q.name for q in CV.DURABLE_ROOT.glob("*"))}')


def test_a_pass_row_may_not_claim_a_capture_it_cannot_name():
    """The other half of WS-J's requirement, read exactly as an auditor would."""
    _ret = {'raw_bytes': 'nfl/vintage/x.raw.csv.gz', 'raw_hash': 'b' * 64,
            'transformation_version': CV.TRANSFORM_VERSION,
            'reduced_artifact': 'nfl/vintage/x.gz', 'reduced_hash': 'a' * 64,
            'raw_home_is_gitignored_only': False}
    ok_row = {'state': 'PASS', 'source': 'x',
              'value': {'blob': 'nfl/vintage/x.gz',
                        'persisted_content_sha256': 'a' * 64,
                        'upstream_content_sha256': 'b' * 64,
                        'raw_blob_durable': True,
                        'retention_ruling3': dict(_ret)}}
    try:
        CV._assert_no_pass_without_capture([ok_row])
        assert check('a complete PASS row is accepted', True)
    except SystemExit as exc:
        assert check('a complete PASS row is accepted', False, str(exc))

    for label, val in (
            ('with no artifact', {'upstream_content_sha256': 'b' * 64}),
            ('with no digest of the persisted bytes',
             {'blob': 'nfl/vintage/x.gz', 'upstream_content_sha256': 'b' * 64}),
            ('with a malformed persisted digest',
             {'blob': 'nfl/vintage/x.gz', 'persisted_content_sha256': 'short',
              'upstream_content_sha256': 'b' * 64}),
            ('with no upstream digest',
             {'blob': 'nfl/vintage/x.gz',
              'persisted_content_sha256': 'a' * 64}),
            # RULING 3. A row that stored bytes but cannot name the raw
            # artifact, or whose only raw home is gitignored, is claiming a
            # retention it does not have.
            ('with no Ruling 3 retention block at all',
             {'blob': 'nfl/vintage/x.gz', 'persisted_content_sha256': 'a' * 64,
              'upstream_content_sha256': 'b' * 64, 'raw_blob_durable': True}),
            ('whose raw bytes live only in a gitignored home',
             {'blob': 'nfl/vintage/x.gz', 'persisted_content_sha256': 'a' * 64,
              'upstream_content_sha256': 'b' * 64, 'raw_blob_durable': False,
              'retention_ruling3': dict(_ret,
                                        raw_home_is_gitignored_only=True)}),
            ('that names no durable raw blob',
             {'blob': 'nfl/vintage/x.gz', 'persisted_content_sha256': 'a' * 64,
              'upstream_content_sha256': 'b' * 64, 'raw_blob_durable': False,
              'retention_ruling3': dict(_ret)})):
        bad = {'state': 'PASS', 'source': 'x', 'value': val}
        raised = False
        try:
            CV._assert_no_pass_without_capture([bad])
        except SystemExit:
            raised = True
        assert check(f'a PASS row {label} is refused', raised,
                     'MANIFEST_CLAIMED_PASS_WITHOUT_A_QUALIFYING_CAPTURE')


def test_a_persisted_artifact_that_does_not_match_its_digest_is_not_a_pass():
    with _Sandbox() as sb:
        blob = CV.DURABLE_ROOT / 'tampered.csv.gz'
        CV._write_gz_deterministic(blob, b'these are not the bytes you claim')
        raised = False
        try:
            CV._verify_persisted(blob, 'c' * 64, 'tampered')
        except CV.PersistIntegrityError:
            raised = True
        assert check('write-time self-verification refuses a wrong digest',
                     raised)

        good = CV.DURABLE_ROOT / 'good.csv.gz'
        body = b'a,b\n1,2\n'
        CV._write_gz_deterministic(good, body)
        file_sha = CV._verify_persisted(
            good, hashlib.sha256(body).hexdigest(), 'good')
        assert check('  and returns the file digest when it matches',
                     file_sha == hashlib.sha256(good.read_bytes()).hexdigest())
        # A reproducible container is what makes blob_file_sha256 a quantity
        # rather than a timestamp.
        again = CV.DURABLE_ROOT / 'good2.csv.gz'
        CV._write_gz_deterministic(again, body)
        assert check('gzip containers are byte-reproducible',
                     again.read_bytes() == good.read_bytes())


def test_ordering_is_structural_not_incidental():
    """Rows are appended before blobs are promoted, in the source itself."""
    text = TOOL.read_text()
    i_flush = text.index('n_written = _flush(manifest, rows)')
    i_prom = text.index('promoted = _promote_staging(staged)')
    assert check('_flush precedes _promote_staging in main()', i_flush < i_prom)
    assert check('the no-row exit purges staging first',
                 '_purge_staging(staged)\n        raise SystemExit(\n'
                 '            "CAPTURE_WROTE_NO_MANIFEST_ROW' in text)
    assert check('no durability path still claims "uncompressed_bytes" bare',
                 '"sha256_is_of": "uncompressed_bytes"' not in text)


# ---------------------------------------------------------------- historical

def test_the_live_manifest_still_carries_the_defect_unaltered():
    """NO SILENT REWRITE. The repair is additive; the evidence stays.

    If a later change starts editing historical rows in place, this fails --
    which is the point. The manifest is the record of what was believed when
    each row was written, and a repaired-looking history cannot be told from a
    history that never had the defect.
    """
    # SCOPED TO THE DEFECT POPULATION, NOT TO EVERY REDUCE ROW. The manifest
    # is append-only and grows with every capture, so `reduce_rows()` is a
    # moving number and pinning a frozen count to it fails on the next
    # legitimate capture -- as it did. `defect_rows()` is closed by
    # construction; see its docstring.
    out = PP.defect_rows()
    assert check('defect rows are readable', out.state is State.PASS, out.code)
    n = out.evidence['n_rows']
    assert check('the measured population is still 368 defect rows',
                 n == 368, f'{n}')
    assert check('  and the repaired rows are outside it, not edited into it',
                 out.evidence['n_reduce_rows_total'] >= n,
                 str(out.evidence))
    rewritten = [r for rows in out.value.values() for r in rows
                 if (r.get('value') or {}).get('persisted_content_sha256')]
    assert check('not one historical row was rewritten in place',
                 not rewritten, f'{len(rewritten)} rows carry a backfilled '
                                f'digest inside vintage_manifest.jsonl')
    still = [r for rows in out.value.values() for r in rows
             if (r.get('value') or {}).get('sha256_is_of') ==
             'uncompressed_bytes']
    assert check('  the false sha256_is_of is preserved as evidence, not edited',
                 len(still) == 366, f'{len(still)}')


def test_recovery_is_earned_from_bytes_and_re_derived_here():
    """Re-run the whole chain now. A recorded digest is not taken on trust.

    manifest declares upstream sha256 -> a retained raw file hashes to exactly
    that -> the reduction of those bytes reproduces the stored blob EXACTLY.
    Only a closed chain licenses a recovered digest.
    """
    recs = PP.load_recovery()
    assert check('the recovery sidecar exists and covers every reduce blob',
                 len(recs) == 15, f'{len(recs)}')

    good = [r for r in recs.values()
            if r['verification_state'] == PP.RECONSTRUCTED_AND_VERIFIED]
    bad = [r for r in recs.values()
           if r['verification_state'] == PP.UNVERIFIABLE_NO_RETAINED_RAW]
    assert check('9 cited blob paths reconstruct, 6 do not',
                 len(good) == 9 and len(bad) == 6,
                 f'{len(good)}/{len(bad)}')

    cols = {s.name: tuple(s.reduce_cols)
            for s in REG.REGISTRY if s.durability == 'reduce'}
    rederived = 0
    for r in good:
        raw = pathlib.Path(_ROOT) / r['recovered_from']
        if not raw.exists():
            # The raw store is gitignored and ephemeral. Its absence does not
            # invalidate the recorded recovery -- it means this check cannot
            # re-run today, which is a different fact and is reported as one.
            continue
        payload = raw.read_bytes()
        if hashlib.sha256(payload).hexdigest() != r['upstream_content_sha256']:
            assert check(f'  raw attests the row for {r["blob"]}', False)
            continue
        rebuilt, _ = CV._reduce_frame(payload, cols[r['source']])
        rs = hashlib.sha256(rebuilt).hexdigest()
        path, _how = PP.resolve_blob(r['blob'])
        stored = hashlib.sha256(PP.read_blob(path)).hexdigest()
        ok = (rs == stored == r['persisted_content_sha256'])
        rederived += ok
        if not ok:
            assert check(f'  chain closes for {r["blob"]}', False,
                         f'{rs[:16]} vs {stored[:16]}')
    assert check('every recorded recovery re-derives from the raw bytes today',
                 rederived == len(good),
                 f'{rederived}/{len(good)} -- if the gitignored raw store was '
                 f'cleared this is 0 and the recovery is no longer re-runnable')


def test_an_unverifiable_row_is_never_quietly_made_to_look_verified():
    """THE ANTI-BACKFILL CHECK, and the most important one here.

    Every one of the 6 unrecovered blobs is sitting on disk and could be hashed
    in one line. Doing so would make all 368 rows self-consistent and would
    establish nothing about whether those blobs are faithful reductions. The
    migration must refuse, and must keep refusing.
    """
    recs = PP.load_recovery()
    bad = [r for r in recs.values()
           if r['verification_state'] != PP.RECONSTRUCTED_AND_VERIFIED]
    assert check('there are unverifiable blobs to test', len(bad) == 6)
    for r in bad:
        assert check(f'  {r["blob"].split("/")[-1]}: no digest is claimed',
                     r['persisted_content_sha256'] is None,
                     'A DIGEST WAS BACKFILLED WITHOUT A CLOSED CHAIN')
        assert check('    and it says why, specifically',
                     len(r.get('why_unverifiable', '')) > 80)
        assert check('    the tamper baseline is named as attesting nothing',
                     'NOT that they are a faithful reduction'
                     in r.get('unattested_blob_digest_attests', ''))


def test_the_loss_has_a_mechanism_and_it_is_not_the_source_or_the_date():
    """WS-L RL-9, reproduced independently from the manifest in this checkout.

    `nfl_vintage/raw/` is gitignored and GitHub-Actions runners are ephemeral,
    so the upstream bytes never leave the runner. Raw retention is therefore a
    property of WHICH MACHINE HAPPENED TO LOOK. That is why the split is a
    clean 6/7 rather than a scatter, and it is the reason the 152 rows are
    permanently unverifiable -- an artifact consumed by governance whose only
    home was an untracked store.
    """
    recs = PP.load_recovery()
    lost = {r['blob'].split('/')[-1].split('.')[1]: r for r in recs.values()
            if r['verification_state'] != PP.RECONSTRUCTED_AND_VERIFIED}
    kept = [r for r in recs.values()
            if r['verification_state'] == PP.RECONSTRUCTED_AND_VERIFIED]

    assert check('every lost vintage was observed ONLY from GitHub Actions',
                 all(r['actions_only'] for r in lost.values()),
                 str({k: v['observed_by_executors'] for k, v in lost.items()}))
    assert check('every recovered vintage was seen at least once elsewhere',
                 not any(r['actions_only'] for r in kept),
                 'a recovered vintage was Actions-only, which would break the '
                 'mechanism')
    # The six WS-L names it as final. Pinned so a later "recovery" of one of
    # them has to explain itself rather than appear.
    for d in ('ecc4973e8715d866', 'f57ef0724d907160', '361f1c69443cba69',
              'e157129706145664', '125c300ff066d314', '0b005c45d924a541'):
        assert check(f'  {d} is recorded lost, with a named mechanism',
                     d in lost and lost[d]['loss_mechanism'] ==
                     'RAW_STORE_IS_GITIGNORED_AND_THE_EXECUTOR_WAS_EPHEMERAL',
                     str(lost.get(d, {}).get('loss_mechanism')))

    # RL-9 applied to THIS repair. The recovered digests are governance
    # evidence; their home must not be the untracked store they came from.
    sidecar = pathlib.Path(_ROOT) / 'nfl' / 'vintage_provenance_recovery.jsonl'
    ignored = os.system(f'cd {_ROOT} && git check-ignore -q '
                        f'nfl/vintage_provenance_recovery.jsonl') == 0
    assert check('the recovery sidecar is not itself gitignored',
                 sidecar.exists() and not ignored,
                 'the repair would inherit the defect it documents')


def test_self_verification_is_a_three_way_answer():
    """PASS / FAIL / BLOCKED. Unverifiable is not the same as wrong."""
    recs = PP.load_recovery()
    out = PP.defect_rows()
    tallies = {}
    for rows in out.value.values():
        for r in rows:
            o = PP.self_verifies(r['value'], recovery=recs)
            k = f'{o.state.value}[{o.code}]'
            tallies[k] = tallies.get(k, 0) + 1

    verified = tallies.get('PASS[PERSISTED_ARTIFACT_SELF_VERIFIES]', 0)
    blockedn = tallies.get('BLOCKED[PERSISTED_DIGEST_ABSENT]', 0)
    assert check('216 of the 368 rows now self-verify', verified == 216,
                 f'{verified}')
    assert check('152 remain unverifiable and are BLOCKED, not FAIL',
                 blockedn == 152, f'{blockedn}')
    assert check('  nothing was reported as an integrity failure',
                 not any(k.startswith('FAIL') for k in tallies), str(tallies))
    assert check('  and the two account for every reduce row',
                 verified + blockedn == 368, str(tallies))

    # A tampered blob must come back FAIL, not BLOCKED. The states must not be
    # interchangeable or the BLOCKED bucket becomes a place to hide damage.
    # An ABSOLUTE path outside the repository. `resolve_blob` joins onto the
    # repo root, and joining an absolute path yields that path, so the probe
    # never touches nfl/vintage. Writing a probe blob into the live store --
    # even one deleted a line later -- would create exactly the orphan this
    # workstream exists to prevent, and a failing check between the two lines
    # would leave it there.
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='ws_k_tamper_'))
    try:
        real = tmp / 'probe.csv.gz'
        CV._write_gz_deterministic(real, b'x,y\n1,2\n')
        blob = str(real)
        o = PP.self_verifies({'blob': blob,
                              'persisted_content_sha256': 'd' * 64})
        assert check('a blob that contradicts its digest is FAIL',
                     o.state is State.FAIL
                     and o.code == 'PERSISTED_CONTENT_SHA256_MISMATCH', o.code)
        o2 = PP.self_verifies({'blob': blob, 'persisted_content_sha256':
                               hashlib.sha256(b'x,y\n1,2\n').hexdigest()})
        assert check('  and one that matches is PASS', o2.state is State.PASS)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        assert check('the probe never entered the live vintage store',
                     not list((pathlib.Path(_ROOT) / 'nfl' / 'vintage')
                              .glob('*ws_k*')))


def test_the_defect_is_reproduced_before_it_is_claimed_repaired():
    """PRE-REPAIR FAILURE, measured, not recalled.

    THE BASELINE IS PINNED HERE, NOT READ FROM A LIVE FUNCTION

    This check originally called `coverage._blob_ok`, on the reasoning that it
    belonged to WS-J and was unpatched. WS-J has since patched it -- correctly,
    and with this workstream's own sidecar -- so calling it now measures the
    REPAIRED world and reports 216 OK, which is the opposite of what a
    pre-repair reproduction is for. A baseline obtained by calling code that
    the repair changes is not a baseline.

    So the withdrawn behaviour is reconstructed verbatim below from
    `HEAD:nfl/capture/coverage.py:104-129`: read `value['sha256']` -- the field
    that describes the UPSTREAM file -- and hash the bytes actually persisted.
    That comparison refused all 368 and always will, because neither operand
    can change. The reconstruction is what makes the 216 meaningful: it is the
    number they are measured against.
    """
    import gzip as _gzip, hashlib as _hashlib

    def _blob_ok(value: dict) -> tuple:
        """`coverage._blob_ok` as it stood at 837d52f, before WS-J's patch."""
        blob = (value or {}).get('blob')
        sha = (value or {}).get('sha256')
        if not blob:
            return False, 'RAW_ARTIFACT_NOT_PERSISTED'
        if not sha or len(sha) != 64:
            return False, 'RAW_SHA256_ABSENT_OR_MALFORMED'
        path = PP._REPO / blob if hasattr(PP, '_REPO') else pathlib.Path(blob)
        if not path.exists():
            return False, f'RAW_ARTIFACT_MISSING_ON_DISK:{blob}'
        try:
            raw = (_gzip.open(path, 'rb').read() if str(path).endswith('.gz')
                   else path.read_bytes())
        except OSError as exc:
            return False, f'RAW_ARTIFACT_UNREADABLE:{type(exc).__name__}'
        if _hashlib.sha256(raw).hexdigest() != sha:
            return False, 'RAW_SHA256_MISMATCH'
        return True, None
    out = PP.defect_rows()
    codes = {}
    for rows in out.value.values():
        for r in rows:
            ok, why = _blob_ok(r['value'])
            codes[('OK' if ok else why.split(':')[0])] = codes.get(
                ('OK' if ok else why.split(':')[0]), 0) + 1
    assert check('zero of the 368 verified before this repair',
                 codes.get('OK', 0) == 0, str(codes))
    assert check('  366 by hash mismatch',
                 codes.get('RAW_SHA256_MISMATCH') == 366, str(codes))
    assert check('  2 by a path missing its .gz suffix',
                 codes.get('RAW_ARTIFACT_MISSING_ON_DISK') == 2, str(codes))
    # And the resolution those 2 need, which is cosmetic next to the hash.
    for b in ('nfl/vintage/depth_charts.76d7bcb384ec11e3.reduced.csv',
              'nfl/vintage/weekly_rosters.5ec59c5228198f57.reduced.csv'):
        p, how = PP.resolve_blob(b)
        assert check(f'  {b.split("/")[-1]} resolves with .gz appended',
                     p is not None and how == 'gz_suffix_appended')


if __name__ == '__main__':
    for name, fn in sorted(list(globals().items())):
        if name.startswith('test_') and callable(fn):
            print(name)
            fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
