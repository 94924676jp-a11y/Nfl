"""The slate board: one row per player, every number with its evidence.

WHAT THIS IS FOR

Fantasy Cruncher gives a projection. This gives a projection that can defend
itself. Every row carries not just `carries 12.8` but the grade of the
evidence under it, the tier that produced it, how it moved since the last
refresh and why.

The columns a conventional optimizer has are here so the board is usable.
The columns it cannot have are the point:

    projected carries | evidence MEASURED 2026 W1 | 18 observed
    projection change +3.2 | cause: declared starter + teammate inactive
    review verdict    | BLOCKING_REVIEW: role unsupported

THREE RULES THIS FILE DOES NOT BEND

1. **A missing value is never a zero.** No salary is `SALARY_UNAVAILABLE` and
   not optimizer-eligible. No projection is `NOT_EMITTED`. No current-season
   average is `COLD_START`. A reader can always tell "we measured nothing"
   from "we measured zero".
2. **Every delta has a cause or it is not published as explained.** A row whose
   projection moved and whose cause is `UNEXPLAINED` says so in the cause
   field. There is no "model refresh" bucket that absorbs everything.
3. **The board never invents a number the model did not emit.** It reads
   draws, dossiers and attribution. It computes value (a ratio of two numbers
   already here) and nothing else.
"""
from __future__ import annotations

import collections
import csv
import datetime as _dt
import hashlib
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import evidence as EV                     # noqa: E402
from nfl.production.state import availability as AV                    # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome        # noqa: E402

SPEC_VERSION = 'nfl-player-board-1'

SALARY_UNAVAILABLE = 'SALARY_UNAVAILABLE'
NOT_EMITTED = 'NOT_EMITTED'

#: Column order. Fixed so two boards from different weeks are diffable and a
#: CSV reader can rely on it.
COLUMNS = (
    'player', 'gsis_id', 'team', 'opponent', 'position', 'salary',
    'injury_status', 'practice_status', 'availability',
    'offensive_depth', 'special_teams', 'role', 'role_support',
    'proj_snap_share', 'proj_carries', 'proj_targets', 'proj_receptions',
    'proj_pass_yards', 'proj_rush_yards', 'proj_rec_yards',
    'proj_pass_td', 'proj_rush_td', 'proj_rec_td', 'td_expectation',
    'dk_mean', 'dk_floor_p10', 'dk_median', 'dk_ceiling_p90', 'dk_p95',
    'dk_sd', 'p_zero', 'value_per_1k',
    'current_season_avg', 'previous_season_avg',
    'evidence_grade', 'uncertainty', 'opportunity_basis',
    'review_verdict', 'conflict_codes',
    'dk_delta', 'carries_delta', 'targets_delta', 'change_cause',
    'change_evidence',
)

#: The causes a projection movement may be attributed to. A movement whose
#: cause is not one of these is UNEXPLAINED, and that is a finding.
CAUSES = (
    'TEAMMATE_INACTIVE', 'STARTER_PROMOTION', 'SNAP_TREND',
    'PRACTICE_OR_INJURY', 'TEAM_VOLUME_CHANGE', 'DEPTH_CHANGE',
    'CURRENT_SEASON_EVIDENCE', 'MODEL_UPDATE', 'REDISTRIBUTION',
    'WEATHER', 'UNCERTAINTY_CHANGE', 'NEW_TO_BOARD', 'UNEXPLAINED',
)

#: Which cause an availability MOVE is attributed to, by explicit state
#: membership. Every state the availability vocabulary declares is named
#: here, and a state that is not named falls through to the next cause test
#: rather than being guessed at.
#:
#: THE DEFECT THIS REPLACES. This was
#:
#:     'PRACTICE_OR_INJURY' if 'INACTIVE' not in str(av) else 'TEAMMATE_INACTIVE'
#:
#: a SUBSTRING test, written when the only values were 'ACTIVE' and
#: 'INACTIVE'. The availability vocabulary now contains
#: 'NOT_ON_INACTIVE_LIST', and that string CONTAINS 'INACTIVE', so a player
#: who moved from UNKNOWN to NOT_ON_INACTIVE_LIST -- a change that asserts
#: nothing at all -- would have been attributed to a teammate going out.
#: Membership in a declared set cannot make that mistake.
#:
#: The label TEAMMATE_INACTIVE is a misnomer for the branch it serves: it
#: fires when THIS player is the one who will not play. It is kept because
#: renaming a cause is a change to the board's vocabulary and this commit
#: fixes one bug. Registered.
AVAILABILITY_CAUSE = {
    # he will not take the field
    'INACTIVE': 'TEAMMATE_INACTIVE',
    AV.OFFICIAL_INACTIVE: 'TEAMMATE_INACTIVE',
    AV.INJURY_OUT: 'TEAMMATE_INACTIVE',
    # the club published something about his condition
    AV.INJURY_DOUBTFUL: 'PRACTICE_OR_INJURY',
    AV.INJURY_QUESTIONABLE: 'PRACTICE_OR_INJURY',
    # these assert nothing about whether he plays
    AV.NOT_ON_INACTIVE_LIST: 'PRACTICE_OR_INJURY',
    AV.UNKNOWN: 'PRACTICE_OR_INJURY',
    # pre-availability-slice values, still readable on an older board
    'ACTIVE': 'PRACTICE_OR_INJURY',
    'NOT_DECLARED': 'PRACTICE_OR_INJURY',
}

