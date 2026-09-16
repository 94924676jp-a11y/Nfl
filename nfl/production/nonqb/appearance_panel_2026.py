"""2026 week-1 OBSERVED rows, so the previous game is the previous game.

WHAT THIS FIXES. The appearance panel ends at 2025 week 18. Every player on a
2026 week-2 board therefore carries week 18 as his most recent game, and week
18 is a rest week across the league: measured f_prev_snap means 0.332 for
Buffalo and 0.368 for Detroit against a normal starter share near 0.8.

James Cook is the clearest instance and he is an INSTANCE, not a special
case. His appearance history is otherwise perfect -- f_prev_appeared 1,
f_rate3 and f_rate5 1.0, f_rate_ewma 0.99968, f_consec_missed 0, 67 prior
games -- and the single feature dragging him to 0.7138, essentially the
0.6936 training base rate, is f_prev_snap = 0.03 from a 2-snap rest game. His
true previous game is 2026 week 1 at 0.72.

WHY A NEW MODULE AND NOT AN EDIT TO panel_2026w1. That panel exists for the
non-QB PARTICIPATION estimator and its identity is part of the R9_W1P
candidate, so it may not be edited. It also filters `POSITIONS = ('WR','TE',
'RB')`, which is correct for what it feeds and wrong here: quarterbacks have
no 2026 row at all, which is why Josh Allen sits at 0.4188 and why the
f_prev_snap substitution does nothing for him. This module reads the same
snap-count capture and keeps every position the appearance model scores.

APPEARANCE IS SNAPS, NOT STATISTICS. A player appeared if he was on the field
for an offensive snap. A quarterback who hands off forty times appeared; a
receiver targeted zero times appeared. So `did_not_appear` is resolved from
offense_snaps and from nothing else, and a player with no snap-count row is
left UNKNOWN rather than recorded as absent -- the capture covers 30 of 32
clubs and a missing club is missing evidence, not a team that did not play.
"""
from __future__ import annotations

import csv
import glob
import gzip
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'appearance-panel-2026w1-1'

#: Every position the appearance model scores. Kickers are included because
#: the board now carries a kicking line and his appearance matters to it.
POSITIONS = ('QB', 'RB', 'FB', 'HB', 'WR', 'TE', 'K')

_CACHE: dict = {}


def _widest(pattern):
    """The capture carrying the most rows. Coverage, not recency.

    These captures are partial by club -- one holds two teams, another
    thirty -- so the newest is routinely the thinnest. The widest is chosen
    and the choice is reported, because "which blob" must have one answer.
    """
    best = None
    for f in sorted(glob.glob(str(_REPO / pattern))):
        op = gzip.open if f.endswith('.gz') else open
        try:
            rows = list(csv.DictReader(op(f, 'rt', errors='ignore')))
        except OSError:
            continue
        if best is None or len(rows) > len(best[0]):
            best = (rows, f)
    return best or ([], None)


