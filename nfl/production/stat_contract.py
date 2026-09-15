"""THE STAT CONTRACT: what a count is, and what a passing event is.

Two subjects, one file, because they are one contract. Both exist because the
same class of defect was paid for twice in this repository.

    1. A COUNT MUST BE A COUNT. `rushing/carries` reaches the sealed artifact
       as float64 and is non-integer in 243,766 of 384,000 cells across the 102
       sealed runs (63.48%), while `nfl/product/metrics.py` declares it
       `kind: 'count'` and `nfl/product/render.py` prints it with `:.0f`. A
       "9.5+" threshold read off that quantity is being read off a continuous
       variable that never takes the value 9 or 10 in most draws. Integerising
       at the END -- rounding a mean, or rounding each cell independently --
       does not fix it: independent per-row rounding destroys the closure the
       allocation was built to satisfy. The count has to be GENERATED as a
       count, inside the draw, by a construction that partitions an integer
       budget. `deal_counts` is that construction.

    2. A PASS ATTEMPT MUST MEAN ONE THING. nflverse `pass_attempt` INCLUDES
       every sack and every spike. The board's `qb/att` is
       `pass_attempt & !sack & !qb_spike`. The gap is 2.4356 per QB1 team-game
       (`nfl/research/refbands/REFERENCE_BANDS.json`), and reading a reference
       band built on one definition against a forecast built on the other moved
       tonight's Bo Nix percentile placement from 39.8 to 51.6 -- 11.8 points
       of nothing but vocabulary. Separately, `panel_p3.dropbacks_as_passer`
       EQUALS `pass_att_as_passer` in all 57,670 rows of
       `nfl/research/inputs/panel_p3.csv.gz`: it is `att_raw` under a second
       name and is NOT a dropback column. Both traps are named here and both
       are given an executable refusal.

NOTHING IN THIS FILE IS FITTED. Every term is a predicate over nflverse
play-by-play flags, every identity is exact arithmetic over those predicates,
and every number in the docstrings was measured by
`nfl/tests/test_stat_contract.py` against the pbp corpus in
`nfl/research/postgame/`, not recalled.

THIS MODULE REPAIRS NOTHING. `assert_counts_are_counts`,
`assert_events_within_opportunity` and `assert_dropback_identity` return a FAIL
naming the violating cells; they never round, clip or renormalise. `deal_counts` is a generator, not a repair: it is
called INSTEAD of forming a continuous product, never afterwards.
"""
from __future__ import annotations

import numpy as np

from sportsplatform.governance.outcome import Cause, Outcome, State

# THE VERSION IS THE POINT OF THE FILE. A consumer that reports a count or a
# band records this string beside it, so "which definition of attempts was
# that" is answerable from the artifact instead of from memory.
CONTRACT_VERSION = 'nfl-stat-contract-1'

# The corpus this contract's partition and identities were verified against.
# Re-measured by the test module; a drift fails there rather than here.
VERIFIED_AGAINST = {
    'corpus': 'nfl/research/postgame/pbp_{2021..2026}.*.csv.gz',
    'filter': ('season_type == REG, two_point_attempt == 0, '
               'play_type != no_play, posteam non-empty'),
    'plays': 211755,
    'counts': {'att_raw': 97696, 'att': 90748, 'sack': 6601, 'spike': 347,
               'rush_attempt': 73815, 'scramble': 5054, 'kneel': 2104,
               'designed_rush': 66657, 'dropbacks': 102403},
    'partition_overlaps': 0,
}


# --------------------------------------------------------------------------
# 1. THE PASSING / RUSHING EVENT TAXONOMY
# --------------------------------------------------------------------------
#
# Seven classes. Every offensive play belongs to AT MOST ONE of them, and the
# six football classes are mutually exclusive by construction rather than by
# convention -- `classify_play` returns exactly one and the test module
# measures that no play of 211,755 lands in two.
#
# `attributed_to` is not decoration. On all 5,054 scramble plays in the corpus
# the passer id is null and the rusher id is set; a scramble charged to the
# passer produces a structurally-zero column, and this project has already
# built one (`nfl/research/p3/build_panel_p3.py`, the comment at line 106).

CLASSES = ('pass_attempt', 'sack', 'spike', 'scramble', 'kneel',
           'designed_rush')

