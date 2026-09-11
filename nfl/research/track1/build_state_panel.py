"""Track 1 step 1: reduce raw play-by-play to a GAME-STATE panel.

WHAT THIS PRODUCES AND WHY IT IS SHAPED THIS WAY.

Two tables, both at units that can actually be estimated on:

  * TEAM-QUARTER: for one offense in one quarter -- plays, dropbacks, designed
    rushes, pass attempts, sacks, passing yards, seconds of game clock -- with
    the SCORE DIFFERENTIAL THAT TEAM FACED AT THE START OF THE QUARTER. That
    differential is the conditioning variable, and taking it at the quarter
    BOUNDARY rather than play-by-play is deliberate: a within-quarter
    differential is partly caused by the plays being counted, and conditioning
    a play count on a quantity the plays themselves moved is circular.

  * GAME: final margin and the margin at each quarter boundary, which is what
    the pregame state generator has to reproduce.

WHAT IS DELIBERATELY NOT EXTRACTED. `spread_line`, `total_line`, `vegas_wp`
and every other market column in the source are never read. They are in the
file; they are forbidden inputs to a football forecast, and the cheapest way
to keep them out is to never put them in the panel. A test asserts the panel
carries no such column.

ESTIMAND HONESTY. `plays` here is a count of OFFENSIVE PLAY ROWS -- pass
attempts, designed rushes, scrambles and sacks. It is NOT `team_off_snaps`
from snap counts, which includes penalty-nullified plays that appear here as
separate rows. The two are different quantities and the Track 1 response is
therefore used as a RELATIVE multiplier on whatever the baseline forecasts,
never as a level substituted into it.
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

HERE = _REPO / 'nfl' / 'research' / 'track1'
RAW = HERE / 'raw'
TEAM_QUARTER = HERE / 'state_team_quarter.csv.gz'
GAME = HERE / 'state_game.csv.gz'
QB_GAME = HERE / 'state_qb_game.csv.gz'
MANIFEST = HERE / 'RAW_PROVENANCE.json'

SEASONS = (2020, 2021, 2022, 2023, 2024, 2025)
URL = ('https://github.com/nflverse/nflverse-data/releases/download/pbp/'
       'play_by_play_{season}.csv.gz')

# Columns read from the source. Everything else is dropped, and the market
# columns are absent from this list on purpose.
READ = ('game_id', 'season', 'week', 'season_type', 'posteam', 'defteam',
        'home_team', 'away_team', 'qtr', 'game_seconds_remaining',
        'play_type', 'pass_attempt', 'rush_attempt', 'qb_dropback',
        'qb_scramble', 'sack', 'passing_yards', 'total_home_score',
        'total_away_score', 'passer_player_id', 'passer_player_name', 'desc')

# Market quantities, refused as INPUTS. The source file legitimately carries
# them -- that is the upstream's business. What matters is that this module
# never reads one and the emitted panel never carries one, so the check is on
# `READ` and on the panel's own columns, never on the source's column list.
#
# The first version checked the SOURCE header and refused the whole build,
# because nflverse ships `spread_line` and `vegas_wp` and because the
# substring `_line` also matches `yardline_100` and `end_yard_line`, which are
# field position and not a price. Checking the artifact instead of the
# upstream is the same lesson a source-grep keeps teaching.
FORBIDDEN_SUBSTRINGS = ('spread_line', 'total_line', 'vegas', 'moneyline',
                        'odds', 'implied_prob')


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def market_columns(fieldnames):
    return [c for c in fieldnames
            if any(s in str(c).lower() for s in FORBIDDEN_SUBSTRINGS)]


def assert_no_market_column(fieldnames, where):
    """The market may not enter the football forecast, at any layer."""
    bad = market_columns(fieldnames)
    if bad:
        raise SystemExit(
            f'TRACK1_MARKET_COLUMN_IN_{where}: {bad}. Sportsbook prices, '
            f'lines and market probabilities are forbidden inputs to the '
            f'football forecast.')


# Checked at import: the read list itself must be market-free. This is the
# real guard -- a column that is never read cannot reach a forecast.
assert_no_market_column(READ, 'READ_LIST')


def reduce_season(path):
    """One season of play-by-play -> team-quarter rows and game rows."""
    tq = collections.defaultdict(collections.Counter)
    qb = collections.defaultdict(collections.Counter)
    qbname = {}
    meta = {}
    boundary = {}          # (game_id, qtr) -> (home_score, away_score)
    final = {}             # game_id -> (home_score, away_score)
    seen_qtr = set()
    with gzip.open(path, 'rt', newline='') as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            if r.get('season_type') != 'REG':
                continue
            gid = r.get('game_id')
            if not gid:
                continue
            hs, as_ = _i(r.get('total_home_score')), _i(r.get('total_away_score'))
            final[gid] = (hs, as_)
            q = _i(r.get('qtr'))
            if q and (gid, q) not in seen_qtr:
                # the FIRST row of a quarter carries the score entering it
                seen_qtr.add((gid, q))
                boundary[(gid, q)] = (hs, as_)
            meta.setdefault(gid, {
                'season': _i(r.get('season')), 'week': _i(r.get('week')),
                'home_team': r.get('home_team'), 'away_team': r.get('away_team'),
            })
            off = r.get('posteam')
            if not off or not q:
                continue
            pa = _i(r.get('pass_attempt'))
            ra = _i(r.get('rush_attempt'))
            db = _i(r.get('qb_dropback'))
            sk = _i(r.get('sack'))
            scr = _i(r.get('qb_scramble'))
            is_play = bool(pa or ra or sk or db)
            if not is_play:
                continue
            c = tq[(gid, off, q)]
            c['plays'] += 1
            c['dropbacks'] += 1 if db else 0
            c['pass_att'] += 1 if (pa and not sk) else 0
            c['sacks'] += 1 if sk else 0
            c['scrambles'] += 1 if scr else 0
            # A DESIGNED rush is a rush that was not a scramble. Scrambles are
            # dropbacks that became runs; counting them as designed rushes
            # would move pass-tendency mass into the run game.
            c['designed_rush'] += 1 if (ra and not scr and not db) else 0
            c['pass_yards'] += _i(r.get('passing_yards'))
            # PER-QUARTERBACK, on the same rows. The downstream metrics the
            # directive asks for -- dropbacks, attempts, passing yards -- have
            # to come from the same play stream as the team budget, or the
            # propagation test would be measuring two different games.
            pid = (r.get('passer_player_id') or '').strip()
            if pid and db:
                k = (gid, off, pid)
                qbname[pid] = (r.get('passer_player_name') or '').strip()
                qc = qb[k]
                qc['dropbacks'] += 1
                qc['attempts'] += 1 if (pa and not sk) else 0
                qc['sacks'] += 1 if sk else 0
                qc['scrambles'] += 1 if scr else 0
                qc['pass_yards'] += _i(r.get('passing_yards'))
    return tq, meta, boundary, final, qb, qbname


def build(seasons=SEASONS):
    tq_rows, g_rows, qb_rows, prov = [], [], [], []
    for s in seasons:
        p = RAW / f'play_by_play_{s}.csv.gz'
        if not p.exists():
            raise SystemExit(
                f'TRACK1_RAW_SEASON_MISSING: {p} is absent. A season silently '
                f'skipped would shrink the frame without saying so.')
        tq, meta, boundary, final, qb, qbname = reduce_season(p)
        raw = p.read_bytes()
        prov.append({
            'season': s, 'file': str(p.relative_to(_REPO)),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'n_bytes': len(raw), 'source_url': URL.format(season=s),
            'source_name': 'nflverse_pbp', 'source_rank': 1,
        })
        for gid, m in sorted(meta.items()):
            hs, as_ = final[gid]
            row = {'game_id': gid, 'season': m['season'], 'week': m['week'],
                   'home_team': m['home_team'], 'away_team': m['away_team'],
                   'home_final': hs, 'away_final': as_,
                   'final_margin_home': hs - as_}
            for q in (1, 2, 3, 4, 5):
                b = boundary.get((gid, q))
                row[f'margin_home_start_q{q}'] = (
                    (b[0] - b[1]) if b else '')
            g_rows.append(row)
        for (gid, off, pid), c in sorted(qb.items()):
            m = meta[gid]
            qb_rows.append({
                'game_id': gid, 'season': m['season'], 'week': m['week'],
                'team': off, 'passer_id': pid,
                'passer_name': qbname.get(pid, ''),
                'dropbacks': c['dropbacks'], 'attempts': c['attempts'],
                'sacks': c['sacks'], 'scrambles': c['scrambles'],
                'pass_yards': c['pass_yards'],
            })
        for (gid, off, q), c in sorted(tq.items()):
            m = meta[gid]
            b = boundary.get((gid, q))
            if b is None:
                continue
            home = off == m['home_team']
            diff = (b[0] - b[1]) if home else (b[1] - b[0])
            tq_rows.append({
                'game_id': gid, 'season': m['season'], 'week': m['week'],
                'team': off,
                'opponent': m['away_team'] if home else m['home_team'],
                'home': int(home), 'qtr': q,
                'diff_at_quarter_start': diff,
                'plays': c['plays'], 'dropbacks': c['dropbacks'],
                'pass_att': c['pass_att'], 'sacks': c['sacks'],
                'scrambles': c['scrambles'],
                'designed_rush': c['designed_rush'],
                'pass_yards': c['pass_yards'],
            })
    assert_no_market_column(list(tq_rows[0]), 'TEAM_QUARTER_PANEL')
    assert_no_market_column(list(g_rows[0]), 'GAME_PANEL')
    assert_no_market_column(list(qb_rows[0]), 'QB_GAME_PANEL')
    _write(TEAM_QUARTER, tq_rows)
    _write(GAME, g_rows)
    _write(QB_GAME, qb_rows)
    MANIFEST.write_text(json.dumps({
        'artifact': 'NFL_TRACK1_RAW_PROVENANCE',
        'note': ('the raw seasonal play-by-play is not committed -- it is '
                 '19MB per season and re-fetchable from the recorded url at '
                 'the recorded hash. This manifest is the audit trail, in the '
                 'same shape the vintage capture uses.'),
        'market_columns_refused': list(FORBIDDEN_SUBSTRINGS),
        'seasons': prov,
    }, indent=1) + '\n')
    return {'team_quarter_rows': len(tq_rows), 'game_rows': len(g_rows),
            'qb_game_rows': len(qb_rows), 'seasons': list(seasons)}


def _write(path, rows):
    if not rows:
        raise SystemExit(f'TRACK1_EMPTY_PANEL: {path} would be written with '
                         f'no rows. An empty panel is an error, not a result.')
    with gzip.open(path, 'wt', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def load(path):
    with gzip.open(path, 'rt', newline='') as fh:
        return list(csv.DictReader(fh))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in SEASONS))
    a = ap.parse_args(argv)
    out = build(tuple(int(x) for x in a.seasons.split(',')))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