def build(season: int = 2026, week: int = 1) -> Outcome:
    """Observed appearance rows for `season` week `week`, all offence."""
    key = (season, week)
    if key in _CACHE:
        return _CACHE[key]
    snaps, snap_f = _widest(f'nfl/availability_raw/snap_counts_{season}.*.csv.gz')
    if not snaps:
        return Outcome.blocked(
            'APPEARANCE_2026_NO_SNAP_CAPTURE',
            f'no snap-count capture for {season}, so offensive snaps cannot '
            f'be read and appearance cannot be resolved. It is NOT inferred '
            f'from statistics: a player with no target still appeared.',
            cause=Cause.DATA)

    # pfr_player_id -> gsis_id, from the roster capture. Identity is by id;
    # a snap row this cannot resolve is REPORTED, never name-matched.
    ident, n_roster = {}, 0
    for f in sorted(glob.glob(str(_REPO / 'nfl/vintage/weekly_rosters.*raw.csv*'))):
        op = gzip.open if f.endswith('.gz') else open
        for r in csv.DictReader(op(f, 'rt', errors='ignore')):
            pid = (r.get('pfr_id') or '').strip()
            g = (r.get('gsis_id') or '').strip()
            if pid and g and pid not in ident:
                ident[pid] = (g, (r.get('position') or '').strip().upper(),
                              (r.get('team') or '').strip().upper(),
                              (r.get('full_name') or '').strip())
                n_roster += 1
    if not ident:
        return Outcome.blocked(
            'APPEARANCE_2026_NO_IDENTITY_BRIDGE',
            'no raw roster capture carries pfr_id, so snap-count rows cannot '
            'be joined to a gsis_id. Name matching is forbidden here.',
            cause=Cause.DATA)

    rows, unresolved, skipped_pos, teams = [], 0, 0, set()
    for s in snaps:
        try:
            if int(s.get('season') or 0) != int(season) or \
                    int(s.get('week') or 0) != int(week):
                continue
        except ValueError:
            continue
        pid = (s.get('pfr_player_id') or '').strip()
        got = ident.get(pid)
        if not got:
            unresolved += 1
            continue
        g, rpos, rteam, name = got
        pos = (s.get('position') or rpos or '').strip().upper()
        if pos not in POSITIONS:
            skipped_pos += 1
            continue
        try:
            off = float(s.get('offense_snaps') or 0)
        except ValueError:
            off = 0.0
        try:
            st = float(s.get('st_snaps') or 0)
        except ValueError:
            st = 0.0
        pct = s.get('offense_pct')
        try:
            pct = float(pct) if pct not in (None, '') else None
        except ValueError:
            pct = None
        # A KICKER TAKES NO OFFENSIVE SNAP AND HE CERTAINLY APPEARED.
        # Reading appearance off `offense_snaps` marked Tyler Bass absent
        # from a game in which he went 3-for-3 on field goals. For a kicker
        # the snaps that exist are SPECIAL TEAMS snaps, so his appearance and
        # his share are read from that column instead.
        if pos == 'K':
            # HIS APPEARANCE IS A FACT; HIS SNAP SHARE IS NOT DEFINED ON THE
            # SCALE THE MODEL LEARNED. The appearance feature `snap_share` is
            # an OFFENSIVE share throughout the training panel, and a kicker
            # takes no offensive snap. Handing over his special-teams share
            # instead read 0.45 for Tyler Bass -- which on the offensive scale
            # means a rotational player -- and drove him 0.9970 -> 0.6850 on a
            # game he kicked three field goals in. That is a category error,
            # not evidence.
            #
            # So the appearance is kept and the share is left MISSING, which
            # the featuriser already has a flag for. The training panel holds
            # 47 kicker rows against 21,219 receivers, so this position is
            # thin support at best and is not worth a fabricated number.
            counted, pct = st, None
        else:
            counted = off
        team = (s.get('team') or rteam or '').strip().upper()
        teams.add(team)
        rows.append({
            'season': int(season), 'week': int(week),
            'ord': int(season) * 100 + int(week),
            'gsis_id': g, 'player_name': name, 'position': pos, 'team': team,
            'game_id': (s.get('game_id') or '').strip(),
            'offense_snaps': off, 'st_snaps': st,
            'offense_pct': pct, 'snap_share': pct,
            'snap_share_defined': pct is not None,
            'snaps_counted': counted,
            'snap_basis': 'ST_SNAPS' if pos == 'K' else 'OFFENSE_SNAPS',
            # APPEARANCE IS SNAPS -- the snaps his position actually takes.
            'did_not_appear': 0 if counted > 0 else 1,
            'appeared': 1 if counted > 0 else 0,
            'source_blob': pathlib.Path(snap_f).name,
        })
    if not rows:
        return Outcome.blocked(
            'APPEARANCE_2026_NO_ROWS',
            f'the widest {season} snap capture carries no week-{week} '
            f'offensive row this module can resolve. Zero rows is an absence, '
            f'not a week nobody played.', cause=Cause.DATA,
            blob=pathlib.Path(snap_f).name if snap_f else None)
    import collections
    return Outcome.ok(
        'APPEARANCE_2026_PANEL', value=rows, spec_version=SPEC_VERSION,
        n_rows=len(rows), n_teams=len(teams), teams=sorted(teams),
        by_position=dict(collections.Counter(r['position'] for r in rows)),
        n_appeared=sum(1 for r in rows if r['appeared']),
        n_did_not_appear=sum(1 for r in rows if not r['appeared']),
        snap_blob=pathlib.Path(snap_f).name,
        n_snap_rows_unresolved_identity=unresolved,
        n_rows_skipped_non_offensive_position=skipped_pos,
        appearance_rule='offensive snaps > 0, except a KICKER, whose '
                        'appearance is special-teams snaps -- he takes no '
                        'offensive snap and reading that column marked a '
                        'kicker absent from a game he kicked three field '
                        'goals in. A player with no snap-count row '
                        'is absent from this panel and stays UNKNOWN -- the '
                        'capture covers a subset of clubs and a missing club '
                        'is missing evidence, not a team that did not play.',
        coverage_caveat=f'{len(teams)} club(s) covered')


def by_id(season: int = 2026, week: int = 1):
    """{gsis_id: row}, or an empty dict when the panel refuses."""
    o = build(season, week)
    return {r['gsis_id']: r for r in o.value} if o.ok else {}


#: The spec version of the R7/R8-frame adapter. Named separately from
#: SPEC_VERSION because the panel and the shape it is handed to a different
#: mechanism in are two things that can change independently.
R8_ADAPTER_SPEC_VERSION = 'appearance-panel-2026w1-r8-frame-1'


