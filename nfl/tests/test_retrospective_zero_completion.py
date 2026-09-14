"""ZERO BY COMPLETION: the scored set must not be chosen by the outcome.

WHAT THIS PROTECTS.

  * A MISSING PLAYER IS A ZERO. `actuals` emits a record only for a player who
    recorded at least one target, carry or dropback. In a COMPLETED game an
    absent record is therefore an observed zero, not an unknown. Version 1.0.0
    of `same_day_retrospective` refused those rows -- and they are exactly the
    rows where the model forecast volume and the player produced none, i.e.
    every over-forecast. Deleting them moved pooled bias from -4.80 to -0.07,
    reversed the sign on nine of eleven metrics, and moved interval coverage
    from 0.643 to 0.837 at the 50% level. The regression test is that an
    absent player is SCORED AGAINST ZERO, not refused.

  * A MISSING FIELD IS STILL A MAPPING BUG. The opposite error is just as
    expensive: when the record EXISTS and the field is absent, the estimand
    map is broken and zeroing it scored Puka Nacua's 74 receiving yards as 0.
    That row must be refused by name, never zeroed.

  * ZERO IS NOT THE ANSWER FOR EVERY ESTIMAND. A global missing-to-zero
    conversion is a second defect wearing the first one's clothes. An estimand
    classified MISSING_IF_ABSENT, NOT_APPLICABLE or UNRESOLVED must be refused
    by name even though the player is absent, and every estimand the scorer
    can reach must carry a classification at all.

  * ZERO BY COMPLETION IS LICENSED BY COMPLETION. Applied to a game that is
    not final it would invent zeros for plays that have not happened yet, so
    `score_seal` must refuse to run without proven finality rather than trust
    its caller.

  * ROWS ARE NOT INDEPENDENT. Player-rows inside a game move together. The
    statistics layer must emit game-clustered and player-game-clustered
    standard errors with their cluster counts, and must not emit a naive one.

  * A LEAKED STATISTIC MAY NOT RANK ANYTHING. The 2026-09-13 health artifact
    made `receiving/targets` its single ranking-eligible metric on a coverage
    figure the selection had created. The contract must now ask how the rows
    were chosen, and treat an undeclared answer as an outcome-conditional one.

EVERYTHING HERE RUNS ON A SYNTHETIC SEAL IN A TEMPORARY DIRECTORY. No live
artifact, ledger or board is read or written.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import model_health as MH                          # noqa: E402
from nfl.research import postgame as PG                             # noqa: E402
from nfl.research import same_day_retrospective as SDR              # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


GID = '2099_01_AAA_BBB'
KO = '2099_09_13T17:00:00Z'
FINAL = {'final': True, 'code': 'POSTGAME_FINAL', 'unmet': []}

# Three forecast subjects. Only WR_PLAYED appears in the play-by-play.
WR_PLAYED, WR_ZERO, QB_ZERO = 'ID_WR_PLAYED', 'ID_WR_ZERO', 'ID_QB_ZERO'


def _pbp():
    """Three pass plays, all to WR_PLAYED, thrown by a passer who is NOT a
    forecast subject. So WR_ZERO and QB_ZERO have no record, and the game is
    complete: both realised zero."""
    base = {'game_id': GID, 'posteam': 'AAA', 'qtr': '4',
            'game_seconds_remaining': '0', 'result': '7',
            'total_home_score': '7', 'total_away_score': '0'}
    rows = []
    for i in range(3):
        r = dict(base)
        r.update({'play_id': str(100 + i), 'pass_attempt': '1',
                  'rush_attempt': '0', 'sack': '0', 'qb_scramble': '0',
                  'qb_dropback': '1', 'two_point_attempt': '0',
                  'complete_pass': '1' if i < 2 else '0',
                  'passer_player_id': 'ID_OTHER_QB',
                  'passer_player_name': 'Other QB',
                  'receiver_player_id': WR_PLAYED,
                  'receiver_player_name': 'WR Played',
                  'receiving_yards': '10', 'passing_yards': '10',
                  'pass_touchdown': '0', 'interception': '0',
                  'yardline_100': '50', 'desc': 'pass'})
        rows.append(r)
    end = dict(base)
    end.update({'play_id': '999', 'desc': 'END GAME'})
    rows.append(end)
    return rows


def _seal(tmp, metrics_by_player=None):
    """A synthetic sealed board + manifest + draws. Returns the seal dir."""
    d = pathlib.Path(tmp) / 'pre_inactives_V1_CANDIDATE_R8' / 'seal0'
    d.mkdir(parents=True)
    mb = metrics_by_player or {
        WR_PLAYED: ('receiving', ['receiving/targets']),
        WR_ZERO: ('receiving', ['receiving/targets']),
        QB_ZERO: ('qb', ['qb/att']),
    }
    players, layers, arrays = [], {}, {}
    for pid, (lay, mets) in mb.items():
        players.append({
            'gsis_id': pid, 'team': 'AAA',
            'position': 'WR' if lay == 'receiving' else 'QB',
            'metrics': {m: {'mean': 4.0, 'kind': 'count'} for m in mets}})
        layers.setdefault(lay, {'row_ids': []})['row_ids'].append(pid)
    for lay, spec in layers.items():
        for pid in spec['row_ids']:
            for m in mb[pid][1]:
                key = m.replace('/', '__')
                arrays.setdefault(key, {})[pid] = np.full(200, 4.0)
    np_arrays = {}
    for key, per_pid in arrays.items():
        lay = key.split('__')[0]
        ids = layers[lay]['row_ids']
        np_arrays[key] = np.array([per_pid.get(p, np.zeros(200))
                                   for p in ids], float)
    np.savez(d / 'player_draws.npz', **np_arrays)
    (d / 'player_draws_manifest.json').write_text(json.dumps(
        {'game_id': GID, 'n_draws': 200, 'layers': layers}))
    (d / 'board.json').write_text(json.dumps({
        'game_id': GID, 'run_id': 'RUN_TEST', 'completeness': 'TEST',
        'freshness': {'written_at': '2099_09_13T15:00:00Z'},
        'players': players}))
    return d


def _score(d, rows, **kw):
    return SDR.score_seal(GID, KO, d, rows, 'sha_test',
                          {WR_PLAYED: 'WR Played'}, finality=FINAL, **kw)


# ------------------------------------------------- 1. the core regression
def test_absent_player_is_scored_as_zero_not_refused():
    with tempfile.TemporaryDirectory() as tmp:
        d = _seal(tmp)
        out, meta = _score(d, _pbp())
        by = {(r['gsis_id'], r['metric']): r for r in out}
        check('every forecast subject is scored', len(out) == 3,
              f'n={len(out)} refused={meta["n_refused"]}')
        check('no row is refused for having a zero outcome',
              meta['n_refused'] == 0, str(meta.get('refused_by_reason')))
        z = by.get((WR_ZERO, 'receiving/targets'))
        check('the absent receiver is present in the scored set', z is not None)
        if z:
            check('his realised value is 0.0', z['actual'] == 0.0,
                  repr(z['actual']))
            check('and is labelled ZERO_BY_COMPLETION',
                  z['actual_basis'] == 'ZERO_BY_COMPLETION', z['actual_basis'])
        q = by.get((QB_ZERO, 'qb/att'))
        check('the quarterback who never threw is scored at 0',
              q is not None and q['actual'] == 0.0
              and q['actual_basis'] == 'ZERO_BY_COMPLETION')
        p = by.get((WR_PLAYED, 'receiving/targets'))
        check('the receiver who played keeps his OBSERVED value',
              p is not None and p['actual'] == 3.0
              and p['actual_basis'] == 'OBSERVED',
              repr(p and (p['actual'], p['actual_basis'])))


# --------------------------------- 2. the restored rows ARE the over-forecasts
def test_restored_rows_are_exactly_the_over_forecasts():
    with tempfile.TemporaryDirectory() as tmp:
        d = _seal(tmp)
        new, _ = _score(d, _pbp())
        old, meta_old = _score(d, _pbp(), legacy_outcome_selection=True)
        old_keys = {(r['gsis_id'], r['metric']) for r in old}
        new_keys = {(r['gsis_id'], r['metric']) for r in new}
        restored = new_keys - old_keys
        check('the old rule is a strict subset of the new one',
              old_keys < new_keys, f'{len(old_keys)} < {len(new_keys)}')
        check('exactly the zero-outcome rows were missing',
              restored == {(WR_ZERO, 'receiving/targets'),
                           (QB_ZERO, 'qb/att')}, str(sorted(restored)))
        rest = [r for r in new if (r['gsis_id'], r['metric']) in restored]
        check('every restored row is an over-forecast',
              all(r['forecast_minus_actual'] > 0 for r in rest),
              str([r['forecast_minus_actual'] for r in rest]))
        check('the old rule refused them by the leaked reason',
              meta_old['refused_by_reason'].get(SDR.R_LEGACY_LEAK) == 2,
              str(meta_old['refused_by_reason']))
        check('and stamps its own selection basis as leaked',
              meta_old['outcome_selection_basis'] == SDR.SELECTION_LEAKED)
        check('while the repaired run declares a complete set',
              _score(d, _pbp())[1]['outcome_selection_basis']
              == SDR.SELECTION_COMPLETE)
        e_old = np.mean([r['forecast_minus_actual'] for r in old])
        e_new = np.mean([r['forecast_minus_actual'] for r in new])
        check('deleting them biased the pooled error downward',
              e_old < e_new, f'{e_old:+.4f} -> {e_new:+.4f}')


# ------------------------------------- 3. a missing FIELD is still a mapping bug
def test_missing_field_on_an_existing_record_is_refused_not_zeroed():
    with tempfile.TemporaryDirectory() as tmp:
        d = _seal(tmp)
        orig = dict(PG.EXACT_ESTIMANDS)
        try:
            PG.EXACT_ESTIMANDS['receiving/targets'] = ('receiving', 'no_such')
            out, meta = _score(d, _pbp())
        finally:
            PG.EXACT_ESTIMANDS.clear()
            PG.EXACT_ESTIMANDS.update(orig)
        scored = {(r['gsis_id'], r['metric']) for r in out}
        check('the player who DID play is refused, not scored as zero',
              (WR_PLAYED, 'receiving/targets') not in scored, str(scored))
        check('and the refusal is named as a mapping bug',
              meta['refused_by_reason'].get(SDR.R_FIELD_NOT_IN_ACTUALS) == 1,
              str(meta['refused_by_reason']))


# ------------------------------- 4. NOT a global missing-to-zero conversion
def test_absence_classes_other_than_zero_are_refused_by_name():
    cases = ((SDR.MISSING_IF_ABSENT, SDR.R_UNOBSERVED),
             (SDR.NOT_APPLICABLE, SDR.R_NOT_APPLICABLE),
             (SDR.UNRESOLVED, SDR.R_UNRESOLVED))
    for cls, code in cases:
        with tempfile.TemporaryDirectory() as tmp:
            d = _seal(tmp)
            orig = SDR.ABSENCE_SEMANTICS['receiving/targets']
            try:
                SDR.ABSENCE_SEMANTICS['receiving/targets'] = (cls, 'test')
                out, meta = _score(d, _pbp())
            finally:
                SDR.ABSENCE_SEMANTICS['receiving/targets'] = orig
            scored = {(r['gsis_id'], r['metric']) for r in out}
            check(f'{cls}: the absent player is NOT zeroed',
                  (WR_ZERO, 'receiving/targets') not in scored)
            check(f'{cls}: he is refused as {code}',
                  meta['refused_by_reason'].get(code) == 1,
                  str(meta['refused_by_reason']))
            check(f'{cls}: the player who played is still scored',
                  (WR_PLAYED, 'receiving/targets') in scored)


def test_an_unclassified_estimand_is_refused_not_guessed():
    with tempfile.TemporaryDirectory() as tmp:
        d = _seal(tmp)
        orig = SDR.ABSENCE_SEMANTICS.pop('receiving/targets')
        try:
            out, meta = _score(d, _pbp())
        finally:
            SDR.ABSENCE_SEMANTICS['receiving/targets'] = orig
        scored = {(r['gsis_id'], r['metric']) for r in out}
        check('an estimand with no declared absence class is not zeroed',
              (WR_ZERO, 'receiving/targets') not in scored)
        check('it is refused as ABSENCE_SEMANTICS_UNRESOLVED',
              meta['refused_by_reason'].get(SDR.R_UNRESOLVED) == 1,
              str(meta['refused_by_reason']))


def test_every_reachable_estimand_carries_a_classification():
    classes = {SDR.ZERO_IF_ABSENT, SDR.MISSING_IF_ABSENT,
               SDR.NOT_APPLICABLE, SDR.UNRESOLVED}
    missing = [m for m in PG.EXACT_ESTIMANDS if m not in SDR.ABSENCE_SEMANTICS]
    check('every EXACT estimand is classified', not missing, str(missing))
    missing2 = [m for m in PG.REFUSED_ESTIMANDS
                if m not in SDR.ABSENCE_SEMANTICS_REFUSED]
    check('every REFUSED estimand is classified too', not missing2,
          str(missing2))
    allc = dict(SDR.ABSENCE_SEMANTICS)
    allc.update(SDR.ABSENCE_SEMANTICS_REFUSED)
    allc.update(SDR.ABSENCE_SEMANTICS_DERIVED_RATES)
    bad = {k: v[0] for k, v in allc.items() if v[0] not in classes}
    check('every class is one of the four declared ones', not bad, str(bad))
    thin = {k for k, v in allc.items() if len(str(v[1])) < 40}
    check('every classification carries a written derivation', not thin,
          str(thin))
    check('a per-event RATE is never classified as zero',
          all(v[0] == SDR.MISSING_IF_ABSENT
              for k, v in SDR.ABSENCE_SEMANTICS_DERIVED_RATES.items()))
    check('a team aggregate is never classified as zero',
          SDR.ABSENCE_SEMANTICS['team_volume/team_carries'][0]
          == SDR.MISSING_IF_ABSENT)
    check('a yardage SUM is classified as zero, because an empty sum is zero',
          SDR.ABSENCE_SEMANTICS['receiving/receiving_yards'][0]
          == SDR.ZERO_IF_ABSENT
          and SDR.ABSENCE_SEMANTICS['qb/pyds'][0] == SDR.ZERO_IF_ABSENT)


# ------------------------------ 5. zero by completion requires completion
def test_zero_completion_refuses_to_run_without_proven_finality():
    with tempfile.TemporaryDirectory() as tmp:
        d = _seal(tmp)
        for fin in (None, {}, {'final': False, 'code': 'POSTGAME_NOT_FINAL'}):
            try:
                SDR.score_seal(GID, KO, d, _pbp(), 'sha', {}, finality=fin)
                check(f'finality={fin!r} refused', False, 'it did not raise')
            except RuntimeError as e:
                check(f'finality={fin!r} refused',
                      'ZERO_COMPLETION_WITHOUT_PROVEN_FINALITY' in str(e))
        out, _ = SDR.score_seal(GID, KO, d, _pbp(), 'sha', {}, finality=None,
                                legacy_outcome_selection=True)
        check('the legacy rule needs no finality proof, because it zeroes '
              'nothing', len(out) == 1, f'n={len(out)}')


# ------------------------------------------- 6. clustering, and no naive SE
def test_stats_cluster_and_refuse_a_naive_se():
    rows = []
    for g in range(4):
        for p in range(3):
            for m in ('a', 'b'):
                rows.append({'game_id': f'G{g}', 'gsis_id': f'P{g}_{p}',
                             'metric': m, 'forecast_minus_actual': 1.0 + g,
                             'abs_error': 1.0 + g, 'crps': 0.5, 'pit': 0.5,
                             'in_50': True, 'in_80': True, 'in_90': True,
                             'actual_basis': 'OBSERVED'})
    st = SDR._stats(rows)
    check('game clusters counted', st['n_game_clusters'] == 4,
          str(st['n_game_clusters']))
    check('player-game clusters counted',
          st['n_player_game_clusters'] == 12,
          str(st['n_player_game_clusters']))
    check('a game-clustered SE is emitted',
          st['se_mean_signed_error_game_clustered'] is not None)
    check('a player-game-clustered SE is emitted',
          st['se_mean_signed_error_player_game_clustered'] is not None)
    check('a clustered SE for coverage is emitted too',
          'se_coverage_50_game_clustered' in st)
    naive = [k for k in st if 'naive' in k and not isinstance(st[k], str)]
    check('no naive SE is emitted as a number', not naive, str(naive))
    check('the SE convention is stated on the stats block',
          'NAIVE SE IS NOT EMITTED' in str(st['se_convention']))
    check('rows are labelled as not being a sample size',
          'n_rows_is_not_a_sample_size' in st)
    check('a single cluster yields no clustered SE',
          SDR._cluster_se([1.0, 2.0, 3.0], ['G', 'G', 'G']) is None)
    # A DEGENERATE CLUSTERING MUST SAY SO. With one row per player-game the
    # player-game SE is the naive SE, and a table that does not say that
    # reads as two robustness layers when it is one.
    check('a non-degenerate player-game clustering is labelled as such',
          st['player_game_clustering_degenerate'] is False)
    one_each = [dict(r, gsis_id=f'P{i}') for i, r in enumerate(rows)]
    st1 = SDR._stats(one_each)
    check('one row per player-game is flagged degenerate',
          st1['player_game_clustering_degenerate'] is True)
    check('and the flag explains that it is the naive SE',
          'IS the naive SE' in st1['player_game_clustering_note'])
    # Correlation inside a cluster must WIDEN the interval relative to
    # treating the rows as independent. Constructed so it does.
    x = [r['forecast_minus_actual'] for r in rows]
    naive_se = float(np.std(x, ddof=1) / np.sqrt(len(x)))
    check('the clustered SE is wider than a naive one on clustered data',
          st['se_mean_signed_error_game_clustered'] > naive_se,
          f"{st['se_mean_signed_error_game_clustered']:.4f} > "
          f'{naive_se:.4f}')
    check('PIT is published as not interpretable while its own defect stands',
          st['pit_interpretable'] is False)


# ------------------------------------------- 7. the health gate must ask
def test_health_treats_an_undeclared_selection_as_outcome_conditional():
    o = {'n': 40, 'coverage_50': 0.90, 'coverage_80': 0.95}
    r = MH.evaluate('receiving/targets', outcome_stats=o)
    check('an undeclared selection basis raises the warning',
          'OUTCOME_CONDITIONAL_SELECTION' in r['warnings'], str(r['warnings']))
    check('and the metric cannot rank', r['ranking_eligible'] is False)
    r2 = MH.evaluate('receiving/targets', outcome_stats=o,
                     outcome_selection_basis=MH.SELECTION_COMPLETE,
                     n_game_clusters=9, n_zero_completed=50)
    check('a declared complete selection clears that warning',
          'OUTCOME_CONDITIONAL_SELECTION' not in r2['warnings'])
    check('the zero-completed count is published',
          r2['n_zero_completed_rows'] == 50)
    check('the cluster count is published beside n_scored',
          r2['n_game_clusters'] == 9 and r2['n_scored'] == 40)
    m = {'n': 20, 'pct_under': 0.5, 'hit_rate_excl_push': 0.6}
    r3 = MH.evaluate('x/y', outcome_stats=o, market_stats=m,
                     outcome_selection_basis=MH.SELECTION_COMPLETE)
    check('an undeclared MARKET selection basis raises its own warning',
          'MARKET_STATS_OUTCOME_SELECTED' in r3['warnings'], str(r3['warnings']))
    r4 = MH.evaluate('x/y', outcome_stats=o,
                     outcome_selection_basis=MH.SELECTION_COMPLETE,
                     carried_warnings=('MARKET_GAP_ANTICALIBRATED',))
    check('a warning carried from a superseded artifact is kept',
          'MARKET_GAP_ANTICALIBRATED' in r4['warnings']
          and r4['ranking_eligible'] is False)
    try:
        MH.evaluate('x/y', outcome_stats=o, carried_warnings=('MADE_UP',))
        check('an unknown carried warning is refused', False, 'no raise')
    except ValueError as e:
        check('an unknown carried warning is refused',
              'MODEL_HEALTH_UNKNOWN_CARRIED_WARNING' in str(e))
    check('every warning in the vocabulary carries a meaning',
          all(isinstance(v, str) and len(v) > 20 for v in MH.WARNINGS.values()))
    check('the selection fields are in the published contract',
          {'n_zero_completed_rows', 'n_game_clusters',
           'outcome_selection_basis', 'market_selection_basis'}
          <= set(MH.FIELDS))
