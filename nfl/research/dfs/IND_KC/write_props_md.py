"""Shortlist rendered FROM the evaluation JSON. Ranked after calibration."""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
D = _REPO / 'nfl' / 'research' / 'market' / 'SNF_IND_KC_2026W2'
GOOD = ('HIGH', 'MEDIUM')


def _tbl(rows, L, n=15):
    L += ['| player | market | line | side | model p | no-vig p | RAW_EDGE | '
          'ADJ_EDGE | conf | MCSE | mechanism |',
          '|---|---|---|---|---|---|---|---|---|---|---|']
    for x in rows[:n]:
        L.append(
            f"| {x['player']} | {x['market']} | {x['line']} | "
            f"{x['model_side']} | {x['model_probability']:.4f} | "
            f"{x['novig_probability']:.4f} | {x['RAW_EDGE']:+.4f} | "
            f"**{x['CALIBRATION_ADJUSTED_EDGE']:+.4f}** | "
            f"`{x['CALIBRATION_ADJUSTED_CONFIDENCE']}` | "
            f"{x['mcse_over']:.4f} | "
            f"{x['correlated_signal_group_mechanism'].split(':')[-1]} |")
    L.append('')


def main():
    import os
    src = os.environ.get('PROPS_OUT', 'IND_KC_PROPS_PREINACTIVES_2026W2.json')
    d = json.loads((D / src).read_text())
    ms, cal, m = d['market_snapshot'], d['calibration_layer'], d['model']
    r = [x for x in d['rows'] if x['support'] == 'EXACT_SIMULATION_SUPPORTED']
    e = [x for x in r if x.get('RAW_EDGE') is not None]
    ok = [x for x in e if x['CALIBRATION_ADJUSTED_CONFIDENCE'] in GOOD]
    ok.sort(key=lambda x: -x['CALIBRATION_ADJUSTED_EDGE'])
    sides = collections.Counter(x['model_side'] for x in e)
    L = [f"# IND@KC — model vs Hard Rock — {d['LABEL']}", '',
         f"Board `{ms['sha256'][:16]}…` captured "
         f"{ms['capture_window_utc'][0]}–{ms['capture_window_utc'][-1]} · "
         f"{ms['n_rows']} rows ({ms['n_main_line']} main, "
         f"{ms['n_alternate_line']} alternate)", '',
         f"Model run `{m['run_id']}` · {m['n_draws']:,} draws · cut "
         f"`{m['information_cut']}` · {m['candidate_status']} · "
         f"inactive gate **{m['inactive_gate']}**", '',
         ms['handling'], '',
         '## Read this before ranking anything', '',
         f"Week-2 grading measured a mean predicted probability of "
         f"{cal['by_family'] and ''}"
         f"{(cal['overall_gap']):+.4f} gap between what the model said and "
         f"what happened, over {cal['overall_n']} graded markets across "
         f"{cal['n_game_clusters']} games. {cal['warning']}", '',
         f"On this board the model again leans one way: "
         f"**{sides.get('UNDER', 0)} UNDER against {sides.get('OVER', 0)} "
         f"OVER** among {len(e)} two-sided markets. Mean RAW_EDGE is "
         f"{sum(x['RAW_EDGE'] for x in e) / len(e):+.4f}; after applying the "
         f"Week-2 family gaps it is "
         f"{sum(x['CALIBRATION_ADJUSTED_EDGE'] for x in e) / len(e):+.4f}. "
         f"The calibration layer removes about "
         f"{100 * (1 - (sum(x['CALIBRATION_ADJUSTED_EDGE'] for x in e) / sum(x['RAW_EDGE'] for x in e))):.0f}% "
         f"of the claimed edge. **Do not rank by RAW_EDGE.**", '',
         '| confidence label | n |', '|---|---|']
    for k, v in collections.Counter(
            x['CALIBRATION_ADJUSTED_CONFIDENCE'] for x in r).most_common():
        L.append(f"| `{k}` | {v} |")
    L += ['', '## Strongest supported props (any line type), ranked AFTER '
          'calibration', '']
    _tbl(ok, L, 18)
    main_ = [x for x in ok if x['is_main_line']]
    L += ['## Strongest MAIN-LINE props', '']
    if main_:
        _tbl(main_, L, 12)
    else:
        L += ['No main line survives the calibration filter at MEDIUM or '
              'better. That is a result, not an omission.', '']
    alt = [x for x in ok if not x['is_main_line']]
    L += ['## Strongest ALTERNATE-LINE props', '',
          'Alternate lines are kept strictly separate from main lines. They '
          'are the same opinion about a player expressed at a different '
          'threshold, so they are not additional evidence.', '']
    _tbl(alt, L, 12)
    avoid = [x for x in e
             if x['CALIBRATION_ADJUSTED_CONFIDENCE'].startswith('AVOID')]
    avoid.sort(key=lambda x: -x['RAW_EDGE'])
    L += ['## Avoid despite a large RAW_EDGE', '',
          'These carry the biggest raw numbers on the board and do not '
          'survive the Week-2 correction. Last week these are exactly the '
          'rows that lost.', '']
    _tbl(avoid, L, 15)
    L += ['## Correlated signals — one opinion counted once', '',
          'Markets sharing a player, or sharing a team allocation mechanism, '
          'move together. Treating them as independent is how a single role '
          'error becomes a whole portfolio.', '',
          '| group | markets on the board | in the shortlist |',
          '|---|---|---|']
    gp = collections.Counter(x['correlated_signal_group_player'] for x in e)
    gs = collections.Counter(x['correlated_signal_group_player'] for x in ok)
    for k, v in gp.most_common(14):
        L.append(f"| {k} | {v} | {gs.get(k, 0)} |")
    gm = collections.Counter(x['correlated_signal_group_mechanism']
                             for x in ok)
    L += ['', '| allocation mechanism | shortlisted markets |', '|---|---|']
    for k, v in gm.most_common():
        L.append(f"| {k} | {v} |")
    L += ['', '## Refused rather than approximated', '', '| reason | n |',
          '|---|---|']
    for k, v in d['counts'].items():
        if k != 'EXACT_SIMULATION_SUPPORTED':
            L.append(f"| `{k}` | {v} |")
    L += ['', 'Every probability above is counted from the frozen draws: the '
          'fraction of the 8,000 simulated games in which the quantity beat '
          'the line. No normal approximation is used anywhere, and a market '
          'whose settling quantity is not in the sealed artifact is refused '
          'by name.', '',
          '## When inactives land', '',
          'Capture a second Hard Rock board and re-evaluate **these same '
          'frozen draws** at the new lines. The football projection is not '
          'rerun because a price moved. The comparison will report line '
          'movement, price movement, new and removed markets, and whether '
          'movement ran toward or away from the model.', '',
          'V2 NOT YET EARNED.']
    t = '\n'.join(L) + '\n'
    out = src.replace('.json', '.md')
    (D / out).write_text(t)
    print(f'wrote {out} {len(t)} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
