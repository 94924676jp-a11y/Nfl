#!/usr/bin/env python3.12
"""Does the role-state cap earn its place? Four arms, forward-chained, weekly priors.

THE CLAIM UNDER TEST. Production caps a player's role band by his depth rank, so an
injury-replacement share expires when the starter returns. It was asserted from one worked example
(Drew Lock at 17.88 DK points on snaps he held only because Sam Darnold was hurt) and never measured,
because `forward_chain.historical_band` says a historical role state is not reconstructible. It is,
from prior weeks only, and `role_state_history.assert_no_leakage` proves the reconstruction does not
read the scored week by rebuilding it from a panel with that week deleted.

THE ARMS, declared before any of them ran:

    SEASON_CONSTANT        what the chain does today: one band per player per season, from the
                           previous season, no cap. A player promoted in week 4 keeps last year's
                           band through week 18.
    WEEKLY_NO_CAP          the band updates weekly from prior weeks of this season, still uncapped.
                           Isolates "update it weekly" from "cap it".
    WEEKLY_CAPPED_PREGAME  weekly band, capped by pregame depth rank. This is production's
                           mechanism minus the injury report, which this repository does not hold
                           for past Sundays.
    WEEKLY_CAPPED_ORACLE   the same, with who actually appeared supplied so the cap falls on the
                           right player. AN ORACLE. It measures the mechanism given correct
                           availability and is NOT live performance.

The gap between the last two is the value of knowing who is out, which is what an injury report buys.
Separating them is what stops "the cap is the wrong idea" being confused with "the cap is right and
we cannot see who is injured".

COST. Priors depend on the band, so a weekly band needs weekly priors: this rebuilds them for every
week of every season rather than once per season, which is why it takes tens of minutes.
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.shrinkage.study import (  # noqa: E402
    MIN_WEEK_N, block_mean_se, paired_block, spearman, top_decile_to_median)
from sportsplatform.governance.outcome import Outcome  # noqa: E402

OUT = _REPO / 'nfl/research/rolestate/ROLE_STATE_STUDY.json'
SPEC_VERSION = 'rolestate-1'

SELECTION_SEASONS = (2023, 2024, 2025)
CONFIRMATION_SEASONS = (2022,)
#: 2021 is void here for the same reason as in the shrinkage study: the panel begins in 2021, so a
#: 2021 forecast has no prior season, every prior is PRIOR_UNAVAILABLE and no arm can differ.
VOID_SEASONS = {2021: 'panel begins in 2021; no prior season exists so no arm can differ'}
ALL = (2022, 2023, 2024, 2025)

#: The thing V1 replaced, and the arm FORWARD_CHAIN_VERDICT.md says V1 loses to on ranking. It is
#: included here because that verdict was measured with the SEASON_CONSTANT band, and the band fix
#: is worth more rho than the gap the verdict rested on. Whether the verdict survives is a question
#: this study can answer and must not assume either way.
CURRENT_SEASON_ONLY = 'CURRENT_SEASON_ONLY'
SEASON_CONSTANT = 'SEASON_CONSTANT'
WEEKLY_NO_CAP = 'WEEKLY_NO_CAP'
WEEKLY_CAPPED_PREGAME = 'WEEKLY_CAPPED_PREGAME'
WEEKLY_CAPPED_ORACLE = 'WEEKLY_CAPPED_ORACLE'
ARMS = (CURRENT_SEASON_ONLY, SEASON_CONSTANT, WEEKLY_NO_CAP, WEEKLY_CAPPED_PREGAME,
        WEEKLY_CAPPED_ORACLE)


def _bands_for_week(panel, sp, season, week, arm, appeared, RH, F):
    """The band every player is asked about in this week, under one arm."""
    if arm in (SEASON_CONSTANT, CURRENT_SEASON_ONLY):
        return None  # signals "use forward_chain's own season-constant band"
    use_arm = RH.ARM_ORACLE if arm == WEEKLY_CAPPED_ORACLE else RH.ARM_PREGAME
    o = RH.role_state_for_week(panel, sp, season, week, F.historical_band, arm=use_arm,
                               appeared=(appeared if use_arm == RH.ARM_ORACLE else None))
    if o.state.name != 'PASS':
        return o
    key = 'band_before_cap' if arm == WEEKLY_NO_CAP else 'role_band'
    return {g: r[key] for g, r in o.value['rows'].items()}


def run(seasons=ALL) -> Outcome:
    from nfl.tools import forward_chain as F
    from nfl.tools import player_prior as P
    from nfl.tools import proj_v1 as V
    from nfl.tools import role_state_history as RH
    from nfl.tools import td_rates as R

    po = P.load_panel()
    if po.state.name != 'PASS':
        return po
    panel = po.value
    roster_pos = P.position_index()
    pg = json.loads((_REPO / 'nfl/warehouse/PLAYER_GAME.json').read_text())['rows']
    actual = {(r['season'], int(r['week']), r['player_id']): r for r in pg.values()}
    appeared_by_week = collections.defaultdict(set)
    for (s, w, g) in actual:
        appeared_by_week[(s, w)].add(g)
    pos_map, inferred = F.positions_for_chain(panel, roster_pos)

    per_arm_weeks = {a: [] for a in ARMS}
    cap_counts = collections.Counter()
    t0 = time.time()
    for season in seasons:
        sp = F._SeasonPos(pos_map, season, roster_pos)
        excluded = {g for (g, s) in inferred if s == season}
        depth = V.depth_shares(panel, sp, through=season - 1)
        groups = V.group_shares(panel, sp, through=season - 1)
        bonus = V.bonus_rates(panel, sp, through=season - 1)
        ip = V.int_rate(panel, sp, through=season - 1)['int_per_attempt']
        prates = R.positional_rates(panel, sp)
        gl = [g for g in panel['players'] if sp.get(g) in F.SKILL]
        season_priors = F.season_priors(panel, sp, season, gl)
        weeks = [w for w in sorted({int(w) for g, ss in panel['players'].items()
                                    for s2, ws in ss.items() if int(s2) == season for w in ws})
                 if w > F.MIN_PRIOR_WEEKS]
        for week in weeks:
            appeared = appeared_by_week.get((season, week), set())
            for arm in ARMS:
                F.PRATES[0] = prates
                bands = _bands_for_week(panel, sp, season, week, arm, appeared, RH, F)
                if isinstance(bands, Outcome):
                    return bands
                if bands is None:
                    priors = season_priors
                else:
                    # the band decides which slice of history the prior may see, so a weekly band
                    # needs a weekly prior. Recomputed rather than reused, which is the cost.
                    priors = {}
                    for g, (sb, _pr) in season_priors.items():
                        b = bands.get(g, sb)
                        if b == sb:
                            priors[g] = (sb, _pr)
                        else:
                            priors[g] = (b, P.hierarchical(panel, g, sp.get(g), b, season,
                                                           season - 1))
                            cap_counts[f'{arm}:band_changed'] += 1
                proj = F.project_week(
                    panel, sp, season, week, priors, depth, groups, bonus, ip,
                    (F.BASELINE_ARM if arm == CURRENT_SEASON_ONLY else 1.0),
                    prior_cap=V.PRIOR_WEIGHT_CAP)
                pool_club = F.POOL_CLUB[0]
                recs = []
                for g in F.POOL[0]:
                    if g in excluded:
                        continue
                    pred = proj.get(g)
                    if pred is None:
                        continue
                    ar = actual.get((season, week, g))
                    recs.append({'player_id': g, 'position': sp.get(g),
                                 'club': pool_club.get(g), 'pred': pred,
                                 'actual': (ar.get('dk_points_current_rules') if ar else 0.0) or 0.0,
                                 'role_band': (priors.get(g) or (None, None))[0]})
                if len(recs) >= MIN_WEEK_N:
                    per_arm_weeks[arm].append({'season': season, 'week': week, 'records': recs})
        print(f'  {season} done, {time.time() - t0:.0f}s elapsed', flush=True)

    def score(weeks):
        rho, mae, sepp, lvl = [], [], [], []
        for w in weeks:
            p = [r['pred'] for r in w['records']]
            a = [r['actual'] for r in w['records']]
            rho.append(spearman(p, a))
            mae.append(statistics.fmean(abs(x - y) for x, y in zip(p, a)))
            mp = statistics.fmean(p)
            lvl.append((statistics.fmean(a) / mp) if mp > 0 else None)
            sepp.append(top_decile_to_median(p))
        out = {}
        for nm, s in (('rho', rho), ('mae', mae), ('level', lvl), ('sep_pred', sepp)):
            m, se, n = block_mean_se(s)
            out[nm] = {'mean': round(m, 4) if m is not None else None,
                       'week_blocked_se': round(se, 4) if se is not None else None, 'n_weeks': n}
        out['_rho'] = rho
        out['_mae'] = mae
        return out

    results, store = {}, {}
    for arm in ARMS:
        sel = [w for w in per_arm_weeks[arm] if w['season'] in SELECTION_SEASONS]
        con = [w for w in per_arm_weeks[arm] if w['season'] in CONFIRMATION_SEASONS]
        ss, cc = score(sel), score(con)
        store[arm] = {'selection': ss, 'confirmation': cc}
        results[arm] = {'selection': {k: v for k, v in ss.items() if not k.startswith('_')},
                        'confirmation': {k: v for k, v in cc.items() if not k.startswith('_')},
                        'n_weeks_selection': len(sel), 'n_weeks_confirmation': len(con)}

    def paired_against(reference, label):
        out = {}
        for arm in ARMS:
            if arm == reference:
                continue
            row = {}
            for split in ('selection', 'confirmation'):
                for metric in ('rho', 'mae'):
                    m, se, n = paired_block(store[arm][split][f'_{metric}'],
                                            store[reference][split][f'_{metric}'])
                    row[f'{split}.{metric}'] = {
                        label: round(m, 4) if m is not None else None,
                        'week_blocked_se': round(se, 4) if se is not None else None,
                        'z': round(m / se, 2) if m is not None and se else None,
                        'n_paired_weeks': n}
            out[arm] = row
        return out

    paired = paired_against(SEASON_CONSTANT, 'mean_diff_vs_season_constant')
    paired_vs_base = paired_against(CURRENT_SEASON_ONLY, 'mean_diff_vs_current_season_only')

    art = {
        'ARTIFACT': 'ROLE_STATE_STUDY', 'SPEC_VERSION': SPEC_VERSION,
        'QUESTION': ('does capping a player\'s role band by his pregame depth rank improve '
                     'forward-chained ranking, and how much of the answer depends on knowing who '
                     'is out'),
        'PREREGISTERED': {
            'arms': list(ARMS), 'selection_seasons': list(SELECTION_SEASONS),
            'confirmation_seasons': list(CONFIRMATION_SEASONS),
            'void_seasons': {str(k): v for k, v in VOID_SEASONS.items()},
            'primary_outcome': 'within-slate-week Spearman rho, week-blocked SE',
            'reference_arm': SEASON_CONSTANT},
        'ORACLE_ARM_IS_NOT_LIVE_PERFORMANCE': (
            f'{WEEKLY_CAPPED_ORACLE} is fed the set of players who actually appeared in the scored '
            'week so the cap falls on the right player. That is an oracle condition, the same kind '
            'as feeding a simulator the actual batting order, and it must never be quoted as live '
            'performance. The gap between it and '
            f'{WEEKLY_CAPPED_PREGAME} is what an injury report would be worth, and no injury '
            'report exists in this checkout for a past Sunday (OUT-038).'),
        'LEAKAGE_PROOF': ('role_state_history.assert_no_leakage rebuilds the state from a panel '
                          'with the scored week and every later week removed and requires every '
                          'band and rank to be identical. It is run per season in the test suite.'),
        'PROJECTION_SYSTEM_STATE': 'NOT_VALIDATED',
        'THE_COMPARISON_THAT_MATTERS': (
            'FORWARD_CHAIN_VERDICT.md concluded that the multi-season prior loses to '
            'CURRENT_SEASON_ONLY on ranking, by -0.0181 rho from week 5. That was measured with '
            'the SEASON_CONSTANT band -- one band per player per season, from the previous season '
            '-- which is NOT the band production uses: the live path rebuilds role state weekly. '
            'The band fix alone is worth more rho than the gap the verdict rested on, so '
            'paired_vs_current_season_only below is the comparison that decides whether the '
            'verdict survives. Both arms are measured in ONE harness here, so the comparison is '
            'internally like-for-like; the absolute numbers are not comparable with the verdict '
            "document's, whose week sets and metric definition differ."),
        'arms': results, 'paired_vs_season_constant': paired,
        'paired_vs_current_season_only': paired_vs_base,
        'n_bands_changed_from_season_constant': dict(cap_counts),
    }
    OUT.write_text(json.dumps(art, indent=2))
    return Outcome.ok('ROLE_STATE_STUDY_RUN', value={
        'rho_selection': {a: results[a]['selection']['rho']['mean'] for a in ARMS},
        'rho_confirmation': {a: results[a]['confirmation']['rho']['mean'] for a in ARMS},
        'paired': {a: {k: v['mean_diff_vs_season_constant'] for k, v in r.items()}
                   for a, r in paired.items()}})


def main() -> int:
    o = run()
    print(o.state, o.code)
    print(json.dumps(o.value if o.state.name == 'PASS' else o.detail, indent=2, default=str))
    return 0 if o.state.name == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
