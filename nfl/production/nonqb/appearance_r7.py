"""R7 appearance: the same estimator, on a frame that is not right-censored.

THE DEFECT THIS EXISTS FOR

`model.extend_with_zeros` builds the candidate set for a team-game from the
players who APPEARED in that team's previous `LOOKBACK_CANDIDATE = 4` games.
A player absent for four straight games therefore leaves the candidate set and
can only re-enter it by playing. The absence distribution is right-censored at
exactly the lookback, and the censoring point sits inside the range the
featuriser encodes (`min(f_consec_missed, 5) / 5`).

Measured on the frozen panel, 83,144 rows:

    f_consec_missed   0      1      2      3      4      5+
    appearance rate  .825   .406   .201   .165   .958   .43
    non-appearing    10360   6091   4813   3987    109    114

The relationship is monotone and steep to 3 and then INVERTS at 4, where 2,454
of 2,563 rows are appearances. The model is not misreading absence; it is
reading a training set in which long absence is, by construction, a marker of
having played. That is the appearance inversion, and no coefficient change
fixes it because the defect is in the frame.

THE REPAIR IS THE FRAME

A depth chart lists a team's players whether or not they play, so it supplies
the denominator the panel lacks. Union the panel with the point-in-time depth
listing and the censoring largely lifts:

    cm (union frame) 0      1      2      3      4      5      8+
    appearance rate  .737   .555   .252   .169   .363   .418   .134
    non-appearing    6887   3079   2298   1911   1056    480   1434

The residual bump at 4-5 is honest and is stated rather than smoothed: a player
who is off the depth chart AND has no panel row still produces no row, so the
tail is reduced, not eliminated.

WHAT IS NOT ESTIMABLE, AND IS REFUSED

A player with no prior frame row and no depth listing enters the frame only by
appearing. Measured 2021-2025: appearance rate 1.0000 with zero variance at
every position. That is not a high probability, it is a degenerate estimator,
and fitting through it would rebuild the inversion in a new place. Rows in that
cell are DROPPED from the fit and players in that cell are DECLINED at
prediction time by name. The caller keeps the control's number for them and
counts how many there were.

THE SEASON BOUNDARY INVERTS, IT DOES NOT DECAY

Within a season the streak is monotone (.722 / .504 / .206 / .178). Carried
across the offseason at depth rank 1 it runs the OTHER WAY -- streak 0 appears
0.7765 (n=85) against 0.9515 for streak 1-2 (n=722) -- because resting a
week-18 starter is a marker of a good team, not of an injury. So the streak is
reset at the boundary, the carried value is kept as a SEPARATE feature that
only fires when the boundary was crossed, and a week-1 indicator lets the
regime have its own intercept. A flat reset-to-zero would have thrown the
carried signal away; carrying it through unchanged inverts it.

NOTHING ELSE MOVES. The estimator is `stage_a.fit_logistic`, imported, not
restated. QB allocation does not pass through this layer at all
(`qb_accounting.py:377`). Team volume, efficiency, conversion and the R6 role
prior are untouched.
"""
from __future__ import annotations

import collections
import datetime as dt
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
from nfl.production.nonqb import depth_vintage as DV  # noqa: E402

SPEC_VERSION = 'appearance-r7-union-frame-depth-1'
POS = ('QB', 'RB', 'WR', 'TE')
_NORM = {'FB': 'RB', 'HB': 'RB'}
DAILY_LEAF = _REPO / 'nfl' / 'research' / 'inputs' / 'dc25_daily.csv.gz'
DAILY_FIRST_SEASON = 2025

UNSUPPORTED_CELL = 'no_history_and_not_depth_listed'

# Appearance state vocabulary. Three states, kept apart on purpose: "has never
# been seen" is not "has been seen and was well", and neither is "we do not
# know". Collapsing them is what let a camp body outrank a starter.
KNOWN_HEALTHY = 'KNOWN_HEALTHY'
NO_HISTORY = 'NO_HISTORY'
UNKNOWN_STATUS = 'UNKNOWN_STATUS'

