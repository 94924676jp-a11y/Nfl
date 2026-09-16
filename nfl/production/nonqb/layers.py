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
from nfl.production import seeds as SEEDS                         # noqa: E402
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
    'rushing_td': 'td2-rush|carry-pooled-positional-control-frozen; governance '
                  'HOLD_TENTATIVE',
    'rushing_conversion': 'rushing-conversion-A-emp_tilt-stratified-1; family CARRIED_FORWARD_NOT_SELECTED; governance HOLD_TENTATIVE',
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

def _game_stream(seed_parts, game_id):
    """Append a stable per-game component, or say plainly that it is absent.

    Without it every game on a slate draws from ONE stream: measured
    bit-identical target-mass vectors and r = +0.545 appearance correlation
    between games sharing no player. `game_id=None` keeps the old vector and
    reports `game_stream_separated: False` in the outcome evidence, so a caller
    that has not been wired yet is visible rather than silently colliding.
    """
    if not game_id:
        return list(seed_parts), False
    g = SEEDS.game_component(game_id)
    if g.state is not State.PASS:
        return list(seed_parts), False
    return list(seed_parts) + [int(g.value)], True

def appearance(season, week, players, fixture=None, seed=20260908, m=200,
               teams=None, kickoff_utc=None, game_id=None,
               appearance_spec='frozen', observed_before=None,
               inactive_ids=None):
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
        # READINESS IS A PER-GAME PROPERTY (R4 section G). When the caller
        # names the two teams, only those two are consulted: thirty unfiled
        # reports elsewhere on the slate say nothing about this game. Without
        # teams the slate-wide answer is used, which is strictly more
        # conservative.
        if teams:
            tr = [RD.team_readiness(season, week, t, kickoff_utc=kickoff_utc)
                  for t in teams]
            bad = [t for t in tr if not t['state'].startswith('READY')]
            if bad:
                worst = bad[0]
                return Outcome.deferred(
                    worst['state'], worst['reason'],
                    owed={'teams': [{'team': t['team'], 'state': t['state']}
                                    for t in tr],
                          'blocking_team': worst['team'],
                          'note': 'a team with no filed report is NOT a team '
                                  'with no injuries'})
        else:
            rd = RD.report(season, week)
            # THE READY STATE IS ENGINE_INPUTS_READY, NOT INJURIES_READY.
            #
            # readiness.report sets overall_state to ENGINE_INPUTS_READY when
            # nothing is blocking, and to the injuries sub-state only when
            # something IS. Comparing against 'INJURIES_READY' therefore
            # deferred precisely when the inputs were ready -- the ready
            # answer read as a refusal. It stayed hidden because every
            # production caller names `teams` and takes the per-game branch
            # above; only the slate-wide path could reach it.
            if rd['overall_state'] != 'ENGINE_INPUTS_READY':
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
                         test_only=False, appearance_spec=appearance_spec,
                         observed_before=observed_before,
                         kickoff_utc=kickoff_utc, inactive_ids=inactive_ids)

    # ---- TEST-ONLY fixture ------------------------------------------------
    if fixture.get('injuries_rows'):
        # The REAL mechanism, on fixture rows. This is the path that proves
        # the unblock: identical code, quarantined data.
        return _run_real(season, week, players, fixture['injuries_rows'],
                         seed, m, test_only=True, game_id=game_id,
                         appearance_spec=appearance_spec,
                         observed_before=observed_before,
                         kickoff_utc=kickoff_utc, inactive_ids=inactive_ids)
    p = fixture.get('p_appear')
    if p is None:
        return Outcome.fail(
            'FIXTURE_NO_APPEARANCE', 'the TEST-ONLY fixture supplies neither '
            'p_appear nor injuries_rows; this layer will not invent one')
    parts, sep = _game_stream([seed, season * 100 + week, 11], game_id)
    rng = np.random.default_rng(parts)
    out = {q['gsis_id']: rng.binomial(1, float(np.clip(p.get(q['gsis_id'], 0.0),
                                                       0, 1)), size=m)
           for q in players if q.get('gsis_id')}
    return Outcome.ok('APPEARANCE_OK', value=out, spec_version=SPEC['appearance'],
                      test_only=True, n_players=len(out), mechanism='SHAPE_ONLY',
                      game_stream_separated=sep,
                      detail=f'{len(out)} player(s), TEST-ONLY fixture')


