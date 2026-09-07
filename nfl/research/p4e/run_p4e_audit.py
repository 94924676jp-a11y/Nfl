"""P4E item 4: the data and feature audit.

The claim "every feature is prior-only" is worth nothing as prose. This tests
it MECHANICALLY: blank every outcome field on every row at ordinal >= k, rebuild
the whole feature set from the masked panel, and require that the features on
rows at ordinal == k are bit-identical to the ones built from the full panel.
Any feature that moves has read something at or after its own game.
"""
import collections, copy, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4e_build as B                                          # noqa: E402

OUTCOME_FIELDS = ('s_carries', 'y_carries', 'appeared', 's_snaps', 'y_snaps',
                  'carries', 'carry_share', 'y_targets', 's_targets',
                  'designed_rushes', 'gl_carries', 'did_not_appear')
GFEATS = None


def gfeats(sub):
    ks = set()
    for r in sub:
        ks |= {k for k in r if k.startswith('g_')}
    return sorted(ks)


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    feats = gfeats(sub)
    print(f'{len(feats)} derived features on {len(sub)} RB player-games')

    OUT = {'n_rows': len(sub), 'features': feats, 'coverage': {}, 'masking': {}}

    # ---- 1. coverage and range, by season ------------------------------
    seasons = sorted({r['season'] for r in sub})
    print('\n== coverage (fraction present) ==')
    hdr = ' '.join(f'{s:>7d}' for s in seasons)
    print(f"  {'feature':26s} {hdr}   {'min':>9s} {'max':>9s}")
    for f in feats:
        cov, vals = [], []
        for s in seasons:
            rs = [r for r in sub if r['season'] == s]
            present = [r.get(f) for r in rs if r.get(f) is not None]
            cov.append(len(present) / max(len(rs), 1))
            vals += [float(v) for v in present]
        OUT['coverage'][f] = {
            'by_season': {str(s): round(c, 4) for s, c in zip(seasons, cov)},
            'min': (min(vals) if vals else None),
            'max': (max(vals) if vals else None)}
        print(f"  {f:26s} " + ' '.join(f'{c:7.3f}' for c in cov) +
              f"   {(min(vals) if vals else float('nan')):9.3f} "
              f"{(max(vals) if vals else float('nan')):9.3f}")

    # ---- 2. the masking audit ------------------------------------------
    ords = sorted({r['ord'] for r in sub})
    probes = [ords[len(ords) // 4], ords[len(ords) // 2],
              ords[3 * len(ords) // 4], ords[-3]]
    print('\n== masking audit: blank outcomes at ord >= k, rebuild, compare ==')
    allbad = {}
    for k in probes:
        masked = copy.deepcopy(sub)
        nb = 0
        for r in masked:
            if r['ord'] >= k:
                for f in OUTCOME_FIELDS:
                    if f not in r:
                        continue
                    if f in ('appeared', 'did_not_appear'):
                        r[f] = False
                    elif f.startswith('s_') or f == 'carry_share':
                        r[f] = None          # share fields are optional
                    else:
                        r[f] = 0.0           # count fields must stay numeric
                nb += 1
            for g in list(r):
                if g.startswith('g_'):
                    del r[g]
        B.attach_features(masked)
        at_k_full = [r for r in sub if r['ord'] == k]
        at_k_mask = [r for r in masked if r['ord'] == k]
        key = lambda r: (r['team'], r['gsis_id'])
        mm = {key(r): r for r in at_k_mask}
        bad = collections.Counter()
        n_cmp = 0
        for r in at_k_full:
            m = mm.get(key(r))
            if m is None:
                continue
            for f in feats:
                a, b = r.get(f), m.get(f)
                n_cmp += 1
                if a is None and b is None:
                    continue
                if a is None or b is None or abs(float(a) - float(b)) > 1e-12:
                    bad[f] += 1
        print(f'  ord >= {k}: {nb} rows blanked, {len(at_k_full)} rows at k, '
              f'{n_cmp} feature values compared, '
              f'{"CLEAN" if not bad else "LEAKING: " + str(dict(bad))}')
        OUT['masking'][str(k)] = {'rows_blanked': nb, 'rows_at_k': len(at_k_full),
                                  'values_compared': n_cmp,
                                  'leaking': dict(bad)}
        for f, c in bad.items():
            allbad[f] = allbad.get(f, 0) + c
    OUT['masking_verdict'] = ('CLEAN -- no derived feature changed when its own '
                              'game and everything after it was blanked'
                              if not allbad else f'LEAKING: {allbad}')
    print(f"\n  verdict: {OUT['masking_verdict']}")

    json.dump(OUT, open(f'{HERE}/p4e_audit.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4e_audit.json')


if __name__ == '__main__':
    main()
