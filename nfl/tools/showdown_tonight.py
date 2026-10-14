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
import os
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def roster_blocked(export, tag, roster_capture, official_inactives=None, transactions=None, elevations=None, reasons=False,
                   withheld=False, unresolved=False):
    """Names the roster-eligibility gate blocks (nfl.tools.roster_eligibility): no positive roster evidence -> blocked.
    The optimizer must never select them; the release gate (showdown_run_guards.upload_roster_eligibility) refuses an
    upload that carries one anyway. Empty capture week is an error, never 'nobody blocked'."""
    from nfl.tools import roster_eligibility as E
    season, week = int(tag.rsplit('_', 1)[-1][:4]), int(tag.rsplit('W', 1)[-1])
    rows = E.roster_rows(roster_capture, season, week)
    if not rows:
        raise RuntimeError(f'ROSTER_CAPTURE_EMPTY_WEEK {roster_capture} {season} week {week}')
    res = E.classify(E.dk_pool(export), rows, official_inactives or (), transactions or {}, elevations)
    if withheld:      # the shared upstream rule (OD-002), the same function the Classic state applies
        return {n: {'reason': v['reason'], 'eligibility_state': v['eligibility_state']}
                for (n, _c), v in E.opportunity_withheld(res).items()}
    if unresolved:    # kept in the forecast, never selectable, a release blocker while material (OD-002)
        return {n: {'reason': v['reason'], 'missing_evidence': v['missing_evidence']}
                for (n, _c), v in E.unresolved(res).items()}
    if reasons:
        return {n: v['reason'] for (n, _c), v in res.items() if not v['eligible']}
    return sorted({n for (n, _c), v in res.items() if not v['eligible']})


#: Every NFL_SHOWDOWN_* switch the code reads (ENG-017, owner OD-001 2026-10-14). Any other NFL_SHOWDOWN_* value in the
#: environment refuses the run: an environment variable may not silently determine undocumented production behaviour.
DECLARED_ENV = ('NFL_SHOWDOWN_ARM', 'NFL_SHOWDOWN_SELECTOR', 'NFL_SHOWDOWN_OVERLAP_POLICY',
                'NFL_SHOWDOWN_DESIGNATIONS_PROVENANCE', 'NFL_SHOWDOWN_INACTIVES_RESOLVED')
RELEASE_CANDIDATE = 'CERTIFIABLE_CANDIDATE'          # may proceed to the governed finalize/verify path
RELEASE_DIAGNOSTIC = 'DIAGNOSTIC_NOT_RELEASABLE'     # never produces a releasable upload


def unresolved_material(unres, draws):
    """OD-002: the unresolved players (by name) whose simulated DK points are nonzero in any world. Draws are keyed
    'name|club'. Material means any nonzero draw: no margin is declared, so none is invented."""
    return sorted({n for n in unres for k, v in draws.items() if k.split('|')[0] == n and max(v or [0]) > 0})


def undeclared_env(env=None):
    env = os.environ if env is None else env
    return sorted(k for k in env if k.startswith('NFL_SHOWDOWN_') and k not in DECLARED_ENV)


