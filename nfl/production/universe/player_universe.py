"""The authoritative point-in-time player universe for one game.

WHAT IT ANSWERS AND WHAT IT REFUSES TO ANSWER

It answers WHO EXISTS and WHETHER THE MODEL SUPPORTS THEM. It does not touch
workload, targets, carries, snaps, fantasy value or any optimizer quantity.
Ben VanSumeren appears here with his club-declared depth position attached
and his carries untouched: whether a fullback should out-carry a lead back is
a ROLE question and it belongs to the model that comes after P0-C.

CHRONOLOGY IS THE SELECTOR'S JOB, NOT A FILTER HERE

Every input is drawn through `vintage_selector.select(family, as_of=cut)`,
which returns the single lawful capture at the information cut or a named
refusal. There is no "latest file" path in this module: a post-cut depth
chart cannot be reached, because it is never selected.

EVERY EXPECTED PLAYER LANDS IN EXACTLY ONE STATE

Blueprint 1.2. The states are a closed set in `support_state`, assignment is
by declared precedence, and the classifier RAISES if a row would leave with
no state. "Absent from the board" is not a state.
"""
from __future__ import annotations

import csv
import gzip
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import vintage_selector as VS          # noqa: E402
from nfl.production.universe import depth_role as DR
from nfl.production.universe import support_state as S           # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome     # noqa: E402

SPEC_VERSION = 'nfl-player-universe-1'


def _rows(blob):
    p = _REPO / blob
    op = gzip.open if str(p).endswith('.gz') else open
    with op(p, 'rt', newline='') as f:
        return list(csv.DictReader(f))


def _roster_blob(v) -> str:
    """The RAW roster blob, because the reduced one drops `status`.

    The selector's own evidence ceiling for this family says it: "The reduced
    vintage DROPS `status`, so the reduced blobs cannot answer roster
    membership at all." Roster membership is the entire question here, so
    using the reduced blob would answer it with a column that is not there.
    """
    b = v.blob
    return b.replace('.reduced.csv.gz', '.raw.csv.gz')


def classify(r: dict, *, inactive_ids: set, emitted_ids: set,
             evidence_missing: bool, removed_ids: set) -> tuple[str, str, int]:
    """(support_state, why, evidence_tier). Precedence order, first wins."""
    pid = r.get('gsis_id') or ''
    if not pid:
        return (S.IDENTITY_UNRESOLVED,
                'the roster row carries no gsis_id, so nothing downstream can '
                'be attributed to this person', 3)
    if pid in removed_ids:
        return (S.REMOVED_BY_GOVERNED_RULE,
                'excluded by a declared governing rule', 2)
    if pid in inactive_ids:
        return (S.OFFICIALLY_INACTIVE,
                'named on the official inactive list for this game', 1)
    if (r.get('position') or '') not in S.SUPPORTED_POSITIONS:
        return (S.OUTSIDE_SUPPORTED_POSITION,
                f'roster position {r.get("position")!r} is outside the '
                f'positions this engine models; a declared scope limit, not '
                f'a defect', 3)
    if (r.get('status') or '') not in S.ACTIVE_ROSTER_STATUS:
        return (S.ROSTERED_BUT_NOT_EXPECTED_TO_PARTICIPATE,
                f'roster status {r.get("status")!r} is not an active '
                f'game-day status. This states what the ROSTER says; it is '
                f'not an inference about availability, and an elevation '
                f'would be a transaction this module has not been given', 3)
    if pid in emitted_ids:
        return (S.PROJECTED, 'the model emitted a row for this player', 3)
    if evidence_missing:
        return (S.EVIDENCE_DEFERRED,
                'a required evidence family was unavailable at the '
                'information cut, so support cannot yet be decided', 3)
    return (S.MODEL_UNSUPPORTED,
            'active, on a supported position, not officially inactive, and '
            'the model emitted NO row for him. A coverage gap, not an '
            'availability one', 3)


