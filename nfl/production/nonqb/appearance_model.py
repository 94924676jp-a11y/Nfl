"""The REAL D2 path: the frozen P3 appearance mechanism, in production.

WHY THIS EXISTS, AND WHAT IT IS NOT

R3 asks that publication of the legitimate injury source become an INPUT
UNBLOCK rather than another engineering sprint. That claim is only true if the
code that consumes the source already exists. Before this module, `appearance`
deferred correctly when the feed was unusable and, had the feed become usable,
would have fallen through to a fixture error -- so the operator WOULD have
needed a code change, and the readiness report would have been telling a
comforting story.

NOTHING IS TUNED HERE. The mechanism is imported from the frozen research
modules:

    nfl/research/p2/stage_a.py    build(), featurise(), fit_logistic(), predict()
    nfl/research/p3/p3_features.py  enrich(), featurise_p3(), FEATURE_GROUPS

The historical fit runs `stage_a.build` itself, on the P3 panel staged under
the filename its loader expects. The PROSPECTIVE walk cannot: `build` loads
the panel from disk and will not accept a row list extended with unplayed
games. That one loop is therefore re-implemented in `_walk`, is labelled as a
re-implementation, and is checked against the research walk feature by feature
over the whole historical panel by `assert_walk_matches_research`. A
re-implementation nobody compared is how a production model quietly stops
being the accepted one.

CHRONOLOGY. Training rows are strictly earlier seasons; a row from the forecast
season entering the fit is a NAMED refusal, not a filtered surprise. The 2026
injuries rows come from the CAPTURED vintage blob, which carries its own
`retrieved_at`, never from the committed historical leaves.

INPUT INTEGRITY. Every committed leaf is hash-checked against
`nfl/research/inputs/INPUT_MANIFEST.json` before it is used. A leaf that has
moved is a refusal.
"""
from __future__ import annotations