_FRAME = {}
_FIT = {}


def _pos(p):
    p = (p or '').upper()
    return _NORM.get(p, p)


def _parse(t):
    if not t:
        return None
    if isinstance(t, dt.datetime):
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)



def _dependency_fingerprint():
    """Content hash of everything build_frame reads. Cheap: two files."""
    import hashlib as _h
    out = _h.sha256()
    for p in (AM.MANIFEST, DAILY_LEAF):
        try:
            out.update(_h.sha256(pathlib.Path(p).read_bytes()).hexdigest()
                       .encode())
        except OSError:
            out.update(b'MISSING')
    return out.hexdigest()[:32]


# ------------------------------------------------------------------ frame
def build_frame() -> Outcome:
    """Panel UNION point-in-time depth listing, walked chronologically.

    The union is the whole repair, so every piece of it is counted in the
    evidence: how many rows the panel contributed, how many the depth chart
    added, and how many team-weeks could not be given a lawful chart.
    """
    # THE CACHE IS KEYED ON ITS DEPENDENCIES, NOT ON NOTHING.
    #
    # This dict was served for the life of the process regardless of what
    # happened underneath it, so a restaged leaf or an edited daily file
    # would have been ignored until the process died. The frame reads only
    # immutable history -- the twelve staged leaves and dc25_daily -- so it
    # is genuinely reusable, but only while those are unchanged.
    _fp = _dependency_fingerprint()
    if _FRAME.get('rows') and _FRAME.get('fingerprint') == _fp:
        return Outcome.ok('R7_FRAME_CACHED', value=_FRAME['rows'],
                          spec_version=SPEC_VERSION, cached=True,
                          fingerprint=_fp, **_FRAME['evidence'])
    if _FRAME.get('rows'):
        _FRAME.clear()
    st = AM.stage_inputs()
    if st.state is not State.PASS:
        return st
    M, A, F = AM._frozen()
    kick = A.kickoffs()
    inj, _ = A.injuries(kick)
    dep = A.depth()
    panel = A.build(kick, inj, dep)

    wk = DV.weekly(st.value)
    if wk.state is not State.PASS:
        return wk
    if not DAILY_LEAF.exists():
        return Outcome.blocked(
            'R7_DAILY_LEAF_MISSING',
            f'{DAILY_LEAF} is absent, so seasons {DAILY_FIRST_SEASON}+ would '
            f'carry no depth listing and the frame would silently revert to '
            f'the censored panel for them', cause=Cause.DATA)
    dy = DV.daily(gzip.open(DAILY_LEAF, 'rt').read())
    if dy.state is not State.PASS:
        return dy

    by_key = {}
    team_weeks = set()
    for r in panel:
        s, w, t, pid = int(r['season']), int(r['week']), r['team'], r['gsis_id']
        if _pos(r.get('position')) not in POS:
            continue
        by_key[(s, w, t, pid)] = {
            's': s, 'w': w, 't': t, 'pid': pid, 'pos': _pos(r.get('position')),
            'appeared': r['appeared'], 'in_panel': True, 'rank': None,
            'vendor': None}
        team_weeks.add((s, w, t))

    wk_ix = collections.defaultdict(dict)
    for (ss, ww, cc, pid), v in wk.value.items():
        wk_ix[(ss, ww, cc)][pid] = v

    by_tw = collections.defaultdict(list)
    for k2 in by_key:
        by_tw[(k2[0], k2[1], k2[2])].append(k2)

    added, no_chart, chart = 0, [], {}
    for (s, w, t) in sorted(team_weeks):
        if s < DAILY_FIRST_SEASON:
            listed = wk_ix.get((s, w, t), {})
            vendor = DV.WEEKLY_VENDOR
        else:
            k = kick.get((s, w, t))
            pit = DV.daily_point_in_time(dy.value, t, k) if k else None
            if pit is None or pit.state is not State.PASS:
                no_chart.append({'season': s, 'week': w, 'team': t,
                                 'code': 'NO_KICKOFF' if pit is None
                                         else pit.code})
                continue
            listed = pit.value
            vendor = DV.DAILY_VENDOR
            chart[(s, w, t)] = pit.evidence['chosen_dt']
        # THE VENDOR TAGS THE TEAM-WEEK, NOT THE LISTED PLAYER. Tagging only
        # listed rows made `unlisted` mean "weekly vendor" in both eras, so the
        # daily-vendor interaction on the unlisted bucket was identically zero
        # and the two eras' unlisted rows shared one intercept. The chart that
        # was consulted is a property of the team-week either way.
        for k2 in by_tw.get((s, w, t), ()):
            by_key[k2]['vendor'] = vendor
        for pid, (rank, pos) in listed.items():
            k2 = (s, w, t, pid)
            if k2 in by_key:
                by_key[k2]['rank'] = rank
                by_key[k2]['vendor'] = vendor
            else:
                by_key[k2] = {'s': s, 'w': w, 't': t, 'pid': pid, 'pos': pos,
                              'appeared': 0, 'in_panel': False, 'rank': rank,
                              'vendor': vendor}
                added += 1

    rows = sorted(by_key.values(), key=lambda r: (r['s'], r['w']))
    _walk(rows, inj)
    ev = {'n_rows': len(rows), 'n_from_panel': len(panel),
          'n_added_by_depth_chart': added,
          'n_team_weeks': len(team_weeks),
          'n_team_weeks_without_a_lawful_chart': len(no_chart),
          'team_weeks_without_a_lawful_chart': no_chart[:10],
          'seasons': sorted({r['s'] for r in rows}),
          'weekly_vendor_seasons': sorted({r['s'] for r in rows
                                           if r['vendor'] == DV.WEEKLY_VENDOR}),
          'daily_vendor_seasons': sorted({r['s'] for r in rows
                                          if r['vendor'] == DV.DAILY_VENDOR}),
          'n_unlisted': sum(1 for r in rows if r['rank'] is None)}
    _FRAME['rows'], _FRAME['evidence'], _FRAME['inj'] = rows, ev, inj
    _FRAME['fingerprint'] = _fp
    return Outcome.ok('R7_FRAME_OK', value=rows, spec_version=SPEC_VERSION,
                      cached=False, **ev)


