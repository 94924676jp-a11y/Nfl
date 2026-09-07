"""P4 team-game panel: one row per (season, week, team) with volume targets.

DENOMINATORS ARE STATED, NOT ASSUMED. P1 already lost a result to
`pass_attempt` silently including sacks, so every count below names what it
counts and the shares are built from those counts rather than from a pbp column
whose semantics were guessed.

xPASS IS REBUILT, NOT BORROWED. nflfastR ships `xpass` and `pass_oe`, and their
fitting window is not documented in the artifact -- it may include the seasons
being evaluated. They are quarantined. This module writes the play-state
primitives needed to fit xPass ourselves on prior seasons only.
"""
import collections, csv, json, os, sys
csv.field_size_limit(10**9)

P1 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '..', 'p1'))
HERE = os.path.dirname(os.path.abspath(__file__))
SEASONS = list(range(2016, 2026))


def i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def f(v, d=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def build(season):
    team = collections.defaultdict(collections.Counter)
    pace = collections.defaultdict(list)
    plays_out = []                      # play-state rows for the xPass fit
    qb_rush = collections.defaultdict(collections.Counter)
    passers = collections.defaultdict(collections.Counter)

    prev_secs = {}
    for r in csv.DictReader(open(f'{P1}/pbp_{season}.csv')):
        if r.get('season_type') != 'REG':
            continue
        pos = r.get('posteam') or ''
        if not pos:
            continue
        if i(r.get('two_point_attempt')):
            continue
        pt = r.get('play_type') or ''
        db = i(r.get('qb_dropback'))
        rush = i(r.get('rush_attempt'))
        pa = i(r.get('pass_attempt'))
        sk = i(r.get('sack'))
        scr = i(r.get('qb_scramble'))
        if not (db or rush or pa):
            continue                    # kneels, spikes, specials, no-plays
        wk = i(r.get('week'))
        key = (wk, pos)
        t = team[key]
        t['plays'] += 1
        t['dropbacks'] += db
        t['pass_att_ex_sacks'] += 1 if (pa and not sk) else 0
        t['sacks'] += sk
        t['scrambles'] += scr
        t['rush_att'] += rush
        down = i(r.get('down'))
        sd = f(r.get('score_differential'), 0.0) or 0.0
        qtr = i(r.get('qtr'))
        gsr = f(r.get('game_seconds_remaining'), 0.0) or 0.0
        neutral = abs(sd) <= 8 and qtr <= 3 and down in (1, 2)
        if neutral:
            t['neutral_plays'] += 1
            t['neutral_dropbacks'] += db
        if down in (1, 2):
            t['early_plays'] += 1
            t['early_dropbacks'] += db
        if qtr <= 2:
            t['h1_plays'] += 1
            t['h1_dropbacks'] += db
        # pace: seconds between consecutive plays by the same team, neutral only
        p = prev_secs.get(key)
        if p is not None and neutral and 0 < p - gsr < 60:
            pace[key].append(p - gsr)
        prev_secs[key] = gsr
        # QB rushes: designed vs scramble
        rid = r.get('rusher_player_id') or ''
        pid = r.get('passer_player_id') or ''
        if pid and db:
            passers[key][pid] += 1
        if rush and rid:
            qb_rush[key][rid] += 1
            if scr:
                t['scramble_rush'] += 1
        # play-state row for the xPass reconstruction
        if down in (1, 2, 3, 4):
            plays_out.append((season, wk, pos, down,
                              f(r.get('ydstogo'), 10.0) or 10.0,
                              f(r.get('yardline_100'), 50.0) or 50.0,
                              sd, gsr, 1 if qtr <= 2 else 0,
                              i(r.get('posteam_timeouts_remaining'), 3), db))
    return team, pace, plays_out, qb_rush, passers


def main():
    import statistics
    schedules = {}
    import glob, gzip, io
    sfile = sorted(glob.glob('/home/user/nfl/nfl/vintage/schedules.*.csv.gz'))[-1]
    for r in csv.DictReader(io.StringIO(gzip.open(sfile, 'rt').read())):
        if r.get('game_type') != 'REG':
            continue
        s, w = i(r.get('season')), i(r.get('week'))
        for side, opp in (('home', 'away'), ('away', 'home')):
            schedules[(s, w, r[f'{side}_team'])] = {
                'opponent': r[f'{opp}_team'],
                'coach': r.get(f'{side}_coach'),
                'qb_id': r.get(f'{side}_qb_id'),
                'qb_name': r.get(f'{side}_qb_name'),
                'rest': i(r.get(f'{side}_rest'), 7),
                'home': 1 if side == 'home' else 0,
                'div_game': i(r.get('div_game')),
                'roof': r.get('roof'), 'surface': r.get('surface'),
                'gameday': r.get('gameday'),
            }
    print(f'schedule rows: {len(schedules)}')

    rows, all_plays = [], []
    for s in SEASONS:
        if not os.path.exists(f'{P1}/pbp_{s}.csv'):
            print(f'skip {s}')
            continue
        team, pace, plays, qb_rush, passers = build(s)
        all_plays.extend(plays)
        for (wk, pos), t in sorted(team.items()):
            meta = schedules.get((s, wk, pos), {})
            qb = meta.get('qb_id')
            designed = sum(v for k, v in qb_rush[(wk, pos)].items()
                           if k == qb) - t['scramble_rush'] \
                if qb in qb_rush[(wk, pos)] else 0
            designed = max(designed, 0)
            row = {
                'season': s, 'week': wk, 'team': pos,
                'ord': s * 100 + wk,
                'plays': t['plays'], 'dropbacks': t['dropbacks'],
                'pass_att_ex_sacks': t['pass_att_ex_sacks'],
                'sacks': t['sacks'], 'scrambles': t['scrambles'],
                'rush_att': t['rush_att'],
                'designed_qb_rush': designed,
                'nonqb_rush_att': max(t['rush_att'] - t['scrambles'] - designed, 0),
                'neutral_plays': t['neutral_plays'],
                'neutral_dropbacks': t['neutral_dropbacks'],
                'early_plays': t['early_plays'],
                'early_dropbacks': t['early_dropbacks'],
                'h1_plays': t['h1_plays'], 'h1_dropbacks': t['h1_dropbacks'],
                'sec_per_play': (round(statistics.mean(pace[(wk, pos)]), 3)
                                 if len(pace[(wk, pos)]) >= 5 else ''),
                'n_pace_obs': len(pace[(wk, pos)]),
                **{k: meta.get(k, '') for k in
                   ('opponent', 'coach', 'qb_id', 'qb_name', 'rest', 'home',
                    'div_game', 'roof', 'surface', 'gameday')},
            }
            row['pass_rate'] = (row['dropbacks'] / row['plays']
                                if row['plays'] else '')
            row['neutral_pass_rate'] = (
                row['neutral_dropbacks'] / row['neutral_plays']
                if row['neutral_plays'] >= 10 else '')
            row['early_down_pass_rate'] = (
                row['early_dropbacks'] / row['early_plays']
                if row['early_plays'] >= 10 else '')
            rows.append(row)
        print(f'{s}: {len(team)} team-games', flush=True)

    with open(f'{HERE}/team_panel.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    import numpy as np
    arr = np.array(all_plays, dtype=object)
    np.save(f'{HERE}/play_state.npy', arr, allow_pickle=True)
    print(f'wrote team_panel.csv: {len(rows)} team-games; '
          f'play_state.npy: {len(all_plays)} plays')


if __name__ == '__main__':
    main()
