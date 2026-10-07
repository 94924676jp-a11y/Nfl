#!/usr/bin/env python3.12
"""The candidate status register (nfl/research/registry/CANDIDATE_STATUS_REGISTER.json) cannot quietly revive a failure.

    python3.12 nfl/tests/test_candidate_status_register.py

  every row: known status, ladder levels from the declared ladder in order, every cited evidence file exists
  a FAILED or DEVELOPMENT_EVIDENCE_ONLY candidate never has a later row promoting it under the same id
  PROMOTED appears only on a PRODUCTION_OWNER_APPROVED row that carries an owner ruling
  the latest row per candidate is what this test reports, so a supersession is visible
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
REG = _REPO / 'nfl/research/registry/CANDIDATE_STATUS_REGISTER.json'
PASSED = FAILED = 0


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def _load():
    return json.loads(REG.read_text())


def test_rows_are_well_formed():
    d = _load()
    check(len(d['rows']) > 0, f"{len(d['rows'])} rows")
    for r in d['rows']:
        lad = r.get('ladder_reached', [])
        check(r['status'] in d['STATUS_VOCABULARY'], f"{r['candidate']}: status {r['status']} is in the vocabulary")
        check(all(x in d['LADDER'] for x in lad) and lad == sorted(lad, key=d['LADDER'].index),
              f"{r['candidate']}: ladder levels are declared levels, in order")
        miss = [e for e in r['evidence'] if not (_REPO / e).exists()]
        check(not miss, f"{r['candidate']}: every cited evidence file exists {miss}")


def test_no_revival_and_promotion_needs_owner():
    d = _load()
    dead = set()
    for r in d['rows']:
        c = r['candidate']
        if c in dead:
            check(r['status'] not in ('PRODUCTION_OWNER_APPROVED', 'SHADOW', 'SHADOW_ON_PATH_NOT_CONSUMED'),
                  f'{c}: a failed candidate is not revived under the same id')
        if r['status'] in ('FAILED_PREREGISTERED_BAR', 'DEVELOPMENT_EVIDENCE_ONLY'):
            dead.add(c)
            check('PROMOTED' not in r.get('ladder_reached', []), f'{c}: a failed row carries no PROMOTED level')
        if 'PROMOTED' in r.get('ladder_reached', []):
            check(r['status'] == 'PRODUCTION_OWNER_APPROVED' and r.get('owner_ruling'),
                  f'{c}: PROMOTED only with an owner-approved production row')
    latest = {}
    for r in d['rows']:
        latest[r['candidate']] = r['status']
    promoted = [c for c, s in latest.items() if s == 'PRODUCTION_OWNER_APPROVED']
    check(promoted == ['Automatic specialist detector (showdown_slate_state.specialist_class)'],
          f'the only owner-approved production change is the specialist detector ({promoted})')
    check(latest.get('SC-OWN-ROTATION-1') == 'FAILED_PREREGISTERED_BAR', 'SC-OWN-ROTATION-1 is registered FAILED')


if __name__ == '__main__':
    for t in (test_rows_are_well_formed, test_no_revival_and_promotion_needs_owner):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
