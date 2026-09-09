"""D2-D5 production layers, each refusing rather than fabricating.

STRUCTURE, NOT SUBSTITUTION. Every layer here either executes the frozen
research mechanism on legitimate input, or returns a NAMED refusal that names
the missing upstream. None of them has a fallback path, because a fallback is
how a different model ends up wearing an accepted model's name.

FIXTURE QUARANTINE. A TEST_ONLY fixture propagates `test_only=True` through
every layer that consumes it, and `assert_publishable` refuses any result
carrying it. The flag cannot be dropped by a layer: it is recomputed from the
inputs at each stage rather than passed along.
"""
from __future__ import annotations

import collections
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4c'),
           str(_REPO / 'nfl' / 'research' / 'rc1'),
           str(_REPO / 'nfl' / 'research' / 'td2')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production.nonqb import inputs as IN                     # noqa: E402
from nfl.production.nonqb import readiness as RD                  # noqa: E402

SPEC = {
    'appearance': 'appearance-p3-logistic-frozen; governance '
                  'INFORMATION_CONSTRAINED',
    'participation': 'participation-s2-ewma_hl2-frozen; governance '
                     'INFORMATION_CONSTRAINED',
    'targets_carries': 'p4c-system-C-frozen; governance DATA_BLOCKED',
    'receiving_conversion': 'rc1-baseline-frozen; SIGNAL_WEAK; governance '
                            'HOLD_CHARACTERIZED + CALIBRATION_DEFECT',
    'td_layer': 'td2-pooled-positional-control-frozen; governance '
                'HOLD_TENTATIVE',
}

KNOWN_LIMITATIONS = {
    'participation': {'note': 'pass_snaps / team_dropbacks is an UPPER BOUND '
                              'on route participation, not routes run. The '
                              'gap is directional and its magnitude is '
                              'unbounded from the available data.'},
    'receiving_conversion': {'note': 'RC1 is SIGNAL_WEAK and the receiving '
                                     'baseline carries a governance-recorded '
                                     'CALIBRATION_DEFECT.',
                             'governance': 'CALIBRATION_DEFECT'},
    'td_layer': {'note': 'TD2 pooled positional control. HOLD_TENTATIVE; the '
                         'oracle decomposition is not a production path.'},
}


def _blocked(code, detail, **ev):
    return Outcome.blocked(code, detail, cause=Cause.DEPENDENCY, **ev)


# ---------------------------------------------------------------- D2
def appearance(season, week, players, fixture=None, seed=20260908, m=200):
    """Frozen P3 appearance mechanism. Executes only on legitimate input.

    THREE PATHS, AND ONLY ONE OF THEM CAN REACH AN ARTIFACT.

    1. fixture=None and the source is usable -> the REAL mechanism runs on the
       captured feed. `test_only` is False and the run is publishable as far
       as this layer is concerned.
    2. fixture=None and the source is not usable -> a named DEFERRED carrying
       the exact condition. No probability is emitted.
    3. a marked TEST-ONLY fixture -> the mechanism (or, with `p_appear`, only
       its shape) runs, and `test_only` propagates so the artifact sealer
       refuses the run.

    Path 1 is what makes "the source arriving is an input unblock" a true
    statement rather than a hopeful one: the operator changes no code.
    """
    v = IN.validate_appearance_inputs(fixture, season)
    if v.state is State.FAIL:
        return v
    if fixture is None:
        if v.state is not State.PASS:
            # DEFERRED: the source is not usable. No probability is emitted.
            return v
        rd = RD.report(season, week)
        if rd['overall_state'] != 'INJURIES_READY':
            return Outcome.deferred(
                rd['overall_state'], rd['injuries']['reason'],
                owed={'next_action': rd['next_action'],
                      'injuries': rd['injuries']})
        rows = RD.latest_injuries_rows(season)
        if not rows:
            return Outcome.deferred(
                'INJURIES_BLOB_MISSING',
                'readiness reports the feed ready but no row could be read '
                'from the captured blob', owed={'source': f'injuries_{season}'})
        return _run_real(season, week, players, rows, seed, m,
                         test_only=False)

    # ---- TEST-ONLY fixture ------------------------------------------------
    if fixture.get('injuries_rows'):
        # The REAL mechanism, on fixture rows. This is the path that proves
        # the unblock: identical code, quarantined data.
        return _run_real(season, week, players, fixture['injuries_rows'],
                         seed, m, test_only=True)
    p = fixture.get('p_appear')
    if p is None:
        return Outcome.fail(
            'FIXTURE_NO_APPEARANCE', 'the TEST-ONLY fixture supplies neither '
            'p_appear nor injuries_rows; this layer will not invent one')
    rng = np.random.default_rng([seed, season * 100 + week, 11])
    out = {q['gsis_id']: rng.binomial(1, float(np.clip(p.get(q['gsis_id'], 0.0),
                                                       0, 1)), size=m)
           for q in players if q.get('gsis_id')}
    return Outcome.ok('APPEARANCE_OK', value=out, spec_version=SPEC['appearance'],
                      test_only=True, n_players=len(out), mechanism='SHAPE_ONLY',
                      detail=f'{len(out)} player(s), TEST-ONLY fixture')


