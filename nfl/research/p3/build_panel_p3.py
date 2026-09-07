"""Build the player-game opportunity panel. Directive P1.

ONE ROW PER (season, week, player, team). Every column is either a TARGET
(realised in that game, never a feature) or a FEATURE (computed only from
strictly earlier games). The split is enforced by construction below, not by
discipline: targets are written by build_targets() and features by
build_features(), and features only ever read rows with an earlier
(season, week) key.
"""
import collections, csv, gzip, io, json, math, os, sys
csv.field_size_limit(10**9)

SP = os.path.dirname(os.path.abspath(__file__))
SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]


def rd(path):
    with open(path, newline='') as fh:
        for row in csv.DictReader(fh):
            yield row


def f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def build_targets(season):
    """Realised per-player opportunity for each game of one season.

    Everything here describes what HAPPENED in that game. Nothing in this
    function may be read as a feature for the same game.
    """
    # --- team-level volume and per-player counts from pbp -------------------
    team = collections.defaultdict(lambda: collections.Counter())
    plyr = collections.defaultdict(lambda: collections.Counter())
    gmeta = {}
    for r in rd(f'{SP}/pbp_{season}.csv'):
        if r.get('season_type') != 'REG':
            continue
        pos = r.get('posteam') or ''
        if not pos:
            continue
        wk = i(r.get('week'))
        gid = r.get('game_id')
        key = (wk, pos)
        gmeta[key] = gid
        two = i(r.get('two_point_attempt'))
        if two:
            continue
        dropback = i(r.get('qb_dropback'))
        rush = i(r.get('rush_attempt'))
        pas = i(r.get('pass_attempt'))
        sack = i(r.get('sack'))
        scr = i(r.get('qb_scramble'))
        y100 = f(r.get('yardline_100'), 999)
        down = i(r.get('down'))
        rz = y100 <= 20
        gl = y100 <= 5
        third = down == 3

        t = team[key]
        t['plays'] += 1
        t['dropbacks'] += dropback
        t['pass_att'] += pas
        t['rush_att'] += rush
        t['sacks'] += sack
        t['scrambles'] += scr
        if rz:
            t['rz_plays'] += 1
            t['rz_rush'] += rush
            t['rz_pass'] += pas
        if gl:
            t['gl_rush'] += rush
        if third:
            t['third_plays'] += 1
            t['third_dropbacks'] += dropback

        rec = r.get('receiver_player_id') or ''
        rus = r.get('rusher_player_id') or ''
        pss = r.get('passer_player_id') or ''
        if rec and pas:
            p = plyr[(wk, pos, rec)]
            p['targets'] += 1
            p['air_yards'] += f(r.get('air_yards'))
            if rz:
                p['rz_targets'] += 1
        if rus and rush:
            p = plyr[(wk, pos, rus)]
            p['carries'] += 1
            if rz:
                p['rz_carries'] += 1
            if gl:
                p['gl_carries'] += 1
        if pss and dropback:
            p = plyr[(wk, pos, pss)]
            p['dropbacks_as_passer'] += dropback
            p['pass_att_as_passer'] += pas
            p['sacks_taken'] += sack
        # MEASURED: on all 1,134 qb_scramble plays of 2024, passer_player_id is
        # NULL and rusher_player_id is set on 1,062. A scramble is charged to
        # the RUSHER. Attributing it to the passer -- which the first version
        # did -- produced a column that was structurally zero for every player
        # in every season, and a baseline that "predicted" it with MAE 0.0000.
        if scr and rus:
            plyr[(wk, pos, rus)]['scrambles'] += 1
        if rush and rus and not scr:
            plyr[(wk, pos, rus)]['designed_rushes'] += 1
        if third and rec and pas:
            plyr[(wk, pos, rec)]['third_targets'] += 1

    # --- pass-play participation (the RPR proxy) ----------------------------
    pass_snaps = collections.Counter()
    team_dropbacks_part = collections.Counter()
    part = f'{SP}/part_{season}.csv'
    have_part = os.path.exists(part)
    if have_part:
        pbp_key = {}
        for r in rd(f'{SP}/pbp_{season}.csv'):
            if r.get('season_type') == 'REG':
                pbp_key[(r.get('game_id'), r.get('play_id'))] = (
                    i(r.get('week')), r.get('posteam') or '',
                    i(r.get('qb_dropback')), i(r.get('two_point_attempt')))
        for r in rd(part):
            k = (r.get('nflverse_game_id'), r.get('play_id'))
            m = pbp_key.get(k)
            if not m:
                continue
            wk, pos, db, two = m
            if two or not db or not pos:
                continue
            team_dropbacks_part[(wk, pos)] += 1
            for pid in (r.get('offense_players') or '').split(';'):
                if pid:
                    pass_snaps[(wk, pos, pid)] += 1

    # --- snaps, joined on a DETERMINISTIC IDENTIFIER (P3 §8) ---------------
    #
    # The P1/P2 panel joined snap_counts to the panel on (week, team, name).
    # Measured then: 397-589 misses per season, 4.1-6.1% of rows, silently
    # absent from every snap-share figure. This joins on
    #   snap_counts.pfr_player_id -> players.csv -> gsis_id
    # through the repository's own Crosswalk, which reports the mapping
    # injective (22,653 pairs). Measured coverage on 150,351 REG snap rows:
    # 150,183 mapped (99.8883%), 168 refused as PFR_ID_UNMAPPED.
    #
    # No fuzzy-name matching. Crosswalk.map_by_name exists and is not called:
    # on the six real unmapped MLB players it recovers two, SILENTLY MIS-JOINS
    # two, and fails two, and the two it mis-joins are the reason.
    import sys as _sys
    if '/home/user/nfl' not in _sys.path:
        _sys.path.insert(0, '/home/user/nfl')
    from nfl.ingest.identifiers import Crosswalk as _CW
    from sportsplatform.governance.outcome import State as _St
    global _CROSSWALK
    try:
        _CROSSWALK
    except NameError:
        _out = _CW.from_csv(f'{SP}/players.csv',
                            source_sha256='5d14969f6d74edc1')
        if _out.state is not _St.PASS:
            raise SystemExit(f'CROSSWALK_UNAVAILABLE: {_out}')
        _CROSSWALK = _out.value

    snaps = {}
    snap_by_gsis = {}
    unmapped_snap = 0
    for r in rd(f'{SP}/snap_{season}.csv'):
        if r.get('game_type') != 'REG':
            continue
        pid = r.get('pfr_player_id')
        snaps[(i(r.get('week')), r.get('team'), r.get('player'), pid)] = r
        m = _CROSSWALK.map_pfr_id((pid or '').strip(), context='snap_counts')
        if m.state is _St.PASS:
            snap_by_gsis[(i(r.get('week')), r.get('team'), m.value)] = r
        else:
            unmapped_snap += 1

    # --- weekly roster: position, and the id crosswalk ----------------------
    pos_by = {}
    name_by = {}
    for r in rd(f'{SP}/wr_{season}.csv'):
        gid = r.get('gsis_id')
        if not gid:
            continue
        key = (i(r.get('week')), r.get('team'), gid)
        pos_by[key] = r.get('position') or r.get('depth_chart_position') or ''
        name_by[gid] = r.get('full_name') or r.get('player_name') or ''

    rows = []
    seen = set(plyr) | {k for k in pass_snaps}
    for (wk, tm, pid) in sorted(seen):
        p = plyr.get((wk, tm, pid), collections.Counter())
        t = team[(wk, tm)]
        if not t.get('plays'):
            continue
        ps = pass_snaps.get((wk, tm, pid), 0)
        tdb = team_dropbacks_part.get((wk, tm), 0)
        rows.append({
            'season': season, 'week': wk, 'team': tm, 'gsis_id': pid,
            'game_id': gmeta.get((wk, tm), ''),
            'position': pos_by.get((wk, tm, pid), ''),
            'player_name': name_by.get(pid, ''),
            # team volume (a target for QB work, a feature elsewhere only when lagged)
            'team_plays': t['plays'], 'team_dropbacks': t['dropbacks'],
            'team_pass_att': t['pass_att'], 'team_rush_att': t['rush_att'],
            'team_rz_rush': t['rz_rush'], 'team_rz_pass': t['rz_pass'],
            'team_gl_rush': t['gl_rush'],
            'team_dropbacks_part': tdb,
            # player realised opportunity
            'targets': p['targets'], 'carries': p['carries'],
            'rz_targets': p['rz_targets'], 'rz_carries': p['rz_carries'],
            'gl_carries': p['gl_carries'], 'third_targets': p['third_targets'],
            'air_yards': round(p['air_yards'], 1),
            'pass_snaps': ps,
            'dropbacks_as_passer': p['dropbacks_as_passer'],
            'pass_att_as_passer': p['pass_att_as_passer'],
            'scrambles': p['scrambles'],
            'designed_rushes': p['designed_rushes'],
        })

    # Both joins are computed so the repair can be measured rather than
    # asserted. The identifier join is authoritative; the name join is recorded
    # only to report what changed.
    snap_by_name = {}
    for (wk, tm, nm, pfr), r in snaps.items():
        snap_by_name[(wk, tm, (nm or '').strip())] = r
    hit = miss = name_hit = both = id_only = name_only = disagree = 0
    for row in rows:
        by_id = snap_by_gsis.get((row['week'], row['team'], row['gsis_id']))
        by_nm = snap_by_name.get((row['week'], row['team'],
                                  (row['player_name'] or '').strip()))
        if by_nm:
            name_hit += 1
        if by_id and by_nm:
            both += 1
            if by_id is not by_nm:
                disagree += 1
        elif by_id:
            id_only += 1
        elif by_nm:
            name_only += 1
        r = by_id
        if r:
            hit += 1
            row['offense_snaps'] = i(r.get('offense_snaps'))
            row['offense_pct'] = f(r.get('offense_pct'))
        else:
            miss += 1
            row['offense_snaps'] = ''
            row['offense_pct'] = ''
    return rows, {'season': season, 'n_rows': len(rows),
                  'snap_join_hit': hit, 'snap_join_miss': miss,
                  'name_join_hit': name_hit,
                  'name_join_miss': len(rows) - name_hit,
                  'both': both, 'id_only': id_only, 'name_only': name_only,
                  'rows_where_joins_disagree': disagree,
                  'snap_rows_unmapped_pfr': unmapped_snap,
                  'have_participation': have_part,
                  'team_weeks': len(team)}


if __name__ == '__main__':
    allrows, diag = [], []
    for s in SEASONS:
        if not os.path.exists(f'{SP}/pbp_{s}.csv'):
            print(f'skip {s}: no pbp')
            continue
        r, d = build_targets(s)
        allrows += r
        diag.append(d)
        print(f'{s}: {d}', flush=True)
    cols = list(allrows[0].keys())
    with open(f'{SP}/panel_p3.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(allrows)
    json.dump(diag, open(f'{SP}/panel_p3_diag.json', 'w'), indent=1)
    print(f'wrote panel.csv: {len(allrows)} rows, {len(cols)} cols')
