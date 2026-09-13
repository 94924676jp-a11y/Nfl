"""The seal must read the ingestion record THIS run wrote, and every book quote
must be accounted for.

TWO DEFECTS, ONE SHAPE. Both are the project's most expensive failure mode: a
step that returned nothing, or something from a previous run, read as success.

  * READ-BEFORE-WRITE. `ingest_inactives.py` seals boards in step 6, and
    `make_board._inactive_provenance` opens INACTIVES_INGESTION.json to learn
    what step 3 resolved. The record was written only at the very end, so the
    seal read the PREVIOUS run's record -- or, on a first ingestion, no file at
    all. Measured 2026-09-13: all four afternoon boards carried
    `n_unmapped: null` and failed `no_unresolved_identity` even for GB/MIN and
    WAS/PHI, whose ingestions resolved every official name. Nothing was wrong
    with the evidence; the board could not see it.

  * THE MASK. That went unnoticed longer than it should have because
    `official_inactive_evidence_ingested` read `bool(inact) or
    post_inactives_complete`. Passing an inactive id satisfied it. So a board
    asserted that official inactive evidence had been ingested while its own
    provenance block said `no INACTIVES_INGESTION.json for this game`. An
    argument is not evidence of its own provenance.

  * SILENT QUOTE LOSS. `market_comparison` walks BOARD PLAYERS and looks up
    their quotes, so a quote whose player the board does not carry was never
    visited: no row, no refusal, no count. 166 quotes in, 76 rows and 3
    refusals out, 87 simply gone.

These tests assert on RETURNED VALUES and EMITTED ARTIFACTS, never on source
text, because the prose in a module is not the behaviour of a module.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_Q3 = os.path.join(_ROOT, 'nfl', 'research', 'qb3')
if _Q3 not in sys.path:
    sys.path.insert(0, _Q3)

from nfl.tools import make_board as MB                               # noqa: E402
from nfl.tools import ingest_inactives as II                         # noqa: E402
from nfl.production.nonqb import qb_allocation as QA                 # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _record(inactive_ids, n_unmapped=0, detail=None):
    """An ingestion record of the shape _inactive_provenance reads."""
    return {'artifact': 'NFL_OFFICIAL_INACTIVES_INGESTION',
            'result': 'COMPLETE',
            'provenance': {'kind': 'EXTERNAL_AUTHORITATIVE_DELIVERY'},
            'steps': [
                {'step': '3. identity resolved', 'ok': True,
                 'n_unmapped': n_unmapped,
                 'unmapped': [f'ZZ:Name {i}' for i in range(n_unmapped)],
                 'unmapped_detail': detail if detail is not None else
                 [{'team': 'ZZ', 'name': f'Name {i}', 'source_position': None}
                  for i in range(n_unmapped)]},
                {'step': '4. POST_INACTIVES_COMPLETE', 'ok': True,
                 'inactive_by_team': {'ZZ': list(inactive_ids)}},
            ]}


def _prov_with(tmp, rec, inactive_ids, game='2026_01_ZZ_YY'):
    g = pathlib.Path(tmp) / 'nfl' / 'research' / 'live' / game
    g.mkdir(parents=True, exist_ok=True)
    if rec is not None:
        (g / 'INACTIVES_INGESTION.json').write_text(json.dumps(rec))
    old = MB._REPO
    try:
        MB._REPO = pathlib.Path(tmp)
        return MB._inactive_provenance(game, ('ZZ', 'YY'), inactive_ids)
    finally:
        MB._REPO = old


def test_a_no_record_at_all_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        p = _prov_with(tmp, None, ['P1'])
    check('a seal with no ingestion record gets provenance, not None',
          isinstance(p, dict))
    check('  which does not claim the list was ingested',
          p.get('post_inactives_complete') is False)
    check('  and cannot answer how many names went unresolved',
          p.get('n_unmapped') is None)
    own = QA.ownership_verdict(('ZZ',), {}, set(), {}, 0.0, p)
    check('  so the ownership verdict refuses', own['enforced'] is False)


def test_b_an_argument_is_not_evidence_of_its_own_provenance():
    """THE MASK. Passing inactive ids must not satisfy the evidence condition."""
    with tempfile.TemporaryDirectory() as tmp:
        p = _prov_with(tmp, None, ['P1'])
    own = QA.ownership_verdict(('ZZ',), {}, {'P1'}, {}, 0.0, p)
    check('passing an inactive id does NOT assert the evidence was ingested',
          own['conditions']['official_inactive_evidence_ingested'] is False,
          str(own['conditions']))
    check('  and the failure is named',
          'official_inactive_evidence_ingested' in own['failed_conditions'])


def test_c_a_record_of_a_different_set_is_not_this_provenance():
    """STALE-RECORD READ. The previous run's record must never pass as this one."""
    with tempfile.TemporaryDirectory() as tmp:
        p = _prov_with(tmp, _record(['P1', 'P2'], n_unmapped=0), ['P7', 'P8'])
    check('a record listing a different inactive set is refused',
          p.get('post_inactives_complete') is False)
    check('  by a NAMED reason, not a silent None',
          'INACTIVES_INGESTION_RECORD_DOES_NOT_DESCRIBE_THIS_SET'
          in str(p.get('why')), str(p.get('why')))
    check('  and it reports no unresolved count it cannot vouch for',
          p.get('n_unmapped') is None)


