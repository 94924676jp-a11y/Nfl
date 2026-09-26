"""IND@KC Showdown decision package, built from the frozen draws.

CPT IS A SCORING RULE, NOT A SECOND FORECAST. DraftKings pays the captain
1.5x. That multiplier is applied PER DRAW to the same simulated world, so the
captain distribution is the flex distribution rescaled and the two can never
disagree about what happened in a given world.

CORRELATIONS ARE COUNTED, NOT ASSUMED. Every number in the correlation
section is a Pearson correlation between two players' DK point draws in the
same 8,000 simulated games. Nothing is taken from a stacking heuristic.

SALARY IS DOWNSTREAM METADATA. It enters only the two value columns, which
are labelled as such, and never a projection. Sportsbook prices, ownership,
contest results and third-party projections enter nowhere at all.

THE INACTIVE STATE IS NOT CERTIFIED AND SAYS SO. This board is built before
official inactives. The gate reads PREINACTIVES_NOT_CERTIFIED. No player is
inferred active from his presence in a salary file, and no player is inferred
inactive from omission.
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import build_postinactives_package as B  # noqa: E402
from nfl.research.dfs.IND_KC import dk_universe_showdown as U  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

import os as _os

SPEC_VERSION = 'nfl-showdown-preinactives-1'
#: One builder serves both phases. The pre-inactives defaults are unchanged,
#: so re-emitting that board is the same work; the post-inactives phase
#: overrides these through the environment rather than by editing the file.
LABEL = _os.environ.get('SHOWDOWN_LABEL', 'PREINACTIVES_SAFE_CANDIDATE')
RUNS_GLOB = _os.environ.get('SHOWDOWN_RUNS', '/tmp/claude-0/indkc/*/')
OUT_NAME = _os.environ.get(
    'SHOWDOWN_OUT', 'IND_KC_SHOWDOWN_PREINACTIVES_2026W2.json')
INACTIVE_STATE = _os.environ.get('SHOWDOWN_INACTIVE_STATE', '')
#: A kicker's DK distribution does NOT live in `dk_scoring`. It lives in the
#: `kicking` layer under its own `dk_points`. Reading only the first key
#: dropped both kickers from a Showdown board silently -- and a kicker is a
#: legitimate captain in this format. Both sources are read, and K is gated
#: below so the same omission cannot pass quietly again.
DK_KEY = 'dk_scoring/dk_points'
DK_KEY_KICKER = 'kicking/dk_points'
CPT_MULTIPLIER = 1.5
THRESHOLDS = (10, 15, 20, 25, 30)
#: Skill positions that MUST have a per-player layer or the board fails.
REQUIRED_POS = ('QB', 'RB', 'WR', 'TE', 'K')


def _summary(v: np.ndarray) -> dict:
    return {
        'mean': round(float(v.mean()), 4),
        'median': round(float(np.median(v)), 4),
        'p75': round(float(np.percentile(v, 75)), 4),
        'p80': round(float(np.percentile(v, 80)), 4),
        'p90': round(float(np.percentile(v, 90)), 4),
        'p95': round(float(np.percentile(v, 95)), 4),
        'ceiling_max_draw': round(float(v.max()), 4),
        'sd': round(float(v.std(ddof=1)), 4),
        'p_zero': round(float((v <= 0).mean()), 4),
        **{f'p_ge_{t}': round(float((v >= t).mean()), 4) for t in THRESHOLDS},
    }


def build(run_dir) -> Outcome:
    run = B.read_run(run_dir)
    if run['n_draws'] <= 0:
        return Outcome.blocked('RUN_HAS_NO_DRAWS', str(run_dir),
                               cause=Cause.DATA)
    uni = U.read_universe()
    if uni.state.name != 'PASS':
        return uni
    ident = U.resolve_identity(uni.value)
    gid_by_dk = ident.value
    ros = {}
    import csv
    import gzip
    with gzip.open(_REPO / U.ROSTER, 'rt') as f:
        for r in csv.DictReader(f):
            if r.get('season') == '2026' and r.get('week') == '2':
                ros[r['gsis_id']] = r

    # One FLEX vector per emitted player. The DK scoring layer IS the flex
    # distribution; CPT is that same vector times 1.5, per draw.
    flex, dk_source = {}, {}
    for pid, st in run['stats'].items():
        for key in (DK_KEY, DK_KEY_KICKER):
            if key in st:
                flex[pid] = st[key]
                dk_source[pid] = key
                break
    if not flex:
        return Outcome.blocked(
            'NO_DK_SCORING_LAYER',
            f'{run["run_id"]} emitted no {DK_KEY}; a Showdown board cannot '
            f'be built from a run with no DK distribution', cause=Cause.DATA)

    qbs = sorted(
        (pid for pid in flex
         if (ros.get(pid) or {}).get('position') == 'QB'),
        key=lambda p: -float(flex[p].mean()))

    def _corr(a, b):
        sa, sb = a.std(), b.std()
        if sa == 0 or sb == 0:
            return None
        return round(float(np.corrcoef(a, b)[0, 1]), 4)

    sal = {}
    for u in uni.value:
        pid = gid_by_dk.get(u['dk_id'])
        if pid:
            sal.setdefault(pid, {})[u['roster_position']] = u['salary']

    emitted = set(flex)
    players, uncertain = [], []
    for pid, v in sorted(flex.items(), key=lambda kv: -float(kv[1].mean())):
        r = ros.get(pid) or {}
        pos = r.get('position')
        cpt_v = v * CPT_MULTIPLIER
        s_flex, s_cpt = _summary(v), _summary(cpt_v)
        row = {
            'gsis_id': pid, 'player': r.get('full_name'),
            'team': r.get('team'), 'position': pos,
            'opponent': ('KC' if r.get('team') == 'IND' else 'IND'),
            'n_draws': run['n_draws'],
            'dk_flex': s_flex,
            'dk_cpt': s_cpt,
            'dk_cpt_definition':
                '1.5x the FLEX draw, applied per simulated world',
            'dk_draw_source': dk_source[pid],
            'role_opportunity': {
                k: {'mean': round(float(x.mean()), 4),
                    'median': round(float(np.median(x)), 4),
                    'p90': round(float(np.percentile(x, 90)), 4),
                    'sd': round(float(x.std(ddof=1)), 4)}
                for k, x in sorted(run['stats'][pid].items())
                if k != DK_KEY},
            'correlation_with_qb': {
                (ros.get(q) or {}).get('full_name') or q: _corr(v, flex[q])
                for q in qbs[:4]},
        }
        same = [_corr(v, flex[o]) for o, ov in flex.items()
                if o != pid and (ros.get(o) or {}).get('team') == r.get('team')]
        opp = [_corr(v, flex[o]) for o, ov in flex.items()
               if o != pid and (ros.get(o) or {}).get('team') not in
               (None, r.get('team'))]
        same = [x for x in same if x is not None]
        opp = [x for x in opp if x is not None]
        row['same_team_correlation'] = {
            'n': len(same),
            'mean': round(float(np.mean(same)), 4) if same else None,
            'min': round(float(np.min(same)), 4) if same else None,
            'max': round(float(np.max(same)), 4) if same else None}
        row['opposing_team_correlation'] = {
            'n': len(opp),
            'mean': round(float(np.mean(opp)), 4) if opp else None,
            'min': round(float(np.min(opp)), 4) if opp else None,
            'max': round(float(np.max(opp)), 4) if opp else None}
        s = sal.get(pid) or {}
        row['downstream_metadata_not_a_model_input'] = {
            'dk_salary_flex': s.get('FLEX'), 'dk_salary_cpt': s.get('CPT'),
            'flex_value_ceiling_per_1k': (
                round(s_flex['p95'] / s['FLEX'] * 1000, 4)
                if s.get('FLEX') else None),
            'flex_value_mean_per_1k': (
                round(s_flex['mean'] / s['FLEX'] * 1000, 4)
                if s.get('FLEX') else None),
            'cpt_value_ceiling_per_1k': (
                round(s_cpt['p95'] / s['CPT'] * 1000, 4)
                if s.get('CPT') else None),
            'cpt_value_mean_per_1k': (
                round(s_cpt['mean'] / s['CPT'] * 1000, 4)
                if s.get('CPT') else None),
            'note': 'salary is used ONLY here, for downstream pricing. It '
                    'did not enter any projection.'}
        if pos in ('QB', 'RB', 'WR', 'TE') and not row['role_opportunity']:
            uncertain.append({'gsis_id': pid, 'player': r.get('full_name'),
                              'position': pos,
                              'flag': 'DK_POINTS_WITHOUT_ROLE_LAYER',
                              'why': 'a DK distribution exists but no '
                                     'underlying opportunity layer does, so '
                                     'the role behind the score is not '
                                     'visible'})
        players.append(row)

    dk_skill = [u for u in uni.value
                if u['roster_position'] == 'FLEX'
                and u['position'] in REQUIRED_POS]
    missing = []
    # AN UNRESOLVED SALARY ROW IS NOT A MISSING FORECAST. Collapsing the two
    # reads as "the model has nothing for this player" when the truth may be
    # "the model has him, we just could not attach his DraftKings price".
    # Those call for different downstream handling, so they are separate
    # states. An alias is resolved here ONLY from the roster vintage's own
    # name fields; where it is not, the row stays unresolved rather than
    # being matched by resemblance.
    emitted_names = {(ros.get(q) or {}).get('team'):
                     None for q in emitted}
    del emitted_names
    for u in dk_skill:
        pid = gid_by_dk.get(u['dk_id'])
        if pid is None:
            missing.append({'name': u['name'], 'team': u['team'],
                            'position': u['position'],
                            'state': 'DK_SALARY_ROW_IDENTITY_UNRESOLVED',
                            'why': 'the DraftKings display name matches no '
                                   'roster row on this club by exact '
                                   'normalised name. The model may still '
                                   'carry a projection for this person under '
                                   'the club-declared name; what is missing '
                                   'is the link to his DK salary row, not '
                                   'necessarily the forecast.'})
        elif pid not in emitted:
            missing.append({'name': u['name'], 'team': u['team'],
                            'position': u['position'], 'gsis_id': pid,
                            'state': 'NO_EMITTED_ROW'})
    # A player sitting in the owner's saved lineup template with NO emitted
    # row is the most expensive kind of gap here, because a downstream
    # optimiser starting from that template would carry him forward with no
    # projection behind him. Named separately rather than left inside the
    # general missing list.
    templ = set()
    import csv as _csv
    for r in _csv.reader(open(_REPO / U.ENTRIES[0], newline='')):
        for c in r[4:10]:
            c = (c or '').strip()
            if '(' in c and c.endswith(')'):
                templ.add(c[c.rindex('(') + 1:-1])
    in_template_without_row = []
    by_dkid = {u['dk_id']: u for u in uni.value}
    for dkid in sorted(templ):
        u = by_dkid.get(dkid)
        if not u:
            continue
        pid = gid_by_dk.get(dkid)
        if pid is None or pid not in emitted:
            in_template_without_row.append(
                {'name': u['name'], 'team': u['team'],
                 'position': u['position'], 'dk_id': dkid,
                 'state': 'IDENTITY_UNRESOLVED' if pid is None
                          else 'NO_EMITTED_ROW'})

    # ROLE PLAUSIBILITY, CHECKED AGAINST THE DEPTH CHART AND NOTHING ELSE.
    # The engine has no depth-chart prior, so it can hand a fullback a lead
    # back's workload. That is a football claim a reader must see, and the
    # club's own declared depth_chart_position is the evidence for it.
    # Salary is NOT used here: a cheap player is not thereby implausible,
    # and letting price judge a projection is the contamination this whole
    # pipeline is built to prevent.
    role_flags = []
    order = {}
    for club in ('IND', 'KC'):
        mates = [pid for pid in emitted
                 if (ros.get(pid) or {}).get('team') == club]

        def _m(pid, key):
            v = run['stats'].get(pid, {}).get(key)
            return float(v.mean()) if v is not None else 0.0
        carries = sorted(mates, key=lambda q: -_m(q, 'rushing/carries'))
        tgts = sorted(mates, key=lambda q: -_m(q, 'receiving/targets'))
        order[club] = {
            'projected_carry_order': [
                {'player': (ros.get(q) or {}).get('full_name'),
                 'depth_chart_position': (ros.get(q) or {}).get(
                     'depth_chart_position'),
                 'carries_mean': round(_m(q, 'rushing/carries'), 3)}
                for q in carries[:6] if _m(q, 'rushing/carries') > 0],
            'projected_target_order': [
                {'player': (ros.get(q) or {}).get('full_name'),
                 'depth_chart_position': (ros.get(q) or {}).get(
                     'depth_chart_position'),
                 'targets_mean': round(_m(q, 'receiving/targets'), 3)}
                for q in tgts[:8] if _m(q, 'receiving/targets') > 0]}
        rb1 = next((q for q in mates
                    if (ros.get(q) or {}).get('depth_chart_position') == 'RB'
                    and _m(q, 'rushing/carries') > 0), None)
        for q in mates:
            r = ros.get(q) or {}
            c = _m(q, 'rushing/carries')
            if r.get('depth_chart_position') == 'FB' and c >= 3:
                role_flags.append({
                    'player': r.get('full_name'), 'team': club,
                    'gsis_id': q, 'flag': 'FULLBACK_GIVEN_RUSHING_WORKLOAD',
                    'depth_chart_position': 'FB',
                    'projected_carries_mean': round(c, 3),
                    'projected_rushing_yards_mean': round(
                        _m(q, 'rushing/rushing_yards'), 3),
                    'why': "the club's declared depth chart lists this "
                           "player as a fullback, and the engine carries no "
                           "depth-chart prior. Treat the workload as a "
                           "MODEL ROLE ASSUMPTION, not a forecast of usage."})
            if (rb1 and q != rb1
                    and r.get('depth_chart_position') in ('FB', 'TE', 'WR')
                    and c > _m(rb1, 'rushing/carries')):
                role_flags.append({
                    'player': r.get('full_name'), 'team': club,
                    'gsis_id': q,
                    'flag': 'NON_RB_PROJECTED_ABOVE_DEPTH_CHART_RB1',
                    'depth_chart_position': r.get('depth_chart_position'),
                    'projected_carries_mean': round(c, 3),
                    'depth_chart_rb1': (ros.get(rb1) or {}).get('full_name'),
                    'rb1_carries_mean': round(_m(rb1, 'rushing/carries'), 3),
                    'why': 'a player the club does not list as its lead back '
                           'is projected for more carries than the one it '
                           'does. Role assumption, not usage evidence.'})

    support = {}
    for club in ('IND', 'KC'):
        support[club] = {}
        for p in REQUIRED_POS + ('K',):
            support[club][p] = sum(
                1 for pid in emitted
                if (ros.get(pid) or {}).get('team') == club
                and (ros.get(pid) or {}).get('position') == p)
    empty = [f'{c}/{p}' for c, d in support.items() for p, n in d.items()
             if p in REQUIRED_POS and n == 0]

    # THE GATE IS COMPUTED FROM THE EMITTED ROWS, NOT FROM INTENT. A fixture
    # can declare a player excluded and a layer still emit him; the check
    # that matters is the intersection of declared ids with the ids the run
    # actually wrote.
    inact = {}
    if INACTIVE_STATE and pathlib.Path(INACTIVE_STATE).exists():
        inact = json.loads(pathlib.Path(INACTIVE_STATE).read_text())
    if inact:
        declared = {x['gsis_id'] for x in inact['resolved']}
        survivors = sorted(declared & emitted)
        gate = ('OFFICIALLY_INACTIVE_PLAYER_IN_PLAYABLE_BOARD' if survivors
                else '0_OFFICIALLY_INACTIVE_PLAYERS_IN_PLAYABLE_BOARD')
        gate_why = (
            f'{len(declared)} declared inactive ids were intersected with '
            f'the {len(emitted)} gsis_id rows the run actually emitted. '
            f'{len(survivors)} survived.')
        inactive_block = {
            'n_declared': len(declared),
            'n_survivors_in_playable_board': len(survivors),
            'survivors': [{'gsis_id': q,
                           'player': (ros.get(q) or {}).get('full_name')}
                          for q in survivors],
            'provenance': inact.get('provenance'),
            'resolved': inact['resolved'],
            'unresolved': inact.get('unresolved') or []}
    else:
        gate = 'PREINACTIVES_NOT_CERTIFIED'
        gate_why = (
            'Official inactives are not available at this information cut. '
            'No player was excluded on availability grounds. Presence in a '
            'DraftKings salary file is NOT evidence of activity and absence '
            'from one is NOT evidence of inactivity.')
        inactive_block = None
    gates = {
        'inactive_gate': gate,
        'inactive_gate_why': gate_why,
        'inactive_evidence': inactive_block,
        'skill_layer_gate': ('FAIL_EMPTY_SKILL_POSITION' if empty
                             else 'ALL_SKILL_POSITIONS_HAVE_ROWS'),
        'empty_skill_positions': empty,
        'role_plausibility_flags': role_flags,
        'projected_usage_order_vs_depth_chart': order,
        'players_in_owner_entry_template_without_a_projection':
            in_template_without_row,
        'dk_universe_vs_emitted': {
            'dk_skill_rows': len(dk_skill),
            'not_emitted_or_unresolved': missing,
            'n_missing': len(missing)},
        'alias_policy': {
            'rule': 'An alias is accepted only when the roster vintage\'s '
                    'own name fields carry it. No edit-distance, nickname '
                    'table or resemblance matching is permitted.',
            'open_cases': [
                {'dk_name': 'Drew Ogletree', 'team': 'IND',
                 'club_declared_name': 'Andrew Ogletree',
                 'gsis_id_if_same_person': '00-0037292',
                 'state': 'LEFT_UNRESOLVED_BY_OWNER_RULING',
                 'verification': 'The roster vintage carries full_name '
                                 '"Andrew Ogletree" and football_name '
                                 '"Andrew". Neither field contains "Drew", '
                                 'so the alias CANNOT be verified cleanly '
                                 'from the authoritative source held here '
                                 'and was not assumed.',
                 'materiality': 'NON_CORE. The model does emit a row for '
                                '00-0037292: DK mean 1.0965, p95 6.6, third '
                                'among IND tight ends behind Tyler Warren '
                                '(9.05 / 22.7) and Mo Alie-Cox (2.47 / '
                                '10.5). That is not a meaningful ceiling, so '
                                'the unresolved salary link changes no '
                                'Showdown decision.',
                 'blocking': False}]},
        'identity': {'n_resolved': ident.evidence['n_resolved'],
                     'n_unresolved': ident.evidence['n_unresolved'],
                     'unresolved': ident.evidence['unresolved'],
                     'ambiguous': ident.evidence['ambiguous']},
    }
    for f in role_flags:
        uncertain.append(f)
    usable = not empty and bool(players)
    pkg = {
        'LABEL': LABEL,
        'USABLE_FOR_PREINACTIVES_SAFE_SHOWDOWN_CONSTRUCTION':
            'YES' if usable else 'NO',
        'READ_THIS_FIRST': {
            'what_this_is':
                'A PRE-INACTIVES Showdown decision board for IND@KC, built '
                'from one set of 8,000 simulated games. It is a CANDIDATE '
                'board and it is not certified against official inactives.',
            'candidate_status': 'CANDIDATE_NOT_ACCEPTED_BASELINE',
            'board_is_unsealed':
                'The run stops at artifact_sealing on two stale registered '
                'inputs (denom_panel, team_volume_history). Every football '
                'layer upstream of that stop passed.',
            'dst': 'DST_UNSUPPORTED: the engine emits no team-defence '
                   'outputs, so the two DST salary rows have no projection '
                   'here and none was invented.',
            'forbidden_inputs_confirmed':
                'No sportsbook price, DraftKings salary, ownership estimate, '
                'optimiser metric or third-party projection entered the '
                'football model. The third-party sheet supplied with this '
                'request carries VegasPts, FC Proj, My Proj, Floor, Ceiling '
                'and an exposure column; it is preserved as evidence and is '
                'never parsed by this pipeline.',
            'v2_status': 'V2 NOT YET EARNED',
        },
        'spec_version': SPEC_VERSION,
        'generated_at_utc': _dt.datetime.now(_dt.UTC).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
        'provenance': {
            'game_id': run['game_id'], 'run_id': run['run_id'],
            'run_status': run['status'],
            'information_cut': run['written_at'],
            'n_draws': run['n_draws'],
            'execution_identity': run['execution_identity'],
            'code_commit': run['code_commit'],
            'draw_content_digest': run['content_digest'],
            'dk_entry_file': U.ENTRIES[0],
            'dk_entry_file_sha256': U.ENTRIES[1],
            'third_party_sheet':
                'nfl/dfs/salaries/raw/'
                'THIRDPARTY_players_IND_KC_2026W2_CONTEXT_ONLY.csv',
            'third_party_sheet_handling': 'PRESERVED_NEVER_PARSED',
        },
        'gates': gates,
        'position_support_per_club': support,
        'uncertain_roles': uncertain,
        'players': players,
    }
    return Outcome.ok('SHOWDOWN_PACKAGE_BUILT', value=pkg,
                      n_players=len(players), usable=usable,
                      empty_skill_positions=empty)


def main():
    import glob
    dirs = sorted(glob.glob(RUNS_GLOB))
    if not dirs:
        print('BLOCKED[NO_RUN_DIRECTORY] /tmp/claude-0/indkc/*/ is empty')
        return 1
    o = build(dirs[-1])
    if o.state.name != 'PASS':
        print(f'{o.state.name}[{o.code}] {o.detail}')
        return 1
    p = _REPO / 'nfl' / 'research' / 'sunday' / OUT_NAME
    p.write_text(json.dumps(o.value, indent=1, sort_keys=True) + '\n')
    g = o.value['gates']
    print(f'wrote {p.name}  {p.stat().st_size} bytes')
    print(f'players      : {o.evidence["n_players"]}')
    print(f'inactive gate: {g["inactive_gate"]}')
    print(f'skill gate   : {g["skill_layer_gate"]} {g["empty_skill_positions"]}')
    print(f'dk missing   : {g["dk_universe_vs_emitted"]["n_missing"]}')
    print(f'support      : {o.value["position_support_per_club"]}')
    print(f'USABLE       : '
          f'{o.value["USABLE_FOR_PREINACTIVES_SAFE_SHOWDOWN_CONSTRUCTION"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
