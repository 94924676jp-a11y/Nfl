#!/usr/bin/env python3.12
"""Individual player research records for every positively projected row of a Classic research board. Read-only.

    python3.12 nfl/tools/classic_player_records.py BOARD_DIR --week 5 [--news NEWS.json]

Each record keeps three kinds of statement apart -- CONFIRMED FACTS (captures), ESTIMATES (computed from captures)
and REPORTED NEWS (web-search supplement, with its own CONFIRMED/REPORTED/CONFLICTING tag and source URLs) -- and adds:
  what drives his production this week   the opportunity facts (share, role, red zone) and the environment that sets
                                          volume (QB, teammates out, game total, weather), stated from the facts
  dependencies                           the teammates whose availability moves his opportunity, from the board
  missing model dependencies             which of those the engine does not consume (per the gap register)
  recommended research action            specific, from the flags
Nothing is invented: a field with no evidence says so. No record changes a projection.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

SKILL = ('QB', 'RB', 'WR', 'TE')


def _news_for(news, name, team):
    if not news:
        return []
    out = []
    t = (news.get('teams') or {}).get(team) or {}
    last = name.split(' ')[-1].replace('.', '')
    pat = re.compile(r'\b' + re.escape(last) + r'\b')
    for k in ('qb', 'injuries', 'transactions', 'role_news'):
        v = t.get(k) or []
        for x in (v if isinstance(v, list) else [v]):
            if x and pat.search(str(x.get('fact', ''))):
                out.append({'kind': k, 'status': x.get('status'), 'fact': x.get('fact'),
                            'sources': [s.get('url') for s in (x.get('sources') or [])][:3]})
    return out


def _drivers(r, sched, team_rows, qb):
    E, F = r['estimates'], r['facts']
    d = []
    if r['pos'] in ('WR', 'TE', 'RB') and E.get('target_share_avg') is not None:
        d.append(f"2026 target share {E['target_share_avg']:.0%}" + (f", carry share {E['carry_share_avg']:.0%}"
                                                                     if E.get('carry_share_avg') else ''))
    if r['pos'] == 'RB' and E.get('carry_share_avg') is not None and not E.get('target_share_avg'):
        d.append(f"2026 carry share {E['carry_share_avg']:.0%}")
    if E.get('red_zone_targets_2026') or E.get('red_zone_carries_2026'):
        d.append(f"red zone 2026: {E.get('red_zone_targets_2026', 0)} targets, {E.get('red_zone_carries_2026', 0)} carries")
    if E.get('snap_trend_pp') is not None:
        d.append(f"snap share trend {E['snap_trend_pp']:+.0f} pp (last 2 vs first 2 games)")
    g = sched
    d.append(f"game total {g.get('total_line')} (nflverse schedule line), {'home' if g.get('home') else 'away'}, "
             f"roof {g.get('roof')}, rest {g.get('rest_days')} days")
    d.append(f"club QB: {qb.get('listed_starter_nflverse_schedule')} (attempt leaders by week {qb.get('attempt_leader_by_week')})")
    out_mates = [x['player'] for x in team_rows if x is not r and x['pos'] in SKILL
                 and ('DID_NOT_PRACTICE' in x['flags'] or any(f.startswith('MISSED_LAST_GAME') for f in x['flags']))]
    if out_mates:
        d.append('teammates with availability doubt: ' + ', '.join(out_mates[:6]))
    return d


def _missing(r, qb):
    m = []
    if qb.get('flags'):
        m.append('QB-conditioned team volume / shares NOT consumed by the engine (W5-G1)')
    if r['pos'] == 'QB' and qb.get('flags'):
        m.append('QB rushing from a generic cohort prior, starts pooled with relief (D-03)')
    if any(f.startswith('ROLE_CHANGE') for f in r['flags']):
        m.append('4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8)')
    if 'DID_NOT_PRACTICE' in r['flags'] or (r['facts'].get('practice_status_latest') or '').startswith('Limited'):
        m.append('practice participation does not change a projection until a designation; no partial-workload model (W5-G4)')
    m.append('lower-tail volatility under-stated for high-mean players (D-01)' if r['fc_proj'] >= 15 else
             'accounting repair pending (D-05) affects all players')
    return m


def _actions(r):
    a = []
    for f in r['flags']:
        if f.startswith('QB_'):
            a.append('confirm the starter from a team source; run the QB shadow candidate for this club')
        elif f == 'DID_NOT_PRACTICE':
            a.append('capture Friday designation; if OUT, check redistribution to same-position teammates')
        elif f.startswith('MISSED_LAST_GAME'):
            a.append('verify return status and any snap limit; compare to pre-injury usage')
        elif f.startswith('ROLE_CHANGE'):
            a.append('read the last two games: is the snap change a role change, an injury exit or game script?')
        elif f.startswith('FC_VS_RECENT'):
            a.append('decompose FC vs recent production: volume, efficiency or availability assumption')
        elif f == 'NO_2026_REGULAR_SEASON_PRODUCTION_ON_RECORD':
            a.append('establish role: rookie, returning, or depth player; FC basis unknown')
    return sorted(set(a)) or ['no flag fired; re-check after Friday designations and Sunday inactives']


def build(board_dir, week, news=None):
    bd = pathlib.Path(board_dir)
    W = f'WEEK{week}'
    b = json.loads((bd / f'{W}_FULL_PLAYER_RESEARCH_BOARD.json').read_text())
    qbb = json.loads((bd / f'{W}_QB_REGIME_BOARD.json').read_text())['QB_REGIME_BOARD']
    rows, sched = b['rows'], b['schedule']
    recs = []
    for r in sorted((x for x in rows if x['positive_projection']), key=lambda x: (x['team'], -x['fc_proj'])):
        team_rows = [x for x in rows if x['team'] == r['team']]
        qb = qbb.get(r['team'], {})
        facts = {k: v for k, v in r['facts'].items() if k not in ('usage_by_week', 'club_qb_regime')}
        rec = {'player': r['player'], 'team': r['team'], 'opp': r['opp'], 'pos': r['pos'], 'salary': r['salary'],
               'kickoff_et': r['kickoff_et'], 'identity': r['identity'], 'eligibility': r['eligibility'],
               'benchmark_fc': {'proj': r['fc_proj'], 'floor': r['fc_floor'], 'ceiling': r['fc_ceiling'],
                                'depth_tag': r['fc_depth_tag'], 'injury_flag': r['fc_injury_flag']},
               'our_projection': r['our_projection'],
               'confirmed_facts': facts,
               'usage_by_week': r['facts'].get('usage_by_week'),
               'estimates': r['estimates'],
               'reported_news': _news_for(news, r['player'], r['team']),
               'what_drives_production': _drivers(r, sched[r['team']], team_rows, qb) if r['pos'] != 'DST' else
               [f"opponent {r['opp']} QB {qbb.get(r['opp'], {}).get('listed_starter_nflverse_schedule')}; "
                f"opponent QB flags {qbb.get(r['opp'], {}).get('flags')}", f"game total {sched[r['team']].get('total_line')}"],
               'flags': r['flags'],
               'missing_model_dependencies': _missing(r, qb) if r['pos'] != 'DST' else
               ['opponent QB identity not consumed by DST model (D-02)', 'turnovers not event-linked (D-05)'],
               'recommended_research_action': _actions(r)}
        recs.append(rec)
    return recs


def write_md(recs, path, week):
    L = [f'# Week {week} player research records (positive-projection rows)', '',
         'Confirmed facts come from captures in `nfl/dfs/salaries/raw/classic_early_2026W5/PROVENANCE.json`. Estimates are '
         'computed from those facts. Reported news is a secondary web-search supplement and carries its own tag. Our '
         'projection is not built yet, because the DK DKEntries export is missing. FC is a benchmark only.', '']
    team = None
    for r in recs:
        if r['team'] != team:
            team = r['team']
            L += [f'## {team} vs {r["opp"]}', '']
        F, E = r['confirmed_facts'], r['estimates']
        L.append(f"### {r['player']} ({r['pos']}, ${r['salary']})")
        L.append(f"- **Eligibility:** {r['eligibility']}. Practice: {F.get('practice_status_latest', 'not on report')}"
                 f"{' (' + F['injury'] + ')' if F.get('injury') else ''}. Designation: {F.get('game_designation', 'n/a')}. "
                 f"Depth: {F.get('depth_chart')}.")
        if E:
            L.append(f"- **2026:** {E.get('games_played_2026')} games, DK average {E.get('dk_avg_2026')}, last game "
                     f"{E.get('dk_last_game')} (week {E.get('last_game_week')}).")
        L.append(f"- **What drives his production:** {'; '.join(r['what_drives_production'])}.")
        for n in r['reported_news'][:3]:
            L.append(f"- **Reported [{n['status']}]:** {n['fact']} ({', '.join(n['sources'][:1])})")
        L.append(f"- **Benchmark FC:** {r['benchmark_fc']['proj']} (floor {r['benchmark_fc']['floor']}, ceiling "
                 f"{r['benchmark_fc']['ceiling']}). Our projection: NOT BUILT.")
        if r['flags']:
            L.append(f"- **Flags:** {' | '.join(r['flags'])}")
        L.append(f"- **Missing model dependencies:** {'; '.join(r['missing_model_dependencies'])}.")
        L.append(f"- **Next research action:** {'; '.join(r['recommended_research_action'])}.")
        L.append('')
    pathlib.Path(path).write_text('\n'.join(L) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('board_dir')
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--news')
    a = ap.parse_args(argv)
    news = json.loads(pathlib.Path(a.news).read_text()) if a.news else None
    recs = build(a.board_dir, a.week, news)
    bd = pathlib.Path(a.board_dir)
    (bd / f'WEEK{a.week}_PLAYER_RESEARCH_RECORDS.json').write_text(json.dumps(recs, indent=1, default=str) + '\n')
    write_md(recs, bd / f'WEEK{a.week}_PLAYER_RESEARCH_RECORDS.md', a.week)
    print(len(recs), 'records;', sum(1 for r in recs if r['reported_news']), 'with reported news;',
          sum(1 for r in recs if r['flags']), 'flagged')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
