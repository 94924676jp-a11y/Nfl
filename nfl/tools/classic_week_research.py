#!/usr/bin/env python3.12
"""Full-slate player research board for a DraftKings Classic slate, from captured evidence only. Read-only.

    python3.12 nfl/tools/classic_week_research.py RAW_DIR --season 2026 --week 5 --kickoff 2026-10-11T17:00:00Z \
        --out-dir DIR [--news NEWS.json]

Owner directive 2026-10-09 (Week 5 full-slate research). Every row of the third-party export is researched, not just
the expensive or popular players. Each fact on a row names the capture it came from (PROVENANCE.json in RAW_DIR).

THREE KINDS OF STATEMENT, NEVER MIXED
  FACT       read from a capture: roster status, practice participation, depth-chart rank, play-by-play usage, snaps
  ESTIMATE   computed from facts with a stated formula: usage shares, per-game averages, trends
  FLAG       a rule fired on facts or estimates (e.g. QB_REGIME_CHANGE); it is a reason to research, not a conclusion

WHAT THIS IS NOT
  Not a projection. The third-party projection is shown as a benchmark and is never copied, blended or substituted.
  Our own projection comes from the Classic pipeline (classic_slate_pipeline.py), which needs the DK DKEntries export;
  until it exists every row says OUR_PROJECTION_NOT_BUILT -- never a number borrowed from elsewhere.
  Zero is not inactive: a zero third-party projection gets the eligibility screen, not an assumption.

Outputs (DIR): WEEK<N>_FULL_PLAYER_RESEARCH_BOARD.{json,csv}, WEEK<N>_INJURY_AND_ROLE_DEPENDENCY_BOARD.json,
WEEK<N>_QB_REGIME_BOARD.json, WEEK<N>_PROJECTION_DISAGREEMENT_BOARD.json, WEEK<N>_PLAYER_EVIDENCE_LEDGER.json,
WEEK<N>_PROGRESS_BOARD.json.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import io
import json
import pathlib
import re
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import dk_scoring as DKS  # noqa: E402

SKILL = ('QB', 'RB', 'WR', 'TE')
#: rule thresholds, each a flag trigger for research -- never a model coefficient
ROLE_JUMP_PP = 15.0          # snap share moved >= 15 percentage points between the first and last two games
DISAGREE_ABS = 3.0           # third-party projection vs our recent DK average, points
DISAGREE_REL = 0.35


class ResearchError(RuntimeError):
    pass


def need(c, code, detail=''):
    if not c:
        raise ResearchError(f'{code}: {detail}')


def norm(n):
    n = re.sub(r'[\.\']', '', str(n)).lower()
    n = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', n)
    return re.sub(r'\s+', ' ', n).strip()


def _load(raw, kind):
    prov = json.loads((raw / 'PROVENANCE.json').read_text())
    rec = next((f for f in prov['files'] if f['kind'] == kind), None)
    need(rec, 'CAPTURE_MISSING', kind)
    p = _REPO / rec['file'] if not pathlib.Path(rec['file']).is_absolute() else pathlib.Path(rec['file'])
    return p, rec


def load_export(path):
    rows = list(csv.reader(open(path, encoding='utf-8-sig')))
    hi = next(i for i, r in enumerate(rows) if r and r[0] == 'Player')
    h = rows[hi]
    out = [dict(zip(h, r)) for r in rows[hi + 1:] if r and r[0].strip()]
    need(out, 'EMPTY_EXPORT', str(path))
    for need_col in ('Player', 'Pos', 'Team', 'Opp', 'Salary', 'FC Proj', 'Floor', 'Ceiling', 'Inj', 'pDepth'):
        need(need_col in h, 'EXPORT_SCHEMA', need_col)
    return out, hi


def dk_points(r):
    """DK points from one nflverse weekly stat row, by the project's one scorer (bonuses per game)."""
    g = lambda c: float(r.get(c) or 0)  # noqa: E731
    p = float(DKS.skill_points(1, pass_yds=[g('passing_yards')], pass_td=[g('passing_tds')],
                               ints=[g('passing_interceptions')], rush_yds=[g('rushing_yards')],
                               rush_td=[g('rushing_tds')], rec=[g('receptions')], rec_yds=[g('receiving_yards')],
                               rec_td=[g('receiving_tds')],
                               fumbles_lost=[g('rushing_fumbles_lost') + g('receiving_fumbles_lost') + g('sack_fumbles_lost')])[0])
    p += DKS.realised_extra_points(two_pt=g('passing_2pt_conversions') + g('rushing_2pt_conversions')
                                   + g('receiving_2pt_conversions'), return_td=g('special_teams_tds'))
    return round(p, 2)


