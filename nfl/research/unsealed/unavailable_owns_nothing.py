"""No player the run itself declared unavailable may own football mass.

WHY THIS EXISTS

The engine has a removal path: `run_forecast` drops players whose availability
is a TERMINAL state before the allocation layers run, and records who it
removed and on what evidence. The path is guarded by a candidate flag, depends
on a name-keyed join against a feed that carries no gsis_id, and its comments
record two occasions on which it silently removed nobody -- once when every
one of 108 players resolved to UNRESOLVED_IDENTITY, and once when a back was
allocated 4.1 carries in a week the feed listed him OUT.

Each time the repair was made at the point of failure. This check is different
in kind: it does not care WHY the removal failed. It reads the finished draws
against the run's own truth snapshot and asks whether any player that snapshot
calls unavailable nevertheless holds opportunity. A check written against the
output cannot be defeated by a new way of failing upstream.

WHAT IT COMPARES, AND WHY THAT IS THE HONEST PAIRING

The truth snapshot is the run's OWN record of what it believed at execution
time, so this is not scoring the engine against hindsight or against a feed
it never saw. If the snapshot says OUT and the draws give him carries, the run
contradicted itself, and that is true regardless of whether the designation
was correct.

ONLY TERMINAL STATES ACT. DOUBTFUL and QUESTIONABLE are probabilistic and
deliberately move nobody -- turning a probability into a certainty because
the word sounds bad is the fabrication this project forbids. UNKNOWN is not
evidence of anything and is not treated as either. A player absent from the
snapshot is reported separately rather than assumed available.
"""
from __future__ import annotations

import numpy as np

SPEC_VERSION = 'unavailable-owns-nothing/1.0.0'

#: Designations that mean the player does not take the field. Only these act.
TERMINAL = frozenset({
    'OUT', 'INACTIVE_OFFICIAL', 'OFFICIAL_GAMEDAY_INACTIVE',
    'INJURED_RESERVE', 'IR', 'PUP', 'NFI', 'SUSPENDED',
})

#: Explicitly NOT terminal, listed so a reader can see the decision was made.
PROBABILISTIC = frozenset({'DOUBTFUL', 'QUESTIONABLE'})

#: Layer -> opportunity metrics. Outcomes are excluded on purpose: a back who
#: carries for no gain still took the carry, and a check keyed on yards would
#: miss exactly the case it is for.
OPPORTUNITY = {
    'qb': ('att', 'db'),
    'receiving': ('targets',),
    'rushing': ('carries',),
    'kicking': ('fga', 'xpa'),
    'gadget_rush': ('te', 'wr'),
}


class InvariantError(RuntimeError):
    """The check cannot be run at all. Distinct from the check failing."""


def declared_unavailable(truth: dict) -> dict[str, dict]:
    """gsis_id -> record, for players the snapshot gives a TERMINAL state."""
    players = truth.get('players')
    if not players:
        raise InvariantError(
            'the truth snapshot carries no players, so this check would pass '
            'vacuously. An empty input is not a clean result.')
    out = {}
    for p in players:
        state = str(p.get('availability') or '').upper()
        if state in TERMINAL:
            out[p['gsis_id']] = {
                'name': p.get('full_name'), 'team': p.get('team'),
                'position': p.get('position'), 'availability': state,
                'report_status_raw': p.get('report_status_raw'),
                'basis': p.get('availability_basis'),
            }
    return out


def violations(arrays: dict, layers: dict, truth: dict) -> list[dict]:
    """Every terminal-state player holding opportunity, with where and how much."""
    unavailable = declared_unavailable(truth)
    found = []
    for gsis_id, rec in sorted(unavailable.items()):
        holds = []
        for layer, metrics in OPPORTUNITY.items():
            spec = layers.get(layer)
            if not spec or gsis_id not in (spec.get('row_ids') or ()):
                continue
            i = list(spec['row_ids']).index(gsis_id)
            for metric in metrics:
                arr = arrays.get(f'{layer}__{metric}')
                if arr is None:
                    continue
                row = np.asarray(arr[i], dtype=float)
                share = float((row > 0).mean())
                if share > 0:
                    holds.append({
                        'layer': layer, 'metric': metric,
                        'p_nonzero': share,
                        'mean': float(row.mean()),
                        'max': float(row.max()),
                    })
        if holds:
            found.append({**rec, 'gsis_id': gsis_id, 'holds': holds})
    return found


def check(arrays: dict, layers: dict, truth: dict) -> dict:
    """Run the invariant. Returns a verdict; never raises on a violation."""
    unavailable = declared_unavailable(truth)
    bad = violations(arrays, layers, truth)
    verdict = {
        'spec_version': SPEC_VERSION,
        'n_declared_unavailable': len(unavailable),
        'n_violating': len(bad),
        'violations': bad,
        'terminal_states_considered': sorted(TERMINAL),
        'states_deliberately_not_acting': sorted(PROBABILISTIC),
    }
    if not unavailable:
        verdict['state'] = 'NOT_APPLICABLE'
        verdict['code'] = 'NO_PLAYER_DECLARED_UNAVAILABLE'
        verdict['detail'] = (
            'the snapshot declares nobody terminal, so there is nothing for '
            'this check to catch. That is NOT the same as the removal path '
            'having worked, and must not be read as a pass.')
    elif bad:
        worst = max(
            (h['p_nonzero'] for v in bad for h in v['holds']), default=0.0)
        verdict['state'] = 'FAIL'
        verdict['code'] = 'UNAVAILABLE_PLAYER_OWNS_OPPORTUNITY'
        verdict['detail'] = (
            f'{len(bad)} of {len(unavailable)} player(s) the run itself '
            f'declared unavailable hold non-zero opportunity in the draws; '
            f'the largest share is {worst:.3f} of draws. The run contradicts '
            f'its own truth snapshot.')
    else:
        verdict['state'] = 'PASS'
        verdict['code'] = 'UNAVAILABLE_OWN_NOTHING'
        verdict['detail'] = (
            f'all {len(unavailable)} player(s) declared unavailable hold zero '
            f'opportunity in every layer checked.')
    return verdict
