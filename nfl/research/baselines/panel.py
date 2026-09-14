"""The lawful historical player-game panel, built from play-by-play.

CHRONOLOGY IS A GUARD, NOT A CONVENTION.

`LAWFUL_SEASONS` is (2021, 2022, 2023, 2024) and the loader refuses anything
else by raising `ChronologyRefused`. It resolves each season's blob by an
EXACT-SEASON glob, never `pbp_20*`: a prior agent on this project globbed
`pbp_20*` and pulled 2026 -- one game of which (DEN@KC) was still unplayed and
the rest are this season's own outcomes -- into a frame it then called
historical. A comment would not have stopped that. A refusal does.

GROUPING IS BY `(game_id, posteam)`, NEVER BY GAME.

Grouping by game alone silently selects the better of the two starting
quarterbacks and inflates every passing quantity. That error was made and
corrected once already in this session's work.

KNEELS ARE EXCLUDED (`qb_kneel != '1'`), which removes both the quarterback's
negative carries and the team rush attempts that are a function of the score
rather than of the offence.

EVERY STAGE ASSERTS ITS OUTPUT. An empty read, a season with no games, a
player-game whose completions exceed its attempts: each raises a named error
rather than returning a smaller number quietly.
"""
from __future__ import annotations

import collections
import csv
import gzip
import glob
import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
POSTGAME = os.path.join(REPO, 'nfl', 'research', 'postgame')
PANEL_P3 = os.path.join(REPO, 'nfl', 'research', 'inputs', 'panel_p3.csv.gz')

#: The only seasons this module will read. 2025 has no play-by-play blob in
#: this repository and 2026 is the live season, whose outcomes are the thing a
#: baseline is supposed to be judged against.
LAWFUL_SEASONS = (2021, 2022, 2023, 2024)

#: Regular season only. Postseason has a different team population (the
#: fourteen that qualified) and a different week numbering, so pooling it into
#: a per-game mean changes the estimand without saying so.
SEASON_TYPE = 'REG'

QUANTITIES = (
    'pass_att', 'pass_cmp', 'pass_yds', 'pass_td', 'pass_int',
    'carries', 'rush_yds', 'rush_td',
    'targets', 'receptions', 'rec_yds', 'rec_td',
)
TEAM_QUANTITIES = ('team_plays', 'team_pass_att', 'team_rush_att',
                   'team_dropbacks')


class ChronologyRefused(Exception):
    """A season outside `LAWFUL_SEASONS` was requested."""


class EmptyRead(Exception):
    """A read returned nothing, or nothing that survived the filters."""


class PanelContract(Exception):
    """A built row violates an arithmetic identity it must satisfy."""


def blob_for(season: int) -> str:
    """The one play-by-play blob for `season`, or a refusal.

    The glob is `pbp_{season}.*.csv.gz` with the season interpolated, so no
    wildcard can reach an adjacent season. Requiring EXACTLY one match is
    itself a guard: two blobs for one season means an ambiguous data identity
    and the caller must not be handed either of them silently.
    """
    if season not in LAWFUL_SEASONS:
        raise ChronologyRefused(
            f'BASELINE_CHRONOLOGY_REFUSED: season {season} is not in '
            f'{LAWFUL_SEASONS}. 2025 has no blob here and 2026 is the live '
            f'season whose outcomes a baseline is measured against, so '
            f'reading it would make the baseline unbeatable rather than '
            f'informative.')
    hits = sorted(glob.glob(os.path.join(POSTGAME, f'pbp_{season}.*.csv.gz')))
    if len(hits) != 1:
        raise EmptyRead(
            f'BASELINE_BLOB_NOT_UNIQUE: season {season} matched {len(hits)} '
            f'play-by-play blobs in {POSTGAME}; exactly one is required.')
    return hits[0]


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def data_identity() -> dict:
    """The exact bytes this panel is a function of. Part of every spec hash."""
    out = {}
    for season in LAWFUL_SEASONS:
        p = blob_for(season)
        out[str(season)] = {'blob': os.path.relpath(p, REPO),
                            'sha256': sha256_of(p)}
    out['position_source'] = {
        'blob': os.path.relpath(PANEL_P3, REPO),
        'sha256': sha256_of(PANEL_P3),
        'note': 'position labels only; no quantity is taken from this file',
    }
    return out


