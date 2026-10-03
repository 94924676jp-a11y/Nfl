#!/usr/bin/env python3.12
"""Pre-lock triggers: does Sunday's evidence force a re-run before lock?

    python3.12 nfl/tools/classic_prelock.py 2026W4 [--official-inactives FILE] [--confirmed-starters FILE]

FILE formats: inactives = JSON list of player names (the official game-day inactive lists for the
slate's clubs); confirmed starters = JSON {club: quarterback name} from a club or league source.

RERUN_REQUIRED when any of:
  STARTER_ASSUMPTION_BROKEN   a chart-only starter (behind a reported-OUT starter) is inactive, or a
                              confirmed starter for his club is someone else
  INACTIVE_IN_A_LINEUP        a player in any of the owner's lineups is officially inactive
  QUESTIONABLE_RESOLVED       a Questionable/Doubtful player in the pool is now known active or inactive
                              (either way his projection was built on the open question)
AWAITING_OFFICIAL_INACTIVES when no inactive list is supplied: that is not "no change".
NO_RERUN_REQUIRED only when the lists were supplied and none of the above holds.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
NEXT_HEALTHY = 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT'


def evaluate(state, port, inactives=None, confirmed=None):
    chart_only = {v['team']: v for v in state['players'].values()
                  if (v.get('predicted_lineup_context') or {}).get('state') == NEXT_HEALTHY}
    in_lineups = {}
    for c in (port or {}).get('contests', []):
        for _n, e in c['report']['player_exposure'].items():
            in_lineups.setdefault(e['dk_id'], {})[c['profile']] = e['overall']
    watch = [{'club': club, 'player': v['name'], 'evidence': NEXT_HEALTHY, 'exposure': in_lineups.get(dk, {})}
             for dk, v in state['players'].items() for club in [v['team']]
             if (v.get('predicted_lineup_context') or {}).get('state') == NEXT_HEALTHY]
    if inactives is None:
        return Outcome.blocked('AWAITING_OFFICIAL_INACTIVES',
                               f'no official inactive list supplied; {len(watch)} chart-only starter(s) unconfirmed',
                               cause=Cause.DATA, watch=watch)
    out = {n.strip().lower() for n in inactives}
    reasons = []
    for club, v in chart_only.items():
        if v['name'].lower() in out:
            reasons.append({'kind': 'STARTER_ASSUMPTION_BROKEN', 'club': club, 'player': v['name'], 'why': 'inactive'})
        if confirmed and confirmed.get(club) and confirmed[club].strip().lower() != v['name'].lower():
            reasons.append({'kind': 'STARTER_ASSUMPTION_BROKEN', 'club': club, 'player': v['name'],
                            'why': f'confirmed starter is {confirmed[club]}'})
    for dk, ex in in_lineups.items():
        p = state['players'].get(dk) or {}
        if p.get('name', '').lower() in out:
            reasons.append({'kind': 'INACTIVE_IN_A_LINEUP', 'player': p['name'], 'club': p.get('team'), 'exposure': ex})
    for dk, p in state['players'].items():
        if (p['current_availability'].get('designation') or '') in ('QUESTIONABLE', 'DOUBTFUL'):
            reasons.append({'kind': 'QUESTIONABLE_RESOLVED', 'player': p['name'], 'club': p['team'],
                            'now': 'INACTIVE' if p['name'].lower() in out else 'ACTIVE (not on the inactive list)',
                            'exposure': in_lineups.get(dk, {})})
    if reasons:
        return Outcome.fail('RERUN_REQUIRED', f'{len(reasons)} trigger(s): ' + ', '.join(sorted({r["kind"] for r in reasons})),
                            reasons=reasons, watch=watch)
    return Outcome.measured('NO_RERUN_REQUIRED', {'n_checked': len(state['players'])}, n_measured=len(state['players']),
                            what='players checked against the official lists', detail='no trigger fired', watch=watch)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--official-inactives', default=None)
    ap.add_argument('--confirmed-starters', default=None)
    a = ap.parse_args()
    st = json.loads((OUT_DIR / f'DK_{a.slate_id}_EARLY_STATE.json').read_text())
    pp = OUT_DIR / f'DK_{a.slate_id}_EARLY_PORTFOLIOS.json'
    port = json.loads(pp.read_text()) if pp.exists() else None
    ina = json.loads(pathlib.Path(a.official_inactives).read_text()) if a.official_inactives else None
    con = json.loads(pathlib.Path(a.confirmed_starters).read_text()) if a.confirmed_starters else None
    o = evaluate(st, port, ina, con)
    (OUT_DIR / f'DK_{a.slate_id}_EARLY_PRELOCK.json').write_text(json.dumps(
        {'ARTIFACT': 'CLASSIC_PRELOCK', 'slate_id': a.slate_id, 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
         'state': o.state.value, 'code': o.code, 'detail': o.detail, **(o.evidence or {})}, indent=1, default=str))
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
