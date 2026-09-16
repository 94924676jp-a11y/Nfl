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
import gzip
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
            kickoff_utc=None, depth=None, extra_rows=None) -> Outcome:
    """Per-player P(appear). The refused cell is declined, exactly as in R7.

    `extra_rows` IS ADDITIVE AND OPT-IN, so every caller that does not pass it
    gets the identical numbers R8 has always produced. With `None` -- which is
    every frozen arm -- nothing below this line executes.

    WHAT IT IS FOR. R8's prospective row is assembled from `hist[pid]`, the
    frame rows for that player, and the frame stops at 2025 week 18, a
    league-wide rest week. So a week-2 2026 forecast asked R8 "what did he do
    most recently" and R8 answered with a game half the league sat out. The
    2026 week-1 rows exist and are observed; appending them to the frame is
    the whole repair.

    WHY NOT JUST USE THE FROZEN MECHANISM'S INJECTION. Because that mechanism
    is the one R8 replaced. Forward-chained 2022-2025 on identical rows, weeks
    2-4: frozen Brier 0.18146, R8 0.10049, n = 7,709, team-week-blocked
    interval excluding zero. Handing the current data only to the losing model
    is a choice between information and mechanism that nobody has to make.

    THE COEFFICIENTS CANNOT MOVE. `fit` trains on `r['s'] < season`, so a 2026
    row never reaches a 2026 fit. This adds history to a fitted model and
    refits nothing; `coef_sha256` is identical with and without it.

    THE CLOCK IS ENFORCED HERE, not trusted from the caller. Only rows in the
    forecast season and STRICTLY EARLIER than the forecast week are admitted.
    A row from the week being forecast would be the outcome being predicted.
    """
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
    inj_ev = None
    if extra_rows:
        need = ('s', 'w', 't', 'pid', 'appeared')
        kept, refused = [], collections.Counter()
        for r in extra_rows:
            if any(r.get(k) is None for k in need):
                refused['MISSING_A_REQUIRED_FIELD'] += 1
                continue
            if int(r['s']) != int(season):
                refused['NOT_THE_FORECAST_SEASON'] += 1
                continue
            if int(r['w']) >= int(week):
                # THE ROW BEING FORECAST IS NOT EVIDENCE ABOUT ITSELF.
                refused['AT_OR_AFTER_THE_FORECAST_WEEK'] += 1
                continue
            kept.append({'s': int(r['s']), 'w': int(r['w']), 't': r['t'],
                         'pid': r['pid'], 'appeared': int(r['appeared']),
                         'snap': r.get('snap')})
        if not kept:
            return Outcome.fail(
                'R8_EXTRA_ROWS_ALL_REFUSED',
                f'{len(extra_rows)} injected row(s) were offered and none '
                f'survived the clock and completeness checks: '
                f'{dict(refused)}. An injection that adds nothing is an '
                f'error, not a no-op -- it would look exactly like the '
                f'uninjected arm while claiming to be a different one.',
                refused=dict(refused), n_offered=len(extra_rows))
        touched = set()
        for r in kept:
            hist[r['pid']].append(r)
            cur[r['pid']].append(r)
            touched.add(r['pid'])
        # RE-SORTED, NOT ASSUMED. `past[-1]` is read as "his most recent
        # game", so an appended row that is not last would silently answer a
        # different question.
        for pid in touched:
            hist[pid].sort(key=lambda x: (int(x['s']), int(x['w'])))
            cur[pid].sort(key=lambda x: (int(x['s']), int(x['w'])))
        inj_ev = {
            'spec': 'r8-frame-injection-1',
            'n_offered': len(extra_rows), 'n_admitted': len(kept),
            'n_refused': dict(refused),
            'n_players_touched': len(touched),
            'weeks_admitted': sorted({r['w'] for r in kept}),
            'n_with_a_snap_share':
                sum(1 for r in kept if r.get('snap') is not None),
            'coefficients_unchanged': True,
            'clock': f'season == {int(season)} and week < {int(week)}, '
                     f'enforced here rather than trusted from the caller'}

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
        frame_injection=inj_ev,
        clock=clock.isoformat(), depth=depth_ev,
        reliability_weight_mean=round(float(np.mean(ws)), 6),
        reliability_weight_max=round(float(np.max(ws)), 6),
        n_with_a_depth_listing=sum(1 for q in players
                                   if depth.get(q.get('gsis_id'))),
        p_mean=float(np.mean(p)), p_min=float(np.min(p)),
        p_max=float(np.max(p)), **f.value['evidence'])


