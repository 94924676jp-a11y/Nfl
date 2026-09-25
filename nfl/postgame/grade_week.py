"""Join a frozen pregame board to realised outcomes. One row per comparison.

THE TWO TRUTHS ARE NEVER MIXED

A row carries the pregame fields EXACTLY as the board froze them -- candidate
identity, information cut, run_id, market timestamp, line, model probability,
no-vig book probability -- and the realised fields beside them. Nothing
pregame is recomputed here, so a regrade cannot quietly improve a forecast.

WHY A MARKET IS GRADED ONLY WHEN ITS GAME IS IN THE SNAPSHOT

A game absent from the results feed produces zeros on every join, and zeros
are indistinguishable from a player who did nothing. Those rows are emitted
with grade_state=GAME_RESULT_NOT_PUBLISHED and are excluded from every
metric rather than scored as losses.

OUTCOME_INTERPRETATION IS EVIDENCE-BACKED OR IT IS NOT SET

A prop that wins because its player left in the first quarter is not the same
evidence as one that wins on a full workload. The field exists so that view
can be filtered. It is populated ONLY from ingested evidence; with no in-game
or snap data for a game every row reads NORMAL with the basis stated, and the
filtered calibration view is reported as not yet computable rather than
silently equal to the unfiltered one.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import join_provenance as JP
from nfl.postgame import actuals as A  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'nfl-postgame-grading-1'

#: market name -> realised quantity. Read from the actuals schema, never
#: guessed: a market whose quantity is not here is refused BY NAME.
MARKET_TO_ACTUAL = {
    'Player Receiving Yards': ('receiving_yards',),
    'Player Receptions': ('receptions',),
    'Player Rushing Yards': ('rushing_yards',),
    'Player Rushing Attempts': ('carries',),
    'Player Rushing + Receiving Yards': ('rushing_yards', 'receiving_yards'),
    'Player Passing Yards': ('passing_yards',),
    'Player Passing Completions': ('completions',),
    'Player Passing Attempts': ('attempts',),
    'Player Passing Touchdowns': ('passing_tds',),
    'Player Interceptions': ('passing_interceptions',),
    'Player Field Goals Made': ('fg_made',),
}

#: board metric key -> realised column(s). Keys read off the emitted board,
#: not remembered: a renamed layer silently drops out of the report unless it
#: is named here, so the mapping is explicit and small.
WORKLOAD_METRIC = {
    'receiving/targets': ('targets',),
    'receiving/receptions': ('receptions',),
    'receiving/receiving_yards': ('receiving_yards',),
    'receiving/receiving_td': ('receiving_tds',),
    'rushing/carries': ('carries',),
    'rushing/rushing_yards': ('rushing_yards',),
    'rushing/rushing_td': ('rushing_tds',),
    'rushing_total/rushing_yards': ('rushing_yards',),
    'qb/att': ('attempts',),
    'qb/cmp': ('completions',),
    'qb/pyds': ('passing_yards',),
    'qb/ptd': ('passing_tds',),
    'qb/int': ('passing_interceptions',),
    'qb/ryds': ('rushing_yards',),
    'qb/rtd': ('rushing_tds',),
}


def _settle(actual, line, side):
    """Over/under settlement. A push is a push, not a half-win."""
    if actual is None or line is None:
        return None
    if actual > line:
        return 'WIN' if side == 'OVER' else 'LOSS'
    if actual < line:
        return 'LOSS' if side == 'OVER' else 'WIN'
    return 'PUSH'


def build(package_path, season=2026, week=2) -> Outcome:
    pkg = json.loads(pathlib.Path(package_path).read_text())
    act = A.load_weekly(season, week)
    if act.state.name != 'PASS':
        return act
    by_id = act.value
    graded_games = set(act.evidence['games_present'])
    pv = pkg['provenance']
    run_by_game = {r['game_id']: r for r in pv['runs']}
    common = {
        'season': season, 'week': week,
        'model_configuration': pkg['READ_THIS_FIRST'].get(
            'model_configuration'),
        'pregame_information_cut': pv['information_cut'],
        'candidate_status': 'CANDIDATE_NOT_ACCEPTED_BASELINE',
        'actuals_snapshot': act.evidence['snapshot'],
        'actuals_snapshot_sha256': act.evidence['snapshot_sha256'],
    }
    rows = []
    dfs_by_id = {(d['game_id'], d['gsis_id']): d for d in pkg['dfs_board']}

    for r in pkg['football_board']:
        a = by_id.get(r['gsis_id'])
        published = r['game_id'] in graded_games
        run = run_by_game.get(r['game_id'], {})
        row = dict(common)
        row.update({
            'row_type': 'PLAYER_GAME_PROJECTION',
            'game_id': r['game_id'], 'gsis_id': r['gsis_id'],
            'player': r['player'], 'team': r['team'],
            'opponent': r['opponent'], 'position': r['position'],
            'run_id': r['run_id'], 'n_draws': r['n_draws'],
            'grade_state': ('GRADED' if published and a else
                            'GAME_RESULT_NOT_PUBLISHED' if not published else
                            'PLAYER_ABSENT_FROM_RESULTS'),
            # This grader joins on gsis_id ONLY -- `by_id` is keyed on the
            # actuals' player_id and there is no name path to fall back to --
            # so a miss here is genuinely "not in the results", never a
            # spelling failure wearing a zero. Stated rather than assumed,
            # because that is the difference join_provenance.py exists for.
            'join_provenance': (JP.stamp(JP.MATCHED_BY_IDENTITY,
                                         key=r['gsis_id'],
                                         zero_basis=JP.REAL_ZERO)
                                if published and a else
                                JP.stamp(JP.PLAYER_NOT_IN_OUTCOME,
                                         key=r['gsis_id'])),
            'outcome_interpretation': 'NORMAL',
            'outcome_interpretation_basis':
                'NO_IN_GAME_OR_SNAP_EVIDENCE_AVAILABLE_FOR_THIS_GAME',
            'execution_identity': run.get('execution_identity'),
            'code_commit': run.get('code_commit'),
        })
        # Projected vs realised for every workload quantity the board
        # actually carries for this player. A metric he has no layer for is
        # left absent, never zero: "the model emitted no rushing layer for a
        # slot receiver" and "the model projected zero carries" are different
        # statements and only one of them is a forecast.
        for metric, cols in WORKLOAD_METRIC.items():
            st = (r.get('stats') or {}).get(metric)
            if not st:
                continue
            short = metric.split('/')[-1]
            row[f'proj_{short}_mean'] = st.get('mean')
            row[f'proj_{short}_p50'] = st.get('p50')
            row[f'proj_{short}_p90'] = st.get('p90')
            row[f'proj_{short}_p95'] = st.get('p95')
            if a:
                row[f'actual_{short}'] = round(sum(a[c] for c in cols), 3)
        dk = dfs_by_id.get((r['game_id'], r['gsis_id']))
        if dk:
            k = dk['dk']
            row.update({
                'proj_dk_mean': k['mean'], 'proj_dk_p50': k['p50'],
                'proj_dk_p10': k['p10'], 'proj_dk_p90': k['p90'],
                'proj_dk_p95': k['p95'], 'proj_dk_sd': k['sd'],
                'proj_dk_p_zero': k['p_zero'],
                'proj_dk_p_ge_10': dk.get('p_ge_10'),
                'proj_dk_p_ge_15': dk.get('p_ge_15'),
                'proj_dk_p_ge_20': dk.get('p_ge_20'),
                'proj_dk_p_ge_30': dk.get('p_ge_30'),
            })
            if a:
                row['actual_dk_points'] = A.dk_points_actual(a)
        rows.append(row)

    for r in pkg['prop_board']['rows']:
        if r.get('support') != 'EXACT_SIMULATION_SUPPORTED':
            continue
        gid = None
        for g in graded_games | set(pv['games_expected']):
            parts = g.split('_')
            if len(parts) >= 4 and r.get('game') == f'{parts[2]}@{parts[3]}':
                gid = g
                break
        a = by_id.get(r['gsis_id'])
        cols = MARKET_TO_ACTUAL.get(r['market'])
        published = gid in graded_games if gid else False
        actual = None
        if a and cols:
            actual = round(sum(a[c] for c in cols), 3)
        side = ('OVER' if (r.get('edge_over') or 0) >= (r.get('edge_under')
                or 0) else 'UNDER')
        line = float(r['line']) if r.get('line') not in (None, '') else None
        row = dict(common)
        row.update({
            'row_type': 'PLAYER_PROP_MARKET',
            'game_id': gid, 'gsis_id': r['gsis_id'], 'player': r['player'],
            'team': r.get('team'), 'opponent': r.get('opponent'),
            'position': r.get('position'), 'run_id': None,
            'market': r['market'], 'line': line, 'side': side,
            'sportsbook': r.get('sportsbook'),
            'market_capture_utc': r.get('market_snapshot_time'),
            'book_line_timestamp_utc': r.get('book_line_timestamp_utc'),
            'over_price': r.get('over_price'),
            'under_price': r.get('under_price'),
            'model_p_over': r.get('model_p_over'),
            'model_p_under': r.get('model_p_under'),
            'model_p_push': r.get('model_p_push'),
            'model_probability': (r.get('model_p_over') if side == 'OVER'
                                  else r.get('model_p_under')),
            'novig_p_over': r.get('novig_p_over'),
            'novig_p_under': r.get('novig_p_under'),
            'novig_probability': (r.get('novig_p_over') if side == 'OVER'
                                  else r.get('novig_p_under')),
            'book_hold': r.get('book_hold'),
            'raw_edge': (r.get('edge_over') if side == 'OVER'
                         else r.get('edge_under')),
            'mcse_over': r.get('mcse_over'),
            'model_mean': r.get('model_mean'),
            'model_median': r.get('model_median'),
            'model_p25': r.get('model_p25'),
            'model_p75': r.get('model_p75'),
            'model_p95': r.get('model_p95'),
            'market_movement': json.dumps(r.get('market_movement') or {}),
            'realized_result': actual,
            'settlement': _settle(actual, line, side) if published else None,
            'grade_state': ('GRADED' if published and a and cols else
                            'GAME_RESULT_NOT_PUBLISHED' if not published else
                            'MARKET_HAS_NO_MAPPED_ACTUAL' if not cols else
                            'PLAYER_ABSENT_FROM_RESULTS'),
            # Same identity-only join. `cols` failing is a THIRD thing again:
            # the market has no mapped actual, which is a coverage gap in the
            # mapping and not a statement about the player at all.
            'join_provenance': (JP.stamp(JP.MATCHED_BY_IDENTITY,
                                         key=r['gsis_id'],
                                         zero_basis=JP.REAL_ZERO)
                                if published and a and cols else
                                JP.stamp(JP.PLAYER_NOT_IN_OUTCOME,
                                         key=r['gsis_id'])),
            'outcome_interpretation': 'NORMAL',
            'outcome_interpretation_basis':
                'NO_IN_GAME_OR_SNAP_EVIDENCE_AVAILABLE_FOR_THIS_GAME',
        })
        rows.append(row)

    return Outcome.ok('GRADING_ROWS_BUILT', value=rows,
                      spec_version=SPEC_VERSION,
                      n_rows=len(rows),
                      games_graded=sorted(graded_games
                                          & set(pv['games_expected'])),
                      games_not_published=sorted(
                          set(pv['games_expected']) - graded_games))
