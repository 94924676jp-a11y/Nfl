"""Score a SEALED forecast against a final game. Permanent, cumulative.

THE FORECAST IS IMMUTABLE BEFORE THIS RUNS, AND THAT IS ENFORCED, NOT ASSUMED.
`score()` refuses unless every sealed file still hashes to the value recorded
at seal time. Scoring a forecast that may have been edited after the outcome
was known is not scoring; it is a description of the outcome.

ONE GAME CREATES A HYPOTHESIS. REPEATED INDEPENDENT MISSES CREATE A REFINEMENT
CANDIDATE. The cumulative ledger therefore carries a cluster count alongside
every rate, because player-metrics inside one game are not independent
observations of anything -- attempts, completions and yards for one passer are
near-deterministic functions of each other, and both teams share one game
script. A refinement candidate is raised only on games, never on rows.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import pathlib

import numpy as np

from nfl.product import distributions as D
from nfl.product import metrics as M

# The minimum number of INDEPENDENT GAMES before a repeated miss is allowed to
# be called a refinement candidate. Declared here, in advance, so it can never
# be lowered to make a finding qualify.
MIN_GAMES_FOR_CANDIDATE = 4
CLUSTER_UNIT = 'game'


class SealBroken(RuntimeError):
    """Named. A broken seal stops scoring; it does not warn and continue."""


def verify_seal(directory) -> dict:
    """Every file named in SEAL_SHA256.txt must still hash to its value."""
    d = pathlib.Path(directory)
    f = d / 'SEAL_SHA256.txt'
    if not f.exists():
        raise SealBroken(f'SEAL_RECORD_ABSENT: {f}. A forecast with no seal '
                         f'record cannot be shown to predate its outcome.')
    rec, bad, checked = {}, [], {}
    root = _repo()
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        h, name = line.split()
        rec[name] = h
        # THE FORECAST BEING SCORED IS THE ONE IN THIS DIRECTORY.
        #
        # The seal file records repo-relative paths, and resolving those FIRST
        # meant that scoring a copy verified the ORIGINAL: the copy could be
        # edited freely and the seal still passed, because it had hashed a
        # different file with the same name. A guard that verifies something
        # other than the thing it is guarding is worse than no guard, because
        # it reports success. Caught by the product layer's own tamper test.
        local = d / pathlib.Path(name).name
        target = local if local.exists() else (root / name)
        if not target.exists():
            bad.append(f'{name}: MISSING')
            continue
        got = hashlib.sha256(target.read_bytes()).hexdigest()
        checked[name] = str(target)
        if got != h:
            bad.append(f'{name}: {got[:16]} != {h[:16]} (read {target})')
    if bad:
        raise SealBroken('SEAL_BROKEN: ' + '; '.join(bad))
    if not rec:
        raise SealBroken(
            f'SEAL_RECORD_EMPTY: {f} names no file, so nothing was verified. '
            f'An empty seal record must never read as a clean one.')
    return {'files': rec, 'verified_paths': checked}


def _repo():
    return pathlib.Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ scores
def crps(x, y) -> float:
    """CRPS of an empirical predictive sample, exactly."""
    x = np.sort(np.asarray(x, float))
    n = x.size
    i = np.arange(n)
    return float(np.mean(np.abs(x - y))) - float(
        (x * (2 * i - n + 1)).sum()) / (n * n)


def pit(x, y) -> dict:
    """Non-randomised PIT. A single number is not honest for a discrete
    forecast, so the bracket is reported with the deterministic midpoint."""
    x = np.asarray(x, float)
    n = x.size
    lo = float((x < y).sum()) / n
    hi = float((x <= y).sum()) / n
    return {'F_below': round(lo, 6), 'F_at_or_below': round(hi, 6),
            'mid_pit': round((lo + hi) / 2.0, 6),
            'p_mass_at_actual': round(hi - lo, 6)}


LEVELS = (0.50, 0.80, 0.90, 0.95)


def score_metric(vec, actual) -> dict:
    x = np.asarray(vec, float)
    y = float(actual)
    out = {'actual': y, 'forecast_mean': round(float(x.mean()), 4),
           'forecast_median': round(float(np.percentile(x, 50)), 4),
           'median_error': round(y - float(np.percentile(x, 50)), 4),
           'mean_error': round(y - float(x.mean()), 4),
           'crps': round(crps(x, y), 4), 'pit': pit(x, y),
           'actual_percentile': round(pit(x, y)['mid_pit'] * 100.0, 2),
           'coverage': {}, 'n_draws': int(x.size)}
    for lv in LEVELS:
        a = (1.0 - lv) / 2.0
        lo, hi = float(np.quantile(x, a)), float(np.quantile(x, 1.0 - a))
        out['coverage'][f'{int(lv * 100)}%'] = {
            'lo': round(lo, 3), 'hi': round(hi, 3),
            'covered': bool(lo <= y <= hi)}
    # OUTSIDE THE SUPPORT is a different statement from "in the tail".
    out['outside_sample_support'] = bool(y < x.min() or y > x.max())
    out['miss_class'] = classify(out)
    return out


def classify(sc) -> str:
    """Miss classification. A stated rule, evaluated on the numbers."""
    if sc['outside_sample_support']:
        return 'OUTSIDE_DISTRIBUTION'
    if sc['coverage']['90%']['covered']:
        return ('CENTRAL' if sc['coverage']['50%']['covered']
                else 'WITHIN_DISTRIBUTION')
    return 'TAIL_MISS'


# ------------------------------------------------------------------ scoring
def score(forecast_dir, actuals, *, verify=True) -> dict:
    """Score one sealed forecast. `actuals` is {gsis_id: {layer/key: value}}."""
    seal = verify_seal(forecast_dir) if verify else {}
    fc = D.Forecast(forecast_dir)
    art = fc.artifact
    rows = []
    for pid, layers in fc.players().items():
        got = actuals.get(pid)
        for layer in sorted(layers):
            for key in layers[layer]:
                if (layer, key) not in M.SUPPORTED:
                    continue
                v = fc.vector(layer, key, pid)
                if v is None:
                    continue
                name = f'{layer}/{key}'
                if got is None or name not in got:
                    # NOT SCORED IS NOT ZERO. A player absent from the outcome
                    # feed may have played and not been credited, or not
                    # played at all, and only the caller knows which.
                    continue
                sc = score_metric(v, got[name])
                rows.append({'gsis_id': pid, 'layer': layer, 'metric': key,
                             'metric_label': M.SUPPORTED[(layer, key)]['label'],
                             'status': M.SUPPORTED[(layer, key)]['status'],
                             'position': got.get('_position'),
                             'team': got.get('_team'), **sc})
    return {
        'artifact': 'NFL_V1_POSTGAME_EVALUATION',
        'game_id': art.get('game_id'),
        'kickoff_utc': art.get('kickoff_utc'),
        'written_at': art.get('written_at'),
        'run_id': art.get('spec_hash'),
        'model_configuration': art.get('model_configuration'),
        'components_applied': art.get('candidate_components_applied') or [],
        'draw_content_digest': art.get('draw_content_digest'),
        'draws_sha256': fc.draws_sha256,
        'seal_verified': bool(seal),
        'sealed_files': (seal or {}).get('files', {}),
        'seal_verified_paths': (seal or {}).get('verified_paths', {}),
        'scored_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'n_scored': len(rows), 'rows': rows,
        'summary': summarise(rows),
        'exploratory': True, 'promoted': False,
    }


def summarise(rows) -> dict:
    """Aggregate, and always with the cluster count beside the rate."""
    def agg(sel):
        if not sel:
            return None
        cov = {f'{int(l * 100)}%':
               round(100.0 * sum(r['coverage'][f'{int(l * 100)}%']['covered']
                                 for r in sel) / len(sel), 1) for l in LEVELS}
        return {'n_rows': len(sel),
                'n_games': len({r.get('game_id') for r in sel
                                if r.get('game_id')}) or None,
                'mean_crps': round(float(np.mean([r['crps'] for r in sel])), 4),
                'median_abs_error': round(float(np.median(
                    [abs(r['median_error']) for r in sel])), 4),
                'bias_mean_error': round(float(np.mean(
                    [r['mean_error'] for r in sel])), 4),
                'median_mid_pit': round(float(np.median(
                    [r['pit']['mid_pit'] for r in sel])), 4),
                'coverage_pct': cov,
                'miss_classes': dict(collections.Counter(
                    r['miss_class'] for r in sel))}

    out = {'overall': agg(rows)}
    for dim, keyf in (('by_metric', lambda r: f'{r["layer"]}/{r["metric"]}'),
                      ('by_position', lambda r: r.get('position')),
                      ('by_team', lambda r: r.get('team')),
                      ('by_layer', lambda r: r['layer'])):
        buckets = collections.defaultdict(list)
        for r in rows:
            k = keyf(r)
            if k:
                buckets[k].append(r)
        out[dim] = {k: agg(v) for k, v in sorted(buckets.items())}
    out['caution'] = (
        'Rows inside one game are NOT independent observations. Attempts, '
        'completions and yards for one passer are near-deterministic '
        'functions of each other and both teams share one game script. Read '
        'n_games, never n_rows, as the sample size.')
    return out


# ------------------------------------------------- the cumulative ledger
LEDGER = 'nfl/product/EVALUATION_LEDGER.jsonl'


def append(evaluation, path=None) -> int:
    """Append one game's scored rows. Append-only; never rewritten."""
    # REFUSE BEFORE TOUCHING DISK. Opening the file first created an empty
    # ledger even on the refusal path, so a rejected append still left a file
    # behind that looked like a ledger with nothing in it.
    if not evaluation.get('rows'):
        raise RuntimeError(
            'EVALUATION_WROTE_NO_ROWS: an evaluation that scored nothing is '
            'not a result. An empty append would leave the ledger looking '
            'complete.')
    p = _repo() / (path or LEDGER)
    p.parent.mkdir(parents=True, exist_ok=True)
    base = {k: evaluation[k] for k in
            ('game_id', 'kickoff_utc', 'written_at', 'run_id',
             'model_configuration', 'draw_content_digest')}
    n = 0
    with open(p, 'a') as fh:
        for r in evaluation['rows']:
            fh.write(json.dumps({**base, **r}, sort_keys=True,
                                default=str) + '\n')
            n += 1
    return n


