"""Build the POST-INACTIVES Early Only projection board from finished runs.

WHAT THIS IS

A reader, not a model. It opens the draw arrays a run actually wrote, computes
the summary statistics the owner asked for, and states per position whether a
real per-player distribution exists. It invents nothing and it fills nothing.

THE RULE IT ENFORCES, AND IT FAILS THE BOARD RATHER THAN REPAIRING IT

    A position is SUPPORTED only when PER-PLAYER draws exist for it.

Team-level totals are not player support. `team_volume` carrying
`team_targets` says how many targets a club throws; it says nothing about who
catches them. A board that counted that as WR support would be reporting a
denominator as a projection.

THE INACTIVE AUDIT IS A GATE, NOT A COLUMN

`assert_no_inactive_survived` returns FAIL, not a warning, if any officially
inactive gsis_id appears in a playable row. With no official inactive evidence
ingested the audit reports `NO_OFFICIAL_INACTIVE_EVIDENCE` and the board is
NOT certified inactive-clean -- an empty inactive list and a verified-empty
one are different facts, and collapsing them is how an unchecked board gets
called checked.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'postinactives-board-1'

#: Per-player layers. `team_volume` is deliberately absent: it is a club
#: quantity and counting it as player support is the defect above.
PLAYER_LAYERS = ('receiving', 'rushing', 'rushing_total', 'qb', 'kicking',
                 'dk_scoring', 'receiving_conversion', 'td', 'targets_carries')

PCTS = (5, 10, 25, 50, 75, 90, 95)


def _open(run_dir: pathlib.Path):
    for n in ('player_draws.npz', 'player_draws.npz.gz'):
        p = run_dir / n
        if p.exists():
            return np.load(p)
    return None


def _vec(z, layer, metric):
    """The draw array, trying both spellings the two files use."""
    for k in (f'{layer}__{metric}', f'{layer}/{metric}'):
        if k in getattr(z, 'files', []):
            return z[k]
    return None


def read_run(run_dir) -> dict:
    """One finished run -> per-player rows, measured from the arrays."""
    run_dir = pathlib.Path(run_dir)
    mf = run_dir / 'player_draws_manifest.json'
    st = run_dir / 'run_status.json'
    if not mf.exists():
        return {'run_dir': str(run_dir), 'state': 'NO_MANIFEST'}
    m = json.loads(mf.read_text())
    s = json.loads(st.read_text()) if st.exists() else {}
    z = _open(run_dir)
    n_draws = int(m.get('n_draws') or 0)

    by_pid = collections.defaultdict(dict)
    layers_seen, player_layers_seen = [], []
    for lname, layer in sorted((m.get('layers') or {}).items()):
        layers_seen.append(lname)
        if layer.get('row_axis') != 'gsis_id':
            continue
        if lname not in PLAYER_LAYERS:
            continue
        ids = layer.get('row_ids') or []
        got_any = False
        for metric in (layer.get('metrics') or []):
            arr = _vec(z, lname, metric) if z is not None else None
            if arr is None:
                continue
            a = np.asarray(arr)
            for i, pid in enumerate(ids):
                if i >= a.shape[0]:
                    continue
                v = np.asarray(a[i], float)
                if v.size != n_draws or not np.isfinite(v).all():
                    continue
                got_any = True
                by_pid[pid][f'{lname}/{metric}'] = v
        if got_any:
            player_layers_seen.append(lname)
    return {
        'run_dir': str(run_dir),
        'run_id': s.get('run_id') or m.get('run_id'),
        'game_id': m.get('game_id'),
        'status': s.get('status'),
        'n_draws': n_draws,
        'seed': s.get('seed'),
        'written_at': s.get('written_at'),
        'model_configuration': (s.get('qb3_configuration') or {}).get('mode')
        or s.get('model_configuration'),
        'execution_identity': s.get('execution_identity'),
        'code_commit': s.get('code_commit'),
        'dry_run': s.get('dry_run'),
        'content_digest': (s.get('draw_artifact') or {}).get('content_digest'),
        'layers_in_manifest': layers_seen,
        'player_layers_with_readable_draws': player_layers_seen,
        'first_failure': (s.get('first_failure') or {}).get('stage'),
        '_by_pid': by_pid,
    }


def summarise(v: np.ndarray) -> dict:
    q = np.percentile(v, PCTS)
    return {'mean': round(float(v.mean()), 4),
            'median': round(float(np.median(v)), 4),
            'sd': round(float(v.std(ddof=1)) if v.size > 1 else 0.0, 4),
            **{f'p{p}': round(float(x), 4) for p, x in zip(PCTS, q)},
            'p_zero': round(float((v == 0).mean()), 4),
            'n_draws': int(v.size)}


def position_support(rows, universe_by_pid) -> dict:
    """Per position: does a PER-PLAYER distribution exist? Measured."""
    out = {}
    for pos in ('QB', 'RB', 'WR', 'TE', 'K', 'DST'):
        have = [r for r in rows if r.get('position') == pos
                and r.get('dk_points_mean') is not None]
        n_uni = sum(1 for p in universe_by_pid.values()
                    if p.get('position') == pos)
        out[pos] = {
            'n_in_universe': n_uni,
            'n_with_player_distribution': len(have),
            'supported': bool(have),
            'why_not': None if have else (
                'no per-player draw array exists for this position in any '
                'run; team-level totals are not player support'),
        }
    return out


def assert_no_inactive_survived(rows, inactive_ids, evidence) -> Outcome:
    """A GATE. Fails the board; never silently drops a row.

    With no official inactive evidence this returns BLOCKED, not PASS. An
    empty inactive list and a verified-empty one are different facts.
    """
    if not evidence:
        return Outcome.blocked(
            'NO_OFFICIAL_INACTIVE_EVIDENCE',
            'no official game-day inactive declaration was ingested for any '
            'game, so the board CANNOT be certified inactive-clean. This is '
            'not the same as having verified that no inactive player is '
            'present.', cause=Cause.DATA, n_rows=len(rows))
    survivors = [r for r in rows
                 if r.get('gsis_id') in set(inactive_ids)
                 and r.get('dk_points_mean') is not None]
    if survivors:
        return Outcome.fail(
            'OFFICIALLY_INACTIVE_PLAYER_IN_PLAYABLE_BOARD', Cause.DATA,
            f'{len(survivors)} officially inactive player(s) carry a playable '
            f'projection. Publication is refused.',
            survivors=[{'gsis_id': r['gsis_id'], 'player': r.get('player')}
                       for r in survivors])
    return Outcome.ok('0_OFFICIALLY_INACTIVE_PLAYERS_IN_FINAL_PLAYABLE_BOARD',
                      value={'n_inactive_checked': len(set(inactive_ids)),
                             'n_rows': len(rows)})