def kickoff_gate(kickoff_et_naive, *, diagnostic=False, now=None):
    """ENG-014: 'OK' before kickoff; after it 'REFUSE', or 'DIAGNOSTIC' when a non-releasable analysis was asked for."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    kick = dt.datetime.fromisoformat(kickoff_et_naive).replace(tzinfo=ZoneInfo('America/New_York'))
    now = now or dt.datetime.now(dt.timezone.utc)
    if now < kick:
        return 'OK'
    return 'DIAGNOSTIC' if diagnostic else 'REFUSE'


def withhold_uploads(sd, pre):
    """ENG-014: rename every upload-named file of a DIAGNOSTIC run so nothing releasable remains. Returns the new names."""
    out = []
    for f in sorted(pathlib.Path(sd).glob(f'{pre}_DK_UPLOAD*.csv')):
        if f.name.endswith('.DIAGNOSTIC_NOT_RELEASABLE.csv'):
            continue
        g = f.with_name(f.name[:-4] + '.DIAGNOSTIC_NOT_RELEASABLE.csv')
        f.rename(g)
        out.append(g.name)
    return out


def effective_config(export, roster_gate, release_status, reasons, state_value=None, env=None):
    """ENG-017: the configuration that actually governed this run, each switch with its source, plus input hashes."""
    import hashlib
    env = os.environ if env is None else env
    from nfl.tools import showdown_portfolio as SPF, showdown_to_portfolio as S, showdown_slate_run as SR

    def sw(name, default):
        return {'value': env.get(name) or default, 'source': 'ENV' if env.get(name) else 'CODE_DEFAULT'}

    def sha(p):
        try:
            return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
        except (OSError, TypeError):
            return None
    code = {m: sha(_REPO / f'nfl/tools/{m}.py') for m in ('showdown_portfolio', 'showdown_to_portfolio', 'showdown_slate_run',
                                                           'showdown_slate_state', 'showdown_draws', 'proj_v1')}
    return {
        'ARTIFACT': 'SHOWDOWN_EFFECTIVE_CONFIG', 'spec_version': 'showdown-effective-config-1',
        'release_status': release_status, 'release_reasons': list(reasons),
        'forecast_arm': sw('NFL_SHOWDOWN_ARM', SR.ARM_INCUMBENT),
        'selector': sw('NFL_SHOWDOWN_SELECTOR', 'GREEDY'),
        'overlap_policy': sw('NFL_SHOWDOWN_OVERLAP_POLICY', 'EQUAL_SIZE'),
        'candidate_generator': {'function': 'showdown_to_portfolio.near_optimal_candidates',
                                'near_optimal_loss_band': getattr(S, 'NEAR_OPTIMAL_LOSS_BAND', None),
                                'forced_captain': True, 'code_sha256': code['showdown_to_portfolio']},
        'exposure_and_relaxation': {'ladder': SPF.LADDER, 'fixed_policy': {
            'level': SPF.FIXED_POLICY_LEVEL, 'min_n': SPF.FIXED_POLICY_MIN_N, 'max_n': SPF.FIXED_POLICY_MAX_N}},
        'declared_env_present': {k: env[k] for k in DECLARED_ENV if k in env},
        'inputs': {'export': {'path': str(export), 'sha256': sha(export)},
                   'roster_capture': ({'path': str(roster_gate.get('roster_capture')),
                                       'sha256': sha(roster_gate.get('roster_capture'))} if roster_gate else None)},
        'point_in_time': (state_value or {}).get('point_in_time'),
        'kickoff_et_naive': (state_value or {}).get('kickoff_et_naive'),
        'code_sha256': code,
    }


def run(export, tag, scenario, designations=None, outs=(), official_inactives=None, n_sims=2000,
        confirmed_starters=None, starter_tier=None, depth_chart_csv=None, roster_gate=None, diagnostic=False):
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
    from sportsplatform.governance.outcome import Outcome as _OE, Cause as _CE
    und = undeclared_env()
    if und:
        return _OE.blocked('UNDECLARED_RUN_CONFIG', f'NFL_SHOWDOWN_* values this code does not declare: {und}. An '
                           f'environment variable may not silently change production behaviour (ENG-017).', cause=_CE.DATA,
                           undeclared=und)
    # ENG-014 (owner OD-001): without dated roster evidence a run is DIAGNOSTIC and can never produce a releasable upload
    release_reasons = ([] if roster_gate else ['NO_ROSTER_CAPTURE']) + (['DIAGNOSTIC_REQUESTED'] if diagnostic else [])
    release_status = RELEASE_DIAGNOSTIC if release_reasons else RELEASE_CANDIDATE
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
        chart = SSS.chart_from_capture(depth_chart_csv, [SSS.S.corpus_team(t) for t in tag.split('_2026')[0].split('_')],
                                       cid)   # the state's clubs are corpus codes (LAR -> LA)
    # the roster status is applied UPSTREAM (state -> projection -> worlds), not only at selection; the inactive list
    # keeps its own path, so only roster reasons are passed here
    rb = rbs = unres = None
    if roster_gate:
        _rg = {k: v for k, v in roster_gate.items() if k != 'official_inactives'}
        wh = roster_blocked(export, tag, withheld=True, **_rg)
        unres = roster_blocked(export, tag, unresolved=True, **_rg)
        rb = {n: v['reason'] for n, v in wh.items()}
        rbs = {**{n: v['eligibility_state'] for n, v in wh.items()},
               **{n: 'ELIGIBILITY_UNRESOLVED' for n in unres}}
    st = SSS.build(export, designations=desig, official_inactives=official_inactives, roster_blocked=rb,
                   roster_eligibility_state=rbs, confirmed_starters=confirmed_starters, depth_chart=chart)
    print('state', st.state.value, st.code, st.detail, flush=True)
    if st.state.value != 'PASS':
        return st
    # P0-A: a state stamped NOT_POINT_IN_TIME (a pit_exempt replay) can never feed a production run
    if (st.value.get('point_in_time') or {}).get('mode') == 'NOT_POINT_IN_TIME':
        return _OE.fail('NOT_POINT_IN_TIME_STATE', 'the state was built pit_exempt; it is barred from any run that '
                        'could release', cause=_CE.DATA)
    # ENG-014: a run after kickoff is never a prelock forecast. Only an explicitly requested diagnostic may proceed.
    kg = kickoff_gate(st.value['kickoff_et_naive'], diagnostic=diagnostic)
    if kg == 'REFUSE':
        return _OE.blocked('RUN_AFTER_KICKOFF', f"kickoff was {st.value['kickoff_et_naive']} ET; a run after kickoff is not a "
                           f'prelock forecast. Re-run with --diagnostic for a non-releasable analysis.', cause=_CE.DATA)
    if kg == 'DIAGNOSTIC':
        release_reasons.append('AFTER_KICKOFF')
        release_status = RELEASE_DIAGNOSTIC
    (sd / 'EFFECTIVE_CONFIG.json').write_text(json.dumps(
        effective_config(export, roster_gate, release_status, release_reasons, st.value), indent=1, default=str))
    # STARTER-STATE INTEGRITY, BEFORE ANY PROJECTION OR SIMULATION (independent P0 fixtures QB-*): bind this
    # scenario's identity and starter evidence onto the state, then require the state to say, positively and
    # completely, what the scenario says. A refusal here means role_state / proj_v1 / the simulator never ran.
    from nfl.tools import showdown_run_guards as G, availability as _AV
    from sportsplatform.governance.outcome import Outcome as _O0
    import os as _os
    sid = G.scenario_identity(tag, scenario, desig, confirmed_starters or {})
    told = _os.environ.get('SHOWDOWN_SCENARIO_IDENTITY')
    guard = {'ARTIFACT': 'SCENARIO_GUARD', 'stage': 'BEFORE_PROJECTION', 'scenario': scenario, 'scenario_identity': sid}
    if told and told != sid:
        bad = [f'RUN_CONTEXT_SCENARIO:{told}!={sid}']
    elif not depth_chart_csv:
        bad = ['IDENTITY_SOURCE_ABSENT (no captured depth chart to establish canonical ids)']
    else:
        exp = G.expected_state(tag, scenario, desig, confirmed_starters or {},
                               G.identity_from_depth_chart(depth_chart_csv, set(confirmed_starters or {}) | set(desig)))
        state = json.loads(P['state'].read_text())
        G.bind_scenario(state, sid, G.starters_digest(confirmed_starters or {}), SSS.STARTER_TIER)
        P['state'].write_text(json.dumps(state, indent=1, default=str))
        bad = G.verify_starter_state(state, exp, tuple(_AV.ABSENT_STATUSES) + ('OUT',),
                                     G.starters_digest(confirmed_starters or {}))
        guard['expected'] = exp
    guard.update({'reasons': bad, 'state': 'PASS' if not bad else 'REFUSED',
                  'projection_ran': False, 'simulation_ran': False})
    (sd / 'SCENARIO_GUARD.json').write_text(json.dumps(guard, indent=1, default=str))
    if bad:
        print('scenario_guard REFUSED', bad, flush=True)
        return _O0.fail('SCENARIO_STATE_MISMATCH', f'{len(bad)} starter-state mismatch(es) before projection: {bad[:4]}',
                        reasons=bad)
    dr = SR.run(tag, n_sims=n_sims, work=sd)
    print('draws', dr.state.value, dr.code, dr.detail, flush=True)
    if dr.state.value != 'PASS':
        return dr
    from sportsplatform.governance.outcome import Outcome as _O
    # OD-002 EVIDENCE-COMPLETENESS GATE: an unresolved player is kept in the forecast; a certified release refuses while
    # any of them carries material opportunity -- any nonzero simulated DK points (no margin is declared, so none is
    # invented). The research forecast stands; only release changes.
    unres_material = []
    if unres:
        unres_material = unresolved_material(unres, json.loads(P['draws'].read_text()).get('draws') or {})
        (sd / 'ELIGIBILITY_COVERAGE.json').write_text(json.dumps(
            {'unresolved': unres, 'material_in_draws': unres_material,
             'RULE': 'OD-002: certified release refuses while an unresolved player has nonzero simulated DK points'},
            indent=1))
    if unres_material and release_status == RELEASE_CANDIDATE:
        release_reasons.append(f'ELIGIBILITY_UNRESOLVED_MATERIAL {len(unres_material)}: {unres_material[:6]}')
        release_status = RELEASE_DIAGNOSTIC
        (sd / 'EFFECTIVE_CONFIG.json').write_text(json.dumps(     # the record states the FINAL release status
            effective_config(export, roster_gate, release_status, release_reasons, st.value), indent=1, default=str))
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
    blocked = roster_blocked(export, tag, **roster_gate) if roster_gate else None
    if blocked:
        absent = sorted(set(absent) | set(blocked))
    (sd / 'SCENARIO.json').write_text(json.dumps({
        'roster_blocked': blocked, 'roster_gate': {k: str(v)[:200] for k, v in (roster_gate or {}).items()} or None,
        'scenario': scenario, 'export': str(export), 'designations': desig,
        'forced_out': list(outs), 'official_inactives': official_inactives,
        'confirmed_starters': confirmed_starters, 'starter_tier': starter_tier,
        'depth_chart_csv': depth_chart_csv,
        'absent_in_state': absent, 'n_sims': n_sims}, indent=1))
    pf = SPF.run(export, sd / P['draws'].name, sd, f'SHOWDOWN_{tag.split("_2026")[0]}', inactives=absent,
                 proj_path=sd / P['proj'].name, state_path=sd / P['state'].name)
    print('portfolio', pf.state.value, pf.code, pf.detail, flush=True)
    pre = f'SHOWDOWN_{tag.split("_2026")[0]}'
    if release_status != RELEASE_CANDIDATE:
        # ENG-014: a DIAGNOSTIC run keeps no file under an upload name, and writes no receipt (finalize needs one)
        withhold_uploads(sd, pre)
    role_diagnostic(P['dir'] / f'{pre}_ROLE_REVIEW.csv', sd / P['proj'].name, sd / f'{pre}_ROLE_DIAGNOSTIC.csv')
    audit = (pf.value if pf.state.value == 'PASS' else (pf.evidence or {}).get('audit'))
    if audit:
        final_board(audit, json.loads((sd / 'SCENARIO.json').read_text()), sd / f'{pre}_FINAL_BOARD', pf)
    if pf.state.value == 'PASS' and release_status == RELEASE_CANDIDATE:
        # THE LAST ACT: a receipt binding this run, commit, scenario, freeze seal, environment and the sha256 of every
        # football-state and publication artifact. Absent run context (a direct call) it is written with run_id None
        # and can never finalize.
        G.write_receipt(sd, run_id=_os.environ.get('SHOWDOWN_RUN_ID'), commit=_os.environ.get('SHOWDOWN_RUN_COMMIT'),
                        scenario=scenario, scenario_identity=sid, freeze_seal=_os.environ.get('SHOWDOWN_FREEZE_SEAL'),
                        env=_os.environ, tag=tag,
                        publication=[sd / f'{pre}_DK_UPLOAD.csv', sd / f'{pre}_FINAL_LINEUPS.csv',
                                     sd / f'{pre}_PROJECTIONS.csv', sd / f'{pre}_FINAL_BOARD.json'])
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
    ap.add_argument('--roster-capture', help='weekly roster capture (nflverse weekly_rosters); enables the eligibility gate')
    ap.add_argument('--transactions', help='JSON {name: evidence} of releases after the capture')
    ap.add_argument('--elevations', help='JSON [name] of game-day practice-squad elevations')
    ap.add_argument('--diagnostic', action='store_true', help='non-releasable analysis run (ENG-014)')
    a = ap.parse_args()
    # Point-in-time contract (nfl/warehouse/point_in_time.py). NFL_PIT_MANIFEST names a sealed manifest: the run then
    # reads only the captures it admits, and opening any other guarded file is refused. Unset (live): no effect.
    from nfl.warehouse import point_in_time as PIT
    pit = PIT.active()
    if pit is not None:
        print(f"POINT_IN_TIME {pit.man['label']} cutoff {pit.man['cutoff_utc']} seal {pit.man['seal'][:16]}")
    if a.portfolio_only:
        return 0 if portfolio_only(a.export, a.tag, a.scenario).state.value == 'PASS' else 1
    d = json.loads(pathlib.Path(a.designations).read_text()) if a.designations else None
    oi = json.loads(pathlib.Path(a.official_inactives).read_text()) if a.official_inactives else None
    cs = json.loads(pathlib.Path(a.confirmed_starters).read_text()) if a.confirmed_starters else None
    rg = None
    if a.roster_capture:
        rg = {'roster_capture': a.roster_capture, 'official_inactives': oi,
              'transactions': json.loads(pathlib.Path(a.transactions).read_text()) if a.transactions else None,
              'elevations': json.loads(pathlib.Path(a.elevations).read_text()) if a.elevations else None}
    o = run(a.export, a.tag, a.scenario, d, a.out, oi, a.n_sims, cs, a.starter_tier, a.depth_chart, roster_gate=rg,
            diagnostic=a.diagnostic)
    if pit is not None:
        sd = _scenario_root(a.tag) / a.scenario
        if sd.is_dir():
            (sd / 'PIT_READS.json').write_text(json.dumps(PIT.record(), indent=1, sort_keys=True) + '\n')
    return 0 if o.state.value == 'PASS' else 1


def _scenario_root(tag):
    from nfl.tools import showdown_slate_run as SR
    return SR.paths(tag)['dir']


if __name__ == '__main__':
    raise SystemExit(main())
