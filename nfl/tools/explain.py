#!/usr/bin/env python3.12
"""Why each projection is the number it is. Additive by construction, not by labelling.

THE OWNER CALLS THIS THE PRODUCT DIFFERENTIATOR, so it is built to a standard a sceptic can check
rather than a list of plausible-sounding contributions. The requirement was a decomposition like

    historical prior +X, current role +Y, recent usage +Z, teammate absence +A, team volume +B,
    opponent -C, weather -D, touchdowns/red zone +E, uncertainty W

HOW IT IS DONE, AND WHY THIS WAY. Attributing a number produced by a normalisation is not a matter
of reading off coefficients: a player's allocated share depends on every other player's claim, so
there is no linear coefficient to quote. So the projection is REBUILT under a nested sequence of
configurations, each adding exactly one thing, and each stage's contribution IS the change in DK
points it caused. The deltas therefore sum to the final projection exactly -- that is an identity,
not an approximation, and the artifact checks it per player rather than asserting it.

    S0  STRUCTURAL BASELINE   what the Nth man at your position gets on an average club, from the
                              measured depth curve and group split alone. No identity at all.
    S1  + WHO YOU ARE         your own multi-season prior replaces the structural claim
    S2  + WHAT YOU ARE DOING  the current season's measured usage enters at its declared weight
    S3  + ROLE STATE          the evidence ceiling, the duplicate-alpha demotion and the appearance
                              probability are applied
    S4  + YOUR CLUB           the club's own measured volume replaces the league average
    S5  + THE MARKET          the measured market response for this week's line

ORDER MATTERS AND IS DECLARED. A nested decomposition assigns shared credit to whichever stage comes
first, so the order is fixed, stated, and chosen to run from the least player-specific to the most
game-specific. It is not a Shapley value and does not claim to be.

WHAT IS NOT YET IN IT. Opponent strength and weather are not yet model inputs, so they carry no
contribution and are reported as NOT_MODELLED rather than as zero -- a zero would say the opponent
does not matter. Uncertainty needs a distribution, which arrives with the simulator; the field is
present and states that.
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'explain-1'

STAGES = (
    ('S0_STRUCTURAL_BASELINE', 'the Nth man at your position on an average club'),
    ('S1_PLAYER_HISTORY', 'your own multi-season prior'),
    ('S2_CURRENT_SEASON_USAGE', "this season's measured usage at its declared weight"),
    ('S3_ROLE_STATE_AND_APPEARANCE', 'evidence ceiling, duplicate-alpha demotion, P(appears)'),
    ('S4_CLUB_VOLUME', "the club's own measured volume instead of the league average"),
    ('S5_MARKET_RESPONSE', "the measured response to this week's line"),
)

NOT_MODELLED = {
    'opponent_adjustment': ('opponent strength is not yet a model input. Reported as NOT_MODELLED '
                            'rather than 0.0, because a zero would assert that the opponent does '
                            'not matter.'),
    'weather_adjustment': ('weather is carried in the warehouse and is not yet a projection input. '
                           'Same reasoning.'),
    'teammate_absence': ('the redistribution study measures this from history '
                         '(nfl/warehouse/REDISTRIBUTION_STUDY.json) and is not yet wired into the '
                         'projection, so no contribution is claimed for it.'),
}


def _league_mean_volume(tv_all):
    fields = collections.defaultdict(list)
    for t in tv_all.values():
        if t.get('state') != 'OK':
            continue
        for k, v in t.items():
            if k.startswith('proj_') and isinstance(v, (int, float)):
                fields[k].append(v)
    return {k: statistics.fmean(v) for k, v in fields.items() if v}


def decompose(rows_by_club, tv_all, depth, groups, prates, pass_share, td_pool_by_club,
              bonus, ip, V):
    """Rebuild every club under the nested stages. Returns {dk_id: decomposition}."""
    league = _league_mean_volume(tv_all)
    out = {}
    for club, crows in rows_by_club.items():
        tv_final = tv_all.get(club) or {}
        tv_league = dict(tv_final)
        for k, v in league.items():
            tv_league[k] = v
        # club volume with the market response removed: the pre-adjustment baseline
        tv_nomkt = dict(tv_final)
        for f, acct in (tv_final.get('market_response') or {}).items():
            if isinstance(acct, dict) and acct.get('baseline') is not None:
                tv_nomkt[f'proj_{f}'] = acct['baseline']

        configs = [
            ('S0_STRUCTURAL_BASELINE', {'blend': 0.0, 'claims': '_claims', 'tv': tv_league}),
            ('S1_PLAYER_HISTORY', {'blend': 1.0, 'claims': '_claims_prior_only', 'tv': tv_league}),
            ('S2_CURRENT_SEASON_USAGE', {'blend': 1.0, 'claims': '_claims_pre_role',
                                         'tv': tv_league}),
            ('S3_ROLE_STATE_AND_APPEARANCE', {'blend': 1.0, 'claims': '_claims', 'tv': tv_league}),
            ('S4_CLUB_VOLUME', {'blend': 1.0, 'claims': '_claims', 'tv': tv_nomkt}),
            ('S5_MARKET_RESPONSE', {'blend': 1.0, 'claims': '_claims', 'tv': tv_final}),
        ]
        prev = {}
        stage_points = collections.defaultdict(dict)
        for name, cfg in configs:
            work = []
            for r in crows:
                w = {'position': r['position'], 'role_band': r.get('role_band'),
                     'is_predicted_starter': r.get('is_predicted_starter'),
                     'efficiency': r.get('efficiency'), 'rz_intensity': r.get('rz_intensity'),
                     '_dk': r['dk_id']}
                src = r.get(cfg['claims']) or {}
                base = r.get('_claims') or {}
                w['_claims'] = {k: (src.get(k) if src.get(k) is not None else base.get(k))
                                for k in ('targets', 'carries', 'pass_attempts')}
                work.append(w)
            V.allocate_opportunity(work, cfg['tv'], depth, groups, blend=cfg['blend'])
            for w in work:
                V.finalize(w)
            pool = td_pool_by_club.get(club)
            if pool is not None and pass_share is not None:
                V.allocate_club_td(pool, pass_share, work, prates)
            for w in work:
                pts, items = V.dk_points(w, w.get('td'), bonus, ip)
                stage_points[w['_dk']][name] = pts
        for r in crows:
            pts = stage_points.get(r['dk_id']) or {}
            seq, running, deltas = [], None, {}
            for name, why in STAGES:
                v = pts.get(name)
                if v is None:
                    continue
                d = v if running is None else v - running
                deltas[name] = round(d, 4)
                seq.append({'stage': name, 'why': why, 'dk_points_after': round(v, 4),
                            'contribution': round(d, 4)})
                running = v
            final = running
            out[r['dk_id']] = {
                'name': r.get('name'), 'position': r.get('position'), 'team': club,
                'final_dk_points_from_decomposition': (round(final, 4) if final is not None
                                                       else None),
                'stages': seq, 'contributions': deltas,
                'line_items': r.get('dk_line_items'),
                'not_modelled': NOT_MODELLED,
                'uncertainty': ('NOT_AVAILABLE_UNTIL_SIMULATOR: a point projection carries no '
                                'interval. The distribution arrives with the joint game simulator.'),
                'ORDER_DECLARED': [n for n, _ in STAGES],
                'ORDER_MATTERS': ('a nested decomposition credits shared effect to whichever stage '
                                  'comes first. The order is fixed and runs least player-specific '
                                  'to most game-specific. This is not a Shapley value.'),
            }
    return out


def verify(decomp, rows):
    """The identity: stage contributions must sum to the projection they explain."""
    bad, checked = [], 0
    for dk, d in decomp.items():
        r = rows.get(dk) or {}
        actual = r.get('dk_points')
        got = d.get('final_dk_points_from_decomposition')
        if actual is None or got is None:
            continue
        checked += 1
        s = sum(d['contributions'].values())
        if abs(s - got) > 1e-6:
            bad.append({'name': d['name'], 'sum_of_contributions': round(s, 6),
                        'final_from_stages': got, 'reason': 'CONTRIBUTIONS_DO_NOT_SUM'})
        elif abs(got - actual) > 0.02:
            bad.append({'name': d['name'], 'final_from_stages': got,
                        'projection': actual, 'gap': round(got - actual, 4),
                        'reason': 'LAST_STAGE_DISAGREES_WITH_PROJECTION'})
    return {'n_checked': checked, 'n_violations': len(bad), 'violations': bad[:10],
            'IDENTITY': ('stage contributions sum to the final stage by construction; the final '
                         'stage must equal the projection it explains, or the decomposition is '
                         'explaining a different number from the one shipped.')}
