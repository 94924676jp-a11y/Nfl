"""Phases 4 and 5: the frozen Hard Rock main lines against what happened.

WHAT IS BEING GRADED, AND WHAT IS NOT

  GRADED      the 43 main lines the sealed board could price, each one a
              statement the model made before kickoff and cannot revise.
  NOT GRADED  the 35 rows the model could not price -- kicking, longest-play
              markets, anytime touchdowns, the two game-line markets, and the
              two players outside the model universe. They are listed with
              their reason. A market the model refused to price is not a
              market the model got right.

THE CARD (Phase 5). There is no staked card. Nothing was wagered on this
game, no accepted price exists, and section 8 of the pre-kickoff export
carried an explicit `None of this is an edge claim`. What does exist is an
ordering: the supported lines sorted by |model - market|. This file grades the
top ten of that ordering as `CARD_AS_ORDERED`, and reports ROI, closing-line
value and realised performance as NOT_AVAILABLE -- because there were no
prices accepted and no second player-prop vintage was ever captured, not
because they were inconvenient.

STANDARD ERRORS ARE REFUSED. 43 lines drawn from fourteen players in ONE game
are not 43 independent observations: every line on a player moves with that
player, and every player moves with the game. A naive binomial SE on 43 would
understate the uncertainty roughly threefold, which is the measured factor on
this project's prop grading. The cluster counts are carried instead, and the
hit rates are descriptive.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.postgame import outcome as OC                                 # noqa: E402
from nfl.dfs.showdown import universe as UNI                           # noqa: E402

SPEC_VERSION = 'nfl-postgame-grade-props-1'

BOARD = _REPO / 'nfl/research/market/DET_BUF_2026W2/MAIN_LINE_BOARD.csv'
VINTAGES = _REPO / ('nfl/research/market/DET_BUF_2026W2_VINTAGES/'
                    'MARKET_VINTAGES.json')
SUPPORTED = 'EXACT_MODEL_SUPPORTED'
CARD_N = 10

#: market name -> the outcome stat keys that sum to it. Explicit and total:
#: a market absent from this table is NOT graded, rather than guessed at.
MARKET_STATS = {
    'Player Passing Attempts': ('pass_att',),
    'Player Passing Completions': ('pass_cmp',),
    'Player Passing Yards': ('pass_yards',),
    'Player Passing Touchdowns': ('pass_td',),
    'Player Interceptions': ('interceptions',),
    'Player Rushing Attempts': ('rush_att',),
    'Player Rushing Yards': ('rush_yards',),
    'Player Receptions': ('receptions',),
    'Player Receiving Yards': ('rec_yards',),
    'Player Rushing + Receiving Yards': ('rush_yards', 'rec_yards'),
}

#: Bands on the probability the model gave ITS OWN side. A band is a reporting
#: bucket, never a threshold anything is selected on.
BANDS = ((0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.01))

NO_SE = ('REFUSED: 43 lines over fourteen players in one game are not 43 '
         'independent observations. Naive binomial SEs understate prop '
         'grading uncertainty roughly threefold on this project. Cluster '
         'counts are reported instead.')


def _band(p: float) -> str:
    for lo, hi in BANDS:
        if lo <= p < hi:
            return f'{lo:.2f}-{min(hi, 1.0):.2f}'
    return 'BELOW_0.50'


def _f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _rows() -> Outcome:
    claim = AC.verify(BOARD, schema=['player', 'market', 'line',
                                     'model_p_over', 'market_novig_p_over',
                                     'support_status', 'push_rule'],
                      label='frozen main-line board')
    if claim.state is not State.PASS:
        return claim
    with BOARD.open() as fh:
        rows = list(csv.DictReader(fh))
    return Outcome.ok('BOARD_LOADED', value=rows,
                      detail=f'{len(rows)} main line(s)',
                      sha256=claim.evidence['sha256'])


def grade(outcome_path=None) -> Outcome:
    got = OC.require(outcome_path)
    if got.state is not State.PASS:
        return got
    result = got.value
    board = _rows()
    if board.state is not State.PASS:
        return board
    actual_by_name = {UNI.norm(k): v for k, v in result['players'].items()}
    # AND BY IDENTITY, BECAUSE THE BOARD CARRIES ONE.
    #
    # MAIN_LINE_BOARD.csv has a `gsis_id` column (29th), and the outcome rows
    # carry `player_id`. This graded by normalised name anyway, so a player
    # whose board spelling and stat-feed spelling disagree was reported
    # PLAYER_NOT_IN_OUTCOME while both artifacts held the same id.
    #
    # The refusal was at least honest -- unlike grade_projections, which fell
    # through to a zero line and called it GRADED (DEF-063) -- but it is a
    # refusal that need not happen. `actual_dk` in grade_portfolios documents
    # the exact spellings that bite: 'James Cook III' against 'James Cook',
    # 'Joshua Palmer' against 'Josh Palmer'.
    #
    # grade_portfolios keeps its name join, and that one IS forced: the
    # PORTFOLIO csv is DraftKings entry format and carries no id at all.
    actual_by_id = {}
    for _nm, _v in result['players'].items():
        _pid = (_v or {}).get('player_id')
        if _pid:
            actual_by_id.setdefault(_pid, _v)

    graded, not_graded = [], []
    for r in board.value:
        base = {'player': r['player'], 'market': r['market'],
                'line': _f(r['line']), 'team': r['team'],
                'support_status': r['support_status']}
        if r['support_status'] != SUPPORTED:
            not_graded.append({**base, 'reason': r['support_status']})
            continue
        stats = MARKET_STATS.get(r['market'])
        if stats is None:
            not_graded.append({**base, 'reason': 'MARKET_NOT_IN_STAT_MAP'})
            continue
        a = (actual_by_id.get((r.get('gsis_id') or '').strip())
             or actual_by_name.get(UNI.norm(r['player'])))
        if a is None:
            not_graded.append({**base, 'reason': 'PLAYER_NOT_IN_OUTCOME',
                               'gsis_id': r.get('gsis_id') or None})
            continue
        missing = [s for s in stats if a.get(s) is None]
        if missing:
            not_graded.append({**base,
                               'reason': f'STAT_NOT_IN_OUTCOME:{",".join(missing)}'})
            continue
        line = _f(r['line'])
        if line is None or abs(line * 2 - round(line * 2)) > 1e-9:
            not_graded.append({**base, 'reason': 'LINE_NOT_READABLE'})
            continue
        if float(line).is_integer():
            # Every row on this board is a half-point line with push_rule
            # "no push". A whole number would need a push rule this file does
            # not encode, so it refuses rather than guessing which way a tie
            # settles.
            not_graded.append({**base, 'reason': 'PUSH_RULE_NOT_ENCODED'})
            continue
        act = sum(float(a[s]) for s in stats)
        settled = 'OVER' if act > line else 'UNDER'
        p_over = _f(r['model_p_over'])
        mkt_over = _f(r['market_novig_p_over'])
        if p_over is None or mkt_over is None:
            not_graded.append({**base, 'reason': 'PROBABILITY_MISSING'})
            continue
        model_side = ('NO_SIDE' if abs(p_over - 0.5) < 1e-12
                      else ('OVER' if p_over > 0.5 else 'UNDER'))
        p_model_side = max(p_over, 1.0 - p_over)
        diff = p_over - mkt_over
        lean = ('NO_LEAN' if abs(diff) < 1e-12
                else ('OVER' if diff > 0 else 'UNDER'))
        graded.append({
            **base, 'actual': act, 'settled': settled,
            'model_p_over': p_over, 'market_novig_p_over': mkt_over,
            'model_side': model_side, 'model_p_own_side': p_model_side,
            'band': _band(p_model_side),
            'model_correct': (None if model_side == 'NO_SIDE'
                              else model_side == settled),
            'model_minus_market': diff,
            'lean_vs_market': lean,
            'lean_correct': (None if lean == 'NO_LEAN' else lean == settled),
            'confidence_tag': UNI.confidence_tag(r['player']),
        })

    def _rate(sel, key='model_correct'):
        d = [g for g in sel if g.get(key) is not None]
        n = len(d)
        h = sum(1 for g in d if g[key])
        return {'n': n, 'hits': h, 'rate': (h / n if n else None),
                'n_player_clusters': len({g['player'] for g in d}),
                'n_game_clusters': 1, 'standard_error': NO_SE}

    bands = {}
    for g in graded:
        bands.setdefault(g['band'], []).append(g)
    by_band = {k: _rate(v) for k, v in sorted(bands.items())}
    by_tag = {}
    for g in graded:
        by_tag.setdefault(g['confidence_tag'], []).append(g)
    role_split = {k: {'model_side': _rate(v),
                      'lean_vs_market': _rate(v, 'lean_correct')}
                  for k, v in sorted(by_tag.items())}

    # PHASE 5. The ordering that section 8 of the pre-kickoff export
    # published, graded as it stood. Not a staked card.
    card = sorted(graded, key=lambda g: -abs(g['model_minus_market']))[:CARD_N]
    for i, g in enumerate(card, 1):
        g['card_rank'] = i

    return Outcome.ok(
        'PROPS_GRADED',
        value={'graded': graded, 'not_graded': not_graded,
               'overall_model_side': _rate(graded),
               'overall_lean_vs_market': _rate(graded, 'lean_correct'),
               'by_probability_band': by_band,
               'by_confidence_tag': role_split,
               'card_as_ordered': {
                   'what_it_is': ('the top %d supported lines by '
                                  '|model - market| as published in section 8 '
                                  'of DET_BUF_PREKICKOFF_PROJECTIONS_'
                                  '2026-09-17.md. NOT a staked card.' % CARD_N),
                   'rows': card,
                   'hit_rate': _rate(card),
                   'lean_vs_market': _rate(card, 'lean_correct'),
                   'roi': 'NOT_AVAILABLE_NO_STAKED_PLAYS',
                   'closing_line_value': 'NOT_AVAILABLE_NO_CLOSING_VINTAGE',
                   'realised_performance': 'NOT_AVAILABLE_NO_STAKED_PLAYS'}},
        detail=f'{len(graded)} line(s) graded, {len(not_graded)} refused; '
               f'model side {_rate(graded)["hits"]}/{_rate(graded)["n"]}',
        spec_version=SPEC_VERSION, board_sha256=board.evidence['sha256'],
        n_graded=len(graded), n_not_graded=len(not_graded),
        standard_error=NO_SE,
        closing_line=(
            'NOT_AVAILABLE. The only player-prop capture is the 21:44-21:45Z '
            'vintage-1 API snapshot; vintages 2 and 3 are game-line displays '
            'at 23:05Z and 23:06Z, 69 minutes before kickoff and not a close. '
            'A closing-line comparison for player props would require a '
            'second prop capture that was never taken. See OUT-023.'),
        market_is_evaluation_only=(
            'these prices graded a forecast sealed 2026-09-16T15:45:14Z. '
            'Nothing here may move a projection.'),
        one_game_cannot_measure_calibration=(
            'a hit rate over 43 clustered lines in one game generates a '
            'hypothesis. It does not estimate a probability, and no threshold '
            'may be fitted to it.'),
        is_measurement_not_development=True)


def main() -> int:
    o = grade()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    out = OC.DIR / 'GRADE_PROPS.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         **o.value}, indent=1, sort_keys=True))
    c = AC.claim(out, schema=['graded', 'card_as_ordered'], label=out.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
