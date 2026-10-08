"""QB-regime detection and the 'claims QB-conditioned without consuming the starter' guard (owner directive 2026-10-08).

Real TB@DAL R10 state and projection: the audit must find TB's regime change without being asked, must flag that
Daniels' inputs pool his relief game with his start on a generic cohort prior, and must agree with the readiness
layer: a club in a regime change can never be reported QB-conditioned while the conditioning edges are not consumed.
"""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import qb_regime_audit as A, showdown_run_guards as G  # noqa: E402

PASSED = FAILED = 0
D = _REPO / 'nfl/dfs/salaries/showdown_tb_dal'


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def test_real_tb_dal():
    sd = D / 'PRECOMPUTE_TBQB_DANIELS_R10'
    if not sd.is_dir():
        check(False, 'R10 scenario present')
        return
    r = A.run(sd, D / 'PRECOMPUTE_TBQB_MAYFIELD_R4')
    tb, dal = r['clubs']['TB'], r['clubs']['DAL']
    check(r['REGIME_CHANGES'] == ['TB'], f"the regime change is found without being asked: {r['REGIME_CHANGES']}")
    check(tb['starter_starts_this_season'] == [4] and tb['starter_relief_appearances'] == [3],
          'Daniels: one start (week 4), one relief appearance (week 3)')
    check(tb['dominant_qb_in_window'] == 'Baker Mayfield', 'the environment is dominated by Mayfield')
    c = tb['starter_projection_consumption']['carry_share']
    check('RELIEF_POOLED_WITH_STARTS' in c['flags'] and 'GENERIC_COHORT_PRIOR' in c['flags'],
          'his carry share pools relief with starts on a generic cohort prior (the root cause of 3.4 carries)')
    check(dal['status'] == 'NO_REGIME_CHANGE', 'Prescott: no regime change')
    eg = next(m for m in tb['teammates'] if m['player'] == 'Emeka Egbuka')
    check(eg['weight_of_starter_games_in_projection'] is not None and eg['weight_of_starter_games_in_projection'] < 0.25,
          f"the Daniels game carries {eg['weight_of_starter_games_in_projection']} of Egbuka's target projection")


def test_claim_requires_consumption():
    """PERMANENT GUARD: a club in a regime change may be reported QB-conditioned only if every QB edge is consumed."""
    sd = D / 'PRECOMPUTE_TBQB_DANIELS_R10'
    if not sd.is_dir():
        return
    r = A.run(sd)
    st = json.loads(next(sd.glob('SHOWDOWN_*_STATE.json')).read_text())
    from nfl.tools import player_prior as PP, proj_v1 as PV
    fm = G.football_model_status(st, PP.load_panel().value, PV.TEAM_VOLUME_PRIOR_GAMES)
    rel = G.release_classification([], fm, {'status': 'PASS'})
    for club in r['REGIME_CHANGES']:
        edges = r['clubs'][club]['qb_dependent_edges']
        consumed = all(v == 'IMPLEMENTED_AND_CONSUMED' for v in edges.values())
        check(consumed or rel['statuses']['QB_CONDITIONED_FORECAST_VALIDATED'] != 'NOT_REQUIRED',
              f'{club}: regime change with unconsumed QB edges is never reported as needing no QB conditioning')
        check(consumed or fm['status'] != 'COMPLETE_FOR_STARTERS',
              f'{club}: the football-model status cannot claim COMPLETE while the starter\'s evidence is not consumed')


if __name__ == '__main__':
    for t in (test_real_tb_dal, test_claim_requires_consumption):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