def build(season: int, week: int, game_id: str, written_at: str, *,
          emitted_ids=None, inactive_ids=None, removed_ids=None,
          salary_resolved_ids=None) -> Outcome:
    """One row per player in the point-in-time universe for `game_id`.

    `emitted_ids` is the set of gsis_ids the model actually wrote. Passing
    None means "no model output supplied", which is a legitimate state (the
    universe can be built before a forecast runs) and every otherwise-active
    supported player then reads MODEL_UNSUPPORTED.
    """
    emitted_ids = set(emitted_ids or ())
    inactive_ids = set(inactive_ids or ())
    removed_ids = set(removed_ids or ())
    salary_resolved_ids = (None if salary_resolved_ids is None
                           else set(salary_resolved_ids))

    parts = (game_id or '').split('_')
    if len(parts) < 4:
        return Outcome.blocked(
            'GAME_ID_UNPARSEABLE',
            f'{game_id!r} is not SEASON_WEEK_AWAY_HOME, so the two clubs '
            f'cannot be named', cause=Cause.DATA)
    clubs = (parts[2], parts[3])

    sources, evidence_missing = {}, False
    for fam in ('weekly_rosters', 'depth_charts', 'injuries'):
        o = VS.select(fam, as_of=written_at)
        if o.state.name != 'PASS':
            if fam == 'weekly_rosters':
                return Outcome.blocked(
                    'UNIVERSE_ROSTER_VINTAGE_UNAVAILABLE',
                    f'no lawful weekly_rosters capture at {written_at}: '
                    f'{o.code}. Without a roster there is no universe to '
                    f'classify, and guessing one is the defect.',
                    cause=Cause.DATA)
            evidence_missing = True
            sources[fam] = {'state': o.state.name, 'code': o.code}
            continue
        sources[fam] = {'state': 'PASS', 'blob': o.value.blob,
                        'content_sha256': o.value.content_sha256,
                        'retrieved_at': o.value.retrieved_at,
                        'published_at': o.value.published_at}

    ros_v = VS.select('weekly_rosters', as_of=written_at).value
    roster = [r for r in _rows(_roster_blob(ros_v))
              if r.get('season') == str(season) and r.get('week') == str(week)
              and r.get('team') in clubs]
    if not roster:
        return Outcome.blocked(
            'UNIVERSE_EMPTY_FOR_GAME',
            f'the lawful roster vintage carries no rows for {clubs} in '
            f'{season} week {week}. An empty universe is not a universe.',
            cause=Cause.DATA)

    depth = {}
    if sources.get('depth_charts', {}).get('state') == 'PASS':
        best = {}
        for d in _rows(sources['depth_charts']['blob']):
            if d.get('team') not in clubs or not d.get('gsis_id'):
                continue
            k = (d['team'], d['gsis_id'])
            # The vendor `dt` is a real publication clock; the newest slice at
            # or before the cut is already all the selector returned, so the
            # max here orders WITHIN that lawful capture.
            if k not in best or (d.get('dt') or '') > (best[k].get('dt') or ''):
                best[k] = d
        depth = best

    inj = {}
    if sources.get('injuries', {}).get('state') == 'PASS':
        for i in _rows(sources['injuries']['blob']):
            if (i.get('season') == str(season) and i.get('week') == str(week)
                    and i.get('gsis_id')):
                inj[i['gsis_id']] = i

    rows = []
    for r in sorted(roster, key=lambda x: (x.get('team') or '',
                                           x.get('position') or '',
                                           x.get('full_name') or '')):
        pid = r.get('gsis_id') or ''
        d = depth.get((r.get('team'), pid), {})
        j = inj.get(pid, {})
        state, why, tier = classify(
            r, inactive_ids=inactive_ids, emitted_ids=emitted_ids,
            evidence_missing=evidence_missing, removed_ids=removed_ids)
        if state not in S.FOOTBALL_STATES:
            raise AssertionError(
                f'classify returned {state!r}, which is not one of the '
                f'declared states. A row with no state is the defect this '
                f'module exists to prevent.')
        row = {
            'game_id': game_id, 'season': season, 'week': week,
            'team': r.get('team'),
            'opponent': clubs[1] if r.get('team') == clubs[0] else clubs[0],
            'gsis_id': pid, 'display_name': r.get('full_name'),
            'football_name': r.get('football_name'),
            'roster_position': r.get('position'),
            'roster_depth_chart_position': r.get('depth_chart_position'),
            'roster_status': r.get('status'),
            'roster_status_abbr': r.get('status_description_abbr'),
            'jersey_number': r.get('jersey_number'),
            'years_exp': r.get('years_exp'),
            'rookie_year': r.get('rookie_year'),
            'pfr_id': r.get('pfr_id') or None,
            'espn_id': r.get('espn_id') or None,
            'depth_pos_abb': d.get('pos_abb'),
            'depth_rank': d.get('pos_rank'),
            'depth_dt': d.get('dt'),
            # SEPARATE EVIDENCE AXES. A depth listing is two different facts
            # and this row used to carry them as one. `offensive_depth_role`
            # is a rank that may inform a workload room; `special_teams_role`
            # is standing on a return or kicking unit and informs no room at
            # all. A player is KR2 on one axis and OFFENSIVE_DEPTH_UNKNOWN on
            # the other without either contaminating the other.
            'offensive_depth_rank': DR.offensive_depth_rank(
                r.get('position'), d.get('pos_abb'), d.get('pos_rank'))[0],
            'offensive_depth_state': DR.offensive_depth_rank(
                r.get('position'), d.get('pos_abb'), d.get('pos_rank'))[1],
            'special_teams_role': DR.special_teams_role(
                d.get('pos_abb'), d.get('pos_rank')),
            'injury_report_status': j.get('report_status') or None,
            'injury_practice_status': j.get('practice_status') or None,
            'officially_inactive': pid in inactive_ids,
            'support_state': state,
            'support_state_why': why,
            'evidence_tier': tier,
            'information_cut': written_at,
        }
        # SALARY IDENTITY IS A SEPARATE AXIS. It is attached only when a DK
        # universe was supplied, and it never participates in the football
        # state above.
        if salary_resolved_ids is not None:
            row['salary_identity_state'] = (
                S.SALARY_IDENTITY_RESOLVED if pid in salary_resolved_ids
                else S.SALARY_IDENTITY_UNRESOLVED)
        rows.append(row)

    counts = {}
    for r in rows:
        counts[r['support_state']] = counts.get(r['support_state'], 0) + 1
    unaccounted = [r for r in rows if r['support_state'] not in
                   S.FOOTBALL_STATES]
    return Outcome.ok(
        'PLAYER_UNIVERSE_BUILT', value=rows,
        spec_version=SPEC_VERSION, game_id=game_id, clubs=list(clubs),
        information_cut=written_at, n_players=len(rows),
        support_state_counts=counts,
        n_unaccounted=len(unaccounted),
        evidence_missing=evidence_missing, sources=sources,
        detail=f'{len(rows)} player(s) across {clubs[0]} and {clubs[1]}, '
               f'every one in exactly one declared support state')
