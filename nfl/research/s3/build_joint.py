"""Stage 3: build JointDraws from the ACCEPTED models, unchanged.

Nothing here fits, tunes or improves a marginal. It assembles what P4C already
accepted -- system C for every class -- into the joint schema the diagnostic
harness reads.
"""
import hashlib, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import joint as J                                              # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..', 'p4c'))
sys.path.insert(0, os.path.join(HERE, '..', 'p4e'))
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
from run_p4c import groups_of                                  # noqa: E402

ACCEPTED_SYSTEM = 'C'
CLASSES = ('carries', 'targets', 'snaps')


def marginal_identity(cls, ev):
    """What produced the weights. Hashed so a swapped marginal cannot pass
    unnoticed -- see test_joint_scaffold.py."""
    src = b''
    for p in ('p4c_build.py', 'p4c_lib.py'):
        src += open(os.path.join(HERE, '..', 'p4c', p), 'rb').read()
    return {'system': ACCEPTED_SYSTEM, 'class': cls, 'season': ev,
            'code_sha256': hashlib.sha256(src).hexdigest(),
            'seed': CL.SEED, 'M': CL.M_DRAWS}


def build(rows, vol, pa, cls, ev):
    c = CL.CLASSES[cls]
    mode, skey, ykey = c['mode'], c['share'], c['y']
    store = vol.get((c['den'], ev))
    if store is None:
        return None
    sub = CB.prepare_class(rows, cls)
    par = CB.fit_params(sub, cls, ev, rows)
    te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
          and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
          and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
    te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    if len(te) < 200:
        return None
    n = len(te)
    starts, counts, _gk = groups_of(te)
    G = len(starts)
    ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
    T = store['B'][ti]
    Cp = np.array([r['_C'] for r in te], np.float32)
    pos = [r['position'] for r in te]
    si = ['A', 'B', 'C', 'C2', 'D_dir', 'D_sln', 'D_emp', 'E'].index('C') \
        if mode == 'simplex' else ['A', 'B', 'C', 'D_ln', 'D_emp', 'E'].index('C')
    W = CB.gen_weights('C', Cp, pos, par, cls, n, CL.M_DRAWS,
                       np.random.default_rng(CL.SEED + 3000 + 17 * si))
    p_app = np.array([pa[id(r)] for r in te], np.float32)
    A = (np.random.default_rng(CL.SEED + 1009)
         .random((n, CL.M_DRAWS), np.float32) < p_app[:, None])
    mass = CB.mass_draws('C', par, G, CL.M_DRAWS,
                         np.random.default_rng(CL.SEED + 5000 + si))
    avail = (1.0 - mass) if mode == 'simplex' else mass
    Sp, _other, _nb = CL.allocate(W, A, starts, counts, 'occupancy', avail)
    y = np.array([r[ykey] for r in te], float)
    Sstar = np.array([r[skey] for r in te], np.float64)
    Astar = np.array([1.0 if r['appeared'] else 0.0 for r in te], np.float32)
    return J.JointDraws(cls, ev, te, starts, counts, T, A, W,
                        Sp.astype(np.float32), y, Sstar, Astar,
                        cap=1.0, group_cap=(1.0 if mode == 'simplex' else 5.0),
                        marginal_id=marginal_identity(cls, ev), mode=mode)
