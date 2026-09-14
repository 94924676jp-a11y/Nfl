"""Candidate B appearance: the V1 block recomputed over the candidate universe.

WHAT IS WRONG WITH THE INCUMBENT, IN ONE SENTENCE

`appearance_r8._panel_v1_features` keys the V1 feature block on the rows of the
frozen P3 panel, and the panel holds a row for a player-team-week if and only
if he took a snap (or was a `LOOKBACK_CANDIDATE` zero row). So on the union
frame the block is PRESENT on 53,626 rows whose appearance rate is 0.7119 and
ABSENT on 6,158 rows whose appearance rate is **0.0000, exactly**. Feature
presence is very nearly the label. At serve, `appearance_r8.predict` fills the
block for every player from `AM.prospective_feature_rows`, because at serve
nobody knows who played -- so the column is a constant there. That is
simultaneously leakage and train/serve skew, and it costs, measured:

    arm            Brier    AUC      calibration-in-the-large
    BASE_INFRAME   0.0901   0.9415   +0.0059     (what the leak makes it look like)
    BASE_SERVE     0.1585   0.8237   +0.0890     (what it actually is at serve)

Top-5%-by-prediction, which is the leak in one number: the in-frame arm
predicts 0.99196 and observes 0.98866; the serve-shaped arm predicts 0.99423
and observes **0.57565**.

WHAT THIS MODULE DOES INSTEAD

It rebuilds the V1 block over the **union candidate universe** rather than over
the panel. The panel is extended with one zero-opportunity, panel-shaped row
for every union-frame candidate the panel lacks -- the same row shape
`appearance_model.prospective_rows` builds at serve -- and the frozen
`appearance_model._walk` + `p3_features.enrich` are then run over the extended
panel. Every union frame row carries a block afterwards, so block presence is
a CONSTANT, in training and at serve alike, and a constant column carries no
information about anything including the label.

The featuriser is `appearance_r8.featurise` with its last column removed. That
column is `1.0 if r.get('v1') is None else 0.0` -- the presence indicator --
and under this basis it is identically zero. A constant column is not a
feature. It is removed by SLICING R8's own output, never by restating R8's
featuriser, and `_assert_presence_is_last_column` proves at import that the
sliced column is the one claimed.

AND THE SERVE PATH USES THE SAME BASIS. This is the part that would have been
easy to get wrong. Training on the union basis while serving on the panel basis
would swap one train/serve skew for a subtler one, so `_prospective_union`
extends the panel with the SAME union synthetic rows before appending the
target week's prospective rows. `assert_prospective_matches_frozen` runs the
same code path with the extension switched off and requires the V1 blocks to
come back bit-identical to `appearance_model.prospective_feature_rows`, so the
extension is the only difference between this walk and the accepted one.

WHAT IT DOES NOT FIX, STATED HERE RATHER THAN DISCOVERED LATER

* **The universe is still not the roster.** A union frame row is panel-or-
  depth-listed. A player with history who is not depth-listed and does not play
  still produces no frame row. B narrows the censoring; it does not close it.
  Closing it needs weekly 53-man roster membership for 2020-2025, which is not
  in this checkout.
* **Duplicate player-ordinals.** `appearance_model._walk` orders by `ord`
  alone, so where one player holds two frame rows at the same (season, week) --
  he is listed by two teams in one week -- the first row in list order becomes
  history for the second and its label reaches the second row's features. This
  is a property of the frozen walk and of the union frame key `(s, w, t, pid)`,
  present in R7 and R8 exactly as it is here; B neither introduces nor repairs
  it. It is measured and reported rather than asserted away.
* **Gameday inactives.** No appearance model in this repository reads the
  official inactive list; it is applied a layer later in `layers.py`. B does not
  change that and does not claim to.

NOTHING HERE IS FITTED BY HAND. The estimator is `stage_a.fit_logistic` with
the same `l2` R8 uses, `k` is `appearance_r8.reliability_k` unchanged, and the
featuriser is R8's own minus one constant column. No coefficient, threshold or
cutoff is introduced by this module.

GOVERNANCE. Nothing in this module promotes anything. It is selectable only
through `appearance_arm.py`, which stamps the arm that produced each number
onto the row, and the incumbent stays the default.
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
        sys.path.insert(0, str(_q))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production.nonqb import appearance_model as AM  # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7  # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8  # noqa: E402
from nfl.production.nonqb import depth_vintage as DV  # noqa: E402

SPEC_VERSION = 'appearance-b-union-candidate-universe-1'
PREREG_SHA256 = ('b14738a0a4a262cccba416b6d76e3b80'
                 'db4340b46f1ab144d0546bfe8f368dda')

# Inherited verbatim from R8 so a reader of this file alone still sees what is
# refused and on what vocabulary.
V1_KEYS = R8.V1_NUMERIC + ('f_weeks_since_appear', 'f_n_teammates_out',
                           'f_practice_seq', 'f_practice_improving',
                           'f_practice_worsening')
UNSUPPORTED_CELL = R8.UNSUPPORTED_CELL
is_unsupported = R8.is_unsupported
state_of = R8.state_of

_FRAME = {}
_FIT = {}
_PANEL = {}


class CandidateBError(RuntimeError):
    """A named failure. An empty or partial result is never returned as one."""


# ------------------------------------------------- the featuriser, by slicing
def _assert_presence_is_last_column():
    """R8's last feature column is the V1-presence indicator, and only that.

    Verified against R8's own output, never asserted: a row whose `v1` is None
    and a row whose `v1` is an EMPTY dict take identical paths through every
    other line of `R8.featurise` -- `blk = r.get('v1') or {}` maps both to {} --
    so the two outputs may differ in exactly one position, the last, and must
    differ there.
    """
    a = R8.featurise({'w': 5, 'pos': 'WR', 'rank': 2, 'n_cur': 3,
                      'v1': None}, 1.2)
    b = R8.featurise({'w': 5, 'pos': 'WR', 'rank': 2, 'n_cur': 3,
                      'v1': {}}, 1.2)
    if len(a) != len(b):
        raise CandidateBError('B_FEATURISER_SHAPE_DIFFERS')
    moved = [i for i in range(len(a)) if a[i] != b[i]]
    if moved != [len(a) - 1]:
        raise CandidateBError(
            f'B_PRESENCE_COLUMN_NOT_LAST: columns {moved} moved when only the '
            f'V1-presence indicator should have. Slicing R8.featurise would '
            f'remove the wrong column.')
    if (a[-1], b[-1]) != (1.0, 0.0):
        raise CandidateBError(
            f'B_PRESENCE_COLUMN_NOT_AN_INDICATOR: got {a[-1]}, {b[-1]}')
    return len(a) - 1


N_FEATURES = _assert_presence_is_last_column()


def featurise(r, k):
    """R8's design row minus the V1-presence column, which is constant here.

    R8's featuriser is CALLED and sliced, never restated. A second copy of a
    featuriser is how a production model quietly stops being the accepted one.
    """
    if r.get('v1') is None:
        raise CandidateBError(
            'B_BLOCK_ABSENT: a Candidate B row reached the featuriser with no '
            'V1 block. Under the union basis every row carries one, so an '
            'absent block means the basis was not built, and imputing it here '
            'would restore the defect this candidate exists to remove.')
    return R8.featurise(r, k)[:N_FEATURES]


# --------------------------------------------------------- the union basis
def _panel_and_inputs():
    if _PANEL.get('panel'):
        return _PANEL
    st = AM.stage_inputs()
    if st.state is not State.PASS:
        raise CandidateBError(f'B_INPUTS_UNAVAILABLE {st.code}')
    M, A, F = AM._frozen()
    kick = A.kickoffs()
    inj, _ = A.injuries(kick)
    dep = A.depth()
    panel = A.build(kick, inj, dep)
    if not panel:
        raise CandidateBError('B_PANEL_EMPTY')
    _PANEL.update({'M': M, 'A': A, 'F': F, 'kick': kick, 'inj': inj,
                   'dep': dep, 'panel': panel,
                   'cols': AM._panel_columns(),
                   'in_panel': {(int(r['season']), int(r['week']), r['team'],
                                 r['gsis_id']) for r in panel}})
    return _PANEL


def synthetic_row(s, w, t, pid, pos, cols, did_not_appear):
    """A zero-opportunity panel-shaped row, the shape production builds at serve.

    `appearance_model.prospective_rows` zeroes every integer column and keeps
    only the identity fields and a game_id, so the team_* columns carry zero
    here too. No target-week feature reads a target-week team total -- `f_vac_*`
    reads the PREVIOUS team-week -- so this is the same row production builds.

    `did_not_appear` is 1 for a historical candidate known not to have played
    and None for a game not yet played, which is what serve has.
    """
    z = {c: 0 for c in cols}
    z.update({'season': int(s), 'week': int(w), 'team': t, 'gsis_id': pid,
              'position': pos, 'player_name': pid,
              'game_id': f'{int(s)}_{int(w):02d}_{t}',
              'offense_pct': (0.0 if did_not_appear == 1 else None),
              'did_not_appear': did_not_appear,
              'ord': int(s) * 100 + int(w)})
    return z


def _union_synthetics(union_rows, cols, in_panel):
    """One zero-opportunity row per union candidate the panel does not hold.

    A union row the panel lacks is by construction a player who did NOT take a
    snap that week, so `did_not_appear = 1` is a fact about him and not an
    imputation. If one of them carries `appeared == 1` the frame and the panel
    disagree about who played, which is a named failure rather than something
    to average over.
    """
    missing = [r for r in union_rows
               if (r['s'], r['w'], r['t'], r['pid']) not in in_panel]
    bad = [r for r in missing if r['appeared']]
    if bad:
        raise CandidateBError(
            f'B_UNION_APPEARER_OFF_PANEL: {len(bad)} union frame row(s) are '
            f'marked appeared but hold no panel row; the frame and the panel '
            f'disagree about who played')
    return [synthetic_row(r['s'], r['w'], r['t'], r['pid'], r['pos'], cols, 1)
            for r in missing]


def union_frame() -> Outcome:
    """R8's enriched frame with the V1 block recomputed over the candidate universe.

    The rows are COPIES. `appearance_r8.enriched_frame` returns objects from a
    module-level cache that the incumbent serves from, and mutating `v1` on
    them in place would silently change what the incumbent predicts -- exactly
    the "do not silently replace the incumbent" failure, arrived at by
    aliasing rather than by intent.
    """
    fp = R7._dependency_fingerprint()
    if _FRAME.get('rows') and _FRAME.get('fingerprint') == fp:
        ev = dict(_FRAME['evidence'])
        ev['fingerprint'] = fp
        return Outcome.ok('B_FRAME_CACHED', value=_FRAME['rows'],
                          spec_version=SPEC_VERSION, cached=True, **ev)
    if _FRAME.get('rows'):
        _FRAME.clear()
    fr = R8.enriched_frame()
    if fr.state is not State.PASS:
        return fr
    if not fr.value:
        return Outcome.blocked(
            'B_FRAME_EMPTY', 'the R8 union frame came back with no rows; an '
            'empty frame is an absence, not a basis', cause=Cause.DATA)
    try:
        S = _panel_and_inputs()
        syn = _union_synthetics(fr.value, S['cols'], S['in_panel'])
        walked = AM._walk(S['A'], S['M'],
                          [dict(r) for r in S['panel']] + syn,
                          S['inj'], S['dep'])
        S['F'].enrich(walked, S['inj'])
    except CandidateBError as e:
        return Outcome.fail('B_UNION_BASIS_FAILED', str(e))
    blocks = {}
    for r in walked:
        blocks[(int(r['season']), int(r['week']), r['team'],
                r['gsis_id'])] = {k: r.get(k) for k in V1_KEYS}
    rows, n_missing = [], 0
    for r in fr.value:
        q = dict(r)
        b = blocks.get((r['s'], r['w'], r['t'], r['pid']))
        if b is None:
            n_missing += 1
        q['v1'] = b
        rows.append(q)
    if n_missing:
        return Outcome.fail(
            'B_UNION_BLOCK_COVERAGE',
            f'{n_missing} of {len(rows)} union frame rows carry no V1 block '
            f'after the union walk. Candidate B is the claim that presence is '
            f'a constant; a gap in it falsifies the claim rather than being '
            f'patched over.', n_missing=n_missing, n_rows=len(rows))
    present = sum(1 for r in rows if r['v1'] is not None)
    ev = {kk: vv for kk, vv in fr.evidence.items()
          if kk not in ('cached', 'spec_version', 'value', 'fingerprint')}
    ev.update({'n_rows': len(rows),
               'n_synthetic_union_rows_added_to_the_panel': len(syn),
               'n_rows_with_the_v1_feature_block': present,
               'n_rows_without_the_v1_feature_block': len(rows) - present,
               'v1_presence_rate': round(present / len(rows), 6),
               'basis': 'U_UNION_CANDIDATE_UNIVERSE'})
    _FRAME['rows'], _FRAME['evidence'], _FRAME['fingerprint'] = rows, ev, fp
    return Outcome.ok('B_FRAME_OK', value=rows, spec_version=SPEC_VERSION,
                      cached=False, **ev)


# -------------------------------------------------------------------- fit
def fit(season: int, l2=1.0) -> Outcome:
    """Fit on union-basis rows from STRICTLY EARLIER seasons, minus the refused cell.

    Chronology is a REFUSAL, not a filter: a forecast-season row reaching the
    training set means the frame moved underneath us, and dropping it quietly
    would hide that.
    """
    key = (int(season), float(l2))
    if key in _FIT:
        m = _FIT[key]
        return Outcome.ok('B_FIT', value=m, spec_version=SPEC_VERSION,
                          cached=True, **m['evidence'])
    fr = union_frame()
    if fr.state is not State.PASS:
        return fr
    rows = fr.value
    ko = R8.reliability_k(rows, cut=int(season) * 100)
    if ko.state is not State.PASS:
        return ko
    k = ko.value
    M, A, F = AM._frozen()
    train = [r for r in rows if r['s'] < season and not is_unsupported(r)]
    dropped = sum(1 for r in rows if r['s'] < season and is_unsupported(r))
    late = [r for r in train if r['s'] >= season]
    if late:
        return Outcome.fail(
            'B_TRAINING_LEAKAGE',
            f'{len(late)} row(s) from season {season} or later entered the '
            f'training set')
    if not train:
        return Outcome.fail(
            'B_FRAME_EMPTY',
            f'no union-basis row earlier than {season} survived the '
            f'unsupported-cell exclusion; a fit on nothing is not a fit')
    absent = sum(1 for r in train if r.get('v1') is None)
    if absent:
        return Outcome.fail(
            'B_TRAINING_BLOCK_ABSENT',
            f'{absent} training row(s) carry no V1 block, so feature presence '
            f'would again be a variable and could again encode the label')
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
          'v1_presence_rate_in_training': 1.0,
          'basis': 'U_UNION_CANDIDATE_UNIVERSE',
          'preregistration_sha256': PREREG_SHA256}
    m = {'model': model, 'k': k, 'evidence': ev,
         'coef_sha256': hashlib.sha256(
             np.asarray(model['w']).tobytes()).hexdigest()[:16]}
    _FIT[key] = m
    return Outcome.ok('B_FIT', value=m, spec_version=SPEC_VERSION,
                      cached=False, **ev)


# ------------------------------------------------ the serve-time V1 block
def _prospective_union(season, week, players, injuries_rows,
                       extend=True, replay=False) -> Outcome:
    """The target week's V1 block, on the SAME union basis the fit used.

    `appearance_model._prospective` walks the panel plus the target week's
    prospective rows. That is the right walk and it is reused here through its
    own helpers -- `prospective_rows`, `_typed`, `_walk`, `enrich` -- with one
    difference: the historical base is the panel EXTENDED by the union
    synthetic rows, so a player's history at serve is built from the same
    candidate universe the coefficients were fitted on.

    `extend=False` runs the identical code path with the extension removed and
    exists so `assert_prospective_matches_frozen` can prove the extension is
    the only difference from the accepted walk.

    `replay=True` TRUNCATES the historical base to rows strictly earlier than
    the target week instead of REFUSING when such rows exist. It is for
    replaying a serve on a week whose labels are already known -- the only way
    to check train/serve parity against a measured basis -- and it is a
    separate flag rather than a silent truncation because at a real serve there
    is nothing at or after the target week to truncate, so a truncation that
    fired there would be hiding a frame that had moved. Production leaves it
    False and gets the refusal.
    """
    inj26 = AM.parse_injuries_rows(injuries_rows, season)
    if not inj26:
        return Outcome.deferred(
            f'B_INJURIES_{season}_EMPTY',
            'no usable injuries row for the forecast season reached the '
            'model, so two prediction-time feature groups would both be '
            'absent and the mechanism would be a different one',
            owed={'source': f'injuries_{season}'})
    ident = [q for q in players if not q.get('gsis_id')]
    if ident:
        return Outcome.fail(
            'B_IDENTITY_UNRESOLVED',
            f'{len(ident)} player(s) carry no gsis_id. Fuzzy name matching is '
            f'forbidden, so they are refused rather than guessed.')
    try:
        S = _panel_and_inputs()
    except CandidateBError as e:
        return Outcome.blocked('B_INPUTS_UNAVAILABLE', str(e),
                               cause=Cause.DEPENDENCY)
    base = [dict(r) for r in S['panel']]
    n_syn = 0
    if extend:
        fr = union_frame()
        if fr.state is not State.PASS:
            return fr
        syn = _union_synthetics(fr.value, S['cols'], S['in_panel'])
        n_syn = len(syn)
        base = base + syn
    # CHRONOLOGY. Nothing at or after the target week may enter any history.
    o = int(season) * 100 + int(week)
    late = [r for r in base if int(r['ord']) >= o]
    n_truncated = 0
    if late and not replay:
        return Outcome.fail(
            'B_HISTORY_NOT_STRICTLY_EARLIER',
            f'{len(late)} historical row(s) sit at or after {season} week '
            f'{week} and would enter a player\'s own history')
    if late:
        base = [r for r in base if int(r['ord']) < o]
        n_truncated = len(late)
        if not base:
            return Outcome.fail(
                'B_REPLAY_NO_HISTORY',
                f'truncating to rows earlier than {season} week {week} left '
                f'no history at all; a replay on nothing is not a replay')
    last_season = max(int(x['season']) for x in base)
    tmpl = {}
    for r in base:
        if int(r['season']) == last_season:
            tmpl.setdefault(r['team'], r)
    pros = AM.prospective_rows(int(season), int(week), players, tmpl)
    rows = sorted(base + [AM._typed(r) for r in pros],
                  key=lambda x: x['ord'])
    inj = dict(S['inj'])
    inj.update(inj26)
    walked = AM._walk(S['A'], S['M'], rows, inj, S['dep'])
    S['F'].enrich(walked, inj)
    target = [r for r in walked if int(r['season']) == int(season)
              and int(r['week']) == int(week)]
    if not target:
        return Outcome.fail(
            'B_NO_PROSPECTIVE_ROWS',
            f'no row was built for {season} week {week}; a feature block over '
            f'zero players is not a feature block')
    if len(target) != len(players):
        return Outcome.fail(
            'B_PROSPECTIVE_ROW_COUNT',
            f'{len(target)} target rows for {len(players)} players')
    return Outcome.ok('B_PROSPECTIVE_ROWS', value=target,
                      spec_version=SPEC_VERSION, n_rows=len(target),
                      n_synthetic_union_rows=n_syn,
                      extended=bool(extend), replay=bool(replay),
                      n_history_rows_truncated_for_replay=n_truncated)


def assert_prospective_matches_frozen(season, week, players,
                                      injuries_rows) -> Outcome:
    """With the extension off, this walk must reproduce the accepted one exactly.

    The production walk exists only because the research one cannot be handed
    an extended row list, and `appearance_model.assert_walk_matches_research`
    already guards that boundary. This is the same guard one level up: if
    `_prospective_union(extend=False)` and
    `appearance_model.prospective_feature_rows` ever disagree, Candidate B is
    running a different mechanism under a name that claims otherwise, and the
    union extension is no longer the only thing that changed.
    """
    mine = _prospective_union(season, week, players, injuries_rows,
                              extend=False)
    if mine.state is not State.PASS:
        return mine
    theirs = AM.prospective_feature_rows(season, week, players, injuries_rows)
    if theirs.state is not State.PASS:
        return theirs
    a = {r['gsis_id']: {k: r.get(k) for k in V1_KEYS} for r in mine.value}
    b = {r['gsis_id']: {k: r.get(k) for k in V1_KEYS}
         for r in theirs.value['target']}
    if set(a) != set(b):
        return Outcome.fail(
            'B_PROSPECTIVE_PLAYER_SET_DIFFERS',
            f'{len(set(a) ^ set(b))} player(s) differ between the two walks')
    diffs, n = [], 0
    for pid in a:
        for key in V1_KEYS:
            n += 1
            if a[pid][key] != b[pid][key]:
                diffs.append({'gsis_id': pid, 'field': key,
                              'candidate_b': a[pid][key],
                              'frozen': b[pid][key]})
    if n == 0:
        return Outcome.fail('B_PROSPECTIVE_COMPARISON_VACUOUS',
                            'no feature was compared, so nothing was proven')
    if diffs:
        return Outcome.fail(
            'B_PROSPECTIVE_WALK_DIVERGES',
            f'{len(diffs)} of {n} V1 feature values differ between Candidate '
            f'B with the union extension OFF and the frozen prospective walk',
            examples=diffs[:5], n_compared=n)
    return Outcome.ok('B_PROSPECTIVE_WALK_EQUIVALENT', value=n,
                      n_players=len(a), n_comparisons=n,
                      detail=f'{n} V1 feature values identical across '
                             f'{len(a)} players')


# ---------------------------------------------------------------- predict
def predict(season, week, players, injuries_rows, observed_before=None,
            kickoff_utc=None, depth=None) -> Outcome:
    """Per-player P(appear) under Candidate B. The refused cell is declined.

    Identical to `appearance_r8.predict` in every respect except the two this
    candidate is about: the fit is on the union basis, and the serve-time V1
    block comes from the union-extended prospective walk instead of the
    panel-only one.
    """
    fr = union_frame()
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
            'B_NO_CLOCK',
            'neither observed_before nor kickoff_utc was supplied, so the '
            'depth chart could not be selected point-in-time and the newest '
            'capture would have been used by default')
    if depth is None:
        teams = sorted({q.get('team') for q in players if q.get('team')})
        if not teams:
            return Outcome.fail('B_NO_TEAMS', 'no player carries a team')
        cap = DV.captured(teams, clock)
        if cap.state is not State.PASS:
            return cap
        depth = cap.value
        depth_ev = {kk: vv for kk, vv in cap.evidence.items() if kk != 'value'}
    else:
        depth_ev = {'source': 'supplied_by_caller'}

    pr = _prospective_union(season, week, players, injuries_rows)
    if pr.state is not State.PASS:
        return pr
    v1rows = {r['gsis_id']: r for r in pr.value}

    inj26 = AM.parse_injuries_rows(injuries_rows, season)
    hist = collections.defaultdict(list)
    cur = collections.defaultdict(list)
    for r in fr.value:
        hist[r['pid']].append(r)
        if r['s'] == int(season):
            cur[r['pid']].append(r)

    declined, states = {}, collections.Counter()
    rowsX, ids, ws, rows_out = [], [], [], {}
    for q in players:
        pid = q.get('gsis_id')
        if not pid:
            return Outcome.fail(
                'B_IDENTITY_UNRESOLVED',
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
                ww *= R8._HL
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
        if _v is None:
            return Outcome.fail(
                'B_SERVE_BLOCK_ABSENT',
                f'no union-basis V1 block was built for {pid}. Under this '
                f'candidate presence is a constant; a gap in it at serve is '
                f'the defect returning, not something to impute.')
        r['v1'] = {kk: _v.get(kk) for kk in V1_KEYS}
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
        ws.append(R8.weight(r['n_cur'], k))
        rows_out[pid] = r
    if not ids:
        return Outcome.fail(
            'B_NO_SCORABLE_PLAYER',
            f'all {len(players)} player(s) fall in the unsupported cell',
            n_declined=len(declined))
    p = A.predict(f.value['model'], rowsX)
    out = {pid: float(v) for pid, v in zip(ids, p)}
    return Outcome.ok(
        'B_APPEARANCE_PREDICTED', value=out, spec_version=SPEC_VERSION,
        test_only=False, n_players=len(out), n_declined=len(declined),
        declined=declined, states=dict(states),
        coef_sha256=f.value['coef_sha256'],
        clock=clock.isoformat(), depth=depth_ev,
        serve_v1_presence_rate=1.0,
        n_synthetic_union_rows=pr.evidence.get('n_synthetic_union_rows'),
        reliability_weight_mean=round(float(np.mean(ws)), 6),
        reliability_weight_max=round(float(np.max(ws)), 6),
        n_with_a_depth_listing=sum(1 for q in players
                                   if depth.get(q.get('gsis_id'))),
        p_mean=float(np.mean(p)), p_min=float(np.min(p)),
        p_max=float(np.max(p)), rows=rows_out, **f.value['evidence'])
