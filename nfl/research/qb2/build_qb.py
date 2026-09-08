"""QB primitives per player-game, on the BINDING QB1 definitions.

    dropbacks = pass_attempts + scrambles - spikes

NOT dropbacks - sacks - scrambles. `pass_attempt` INCLUDES every sack
(5,308/5,308) and every spike (278/278), so the naive form errs by 5,586 plays.

Attribution follows the field that actually carries the player:
  attempts / sacks / spikes / completions   -> passer_player_id
  scrambles / designed rushes               -> rusher_player_id
Scrambles carry NO passer_player_id (0 of 4,091), so a scramble charged to the
passer would be a structurally-zero column -- this project has produced one
already.
"""
import csv, gzip, collections, pickle
csv.field_size_limit(10**7)

def i(v, d=0):
    try: return int(float(v))
    except (TypeError, ValueError): return d
def f(v, d=0.0):
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
            pos = r.get('posteam') or ''
            if not pos:
                continue
            wk = i(r.get('week'))
            tk = (y, wk, pos)
            pas, sack = i(r.get('pass_attempt')), i(r.get('sack'))
            spike, kneel = i(r.get('qb_spike')), i(r.get('qb_kneel'))
            scr, rush = i(r.get('qb_scramble')), i(r.get('rush_attempt'))
            pss = r.get('passer_player_id') or ''
            rus = r.get('rusher_player_id') or ''

            T[tk]['plays'] += 1
            if pas and pss:
                p = P[(y, wk, pos, pss)]
                p['att_raw'] += 1                 # INCLUDES sacks and spikes
                T[tk]['att_raw'] += 1
                if sack:
                    p['sacks'] += 1; T[tk]['sacks'] += 1
                    p['sack_yards'] += f(r.get('yards_gained'))
                if spike:
                    p['spikes'] += 1; T[tk]['spikes'] += 1
                if not sack and not spike:
                    p['attempts'] += 1; T[tk]['attempts'] += 1
                    if i(r.get('complete_pass')):
                        p['completions'] += 1; T[tk]['completions'] += 1
                        p['pass_yards'] += f(r.get('passing_yards'))
                        T[tk]['pass_yards'] += f(r.get('passing_yards'))
                    if i(r.get('pass_touchdown')):
                        p['pass_td'] += 1; T[tk]['pass_td'] += 1
                    if i(r.get('interception')):
                        p['interceptions'] += 1; T[tk]['interceptions'] += 1
            elif pas and not pss and not sack:
                named['pass_attempt_no_passer_id'] += 1
            if rush and rus:
                T[tk]['team_rushes'] += 1
                p = P[(y, wk, pos, rus)]
                if scr:
                    p['scrambles'] += 1; T[tk]['scrambles'] += 1
                elif kneel:
                    named['kneel_excluded_from_designed'] += 1
                else:
                    p['designed_rushes'] += 1
                if not kneel:
                    p['rush_yards'] += f(r.get('rushing_yards'))
                    if i(r.get('rush_touchdown')):
                        p['rush_td'] += 1
            if scr and not rus:
                named['scramble_no_rusher_id'] += 1
    for k, v in P.items():
        d = dict(v)
        # THE BINDING IDENTITY
        d['dropbacks'] = d.get('att_raw', 0) + d.get('scrambles', 0) - d.get('spikes', 0)
        plyr[k] = d
    for k, v in T.items():
        d = dict(v)
        d['dropbacks'] = d.get('att_raw', 0) + d.get('scrambles', 0) - d.get('spikes', 0)
        team[k] = d
    print(f'  {y}: {len(P)} player-games, {len(T)} team-games')
pickle.dump({'player': plyr, 'team': team, 'named': dict(named)},
            open('qb.pkl', 'wb'))
print(f'wrote qb.pkl  {len(plyr)} player-games, {len(team)} team-games')
print('named:', dict(named))
