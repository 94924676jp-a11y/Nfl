"""WS-A step 3: the structural probes the results document cites.

    python3.12 nfl/research/remediation/ws_a/probes.py

Three things the headline table cannot carry: the determinism of the leaked
cell, the residual gap between the training candidate universe and the served
one, and the WS04 conditioning table re-derived here so the results document is
not quoting another artifact for its own central claim.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('wsa_harness', HERE / 'harness.py')
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)

from nfl.production.nonqb import appearance_r7 as R7     # noqa: E402

OUT = HERE / 'WS_A_PROBES.json'


def main():
    S = H.load()
    urows = S['urows']
    out = {'artifact': 'WS_A_STRUCTURAL_PROBES',
           'spec_version': H.SPEC_VERSION,
           'preregistration_sha256': H.PREREG_SHA256}

    # ---- 1. the leaked cell, as a contingency table ----------------------
    pres = np.array([r.get('v1') is not None for r in urows])
    inp = np.array([bool(r.get('in_panel')) for r in urows])
    app = np.array([int(r['appeared']) for r in urows])
    out['contingency'] = {
        'n_rows': int(len(urows)),
        'v1_present_and_appeared': int((pres & (app == 1)).sum()),
        'v1_present_and_absent_from_field': int((pres & (app == 0)).sum()),
        'v1_missing_and_appeared': int(((~pres) & (app == 1)).sum()),
        'v1_missing_and_absent_from_field': int(((~pres) & (app == 0)).sum()),
        'P_appeared_given_v1_present': round(float(app[pres].mean()), 6),
        'P_appeared_given_v1_missing': round(float(app[~pres].mean()), 6),
        'v1_present_equals_in_panel_fraction': round(float((pres == inp).mean()), 6),
        'reading': 'P(appeared | block missing) is exactly zero on every one '
                   'of these rows. It is a property of the join key, not an '
                   'estimate, and no resampling scheme changes it.'}

    # ---- 2. WS04's conditioning table, re-derived -------------------------
    def cell(rows, fn):
        sel = [r for r in rows if fn(r)]
        return {'n': len(sel),
                'appearance_rate': (round(float(np.mean([r['appeared']
                                                         for r in sel])), 4)
                                    if sel else None)}
    w1 = [r for r in urows if r['w'] == 1]
    w1p = [r for r in w1 if r.get('v1') is not None]
    conds = {
        'app_ewma_is_None_cold_start': lambda r: r.get('app_ewma') is None,
        'app_ewma_lt_0.05': lambda r: (r.get('app_ewma') is not None
                                       and r['app_ewma'] < 0.05),
        'cm_carried_ge_9': lambda r: (r.get('cm_carried') or 0) >= 9,
        'app_ewma_0.95_to_1': lambda r: (r.get('app_ewma') is not None
                                         and r['app_ewma'] >= 0.95),
    }
    out['week1_conditioning'] = {
        'n_week1_rows': len(w1), 'n_week1_rows_with_the_block': len(w1p),
        'cells': {k: {'unconditional': cell(w1, f),
                      'conditional_on_v1_present': cell(w1p, f)}
                  for k, f in conds.items()},
        'reading': 'Conditioning on block presence drives every long-absence '
                   'cell to 1.0000. That is the R7 inversion arriving through '
                   'the V1 join rather than through the frame.'}

    # ---- 3. the residual universe gap ------------------------------------
    per_tw = collections.Counter()
    panel_tw = collections.Counter()
    listed_tw = collections.Counter()
    for r in urows:
        k = (r['s'], r['w'], r['t'])
        per_tw[k] += 1
        if r.get('in_panel'):
            panel_tw[k] += 1
        if r.get('rank') is not None:
            listed_tw[k] += 1
    ks = sorted(per_tw)
    out['candidate_universe'] = {
        'n_team_weeks': len(ks),
        'mean_union_candidates_per_team_week': round(
            float(np.mean([per_tw[k] for k in ks])), 3),
        'mean_panel_rows_per_team_week': round(
            float(np.mean([panel_tw[k] for k in ks])), 3),
        'mean_depth_listed_per_team_week': round(
            float(np.mean([listed_tw[k] for k in ks])), 3),
        'unsupported_cell_rows_declined': int(sum(
            1 for r in urows if R7.is_unsupported(r))),
        'limit': 'A player WITH history who is neither depth-listed nor a '
                 'panel row still produces no training row. The union frame '
                 'narrows the LOOKBACK_CANDIDATE censoring; it does not close '
                 'it, and no candidate in this pass claims to. Closing it '
                 'needs weekly roster membership for 2020-2025, which this '
                 'checkout does not hold.'}

    # ---- 4. what the frame says appearance depends on ---------------------
    def rate_by(fn, labels):
        tab = {}
        for lab in labels:
            sel = [r for r in urows if fn(r) == lab]
            tab[str(lab)] = {'n': len(sel),
                             'appearance_rate': (round(float(np.mean(
                                 [r['appeared'] for r in sel])), 4)
                                 if sel else None)}
        return tab

    def ewb(r):
        v = r.get('app_ewma')
        if v is None:
            return 'none'
        return ('lt_0.05' if v < 0.05 else '0.05-0.5' if v < 0.5 else
                '0.5-0.95' if v < 0.95 else '0.95-1')

    def rkb(r):
        rk = r.get('rank')
        return ('unlisted' if rk is None else
                ('r1' if rk == 1 else 'r2' if rk == 2 else
                 'r3' if rk == 3 else 'r4plus'))

    out['frame_is_correctly_signed'] = {
        'by_prior_participation': rate_by(
            ewb, ['none', 'lt_0.05', '0.05-0.5', '0.5-0.95', '0.95-1']),
        'by_depth_rank': rate_by(
            rkb, ['r1', 'r2', 'r3', 'r4plus', 'unlisted']),
        'reading': 'WS04 finding 6, re-derived. The union frame itself is '
                   'monotone and correctly signed, so the inversion is not a '
                   'frame defect.'}

    OUT.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    main()
