"""Run MKT1 against a sealed forecast. Diagnostic only; changes nothing."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import statistics
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import distributions as D                       # noqa: E402
from nfl.product import names as NM                              # noqa: E402
from nfl.research.mkt1 import market_diagnostic as MD            # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--forecast-dir', required=True)
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    fc = D.Forecast(a.forecast_dir)
    art = fc.artifact
    names = NM.lookup(art.get('written_at'))
    by_name = {}
    for pid, nm in names.items():
        by_name.setdefault(nm, pid)

    rows = MD.load_snapshot(a.snapshot)
    cons = MD.consensus(rows)

    out, gaps = [], []
    for (player, market), c in sorted(cons.items()):
        pid = by_name.get(player)
        rec = {**c, 'gsis_id': pid}
        if pid is None:
            rec.update({'comparable': False,
                        'reason': 'PLAYER_NOT_RESOLVED_TO_GSIS_ID'})
            out.append(rec)
            continue

        if market == MD.ANYTIME:
            from nfl.product import thresholds as TH
            layers = fc.players().get(pid, {})
            td = TH.td_probability(fc, pid, list(layers))
            pm = td.get('anytime')
            rec.update({'comparable': pm is not None,
                        'p_model_over': pm,
                        'model_components': td.get('components'),
                        'disagreement_pp': (round((pm - c['p_market_raw'])
                                                  * 100, 2)
                                            if pm is not None else None),
                        'caution': 'the market side is one-sided and carries '
                                   'its full hold; the gap overstates model '
                                   'shortfall by roughly that margin'})
            out.append(rec)
            continue

        key = MD.MARKET_MAP.get(market)
        if key is None:
            rec.update({'comparable': False,
                        'reason': f'MARKET_NOT_MAPPED: {market}'})
            out.append(rec)
            continue
        layer, metric = key
        vec = fc.vector(layer, metric, pid)
        if vec is None and market == 'Rushing yards':
            # THE MODEL DECLINES TO PRICE THIS AT ALL for a non-QB.
            rec.update({'comparable': False, 'reason': MD.NO_MODEL_METRIC,
                        'detail': 'V1 has no governed carry -> rushing-yards '
                                  'control; this is a coverage gap, not a '
                                  'disagreement'})
            out.append(rec)
            continue
        if vec is None:
            rec.update({'comparable': False,
                        'reason': f'NO_MODEL_DISTRIBUTION: {layer}/{metric}'})
            out.append(rec)
            continue

        m = MD.model_probability(vec, c['line'], market)
        pp = round((m['p_model_over'] - c['p_market_fair']) * 100, 2)
        z = MD.standardized(c['line'], m['model_mean'], m['model_sd'])
        rec.update({'comparable': True, 'layer': layer, 'metric': metric,
                    **m, 'disagreement_pp': pp,
                    'standardized_line_vs_model_mean': z,
                    'implied_market_central_estimate': c['line']})
        out.append(rec)
        gaps.append(rec)

    # ---- is the disagreement systematic? --------------------------------
    def agg(sel, label):
        if not sel:
            return None
        pps = [r['disagreement_pp'] for r in sel]
        zs = [r['standardized_line_vs_model_mean'] for r in sel
              if r['standardized_line_vs_model_mean'] is not None]
        neg = sum(1 for p in pps if p < 0)
        return {'group': label, 'n': len(sel),
                'median_disagreement_pp': round(statistics.median(pps), 2),
                'mean_disagreement_pp': round(statistics.mean(pps), 2),
                'median_standardized': (round(statistics.median(zs), 3)
                                        if zs else None),
                'n_model_below_market': neg,
                'n_model_above_market': len(pps) - neg,
                'all_one_direction': neg == len(pps) or neg == 0}

    by_metric = collections.defaultdict(list)
    by_player = collections.defaultdict(list)
    for r in gaps:
        by_metric[f'{r["layer"]}/{r["metric"]}'].append(r)
        by_player[r['player']].append(r)

    summary = {
        'overall': agg(gaps, 'all comparable markets'),
        'by_metric': {k: agg(v, k) for k, v in sorted(by_metric.items())},
        'by_player': {k: agg(v, k) for k, v in sorted(by_player.items())},
    }

    # ---- the declared hypothesis ----------------------------------------
    opp = [r for r in gaps if (r['layer'], r['metric']) in
           (('qb', 'att'), ('rushing', 'carries'),
            ('receiving', 'receptions'))]
    eff = [r for r in gaps if (r['layer'], r['metric']) in
           (('qb', 'pyds'), ('qb', 'ptd'), ('qb', 'int'), ('qb', 'ryds'),
            ('receiving', 'receiving_yards'))]
    hyp = {
        'name': 'PLAYER_OPPORTUNITY_ALLOCATION_TOO_DIFFUSE',
        'opportunity_markets': agg(opp, 'opportunity (att/carries/receptions)'),
        'conversion_markets': agg(eff, 'conversion (yards/TD/INT)'),
        'test': 'if the defect were allocation, OPPORTUNITY markets should '
                'disagree in one direction and CONVERSION markets should not '
                'disagree nearly as much. If both disagree equally the cause '
                'is more likely the team-volume level, not the player split.',
    }

    res = {
        'artifact': 'NFL_MKT1_MARKET_DISAGREEMENT_DIAGNOSTIC',
        'diagnostic_only': True, 'model_unchanged': True,
        'no_tuning': 'no price was used as a label, a target or a fit',
        'game_id': art.get('game_id'),
        'forecast_run_id': art.get('spec_hash'),
        'forecast_written_at': art.get('written_at'),
        'draw_content_digest': art.get('draw_content_digest'),
        'model_configuration': art.get('model_configuration'),
        'authorization': 'SHADOW / NOT AUTHORIZED',
        'snapshot': str(a.snapshot),
        'snapshot_sha256': hashlib.sha256(
            pathlib.Path(a.snapshot).read_bytes()).hexdigest(),
        'n_market_rows_returned': len(rows),
        'n_consensus_markets': len(cons),
        'n_comparable': len(gaps),
        'devig_method': 'proportional; approximate, and it flatters the '
                        'favourite slightly because real vig is applied '
                        'asymmetrically',
        'rows': out, 'summary': summary, 'hypothesis': hyp,
    }
    pathlib.Path(a.out).write_text(
        json.dumps(res, indent=1, sort_keys=True, default=str))
    print('comparable markets:', len(gaps), 'of', len(cons))
    o = summary['overall']
    print('overall median disagreement %+.2f pp, model below market in %d/%d'
          % (o['median_disagreement_pp'], o['n_model_below_market'], o['n']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
