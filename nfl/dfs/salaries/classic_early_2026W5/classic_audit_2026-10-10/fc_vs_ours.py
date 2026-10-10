#!/usr/bin/env python3.12
"""Fantasy Cruncher (owner export) against our projection of record. EXTERNAL COMPARISON ONLY.

    python3.12 fc_vs_ours.py FC_NEW.csv FC_OLD.csv BUILD_DIR OUT.json

Reads our build (STATE, PROJ, DRAWS) as data and imports no projection module. Nothing here is written
back into any forecast. Players are matched on case/punctuation-normalised name plus club, then on a
declared generational suffix; nothing fuzzier. Unmatched rows are listed, never guessed.
"""
import collections
import csv
import gzip
import hashlib
import json
import pathlib
import re
import statistics
import sys


def norm(s):
    s = s.lower().replace('-', ' ')
    s = re.sub(r"[.,'’`]", '', s)
    s = ' '.join(s.split())
    for suf in (' jr', ' sr', ' ii', ' iii', ' iv', ' v'):
        if s.endswith(suf):
            s = s[:-len(suf)].strip()
    return s


def fc_rows(p):
    rows = list(csv.reader(open(p, newline='', encoding='utf-8-sig')))
    hi = next(i for i, r in enumerate(rows[:5]) if 'Player' in r and 'FC Proj' in r)
    hdr = rows[hi]
    return [dict(zip(hdr, r)) for r in rows[hi + 1:] if r and r[0].strip()]


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main(fc_new, fc_old, build, out):
    build = pathlib.Path(build)
    st = json.loads((build / 'STATE.json').read_text())
    pj = json.load(gzip.open(build / 'PROJ.json.gz'))
    dr = json.load(gzip.open(build / 'DRAWS.json.gz'))
    ours = {}
    for pid, r in pj['rows'].items():
        sp = st['players'].get(pid) or {}
        w = dr['draws'].get(f"{r['name']}|{r['team']}")
        ours[(norm(r['name']), r['team'])] = {
            'name': r['name'], 'team': r['team'], 'pos': r['position'], 'dk_points': r.get('dk_points'),
            'dk_points_if_plays': r.get('dk_points_if_plays'), 'role_state': r.get('role_state'),
            'projection_state': r.get('projection_state'), 'availability': r.get('availability'),
            'designation': (sp.get('current_availability') or {}).get('designation'),
            'depth_rank': sp.get('depth_rank'), 'targets': r.get('targets'), 'carries': r.get('carries'),
            'pass_attempts': r.get('pass_attempts'),
            'sim_mean': round(statistics.fmean(w), 3) if w else None,
            'sim_sd': round(statistics.pstdev(w), 3) if w else None,
            'sim_p90': round(sorted(w)[int(0.9 * len(w))], 2) if w else None}
    new, old = fc_rows(fc_new), fc_rows(fc_old)
    old_by = {(norm(r['Player']), r['Team']): r for r in old}
    rows, unmatched = [], []
    for r in new:
        k = (norm(r['Player']), r['Team'])
        o = ours.get(k)
        fp = f(r['FC Proj'])
        prev = old_by.get(k)
        rec = {'fc_name': r['Player'], 'team': r['Team'], 'pos': r['Pos'], 'salary': f(r['Salary']),
               'fc_inj': r['Inj'] or None, 'fc_depth': r['pDepth'] or None, 'fc_proj': fp,
               'fc_floor': f(r['Floor']), 'fc_ceiling': f(r['Ceiling']), 'fc_stdv': f(r['STDV']),
               'fc_my_proj_differs': (r['My Proj'] != r['FC Proj']),
               'fc_proj_previous_export': f(prev['FC Proj']) if prev else None}
        if o is None:
            unmatched.append(rec)
            continue
        rec.update({f'our_{a}': b for a, b in o.items() if a not in ('team',)})
        ref = o['sim_mean'] if o['sim_mean'] is not None else o['dk_points']
        rec['gap_fc_minus_ours'] = round(fp - ref, 2) if fp is not None and ref is not None else None
        rows.append(rec)
    fc_keys = {(norm(r['Player']), r['Team']) for r in new}
    ours_not_in_fc = sorted((v['name'], v['team'], v['sim_mean']) for k, v in ours.items()
                            if k not in fc_keys and (v['sim_mean'] or 0) >= 3)
    gaps = [r for r in rows if r['gap_fc_minus_ours'] is not None]
    by_pos = {}
    for pos in ('QB', 'RB', 'WR', 'TE'):
        g = [r['gap_fc_minus_ours'] for r in gaps if r['pos'] == pos and (r['fc_proj'] or 0) >= 3]
        if g:
            by_pos[pos] = {'n': len(g), 'mean_gap': round(statistics.fmean(g), 2),
                           'mean_abs_gap': round(statistics.fmean(abs(x) for x in g), 2)}
    changed = [r for r in rows if r['fc_proj_previous_export'] is not None
               and abs(r['fc_proj'] - r['fc_proj_previous_export']) >= 1.0]
    res = {'ROLE': 'EXTERNAL_COMPARISON_ONLY: FC is never a model input; no value here enters a forecast',
           'files': {p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
                     for p in (fc_new, fc_old)},
           'build': str(build), 'build_as_of': st.get('as_of'),
           'n_fc_rows': len(new), 'n_matched': len(rows), 'fc_unmatched': unmatched,
           'ours_projected_ge3_not_in_fc': ours_not_in_fc,
           'fc_teams': sorted({r['Team'] for r in new}),
           'gap_by_position_fc_ge3': by_pos,
           'fc_changed_since_previous_export_ge1pt': sorted(
               ({'name': r['fc_name'], 'team': r['team'], 'before': r['fc_proj_previous_export'],
                 'after': r['fc_proj']} for r in changed), key=lambda x: -abs(x['after'] - x['before'])),
           'largest_gaps': sorted(gaps, key=lambda r: -abs(r['gap_fc_minus_ours']))[:60],
           'rows': rows}
    pathlib.Path(out).write_text(json.dumps(res, indent=1, default=str) + '\n')
    print(f"{len(new)} FC rows, {len(rows)} matched, {len(unmatched)} unmatched; {len(changed)} FC changes >=1pt; "
          f"by position {by_pos}")


if __name__ == '__main__':
    main(*sys.argv[1:5])
