"""Per-draw coherence of the FINAL, PUBLISHED draw matrices.

WHY THIS FILE EXISTS AND WHY IT IS PURE
=======================================
Every QB coherence verdict in a sealed artifact was evaluated on an
INTERMEDIATE draw set. `run_forecast` calls `qb_v1.identity_check` and
`qb_accounting.reconcile_draws` while the quarterback's completions, passing
yards and passing touchdowns are still QB V1's own draws, and
`football_engine` then OVERWRITES all three from the receiving event before
anything is sealed. So 101 of 101 sealed artifacts carry
QB_DRAW_ACCOUNTING_HOLDS over draws in which 5,278 cells have more completions
than attempts. A verdict about a value that was replaced afterwards is not a
verdict about the forecast.

The checks therefore live HERE -- pure functions over arrays, no file access,
no engine state -- so that the identical code can be run
  * by the engine, on the matrices it is about to emit,
  * by the production path, on the matrices it is about to seal,
  * by a test, on matrices sealed months ago,
and none of the three can drift from the others.

WHERE EACH CHECK MAY BE EVALUATED, AND WHY IT IS NOT A FREE CHOICE
=================================================================
The QB checks may run anywhere after the last write to the QB draws. The CARRY
checks may not run inside the engine at all. `football_engine._team_carries`
returns the SC1-coupled carry vector, while `run_forecast` seals the raw D1
vector into `team_volume/team_carries`; with SC1 live they are different
vectors on the same draw index. An engine-side carry check therefore attests
to a vector nobody publishes -- which is exactly how `SC1_COHERENT` reads PASS
in all nine sealed runs where the published scramble total exceeds the
published carry total. `carry_containment` below is callable only where the
PUBLISHED arrays are in hand, and it says so in its own refusal text.

HARD, DIAGNOSTIC AND DEFERRED
=============================
HARD means IMPOSSIBLE: a rule of the game or an arithmetic identity makes the
state unreachable in any real football game. It is never justified by
plausibility, by calibration, or by what a good forecast ought to look like.
DIAGNOSTIC means the identity is real but the artifact cannot currently
attribute a failure, so gating on it would refuse runs for a reason nobody
could act on. DEFERRED is a third answer and is not a pass: the check is HARD,
it cannot be evaluated without an undeclared step, and the debt is carried.

THREE THINGS THAT LOOK LIKE INVARIANTS AND ARE DELIBERATELY NOT
===============================================================
* NEGATIVE YARDAGE. A catch or a carry for a loss is ordinary football. The
  repository carries 2,261 negative `qb/pyds`, 2,821 `qb/ryds` and 8,213
  `receiving/receiving_yards` cells. All 2,261 negative passing-yard cells are
  in the 68 runs WITHOUT the shared passing event, and every one of them has
  at least one completion, so none is reachable by the zero identity either.
  A floor would also contradict the already-HARD `qb_cross_layer_reconciliation`,
  which asserts team passing yards EQUALS player receiving yards -- and those
  are lawfully negative. `pyds >= 0`, `pyds >= -k` and any clip are refused.
  Only a negative COUNT is impossible.
* `qb/pyds` BEING INTEGER-VALUED. Realised passing yards are integers and
  22.75% of stored cells are not. A continuous predictive representation of an
  integer quantity is a modelling choice, not an impossible state.
* AN OFFICIALLY INACTIVE QUARTERBACK OWNING DROPBACKS. Already declared HARD
  and already gating as `qb_inactive_owns_nothing` in
  `nfl.prospective.artifact.INVARIANTS`. It is CONTRACT_DEPENDENT -- the
  emergency third-quarterback rule -- and is handled there, by the guard that
  owns the official list. Restating it here as a diagnostic would trip
  INVARIANT_MISCLASSIFIED and reopen defect D04.
"""
from __future__ import annotations

import numpy as np

from sportsplatform.governance.outcome import Cause, Outcome, State
from nfl.product import metrics as M

SPEC_VERSION = 'nfl-draw-coherence-1'

HARD = 'HARD'
DIAGNOSTIC = 'DIAGNOSTIC'

# Integer accumulation allowance in float64. NOT a modelling tolerance: no
# check here is given slack chosen to let a run pass.
TOL = 1e-6
# Yardage agreement across two layers counting the same event. Wider than TOL
# because it accumulates over a whole receiver room; the measured worst
# residual in the repository is 1.14e-13.
YARD_TOL = 1e-4

