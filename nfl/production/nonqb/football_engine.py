"""The complete V1 football engine: one call, one game, one draw index.

WHAT THIS IS

R3 left the engine spread across a rehearsal script. R4 needs the same chain
run three ways -- on a TEST-ONLY injury stand-in, on the real feed, and by the
test suite -- so it lives here once and the rehearsals are thin callers. A
second copy of an engine is a second engine.

ONE DRAW INDEX. Every layer for a game shares draw column j: appearance,
participation, the targets allocation, the carries allocation, conversion, both
touchdown layers and the QB layer. Coupling is the point -- a receiver's
receptions and his team's target volume have to move together within a draw or
the joint distribution is a fiction assembled from marginals.

WHAT IS ABSENT AND WHY. `rushing_yards` has no governed control (see
rushing_inventory.json). It is emitted as an explicit ABSENT record naming the
three open decisions. It is never emitted as zero.
"""
from __future__ import annotations

import collections
import dataclasses
import pathlib
import sys
import time

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4c'),
           str(_REPO / 'nfl' / 'research' / 'qb2')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State      # noqa: E402
from nfl.production import team_volume_v1 as TV                   # noqa: E402
from nfl.production import qb_accounting as QBACC                 # noqa: E402
from nfl.production import qb_v1 as QBV1                          # noqa: E402
from nfl.production.nonqb import accounting as ACC                # noqa: E402
from nfl.production.nonqb import frozen_priors as FP              # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402
from nfl.production.nonqb import p4c_params as P4                 # noqa: E402
from nfl.production.nonqb import readiness as RD                  # noqa: E402
from nfl.production.nonqb import shared_pass as SP                # noqa: E402
from nfl.production import seeds as SEEDS                         # noqa: E402
from nfl.production.nonqb import qb_allocation as QA               # noqa: E402
from nfl.production.nonqb import participation_prior as PP        # noqa: E402
from nfl.production.nonqb import player_record as PR              # noqa: E402
from nfl.production import draw_coherence as DC                   # noqa: E402
from nfl.production import stat_contract as SCT                   # noqa: E402
from nfl.production.nonqb import rushing_a1 as RA1                # noqa: E402

# What the per-quarterback split is and is not. The counts are an exact
# combinatorial allocation of the team's own events; the YARDAGE is still a
# proportional attribution -- on the COMPLETION share rather than the attempt
# share -- and is exact in any draw with a single passer, which is the
# ordinary case. Named here rather than left for a reader to discover.
PASSER_CREDIT_ATTRIBUTION = (
    'EXACT_COMBINATORIAL for completions and passing touchdowns (each is '
    'dealt from the passer own attempts and own completions, so the '
    'allocation cannot exceed what he threw); PROPORTIONAL on the COMPLETION '
    'share for passing yards, exact at team level in every draw and exact per '
    'quarterback in any draw with a single passer.')

RECEIVING_POS = ('WR', 'TE', 'RB')
CARRY_POS = ('RB',)
ENGINE_VERSION = 'nfl-football-engine-v1-r4'

# R4. THE COUNT STREAMS, DECLARED AS LITERAL COMPONENTS.
#
# Dealing an integer budget consumes randomness, and a new draw taken from an
# EXISTING stream would move every subsequent draw of that stream -- the
# allocation, the conversion, the touchdowns -- for a reason that has nothing
# to do with any of them. Each deal therefore gets its own stream, seeded the
# way the C3 deal beside it already is: [seed, ordinal, game component,
# literal]. The literals are here, named, rather than inline, because a magic
# number written twice is two streams nobody knows are the same one.
COUNT_STREAM_CARRIES = 0xC0417
COUNT_STREAM_TARGETS = 0xC0418
COUNT_CONTRACT_VERSION = SCT.CONTRACT_VERSION


def team_completion_atoms(atom_rows, receptions, ri, m):
    """Regroup RC1's per-receiver per-catch yardages into the TEAM's per-draw
    multiset of completion yardages.

    RC1 lays each receiver's atoms out draw-major and `receptions` carries the
    segment lengths, so draw d of row i occupies `a[e - r[d]:e]` for
    `e = r[:d+1].sum()`. A team's completions in draw d are the union of those
    segments over the team's receivers, which is exactly the multiset
    `credit_passing_line` partitions.

    Returns `(per_draw, bad)`. `bad` is None on success and otherwise names
    the row whose atom count disagrees with its own reception count -- an
    impossible state that is reported rather than absorbed, because a silently
    short multiset would deal the wrong yards to a real quarterback.
    """
    vals, drw = [], []
    for i in ri:
        a = np.asarray(atom_rows[i], float).reshape(-1)
        r = np.rint(np.asarray(receptions[i], float)).astype(np.int64)
        if int(r.sum()) != a.size:
            return None, (int(i), int(r.sum()), int(a.size))
        if not a.size:
            continue
        vals.append(a)
        drw.append(np.repeat(np.arange(m), r))
    if not vals:
        return [np.zeros(0, float) for _ in range(m)], None
    A = np.concatenate(vals)
    D = np.concatenate(drw)
    # A STABLE sort, so the layout is a deterministic function of the row
    # order and not of numpy's partitioning choices. The partition shuffles
    # afterwards anyway; determinism here is what makes the run reproducible.
    order = np.argsort(D, kind='stable')
    A = A[order]
    starts = np.concatenate([[0], np.cumsum(np.bincount(D, minlength=m))])
    return [A[starts[j]:starts[j + 1]] for j in range(m)], None


