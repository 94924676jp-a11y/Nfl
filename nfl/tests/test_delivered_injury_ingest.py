"""Guards on DELIVERED authoritative injury/game-status ingestion.

WHAT THESE TESTS PROTECT.

  * BYTES ARE THE EVIDENCE. A delivery whose files do not hash to its own
    manifest is not authoritative evidence, and the ingestion refuses it
    rather than parsing whatever happens to be on disk.

  * CLOCKS ARE NOT INTERCHANGEABLE. Retrieval, publication, source
    modification, effective date and ingestion are five different facts. The
    delivered clocks are carried through unchanged; the ingestion clock never
    overwrites any of them. Restamping two-day-old evidence with the ingestion
    time would make it look fresh to the chronology gate, which is the exact
    failure this path exists to prevent.

  * REFUSALS ARE REFUSALS, NOT CORRECTIONS. A status outside the governed
    vocabulary is refused, never fixed. The live package carries a literal
    `QUESTIONBLE` from nfl.com; a parser that reads that as `Questionable` is
    one that will read something worse as something convenient.

  * ABSENCE OF EVIDENCE IS NOT EVIDENCE OF ABSENCE, IN BOTH DIRECTIONS. An
    explicit team statement of "no injury designations" is recorded as its own
    record kind, and is never turned into injury rows, never turned into a
    silent empty team block, and never given the power to clear a readiness
    gate. Equally, a team with no delivered rows is not thereby healthy.

  * GAME STATUS IS NOT GAME-DAY INACTIVE. Two different facts, two different
    clocks, two different consumers, two different ingestion paths.

  * NATIVE CAPTURE IS UNCHANGED. Delivered evidence enters the same schema at
    the same path convention, and the native capture path keeps its own
    acquisition label and its own behaviour.

EVERY SYNTHETIC CASE RUNS IN A TEMPORARY VINTAGE ROOT AND A TEMPORARY
MANIFEST. Nothing here writes into the live vintage store.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.capture import delivered_injuries as DI                     # noqa: E402
from nfl.production.nonqb import appearance_model as AM              # noqa: E402
from nfl.production.nonqb import readiness as RD                     # noqa: E402
from nfl.tools import ingest_delivered_injuries as CLI               # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


# ----------------------------------------------------------------- fixtures
RAW_DOC = (b'<html><body><h1>Week 1 injury report</h1>'
           b'<li>OUT: RB Aaron Testman (knee)</li>'
           b'<li>QUESTIONABLE: WR Brett Casey (hamstring)</li>'
           b'</body></html>')
RAW_SHA = hashlib.sha256(RAW_DOC).hexdigest()

CLOCKS = {
    'retrieval_start': '2026-09-13T12:46:53.674810+00:00',
    'retrieved_at': '2026-09-13T12:47:00.990929+00:00',
    'publication_time': '2026-09-11T21:02:00Z',
    'source_modified_time': '2026-09-12T23:07:53.998Z',
    'effective_time': None,
}

ROSTER = {
    '00-0000001': {'name': 'Aaron Testman', 'team': 'AAA', 'position': 'RB'},
    '00-0000002': {'name': 'Brett Casey', 'team': 'AAA', 'position': 'WR'},
    '00-0000003': {'name': 'Carl Dunn Jr.', 'team': 'BBB', 'position': 'TE'},
    '00-0000004': {'name': 'Dale Evans', 'team': 'CCC', 'position': 'QB'},
}


def _cand(**kw):
    r = {'source_id': 'REPORT', 'source_url': 'https://example.invalid/report',
         'content_sha256': RAW_SHA, 'evidence_class': 'OFFICIAL_SOURCE_OBSERVATION',
         'conclusion_class': 'PROVEN', 'game_day_inactive': None,
         'team': 'AAA', 'game_date': '2026-09-13', 'player': 'Aaron Testman',
         'position': 'RB', 'injury': 'knee',
         'identity_resolution': 'EXACT_NAME_TEAM',
         'practice_participation': None, 'report_status': 'Out',
         'report_status_raw': 'OUT', 'status_semantics': 'EXPLICIT_DESIGNATION',
         'report_period': 'week 1', 'report_period_class': 'EXPLICIT',
         'evidence_text': 'OUT: RB Aaron Testman (knee)', 'locator': '/li[1]'}
    r.update(CLOCKS)
    r.update(kw)
    return r


def _stmt(team='CCC', **kw):
    r = {'source_id': 'REPORT', 'source_url': 'https://example.invalid/report',
         'content_sha256': RAW_SHA, 'team': team, 'game_date': '2026-09-13',
         'evidence_class': 'OFFICIAL_SOURCE_OBSERVATION',
         'conclusion_class': 'PROVEN', 'game_day_inactive': None,
         'status_semantics': DI.EXPLICIT_NO_DESIGNATIONS,
         'evidence_text': 'No injury designations', 'locator': '/p[2]',
         'report_period': 'week 1', 'report_status': None}
    r.update(CLOCKS)
    r.update(kw)
    return r


def _package(tmp, candidates=None, statements=None, observations=None,
             corrupt=False):
    """A minimal but structurally real delivered package."""
    root = pathlib.Path(tmp) / 'pkg'
    (root / 'raw').mkdir(parents=True, exist_ok=True)
    (root / 'raw' / 'REPORT.html').write_bytes(
        RAW_DOC + (b'<!--tampered-->' if corrupt else b''))
    manifest = [{
        'source_id': 'REPORT', 'authority': 'NFL',
        'requested_url': 'https://example.invalid/report',
        'final_url': 'https://example.invalid/report', 'http_status': 200,
        'byte_size': len(RAW_DOC), 'sha256': RAW_SHA,
        'raw_path': 'raw/REPORT.html',
        'retrieval_start': CLOCKS['retrieval_start'],
        'retrieval_end': CLOCKS['retrieved_at'],
        'publication_time': CLOCKS['publication_time'],
        'source_modified_time': CLOCKS['source_modified_time'],
    }]
    (root / 'manifest.json').write_text(json.dumps(manifest))
    cands = candidates if candidates is not None else [_cand()]
    stmts = statements if statements is not None else []
    obs = observations if observations is not None else list(cands)
    for name, rows in (('status_candidates.jsonl', cands),
                       ('status_observations.jsonl', obs),
                       ('team_status_statements.jsonl', stmts)):
        (root / name).write_text(
            ''.join(json.dumps(r) + '\n' for r in rows))
    (root / 'reconciliation.json').write_text(json.dumps(
        {'new_status_discrepancies': [], 'retained_practice_discrepancies': []}))
    ck = {}
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name != 'checksums.json':
            ck[str(p.relative_to(root))] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    (root / 'checksums.json').write_text(json.dumps(ck))
    return root


def _run_cli(tmp, root, extra=()):
    vroot = pathlib.Path(tmp) / 'vintage'
    man = pathlib.Path(tmp) / 'manifest.jsonl'
    man.touch()
    out = pathlib.Path(tmp) / 'ingest.json'
    rc = CLI.main(['--package', str(root), '--season', '2026', '--week', '1',
                   '--delivered-by', 'test', '--roster-csv', str(_roster_csv(tmp)),
                   '--vintage-root', str(vroot), '--manifest', str(man),
                   '--out', str(out), *extra])
    rows = [json.loads(x) for x in man.read_text().splitlines() if x.strip()]
    return rc, json.loads(out.read_text()), rows, vroot, man


def _roster_csv(tmp):
    p = pathlib.Path(tmp) / 'roster.csv'
    if not p.exists():
        with open(p, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['season', 'week', 'team',
                                              'gsis_id', 'full_name',
                                              'position', 'status'])
            w.writeheader()
            for pid, r in ROSTER.items():
                w.writerow({'season': '2026', 'week': '1', 'team': r['team'],
                            'gsis_id': pid, 'full_name': r['name'],
                            'position': r['position'], 'status': 'ACT'})
    return p


# --------------------------------------------------------------- the tests
def test_a_delivered_raw_bytes_preserve_their_hashes():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp)
        v = DI.verify_package(root)
        check('a well-formed package verifies', v.state is State.PASS, v.code)
        check('  every raw file was hashed',
              v.evidence['n_raw_verified'] == 1)
        check('  every checksummed file was hashed',
              v.evidence['n_checksums_verified'] == len(
                  json.loads((root / 'checksums.json').read_text())))
        rc, rec, rows, vroot, _ = _run_cli(tmp, root)
        check('the ingest completes', rc == 0, str(rc))
        blobs = sorted(vroot.glob('delivered_injury_evidence.*.html.gz'))
        check('the raw document is stored content-addressed', len(blobs) == 1,
              str([b.name for b in blobs]))
        back = gzip.open(blobs[0], 'rb').read()
        check('  and reads back byte-identical to the delivery',
              hashlib.sha256(back).hexdigest() == RAW_SHA)
        check('  with the digest in its own filename',
              RAW_SHA[:16] in blobs[0].name, blobs[0].name)
        step2 = next(s for s in rec['steps'] if s['step'].startswith('2.'))
        check('  and the recorded digest is the delivered digest',
              step2['blobs'][0]['sha256'] == RAW_SHA)


def test_b_retrieval_clocks_survive_unchanged():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp)
        rc, rec, rows, _, _ = _run_cli(tmp, root)
        check('the ingest completes', rc == 0)
        pv = rows[0]['value']['provenance']
        check('retrieved_at is the DELIVERED clock, not the ingestion clock',
              pv['retrieved_at'] == CLOCKS['retrieved_at'],
              f'{pv["retrieved_at"]} vs {CLOCKS["retrieved_at"]}')
        check('requested_at is the delivered retrieval_start',
              pv['requested_at'] == CLOCKS['retrieval_start'])
        check('publication_time is carried through verbatim',
              pv['publication_time'] == CLOCKS['publication_time'])
        check('source_timestamp is the delivered source_modified_time',
              pv['source_timestamp'] == CLOCKS['source_modified_time'])
        check('the ingestion clock appears ONLY as generated_at',
              pv['generated_at'] == rec['ingested_at'] and
              pv['generated_at'] != pv['retrieved_at'])
        check('the top-level retrieved_at the selector reads is the same one',
              rows[0]['value']['retrieved_at'] == CLOCKS['retrieved_at'])
        check('cache_timestamp is null and says why',
              pv['cache_timestamp'] is None and
              'never restamped' in pv['cache_timestamp_note'])


def test_c_the_same_bytes_twice_deduplicate_without_restamping():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp)
        rc1, rec1, rows1, vroot, man = _run_cli(tmp, root)
        blob = sorted(vroot.glob('delivered_injury_evidence.*.html.gz'))[0]
        mtime1, bytes1 = blob.stat().st_mtime_ns, blob.read_bytes()
        inj1 = sorted(vroot.glob('injuries.*.csv.gz'))
        rc2, rec2, rows2, _, _ = _run_cli(tmp, root)
        check('the second delivery also completes', rc1 == 0 and rc2 == 0)
        check('no second raw blob is created',
              len(sorted(vroot.glob('delivered_injury_evidence.*.html.gz'))) == 1)
        check('no second injuries blob is created',
              sorted(vroot.glob('injuries.*.csv.gz')) == inj1,
              str([p.name for p in inj1]))
        check('the stored bytes are untouched', blob.read_bytes() == bytes1)
        check('  and the file was not rewritten',
              blob.stat().st_mtime_ns == mtime1)
        check('the redelivery is recorded as a MEASUREMENT: a second '
              'manifest row', len(rows2) == 2, str(len(rows2)))
        check('  whose delivered clocks are identical to the first',
              rows2[0]['value']['provenance']['retrieved_at'] ==
              rows2[1]['value']['provenance']['retrieved_at'])
        check('  and whose content digest is identical',
              rows2[0]['value']['sha256'] == rows2[1]['value']['sha256'])
        step = next(s for s in rec2['steps'] if s['step'].startswith('7b.'))
        check('  and the run says so rather than claiming a fresh write',
              step['deduplicated'] is True)


def test_d_the_clocks_remain_distinct_fields():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp)
        rc, rec, rows, _, _ = _run_cli(tmp, root)
        pv = rows[0]['value']['provenance']
        vals = [pv['retrieved_at'], pv['publication_time'],
                pv['source_timestamp'], pv['generated_at']]
        check('the four populated clocks are four different values',
              len(set(vals)) == 4, str(vals))
        check('effective_for_date is a DATE, not a timestamp',
              pv['effective_for_date'] == '2026-09-13')
        check('effective_time stays null when the source gave none',
              pv['effective_time'] is None)
        check('the run reports the clocks it used',
              set(rec['clocks']) >= {'requested_at', 'retrieved_at',
                                     'publication_time', 'source_timestamp',
                                     'effective_for_date', 'generated_at',
                                     'cache_timestamp'})


def test_e_no_designation_evidence_is_explicit_never_inferred():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp, statements=[_stmt(team='CCC')])
        rc, rec, rows, vroot, _ = _run_cli(tmp, root)
        check('the ingest completes', rc == 0)
        nd = rows[0]['value']['explicit_no_designations']
        check('the statement is recorded as its own record kind',
              len(nd) == 1 and nd[0]['kind'] == DI.EXPLICIT_NO_DESIGNATIONS)
        check('  carrying the source hash it came from',
              nd[0]['content_sha256'] == RAW_SHA)
        check('  and the clock it was observed at',
              nd[0]['retrieved_at'] == CLOCKS['retrieved_at'])
        check('  and its verbatim text',
              nd[0]['evidence_text'] == 'No injury designations')
        blob = sorted(vroot.glob('injuries.*.csv.gz'))[0]
        got = list(csv.DictReader(gzip.open(blob, 'rt')))
        check('NO injury row is manufactured for the stated club',
              not any(r['team'] == 'CCC' for r in got),
              str(sorted({r['team'] for r in got})))
        check('the record says plainly that it clears no gate',
              nd[0]['clears_a_readiness_gate'] is False and nd[0]['why_not'])
        # the inverse, and the one that matters: a club that simply sent
        # nothing must not acquire a no-designation record by omission.
        check('a club with no rows and no statement gets NO record',
              not any(r['team'] == 'BBB' for r in nd))


def test_f_missing_status_remains_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp, candidates=[_cand(), _cand(
            player='Brett Casey', position='WR', report_status=None,
            report_status_raw=None)])
        rc, rec, rows, vroot, _ = _run_cli(tmp, root)
        check('a row with no designation is refused, not defaulted', rc == 0)
        blob = sorted(vroot.glob('injuries.*.csv.gz'))[0]
        got = list(csv.DictReader(gzip.open(blob, 'rt')))
        check('  so it is absent from the written rows', len(got) == 1,
              str(len(got)))
        refs = rec['row_build']['evidence']['refusals']
        check('  and the refusal is named',
              any(r['code'] == 'STATUS_NOT_IN_GOVERNED_VOCABULARY'
                  for r in refs), json.dumps(refs)[:200])
        check('practice_status is left empty, never backfilled from the '
              'designation', got[0]['practice_status'] == '')
        check('  and so is practice_primary_injury',
              got[0]['practice_primary_injury'] == '')


def test_g_temporally_unaligned_evidence_stays_quarantined():
    with tempfile.TemporaryDirectory() as tmp:
        keep = _cand()
        held = _cand(player='Brett Casey', position='WR',
                     report_status='Questionable',
                     report_status_raw='QUESTIONABLE')
        root = _package(tmp, candidates=[keep], observations=[keep, held])
        (root / 'reconciliation.json').write_text(json.dumps({
            'new_status_discrepancies': [{
                'team': 'AAA', 'player': 'Brett Casey',
                'article_status': 'Questionable', 'table_status': 'Out',
                'classification': 'OFFICIAL_DISCREPANCY_TEMPORAL_UNALIGNED',
                'reason': 'revision period not established'}],
            'retained_practice_discrepancies': []}))
        ck = json.loads((root / 'checksums.json').read_text())
        ck['reconciliation.json'] = hashlib.sha256(
            (root / 'reconciliation.json').read_bytes()).hexdigest()
        (root / 'checksums.json').write_text(json.dumps(ck))
        rc, rec, rows, vroot, _ = _run_cli(tmp, root)
        check('the ingest completes', rc == 0)
        q = rows[0]['value']['quarantined_evidence']
        check('the unaligned observation is quarantined', len(q) == 1,
              str(len(q)))
        check('  with the delivery\'s own classification',
              q[0]['classification'] ==
              'OFFICIAL_DISCREPANCY_TEMPORAL_UNALIGNED')
        check('  and its reason preserved',
              'revision period not established' in q[0]['reason'])
        check('  and no winner chosen here',
              q[0]['resolved_by_this_module'] is False)
        blob = sorted(vroot.glob('injuries.*.csv.gz'))[0]
        got = list(csv.DictReader(gzip.open(blob, 'rt')))
        check('  and neither side of it becomes a row',
              not any(r['full_name'] == 'Brett Casey' for r in got))


def test_h_questionble_cannot_silently_become_questionable():
    with tempfile.TemporaryDirectory() as tmp:
        typo = _cand(player='Brett Casey', position='WR',
                     report_status='QUESTIONBLE',
                     report_status_raw='QUESTIONBLE',
                     status_semantics='SOURCE_TYPO_REQUIRES_GOVERNED_NORMALIZATION')
        root = _package(tmp, candidates=[_cand(), typo])
        rc, rec, rows, vroot, _ = _run_cli(tmp, root)
        blob = sorted(vroot.glob('injuries.*.csv.gz'))[0]
        got = list(csv.DictReader(gzip.open(blob, 'rt')))
        check('the typo produces NO row', len(got) == 1, str(len(got)))
        check('  and no row anywhere reads Questionable for that player',
              not any(r['full_name'] == 'Brett Casey' and
                      r['report_status'] == 'Questionable' for r in got))
        refs = rec['row_build']['evidence']['refusals']
        check('  and the refusal names the semantics, not a spelling fix',
              any(r['code'] == 'STATUS_SEMANTICS_NOT_EXPLICIT' for r in refs),
              json.dumps(refs)[:200])
        # executable, not textual: the vocabulary is exact membership.
        check('the governed vocabulary does not contain the typo',
              'QUESTIONBLE' not in DI.REPORT_STATUS_VOCAB)
        check('  and membership is exact, not prefix or case-folded',
              all(DI.rows_from_candidates(
                  [_cand(report_status=s)], ROSTER, 2026, 1).state
                  is not State.PASS
                  for s in ('out', 'OUT', 'Questionable ', 'Quest')))


def test_i_game_status_cannot_become_inactive_status():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp, candidates=[
            _cand(), _cand(player='Brett Casey', position='WR',
                           game_day_inactive=True)])
        rc, rec, rows, vroot, _ = _run_cli(tmp, root)
        refs = rec['row_build']['evidence']['refusals']
        check('a row carrying a game-day inactive flag is refused',
              any(r['code'] == 'GAME_STATUS_IS_NOT_INACTIVE_STATUS'
                  for r in refs), json.dumps(refs)[:200])
        blob = sorted(vroot.glob('injuries.*.csv.gz'))[0]
        got = list(csv.DictReader(gzip.open(blob, 'rt')))
        check('  and does not become a row', len(got) == 1)
        check('the written schema has no inactive column at all',
              not any('inactive' in c for c in DI.INJURY_COLUMNS),
              str(DI.INJURY_COLUMNS))
        check('this path writes only the injuries source',
              rows[0]['source'] == 'injuries' and
              all(r['source'] != 'official_inactives' for r in rows))


def test_j_native_capture_behaviour_is_unchanged():
    live = [json.loads(x) for x in
            (pathlib.Path(_ROOT) / 'nfl' / 'vintage_manifest.jsonl'
             ).read_text().splitlines() if x.strip()]
    inj = [r for r in live if r.get('source') == 'injuries'
           and r.get('state') == 'PASS']
    native = [r for r in inj
              if (r.get('value') or {}).get('acquisition') != DI.ACQUISITION]
    check('native injuries captures are still on the manifest', bool(native),
          str(len(native)))
    check('  and none of them was relabelled as a delivery',
          all((r.get('value') or {}).get('acquisition') is None or
              (r['value']['acquisition'] == DI.NATIVE_ACQUISITION)
              for r in native))
    check('  and none of them acquired a delivery block',
          all('delivery' not in (r.get('value') or {}) for r in native))
    delivered = [r for r in inj
                 if (r.get('value') or {}).get('acquisition') == DI.ACQUISITION]
    for r in delivered:
        check(f'the delivered capture {r["capture_id"]} says it is a delivery',
              r['value']['delivery']['kind'] == DI.ACQUISITION)
        check('  and says explicitly what it is NOT',
              r['value']['delivery']['not'] == DI.NATIVE_ACQUISITION)
        check('  and names who delivered it',
              bool(r['value']['delivery']['delivered_by']))
    check('the two acquisition labels are different strings',
          DI.ACQUISITION != DI.NATIVE_ACQUISITION)


def test_k_a_corrupted_delivery_refuses():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp, corrupt=True)
        v = DI.verify_package(root)
        check('a package whose bytes do not match its manifest FAILS',
              v.state is State.FAIL, f'{v.state.value}:{v.code}')
        check('  with a named code',
              v.code == 'DELIVERED_PACKAGE_HASH_MISMATCH')
        check('  naming the offending file',
              any('REPORT' in x for x in v.evidence['mismatched']),
              str(v.evidence['mismatched']))
        vroot = pathlib.Path(tmp) / 'vintage'
        man = pathlib.Path(tmp) / 'manifest.jsonl'
        man.touch()
        rc = CLI.main(['--package', str(root), '--season', '2026',
                       '--week', '1', '--delivered-by', 'test',
                       '--roster-csv', str(_roster_csv(tmp)),
                       '--vintage-root', str(vroot), '--manifest', str(man)])
        check('the CLI exits non-zero', rc != 0, str(rc))
        check('  and nothing was written to the vintage root',
              not vroot.exists() or not list(vroot.iterdir()))
        check('  and no manifest row was appended',
              man.read_text().strip() == '')
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp)
        (root / 'checksums.json').unlink()
        v = DI.verify_package(root)
        check('a package that cannot state its own identity is BLOCKED',
              v.state is State.BLOCKED, f'{v.state.value}:{v.code}')


def test_l_downstream_consumes_only_contract_satisfying_rows():
    with tempfile.TemporaryDirectory() as tmp:
        root = _package(tmp, candidates=[
            _cand(), _cand(player='Carl Dunn', team='BBB', position='TE',
                           report_status='Doubtful', report_status_raw='DOUBTFUL',
                           injury='ankle')])
        rc, rec, rows, vroot, _ = _run_cli(tmp, root)
        check('the ingest completes', rc == 0)
        blob = sorted(vroot.glob('injuries.*.csv.gz'))[0]
        got = list(csv.DictReader(gzip.open(blob, 'rt')))
        check('the written header is the nflverse injuries schema, unchanged',
              tuple(got[0].keys()) == DI.INJURY_COLUMNS,
              str(tuple(got[0].keys())))
        parsed = AM.parse_injuries_rows(got, 2026)
        check('EVERY written row survives the production parser',
              len(parsed) == len(got), f'{len(parsed)} of {len(got)}')
        check('  keyed by (season, week, team, gsis_id) as production expects',
              all(len(k) == 4 and k[0] == 2026 and k[1] == 1
                  for k in parsed))
        check('  with the designation the evidence carried',
              {v['report_status'] for v in parsed.values()} ==
              {'Out', 'Doubtful'}, str(sorted(
                  v['report_status'] for v in parsed.values())))
        check('a generational suffix in the roster resolves to the one player',
              any(v['report_status'] == 'Doubtful' for v in parsed.values()))
        # and the guard that makes the above non-vacuous: a row the parser
        # would silently skip must never have been written in the first place.
        bad = DI.rows_from_candidates(
            [_cand(player='Nobody At All')], ROSTER, 2026, 1)
        check('an unresolvable name BLOCKS the whole set rather than being '
              'written without a gsis_id', bad.state is State.BLOCKED,
              f'{bad.state.value}:{bad.code}')
        check('  naming the unmapped player',
              any('Nobody At All' in x for x in bad.evidence['unmapped']),
              str(bad.evidence['unmapped']))
        check('the readiness gate still requires a filed designation',
              RD.NEEDS_REPORT_STATUS is True)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
