"""A3G measurement helpers. Scoring and acceptance are fixed in
predeclaration_a3g.md; this file only computes what that document declared.

THE LIKE-FOR-LIKE RULE IS ENFORCED HERE, NOT REMEMBERED.

Reality supplies ONE draw per game. A model statistic that is going to stand
next to a realised series is therefore computed one draw per game, over the
games of the slate, and reported as a distribution over draws. This project has
inflated a correlation six times by averaging the draws first and correlating
the per-game means against a realised series; `per_draw` is written so that the
inflated version is not reachable by accident -- it takes an (n_games, m)
matrix and never collapses the m axis before the statistic.

The historical comparator is put on the same footing: a 16-game model statistic
is compared against 16-game historical subsets, never against the 1,615-game
value, because a correlation over 16 points and one over 1,615 points do not
have the same sampling distribution.
"""
from __future__ import annotations

import csv
import glob
import gzip
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production import team_volume_v1 as TV                      # noqa: E402

METRICS = TV.METRICS
PANEL = os.path.join(_ROOT, 'nfl', 'research', 'inputs', 'denom_panel.csv.gz')
TOTAL_METRIC = 'team_off_snaps'


# ------------------------------------------------------------------ inputs
def slate(season, week):
    """The (away, home) pairs of one week, from the captured schedule."""
    snaps = sorted(glob.glob(os.path.join(_ROOT, 'nfl', 'vintage',
                                          'schedules.*.csv.gz')))
    if not snaps:
        return Outcome.blocked('NO_SCHEDULE_SNAPSHOT',
                               'no schedules artifact has been captured',
                               cause=Cause.DEPENDENCY)
    out = []
    with gzip.open(snaps[-1], 'rt') as fh:
        for r in csv.DictReader(fh):
            if (r.get('season') == str(season) and r.get('week') == str(week)
                    and r.get('game_type') == 'REG'):
                out.append((r['away_team'], r['home_team']))
    if not out:
        return Outcome.blocked(
            'NO_GAMES_FOR_SLATE',
            f'the captured schedule carries no REG games for {season} week '
            f'{week}', cause=Cause.DATA)
    return Outcome.ok('SLATE_RESOLVED', value=sorted(out), n_games=len(out),
                      snapshot=os.path.basename(snaps[-1]))


def historical_games(max_season=None):
    """Paired historical games: [(row_a, row_b)], both sides present.

    An unpaired team-game is DROPPED and counted, never half-used.
    """
    rows = []
    with gzip.open(PANEL, 'rt') as fh:
        for r in csv.DictReader(fh):
            r['season'], r['ord'] = int(r['season']), int(r['ord'])
            for k in METRICS:
                r[k] = int(r[k])
            if max_season is None or r['season'] <= max_season:
                rows.append(r)
    by = {}
    for r in rows:
        by.setdefault((r['ord'],) + tuple(sorted((r['team'], r['opponent']))),
                      []).append(r)
    paired = [tuple(v) for v in by.values() if len(v) == 2]
    if not paired:
        return Outcome.blocked('NO_PAIRED_HISTORY',
                               'no historical game has both sides in the '
                               'panel', cause=Cause.DATA)
    return Outcome.ok('HISTORY_PAIRED', value=paired,
                      n_team_games=len(rows), n_games=len(by),
                      n_paired=len(paired),
                      n_unpaired_dropped=len(by) - len(paired))


# -------------------------------------------------------------- statistics
def _sym_corr(a, b, rank=False):
    """Symmetrised correlation of an unordered pair. Never home-vs-away."""
    x = np.concatenate([np.asarray(a, float), np.asarray(b, float)])
    y = np.concatenate([np.asarray(b, float), np.asarray(a, float)])
    if rank:
        x, y = TV._rank_avg(x), TV._rank_avg(y)
    if x.std() == 0 or y.std() == 0:
        return float('nan')
    return float(np.corrcoef(x, y)[0, 1])


def per_draw(mat_a, mat_b, fn):
    """Apply `fn(col_a, col_b)` once per draw. (n_games, m) in, (m,) out.

    The m axis is never collapsed before `fn` runs. That is the whole point.
    """
    A, B = np.asarray(mat_a, float), np.asarray(mat_b, float)
    if A.shape != B.shape:
        raise ValueError(f'shape mismatch {A.shape} vs {B.shape}')
    if A.ndim != 2:
        raise ValueError('per_draw needs an (n_games, m) matrix')
    return np.array([fn(A[:, d], B[:, d]) for d in range(A.shape[1])])


