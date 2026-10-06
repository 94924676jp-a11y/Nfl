#!/usr/bin/env python3.12
"""ATL@NO DraftKings Showdown (2026-10-05) -- immutable POSTGAME_ACTUAL truth package.

    python3.12 nfl/postgame/showdown_atl_no_postgame.py PBP_GZ ENTRY_HISTORY_CSV

Layers kept apart (owner directive 2026-10-06): PRELOCK_FORECAST and PRELOCK_PORTFOLIO are the sealed artifacts in
nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX (and the prop seal); this module writes only POSTGAME_ACTUAL
under nfl/postgame/showdown_atl_no_2026W4/. It reads prelock artifacts, never writes them, and nothing here is an
input to any forecast.

ACTUALS come from nflverse play-by-play for game 2026_04_ATL_NO and are scored with the SAME DK scorer the projection
used (nfl.product.dk_scoring), so a forecast error is football, not two formulas disagreeing. The reconciliation is the
test: every owner entry's lineup (from the sealed upload, joined by Entry ID) is rescored from these actuals and must
equal the DK-reported points for that Entry ID. It also settles the missed-field-goal rule empirically.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import dk_scoring as DKS  # noqa: E402

GAME = '2026_04_ATL_NO'
SD = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
UPLOAD = SD / 'SHOWDOWN_ATL_NO_DK_UPLOAD.csv'
UPLOAD_SHA = '8f4d9a77f37957ab44b116ebc35a950a601fb2a2d39f1d8823f7fd847c6931d5'
OUT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4'
RAW = _REPO / 'nfl/postgame/raw/showdown_atl_no_2026W4'
CONTESTS = ('196285137', '196285160', '196285161')


class PostgameError(RuntimeError):
    pass


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def preserve(pbp_gz, history_csv):
    RAW.mkdir(parents=True, exist_ok=True)
    rec = []
    for src, kind in ((pbp_gz, 'NFLVERSE_PBP_2026'), (history_csv, 'DK_CONTEST_ENTRY_HISTORY_OWNER')):
        h = _sha(src)
        dst = RAW / f'{kind}.{h[:16]}{"".join(pathlib.Path(src).suffixes)}'
        if not dst.exists():
            shutil.copy2(src, dst)
            dst.chmod(0o444)
        rec.append({'kind': kind, 'file': str(dst.relative_to(_REPO)), 'sha256': h})
    if _sha(UPLOAD) != UPLOAD_SHA:
        raise PostgameError('FINAL_UPLOAD_HASH_CHANGED')
    rec.append({'kind': 'FINAL_UPLOAD_PRELOCK_PORTFOLIO', 'file': str(UPLOAD.relative_to(_REPO)), 'sha256': UPLOAD_SHA})
    (RAW / 'PROVENANCE.json').write_text(json.dumps({'captured_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                                                     'files': rec, 'IMMUTABLE': True}, indent=1))
    return rec


def actuals(pbp_gz, state):
    d = pd.read_csv(pbp_gz, low_memory=False)
    g = d[d.game_id == GAME].copy()
    if len(g) < 100:
        raise PostgameError(f'PBP_GAME_TOO_THIN {len(g)} plays')
    f = lambda c: g[c].fillna(0)
    home, away = g.home_team.iloc[0], g.away_team.iloc[0]
    final = {home: int(g.total_home_score.max()), away: int(g.total_away_score.max())}
    st = collections.defaultdict(lambda: collections.Counter())
    for _, r in g.iterrows():
        two = r.get('two_point_conv_result') == 'success'
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
        if r.get('return_touchdown') == 1 and pd.notna(r.get('td_player_id')) and r.get('td_team') == r.get('posteam') \
                and r.get('play_type') in ('kickoff', 'punt'):
            pass   # kick/punt return TDs are by the RECEIVING team; credited below by td_team on special teams
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
    # DST per defending team
    dst = {}
    for team in (home, away):
        opp = away if team == home else home
        dfn = g[g.defteam == team]
        sacks = float(f('sack')[g.defteam == team].sum())
        ints = float(f('interception')[g.defteam == team].sum())
        fr = float(((g.fumble_lost == 1) & (g.defteam == team)).sum())
        # defensive / return TDs scored BY this team when it was not the offence
        dtd = float(((g.return_touchdown == 1) & (g.td_team == team)).sum())
        saf = float(((g.safety == 1) & (g.defteam == team)).sum())
        blk = float((((g.punt_blocked == 1) | (g.field_goal_result == 'blocked') | (g.extra_point_result == 'blocked'))
                     & (g.defteam == team)).sum())
        # points allowed: the opponent's points minus those it scored on non-offensive (return / defensive) TDs
        opp_ret_td = int(((g.return_touchdown == 1) & (g.td_team == opp)).sum())
        pa = final[opp] - 6 * opp_ret_td   # the try after such a TD is still counted by DK as allowed? recorded both ways
        dst[team] = {'sacks': sacks, 'ints': ints, 'fumble_recoveries': fr, 'tds': dtd, 'safeties': saf,
                     'blocked_kicks': blk, 'points_allowed_final': final[opp], 'opp_return_tds': opp_ret_td,
                     'points_allowed_excl_return_td6': pa}
    # map to DK players
    players = {}
    for k, v in state['players'].items():
        nm, tm, pos = v['name'], v['team'], v['position']
        key = f'{nm}|{tm}'
        if pos == 'DST':
            x = dst[tm]
            players[key] = {'pos': 'DST', 'stats': x, 'dk_A': DKS.dst_points(points_allowed=x['points_allowed_final'],
                            sacks=x['sacks'], ints=x['ints'], fumble_recoveries=x['fumble_recoveries'], tds=x['tds'],
                            safeties=x['safeties'], blocked_kicks=x['blocked_kicks']),
                            'dk_B': DKS.dst_points(points_allowed=x['points_allowed_excl_return_td6'], sacks=x['sacks'],
                            ints=x['ints'], fumble_recoveries=x['fumble_recoveries'], tds=x['tds'],
                            safeties=x['safeties'], blocked_kicks=x['blocked_kicks'])}
            continue
        s = st.get(v.get('gsis_id'), collections.Counter())
        if pos == 'K':
            a = (s['fg_lt40'] * DKS.FG_UNDER_40 + s['fg_40s'] * DKS.FG_40_49 + s['fg_50p'] * DKS.FG_50_PLUS
                 + s['xp_made'] * DKS.EXTRA_POINT)
            players[key] = {'pos': 'K', 'stats': dict(s), 'dk_A': float(a), 'dk_B': float(a - s['fg_missed'])}
            continue
        p = float(DKS.skill_points(1, pass_yds=[s['pass_yds']], pass_td=[s['pass_td']], ints=[s['int']],
                                   rush_yds=[s['rush_yds']], rush_td=[s['rush_td']], rec=[s['rec']],
                                   rec_yds=[s['rec_yds']], rec_td=[s['rec_td']], fumbles_lost=[s['fum_lost']])[0])
        p += DKS.realised_extra_points(two_pt=s['two_pt'], return_td=s['return_td'])
        players[key] = {'pos': pos, 'stats': dict(s), 'dk_A': round(p, 2), 'dk_B': round(p, 2)}
    return {'final': final, 'home': home, 'away': away, 'n_plays': int(len(g)), 'dst': dst, 'players': players}


def reconcile(act, state, history_csv):
    by_id = {}
    for v in state['players'].values():
        key = f"{v['name']}|{v['team']}"
        by_id[str(v['cpt_dk_id'])] = (key, 1.5)
        by_id[str(v['flex_dk_id'])] = (key, 1.0)
    hist = {r['Entry_Key']: r for r in csv.DictReader(open(history_csv, encoding='utf-8-sig')) if r['Contest_Key'] in CONTESTS}
    up = list(csv.reader(open(UPLOAD)))
    rows, mism = [], collections.Counter()
    for r in up[1:]:
        eid, cid = r[0], r[2]
        slots = [by_id[x] for x in r[4:10]]
        h = hist.get(eid)
        if h is None:
            raise PostgameError(f'ENTRY_NOT_IN_HISTORY {eid}')
        for rule in ('A', 'B'):
            pts = round(sum(m * act['players'][k][f'dk_{rule}'] for k, m in slots), 2)
            ok = abs(pts - float(h['Points'])) < 0.011
            mism[(rule, ok)] += 1
        ptsA = round(sum(m * act['players'][k]['dk_A'] for k, m in slots), 2)
        ptsB = round(sum(m * act['players'][k]['dk_B'] for k, m in slots), 2)
        win = float(h['Winnings_Non_Ticket'].replace('$', '').replace(',', '') or 0)
        rows.append({'entry_id': eid, 'contest_id': cid, 'captain': slots[0][0], 'flex': [k for k, _ in slots[1:]],
                     'dk_points': float(h['Points']), 'recomputed_rule_A': ptsA, 'recomputed_rule_B': ptsB,
                     'place': int(h['Place']), 'field': int(h['Contest_Entries']),
                     'fee': float(h['Entry_Fee'].replace('$', '')), 'winnings': win,
                     'winnings_ticket': h['Winnings_Ticket'], 'places_paid': int(h['Places_Paid'])})
    return rows, {f'rule_{a}_{"match" if b else "mismatch"}': n for (a, b), n in mism.items()}


def run(pbp_gz, history_csv):
    OUT.mkdir(parents=True, exist_ok=True)
    prov = preserve(pbp_gz, history_csv)
    state = json.loads(next(SD.glob('SHOWDOWN_*_STATE.json')).read_text())
    act = actuals(pbp_gz, state)
    rows, rec = reconcile(act, state, history_csv)
    doc = {'ARTIFACT': 'ATL_NO_POSTGAME_ACTUAL', 'LAYER': 'POSTGAME_ACTUAL', 'game': GAME, 'provenance': prov,
           'final_score': act['final'], 'n_plays': act['n_plays'], 'dst_components': act['dst'],
           'player_actuals': act['players'], 'reconciliation': rec, 'n_entries': len(rows),
           'NOT_A_FORECAST_INPUT': True, 'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    (OUT / 'ATL_NO_POSTGAME_ACTUAL.json').write_text(json.dumps(doc, indent=1, default=float))
    with (OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return doc, rows


if __name__ == '__main__':
    doc, rows = run(sys.argv[1], sys.argv[2])
    print(doc['final_score'], doc['reconciliation'])
    top = sorted(((k, v['dk_A'], v['dk_B']) for k, v in doc['player_actuals'].items()), key=lambda x: -x[1])[:16]
    for t in top:
        print(t)
    print('DST', json.dumps(doc['dst_components']))
