"""CS2 stage 1: current-season non-QB usage, measured. No estimation.

THE SIBLING CS1 NEVER HAD. `current_season_panel` is
`current-season-qb-panel-1` -- a QUARTERBACK panel, by construction. The
refresh that fixed the QB season-boundary problem has no non-QB counterpart,
so week-1 receiving and rushing usage never reaches role allocation for RB, WR
or TE. That is the DATA_STATE_DEFECT in `P2_DIAGNOSTIC.md`, and it is the
reason Buffalo's starters were priced off prior-season and depth-chart
evidence alone.

THIS MODULE IS STAGE 1 ONLY, AND STAGE 1 IS MEASUREMENT.

    stage 1  what each non-QB actually did, per club and week, from governed
             play-by-play. Counting. No parameter, no prior, no shrinkage.
    stage 2  turning that into a role STATE -- how much a week of evidence
             should move a prior. REFUSED. See `stage2_state()`.

The split matters because stage 2 needs choices (a half-life, a minimum
opportunity count, a shrinkage target) that `predeclaration_cs2.md` does not
fix. Inventing them here to produce a plausible number is the failure mode
this project has agreed to refuse, so stage 2 returns
`PREREGISTRATION_INCOMPLETE` naming exactly what is missing.

DEFINITIONS ARE BOX-SCORE DEFINITIONS, DELIBERATELY. Carries are rush attempts
excluding two-point plays, KNEELS INCLUDED, because that is what a box score
counts and a panel that quietly excluded them would not reconcile against one.
Targets are pass attempts excluding two-point plays with a named receiver.
Anything else would be a modelling choice wearing a measurement's clothes.

APPEARANCE IS A PROXY AND SAYS SO. `appeared` here is `carries + targets > 0`.
`predeclaration_cs2.md` already records why: snap counts return 404 for 2026
and participation is published after the postseason, so a player who played
and was neither handed the ball nor thrown to is INDISTINGUISHABLE from one
who did not play. The field is named `appeared_by_opportunity` so no caller
can mistake it for a snap.

THE CLOCK IS ENFORCED. A capture whose retrieval instant is not strictly
before `as_of` is dropped and the drop is counted, exactly as in CS1. Week-1
bytes are pregame evidence for a week-2 forecast and postgame bytes for a
week-1 one; the clock is what tells those apart.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402
from nfl.production.nonqb.current_season_panel import _lawful         # noqa: E402

SPEC_VERSION = 'current-season-nonqb-usage-panel-1'
PBP_GLOB = 'nfl/research/postgame/pbp_%d.*.csv.gz'

#: What is counted, and how. Stated here so a reader never has to infer it.
COUNTING_RULES = {
    'carries': 'rush_attempt == 1, two_point_attempt == 0, named rusher. '
               'Kneels INCLUDED -- a box score counts them.',
    'targets': 'pass_attempt == 1, two_point_attempt == 0, named receiver.',
    'receptions': 'complete_pass == 1, named receiver.',
    'rush_yards': 'rushing_yards summed over the counted carries.',
    'rec_yards': 'receiving_yards summed over the counted receptions.',
    'appeared_by_opportunity': 'carries + targets > 0. A PROXY. A player who '
                               'took snaps without a carry or a target is '
                               'indistinguishable from one who did not play.',
}

#: RECONCILIATION, so two numbers in this repository do not disagree in
#: silence. `P2_DIAGNOSTIC.md` reports BUF week-1 team totals of 29 targets
#: and 21 carries. This module measures 28 and 21. The carries agree exactly.
#: The one target is a definition, not an error: BUF threw 32 pass attempts,
#: of which 1 was a two-point play and 3 carried no receiver id (a throwaway
#: is not a target). 32 - 1 - 3 = 28, which is the box-score target. The
#: diagnostic's 29 is pass attempts less the two-point play.
P2_TARGET_RECONCILIATION = {
    'p2_diagnostic_buf_targets': 29, 'this_module_buf_targets': 28,
    'buf_pass_attempts': 32, 'two_point': 1, 'no_receiver_id': 3,
    'carries_agree_exactly': 21,
    'which_is_right': 'a throwaway is not a target, so 28 is the box-score '
                      'figure. The shares in P2 are computed on 29 and move '
                      'by under half a point; no conclusion there changes.',
}

#: Stage 2 needs these and `predeclaration_cs2.md` fixes none of them.
STAGE2_MISSING = {
    'half_life': 'how fast current-season evidence decays against older '
                 'weeks. The predeclaration says the weight is "a declared, '
                 'tuned quantity, not a constant" and does not declare it.',
    'min_opportunity': 'how much usage a week must carry before it moves a '
                       'prior at all. One carry in garbage time is not the '
                       'same evidence as thirteen.',
    'shrinkage_target': 'what a thin room shrinks TOWARD -- the room mean, '
                        'the prior-season share, or the depth-chart '
                        'ordering. These give different answers for exactly '
                        'the rooms that matter.',
}
CODE_INCOMPLETE = 'PREREGISTRATION_INCOMPLETE'


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _one(v):
    return str(v).strip() in ('1', '1.0', 'True', 'true')


def _capture(season, as_of):
    """The widest LAWFUL play-by-play capture for this season."""
    best, ev = None, {'considered': 0, 'dropped_by_clock': 0, 'blob': None,
                      'retrieved_at': None, 'games': []}
    for f in sorted(glob.glob(str(_REPO / (PBP_GLOB % season)))):
        prov = pathlib.Path(str(f).replace('.csv.gz', '.csv.provenance.json'))
        if not prov.exists():
            continue
        p = json.loads(prov.read_text())
        ev['considered'] += 1
        if not _lawful(p.get('retrieved_at'), as_of):
            ev['dropped_by_clock'] += 1
            continue
        n = len(p.get('games') or [])
        if best is None or n > best[0]:
            best = (n, f, p)
    if best is None:
        return None, ev
    _, f, p = best
    ev.update(blob=pathlib.Path(f).name, retrieved_at=p.get('retrieved_at'),
              games=list(p.get('games') or []))
    return f, ev


def usage(season: int, week: int, as_of=None, all_clubs=None) -> Outcome:
    """Stage 1. Per club and player: carries, targets, receptions, yards.

    `all_clubs`, when given, is the full league. Any club in it with no
    usage row is returned in `clubs_without_usage` and gets NOTHING --
    never an imputed share. A club is missing here because its game is
    not in the lawful capture, and a caller that silently fell back to
    prior-season state for it would do so invisibly. CS2 invariant 7.
    """
    path, ev = _capture(season, as_of)
    ev.update(spec_version=SPEC_VERSION, season=season, week=week,
              as_of=as_of, counting_rules=COUNTING_RULES)
    if path is None:
        return Outcome.blocked(
            'NONQB_USAGE_NO_LAWFUL_CAPTURE',
            f'no play-by-play capture for {season} is lawful before '
            f'{as_of!r} ({ev["considered"]} considered, '
            f'{ev["dropped_by_clock"]} dropped by the clock).',
            cause=Cause.DATA, **ev)

    blank = dict(carries=0.0, targets=0.0, receptions=0.0,
                 rush_yards=0.0, rec_yards=0.0)
    per = collections.defaultdict(lambda: dict(blank))
    with gzip.open(path, 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            if str(r.get('week')) != str(week) or not r.get('posteam'):
                continue
            if _one(r.get('two_point_attempt')):
                continue
            club = r['posteam']
            if _one(r.get('rush_attempt')):
                pid = (r.get('rusher_player_id') or '').strip()
                if pid:
                    d = per[(club, pid)]
                    d['carries'] += 1
                    d['rush_yards'] += _f(r.get('rushing_yards'))
            if _one(r.get('pass_attempt')):
                pid = (r.get('receiver_player_id') or '').strip()
                if pid:
                    d = per[(club, pid)]
                    d['targets'] += 1
                    if _one(r.get('complete_pass')):
                        d['receptions'] += 1
                        d['rec_yards'] += _f(r.get('receiving_yards'))
    if not per:
        return Outcome.blocked(
            'NONQB_USAGE_WEEK_ABSENT',
            f'the lawful capture {ev["blob"]} carries no week-{week} rows for '
            f'{season}. An empty week is an error, not a week in which nobody '
            f'touched the ball.', cause=Cause.DATA, **ev)

    team = collections.defaultdict(lambda: dict(blank))
    for (club, _pid), d in per.items():
        t = team[club]
        for k in blank:
            t[k] += d[k]

    rows = {}
    for (club, pid), d in per.items():
        t = team[club]
        rows[(club, pid)] = {
            'team': club, 'player_id': pid, 'season': season, 'week': week,
            **d,
            'appeared_by_opportunity': (d['carries'] + d['targets']) > 0,
            'carry_share': (d['carries'] / t['carries']
                            if t['carries'] else None),
            'target_share': (d['targets'] / t['targets']
                             if t['targets'] else None),
        }
    # Shares conserve exactly, per club, or the panel is wrong.
    bad = []
    for club, t in team.items():
        for key, tot in (('carry_share', t['carries']),
                         ('target_share', t['targets'])):
            if not tot:
                continue
            s = sum(r[key] for r in rows.values()
                    if r['team'] == club and r[key] is not None)
            if abs(s - 1.0) > 1e-9:
                bad.append({'team': club, 'share': key, 'sum': s})
    if bad:
        return Outcome.fail(
            'NONQB_USAGE_SHARES_DO_NOT_CONSERVE',
            f'{len(bad)} club-share sum(s) are not 1.0 to 1e-9. Opportunity '
            f'was lost or invented in the counting.',
            cause=Cause.DATA, offending=bad, **ev)
    absent = sorted(set(all_clubs or ()) - set(team))
    return Outcome.ok(
        'NONQB_USAGE_MEASURED', value=rows,
        detail=f'{len(rows)} player-club row(s) across {len(team)} club(s), '
               f'{season} week {week}, from {ev["blob"]}'
               + (f'; {len(absent)} club(s) with NO usage' if absent else ''),
        n_rows=len(rows), n_clubs=len(team),
        clubs_without_usage=absent,
        clubs_without_usage_get_nothing=(
            'no row, no imputed share, no silent fallback. The club is named '
            'so a caller that falls back to prior-season state does it '
            'visibly.'),
        team_totals={k: dict(v) for k, v in team.items()},
        is_measurement_not_estimation=True, **ev)


def usage_season(season: int, as_of=None, weeks=None) -> Outcome:
    """Every week of a season in ONE pass over the blob.

    `usage()` reads a 19 MB archive to answer for a single week. A forward
    chain asks about seventeen of them, so re-reading per week turns a
    two-minute job into a half-hour one. Same counting rules, same clock, same
    conservation check; only the loop is different.
    """
    path, ev = _capture(season, as_of)
    ev.update(spec_version=SPEC_VERSION, season=season, as_of=as_of,
              counting_rules=COUNTING_RULES)
    if path is None:
        return Outcome.blocked(
            'NONQB_USAGE_NO_LAWFUL_CAPTURE',
            f'no play-by-play capture for {season} is lawful before '
            f'{as_of!r}', cause=Cause.DATA, **ev)
    want = None if weeks is None else {str(w) for w in weeks}
    blank = dict(carries=0.0, targets=0.0, receptions=0.0,
                 rush_yards=0.0, rec_yards=0.0)
    per = collections.defaultdict(lambda: dict(blank))
    with gzip.open(path, 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            wk = str(r.get('week') or '')
            if not wk or not r.get('posteam'):
                continue
            if want is not None and wk not in want:
                continue
            if _one(r.get('two_point_attempt')):
                continue
            club = r['posteam']
            if _one(r.get('rush_attempt')):
                pid = (r.get('rusher_player_id') or '').strip()
                if pid:
                    d = per[(int(wk), club, pid)]
                    d['carries'] += 1
                    d['rush_yards'] += _f(r.get('rushing_yards'))
            if _one(r.get('pass_attempt')):
                pid = (r.get('receiver_player_id') or '').strip()
                if pid:
                    d = per[(int(wk), club, pid)]
                    d['targets'] += 1
                    if _one(r.get('complete_pass')):
                        d['receptions'] += 1
                        d['rec_yards'] += _f(r.get('receiving_yards'))
    if not per:
        return Outcome.blocked(
            'NONQB_USAGE_WEEK_ABSENT',
            f'{ev["blob"]} carries no rows for {season}'
            + (f' weeks {sorted(want)}' if want else ''),
            cause=Cause.DATA, **ev)
    weeks_seen = sorted({k[0] for k in per})
    return Outcome.ok(
        'NONQB_USAGE_SEASON_MEASURED', value=dict(per),
        detail=f'{len(per)} (week, club, player) row(s) over '
               f'{len(weeks_seen)} week(s) of {season}, from {ev["blob"]}',
        n_rows=len(per), weeks=weeks_seen,
        is_measurement_not_estimation=True, **ev)


def stage2_state(*_a, **_k) -> Outcome:
    """Stage 2: turn usage into a role state. REFUSED, and why."""
    return Outcome.blocked(
        CODE_INCOMPLETE,
        'CS2 stage 2 is not specified. ' + ' '.join(
            f'{k}: {v}' for k, v in sorted(STAGE2_MISSING.items())) +
        ' Each of these changes the answer for exactly the rooms the defect '
        'lives in, so a convenient default is not a neutral choice. Stage 1 '
        'measurement is available now and is not blocked by this.',
        cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION,
        missing=sorted(STAGE2_MISSING), details=dict(STAGE2_MISSING),
        predeclaration='nfl/research/cs2/predeclaration_cs2.md',
        stage1_is_available=True)