# WHICH ARRAYS ARE COUNTS, READ FROM THE PRODUCT CONTRACT RATHER THAN TYPED
# HERE. A hand-written tuple goes stale the moment a metric is added, and the
# stored dtype is worse than useless for this: `rushing/carries` is int-typed
# nowhere and is declared a count, `qb/pyds` is float and is declared yards.
# `metrics.SUPPORTED[(layer, key)]['kind']` is the declaration, so it is the
# thing consulted.
COUNT_ARRAYS = tuple(sorted(
    f'{layer}/{key}' for (layer, key), spec in M.SUPPORTED.items()
    if spec.get('kind') == 'count'))

COHERENCE = {
    # ---------------- QB, per quarterback per draw ----------------------
    'counts_non_negative': {
        'class': HARD, 'unit': 'cell', 'layers': ('any',),
        'asserts': 'every array declared kind=="count" in '
                   'nfl.product.metrics.SUPPORTED is >= 0 in every cell',
        'why_impossible': 'a negative count of events is not a small count; '
                          'it is not a quantity a game can produce. Scope is '
                          'read from the product contract, never from dtype.'},
    'qb_completions_within_attempts': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'cmp <= att',
        'why_impossible': 'a completion IS an attempt -- one forward pass '
                          'scored twice for the same passer. cmp > att is a '
                          'completed pass that was never thrown.'},
    'qb_completions_and_interceptions_within_attempts': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'cmp + int <= att',
        'why_impossible': 'completions and interceptions are DISJOINT subsets '
                          'of attempts: a pass caught by the defence was not '
                          'also caught by the offence. This is NOT implied by '
                          'cmp <= att and must be stated separately -- of the '
                          '5,929 violating cells in the sealed artifacts, 651 '
                          'satisfy cmp <= att (e.g. att=6, cmp=6, int=1) and '
                          'would survive a repair that only caps completions.'},
    'qb_passing_td_within_completions': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'ptd <= cmp',
        'why_impossible': 'a passing touchdown is a completed pass into the '
                          'end zone, so it is a completion.'},
    'qb_passing_td_within_attempts': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'ptd <= att',
        'why_impossible': 'a touchdown pass is a pass. Independent of '
                          'ptd <= cmp whenever cmp itself exceeds att, which '
                          'is how 22 sealed cells hold more touchdowns than '
                          'the passer had attempts.'},
    'qb_zero_completions_zero_passing_yards': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'cmp == 0 implies pyds == 0',
        'why_impossible': 'passing yards accrue only on completed passes. '
                          'Stated as the ZERO identity and deliberately not '
                          'as pyds >= 0: a completion for a loss is lawful.'},
    'qb_attempts_within_dropbacks': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'att <= db',
        'why_impossible': 'a dropback that becomes an attempt is one '
                          'dropback. Implied by the partition below given '
                          'non-negative sacks and scrambles, and stated so a '
                          'reader need not derive it.'},
    'qb_dropback_partition': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'db == att + sacks + scr, exactly',
        'why_impossible': 'the layer DEFINES a dropback as ending in exactly '
                          'one of the three. A partition, not an '
                          'approximation. Already asserted by '
                          'qb_v1.identity_check -- restated here because that '
                          'check runs BEFORE the shared-pass credit rewrites '
                          'the same draw set.'},
    'qb_rushing_td_within_rush_opportunity': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'rtd <= rush_opp',
        'why_impossible': 'a rushing touchdown requires a rush attempt by the '
                          'same player in the same draw.'},
    'qb_zero_rush_opportunity_zero_rushing_yards': {
        'class': HARD, 'unit': 'cell', 'layers': ('qb',),
        'asserts': 'rush_opp == 0 implies ryds == 0',
        'why_impossible': 'rushing yards accrue on carries. Again the zero '
                          'identity: a carry for a loss is lawful, so this is '
                          'not a non-negativity claim.'},

    # ---------------- receiving, per receiver per draw ------------------
    'receptions_within_targets': {
        'class': HARD, 'unit': 'cell', 'layers': ('receiving',),
        'asserts': 'receptions <= targets',
        'why_impossible': 'a reception IS a target -- the same thrown ball, '
                          'counted once as intended for the receiver and once '
                          'as caught by him. More catches than targets is a '
                          'catch of a pass that was thrown to nobody.'},
    'receiving_td_within_receptions': {
        'class': HARD, 'unit': 'cell', 'layers': ('receiving',),
        'asserts': 'receiving_td <= receptions',
        'why_impossible': 'a receiving touchdown IS a reception -- a catch '
                          'made in the end zone. More touchdown catches than '
                          'catches is a score on a ball nobody caught.'},
    'zero_receptions_zero_receiving_yards': {
        'class': HARD, 'unit': 'cell', 'layers': ('receiving',),
        'asserts': 'receptions == 0 implies receiving_yards == 0',
        'why_impossible': 'receiving yards accrue on catches. The zero '
                          'identity, not a floor: 8,213 negative cells are '
                          'lawful catches for a loss.'},

    # ---------------- rushing -------------------------------------------
    'rushing_td_within_carries': {
        'class': HARD, 'unit': 'cell', 'layers': ('rushing',),
        'asserts': 'rushing_td <= carries',
        'why_impossible': 'a rushing touchdown requires a carry in the same '
                          'draw.',
        'deferred_because':
            'NOT EVALUABLE WITHOUT AN UNDECLARED ROUNDING, AND THE ROUNDING '
            'IS WHAT MANUFACTURES THE PASS. Compared against rint(carries) '
            'there are 0 violations in 381,000 cells; compared against '
            'carries as stored there are 323, of which 306 are a whole '
            'touchdown on a fractional carry. Underneath sits a live contract '
            'violation, not a tolerance question: `rushing/carries` is '
            'declared kind="count", status=MODELED in '
            'nfl.product.metrics.SUPPORTED and is non-integer in 241,584 of '
            '381,000 stored cells (63.4%). Reporting PASS here would launder '
            'that through a rounding step this table never declared. The '
            'debt is carried as DEFERRED and is owed by whoever owns the '
            'carry allocation contract.'},

    # ---------------- team closures -------------------------------------
    'team_targets_within_team_attempts': {
        'class': HARD, 'unit': 'team-draw', 'layers': ('qb', 'receiving'),
        'asserts': 'sum of player targets <= sum of QB attempts, per team per '
                   'draw',
        'why_impossible': 'every target is a pass that team threw in that '
                          'draw. An inequality and not an equality, because '
                          'throwaways and spikes are targeted at nobody and '
                          'players outside the modelled set hold a named '
                          'share.'},
    'team_passing_line_closes_on_receiving': {
        'class': HARD, 'unit': 'team-draw', 'layers': ('qb', 'receiving'),
        'asserts': 'with the shared passing event live, team qb/cmp equals '
                   'team receiving/receptions, qb/ptd equals '
                   'receiving/receiving_td and qb/pyds equals '
                   'receiving/receiving_yards, on the same draw index',
        'why_impossible': 'under C3 these are ONE event counted from two '
                          'sides, so a difference is arithmetic and not a '
                          'disagreement about football. This is the only '
                          'player-to-team EQUALITY the model contract states; '
                          'it is read from the contract rather than invented, '
                          'and it is evaluated only where the receiving layer '
                          'is present and the passing line was credited from '
                          'it.'},

    # ---------------- carries: real identities, unattributable today ----
    'team_qb_rush_opportunity_within_team_carries': {
        'class': DIAGNOSTIC, 'unit': 'team-draw',
        'layers': ('qb', 'team_volume'),
        'asserts': 'sum of QB rush opportunity <= team carries, per team per '
                   'draw',
        'why_not_hard': 'the identity is an impossibility -- a quarterback '
                        'rush IS one of the team\'s rush attempts -- but the '
                        'artifact does not store the carry vector the game '
                        'consumed. run_forecast seals team_volume from D1\'s '
                        'raw level while the engine partitions the '
                        'SC1-coupled level, so a failure cannot be attributed '
                        'between a double-counted carry and a denominator '
                        'that was never used. It is the cheapest early '
                        'warning in the set -- 365 cells across 59 runs, '
                        'against 33 for the RB-inclusive form -- so it is '
                        'measured and reported on every run and gates '
                        'nothing until the stored-vector defect is closed.'},
    'team_scrambles_within_team_carries': {
        'class': DIAGNOSTIC, 'unit': 'team-draw',
        'layers': ('qb', 'team_volume'),
        'asserts': 'sum of QB scrambles <= team carries, per team per draw',
        'why_not_hard': 'same identity and the same unattributable '
                        'denominator. A scramble IS a rush attempt; the '
                        'repository measures team_carries >= scrambles in '
                        '3,230 of 3,230 historical team-games.'},
    'team_carry_allocation_containment': {
        'class': DIAGNOSTIC, 'unit': 'team-draw',
        'layers': ('qb', 'rushing', 'team_volume'),
        'asserts': 'sum of RB carries plus sum of QB rush opportunity <= team '
                   'carries, per team per draw',
        'why_not_hard': 'RB carries and QB rush attempts are disjoint subsets '
                        'of the team rush-attempt count, so exceeding the '
                        'total means a carry was credited twice -- but the '
                        'same stored-denominator defect blocks attribution, '
                        'and the 6,186 violating cells cannot today be split '
                        'between a double-count and the wrong vector.'},
}