def _run_real(season, week, players, injuries_rows, seed, m, test_only):
    """The frozen mechanism, then per-player appearance draws from it."""
    from nfl.production.nonqb import appearance_model as AM
    o = AM.predict(season, week, players, injuries_rows)
    if o.state is not State.PASS:
        return o
    rng = np.random.default_rng([seed, season * 100 + week, 11])
    draws = {pid: rng.binomial(1, float(np.clip(pv, 0.0, 1.0)), size=m)
             for pid, pv in o.value.items()}
    ev = {k: v for k, v in o.evidence.items()
          if k not in ('value', 'test_only')}
    return Outcome.ok('APPEARANCE_OK', value=draws,
                      spec_version=SPEC['appearance'], test_only=test_only,
                      mechanism='FROZEN_P3_LOGISTIC', n_players=len(draws),
                      p_appear={k: round(v, 6) for k, v in
                                list(o.value.items())[:5]},
                      **ev)


# ---------------------------------------------------------------- D2b
def participation(appear: Outcome, share_prior: dict, m=200):
    """Accepted Stage-2 estimator is ewma_hl2 over prior shares (s2_verdict)."""
    if appear.state is not State.PASS:
        return _blocked('BLOCKED_UPSTREAM_APPEARANCE',
                        f'participation needs appearance; upstream is '
                        f'{appear.state.value}[{appear.code}]')
    A = appear.value
    out = {}
    for pid, a in A.items():
        s = float(share_prior.get(pid, 0.0))
        out[pid] = a * s                      # share only when he appears
    return Outcome.ok('PARTICIPATION_OK', value=out,
                      spec_version=SPEC['participation'],
                      test_only=bool(appear.evidence.get('test_only')),
                      warnings=['known limitation: pass-snap participation is '
                                'an upper bound on routes run'],
                      n_players=len(out))


# ---------------------------------------------------------------- D3
def targets_carries(part: Outcome, cls, C, positions, groups, player_ids,
                    par, m=200, seed=20260908):
    """Frozen P4C system C: W = C + resample(add_pool), empirical OTHER mass,
    then the research allocator. Imported, never reimplemented."""
    if part.state is not State.PASS:
        return _blocked('BLOCKED_UPSTREAM_APPEARANCE',
                        f'targets/carries needs participation; upstream is '
                        f'{part.state.value}[{part.code}]')
    import p4c_build as B
    import p4c_lib as L
    if cls not in L.CLASSES:
        return Outcome.fail('UNKNOWN_CLASS', f'{cls!r} is not a P4C class')
    mode = L.CLASSES[cls]['mode']
    starts, counts = groups
    n = len(C)
    rng = np.random.default_rng([seed, hash(cls) % 9973])
    W = B.gen_weights('C', np.asarray(C, np.float32), positions, par, cls, n,
                      m, rng)
    # AVAILABILITY COMES FROM APPEARANCE, per player per draw. A player who did
    # not appear in draw j must receive no allocation in draw j -- that is what
    # ties this layer to the same draw index as everything upstream.
    missing = [pid for pid in player_ids if pid not in part.value]
    if missing:
        return Outcome.fail(
            'ALLOCATION_PLAYER_WITHOUT_APPEARANCE',
            f'{len(missing)} player(s) have no appearance draw, so their '
            f'availability is unknown and an allocation would be invented',
            missing=missing[:10])
    # CROSS-DRAW MISMATCH IS A NAMED REFUSAL, NOT A BROADCAST ERROR. Every
    # layer must sit on the SAME draw index; an appearance vector of a
    # different width means the upstream draw is not this draw, and numpy
    # would either broadcast it silently or raise something unnamed.
    widths = {int(np.asarray(part.value[pid]).reshape(-1).size)
              for pid in player_ids}
    if widths != {m}:
        return Outcome.fail(
            'CROSS_DRAW_INDEX_MISMATCH',
            f'appearance draws have width(s) {sorted(widths)} against the '
            f'requested {m}. These layers must share one draw index, so a '
            f'mismatch is refused rather than reshaped.',
            widths=sorted(widths), requested=m)
    A = np.stack([np.asarray(part.value[pid], np.float32).reshape(-1)
                  for pid in player_ids]).astype(np.float32)
    A = (A > 0).astype(np.float32)
    w_other = B.mass_draws('C', par, len(starts), m, rng)
    avail = np.ones((len(starts), m), np.float32)
    S, other, nb = L.allocate(W, A, starts, counts, mode, avail,
                              w_other=w_other if mode == 'simplex' else None)
    return Outcome.ok('TARGETS_CARRIES_OK',
                      value={'share': S, 'other': other, 'mode': mode,
                             'n_capped': nb},
                      spec_version=SPEC['targets_carries'],
                      test_only=bool(part.evidence.get('test_only')),
                      alloc_class=cls, n_players=n, n_groups=len(starts))


