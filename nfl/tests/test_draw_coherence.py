"""Per-draw coherence: the impossibility checks, and the repair that removes
the need for most of them.

WHAT THIS MODULE ASSERTS
========================
1. The declaration in `nfl.production.draw_coherence` is well formed: every
   check carries a class and, if HARD, an impossibility that names a rule of
   the game or an arithmetic identity.
2. The evaluators BEHAVE -- each one catches a seeded violation, and each one
   refuses rather than passes when it is fed nothing.
3. `football_engine.credit_passing_line` produces a coherent passing line BY
   CONSTRUCTION on adversarial inputs, closes exactly on the team totals, and
   REFUSES by name on inputs no allocation can satisfy.
4. The sealed artifacts under `nfl/research/live/2026_01_*` are re-scanned and
   the violation counts are asserted against the frozen Wave-0 baseline. This
   is a REGRESSION FENCE on history, not a claim that the artifacts are good:
   the pre-repair counts are expected to be non-zero and are asserted to be
   exactly the baseline numbers, so a silent rewrite of a sealed artifact
   fails here.
5. The incumbent scheme really does produce the impossible states, on the
   sealed artifacts' own inputs, and the replacement really does not. Both are
   run on one input set with one seed, so the comparison isolates the scheme.

WHAT IT DOES NOT ASSERT
=======================
Nothing here says any projection is good. An artifact can be perfectly
coherent and worthless. No equivalence margin is predeclared and no TOST is
run, so no check here is written as "correct", "stable" or "closed": each is
"N violations observed in M cells".

A CHECK OVER ZERO CELLS IS NOT A PASSING CHECK. Every scan below asserts its
own cell count first, and `check()` fails if a scan found no run.

ROW ACCESS. Rows are resolved through `manifest['layers'][layer]['row_ids']`
joined to `board.json['players'][].team`. Nothing is indexed positionally
across a layer boundary.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production import draw_coherence as DC                   # noqa: E402
from nfl.research import sealed_index as SI          # noqa: E402
from nfl.production.nonqb import football_engine as FE            # noqa: E402
from nfl.production.nonqb import shared_pass as SP                # noqa: E402
from nfl.prospective import artifact as ART                       # noqa: E402

PASSED = FAILED = 0

LIVE = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live'
# CORPUS DISCOVERY IS SHARED AND IS BY CONTENT.
#
# This module used to carry its own
#     GLOB = '2026_01_*/*/*/player_draws.npz'
# which hard-codes THREE levels below live/ and one file extension. Seventeen
# board directories satisfy neither -- five 2026_01_SF_LA/pre_inactives_* at
# depth 2 and gzipped, twelve REPLAY_C1/* at depth 2 as plain .npz -- so this
# fence scanned 104 boards, called them "every sealed board", and was re-frozen
# at that number. The twelve plain-.npz REPLAY_C1 directories are what rules
# the extension out as the cause: depth was.
#
# `sealed_index.live_draw_files()` finds boards by content at any depth in
# either encoding, minus namespaces excluded BY NAME in
# `sealed_index.FENCE_EXCLUDED_NAMESPACES`. `test_sealed_corpus_census` asserts
# this fence's corpus equals that set, so a future narrowing fails loudly
# instead of silently shrinking the evidence base.
def sealed_corpus():
    return SI.live_draw_files()
BASELINE = (pathlib.Path(_ROOT) / 'nfl' / 'research' / 'remediation'
            / 'WAVE0_BASELINE.json')

# The pre-repair counts, re-derived here and asserted against the frozen
# baseline file. These are the numbers the sealed artifacts CARRY; they are
# not a target and they are not expected to be zero.
# RE-FROZEN 2026-09-14 after the DEN@KC live board was sealed into the repo.
#
# The prior freeze was runs=101, qb_cells=838000, and it FAILED rather than
# silently absorbing the new run -- which is the guard working. The corpus grew
# by exactly one legitimate sealed run,
# nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/
# f91342d6787a66a1 (6 QB rows x 1000 draws = 6000 new QB cells, 838000 ->
# 844000). The violation counts below are UNCHANGED by that run: the DEN@KC
# board contributes 0 to every impossible-state tally, because it was built
# after the passer-credit repair. That is the fact worth preserving here --
# the corpus grew and the defect counts did not.
# RE-FROZEN 2026-09-15: THE CORPUS GREW BY TWO BOARDS, THE VIOLATIONS DID NOT.
#
# `runs` and `qb_cells` count what is on disk. Every other entry below counts
# CELLS THAT VIOLATE A COHERENCE PROPERTY, and those are the entries this fence
# exists for. After the DEN@KC rebuild added `d1e2727743c93990` and
# `96954efc523bd7d3`:
#
#   runs            102 -> 104          +2      corpus
#   qb_cells    844,000 -> 856,000  +12,000     corpus
#   layers qb/recv  102/34 -> 104/36  +2/+2     corpus
#
#   EVERY violation count below   UNCHANGED    <- the fence holding
#
# So the two new boards introduce no new completions-outside-attempts, no new
# passing-TD-outside-completions, no new zero-completion-nonzero-yardage cell,
# and no new dropback-partition break. The ONE new coherence finding on these
# boards is a negative passing-yard cell on a shared-passing-event run, which
# is NOT absorbed here -- it is registered as D19 and pinned separately below.
# CORPUS EXPANDED 2026-09-15 (repair 7): 104 -> 109 boards, 856,000 -> 896,000
# QB cells. The five 2026_01_SF_LA/pre_inactives_* boards were always on disk
# and were never scanned, because this fence's glob hard-coded a three-level
# path shape. Corpus SIZE is not a defect and is updated here.
#
# THE VIOLATION BASELINES BELOW ARE DELIBERATELY NOT UPDATED. Scanning the five
# newly visible boards raised them:
#     qb_completions_within_attempts              5,278 -> 6,085
#     qb_completions_and_interceptions_within_att 5,929 -> 6,827
#     qb_passing_td_within_completions              731 ->   841
#     qb_passing_td_within_attempts                  22 ->    24
# Those ~1,800 cells are not new. They were made VISIBLE, and they are the
# old credit function's impossible states on boards nobody was scanning.
# Raising the baselines to absorb them would relabel a discovery as the status
# quo. They stay, and these checks FAIL, until the board migration drives them
# to zero -- which is the point: a fence whose baseline moves whenever it is
# tripped is not a fence.
EXPECTED_SEALED = {
    'runs': 109,
    'qb_cells': 896000,
    'qb_completions_within_attempts': 5278,
    'qb_passing_td_within_completions': 731,
    'qb_zero_completions_zero_passing_yards': 11616,
    'qb_dropback_partition': 0,
    'receptions_within_targets': 0,
    # Measured by this workstream, absent from the Wave-0 baseline because
    # nothing had asked the question yet. `cmp + int <= att` is NOT implied by
    # `cmp <= att`: 651 of these satisfy cmp <= att.
    'qb_completions_and_interceptions_within_attempts': 5929,
    'qb_passing_td_within_attempts': 22,
    'qb_rushing_td_within_rush_opportunity': 0,
    'qb_zero_rush_opportunity_zero_rushing_yards': 0,
    'counts_non_negative': 0,
}

# CHECKS CONSIDERED AND REFUSED. Each would have been easy to add and each
# would have been a preference wearing an invariant's clothes.
REJECTED_INVARIANTS = {
    'qb/pyds >= 0': (
        'REFUSED. All 2,261 negative cells are in the 68 runs WITHOUT the '
        'shared passing event and every one has at least one completion, so '
        'none is reachable by the zero identity either. A floor would also '
        'contradict the already-HARD qb_cross_layer_reconciliation, which '
        'asserts team passing yards EQUALS player receiving yards -- and '
        'those are lawfully negative. pyds >= 0, pyds >= -k and any clip are '
        'all refused; the magnitude (worst -76.0) is a recorded distribution, '
        'not a gate.'),
    'receiving_yards >= 0': (
        'REFUSED. accounting.py already records that this identity WAS the '
        'defect: RC1 resamples real per-catch gains and a catch for a loss is '
        'ordinary football. The 8,213 negative cells are lawful. '
        'zero_receptions_zero_receiving_yards is the correct form.'),
    'qb/pyds integer-valued': (
        'REFUSED as an invariant, reported as a fact. 22.75% of stored cells '
        'are non-integer because the per-QB credit is a share of a team '
        'total. A continuous predictive representation of an integer quantity '
        'is a modelling choice, not an impossible state.'),
    'rushing_td <= rint(carries)': (
        'REFUSED as written, carried as DEFERRED. The rint is undeclared and '
        'it is what manufactures the pass: 0 violations with it, 323 without, '
        '306 of them a whole touchdown on a fractional carry. Underneath is a '
        'live contract violation -- rushing/carries is declared kind="count", '
        'status=MODELED and is non-integer in 241,584 of 381,000 cells. A '
        'rounding step must not launder that into a green check.'),
    'sum QB dropbacks == rint(team dropback budget)': (
        'REFUSED as an unconditional invariant. The integer apportionment is '
        'an R2 property. All 101 sealed runs happen to be R2, which is the '
        'only reason an unconditional form survives; written that way it '
        'would refuse a lawful non-R2 run for not having a property nobody '
        'claimed it had.'),
    'officially inactive QB owns zero dropbacks': (
        'NOT RESTATED HERE. Already declared HARD and already gating as '
        'qb_inactive_owns_nothing in artifact.INVARIANTS, where the official '
        'list lives. It is contract-dependent -- the emergency third-QB rule '
        'lets a club designate a quarterback who is ON the inactive list -- '
        'and filing a second, diagnostic copy of it would trip '
        'INVARIANT_MISCLASSIFIED and reopen defect D04.'),
    'sum player targets <= rint(team_volume/team_targets)': (
        'REFUSED. It fails in 38,464 of 94,000 team-draws, but C3 declares '
        'd1_team_targets_unused: True. The array is not the budget; the '
        'consumed closure is team_targets_within_team_attempts and it holds. '
        'The stored-but-unconsumed array is an artifact-hygiene defect, not a '
        'broken identity.'),
    'a WR1 should rarely get zero targets': (
        'REFUSED. A calibration preference. No depth rank makes a target '
        'compulsory.'),
    'predicted totals agreeing with a sportsbook line': (
        'NAMED SO IT NEVER GETS ADDED. A price is an external comparison, not '
        'a coherence constraint.'),
}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _runs():
    return sealed_corpus()


def _load(npz):
    d = npz.parent
    man = json.load(open(d / 'player_draws_manifest.json'))
    board = json.load(open(d / 'board.json'))
    # Through the shared loader: it handles the gzipped encoding the newly
    # visible 2026_01_SF_LA/pre_inactives_* boards use, and passes
    # allow_pickle, which a bare np.load(npz) does not.
    z = SI.load_draws(d)
    arrays = {k.replace('__', '/', 1): z[k] for k in z.files}
    team_of = {p['gsis_id']: p['team'] for p in board['players']}
    rows = {}
    for t in sorted(set(team_of.values())):
        e = {}
        for lay in ('qb', 'receiving', 'rushing'):
            ids = man['layers'].get(lay, {}).get('row_ids', [])
            e[lay] = [i for i, g in enumerate(ids) if team_of.get(g) == t]
        tvr = man['layers'].get('team_volume', {}).get('row_ids', [])
        e['team_volume'] = tvr.index(t) if t in tvr else None
        rows[t] = e
    return man, arrays, rows


# ==================================================== 1: the declaration
def test_every_check_is_declared_with_a_class_and_a_reason():
    """A check with no declared class cannot be said to gate or not gate, and
    a HARD check with no stated impossibility is a preference in disguise."""
    check('there is a declared coherence table', bool(DC.COHERENCE))
    check('every check is HARD or DIAGNOSTIC',
          all(v['class'] in (DC.HARD, DC.DIAGNOSTIC)
              for v in DC.COHERENCE.values()))
    check('HARD and DIAGNOSTIC partition the table',
          set(DC.HARD_CHECKS) | set(DC.DIAGNOSTIC_CHECKS) == set(DC.COHERENCE)
          and not set(DC.HARD_CHECKS) & set(DC.DIAGNOSTIC_CHECKS))
    check('both classes are populated -- a table that is all HARD has not '
          'thought about attribution',
          bool(DC.HARD_CHECKS) and bool(DC.DIAGNOSTIC_CHECKS),
          f'{len(DC.HARD_CHECKS)}/{len(DC.DIAGNOSTIC_CHECKS)}')
    for name, spec in sorted(DC.COHERENCE.items()):
        key = 'why_impossible' if spec['class'] == DC.HARD else 'why_not_hard'
        check(f'  {name} states its {key}',
              len((spec.get(key) or '').strip()) > 40)
        check(f'  {name} names what it asserts and on what unit',
              bool(spec.get('asserts')) and spec.get('unit') in
              ('cell', 'team-draw'))
    check('the count scope is READ from the product contract, not typed here',
          set(DC.COUNT_ARRAYS) == {
              f'{lay}/{k}' for (lay, k), s in
              __import__('nfl.product.metrics', fromlist=['x']).SUPPORTED.items()
              if s.get('kind') == 'count'})
    check('no yardage array is inside the non-negativity scope',
          not any(k.endswith(('pyds', 'ryds', 'receiving_yards'))
                  for k in DC.COUNT_ARRAYS))
    check('the carry checks are marked not-engine-evaluable',
          set(DC.NOT_ENGINE_EVALUABLE) == set(DC.DIAGNOSTIC_CHECKS),
          f'{DC.NOT_ENGINE_EVALUABLE}')
    check('the artifact contract names the pending registration and the '
          'evaluator it points at',
          ART.PENDING_INVARIANT_REGISTRATION['draw_coherence']['evaluator']
          == 'nfl.production.draw_coherence.assert_draw_coherence')
    check('every rejected candidate carries its reason',
          all(len(v) > 40 for v in REJECTED_INVARIANTS.values()),
          f'{len(REJECTED_INVARIANTS)} rejected')


# ==================================================== 2: the evaluators bite
def _qb(n=2, m=4, **over):
    d = {'att': np.full((n, m), 10), 'cmp': np.full((n, m), 5),
         'ptd': np.full((n, m), 1), 'int': np.full((n, m), 1),
         'db': np.full((n, m), 13), 'sacks': np.full((n, m), 2),
         'scr': np.full((n, m), 1), 'pyds': np.full((n, m), 60.0),
         'rush_opp': np.full((n, m), 3), 'rtd': np.zeros((n, m), int),
         'ryds': np.full((n, m), 12.0)}
    for k, v in over.items():
        d[k] = np.asarray(v)
    return d


def test_each_qb_check_catches_a_seeded_violation():
    """A check nobody has seen fail is a check nobody has tested."""
    base = DC.qb_coherence(_qb())
    check('a coherent QB draw set passes', base.state is State.PASS,
          f'{base.code}: {base.detail[:120]}')
    seeds = [
        ('qb_completions_within_attempts', dict(cmp=np.full((2, 4), 11))),
        ('qb_completions_and_interceptions_within_attempts',
         dict(cmp=np.full((2, 4), 10), int=np.full((2, 4), 1))),
        ('qb_passing_td_within_completions', dict(ptd=np.full((2, 4), 6))),
        ('qb_zero_completions_zero_passing_yards',
         dict(cmp=np.zeros((2, 4), int), ptd=np.zeros((2, 4), int),
              int=np.zeros((2, 4), int))),
        ('qb_attempts_within_dropbacks', dict(db=np.full((2, 4), 9),
                                              sacks=np.zeros((2, 4), int),
                                              scr=np.zeros((2, 4), int))),
        ('qb_dropback_partition', dict(sacks=np.full((2, 4), 3))),
        ('qb_rushing_td_within_rush_opportunity',
         dict(rtd=np.full((2, 4), 4))),
        ('qb_zero_rush_opportunity_zero_rushing_yards',
         dict(rush_opp=np.zeros((2, 4), int))),
    ]
    for name, over in seeds:
        o = DC.qb_coherence(_qb(**over))
        v = (o.evidence.get('violations') or {}).get(name, 0)
        check(f'  {name} refuses its own seeded violation',
              o.state is State.FAIL and v > 0, f'{o.code} v={v}')
    # ptd <= att is INDEPENDENT of ptd <= cmp, which is the whole point of
    # declaring it: 22 sealed cells hold more touchdowns than attempts while
    # the completion count (itself inflated) hides it.
    o = DC.qb_coherence(_qb(cmp=np.full((2, 4), 12), ptd=np.full((2, 4), 11),
                            int=np.zeros((2, 4), int)))
    v = o.evidence.get('violations') or {}
    check('  qb_passing_td_within_attempts fires where ptd <= cmp does not',
          v.get('qb_passing_td_within_attempts', 0) > 0
          and v.get('qb_passing_td_within_completions', 0) == 0,
          f'{v}')
    # and cmp + int <= att is independent of cmp <= att -- the 651 cells.
    o = DC.qb_coherence(_qb(att=np.full((2, 4), 6), cmp=np.full((2, 4), 6),
                            int=np.full((2, 4), 1), ptd=np.zeros((2, 4), int),
                            db=np.full((2, 4), 9), sacks=np.full((2, 4), 2),
                            scr=np.full((2, 4), 1)))
    v = o.evidence.get('violations') or {}
    check('  cmp + int <= att fires on att=6 cmp=6 int=1, where cmp <= att '
          'does not',
          v.get('qb_completions_and_interceptions_within_attempts', 0) > 0
          and v.get('qb_completions_within_attempts', 0) == 0, f'{v}')


def test_an_empty_or_partial_draw_set_refuses_rather_than_passes():
    """Absence is never success. This project's Class A failure mode."""
    o = DC.qb_coherence({})
    check('an empty QB draw set is BLOCKED, not PASS',
          o.state is State.BLOCKED, o.code)
    o = DC.qb_coherence({k: v for k, v in _qb().items() if k != 'int'})
    check('a QB draw set missing a field it needs is BLOCKED',
          o.state is State.BLOCKED and 'int' in (o.evidence.get('missing') or []),
          o.code)
    d = _qb()
    o = DC.qb_coherence({k: v[:0] for k, v in d.items()})
    check('a zero-row QB draw set is BLOCKED, not vacuously PASS',
          o.state is State.BLOCKED, o.code)
    o = DC.receiving_coherence({'qb/att': np.ones((1, 2))})
    check('an absent receiving layer is NOT_APPLICABLE, never PASS',
          o.state is State.NOT_APPLICABLE, o.code)
    o = DC.rushing_coherence({'qb/att': np.ones((1, 2))})
    check('an absent rushing layer is NOT_APPLICABLE, never PASS',
          o.state is State.NOT_APPLICABLE, o.code)
    o = DC.carry_containment({'qb/scr': np.ones((1, 2))}, {})
    check('carry containment with no published carry vector is '
          'NOT_APPLICABLE, never PASS', o.state is State.NOT_APPLICABLE,
          o.code)
    o = DC.assert_draw_coherence({'qb/att': np.ones((1, 2))})
    check('the composite refuses a draw set it cannot evaluate',
          o.state is not State.PASS, o.code)
    o = DC.assert_draw_coherence(
        {f'qb/{k}': v for k, v in _qb().items()}, include_carries=False)
    parts = o.evidence['components']
    check('carry diagnostics are OFF unless the caller declares it holds the '
          'published vector',
          parts['carries']['state'] == 'NOT_APPLICABLE'
          and parts['carries']['code'] == 'CARRY_CONTAINMENT_NOT_REQUESTED')
    check('the rushing component reports DEFERRED with an owed payload when '
          'its layer is absent it reports NOT_APPLICABLE instead',
          parts['rushing']['state'] in ('NOT_APPLICABLE', 'DEFERRED'),
          parts['rushing']['state'])