#: The offensive positions the R7/R8 frame keeps. Named here rather than
#: imported so this module does not import the mechanism it feeds.
FRAME_POS = ('QB', 'RB', 'WR', 'TE')

UNION_SPEC_VERSION = 'appearance-panel-2026w1-union-1'


def _kickoffs(season: int, week: int):
    """(team) -> kickoff, for the point-in-time depth selection."""
    from nfl.capture import coverage as C
    p = C.load_week_plan(int(season), int(week))
    if p.state is not State.PASS:
        return None, p
    out = {}
    for c in p.value:
        parts = str(c.game_id).split('_')
        if len(parts) < 4:
            continue
        for t in (parts[2], parts[3]):
            out[t] = c.kickoff_utc
    return out, None


def as_union_frame_rows(season: int = 2026, week: int = 1) -> Outcome:
    """The week, built the way EVERY other week in the R7/R8 frame is built.

    WHY THIS EXISTS. `as_r8_frame_rows` returns the observed panel alone, and
    the panel comes from the snap-count file -- so a player who dressed and did
    not take an offensive snap, or was a healthy scratch, has NO row. The frame
    R8 was fitted on is the panel UNION the point-in-time depth chart, where he
    has one with `appeared = 0`.

    Measured, and this is the whole reason: the R7 frame's week-1 rows run a
    base rate of 0.5390 over 4,176 rows. The panel alone is 0.9265 over 422. So
    `n_cur = 1` at serve time was not the `n_cur = 1` the fit saw, and R8 --
    which moves w = n_cur/(n_cur+k) = 0.4509 of its weight off the depth
    listing the moment a player has one current-season game -- read a starter
    who PLAYED as evidence to lower him. Josh Allen 0.9625 to 0.8449 on a 100%
    snap share; James Cook 0.8381 to 0.6299 on 0.72.

    THE DEPTH CHART IS SELECTED POINT-IN-TIME, at each team's own week-1
    kickoff, from the captured 2026 vintage. It is not today's chart: a chart
    captured after the game would be contaminated by it. If no lawful chart
    predates a team's kickoff, that team is REPORTED as chart-less and
    contributes only its panel rows -- the same treatment
    `appearance_r7.build_frame` gives a team-week it cannot chart, and never a
    fabricated zero.

    `appeared = 0` here means "listed on the depth chart and took no offensive
    snap". It does NOT mean "did not dress": the two are indistinguishable from
    this evidence, and they were indistinguishable in training too, which is
    the point -- the serve population has to be built the way the fit
    population was, defects included.
    """
    o = build(int(season), int(week))
    if o.state is not State.PASS:
        return o
    by_key, teams = {}, set()
    n_panel_kept = n_panel_dropped_pos = 0
    for r in o.value:
        if not r.get('gsis_id') or not r.get('team'):
            continue
        if (r.get('position') or '').upper() not in FRAME_POS:
            n_panel_dropped_pos += 1
            continue
        sn = r.get('snap_share') if r.get('snap_share_defined') else None
        by_key[(r['team'], r['gsis_id'])] = {
            's': int(r['season']), 'w': int(r['week']), 't': r['team'],
            'pid': r['gsis_id'], 'pos': (r.get('position') or '').upper(),
            'appeared': int(r['appeared']),
            'snap': (None if sn is None else float(sn)),
            'in_panel': True, 'rank': None}
        teams.add(r['team'])
        n_panel_kept += 1
    if not by_key:
        return Outcome.fail(
            'APPEARANCE_2026_UNION_PANEL_EMPTY',
            f'the {season} week {week} panel produced no row in {FRAME_POS} '
            f'carrying both a gsis_id and a team.')

    kicks, err = _kickoffs(int(season), int(week))
    if kicks is None:
        return err
    from nfl.production.nonqb import depth_vintage as DV
    added, no_chart, charted = 0, [], {}
    for t in sorted(teams):
        k = kicks.get(t)
        if k is None:
            no_chart.append({'team': t, 'code': 'NO_KICKOFF_IN_WEEK_PLAN'})
            continue
        cap = DV.captured([t], k)
        if cap.state is not State.PASS:
            no_chart.append({'team': t, 'code': cap.code})
            continue
        listed = cap.value or {}
        charted[t] = str(k)
        for pid, v in listed.items():
            rank, pos = (v if isinstance(v, tuple) else (None, None))
            key = (t, pid)
            if key in by_key:
                by_key[key]['rank'] = rank
                continue
            if (pos or '').upper() not in FRAME_POS:
                continue
            by_key[key] = {
                's': int(season), 'w': int(week), 't': t, 'pid': pid,
                'pos': (pos or '').upper(),
                # LISTED AND TOOK NO OFFENSIVE SNAP. This is the row the
                # snap-count file cannot contain, and its absence is what
                # made the injected population 93% appearers.
                'appeared': 0, 'snap': None, 'in_panel': False, 'rank': rank}
            added += 1
            
    rows = sorted(by_key.values(), key=lambda r: (r['t'], r['pid']))
    app = sum(r['appeared'] for r in rows)
    return Outcome.ok(
        'APPEARANCE_2026_UNION_FRAME_ROWS', value=rows,
        spec_version=UNION_SPEC_VERSION,
        n_rows=len(rows), n_from_panel=n_panel_kept,
        n_added_by_depth_chart=added,
        n_panel_rows_dropped_off_position=n_panel_dropped_pos,
        appeared=app, base_rate=round(app / len(rows), 6),
        n_teams=len(teams), n_teams_charted=len(charted),
        n_teams_without_a_lawful_chart=len(no_chart),
        teams_without_a_lawful_chart=no_chart[:8],
        depth_selection='point-in-time at each team`s own week-1 kickoff, '
                        'from the captured 2026 vintage',
        construction='panel UNION point-in-time depth chart, appeared = 0 for '
                     'a listed player with no offensive snap -- the same '
                     'construction appearance_r7.build_frame uses for every '
                     'other week',
        detail=f'{len(rows)} row(s): {n_panel_kept} from the panel, {added} '
               f'added by the depth chart; base rate {app / len(rows):.4f}')