HARD_CHECKS = tuple(sorted(k for k, v in COHERENCE.items()
                           if v['class'] == HARD))
DIAGNOSTIC_CHECKS = tuple(sorted(k for k, v in COHERENCE.items()
                                 if v['class'] == DIAGNOSTIC))
DEFERRED_CHECKS = tuple(sorted(k for k, v in COHERENCE.items()
                               if 'deferred_because' in v))

# Checks that must NEVER be evaluated from inside the engine, because the
# engine holds a different vector from the one that gets published. Named as
# data so a caller can assert it rather than remember it.
NOT_ENGINE_EVALUABLE = tuple(sorted(
    k for k, v in COHERENCE.items() if 'team_volume' in v['layers']))


class _Tally:
    """Violations and cells-checked, per named check.

    A CHECK OVER ZERO CELLS HAS NOT PASSED. Every check records its own
    cells-checked count and a check that was never fed reports as
    not-evaluated, never as clean. This mirrors NONQB_ACCOUNTING_VACUOUS in
    nfl/production/nonqb/accounting.py.
    """

    def __init__(self):
        self.violations, self.cells, self.skipped, self.worst = {}, {}, [], {}

    def rec(self, name, mask, checked, worst=None):
        """`mask` is a boolean array of violations, or an integer count."""
        if name not in COHERENCE:
            raise KeyError(
                f'COHERENCE_CHECK_NOT_DECLARED: {name!r} is not in '
                f'draw_coherence.COHERENCE, so nothing says whether it gates.')
        n = int(mask) if isinstance(mask, (int, np.integer)) \
            else int(np.count_nonzero(mask))
        self.violations[name] = self.violations.get(name, 0) + n
        self.cells[name] = self.cells.get(name, 0) + int(checked)
        if n and worst is not None:
            self.worst[name] = worst

    def skip(self, name, why):
        self.skipped.append({'check': name, 'why': why})

    def evidence(self):
        return {'violations': dict(sorted(self.violations.items())),
                'cells_checked': dict(sorted(self.cells.items())),
                'not_evaluated': self.skipped,
                'worst': self.worst}


