"""Per-player opportunity decomposition: the chain from team volume to output.

WHAT THIS IS

A READER. It opens a sealed board directory, joins the stored draw matrices to
players by declared identity, and writes down -- link by link -- how a final
number was reached from a team-level quantity. It computes nothing the engine
did not already produce, adjusts no projection, applies no floor and selects no
estimator. Every number it emits is either read straight out of a stored draw
matrix or is an arithmetic combination of stored matrices whose *provenance
grade is recorded alongside it*.

WHY THE PROVENANCE GRADE IS THE POINT

A decomposition is only evidence if you can tell which of its links were
measured and which were reconstructed. `yards_per_reception = yards / receptions`
is not a measurement of a conversion rate: it is a ratio of two numbers the
engine emitted, and it will reproduce itself exactly no matter what the engine
did. Presenting it beside a genuinely measured per-draw identity as though both
were findings is how a decomposition starts confirming whatever produced it.

So every link carries an `evidence` grade:

    MEASURED_DRAWS          both sides are stored draw matrices, and the stated
                            relation was checked on every draw cell
    DERIVED_BY_SUM          a total formed by summing stored matrices
    DERIVED_BY_DIFFERENCE   formed by subtracting stored matrices
    DERIVED_BY_DIVISION     a rate obtained by dividing two of the above. NOT
                            independent evidence about the rate.
    ABSENT                  the engine has no such quantity. A substitute may
                            be named, and then it must say why the substitution
                            is honest and in which direction it is wrong.

THE THREE ABSENCES THIS BOARD ACTUALLY HAS, named rather than papered over

1.  ROUTES. There is no routes layer anywhere in V1. The upstream stand-in is
    pass-snap participation, which `nfl/production/nonqb/layers.py:272` itself
    calls "an upper bound on routes run", and which is not persisted into the
    sealed artifact at all. So the receiving chain records the route link as
    ABSENT with a named substitute that is *itself* absent from the artifact.
2.  RUSHING YARDS for RB/WR/TE. The board declares
    `RUSHING_CONVERSION_CONTROL_UNDEFINED` and names `carries x yards-per-carry`
    as the PROHIBITED implementation. This module therefore terminates the
    rushing chain at carries and emits null. Computing the prohibited product
    "just as a diagnostic" would be the model change this pass forbids.
3.  P(participates) for every non-quarterback. The appearance layer runs, but
    its probability is not written into the sealed artifact, and the draws
    cannot recover it: a player who appears and receives nothing is
    indistinguishable, cell by cell, from a player who did not appear. What the
    draws DO identify is a bound, and the bound is recorded as a bound.

A TEAM WITH NO MODELLED LAYER IS A STATE, NOT A ZERO

DEN carries no receiving and no rushing layer on this board because the
appearance layer deferred the whole team (`APPEARANCE_TEAM_DEFERRED`: a team
with no filed injury report is not a team with no injuries). Rendering that as
0.0 targets would be a forecast of zero, which is a much stronger and quite
false claim. Team layer state is therefore a first-class enum and the absence
carries the governance code that caused it.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

CONTRACT = 'nfl-decomposition-1'

# -- evidence grades ---------------------------------------------------------
MEASURED = 'MEASURED_DRAWS'
SUMMED = 'DERIVED_BY_SUM'
DIFFERENCED = 'DERIVED_BY_DIFFERENCE'
DIVIDED = 'DERIVED_BY_DIVISION'
ABSENT = 'ABSENT'

# -- team layer states -------------------------------------------------------
LAYER_MODELLED = 'MODELLED'
LAYER_ABSENT_DEFERRED = 'ABSENT_TEAM_DEFERRED'
LAYER_ABSENT_UNEXPLAINED = 'ABSENT_UNEXPLAINED'

# -- participation bases -----------------------------------------------------
PART_IDENTIFIED = 'IDENTIFIED_IN_DRAWS'
PART_BOUND_ONLY = 'LOWER_BOUND_ONLY'

_RECEIVING = 'receiving'
_RUSHING = 'rushing'
_QB = 'qb'
_TEAM = 'team_volume'


class DecompositionInputError(RuntimeError):
    """A named refusal. An unreadable input is never a zero row."""


# ---------------------------------------------------------------------------
# loading, with every absence named
# ---------------------------------------------------------------------------
def _read_json(path: pathlib.Path, code: str):
    if not path.exists():
        raise DecompositionInputError(f'{code}: {path} does not exist')
    txt = path.read_text()
    if not txt.strip():
        raise DecompositionInputError(f'{code}: {path} is empty (0 useful bytes)')
    return json.loads(txt)


def load(board_dir) -> tuple:
    """(board, manifest, draws). Every failure is a named raise, never a None."""
    d = pathlib.Path(board_dir)
    if not d.is_dir():
        raise DecompositionInputError(f'BOARD_DIR_MISSING: {d}')
    board = _read_json(d / 'board.json', 'BOARD_JSON_MISSING')
    manifest = _read_json(d / 'player_draws_manifest.json',
                          'DRAW_MANIFEST_MISSING')
    npz = d / 'player_draws.npz'
    if not npz.exists():
        raise DecompositionInputError(f'DRAW_MATRIX_MISSING: {npz}')
    draws = np.load(npz)
    if not list(draws.files):
        raise DecompositionInputError(
            f'DRAW_MATRIX_EMPTY: {npz} carries zero arrays. An empty draw set '
            f'is an error, not a result.')
    layers = manifest.get('layers') or {}
    if not layers:
        raise DecompositionInputError(
            'DRAW_MANIFEST_NO_LAYERS: row identity is declared under '
            "manifest['layers'][<layer>]['row_ids']; without it a join could "
            'only be positional, which is the defect test_draw_row_identity '
            'exists to prevent.')
    return board, manifest, draws


def rows_of(manifest: dict, layer: str) -> dict:
    """{row_id: row index} for one layer. Identity, never position."""
    lay = (manifest.get('layers') or {}).get(layer)
    if lay is None:
        return {}
    ids = lay.get('row_ids')
    if not ids:
        raise DecompositionInputError(
            f'LAYER_ROW_IDS_EMPTY: layer {layer!r} declares no row_ids')
    return {rid: i for i, rid in enumerate(ids)}


def matrix(draws, layer: str, metric: str):
    key = f'{layer}__{metric}'
    if key not in draws.files:
        raise DecompositionInputError(
            f'DRAW_ARRAY_MISSING: {key} is not in the stored draw set '
            f'({len(draws.files)} arrays present)')
    return np.asarray(draws[key])


# ---------------------------------------------------------------------------
# small numeric helpers. Every one of them is descriptive only.
# ---------------------------------------------------------------------------
def _f(x):
    return None if x is None else round(float(x), 6)


def _mean(a):
    return _f(np.mean(a))


def _cond_mean(a, mask):
    """E[a | mask]. None when the mask never fires -- never a silent 0."""
    m = np.asarray(mask, dtype=bool)
    if not m.any():
        return None
    return _f(np.mean(np.asarray(a)[m]))


def _p_zero(a):
    return _f(np.mean(np.asarray(a) == 0))


def _ratio(num, den):
    """num/den, or None. A zero denominator is an absence, not an infinity."""
    if den is None or num is None:
        return None
    return None if abs(den) < 1e-12 else _f(num / den)


def _link(step, evidence, value=None, **kw):
    out = {'step': step, 'evidence': evidence, 'value': value}
    out.update(kw)
    return out


def _ratio_link(step, num_name, num, den_name, den, note=''):
    """A rate obtained by dividing. Graded DERIVED_BY_DIVISION, always.

    The inputs may each be measured; the RATE is not, and the distinction is
    the reason this helper exists rather than an inline division.
    """
    return _link(step, DIVIDED, _ratio(num, den),
                 numerator={'name': num_name, 'mean': _f(num)},
                 denominator={'name': den_name, 'mean': _f(den)},
                 note=note or 'a ratio computed backwards from two engine '
                              'outputs; it reproduces itself by construction '
                              'and is not independent evidence about the rate')


# ---------------------------------------------------------------------------
# team scaffolding
# ---------------------------------------------------------------------------
def team_of_player(board: dict) -> dict:
    out = {}
    for p in board.get('players') or []:
        gid = p.get('gsis_id')
        if not gid:
            raise DecompositionInputError(
                'BOARD_PLAYER_WITHOUT_GSIS: a board row with no identity '
                'cannot be joined to a draw row')
        out[gid] = p
    if not out:
        raise DecompositionInputError(
            'BOARD_HAS_NO_PLAYERS: an empty board is an error, not a result')
    return out


def _deferral_code(board: dict, team: str):
    """The governance code that explains a missing layer, or None."""
    for rec in board.get('layer_governance') or []:
        for w in rec.get('warnings') or []:
            if team in w and 'DEFERRED' in w:
                code = w.split(':')[1].strip() if ':' in w else 'DEFERRED'
                return code.split()[0], w
    return None, None


def team_layer_states(board, manifest, teams) -> dict:
    """Per team, per layer: MODELLED, or ABSENT with the code that caused it.

    Absence is carried as a state. It is never rendered as a modelled zero.
    """
    players = team_of_player(board)
    out = {}
    for team in teams:
        state = {}
        for layer in (_QB, _RECEIVING, _RUSHING):
            rows = rows_of(manifest, layer)
            mine = [g for g, p in players.items()
                    if p.get('team') == team and g in rows]
            if mine:
                state[layer] = {'state': LAYER_MODELLED,
                                'n_rows': len(mine), 'code': None,
                                'detail': None}
                continue
            code, detail = _deferral_code(board, team)
            state[layer] = {
                'state': LAYER_ABSENT_DEFERRED if code else
                         LAYER_ABSENT_UNEXPLAINED,
                'n_rows': 0,
                'code': code or 'ABSENCE_WITHOUT_A_DECLARED_CAUSE',
                'detail': detail or
                          'no layer rows for this team and no governance '
                          'warning naming it. An unexplained absence is '
                          'reported as unexplained, not as zero opportunity.'}
        out[team] = state
    return out


def _team_qb_rows(board, manifest, team):
    rows = rows_of(manifest, _QB)
    players = team_of_player(board)
    return [rows[g] for g, p in players.items()
            if p.get('team') == team and g in rows]


# ---------------------------------------------------------------------------
# the team chain: plays -> dropbacks / designed rushes -> allocation pools
# ---------------------------------------------------------------------------
def team_chain(board, manifest, draws, team) -> dict:
    trow = rows_of(manifest, _TEAM)
    if team not in trow:
        raise DecompositionInputError(
            f'TEAM_VOLUME_ROW_MISSING: {team} has no team_volume row')
    ti = trow[team]
    snaps = matrix(draws, _TEAM, 'team_off_snaps')[ti]
    db = matrix(draws, _TEAM, 'team_dropbacks_part')[ti]
    carries = matrix(draws, _TEAM, 'team_carries')[ti]
    stored_targets = matrix(draws, _TEAM, 'team_targets')[ti]

    qb_rows = _team_qb_rows(board, manifest, team)
    qb_db = matrix(draws, _QB, 'db')[qb_rows].sum(0) if qb_rows else None
    qb_att = matrix(draws, _QB, 'att')[qb_rows].sum(0) if qb_rows else None
    qb_cmp = matrix(draws, _QB, 'cmp')[qb_rows].sum(0) if qb_rows else None
    qb_pyds = matrix(draws, _QB, 'pyds')[qb_rows].sum(0) if qb_rows else None
    qb_scr = matrix(draws, _QB, 'scr')[qb_rows].sum(0) if qb_rows else None

    links = [
        _link('team_plays (offensive snaps)', MEASURED, _mean(snaps),
              array='team_volume__team_off_snaps'),
        _link('team_plays -> team_dropbacks', MEASURED, _mean(db),
              array='team_volume__team_dropbacks_part'),
        _link('team_plays -> team_carries (designed rushes + scrambles)',
              MEASURED, _mean(carries), array='team_volume__team_carries'),
        _ratio_link('dropback rate = team_dropbacks / team_plays',
                    'team_dropbacks_part', float(np.mean(db)),
                    'team_off_snaps', float(np.mean(snaps))),
    ]

    resid = snaps - (db + carries)
    links.append(_link(
        'residual = team_plays - (team_dropbacks + team_carries)',
        DIFFERENCED, _mean(resid),
        min=_f(resid.min()), max=_f(resid.max()),
        note='the three team levels are drawn as separate streams and do not '
             'close to each other by construction. The residual is reported '
             'because a decomposition that hid it would imply a closure the '
             'engine does not enforce.'))

    # -- the QB dropback closure, which IS a per-draw measured identity
    if qb_db is not None:
        gap = np.abs(qb_db - np.rint(db))
        links.append(_link(
            'team_dropbacks -> sum(QB dropbacks)', MEASURED,
            _mean(qb_db),
            identity='sum(qb__db over the team) == rint(team_dropbacks_part)',
            holds_on_every_draw=bool(gap.max() == 0),
            worst_absolute_deviation=_f(gap.max()),
            note='checked cell by cell on the stored draws; this one is a '
                 'measurement, not a reconstruction'))

    # -- designed rush budget
    budget = None
    if qb_scr is not None:
        budget = np.rint(carries) - qb_scr
        links.append(_link(
            'designed_rush_budget = rint(team_carries) - sum(QB scrambles)',
            DIFFERENCED, _mean(budget),
            min=_f(budget.min()),
            note='the A1 ownership graph subtracts dropback-owned scrambles '
                 'from the carry level before partitioning. rint() is the '
                 "caller's declared level_rounding, not this module's choice."))

    # -- the receiving allocation denominator, and the stored value that is NOT it
    rrows = rows_of(manifest, _RECEIVING)
    players = team_of_player(board)
    mine = [rrows[g] for g, p in players.items()
            if p.get('team') == team and g in rrows]
    sum_targets = (matrix(draws, _RECEIVING, 'targets')[mine].sum(0)
                   if mine else None)
    if sum_targets is not None and qb_att is not None:
        unallocated = qb_att - sum_targets
        links.append(_link(
            'QB attempts -> sum(modelled player targets)', SUMMED,
            _mean(sum_targets),
            unallocated_attempts_mean=_mean(unallocated),
            unallocated_attempts_min=_f(unallocated.min()),
            unallocated_attempts_max=_f(unallocated.max()),
            note='every modelled target sits inside a QB attempt, but not '
                 'every attempt carries a modelled target. The gap is the '
                 'attempts that reach no modelled receiver and it is never '
                 'negative on this board.'))
    links.append(_link(
        'stored team_volume__team_targets', MEASURED, _mean(stored_targets),
        is_the_allocation_denominator=False,
        code='WS09_J12_STORED_TEAM_TARGETS_IS_NOT_THE_DENOMINATOR',
        note='persisted so the wrong denominator is visible rather than '
             'merely absent. Dividing a player target mean by this value '
             'yields a share of a pool the allocator never used.'))

    # -- conservation of the receiving layer into the QB layer
    conservation = []
    if mine and qb_cmp is not None:
        rec = matrix(draws, _RECEIVING, 'receptions')[mine].sum(0)
        yds = matrix(draws, _RECEIVING, 'receiving_yards')[mine].sum(0)
        conservation.append({
            'identity': 'sum(receiving__receptions) == sum(qb__cmp)',
            'evidence': MEASURED,
            'worst_absolute_deviation': _f(np.abs(rec - qb_cmp).max()),
            'holds_on_every_draw': bool(np.abs(rec - qb_cmp).max() == 0),
            'note': 'C3 CONSTRUCTS the receiving layer out of QB completions '
                    'rather than reconciling two independent draws. The '
                    'receiving chain must therefore route through QB '
                    'attempts, not through a separately stored team total.'})
        conservation.append({
            'identity': 'sum(receiving__receiving_yards) == sum(qb__pyds)',
            'evidence': MEASURED,
            'worst_absolute_deviation': _f(np.abs(yds - qb_pyds).max()),
            'holds_on_every_draw': bool(np.abs(yds - qb_pyds).max() < 1e-9)})

    if budget is not None:
        urows = rows_of(manifest, _RUSHING)
        rb = [urows[g] for g, p in players.items()
              if p.get('team') == team and g in urows]
        if rb:
            tot = matrix(draws, _RUSHING, 'carries')[rb].sum(0)
            excess = tot - budget
            # TOLERANCE IS DECLARED, NOT CHOSEN TO MAKE IT PASS. The worst
            # excess on this board is 2.3e-06 on a budget of 25, which is one
            # part in 2**23 -- the signature of a float32 round trip somewhere
            # upstream of a float64 array, not of an allocation that overflows.
            # Claiming exact containment would be false; claiming a violation
            # would be reading a storage artefact as a modelling one.
            tol = 1e-5
            conservation.append({
                'identity': 'sum(modelled RB carries) <= designed_rush_budget',
                'evidence': MEASURED,
                'worst_excess': float(f'{excess.max():.3e}'),
                'tolerance': tol,
                'holds_exactly': bool(excess.max() <= 0.0),
                'holds_within_tolerance': bool(excess.max() <= tol),
                'draws_at_the_boundary': int((excess > -1e-9).sum()),
                'note': 'the RB *category* budget A1 drew is not persisted. '
                        'What is checked here is containment inside the whole '
                        'rush-play budget, which is weaker. It holds to 1e-5 '
                        'and NOT exactly: the overshoot is float32-scale and '
                        'is reported rather than rounded away.'})
    return {'team': team, 'links': links, 'conservation': conservation,
            'means': {'team_off_snaps': _mean(snaps),
                      'team_dropbacks': _mean(db),
                      'team_carries': _mean(carries),
                      'designed_rush_budget':
                          None if budget is None else _mean(budget),
                      'sum_modelled_targets':
                          None if sum_targets is None else _mean(sum_targets),
                      'qb_attempts': None if qb_att is None else _mean(qb_att),
                      'stored_team_targets': _mean(stored_targets)}}


# ---------------------------------------------------------------------------
# participation
# ---------------------------------------------------------------------------
def qb_participation(draws, row) -> dict:
    """For a QB, participation IS identified in the draws -- and it is checked.

    A quarterback with zero dropbacks has zero of every other quarterback
    quantity on this board. That is asserted cell by cell rather than assumed,
    because it is exactly the kind of fact that stops being true one engine
    version later and takes the conditional means with it.
    """
    db = matrix(draws, _QB, 'db')[row]
    others = [matrix(draws, _QB, k)[row]
              for k in ('att', 'cmp', 'sacks', 'scr', 'rush_opp')]
    zero_db = db == 0
    leak = int(sum(int((o[zero_db] != 0).sum()) for o in others))
    p = _f(np.mean(~zero_db))
    return {'mask': 'qb__db > 0',
            'basis': PART_IDENTIFIED if leak == 0 else PART_BOUND_ONLY,
            'basis_detail':
                'zero dropbacks implies zero of every other QB quantity on '
                'every draw cell, so the mask separates "did not play as a '
                'passer" from "played and produced nothing"'
                if leak == 0 else
                'a zero-dropback draw carried a non-zero QB quantity; the '
                'mask no longer identifies participation',
            'verified_cells_violating': leak,
            'p_participates': p,
            'p_participates_lower_bound': p,
            'p_participates_is_a_bound': leak != 0}


def nonqb_participation(draws, manifest, gsis_id) -> dict:
    """For everyone else, participation is NOT identified. Bound, and say so."""
    parts, names = [], []
    for layer, metric in ((_RECEIVING, 'targets'), (_RUSHING, 'carries')):
        rows = rows_of(manifest, layer)
        if gsis_id in rows:
            parts.append(matrix(draws, layer, metric)[rows[gsis_id]] != 0)
            names.append(f'{layer}__{metric}')
    if not parts:
        raise DecompositionInputError(
            f'NO_OPPORTUNITY_METRIC: {gsis_id} has no modelled opportunity '
            f'array, so nothing about participation can be stated')
    any_opp = np.logical_or.reduce(parts)
    lower = _f(np.mean(any_opp))
    return {'mask': ' or '.join(f'{n} > 0' for n in names),
            'basis': PART_BOUND_ONLY,
            'basis_detail':
                'the appearance probability is computed upstream and is not '
                'persisted in the sealed artifact. A player who appears and '
                'receives nothing is cell-for-cell identical to a player who '
                'did not appear, so the draws bound P(participates) from '
                'below and cannot identify it.',
            'verified_cells_violating': None,
            'p_participates': None,
            'p_participates_lower_bound': lower,
            'p_participates_is_a_bound': True}


# ---------------------------------------------------------------------------
# the five required views, computed once and identically for every chain
# ---------------------------------------------------------------------------
def views(opportunity, outcome, part_mask, participation,
          opportunity_name, outcome_name) -> dict:
    """Unconditional and conditional, with the two different zeros kept apart.

    P(zero opportunity) and P(zero outcome) are DIFFERENT EVENTS and only
    coincide when the outcome is zero exactly when the opportunity is. Both are
    persisted, because the ratio identity E[Y] = (1 - p) * E[Y | participates]
    holds for the participation mask and for no other p.
    """
    opp = None if opportunity is None else np.asarray(opportunity)
    out = None if outcome is None else np.asarray(outcome)
    identified = participation['basis'] == PART_IDENTIFIED
    nonzero_opp = None if opp is None else (opp != 0)

    e_out = None if out is None else _mean(out)
    e_out_part = None if (out is None) else _cond_mean(out, part_mask)
    p_part = participation['p_participates']
    implied = None
    if e_out is not None and e_out_part not in (None, 0):
        implied = _ratio(e_out, e_out_part)

    return {
        'opportunity_metric': opportunity_name,
        'outcome_metric': outcome_name,
        'p_participates': p_part,
        'p_participates_lower_bound':
            participation['p_participates_lower_bound'],
        'p_zero_opportunity': None if opp is None else _p_zero(opp),
        'p_zero_outcome': None if out is None else _p_zero(out),
        'zero_opportunity_and_zero_outcome_agree':
            None if (opp is None or out is None)
            else bool(np.array_equal(opp == 0, out == 0)),
        'e_opportunity': None if opp is None else _mean(opp),
        'e_opportunity_given_participates':
            None if opp is None else _cond_mean(opp, part_mask),
        'e_opportunity_given_nonzero_opportunity':
            None if opp is None else _cond_mean(opp, nonzero_opp),
        'e_outcome': e_out,
        'e_outcome_given_participates': e_out_part,
        'e_outcome_given_nonzero_opportunity':
            None if (out is None or opp is None)
            else _cond_mean(out, nonzero_opp),
        'uncond_over_cond_on_participation': implied,
        'cond_over_uncond_on_participation':
            None if (implied in (None, 0)) else _f(1.0 / implied),
        'opportunity_cond_over_uncond_on_participation': _ratio(
            _cond_mean(opp, part_mask) if opp is not None else None,
            _mean(opp) if opp is not None else None),
        'one_over_one_minus_p_zero_opportunity':
            None if opp is None or np.mean(opp == 0) >= 1.0
            else _f(1.0 / (1.0 - np.mean(opp == 0))),
        'one_over_one_minus_p_zero_outcome':
            None if out is None or np.mean(out == 0) >= 1.0
            else _f(1.0 / (1.0 - np.mean(out == 0))),
        'one_over_p_participates':
            None if p_part in (None, 0) else _f(1.0 / p_part),
        'ratio_identity_holds_against_p_participates':
            None if (implied is None or p_part in (None, 0))
            else bool(abs((1.0 / implied) - (1.0 / p_part)) < 1e-6),
        'p_zero_opportunity_equals_non_participation':
            None if opp is None else
            bool(np.array_equal(opp == 0, ~np.asarray(part_mask, dtype=bool))),
        'participating_draws_with_zero_opportunity':
            None if opp is None else
            int(((opp == 0) & np.asarray(part_mask, dtype=bool)).sum()),
        'ratio_identity_note':
            'E[Y] = P(participates) * E[Y | participates] holds exactly for '
            'the PARTICIPATION mask and for no other probability. Against '
            'P(zero OUTCOME) it is off by the draws where a participating '
            'player produced a zero; against P(zero OPPORTUNITY) it is off by '
            'the draws where a participating player drew no opportunity -- on '
            'this board, backup quarterbacks who were sacked or scrambled '
            'without attempting a pass.',
        'one_minus_p_zero_outcome':
            None if out is None else _f(1.0 - np.mean(out == 0)),
        'conditional_is_identified': identified,
        'conditional_caveat':
            None if identified else
            'participation is not identified in the artifact, so every '
            '"| participates" figure here is conditioned on the LOWER-BOUND '
            'mask (any modelled opportunity > 0). It is an upper bound on the '
            'true conditional mean, because it drops the appear-and-receive-'
            'nothing draws that belong in the denominator.'}


# ---------------------------------------------------------------------------
# the three chains
# ---------------------------------------------------------------------------
def qb_passing_chain(board, manifest, draws, gsis_id, team, tchain) -> dict:
    row = rows_of(manifest, _QB)[gsis_id]
    db = matrix(draws, _QB, 'db')[row]
    att = matrix(draws, _QB, 'att')[row]
    cmp_ = matrix(draws, _QB, 'cmp')[row]
    sacks = matrix(draws, _QB, 'sacks')[row]
    scr = matrix(draws, _QB, 'scr')[row]
    pyds = matrix(draws, _QB, 'pyds')[row]
    part = qb_participation(draws, row)
    mask = db > 0
    tm = tchain['means']

    ident = np.abs(db - (att + sacks + scr))
    links = [
        _link('team_plays', MEASURED, tm['team_off_snaps'],
              array='team_volume__team_off_snaps'),
        _link('team_dropbacks', MEASURED, tm['team_dropbacks'],
              array='team_volume__team_dropbacks_part'),
        _ratio_link('QB participation/share of team dropbacks',
                    f'qb__db[{gsis_id}]', float(np.mean(db)),
                    'team_dropbacks_part', tm['team_dropbacks']),
        _link('QB dropbacks', MEASURED, _mean(db), array='qb__db'),
        _link('dropbacks -> attempts', MEASURED, _mean(att),
              identity='qb__db == qb__att + qb__sacks + qb__scr',
              holds_on_every_draw=bool(ident.max() == 0),
              worst_absolute_deviation=_f(ident.max()),
              array='qb__att',
              note='an exact per-draw identity in the stored artifact, so the '
                   'attempt link is measured rather than reconstructed'),
        _link('completions', MEASURED, _mean(cmp_), array='qb__cmp'),
        _ratio_link('completion rate = completions / attempts',
                    'qb__cmp', float(np.mean(cmp_)),
                    'qb__att', float(np.mean(att))),
        _link('passing yards', MEASURED, _mean(pyds), array='qb__pyds'),
        _ratio_link('yards per completion = passing yards / completions',
                    'qb__pyds', float(np.mean(pyds)),
                    'qb__cmp', float(np.mean(cmp_))),
    ]
    return {'chain': 'QB_PASSING', 'links': links, 'participation': part,
            'views': views(att, pyds, mask, part, 'qb__att', 'qb__pyds'),
            'absences': []}


def qb_rushing_chain(manifest, draws, gsis_id) -> dict:
    """Beyond the three requested chains, and recorded because the asymmetry
    matters: QB rushing yards ARE modelled while RB rushing yards are not."""
    row = rows_of(manifest, _QB)[gsis_id]
    db = matrix(draws, _QB, 'db')[row]
    opp = matrix(draws, _QB, 'rush_opp')[row]
    yds = matrix(draws, _QB, 'ryds')[row]
    part = qb_participation(draws, row)
    links = [
        _link('QB rush opportunities', MEASURED, _mean(opp),
              array='qb__rush_opp'),
        _link('QB rushing yards', MEASURED, _mean(yds), array='qb__ryds',
              note='the QB layer HAS a carry->yards conversion. The non-QB '
                   'layer does not. Same board, two different answers to the '
                   'same modelling question.'),
        _ratio_link('yards per rush opportunity', 'qb__ryds',
                    float(np.mean(yds)), 'qb__rush_opp', float(np.mean(opp))),
    ]
    return {'chain': 'QB_RUSHING', 'links': links, 'participation': part,
            'views': views(opp, yds, db > 0, part,
                           'qb__rush_opp', 'qb__ryds'),
            'absences': []}


def rb_rushing_chain(manifest, draws, gsis_id, tchain) -> dict:
    row = rows_of(manifest, _RUSHING)[gsis_id]
    carries = matrix(draws, _RUSHING, 'carries')[row]
    part = nonqb_participation(draws, manifest, gsis_id)
    parts = []
    for layer, metric in ((_RECEIVING, 'targets'), (_RUSHING, 'carries')):
        rws = rows_of(manifest, layer)
        if gsis_id in rws:
            parts.append(matrix(draws, layer, metric)[rws[gsis_id]] != 0)
    mask = np.logical_or.reduce(parts)
    tm = tchain['means']

    links = [
        _link('team_plays', MEASURED, tm['team_off_snaps'],
              array='team_volume__team_off_snaps'),
        _link('team_carries', MEASURED, tm['team_carries'],
              array='team_volume__team_carries'),
        _link('designed_rush_budget = rint(team_carries) - sum(QB scrambles)',
              DIFFERENCED, tm['designed_rush_budget']),
        _link('designed_rush_budget -> RB carry budget', ABSENT, None,
              code='RB_CATEGORY_BUDGET_NOT_PERSISTED',
              substitute='sum of the modelled RBs\' carries',
              substitute_value=tchain.get('_rb_pool'),
              why_honest='A1 partitions the rush-play budget across six named '
                         'categories and the rb category total is a real '
                         'quantity the engine computed, but it is not written '
                         'into the artifact. The sum over modelled RBs is a '
                         'LOWER BOUND on it: any carry A1 gave the rb '
                         'category that landed on an unmodelled back is '
                         'missing from the sum and from nothing else.'),
        _ratio_link('RB share of the modelled RB pool',
                    f'rushing__carries[{gsis_id}]', float(np.mean(carries)),
                    'sum(modelled RB carries)', tchain.get('_rb_pool')),
        _ratio_link('RB share of team_carries',
                    f'rushing__carries[{gsis_id}]', float(np.mean(carries)),
                    'team_volume__team_carries', tm['team_carries'],
                    note='the second denominator, persisted beside the first '
                         'so a share can never be quoted without saying what '
                         'it is a share OF'),
        _link('carries', MEASURED, _mean(carries), array='rushing__carries',
              non_integer_draw_cells=int((carries != np.rint(carries)).sum()),
              note='stored as float64 and fractional in most cells: these are '
                   'allocated carry mass under the P4C simplex, not integer '
                   'carries. A threshold read off them is reading a '
                   'continuous quantity.'),
        _link('carries -> rushing yards', ABSENT, None,
              code='RUSHING_CONVERSION_CONTROL_UNDEFINED',
              substitute=None,
              why_honest='the board declares this metric UNAVAILABLE and '
                         'names carries x yards-per-carry as the PROHIBITED '
                         'implementation. There is no substitute, so none is '
                         'offered; the chain terminates at carries and the '
                         'outcome view is null rather than invented.'),
    ]
    absences = [l for l in links if l['evidence'] == ABSENT]
    return {'chain': 'RB_RUSHING', 'links': links, 'participation': part,
            'views': views(carries, None, mask, part,
                           'rushing__carries', None),
            'absences': [{'code': a['code'], 'step': a['step']}
                         for a in absences]}


def receiving_chain(manifest, draws, gsis_id, tchain) -> dict:
    row = rows_of(manifest, _RECEIVING)[gsis_id]
    tgt = matrix(draws, _RECEIVING, 'targets')[row]
    rec = matrix(draws, _RECEIVING, 'receptions')[row]
    yds = matrix(draws, _RECEIVING, 'receiving_yards')[row]
    part = nonqb_participation(draws, manifest, gsis_id)
    parts = []
    for layer, metric in ((_RECEIVING, 'targets'), (_RUSHING, 'carries')):
        rws = rows_of(manifest, layer)
        if gsis_id in rws:
            parts.append(matrix(draws, layer, metric)[rws[gsis_id]] != 0)
    mask = np.logical_or.reduce(parts)
    tm = tchain['means']

    links = [
        _link('team_dropbacks', MEASURED, tm['team_dropbacks'],
              array='team_volume__team_dropbacks_part'),
        _link('team_dropbacks -> routes run', ABSENT, None,
              code='NO_ROUTES_LAYER',
              substitute='pass-snap participation share '
                         '(participation-s2-ewma_hl2)',
              substitute_value=None,
              why_honest='V1 has no routes layer anywhere. The engine\'s own '
                         'stand-in is pass_snaps / team_dropbacks, which '
                         'nfl/production/nonqb/layers.py names as an UPPER '
                         'BOUND on routes run with an unbounded gap -- and it '
                         'is not persisted into this artifact either, so the '
                         'proxy cannot even be quoted here. It is named as a '
                         'proxy and left null rather than back-solved from '
                         'targets, which would only re-derive the target '
                         'share it is supposed to explain.'),
        _link('QB attempts (the real allocation pool)', MEASURED,
              tm['qb_attempts'],
              note='C3 constructs receptions out of QB completions, so the '
                   'receiving chain routes through the QB layer'),
        _link('sum of modelled player targets (the allocation denominator)',
              SUMMED, tm['sum_modelled_targets']),
        _link('stored team_volume__team_targets', MEASURED,
              tm['stored_team_targets'],
              is_the_allocation_denominator=False,
              code='WS09_J12_STORED_TEAM_TARGETS_IS_NOT_THE_DENOMINATOR'),
        _ratio_link('target share of the modelled target pool',
                    f'receiving__targets[{gsis_id}]', float(np.mean(tgt)),
                    'sum(modelled targets)', tm['sum_modelled_targets']),
        _ratio_link('target share if the stored team total were used (WRONG)',
                    f'receiving__targets[{gsis_id}]', float(np.mean(tgt)),
                    'team_volume__team_targets', tm['stored_team_targets'],
                    note='persisted only so the size of the error is visible. '
                         'This is not the share; it is what the share becomes '
                         'when the denominator is taken from the wrong place.'),
        _link('targets', MEASURED, _mean(tgt), array='receiving__targets'),
        _link('receptions', MEASURED, _mean(rec), array='receiving__receptions',
              cells_with_receptions_above_targets=int((rec > tgt).sum())),
        _ratio_link('catch probability = receptions / targets',
                    'receiving__receptions', float(np.mean(rec)),
                    'receiving__targets', float(np.mean(tgt))),
        _link('receiving yards', MEASURED, _mean(yds),
              array='receiving__receiving_yards',
              cells_with_yards_and_no_reception=int(((yds != 0) &
                                                     (rec == 0)).sum())),
        _ratio_link('yards per reception = receiving yards / receptions',
                    'receiving__receiving_yards', float(np.mean(yds)),
                    'receiving__receptions', float(np.mean(rec))),
    ]
    absences = [l for l in links if l['evidence'] == ABSENT]
    return {'chain': 'RECEIVING', 'links': links, 'participation': part,
            'views': views(tgt, yds, mask, part,
                           'receiving__targets',
                           'receiving__receiving_yards'),
            'absences': [{'code': a['code'], 'step': a['step']}
                         for a in absences]}


# ---------------------------------------------------------------------------
# top level
# ---------------------------------------------------------------------------
def decompose(board_dir) -> Outcome:
    """The whole board, decomposed. PASS with an artifact, or a named refusal."""
    try:
        board, manifest, draws = load(board_dir)
    except DecompositionInputError as exc:
        return Outcome.blocked('DECOMPOSITION_INPUT_UNREADABLE', str(exc),
                               cause=Cause.DATA, board_dir=str(board_dir))
    teams = board.get('teams') or []
    if not teams:
        return Outcome.fail('BOARD_DECLARES_NO_TEAMS',
                            'a board with no teams cannot be decomposed')
    if isinstance(teams, dict):
        teams = list(teams)
    players = team_of_player(board)
    states = team_layer_states(board, manifest, teams)

    tchains = {}
    for t in teams:
        tc = team_chain(board, manifest, draws, t)
        urows = rows_of(manifest, _RUSHING)
        mine = [urows[g] for g, p in players.items()
                if p.get('team') == t and g in urows]
        tc['_rb_pool'] = (_mean(matrix(draws, _RUSHING, 'carries')[mine].sum(0))
                          if mine else None)
        tchains[t] = tc

    qb_rows = rows_of(manifest, _QB)
    rc_rows = rows_of(manifest, _RECEIVING)
    ru_rows = rows_of(manifest, _RUSHING)

    out_players = []
    for gid, p in sorted(players.items()):
        team = p.get('team')
        tc = tchains.get(team)
        if tc is None:
            continue
        chains = []
        if gid in qb_rows:
            chains.append(qb_passing_chain(board, manifest, draws, gid,
                                           team, tc))
            chains.append(qb_rushing_chain(manifest, draws, gid))
        if gid in ru_rows:
            chains.append(rb_rushing_chain(manifest, draws, gid, tc))
        if gid in rc_rows:
            chains.append(receiving_chain(manifest, draws, gid, tc))
        if not chains:
            chains = [{'chain': 'NONE', 'links': [], 'participation': None,
                       'views': None,
                       'absences': [{'code': 'PLAYER_HAS_NO_DRAW_ROW',
                                     'step': 'board row without a draw row'}]}]
        out_players.append({'gsis_id': gid, 'team': team,
                            'position': p.get('position'),
                            'depth_chart': p.get('depth_chart'),
                            'chains': chains})
    if not out_players:
        return Outcome.fail(
            'DECOMPOSITION_EMPTY',
            'no player produced a chain. An empty decomposition is an error, '
            'not a result.')

    for tc in tchains.values():
        tc.pop('_rb_pool', None)

    art = {
        'contract_version': CONTRACT,
        'board_dir': str(board_dir),
        'game_id': board.get('game_id'),
        'run_id': board.get('run_id'),
        'n_draws': board.get('n_draws'),
        'code_commit': board.get('code_commit'),
        'model_configuration': board.get('model_configuration'),
        'changes_no_model': True,
        'teams': teams,
        'team_layer_states': states,
        'team_chains': tchains,
        'players': out_players,
        'evidence_grades': {
            MEASURED: 'both sides are stored draw matrices and the relation '
                      'was checked on every draw cell',
            SUMMED: 'a total formed by summing stored matrices',
            DIFFERENCED: 'formed by subtracting stored matrices',
            DIVIDED: 'a rate obtained by division; reproduces itself by '
                     'construction and is not independent evidence',
            ABSENT: 'the engine has no such quantity; a substitute, if any, '
                    'is named with its direction of error'},
    }
    return Outcome.ok('DECOMPOSITION_OK', value=art,
                      n_players=len(out_players), n_teams=len(teams),
                      contract=CONTRACT)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print('usage: decomposition.py <sealed_board_dir>', file=sys.stderr)
        return 2
    res = decompose(argv[0])
    if res.state is not State.PASS:
        print(str(res), file=sys.stderr)
        return 1
    print(json.dumps(res.value, indent=1, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