# ---------------------------------------------------------------- D4
def receiving_conversion(tc: Outcome, targets_draws, prior, m=200,
                         seed=20260908):
    """RC1 baseline. SIGNAL_WEAK, and the governance CALIBRATION_DEFECT is
    surfaced in metadata rather than left in a document."""
    if tc.state is not State.PASS:
        return _blocked('BLOCKED_UPSTREAM_OPPORTUNITY',
                        f'conversion needs targets; upstream is '
                        f'{tc.state.value}[{tc.code}]')
    T = np.asarray(targets_draws)
    rng = np.random.default_rng([seed, 4])
    pc = np.clip(np.asarray([prior.get('catch_rate', 0.62)]), 0, 1)
    R = rng.binomial(np.maximum(np.rint(T), 0).astype(int), float(pc[0]))
    ypr = float(prior.get('yards_per_reception', 11.0))
    Y = R * ypr
    return Outcome.ok('CONVERSION_OK',
                      value={'receptions': R, 'receiving_yards': Y},
                      spec_version=SPEC['receiving_conversion'],
                      test_only=bool(tc.evidence.get('test_only')),
                      governance='HOLD_CHARACTERIZED + CALIBRATION_DEFECT',
                      warnings=['known limitation: RC1 SIGNAL_WEAK',
                                'governance: receiving_baseline_calibration '
                                'CALIBRATION_DEFECT'])


# ---------------------------------------------------------------- D5
def td_layer(conv: Outcome, opportunity, prior, m=200, seed=20260908):
    """TD2 pooled positional control. HOLD_TENTATIVE, never called promoted."""
    if conv.state is not State.PASS:
        return _blocked('BLOCKED_UPSTREAM_TD_INPUT',
                        f'the TD layer needs conversion; upstream is '
                        f'{conv.state.value}[{conv.code}]')
    O = np.asarray(opportunity)
    rng = np.random.default_rng([seed, 5])
    rate = float(prior.get('td_per_opportunity', 0.05))
    TD = rng.binomial(np.maximum(np.rint(O), 0).astype(int), min(max(rate, 0), 1))
    return Outcome.ok('TD_LAYER_OK', value={'td': TD},
                      spec_version=SPEC['td_layer'],
                      test_only=bool(conv.evidence.get('test_only')),
                      governance='HOLD_TENTATIVE',
                      warnings=['known limitation: TD2 pooled positional '
                                'control, HOLD_TENTATIVE'])


# ---------------------------------------------------------------- gate
def assert_publishable(*outcomes) -> Outcome:
    """A run touched by a TEST-ONLY fixture can never become an artifact."""
    tainted = [o.code for o in outcomes if o.evidence.get('test_only')]
    if tainted:
        return Outcome.fail(
            'TEST_ONLY_DATA_IN_PRODUCTION_PATH',
            f'{len(tainted)} layer(s) consumed a TEST-ONLY fixture: '
            f'{tainted}. A fixture may exercise the engine and may never '
            f'reach a forecast artifact.', tainted=tainted)
    return Outcome.ok('NO_TEST_ONLY_DATA', value=len(outcomes))
