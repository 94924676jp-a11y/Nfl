#!/usr/bin/env python3.12
"""Game-day eligibility of every DraftKings Showdown player, from positive roster evidence. Fail-closed.

    python3.12 nfl/tools/roster_eligibility.py EXPORT --rosters ROSTER_CAPTURE --season 2026 --week 5 \
        [--inactives JSON] [--transactions JSON] [--elevations JSON] [--out JSON]

Owner directive 2026-10-08 (TB@DAL): David Sills V (TB, on IR since Aug 30), Josh Williams (TB practice squad) and
Emari Demercado (DAL, waived the day of the game) were selected into the portfolio. The Showdown availability layer
mapped "everyone not named" to UNKNOWN_ACTIVE_STATE (showdown_slate_state.py:33), which is not an absent status, and
never read the roster capture's own status column. Silence was read as eligibility.

THE RULE. A player is ELIGIBLE only with positive evidence that he can play this game:
  * on the club's roster for this week in the latest capture with status ACT, and not on the inactive list, and not
    released by a later transaction; or
  * a practice-squad player (DEV) with an explicit game-day ELEVATION record.
Everything else is BLOCKED with a named reason: RESERVE (RES: IR / PUP / NFI / suspended), PRACTICE_SQUAD_NOT_ELEVATED
(DEV), NOT_ON_WEEK_ROSTER, RELEASED (a transaction after the capture), GAME_DAY_INACTIVE, RETIRED, or
STATUS_UNRECOGNISED. Team defences (DST) are eligible by construction. Unknown is never eligible.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import pathlib

ALIASES = {'Kenny Gainwell': 'Kenneth Gainwell'}


def dk_pool(export):
    rows = list(csv.reader(open(export, newline='', encoding='utf-8-sig')))
    out = {}
    for t in (r[11:] for r in rows[1:]):
        if len(t) >= 8 and t[3].strip().isdigit():
            out.setdefault((t[2].strip(), t[7].strip()), {'pos': t[0], 'ids': []})['ids'].append(t[3].strip())
    return out


def roster_rows(path, season, week):
    p = pathlib.Path(path)
    raw = p.read_bytes()
    text = gzip.decompress(raw).decode() if p.name.endswith('.gz') else raw.decode()
    return [r for r in csv.DictReader(io.StringIO(text)) if r.get('season') == str(season) and r.get('week') == str(week)]


def classify(pool, rosters, inactives=(), transactions=None, elevations=()):
    """{(name, club): {'eligible': bool, 'reason': str, 'evidence': str}}"""
    by = {}
    for r in rosters:
        by.setdefault((r['full_name'], r['team']), []).append(r)
    inact, elev = set(inactives), set(elevations)
    tx = transactions or {}
    out = {}
    for (name, club), info in pool.items():
        if info['pos'] == 'DST':
            out[(name, club)] = {'eligible': True, 'reason': 'TEAM_DEFENCE', 'evidence': 'by construction'}
            continue
        rr = by.get((name, club)) or by.get((ALIASES.get(name, ''), club)) or []
        st = sorted({r['status'] for r in rr})
        if name in tx:
            res = (False, 'RELEASED', tx[name])
        elif name in inact:
            res = (False, 'GAME_DAY_INACTIVE', 'inactive list')
        elif not rr:
            res = (False, 'NOT_ON_WEEK_ROSTER', 'absent from the week roster capture')
        elif st == ['ACT']:
            res = (True, 'ACTIVE_ROSTER', 'roster status ACT')
        elif st == ['DEV']:
            res = (True, 'PRACTICE_SQUAD_ELEVATED', 'elevation record') if name in elev else \
                  (False, 'PRACTICE_SQUAD_NOT_ELEVATED', 'roster status DEV, no elevation record')
        elif st == ['RES']:
            res = (False, 'RESERVE', 'roster status RES (IR/PUP/NFI/suspended)')
        elif st == ['RET']:
            res = (False, 'RETIRED', 'roster status RET')
        else:
            res = (False, 'STATUS_UNRECOGNISED', f'roster status {st}')
        out[(name, club)] = {'eligible': res[0], 'reason': res[1], 'evidence': res[2], 'roster_status': st}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('--rosters', required=True)
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--inactives')
    ap.add_argument('--transactions', help='JSON {name: evidence} for releases after the roster capture')
    ap.add_argument('--elevations', help='JSON [name] of game-day practice-squad elevations')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    ld = lambda p, d: json.loads(pathlib.Path(p).read_text()) if p else d  # noqa: E731
    res = classify(dk_pool(a.export), roster_rows(a.rosters, a.season, a.week), ld(a.inactives, []),
                   ld(a.transactions, {}), ld(a.elevations, []))
    doc = {'ARTIFACT': 'ROSTER_ELIGIBILITY', 'rule': 'eligible only with positive evidence; unknown is blocked',
           'players': {f'{n}|{c}': v for (n, c), v in sorted(res.items())},
           'blocked': sorted(f'{n}|{c}' for (n, c), v in res.items() if not v['eligible'])}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps({'n': len(res), 'blocked': doc['blocked']}, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