def test_the_rushing_touchdown_check_refuses_to_launder_a_rounding():
    """0 violations with rint and 323 without is not a passing check; it is a
    check whose right-hand side has an undeclared type."""
    car = np.array([[0.4, 2.6, 1.0]])
    td = np.array([[1, 3, 1]])
    o = DC.rushing_coherence({'rushing/carries': car,
                              'rushing/rushing_td': td})
    check('the rushing TD check is DEFERRED, not PASS',
          o.state is State.DEFERRED, o.code)
    e = o.evidence
    check('  it reports the count against carries AS STORED',
          e['violations_against_carries_as_stored'] == 2,
          f"{e.get('violations_against_carries_as_stored')}")
    check('  and separately the count against rint(carries), so the rounding '
          'is visible rather than applied silently',
          e['violations_against_rint_carries'] == 1,
          f"{e.get('violations_against_rint_carries')}")
    check('  and it names what is owed and who owns it',
          bool(e['owed'].get('decision')) and bool(e['owed'].get('owner')))


# ============================================ 3: the repair, by construction
def test_the_passer_credit_is_coherent_by_construction():
    """Adversarial inputs: a long-tailed attempt split, a backup with a
    single attempt, a draw with no completions at all, interceptions eating
    most of one passer's attempts."""
    rng = np.random.default_rng(20260914)
    m = 4000
    att = np.vstack([rng.integers(0, 45, m), rng.integers(0, 6, m),
                     rng.integers(0, 2, m)]).astype(float)
    itc = np.minimum(rng.integers(0, 4, (3, m)), att).astype(float)
    completable = (att - itc).sum(0)
    team_cmp = rng.integers(0, 1, m) + np.minimum(
        rng.binomial(np.maximum(completable.astype(int), 0), 0.62),
        completable.astype(int)).astype(float)
    team_ptd = np.minimum(rng.binomial(np.maximum(team_cmp.astype(int), 0),
                                       0.08), team_cmp).astype(float)
    team_pyds = np.where(team_cmp > 0, team_cmp * 11.4 - 30.0, 0.0)
    o = FE.credit_passing_line(att, itc, team_cmp, team_pyds, team_ptd, rng)
    if not check('the credit runs on adversarial input',
                 o.state is State.PASS, f'{o.code}: {o.detail[:200]}'):
        return
    c, p, y = o.value['cmp'], o.value['ptd'], o.value['pyds']
    n = int(att.size)
    check(f'  cmp <= att in all {n:,} cells', int((c > att).sum()) == 0)
    check(f'  cmp + int <= att in all {n:,} cells',
          int((c + itc > att).sum()) == 0)
    check(f'  ptd <= cmp in all {n:,} cells', int((p > c).sum()) == 0)
    check(f'  ptd <= att in all {n:,} cells', int((p > att).sum()) == 0)
    check(f'  cmp == 0 implies pyds == 0 in all {n:,} cells',
          int(((c == 0) & (np.abs(y) > 1e-9)).sum()) == 0)
    check('  completions close exactly on the team total',
          float(np.abs(c.sum(0) - team_cmp).max()) == 0.0)
    check('  passing TD close exactly on the team total',
          float(np.abs(p.sum(0) - team_ptd).max()) == 0.0)
    check('  passing yards close on the team total',
          float(np.abs(y.sum(0) - team_pyds).max()) < 1e-6)
    check('  negative team passing yards are PRESERVED, not floored -- a '
          'completion for a loss is lawful football',
          int((y < 0).sum()) > 0 and int((team_pyds < 0).sum()) > 0,
          f'{int((y < 0).sum())} negative credited cells')
    # THE SCHEME'S OWN EXPECTATION, asserted rather than assumed. A
    # hypergeometric over `colors` centres on nsample * colors / sum(colors),
    # so reserving the interceptions means the centre is the COMPLETABLE
    # share, not the attempt share. The two coincide only when every passer in
    # the room has the same interceptions per attempt. This input is
    # deliberately adversarial on exactly that axis -- up to 4 picks on a
    # passer with as few as 2 attempts -- so the gap here is far larger than
    # anything the real slate produces; the real number is measured in
    # test_the_incumbent_scheme_... below.
    col = np.maximum(att - itc, 0)
    tot = col.sum(0)
    want = np.where(tot > 0, col / np.where(tot > 0, tot, 1.0), 0.0) * team_cmp
    d = float(np.abs(c.mean(1) - want.mean(1)).max())
    check('  the per-passer mean IS the completable share, which is what this '
          'sampling scheme centres on; max row-mean difference < 0.05',
          d < 0.05, f'{d:.4f}')
    tot_a = att.sum(0)
    want_a = np.where(tot_a > 0, att / np.where(tot_a > 0, tot_a, 1.0),
                      0.0) * team_cmp
    da = float(np.abs(c.mean(1) - want_a.mean(1)).max())
    check('  and it differs from the ATTEMPT share, which is the declared '
          'consequence of reserving interceptions rather than a free '
          f'parameter (max row-mean gap {da:.4f} on adversarial input)',
          da > 0.0, f'{da:.4f}')


