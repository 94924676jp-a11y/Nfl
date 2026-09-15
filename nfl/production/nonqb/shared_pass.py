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

from sportsplatform.governance.outcome import Cause, Outcome, State

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

# SUPERSEDED. Read this before calling `credit_to_passers`.
#
# The paragraph above is accurate and was not enough. "Attributes on the
# targeted-throw share rather than on which throw was caught" is a true
# sentence about a scheme that can hand a quarterback more completions than he
# threw attempts -- a multinomial samples a finite pool WITH replacement -- and
# can hand him passing yards in a draw where he completed nothing, because the
# yardage rides on the attempt share and never looks at the completion draw.
#
# Measured across the 121 sealed boards on 2026-09-15: 18,041 cells with yards
# on zero completions, 8,214 with cmp > att, 9,189 where cmp + int no longer
# fits inside att, 1,113 with ptd > cmp. Every one of them sits on a board
# built by this function. The 68 boards that never called it and the 3 built
# by the replacement carry zero.
#
# `football_engine.credit_passing_line` (football_engine.py:84) replaces it and
# production has called that since the R9 rebuild. This function is retained
# ONLY so the sealed boards built with it stay reproducible -- not because it
# is a supported option. Nothing new should call it.
#
# ITS BEHAVIOUR IS DELIBERATELY UNCHANGED. Fixing it in place would silently
# alter what the historical generator does and destroy the one property it is
# still kept for.
CREDIT_TO_PASSERS_STATUS = (
    'SUPERSEDED by nfl.production.nonqb.football_engine.credit_passing_line '
    '(football_engine.py:84). Retained only so the sealed boards built with '
    'it remain reproducible. Its per-quarterback split is not a box score: '
    'the counts are multinomial on the ATTEMPT share, which samples a finite '
    'pool with replacement, and the yardage rides on that same attempt share '
    'independent of the completion draw. Do not call it in new code. The '
    'affected boards are migrated by nfl/tools/passer_credit_migration.py and '
    'reported in nfl/research/v4/p4/P4_CREDIT_MIGRATION.md.')
CREDIT_TO_PASSERS_REPLACEMENT = \
    'nfl.production.nonqb.football_engine.credit_passing_line'


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

    SUPERSEDED -- see `CREDIT_TO_PASSERS_STATUS` above, and do not call this in
    new code. `football_engine.credit_passing_line` replaces it. This body is
    left exactly as the sealed boards were built with it.

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