def test_d_the_matching_record_is_read_in_full():
    with tempfile.TemporaryDirectory() as tmp:
        p = _prov_with(tmp, _record(['P1', 'P2'], n_unmapped=0), ['P2', 'P1'])
    check('a record describing THIS set is accepted regardless of order',
          p.get('post_inactives_complete') is True, str(p.get('why')))
    check('  and carries the resolved count', p.get('n_unmapped') == 0)
    own = QA.ownership_verdict(('ZZ',), {}, {'P1'}, {}, 0.0, p)
    check('  so identity no longer blocks',
          own['conditions']['no_unresolved_identity'] is True)
    check('  and the evidence condition is satisfied by the RECORD',
          own['conditions']['official_inactive_evidence_ingested'] is True)


def test_e_an_unresolved_qb_still_refuses_through_a_valid_record():
    """The repair must not have loosened the condition it exposed."""
    det = [{'team': 'ZZ', 'name': 'Some Passer', 'source_position': 'QB'}]
    with tempfile.TemporaryDirectory() as tmp:
        p = _prov_with(tmp, _record(['P1'], n_unmapped=1, detail=det), ['P1'])
    own = QA.ownership_verdict(('ZZ',), {}, {'P1'}, {}, 0.0, p)
    check('an unresolved QB refuses even on a valid, matching record',
          own['conditions']['no_unresolved_identity'] is False)
    check('  and an unknown position refuses too',
          QA.unresolved_qb_room_risk(
              {'n_unmapped': 1,
               'unmapped_detail': [{'name': 'X', 'source_position': None}]}
          )['blocks_qb_enforcement'] is True)


def test_f_the_checkpoint_is_readable_and_says_it_is_unfinished():
    """The record put on disk BEFORE the seal must be usable and honest."""
    class A:
        pass
    with tempfile.TemporaryDirectory() as tmp:
        a = A()
        a.out = tmp
        rec = _record(['P1'], n_unmapped=0)
        rec.pop('result')
        p = II._checkpoint(rec, a)
        on_disk = json.loads(pathlib.Path(p).read_text())
    check('the checkpoint writes the record the seal will read',
          pathlib.Path(p).name == 'INACTIVES_INGESTION.json')
    check('  it is never mistaken for a finished ingestion',
          on_disk['result'] == 'IN_PROGRESS', on_disk.get('result'))
    check('  and steps 1-5 are already in it',
          any(s['step'].startswith('3.') for s in on_disk['steps']))
    check('  _finish still overwrites the verdict',
          II._finish(rec, a, 0) == 0 and json.loads(
              pathlib.Path(p).read_text())['result'] == 'COMPLETE')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