def _run_real(season, week, players, injuries_rows, seed, m, test_only,
              game_id=None, appearance_spec='frozen', observed_before=None,
              kickoff_utc=None, inactive_ids=None):
    """The named appearance mechanism, then per-player draws from it.

    `appearance_spec` selects WHICH mechanism, and 'frozen' is the only value
    V1, R5 and R6 ever pass, so their draws are bit-identical to what they were
    before this parameter existed. 'r7' is the union-frame repair and carries
    its own spec_version into the artifact; an unrecognised name is a FAIL, not
    a quiet fallback to the frozen path.
    """
    if appearance_spec == 'frozen':
        from nfl.production.nonqb import appearance_model as AM
        o = AM.predict(season, week, players, injuries_rows)
        mech = 'FROZEN_P3_LOGISTIC'
        spec = SPEC['appearance']
    elif appearance_spec == 'frozen_2026panel':
        # THE SAME MECHANISM ON A PANEL THAT REACHES THE FORECAST SEASON.
        # Not a new model: identical coefficients, identical featuriser. What
        # changes is that a player's PREVIOUS GAME is his previous game.
        # Without the injection the panel ends at 2025 week 18 -- a league-wide
        # rest week -- so Josh Allen carried a 0.0 snap share into a week-2
        # forecast and scored 0.4188, and James Cook carried a 2-snap rest
        # game and scored 0.7138 against a 0.6936 training base rate.
        from nfl.production.nonqb import appearance_model as AM
        from nfl.production.nonqb import appearance_panel_2026 as AP26
        _ap = AP26.build(int(season), 1)
        if _ap.state is not State.PASS:
            return _ap
        o = AM.predict(season, week, players, injuries_rows,
                       extra_rows=_ap.value)
        mech = 'FROZEN_P3_LOGISTIC_ON_2026_PANEL'
        spec = AP26.SPEC_VERSION
    elif appearance_spec == 'r8':
        from nfl.production.nonqb import appearance_r8 as AR8
        o = AR8.predict(season, week, players, injuries_rows,
                        observed_before=observed_before,
                        kickoff_utc=kickoff_utc)
        mech = 'R8_RELIABILITY_WEIGHTED_LOGISTIC'
        spec = AR8.SPEC_VERSION
    elif appearance_spec == 'r8_w1union':
        # THE VALIDATED MECHANISM, GIVEN THE CURRENT SEASON. Same model, same
        # coefficients -- `appearance_r8.fit` trains on `s < season`, so a
        # 2026 row cannot enter a 2026 fit and `coef_sha256` is unmoved. What
        # changes is that R8's history walk reaches the forecast season.
        #
        # The rows are the UNION construction: the observed panel plus the
        # point-in-time depth chart, `appeared = 0` for a listed player with
        # no offensive snap. The panel alone runs a 0.9265 week-1 base rate
        # against a fitted 0.5390, and serving that skew moved a 100%-snap
        # starter DOWN. The union reads 0.6275, inside the 0.4856-0.7476 range
        # of the seasons the model was fitted on.
        from nfl.production.nonqb import appearance_r8 as AR8
        from nfl.production.nonqb import appearance_panel_2026 as AP26
        _u = AP26.as_union_frame_rows(int(season), 1)
        if _u.state is not State.PASS:
            return _u
        o = AR8.predict(season, week, players, injuries_rows,
                        observed_before=observed_before,
                        kickoff_utc=kickoff_utc, extra_rows=_u.value)
        mech = 'R8_RELIABILITY_WEIGHTED_LOGISTIC_ON_2026_UNION_WEEK1'
        spec = AP26.UNION_SPEC_VERSION
    elif appearance_spec == 'r7':
        from nfl.production.nonqb import appearance_r7 as AR7
        o = AR7.predict(season, week, players, injuries_rows,
                        observed_before=observed_before,
                        kickoff_utc=kickoff_utc)
        mech = 'R7_UNION_FRAME_LOGISTIC'
        spec = AR7.SPEC_VERSION
    else:
        return Outcome.fail(
            'APPEARANCE_SPEC_UNKNOWN',
            f'appearance_spec={appearance_spec!r} names no mechanism this '
            f'layer implements; falling back to the frozen one would put an '
            f'unrequested model behind a requested name',
            appearance_spec=appearance_spec)
    if o.state is not State.PASS:
        return o
    parts, sep = _game_stream([seed, season * 100 + week, 11], game_id)
    rng = np.random.default_rng(parts)
    draws = {pid: rng.binomial(1, float(np.clip(pv, 0.0, 1.0)), size=m)
             for pid, pv in o.value.items()}
    # OFFICIAL INACTIVES, APPLIED LAST AND ADDING NOTHING.
    #
    # The list is the highest-authority statement about who plays tonight
    # (registry authority_rank 1), so it overrides the model's own estimate
    # rather than being blended with it. Zeroing the appearance draws is the
    # whole intervention: `accounting.reconcile_nonqb` already enforces
    # `share == 0 wherever appearance == 0` per cell, and the P4C simplex
    # renormalises over the survivors, so the opportunity is redistributed by
    # the configuration's own declared mechanism.
    ina_ev = None
    if inactive_ids:
        from nfl.production.nonqb import inactives as INA
        ao = INA.apply_to_appearance(draws, inactive_ids)
        if ao.state is State.PASS:
            draws = ao.value
            ina_ev = {k: v for k, v in ao.evidence.items() if k != 'value'}
        else:
            ina_ev = {'state': ao.state.value, 'code': ao.code}
    ev = {k: v for k, v in o.evidence.items()
          if k not in ('value', 'test_only', 'spec_version', 'n_players')}
    if ina_ev is not None:
        ev['official_inactives'] = ina_ev
    return Outcome.ok('APPEARANCE_OK', value=draws,
                      spec_version=spec, test_only=test_only,
                      mechanism=mech, appearance_spec=appearance_spec,
                      n_players=len(draws),
                      p_appear={k: round(v, 6) for k, v in
                                list(o.value.items())[:5]},
                      game_stream_separated=sep,
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
                    par, m=200, seed=20260908, game_id=None, ordinal=None):
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
    # THE PARAMETERS ARE AN INPUT, AND AN INPUT GETS ASSERTED.
    #
    # `par` goes straight into p4c_build.gen_weights, which indexes
    # par['add_pool']. An incomplete mapping therefore raised a bare
    # KeyError -- an UNNAMED failure, which this project forbids precisely
    # because a stack trace tells a caller nothing about what to supply.
    #
    # It only became reachable when the appearance layer started running:
    # while the upstream refused, this function returned at the guard above
    # and never touched `par`. A code path that cannot execute is not a
    # working one, which is the same lesson as the content_markers defect.
    _need = ('add_pool',)
    if not isinstance(par, dict):
        return Outcome.fail(
            'P4C_PARAMS_NOT_A_MAPPING',
            f'targets/carries needs the fitted P4C parameters as a mapping; '
            f'got {type(par).__name__}')
    _missing = [k for k in _need if k not in par]
    if _missing:
        return Outcome.fail(
            'P4C_PARAMS_INCOMPLETE',
            f'the fitted P4C parameters are missing {_missing}, so the '
            f'weight generator cannot run. Refusing by name rather than '
            f'raising KeyError from inside the allocator.',
            missing=_missing, n_keys_supplied=len(par),
            p4c_class=cls)
    starts, counts = groups
    n = len(C)
    # STABLE STREAM IDENTITY. This was `hash(cls) % 9973`, and Python
    # randomises str hashing per process, so the allocation drew a different
    # stream on every run at an identical declared seed. See nfl/production/
    # seeds.py. An undeclared class is refused rather than defaulted.
    sid = SEEDS.stream_id('p4c_alloc', cls)
    if sid.state is not State.PASS:
        return sid
    # THIS VECTOR CARRIED NEITHER GAME NOR WEEK, so every game in every week
    # drew the identical allocation stream. The stream id alone is a class
    # identity, not an execution identity.
    _base = [seed, sid.value] + ([int(ordinal)] if ordinal else [])
    parts, sep = _game_stream(_base, game_id)
    rng = np.random.default_rng(parts)
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
    try:
        S, other, nb = L.allocate(W, A, starts, counts, mode, avail,
                                  w_other=w_other if mode == 'simplex'
                                  else None)
    except ValueError as exc:                                    # noqa: BLE001
        code, _, detail = str(exc).partition(': ')
        return Outcome.fail(code or 'ALLOCATION_REFUSED',
                            detail or str(exc), alloc_class=cls)
    return Outcome.ok('TARGETS_CARRIES_OK',
                      value={'share': S, 'other': other, 'mode': mode,
                             'n_capped': nb},
                      seed_contract=SEEDS.SEED_CONTRACT,
                      stream_id=sid.value,
                      n_groups_with_no_modelled_weight=(
                          nb if mode == 'simplex' else 0),
                      spec_version=SPEC['targets_carries'],
                      test_only=bool(part.evidence.get('test_only')),
                      alloc_class=cls, n_players=n, n_groups=len(starts))


