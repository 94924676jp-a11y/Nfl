#!/usr/bin/env python3.12
"""Pasted game-day inactive lists -> the day's cumulative evidence packet, with provenance.

    python3.12 nfl/tools/sunday_paste.py 2026W4 PASTE.txt [--packet nfl/dfs/salaries/evidence/2026W4_SUNDAY_OWNER.json]

PASTE.txt, one club per line, as copied from the source:

    SOURCE: RotoWire NFL lineups (aggregation of official game-day inactives) https://www.rotowire.com/football/lineups.php
    BAL: Name One, Name Two, Name Three
    CHI: ...
    SOURCE: Sarah Barshop (Rams beat reporter) https://x.com/sarahbarshop/status/2106770137592557697
    LA: ...
    TB: none

Each player becomes INACTIVE cited AGGREGATOR (an aggregation or a reporter relaying the club's official
list; never relabelled first-party). A club line is that club's FULL game-day list, so every Questionable
or Doubtful player of that club who is NOT on it is written ACTIVE (REPORTED_ACTIVE_NOT_ON_LIST, the
aggregator tier) with a note saying exactly that. A club with no line stays unresolved: absence of a
list is never "everyone plays". Names resolve fail-closed against the DraftKings pool; a name that does
not resolve stops the write and is printed. Players not in the DK pool (linemen, defenders) are kept in
the packet's off_pool list, since they move nobody's DK points here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import sunday_evidence as SE  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
ALIAS = {'LAR': 'LA', 'JAC': 'JAX'}


def parse(text):
    src, out = None, {}
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.upper().startswith('SOURCE:'):
            src = ln.split(':', 1)[1].strip()
            continue
        m = re.match(r'^([A-Za-z]{2,3})\s*(?:inactives)?\s*[:\-]\s*(.*)$', ln, re.I)
        if not m:
            raise ValueError(f'unreadable line: {ln!r}')
        club = ALIAS.get(m.group(1).upper(), m.group(1).upper())
        body = m.group(2).strip()
        names = [] if body.lower() in ('none', 'no inactives', '') else \
            [re.sub(r'\s*\((?:[A-Z]{1,3}|[A-Za-z ]+)\)\s*$', '', re.sub(r'^(?:QB|RB|WR|TE|K|P|OL|OT|OG|C|DL|DE|DT|LB|CB|S|LS)\s+', '', n.strip()))
             for n in re.split(r',|;', body) if n.strip()]
        out[club] = {'names': names, 'source': src}
    return out


def build(slate, text, packet_path, received_at, state_path=None):
    # The production state path exists only for a slate with a DK file. A research-universe slate (2026 W5:
    # no DK file yet) never writes it, so the fallback must be able to read the state it is applied to.
    state = json.loads(pathlib.Path(state_path or (OUT_DIR / f'DK_{slate}_EARLY_STATE.json')).read_text())
    pool = [{'dk_id': k, 'dk_name': v['name'], 'team': v['team'], 'dk_pos': v['position']} for k, v in state['players'].items()]
    clubs = parse(text)
    slate_clubs = {v['team'] for v in state['players'].values()}
    bad = sorted(set(clubs) - slate_clubs)
    if bad:
        raise SystemExit(f'REFUSED: clubs not on this slate: {bad}')
    pk = json.loads(pathlib.Path(packet_path).read_text())
    keep = {(x['name'], x['team']): x for x in pk.get('players') or []}
    off_pool = list(pk.get('off_pool') or [])
    probe = {'packet_id': 'probe', 'source': pk['source'], 'received_at': received_at, 'starters': {}}
    for club, v in clubs.items():
        resolved = []
        for nm in v['names']:
            m = re.match(r'^([A-Z])\.\s*(.+)$', nm)
            if m:   # "M. Carter": exactly one pool player on the club with that initial and surname, or refuse
                ini, sur = m.group(1).lower(), SE._norm(m.group(2))
                hits = [q['dk_name'] for q in pool if q['team'] == club and q['dk_name'][:1].lower() == ini
                        and SE._norm(q['dk_name']).endswith(sur)]
                if len(hits) > 1:
                    raise SystemExit(f'REFUSED: {nm!r} ({club}) is ambiguous: {hits}')
                if hits:
                    nm = hits[0]
            resolved.append(nm)
        v['names'] = resolved
        for nm in v['names']:
            r = SE.resolve({**probe, 'players': [{'name': nm, 'team': club, 'status': 'INACTIVE'}]}, pool)
            if r.state.value != 'PASS':
                import difflib
                near = [q['dk_name'] for q in pool if q['team'] == club and
                        difflib.SequenceMatcher(None, SE._norm(q['dk_name']), SE._norm(nm)).ratio() >= 0.85]
                if near:
                    raise SystemExit(f'REFUSED: {nm!r} ({club}) is not an exact pool name but is close to {near}: fix the spelling')
                off_pool.append({'name': nm, 'team': club, 'source': v['source'], 'received_at': received_at,
                                 'why': 'not in the DraftKings pool under this name and club (linemen and defenders are not)'})
                continue
            keep[(nm, club)] = {'name': nm, 'team': club, 'status': 'INACTIVE', 'cited': 'AGGREGATOR',
                                'received_at': received_at, 'note': f"game-day inactive per {v['source']}"}
        listed = {SE._norm(n) for n in v['names']}
        for p in state['players'].values():
            if p['team'] == club and (p['current_availability'].get('designation') or '') in ('QUESTIONABLE', 'DOUBTFUL') \
                    and SE._norm(p['name']) not in listed:
                keep[(p['name'], club)] = {'name': p['name'], 'team': club, 'status': 'ACTIVE', 'cited': 'AGGREGATOR',
                                           'received_at': received_at,
                                           'note': f"{p['current_availability']['designation']} on Friday; NOT on {club}'s full "
                                                   f"game-day inactive list per {v['source']}"}
    pk['players'] = sorted(keep.values(), key=lambda x: (x['team'], x['name']))
    pk['off_pool'] = off_pool
    pk['clubs_with_full_list'] = sorted(set(pk.get('clubs_with_full_list') or []) | set(clubs))
    # per-club receipt, so a coverage check can tell a list taken before the publication window from one after
    cl = dict(pk.get('club_lists') or {})
    for club, v in clubs.items():
        cl[club] = {'received_at': received_at, 'source': v['source'], 'n_names': len(v['names'])}
    pk['club_lists'] = cl
    pk['source_detail'] = (pk.get('source_detail') or '') + f" | {received_at}: game-day inactives for {sorted(clubs)} " \
                                                            f"from {sorted({v['source'] for v in clubs.values()})}"
    lo_tmp = pathlib.Path(packet_path).with_suffix('.candidate.json')
    lo_tmp.write_text(json.dumps(pk, indent=1))
    lo = SE.load(lo_tmp)
    if lo.state.value != 'PASS':
        raise SystemExit(f'REFUSED: {lo.code} {lo.detail}')
    ro = SE.resolve(lo.value, pool)
    if ro.state.value != 'PASS':
        raise SystemExit(f'REFUSED: {ro.code} {ro.detail}')
    lo_tmp.replace(packet_path)
    missing = sorted(slate_clubs - set(pk['clubs_with_full_list']))
    return pk, ro.value, missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('paste')
    ap.add_argument('--packet', default=str(OUT_DIR / 'evidence/2026W4_SUNDAY_OWNER.json'))
    ap.add_argument('--state', help='the state the packet is applied to (default: the production state path)')
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    pk, res, missing = build(a.slate_id, pathlib.Path(a.paste).read_text(), a.packet, now, state_path=a.state)
    ina = [x for x in pk['players'] if x['status'] == 'INACTIVE']
    act = [x for x in pk['players'] if x['status'] == 'ACTIVE']
    print(f'PASS[PASTE_APPLIED] {len(ina)} DK-pool inactives, {len(act)} cleared Questionables, '
          f"{len(pk['off_pool'])} off-pool names kept, clubs without a list: {missing or 'none'}")
    for x in ina:
        print(f"  INACTIVE {x['team']} {x['name']}")
    for x in act:
        print(f"  ACTIVE   {x['team']} {x['name']}  ({x['note']})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