def _walk(rows, inj):
    """Pregame features from PRIOR frame rows only. Season boundary explicit."""
    hist = collections.defaultdict(list)
    hl = 0.5 ** (1 / 3)
    for r in rows:
        past = hist[r['pid']]
        r['n_prior'] = len(past)
        r['prev_appeared'] = past[-1]['appeared'] if past else None
        r['crossed'] = bool(past) and past[-1]['s'] < r['s']
        cm = 0
        for x in reversed(past):
            if x['s'] != r['s'] or x['appeared']:
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
        if past:
            num = den = 0.0
            ww = 1.0
            for x in reversed(past):
                num += ww * x['appeared']
                den += ww
                ww *= hl
            r['app_ewma'] = num / den
        else:
            r['app_ewma'] = None
        d = inj.get((r['s'], r['w'], r['t'], r['pid']))
        r['inj_status'] = d['report_status'] if d else None
        r['inj_practice'] = d['practice_status'] if d else None
        r['inj_available'] = 1 if d is not None else 0
        r['state'] = state_of(r)
        hist[r['pid']].append(r)
    return rows


def state_of(r) -> str:
    """KNOWN_HEALTHY / NO_HISTORY / UNKNOWN_STATUS -- never collapsed.

    NO_HISTORY is not evidence of availability. UNKNOWN_STATUS is the honest
    label for a player we have seen before but about whom this week says
    nothing: no depth listing and no injury row.
    """
    if not r.get('n_prior'):
        return NO_HISTORY
    if r.get('rank') is None and not r.get('inj_available'):
        return UNKNOWN_STATUS
    return KNOWN_HEALTHY