def _get(arrays, key):
    v = arrays.get(key)
    return None if v is None else np.asarray(v)


def _verdict(tally, code_ok, code_bad, what):
    """PASS / FAIL / BLOCKED from a tally. Emptiness is never a pass."""
    ev = tally.evidence()
    if not tally.cells or not any(tally.cells.values()):
        return Outcome.blocked(
            f'{code_ok}_VACUOUS',
            f'{what}: no cell was checked. A check that measured nothing has '
            f'not held, and reporting it as clean is the failure mode this '
            f'file exists to end.', cause=Cause.DATA, **ev)
    hard_bad = {k: v for k, v in tally.violations.items()
                if v and COHERENCE[k]['class'] == HARD}
    diag_bad = {k: v for k, v in tally.violations.items()
                if v and COHERENCE[k]['class'] == DIAGNOSTIC}
    if hard_bad:
        worst = max(hard_bad, key=hard_bad.get)
        return Outcome.fail(
            code_bad,
            f'{what}: {len(hard_bad)} impossible-state check(s) fail on the '
            f'final draws -- '
            + '; '.join(f'{k} in {v:,} of {tally.cells[k]:,} cell(s)'
                        for k, v in sorted(hard_bad.items()))
            + f'. Worst is {worst}: '
            + COHERENCE[worst]['why_impossible']
            + ' These are impossible states, not mis-calibrated ones, and '
              'clipping them would hide the mechanism that produced them.',
            first_failure=worst, **ev)
    return Outcome.ok(
        code_ok, value={'checks': len(tally.cells),
                        'cells': int(sum(tally.cells.values()))},
        detail=f'{what}: {len(tally.cells)} check(s) hold over '
               f'{sum(tally.cells.values()):,} cell(s)'
               + (f'; {len(tally.skipped)} not evaluated'
                  if tally.skipped else '')
               + (f'; {len(diag_bad)} diagnostic(s) not clean (recorded, not '
                  f'gating): {sorted(diag_bad)}' if diag_bad else ''),
        diagnostics_not_clean=diag_bad, **ev)


