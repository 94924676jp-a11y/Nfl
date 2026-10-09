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
#: DraftKings club code -> nflverse roster club code (DK writes LAR; nflverse writes LA)
CLUB = {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS'}


def _norm(n):
    """Name key robust to punctuation and generational suffixes (James Cook III == James Cook)."""
    import re
    n = re.sub(r"[.'`]", '', str(n)).lower()
    n = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', n)
    return re.sub(r'\s+', ' ', n).strip()


def dk_pool(export):
    """{(name, club): {'pos', 'ids'}} from the player-pool block of a DKEntries export. The block's column offset is
    found from its own header ('Position', 'Name + ID'): Showdown puts it at column 11, Classic at 14. A fixed offset
    read the Classic pool as nothing, and every id became 'unknown' -- an empty read is an error, never a result."""
    rows = list(csv.reader(open(export, newline='', encoding='utf-8-sig')))
    off = next((i for r in rows for i in range(len(r) - 1) if r[i] == 'Position' and r[i + 1] == 'Name + ID'), None)
    if off is None:
        raise ValueError(f'DK_POOL_HEADER_NOT_FOUND {export}')
    out = {}
    for t in (r[off:] for r in rows[1:]):
        if len(t) >= 8 and t[3].strip().isdigit():
            out.setdefault((t[2].strip(), t[7].strip()), {'pos': t[0], 'ids': []})['ids'].append(t[3].strip())
    if not out:
        raise ValueError(f'DK_POOL_EMPTY {export}')
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
        by.setdefault(('~' + _norm(r['full_name']), r['team']), []).append(r)
    inact, elev = set(inactives), set(elevations)
    tx = transactions or {}
    out = {}
    for (name, club), info in pool.items():
        if info['pos'] == 'DST':
            out[(name, club)] = {'eligible': True, 'reason': 'TEAM_DEFENCE', 'evidence': 'by construction'}
            continue
        rc = CLUB.get(club, club)
        rr = (by.get((name, rc)) or by.get((ALIASES.get(name, ''), rc)) or by.get(('~' + _norm(name), rc))
              or by.get(('~' + _norm(ALIASES.get(name, '')), rc)) or [])
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