#: Below this DK-point movement a delta is not worth attributing. Declared
#: review choice, not fitted: it is roughly one reception and cannot reorder
#: a lineup on its own.
MATERIAL_DELTA_DK = 1.0


def _num(v, nd=4):
    return None if v is None else round(float(v), nd)


def _q(vec, p):
    import numpy as np
    a = np.asarray(vec, float)
    return float(np.percentile(a, p)) if a.size else None


def _summ(M, i):
    import numpy as np
    v = np.asarray(M[i], float)
    if v.size == 0:
        return {}
    return {'mean': float(v.mean()),
            'sd': float(v.std(ddof=1)) if v.size > 1 else 0.0,
            'p10': _q(v, 10), 'p50': _q(v, 50), 'p90': _q(v, 90),
            'p95': _q(v, 95), 'p_zero': float((v <= 0).mean())}


#: layer/metric -> board column
DRAW_MAP = {
    'dk_scoring/dk_points': 'dk',
    'rushing/carries': 'proj_carries',
    'rushing/rushing_yards': 'proj_rush_yards',
    'rushing/rushing_td': 'proj_rush_td',
    'receiving/targets': 'proj_targets',
    'receiving/receptions': 'proj_receptions',
    'receiving/receiving_yards': 'proj_rec_yards',
    'receiving/receiving_td': 'proj_rec_td',
    'qb/pyds': 'proj_pass_yards',
    'qb/ptd': 'proj_pass_td',
}


def _draw_table(arrays, layers) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = collections.defaultdict(dict)
    for key, col in DRAW_MAP.items():
        layer = key.split('/')[0]
        M = arrays.get(key)
        ids = (layers.get(layer) or {}).get('row_ids') or []
        if M is None:
            continue
        if len(ids) != M.shape[0]:
            raise ValueError(
                f'{key}: {M.shape[0]} rows against {len(ids)} row_ids. '
                f'Reading a board off a misaligned axis attributes one '
                f'player\'s numbers to another.')
        for i, pid in enumerate(ids):
            out[pid][col] = _summ(M, i)
    return dict(out)


def load_salaries(path) -> Outcome:
    """{gsis_id: salary} from a DK salary universe artifact.

    Reads the resolved `join` rows, which carry the identity the artifact
    already established. Rows WITHOUT a gsis_id are counted and named, never
    dropped silently: an unmatched salary row is a player the board cannot
    price, and that is a finding rather than an absence.
    """
    p = pathlib.Path(path)
    if not p.exists():
        return Outcome.blocked(
            'SALARY_ARTIFACT_ABSENT',
            f'{p} does not exist, so no row can be priced. Every row then '
            f'reads SALARY_UNAVAILABLE and none is optimizer-eligible.',
            cause=Cause.DATA)
    j = json.loads(p.read_text())
    rows = j.get('join') or []
    out, unmatched, no_salary = {}, [], []
    for r in rows:
        pid, sal = r.get('gsis_id'), r.get('dk_salary')
        if not pid:
            unmatched.append(r.get('dk_name'))
            continue
        if sal in (None, '', 0):
            no_salary.append(r.get('dk_name'))
            continue
        out[pid] = float(sal)
    if not out:
        return Outcome.fail(
            'SALARY_JOIN_EMPTY',
            f'{len(rows)} salary row(s) read from {p.name} and none resolved '
            f'to a gsis_id. An empty join read as "no salaries exist" is the '
            f'failure mode this project pays for most.',
            value={'n_rows': len(rows)})
    return Outcome.ok(
        'SALARIES_LOADED',
        {'salary': out, 'n_rows': len(rows), 'n_matched': len(out),
         'n_unmatched_identity': len(unmatched),
         'unmatched_identity': sorted(x for x in unmatched if x)[:40],
         'n_without_salary': len(no_salary),
         'source': str(p), 'season': j.get('season'), 'week': j.get('week')},
        detail=f'{len(out)} of {len(rows)} salary row(s) resolved to a '
               f'gsis_id; {len(unmatched)} unmatched identity')


