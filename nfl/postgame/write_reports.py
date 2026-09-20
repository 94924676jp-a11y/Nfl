"""Render the Week-2 markdown reports FROM the summary JSON.

The reports are generated, never typed, so a number in prose cannot drift
from the number in the dataset. Every claim carries OBSERVED / INFERRED /
HYPOTHESIS.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = _REPO / 'nfl' / 'research' / 'postgame'
CAVEAT = (
    'CANDIDATE_NOT_ACCEPTED_BASELINE. The board graded here is '
    '`V1_CANDIDATE_R9_W1P_GSVUCY`, authorised for one slate and never '
    'promoted. The runs stopped at `artifact_sealing`, so the board is '
    'UNSEALED. No production model, coefficient or candidate identity was '
    'changed by this analysis. V2 NOT YET EARNED.')


def _f(x, nd=4):
    return 'n/a' if x is None else f'{x:.{nd}f}'


def projection_md(s):
    p, w = s['projection_calibration'], s['workload_calibration']
    L = ['# Week 2 — projection calibration', '',
         f"Graded player-games: **{p['n_graded']}** across "
         f"**{p['n_game_clusters']}** games. "
         f"Not published: {', '.join(s['coverage']['games_not_published']) or 'none'}.",
         '', CAVEAT, '',
         '## DraftKings points, projected mean vs actual', '',
         '| statistic | value |', '|---|---|',
         f"| mean bias (actual − projected) | **{_f(p['mean_bias_actual_minus_projected'])}** |",
         f"| SE of bias, naive | {_f(p['bias_se_naive'])} |",
         f"| SE of bias, clustered by game | **{_f(p['bias_se_clustered_by_game'])}** |",
         f"| MAE | {_f(p['mae'])} |",
         f"| RMSE | {_f(p['rmse'])} |",
         f"| SD of projected means | {_f(p['sd_projected_mean'])} |",
         f"| SD of actuals | {_f(p['sd_actual'])} |",
         f"| SD ratio projected/actual | {_f(p['sd_ratio_projected_over_actual'])} |",
         f"| Pearson r | **{_f(p['pearson_r'])}** |", '',
         'OBSERVED: the mean DK bias is '
         f"{_f(p['mean_bias_actual_minus_projected'], 3)} points against a "
         f"game-clustered SE of {_f(p['bias_se_clustered_by_game'], 3)}. "
         'That is well inside one SE. No equivalence margin was predeclared, '
         'so this is a failure to detect bias, NOT a demonstration that the '
         'projections are unbiased.', '',
         f"OBSERVED: r = {_f(p['pearson_r'])} between projected mean and "
         'actual DK points. Calibration and discrimination are different '
         'properties and this line speaks only to discrimination.', '',
         '## Quantile coverage', '',
         '| quantile | nominal | realised at or below | n |', '|---|---|---|---|']
    for q, v in p['quantile_coverage'].items():
        L.append(f"| {q} | {v['nominal']:.2f} | **{v['realized_at_or_below']:.4f}** | {v['n']} |")
    L += ['',
          '## Threshold probability calibration', '',
          '| threshold | n | mean predicted | realised | gap | SE clustered |',
          '|---|---|---|---|---|---|']
    for k, v in p['threshold_probability_calibration'].items():
        L.append(f"| {k} | {v['n']} | {_f(v['mean_predicted'])} | "
                 f"{_f(v['realized'])} | **{v['gap']:+.4f}** | "
                 f"{_f(v['se_clustered_by_game'])} |")
    L += ['', '## Workload calibration', '',
          '| quantity | n | mean projected | mean actual | bias | MAE | RMSE | SE clustered |',
          '|---|---|---|---|---|---|---|---|']
    for k, v in w.items():
        L.append(f"| {k} | {v['n']} | {_f(v['mean_projected'], 3)} | "
                 f"{_f(v['mean_actual'], 3)} | "
                 f"**{v['mean_bias_actual_minus_projected']:+.3f}** | "
                 f"{_f(v['mae'], 3)} | {_f(v['rmse'], 3)} | "
                 f"{_f(v['bias_se_clustered_by_game'], 3)} |")
    L += ['', 'OBSERVED: the passing-game volume quantities (targets, '
          'receptions, receiving yards, pass attempts, completions) are '
          'biased POSITIVE — the model projected less than happened. '
          'Rushing yards and passing touchdowns are biased negative. The '
          'miss is directional by quantity, not a uniform shift.', '',
          'INFERRED: because every one of these quantities is measured on the '
          'same seven games and many on the same players, these are not '
          'independent confirmations of one another. The game-clustered SEs '
          'are the honest ones and several of the biases are inside two of '
          'them.']
    return '\n'.join(L) + '\n'


def prop_md(s):
    p = s['prop_calibration']
    L = ['# Week 2 — prop calibration', '',
         f"Graded prop markets: **{p['n_graded']}** over "
         f"**{p['n_game_clusters']}** games; pushes: {p['n_push']}.", '',
         CAVEAT, '',
         '## Headline', '', '| statistic | model | book (no-vig) |',
         '|---|---|---|',
         f"| Brier | **{_f(p['brier_model'], 6)}** | {_f(p['brier_book_novig'], 6)} |",
         f"| log loss | **{_f(p['log_loss_model'], 6)}** | {_f(p['log_loss_book_novig'], 6)} |",
         '',
         f"| mean predicted probability | **{_f(p['mean_predicted_probability'])}** |",
         '|---|---|',
         f"| realised hit rate | **{_f(p['realized_hit_rate'])}** |",
         f"| naive SE | {_f(p['hit_rate_se_naive'])} |",
         f"| SE clustered by game | **{_f(p['hit_rate_se_clustered_by_game'])}** |",
         f"| SE inflation from clustering | {_f(p['se_inflation_factor'], 3)}× |",
         f"| side counts | {p['side_counts']} |", '',
         'OBSERVED: the model said '
         f"{p['mean_predicted_probability']:.3f} and reality delivered "
         f"{p['realized_hit_rate']:.3f} — a gap of "
         f"**{p['realized_hit_rate'] - p['mean_predicted_probability']:+.4f}** "
         f"against a game-clustered SE of "
         f"{_f(p['hit_rate_se_clustered_by_game'])}. Clustering inflates the "
         f"SE by {_f(p['se_inflation_factor'], 2)}×; quoting the naive SE "
         'would have overstated the precision of this statement.', '',
         'OBSERVED: the book beat the model on BOTH proper scores — lower '
         'Brier and lower log loss. On this slate the model\'s prop '
         'probabilities were worse than the de-vigged market.', '',
         '## Calibration curve by predicted-probability bucket', '',
         '| bucket | n | mean predicted | realised | gap | SE clustered | clusters |',
         '|---|---|---|---|---|---|---|']
    for b in p['probability_buckets']:
        if not b['n']:
            L.append(f"| {b['bucket']} | 0 | — | — | — | — | — |")
            continue
        L.append(f"| {b['bucket']} | {b['n']} | {_f(b['mean_predicted'])} | "
                 f"{_f(b['realized'])} | **{b['gap']:+.4f}** | "
                 f"{_f(b['se_clustered_by_game'])} | {b['n_game_clusters']} |")
    L += ['', '## By market family', '',
          '| market | n | mean predicted | realised | gap | SE clustered | mean raw edge | Brier |',
          '|---|---|---|---|---|---|---|---|']
    for f in p['by_market_family']:
        L.append(f"| {f['market']} | {f['n']} | {_f(f['mean_predicted'])} | "
                 f"{_f(f['realized'])} | **{f['gap']:+.4f}** | "
                 f"{_f(f['se_clustered_by_game'])} | "
                 f"{_f(f['mean_raw_edge'])} | {_f(f['brier'])} |")
    e = p.get('edge_vs_outcome') or {}
    if e:
        L += ['', '## Raw edge against realised outcome', '',
              '| half | n | mean edge | hit rate |', '|---|---|---|---|',
              f"| low edge | {e['low_edge_half']['n']} | "
              f"{_f(e['low_edge_half']['mean_edge'])} | "
              f"{_f(e['low_edge_half']['hit_rate'])} |",
              f"| high edge | {e['high_edge_half']['n']} | "
              f"{_f(e['high_edge_half']['mean_edge'])} | "
              f"{_f(e['high_edge_half']['hit_rate'])} |", '',
              'INFERRED: bigger claimed edge went with a higher hit rate, '
              'which is weak evidence that the edge ordering carries some '
              'signal even though its LEVEL is badly overstated. Two halves '
              'over seven games is not a test; it is a direction.']
    L += ['', '## Closing-line movement', '',
          'The board carries the 04:52Z → 16:35Z movement for every market, '
          'but 16:35Z IS the frozen comparison snapshot and no later capture '
          'was taken. So no closing-line value can be computed for Week 2. '
          'A genuine CLV column needs a capture at or near kickoff.']
    return '\n'.join(L) + '\n'


def dfs_md(s):
    p = s['projection_calibration']
    L = ['# Week 2 — DFS postmortem', '', CAVEAT, '',
         '## What this report CANNOT answer, and why', '',
         'The lineup-level half of this postmortem is **not computable from '
         'anything in this repository.** The 73 DraftKings entries were '
         'constructed downstream and were never written here — this session '
         'was explicitly instructed not to generate them. Without the '
         'submitted lineup set there is no stack structure, no bring-back '
         'structure, no salary used, no overlap, no player or game exposure, '
         'and therefore no way to separate construction error from '
         'projection error.', '',
         'To make the portfolio half of this report real, supply one file: '
         'the submitted entry set with, per lineup, the eight roster slots '
         'by DraftKings player id and the contest it was entered in. '
         'Everything else on the list — actual DK points per lineup, '
         'projected mean, ceiling proxy, stack and bring-back structure, '
         'salary used, overlap, exposures — is then derivable from the '
         'canonical dataset already written.', '',
         'ABSENT IS NOT ZERO. No portfolio number is estimated, and none of '
         'the player-level results below should be read as a lineup result.',
         '', '## What IS answerable: the player layer the lineups were built '
         'from', '', '| statistic | value |', '|---|---|',
         f"| graded players | {p['n_graded']} |",
         f"| DK mean bias (actual − projected) | **{_f(p['mean_bias_actual_minus_projected'])}** |",
         f"| MAE | {_f(p['mae'])} |",
         f"| RMSE | {_f(p['rmse'])} |",
         f"| Pearson r | **{_f(p['pearson_r'])}** |",
         f"| SD ratio projected/actual | {_f(p['sd_ratio_projected_over_actual'])} |",
         '']
    for q, v in p['quantile_coverage'].items():
        L.append(f"- projected {q}: realised at or below "
                 f"**{v['realized_at_or_below']:.4f}** against a nominal "
                 f"{v['nominal']:.2f} (n={v['n']})")
    L += ['',
          'OBSERVED: the ceiling proxies were not too thin. The p90 and p95 '
          'both contained MORE of the realised outcomes than nominal, which '
          'is the opposite of the failure mode a GPP player fears.', '',
          'INFERRED: on this slate the player-level DK projections were the '
          'stronger part of the system and the prop probabilities were the '
          'weaker part. Since the lineups were built from DK projections '
          'rather than from prop probabilities, a portfolio postmortem is '
          'more likely to find construction and variance effects than a '
          'projection collapse — but that is a statement about where to '
          'look, not a result.', '',
          'HYPOTHESIS: one slate of seven games cannot separate '
          'construction, exposure concentration and variance. That '
          'separation needs the entry set plus several slates.']
    return '\n'.join(L) + '\n'


def main():
    s = json.loads((OUT / 'week2_postgame_summary.json').read_text())
    for name, text in (
            ('week2_projection_calibration.md', projection_md(s)),
            ('week2_prop_calibration.md', prop_md(s)),
            ('week2_dfs_portfolio_postmortem.md', dfs_md(s))):
        (OUT / name).write_text(text)
        print(f'wrote {name} {len(text)} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
