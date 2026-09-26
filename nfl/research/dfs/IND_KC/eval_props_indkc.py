"""Evaluate the IND@KC Hard Rock board against the frozen simulation draws.

DIRECTION OF FLOW, STATED ONCE AND ENFORCED BY STRUCTURE

Draws -> probabilities -> comparison against a price. Never the reverse. This
module is not imported by anything in the forecast path, and no line, price,
spread, total or implied probability it reads can reach a projection. The
football numbers were frozen by run 44fccb9d9f0458a6 before this board was
ever opened.

EXACT COUNTING, NEVER A NORMAL APPROXIMATION

P(over) is the fraction of the 8,000 simulated games in which the quantity
exceeded the line; P(under) and P(push) likewise. No mean, no standard
deviation and no Gaussian tail is used anywhere. A market whose settling
quantity is not in the sealed artifact is refused BY NAME rather than
approximated from one that is.

THE CALIBRATION LAYER EXISTS BECAUSE LAST WEEK'S EDGES WERE OVERSTATED

Week-2 grading measured a mean predicted probability of 0.6315 against a
realised 0.5361 over 263 graded markets, with the book beating the model on
both Brier and log loss. RAW_EDGE is therefore reported UNCHANGED, and a
separate CALIBRATION_ADJUSTED_CONFIDENCE applies the per-family gap measured
that week. The adjustment is a WARNING, not a corrected probability: it comes
from one slate of seven games with wide game-clustered standard errors, and
it is never silently folded into the model number.

CORRELATED SIGNALS ARE GROUPED, NOT COUNTED TWICE

Eight markets on one receiver are one opinion about his role expressed eight
times. Every row carries its player group and its allocation-mechanism group
so a downstream selector cannot treat them as independent evidence.
"""
from __future__ import annotations

import collections
import csv
import datetime as _dt
import hashlib
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import build_postinactives_package as B  # noqa: E402
from nfl.market import evaluate as EV, odds as OD  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

import os as _os

SPEC_VERSION = 'nfl-showdown-prop-eval-1'
#: The same frozen 22:52Z board is re-evaluated against whichever draw set is
#: named. A price moving never reruns football, and football moving never
#: rewrites the board -- the two axes are changed one at a time and on
#: purpose.
PHASE = _os.environ.get('PROPS_PHASE', 'PREINACTIVES_MARKET')
RUNS_GLOB = _os.environ.get('PROPS_RUNS', '/tmp/claude-0/indkc/*/')
OUT_NAME = _os.environ.get(
    'PROPS_OUT', 'IND_KC_PROPS_PREINACTIVES_2026W2.json')
BOARD = ('nfl/research/market/SNF_IND_KC_2026W2/raw/'
         'SNF_IND_KC_hardrock_PREINACTIVES_2026-09-20T2252Z.csv')
BOARD_SHA = 'f6e4b8e611cb085dda28f2cc7b4bebd7bc2ef9c2c03c787eea0e46f03d4398f6'
WEEK2 = 'nfl/research/postgame/week2_postgame_summary.json'
PKG = _os.environ.get(
    'PROPS_PKG', 'nfl/research/sunday/IND_KC_SHOWDOWN_PREINACTIVES_2026W2.json')

#: Markets the sealed artifact CAN settle that the shared map does not carry.
#: Total touchdowns SCORED is rushing plus receiving within the same draw. A
#: quarterback's is his rushing score only -- a thrown touchdown is not one he
#: scored -- and mixing the two compositions under one name would answer two
#: different questions, so the QB case is refused rather than guessed.
EXTRA_MARKETS = {
    'Player Touchdowns': {'sum': [('rushing', 'rushing_td'),
                                  ('receiving', 'receiving_td')],
                          'not_for_positions': ('QB',),
                          'note': 'touchdowns SCORED, added within each draw'},
}
#: Families whose Week-2 sample was too thin to carry their own adjustment.
MIN_FAMILY_N = 20


def _norm_fam(m):
    return m