# ---------------------------------------------------------------- D4
def _row_rng(seed, ordinal, pid):
    """RC1's per-row seeding: every row reproducible on its own, independent of
    what any other row consumed from the stream."""
    return np.random.default_rng(
        [seed, int(ordinal),
         int.from_bytes(str(pid).encode()[-8:], 'little')])


def receiving_conversion(tc: Outcome, targets_draws, priors, player_ids,
                         positions, ordinal, m=200, seed=20260908,
                         intercepted=None, pick_share=None):
    """RC1 baseline: shrunk catch rate, and per-catch yardage RESAMPLED.

    T is supplied by D3 rather than drawn, which is the one thing that differs
    from `rc1_sim.simulate`; C and V follow RC1's scheme exactly, including the
    shrinkage weight h_n/(h_n+K_SHRINK) and the own-versus-pool mixture.

    THE YARDAGE IS NEVER A CONSTANT PER CATCH. An earlier version of this
    function multiplied receptions by a fixed yards-per-reception, which
    collapses a distribution whose tail a Normal already understates
    thirteenfold. SIGNAL_WEAK, and the governance CALIBRATION_DEFECT is
    surfaced in metadata rather than left in a document.

    SC2 -- `intercepted` AND `pick_share`, BOTH OPT-IN AND BOTH OR NEITHER.
    With neither supplied this function is byte-identical to what every frozen
    arm has always run, which is why they are parameters and not a rewrite.

    With them, a target's outcome is treated as what it is: one of caught,
    incomplete, or intercepted, mutually exclusive on one throw. The picks are
    removed from the pool the binomial converts, and the rate is taken
    conditional on not having been picked --

        R_i ~ Binomial(T_i - int_i,  c_i / (1 - pi))

    -- so that E[R_i] = T_i (1 - pi) c_i / (1 - pi) = T_i c_i, EXACTLY the
    expectation the unreserved form had. The level does not move; only the
    joint state with the interception draw does. `pi` is measured, not chosen:
    `shared_pass.INTERCEPTION_SHARE_OF_TARGETS`.

    Re-basing the denominator WITHOUT re-basing the rate would have cut about
    0.51 receptions per team-game -- a level change wearing a coherence fix's
    clothes, which SC2's pre-registration named as the objection it had to
    answer before it was allowed to build anything.

    A rate that lands above 1 after the division is CAPPED AT 1 AND COUNTED.
    It can only happen where the shrunk own-rate is already at the boundary,
    and a cap nobody counts is the kind of silence this project keeps paying
    for.
    """
    if tc.state is not State.PASS:
        return _blocked('BLOCKED_UPSTREAM_OPPORTUNITY',
                        f'conversion needs targets; upstream is '
                        f'{tc.state.value}[{tc.code}]')
    need = ('pos_catch_rate', 'pos_yardage_pool', 'own', 'k_shrink')
    missing = [k for k in need if k not in (priors or {})]
    if missing:
        return Outcome.fail(
            'CONVERSION_PRIOR_NOT_FROZEN',
            f'the conversion priors omit {missing}. This layer implements the '
            f'RC1 baseline and will not run on a prior supplied by its '
            f'caller.', missing=missing)
    T = np.maximum(np.rint(np.asarray(targets_draws, float)), 0).astype(int)
    if T.shape != (len(player_ids), m):
        return Outcome.fail(
            'CROSS_DRAW_INDEX_MISMATCH',
            f'target draws have shape {T.shape} against '
            f'{(len(player_ids), m)}', got=list(T.shape))
    if (intercepted is None) != (pick_share is None):
        return Outcome.fail(
            'SC2_RESERVATION_HALF_SUPPLIED',
            'the interception reservation needs the dealt picks AND the '
            'share they are drawn at. One without the other would either '
            'remove throws without restoring the rate, or restore the rate '
            'without removing the throws -- both move the level.')
    INT = None
    if intercepted is not None:
        INT = np.maximum(np.rint(np.asarray(intercepted, float)),
                         0).astype(int)
        if INT.shape != T.shape:
            return Outcome.fail(
                'SC2_RESERVATION_SHAPE',
                f'reserved interceptions have shape {INT.shape} against '
                f'targets {T.shape}', got=list(INT.shape))
        if (INT > T).any():
            return Outcome.fail(
                'SC2_RESERVATION_EXCEEDS_TARGETS',
                f'{int((INT > T).sum())} cell(s) reserve more interceptions '
                f'than the receiver had targets. Refused rather than clipped.',
                n_bad=int((INT > T).sum()))
        pi = float(pick_share)
        if not 0.0 <= pi < 1.0:
            return Outcome.fail(
                'SC2_PICK_SHARE_OUT_OF_RANGE',
                f'the interception share of targets is {pi}, which is not a '
                f'share')
    K = float(priors['k_shrink'])
    R = np.zeros_like(T)
    n_rate_capped = 0
    Y = np.zeros(T.shape, float)
    used_pos_rate = 0
    for i, pid in enumerate(player_ids):
        pos = positions[i]
        rng = _row_rng(seed, ordinal, pid)
        own = priors['own'].get(pid) or {}
        h_n = float(own.get('h_n') or 0.0)
        w = h_n / (h_n + K)
        pos_rate = float(priors['pos_catch_rate'].get(pos, 0.0))
        own_rate = ((own.get('h_rec') or 0) / own['h_tgt']
                    if own.get('h_tgt') else None)
        if own_rate is None:
            c = pos_rate
            used_pos_rate += 1
        else:
            c = w * own_rate + (1 - w) * pos_rate
        c = min(max(c, 0.0), 1.0)
        if INT is None:
            R[i] = rng.binomial(T[i], c)
        else:
            c_cond = c / (1.0 - pi)
            if c_cond > 1.0:
                c_cond = 1.0
                n_rate_capped += 1
            R[i] = rng.binomial(T[i] - INT[i], c_cond)
        own_v = np.asarray(own.get('h_V_flat') or [], float)
        pool_v = np.asarray(priors['pos_yardage_pool'].get(
            pos, np.array([0.0])), float)
        total = int(R[i].sum())
        if total == 0:
            continue
        use_own = (rng.random(total) < w) if len(own_v) else np.zeros(total,
                                                                      bool)
        picks = np.where(
            use_own,
            own_v[rng.integers(0, max(len(own_v), 1), total)] if len(own_v)
            else 0.0,
            pool_v[rng.integers(0, len(pool_v), total)])
        # A draw with ZERO receptions has to yield exactly 0. np.add.reduceat
        # cannot express a zero-length segment and raises on it; a cumulative
        # sum differenced at the segment bounds returns 0 there, which is the
        # right answer rather than a borrowed neighbouring one.
        cs = np.concatenate([[0.0], np.cumsum(picks)])
        ends = np.cumsum(R[i])
        Y[i] = cs[ends] - cs[ends - R[i]]
    return Outcome.ok('CONVERSION_OK',
                      value={'receptions': R, 'receiving_yards': Y},
                      spec_version=SPEC['receiving_conversion'],
                      test_only=bool(tc.evidence.get('test_only')),
                      governance='HOLD_CHARACTERIZED + CALIBRATION_DEFECT',
                      n_players=len(player_ids),
                      n_on_positional_catch_rate=used_pos_rate,
                      k_shrink=K,
                      interception_reservation=(
                          None if INT is None else {
                              'spec_version': 'sc2-interception-reservation-1',
                              'pick_share': float(pick_share),
                              'mean_reserved_per_draw':
                                  float(INT.sum(0).mean()),
                              'n_rows_whose_rate_capped_at_one':
                                  n_rate_capped,
                              'identity': 'E[R_i] = T_i c_i is preserved: the '
                                          'rate is taken conditional on not '
                                          'having been intercepted'}),
                      warnings=['known limitation: RC1 SIGNAL_WEAK',
                                'governance: receiving_baseline_calibration '
                                'CALIBRATION_DEFECT'])


