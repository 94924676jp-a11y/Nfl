"""TD / red-zone primitives per player-game, and per team-game.

AUDITED BEFORE BUILDING, and each decision below is a measured one:

  yardline_100 NULL   13,429 plays 2022-2025. Measured composition (2024):
                      no_play 2,007 and blank play_type 1,371 -- NEVER a live
                      scrimmage play. A null is EXCLUDED, never coerced to 0,
                      because 0 would read as the 1-yard line, i.e. maximum
                      red-zone opportunity.
  TDs that are neither pass, rush nor return: 29 over 2022-2025. Measured:
                      end-zone fumble recoveries and blocked punts/FGs. They
                      are NOT receiving or rushing TDs and are excluded from
                      player TD, but counted in a named bucket.
  qb_scramble w/o rush_attempt: 289; all play_type no_play, penalty-nullified.
  td_team != posteam: 263 -- defensive/return TDs. Excluded from offense.
  no_play / penalty:  excluded from every opportunity denominator.
"""
import csv, gzip, collections, pickle
csv.field_size_limit(10**7)

def i(v, d=0):
    try: return int(float(v))
    except (TypeError, ValueError): return d
def f(v, d=None):
    try: return float(v)
    except (TypeError, ValueError): return d

plyr, team, named = {}, {}, collections.Counter()
for y in (2020, 2021, 2022, 2023, 2024, 2025):
    P = collections.defaultdict(collections.Counter)
    T = collections.defaultdict(collections.Counter)
    with gzip.open(f'pbp{y}.csv.gz', 'rt') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            if i(r.get('two_point_attempt')):
                named['two_point_excluded'] += 1
                continue
            if r.get('play_type') == 'no_play':
                named['no_play_excluded'] += 1
                continue
            if i(r.get('qb_kneel')) or i(r.get('qb_spike')):
                named['kneel_or_spike_excluded'] += 1
                continue
            pos = r.get('posteam') or ''
            if not pos:
                continue
            wk = i(r.get('week'))
            tk = (y, wk, pos)
            y100 = f(r.get('yardline_100'))
            if y100 is None:
                named['yardline_null_excluded'] += 1
                continue                       # never coerced to 0
            rz, in10, in5 = y100 <= 20, y100 <= 10, y100 <= 5
            g2g = i(r.get('goal_to_go'))
            pas, rush = i(r.get('pass_attempt')), i(r.get('rush_attempt'))
            rec = r.get('receiver_player_id') or ''
            rus = r.get('rusher_player_id') or ''
            ptd, rtd = i(r.get('pass_touchdown')), i(r.get('rush_touchdown'))
            tdt = r.get('td_team') or ''
            if i(r.get('touchdown')) and tdt and tdt != pos:
                named['defensive_td_excluded'] += 1
            if i(r.get('touchdown')) and not (ptd or rtd or i(r.get('return_touchdown'))):
                named['recovery_or_blocked_kick_td_excluded'] += 1

            T[tk]['plays'] += 1
            if rz: T[tk]['rz_plays'] += 1
            if in5: T[tk]['in5_plays'] += 1
            if g2g: T[tk]['g2g_plays'] += 1
            if rec and pas:
                T[tk]['targets'] += 1
                p = P[(y, wk, pos, rec)]
                p['targets'] += 1
                if rz: p['rz_targets'] += 1; T[tk]['rz_targets'] += 1
                if in10: p['in10_targets'] += 1
                if in5: p['in5_targets'] += 1
                if g2g: p['g2g_targets'] += 1
                if ptd: p['rec_td'] += 1; T[tk]['rec_td'] += 1
                if ptd and rz: p['rec_td_rz'] += 1
            if rush and rus:
                T[tk]['carries'] += 1
                p = P[(y, wk, pos, rus)]
                p['carries'] += 1
                if i(r.get('qb_scramble')): p['scrambles'] += 1
                else: p['designed_rushes'] += 1
                if rz: p['rz_carries'] += 1; T[tk]['rz_carries'] += 1
                if in10: p['in10_carries'] += 1
                if in5: p['in5_carries'] += 1
                if g2g: p['g2g_carries'] += 1
                if rtd: p['rush_td'] += 1; T[tk]['rush_td'] += 1
                if rtd and rz: p['rush_td_rz'] += 1
    for k, v in P.items(): plyr[k] = dict(v)
    for k, v in T.items(): team[k] = dict(v)
    print(f'  {y}: {len(P)} player-games, {len(T)} team-games')
pickle.dump({'player': plyr, 'team': team, 'named_exclusions': dict(named)},
            open('td.pkl', 'wb'))
print(f'wrote td.pkl  {len(plyr)} player-games, {len(team)} team-games')
print('named exclusions:', dict(named))
