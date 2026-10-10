#!/usr/bin/env python3.12
"""Read-only structural audit of the owner's DKEntries export for a Classic slate. Changes nothing.

    PYTHONPATH=. python3.12 entries_audit.py DKEntries.csv POOL_CHECK.json OUT.json

Facts are read from the file itself: contests, entry ids, the lineup in every entry, DK's own pool block
beside it. Each lineup is judged by nfl/dfs/classic/rules.assert_roster_legal (the single place a Classic
roster is judged legal), by slot eligibility from DK's Roster Position, by the two-game rule, and against
the pool check (nfl/integrations/dk_pool_check.py) for each player's upload state.
"""
import collections
import csv
import hashlib
import json
import pathlib
import re
import sys

from nfl.dfs.classic import rules as R

SLOTS = ('QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST')


def main(path, pool_check, out):
    raw = pathlib.Path(path).read_bytes()
    rows = list(csv.reader(raw.decode('utf-8-sig').splitlines()))
    hdr = [c.strip() for c in rows[0]]
    assert tuple(hdr[4:13]) == SLOTS, f'unexpected roster header {hdr[4:13]}'
    hi, off = next((i, j) for i, r in enumerate(rows) for j in range(len(r) - 1)
                   if r[j].strip() == 'Position' and r[j + 1].strip() == 'Name + ID')
    ph = [c.strip() for c in rows[hi][off:]]
    pool = {}
    for r in rows[hi + 1:]:
        if len(r) > off and r[off].strip():
            d = dict(zip(ph, [c.strip() for c in r[off:]]))
            pool[d['ID']] = d
    pc = {p['dk_id']: p for p in json.loads(pathlib.Path(pool_check).read_text())['evidence']['players']}
    ent = [r for r in rows[1:] if r and r[0].strip().isdigit()]
    contests = collections.defaultdict(list)
    for r in ent:
        contests[(r[2].strip(), r[1].strip(), r[3].strip())].append(r[0].strip())
    lineups, problems = collections.Counter(), []
    per_entry = []
    for r in ent:
        ids = []
        for s, c in zip(SLOTS, r[4:13]):
            m = re.search(r'\((\d+)\)\s*$', c or '')
            ids.append(m.group(1) if m else None)
        lu = tuple(ids)
        lineups[lu] += 1
        per_entry.append({'entry_id': r[0].strip(), 'contest_id': r[2].strip(), 'lineup': lu})
        if None in ids:
            problems.append({'entry_id': r[0], 'problem': 'UNFILLED_OR_UNPARSED_SLOT'})
    judged = []
    for lu, n in lineups.most_common():
        if None in lu or any(i not in pool for i in lu):
            judged.append({'n_entries': n, 'legal': False, 'why': 'slot empty or id not in the pool'})
            continue
        ps = [pool[i] for i in lu]
        slot_bad = [(s, p['Name'], p['Roster Position']) for s, p in zip(SLOTS, ps)
                    if not (p['Roster Position'].split('/')[0] == s or (s == 'FLEX' and 'FLEX' in p['Roster Position']))]
        legal, why = R.assert_roster_legal([p['Position'] for p in ps], [int(p['Salary']) for p in ps])
        games = collections.Counter(p['Game Info'].split()[0] for p in ps)
        judged.append({
            'n_entries': n, 'legal_shape_and_cap': legal, 'why': why,
            'salary': sum(int(p['Salary']) for p in ps), 'slot_violations': slot_bad,
            'n_games': len(games), 'games': dict(games), 'two_game_rule': len(games) >= 2,
            'players': [{'slot': s, 'name': p['Name'], 'id': p['ID'], 'team': p['TeamAbbrev'], 'pos': p['Position'],
                         'salary': int(p['Salary']), 'dk_avg': p.get('AvgPointsPerGame'),
                         'upload_state': (pc.get(p['ID']) or {}).get('upload'),
                         'reasons': (pc.get(p['ID']) or {}).get('reasons')}
                        for s, p in zip(SLOTS, ps)],
            'blocked_players': [p['Name'] for p in ps if (pc.get(p['ID']) or {}).get('upload') == 'BLOCKED']})
    res = {'ARTIFACT': 'CLASSIC_ENTRIES_AUDIT', 'READ_ONLY': 'the entries file is not modified or uploaded',
           'file_sha256': hashlib.sha256(raw).hexdigest(), 'n_entries': len(ent),
           'n_distinct_entry_ids': len({e['entry_id'] for e in per_entry}),
           'contests': [{'contest_id': k[0], 'contest_name': k[1], 'entry_fee': k[2], 'n_entries': len(v)}
                        for k, v in contests.items()],
           'roster_format': list(SLOTS), 'salary_cap': R.SALARY_CAP, 'pool_rows': len(pool),
           'pool_games': sorted({d['Game Info'].split()[0] for d in pool.values()}),
           'pool_kickoffs': sorted({d['Game Info'].split(' ', 1)[1] for d in pool.values()}),
           'n_distinct_lineups': len(lineups), 'lineups': judged, 'unfilled_or_unparsed': problems,
           'duplication': {'largest_identical_group': lineups.most_common(1)[0][1] if lineups else 0,
                           'by_contest': {cid: len({tuple(e['lineup']) for e in per_entry if e['contest_id'] == cid})
                                          for cid in {e['contest_id'] for e in per_entry}}}}
    pathlib.Path(out).write_text(json.dumps(res, indent=1) + '\n')
    print(f"{res['n_entries']} entries, {len(res['contests'])} contests, {res['n_distinct_lineups']} distinct lineup(s); "
          f"blocked players in lineups: {[j.get('blocked_players') for j in judged]}")


if __name__ == '__main__':
    main(*sys.argv[1:4])