# ---------------------------------------------------------------- D5
def td_layer(conv: Outcome, targets_draws, priors, player_ids, positions,
             ordinal, m=200, seed=20260908):
    """TD2 pooled positional control (B_pos). HOLD_TENTATIVE, never promoted.

    TD2's primary estimand for receiving is touchdowns per TARGET. A receiving
    touchdown is nevertheless a catch, so drawing per target would let a draw
    score more touchdowns than it had receptions. The rate is therefore
    expressed per RECEPTION as B_pos / pos_catch_rate, which leaves the
    expected touchdown count per target unchanged and keeps the count inside
    receptions by construction. That is a stated identity, not a fitted
    constant, and a rate above one is refused rather than clipped.
    """
    if conv.state is not State.PASS:
        return _blocked('BLOCKED_UPSTREAM_TD_INPUT',
                        f'the TD layer needs conversion; upstream is '
                        f'{conv.state.value}[{conv.code}]')
    if 'B_pos' not in (priors or {}):
        return Outcome.fail(
            'TD_PRIOR_NOT_FROZEN',
            'the TD priors carry no B_pos. This layer implements the TD2 '
            'pooled positional control and will not run on a caller-supplied '
            'rate.')
    R = np.asarray(conv.value['receptions'], int)
    catch = priors.get('pos_catch_rate') or {}
    TD = np.zeros_like(R)
    rates = {}
    for i, pid in enumerate(player_ids):
        pos = positions[i]
        per_target = float(priors['B_pos'].get(pos, priors['B_league']))
        c = float(catch.get(pos, 0.0))
        if c <= 0:
            return Outcome.fail(
                'TD_RATE_UNDEFINED',
                f'no positional catch rate for {pos}, so a per-reception '
                f'touchdown rate cannot be stated', position=pos)
        rate = per_target / c
        if rate > 1.0:
            return Outcome.fail(
                'TD_RATE_ABOVE_ONE',
                f'{pos}: B_pos {per_target:.6f} over catch rate {c:.6f} is '
                f'{rate:.6f}. Refused rather than clipped.', position=pos)
        rates[pos] = round(rate, 6)
        TD[i] = _row_rng(seed, ordinal, pid).binomial(R[i], rate)
    return Outcome.ok('TD_LAYER_OK', value={'td': TD},
                      spec_version=SPEC['td_layer'],
                      test_only=bool(conv.evidence.get('test_only')),
                      governance='HOLD_TENTATIVE', baseline='B_pos',
                      per_reception_rate=rates, n_players=len(player_ids),
                      warnings=['known limitation: TD2 pooled positional '
                                'control, HOLD_TENTATIVE'])


