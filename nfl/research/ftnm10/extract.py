"""FTN-M10: flatten the matchup endpoint into a play/matchup table.

Outcomes are NOT in this endpoint. Only `description` carries them, so the
target receiver, completion and yardage are parsed from the NFL gamebook
string. That parse is checked, not assumed: every pass play must resolve to
exactly one of {target, no-target} and the residue is reported.
"""
import collections, glob, json, os, re, sys

TARGET = re.compile(
    r'pass\s+(?:(incomplete)\s+)?(?:(short|deep)\s+)?(?:(left|right|middle)\s+)?'
    r'to\s+(\d+)-([A-Z]\.[A-Za-z\'\-]+\.?(?:\s+[A-Z][a-zA-Z\'\-]+)?)')
YARDS = re.compile(r'for (-?\d+) yard')
SACK = re.compile(r'\bsacked\b', re.I)
SPIKE = re.compile(r'spiked the ball', re.I)
THROWAWAY = re.compile(r'pass incomplete(?! .*\bto\b)', re.I)
INT = re.compile(r'INTERCEPTED', re.I)


def parse_pass(desc):
    if SPIKE.search(desc):
        return {'kind': 'spike'}
    if SACK.search(desc):
        return {'kind': 'sack'}
    m = TARGET.search(desc)
    if not m:
        return {'kind': 'no_target'}      # throwaway / batted / scramble
    inc, depth, side, num, name = m.groups()
    y = YARDS.search(desc)
    return {'kind': 'target', 'jersey': int(num), 'name_abbrev': name,
            'complete': inc is None and not INT.search(desc),
            'intercepted': bool(INT.search(desc)),
            'depth': depth, 'side': side,
            'yards': (int(y.group(1)) if y and inc is None else
                      (0 if inc else None))}


def load(dirpath):
    rows, plays, events = [], [], []
    for f in sorted(glob.glob(os.path.join(dirpath, '*.json'))):
        d = json.load(open(f))
        e = d['event']
        events.append({'event_id': e['id'], 'name': e['name'],
                       'season': e['season'], 'date': e['date'],
                       'season_type': e['season_type']['id'],
                       'file': os.path.basename(f), 'n_plays': len(d['plays'])})
        for p in d['plays']:
            pl = p['play']
            ptype = (pl.get('play_type') or {}).get('id')
            desc = pl.get('description') or ''
            pr = parse_pass(desc) if ptype == 'pass' else {'kind': ptype}
            prow = {'event_id': e['id'], 'game': e['name'], 'date': e['date'],
                    'play_id': pl['id'], 'number': pl['number'],
                    'period': pl['period'], 'play_type': ptype,
                    'offense': (pl.get('offense') or {}).get('name'),
                    'offense_id': (pl.get('offense') or {}).get('id'),
                    'defense_id': (pl.get('defense') or {}).get('id'),
                    'n_matchups': len(p.get('matchups') or []),
                    'desc': desc, **{f'p_{k}': v for k, v in pr.items()}}
            plays.append(prow)
            for m in (p.get('matchups') or []):
                o = m.get('offensive_player') or {}
                dd = m.get('defensive_player') or {}
                rows.append({
                    'event_id': e['id'], 'play_id': pl['id'],
                    'play_type': ptype, 'period': pl['period'],
                    'off_id': (o.get('player') or {}).get('id'),
                    'off_name': (o.get('player') or {}).get('name'),
                    'off_team': (o.get('team') or {}).get('id'),
                    'off_pos': o.get('position'), 'off_role': o.get('role'),
                    'def_id': (dd.get('player') or {}).get('id'),
                    'def_name': (dd.get('player') or {}).get('name'),
                    'def_pos': dd.get('position'),
                })
    return events, plays, rows


SUFFIXES = {'JR', 'SR', 'II', 'III', 'IV', 'V'}


def _surname_key(full_name):
    """(first initial, normalised surname). Deterministic; suffixes dropped."""
    parts = [x for x in full_name.replace('.', ' ').split() if x]
    if len(parts) < 2:
        return None
    tail = [x for x in parts[1:] if x.upper().strip(".,'") not in SUFFIXES]
    if not tail:
        return None
    sur = ''.join(tail).upper().replace("'", '').replace('-', '')
    return (parts[0][0].upper(), sur)


ALIGN = {'WR': 'WIDE', 'SLT': 'SLOT', 'HB': 'BACK', 'FB': 'BACK',
         'H-TE': 'TE_FLEX', 'Y-TE': 'TE_INLINE'}
DEFCLASS = {'CB': 'CB', 'SCB': 'SCB', 'LB': 'LB', 'OLB': 'LB', 'SLB': 'LB',
            'SS': 'S', 'FS': 'S'}
ROUTE_ROLES = {'rte', 'brte', 'frte'}


def resolve_targets(plays, mus):
    """Link the parsed target to a charted offensive player.

    NOT FUZZY MATCHING. The key is EXACT: first initial plus surname, both
    taken deterministically from the two sides, restricted to the players
    charted for that offense in that game. A key that resolves to anything
    other than exactly one charted player is REFUSED and counted; nothing is
    scored, ranked or approximated.
    """
    charted = collections.defaultdict(dict)      # (event, off_team) -> key->ids
    collide = collections.defaultdict(set)
    for m in mus:
        if m['off_name'] is None:
            continue
        key = _surname_key(m['off_name'])
        if key is None:
            continue
        k = (m['event_id'], m['off_team'])
        prev = charted[k].get(key)
        if prev is not None and prev != m['off_id']:
            collide[k].add(key)
        charted[k][key] = m['off_id']
    stats = collections.Counter()
    for p in plays:
        p['target_off_id'] = None
        if p.get('p_kind') != 'target':
            continue
        key = _surname_key(p['p_name_abbrev'])
        if key is None:
            stats['unparseable_name'] += 1
            continue
        k = (p['event_id'], p['offense_id'])
        if key in collide.get(k, ()):
            stats['ambiguous_refused'] += 1
            continue
        pid = charted.get(k, {}).get(key)
        if pid is None:
            stats['not_charted'] += 1
            continue
        p['target_off_id'] = pid
        stats['resolved'] += 1
    return stats
