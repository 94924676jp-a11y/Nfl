"""Team-by-team role review for a Showdown game, from public nflverse data captured by this machine.

Every rostered skill player and kicker of both clubs gets a row, whether or not he has touched the
ball: a depth piece with no usage is ZERO_OBSERVED_USAGE, never absent. Usage is measured from
play-by-play weeks strictly before this game; availability is the club's own injury report as
nflverse carries it, and the roster status of the current week. Nothing here is a projection.

Inputs are files, each hashed into the output: injuries, depth charts, weekly rosters, snap counts
(nflverse releases) and the latest play-by-play capture under nfl/research/postgame.
"""
from __future__ import annotations

import collections
import csv
import gzip
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
SKILL = ('QB', 'RB', 'FB', 'WR', 'TE', 'K')


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def build(clubs, week, season, *, injuries, depth, rosters, snaps, pbp, out_csv, out_json,
          captured_at):
    clubs = tuple(clubs)
    ro = [r for r in csv.DictReader(open(rosters)) if r['team'] in clubs and r['week'] == str(week)
          and r['position'] in SKILL]
    if not ro:
        raise RuntimeError(f'ROLE_REVIEW_NO_ROSTER for {clubs} week {week}')
    inj = {r['gsis_id']: r for r in csv.DictReader(open(injuries))
           if r['team'] in clubs and r['week'] == str(week)}
    dc_rows = [r for r in csv.DictReader(open(depth)) if r['team'] in clubs]
    latest = max(r['dt'] for r in dc_rows)
    depth_by = {}
    for r in dc_rows:
        if r['dt'] == latest and r['gsis_id']:
            k = r['gsis_id']
            rk = int(r['pos_rank']) if r['pos_rank'].isdigit() else 99
            if k not in depth_by or rk < depth_by[k][1]:
                depth_by[k] = (r['pos_abb'], rk)
    sn = collections.defaultdict(dict)
    pfr_to_name = {}
    for r in csv.DictReader(open(snaps)):
        if r['team'] in clubs and int(r['week']) < week and r['game_type'] == 'REG':
            # keyed by PFR id: names differ between feeds ('Michael Penix Jr.' vs 'Michael Penix')
            sn[(r['team'], r['pfr_player_id'])][int(r['week'])] = (float(r['offense_pct'] or 0),
                                                                   float(r['st_pct'] or 0))
    use = collections.defaultdict(collections.Counter)
    team = collections.defaultdict(collections.Counter)
    weeks_played = collections.defaultdict(set)
    with gzip.open(pbp, 'rt', newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG' or r.get('posteam') not in clubs:
                continue
            if int(r['week']) >= week:
                continue
            c = r['posteam']
            weeks_played[c].add(int(r['week']))
            if r.get('play_type') not in ('pass', 'run') or r.get('two_point_attempt') == '1':
                continue
            yl = float(r['yardline_100']) if r.get('yardline_100') else 99
            rz, gl = yl <= 20, yl <= 5
            third = r.get('down') == '3'
            two_min = (r.get('half_seconds_remaining') and float(r['half_seconds_remaining']) <= 120)
            team[c]['plays'] += 1
            if r.get('pass_attempt') == '1' and r.get('sack') != '1':
                team[c]['pass_att'] += 1
                pid = r.get('passer_player_id')
                if pid:
                    use[pid]['pass_att'] += 1
                    use[pid]['pass_rz'] += rz
                tid = r.get('receiver_player_id')
                if tid:
                    team[c]['targets'] += 1
                    team[c]['rz_targets'] += rz
                    use[tid]['targets'] += 1
                    use[tid]['rz_targets'] += rz
                    use[tid]['third_targets'] += third
                    use[tid]['two_min_targets'] += bool(two_min)
                    use[tid]['air_yards'] += float(r.get('air_yards') or 0)
                    use[tid]['rec'] += r.get('complete_pass') == '1'
                    use[tid]['rec_yards'] += float(r.get('yards_gained') or 0) if r.get('complete_pass') == '1' else 0
                    use[tid]['rec_td'] += r.get('pass_touchdown') == '1'
            if r.get('rush_attempt') == '1':
                rid = r.get('rusher_player_id')
                team[c]['carries'] += 1
                team[c]['rz_carries'] += rz
                team[c]['gl_carries'] += gl
                if rid:
                    use[rid]['carries'] += 1
                    use[rid]['rz_carries'] += rz
                    use[rid]['gl_carries'] += gl
                    use[rid]['rush_yards'] += float(r.get('yards_gained') or 0)
                    use[rid]['rush_td'] += r.get('rush_touchdown') == '1'
    rows = []
    for r in ro:
        g = r['gsis_id']
        c = r['team']
        u = use.get(g, collections.Counter())
        t = team[c]
        i = inj.get(g, {})
        nm = r['full_name']
        s = sn.get((c, r.get('pfr_id')), {})
        wk = sorted(weeks_played[c])
        snap_off = [s.get(w, (None, None))[0] for w in wk]
        snap_st = [s.get(w, (None, None))[1] for w in wk]
        dpos, drank = depth_by.get(g, (None, None))
        touched = u['targets'] + u['carries'] + u['pass_att']
        played = any(x for x in snap_off if x) or any(x for x in snap_st if x)
        row = {
            'club': c, 'player': nm, 'gsis_id': g, 'position': r['position'],
            'roster_status': r['status'], 'roster_status_detail': r.get('status_description_abbr'),
            'injury_report_status': i.get('report_status') or '',
            'injury': i.get('report_primary_injury') or '',
            'practice_status': i.get('practice_status') or '',
            'depth_pos': dpos or '', 'depth_rank': drank if drank is not None else '',
            'games': len(wk),
            'off_snap_pct_by_week': '/'.join('' if x is None else f'{x:.0%}' for x in snap_off),
            'st_snap_pct_by_week': '/'.join('' if x is None else f'{x:.0%}' for x in snap_st),
            'pass_att': u['pass_att'], 'targets': u['targets'],
            'target_share': round(u['targets'] / t['targets'], 4) if t['targets'] else '',
            'rec': u['rec'], 'rec_yards': u['rec_yards'], 'rec_td': u['rec_td'],
            'air_yards': u['air_yards'],
            'carries': u['carries'],
            'carry_share': round(u['carries'] / t['carries'], 4) if t['carries'] else '',
            'rush_yards': u['rush_yards'], 'rush_td': u['rush_td'],
            'rz_targets': u['rz_targets'], 'rz_carries': u['rz_carries'],
            'gl_carries': u['gl_carries'], 'third_down_targets': u['third_targets'],
            'two_min_targets': u['two_min_targets'],
            'usage_state': ('OBSERVED_USAGE' if touched else
                            'PLAYED_NO_TOUCH' if played else 'ZERO_OBSERVED_USAGE'),
        }
        rows.append(row)
    order = {p: i for i, p in enumerate(SKILL)}
    rows.sort(key=lambda x: (x['club'], order[x['position']],
                             x['depth_rank'] if x['depth_rank'] != '' else 99, -x['targets'] - x['carries']))
    with open(out_csv, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    art = {'ARTIFACT': 'SHOWDOWN_ROLE_REVIEW', 'clubs': clubs, 'season': season, 'week': week,
           'usage_weeks': {c: sorted(weeks_played[c]) for c in clubs},
           'team_usage': {c: dict(team[c]) for c in clubs},
           'depth_chart_dt': latest, 'captured_at': captured_at,
           'inputs': {k: {'path': str(v), 'sha256': _sha(v)} for k, v in
                      (('injuries', injuries), ('depth', depth), ('rosters', rosters),
                       ('snaps', snaps), ('pbp', pbp))},
           'n_rows': len(rows),
           'usage_state_counts': dict(collections.Counter(r['usage_state'] for r in rows)),
           'NOT_A_PROJECTION': 'measured usage before this game; projections are a separate artifact'}
    pathlib.Path(out_json).write_text(json.dumps(art, indent=1) + '\n')
    return rows, art
