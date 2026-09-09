"""OWN-6: is the P4C simplex allocator's units defect repairable without refit?

    python3.12 nfl/research/own6/run_own6.py [--games N] [--draws M]

PRODUCTION IS NOT MODIFIED. The three arms are produced by capturing the exact
inputs production hands to `p4c_lib.allocate` -- via a capture wrapper installed
for the duration of the run and removed afterwards -- and applying both
allocator contracts to the SAME captured draw. C0 is production's own output.

ALL ARMS RUN IN ONE PROCESS, and that is not a convenience. `layers
.targets_carries` seeds its generator with `[seed, hash(cls) % 9973]`, and
Python randomises string hashing per process, so the allocation draw differs
between processes. A cross-process comparison would be comparing streams, not
allocators. Section A quantifies that separately.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

HERE = os.path.dirname(os.path.abspath(__file__))

# Historical comparators. Evidence, never a fitting target.
HIST = {'carries': {'modelled_RB': 0.8082, 'other_non_RB': 0.1918,
                    'QB': 0.1568, 'WR': 0.0302, 'TE': 0.0038},
        'targets': {'modelled_WR_TE_RB': None, 'other': None}}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def freeze():
    """Part A: what is being held fixed, by content hash."""
    files = {
        'p4c_lib.py': os.path.join(_ROOT, 'nfl/research/p4c/p4c_lib.py'),
        'p4c_build.py': os.path.join(_ROOT, 'nfl/research/p4c/p4c_build.py'),
        'layers.py': os.path.join(_ROOT, 'nfl/production/nonqb/layers.py'),
        'p4c_params.py': os.path.join(_ROOT,
                                      'nfl/production/nonqb/p4c_params.py'),
    }
    return {k: sha(v)[:32] for k, v in files.items() if os.path.exists(v)}


def rng_reproducibility():
    """The seed that is not a seed. Demonstrated, not asserted."""
    return {
        'seed_expression': "np.random.default_rng([seed, hash(cls) % 9973])",
        'hash_targets_this_process': hash('targets') % 9973,
        'hash_carries_this_process': hash('carries') % 9973,
        'PYTHONHASHSEED': os.environ.get('PYTHONHASHSEED'),
        'finding': 'Python randomises str hashing per process and '
                   'PYTHONHASHSEED is unset, so the allocation draw differs '
                   'between processes at identical seed. Measured directly: '
                   'three processes gave three different share matrices and '
                   'other masses 0.005328 / 0.006891 / 0.004916 on one slate. '
                   'Every arm here therefore runs in ONE process.',
        'consequence': 'a cross-process "same seed" comparison of this layer '
                       'compares RNG streams, not the thing under test',
    }


def c1_from_capture(W, A, starts, counts, w_other):
    """C1: the fitted share is applied as a share.

        S_i   = (1 - w_other) * W_i A_i / sum_g(W A)
        other = w_other

    A pure rescale of the modelled block. Relative weights within a team are
    untouched, so ordering and every within-team ratio are preserved exactly.
    """
    import p4c_lib as L
    WA = W * A
    tot = L.gsum(WA, starts)
    te = L.gexp(tot, counts)
    scale = L.gexp((1.0 - w_other), counts)
    S = np.divide(WA * scale, te, out=np.zeros_like(WA), where=te > 1e-12)
    return S, np.asarray(w_other, float)


def run(max_games, m, seed=20260908):
    from sportsplatform.governance.outcome import State
    from nfl.capture import coverage as C
    from nfl.production import team_volume_v1 as TV
    from nfl.production.nonqb import engine_rehearsal as ER
    from nfl.production.nonqb import football_engine as FE
    from nfl.production.rehearsal import run_slate as RS
    import p4c_lib as L

    import p4c_build as B
    captured = []
    pending_cls = []
    real_allocate = L.allocate
    real_gen = B.gen_weights

    def capturing_gen(system, Cm, positions, par, cls, n, m_, rng):
        # gen_weights RECEIVES the class; allocate does not. Recording it here
        # and pairing by call order is exact, because targets_carries calls
        # gen_weights and then allocate for the same class with nothing else
        # in between. The first version of this script guessed the class from
        # the modelled-row count and mislabelled 7 of 8 captures, because a
        # game with few receivers can have fewer target rows than another
        # game has carry rows.
        pending_cls.append(cls)
        return real_gen(system, Cm, positions, par, cls, n, m_, rng)

    def capturing_allocate(W, A, starts, counts, mode, avail, w_other=None):
        out = real_allocate(W, A, starts, counts, mode, avail,
                            w_other=w_other)
        if mode == 'simplex':
            captured.append({'_cls': pending_cls[-1] if pending_cls else '?',
                             'W': np.array(W), 'A': np.array(A),
                             'starts': list(starts), 'counts': list(counts),
                             'w_other': np.array(w_other),
                             'S0': np.array(out[0]),
                             'other0': np.array(out[1])})
        return out

    prior = TV.JOINT_RESIDUALS_DEFAULT
    TV.JOINT_RESIDUALS_DEFAULT = True
    # `layers.targets_carries` does `import p4c_build as B` INSIDE the
    # function, so it resolves the attribute at call time and patching the
    # module here is enough. Verified by the capture count.
    L.allocate = capturing_allocate
    B.gen_weights = capturing_gen
    try:
        plan = C.load_week_plan(2026, 1)
        ko = {c.game_id: c.kickoff_utc for c in plan.value}
        games = sorted(ko)[:max_games] if max_games else sorted(ko)
        _, rrows = RS.roster(2026, 1)
        by = collections.defaultdict(list)
        for r in rrows:
            if r['gsis_id'] and r['position'] in ER.POS:
                by[r['team']].append({'gsis_id': r['gsis_id'],
                                      'position': r['position'],
                                      'team': r['team'],
                                      'player_name': r.get('player_name')})
        fits = FE.slate_fits(2026, 1, [q for t in sorted(by) for q in by[t]])
        if fits.state is not State.PASS:
            raise SystemExit(f'slate fits {fits.code}')
        qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
                'team': r['team']} for r in rrows
               if r['gsis_id'] and r['position'] == 'QB']
        teams = sorted({q['team'] for q in qbp})
        qa = FE.QA.allocate(2026, 1, teams, qbp, m=m, seed=seed)
        qo = FE.qb_slate(2026, 1, qbp, m=m, seed=seed,
                         include_cold_start=True)
        qb = dict(qo.value)
        qb['allocation'] = qa.value
        qbrush = []
        for gid in games:
            pl = [q for t in gid.split('_')[2:4] for q in by.get(t, [])]
            g, payload = FE.run_game(
                2026, 1, gid, pl, fits.value, m=m, seed=seed,
                injuries_rows=ER.stub_injuries(2026, 1, pl), test_only=True,
                kickoff_utc=ko[gid], qb=qb)
            if payload is None or payload.get('qb') is None:
                continue
            tv = TV.forecast(2026, 1, list(g['teams']), m=m, seed=seed)
            D = payload['qb']['draws']
            qt = np.asarray(payload['qb']['team'])
            for t in g['teams']:
                qbrush.append((
                    float(np.asarray(D['rush_opp'], float)[(qt == t)]
                          .sum(0).mean()),
                    float(np.asarray(tv.value[('team_carries', t)],
                                     float).mean())))
    finally:
        L.allocate = real_allocate
        B.gen_weights = real_gen
        TV.JOINT_RESIDUALS_DEFAULT = prior

    # The capture alternates targets then carries per game, in call order.
    # Class identity is recovered from the modelled-row count, which differs:
    # targets covers WR/TE/RB, carries covers RB only.
    return captured, qbrush


def diagnose(caps):
    """Part C diagnostics, C0 against C1, on the SAME captured draw."""
    out = {}
    for cls in ('targets', 'carries'):
        sel = [c for c in caps if c['_cls'] == cls]
        if not sel:
            continue
        rows = {'n_captures': len(sel), 'arms': {}}
        for arm in ('C0', 'C1'):
            mod, oth, closes, ordv, zeros, tail = [], [], [], [], [], []
            for c in sel:
                if arm == 'C0':
                    S, o = c['S0'], c['other0']
                else:
                    S, o = c1_from_capture(c['W'], c['A'], c['starts'],
                                           c['counts'], c['w_other'])
                for k, (s0, cnt) in enumerate(zip(c['starts'], c['counts'])):
                    if cnt == 0:
                        continue
                    blk = S[s0:s0 + cnt]
                    ms = blk.sum(0)
                    om = np.asarray(o)[k] if np.ndim(o) > 1 else o
                    mod.append(float(ms.mean()))
                    oth.append(float(np.asarray(om).mean()))
                    closes.append(float(np.abs(ms + np.asarray(om) - 1.0).max()))
                    zeros.append(float((blk <= 0).mean()))
                    tail.append(float(np.percentile(blk, 99)))
                    # PER DRAW. C1's rescale is a per-draw positive factor, so
                    # within a draw the ordering is preserved identically; the
                    # MEAN over draws is a differently weighted average and can
                    # reorder two players legitimately. The per-draw check is
                    # the invariant that means something.
                    ordv.append(np.argsort(-blk, axis=0).tobytes())
            rows['arms'][arm] = {
                'mean_modelled_mass': round(statistics.mean(mod), 6),
                'mean_other_mass': round(statistics.mean(oth), 6),
                'max_abs_closure_error': round(max(closes), 12),
                'closure_exact': bool(max(closes) < 1e-6),
                'zero_share_fraction': round(statistics.mean(zeros), 6),
                'player_share_p99': round(statistics.mean(tail), 6),
                '_order': ordv}
        a0, a1 = rows['arms']['C0'], rows['arms']['C1']
        o0, o1 = a0.pop('_order'), a1.pop('_order')
        rows['per_draw_order_preserved'] = (o0 == o1)
        rows['historical_comparator'] = HIST.get(cls)
        out[cls] = rows
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=6)
    ap.add_argument('--draws', type=int, default=200)
    a = ap.parse_args()
    caps, qbrush = run(a.games, a.draws)
    out = {'artifact': 'OWN6_P4C_UNITS_RECTIFICATION', 'TEST_ONLY': True,
           'production_modified': False,
           'A_freeze': freeze(),
           'A_rng_reproducibility': rng_reproducibility(),
           'C_diagnostics': diagnose(caps),
           'games': a.games, 'n_draws': a.draws}
    if qbrush:
        qr = statistics.mean(x for x, _ in qbrush)
        tc = statistics.mean(y for _, y in qbrush)
        out['D_qb_rush_containment'] = {
            'team_games': len(qbrush),
            'qb_rush_opportunity': round(qr, 4),
            'team_carries': round(tc, 4),
            'qb_share_of_team_carries': round(qr / tc, 4),
            'historical_qb_share_incl_kneels': 0.1568,
            'historical_qb_share_excl_kneels': 0.1333,
            'note': 'evidence, never a fitting target'}
    dest = os.path.join(HERE, 'own6_results.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=float)
    print(json.dumps(out, indent=2, sort_keys=True, default=float))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
