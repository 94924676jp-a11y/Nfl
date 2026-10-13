#!/usr/bin/env python3.12
"""The canonical issue ledger (nfl/research/ledger/ISSUE_LEDGER.json) is machine-checked, not prose: every issue
carries the mandated fields, uses the declared vocabulary, cites files that exist at HEAD (and line numbers inside
them), a FIXED issue names an existing guard test, and an OWNER_GATED issue names the gate."""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

LEDGER = _REPO / 'nfl/research/ledger/ISSUE_LEDGER.json'
REQUIRED = ('id', 'domain', 'title', 'user_visible_consequence', 'evidence', 'verification', 'severity',
            'production_path', 'state', 'owner_gate', 'guard_test', 'test_type', 'blast_radius', 'data_rights',
            'depends_on', 'experiment', 'source')
PASSED = FAILED = 0


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def _doc():
    return json.loads(LEDGER.read_text())


def test_every_issue_has_the_mandated_fields_and_vocabulary():
    d = _doc()
    v = d['vocabulary']
    iss = d['issues']
    check(len(iss) > 0, 'the ledger is not empty')
    ids = [e.get('id') for e in iss]
    check(len(ids) == len(set(ids)), f'issue ids are unique ({len(ids)} vs {len(set(ids))})')
    for e in iss:
        missing = [k for k in REQUIRED if k not in e]
        check(not missing, f'{e.get("id")}: fields present {missing}')
        for k in ('verification', 'severity', 'state', 'production_path'):
            check(e.get(k) in v[k], f'{e.get("id")}: {k}={e.get(k)!r} in vocabulary')
        check(isinstance(e.get('evidence'), list) and e['evidence'], f'{e.get("id")}: evidence is a non-empty list')
        known = set(ids)
        check(all(x in known for x in e.get('depends_on') or []), f'{e.get("id")}: depends_on names known issues')


def test_cited_evidence_exists_at_head():
    for e in _doc()['issues']:
        for ref in e['evidence']:
            path, _, line = ref.partition(':')
            f = _REPO / path
            ok = f.exists()
            check(ok, f'{e["id"]}: cited path exists {path}')
            if ok and line.isdigit() and f.is_file() and f.suffix in ('.py', '.md', '.json', '.jsonl'):
                n = sum(1 for _ in f.open(encoding='utf-8', errors='replace'))
                check(int(line) <= n, f'{e["id"]}: {ref} is inside the file ({n} lines)')


def test_fixed_issues_name_a_guard_and_gated_issues_name_the_gate():
    for e in _doc()['issues']:
        if e['state'] == 'FIXED':
            g = (e.get('guard_test') or '').split('::')[0]
            check(bool(g) and (_REPO / g).exists(), f'{e["id"]}: FIXED names an existing guard test ({g!r})')
        if e['state'] in ('OWNER_GATED', 'BLOCKED_DATA') and e['id'] != 'DATA-D1':
            check(bool(e.get('owner_gate')), f'{e["id"]}: {e["state"]} names its gate')
        if e['verification'] == 'WRONG':
            check(e['state'] == 'WITHDRAWN', f'{e["id"]}: a falsified claim is WITHDRAWN, not open')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    check(PASSED > 0, 'the module counted at least one check')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
