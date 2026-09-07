"""Re-derive P4B's over-allocation figure and the corrected one, side by side.

P4B section 13 reported that independent share draws "allocate roughly a third
more of the pie than exists" -- 27% to 45% depending on class. The first P4C
numbers put system A's over-allocation near zero, so one of the two is wrong.
This recomputes BOTH quantities from the same draws so the answer is not a
matter of opinion.

  quantity 1 (what P4B printed):   sum_i S_i          -- NO appearance mask
  quantity 2 (what it was compared
             against):             sum_i S_i^realised -- absences ARE zeros
  quantity 3 (the like-for-like):  sum_i A_i S_i      -- appearance mask applied
"""
import collections, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
sys.path.insert(0, HERE)
sys.path.insert(0, P4B)
import p4c_lib as L                                            # noqa: E402
import p4c_build as BLD                                        # noqa: E402

rows = BLD.load_panel()
pa = BLD.appearance(rows)
print(f'{"class":12s} {"ev":4s} {"sum S (P4B)":>12s} {"sum A*S":>9s} '
      f'{"realised":>9s} | {"P4B over%":>9s} {"corrected%":>10s}')
for cls, c in L.CLASSES.items():
    sub = BLD.prepare_class(rows, cls)
    skey = c['share']
    for ev in L.EVAL:
        par = BLD.fit_params(sub, cls, ev, rows)
        te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
              and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
              and r['_C'] is not None]
        te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
        if len(te) < 200:
            continue
        keys = [(r['team'], r['ord']) for r in te]
        starts = np.array([i for i, k in enumerate(keys)
                           if i == 0 or k != keys[i - 1]])
        n = len(te)
        C = np.array([r['_C'] for r in te], np.float32)
        positions = [r['position'] for r in te]
        p_app = np.array([pa[id(r)] for r in te], np.float32)
        S_real = np.array([r[skey] for r in te], np.float32)
        A_real = np.array([1.0 if r['appeared'] else 0.0 for r in te])
        rng = np.random.default_rng(L.SEED + 2003)
        pool = par['add_pool']
        allp = np.concatenate(list(pool.values()))
        Sd = C[:, None] + BLD._resample(pool, positions, n, L.M_DRAWS, rng, allp)
        np.clip(Sd, 0, 1, out=Sd)
        Ad = (np.random.default_rng(L.SEED + 1009)
              .random((n, L.M_DRAWS), np.float32) < p_app[:, None])
        q1 = L.gsum(Sd, starts).mean()
        q3 = L.gsum(Sd * Ad, starts).mean()
        q2 = L.gsum((S_real * A_real)[:, None], starts).mean()
        print(f'{cls:12s} {ev} {q1:12.4f} {q3:9.4f} {q2:9.4f} | '
              f'{100*(q1-q2)/q2:+9.1f} {100*(q3-q2)/q2:+10.1f}')