def counts_non_negative(arrays) -> Outcome:
    """Every declared count array is >= 0. Yardage is out of scope by
    declaration, not by omission -- see the module docstring."""
    t = _Tally()
    present = [k for k in COUNT_ARRAYS if _get(arrays, k) is not None]
    if not present:
        return Outcome.not_applicable(
            'COUNT_NON_NEGATIVITY_NOT_APPLICABLE',
            'this draw set carries no array declared kind=="count" in the '
            'product contract, so there is nothing to check. Recorded rather '
            'than left silent.',
            declared_count_arrays=list(COUNT_ARRAYS))
    worst, n, cells = None, 0, 0
    for k in present:
        v = _get(arrays, k)
        bad = int((v < -TOL).sum())
        n += bad
        cells += int(v.size)
        if bad and worst is None:
            worst = {'array': k, 'min': float(v.min())}
    t.rec('counts_non_negative', n, cells, worst)
    return _verdict(t, 'COUNTS_NON_NEGATIVE', 'COUNT_ARRAY_NEGATIVE',
                    f'{len(present)} declared count array(s)')


def qb_coherence(draws) -> Outcome:
    """Per-quarterback per-draw impossibility checks on the FINAL QB draws.

    `draws` maps either 'qb/<field>' or bare '<field>' to a (rows x draws)
    array, so the engine can pass `qb['draws']` unchanged and a test can pass
    an npz view. Nothing here indexes a row positionally across layers.

    Safe to call from anywhere after the last write to the QB draws. It reads
    no team quantity, so the published-vs-consumed carry-vector trap described
    in the module docstring cannot reach it.
    """
    a = {k.split('/', 1)[-1]: np.asarray(v) for k, v in draws.items()
         if not k.startswith(('receiving/', 'rushing/', 'team_volume/'))}
    need = ('att', 'cmp', 'ptd', 'pyds', 'int', 'db', 'sacks', 'scr')
    missing = [k for k in need if k not in a]
    if missing:
        return Outcome.blocked(
            'QB_COHERENCE_INPUT_INCOMPLETE',
            f'the QB draw set has no {missing}. A skipped identity is not a '
            f'satisfied identity.', cause=Cause.DATA, missing=missing)
    att, cmp_, ptd = a['att'], a['cmp'], a['ptd']
    pyds, itc, db = a['pyds'], a['int'], a['db']
    sacks, scr = a['sacks'], a['scr']
    n = int(att.size)
    if not n:
        return Outcome.blocked(
            'QB_COHERENCE_EMPTY',
            'the QB draw set is empty; zero draw cells is an error, not a '
            'reconciliation.', cause=Cause.DATA)
    t = _Tally()

    def w(mask, excess):
        if not np.count_nonzero(mask):
            return None
        sev = np.where(mask, excess, -np.inf)
        i, j = np.unravel_index(int(np.argmax(sev)), sev.shape)
        return {'row': int(i), 'draw': int(j), 'excess': float(sev[i, j]),
                'att': float(att[i, j]), 'cmp': float(cmp_[i, j]),
                'int': float(itc[i, j]), 'ptd': float(ptd[i, j]),
                'pyds': float(pyds[i, j])}

    m1 = cmp_ > att + TOL
    t.rec('qb_completions_within_attempts', m1, n, w(m1, cmp_ - att))
    m2 = cmp_ + itc > att + TOL
    t.rec('qb_completions_and_interceptions_within_attempts', m2, n,
          w(m2, cmp_ + itc - att))
    m3 = ptd > cmp_ + TOL
    t.rec('qb_passing_td_within_completions', m3, n, w(m3, ptd - cmp_))
    m4 = ptd > att + TOL
    t.rec('qb_passing_td_within_attempts', m4, n, w(m4, ptd - att))
    m5 = (np.abs(cmp_) <= TOL) & (np.abs(pyds) > TOL)
    t.rec('qb_zero_completions_zero_passing_yards', m5, n,
          w(m5, np.abs(pyds)))
    m6 = att > db + TOL
    t.rec('qb_attempts_within_dropbacks', m6, n, w(m6, att - db))
    m7 = np.abs(att + sacks + scr - db) > TOL
    t.rec('qb_dropback_partition', m7, n, w(m7, np.abs(att + sacks + scr - db)))
    if 'rush_opp' in a and 'rtd' in a:
        ro, rtd = a['rush_opp'], a['rtd']
        m8 = rtd > ro + TOL
        t.rec('qb_rushing_td_within_rush_opportunity', m8, int(ro.size),
              w(m8, rtd - ro))
        if 'ryds' in a:
            m9 = (np.abs(ro) <= TOL) & (np.abs(a['ryds']) > TOL)
            t.rec('qb_zero_rush_opportunity_zero_rushing_yards', m9,
                  int(ro.size), w(m9, np.abs(a['ryds'])))
        else:
            t.skip('qb_zero_rush_opportunity_zero_rushing_yards',
                   'the draw set carries no qb/ryds')
    else:
        t.skip('qb_rushing_td_within_rush_opportunity',
               'the draw set carries no qb/rush_opp or qb/rtd')
        t.skip('qb_zero_rush_opportunity_zero_rushing_yards',
               'the draw set carries no qb/rush_opp')
    return _verdict(t, 'QB_DRAW_COHERENCE_HOLDS', 'QB_DRAW_COHERENCE_VIOLATED',
                    f'{att.shape[0]} quarterback row(s)')


