#!/usr/bin/env python3.12
"""Pre-computed injury cascades for the slate's open questions. SCENARIO MAP ONLY -- never production.

    python3.12 nfl/tools/classic_scenarios.py 2026W4

Owner directive 2026-10-04 (pre-lock staging). The OPEN QUESTIONS are read from the state, not chosen:
every unresolved Questionable/Doubtful player and every quarterback whose starter evidence is the chart
alone (DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT). For each, one scenario: he is inactive. The real
state builder resolves a REHEARSAL packet, the real role-state and projection modules run with their
paths pointed into a scratch directory, and the scenario projection is diffed against production.

There is no "he plays" scenario because there is nothing to compute: the projection does not price a
Questionable designation (P(plays) is the measured appearance rate at depth rank, proj_v1
allocate_opportunity), so clearing a Questionable changes only his conviction-pool eligibility.

MATERIAL (owner's declared definition): >= 5% of the 150-max, >= 10% of the 20-max, in the 3-entry
set, or his absence moves another player >= 2.0 DK points. Non-material questions are listed as
checked, not dropped.

Nothing here alters production: the production STATE/PROJ/DRAWS/PORTFOLIOS are hashed before and after
and the run refuses if any changed. Writes DK_<slate>_EARLY_SCENARIOS.json.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
NEXT_HEALTHY = 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT'
#: owner's materiality definition, 2026-10-04 (declared by the owner, not fitted)
MATERIAL_150, MATERIAL_20, MATERIAL_MOVE = 0.05, 0.10, 2.0
#: reporting floor for a teammate row in the dependency map (same as the change log's)
REPORT_MOVE = 0.5
COMPONENTS = ('pass_attempts', 'pass_yards', 'carries', 'rush_yards', 'targets', 'receptions', 'rec_yards')
#: Hard Rock markets (classic_prop_compare.MARKETS names) a position's numbers feed
MARKETS = {'QB': ('player_passing_yards', 'player_passing_attempts', 'player_passing_touchdowns',
                  'player_interceptions', 'player_rushing_yards', 'player_rushing_attempts'),
           'RB': ('player_rushing_yards', 'player_rushing_attempts', 'player_receptions', 'player_receiving_yards',
                  'player_rushing_+_receiving_yards', 'player_touchdowns'),
           'WR': ('player_receptions', 'player_receiving_yards', 'player_touchdowns'),
           'TE': ('player_receptions', 'player_receiving_yards', 'player_touchdowns')}


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def open_questions(state):
    out = []
    for dk, p in state['players'].items():
        av = p['current_availability']
        if av.get('resolution'):
            continue
        if (av.get('designation') or '') in ('QUESTIONABLE', 'DOUBTFUL'):
            out.append((dk, f"{av['designation']} (Friday report)"))
        elif (p.get('predicted_lineup_context') or {}).get('state') == NEXT_HEALTHY:
            out.append((dk, 'starter by depth chart only (QB1 reported OUT)'))
    return sorted(out, key=lambda x: state['players'][x[0]]['name'])


@contextlib.contextmanager
def _redirected(td):
    """Point role_state and proj_v1 at scratch paths; restore on exit."""
    from nfl.tools import role_state as RS, proj_v1 as PV
    saved = (RS.POST, RS.OUT, PV.POST, PV.ROLE, PV.OUT, PV.SLATE_WEEK, PV.MARKET_ARM)
    try:
        RS.OUT, PV.ROLE = td / 'ROLE_STATE.json', td / 'ROLE_STATE.json'
        RS.POST = PV.POST = td / 'STATE.json'
        PV.OUT = td / 'PROJ.json'
        PV.MARKET_ARM = 'FOOTBALL_ONLY'
        yield RS, PV
    finally:
        RS.POST, RS.OUT, PV.POST, PV.ROLE, PV.OUT, PV.SLATE_WEEK, PV.MARKET_ARM = saved


def scenario_projection(slate, as_of, packet, td):
    from nfl.tools import classic_slate_state as C
    o = C.build(slate, as_of=as_of, evidence_packet=packet, write=False)
    if o.state.value != 'PASS':
        return o
    (td / 'STATE.json').write_text(json.dumps(o.value, default=str))
    with _redirected(td) as (RS, PV):
        PV.SLATE_WEEK = int(o.value['week'])
        rs = RS.run()
        if rs.state.value != 'PASS':
            return rs
        rc = PV.main()
    if rc != 0 or not (td / 'PROJ.json').exists():
        return Outcome.fail('SCENARIO_PROJECTION_REFUSED', f'proj_v1 returned {rc}')
    return Outcome.ok('SCENARIO_PROJECTED', json.loads((td / 'PROJ.json').read_text()), 'ok')


def build(slate, as_of=None):
    f = lambda n: OUT_DIR / f'DK_{slate}_EARLY_{n}'  # noqa: E731
    guard = {n: _sha(f(n)) for n in ('STATE.json', 'PROJ.json', 'DRAWS.json', 'PORTFOLIOS.json', 'UPLOAD.csv')}
    role_prod = _REPO / 'nfl/derived/ROLE_STATE.json'
    guard['nfl/derived/ROLE_STATE.json'] = _sha(role_prod)
    state = json.loads(f('STATE.json').read_text())
    proj = json.loads(f('PROJ.json').read_text())['rows']
    port = json.loads(f('PORTFOLIOS.json').read_text())
    book = json.loads(f('RESEARCH_BOOK.json').read_text()) if f('RESEARCH_BOOK.json').exists() else {}
    as_of = as_of or state.get('as_of')
    expo, n_lu = {}, {}
    for c in port['contests']:
        for _n, e in c['report']['player_exposure'].items():
            expo.setdefault(e['dk_id'], {})[c['profile']] = e['overall']
        for lu in c['lineups']:
            for s in lu['slots']:
                n_lu.setdefault(s['dk_id'], {}).setdefault(c['profile'], 0)
                n_lu[s['dk_id']][c['profile']] += 1
    from nfl.tools import classic_prop_compare as PC
    _slate_gate, tg = PC.team_gates(book, json.loads(f('PROJ.json').read_text()), state)
    yards_blocked = {c for c, t in tg.items() if not t['yards_props_open']}
    YARDS_MARKETS = PC.YARDS_MARKETS
    qs = open_questions(state)
    if not qs:
        return Outcome.blocked('SCENARIOS_NO_OPEN_QUESTIONS', 'the state carries no unresolved question',
                               cause=Cause.EMPTY_INPUT)
    rows = []
    for dk, why in qs:
        p = state['players'][dk]
        # inside the repo (the projection records its inputs relative to it), in the gitignored sensitivity/
        td = OUT_DIR / 'sensitivity' / 'scenarios' / f'{dk}_inactive'
        td.mkdir(parents=True, exist_ok=True)
        pk = {'packet_id': f'scenario-{dk}-inactive', 'source': 'REHEARSAL', 'received_at': as_of,
              'source_detail': 'pre-computed scenario, not evidence', 'starters': {},
              'players': [{'name': p['name'], 'team': p['team'], 'status': 'INACTIVE'}]}
        o = scenario_projection(slate, as_of, pk, td)
        ex = expo.get(dk, {})
        row = {'player': p['name'], 'dk_id': dk, 'team': p['team'], 'position': p['position'],
               'open_question': why, 'base_dk_points': round((proj.get(dk) or {}).get('dk_points') or 0.0, 2),
               'exposure': ex, 'lineups_containing': n_lu.get(dk, {})}
        if o.state.value != 'PASS':
            row.update(scenario='REFUSED', refusal=f'{o.code}: {o.detail}')
            rows.append(row)
            continue
        sp = o.value['rows']
        successor = None
        if p['position'] == 'QB':
            sst = json.loads((td / 'STATE.json').read_text())['players']
            nh = [v['name'] for v in sst.values() if v['team'] == p['team'] and v['position'] == 'QB'
                  and (v.get('predicted_lineup_context') or {}).get('state') == NEXT_HEALTHY]
            split = sorted(((r_.get('pass_attempts') or 0.0, r_['name']) for r_ in sp.values()
                            if r_.get('team') == p['team'] and r_.get('position') == 'QB' and (r_.get('pass_attempts') or 0) >= 1),
                           reverse=True)
            successor = ({'state': 'NEXT_HEALTHY_ON_CAPTURED_CHART', 'player': nh[0]} if nh else
                         {'state': 'NO_SUCCESSOR_ON_CAPTURED_CHART',
                          'why': 'every quarterback the captured chart lists is out; the projection splits the '
                                 'passing volume among unlisted quarterbacks, which is the honest reading of no evidence',
                          'pass_attempts_split': {n: round(a, 1) for a, n in split}})
        moves = []
        for k, r in proj.items():
            if k == dk or r.get('team') != p['team']:
                continue
            a, b = r.get('dk_points') or 0.0, (sp.get(k) or {}).get('dk_points') or 0.0
            if abs(b - a) >= REPORT_MOVE:
                comp = {c: round(((sp.get(k) or {}).get(c) or 0.0) - (r.get(c) or 0.0), 2) for c in COMPONENTS
                        if abs(((sp.get(k) or {}).get(c) or 0.0) - (r.get(c) or 0.0)) >= 0.05}
                moves.append({'player': r['name'], 'dk_id': k, 'position': r.get('position'),
                              'old': round(a, 2), 'new': round(b, 2), 'change': round(b - a, 2),
                              'components': comp, 'exposure': expo.get(k, {}),
                              'hard_rock_markets': [m for m in MARKETS.get(r.get('position'), ())
                                                    if not (m in YARDS_MARKETS and p['team'] in yards_blocked)]})

        moves.sort(key=lambda m: -abs(m['change']))
        why_mat = [w for w, ok in ((f'>= {MATERIAL_150:.0%} of the 150-max', ex.get('MAX150', 0) >= MATERIAL_150),
                                   (f'>= {MATERIAL_20:.0%} of the 20-max', ex.get('MAX20', 0) >= MATERIAL_20),
                                   ('in the 3-entry set', ex.get('MAX3', 0) > 0),
                                   (f'moves a teammate >= {MATERIAL_MOVE} DK points',
                                    any(abs(m['change']) >= MATERIAL_MOVE for m in moves))) if ok]
        row.update(scenario='HE_IS_INACTIVE', material=bool(why_mat), material_because=why_mat, successor=successor,
                   cascade=moves, club_total_change=round(sum(
                       ((sp.get(k) or {}).get('dk_points') or 0.0) - (r.get('dk_points') or 0.0)
                       for k, r in proj.items() if r.get('team') == p['team']), 2),
                   portfolios_to_rebuild=sorted({c for c, n in n_lu.get(dk, {}).items() if n} |
                                                {c for m in moves for c, x in m['exposure'].items() if x}),
                   hard_rock_markets_affected=sorted({f"{m['player']} {mk}" for m in moves for mk in m['hard_rock_markets']}),
                   yards_markets_blocked_for_club=p['team'] in yards_blocked)
        rows.append(row)
    after = {n: _sha(_REPO / n if n.startswith('nfl/') else f(n)) for n in guard}
    if after != guard:
        return Outcome.fail('SCENARIOS_TOUCHED_PRODUCTION', f'production artifacts changed: {[n for n in guard if guard[n] != after[n]]}')
    doc = {'ARTIFACT': 'CLASSIC_SCENARIOS', 'slate_id': slate, 'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'LABEL': 'SCENARIO_MAP_ONLY_NOT_PRODUCTION: nothing here changes a projection, a lineup or a price',
           'base': {'projection_sha256': guard['PROJ.json'], 'state_sha256': guard['STATE.json'],
                    'portfolios_sha256': guard['PORTFOLIOS.json']},
           'materiality': {'MAX150': MATERIAL_150, 'MAX20': MATERIAL_20, 'MAX3': 'any', 'teammate_move_dk': MATERIAL_MOVE,
                           'SOURCE': 'owner directive 2026-10-04'},
           'NO_ACTIVE_SCENARIO': 'the projection does not price a Questionable designation; clearing one changes '
                                 'only conviction-pool eligibility',
           'scenarios': rows}
    f('SCENARIOS.json').write_text(json.dumps(doc, indent=1, default=str))
    n_mat = sum(1 for r in rows if r.get('material'))
    n_ref = sum(1 for r in rows if r.get('scenario') == 'REFUSED')
    if n_ref:
        return Outcome.fail('SCENARIOS_REFUSED', f'{n_ref} of {len(rows)} scenario(s) refused', refused=n_ref)
    return Outcome.measured('SCENARIOS_BUILT', {'n': len(rows), 'material': n_mat}, n_measured=len(rows),
                            what='open questions', detail=f'{len(rows)} open questions, {n_mat} material; production untouched')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--as-of', default=None)
    a = ap.parse_args()
    o = build(a.slate_id, a.as_of)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
