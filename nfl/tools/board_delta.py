#!/usr/bin/env python3.12
r"""What changed between two governed boards, stated per player and per game.

    python3.12 nfl/tools/board_delta.py BEFORE.csv AFTER.csv [--games G,G]

WHY THIS EXISTS

"Rerun and report the delta" is not answered by two summary lines. The
question a live operator actually has is which projections moved, by how much,
and whether a named contamination flag cleared -- and the honest answer has to
distinguish a row that MOVED from a row that APPEARED and from a row that
VANISHED, because averaging over a changing population hides exactly the games
that changed most.

Nothing here ranks, prices, or recommends. It subtracts.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json


KEY = ('game_id', 'team', 'player', 'metric')
FLAG = 'QB_INACTIVE_NOT_CONSUMED'


def load(path, games=None):
    out = {}
    for r in csv.DictReader(open(path)):
        if games and r['game_id'] not in games:
            continue
        out[tuple(r[k] for k in KEY)] = r
    return out


def flags_of(row):
    try:
        return {f['id'] for f in json.loads(row.get('known_defect_flags') or '[]')}
    except (ValueError, TypeError):
        return set()


def delta(before, after, games=None):
    b, a = load(before, games), load(after, games)
    moved, appeared, vanished, still = [], [], [], []
    for k, ra in a.items():
        rb = b.get(k)
        if rb is None:
            appeared.append((k, ra))
            continue
        try:
            d = float(ra['model_mean']) - float(rb['model_mean'])
        except (ValueError, TypeError):
            continue
        if abs(d) > 1e-9:
            moved.append((k, d, float(rb['model_mean']), float(ra['model_mean'])))
        else:
            still.append(k)
    for k, rb in b.items():
        if k not in a:
            vanished.append((k, rb))

    def contam(rows):
        c = collections.Counter()
        for k, r in rows.items():
            c[k[0]] += 1 if FLAG in flags_of(r) else 0
        return c
    cb, ca = contam(b), contam(a)
    per_game = {}
    for g in sorted({k[0] for k in b} | {k[0] for k in a}):
        nb = sum(1 for k in b if k[0] == g)
        na = sum(1 for k in a if k[0] == g)
        per_game[g] = {
            'rows_before': nb, 'rows_after': na,
            'contaminated_before': cb.get(g, 0),
            'contaminated_after': ca.get(g, 0),
            'contamination_cleared': cb.get(g, 0) > 0 and ca.get(g, 0) == 0,
            'rows_moved': sum(1 for k, *_ in moved if k[0] == g),
            'rows_appeared': sum(1 for k, _ in appeared if k[0] == g),
            'rows_vanished': sum(1 for k, _ in vanished if k[0] == g),
            'rows_identical': sum(1 for k in still if k[0] == g),
        }
    return {'moved': moved, 'appeared': appeared, 'vanished': vanished,
            'identical': len(still), 'per_game': per_game}


def main(argv=None):
    ap = argparse.ArgumentParser(description='board delta')
    ap.add_argument('before')
    ap.add_argument('after')
    ap.add_argument('--games', default=None)
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--json-out', default=None)
    x = ap.parse_args(argv)
    games = set(x.games.split(',')) if x.games else None
    d = delta(x.before, x.after, games)
    print(f'{"game":22s} {"rows b/a":>11s} {"contam b/a":>12s} '
          f'{"moved":>6s} {"new":>5s} {"gone":>5s} {"same":>5s}')
    for g, v in d['per_game'].items():
        print(f'{g:22s} {v["rows_before"]:5d}/{v["rows_after"]:<5d} '
              f'{v["contaminated_before"]:5d}/{v["contaminated_after"]:<6d} '
              f'{v["rows_moved"]:6d} {v["rows_appeared"]:5d} '
              f'{v["rows_vanished"]:5d} {v["rows_identical"]:5d}'
              + ('   CONTAMINATION CLEARED' if v['contamination_cleared'] else ''))
    print(f'\nlargest {x.top} movements by absolute change in model mean:')
    for k, dd, vb, va in sorted(d['moved'], key=lambda t: -abs(t[1]))[:x.top]:
        print(f'   {k[0]:20s} {k[1]:4s} {k[2]:24s} {k[3]:26s} '
              f'{vb:8.2f} -> {va:8.2f}  ({dd:+.2f})')
    if d['appeared']:
        print(f'\n{len(d["appeared"])} row(s) APPEARED (absent before):')
        for k, r in d['appeared'][:x.top]:
            print(f'   {k[0]:20s} {k[1]:4s} {k[2]:24s} {k[3]:26s} '
                  f'= {r["model_mean"]}')
    if d['vanished']:
        print(f'\n{len(d["vanished"])} row(s) VANISHED (present before):')
        for k, r in d['vanished'][:x.top]:
            print(f'   {k[0]:20s} {k[1]:4s} {k[2]:24s} {k[3]:26s} '
                  f'was {r["model_mean"]}')
    print(f'\nidentical rows: {d["identical"]}')
    if x.json_out:
        open(x.json_out, 'w').write(json.dumps(
            {'per_game': d['per_game'], 'n_moved': len(d['moved']),
             'n_appeared': len(d['appeared']),
             'n_vanished': len(d['vanished']),
             'n_identical': d['identical'],
             'largest_movements': [
                 {'game_id': k[0], 'team': k[1], 'player': k[2],
                  'metric': k[3], 'before': vb, 'after': va, 'delta': dd}
                 for k, dd, vb, va in sorted(
                     d['moved'], key=lambda t: -abs(t[1]))[:200]]},
            indent=1) + '\n')
        print(f'-> {x.json_out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
