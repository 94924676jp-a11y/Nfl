"""Sunday evidence packets: inactives, cleared Questionables and starting quarterbacks, with provenance.

A packet is a JSON file:

    {
      "packet_id": "2026W4-owner-1030",
      "source": "OWNER_RELAYED" | "OFFICIAL_CAPTURED" | "REHEARSAL",
      "received_at": "2026-10-04T14:30:00Z",
      "source_detail": "what the owner or the capture said it came from",
      "complete_clubs": ["CHI", ...],          # OFFICIAL_CAPTURED only: clubs whose FULL list is held
      "players": [
        {"name": "Zay Flowers", "team": "BAL", "status": "ACTIVE" | "INACTIVE",
         "cited": "OFFICIAL_RELEASE" | "AGGREGATOR" | "SECONDHAND", "note": "..."}
      ],
      "starters": {"CHI": "Tyson Bagent",                                    # bare name = SECONDHAND
                   "TB": {"name": "Jalon Daniels", "cited": "OFFICIAL_RELEASE", "note": "...",
                          "received_at": "..."}}
    }

A STARTER carries its own citation, mapped to the owner's starter vocabulary (STARTER_STATE_FOR):
OFFICIAL_RELEASE -> CONFIRMED_BY_TEAM_PUBLISHED_EVIDENCE (tier OFFICIAL_TEAM_PUBLISHED), AGGREGATOR ->
REPORTED_EXPECTED_STARTER (tier HIGH_CONFIDENCE_REPORTED_STARTER), none/SECONDHAND ->
REPORTED_STARTER_UNVERIFIED. Every tier drives the depth chart the same way (he starts); the label is
what keeps "the team published it" apart from "reporters expect it". Items and starters may carry their
own received_at; a packet is cumulative for the day, later evidence replacing earlier in place.

PROVENANCE IS NEVER UPGRADED. An owner-relayed item is evidence at the tier the owner cites (or
EXTERNAL_RESEARCH_SECONDHAND when none is cited); it is never CONFIRMED_INACTIVE, which needs a captured
official document. A REHEARSAL packet runs the whole chain and is labelled so everywhere; nothing built
from it may be promoted to a FINAL artifact.

IDENTITY FAILS CLOSED. Every packet player must resolve to exactly one DraftKings pool row by name and
club; a typo is a refusal naming the row, never a silently dropped item.

ABSENCE IS NOT ACTIVE. Only an OFFICIAL_CAPTURED packet listing a club as complete makes the club's
unlisted players ACTIVE_NOT_ON_INACTIVE_LIST. A partial or relayed list resolves only the names on it.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

from nfl.tools import availability as AV
from sportsplatform.governance.outcome import Cause, Outcome

SOURCES = ('OWNER_RELAYED', 'OFFICIAL_CAPTURED', 'REHEARSAL')
CITED_TIER = {'OFFICIAL_RELEASE': AV.TIER_OFFICIAL_RELEASE_CITED, 'AGGREGATOR': AV.TIER_AGGREGATOR_REPORTED,
              'SECONDHAND': AV.TIER_EXTERNAL_SECONDHAND}
#: (tier, claim) -> availability status. Each pairing respects availability.STATUS_REQUIRES_TIER.
STATUS_FOR = {
    (AV.TIER_OFFICIAL_CAPTURED, 'INACTIVE'): AV.CONFIRMED_INACTIVE,
    (AV.TIER_OFFICIAL_CAPTURED, 'ACTIVE'): AV.ACTIVE_NOT_ON_INACTIVE_LIST,
    (AV.TIER_OFFICIAL_RELEASE_CITED, 'INACTIVE'): AV.REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED,
    (AV.TIER_OFFICIAL_RELEASE_CITED, 'ACTIVE'): AV.REPORTED_ACTIVE_NOT_ON_LIST,
    (AV.TIER_AGGREGATOR_REPORTED, 'INACTIVE'): AV.REPORTED_INACTIVE_HIGH_CONFIDENCE,
    (AV.TIER_AGGREGATOR_REPORTED, 'ACTIVE'): AV.REPORTED_ACTIVE_NOT_ON_LIST,
    (AV.TIER_EXTERNAL_SECONDHAND, 'INACTIVE'): AV.REPORTED_OUT_UNVERIFIED,
    # a secondhand "he's active" is not a status any tier rule admits; it resolves the open
    # Questionable for selection purposes and leaves the availability status UNKNOWN_ACTIVE_STATE
    (AV.TIER_EXTERNAL_SECONDHAND, 'ACTIVE'): AV.UNKNOWN_ACTIVE_STATE,
}
#: owner-relayed starter citation -> (evidence tier, starter state); owner vocabulary 2026-10-04
STARTER_STATE_FOR = {'OFFICIAL_RELEASE': ('OFFICIAL_TEAM_PUBLISHED', 'CONFIRMED_BY_TEAM_PUBLISHED_EVIDENCE'),
                     'AGGREGATOR': ('HIGH_CONFIDENCE_REPORTED_STARTER', 'REPORTED_EXPECTED_STARTER'),
                     'SECONDHAND': ('EXTERNAL_RESEARCH_SECONDHAND', 'REPORTED_STARTER_UNVERIFIED')}
STATE_FOR_SOURCE = {'OFFICIAL_CAPTURED': 'APPLIED', 'OWNER_RELAYED': 'APPLIED_OWNER_RELAYED',
                    'REHEARSAL': 'REHEARSAL_NOT_EVIDENCE'}


def _norm(s):
    return re.sub(r'[^a-z]', '', re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', (s or '').lower()))


def load(path) -> Outcome:
    p = pathlib.Path(path)
    if not p.exists():
        return Outcome.blocked('EVIDENCE_PACKET_ABSENT', f'{p} does not exist', cause=Cause.DATA)
    raw = p.read_bytes()
    try:
        pk = json.loads(raw)
    except ValueError as e:
        return Outcome.fail('EVIDENCE_PACKET_NOT_JSON', str(e))
    bad = []
    if pk.get('source') not in SOURCES:
        bad.append(f"source {pk.get('source')!r} not in {SOURCES}")
    if not pk.get('packet_id') or not pk.get('received_at'):
        bad.append('packet_id and received_at are required')
    for i, x in enumerate(pk.get('players') or []):
        if x.get('status') not in ('ACTIVE', 'INACTIVE'):
            bad.append(f"players[{i}] {x.get('name')}: status must be ACTIVE or INACTIVE, got {x.get('status')!r}")
        if not x.get('name') or not x.get('team'):
            bad.append(f'players[{i}]: name and team are required')
        if x.get('cited') and x['cited'] not in CITED_TIER:
            bad.append(f"players[{i}] {x.get('name')}: cited {x['cited']!r} not in {sorted(CITED_TIER)}")
    for club, v in (pk.get('starters') or {}).items():
        if isinstance(v, dict) and (not v.get('name') or (v.get('cited') and v['cited'] not in STARTER_STATE_FOR)):
            bad.append(f"starters[{club}]: needs a name, and cited in {sorted(STARTER_STATE_FOR)}")
        elif not isinstance(v, (dict, str)):
            bad.append(f'starters[{club}]: a name or {{name, cited}}')
    if pk.get('complete_clubs') and pk.get('source') != 'OFFICIAL_CAPTURED':
        bad.append('complete_clubs is only meaningful for an OFFICIAL_CAPTURED packet')
    if not (pk.get('players') or pk.get('starters')):
        return Outcome.blocked('EVIDENCE_PACKET_EMPTY_INPUT', 'the packet carries no players and no starters',
                               cause=Cause.EMPTY_INPUT)
    if bad:
        return Outcome.fail('EVIDENCE_PACKET_SCHEMA', '; '.join(bad[:6]), problems=bad)
    pk['_sha256'] = hashlib.sha256(raw).hexdigest()
    return Outcome.ok('EVIDENCE_PACKET_LOADED', pk, f"{pk['packet_id']}: {len(pk.get('players') or [])} players, "
                                                    f"{len(pk.get('starters') or {})} starters")


def tier_of(pk, item):
    if pk['source'] == 'OFFICIAL_CAPTURED':
        return AV.TIER_OFFICIAL_CAPTURED
    return CITED_TIER.get(item.get('cited') or 'SECONDHAND', AV.TIER_EXTERNAL_SECONDHAND)


def resolve(pk, pool_rows) -> Outcome:
    """Packet -> {dk_id: resolution} and {club: starter dk_id}, or a refusal naming every unmatched row."""
    by = {}
    for r in pool_rows:
        by.setdefault((_norm(r['dk_name']), r['team']), []).append(r)
    res, unmatched = {}, []
    for x in pk.get('players') or []:
        hit = by.get((_norm(x['name']), x['team'])) or []
        if len(hit) != 1:
            unmatched.append({'name': x['name'], 'team': x['team'], 'why': 'NOT_IN_POOL' if not hit else 'AMBIGUOUS'})
            continue
        r = hit[0]
        tier = tier_of(pk, x)
        res[r['dk_id']] = {'claim': x['status'], 'tier': tier, 'status': STATUS_FOR[(tier, x['status'])],
                           'packet_id': pk['packet_id'], 'source': pk['source'],
                           'received_at': x.get('received_at') or pk['received_at'], 'note': x.get('note')}
    starters = {}
    for club, sv in (pk.get('starters') or {}).items():
        nm = sv['name'] if isinstance(sv, dict) else sv
        sv = sv if isinstance(sv, dict) else {}
        hit = [r for r in by.get((_norm(nm), club), []) if r['dk_pos'] == 'QB']
        if len(hit) != 1:
            unmatched.append({'name': nm, 'team': club, 'why': 'STARTER_NOT_A_QB_IN_POOL'})
            continue
        cited = sv.get('cited') or 'SECONDHAND'
        tier, sstate = STARTER_STATE_FOR[cited]
        if pk['source'] == 'OFFICIAL_CAPTURED':
            tier, sstate = AV.TIER_OFFICIAL_CAPTURED, 'CONFIRMED_BY_CAPTURED_TEAM_DOCUMENT'
        elif pk['source'] == 'REHEARSAL':
            sstate = 'REHEARSAL_STARTER_NOT_EVIDENCE'
        starters[club] = {'dk_id': hit[0]['dk_id'], 'name': hit[0]['dk_name'], 'cited': cited, 'evidence_tier': tier,
                          'starter_state': sstate, 'relayed_by': pk['source'], 'captured_document': pk['source'] == 'OFFICIAL_CAPTURED',
                          'received_at': sv.get('received_at') or pk['received_at'], 'note': sv.get('note')}
        if res.get(hit[0]['dk_id'], {}).get('claim') == 'INACTIVE':
            unmatched.append({'name': nm, 'team': club, 'why': 'NAMED_STARTER_AND_INACTIVE'})
    if unmatched:
        return Outcome.fail('EVIDENCE_PACKET_UNRESOLVED_PLAYER',
                            f'{len(unmatched)} packet row(s) do not resolve to exactly one pool player: '
                            + ', '.join(f"{u['name']} {u['team']} ({u['why']})" for u in unmatched[:6]),
                            unmatched=unmatched)
    complete = set(pk.get('complete_clubs') or ()) if pk['source'] == 'OFFICIAL_CAPTURED' else set()
    return Outcome.ok('EVIDENCE_PACKET_RESOLVED', {'players': res, 'starters': starters, 'complete_clubs': sorted(complete)},
                      f'{len(res)} players, {len(starters)} starters resolved')
