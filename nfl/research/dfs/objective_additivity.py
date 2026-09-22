"""Is a summed per-player simulation statistic a valid lineup objective?

Enumerates EVERY legal DK Classic lineup from a small correlated pool, scores
each lineup the correct way -- world by world, then evaluate the LINEUP
distribution -- and compares that ranking against the ranking you get by
summing the per-player statistics `score_pool` produces.
"""
import itertools
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
import numpy as np
from nfl.dfs.classic import optimizer as O, rules as R

RNG = np.random.default_rng(20260922)
W = 20000

# Two games, four teams. Same-team players share a team factor; the two teams
# in a game share a game factor (shootout / slog). That is the correlation a
# GPP lineup is built to exploit.
# Three teams. AAA and BBB play each other, so lineups that stack them pick
# up the game factor; CCC is in a different game and does not. That contrast
# is the whole point -- it is the correlation a GPP lineup exists to buy.
TEAMS = [('AAA', 'BBB'), ('CCC',)]
SPEC = [('QB', 1), ('RB', 1), ('WR', 2), ('TE', 1), ('DST', 1)]
MEAN = {'QB': 18.0, 'RB': 11.0, 'WR': 11.0, 'TE': 8.0, 'DST': 7.0}
SD = {'QB': 7.0, 'RB': 7.0, 'WR': 8.0, 'TE': 5.0, 'DST': 5.0}

players, draws, i = [], [], 0
game_factor = {g: RNG.standard_normal(W) for g in range(len(TEAMS))}
team_factor = {}
for gi, tt in enumerate(TEAMS):
    for t in tt:
        team_factor[t] = RNG.standard_normal(W)
for gi, tt in enumerate(TEAMS):
    for t in tt:
        opp = next((x for x in tt if x != t), 'ZZZ')
        for pos, k in SPEC:
            for j in range(k):
                z = (0.55 * team_factor[t] + 0.35 * game_factor[gi]
                     + 0.75 * RNG.standard_normal(W))
                d = np.maximum(MEAN[pos] + SD[pos] * z + j * -1.5, 0.0)
                players.append(O.Player(
                    gsis_id=f'{t}-{pos}{j}', name=f'{t} {pos}{j}',
                    position=pos, team=t, opponent=opp, salary=5000,
                    dk_id=str(9000 + i), value=0.0, draw_row=i))
                draws.append(d)
                i += 1
M = np.array(draws)
print(f'pool {len(players)} players, {W} worlds')

by_pos = {}
for p in players:
    by_pos.setdefault(p.position, []).append(p)

# Every legal lineup. No salary cap: this is a question about the OBJECTIVE,
# and a cap would only shrink the field without changing the mathematics.
lineups = []
for shape in R.LEGAL_SHAPES:
    picks = [itertools.combinations(by_pos[pos], shape[pos]) for pos in shape]
    for combo in itertools.product(*picks):
        lineups.append(tuple(sorted((p for grp in combo for p in grp),
                                    key=lambda x: x.gsis_id)))
lineups = sorted(set(lineups), key=lambda lu: tuple(p.gsis_id for p in lu))
print(f'{len(lineups)} legal lineups enumerated')

idx = np.array([[p.draw_row for p in lu] for lu in lineups])
A = np.zeros((len(lineups), len(players)))
for r, row in enumerate(idx):
    A[r, row] = 1.0
LS = A @ M                                 # lineups x worlds  <- THE CORRECT
print(f'lineup score matrix {LS.shape}')   #    object to evaluate

# --- the correct tournament metrics, on the LINEUP distribution -----------
n_lu = LS.shape[0]
lin_mean = LS.mean(axis=1)
k10 = max(1, int(round(0.10 * n_lu)))
k1 = max(1, int(round(0.01 * n_lu)))
thr10 = np.partition(LS, n_lu - k10, axis=0)[n_lu - k10, :]
thr1 = np.partition(LS, n_lu - k1, axis=0)[n_lu - k1, :]
true_top10 = (LS >= thr10).mean(axis=1)
true_top1 = (LS >= thr1).mean(axis=1)
true_first = (LS >= LS.max(axis=0)).mean(axis=1)