def receiving_coherence(arrays) -> Outcome:
    """Per-receiver per-draw checks. NOT_APPLICABLE, never PASS, when the
    receiving layer is absent -- which is 68 of the 101 sealed runs, because
    defect D03 deferred the appearance layer for the twelve-game slate."""
    tg, rc = _get(arrays, 'receiving/targets'), _get(arrays,
                                                     'receiving/receptions')
    ry = _get(arrays, 'receiving/receiving_yards')
    rtd = _get(arrays, 'receiving/receiving_td')
    if tg is None or rc is None:
        return Outcome.not_applicable(
            'RECEIVING_COHERENCE_NOT_IN_THIS_RUN',
            'this run carries no receiving draw set, so its identities cannot '
            'be evaluated. Recorded rather than left silent: an absent check '
            'is not a satisfied one.')
    t = _Tally()
    n = int(tg.size)
    t.rec('receptions_within_targets', rc > tg + TOL, n)
    if rtd is not None:
        t.rec('receiving_td_within_receptions', rtd > rc + TOL, n)
    else:
        t.skip('receiving_td_within_receptions', 'no receiving/receiving_td')
    if ry is not None:
        t.rec('zero_receptions_zero_receiving_yards',
              (np.abs(rc) <= TOL) & (np.abs(ry) > TOL), n)
    else:
        t.skip('zero_receptions_zero_receiving_yards',
               'no receiving/receiving_yards')
    return _verdict(t, 'RECEIVING_DRAW_COHERENCE_HOLDS',
                    'RECEIVING_DRAW_COHERENCE_VIOLATED',
                    f'{tg.shape[0]} receiver row(s)')


def rushing_coherence(arrays) -> Outcome:
    """Rushing checks. Returns DEFERRED with the debt named, because the one
    identity here cannot be evaluated without a rounding step that nothing
    declares -- and that rounding is what produces its clean result."""
    car = _get(arrays, 'rushing/carries')
    rtd = _get(arrays, 'rushing/rushing_td')
    if car is None or rtd is None:
        return Outcome.not_applicable(
            'RUSHING_COHERENCE_NOT_IN_THIS_RUN',
            'this run carries no rushing draw set. Recorded rather than left '
            'silent.')
    raw = int((rtd > car + TOL).sum())
    rounded = int((rtd > np.rint(car) + TOL).sum())
    frac = int((np.abs(car - np.rint(car)) > 1e-9).sum())
    whole_on_frac = int(((rtd >= 1) & (car < 1) & (car > TOL)).sum())
    spec = COHERENCE['rushing_td_within_carries']
    return Outcome.deferred(
        'RUSHING_TD_WITHIN_CARRIES_DEFERRED',
        spec['deferred_because'],
        owed={'decision': 'is `rushing/carries` a count or a continuous '
                          'level? The product contract says count, MODELED; '
                          'the stored array is non-integer in '
                          f'{frac:,} of {car.size:,} cell(s) '
                          f'({frac / max(car.size, 1):.1%}).',
              'owner': 'the carry-allocation contract, not this file',
              'blocks': 'rushing_td_within_carries, which cannot be a HARD '
                        'gate while its right-hand side is of undeclared '
                        'type'},
        violations_against_carries_as_stored=raw,
        violations_against_rint_carries=rounded,
        whole_touchdowns_on_a_fractional_carry=whole_on_frac,
        non_integer_carry_cells=frac, cells=int(car.size),
        note='both numbers are reported so that the rounding cannot launder '
             'the result: 0 violations with rint, '
             f'{raw} without.')