TERMS = {
    'pass_attempt': {
        'label': 'official pass attempt',
        'predicate': 'pass_attempt & !sack & !qb_spike',
        'attributed_to': 'passer_player_id',
        'is_dropback': True,
        'board_key': ('qb', 'att'),
        'note': 'THE BOARD METRIC. Not nflverse `pass_attempt`.'},
    'sack': {
        'label': 'sack',
        'predicate': 'pass_attempt & sack',
        'attributed_to': 'passer_player_id',
        'is_dropback': True,
        'board_key': ('qb', 'sacks'),
        'note': 'a sack is INSIDE nflverse pass_attempt, which is why the '
                'naive `dropbacks - sacks - scrambles` form is wrong.'},
    'spike': {
        'label': 'spike',
        'predicate': 'pass_attempt & qb_spike',
        'attributed_to': 'passer_player_id',
        'is_dropback': False,
        'board_key': None,
        'note': 'also inside nflverse pass_attempt, and NOT a dropback. No '
                'board metric exposes it; it is here so that att_raw can be '
                'decomposed exactly.'},
    'scramble': {
        'label': 'scramble',
        'predicate': 'rush_attempt & qb_scramble',
        'attributed_to': 'rusher_player_id',
        'is_dropback': True,
        'board_key': ('qb', 'scr'),
        'note': 'a dropback that became a run. It is a RUSH ATTEMPT in the '
                'team carry count and a DROPBACK in the passing count; that '
                'double membership is real football and is the reason '
                'rushing_a1 subtracts scrambles before partitioning.'},
    'kneel': {
        'label': 'quarterback kneel',
        'predicate': 'rush_attempt & qb_kneel',
        'attributed_to': 'rusher_player_id',
        'is_dropback': False,
        'board_key': None,
        'note': 'inside D1 `team_carries` (0.7746 per team-game, OWN-5) and '
                'modelled by nobody. It is an EXPLICIT rushing_a1 category '
                'and must never be folded into designed quarterback rushing.'},
    'designed_rush': {
        'label': 'designed rush',
        'predicate': 'rush_attempt & !qb_scramble & !qb_kneel',
        'attributed_to': 'rusher_player_id',
        'is_dropback': False,
        'board_key': None,
        'note': 'the category that rushing_a1 splits into designed_qb / rb / '
                'wr / te / fringe.'},
}

# Aggregates a consumer is allowed to form, each stated as a sum of classes.
AGGREGATES = {
    # nflverse `pass_attempt`, the quantity the broad public reference bands
    # label "pass attempts". IT IS NOT THE BOARD'S qb/att.
    'att_raw': ('pass_attempt', 'sack', 'spike'),
    'dropbacks': ('pass_attempt', 'sack', 'scramble'),
    'rush_attempts': ('scramble', 'kneel', 'designed_rush'),
}

IDENTITIES = {
    'dropback_partition': 'db == att + sacks + scr',
    'att_raw_decomposition': 'att_raw == att + sacks + spikes',
    'att_raw_is_not_att': 'att_raw - att == sacks + spikes  (2.4356 / QB1 tg)',
    'rush_attempt_partition': 'rush_attempts == scr + kneel + designed_rush',
    'a1_ownership_graph': ('team_carries - scrambles == kneel + designed_qb + '
                           'rb + wr + te + fringe'),
}

# Columns that LOOK like a term of this contract and are not. Each entry is a
# trap somebody in this project already fell into.
FALSE_FRIENDS = {
    'panel_p3.dropbacks_as_passer': {
        'looks_like': 'dropbacks',
        'actually_is': 'pass_att_as_passer, i.e. att_raw',
        'evidence': ('equal in 57670 of 57670 rows of '
                     'nfl/research/inputs/panel_p3.csv.gz'),
        'why': ('scrambles are charged to the rusher so none reaches the '
                'passer column, and sacks are already inside pass_attempt. '
                'The leaf carries no true dropback column and a band built on '
                'it is att_raw twice.'),
        'refusal': 'DROPBACK_COLUMN_IS_ATT_RAW'},
    'nflverse.pass_attempt': {
        'looks_like': 'pass_attempt (the board metric)',
        'actually_is': 'att_raw -- includes every sack and every spike',
        'evidence': '6601 sacks and 347 spikes of 97696 att_raw in the corpus',
        'why': 'the board metric qb/att excludes both.',
        'refusal': 'ATT_RAW_USED_AS_ATT'},
}