def load_calibration():
    s = json.loads((_REPO / WEEK2).read_text())
    p = s['prop_calibration']
    fam = {f['market']: {'n': f['n'], 'gap': f['gap'],
                         'se_clustered_by_game': f['se_clustered_by_game'],
                         'realized': f['realized'],
                         'mean_predicted': f['mean_predicted']}
           for f in p['by_market_family']}
    return {'overall_gap': round(p['realized_hit_rate']
                                 - p['mean_predicted_probability'], 6),
            'overall_n': p['n_graded'],
            'n_game_clusters': p['n_game_clusters'],
            'by_family': fam,
            'provenance': 'measured on the Week-2 graded board, 7 games',
            'warning': 'one slate, heavily overlapping markets, wide '
                       'game-clustered standard errors. A shrink toward the '
                       'book, not a corrected probability.'}


def build(run_dir) -> Outcome:
    p = _REPO / BOARD
    if not p.exists():
        return Outcome.blocked('MARKET_BOARD_MISSING', str(p),
                               cause=Cause.DATA)
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != BOARD_SHA:
        return Outcome.blocked(
            'MARKET_BOARD_BYTES_CHANGED',
            f'{h[:16]} != {BOARD_SHA[:16]}; an evaluation against different '
            f'bytes is a different evaluation', cause=Cause.DATA)
    rows_in = list(csv.DictReader(open(p, newline='')))
    if not rows_in:
        return Outcome.blocked('MARKET_BOARD_EMPTY', str(p), cause=Cause.DATA)

    run = B.read_run(run_dir)
    cal = load_calibration()
    pkg = json.loads((_REPO / PKG).read_text())
    flagged = {f['gsis_id'] for f in pkg['gates']['role_plausibility_flags']}
    flag_by_name = {f['player']: f['flag']
                    for f in pkg['gates']['role_plausibility_flags']}
    name_to_pid, pos_by_pid = {}, {}
    for pl in pkg['players']:
        name_to_pid[pl['player']] = pl['gsis_id']
        pos_by_pid[pl['gsis_id']] = pl['position']

    mc = _dt.datetime.fromisoformat(
        run['written_at'].replace('Z', '+00:00'))
    out, counts = [], collections.Counter()

    for r in rows_in:
        market = r['market']
        base = {
            'game_id': r['game_id'], 'game': r['game'],
            'player': r['player'], 'displayed_selection':
                r['displayed_selection'],
            'team': r['team'], 'opponent': r['opponent'],
            'book_position': r['position'],
            'market': market, 'market_id': r['market_id'],
            'market_class': r['market_class'],
            'is_main_line': r['is_main_line'] == 'True',
            'line_type': ('MAIN_LINE' if r['is_main_line'] == 'True'
                          else 'ALTERNATE_LINE'),
            'line': r['line'], 'over_price': r['over_price'],
            'under_price': r['under_price'],
            'selection_price': r['selection_price'],
            'market_status': r['market_status'],
            'sportsbook': r['book'],
            'retrieved_at_utc': r['retrieved_at_utc'],
            'book_line_timestamp_utc': r['book_line_timestamp_utc'],
            'odds_id_over': r['odds_id_over'],
            'odds_id_under': r['odds_id_under'],
            'source_url': r['source_url'],
            'source_endpoint': r['source_endpoint'],
            'evidence_type': r['evidence_type'],
            'raw_file': r['raw_file'],
            'model_information_cut': run['written_at'],
            'model_run_id': run['run_id'],
        }
        for k in ('retrieved_at_utc', 'book_line_timestamp_utc'):
            try:
                t = _dt.datetime.fromisoformat(r[k].replace('Z', '+00:00'))
                base[f'seconds_from_model_cut_to_{k}'] = int(
                    (t - mc).total_seconds())
            except (ValueError, AttributeError):
                base[f'seconds_from_model_cut_to_{k}'] = None

        if r['market_class'] != 'player_prop':
            base.update(support='NOT_A_PLAYER_PROP',
                        why='game-level market; this evaluator scores player '
                            'props only and does not approximate one from '
                            'the other')
            counts['NOT_A_PLAYER_PROP'] += 1
            out.append(base)
            continue

        pid = name_to_pid.get(r['player'])
        if pid is None:
            base.update(support='IDENTITY_UNRESOLVED',
                        why='no emitted model row answers to this displayed '
                            'name; no edit-distance matching is permitted')
            counts['IDENTITY_UNRESOLVED'] += 1
            out.append(base)
            continue
        base['gsis_id'] = pid
        base['model_position'] = pos_by_pid.get(pid)

        spec = EV.MARKET_MAP.get(market) or EXTRA_MARKETS.get(market)
        if spec is None:
            base.update(
                support='UNSUPPORTED_MARKET',
                why=EV.UNSUPPORTED_MARKETS.get(
                    market, f'{market!r} has no declared mapping to a sealed '
                            f'quantity, and an approximation is worse than a '
                            f'refusal'))
            counts['UNSUPPORTED_MARKET'] += 1
            out.append(base)
            continue
        if base['model_position'] in (spec.get('not_for_positions') or ()):
            base.update(support='UNSUPPORTED_COMPOSITION_FOR_POSITION',
                        why=f'{market!r} settles on a different composition '
                            f'for a {base["model_position"]}; refused rather '
                            f'than guessed')
            counts['UNSUPPORTED_COMPOSITION_FOR_POSITION'] += 1
            out.append(base)
            continue

        met = run['stats'].get(pid) or {}
        if 'sum' in spec:
            parts = [met.get(f'{l}/{m}') for l, m in spec['sum']]
            if any(x is None for x in parts):
                base.update(support='UNSUPPORTED',
                            why='a component layer is absent for this player')
                counts['UNSUPPORTED'] += 1
                out.append(base)
                continue
            x = np.sum(parts, axis=0)
            src = '+'.join(f'{l}/{m}' for l, m in spec['sum'])
        else:
            src = f"{spec['layer']}/{spec['metric']}"
            x = met.get(src)
            if x is None:
                base.update(support='UNSUPPORTED',
                            why=f'{src} absent for this player')
                counts['UNSUPPORTED'] += 1
                out.append(base)
                continue
        try:
            line = float(r['line'])
        except (TypeError, ValueError):
            base.update(support='UNPARSEABLE_LINE', why=f'line={r["line"]!r}')
            counts['UNPARSEABLE_LINE'] += 1
            out.append(base)
            continue

        ev = EV.evaluate_line(x, line)
        dv = OD.devig(r['over_price'] or None, r['under_price'] or None)
        base.update(
            support='EXACT_SIMULATION_SUPPORTED', draw_source=src,
            n_draws=ev['n_draws'], method=ev['method'],
            model_p_over=round(ev['p_over'], 6),
            model_p_under=round(ev['p_under'], 6),
            model_p_push=round(ev['p_push'], 6),
            mcse_over=round(ev['mcse_over'], 6),
            model_mean=round(ev['mean'], 4),
            model_median=round(ev['median'], 4),
            model_p25=round(ev['p25'], 4), model_p75=round(ev['p75'], 4),
            model_p95=round(ev['p95'], 4),
            novig_p_over=(round(dv['novig_p_over'], 6)
                          if dv.get('novig_p_over') is not None else None),
            novig_p_under=(round(dv['novig_p_under'], 6)
                           if dv.get('novig_p_under') is not None else None),
            book_hold=(round(dv['hold'], 6)
                       if dv.get('hold') is not None else None),
            devig_code=dv.get('devig_status'),
            devig_method=dv.get('devig_method'),
            role_uncertainty=(flag_by_name.get(r['player'])
                              if pid in flagged else None),
            role_uncertainty_effect=(
                'the workload behind this line is a MODEL ROLE ASSUMPTION '
                'the club depth chart does not support' if pid in flagged
                else None),
            correlated_signal_group_player=f"{r['team']}:{r['player']}",
            correlated_signal_group_mechanism=(
                f"{r['team']}:{'pass_allocation' if 'Receiv' in market or market == 'Player Receptions' else 'rush_allocation' if 'Rushing' in market else 'qb_aggregate' if 'Passing' in market or market == 'Player Interceptions' else 'kicking' if 'Field Goal' in market or 'Kicking' in market else 'other'}"),
        )
        if dv.get('novig_p_over') is not None:
            side = ('OVER' if ev['p_over'] - dv['novig_p_over']
                    >= ev['p_under'] - dv['novig_p_under'] else 'UNDER')
            mp = ev['p_over'] if side == 'OVER' else ev['p_under']
            bp = (dv['novig_p_over'] if side == 'OVER'
                  else dv['novig_p_under'])
            raw = mp - bp
            f = cal['by_family'].get(market)
            use_family = bool(f and f['n'] >= MIN_FAMILY_N)
            gap = f['gap'] if use_family else cal['overall_gap']
            adj = min(max(mp + gap, 0.01), 0.99)
            adj_edge = adj - bp
            mcse = ev['mcse_over']
            if pid in flagged:
                conf = 'AVOID_ROLE_ASSUMPTION_NOT_SUPPORTED_BY_DEPTH_CHART'
            elif adj_edge <= 0 and raw > 0.05:
                conf = 'AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION'
            elif adj_edge <= 0:
                conf = 'NO_EDGE_AFTER_CALIBRATION'
            elif adj_edge >= 0.05 and adj_edge >= 3 * mcse and use_family:
                conf = 'HIGH'
            elif adj_edge >= 2 * mcse:
                conf = 'MEDIUM'
            else:
                conf = 'LOW_EDGE_INSIDE_TWO_MCSE'
            base.update(
                model_side=side, model_probability=round(mp, 6),
                novig_probability=round(bp, 6),
                RAW_EDGE=round(raw, 6),
                calibration_gap_applied=round(gap, 6),
                calibration_gap_source=('WEEK2_FAMILY' if use_family
                                        else 'WEEK2_OVERALL_FAMILY_TOO_THIN'),
                calibration_family_n=(f['n'] if f else 0),
                calibration_adjusted_probability=round(adj, 6),
                CALIBRATION_ADJUSTED_EDGE=round(adj_edge, 6),
                CALIBRATION_ADJUSTED_CONFIDENCE=conf,
                edge_to_mcse_ratio=(round(adj_edge / mcse, 3) if mcse else
                                    None))
        else:
            base.update(
                model_side=None, RAW_EDGE=None,
                CALIBRATION_ADJUSTED_EDGE=None,
                CALIBRATION_ADJUSTED_CONFIDENCE='NO_EDGE_COMPUTABLE',
                why_no_edge='only one side is priced, so there is no pair to '
                            'normalise and no no-vig book probability. The '
                            'model probability above is still exact.')
        counts['EXACT_SIMULATION_SUPPORTED'] += 1
        out.append(base)

    return Outcome.ok('PROPS_EVALUATED', value={
        'LABEL': PHASE,
        'market_board_phase': 'PREINACTIVES_MARKET',
        'market_board_note':
            'The Hard Rock board is the 22:52Z PRE-INACTIVES capture in both '
            'phases. Only the draws change between them, so a difference '
            'between the two evaluations is a football difference and not a '
            'price difference.',
        'spec_version': SPEC_VERSION,
        'generated_at_utc': _dt.datetime.now(_dt.UTC).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
        'market_snapshot': {
            'book': 'Hard Rock Bet',
            'raw_file': BOARD, 'sha256': BOARD_SHA,
            'capture_window_utc': sorted(
                {r['retrieved_at_utc'] for r in rows_in}),
            'n_rows': len(rows_in),
            'n_main_line': sum(1 for r in rows_in
                               if r['is_main_line'] == 'True'),
            'n_alternate_line': sum(1 for r in rows_in
                                    if r['is_main_line'] != 'True'),
            'market_status_counts': dict(collections.Counter(
                r['market_status'] for r in rows_in)),
            'handling': 'DOWNSTREAM_COMPARISON_ONLY. No line, price, spread, '
                        'total or implied probability entered the football '
                        'model. The draws were frozen before this file was '
                        'opened.',
        },
        'model': {'run_id': run['run_id'], 'n_draws': run['n_draws'],
                  'information_cut': run['written_at'],
                  'execution_identity': run['execution_identity'],
                  'draw_content_digest': run['content_digest'],
                  'candidate_status': 'CANDIDATE_NOT_ACCEPTED_BASELINE',
                  'inactive_gate': pkg['gates']['inactive_gate']},
        'calibration_layer': cal,
        'counts': dict(counts),
        'rows': out,
    }, n_rows=len(out), counts=dict(counts))


def main():
    import glob
    dirs = sorted(glob.glob(RUNS_GLOB))
    if not dirs:
        print('BLOCKED[NO_RUN_DIRECTORY]')
        return 1
    o = build(dirs[-1])
    if o.state.name != 'PASS':
        print(f'{o.state.name}[{o.code}] {o.detail}')
        return 1
    p = (_REPO / 'nfl' / 'research' / 'market' / 'SNF_IND_KC_2026W2'
         / OUT_NAME)
    p.write_text(json.dumps(o.value, indent=1, sort_keys=True) + '\n')
    print(f'wrote {p.name} {p.stat().st_size} bytes')
    print('counts:', o.evidence['counts'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
