"""Q7 step 1: the efficiency panel, built from play-by-play with provenance.

WHY A SEPARATE PANEL RATHER THAN TRACK 1'S.

Track 1's reduction is frozen with its own specification and carries no
completions, no passing touchdowns and no receiver rows. Extending it would
edit a frozen artifact; building beside it from the same six source files,
re-hashed here, leaves both auditable.

DEFINITIONS, FIXED HERE AND USED EVERYWHERE DOWNSTREAM.

    attempt      pass_attempt and not sack and not spike
    completion   an attempt that completed
    sack         a sack on a dropback
    scramble     a scramble
    dropback     attempts + sacks + scrambles

Dropbacks are COMPOSED from the three components rather than read from
`qb_dropback`, so the identity the QB layer rests on --
`attempts + sacks + scrambles == dropbacks` -- holds in this panel by
construction and cannot drift from the engine's own check.

PER-RECEPTION YARDAGE IS KEPT PER CATCH, not as a game mean. RC1 measured skew
2.197 and excess kurtosis 7.830 on this quantity, with P(gain > 40) = 0.0203
empirically against 0.0016 under a fitted Normal -- a Gaussian understates the
tail thirteenfold. The list is what makes a resampled tail possible.

NO MARKET COLUMN IS READ. `READ` is the complete list and is checked against a
forbidden-substring list at import, exactly as the Track 1 builder is.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'q7-panel-1'
HERE = _REPO / 'nfl' / 'research' / 'q7'
RAW = _REPO / 'nfl' / 'research' / 'track1' / 'raw'
QB = HERE / 'q7_qb_game.csv.gz'
RECV = HERE / 'q7_recv_game.csv.gz'
MANIFEST = HERE / 'Q7_RAW_PROVENANCE.json'

SEASONS = (2020, 2021, 2022, 2023, 2024, 2025)
URL = ('https://github.com/nflverse/nflverse-data/releases/download/pbp/'
       'play_by_play_{season}.csv.gz')

READ = ('game_id', 'season', 'week', 'season_type', 'posteam', 'defteam',
        'passer_player_id', 'passer_player_name', 'receiver_player_id',
        'receiver_player_name', 'pass_attempt', 'complete_pass', 'sack',
        'qb_scramble', 'qb_spike', 'qb_dropback', 'passing_yards',
        'receiving_yards', 'pass_touchdown', 'interception')

FORBIDDEN_SUBSTRINGS = ('spread_line', 'total_line', 'vegas', 'moneyline',
                        'odds', 'implied_prob')


def market_columns(fieldnames):
    return [c for c in fieldnames
            if any(s in str(c).lower() for s in FORBIDDEN_SUBSTRINGS)]


def assert_no_market_column(fieldnames, where):
    bad = market_columns(fieldnames)
    if bad:
        raise SystemExit(
            f'Q7_MARKET_COLUMN_IN_{where}: {bad}. Sportsbook prices, lines and '
            f'market probabilities are forbidden inputs.')


assert_no_market_column(READ, 'READ_LIST')


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def reduce_season(path):
    qb = collections.defaultdict(collections.Counter)
    rc = collections.defaultdict(collections.Counter)
    rec_yards = collections.defaultdict(list)
    names = {}
    meta = {}
    with gzip.open(path, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            gid, off = r.get('game_id'), r.get('posteam')
            if not gid or not off:
                continue
            meta.setdefault(gid, {'season': _i(r.get('season')),
                                  'week': _i(r.get('week'))})
            sack = _i(r.get('sack'))
            scr = _i(r.get('qb_scramble'))
            spike = _i(r.get('qb_spike'))
            pa = _i(r.get('pass_attempt'))
            is_att = bool(pa and not sack and not spike)
            comp = _i(r.get('complete_pass')) if is_att else 0
            pid = (r.get('passer_player_id') or '').strip()
            if pid:
                names[pid] = (r.get('passer_player_name') or '').strip()
                c = qb[(gid, off, pid)]
                if is_att:
                    c['att'] += 1
                    c['cmp'] += comp
                    c['pyds'] += _i(r.get('passing_yards'))
                    c['ptd'] += _i(r.get('pass_touchdown'))
                    c['int'] += _i(r.get('interception'))
                if sack and _i(r.get('qb_dropback')):
                    c['sacks'] += 1
                if scr:
                    c['scr'] += 1
            rid = (r.get('receiver_player_id') or '').strip()
            if rid and is_att:
                names[rid] = (r.get('receiver_player_name') or '').strip()
                c = rc[(gid, off, rid)]
                c['targets'] += 1
                c['rec'] += comp
                c['rec_yds'] += _i(r.get('receiving_yards'))
                c['rec_td'] += _i(r.get('pass_touchdown')) if comp else 0
                if comp:
                    rec_yards[(gid, off, rid)].append(
                        _i(r.get('receiving_yards')))
    return qb, rc, rec_yards, names, meta


def build(seasons=SEASONS):
    qb_rows, rc_rows, prov = [], [], []
    for s in seasons:
        p = RAW / f'play_by_play_{s}.csv.gz'
        if not p.exists():
            raise SystemExit(
                f'Q7_RAW_SEASON_MISSING: {p} is absent. A season silently '
                f'skipped would shrink the frame without saying so. It is '
                f're-fetchable from the url and hash in '
                f'nfl/research/track1/RAW_PROVENANCE.json.')
        qb, rc, ry, names, meta = reduce_season(p)
        raw = p.read_bytes()
        prov.append({'season': s, 'file': str(p.relative_to(_REPO)),
                     'sha256': hashlib.sha256(raw).hexdigest(),
                     'n_bytes': len(raw), 'source_url': URL.format(season=s),
                     'source_name': 'nflverse_pbp', 'source_rank': 1})
        for (gid, team, pid), c in sorted(qb.items()):
            m = meta[gid]
            att, sk, sc = int(c['att']), int(c['sacks']), int(c['scr'])
            db = att + sk + sc
            if db <= 0:
                continue
            qb_rows.append({
                'game_id': gid, 'season': m['season'], 'week': m['week'],
                'ord': m['season'] * 100 + m['week'], 'team': team,
                'gsis_id': pid, 'name': names.get(pid, ''),
                'db': db, 'att': att, 'cmp': int(c['cmp']),
                'sacks': sk, 'scr': sc, 'pyds': int(c['pyds']),
                'ptd': int(c['ptd']), 'int': int(c['int'])})
        for (gid, team, rid), c in sorted(rc.items()):
            m = meta[gid]
            rc_rows.append({
                'game_id': gid, 'season': m['season'], 'week': m['week'],
                'ord': m['season'] * 100 + m['week'], 'team': team,
                'gsis_id': rid, 'name': names.get(rid, ''),
                'targets': int(c['targets']), 'rec': int(c['rec']),
                'rec_yds': int(c['rec_yds']), 'rec_td': int(c['rec_td']),
                'rec_yards_list': '|'.join(
                    str(x) for x in ry.get((gid, team, rid), []))})
    for rows, path, where in ((qb_rows, QB, 'QB_PANEL'),
                              (rc_rows, RECV, 'RECV_PANEL')):
        if not rows:
            raise SystemExit(f'Q7_EMPTY_PANEL: {path} would carry no rows. An '
                             f'empty panel is an error, not a result.')
        assert_no_market_column(list(rows[0]), where)
        with gzip.open(path, 'wt', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    bad = [r for r in qb_rows if r['att'] + r['sacks'] + r['scr'] != r['db']]
    if bad:
        raise SystemExit(f'Q7_DROPBACK_IDENTITY_VIOLATED: {len(bad)} rows')
    MANIFEST.write_text(json.dumps({
        'artifact': 'NFL_Q7_RAW_PROVENANCE', 'spec_version': SPEC_VERSION,
        'market_columns_refused': list(FORBIDDEN_SUBSTRINGS),
        'definitions': {
            'attempt': 'pass_attempt and not sack and not spike',
            'completion': 'an attempt that completed',
            'dropback': 'attempts + sacks + scrambles, COMPOSED not read',
        },
        'seasons': prov}, indent=1) + '\n')
    return {'qb_game_rows': len(qb_rows), 'recv_game_rows': len(rc_rows),
            'seasons': list(seasons)}


def load(path, ints=(), lists=()):
    with gzip.open(path, 'rt', newline='') as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ints:
            r[k] = int(r[k])
        for k in lists:
            r[k] = [int(x) for x in r[k].split('|') if x != '']
    return rows


QB_INTS = ('season', 'week', 'ord', 'db', 'att', 'cmp', 'sacks', 'scr',
           'pyds', 'ptd', 'int')
RECV_INTS = ('season', 'week', 'ord', 'targets', 'rec', 'rec_yds', 'rec_td')


def load_qb():
    return load(QB, QB_INTS)


def load_recv():
    return load(RECV, RECV_INTS, ('rec_yards_list',))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in SEASONS))
    a = ap.parse_args(argv)
    print(json.dumps(build(tuple(int(x) for x in a.seasons.split(','))),
                     indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
