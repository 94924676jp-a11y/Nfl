#!/usr/bin/env python3.12
"""Distributional summaries from a sealed-format draw artifact. RESEARCH ONLY.

    python3.12 nfl/research/unsealed/summarise_draws.py --run-dir <dir> \
        --out <SUMMARY.json>

WHAT THIS MAY AND MAY NOT CLAIM

The run that produced these draws executed every football stage and then
FAILED artifact sealing on a hard invariant. So the numbers below are real
simulated quantities and are NOT a sealed forecast. Every output carries
`output_class: UNSEALED_RESEARCH_OUTPUT` and the blocker verbatim, because a
summary that reads like a board is how an unsealed run becomes a board.

THE ONE STATISTIC THIS REFUSES TO COMPUTE, AND WHY

The artifact's own manifest states the draw-index semantics:

  within_row_across_metrics : SAME_SIMULATED_WORLD
  across_rows               : INDEPENDENT_STREAMS_COLUMN_ALIGNED
  "Rows are seeded independently, so a CROSS-ROW correlation read off the
   same axis measures the generator's lack of coupling, not a football
   quantity."

So cross-metric dependence WITHIN a row is real and is reported. CROSS-PLAYER
correlation is refused by name rather than computed and captioned, because a
number that looks like a correlation gets used as one. A stack or a bring-back
read off this axis would be reading the seeding, not the game.

PROBABILITY AT A LINE IS EXACT HERE. It is the empirical share of draws
strictly above the line plus half the ties, computed from all 8,000 draws --
not interpolated from stored quantiles. That is the property the MLB project
learned the hard way and it is why the full draws are kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np

SPEC_VERSION = 'unsealed-draw-summary/1.0.0'
OUTPUT_CLASS = 'UNSEALED_RESEARCH_OUTPUT'
QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)


def prob_over(row: np.ndarray, line: float) -> float:
    """P(X > line) with ties split. Exact from the draws, never interpolated.

    Half the ties is the standard sportsbook push convention made explicit:
    a discrete count landing exactly on an integer line is neither over nor
    under, and silently assigning it to one side biases every integer line.
    """
    n = row.size
    if n == 0:
        return float('nan')
    over = float(np.count_nonzero(row > line))
    ties = float(np.count_nonzero(row == line))
    return (over + 0.5 * ties) / n


def summarise(arr: np.ndarray) -> dict:
    q = np.quantile(arr, QUANTILES, axis=1)
    return {
        'n_rows': int(arr.shape[0]), 'n_draws': int(arr.shape[1]),
        'mean': [float(x) for x in arr.mean(axis=1)],
        'median': [float(x) for x in np.median(arr, axis=1)],
        'sd': [float(x) for x in arr.std(axis=1, ddof=1)],
        'variance': [float(x) for x in arr.var(axis=1, ddof=1)],
        'min': [float(x) for x in arr.min(axis=1)],
        'max': [float(x) for x in arr.max(axis=1)],
        'quantiles': {str(p): [float(x) for x in q[i]]
                      for i, p in enumerate(QUANTILES)},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--out', default='')
    ap.add_argument('--truth', default='',
                    help='truth snapshot, to put names beside the gsis ids')
    a = ap.parse_args(argv)
    d = pathlib.Path(a.run_dir)

    man = json.loads((d / 'player_draws_manifest.json').read_text())
    status = json.loads((d / 'run_status.json').read_text())
    npz_path = d / 'player_draws.npz'
    actual = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    declared = (man.get('file') or {}).get('sha256')
    if declared and actual != declared:
        print(f'DRAW_ARTIFACT_HASH_MISMATCH: manifest {declared} '
              f'against measured {actual}')
        return 1

    # ROW IDENTITY, because an unlabelled distribution is not a finding.
    # `layers[<layer>].row_ids` is the row axis; the array name is
    # '<layer>__<metric>'. Without this the summary reports "row 17" and
    # nobody can act on it or check it.
    names = {}
    if a.truth:
        for q in json.loads(pathlib.Path(a.truth).read_text())['players']:
            if q.get('full_name'):
                names[q['gsis_id']] = {'full_name': q['full_name'],
                                       'team': q.get('team'),
                                       'position': q.get('position'),
                                       'availability': q.get('availability')}
    rows_by_layer = {k: (v or {}).get('row_ids')
                     for k, v in (man.get('layers') or {}).items()}

    z = np.load(npz_path)
    per = {}
    for name in sorted(z.files):
        arr = np.asarray(z[name], dtype=float)
        if arr.ndim != 2:
            continue
        rec = summarise(arr)
        layer = name.split('__', 1)[0]
        ids = rows_by_layer.get(layer)
        if ids and len(ids) == arr.shape[0]:
            rec['row_axis'] = 'gsis_id'
            rec['row_ids'] = list(ids)
            rec['row_labels'] = [names.get(i, {}).get('full_name') for i in ids]
            rec['row_teams'] = [names.get(i, {}).get('team') for i in ids]
        else:
            # NAMED, not omitted: a caller must be able to tell "no labels
            # available" from "labels were not looked for".
            rec['row_axis'] = 'UNLABELLED'
            rec['row_label_refusal'] = (
                f'layer {layer!r} declares '
                f'{0 if not ids else len(ids)} row id(s) against '
                f'{arr.shape[0]} rows; not aligned, so no labels are '
                f'attached rather than guessed')
        per[name] = rec

    fresh = status.get('current_season_input_freshness') or {}
    blocked = {k: v for k, v in (fresh.get('inputs') or {}).items()
               if v.get('state') != 'PASS'}

    out = {
        'schema': 'nfl_unsealed_draw_summary',
        'schema_version': SPEC_VERSION,
        'output_class': OUTPUT_CLASS,
        'game_id': man.get('game_id'),
        'run_id': man.get('run_id'),
        'code_sha': status.get('code_commit'),
        'draw_artifact': {'file': man.get('file'),
                          'measured_sha256': actual,
                          'content_digest': man.get('content_digest'),
                          'n_draws': man.get('n_draws'),
                          'n_matrices': man.get('n_matrices'),
                          'n_draw_cells': man.get('n_draw_cells'),
                          'rng': man.get('rng')},
        'draw_index_semantics': man.get('draw_index_semantics'),
        'sealing': {
            'state': (status.get('first_failure') or {}).get('state'),
            'code': (status.get('first_failure') or {}).get('code'),
            'stage': (status.get('first_failure') or {}).get('stage'),
            'blocking_inputs': blocked,
        },
        'publication': status.get('publication'),
        'refusals': {
            'cross_player_correlation':
                'REFUSED_BY_DESIGN. The manifest states rows are seeded '
                'independently, so a cross-row correlation on the draw axis '
                'measures the generator, not the game. Any stack, bring-back '
                'or duplication figure derived from it would be an artefact.',
            'sealed_or_publishable':
                'This artifact is NOT a sealed forecast and NOT publishable. '
                'Artifact sealing failed on a hard invariant and NFL-1 is not '
                'authorised.',
        },
        'probability_at_line':
            'Exact from all draws: share strictly above, plus half the ties. '
            'Never interpolated from the quantiles recorded here.',
        'per_matrix': per,
    }
    text = json.dumps(out, indent=1) + '\n'
    if a.out:
        pathlib.Path(a.out).write_text(text)
        print(f'wrote {a.out} ({len(text)} bytes)')
    print(f'  matrices summarised: {len(per)}')
    print(f'  sealing: {out["sealing"]["code"]}  blocking: {sorted(blocked)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
