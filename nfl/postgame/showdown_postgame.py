#!/usr/bin/env python3.12
"""Slate-generic DraftKings Showdown postgame: realised actuals, frozen-forecast grading, portfolio grading.

    python3.12 nfl/postgame/showdown_postgame.py CONFIG.json PBP_GZ [--history DK_ENTRY_HISTORY.csv]

Generalises the ATL@NO 2026W4 postgame (showdown_atl_no_postgame.py, which now delegates its actuals here) so a slate
is graded by configuration, not by a new module per game.

LAYERS, KEPT APART
  PRELOCK_FORECAST   the sealed scenario directory (STATE, DRAWS, PROJ, WORLDS) and the FC export -- read, never written
  PRELOCK_PORTFOLIO  every named portfolio in the config (official, corrected, research) -- read, never written
  POSTGAME_ACTUAL    nflverse play-by-play for the one game, scored with the SAME DK scorer the projection used
                     (nfl.product.dk_scoring), so a forecast error is football, not two formulas disagreeing
  CONTEST_FINANCIAL  only from an authenticated DraftKings entry-history export. Without one every financial field is
                     UNKNOWN; nothing is estimated and called a return.

REFUSALS, BY NAME
  GAME_NOT_IN_PBP        the pbp file does not carry the game (nflverse has not published it yet)
  GAME_NOT_FINAL         the game is present but has no final whistle in the file
  PBP_GAME_TOO_THIN      fewer than 100 plays
  FROZEN_ARTIFACT_CHANGED  a prelock file no longer matches its hash in the freeze manifest
  PLAYER_NOT_SCORED      a lineup names a player with no realised actual

Nothing written here is an input to any forecast. Hindsight quantities (the best lineup that could have been built with
final scores) are labelled HINDSIGHT and are never presented as selectable before lock.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import itertools
import json
import pathlib
import shutil
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import join_provenance as JP  # noqa: E402
from nfl.product import dk_scoring as DKS  # noqa: E402

SALARY_CAP = 50000
CPT_MULT = 1.5


class PostgameError(RuntimeError):
    pass


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _rel(p):
    p = pathlib.Path(p).resolve()
    try:
        return str(p.relative_to(_REPO))
    except ValueError:
        return str(p)


# ---------------------------------------------------------------------------------------------------- 1. actuals

def load_game(pbp_gz, game):
    import pandas as pd
    d = pd.read_csv(pbp_gz, low_memory=False)
    g = d[d.game_id == game].copy()
    if g.empty:
        weeks = sorted(set(d.week.dropna().astype(int))) if 'week' in d else []
        raise PostgameError(f'GAME_NOT_IN_PBP {game}: file carries weeks {weeks[:1]}..{weeks[-1:]}')
    if len(g) < 100:
        raise PostgameError(f'PBP_GAME_TOO_THIN {len(g)} plays')
    if 'desc' in g and not g['desc'].astype(str).str.contains('END GAME', case=False).any():
        raise PostgameError(f'GAME_NOT_FINAL {game}: no END GAME row')
    return g


def actuals(pbp_gz, state, game):
    """Realised stat line and DK points for every DK-pool player. rule A = DK (missed FG scores 0, settled 172/172 on
    ATL@NO); rule B (missed FG -1) is kept only as the comparison that settled it."""
    import pandas as pd
    g = load_game(pbp_gz, game)
    f = lambda c: g[c].fillna(0)  # noqa: E731
    home, away = g.home_team.iloc[0], g.away_team.iloc[0]
    final = {home: int(g.total_home_score.max()), away: int(g.total_away_score.max())}
    st = collections.defaultdict(lambda: collections.Counter())
    for _, r in g.iterrows():
        two = r.get('two_point_conv_result') == 'success'
        # A FAILED two-point try is not an ordinary play: it is no pass attempt, no target and no carry (nflverse
        # stats_player_week agrees). Counting it inflated targets/attempts and -- had a failed try been caught short of
        # the goal line -- would have added a reception and its DK point. Found by the 2026-10-09 TB@DAL cross-check.
        if r.get('two_point_attempt') == 1 and not two:
            continue
        if r.get('play_type') in ('pass',) or r.get('pass_attempt') == 1:
            if pd.notna(r.get('passer_player_id')) and r.get('sack') != 1:
                p = st[r['passer_player_id']]
                if two:
                    p['two_pt'] += 1
                else:
                    p['pass_att'] += 1 if r.get('pass_attempt') == 1 and r.get('sack') != 1 else 0
                    p['pass_yds'] += r['passing_yards'] if pd.notna(r.get('passing_yards')) else 0
                    p['pass_td'] += 1 if r.get('pass_touchdown') == 1 else 0
                    p['int'] += 1 if r.get('interception') == 1 else 0
            if pd.notna(r.get('receiver_player_id')):
                q = st[r['receiver_player_id']]
                if two:
                    q['two_pt'] += 1
                else:
                    q['targets'] += 1
                    q['rec'] += 1 if r.get('complete_pass') == 1 else 0
                    q['rec_yds'] += r['receiving_yards'] if pd.notna(r.get('receiving_yards')) else 0
                    q['rec_td'] += 1 if r.get('pass_touchdown') == 1 else 0
        if pd.notna(r.get('rusher_player_id')) and (r.get('rush_attempt') == 1 or (two and r.get('play_type') == 'run')):
            q = st[r['rusher_player_id']]
            if two:
                q['two_pt'] += 1
            else:
                q['carries'] += 1
                q['rush_yds'] += r['rushing_yards'] if pd.notna(r.get('rushing_yards')) else 0
                q['rush_td'] += 1 if r.get('rush_touchdown') == 1 else 0
        if r.get('fumble_lost') == 1 and pd.notna(r.get('fumbled_1_player_id')):
            st[r['fumbled_1_player_id']]['fum_lost'] += 1
        if r.get('play_type') in ('kickoff', 'punt') and r.get('return_touchdown') == 1 and pd.notna(r.get('td_player_id')):
            st[r['td_player_id']]['return_td'] += 1
        if r.get('field_goal_attempt') == 1 and pd.notna(r.get('kicker_player_id')):
            k = st[r['kicker_player_id']]
            k['fg_att'] += 1
            if r.get('field_goal_result') == 'made':
                dist = float(r['kick_distance'])
                k['fg_made'] += 1
                k['fg_lt40'] += dist < 40
                k['fg_40s'] += 40 <= dist < 50
                k['fg_50p'] += dist >= 50
            else:
                k['fg_missed'] += 1
        if r.get('extra_point_attempt') == 1 and pd.notna(r.get('kicker_player_id')):
            k = st[r['kicker_player_id']]
            k['xp_att'] += 1
            k['xp_made'] += r.get('extra_point_result') == 'good'
            k['xp_missed'] += r.get('extra_point_result') != 'good'
    # EVERY ID THE PLAY-BY-PLAY NAMES FOR THIS GAME, in any role. A player in it is MATCHED_BY_IDENTITY (a zero is a
    # REAL_ZERO); a player with an id who is not in it recorded no production in a covered game (a governed
    # ABSENCE_RESOLVED_TO_ZERO); a player with no id is IDENTITY_NOT_ESTABLISHED and is NOT graded (join_provenance).
    seen_ids = set()
    for c in [c for c in g.columns if c.endswith('_player_id')]:
        seen_ids |= set(g[c].dropna().astype(str))
    dst = {}
    for team in (home, away):
        opp = away if team == home else home
        sacks = float(f('sack')[g.defteam == team].sum())
        ints = float(f('interception')[g.defteam == team].sum())
        fr = float(((g.fumble_lost == 1) & (g.defteam == team)).sum())
        dtd = float(((g.return_touchdown == 1) & (g.td_team == team)).sum())
        saf = float(((g.safety == 1) & (g.defteam == team)).sum())
        blk = float((((g.punt_blocked == 1) | (g.field_goal_result == 'blocked') | (g.extra_point_result == 'blocked'))
                     & (g.defteam == team)).sum())
        opp_ret_td = int(((g.return_touchdown == 1) & (g.td_team == opp)).sum())
        pa = final[opp] - 6 * opp_ret_td
        dst[team] = {'sacks': sacks, 'ints': ints, 'fumble_recoveries': fr, 'tds': dtd, 'safeties': saf,
                     'blocked_kicks': blk, 'points_allowed_final': final[opp], 'opp_return_tds': opp_ret_td,
                     'points_allowed_excl_return_td6': pa}
    players, ungradeable = {}, {}

    def _prov(gid):
        if gid in seen_ids:
            return JP.stamp(JP.MATCHED_BY_IDENTITY, key=gid, zero_basis=JP.REAL_ZERO)
        return JP.stamp(JP.ABSENCE_RESOLVED_TO_ZERO, key='ZERO_NO_RECORDED_PRODUCTION',
                        zero_basis=JP.ABSENCE_RESOLVED_TO_ZERO)
    for v in state['players'].values():
        nm, tm, pos = v['name'], v['team'], v['position']
        key = f'{nm}|{tm}'
        if pos != 'DST' and not v.get('gsis_id'):
            ungradeable[key] = JP.IDENTITY_NOT_ESTABLISHED
            continue
        if pos == 'DST':
            x = dst[tm]
            players[key] = {'pos': 'DST', 'stats': x, 'dk_A': DKS.dst_points(points_allowed=x['points_allowed_final'],
                            sacks=x['sacks'], ints=x['ints'], fumble_recoveries=x['fumble_recoveries'], tds=x['tds'],
                            safeties=x['safeties'], blocked_kicks=x['blocked_kicks']),
                            'dk_B': DKS.dst_points(points_allowed=x['points_allowed_excl_return_td6'], sacks=x['sacks'],
                            ints=x['ints'], fumble_recoveries=x['fumble_recoveries'], tds=x['tds'],
                            safeties=x['safeties'], blocked_kicks=x['blocked_kicks']),
                            'join_provenance': JP.stamp(JP.MATCHED_BY_IDENTITY, key=f'club:{tm}', zero_basis=JP.REAL_ZERO)}
            continue
        s = st.get(v.get('gsis_id'), collections.Counter())
        if pos == 'K':
            a = (s['fg_lt40'] * DKS.FG_UNDER_40 + s['fg_40s'] * DKS.FG_40_49 + s['fg_50p'] * DKS.FG_50_PLUS
                 + s['xp_made'] * DKS.EXTRA_POINT)
            players[key] = {'pos': 'K', 'stats': dict(s), 'dk_A': float(a), 'dk_B': float(a - s['fg_missed']),
                            'join_provenance': _prov(v['gsis_id'])}
            continue
        p = float(DKS.skill_points(1, pass_yds=[s['pass_yds']], pass_td=[s['pass_td']], ints=[s['int']],
                                   rush_yds=[s['rush_yds']], rush_td=[s['rush_td']], rec=[s['rec']],
                                   rec_yds=[s['rec_yds']], rec_td=[s['rec_td']], fumbles_lost=[s['fum_lost']])[0])
        p += DKS.realised_extra_points(two_pt=s['two_pt'], return_td=s['return_td'])
        players[key] = {'pos': pos, 'stats': dict(s), 'dk_A': round(p, 2), 'dk_B': round(p, 2),
                        'join_provenance': _prov(v['gsis_id'])}
    for key, r in players.items():
        JP.assert_graded_row(r, actual=r['dk_A'], where=f'{game}:{key}')
    return {'final': final, 'home': home, 'away': away, 'n_plays': int(len(g)), 'dst': dst, 'players': players,
            'ungradeable': ungradeable,
            'join_audit': {j: sum(1 for r in players.values() if r['join_provenance']['join'] == j) for j in JP.JOINS}}


def game_flow(pbp_gz, game):
    """Descriptive reconstruction of how the game went: scoring sequence, drives, pace, script. Never a forecast input."""
    g = load_game(pbp_gz, game)
    home, away = g.home_team.iloc[0], g.away_team.iloc[0]
    sc = g[(g.sp == 1) if 'sp' in g else (g.touchdown == 1)]
    scoring = [{'qtr': int(r.qtr), 'clock': str(r.time), 'posteam': str(r.posteam), 'desc': str(r.desc)[:160],
                'home': int(r.total_home_score), 'away': int(r.total_away_score)} for r in sc.itertuples()]
    teams = {}
    for t in (home, away):
        o = g[(g.posteam == t) & (g.two_point_attempt.fillna(0) != 1)]      # tries are not offensive plays
        plays = o[o.play_type.isin(['pass', 'run'])]
        drives = o.drive.dropna().nunique() if 'drive' in o else None
        teams[t] = {'offensive_plays': int(len(plays)), 'dropbacks': int(o.qb_dropback.fillna(0).sum()),
                    'pass_attempts': int(o.pass_attempt.fillna(0).sum() - o.sack.fillna(0).sum()),
                    'sacks_taken': int(o.sack.fillna(0).sum()), 'scrambles': int(o.qb_scramble.fillna(0).sum()),
                    'designed_runs': int(((o.play_type == 'run') & (o.qb_scramble.fillna(0) == 0)).sum()),
                    'drives': None if drives is None else int(drives),
                    'red_zone_plays': int(((o.yardline_100 <= 20) & o.play_type.isin(['pass', 'run'])).sum()),
                    'explosive_plays_20plus': int((o.yards_gained.fillna(0) >= 20).sum()),
                    'turnovers': int(o.interception.fillna(0).sum() + o.fumble_lost.fillna(0).sum()),
                    'epa_per_play': round(float(plays.epa.mean()), 3) if 'epa' in plays and len(plays) else None,
                    'pass_rate': round(float((plays.play_type == 'pass').mean()), 3) if len(plays) else None}
    by_q = {}
    for q in sorted(set(g.qtr.dropna().astype(int))):
        last = g[g.qtr <= q].iloc[-1]
        by_q[q] = {home: int(last.total_home_score), away: int(last.total_away_score)}
    return {'home': home, 'away': away, 'score_after_quarter': by_q, 'scoring_plays': scoring, 'teams': teams}


# ------------------------------------------------------------------------------------------- 2. forecast grading

def pit(draws, x):
    """Mid-rank probability integral transform: P(X < x) + 0.5 P(X == x). Ties matter -- DK points are discrete-ish."""
    a = np.asarray(draws, dtype=float)
    return float(((a < x).sum() + 0.5 * (a == x).sum()) / a.size)


def _fc(fc_csv):
    if not fc_csv:
        return {}
    from nfl.tools import fc_qb_scenario_compare as FCC
    flex, _cpt, _ver = FCC.load_fc(fc_csv)
    return {f'{n}|{t}': v for (n, t), v in flex.items()}


def grade_players(act, draws_doc, fc_csv=None, worlds_npz=None):
    fc = _fc(fc_csv)
    stats_w = None
    if worlds_npz:
        z = np.load(worlds_npz)
        meta = json.loads(bytes(z['meta']).decode())
        stats_w = (z['stats'], meta)
    rows = []
    for k, d in draws_doc['draws'].items():
        a = np.asarray(d, dtype=float)
        if k not in act['players']:
            if k in act.get('ungradeable', {}):
                continue          # reported in the document's `ungradeable`, never given a number
            raise PostgameError(f'PLAYER_NOT_SCORED {k}')
        y = float(act['players'][k]['dk_A'])
        f = (fc.get(k) or {}).get('proj')
        r = {'player': k, 'pos': act['players'][k]['pos'], 'ours_mean': round(float(a.mean()), 2),
             'ours_p10': round(float(np.percentile(a, 10)), 1), 'ours_p50': round(float(np.percentile(a, 50)), 1),
             'ours_p90': round(float(np.percentile(a, 90)), 1), 'fc_proj': f, 'actual': y,
             'our_error': round(y - float(a.mean()), 2), 'fc_error': None if f is None else round(y - f, 2),
             'pit': round(pit(a, y), 4), 'inside_80': bool(np.percentile(a, 10) <= y <= np.percentile(a, 90))}
        rows.append(r)
    stat_rows = []
    if stats_w is not None:
        S, meta = stats_w
        flds, scale = meta['fields'], meta.get('yard_scale', 1)
        amap = {'pass_att': 'pass_att', 'pass_yards': 'pass_yds', 'pass_td': 'pass_td', 'carries': 'carries',
                'rush_yards': 'rush_yds', 'rush_td': 'rush_td', 'targets': 'targets', 'receptions': 'rec',
                'rec_yards': 'rec_yds', 'rec_td': 'rec_td', 'interceptions': 'int'}
        for i, k in enumerate(meta['keys']):
            s = act['players'].get(k, {}).get('stats') or {}
            if act['players'].get(k, {}).get('pos') in ('K', 'DST'):
                continue
            for j, fl in enumerate(flds):
                w = S[i, :, j].astype(float) / (scale if fl in meta.get('yard_fields', ()) else 1)
                if w.mean() < 0.05 and float(s.get(amap[fl], 0)) == 0:
                    continue
                y = float(s.get(amap[fl], 0))
                stat_rows.append({'player': k, 'stat': fl, 'ours_mean': round(float(w.mean()), 2), 'actual': y,
                                  'error': round(y - float(w.mean()), 2), 'pit': round(pit(w, y), 4)})
    return rows, stat_rows


def calibration_summary(rows):
    p = np.array([r['pit'] for r in rows])
    e = np.array([r['our_error'] for r in rows])
    fe = [(r['our_error'], r['fc_error']) for r in rows if r['fc_error'] is not None]
    out = {'n_players': int(p.size), 'mean_pit': round(float(p.mean()), 3),
           'share_inside_ours_p10_p90': round(float(np.mean([r['inside_80'] for r in rows])), 3),
           'share_below_p10': round(float((p < 0.10).mean()), 3), 'share_above_p90': round(float((p > 0.90).mean()), 3),
           'our_mae': round(float(np.abs(e).mean()), 2), 'our_mean_error': round(float(e.mean()), 2),
           'READING': ('One game is ONE draw per player from correlated outcomes (players share a game script). These '
                       'shares describe this game; they are not a calibration test. Calibration needs many slates, '
                       'clustered by game.')}
    if fe:
        o = np.array(fe, dtype=float)
        out.update({'n_with_fc': int(len(o)), 'our_mae_on_fc_players': round(float(np.abs(o[:, 0]).mean()), 2),
                    'fc_mae_on_fc_players': round(float(np.abs(o[:, 1]).mean()), 2)})
    return out


def grade_teams(act, draws_doc):
    wp = draws_doc.get('world_points')
    if not wp or 'points' not in wp:
        raise PostgameError('WORLD_POINTS_MISSING')
    P = np.asarray(wp['points'], dtype=float)
    series = {wp['home']: P[:, 0], wp['away']: P[:, 1], 'TOTAL': P.sum(1),
              f"MARGIN_{wp['home']}": P[:, 0] - P[:, 1]}
    real = {wp['home']: act['final'][wp['home']], wp['away']: act['final'][wp['away']],
            'TOTAL': act['final'][wp['home']] + act['final'][wp['away']],
            f"MARGIN_{wp['home']}": act['final'][wp['home']] - act['final'][wp['away']]}
    out = {}
    for t, a in series.items():
        y = real[t]
        out[t] = {'ours_mean': round(float(a.mean()), 2), 'ours_p10': round(float(np.percentile(a, 10)), 1),
                  'ours_p90': round(float(np.percentile(a, 90)), 1), 'actual': y, 'pit': round(pit(a, y), 4)}
    if 'MARGIN_' + wp['home'] in out:
        out['P_HOME_WIN_OURS'] = round(float((series[f"MARGIN_{wp['home']}"] > 0).mean()), 3)
    return out


# ------------------------------------------------------------------------------------------ 3. portfolio grading

def lineups_from_final(path):
    """[(contest_id, entry_id, captain, (flex x5))] from a *_FINAL_LINEUPS.csv (names)."""
    out = []
    for r in csv.DictReader(open(path)):
        out.append((r['contest_id'], r.get('entry_id', ''), r['CPT'], tuple(r[f'FLEX{i}'] for i in range(1, 6))))
    if not out:
        raise PostgameError(f'EMPTY_PORTFOLIO {path}')
    return out


def lineups_from_upload(path, state):
    """[(contest_id, entry_id, captain, flex)] from a DK upload or DKEntries CSV (ids, or 'Name (id)')."""
    by_id = {}
    for v in state['players'].values():
        by_id[str(v['cpt_dk_id'])] = v['name']
        by_id[str(v['flex_dk_id'])] = v['name']
    out = []
    for r in list(csv.reader(open(path, encoding='utf-8-sig')))[1:]:
        if not r or not r[0].strip().isdigit():
            continue
        ids = [x.strip().rsplit('(', 1)[-1].rstrip(')') for x in r[4:10]]
        if not all(ids):
            continue
        out.append((r[2], r[0], by_id[ids[0]], tuple(by_id[i] for i in ids[1:])))
    if not out:
        raise PostgameError(f'EMPTY_PORTFOLIO {path}')
    return out


def _name_key(state):
    return {v['name']: f"{v['name']}|{v['team']}" for v in state['players'].values()}


def score_lineup(cpt, flex, pts, nk):
    for n in (cpt, *flex):
        if nk.get(n) not in pts:
            raise PostgameError(f'PLAYER_NOT_SCORED {n}')
    return round(CPT_MULT * pts[nk[cpt]] + sum(pts[nk[x]] for x in flex), 2)


def hindsight_optimum(pts, state, eligible_keys):
    """HINDSIGHT: the best legal lineup given final DK points (cap 50,000, CPT at 1.5x salary and points, both clubs).
    Exhaustive over captains x 5-subsets; exact, not a heuristic. Never selectable before lock."""
    pl = [v for v in state['players'].values() if f"{v['name']}|{v['team']}" in eligible_keys]
    # EXACT PRUNING (exchange argument): a player scoring <= 0 is only ever salary/coverage filler, and any such filler
    # can be swapped for a cheaper non-positive player without lowering the score -- so keeping every positive scorer,
    # the five cheapest non-positive players overall and the cheapest non-positive player per club loses no optimum.
    pos_ = [v for v in pl if pts[f"{v['name']}|{v['team']}"] > 0]
    nonpos = sorted((v for v in pl if pts[f"{v['name']}|{v['team']}"] <= 0), key=lambda v: v['salary'])
    keep = {id(v) for v in nonpos[:5]}
    for t in {v['team'] for v in nonpos}:
        keep.add(id(next(v for v in nonpos if v['team'] == t)))
    pl = pos_ + [v for v in nonpos if id(v) in keep]
    keys = [f"{v['name']}|{v['team']}" for v in pl]
    sal = np.array([v['salary'] for v in pl], dtype=float)
    csal = np.array([v['cpt_salary'] for v in pl], dtype=float)
    team = np.array([v['team'] for v in pl])
    p = np.array([pts[k] for k in keys], dtype=float)
    n = len(pl)
    best = (-1e9, None)
    for c in range(n):
        others = [i for i in range(n) if i != c]
        comb = np.array(list(itertools.combinations(others, 5)))
        s = csal[c] + sal[comb].sum(1)
        ok = s <= SALARY_CAP
        two = (team[comb] != team[c]).any(1)
        ok &= two
        if not ok.any():
            continue
        sc = CPT_MULT * p[c] + p[comb].sum(1)
        sc[~ok] = -1e9
        j = int(sc.argmax())
        if sc[j] > best[0]:
            best = (float(sc[j]), (keys[c], [keys[i] for i in comb[j]], float(s[j])))
    return {'score': round(best[0], 2), 'captain': best[1][0], 'flex': best[1][1], 'salary': best[1][2],
            'LABEL': 'HINDSIGHT -- chosen with final scores; not a pregame decision'}


def portfolio_report(name, lineups, pts, state, prelock_means=None):
    nk = _name_key(state)
    sc = np.array([score_lineup(c, f, pts, nk) for _, _, c, f in lineups])
    cap, fx = collections.Counter(), collections.Counter()
    sal, split, stack = [], collections.Counter(), collections.Counter()
    qbs = {f"{v['name']}": v['team'] for v in state['players'].values() if v['position'] == 'QB'}
    pos = {v['name']: v['position'] for v in state['players'].values()}
    tm = {v['name']: v['team'] for v in state['players'].values()}
    salmap = {v['name']: (v['salary'], v['cpt_salary']) for v in state['players'].values()}
    for _, _, c, f in lineups:
        cap[c] += 1
        for x in (c, *f):      # captain counted once, as a roster spot; captain share is reported separately
            fx[x] += 1
        sal.append(salmap[c][1] + sum(salmap[x][0] for x in f))
        teams = collections.Counter(tm[x] for x in (c, *f))
        split['-'.join(f'{t}{teams[t]}' for t in sorted(teams))] += 1
        for q, qt in qbs.items():
            if q in (c, *f):
                nrec = sum(1 for x in (c, *f) if tm[x] == qt and pos[x] in ('WR', 'TE'))
                stack[f'{q}+{nrec}rec'] += 1
    by_contest = collections.defaultdict(list)
    for (cid, _e, _c, _f), s in zip(lineups, sc):
        by_contest[cid].append(float(s))
    distinct = len({(c, tuple(sorted(f))) for _, _, c, f in lineups})
    rep = {'portfolio': name, 'n_lineups': len(lineups), 'distinct_lineups': distinct,
           'actual_mean': round(float(sc.mean()), 2), 'actual_median': round(float(np.median(sc)), 2),
           'actual_max': round(float(sc.max()), 2), 'actual_min': round(float(sc.min()), 2),
           'by_contest': {cid: {'n': len(v), 'max': max(v), 'mean': round(float(np.mean(v)), 2),
                                'median': round(float(np.median(v)), 2)} for cid, v in by_contest.items()},
           'mean_salary': round(float(np.mean(sal))), 'captains': cap.most_common(),
           'exposure': fx.most_common(), 'team_splits': dict(split), 'qb_stacks': dict(stack),
           'best_lineup': None}
    i = int(sc.argmax())
    rep['best_lineup'] = {'captain': lineups[i][2], 'flex': list(lineups[i][3]), 'score': float(sc[i]),
                          'contest': lineups[i][0], 'entry_id': lineups[i][1]}
    return rep, sc


def captain_attribution(lineups, pts, state):
    """Mean actual score of lineups by captain, and the captain's own actual (x1.5)."""
    nk = _name_key(state)
    g = collections.defaultdict(list)
    for _, _, c, f in lineups:
        g[c].append(score_lineup(c, f, pts, nk))
    return sorted(({'captain': c, 'n': len(v), 'mean_lineup': round(float(np.mean(v)), 2),
                    'captain_actual_x1_5': round(CPT_MULT * pts[nk[c]], 2)} for c, v in g.items()),
                  key=lambda r: -r['n'])


