#!/usr/bin/env python3.12
"""Forward-chained calibration: the model against seven baselines, sliced, with distributions.

THE CHAIN. For each scored week, every input comes from strictly earlier football. The model's prior
sees seasons up to the previous one; its current-season evidence stops the week before; the baselines
read the same boundary. Nothing that happened in the scored week, or after it, enters any prediction.

THE DISTRIBUTION IS FITTED AND TESTED ON DIFFERENT SEASONS. V1 emits a point projection, so a
predictive distribution is built from out-of-sample residuals: per position and per projected-level
bucket, the realised spread of (actual - predicted). Those residual pools are fitted on the FIT
seasons and the coverage, PIT, CRPS and ceiling calibration are measured on the HELD-OUT seasons. A
distribution fitted and scored on the same games would report whatever coverage it was given.

WHAT IS SLICED, and where a slice cannot be built it says so instead of quietly disappearing:
position, role type, transition type, experience, favourite/underdog, home/road, weather bucket,
game total, projected opportunity, and cold-start status. SALARY TIER IS NOT AVAILABLE historically
-- this checkout holds no past DraftKings salaries -- so that slice is reported unavailable rather
than approximated by a proxy for money.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.eval import baselines as B, metrics as M  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'calibration-1'
OUT = _REPO / 'nfl/eval/CALIBRATION.json'
PLAYER_GAME = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
TEAM_GAME = _REPO / 'nfl/warehouse/TEAM_GAME.json'
ROLE_HISTORY = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'

#: Residual pools are fitted here and scored on HELDOUT. Declared in advance.
FIT_SEASONS = (2021, 2022, 2023)
HELDOUT_SEASONS = (2024, 2025)

#: Projected-level buckets for the residual pools, in DK points.
LEVEL_EDGES = (0, 2, 5, 9, 14, 20, 28, 999)

#: Nominal interval levels checked.
LEVELS = (0.50, 0.80, 0.90)

#: Event thresholds for Brier and log loss, in DK points.
EVENT_THRESHOLDS = (10.0, 20.0, 30.0)

UNAVAILABLE_SLICES = {
    'salary_tier': ('no historical DraftKings salaries are held in this checkout, so a salary-tier '
                    'slice cannot be built. Not approximated: a proxy for money is not money.'),
    'injury_return_from_report': ('historical injury reports are not held. The role-history '
                                  'RETURNING_STARTER transition is used instead and is labelled as '
                                  'a usage-derived proxy, not a medical one.'),
}


def _level_bucket(v):
    for i in range(len(LEVEL_EDGES) - 1):
        if LEVEL_EDGES[i] <= v < LEVEL_EDGES[i + 1]:
            return f'{LEVEL_EDGES[i]}-{LEVEL_EDGES[i + 1]}'
    return f'{LEVEL_EDGES[-2]}+'


def collect(seasons):
    """Forward-chained records: model prediction, baselines, actual, and slice attributes.

    Scored on the UNCONDITIONAL DFS payoff: every candidate in the club's plausible roster is
    scored, and one who did not appear scores exactly zero. For usage an absent row is UNKNOWN; for
    DraftKings points it is nothing, and that is a fact about the payoff rather than an inference
    about his usage.
    """
    from nfl.tools import forward_chain as F
    from nfl.tools import player_prior as P
    from nfl.tools import proj_v1 as V
    from nfl.tools import td_rates as R
    po = P.load_panel()
    if po.state.name != 'PASS':
        return po
    panel = po.value
    roster_pos = P.position_index()
    pg = json.loads(PLAYER_GAME.read_text())['rows']
    tg = json.loads(TEAM_GAME.read_text())['rows']
    rh = (json.loads(ROLE_HISTORY.read_text())['rows'] if ROLE_HISTORY.exists() else {})
    pg_rows = list(pg.values())
    hist = B.build_history(pg_rows)
    club_imp = B.club_implied_index(list(tg.values()))

    actual_idx = {(r['season'], int(r['week']), r['player_id']): r for r in pg_rows}
    team_idx = {(r['season'], int(r['week']), r['club']): r for r in tg.values()}
    role_idx = {(r['season'], int(r['week']), r['player_id']): r for r in rh.values()}
    seasons_seen = collections.defaultdict(set)
    for r in pg_rows:
        seasons_seen[r['player_id']].add(r['season'])

    pos_map, inferred = F.positions_for_chain(panel, roster_pos)
    records = []
    for season in seasons:
        through = season - 1
        season_pos = F._SeasonPos(pos_map, season, roster_pos)
        excluded = {g for (g, s) in inferred if s == season}
        depth = V.depth_shares(panel, season_pos, through=through)
        groups = V.group_shares(panel, season_pos, through=through)
        bonus = V.bonus_rates(panel, season_pos, through=through)
        ip = V.int_rate(panel, season_pos, through=through)['int_per_attempt']
        F.PRATES[0] = R.positional_rates(panel, season_pos)
        gl = [g for g in panel['players'] if season_pos.get(g) in F.SKILL]
        priors = F.season_priors(panel, season_pos, season, gl)
        pool_mean = B.positional_pool(pg_rows, season_pos, through)
        pool_share = B.positional_share_of_club_points(pg_rows, season_pos, through, club_imp)
        weeks = sorted({int(w) for g, ss in panel['players'].items()
                        for s2, ws in ss.items() if int(s2) == season for w in ws})
        for week in [w for w in weeks if w > F.MIN_PRIOR_WEEKS]:
            proj = F.project_week(panel, season_pos, season, week, priors, depth, groups,
                                  bonus, ip, 1.0, prior_cap=V.PRIOR_WEIGHT_CAP)
            pool_club = F.POOL_CLUB[0]
            for gsis in F.POOL[0]:
                if gsis in excluded:
                    continue
                pred = proj.get(gsis)
                if pred is None:
                    continue
                pos = season_pos.get(gsis)
                club = pool_club.get(gsis)
                ar = actual_idx.get((season, week, gsis))
                actual = (ar.get('dk_points_current_rules') if ar else 0.0)
                tgr = team_idx.get((season, week, club)) or {}
                rhr = role_idx.get((season, week, gsis)) or {}
                ci = club_imp.get((season, week, club))
                base = {}
                for nm in B.NAMES:
                    base[nm] = B.predict(nm, player_id=gsis, position=pos, season=season,
                                         week=week, hist=hist, pos_pool=pool_mean,
                                         club_implied=ci,
                                         pos_share_of_club_points=pool_share)
                prior_seasons = [s for s in seasons_seen.get(gsis, ()) if s < season]
                temp, wind = tgr.get('temp'), tgr.get('wind')
                records.append({
                    'season': season, 'week': week, 'player_id': gsis, 'position': pos,
                    'club': club, 'game_id': tgr.get('game_id'),
                    'pred': pred, 'actual': actual, 'appeared': ar is not None,
                    'baselines': base,
                    'club_spread': tgr.get('club_spread'),
                    'total_line': tgr.get('total_line'),
                    'club_implied': ci,
                    'is_home': tgr.get('is_home'),
                    'temp': temp if not isinstance(temp, str) else None,
                    'wind': wind if not isinstance(wind, str) else None,
                    'roof': tgr.get('roof'),
                    'role_depth': rhr.get('depth'),
                    'role_transition': rhr.get('transition'),
                    'role_archetypes': rhr.get('archetypes') or [],
                    'experience_prior_seasons': len(prior_seasons),
                })
    return records


# ------------------------------------------------------------------- predictive distribution
def fit_residual_pools(records, fit_seasons):
    """Residual pools by position and projected-level bucket, from the FIT seasons only."""
    pools = collections.defaultdict(list)
    for r in records:
        if r['season'] not in fit_seasons or r['actual'] is None:
            continue
        pools[(r['position'], _level_bucket(r['pred']))].append(r['actual'] - r['pred'])
    out, thin = {}, []
    for k, v in pools.items():
        if len(v) < 40:
            thin.append({'position': k[0], 'bucket': k[1], 'n': len(v)})
            continue
        out[f'{k[0]}|{k[1]}'] = sorted(v)
    # a position-wide fallback, so a thin bucket borrows from its own position rather than
    # silently receiving no distribution at all
    bypos = collections.defaultdict(list)
    for r in records:
        if r['season'] in fit_seasons and r['actual'] is not None:
            bypos[r['position']].append(r['actual'] - r['pred'])
    fallback = {p: sorted(v) for p, v in bypos.items() if len(v) >= 100}
    return {'pools': out, 'position_fallback': fallback, 'thin_buckets': thin,
            'FIT_SEASONS': list(fit_seasons),
            'METHOD': ('empirical residuals, not a parametric family. DK points are bounded below '
                       'at roughly zero, heavily right-skewed and have an atom at zero for players '
                       'who did not appear; no normal or gamma fits that, and an empirical pool '
                       'reproduces all three features for free.')}


def sample_for(rec, fitted, n=None):
    """The predictive sample for one record: its projection plus the matching residual pool."""
    key = f"{rec['position']}|{_level_bucket(rec['pred'])}"
    pool = fitted['pools'].get(key) or fitted['position_fallback'].get(rec['position'])
    if not pool:
        return None
    return sorted(rec['pred'] + d for d in pool)


# -------------------------------------------------------------------------------- the slices
def slices_for(r):
    """Every slice this record belongs to. A record can be in many."""
    out = [('all', 'all'), ('position', r['position'] or 'UNKNOWN')]
    cs = r.get('club_spread')
    if cs is not None:
        out.append(('favourite_or_underdog',
                    'FAVOURITE' if cs > 0 else 'UNDERDOG' if cs < 0 else 'PICKEM'))
        out.append(('spread_bucket',
                    'BIG_FAVOURITE' if cs >= 7 else 'FAVOURITE' if cs > 0
                    else 'UNDERDOG' if cs > -7 else 'BIG_UNDERDOG'))
    if r.get('is_home') is not None:
        out.append(('home_or_road', 'HOME' if r['is_home'] else 'ROAD'))
    tl = r.get('total_line')
    if tl is not None:
        out.append(('game_total', 'HIGH_48_PLUS' if tl >= 48 else
                    'MID_43_48' if tl >= 43 else 'LOW_UNDER_43'))
    roof = (r.get('roof') or '').lower()
    if roof in ('dome', 'closed'):
        out.append(('weather', 'INDOORS'))
    else:
        w, t = r.get('wind'), r.get('temp')
        if w is not None and w >= 15:
            out.append(('weather', 'WINDY_15_PLUS'))
        elif t is not None and t <= 35:
            out.append(('weather', 'COLD_35_OR_BELOW'))
        elif t is not None:
            out.append(('weather', 'OUTDOORS_MILD'))
        else:
            out.append(('weather', 'OUTDOORS_UNMEASURED'))
    if r.get('role_depth'):
        out.append(('role_depth', r['role_depth']))
    tr = r.get('role_transition')
    if tr:
        out.append(('role_transition', tr))
        if tr in ('INJURY_REPLACEMENT', 'PROMOTED_RESERVE'):
            out.append(('promoted_backup', 'YES'))
        if tr == 'RETURNING_STARTER':
            out.append(('usage_derived_return', 'YES'))
    for a in (r.get('role_archetypes') or ()):
        out.append(('archetype', a))
    e = r.get('experience_prior_seasons')
    if e is not None:
        out.append(('experience', 'ROOKIE_OR_FIRST_SEASON_IN_TABLE' if e == 0
                    else 'SECOND_SEASON' if e == 1 else 'VETERAN_3_PLUS' if e >= 2 else 'OTHER'))
    out.append(('projected_opportunity',
                'HIGH_14_PLUS' if r['pred'] >= 14 else 'MID_5_14' if r['pred'] >= 5
                else 'LOW_UNDER_5'))
    out.append(('appeared', 'APPEARED' if r.get('appeared') else 'DID_NOT_APPEAR'))
    return out


def evaluate(records, fitted, heldout_seasons):
    """The battery on the held-out seasons: the model, the baselines, and every slice."""
    held = [r for r in records if r['season'] in heldout_seasons]
    if len(held) < 200:
        return {'state': 'TOO_FEW_HELDOUT', 'n': len(held)}

    def arm_values(rows, arm):
        if arm == 'MODEL_V1':
            return [r['pred'] for r in rows]
        return [(r['baselines'] or {}).get(arm) for r in rows]

    arms = ['MODEL_V1'] + list(B.NAMES)
    overall = {}
    for arm in arms:
        pv = arm_values(held, arm)
        got = [(p, r['actual']) for p, r in zip(pv, held) if p is not None]
        if len(got) < 100:
            overall[arm] = {'state': 'UNAVAILABLE',
                            'reason': B.UNAVAILABLE.get(arm, f'only {len(got)} usable predictions'),
                            'n': len(got)}
            continue
        overall[arm] = M.point_metrics([g[0] for g in got], [g[1] for g in got])
        overall[arm]['n_with_prediction'] = len(got)

    # paired differences against each baseline, blocked by week
    by_week = collections.defaultdict(list)
    for r in held:
        by_week[(r['season'], r['week'])].append(r)
    paired = {}
    for arm in B.NAMES:
        diffs = collections.defaultdict(list)
        for wk, rows in by_week.items():
            sub = [r for r in rows if (r['baselines'] or {}).get(arm) is not None]
            if len(sub) < 40:
                continue
            m_model = M.point_metrics([r['pred'] for r in sub], [r['actual'] for r in sub])
            m_base = M.point_metrics([r['baselines'][arm] for r in sub],
                                     [r['actual'] for r in sub])
            if m_model.get('state') != 'OK' or m_base.get('state') != 'OK':
                continue
            for k in ('mae', 'rmse', 'spearman_rho', 'pearson_r'):
                if m_model.get(k) is not None and m_base.get(k) is not None:
                    diffs[k].append(m_model[k] - m_base[k])
        out = {}
        for k, d in diffs.items():
            if len(d) < 3:
                continue
            mu = statistics.fmean(d)
            se = statistics.pstdev(d) / math.sqrt(len(d)) if len(d) > 1 else None
            out[k] = {'mean_difference': round(mu, 5),
                      'week_blocked_se': round(se, 5) if se else None,
                      'n_weeks': len(d),
                      'model_better': (mu < 0 if k in ('mae', 'rmse') else mu > 0),
                      'beyond_2se': (abs(mu) > 2 * se) if se else None}
        paired[arm] = out or {'state': 'NOT_COMPARABLE'}

    # distribution calibration on the held-out seasons
    with_samples = [(r, sample_for(r, fitted)) for r in held]
    with_samples = [(r, s) for r, s in with_samples if s]
    dist = {'n_with_distribution': len(with_samples),
            'n_without_distribution': len(held) - len(with_samples)}
    if with_samples:
        acts = [r['actual'] for r, _s in with_samples]
        samps = [s for _r, s in with_samples]
        dist['pit'] = M.pit(lambda i: samps[i], acts)
        dist['coverage'] = {}
        for lvl in LEVELS:
            a, b = (1 - lvl) / 2, 1 - (1 - lvl) / 2
            lo = [s[min(len(s) - 1, int(a * len(s)))] for s in samps]
            hi = [s[min(len(s) - 1, int(b * len(s)))] for s in samps]
            dist['coverage'][f'{int(lvl * 100)}%'] = M.interval_coverage(lo, hi, acts, lvl)
        dist['crps_mean'] = round(statistics.fmean(
            M.crps_empirical(s, a) for s, a in zip(samps, acts)), 5)
        dist['ceiling'] = {}
        for q in (0.85, 0.90, 0.95):
            hi = [s[min(len(s) - 1, int(q * len(s)))] for s in samps]
            dist['ceiling'][f'p{int(q * 100)}'] = M.ceiling_calibration(hi, acts, q)
        dist['events'] = {}
        for thr in EVENT_THRESHOLDS:
            probs = [sum(1 for x in s if x >= thr) / len(s) for s in samps]
            outs = [1 if a >= thr else 0 for a in acts]
            dist['events'][f'{thr:.0f}+'] = {'brier': M.brier(probs, outs),
                                             'log_loss': M.log_loss(probs, outs)}

    # slices
    sl = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in held:
        for dim, val in slices_for(r):
            sl[dim][val].append(r)
    slice_out = {}
    for dim, vals in sorted(sl.items()):
        slice_out[dim] = {}
        for val, rows in sorted(vals.items()):
            if len(rows) < 40:
                slice_out[dim][val] = {'state': 'TOO_FEW', 'n': len(rows)}
                continue
            mm = M.point_metrics([r['pred'] for r in rows], [r['actual'] for r in rows])
            entry = {k: mm.get(k) for k in ('n', 'mae', 'rmse', 'bias', 'bias_pct_of_actual',
                                            'pearson_r', 'spearman_rho', 'calibration_slope',
                                            'mean_pred', 'mean_actual')}
            # the best baseline on this slice, so a slice where the model loses is visible
            best = None
            for arm in B.NAMES:
                sub = [r for r in rows if (r['baselines'] or {}).get(arm) is not None]
                if len(sub) < 40:
                    continue
                bm = M.point_metrics([r['baselines'][arm] for r in sub],
                                     [r['actual'] for r in sub])
                if bm.get('state') != 'OK':
                    continue
                if best is None or bm['mae'] < best[1]:
                    best = (arm, bm['mae'], bm.get('spearman_rho'))
            if best:
                entry['best_baseline'] = best[0]
                entry['best_baseline_mae'] = round(best[1], 5)
                entry['best_baseline_rho'] = best[2]
                entry['model_beats_best_baseline_mae'] = (entry['mae'] < best[1]
                                                          if entry['mae'] else None)
            slice_out[dim][val] = entry
    return {'state': 'OK', 'n_heldout': len(held), 'overall': overall,
            'paired_vs_baselines_blocked_by_week': paired,
            'distribution': dist, 'slices': slice_out,
            'unavailable_slices': UNAVAILABLE_SLICES}


def build(seasons=(2021, 2022, 2023, 2024, 2025)):
    for f in (PLAYER_GAME, TEAM_GAME):
        if not f.exists():
            return Outcome.blocked('WAREHOUSE_INCOMPLETE', f'{f.name} missing',
                                   cause=Cause.DEPENDENCY)
    recs = collect(seasons)
    if not isinstance(recs, list):
        return recs
    if len(recs) < 1000:
        return Outcome.blocked('TOO_FEW_RECORDS', f'{len(recs)} forward-chained records',
                               cause=Cause.DATA)
    fitted = fit_residual_pools(recs, FIT_SEASONS)
    ev = evaluate(recs, fitted, HELDOUT_SEASONS)
    art = {
        'artifact': 'CALIBRATION', 'spec_version': SPEC_VERSION,
        'seasons_collected': list(seasons),
        'FIT_SEASONS': list(FIT_SEASONS), 'HELDOUT_SEASONS': list(HELDOUT_SEASONS),
        'n_records': len(recs),
        'CHAIN': ('every input comes from strictly earlier football: the prior sees seasons up to '
                  'the previous one, current-season evidence stops the week before, and the '
                  'baselines read the same boundary.'),
        'SCORING': ('unconditional DFS payoff -- every candidate in the club plausible roster is '
                    'scored and one who did not appear scores exactly zero. For usage an absent row '
                    'is UNKNOWN; for DK points it is nothing.'),
        'DISTRIBUTION_DISCIPLINE': ('residual pools are fitted on FIT_SEASONS and every coverage, '
                                    'PIT, CRPS and ceiling figure is measured on HELDOUT_SEASONS. A '
                                    'distribution fitted and scored on the same games reports '
                                    'whatever coverage it was given.'),
        'residual_pools': {'n_pools': len(fitted['pools']),
                           'n_position_fallbacks': len(fitted['position_fallback']),
                           'thin_buckets': fitted['thin_buckets'],
                           'METHOD': fitted['METHOD']},
        'evaluation': ev,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True, default=str))
    return Outcome.ok('CALIBRATION_BUILT', art, f'{len(recs)} records, '
                      f'{ev.get("n_heldout")} held out')


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    if o.state.name != 'PASS':
        return 1
    a = o.value
    ev = a['evaluation']
    print(f"  records {a['n_records']}, fit {a['FIT_SEASONS']}, held out {a['HELDOUT_SEASONS']} "
          f"(n={ev.get('n_heldout')})")
    print(f"\n  {'arm':20s} {'n':>6s} {'MAE':>7s} {'RMSE':>7s} {'bias':>7s} {'r':>7s} "
          f"{'rho':>7s} {'slope':>6s}")
    for arm, m in ev['overall'].items():
        if m.get('state') != 'OK':
            print(f"  {arm:20s} {m.get('state')}: {str(m.get('reason'))[:60]}")
            continue
        print(f"  {arm:20s} {m['n']:6d} {m['mae']:7.4f} {m['rmse']:7.4f} {m['bias']:+7.4f} "
              f"{(m['pearson_r'] or 0):7.4f} {(m['spearman_rho'] or 0):7.4f} "
              f"{(m['calibration_slope'] or 0):6.3f}")
    print('\n  model minus baseline, blocked by week (negative MAE and positive rho favour us):')
    for arm, d in ev['paired_vs_baselines_blocked_by_week'].items():
        if d.get('state'):
            print(f"    {arm:18s} {d['state']}")
            continue
        bits = []
        for k in ('mae', 'spearman_rho'):
            if k in d:
                x = d[k]
                flag = '**' if x['beyond_2se'] else '  '
                bits.append(f"{k} {x['mean_difference']:+.4f}+/-{x['week_blocked_se']:.4f}{flag}")
        print(f"    {arm:18s} " + '  '.join(bits))
    dist = ev['distribution']
    print(f"\n  distribution: {dist['n_with_distribution']} with, "
          f"{dist['n_without_distribution']} without")
    if 'coverage' in dist:
        for lvl, c in dist['coverage'].items():
            print(f"    {lvl:>4s} interval  nominal {c['nominal']:.2f}  empirical "
                  f"{c['empirical']:.4f}  gap {c['gap_in_se']} SE")
        p = dist['pit']
        print(f"    PIT mean {p.get('mean_pit')}  KS {p.get('ks_distance_from_uniform')} vs "
              f"critical {p.get('ks_critical_95')}  uniform rejected "
              f"{p.get('uniform_rejected_at_95')}")
        print(f"    CRPS {dist['crps_mean']}")
        for q, c in dist['ceiling'].items():
            print(f"    ceiling {q}  nominal exceedance {c['nominal_exceedance']:.2f}  "
                  f"empirical {c['empirical_exceedance']:.4f}")
        for thr, e in dist['events'].items():
            print(f"    event {thr:>4s}  brier {e['brier']['brier']:.5f} "
                  f"(skill {e['brier']['brier_skill_vs_base_rate']})  "
                  f"log loss {e['log_loss']['log_loss']:.5f} "
                  f"(skill {e['log_loss']['skill_vs_base_rate']})")
    print('\n  worst slices by MAE where a baseline beats the model:')
    losses = []
    for dim, vals in ev['slices'].items():
        for val, m in vals.items():
            if m.get('state') == 'TOO_FEW' or m.get('model_beats_best_baseline_mae') is not False:
                continue
            losses.append((m['mae'] - m['best_baseline_mae'], dim, val, m))
    for gap, dim, val, m in sorted(losses, reverse=True)[:8]:
        print(f"    {dim}={val:<32s} n={m['n']:5d} ours {m['mae']:6.3f} vs "
              f"{m['best_baseline']} {m['best_baseline_mae']:6.3f}  (+{gap:.3f})")
    print(f"\n  -> {OUT.relative_to(_REPO)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