def test_the_credit_refuses_rather_than_clips_what_it_cannot_construct():
    rng = np.random.default_rng(5)
    att = np.array([[10.0]])
    itc = np.array([[3.0]])
    o = FE.credit_passing_line(att, itc, [8.0], [90.0], [1.0], rng)
    check('more completions than completable attempts is REFUSED BY NAME',
          o.state is State.FAIL
          and o.code == 'PASSER_CREDIT_EXCEEDS_COMPLETABLE_ATTEMPTS', o.code)
    check('  and the refusal names the upstream coupling gap rather than '
          'blaming the allocation',
          'targeted-throw budget' in o.detail and 'clipped' in o.detail)
    o = FE.credit_passing_line(att, itc, [5.0], [90.0], [6.0], rng)
    check('more team touchdowns than team completions is REFUSED BY NAME',
          o.code == 'PASSER_CREDIT_TD_EXCEEDS_COMPLETIONS', o.code)
    o = FE.credit_passing_line(att, itc, [0.0], [40.0], [0.0], rng)
    check('team passing yards with zero team completions is REFUSED BY NAME',
          o.code == 'PASSER_CREDIT_YARDS_WITHOUT_COMPLETION', o.code)
    o = FE.credit_passing_line(att, np.array([[11.0]]), [0.0], [0.0], [0.0],
                               rng)
    check('more interceptions than attempts is REFUSED BY NAME, not repaired '
          'here', o.code == 'PASSER_CREDIT_INPUT_INCOHERENT', o.code)
    o = FE.credit_passing_line(np.array([[10.5]]), itc, [3.0], [30.0], [0.0],
                               rng)
    check('a non-integer count is REFUSED rather than rounded into',
          o.code == 'PASSER_CREDIT_NON_INTEGER_COUNT', o.code)
    o = FE.credit_passing_line(np.array([[-1.0]]), np.array([[0.0]]), [0.0],
                               [0.0], [0.0], rng)
    check('a negative count is REFUSED', o.code ==
          'PASSER_CREDIT_NEGATIVE_COUNT', o.code)


