"""Scenario vs base, per club, from the projections and the simulated worlds. Read-only.

    python3.12 analyse_scenarios.py SCENARIOS_DIR WORLDS_DIR OUT.json

For each scenario: the absent player's active projection (the base) and his inactive value (zero), every teammate who
moves by >= 0.25 DK points with his target and carry change, the club's volume totals, the club's and the opponent's
simulated points, the opponent DST, and 10th/50th/90th percentiles from the worlds. Quantities the worlds do not carry
(sacks, completions for passers, kicker events, snaps, routes) are listed as NOT_MODELLED, never estimated.
"""
import gzip
import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
from nfl.tools.sim_query import dk_from_stats_vec  # noqa: E402

NOT_MODELLED = {'sacks': 'not in the player stat lines', 'completions': 'not stored for passers',
                'kicker': 'DK Classic rosters no kicker; no kicker rows in this run',
                'snaps_routes': 'not in the worlds', 'fumbles': 'not drawn per player'}


def load(sd, wd):
    pj = json.load(gzip.open(sd / 'PROJ.json.gz'))['rows']
    st = json.loads((sd / 'STATE.json').read_text())
    z = np.load(wd / 'WORLDS.npz', allow_pickle=False)
    meta = json.loads(z['meta'].tobytes())
    S = z['stats'].astype('float64')
    for f in meta['yard_fields']:
        S[:, :, meta['fields'].index(f)] /= meta['yard_scale']
    F = {f: i for i, f in enumerate(meta['fields'])}
    keys = meta['keys']
    dk = dk_from_stats_vec(S, F)
    dr = json.loads((wd / 'DRAWS.json').read_text())
    return pj, st, S, F, keys, dk, meta, z['points'], dr


def pct(a):
    return [round(float(x), 2) for x in np.percentile(a, [10, 50, 90])]


def wkey(r):
    """The worlds are keyed 'name|club', not by projection id."""
    return f"{r['name']}|{r['team']}"


def club_summary(pj, S, F, keys, dk, meta, pts, club):
    idx = {k: i for i, k in enumerate(keys)}
    ks = [wkey(r) for r in pj.values() if r['team'] == club and wkey(r) in idx and r['position'] != 'DST']
    if not ks:
        raise SystemExit(f'NO_WORLD_ROWS_FOR_CLUB {club}: a club with no matched rows would sum to zero, not measure it')
    tot = {f: round(float(sum(S[idx[k], :, F[f]].mean() for k in ks)), 2) for f in
           ('pass_att', 'pass_yards', 'pass_td', 'interceptions', 'carries', 'rush_yards', 'rush_td', 'targets',
            'receptions', 'rec_yards', 'rec_td')}
    tot['n_player_rows'] = len(ks)
    tot['plays_ex_sacks'] = round(tot['pass_att'] + tot['carries'], 2)
    tot['completions_proxy_receptions'] = tot['receptions']
    g = next(i for i, gg in enumerate(meta['games']) if club in (gg['home'], gg['away']))
    gg = meta['games'][g]
    side = 0 if gg['home'] == club else 1
    tot['club_points'] = round(float(pts[g, :, side].mean()), 2)
    tot['opp_points'] = round(float(pts[g, :, 1 - side].mean()), 2)
    tot['opponent'] = gg['away'] if side == 0 else gg['home']
    return tot


def compare(base, scen, club, subj_names):
    pjb, stb, Sb, Fb, kb, dkb, mb, pb, drb = base
    pjs, sts, Ss, Fs, ks, dks, ms, ps, drs = scen
    ib, is_ = {k: i for i, k in enumerate(kb)}, {k: i for i, k in enumerate(ks)}
    tb, ts = club_summary(pjb, Sb, Fb, kb, dkb, mb, pb, club), club_summary(pjs, Ss, Fs, ks, dks, ms, ps, club)
    movers = []
    for k, r in pjb.items():
        if r['team'] not in (club, tb['opponent']):
            continue
        a, b = r['dk_points'] or 0.0, (pjs[k]['dk_points'] or 0.0)
        if abs(b - a) < 0.25 and r['name'] not in subj_names:
            continue
        row = {'name': r['name'], 'team': r['team'], 'pos': r['position'], 'dk_active_case': round(a, 2),
               'dk_scenario': round(b, 2), 'delta': round(b - a, 2),
               'band': (r.get('role_band'), pjs[k].get('role_band')),
               'd_targets': round(float((pjs[k].get('targets') or 0) - (r.get('targets') or 0)), 2),
               'd_carries': round(float((pjs[k].get('carries') or 0) - (r.get('carries') or 0)), 2),
               'd_pass_attempts': round(float((pjs[k].get('pass_attempts') or 0) - (r.get('pass_attempts') or 0)), 2)}
        w = wkey(r)
        if w in ib:
            row['p10_50_90_active_case'] = pct(dkb[ib[w]])
        if w in is_:
            row['p10_50_90_scenario'] = pct(dks[is_[w]])
        movers.append(row)
    return {'club': club, 'team_active_case': tb, 'team_scenario': ts,
            'team_delta': {f: round(ts[f] - tb[f], 2) for f in tb if isinstance(tb[f], float)},
            'movers': sorted(movers, key=lambda m: -abs(m['delta']))}


