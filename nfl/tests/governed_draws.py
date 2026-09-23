"""Build a GOVERNED simulation draw artifact for a fixture.

WHY THIS EXISTS. The owner promoted SIMULATION_DRAW_COHERENCE_VIOLATED to an
advertised invariant on 2026-09-23: for a governed publishable simulation
artifact, draw coherence is required, and a missing evaluation may not be
treated as equivalent to a pass. Two synthetic fixtures then blocked, because
they wrote a three-metric npz with no quarterback layer and a two-key
run_status. The ruling was to repair the fixtures, not the rule, and NOT to
turn NOT_EVALUABLE into PASS or fabricate a certificate.

So this helper builds an artifact the REAL checker can evaluate and then runs
the REAL checker and the REAL certifier over it. Nothing here asserts a
verdict; it records whichever verdict production's own code returns. If a
future change to `draw_coherence` starts rejecting these arrays, every fixture
built here goes red, which is correct -- they are supposed to be governed
artifacts, and a governed artifact that stops cohering is news.

THE VALUES SATISFY THE IDENTITIES BY CONSTRUCTION, NOT BY LUCK. The QB line is
built from a dropback partition outward -- dropbacks split into attempts,
sacks and scrambles, completions drawn inside attempts, interceptions inside
the remainder, touchdowns inside completions -- so every identity
`qb_coherence` checks holds for arithmetic reasons. `corrupt_qb` then breaks
exactly one of them, which is what the end-to-end corruption tests need.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Dict, Sequence

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import coherence_certificate as CCERT            # noqa: E402
from nfl.production import draw_coherence as DC                      # noqa: E402

#: The metrics `qb_coherence` requires. Named here so a fixture that omits
#: one gets a readable failure instead of a BLOCKED verdict nobody expected.
QB_METRICS = ('db', 'att', 'sacks', 'scr', 'cmp', 'int', 'ptd', 'pyds')
RECEIVING_METRICS = ('targets', 'receptions', 'receiving_yards',
                     'receiving_td')


def qb_arrays(n_rows: int, n_draws: int, rng) -> Dict[str, np.ndarray]:
    """A quarterback draw set that satisfies every identity by construction."""
    db = rng.integers(28, 42, size=(n_rows, n_draws)).astype(float)
    sacks = rng.integers(0, 4, size=db.shape).astype(float)
    scr = rng.integers(0, 4, size=db.shape).astype(float)
    att = db - sacks - scr                      # the partition, exactly
    cmp_ = np.floor(att * rng.uniform(0.5, 0.72, size=db.shape))
    rest = att - cmp_
    itc = np.minimum(rest, rng.integers(0, 2, size=db.shape).astype(float))
    ptd = np.floor(cmp_ * rng.uniform(0.0, 0.12, size=db.shape))
    pyds = cmp_ * rng.uniform(9.0, 13.0, size=db.shape)
    pyds = np.where(cmp_ <= 0.0, 0.0, pyds)     # zero completions, zero yards
    return {'qb/db': db, 'qb/att': att, 'qb/sacks': sacks, 'qb/scr': scr,
            'qb/cmp': cmp_, 'qb/int': itc, 'qb/ptd': ptd, 'qb/pyds': pyds}


def receiving_arrays(n_rows: int, n_draws: int, rng) -> Dict[str, np.ndarray]:
    tg = rng.integers(0, 12, size=(n_rows, n_draws)).astype(float)
    rc = np.floor(tg * rng.uniform(0.4, 0.8, size=tg.shape))
    rtd = np.minimum(rc, rng.integers(0, 2, size=tg.shape).astype(float))
    ry = rc * rng.uniform(8.0, 14.0, size=tg.shape)
    ry = np.where(rc <= 0.0, 0.0, ry)
    return {'receiving/targets': tg, 'receiving/receptions': rc,
            'receiving/receiving_yards': ry, 'receiving/receiving_td': rtd}


def corrupt_qb(arrays: Dict[str, np.ndarray], row: int = 0, draw: int = 0
               ) -> Dict[str, np.ndarray]:
    """Break ONE identity: more completions than attempts, in one cell.

    Deliberately the identity that `draw_coherence.py` records as having
    actually happened in production -- 101 sealed artifacts reporting
    QB_DRAW_ACCOUNTING_HOLDS while 5,278 cells carried more completions than
    attempts. The fixture reproduces the real defect, not an invented one.
    """
    out = {k: np.array(v, copy=True) for k, v in arrays.items()}
    out['qb/cmp'][row, draw] = out['qb/att'][row, draw] + 3.0
    return out


def write(d, *, player_ids: Sequence[str], n_draws: int = 32, seed: int = 11,
          extra_arrays: Dict[str, np.ndarray] = None,
          extra_layers: Dict[str, Any] = None,
          run_id: str = 'SYNTH', game_id: str = None, status: str = 'PASS',
          corrupt: bool = False, certificate_valid: bool = True,
          omit_coherence_verdict: bool = False) -> Dict[str, Any]:
    """Write npz, manifest and run_status for a governed simulation artifact.

    `corrupt` breaks one QB identity, so the REAL checker returns
    DRAW_COHERENCE_VIOLATED and the artifact carries that verdict honestly.
    `certificate_valid=False` certifies one set of arrays and publishes a
    different one, which is the overwritten-after-the-guard failure.
    `omit_coherence_verdict` writes the old two-key run_status, so a test can
    prove that APPLICABLE_BUT_NOT_CHECKED blocks.
    """
    d = pathlib.Path(d)
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    ids = list(player_ids)
    arrays: Dict[str, np.ndarray] = {}
    arrays.update(qb_arrays(len(ids), n_draws, rng))
    arrays.update(receiving_arrays(len(ids), n_draws, rng))
    arrays.update(extra_arrays or {})

    certified = arrays
    if corrupt:
        arrays = corrupt_qb(arrays)
        certified = arrays              # certify what is actually published
    row_ids = {lay: ids for lay in ('qb', 'receiving')}
    for k in (extra_layers or {}):
        row_ids[k] = (extra_layers[k] or {}).get('row_ids') or ids

    # THE REAL CHECKER. No verdict is asserted here; whatever it says is what
    # the artifact carries.
    verdict = DC.assert_draw_coherence(arrays, team_rows={},
                                       shared_pass_live=False)

    cert = CCERT.certify(certified, row_ids=row_ids,
                         guards=sorted(DC.HARD_CHECKS))
    published = arrays
    if not certificate_valid:
        # Certify one array set, publish another: the guard ran, then the
        # values it guarded were replaced.
        published = {k: np.array(v, copy=True) for k, v in arrays.items()}
        published['qb/pyds'] = published['qb/pyds'] + 1.0
    cert_verdict = CCERT.verify(cert.value, published, row_ids=row_ids)

    np.savez(d / 'player_draws.npz',
             **{k.replace('/', '__', 1): v for k, v in published.items()})

    layers: Dict[str, Any] = {}
    for k in sorted(published):
        lay, metric = k.split('/', 1)
        layers.setdefault(lay, {'metrics': [], 'row_axis': 'gsis_id',
                                'row_ids': row_ids.get(lay, ids),
                                'shape': [len(row_ids.get(lay, ids)),
                                          n_draws]})
        layers[lay]['metrics'].append(metric)
    for k, v in (extra_layers or {}).items():
        layers[k] = v
    (d / 'player_draws_manifest.json').write_text(json.dumps(
        {'run_id': run_id, 'game_id': game_id, 'n_draws': n_draws,
         'n_matrices': len(published), 'layers': layers,
         'draw_index_semantics': {
             'across_rows': 'INDEPENDENT_STREAMS_COLUMN_ALIGNED',
             'note': 'a fixture inherits the generator\'s own declaration; '
                     'nothing here claims a shared football world'},
         'arrays': {k: {'shape': list(v.shape)}
                    for k, v in sorted(published.items())}}, indent=1))

    summary: Dict[str, Any] = {'run_id': run_id, 'status': status,
                               'n_refusals': 0}
    if not omit_coherence_verdict:
        summary['draw_coherence'] = {
            'state': verdict.state.value, 'code': verdict.code,
            'detail': verdict.detail,
            'components': (verdict.evidence or {}).get('components') or {},
            'failed': (verdict.evidence or {}).get('failed') or [],
        }
        summary['coherence_certificate'] = cert.value or {}
        summary['coherence_certificate_verdict'] = {
            'state': cert_verdict.state.value, 'code': cert_verdict.code}
    (d / 'run_status.json').write_text(json.dumps(summary, indent=1))
    return {'arrays': published, 'ids': ids, 'layers': layers,
            'coherence_code': verdict.code,
            'certificate_code': cert_verdict.code}


def attach(d, *, seed: int = 11, corrupt: bool = False,
           certificate_valid: bool = True, zero_row_ids: Sequence[str] = (),
           omit_coherence_verdict: bool = False) -> Dict[str, Any]:
    """Upgrade an npz a fixture ALREADY wrote into a governed artifact.

    The two fixtures repaired on 2026-09-23 each build their own draw set for
    their own reasons -- one zeroes an inactive player's rows, the other
    varies projections -- and rewriting those builders would have changed what
    those suites test. So this reads what they wrote, adds the quarterback
    layer the coherence checker needs, and records the REAL verdict of the
    REAL checker over the union.

    The added QB rows use the SAME row ids as the layer that was already
    there, so the row axis stays consistent and `simulation_row_mismatch`
    keeps passing.
    """
    d = pathlib.Path(d)
    man = json.loads((d / 'player_draws_manifest.json').read_text())
    arrays: Dict[str, np.ndarray] = {}
    with np.load(d / 'player_draws.npz') as z:
        for k in z.files:
            arrays[k.replace('__', '/', 1)] = np.asarray(z[k])
    layers = man.get('layers') or {}
    ids = next((v.get('row_ids') for v in layers.values() if v.get('row_ids')),
               None)
    if not ids:
        raise AssertionError(
            'attach() needs a layer carrying row_ids; an artifact without '
            'one is a different defect and must not be papered over here.')
    n_draws = int(man.get('n_draws')
                  or next(iter(arrays.values())).shape[1])
    rng = np.random.default_rng(seed)
    qb = qb_arrays(len(ids), n_draws, rng)
    # A PLAYER THE ARTIFACT ALREADY ZEROES EVERYWHERE STAYS ZEROED IN THE
    # LAYER WE ADD. `test_dfs_eligibility` zeroes an inactive player's rows on
    # purpose, and an added quarterback layer that gave him live draws would
    # have manufactured the very defect that suite exists to detect -- which
    # is exactly what happened on the first attempt. Detected from the
    # artifact rather than passed in, so no caller has to remember.
    # `zero_row_ids` is EXPLICIT because auto-detection is not enough. A
    # fixture can zero a player's OPPORTUNITY while leaving his points live
    # -- `test_dfs_eligibility` does exactly that, to reach the case the
    # audit cannot see -- and a quarterback layer with live dropbacks for
    # that player is opportunity, which moves the detection upstream and
    # silently changes what the suite proves. That happened on the first
    # attempt here. Auto-detection stays as the default for the simple case.
    named = {i for i, pid in enumerate(ids) if pid in set(zero_row_ids or ())}
    detected = {i for i, _pid in enumerate(ids)
                if arrays and all(
                    float(np.abs(np.asarray(v)[i]).sum()) == 0.0
                    for v in arrays.values()
                    if getattr(v, 'ndim', 0) == 2 and v.shape[0] == len(ids))}
    zeroed = sorted(named | detected)
    for i in zeroed:
        for k in qb:
            qb[k][i, :] = 0.0
    if corrupt:
        qb = corrupt_qb(qb, row=next((i for i in range(len(ids))
                                      if i not in zeroed), 0))
    arrays.update(qb)
    row_ids = {lay: (layers.get(lay) or {}).get('row_ids') or ids
               for lay in {k.split('/', 1)[0] for k in arrays}}
    row_ids['qb'] = ids

    verdict = DC.assert_draw_coherence(arrays, team_rows={},
                                       shared_pass_live=False)
    cert = CCERT.certify(arrays, row_ids=row_ids, guards=sorted(DC.HARD_CHECKS))
    published = arrays
    if not certificate_valid:
        published = {k: np.array(v, copy=True) for k, v in arrays.items()}
        published['qb/pyds'] = published['qb/pyds'] + 1.0
    cert_verdict = CCERT.verify(cert.value, published, row_ids=row_ids)

    np.savez(d / 'player_draws.npz',
             **{k.replace('/', '__', 1): v for k, v in published.items()})
    layers['qb'] = {'metrics': sorted(k.split('/', 1)[1] for k in qb),
                    'row_axis': 'gsis_id', 'row_ids': ids,
                    'shape': [len(ids), n_draws]}
    man['layers'] = layers
    man['n_matrices'] = len(published)
    man['arrays'] = {k: {'shape': list(v.shape)}
                     for k, v in sorted(published.items())}
    man.setdefault('draw_index_semantics', {
        'across_rows': 'INDEPENDENT_STREAMS_COLUMN_ALIGNED',
        'note': 'a fixture inherits the generator\'s own declaration'})
    (d / 'player_draws_manifest.json').write_text(json.dumps(man, indent=1))

    rp = d / 'run_status.json'
    summary = json.loads(rp.read_text()) if rp.exists() else {
        'run_id': 'SYNTH', 'status': 'PASS', 'n_refusals': 0}
    if omit_coherence_verdict:
        summary.pop('draw_coherence', None)
        summary.pop('coherence_certificate_verdict', None)
    else:
        summary['draw_coherence'] = {
            'state': verdict.state.value, 'code': verdict.code,
            'detail': verdict.detail,
            'components': (verdict.evidence or {}).get('components') or {},
            'failed': (verdict.evidence or {}).get('failed') or []}
        summary['coherence_certificate'] = cert.value or {}
        summary['coherence_certificate_verdict'] = {
            'state': cert_verdict.state.value, 'code': cert_verdict.code}
    rp.write_text(json.dumps(summary, indent=1))
    return {'coherence_code': verdict.code,
            'certificate_code': cert_verdict.code,
            'zeroed_rows': [ids[i] for i in zeroed],
            'npz_sha256': __import__('hashlib').sha256(
                (d / 'player_draws.npz').read_bytes()).hexdigest()}