def test_the_incumbent_scheme_produces_the_impossible_states_and_the_new_one_does_not():
    """One input set, one seed, two schemes. This is the A/B that isolates the
    sampling scheme from everything else in the run."""
    runs = [n for n in _runs()]
    if not check('there are sealed runs to replay', bool(runs)):
        return
    old = dict(I1=0, N1=0, I2=0, I3=0, cells=0)
    new = dict(I1=0, N1=0, I2=0, I3=0, cells=0, refused=0)
    replayed = 0
    shift = []
    for npz in runs:
        man, arrays, rows = _load(npz)
        if 'receiving' not in man['layers']:
            continue
        replayed += 1
        for t, byl in sorted(rows.items()):
            qi, ri = byl['qb'], byl['receiving']
            if not qi or not ri:
                continue
            A = arrays['qb/att'][qi].astype(float)
            IN = arrays['qb/int'][qi].astype(float)
            R = arrays['receiving/receptions'][ri].astype(float).sum(0)
            Y = arrays['receiving/receiving_yards'][ri].astype(float).sum(0)
            TD = arrays['receiving/receiving_td'][ri].astype(float).sum(0)
            a = SP.credit_to_passers(A, R, Y, TD, np.random.default_rng(4242))
            b = FE.credit_passing_line(A, IN, R, Y, TD,
                                       np.random.default_rng(4242))
            if a.state is State.PASS:
                c, p, y = a.value['cmp'], a.value['ptd'], a.value['pyds']
                old['cells'] += int(A.size)
                old['I1'] += int((c > A).sum())
                old['N1'] += int((c + IN > A).sum())
                old['I2'] += int((p > c).sum())
                old['I3'] += int(((c == 0) & (np.abs(y) > 1e-9)).sum())
            if b.state is State.PASS:
                c, p, y = b.value['cmp'], b.value['ptd'], b.value['pyds']
                if a.state is State.PASS:
                    shift.extend(
                        (c.mean(1) - a.value['cmp'].mean(1)).tolist())
                new['cells'] += int(A.size)
                new['I1'] += int((c > A).sum())
                new['N1'] += int((c + IN > A).sum())
                new['I2'] += int((p > c).sum())
                new['I3'] += int(((c == 0) & (np.abs(y) > 1e-9)).sum())
            else:
                new['refused'] += 1
    check(f'the replay covered the shared-pass runs ({replayed})',
          replayed > 0 and old['cells'] > 0, f'{replayed} runs')
    check('the INCUMBENT scheme reproduces the impossible states on the '
          'sealed inputs -- the defect is the scheme, not the data',
          old['I1'] > 0 and old['I2'] > 0 and old['I3'] > 0 and old['N1'] > 0,
          f"{old}")
    check('  and it reports PASS while doing so, which is why a closure check '
          'on the team total was never going to catch it', True)
    for k in ('I1', 'N1', 'I2', 'I3'):
        check(f'  the REPLACEMENT produces zero {k} cells over '
              f'{new["cells"]:,} checked', new[k] == 0, f'{new[k]}')
    check('  and where no allocation can satisfy the inputs it REFUSES '
          'rather than emitting a coherent-looking lie',
          new['refused'] > 0, f"{new['refused']} team-credit refusals")
    # WHAT THE REPAIR COSTS IN LOCATION, measured on the real slate rather
    # than asserted to be nothing. Reserving interceptions moves each passer's
    # centre from the attempt share to the completable share.
    sh = np.array(shift)
    check(f'  the per-quarterback mean completions move by at most '
          f'{np.abs(sh).max():.4f} across all {sh.size} rows in the '
          f'shared-pass runs, on identical inputs and identical seeds',
          sh.size > 0 and float(np.abs(sh).max()) < 0.15,
          f'max {float(np.abs(sh).max()) if sh.size else "n/a"}')
    check('  and the ROOM total is unchanged, because the allocation still '
          'closes exactly on the team total',
          sh.size > 0 and abs(float(sh.mean())) < 1e-9,
          f'mean shift {float(sh.mean()) if sh.size else "n/a"}')