# ---------------------------------------------------------------------------
# P9. THE PUBLISHED TARGET LEVEL IS NOT THE PARTITIONED TARGET LEVEL.
# ---------------------------------------------------------------------------
#
# WHAT CLOSES, MEASURED FIRST, SO THE DEFECT IS NOT OVERSTATED.
#
# The C3 target partition closes. `deal_targets` hands an integer targeted-
# throw budget to a multinomial over the receivers plus the named `other`
# pool, so `sum_i T_i + other == targeted` per team per draw by construction,
# and `football_engine.run_game` halts if it ever does not. Measured across
# every sealed board in this repository that ran C3 and carries a receiving
# layer -- 113 team-runs, 139,800 draws -- the residual against the throw
# budget `rint(sum qb/att)` is NEVER NEGATIVE in any draw, minimum 0.0000,
# mean +1.7651. Containment against the level the game consumed holds
# everywhere.
#
# WHAT DOES NOT, AND IT IS A PUBLICATION DEFECT RATHER THAN AN ALLOCATION ONE.
#
# `team_volume/team_targets` is D1's own, separately drawn, CONTINUOUS team
# target level. Under C3 nothing consumes it -- `football_engine` marks it
# `d1_team_targets_unused: True` in its own evidence -- and `run_forecast`
# seals it anyway, under a name that asserts it is the team's targets. So the
# board publishes one team target level and partitions a different one. On the
# same 113 team-runs:
#
#     sum of named receivers' targets == published team_targets   0 / 139,800
#     ... == rint(published)                                 10,849 / 139,800
#     ... EXCEEDS the published level              71,550 / 139,800 (51.18%)
#     worst per-draw excess over the published level                  +28.63
#
# A reader who divides a receiver's targets by the published team target level
# gets a target share above 1.0 in half the draws. Nothing in production does
# that today -- `product/board._shares` divides by the modelled pool, and
# `postgame` refuses the estimand by name -- so this is latent, not live.
#
# THIS IS THE RECEIVING ANALOGUE OF R11's THIRD RUSH CAUSE, AND ONLY THE
# THIRD. The rush repair had to fix three things; two of them are absent here.
# There is no wrong coupling quantity: the budget is the whole throw process,
# not a sub-component of it. There is no live second owner: D1's level is
# inert under C3, where A1's `designed_qb` was not inert. What remains is
# exactly cause three -- the published level is not the level partitioned.
#
# THE PRIOR FINDING, READ CORRECTLY. `stored_team_targets_is_not_the_
# denominator` reports 0 of 100,000 draws in exact agreement across 68
# team-runs (WS09 J-12, `nfl/research/v2/d6/D6_CONSERVATION_DASHBOARD.md:291`).
# Read as "the target partition does not close" that is a MIS-SPECIFIED
# COMPARISON: it compares a published-but-unused draw against a quantity no
# partition consumed either, and it never gated anything. Read as what its own
# name says -- a gauge on a second owner that is published and unused -- it is
# correctly specified, and the number it reports is the size of the
# publication defect above, not of an allocation defect.
PUBLISHED_TARGET_LEVEL_STATUS = (
    'NOT_THE_PARTITIONED_LEVEL. Under C3 the receiving target partition is '
    'dealt from the throw process (`targeted_throws`), and `team_volume/'
    'team_targets` -- D1`s separately drawn continuous level -- is sealed '
    'beside it unused. Named receivers exceed the published level in 71,550 '
    'of 139,800 draws across 113 sealed C3 team-runs, by up to 28.63 targets, '
    'and agree with it exactly in 0. Containment against the level the game '
    'ACTUALLY consumed holds in every one of those draws with a non-negative '
    'residual. Repairing the publication needs `football_engine.run_game` to '
    'return the composed vectors and `run_forecast` to seal them, neither of '
    'which this module owns.')

# The four vectors of the target identity, named once. Three of the four are
# absent from every sealed board, which is why the identity is checkable today
# only in its weak form (`sum targets <= throws`) and not in its exact one.
TARGET_IDENTITY = ('throws == untargeted + sum_i targets_i + other, per team '
                   'per draw, exactly. `throws` is recoverable from a sealed '
                   'board as rint(sum qb/att); `untargeted`, `targeted` and '
                   '`other` are NOT SEALED by any board in this repository.')
TARGET_VECTORS_NOT_SEALED = ('targeted', 'untargeted', 'other')


