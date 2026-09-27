#!/usr/bin/env python3.12
"""Per-player, per-week usage across 2024-2026. The panel the player prior needs.

WHY THIS EXISTS. V0 had no player-level prior, so it shrank every receiver toward the mean of
a population where 40 of 96 held under a 5% target share. Ja'Marr Chase came out at 7.82
against FantasyCruncher's 27.08 on the strength of two quiet games, because nothing in the
model knew who he had been. This panel is what fixes that, and its inputs were already in the
repository: pbp_2024 (49,492 rows), pbp_2025 (48,771) and pbp_2026 (2,756), 22 weeks each for
the complete seasons.

WHAT IS COUNTED AND WHAT IS NOT. Regular season only, because a January playoff game is not
a sample from the same population as a week-3 Sunday. Two-point conversions are excluded from
attempt counts -- they are not plays from scrimmage in the volume sense -- but the panel keeps
them separately so nothing is silently dropped.

THREE STATES, NEVER TWO. A player-week row exists only when that player appears in the
play-by-play with an opportunity. Absence of a row is UNKNOWN: it may mean he did not play, or
played and touched nothing, or was not in the league. The panel records which, per season, so
a downstream prior can tell a rookie apart from a healthy scratch. Collapsing those is the
same defect as reading missing as zero.

TEAM VOLUME IS COUNTED ONCE PER TEAM-WEEK, not summed from players. Summing player rows would
double-count a play with both a rusher and a receiver, and would miss plays with neither.
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
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'usage-history-1'
VINTAGE = _REPO / 'nfl/vintage'
OUT = _REPO / 'nfl/derived/USAGE_HISTORY_2021_2026.json'
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
REG = 'REG'

NEEDED = ('season', 'week', 'season_type', 'posteam', 'defteam', 'play_type',
          'passer_player_id', 'rusher_player_id', 'receiver_player_id',
          'pass_attempt', 'rush_attempt', 'complete_pass', 'air_yards', 'yards_gained',
          'passing_yards', 'rushing_yards', 'receiving_yards', 'touchdown',
          'pass_touchdown', 'rush_touchdown', 'td_player_id', 'yardline_100',
          'sack', 'interception', 'two_point_attempt', 'qb_scramble', 'qb_dropback')

RZ, GL = 20.0, 5.0


def _f(v):
    if v in (None, '', 'NA'):
        return None
    try:
        return float(v)
    except ValueError:
        return None


SEARCH_DIRS = ('nfl/research/postgame', 'nfl/vintage')


def _blob(season):
    """The WIDEST capture for a season, plus every capture it rejected.

    THIS FUNCTION EXISTS BECAUSE THE FIRST VERSION TOOK THE FIRST FILE IT FOUND AND GOT A
    STALE ONE. Four pbp_2026 captures exist. `nfl/vintage/pbp_2026.b69f55a172965e16` sounds
    like the authoritative copy and holds week 1 only, 2,756 rows; the complete capture is
    `nfl/research/postgame/pbp_2026.6643f82adb1158c8` with weeks 1-2 and 5,489 rows. Taking
    the vintage file silently halved the current season and would have halved the weight the
    prior gives to 2026.

    So selection is by measured week coverage, and the rejected candidates are recorded in
    the artifact. A future stale capture cannot be chosen quietly.
    """
    cands = []
    for d in SEARCH_DIRS:
        for f in sorted((_REPO / d).glob(f'pbp_{season}.*.csv.gz')):
            weeks, rows = set(), 0
            with gzip.open(f, 'rt', newline='') as fh:
                for r in csv.DictReader(fh):
                    rows += 1
                    if (r.get('season_type') or '').upper() == REG:
                        w = r.get('week')
                        if w and w.isdigit():
                            weeks.add(int(w))
            cands.append({'path': str(f.relative_to(_REPO)), 'n_rows': rows,
                          'n_reg_weeks': len(weeks),
                          'week_span': [min(weeks), max(weeks)] if weeks else None,
                          'file': f})
    if not cands:
        return None, []
    cands.sort(key=lambda c: (-c['n_reg_weeks'], -c['n_rows']))
    chosen = cands[0]
    rejected = [{k: v for k, v in c.items() if k != 'file'} for c in cands[1:]]
    return chosen, rejected


def _zero_player():
    return {
        'targets': 0, 'receptions': 0, 'rec_yards': 0.0, 'air_yards': 0.0, 'rec_td': 0,
        'carries': 0, 'rush_yards': 0.0, 'rush_td': 0,
        'pass_attempts': 0, 'completions': 0, 'pass_yards': 0.0, 'pass_td': 0,
        'interceptions': 0, 'sacks_taken': 0, 'dropbacks': 0, 'scrambles': 0,
        'rz_targets': 0, 'rz_carries': 0, 'gl_targets': 0, 'gl_carries': 0,
        'two_point_targets': 0, 'two_point_carries': 0,
        # THE TEAM IS RECORDED PER PLAYER-WEEK. Without it a player's share has to be
        # divided by a LEAGUE-MEDIAN team-week, which produced Aaron Rodgers at a
        # pass-attempt share of 1.0259 -- above 1.0, and therefore impossible rather than
        # approximate. A share must be divided by the denominator it actually came from.
        'team': None,
    }


def _zero_team():
    return {'plays': 0, 'dropbacks': 0, 'pass_attempts': 0, 'rush_attempts': 0,
            'targets': 0, 'team_td': 0, 'rz_plays': 0, 'gl_plays': 0, 'sacks': 0}


def extract_season(season):
    chosen, rejected = _blob(season)
    if chosen is None:
        return Outcome.blocked('PBP_SEASON_ABSENT', f'no pbp blob for {season}',
                               cause=Cause.DATA)
    p = chosen['file']
    players = collections.defaultdict(_zero_player)   # (gsis, season, week) -> counts
    teams = collections.defaultdict(_zero_team)       # (team, season, week) -> counts
    seen_weeks = collections.defaultdict(set)         # gsis -> weeks appearing at all
    n_rows = n_reg = 0
    with gzip.open(p, 'rt', newline='') as fh:
        rd = csv.DictReader(fh)
        missing = [c for c in NEEDED if c not in (rd.fieldnames or ())]
        if missing:
            return Outcome.fail('PBP_SCHEMA', f'{season} lacks {missing}')
        for r in rd:
            n_rows += 1
            if (r.get('season_type') or '').upper() != REG:
                continue
            n_reg += 1
            wk = _f(r.get('week'))
            team = (r.get('posteam') or '').strip()
            if wk is None or not team:
                continue
            wk = int(wk)
            tk = (team, season, wk)
            t = teams[tk]
            two = _f(r.get('two_point_attempt')) == 1.0
            pa = _f(r.get('pass_attempt')) == 1.0
            ra = _f(r.get('rush_attempt')) == 1.0
            sack = _f(r.get('sack')) == 1.0
            yl = _f(r.get('yardline_100'))
            in_rz = yl is not None and yl <= RZ
            in_gl = yl is not None and yl <= GL

            if not two:
                t['plays'] += 1
                if in_rz:
                    t['rz_plays'] += 1
                if in_gl:
                    t['gl_plays'] += 1
                if _f(r.get('qb_dropback')) == 1.0 or pa or sack:
                    t['dropbacks'] += 1
                if pa:
                    t['pass_attempts'] += 1
                if ra:
                    t['rush_attempts'] += 1
                if sack:
                    t['sacks'] += 1
            if _f(r.get('touchdown')) == 1.0 and not two:
                t['team_td'] += 1

            rec = (r.get('receiver_player_id') or '').strip()
            rush = (r.get('rusher_player_id') or '').strip()
            pas = (r.get('passer_player_id') or '').strip()

            if rec:
                seen_weeks[rec].add(wk)
                d = players[(rec, season, wk)]
                d['team'] = d['team'] or team
                if two:
                    d['two_point_targets'] += 1
                elif pa:
                    d['targets'] += 1
                    t['targets'] += 1
                    d['air_yards'] += _f(r.get('air_yards')) or 0.0
                    if _f(r.get('complete_pass')) == 1.0:
                        d['receptions'] += 1
                        d['rec_yards'] += _f(r.get('receiving_yards')) or 0.0
                    if in_rz:
                        d['rz_targets'] += 1
                    if in_gl:
                        d['gl_targets'] += 1
            if rush:
                seen_weeks[rush].add(wk)
                d = players[(rush, season, wk)]
                d['team'] = d['team'] or team
                if two:
                    d['two_point_carries'] += 1
                elif ra:
                    d['carries'] += 1
                    d['rush_yards'] += _f(r.get('rushing_yards')) or 0.0
                    if in_rz:
                        d['rz_carries'] += 1
                    if in_gl:
                        d['gl_carries'] += 1
            if pas:
                seen_weeks[pas].add(wk)
                d = players[(pas, season, wk)]
                d['team'] = d['team'] or team
                if not two:
                    if pa:
                        d['pass_attempts'] += 1
                        d['pass_yards'] += _f(r.get('passing_yards')) or 0.0
                        if _f(r.get('complete_pass')) == 1.0:
                            d['completions'] += 1
                        if _f(r.get('interception')) == 1.0:
                            d['interceptions'] += 1
                    if sack:
                        d['sacks_taken'] += 1
                    if _f(r.get('qb_dropback')) == 1.0 or pa or sack:
                        d['dropbacks'] += 1
                    if _f(r.get('qb_scramble')) == 1.0:
                        d['scrambles'] += 1

            # touchdowns are attributed by td_player_id, never inferred from the play row
            tdp = (r.get('td_player_id') or '').strip()
            if tdp and not two and _f(r.get('touchdown')) == 1.0:
                d = players[(tdp, season, wk)]
                d['team'] = d['team'] or team
                if _f(r.get('pass_touchdown')) == 1.0:
                    d['rec_td'] += 1
                elif _f(r.get('rush_touchdown')) == 1.0:
                    d['rush_td'] += 1
                if pas and _f(r.get('pass_touchdown')) == 1.0:
                    players[(pas, season, wk)]['pass_td'] += 1

    return Outcome.ok('SEASON_EXTRACTED',
                      {'players': players, 'teams': teams, 'seen_weeks': seen_weeks},
                      f'{season}: {n_reg} regular-season rows of {n_rows}',
                      season=season, n_rows=n_rows, n_reg=n_reg,
                      n_player_weeks=len(players), n_team_weeks=len(teams),
                      blob=chosen['path'], n_reg_weeks=chosen['n_reg_weeks'],
                      week_span=chosen['week_span'],
                      rejected_captures=rejected,
                      sha256=hashlib.sha256(p.read_bytes()).hexdigest()[:16])


def build():
    panel, team_panel, prov = {}, {}, {}
    for season in SEASONS:
        r = extract_season(season)
        if r.state.value != 'PASS':
            return r
        prov[str(season)] = dict(r.evidence)
        for (gsis, s, wk), d in r.value['players'].items():
            panel.setdefault(gsis, {}).setdefault(str(s), {})[str(wk)] = d
        for (team, s, wk), d in r.value['teams'].items():
            team_panel.setdefault(team, {}).setdefault(str(s), {})[str(wk)] = d

    art = {
        'artifact': 'USAGE_HISTORY_2021_2026', 'spec_version': SPEC_VERSION,
        'seasons': list(SEASONS), 'season_type': 'REG only',
        'SEMANTICS': {
            'ABSENT_ROW_IS_UNKNOWN': (
                'a player-week row exists only where the player appears with an '
                'opportunity. No row means UNKNOWN -- did not play, played and touched '
                'nothing, or was not in the league. Never zero.'),
            'TEAM_VOLUME_COUNTED_ONCE': (
                'team counts come from the play rows themselves, not from summing players. '
                'Summing would double-count a play with a rusher and a receiver and miss '
                'plays with neither.'),
            'TWO_POINT_SEPARATED': (
                'two-point conversions are excluded from attempt and volume counts and kept '
                'in their own fields, so they are neither counted as scrimmage volume nor '
                'silently dropped.'),
            'TEAM_ON_EVERY_PLAYER_WEEK': (
                'each player-week records the club whose plays it came from, so a share is '
                'always divided by that club own team-week. An earlier build omitted it and '
                'fell back to a league-median denominator, which produced a pass-attempt '
                'share above 1.0.'),
            'WIDEST_CAPTURE_CHOSEN': (
                'where several captures exist for a season the one with the most regular '
                'season weeks is used, and the rejected candidates are listed under '
                'provenance. Four pbp_2026 captures exist and the nfl/vintage copy is week 1 '
                'only -- taking the first file found silently halved the current season.'),
            'TD_BY_ATTRIBUTION': (
                'touchdowns are attributed from td_player_id, never inferred from a play '
                'row, so a receiving score is not credited to a rusher on the same snap.'),
        },
        'provenance': prov,
        'n_players': len(panel), 'n_teams': len(team_panel),
        'players': panel, 'teams': team_panel,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art) + '\n')
    return Outcome.ok('USAGE_HISTORY_BUILT', art,
                      f'{len(panel)} players, {len(team_panel)} teams',
                      n_players=len(panel), n_teams=len(team_panel),
                      bytes=OUT.stat().st_size)


def main() -> int:
    r = build()
    print(r)
    if r.state.value != 'PASS':
        return 1
    a = r.value
    for s, p in a['provenance'].items():
        print(f"  {s}: {p['n_reg']:6d} reg rows  {p['n_reg_weeks']:2d} wks  "
              f"{p['n_player_weeks']:5d} player-weeks  {p['n_team_weeks']:4d} team-weeks  "
              f"{p['blob'].split('/')[-1]}"
              + (f"  [rejected {len(p['rejected_captures'])}]"
                 if p['rejected_captures'] else ''))
    # spot-check the player the whole exercise is about
    import collections as C
    for name, gsis in (("Ja'Marr Chase", '00-0036900'),):
        pass
    tot = C.Counter()
    for gsis, seasons in a['players'].items():
        for s, weeks in seasons.items():
            tot[s] += len(weeks)
    print(f"  player-weeks by season: {dict(sorted(tot.items()))}")
    print(f"  artifact {OUT.relative_to(_REPO)} {OUT.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