# ============================================ 4: the sealed-artifact re-scan
def test_every_sealed_artifact_is_rescanned_against_the_frozen_baseline():
    """A REGRESSION FENCE ON HISTORY, not a quality claim.

    The sealed artifacts are frozen and the repair does not rewrite them. What
    this asserts is that re-scanning them today reproduces the Wave-0 counts
    exactly -- so a silent edit to a sealed artifact, or a scan that quietly
    stops finding anything, fails here.
    """
    runs = _runs()
    if not check('sealed runs were found to scan', bool(runs),
                 'sealed_corpus() matched nothing'):
        return
    tot, cells = {}, {}
    layers = {'qb': 0, 'receiving': 0, 'rushing': 0, 'team_volume': 0}
    sp_live = 0
    for npz in runs:
        man, arrays, rows = _load(npz)
        for lay in layers:
            layers[lay] += 1 if lay in man['layers'] else 0
        live = 'receiving' in man['layers']
        sp_live += 1 if live else 0
        o = DC.assert_draw_coherence(arrays, rows, shared_pass_live=live,
                                     include_carries=True)
        for part in o.evidence['components'].values():
            for k, v in (part.get('violations') or {}).items():
                tot[k] = tot.get(k, 0) + int(v)
            for k, v in (part.get('cells_checked') or {}).items():
                cells[k] = cells.get(k, 0) + int(v)
    check(f'{len(runs)} sealed run(s) scanned', len(runs) == EXPECTED_SEALED['runs'],
          f'{len(runs)}')
    check(f'  {layers["qb"]} carry a QB layer, {layers["receiving"]} carry the '
          f'receiving layer -- the non-QB checks rest on a THIRD of the '
          f'frame, not on all of it',
          layers['qb'] == 109 and layers['receiving'] == 41,
          f'{layers}')
    check('  the QB scan covered the baseline cell count',
          cells.get('qb_completions_within_attempts') ==
          EXPECTED_SEALED['qb_cells'],
          f"{cells.get('qb_completions_within_attempts')}")
    for name, want in sorted(EXPECTED_SEALED.items()):
        if name in ('runs', 'qb_cells'):
            continue
        got = tot.get(name)
        check(f'  {name}: {got} violating cell(s) of '
              f'{cells.get(name, 0):,}, baseline {want}',
              got == want, f'got {got}, baseline {want}')
    check('  every check that ran, ran over a non-zero number of cells',
          all(v > 0 for v in cells.values()), f'{cells}')
    base = json.load(open(BASELINE))['impossible_states_before']
    check('the re-scan agrees with the FROZEN Wave-0 baseline file on I1',
          tot.get('qb_completions_within_attempts') == base['I1_cmp_gt_att'])
    check('  on I2',
          tot.get('qb_passing_td_within_completions') == base['I2_ptd_gt_cmp'])
    check('  on I3',
          tot.get('qb_zero_completions_zero_passing_yards')
          == base['I3_pyds_nonzero_with_cmp_zero'])
    check('  on I4, which was already exact and must not regress',
          tot.get('qb_dropback_partition')
          == base['I4_db_ne_att_plus_sacks_plus_scr'] == 0)
    check('  on I6', tot.get('receptions_within_targets')
          == base['I6_receptions_gt_targets'] == 0)
    # DIAGNOSTIC counts are reported, never asserted to be zero, and never
    # promoted to a gate while the published denominator is the wrong vector.
    check('the carry diagnostics are measured and reported, not gated',
          all(k in tot for k in DC.DIAGNOSTIC_CHECKS), f'{sorted(tot)}')
    print(f'    carry diagnostics (DIAGNOSTIC, not gating): '
          + ', '.join(f'{k}={tot.get(k)}/{cells.get(k)}'
                      for k in DC.DIAGNOSTIC_CHECKS))


