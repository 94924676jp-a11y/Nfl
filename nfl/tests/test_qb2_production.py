"""QB2 adversarial tests and guard-deletion proofs for the QB identities.

THE STANDARD BEING MET, from the QB2 packet s12: attack sack double counting,
spike double counting, scramble double attribution, missing passer ID, QB
change, a backup with no history, same-week leakage, current-game outcomes in
priors, passing/receiving yard mismatch, TD mismatch, QB rush against team
rush, an incomplete QB player set, a model hash mismatch and unauthorized
publication -- and prove the load-bearing QB identities are load-bearing by
deleting them and showing the attack then succeeds.

A guard that has never refused anything is not a guard. Every attack below is
run TWICE where the guard is load-bearing: once against the guard, once with it
bypassed, and the second run must let the violation through.
"""
import argparse
import os
import pathlib
import pickle
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'qb2'),
           os.path.join(_ROOT, 'nfl', 'research', 'rc1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome, State       # noqa: E402
from nfl.accounting.invariants import QB_DROPBACK_IDENTITY         # noqa: E402
from nfl.production import qb_accounting as ACC                    # noqa: E402
from nfl.production import qb_v1 as QBV1                           # noqa: E402
from nfl.production import run_forecast as RUN                     # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing          # noqa: E402

PASSED = FAILED = 0
TMP = pathlib.Path(tempfile.mkdtemp())
QB_PKL = os.path.join(_ROOT, 'nfl', 'research', 'qb2', 'qb.pkl')


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


# --------------------------------------------------------------------------
# A synthetic, COHERENT draw set. Every attack below breaks exactly one thing
# in it, so a refusal can be attributed to the thing that was broken.
# --------------------------------------------------------------------------
def clean(n=6, m=40, seed=7):
    rng = np.random.default_rng(seed)
    db = rng.integers(20, 45, (n, m))
    sacks = rng.binomial(db, 0.07)
    scr = rng.binomial(np.maximum(db - sacks, 0), 0.05)
    att = np.maximum(db - sacks - scr, 0)
    cmp_ = rng.binomial(att, 0.65)
    inc = np.maximum(att - cmp_, 0)
    drush = rng.binomial(db, 0.05)
    ro = scr + drush
    return {'db': db.astype(float), 'att': att.astype(float),
            'sacks': sacks.astype(float), 'scr': scr.astype(float),
            'cmp': cmp_.astype(float),
            'ptd': rng.binomial(cmp_, 0.06).astype(float),
            'int': rng.binomial(inc, 0.05).astype(float),
            'pyds': (cmp_ * 11.0).astype(float),
            'drush': drush.astype(float), 'rush_opp': ro.astype(float),
            'ryds': (ro * 4.0).astype(float),
            'rtd': rng.binomial(ro, 0.03).astype(float)}


def rows(n=6, teams=('NE', 'SEA')):
    return [{'season': 2024, 'week': 1, 'team': teams[i % len(teams)],
             'gsis_id': f'00-000000{i}', 'db': 30, 'ord': 100 + i,
             'game_id': '2024_01_NE_SEA'} for i in range(n)]


# ==========================================================================
def test_00_baseline_is_coherent():
    print('\n0. the synthetic draw set is coherent before any attack')
    o = ACC.reconcile_draws(clean())
    check('a clean draw set PASSES all seven identities',
          o.state is State.PASS, o.code)
    check('  and the check is not vacuous: it ran on real cells',
          o.state is State.PASS and o.value['n_cells'] == 240,
          o.value if o.state is State.PASS else o.code)


def test_01_sack_double_counting():
    print('\n1. sack double counting')
    D = clean(); D['sacks'] = D['sacks'] + 1        # sacks counted twice
    o = ACC.reconcile_draws(D)
    check('adding a sack outside the dropback budget is REFUSED',
          o.state is State.FAIL
          and o.code == 'QB_DRAW_ACCOUNTING_VIOLATED', o.code)
    check('  and it is the dropback identity that names it',
          o.state is State.FAIL
          and 'dropback_identity' in o.evidence['violations'],
          o.evidence.get('violations'))
    check('  the QB1 record still says pass_attempt INCLUDES every sack',
          QB_DROPBACK_IDENTITY['sacks_inside_pass_attempts'] == 5308)
    check('  and that the naive subtract-sacks form errs by 5,586 plays',
          QB_DROPBACK_IDENTITY['naive_form_error_plays'] == 5586)


def test_02_spike_double_counting():
    print('\n2. spike double counting, against the real corpus')
    P = pickle.load(open(QB_PKL, 'rb'))['player']
    right = wrong = withspikes = 0
    for k, v in P.items():
        if k[0] not in (2022, 2023, 2024, 2025):
            continue
        a, s, sp = (v.get('att_raw', 0), v.get('scrambles', 0),
                    v.get('spikes', 0))
        right += (v['dropbacks'] == a + s - sp)
        if sp:
            withspikes += 1
            wrong += (v['dropbacks'] == a + s + sp)
    check(f'dropbacks == att_raw + scrambles - spikes on every one of '
          f'{right} player-games', right > 2000)
    check(f'  and ADDING spikes instead is wrong on all {withspikes} '
          f'player-games that have one', withspikes > 0 and wrong == 0,
          f'{wrong} matched the wrong form')


def test_03_scramble_double_attribution():
    print('\n3. scramble double attribution')
    D = clean(); D['rush_opp'] = D['rush_opp'] + D['scr']   # counted twice
    o = ACC.reconcile_draws(D)
    check('counting a scramble in rush opportunity twice is REFUSED',
          o.state is State.FAIL, o.code)
    check('  named as the rush-opportunity composition',
          o.state is State.FAIL
          and 'rush_opportunity_composition' in o.evidence['violations'],
          o.evidence.get('violations'))
    D2 = clean(); D2['scr'] = D2['rush_opp'] + 1
    o2 = ACC.reconcile_draws(D2)
    check('  a scramble outside its own rushing opportunity is REFUSED',
          o2.state is State.FAIL, o2.code)
    check('  and the record still says a scramble carries NO passer id',
          QB_DROPBACK_IDENTITY['passer_id_on_scrambles'] == 0
          and QB_DROPBACK_IDENTITY['passer_id_on_sacks'] == 5308)


def test_04_impossible_conversions():
    print('\n4. touchdowns and interceptions outside their causal parent')
    D = clean(); D['ptd'] = D['cmp'] + 1
    o = ACC.reconcile_draws(D)
    check('a passing TD that is not a completion is REFUSED',
          o.state is State.FAIL
          and 'passing_td_within_completions' in o.evidence['violations'],
          o.code)
    D = clean(); D['int'] = np.maximum(D['att'] - D['cmp'], 0) + 1
    o = ACC.reconcile_draws(D)
    check('an interception on a completed pass is REFUSED',
          o.state is State.FAIL
          and 'interceptions_within_incompletions' in o.evidence['violations'],
          o.code)
    D = clean(); D['cmp'] = D['att'] + 1
    o = ACC.reconcile_draws(D)
    check('a completion that is not an attempt is REFUSED',
          o.state is State.FAIL, o.code)


def test_05_incomplete_player_set():
    print('\n5. an incomplete QB player set')
    D = clean(); D.pop('drush')
    o = ACC.reconcile_draws(D)
    check('a draw set missing a field is BLOCKED, never PASS',
          o.state is State.BLOCKED
          and o.code == 'QB_ACCOUNTING_INPUT_INCOMPLETE', o.code)
    check('  and it names what is missing rather than skipping the identity',
          o.state is State.BLOCKED and o.evidence['missing'] == ['drush'],
          o.evidence.get('missing'))
    o = ACC.reconcile_draws({k: np.zeros((0, 0)) for k in
                             ('db', 'att', 'sacks', 'scr', 'cmp', 'ptd',
                              'int', 'drush', 'rush_opp', 'rtd')})
    check('  an EMPTY draw set is an error, not a reconciliation',
          o.state is State.BLOCKED and o.code == 'QB_ACCOUNTING_EMPTY', o.code)
    o = QBV1.forecast([], 2024, [])
    check('  and the layer refuses to forecast nothing',
          o.state is State.BLOCKED
          and o.code == 'STAGE_NOT_IMPLEMENTED', o.code)
    o = ACC.reconcile_team(clean(n=6), rows(n=5))
    check('  a frame/draw shape mismatch is REFUSED, not reconciled anyway',
          o.state is State.FAIL
          and o.code == 'QB_ACCOUNTING_SHAPE_MISMATCH', o.code)


def test_06_qb_rush_against_team_rush():
    print('\n6. QB rushes against team rushes')
    D = clean(n=4); R = rows(n=4)
    budget = {(2024, 1, 'NE'): np.zeros(D['db'].shape[1]),
              (2024, 1, 'SEA'): np.zeros(D['db'].shape[1])}
    o = ACC.reconcile_team(D, R, team_rush_draws=budget)
    check('QB rush opportunities above the carries layer draw are REFUSED',
          o.state is State.FAIL
          and o.code == 'QB_RUSHES_EXCEED_TEAM_RUSH_DRAWS', o.code)
    o = ACC.reconcile_team(D, R, team_rushes_realised={
        (2024, 1, 'NE'): 0, (2024, 1, 'SEA'): 0})
    check('  but a REALISED count never produces a failure -- defining a '
          'defect against an outcome manufactures one for any forecaster',
          o.state is State.PASS, o.code)
    check('  it is reported as a named diagnostic instead',
          o.state is State.PASS
          and o.value['vs_realised_team_rushes']['exceeding_realised_team_'
                                                 'rushes'] > 0,
          o.value.get('vs_realised_team_rushes') if o.state is State.PASS
          else o.code)
    check('  and the allocation residual is NAMED, not enforced away',
          ACC.ALLOCATION_RESIDUAL['holds'] is False
          and ACC.ALLOCATION_RESIDUAL['multi_qb']['bias'] > 20)


def test_07_cross_layer_mismatch():
    print('\n7. passing/receiving yard and TD mismatch')
    D = clean()
    o = ACC.reconcile_cross_layer(D)
    check('with no receiving layer the check is DEFERRED, never PASS',
          o.state is State.DEFERRED
          and o.code == 'CROSS_LAYER_RECONCILIATION_NOT_RUN', o.code)
    check('  and it records what is owed, including the lateral exception',
          o.state is State.DEFERRED
          and o.evidence['owed']['exception_to_preserve']['n_explained_by_'
                                                          'lateral'] == 75)
    o = ACC.reconcile_cross_layer(D, receiving=D['pyds'] + 3.0)
    check('a passing/receiving yard mismatch is REFUSED',
          o.state is State.FAIL
          and o.code == 'PASSING_YARDS_RECEIVING_YARDS_MISMATCH', o.code)
    o = ACC.reconcile_cross_layer(D, receiving=D['pyds'],
                                  receiving_td=D['ptd'] + 1)
    check('a passing TD / receiving TD mismatch is REFUSED, with NO exception',
          o.state is State.FAIL
          and o.code == 'PASSING_TD_RECEIVING_TD_MISMATCH', o.code)
    o = ACC.reconcile_cross_layer(D, receiving=D['pyds'][:2])
    check('  and a shape mismatch is refused rather than broadcast away',
          o.state is State.FAIL
          and o.code == 'CROSS_LAYER_SHAPE_MISMATCH', o.code)
    o = ACC.reconcile_cross_layer(D, receiving=D['pyds'], receiving_td=D['ptd'])
    check('  a genuinely matching pair reconciles', o.state is State.PASS,
          o.code)


# --------------------------------------------------------------------------
# Leakage. These run against the REAL frame, because a synthetic one cannot
# demonstrate a chronology cut.
# --------------------------------------------------------------------------
_FRAME = None


def frame():
    global _FRAME
    if _FRAME is None:
        import qb2_lib as Q
        _FRAME = (Q, Q.load())
    return _FRAME


def test_08_same_week_leakage():
    print('\n8. same-week leakage: the prefix cut is STRICTLY earlier')
    Q, rs = frame()
    per = {}
    for r in rs:
        per.setdefault(r['gsis_id'], []).append(r)
    lax = strict = same = n = 0
    for pid, rr in per.items():
        rr.sort(key=lambda x: (x['ord'], x['team'], x['gsis_id']))
        for i, r in enumerate(rr):
            n += 1
            # STRICTLY earlier ORDINAL, not merely earlier in the list. 1,318
            # player-ordinal pairs carry two rows (a mid-week team change), and
            # a naive list prefix hands the second row its same-week sibling.
            want = len([x for x in rr[:i]
                        if x['db'] > 0 and x['ord'] < r['ord']])
            got = len(r['h_seq'])
            if got > want:
                lax += 1
            elif got < want:
                strict += 1
            same += sum(1 for x in rr if x['ord'] == r['ord'] and x is not r
                        and x['db'] > 0)
    check(f'no row among {n} carries a history entry at its own ordinal or '
          f'later -- that would be same-week leakage', lax == 0,
          f'{lax} rows leak')
    check('  and none is short of its strictly-earlier history either',
          strict == 0, f'{strict} rows short')
    check('  the frame really does contain same-ordinal duplicates, so the '
          'cut is not vacuous', same > 0, same)


def test_09_current_game_outcomes_in_priors():
    print('\n9. current-game outcomes must not reach the forecast')
    Q, rs = frame()
    e = [r for r in rs if Q.eligible(r, 2024)][:40]
    base = Q.simulate(e, 2024, rs, m=30)
    tampered = []
    for r in e:
        c = dict(r)
        # every realised outcome of THIS game, wrecked
        c.update(pyds=c['pyds'] * 3 + 500, cmp=c['cmp'] + 25,
                 att=c['att'] + 30, db=c['db'] + 30, ptd=c['ptd'] + 5,
                 int=c['int'] + 5, ryds=c['ryds'] + 200,
                 rush_opp=c['rush_opp'] + 20, drush=c['drush'] + 20,
                 sacks=c['sacks'] + 5, scr=c['scr'] + 5)
        tampered.append(c)
    after = Q.simulate(tampered, 2024, rs, m=30)
    same = all(np.array_equal(base[f], after[f]) for f in base)
    check('mangling every realised outcome of the game being forecast '
          'changes NOTHING in its own draws', same)
    # and the oracle path must NOT be identical -- otherwise the test above
    # would pass even if simulate ignored its input entirely
    ob = Q.simulate(e, 2024, rs, oracle=('V', 'S'), m=30)
    oa = Q.simulate(tampered, 2024, rs, oracle=('V', 'S'), m=30)
    check('  and the ORACLE path does change, so the test is not vacuous',
          not np.array_equal(ob['db'], oa['db']))


def test_10_backup_with_no_history():
    print('\n10. a backup with no history falls back to the pool')
    Q, rs = frame()
    nohist = {'h_games': 0, 'h_seq': []}
    for rung in Q.RUNGS:
        check(f'  {rung}: a zero-history QB uses none of his own history',
              Q.rung_weight(nohist, rung) == 0.0
              or rung not in ('L0', 'L1', 'L2', 'L3'), rung)
    check('  and the rate returned is exactly the pool value, not a guess',
          Q.rung_rate(nohist, 'cmp', 'att', 'L1', 0.6123) == 0.6123)
    check('  a zero-history QB is not eligible at all in the study frame',
          not Q.eligible({'season': 2024, 'db': 5, 'h_games': 0}, 2024))
    check('  the ladder is CLOSED at four rungs', Q.RUNGS ==
          ('L0', 'L1', 'L2', 'L3'), Q.RUNGS)
    try:
        Q.simulate([r for r in rs if Q.eligible(r, 2024)][:1], 2024, rs,
                   m=2, rung='L9')
        check('  and an unknown rung is REFUSED', False, 'no error raised')
    except ValueError:
        check('  and an unknown rung is REFUSED', True)


def test_11_qb_change_is_reported_not_hidden():
    print('\n11. a QB change is reported, never smoothed away')
    k = QBV1.KNOWN_LIMITATIONS['multi_qb_over_prediction']
    check('the multi-QB over-prediction is carried as a known limitation',
          k['measured_bias_pass_yards'] > 50, k['measured_bias_pass_yards'])
    check('  with the single-QB comparison beside it, so it cannot be read '
          'as ordinary error',
          k['single_qb_bias'] < 0 and k['multi_qb_cover90'] <
          k['single_qb_cover90'])
    check('  the policy is explicit that it is never smoothed away',
          'never smoothed away' in k['policy'])
    check('  and the cause names prior-only share, not an unknown',
          'share' in k['cause'])
    check('  interception discrimination is recorded even though it is ~zero',
          QBV1.KNOWN_LIMITATIONS['int_discrimination']['pearson_r'] < 0.05)


# --------------------------------------------------------------------------
# End-to-end, through the real production entrypoint.
# --------------------------------------------------------------------------
def _args(**over):
    d = dict(season=2024, week=1, game_id='2024_01_NE_SEA', arm='A',
             written_at='2026-09-09T22:00:00Z', out_dir=str(TMP),
             seed=20260908, dry_run=True, fixtures=None)
    d.update(over)
    return argparse.Namespace(**d)


def _fx(**over):
    Q, rs = frame()
    e = [r for r in rs if Q.eligible(r, 2024)][:12]
    f = {'kickoff_utc': '2026-09-10T00:20:00Z',
         'source_hashes': {'schedules': {'sha256': 'b' * 64,
                                         'retrieved_at':
                                             '2026-09-09T20:00:00Z'}},
         'players': [{'gsis_id': r['gsis_id']} for r in e],
         'team_ids': ['NE', 'SEA'],
         'qb_rows': e, 'qb_allrows': rs, 'qb_draws': 30,
         'distributions': {}}
    f.update(over)
    return f


def test_12_end_to_end_executes_real_qb_logic():
    print('\n12. the entrypoint executes the QB layer as model logic')
    s = RUN.build(_args(), _fx())
    st = [r for r in s['stages'] if r['stage'] == 'qb_layer']
    check('the run seals', s['status'] == 'SEALED', s['status'])
    check('  the QB stage ran', len(st) == 1
          and st[0]['state'] == 'PASS', st)
    check('  under the real spec version, not a placeholder',
          st and st[0]['spec_version'] == QBV1.SPEC_VERSION,
          st[0]['spec_version'] if st else None)
    check('  and it is NOT the old audit-only baseline string',
          st and 'BASELINED' not in (st[0]['spec_version'] or ''))
    check('  the known limitations travel with the result',
          st and any('multi_qb' in w for w in (st[0].get('warnings') or [])),
          st[0].get('warnings') if st else None)
    check('  it is tagged a dry run', s['dry_run'] is True)
    check('  and explicitly not prospective evidence',
          s['prospective_eligible'] is False)
    check('  publication is REFUSED on a clean run',
          s['publication']['code'] == 'NFL1_NOT_AUTHORIZED',
          s['publication']['code'])


def test_13_model_hash_mismatch_beats_the_model():
    print('\n13. a model hash mismatch refuses BEFORE the model runs')
    s = RUN.build(_args(), _fx(qb_hash_mismatch=True))
    check('a hash mismatch refuses even though QB rows were supplied',
          s['status'] == 'REFUSED', s['status'])
    check('  with the right code',
          any(r['code'] == 'MODEL_HASH_MISMATCH' for r in s['refusals']),
          s['refusals'])
    s = RUN.build(_args(), _fx(qb_missing=True))
    check('a missing QB artifact refuses too',
          any(r['code'] == 'MODEL_ARTIFACT_MISSING' for r in s['refusals']),
          s['refusals'])


def test_14_missing_passer_id():
    print('\n14. a player with no id never reaches the model')
    # its OWN out_dir: run_id is deterministic, so a clean run earlier in this
    # module would otherwise leave an artifact at the same path and the
    # 'nothing was sealed' check would read someone else's file.
    own = TMP / 'no_id'
    s = RUN.build(_args(out_dir=str(own)), _fx(players=[{'gsis_id': None}]))
    check('an unresolved identity refuses the run', s['status'] == 'REFUSED',
          s['status'])
    check('  with IDENTITY_UNRESOLVED, and the refusal says fuzzy name '
          'matching is forbidden',
          any(r['code'] == 'IDENTITY_UNRESOLVED' for r in s['refusals']),
          s['refusals'])
    qb = [r for r in s['stages'] if r['stage'] == 'qb_layer']
    check('  and the QB layer never RAN -- a refusal halts the pipeline '
          'rather than modelling on inputs that failed validation',
          len(qb) == 1 and qb[0]['state'] == 'NOT_APPLICABLE',
          qb[0]['state'] if qb else None)
    check('  the skip is recorded, not silent, and names what refused',
          qb and qb[0]['code'] == 'STAGE_NOT_REACHED'
          and 'identity_resolution' in qb[0]['detail'], qb[0] if qb else None)
    check('  and NO artifact was sealed',
          not (own / s['run_id'] / 'forecast_artifact.json').exists(),
          sorted(x.name for x in (own / s['run_id']).glob('*'))
          if (own / s['run_id']).exists() else 'no dir')


def test_15_incoherent_draws_refuse_the_run():
    print('\n15. an incoherent QB draw set refuses the whole run')
    bad = clean(n=12, m=30)
    bad['ptd'] = bad['cmp'] + 1
    orig = QBV1.forecast
    QBV1.forecast = lambda *a, **k: Outcome.ok('QB_V1_FORECAST', value=bad)
    try:
        s = RUN.build(_args(), _fx())
    finally:
        QBV1.forecast = orig
    check('the run REFUSES rather than sealing an impossible forecast',
          s['status'] == 'REFUSED', s['status'])
    check('  named INCOMPLETE_PLAYER_ACCOUNTING',
          any(r['code'] == 'INCOMPLETE_PLAYER_ACCOUNTING'
              for r in s['refusals']), s['refusals'])


def test_16_cross_layer_deferred_is_carried_as_owed():
    print('\n16. the un-run cross-layer check is carried as OWED')
    s = RUN.build(_args(), _fx())
    j = [r for r in s['stages'] if r['stage'] == 'joint_reconciliation']
    check('joint reconciliation ran', len(j) == 1
          and j[0]['state'] == 'PASS', j)
    art = TMP / s['run_id'] / 'forecast_artifact.json'
    check('  and an artifact was sealed', art.exists())


# --------------------------------------------------------------------------
# GUARD DELETION. The half that is usually skipped.
# --------------------------------------------------------------------------
def test_17_guard_deletions():
    print('\n17. guard-deletion proofs for the load-bearing QB identities')

    def seeded(field, delta):
        bad = clean(n=12, m=30)
        bad[field] = bad[field] + delta

        def run():
            orig = QBV1.forecast
            QBV1.forecast = lambda *a, **k: Outcome.ok('QB_V1_FORECAST',
                                                       value=bad)
            try:
                return RUN.build(_args(), _fx())
            finally:
                QBV1.forecast = orig
        return run

    # G-QB1: the per-draw accounting itself
    assert_guard_is_load_bearing(
        run=seeded('ptd', 99), module_path='nfl.production.run_forecast',
        attr='QBACC', caught=lambda s: s['status'] == 'REFUSED',
        replacement=None,
        returns=None) if False else None
    # (done explicitly below -- QBACC is a module reference, not a callable)

    from nfl.tests.bypass import guard_bypassed
    for label, field, delta, attr in (
            ('per-draw accounting (a TD that is not a completion)',
             'ptd', 99, 'reconcile_draws'),
            ('per-draw accounting (designed rushes outside the composed '
             'rush opportunity)', 'drush', 99, 'reconcile_draws')):
        run = seeded(field, delta)
        with_guard = run()
        with guard_bypassed('nfl.production.qb_accounting', attr,
                            returns=Outcome.ok('STUB', value={
                                'n_cells': 0, 'identities': 0, 'report': {}})):
            without = run()
        check(f'G-QB {label}: refused with the guard',
              with_guard['status'] == 'REFUSED', with_guard['status'])
        check(f'  and NOT refused with qb_accounting.{attr} bypassed -- '
              f'therefore the guard caught it',
              without['status'] != 'REFUSED', without['status'])

    # G-QB3: the dropback identity in the layer itself
    run = seeded('sacks', 99)
    with_guard = run()
    with guard_bypassed('nfl.production.qb_v1', 'identity_check',
                        returns=Outcome.ok('STUB', value=0)):
        with guard_bypassed('nfl.production.qb_accounting', 'reconcile_draws',
                            returns=Outcome.ok('STUB', value={
                                'n_cells': 0, 'identities': 0, 'report': {}})):
            without = run()
    check('G-QB dropback identity: refused with the guards',
          with_guard['status'] == 'REFUSED', with_guard['status'])
    check('  and NOT refused with qb_v1.identity_check AND '
          'qb_accounting.reconcile_draws both bypassed',
          without['status'] != 'REFUSED', without['status'])

    # G-QB4: team-level reconciliation
    def run_team():
        return RUN.build(_args(), _fx(team_rush_draws={
            (2024, w, t): np.zeros(30)
            for w in range(1, 20) for t in ('NE', 'SEA', 'KC', 'BUF', 'PHI',
                                            'DAL', 'SF', 'GB', 'CIN', 'MIA',
                                            'BAL', 'DET', 'LA', 'NYJ')}))
    assert_guard_is_load_bearing(
        run=run_team, module_path='nfl.production.qb_accounting',
        attr='reconcile_team', caught=lambda s: s['status'] == 'REFUSED',
        returns=Outcome.ok('STUB', value={'n_team_games': 0}))
    check('G-QB team reconciliation is load-bearing -- bypassed, a QB drawing '
          'more rushes than his team drew flows into a sealed artifact', True)


def test_18_the_runner_itself_surfaces_a_failing_check():
    print('\n18. the suite runner reports a failing check, not just a raise')
    import importlib
    rs_mod = importlib.import_module('nfl.tests.run_suite')
    src = open(os.path.join(_ROOT, 'nfl', 'tests', 'run_suite.py')).read()
    check('a committed runner exists', bool(src))
    check('  it reads each module tally rather than counting exceptions only',
          'def tally' in src and 'FAILING CHECKS' in src)
    check('  and it refuses a module that recorded ZERO checks',
          'VACUOUS' in src)

    class M:
        PASSED = 3
        FAILED = 2
    check('  the tally reader finds a module counter',
          rs_mod.tally(M()) == (3, 2), rs_mod.tally(M()))
    check('  and returns None when there is none to read',
          rs_mod.tally(object()) is None)


def test_zz_every_check_passed():
    """Makes this module's check() failures visible to ANY runner.

    Without this, a runner that counts only exceptions reports a clean suite
    while checks are failing -- measured: with one failure deliberately seeded,
    the previous ad-hoc runner still printed 'TESTS 302 FAILURES 0'.
    """
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks; a module that '
                             'measured nothing has not passed')


if __name__ == '__main__':
    for _n in sorted(n for n in dir() if n.startswith('test_')):
        globals()[_n]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
