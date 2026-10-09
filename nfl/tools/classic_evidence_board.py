#!/usr/bin/env python3.12
"""Per-player evidence board for a Classic slate: what we know, what our engine did with it, and what it ignored.

    python3.12 nfl/tools/classic_evidence_board.py BOARD_DIR RUN_DIR --week 5 [--news NEWS.json] [--alt RUN_DIR2]

Rows: every positively benchmarked player on the research board (FC is the benchmark, never an input), plus every
player in our own universe with a projection of at least 4 DK points that the benchmark export omits.

For each row: current eligibility, injury and practice evidence, starting role, the club quarterback dependency,
workload, opponent, our projection with its simulated uncertainty, and the benchmark. Then STORED_NOT_CONSUMED: each
piece of relevant information this checkout holds that the forecasting engine does not read, named per player:

  PRACTICE_STATUS_NOT_CONSUMED     DNP/limited practice is in the state; only an OUT designation changes a projection
  DESIGNATION_NOT_CONSUMED         QUESTIONABLE/DOUBTFUL is in the state; p_plays is unchanged by it
  LISTED_STARTER_NOT_CONSUMED      the schedule capture lists a different club starter from the engine's rank-1 QB
  QB_REGIME_NOT_CONSUMED           the club's QB flags (change/churn/thin evidence); team volume ignores QB identity
  TEAMMATE_PRACTICE_NOT_CONSUMED   a same-club skill teammate did not practise and is undesignated; no redistribution
  DEPTH_TIE_BROKEN_BY_ID           his depth rank ties a room-mate's and the tie was broken by id order, not evidence
  ROLE_HISTORY_ABOVE_CEILING       his history is >= 2 bands above the depth-evidence ceiling (engine names it)
  SECONDARY_NEWS_NOT_CONSUMED      the web supplement reports on him; by rule it is discovery, never an input
  OPPONENT_QB_NOT_CONSUMED         (DST) the opponent QB flags are not read by the defence model

Read-only. It changes no projection.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import re

import numpy as np

SKILL = ('QB', 'RB', 'WR', 'TE')


def _nk(name, team):
    n = re.sub(r"[^a-z ]", '', name.lower().replace('-', ' '))
    n = ' '.join(w for w in n.split() if w not in ('jr', 'sr', 'ii', 'iii', 'iv', 'v'))
    return n, team


def _desig(ca):
    d = (ca or {}).get('designation')
    return None if d in (None, 'NO_DESIGNATION') else d


def _last(s):
    return re.sub(r'[^a-z]', '', (s or '').split('.')[-1].split(' ')[-1].lower())


def _news(news, name, team):
    if not news:
        return []
    t = (news.get('teams') or {}).get(team) or {}
    pat = re.compile(r'\b' + re.escape(name.split(' ')[-1].replace('.', '')) + r'\b')
    out = []
    for k in ('qb', 'injuries', 'transactions', 'role_news'):
        v = t.get(k) or []
        for x in (v if isinstance(v, list) else [v]):
            if x and pat.search(str(x.get('fact', ''))):
                out.append({'kind': k, 'status': x.get('status'), 'fact': x.get('fact'),
                            'source': ((x.get('sources') or [{}])[0]).get('url')})
    return out


def load_run(run_dir):
    rd = pathlib.Path(run_dir)
    st = json.loads((rd / 'STATE.json').read_text())
    pj = json.loads((rd / 'PROJ.json').read_text())
    dr = json.loads((rd / 'DRAWS.json').read_text())
    rs = json.loads((rd / 'ROLE_STATE.json').read_text())
    return st, pj, dr, rs


def build(board_dir, run_dir, week, news=None, alt_dir=None):
    bd = pathlib.Path(board_dir)
    W = f'WEEK{week}'
    board = json.loads((bd / f'{W}_FULL_PLAYER_RESEARCH_BOARD.json').read_text())
    qbb = json.loads((bd / f'{W}_QB_REGIME_BOARD.json').read_text())['QB_REGIME_BOARD']
    st, pj, dr, _rs = load_run(run_dir)
    alt, alt_g = {}, {}
    if alt_dir:
        _s2, pj2, _d2, _r2 = load_run(alt_dir)
        alt = {_nk(r['name'], r['team']): r for r in pj2['rows'].values()}
        alt_g = {r.get('gsis_id'): r for r in pj2['rows'].values() if r.get('gsis_id')}
    P = st['players']
    proj = {_nk(r['name'], r['team']): r for r in pj['rows'].values()}
    state_by = {_nk(v['name'], v['team']): (k, v) for k, v in P.items()}
    # JOIN ON THE GSIS ID FIRST: a name join loses 'Chigoziem' vs 'Chig' Okonkwo. Names only as the fallback.
    proj_g = {r.get('gsis_id'): r for r in pj['rows'].values() if r.get('gsis_id')}
    state_g = {v.get('gsis_id'): (k, v) for k, v in P.items() if v.get('gsis_id')}
    draws = dr['draws']

    # rooms with tied supplied depth ranks
    rank_ct = collections.Counter((v['team'], v['position'], v['depth_rank']) for v in P.values()
                                  if isinstance(v.get('depth_rank'), int) and v['position'] in SKILL)
    # the engine's starting QB per club: the QB whose projection has the most pass attempts
    eng_qb = {}
    for r in pj['rows'].values():
        if r['position'] == 'QB' and (r.get('pass_attempts') or 0) > (eng_qb.get(r['team'], (None, -1))[1]):
            eng_qb[r['team']] = (r['name'], r.get('pass_attempts') or 0)
    # undesignated, did-not-practise skill players per club
    dnp = collections.defaultdict(list)
    for v in P.values():
        ca = v.get('current_availability') or {}
        if v['position'] in SKILL and (ca.get('practice_status') or '').startswith('Did Not') and not _desig(ca):
            dnp[v['team']].append(v['name'])
    for b in board['rows']:   # the later capture the board read (the state reads only manifest captures)
        if b['pos'] in SKILL and (b['facts'].get('practice_status_latest') or '').startswith('Did Not') \
                and not b['facts'].get('game_designation') and b['player'] not in dnp[b['team']]:
            dnp[b['team']].append(b['player'])

    rows_in = [r for r in board['rows'] if r['positive_projection']]
    fc_keys = {_nk(r['player'], r['team']) for r in board['rows']}
    fc_gsis = {(r.get('identity') or {}).get('gsis_id') for r in board['rows']} - {None}
    extra = [r for r in pj['rows'].values() if r['position'] != 'DST' and (r.get('dk_points') or 0) >= 4
             and r.get('gsis_id') not in fc_gsis and _nk(r['name'], r['team']) not in fc_keys]
    out = []

    def one(name, team, pos, b=None, gsis=None):
        key = _nk(name, team)
        gsis = gsis or ((b or {}).get('identity') or {}).get('gsis_id')
        pr = proj_g.get(gsis) or proj.get(key)
        sk = state_g.get(gsis) or state_by.get(key)
        if pos == 'DST':
            pr = next((r for r in pj['rows'].values() if r['position'] == 'DST' and r['team'] == team), None)
            sk = next(((k, v) for k, v in P.items() if v['position'] == 'DST' and v['team'] == team), None)
        sv = sk[1] if sk else {}
        ca = sv.get('current_availability') or {}
        dkey = f"{pr['name']}|{team}" if pr else None
        d = np.asarray(draws.get(dkey) or [], float)
        qb = qbb.get(team, {})
        F = (b or {}).get('facts') or {}
        E = (b or {}).get('estimates') or {}
        flags = []
        # the newest stored practice line: the board's later capture when it has one, else the state's
        prac = F.get('practice_status_latest') or ca.get('practice_status') or ''
        if pos != 'DST' and (prac.startswith('Did Not') or prac.startswith('Limited')) and not _desig(ca):
            flags.append(f'PRACTICE_STATUS_NOT_CONSUMED: {prac}; no designation yet, projection assumes he plays '
                         f'(p_plays {round(min((pr or {}).get("p_plays", {}).values() or [None]) or 0, 2) if pr else None})')
        if _desig(ca) in ('QUESTIONABLE', 'DOUBTFUL'):
            flags.append(f"DESIGNATION_NOT_CONSUMED: {ca['designation']}")
        lst = qb.get('listed_starter_nflverse_schedule')
        eq = (eng_qb.get(team) or (None,))[0]
        if pos in SKILL and lst and eq and _last(lst) != _last(eq):
            flags.append(f'LISTED_STARTER_NOT_CONSUMED: schedule capture lists {lst}; engine starts {eq}')
        if pos in SKILL and qb.get('flags'):
            flags.append('QB_REGIME_NOT_CONSUMED: ' + '; '.join(f.split(':')[0] for f in qb['flags']))
        mates = [m for m in dnp.get(team, []) if _nk(m, team) != key]
        if pos in SKILL and mates:
            flags.append(f"TEAMMATE_PRACTICE_NOT_CONSUMED: {', '.join(mates[:5])} did not practise, undesignated")
        rnk = sv.get('depth_rank')
        if pos in SKILL and isinstance(rnk, int) and rank_ct[(team, pos, rnk)] > 1:
            scoped = (pr or {}).get('_chart_rank')
            flags.append(f'DEPTH_TIE_BROKEN_BY_ID: supplied rank {rnk} shared by {rank_ct[(team, pos, rnk)]} at {pos}; '
                         f'ceiling {(pr or {}).get("askable_ceiling")}')
        if (pr or {}).get('role_evidence_conflict'):
            c = pr['role_evidence_conflict']
            flags.append(f"ROLE_HISTORY_ABOVE_CEILING: history {c.get('history_band')}, assigned {c.get('assigned_band')}")
        nws = _news(news, name, team) if pos != 'DST' else []
        if nws:
            flags.append('SECONDARY_NEWS_NOT_CONSUMED: ' + '; '.join(f"[{n['status']}] {n['fact'][:90]}" for n in nws[:2]))
        if pos == 'DST' and (qbb.get((b or {}).get('opp') or '', {}).get('flags')):
            flags.append('OPPONENT_QB_NOT_CONSUMED: ' + '; '.join(
                f.split(':')[0] for f in qbb[(b or {}).get('opp')]['flags']))
        a = (alt_g.get(gsis) or alt.get(key)) if pos != 'DST' else None
        return {
            'player': name, 'team': team, 'pos': pos, 'opp': (b or {}).get('opp') or (sv.get('opponent')),
            'game_id': sv.get('game_id') or (b or {}).get('game_id'),
            'in_benchmark_export': b is not None,
            'eligibility': (b or {}).get('eligibility') or 'ELIGIBLE (ACT) -- research universe',
            'availability_state': ca.get('status'), 'availability_tier': ca.get('tier'),
            'designation': _desig(ca), 'practice_status': prac or None,
            'practice_status_in_engine_state': ca.get('practice_status'),
            'injury': ca.get('injury') or F.get('injury'),
            'depth_chart_captured': F.get('depth_chart'), 'supplied_depth_rank': rnk,
            'role_band': (pr or {}).get('role_band'), 'role_ceiling': (pr or {}).get('askable_ceiling'),
            'role_evidence': (pr or {}).get('basis') if isinstance((pr or {}).get('basis'), str) else None,
            'club_qb_listed_by_schedule': lst, 'club_qb_engine_starter': eq, 'club_qb_flags': qb.get('flags'),
            'workload_2026': {k: E.get(k) for k in ('games_played_2026', 'target_share_avg', 'carry_share_avg',
                                                     'red_zone_targets_2026', 'red_zone_carries_2026', 'snap_trend_pp')},
            'our_volume': {k: (round(pr[k], 2) if isinstance((pr or {}).get(k), (int, float)) else None)
                           for k in ('pass_attempts', 'carries', 'targets')},
            'our_p_plays': (pr or {}).get('p_plays'),
            'our_dk_points': round(pr['dk_points'], 2) if pr and isinstance(pr.get('dk_points'), (int, float)) else None,
            'our_dk_if_plays': (pr or {}).get('dk_points_if_plays'),
            'our_sim': ({'p10': round(float(np.percentile(d, 10)), 1), 'p50': round(float(np.percentile(d, 50)), 1),
                         'p90': round(float(np.percentile(d, 90)), 1), 'sd': round(float(d.std()), 1),
                         'mean': round(float(d.mean()), 2)} if d.size else None),
            'alt_arm_dk_points': round(a['dk_points'], 2) if a and isinstance(a.get('dk_points'), (int, float)) else None,
            'benchmark_fc': ({'proj': b['fc_proj'], 'floor': b['fc_floor'], 'ceiling': b['fc_ceiling'],
                              'depth_tag': b['fc_depth_tag']} if b else None),
            'ours_minus_benchmark': (round(pr['dk_points'] - b['fc_proj'], 2)
                                     if b and pr and isinstance(pr.get('dk_points'), (int, float)) else None),
            'research_flags': (b or {}).get('flags'),
            'STORED_NOT_CONSUMED': flags,
        }

    for b in rows_in:
        out.append(one(b['player'], b['team'], b['pos'], b))
    for r in extra:
        out.append(one(r['name'], r['team'], r['position'], None, r.get('gsis_id')))
    if not out:
        raise RuntimeError('EVIDENCE_BOARD_EMPTY: no rows; an empty board is an error, not a result')
    unmatched = [r['player'] for r in out if r['our_dk_points'] is None]
    if len(unmatched) > len(out) // 10:
        raise RuntimeError(f'EVIDENCE_BOARD_JOIN_FAILED: {len(unmatched)} of {len(out)} rows have no projection of ours')
    return out


def summary(rows):
    c = collections.Counter(f.split(':')[0] for r in rows for f in r['STORED_NOT_CONSUMED'])
    return {'n_rows': len(rows), 'n_benchmark_positive': sum(r['in_benchmark_export'] for r in rows),
            'n_omitted_by_benchmark_with_our_proj_ge_4': sum(not r['in_benchmark_export'] for r in rows),
            'n_rows_with_any_stored_not_consumed': sum(1 for r in rows if r['STORED_NOT_CONSUMED']),
            'by_kind': dict(c.most_common())}


def write(rows, out_dir, week, meta):
    od = pathlib.Path(out_dir)
    W = f'WEEK{week}'
    doc = {'ARTIFACT': f'{W}_EVIDENCE_BOARD', **meta, 'summary': summary(rows), 'rows': rows}
    (od / f'{W}_EVIDENCE_BOARD.json').write_text(json.dumps(doc, indent=1, default=str) + '\n')
    cols = ['player', 'team', 'pos', 'opp', 'in_benchmark_export', 'eligibility', 'availability_state', 'designation',
            'practice_status', 'injury', 'depth_chart_captured', 'role_band', 'role_ceiling', 'club_qb_engine_starter',
            'club_qb_listed_by_schedule', 'our_dk_points', 'alt_arm_dk_points', 'sim_p10', 'sim_p90', 'fc_proj',
            'ours_minus_benchmark', 'n_stored_not_consumed', 'stored_not_consumed']
    with open(od / f'{W}_EVIDENCE_BOARD.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([r['player'], r['team'], r['pos'], r['opp'], r['in_benchmark_export'], r['eligibility'],
                        r['availability_state'], r['designation'], r['practice_status'], r['injury'],
                        r['depth_chart_captured'], r['role_band'], r['role_ceiling'], r['club_qb_engine_starter'],
                        r['club_qb_listed_by_schedule'], r['our_dk_points'], r['alt_arm_dk_points'],
                        (r['our_sim'] or {}).get('p10'), (r['our_sim'] or {}).get('p90'),
                        (r['benchmark_fc'] or {}).get('proj'), r['ours_minus_benchmark'],
                        len(r['STORED_NOT_CONSUMED']), ' | '.join(r['STORED_NOT_CONSUMED'])])
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('board_dir')
    ap.add_argument('run_dir')
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--news')
    ap.add_argument('--alt')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    news = json.loads(pathlib.Path(a.news).read_text()) if a.news else None
    rows = build(a.board_dir, a.run_dir, a.week, news, a.alt)
    doc = write(rows, a.out or a.board_dir, a.week, {'run_dir': a.run_dir, 'alt_run_dir': a.alt})
    print(json.dumps(doc['summary'], indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
