#!/usr/bin/env python3.12
"""Run the unavailable-owns-nothing invariant over a finished run directory.

    python3.12 nfl/tools/check_unavailable_owns_nothing.py --run-dir <dir>
                                                           [--json <out>]

WHY A SCRIPT AND NOT A LINE IN run_forecast

The invariant compares the draws against the run's OWN truth snapshot, and
`TRUTH_SNAPSHOT_as_run.json` is written by the caller that orchestrates an
unsealed run, not by `run_forecast` itself. Wiring the check inside
`run_forecast` would mean either passing the snapshot down through a path that
does not currently carry it, or re-deriving availability there from a
different source -- and a check that reads a DIFFERENT record than the run
recorded is not the check that was wanted.

So it runs after the artifacts exist, on exactly the two files that describe
what the run believed and what it produced. The invariant is registered in
`artifact.INVARIANTS` as DIAGNOSTIC, so its class is declared even though the
evaluation is driven from here.

Exit status is 1 when the invariant FAILS, so this can gate a pipeline step
without anyone re-reading the JSON to find out what happened.
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

from nfl.research.unsealed.unavailable_owns_nothing import (  # noqa: E402
    InvariantError,
    check,
)

REQUIRED = ('player_draws_manifest.json', 'player_draws.npz',
            'TRUTH_SNAPSHOT_as_run.json')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--json', help='write the full verdict here')
    a = ap.parse_args(argv)

    d = pathlib.Path(a.run_dir)
    missing = [f for f in REQUIRED if not (d / f).exists()]
    if missing:
        # NOT A PASS. A check that cannot read its inputs has not been run,
        # and saying so is the whole discipline this repository is built on.
        print(f'BLOCKED  cannot run: {d} is missing {missing}')
        return 2

    manifest = json.loads((d / REQUIRED[0]).read_text())
    truth = json.loads((d / REQUIRED[2]).read_text())
    with np.load(d / REQUIRED[1], allow_pickle=True) as z:
        arrays = {k: z[k] for k in z.keys()}

    try:
        verdict = check(arrays, manifest['layers'], truth)
    except InvariantError as exc:
        print(f'BLOCKED  {exc}')
        return 2

    print(f"{verdict['state']}  {verdict['code']}")
    print(f"  {verdict['detail']}")
    print(f"  declared unavailable: {verdict['n_declared_unavailable']}  "
          f"violating: {verdict['n_violating']}")
    for v in verdict['violations']:
        print(f"  * {v['name']} ({v['team']}, {v['position']}) "
              f"{v['availability']} basis={v['basis']}")
        for h in v['holds']:
            print(f"      {h['layer']}__{h['metric']}: "
                  f"P(nonzero)={h['p_nonzero']:.3f} mean={h['mean']:.3f} "
                  f"max={h['max']:.0f}")

    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(verdict, indent=2) + '\n')
        print(f'  verdict written to {a.json}')

    return 1 if verdict['state'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
