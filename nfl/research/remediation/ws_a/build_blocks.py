"""WS-A step 1: build the three V1 feature bases and cache them.

    python3.12 nfl/research/remediation/ws_a/build_blocks.py

Writes a pickle of the S-serve and U-union blocks to the session scratchpad.
The cache is an intermediate, not an artifact: every number reported comes from
a run that rebuilt it or read a cache whose fingerprint matches.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import os
import pathlib
import pickle
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('wsa_harness', HERE / 'harness.py')
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)

CACHE = pathlib.Path(os.environ.get(
    'WSA_CACHE', '/tmp/claude-0/-home-user-mlb-prop-system-v7/'
    '8de98087-4781-5a10-ae09-ef74590f8116/scratchpad/wsa/blocks.pkl'))


def main():
    t0 = time.time()
    S = H.load()
    urows = S['urows']
    print(f'frame {len(urows)} rows, panel {len(S["panel"])}, '
          f'load {S["load_seconds"]}s', flush=True)

    present_p = sum(1 for r in urows if r.get('v1') is not None)
    absent_p = len(urows) - present_p
    import numpy as np
    rate_abs = (float(np.mean([r['appeared'] for r in urows
                               if r.get('v1') is None])) if absent_p else None)
    rate_pre = float(np.mean([r['appeared'] for r in urows
                              if r.get('v1') is not None]))
    print(f'P-join: present {present_p} (rate {rate_pre:.4f}), '
          f'absent {absent_p} (rate {rate_abs:.4f})', flush=True)

    t = time.time()
    blk_u, n_added = H.union_blocks()
    print(f'U-union: {len(blk_u)} blocks, {n_added} synthetic rows, '
          f'{round(time.time()-t,1)}s', flush=True)

    weeks = sorted({(r['s'], r['w']) for r in urows if r['s'] in H.EVAL_SEASONS})
    print(f'S-serve: {len(weeks)} target weeks', flush=True)
    blk_s = {}
    for i, (s, w) in enumerate(weeks):
        t = time.time()
        blk_s.update(H.serve_blocks(s, w))
        if i % 10 == 0 or i == len(weeks) - 1:
            print(f'  [{i+1}/{len(weeks)}] {s} w{w} '
                  f'{round(time.time()-t,1)}s cum={len(blk_s)}', flush=True)

    # S2, the label-flip invariance test, on the first and last target week.
    flips = {}
    for (s, w) in (weeks[0], weeks[len(weeks)//2], weeks[-1]):
        a = H.serve_blocks(s, w, flip_labels=False)
        b = H.serve_blocks(s, w, flip_labels=True)
        diff = [k for k in a if a[k] != b.get(k)]
        flips[f'{s}_w{w}'] = {'n_rows': len(a), 'n_rows_that_moved': len(diff)}
        print(f'S2 flip {s} w{w}: {len(diff)}/{len(a)} rows moved', flush=True)

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE, 'wb') as fh:
        pickle.dump({'blk_u': blk_u, 'blk_s': blk_s, 'weeks': weeks,
                     'flip_test': flips, 'n_synth_union': n_added,
                     'p_join': {'present': present_p, 'absent': absent_p,
                                'rate_present': rate_pre,
                                'rate_absent': rate_abs}}, fh)
    print(f'cached {CACHE} in {round(time.time()-t0,1)}s', flush=True)


if __name__ == '__main__':
    main()
