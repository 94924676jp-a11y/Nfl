"""Build receiving primitives per player-game, replicating P1's target rule.

TARGET, from nfl/research/p1/build_panel.py:88-95: receiver_player_id set AND
pass_attempt == 1. Two-point attempts excluded, matching the participation join.

WHY receiver_player_id AND NOT pass_attempt ALONE. Measured here: every sack in
2020-2025 carries pass_attempt == 1 (1,135 / 1,244 / 1,297 / 1,410 / 1,314 /
1,287, all of them). What keeps sacks out of the receiving denominator is that
NO sack carries a receiver_player_id -- 0 in every season. Defining a target on
pass_attempt would put every sack in the denominator.
"""
import csv, gzip, collections, pickle
csv.field_size_limit(10**7)

def i(v, d=0):
    try: return int(float(v))
    except (TypeError, ValueError): return d
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

out = {}
diag = collections.Counter()
for y in (2020, 2021, 2022, 2023, 2024, 2025):
    plyr = collections.defaultdict(lambda: collections.Counter())
    per_rec = collections.defaultdict(list)
    with gzip.open(f'pbp{y}.csv.gz', 'rt') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            if i(r.get('two_point_attempt')):
                continue
            rec = r.get('receiver_player_id') or ''
            if not (rec and i(r.get('pass_attempt'))):
                continue
            k = (y, i(r.get('week')), r.get('posteam') or '', rec)
            p = plyr[k]
            p['targets'] += 1
            ay = f(r.get('air_yards'))
            # NULL IS NOT ZERO. A null air_yards on a target is counted as a
            # missing observation, never folded into the sum as 0 -- that is
            # the silent-zero defect, and it would bias air-yards-per-target
            # downward by exactly the missing count.
            if ay is None:
                p['target_air_yards_missing'] += 1
            else:
                p['air_yards_targeted'] += ay
            if i(r.get('complete_pass')):
                p['receptions'] += 1
                ry, yac = f(r.get('receiving_yards')), f(r.get('yards_after_catch'))
                if ry is None:
                    p['reception_yards_missing'] += 1
                else:
                    p['rec_yards'] += ry
                    per_rec[k].append(ry)
                if yac is None:
                    p['yac_missing'] += 1
                else:
                    p['yac'] += yac
                if ay is not None:
                    p['air_yards_caught'] += ay
                if (ry is not None and yac is not None and ay is not None
                        and abs((ay + yac) - ry) > 1e-6):
                    p['identity_violations'] += 1
                if i(r.get('lateral_reception')):
                    p['lateral_receptions'] += 1
    for k, v in plyr.items():
        d = dict(v)
        # PER-RECEPTION yardage, kept as a list rather than a game mean. A game
        # mean would flatten exactly the tail this study exists to measure:
        # one 70-yard catch and four 3-yard catches is not five 14-yard catches.
        d['rec_yards_list'] = per_rec.get(k, [])
        out[k] = d
    diag[y] = len(plyr)
    print(f'  {y}: {len(plyr)} player-games with >=1 target')
pickle.dump(out, open('recv.pkl', 'wb'))
print(f'wrote recv.pkl  {len(out)} player-games')