# ======================================================================
# P1 / R10. THE TWO APPEARANCE-PATH REPAIRS FROM AUTOPSY_DEN_KC SECTION 4.
#
# EVERYTHING ABOVE THIS LINE IS UNTOUCHED AND STAYS THAT WAY. R8 is frozen
# lineage: `V1_CANDIDATE_R8` and `V1_CANDIDATE_R9` both run `featurise`,
# `fit` and `predict` above, and their fitted coefficients must not move
# because of work done here. R10 is a SUCCESSOR, not an edit -- the same
# shape as R9 replacing the quarterback room while `qb3_lib` stayed frozen.
#
# REPAIR 1 -- `f_weeks_since_appear` was a value with no missingness flag,
# encoded through a FALSY test.
#
#     f.append(min(v or 9, 9) / 9.0)
#
# All twelve V1_NUMERIC features carry a value AND a flag; this one carried
# neither. `v or 9` fires on None AND on 0, so "never appeared", "appeared in
# the most recent game" and "gone for nine games" are one number, 1.0000,
# while "missed exactly one game" is 0.1111. The encoding is therefore not
# monotone in its own quantity.
#
# Measured on the union frame (n=59,742): the value is 1-based, so 0 never
# occurs in stored data -- the 0 collision is a latent hazard rather than an
# occurring one, and it is repaired structurally rather than argued away. The
# collision that DOES occur is None against 9+: 1,273 rows carry None and
# appear at rate 1.0000, 11 rows carry 9-11 and appear at rate 0.5455, and
# the design row cannot tell them apart. That is what put +1.2600 of logit on
# a back with no NFL history and -0.2785 on one with 68 games.
#
# The repair is the treatment every other numeric already gets: value, then
# flag, with an explicit `is None` test and a monotone encoding in which a
# player who appeared in the most recent game sits at the MINIMUM.
#
# REPAIR 2 -- the depth ordinal was offence-wide in the daily era and
# within-position in the weekly era, in one column of one design row.
#
#     weekly era (2020-2024, n=48,543)  r1 0.8930  r2 0.7018  r3 0.5186
#     daily  era (2025,      n=11,199)  r1 0.9136  r2 0.9357  r3 0.8805
#
# The daily era's top three buckets are flat because they are not roles --
# they are the three alphabetically-first `pos_rank == 1` players on the
# club. `depth_vintage` now SUPPLIES a within-position scale beside the
# offence-wide one rather than replacing it, and R10 consumes that scale on
# both sides of the fit. On it the same 2025 rows give 0.9139 / 0.7451 /
# 0.6425 / 0.3720 / 0.0596, monotone and on the weekly era's footing.
#
# BOTH REPAIRS CHANGE THE DESIGN MATRIX, SO R10 REFITS. That is why they are
# one candidate and not two: a run carrying one of them is not a control for
# the other.
SPEC_VERSION_R10 = 'appearance-r10-monotone-weeks-and-within-position-rank-1'

# The rank scale R10 is fitted on and served on. Named once so the fit and
# the forecast cannot drift apart -- a model fitted on one scale and served
# on another is exactly the train/serve break repair 2 is about.
RANK_SCALE_R10 = DV.WITHIN_POSITION

_FRAME_R10 = {}
_FIT_R10 = {}


