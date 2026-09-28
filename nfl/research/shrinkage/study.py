#!/usr/bin/env python3.12
"""#99 -- where the between-player variance goes, and whether the prior is what destroys it.

THE QUESTION. V1's projected means vary far less between players than realised points do. The
hypothesis on the table is that the hierarchical prior is the cause: it shrinks players toward broad
positional and depth shapes, so players who should be separated arrive at nearly the same number.

WHAT THE REPOSITORY ALREADY SAID, AND WHY IT IS NOT AN ANSWER. `proj_v1.PRIOR_WEIGHT_CAP` was swept
over {0, 2, 4, 8, 12, 24} and rank correlation came out HIGHEST at a cap of 0 -- no prior at all --
falling monotonically as prior weight rose. Read naively that says the prior is worthless. It cannot
say that, because the cap is one scalar applied to a prior that is not one thing:

    a PLAYER-OWN prior is built from this player's own games -- every player gets a different value;
    a COHORT prior (ROLE_GROUP, ARCHETYPE, POSITIONAL_BROAD) is a pooled average of OTHER players,
    so everyone in the cohort gets the SAME value.

Measured on the Week 3 slate, 63.5% of skill players receive a cohort prior, and 46 tight ends at
ARCHETYPE hold ONE distinct prior value between them. Setting the cap to 0 switches off both kinds
at once, so the sweep cannot distinguish "his own history does not help" from "a constant shared
with 45 other players actively hurts". Those call for opposite repairs.

THE DESIGN. The cap is made per-tier and the two are separated:

    OWN_OFF_COHORT_OFF   cap 0 everywhere -- the sweep's rank winner, current season only
    PRODUCTION           cap 2 everywhere -- what ships today
    OWN_ON_COHORT_OFF    a player's own history keeps weight; cohort constants get none
    OWN_HIGH_COHORT_OFF  own history weighted MORE than production allows; cohort none
    OWN_ON_COHORT_LOW    own history keeps weight; cohort constants keep a little
    COHORT_ONLY          the mirror image, included so the design cannot be accused of only
                         testing the direction it expects

PREREGISTERED BEFORE ANY ARM RAN. Selection on 2023-2025, confirmation on 2021-2022, the same split
the original cap sweep used. THAT SPLIT IS THEREFORE NOT UNTOUCHED FOR THIS QUESTION and the
confirmation seasons have now been read twice; this is recorded in the artifact as a multiplicity
cost rather than presented as a clean holdout. An arm is reported as better only if it wins on the
selection seasons AND holds on the confirmation seasons AND does not degrade calibration level.

PRIMARY OUTCOME: Spearman rank correlation between projection and realised DK points, computed
WITHIN slate-week so that week-to-week scoring level cannot inflate it, and averaged over weeks with
a week-blocked paired standard error. Games in a week are not independent observations.

SECONDARY, and none of them can override the primary: MAE, calibration level, realised points of
the top 30 by projection, and the separation measurements this task was set to make -- cross-
sectional SD of projected means against realised, top-decile-to-median separation, and the same
within position, role band and projected-opportunity slices.

WHAT THIS CANNOT DO. It cannot validate the projection system. It compares shrinkage arms on
historical seasons; it says nothing about 2026 and nothing about whether any arm is good enough to
act on. PROJECTION_SYSTEM_STATE stays NOT_VALIDATED whatever comes out of it.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT = _REPO / 'nfl/research/shrinkage/SHRINKAGE_STUDY.json'
PLAYER_GAME = _REPO / 'nfl/warehouse/PLAYER_GAME.json'

SPEC_VERSION = 'shrinkage-99-1'

#: PREREGISTERED. Selection first, confirmation second, and the arm is chosen on selection only.
SELECTION_SEASONS = (2023, 2024, 2025)

#: 2021 WAS PREREGISTERED AS A CONFIRMATION SEASON AND IS VOID. The usage panel begins in 2021, so
#: a 2021 forecast reads `through_season = 2020`, which holds nothing: every prior comes back
#: PRIOR_UNAVAILABLE and all 2,698 projections are IDENTICAL across all six arms. A season in which
#: the treatment cannot act is not a weak test of it, it is not a test of it. Dropping it is
#: recorded here rather than done silently, because dropping a preregistered season after seeing
#: the data is exactly the move that needs to be visible.
VOID_SEASONS = {2021: ('panel begins in 2021 so through_season=2020 is empty; every prior is '
                       'PRIOR_UNAVAILABLE and every arm produces identical projections')}
CONFIRMATION_SEASONS = (2022,)
ALL_SEASONS = (2021, 2022, 2023, 2024, 2025)

OWN_TIERS = ('PLAYER_OWN_ROLE', 'PLAYER_OWN_OFF_ROLE')
COHORT_TIERS = ('ROLE_GROUP', 'ARCHETYPE', 'TEAM_CONTEXT', 'POSITIONAL_BROAD')

#: (name, own cap, cohort cap). Declared in full before any of them ran.
ARMS = (
    ('OWN_OFF_COHORT_OFF', 0.0, 0.0),
    ('PRODUCTION', 2.0, 2.0),
    ('OWN_ON_COHORT_OFF', 2.0, 0.0),
    ('OWN_HIGH_COHORT_OFF', 8.0, 0.0),
    ('OWN_ON_COHORT_LOW', 2.0, 0.5),
    ('COHORT_ONLY', 0.0, 2.0),
)

MIN_WEEK_N = 20  # a slate-week with fewer scored players cannot carry a within-week rank


# ------------------------------------------------------------------------------- small statistics
def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = _rank(a), _rank(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return (num / (da * db)) if da > 0 and db > 0 else None


def block_mean_se(per_week):
    """Mean over weeks and its standard error, treating the WEEK as the independent unit."""
    v = [x for x in per_week if x is not None]
    if len(v) < 2:
        return (statistics.fmean(v) if v else None), None, len(v)
    m = statistics.fmean(v)
    se = statistics.stdev(v) / math.sqrt(len(v))
    return m, se, len(v)


def paired_block(per_week_a, per_week_b):
    """Week-blocked paired difference a-b. Weeks, not players, are the unit."""
    d = [x - y for x, y in zip(per_week_a, per_week_b) if x is not None and y is not None]
    if len(d) < 2:
        return None, None, len(d)
    m = statistics.fmean(d)
    se = statistics.stdev(d) / math.sqrt(len(d))
    return m, se, len(d)


#: Below this the median is too close to zero for a ratio to it to mean anything: the statistic
#: explodes on the denominator rather than reporting separation. ROLE_GROUP hit exactly this, with
#: a median near zero returning a "separation" of 34.4 against an actual that could not be computed
#: at all. DECLARED as a reporting floor in DK points; nothing is clipped or dropped because of it.
MEDIAN_FLOOR_FOR_RATIO = 0.5


def top_decile_to_median(xs):
    """Separation: the top decile's mean over the median. Dimensionless, so arms compare.

    Returns None when the median is at or below MEDIAN_FLOOR_FOR_RATIO. A ratio to a near-zero
    denominator is not a large separation, it is an undefined one, and reporting it as a number
    invites it to be quoted as a finding.
    """
    if len(xs) < 20:
        return None
    s = sorted(xs)
    med = statistics.median(s)
    top = s[int(0.9 * len(s)):]
    if not top or med <= MEDIAN_FLOOR_FOR_RATIO:
        return None
    return statistics.fmean(top) / med


# ------------------------------------------------------------------------------------ the arms
def run_arm(own_cap, cohort_cap, seasons, ctx):
    """One arm, forward-chained. Returns per-(season, week) lists of (player, pred, actual, meta)."""
    from nfl.tools import forward_chain as F
    from nfl.tools import proj_v1 as V

    V.PRIOR_WEIGHT_CAP_BY_TIER = ({t: own_cap for t in OWN_TIERS}
                                  | {t: cohort_cap for t in COHORT_TIERS})
    weeks_out = []
    try:
        for season in seasons:
            sp, depth, groups, bonus, ip, priors = ctx[season]
            # PRATES is a module global consumed inside project_week. Building the context for a
            # later season left it pinned to that season, so every arm would have been scored with
            # one season's touchdown rates. Re-pin it per season here.
            F.PRATES[0] = ctx['_prates'][season]
            for week in ctx[(season, 'weeks')]:
                proj = F.project_week(ctx['panel'], sp, season, week, priors, depth, groups,
                                      bonus, ip, 1.0, prior_cap=max(own_cap, cohort_cap))
                pool_club = F.POOL_CLUB[0]
                recs = []
                for gsis in F.POOL[0]:
                    if gsis in ctx[(season, 'excluded')]:
                        continue
                    pred = proj.get(gsis)
                    if pred is None:
                        continue
                    ar = ctx['actual'].get((season, week, gsis))
                    recs.append({
                        'player_id': gsis,
                        'position': sp.get(gsis),
                        'club': pool_club.get(gsis),
                        'pred': pred,
                        'actual': (ar.get('dk_points_current_rules') if ar else 0.0) or 0.0,
                        'appeared': ar is not None,
                        'prior_tier': (priors.get(gsis) or (None, {}))[1].get('tier'),
                        'role_band': (priors.get(gsis) or (None, None))[0],
                    })
                if len(recs) >= MIN_WEEK_N:
                    weeks_out.append({'season': season, 'week': week, 'records': recs})
    finally:
        V.PRIOR_WEIGHT_CAP_BY_TIER = {}
    return weeks_out


def build_context(seasons):
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
    pg_rows = list(pg.values())
    pos_map, inferred = F.positions_for_chain(panel, roster_pos)

    ctx = {'panel': panel,
           'actual': {(r['season'], int(r['week']), r['player_id']): r for r in pg_rows}}
    for season in seasons:
        through = season - 1
        sp = F._SeasonPos(pos_map, season, roster_pos)
        depth = V.depth_shares(panel, sp, through=through)
        groups = V.group_shares(panel, sp, through=through)
        bonus = V.bonus_rates(panel, sp, through=through)
        ip = V.int_rate(panel, sp, through=through)['int_per_attempt']
        F.PRATES[0] = R.positional_rates(panel, sp)
        gl = [g for g in panel['players'] if sp.get(g) in F.SKILL]
        priors = F.season_priors(panel, sp, season, gl)
        ctx[season] = (sp, depth, groups, bonus, ip, priors)
        ctx[(season, 'excluded')] = {g for (g, s) in inferred if s == season}
        ctx[(season, 'weeks')] = [w for w in sorted(
            {int(w) for g, ss in panel['players'].items()
             for s2, ws in ss.items() if int(s2) == season for w in ws})
            if w > F.MIN_PRIOR_WEEKS]
    # PRATES is a module global read during projection, so it must be re-pinned per season inside
    # the arm loop rather than left at whatever the last context build set it to.
    ctx['_prates'] = {s: R.positional_rates(panel, ctx[s][0]) for s in seasons}
    return ctx


# ------------------------------------------------------------------------------------- measuring
#: A slice standing in for "players a DFS lineup would actually consider". TRUE DFS RELEVANCE IS
#: UNAVAILABLE HISTORICALLY -- this checkout holds no past DraftKings salaries or rosters, which
#: `eval/calibration.py` already declares -- so this is a PROXY and is named as one. It is built
#: from the PREGAME role band, which is neither a prediction nor an outcome: conditioning the slice
#: on the projection would restrict range on the predictor, and conditioning it on realised points
#: would define the slice by the thing being scored.
DFS_PROXY_BANDS = ('ALPHA', 'PRIMARY', 'SECONDARY')


def score_arm(weeks, dfs_relevant=None):
    """Within-week rank correlation and the separation measurements, per week then blocked."""
    rho, mae, level, top30, sd_pred, sd_act, sep_pred, sep_act = ([] for _ in range(8))
    rho_dfs = []
    for w in weeks:
        recs = w['records']
        p = [r['pred'] for r in recs]
        a = [r['actual'] for r in recs]
        rho.append(spearman(p, a))
        mae.append(statistics.fmean(abs(x - y) for x, y in zip(p, a)))
        mp = statistics.fmean(p)
        level.append((statistics.fmean(a) / mp) if mp > 0 else None)
        order = sorted(range(len(recs)), key=lambda i: -p[i])[:30]
        top30.append(statistics.fmean(a[i] for i in order) if order else None)
        sd_pred.append(statistics.pstdev(p) if len(p) > 1 else None)
        sd_act.append(statistics.pstdev(a) if len(a) > 1 else None)
        sep_pred.append(top_decile_to_median(p))
        sep_act.append(top_decile_to_median(a))
        idx = [i for i, r in enumerate(recs) if r.get('role_band') in DFS_PROXY_BANDS]
        rho_dfs.append(spearman([p[i] for i in idx], [a[i] for i in idx])
                       if len(idx) >= MIN_WEEK_N else None)
    out = {}
    for nm, series in (('rho', rho), ('mae', mae), ('level', level), ('top30_actual', top30),
                       ('sd_pred', sd_pred), ('sd_actual', sd_act),
                       ('sep_pred_top_decile_over_median', sep_pred),
                       ('sep_actual_top_decile_over_median', sep_act),
                       ('rho_dfs_relevant', rho_dfs)):
        m, se, n = block_mean_se(series)
        out[nm] = {'mean': (round(m, 4) if m is not None else None),
                   'week_blocked_se': (round(se, 4) if se is not None else None), 'n_weeks': n}
    out['_per_week'] = {'rho': rho, 'mae': mae, 'top30_actual': top30,
                        'rho_dfs_relevant': rho_dfs}
    sdp = out['sd_pred']['mean']
    sda = out['sd_actual']['mean']
    out['sd_ratio_pred_over_actual'] = (round(sdp / sda, 4) if sdp and sda else None)
    return out


# ---------------------------------------------------------------------------- prior-side anatomy
def prior_anatomy(ctx, seasons):
    """How much of the cross-sectional spread the PRIOR itself carries, before any blending.

    This is the measurement the task is named for. For each tier it reports how many players hold
    it, how many DISTINCT prior values they hold between them, and the spread of those values. A
    cohort tier is a constant by construction, so its distinct count is the number of cohorts and
    not the number of players, and the gap between the two is variance that no downstream stage can
    put back.
    """
    from nfl.tools import proj_v1 as V
    KEY = {'WR': 'target_share', 'TE': 'target_share', 'RB': 'carry_share',
           'QB': 'pass_attempt_share'}
    out = {}
    for season in seasons:
        sp, _d, _g, _b, _ip, priors = ctx[season]
        per = collections.defaultdict(list)
        for gsis, (band, pr) in priors.items():
            pos = sp.get(gsis)
            tier = (pr or {}).get('tier')
            if pos not in KEY or not tier:
                continue
            v = ((pr.get('measures') or {}).get(KEY[pos]))
            eff = pr.get('effective_obs_for_prior', pr.get('effective_obs_at_role'))
            per[(pos, tier)].append((v, eff))
        rows = []
        for (pos, tier), vals in sorted(per.items()):
            vs = [round(v, 6) for v, _e in vals if v is not None]
            effs = [e for _v, e in vals if e is not None]
            if not vs:
                continue
            rows.append({
                'position': pos, 'tier': tier, 'n_players': len(vals),
                'n_distinct_prior_values': len(set(vs)),
                'collapse_fraction': round(1 - len(set(vs)) / len(vs), 4),
                'sd_of_prior_values': round(statistics.pstdev(vs), 6) if len(vs) > 1 else 0.0,
                'median_effective_obs': round(statistics.median(effs), 2) if effs else None,
                'effective_obs_at_or_above_cap': (
                    round(sum(1 for e in effs if e >= V.PRIOR_WEIGHT_CAP) / len(effs), 4)
                    if effs else None),
            })
        out[str(season)] = rows
    return out


# ------------------------------------------------------------------------------------- the study
def run() -> Outcome:
    seasons = tuple(sorted(set(SELECTION_SEASONS + CONFIRMATION_SEASONS)))
    ctx = build_context(ALL_SEASONS)
    if isinstance(ctx, Outcome):
        return ctx

    # A NO-OP CHECK BEFORE ANY ARM IS BELIEVED. A per-tier cap set to production's single value must
    # reproduce production exactly. If it does not, the mechanism is changing something other than
    # the weight and every arm below is measuring that instead.
    from nfl.tools import proj_v1 as V
    parity_weeks = run_arm(V.PRIOR_WEIGHT_CAP, V.PRIOR_WEIGHT_CAP, (seasons[0],), ctx)
    V.PRIOR_WEIGHT_CAP_BY_TIER = {}
    plain_weeks = run_arm_plain(seasons[0], ctx)
    mismatch = []
    for a, b in zip(parity_weeks, plain_weeks):
        for ra, rb in zip(a['records'], b['records']):
            if ra['player_id'] != rb['player_id'] or abs(ra['pred'] - rb['pred']) > 1e-9:
                mismatch.append({'week': a['week'], 'player_id': ra['player_id'],
                                 'tiered': ra['pred'], 'production': rb['pred']})
    if mismatch:
        return Outcome.fail(
            'TIERED_CAP_IS_NOT_A_NO_OP',
            f'{len(mismatch)} projections differ when the per-tier cap is set to the single '
            f'production cap, so the mechanism changes more than the weight',
            examples=mismatch[:5])

    results, per_week_store, slices = {}, {}, {}
    for name, own_cap, cohort_cap in ARMS:
        weeks = run_arm(own_cap, cohort_cap, seasons, ctx)
        if name in ('PRODUCTION', 'OWN_OFF_COHORT_OFF', 'OWN_ON_COHORT_OFF'):
            slices[name] = slice_report(
                [w for w in weeks if w['season'] in SELECTION_SEASONS], ctx, own_cap, cohort_cap)
        sel = [w for w in weeks if w['season'] in SELECTION_SEASONS]
        con = [w for w in weeks if w['season'] in CONFIRMATION_SEASONS]
        results[name] = {
            'own_cap': own_cap, 'cohort_cap': cohort_cap,
            'selection': {k: v for k, v in score_arm(sel).items() if k != '_per_week'},
            'confirmation': {k: v for k, v in score_arm(con).items() if k != '_per_week'},
            'n_weeks_selection': len(sel), 'n_weeks_confirmation': len(con),
        }
        per_week_store[name] = {'selection': score_arm(sel)['_per_week'],
                                'confirmation': score_arm(con)['_per_week']}

    # paired, week-blocked, against production
    paired = {}
    for name in results:
        if name == 'PRODUCTION':
            continue
        row = {}
        for split in ('selection', 'confirmation'):
            for metric in ('rho', 'rho_dfs_relevant', 'mae', 'top30_actual'):
                a = per_week_store[name][split][metric]
                b = per_week_store['PRODUCTION'][split][metric]
                m, se, n = paired_block(a, b)
                row[f'{split}.{metric}'] = {
                    'mean_diff_vs_production': (round(m, 4) if m is not None else None),
                    'week_blocked_se': (round(se, 4) if se is not None else None),
                    'n_paired_weeks': n,
                    'z': (round(m / se, 2) if m is not None and se else None)}
        paired[name] = row

    art = {
        'ARTIFACT': 'SHRINKAGE_STUDY',
        'SPEC_VERSION': SPEC_VERSION,
        'QUESTION': __doc__.strip().splitlines()[0],
        'WHY_THE_EXISTING_SWEEP_CANNOT_ANSWER_IT': (
            'PRIOR_WEIGHT_CAP is one scalar over a prior that is two different objects. A '
            'player-own prior differs for every player; a cohort prior is a constant shared by '
            'everyone in the cohort. Setting the cap to 0 switches off both, so the sweep cannot '
            'separate "his own history does not help" from "a shared constant hurts".'),
        'PREREGISTERED': {
            'selection_seasons': list(SELECTION_SEASONS),
            'confirmation_seasons': list(CONFIRMATION_SEASONS),
            'confirmation_seasons_as_preregistered': [2021, 2022],
            'confirmation_seasons_dropped': {str(k): v for k, v in VOID_SEASONS.items()},
            'arms': [{'name': n, 'own_cap': o, 'cohort_cap': c} for n, o, c in ARMS],
            'primary_outcome': ('within-slate-week Spearman rank correlation between projection '
                                'and realised DK points, averaged over weeks, week-blocked SE'),
            'own_tiers': list(OWN_TIERS), 'cohort_tiers': list(COHORT_TIERS),
        },
        'VOID_SEASON_2021': {
            'state': 'VOID',
            'why': VOID_SEASONS[2021],
            'measured': ('0 of 2698 projections differ between the cap-0 and cap-2 arms in 2021, '
                         'against 3617 of 3627 in 2022'),
            'CONSEQUENCE_FOR_THE_EXISTING_CONSTANT': (
                'PRIOR_WEIGHT_CAP=2.0 was CONFIRMED on "untouched 2021-2022". Half of that '
                'confirmation set cannot respond to the cap at all, so any difference measured on '
                'it was mechanically halved toward zero before it was read. The sweep concluded '
                'that cap 2 and cap 0 were near-tied on MAE and top-30 points on exactly that '
                'set. That near-tie is partly an artefact of the split. This does not show the '
                'constant is wrong; it shows the evidence recorded for it does not support it.'),
        },
        'MULTIPLICITY_COST': (
            'the confirmation season 2022 was already read once, to confirm '
            'PRIOR_WEIGHT_CAP=2. This study reads it a second time for a related question, so it '
            'is NOT an untouched holdout here, and after 2021 was voided it is ONE season of 14 '
            'weeks. Six arms are compared, and no multiplicity '
            'correction is applied to the paired z values below; they are descriptive. A genuinely '
            'confirmatory result needs a season this question has never seen.'),
        'DFS_RELEVANCE_IS_A_PROXY': (
            'no historical DraftKings salaries or rosters exist in this checkout, so the '
            f'DFS-relevant slice is pregame role band in {DFS_PROXY_BANDS}. It is neither a '
            'prediction nor an outcome, which the alternatives would have been.'),
        'PROJECTION_SYSTEM_STATE': 'NOT_VALIDATED',
        'WHAT_THIS_DOES_NOT_DO': (
            'it does not validate the projection system, it does not measure 2026, and no arm '
            'here is adopted by running it. Adoption is a separate decision on a separate commit.'),
        'TIERS_THE_HISTORY_CANNOT_TEST': {
            'observed_in_the_forward_chain': ['PLAYER_OWN_ROLE', 'PLAYER_OWN_OFF_ROLE',
                                              'ROLE_GROUP'],
            'observed_on_the_live_week_3_slate': ['PLAYER_OWN_ROLE', 'PLAYER_OWN_OFF_ROLE',
                                                  'ROLE_GROUP', 'ARCHETYPE'],
            'why_they_differ': (
                'a forward-chained season builds its priors from a complete previous season, so a '
                'player usually has enough of his own history to reach ROLE_GROUP at worst. Week 3 '
                'of 2026 is three games into a panel that thins at its live edge, so 98 players '
                'fall all the way to ARCHETYPE.'),
            'CONSEQUENCE': (
                'ARCHETYPE is where the collapse is most extreme -- 46 tight ends hold ONE distinct '
                'prior value between them, 17 receivers hold one, and the prior takes 95-96% of '
                'their blend. The arm comparison below CANNOT measure the harm from that tier, '
                'because it barely fires in the seasons being scored. The live slate is therefore '
                'MORE compressed than anything measured here, and the arm differences below are a '
                'LOWER BOUND on what the same change would do to the Week 3 slate. That is a '
                'reason not to extrapolate, not a reason to assume the effect is larger.'),
        },
        'prior_anatomy': prior_anatomy(ctx, ALL_SEASONS),
        'arms': results,
        'paired_vs_production': paired,
        'slices_selection_seasons': slices,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=2))
    return Outcome.ok('SHRINKAGE_STUDY_RUN', value={
        'arms': {k: {'sel_rho': v['selection']['rho']['mean'],
                     'con_rho': v['confirmation']['rho']['mean'],
                     'sel_rho_dfs': v['selection']['rho_dfs_relevant']['mean'],
                     'sel_mae': v['selection']['mae']['mean'],
                     'sd_ratio': v['selection'].get('sd_ratio_pred_over_actual')}
                 for k, v in results.items()},
        'paired': {k: {kk: vv['mean_diff_vs_production'] for kk, vv in v.items()
                       if kk.startswith('selection.')} for k, v in paired.items()}})


def run_arm_plain(season, ctx):
    """Production's own path, with no per-tier dict in force at all. The parity reference."""
    from nfl.tools import forward_chain as F
    from nfl.tools import proj_v1 as V
    V.PRIOR_WEIGHT_CAP_BY_TIER = {}
    out = []
    sp, depth, groups, bonus, ip, priors = ctx[season]
    F.PRATES[0] = ctx['_prates'][season]
    for week in ctx[(season, 'weeks')]:
        proj = F.project_week(ctx['panel'], sp, season, week, priors, depth, groups, bonus, ip,
                              1.0, prior_cap=V.PRIOR_WEIGHT_CAP)
        pool_club = F.POOL_CLUB[0]
        recs = []
        for gsis in F.POOL[0]:
            if gsis in ctx[(season, 'excluded')]:
                continue
            pred = proj.get(gsis)
            if pred is None:
                continue
            ar = ctx['actual'].get((season, week, gsis))
            recs.append({'player_id': gsis, 'position': sp.get(gsis),
                         'club': pool_club.get(gsis), 'pred': pred,
                         'actual': (ar.get('dk_points_current_rules') if ar else 0.0) or 0.0,
                         'appeared': ar is not None,
                         'prior_tier': (priors.get(gsis) or (None, {}))[1].get('tier'),
                         'role_band': (priors.get(gsis) or (None, None))[0]})
        if len(recs) >= MIN_WEEK_N:
            out.append({'season': season, 'week': week, 'records': recs})
    return out