ABSENT = ('REPORTED_OUT_UNVERIFIED', 'REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED', 'REPORTED_INACTIVE_HIGH_CONFIDENCE',
          'CONFIRMED_INACTIVE')


def propagation(sd, scen, names, club, base_team, qb_starts=None):
    """Each absent player through state -> role -> projection -> worlds, plus team and starter checks."""
    pj, st, S, F, keys, dk, meta, pts, dr = scen
    roles = json.loads((sd / 'ROLE_STATE.json').read_text())['states']
    rows, ok = [], True
    for nm in names:
        k = next(k for k, p in st['players'].items() if p['name'] == nm)
        p, r, q = st['players'][k], roles.get(k, {}), pj.get(k, {})
        rec = {'name': nm, 'state_status': p['current_availability']['status'],
               'role_state': r.get('state'), 'role_band': r.get('role_band'),
               'projection_state': q.get('projection_state'), 'dk_points': q.get('dk_points'),
               'in_worlds': wkey(p) in keys}
        rec['pass'] = (rec['state_status'] in ABSENT and rec['role_state'] == 'NOT_PLAYING'
                       and str(rec['projection_state']).startswith('NOT_PLAYING') and not rec['dk_points']
                       and not rec['in_worlds'])
        ok &= rec['pass']
        rows.append(rec)
    team = club_summary(pj, S, F, keys, dk, meta, pts, club)
    tol = {'pass_att': 1.5, 'carries': 1.5, 'targets': 1.5}
    recon = {f: {'base': base_team[f], 'scenario': team[f], 'pass': abs(team[f] - base_team[f]) <= t}
             for f, t in tol.items()}
    idx = {kk: i for i, kk in enumerate(keys)}
    qbs = sorted(((r['name'], round(float(S[idx[wkey(r)], :, F['pass_att']].mean()), 2)) for r in pj.values()
                  if r['team'] == club and r['position'] == 'QB' and wkey(r) in idx), key=lambda x: -x[1])
    starters = [q for q in qbs if q[1] >= 15]
    single = len(starters) == 1 and (qb_starts is None or starters[0][0] == qb_starts)
    arm = dr.get('market_arm')
    out = {'absent_players': rows, 'team_reconciliation_vs_base': recon,
           'qb_pass_attempts': qbs, 'single_starter_workload': single,
           'market_arm': arm, 'forbidden_source_check': 'PASS' if arm == 'FOOTBALL_ONLY' else f'CHECK: {arm}',
           'optimizer_stage': 'BLOCKED_NO_DK_POOL (research-universe ids are never uploadable; no portfolio stage reads them)'}
    out['pass'] = ok and all(v['pass'] for v in recon.values()) and single and arm == 'FOOTBALL_ONLY'
    return out


def main():
    sd, wd, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    spec = json.loads((sd / 'SPEC.json').read_text())
    base = load(sd / 'BASE', wd / 'BASE')
    res = {'NOT_MODELLED': NOT_MODELLED, 'base': str(sd / 'BASE'), 'scenarios': {}}
    for s in spec['scenarios']:
        d = sd / s['label']
        if not (d / 'PROJ.json.gz').exists() or not (wd / s['label'] / 'WORLDS.npz').exists():
            res['scenarios'][s['label']] = {'state': 'NOT_RUN'}
            continue
        ro = json.loads((d / 'RUN_OUTCOME.json').read_text())
        sc = load(d, wd / s['label'])
        names = s['out']
        club = next(r['team'] for r in base[0].values() if r['name'] == (names[0] if names else s.get('qb_starts')))
        r = compare(base, sc, club, set(names) | ({s['qb_starts']} if s.get('qb_starts') else set()))
        r.update(run=f"{ro['state']}[{ro['code']}] {ro['detail']}", out=names, qb_starts=s.get('qb_starts'), why=s['why'],
                 receipt=ro.get('receipt'))
        r['propagation'] = propagation(d, sc, names, club, r['team_active_case'], s.get('qb_starts'))
        res['scenarios'][s['label']] = r
    out.write_text(json.dumps(res, indent=1) + '\n')
    for lab, r in res['scenarios'].items():
        if r.get('state') == 'NOT_RUN':
            print(lab, 'NOT_RUN'); continue
        print(f"\n{lab}  ({r['run'][:60]})  team d: {r['team_delta']}")
        for m in r['movers'][:9]:
            print(f"  {m['name']:<22}{m['team']:<4}{m['pos']:<4}{m['dk_active_case']:6.2f} -> {m['dk_scenario']:6.2f} ({m['delta']:+.2f})"
                  f" tgt {m['d_targets']:+.2f} car {m['d_carries']:+.2f} att {m['d_pass_attempts']:+.2f}  {m['band'][0]}->{m['band'][1]}")


if __name__ == '__main__':
    main()