def classify_play(row) -> Outcome:
    """The class of ONE play, or NOT_APPLICABLE with the reason.

    `row` is any mapping carrying the nflverse flags. Returns PASS with the
    class name; a play that is neither a pass attempt nor a rush attempt is
    NOT_APPLICABLE, which is a different answer from "no class matched".
    """
    def flag(k):
        v = row.get(k)
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0

    if flag('two_point_attempt'):
        return Outcome.not_applicable(
            'PLAY_EXCLUDED_TWO_POINT',
            'two-point attempts are outside every count in this contract; '
            'the corpus builders drop them and so does this.')
    if str(row.get('play_type') or '') == 'no_play':
        return Outcome.not_applicable(
            'PLAY_EXCLUDED_NO_PLAY',
            'a no_play row is a penalty record, not a football event.')
    pas, sack, spike = flag('pass_attempt'), flag('sack'), flag('qb_spike')
    rush, scr, kneel = flag('rush_attempt'), flag('qb_scramble'), \
        flag('qb_kneel')
    if pas and rush:
        return Outcome.fail(
            'PLAY_IS_BOTH_PASS_AND_RUSH',
            'this row carries pass_attempt and rush_attempt together, so the '
            'six classes are not a partition of it. Refused rather than '
            'assigned to one of them: 0 of 211,755 corpus plays do this, so a '
            'row that does is a feed change, not a football event.')
    if pas:
        if sack and spike:
            return Outcome.fail(
                'PLAY_IS_BOTH_SACK_AND_SPIKE',
                'sack and qb_spike on one play. 0 of 211,755 corpus plays do '
                'this and there is no defensible way to choose between them.')
        cls = 'sack' if sack else 'spike' if spike else 'pass_attempt'
        return Outcome.ok(f'PLAY_CLASS_{cls.upper()}', value=cls,
                          detail=TERMS[cls]['predicate'],
                          attributed_to=TERMS[cls]['attributed_to'],
                          contract_version=CONTRACT_VERSION)
    if rush:
        if scr and kneel:
            return Outcome.fail(
                'PLAY_IS_BOTH_SCRAMBLE_AND_KNEEL',
                'qb_scramble and qb_kneel on one play. 0 of 211,755 corpus '
                'plays do this.')
        cls = 'scramble' if scr else 'kneel' if kneel else 'designed_rush'
        return Outcome.ok(f'PLAY_CLASS_{cls.upper()}', value=cls,
                          detail=TERMS[cls]['predicate'],
                          attributed_to=TERMS[cls]['attributed_to'],
                          contract_version=CONTRACT_VERSION)
    if sack or spike or scr or kneel:
        return Outcome.fail(
            'EVENT_FLAG_WITHOUT_ITS_PLAY',
            'a sack / spike / scramble / kneel flag is set on a row that is '
            'neither pass_attempt nor rush_attempt. In the corpus every one '
            'of these flags implies its play flag; a row that breaks that has '
            'changed under us and is refused rather than counted.')
    return Outcome.not_applicable(
        'PLAY_IS_NOT_A_PASS_OR_RUSH',
        'kickoffs, punts, field goals and extra points carry no term of this '
        'contract.')


def tabulate(rows) -> Outcome:
    """Count a sequence of plays into the contract's classes and aggregates.

    Returns the six class counts, the three aggregates, and the count of rows
    excluded with the reason. Excluded rows are COUNTED, never dropped
    silently: "we counted 90,748 attempts" and "we counted 90,748 attempts and
    threw away 4,000 rows we did not understand" are different claims.
    """
    c = {k: 0 for k in CLASSES}
    skipped = {}
    n = 0
    for r in rows:
        n += 1
        o = classify_play(r)
        if o.state is State.FAIL:
            return o
        if o.state is State.NOT_APPLICABLE:
            skipped[o.code] = skipped.get(o.code, 0) + 1
            continue
        c[o.value] += 1
    agg = {k: sum(c[t] for t in terms) for k, terms in AGGREGATES.items()}
    ident = {
        'dropback_partition': (agg['dropbacks']
                               == c['pass_attempt'] + c['sack']
                               + c['scramble']),
        'att_raw_decomposition': (agg['att_raw']
                                  == c['pass_attempt'] + c['sack']
                                  + c['spike']),
        'rush_attempt_partition': (agg['rush_attempts']
                                   == c['scramble'] + c['kneel']
                                   + c['designed_rush']),
    }
    broken = [k for k, v in ident.items() if not v]
    if broken:
        return Outcome.fail(
            'STAT_CONTRACT_IDENTITY_BROKEN',
            f'{broken} do not hold on {n} row(s). These are exact sums of a '
            f'partition, so a failure is an arithmetic defect in this module, '
            f'never a tolerance to widen.',
            counts=c, aggregates=agg, n_rows=n)
    return Outcome.ok(
        'STAT_CONTRACT_TABULATED',
        value={'counts': c, 'aggregates': agg},
        detail=f'{n} row(s); {agg["dropbacks"]} dropbacks = '
               f'{c["pass_attempt"]} attempts + {c["sack"]} sacks + '
               f'{c["scramble"]} scrambles',
        contract_version=CONTRACT_VERSION, n_rows=n,
        rows_excluded=skipped, identities_hold=ident)


