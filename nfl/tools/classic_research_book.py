#!/usr/bin/env python3.12
"""The game research book: every game on a classic slate understood as football before any lineup.

    python3.12 nfl/tools/classic_research_book.py 2026W4

SLATE -> GAME -> TEAM -> UNIT -> POSITION ROOM -> PLAYER -> ROLE -> OPPORTUNITY -> EFFICIENCY ->
CONTEXT -> UNCERTAINTY -> DISTRIBUTION -> DFS / PROP IMPLICATION (owner football_intelligence_graph,
2026-10-03). Built from frozen artifacts and captured evidence only:

  DK_<slate>_EARLY_STATE.json / _PROJ.json / _DRAWS.json / _WORLDS.npz   the proprietary chain
  depth chart capture lawful at the state's as_of                          DECLARED roles, OL, defence
  nflverse play-by-play 2026 (weeks before the slate)                      MEASURED roles
  nflverse snap counts 2026                                                playing time (weeks it covers)
  the captured official injury report (pool_audit.injury_rows)             status of every listed player
  roster captures                                                          names for gsis ids

It never reads FantasyCruncher, a Hard Rock price, or an implied total.

WHAT IT DOES NOT PRETEND. Routes, route participation, alignment (slot/outside), personnel groupings
and pressure are in no capture, and every such field is the string UNAVAILABLE_NO_CAPTURE, never a
zero. Opponent and offensive-line context is OBSERVED ONLY: the projection's game centre is each
offence's own scoring history, so the opposing defence and a missing lineman change no number, and
the book says so on every team. A cascade after an injury is the projection minus the club's observed
usage, which is a description of what the projection did, not a counterfactual.

THE ACCOUNTING GATE. Player pass attempts, targets and carries must sum to the club's totals and the
receiving touchdowns to the passing-touchdown pool, in the projection; the simulator must report its
identities held. If any fails the book's ACCOUNTING state is FAIL and classic_portfolio refuses to
build. Yards closure (receivers' yards vs the quarterback's) is efficiency, not opportunity; it is
reported on every club and does not gate, and the book says that too.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
import hashlib
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
SPEC_VERSION = 'research-book-1'
UNAVAILABLE = 'UNAVAILABLE_NO_CAPTURE'
PBP_GLOB = 'nfl/research/postgame/pbp_{season}.*.csv.gz'
SNAP_GLOB = 'nfl/availability_raw/snap_counts_{season}.*.csv.gz'
ROSTER_GLOB = 'nfl/vintage/weekly_rosters.*.raw.csv.gz'
OL_SLOTS = ('LT', 'LG', 'C', 'RG', 'RT')
DEF_SLOTS = ('LDE', 'RDE', 'LDT', 'RDT', 'NT', 'WLB', 'MLB', 'SLB', 'LILB', 'RILB', 'LOLB', 'ROLB',
             'LCB', 'RCB', 'NB', 'FS', 'SS')
#: football conventions, used as LABELS for observed context, never as model inputs
DEEP_AIR_YARDS = 20          # a deep target
SHORT_AIR_YARDS = 5          # a short / underneath target
RED_ZONE = 20                # yardline_100 at or inside
GOAL_LINE = 5
EXPLOSIVE_PASS = 20          # yards gained
EXPLOSIVE_RUN = 10
ONE_SCORE = 8                # final margin within one score
TWO_SCORES = 16
ACCOUNTING_TOL = 1e-6        # relative; the projection's identities hold by construction


def _p(slate_id, name):
    return OUT_DIR / f'DK_{slate_id}_EARLY_{name}'


def _sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _f(x, nd=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _newest(pattern, *, cover_weeks, season):
    """The capture under `pattern` covering the most of `cover_weeks` (ties: largest file)."""
    best = None
    for f in glob.glob(str(_REPO / pattern.format(season=season))):
        with gzip.open(f, 'rt', newline='') as fh:
            wk = collections.Counter(r.get('week') for r in csv.DictReader(fh))
        cov = sum(1 for w in cover_weeks if wk.get(str(w), 0) > 0)
        full = sum(1 for w in cover_weeks if wk.get(str(w), 0) > 1000)
        key = (cov, full, sum(wk.values()))
        if best is None or key > best[0]:
            best = (key, f, dict(wk))
    return best


# ------------------------------------------------------------------------------- measured usage
def measured_usage(pbp_path, season, weeks):
    """Per gsis id and per club, what weeks `weeks` of play-by-play say each player did."""
    P = collections.defaultdict(lambda: collections.defaultdict(float))
    T = collections.defaultdict(lambda: collections.defaultdict(float))
    D = collections.defaultdict(lambda: collections.defaultdict(float))
    games = collections.defaultdict(set)
    club_games = collections.defaultdict(set)
    wk = {str(w) for w in weeks}
    with gzip.open(pbp_path, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG' or r.get('week') not in wk or not r.get('posteam'):
                continue
            if r.get('two_point_attempt') == '1' or r.get('qb_kneel') == '1' or r.get('qb_spike') == '1':
                continue
            pt, dfn, g = r['posteam'], r.get('defteam'), r['game_id']
            club_games[pt].add(g)
            yl = float(r['yardline_100']) if r.get('yardline_100') not in (None, '', 'NA') else None
            down = r.get('down')
            yg = float(r['yards_gained']) if r.get('yards_gained') not in (None, '', 'NA') else 0.0
            if r.get('pass_attempt') == '1' or r.get('sack') == '1':
                T[pt]['dropbacks'] += 1
                D[dfn]['dropbacks_faced'] += 1
                if r.get('sack') == '1':
                    T[pt]['sacks'] += 1
                    D[dfn]['sacks'] += 1
                    pid = r.get('passer_player_id')
                    if pid and pid != 'NA':
                        P[pid]['sacks_taken'] += 1
                        games[pid].add(g)
            if r.get('pass_attempt') == '1' and r.get('sack') != '1':
                T[pt]['pass_att'] += 1
                D[dfn]['pass_att_faced'] += 1
                if yg >= EXPLOSIVE_PASS:
                    D[dfn]['explosive_pass_allowed'] += 1
                qb = r.get('passer_player_id')
                if qb and qb != 'NA':
                    P[qb]['pass_att'] += 1
                    P[qb]['pass_yards'] += float(r.get('passing_yards') or 0) if r.get('passing_yards') not in ('', 'NA') else 0.0
                    P[qb]['completions'] += r.get('complete_pass') == '1'
                    P[qb]['pass_td'] += r.get('pass_touchdown') == '1'
                    P[qb]['interceptions'] += r.get('interception') == '1'
                    if yl is not None and yl <= RED_ZONE:
                        P[qb]['rz_pass_att'] += 1
                    games[qb].add(g)
                rid = r.get('receiver_player_id')
                if rid and rid != 'NA':
                    ay = float(r['air_yards']) if r.get('air_yards') not in (None, '', 'NA') else None
                    T[pt]['targets'] += 1
                    P[rid]['targets'] += 1
                    P[rid]['receptions'] += r.get('complete_pass') == '1'
                    P[rid]['rec_yards'] += float(r.get('receiving_yards') or 0) if r.get('receiving_yards') not in ('', 'NA') else 0.0
                    P[rid]['rec_td'] += r.get('pass_touchdown') == '1'
                    if ay is not None:
                        P[rid]['air_yards'] += ay
                        P[rid]['targets_with_air'] += 1
                        T[pt]['air_yards'] += ay
                        P[rid]['deep_targets'] += ay >= DEEP_AIR_YARDS
                        P[rid]['short_targets'] += ay <= SHORT_AIR_YARDS
                        T[pt]['deep_targets'] += ay >= DEEP_AIR_YARDS
                        if yl is not None and ay >= yl:
                            P[rid]['end_zone_targets'] += 1
                    if yl is not None and yl <= RED_ZONE:
                        P[rid]['rz_targets'] += 1
                        T[pt]['rz_targets'] += 1
                    if down == '3':
                        P[rid]['third_down_targets'] += 1
                    games[rid].add(g)
            if r.get('rush_attempt') == '1':
                rb = r.get('rusher_player_id')
                T[pt]['carries'] += 1
                D[dfn]['rush_att_faced'] += 1
                if yg >= EXPLOSIVE_RUN:
                    D[dfn]['explosive_run_allowed'] += 1
                if rb and rb != 'NA':
                    P[rb]['carries'] += 1
                    P[rb]['rush_yards'] += float(r.get('rushing_yards') or 0) if r.get('rushing_yards') not in ('', 'NA') else 0.0
                    P[rb]['rush_td'] += r.get('rush_touchdown') == '1'
                    P[rb]['scrambles'] += r.get('qb_scramble') == '1'
                    if down in ('1', '2'):
                        P[rb]['early_down_carries'] += 1
                        T[pt]['early_down_carries'] += 1
                    if down == '3':
                        P[rb]['third_down_carries'] += 1
                    if r.get('ydstogo') not in (None, '', 'NA') and float(r['ydstogo']) <= 2:
                        P[rb]['short_yardage_carries'] += 1
                        T[pt]['short_yardage_carries'] += 1
                    if yl is not None and yl <= RED_ZONE:
                        P[rb]['rz_carries'] += 1
                        T[pt]['rz_carries'] += 1
                    if yl is not None and yl <= GOAL_LINE:
                        P[rb]['gl_carries'] += 1
                        T[pt]['gl_carries'] += 1
                    games[rb].add(g)
            if r.get('touchdown') == '1' and dfn and yl is not None:
                pass
            if yl is not None and yl <= RED_ZONE and (r.get('pass_attempt') == '1' or r.get('rush_attempt') == '1'):
                D[dfn]['rz_plays_faced'] += 1
                D[dfn]['rz_td_allowed'] += (r.get('pass_touchdown') == '1' or r.get('rush_touchdown') == '1')
            if r.get('pass_touchdown') == '1' or r.get('rush_touchdown') == '1':
                T[pt]['off_td'] += 1
    for c, gs in club_games.items():
        T[c]['games'] = len(gs)
    for c in D:
        D[c]['games'] = len(club_games.get(c, ()))
    return ({g: {**dict(v), 'games': len(games[g])} for g, v in P.items()},
            {c: dict(v) for c, v in T.items()}, {c: dict(v) for c, v in D.items()})


def snap_shares(snap_path, season, weeks):
    """(name, team) -> {'weeks': n, 'offense_pct_mean': x} over the weeks the capture covers."""
    acc = collections.defaultdict(list)
    wk = {str(w) for w in weeks}
    with gzip.open(snap_path, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('game_type', 'REG') != 'REG' or r.get('week') not in wk:
                continue
            try:
                acc[(r['player'].strip(), r['team'])].append((int(r['week']), float(r['offense_pct'] or 0)))
            except (ValueError, KeyError):
                continue
    return {k: {'weeks': sorted({w for w, _ in v}), 'offense_pct_mean': round(sum(p for _, p in v) / len(v), 3)}
            for k, v in acc.items()}


def gsis_names():
    out = {}
    for f in sorted(glob.glob(str(_REPO / ROSTER_GLOB))):
        with gzip.open(f, 'rt', newline='') as fh:
            for r in csv.DictReader(fh):
                g, nm = (r.get('gsis_id') or '').strip(), (r.get('full_name') or r.get('player_name') or '').strip()
                if g and nm:
                    out[g] = nm
    return out


def chart_tree(as_of):
    """{club: {slot: [gsis by rank]}} from the newest depth-chart capture lawful at as_of."""
    cut = as_of.replace('-', '').replace(':', '')[:15] + 'Z'
    best = None
    for ln in open(_REPO / 'nfl' / 'vintage_manifest.jsonl'):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get('source') != 'depth_charts' or r.get('state') != 'PASS':
            continue
        cid, b = str(r.get('capture_id') or ''), (r.get('value') or {}).get('blob')
        if cid <= cut and b and (_REPO / b).exists() and (best is None or cid > best[0]):
            best = (cid, b)
    if best is None:
        return None, {}
    rows = list(csv.DictReader(gzip.open(_REPO / best[1], 'rt')))
    out = {}
    for club in {x['team'] for x in rows}:
        last = max(x['dt'] for x in rows if x['team'] == club)
        t = collections.defaultdict(list)
        for x in sorted((x for x in rows if x['team'] == club and x['dt'] == last), key=lambda x: int(x['pos_rank'])):
            t[x['pos_abb']].append(x['gsis_id'])
        out[club] = {'dt': last, 'slots': dict(t)}
    return best[0], out


# ------------------------------------------------------------------------------- worlds
def load_worlds(slate_id):
    from nfl.tools import classic_slate_run as R
    return R.load_worlds(_p(slate_id, 'WORLDS.npz'))


def _q(a, qs=(10, 25, 50, 75, 90)):
    return {f'p{q}': _f(np.percentile(a, q), 2) for q in qs}


def prop_distribution(st, fields, yard_scale):
    """Per-market distribution of one player's stat line, read from the stored worlds."""
    F = {f: i for i, f in enumerate(fields)}

    def col(f):
        v = st[:, F[f]].astype(float)
        return v / yard_scale if f.endswith('yards') else v
    out = {}
    for mk, f in (('pass_yards', 'pass_yards'), ('pass_attempts', 'pass_att'), ('pass_td', 'pass_td'),
                  ('interceptions', 'interceptions'), ('rush_yards', 'rush_yards'), ('carries', 'carries'),
                  ('receptions', 'receptions'), ('rec_yards', 'rec_yards'), ('targets', 'targets')):
        a = col(f)
        if a.mean() <= 0:
            continue
        out[mk] = {'mean': _f(a.mean()), **_q(a)}
    td = col('rush_td') + col('rec_td')
    if td.mean() > 0:
        out['anytime_td'] = {'p_yes': _f((td >= 1).mean(), 4), 'mean_tds': _f(td.mean(), 3)}
    out['NOT_DRAWN'] = ['completions', 'longest reception/rush', 'fumbles']
    out['P_OVER_FROM'] = 'the stored worlds (DK_<slate>_EARLY_WORLDS.npz), never from these percentiles'
    return out


