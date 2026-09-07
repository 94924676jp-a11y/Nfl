"""Leakage probe. Predeclared in PREDECLARATION_P1.md before any result.

The claim under test is that no baseline reads game t. If a feature builder
were accidentally including the target week, then destroying the temporal
ORDER of a player's values while leaving the multiset intact would not hurt it
much -- the same-game value would still be there to be read. Under an honest
lagged builder, shuffling within player must degrade every history-based
baseline toward the player's own mean.

This is a necessary condition, not a proof of no leakage. It cannot detect a
leak that is constant within a player.
"""
import collections, csv, random, statistics, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M

rows = M.load()
rows, _ = M.extend_with_zeros(rows)
rows = M.add_shares(rows)

EV = 2024
for target, positions in [('target_share', ('WR', 'TE', 'RB')),
                          ('rpr', ('WR', 'TE', 'RB')),
                          ('snap_share', ('WR', 'TE', 'RB'))]:
    train = [r for r in rows if r['season'] < EV]
    prior = {}
    for pos in positions:
        v = [r[target] for r in train
             if r['position'] == pos and r.get(target) is not None]
        if v:
            prior[(pos, target)] = statistics.mean(v)

    def run(rs):
        recs = M.build_predictions([r for r in rs if r['season'] <= EV],
                                   target, positions, prior)
        recs = [x for x in recs if x['row']['season'] == EV]
        return {b: M.metrics([(x['y'], x['preds'][b]) for x in recs])['mae']
                for b in ('lag1', 'ma3', 'ewma3', 'std', 'prior')}

    real = run(rows)

    # Shuffle each player's target values across his own games, keeping the
    # multiset. Order is destroyed; level is not.
    rng = random.Random(4242)
    by_p = collections.defaultdict(list)
    for r in rows:
        if r['position'] in positions and r.get(target) is not None:
            by_p[r['gsis_id']].append(r)
    shuf = [dict(r) for r in rows]
    idx = {(r['gsis_id'], r['ord']): r for r in shuf}
    for pid, rs in by_p.items():
        vals = [r[target] for r in rs]
        rng.shuffle(vals)
        for r, v in zip(rs, vals):
            idx[(pid, r['ord'])][target] = v
    fake = run(shuf)

    print(f'\n{target}:')
    for b in ('lag1', 'ma3', 'ewma3', 'std', 'prior'):
        d = fake[b] - real[b]
        print(f'  {b:<7} real MAE {real[b]:.4f}  shuffled {fake[b]:.4f}  '
              f'{d:+.4f}  {"degrades (expected)" if d > 1e-6 else "NO DEGRADATION"}')
