#!/usr/bin/env python3.12
"""Tonight's showdown, one command per football state: slate state -> projection -> worlds -> portfolio.

    python3.12 nfl/tools/showdown_tonight.py EXPORT --tag ATL_NO_2026W4 --scenario BASE \
        --designations nfl/dfs/salaries/showdown_atl_no/DESIGNATIONS_ATL_NO_2026W4.json \
        [--out NAME ...] [--official-inactives JSON] [--n-sims 2000]

A SCENARIO IS A FOOTBALL STATE, NOTHING ELSE. `--out NAME` marks a player OUT on top of the team's own
designations (an IF-INACTIVE precompute); `--official-inactives` applies a captured list. Each scenario
writes its own directory, so precomputed states never overwrite one another, and when the inactives
arrive the only change is the football state: the same code reruns on it.

IF-LIMITED is NOT a scenario here: there is no measured snap- or route-reduction for a limited player,
and inventing one would be a silent constant. A limited player is either active (full role) or out.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def run(export, tag, scenario, designations=None, outs=(), official_inactives=None, n_sims=2000,
        confirmed_starters=None, starter_tier=None, depth_chart_csv=None):
    from nfl.tools import showdown_slate_state as SSS, showdown_slate_run as SR, showdown_portfolio as SPF
    P = SR.paths(tag)
    P['dir'].mkdir(parents=True, exist_ok=True)
    desig = dict(designations or {})
    for n in outs:
        desig[n] = 'OUT'
    from nfl.tools.showdown_portfolio import dk_input_gate
    gate = dk_input_gate(export)
    print('dk_input_gate', gate.state.value, gate.code, json.dumps(gate.value if gate.value else gate.evidence,
                                                                  default=str)[:1500], flush=True)
    if gate.state.value != 'PASS':
        return gate
    sd = P['dir'] / scenario
    sd.mkdir(exist_ok=True)
    P = SR.paths(tag, work=sd)          # every intermediate in the scenario's own directory
    SSS.OUT = P['state']
    if starter_tier:
        # the label says WHERE the starter evidence came from; downstream reads only the boolean
        SSS.STARTER_TIER = starter_tier
    chart = None
    if depth_chart_csv:
        import hashlib as _h
        cid = 'nflverse_depth_charts_' + _h.sha256(pathlib.Path(depth_chart_csv).read_bytes()).hexdigest()[:16]
        chart = SSS.chart_from_capture(depth_chart_csv, tag.split('_2026')[0].split('_'), cid)
    st = SSS.build(export, designations=desig, official_inactives=official_inactives,
                   confirmed_starters=confirmed_starters, depth_chart=chart)
    print('state', st.state.value, st.code, st.detail, flush=True)
    if st.state.value != 'PASS':
        return st
    dr = SR.run(tag, n_sims=n_sims, work=sd)
    print('draws', dr.state.value, dr.code, dr.detail, flush=True)
    if dr.state.value != 'PASS':
        return dr
    from sportsplatform.governance.outcome import Outcome as _O
    if (dr.evidence or {}).get('sanity') != 'PASS':
        # a football contradiction (e.g. a starter carrying a backup's appearance discount) is never
        # optimised over: no portfolio is built on a failed sanity gate
        return _O.fail('SHOWDOWN_FOOTBALL_SANITY_FAILED', dr.detail)
    for k in ('state', 'proj', 'draws', 'worlds'):
        if P[k].parent != sd:
            raise RuntimeError(f'SCENARIO_ISOLATION {k} written outside the scenario: {P[k]}')
    state = json.loads(P['state'].read_text())
    from nfl.tools import availability as AV
    absent = sorted(v['name'] for v in state['players'].values()
                    if v['current_availability']['status'] in AV.ABSENT_STATUSES)
    (sd / 'SCENARIO.json').write_text(json.dumps({
        'scenario': scenario, 'export': str(export), 'designations': desig,
        'forced_out': list(outs), 'official_inactives': official_inactives,
        'confirmed_starters': confirmed_starters, 'starter_tier': starter_tier,
        'depth_chart_csv': depth_chart_csv,
        'absent_in_state': absent, 'n_sims': n_sims}, indent=1))
    pf = SPF.run(export, sd / P['draws'].name, sd, f'SHOWDOWN_{tag.split("_2026")[0]}', inactives=absent,
                 proj_path=sd / P['proj'].name, state_path=sd / P['state'].name)
    print('portfolio', pf.state.value, pf.code, pf.detail, flush=True)
    pre = f'SHOWDOWN_{tag.split("_2026")[0]}'
    role_diagnostic(P['dir'] / f'{pre}_ROLE_REVIEW.csv', sd / P['proj'].name, sd / f'{pre}_ROLE_DIAGNOSTIC.csv')
    audit = (pf.value if pf.state.value == 'PASS' else (pf.evidence or {}).get('audit'))
    if audit:
        final_board(audit, json.loads((sd / 'SCENARIO.json').read_text()), sd / f'{pre}_FINAL_BOARD', pf)
    return pf


def portfolio_only(export, tag, scenario):
    """Rebuild boards and portfolios for an existing scenario directory from its OWN frozen state,
    projection and worlds. No football is recomputed; the scenario's SCENARIO.json is reused."""
    from nfl.tools import showdown_slate_run as SR, showdown_portfolio as SPF
    P = SR.paths(tag)
    sd = P['dir'] / scenario
    scen = json.loads((sd / 'SCENARIO.json').read_text())
    pf = SPF.run(export, sd / P['draws'].name, sd, f'SHOWDOWN_{tag.split("_2026")[0]}',
                 inactives=scen['absent_in_state'], proj_path=sd / P['proj'].name, state_path=sd / P['state'].name)
    print('portfolio', pf.state.value, pf.code, pf.detail, flush=True)
    audit = (pf.value if pf.state.value == 'PASS' else (pf.evidence or {}).get('audit'))
    if audit:
        final_board(audit, scen, sd / f'SHOWDOWN_{tag.split("_2026")[0]}_FINAL_BOARD', pf)
    return pf


