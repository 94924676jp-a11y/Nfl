#!/usr/bin/env python3.12
"""Final-inactives coverage for a slate: every club's own list, inside its publication window, or a named block.

    python3.12 nfl/integrations/inactives_coverage.py --state STATE.json --packet PACKET.json [--out JSON]

A scheduled task firing is not evidence, and an empty or missing list is not "everyone active". This reads the
cumulative Sunday evidence packet (nfl/tools/sunday_evidence.py, filled by nfl/tools/sunday_paste.py or an
official capture) and the state's games, and judges each of the slate's clubs separately:

  COVERED                  a full game-day list for the club, received at or after its window opens
                           (kickoff - 90 minutes, the nominal deadline for inactive lists)
  STALE_BEFORE_WINDOW      a list received before the window opened: it cannot be the final list
  RECEIPT_TIME_UNKNOWN     a list with no per-club receipt time (older packets): cannot be judged
  REHEARSAL_NOT_EVIDENCE   a rehearsal packet: exercises the chain, certifies nothing
  MISSING                  no list for the club

PASS only when every club is COVERED. Otherwise BLOCKED[SUN_INACTIVES_COVERAGE_INCOMPLETE] naming each club.
A COVERED owner-relayed or aggregator list is still relayed evidence; its tier travels with it and is never
upgraded to a captured official document.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

T_MINUS = dt.timedelta(minutes=90)
KICK_FMT = '%m/%d/%Y %I:%M%p'


def _ts(s):
    return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))


def kickoff_utc(state):
    """The slate kickoff ('10/11/2026 01:00PM ET') in UTC; ET is UTC-4 in the regular season's first half."""
    k = state['kickoff'].replace(' ET', '')
    local = dt.datetime.strptime(k, KICK_FMT)
    # The slate is one kickoff. EDT runs to the first Sunday of November; refuse a date outside it rather
    # than guess the offset.
    if not (3 <= local.month <= 10 or (local.month == 11 and local.day < 1)):
        raise SystemExit(f'KICKOFF_OFFSET_UNDECLARED: {state["kickoff"]} is outside the EDT range this tool assumes')
    return (local + dt.timedelta(hours=4)).replace(tzinfo=dt.timezone.utc)


def judge(state, packet) -> Outcome:
    ko = kickoff_utc(state)
    opens = ko - T_MINUS
    lists = packet.get('club_lists') or {}
    full = set(packet.get('clubs_with_full_list') or []) | set(packet.get('complete_clubs') or [])
    rows = []
    for gid, g in sorted(state['games'].items()):
        for club in (g['away'], g['home']):
            if packet.get('source') == 'REHEARSAL':
                verdict = 'REHEARSAL_NOT_EVIDENCE' if club in full else 'MISSING'
            elif club not in full:
                verdict = 'MISSING'
            elif club not in lists or not lists[club].get('received_at'):
                verdict = 'RECEIPT_TIME_UNKNOWN'
            elif _ts(lists[club]['received_at']) < opens:
                verdict = 'STALE_BEFORE_WINDOW'
            else:
                verdict = 'COVERED'
            rows.append({'game_id': gid, 'club': club, 'verdict': verdict,
                         'received_at': (lists.get(club) or {}).get('received_at'),
                         'source': (lists.get(club) or {}).get('source'),
                         'n_names': (lists.get(club) or {}).get('n_names'),
                         'tier': packet.get('source')})
    bad = [r for r in rows if r['verdict'] != 'COVERED']
    ev = dict(kickoff_utc=ko.isoformat(), window_opens_utc=opens.isoformat(), packet_id=packet.get('packet_id'),
              packet_source=packet.get('source'), n_clubs=len(rows), clubs=rows,
              NOT_EVIDENCE_OF='a scheduled run firing; an empty or missing list meaning everyone is active')
    if bad:
        return Outcome.blocked('SUN_INACTIVES_COVERAGE_INCOMPLETE',
                               f"{len(bad)} of {len(rows)} clubs not covered: "
                               + ', '.join(f"{r['club']}={r['verdict']}" for r in bad[:16]),
                               cause=Cause.DATA, **ev)
    return Outcome.ok('SUN_INACTIVES_COVERAGE_COMPLETE', value=rows, detail=f'all {len(rows)} clubs covered', **ev)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--state', required=True)
    ap.add_argument('--packet', required=True)
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    st = json.loads(pathlib.Path(a.state).read_text())
    pk = json.loads(pathlib.Path(a.packet).read_text())
    o = judge(st, pk)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps({'code': o.code, 'detail': o.detail, 'evidence': o.evidence},
                                                  indent=1, default=str) + '\n')
    return 0 if o.state.value == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
