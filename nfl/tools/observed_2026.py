"""Observed 2026 weeks 1-2 usage per player, from held evidence only.

    python3.12 -m nfl.tools.observed_2026

WHAT THIS IS. Every value here was OBSERVED in a played 2026 game. Nothing is a
forecast, nothing is smoothed, nothing is carried over from 2025. Weeks are kept
apart and also summed, because a two-week total hides a role that changed
between them.

SOURCES, AND WHY THESE ONES
  snap_counts_2026.62419bd0b011368e  1,492 rows week 1 + 1,502 week 2 + 92
        week 3. Materialised from origin/main, uncompressed sha256 verified
        against its content-addressed name. A LOCAL copy carrying 1,585 rows
        exists and is STALE -- an earlier pass read it and reported week 2 as
        "93 rows, probably a partial". That was true of the checkout and false
        of the project, so this module takes the widest file it can find and
        records which one it used.
  pbp_2026.6643f82adb1158c8          5,489 plays, weeks 1-2, 372 columns.
  weekly_rosters.*.raw.csv.gz        the pfr_id -> gsis_id bridge. Snap counts
        are keyed by pfr_player_id and everything else by gsis_id; without the
        bridge nothing joins, so its absence is a REFUSAL rather than a silent
        drop.

WHAT CANNOT BE BUILT, AND IS NOT ESTIMATED

`routes` and `route_participation` are UNKNOWN_SOURCE_UNAVAILABLE.
`pbp_participation_2026` returned 404 at every probe through
2026-09-27T06:34:57Z, and per-play on-field presence exists nowhere else --
`offense_players`, `offense_personnel`, `defense_players` and `n_offense` are all
absent from the play-by-play. Routes are NOT inferred from targets or snaps. A
route number invented from a target count would look like evidence and be a
guess.

RED ZONE AND GOAL LINE are `yardline_100 <= 20` and `<= 5`, counted as
OPPORTUNITIES (a target or a carry inside that line), not as touches.

ONE SEMANTIC CARE POINT. A player with a snap row and no pbp row has zero
observed targets and carries, and that zero is REAL -- he was on the field and
did not touch the ball. A player with no snap row at all has UNKNOWN, not zero:
he may have been inactive, or the capture may not cover him. The two are
different and are recorded differently.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

SPEC_VERSION = 'observed-2026-1'
WEEKS = (1, 2)
UNKNOWN_SRC = 'UNKNOWN_SOURCE_UNAVAILABLE'


def _rows(path):
    return list(csv.DictReader(gzip.open(path, 'rt')))


def _num(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _widest(pattern, want_weeks):
    """The capture covering the most of `want_weeks`. Never the first found."""
    best, best_f, best_n = None, None, -1
    for f in sorted(glob.glob(str(_REPO / pattern))):
        try:
            rows = _rows(f)
        except Exception:                                        # noqa: BLE001
            continue
        n = sum(1 for r in rows if int(_num(r.get('week'), -1)) in want_weeks)
        if n > best_n:
            best, best_f, best_n = rows, f, n
    return best, best_f, best_n


def build():
    pbp, pbp_f, pbp_n = _widest('nfl/research/postgame/pbp_2026.*.csv.gz', WEEKS)
    if not pbp or pbp_n == 0:
        return Outcome.blocked(
            'OBS26_PBP_ABSENT',
            'no 2026 play-by-play capture covers weeks 1-2, so targets, '
            'carries, dropbacks and red-zone opportunity have no source.',
            cause=Cause.DATA)
    snaps, snap_f, snap_n = _widest(
        'nfl/availability_raw/snap_counts_2026.*.csv.gz', WEEKS)
    if not snaps or snap_n == 0:
        return Outcome.blocked(
            'OBS26_SNAPS_ABSENT',
            'no 2026 snap-count capture covers weeks 1-2, so snaps and snap '
            'share have no source.', cause=Cause.DATA)

    bridge, roster_f = {}, None
    for f in sorted(glob.glob(str(_REPO / 'nfl/vintage/weekly_rosters.*raw.csv*'))):
        rows = _rows(f)
        if not rows or 'pfr_id' not in rows[0]:
            continue
        roster_f = f
        for r in rows:
            p, g = (r.get('pfr_id') or '').strip(), (r.get('gsis_id') or '').strip()
            if p and g:
                bridge[p] = g
    if not bridge:
        return Outcome.blocked(
            'OBS26_IDENTITY_BRIDGE_ABSENT',
            'no raw roster capture carries pfr_id, so snap rows keyed by '
            'pfr_player_id cannot reach gsis_id. Nothing joins without it.',
            cause=Cause.DATA)

    # ---------------------------------------------------------- team totals
    team = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in pbp:
        w = int(_num(r.get('week'), -1))
        if w not in WEEKS:
            continue
        t = (r.get('posteam') or '').strip()
        if not t:
            continue
        k = (t, w)
        team[k]['plays'] += 1
        team[k]['dropbacks'] += _num(r.get('qb_dropback'))
        if _num(r.get('pass')) == 1.0:
            team[k]['pass_plays'] += 1
        if _num(r.get('rush')) == 1.0:
            team[k]['rush_plays'] += 1
        if r.get('receiver_player_id'):
            team[k]['targets'] += 1
        if r.get('rusher_player_id'):
            team[k]['carries'] += 1

    # -------------------------------------------------------- player totals
    per = collections.defaultdict(lambda: collections.defaultdict(float))
    seen_pbp = set()
    for r in pbp:
        w = int(_num(r.get('week'), -1))
        if w not in WEEKS:
            continue
        yl = _num(r.get('yardline_100'), 999)
        rz, gl = yl <= 20, yl <= 5
        rec, rush, pas = (r.get('receiver_player_id'),
                          r.get('rusher_player_id'),
                          r.get('passer_player_id'))
        yds = _num(r.get('yards_gained'))
        td = _num(r.get('touchdown'))
        if rec:
            k = (rec, w); seen_pbp.add(k); d = per[k]
            d['targets'] += 1
            d['air_yards'] += _num(r.get('air_yards'))
            if _num(r.get('complete_pass')) == 1.0:
                d['receptions'] += 1
                d['receiving_yards'] += yds
                if td:
                    d['receiving_td'] += 1
            if rz:
                d['rz_targets'] += 1
            if gl:
                d['gl_targets'] += 1
        if rush:
            k = (rush, w); seen_pbp.add(k); d = per[k]
            d['carries'] += 1
            d['rushing_yards'] += yds
            if td:
                d['rushing_td'] += 1
            if rz:
                d['rz_carries'] += 1
            if gl:
                d['gl_carries'] += 1
        if pas:
            k = (pas, w); seen_pbp.add(k); d = per[k]
            d['pass_attempts'] += 1 if _num(r.get('pass')) == 1.0 else 0
            d['dropbacks'] += _num(r.get('qb_dropback'))
            if _num(r.get('complete_pass')) == 1.0:
                d['completions'] += 1
            d['passing_yards'] += yds if _num(r.get('pass')) == 1.0 else 0
            if td and _num(r.get('pass')) == 1.0:
                d['passing_td'] += 1

    # ------------------------------------------------------------ the snaps
    snap = {}
    unbridged = set()
    for r in snaps:
        w = int(_num(r.get('week'), -1))
        if w not in WEEKS:
            continue
        p = (r.get('pfr_player_id') or '').strip()
        g = bridge.get(p)
        if not g:
            if p:
                unbridged.add(p)
            continue
        snap[(g, w)] = {
            'offense_snaps': int(_num(r.get('offense_snaps'))),
            'offense_pct': _num(r.get('offense_pct')),
            'defense_snaps': int(_num(r.get('defense_snaps'))),
            'st_snaps': int(_num(r.get('st_snaps'))),
            'team': (r.get('team') or '').strip(),
            'opponent': (r.get('opponent') or '').strip(),
            'position_in_snap_file': (r.get('position') or '').strip(),
        }

    ids = {g for (g, _w) in list(snap) + list(seen_pbp)}
    out = {}
    for g in sorted(ids):
        rec = {'gsis_id': g, 'provenance': 'OBSERVED_2026',
               'routes': UNKNOWN_SRC, 'route_participation': UNKNOWN_SRC,
               'weeks': {}}
        for w in WEEKS:
            s, p = snap.get((g, w)), per.get((g, w))
            if s is None and p is None:
                rec['weeks'][str(w)] = {'state': 'UNKNOWN_NO_ROW_EITHER_SOURCE'}
                continue
            tm = (s or {}).get('team') or ''
            tt = team.get((tm, w), {})
            row = {'state': 'OBSERVED',
                   'has_snap_row': s is not None,
                   'has_pbp_row': p is not None,
                   'team': tm or None, 'opponent': (s or {}).get('opponent')}
            if s is not None:
                row.update({k: s[k] for k in
                            ('offense_snaps', 'offense_pct',
                             'defense_snaps', 'st_snaps')})
            else:
                row['snap_state'] = 'UNKNOWN_NO_SNAP_ROW'
            if p is not None:
                for k in ('targets', 'receptions', 'receiving_yards',
                          'receiving_td', 'air_yards', 'carries',
                          'rushing_yards', 'rushing_td', 'rz_targets',
                          'gl_targets', 'rz_carries', 'gl_carries',
                          'pass_attempts', 'completions', 'passing_yards',
                          'passing_td', 'dropbacks'):
                    if p.get(k):
                        row[k] = round(p[k], 1) if isinstance(p[k], float) \
                            else p[k]
                row['rz_opportunities'] = int(p.get('rz_targets', 0)
                                              + p.get('rz_carries', 0))
                row['gl_opportunities'] = int(p.get('gl_targets', 0)
                                              + p.get('gl_carries', 0))
            elif s is not None:
                # ON THE FIELD AND DID NOT TOUCH THE BALL. A REAL ZERO.
                row['touch_state'] = 'OBSERVED_ZERO_TOUCHES'
            if tt.get('targets'):
                row['team_targets'] = int(tt['targets'])
                if p and p.get('targets'):
                    row['target_share'] = round(p['targets'] / tt['targets'], 4)
            if tt.get('carries'):
                row['team_carries'] = int(tt['carries'])
                if p and p.get('carries'):
                    row['rush_share'] = round(p['carries'] / tt['carries'], 4)
            if tt.get('plays'):
                row['team_plays'] = int(tt['plays'])
            if tt.get('dropbacks'):
                row['team_dropbacks'] = int(tt['dropbacks'])
            rec['weeks'][str(w)] = row
        obs = [rec['weeks'][str(w)] for w in WEEKS
               if rec['weeks'][str(w)].get('state') == 'OBSERVED']
        if obs:
            comb = {'n_weeks_observed': len(obs)}
            for k in ('offense_snaps', 'targets', 'receptions',
                      'receiving_yards', 'air_yards', 'carries',
                      'rushing_yards', 'receiving_td', 'rushing_td',
                      'rz_opportunities', 'gl_opportunities', 'pass_attempts',
                      'completions', 'passing_yards', 'passing_td',
                      'dropbacks'):
                v = sum(w.get(k, 0) for w in obs)
                if v:
                    comb[k] = round(v, 1) if isinstance(v, float) else v
            tt_ = sum(w.get('team_targets', 0) for w in obs)
            tc_ = sum(w.get('team_carries', 0) for w in obs)
            if tt_ and comb.get('targets'):
                comb['target_share'] = round(comb['targets'] / tt_, 4)
            if tc_ and comb.get('carries'):
                comb['rush_share'] = round(comb['carries'] / tc_, 4)
            pcts = [w['offense_pct'] for w in obs if 'offense_pct' in w]
            if pcts:
                comb['mean_offense_pct'] = round(sum(pcts) / len(pcts), 4)
            rec['combined'] = comb
        out[g] = rec

    return Outcome.ok(
        'OBSERVED_2026_BUILT',
        value={'spec_version': SPEC_VERSION, 'weeks': list(WEEKS),
               'n_players': len(out), 'players': out,
               'sources': {
                   'pbp': str(pathlib.Path(pbp_f).relative_to(_REPO)),
                   'pbp_rows_in_weeks': pbp_n,
                   'snaps': str(pathlib.Path(snap_f).relative_to(_REPO)),
                   'snap_rows_in_weeks': snap_n,
                   'identity_bridge': str(
                       pathlib.Path(roster_f).relative_to(_REPO)),
                   'bridge_pairs': len(bridge)},
               'ROUTES_UNAVAILABLE': (
                   'routes and route_participation are '
                   f'{UNKNOWN_SRC}: pbp_participation_2026 returned 404 at '
                   'every probe through 2026-09-27T06:34:57Z and per-play '
                   'on-field presence exists nowhere else. Not inferred from '
                   'targets or snaps.'),
               'ZERO_VS_UNKNOWN': (
                   'a player with a snap row and no pbp row carries '
                   'OBSERVED_ZERO_TOUCHES -- he was on the field and did not '
                   'touch the ball, which is a real zero. A player with no row '
                   'in either source carries UNKNOWN_NO_ROW_EITHER_SOURCE. The '
                   'two are never merged.'),
               'n_snap_rows_unbridged': len(unbridged)},
        n_players=len(out))


if __name__ == '__main__':
    import json
    o = build()
    if o.state.name != 'PASS':
        print(f'{o.state.name} {o.code}: {o.detail}')
        raise SystemExit(1)
    v = o.value
    print(f"{v['n_players']} players with observed 2026 evidence")
    print('sources:', json.dumps(v['sources'], indent=1))
    print('snap rows that could not be bridged to gsis_id:',
          v['n_snap_rows_unbridged'])