def build(raw, season, week, kickoff, news=None):
    exp_path, exp_rec = _load(raw, 'FC_CLASSIC_EXPORT_OWNER_UPLOAD')
    export, header_row = load_export(exp_path)
    ros = pd.read_csv(_load(raw, 'NFLVERSE_ROSTER_WEEKLY_2026')[0], low_memory=False)
    inj = pd.read_csv(_load(raw, 'NFLVERSE_INJURIES_2026')[0])
    dep = pd.read_csv(_load(raw, 'NFLVERSE_DEPTH_CHARTS_2026_LATEST')[0])
    snp = pd.read_csv(_load(raw, 'NFLVERSE_SNAP_COUNTS_2026')[0])
    stw = pd.read_csv(_load(raw, 'NFLVERSE_STATS_PLAYER_WEEK_2026')[0], low_memory=False)
    gms = pd.read_csv(_load(raw, 'NFLVERSE_GAMES_2026')[0])
    pbp = pd.read_csv(_load(raw, 'NFLVERSE_PBP_2026')[0], low_memory=False)

    teams = sorted({r['Team'] for r in export})
    wk = gms[(gms.season == season) & (gms.week == week) & (gms.home_team.isin(teams) | gms.away_team.isin(teams))]
    need(len(wk) == len(teams) // 2, 'SLATE_GAMES_MISMATCH', f'{len(wk)} schedule games for {len(teams)} export teams')
    need(wk.home_score.isna().all(), 'SLATE_CONTAINS_A_PLAYED_GAME', str(wk[wk.home_score.notna()].game_id.tolist()))
    sched = {}
    for g in wk.itertuples():
        for t, o, home in ((g.home_team, g.away_team, True), (g.away_team, g.home_team, False)):
            sched[t] = {'game_id': g.game_id, 'opp': o, 'home': home, 'gameday': g.gameday, 'gametime_et': g.gametime,
                        'roof': g.roof, 'rest_days': int(g.home_rest if home else g.away_rest),
                        'nflverse_listed_qb': g.home_qb_name if home else g.away_qb_name,
                        'spread_line_home_minus': g.spread_line, 'total_line': g.total_line}
    for r in export:
        o = r['Opp'].replace('@', '').replace('vs', '').strip()
        need(sched.get(r['Team'], {}).get('opp') == o, 'EXPORT_OPPONENT_DISAGREES_WITH_SCHEDULE', f"{r['Player']} {r['Team']} {o}")

    r5 = ros[(ros.week == week)]
    by_nt = {(norm(x.full_name), x.team): x for x in r5.itertuples()}
    inj5 = inj[inj.week == week]
    inj_by = {x.gsis_id: x for x in inj5.itertuples()}
    dep_by = collections.defaultdict(list)
    for x in dep.itertuples():
        dep_by[x.gsis_id].append(x)

    # play-by-play usage, regular season, weeks before this one
    p = pbp[(pbp.season_type == 'REG') & (pbp.week < week) & (pbp.two_point_attempt.fillna(0) != 1)]
    p = p[p.posteam.isin(teams)]
    tgt = p[p.receiver_player_id.notna()].groupby(['posteam', 'week', 'receiver_player_id']).size()
    car = p[(p.rush_attempt == 1) & p.rusher_player_id.notna()].groupby(['posteam', 'week', 'rusher_player_id']).size()
    rz = p[(p.yardline_100 <= 20)]
    rzt = rz[rz.receiver_player_id.notna()].groupby(['posteam', 'receiver_player_id']).size()
    rzc = rz[(rz.rush_attempt == 1) & rz.rusher_player_id.notna()].groupby(['posteam', 'rusher_player_id']).size()
    team_t = p[p.receiver_player_id.notna()].groupby(['posteam', 'week']).size()
    team_c = p[(p.rush_attempt == 1)].groupby(['posteam', 'week']).size()
    passers = p[(p.pass_attempt == 1) & (p.sack != 1) & p.passer_player_name.notna()]
    qb_week = passers.groupby(['posteam', 'week']).passer_player_name.agg(lambda s: s.value_counts().to_dict())

    # QB regime per club
    qb_board = {}
    for t in teams:
        wks = {int(w): d for (tm, w), d in qb_week.items() if tm == t}
        leaders = {w: max(d, key=d.get) for w, d in wks.items()}
        listed = sched[t]['nflverse_listed_qb']
        dom = collections.Counter(leaders.values()).most_common(1)[0][0] if leaders else None
        listed_short = (listed.split(' ')[0][0] + '.' + ' '.join(listed.split(' ')[1:])) if isinstance(listed, str) else None
        starts = sum(1 for v in leaders.values() if listed_short and v.replace(' ', '') == listed_short.replace(' ', ''))
        flags = []
        if listed_short and dom and dom.replace(' ', '') != listed_short.replace(' ', ''):
            flags.append('QB_REGIME_CHANGE: listed starter is not the dominant passer of the modelling window')
        if listed_short and starts <= 1:
            flags.append(f'THIN_STARTER_EVIDENCE: {starts} 2026 start(s) by the listed starter')
        if leaders and listed_short:
            last = leaders[max(leaders)]
            if last.replace(' ', '') != listed_short.replace(' ', ''):
                flags.append(f'QB_DIFFERS_FROM_LAST_GAME: week {max(leaders)} passer {last}, listed {listed}')
            n_distinct = len(set(leaders.values()))
            if n_distinct >= 3:
                flags.append(f'QB_CHURN: {n_distinct} different attempt leaders in {len(leaders)} games')
        qb_board[t] = {'listed_starter_nflverse_schedule': listed, 'attempt_leader_by_week': leaders,
                       'attempts_by_week': {w: d for w, d in sorted(wks.items())}, 'dominant_passer': dom,
                       'listed_starter_2026_starts': starts, 'flags': flags,
                       'IS_NOT': 'nflverse schedule qb fields are a listing, not a team announcement; confirm with news'}

    snp_by = collections.defaultdict(dict)
    for x in snp[snp.week < week].itertuples():
        snp_by[(norm(x.player), x.team)][int(x.week)] = float(x.offense_pct) * 100
    st_by = collections.defaultdict(dict)
    for x in stw[(stw.season_type == 'REG') & (stw.week < week)].to_dict('records'):
        st_by[x['player_id']][int(x['week'])] = x

    rows, ledger = [], {}
    for r in export:
        name, team, pos = r['Player'].strip(), r['Team'], r['Pos']
        fc = float(r['FC Proj'] or 0)
        row = {'player': name, 'team': team, 'pos': pos, 'opp': sched[team]['opp'], 'home': sched[team]['home'],
               'game_id': sched[team]['game_id'], 'kickoff_et': f"{sched[team]['gameday']} {sched[team]['gametime_et']}",
               'salary': int(r['Salary']), 'fc_proj': fc, 'fc_floor': float(r['Floor'] or 0),
               'fc_ceiling': float(r['Ceiling'] or 0), 'fc_stdv': float(r.get('STDV') or 0), 'fc_depth_tag': r['pDepth'],
               'fc_injury_flag': r['Inj'] or None, 'positive_projection': fc > 0,
               'our_projection': 'OUR_PROJECTION_NOT_BUILT (Classic pipeline needs the DK DKEntries export)',
               'facts': {}, 'estimates': {}, 'flags': []}
        if pos == 'DST':
            row['identity'] = {'status': 'TEAM_DEFENCE', 'gsis_id': None}
            row['eligibility'] = 'ELIGIBLE_BY_CONSTRUCTION'
            dinj = inj5[(inj5.team == team) & ~inj5.position.isin(SKILL + ('K',))]
            row['facts']['defensive_players_on_injury_report'] = [
                f'{x.full_name} ({x.position}): {x.practice_status}' for x in dinj.itertuples()]
            rows.append(row)
            continue
        m = by_nt.get((norm(name), team))
        if m is None:
            cands = [x for (n, t), x in by_nt.items() if t == team and n.split(' ')[-1] == norm(name).split(' ')[-1]
                     and n[:1] == norm(name)[:1]]
            m = cands[0] if len(cands) == 1 else None
        if m is None:
            row['identity'] = {'status': 'IDENTITY_NOT_ESTABLISHED', 'gsis_id': None}
            row['eligibility'] = 'UNVERIFIED (no week-roster identity)'
            row['flags'].append('IDENTITY_UNRESOLVED')
            rows.append(row)
            continue
        gid = m.gsis_id
        row['identity'] = {'status': 'MATCHED', 'gsis_id': gid, 'roster_name': m.full_name, 'roster_position': m.position,
                           'years_exp': None if pd.isna(m.years_exp) else int(m.years_exp)}
        row['facts']['roster_status_week'] = m.status
        e = {'ACT': 'ELIGIBLE (ACT)', 'DEV': 'NOT_ELIGIBLE_UNLESS_ELEVATED (practice squad)',
             'RES': 'NOT_ELIGIBLE (reserve: IR/PUP/NFI/suspended)'}.get(m.status, f'NOT_ELIGIBLE ({m.status})')
        ij = inj_by.get(gid)
        if ij is not None:
            row['facts']['practice_status_latest'] = ij.practice_status
            row['facts']['injury'] = ', '.join(str(x) for x in (ij.practice_primary_injury, ij.practice_secondary_injury)
                                                if isinstance(x, str))
            row['facts']['game_designation'] = ij.report_status if isinstance(ij.report_status, str) else \
                'NOT_YET_ISSUED (designations are issued Friday; absence is not health)'
            if isinstance(ij.practice_status, str) and ij.practice_status.startswith('Did Not'):
                row['flags'].append('DID_NOT_PRACTICE')
        row['eligibility'] = e
        if not e.startswith('ELIGIBLE') and fc > 0:
            row['flags'].append('POSITIVE_PROJECTION_BUT_NOT_ON_ACTIVE_ROSTER')
        dp = [d for d in dep_by.get(gid, []) if d.pos_abb in (pos, 'QB', 'RB', 'WR', 'TE')]
        if dp:
            row['facts']['depth_chart'] = sorted({f'{d.pos_abb}{int(d.pos_rank)}' for d in dp})
            row['facts']['depth_chart_dt'] = dp[0].dt
        else:
            row['facts']['depth_chart'] = 'NOT_ON_LATEST_DEPTH_CHART'
        # usage
        wks = sorted({int(w) for (tm, w, pid) in tgt.index if tm == team} | {int(w) for (tm, w, pid) in car.index if tm == team})
        u = {}
        for w in wks:
            t_ = int(tgt.get((team, w, gid), 0))
            c_ = int(car.get((team, w, gid), 0))
            u[w] = {'targets': t_, 'carries': c_,
                    'target_share': round(t_ / int(team_t.get((team, w), 1)), 3),
                    'carry_share': round(c_ / int(team_c.get((team, w), 1)), 3),
                    'snap_pct': snp_by.get((norm(name), team), {}).get(w),
                    'dk_points': dk_points(st_by[gid][w]) if w in st_by.get(gid, {}) else 0.0,
                    'played': w in st_by.get(gid, {}) or snp_by.get((norm(name), team), {}).get(w) is not None}
        row['facts']['usage_by_week'] = u
        played = [w for w in wks if u[w]['played']]
        if wks and played and max(wks) not in played:
            row['flags'].append(f'MISSED_LAST_GAME: no participation in week {max(wks)}')
        if played:
            dk = [u[w]['dk_points'] for w in played]
            row['estimates'].update({
                'games_played_2026': len(played), 'dk_avg_2026': round(float(np.mean(dk)), 2),
                'dk_last_game': u[played[-1]]['dk_points'], 'last_game_week': played[-1],
                'target_share_avg': round(float(np.mean([u[w]['target_share'] for w in played])), 3),
                'carry_share_avg': round(float(np.mean([u[w]['carry_share'] for w in played])), 3),
                'red_zone_targets_2026': int(rzt.get((team, gid), 0)), 'red_zone_carries_2026': int(rzc.get((team, gid), 0))})
            sp = [u[w]['snap_pct'] for w in played if u[w]['snap_pct'] is not None]
            if len(sp) >= 3:
                d = float(np.mean(sp[-2:]) - np.mean(sp[:2]))
                row['estimates']['snap_trend_pp'] = round(d, 1)
                if abs(d) >= ROLE_JUMP_PP:
                    row['flags'].append(f'ROLE_CHANGE: snap share {"up" if d > 0 else "down"} {abs(d):.0f} pp')
            avg = row['estimates']['dk_avg_2026']
            if fc > 0 and (abs(fc - avg) >= DISAGREE_ABS and abs(fc - avg) / max(avg, 1) >= DISAGREE_REL):
                row['flags'].append(f'FC_VS_RECENT_PRODUCTION: FC {fc} vs 2026 DK avg {avg}')
        elif fc > 0:
            row['flags'].append('NO_2026_REGULAR_SEASON_PRODUCTION_ON_RECORD')
        if pos == 'QB':
            row['facts']['club_qb_regime'] = qb_board[team]
            if qb_board[team]['flags']:
                row['flags'] += qb_board[team]['flags']
        if fc == 0:
            row['zero_projection_screen'] = (
                'RESERVE_OR_INACTIVE' if m.status == 'RES' else
                'PRACTICE_SQUAD' if m.status == 'DEV' else
                'NOT_ACT_' + str(m.status) if m.status != 'ACT' else
                'ACTIVE_CONTINGENT_OPPORTUNITY' if (row['estimates'].get('games_played_2026') or 0) > 0 else
                'ACTIVE_NO_2026_USAGE')
        rows.append(row)
        ledger[f'{name}|{team}'] = {'identity': row['identity'], 'roster': 'NFLVERSE_ROSTER_WEEKLY_2026',
                                    'injury': 'NFLVERSE_INJURIES_2026' if ij is not None else None,
                                    'depth': 'NFLVERSE_DEPTH_CHARTS_2026_LATEST', 'usage': ['NFLVERSE_PBP_2026',
                                    'NFLVERSE_SNAP_COUNTS_2026', 'NFLVERSE_STATS_PLAYER_WEEK_2026']}

    # dependency board: each club's skill players who are not plainly available, and who inherits the role
    dep_board = {}
    for t in teams:
        tr = [x for x in rows if x['team'] == t and x['pos'] in SKILL]
        events = []
        for x in tr:
            st_ = x['facts'].get('practice_status_latest')
            bad = (x['eligibility'] != 'ELIGIBLE (ACT)') or (isinstance(st_, str) and not st_.startswith('Full'))
            share = (x['estimates'].get('target_share_avg') or 0) + (x['estimates'].get('carry_share_avg') or 0)
            if bad and share >= 0.08:
                mates = sorted((y for y in tr if y['pos'] == x['pos'] and y is not x),
                               key=lambda y: -((y['estimates'].get('target_share_avg') or 0) + (y['estimates'].get('carry_share_avg') or 0)))
                events.append({'player': x['player'], 'pos': x['pos'], 'status': x['eligibility'],
                               'practice': st_, 'usage_share_2026': round(share, 3),
                               'same_position_teammates': [(y['player'], y['estimates'].get('target_share_avg'),
                                                            y['estimates'].get('carry_share_avg'), y['fc_proj']) for y in mates[:4]],
                               'also_affects': ['QB passing volume/efficiency' if x['pos'] in ('WR', 'TE') else
                                                'RB workload split' if x['pos'] == 'RB' else 'every pass catcher'],
                               'ENGINE_CONSUMES': 'availability -> opportunity redistribution exists (redistribution.py); '
                                                  'QB-conditioned shares do NOT (D-02/D-04)'})
        dinj = [f"{x['player']}" for x in rows if x['team'] == sched[t]['opp'] and x['pos'] == 'DST']
        dep_board[t] = {'opponent': sched[t]['opp'], 'skill_events': events, 'qb_flags': qb_board[t]['flags'],
                        'opponent_defence_injuries': next((x['facts'].get('defensive_players_on_injury_report')
                                                           for x in rows if x['team'] == sched[t]['opp'] and x['pos'] == 'DST'), [])}
    disagree = sorted(({'player': x['player'], 'team': x['team'], 'pos': x['pos'], 'fc_proj': x['fc_proj'],
                        'dk_avg_2026': x['estimates'].get('dk_avg_2026'), 'dk_last_game': x['estimates'].get('dk_last_game'),
                        'gap_fc_minus_avg': round(x['fc_proj'] - (x['estimates'].get('dk_avg_2026') or 0), 2),
                        'our_projection': 'NOT_BUILT', 'flags': x['flags']}
                       for x in rows if x['positive_projection'] and x['pos'] != 'DST'),
                      key=lambda r: -abs(r['gap_fc_minus_avg']))
    progress = {
        'rows_total': len(rows), 'positive_projection_rows': sum(1 for x in rows if x['positive_projection']),
        'zero_projection_rows': sum(1 for x in rows if not x['positive_projection']),
        'identities_unresolved': [f"{x['player']}|{x['team']}" for x in rows if x['identity']['status'] == 'IDENTITY_NOT_ESTABLISHED'],
        'positive_projection_not_eligible': [f"{x['player']}|{x['team']} ({x['eligibility']})" for x in rows
                                             if x['positive_projection'] and not str(x['eligibility']).startswith('ELIGIBLE')],
        'did_not_practice_positive': [f"{x['player']}|{x['team']}" for x in rows if x['positive_projection'] and 'DID_NOT_PRACTICE' in x['flags']],
        'qb_regime_flags': {t: v['flags'] for t, v in qb_board.items() if v['flags']},
        'role_change_flags': [f"{x['player']}|{x['team']}: {f}" for x in rows for f in x['flags'] if f.startswith('ROLE_CHANGE')],
        'missed_last_game_positive': [f"{x['player']}|{x['team']}" for x in rows if x['positive_projection']
                                      and any(f.startswith('MISSED_LAST_GAME') for f in x['flags'])],
        'awaiting_evidence': ['Friday game designations', 'official inactives (~11:30 ET Sunday)', 'confirmed starters',
                              'weather on game day', 'DK DKEntries export (ids, contests) for our own projections'],
        'zero_projection_screen': dict(collections.Counter(x.get('zero_projection_screen') for x in rows
                                                           if not x['positive_projection'] and x['pos'] != 'DST'))}
    meta = {'season': season, 'week': week, 'kickoff_utc': kickoff, 'export': exp_rec, 'export_header_row_index': header_row,
            'slate_games': sorted({v['game_id'] for v in sched.values()}), 'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'news_supplement': news}
    return {'meta': meta, 'rows': rows, 'qb_board': qb_board, 'dependency_board': dep_board, 'disagreement': disagree,
            'ledger': ledger, 'progress': progress, 'schedule': sched}


def write(doc, out, week):
    out.mkdir(parents=True, exist_ok=True)
    W = f'WEEK{week}'
    (out / f'{W}_FULL_PLAYER_RESEARCH_BOARD.json').write_text(json.dumps({'meta': doc['meta'], 'schedule': doc['schedule'],
                                                                         'rows': doc['rows']}, indent=1, default=str) + '\n')
    flat = ['player', 'team', 'pos', 'opp', 'kickoff_et', 'salary', 'fc_proj', 'fc_floor', 'fc_ceiling', 'fc_depth_tag',
            'fc_injury_flag', 'eligibility', 'roster_status', 'practice', 'injury', 'depth_chart', 'games_2026',
            'dk_avg_2026', 'dk_last_game', 'target_share', 'carry_share', 'rz_targets', 'rz_carries', 'snap_trend_pp',
            'zero_screen', 'flags', 'our_projection']
    with (out / f'{W}_FULL_PLAYER_RESEARCH_BOARD.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(flat)
        for x in sorted(doc['rows'], key=lambda r: (-r['fc_proj'], r['team'])):
            F, E = x['facts'], x['estimates']
            w.writerow([x['player'], x['team'], x['pos'], x['opp'], x['kickoff_et'], x['salary'], x['fc_proj'], x['fc_floor'],
                        x['fc_ceiling'], x['fc_depth_tag'], x['fc_injury_flag'] or '', x['eligibility'],
                        F.get('roster_status_week', ''), F.get('practice_status_latest', ''), F.get('injury', ''),
                        ' '.join(F['depth_chart']) if isinstance(F.get('depth_chart'), list) else F.get('depth_chart', ''),
                        E.get('games_played_2026', ''), E.get('dk_avg_2026', ''), E.get('dk_last_game', ''),
                        E.get('target_share_avg', ''), E.get('carry_share_avg', ''), E.get('red_zone_targets_2026', ''),
                        E.get('red_zone_carries_2026', ''), E.get('snap_trend_pp', ''), x.get('zero_projection_screen', ''),
                        ' | '.join(x['flags']), 'NOT_BUILT'])
    for name, key in (('INJURY_AND_ROLE_DEPENDENCY_BOARD', 'dependency_board'), ('QB_REGIME_BOARD', 'qb_board'),
                      ('PROJECTION_DISAGREEMENT_BOARD', 'disagreement'), ('PLAYER_EVIDENCE_LEDGER', 'ledger'),
                      ('PROGRESS_BOARD', 'progress')):
        (out / f'{W}_{name}.json').write_text(json.dumps({'meta': doc['meta'], name: doc[key]}, indent=1, default=str) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('raw_dir')
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--kickoff', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--news')
    a = ap.parse_args(argv)
    news = json.loads(pathlib.Path(a.news).read_text()) if a.news else None
    try:
        doc = build(pathlib.Path(a.raw_dir), a.season, a.week, a.kickoff, news)
    except ResearchError as e:
        print(f'REFUSED {e}')
        return 4
    write(doc, pathlib.Path(a.out_dir), a.week)
    print(json.dumps(doc['progress'], indent=1, default=str)[:4000])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
