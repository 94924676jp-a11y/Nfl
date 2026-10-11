#!/usr/bin/env python3.12
"""Participation in the simulated worlds: a player on the injury report plays a DRAWN share of his role, and the share he
does not play goes to his teammates the way the projection engine itself reallocates an absent player's work.

Task #45 P1-3 (owner contract 2026-10-11). Used only by the declared CORRECTED_V1 arm (nfl/tools/classic_slate_run.py);
the incumbent arm never imports it.

WHAT IS MEASURED AND WHAT IS DECLARED

  P(no participation)   PM-1's frozen table (nfl/research/participation_pm1/PM1_TABLE.json), held-out verdict
                        SHADOW-CONTINUE. Used ONLY while game-day status is unresolved. A player the evidence resolves
                        ACTIVE gets 0: the declared assumption of PREREG_PM2 section 2, printed in every account.
  phi                   PM-3's participation factor (PM3_PHI.json): the share of his normal role he keeps when he
                        plays, net of ordinary week-to-week dispersion (which the simulator already draws). No held-out
                        evidence yet; prospective only.
  role band             PM-3's strata are by baseline snap share r0, which 2026 data cannot give before the season ends.
                        DECLARED mapping from the projection's own role band: ALPHA/PRIMARY -> R_GE_070, SECONDARY ->
                        R_040_070, ROTATIONAL/FRINGE -> R_LT_040, none -> NO_BASELINE. Unvalidated; printed.
  redistribution        NOT a fantasy-point transfer. For each designated player the projection engine is re-run with
                        him absent (role state -> proj_v1, the same code an inactive takes). The share he frees in a
                        world goes to each teammate in proportion to that teammate's share gain in the absent
                        projection, field by field (targets, carries, pass attempts, TD shares). Gains below zero are
                        clamped at zero and the rest renormalised (declared).
  team volume           a club whose position LEADER is limited moves its pass rate by the measured association
                        nfl/warehouse/REDISTRIBUTION_STUDY.json (leader absent vs present, same club and season;
                        WR -0.027, TE -0.023, RB +0.002 pass-rate points; ASSOCIATION_NOT_CAUSE), drawn per world from
                        N(mean, se) and scaled by (1 - phi). Plays are held, pass share moves. A non-leader moves nothing.

Nothing here chooses a number to make a forecast look right; each choice above is declared and carried into the artifact.
"""
from __future__ import annotations

import json
import pathlib
import random

_REPO = pathlib.Path(__file__).resolve().parents[2]
PM_DIR = _REPO / 'nfl/research/participation_pm1'
STUDY = _REPO / 'nfl/warehouse/REDISTRIBUTION_STUDY.json'
SPEC_VERSION = 'participation-worlds-1'

ROLE_BAND = {'ALPHA': 'R_GE_070', 'PRIMARY': 'R_GE_070', 'SECONDARY': 'R_040_070', 'ROTATIONAL': 'R_LT_040',
             'FRINGE': 'R_LT_040'}
POS_GROUP = {'QB': 'QB', 'RB': 'RB', 'WR': 'WR_TE', 'TE': 'WR_TE'}
PRACTICE = (('Did Not Participate', 'DID_NOT_PARTICIPATE'), ('Limited', 'LIMITED'), ('Full', 'FULL'))
SOFT = ('hamstring', 'groin', 'calf', 'quad', 'thigh')
SHARE_FIELDS = ('target_share', 'carry_share', 'pass_att_share', 'pass_td_share', 'rush_td_share')
LEADER_MEASURE = {'WR': 'WR', 'TE': 'TE', 'RB': 'RB'}


def load():
    t1 = json.loads((PM_DIR / 'PM1_TABLE.json').read_text())
    t3 = json.loads((PM_DIR / 'PM3_PHI.json').read_text())
    st = json.loads(STUDY.read_text())['by_position']
    return {'pm1': t1, 'pm3': t3, 'study': st}


def classify(player: dict, proj_row: dict):
    """The PM unit for a designated, not-absent skill player, or None when he is not on the report."""
    pos = POS_GROUP.get(player.get('position'))
    if pos is None:
        return None
    av = player.get('current_availability') or {}
    d = av.get('designation')
    pr_txt = av.get('practice_status') or ''
    practice = next((v for k, v in PRACTICE if k in pr_txt), 'NONE_RECORDED')
    if d in ('QUESTIONABLE', 'DOUBTFUL'):
        desig = d
    elif practice in ('LIMITED', 'DID_NOT_PARTICIPATE'):
        desig = 'NONE_WITH_LIMITED_OR_DNP_PRACTICE'
    else:
        return None
    inj = f"{av.get('injury') or ''} {av.get('injury_secondary') or ''}".lower()
    res = av.get('resolution') or {}
    return {'desig': desig, 'practice': practice, 'pos': pos,
            'inj': 'SOFT_TISSUE_LOWER' if any(k in inj for k in SOFT) else 'OTHER',
            'role': ROLE_BAND.get((proj_row or {}).get('role_band'), 'NO_BASELINE'),
            'resolved_active': res.get('claim') == 'ACTIVE',
            'reported_expectation': (res.get('participation') or {}).get('expectation')}