def sunday_frozen_intact():
    m = json.loads((_REPO / 'nfl/dfs/salaries/postgame/FROZEN_2026W4_EARLY.json').read_text())
    import hashlib
    bad = [f for f, h in m['sha256'].items()
           if not (_REPO / f).exists() or hashlib.sha256((_REPO / f).read_bytes()).hexdigest() != h]
    return {'files': len(m['sha256']), 'changed_or_missing': bad, 'graded_at_commit': m['graded_at_commit']}


def final_board(a, scen, out, pf):
    import hashlib
    g = a['dk_input_gate']
    rc = a['roster_completeness']
    sc = rc['state_counts']
    up = pathlib.Path(a['files'].get('DK_UPLOAD', '')) if a['files'].get('DK_UPLOAD') else None
    ver = a['upload_verification']
    k = a['kickers']
    dst = a['dst_coherence']
    fant = next((v for n, v in (scen.get('designations') or {}).items() if n == 'Noah Fant'), 'NOT_DESIGNATED')
    b = {
        'SLATE': f"{a['away']} @ {a['home']} DraftKings Showdown, {g['game']}",
        'RESULT': pf.code,
        'SCENARIO': scen['scenario'],
        'CONTESTS': g['contests'],
        'ENTRY_COUNTS': {c: v['entries'] for c, v in g['contests'].items()},
        'DK_PLAYER_ROWS': g['dk_player_rows'], 'DK_FOOTBALL_PLAYERS': g['football_players'],
        'PROJECTED': sc.get('PROJECTED', 0), 'PROJECTED_WITH_UNCERTAINTY': sc.get('PROJECTED_WITH_UNCERTAINTY', 0),
        'ZERO_OPPORTUNITY': sc.get('ZERO_OPPORTUNITY', 0), 'INACTIVE': sc.get('INACTIVE', 0),
        'BLOCKED': sc.get('BLOCKED', 0), 'BY_POSITION': rc['by_position'], 'UNCLASSIFIED': rc['unclassified'],
        'KICKER_STATUS': {n: {'distribution': v['SCORING_A_no_miss_deduction'], 'scoring_B': v['SCORING_B_minus_1_per_miss'],
                              'fg_att': v['fg_attempts_mean'], 'xp_att': v['xp_attempts_mean'],
                              'cpt_eligible': v['cpt_eligible'], 'validated': False} for n, v in k.items()},
        'KICKER_RULE_B': {x: a['kicker_rule_B'].get(x) for x in ('state', 'MATERIAL', 'MATERIAL_RULE',
                                                                  'top100_candidates_shared_A_B', 'contests')},
        'DST_STATUS': {'state': dst.get('state'), 'by_dst': dst.get('by_dst'), 'warnings': dst.get('warnings'),
                       'LIMITATION': dst.get('LIMITATION'),
                       'cpt_eligible': {n: v['cpt_candidates'] > 0 for n, v in a['kickers_and_dst'].items()
                                        if v['pos'] == 'DST'},
                       'NOT_CALIBRATED': 'DST captain rates are model outputs, not calibrated probabilities'},
        'FANT_STATUS': fant,
        'OFFICIAL_INACTIVES_STATUS': ('APPLIED: ' + str(len(scen['official_inactives'])) + ' names'
                                      if scen.get('official_inactives') else 'NOT YET PUBLISHED / NOT APPLIED'),
        'ABSENT_IN_STATE': scen.get('absent_in_state'),
        'SIMULATION_WORLDS': a['n_worlds'], 'CANDIDATES': a['candidates']['n'],
        'CANDIDATE_COVERAGE': {x: a['candidates'][x] for x in ('by_captain_pos', 'by_split_away_home',
                                                                'split_orientation', 'by_salary_band')},
        'FINAL_LINEUPS_PER_CONTEST': {c: v['n_built'] for c, v in a['portfolios'].items()},
        'RELAXATION_LEVEL_USED': {c: v['relaxation_level'] for c, v in a['portfolios'].items()},
        'VERIFIER_VIOLATIONS': (len(ver.get('violations', [])) if isinstance(ver, dict) and 'violations' in ver
                                else ver),
        'DK_UPLOAD': (str(up.relative_to(_REPO)) if up and up.exists() else None),
        'DK_UPLOAD_SHA256': (hashlib.sha256(up.read_bytes()).hexdigest() if up and up.exists() else None),
        'SUNDAY_FROZEN_RECORD': sunday_frozen_intact(),
        'NOT_SUBMITTED': 'nothing here enters a contest; PROJECTION_SYSTEM_STATE NOT_VALIDATED; no wager is recommended',
    }
    pathlib.Path(str(out) + '.json').write_text(json.dumps(b, indent=1, default=str))
    L = [f"# {b['SLATE']} -- final board ({b['SCENARIO']})", '', f"**{b['RESULT']}**", '']
    for key in ('CONTESTS', 'ENTRY_COUNTS', 'DK_PLAYER_ROWS', 'DK_FOOTBALL_PLAYERS', 'PROJECTED',
                'PROJECTED_WITH_UNCERTAINTY', 'ZERO_OPPORTUNITY', 'INACTIVE', 'BLOCKED', 'BY_POSITION',
                'KICKER_STATUS', 'KICKER_RULE_B', 'DST_STATUS', 'FANT_STATUS', 'OFFICIAL_INACTIVES_STATUS',
                'SIMULATION_WORLDS', 'CANDIDATES', 'CANDIDATE_COVERAGE', 'FINAL_LINEUPS_PER_CONTEST',
                'VERIFIER_VIOLATIONS', 'RELAXATION_LEVEL_USED', 'DK_UPLOAD', 'DK_UPLOAD_SHA256', 'SUNDAY_FROZEN_RECORD'):
        L.append(f"- **{key}**: `{json.dumps(b[key], default=str)}`")
    L += ['', b['NOT_SUBMITTED']]
    pathlib.Path(str(out) + '.md').write_text('\n'.join(L) + '\n')