def _cause(row, prev, dossier, run_identity=None, prev_identity=None) -> Dict[str, Any]:
    """Why did this number move? Named, or named as unexplained."""
    if prev is None:
        return {'cause': 'NEW_TO_BOARD', 'evidence': 'first appearance on '
                                                     'this slate board'}
    # A CHANGE OF MODEL IS A CAUSE, AND THE BOARD MUST BE TOLD.
    #
    # MEASURED DEFECT: comparing a baseline board against a CS6 board, all
    # four material moves came back UNEXPLAINED -- correctly by the rules the
    # board had, because nothing on the ROW changed. What changed was the
    # engine. A change log that cannot see its own run identity attributes a
    # known model change to "nothing explains this", which discredits the one
    # label that is supposed to mean something.
    model_changed = (run_identity is not None and prev_identity is not None
                     and run_identity != prev_identity)
    a, b = row.get('dk_mean'), prev.get('dk_mean')
    # NOT_EMITTED is a STRING, not a zero -- that is the whole point of the
    # sentinel, and treating it as 0.0 would manufacture a delta out of an
    # absence. A row that gained or lost a projection is its own finding.
    if not isinstance(a, float) or not isinstance(b, float):
        if isinstance(a, float) and not isinstance(b, float):
            return {'cause': 'MODEL_UPDATE',
                    'evidence': f'the model emitted no projection for him '
                                f'before and emits {a:.2f} now'}
        if isinstance(b, float) and not isinstance(a, float):
            return {'cause': 'MODEL_UPDATE',
                    'evidence': f'the model projected {b:.2f} before and '
                                f'emits nothing now'}
        return {'cause': None, 'evidence': None}
    d = a - b
    if abs(d) < MATERIAL_DELTA_DK:
        return {'cause': None, 'evidence': None}

    av, pav = row.get('availability'), prev.get('availability')
    if av != pav:
        c = AVAILABILITY_CAUSE.get(str(av))
        if c is not None:
            return {'cause': c,
                    'evidence': f'availability {pav} -> {av}'}
    if row.get('offensive_depth') != prev.get('offensive_depth'):
        return {'cause': 'DEPTH_CHANGE',
                'evidence': f'offensive depth {prev.get("offensive_depth")} '
                            f'-> {row.get("offensive_depth")}'}
    if row.get('role') != prev.get('role'):
        return {'cause': 'STARTER_PROMOTION' if row.get('role') == 'STARTER'
                else 'SNAP_TREND',
                'evidence': f'role {prev.get("role")} -> {row.get("role")}'}
    if row.get('opportunity_basis') != prev.get('opportunity_basis'):
        return {'cause': 'CURRENT_SEASON_EVIDENCE',
                'evidence': f'opportunity basis '
                            f'{prev.get("opportunity_basis")} -> '
                            f'{row.get("opportunity_basis")}'}
    if (dossier is not None
            and dossier.axis('vacated_opportunity').grade == EV.REDISTRIBUTED):
        return {'cause': 'REDISTRIBUTION',
                'evidence': 'opportunity assigned after a teammate became '
                            'unavailable'}
    if row.get('evidence_grade') != prev.get('evidence_grade'):
        return {'cause': 'CURRENT_SEASON_EVIDENCE',
                'evidence': f'evidence grade {prev.get("evidence_grade")} -> '
                            f'{row.get("evidence_grade")}'}
    if row.get('uncertainty') != prev.get('uncertainty'):
        return {'cause': 'UNCERTAINTY_CHANGE',
                'evidence': f'{prev.get("uncertainty")} -> '
                            f'{row.get("uncertainty")}'}
    if model_changed:
        return {'cause': 'MODEL_UPDATE',
                'evidence': f'DK moved {d:+.2f} and nothing on this row '
                            f'changed; the engine did: '
                            f'{prev_identity} -> {run_identity}'}
    return {'cause': 'UNEXPLAINED',
            'evidence': f'DK moved {d:+.2f} and nothing on this row changed. '
                        f'This is a finding, not a bucket: an unexplained '
                        f'material move means the board cannot see what the '
                        f'model did.'}


