#!/usr/bin/env python3.12
"""Material-player research pass: an audit over the structured model, never a second projection.

    python3.12 nfl/tools/classic_material_research.py 2026W4

Owner directive 2026-10-04 10:22 ET. Every player meeting ANY of the owner's criteria is reviewed against
the evidence this repository holds, and gets a verdict:

  SUPPORTED                 the projection is consistent with the held evidence
  SUPPORTED_WITH_UNCERTAINTY consistent, but a named uncertainty (availability, a changed role, a
                            chart/usage conflict, a short sample) could move it
  NEEDS_REVIEW              the projection departs from his own measured usage without a role change
                            that explains it, or an identity/club contradiction is open
  INPUT_DEFECT_FOUND        a factual input is wrong (projected while absent; club mismatch on a
                            projected player) -- fix the football state, never the number

Nothing here edits a projection. Items this machine cannot see (latest news, coaching comments, a
practice trend beyond the Friday report) are marked UNAVAILABLE_HERE and belong to the networked agent.
Writes DK_<slate>_EARLY_MATERIAL_RESEARCH.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402
from nfl.tools import availability as AV               # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
#: owner's materiality definition (2026-10-04)
EXPO_150, EXPO_20 = 0.05, 0.10
#: DECLARED review thresholds (reporting only; they flag a card for a human look and change nothing)
OPP_GAP_ABS, OPP_GAP_REL = 3.0, 0.5       # projected vs measured opportunities per game
SIM_GAP = 1.5                             # simulated mean vs projection, DK points
UNAVAILABLE_HERE = 'UNAVAILABLE_HERE: no network on this machine; the networked agent holds it'


def _j(p):
    return json.loads(p.read_text()) if p.exists() else None


def _opp(pos, d):
    """(projected, measured per game, unit) opportunities for a position."""
    pr, m = d['projection'], d['measured_2026']
    g = m.get('games') or 0
    if pos == 'QB':
        return pr.get('pass_attempts') or 0.0, (m.get('pass_att') or 0) / g if g else None, 'pass attempts'
    if pos == 'RB':
        return ((pr.get('carries') or 0) + (pr.get('targets') or 0),
                ((m.get('carries') or 0) + (m.get('targets') or 0)) / g if g else None, 'carries + targets')
    return pr.get('targets') or 0.0, (m.get('targets') or 0) / g if g else None, 'targets'


def material_set(state, board, audit, slots, scen, fcd=None):
    why = {}
    add = lambda dk, w: why.setdefault(dk, []).append(w)  # noqa: E731
    by_name = {(p['name'], p['team']): dk for dk, p in state['players'].items()}
    for p in board['players']:
        dk = p['dk_id']
        if p['pos'] == 'QB' and p.get('starter_state') and p['availability'] not in AV.ABSENT_STATUSES \
                and (state['players'][dk].get('depth_rank') == 1):
            add(dk, 'starting QB')
        if (p.get('exp_150max') or 0) >= EXPO_150:
            add(dk, f">= {EXPO_150:.0%} of the 150-max")
        if (p.get('exp_20max') or 0) >= EXPO_20:
            add(dk, f">= {EXPO_20:.0%} of the 20-max")
        if (p.get('exp_3entry') or 0) > 0:
            add(dk, 'in the 3-entry set')
        if (p.get('designation') or '') in ('QUESTIONABLE', 'DOUBTFUL'):
            add(dk, p['designation'].title())
        if p['classification'] == 'role-dependent':
            add(dk, 'material role uncertainty (board: role-dependent)')
    for g in board.get('fc_comparison', []):
        dk = by_name.get((g['player'], g['team']))
        if dk:
            add(dk, f"large FC disagreement ({g['diff']:+.1f})")
    for x in audit['simulator']['dk_top20_positive'] + audit['simulator']['dk_top20_negative']:
        dk = by_name.get((x['player'], x['team']))
        if dk and x['abs_diff'] >= SIM_GAP:
            add(dk, f"simulation vs projection {x['sim_mean'] - x['projection']:+.1f}")
    starters = {(r['player'], r['team']) for r in slots['rows']}
    for (n, t) in starters:
        dk = by_name.get((n, t))
        if dk and why.get(dk):          # a prop candidate is researched when it is ALSO material otherwise
            why[dk].append('likely Hard Rock prop candidate')
    for s in scen.get('scenarios', []):
        if s.get('material'):
            add(s['dk_id'], 'material open question (scenario map)')
    for r in (fcd or {}).get('rows', []):
        if r.get('material') and r.get('classification') != 'OUR_STATE_SUPPORTED' or \
                (r.get('material') and any(v for v in (r['ours'].get('exposure') or {}).values())):
            add(r['dk_id'], f"FC snapshot change ({'; '.join(r['material_because'])}) classified {r.get('classification')}")
    return {dk: sorted(set(w)) for dk, w in why.items()}


def card_index(book):
    out, teams = {}, {}
    for gid, g in book['games'].items():
        for club, t in g['teams'].items():
            teams[club] = t
            for c in t['players']:
                out[c['dk_id']] = (gid, club, c)
    return out, teams


def judge(dk, reasons, state, cards, teams, board_by, audit, scen_by, contradictions):
    p = state['players'][dk]
    gid, club, c = cards.get(dk, (None, p['team'], None))
    b = board_by.get(dk, {})
    av = p['current_availability']
    pos = p['position']
    out = {'player': p['name'], 'team': p['team'], 'position': pos, 'dk_id': dk, 'material_because': reasons,
           'MODEL_PROJECTION': b.get('projection'), 'SIM_MEAN': b.get('sim_mean'),
           'ROLE_STATE': {'role_band': b.get('role'), 'depth_rank': p.get('depth_rank'),
                          'starter_evidence': (p.get('predicted_lineup_context') or {}).get('state'),
                          'starter_tier': (p.get('predicted_lineup_context') or {}).get('evidence_tier')},
           'exposure': {'MAX150': b.get('exp_150max'), 'MAX20': b.get('exp_20max'), 'MAX3': b.get('exp_3entry')}}
    risks, review, defects = [], [], []
    absent = av['status'] in AV.ABSENT_STATUSES
    if absent and (b.get('projection') or 0) > 0.5:
        defects.append(f"projected {b.get('projection')} while {av['status']}")
    for x in contradictions:
        if not x['player'].startswith(p['name'] + ' ('):
            continue
        if x['kind'] in ('ROSTER_MOVE_SINCE_LAST_CAPTURE', 'TEAM_MISMATCH'):
            review.append(f"club in the DraftKings pool ({x.get('dk_club')}) differs from the last roster capture ({x.get('roster_capture_club')})")
        elif x['kind'] == 'IDENTITY_NOT_RESOLVED':
            review.append('identity not resolved to a football record, so he is NOT projected (input gap: roster capture)')
    ev = {
        '1_starter_availability': f"{av['status']} (tier {av.get('tier')})" + (f"; starter evidence {out['ROLE_STATE']['starter_evidence']}"
                                                                              f" [{out['ROLE_STATE']['starter_tier']}]" if out['ROLE_STATE']['starter_evidence'] else ''),
        '2_latest_injury_news': (f"Friday report: {av.get('designation')} ({av.get('injury')})" if av.get('designation') else 'not on the final report')
                                + '; anything newer: ' + UNAVAILABLE_HERE,
        '3_practice_trend': (av.get('practice_status') or 'no practice line') + ' (final day only; the daily trend is not captured)',
        '4_depth_chart': None, '5_recent_usage': None, '6_trend': None,
        '7_teammate_absences': sorted(q['name'] for q in state['players'].values() if q['team'] == p['team'] and q['position'] in ('QB', 'RB', 'WR', 'TE')
                                      and q['current_availability']['status'] in AV.ABSENT_STATUSES),
        '8_coaching_comments': UNAVAILABLE_HERE,
        '9_offensive_line': None, '10_opponent': None, '11_role_uncertainty': None, '12_model_consistent': None}
    if c is None and pos == 'DST':
        t = teams[p['team']]
        dc = t['dst']
        pa = dc['points_allowed_simulated']
        ev.update({'4_depth_chart': 'team unit', '5_recent_usage': f"observed 2026: {dc['observed_2026']}",
                   '6_trend': UNAVAILABLE_HERE, '9_offensive_line': 'n/a (defence)',
                   '10_opponent': f"{dc['opponent']} simulated to score {pa['mean']} (p10 {pa['p10']}, p90 {pa['p90']}); "
                                  f"P(allow <= 6) {pa['p_allow_6_or_fewer']}, P(allow >= 28) {pa['p_allow_28_or_more']}",
                   '11_role_uncertainty': 'sacks and takeaways NOT_DECOMPOSED; defensive/return TDs NOT_MODELLED',
                   '12_model_consistent': 'points allowed drawn from the opponent\'s simulated score in the same world'})
        risks = ['DST projection is a floor: sacks/takeaways are not decomposed and defensive or return TDs are not modelled']
        out.update(evidence=ev, RESEARCH_VERDICT='SUPPORTED_WITH_UNCERTAINTY', WHY='; '.join(risks), concerns=[])
        return out
    if c is None:
        out.update(evidence=ev, RESEARCH_VERDICT='NEEDS_REVIEW' if not defects else 'INPUT_DEFECT_FOUND',
                   WHY='no research-book card for this player', concerns=defects or ['no card'])
        return out
    t = teams[club]
    d = c['depth']
    ev['4_depth_chart'] = f"chart rank {d.get('declared_rank')}, usage rank {d.get('measured_usage_rank')}, projection rank {d.get('projection_depth_rank')}"
    m = c['measured_2026']
    ev['5_recent_usage'] = (f"{m.get('games')} games: {m.get('pass_att')} att, {m.get('carries')} carries, {m.get('targets')} targets"
                            f" (target share {m.get('target_share')}, carry share {m.get('carry_share')})")
    pt = c['playing_time']
    ev['6_trend'] = f"offense snap share {pt.get('offense_snap_share')} (weeks {pt.get('snap_weeks')}); routes {pt.get('route_participation')}"
    ol = t['offensive_line']['starters']
    hurt = [f"{x['slot']} {x['starter']} ({x['report_status']})" for x in ol if x['report_status'] not in ('NOT_ON_REPORT', 'NONE_LISTED')]
    ev['9_offensive_line'] = ('OL starters on the report: ' + ', '.join(hurt)) if hurt else 'no OL starter on the final report'
    ol_ = t['opponent_layer']
    o = ol_.get('OBSERVED_CONTEXT_2026', {})
    ev['10_opponent'] = (f"{ol_['opponent']} allowed {o.get('pass_att_faced_pg')} pass att / {o.get('rush_att_faced_pg')} rush att per game, "
                         f"sack rate {o.get('sack_rate')}, explosive pass {o.get('explosive_pass_rate_allowed')}; observed context only, not a model term")
    conf = (c.get('uncertainty') or {}).get('conflicts') or []
    ev['11_role_uncertainty'] = f"role confidence {c['uncertainty'].get('role_confidence')}; prior tier {c['uncertainty'].get('prior_tier')}" + \
        (f"; conflicts: {'; '.join(conf)}" if conf else '')
    proj, meas, unit = _opp(pos, c)
    role_changed = bool(ev['7_teammate_absences']) or (out['ROLE_STATE']['starter_evidence'] is not None) or \
        (isinstance(d.get('projection_depth_rank'), int) and isinstance(d.get('measured_usage_rank'), int)
         and d['projection_depth_rank'] < d['measured_usage_rank'])
    gap = None if meas is None else proj - meas
    if gap is not None and abs(gap) >= max(OPP_GAP_ABS, OPP_GAP_REL * meas):
        (risks if role_changed else review).append(
            f"projects {proj:.1f} {unit} against {meas:.1f} measured per game"
            + (' -- explained by a role change this week' if role_changed else ' with no role change that explains it'))
    ev['12_model_consistent'] = (f"projected {proj:.1f} {unit} vs measured {meas:.1f}/game" if meas is not None else
                                 f"projected {proj:.1f} {unit}; no 2026 games measured")
    if (av.get('designation') or '') in ('QUESTIONABLE', 'DOUBTFUL') and not av.get('resolution'):
        s = scen_by.get(dk) or {}
        risks.append(f"{av['designation']} and unresolved; if out: " + (', '.join(f"{x['player']} {x['change']:+.1f}" for x in s.get('cascade', [])[:3]) or 'no teammate moves 0.5+'))
    if pos == 'QB' and (m.get('pass_att') or 0) < 30 and (proj or 0) >= 25:
        risks.append(f"starter on a thin passing sample ({m.get('pass_att')} attempts in 2026)")
    st_ev = out['ROLE_STATE']['starter_evidence']
    if st_ev in ('REPORTED_EXPECTED_STARTER', 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT', 'REPORTED_STARTER_UNVERIFIED'):
        risks.append(f'starter not confirmed by the club ({st_ev})')
    if conf:
        risks.append('chart and usage disagree on his rank')
    if t['accounting'].get('yards_closure_DIAGNOSTIC_NOT_A_GATE', {}).get('gap') and \
            abs(t['accounting']['yards_closure_DIAGNOSTIC_NOT_A_GATE']['gap']) / (t['accounting']['yards_closure_DIAGNOSTIC_NOT_A_GATE'].get('qbs_pass_yards') or 1) > 0.05:
        risks.append(f'{club} receiving and passing yards do not close inside the projection (yards props blocked)')
    simgap = (b.get('sim_mean') or 0) - (b.get('projection') or 0)
    if abs(simgap) >= SIM_GAP:
        risks.append(f'simulated mean differs from the projection by {simgap:+.1f} (touchdowns and bonuses as simulated, not rescaled)')
    if (m.get('games') or 0) < 3:
        risks.append(f"{m.get('games')} games measured in 2026")
    verdict = 'INPUT_DEFECT_FOUND' if defects else 'NEEDS_REVIEW' if review else \
        'SUPPORTED_WITH_UNCERTAINTY' if risks else 'SUPPORTED'
    why = '; '.join(defects + review + risks) or 'projection consistent with his measured role and held evidence'
    out.update(evidence=ev, RESEARCH_VERDICT=verdict, WHY=why, concerns=defects + review)
    return out


def build(slate, state_path=None):
    """`state_path`: an evidence-applied state (e.g. built write=False from the day's packet) whose starter and
    availability evidence is newer than the production state; projections are still read from production."""
    f = lambda n: OUT_DIR / f'DK_{slate}_EARLY_{n}'  # noqa: E731
    state, book, board, audit = (_j(f(n)) for n in ('STATE.json', 'RESEARCH_BOOK.json', 'OWNER_BOARD.json', 'AUDIT.json'))
    if state_path:
        state = _j(pathlib.Path(state_path))
    slots, scen = _j(f('HARD_ROCK_SLOTS.json')) or {'rows': []}, _j(f('SCENARIOS.json')) or {}
    if not all((state, book, board, audit)):
        return Outcome.fail('MATERIAL_RESEARCH_INPUT_MISSING', 'state, book, board and audit are required')
    mat = material_set(state, board, audit, slots, scen, _j(f('FC_DIFF.json')))
    if not mat:
        return Outcome.fail('MATERIAL_RESEARCH_EMPTY', 'no material player found -- the criteria matched nothing, which is not plausible')
    cards, teams = card_index(book)
    board_by = {p['dk_id']: p for p in board['players']}
    scen_by = {s['dk_id']: s for s in scen.get('scenarios', [])}
    rows = [judge(dk, w, state, cards, teams, board_by, audit, scen_by, audit.get('contradictions', [])) for dk, w in mat.items()]
    rows.sort(key=lambda r: ({'INPUT_DEFECT_FOUND': 0, 'NEEDS_REVIEW': 1, 'SUPPORTED_WITH_UNCERTAINTY': 2, 'SUPPORTED': 3}[r['RESEARCH_VERDICT']],
                             -(r['MODEL_PROJECTION'] or 0)))
    counts = {v: sum(1 for r in rows if r['RESEARCH_VERDICT'] == v)
              for v in ('SUPPORTED', 'SUPPORTED_WITH_UNCERTAINTY', 'NEEDS_REVIEW', 'INPUT_DEFECT_FOUND')}
    doc = {'ARTIFACT': 'CLASSIC_MATERIAL_RESEARCH', 'slate_id': slate, 'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'IS_NOT': 'a projection. No number here entered the model; a defect is fixed in the football state and regenerated.',
           'thresholds': {'MAX150': EXPO_150, 'MAX20': EXPO_20, 'opp_gap': [OPP_GAP_ABS, OPP_GAP_REL], 'sim_gap': SIM_GAP,
                          'SOURCE': 'exposure: owner 2026-10-04; review gaps: DECLARED reporting thresholds'},
           'external_items_pending': ['latest injury news', 'coaching comments', 'daily practice trend', 'current depth charts'],
           'state_used': str(state_path or f('STATE.json')), 'evidence_state': (state.get('official_inactives') or {}).get('STATE'),
           'n_material': len(rows), 'verdicts': counts, 'rows': rows}
    f('MATERIAL_RESEARCH.json').write_text(json.dumps(doc, indent=1, default=str))
    return Outcome.measured('MATERIAL_RESEARCH_BUILT', counts, n_measured=len(rows), what='material players',
                            detail=f"{len(rows)} material players: " + ', '.join(f'{k} {v}' for k, v in counts.items()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--state', default=None, help='an evidence-applied state to read availability and starters from')
    a = ap.parse_args()
    o = build(a.slate_id, a.state)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
