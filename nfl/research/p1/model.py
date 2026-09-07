"""P1 opportunity baselines, walk-forward. Nothing here reads game t.

TWO CONSTRUCTION DECISIONS THAT CHANGE THE ANSWER

1. DENOMINATORS ARE SUMS OF WHAT WE COUNTED, NOT pbp's pass_attempt.
   Measured on 2024: pass_attempt = 19,125 and includes all 1,314 sacks; 2,112
   pass attempts carry no receiver_player_id. targets/pass_attempt = 0.8896, and
   the shortfall varies by team-game with the sack rate. Using it as a target
   share denominator would inject offensive-line noise into a receiver metric.
   team_targets and team_carries below are sums over the panel, so shares sum to
   exactly 1 by construction.

2. THE PANEL IS EXTENDED WITH ZERO-OPPORTUNITY ROWS.
   The raw panel only holds players who did something, so it silently conditions
   on appearing -- the hardest part of the question the owner actually asked
   ("who will be on the field"). For each team-week the candidate set is every
   player who appeared for that team in any of the previous 4 team-games, which
   is knowable pregame. Candidates who did not appear get a row of zeros. This
   does NOT use weekly_rosters.status, which is quarantined.
"""
import bisect, collections, csv, json, math, os, random, statistics, sys

SP = os.path.dirname(os.path.abspath(__file__))
EVAL_SEASONS = [2022, 2023, 2024, 2025]
LOOKBACK_CANDIDATE = 4


def ordkey(s, w):
    return int(s) * 100 + int(w)


def load():
    rows = []
    for r in csv.DictReader(open(f'{SP}/panel.csv')):
        r['season'] = int(r['season']); r['week'] = int(r['week'])
        for k in ('targets', 'carries', 'rz_targets', 'rz_carries',
                  'gl_carries', 'third_targets', 'pass_snaps', 'team_plays',
                  'team_dropbacks', 'team_pass_att', 'team_rush_att',
                  'team_rz_rush', 'team_gl_rush', 'team_dropbacks_part',
                  'dropbacks_as_passer', 'pass_att_as_passer',
                  'scrambles', 'designed_rushes'):
            r[k] = int(float(r[k] or 0))
        r['offense_pct'] = (float(r['offense_pct']) if r['offense_pct'] else None)
        r['ord'] = ordkey(r['season'], r['week'])
        rows.append(r)
    return rows


def extend_with_zeros(rows):
    """Add zero-opportunity rows for pregame-identifiable candidates."""
    by_team_week = collections.defaultdict(list)
    for r in rows:
        by_team_week[(r['team'], r['ord'])].append(r)
    team_weeks = collections.defaultdict(list)
    for (tm, o) in by_team_week:
        team_weeks[tm].append(o)
    for tm in team_weeks:
        team_weeks[tm].sort()

    added = 0
    out = list(rows)
    for tm, ords in team_weeks.items():
        for idx, o in enumerate(ords):
            present = {r['gsis_id'] for r in by_team_week[(tm, o)]}
            cands = {}
            for prev in ords[max(0, idx - LOOKBACK_CANDIDATE):idx]:
                for r in by_team_week[(tm, prev)]:
                    cands[r['gsis_id']] = r
            tmpl = by_team_week[(tm, o)][0]
            for pid, src in cands.items():
                if pid in present:
                    continue
                z = {k: 0 for k in tmpl if isinstance(tmpl[k], int)}
                z.update({'season': tmpl['season'], 'week': tmpl['week'],
                          'team': tm, 'gsis_id': pid, 'ord': o,
                          'game_id': tmpl['game_id'],
                          'position': src['position'],
                          'player_name': src['player_name'],
                          'team_plays': tmpl['team_plays'],
                          'team_dropbacks': tmpl['team_dropbacks'],
                          'team_pass_att': tmpl['team_pass_att'],
                          'team_rush_att': tmpl['team_rush_att'],
                          'team_rz_rush': tmpl['team_rz_rush'],
                          'team_gl_rush': tmpl['team_gl_rush'],
                          'team_dropbacks_part': tmpl['team_dropbacks_part'],
                          'offense_pct': 0.0, 'did_not_appear': 1})
                out.append(z)
                added += 1
    for r in out:
        r.setdefault('did_not_appear', 0)
    return out, added


def add_shares(rows):
    tt = collections.Counter()
    tc = collections.Counter()
    trz = collections.Counter()
    for r in rows:
        k = (r['team'], r['ord'])
        tt[k] += r['targets']; tc[k] += r['carries']; trz[k] += r['rz_carries']
    for r in rows:
        k = (r['team'], r['ord'])
        r['team_targets'] = tt[k]; r['team_carries'] = tc[k]
        r['team_rz_carries'] = trz[k]
        r['target_share'] = r['targets'] / tt[k] if tt[k] else None
        r['carry_share'] = r['carries'] / tc[k] if tc[k] else None
        r['rz_carry_share'] = (r['rz_carries'] / trz[k]) if trz[k] else None
        r['rpr'] = (r['pass_snaps'] / r['team_dropbacks_part']
                    if r['team_dropbacks_part'] else None)
        # MEASURED, not assumed: snap_counts.offense_pct is already a
        # fraction (2024: min 0.000, max 1.000, mean 0.236, n=26,615). An
        # earlier version divided by 100 as well, which reported snap_share MAE
        # as 0.0015 -- a hundredfold understatement that would have read as the
        # most forecastable target in the study.
        r['snap_share'] = r['offense_pct']
    return rows