def _lookup(cells, unit, levels):
    for lv in levels:
        k = '|'.join(unit[x] for x in lv.split('|'))
        c = cells.get(k)
        if c is not None:
            return k, c
    return None, None


def spec(unit: dict, tables: dict) -> dict:
    """P(no participation) and the phi quantile grid for one unit, with where each came from."""
    k1, c1 = _lookup(tables['pm1']['cells'], unit, tables['pm1']['levels'])
    k3, c3 = _lookup(tables['pm3']['cells'], unit, tables['pm3']['levels'])
    if unit['resolved_active']:
        p0, p0_basis = 0.0, 'RESOLVED_ACTIVE: declared 0 (PREREG_PM2 s.2, untestable without game-day rosters)'
    else:
        p0 = (c1 or {}).get('p_no_participation')
        p0_basis = f'PM-1 cell {k1}' if c1 else 'NO_PM1_CELL'
    return {'unit': unit, 'p_no_participation': p0 if p0 is not None else 0.0, 'p_no_participation_basis': p0_basis,
            'phi_quantiles': (c3 or {}).get('phi_quantiles'), 'phi_cell': k3,
            'phi_basis': f'PM-3 cell {k3} (n_r {c3["n_r"]})' if c3 else 'NO_PM3_CELL: phi = 1 (declared)',
            'LIMITATIONS': ['P(no participation) mixes role (PM1_RESULT.md)',
                            'role band mapped from the projection, not measured snap share',
                            'a reported "limited snaps" statement is not separately modelled beyond its practice '
                            'status and designation']}


def draw_phi(sp: dict, n: int, rng: random.Random) -> list:
    """Per-world participation factor: 0 with P(no participation), else phi(u) on PM-3's grid (linear interpolation)."""
    q = sp.get('phi_quantiles')
    p0 = sp['p_no_participation']
    out = []
    for _ in range(n):
        if rng.random() < p0:
            out.append(0.0)
            continue
        if not q:
            out.append(1.0)
            continue
        u = rng.random() * (len(q) - 1)
        i = int(u)
        f = u - i
        out.append(q[i] if i + 1 >= len(q) else q[i] * (1 - f) + q[i + 1] * f)
    return out


def redistribution(present: list, absent: list, k: int) -> dict:
    """{field: weights over present-list indices}: where player k's freed share of each field goes.

    present / absent: showdown_draws._shares-style lists for one club, matched by 'id'. The absent list lacks k."""
    ab = {p['id']: p for p in absent}
    red = {}
    for f in SHARE_FIELDS:
        gains = []
        for i, p in enumerate(present):
            if i == k:
                gains.append(0.0)
                continue
            a = ab.get(p['id'])
            gains.append(max(0.0, (a.get(f, 0.0) if a else 0.0) - p.get(f, 0.0)))
        s = sum(gains)
        red[f] = [g / s for g in gains] if s > 0 else None   # None: nobody gains -> the freed share stays unallocated
    return red


def leader_pass_rate(tables, club_players: list, k: int):
    """(mean, se) of the club pass-rate change when player k, his club's position leader, is out; else None."""
    p = club_players[k]
    m = LEADER_MEASURE.get(p['position'])
    if m is None:
        return None
    field = 'carry_share' if p['position'] == 'RB' else 'target_share'
    same = [q for q in club_players if q['position'] == p['position']]
    if not same or max(same, key=lambda q: q.get(field, 0.0)) is not p:
        return None
    cr = (tables['study'].get(m) or {}).get('club_response', {}).get('pass_rate_change') or {}
    if cr.get('mean') is None or cr.get('se') is None:
        return None
    return float(cr['mean']), float(cr['se'])


def effective_shares(players: list, entries: list, w: int) -> list:
    """The club's share lists for world w after every designated player's participation is applied.

    entries: [{'idx', 'phi' (per world), 'red' (per field)}]. Players with phi = 0 in this world end with exactly 0 in
    every field: their own share and anything redistributed to them by another entry is passed on."""
    S = {f: [p.get(f, 0.0) for p in players] for f in SHARE_FIELDS}
    zero = set()
    for e in entries:
        phi = e['phi'][w % len(e['phi'])]
        if phi <= 0.0:
            zero.add(e['idx'])
    for e in entries:
        k, phi = e['idx'], e['phi'][w % len(e['phi'])]
        if phi >= 1.0:
            continue
        for f in SHARE_FIELDS:
            freed = (1.0 - phi) * S[f][k]
            if freed <= 0:
                continue
            S[f][k] -= freed
            red = e['red'][f]
            if red is None:
                continue
            live = [i for i, r in enumerate(red) if r > 0 and i not in zero]
            tot = sum(red[i] for i in live)
            if tot <= 0:
                continue
            for i in live:
                S[f][i] += freed * red[i] / tot
    for i in zero:
        for f in SHARE_FIELDS:
            S[f][i] = 0.0
    out = []
    for i, p in enumerate(players):
        q = dict(p)
        for f in SHARE_FIELDS:
            q[f] = S[f][i]
        out.append(q)
    return out