# ------------------------------------------------------------------------------------------ 4. contest financials

def contest_financials(history_csv, contests, uploads):
    """From an authenticated DK entry-history export only. Without one, everything is UNKNOWN."""
    if not history_csv:
        return {'STATUS': 'UNKNOWN', 'reason': 'no DraftKings entry-history or standings export captured',
                'fields_unknown': ['entries_accepted', 'accepted_lineups', 'points_by_entry', 'place', 'field_size',
                                   'fees', 'winnings', 'net', 'duplication_with_field', 'payout_table']}
    hist = [r for r in csv.DictReader(open(history_csv, encoding='utf-8-sig')) if r.get('Contest_Key') in contests]
    if not hist:
        raise PostgameError('HISTORY_HAS_NO_ROWS_FOR_CONTESTS')
    fee = sum(float(r['Entry_Fee'].replace('$', '') or 0) for r in hist)
    win = sum(float((r.get('Winnings_Non_Ticket') or '0').replace('$', '').replace(',', '') or 0) for r in hist)
    per = collections.defaultdict(lambda: {'entries': 0, 'fees': 0.0, 'winnings': 0.0, 'best_place': None})
    for r in hist:
        c = per[r['Contest_Key']]
        c['entries'] += 1
        c['fees'] += float(r['Entry_Fee'].replace('$', '') or 0)
        c['winnings'] += float((r.get('Winnings_Non_Ticket') or '0').replace('$', '').replace(',', '') or 0)
        pl = int(r['Place'])
        c['best_place'] = pl if c['best_place'] is None else min(c['best_place'], pl)
        c['field'] = int(r['Contest_Entries'])
    out = {'STATUS': 'ACTUAL (DK entry history)', 'entries': len(hist), 'fees': round(fee, 2),
           'winnings': round(win, 2), 'net': round(win - fee, 2), 'by_contest': dict(per)}
    if uploads:
        # WHICH FILE WAS ACCEPTED: DK's own points per Entry ID against each candidate portfolio rescored from actuals.
        # A generated CSV is a candidate; the portfolio whose rescored points equal DK's for an entry is what DK held.
        pts_by_entry = {r['Entry_Key']: float(r['Points']) for r in hist}
        m = {}
        for name, per_entry in uploads.items():
            hit = sum(1 for e, p in per_entry.items() if e in pts_by_entry and abs(p - pts_by_entry[e]) < 0.011)
            m[name] = {'entries_matching_dk_points': hit, 'of': len(pts_by_entry)}
        out['accepted_portfolio_identification'] = m
    return out