def compose_pass_event_ownership(att_by_team, share, other, starts, counts,
                                 rate, rng) -> Outcome:
    """THE WHOLE TARGET COMPOSITION, in one named function with one owner.

    `targeted_throws` and `deal_targets` were already correct and are called
    here UNCHANGED, in the same order, on the same generator. What did not
    exist was a single place that holds all four vectors of the identity at
    once and states which of them a board must publish. Splitting them across
    a call site is how the rush composition came apart, and the two halves of
    this one are already one step from drifting: `football_engine` keeps
    `tgt_vol` and `c3_other` as locals, reduces them to means for its evidence
    block, and discards the vectors.

    NOTHING IS CLIPPED, TRUNCATED OR RENORMALISED, and no drawn value moves.
    This composes existing calls; it does not replace an estimator, so it is
    not a new configuration identity on its own. Sealing what it returns IS a
    change to what the board publishes and needs one.

    Returns, per team index, the four vectors of TARGET_IDENTITY plus
    `published_level` -- the vector a board must seal as the team target
    level, which is `targeted`, because that is the one the partition
    consumed.
    """
    n_teams = len(starts)
    if n_teams != len(counts) or n_teams != len(att_by_team):
        return Outcome.fail(
            'PASS_EVENT_TEAM_SHAPE_MISMATCH',
            f'{len(att_by_team)} attempt block(s), {len(starts)} start(s) and '
            f'{len(counts)} count(s). These index the same teams; a mismatch '
            f'is refused rather than zipped to the shortest.')
    tgt = []
    for k, a in enumerate(att_by_team):
        if a is None:
            return Outcome.fail(
                'PASS_EVENT_TEAM_HAS_NO_PASSER',
                f'team index {k} carries no quarterback attempt block. The '
                f'throw budget IS the attempts, so this is not a team with '
                f'zero targets, it is a team with no budget at all.', team=k)
        o = targeted_throws(a, rate, rng)
        if o.state is not State.PASS:
            return o
        tgt.append(o.value)
    dealt = deal_targets(share, other, [x['targeted'] for x in tgt],
                         starts, counts, rng)
    if dealt.state is not State.PASS:
        return dealt
    T = dealt.value['targets']
    per_team = np.stack([np.asarray(T[s0:s0 + c].sum(0), np.int64)
                         if c else np.zeros(len(tgt[k]['targeted']), np.int64)
                         for k, (s0, c) in enumerate(zip(starts, counts))])
    targeted = np.stack([np.asarray(x['targeted'], np.int64) for x in tgt])
    untargeted = np.stack([np.asarray(x['untargeted'], np.int64) for x in tgt])
    throws = np.stack([np.asarray(x['throws'], np.int64) for x in tgt])
    other_out = np.asarray(dealt.value['other'], np.int64)
    # BOTH HALVES OF THE IDENTITY, ASSERTED SEPARATELY, so a failure names the
    # half it is in rather than a single summed number that names neither.
    bad_partition = int((per_team + other_out != targeted).sum())
    bad_budget = int((targeted + untargeted != throws).sum())
    if bad_partition or bad_budget:
        return Outcome.fail(
            'PASS_EVENT_OWNERSHIP_DOES_NOT_CLOSE',
            f'the target identity fails in {bad_partition} partition cell(s) '
            f'(sum_i targets_i + other != targeted) and {bad_budget} budget '
            f'cell(s) (targeted + untargeted != throws). This is a '
            f'construction, so a deviation is a defect and never a tolerance '
            f'to widen.',
            partition_violating_cells=bad_partition,
            budget_violating_cells=bad_budget)
    return Outcome.ok(
        'PASS_EVENT_OWNERSHIP_COMPOSED',
        value={'targets': T, 'other': other_out, 'targeted': targeted,
               'untargeted': untargeted, 'throws': throws,
               'published_level': targeted},
        detail=f'{n_teams} team(s), {throws.shape[1]} draw(s); every throw '
               f'owned exactly once by a receiver, the other pool or the '
               f'untargeted pool',
        identity=TARGET_IDENTITY,
        partition_violating_cells=0, budget_violating_cells=0,
        published_level_is='targeted -- the level the partition consumed, '
                           'NOT D1`s team_volume/team_targets',
        not_sealed_by_any_board=list(TARGET_VECTORS_NOT_SEALED),
        no_clip_truncation_or_renormalisation=True)