def assert_dropback_identity(db, att, sacks, scr, *, atol=0.0) -> Outcome:
    """`db == att + sacks + scr`, EXACTLY, cell by cell.

    `atol` defaults to 0.0 on purpose. These are counts; the identity is a sum
    of integers and holds exactly or it does not hold. A caller working in
    float may pass atol=1e-9, which is a statement about the float
    representation and not about the football.
    """
    D, A, S, R = (np.asarray(x, float) for x in (db, att, sacks, scr))
    if not (D.shape == A.shape == S.shape == R.shape):
        return Outcome.fail(
            'DROPBACK_IDENTITY_SHAPE',
            f'db {D.shape}, att {A.shape}, sacks {S.shape}, scr {R.shape} are '
            f'not the same shape, so they are not the same rows and draws.')
    if D.size == 0:
        return Outcome.blocked(
            'DROPBACK_IDENTITY_NO_CELLS',
            'no cells were supplied. An identity checked over nothing is not '
            'a satisfied identity.', cause=Cause.DATA)
    resid = D - (A + S + R)
    bad = int((np.abs(resid) > atol).sum())
    ev = {'n_cells': int(D.size), 'violating_cells': bad,
          'max_abs_deviation': float(np.abs(resid).max()),
          'identity': IDENTITIES['dropback_partition'],
          'contract_version': CONTRACT_VERSION}
    if bad:
        return Outcome.fail(
            'DROPBACK_IDENTITY_VIOLATED',
            f'{bad} of {D.size} cell(s) where db != att + sacks + scr, worst '
            f'{np.abs(resid).max():.6f}. Refused, never reconciled: this is '
            f'the identity that distinguishes the board`s attempt definition '
            f'from nflverse pass_attempt, and adjusting it would erase the '
            f'distinction.', **ev)
    return Outcome.ok('DROPBACK_IDENTITY_EXACT', value=ev,
                      detail=f'db == att + sacks + scr in all {D.size} '
                             f'cell(s), max deviation '
                             f'{ev["max_abs_deviation"]:.6f}', **ev)


def assert_not_a_dropback_column(name, candidate, att_raw) -> Outcome:
    """Refuse a column that is att_raw wearing the word "dropback".

    The check is behavioural rather than nominal: a column IS att_raw if it
    equals att_raw everywhere. `panel_p3.dropbacks_as_passer` does, in all
    57,670 rows.
    """
    a = np.asarray(candidate, float).reshape(-1)
    b = np.asarray(att_raw, float).reshape(-1)
    if a.shape != b.shape:
        return Outcome.fail(
            'DROPBACK_COLUMN_SHAPE',
            f'{name} has {a.size} row(s) against {b.size} for att_raw.')
    if a.size == 0:
        return Outcome.blocked(
            'DROPBACK_COLUMN_NO_ROWS',
            f'{name} carries no rows, so nothing can be concluded about it.',
            cause=Cause.DATA)
    eq = int((a == b).sum())
    if eq == a.size:
        return Outcome.fail(
            'DROPBACK_COLUMN_IS_ATT_RAW',
            f'{name} equals att_raw in all {a.size} row(s), so it is att_raw '
            f'under a second name and carries no scramble. Using it as a '
            f'dropback count builds a band on att_raw twice. '
            f'{FALSE_FRIENDS["panel_p3.dropbacks_as_passer"]["why"]}',
            column=name, rows=int(a.size), rows_equal=eq,
            contract_version=CONTRACT_VERSION)
    return Outcome.ok(
        'DROPBACK_COLUMN_DISTINCT', value={'rows': int(a.size),
                                           'rows_equal': eq},
        detail=f'{name} differs from att_raw in {a.size - eq} of {a.size} '
               f'row(s), so it is not att_raw under another name. That does '
               f'NOT by itself make it a dropback count.',
        column=name, contract_version=CONTRACT_VERSION)


# --------------------------------------------------------------------------
# 2. COUNTS
# --------------------------------------------------------------------------
#
# The metrics this production tree declares to be counts, keyed the way the
# sealed draw artifact keys them. `nfl/product/metrics.py` holds the same fact
# for the PRODUCT layer and is owned by R5; `reconcile_with_product_registry`
# asserts the two agree, so a divergence is a failing test rather than two
# quiet answers to one question. It is declared here and cross-checked there,
# not imported, because production must not depend on the product layer.