def _f(s: str) -> float:
    return float(s) if s not in ('', 'NA', 'None', None) else 0.0


def _one(s: str) -> int:
    return 1 if s == '1' else 0


def build_season(season: int) -> tuple[dict, dict, dict]:
    """(player_rows, team_rows, audit) for one lawful season.

    `player_rows` is keyed `(game_id, team, gsis_id)`, `team_rows` is keyed
    `(game_id, team)`. Both keys carry the team, which is what makes the
    `(game_id, posteam)` grouping structural rather than a convention a later
    caller can forget.
    """
    path = blob_for(season)
    players: dict = {}
    teams: dict = {}
    audit = collections.Counter()
    with gzip.open(path, 'rt', newline='') as fh:
        rdr = csv.reader(fh)
        hdr = next(rdr)
        ix = {h: i for i, h in enumerate(hdr)}
        need = ('game_id', 'posteam', 'defteam', 'week', 'season_type',
                'qb_kneel', 'play_type', 'sack', 'two_point_attempt',
                'passer_player_id', 'receiver_player_id', 'rusher_player_id',
                'complete_pass', 'incomplete_pass', 'interception',
                'passing_yards', 'receiving_yards', 'rushing_yards',
                'pass_touchdown', 'rush_touchdown', 'rush_attempt',
                'qb_dropback', 'play_deleted')
        missing = [c for c in need if c not in ix]
        if missing:
            raise EmptyRead(
                f'BASELINE_PBP_SCHEMA_MISSING: {path} lacks {missing}. Field '
                f'names are read from the header, never guessed.')
        for row in rdr:
            audit['rows_total'] += 1
            if row[ix['season_type']] != SEASON_TYPE:
                audit['drop_season_type'] += 1
                continue
            if row[ix['play_deleted']] == '1':
                audit['drop_play_deleted'] += 1
                continue
            if row[ix['qb_kneel']] == '1':
                audit['drop_kneel'] += 1
                continue
            team = row[ix['posteam']]
            gid = row[ix['game_id']]
            if not team or not gid:
                audit['drop_no_posteam'] += 1
                continue
            week = int(row[ix['week']])
            tk = (gid, team)
            t = teams.get(tk)
            if t is None:
                t = teams[tk] = dict(
                    season=season, week=week, game_id=gid, team=team,
                    opponent=row[ix['defteam']],
                    team_plays=0, team_pass_att=0, team_rush_att=0,
                    team_dropbacks=0, team_sacks=0)
            t['team_dropbacks'] += _one(row[ix['qb_dropback']])

            def cell(pid):
                k = (gid, team, pid)
                r = players.get(k)
                if r is None:
                    r = players[k] = dict(
                        season=season, week=week, game_id=gid, team=team,
                        opponent=row[ix['defteam']], gsis_id=pid,
                        **{q: 0.0 for q in QUANTITIES})
                return r

            ptype = row[ix['play_type']]
            two = row[ix['two_point_attempt']] == '1'
            sack = row[ix['sack']] == '1'
            comp = _one(row[ix['complete_pass']])
            inc = _one(row[ix['incomplete_pass']])
            intc = _one(row[ix['interception']])
            if ptype == 'pass' and not two:
                if sack:
                    t['team_sacks'] += 1
                    t['team_plays'] += 1
                    continue
                att = comp + inc + intc
                pid = row[ix['passer_player_id']]
                if pid and att:
                    c = cell(pid)
                    c['pass_att'] += att
                    c['pass_cmp'] += comp
                    c['pass_int'] += intc
                    c['pass_yds'] += _f(row[ix['passing_yards']])
                    c['pass_td'] += _one(row[ix['pass_touchdown']])
                    t['team_pass_att'] += att
                    t['team_plays'] += att
                rid = row[ix['receiver_player_id']]
                if rid and att:
                    c = cell(rid)
                    c['targets'] += att
                    c['receptions'] += comp
                    c['rec_yds'] += _f(row[ix['receiving_yards']])
                    c['rec_td'] += _one(row[ix['pass_touchdown']]) * comp
            elif ptype == 'run' and not two:
                ra = _one(row[ix['rush_attempt']])
                pid = row[ix['rusher_player_id']]
                if pid and ra:
                    c = cell(pid)
                    c['carries'] += ra
                    c['rush_yds'] += _f(row[ix['rushing_yards']])
                    c['rush_td'] += _one(row[ix['rush_touchdown']])
                    t['team_rush_att'] += ra
                    t['team_plays'] += ra
    if not players or not teams:
        raise EmptyRead(
            f'BASELINE_PANEL_EMPTY: season {season} produced '
            f'{len(players)} player rows and {len(teams)} team rows from '
            f'{path}. An empty read is not an empty season.')
    for k, r in players.items():
        if r['pass_cmp'] > r['pass_att']:
            raise PanelContract(
                f'BASELINE_CMP_EXCEEDS_ATT: {k} has cmp={r["pass_cmp"]} > '
                f'att={r["pass_att"]}')
        if r['receptions'] > r['targets']:
            raise PanelContract(
                f'BASELINE_REC_EXCEEDS_TGT: {k} has rec={r["receptions"]} > '
                f'tgt={r["targets"]}')
    audit['player_rows'] = len(players)
    audit['team_rows'] = len(teams)
    audit['games'] = len({g for g, _ in teams})
    return players, teams, dict(audit)


