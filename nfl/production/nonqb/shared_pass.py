"""XL1: the shared passing event, generated once.

Pre-registered under `nfl/research/xl1/predeclaration_xl1.md`. Two candidates,
neither promoted:

    C1  receiver-owned derivation. The receiving chain is untouched and the QB's
        completions, passing yards and passing touchdowns are DERIVED from it.
    C3  event-owned construction. The targeted-throw budget comes from the QB
        layer's own attempt multinomial, the throws are dealt to receivers by
        the existing target simplex, and RC1 and TD2 then run UNCHANGED on that
        budget. All three identities then hold by construction.

C3 changes exactly one input to the receiving chain -- the target vector -- and
calls `layers.receiving_conversion` and `layers.td_layer` with no modification.
A candidate that reimplemented them would be testing itself.

NOTHING HERE IS PROMOTED. `SHARED_PASS_DEFAULT` is 'off' and the production
default is B0.
"""
from __future__ import annotations

import json
import os

import numpy as np

from sportsplatform.governance.outcome import Cause, Outcome

SPEC_VERSION = 'xl1-shared-pass-1'
GOVERNANCE = ('CANDIDATE -- pre-registered, exploratory, NOT promoted and not '
              'prospectively validated')
PREDECLARATION = 'nfl/research/xl1/predeclaration_xl1.md'
PREDECLARATION_SHA256 = \
    '60fe3fbc0f35933e7bd4b43c56fb0afb68d95de67b4f51699a878ceb488d94da'

MODES = ('off', 'c1', 'c3')
SHARED_PASS_DEFAULT = 'off'

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_HISTORY = os.path.join(_ROOT, 'nfl', 'research', 'xl1',
                        'history_levels.json')

# The per-QB credit inside a draw where more than one quarterback threw is a
# PROPORTIONAL attribution, not an event-level one: counts split multinomially
# on the targeted-throw share, yardage splits on the same share. The team
# identity is exact either way; the attribution is exact whenever one
# quarterback threw every pass in that draw, which is the ordinary case. Named
# here rather than left for a reader to discover.
PER_QB_CREDIT = ('PROPORTIONAL_ATTRIBUTION -- exact at team level in every '
                 'draw, and exact per quarterback in any draw with a single '
                 'passer. A draw with two passers attributes on the '
                 'targeted-throw share rather than on which throw was caught.')


def untargeted_rate() -> Outcome:
    """The share of throws with no intended receiver: throwaways and spikes.

    ESTIMATED, never assumed. Refuses by name if the historical artifact that
    carries it is absent, because a rate invented here would be exactly the
    silent constant the project logs as a bug.
    """
    if not os.path.exists(_HISTORY):
        return Outcome.blocked(
            'UNTARGETED_RATE_NOT_ESTIMATED',
            f'{_HISTORY} is absent, so the untargeted-throw rate has no '
            f'empirical anchor. It is refused rather than assumed.',
            cause=Cause.DATA, wanted=_HISTORY)
    with open(_HISTORY) as fh:
        h = json.load(fh)
    tgm = h.get('team_game_means') or {}
    throws, gap = tgm.get('throws'), tgm.get('throws_minus_targets')
    if not throws or gap is None:
        return Outcome.fail(
            'UNTARGETED_RATE_MALFORMED',
            'the history artifact carries no throws / throws_minus_targets '
            'pair; a rate cannot be stated from it')
    u = float(gap) / float(throws)
    if not 0.0 <= u < 0.5:
        return Outcome.fail(
            'UNTARGETED_RATE_OUT_OF_RANGE',
            f'estimated untargeted-throw rate {u:.6f} is not a plausible '
            f'share of throws. Refused rather than clipped.', rate=u)
    return Outcome.ok(
        'UNTARGETED_RATE', value=u,
        detail=f'{u:.6f} of throws carry no intended receiver',
        source=os.path.relpath(_HISTORY, _ROOT),
        seasons=h.get('seasons'), n_team_games=h.get('n_team_games'),
        mean_throws_per_team_game=throws,
        mean_untargeted_per_team_game=gap,
        estimated_not_assumed=True)


def targeted_throws(att_by_qb, rate, rng) -> Outcome:
    """Team targeted-throw budget per draw, from the QB attempt multinomial.

    `att_by_qb` is (n_qb, m). Untargeted throws are a NAMED pool drawn from the
    throw budget, never a residual left over from something else.
    """
    A = np.asarray(att_by_qb, float)
    if A.ndim != 2 or not A.size:
        return Outcome.fail('THROW_BUDGET_EMPTY',
                            f'attempt draws have shape {A.shape}; a team with '
                            f'no quarterback row has no throw budget')
    if (A < -1e-9).any():
        return Outcome.fail('THROW_BUDGET_NEGATIVE',
                            'a negative attempt count reached the throw '
                            'budget. Refused rather than clipped.')
    throws = np.rint(A.sum(0)).astype(int)
    untargeted = rng.binomial(throws, float(rate))
    tt = throws - untargeted
    if (tt < 0).any():
        return Outcome.fail('TARGETED_THROWS_NEGATIVE',
                            'untargeted throws exceeded the throw budget')
    return Outcome.ok(
        'TARGETED_THROWS', value={'throws': throws, 'untargeted': untargeted,
                                  'targeted': tt},
        detail=f'{throws.mean():.3f} throws, {untargeted.mean():.3f} '
               f'untargeted, {tt.mean():.3f} targeted per draw',
        mean_throws=float(throws.mean()), mean_targeted=float(tt.mean()),
        mean_untargeted=float(untargeted.mean()),
        untargeted_is_a_named_pool=True)