def within_position_overlay(rows) -> Outcome:
    """{(s, w, t, pid): within-position ordinal} for the daily-vendor rows.

    Built from the SAME leaf and the SAME point-in-time selection R7's frame
    used, so the only thing that differs from `r['rank']` is the scale. A row
    the offence-wide scale listed and this one does not would mean the two
    disagree about who is on the chart, which is a different claim entirely
    and is refused by name rather than filled in.
    """
    if not R7.DAILY_LEAF.exists():
        return Outcome.blocked(
            'R10_DAILY_LEAF_MISSING',
            f'{R7.DAILY_LEAF} is absent, so the daily-vendor seasons carry no '
            f'within-position rank and the successor would silently fall back '
            f'to the offence-wide ordinal it exists to replace',
            cause=Cause.DATA)
    dy = DV.daily(gzip.open(R7.DAILY_LEAF, 'rt').read(), scale=RANK_SCALE_R10)
    if dy.state is not State.PASS:
        return dy
    M, A, F = AM._frozen()
    kick = A.kickoffs()
    chart, over = {}, {}
    n_daily = n_listed_old = n_listed_new = 0
    no_chart = []
    for r in rows:
        if r.get('vendor') != DV.DAILY_VENDOR:
            continue
        n_daily += 1
        key = (r['s'], r['w'], r['t'])
        if key not in chart:
            k = kick.get(key)
            pit = DV.daily_point_in_time(dy.value, r['t'], k) if k else None
            chart[key] = (pit.value if (pit is not None
                                        and pit.state is State.PASS) else None)
            if chart[key] is None:
                no_chart.append({'season': key[0], 'week': key[1],
                                 'team': key[2],
                                 'code': 'NO_KICKOFF' if pit is None
                                         else pit.code})
        m = chart[key]
        if r.get('rank') is not None:
            n_listed_old += 1
        if m is None:
            continue
        v = m.get(r['pid'])
        if v is not None:
            over[(r['s'], r['w'], r['t'], r['pid'])] = int(v[0])
            n_listed_new += 1
    if n_daily and not over:
        return Outcome.fail(
            'R10_OVERLAY_EMPTY',
            f'{n_daily} daily-vendor frame row(s) produced no within-position '
            f'rank at all; an empty overlay is an error, not a result')
    if n_listed_old != n_listed_new:
        return Outcome.fail(
            'R10_OVERLAY_LISTEDNESS_DISAGREES',
            f'{n_listed_old} frame row(s) carry an offence-wide depth rank '
            f'but {n_listed_new} carry a within-position one. The repair '
            f're-ranks players; it must not re-list them, and a difference '
            f'here means the two scales disagree about who is on the chart',
            n_listed_offence_wide=n_listed_old,
            n_listed_within_position=n_listed_new)
    return Outcome.ok(
        'R10_OVERLAY_OK', value=over, spec_version=SPEC_VERSION_R10,
        rank_scale=RANK_SCALE_R10, n_daily_rows=n_daily,
        n_listed=n_listed_new, n_team_weeks=len(chart),
        n_team_weeks_without_a_lawful_chart=len(no_chart),
        team_weeks_without_a_lawful_chart=no_chart[:10],
        leaf=str(R7.DAILY_LEAF.relative_to(_REPO)),
        rank_1_position_mix=dy.evidence.get('rank_1_position_mix'))