TARGETS = {
    'snap_share':    ('WR', 'TE', 'RB'),
    'rpr':           ('WR', 'TE', 'RB'),
    'target_share':  ('WR', 'TE', 'RB'),
    'carry_share':   ('RB',),
    'rz_carry_share': ('RB',),
    'team_dropbacks': ('QB',),
    'pass_att_as_passer': ('QB',),
    'scrambles': ('QB',),
    'designed_rushes': ('QB',),
}


def ewma(vals, half_life=3.0):
    lam = 0.5 ** (1.0 / half_life)
    num = den = 0.0
    for v in reversed(vals):            # most recent first
        num += v; den += 1
        break
    num = den = 0.0
    w = 1.0
    for v in reversed(vals):
        num += w * v; den += w; w *= lam
    return num / den if den else None


def build_predictions(rows, target, positions, prior_by_pos):
    """Every baseline for one target, chronologically."""
    hist = collections.defaultdict(list)      # player -> [(ord, value)]
    out = []
    for r in sorted(rows, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        if r['position'] not in positions:
            continue
        y = r.get(target)
        pid = r['gsis_id']
        past = [v for (_o, v) in hist[pid]]
        prior = prior_by_pos.get((r['position'], target))
        if y is not None and prior is not None:
            n = len(past)
            preds = {
                'prior': prior,
                'std': statistics.mean(past) if past else prior,
                'lag1': past[-1] if past else prior,
                'ma3': statistics.mean(past[-3:]) if past else prior,
                'ma5': statistics.mean(past[-5:]) if past else prior,
                'ewma3': ewma(past) if past else prior,
            }
            for k in (2, 4, 8):
                preds[f'shrink{k}'] = (
                    ((n * statistics.mean(past) + k * prior) / (n + k))
                    if past else prior)
            out.append({'row': r, 'y': y, 'n_prior': n, 'preds': preds})
        if y is not None:
            hist[pid].append((r['ord'], y))
    return out


def metrics(pairs):
    if len(pairs) < 3:
        return None
    ys = [p[0] for p in pairs]; ps = [p[1] for p in pairs]
    err = [a - b for a, b in zip(ys, ps)]
    mae = statistics.mean(abs(e) for e in err)
    rmse = math.sqrt(statistics.mean(e * e for e in err))
    try:
        r = statistics.correlation(ys, ps)
    except (statistics.StatisticsError, ValueError):
        r = float('nan')
    ybar = statistics.mean(ys)
    sst = sum((y - ybar) ** 2 for y in ys)
    sse = sum(e * e for e in err)
    r2 = 1 - sse / sst if sst > 0 else float('nan')
    return {'mae': mae, 'rmse': rmse, 'r': r, 'r2': r2, 'n': len(pairs)}


def block_bootstrap(recs, a, b, n=1000, seed=20260907):
    """Difference in MAE between two baselines, resampled over PLAYERS.

    Games within a player are not independent -- a player's role persists -- so
    resampling player-games would understate the interval. The unit is the
    player and every one of that player's games travels with him.
    """
    rng = random.Random(seed)
    by_p = collections.defaultdict(list)
    for rec in recs:
        by_p[rec['row']['gsis_id']].append(rec)
    keys = list(by_p)
    if len(keys) < 5:
        return None
    diffs = []
    for _ in range(n):
        samp = [rng.choice(keys) for _ in keys]
        ea = eb = cnt = 0.0
        for k in samp:
            for rec in by_p[k]:
                ea += abs(rec['y'] - rec['preds'][a])
                eb += abs(rec['y'] - rec['preds'][b])
                cnt += 1
        if cnt:
            diffs.append(ea / cnt - eb / cnt)
    diffs.sort()
    return {'mean': statistics.mean(diffs),
            'lo': diffs[int(0.025 * len(diffs))],
            'hi': diffs[int(0.975 * len(diffs))],
            'n_players': len(keys)}


def role_flag(rows):
    """Role change, declared in PREDECLARATION_P1.md before any result:
    |snap_share(t-1) - mean snap_share(t-2..t-4)| > 0.20. Uses only prior
    games, so it is a pregame label."""
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        pid = r['gsis_id']
        past = [v for v in hist[pid] if v is not None]
        if len(past) >= 4:
            recent, base = past[-1], statistics.mean(past[-4:-1])
            r['role_change'] = 1 if abs(recent - base) > 0.20 else 0
        else:
            r['role_change'] = None
        r['starter_prior'] = (1 if past and past[-1] >= 0.50
                              else (0 if past else None))
        r['n_prior_games'] = len(past)
        hist[pid].append(r.get('snap_share'))
    return rows


BASELINES = ['prior', 'std', 'lag1', 'ma3', 'ma5', 'ewma3',
             'shrink2', 'shrink4', 'shrink8']


def main(conditional=False):
    rows = load()
    rows, added = extend_with_zeros(rows)
    rows = add_shares(rows)
    rows = role_flag(rows)
    if conditional:
        # ARM B, conditional on appearing. A different and easier question than
        # "will he be on the field and get opportunity". Both are reported
        # because the unconditional panel is heavily zero-inflated -- measured
        # on 2022-2025 WR/TE/RB, 29.0% of snap_share and 46.0% of target_share
        # values are exactly zero -- so a model can score well on MAE there by
        # predicting zero. Correlation is what exposes that; MAE alone hides it.
        rows = [r for r in rows if r.get('did_not_appear') == 0]
    print(f'panel {len(rows)} rows ({added} zero rows added; '
          f'ARM={"CONDITIONAL" if conditional else "UNCONDITIONAL"})')

    results = {}
    for target, positions in TARGETS.items():
        results[target] = {}
        for ev in EVAL_SEASONS:
            train = [r for r in rows if r['season'] < ev]
            prior = {}
            for pos in positions:
                vals = [r[target] for r in train
                        if r['position'] == pos and r.get(target) is not None]
                if vals:
                    prior[(pos, target)] = statistics.mean(vals)
            if not prior:
                continue
            recs = build_predictions(
                [r for r in rows if r['season'] <= ev], target, positions, prior)
            recs = [x for x in recs if x['row']['season'] == ev]
            if len(recs) < 50:
                continue
            per = {}
            for b in BASELINES:
                m = metrics([(x['y'], x['preds'][b]) for x in recs])
                if m:
                    per[b] = m
            best = min(per, key=lambda b: per[b]['mae'])
            # The question the directive actually asks is whether ANYTHING
            # beats persistence. When lag1 is itself the winner, comparing best
            # to lag1 gives a difference of exactly zero by construction and
            # answers nothing -- so the challenger is always the best NON-lag1
            # baseline, and lag1 is always the incumbent.
            non_lag = min((b for b in per if b != 'lag1'),
                          key=lambda b: per[b]['mae'])
            results[target][ev] = {
                'n': len(recs), 'per_baseline': per, 'best': best,
                'challenger': non_lag,
                'challenger_vs_lag1': block_bootstrap(recs, non_lag, 'lag1'),
                'best_vs_prior': block_bootstrap(recs, best, 'prior'),
                'recs_meta': {
                    'positions': list(positions),
                    'mean_y': statistics.mean(x['y'] for x in recs),
                    'sd_y': (statistics.pstdev([x['y'] for x in recs])
                             if len(recs) > 1 else 0.0),
                },
            }
            # subgroups on the best baseline and on lag1
            subs = {}
            def sub(name, pred, _best=best, _ch=non_lag):
                sel = [x for x in recs if pred(x)]
                if len(sel) >= 50:
                    subs[name] = {
                        b: metrics([(x['y'], x['preds'][b]) for x in sel])
                        for b in {_best, _ch, 'lag1', 'prior'}}
                    subs[name]['n'] = len(sel)
            for pos in positions:
                sub(f'pos={pos}', lambda x, p=pos: x['row']['position'] == p)
            sub('role=stable', lambda x: x['row'].get('role_change') == 0)
            sub('role=change', lambda x: x['row'].get('role_change') == 1)
            sub('starter', lambda x: x['row'].get('starter_prior') == 1)
            sub('backup', lambda x: x['row'].get('starter_prior') == 0)
            sub('lowhist(<4)', lambda x: x['n_prior'] < 4)
            sub('did_not_appear',
                lambda x: x['row'].get('did_not_appear') == 1)
            results[target][ev]['subgroups'] = subs
    tag = 'cond' if conditional else 'uncond'
    json.dump(results, open(f'{SP}/results_{tag}.json', 'w'), indent=1,
              default=lambda o: None)
    print('wrote results.json')

    for target in TARGETS:
        print(f'\n=== {target} ({",".join(TARGETS[target])})')
        for ev in EVAL_SEASONS:
            d = results[target].get(ev)
            if not d:
                continue
            per = d['per_baseline']
            line = '  '.join(f'{b}={per[b]["mae"]:.4f}' for b in BASELINES
                             if b in per)
            bb = d['challenger_vs_lag1']
            ch = d['challenger']
            beats = (bb and bb['hi'] < 0)
            print(f' {ev} n={d["n"]:6d} lag1={per["lag1"]["mae"]:.4f} '
                  f'{ch}={per[ch]["mae"]:.4f} r={per[ch]["r"]:.3f} '
                  f'| {ch}-lag1 {bb["mean"]:+.5f} '
                  f'[{bb["lo"]:+.5f},{bb["hi"]:+.5f}] '
                  f'{"BEATS persistence" if beats else "does NOT beat persistence"}'
                  if bb else f' {ev} n={d["n"]}')
            print(f'      {line}')


if __name__ == '__main__':
    main(conditional='--conditional' in sys.argv)