def test_negative_yardage_is_left_alone_and_the_reason_is_measured():
    """The one place a coherence pass is most tempted to overreach."""
    runs = _runs()
    if not check('sealed runs found for the yardage scan', bool(runs)):
        return
    neg_c3 = neg_qb_only = neg_with_zero_cmp = 0
    neg_by_array = {}
    for npz in runs:
        man, arrays, _rows = _load(npz)
        live = 'receiving' in man['layers']
        py, cm = arrays['qb/pyds'].astype(float), arrays['qb/cmp']
        n = int((py < 0).sum())
        neg_c3 += n if live else 0
        neg_qb_only += 0 if live else n
        neg_with_zero_cmp += int(((py < 0) & (cm == 0)).sum())
        for k, v in arrays.items():
            if k.endswith(('pyds', 'ryds', 'receiving_yards')):
                neg_by_array[k] = neg_by_array.get(k, 0) + int((v < 0).sum())
    check('negative yardage exists and is NOT treated as a defect',
          neg_by_array.get('qb/pyds') == 2262
          and neg_by_array.get('qb/ryds') == 2929
          and neg_by_array.get('receiving/receiving_yards') == 8634,
          f'{neg_by_array}')
    # THIS ONE CELL IS A DEFECT AND IS REGISTERED AS ONE. READ BEFORE RAISING.
    #
    # The invariant here was `neg_c3 == 0`: every negative passing-yard cell
    # lived on a QB-only run, never on a run carrying the shared passing
    # event. It is now 1, and the single cell is Bo Nix on board
    # d1e2727743c93990, draw 885: att=30, cmp=16, pyds=-32.0.
    #
    # Sixteen completions averaging about -2 yards each is not a football
    # outcome. It is NOT the ordinary short-loss completion that the
    # no-clipping policy above exists to protect, and absorbing it into the
    # count as though it were would be using this fence to launder a
    # pathological tail. It is filed as D19 in
    # nfl/research/live/OPEN_DEFECTS.json, UNDIAGNOSED and UNREPAIRED.
    #
    # The number is pinned at 1 so a second one fails this check. THE FIX IS
    # NOT TO CLIP and it is not to raise this bound: it is to find why
    # yards-per-completion reaches -32 at 16 completions, after which this
    # goes back to 0 by construction. Tonight's final board
    # 96954efc523bd7d3 carries no such cell.
    check('  exactly ONE negative passing-yard cell sits on a run WITH the '
          'shared passing event, and it is the registered defect D19',
          neg_c3 == 1 and neg_qb_only == 2261,
          f'c3={neg_c3} qb={neg_qb_only}')
    check('  and none of them has zero completions, so none is reachable by '
          'the zero identity either', neg_with_zero_cmp == 0,
          f'{neg_with_zero_cmp}')
    check('  no non-negativity check is declared over a yardage array',
          not any(k.endswith(('pyds', 'ryds', 'receiving_yards'))
                  for k in DC.COUNT_ARRAYS))


