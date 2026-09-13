"""Same-day DIAGNOSTIC retrospective: sealed pregame forecasts vs realised play.

THIS IS NOT PROSPECTIVE EVIDENCE AND MUST NEVER BE COUNTED AS ANY.

`postgame.run` refused all 65 week-1 sealed forecasts with
POSTGAME_ARTIFACT_NOT_CURRENTLY_ADMISSIBLE -- three mandatory controls
(`completeness_evidence_class`, `current_blocker_state`,
`prospective_evidence_eligibility`) say these artifacts may not COUNT toward
the decision floors. That gate is correct and is not touched here.

"May not count as evidence" and "may not be looked at" are different claims.
This module answers the second: how wrong was the forecast, and is the error
structured? It reuses the SAME governed pieces -- `actuals` for the realised
side, `postgame.EXACT_ESTIMANDS` for what may be scored at all, and
`postgame.REFUSED_ESTIMANDS` for what is refused by name -- so there is no
second definition of any quantity. What it does not do is write a ledger row,
increment a sample count, or clear a blocker.

CHRONOLOGY IS ENFORCED, NOT ASSUMED. Only seals with
`written_at < kickoff` are scored, and the outcome blob's digest is recorded
on every row. No forecast is regenerated, restamped or rewritten.

ROLE IS DEFINED PREGAME. A receiver's stratum comes from the FORECAST's own
ordering of projected targets, never from what he actually caught. Ranking by
realised production and then reporting that the model mis-ranked players is
circular -- it conditions the stratum on the outcome.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.product import forecast_stage as FS                        # noqa: E402
from nfl.research import postgame as PG                             # noqa: E402
from nfl.research.shadow import actuals as ACT                      # noqa: E402

SPEC_VERSION = 'same-day-retrospective/1.0.0'
NOT_EVIDENCE = ('DIAGNOSTIC ONLY. Not prospective evidence, not a ledger row, '
                'does not count toward any sample floor, and clears no '
                'blocker.')

COLUMNS = ('game_id', 'kickoff_utc', 'player', 'gsis_id', 'team', 'position',
           'metric', 'layer', 'forecast_stage', 'seal_written_at', 'run_id',
           'role_tier', 'model_mean', 'model_median',
           'q10', 'q25', 'q50', 'q75', 'q90',
           'actual', 'forecast_minus_actual', 'abs_error', 'pct_error',
           'pit', 'in_50', 'in_80', 'in_90', 'crps',
           'n_draws', 'completeness', 'qb3_configuration',
           'qb3_contaminated', 'qb3_contamination_basis', 'outcome_sha256')


def crps_sample(draws, y):
    d = np.sort(np.asarray(draws, float))
    n = len(d)
    if not n:
        return None
    t1 = float(np.abs(d - y).mean())
    i = np.arange(1, n + 1)
    t2 = float(2 * np.sum((2 * i - n - 1) * d) / (n * n))
    return t1 - 0.5 * t2


def pit_of(draws, y):
    """Randomised PIT for a discrete forecast.

    A COUNT FORECAST IS DISCRETE, so the plain `mean(draws <= y)` piles PIT
    mass at the atoms and a histogram of it looks miscalibrated even when the
    forecast is perfect. The randomised version spreads each atom's mass
    across its interval, which is the standard correction and is stated here
    rather than left for a reader to wonder about.
    """
    d = np.asarray(draws, float)
    n = len(d)
    if not n:
        return None
    lo = float((d < y).mean())
    eq = float((d == y).mean())
    rng = np.random.default_rng(20260913)
    return float(lo + eq * rng.random())


def interval_flags(draws, y):
    d = np.asarray(draws, float)
    out = {}
    for lab, lvl in (('in_50', 50), ('in_80', 80), ('in_90', 90)):
        a = (100 - lvl) / 2.0
        lo, hi = np.percentile(d, [a, 100 - a])
        out[lab] = bool(lo <= y <= hi)
    return out


def role_tiers(board, names):
    """Pregame role, from the FORECAST's own projected volume. Never postgame.

    Receivers are tiered by projected targets within their club, rushers by
    projected carries. The forecast made this ordering before kickoff; using it
    keeps the stratum independent of what happened.
    """
    tiers = {}
    for fam, metric, tags in (('receiving', 'receiving/targets',
                               ('PRIMARY_RECEIVER', 'SECONDARY_RECEIVER',
                                'DEPTH_RECEIVER')),
                              ('rushing', 'rushing/carries',
                               ('PRIMARY_RUSHER', 'SECONDARY_RUSHER',
                                'DEPTH_RUSHER'))):
        by_team = collections.defaultdict(list)
        for p in board.get('players') or []:
            m = (p.get('metrics') or {}).get(metric)
            if not isinstance(m, dict) or m.get('mean') is None:
                continue
            by_team[p.get('team')].append((float(m['mean']), p['gsis_id']))
        for team, lst in by_team.items():
            lst.sort(reverse=True)
            for i, (_, pid) in enumerate(lst):
                tiers[(pid, fam)] = tags[0] if i == 0 else (
                    tags[1] if i <= 2 else tags[2])
    return tiers


def score_seal(gid, ko, sealed_dir, rows, outcome_sha, names):
    """Diagnostic rows for one sealed forecast. Refuses, never imputes."""
    d = pathlib.Path(sealed_dir)
    board_p = d / 'board.json'
    man_p = d / 'player_draws_manifest.json'
    if not board_p.exists() or not man_p.exists():
        return [], {'game_id': gid, 'dir': str(d),
                    'status': 'NO_BOARD_OR_MANIFEST'}
    board = json.loads(board_p.read_text())
    wa = (board.get('freshness') or {}).get('written_at')
    if not wa or str(wa) >= str(ko):
        return [], {'game_id': gid, 'dir': str(d),
                    'status': 'NOT_PREGAME', 'written_at': wa,
                    'kickoff_utc': ko}
    man = json.loads(man_p.read_text())
    npz = d / 'player_draws.npz'
    if not npz.exists():
        return [], {'game_id': gid, 'dir': str(d),
                    'status': 'NO_STORED_DRAWS',
                    'detail': 'nine percentiles cannot support CRPS and none '
                              'is computed from them'}
    draws = np.load(npz)
    stage = FS.stage_of_dirname(d.parent.name)
    qb = ACT.qb_actuals(rows)
    rr = ACT.receiving_rushing_actuals(rows)
    tiers = role_tiers(board, names)
    cfg = board.get('qb3_configuration') or {}
    # CONTAMINATION IS DERIVED, NOT READ FROM A FIELD THE BOARD MAY PREDATE.
    #
    # `qb3_configuration` was added to the board on 2026-09-13 at ~21:20Z. The
    # 1 PM boards were sealed at 15:46Z, so the field is ABSENT on every one of
    # them -- and reading it gave `qb3_contaminated: 0` across 268 rows, which
    # would have presented 112 contaminated quarterback rows as clean. An
    # absent flag is not a false flag. The season-boundary condition is
    # recomputed here from the same governed function the allocation uses.
    _season = int(str(gid).split('_')[0])
    _week = int(str(gid).split('_')[1])
    _opener = {}
    try:
        from nfl.production.nonqb import qb_allocation as _QA
        _pd = _QA.previous_primary_detail(_season, _week)
        _opener = {k: bool((v or {}).get('is_season_opener'))
                   for k, v in _pd.items()}
    except Exception:
        _opener = {}
    out, refused = [], []
    for p in board.get('players') or []:
        pid = p.get('gsis_id')
        for metric, (family, field) in PG.EXACT_ESTIMANDS.items():
            if family == 'team':
                continue
            if metric not in (p.get('metrics') or {}):
                continue
            src = qb.get(pid) if family == 'qb' else rr.get(pid)
            if src is None or src.get(field) is None:
                refused.append({'game_id': gid, 'player': names.get(pid, pid),
                                'metric': metric,
                                'reason': 'NO_REALISED_VALUE_FOR_THIS_PLAYER',
                                'detail': 'the player has no row in the '
                                          'authoritative play-by-play for '
                                          'this estimand. Not imputed.'})
                continue
            lay = metric.split('/')[0]
            ids = ((man.get('layers') or {}).get(lay) or {}).get('row_ids') or []
            key = metric.replace('/', '__')
            if pid not in ids or key not in draws.files:
                refused.append({'game_id': gid, 'player': names.get(pid, pid),
                                'metric': metric,
                                'reason': 'NO_IDENTIFIED_DRAW_ROW'})
                continue
            v = np.asarray(draws[key][ids.index(pid)], float)
            y = float(src[field])
            mean = float(v.mean())
            fam_tier = 'receiving' if lay == 'receiving' else (
                'rushing' if lay == 'rushing' else None)
            tier = tiers.get((pid, fam_tier)) if fam_tier else (
                'QB' if lay == 'qb' else None)
            teamcfg = (cfg.get(p.get('team')) or {})
            row = {
                'game_id': gid, 'kickoff_utc': ko,
                'player': names.get(pid, pid), 'gsis_id': pid,
                'team': p.get('team'), 'position': p.get('position'),
                'metric': metric, 'layer': lay, 'forecast_stage': stage,
                'seal_written_at': wa, 'run_id': board.get('run_id'),
                'role_tier': tier,
                'model_mean': round(mean, 4),
                'model_median': round(float(np.median(v)), 4),
                'actual': y,
                'forecast_minus_actual': round(mean - y, 4),
                'abs_error': round(abs(mean - y), 4),
                'pct_error': (round((mean - y) / y * 100.0, 4) if y else ''),
                'pit': round(pit_of(v, y), 6),
                'crps': round(crps_sample(v, y), 6),
                'n_draws': int(v.size),
                'completeness': board.get('completeness'),
                'qb3_configuration': teamcfg.get('configuration'),
                'qb3_contaminated': bool(
                    lay == 'qb' and (
                        teamcfg.get('week1_specification_defect')
                        if teamcfg else _opener.get(p.get('team'), False))),
                'qb3_contamination_basis': (
                    'board qb3_configuration' if teamcfg
                    else 'derived from previous_primary_detail; the board '
                         'predates the qb3_configuration field'),
                'outcome_sha256': outcome_sha,
            }
            for lab, q in (('q10', 10), ('q25', 25), ('q50', 50),
                           ('q75', 75), ('q90', 90)):
                row[lab] = round(float(np.percentile(v, q)), 4)
            row.update(interval_flags(v, y))
            out.append(row)
    return out, {'game_id': gid, 'dir': str(d), 'status': 'SCORED',
                 'n_rows': len(out), 'written_at': wa, 'stage': stage,
                 'run_id': board.get('run_id'), 'n_refused': len(refused),
                 'refused': refused[:40]}


def _stats(rows, key=None):
    """Descriptive error statistics. No adequacy word is used anywhere."""
    if not rows:
        return None
    e = np.array([r['forecast_minus_actual'] for r in rows], float)
    a = np.array([r['abs_error'] for r in rows], float)
    c = np.array([r['crps'] for r in rows], float)
    pit = np.array([r['pit'] for r in rows], float)
    return {
        'n': len(rows),
        'n_model_above_actual': int((e > 0).sum()),
        'n_model_below_actual': int((e < 0).sum()),
        'mean_signed_error': round(float(e.mean()), 4),
        'median_signed_error': round(float(np.median(e)), 4),
        'mean_abs_error': round(float(a.mean()), 4),
        'mean_crps': round(float(c.mean()), 4),
        'coverage_50': round(float(np.mean([r['in_50'] for r in rows])), 4),
        'coverage_80': round(float(np.mean([r['in_80'] for r in rows])), 4),
        'coverage_90': round(float(np.mean([r['in_90'] for r in rows])), 4),
        'pit_mean': round(float(pit.mean()), 4),
        'pit_q25': round(float(np.percentile(pit, 25)), 4),
        'pit_q75': round(float(np.percentile(pit, 75)), 4),
    }


def _by(rows, keyfn):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyfn(r)].append(r)
    return {str(k): _stats(v) for k, v in sorted(g.items(), key=lambda x: str(x[0]))}


def compression_diagnostic(rows, metric):
    """Does the model spread players LESS than reality did?

    Reported as the OLS slope of actual on model and the ratio of standard
    deviations. A slope above 1 means the realised spread is wider than the
    forecast spread -- the forecast compressed. Both are descriptive; neither
    is a test, and no equivalence margin was predeclared.
    """
    s = [r for r in rows if r['metric'] == metric]
    if len(s) < 4:
        return {'metric': metric, 'n': len(s),
                'status': 'INSUFFICIENT_ROWS_FOR_A_SLOPE'}
    m = np.array([r['model_mean'] for r in s], float)
    y = np.array([r['actual'] for r in s], float)
    if m.std(ddof=1) == 0:
        return {'metric': metric, 'n': len(s), 'status': 'NO_MODEL_SPREAD'}
    slope = float(np.polyfit(m, y, 1)[0])
    return {
        'metric': metric, 'n': len(s),
        'ols_actual_on_model_slope': round(slope, 4),
        'sd_model': round(float(m.std(ddof=1)), 4),
        'sd_actual': round(float(y.std(ddof=1)), 4),
        'sd_ratio_model_over_actual': round(
            float(m.std(ddof=1) / y.std(ddof=1)), 4) if y.std(ddof=1) else None,
        'corr': round(float(np.corrcoef(m, y)[0, 1]), 4),
        'reading': ('slope > 1 and sd ratio < 1 both indicate the forecast '
                    'spread players less than the outcome did'),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='same-day diagnostic retrospective')
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--games', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seal', default='last',
                    choices=('first', 'last', 'all'),
                    help='which pregame seal per game: the earliest, the most '
                         'informed, or every one (each labelled).')
    a = ap.parse_args(argv)

    o = PG.fetch_outcomes(a.season)
    if o.state is not State.PASS:
        raise SystemExit(f'OUTCOME_FETCH_REFUSED: {o.code} {o.detail}')
    blob = o.evidence['blob']
    outcome_sha = o.evidence['sha256']
    allrows = PG._rows(blob)
    names = ACT.names(allrows)

    from nfl.capture import coverage as CV
    plan = CV.load_week_plan(a.season, 1)
    ko_of = {}
    for g in plan.value or []:
        k = g.kickoff_utc
        ko_of[g.game_id] = (k.isoformat().replace('+00:00', 'Z')
                            if hasattr(k, 'isoformat') else str(k))

    want = a.games.split(',')
    rows, seals, skipped = [], [], []
    for gid in want:
        sub = [r for r in allrows if r.get('game_id') == gid]
        if not sub:
            skipped.append({'game_id': gid,
                            'status': 'NOT_IN_AUTHORITATIVE_OUTCOME_SOURCE'})
            continue
        fin = PG.game_finality(sub)
        if not fin['final']:
            skipped.append({'game_id': gid, 'status': PG.NOT_FINAL,
                            'unmet': fin['unmet']})
            continue
        ko = ko_of.get(gid)
        if not ko:
            skipped.append({'game_id': gid, 'status': 'NO_KICKOFF_IN_PLAN'})
            continue
        cands = []
        gdir = _REPO / 'nfl' / 'research' / 'live' / gid
        for cfg in sorted(gdir.glob('*_V1_CANDIDATE_R8')):
            for b in sorted(cfg.glob('*/board.json')):
                j = json.loads(b.read_text())
                wa = (j.get('freshness') or {}).get('written_at')
                if wa and str(wa) < str(ko):
                    cands.append((str(wa), b.parent))
        if not cands:
            skipped.append({'game_id': gid, 'status': 'NO_PREGAME_SEAL'})
            continue
        cands.sort()
        pick = ([cands[0]] if a.seal == 'first'
                else [cands[-1]] if a.seal == 'last' else cands)
        for wa, sd in pick:
            r, s = score_seal(gid, ko, sd, sub, outcome_sha, names)
            rows += r
            seals.append(s)

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in COLUMNS})

    clean = [r for r in rows if not r['qb3_contaminated']]
    contam = [r for r in rows if r['qb3_contaminated']]
    summary = {
        'artifact': 'SUNDAY_1PM_OUTCOME_AUDIT',
        'spec_version': SPEC_VERSION,
        'governance': NOT_EVIDENCE,
        'why_this_is_not_the_prospective_ledger': (
            'postgame.run refuses every one of these sealed forecasts with '
            'POSTGAME_ARTIFACT_NOT_CURRENTLY_ADMISSIBLE -- three mandatory '
            'controls say they may not COUNT toward the decision floors. That '
            'gate is correct and untouched. This audit measures how wrong the '
            'forecasts were, which is a different question from whether they '
            'are admissible as evidence.'),
        'outcome_source': {'blob': str(blob), 'sha256': outcome_sha,
                           'n_pbp_rows': len(allrows),
                           'finality': 'proven per game from the bytes'},
        'seal_selection': a.seal,
        'seals_used': seals, 'games_skipped': skipped,
        'n_rows': len(rows),
        'n_rows_qb3_contaminated': len(contam),
        'strata_note': ('QB rows from season-opener rooms are carried in a '
                        'SEPARATE contaminated stratum and never pooled into '
                        'conclusions about non-QB layers.'),
        'overall_excluding_qb3_contaminated': _stats(clean),
        'overall_qb3_contaminated_stratum': _stats(contam),
        'by_metric': _by(clean, lambda r: r['metric']),
        'by_position': _by(clean, lambda r: r['position']),
        'by_game': _by(clean, lambda r: r['game_id']),
        'by_role_tier': _by(clean, lambda r: r['role_tier']),
        'by_layer': _by(clean, lambda r: r['layer']),
        'by_completeness': _by(clean, lambda r: r['completeness']),
        'compression': {m: compression_diagnostic(clean, m)
                        for m in ('receiving/targets', 'receiving/receptions',
                                  'receiving/receiving_yards',
                                  'rushing/carries')},
        'estimands_refused_by_name': PG.REFUSED_ESTIMANDS,
        'what_cannot_be_concluded': [
            'one slate is not a sample. Every figure here is descriptive and '
            'none is a test.',
            'games are not independent observations; nothing here is clustered '
            'and no interval is quoted.',
            'no threshold may be chosen because it would have worked today.',
            'a forecast that was wrong today is not thereby a defect, and one '
            'that was right is not thereby correct.'],
    }
    sp = out.with_suffix('.summary.json')
    sp.write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(f'{len(rows)} diagnostic row(s) -> {out}')
    print(f'summary -> {sp}')
    print(f'seals used: {len(seals)}, games skipped: {len(skipped)}')
    ov = summary['overall_excluding_qb3_contaminated']
    if ov:
        print(f"overall (ex-contaminated): n={ov['n']} "
              f"mean signed={ov['mean_signed_error']:+.3f} "
              f"below={ov['n_model_below_actual']} above={ov['n_model_above_actual']} "
              f"cov50={ov['coverage_50']:.3f} cov80={ov['coverage_80']:.3f} "
              f"cov90={ov['coverage_90']:.3f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