# --- the additive proxies: sum the per-player statistic -------------------
proxy = {}
for obj in (O.OBJ_MEAN, O.OBJ_PERCENTILE, O.OBJ_TOP_X, O.OBJ_EXPECTED_RANK):
    out = O.score_pool(players, objective=obj,
                       draws=None if obj == O.OBJ_MEAN else M, top_x=0.10)
    assert out.state.name == 'PASS', (obj, out.code)
    if obj == O.OBJ_MEAN:
        # score_pool leaves `value` alone for the mean objective, so supply
        # the same thing production supplies: the player's mean.
        vals = {p.gsis_id: float(M[p.draw_row].mean()) for p in players}
    else:
        vals = {p.gsis_id: p.value for p in out.value['players']}
    proxy[obj] = np.array([sum(vals[p.gsis_id] for p in lu)
                           for lu in lineups])


def spearman(a, b):
    ra = a.argsort().argsort().astype(float)
    rb = b.argsort().argsort().astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def name(lu):
    return ' '.join(p.gsis_id for p in lu)


print()
print('TARGET the proxy is standing in for, and how well the proxy ranks it')
print(f'{"proxy (summed per player)":34s} {"vs lineup mean":>15s} '
      f'{"vs true top-10%":>16s} {"vs true top-1%":>15s} {"vs P(1st)":>10s}')
for obj, v in proxy.items():
    print(f'{obj:34s} {spearman(v, lin_mean):15.4f} '
          f'{spearman(v, true_top10):16.4f} {spearman(v, true_top1):15.4f} '
          f'{spearman(v, true_first):10.4f}')

print()
print('EXACTNESS OF THE MEAN, which IS additive:')
err = np.abs(proxy[O.OBJ_MEAN] - lin_mean).max()
print(f'  max |sum(player mean) - mean(lineup score)| = {err:.3e}')

print()
print('WHO EACH CRITERION ACTUALLY PICKS')
for label, v in (('TRUE lineup top-1%', true_top1),
                 ('TRUE P(first)', true_first),
                 ('TRUE lineup mean', lin_mean)):
    b = int(v.argmax())
    print(f'  {label:26s} -> {name(lineups[b]):68s} '
          f'top1%={true_top1[b]:.4f} mean={lin_mean[b]:.2f}')
for obj, v in proxy.items():
    b = int(v.argmax())
    print(f'  summed {obj:19s} -> {name(lineups[b]):68s} '
          f'top1%={true_top1[b]:.4f} mean={lin_mean[b]:.2f}')

print()
print('HEAD-TO-HEAD INVERSION (the counterexample)')
for obj in (O.OBJ_PERCENTILE, O.OBJ_TOP_X, O.OBJ_EXPECTED_RANK):
    v = proxy[obj]
    a = int(v.argmax())                      # what the proxy would choose
    b = int(true_top1.argmax())              # what a GPP actually wants
    if a == b:
        print(f'  {obj}: proxy and truth agree on the argmax')
        continue
    print(f'  {obj}')
    print(f'    proxy picks  {name(lineups[a])}')
    print(f'      true top-1% {true_top1[a]:.4f}  P(1st) {true_first[a]:.5f}'
          f'  mean {lin_mean[a]:.2f}  sd {LS[a].std():.2f}')
    print(f'    truth wants  {name(lineups[b])}')
    print(f'      true top-1% {true_top1[b]:.4f}  P(1st) {true_first[b]:.5f}'
          f'  mean {lin_mean[b]:.2f}  sd {LS[b].std():.2f}')
    print(f'    the proxy ranks the better lineup '
          f'#{int((v > v[b]).sum()) + 1} of {n_lu}')