# ------------------------------------------------------- slices, prior contribution, season phase
def prior_weight_fraction(pr, cur_n, own_cap, cohort_cap):
    """Reproduce `_combine`'s weight arithmetic without touching production.

    pn = min(effective observations, the cap in force for this tier); cn = current-season weeks
    already played. The fraction the prior takes of the blend is pn / (pn + cn).
    """
    tier = (pr or {}).get('tier')
    if tier in OWN_TIERS:
        cap = own_cap
    elif tier in COHORT_TIERS:
        cap = cohort_cap
    else:
        return None
    eff = pr.get('effective_obs_for_prior', pr.get('effective_obs_at_role'))
    if eff is None:
        return None
    pn = min(float(eff), float(cap))
    cn = float(cur_n or 0.0)
    if pn + cn <= 0:
        return 0.0
    return pn / (pn + cn)


def slice_report(weeks, ctx, own_cap, cohort_cap):
    """Separation by slice, prior contribution, and rank error against prior weight.

    SALARY SLICES ARE UNAVAILABLE and are not approximated: this checkout holds no historical
    DraftKings salaries, so there is no money axis to slice on. PROJECTED OPPORTUNITY is used
    instead and is labelled as what it is -- a slice on the model's own output, which restricts
    range on the predictor, so it reads within-slice separation and NOT a within-slice correlation.
    """
    from nfl.tools import forward_chain as F
    by_pos = collections.defaultdict(lambda: {'pred': [], 'actual': []})
    by_band = collections.defaultdict(lambda: {'pred': [], 'actual': []})
    by_tier = collections.defaultdict(lambda: {'pred': [], 'actual': []})
    pw_bins = collections.defaultdict(lambda: {'err': [], 'n': 0})
    by_week_index = collections.defaultdict(lambda: {'rho': [], 'pw': []})

    for w in weeks:
        recs = w['records']
        season, week = w['season'], w['week']
        _sp, _d, _g, _b, _ip, priors = ctx[season]
        p = [r['pred'] for r in recs]
        a = [r['actual'] for r in recs]
        rp, ra = _rank(p), _rank(a)
        n = len(recs)
        pw_this_week = []
        for i, r in enumerate(recs):
            by_pos[r['position']]['pred'].append(r['pred'])
            by_pos[r['position']]['actual'].append(r['actual'])
            by_band[r['role_band']]['pred'].append(r['pred'])
            by_band[r['role_band']]['actual'].append(r['actual'])
            by_tier[r['prior_tier']]['pred'].append(r['pred'])
            by_tier[r['prior_tier']]['actual'].append(r['actual'])
            pr = (priors.get(r['player_id']) or (None, None))[1]
            _cur, cur_n = F.shares_before(ctx['panel'], r['player_id'], r['club'],
                                          r['position'], season, week)
            pwf = prior_weight_fraction(pr, cur_n, own_cap, cohort_cap)
            if pwf is None:
                continue
            pw_this_week.append(pwf)
            # normalised rank error: 0 is a perfect placement, 1 is the worst possible
            err = abs(rp[i] - ra[i]) / (n - 1) if n > 1 else None
            if err is not None:
                b = min(int(pwf * 5), 4)
                pw_bins[f'{b/5:.1f}-{(b+1)/5:.1f}']['err'].append(err)
                pw_bins[f'{b/5:.1f}-{(b+1)/5:.1f}']['n'] += 1
        by_week_index[week]['rho'].append(spearman(p, a))
        if pw_this_week:
            by_week_index[week]['pw'].append(statistics.fmean(pw_this_week))

    def sep(d):
        return {'n': len(d['pred']),
                'sd_pred': round(statistics.pstdev(d['pred']), 4) if len(d['pred']) > 1 else None,
                'sd_actual': round(statistics.pstdev(d['actual']), 4) if len(d['actual']) > 1 else None,
                'sep_pred': (round(v, 3) if (v := top_decile_to_median(d['pred'])) else None),
                'sep_actual': (round(v, 3) if (v := top_decile_to_median(d['actual'])) else None),
                'rho_within_slice': (round(v, 4)
                                     if (v := spearman(d['pred'], d['actual'])) else None)}

    return {
        'SALARY_SLICE': ('UNAVAILABLE. No historical DraftKings salaries exist in this checkout. '
                         'Not approximated -- a proxy for money is not money.'),
        'by_position': {k: sep(v) for k, v in sorted(by_pos.items()) if k},
        'by_pregame_role_band': {k: sep(v) for k, v in sorted(by_band.items()) if k},
        'by_prior_tier': {str(k): sep(v) for k, v in sorted(by_tier.items(), key=lambda x: str(x[0]))},
        'rank_error_by_prior_weight': {
            k: {'n': v['n'], 'mean_normalised_rank_error': round(statistics.fmean(v['err']), 4)}
            for k, v in sorted(pw_bins.items()) if v['err']},
        'RANK_ERROR_CAVEAT': (
            'the prior-weight bins are OBSERVATIONAL, not an experiment. A player receives a high '
            'prior weight BECAUSE he has little current-season evidence, and a player with little '
            'current-season evidence is a different kind of player -- typically a reserve. So a '
            'higher rank error in a high-prior-weight bin is confounded with who lands there and '
            'must not be read as the prior causing the error. The ARMS above are the experiment; '
            'this table is a description of where the weight falls.'),
        'by_week_index': {
            str(k): {'mean_rho': (round(statistics.fmean([x for x in v['rho'] if x is not None]), 4)
                                  if any(x is not None for x in v['rho']) else None),
                     'mean_prior_weight_fraction': (round(statistics.fmean(v['pw']), 4)
                                                    if v['pw'] else None),
                     'n_season_weeks': len(v['rho'])}
            for k, v in sorted(by_week_index.items())},
        'SEASON_PHASE_NOT_HARD_CODED': (
            'week index is reported continuously rather than cut into early/mid/late. A boundary '
            'drawn because it sounds intuitive would be a fitted constant wearing a name. If a '
            'phase effect exists it has to show as a pattern across this series first.'),
    }


def main() -> int:
    o = run()
    print(o.state, o.code)
    print(json.dumps(o.value if o.state.name == 'PASS' else o.detail, indent=2, default=str))
    return 0 if o.state.name == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