def is_unsupported(r) -> bool:
    """The cell whose appearance rate is 1.0000 with zero variance."""
    return (not r.get('n_prior')) and r.get('rank') is None


# ------------------------------------------------------------- featurise
STATUS = ('Out', 'Doubtful', 'Questionable')


def featurise(r):
    f = [1.0]
    rk = r.get('rank')
    bucket = ('unlisted' if rk is None else
              ('r1' if rk == 1 else 'r2' if rk == 2 else
               'r3' if rk == 3 else 'r4plus'))
    for b in ('r1', 'r2', 'r3', 'r4plus', 'unlisted'):
        f.append(1.0 if bucket == b else 0.0)
    daily = 1.0 if r.get('vendor') == DV.DAILY_VENDOR else 0.0
    f.append(daily)
    for b in ('r1', 'r2', 'r3', 'r4plus', 'unlisted'):
        f.append(daily if bucket == b else 0.0)
    p = r.get('pos')
    for q in POS:
        f.append(1.0 if p == q else 0.0)
    f.append(1.0 if int(r['w']) == 1 else 0.0)
    f.append(1.0 if r.get('crossed') else 0.0)
    f.append(min(r.get('cm_within') or 0, 4) / 4.0)
    f.append(1.0 if (r.get('cm_within') or 0) == 0 else 0.0)
    f.append(min(r.get('cm_carried') or 0, 4) / 4.0)
    v = r.get('app_ewma')
    f.append(0.0 if v is None else float(v))
    f.append(1.0 if v is None else 0.0)
    v = r.get('prev_appeared')
    f.append(0.0 if v is None else float(v))
    f.append(1.0 if v is None else 0.0)
    f.append(min(r.get('n_prior') or 0, 20) / 20.0)
    f.append(1.0 if (r.get('n_prior') or 0) < 4 else 0.0)
    s = r.get('inj_status')
    for L in STATUS:
        f.append(1.0 if s == L else 0.0)
    f.append(1.0 if (r.get('inj_practice') or '').startswith('Did Not') else 0.0)
    f.append(float(r.get('inj_available') or 0))
    return f


N_FEATURES = len(featurise({'w': 1, 'pos': 'WR', 'rank': 1}))


# -------------------------------------------------------------------- fit
def fit(season: int, l2=1.0) -> Outcome:
    """Fit on frame rows from STRICTLY EARLIER seasons, minus the degenerate cell."""
    key = (int(season), float(l2))
    if key in _FIT:
        m = _FIT[key]
        return Outcome.ok('R7_FIT', value=m, spec_version=SPEC_VERSION,
                          cached=True, **m['evidence'])
    fr = build_frame()
    if fr.state is not State.PASS:
        return fr
    M, A, F = AM._frozen()
    rows = fr.value
    train = [r for r in rows if r['s'] < season]
    late = [r for r in rows if r['s'] >= season]
    if any(r in train for r in late):
        return Outcome.fail('R7_TRAINING_LEAKAGE',
                            'a forecast-season row entered the training set')
    kept = [r for r in train if not is_unsupported(r)]
    dropped = len(train) - len(kept)
    if not kept:
        return Outcome.fail(
            'R7_FRAME_EMPTY',
            f'no frame row earlier than {season} survived the unsupported-cell '
            f'exclusion; a fit on nothing is not a fit', n_train=len(train))
    X = [featurise(r) for r in kept]
    y = [r['appeared'] for r in kept]
    model = A.fit_logistic(X, y, l2=l2)
    p = A.predict(model, X)
    ev = {'n_train_rows': len(kept), 'n_features': len(X[0]),
          'n_dropped_unsupported_cell': dropped,
          'unsupported_cell': UNSUPPORTED_CELL,
          'train_seasons': sorted({r['s'] for r in kept}),
          'in_sample_brier': float(A.brier(y, p)),
          'in_sample_auc': float(A.auc(y, p)),
          'base_rate': float(np.mean(y)), 'l2': l2}
    m = {'model': model, 'evidence': ev,
         'coef_sha256': hashlib.sha256(
             np.asarray(model['w']).tobytes()).hexdigest()[:16]}
    _FIT[key] = m
    return Outcome.ok('R7_FIT', value=m, spec_version=SPEC_VERSION,
                      cached=False, **ev)