def credit_passing_line(att_by_qb, int_by_qb, team_cmp, team_pyds,
                        team_ptd, rng, atoms=None, atom_rng=None) -> Outcome:
    """Split the team's passing line among that team's quarterbacks.

    WHAT WAS WRONG, AND WHY MOVING A GUARD WOULD NOT HAVE FIXED IT
    --------------------------------------------------------------
    `shared_pass.credit_to_passers` dealt the team's completions with

        w      = att_q / sum(att)              # the attempt SHARE
        cmp_q  = rng.multinomial(team_cmp, w)
        ptd_q  = rng.multinomial(team_ptd, w)
        pyds_q = w * team_pyds

    A multinomial is sampling WITH replacement. It can hand a quarterback more
    completions than he has attempts, more touchdowns than he has completions,
    and -- because the yardage rode on the ATTEMPT share rather than the
    completion share -- passing yards in a draw where he completed nothing.
    Measured on this repository's own sealed artifacts: 5,278 cells with
    cmp > att, 731 with ptd > cmp, 11,616 with yards on zero completions, and
    5,929 where the interception count no longer fitted inside the
    incompletions because the completion count had been inflated past it.

    The engine wrote all three straight over `qb['draws']` AFTER
    `qb_v1.forecast` and `qb_accounting.reconcile_draws` had already passed on
    the pre-credit values, so every sealed artifact carries
    QB_DRAW_ACCOUNTING_HOLDS over draws that violate it.

    Moving the guard later would have caught the cells. It would not have
    produced a usable forecast: a guard that fires is still a broken draw, and
    the run would simply refuse. The defect is the SAMPLING SCHEME.

    WHAT THIS DOES INSTEAD -- CONSTRUCTION, NOT REPAIR
    --------------------------------------------------
    The completions are the subset of the team's attempts that were caught. So
    deal them as what they are: a simple random sample, WITHOUT replacement,
    from the pool of attempts each quarterback actually threw --

        cmp_q ~ MultivariateHypergeometric(colors = att_q - int_q,
                                           nsample = team_cmp)

    Same assumption as the incumbent -- attempts exchangeable across the
    quarterbacks who threw them -- but the correct sampling scheme for a finite
    pool. Nothing is clipped, nothing is renormalised, no constant is
    introduced, and the team total still closes exactly, because a
    hypergeometric draw sums to `nsample` by construction.

    THE EXPECTATION MOVES A LITTLE, AND SAYING SO IS THE POINT. The incumbent
    centred on `team_cmp * att_q / sum(att)`; this centres on
    `team_cmp * (att_q - int_q) / sum(att - int)`. The two coincide only when
    every passer in the room has the same interception count per attempt, so
    reserving picks shifts credit very slightly towards the passer who threw
    fewer of them -- which is the correct direction and is a consequence of
    the reservation, not a tuning knob. Measured across all 218 quarterback
    rows in the 33 sealed shared-pass runs, replayed on identical inputs with
    identical seeds: mean shift 0.0000 completions, largest 0.0900, and the
    team mean is unchanged at 6.0211 because the allocation still closes.

    INTERCEPTIONS ARE RESERVED OUT OF THE POOL rather than re-drawn. QB V1
    draws them as `Binomial(att - cmp, p_int)` (qb2_lib.py:322): an
    interception IS an incompletion, so an intercepted attempt is an attempt
    that cannot also be a completion. Holding those attempts back is the
    causally correct order -- the passer's own layer fixes them, and the
    receiving event then allocates completions among what is left. Re-drawing
    interceptions against the new completion count would be a change to a
    metric C3 does not own and would need its own pre-registration.

    The touchdowns are then the subset of the CREDITED completions that reached
    the end zone, dealt the same way from `cmp_q`. And the yards ride on the
    COMPLETION share, not the attempt share, because passing yards accrue on
    completions -- which makes "no completion, no yards" hold by construction
    rather than by assertion.

    WHAT IT REFUSES, AND WHY IT DOES NOT CLIP INSTEAD
    -------------------------------------------------
    The construction needs `team_cmp <= sum(att_q - int_q)`. That is an
    ordinary condition -- it holds in 93,992 of 94,000 sealed team-draws -- but
    it is not guaranteed, because C3's targeted-throw budget
    (`shared_pass.targeted_throws`) does not reserve intercepted throws out of
    the pool that RC1 then converts to catches. In the 8 team-draws where it
    fails, the receiving chain has caught more balls than the quarterbacks had
    non-intercepted attempts to throw. No per-passer allocation can resolve
    that: it is an upstream coupling gap between two layers, of exactly the
    kind SC1 was pre-registered to fix for carries and scrambles. It is
    REFUSED BY NAME here rather than clipped, and the analogous coupling is
    named as owed work rather than improvised.

    QY1 -- THE YARDS, WHEN THE ATOMS ARE SUPPLIED
    ---------------------------------------------
    `atoms` is optional and OFF by default, so every frozen arm is bit-for-bit
    unmoved. Supplied, it is the per-draw multiset of the team's completion
    yardages -- the vector RC1 already drew and used to sum
    `receiving_yards` -- and the yardage is then dealt as what it is:

        partition the K completion-yardages into blocks of sizes
        cmp_1 ... cmp_n, and give quarterback i the sum of his block.

    That replaces `cmp_q / K * Y`, a CONTINUOUS SHARE of a team total, which
    is why `qb/pyds` is non-integer in 17.48% of sealed cells. Every property
    the share version had to assert now holds by construction: the blocks
    partition the multiset so the totals close exactly; a block of integers
    sums to an integer; an EMPTY block sums to 0, so "no completion, no
    yards" needs no `np.where`; and nothing anywhere is compared against zero,
    so a NEGATIVE team total -- 2,261 lawful negative cells in this repository
    -- is dealt like any other.

    A MULTIVARIATE HYPERGEOMETRIC WOULD BE THE WRONG FAMILY and is not used.
    It distributes NON-NEGATIVE integer counts from an urn; there is no urn
    with -7 balls in it, and the clip that would "fix" that breaks the HARD
    `qb_cross_layer_reconciliation`, which asserts team passing yards EQUALS
    player receiving yards over values that are lawfully negative.

    THE PERMUTATION DRAWS FROM `atom_rng`, A SEPARATE STREAM, on purpose. The
    completion and touchdown allocations must be identical to the incumbent's
    for the same `rng`, so that an arm comparison isolates the yardage change
    instead of measuring a shifted random stream.

    The atoms are VALIDATED, NOT TRUSTED: a count that disagrees with the
    completions, a non-integer atom, or a multiset that does not sum to the
    declared team total is refused by its own name. Each of those would be a
    silent mis-attribution otherwise, which is the failure mode this whole
    function exists to have stopped doing.
    """
    A = np.asarray(att_by_qb, float)
    I = np.asarray(int_by_qb, float)
    if A.shape != I.shape or A.ndim != 2 or not A.size:
        return Outcome.fail(
            'PASSER_CREDIT_SHAPE',
            f'attempts {A.shape} and interceptions {I.shape} must be the same '
            f'2-D (quarterback x draw) matrix')
    nq, m = A.shape
    K = np.asarray(team_cmp, float).reshape(-1)
    P = np.asarray(team_ptd, float).reshape(-1)
    Y = np.asarray(team_pyds, float).reshape(-1)
    if not (K.size == P.size == Y.size == m):
        return Outcome.fail(
            'PASSER_CREDIT_SHAPE',
            f'team totals have {K.size}/{P.size}/{Y.size} draws against '
            f'{m} in the attempt matrix; the draw index is not shared')
    # INTEGRALITY IS CHECKED, NEVER ROUNDED INTO. The incumbent applied
    # `int(round(...))` to the team total, which silently absorbs a
    # non-integer wherever one appears. A count that is not a count is a
    # defect upstream, and rounding it here would hide it.
    for name, v in (('attempts', A), ('interceptions', I),
                    ('team_completions', K), ('team_passing_td', P)):
        if np.any(np.abs(v - np.rint(v)) > 1e-9):
            return Outcome.fail(
                'PASSER_CREDIT_NON_INTEGER_COUNT',
                f'{name} carries a non-integer value; a count that is not a '
                f'count cannot be dealt and is refused rather than rounded.',
                metric=name)
        if np.any(v < -1e-9):
            return Outcome.fail(
                'PASSER_CREDIT_NEGATIVE_COUNT',
                f'{name} carries a negative value. A negative count of events '
                f'is not a small count.', metric=name)
    Ai = np.rint(A).astype(np.int64)
    Ii = np.rint(I).astype(np.int64)
    Ki = np.rint(K).astype(np.int64)
    Pi = np.rint(P).astype(np.int64)
    completable = Ai - Ii
    if (completable < 0).any():
        return Outcome.fail(
            'PASSER_CREDIT_INPUT_INCOHERENT',
            f'{int((completable < 0).sum())} cell(s) where a quarterback has '
            f'more interceptions than attempts. The QB layer handed this '
            f'function an impossible state; repairing it here would hide it.',
            n_bad=int((completable < 0).sum()))
    short = completable.sum(0) - Ki
    if (short < 0).any():
        j = int(np.argmin(short))
        return Outcome.fail(
            'PASSER_CREDIT_EXCEEDS_COMPLETABLE_ATTEMPTS',
            f'{int((short < 0).sum())} draw(s) in which the receiving event '
            f'produced more completions than the quarterbacks had '
            f'non-intercepted attempts to throw -- worst draw {j}: '
            f'{int(Ki[j])} completions against {int(completable[:, j].sum())} '
            f'completable attempts ({int(Ai[:, j].sum())} attempts less '
            f'{int(Ii[:, j].sum())} interceptions). This is a coupling gap '
            f'between the targeted-throw budget and the interception draw, '
            f'not a per-passer allocation question, and it is refused rather '
            f'than clipped. The fix is an SC1-style coupling that reserves '
            f'intercepted throws out of the targeted budget, which is a '
            f'pre-registered mechanism change and not a patch.',
            n_bad=int((short < 0).sum()), worst_draw=j,
            worst_shortfall=int(-short[j]))
    bad_td = int((Pi > Ki).sum())
    if bad_td:
        return Outcome.fail(
            'PASSER_CREDIT_TD_EXCEEDS_COMPLETIONS',
            f'{bad_td} draw(s) where the team receiving touchdowns exceed its '
            f'receptions. A touchdown catch is a catch; refused rather than '
            f'clipped.', n_bad=bad_td)
    bad_y = int(((Ki == 0) & (np.abs(Y) > 1e-9)).sum())
    if bad_y:
        return Outcome.fail(
            'PASSER_CREDIT_YARDS_WITHOUT_COMPLETION',
            f'{bad_y} draw(s) carry team passing yards with zero team '
            f'completions. Yards accrue on catches; there is nothing to '
            f'attribute them to and none is invented.', n_bad=bad_y)

    cmp_q = np.zeros((nq, m), np.int64)
    ptd_q = np.zeros((nq, m), np.int64)
    for j in range(m):
        cmp_q[:, j] = rng.multivariate_hypergeometric(
            completable[:, j], int(Ki[j]))
        ptd_q[:, j] = rng.multivariate_hypergeometric(
            cmp_q[:, j], int(Pi[j]))
    if atoms is None:
        # THE INCUMBENT PATH, UNTOUCHED. A continuous share of the team total,
        # and the reason `qb/pyds` has a continuous support it should not.
        denom = np.where(Ki > 0, Ki, 1)
        pyds_q = np.where(Ki[None, :] > 0,
                          cmp_q / denom[None, :] * Y[None, :], 0.0)
        yard_scheme = 'yards on the completion share of the team total'
    else:
        seg = list(atoms)
        if len(seg) != m:
            return Outcome.fail(
                'PASSER_CREDIT_ATOM_SHAPE',
                f'{len(seg)} atom vector(s) against {m} draw(s); the atoms '
                f'do not share the draw index they are supposed to be '
                f'indexed by.', n_atoms=len(seg), m=m)
        seg = [np.asarray(v, float).reshape(-1) for v in seg]
        n_bad = [j for j in range(m) if seg[j].size != int(Ki[j])]
        if n_bad:
            j = n_bad[0]
            return Outcome.fail(
                'PASSER_CREDIT_ATOM_COUNT_MISMATCH',
                f'{len(n_bad)} draw(s) supply a number of completion '
                f'yardages that is not the number of completions -- worst '
                f'draw {j}: {seg[j].size} atom(s) against {int(Ki[j])} team '
                f'completion(s). A partition needs the multiset it is '
                f'partitioning; this is refused rather than padded or '
                f'truncated.', n_bad=len(n_bad), worst_draw=j)
        frac = [j for j in range(m)
                if seg[j].size and np.any(np.abs(seg[j] - np.rint(seg[j]))
                                          > 1e-9)]
        if frac:
            return Outcome.fail(
                'PASSER_CREDIT_ATOM_NON_INTEGER',
                f'{len(frac)} draw(s) carry a non-integer per-completion '
                f'yardage -- first draw {frac[0]}. A yard is an integer; a '
                f'fractional atom means the quantity has already been '
                f'divided somewhere upstream, and rounding it here would '
                f'hide exactly the defect this deal exists to remove.',
                n_bad=len(frac), worst_draw=frac[0])
        tot = np.array([seg[j].sum() for j in range(m)], float)
        off = np.abs(tot - Y) > 1e-9
        if off.any():
            j = int(np.argmax(np.abs(tot - Y)))
            return Outcome.fail(
                'PASSER_CREDIT_ATOM_TOTAL_MISMATCH',
                f'{int(off.sum())} draw(s) where the completion yardages do '
                f'not sum to the declared team passing total -- worst draw '
                f'{j}: atoms sum to {float(tot[j])} against {float(Y[j])}. '
                f'One of the two is wrong and this function cannot tell '
                f'which, so it refuses instead of preferring one.',
                n_bad=int(off.sum()), worst_draw=j,
                atom_total=float(tot[j]), declared_total=float(Y[j]))
        arng = atom_rng if atom_rng is not None else rng
        pyds_q = np.zeros((nq, m), float)
        for j in range(m):
            k = seg[j].size
            if k == 0:
                continue
            shuffled = seg[j][arng.permutation(k)]
            # The same cumulative-sum idiom RC1 uses, and for the same reason:
            # `np.add.reduceat` cannot express the zero-length block a
            # quarterback with no completions must receive, and that block's
            # sum -- exactly 0 -- is the whole point of the construction.
            cs = np.concatenate([[0.0], np.cumsum(shuffled)])
            e = np.cumsum(cmp_q[:, j])
            pyds_q[:, j] = cs[e] - cs[e - cmp_q[:, j]]
        frac_out = int((np.abs(pyds_q - np.rint(pyds_q)) > 1e-9).sum())
        if frac_out:
            return Outcome.fail(
                'PASSER_CREDIT_INCOHERENT',
                f'{frac_out} credited cell(s) are non-integer after a '
                f'partition of integers, which is arithmetically impossible. '
                f'This is a defect in this function, not in its inputs.',
                check='integer_yards_from_integer_atoms', n_bad=frac_out)
        yard_scheme = ('yards by random PARTITION of the team\'s completion '
                       'yardages into blocks of the credited completion '
                       'counts; signed, integer, and closing by construction')

    # THE CLOSURE THE INCUMBENT CHECKED, KEPT VERBATIM. The new scheme closes
    # by construction; the check stays because a construction that is believed
    # to close and is never checked is how the last one survived.
    for name, got, want in (('completions', cmp_q.sum(0), Ki),
                            ('passing_td', ptd_q.sum(0), Pi),
                            ('passing_yards', pyds_q.sum(0), Y)):
        n_bad = int((np.abs(got - np.asarray(want, float)) > 1e-6).sum())
        if n_bad:
            return Outcome.fail(
                'PASSER_CREDIT_DOES_NOT_CLOSE',
                f'{name}: {n_bad} draw(s) where the per-quarterback split does '
                f'not sum to the team total. Refused rather than adjusted.',
                metric=name, n_bad=n_bad)
    # AND THE PER-PASSER COHERENCE, ON THE VALUES ABOUT TO BE WRITTEN. These
    # hold by construction; asserting them is what makes "by construction" a
    # claim anyone can check rather than a claim in a comment.
    for name, viol in (
            ('completions_within_attempts', int((cmp_q > Ai).sum())),
            ('completions_within_completable',
             int((cmp_q > completable).sum())),
            ('passing_td_within_completions', int((ptd_q > cmp_q).sum())),
            ('interceptions_within_incompletions',
             int((Ii > Ai - cmp_q).sum())),
            ('zero_completions_zero_yards',
             int(((cmp_q == 0) & (np.abs(pyds_q) > 1e-9)).sum()))):
        if viol:
            return Outcome.fail(
                'PASSER_CREDIT_INCOHERENT',
                f'{viol} cell(s) violate {name} after a construction that '
                f'cannot produce it. This is a defect in this function, not '
                f'in its inputs.', check=name, n_bad=viol)
    return Outcome.ok(
        'PASSER_CREDIT', value={'cmp': cmp_q.astype(float),
                                'pyds': pyds_q,
                                'ptd': ptd_q.astype(float)},
        detail=f'{nq} quarterback row(s) credited from the team totals by '
               f'hypergeometric allocation over their own attempts',
        attribution=PASSER_CREDIT_ATTRIBUTION,
        scheme='multivariate hypergeometric over (attempts - interceptions), '
               'then over credited completions; ' + yard_scheme,
        yard_allocation=('QY1_ATOM_PARTITION' if atoms is not None
                         else 'CONTINUOUS_COMPLETION_SHARE'),
        replaces='nfl.production.nonqb.shared_pass.credit_to_passers, whose '
                 'attempt-share multinomial sampled a finite pool WITH '
                 'replacement',
        closes_exactly_on_team_totals=True,
        coherent_by_construction=['cmp <= att', 'cmp <= att - int',
                                  'ptd <= cmp', 'cmp == 0 -> pyds == 0'],
        n_draws=int(m))


def slate_fits(season, week, players, role_priors=None, tiers=None) -> Outcome:
    """Everything that depends only on history, computed once per slate.

    `role_priors` is R6's tier-conditional prior, keyed by class. Absent -- the
    V1 and R5 path -- the class point forecast is exactly what it was.
    """
    rp = role_priors or {}
    fits, states = {}, {}
    for name, o in (
            ('p4c_params_targets', P4.params('targets', season)),
            ('p4c_params_carries', P4.params('carries', season)),
            ('C_targets', P4.class_point_forecast(
                'targets', season, week, players,
                role_prior=rp.get('targets'), tiers=tiers)),
            ('C_carries', P4.class_point_forecast(
                'carries', season, week, players,
                role_prior=rp.get('carries'), tiers=tiers)),
            ('participation_prior', PP.share_prior(season, week, players)),
            ('receiving_priors', FP.receiving_priors(season)),
            ('td_priors_rec', FP.td_priors(season, 'rec')),
            ('td_priors_rush', FP.td_priors(season, 'rush'))):
        states[name] = f'{o.state.value}[{o.code}]'
        if o.state is not State.PASS:
            # A CAUSE READ BACK OUT OF EVIDENCE IS A STRING, NOT THE ENUM.
            #
            # `Outcome` stores cause as its `.value`, so this handed the
            # literal 'DATA' to a constructor that requires `Cause.DATA` and
            # got OutcomeError: BLOCKED_CAUSE_UNDECLARED ... (got 'DATA') --
            # an error message naming DATA as invalid while listing DATA among
            # the valid choices, which is how long it took to read.
            #
            # The consequence was worse than the crash. This refusal exists to
            # say WHICH prior was unavailable and why; raising here destroyed
            # that and the caller reported the generic SLATE_FITS_RAISED
            # instead, so five stages went NOT_APPLICABLE for a reason nobody
            # could see. The upstream refusal is preserved now.
            _c = o.evidence.get('cause')
            if isinstance(_c, str):
                _c = next((c for c in Cause if c.value == _c or c.name == _c),
                          None)
            elif not isinstance(_c, Cause):
                _c = None
            return Outcome.blocked(
                'SLATE_FITS_UNAVAILABLE',
                f'{name} returned {o.state.value}[{o.code}]: {o.detail[:160]}',
                cause=_c or Cause.DEPENDENCY,
                failing_fit=name, upstream_code=o.code,
                upstream_cause=o.evidence.get('cause'), states=states)
        fits[name] = o
    return Outcome.ok('SLATE_FITS_OK', value=fits, states=states,
                      evidence_by_fit={
                          k: {kk: vv for kk, vv in v.evidence.items()
                              if kk != 'value'} for k, v in fits.items()})


def qb_slate(season, week, qb_players, m=200, seed=20260908,
             include_cold_start=False) -> Outcome:
    """The QB layer for the whole slate, computed once.

    QB rushing yards ARE supported and RB rushing yards are not, which looks
    inconsistent until you read both mechanisms. QB V1 draws a per-game
    yards-per-rush from the quarterback's own history mixed with the positional
    pool and multiplies by his drawn rush opportunity -- a distribution, and
    the owner-accepted production baseline. P5A's rushing control is a
    per-CARRY compound and is unadjudicated. Whatever P5A eventually defines
    should be checked against the QB mechanism, because the same football
    quantity is currently produced two different ways.
    """
    # The QB layer reads the derived panel too, through p4c_build. Ensuring
    # the cache here is what stops it depending on a copy someone else
    # happened to leave in the research tree.
    from nfl.production import derived as _D
    a = _D.artifacts()
    if a.state is not State.PASS:
        return a
    fh = QBV1.artifact_hash()
    if fh.state is not State.PASS:
        return fh
    sl = QBV1.slate_prospective(season, week, qb_players,
                                include_cold_start=include_cold_start)
    if sl.state is not State.PASS:
        return sl
    rows, allrows = sl.value
    o = QBV1.forecast(rows, season, allrows, seed=seed, m=m)
    if o.state is not State.PASS:
        return o
    by_team = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by_team[r.get('team')].append(i)
    return Outcome.ok('QB_SLATE_OK', value={'rows': rows, 'draws': o.value,
                                            'index_by_team': dict(by_team),
                                            # kept so R2 can re-run the layer
                                            # at the allocated level without
                                            # reloading the frame
                                            'allrows': allrows,
                                            'season': season, 'm': m,
                                            'seed': seed},
                      spec_version=QBV1.SPEC_VERSION, n_qb=len(rows),
                      cold_start_included=bool(include_cold_start),
                      n_cold_start_rows=sl.evidence.get('n_cold_start_rows', 0),
                      qb_frame_sha256=fh.value,
                      warnings=[f'known limitation: {k}'
                                for k in QBV1.KNOWN_LIMITATIONS])



