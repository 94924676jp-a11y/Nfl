"""Re-run Q7's own forward chain on the superseded panel and on the corrected one.

    python3.12 nfl/research/v4/p5/rerun_q7.py --panel old
    python3.12 nfl/research/v4/p5/rerun_q7.py --panel new

WHY A DRIVER RATHER THAN `analyse.main()`.

`nfl/research/q7/analyse.py` writes to fixed paths inside `nfl/research/q7/`.
Running it would overwrite the published Q7 artifacts -- the very things the
before/after comparison is about. This driver calls the same two functions,
`forward_chain.run` and `analyse.summarise`, and writes beside them instead.
Neither `forward_chain.py` nor `analyse.py` is modified.

THE OLD ARM IS A HARNESS CHECK, NOT JUST A BASELINE. `--panel old` points the
loader at the superseded artifact and must reproduce the published
`Q7_FORWARD_CHAIN_RESULTS.json`. If it does not, the comparison measures this
driver rather than the panel repair, and the report says so.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.q7 import panel as PAN                          # noqa: E402

HERE = _REPO / 'nfl' / 'research' / 'v4' / 'p5'
PANELS = {'old': PAN.SUPERSEDED_QB, 'new': PAN.QB}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--panel', choices=sorted(PANELS), required=True)
    ap.add_argument('--seasons', default='')
    ap.add_argument('--draws', type=int, default=0)
    a = ap.parse_args(argv)

    qb_path = PANELS[a.panel]
    if not qb_path.exists():
        raise SystemExit(f'P5_PANEL_MISSING: {qb_path}')
    # point the loader at the chosen panel BEFORE importing the chain, so the
    # chain's own module-level constants cannot capture the other one
    PAN.QB = qb_path
    from nfl.research.q7 import analyse as AN                      # noqa: E402
    from nfl.research.q7 import forward_chain as FC                # noqa: E402

    seasons = (tuple(int(x) for x in a.seasons.split(','))
               if a.seasons else FC.EVAL_SEASONS)
    draws = a.draws or FC.N_DRAWS
    rows = PAN.load_qb()
    print(f'panel {a.panel}: {qb_path.name}  {len(rows)} qb-games  '
          f'scr {sum(r["scr"] for r in rows)}  db {sum(r["db"] for r in rows)}',
          flush=True)

    t0 = time.time()
    res = FC.run(seasons, draws)
    print(f'  chain {time.time() - t0:.0f}s  rows {len(res["rows"])}',
          flush=True)
    t1 = time.time()
    s = AN.summarise(res)
    s['n_draws'] = draws
    s['p5_panel_arm'] = a.panel
    s['p5_panel_path'] = str(qb_path.relative_to(_REPO))
    s['p5_panel_qb_games'] = len(rows)
    s['p5_panel_scrambles'] = sum(r['scr'] for r in rows)
    s['p5_panel_dropbacks'] = sum(r['db'] for r in rows)
    print(f'  summarise {time.time() - t1:.0f}s', flush=True)

    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / f'Q7_RESULTS_{a.panel.upper()}_PANEL.json').write_text(
        json.dumps(s, indent=1, default=str) + '\n')
    AN.write_rows(res['rows'], HERE / f'Q7_SCORED_ROWS_{a.panel.upper()}.csv.gz')
    AN.write_rows(res['composed'],
                  HERE / f'Q7_DIAGNOSTICS_{a.panel.upper()}.csv', gz=False)
    print(f"decision {s['decision']['decision']} ({s['decision']['arm']})")
    for arm, d in s['decision_by_arm'].items():
        print(f"  {arm:12s} -> {d['decision']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
