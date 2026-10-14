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


#: THE SHARED THREE-STATE ELIGIBILITY CONTRACT (owner OD-001 decision 1 and OD-002, 2026-10-14), Classic AND Showdown.
#: `eligible` stays the fail-closed SELECTION boolean (only CONFIRMED_ELIGIBLE may be selected); `eligibility_state` is
#: what the FORECAST may act on:
#:   CONFIRMED_ELIGIBLE    included, subject to normal playing-time and role uncertainty (eligibility is not playing)
#:   CONFIRMED_INELIGIBLE  game-specific evidence says he cannot play: no opportunity, his share redistributed
#:   ELIGIBILITY_UNRESOLVED missing evidence is NOT proof of ineligibility: the forecast keeps him as the incumbent
#:                          had him, the missing evidence is named, he is never selectable, and a certified release
#:                          refuses while he carries material opportunity. No probability of eligibility is invented.
CONFIRMED_ELIGIBLE = 'CONFIRMED_ELIGIBLE'
CONFIRMED_INELIGIBLE = 'CONFIRMED_INELIGIBLE'
ELIGIBILITY_UNRESOLVED = 'ELIGIBILITY_UNRESOLVED'
#: the evidence an unresolved player lacks, by reason (OD-002: "record exactly which evidence is missing")
MISSING_EVIDENCE = {
    'PRACTICE_SQUAD_NOT_ELEVATED': 'GAME_DAY_ELEVATION_RECORDS (no elevation evidence was supplied for this game)',
    'NOT_ON_WEEK_ROSTER': 'WEEK_ROSTER_ENTRY (he is absent from this week\'s roster capture)',
    'STATUS_UNRECOGNISED': 'RECOGNISED_ROSTER_STATUS (the capture carries a status outside the closed vocabulary)',
}
_INELIGIBLE_REASONS = ('RESERVE', 'EXEMPT_LIST', 'RETIRED', 'RELEASED', 'GAME_DAY_INACTIVE')
_ELIGIBLE_REASONS = ('ACTIVE_ROSTER', 'PRACTICE_SQUAD_ELEVATED', 'TEAM_DEFENCE')


def eligibility_state(reason, *, elevation_evidence: bool) -> str:
    """Map a classify() reason to the three-state contract. A practice-squad player is CONFIRMED ineligible only when
    elevation evidence for this game was supplied and does not name him; without that evidence he is UNRESOLVED.
    Absent from the week capture or an unrecognised status is UNRESOLVED, never confirmed either way."""
    if reason in _ELIGIBLE_REASONS:
        return CONFIRMED_ELIGIBLE
    if reason in _INELIGIBLE_REASONS:
        return CONFIRMED_INELIGIBLE
    if reason == 'PRACTICE_SQUAD_NOT_ELEVATED':
        return CONFIRMED_INELIGIBLE if elevation_evidence else ELIGIBILITY_UNRESOLVED
    return ELIGIBILITY_UNRESOLVED


def classify(pool, rosters, inactives=(), transactions=None, elevations=None):
    """{(name, club): {'eligible': bool, 'reason': str, 'evidence': str, 'eligibility_state': str}}

    `elevations=None` means NO elevation evidence was supplied (a practice-squad player is then UNRESOLVED); a list,
    even an empty one, is evidence for this game day."""
    by = {}
    for r in rosters:
        by.setdefault((r['full_name'], r['team']), []).append(r)
        by.setdefault(('~' + _norm(r['full_name']), r['team']), []).append(r)
    elevation_evidence = elevations is not None
    inact, elev = set(inactives), set(elevations or ())
    tx = transactions or {}
    out = {}
    for (name, club), info in pool.items():
        if info['pos'] == 'DST':
            out[(name, club)] = {'eligible': True, 'reason': 'TEAM_DEFENCE', 'evidence': 'by construction',
                                 'eligibility_state': CONFIRMED_ELIGIBLE}
            continue
        rc = CLUB.get(club, club)
        # the declared availability.NAME_ALIASES too (2026-10-12: DK 'Joshua Palmer' read NOT_ON_WEEK_ROSTER against the
        # roster's 'Josh Palmer')
        from nfl.tools.availability import NAME_ALIASES as _NA
        al2 = _NA.get((name, club)) or _NA.get((name, rc)) or ''
        rr = (by.get((name, rc)) or by.get((ALIASES.get(name, ''), rc)) or by.get(('~' + _norm(name), rc))
              or by.get(('~' + _norm(ALIASES.get(name, '')), rc)) or by.get((al2, rc)) or [])
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
        elif st == ['EXE']:
            res = (False, 'EXEMPT_LIST', 'roster status EXE (exempt list)')
        elif st == ['CUT']:
            res = (False, 'RELEASED', 'roster status CUT in the week capture')
        else:
            res = (False, 'STATUS_UNRECOGNISED', f'roster status {st}')
        out[(name, club)] = {'eligible': res[0], 'reason': res[1], 'evidence': res[2], 'roster_status': st,
                             'eligibility_state': eligibility_state(res[1], elevation_evidence=elevation_evidence)}
    return out


