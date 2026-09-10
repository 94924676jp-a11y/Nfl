"""Realised quantities for one completed game, computed LIKE FOR LIKE.

Every definition here was read out of the panel builder the model was fitted
on, not reconstructed from a box score. Where the model's estimand cannot be
rebuilt from play-by-play alone the function says so by returning a `basis` of
`SURROGATE` with the substitution named, and never by quietly returning a
nearby number.

DEFINITIONS, with their source:

  team_targets       nfl/research/p1/build_panel.py -- a row with
                     receiver_player_id set and pass_attempt == 1
  team_carries       -- rusher_player_id set and rush_attempt == 1
  team_rz_carries    -- as team_carries with yardline_100 <= 20
  team_dropbacks_part
                     nfl/research/p4b/mk_denom.py -- dropback plays that
                     MATCHED a participation row, two-point attempts removed.
                     Participation is a separate feed. EXACT ONLY WITH IT.
  team_off_snaps     mk_denom.py -- median(offense_snaps / offense_pct) over
                     players at offense_pct >= 0.75, from snap_counts. It is
                     not a play-by-play quantity at all.

  db / att / sacks / scr
                     build_panel.py, and the identity the QB layer enforces at
                     qb_v1.py:267 -- att + sacks + scr == db. So `att` is
                     THROWS, with sacks and scrambles carried separately, and a
                     box-score attempt count is the right comparison for it.
  scr                charged to the RUSHER: on a scramble nflverse leaves
                     passer_player_id null.
  rush_opp           qb2_lib.py:52 -- designed rushes + scrambles.
"""
from __future__ import annotations

import collections
import csv
import gzip
import pathlib


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


def load(pbp_gz: pathlib.Path, game_id: str) -> list:
    rows = [r for r in csv.DictReader(gzip.open(pbp_gz, 'rt'))
            if r.get('game_id') == game_id]
    if not rows:
        raise RuntimeError(
            f'OUTCOME_EMPTY: {pbp_gz} carries no rows for {game_id}. An empty '
            f'read is not a zero-outcome game.')
    return rows


def team_actuals(rows) -> dict:
    """The five team-volume metrics, each labelled EXACT or SURROGATE."""
    t = collections.defaultdict(collections.Counter)
    for r in rows:
        pos = r.get('posteam') or ''
        if not pos:
            continue
        c = t[pos]
        rush = _i(r.get('rush_attempt'))
        pas = _i(r.get('pass_attempt'))
        db = _i(r.get('qb_dropback'))
        two = _i(r.get('two_point_attempt'))
        y100 = _f(r.get('yardline_100'), 999.0)
        c['plays'] += 1
        if r.get('receiver_player_id') and pas:
            c['team_targets'] += 1
        if r.get('rusher_player_id') and rush:
            c['team_carries'] += 1
            if y100 <= 20:
                c['team_rz_carries'] += 1
        if db and not two:
            c['dropbacks_ex_2pt'] += 1
    out = {}
    for team, c in t.items():
        out[team] = {
            'team_targets': {'value': c['team_targets'], 'basis': 'EXACT'},
            'team_carries': {'value': c['team_carries'], 'basis': 'EXACT'},
            'team_rz_carries': {'value': c['team_rz_carries'],
                                'basis': 'EXACT'},
            # The participation feed is BLOCKED in this environment, so the
            # match step that defines this metric cannot be run. The dropback
            # count with two-point attempts removed is its ceiling: every
            # matched play is a dropback, so surrogate >= metric always, and
            # the gap is exactly the unmatched plays.
            'team_dropbacks_part': {
                'value': c['dropbacks_ex_2pt'], 'basis': 'SURROGATE',
                'surrogate': 'qb_dropback count excluding two-point attempts',
                'relation': 'upper bound on the participation-matched count'},
            # snap_counts is a different feed and is not derivable from pbp.
            'team_off_snaps': {
                'value': c['plays'], 'basis': 'SURROGATE',
                'surrogate': 'play-by-play rows with a posteam',
                'relation': 'NOT the same quantity; offensive snaps from '
                            'snap_counts include penalty-nullified plays that '
                            'appear here as separate no_play rows'},
        }
    return out


