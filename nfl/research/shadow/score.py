"""Score the SEALED NE@SEA forecast against the completed game.

REFUSES TO RUN unless the sealed artifact hashes to the value recorded at seal
time. Scoring a forecast you may have edited is not scoring.

Everything here is a proper score or a direct comparison. Nothing is tuned,
nothing is promoted, and no threshold is chosen after the fact: the prop-style
thresholds are round numbers laid out around each metric's forecast median,
which is a rule fixed in advance rather than a line taken from a book. No book
price enters this file, by design and by project rule.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.shadow import actuals as ACT                    # noqa: E402

_DIR = _REPO / 'nfl' / 'research' / 'shadow' / 'g1_ne_sea'


def verify_seal() -> dict:
    """Every sealed file must still hash to what SEAL_SHA256.txt recorded."""
    rec = {}
    for line in (_DIR / 'SEAL_SHA256.txt').read_text().splitlines():
        if not line.strip():
            continue
        h, p = line.split()
        rec[p] = h
    bad = []
    for p, h in sorted(rec.items()):
        f = _REPO / p
        if not f.exists():
            bad.append(f'{p}: MISSING')
            continue
        got = hashlib.sha256(f.read_bytes()).hexdigest()
        if got != h:
            bad.append(f'{p}: {got} != {h}')
    if bad:
        raise SystemExit('SEAL_BROKEN: ' + '; '.join(bad))
    return rec


def draws() -> dict:
    with gzip.open(_DIR / 'player_draws.npz.gz', 'rb') as fh:
        z = np.load(io.BytesIO(fh.read()))
        return {k: z[k] for k in z.files}


# --- proper scores ---------------------------------------------------------

def crps(x: np.ndarray, y: float) -> float:
    """CRPS of an empirical predictive sample. E|X-y| - 0.5 E|X-X'|, with the
    second term computed exactly from the sorted sample rather than by
    resampling."""
    x = np.sort(np.asarray(x, float))
    n = x.size
    t1 = float(np.mean(np.abs(x - y)))
    # sum_{i<j}(x_j - x_i) = sum_i x_i * (2i - n + 1), i zero-based
    i = np.arange(n)
    t2 = float((x * (2 * i - n + 1)).sum()) / (n * n)
    return t1 - t2


def pit(x: np.ndarray, y: float) -> dict:
    """Non-randomised PIT for a discrete predictive sample.

    A single number is not honest for a discrete forecast, so the bracket
    [F(y-), F(y)] is reported alongside the midpoint. The midpoint is the
    deterministic mid-PIT; it is NOT a randomised PIT and the two must not be
    read as the same statistic.
    """
    x = np.asarray(x, float)
    n = x.size
    lo = float((x < y).sum()) / n
    hi = float((x <= y).sum()) / n
    return {'F_below': round(lo, 6), 'F_at_or_below': round(hi, 6),
            'mid_pit': round((lo + hi) / 2.0, 6),
            'p_mass_at_actual': round(hi - lo, 6)}


def interval(x: np.ndarray, level: float) -> tuple:
    a = (1.0 - level) / 2.0
    return (float(np.quantile(x, a)), float(np.quantile(x, 1.0 - a)))


def summarise(x: np.ndarray, y=None, levels=(0.50, 0.80, 0.90, 0.95)) -> dict:
    x = np.asarray(x, float)
    out = {
        'n_draws': int(x.size),
        'mean': round(float(x.mean()), 4),
        'sd': round(float(x.std(ddof=1)), 4),
        'percentiles': {str(p): round(float(np.percentile(x, p)), 3)
                        for p in (1, 5, 10, 25, 50, 75, 90, 95, 99)},
        'min': round(float(x.min()), 3), 'max': round(float(x.max()), 3),
    }
    if y is None:
        return out
    y = float(y)
    out['actual'] = y
    out['error_actual_minus_mean'] = round(y - float(x.mean()), 4)
    out['crps'] = round(crps(x, y), 4)
    out['pit'] = pit(x, y)
    out['coverage'] = {}
    for lv in levels:
        lo, hi = interval(x, lv)
        out['coverage'][f'{int(lv * 100)}%'] = {
            'lo': round(lo, 3), 'hi': round(hi, 3),
            'covered': bool(lo <= y <= hi)}
    # OUTSIDE THE SUPPORT is a different statement from "in the tail", and the
    # difference is the whole question the owner asked about extreme outcomes.
    out['outside_sample_support'] = bool(y < x.min() or y > x.max())
    return out


def thresholds(x: np.ndarray, step: float, k: int = 3) -> list:
    """Round thresholds either side of the forecast median. THE RULE IS FIXED
    IN ADVANCE: `step` per metric, k on each side, half-point lines so no draw
    can land exactly on one. No book price is consulted anywhere."""
    x = np.asarray(x, float)
    med = float(np.median(x))
    base = round(med / step) * step
    out = []
    for j in range(-k, k + 1):
        line = base + j * step + 0.5
        if line <= 0:
            continue
        out.append({'line': round(line, 1),
                    'p_over': round(float((x > line).mean()), 4),
                    'p_under': round(float((x < line).mean()), 4)})
    return out


# Step size per metric. Chosen to be the natural granularity of the quantity,
# fixed here rather than per-player.
# A step BELOW the quantity's granularity produces duplicate lines: at
# step 0.5 an integer metric yields both 1.0 and 1.5, which are different
# lines carrying identical probabilities because no draw can fall between
# them. Every count metric therefore steps by 1.
STEP = {'att': 5.0, 'cmp': 5.0, 'pyds': 25.0, 'ptd': 1.0, 'int': 1.0,
        'db': 5.0, 'sacks': 1.0, 'scr': 1.0, 'rush_opp': 1.0, 'ryds': 5.0,
        'rtd': 1.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pbp', required=True,
                    help='gzipped play-by-play, sealed before the forecast')
    ap.add_argument('--pbp-sha256', required=True,
                    help='the hash recorded when it was downloaded')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    seal = verify_seal()

    pbp = pathlib.Path(a.pbp)
    got = hashlib.sha256(pbp.read_bytes()).hexdigest()
    if got != a.pbp_sha256:
        raise SystemExit(f'OUTCOME_HASH_MISMATCH: {got} != {a.pbp_sha256}')

    art = json.loads((_DIR / 'forecast_artifact.json').read_text())
    sealed = json.loads((_DIR / 'SEALED_FORECAST.json').read_text())
    gid = art['game_id']

    rows = ACT.load(pbp, gid)
    nm = ACT.names(rows)
    team_act = ACT.team_actuals(rows)
    qb_act = ACT.qb_actuals(rows)
    tl = ACT.qb_timeline(rows)
    skill = ACT.receiving_rushing_actuals(rows)

    D = draws()
    man = json.loads((_DIR / 'player_draws_manifest.json').read_text())

    # --- team environment ------------------------------------------------
    teams = art['team_ids']
    team_rows = {}
    for met in ('team_off_snaps', 'team_dropbacks_part', 'team_targets',
                'team_carries', 'team_rz_carries'):
        key = f'team_volume__{met}'
        if key not in D:
            continue
        M = D[key]
        for i, t in enumerate(teams):
            act = (team_act.get(t) or {}).get(met)
            s = summarise(M[i], act['value'] if act else None)
            s['actual_basis'] = act['basis'] if act else 'ABSENT'
            if act and act['basis'] == 'SURROGATE':
                s['actual_surrogate'] = act['surrogate']
                s['actual_relation'] = act['relation']
                # A SURROGATE ACTUAL CANNOT CARRY A PROPER SCORE. Reporting a
                # CRPS against a different quantity would look like evidence
                # and be none.
                for k in ('crps', 'pit', 'coverage', 'outside_sample_support',
                          'error_actual_minus_mean'):
                    s.pop(k, None)
            team_rows[f'{t}|{met}'] = s

    # --- quarterbacks -----------------------------------------------------
    pids = art['player_ids']
    qb_index = {}
    for k, v in art['distributions'].items():
        for met, d in (v.get('qb') or {}).items():
            ref = d.get('draws_ref') or {}
            if 'row' in ref:
                qb_index[k] = ref['row']
            break
    # A QUARTERBACK WHO NEVER APPEARED HAS AN ACTUAL OF ZERO, NOT A MISSING
    # ACTUAL. The first version of this scorer left these players unscored
    # because they had no play-by-play row -- reading absence as "no
    # observation" when the game is complete and the observation is 0. Three
    # of the six forecast quarterbacks are in that state, and dropping them
    # would have removed every case the model got RIGHT by predicting near
    # zero.
    played = set(qb_act) | set(tl)
    qb_rows = {}
    for pid, row in sorted(qb_index.items(), key=lambda kv: kv[1]):
        did_play = pid in played
        rec = {'gsis_id': pid, 'name': nm.get(pid, ''),
               'played': did_play,
               'actual_basis': 'OBSERVED' if did_play else
                               'ZERO_BY_COMPLETION: the game is complete and '
                               'this player appears on no play, so every '
                               'count is a realised zero',
               'timeline': tl.get(pid), 'metrics': {}}
        for met in ('db', 'att', 'cmp', 'pyds', 'ptd', 'int', 'sacks', 'scr',
                    'rush_opp', 'ryds', 'rtd'):
            key = f'qb__{met}'
            if key not in D:
                continue
            x = D[key][row]
            act = (qb_act.get(pid) or {}).get(met, 0 if not did_play else None)
            s = summarise(x, act)
            s['thresholds'] = thresholds(x, STEP.get(met, 1.0))
            rec['metrics'][met] = s
        qb_rows[pid] = rec

    # --- TEAM-LEVEL QB AGGREGATE ------------------------------------------
    # WHO took the snaps and HOW MANY there were are separate questions, and
    # an in-game quarterback change destroys the first while leaving the
    # second untouched. Summing a team's quarterback rows WITHIN each draw is
    # legitimate precisely because the draw index is shared -- that is what
    # B13 stored the joint container for -- and it yields the distribution of
    # the quantity the model could actually have known about.
    dc = sealed['depth_chart']
    team_of = {}
    for k, v in dc.items():
        t, pos, _rank = k.split('|')
        if pos == 'QB':
            team_of[v] = t
    agg = {}
    for t in teams:
        idx = [r for pid, r in qb_index.items() if team_of.get(pid) == t]
        if not idx:
            continue
        block = {}
        for met in ('db', 'att', 'cmp', 'pyds', 'ptd', 'int', 'sacks', 'scr',
                    'rush_opp', 'ryds', 'rtd'):
            key = f'qb__{met}'
            if key not in D:
                continue
            x = D[key][idx, :].sum(axis=0)
            act = sum((qb_act.get(pid) or {}).get(met, 0)
                      for pid, r in qb_index.items() if team_of.get(pid) == t)
            block[met] = summarise(x, act)
        agg[t] = {'n_quarterbacks': len(idx), 'metrics': block}

    out = {
        'what': 'NE@SEA Game 1 shadow evaluation of the frozen V1 candidate',
        'promoted': False, 'prospective_eligible': False,
        'exploratory': True,
        'classification_of_all_findings': 'POST_V1_REFINEMENT',
        'seal': {'files': seal,
                 'outcome_sha256': a.pbp_sha256,
                 'outcome_downloaded_before_forecast': True},
        'game_id': gid,
        'kickoff_utc': art['kickoff_utc'],
        'written_at': art['written_at'],
        'model_configuration': art['model_configuration'],
        'candidate_components_applied': art['candidate_components_applied'],
        'candidate_components_not_reached':
            art['candidate_components_not_reached'],
        'information_set': sealed['information_set'],
        'stages': [{'stage': s['stage'], 'state': s['state'],
                    'code': s.get('code')} for s in sealed['run']['stages']],
        'final_score': {'home': rows[0].get('home_score'),
                        'away': rows[0].get('away_score'),
                        'home_team': rows[0].get('home_team'),
                        'away_team': rows[0].get('away_team')},
        'team_environment': team_rows,
        'team_actuals_raw': team_act,
        'quarterbacks': qb_rows,
        'team_qb_aggregate': agg,
        'skill_actuals_no_forecast_produced': skill,
        'depth_chart_as_of': sealed['depth_chart_as_of'],
        'depth_chart': sealed['depth_chart'],
    }
    p = pathlib.Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    print('WROTE', p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
