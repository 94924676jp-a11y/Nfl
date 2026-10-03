#!/usr/bin/env python3.12
"""What changed between the previous classic-slate run and this one, and why.

    python3.12 nfl/tools/classic_change_log.py 2026W4 [--against nfl/dfs/salaries/runs/2026W4/<utc>]

Owner priority 18. Compares the snapshot the pipeline took before re-running with the current artifacts:
per player OLD PROJ / NEW PROJ / CHANGE / CAUSE and OLD/NEW exposure in each contest; lineup turnover;
game-exposure and stack changes; and prop probability changes when both runs hold a prop diagnostic.
A CAUSE is read from the two states (availability, designation, depth rank, starter evidence); when
none of those changed for the player the cause is 'reallocation inside the club', and it says so.
Writes DK_<slate>_EARLY_RUN_CHANGES.json.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
#: DECLARED reporting threshold for a projection change worth a row
MIN_CHANGE = 0.5


def _j(p):
    return json.loads(p.read_text()) if p.exists() else None


def _expo(port):
    out = collections.defaultdict(dict)
    for c in (port or {}).get('contests', []):
        for _n, e in c['report']['player_exposure'].items():
            out[e['dk_id']][c['profile']] = e['overall']
    return out


def _cause(a, b):
    if not a:
        return 'new to the slate'
    why = []
    sa, sb = a['current_availability'], b['current_availability']
    if sa.get('status') != sb.get('status'):
        why.append(f"availability {sa.get('status')} -> {sb.get('status')}")
    if sa.get('designation') != sb.get('designation'):
        why.append(f"designation {sa.get('designation')} -> {sb.get('designation')}")
    if a.get('depth_rank') != b.get('depth_rank'):
        why.append(f"depth rank {a.get('depth_rank')} -> {b.get('depth_rank')}")
    ca, cb = (a.get('predicted_lineup_context') or {}).get('state'), (b.get('predicted_lineup_context') or {}).get('state')
    if ca != cb:
        why.append(f'starter evidence {ca} -> {cb}')
    return '; '.join(why) or 'reallocation inside the club (his own evidence did not change)'


def build(slate, against=None):
    if against is None:
        lp = OUT_DIR / 'runs' / slate / 'LATEST_SNAPSHOT'
        if not lp.exists():
            return Outcome.blocked('CHANGE_LOG_NO_SNAPSHOT', 'no previous run snapshot', cause=Cause.NOT_EXECUTED)
        against = OUT_DIR / 'runs' / slate / lp.read_text().strip()
    against = pathlib.Path(against)
    if not against.is_absolute():
        against = _REPO / against
    old = {n: _j(against / f'DK_{slate}_EARLY_{n}') for n in ('STATE.json', 'PROJ.json', 'PORTFOLIOS.json', 'PROP_DIAGNOSTIC.json')}
    new = {n: _j(OUT_DIR / f'DK_{slate}_EARLY_{n}') for n in old}
    if not new['PROJ.json'] or not old['PROJ.json']:
        return Outcome.blocked('CHANGE_LOG_INPUT_MISSING', 'both runs need a projection', cause=Cause.NOT_EXECUTED)
    eo, en = _expo(old['PORTFOLIOS.json']), _expo(new['PORTFOLIOS.json'])
    rows = []
    po, pn = old['PROJ.json']['rows'], new['PROJ.json']['rows']
    for dk in sorted(set(po) | set(pn)):
        a, b = po.get(dk) or {}, pn.get(dk) or {}
        x, y = a.get('dk_points') or 0.0, b.get('dk_points') or 0.0
        ex_o, ex_n = eo.get(dk, {}), en.get(dk, {})
        moved_expo = any(abs(ex_o.get(k, 0) - ex_n.get(k, 0)) >= 0.05 for k in ('MAX150', 'MAX20', 'MAX3'))
        if abs(y - x) < MIN_CHANGE and not moved_expo:
            continue
        rows.append({'player': b.get('name') or a.get('name'), 'team': b.get('team') or a.get('team'),
                     'old_proj': round(x, 2), 'new_proj': round(y, 2), 'change': round(y - x, 2),
                     'cause': _cause((old['STATE.json'] or {}).get('players', {}).get(dk),
                                     (new['STATE.json'] or {}).get('players', {}).get(dk) or {'current_availability': {}}),
                     'old_150': ex_o.get('MAX150'), 'new_150': ex_n.get('MAX150'),
                     'old_20': ex_o.get('MAX20'), 'new_20': ex_n.get('MAX20'),
                     'old_3': ex_o.get('MAX3'), 'new_3': ex_n.get('MAX3')})
    rows.sort(key=lambda r: -abs(r['change']))
    contests = {}
    for co in (old['PORTFOLIOS.json'] or {}).get('contests', []):
        cn = next((c for c in (new['PORTFOLIOS.json'] or {}).get('contests', []) if c['profile'] == co['profile']), None)
        if not cn:
            continue
        so = {frozenset(s['dk_id'] for s in lu['slots']) for lu in co['lineups']}
        sn = {frozenset(s['dk_id'] for s in lu['slots']) for lu in cn['lineups']}
        ge_o, ge_n = co['report']['game_exposure'], cn['report']['game_exposure']
        st_o, st_n = co['report']['stack_table'], cn['report']['stack_table']
        contests[co['profile']] = {
            'lineups_kept': len(so & sn), 'lineups_new': len(sn - so), 'of': len(sn),
            'game_exposure_change': {g: round(ge_n.get(g, 0) - ge_o.get(g, 0), 3) for g in sorted(set(ge_o) | set(ge_n))},
            'stack_change': {k: round(st_n.get(k, 0) - st_o.get(k, 0), 3) for k in sorted(set(st_o) | set(st_n))},
            'qb_exposure_old': dict(list(co['report']['qb_exposure'].items())[:5]),
            'qb_exposure_new': dict(list(cn['report']['qb_exposure'].items())[:5])}
    props = None
    if old['PROP_DIAGNOSTIC.json'] and new['PROP_DIAGNOSTIC.json']:
        ko = {(r['player'], r['market'], r['hard_rock_line']): r['p_over'] for r in old['PROP_DIAGNOSTIC.json']['rows']}
        props = [{'player': r['player'], 'market': r['market'], 'line': r['hard_rock_line'],
                  'old_p_over': ko.get((r['player'], r['market'], r['hard_rock_line'])), 'new_p_over': r['p_over']}
                 for r in new['PROP_DIAGNOSTIC.json']['rows'] if (r['player'], r['market'], r['hard_rock_line']) in ko
                 and abs(ko[(r['player'], r['market'], r['hard_rock_line'])] - r['p_over']) >= 0.02]
    doc = {'ARTIFACT': 'CLASSIC_RUN_CHANGES', 'slate_id': slate, 'against': str(against.relative_to(_REPO)),
           'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'players': rows, 'contests': contests,
           'props': props if props is not None else 'one or both runs hold no prop diagnostic'}
    (OUT_DIR / f'DK_{slate}_EARLY_RUN_CHANGES.json').write_text(json.dumps(doc, indent=1))
    return Outcome.measured('CHANGE_LOG_BUILT', {'n_players': len(rows)}, n_measured=len(rows), what='player rows',
                            detail=f'{len(rows)} player rows; lineups kept ' + ', '.join(
                                f"{k} {v['lineups_kept']}/{v['of']}" for k, v in contests.items()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--against', default=None)
    a = ap.parse_args()
    o = build(a.slate_id, a.against)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
