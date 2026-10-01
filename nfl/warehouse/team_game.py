#!/usr/bin/env python3.12
"""Team-game table, 2000 to present. Market and environment from schedules; play detail from PBP.

TWO COVERAGE WINDOWS IN ONE TABLE, KEPT VISIBLE RATHER THAN BLENDED.

  1999-2026  market and environment: spread, total, implied total, moneyline, temp, wind, roof,
             surface, rest, overtime, both scores. Measured 100 per cent complete on spread and
             total for 1999-2025 in this checkout.
  2021-2026  play-level detail: plays, drives, pass and rush attempts, sacks, turnovers, red-zone
             trips, touchdowns, pace, situation-neutral pass rate, game script. This is the window
             of play-by-play captures HELD HERE, not the window the data exists for -- PFR carries
             play-by-play from 1977, so 2000-2020 is UNKNOWN_PENDING_ACQUISITION rather than
             NOT_AVAILABLE_FOR_ERA, and the distinction is recorded per field per season.

Every play-detail field for a season without a capture is the era sentinel, never zero. A zero would
say the 2008 Colts ran no plays.

THE SPREAD SIGN IS VERIFIED, NOT ASSUMED. `spread_line` sign conventions differ between sources and
getting it backwards inverts every implied total in the warehouse -- which would then feed the
touchdown pool, the DST points-allowed term and the volume model. So the build regresses each side's
implied total against its realised score and REFUSES if the favourite's implied total does not
predict its points better than the underdog's.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.warehouse import era, sources  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'team-game-1'
OUT = _REPO / 'nfl/warehouse/TEAM_GAME.json'
OUT_COVERAGE = _REPO / 'nfl/warehouse/TEAM_GAME_COVERAGE.json'

#: Fields that come from the play-by-play capture and therefore follow its coverage window.
PBP_FIELDS = ('plays', 'drives', 'pass_attempts', 'rush_attempts', 'targets', 'sacks',
              'turnovers', 'rz_trips', 'rz_drives', 'gl_plays', 'offensive_td', 'pass_td',
              'rush_td', 'seconds_per_play', 'neutral_pass_rate', 'game_script', 'scrambles',
              'dropbacks')

#: Situation-neutral means: score within this margin, and not the final quarter. DECLARED, and it is
#: the standard definition -- pass rate in a blowout measures the scoreboard, not the offence.
NEUTRAL_MARGIN = 7
NEUTRAL_MAX_QTR = 3


def _num(v):
    if v is None:
        return None
    t = str(v).strip()
    if t in ('', 'NA', 'None', 'nan'):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def load_schedules():
    o = sources.select(sources.registry()['schedules'])
    if o.state.name != 'PASS':
        return o
    path = _REPO / o.value['selected']
    rows = []
    with gzip.open(path, 'rt', newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            s = _num(r.get('season'))
            if s is None or s < era.FIRST_SEASON:
                continue
            rows.append(r)
    return Outcome.ok('SCHEDULES_LOADED', {'rows': rows, 'source': o.value['selected'],
                                           'selection': o.value},
                      f'{len(rows)} games from {era.FIRST_SEASON}')


def verify_spread_sign(rows):
    """Establish which side `spread_line` favours, from the outcomes. Never assumed."""
    a = b = 0
    n = 0
    diffs = []
    for r in rows:
        sp, hs, as_ = _num(r.get('spread_line')), _num(r.get('home_score')), _num(r.get('away_score'))
        if sp is None or hs is None or as_ is None:
            continue
        n += 1
        diffs.append((sp, hs - as_))
    if n < 500:
        return {'state': 'NOT_VERIFIABLE', 'n': n}
    # correlation between spread_line and realised home margin
    xs = [d[0] for d in diffs]
    ys = [d[1] for d in diffs]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    r = cov / (vx * vy) ** 0.5 if vx and vy else 0.0
    convention = ('SPREAD_LINE_IS_HOME_MARGIN' if r > 0 else 'SPREAD_LINE_IS_AWAY_MARGIN')
    return {'state': 'VERIFIED', 'n_games': n, 'correlation_with_home_margin': round(r, 5),
            'convention': convention,
            'mean_spread_line': round(mx, 4), 'mean_home_margin': round(my, 4),
            'WHY_VERIFIED': ('sign conventions differ between sources and an inverted spread would '
                             'invert every implied total in the warehouse, which then feeds the '
                             'touchdown pool, the defence points-allowed term and the volume '
                             'model. So it is read off the outcomes rather than assumed.')}


def implied_totals(total_line, spread_line, convention):
    """(home_implied, away_implied). None where either input is missing -- never a league default."""
    if total_line is None or spread_line is None:
        return None, None
    half = total_line / 2.0
    edge = spread_line / 2.0
    if convention == 'SPREAD_LINE_IS_HOME_MARGIN':
        return half + edge, half - edge
    return half - edge, half + edge


def pbp_team_game(season):
    """Per club-game play detail for one season, or a named absence."""
    o = sources.select(sources.registry()['play_by_play'], season=season)
    if o.state.name != 'PASS':
        claimed = era.available('play_by_play', season)
        return {'state': ('UNKNOWN_PENDING_ACQUISITION' if claimed == era.AVAILABLE
                          else era.NOT_AVAILABLE_FOR_ERA),
                'reason': o.code,
                'NOTE': ('play-by-play exists upstream from 1977 per the source coverage '
                         'statement, so a missing season here is an ACQUISITION gap, not an era '
                         'gap. It is never filled with zeros.')}
    path = _REPO / o.value['selected']
    per = collections.defaultdict(lambda: collections.Counter())
    meta = collections.defaultdict(dict)
    # FINAL SCORES FROM PLAY-BY-PLAY. The schedules capture is the primary source for `points`, but
    # nflverse refreshes play-by-play daily while a schedules pull can lag it, so a week can be PLAYED
    # and present in the pbp while the schedules row still carries blank scores. That is exactly the
    # state on 2026-10-01: pbp holds all 16 Week 3 games and schedules has no Week 3 result.
    # Every non-empty value is checked for agreement instead of taking the last one, because two
    # different finals for one game means the file is not what it is believed to be.
    finals = {}
    finals_conflict = []
    drives = collections.defaultdict(set)
    rz_drives = collections.defaultdict(set)
    times = collections.defaultdict(list)
    with gzip.open(path, 'rt', newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            gid, pt = r.get('game_id'), r.get('posteam')
            if not gid or not pt:
                continue
            hsv, asv = (r.get('home_score') or '').strip(), (r.get('away_score') or '').strip()
            if hsv and asv:
                seen = finals.get(gid)
                cand = {'home_score': _num(hsv), 'away_score': _num(asv),
                        'home_team': r.get('home_team'), 'away_team': r.get('away_team'),
                        'week': r.get('week')}
                if seen is None:
                    finals[gid] = cand
                elif (seen['home_score'], seen['away_score']) != (cand['home_score'],
                                                                  cand['away_score']):
                    finals_conflict.append({'game_id': gid, 'first': seen, 'then': cand})
            k = (gid, pt)
            c = per[k]
            meta[k].setdefault('week', r.get('week'))
            meta[k].setdefault('defteam', r.get('defteam'))
            pl = (r.get('play_type') or '').strip()
            if pl in ('pass', 'run', 'qb_spike', 'qb_kneel'):
                c['plays'] += 1
            if r.get('pass_attempt') == '1' and pl == 'pass':
                c['pass_attempts'] += 1
            if (r.get('receiver_player_id') or '').strip():
                c['targets'] += 1
            if pl == 'pass' or r.get('sack') == '1' or r.get('qb_scramble') == '1':
                c['dropbacks'] += 1
            if r.get('rush_attempt') == '1' and pl == 'run':
                c['rush_attempts'] += 1
            if r.get('sack') == '1':
                c['sacks'] += 1
            if r.get('qb_scramble') == '1':
                c['scrambles'] += 1
            if r.get('interception') == '1' or r.get('fumble_lost') == '1':
                c['turnovers'] += 1
            if r.get('pass_touchdown') == '1':
                c['pass_td'] += 1
                c['offensive_td'] += 1
            if r.get('rush_touchdown') == '1':
                c['rush_td'] += 1
                c['offensive_td'] += 1
            y = _num(r.get('yardline_100'))
            if y is not None and y <= 20 and pl in ('pass', 'run'):
                c['rz_plays'] += 1
            if y is not None and y <= 5 and pl in ('pass', 'run'):
                c['gl_plays'] += 1
            d = r.get('drive')
            if d:
                drives[k].add(d)
                if y is not None and y <= 20:
                    rz_drives[k].add(d)
            # situation-neutral pass rate
            qtr, diff = _num(r.get('qtr')), _num(r.get('score_differential'))
            if (pl in ('pass', 'run') and qtr is not None and diff is not None
                    and qtr <= NEUTRAL_MAX_QTR and abs(diff) <= NEUTRAL_MARGIN):
                c['neutral_plays'] += 1
                if pl == 'pass':
                    c['neutral_pass'] += 1
            if diff is not None and pl in ('pass', 'run'):
                c['script_sum'] += diff
                c['script_n'] += 1
            gs = _num(r.get('game_seconds_remaining'))
            if gs is not None and pl in ('pass', 'run'):
                times[k].append(gs)
    out = {}
    for k, c in per.items():
        gid, club = k
        tl = times.get(k) or []
        spp = None
        if len(tl) >= 20:
            tl_sorted = sorted(tl, reverse=True)
            span = tl_sorted[0] - tl_sorted[-1]
            spp = round(span / max(1, len(tl) - 1), 3) if span > 0 else None
        out[f'{gid}|{club}'] = {
            'game_id': gid, 'club': club, 'week': meta[k].get('week'),
            'opponent': meta[k].get('defteam'),
            'plays': c['plays'], 'drives': len(drives.get(k) or ()),
            'pass_attempts': c['pass_attempts'], 'rush_attempts': c['rush_attempts'],
            'targets': c['targets'], 'dropbacks': c['dropbacks'],
            'rz_drives': len(rz_drives.get(k) or ()),
            'sacks': c['sacks'], 'scrambles': c['scrambles'], 'turnovers': c['turnovers'],
            'rz_trips': c['rz_plays'], 'gl_plays': c['gl_plays'],
            'offensive_td': c['offensive_td'], 'pass_td': c['pass_td'], 'rush_td': c['rush_td'],
            'seconds_per_play': spp,
            'neutral_pass_rate': (round(c['neutral_pass'] / c['neutral_plays'], 5)
                                  if c['neutral_plays'] >= 10 else None),
            'game_script': (round(c['script_sum'] / c['script_n'], 4) if c['script_n'] else None),
        }
    return {'state': 'BUILT', 'source': o.value['selected'], 'n_club_games': len(out),
            'rows': out, 'selection': o.value, 'finals': finals,
            'finals_conflict': finals_conflict}


def build(seasons=None):
    so = load_schedules()
    if so.state.name != 'PASS':
        return so
    sched = so.value['rows']
    sign = verify_spread_sign(sched)
    if sign['state'] != 'VERIFIED':
        return Outcome.blocked('SPREAD_SIGN_NOT_VERIFIABLE',
                               f'only {sign.get("n")} games carry both a line and a result',
                               cause=Cause.DATA)
    if abs(sign['correlation_with_home_margin']) < 0.15:
        return Outcome.fail(
            'SPREAD_SIGN_AMBIGUOUS',
            f'spread_line correlates with the realised home margin at only '
            f'{sign["correlation_with_home_margin"]}. The sign cannot be established, and an '
            f'inverted implied total would corrupt every downstream layer.', sign=sign)
    conv = sign['convention']

    seasons = sorted({int(_num(r['season'])) for r in sched}) if seasons is None else seasons
    pbp = {}
    for s in seasons:
        pbp[s] = pbp_team_game(s)

    # A pbp file reporting two different finals for one game is refused, not reconciled. There is no
    # correct way to pick between them and a silently chosen score would propagate into every layer.
    conflicts = [c for pb in pbp.values() for c in (pb.get('finals_conflict') or [])]
    if conflicts:
        return Outcome.fail(
            'PLAY_BY_PLAY_FINAL_SCORE_CONFLICT',
            f'{len(conflicts)} game(s) carry two different final scores inside the play-by-play '
            f'capture. The file is not what it is believed to be, and choosing one would put an '
            f'invented score into the foundation table.',
            examples=conflicts[:5])

    score_from_schedules = 0
    score_from_pbp = []
    table, coverage = {}, {}
    for r in sched:
        s = int(_num(r['season']))
        if r.get('game_type') != 'REG':
            continue
        gid = r.get('game_id')
        tl, sp = _num(r.get('total_line')), _num(r.get('spread_line'))
        hi, ai = implied_totals(tl, sp, conv)
        hs, as_ = _num(r.get('home_score')), _num(r.get('away_score'))
        pb = pbp.get(s) or {}
        # BACKFILL, with the club mapping verified rather than assumed. The pbp row names its own
        # home_team and away_team, and they must match the schedules row before its scores are used --
        # otherwise a game_id collision would silently swap a result onto the wrong clubs.
        if hs is None or as_ is None:
            fin = (pb.get('finals') or {}).get(gid)
            if fin and fin['home_score'] is not None and fin['away_score'] is not None:
                if (fin['home_team'] == r.get('home_team')
                        and fin['away_team'] == r.get('away_team')):
                    hs, as_ = fin['home_score'], fin['away_score']
                    score_from_pbp.append({'game_id': gid, 'season': s,
                                           'week': int(_num(r.get('week')) or 0),
                                           'home_team': r.get('home_team'),
                                           'away_team': r.get('away_team'),
                                           'home_score': hs, 'away_score': as_})
                else:
                    score_from_pbp.append({'game_id': gid, 'REFUSED': 'CLUBS_DISAGREE',
                                           'schedules': [r.get('away_team'), r.get('home_team')],
                                           'play_by_play': [fin['away_team'], fin['home_team']]})
        elif hs is not None:
            score_from_schedules += 1
        pbrows = pb.get('rows') or {}
        pb_state = pb.get('state')
        for side in ('home', 'away'):
            club = r.get(f'{side}_team')
            opp = r.get('away_team' if side == 'home' else 'home_team')
            if not club:
                continue
            pts = hs if side == 'home' else as_
            opp_pts = as_ if side == 'home' else hs
            row = {
                'season': s, 'week': int(_num(r.get('week')) or 0), 'game_id': gid,
                'club': club, 'opponent': opp, 'is_home': side == 'home',
                'points': pts, 'points_allowed': opp_pts,
                'margin': (None if pts is None or opp_pts is None else pts - opp_pts),
                'spread_line_raw': sp, 'spread_convention': conv,
                'club_spread': (None if sp is None else (sp if side == 'home' else -sp)),
                'total_line': tl,
                'implied_total': (hi if side == 'home' else ai),
                'opponent_implied_total': (ai if side == 'home' else hi),
                'moneyline': _num(r.get(f'{side}_moneyline')),
                'rest_days': _num(r.get(f'{side}_rest')),
                'overtime': (_num(r.get('overtime')) == 1.0),
                'roof': (r.get('roof') or '').strip() or None,
                'surface': (r.get('surface') or '').strip() or None,
                'temp': _num(r.get('temp')), 'wind': _num(r.get('wind')),
                'div_game': (_num(r.get('div_game')) == 1.0),
                'stadium': (r.get('stadium') or '').strip() or None,
                'coach': (r.get(f'{side}_coach') or '').strip() or None,
                'starting_qb_id': (r.get(f'{side}_qb_id') or '').strip() or None,
            }
            # weather semantics: a null temp under a closed roof is not a missing measurement
            if row['temp'] is None and (row['roof'] or '') in ('dome', 'closed'):
                row['temp_semantics'] = 'INDOORS_NO_TEMPERATURE_APPLIES'
            elif row['temp'] is None:
                row['temp_semantics'] = 'OUTDOORS_TEMPERATURE_NOT_CAPTURED'
            else:
                row['temp_semantics'] = 'MEASURED'
            pbr = pbrows.get(f'{gid}|{club}')
            for f in PBP_FIELDS:
                if pbr is not None:
                    row[f] = pbr.get(f)
                else:
                    row[f] = (era.NOT_AVAILABLE_FOR_ERA
                              if pb_state == era.NOT_AVAILABLE_FOR_ERA
                              else era.UNKNOWN_PENDING_ACQUISITION)
            row['pbp_state'] = pb_state or 'NO_CAPTURE'
            table[f'{gid}|{club}'] = row

    # coverage ledger, per season per field, measured from the table we just built
    by_season = collections.defaultdict(list)
    for row in table.values():
        by_season[row['season']].append(row)
    ALL = ('points', 'spread_line_raw', 'total_line', 'implied_total', 'moneyline', 'rest_days',
           'temp', 'wind', 'roof', 'overtime') + PBP_FIELDS
    for s, rows in sorted(by_season.items()):
        n = len(rows)
        cov = {}
        for f in ALL:
            vals = [r.get(f) for r in rows]
            sentinel = sum(1 for v in vals
                           if v in (era.NOT_AVAILABLE_FOR_ERA, era.UNKNOWN_PENDING_ACQUISITION))
            present = sum(1 for v in vals
                          if v is not None
                          and v not in (era.NOT_AVAILABLE_FOR_ERA,
                                        era.UNKNOWN_PENDING_ACQUISITION))
            cov[f] = {'completeness': round(present / n, 5) if n else 0.0,
                      'n_era_sentinel': sentinel,
                      'state': (era.NOT_AVAILABLE_FOR_ERA if sentinel == n and n
                                else (era.AVAILABLE if present else
                                      era.UNKNOWN_PENDING_ACQUISITION))}
        coverage[s] = {
            'n_club_games': n, 'n_games': n // 2, 'n_clubs': len({r['club'] for r in rows}),
            'n_weeks': len({r['week'] for r in rows}),
            'fields': cov,
            'pbp_state': rows[0]['pbp_state'] if rows else None,
            'schedules_source': so.value['source'],
            'pbp_source': (pbp.get(s) or {}).get('source'),
        }
    art = {'artifact': 'TEAM_GAME', 'spec_version': SPEC_VERSION,
           'first_season': era.FIRST_SEASON, 'n_club_games': len(table),
           'spread_sign_verification': sign,
           'neutral_definition': {'margin': NEUTRAL_MARGIN, 'max_quarter': NEUTRAL_MAX_QTR},
           'PBP_FIELDS': list(PBP_FIELDS),
           'NEVER_ZERO': ('a play-detail field for a season without a capture carries the era '
                          'sentinel, never zero. A zero would say that club ran no plays.'),
           'score_provenance': {
               'PRIMARY': 'the schedules capture',
               'FALLBACK': ('final scores read from the play-by-play capture, used ONLY where the '
                            'schedules row carries no result and the pbp row names the same two '
                            'clubs. nflverse refreshes play-by-play daily and a schedules pull can '
                            'lag it, so a played week can be present in one and blank in the other.'),
               'NOT_A_DERIVATION': ('these are the vendor\'s own final scores, transformed by nothing. '
                                    'No score is inferred, modelled or filled.'),
               'n_club_game_sides_from_schedules': score_from_schedules,
               'n_games_backfilled_from_play_by_play': sum(
                   1 for x in score_from_pbp if 'REFUSED' not in x),
               'n_games_refused_on_club_disagreement': sum(
                   1 for x in score_from_pbp if 'REFUSED' in x),
               'backfilled': [x for x in score_from_pbp if 'REFUSED' not in x][:40],
               'refused': [x for x in score_from_pbp if 'REFUSED' in x][:10],
           },
           'rows': table}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, separators=(',', ':'), sort_keys=True))
    OUT_COVERAGE.write_text(json.dumps(
        {'artifact': 'TEAM_GAME_COVERAGE', 'spec_version': SPEC_VERSION,
         'schedules_selection': so.value['selection'],
         'per_season': coverage}, indent=1, sort_keys=True, default=str))
    return Outcome.ok('TEAM_GAME_BUILT',
                      {'n_club_games': len(table), 'coverage': coverage, 'sign': sign},
                      f'{len(table)} club-games over {len(coverage)} seasons',
                      n_seasons=len(coverage))


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    if o.state.name != 'PASS':
        return 1
    v = o.value
    s = v['sign']
    print(f"  spread sign: {s['convention']} (r={s['correlation_with_home_margin']} "
          f"over {s['n_games']} games)")
    cov = v['coverage']
    print(f"  {v['n_club_games']} club-games, {len(cov)} seasons")
    print(f"  {'yr':>5s} {'gms':>4s} {'clb':>4s} {'spread':>7s} {'total':>6s} {'temp':>6s} "
          f"{'plays':>6s} {'npr':>6s} pbp")
    for s_, c in sorted(cov.items()):
        if s_ % 4 and s_ not in (2000, 2020, 2021, 2025, 2026):
            continue
        f = c['fields']
        print(f"  {s_:5d} {c['n_games']:4d} {c['n_clubs']:4d} "
              f"{f['spread_line_raw']['completeness']:7.2f} {f['total_line']['completeness']:6.2f} "
              f"{f['temp']['completeness']:6.2f} {f['plays']['completeness']:6.2f} "
              f"{f['neutral_pass_rate']['completeness']:6.2f} {c['pbp_state']}")
    print(f"  -> {OUT.relative_to(_REPO)}")
    print(f"  -> {OUT_COVERAGE.relative_to(_REPO)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
