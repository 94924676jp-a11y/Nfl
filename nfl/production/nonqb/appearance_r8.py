"""R8 appearance: one model whose regime moves with evidence, not the calendar.

WHAT R7 ESTABLISHED, AND WHY A SWITCH WOULD BE THE WRONG ANSWER

Forward-chained 2022-2025 on identical rows, Brier by week bucket:

    week 1     V1 0.24667   R7 0.10966
    weeks 2-4  V1 0.18146   R7 0.11510
    weeks 5-9  V1 0.11213   R7 0.11814
    weeks 10-18 V1 0.10975  R7 0.11989

Every one of those intervals excludes zero. The two models are strong in
complementary regimes: R7 carries the depth/roster frame, which is all there is
in week 1; V1 carries current-season participation history, which does not
exist in week 1 and dominates by week 5.

`if week <= 4 use R7 else V1` would reproduce the table and learn nothing. Week
number is not the cause -- it is a proxy for HOW MANY CURRENT-SEASON GAMES THIS
PLAYER HAS. A player who signs in week 9 has as little current-season evidence
as one in week 1, and a calendar switch would hand him the wrong model.

THE STRUCTURE

Each participation quantity enters weighted by its own reliability,

    w = n_cur / (n_cur + k)

where `n_cur` is the player's own count of prior CURRENT-SEASON frame rows and
`k` is estimated, never chosen: the ratio of within-player to between-player
variance of player-season appearance rates. Measured over 4,073 player-seasons
with at least four games: within 0.139520, between 0.114588, **k = 1.2176**.
So w is 0 at cold start, 0.45 after one game, 0.71 after three, 0.87 after
eight. The depth block is additionally interacted with (1 - w), so depth is free
to carry more weight exactly where participation carries less.

Nothing here is a week number and nothing is a threshold. The transition is a
consequence of how much evidence exists about the player in front of us.

WHAT IS INHERITED AND MUST NOT BE LOST

Everything R7 refuses, R8 refuses. The frame is R7's union frame, so the
LOOKBACK_CANDIDATE censoring stays lifted; depth selection stays point-in-time
through `depth_vintage`; the season boundary stays explicitly represented as a
reset streak plus a separate carried streak; and the
`no_history_and_not_depth_listed` cell stays dropped from the fit and declined
by name at prediction time, because its appearance rate is 1.0000 with zero
variance and that is a construction rather than an estimate.
"""
from __future__ import annotations