# ---------------------------------------------------------------------------------------------------- 5. run

def verify_freeze(manifest_path):
    m = json.loads(pathlib.Path(manifest_path).read_text())
    bad = []
    for grp in m['groups'].values():
        for e in grp:
            p = _REPO / e['path']
            if not p.is_file() or _sha(p) != e['sha256']:
                bad.append(e['path'])
    if bad:
        raise PostgameError(f'FROZEN_ARTIFACT_CHANGED {bad[:5]} (+{max(0, len(bad) - 5)})')
    return {'manifest': _rel(manifest_path), 'files_verified': sum(len(g) for g in m['groups'].values())}


def preserve_pbp(pbp_gz, raw_dir):
    raw_dir.mkdir(parents=True, exist_ok=True)
    h = _sha(pbp_gz)
    dst = raw_dir / f'NFLVERSE_PBP_2026.{h[:16]}.csv.gz'
    if not dst.exists():
        shutil.copy2(pbp_gz, dst)
        dst.chmod(0o444)
    return {'kind': 'NFLVERSE_PBP_2026', 'file': _rel(dst), 'sha256': h}


def run(config_path, pbp_gz, history_csv=None, write=True):
    cfg = json.loads(pathlib.Path(config_path).read_text())
    out = _REPO / cfg['out_dir']
    sd = _REPO / cfg['forecast_scenario_dir']
    frz = verify_freeze(_REPO / cfg['freeze_manifest']) if cfg.get('freeze_manifest') else \
        {'STATUS': 'NO_FREEZE_MANIFEST', 'reading': 'prelock files were not hash-frozen before grading; say so'}
    state = json.loads(next(sd.glob('SHOWDOWN_*_STATE.json')).read_text())
    draws = json.loads(next(sd.glob('SHOWDOWN_*_DRAWS.json')).read_text())
    act = actuals(pbp_gz, state, cfg['game'])
    pts = {k: float(v['dk_A']) for k, v in act['players'].items()}
    rows, stat_rows = grade_players(act, draws, _REPO / cfg['fc_csv'] if cfg.get('fc_csv') else None,
                                    next(sd.glob('SHOWDOWN_*_WORLDS.npz'), None))
    elig = set(cfg.get('eligible_keys') or [k for k in pts])
    hs = hindsight_optimum(pts, state, elig)
    ports, per_entry = {}, {}
    for p in cfg['portfolios']:
        path = _REPO / p['path']
        lu = lineups_from_final(path) if p['format'] == 'FINAL_LINEUPS' else lineups_from_upload(path, state)
        rep, sc = portfolio_report(p['name'], lu, pts, state)
        if all(e for _, e, _, _ in lu):
            per_entry[p['name']] = {e: float(s) for (_, e, _, _), s in zip(lu, sc)}
        rep['status'] = p['status']
        rep['gap_to_hindsight_optimum'] = round(hs['score'] - rep['actual_max'], 2)
        rep['captain_attribution'] = captain_attribution(lu, pts, state)
        ports[p['name']] = rep
    doc = {'ARTIFACT': 'SHOWDOWN_POSTGAME', 'LAYER': 'POSTGAME_ACTUAL', 'game': cfg['game'], 'tag': cfg['tag'],
           'freeze': frz, 'final_score': act['final'], 'n_plays': act['n_plays'], 'dst_components': act['dst'],
           'game_flow': game_flow(pbp_gz, cfg['game']),
           'player_actuals': act['players'], 'ungradeable': act['ungradeable'], 'join_audit': act['join_audit'],
           'player_grading': sorted(rows, key=lambda r: -abs(r['our_error'])),
           'stat_grading': stat_rows, 'team_grading': grade_teams(act, draws),
           'calibration_this_game': calibration_summary(rows), 'hindsight_optimum': hs, 'portfolios': ports,
           'contest_financials': contest_financials(history_csv, cfg.get('contests', ()), per_entry),
           'NOT_A_FORECAST_INPUT': True, 'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    if write:
        out.mkdir(parents=True, exist_ok=True)
        doc['provenance'] = [preserve_pbp(pbp_gz, _REPO / cfg['raw_dir'])]
        (out / f"{cfg['tag']}_POSTGAME.json").write_text(json.dumps(doc, indent=1, default=float) + '\n')
        doc['ledger_rows_appended'] = append_ledger(doc)
    return doc


LEDGER = _REPO / 'nfl/postgame/SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl'


def append_ledger(doc, ledger=LEDGER):
    """One row per graded player per slate, so provider disagreement and calibration accumulate across slates.
    Idempotent by tag: a slate already in the ledger is never appended twice (a regrade is a new tag)."""
    seen = set()
    if ledger.exists():
        seen = {json.loads(x)['tag'] for x in ledger.read_text().splitlines() if x.strip()}
    if doc['tag'] in seen:
        return 0
    rows = [{'tag': doc['tag'], 'game': doc['game'], **{k: r[k] for k in ('player', 'pos', 'ours_mean', 'ours_p10',
             'ours_p90', 'fc_proj', 'actual', 'our_error', 'fc_error', 'pit')}} for r in doc['player_grading']]
    with ledger.open('a') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('config')
    ap.add_argument('pbp')
    ap.add_argument('--history')
    a = ap.parse_args(argv)
    try:
        doc = run(a.config, a.pbp, a.history)
    except PostgameError as e:
        print(f'REFUSED {e}')
        return 4
    print(doc['final_score'], doc['calibration_this_game'])
    for n, r in doc['portfolios'].items():
        print(f"{n:28s} max {r['actual_max']:6.2f} mean {r['actual_mean']:6.2f} gap {r['gap_to_hindsight_optimum']}")
    print('HINDSIGHT', doc['hindsight_optimum'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
