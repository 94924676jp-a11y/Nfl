#!/usr/bin/env python3.12
"""Verify a post-inactive rerun against the pre-inactive run it replaces.

    python3.12 nfl/tools/post_inactive_verify.py --before <run-dir> \
        --after <run-dir> [--json <out>]

WHY THIS EXISTS

The official inactive list publishes about ninety minutes before kickoff and
everything after it is on a clock. `ingest_inactives.py` already refuses to let
the INGESTION chain be improvised under time pressure. This is the other half:
once the rerun exists, the checks that say whether it did what a post-inactive
rerun is FOR should also not be improvised, and their expected answers should
already be written down.

THE PREDICTION THIS TESTS WAS RECORDED BEFORE THE EVIDENCE ARRIVED

On 2026-09-24, before any inactive list was available, this was written into
`nfl/research/findings/2026-09-24_QB_ALLOCATION_AND_CONDITIONALITY.md`:

    If ATL's list rules out Penix and/or Tua, Cooper Rush's P(plays) should
    rise toward 1.0 and his unconditional DK mean should move up toward
    roughly 14, his current conditional value. If his P(plays) does NOT move
    after the inactives are ingested, the availability evidence is not
    reaching the QB allocation. That would be a wiring defect, not a
    modelling one.

A prediction recorded after seeing the outcome is not a prediction, so this
script only compares -- it never decides what the expectation should have been.

WHAT IT CHECKS, AND WHAT IT REFUSES TO CONCLUDE

1. Every player the AFTER run declares terminal owns nothing. On the run this
   was written against, that check FAILS for one player in one layer, so a
   rerun that still fails it has not fixed the gadget-pool defect.
2. Players newly ruled out between the two runs lost their opportunity, named
   individually rather than counted.
3. For players still available, the movement in P(opportunity) and in the
   conditional and unconditional means.

It does NOT decide whether the new numbers are BETTER. Nothing here observes
an outcome, and a rerun moving in the direction someone hoped for is not
evidence that it is right. It reports what moved.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.unsealed.conditionality import table  # noqa: E402
from nfl.research.unsealed.unavailable_owns_nothing import (  # noqa: E402
    check as owns_nothing_check,
    declared_unavailable,
)

REQUIRED = ('player_draws_manifest.json', 'player_draws.npz',
            'TRUTH_SNAPSHOT_as_run.json')


class LoadError(RuntimeError):
    pass


def load(run_dir) -> dict:
    d = pathlib.Path(run_dir)
    missing = [f for f in REQUIRED if not (d / f).exists()]
    if missing:
        raise LoadError(f'{d} is missing {missing}')
    manifest = json.loads((d / REQUIRED[0]).read_text())
    truth = json.loads((d / REQUIRED[2]).read_text())
    with np.load(d / REQUIRED[1], allow_pickle=True) as z:
        arrays = {k: z[k] for k in z.keys()}
    names = {p['gsis_id']: (p.get('full_name'), p.get('team'),
                            p.get('position'))
             for p in truth.get('players', ())}
    return {'dir': str(d), 'manifest': manifest, 'truth': truth,
            'arrays': arrays, 'names': names}


def compare(before: dict, after: dict) -> dict:
    rows_b = {r['gsis_id']: r for r in
              table(before['arrays'], before['manifest']['layers'],
                    'dk_scoring', 'dk_points')}
    rows_a = {r['gsis_id']: r for r in
              table(after['arrays'], after['manifest']['layers'],
                    'dk_scoring', 'dk_points')}

    out_b = set(declared_unavailable(before['truth']))
    out_a = set(declared_unavailable(after['truth']))
    newly_out = sorted(out_a - out_b)

    verdict = owns_nothing_check(after['arrays'],
                                 after['manifest']['layers'], after['truth'])

    moved = []
    for gsis_id, ra in rows_a.items():
        rb = rows_b.get(gsis_id)
        if rb is None:
            continue
        pb = rb.get('p_any_modelled_opportunity')
        pa = ra.get('p_any_modelled_opportunity')
        moved.append({
            'gsis_id': gsis_id,
            'name': (after['names'].get(gsis_id) or (None,))[0],
            'team': (after['names'].get(gsis_id) or (None, None))[1],
            'p_before': pb, 'p_after': pa,
            'd_p': (None if pb is None or pa is None else pa - pb),
            'mean_before': rb['mean_unconditional'],
            'mean_after': ra['mean_unconditional'],
            'd_mean': ra['mean_unconditional'] - rb['mean_unconditional'],
            'cond_before': rb.get('mean_given_opportunity'),
            'cond_after': ra.get('mean_given_opportunity'),
        })
    moved.sort(key=lambda r: -abs(r['d_mean']))

    return {
        'before_dir': before['dir'], 'after_dir': after['dir'],
        'newly_declared_unavailable': [
            {'gsis_id': g,
             'name': (after['names'].get(g) or (None,))[0],
             'team': (after['names'].get(g) or (None, None))[1],
             'p_after': (rows_a.get(g) or {}).get('p_any_modelled_opportunity'),
             'mean_after': (rows_a.get(g) or {}).get('mean_unconditional')}
            for g in newly_out],
        'unavailable_owns_nothing': verdict,
        'dropped_from_board': sorted(set(rows_b) - set(rows_a)),
        'added_to_board': sorted(set(rows_a) - set(rows_b)),
        'movement': moved,
        'interpretation_limits': (
            'This compares two runs. It observes no outcome and it does not '
            'say which run is better. A rerun moving in the direction someone '
            'expected is not evidence that it is right.'),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before', required=True)
    ap.add_argument('--after', required=True)
    ap.add_argument('--json')
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args(argv)

    try:
        cmp = compare(load(a.before), load(a.after))
    except LoadError as exc:
        print(f'BLOCKED  {exc}')
        return 2

    v = cmp['unavailable_owns_nothing']
    print(f"unavailable_owns_nothing: {v['state']}  {v['code']}")
    print(f"  {v['detail']}")

    print(f"\nnewly declared unavailable: "
          f"{len(cmp['newly_declared_unavailable'])}")
    for r in cmp['newly_declared_unavailable']:
        p = r['p_after']
        flag = '' if (p in (None, 0) or p == 0.0) else '   <-- STILL HOLDS MASS'
        print(f"  {r['name']} ({r['team']}): P(opp) after = "
              f"{'n/a' if p is None else f'{p:.3f}'}{flag}")

    if cmp['dropped_from_board']:
        print(f"\ndropped from the board entirely: "
              f"{len(cmp['dropped_from_board'])}")
    if cmp['added_to_board']:
        print(f"added to the board: {len(cmp['added_to_board'])}")

    print(f"\nlargest movement in unconditional DK mean (top {a.top}):")
    print(f"  {'player':22} {'tm':4} {'P before':>9} {'P after':>8} "
          f"{'mean before':>12} {'mean after':>11} {'delta':>8}")
    for r in cmp['movement'][:a.top]:
        pb = 'n/a' if r['p_before'] is None else f"{r['p_before']:.3f}"
        pa = 'n/a' if r['p_after'] is None else f"{r['p_after']:.3f}"
        print(f"  {str(r['name']):22} {str(r['team']):4} {pb:>9} {pa:>8} "
              f"{r['mean_before']:12.2f} {r['mean_after']:11.2f} "
              f"{r['d_mean']:+8.2f}")

    print(f"\n{cmp['interpretation_limits']}")

    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(cmp, indent=2) + '\n')
        print(f'\nfull comparison written to {a.json}')

    return 1 if v['state'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