COUNT_METRICS = (
    'qb/att', 'qb/cmp', 'qb/db', 'qb/int', 'qb/ptd', 'qb/rtd',
    'qb/rush_opp', 'qb/sacks', 'qb/scr',
    'receiving/targets', 'receiving/receptions', 'receiving/receiving_td',
    'rushing/carries', 'rushing/rushing_td',
)

# Quantities that are NOT counts and must never be asserted as such.
CONTINUOUS_METRICS = ('qb/pyds', 'qb/ryds', 'receiving/receiving_yards')

# Team LEVELS. D1 draws these as continuous intensities, not as realised
# events, and that is a defensible modelling choice -- a level is a rate of
# play, not a play. They are listed so that "not in COUNT_METRICS" is a
# declaration rather than an omission. Anything that PARTITIONS one of them
# must integerise it first and declare that it did (see `integerise_level`).
TEAM_LEVELS = ('team_volume/team_carries', 'team_volume/team_dropbacks_part',
               'team_volume/team_off_snaps', 'team_volume/team_rz_carries',
               'team_volume/team_targets')


def reconcile_with_product_registry(supported) -> Outcome:
    """`nfl/product/metrics.SUPPORTED` and COUNT_METRICS must name one set.

    `supported` is that mapping, passed in by the caller -- the test module --
    so this module holds no import of the product layer.
    """
    theirs = {f'{a}/{b}' for (a, b), v in supported.items()
              if v.get('kind') == 'count'}
    mine = set(COUNT_METRICS)
    only_theirs, only_mine = sorted(theirs - mine), sorted(mine - theirs)
    if only_theirs or only_mine:
        return Outcome.fail(
            'COUNT_REGISTRY_DIVERGED',
            f'the product layer calls {only_theirs} counts and this contract '
            f'does not; this contract calls {only_mine} counts and the '
            f'product layer does not. One quantity, two answers.',
            only_in_product=only_theirs, only_in_contract=only_mine)
    return Outcome.ok(
        'COUNT_REGISTRY_AGREES', value=sorted(mine),
        detail=f'{len(mine)} metric(s) declared count by both layers',
        contract_version=CONTRACT_VERSION)


def assert_counts_are_counts(matrices, *, metrics=None) -> Outcome:
    """Support validity for every declared count. ASSERTS; never repairs.

    `matrices` is {'<layer>/<metric>': array}. A metric not in the declared
    count set is skipped and NAMED in the evidence, so a typo in a key cannot
    silently mean "nothing to check".
    """
    declared = set(metrics if metrics is not None else COUNT_METRICS)
    checked, skipped, viol = {}, [], []
    for k, v in sorted(matrices.items()):
        if k not in declared:
            skipped.append(k)
            continue
        a = np.asarray(v)
        if a.size == 0:
            return Outcome.fail(
                'COUNT_MATRIX_EMPTY',
                f'{k} carries no cells. An empty matrix is not a count of '
                f'zero.', metric=k)
        f = a.astype(float)
        frac = int((np.abs(f - np.rint(f)) > 0).sum())
        neg = int((f < 0).sum())
        checked[k] = {'cells': int(f.size), 'non_integer': frac,
                      'negative': neg, 'dtype': str(a.dtype)}
        if frac or neg:
            viol.append((k, frac, neg, float(np.abs(f - np.rint(f)).max())))
    if not checked:
        return Outcome.blocked(
            'NO_DECLARED_COUNT_SUPPLIED',
            f'none of the {len(matrices)} matrix(es) supplied is a declared '
            f'count: {sorted(matrices)[:8]}. Nothing was checked, which is '
            f'not the same as everything passing.',
            cause=Cause.DATA, supplied=sorted(matrices), declared=sorted(declared))
    if viol:
        return Outcome.fail(
            'COUNT_SUPPORT_VIOLATED',
            '; '.join(f'{k}: {fr} non-integer and {ng} negative cell(s), '
                      f'worst fractional part {w:.6f}'
                      for k, fr, ng, w in viol)
            + '. A declared count that is not a count cannot carry a '
              'threshold: "9.5+" read off a continuous quantity is not the '
              'probability of nine or more carries. Refused rather than '
              'rounded -- rounding here would hide where it was generated.',
            violations=[{'metric': k, 'non_integer': fr, 'negative': ng,
                         'worst_fractional_part': w} for k, fr, ng, w in viol],
            checked=checked, not_declared_counts=skipped,
            contract_version=CONTRACT_VERSION)
    return Outcome.ok(
        'COUNT_SUPPORT_VALID', value=checked,
        detail=f'{len(checked)} declared count(s) are non-negative integers '
               f'in every cell',
        checked=checked, not_declared_counts=skipped,
        contract_version=CONTRACT_VERSION)