def enriched_frame_r10() -> Outcome:
    """R8's frame with the depth rank restated on ONE scale, in a new key.

    `rank` is left exactly as it was, because R7, R8 and `pool_audit` read it
    and a successor does not get to move a quantity its predecessors are still
    serving. The within-position value lands in `rank_pos`, and rows are
    COPIED rather than annotated so nothing above this line can see it.

    The weekly vendor needs no overlay: `depth_vintage.weekly` already groups
    inside (season, week, club, normalised position), so its rank is the
    within-position quantity on both scales. Only the daily vendor's ordinal
    was offence-wide.
    """
    _fp = R7._dependency_fingerprint()
    if _FRAME_R10.get('rows') and _FRAME_R10.get('fingerprint') == _fp:
        _ev = dict(_FRAME_R10['evidence'])
        _ev['fingerprint'] = _fp
        return Outcome.ok('R10_FRAME_CACHED', value=_FRAME_R10['rows'],
                          spec_version=SPEC_VERSION_R10, cached=True, **_ev)
    if _FRAME_R10.get('rows'):
        _FRAME_R10.clear()
    fr = enriched_frame()
    if fr.state is not State.PASS:
        return fr
    ov = within_position_overlay(fr.value)
    if ov.state is not State.PASS:
        return ov
    rows, n_weekly, n_daily, n_unlisted = [], 0, 0, 0
    for r in fr.value:
        q = dict(r)
        if q.get('vendor') == DV.DAILY_VENDOR:
            q['rank_pos'] = ov.value.get((q['s'], q['w'], q['t'], q['pid']))
            n_daily += 1
        else:
            q['rank_pos'] = q.get('rank')
            n_weekly += 1
        if q['rank_pos'] is None:
            n_unlisted += 1
        rows.append(q)
    n_moved = sum(1 for a, b in zip(fr.value, rows)
                  if a.get('rank') != b.get('rank_pos'))
    ev = {kk: vv for kk, vv in fr.evidence.items()
          if kk not in ('cached', 'spec_version', 'value', 'fingerprint')}
    ev['rank_scale'] = RANK_SCALE_R10
    ev['n_rows'] = len(rows)
    ev['n_weekly_vendor_rows_already_within_position'] = n_weekly
    ev['n_daily_vendor_rows_rescaled'] = n_daily
    ev['n_rows_with_no_depth_listing'] = n_unlisted
    ev['n_rows_whose_depth_rank_moved'] = n_moved
    ev['overlay'] = {k: v for k, v in ov.evidence.items()
                     if k not in ('value', 'spec_version')}
    ev['rank_is_not_mutated'] = (
        "`rank` is untouched on every row; the within-position value is a "
        "new key, `rank_pos`, and only R10's featuriser reads it")
    _FRAME_R10['rows'], _FRAME_R10['evidence'] = rows, ev
    _FRAME_R10['fingerprint'] = _fp
    return Outcome.ok('R10_FRAME_OK', value=rows,
                      spec_version=SPEC_VERSION_R10, cached=False, **ev)


def featurise_r10(r, k):
    """R8's design row with the two repairs, and nothing else changed.

    Deliberately a copy of `featurise` rather than a call into it: R8's
    featuriser is served by two frozen candidate modes, and a successor that
    reaches inside it to change a column is an edit wearing a new name.
    """
    if 'rank_pos' not in r:
        raise ValueError(
            'R10_RANK_SCALE_MISSING: this row carries no `rank_pos`, so the '
            'within-position depth rank is unavailable and the only value to '
            'hand the depth bucket would be the offence-wide ordinal this '
            'model exists to stop consuming. Build rows through '
            'enriched_frame_r10() or predict_r10().')
    # REPAIR 2, applied to BOTH depth blocks through one substitution. R7's
    # featuriser reads `rank`, so it is handed a row whose rank IS the
    # within-position ordinal; the original row is not modified.
    rr = dict(r)
    rr['rank'] = r['rank_pos']
    f = list(R7.featurise(rr))
    w = weight(rr.get('n_cur'), k)
    f.append(w)
    f.append(1.0 - w)
    for key in ('app_cur', 'app_ewma_cur', 'rate3_cur', 'snap_ewma_cur'):
        v = rr.get(key)
        f.append(0.0 if v is None else w * float(v))
        f.append(1.0 if v is None else 0.0)
    f.append(min(rr.get('n_cur') or 0, 12) / 12.0)
    rk = rr.get('rank')
    bucket = ('unlisted' if rk is None else
              ('r1' if rk == 1 else 'r2' if rk == 2 else
               'r3' if rk == 3 else 'r4plus'))
    for b in ('r1', 'r2', 'r3', 'r4plus', 'unlisted'):
        f.append((1.0 - w) if bucket == b else 0.0)
    blk = rr.get('v1') or {}
    for key in V1_NUMERIC:
        v = blk.get(key)
        f.append(0.0 if v is None else float(v))
        f.append(1.0 if v is None else 0.0)
    # REPAIR 1. VALUE THEN FLAG, LIKE EVERY OTHER NUMERIC IN THIS BLOCK.
    #
    # `is None` and not a falsy test, so a real 0 is a real 0. The value is
    # non-decreasing in weeks-since-appear across the whole range and 0 sits
    # at the minimum, which is the direction the quantity actually runs: a
    # player who appeared in the most recent game is the LEAST overdue. The
    # negative branch of the clamp cannot fire on stored data -- the quantity
    # is 1-based -- and is there so that a generator change cannot fold a
    # future value back onto an existing one silently.
    v = blk.get('f_weeks_since_appear')
    f.append(0.0 if v is None else min(max(float(v), 0.0), 9.0) / 9.0)
    f.append(1.0 if v is None else 0.0)
    f.append(min(float(blk.get('f_n_teammates_out') or 0.0), 3.0) / 3.0)
    f.append(float(blk.get('f_practice_improving') or 0.0))
    f.append(float(blk.get('f_practice_worsening') or 0.0))
    f.append(1.0 if rr.get('v1') is None else 0.0)
    return f


