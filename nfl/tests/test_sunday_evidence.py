"""sunday_evidence: Sunday news enters with its provenance, resolves exactly, and never upgrades itself."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV      # noqa: E402
from nfl.tools import sunday_evidence as SE   # noqa: E402
from nfl.tests._controls import observe       # noqa: E402

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


POOL = [{'dk_id': '1', 'dk_name': 'Zay Flowers', 'team': 'BAL', 'dk_pos': 'WR'},
        {'dk_id': '2', 'dk_name': 'Tyson Bagent', 'team': 'CHI', 'dk_pos': 'QB'},
        {'dk_id': '3', 'dk_name': 'Case Keenum', 'team': 'CHI', 'dk_pos': 'QB'},
        {'dk_id': '4', 'dk_name': 'James Cook III', 'team': 'BUF', 'dk_pos': 'RB'},
        {'dk_id': '5', 'dk_name': 'DJ Moore', 'team': 'BUF', 'dk_pos': 'WR'}]


def _write(pk):
    p = pathlib.Path(tempfile.mkdtemp()) / 'pk.json'
    p.write_text(json.dumps(pk))
    return p


def _pk(**k):
    base = {'packet_id': 't', 'source': 'OWNER_RELAYED', 'received_at': '2026-10-04T14:30:00Z',
            'players': [{'name': 'Zay Flowers', 'team': 'BAL', 'status': 'INACTIVE'},
                        {'name': 'James Cook', 'team': 'BUF', 'status': 'ACTIVE', 'cited': 'OFFICIAL_RELEASE'}],
            'starters': {'CHI': 'Tyson Bagent'}}
    base.update(k)
    return base


def test_01_provenance_is_never_upgraded():
    lo = SE.load(_write(_pk()))
    check('negative control: a well-formed owner packet loads', lo.state.value == 'PASS', lo.detail)
    r = SE.resolve(lo.value, POOL).value
    check('an owner-relayed INACTIVE with no citation is REPORTED_OUT_UNVERIFIED, never CONFIRMED_INACTIVE',
          r['players']['1']['status'] == AV.REPORTED_OUT_UNVERIFIED and r['players']['1']['tier'] == AV.TIER_EXTERNAL_SECONDHAND,
          r['players']['1'])
    check('  and it is still an absence for the role tree', r['players']['1']['status'] in AV.ABSENT_STATUSES)
    check('an owner-relayed ACTIVE citing the club release is REPORTED_ACTIVE_NOT_ON_LIST',
          r['players']['4']['status'] == AV.REPORTED_ACTIVE_NOT_ON_LIST)
    check('  name suffixes resolve ("James Cook" -> "James Cook III")', '4' in r['players'])
    lo = SE.load(_write(_pk(source='OFFICIAL_CAPTURED', complete_clubs=['BAL'])))
    r = SE.resolve(lo.value, POOL).value
    check('only an official capture produces CONFIRMED_INACTIVE', r['players']['1']['status'] == AV.CONFIRMED_INACTIVE)
    check('a starter resolves to the QB row', r['starters']['CHI']['dk_id'] == '2')
    check('every status respects the tier rule',
          all(v['tier'] in AV.STATUS_REQUIRES_TIER.get(v['status'], (v['tier'],)) for v in r['players'].values()))


def test_02_typos_and_contradictions_refuse():
    lo = SE.load(_write(_pk(players=[{'name': 'Zay Flowerz', 'team': 'BAL', 'status': 'INACTIVE'}])))
    o = SE.resolve(lo.value, POOL)
    observe('nfl.tools.sunday_evidence:resolve:EVIDENCE_PACKET_UNRESOLVED_PLAYER', o)
    check('positive control: a misspelt name is refused by name, never dropped',
          o.code == 'EVIDENCE_PACKET_UNRESOLVED_PLAYER' and o.evidence['unmatched'][0]['name'] == 'Zay Flowerz', o.detail)
    lo = SE.load(_write(_pk(players=[{'name': 'Tyson Bagent', 'team': 'CHI', 'status': 'INACTIVE'}])))
    o = SE.resolve(lo.value, POOL)
    check('positive control: a named starter who is also inactive is refused',
          o.code == 'EVIDENCE_PACKET_UNRESOLVED_PLAYER' and 'NAMED_STARTER_AND_INACTIVE' in o.detail, o.detail)
    lo = SE.load(_write(_pk(starters={'CHI': 'DJ Moore'})))
    o = SE.resolve(lo.value, POOL)
    check('positive control: a "starter" who is not a quarterback in the pool is refused', o.code == 'EVIDENCE_PACKET_UNRESOLVED_PLAYER')


def test_03_schema_and_empty():
    o = SE.load(_write(_pk(players=[{'name': 'Zay Flowers', 'team': 'BAL', 'status': 'PROBABLY'}])))
    observe('nfl.tools.sunday_evidence:load:EVIDENCE_PACKET_SCHEMA', o)
    check('positive control: a status outside ACTIVE/INACTIVE is refused', o.code == 'EVIDENCE_PACKET_SCHEMA', o.code)
    o = SE.load(_write(_pk(complete_clubs=['BAL'])))
    check('positive control: an owner packet cannot claim complete club lists', o.code == 'EVIDENCE_PACKET_SCHEMA', o.code)
    o = SE.load(_write(_pk(players=[], starters={})))
    observe('nfl.tools.sunday_evidence:load:EVIDENCE_PACKET_EMPTY_INPUT', o)
    check('positive control: an empty packet is BLOCKED, not "no news"', o.code == 'EVIDENCE_PACKET_EMPTY_INPUT', o.code)
    check('a rehearsal packet maps to a state that is never official',
          SE.STATE_FOR_SOURCE['REHEARSAL'] == 'REHEARSAL_NOT_EVIDENCE' and SE.STATE_FOR_SOURCE['OWNER_RELAYED'] != 'APPLIED')


def test_04_starter_citations_stay_distinct():
    lo = SE.load(_write(_pk(players=[], starters={'CHI': {'name': 'Tyson Bagent', 'cited': 'AGGREGATOR'}})))
    r = SE.resolve(lo.value, POOL).value['starters']['CHI']
    check('a media-reported starter is REPORTED_EXPECTED_STARTER at HIGH_CONFIDENCE_REPORTED_STARTER, never confirmed',
          (r['starter_state'], r['evidence_tier']) == ('REPORTED_EXPECTED_STARTER', 'HIGH_CONFIDENCE_REPORTED_STARTER')
          and r['captured_document'] is False, r)
    lo = SE.load(_write(_pk(players=[], starters={'CHI': {'name': 'Tyson Bagent', 'cited': 'OFFICIAL_RELEASE'}})))
    r = SE.resolve(lo.value, POOL).value['starters']['CHI']
    check('a team-published starter relayed by the owner is CONFIRMED_BY_TEAM_PUBLISHED_EVIDENCE, document not captured',
          r['starter_state'] == 'CONFIRMED_BY_TEAM_PUBLISHED_EVIDENCE' and r['relayed_by'] == 'OWNER_RELAYED'
          and r['captured_document'] is False, r)
    r = SE.resolve(SE.load(_write(_pk(players=[]))).value, POOL).value['starters']['CHI']
    check('negative control: an uncited bare name is REPORTED_STARTER_UNVERIFIED', r['starter_state'] == 'REPORTED_STARTER_UNVERIFIED', r)
    o = SE.load(_write(_pk(players=[], starters={'CHI': {'name': 'Tyson Bagent', 'cited': 'TWITTER'}})))
    check('positive control: an unknown starter citation is refused', o.code == 'EVIDENCE_PACKET_SCHEMA', o.code)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
