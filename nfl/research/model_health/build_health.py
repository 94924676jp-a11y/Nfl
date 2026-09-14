#!/usr/bin/env python3.12
"""Build the MODEL_HEALTH artifact from a retrospective summary. COMMITTED.

WHY THIS EXISTS. `MODEL_HEALTH_2026-09-13.json` had no build script anywhere
in the repository: `nfl/product/model_health.py` defines the contract and is
imported by nothing, so the published artifact could not be re-derived, and
nothing checked that its rows came from one run. They did not. Measured:

  * its eleven receiving and rushing rows reproduce a SEVEN-game retrospective
    run (receiving n=48, rushing/carries n=12);
  * its seven QB rows reproduce an EIGHT-game run of the same module
    (qb n=18, bias -7.2284, mae 8.5721, crps 6.2938, cov50 0.5556).

Two populations in one table, with no field saying so. That is not a rounding
concern: the QB and non-QB rows are not comparable with each other and the
artifact presented them as if they were.

WHAT THIS SCRIPT WILL NOT DO.

  * It does not read a price file. Market columns are CARRIED FORWARD verbatim
    from the superseded artifact and stamped as carried, because these repairs
    are evaluation-only and move no price. They are not thereby endorsed
    either: the caller must DECLARE their selection basis with a written
    justification, and with no declaration they are treated as
    outcome-conditional, flagged MARKET_STATS_OUTCOME_SELECTED, and cannot
    make anything rankable. The market grader
    (`nfl/research/market_outcome_audit.py`) carried the same selection defect
    at spec 1.0.0; at 2.0.0 it does not, and it reproduces the carried columns
    cell for cell, which is what licenses declaring a complete basis for them.
  * It does not drop a warning it cannot recompute. MARKET_GAP_ANTICALIBRATED
    is raised from probability buckets this script has no input for, so it is
    carried from the superseded row rather than silently lost.
  * It does not invent a metric. Only metrics present in the retrospective
    summary appear, and a metric whose market row is absent gets zeros and
    nulls, never a guess.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import model_health as MH                          # noqa: E402

SPEC_VERSION = 'model-health-build/1.0.0'

# Market-derived warnings this script cannot recompute from its inputs and
# therefore carries forward from the superseded row instead of dropping.
NON_RECOMPUTABLE = ('MARKET_GAP_ANTICALIBRATED',)

MARKET_FIELDS = ('market_n_graded', 'market_pct_under', 'market_hit_rate',
                 'market_mean_model_probability',
                 'market_mean_novig_probability', 'market_mean_gap_pp')


def sha16(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:16]


def rel(p):
    """Repo-relative path, whether the caller passed relative or absolute.

    A path recorded wrongly is a broken audit trail, and refusing a relative
    argument would only train the caller to type the long form."""
    q = pathlib.Path(p).resolve()
    try:
        return str(q.relative_to(_REPO.resolve()))
    except ValueError:
        return str(q)


def main(argv=None):
    ap = argparse.ArgumentParser(description='build MODEL_HEALTH')
    ap.add_argument('--summary', required=True,
                    help='a same_day_retrospective *.summary.json')
    ap.add_argument('--rows', required=True,
                    help='the matching retrospective CSV')
    ap.add_argument('--supersedes', required=True,
                    help='the MODEL_HEALTH artifact this one corrects')
    ap.add_argument('--date', required=True)
    ap.add_argument('--market-selection-basis', default=None,
                    help='the selection basis of the CARRIED market columns. '
                         'Omit unless the grader that produced them declares '
                         'a complete selection: an undeclared basis is '
                         'treated as outcome-conditional and blocks ranking, '
                         'which is the safe default.')
    ap.add_argument('--market-basis-justification', default='',
                    help='why the basis above is asserted. Recorded in the '
                         'artifact; required whenever a basis is declared, so '
                         'the claim is never a bare flag.')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)

    if a.market_selection_basis and not a.market_basis_justification.strip():
        raise SystemExit(
            'MODEL_HEALTH_UNJUSTIFIED_MARKET_BASIS: --market-selection-basis '
            'was declared with no --market-basis-justification. A selection '
            'basis asserted without a reason is a flag, not evidence, and '
            'this one clears a warning.')
    summ = json.loads(pathlib.Path(a.summary).read_text())
    rows = list(csv.DictReader(open(a.rows)))
    old = json.loads(pathlib.Path(a.supersedes).read_text())
    if not rows:
        raise SystemExit('MODEL_HEALTH_EMPTY_INPUT: the retrospective CSV '
                         'carries no rows. An empty input is an error.')
    old_by_metric = {r['metric']: r for r in old.get('metrics') or []}

    per = summ.get('by_metric_including_contaminated') or {}
    if not per:
        raise SystemExit('MODEL_HEALTH_NO_PER_METRIC_STATS: the summary '
                         'carries no by_metric_including_contaminated block.')
    contam = collections.Counter(
        r['metric'] for r in rows if r.get('qb3_contaminated') == 'True')
    zeroed = collections.Counter(
        r['metric'] for r in rows
        if r.get('actual_basis') == 'ZERO_BY_COMPLETION')
    refused = summ.get('refused_by_reason') or {}
    # Refusals are counted per metric from the seal records, which is where
    # the module records them. A metric with no refusals gets 0, explicitly.
    ref_by_metric = collections.Counter()
    for s in summ.get('seals_used') or []:
        for r in s.get('refused') or []:
            ref_by_metric[r.get('metric')] += 1

    basis = summ.get('outcome_selection_basis')
    out_rows = []
    for metric in sorted(per):
        st = per[metric]
        o = dict(old_by_metric.get(metric) or {})
        mkt = {'n': o.get('market_n_graded') or 0,
               'pct_under': o.get('market_pct_under'),
               'hit_rate_excl_push': o.get('market_hit_rate'),
               'mean_model_probability': o.get('market_mean_model_probability'),
               'mean_market_novig_probability':
                   o.get('market_mean_novig_probability'),
               'mean_probability_gap_pp': o.get('market_mean_gap_pp')}
        carried = [x for x in (o.get('warnings') or []) if x in NON_RECOMPUTABLE]
        declared = ['LAYER_SPECIFICATION_DEFECT'] if (
            'LAYER_SPECIFICATION_DEFECT' in (o.get('warnings') or [])) else []
        row = MH.evaluate(
            metric, outcome_stats=st, market_stats=mkt, buckets=None,
            declared_defects=declared,
            n_contaminated=contam.get(metric, 0),
            n_refused=ref_by_metric.get(metric, 0),
            n_zero_completed=zeroed.get(metric, 0),
            n_game_clusters=st.get('n_game_clusters'),
            outcome_selection_basis=basis,
            # NOT ASSUMED EITHER WAY. Whoever regenerates states the
            # basis of the carried market columns and justifies it; with no
            # declaration the contract treats them as outcome-conditional,
            # which blocks ranking. Silence is not a clean bill.
            market_selection_basis=(
                a.market_selection_basis if mkt['n'] else None),
            carried_warnings=carried)
        row['market_fields_carried_forward'] = bool(mkt['n'])
        row['se_convention'] = st.get('se_convention')
        row['se_mean_signed_error_game_clustered'] = st.get(
            'se_mean_signed_error_game_clustered')
        row['z_mean_signed_error_game_clustered'] = st.get(
            'z_mean_signed_error_game_clustered')
        row['se_mean_signed_error_player_game_clustered'] = st.get(
            'se_mean_signed_error_player_game_clustered')
        row['z_mean_signed_error_player_game_clustered'] = st.get(
            'z_mean_signed_error_player_game_clustered')
        row['se_coverage_50_game_clustered'] = st.get(
            'se_coverage_50_game_clustered')
        # Within one metric each player-game holds one row, so the
        # player-game SE above is the naive SE. Carried with its own flag so
        # the table cannot read as two robustness layers when it is one.
        row['player_game_clustering_degenerate'] = st.get(
            'player_game_clustering_degenerate')
        row['player_game_clustering_note'] = st.get(
            'player_game_clustering_note')
        row['pit_interpretable'] = st.get('pit_interpretable')
        row['pit_defect'] = st.get('pit_defect')
        out_rows.append(row)

    art = {
        'artifact': 'MODEL_HEALTH',
        'spec_version': MH.SPEC_VERSION,
        'build_spec_version': SPEC_VERSION,
        'date': a.date,
        'supersedes': {
            'path': rel(a.supersedes),
            'sha16': sha16(a.supersedes),
            'why': ('its outcome columns were computed on a set from which '
                    'every row with a realised value of zero had been '
                    'deleted (same_day_retrospective.py:186-192, v1.0.0), and '
                    'its QB rows came from a different game population than '
                    'its non-QB rows. The superseded file is NOT modified.'),
        },
        'built_from': {
            'summary': rel(a.summary),
            'summary_sha16': sha16(a.summary),
            'rows': rel(a.rows),
            'rows_sha16': sha16(a.rows),
            'retrospective_spec_version': summ.get('spec_version'),
            'outcome_source': summ.get('outcome_source'),
            'games': sorted({r['game_id'] for r in rows}),
            'seal_selection': summ.get('seal_selection'),
            'single_population': True,
            'single_population_note': (
                'every row in this artifact comes from ONE retrospective run '
                'over ONE game population. The superseded artifact did not.'),
        },
        'outcome_selection_basis': basis,
        'outcome_selection_note': summ.get('outcome_selection_note'),
        'market_selection_basis_declared': a.market_selection_basis,
        'market_basis_justification': a.market_basis_justification,
        'market_columns': (
            'CARRIED FORWARD VERBATIM from the superseded artifact and not '
            'recomputed. No price file is opened by this build. The repairs '
            'behind this artifact are evaluation-only: no projection and no '
            'price moves. Whether the carried columns are under '
            'MARKET_STATS_OUTCOME_SELECTED depends entirely on the declared '
            '--market-selection-basis, and with none declared they are.'),
        'fields': list(MH.FIELDS),
        'warning_vocabulary': MH.WARNINGS,
        'gate': ('a metric under ANY warning is ranking_eligible=false. The '
                 'row is still published with its warning attached; it is '
                 'removed from RANKING, not from the comparison.'),
        'n_metrics': len(out_rows),
        'n_ranking_eligible': sum(1 for r in out_rows if r['ranking_eligible']),
        'sample_size_note': (
            'n_scored counts player-game-metric ROWS. n_game_clusters is the '
            'unit the errors vary in and is the sample size. Neither this '
            'artifact nor anything built on it is prospective evidence, and '
            'no adequacy claim -- unbiased, stable, closed, correct -- is '
            'made about any metric here: no equivalence margin has been '
            'predeclared and no two-one-sided test has been run.'),
        'metrics': out_rows,
    }
    p = pathlib.Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(art, indent=1) + '\n')
    print(f'{len(out_rows)} metric row(s) -> {p}')
    print(f"ranking eligible: {art['n_ranking_eligible']} / {len(out_rows)}")
    for r in out_rows:
        print(f"  {r['metric']:28s} n={r['n_scored']:4d} "
              f"G={r['n_game_clusters']} zero={r['n_zero_completed_rows']:4d} "
              f"elig={str(r['ranking_eligible']):5s} {','.join(r['warnings'])}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