def deal_targets(share, other, targeted, starts, counts, rng) -> Outcome:
    """Deal each targeted throw to a receiver by the EXISTING target simplex.

    `share` is (n_players, m) and `other` is (n_teams, m): the mass held by
    players outside the modelled set. Both come from the unchanged allocation
    layer. This replaces `T = share * team_target_volume`, which multiplied a
    share by a separately drawn volume and then rounded -- two independent
    draws of one football quantity, and a continuous product where a count
    belongs.

    Receiver competition is preserved exactly: the probability vector is the
    simplex itself. Only the denominator changes.
    """
    S = np.asarray(share, float)
    O = np.asarray(other, float)
    n, m = S.shape
    T = np.zeros((n, m), int)
    other_out = np.zeros(O.shape, int)
    for k, (s0, c) in enumerate(zip(starts, counts)):
        tt = np.asarray(targeted[k], int)
        if c == 0:
            other_out[k] = tt
            continue
        p = np.empty((c + 1, m), float)
        p[:c] = S[s0:s0 + c]
        p[c] = O[k]
        tot = p.sum(0)
        if (tot <= 0).any():
            return Outcome.fail(
                'TARGET_SIMPLEX_DEGENERATE',
                f'team index {k}: the target simplex sums to zero in '
                f'{int((tot <= 0).sum())} draw(s); a throw cannot be dealt')
        p = p / tot
        for j in range(m):
            T[s0:s0 + c, j], other_out[k, j] = \
                rng.multinomial(int(tt[j]), p[:, j])[:c], 0
            other_out[k, j] = int(tt[j]) - int(T[s0:s0 + c, j].sum())
    return Outcome.ok(
        'TARGETS_DEALT', value={'targets': T, 'other': other_out},
        detail=f'{n} receiver row(s), {m} draw(s); every targeted throw dealt '
               f'to exactly one receiver or to the named other-player pool',
        mean_targets_per_draw=float(T.sum(0).mean()),
        mean_other_per_draw=float(other_out.sum(0).mean()),
        competition_preserved='the multinomial probability vector IS the '
                              'existing simplex; only the denominator changed')


def credit_to_passers(att_by_qb, team_cmp, team_pyds, team_ptd,
                      rng) -> Outcome:
    """Split derived team passing totals among that team's quarterbacks.

    Counts split multinomially on the targeted-throw share so they sum EXACTLY;
    yardage splits on the same share. See PER_QB_CREDIT for what this is and is
    not.
    """
    A = np.asarray(att_by_qb, float)
    nq, m = A.shape
    tot = A.sum(0)
    w = np.where(tot > 0, A / np.where(tot > 0, tot, 1.0), 1.0 / max(nq, 1))
    cmp_q = np.zeros((nq, m), float)
    ptd_q = np.zeros((nq, m), float)
    for j in range(m):
        cmp_q[:, j] = rng.multinomial(int(round(float(team_cmp[j]))), w[:, j])
        ptd_q[:, j] = rng.multinomial(int(round(float(team_ptd[j]))), w[:, j])
    pyds_q = w * np.asarray(team_pyds, float)[None, :]
    for name, got, want in (('completions', cmp_q.sum(0), team_cmp),
                            ('passing_td', ptd_q.sum(0), team_ptd),
                            ('passing_yards', pyds_q.sum(0), team_pyds)):
        bad = int((np.abs(got - np.asarray(want, float)) > 1e-6).sum())
        if bad:
            return Outcome.fail(
                'PASSER_CREDIT_DOES_NOT_CLOSE',
                f'{name}: {bad} draw(s) where the per-quarterback split does '
                f'not sum to the team total. Refused rather than adjusted.',
                metric=name, n_bad=bad)
    return Outcome.ok(
        'PASSER_CREDIT', value={'cmp': cmp_q, 'pyds': pyds_q, 'ptd': ptd_q},
        detail=f'{nq} quarterback row(s) credited from the team totals',
        attribution=PER_QB_CREDIT,
        single_passer_draws=int((A > 0).sum(0).max(initial=0) and
                                ((A > 0).sum(0) == 1).sum()),
        n_draws=int(m))


def identity_report(team_cmp, team_pyds, team_ptd, recv_R, recv_Y,
                    recv_TD) -> Outcome:
    """The three identities, checked on the same draw index. Never clipped."""
    checks = (('completions', np.asarray(team_cmp, float),
               np.asarray(recv_R, float).sum(0)),
              ('passing_yards', np.asarray(team_pyds, float),
               np.asarray(recv_Y, float).sum(0)),
              ('passing_td', np.asarray(team_ptd, float),
               np.asarray(recv_TD, float).sum(0)))
    ev, viol = {}, []
    for name, lhs, rhs in checks:
        d = np.abs(lhs - rhs)
        bad = int((d > 1e-6).sum())
        ev[f'{name}_violating_draws'] = bad
        ev[f'{name}_mean_abs_diff'] = round(float(d.mean()), 6)
        ev[f'{name}_n_draws'] = int(d.size)
        if bad:
            viol.append((name, bad, round(float(d.max()), 4)))
    if viol:
        return Outcome.fail(
            'SHARED_PASS_IDENTITY_VIOLATED',
            'the shared passing event does not close: '
            + '; '.join(f'{n} in {b} draw(s), worst {w}' for n, b, w in viol),
            violations=viol, **ev)
    return Outcome.ok('SHARED_PASS_IDENTITY_EXACT', value=ev,
                      detail='completions, passing yards and passing '
                             'touchdowns agree in every draw',
                      **ev)
