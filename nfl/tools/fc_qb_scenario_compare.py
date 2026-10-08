#!/usr/bin/env python3.12
"""QB-scenario sensitivity board: how our engine and Fantasy Cruncher each respond to a starting-QB change. Read-only.

    python3.12 nfl/tools/fc_qb_scenario_compare.py --ours-a SCEN_DIR_A --ours-b SCEN_DIR_B \
        [--fc-a FC_CSV_A] --fc-b FC_CSV_B --label-a MAYFIELD --label-b DANIELS --qb-club TB --out-prefix PATH

Owner directive 2026-10-08. FC is EXTERNAL INTELLIGENCE: it is never read by a projection, a simulation or the
optimizer, and nothing here writes into a scenario directory. The board is a DEPENDENCY-SENSITIVITY diagnostic: a
player whose FC projection moves with the QB while ours does not is a question about our model, not proof that FC is
right.

  ours     each scenario's projection rows (deterministic; no random path) and the portfolio's FLEX and CPT exposures.
  FC       each FC export's FLEX and CPT rows (fantasy points, floor, ceiling, STDV; FC exports carry no stat lines).
  versions every FC file is checked against its content hash and its slate PROVENANCE.jsonl record. Two FC versions
           are compared only after CONTROLS: capture times, the player set, salaries, injury flags and depth labels of
           everyone except the two QBs, and FC's Vegas team totals. Any other change found makes the FC deltas an
           OBSERVED_VERSION_DIFFERENCE (confounded), never an identified QB effect. Even with clean controls FC's own
           model may have been updated between exports, so the strongest label is QB_SWAP_ONLY_IDENTIFIED_INPUT_CHANGE.
  depend   for every player, which edge of nfl/research/intel/DEPENDENCY_GRAPH_SHOWDOWN_v0.json would carry a QB effect
           in our engine, and that edge's status (IMPLEMENTED_AND_CONSUMED / MISSING / ...).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
MATERIAL = 1.0          # DK FLEX points: |FC delta - our delta| at or above this is triaged
GRAPH = _REPO / 'nfl/research/intel/DEPENDENCY_GRAPH_SHOWDOWN_v0.json'


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_fc(path):
    p = pathlib.Path(path).resolve()
    rows = list(csv.reader(p.open(newline='', encoding='utf-8-sig')))
    hi = next(i for i, r in enumerate(rows) if r and r[0] == 'Player')
    h = rows[hi]
    flex, cpt = {}, {}
    for r in rows[hi + 1:]:
        if len(r) < len(h) or not r[0]:
            continue
        d = dict(zip(h, r))
        k = (d['Player'].strip(), d['Team'].strip())
        rec = {'pos': d['Pos'], 'depth': d.get('pDepth') or None, 'inj': d.get('Inj') or None,
               'salary': _num(d['Salary']), 'proj': _num(d['FC Proj']), 'floor': _num(d['Floor']),
               'ceiling': _num(d['Ceiling']), 'stdv': _num(d['STDV']), 'vegas': _num(d['VegasPts'])}
        (cpt if d['Pos'] == 'CPTN' else flex)[k] = rec
    sha = _sha(p)
    m = re.search(r'\.([0-9a-f]{16})\.csv$', p.name)
    prov = None
    pj = p.parent / 'PROVENANCE.jsonl'
    if pj.is_file():
        for line in pj.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('file') == p.name:
                prov = r
    side = p.with_name(p.name + '.PROVENANCE.json')
    if prov is None and side.is_file():
        prov = json.loads(side.read_text())
    ver = {'file': str(p.relative_to(_REPO)) if p.resolve().is_relative_to(_REPO) else str(p), 'sha256': sha,
           'name_hash_matches_content': (m.group(1) == sha[:16]) if m else None,
           'provenance': prov, 'received_at': (prov or {}).get('received_at_utc') or (prov or {}).get('built_at'),
           'n_flex': len(flex), 'n_cpt': len(cpt)}
    return flex, cpt, ver


def load_ours(sd):
    sd = pathlib.Path(sd).resolve()
    pj = json.loads(next(sd.glob('*_PROJ.json')).read_text())
    rows = pj.get('rows') or pj
    out = {}
    for r in (rows.values() if isinstance(rows, dict) else rows):
        if isinstance(r, dict) and r.get('name') and r.get('team'):
            rec = {k: r.get(k) for k in (
                'position', 'availability', 'dk_points', 'dk_points_if_plays', 'pass_attempts', 'pass_yards',
                'carries', 'rush_yards', 'targets', 'receptions', 'rec_yards', 'role_band', 'is_predicted_starter')}
            td = r.get('td') or {}
            for f in ('pass_td', 'rush_td', 'rec_td'):
                rec[f] = td.get(f) if isinstance(td, dict) else None
            out[(r['name'], r['team'])] = rec
    flex, cpt = {}, {}
    for f, dst, col in (('EXPOSURES', flex, 'player'), ('CPT_EXPOSURES', cpt, 'captain')):
        p = next(sd.glob(f'*_{f}.csv'), None)
        if p is None:
            continue
        for r in csv.DictReader(p.open()):
            k = (r[col], r['team'])
            dst[k] = dst.get(k, 0) + int(r['n'])
    up = next(sd.glob('*_DK_UPLOAD.csv'), None)
    n = sum(1 for _ in up.open()) - 1 if up else None
    st = json.loads(next(sd.glob('*_STATE.json')).read_text())
    return out, flex, cpt, n, {'scenario_dir': str(sd.relative_to(_REPO)), 'state_sha256': _sha(next(sd.glob('*_STATE.json'))),
                               'proj_sha256': _sha(next(sd.glob('*_PROJ.json'))), 'upload_sha256': _sha(up) if up else None,
                               'scenario_identity': st.get('scenario_identity')}


def dependency(key, row, qb_club, opp):
    """Which edge of our graph would carry a QB effect to this player, and its status."""
    g = {e['id']: e for e in json.loads(GRAPH.read_text())['edges']} if GRAPH.is_file() else {}
    st = lambda i: f"{i} {g.get(i, {}).get('status', 'UNKNOWN')}"  # noqa: E731
    pos, club = (row or {}).get('position'), key[1]
    if club == qb_club:
        if pos == 'QB':
            return [st('ID3'), st('QB6')]
        if pos in ('WR', 'TE'):
            return [st('QB1'), st('QB3'), st('QB4'), st('AC1')]
        if pos == 'RB':
            return [st('QB1'), st('QB3'), st('QB4')]
        if pos == 'K':
            return [st('QB2')]
        if pos == 'DST':
            return [st('QB2'), 'opponent offence vs this defence: not a QB edge']
    if club == opp:
        if pos == 'DST':
            return [st('QB5'), st('AC3'), st('QB2') + ' (points allowed)']
        return [st('EN3') + ' (no opponent-QB effect on this club by design)']
    return ['unmatched club']


def pct(a, b):
    return round(100.0 * (b - a) / a, 1) if a not in (None, 0) and b is not None else None


def delta(a, b):
    ok = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b))
    return round(b - a, 3) if ok else None


def controls(fa, fb, va, vb, qb_names):
    out, conf = {}, []
    ka, kb = set(fa), set(fb)
    out['players_only_in_a'] = sorted(f'{n}|{t}' for n, t in ka - kb)
    out['players_only_in_b'] = sorted(f'{n}|{t}' for n, t in kb - ka)
    if out['players_only_in_a'] or out['players_only_in_b']:
        conf.append('PLAYER_SET_CHANGED')
    ch = {f: [] for f in ('salary', 'inj', 'depth')}
    for k in ka & kb:
        if k[0] in qb_names:
            continue
        for f in ch:
            if fa[k][f] != fb[k][f]:
                ch[f].append(f'{k[0]}|{k[1]}: {fa[k][f]} -> {fb[k][f]}')
    for f, v in ch.items():
        out[f'non_qb_{f}_changes'] = sorted(v)
        if v:
            conf.append(f'NON_QB_{f.upper()}_CHANGED')
    veg = {}
    for k in ka & kb:
        veg.setdefault(k[1], set()).add((fa[k]['vegas'], fb[k]['vegas']))
    out['vegas_team_totals'] = {t: sorted(v) for t, v in veg.items()}
    if any(a != b for v in veg.values() for a, b in v):
        conf.append('FC_VEGAS_TEAM_TOTAL_CHANGED (FC is market-informed; a moved total is not a QB-only input change)')
    out['captured'] = [va.get('received_at'), vb.get('received_at')]
    if None in out['captured']:
        conf.append('CAPTURE_TIME_UNRECORDED')
    label = ('OBSERVED_VERSION_DIFFERENCE (confounded: ' + '; '.join(conf) + ')') if conf else \
        'QB_SWAP_ONLY_IDENTIFIED_INPUT_CHANGE (FC model updates between exports remain unobservable; not causal)'
    return label, out


def triage(o_d, fc_d, ra, rb, pos):
    if fc_d is None or o_d is None or abs(fc_d - o_d) < MATERIAL:
        return None
    if pos == 'K':
        return 'SCORING_CENTRE (QB2 MISSING: club points do not depend on the QB)'
    if pos == 'DST':
        return 'OPPOSING-QB EVENTS (QB5 MISSING) and points allowed (QB2 MISSING)'
    if pos == 'QB':
        return 'QB OWN PROJECTION (efficiency prior / attempts); dependency exists, magnitude differs'
    t = delta((ra or {}).get('targets'), (rb or {}).get('targets'))
    if t is not None and abs(t) < 0.1:
        return ('TEAM VOLUME / TARGET SHARE (QB1, QB4 MISSING: our targets moved %+.2f) and CATCHABILITY (QB3 '
                'IMPLEMENTED_NOT_CONSUMED)' % t)
    return 'EFFICIENCY / TD (QB3 IMPLEMENTED_NOT_CONSUMED); our opportunity did move'


def build(a):
    oa, xa, ca, na, ida = load_ours(a.ours_a)
    ob, xb, cb, nb, idb = load_ours(a.ours_b)
    fb_flex, fb_cpt, vb = load_fc(a.fc_b)
    fa_flex = fa_cpt = va = None
    if a.fc_a:
        fa_flex, fa_cpt, va = load_fc(a.fc_a)
        if va['sha256'] == vb['sha256']:
            raise SystemExit('FC_VERSIONS_IDENTICAL: the two FC files are the same bytes; there is no before/after')
    qbs = {k[0] for k, r in {**oa, **ob}.items() if r.get('position') == 'QB' and k[1] == a.qb_club}
    opp = next(k[1] for k in {**oa, **ob} if k[1] != a.qb_club)
    label, ctl = (controls(fa_flex, fb_flex, va, vb, qbs) if fa_flex is not None else
                  ('FC_BEFORE_VERSION_NOT_AVAILABLE (only the after-scenario FC export exists)', {}))
    rows = []
    for k in sorted(set(oa) | set(ob) | set(fb_flex) | set(fa_flex or {})):
        ra, rb = oa.get(k), ob.get(k)
        pos = (rb or ra or {}).get('position') or (fb_flex.get(k) or {}).get('pos')
        # UNCONDITIONAL expected DK points (P(plays) x if-plays): the like-for-like object for FC's projection, which
        # is an expectation and zeroes backups. The conditional value a lineup consumes is reported beside it.
        o_a = ((ra or {}).get('dk_points') or 0.0) if ra else None
        o_b = ((rb or {}).get('dk_points') or 0.0) if rb else None
        f_b = (fb_flex.get(k) or {}).get('proj')
        f_a = (fa_flex.get(k) or {}).get('proj') if fa_flex is not None else None
        od, fd = delta(o_a, o_b), delta(f_a, f_b)
        row = {'player': k[0], 'team': k[1], 'pos': pos,
               'ours': {'a': o_a, 'b': o_b, 'delta': od, 'pct': pct(o_a, o_b),
                        'if_plays': [(ra or {}).get('dk_points_if_plays'), (rb or {}).get('dk_points_if_plays')],
                        'stats_delta': {f: delta((ra or {}).get(f), (rb or {}).get(f)) for f in
                                        ('pass_attempts', 'pass_yards', 'carries', 'rush_yards', 'targets',
                                         'receptions', 'rec_yards', 'pass_td', 'rush_td', 'rec_td')},
                        'flex_lineups': [xa.get(k, 0), xb.get(k, 0)], 'cpt_lineups': [ca.get(k, 0), cb.get(k, 0)]},
               'fc': {'a': f_a, 'b': f_b, 'delta': fd, 'pct': pct(f_a, f_b),
                      'cpt_b': (fb_cpt.get(k) or {}).get('proj'),
                      'cpt_delta': delta((fa_cpt or {}).get(k, {}).get('proj') if fa_cpt else None,
                                         (fb_cpt.get(k) or {}).get('proj')),
                      'floor_ceiling_b': [(fb_flex.get(k) or {}).get('floor'), (fb_flex.get(k) or {}).get('ceiling')],
                      'inj_b': (fb_flex.get(k) or {}).get('inj')},
               'level_gap_b_ours_minus_fc': delta(f_b, o_b),
               'delta_gap_fc_minus_ours': delta(od, fd),
               'our_dependency_path': dependency(k, rb or ra, a.qb_club, opp),
               'triage': triage(od, fd, ra, rb, pos)}
        if any(v not in (None, 0, 0.0) for v in (o_a, o_b, f_a, f_b)):
            rows.append(row)
    key = lambda r, s: (r[s]['delta'] if r[s]['delta'] is not None else 0.0)  # noqa: E731
    out = {'ARTIFACT': 'QB_SCENARIO_SENSITIVITY_BOARD', 'scenarios': [a.label_a, a.label_b], 'qb_club': a.qb_club,
           'ROLE': 'DIAGNOSTIC ONLY. FC is never a model input; nothing here changes a projection, a world or a lineup.',
           'ours': {a.label_a: {**ida, 'lineups': na}, a.label_b: {**idb, 'lineups': nb}},
           'fc_versions': {a.label_a: va, a.label_b: vb}, 'fc_version_comparison': label, 'controls': ctl,
           'material_threshold_dk': MATERIAL,
           'ours_largest_gainers': [(r['player'], r['ours']['delta']) for r in sorted(rows, key=lambda r: -key(r, 'ours'))[:6]],
           'ours_largest_losers': [(r['player'], r['ours']['delta']) for r in sorted(rows, key=lambda r: key(r, 'ours'))[:6]],
           'fc_largest_gainers': ([(r['player'], r['fc']['delta']) for r in sorted(rows, key=lambda r: -key(r, 'fc'))[:6]]
                                  if fa_flex is not None else 'PENDING_FC_BEFORE_VERSION'),
           'fc_largest_losers': ([(r['player'], r['fc']['delta']) for r in sorted(rows, key=lambda r: key(r, 'fc'))[:6]]
                                 if fa_flex is not None else 'PENDING_FC_BEFORE_VERSION'),
           'triaged': [r for r in rows if r['triage']], 'rows': rows}
    # LEVEL GAPS BY CLUB AND GROUP (scenario B). Our-minus-FC gaps exist on both clubs for reasons unrelated to the QB
    # (different models). Only a QB-club gap well beyond the other club's, in the groups a QB would move, is a signal.
    grp = {}
    for r in rows:
        g = 'PASS_CATCHERS' if r['pos'] in ('WR', 'TE') else r['pos']
        if r['level_gap_b_ours_minus_fc'] is None or not r['fc']['b']:
            continue
        x = grp.setdefault(f"{r['team']}:{g}", {'n': 0, 'ours_b': 0.0, 'fc_b': 0.0})
        x['n'] += 1
        x['ours_b'] += r['ours']['b'] or 0.0
        x['fc_b'] += r['fc']['b']
    for x in grp.values():
        x['ours_minus_fc'] = round(x['ours_b'] - x['fc_b'], 2)
        x['ratio_ours_over_fc'] = round(x['ours_b'] / x['fc_b'], 3) if x['fc_b'] else None
        x['ours_b'], x['fc_b'] = round(x['ours_b'], 2), round(x['fc_b'], 2)
    out['level_gap_by_club_group_' + a.label_b] = dict(sorted(grp.items()))
    out['READING'] = ('Without an FC export under the other QB, FC deltas cannot be measured: the level gaps above compare '
                      'two different models under one scenario and are a weak signal only. A Mayfield-scenario FC export '
                      'is needed for an FC-vs-FC delta.') if fa_flex is None else out.get('READING')
    return out


def markdown(b):
    la, lb = b['scenarios']
    L = [f"# QB scenario sensitivity board: {la} -> {lb} ({b['qb_club']})", '', b['ROLE'], '',
         f"- **FC version comparison:** {b['fc_version_comparison']}",
         f"- **Our scenarios:** {la} `{b['ours'][la]['scenario_dir']}`; {lb} `{b['ours'][lb]['scenario_dir']}`",
         f"- **FC after ({lb}):** `{b['fc_versions'][lb]['file']}`, received {b['fc_versions'][lb]['received_at']}",
         '', '| Player | Team | Pos | Ours ' + la + ' | Ours ' + lb + ' | Ours delta | FC ' + la + ' | FC ' + lb +
         ' | FC delta | Ours minus FC (' + lb + ') | Our dependency path | Triage |',
         '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|']
    def v(x):
        return '' if x is None else f'{x:.2f}'

    def d(x):
        return '' if x is None else f'{x:+.2f}'
    for r in sorted(b['rows'], key=lambda r: (r['team'] != b['qb_club'], -(r['ours']['b'] or 0))):
        L.append(f"| {r['player']} | {r['team']} | {r['pos']} | {v(r['ours']['a'])} | {v(r['ours']['b'])} | "
                 f"{d(r['ours']['delta'])} | {v(r['fc']['a'])} | {v(r['fc']['b'])} | {d(r['fc']['delta'])} | "
                 f"{d(r['level_gap_b_ours_minus_fc'])} | {'; '.join(r['our_dependency_path'])} | {r['triage'] or ''} |")
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ours-a', required=True)
    ap.add_argument('--ours-b', required=True)
    ap.add_argument('--fc-a')
    ap.add_argument('--fc-b', required=True)
    ap.add_argument('--label-a', default='A')
    ap.add_argument('--label-b', default='B')
    ap.add_argument('--qb-club', required=True)
    ap.add_argument('--out-prefix', required=True)
    a = ap.parse_args(argv)
    b = build(a)
    pathlib.Path(a.out_prefix + '.json').write_text(json.dumps(b, indent=1, default=str) + '\n')
    pathlib.Path(a.out_prefix + '.md').write_text(markdown(b))
    print(json.dumps({k: b[k] for k in ('fc_version_comparison', 'ours_largest_gainers', 'ours_largest_losers',
                                        'fc_largest_gainers', 'fc_largest_losers')}, indent=1, default=str))
    print('triaged:', len(b['triaged']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
