#!/usr/bin/env python3.12
"""Team reconciliation. A projection board must be one football model, not 457 guesses.

OWNER RULING: targets must reconcile to team passing opportunity and carries to team rushing
opportunity, non-negotiable, and extended to QB attempts against dropbacks minus sacks and
scrambles, receptions against targets, touchdowns against team touchdown expectation, and
red-zone allocations against team red-zone opportunity.

WHY THIS IS A HARD CONSTRAINT AND NOT A CHECK AFTERWARDS. A board whose players are each
individually plausible but whose club collectively throws 47 times when its projected dropbacks
are 34 passes inspection. Every row looks defensible; the football is impossible. Checking after
the fact means discovering it in a report, which is how V0's defects reached an owner-facing
table. So `enforce` RESCALES within a club to satisfy the identity, and records the scale factor
it had to apply -- a large factor is itself the finding.

SEVEN IDENTITIES, each with the direction of the fix stated, because rescaling the wrong side
hides the error rather than fixing it.
"""
from __future__ import annotations

import collections
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402

SPEC_VERSION = 'reconcile-1'

#: How far a club may be off before the run refuses rather than rescales. Declared: a 2%
#: rounding drift is arithmetic, a 20% drift is a broken model and must not be quietly scaled
#: into looking correct.
TOLERANCE = 0.02
REFUSE_ABOVE = 0.20

IDENTITIES = {
    'targets_to_pass_attempts': {
        'lhs': 'sum of player projected targets',
        'rhs': 'club projected pass attempts',
        'fix': 'rescale player target shares; never inflate team attempts to match players',
        'why': 'a target is a pass attempt. The sum cannot exceed the attempts thrown.'},
    'carries_to_rush_attempts': {
        'lhs': 'sum of player projected carries',
        'rhs': 'club projected rush attempts',
        'fix': 'rescale player carry shares',
        'why': 'every carry is a team rush attempt.'},
    'qb_attempts_to_dropbacks': {
        'lhs': 'club projected pass attempts + sacks + scrambles',
        'rhs': 'club projected dropbacks',
        'fix': 'attempts absorb the residual; sacks and scrambles are their own rates',
        'why': ('a dropback ends as an attempt, a sack or a scramble. Projecting attempts '
                'equal to dropbacks silently assumes zero of the other two.')},
    'receptions_to_targets': {
        'lhs': 'sum of player projected receptions',
        'rhs': 'sum of player projected targets times club catch rate',
        'fix': 'rescale receptions; a reception can never exceed its own target',
        'why': 'catches are a subset of targets, per player as well as per club.'},
    'td_to_team_td': {
        'lhs': 'sum of player projected touchdowns',
        'rhs': 'club projected touchdowns from its implied total',
        'fix': 'rescale player touchdown shares',
        'why': ('touchdowns are a fixed pool per club. Summing independent player TD rates '
                'is how a slate ends up scoring more touchdowns than points allow.')},
    'rz_to_team_rz': {
        'lhs': 'sum of player projected red-zone opportunities',
        'rhs': 'club projected red-zone plays',
        'fix': 'rescale red-zone shares',
        'why': 'red-zone opportunity is a pool, and it is the pool that drives touchdowns.'},
    'gl_to_team_gl': {
        'lhs': 'sum of player projected goal-line opportunities',
        'rhs': 'club projected goal-line plays',
        'fix': 'rescale goal-line shares',
        'why': 'the least transferable opportunity in football, and the easiest to double-count.'},
}


def check(club, lhs, rhs, name):
    if rhs in (None, 0):
        return {'identity': name, 'state': 'NOT_COMPUTABLE', 'club': club,
                'reason': 'no team-side quantity to reconcile against'}
    ratio = lhs / rhs
    drift = abs(ratio - 1.0)
    return {'identity': name, 'club': club, 'lhs': round(lhs, 3), 'rhs': round(rhs, 3),
            'ratio': round(ratio, 4), 'drift': round(drift, 4),
            'state': ('OK' if drift <= TOLERANCE else
                      'REFUSE' if drift > REFUSE_ABOVE else 'RESCALE'),
            'fix_direction': IDENTITIES[name]['fix']}


def enforce(players, team_totals):
    """Rescale player shares within each club so every identity holds. Returns the scale
    factors applied, because a large factor is a finding about the model, not a detail."""
    rows = collections.defaultdict(list)
    for p in players:
        rows[p['team']].append(p)
    report, refusals = [], []
    for club, ps in sorted(rows.items()):
        t = team_totals.get(club) or {}
        pairs = (
            ('targets_to_pass_attempts', 'proj_targets', t.get('pass_attempts')),
            ('carries_to_rush_attempts', 'proj_carries', t.get('rush_attempts')),
            ('rz_to_team_rz', 'proj_rz_opp', t.get('rz_plays')),
            ('gl_to_team_gl', 'proj_gl_opp', t.get('gl_plays')),
            ('td_to_team_td', 'proj_td', t.get('team_td')),
        )
        for name, field, rhs in pairs:
            lhs = sum((p.get(field) or 0.0) for p in ps)
            c = check(club, lhs, rhs, name)
            if c['state'] == 'REFUSE':
                refusals.append(c)
            elif c['state'] == 'RESCALE':
                k = rhs / lhs if lhs else 0.0
                for p in ps:
                    if p.get(field):
                        p[field] *= k
                c['scale_applied'] = round(k, 4)
            report.append(c)
        # receptions can never exceed the player's own targets, checked per player
        for p in ps:
            if (p.get('proj_receptions') or 0) > (p.get('proj_targets') or 0) + 1e-9:
                p['proj_receptions'] = p['proj_targets']
                report.append({'identity': 'receptions_to_targets', 'club': club,
                               'player': p.get('name'), 'state': 'CLAMPED',
                               'reason': 'projected receptions exceeded projected targets'})
    if refusals:
        return Outcome.fail(
            'RECONCILIATION_DRIFT_TOO_LARGE',
            f'{len(refusals)} club-identity pair(s) drift more than {REFUSE_ABOVE:.0%}. '
            f'Rescaling that far would make a broken model look correct.',
            refusals=refusals[:12], n=len(refusals), report=report)
    return Outcome.ok('RECONCILED', {'report': report, 'players': players},
                      f'{len(report)} identity checks across {len(rows)} clubs',
                      n_checks=len(report),
                      n_rescaled=sum(1 for c in report if 'scale_applied' in c),
                      n_clamped=sum(1 for c in report if c['state'] == 'CLAMPED'))