def game_stories(home_pts, away_pts, slate_totals, home, away):
    """Each world's final score classified by football conventions. Shares, not narratives."""
    tot, mar = home_pts + away_pts, home_pts - away_pts
    hi, lo = np.percentile(slate_totals, 75), np.percentile(slate_totals, 25)
    labels = np.empty(len(tot), dtype=object)
    for i in range(len(tot)):
        t, m = tot[i], mar[i]
        lead = home if m > 0 else away
        if t >= hi and abs(m) < ONE_SCORE:
            labels[i] = 'competitive shootout'
        elif t >= hi:
            labels[i] = f'high-scoring, {lead} pulls away'
        elif t <= lo and abs(m) < ONE_SCORE:
            labels[i] = 'close defensive game'
        elif t <= lo:
            labels[i] = f'low-scoring, {lead} controls'
        elif abs(m) >= TWO_SCORES:
            labels[i] = f'{lead} wins by two scores or more'
        elif abs(m) < ONE_SCORE:
            labels[i] = 'one-score game, middling total'
        else:
            labels[i] = f'{lead} by 8-15, middling total'
    return labels, {'total_p75_slate': _f(hi, 1), 'total_p25_slate': _f(lo, 1), 'one_score': ONE_SCORE,
                    'two_scores': TWO_SCORES}


