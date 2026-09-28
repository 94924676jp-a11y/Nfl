#!/usr/bin/env python3.12
"""GAP 4 driver: build the field model for the frozen slate and write one auditable artifact.

Runs every part in order, records what each part measured INCLUDING the two failed
identifications of the shape mix, and writes nfl/dfs/salaries/FIELD_MODEL.json.

Nothing here may be read by a projection. Ownership is downstream of football, always.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import opponent, ownership as own_mod  # noqa: E402
from nfl.opt import exact  # noqa: E402

V1 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'
POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
OUT = _REPO / 'nfl/dfs/salaries/FIELD_MODEL.json'


def load_pool():
    art = json.loads(V1.read_text())
    post = json.loads(POST.read_text()) if POST.exists() else {'players': {}}
    pool, team_of, uncond = [], {}, {}
    for dk, r in art['rows'].items():
        if not r.get('salary') or r.get('dk_points_if_plays') is None:
            continue
        pool.append({'id': dk, 'position': r['position'], 'salary': r['salary'],
                     'value': float(r['dk_points_if_plays']), 'name': r['name']})
        team_of[dk] = r['team']
        # the field prices in injury news too, so ownership keys off the UNCONDITIONAL number
        uncond[dk] = float(r.get('dk_points') if r.get('dk_points') is not None
                           else r['dk_points_if_plays'])
    return pool, team_of, uncond, art


def main(n_entries: int = 20000, frontier_depth: int = own_mod.FRONTIER_DEPTH) -> int:
    t0 = time.time()
    pool, team_of, uncond, art = load_pool()
    own_pool = [dict(r, value=uncond[r['id']]) for r in pool]
    report: dict = {
        'BUILD': 'GAP4_FIELD_MODEL',
        'slate': 'DK_WEEK3_2026',
        'n_pool': len(pool),
        'CALIBRATION_STATE': own_mod.CALIBRATION_STATE,
        'DATA_REQUEST': own_mod.DATA_REQUEST,
        'READ_THIS_FIRST': (
            'This is a STRUCTURAL field model. No archived contest ownership exists in this '
            'checkout, so nothing here is a measurement of ownership. What is earned is the '
            'accounting identity, the generator reproducing its own target marginals, and the '
            'sensitivity result that says which decisions survive the uncalibrated range.'),
        'MUST_NOT': 'no projection may read any field quantity; the field is downstream',
    }

    # --- shape mix: two candidate identifications, both recorded with their defects --------
    fc = own_mod.measure_shape_mix(art['rows'])
    fc_mix = fc.value['mix'] if fc.state.value == 'PASS' else None
    shallow = own_mod.shape_mix_from_frontier(pool, 50)
    deep = own_mod.shape_mix_from_frontier(pool, frontier_depth)
    decision = own_mod.shape_mix_decision(
        shallow.value['mix'] if shallow.state.value == 'PASS' else None,
        deep.value['mix'] if deep.state.value == 'PASS' else None, fc_mix)
    report['shape_mix'] = decision.value
    report['shape_mix']['tool_lineups_raw'] = (
        {k: v for k, v in fc.value.items() if not k.startswith('_')} if fc_mix else fc.code)
    mix = (deep.value['mix'] if deep.state.value == 'PASS'
           else list(own_mod.DECLARED_SHAPE_MIX))
    report['shape_mix']['mix_used'] = list(mix)
    print(f'[{time.time()-t0:5.1f}s] shape mix used {[round(m,4) for m in mix]}')

    # --- ownership marginals ---------------------------------------------------------------
    o = own_mod.ownership(own_pool, mix=mix)
    if o.state.value != 'PASS':
        report['ownership'] = {'state': o.state.value, 'code': o.code, 'evidence': o.evidence}
        OUT.write_text(json.dumps(report, indent=2, default=str))
        print('OWNERSHIP REFUSED', o.code)
        return 1
    ownvec = o.value['ownership']
    report['ownership'] = {k: v for k, v in o.value.items() if k != 'ownership'}
    report['parameters'] = {k: {kk: vv for kk, vv in v.items() if kk != 'value'} | {
        'value': v['value']} for k, v in own_mod.PARAMETERS.items()}
    report['generator_parameters'] = opponent.GEN_PARAMETERS
    top = sorted(ownvec.items(), key=lambda kv: -kv[1])[:15]
    names = {r['id']: r['name'] for r in pool}
    report['ownership']['top_15'] = [{'name': names[i], 'share': round(v, 4)} for i, v in top]
    print(f'[{time.time()-t0:5.1f}s] ownership sums to {o.value["sum_of_shares"]}, '
          f'top {top[0][0]} {top[0][1]:.3f}')

    # --- sensitivity: the substitute for calibration ---------------------------------------
    sens = own_mod.sensitivity(own_pool, base_mix=mix)
    report['sensitivity'] = sens.value if sens.state.value == 'PASS' else {'code': sens.code}
    print(f'[{time.time()-t0:5.1f}s] sensitivity {report["sensitivity"].get("VERDICT")} '
          f'worst overlap {report["sensitivity"].get("worst_top_leverage_overlap")}')

    # --- the field itself -------------------------------------------------------------------
    g = opponent.generate(own_pool, ownvec, mix=mix, n_entries=n_entries, team_of=team_of,
                          ipf_rounds=14)
    if g.state.value != 'PASS':
        report['field'] = {'state': g.state.value, 'code': g.code, 'evidence': g.evidence}
        OUT.write_text(json.dumps(report, indent=2, default=str))
        print('FIELD REFUSED', g.code)
        return 1
    field = g.value.pop('_field')
    field_own = g.value.pop('field_ownership')
    report['field'] = g.value
    report['field']['field_ownership_top_15'] = [
        {'name': names[i], 'share': round(v, 4), 'marginal_form_target': round(ownvec[i], 4)}
        for i, v in sorted(field_own.items(), key=lambda kv: -kv[1])[:15]]
    print(f'[{time.time()-t0:5.1f}s] field {g.value["n_entries"]} entries, '
          f'{g.value["n_distinct_lineups"]} distinct, marginal residual '
          f'{g.value["realised_vs_target"]["max_abs_deviation"]}')

    # --- duplication of the lineups we would actually consider -----------------------------
    best = exact.solve(pool)
    dups = {}
    if best.state.value == 'PASS':
        d = opponent.duplication(field, best.value['ids'], n_entries)
        dups['exact_optimal_lineup'] = {
            'value': best.value['value'], 'optimality': best.value.get('optimality'),
            **(d.value if d.state.value == 'PASS' else {'code': d.code})}
    report['duplication'] = dups
    if dups:
        e = dups['exact_optimal_lineup']
        print(f'[{time.time()-t0:5.1f}s] optimal lineup expected identical entries '
              f'{e.get("expected_other_entries_identical")}')

    # leverage uses the OPERATIVE ownership -- the field's own marginals. Using the marginal
    # form here would systematically overrate minimum-priced players, which is exactly what
    # JOINT_FEASIBILITY_FINDING measured.
    lev = opponent.leverage(own_pool, field_own)
    report['leverage_top_25'] = [
        {'name': names.get(r['id'], r['id']), 'position': r['position'],
         'projected': r['projected'], 'ownership': r['ownership'],
         'leverage_ratio': r['leverage_ratio']}
        for r in lev.value['rows'][:25]]
    report['leverage_MEANING'] = lev.value['MEANING']
    report['leverage_STATUS'] = lev.value['STATUS']
    report['leverage_WHY_NOT_AN_ORDERING'] = lev.value['WHY_NOT_AN_ORDERING']
    report['leverage_n_ranked'] = lev.value['n_ranked']
    report['leverage_n_excluded_below_floor'] = lev.value['n_excluded_below_ownership_floor']
    report['DUPLICATION_USABLE'] = {
        'state': 'NO',
        'measured': (f"{report['field']['share_of_entries_that_are_unique']} of entries are "
                     f"unique at max multiplicity "
                     f"{report['field']['max_multiplicity']}"),
        'why': ('real large-field contests duplicate heavily, and this field barely duplicates '
                'at all. The cause is recorded in KNOWN_BIASES: entries are sampled '
                'independently, whereas a real field is many entries from few entrants who '
                'diversify within their own set. So the duplication numbers here are a floor, '
                'not an estimate, and no decision may rest on them.'),
        'what_would_fix_it': ('entrant-level generation with a within-entrant diversification '
                             'rule, calibrated against archived contest entry lists'),
    }
    sv = report.get('sensitivity', {}).get('VERDICT')
    stable = sv == 'LEVERAGE_SET_STABLE_ACROSS_UNCALIBRATED_RANGE'
    report['STAGE_READINESS'] = {
        'gap_4_field_model': 'PARTIAL',
        'what_is_built': ['ownership marginals with enforced identities',
                          'a generated field of legal lineups reproducing its marginals',
                          'duplication estimates from whole lineups',
                          'leverage against the operative field ownership',
                          'a sensitivity result standing in for absent calibration'],
        'what_is_not': ['any calibration of the ownership LEVEL against real contest data',
                        'stacking propensity beyond the independence benchmark',
                        'within-entrant diversification, so duplication is a floor not an '
                        'estimate and is marked DUPLICATION_USABLE: NO',
                        'a usable leverage ORDERING -- the value-over-ownership ratio is a '
                        'diagnostic only, for the reason in leverage_WHY_NOT_AN_ORDERING'],
        'contest_aware_portfolio_decisions': (
            'UNBLOCKED_FOR_ORDERING_ONLY' if stable else 'BLOCKED_PENDING_ARCHIVED_OWNERSHIP'),
        'because': report.get('sensitivity', {}).get('THEREFORE'),
        'data_request': own_mod.DATA_REQUEST,
    }
    report['elapsed_seconds'] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f'[{time.time()-t0:5.1f}s] wrote {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    raise SystemExit(main(n))
