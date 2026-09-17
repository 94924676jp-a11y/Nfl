"""The MATHEMATICAL support of every emitted array, declared rather than sniffed.

WHY THIS IS NOT `metrics.SUPPORTED`. That registry is the PUBLICATION contract:
17 entries, each with a label and a status, describing what appears on a board.
The engine emits 54 matrices. Adding the other 37 to `SUPPORTED` would change
what boards publish, which is a production change and not a classification one.
So this is a second, disjoint-purpose registry, and `test_support_kinds`
asserts the two never disagree about the 17 they share.

WHY DECLARED AND NOT INFERRED. `draw_coherence.py` already records why the
stored dtype is useless: `rushing/carries` is int-typed nowhere and `qb/pyds`
is float and declared yards. Cardinality is worse -- a quantity would change
contract when the draw count changed. Support is a property of the QUANTITY.

THE TWO FIELDS, AND THE GAP BETWEEN THEM IS THE POINT
  `kind`     what the quantity IS, mathematically.
  `emitted`  what the engine CURRENTLY produces.

Where they disagree, that disagreement IS the support defect, declared in data
instead of prose. `qb/pyds` is `yards` -- realised passing yards are integers --
and is emitted `continuous`, because `credit_passing_line` splits a team total
by a continuous completion share. Three arrays are in that state and they are
listed by `discrepancies()`, not buried in a comment.
"""
from __future__ import annotations

#: Integer-valued, non-negative. A negative count is impossible.
COUNT = 'count'
#: Integer-valued in reality, and SIGNED: a carry or catch for a loss is
#: ordinary football. `draw_coherence` declares 2,261 negative `qb/pyds`,
#: 2,821 `qb/ryds` and 8,213 `receiving/receiving_yards` cells lawful.
YARDS = 'yards'
#: A fixed rational grid. DraftKings scoring is a weighted sum of counts and
#: yards, so its step is determined by the coefficients, not chosen.
LATTICE = 'lattice'
#: Genuinely continuous, never rounded at source, and rounded by CONSUMERS.
CONTINUOUS_LEVEL = 'continuous_level'
#: Bounded to [0, 1].
PROBABILITY = 'probability'

KINDS = (COUNT, YARDS, LATTICE, CONTINUOUS_LEVEL, PROBABILITY)

INTEGER = 'integer'
CONTINUOUS = 'continuous'

_C = {'kind': COUNT, 'emitted': INTEGER}
_Y_INT = {'kind': YARDS, 'emitted': INTEGER}
#: Declared support is integer; the engine emits a continuous share. The gap is
#: the defect pre-registered in nfl/research/qb_yards/.
_Y_CONT = {'kind': YARDS, 'emitted': CONTINUOUS,
           'defect': 'QB_YARDS_CONTINUOUS_SHARE'}