def load(path=None) -> list:
    p = _repo() / (path or LEDGER)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def cumulative(path=None) -> dict:
    """Everything scored so far, by every dimension the directive named."""
    rows = load(path)
    if not rows:
        return {'n_rows': 0, 'n_games': 0,
                'note': 'the ledger is empty; nothing has been scored yet'}
    games = {r['game_id'] for r in rows}
    out = {'n_rows': len(rows), 'n_games': len(games),
           'games': sorted(games), **summarise(rows)}
    by_week = collections.defaultdict(list)
    for r in rows:
        parts = str(r.get('game_id') or '').split('_')
        if len(parts) > 1:
            by_week[f'{parts[0]}_wk{parts[1]}'].append(r)
    out['by_week'] = {k: summarise(v)['overall'] for k, v in
                      sorted(by_week.items())}
    by_comp = collections.defaultdict(list)
    for r in rows:
        for c in (r.get('components_applied') or ['NONE']):
            by_comp[c].append(r)
    out['by_model_component'] = {k: summarise(v)['overall']
                                 for k, v in sorted(by_comp.items())}
    out['refinement_candidates'] = candidates(rows)
    return out


def candidates(rows) -> dict:
    """A repeated miss is a candidate ONLY across independent games.

    The bar is stated before any data arrives: a metric must miss its own 90%
    interval in the SAME DIRECTION across at least MIN_GAMES_FOR_CANDIDATE
    distinct games. One game is a hypothesis, and a metric that misses ten
    times inside one game has still missed once.
    """
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        per[f'{r["layer"]}/{r["metric"]}'][r['game_id']].append(r)
    out, held = {}, {}
    for metric, by_game in sorted(per.items()):
        high = {g for g, rs in by_game.items()
                if any(not x['coverage']['90%']['covered']
                       and x['pit']['mid_pit'] > 0.5 for x in rs)}
        low = {g for g, rs in by_game.items()
               if any(not x['coverage']['90%']['covered']
                      and x['pit']['mid_pit'] < 0.5 for x in rs)}
        for direction, gs in (('actual_above_interval', high),
                              ('actual_below_interval', low)):
            if len(gs) >= MIN_GAMES_FOR_CANDIDATE:
                out.setdefault(metric, []).append(
                    {'direction': direction, 'n_games': len(gs),
                     'games': sorted(gs)})
            elif gs:
                held.setdefault(metric, []).append(
                    {'direction': direction, 'n_games': len(gs),
                     'games': sorted(gs)})
    return {'bar': f'the same directional miss in at least '
                   f'{MIN_GAMES_FOR_CANDIDATE} distinct games',
            'cluster_unit': CLUSTER_UNIT,
            'candidates': out,
            'below_the_bar_watchlist': held,
            'note': 'A candidate is a REQUEST FOR A RESEARCH RULING, never a '
                    'licence to change the model. Nothing here modifies V1.'}