# --------------------------------------------------------------------------
doc = {
    'artifact': 'CLASSIC_OBJECTIVE_ADDITIVITY',
    'spec_version': 'classic-objective-additivity-1',
    'question': 'score_pool assigns each player a statistic computed across '
                'shared simulated worlds, and the search maximises the SUM of '
                'those statistics over a lineup. Is that a valid lineup '
                'objective?',
    'method': 'enumerate EVERY legal DK Classic lineup from a small '
              'correlated pool, score each lineup the correct way -- world by '
              'world, lineup_score_j = sum(player_score_pj) -- and compare '
              'the resulting ranking against the ranking you get by summing '
              'the per-player statistics.',
    'reproduce': 'python3.12 nfl/research/dfs/objective_additivity.py',
    'fixture': {'players': len(players), 'worlds': W, 'lineups': n_lu,
                'teams': ['AAA', 'BBB', 'CCC'],
                'correlation': 'each player z = 0.55*team + 0.35*game + '
                               '0.75*idiosyncratic; AAA and BBB share a game, '
                               'CCC does not'},
    'answer': {
        'EXPECTED_FANTASY_POINTS': 'ADDITIVE AND VALID. max |sum(player mean) '
                                   f'- mean(lineup score)| = {err:.3e}, which '
                                   'is float noise. Expectation is linear; '
                                   'correlation does not affect it.',
        'MEAN_WITHIN_WORLD_PERCENTILE': 'NOT ADDITIVE',
        'TOP_X_PERCENT_FREQUENCY': 'NOT ADDITIVE',
        'EXPECTED_RANK': 'NOT ADDITIVE',
    },
    'spearman_vs_true_lineup_metric': {
        obj: {'lineup_mean': round(spearman(v, lin_mean), 4),
              'true_top_10pct': round(spearman(v, true_top10), 4),
              'true_top_1pct': round(spearman(v, true_top1), 4),
              'true_p_first': round(spearman(v, true_first), 4)}
        for obj, v in proxy.items()},
    'counterexample': {
        'what_truth_wants': {
            'lineup': name(lineups[int(true_top1.argmax())]),
            'true_top_1pct': round(float(true_top1.max()), 4),
            'p_first': round(float(true_first[int(true_top1.argmax())]), 5),
            'lineup_mean': round(float(lin_mean[int(true_top1.argmax())]), 2),
            'lineup_sd': round(float(LS[int(true_top1.argmax())].std()), 2)},
        'what_each_proxy_picks': {
            obj: {
                'lineup': name(lineups[int(v.argmax())]),
                'true_top_1pct': round(float(true_top1[int(v.argmax())]), 4),
                'p_first': round(float(true_first[int(v.argmax())]), 5),
                'lineup_mean': round(float(lin_mean[int(v.argmax())]), 2),
                'lineup_sd': round(float(LS[int(v.argmax())].std()), 2),
                'rank_it_gives_the_correct_lineup':
                    int((v > v[int(true_top1.argmax())]).sum()) + 1,
                'of': n_lu}
            for obj, v in proxy.items()},
    },
    'reading': 'the three world-based objectives are summed per player, and '
               'summing destroys exactly the property a tournament pays for. '
               'The correct lineup is a full AAA/BBB game stack: lower mean, '
               'much higher spread, and the highest probability of a winning '
               'score. Every summed proxy prefers a decorrelated lineup with '
               'a slightly higher mean and a far worse chance of winning. '
               'Note also that summed EXPECTED_FANTASY_POINTS tracks the true '
               'tournament metrics AS WELL AS or BETTER THAN the three '
               'objectives that were built to beat it, so the non-additive '
               'objectives are not merely invalid, they buy nothing.',
    'production_exposure': 'ZERO TODAY, and this was verified rather than '
                           'assumed. score_pool has no caller outside the '
                           'test suite; nfl/dfs/classic/pool.py sets '
                           'Player.value from the board dk_mean and never '
                           'sets draw_row, so score_pool would refuse a '
                           'production pool with POOL_NOT_ALIGNED_TO_DRAWS. '
                           'The three objectives are ORPHANED, exported, and '
                           'documented as usable. That is the hazard.',
}
out = _REPO / 'nfl/research/dfs/CLASSIC_OBJECTIVE_ADDITIVITY.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(doc, indent=1) + '\n')
print(f'\nwrote {out.relative_to(_REPO)}')