EMITTED_KINDS = {
    # ---- counts -------------------------------------------------------
    'gadget_rush/kneel': _C, 'gadget_rush/te': _C, 'gadget_rush/wr': _C,
    'kicking/att_FG<20': _C, 'kicking/att_FG20s': _C, 'kicking/att_FG30s': _C,
    'kicking/att_FG40s': _C, 'kicking/att_FG50+': _C,
    'kicking/made_FG<20': _C, 'kicking/made_FG20s': _C,
    'kicking/made_FG30s': _C, 'kicking/made_FG40s': _C,
    'kicking/made_FG50+': _C,
    'kicking/fga': _C, 'kicking/fgm': _C, 'kicking/xpa': _C, 'kicking/xpm': _C,
    # NOT a kicker metric: the TEAM's offensive touchdowns in that draw,
    # carried on his row as the INPUT his model was conditioned on.
    'kicking/offensive_td': {'kind': COUNT, 'emitted': INTEGER,
                             'note': 'team input on the kicker row, not his '
                                     'production'},
    'qb/att': _C, 'qb/cmp': _C, 'qb/db': _C, 'qb/int': _C, 'qb/ptd': _C,
    'qb/rtd': _C, 'qb/rush_opp': _C, 'qb/sacks': _C, 'qb/scr': _C,
    'receiving/receiving_td': _C, 'receiving/receptions': _C,
    'receiving/targets': _C,
    'rush_category/designed_qb': _C, 'rush_category/fringe': _C,
    'rush_category/kneel': _C, 'rush_category/rb': _C,
    'rush_category/te': _C, 'rush_category/wr': _C,
    'rush_player_pool/unmodelled_back_pool': _C,
    'rushing/carries': _C, 'rushing/rushing_td': _C,
    # team_off_snaps is the ONLY team_volume array that is genuinely a count.
    # Measured across 112 sealed boards: integer on 112 of 112.
    'team_volume/team_off_snaps': _C,
    # ---- yards, signed integers ---------------------------------------
    'gadget_rush/kneel_yards': _Y_INT, 'gadget_rush/te_yards': _Y_INT,
    'gadget_rush/wr_yards': _Y_INT,
    'receiving/receiving_yards': _Y_INT, 'rushing/rushing_yards': _Y_INT,
    'qb/pyds': _Y_CONT, 'qb/ryds': _Y_CONT,
    'rushing_total/rushing_yards': {
        'kind': YARDS, 'emitted': CONTINUOUS,
        'defect': 'QB_YARDS_CONTINUOUS_SHARE',
        'note': 'inherits qb/ryds; repaired by the same change'},
    # ---- lattice ------------------------------------------------------
    'dk_scoring/dk_points': {
        'kind': LATTICE, 'emitted': CONTINUOUS,
        'defect': 'QB_YARDS_CONTINUOUS_SHARE',
        'note': 'a weighted sum of counts and yards; it returns to its lattice '
                'once QB yards are integral'},
    'kicking/dk_points': {'kind': LATTICE, 'emitted': INTEGER,
                          'note': 'made kicks only, so already on its grid'},
    # ---- continuous team levels, and they are NOT counts ---------------
    # 100% non-integer BY DESIGN. Consumers `rint` them. Scoring either as a
    # count would apply a discrete instrument to a continuous quantity.
    'team_volume/team_dropbacks_part': {'kind': CONTINUOUS_LEVEL,
                                        'emitted': CONTINUOUS},
    'team_volume/team_rz_carries': {'kind': CONTINUOUS_LEVEL,
                                    'emitted': CONTINUOUS},
    # I DECLARED THESE TWO COUNTS AND WAS WRONG, on one board's evidence.
    # Measured across 112 sealed boards: `team_carries` and `team_targets` are
    # all-integer on 3 of 112 -- the three DET-BUF C3 boards, where C3 consumed
    # and re-emitted a rinted level. Everywhere else they carry fractions, like
    # the two levels above. FOUR of the five team_volume arrays are continuous
    # levels that consumers `rint`; only `team_off_snaps` is a count.
    'team_volume/team_carries': {'kind': CONTINUOUS_LEVEL,
                                 'emitted': CONTINUOUS,
                                 'note': 'integer on 3 of 112 sealed boards'},
    'team_volume/team_targets': {'kind': CONTINUOUS_LEVEL,
                                 'emitted': CONTINUOUS,
                                 'note': 'integer on 3 of 112 sealed boards'},
}


def kind_of(key: str):
    """The declared kind, or None. NEVER guessed from dtype or cardinality."""
    e = EMITTED_KINDS.get(key)
    return e['kind'] if e else None


def unclassified(keys):
    """Emitted arrays with no declared kind. Contract 4 counts these against
    its coverage rather than guessing them."""
    return sorted(k for k in keys if k not in EMITTED_KINDS)


def discrepancies():
    """Arrays whose emitted form does not match their mathematical support.

    Returned as data so a contract can read the defect rather than a reader
    having to know it.
    """
    return sorted(k for k, v in EMITTED_KINDS.items()
                  if v['kind'] in (YARDS, LATTICE)
                  and v['emitted'] == CONTINUOUS)


def by_kind(kind: str):
    return sorted(k for k, v in EMITTED_KINDS.items() if v['kind'] == kind)