def build(*, slate_key: str, dossiers: Sequence[Any],
          arrays: Optional[dict] = None, layers: Optional[dict] = None,
          salaries: Optional[Dict[str, Any]] = None,
          gate_rows: Optional[Sequence[dict]] = None,
          attribution: Optional[Dict[str, dict]] = None,
          current_season: Optional[Dict[str, list]] = None,
          previous_board: Optional[Dict[str, dict]] = None,
          run_identity: Optional[str] = None,
          previous_run_identity: Optional[str] = None,
          information_cut: Optional[str] = None) -> Outcome:
    """One board row per dossier. Refuses on an empty population."""
    if not dossiers:
        return Outcome.blocked(
            'BOARD_POPULATION_EMPTY',
            'no dossiers were supplied, so there is no board. An empty board '
            'read as "no players" is the defect this project pays for most.',
            cause=Cause.DATA)

    try:
        draws = _draw_table(arrays or {}, layers or {})
    except ValueError as exc:
        return Outcome.fail('BOARD_DRAW_AXIS_MISALIGNED', str(exc))

    verdict_by_id: Dict[str, str] = {}
    codes_by_id: Dict[str, set] = collections.defaultdict(set)
    for c in (gate_rows or ()):
        pid = c.get('gsis_id')
        if not pid:
            continue
        codes_by_id[pid].add(c.get('code'))
        if c.get('disposition') == 'BLOCKING':
            verdict_by_id[pid] = 'BLOCKING_REVIEW'
        elif verdict_by_id.get(pid) != 'BLOCKING_REVIEW':
            verdict_by_id[pid] = 'CLEARED_WITH_WARNING'

    rows: List[Dict[str, Any]] = []
    changes: List[Dict[str, Any]] = []
    for d in dossiers:
        pid = d.gsis_id
        dr = draws.get(pid) or {}
        dk = dr.get('dk') or {}
        sal = (salaries or {}).get(pid)
        att = (attribution or {}).get(pid) or {}
        cs = (current_season or {}).get(pid) or []

        def m(col, stat='mean'):
            return _num((dr.get(col) or {}).get(stat))

        row = {
            'player': d.display_name, 'gsis_id': pid, 'team': d.team,
            'opponent': d.opponent,
            'position': d.value('room') and d.axis('room').value,
            'salary': sal if sal is not None else SALARY_UNAVAILABLE,
            'injury_status': (d.axis('injury_designation').value or {}
                              ).get('report'),
            'practice_status': (d.axis('injury_designation').value or {}
                                ).get('practice'),
            'availability': d.axis('official_availability').value,
            'offensive_depth': d.value('offensive_depth_rank'),
            'special_teams': d.value('special_teams_role'),
            'role': d.value('role'), 'role_support': d.value('role_support'),
            'proj_snap_share': _num(d.value('current_season_snap_share')),
            'proj_carries': m('proj_carries'),
            'proj_targets': m('proj_targets'),
            'proj_receptions': m('proj_receptions'),
            'proj_pass_yards': m('proj_pass_yards'),
            'proj_rush_yards': m('proj_rush_yards'),
            'proj_rec_yards': m('proj_rec_yards'),
            'proj_pass_td': m('proj_pass_td'),
            'proj_rush_td': m('proj_rush_td'),
            'proj_rec_td': m('proj_rec_td'),
            'dk_mean': _num(dk.get('mean')) if dk else NOT_EMITTED,
            'dk_floor_p10': _num(dk.get('p10')),
            'dk_median': _num(dk.get('p50')),
            'dk_ceiling_p90': _num(dk.get('p90')),
            'dk_p95': _num(dk.get('p95')),
            'dk_sd': _num(dk.get('sd')),
            'p_zero': _num(dk.get('p_zero')),
            'current_season_avg': (
                _num(sum(float(r.get('carries') or 0)
                         + float(r.get('targets') or 0) for r in cs) / len(cs))
                if cs else EV.COLD_START),
            'previous_season_avg': _num(
                (att.get('contributions') or {}).get('PRIOR_SEASON_MEASURED')),
            'evidence_grade': att.get('evidence_grade') or d.axis(
                'current_season_snap_share').grade,
            'uncertainty': d.uncertainty_state,
            'opportunity_basis': att.get('basis'),
            'review_verdict': verdict_by_id.get(pid, 'CLEARED'),
            'conflict_codes': ';'.join(sorted(x for x in codes_by_id.get(pid, ())
                                              if x)),
        }
        td = sum(x for x in (row['proj_pass_td'], row['proj_rush_td'],
                             row['proj_rec_td']) if isinstance(x, float))
        row['td_expectation'] = _num(td) if td else None
        row['value_per_1k'] = (
            _num(row['dk_mean'] / (float(sal) / 1000.0))
            if isinstance(row['dk_mean'], float) and isinstance(sal, (int, float))
            and float(sal) > 0 else None)

        prev = (previous_board or {}).get(pid)
        for col, key in (('dk_mean', 'dk_delta'),
                         ('proj_carries', 'carries_delta'),
                         ('proj_targets', 'targets_delta')):
            a, b = row.get(col), (prev or {}).get(col)
            row[key] = (_num(a - b) if isinstance(a, float)
                        and isinstance(b, float) else None)
        c = _cause(row, prev, d, run_identity, previous_run_identity)
        row['change_cause'] = c['cause']
        row['change_evidence'] = c['evidence']
        if c['cause'] and c['cause'] != 'NEW_TO_BOARD':
            changes.append({
                'player': row['player'], 'gsis_id': pid, 'team': row['team'],
                'dk_before': (prev or {}).get('dk_mean'),
                'dk_after': row['dk_mean'], 'dk_delta': row['dk_delta'],
                'carries_before': (prev or {}).get('proj_carries'),
                'carries_after': row['proj_carries'],
                'targets_before': (prev or {}).get('proj_targets'),
                'targets_after': row['proj_targets'],
                'cause': c['cause'], 'evidence': c['evidence']})
        rows.append(row)

    rows.sort(key=lambda r: -(r['dk_mean'] if isinstance(r['dk_mean'], float)
                              else -1))
    unexplained = [c for c in changes if c['cause'] == 'UNEXPLAINED']
    return Outcome.ok(
        'PLAYER_BOARD_BUILT',
        {'rows': rows, 'changes': changes,
         'n_rows': len(rows),
         'n_with_projection': sum(1 for r in rows
                                  if isinstance(r['dk_mean'], float)),
         'n_with_salary': sum(1 for r in rows
                              if r['salary'] != SALARY_UNAVAILABLE),
         'n_changes': len(changes),
         'n_unexplained_changes': len(unexplained),
         'unexplained': unexplained,
         'by_verdict': dict(collections.Counter(
             r['review_verdict'] for r in rows)),
         'slate_key': slate_key, 'information_cut': information_cut,
         'run_identity': run_identity,
         'previous_run_identity': previous_run_identity,
         'columns': list(COLUMNS), 'spec_version': SPEC_VERSION},
        detail=f'{len(rows)} row(s), '
               f'{sum(1 for r in rows if isinstance(r["dk_mean"], float))} '
               f'projected, {len(changes)} change(s), '
               f'{len(unexplained)} unexplained')