# ---------------------------------------------------------------- D5b
def rushing_td(carries_outcome: Outcome, carry_draws, priors, player_ids,
               positions, ordinal, m=200, seed=20260908):
    """TD2 pooled positional control for `rush|carry`. Same shape as receiving.

    THE DENOMINATOR IS THE OPPORTUNITY ITSELF. TD2's primary rushing estimand
    is touchdowns per CARRY, and carries are what D3 allocates, so this needs
    none of the per-reception restatement the receiving layer needs: the draw
    is binomial on the same carry count, on the same draw index.

    A player with no carries in draw j gets no rushing touchdown in draw j,
    which is the invariant rather than a check applied afterwards.
    """
    if carries_outcome.state is not State.PASS:
        return _blocked('BLOCKED_UPSTREAM_RUSH_OPPORTUNITY',
                        f'the rushing TD layer needs a carry allocation; '
                        f'upstream is {carries_outcome.state.value}'
                        f'[{carries_outcome.code}]')
    if 'B_pos' not in (priors or {}) or (priors or {}).get('kind') != 'rush':
        return Outcome.fail(
            'TD_PRIOR_NOT_FROZEN',
            'the rushing TD priors are absent or are not the rush estimand. '
            'This layer implements the TD2 rush|carry control and will not run '
            'on a caller-supplied rate.')
    C = np.maximum(np.rint(np.asarray(carry_draws, float)), 0).astype(int)
    if C.shape != (len(player_ids), m):
        return Outcome.fail(
            'CROSS_DRAW_INDEX_MISMATCH',
            f'carry draws have shape {C.shape} against '
            f'{(len(player_ids), m)}', got=list(C.shape))
    TD = np.zeros_like(C)
    rates = {}
    for i, pid in enumerate(player_ids):
        pos = positions[i]
        rate = float(priors['B_pos'].get(pos, priors['B_league']))
        if not 0.0 <= rate <= 1.0:
            return Outcome.fail(
                'TD_RATE_ABOVE_ONE',
                f'{pos}: rushing TD rate {rate:.6f} is outside [0, 1]. '
                f'Refused rather than clipped.', position=pos)
        rates[pos] = round(rate, 6)
        TD[i] = _row_rng(seed, ordinal, pid).binomial(C[i], rate)
    return Outcome.ok('RUSHING_TD_OK', value={'rush_td': TD},
                      spec_version=SPEC['rushing_td'],
                      test_only=bool(carries_outcome.evidence.get('test_only')),
                      governance='HOLD_TENTATIVE', baseline='B_pos',
                      estimand='rush|carry', per_carry_rate=rates,
                      n_players=len(player_ids),
                      warnings=['known limitation: TD2 pooled positional '
                                'control, HOLD_TENTATIVE'])