# ---------------------------------------------------------------- predict
def predict(season, week, players, injuries_rows, observed_before=None,
            kickoff_utc=None, depth=None) -> Outcome:
    """Per-player P(appear), with the unsupported cell declined by name."""
    fr = build_frame()
    if fr.state is not State.PASS:
        return fr
    f = fit(season)
    if f.state is not State.PASS:
        return f
    M, A, F = AM._frozen()

    clock = _parse(observed_before) or _parse(kickoff_utc)
    if clock is None:
        return Outcome.fail(
            'R7_NO_CLOCK',
            'neither observed_before nor kickoff_utc was supplied, so the '
            'depth chart could not be selected point-in-time and the newest '
            'capture would have been used by default')
    if depth is None:
        teams = sorted({q.get('team') for q in players if q.get('team')})
        if not teams:
            return Outcome.fail(
                'R7_NO_TEAMS',
                'no player carries a team, so no depth chart can be selected')
        cap = DV.captured(teams, clock)
        if cap.state is not State.PASS:
            return cap
        depth = cap.value
        depth_ev = {k: v for k, v in cap.evidence.items() if k != 'value'}
    else:
        depth_ev = {'source': 'supplied_by_caller'}

    inj26 = AM.parse_injuries_rows(injuries_rows, season)
    hist = collections.defaultdict(list)
    for r in fr.value:
        hist[r['pid']].append(r)

    out, declined, states = {}, {}, collections.Counter()
    rowsX, ids = [], []
    for q in players:
        pid = q.get('gsis_id')
        if not pid:
            return Outcome.fail(
                'R7_IDENTITY_UNRESOLVED',
                'a player carries no gsis_id; fuzzy name matching is forbidden')
        d = depth.get(pid)
        r = {'s': int(season), 'w': int(week), 't': q.get('team'), 'pid': pid,
             'pos': _pos(q.get('position')),
             'rank': (d[0] if d else None), 'appeared': None,
             # The chart consulted for 2026 is the daily one whether or not
             # THIS player appears on it, so the vendor tags the row either way.
             'vendor': DV.DAILY_VENDOR}
        past = hist.get(pid) or []
        r['n_prior'] = len(past)
        r['prev_appeared'] = past[-1]['appeared'] if past else None
        r['crossed'] = bool(past) and past[-1]['s'] < int(season)
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
        if past:
            num = den = 0.0
            ww = 1.0
            for x in reversed(past):
                num += ww * x['appeared']
                den += ww
                ww *= 0.5 ** (1 / 3)
            r['app_ewma'] = num / den
        else:
            r['app_ewma'] = None
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
        rowsX.append(featurise(r))
        ids.append(pid)
    if not ids:
        return Outcome.fail(
            'R7_NO_SCORABLE_PLAYER',
            f'all {len(players)} player(s) fall in the unsupported cell; a '
            f'prediction over zero players is not a prediction',
            n_declined=len(declined))
    p = A.predict(f.value['model'], rowsX)
    out = {pid: float(v) for pid, v in zip(ids, p)}
    return Outcome.ok(
        'R7_APPEARANCE_PREDICTED', value=out, spec_version=SPEC_VERSION,
        test_only=False, n_players=len(out), n_declined=len(declined),
        declined=declined, states=dict(states),
        coef_sha256=f.value['coef_sha256'],
        clock=clock.isoformat(), depth=depth_ev,
        n_with_a_depth_listing=sum(1 for q in players
                                   if depth.get(q.get('gsis_id'))),
        p_mean=float(np.mean(p)), p_min=float(np.min(p)),
        p_max=float(np.max(p)), **f.value['evidence'])