def apply_r2_level(qb, alloc, tv, teams) -> Outcome:
    """R2: re-run QB V1 at the level D1 x QB3 already own.

    Pre-registered in nfl/research/r2/predeclaration_qb_level_ownership_r2.md,
    sha256 3d7beeb39f32da11623ac2be178ca4b764ecf314a5a55515b0d45c0e3d4f323c.

    THE DEFECT R2 REMOVES. QB V1 drew its own level, `DB = rint(V x S)`, from
    the same two pools D1 and QB3 own. `run_game` reconciled the duplicate by
    dividing one level by the other, and dividing by a small draw is what
    produced composition factors to 59.85 and a 49.14 passing-touchdown tail
    off a one-dropback donor. R2 deletes the duplicate instead of bounding the
    ratio: the level is apportioned from the team budget by largest remainder,
    and QB V1 supplies conditional rates at that level.

    After this, team dropback closure is INTEGER-exact by construction rather
    than float-exact through a division, which the pre-registration declares in
    advance as the invariant R2 replaces rather than preserves. There is no
    denominator, so the OWN-4 donor mechanism has nothing to repair.
    """
    if not qb or 'rows' not in qb:
        return Outcome.fail('R2_NO_QB_SLATE',
                            'R2 needs the QB slate it is re-levelling')
    rows = qb['rows']
    idx_by_team = qb['index_by_team']
    ext = np.zeros((len(rows), int(qb['m'])), np.int64)
    named = set()
    ev = {}
    for t in teams:
        a = alloc.get(t)
        if a is None:
            continue
        tdb = np.asarray(tv.value[('team_dropbacks_part', t)], float)
        pids = list(a['pids'])
        rows_for = {rows[i]['gsis_id']: i for i in idx_by_team.get(t, [])}
        keep = [(j, p) for j, p in enumerate(pids) if p in rows_for]
        if not keep:
            # Allocated mass with no modelled quarterback to receive it. This
            # is OWN-1's leak, and it is refused by name rather than shared out
            # among the survivors.
            return Outcome.fail(
                'R2_ALLOCATED_MASS_HAS_NO_MODELLED_QB',
                f'{t}: the allocation names {len(pids)} quarterback(s), none '
                f'of whom QB V1 forecast. No survivor renormalisation.',
                team=t, pids=pids)
        sub = np.stack([np.asarray(a['shares'][j], float) for j, _ in keep])
        ap = QBACC.apportion_dropbacks(tdb, sub, [p for _, p in keep])
        if ap.state is not State.PASS:
            return ap
        for k, (_, p) in enumerate(keep):
            ext[rows_for[p]] = ap.value[k]
            named.add(p)
        ev[t] = {'n_qb_levelled': len(keep),
                 'team_budget_mean': ap.evidence['team_budget_mean'],
                 'closes_exactly': True}
    o = QBV1.forecast(rows, qb['season'], qb['allrows'],
                      seed=qb['seed'], m=qb['m'], db_external=ext)
    if o.state is not State.PASS:
        return o
    out = dict(qb)
    out['draws'] = o.value
    out['r2'] = {'applied': True, 'per_team': ev,
                 'level_owner': 'D1 x QB3, apportioned by largest remainder',
                 'qb_v1_draws_no_level': True,
                 'donor_mechanism_reachable': False,
                 'closure': 'integer-exact by construction'}
    return Outcome.ok('QB_LEVEL_R2_APPLIED', value=out,
                      n_qb_levelled=len(named), **{'teams': list(ev)})