# EVENT -> OPPORTUNITY. Which count is bounded by which, per draw cell.
#
# THE DEFECT THIS EXISTS FOR. 442 cells of the sealed corpus carry more
# rushing touchdowns than carries. Every one of them has a FRACTIONAL carry:
# 415 sit at 0 < carries < 1 with one touchdown and 27 at 1 < carries < 2 with
# two, because `layers.rushing_td` drew its binomial on a ROUNDED carry count
# while the board published the unrounded one. Two numbers for one quantity.
#
# The generation half is already repaired -- `deal_counts` deals an integer
# budget, and the two boards built after that repair carry zero fractional
# carries and zero violations -- but NOTHING ASSERTED THE INVARIANT. The
# repair closed the cause and left the symptom unfenced, so a second route to
# the same state would reach a sealed artifact unannounced.
#
# THE COMPARISON IS AGAINST THE PUBLISHED OPPORTUNITY, NEVER A ROUNDING OF IT.
# All 442 violations vanish against `ceil(carries)` or `rint(carries)`, and
# that is exactly why neither is used: rounding the denominator would make the
# count zero while leaving a fractional carry in a published artifact, which
# is the symptom disappearing rather than the defect closing.
EVENT_BOUNDS = {
    'rushing/rushing_td': ('rushing/carries',
                           'a rushing touchdown is scored on a carry'),
    'receiving/receptions': ('receiving/targets',
                             'a reception is a completed target'),
    'receiving/receiving_td': ('receiving/receptions',
                               'a receiving touchdown is caught'),
    'qb/cmp': ('qb/att', 'a completion is a completed attempt'),
    'qb/ptd': ('qb/cmp', 'a passing touchdown is a completion'),
}


def assert_events_within_opportunity(matrices, *, round_opportunity=None,
                                     bounds=None) -> Outcome:
    """Every declared event <= its opportunity, per draw cell. ASSERTS only.

    A pair whose opportunity array is absent is SKIPPED AND NAMED, because a
    check that silently had nothing to check is this project's Class A defect
    wearing a green tick. A call that checks nothing at all is BLOCKED.
    """
    if round_opportunity is not None:
        return Outcome.fail(
            'EVENT_OPPORTUNITY_ROUNDING_REQUESTED',
            f'round_opportunity={round_opportunity!r}. The bound is read '
            f'against the opportunity the artifact PUBLISHES. Rounding it '
            f'first is what turns 442 impossible cells into zero impossible '
            f'cells without removing one fractional carry from one board, '
            f'and this contract refuses to be the place that happens.')
    pairs = dict(bounds if bounds is not None else EVENT_BOUNDS)
    checked, skipped, viol = {}, [], []
    for ev, (opp, why) in sorted(pairs.items()):
        if ev not in matrices or opp not in matrices:
            skipped.append({'event': ev, 'opportunity': opp,
                            'missing': [k for k in (ev, opp)
                                        if k not in matrices]})
            continue
        e = np.asarray(matrices[ev], float)
        o = np.asarray(matrices[opp], float)
        if e.shape != o.shape:
            return Outcome.fail(
                'EVENT_OPPORTUNITY_SHAPE',
                f'{ev} has shape {list(e.shape)} against {opp} '
                f'{list(o.shape)}. These share one draw index, so a mismatch '
                f'is refused rather than broadcast.', event=ev, opportunity=opp)
        if e.size == 0:
            return Outcome.fail(
                'EVENT_MATRIX_EMPTY',
                f'{ev} carries no cells. An empty matrix is not zero '
                f'violations.', event=ev)
        bad = e > o
        n = int(bad.sum())
        checked[ev] = {'opportunity': opp, 'cells': int(e.size),
                       'violations': n, 'why': why}
        if n:
            worst = float((e - o)[bad].max())
            checked[ev]['worst_excess'] = worst
            viol.append((ev, opp, n, worst, why))
    if not checked:
        return Outcome.blocked(
            'NO_EVENT_OPPORTUNITY_PAIR_SUPPLIED',
            f'none of the {len(matrices)} matrix(es) supplied completes a '
            f'declared event/opportunity pair: {sorted(matrices)[:8]}. '
            f'Nothing was checked, which is not the same as everything '
            f'passing.', cause=Cause.DATA, supplied=sorted(matrices),
            declared=sorted(pairs), skipped=skipped)
    if viol:
        return Outcome.fail(
            'EVENT_EXCEEDS_OPPORTUNITY',
            '; '.join(f'{e}: {n} cell(s) above {o} (worst excess {w:.6f}) -- '
                      f'{why}' for e, o, n, w, why in viol)
            + '. Refused rather than reconciled: the opportunity is what the '
              'artifact publishes, and an event that cannot have happened is '
              'a defect in whatever generated the pair.',
            violations=[{'event': e, 'opportunity': o, 'cells': n,
                         'worst_excess': w} for e, o, n, w, _ in viol],
            checked=checked, skipped_pairs=skipped,
            contract_version=CONTRACT_VERSION)
    return Outcome.ok(
        'EVENTS_WITHIN_OPPORTUNITY', value=checked,
        detail=f'{len(checked)} event/opportunity pair(s) hold in every draw '
               f'cell',
        checked=checked, skipped_pairs=skipped,
        contract_version=CONTRACT_VERSION)