# ---------------------------------------------------------------- D6
RUSHING_CONVERSION_DECISIONS = (
    'RUSH-DECISION-1: which distributional family the control uses for a '
    'season with no outcomes. P5A selects it by CRPS against the evaluation '
    "season's own realised yards, so the rule cannot run for 2026, and the "
    'predeclared inner-validation (Y-1) nesting was never implemented.',
    'RUSH-DECISION-2: whether promotion criterion 4 (randomised PIT within '
    '25%) is read per season or pooled. It is the only criterion system B '
    'breaches, and it breaches in one season of four. Per season, the control '
    'is the opportunity-only pool A; pooled, a player-shrunk system may be '
    'promoted instead.',
    'RUSH-DECISION-3: whether the control is the PREDECLARED '
    'position-stratified pool (RB versus non-RB) or the UNSTRATIFIED pool that '
    'was implemented. They are different distributions.',
)


def rushing_conversion(carries_outcome: Outcome, carry_draws=None,
                       priors=None, player_ids=None, positions=None,
                       ordinal=None, m=200, seed=20260908):
    """carry -> rushing yards. THE THREE DECISIONS ARE MADE; THIS NOW RUNS.

    THIS LAYER DEFERRED FOR A REASON AND THE REASON IS GONE. It returned
    RUSHING_CONVERSION_CONTROL_UNDEFINED because P5A had run without an
    adjudication: no rule named a distributional family for a season with no
    outcomes, no rule read promotion criterion 4, and the implemented pool was
    unstratified where the pre-declaration said RB versus non-RB. Those are
    scientific choices, not engineering ones, so the layer refused rather than
    picked. The owner decided all three on 2026-09-16 and
    RUSHING_CONVERSION_DECISIONS.json records them:

        family          emp_tilt, CARRIED_FORWARD_NOT_SELECTED from 2025
        system          A -- opportunity only, no shrinkage blocks
        stratification  RB versus non-RB, as predeclared

    WHAT IS STILL REFUSED. A caller-supplied efficiency prior, for the same
    reason as before: the frozen control owns those priors and a caller may
    not stand in for it. And `rushing_yards = carries x yards_per_carry`,
    which is a point where a distribution belongs. Every carry is drawn.

    THE CARRIES ARE CONSUMED, NEVER RESAMPLED. `carry_draws` is the vector the
    conserved allocation already dealt, so the yards belong to the same
    carries the accounting closed on and the rush partition stays exact.
    """
    if priors:
        # A caller-supplied efficiency prior is refused BEFORE anything else,
        # so the refusal is about ownership rather than about absence.
        return Outcome.fail(
            'RUSHING_PRIOR_NOT_OWNED_BY_CALLER',
            'a rushing efficiency prior was supplied by the caller. The frozen '
            'control owns those priors, and a caller may not stand in for it.',
            supplied=sorted(priors))
    if carries_outcome.state is not State.PASS:
        return _blocked('BLOCKED_UPSTREAM_RUSH_OPPORTUNITY',
                        f'the rushing conversion layer needs a carry '
                        f'allocation; upstream is '
                        f'{carries_outcome.state.value}'
                        f'[{carries_outcome.code}]')
    if carry_draws is None or not player_ids or positions is None \
            or ordinal is None:
        return Outcome.fail(
            'RUSHING_CONVERSION_INPUTS_ABSENT',
            'the conversion needs the dealt carry draws, the row identities '
            'and the positions that select the stratum. Running without the '
            'positions would put every carry in one pool, which is the '
            'unstratified control wearing a stratified name.',
            have={'carry_draws': carry_draws is not None,
                  'player_ids': bool(player_ids),
                  'positions': positions is not None,
                  'ordinal': ordinal is not None})
    from nfl.production.nonqb import rushing_conversion as RC

    built = RC.pools(int(ordinal))
    if built.state is not State.PASS:
        # The pool build's own refusal is passed through rather than
        # relabelled -- a missing play-by-play corpus is a DATA cause and
        # saying "conversion failed" would lose that.
        return built
    C = np.maximum(np.rint(np.asarray(carry_draws, float)), 0).astype(int)
    if C.shape != (len(player_ids), m):
        return Outcome.fail(
            'CROSS_DRAW_INDEX_MISMATCH',
            f'carry draws have shape {C.shape} against '
            f'{(len(player_ids), m)}', got=list(C.shape))
    pools_v = built.value
    Y = np.zeros(C.shape, dtype=np.float64)
    strata_used = {}
    for i, pid in enumerate(player_ids):
        pos = positions[i]
        strata_used[str(pid)] = RC._stratum(pos)
        Y[i] = RC.yards_for(C[i], pos, pools_v, seed, f'{ordinal}:{pid}')
    # EVERY CARRY HAS YARDS AND ONLY CARRIES HAVE YARDS. A row with no carry
    # in draw j must carry no yards in draw j; the reverse would be yardage
    # with no opportunity behind it.
    bad = int(((C == 0) & (Y != 0.0)).sum())
    if bad:
        return Outcome.fail(
            'RUSHING_YARDS_WITHOUT_A_CARRY',
            f'{bad} (row, draw) cell(s) carry rushing yards with zero '
            f'carries. Yardage with no opportunity behind it is not a '
            f'distribution, it is an accounting break.', n_cells=bad)
    prov = built.as_dict()['evidence']['provenance']
    return Outcome.ok(
        'RUSHING_CONVERSION_OK', value={'rushing_yards': Y},
        spec_version=RC.SPEC_VERSION,
        test_only=bool(carries_outcome.evidence.get('test_only')),
        governance='HOLD_TENTATIVE',
        family=RC.FAMILY, family_label=RC.FAMILY_LABEL, system=RC.SYSTEM,
        decisions='nfl/production/nonqb/RUSHING_CONVERSION_DECISIONS.json',
        strata={s: prov['strata'][s] for s in RC.STRATA},
        n_players=len(player_ids),
        rows_by_stratum=collections.Counter(strata_used.values()),
        carries_with_no_position=prov['carries_with_no_position'],
        position_precedence=prov['position_precedence'],
        warnings=['the family was CARRIED FORWARD from 2025, not selected for '
                  '2026 -- P5A selects by CRPS against realised yards and '
                  '2026 has none. HOLD_TENTATIVE.'])


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
