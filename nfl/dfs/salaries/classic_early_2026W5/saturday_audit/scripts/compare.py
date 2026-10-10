"""Base (frozen Friday board) vs rebuild: per-player DK mean, P(plays), role band, and the availability inputs."""
import gzip, json, pathlib, sys
def load(d, n):
    p = pathlib.Path(d) / n
    return json.load(gzip.open(p)) if p.suffix == '.gz' else json.loads(p.read_text())
A, B, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
pa = load(A, 'PROJ.json.gz')['rows']; pb = load(B, 'PROJ.json.gz' if (pathlib.Path(B) / 'PROJ.json.gz').exists() else 'PROJ.json')['rows']
sa = load(A, 'STATE.json')['players']; sb = load(B, 'STATE.json')['players']
rows = []
for k in sorted(set(pa) | set(pb)):
    a, b = pa.get(k), pb.get(k)
    if not a or not b:
        rows.append({'id': k, 'only_in': 'base' if a else 'rebuild', 'name': (a or b)['name'], 'team': (a or b)['team']})
        continue
    av = (sa.get(k) or {}).get('current_availability') or {}; bv = (sb.get(k) or {}).get('current_availability') or {}
    pp = lambda r: max((r.get('p_plays') or {}).values() or [0])
    rec = {'id': k, 'name': a['name'], 'team': a['team'], 'pos': a['position'],
           'dk_base': a['dk_points'] or 0.0, 'dk_rebuild': b['dk_points'] or 0.0,
           'delta': round((b['dk_points'] or 0.0) - (a['dk_points'] or 0.0), 3),
           'state_base': a.get('projection_state'), 'state_rebuild': b.get('projection_state'),
           'p_base': pp(a), 'p_rebuild': pp(b), 'band_base': a.get('role_band'), 'band_rebuild': b.get('role_band'),
           'practice_base': av.get('practice_status'), 'practice_rebuild': bv.get('practice_status'),
           'status_base': av.get('status'), 'status_rebuild': bv.get('status'),
           'depth_base': (sa.get(k) or {}).get('depth_rank'), 'depth_rebuild': (sb.get(k) or {}).get('depth_rank')}
    rows.append(rec)
both = [r for r in rows if 'delta' in r]
moved = sorted([r for r in both if abs(r['delta']) >= 0.25 or r['band_base'] != r['band_rebuild']
                or r['depth_base'] != r['depth_rebuild'] or r['status_base'] != r['status_rebuild']
                or r['state_base'] != r['state_rebuild']],
               key=lambda r: -abs(r['delta']))
prac = [r for r in both if r['practice_base'] != r['practice_rebuild']]
summ = {'n_players_compared': len(both), 'only_one_side': [r for r in rows if 'only_in' in r],
        'n_moved_025_or_role_or_depth_or_status': len(moved), 'n_practice_status_changed': len(prac),
        'max_abs_delta': max((abs(r['delta']) for r in both), default=None),
        'sum_abs_delta': round(sum(abs(r['delta']) for r in both), 2)}
json.dump({'summary': summ, 'moved': moved, 'practice_changed': prac}, open(OUT, 'w'), indent=1)
print(json.dumps(summ, indent=1))
for r in moved[:30]:
    print(f"{r['name']:<24}{r['team']:<4}{r['pos']:<3} {r['dk_base']:6.2f} -> {r['dk_rebuild']:6.2f} ({r['delta']:+.2f}) "
          f"p {r['p_base']:.3f}->{r['p_rebuild']:.3f} {r['band_base']}->{r['band_rebuild']} depth {r['depth_base']}->{r['depth_rebuild']} "
          f"| {r['practice_base']} -> {r['practice_rebuild']}")