def opportunity_withheld(res):
    """THE SHARED UPSTREAM RULE, used by Classic and Showdown before projection (OD-002, 2026-10-14):
    {(name, club): entry} for every CONFIRMED_INELIGIBLE player -- he receives no active-game opportunity. An
    ELIGIBILITY_UNRESOLVED player is NOT withheld (missing evidence is not evidence of absence; see `unresolved`).
    GAME_DAY_INACTIVE is left out only because the inactive list has its own path in both pipelines."""
    return {k: v for k, v in res.items()
            if v['eligibility_state'] == CONFIRMED_INELIGIBLE and v['reason'] != 'GAME_DAY_INACTIVE'}


def unresolved(res):
    """{(name, club): entry + 'missing_evidence'} for every ELIGIBILITY_UNRESOLVED player: kept in the forecast as the
    incumbent had him, never selectable, and a release blocker while he carries material opportunity."""
    return {k: {**v, 'missing_evidence': MISSING_EVIDENCE.get(v['reason'], 'UNSPECIFIED')}
            for k, v in res.items() if v['eligibility_state'] == ELIGIBILITY_UNRESOLVED}


def withheld_status(eligibility_state_, reason):
    """(availability status, tier) for a CONFIRMED_INELIGIBLE player. Every value is in availability.ABSENT_STATUSES
    (zero opportunity); the label says which evidence withheld him. An unresolved player is never withheld, so asking
    for his status is an error rather than a label."""
    from nfl.tools import availability as AV
    if eligibility_state_ != CONFIRMED_INELIGIBLE:
        raise ValueError(f'WITHHELD_STATUS_FOR_{eligibility_state_}: only a confirmed-ineligible player is withheld')
    if reason == 'PRACTICE_SQUAD_NOT_ELEVATED':
        return AV.PRACTICE_SQUAD_NOT_ELEVATED_CONFIRMED, AV.TIER_ROSTER_AND_ELEVATION
    return AV.NOT_ON_ACTIVE_ROSTER_CAPTURED, AV.TIER_ROSTER_STATUS


def capture_clock(path, repo=None):
    """(clock string, basis) of a roster capture, read from the vintage manifest row that names its content hash, so
    the state and the release record can say how current the roster evidence was. The manifest lines are searched as
    text for the 16-hex hash in the file name; no row means UNATTRIBUTABLE, never a guessed time."""
    repo = pathlib.Path(repo or pathlib.Path(__file__).resolve().parents[2])
    h = pathlib.Path(path).name.split('.')[1]
    man = repo / 'nfl' / 'vintage_manifest.jsonl'
    if not man.is_file():
        return None, 'NO_MANIFEST'
    with man.open(encoding='utf-8') as fh:
        for line in fh:
            if h in line:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                t = r.get('retrieved_at') or r.get('capture_id')
                if t:
                    return str(t), 'MANIFEST_' + ('RETRIEVED_AT' if r.get('retrieved_at') else 'CAPTURE_ID')
    return None, 'UNATTRIBUTABLE'


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
                   ld(a.transactions, {}), ld(a.elevations, None))
    doc = {'ARTIFACT': 'ROSTER_ELIGIBILITY', 'rule': 'eligible only with positive evidence; unknown is blocked',
           'players': {f'{n}|{c}': v for (n, c), v in sorted(res.items())},
           'blocked': sorted(f'{n}|{c}' for (n, c), v in res.items() if not v['eligible'])}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps({'n': len(res), 'blocked': doc['blocked']}, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