def assert_target_ownership_closure(teams, published_level, named_targets,
                                    other_pool=None, untargeted=None,
                                    tolerance=0.0) -> Outcome:
    """Named target owners against the PUBLISHED team target level, DECOMPOSED.

    WHY DECOMPOSED. `conservation.target_view` emits three separate rows and
    still cannot say which side moved, because two of them share a right-hand
    side that is neither the published level nor the partitioned one. A single
    summed check aimed the rush repair at the wrong layer; this returns every
    series it measured, always, and a refusal carries all of them.

    WHICH QUANTITY AND WHICH SIDE, explicitly:

        named_only      receivers alone against the published level
        named_plus_other    receivers + the unmodelled-receiver pool
        full_partition  receivers + other + untargeted, which IS the identity

    Pass `published_level` as the vector the BOARD CARRIES, not the one the
    engine used. A containment check against a denominator the run did not
    seal cannot be attributed between an over-deal and a wrong vector -- which
    is the whole finding this fence exists to make visible.

    It REPAIRS NOTHING. It counts and it names. `tolerance` defaults to ZERO
    because the composition it guards makes the bound exact.
    """
    if not teams:
        return Outcome.blocked(
            'TARGET_CLOSURE_NO_TEAMS',
            'no team was supplied, so there is nothing to close. An empty '
            'check is not a passing check.', cause=Cause.DEPENDENCY)
    ev, bad = {}, []
    for t in teams:
        for name, src in (('published_level', published_level),
                          ('named_targets', named_targets)):
            if t not in src:
                return Outcome.fail(
                    'TARGET_CLOSURE_INPUT_MISSING',
                    f'no {name} for {t}. A missing vector is not a vector of '
                    f'zero, and treating it as one would report closure for a '
                    f'quantity nobody measured.', team=t, input=name)
        lvl = np.asarray(published_level[t], np.float64).reshape(-1)
        nt = np.asarray(named_targets[t], np.float64)
        nt = nt.sum(0) if nt.ndim == 2 else nt.reshape(-1)
        op = (np.zeros_like(lvl) if other_pool is None or t not in other_pool
              else np.asarray(other_pool[t], np.float64).reshape(-1))
        ut = (np.zeros_like(lvl) if untargeted is None or t not in untargeted
              else np.asarray(untargeted[t], np.float64).reshape(-1))
        if not (lvl.size == nt.size == op.size == ut.size):
            return Outcome.fail(
                'TARGET_CLOSURE_DRAW_MISMATCH',
                f'{t}: level {lvl.size}, named {nt.size}, other {op.size}, '
                f'untargeted {ut.size}. These share one draw index; a '
                f'mismatch is refused rather than broadcast.', team=t)
        e_named, e_both = nt - lvl, nt + op - lvl
        e_full = nt + op + ut - lvl
        rec = {
            'n_draws': int(lvl.size),
            'named_only_draws_over': int((e_named > tolerance).sum()),
            'named_only_max_excess': float(e_named.max()),
            'named_plus_other_draws_over': int((e_both > tolerance).sum()),
            'named_plus_other_max_excess': float(e_both.max()),
            'full_partition_draws_not_exact':
                int((np.abs(e_full) > tolerance).sum()),
            'full_partition_max_abs': float(np.abs(e_full).max()),
            'exact_agreement_draws': int((np.abs(e_named) <= tolerance).sum()),
            'level_is_integer':
                bool(not (np.abs(lvl - np.rint(lvl)) > 1e-9).any()),
            'other_pool_supplied': other_pool is not None and t in other_pool,
            'untargeted_supplied': untargeted is not None and t in untargeted}
        ev[t] = rec
        if rec['full_partition_draws_not_exact']:
            bad.append((t, 'full_partition',
                        rec['full_partition_draws_not_exact'],
                        rec['full_partition_max_abs']))
        elif rec['named_plus_other_draws_over']:
            bad.append((t, 'named_plus_other',
                        rec['named_plus_other_draws_over'],
                        rec['named_plus_other_max_excess']))
    if bad:
        return Outcome.fail(
            'TARGET_OWNERSHIP_DOES_NOT_CLOSE',
            'the target partition does not close on the PUBLISHED level: '
            + '; '.join(f'{t} {side} in {n} draw(s), worst {w:.4f}'
                        for t, side, n, w in bad)
            + '. Which side moved is named above; do not widen a tolerance.',
            violations=bad, per_team=ev)
    return Outcome.ok(
        'TARGET_OWNERSHIP_CLOSES', value=ev,
        detail=f'{len(teams)} team(s): every named receiver target, the '
               f'unmodelled-receiver pool and the untargeted pool are '
               f'contained by the published team target level',
        per_team=ev, tolerance=float(tolerance))
