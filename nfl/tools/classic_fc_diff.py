#!/usr/bin/env python3.12
"""What changed between two FantasyCruncher snapshots, read against OUR football state. Comparison only.

    python3.12 nfl/tools/classic_fc_diff.py 2026W4

FC is EXTERNAL_COMPARISON_ONLY: nothing here enters a projection, and a changed FC number is never a
reason to change ours. A change is MATERIAL (owner's definition, 2026-10-04) when FC's projection moves
>= 1.0, its pDepth changes, its injury flag changes, or its projection crosses zero either way. Each
material change is then classified against our own state:

  OUR_STATE_SUPPORTED        our role/availability already matches what FC moved to (FC caught up),
                             or FC's move has no football counterpart in our evidence
  OUR_EVIDENCE_MAY_BE_STALE  FC's new depth/availability departs from the depth chart we captured, in a
                             direction our usage evidence does not settle -- a Sunday review item
  FC_HAS_NEW_ROLE_INFORMATION FC moved a player out (to 0) or down while our evidence still plays him
  METHODOLOGY                FC's number moved with no depth, injury or zero change (their inputs,
                             e.g. the sportsbook total VegasPts, which our model does not take)

Writes DK_<slate>_EARLY_FC_DIFF.json.
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

from nfl.tools import fc_context as FC                 # noqa: E402
from nfl.tools import availability as AV               # noqa: E402
from sportsplatform.governance.outcome import Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
#: owner's materiality definition (2026-10-04)
PROJ_MOVE = 1.0
FIELDS = ('FC Proj', 'Floor', 'Ceiling', 'pDepth', 'Inj')


def _rank(depth):
    d = ''.join(ch for ch in str(depth or '') if ch.isdigit())
    return int(d) if d else None


def _j(p):
    return json.loads(p.read_text()) if p.exists() else None


def diff(slate):
    keys = FC.HISTORY[slate]
    old_k, new_k = keys[-2], keys[-1]
    lo, ln = FC.load(old_k), FC.load(new_k)
    for o in (lo, ln):
        if o.state.value != 'PASS':
            return o
    st = _j(OUT_DIR / f'DK_{slate}_EARLY_STATE.json')
    proj = (_j(OUT_DIR / f'DK_{slate}_EARLY_PROJ.json') or {}).get('rows', {})
    book = _j(OUT_DIR / f'DK_{slate}_EARLY_RESEARCH_BOOK.json') or {}
    board = {p['dk_id']: p for p in (_j(OUT_DIR / f'DK_{slate}_EARLY_OWNER_BOARD.json') or {}).get('players', [])}
    cards = {c['dk_id']: c for g in book.get('games', {}).values() for t in g['teams'].values() for c in t['players']}
    players = {k: {'name': v['name'], 'team': v['team'], 'position': v['position']} for k, v in st['players'].items()}
    jo, fo_old, _ = FC.join_to_dk(lo.value, players)
    jn, fo_new, _ = FC.join_to_dk(ln.value, players)
    rows = []
    for dk in sorted(set(jo) | set(jn)):
        a = (jo.get(dk) or {}).get(FC.CONTEXT_KEY) or {}
        b = (jn.get(dk) or {}).get(FC.CONTEXT_KEY) or {}
        p = st['players'][dk]
        ch = {f: [a.get(f), b.get(f)] for f in FIELDS if a.get(f) != b.get(f)}
        if (jo.get(dk) or {}).get('fc_pos') != (jn.get(dk) or {}).get('fc_pos'):
            ch['position'] = [(jo.get(dk) or {}).get('fc_pos'), (jn.get(dk) or {}).get('fc_pos')]
        if dk not in jo or dk not in jn:
            ch['in_snapshot'] = [dk in jo, dk in jn]
        if not ch:
            continue
        pa, pb = a.get('FC Proj') or 0.0, b.get('FC Proj') or 0.0
        why = []
        if isinstance(pa, (int, float)) and isinstance(pb, (int, float)) and abs(pb - pa) >= PROJ_MOVE:
            why.append(f'projection {pa:+.2f} -> {pb:.2f}'.replace('+', ''))
        if 'pDepth' in ch:
            why.append(f"pDepth {a.get('pDepth')} -> {b.get('pDepth')}")
        if 'Inj' in ch:
            why.append(f"injury flag {a.get('Inj')!r} -> {b.get('Inj')!r}")
        if (pa or 0) == 0 and (pb or 0) > 0:
            why.append('zero -> nonzero')
        if (pa or 0) > 0 and (pb or 0) == 0:
            why.append('nonzero -> zero')
        if 'in_snapshot' in ch:
            why.append('entered the FC file' if ch['in_snapshot'][1] else 'left the FC file')
        c = cards.get(dk) or {}
        d = c.get('depth') or {}
        av = p['current_availability']
        ours = {'proj': round((proj.get(dk) or {}).get('dk_points') or 0.0, 2), 'sim_mean': (board.get(dk) or {}).get('sim_mean'),
                'role': (board.get(dk) or {}).get('role'), 'chart_rank': d.get('declared_rank'),
                'usage_rank': d.get('measured_usage_rank'), 'projection_rank': d.get('projection_depth_rank'),
                'availability': av['status'], 'designation': av.get('designation'),
                'exposure': {k: (board.get(dk) or {}).get(x) for k, x in (('MAX150', 'exp_150max'), ('MAX20', 'exp_20max'), ('MAX3', 'exp_3entry'))}}
        row = {'player': p['name'], 'team': p['team'], 'position': p['position'], 'dk_id': dk, 'changes': ch,
               'material': bool(why), 'material_because': why, 'ours': ours,
               'OUR_PROJECTION_CHANGED': False,
               'OUR_PROJECTION_NOTE': 'FC is never an input; our projection is the same number before and after this snapshot'}
        if why:
            row['classification'], row['explanation'] = classify(a, b, ours, why)
        rows.append(row)
    mat = [r for r in rows if r['material']]
    doc = {'ARTIFACT': 'CLASSIC_FC_DIFF', 'slate_id': slate, 'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'EXTERNAL_COMPARISON_ONLY': FC.NOT_A_MODEL_INPUT,
           'old': {'key': old_k, 'sha256': lo.evidence.get('sha256'), 'retrieved': FC.SOURCES[old_k][1], 'n_rows': len(lo.value),
                   'path': str(FC.SOURCES[old_k][0].relative_to(_REPO))},
           'new': {'key': new_k, 'sha256': ln.evidence.get('sha256'), 'retrieved': FC.SOURCES[new_k][1], 'n_rows': len(ln.value),
                   'path': str(FC.SOURCES[new_k][0].relative_to(_REPO))},
           'materiality': {'projection_move': PROJ_MOVE, 'pDepth': 'any change', 'injury_flag': 'any change',
                           'zero_crossing': 'either way', 'SOURCE': 'owner 2026-10-04'},
           'n_changed': len(rows), 'n_material': len(mat),
           'by_classification': {k: sum(1 for r in mat if r['classification'] == k) for k in
                                 ('OUR_STATE_SUPPORTED', 'OUR_EVIDENCE_MAY_BE_STALE', 'FC_HAS_NEW_ROLE_INFORMATION', 'METHODOLOGY')},
           'fc_only_new': fo_new, 'rows': sorted(rows, key=lambda r: (not r['material'], -abs(((r['changes'].get('FC Proj') or [0, 0])[1] or 0)
                                                                                            - ((r['changes'].get('FC Proj') or [0, 0])[0] or 0))))}
    (OUT_DIR / f'DK_{slate}_EARLY_FC_DIFF.json').write_text(json.dumps(doc, indent=1, default=str))
    return Outcome.measured('FC_DIFF_BUILT', {'n_material': len(mat)}, n_measured=len(rows), what='players whose FC row changed',
                            detail=f"{len(rows)} FC rows changed, {len(mat)} material: "
                                   + ', '.join(f'{k} {v}' for k, v in doc['by_classification'].items()))


def classify(a, b, ours, why):
    pa, pb = a.get('FC Proj') or 0.0, b.get('FC Proj') or 0.0
    ra, rb = _rank(a.get('pDepth')), _rank(b.get('pDepth'))
    plays = ours['availability'] not in AV.ABSENT_STATUSES and ours['proj'] > 0.5
    our_rank = ours['projection_rank']
    if isinstance(pb, (int, float)) and abs(pb - ours['proj']) < PROJ_MOVE <= abs(pa - ours['proj']):
        return ('OUR_STATE_SUPPORTED', f"FC moved {pa} -> {pb}, onto our number ({ours['proj']}); our role state already "
                                       f"had him there (chart {ours['chart_rank']}, usage {ours['usage_rank']}, projection rank {our_rank}).")
    if 'nonzero -> zero' in why and plays:
        return ('FC_HAS_NEW_ROLE_INFORMATION',
                f"FC now projects 0 (pDepth {b.get('pDepth')}); we still play him at {ours['proj']} with availability "
                f"{ours['availability']} and projection rank {our_rank}. Review on Sunday evidence; do not copy FC.")
    if 'zero -> nonzero' in why and plays:
        return ('OUR_STATE_SUPPORTED', f"FC now projects him ({pb}); we already did ({ours['proj']}, projection rank {our_rank}).")
    if 'zero -> nonzero' in why and not plays:
        return ('FC_HAS_NEW_ROLE_INFORMATION', f"FC now projects {pb}; we project {ours['proj']} ({ours['availability']}). Review.")
    if ra is None and rb is not None:
        if abs((pb or 0) - ours['proj']) < PROJ_MOVE:
            return ('OUR_STATE_SUPPORTED', f"FC added him at {b.get('pDepth')} projecting {pb}; we project {ours['proj']} -- no disagreement.")
        return ('METHODOLOGY', f"FC added him at {b.get('pDepth')} projecting {pb}; we project {ours['proj']} from his own usage "
                               f"(usage rank {ours['usage_rank']}).")
    if rb is not None and ra != rb:
        if our_rank is not None and our_rank == rb:
            return ('OUR_STATE_SUPPORTED', f"FC moved him {a.get('pDepth')} -> {b.get('pDepth')}; our projection rank is already {our_rank}.")
        if ours['chart_rank'] == ra and ours['usage_rank'] not in (None, rb):
            return ('OUR_EVIDENCE_MAY_BE_STALE', f"FC moved him {a.get('pDepth')} -> {b.get('pDepth')}; our captured chart still says "
                                                f"{ours['chart_rank']} and usage says {ours['usage_rank']}. A current chart settles it.")
        if ours['chart_rank'] == ra:
            return ('OUR_EVIDENCE_MAY_BE_STALE', f"FC moved him {a.get('pDepth')} -> {b.get('pDepth')}; our captured chart still says {ours['chart_rank']}.")
        return ('METHODOLOGY', f"FC moved him {a.get('pDepth')} -> {b.get('pDepth')}; our ranks: chart {ours['chart_rank']}, usage "
                               f"{ours['usage_rank']}, projection {our_rank}. Depth labels differ in method.")
    if 'Inj' in ''.join(why) or any(w.startswith('injury flag') for w in why):
        return ('OUR_STATE_SUPPORTED' if ours['designation'] else 'OUR_EVIDENCE_MAY_BE_STALE',
                f"FC injury flag changed; our designation is {ours['designation']} (Friday report).")
    if a.get('VegasPts') != b.get('VegasPts'):
        return ('METHODOLOGY', f"FC moved {pa} -> {pb} with no depth, injury or zero change, after the sportsbook total it uses moved "
                               f"(VegasPts {a.get('VegasPts')} -> {b.get('VegasPts')}); our model never takes a sportsbook number.")
    return ('METHODOLOGY', f"FC moved {pa} -> {pb} with no depth, injury, zero or sportsbook-total change (VegasPts {b.get('VegasPts')} "
                           f"both times): an FC-side model update with no football fact we can check. Ours: {ours['proj']}.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    o = diff(ap.parse_args().slate_id)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