def team_closure(arrays, team_rows, shared_pass_live: bool) -> Outcome:
    """Team-level closures between the QB room and the receiver room.

    `team_rows` maps a team label to that team's ROW INDICES per layer:
    {'ATL': {'qb': [0, 3], 'receiving': [1, 2, 5]}}. The caller resolves them,
    because row identity in this repository lives in
    `manifest['layers'][layer]['row_ids']` and a positional join across two
    layers is a defect this project has already paid for.

    `shared_pass_live` is REQUIRED and not inferred. The three equalities hold
    only where the passing line was credited from the receiving event; on a
    run without it the two layers draw the same football quantity twice and
    are not contractually equal. Guessing which regime a run was in, from the
    numbers themselves, would be asserting the conclusion.
    """
    att, cmp_ = _get(arrays, 'qb/att'), _get(arrays, 'qb/cmp')
    ptd, pyds = _get(arrays, 'qb/ptd'), _get(arrays, 'qb/pyds')
    tg, rc = _get(arrays, 'receiving/targets'), _get(arrays,
                                                     'receiving/receptions')
    ry = _get(arrays, 'receiving/receiving_yards')
    rtd = _get(arrays, 'receiving/receiving_td')
    if att is None or tg is None or not team_rows:
        return Outcome.not_applicable(
            'TEAM_CLOSURE_NOT_IN_THIS_RUN',
            'the QB and receiving layers are not both present with a row map, '
            'so no team closure can be formed. Recorded rather than left '
            'silent.')
    t = _Tally()
    for team, byl in sorted(team_rows.items()):
        qi, ri = list(byl.get('qb') or []), list(byl.get('receiving') or [])
        if not qi or not ri:
            continue
        t.rec('team_targets_within_team_attempts',
              tg[ri].sum(0) > att[qi].sum(0) + TOL, int(tg.shape[1]))
        if shared_pass_live:
            pairs = [('completions', cmp_[qi].sum(0), rc[ri].sum(0), TOL)]
            if rtd is not None:
                pairs.append(('passing_td', ptd[qi].sum(0), rtd[ri].sum(0),
                              TOL))
            if ry is not None:
                pairs.append(('passing_yards', pyds[qi].sum(0), ry[ri].sum(0),
                              YARD_TOL))
            for _name, lhs, rhs, tol in pairs:
                t.rec('team_passing_line_closes_on_receiving',
                      np.abs(lhs - rhs) > tol, int(lhs.size))
    if not shared_pass_live:
        t.skip('team_passing_line_closes_on_receiving',
               'the shared passing event was not live on this run, so the '
               'three identities are not asserted by the model contract')
    return _verdict(t, 'TEAM_CLOSURE_HOLDS', 'TEAM_CLOSURE_VIOLATED',
                    f'{len(team_rows)} team(s)')


def carry_containment(arrays, team_rows) -> Outcome:
    """DIAGNOSTIC. Carries, measured against the PUBLISHED team carry vector.

    DO NOT CALL THIS FROM INSIDE THE ENGINE. `football_engine._team_carries`
    returns the SC1-coupled vector; `run_forecast` seals D1's raw vector into
    `team_volume/team_carries`. With SC1 live they differ, so an engine-side
    evaluation attests to a vector that is never published -- reproducing, one
    layer along, exactly the defect that lets `SC1_COHERENT` read PASS in the
    nine sealed runs whose published scramble total exceeds their published
    carry total. Call it where the published arrays are in hand.

    Every check here is DIAGNOSTIC and none of them gates. The identities are
    genuine impossibilities; what is unavailable is the attribution, and
    refusing a run on a number whose denominator is known to be the wrong one
    would be a refusal nobody could act on.
    """
    tc = _get(arrays, 'team_volume/team_carries')
    scr, ro = _get(arrays, 'qb/scr'), _get(arrays, 'qb/rush_opp')
    car = _get(arrays, 'rushing/carries')
    if tc is None or scr is None or not team_rows:
        return Outcome.not_applicable(
            'CARRY_CONTAINMENT_NOT_IN_THIS_RUN',
            'no published team carry vector with a row map, so containment '
            'cannot be measured. Recorded rather than left silent.')
    t = _Tally()
    for team, byl in sorted(team_rows.items()):
        qi = list(byl.get('qb') or [])
        ti = byl.get('team_volume')
        if not qi or ti is None:
            continue
        budget = tc[int(ti)]
        n = int(budget.size)
        t.rec('team_scrambles_within_team_carries',
              scr[qi].sum(0) > budget + TOL, n)
        if ro is not None:
            t.rec('team_qb_rush_opportunity_within_team_carries',
                  ro[qi].sum(0) > budget + TOL, n)
        ri = list(byl.get('rushing') or [])
        if car is not None and ro is not None and ri:
            t.rec('team_carry_allocation_containment',
                  car[ri].sum(0) + ro[qi].sum(0) > budget + TOL, n)
    return _verdict(t, 'CARRY_CONTAINMENT_MEASURED',
                    'CARRY_CONTAINMENT_VIOLATED', f'{len(team_rows)} team(s)')