N_FEATURES_R10 = len(featurise_r10(
    {'w': 1, 'pos': 'WR', 'rank': 1, 'rank_pos': 1, 'n_cur': 0}, 1.2))


def fit_r10(season: int, l2=1.0) -> Outcome:
    """R8's fit procedure on R10's design row. Its own cache, its own hash."""
    key = (int(season), float(l2))
    if key in _FIT_R10:
        m = _FIT_R10[key]
        return Outcome.ok('R10_FIT', value=m, spec_version=SPEC_VERSION_R10,
                          cached=True, **m['evidence'])
    fr = enriched_frame_r10()
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
            'R10_FRAME_EMPTY',
            f'no frame row earlier than {season} survived the '
            f'unsupported-cell exclusion; a fit on nothing is not a fit')
    X = [featurise_r10(r, k) for r in train]
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
          'rank_scale': RANK_SCALE_R10,
          'repairs': ('f_weeks_since_appear carries a missingness indicator '
                      'and a monotone encoding; the depth rank is '
                      'within-position on both sides of the fit'),
          'no_week_number_in_the_design':
              'the regime moves with n_cur, not with the calendar'}
    m = {'model': model, 'k': k, 'evidence': ev,
         'coef_sha256': hashlib.sha256(
             np.asarray(model['w']).tobytes()).hexdigest()[:16]}
    _FIT_R10[key] = m
    return Outcome.ok('R10_FIT', value=m, spec_version=SPEC_VERSION_R10,
                      cached=False, **ev)


