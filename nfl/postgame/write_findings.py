"""WHAT FAILED, WHAT HELD, WHAT WE SHOULD TEST NEXT — generated from the data."""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = _REPO / 'nfl' / 'research' / 'postgame'


def main():
    s = json.loads((OUT / 'week2_postgame_summary.json').read_text())
    p, w = s['projection_calibration'], s['workload_calibration']
    pr, u = s['prop_calibration'], s['under_bias_investigation']
    gap = pr['realized_hit_rate'] - pr['mean_predicted_probability']
    L = [
        '# Week 2 — WHAT FAILED, WHAT HELD, WHAT WE SHOULD TEST NEXT', '',
        f"Seven graded games ({', '.join(x[8:] for x in s['coverage']['games_graded'])}). "
        f"{s['coverage']['games_not_published'] and 'Not published: ' + ', '.join(x[8:] for x in s['coverage']['games_not_published']) or ''}",
        '',
        'CANDIDATE_NOT_ACCEPTED_BASELINE. Board unsealed. No production '
        'change was made by this analysis. V2 NOT YET EARNED.', '',
        '## WHAT FAILED', '',
        f"**1. The prop probabilities were overconfident, and the book beat "
        f"them on both proper scores.** OBSERVED: mean predicted "
        f"{pr['mean_predicted_probability']:.4f} against a realised "
        f"{pr['realized_hit_rate']:.4f}, a gap of {gap:+.4f} with a "
        f"game-clustered SE of {pr['hit_rate_se_clustered_by_game']:.4f} — "
        f"roughly {abs(gap) / pr['hit_rate_se_clustered_by_game']:.1f} SE. "
        f"Brier {pr['brier_model']:.6f} against the book's "
        f"{pr['brier_book_novig']:.6f}; log loss {pr['log_loss_model']:.6f} "
        f"against {pr['log_loss_book_novig']:.6f}. Both favour the market.",
        '',
        f"**2. The pregame UNDER lean was real and it was wrong.** OBSERVED: "
        f"{pr['side_counts']} by side. The model's preferred side was UNDER "
        f"on the large majority of markets and the passing-game volume "
        f"quantities all came in ABOVE projection: targets "
        f"{w['targets']['mean_bias_actual_minus_projected']:+.3f} "
        f"(SE {w['targets']['bias_se_clustered_by_game']:.3f}), receptions "
        f"{w['receptions']['mean_bias_actual_minus_projected']:+.3f} "
        f"(SE {w['receptions']['bias_se_clustered_by_game']:.3f}), pass "
        f"attempts {w['att']['mean_bias_actual_minus_projected']:+.3f} "
        f"(SE {w['att']['bias_se_clustered_by_game']:.3f}).",
        '',
        f"**3. Target allocation was too diffuse.** OBSERVED: mean "
        f"target-share concentration (HHI) was "
        f"{u['target_share_hhi_projected']:.4f} projected against "
        f"{u['target_share_hhi_actual']:.4f} realised, a difference of "
        f"{u['hhi_mean_difference_actual_minus_projected']:+.4f} with SE "
        f"{u['hhi_difference_se']:.4f} over "
        f"{u['teams_with_receiving_coverage']} teams "
        f"(t = {u['hhi_t_statistic']:.2f}). Real offences concentrated "
        f"targets more than the model did.",
        '',
        '**4. Two skill-position coverage failures, and I under-reported '
        'them at delivery.** OBSERVED: `2026_02_PHI_TEN` emitted NO '
        '`receiving`, `rushing`, `rush_category`, `rush_player_pool` or '
        '`gadget_rush` layer at all — six rows total, four quarterbacks and '
        'two kickers — while its run reported PASS on appearance, '
        'participation, targets_carries, conversion and td_layer. A stage '
        'reporting success while emitting nothing is precisely the defect '
        'class this project treats as its most expensive. OBSERVED: in '
        '`2026_02_MIN_CHI` every CHI skill player carries only '
        '`gadget_rush` keys and no `receiving` row, while MIN players carry '
        'both — a one-sided failure inside a game that otherwise looks '
        'complete.',
        '',
        'The package DISCLOSED this correctly: '
        '`audits.position_support_per_game["2026_02_PHI_TEN"]` reads '
        '`RB 0, TE 0, WR 0`. I did not read that section when I delivered '
        'the seven- and eight-game boards and reported only row totals, so '
        'a board with no skill players for one game went downstream '
        'described as complete. The artifact was honest; the delivery note '
        'was not. Any slate-wide aggregate over these games is wrong unless '
        'it excludes them, and every number in this package does.',
        '',
        '## WHAT HELD', '',
        f"**1. The DK point projections were close to unbiased and "
        f"discriminated well.** OBSERVED: mean bias "
        f"{p['mean_bias_actual_minus_projected']:+.4f} DK points against a "
        f"game-clustered SE of {p['bias_se_clustered_by_game']:.4f} — inside "
        f"one SE. Pearson r = {p['pearson_r']:.4f}, MAE {p['mae']:.4f}, RMSE "
        f"{p['rmse']:.4f}. No equivalence margin was predeclared, so this is "
        f"a failure to detect bias, not a demonstration of its absence.",
        '',
        f"**2. The DK distributions were not too narrow.** OBSERVED: "
        + '; '.join(f"{q} covered {v['realized_at_or_below']:.4f} against a "
                    f"nominal {v['nominal']:.2f}"
                    for q, v in p['quantile_coverage'].items())
        + '. The tails contained more than nominal, not less.',
        '',
        f"**3. The edge ORDERING carried some signal even though its LEVEL "
        f"did not.** OBSERVED: the low-edge half hit "
        f"{pr['edge_vs_outcome']['low_edge_half']['hit_rate']:.4f} and the "
        f"high-edge half {pr['edge_vs_outcome']['high_edge_half']['hit_rate']:.4f}. "
        f"INFERRED: direction, not a test — two halves over seven games.",
        '',
        '**4. Every governance gate behaved.** OBSERVED: the inactive gate '
        'was certified on real evidence, the DFS and prop views were proven '
        'to share one set of draws, and the unsealed board was labelled as '
        'such in every artifact.',
        '',
        '## THE CENTRAL READING, AND WHAT IT IS NOT', '',
        'INFERRED: the DK mean was nearly unbiased while the prop '
        'probabilities were badly overconfident toward UNDER. Those two '
        'facts are compatible and together they locate the problem: the '
        'central tendency of total fantasy production was about right, '
        'while the PER-QUANTITY distributions used to price a line were '
        'shifted low on passing volume and spread too evenly across '
        'receivers. A DK point total can be right while the receptions and '
        'receiving-yards distributions that compose it are both wrong.',
        '',
        'NOT A CONCLUSION: this is one slate of seven games, the markets '
        'are heavily overlapping, and the clustered SEs are wide. Nothing '
        'here identifies a coefficient to change. The correlated misses are '
        'ONE bias observed many times, and counting them as '
        f"{pr['n_graded']} independent results would be the error this "
        'project keeps finding in its own history.',
        '',
        '## WHAT WE SHOULD TEST NEXT', '',
        '**H1 — target concentration.** HYPOTHESIS: the allocation layer '
        'spreads targets too evenly, and a concentration parameter fitted '
        'out of sample would raise both prop calibration and '
        'discrimination. Test: forward-chained, fit on weeks before the '
        'evaluation week, score with Brier and log loss on held-out weeks. '
        'This is the best-identified finding here (t ≈ '
        f"{u['hhi_t_statistic']:.2f}) and should be first.",
        '',
        '**H2 — team pass volume.** HYPOTHESIS: projected team targets sit '
        f"below realised. OBSERVED support is weaker: projected/actual "
        f"{u['projected_over_team_actual']:.4f} "
        f"({u['volume_shortfall_pct']:.1f}% short) with a per-team ratio of "
        f"{u['per_team_ratio_mean']:.4f} ± {u['per_team_ratio_se']:.4f} over "
        f"{u['teams_with_receiving_coverage']} teams. Test it separately "
        'from H1; they are confounded in this slate.',
        '',
        '**H3 — the coverage hole.** Not a hypothesis, a defect. Find why '
        'CHI, PHI and TEN emitted no receiving layer and fix it before any '
        'further calibration work, because it silently removes teams from '
        'every aggregate.',
        '',
        '**H4 — passing touchdowns.** OBSERVED: bias '
        f"{w['ptd']['mean_bias_actual_minus_projected']:+.3f} (SE "
        f"{w['ptd']['bias_se_clustered_by_game']:.3f}) — the model projected "
        'MORE passing TDs than happened while projecting FEWER pass '
        'attempts. HYPOTHESIS: the conversion layer compensates for low '
        'volume with high per-attempt scoring. Worth a decomposition.',
        '',
        '**H5 — closing line value.** Not computable for Week 2: the 16:35Z '
        'board IS the frozen comparison and no later snapshot exists. '
        'Capture a near-kickoff board next week so CLV becomes measurable.',
        '',
        '**H6 — injury-distorted filtering.** The OUTCOME_INTERPRETATION '
        'field and its filter exist and every Week-2 row reads NORMAL with '
        'the basis stated, because snap counts cover only 2026_02_DET_BUF. '
        'Ingest the participation feed so a prop that won on an early exit '
        'stops counting the same as one that won on a full workload.',
        '',
        '## Reproducing any number here', '',
        f"Canonical dataset: `{s['canonical_dataset']['csv']}` "
        f"({s['canonical_dataset']['n_rows']} rows) and the same rows as "
        f"JSONL. {s['canonical_dataset']['parquet_note']}",
        '',
        'Realised outcomes come from a preserved, read-only snapshot pinned '
        'by sha256 in `nfl/postgame/actuals.py`; a regrade on different '
        'bytes is refused by name rather than silently producing a '
        'different grade.',
    ]
    t = '\n'.join(L) + '\n'
    (OUT / 'week2_what_failed_what_held.md').write_text(t)
    print(f'wrote week2_what_failed_what_held.md {len(t)} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
