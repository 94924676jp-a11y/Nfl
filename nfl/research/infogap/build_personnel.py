"""Per-player-game personnel and formation profile, on pass snaps only.

Replicates P1's exact pass-snap join -- participation row x pbp qb_dropback,
excluding two-point plays -- and adds the personnel/formation share the probe
pre-declaration names. Nothing here is a model.
"""
import collections, csv, json, os, pickle, sys
csv.field_size_limit(10 ** 9)
SP = '/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-4781-5a10-ae09-ef74590f8116/scratchpad/p1'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'personnel.pkl')


def i(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def main():
    prof = {}
    for season in range(2020, 2026):
        pbp_key = {}
        with open(f'{SP}/pbp_{season}.csv') as f:
            for r in csv.DictReader(f):
                if r.get('season_type') != 'REG':
                    continue
                pbp_key[(r.get('game_id'), r.get('play_id'))] = (
                    i(r.get('week')), r.get('posteam') or '',
                    i(r.get('qb_dropback')), i(r.get('two_point_attempt')))
        cnt = collections.Counter()
        tot = collections.Counter()
        with open(f'{SP}/part_{season}.csv') as f:
            for r in csv.DictReader(f):
                m = pbp_key.get((r.get('nflverse_game_id'), r.get('play_id')))
                if not m:
                    continue
                wk, pos, db, two = m
                if two or not db or not pos:
                    continue
                pers = r.get('offense_personnel') or ''
                form = (r.get('offense_formation') or '').upper()
                tags = []
                if '3 WR' in pers:
                    tags.append('pers_3wr')
                if '2 TE' in pers:
                    tags.append('pers_2te')
                if '2 RB' in pers:
                    tags.append('pers_2rb')
                if 'SHOTGUN' in form:
                    tags.append('form_shotgun')
                if 'EMPTY' in form:
                    tags.append('form_empty')
                for pid in (r.get('offense_players') or '').split(';'):
                    if not pid:
                        continue
                    k = (season, wk, pos, pid)
                    tot[k] += 1
                    for t in tags:
                        cnt[(k, t)] += 1
        for k, n in tot.items():
            prof[k] = {t: cnt[(k, t)] / n for t in
                       ('pers_3wr', 'pers_2te', 'pers_2rb', 'form_shotgun',
                        'form_empty')}
            prof[k]['n_pass_snaps'] = n
        print(f'  {season}: {len(tot)} player-games profiled')
    pickle.dump(prof, open(OUT, 'wb'), protocol=4)
    print(f'wrote {OUT}  ({len(prof)} player-games)')


main()