def qb_actuals(rows) -> dict:
    """Per-passer realised QB quantities, on the model's own definitions."""
    q = collections.defaultdict(collections.Counter)
    y = collections.defaultdict(collections.Counter)
    for r in rows:
        pas = _i(r.get('pass_attempt'))
        sack = _i(r.get('sack'))
        scr = _i(r.get('qb_scramble'))
        rush = _i(r.get('rush_attempt'))
        kneel = _i(r.get('qb_kneel'))
        spike = _i(r.get('qb_spike'))
        pid = r.get('passer_player_id') or ''
        rid = r.get('rusher_player_id') or ''
        if pid:
            # THROWS, not "pass plays": the identity the engine enforces is
            # att + sacks + scr == db, so a sack is never also an attempt here.
            if pas and not sack:
                q[pid]['att'] += 1
                q[pid]['cmp'] += _i(r.get('complete_pass'))
                y[pid]['pyds'] += _f(r.get('passing_yards'))
                q[pid]['ptd'] += _i(r.get('pass_touchdown'))
                q[pid]['int'] += _i(r.get('interception'))
            if sack:
                q[pid]['sacks'] += 1
        if rid and scr:
            q[rid]['scr'] += 1
            y[rid]['ryds'] += _f(r.get('rushing_yards'))
            q[rid]['rtd'] += _i(r.get('rush_touchdown'))
        if rid and rush and not scr and not kneel:
            q[rid]['drush'] += 1
            y[rid]['ryds_designed'] += _f(r.get('rushing_yards'))
            q[rid]['rtd_designed'] += _i(r.get('rush_touchdown'))
        if pid and spike:
            q[pid]['spikes'] += 1
        if rid and kneel:
            q[rid]['kneels'] += 1
    out = {}
    for pid in set(q) | set(y):
        a = q[pid]
        rec = {k: int(a[k]) for k in ('att', 'cmp', 'ptd', 'int', 'sacks',
                                      'scr', 'drush', 'spikes', 'kneels')}
        rec['db'] = rec['att'] + rec['sacks'] + rec['scr']
        rec['rush_opp'] = rec['drush'] + rec['scr']
        rec['pyds'] = round(y[pid]['pyds'], 1)
        rec['ryds'] = round(y[pid]['ryds'] + y[pid]['ryds_designed'], 1)
        rec['rtd'] = int(a['rtd'] + a['rtd_designed'])
        out[pid] = rec
    return out


def qb_timeline(rows) -> dict:
    """WHEN each passer threw, so an in-game change is visible rather than
    inferred from a total. A model asked for a full-game distribution is not
    wrong in the same way when the player left the game."""
    seq = collections.defaultdict(list)
    for r in rows:
        pid = r.get('passer_player_id') or ''
        if not pid:
            continue
        seq[pid].append({
            'qtr': _i(r.get('qtr')), 'play_id': _i(r.get('play_id')),
            'game_seconds_remaining': _i(r.get('game_seconds_remaining'), -1)})
    out = {}
    for pid, s in seq.items():
        s.sort(key=lambda x: x['play_id'])
        out[pid] = {'n_pass_plays': len(s),
                    'first_qtr': s[0]['qtr'], 'last_qtr': s[-1]['qtr'],
                    'first_play_id': s[0]['play_id'],
                    'last_play_id': s[-1]['play_id'],
                    'last_game_seconds_remaining':
                        s[-1]['game_seconds_remaining']}
    return out


def receiving_rushing_actuals(rows) -> dict:
    """Player targets / receptions / yards and carries / rush yards.

    Reported for the record even though the engine produced no player-level
    receiving or rushing forecast this run: a comparison that cannot be made
    should be visible as a missing forecast beside a real outcome, not as an
    absent row.
    """
    p = collections.defaultdict(collections.Counter)
    ys = collections.defaultdict(collections.Counter)
    team = {}
    for r in rows:
        pas, rush = _i(r.get('pass_attempt')), _i(r.get('rush_attempt'))
        rec, rus = (r.get('receiver_player_id') or '',
                    r.get('rusher_player_id') or '')
        pos = r.get('posteam') or ''
        if rec and pas:
            p[rec]['targets'] += 1
            p[rec]['rec'] += _i(r.get('complete_pass'))
            ys[rec]['rec_yds'] += _f(r.get('receiving_yards'))
            p[rec]['rec_td'] += _i(r.get('pass_touchdown')) if _i(
                r.get('complete_pass')) else 0
            team[rec] = pos
            p[rec]['name_seen'] = 1
        if rus and rush:
            p[rus]['carries'] += 1
            ys[rus]['rush_yds'] += _f(r.get('rushing_yards'))
            p[rus]['rush_td'] += _i(r.get('rush_touchdown'))
            team[rus] = pos
    names = {}
    for r in rows:
        for i, n in (('receiver_player_id', 'receiver_player_name'),
                     ('rusher_player_id', 'rusher_player_name'),
                     ('passer_player_id', 'passer_player_name')):
            if r.get(i):
                names[r[i]] = r.get(n) or ''
    out = {}
    for pid in set(p) | set(ys):
        out[pid] = {'name': names.get(pid, ''), 'team': team.get(pid, ''),
                    'targets': int(p[pid]['targets']),
                    'receptions': int(p[pid]['rec']),
                    'rec_yds': round(ys[pid]['rec_yds'], 1),
                    'rec_td': int(p[pid]['rec_td']),
                    'carries': int(p[pid]['carries']),
                    'rush_yds': round(ys[pid]['rush_yds'], 1),
                    'rush_td': int(p[pid]['rush_td'])}
    return out


def names(rows) -> dict:
    """gsis_id -> name, taken from the outcome file AFTER the seal and used for
    READABILITY ONLY. No forecast depends on it."""
    out = {}
    for r in rows:
        for i, n in (('passer_player_id', 'passer_player_name'),
                     ('rusher_player_id', 'rusher_player_name'),
                     ('receiver_player_id', 'receiver_player_name')):
            if r.get(i) and r.get(n):
                out[r[i]] = r[n]
    return out
