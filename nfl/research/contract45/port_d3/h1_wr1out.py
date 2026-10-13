"""H1 / H2 of PREREG_WR1_OUT_AND_RB2_TAILS.md (@d8a7d5eb). Point in time: shares are season-to-date through the previous
week. Clustered (team-season) bootstrap. Run from the repository (or an overlay) root."""
import csv, glob, gzip, io, json, hashlib, collections, random, sys
import numpy as np
PG = 'nfl/warehouse/PLAYER_GAME.json'
pg = json.load(open(PG))['rows']
sha = {PG: hashlib.sha256(open(PG, 'rb').read()).hexdigest()}
# position: from the injury/roster files is incomplete; use PLAYER_GAME behaviour + injury position when present
out_status, posmap = set(), {}
for f in sorted(glob.glob('nfl/vintage/hist_injuries_202[1-5].*.csv.gz')):
    sha[f] = hashlib.sha256(open(f, 'rb').read()).hexdigest()
    for x in csv.DictReader(io.TextIOWrapper(gzip.open(f), encoding='utf-8')):
        if x['game_type'] != 'REG':
            continue
        posmap[x['gsis_id']] = x['position']
        if x['report_status'] == 'Out':
            out_status.add((int(x['season']), int(x['week']), x['team'], x['gsis_id']))
for f in sorted(glob.glob('nfl/vintage/weekly_rosters*.csv.gz'))[:0]:
    pass
# team-game tables
games = collections.defaultdict(lambda: collections.defaultdict(dict))   # (season, club) -> week -> player -> row
for r in pg.values():
    try:
        wk = int(r['week'])
    except (TypeError, ValueError):
        continue
    games[(int(r['season']), r['club'])][wk][r['player_id']] = r
def group(pid, rows_hist):
    p = posmap.get(pid)
    if p in ('WR', 'TE', 'RB', 'QB'):
        return p
    if p == 'FB':
        return 'RB'
    tot = sum(x['carries'] for x in rows_hist), sum(x['targets'] for x in rows_hist)
    return 'RB' if tot[0] > tot[1] else 'WR'
cases = []
for (season, club), weeks in games.items():
    wks = sorted(weeks)
    for i, wk in enumerate(wks):
        prior = [w for w in wks if w < wk]
        if len(prior) < 3:
            continue
        tgt = collections.Counter(); car = collections.Counter(); hist = collections.defaultdict(list)
        team_t = team_c = 0
        for w in prior:
            for pid, x in weeks[w].items():
                tgt[pid] += x['targets']; car[pid] += x['carries']; hist[pid].append(x)
                team_t += x['targets']; team_c += x['carries']
        if team_t == 0:
            continue
        leader, lt = tgt.most_common(1)[0]
        if group(leader, hist[leader]) != 'WR' or lt / team_t < 0.20 or len(hist[leader]) < 3:
            continue
        if (season, wk, club, leader) not in out_status or leader in weeks[wk]:
            continue
        ls = lt / team_t
        now = weeks[wk]
        T = sum(x['targets'] for x in now.values())
        C = sum(x['carries'] for x in now.values())
        if T == 0:
            continue
        pred = collections.Counter(); act = collections.Counter(); pred_c = collections.Counter(); act_c = collections.Counter()
        for pid in set(tgt) | set(now):
            if pid == leader:
                continue
            g = group(pid, hist.get(pid) or ([now[pid]] if pid in now else []))
            pred[g] += (tgt[pid] / team_t) / (1 - ls)
            act[g] += (now[pid]['targets'] / T) if pid in now else 0.0
            if team_c:
                pred_c[g] += car[pid] / team_c
                act_c[g] += (now[pid]['carries'] / C) if (pid in now and C) else 0.0
        base_pass = np.mean([sum(x['targets'] for x in weeks[w].values()) for w in prior])
        base_rush = np.mean([sum(x['carries'] for x in weeks[w].values()) for w in prior])
        cases.append({'season': season, 'club': club, 'week': wk, 'leader': leader, 'leader_share': round(ls, 3),
                      'tgt_bias': {g: act[g] - pred[g] for g in ('WR', 'TE', 'RB')},
                      'targets_vs_base': T - base_pass, 'carries_vs_base': C - base_rush})
def boot(vals, clusters, n=2000, seed=7):
    by = collections.defaultdict(list)
    for v, c in zip(vals, clusters):
        by[c].append(v)
    keys = list(by); rng = random.Random(seed); m = []
    for _ in range(n):
        s = [v for k in (rng.choice(keys) for _ in keys) for v in by[k]]
        m.append(np.mean(s))
    return [round(float(np.mean(vals)), 4), round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4)]
cl = [f"{c['season']}_{c['club']}" for c in cases]
res = {'prereg': 'PREREG_WR1_OUT_AND_RB2_TAILS.md @d8a7d5eb', 'inputs_sha256': {k: v[:16] for k, v in sha.items()},
       'n_cases': len(cases), 'n_team_seasons': len(set(cl)),
       'H1_target_share_bias_actual_minus_proportional_[mean,lo,hi]': {g: boot([c['tgt_bias'][g] for c in cases], cl) for g in ('WR', 'TE', 'RB')},
       'H1_team_targets_vs_baseline': boot([c['targets_vs_base'] for c in cases], cl),
       'H1_team_carries_vs_baseline': boot([c['carries_vs_base'] for c in cases], cl)}
# H2: RB2 tails
rb2 = {'RB1_active': [], 'RB1_active_RB3_out': []}
rb2_ratio = {'RB1_active': [], 'RB1_active_RB3_out': []}
for (season, club), weeks in games.items():
    wks = sorted(weeks)
    for wk in wks:
        prior = [w for w in wks if w < wk]
        if len(prior) < 3:
            continue
        car = collections.Counter(); dk = collections.defaultdict(list); hist = collections.defaultdict(list)
        for w in prior:
            for pid, x in weeks[w].items():
                car[pid] += x['carries']; dk[pid].append(x['dk_points_current_rules']); hist[pid].append(x)
        rbs = [p for p, _ in car.most_common() if group(p, hist[p]) == 'RB'][:3]
        if len(rbs) < 2 or rbs[0] not in weeks[wk]:
            continue
        r2 = rbs[1]
        if (season, wk, club, r2) in out_status:
            continue
        pts = weeks[wk][r2]['dk_points_current_rules'] if r2 in weeks[wk] else 0.0
        m2 = np.mean(dk[r2]) if dk[r2] else 0.0
        keyset = ['RB1_active'] + (['RB1_active_RB3_out'] if len(rbs) > 2 and (season, wk, club, rbs[2]) in out_status else [])
        for k in keyset:
            rb2[k].append(pts); rb2_ratio[k].append(pts >= 3 * m2 if m2 > 0 else False)
res['H2_RB2_dk_points'] = {k: {'n': len(v), 'p50': round(float(np.percentile(v, 50)), 2), 'p90': round(float(np.percentile(v, 90)), 2),
                               'p95': round(float(np.percentile(v, 95)), 2), 'p99': round(float(np.percentile(v, 99)), 2),
                               'share_ge_3x_own_mean': round(float(np.mean(rb2_ratio[k])), 4)} for k, v in rb2.items() if v}
json.dump({'summary': res, 'cases': cases}, open('/tmp/claude-0/mnf_post/h1_result.json', 'w'), indent=1, default=float)
print(json.dumps(res, indent=1, default=float))