def integerise_level(level, *, mode='round_half_even') -> Outcome:
    """A continuous team LEVEL to an integer budget, with the moves counted.

    This is the ONE rounding this contract permits and it is permitted only
    here, at the point where a continuous level becomes the budget of a
    partition, because a multinomial has no meaning on a fractional budget.
    `rushing_a1.allocate` already requires the caller to declare exactly this
    (`level_rounding='round_half_even'`) and refuses otherwise; the same
    convention is used here so the two cannot disagree.

    It is NOT permitted on an allocated player quantity. Rounding those
    independently is what destroys closure, and `deal_counts` exists so that
    it never has to happen.
    """
    if mode != 'round_half_even':
        return Outcome.fail(
            'LEVEL_ROUNDING_UNDECLARED',
            f'mode={mode!r}; the only declared level rounding is '
            f'"round_half_even", which is what rushing_a1 requires.')
    a = np.asarray(level, float)
    if a.size == 0:
        return Outcome.blocked(
            'LEVEL_EMPTY', 'no level was supplied to integerise.',
            cause=Cause.DATA)
    r = np.rint(a)
    moved = int((np.abs(a - r) > 0).sum())
    if (r < 0).any():
        return Outcome.fail(
            'LEVEL_NEGATIVE',
            f'{int((r < 0).sum())} cell(s) round to a negative budget. A '
            f'negative count of plays is not a small count.')
    return Outcome.ok(
        'LEVEL_INTEGERISED', value=r.astype(np.int64),
        detail=f'{moved} of {a.size} cell(s) moved by round-half-even; mean '
               f'{a.mean():.6f} -> {r.mean():.6f}',
        cells=int(a.size), cells_moved=moved,
        mean_before=float(a.mean()), mean_after=float(r.mean()),
        mean_shift=float(r.mean() - a.mean()), mode=mode,
        contract_version=CONTRACT_VERSION)