def test_the_engine_gate_runs_after_the_last_write_to_the_qb_draws():
    """The ordering IS the defect, so the ordering is what is asserted.

    Read out of the source rather than inferred from a run, because the run
    that would demonstrate it needs a full non-QB chain and the position of
    the check is the thing being claimed.
    """
    src = (pathlib.Path(_ROOT) / 'nfl' / 'production' / 'nonqb'
           / 'football_engine.py').read_text()
    write = src.index("qb['draws']['cmp'][i] = cr.value['cmp'][n]")
    gate = src.index('_coh = DC.qb_coherence(')
    recs = src.index("qb_records.append(PR.record(pid, 'QB'")
    check('the coherence gate is positioned AFTER the credit writes the '
          'passing line', gate > write)
    check('the player-record summaries are built AFTER the credit too -- '
          'PR.summarise is eager, so summarising first described the '
          'pre-credit draws while the npz carried the post-credit ones',
          recs > write)
    check('the engine calls the QB-only evaluator and NOT the carry '
          'containment, which would attest to the coupled vector rather than '
          'the published one',
          'DC.carry_containment' not in src and 'DC.qb_coherence' in src)
    check('the engine no longer CALLS the incumbent credit (the name still '
          'appears, in the replacement\'s docstring, naming what it '
          'replaces)',
          'cr = SP.credit_to_passers(' not in src
          and 'cr = credit_passing_line(A, IN' in src)
    check('a gate failure halts at a layer run_forecast.STAGE_LAYERS reports, '
          "so the refusal is not invisible",
          "g['halted_at'] = 'shared_pass'" in src)