import collections
import hashlib
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p1'),
           str(_REPO / 'nfl' / 'research' / 'p2'),
           str(_REPO / 'nfl' / 'research' / 'p3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production.nonqb import appearance_model as AM  # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7  # noqa: E402
from nfl.production.nonqb import depth_vintage as DV  # noqa: E402

SPEC_VERSION = 'appearance-r8-reliability-weighted-1'

# Inherited verbatim so a reader of R8 alone still sees what is refused.
UNSUPPORTED_CELL = R7.UNSUPPORTED_CELL
KNOWN_HEALTHY = R7.KNOWN_HEALTHY
NO_HISTORY = R7.NO_HISTORY
UNKNOWN_STATUS = R7.UNKNOWN_STATUS
is_unsupported = R7.is_unsupported
state_of = R7.state_of

MIN_SEASON_GAMES_FOR_K = 4          # a variance over fewer is not a variance
_HL = 0.5 ** (1 / 3)                # the frozen half-life, unchanged

_ENRICHED = {}
_K = {}
_FIT = {}


# ---------------------------------------------------------------- the frame
# The frozen P2/P3 features R8 carries over from V1, all prior-only pregame
# quantities. They are what V1 has and R7 dropped, and the week 5-18 deficit is
# where their absence shows. Joined onto the union frame by (season, week,
# team, gsis) -- present on panel rows, absent by construction on the rows the
# depth chart contributed, and carrying an explicit missingness flag either way.
V1_NUMERIC = ('f_rate3', 'f_rate5', 'f_rate_ewma', 'f_prev_snap',
              'f_snap_ewma', 'f_vac_snap', 'f_vac_route', 'f_vac_target',
              'f_vac_carry', 'f_snap_before_absence', 'f_swing',
              'f_volatility')


def _panel_v1_features() -> dict:
    """(season, week, team, gsis) -> the frozen P2/P3 pregame feature block."""
    st = AM.stage_inputs()
    if st.state is not State.PASS:
        return {}
    M, A, F = AM._frozen()
    kick = A.kickoffs()
    inj, _ = A.injuries(kick)
    rows = A.build(kick, inj, A.depth())
    F.enrich(rows, inj)
    out = {}
    for r in rows:
        out[(int(r['season']), int(r['week']), r['team'], r['gsis_id'])] = {
            k: r.get(k) for k in V1_NUMERIC + (
                'f_weeks_since_appear', 'f_n_teammates_out', 'f_practice_seq',
                'f_practice_improving', 'f_practice_worsening')}
    return out


def _panel_snap_shares() -> dict:
    """(season, week, team, gsis) -> snap_share, for the rows that have one.

    Frame rows contributed by the depth chart have no snap share at all -- they
    are precisely the players who did not take a snap -- so this is missing by
    construction on part of the frame and carries an explicit missingness flag
    rather than a zero that would read as "played, took no snaps".
    """
    st = AM.stage_inputs()
    if st.state is not State.PASS:
        return {}
    M, A, F = AM._frozen()
    kick = A.kickoffs()
    inj, _ = A.injuries(kick)
    out = {}
    for r in A.build(kick, inj, A.depth()):
        v = r.get('snap_share')
        if v is not None:
            out[(int(r['season']), int(r['week']), r['team'],
                 r['gsis_id'])] = float(v)
    return out


def enriched_frame() -> Outcome:
    """R7's frame, plus each player's CURRENT-SEASON evidence to date."""
    # Keyed on the same dependency fingerprint as R7's frame: this is R7's
    # frame plus current-season evidence, so it inherits exactly the same
    # reusability and exactly the same staleness risk.
    _fp = R7._dependency_fingerprint()
    if _ENRICHED.get('rows') and _ENRICHED.get('fingerprint') == _fp:
        # The stored evidence may already carry a `fingerprint` key, so it
        # is merged rather than passed twice -- Outcome.ok refuses a
        # duplicate keyword, which is the right behaviour and was the bug.
        _ev = dict(_ENRICHED['evidence'])
        _ev['fingerprint'] = _fp
        return Outcome.ok('R8_FRAME_CACHED', value=_ENRICHED['rows'],
                          spec_version=SPEC_VERSION, cached=True, **_ev)
    if _ENRICHED.get('rows'):
        _ENRICHED.clear()
    fr = R7.build_frame()
    if fr.state is not State.PASS:
        return fr
    snaps = _panel_snap_shares()
    v1f = _panel_v1_features()
    rows = sorted(fr.value, key=lambda r: (r['s'], r['w']))
    hist = collections.defaultdict(list)
    n_snap = n_v1 = 0
    for r in rows:
        past = hist[(r['pid'], r['s'])]          # CURRENT SEASON ONLY
        app = [x['appeared'] for x in past]
        r['n_cur'] = len(past)
        r['app_cur'] = float(np.mean(app)) if app else None
        r['rate3_cur'] = float(np.mean(app[-3:])) if app else None
        if app:
            num = den = 0.0
            ww = 1.0
            for v in reversed(app):
                num += ww * v
                den += ww
                ww *= _HL
            r['app_ewma_cur'] = num / den
        else:
            r['app_ewma_cur'] = None
        sn = [x['snap'] for x in past if x.get('snap') is not None]
        if sn:
            num = den = 0.0
            ww = 1.0
            for v in reversed(sn):
                num += ww * v
                den += ww
                ww *= _HL
            r['snap_ewma_cur'] = num / den
        else:
            r['snap_ewma_cur'] = None
        r['snap'] = snaps.get((r['s'], r['w'], r['t'], r['pid']))
        if r['snap'] is not None:
            n_snap += 1
        blk = v1f.get((r['s'], r['w'], r['t'], r['pid']))
        r['v1'] = blk
        if blk is not None:
            n_v1 += 1
        hist[(r['pid'], r['s'])].append(r)
    ev = {kk: vv for kk, vv in fr.evidence.items()
          if kk not in ('cached', 'spec_version', 'value')}
    ev['n_rows_with_a_snap_share'] = n_snap
    ev['n_rows_without_a_snap_share'] = len(rows) - n_snap
    ev['n_rows_with_the_v1_feature_block'] = n_v1
    ev['n_rows_without_the_v1_feature_block'] = len(rows) - n_v1
    _ENRICHED['rows'], _ENRICHED['evidence'] = rows, ev
    _ENRICHED['fingerprint'] = _fp
    return Outcome.ok('R8_FRAME_OK', value=rows, spec_version=SPEC_VERSION,
                      cached=False, **ev)


# ------------------------------------------------------------ reliability k
def reliability_k(rows, cut=None) -> Outcome:
    """k = within-player variance / between-player variance. ESTIMATED.

    `cut` is an ordinal (season * 100 + week); only rows strictly earlier are
    used, so the constant a forecast consumes was never computed from the
    season it is forecasting.
    """
    key = int(cut or 0)
    if key in _K:
        m = _K[key]
        return Outcome.ok('R8_K_CACHED', value=m['k'], cached=True, **m['ev'])
    by = collections.defaultdict(list)
    for r in rows:
        if cut is not None and r['s'] * 100 + r['w'] >= cut:
            continue
        by[(r['pid'], r['s'])].append(r['appeared'])
    ps = [v for v in by.values() if len(v) >= MIN_SEASON_GAMES_FOR_K]
    if len(ps) < 100:
        return Outcome.blocked(
            'R8_K_NOT_ESTIMABLE',
            f'only {len(ps)} player-season(s) with at least '
            f'{MIN_SEASON_GAMES_FOR_K} games are available before the cut, so '
            f'the within/between variance ratio would be an artefact of the '
            f'sample rather than an estimate of it',
            cause=Cause.DATA, n_player_seasons=len(ps))
    within = float(np.mean([np.var(v, ddof=1) for v in ps if len(v) > 1]))
    between = float(np.var([np.mean(v) for v in ps], ddof=1))
    if not between > 0:
        return Outcome.fail(
            'R8_K_DEGENERATE',
            'between-player variance of season appearance rates is zero, so '
            'the shrinkage ratio is undefined and no weight can be formed')
    k = within / between
    ev = {'k': round(k, 6), 'within_player_variance': round(within, 6),
          'between_player_variance': round(between, 6),
          'n_player_seasons': len(ps),
          'min_games_per_player_season': MIN_SEASON_GAMES_FOR_K,
          'cut': cut, 'estimated_not_chosen': True}
    _K[key] = {'k': k, 'ev': ev}
    return Outcome.ok('R8_K_ESTIMATED', value=k, cached=False, **ev)


def weight(n_cur, k) -> float:
    """The reliability of a player's own current-season record. No calendar."""
    n = float(n_cur or 0)
    return n / (n + float(k)) if (n + float(k)) > 0 else 0.0


# -------------------------------------------------------------- featurise
def featurise(r, k):
    """R7's design row, plus the reliability-weighted current-season block."""
    f = list(R7.featurise(r))
    w = weight(r.get('n_cur'), k)
    f.append(w)
    f.append(1.0 - w)
    for key in ('app_cur', 'app_ewma_cur', 'rate3_cur', 'snap_ewma_cur'):
        v = r.get(key)
        f.append(0.0 if v is None else w * float(v))
        f.append(1.0 if v is None else 0.0)
    # `r['snap']` IS THIS GAME'S SNAP SHARE AND IS NOT A FEATURE. It was one
    # for exactly one run of this module, which scored an in-sample Brier of
    # 0.04101 at AUC 0.9895 -- a number good enough to be the bug report. A
    # player has a snap share if and only if he appeared, so the column and its
    # own missingness flag both carry the label. It is kept on the row because
    # LATER rows need it to build `snap_ewma_cur` from PRIOR games, and it is
    # never featurised for the row it belongs to.
    f.append(min(r.get('n_cur') or 0, 12) / 12.0)
    # DEPTH, FREED TO MATTER MORE WHERE PARTICIPATION MATTERS LESS. This is the
    # whole hypothesis in four columns: the same depth buckets R7 carries,
    # scaled by how little we know about the player from this season.
    rk = r.get('rank')
    bucket = ('unlisted' if rk is None else
              ('r1' if rk == 1 else 'r2' if rk == 2 else
               'r3' if rk == 3 else 'r4plus'))
    for b in ('r1', 'r2', 'r3', 'r4plus', 'unlisted'):
        f.append((1.0 - w) if bucket == b else 0.0)
    # THE V1 BLOCK. Raw, with missingness, exactly as the frozen featuriser
    # carries it -- these are the features whose absence is the whole of R7's
    # week 5-18 deficit, and damping them would be re-introducing the deficit
    # by another route.
    blk = r.get('v1') or {}
    for key in V1_NUMERIC:
        v = blk.get(key)
        f.append(0.0 if v is None else float(v))
        f.append(1.0 if v is None else 0.0)
    v = blk.get('f_weeks_since_appear')
    f.append(min(v or 9, 9) / 9.0)
    f.append(min(float(blk.get('f_n_teammates_out') or 0.0), 3.0) / 3.0)
    f.append(float(blk.get('f_practice_improving') or 0.0))
    f.append(float(blk.get('f_practice_worsening') or 0.0))
    f.append(1.0 if r.get('v1') is None else 0.0)
    return f


N_FEATURES = len(featurise({'w': 1, 'pos': 'WR', 'rank': 1, 'n_cur': 0}, 1.2))


# -------------------------------------------------------------------- fit
def fit(season: int, l2=1.0) -> Outcome:
    """Fit on frame rows from STRICTLY EARLIER seasons, minus the refused cell."""
    key = (int(season), float(l2))
    if key in _FIT:
        m = _FIT[key]
        return Outcome.ok('R8_FIT', value=m, spec_version=SPEC_VERSION,
                          cached=True, **m['evidence'])
    fr = enriched_frame()
    if fr.state is not State.PASS:
        return fr
    rows = fr.value
    ko = reliability_k(rows, cut=int(season) * 100)
    if ko.state is not State.PASS:
        return ko
    k = ko.value
    M, A, F = AM._frozen()
    train = [r for r in rows if r['s'] < season and not is_unsupported(r)]
    dropped = sum(1 for r in rows if r['s'] < season and is_unsupported(r))
    if not train:
        return Outcome.fail(
            'R8_FRAME_EMPTY',
            f'no frame row earlier than {season} survived the '
            f'unsupported-cell exclusion; a fit on nothing is not a fit')
    X = [featurise(r, k) for r in train]
    y = [r['appeared'] for r in train]
    model = A.fit_logistic(X, y, l2=l2)
    p = A.predict(model, X)
    ev = {'n_train_rows': len(train), 'n_features': len(X[0]),
          'n_dropped_unsupported_cell': dropped,
          'unsupported_cell': UNSUPPORTED_CELL,
          'train_seasons': sorted({r['s'] for r in train}),
          'in_sample_brier': float(A.brier(y, p)),
          'in_sample_auc': float(A.auc(y, p)),
          'base_rate': float(np.mean(y)), 'l2': l2,
          'k': round(k, 6), 'k_evidence': ko.evidence,
          'no_week_number_in_the_design':
              'the regime moves with n_cur, not with the calendar'}
    m = {'model': model, 'k': k, 'evidence': ev,
         'coef_sha256': hashlib.sha256(
             np.asarray(model['w']).tobytes()).hexdigest()[:16]}
    _FIT[key] = m
    return Outcome.ok('R8_FIT', value=m, spec_version=SPEC_VERSION,
                      cached=False, **ev)


# ---------------------------------------------------------------- predict
def predict(season, week, players, injuries_rows, observed_before=None,
            kickoff_utc=None, depth=None) -> Outcome:
    """Per-player P(appear). The refused cell is declined, exactly as in R7."""
    fr = enriched_frame()
    if fr.state is not State.PASS:
        return fr
    f = fit(season)
    if f.state is not State.PASS:
        return f
    k = f.value['k']
    M, A, F = AM._frozen()

    clock = R7._parse(observed_before) or R7._parse(kickoff_utc)
    if clock is None:
        return Outcome.fail(
            'R8_NO_CLOCK',
            'neither observed_before nor kickoff_utc was supplied, so the '
            'depth chart could not be selected point-in-time and the newest '
            'capture would have been used by default')
    if depth is None:
        teams = sorted({q.get('team') for q in players if q.get('team')})
        if not teams:
            return Outcome.fail('R8_NO_TEAMS', 'no player carries a team')
        cap = DV.captured(teams, clock)
        if cap.state is not State.PASS:
            return cap
        depth = cap.value
        depth_ev = {kk: vv for kk, vv in cap.evidence.items() if kk != 'value'}
    else:
        depth_ev = {'source': 'supplied_by_caller'}

    # THE V1 BLOCK AT PREDICTION TIME, FROM THE FROZEN WALK ITSELF.
    #
    # Leaving it empty was a train/serve skew and a severe one: the "v1 block
    # absent" flag fires on 6,158 training rows, all of them depth-listed
    # players who did not appear, so its coefficient is strongly negative. With
    # the block unpopulated at prediction time EVERY player tripped that flag,
    # and the first R8 board came back with SF's modelled targets at 1.41
    # against 28.71. A defect that shows up as an obviously broken board rather
    # than a slightly wrong one is the lucky version of this mistake.
    pr = AM.prospective_feature_rows(season, week, players, injuries_rows)
    if pr.state is not State.PASS:
        return pr
    v1rows = {r['gsis_id']: r for r in pr.value['target']}

    inj26 = AM.parse_injuries_rows(injuries_rows, season)
    hist = collections.defaultdict(list)
    cur = collections.defaultdict(list)
    for r in fr.value:
        hist[r['pid']].append(r)
        if r['s'] == int(season):
            cur[r['pid']].append(r)

    declined, states = {}, collections.Counter()
    rowsX, ids, ws = [], [], []
    for q in players:
        pid = q.get('gsis_id')
        if not pid:
            return Outcome.fail(
                'R8_IDENTITY_UNRESOLVED',
                'a player carries no gsis_id; fuzzy name matching is forbidden')
        d = depth.get(pid)
        past = hist.get(pid) or []
        cpast = cur.get(pid) or []
        r = {'s': int(season), 'w': int(week), 't': q.get('team'), 'pid': pid,
             'pos': R7._pos(q.get('position')), 'appeared': None,
             'rank': (d[0] if d else None), 'vendor': DV.DAILY_VENDOR,
             'n_prior': len(past),
             'prev_appeared': past[-1]['appeared'] if past else None,
             'crossed': bool(past) and past[-1]['s'] < int(season)}
        cm = 0
        for x in reversed(past):
            if x['s'] != int(season) or x['appeared']:
                break
            cm += 1
        r['cm_within'] = cm
        carried = 0
        if r['crossed']:
            for x in reversed(past):
                if x['appeared']:
                    break
                carried += 1
        r['cm_carried'] = carried

        def _ew(vals):
            if not vals:
                return None
            num = den = 0.0
            ww = 1.0
            for v in reversed(vals):
                num += ww * v
                den += ww
                ww *= _HL
            return num / den
        r['app_ewma'] = _ew([x['appeared'] for x in past])
        capp = [x['appeared'] for x in cpast]
        r['n_cur'] = len(cpast)
        r['app_cur'] = float(np.mean(capp)) if capp else None
        r['rate3_cur'] = float(np.mean(capp[-3:])) if capp else None
        r['app_ewma_cur'] = _ew(capp)
        csnap = [x['snap'] for x in cpast if x.get('snap') is not None]
        r['snap_ewma_cur'] = _ew(csnap)
        r['snap'] = None                     # unknown before the game is played
        _v = v1rows.get(pid)
        r['v1'] = ({k: _v.get(k) for k in V1_NUMERIC + (
            'f_weeks_since_appear', 'f_n_teammates_out', 'f_practice_seq',
            'f_practice_improving', 'f_practice_worsening')}
            if _v is not None else None)
        di = inj26.get((int(season), int(week), q.get('team'), pid))
        r['inj_status'] = di['report_status'] if di else None
        r['inj_practice'] = di['practice_status'] if di else None
        r['inj_available'] = 1 if di is not None else 0
        r['state'] = state_of(r)
        states[r['state']] += 1
        if is_unsupported(r):
            declined[pid] = {
                'reason': UNSUPPORTED_CELL,
                'detail': 'no prior frame row and no depth listing. The only '
                          'rows this repository holds in that cell appeared, '
                          'so its appearance rate is 1.0000 with zero '
                          'variance and is not an estimate.'}
            continue
        rowsX.append(featurise(r, k))
        ids.append(pid)
        ws.append(weight(r['n_cur'], k))
    if not ids:
        return Outcome.fail(
            'R8_NO_SCORABLE_PLAYER',
            f'all {len(players)} player(s) fall in the unsupported cell',
            n_declined=len(declined))
    p = A.predict(f.value['model'], rowsX)
    out = {pid: float(v) for pid, v in zip(ids, p)}
    return Outcome.ok(
        'R8_APPEARANCE_PREDICTED', value=out, spec_version=SPEC_VERSION,
        test_only=False, n_players=len(out), n_declined=len(declined),
        declined=declined, states=dict(states),
        coef_sha256=f.value['coef_sha256'],
        clock=clock.isoformat(), depth=depth_ev,
        reliability_weight_mean=round(float(np.mean(ws)), 6),
        reliability_weight_max=round(float(np.max(ws)), 6),
        n_with_a_depth_listing=sum(1 for q in players
                                   if depth.get(q.get('gsis_id'))),
        p_mean=float(np.mean(p)), p_min=float(np.min(p)),
        p_max=float(np.max(p)), **f.value['evidence'])
