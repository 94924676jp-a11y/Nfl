#!/usr/bin/env python3.12
"""Full-field archive: ingest is immutable, reconcile refuses by name, grade only scores sealed prelock shadows.

    python3.12 nfl/tests/test_showdown_field_archive.py
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import zipfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.field import showdown_field_archive as A  # noqa: E402
from nfl.field import showdown_history_calibration as HC  # noqa: E402

PASSED = FAILED = 0


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def _refused(fn, code, msg):
    try:
        fn()
        check(False, f'{msg}: not refused')
    except A.ArchiveError as e:
        check(str(e).startswith(code), f'{msg} ({str(e)[:80]})')


P = ['Q1', 'W1', 'W2', 'R1', 'T1', 'K1', 'Q2', 'W3']


def _standings(entries, drafted):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HC.EXPECTED_HEADER)
    rows = [[i + 1, f'E{i}', f'user{i % 3} (1/1)', '', pts, 'CPT ' + c + ' ' + ' '.join('FLEX ' + x for x in f)]
            for i, (c, f, pts) in enumerate(entries)]
    for i, r in enumerate(rows):
        d = drafted[i] if i < len(drafted) else ['', '', '', '']
        w.writerow(r + [''] + d)
    for d in drafted[len(rows):]:
        w.writerow(['', '', '', '', '', '', ''] + d)
    return buf.getvalue().encode()


def _fixture(td, drafted_cpt_q1=None):
    ent = [('Q1', ('W1', 'W2', 'R1', 'T1', 'K1'), 100.0), ('Q1', ('W1', 'W2', 'R1', 'T1', 'K1'), 100.0),
           ('Q2', ('W1', 'W3', 'R1', 'T1', 'K1'), 90.0), ('W1', ('Q1', 'W2', 'R1', 'T1', 'K1'), 90.0)]
    n = len(ent)
    cpt, flx = {}, {}
    for c, f, _ in ent:
        cpt[c] = cpt.get(c, 0) + 1
        for x in f:
            flx[x] = flx.get(x, 0) + 1
    drafted = [[p, 'CPT', f'{100 * v / n:.2f}%', '1'] for p, v in cpt.items()] + \
              [[p, 'FLEX', f'{100 * v / n:.2f}%', '1'] for p, v in flx.items()]
    if drafted_cpt_q1 is not None:
        drafted[0][2] = f'{drafted_cpt_q1:.2f}%'
    raw = _standings(ent, drafted)
    z = pathlib.Path(td) / 'standings.zip'
    with zipfile.ZipFile(z, 'w') as zz:
        zz.writestr('contest-standings-1.csv', raw)
    return z, raw


def test_ingest():
    with tempfile.TemporaryDirectory() as td:
        z, raw = _fixture(td)
        d, rec = A.ingest(z, '1', 'X_Y', 'fixture contest', 'unit test', root=pathlib.Path(td) / 'arch')
        check(rec['sha256'] == hashlib.sha256(raw).hexdigest() and (d / 'PROVENANCE.jsonl').exists(),
              'ingest stores the CSV content-addressed with provenance')
        _refused(lambda: A.ingest(z, '1', 'X_Y', 'x', 'y', root=pathlib.Path(td) / 'arch'), 'ARCHIVE_EXISTS',
                 'an existing archive is never overwritten')
        two = pathlib.Path(td) / 'two.zip'
        with zipfile.ZipFile(two, 'w') as zz:
            zz.writestr('a.csv', raw)
            zz.writestr('b.csv', raw)
        _refused(lambda: A.ingest(two, '2', 'X_Y', 'x', 'y', root=pathlib.Path(td) / 'arch'), 'ZIP_NEEDS_EXACTLY_ONE_CSV',
                 'a zip with two CSVs is refused')
        bad = pathlib.Path(td) / 'bad.csv'
        bad.write_text('a,b,c\n1,2,3\n')
        _refused(lambda: A.ingest(bad, '3', 'X_Y', 'x', 'y', root=pathlib.Path(td) / 'arch'), 'SCHEMA',
                 'a file that is not DK standings is refused')


def test_reconcile():
    with tempfile.TemporaryDirectory() as td:
        z, _ = _fixture(td)
        A.ingest(z, '1', 'X_Y', 'fixture', 'unit test', root=pathlib.Path(td) / 'arch')
        r = A.reconcile('1', 'X_Y', root=pathlib.Path(td) / 'arch')
        check(r['VERDICT'] == 'RECONCILED', f"fixture reconciles ({r['problems']})")
        check(r['counts']['distinct_lineups'] == 3 and r['counts']['copy_count_distribution_ALL_copies'] == {'1': 2, '2': 1},
              'copies are ALL entries holding a canonical lineup')
        check(r['counts']['score_ties_among_distinct_lineups'] == 1, 'two distinct lineups on 90.0 are a TIE, not a duplicate')
        z2, _ = _fixture(td, drafted_cpt_q1=10.0)
        A.ingest(z2, '9', 'X_Y', 'fixture', 'unit test', root=pathlib.Path(td) / 'arch2')
        r = A.reconcile('9', 'X_Y', root=pathlib.Path(td) / 'arch2')
        check(r['VERDICT'] == 'NOT_RECONCILED' and any(p.startswith('DRAFTED_RECOUNT_GAP') for p in r['problems']),
              'a %Drafted that disagrees with the lineups beyond 0.5 pp is NOT_RECONCILED')
    r = A.reconcile('196285160', 'ATL_NO')
    check(r['VERDICT'] == 'RECONCILED' and r['counts']['entries_filled'] == 47308,
          f"the real ATL@NO 20-max archive reconciles ({r['counts']['entries_filled']} entries)")


def _seal(doc):
    body = {k: v for k, v in doc.items() if k != 'seal_sha256'}
    doc['seal_sha256'] = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    return doc


def test_grade():
    with tempfile.TemporaryDirectory() as td:
        z, _ = _fixture(td)
        root = pathlib.Path(td) / 'arch'
        A.ingest(z, '1', 'X_Y', 'fixture', 'unit test', root=root)
        ko = dt.datetime(2026, 10, 9, 0, 15, tzinfo=dt.timezone.utc)
        doc = _seal({'ARTIFACT': 'SHOWDOWN_DUPE_SHADOW_COMPARISON', 'MODE': 'PRELOCK', 'kickoff': ko.isoformat(),
                     'written_at': (ko - dt.timedelta(hours=1)).isoformat(),
                     'lineups': [{'contest_id': '1', 'entry_id': 'E0', 'captain': 'Q1',
                                  'flex': ['W1', 'W2', 'R1', 'T1', 'K1'],
                                  'models': {'B4': {'copies': 1.5, 'state': 'PRICED'}},
                                  'legacy': {'E1_independent_copies': 0.5}}]})
        p = pathlib.Path(td) / 's.json'
        p.write_text(json.dumps(doc))
        g = A.grade('1', 'X_Y', p, root=root)
        s = g['summary']['B4']
        check(s['actual_all_copies'] == 2 and s['actual_other_copies'] == 1 and s['own_entries'] == 1,
              'all copies 2, ours 1, other copies 1')
        check(abs(s['other_over_pred'] - 1 / 1.5) < 1e-4, f"other/pred = 1/1.5 ({s['other_over_pred']})")
        late = _seal(dict(doc, written_at=(ko + dt.timedelta(minutes=1)).isoformat()))
        p.write_text(json.dumps(late))
        _refused(lambda: A.grade('1', 'X_Y', p, root=root), 'SEAL_WRITTEN_AT_OR_AFTER_KICKOFF',
                 'a shadow sealed after kickoff is not graded')
        tam = dict(doc)
        tam['lineups'] = [dict(doc['lineups'][0], models={'B4': {'copies': 2.0, 'state': 'PRICED'}})]
        p.write_text(json.dumps(tam))
        _refused(lambda: A.grade('1', 'X_Y', p, root=root), 'SEAL_DOES_NOT_VERIFY', 'a tampered shadow is not graded')
        dry = _seal(dict(doc, MODE='DRY_RUN_NOT_PRELOCK'))
        p.write_text(json.dumps(dry))
        _refused(lambda: A.grade('1', 'X_Y', p, root=root), 'NOT_A_PRELOCK_RECORD', 'a dry run is never graded as evidence')


if __name__ == '__main__':
    for t in (test_ingest, test_reconcile, test_grade):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
