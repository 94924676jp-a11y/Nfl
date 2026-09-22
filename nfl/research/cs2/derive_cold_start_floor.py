"""The measured cold-start floor: what a player actually takes in his FIRST
appeared NFL game.

Not a chosen constant. It is the empirical distribution of first-game class
share, over every player whose first appeared row is in the historical panel.

MEDIAN, NOT MEAN, and the reason is the same one the preregistration gives for
scoring on MAE: the share distribution is heavily right-skewed. A handful of
backs who walk straight into a lead role pull the mean far above what a
typical debut looks like, and the floor is meant to describe the typical case
a model knows nothing about.
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import p4c_params as P4                  # noqa: E402
from sportsplatform.governance.outcome import State                # noqa: E402

SPEC_VERSION = 'cold-start-floor-1'
POSITIONS = ('RB', 'WR', 'TE', 'FB', 'QB')


def main():
    if P4.ensure_artifacts().state is not State.PASS:
        print('P4C artifacts unavailable')
        return 2
    import p4c_build as B
    B.P4B = str(P4._DIR)
    rows = B.load_panel()

    first = collections.defaultdict(list)
    seen = set()
    for r in sorted(rows, key=lambda x: (x['ord'], x['gsis_id'])):
        pid = r['gsis_id']
        if not r.get('appeared') or pid in seen:
            continue
        seen.add(pid)
        first[r.get('position')].append(
            (float(r.get('s_carries') or 0.0),
             float(r.get('s_targets') or 0.0)))

    floor = {}
    for pos in POSITIONS:
        v = first.get(pos) or []
        if not v:
            continue
        c = [a for a, _ in v]
        t = [b for _, b in v]
        floor[pos] = {
            'n': len(v),
            'carry_share_median': round(statistics.median(c), 8),
            'carry_share_mean': round(statistics.mean(c), 8),
            'target_share_median': round(statistics.median(t), 8),
            'target_share_mean': round(statistics.mean(t), 8),
        }
    out = {
        'spec_version': SPEC_VERSION,
        'what_this_is': 'the class share a player actually took in his FIRST '
                        'appeared game, measured over the historical panel',
        'statistic_used_by_stage6': 'median',
        'why_median': 'the share distribution is right-skewed; the mean is '
                      'pulled up by the few players who debut in a lead role '
                      'and does not describe a typical debut',
        'panel_ord_range': [min(r['ord'] for r in rows),
                            max(r['ord'] for r in rows)],
        'n_players_with_a_first_appeared_row': len(seen),
        'floor': floor,
    }
    p = _REPO / 'nfl/research/cs2/COLD_START_FLOOR.json'
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in floor.items()}, indent=1))
    print(f'wrote {p}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
