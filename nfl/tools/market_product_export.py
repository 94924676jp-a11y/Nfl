"""The delivered market-product export: one row per book quote, no exceptions.

WHY A SEPARATE EXPORTER. `market_comparison` emits the analytic table and a
separate refusals file. That split is right for analysis and wrong for
delivery: a reader handed only the analytic table sees 28 rows and has no way
to know the book quoted 46. This exporter emits ONE ROW PER QUOTE, compared or
refused, in the column contract the product asks for, so the count in the file
is the count the sportsbook published.

A REFUSED ROW IS A ROW. It carries the player, the market, the line, the odds
and a `refusal_reason`, and leaves every model column empty. It never carries a
number, because a refused market has no number -- and an empty cell that a
reader can see is safer than a row that quietly does not exist.

RANKING IS DISAGREEMENT, NOT EDGE. Candidates are ordered by the absolute gap
between the model's probability at the book's exact line and the book's
de-vigged probability. A large gap says the two disagree. It is equally
consistent with the model being wrong, and this file never calls it an edge,
a value, or a recommendation.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import forecast_stage as FS                        # noqa: E402
from nfl.product import names as NM                                 # noqa: E402
from nfl.research import daily_board as RB                          # noqa: E402
from nfl.tools import market_comparison as MC                       # noqa: E402

SPEC_VERSION = 'market-product-export/1.0.0'

# The delivered column contract, in order.
COLUMNS = ('player', 'team', 'market', 'side', 'model_mean', 'model_median',
           'hardrock_line', 'over_odds', 'under_odds',
           'projection_minus_line', 'projection_minus_line_pct',
           'model_p_over_at_exact_line', 'model_p_under_at_exact_line',
           'hardrock_novig_p_over', 'hardrock_novig_p_under',
           'selected_side', 'model_market_probability_gap_pp',
           'forecast_stage', 'model_written_at', 'market_retrieved_at',
           'data_status', 'refusal_reason')

# `side` describes the QUOTE's structure; `selected_side` is the model's pick.
# Both are in the contract and they are not the same field, so neither is
# derived from the other.
QUOTE_SIDE = 'OVER_UNDER'


def build(rows, refusals, quotes, stage):
    """One row per quote. Compared rows first, then refusals, both ordered."""
    by_key = {}
    for r in rows:
        by_key[(r['player'], r['team'], r['market'])] = r
    out = []
    for r in rows:
        out.append({
            'player': r['player'], 'team': r['team'], 'market': r['market'],
            'side': QUOTE_SIDE,
            'model_mean': r['r8_mean'], 'model_median': r['r8_median'],
            'hardrock_line': r['line'],
            'over_odds': r['over_price'], 'under_odds': r['under_price'],
            'projection_minus_line': r['projection_minus_line'],
            'projection_minus_line_pct': r['projection_minus_line_pct'],
            'model_p_over_at_exact_line': r['r8_p_over'],
            'model_p_under_at_exact_line': r['r8_p_under'],
            'hardrock_novig_p_over': r['no_vig_p_over'],
            'hardrock_novig_p_under': r['no_vig_p_under'],
            'selected_side': r['selected_side'],
            'model_market_probability_gap_pp': r['probability_gap_pp'],
            'forecast_stage': r['forecast_stage'],
            'model_written_at': r['written_at'],
            'market_retrieved_at': r['hard_rock_retrieved_at'],
            'data_status': r['data_status'], 'refusal_reason': '',
        })
    for x in refusals:
        key = (x.get('player'), None, x.get('market'))
        q = None
        for (qn, qt, qm), v in quotes.items():
            if qn == x.get('player') and qm == x.get('market'):
                q, key = v, (qn, qt, qm)
                break
        reason = f"REFUSED:{x.get('reason')}"
        out.append({
            'player': x.get('player', ''), 'team': key[1] or '',
            'market': x.get('market', ''), 'side': QUOTE_SIDE,
            'model_mean': '', 'model_median': '',
            'hardrock_line': (q or {}).get('line', ''),
            'over_odds': (q or {}).get('over_price', ''),
            'under_odds': (q or {}).get('under_price', ''),
            'projection_minus_line': '', 'projection_minus_line_pct': '',
            'model_p_over_at_exact_line': '',
            'model_p_under_at_exact_line': '',
            'hardrock_novig_p_over': '', 'hardrock_novig_p_under': '',
            'selected_side': '', 'model_market_probability_gap_pp': '',
            'forecast_stage': x.get('forecast_stage') or stage,
            'model_written_at': '',
            'market_retrieved_at': (q or {}).get('timestamp', ''),
            'data_status': 'REFUSED',
            'refusal_reason': f'{reason} | {str(x.get("detail") or "")[:400]}',
        })
    return out


def qb_participation_evidence(game, cut, label, names):
    """The QB participation distribution, shown BEFORE any QB prop is admitted.

    REPORTED ON DROPBACK COUNTS, NOT ON A DERIVED SHARE. Dividing `qb/db` by
    `team_volume/team_dropbacks_part` looks like a share but is not one: R2's
    integer apportionment sits between the two, so the per-draw ratio runs
    0.973 to 1.024 and a "share" can read above 1. The counts are exact and
    need no division, so they are what is quoted. The QB3 allocation's own
    shares close to 1 by construction; that is a property of the layer, not of
    this arithmetic.
    """
    import numpy as np
    from nfl.research import board_select as BS2
    from nfl.product import daily_board as PB2
    cfgdir = RB.LIVE / game / f'{cut}_{label}'
    bd, _ = BS2.newest_board_dir(cfgdir)
    if bd is None:
        return {'status': 'NO_SEALED_BOARD'}
    board = json.load(open(bd / 'board.json'))
    man = json.loads((bd / 'player_draws_manifest.json').read_text())
    draws = PB2._load_draws(bd)
    tv = man['layers']['team_volume']
    td = draws['team_volume__team_dropbacks_part']
    out = {'status': 'OK', 'run_id': board.get('run_id'),
           'written_at': (board.get('freshness') or {}).get('written_at'),
           'measured_on': 'qb/db dropback counts, exact; no share is derived',
           'teams': {}}
    for team in board.get('teams') or []:
        cfg = (board.get('qb3_configuration') or {}).get(team) or {}
        tdb = np.asarray(td[tv['row_ids'].index(team)], float)
        room = []
        for pl in board.get('players') or []:
            if pl.get('position') != 'QB' or pl.get('team') != team:
                continue
            db = np.asarray(MC.draw_row_for(man, draws, 'qb/db',
                                            pl['gsis_id']), float)
            room.append({
                'player': names.get(pl['gsis_id'], pl['gsis_id']),
                'gsis_id': pl['gsis_id'],
                'p_takes_any_dropback': round(float((db > 0).mean()), 4),
                'p_at_least_half_the_team': round(
                    float((db >= 0.5 * tdb).mean()), 4),
                'mean_dropbacks': round(float(db.mean()), 3),
                'q10_dropbacks': round(float(np.quantile(db, 0.10)), 3),
                'median_dropbacks': round(float(np.median(db)), 3),
                'q90_dropbacks': round(float(np.quantile(db, 0.90)), 3),
            })
        room.sort(key=lambda r: -r['mean_dropbacks'])
        out['teams'][team] = {
            'qb3_configuration': cfg.get('configuration'),
            'is_season_opener': cfg.get('is_season_opener'),
            'defect_id': cfg.get('defect_id'),
            'prev_primary': names.get(cfg.get('prev_primary_pid'),
                                      cfg.get('prev_primary_pid')),
            'prev_primary_ordinal': cfg.get('prev_primary_ordinal'),
            'depth_chart_qb1': names.get(cfg.get('depth_chart_qb1'),
                                         cfg.get('depth_chart_qb1')),
            'team_mean_dropbacks': round(float(tdb.mean()), 2),
            'room': room,
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='delivered market product export')
    ap.add_argument('--market', required=True)
    ap.add_argument('--game', required=True)
    ap.add_argument('--candidate', default='R8')
    ap.add_argument('--stage', default='pre', choices=('pre', 'post'))
    ap.add_argument('--out-csv', required=True)
    ap.add_argument('--out-top', required=True)
    ap.add_argument('--top', type=int, default=10)
    a = ap.parse_args(argv)

    snap = MC.load_frozen_snapshot(a.market)
    quotes = snap['quotes']
    label = ('V1_CANDIDATE' if a.candidate == 'V1'
             else f'V1_CANDIDATE_{a.candidate}')
    cut = 'pre_inactives' if a.stage == 'pre' else 'post_inactives'
    stage = FS.PRE if a.stage == 'pre' else FS.POST
    names = NM.lookup(None)
    gdir = RB.LIVE / a.game
    cfg = gdir / f'{cut}_{label}'
    if not cfg.exists():
        raise SystemExit(f'NO_SEALED_BOARD_FOR_STAGE: {cfg}')
    rows, refusals = MC.rows_for_game(a.game, cfg, quotes, names)

    # THE INVARIANT, ASSERTED BEFORE ANYTHING IS WRITTEN.
    n_scope = sum(1 for (_, qt, _) in quotes
                  if qt in set(a.game.split('_')[2:4]))
    if len(rows) + len(refusals) != n_scope:
        raise SystemExit(
            f'MARKET_QUOTE_ACCOUNTING_UNBALANCED: {n_scope} quote(s) in scope '
            f'produced {len(rows) + len(refusals)} outcome(s). Refusing to '
            f'write a delivery that loses a quote.')

    delivered = build(rows, refusals, quotes, stage)
    out = pathlib.Path(a.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in delivered:
            w.writerow(r)

    top, n_qual = MC.rank_candidates(rows, a.top)
    board_written = next((r['written_at'] for r in rows if r.get('written_at')),
                         None)
    tp = pathlib.Path(a.out_top)
    tp.write_text(json.dumps({
        'artifact': 'PRE_INACTIVES_TOP_CANDIDATES' if stage == FS.PRE
                    else 'POST_INACTIVES_TOP_CANDIDATES',
        'spec_version': SPEC_VERSION,
        'game': a.game, 'forecast_stage': stage,
        'model_written_at': board_written,
        'market_snapshot': {
            'sportsbook': 'Hard Rock Bet', 'path': snap['path'],
            'sha256': snap['sha256'], 'n_quotes': snap['n_quotes'],
            'availability_derived_from_two_sided_prices':
                snap.get('availability_derived', False)},
        'accounting': {'n_quotes': n_scope, 'n_compared': len(rows),
                       'n_refused': len(refusals),
                       'balanced': len(rows) + len(refusals) == n_scope},
        'refusals_by_reason': dict(collections.Counter(
            x['reason'] for x in refusals)),
        'ranking_basis': (
            'absolute gap between the model probability at the book exact '
            'line and the book de-vigged probability, in percentage points. '
            'A DISAGREEMENT ordering: a large gap is equally consistent with '
            'the model being wrong. It is not an edge, not a value estimate '
            'and not a recommendation.'),
        'not_padded': ('never padded to the cap. If fewer markets are '
                       'scientifically admissible, fewer are returned.'),
        'n_qualified': n_qual, 'n_returned': len(top),
        'candidates': top,
        'visual_series': [{'label': r['play'],
                           'probability_gap_pp': r['probability_gap_pp'],
                           'difference_pct': r['difference_pct'],
                           'model_probability': r['model_probability'],
                           'hard_rock_no_vig_probability':
                               r['hard_rock_no_vig_probability']}
                          for r in top],
        'qb_participation_evidence': qb_participation_evidence(
            a.game, cut, label, names),
        'qb_markets_admitted': False,
        'why_qb_markets_are_refused': (
            'both rooms are season-opener rooms, so QB3_WEEK1_SEASON_BOUNDARY '
            'applies to each. The participation distribution above is the '
            'evidence: it is shown before any QB prop is considered, and it '
            'is why none is admitted.'),
        'no_wager_is_recommended': True,
    }, indent=1) + '\n')
    print(f'{len(delivered)} delivered row(s) ({len(rows)} compared, '
          f'{len(refusals)} refused) -> {out}')
    print(f'{len(top)} candidate(s) of {n_qual} qualified -> {tp}')
    print(f'accounting: {n_scope} quote(s) = {len(rows)} + {len(refusals)} '
          f'-> BALANCED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
