"""Historical DST DK points and NFL game scores from committed nflverse pbp. REG season only.
DK DST: sack 1, INT 2, fumble rec 2, safety 2, def/ST TD 6, blocked kick 2, PA bands 0:+10,1-6:+7,7-13:+4,14-20:+1,
21-27:0,28-34:-1,35+:-4. PA_ALL = opponent final score; PA_EXCL = opponent final minus 6 x opponent def/ST TDs
scored while this club had the ball (pick-six / fumble-six against its offence)."""
import csv, gzip, json, sys, collections, pathlib
REPO = pathlib.Path(__file__).resolve().parents[4]
FILES = {2021: 'pbp_2021.e8743a568f99667a', 2022: 'pbp_2022.0c69a71eb3949895', 2023: 'pbp_2023.4649804ee0f0a40b',
         2024: 'pbp_2024.23370d5d10f8104d', 2025: 'pbp_2025.2f135887790a013f',
         '2026_W1_3': 'pbp_2026.79b02496d26004ee', '2026_W1_4': 'pbp_2026.2b3e9f2c6f92123f'}
def tier(p):
    for lo, hi, v in ((0, 1, 10), (1, 7, 7), (7, 14, 4), (14, 21, 1), (21, 28, 0), (28, 35, -1)):
        if lo <= p < hi: return v
    return -4
out = {}
for label, stem in FILES.items():
    path = REPO / 'nfl/research/postgame' / f'{stem}.csv.gz'
    ev = collections.defaultdict(collections.Counter)
    final, teams, week = {}, {}, {}
    with gzip.open(path, 'rt', newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG': continue
            g = r['game_id']; h, a = r['home_team'], r['away_team']
            teams[g] = (h, a); week[g] = int(r['week'])
            if r.get('home_score') and r.get('away_score'):
                final[g] = (int(float(r['home_score'])), int(float(r['away_score'])))
            pos, dft = r.get('posteam') or '', r.get('defteam') or ''
            if r.get('sack') == '1' and dft: ev[(g, dft)]['sack'] += 1
            if r.get('interception') == '1' and dft: ev[(g, dft)]['int'] += 1
            for fk, rk in (('fumbled_1_team', 'fumble_recovery_1_team'), ('fumbled_2_team', 'fumble_recovery_2_team')):
                f, rc = r.get(fk) or '', r.get(rk) or ''
                if f and rc and f != rc: ev[(g, rc)]['fr'] += 1
            if r.get('safety') == '1' and dft: ev[(g, dft)]['safety'] += 1
            tdt = r.get('td_team') or ''
            if r.get('touchdown') == '1' and tdt:
                offensive = (tdt == pos and (r.get('pass_touchdown') == '1' or r.get('rush_touchdown') == '1')
                             and r.get('return_touchdown') != '1')
                if not offensive:
                    ev[(g, tdt)]['dst_td'] += 1
                    if pos and pos != tdt and r.get('play_type') in ('pass', 'run', 'qb_kneel', 'qb_spike'):
                        ev[(g, tdt)]['td_vs_offence'] += 1     # scored against the other club's offence
            if dft and (r.get('field_goal_result') == 'blocked' or r.get('extra_point_result') == 'blocked'
                        or r.get('punt_blocked') == '1'):
                ev[(g, dft)]['blk'] += 1
    rows = []
    for g, (hs, as_) in final.items():
        h, a = teams[g]
        for club, opp, pa in ((h, a, as_), (a, h, hs)):
            e = ev[(g, club)]
            pa_ex = pa - 6 * ev[(g, opp)]['td_vs_offence']
            comp = e['sack'] + 2 * e['int'] + 2 * e['fr'] + 2 * e['safety'] + 6 * e['dst_td'] + 2 * e['blk']
            rows.append({'game_id': g, 'week': week[g], 'club': club, 'opp': opp, 'pa': pa, 'pa_excl': pa_ex,
                         'sack': e['sack'], 'int': e['int'], 'fr': e['fr'], 'safety': e['safety'], 'dst_td': e['dst_td'],
                         'blk': e['blk'], 'dk_pa_all': comp + tier(pa), 'dk_pa_excl': comp + tier(pa_ex),
                         'dk_no_blk_pa_all': comp - 2 * e['blk'] + tier(pa)})
    games = [{'game_id': g, 'week': week[g], 'home': teams[g][0], 'away': teams[g][1], 'hs': s[0], 'as': s[1]}
             for g, s in final.items()]
    out[str(label)] = {'file': str(path.relative_to(REPO)), 'club_games': rows, 'games': games}
    print(label, len(games), 'games', len(rows), 'club-games', file=sys.stderr)
pathlib.Path(sys.argv[1]).write_text(json.dumps(out))