def as_r8_frame_rows(season: int = 2026, week: int = 1) -> Outcome:
    """The same observed rows, in the shape `appearance_r8`'s frame walk reads.

    WHY THIS EXISTS RATHER THAN A SECOND PANEL. `appearance_model.predict`
    already takes these rows through `extra_rows`, but that is the FROZEN
    logistic -- the mechanism R8 replaced, and the one whose forward-chained
    Brier is 0.18146 against R8's 0.10049 in the weeks 2-4 regime, on 7,709
    rows with a team-week-blocked interval that excludes zero. Handing the
    2026 information only to the losing mechanism is how a candidate ends up
    choosing between "current data" and "the better model" when it could have
    had both.

    R8's prospective row is built from `hist[pid]`, the frame rows for that
    player, so a current-season row appended to the frame IS the repair. Six
    fields are all the walk reads: season, week, team, player, whether he
    appeared, and his offensive snap share.

    THE COEFFICIENTS DO NOT MOVE AND CANNOT. `appearance_r8.fit` trains on
    `r['s'] < season`, so a 2026 row can never enter a 2026 fit. This adds
    information to a fitted model; it does not refit one. `coef_sha256` is
    identical with and without it, and the test asserts that rather than
    trusting this sentence.

    A KICKER'S SNAP SHARE IS LEFT MISSING, not filled from special teams. The
    feature was learned as an OFFENSIVE share, and feeding a 0.45 special-teams
    share into it drove Tyler Bass from 0.9970 to 0.6850 on a game he kicked
    3-for-3. `build` already declines to invent one; this carries the decline
    through instead of turning it into a zero.
    """
    o = build(int(season), int(week))
    if o.state is not State.PASS:
        return o
    rows, n_snap = [], 0
    for r in o.value:
        if not r.get('gsis_id') or not r.get('team'):
            continue
        sn = r.get('snap_share') if r.get('snap_share_defined') else None
        if sn is not None:
            n_snap += 1
        rows.append({'s': int(r['season']), 'w': int(r['week']),
                     't': r['team'], 'pid': r['gsis_id'],
                     'pos': r.get('position'),
                     'appeared': int(r['appeared']),
                     'snap': (None if sn is None else float(sn))})
    if not rows:
        return Outcome.fail(
            'APPEARANCE_2026_R8_ROWS_EMPTY',
            f'the {season} week {week} panel produced no row carrying both a '
            f'gsis_id and a team, so there is nothing to append to the frame. '
            f'An empty injection is an error, not a no-op.')
    return Outcome.ok(
        'APPEARANCE_2026_R8_FRAME_ROWS', value=rows,
        spec_version=R8_ADAPTER_SPEC_VERSION,
        n_rows=len(rows), n_with_a_snap_share=n_snap,
        n_without_a_snap_share=len(rows) - n_snap,
        appeared=sum(r['appeared'] for r in rows),
        teams=len({r['t'] for r in rows}),
        fields_the_walk_reads=['s', 'w', 't', 'pid', 'appeared', 'snap'],
        coefficients_unchanged='appearance_r8.fit trains on s < season, so a '
                               '2026 row cannot enter a 2026 fit',
        detail=f'{len(rows)} observed {season} week {week} row(s) in R8 frame '
               f'shape, {n_snap} with an offensive snap share')