def predict_r10(season, week, players, injuries_rows, observed_before=None,
                kickoff_utc=None, depth=None, depth_scale=None) -> Outcome:
    """Per-player P(appear) under R10. Every R7 and R8 refusal is inherited.

    A caller-supplied depth chart must NAME ITS SCALE. Accepting one silently
    is how a model fitted on within-position ranks ends up served an
    offence-wide ordinal in the same column -- the train/serve break this
    candidate exists to close, reintroduced through a keyword argument.
    """
    fr = enriched_frame_r10()
    if fr.state is not State.PASS:
        return fr
    f = fit_r10(season)
    if f.state is not State.PASS:
        return f
    k = f.value['k']
    M, A, F = AM._frozen()

    clock = R7._parse(observed_before) or R7._parse(kickoff_utc)
    if clock is None:
        return Outcome.fail(
            'R10_NO_CLOCK',
            'neither observed_before nor kickoff_utc was supplied, so the '
            'depth chart could not be selected point-in-time and the newest '
            'capture would have been used by default')
    if depth is None:
        teams = sorted({q.get('team') for q in players if q.get('team')})
        if not teams:
            return Outcome.fail('R10_NO_TEAMS', 'no player carries a team')
        cap = DV.captured(teams, clock, scale=RANK_SCALE_R10)
        if cap.state is not State.PASS:
            return cap
        depth = cap.value
        depth_ev = {kk: vv for kk, vv in cap.evidence.items() if kk != 'value'}
    else:
        if depth_scale != RANK_SCALE_R10:
            return Outcome.fail(
                'R10_DEPTH_SCALE_UNDECLARED',
                f'a depth chart was supplied with depth_scale='
                f'{depth_scale!r}; R10 is fitted on {RANK_SCALE_R10!r} and '
                f'will not consume a chart that does not declare that scale. '
                f'An offence-wide ordinal in this column is the defect, not '
                f'a fallback.',
                required=RANK_SCALE_R10, supplied=str(depth_scale))
        depth_ev = {'source': 'supplied_by_caller',
                    'rank_scale_name': depth_scale}

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
                'R10_IDENTITY_UNRESOLVED',
                'a player carries no gsis_id; fuzzy name matching is forbidden')
        d = depth.get(pid)
        past = hist.get(pid) or []
        cpast = cur.get(pid) or []
        rk = (d[0] if d else None)
        r = {'s': int(season), 'w': int(week), 't': q.get('team'), 'pid': pid,
             'pos': R7._pos(q.get('position')), 'appeared': None,
             'rank': rk, 'rank_pos': rk, 'vendor': DV.DAILY_VENDOR,
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
        rowsX.append(featurise_r10(r, k))
        ids.append(pid)
        ws.append(weight(r['n_cur'], k))
    if not ids:
        return Outcome.fail(
            'R10_NO_SCORABLE_PLAYER',
            f'all {len(players)} player(s) fall in the unsupported cell',
            n_declined=len(declined))
    p = A.predict(f.value['model'], rowsX)
    out = {pid: float(v) for pid, v in zip(ids, p)}
    return Outcome.ok(
        'R10_APPEARANCE_PREDICTED', value=out, spec_version=SPEC_VERSION_R10,
        test_only=False, n_players=len(out), n_declined=len(declined),
        declined=declined, states=dict(states),
        coef_sha256=f.value['coef_sha256'],
        clock=clock.isoformat(), depth=depth_ev,
        # `rank_scale` is NOT repeated here: the fit's own evidence already
        # carries it and it must be the fit's value, not a second one written
        # beside it. Two spellings of one fact is how a served model and its
        # artifact come to disagree.
        reliability_weight_mean=round(float(np.mean(ws)), 6),
        reliability_weight_max=round(float(np.max(ws)), 6),
        n_with_a_depth_listing=sum(1 for q in players
                                   if depth.get(q.get('gsis_id'))),
        p_mean=float(np.mean(p)), p_min=float(np.min(p)),
        p_max=float(np.max(p)), **f.value['evidence'])


# ====================================================== REST fix B
#
# ONE BINARY COLUMN, NO THRESHOLDS, NO PLAYER LIST. Pre-registered in
# `nfl/research/rest/predeclaration_rest.md` before it was built, alongside the
# threshold-based deletion it was preferred over -- that alternative's three
# cuts were chosen while looking at Josh Allen and James Cook, which makes them
# fitted constants with no derivation.
#
# The defect it is aimed at, measured on the frozen mechanism over five season
# transitions, weeks 1-4: an established starter who SAT the last regular week
# is under-predicted by 0.0332 while the PLAYED control is over-predicted by
# 0.0355, a differential of -0.0688 with a team-blocked 95% interval of
# [-0.1133, -0.0256].
#
# THIS IS AN EXPLICIT MECHANISM CHANGE and therefore refits. R8's coefficients
# are untouched and are still what R8 and R9 serve; this is a successor
# lineage, not an edit.
SPEC_VERSION_REST = 'appearance-rest1-prev-was-last-regular-week'


def annotate_rest(rows):
    """Set `prev_was_last_regular_week` on every row, in place.

    1 when the player's IMMEDIATELY PRECEDING frame row is the final
    regular-season week of its own season, 0 otherwise. Nothing else: no rank
    cut, no snap cut, no appearance cut. Whether the sit matters, and by how
    much, is what the fit is being asked.

    The last week is READ FROM THE FRAME rather than assumed to be 17 or 18.
    2020 ends at week 17 and every later season at 18, and hardcoding either
    would silently mislabel a sixth of the corpus.
    """
    last = {}
    for r in rows:
        s = int(r['s'])
        if int(r['w']) > last.get(s, 0):
            last[s] = int(r['w'])
    prev = {}
    for r in sorted(rows, key=lambda x: (int(x['s']), int(x['w']))):
        p = prev.get(r['pid'])
        r['prev_was_last_regular_week'] = (
            1.0 if p is not None and int(p['w']) == last.get(int(p['s']))
            else 0.0)
        prev[r['pid']] = r
    return rows, last


def featurise_rest(r, k):
    """R8's design row plus the one column. Order is append-only on purpose:
    every existing coefficient keeps its position, so a diff of the two weight
    vectors is readable."""
    f = list(featurise(r, k))
    f.append(float(r.get('prev_was_last_regular_week') or 0.0))
    return f


_FIT_REST = {}


def fit_rest(season: int, l2=1.0) -> Outcome:
    """Same frame, same exclusion, same l2, same k. One extra column."""
    key = (int(season), float(l2))
    if key in _FIT_REST:
        m = _FIT_REST[key]
        return Outcome.ok('REST_FIT', value=m,
                          spec_version=SPEC_VERSION_REST, cached=True,
                          **m['evidence'])
    fr = enriched_frame()
    if fr.state is not State.PASS:
        return fr
    rows, last = annotate_rest(list(fr.value))
    ko = reliability_k(rows, cut=int(season) * 100)
    if ko.state is not State.PASS:
        return ko
    k = ko.value
    M, A, F = AM._frozen()
    train = [r for r in rows if r['s'] < season and not is_unsupported(r)]
    if not train:
        return Outcome.fail(
            'REST_FRAME_EMPTY',
            f'no frame row earlier than {season} survived the exclusion')
    X = [featurise_rest(r, k) for r in train]
    y = [r['appeared'] for r in train]
    model = A.fit_logistic(X, y, l2=l2)
    n_flag = sum(1 for r in train if r.get('prev_was_last_regular_week'))
    ev = {'n_train_rows': len(train), 'n_features': len(X[0]),
          'n_rows_carrying_the_flag': n_flag,
          'flag_rate': round(n_flag / len(train), 6),
          'last_regular_week_per_season': dict(sorted(last.items())),
          'train_seasons': sorted({r['s'] for r in train}),
          'base_rate': float(np.mean(y)), 'l2': l2, 'k': round(k, 6),
          'coef_rest': float(np.asarray(model['w'])[-1]),
          'inherits': 'R8, append-only: every prior coefficient keeps its '
                      'column index'}
    m = {'model': model, 'k': k, 'evidence': ev, 'rows': rows,
         'coef_sha256': hashlib.sha256(
             np.asarray(model['w']).tobytes()).hexdigest()[:16]}
    _FIT_REST[key] = m
    return Outcome.ok('REST_FIT', value=m, spec_version=SPEC_VERSION_REST,
                      cached=False, **ev)


# ====================================================== REST2 -- interaction
#
# Pre-registered in `nfl/research/rest/predeclaration_rest2.md` BEFORE it was
# built. Fix B is withdrawn and preserved; this is a successor identity, and
# `featurise` / `fit` / `predict` above are untouched.
#
# WHY A MAIN EFFECT COULD NOT WORK, in one sentence: it nudges the player who
# sat and the player who played by the same amount, so it cannot move the gap
# BETWEEN them, which is exactly what fix B's numbers showed.
#
# FOUR COLUMNS, NO THRESHOLDS. The continuous `prev_snap` is the whole point --
# it is what makes the rank<=3 / snap>=0.50 / snap<=0.10 cuts unnecessary, and
# those cuts were chosen while looking at two players, which is why they are
# confined to the measurement signature the model never sees.
SPEC_VERSION_REST2 = 'appearance-rest2-boundary-x-participation'
N_REST2_COLUMNS = 4


def annotate_rest2(rows):
    """`prev_was_last_regular_week`, plus WHAT HE DID in that game.

    `prev_snap` is the `snap` field of the immediately preceding frame row --
    the same quantity `snap_ewma_cur` is built from, read directly rather than
    aggregated. A chart-added row has no snap share and that is NOT a zero, so
    it carries its own missingness companion.
    """
    rows, last = annotate_rest(rows)
    prev = {}
    for r in sorted(rows, key=lambda x: (int(x['s']), int(x['w']))):
        p = prev.get(r['pid'])
        r['prev_appeared_row'] = (None if p is None else int(p['appeared']))
        r['prev_snap'] = (None if p is None else p.get('snap'))
        prev[r['pid']] = r
    return rows, last


def featurise_rest2(r, k):
    """R8's design row plus the four pre-registered columns, append-only so
    every existing coefficient keeps its index and a weight diff is readable."""
    f = list(featurise(r, k))
    L = float(r.get('prev_was_last_regular_week') or 0.0)
    pa = r.get('prev_appeared_row')
    ps = r.get('prev_snap')
    f.append(L)                                             # 1. main effect
    f.append(L * (0.0 if pa is None else float(pa)))        # 2. x appeared
    f.append(L * (0.0 if ps is None else float(ps)))        # 3. x snap share
    f.append(L * (1.0 if ps is None else 0.0))              # 4. x missing
    return f


REST2_COLUMN_NAMES = ('L', 'L_x_prev_appeared', 'L_x_prev_snap',
                      'L_x_prev_snap_missing')

_FIT_REST2 = {}


def fit_rest2(season: int, l2=1.0) -> Outcome:
    """Same frame, same exclusion, same l2, same k as R8. Four extra columns,
    every one of them zero wherever L is zero -- so no row is added, removed or
    reweighted relative to the arm this is measured against."""
    key = (int(season), float(l2))
    if key in _FIT_REST2:
        m = _FIT_REST2[key]
        return Outcome.ok('REST2_FIT', value=m,
                          spec_version=SPEC_VERSION_REST2, cached=True,
                          **m['evidence'])
    fr = enriched_frame()
    if fr.state is not State.PASS:
        return fr
    rows, last = annotate_rest2(list(fr.value))
    ko = reliability_k(rows, cut=int(season) * 100)
    if ko.state is not State.PASS:
        return ko
    k = ko.value
    M, A, F = AM._frozen()
    train = [r for r in rows if r['s'] < season and not is_unsupported(r)]
    if not train:
        return Outcome.fail(
            'REST2_FRAME_EMPTY',
            f'no frame row earlier than {season} survived the exclusion')
    X = [featurise_rest2(r, k) for r in train]
    y = [r['appeared'] for r in train]
    model = A.fit_logistic(X, y, l2=l2)
    flagged = [r for r in train if r.get('prev_was_last_regular_week')]
    w = np.asarray(model['w'], float)
    ev = {'n_train_rows': len(train), 'n_features': len(X[0]),
          'n_rows_carrying_the_flag': len(flagged),
          'n_flagged_that_appeared': sum(1 for r in flagged
                                         if r.get('prev_appeared_row')),
          'n_flagged_without_a_snap_share': sum(
              1 for r in flagged if r.get('prev_snap') is None),
          'last_regular_week_per_season': dict(sorted(last.items())),
          'train_seasons': sorted({r['s'] for r in train}),
          'base_rate': float(np.mean(y)), 'l2': l2, 'k': round(k, 6),
          'coefs': {n: float(v) for n, v in
                    zip(REST2_COLUMN_NAMES, w[-N_REST2_COLUMNS:])},
          'inherits': 'R8, append-only; R8`s own coefficients are untouched '
                      'and still served by fit()'}
    m = {'model': model, 'k': k, 'evidence': ev, 'rows': rows,
         'coef_sha256': hashlib.sha256(w.tobytes()).hexdigest()[:16]}
    _FIT_REST2[key] = m
    return Outcome.ok('REST2_FIT', value=m, spec_version=SPEC_VERSION_REST2,
                      cached=False, **ev)