def role_diagnostic(review_csv, proj_path, out_csv):
    """Sunday's lesson as a DIAGNOSTIC only: depth pieces whose measured usage exceeds what we project.

    Week 4 confirmed WR3+/TE2+/RB2 under-allocation (nfl/dfs/salaries/postgame/WEEK4_POSTGAME_REPORT.md
    section 2). Nothing here changes a projection; it lists, per player, measured per-game targets and
    carries (weeks 1-3) beside ours, and flags a depth piece where measured exceeds projected.
    """
    import csv
    if not pathlib.Path(review_csv).exists():
        return
    proj = json.loads(pathlib.Path(proj_path).read_text())
    by_g = {r.get('gsis_id'): r for r in proj['rows'].values() if r.get('gsis_id')}
    out = []
    for r in csv.DictReader(open(review_csv)):
        g = int(r['games'] or 0) or 1
        pr = by_g.get(r['gsis_id']) or {}
        mt, mc = int(r['targets']) / g, int(r['carries']) / g
        pt, pc = pr.get('targets'), pr.get('carries')
        rk = int(r['depth_rank']) if str(r['depth_rank']).isdigit() else None
        depth_piece = (rk is not None and ((r['position'] == 'WR' and rk >= 3) or (r['position'] == 'TE' and rk >= 2)
                                           or (r['position'] == 'RB' and rk >= 2)))
        flag = depth_piece and ((isinstance(pt, (int, float)) and mt > pt) or (isinstance(pc, (int, float)) and mc > pc))
        out.append([r['club'], r['player'], r['position'], r['depth_pos'], r['depth_rank'], r['roster_status'],
                    r['injury_report_status'], round(mt, 2), '' if pt is None else round(pt, 2), round(mc, 2),
                    '' if pc is None else round(pc, 2), r['off_snap_pct_by_week'], r['rz_targets'], r['rz_carries'],
                    'IN_PROJECTION' if pr else 'NOT_IN_DK_PROJECTION', 'MEASURED_ABOVE_PROJECTED' if flag else ''])
    with open(out_csv, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['club', 'player', 'pos', 'depth_pos', 'depth_rank', 'roster_status', 'injury_status',
                    'measured_tgt_pg', 'proj_tgt', 'measured_car_pg', 'proj_car', 'snaps_by_week', 'rz_tgt_wk1_3',
                    'rz_car_wk1_3', 'projection', 'diagnostic_flag'])
        w.writerows(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--scenario', required=True)
    ap.add_argument('--designations')
    ap.add_argument('--out', action='append', default=[])
    ap.add_argument('--official-inactives')
    ap.add_argument('--n-sims', type=int, default=2000)
    ap.add_argument('--confirmed-starters', help='JSON {name: CLUB}')
    ap.add_argument('--starter-tier', help='source label for the starter evidence')
    ap.add_argument('--depth-chart', help='captured nflverse depth_charts CSV for the two clubs')
    ap.add_argument('--portfolio-only', action='store_true', help='rebuild portfolios on the scenario\'s frozen worlds')
    a = ap.parse_args()
    if a.portfolio_only:
        return 0 if portfolio_only(a.export, a.tag, a.scenario).state.value == 'PASS' else 1
    d = json.loads(pathlib.Path(a.designations).read_text()) if a.designations else None
    oi = json.loads(pathlib.Path(a.official_inactives).read_text()) if a.official_inactives else None
    cs = json.loads(pathlib.Path(a.confirmed_starters).read_text()) if a.confirmed_starters else None
    o = run(a.export, a.tag, a.scenario, d, a.out, oi, a.n_sims, cs, a.starter_tier, a.depth_chart)
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