def band(v, lo=5, hi=95):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {'n': 0, 'mean': None, 'p05': None, 'p95': None}
    return {'n': int(v.size), 'mean': float(v.mean()),
            'p05': float(np.percentile(v, lo)),
            'p95': float(np.percentile(v, hi))}


def hist_subset_band(paired, metric, k, reps, seed):
    """The historical statistic recomputed on k-game subsets, `reps` times."""
    rng = np.random.default_rng(seed)
    a = np.array([g[0][metric] for g in paired], float)
    b = np.array([g[1][metric] for g in paired], float)
    out = []
    for _ in range(reps):
        ix = rng.choice(len(paired), size=k, replace=False)
        out.append(_sym_corr(a[ix], b[ix]))
    return band(out)


def hist_total_band(paired, k, reps, seed):
    rng = np.random.default_rng(seed)
    tot = np.array([g[0][TOTAL_METRIC] + g[1][TOTAL_METRIC] for g in paired],
                   float)
    out = [float(tot[rng.choice(len(tot), size=k, replace=False)].std(ddof=1))
           for _ in range(reps)]
    return band(out)


# ------------------------------------------------------------------ draws
def draw_slate(season, week, pairs, coupling, m, seed, per_game=True):
    """Draw a whole slate. `per_game=True` matches how production calls it.

    Returns {(game_index, team): {metric: (m,) array}} plus the evidence of
    the first call, or an Outcome that is not PASS.
    """
    out, ev = {}, None
    if per_game:
        for gi, (away, home) in enumerate(pairs):
            o = TV.forecast(season, week, [away, home], m=m, seed=seed,
                            joint_residuals=True,
                            game_pairs=([(away, home)] if coupling != 'none'
                                        else None),
                            game_coupling=coupling)
            if o.state is not State.PASS:
                return o
            ev = ev or o.evidence
            for t in (away, home):
                out[(gi, t)] = {mm: np.asarray(o.value[(mm, t)], float)
                                for mm in METRICS}
    else:
        teams = [t for p in pairs for t in p]
        o = TV.forecast(season, week, teams, m=m, seed=seed,
                        joint_residuals=True,
                        game_pairs=(list(pairs) if coupling != 'none'
                                    else None),
                        game_coupling=coupling)
        if o.state is not State.PASS:
            return o
        ev = o.evidence
        for gi, (away, home) in enumerate(pairs):
            for t in (away, home):
                out[(gi, t)] = {mm: np.asarray(o.value[(mm, t)], float)
                                for mm in METRICS}
    if not out:
        return Outcome.blocked('NO_DRAWS', 'the slate produced no draws',
                               cause=Cause.DATA)
    return Outcome.ok('SLATE_DRAWN', value=out, first_call_evidence=ev,
                      n_rows=len(out))


def sides(drawn, pairs, metric):
    """(n_games, m) matrices for the two sides, in slate order."""
    A = np.stack([drawn[(gi, p[0])][metric] for gi, p in enumerate(pairs)])
    B = np.stack([drawn[(gi, p[1])][metric] for gi, p in enumerate(pairs)])
    return A, B


def marginal_summary(drawn):
    """mean / sd / p05 / p50 / p95 per (team, metric). The marginal evidence."""
    s = {}
    for (gi, t), d in drawn.items():
        for mm, v in d.items():
            s[f'{t}|{mm}'] = {
                'mean': float(v.mean()), 'sd': float(v.std(ddof=1)),
                'p05': float(np.percentile(v, 5)),
                'p50': float(np.percentile(v, 50)),
                'p95': float(np.percentile(v, 95))}
    return s


def marginal_max_move(a, b):
    """Largest relative move of any summary statistic, and where it happened."""
    worst, where, stat = 0.0, None, None
    for k in sorted(set(a) & set(b)):
        for s in ('mean', 'sd', 'p05', 'p50', 'p95'):
            x, y = a[k][s], b[k][s]
            den = max(abs(x), 1e-9)
            rel = abs(y - x) / den
            if rel > worst:
                worst, where, stat = rel, k, s
    return {'max_abs_relative_move': float(worst), 'at': where, 'statistic': stat,
            'n_compared': len(set(a) & set(b))}


def zero_floor_count(drawn):
    """Draws sitting exactly on the zero floor -- this project's clip counter."""
    return int(sum(int((v == 0.0).sum()) for d in drawn.values()
                   for v in d.values()))