def deal_counts(share, other, budget, starts, counts, rng,
                *, metric='count') -> Outcome:
    """GENERATE counts. One multinomial per group per draw.

    THE CONSTRUCTION, AND WHY IT IS NOT A ROUNDING
    ----------------------------------------------
    The incumbent forms `X_i = share_i * budget`, a continuous product, and
    every consumer then rounds it -- `layers.rushing_td` rounds it to draw the
    touchdown, `nfl/product/render.py` rounds it to print it, and a threshold
    reader rounds it implicitly by comparing it to 9.5. Three roundings of one
    quantity, none of them agreeing with the others, and none of them
    preserving the closure `sum_i share_i + other == 1`.

    This deals the integer budget itself:

        (X_1, ..., X_k, X_other) ~ Multinomial(budget, (s_1, ..., s_k, other))

    so in EVERY draw, for EVERY group:

        sum_i X_i + X_other == budget,   exactly, in integers.

    The competition between players is untouched: the probability vector IS
    the simplex the allocation layer produced. The expectation is unchanged --
    E[X_i] = budget * s_i, which is precisely the continuous product it
    replaces -- so no mass is moved on average and nothing is fitted. What
    changes is the VARIANCE: a multinomial draw adds the allocation noise that
    a share-times-level product silently omitted, which is a real property of
    dealing a finite number of carries to a finite number of backs and not an
    artefact. Say so when reporting; do not describe this as a cosmetic
    change.

    This is the same construction `shared_pass.deal_targets` already uses for
    targets under C3, generalised and given a name that says what it does.
    """
    S = np.asarray(share, float)
    O = np.asarray(other, float)
    if S.ndim != 2 or O.ndim != 2:
        return Outcome.fail(
            'DEAL_COUNTS_SHAPE',
            f'share {S.shape} must be (players, draws) and other {O.shape} '
            f'must be (groups, draws)', metric=metric)
    n, m = S.shape
    if O.shape[1] != m or O.shape[0] != len(starts) or len(starts) != len(counts):
        return Outcome.fail(
            'DEAL_COUNTS_GROUP_LAYOUT',
            f'other {O.shape}, {len(starts)} start(s), {len(counts)} count(s) '
            f'and {m} draw(s) do not describe one group layout on one draw '
            f'index.', metric=metric)
    X = np.zeros((n, m), np.int64)
    other_out = np.zeros(O.shape, np.int64)
    for k, (s0, c) in enumerate(zip(starts, counts)):
        b = np.asarray(budget[k]).reshape(-1)
        if b.size != m:
            return Outcome.fail(
                'DEAL_COUNTS_BUDGET_DRAWS',
                f'group {k} has a {b.size}-draw budget against {m}. These '
                f'layers share one draw index, so a mismatch is refused '
                f'rather than reshaped.', metric=metric)
        if np.any(np.abs(b - np.rint(b)) > 0):
            return Outcome.fail(
                'DEAL_COUNTS_BUDGET_NOT_INTEGER',
                f'group {k}: the budget carries '
                f'{int((np.abs(b - np.rint(b)) > 0).sum())} non-integer '
                f'cell(s). A multinomial has no meaning on a fractional '
                f'budget, and turning a continuous level into a count is the '
                f'LEVEL owner`s decision -- see integerise_level -- not this '
                f'allocation`s.', metric=metric, group=k)
        bi = np.rint(np.asarray(b, float)).astype(np.int64)
        if (bi < 0).any():
            return Outcome.fail(
                'DEAL_COUNTS_BUDGET_NEGATIVE',
                f'group {k} carries a negative budget.', metric=metric)
        if c == 0:
            # NOBODY TO DEAL TO IS NOT ZERO OPPORTUNITY. The whole budget is
            # the named other pool, and saying that out loud is the point.
            other_out[k] = bi
            continue
        p = np.empty((c + 1, m), float)
        p[:c] = S[s0:s0 + c]
        p[c] = O[k]
        tot = p.sum(0)
        if (tot <= 0).any():
            return Outcome.fail(
                'DEAL_COUNTS_SIMPLEX_DEGENERATE',
                f'group {k}: the simplex sums to zero in '
                f'{int((tot <= 0).sum())} draw(s), so an event cannot be '
                f'dealt to anybody. Refused rather than dealt uniformly.',
                metric=metric, group=k)
        p = p / tot
        for j in range(m):
            d = rng.multinomial(int(bi[j]), p[:, j])
            X[s0:s0 + c, j] = d[:c]
            other_out[k, j] = d[c]
    # THE CLOSURE IS CHECKED, NOT ASSUMED. It holds by construction; a failure
    # here would be a defect in this function, and a construction that is
    # never checked is a construction nobody knows is still true.
    bad = 0
    for k, (s0, c) in enumerate(zip(starts, counts)):
        b = np.rint(np.asarray(budget[k], float)).astype(np.int64)
        bad += int((X[s0:s0 + c].sum(0) + other_out[k] != b).sum())
    if bad:
        return Outcome.fail(
            'DEAL_COUNTS_DOES_NOT_CLOSE',
            f'{bad} cell(s) where the dealt counts plus the named other pool '
            f'do not equal the budget. This is a multinomial, so it cannot '
            f'happen; it is checked because an unchecked construction is an '
            f'assumption.', metric=metric)
    return Outcome.ok(
        'COUNTS_DEALT',
        value={'counts': X, 'other': other_out},
        detail=f'{metric}: {n} row(s) x {m} draw(s) dealt from an integer '
               f'budget; every event has exactly one owner in every draw',
        metric=metric, n_rows=n, n_draws=m, n_groups=len(starts),
        mean_dealt_per_draw=float(X.sum(0).mean()),
        mean_other_per_draw=float(other_out.sum(0).mean()),
        closure='sum_i counts_i + other == budget, per group per draw, exact',
        competition_preserved='the multinomial probability vector IS the '
                              'allocation simplex; only the support changed',
        nothing_fitted=True, nothing_clipped=True,
        contract_version=CONTRACT_VERSION)