def assert_draw_coherence(arrays, team_rows=None, shared_pass_live=False,
                          include_carries=False) -> Outcome:
    """Every check this file declares, over one run's FINAL published arrays.

    `include_carries` is OFF by default and must be turned on deliberately, by
    a caller holding the published team carry vector. See `carry_containment`.

    Returns PASS only when every HARD check that could be evaluated held and
    at least one check ran. NOT_APPLICABLE and DEFERRED components are carried
    into the evidence by name; neither is counted as a pass.
    """
    parts = {
        'counts_non_negative': counts_non_negative(arrays),
        'qb': qb_coherence(arrays),
        'receiving': receiving_coherence(arrays),
        'rushing': rushing_coherence(arrays),
        'team_closure': team_closure(arrays, team_rows or {},
                                     bool(shared_pass_live)),
    }
    if include_carries:
        parts['carries'] = carry_containment(arrays, team_rows or {})
    else:
        parts['carries'] = Outcome.not_applicable(
            'CARRY_CONTAINMENT_NOT_REQUESTED',
            'the caller did not declare that it holds the PUBLISHED team '
            'carry vector, so the carry diagnostics were not run. They are '
            'off by default on purpose: evaluated against the engine\'s '
            'coupled vector they would attest to numbers nobody seals.')
    ev = {k: {'state': o.state.value, 'code': o.code,
              **{kk: vv for kk, vv in o.evidence.items()
                 if kk in ('violations', 'cells_checked', 'not_evaluated',
                           'owed', 'diagnostics_not_clean')}}
          for k, o in sorted(parts.items())}
    failed = sorted(k for k, o in parts.items() if o.state is State.FAIL)
    blocked = sorted(k for k, o in parts.items() if o.state is State.BLOCKED)
    ran = [k for k, o in parts.items() if o.state is State.PASS]
    if failed:
        first = parts[failed[0]]
        return Outcome.fail(
            'DRAW_COHERENCE_VIOLATED',
            f'{len(failed)} component(s) carry an impossible state on the '
            f'final draws: {failed}. First: {first.code}: '
            f'{first.detail[:300]}',
            components=ev, failed=failed, spec_version=SPEC_VERSION)
    if blocked:
        return Outcome.blocked(
            'DRAW_COHERENCE_NOT_EVALUABLE',
            f'{blocked} could not be evaluated, and a check that did not run '
            f'has not passed.', cause=Cause.DATA, components=ev,
            spec_version=SPEC_VERSION)
    if not ran:
        return Outcome.blocked(
            'DRAW_COHERENCE_VACUOUS',
            'no component evaluated a single cell. Zero checks is an error, '
            'not a clean result.', cause=Cause.DATA, components=ev,
            spec_version=SPEC_VERSION)
    deferred = sorted(k for k, o in parts.items() if o.state is State.DEFERRED)
    na = sorted(k for k, o in parts.items() if o.state is State.NOT_APPLICABLE)
    return Outcome.ok(
        'DRAW_COHERENCE_HOLDS',
        value={'evaluated': ran, 'deferred': deferred, 'not_applicable': na},
        detail=f'{len(ran)} component(s) evaluated and hold'
               + (f'; {len(deferred)} DEFERRED with the debt named: '
                  f'{deferred}' if deferred else '')
               + (f'; {len(na)} not applicable to this run: {na}'
                  if na else ''),
        components=ev, spec_version=SPEC_VERSION)