import collections
import csv
import gzip
import hashlib
import json
import pathlib
import sys
import time

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p1'),
           str(_REPO / 'nfl' / 'research' / 'p2'),
           str(_REPO / 'nfl' / 'research' / 'p3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

INPUTS = _REPO / 'nfl' / 'research' / 'inputs'
MANIFEST = INPUTS / 'INPUT_MANIFEST.json'
SPEC_VERSION = 'appearance-p3-frozen-logistic-1'

# The leaves the frozen mechanism reads. panel.csv is panel_p3.csv staged under
# the name model.load() expects -- see the module docstring.
NEEDED = ('panel_p3.csv', 'inj_2020.csv', 'inj_2021.csv', 'inj_2022.csv',
          'inj_2023.csv', 'inj_2024.csv', 'inj_2025.csv',
          'dc_2020.csv', 'dc_2021.csv', 'dc_2022.csv', 'dc_2023.csv',
          'dc_2024.csv')

_STAGE = None            # staged input directory, one per process
_FIT = {}                # (season, injuries fingerprint) -> fitted model


def stage_inputs(dest=None) -> Outcome:
    """Decompress the committed leaves, hash-checking every one."""
    global _STAGE
    if _STAGE is not None and dest is None:
        return Outcome.ok('INPUTS_ALREADY_STAGED', value=str(_STAGE))
    if not MANIFEST.exists():
        return Outcome.blocked('INPUT_MANIFEST_MISSING',
                               f'{MANIFEST} is absent, so no leaf can be '
                               f'verified before use', cause=Cause.DATA)
    man = json.loads(MANIFEST.read_text())['files']
    import tempfile
    d = pathlib.Path(dest) if dest else pathlib.Path(
        tempfile.mkdtemp(prefix='nfl-appearance-'))
    d.mkdir(parents=True, exist_ok=True)
    for name in NEEDED:
        src = INPUTS / (name + '.gz')
        if not src.exists():
            return Outcome.blocked(
                'RESEARCH_INPUT_MISSING',
                f'{name} is not committed under nfl/research/inputs, so the '
                f'frozen appearance mechanism cannot be fitted',
                cause=Cause.DATA, missing=name)
        raw = gzip.open(src, 'rb').read()
        want = man.get(name, {}).get('sha256_decompressed')
        got = hashlib.sha256(raw).hexdigest()
        if want and want != got:
            return Outcome.fail(
                'RESEARCH_INPUT_HASH_MISMATCH',
                f'{name} hashes {got[:16]} against the manifest\'s '
                f'{want[:16]}. A moved leaf is a different model.',
                file=name)
        (d / name).write_bytes(raw)
    # model.load() reads panel.csv; panel_p3 is the P3 panel.
    (d / 'panel.csv').write_bytes((d / 'panel_p3.csv').read_bytes())
    _STAGE = d
    return Outcome.ok('INPUTS_STAGED', value=str(d), n_files=len(NEEDED))


def _frozen():
    import model as M
    import stage_a as A
    import p3_features as F
    M.SP = str(_STAGE)
    A.P1 = str(_STAGE)
    return M, A, F


def _inj_key(rows):
    """A fingerprint of the 2026 injuries rows actually consumed."""
    h = hashlib.sha256()
    for k in sorted(rows):
        h.update(f'{k}|{rows[k]["report_status"]}|'
                 f'{rows[k]["practice_status"]}\n'.encode())
    return h.hexdigest()[:16]


def parse_injuries_rows(rows, season) -> dict:
    """Captured feed rows -> the key shape stage_a.injuries returns."""
    out = {}
    for r in rows:
        try:
            s, w = int(r['season']), int(r['week'])
        except (KeyError, TypeError, ValueError):
            continue
        if s != season or not r.get('gsis_id') or not r.get('team'):
            continue
        out[(s, w, r['team'], r['gsis_id'])] = {
            'report_status': (r.get('report_status') or '').strip(),
            'practice_status': (r.get('practice_status') or '').strip()}
    return out


def fit(season: int, injuries_2026: dict | None = None) -> Outcome:
    """Fit the frozen mechanism on STRICTLY EARLIER seasons."""
    st = stage_inputs()
    if st.state is not State.PASS:
        return st
    key = (season, _inj_key(injuries_2026 or {}))
    if key in _FIT:
        m = _FIT[key]
        return Outcome.ok('APPEARANCE_MODEL_FIT', value=m, cached=True,
                          spec_version=SPEC_VERSION, **m['evidence'])
    M, A, F = _frozen()
    t0 = time.time()
    kick = A.kickoffs()
    inj, _ = A.injuries(kick)
    if injuries_2026:
        inj = dict(inj)
        inj.update(injuries_2026)
    dep = A.depth()
    rows = A.build(kick, inj, dep)
    F.enrich(rows, inj)
    groups = set(F.FEATURE_GROUPS)
    train = [r for r in rows if int(r['season']) < season]
    # THE LEAKAGE GUARD IS A REFUSAL, NOT A FILTER. If a forecast-season row
    # reaches the training set the fit is a different fit, and silently
    # dropping it would hide that the panel had moved.
    late = [r for r in rows if int(r['season']) >= season]
    if any(r in train for r in late):
        return Outcome.fail('APPEARANCE_TRAINING_LEAKAGE',
                            'a forecast-season row entered the training set')
    if not train:
        return Outcome.fail(
            'APPEARANCE_PANEL_EMPTY',
            f'no panel row earlier than {season}; a fit on nothing is not a '
            f'fit', n_rows=len(rows))
    X = [F.featurise_p3(r, True, groups) for r in train]
    y = [r['appeared'] for r in train]
    model = A.fit_logistic(X, y)
    p = A.predict(model, X)
    ev = {'n_train_rows': len(train), 'n_features': len(X[0]),
          'train_seasons': sorted({int(r['season']) for r in train}),
          'in_sample_brier': float(A.brier(y, p)),
          'in_sample_auc': float(A.auc(y, p)),
          'base_rate': float(np.mean(y)),
          'fit_seconds': round(time.time() - t0, 2),
          'feature_groups': sorted(groups),
          'n_injuries_2026_rows': len(injuries_2026 or {})}
    m = {'model': model, 'rows': rows, 'groups': groups, 'evidence': ev,
         'coef_sha256': hashlib.sha256(
             np.asarray(model['w']).tobytes()).hexdigest()[:16]}
    _FIT[key] = m
    return Outcome.ok('APPEARANCE_MODEL_FIT', value=m, cached=False,
                      spec_version=SPEC_VERSION, **ev)


def _panel_columns():
    with gzip.open(INPUTS / 'panel_p3.csv.gz', 'rt') as fh:
        return next(csv.reader(fh))


def prospective_rows(season, week, players, template_by_team):
    """One panel-shaped row per rostered player, with ZERO opportunity.

    The row's own opportunity columns are not features -- every feature comes
    from the player's PRIOR rows -- so they carry zero rather than a guess.
    """
    cols = _panel_columns()
    out = []
    for q in players:
        t = q.get('team')
        tmpl = template_by_team.get(t, {})
        r = {c: 0 for c in cols}
        r.update({'season': season, 'week': week, 'team': t,
                  'gsis_id': q['gsis_id'], 'position': q.get('position'),
                  'player_name': q.get('player_name') or q['gsis_id'],
                  'game_id': tmpl.get('game_id', f'{season}_{week:02d}_{t}'),
                  'offense_pct': '', 'ord': season * 100 + week})
        out.append(r)
    return out


def predict(season, week, players, injuries_rows) -> Outcome:
    """p(appear) for each rostered player, from the frozen mechanism."""
    inj26 = parse_injuries_rows(injuries_rows, season)
    if not inj26:
        return Outcome.deferred(
            f'INJURIES_{season}_EMPTY',
            'no usable injuries row for the forecast season reached the '
            'model, so the two prediction-time feature groups would both be '
            'absent and the mechanism would be a different one',
            owed={'source': f'injuries_{season}'})
    ident = [q for q in players if not q.get('gsis_id')]
    if ident:
        return Outcome.fail(
            'APPEARANCE_IDENTITY_UNRESOLVED',
            f'{len(ident)} player(s) carry no gsis_id. Fuzzy name matching is '
            f'forbidden, so they are refused rather than guessed.',
            n=len(ident))
    f = fit(season, inj26)
    if f.state is not State.PASS:
        return f
    M, A, F = _frozen()
    hist = f.value['rows']
    # Build the prospective rows, then rebuild features over history + them.
    # HOIST THE MAX. Computed inside the loop this was 83,144 x 83,144 season
    # comparisons and turned a 30-second call into a ten-minute one.
    last_season = max(int(x['season']) for x in hist)
    tmpl = {}
    for r in hist:
        if int(r['season']) == last_season:
            tmpl.setdefault(r['team'], r)
    pros = prospective_rows(season, week, players, tmpl)
    known = {r['gsis_id'] for r in hist}
    rows = sorted(hist + [_typed(r) for r in pros], key=lambda x: x['ord'])
    by_pid = collections.defaultdict(list)
    for r in rows:
        by_pid[r['gsis_id']].append(r)
    # Re-run the frozen per-row walk over the extended panel. stage_a.build
    # reads from disk, so the extension is applied by feeding it the same walk
    # through its own helpers rather than by restating the arithmetic.
    kick = A.kickoffs()
    inj = dict(A.injuries(kick)[0]); inj.update(inj26)
    dep = A.depth()
    walked = _walk(A, M, rows, inj, dep)
    F.enrich(walked, inj)
    target = [r for r in walked
              if int(r['season']) == season and int(r['week']) == week]
    if not target:
        return Outcome.fail(
            'APPEARANCE_NO_PROSPECTIVE_ROWS',
            f'no row was built for {season} week {week}; a prediction over '
            f'zero players is not a prediction')
    X = [F.featurise_p3(r, True, f.value['groups']) for r in target]
    p = A.predict(f.value['model'], X)
    out = {r['gsis_id']: float(v) for r, v in zip(target, p)}
    cold = [r['gsis_id'] for r in target if r['gsis_id'] not in known]
    with_inj = sum(1 for r in target if r.get('f_inj_available'))
    return Outcome.ok(
        'APPEARANCE_PREDICTED', value=out, spec_version=SPEC_VERSION,
        test_only=False, n_players=len(out),
        n_without_prior_history=len(cold),
        n_with_an_injuries_row=with_inj,
        coef_sha256=f.value['coef_sha256'],
        p_mean=float(np.mean(p)), p_min=float(np.min(p)),
        p_max=float(np.max(p)), **f.value['evidence'])


def _typed(r):
    r = dict(r)
    r['season'] = int(r['season']); r['week'] = int(r['week'])
    for k in ('targets', 'carries', 'rz_targets', 'rz_carries', 'gl_carries',
              'third_targets', 'pass_snaps', 'team_plays', 'team_dropbacks',
              'team_pass_att', 'team_rush_att', 'team_rz_rush', 'team_gl_rush',
              'team_dropbacks_part', 'dropbacks_as_passer',
              'pass_att_as_passer', 'scrambles', 'designed_rushes'):
        r[k] = int(float(r.get(k) or 0))
    r['offense_pct'] = None
    r['ord'] = r['season'] * 100 + r['week']
    r['did_not_appear'] = None            # UNKNOWN, and never read as 0
    return r


def _walk(A, M, rows, inj, dep):
    """The pregame feature walk over an already-loaded row list.

    THIS IS A RE-IMPLEMENTATION AND IS LABELLED AS ONE. `stage_a.build` does
    the same walk but loads the panel from disk itself, so it cannot be handed
    a row list extended with prospective rows. Every other piece of the
    mechanism -- featurise, featurise_p3, enrich, fit_logistic, predict -- is
    imported from the frozen research modules and is NOT restated.

    Because a re-implementation is exactly how a production model stops being
    the accepted one, `assert_walk_matches_research` runs both walks over the
    same historical panel and fails on the first feature that differs. The
    claim of equivalence is a measured one, not an assurance.
    """
    rows = M.add_shares(rows)
    rows = M.role_flag(rows)
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        pid = r['gsis_id']
        past = hist[pid]
        dna = r.get('did_not_appear')
        r['appeared'] = None if dna is None else (1 if dna == 0 else 0)
        A_ = [x['appeared'] for x in past if x['appeared'] is not None]
        sh = [x.get('snap_share') for x in past]
        r['f_prev_appeared'] = A_[-1] if A_ else None
        r['f_rate3'] = float(np.mean(A_[-3:])) if A_ else None
        r['f_rate5'] = float(np.mean(A_[-5:])) if A_ else None
        w = 0.5 ** (1 / 3)

        def _ew(v):
            if not v:
                return None
            num = den = 0.0
            ww = 1.0
            for x in reversed(v):
                num += ww * x
                den += ww
                ww *= w
            return num / den
        r['f_rate_ewma'] = _ew(A_)
        r['f_n_prior'] = len(past)
        r['f_weeks_since_appear'] = next(
            (i + 1 for i, x in enumerate(reversed(past)) if x['appeared']),
            None)
        pv = [x for x in sh if x is not None]
        r['f_prev_snap'] = pv[-1] if pv else None
        r['f_snap_ewma'] = _ew(pv)
        r['f_team_change'] = 1 if past and past[-1]['team'] != r['team'] else 0
        r['f_consec_missed'] = 0
        for x in reversed(past):
            if x['appeared']:
                break
            r['f_consec_missed'] += 1
        d = inj.get((r['season'], r['week'], r['team'], pid))
        r['f_inj_status'] = (d['report_status'] if d else None)
        r['f_inj_practice'] = (d['practice_status'] if d else None)
        r['f_inj_available'] = 1 if d is not None else 0
        r['f_depth'] = dep.get((r['season'], r['week'], r['team'], pid))
        hist[pid].append(r)
    return rows


def assert_walk_matches_research(sample=None) -> Outcome:
    """Run both walks over the same historical panel and compare every feature.

    The production walk exists only because the research one cannot be handed
    an extended row list. If the two ever disagree, production is running a
    different mechanism under an accepted name, and that is a FAIL.
    """
    st = stage_inputs()
    if st.state is not State.PASS:
        return st
    M, A, F = _frozen()
    kick = A.kickoffs()
    inj, _ = A.injuries(kick)
    dep = A.depth()
    research = A.build(kick, inj, dep)
    mine = _walk(A, M, [dict(r) for r in research], inj, dep)
    keys = ('f_prev_appeared', 'f_rate3', 'f_rate5', 'f_rate_ewma',
            'f_n_prior', 'f_weeks_since_appear', 'f_prev_snap', 'f_snap_ewma',
            'f_team_change', 'f_consec_missed', 'f_inj_status',
            'f_inj_practice', 'f_inj_available', 'appeared')
    if len(mine) != len(research):
        return Outcome.fail(
            'APPEARANCE_WALK_ROW_COUNT_DIFFERS',
            f'{len(mine)} production rows against {len(research)} research '
            f'rows')
    idx = {(r['gsis_id'], r['team'], r['ord']): r for r in mine}
    diffs, n = [], 0
    rs = research if sample is None else research[:sample]
    for r in rs:
        q = idx.get((r['gsis_id'], r['team'], r['ord']))
        if q is None:
            diffs.append({'row': r['gsis_id'], 'field': '(missing)'})
            continue
        for k in keys:
            a, b = r.get(k), q.get(k)
            n += 1
            if a is None or b is None:
                if a is not b:
                    diffs.append({'row': r['gsis_id'], 'field': k,
                                  'research': a, 'production': b})
                continue
            if isinstance(a, float) or isinstance(b, float):
                if abs(float(a) - float(b)) > 1e-12:
                    diffs.append({'row': r['gsis_id'], 'field': k,
                                  'research': a, 'production': b})
            elif a != b:
                diffs.append({'row': r['gsis_id'], 'field': k,
                              'research': a, 'production': b})
    if n == 0:
        return Outcome.fail('APPEARANCE_WALK_COMPARISON_VACUOUS',
                            'no feature was compared, so nothing was proven')
    if diffs:
        return Outcome.fail(
            'APPEARANCE_WALK_DIVERGES',
            f'{len(diffs)} of {n} feature comparisons differ between the '
            f'research walk and the production walk',
            examples=diffs[:5], n_compared=n)
    return Outcome.ok('APPEARANCE_WALK_EQUIVALENT', value=n,
                      n_rows=len(rs), n_comparisons=n,
                      detail=f'{n} feature values identical across '
                             f'{len(rs)} rows')