def load_positions() -> tuple[dict, dict]:
    """(gsis_id -> modal position, gsis_id -> n distinct labels).

    POSITION IS TREATED AS A STATIC ROSTER ATTRIBUTE, NOT A POINT-IN-TIME ONE,
    and this function returns the evidence for that treatment rather than
    asserting it: the second dict lets a test measure how many players ever
    carry more than one label. The defensible part of the claim is that a
    position label cannot be a function of the forecast game's outcome; the
    part that needs measuring is whether it moves at all.
    """
    counts = collections.defaultdict(collections.Counter)
    with gzip.open(PANEL_P3, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if int(r['season']) not in LAWFUL_SEASONS:
                continue
            if r['gsis_id'] and r['position']:
                counts[r['gsis_id']][r['position']] += 1
    if not counts:
        raise EmptyRead(
            f'BASELINE_POSITION_SOURCE_EMPTY: {PANEL_P3} yielded no position '
            f'labels for {LAWFUL_SEASONS}.')
    modal = {p: c.most_common(1)[0][0] for p, c in counts.items()}
    nlab = {p: len(c) for p, c in counts.items()}
    return modal, nlab


def build_panel() -> dict:
    """The whole lawful frame: player rows, team rows, positions, identity."""
    players, teams, audit = {}, {}, {}
    for s in LAWFUL_SEASONS:
        p, t, a = build_season(s)
        players.update(p)
        teams.update(t)
        audit[str(s)] = a
    modal, nlab = load_positions()
    rows = []
    unlabelled = 0
    for (gid, team, pid), r in players.items():
        pos = modal.get(pid)
        if pos is None:
            unlabelled += 1
        r = dict(r)
        r['position'] = pos or 'UNK'
        rows.append(r)
    rows.sort(key=lambda r: (r['season'], r['week'], r['game_id'], r['team'],
                             r['gsis_id']))
    trows = sorted(teams.values(),
                   key=lambda r: (r['season'], r['week'], r['game_id'],
                                  r['team']))
    audit['position_unlabelled_player_games'] = unlabelled
    audit['position_multi_label_players'] = sum(
        1 for v in nlab.values() if v > 1)
    audit['position_players'] = len(nlab)
    return {'players': rows, 'teams': trows, 'audit': audit,
            'identity': data_identity()}


def ordinal(season: int, week: int) -> int:
    """A total order over games. `season * 100 + week` is strictly increasing
    within and across the lawful seasons because week <= 18 < 100."""
    return season * 100 + week