def write(board: Dict[str, Any], out_dir) -> Outcome:
    """Board JSON + CSV + the change log, digested."""
    d = pathlib.Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    rows = board['rows']
    if not rows:
        return Outcome.blocked('BOARD_EMPTY_ON_WRITE',
                               'refusing to write an empty board',
                               cause=Cause.DATA)
    jp = d / 'PLAYER_BOARD.json'
    body = json.dumps({**board,
                       'written_at_utc': _dt.datetime.now(
                           _dt.timezone.utc).isoformat()},
                      indent=1, sort_keys=True, default=str).encode()
    jp.write_bytes(body)

    cp = d / 'PLAYER_BOARD.csv'
    with cp.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(COLUMNS), extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)

    lp = d / 'PROJECTION_CHANGE_LOG.json'
    lp.write_text(json.dumps(
        {'slate_key': board['slate_key'],
         'information_cut': board.get('information_cut'),
         'n_changes': board['n_changes'],
         'n_unexplained': board['n_unexplained_changes'],
         'material_delta_dk': MATERIAL_DELTA_DK,
         'causes_declared': list(CAUSES),
         'changes': board['changes']}, indent=1, default=str))

    n = sum(1 for _ in csv.DictReader(cp.open()))
    if n != len(rows):
        return Outcome.fail(
            'BOARD_WRITE_COUNT_MISMATCH',
            f'{len(rows)} rows built but {n} in the CSV. A partial write read '
            f'as success is the defect class this project pays for most.',
            value={'built': len(rows), 'on_disk': n})
    return Outcome.ok(
        'PLAYER_BOARD_WRITTEN',
        {'json': str(jp), 'csv': str(cp), 'change_log': str(lp),
         'n_rows': n, 'sha256': hashlib.sha256(body).hexdigest()},
        detail=f'{n} rows -> {cp}')