def run_game(season, week, game_id, players, fits, m=200, seed=20260908,
             injuries_rows=None, test_only=False, kickoff_utc=None,
             run_id='rehearsal', qb=None, shared_pass='off',
             game_coupling='none', rushing_budget=None,
             team_carries_override=None, tv=None, rush_categories=None,
             appearance_spec='frozen', observed_before=None,
             inactive_ids=None, reserve_interceptions=False,
             qb_yard_atoms=False):
    """One game, every implemented layer, one draw index.

    `rushing_budget` is A1's `rb` category carries, {team: (m,) counts}.

    `rush_categories` is A1's WHOLE partition, {(team, category): (m,) counts}
    for every one of kneel / designed_qb / rb / wr / te / fringe -- i.e.
    `rushing_a1.allocate(...).value['carries']` handed over entire rather than
    filtered down to `rb`. Supplying it is what turns the rush residual from
    MEASURED into ATTRIBUTED: D6 found a frame mean of 24.1% of every team's
    carries (range 0.6%-45.3%, 5-10 carries per team-draw) with no modelled
    owner, and the owner was never missing -- `rushing_a1` computes all six
    categories with one multinomial and five of them were discarded at the
    call site. With it supplied, every carry in every draw has a named owner
    in the artifact and the unowned mass is identically zero by construction.
    Without it the ledger is emitted as NOT_APPLICABLE with the reason, and
    the residual is reported as the unattributed quantity it still is.

    A1 IS THE SOLE OWNER OF THE RUSHING-OPPORTUNITY PARTITION, and supplying
    it here is what makes that true rather than merely stated. Without it the
    running-back pool is `share x D1.team_carries` -- the whole team carry
    count, kneels and quarterback runs and receiver runs included -- so the
    backs compete for carries that were never theirs and A1's partition is
    computed beside a second, different answer to the same question. Passing
    the budget in replaces the denominator with the one A1 owns; nothing else
    about the allocation changes, and with `rushing_budget=None` this function
    is bit-for-bit what it was.

    `team_carries_override` is {team: (m,)} replacing D1's team-carry draw.

    SC1 PERMUTES THE CARRY DRAW INDEX, so after it runs the carry level on
    draw j is no longer `tv[('team_carries', t)][j]`. A1 partitions the
    PERMUTED vector; anything downstream that reaches for the original is
    reading a second, differently-indexed answer to the same question. That
    is not hypothetical -- it fired on the first real run, as 9 cells where
    A1's running-back budget sat above a team-carry level A1 had never seen.
    Supplying the coupled level here keeps one carry number in the game.

    `g['layer_outcomes']` carries each layer's real Outcome alongside the
    display string in `g['layers']`. A caller that has to report a per-stage
    state cannot get one by parsing `'PASS[CODE]'` back apart, and inventing a
    state where the string is unparseable is how a refusal becomes a pass.
    """
    away, home = game_id.split('_')[2:4]
    teams = (away, home)
    g = {'game_id': game_id, 'teams': list(teams), 'layers': {},
         'layer_outcomes': {}, 'accounting': {},
         'engine_version': ENGINE_VERSION}

    def _lay(name, outcome):
        """Record a layer's state ONCE, in both forms, from one source."""
        g['layers'][name] = f'{outcome.state.value}[{outcome.code}]'
        g['layer_outcomes'][name] = outcome
        return outcome

    def _team_carries(t):
        """THE team-carry draw for `t` -- one accessor, so the coupled level
        and the raw D1 level can never both be live in the same game."""
        if team_carries_override is not None and t in team_carries_override:
            return np.asarray(team_carries_override[t], float).reshape(-1)
        return np.asarray(tv.value[('team_carries', t)], float).reshape(-1)

    recv = [q for q in players if q.get('position') in RECEIVING_POS]

    # ---- AN EVIDENCE GAP ABOUT ONE TEAM IS SCOPED TO THAT TEAM ----------
    #
    # `layers.appearance` resolves readiness PER TEAM and then defers the
    # WHOLE GAME on the worst of them (layers.py:110-127). Its own `owed`
    # block already carries both per-team states, so the information needed
    # to scope the refusal correctly is present at the moment it is dropped.
    #
    # Measured on 2026_01_DEN_KC: Denver carries exactly ONE injury row and
    # its `report_status` is blank, so the contract reads
    # INJURY_REPORT_INCOMPLETE. Kansas City carries eleven rows, two of them
    # designated, and reads READY. Under the game-scoped refusal Denver's
    # single unfiled designation removed Kansas City's thirteen eligible
    # non-quarterbacks along with Denver's own fourteen, and the board
    # reached quarterbacks only, with no skill player of either club on it.
    # Measured before and after on the sealed board for that game: 6 rows,
    # all QB -> 19 rows, the same 6 quarterbacks plus 13 Kansas City skill
    # players (6 WR, 4 TE, 3 RB) and still no Denver skill player.
    #
    # WHICH REFUSALS MAY BE NARROWED AND WHICH MAY NOT. This is an
    # EVIDENCE-GAP refusal -- "I do not know whether Denver's players are
    # available" -- and an evidence gap about unit U is a statement about U.
    # A CONSTRUCTION-INVARIANT refusal (a partition exceeding the thing it
    # partitions, a count identity that does not close, a player allocated
    # opportunity with no appearance vector) is a statement about the whole
    # construction and is NEVER narrowed. Nothing here touches one of those:
    # every accounting and closure check below still runs, and the QB-side
    # guards -- `reconcile_allocation_share`, `reconcile_team_volume`,
    # `reconcile_cross_layer` -- are still evaluated over BOTH teams.
    #
    # THE GUARD IS NOT WEAKENED AND MUST NOT BE. `layers.appearance` is
    # called with the readiness contract exactly as it stands; it is called
    # with the teams whose evidence exists. A deferred team is not treated as
    # a team with nobody injured (readiness.py:650-657 says why that reading
    # is wrong): it is recorded under its own state and its own reason, and
    # not one of its players reaches a modelled quantity.
    #
    # layers.py is hashed by Q9's frozen candidate identity 481f005f682cd721
    # and may not be edited, so the scoping happens at the CALL SITE -- the
    # same placement the C1 denominator selection uses, for the same reason.
    #
    # THE RNG STATEMENT, IN FULL, BECAUSE IT IS NOT A DRAW-PRESERVING CHANGE.
    # Appearance consumes ONE shared stream sequentially across the player
    # dict, so running it over the READY teams' players produces different
    # draws than running it over both teams' players would have. That is
    # unavoidable and it is not hidden: when every team is READY this block
    # changes nothing at all and the draws are bit-identical to before, and
    # when a team is deferred there is no both-teams run to perturb because
    # the incumbent code produces nothing whatsoever for that game.
    ateams = tuple(teams)
    team_scope = None
    if injuries_rows is None:
        # The gate-cut handoff is a CONTEXT VAR that `team_readiness` appends
        # to and `readiness.latest_injuries_rows` may later consume. Probing
        # readiness here would append a second, identical entry per team and
        # move `n_gate_evaluations` in the feed's own evidence on a run that
        # is otherwise unchanged. The cuts are identical -- same kickoff,
        # same written_at, same teams -- so the probe restores the handoff
        # and the call below sees exactly the state it saw before.
        _gate_before = RD._GATE_CUTS.get()
        try:
            _tr = [RD.team_readiness(season, week, t, kickoff_utc=kickoff_utc)
                   for t in teams]
        finally:
            RD._GATE_CUTS.set(_gate_before)
        _ready = [r for r in _tr if str(r['state']).startswith('READY')]
        _notready = [r for r in _tr
                     if not str(r['state']).startswith('READY')]
        # EVERY TEAM READY -> there is nothing to scope, and the call below is
        # the call that was always made, on the frame that was always built.
        # NO TEAM READY -> there is no game left to scope to, so the
        # whole-game deferral is the correct answer and `layers.appearance`
        # is left to produce it in its own words with its own code.
        if _ready and _notready:
            ateams = tuple(r['team'] for r in _tr
                           if str(r['state']).startswith('READY'))
            _excluded = [q for q in recv if q['team'] not in ateams]
            team_scope = {
                'scoped': True,
                'code': 'APPEARANCE_TEAM_DEFERRED',
                'ready_teams': list(ateams),
                'deferred_teams': [
                    {'team': r['team'], 'state': r['state'],
                     'reason': r['reason'],
                     'n_injury_rows': r.get('n_rows'),
                     'n_players_excluded': sum(
                         1 for q in _excluded if q['team'] == r['team']),
                     'gsis_ids': sorted(q['gsis_id'] for q in _excluded
                                        if q['team'] == r['team'])}
                    for r in _notready],
                'teams': [{'team': r['team'], 'state': r['state']}
                          for r in _tr],
                'n_players_excluded': len(_excluded),
                'note': 'a team with no filed report is NOT a team with no '
                        'injuries. No appearance probability, no allocation '
                        'and no projection is emitted for any player of a '
                        'deferred team.',
                'rng_note': 'the appearance stream is consumed over the READY '
                            'teams\' players only, so these are not the draws '
                            'a both-teams-READY run would have produced. '
                            'There is no such run here: the unscoped code '
                            'produces nothing for this game.'}
            g['appearance_team_scope'] = team_scope
            g['deferred_teams'] = team_scope['deferred_teams']
    ids = [q['gsis_id'] for q in recv]
    pos = [q['position'] for q in recv]
    starts, counts, i = [], [], 0
    by_team = collections.defaultdict(list)
    for q in recv:
        by_team[q['team']].append(q)
    order = []
    for t in ateams:
        order.extend(by_team.get(t, []))
        starts.append(i)
        counts.append(len(by_team.get(t, [])))
        i += len(by_team.get(t, []))
    recv, ids, pos = order, [q['gsis_id'] for q in order], \
        [q['position'] for q in order]
    g['n_players'] = len(recv)

    # A3G in the V1 candidate mode: the two teams in a game share one coupled
    # draw index, so the game total stops being the sum of two independent
    # marginals. Measured: SD(total plays) 12.271 -> 9.269 against a historical
    # 9.265, and the fraction of drawn games outside the entire 2020-2025
    # observed range 1.520% -> 0.188%. The rank copula moves no marginal by
    # construction -- it changes WHICH residual each side receives, not the
    # pool it is drawn from. Opt-in; no production default is changed here.
    # A CALLER THAT ALREADY HOLDS THIS DRAW MUST BE ABLE TO HAND IT OVER.
    # Redrawing it here gave the same quantity two owners: the entrypoint's
    # `team_environment` stage stored one vector and the game ran on another,
    # and under A3G they are genuinely different because that stage drew
    # uncoupled. Same call, same defaults, when nothing is supplied.
    if tv is None:
        tv = (TV.forecast(season, week, list(teams), m=m, seed=seed,
                          joint_residuals=True,
                          game_pairs=[(teams[0], teams[1])],
                          game_coupling=game_coupling)
              if game_coupling and game_coupling != 'none'
              else TV.forecast(season, week, list(teams), m=m, seed=seed))
    g['layers']['game_coupling'] = (f'PASS[A3G_{game_coupling.upper()}]'
                                    if game_coupling
                                    and game_coupling != 'none'
                                    else 'NOT_APPLICABLE[GAME_COUPLING_NONE]')
    _lay('team_environment', tv)
    if tv.state is not State.PASS:
        g['halted_at'] = 'team_environment'
        return g, None

    fixture = None
    if injuries_rows is not None:
        fixture = {'_test_only': True, 'practice_progression': {},
                   'teammate_availability': {},
                   'injuries_rows': injuries_rows}
    # game_id separates this game's streams from every other game on the
    # slate. Without it a sixteen-game slate is not sixteen games.
    ap = LY.appearance(season, week, recv, fixture=fixture, m=m, seed=seed,
                       teams=ateams, kickoff_utc=kickoff_utc,
                       game_id=game_id, appearance_spec=appearance_spec,
                       observed_before=observed_before,
                       inactive_ids=inactive_ids)
    # THE DEFERRAL TRAVELS WITH THE LAYER THAT WOULD HAVE CARRIED IT.
    # `run_forecast._governance_facts` passes a layer's `warnings` through to
    # the sealed stage verbatim, so the team-scoped refusal reaches the
    # artifact by the channel the layers already use rather than by a new one
    # nobody reads. A NEW `g['layers']` KEY WOULD RAISE
    # ENGINE_LAYER_NOT_REPORTED in `run_forecast._assert_every_layer_is_
    # reported`, which is that guard working; the structured record is put on
    # `g` and on this outcome's evidence instead.
    if team_scope is not None and ap.state is State.PASS:
        _w = list(ap.evidence.get('warnings') or [])
        _w.append(
            'APPEARANCE_TEAM_DEFERRED: '
            + '; '.join(f"{d['team']} is {d['state']} and is deferred -- "
                        f"{d['n_players_excluded']} player(s) carry no "
                        f"appearance estimate and no projection"
                        for d in team_scope['deferred_teams'])
            + f". The appearance layer ran on {', '.join(ateams)} only. "
            + team_scope['note'])
        ap = dataclasses.replace(
            ap, evidence={**ap.evidence, 'warnings': _w,
                          'team_scope': team_scope})
    _lay('appearance', ap)
    if ap.state is not State.PASS:
        g['halted_at'] = 'appearance'
        g['halt_reason'] = ap.detail[:200]
        for k in ('participation', 'targets_carries', 'carries',
                  'receiving_conversion', 'receiving_td', 'rushing_td',
                  'rushing_conversion'):
            g['layers'][k] = 'NOT_APPLICABLE[UPSTREAM_NOT_EXECUTED]'
        return g, None

    pa = _lay('participation',
                  LY.participation(ap, fits['participation_prior'].value, m=m))

    # A PLAYER WITH NO APPEARANCE DRAW IS EXCLUDED, NOT A REASON TO REFUSE THE
    # WHOLE GAME.
    #
    # `targets_carries` refuses with ALLOCATION_PLAYER_WITHOUT_APPEARANCE when
    # any player it is handed has no appearance vector, and it is right to:
    # allocating to a player whose availability is unknown invents it. But the
    # refusal was game-scoped where the missing evidence is player-scoped. On
    # 2026-09-13 ONE such player cost CHI@CAR and CLE@JAX every running back
    # and every receiver projection for both clubs.
    #
    # So the frame is narrowed to the players who HAVE the evidence, each
    # exclusion is named, and the refusal is kept for the case where it is
    # genuinely a game-level fact: a team with nobody left has no partition to
    # make. `rb` below is derived from `recv`, so filtering here covers the
    # carry layout too.
    if pa.state is State.PASS:
        _placeable = [q for q in recv if q['gsis_id'] in pa.value]
        _dropped = [q for q in recv if q['gsis_id'] not in pa.value]
        if _dropped:
            _left = {q['team'] for q in _placeable}
            _empty = [t for t in ateams if t not in _left]
            if _empty:
                o = Outcome.fail(
                    'NONQB_TEAM_HAS_NO_APPEARING_PLAYER',
                    f'excluding {len(_dropped)} player(s) with no appearance '
                    f'draw would leave {_empty} with nobody to allocate '
                    f'opportunity among. Refused rather than allocating '
                    f'within an empty team.',
                    teams_emptied=_empty, n_excluded=len(_dropped))
                _lay('participation_frame', o)
                g['halted_at'] = 'participation_frame'
                g['halt_reason'] = o.detail[:200]
                return g, None
            _by = collections.defaultdict(list)
            for q in _placeable:
                _by[q['team']].append(q)
            _order, starts, counts, _i = [], [], [], 0
            for t in ateams:
                _order.extend(_by.get(t, []))
                starts.append(_i)
                counts.append(len(_by.get(t, [])))
                _i += len(_by.get(t, []))
            recv = _order
            ids = [q['gsis_id'] for q in recv]
            pos = [q['position'] for q in recv]
            g['n_players'] = len(recv)
            g['excluded_no_appearance'] = [
                {'gsis_id': q['gsis_id'], 'team': q.get('team'),
                 'position': q.get('position'),
                 'reason': 'NO_APPEARANCE_DRAW'} for q in _dropped]
            _lay('participation_frame', Outcome.ok(
                'PARTICIPATION_FRAME_NARROWED', value=len(recv),
                detail=f'{len(_dropped)} player(s) carry no appearance draw '
                       f'and are excluded by name; {len(recv)} remain and '
                       f'every team still has players to allocate among.',
                n_excluded=len(_dropped), n_remaining=len(recv),
                excluded=g['excluded_no_appearance'][:10]))
        else:
            _lay('participation_frame', Outcome.ok(
                'PARTICIPATION_FRAME_COMPLETE', value=len(recv),
                detail='every modelled player carries an appearance draw'))

    # ---- targets (WR/TE/RB, simplex) ------------------------------------
    Ct = [fits['C_targets'].value.get(p, 0.0) for p in ids]
    tc = LY.targets_carries(pa, 'targets', Ct, pos, (starts, counts), ids,
                            fits['p4c_params_targets'].value, m=m, seed=seed,
                            game_id=game_id, ordinal=season * 100 + week)
    _lay('targets_carries', tc)
    if tc.state is not State.PASS:
        g['halted_at'] = 'targets_carries'
        return g, None
    S, other = tc.value['share'], tc.value['other']
    c3 = None
    c3_other = None
    # Set by BOTH branches below. The count form of the opportunity
    # identity is now checked on every configuration, not only C3.
    opp_other_counts = None
    # R14. The four vectors of the target identity, or None. `None` is the
    # honest value on a path that never composed them: an empty dict here
    # would read as "the pools were empty" where the truth is "no pass event
    # was composed", and `run_forecast` refuses rather than sealing a level
    # it cannot get.
    pass_event = None
    if shared_pass == 'c3' and qb is not None and qb.get('draws'):
        # C3: THE TARGET BUDGET COMES FROM THE THROW PROCESS, NOT FROM D1.
        #
        # `T = share x D1.team_targets` multiplied a share by a SEPARATELY
        # DRAWN count of the same football quantity -- two owners of one
        # number -- and then treated a continuous product as a count. The
        # audit measured the consequence: corr(team passing yards, team
        # receiving yards) = +0.001 under the production default, with the
        # yard identity violated in 12,800 of 12,800 draws.
        #
        # Under C3 the quarterbacks' attempts ARE the throw budget, a named
        # untargeted pool is drawn from it, and every remaining throw is dealt
        # to exactly one receiver by the SAME simplex. Receiver competition is
        # untouched; only the denominator changes, and it changes to the one
        # the football event actually has.
        ur = SP.untargeted_rate()
        if ur.state is not State.PASS:
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = f'{ur.code}: {ur.detail[:180]}'
            return g, None
        att_by_team = [np.stack([np.asarray(qb['draws']['att'][i], float)
                                 for i in qb['index_by_team'].get(t, [])])
                       if qb['index_by_team'].get(t) else None
                       for t in ateams]
        if any(a is None for a in att_by_team):
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = ('C3_TEAM_HAS_NO_QUARTERBACK_ROW: the throw '
                                'budget is the quarterbacks\' attempts, so a '
                                'team with no modelled passer has no budget')
            return g, None
        rng_c3 = np.random.default_rng(
            [seed, season * 100 + week,
             int(SEEDS.game_component(game_id).value), 0xC3])
        # R14. ONE COMPOSITION, ONE OWNER, AND THE VECTORS SURVIVE IT.
        #
        # `targeted_throws` and `deal_targets` were already correct and are
        # still exactly what runs: `shared_pass.compose_pass_event_ownership`
        # calls them UNCHANGED, in the same order, on the same generator, and
        # P9 asserted the composed output bit-identical to the uncomposed
        # deal. What changes is that all four vectors of the target identity
        # -- throws, untargeted, targeted, other -- leave this block instead
        # of being reduced to means for an evidence dict and discarded. The
        # two halves were one call site away from drifting apart, which is how
        # the rush composition came apart before R11.
        #
        # NO DRAWN VALUE MOVES HERE, on any configuration. Composing is not a
        # new configuration identity; SEALING what it returns is, and that is
        # R14's business in `run_forecast`, not this block's.
        comp = SP.compose_pass_event_ownership(
            att_by_team, S, other, starts, counts, ur.value, rng_c3)
        if comp.state is not State.PASS:
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = f'{comp.code}: {comp.detail[:180]}'
            return g, None
        T = comp.value['targets'].astype(float)
        tgt_vol = comp.value['targeted'].astype(float)
        c3_untargeted = comp.value['untargeted'].astype(float)
        c3_throws = comp.value['throws'].astype(float)
        # CLOSURE UNDER C3 IS A COUNT IDENTITY, AND IT IS CHECKED AS ONE.
        # `deal_targets` partitions an integer targeted-throw budget by a
        # multinomial, so `sum_i T_i + other == targeted` holds EXACTLY in
        # every draw by construction. The share-form identity the accounting
        # layer checks -- sum(T) + other_share x V == V -- is a property of
        # the `share x volume` architecture C3 replaces, and neither passing
        # the allocator's share (a different quantity) nor re-expressing the
        # dealt count as a share (which then breaks simplex closure) makes it
        # hold. Both were tried and both moved the failure rather than
        # removing it.
        #
        # So the count identity is asserted HERE, exactly, and reported under
        # its own name. The allocator's own `other` is left untouched so that
        # `share_simplex_closure` still checks the allocator.
        c3_other = comp.value['other'].astype(float)
        opp_other_counts = c3_other
        _per_team = np.stack([T[a:a + cc].sum(0)
                              for a, cc in zip(starts, counts)])
        c3_closure = int((np.abs(_per_team + c3_other
                                 - tgt_vol) > 1e-9).sum())
        # THE FOUR VECTORS, KEPT AND NAMED, so `run_forecast` can seal the
        # level the partition consumed instead of the one D1 drew and nothing
        # used. `published_team_targets` IS `targeted`: that is the vector the
        # multinomial dealt from, and P9 measured what publishing the other
        # one costs -- named receivers above the published level in 71,550 of
        # 139,800 sealed C3 draws, exact agreement in 0.
        pass_event = {
            'teams': list(ateams),
            'throws': c3_throws,
            'untargeted': c3_untargeted,
            'targeted': tgt_vol,
            'other': c3_other,
            'published_team_targets': {t: tgt_vol[k]
                                       for k, t in enumerate(ateams)},
            'identity': SP.TARGET_IDENTITY,
            'published_level_is': 'targeted'}
        c3 = {'untargeted_rate': float(ur.value),
              'count_closure_violating_cells': c3_closure,
              'count_closure_identity': 'sum_i targets_i + other == targeted, '
                                        'per team per draw, exact',
              'mean_throws': [round(float(np.mean(c3_throws[k])), 4)
                              for k in range(len(ateams))],
              'mean_targeted': [round(float(np.mean(tgt_vol[k])), 4)
                                for k in range(len(ateams))],
              'targets_dealt_mean': float(T.sum(0).mean()),
              'other_pool_mean': float(c3_other.sum(0).mean()),
              'target_budget_owner': 'the throw process (QB attempts), not D1',
              'd1_team_targets_unused': True}
        if c3_closure:
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = (
                f'C3_TARGET_COUNT_DOES_NOT_CLOSE: {c3_closure} cell(s) where '
                f'the dealt targets plus the other pool do not equal the '
                f'targeted budget. This is a construction, so a failure here '
                f'is a defect, never a tolerance to widen.')
            g['layers']['shared_pass'] = 'FAIL[C3_TARGET_COUNT_DOES_NOT_CLOSE]'
            return g, None
        g['layers']['shared_pass'] = 'PASS[C3_TARGET_BUDGET_FROM_THROWS]'
    else:
        # R4 -- A TARGET IS AN EVENT, SO IT IS DEALT, NOT MULTIPLIED.
        #
        # `T = share x team_targets` is a continuous product of a simplex
        # share and a continuous D1 level. It is declared `kind: 'count'` in
        # nfl/product/metrics.py and printed with `:.0f`, and `receiving_
        # conversion` then draws its binomial on `rint(T)` -- so the number
        # the reader sees, the number the conversion used, and the number that
        # is sealed are three different quantities.
        #
        # The level is integerised once, by its owner`s declared convention
        # (round-half-even, the same one `rushing_a1.allocate` requires), and
        # the resulting integer budget is then DEALT across the receivers and
        # the named `other` pool by the allocation simplex itself. The C3 path
        # beside this one has done exactly this since XL1; this brings the
        # non-C3 path onto the same construction rather than inventing a
        # second one.
        _lvl = SCT.integerise_level(
            np.stack([np.asarray(tv.value[('team_targets', t)], float)
                      for t in ateams]))
        if _lvl.state is not State.PASS:
            _lay('target_counts', _lvl)
            g['halted_at'] = 'target_counts'
            g['halt_reason'] = _lvl.detail[:200]
            return g, None
        tgt_vol = _lvl.value.astype(float)
        _rng_t = np.random.default_rng(
            [seed, season * 100 + week,
             int(SEEDS.game_component(game_id).value), COUNT_STREAM_TARGETS])
        _dealt_t = SCT.deal_counts(S, other, [tgt_vol[k] for k in
                                              range(len(ateams))],
                                   starts, counts, _rng_t, metric='targets')
        if _dealt_t.state is not State.PASS:
            _lay('target_counts', _dealt_t)
            g['halted_at'] = 'target_counts'
            g['halt_reason'] = _dealt_t.detail[:200]
            return g, None
        T = _dealt_t.value['counts'].astype(float)
        opp_other_counts = _dealt_t.value['other'].astype(float)
        _lay('target_counts', Outcome.ok(
            'TARGET_COUNTS_DEALT',
            value={'mean_dealt': _dealt_t.evidence['mean_dealt_per_draw'],
                   'mean_other': _dealt_t.evidence['mean_other_per_draw']},
            detail=_dealt_t.detail,
            level_cells_moved_by_rounding=_lvl.evidence['cells_moved'],
            level_mean_shift=_lvl.evidence['mean_shift'],
            closure=_dealt_t.evidence['closure'],
            contract_version=COUNT_CONTRACT_VERSION))
        g['layers']['shared_pass'] = f'NOT_APPLICABLE[SHARED_PASS_{shared_pass.upper()}]'

    # ---- carries (RB only, simplex, its own group layout) ----------------
    rb = [q for q in recv if q['position'] in CARRY_POS]
    rb_ids = [q['gsis_id'] for q in rb]
    rb_pos = [q['position'] for q in rb]
    rb_starts, rb_counts, j = [], [], 0
    for t in ateams:
        n = sum(1 for q in rb if q['team'] == t)
        rb_starts.append(j); rb_counts.append(n); j += n
    # C1. THE `other` MASS MUST BE ON THE SAME DENOMINATOR AS THE BUDGET.
    #
    # `p4c_build` fits `mass_pool` as `mall - ms` where `mall` sums EVERY
    # position, so for the carries class it is the share of TEAM CARRIES not
    # taken by modelled backs -- 0.1989, which is the non-RB mass (quarterback
    # rushing 0.157, receivers 0.030, tight ends 0.004) almost exactly.
    #
    # This engine does not multiply those shares by team carries. When A1 owns
    # the partition it multiplies them by A1's `rb` CATEGORY, from which kneel,
    # designed_qb, wr, te and fringe are already gone -- so the default pool
    # takes the same mass off a second time and the modelled backs lose about
    # 19 points of their budget. Measured on the 2026 week-1 slate: carries
    # projected 7.42 against 10.55 actual, bias -3.12 at z = -3.14, while
    # targets -- whose class denominator IS what production feeds it -- came in
    # essentially unbiased under the same estimator and the same code.
    #
    # `mass_pool_partition` is the same numerator on the RUNNING-BACK
    # denominator, 0.0088. Selected HERE, beside the line that chooses the
    # multiplier, because the two must move together; and passed by swapping
    # the pool rather than by adding an argument to `layers.targets_carries`,
    # because the frozen Q9 candidate identity hashes that module's source and
    # editing it would break a freeze this change has no business touching.
    #
    # Registration: predeclaration_c1_denominator.md sha256 9d0443e1,
    # evaluated walk-forward on 2022-2024 in slate_audit/C1_EVALUATION.json.
    _cpar = fits['p4c_params_carries'].value
    if rushing_budget is not None:
        _part = (_cpar or {}).get('mass_pool_partition')
        if _part is None or not len(_part):
            # NEVER FALL BACK TO THE TEAM POOL. That fallback IS the double
            # subtraction, and it would be invisible in the output.
            o = Outcome.fail(
                'P4C_PARTITION_POOL_MISSING',
                'the carry budget is A1\'s `rb` partition but the fitted P4C '
                'carry parameters carry no `mass_pool_partition`. Refused '
                'rather than defaulting to the team-denominator pool, which '
                'is the defect this selection exists to fix.',
                has_mass_pool=bool((_cpar or {}).get('mass_pool') is not None))
            _lay('carries', o)
            g['halted_at'] = 'carries'
            g['halt_reason'] = o.detail[:200]
            return g, None
        _cpar = dict(_cpar)
        _cpar['mass_pool'] = _part
        _cpar['mass_mean'] = float(np.asarray(_part).mean())
        g['layers']['carry_other_denominator'] = \
            'PASS[A1_RB_PARTITION_POOL]'
    else:
        g['layers']['carry_other_denominator'] = \
            'NOT_APPLICABLE[D1_TEAM_CARRIES_POOL]'
    car = LY.targets_carries(
        pa, 'carries', [fits['C_carries'].value.get(p, 0.0) for p in rb_ids],
        rb_pos, (rb_starts, rb_counts), rb_ids,
        _cpar, m=m, seed=seed,
        game_id=game_id, ordinal=season * 100 + week)
    _lay('carries', car)
    if car.state is not State.PASS:
        g['halted_at'] = 'carries'
        g['halt_reason'] = car.detail[:200]
        return g, None
    Sc, other_c = car.value['share'], car.value['other']
    # WHOSE CARRIES ARE THE BACKS COMPETING FOR? Exactly one layer may answer.
    if rushing_budget is None:
        car_vol = np.stack([_team_carries(t) for t in ateams])
        g['layers']['rushing_budget_owner'] = \
            'NOT_APPLICABLE[D1_TEAM_CARRIES]'
    else:
        missing = [t for t in ateams if t not in rushing_budget]
        if missing:
            o = Outcome.fail(
                'RUSHING_BUDGET_TEAM_MISSING',
                f'A1 supplied no running-back carry budget for {missing}. A '
                f'missing budget is refused rather than silently falling back '
                f'to the D1 team-carry level, because the fallback is the '
                f'duplicate owner this argument exists to remove.',
                missing=missing)
            _lay('rushing_budget', o)
            g['halted_at'] = 'rushing_budget'
            g['halt_reason'] = o.detail[:200]
            return g, None
        car_vol = np.stack([np.asarray(rushing_budget[t], float).reshape(-1)
                            for t in ateams])
        if car_vol.shape != (len(ateams), m):
            o = Outcome.fail(
                'RUSHING_BUDGET_DRAW_MISMATCH',
                f'the A1 carry budget has shape {list(car_vol.shape)} against '
                f'{[len(ateams), m]}. These layers share one draw index, so '
                f'a '
                f'mismatch is refused rather than reshaped.',
                got=list(car_vol.shape))
            _lay('rushing_budget', o)
            g['halted_at'] = 'rushing_budget'
            g['halt_reason'] = o.detail[:200]
            return g, None
        # A1's budget can never exceed the team carry level it partitions.
        # Checked rather than assumed: if it did, the backs would be dealt
        # carries the game did not contain.
        tc_lvl = np.stack([np.asarray(_team_carries(t), float)
                           for t in ateams])
        over = int((car_vol > tc_lvl + 1e-9).sum())
        if over:
            o = Outcome.fail(
                'RUSHING_BUDGET_EXCEEDS_TEAM_CARRIES',
                f'{over} cell(s) where the A1 running-back budget is above '
                f'the D1 team-carry level it is a partition of. A partition '
                f'cannot exceed the thing partitioned.', n_cells=over)
            _lay('rushing_budget', o)
            g['halted_at'] = 'rushing_budget'
            g['halt_reason'] = o.detail[:200]
            return g, None
        _lay('rushing_budget', Outcome.ok(
            'RUSHING_BUDGET_FROM_A1', value=True,
            detail='the running-back pool is A1\'s `rb` category, not the '
                   'whole D1 team-carry level; A1 is the sole owner of the '
                   'rushing-opportunity partition',
            mean_rb_budget=[round(float(x.mean()), 4) for x in car_vol],
            mean_team_carries=[round(float(x.mean()), 4) for x in tc_lvl]))
        g['layers']['rushing_budget_owner'] = 'PASS[A1_RB_CATEGORY]'
    # R4 -- A CARRY IS AN EVENT, SO IT IS DEALT, NOT MULTIPLIED.
    #
    # THE DEFECT. `C = share x budget` is a continuous product and it reached
    # the sealed artifact as float64: non-integer in 243,766 of 384,000 cells
    # across the 102 sealed runs (63.48%), and in 795 of 1,000 cells for
    # tonight`s Kansas City RB1. `nfl/product/metrics.py` declares
    # ('rushing','carries') `kind: 'count'` and `render.py` prints it `:.0f`,
    # so a "9.5+" threshold was being read off a quantity that is 10.4183 in a
    # draw where the back carried the ball either ten times or eleven and
    # never 10.4183 times. It is not a display problem: `layers.rushing_td`
    # draws its binomial on `rint(C)`, so the touchdown layer and the sealed
    # carry column were already two different numbers.
    #
    # WHY NOT ROUND. Rounding each player`s cell independently destroys the
    # closure the allocation was built to satisfy -- k independent roundings
    # of a partition do not sum back to the budget -- and rounding a final
    # mean is worse still, because a mean is not a draw and a threshold
    # probability read off a rounded mean is not a probability of anything.
    #
    # WHAT THIS DOES. The integer budget is DEALT:
    #
    #   (C_1..C_k, C_other) ~ Multinomial(budget, (s_1..s_k, other_share))
    #
    # so `sum_i C_i + C_other == budget` exactly, in integers, in every draw.
    # The probability vector IS the simplex `layers.targets_carries` produced,
    # so the competition between backs is untouched and E[C_i] is the same
    # `budget x s_i` the product gave. Nothing is fitted, clipped or
    # renormalised. The VARIANCE rises, because dealing a finite number of
    # carries to a finite number of backs is genuinely noisier than splitting
    # a level by a share, and that noise was missing rather than absent.
    _cl = SCT.integerise_level(car_vol)
    if _cl.state is not State.PASS:
        _lay('carry_counts', _cl)
        g['halted_at'] = 'carry_counts'
        g['halt_reason'] = _cl.detail[:200]
        return g, None
    car_vol = _cl.value.astype(float)
    _rng_c = np.random.default_rng(
        [seed, season * 100 + week,
         int(SEEDS.game_component(game_id).value), COUNT_STREAM_CARRIES])
    _dealt_c = SCT.deal_counts(Sc, other_c,
                               [car_vol[k] for k in range(len(ateams))],
                               rb_starts, rb_counts, _rng_c, metric='carries')
    if _dealt_c.state is not State.PASS:
        _lay('carry_counts', _dealt_c)
        g['halted_at'] = 'carry_counts'
        g['halt_reason'] = _dealt_c.detail[:200]
        return g, None
    C = _dealt_c.value['counts'].astype(float)
    carry_other_counts = _dealt_c.value['other'].astype(float)
    _lay('carry_counts', Outcome.ok(
        'CARRY_COUNTS_DEALT',
        value={'mean_dealt': _dealt_c.evidence['mean_dealt_per_draw'],
               'mean_other': _dealt_c.evidence['mean_other_per_draw']},
        detail=_dealt_c.detail,
        level_cells_moved_by_rounding=_cl.evidence['cells_moved'],
        level_mean_shift=_cl.evidence['mean_shift'],
        closure=_dealt_c.evidence['closure'],
        note='the `other` pool here is the unmodelled-back mass on the A1 '
             '`rb` denominator (C1), not the non-RB categories -- those are '
             'owned by rushing_a1 and reported under rush_category_ownership',
        contract_version=COUNT_CONTRACT_VERSION))

    ordinal = season * 100 + week
    # SC2. RESERVE THE INTERCEPTED THROWS BEFORE THE CATCHES ARE DRAWN.
    #
    # Off by default and reachable only under C3, because it is the C3 target
    # budget that the interception draw has to be made coherent with. Every
    # arm that does not ask for it runs the identical call it always ran.
    _sc2 = None
    if reserve_interceptions and shared_pass == 'c3' and qb is not None:
        _int_by_team = []
        for k, t in enumerate(teams):
            sel = list(qb['index_by_team'].get(t, []))
            _int_by_team.append(
                np.stack([np.asarray(qb['draws']['int'][i], float)
                          for i in sel]).sum(0) if sel else np.zeros(m))
        _rng_sc2 = np.random.default_rng(
            [seed, season * 100 + week,
             int(SEEDS.game_component(game_id).value), 0x5C2])
        _res = SP.deal_interceptions(T, starts, counts, _int_by_team,
                                     _rng_sc2)
        _lay('interception_reservation', _res)
        if _res.state is not State.PASS:
            g['halted_at'] = 'interception_reservation'
            g['halt_reason'] = _res.detail[:200]
            return g, None
        _sc2 = _res.value
        g['accounting']['interception_reservation'] = {
            k: v for k, v in _res.evidence.items() if k != 'value'}
    cv = LY.receiving_conversion(
        tc, T, fits['receiving_priors'].value, ids, pos, ordinal, m=m,
        seed=seed, intercepted=_sc2,
        pick_share=(None if _sc2 is None
                    else SP.INTERCEPTION_SHARE_OF_TARGETS))
    _lay('receiving_conversion', cv)
    tdp = dict(fits['td_priors_rec'].value)
    tdp['pos_catch_rate'] = fits['receiving_priors'].value['pos_catch_rate']
    td = LY.td_layer(cv, T, tdp, ids, pos, ordinal, m=m, seed=seed)
    _lay('receiving_td', td)
    rtd = LY.rushing_td(car, C, fits['td_priors_rush'].value, rb_ids, rb_pos,
                        ordinal, m=m, seed=seed)
    _lay('rushing_td', rtd)
    # THE CONVERSION CONSUMES THE DEALT CARRIES, on the same rows and the
    # same draw index as the carry counts and the rushing touchdowns. Nothing
    # is resampled here, so the yards belong to the carries the accounting
    # already closed on.
    ry = LY.rushing_conversion(car, C, None, rb_ids, rb_pos, ordinal,
                               m=m, seed=seed)
    _lay('rushing_conversion', ry)

    for o in (cv, td, rtd, ry):
        if o.state is not State.PASS:
            g['halted_at'] = 'conversion_or_td'
            g['halt_reason'] = o.detail[:200]
            return g, None

    # ---- accounting, on the same draw index -----------------------------
    A = np.stack([np.asarray(pa.value[p], np.float32).reshape(-1)
                  for p in ids])
    rec_acc = ACC.reconcile_nonqb(
        S, other, tgt_vol, T, (A > 0).astype(np.float32), starts, counts,
        receptions=cv.value['receptions'], receiving_td=td.value['td'],
        receiving_yards=cv.value['receiving_yards'],
        # Under C3 the opportunity identity is checked as exact integer
        # counts, which is stricter than the share form it replaces.
        # BOTH branches now deal an integer budget, so the exact count
        # form of the opportunity identity is available on every
        # configuration rather than only under C3.
        opportunity_other_counts=opp_other_counts)
    g['accounting']['receiving'] = f'{rec_acc.state.value}[{rec_acc.code}]'
    qb_rush, qb_records = None, []
    if qb is not None and qb.get('r2'):
        # R2: THERE IS NOTHING TO COMPOSE. The level was apportioned from
        # D1 x QB3 before QB V1 ran, so the draws already sit at the allocated
        # level. The division that produced factors to 59.85 does not execute,
        # and the OWN-4 donor mechanism has no denominator to repair -- both
        # are unreachable rather than merely unused.
        g['accounting']['qb_composition'] = 'PASS[QB_LEVEL_OWNED_BY_D1_X_QB3]'
        g['accounting']['qb_composition_mass'] = \
            'PASS[QB_COMPOSITION_NO_DIVISION_PERFORMED]'
        g['accounting']['qb_composition_amplification'] = {
            'rows_failing_rate_fidelity': 0, 'cells_stretched': 0,
            'cells_live': 0, 'frac_stretched': 0.0, 'factor_max': 0.0,
            'condition': 'R2 -- no ratio is formed, so none can be extreme',
            'repair': 'R2 applied'}
        g['r2'] = qb['r2']
        share_ok = QBACC.reconcile_allocation_share(
            {t: qb['allocation'][t] for t in teams if t in qb['allocation']},
            {t: [qb['rows'][i]['gsis_id'] for i in
                 qb['index_by_team'].get(t, [])] for t in teams})
        g['accounting']['qb_allocation_share'] = \
            f'{share_ok.state.value}[{share_ok.code}]'
        g['accounting']['qb_allocation_share_evidence'] = {
            k: v for k, v in share_ok.evidence.items() if k != 'value'}
    elif qb is not None and qb.get('allocation'):
        # THE COMPOSITION W2 SECTION 7.1 ALREADY SPECIFIES:
        #     QB dropbacks = team dropbacks x QB dropback share
        # QB V1 forecasts a passer's line CONDITIONAL ON BEING THE PRIMARY
        # PASSER. The allocation supplies the conditioning it was always
        # missing. This is composition, not a replacement of a frozen model,
        # and the rate-type outputs are untouched because every count scales by
        # the same factor.
        D = qb['draws']
        alloc = qb['allocation']
        scaled = {k: np.array(v, float) for k, v in D.items()}
        applied = 0
        repaired_cells = repaired_rows = 0
        at_risk = 0.0
        amp_worst = 0.0
        amp_stretched = amp_cells = amp_fail = 0
        for t in teams:
            a = alloc.get(t)
            if a is None:
                continue
            tdb = np.asarray(tv.value[('team_dropbacks_part', t)], float)
            pos_in_alloc = {pid: i for i, pid in enumerate(a['pids'])}
            for i in qb['index_by_team'].get(t, []):
                pid = qb['rows'][i]['gsis_id']
                j = pos_in_alloc.get(pid)
                if j is None:
                    scaled['db'][i] = 0.0
                    for f in QBV1.FIELDS:
                        scaled[f][i] = 0.0
                    continue
                target = np.asarray(tdb * a['shares'][j], float)
                drawn = np.asarray(D['db'][i], float)
                # OWN-4. A STOCHASTIC ZERO MUST NOT ERASE ALLOCATED OPPORTUNITY.
                #
                # QB V1 draws its OWN level -- V from the team-dropback pool and
                # S from the share pool, DB = rint(V*S) -- which is the very
                # quantity D1 and QB3 already own. This composition then
                # reconciles the duplicate by division, and where QB V1's
                # independent level happens to be zero the ratio is undefined
                # and the allocated dropbacks were being dropped: measured at
                # 20 cells of 47,600, but up to 37.7 dropbacks in a single draw
                # -- an entire team's passing game for that draw.
                #
                # The repair borrows a donor draw FROM THE SAME ROW. Every rate
                # in qb2_lib.simulate is a row-level scalar, so any non-zero
                # draw of this row carries the same rates; scaling it to the
                # allocated target reproduces exactly what the composition
                # would have done had the level draw not been zero. Nothing is
                # fitted, nothing is clipped, no survivor is renormalised, and
                # the terminal-state identity survives because every field of
                # the donor scales by one factor.
                cons = QBACC.conserve_allocated_mass(
                    target, drawn,
                    [seed, int(season) * 100 + int(week),
                     int.from_bytes(str(pid).encode()[-8:], 'little'), 0x04])
                if cons.state is not State.PASS:
                    g['halted_at'] = 'qb_composition'
                    g['halt_reason'] = f'{pid} on {t}: {cons.detail[:220]}'
                    g['accounting']['qb_composition'] = \
                        f'{cons.state.value}[{cons.code}]'
                    return g, None
                src = cons.value
                repaired_cells += cons.evidence['cells_needing_repair']
                repaired_rows += int(bool(cons.evidence['cells_needing_repair']))
                at_risk = max(at_risk,
                              cons.evidence.get('max_single_draw_at_risk', 0.0))
                amp = QBACC.measure_composition_amplification(target,
                                                              drawn[src])
                amp_worst = max(amp_worst,
                                float(amp.evidence.get('factor_max') or 0.0))
                amp_stretched += int(amp.evidence.get('n_stretched') or 0)
                amp_cells += int(amp.evidence.get('n_cells') or 0)
                if amp.state is State.FAIL:
                    amp_fail += 1
                den = drawn[src]
                with np.errstate(divide='ignore', invalid='ignore'):
                    fac = np.where((target > 0) & (den > 0),
                                   target / np.maximum(den, 1e-9), 0.0)
                for f in QBV1.FIELDS:
                    scaled[f][i] = np.asarray(D[f][i], float)[src] * fac
                applied += 1
        qb = dict(qb, draws=scaled)
        g['qb_allocation_applied'] = applied
        # MASS CONSERVATION WAS NEVER THE PROPERTY IN DOUBT. This reported
        # PASS[QB_COMPOSITION_MASS_CONSERVED] while composing quarterbacks by
        # stretching a one-dropback donor draw up to the allocated level --
        # measured factor 59.85, producing a 49.14 passing-touchdown tail for a
        # passer whose raw draws max at 5. The verdict now names what actually
        # failed, and the mass statement is kept beside it rather than standing
        # in for it. The repair is R2 and is not authorised here.
        _mass = ('QB_COMPOSITION_MASS_CONSERVED' if not repaired_cells
                 else 'QB_COMPOSITION_ZERO_DRAW_REPAIRED')
        g['accounting']['qb_composition'] = (
            f'PASS[{_mass}]' if not amp_fail
            else f'FAIL[QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED]')
        g['accounting']['qb_composition_mass'] = f'PASS[{_mass}]'
        g['accounting']['qb_composition_amplification'] = {
            'rows_failing_rate_fidelity': amp_fail,
            'cells_stretched': amp_stretched, 'cells_live': amp_cells,
            'frac_stretched': (round(amp_stretched / amp_cells, 6)
                               if amp_cells else None),
            'factor_max': round(amp_worst, 4),
            'condition': 'drawn < target -- parameter-free, nothing fitted',
            'repair': 'R2, pre-registered, not authorised in this task'}
        g['qb_composition_repair'] = {
            'cells_repaired': repaired_cells, 'rows_repaired': repaired_rows,
            'max_single_draw_dropbacks_at_risk': round(at_risk, 6),
            'mechanism': 'donor draw borrowed from the same row and scaled to '
                         'the allocated target; row-level rates are identical '
                         'across a row so the donor carries them',
            'no_survivor_renormalisation': True, 'nothing_fitted': True}
        # FEED THE GUARD ITS INPUT, at the one place that has both sides.
        # The scaling above zeroes a forecast row that the allocation does not
        # name. The REVERSE -- an allocation entry naming a quarterback QB V1
        # never forecast -- had no counterpart at all, and his share left the
        # system without a refusal. Measured on the real 2026 week-1 slate:
        # 35 quarterbacks, 5.13% of every team's dropbacks, MIA 33.8%.
        share_ok = QBACC.reconcile_allocation_share(
            {t: alloc[t] for t in teams if t in alloc},
            {t: [qb['rows'][i]['gsis_id'] for i in qb['index_by_team'].get(t, [])]
             for t in teams})
        g['accounting']['qb_allocation_share'] = \
            f'{share_ok.state.value}[{share_ok.code}]'
        g['accounting']['qb_allocation_share_evidence'] = {
            k: v for k, v in share_ok.evidence.items() if k != 'value'}
    if qb is not None:
        idx = qb['index_by_team']
        D = qb['draws']
        # THE NON-QB ALLOCATION FRAME, because this vector is stacked
        # against `rb_starts`/`rb_counts` in `reconcile_rushing` and those
        # describe the teams the allocation ran for. The BOTH-TEAMS question
        # -- does each club's quarterback rushing fit inside that club's
        # carries -- is still asked in full by `reconcile_team_volume` below,
        # which is handed `team_carry_draws` for every team in the game.
        rows_by_team = {t: idx.get(t, []) for t in ateams}
        # The team's QB rush opportunity in draw j is the SUM over that team's
        # quarterbacks, because the containment question is about the team's
        # carry budget, not about any one passer.
        qb_rush = np.stack([
            (D['rush_opp'][rows_by_team[t]].sum(0) if rows_by_team[t]
             else np.zeros(m)) for t in ateams])
        # THE QUARTERBACK RECORDS ARE BUILT LATER, NOT HERE. `PR.summarise`
        # computes its mean and quantiles EAGERLY, and the C3 credit below
        # rewrites `qb['draws']['cmp' | 'pyds' | 'ptd']` in place afterwards.
        # Summarising at this point produced a record contract describing the
        # PRE-credit draws while the sealed npz carried the post-credit ones --
        # the same "checked an intermediate value" defect as the accounting
        # verdicts, one layer along. See `_qb_records_from_final_draws`.
    rush_acc = ACC.reconcile_rushing(
        Sc, other_c, car_vol, C, rb_starts, rb_counts,
        rushing_td=rtd.value['rush_td'],
        rushing_yards=ry.value['rushing_yards'],
        qb_rush_opportunity=qb_rush)
    g['accounting']['rushing'] = f'{rush_acc.state.value}[{rush_acc.code}]'

    # ---- R4: EXPLICIT RUSH CATEGORY OWNERSHIP ---------------------------
    #
    # The rebuilt board has to be able to walk team rush opportunity ->
    # category allocation -> player allocation -> unowned mass, and until now
    # it could not, because only A1's `rb` category was ever handed over. The
    # other five -- kneel, designed_qb, wr, te, fringe -- were computed by one
    # multinomial alongside it and thrown away at the call site, which is why
    # D6 could measure 24.1% of the frame's carries as unowned and could not
    # say whose they were.
    #
    # NOTHING IS FORCED ONTO A NAMED BACK. The categories are A1's own draw;
    # this reads them. And nothing is absorbed: `unowned_after` is zero by
    # construction and a non-zero value FAILS rather than becoming a residual.
    if rush_categories:
        # OVER BOTH CLUBS, NOT ONLY THE ONES THE APPEARANCE LAYER RAN FOR.
        # The category partition is a TEAM quantity: it needs the carry level
        # and the scramble draw and nothing else. A team deferred under
        # APPEARANCE_TEAM_DEFERRED has no player split and still has a fully
        # attributed category ledger, and omitting it here would leave the
        # exact team whose evidence is thinnest as the one with no rush
        # ownership record at all.
        _lteams = [t for t in teams if all(
            (t, c) in rush_categories for c in RA1.CATEGORIES)]
        _scr_by_team = {
            t: (np.stack([np.asarray(qb['draws']['scr'][i], float)
                          for i in qb['index_by_team'].get(t, [])]).sum(0)
                if qb is not None and qb['index_by_team'].get(t)
                else np.zeros(m)) for t in _lteams}
        _led = RA1.ownership_ledger(
            _lteams,
            {t: _team_carries(t) for t in _lteams},
            _scr_by_team,
            rush_categories,
            player_carries={t: C[a:a + c] for t, a, c
                            in zip(ateams, rb_starts, rb_counts)},
            player_other={t: carry_other_counts[k]
                          for k, t in enumerate(ateams)},
            qb_rush_opportunity=({t: qb_rush[k] for k, t in enumerate(ateams)}
                                 if qb_rush is not None else None))
        _lay('rush_category_ownership', _led)
        if _led.state is not State.PASS:
            g['halted_at'] = 'rush_category_ownership'
            g['halt_reason'] = _led.detail[:200]
            return g, None
        g['rush_ownership'] = _led.value
        # U1 -- RUSH OPPORTUNITY HAS ONE OWNER, OR THE BOARD SAYS SO.
        #
        # THE DEFECT. `rushing_a1.allocate` returns
        # `qb_rush_opportunity = scrambles + designed_qb` and NOBODY CONSUMED
        # IT. `qb_rush` a few lines above is built from the QB layer's own
        # `rush_opp` draw instead, so the same football quantity -- how many
        # of this team's carries its quarterbacks took -- reached the sealed
        # board with two independently drawn answers, and the `rb` budget the
        # named backs were dealt from was carved out of the OTHER one. The
        # exact consequence, on the arrays this engine holds:
        #
        #   named_owners - team_carries
        #       = (rush_opp - scr - designed_qb)
        #         - (kneel + wr + te + fringe + unmodelled_back_pool)
        #         - (team_carries - rint(team_carries))
        #
        # Verified cell for cell on run d1e2727743c93990: Kansas City, 149 of
        # 1,000 draws over-allocated, worst 9.6915 carries.
        #
        # THE FIX IS UPSTREAM AND IT IS A CONSTRUCTION, NOT A CLAMP: pass the
        # QB layer's designed-rush count to `allocate(qb_designed_rush=...)`,
        # which stops drawing `designed_qb` and draws the other five
        # categories from the exact conditional multinomial. Then the two
        # answers are one array and this verdict reads PASS.
        #
        # THIS DOES NOT HALT THE GAME, DELIBERATELY. The condition is a
        # property of the arrays this engine was HANDED, not of anything it
        # computed, and the product layer already quarantines the rushing
        # family on it. A halt here would replace a quarantined family with no
        # board at all and would hide the very counts that say how large the
        # breach is. It is recorded as a FAIL verdict so it cannot be read as
        # a pass and cannot return silently.
        _so = {t: (_led.value[t].get('qb_rush_opportunity_single_owner') or {})
               for t in _lteams}
        _two = sorted(t for t, v in _so.items()
                      if v.get('state') == 'TWO_OWNERS')
        g['accounting']['rush_opportunity_single_owner'] = (
            f'FAIL[RUSH_OPPORTUNITY_HAS_TWO_OWNERS]' if _two
            else 'PASS[RUSH_OPPORTUNITY_ONE_OWNER]')
        g['accounting']['rush_opportunity_single_owner_evidence'] = {
            'teams_with_two_owners': _two,
            'per_team': {
                t: {'state': v.get('state'),
                    'cells_disagreeing': v.get('cells_disagreeing'),
                    'a1_answer_mean': v.get('a1_answer_mean'),
                    'qb_layer_answer_mean': v.get('qb_layer_answer_mean'),
                    'implied_draws_over_allocated':
                        v.get('implied_draws_over_allocated'),
                    'implied_max_over_allocation':
                        ((v.get('implied_named_owner_over_allocation') or {})
                         .get('max'))}
                for t, v in sorted(_so.items())},
            'repair': ('rushing_a1.allocate(qb_designed_rush=...) -- the QB '
                       'layer becomes the single owner and the remaining five '
                       'categories are drawn from the conditional '
                       'multinomial. Nothing is clipped or renormalised.')}
        # ---- THE DECOMPOSED CONTAINMENT VERDICT --------------------------
        #
        # THE TEST THAT WAS MISSING, AND WHY ITS ABSENCE COST A REPAIR.
        # `quality_gates.gate_rush_accounting` fires on ONE summed quantity --
        # RB carries plus QB scrambles plus QB designed runs against the team
        # level -- so a reader of a fired gate cannot tell which layer moved.
        # An earlier workstream read it as a defect in A1's multinomial and
        # wrote a repair for the running-back deal. Decomposed against the
        # sealed arrays of board 96954efc523bd7d3 (2026_01_DEN_KC, 1,000
        # draws) the RB deal is over the gate's half-carry tolerance in ZERO
        # draws on both clubs (max +0.2619 DEN, +0.0854 KC) while RB plus the
        # quarterbacks' rush opportunity is over in 149 and 148 draws by up to
        # 6.1219 and 9.6915 carries.
        #
        # So the engine reports BOTH HALVES, separately, on every run. It
        # repairs nothing and halts nothing: the condition is a property of
        # the arrays this engine was HANDED, the product layer already
        # quarantines the rushing family on it, and a halt would replace a
        # quarantined family with no board and hide the counts that say how
        # large the breach is.
        #
        # The level is `_team_carries`, which is the vector this game actually
        # partitioned. Under the R11 composition that is also the vector the
        # board publishes; under R9 it is not, and the evidence says which by
        # carrying `level_is_integer`.
        _cteams = [t for t in _lteams if t in ateams]
        _ci = {t: list(ateams).index(t) for t in _cteams}
        if _cteams and qb_rush is not None:
            _cont = RA1.assert_named_owner_containment(
                _cteams,
                {t: np.asarray(_team_carries(t), float) for t in _cteams},
                {t: C[rb_starts[_ci[t]]:rb_starts[_ci[t]] + rb_counts[_ci[t]]]
                 for t in _cteams},
                {t: qb_rush[_ci[t]] for t in _cteams})
        else:
            _cont = Outcome.not_applicable(
                'RUSH_CONTAINMENT_NO_PLAYER_FRAME',
                'no club in this game carries both a named-back split and a '
                'quarterback rush draw, so the decomposed containment has '
                'nothing to decompose. NOT_APPLICABLE with a reason rather '
                'than a pass over an empty set.',
                teams_with_categories=list(_lteams),
                teams_with_player_split=list(ateams))
        g['accounting']['rush_named_owner_containment'] = \
            f'{_cont.state.value}[{_cont.code}]'
        g['accounting']['rush_named_owner_containment_evidence'] = {
            k: v for k, v in _cont.evidence.items() if k != 'value'}
        # A CLUB WITH NO PLAYER SPLIT IS NAMED, NEVER FOLDED IN AS ZERO.
        # A team deferred under APPEARANCE_TEAM_DEFERRED has a fully
        # attributed category ledger and no named backs; adding a zero row for
        # it would report "no over-allocation" for a quantity nobody measured.
        _no_split = [t for t in _lteams if t not in ateams]
        if _no_split:
            g['accounting']['rush_named_owner_containment_evidence'][
                'teams_without_player_split_not_measured'] = _no_split
        rush_category_draws = {
            t: {c: np.asarray(rush_categories[(t, c)]).reshape(-1)
                for c in RA1.CATEGORIES} for t in _lteams}
    else:
        _lay('rush_category_ownership', Outcome.not_applicable(
            'RUSH_CATEGORIES_NOT_SUPPLIED',
            'A1`s full category matrix was not handed to this engine, so the '
            'rush residual can be measured and cannot be attributed. This is '
            'the state D6 measured at a 24.1% frame mean of unowned carries. '
            'It is NOT_APPLICABLE rather than PASS because nothing was '
            'checked: pass rush_categories=allocate(...).value["carries"] to '
            'make the partition auditable from the sealed board.',
            a1_rb_budget_supplied=rushing_budget is not None))
        rush_category_draws = None
    g['accounting']['detail'] = {
        'receiving': {k: v for k, v in rec_acc.evidence.items()
                      if k not in ('value', 'other_mass_interpretation')},
        'rushing': {k: v for k, v in rush_acc.evidence.items()
                    if k not in ('value', 'qb_carry_measurement')}}
    chain = ACC.reconcile_chain(tv, ap, pa, tc, cv, td)
    g['accounting']['chain'] = f'{chain.state.value}[{chain.code}]'
    if qb is not None:
        # FEED THE DORMANT GUARD. reconcile_team's hard rush check has never
        # refused anything because no caller ever passed it a budget.
        rows_here = [qb['rows'][i] for t in teams
                     for i in qb['index_by_team'].get(t, [])]
        sel = [i for t in teams for i in qb['index_by_team'].get(t, [])]
        Dsub = {k: np.asarray(v)[sel] for k, v in qb['draws'].items()}
        qv = QBACC.reconcile_team_volume(
            Dsub, rows_here,
            team_dropback_draws={t: np.asarray(
                tv.value[('team_dropbacks_part', t)], float) for t in teams},
            # SC1's coupled level where it is live. This check asks whether
            # the quarterbacks' rush opportunity fits inside the team's
            # carries; asking it against a carry vector on a different draw
            # index is the same mismatch SC1 exists to remove.
            team_carry_draws={t: _team_carries(t) for t in teams},
            # Under R2 the level is an integer apportionment, so the dropback
            # identity is checked as exact EQUALITY against rint(budget)
            # instead of the incumbent's <= against the float budget. Stricter,
            # and declared in the R2 pre-registration before it was measured.
            integer_level=bool(qb.get('r2')))
        g['accounting']['qb_team_volume'] = f'{qv.state.value}[{qv.code}]'
        # FEED THE THIRD DORMANT GUARD. reconcile_cross_layer has been written,
        # correct and DEFERRED since R3 because no caller ever supplied the
        # receiving draws. They are in this run. Measured on the panel, team
        # passing yards and team receiving yards are the SAME quantity:
        # r = 0.9996, mean |difference| 0.26 yards, exact in 3,154 of 3,230
        # team-games, the residue being the named lateral exception.
        if c3 is not None:
            # C3, SECOND HALF: THE PASSER'S LINE IS A CREDIT FROM THE EVENT.
            # Completions, passing yards and passing touchdowns are no longer
            # drawn independently by QB V1 -- they ARE the receiving totals,
            # attributed back to the quarterbacks on the targeted-throw share.
            # One event, generated once, credited to both sides.
            rngc = np.random.default_rng(
                [seed, season * 100 + week,
                 int(SEEDS.game_component(game_id).value), 0xC301])
            cred_ok = True
            for k, t in enumerate(teams):
                sel = list(qb['index_by_team'].get(t, []))
                ri = [i for i, q in enumerate(recv) if q['team'] == t]
                if not sel or not ri:
                    continue
                A = np.stack([np.asarray(qb['draws']['att'][i], float)
                              for i in sel])
                # THE INTERCEPTIONS TRAVEL WITH THE ATTEMPTS. QB V1 drew them
                # from ITS OWN incompletions, so an intercepted attempt is an
                # attempt this credit may not also call a completion. Passing
                # them in is what lets the allocation reserve them instead of
                # producing a completion count the interception draw no longer
                # fits inside -- 5,929 sealed cells did exactly that.
                IN = np.stack([np.asarray(qb['draws']['int'][i], float)
                               for i in sel])
                # These layers return ROW-INDEXED arrays, not player-keyed
                # dicts; `ri` already holds the row indices for this team.
                R = np.asarray(cv.value['receptions'], float)[ri].sum(0)
                Y = np.asarray(cv.value['receiving_yards'], float)[ri].sum(0)
                TD = np.asarray(td.value['td'], float)[ri].sum(0)
                # CONSTRUCTED, NOT REPAIRED. `SP.credit_to_passers` split the
                # team line on the attempt SHARE with a multinomial -- a
                # with-replacement scheme over a finite pool of attempts,
                # which is what produced completions a passer never threw.
                # `credit_passing_line` deals the same events from the same
                # exchangeability assumption without replacement, so the
                # coherence holds by construction rather than by a guard.
                # QY1. OFF unless the resolved candidate asked for it, so
                # every sealed arm keeps the continuous share it was sealed
                # with. Supplied, the passing yards are a PARTITION of the
                # catches RC1 already drew rather than a division of their
                # sum, and `qb/pyds` becomes integer by construction.
                _atoms = None
                if qb_yard_atoms:
                    _rows = cv.value.get('receiving_yard_atoms')
                    if _rows is None:
                        g['accounting']['qb_yard_allocation'] = (
                            'BLOCKED[QY1_ATOMS_NOT_SUPPLIED]')
                        g['halted_at'] = 'shared_pass'
                        g['halt_reason'] = (
                            'the candidate asked for the QY1 atom partition '
                            'and the conversion layer returned no atoms. '
                            'Refused rather than falling back to the '
                            'continuous share under the QY1 name.')
                        cred_ok = False
                        break
                    _atoms, _bad = team_completion_atoms(
                        _rows, np.asarray(cv.value['receptions'], float),
                        ri, m)
                    if _bad is not None:
                        g['accounting']['qb_yard_allocation'] = (
                            f'FAIL[QY1_ATOM_ROW_MISMATCH row={_bad[0]} '
                            f'receptions={_bad[1]} atoms={_bad[2]}]')
                        g['halted_at'] = 'shared_pass'
                        g['halt_reason'] = (
                            f'receiver row {_bad[0]} carries {_bad[1]} '
                            f'reception(s) and {_bad[2]} per-catch '
                            f'yardage(s). The two cannot both be right.')
                        cred_ok = False
                        break
                cr = credit_passing_line(
                    A, IN, R, Y, TD, rngc, atoms=_atoms,
                    atom_rng=(None if _atoms is None else
                              np.random.default_rng(
                                  [seed, season * 100 + week,
                                   int(SEEDS.game_component(game_id).value),
                                   0xC302, k])))
                if cr.state is not State.PASS:
                    g['accounting']['shared_pass_credit'] = \
                        f'{cr.state.value}[{cr.code}]'
                    g['accounting']['shared_pass_credit_detail'] = \
                        cr.detail[:400]
                    _lay('shared_pass', cr)
                    g['halted_at'] = 'shared_pass'
                    g['halt_reason'] = cr.detail[:300]
                    cred_ok = False
                    break
                for n, i in enumerate(sel):
                    qb['draws']['cmp'][i] = cr.value['cmp'][n]
                    qb['draws']['pyds'][i] = cr.value['pyds'][n]
                    qb['draws']['ptd'][i] = cr.value['ptd'][n]
            if cred_ok:
                g['accounting']['shared_pass_credit'] = \
                    'PASS[PASSING_LINE_CREDITED_FROM_THE_RECEIVING_EVENT]'
                g['accounting']['qb_yard_allocation'] = (
                    'QY1_ATOM_PARTITION' if qb_yard_atoms
                    else 'CONTINUOUS_COMPLETION_SHARE')
                c3['passer_line_owner'] = ('the receiving event; QB V1 no '
                                           'longer draws cmp/pyds/ptd')
            g['c3'] = c3

        # ==============================================================
        # THE FINAL-VALUE GATE. EVERY QB MUTATION IS BEHIND US HERE.
        # ==============================================================
        # `run_forecast` evaluates qb_v1.identity_check, reconcile_draws and
        # reconcile_team on the QB draws BEFORE calling this engine, and the
        # C3 credit above then overwrites three of those columns. Those
        # verdicts are therefore about a draw set that no longer exists by the
        # time anything is sealed, which is how QB_DRAW_ACCOUNTING_HOLDS came
        # to be stamped on 101 of 101 artifacts over 5,278 cells with more
        # completions than attempts.
        #
        # So the identities are re-evaluated HERE, on `qb['draws']` -- the same
        # object the seal reads, after the last write to it. A failure refuses
        # through the `shared_pass` layer, which is a declared layer that
        # `run_forecast.STAGE_LAYERS` already reports, so the refusal reaches
        # the pipeline in its own vocabulary rather than as a traceback.
        #
        # SCOPE. The gate refuses only where THIS engine wrote the values, i.e.
        # where C3 ran. On a non-C3 run the engine does not touch the QB line
        # at all, the run_forecast verdicts are evaluated on exactly the draws
        # that get sealed, and their own HARD invariant already owns any
        # failure. The verdict is still recorded there, because a check that
        # ran and held is worth saying out loud.
        _final = QBACC.reconcile_draws(qb['draws'])
        _ident = QBV1.identity_check(qb['draws'])
        # QB CHECKS ONLY, AND THAT IS A DELIBERATE SCOPE, NOT AN OMISSION.
        # `draw_coherence.carry_containment` must NOT be evaluated here:
        # `_team_carries` returns the SC1-coupled vector while `run_forecast`
        # seals D1's raw vector, so an engine-side carry verdict would attest
        # to a vector nobody publishes -- the same shape of defect that lets
        # SC1_COHERENT read PASS in nine sealed runs whose PUBLISHED scramble
        # total exceeds their PUBLISHED carry total. The carry diagnostics and
        # the team closures belong where the published arrays are in hand.
        _coh = DC.qb_coherence(
            {f: np.asarray(qb['draws'][f]) for f in QBV1.FIELDS
             if f in qb['draws']})
        g['accounting']['qb_final_draw_accounting'] = \
            f'{_final.state.value}[{_final.code}]'
        g['accounting']['qb_final_dropback_identity'] = \
            f'{_ident.state.value}[{_ident.code}]'
        g['accounting']['qb_final_draw_coherence'] = \
            f'{_coh.state.value}[{_coh.code}]'
        g['accounting']['qb_final_draw_coherence_evidence'] = {
            k: v for k, v in _coh.evidence.items() if k != 'value'}
        g['accounting']['qb_final_values_checked_after'] = (
            'the C3 credit' if c3 is not None else
            'no engine-side QB mutation on this configuration')
        _failed = [o for o in (_final, _ident, _coh)
                   if o.state is not State.PASS]
        if _failed and c3 is not None:
            o = _failed[0]
            _lay('shared_pass', Outcome.fail(
                'QB_FINAL_DRAW_COHERENCE_VIOLATED',
                f'the passing line credited from the receiving event does not '
                f'satisfy the QB layer identities on the values that would be '
                f'sealed: {o.code}: {o.detail[:260]}',
                first_failure=o.code,
                **{k: v for k, v in o.evidence.items()
                   if k in ('violations', 'cells_checked', 'n_cells',
                            'not_evaluated')}))
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = f'{o.code}: {o.detail[:260]}'

        # THE RECORD CONTRACT, BUILT FROM THE FINAL DRAWS.
        for t in teams:
            for i in qb['index_by_team'].get(t, []):
                pid = qb['rows'][i]['gsis_id']
                mets = {}
                for fld, name in (('db', 'dropbacks'), ('att', 'attempts'),
                                  ('cmp', 'completions'),
                                  ('pyds', 'passing_yards'),
                                  ('ptd', 'passing_td'),
                                  ('int', 'interceptions'),
                                  ('sacks', 'sacks'),
                                  ('rush_opp', 'rush_opportunity'),
                                  ('ryds', 'rushing_yards'),
                                  ('rtd', 'rushing_td')):
                    mets[name] = PR.summarise(qb['draws'][fld][i],
                                              QBV1.SPEC_VERSION, name, run_id)
                qb_records.append(PR.record(pid, 'QB', game_id, run_id, mets))

        xl = {}
        for t in teams:
            qi = [n for n, tt in enumerate(
                [qb['rows'][i]['team'] for tt2 in teams
                 for i in qb['index_by_team'].get(tt2, [])]) if tt == t]
            sel_t = [i for i in qb['index_by_team'].get(t, [])]
            ri = [i for i, tt in enumerate(
                [q['team'] for q in recv]) if tt == t]
            if not sel_t or not ri:
                continue
            # The guard compares TEAM TOTALS -- it forms py.sum(0) - ry.sum(0)
            # -- but enforces row alignment, and a QB room and a receiver room
            # have different row counts. Summing to (1, m) first is
            # mathematically identical to what the guard computes and satisfies
            # its shape contract honestly. The guard is NOT loosened.
            Dt = {'pyds': np.stack([np.asarray(qb['draws']['pyds'][i], float)
                                    for i in sel_t]).sum(0)[None, :],
                  'ptd': np.stack([np.asarray(qb['draws']['ptd'][i], float)
                                   for i in sel_t]).sum(0)[None, :]}
            RY = np.stack([cv.value['receiving_yards'][i]
                           for i in ri]).sum(0)[None, :]
            RT = np.stack([td.value['td'][i] for i in ri]).sum(0)[None, :]
            o = QBACC.reconcile_cross_layer(Dt, receiving=RY, receiving_td=RT)
            xl[t] = {'state': f'{o.state.value}[{o.code}]',
                     **{k: v for k, v in o.evidence.items()
                        if k in ('violating_draws', 'td_violating_draws',
                                 'worst_abs_residual', 'n_draws')}}
            xl[t]['mean_abs_yard_residual'] = float(
                np.abs(Dt['pyds'].sum(0) - RY.sum(0)).mean())
            xl[t]['mean_team_passing_yards'] = float(Dt['pyds'].sum(0).mean())
            xl[t]['corr_passing_receiving'] = (
                float(np.corrcoef(Dt['pyds'].sum(0), RY.sum(0))[0, 1])
                if Dt['pyds'].sum(0).std() > 0 and RY.sum(0).std() > 0
                else None)
        g['accounting']['cross_layer'] = xl
        g['accounting']['detail']['qb_team_volume'] = {
            k: v for k, v in qv.evidence.items() if k != 'value'}

    # ---- player records --------------------------------------------------
    rb_index = {p: k for k, p in enumerate(rb_ids)}
    records = []
    for k, q in enumerate(recv):
        pid = q['gsis_id']
        mets = {
            'appearance': PR.summarise(ap.value[pid], LY.SPEC['appearance'],
                                       'appearance', run_id),
            'participation': PR.summarise(pa.value[pid],
                                          LY.SPEC['participation'],
                                          'participation', run_id),
            'targets': PR.summarise(T[k], LY.SPEC['targets_carries'],
                                    'targets', run_id),
            'receptions': PR.summarise(cv.value['receptions'][k],
                                       LY.SPEC['receiving_conversion'],
                                       'receptions', run_id),
            'receiving_yards': PR.summarise(cv.value['receiving_yards'][k],
                                            LY.SPEC['receiving_conversion'],
                                            'receiving_yards', run_id),
            'receiving_td': PR.summarise(td.value['td'][k],
                                         LY.SPEC['td_layer'],
                                         'receiving_td', run_id),
        }
        if q['position'] in CARRY_POS:
            r = rb_index[pid]
            mets['carries'] = PR.summarise(C[r], LY.SPEC['targets_carries'],
                                           'carries', run_id)
            mets['rushing_td'] = PR.summarise(rtd.value['rush_td'][r],
                                              LY.SPEC['rushing_td'],
                                              'rushing_td', run_id)
            mets['rushing_yards'] = PR.summarise(
                ry.value['rushing_yards'][r], LY.SPEC['rushing_conversion'],
                'rushing_yards', run_id)
        records.append(PR.record(pid, q['position'], game_id, run_id, mets))
    records.extend(qb_records)
    g['n_records'] = len(records)
    g['n_qb_records'] = len(qb_records)
    v = PR.validate(records)
    g['player_contract'] = f'{v.state.value}[{v.code}]'
    g['player_contract_evidence'] = {k: x for k, x in v.evidence.items()
                                     if k != 'value'}
    pub = LY.assert_publishable(ap, pa, tc, car, cv, td, rtd, ry)
    g['publication_gate'] = f'{pub.state.value}[{pub.code}]'

    # ---- R4: EVERY DECLARED COUNT IS A COUNT, ON THE VALUES THAT SEAL ----
    #
    # Checked HERE, on the arrays this function returns, and after the last
    # write to them. That placement is the whole lesson of the C3 credit gate
    # forty lines up: `run_forecast` stamped QB_DRAW_ACCOUNTING_HOLDS on 101
    # artifacts because it checked an intermediate value that was later
    # overwritten. A support check on a matrix that is not the sealed matrix
    # is the same defect in a different metric.
    #
    # It ASSERTS. It does not round anything into shape: a count that is not a
    # count is a defect in whatever generated it, and repairing it here would
    # move the evidence away from the generator.
    _count_mats = {
        'receiving/targets': T,
        'receiving/receptions': cv.value['receptions'],
        'receiving/receiving_td': td.value['td'],
        'rushing/carries': C,
        'rushing/rushing_td': rtd.value['rush_td'],
    }
    if qb is not None:
        for _f, _k in (('att', 'qb/att'), ('cmp', 'qb/cmp'), ('db', 'qb/db'),
                       ('int', 'qb/int'), ('ptd', 'qb/ptd'),
                       ('rtd', 'qb/rtd'), ('rush_opp', 'qb/rush_opp'),
                       ('sacks', 'qb/sacks'), ('scr', 'qb/scr')):
            if _f in qb['draws']:
                _count_mats[_k] = np.asarray(qb['draws'][_f], float)
    _cc = SCT.assert_counts_are_counts(_count_mats)
    _lay('counts_are_counts', _cc)
    if _cc.state is not State.PASS:
        g['halted_at'] = 'counts_are_counts'
        g['halt_reason'] = _cc.detail[:300]
        return g, None

    # ---- P8: EVERY DECLARED EVENT INSIDE ITS OWN OPPORTUNITY -------------
    #
    # The same arrays, the same placement, and the reason is P8's: the cause
    # was closed and the SYMPTOM was never fenced. 442 cells across the sealed
    # corpus carry `rushing_td > carries` -- 415 of them a whole touchdown on
    # a fractional carry, 27 of them two -- and they reached sealed artifacts
    # with no check pointed at them. The integrality gate above catches the
    # fractional carry BY ACCIDENT and says nothing about the impossible
    # touchdown, so a second route to an over-drawn event would still arrive
    # unannounced.
    #
    # Five declared pairs, each naming why the bound holds, and `_count_mats`
    # already holds every array all five need. It ASSERTS: a rounding of the
    # opportunity would take 442 impossible cells to zero without removing one
    # fractional carry from one board, and `assert_events_within_opportunity`
    # refuses `round_opportunity=` by name so that shortcut cannot be taken
    # through this call site either.
    _ev = SCT.assert_events_within_opportunity(_count_mats)
    _lay('events_within_opportunity', _ev)
    if _ev.state is not State.PASS:
        g['halted_at'] = 'events_within_opportunity'
        g['halt_reason'] = _ev.detail[:300]
        return g, None

    # ---- R4: THE PASSING STAT CONTRACT, ON THE SAME SEALED VALUES --------
    #
    # `db == att + sacks + scr` is the identity that separates the board`s
    # attempt definition from nflverse `pass_attempt`, which includes every
    # sack and every spike. `qb_v1.identity_check` already owns it; this
    # re-states it through the VERSIONED contract so the artifact carries the
    # contract version beside the number, and so the identity is checked once
    # more on the values that actually seal.
    if qb is not None and all(f in qb['draws'] for f in
                              ('db', 'att', 'sacks', 'scr')):
        _sc = SCT.assert_dropback_identity(
            np.asarray(qb['draws']['db'], float),
            np.asarray(qb['draws']['att'], float),
            np.asarray(qb['draws']['sacks'], float),
            np.asarray(qb['draws']['scr'], float))
        _lay('stat_contract', _sc)
        if _sc.state is not State.PASS:
            g['halted_at'] = 'stat_contract'
            g['halt_reason'] = _sc.detail[:300]
            return g, None
        g['stat_contract'] = {
            'version': SCT.CONTRACT_VERSION,
            'dropback_identity': _sc.evidence['identity'],
            'max_abs_deviation': _sc.evidence['max_abs_deviation'],
            'cells': _sc.evidence['n_cells'],
            'att_is': SCT.TERMS['pass_attempt']['predicate'],
            'att_raw_is_not_att': SCT.IDENTITIES['att_raw_is_not_att'],
            'false_friends': sorted(SCT.FALSE_FRIENDS)}
    else:
        _lay('stat_contract', Outcome.not_applicable(
            'STAT_CONTRACT_NO_QB_DRAWS',
            'no quarterback draw set reached this engine, so the dropback '
            'identity has no cells to be checked over. Recorded as not '
            'applicable, never as satisfied.'))
    g['test_only'] = bool(test_only or ap.evidence.get('test_only'))
    # The IDENTITY of every draw row travels with the draws. A covariance
    # diagnostic needs to know which player and which team a row is, and
    # reconstructing that from a parallel list is how a mismatch happens.
    return g, {'records': records, 'draws': {
        'targets': T, 'carries': C, 'receptions': cv.value['receptions'],
        'receiving_yards': cv.value['receiving_yards'],
        'receiving_td': td.value['td'], 'rush_td': rtd.value['rush_td'],
        'rushing_yards': ry.value['rushing_yards']},
        # R4. A1's WHOLE PARTITION, ROW AXIS = TEAM, so a sealed board can
        # walk the rush ledger without re-running the allocator. `None` when
        # the caller supplied no category matrix, which is a different thing
        # from a partition of zero and is why this is not an empty dict.
        'rush_category': rush_category_draws,
        'rush_category_other': ({t: carry_other_counts[k]
                                 for k, t in enumerate(ateams)}
                                if rush_category_draws else None),
        'rush_ownership': g.get('rush_ownership'),
        # R14. THE PASS-EVENT PARTITION, ROW AXIS = TEAM. `targeted`,
        # `untargeted` and `other` are sealed by no board in this repository,
        # so the exact target identity is checkable today only in its weak
        # form. Carrying them here is what lets `run_forecast` seal them and
        # publish the level the partition consumed. `None` on any path that
        # did not compose a pass event -- an absent composition, never a
        # partition of zero.
        'pass_event': pass_event,
        'accounting': (rec_acc, rush_acc),
        'index': {'recv_ids': ids, 'recv_pos': pos,
                  'recv_team': [q['team'] for q in recv],
                  'rb_ids': rb_ids, 'rb_team': [q['team'] for q in rb],
                  # The teams these ROWS belong to, which is the ALLOCATION
                  # frame and equals the game's two clubs on every run where
                  # both are READY. The game's own clubs are `g['teams']` and
                  # the scope, when one was applied, is
                  # `g['appearance_team_scope']`; nothing additive is put here
                  # so that a both-teams-READY payload stays byte-identical to
                  # what it was before this repair.
                  'teams': list(ateams)},
        # The ALLOCATION LAYER's own outputs, so a study can re-run the
        # conversion chain on a different opportunity budget without
        # reimplementing the layers that produced the competition. Additive:
        # nothing downstream reads these and B0 is unchanged by their presence.
        'allocation': {'share': S, 'other': other, 'starts': starts,
                       'counts': counts, 'tc': tc,
                       'team_target_volume': tgt_vol},
        # The level the GAME used, not the level D1 drew: with SC1 live they
        # are different vectors and storing the unused one would make every
        # downstream dependence diagnostic read the wrong carry index.
        'team_draws': {t: {k: (_team_carries(t) if k == 'team_carries'
                               else np.asarray(tv.value[(k, t)], float))
                           for k in TV.METRICS} for t in teams},
        'qb': ({'ids': [qb['rows'][i]['gsis_id']
                        for t in teams for i in qb['index_by_team'].get(t, [])],
                'team': [t for t in teams
                         for i in qb['index_by_team'].get(t, [])],
                'draws': {f: np.stack([np.asarray(qb['draws'][f][i], float)
                                       for t in teams
                                       for i in qb['index_by_team'].get(t, [])])
                          for f in QBV1.FIELDS}}
               if qb is not None else None)}
