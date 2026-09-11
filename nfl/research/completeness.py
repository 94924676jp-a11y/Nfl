"""What a sealed board ACTUALLY modelled, computed from its distributions.

WHY THIS EXISTS.

The slate runner reported "12 games complete / 0 blocked" for the 2026-09-13
slate. Every one of those twelve boards had sealed successfully AND carried
only the quarterback layer: six to nine players, no rushing, no receiving, no
touchdown allocation, because BUF, HOU and ten other clubs had filed injury
rows with report_status unset and the appearance layer correctly deferred.
Orchestration had succeeded completely. The football forecast had not.

So a board sealing says nothing about whether the forecast is usable, and the
two must be reported as INDEPENDENT states. Nothing here is read from prose or
from a status string: every verdict below is computed from whether a declared
layer produced a valid stored distribution for at least one player.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'forecast-completeness-1'

EXECUTION_STATES = ('EXECUTED', 'REUSED')          # plus BLOCKED_<REASON>
COMPLETENESS = ('FULL', 'PARTIAL', 'QB_ONLY', 'NO_USABLE_FORECAST')

# The nine declared layers, each mapped to the metric whose distribution
# proves it ran. A layer is PASS only if a real distribution exists.
LAYERS = (
    ('team_volume', ('team_volume/team_off_snaps',
                     'team_volume/team_dropbacks_part')),
    ('qb_attempts', ('qb/att',)),
    ('qb_passing_yards', ('qb/pyds',)),
    ('qb_td', ('qb/ptd',)),
    ('carries', ('rushing/carries',)),
    ('targets', ('receiving/targets',)),
    ('receptions', ('receiving/receptions',)),
    ('receiving_yards', ('receiving/receiving_yards',)),
    ('td_allocation', ('receiving/receiving_td', 'rushing/rushing_td')),
)
LAYER_NAMES = tuple(n for n, _ in LAYERS)

QB_LAYERS = ('qb_attempts', 'qb_passing_yards', 'qb_td')
NONQB_LAYERS = ('carries', 'targets', 'receptions', 'receiving_yards',
                'td_allocation')

# A market may be ranked only when the layers it causally depends on are all
# PASS. Passing yards does not need the carry allocation; receiving yards
# needs targets AND receptions AND its own conversion.
MARKET_REQUIRES = {
    'qb/att': ('team_volume', 'qb_attempts'),
    'qb/cmp': ('team_volume', 'qb_attempts'),
    'qb/pyds': ('team_volume', 'qb_attempts', 'qb_passing_yards'),
    'qb/ptd': ('team_volume', 'qb_attempts', 'qb_td'),
    'rushing/carries': ('team_volume', 'carries'),
    'rushing/rushing_td': ('team_volume', 'carries', 'td_allocation'),
    'receiving/targets': ('team_volume', 'targets'),
    'receiving/receptions': ('team_volume', 'targets', 'receptions'),
    'receiving/receiving_yards': ('team_volume', 'targets', 'receptions',
                                  'receiving_yards'),
    'receiving/receiving_td': ('team_volume', 'targets', 'receptions',
                              'td_allocation'),
}


def _has_distribution(draws, manifest, metric):
    """True when at least one row of `metric` carries a real distribution.

    An all-zero or constant row is NOT a distribution: it is the absence of
    one wearing the right shape. That distinction is the whole point here.
    """
    if draws is None or manifest is None:
        return False, 'no stored draws'
    lay = metric.split('/')[0]
    info = (manifest.get('layers') or {}).get(lay) or {}
    ids = info.get('row_ids') or []
    key = metric.replace('/', '__')
    if key not in draws or not ids:
        return False, 'metric absent from the stored draw set'
    arr = np.asarray(draws[key], float)
    if arr.size == 0:
        return False, 'stored draw array is empty'
    n = min(arr.shape[0], len(ids))
    for i in range(n):
        row = arr[i]
        if row.size and float(np.max(row)) > 0.0 and float(np.std(row)) > 0.0:
            return True, None
    return False, 'every stored row is constant or zero'


def _absent_reason(board, layer):
    """Why a layer is missing, taken from the board's own refusal record.

    The board already names what it did not reach -- ABSENT in its
    eligibility verdict, `not_reached` in its component manifest, and the
    readiness reason behind the appearance refusal. This reads those rather
    than inventing a reason, and says UNSTATED when the board does not say.
    """
    ev = str(board.get('eligibility_verdict') or '')
    absent = set()
    if 'ABSENT:' in ev:
        absent = {x for x in ev.split('ABSENT:')[1].split('|')[0].split(',')
                  if x}
    stage_for = {
        'carries': 'targets_carries', 'targets': 'targets_carries',
        'receptions': 'conversion', 'receiving_yards': 'conversion',
        'td_allocation': 'td_layer',
    }
    stage = stage_for.get(layer)
    if stage and stage in absent:
        # The appearance layer is the usual root: when it defers, everything
        # downstream is blocked upstream rather than independently broken.
        if 'appearance' in absent:
            rd = (board.get('readiness') or {})
            reasons = {str(v.get('state')) for v in rd.values()
                       if isinstance(v, dict) and v.get('state')}
            named = sorted(r for r in reasons if not r.startswith('READY'))
            if named:
                return f'DEFERRED_{named[0]}'
            return 'DEFERRED_APPEARANCE_NOT_PRODUCED'
        return f'DEFERRED_{stage.upper()}_NOT_PRODUCED'
    if stage:
        return 'BLOCKED_NO_DISTRIBUTION_DESPITE_STAGE_REPORTED'
    return 'NOT_MODELED'


def layer_matrix(board, manifest, draws):
    """{layer: PASS | DEFERRED_<REASON> | BLOCKED_<REASON> | NOT_MODELED}."""
    out = {}
    for layer, metrics in LAYERS:
        ok = False
        for m in metrics:
            good, _why = _has_distribution(draws, manifest, m)
            if good:
                ok = True
                break
        out[layer] = 'PASS' if ok else _absent_reason(board, layer)
    return out


def forecast_completeness(matrix):
    """FULL / PARTIAL / QB_ONLY / NO_USABLE_FORECAST, from the matrix alone.

    QB_ONLY is its own state rather than a flavour of PARTIAL because it is
    the state the whole slate was actually in while being reported complete,
    and a reader needs to see it at a glance.
    """
    ok = {k for k, v in matrix.items() if v == 'PASS'}
    qb_ok = [l for l in QB_LAYERS if l in ok]
    non_ok = [l for l in NONQB_LAYERS if l in ok]
    if not qb_ok and not non_ok:
        return 'NO_USABLE_FORECAST'
    if len(ok) == len(LAYER_NAMES):
        return 'FULL'
    if qb_ok and not non_ok:
        return 'QB_ONLY'
    return 'PARTIAL'


def market_rankable(metric, matrix):
    """(bool, [layers that are not PASS]) for one market against one matrix.

    Completeness is NOT binary per game: a quarterback's passing yards can be
    rankable in a game whose carry allocation never ran, because the causal
    path behind that market is intact. Each market is judged on its own path.
    """
    need = MARKET_REQUIRES.get(metric)
    if need is None:
        return False, ['MARKET_HAS_NO_DECLARED_CAUSAL_PATH']
    bad = [l for l in need if matrix.get(l) != 'PASS']
    return (not bad), bad


def summarise(per_game):
    """Slate-level counts. Never a single complete/blocked pair."""
    c = {k: 0 for k in COMPLETENESS}
    for g in per_game.values():
        c[g['forecast_completeness']] = c.get(
            g['forecast_completeness'], 0) + 1
    awaiting_injury = sum(
        1 for g in per_game.values()
        if any(str(v).startswith('DEFERRED_INJURY')
               for v in (g.get('layer_matrix') or {}).values()))
    return {
        'games_fully_modeled': c['FULL'],
        'games_partially_modeled': c['PARTIAL'],
        'games_qb_only': c['QB_ONLY'],
        'games_unusable': c['NO_USABLE_FORECAST'],
        'games_awaiting_injury_information': awaiting_injury,
    }
