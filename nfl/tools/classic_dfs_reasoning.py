"""Why each materially used player is in the portfolio, and which stacks it actually built -- in football.

The owner's rule (football_intelligence_graph, 2026-10-03): never "the optimiser liked him". Every
reason below is a fact read from the research book (role, volume, injury cascade, efficiency) or from
the joint worlds (ceiling, correlation with his quarterback). A player with exposure but no football
reason found is listed under UNEXPLAINED, which is a finding to investigate, not a gap to paper over.
"""
from __future__ import annotations

import collections

import numpy as np

#: exposure at or above this in any contest is "material" (DECLARED reporting threshold)
MATERIAL_EXPOSURE = 0.10


def _cards(book):
    out = {}
    for gid, g in book['games'].items():
        for club, t in g['teams'].items():
            for c in t['players']:
                out[c['dk_id']] = (gid, club, t, c)
    return out


def reasons(book, port, draws):
    cards = _cards(book)
    by_pos = collections.defaultdict(list)
    for dk, (_g, _c, _t, c) in cards.items():
        d = c['projection'].get('distribution') or {}
        if d.get('dk_mean') is not None and c['salary']:
            by_pos[c['position']].append((dk, d['dk_mean'] / (c['salary'] / 1000), d.get('p90') or 0))
    value_rank, ceil_rank = {}, {}
    for pos, lst in by_pos.items():
        for i, (dk, _v, _c) in enumerate(sorted(lst, key=lambda t: -t[1]), 1):
            value_rank[dk] = (i, len(lst))
        for i, (dk, _v, _c) in enumerate(sorted(lst, key=lambda t: -t[2]), 1):
            ceil_rank[dk] = (i, len(lst))
    beneficiaries = collections.defaultdict(list)
    for g in book['games'].values():
        for club, t in g['teams'].items():
            for cas in t['injury_cascades']:
                v = cas.get('vacated_per_game_2026') or {}
                # only an absence that vacates real volume is named, and never as a cause: the
                # cascade is projection minus 2026 per-game usage, which also moves for a player
                # returning from his own absence
                if not ((v.get('targets') or 0) >= 3 or (v.get('carries') or 0) >= 5 or (v.get('pass_att') or 0) >= 10):
                    continue
                for w in cas.get('who_the_projection_gives_more_to') or []:
                    beneficiaries[(club, w['name'])].append(f"{cas['player']} ({cas['position']})")
    expo = collections.defaultdict(dict)
    lus = {}
    for con in port['contests']:
        for _n, e in con['report']['player_exposure'].items():
            expo[e['dk_id']][con['profile']] = e['overall']
        lus[con['profile']] = [[s['dk_id'] for s in lu['slots']] for lu in con['lineups']]
    players, unexplained = [], []
    for dk, ex in expo.items():
        if max(ex.values()) < MATERIAL_EXPOSURE or dk not in cards:
            continue
        gid, club, t, c = cards[dk]
        pr, m = c['projection'], c['measured_2026']
        why, risk = [], []
        for r in c.get('role_types') or []:
            why.append(r)
        tv = t['environment']
        if c['position'] in ('WR', 'TE', 'RB') and pr.get('targets') and tv.get('proj_targets'):
            sh = pr['targets'] / tv['proj_targets']
            if sh >= 0.18:
                why.append(f"concentrated targets: {pr['targets']:.1f} projected, {sh:.0%} of the club")
        if c['position'] == 'RB' and pr.get('carries') and tv.get('proj_rush_attempts'):
            sh = pr['carries'] / tv['proj_rush_attempts']
            if sh >= 0.5:
                why.append(f"workhorse carries: {pr['carries']:.1f} projected, {sh:.0%} of the club")
        if c['position'] == 'QB' and pr.get('pass_attempts'):
            why.append(f"{pr['pass_attempts']:.1f} projected attempts, {pr.get('carries') or 0:.1f} carries")
        if (m.get('gl_carries') or 0) >= 2:
            why.append(f"goal-line work: {m['gl_carries']} carries inside the 5 in 2026")
        if (m.get('rz_targets') or 0) >= 3:
            why.append(f"red-zone targets: {m['rz_targets']} in 2026")
        vr, cr = value_rank.get(dk), ceil_rank.get(dk)
        if vr and vr[0] <= max(3, vr[1] // 10):
            why.append(f"salary efficiency: #{vr[0]} of {vr[1]} {c['position']} in projected points per $1k")
        if cr and cr[0] <= max(3, cr[1] // 10):
            why.append(f"ceiling: #{cr[0]} of {cr[1]} {c['position']} at the 90th percentile")
        for b in beneficiaries.get((club, c['name']), []):
            why.append(f'opportunity with {b} out: projected above his 2026 per-game volume '
                       f'(the gap is described, not attributed)')
        qb = (t.get('qb_ecosystem') or {}).get('quarterback')
        if c['position'] in ('WR', 'TE', 'RB') and qb:
            qcard = next((x for x in t['players'] if x['name'] == qb), None)
            r = next((x['r'] for x in t.get('qb_correlations') or [] if x['with'] == c['name']), None)
            if qcard:
                shared = [sum(1 for lu in L if dk in lu and qcard['dk_id'] in lu) / max(1, sum(1 for lu in L if dk in lu))
                          for L in lus.values() if any(dk in lu for lu in L)]
                if shared and max(shared) >= 0.4 and r is not None:
                    why.append(f"game-stack synergy: paired with {qb} in up to {max(shared):.0%} of his lineups (joint-sim r = {r})")
        if c['uncertainty']['conflicts']:
            risk.extend(c['uncertainty']['conflicts'])
        if c['uncertainty']['role_confidence'] in ('LOW', None):
            risk.append(f"thin prior ({c['uncertainty']['prior_tier']})")
        if c['status']['designation'] in ('QUESTIONABLE', 'DOUBTFUL'):
            risk.append(f"designated {c['status']['designation']}")
        row = {'player': c['name'], 'team': club, 'position': c['position'], 'salary': c['salary'],
               'exposure': ex, 'why': why, 'risk': risk or ['none recorded']}
        (players if why else unexplained).append(row)
    players.sort(key=lambda r: -max(r['exposure'].values()))
    # ------------------------------------------------------------------ stack reasoning
    role_of = {}
    for dk, (_g, club, t, c) in cards.items():
        tree = (t.get('qb_ecosystem') or {}).get('target_tree') or []
        names = [x['name'] for x in tree]
        if c['position'] in ('WR', 'TE', 'RB') and c['name'] in names:
            k = [x for x in tree if x['pos'] == c['position']]
            idx = [x['name'] for x in k].index(c['name']) + 1 if c['name'] in [x['name'] for x in k] else None
            role_of[dk] = f"{c['position']}{idx}" if idx else c['position']
    stacks = {}
    for con in port['contests']:
        cnt = collections.Counter()
        for lu in con['lineups']:
            ids = [s['dk_id'] for s in lu['slots']]
            qb = next((d for d in ids if cards.get(d, (0, 0, 0, {}))[3].get('position') == 'QB'), None)
            if not qb:
                continue
            club = cards[qb][1]
            mates = sorted(role_of.get(d, '?') for d in ids if d != qb and cards.get(d, (0, None))[1] == club
                           and cards[d][3]['position'] in ('WR', 'TE', 'RB'))
            cnt['QB + ' + (' + '.join(mates) if mates else 'no pass catcher')] += 1
        n = len(con['lineups']) or 1
        stacks[con['profile']] = [{'shape': k, 'share': round(v / n, 3)} for k, v in cnt.most_common(8)]
    pair_r = []
    for g in book['games'].values():
        for club, t in g['teams'].items():
            for x in (t.get('qb_correlations') or [])[:3]:
                pair_r.append({'qb_team': club, 'qb': (t.get('qb_ecosystem') or {}).get('quarterback'),
                               'with': x['with'], 'pos': x['pos'], 'r': x['r']})
    return {'MATERIAL_EXPOSURE': MATERIAL_EXPOSURE, 'players': players, 'UNEXPLAINED': unexplained,
            'stack_shapes': stacks, 'strongest_qb_pairs_joint_sim': sorted(pair_r, key=lambda x: -x['r'])[:16],
            'ROLE_LABELS': 'WR1/WR2/TE1/RB1 are ranks by projected targets inside the club, from the research book'}