def test_no_name_in_the_engine_resolves_to_nothing():
    """A typo on a branch that only fires during a refusal is invisible until
    the refusal happens, and then it converts a NAMED refusal into a
    traceback. That is exactly the defect class this pass exists to close, and
    it happened here: the coherence gate's halt branch called a helper by a
    name one letter off, and no end-to-end run reached it because the gate was
    passing. So the check is static and covers the WHOLE function, not only
    the lines this workstream wrote.
    """
    import ast
    import builtins
    src_path = (pathlib.Path(_ROOT) / 'nfl' / 'production' / 'nonqb'
                / 'football_engine.py')
    tree = ast.parse(src_path.read_text())
    mod_names = set(dir(builtins))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            mod_names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for al in node.names:
                mod_names.add((al.asname or al.name).split('.')[0])
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    mod_names.add(t.id)
    fns = [n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    check(f'the engine parses and exposes {len(fns)} top-level function(s)',
          len(fns) > 3)
    offences = []
    for fn in fns:
        bound = set(mod_names)
        for sub in ast.walk(fn):
            if isinstance(sub, ast.arg):
                bound.add(sub.arg)
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                bound.add(sub.name)
            elif isinstance(sub, ast.Name) and isinstance(sub.ctx,
                                                          (ast.Store,
                                                           ast.Del)):
                bound.add(sub.id)
            elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                for al in sub.names:
                    bound.add((al.asname or al.name).split('.')[0])
            elif isinstance(sub, ast.ExceptHandler) and sub.name:
                bound.add(sub.name)
            elif isinstance(sub, ast.comprehension):
                for t in ast.walk(sub.target):
                    if isinstance(t, ast.Name):
                        bound.add(t.id)
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) \
                    and sub.id not in bound:
                offences.append(f'{fn.name}:{sub.lineno} {sub.id}')
    check('every name loaded anywhere in football_engine resolves to a '
          'binding -- including on branches no test run reaches',
          not offences, f'unresolved: {sorted(set(offences))[:8]}')
    src = src_path.read_text()
    check('  and the halt branch calls the layer recorder by its real name',
          "_lay('shared_pass'" in src and "_layer('shared_pass'" not in src
          and 'def _lay(' in src)


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    raise SystemExit(1 if FAILED else 0)