def kickoff_utc(et_naive: str) -> str:
    """'10/04/2026 01:00PM ET' -> ISO UTC, via the IANA zone (EDT/EST handled by the zone rules)."""
    from zoneinfo import ZoneInfo
    t = dt.datetime.strptime(et_naive.replace(' ET', ''), '%m/%d/%Y %I:%M%p').replace(tzinfo=ZoneInfo('America/New_York'))
    return t.astimezone(dt.timezone.utc).isoformat()


# ------------------------------------------------------------------------------- the book
def build(slate_id: str, *, write: bool = True) -> Outcome:
    from nfl.production import pool_audit as PA
    from nfl.tools import classic_slate_run as R
    paths = {n: _p(slate_id, n) for n in ('STATE.json', 'PROJ.json', 'DRAWS.json', 'WORLDS.npz')}
    miss = [n for n, p in paths.items() if not p.exists()]
    if miss:
        return Outcome.blocked('RESEARCH_BOOK_INPUT_MISSING', f'missing {miss}', cause=Cause.NOT_EXECUTED)
    st = json.loads(paths['STATE.json'].read_text())
    pj = json.loads(paths['PROJ.json'].read_text())
    dr = json.loads(paths['DRAWS.json'].read_text())
    proj_sha = _sha(paths['PROJ.json'])
    if dr.get('projection_sha256') != proj_sha:
        return Outcome.fail('RESEARCH_BOOK_DRAWS_NOT_FROM_THIS_PROJECTION', 'draws and projection disagree')
    stats, pts, wmeta = load_worlds(slate_id)
    if wmeta.get('projection_sha256') != proj_sha:
        return Outcome.fail('RESEARCH_BOOK_WORLDS_NOT_FROM_THIS_PROJECTION', 'worlds and projection disagree')
    season, week = int(st['season']), int(st['week'])
    prior_weeks = list(range(1, week))
    pbp = _newest(PBP_GLOB, cover_weeks=prior_weeks, season=season)
    snaps = _newest(SNAP_GLOB, cover_weeks=prior_weeks, season=season)
    if pbp is None or pbp[0][0] < len(prior_weeks):
        return Outcome.blocked('RESEARCH_BOOK_PBP_DOES_NOT_COVER', f'play-by-play for weeks {prior_weeks} not held',
                               cause=Cause.DATA, have=(pbp or [None, None, None])[2])
    PU, TU, DU = measured_usage(pbp[1], season, prior_weeks)
    snap_weeks = [w for w in prior_weeks if snaps and snaps[2].get(str(w), 0) > 1000]
    SN = snap_shares(snaps[1], season, snap_weeks) if snaps and snap_weeks else {}
    names = gsis_names()
    chart_id, CH = chart_tree(st['as_of'])
    clubs = sorted({c for g in st['games'].values() for c in (g['away'], g['home'])})
    inj = PA.injury_rows(season, week, set(clubs), st['as_of'])
    if inj.state.value != 'PASS':
        return inj
    INJ = inj.value or {}

    rows = pj['rows']
    by_key = {f"{r['name']}|{r['team']}": (dk, r) for dk, r in rows.items()}
    sp = {pl['gsis_id']: pl for pl in st['players'].values() if pl.get('gsis_id')}
    key_ix = {k: i for i, k in enumerate(wmeta['keys'])}
    F = list(wmeta['fields'])
    ys = wmeta['yard_scale']
    draws = dr['draws']
    prev = _p(slate_id, 'RESEARCH_BOOK.json')
    prev_doc = json.loads(prev.read_text()) if prev.exists() else None
    prev_proj = {}
    if prev_doc:
        for g in prev_doc.get('games', {}).values():
            for t in g['teams'].values():
                for c in t['players']:
                    prev_proj[c['key']] = c['projection']['dk_mean']
    port = None
    pp = _p(slate_id, 'PORTFOLIOS.json')
    if pp.exists():
        port = json.loads(pp.read_text())
        if (port.get('inputs_sha256', {}).get('proj') != proj_sha
                or port.get('inputs_sha256', {}).get('draws') != _sha(paths['DRAWS.json'])):
            port = None   # a portfolio from other draws must not lend its exposures to this book
    expo = collections.defaultdict(dict)
    if port:
        for c in port['contests']:
            for _n, e in c['report']['player_exposure'].items():
                expo[e['dk_id']][c['profile']] = e['overall']

    def nm(g):
        return names.get(g) or (INJ.get(g) or {}).get('full_name') or g

    def desig(g):
        r = INJ.get(g) or {}
        return {'report_status': (r.get('report_status') or 'NONE_LISTED') if r else 'NOT_ON_REPORT',
                'practice': r.get('practice_status') or None, 'injury': r.get('report_primary_injury') or None}

    def dk_dist(k):
        v = np.asarray(draws.get(k) or [], dtype=float)
        if not len(v):
            return None
        return {'dk_mean': _f(v.mean()), **_q(v), 'p99': _f(np.percentile(v, 99))}

    slate_totals = pts.sum(axis=2).ravel()
    accounting_fail, games_out = [], {}
    ident_by_club = collections.defaultdict(list)
    for x in pj.get('identities') or []:
        ident_by_club[x['club']].append(x)

    for gi, gmeta in enumerate(wmeta['games']):
        gid, home, away = gmeta['game_id'], gmeta['home'], gmeta['away']
        g = st['games'][gid]
        hp, ap_ = pts[gi, :, 0].astype(float), pts[gi, :, 1].astype(float)
        labels, story_def = game_stories(hp, ap_, slate_totals, home, away)
        centre = (pj.get('football_centre') or {}).get(f'{away}@{home}', {})
        teams = {}
        club_worlds_pa = {}
        for club, opp in ((away, home), (home, away)):
            mem = [(dk, r) for dk, r in rows.items() if r['team'] == club]
            pa_w = np.zeros(stats.shape[1])
            for dk, r in mem:
                k = f"{r['name']}|{r['team']}"
                if k in key_ix:
                    pa_w += stats[key_ix[k], :, F.index('pass_att')]
            club_worlds_pa[club] = pa_w
        for club, opp in ((away, home), (home, away)):
            is_home = club == home
            own_pts, opp_pts = (hp, ap_) if is_home else (ap_, hp)
            margin = own_pts - opp_pts
            tv = pj['team_volume'][club]
            tu = TU.get(club, {})
            gp = max(1, tu.get('games', 0))
            mem = sorted(((dk, r) for dk, r in rows.items() if r['team'] == club),
                         key=lambda t: -(t[1].get('dk_points') or 0))
            chart = (CH.get(club) or {}).get('slots', {})
            # ---------------------------------------------------------------- player cards
            cards = []
            for dk, r in mem:
                if r.get('position') == 'DST':
                    continue
                k = f"{r['name']}|{r['team']}"
                pl = st['players'].get(dk) or {}
                gs = r.get('gsis_id')
                mu = PU.get(gs, {}) if gs else {}
                pos = r['position']
                vol_for_rank = 'carries' if pos == 'RB' else 'pass_att' if pos == 'QB' else 'targets'
                # measured usage rank among teammates at the position
                peers = [(x[1].get('gsis_id'), PU.get(x[1].get('gsis_id'), {}).get(vol_for_rank, 0.0))
                         for x in mem if x[1].get('position') == pos]
                order = [p for p, _ in sorted(peers, key=lambda t: -t[1]) if p]
                m_rank = (order.index(gs) + 1) if gs in order and mu.get(vol_for_rank, 0) > 0 else None
                chart_slot = 'PK' if pos == 'K' else pos
                d_rank = (chart.get(chart_slot, []).index(gs) + 1) if gs in chart.get(chart_slot, []) else None
                sh = SN.get((r['name'], club)) or {}
                av = pl.get('current_availability') or {}
                ctx = pl.get('predicted_lineup_context') or {}
                conflicts = []
                if d_rank and m_rank and d_rank != m_rank:
                    conflicts.append(f'depth chart ranks him {pos}{d_rank}; 2026 usage ranks him {pos}{m_rank}')
                if pl.get('depth_usage_rank') and pl.get('depth_rank') and pl['depth_usage_rank'] != pl['depth_rank']:
                    conflicts.append(f"projection used chart rank {pl['depth_rank']} over usage rank {pl['depth_usage_rank']}")
                if ctx.get('state'):
                    conflicts.append('starter by depth chart behind a reported-OUT starter; not confirmed by the club')
                tgt, car = mu.get('targets', 0.0), mu.get('carries', 0.0)
                cv = r.get('conditional_volume') or {}
                prop = None
                if k in key_ix:
                    prop = prop_distribution(stats[key_ix[k]], F, ys)
                dist = dk_dist(k)
                cards.append({
                    'key': k, 'dk_id': dk, 'gsis_id': gs, 'name': r['name'], 'team': club, 'position': pos,
                    'salary': r.get('salary'),
                    'status': {'availability': av.get('status'), 'tier': av.get('tier'),
                               'designation': av.get('designation'), 'practice': av.get('practice_status'),
                               'confirmed_starter': 'NOT_CAPTURED (no club starter confirmations held)',
                               'reported_starter': ctx.get('state') or None,
                               'inactive_state': 'game-day inactives not yet captured'},
                    'depth': {'declared_rank': d_rank, 'measured_usage_rank': m_rank,
                              'projection_depth_rank': pl.get('depth_rank'),
                              'competing': [x[1]['name'] for x in mem if x[1].get('position') == pos and x[0] != dk][:5]},
                    'playing_time': {'offense_snap_share': sh.get('offense_pct_mean'),
                                     'snap_weeks': sh.get('weeks') or snap_weeks,
                                     'route_participation': UNAVAILABLE, 'dropback_participation': UNAVAILABLE,
                                     'games_2026': mu.get('games', 0)},
                    'measured_2026': {
                        'weeks': prior_weeks, 'games': mu.get('games', 0),
                        'targets': mu.get('targets', 0), 'target_share': _f(tgt / tu['targets'], 3) if tu.get('targets') else None,
                        'air_yards': _f(mu.get('air_yards', 0), 0),
                        'air_yard_share': _f(mu.get('air_yards', 0) / tu['air_yards'], 3) if tu.get('air_yards') else None,
                        'adot': _f(mu['air_yards'] / mu['targets_with_air'], 1) if mu.get('targets_with_air') else None,
                        'deep_targets': mu.get('deep_targets', 0), 'short_targets': mu.get('short_targets', 0),
                        'rz_targets': mu.get('rz_targets', 0), 'end_zone_targets': mu.get('end_zone_targets', 0),
                        'third_down_targets': mu.get('third_down_targets', 0),
                        'carries': mu.get('carries', 0), 'carry_share': _f(car / tu['carries'], 3) if tu.get('carries') else None,
                        'early_down_carries': mu.get('early_down_carries', 0), 'third_down_carries': mu.get('third_down_carries', 0),
                        'short_yardage_carries': mu.get('short_yardage_carries', 0),
                        'rz_carries': mu.get('rz_carries', 0), 'gl_carries': mu.get('gl_carries', 0),
                        'scrambles': mu.get('scrambles', 0), 'sacks_taken': mu.get('sacks_taken', 0),
                        'pass_att': mu.get('pass_att', 0), 'rz_pass_att': mu.get('rz_pass_att', 0),
                        'alignment': UNAVAILABLE, 'routes': UNAVAILABLE,
                        'two_minute_role': UNAVAILABLE},
                    'efficiency_measured_2026': {
                        'yards_per_attempt': _f(mu['pass_yards'] / mu['pass_att'], 2) if mu.get('pass_att') else None,
                        'completion_rate': _f(mu['completions'] / mu['pass_att'], 3) if mu.get('pass_att') else None,
                        'yards_per_carry': _f(mu['rush_yards'] / mu['carries'], 2) if mu.get('carries') else None,
                        'yards_per_target': _f(mu['rec_yards'] / mu['targets'], 2) if mu.get('targets') else None,
                        'catch_rate': _f(mu['receptions'] / mu['targets'], 3) if mu.get('targets') else None},
                    'efficiency_projected': {
                        'yards_per_attempt': _f(cv['pass_yards'] / cv['pass_attempts'], 2) if cv.get('pass_yards') and cv.get('pass_attempts') else None,
                        'yards_per_carry': _f(cv['rush_yards'] / cv['carries'], 2) if cv.get('rush_yards') and cv.get('carries') else None,
                        'yards_per_target': _f(cv['rec_yards'] / cv['targets'], 2) if cv.get('rec_yards') and cv.get('targets') else None,
                        'catch_rate': _f(cv['receptions'] / cv['targets'], 3) if cv.get('receptions') and cv.get('targets') else None},
                    'projection': {
                        'dk_mean': (dist or {}).get('dk_mean'), 'dk_projection': _f(r.get('dk_points')),
                        'pass_attempts': _f(r.get('pass_attempts')), 'targets': _f(r.get('targets')),
                        'carries': _f(r.get('carries')), 'receptions': _f(r.get('receptions')),
                        'rec_yards': _f(r.get('rec_yards'), 1), 'rush_yards': _f(r.get('rush_yards'), 1),
                        'pass_yards': _f(r.get('pass_yards'), 1),
                        'rec_rz_opps': _f(r.get('rec_rz_opps')), 'rush_rz_opps': _f(r.get('rush_rz_opps')),
                        'td': {kk: _f(vv, 3) for kk, vv in (r.get('td') or {}).items() if kk in ('rec_td', 'rush_td', 'pass_td')},
                        'role_band': r.get('role_band'), 'distribution': dist,
                        'change_from_previous_run': (_f((dist or {}).get('dk_mean', 0) - prev_proj[k])
                                                     if k in prev_proj and dist else None)},
                    'uncertainty': {'role_confidence': r.get('prior_confidence'), 'prior_tier': r.get('prior_tier'),
                                    'availability_confidence': av.get('tier'),
                                    'sample_games_2026': mu.get('games', 0), 'conflicts': conflicts},
                    'dfs': {'exposure': expo.get(dk) or None,
                            'value_per_1k': _f(((dist or {}).get('dk_mean') or 0) / (r['salary'] / 1000), 2) if r.get('salary') else None},
                    'props': prop,
                })
            # ---------------------------------------------------------------- role labels (descriptive)
            def lab(pos, key, label, minimum=1):
                pool = [c for c in cards if c['position'] == pos and (c['measured_2026'].get(key) or 0) >= minimum]
                if pool:
                    top = max(pool, key=lambda c: c['measured_2026'][key])
                    top.setdefault('role_types', []).append(label)
            lab('RB', 'carries', 'lead runner (most 2026 carries in the room)')
            lab('RB', 'targets', 'receiving back (most RB targets)')
            lab('RB', 'gl_carries', 'goal-line back (most carries inside the 5)')
            lab('RB', 'third_down_targets', 'third-down back (most third-down targets)')
            lab('WR', 'targets', 'target leader at WR')
            lab('WR', 'air_yards', 'air-yards leader at WR')
            lab('TE', 'targets', 'receiving TE (most TE targets)')
            for c in cards:
                if c['position'] == 'TE' and (c['playing_time']['offense_snap_share'] or 0) >= 0.5 \
                        and (c['measured_2026']['target_share'] or 0) < 0.05:
                    c.setdefault('role_types', []).append('snaps without targets: blocking role likely (routes not captured)')
                if c['position'] == 'WR':
                    ad = c['measured_2026']['adot']
                    if ad is not None and c['measured_2026']['targets'] >= 5:
                        c.setdefault('role_types', []).append(
                            'deep' if ad >= 13 else 'intermediate' if ad >= 8 else 'short / possession')
                if c['position'] == 'QB' and c['measured_2026']['pass_att']:
                    designed = c['measured_2026']['carries'] - c['measured_2026']['scrambles']
                    c.setdefault('role_types', []).append(
                        f"designed runs {designed} and scrambles {c['measured_2026']['scrambles']} in "
                        f"{c['measured_2026']['games']} games")
            # ---------------------------------------------------------------- accounting
            acc = {}
            ids = ident_by_club.get(club, [])
            for x in ids:
                ok = x.get('state') == 'OK' and abs((x.get('ratio') or 0) - 1.0) <= ACCOUNTING_TOL
                acc[x['identity']] = {'player_sum': _f(x['player_sum'], 3), 'club_total': _f(x['club_total'], 3),
                                      'state': 'PASS' if ok else 'FAIL'}
                if not ok:
                    accounting_fail.append(f'{club} {x["identity"]}')
            for need in ('pass_attempts', 'targets', 'carries'):
                if need not in acc:
                    acc[need] = {'state': 'FAIL', 'why': 'the projection carries no identity row for it'}
                    accounting_fail.append(f'{club} {need}: no identity row')
            ptd = sum((r.get('td') or {}).get('pass_td', 0) or 0 for _, r in mem)
            rtd = sum((r.get('td') or {}).get('rec_td', 0) or 0 for _, r in mem)
            td_ok = abs(ptd - rtd) <= max(1e-3, 0.01 * max(ptd, rtd))
            acc['receiving_td_eq_passing_td'] = {'qb_pass_td': _f(ptd, 3), 'receiver_rec_td': _f(rtd, 3),
                                                 'state': 'PASS' if td_ok else 'FAIL'}
            if not td_ok:
                accounting_fail.append(f'{club} rec TD {rtd:.3f} vs pass TD {ptd:.3f}')
            off_td = sum(((r.get('td') or {}).get('rec_td', 0) or 0) + ((r.get('td') or {}).get('rush_td', 0) or 0)
                         for _, r in mem)
            acc['offensive_td_expectation'] = _f(off_td, 3)
            rec_y = sum(r.get('rec_yards') or 0 for _, r in mem)
            pass_y = sum(r.get('pass_yards') or 0 for _, r in mem)
            acc['yards_closure_DIAGNOSTIC_NOT_A_GATE'] = {
                'receivers_rec_yards': _f(rec_y, 1), 'qbs_pass_yards': _f(pass_y, 1), 'gap': _f(rec_y - pass_y, 1),
                'WHY_NOT_GATED': 'efficiency, not opportunity; known defect logged 2026-10-03'}
            tg_sum = sum(r.get('targets') or 0 for _, r in mem)
            acc['ghost_targets'] = _f(tv['proj_targets'] - tg_sum, 4)
            # ---------------------------------------------------------------- ecosystems
            qbs = [c for c in cards if c['position'] == 'QB' and (c['projection']['pass_attempts'] or 0) >= 5]
            recv = sorted([c for c in cards if c['position'] in ('WR', 'TE', 'RB') and (c['projection']['targets'] or 0) >= 0.5],
                          key=lambda c: -(c['projection']['targets'] or 0))
            trail = margin <= -ONE_SCORE
            leadw = margin >= ONE_SCORE

            def cond_mean(c, field, mask):
                k = c['key']
                if k not in key_ix or mask.sum() < 50:
                    return None
                v = stats[key_ix[k], :, F.index(field)].astype(float)
                return _f(v[mask].mean())
            tree = [{'name': c['name'], 'pos': c['position'], 'proj_targets': c['projection']['targets'],
                     'share_of_club_targets': _f((c['projection']['targets'] or 0) / tv['proj_targets'], 3),
                     'rz_targets_proj': c['projection']['rec_rz_opps'],
                     'deep_targets_2026': c['measured_2026']['deep_targets'],
                     'targets_if_trailing_by_8+': cond_mean(c, 'targets', trail),
                     'targets_if_leading_by_8+': cond_mean(c, 'targets', leadw)} for c in recv[:10]]
            by_pos_t = collections.Counter()
            for c in cards:
                by_pos_t[c['position']] += c['projection']['targets'] or 0
            qb_eco = None
            if qbs:
                q = max(qbs, key=lambda c: c['projection']['pass_attempts'])
                qb_eco = {
                    'quarterback': q['name'], 'status': q['status'],
                    'club_pass_attempts': _f(tv['proj_pass_attempts'], 1),
                    'his_pass_attempts': q['projection']['pass_attempts'],
                    'efficiency_projected': q['efficiency_projected'], 'efficiency_2026': q['efficiency_measured_2026'],
                    'rushing': {'proj_carries': q['projection']['carries'], 'proj_rush_yards': q['projection']['rush_yards'],
                                'measured': q.get('role_types')},
                    'target_tree': tree,
                    'targets_by_position': {k_: _f(v_, 1) for k_, v_ in by_pos_t.items() if v_},
                    'club_targets': _f(tv['proj_targets'], 1),
                    'throwaways_implied': _f(tv['proj_pass_attempts'] - tv['proj_targets'], 1),
                    'club_pass_attempts_if_trailing_by_8+': _f(club_worlds_pa[club][trail].mean()) if trail.sum() >= 50 else None,
                    'club_pass_attempts_if_leading_by_8+': _f(club_worlds_pa[club][leadw].mean()) if leadw.sum() >= 50 else None,
                    'worlds_trailing_by_8+': _f(trail.mean(), 3), 'worlds_leading_by_8+': _f(leadw.mean(), 3),
                    'MARGIN_IS': 'the simulated FINAL margin, not the in-game score when each play was called'}
            rbs = [c for c in cards if c['position'] == 'RB' and ((c['projection']['carries'] or 0) + (c['projection']['targets'] or 0)) >= 0.5]
            rb_tot = {'carries': sum(c['projection']['carries'] or 0 for c in rbs),
                      'targets': sum(c['projection']['targets'] or 0 for c in rbs),
                      'rz_opps': sum((c['projection']['rush_rz_opps'] or 0) + (c['projection']['rec_rz_opps'] or 0) for c in rbs)}
            rb_eco = {'room_projected': {k_: _f(v_, 2) for k_, v_ in rb_tot.items()},
                      'backs': [{'name': c['name'], 'carry_share_proj': _f((c['projection']['carries'] or 0) / rb_tot['carries'], 3) if rb_tot['carries'] else None,
                                 'target_share_of_rb_proj': _f((c['projection']['targets'] or 0) / rb_tot['targets'], 3) if rb_tot['targets'] else None,
                                 'early_down_carries_2026': c['measured_2026']['early_down_carries'],
                                 'third_down_carries_2026': c['measured_2026']['third_down_carries'],
                                 'third_down_targets_2026': c['measured_2026']['third_down_targets'],
                                 'short_yardage_carries_2026': c['measured_2026']['short_yardage_carries'],
                                 'gl_carries_2026': c['measured_2026']['gl_carries'],
                                 'route_participation': UNAVAILABLE, 'two_minute_share': UNAVAILABLE,
                                 'roles': c.get('role_types', [])} for c in rbs]}
            # ---------------------------------------------------------------- injury cascades
            cascades = []
            for g_, ir in INJ.items():
                if ir.get('team') != club or (ir.get('report_status') or '').lower() != 'out':
                    continue
                vac = PU.get(g_, {})
                pos_ = ir.get('position')
                item = {'player': ir.get('full_name'), 'position': pos_, 'injury': ir.get('report_primary_injury')}
                if pos_ in ('QB', 'RB', 'WR', 'TE', 'FB') and vac.get('games'):
                    gpp = vac['games']
                    item['vacated_per_game_2026'] = {
                        'targets': _f(vac.get('targets', 0) / gpp, 2), 'carries': _f(vac.get('carries', 0) / gpp, 2),
                        'air_yards': _f(vac.get('air_yards', 0) / gpp, 1), 'rz_targets': _f(vac.get('rz_targets', 0) / gpp, 2),
                        'pass_att': _f(vac.get('pass_att', 0) / gpp, 1), 'games': gpp}
                    gains = []
                    for c in cards:
                        m = c['measured_2026']
                        if not m['games']:
                            continue
                        dt_ = (c['projection']['targets'] or 0) - m['targets'] / m['games']
                        dc_ = (c['projection']['carries'] or 0) - m['carries'] / m['games']
                        da_ = (c['projection']['pass_attempts'] or 0) - m['pass_att'] / m['games']
                        if max(dt_, dc_, da_) >= 0.75:
                            gains.append({'name': c['name'], 'pos': c['position'], 'targets_delta': _f(dt_, 2),
                                          'carries_delta': _f(dc_, 2), 'pass_att_delta': _f(da_, 1)})
                    item['who_the_projection_gives_more_to'] = sorted(gains, key=lambda x: -max(x['targets_delta'], x['carries_delta']))[:6]
                    item['te_target_share_proj_vs_2026'] = [
                        _f(by_pos_t['TE'] / tv['proj_targets'], 3),
                        _f(sum(PU.get(c['gsis_id'], {}).get('targets', 0) for c in cards if c['position'] == 'TE') / tu['targets'], 3) if tu.get('targets') else None]
                    item['rb_target_share_proj_vs_2026'] = [
                        _f(by_pos_t['RB'] / tv['proj_targets'], 3),
                        _f(sum(PU.get(c['gsis_id'], {}).get('targets', 0) for c in cards if c['position'] == 'RB') / tu['targets'], 3) if tu.get('targets') else None]
                    item['club_pass_rate_proj_vs_2026'] = [
                        _f(tv['proj_pass_attempts'] / (tv['proj_pass_attempts'] + tv['proj_rush_attempts']), 3),
                        _f(tu.get('pass_att', 0) / (tu.get('pass_att', 0) + tu.get('carries', 0)), 3) if tu.get('pass_att') else None]
                    item['routes_and_snaps_inherited'] = UNAVAILABLE
                    item['READING'] = 'projection minus 2026 observed per game: what the projection did, not a counterfactual'
                else:
                    item['modelled_effect'] = 'NONE: no validated term for this position; context only'
                cascades.append(item)
            # ---------------------------------------------------------------- OL and opponent
            ol = []
            for s_ in OL_SLOTS:
                lst = chart.get(s_, [])
                if not lst:
                    ol.append({'slot': s_, 'starter': UNAVAILABLE})
                    continue
                s0 = lst[0]
                d0 = desig(s0)
                ent = {'slot': s_, 'starter': nm(s0), **d0}
                if d0['report_status'].lower() in ('out', 'doubtful', 'questionable') and len(lst) > 1:
                    ent['next_on_chart'] = nm(lst[1])
                ol.append(ent)
            o_def = DU.get(opp, {})
            ogp = max(1, o_def.get('games', 0))
            dchart = (CH.get(opp) or {}).get('slots', {})
            d_starters = []
            for s_ in DEF_SLOTS:
                if dchart.get(s_):
                    g0 = dchart[s_][0]
                    d0 = desig(g0)
                    d_starters.append({'slot': s_, 'player': nm(g0), **d0})
            opp_layer = {
                'opponent': opp,
                'OBSERVED_CONTEXT_2026': {
                    'games': o_def.get('games', 0),
                    'pass_att_faced_pg': _f(o_def.get('pass_att_faced', 0) / ogp, 1),
                    'rush_att_faced_pg': _f(o_def.get('rush_att_faced', 0) / ogp, 1),
                    'sack_rate': _f(o_def.get('sacks', 0) / o_def['dropbacks_faced'], 3) if o_def.get('dropbacks_faced') else None,
                    'explosive_pass_rate_allowed': _f(o_def.get('explosive_pass_allowed', 0) / o_def['pass_att_faced'], 3) if o_def.get('pass_att_faced') else None,
                    'explosive_run_rate_allowed': _f(o_def.get('explosive_run_allowed', 0) / o_def['rush_att_faced'], 3) if o_def.get('rush_att_faced') else None,
                    'rz_td_per_play_allowed': _f(o_def.get('rz_td_allowed', 0) / o_def['rz_plays_faced'], 3) if o_def.get('rz_plays_faced') else None,
                    'pressure': UNAVAILABLE},
                'defensive_starters_on_chart': d_starters,
                'defenders_out': [x for x in d_starters if x['report_status'].lower() == 'out'],
                'MODELLED_ADJUSTMENT': ('NONE. The game centre is each offence\'s own scoring history; the opposing '
                                        'defence enters no projected number. Carried for reasoning only.')}
            # ---------------------------------------------------------------- correlations (DFS)
            corr = []
            if qb_eco:
                qk = next(c['key'] for c in cards if c['name'] == qb_eco['quarterback'])
                qv = np.asarray(draws.get(qk) or [], dtype=float)
                for c in recv[:8] + [c for c in cards if c['position'] == 'RB'][:2]:
                    v = np.asarray(draws.get(c['key']) or [], dtype=float)
                    if len(v) == len(qv) and v.std() > 0 and qv.std() > 0:
                        corr.append({'with': c['name'], 'pos': c['position'], 'r': _f(np.corrcoef(qv, v)[0, 1], 3)})
                corr.sort(key=lambda x: -x['r'])
            teams[club] = {
                'club': club, 'opponent': opp, 'home': is_home,
                'environment': {'expected_points': _f(centre.get('home_expected' if is_home else 'away_expected'), 1),
                                'proj_pass_attempts': _f(tv['proj_pass_attempts'], 1),
                                'proj_rush_attempts': _f(tv['proj_rush_attempts'], 1),
                                'proj_targets': _f(tv['proj_targets'], 1),
                                'measured_2026_per_game': {'pass_att': _f(tu.get('pass_att', 0) / gp, 1),
                                                           'carries': _f(tu.get('carries', 0) / gp, 1),
                                                           'targets': _f(tu.get('targets', 0) / gp, 1),
                                                           'games': tu.get('games', 0)}},
                'depth_tree_declared': {s_: [nm(x) for x in chart.get(s_, [])[:4]] for s_ in ('QB', 'RB', 'WR', 'TE', 'PK') if chart.get(s_)},
                'offensive_line': {'starters': ol, 'continuity_snaps': UNAVAILABLE if not SN else 'see playing_time on skill cards; OL snaps by name only',
                                   'MODELLED_ADJUSTMENT': 'NONE: no validated offensive-line term; context only'},
                'qb_ecosystem': qb_eco, 'rb_ecosystem': rb_eco,
                'receiver_ecosystem': {'targets_by_position_proj': {k_: _f(v_, 1) for k_, v_ in by_pos_t.items() if v_},
                                       'ghost_targets': acc['ghost_targets'],
                                       'route_share': UNAVAILABLE, 'alignment': UNAVAILABLE},
                'injury_cascades': cascades,
                'opponent_layer': opp_layer,
                'accounting': acc,
                'qb_correlations': corr,
                'players': cards,
            }
        # ---------------------------------------------------------------- game level
        story_rows = []
        for lab_ in collections.Counter(labels).most_common():
            mask = labels == lab_[0]
            story_rows.append({'story': lab_[0], 'share_of_worlds': _f(mask.mean(), 3),
                               'mean_total': _f((hp + ap_)[mask].mean(), 1),
                               'pass_attempts': {c: _f(club_worlds_pa[c][mask].mean(), 1) for c in (away, home)}})
        top_ceiling = []
        for c in (away, home):
            for card in teams[c]['players']:
                d = card['projection']['distribution']
                if d:
                    top_ceiling.append((d['p90'], card['name'], c, card['position']))
        top_ceiling.sort(reverse=True)
        summary = {
            'GAME_ENVIRONMENT': {'football_total': _f(centre.get('total'), 1), 'home_margin': _f(centre.get('home_margin'), 1),
                                 'simulated_total_p10_p50_p90': [_f(np.percentile(hp + ap_, q), 1) for q in (10, 50, 90)],
                                 'basis': centre.get('BASIS')},
            'KEY_ROLE_CHANGES': [f"{cd['name']} ({cd['team']} {cd['position']}): " + '; '.join(cd['uncertainty']['conflicts'])
                                 for c in (away, home) for cd in teams[c]['players']
                                 if cd['uncertainty']['conflicts'] and (cd['projection']['dk_mean'] or 0) >= 6],
            'BEST_UNDERSTOOD': [f"{cd['name']} ({cd['team']} {cd['position']})" for c in (away, home) for cd in teams[c]['players']
                                if cd['uncertainty']['role_confidence'] == 'HIGH' and cd['measured_2026']['games'] >= len(prior_weeks)
                                and not cd['uncertainty']['conflicts'] and (cd['projection']['dk_mean'] or 0) >= 10],
            'LOW_CONFIDENCE': [f"{cd['name']} ({cd['team']} {cd['position']}): " + ', '.join(
                                   x for x in (f"prior {cd['uncertainty']['role_confidence']}" if cd['uncertainty']['role_confidence'] in ('LOW', None) else None,
                                               f"designated {cd['status']['designation']}" if cd['status']['designation'] in ('QUESTIONABLE', 'DOUBTFUL') else None,
                                               'chart-only starter' if cd['status']['reported_starter'] else None,
                                               f"{cd['measured_2026']['games']} games in 2026" if cd['measured_2026']['games'] < 2 else None) if x)
                               for c in (away, home) for cd in teams[c]['players']
                               if (cd['projection']['dk_mean'] or 0) >= 6 and (
                                   cd['uncertainty']['role_confidence'] in ('LOW', None) or cd['status']['reported_starter']
                                   or cd['status']['designation'] in ('QUESTIONABLE', 'DOUBTFUL') or cd['measured_2026']['games'] < 2)],
            'DFS_CORRELATIONS': {c: teams[c]['qb_correlations'][:4] for c in (away, home)},
            'HIGHEST_CEILINGS_P90': [f'{n} {c} {p} {v}' for v, n, c, p in top_ceiling[:6]],
            'PROP_MARKETS_TO_EXAMINE': 'pending the Hard Rock capture; distributions are frozen in this book and the worlds file',
        }
        games_out[gid] = {'game_id': gid, 'away': away, 'home': home, 'kickoff': st['kickoff'],
                          'game_stories': {'definition': story_def, 'stories': story_rows,
                                           'SOURCE': 'the simulated final score of every world in the joint simulation'},
                          'summary': summary, 'teams': teams}
    state = 'PASS' if not accounting_fail else 'FAIL'
    doc = {
        'ARTIFACT': 'CLASSIC_RESEARCH_BOOK', 'spec_version': SPEC_VERSION, 'slate_id': slate_id,
        'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'as_of': st['as_of'],
        'inputs_sha256': {n: _sha(p) for n, p in paths.items()},
        'evidence': {'pbp': {'file': str(pathlib.Path(pbp[1]).relative_to(_REPO)), 'weeks': pbp[2]},
                     'snap_counts': {'file': str(pathlib.Path(snaps[1]).relative_to(_REPO)) if snaps else None,
                                     'weeks_used': snap_weeks, 'weeks_held': snaps[2] if snaps else None},
                     'depth_chart_capture': chart_id, 'injury_report': 'pool_audit.injury_rows (captured)'},
        'NOT_CAPTURED': ['routes / route participation', 'alignment (slot/outside)', 'personnel groupings',
                         'pressure', 'two-minute roles', 'club starter confirmations', 'game-day inactives'],
        'ACCOUNTING': {'state': state, 'failures': accounting_fail,
                       'simulator_identities_held': sorted({x for v in dr['per_game'].values()
                                                            for x in ((v.get('identities') or {}).get('IDENTITIES_HELD') or [])})},
        'games': games_out,
        'FREEZE': {'worlds_sha256': _sha(paths['WORLDS.npz']), 'projection_sha256': proj_sha,
                   'MEANING': 'the proprietary distributions are fixed by these hashes before any Hard Rock price is read'},
    }
    out = _p(slate_id, 'RESEARCH_BOOK.json')
    if write:
        if prev.exists():
            prev.replace(_p(slate_id, 'RESEARCH_BOOK.previous.json'))
        out.write_text(json.dumps(doc, indent=1, default=str))
        # THE SEAL. Written once the book exists, so its time is a true upper bound on when the
        # proprietary distributions were fixed. price_history.comparable() refuses any price captured
        # before it: a line that existed while the forecast was being built is no test of the forecast.
        # Same projection and worlds -> same frozen distributions -> the ORIGINAL seal time stands;
        # only the book hash is refreshed (a rebuild that adds portfolio exposures changes no number).
        sp_ = _p(slate_id, 'SEAL.json')
        old_seal = json.loads(sp_.read_text()) if sp_.exists() else {}
        same = (old_seal.get('projection_sha256') == proj_sha
                and old_seal.get('worlds_sha256') == doc['FREEZE']['worlds_sha256'])
        seal_doc = {
            'ARTIFACT': 'CLASSIC_FORECAST_SEAL', 'slate_id': slate_id,
            'written_at': old_seal['written_at'] if same else dt.datetime.now(dt.timezone.utc).isoformat(),
            'resealed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'kickoff_utc': kickoff_utc(st['kickoff']),
            'projection_sha256': proj_sha, 'worlds_sha256': doc['FREEZE']['worlds_sha256'],
            'research_book_sha256': _sha(out)}
        sp_.write_text(json.dumps(seal_doc, indent=1))
        with open(_p(slate_id, 'SEAL_HISTORY.jsonl'), 'a') as fh:   # append-only: every seal ever written
            fh.write(json.dumps(seal_doc, sort_keys=True) + '\n')
    n_cards = sum(len(t['players']) for g in games_out.values() for t in g['teams'].values())
    if accounting_fail:
        return Outcome.fail('RESEARCH_BOOK_ACCOUNTING_FAILED', f'{len(accounting_fail)} failure(s): {accounting_fail[:4]}',
                            failures=accounting_fail, path=str(out.relative_to(_REPO)))
    return Outcome.measured('RESEARCH_BOOK_BUILT', {'n_games': len(games_out), 'n_cards': n_cards}, n_measured=n_cards,
                            what='player role cards', detail=f'{len(games_out)} games, {n_cards} cards, accounting PASS',
                            path=str(out.relative_to(_REPO)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    o = build(ap.parse_args().slate_id)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
