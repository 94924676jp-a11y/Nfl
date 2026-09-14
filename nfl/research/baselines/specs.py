"""Freeze the baseline definitions and hash them.

THE FREEZE HAPPENS BEFORE THE EVALUATION RUNS, AND THE EVALUATION REFUSES TO
RUN AGAINST AN UNFROZEN OR ALTERED SPEC.

That ordering is the whole guarantee. A baseline chosen after seeing a
candidate's result is not a baseline, it is a rationalisation, and the only
defence that survives contact with a later reader is a hash written down before
the comparison existed. `evaluate.py` recomputes every hash in this document
and stops if one differs.

WHAT IS IN A HASH. Each baseline's `spec_sha256` covers the canonical JSON of
its own definition -- estimator name, window, constants and how each was
obtained, fallback chain, frame definition, quantity list -- TOGETHER WITH the
sha256 of every byte of input data the constants were derived from. A spec hash
that did not cover the data identity would be stable across a silent change of
corpus, which is precisely the trap the sibling MLB project fell into when
`SIM_FORMULA` excluded the corpus and the fingerprint stayed identical while the
inputs moved.

THE TWO CONSTANT CLASSES ARE LABELLED SEPARATELY, because the directive
distinguishes them and a reader must be able to audit them differently:

  DERIVED_FROM_PRINCIPLE   k = sigma_w^2 / sigma_b^2, the normal-normal
                           posterior weight. A derivation whose inputs are
                           measured, not a search over scores.
  FITTED_PRIOR_WINDOW      c (season carry-over slope), N (recent-window
                           length) and H (EWMA half-life). These ARE selected,
                           on seasons 2021-2022 only -- strictly before the
                           2023-2024 evaluation window -- and no evaluation row
                           took part in the selection.

Nothing here is fitted to a sportsbook line, to Fantasy Cruncher, or to the
2026 season. The 2026 blobs are unreachable from this package: `panel.py`
refuses the season.
"""
from __future__ import annotations

import hashlib
import json
import os
import statistics

from nfl.research.baselines import estimators as E
from nfl.research.baselines import frame as F
from nfl.research.baselines import panel as P

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.join(HERE, 'BASELINE_SPECS.json')

SPEC_VERSION = 'd8-baselines-1'

N_GRID = (1, 2, 3, 4, 6, 8, 10, 16)
H_GRID = (0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0)

#: The window-length selection runs on season 2022 rows with 2021-2022 history.
#: 2021 carries no prior season inside the lawful range, so a 2021 row would
#: score the fallback rather than the estimator.
SELECTION_SEASONS = (2022,)


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False)


def sha256_of_obj(obj) -> str:
    return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()


def _groups():
    g = {}
    for q, pos in F.QUANTITY_POSITIONS.items():
        g[q] = pos
    for q in F.TEAM_QUANTITIES:
        g[q] = ('TEAM',)
    return g


def _team_varcomp(idx, quantity, seasons):
    cells = {}
    for r in idx.teams:
        if r['season'] not in seasons:
            continue
        cells.setdefault((r['team'], r['season']), []).append(float(r[quantity]))
    usable = {k: v for k, v in cells.items() if len(v) >= 4}
    within = [statistics.pvariance(v) * len(v) / (len(v) - 1)
              for v in usable.values()]
    means = [statistics.mean(v) for v in usable.values()]
    ns = [len(v) for v in usable.values()]
    s2w = statistics.mean(within)
    s2m = statistics.pvariance(means) * len(means) / (len(means) - 1)
    s2b = max(s2m - s2w / statistics.mean(ns), 1e-9)
    return s2w, s2b, s2w / s2b


def _team_carryover(idx, quantity, y0, y1):
    a, b = {}, {}
    for r in idx.teams:
        if r['season'] == y0:
            a.setdefault(r['team'], []).append(float(r[quantity]))
        elif r['season'] == y1:
            b.setdefault(r['team'], []).append(float(r[quantity]))
    xs = [statistics.mean(a[t]) for t in sorted(set(a) & set(b))]
    ys = [statistics.mean(b[t]) for t in sorted(set(a) & set(b))]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return (sxy / sxx if sxx > 0 else 0.0), len(xs)


def derive_constants(idx) -> dict:
    """k and c per quantity, from the ESTIMATION window only."""
    out = {}
    for q, pos in _groups().items():
        if pos == ('TEAM',):
            s2w, s2b, k = _team_varcomp(idx, q, F.ESTIMATION_SEASONS)
            c, npairs = _team_carryover(idx, q, 2021, 2022)
        else:
            s2w, s2b, k = F.variance_components(idx, q, pos,
                                                F.ESTIMATION_SEASONS)
            c, npairs = F.carryover_slope(idx, q, pos, 2021, 2022)
        out[q] = {
            'positions': list(pos),
            'sigma2_within': round(s2w, 6),
            'sigma2_between': round(s2b, 6),
            'k_prior_games': round(k, 6),
            'k_class': 'DERIVED_FROM_PRINCIPLE',
            'k_derivation': ('normal-normal posterior weight '
                             'sigma_w^2 / sigma_b^2, both measured on seasons '
                             f'{list(F.ESTIMATION_SEASONS)}'),
            'c_carryover_slope': round(c, 6),
            'c_class': 'FITTED_PRIOR_WINDOW',
            'c_derivation': ('OLS slope of the 2022 per-game mean on the 2021 '
                             f'per-game mean, n_pairs={npairs}; a fit, to '
                             'seasons strictly before the evaluation window'),
            'c_n_pairs': npairs,
        }
    return out


def select_windows(idx, constants, frames_by_season) -> dict:
    """N and H, chosen by MAE on the SELECTION seasons only.

    The grid, the seasons and the loss are all named here. Selecting a window
    length on data strictly prior to the evaluation window is what the
    directive permits; selecting it on the evaluation window would make the
    baseline a model that had seen the test set.
    """
    out = {}
    for q in list(F.QUANTITY_POSITIONS) + list(F.TEAM_QUANTITIES):
        rows = []
        for s in SELECTION_SEASONS:
            rows.extend(frames_by_season[q][s])
        if not rows:
            raise F.FrameEmpty(f'BASELINE_SELECTION_FRAME_EMPTY:{q}')
        best_n, best_n_mae = None, None
        for n in N_GRID:
            errs = []
            for r in rows:
                h = idx.hist(r['pid'], q, r['ordinal'])
                if not h:
                    continue
                errs.append(abs(E.recent_n(h, n) - r['actual']))
            mae = statistics.mean(errs)
            if best_n_mae is None or mae < best_n_mae:
                best_n, best_n_mae = n, mae
        best_h, best_h_mae = None, None
        for hl in H_GRID:
            errs = []
            for r in rows:
                h = idx.hist(r['pid'], q, r['ordinal'])
                if not h:
                    continue
                errs.append(abs(E.ewma(h, hl) - r['actual']))
            mae = statistics.mean(errs)
            if best_h_mae is None or mae < best_h_mae:
                best_h, best_h_mae = hl, mae
        out[q] = {'recent_n': best_n,
                  'recent_n_selection_mae': round(best_n_mae, 6),
                  'ewma_half_life_games': best_h,
                  'ewma_selection_mae': round(best_h_mae, 6),
                  'selection_seasons': list(SELECTION_SEASONS),
                  'selection_rows': len(rows),
                  'class': 'FITTED_PRIOR_WINDOW',
                  'n_grid': list(N_GRID), 'h_grid': list(H_GRID)}
    return out


BASELINE_DEFINITIONS = {
    'B1-SEASON-TO-DATE': {
        'estimator': 'estimators.season_to_date',
        'window': 'all completed games of the CURRENT season, same subject',
        'boundary': 'does not cross the season boundary',
        'fallback_chain': ['W1-PRIOR-SEASON-SHRUNK',
                           'B6-LEAGUE-POSITION-PRIOR'],
        'constants': [],
    },
    'B2-RECENT-N': {
        'estimator': 'estimators.recent_n',
        'window': 'the last N completed games of the subject, N frozen',
        'boundary': 'crosses the season boundary',
        'fallback_chain': ['B6-LEAGUE-POSITION-PRIOR'],
        'constants': ['recent_n'],
    },
    'B3-EWMA': {
        'estimator': 'estimators.ewma',
        'window': ('all completed games of the subject, weight '
                   '0.5 ** (games_back / H); games_back counts APPEARANCES, '
                   'not calendar weeks'),
        'boundary': 'crosses the season boundary',
        'fallback_chain': ['B6-LEAGUE-POSITION-PRIOR'],
        'constants': ['ewma_half_life_games'],
    },
    'B4-SHRINK': {
        'estimator': 'estimators.shrunk',
        'window': ('prior-season mean carried over by c and shrunk to the '
                   'position mean, then updated by the current season with '
                   'prior weight k games'),
        'boundary': 'crosses the season boundary explicitly and by design',
        'fallback_chain': ['(total by construction: collapses to the position '
                           'mean when no history exists)'],
        'constants': ['k_prior_games', 'c_carryover_slope'],
    },
    'B5-ROLE-AVERAGE': {
        'estimator': 'estimators.role_average',
        'window': ('league mean for (position, within-team usage rank) over '
                   'seasons strictly before the forecast season; rank from '
                   'the team\'s last 3 completed games'),
        'boundary': 'uses no level information about the subject himself',
        'fallback_chain': ['B6-LEAGUE-POSITION-PRIOR'],
        'constants': ['role_max_rank=6', 'frame_window_games=3'],
    },
    'B6-LEAGUE-POSITION-PRIOR': {
        'estimator': 'estimators.league_prior',
        'window': ('mean over FRAME_A rows of seasons strictly before the '
                   'forecast season, by position'),
        'boundary': 'terminal fallback; always defined for a labelled position',
        'fallback_chain': [],
        'constants': [],
    },
    'W1-PRIOR-SEASON-SHRUNK': {
        'estimator': 'estimators.w1_prior_season_shrunk',
        'window': ('the prior season\'s per-game mean, carried over by c and '
                   'shrunk to the position mean with prior weight k'),
        'boundary': 'THE FROZEN WEEK-1 / SEASON-OPENER TRANSITION BASELINE',
        'fallback_chain': ['B6-LEAGUE-POSITION-PRIOR'],
        'constants': ['k_prior_games', 'c_carryover_slope'],
        'justification': (
            'Chosen on a stated principle before any evaluation-window score '
            'existed: a mean over a player\'s whole prior season has strictly '
            'smaller sampling variance than any single game drawn from it, '
            'for the same estimand. The rejected alternative -- the prior '
            'season\'s FINAL game -- is the shape the engine already carries, '
            'and its pathology is measured: previous_primary_detail(2026,1) '
            '[\'KC\'] resolves to 2025 week 18, and the charted QB1 equals the '
            'prior-season final-game primary in only 59 of 160 week-1 rooms '
            '(0.3688). The comparator is scored in this package AFTER the '
            'freeze, as a diagnostic, and the choice was not conditioned on '
            'that score.'),
        'assumptions': [
            'a player\'s prior-season per-game level is informative about his '
            'week-1 level, discounted by the measured carry-over slope c',
            'no offseason roster movement is modelled: this package has no '
            'roster feed and does not invent one, so a player who changed '
            'clubs is forecast for his PRIOR club and scores an actual of '
            'zero. The cost is reported as frame_a_zero_actual_rate rather '
            'than assumed away',
            'rookies and any player with no prior-season game fall to the '
            'position prior, which is the honest degenerate case',
        ],
    },
    'W1-FINAL-GAME': {
        'estimator': 'estimators.w1_final_game',
        'window': 'the single final game of the prior season',
        'boundary': 'DIAGNOSTIC COMPARATOR ONLY -- NOT A FROZEN DEFAULT',
        'fallback_chain': ['B6-LEAGUE-POSITION-PRIOR'],
        'constants': [],
        'justification': ('scored so that the cost of the engine\'s existing '
                          '"previous primary" shape is a number rather than '
                          'an assertion'),
    },
    'W1-PRIOR-SEASON-MEAN': {
        'estimator': 'estimators.w1_prior_season_mean',
        'window': 'the prior season\'s per-game mean, unshrunk',
        'boundary': 'DIAGNOSTIC MIDDLE TERM -- isolates shrinkage from window',
        'fallback_chain': ['B6-LEAGUE-POSITION-PRIOR'],
        'constants': [],
    },
}


def build_document(idx, constants, windows) -> dict:
    frame_def = {
        'FRAME_A': ('point-in-time eligible: >=1 opportunity for this team in '
                    'the team\'s 3 most recent completed games before the '
                    'forecast ordinal (in-season; at a season opener, the '
                    'team\'s last 3 games of the previous season). Membership '
                    'is a function of prior games only. A selected player who '
                    'does not play scores an actual of zero.'),
        'FRAME_B': ('appeared: FRAME_A restricted to rows with >=1 realised '
                    'opportunity. CONDITIONS ON THE OUTCOME and is reported '
                    'only as a labelled secondary frame.'),
        'grouping': '(game_id, posteam) -- never by game alone',
        'kneels': "excluded: qb_kneel != '1'",
        'season_type': 'REG only',
        'frame_window_games': F.FRAME_WINDOW_GAMES,
        'clustering': 'game_id; every reported interval is a game-clustered '
                      'block bootstrap',
    }
    identity = idx.identity
    doc = {
        'artifact': 'D8_FROZEN_BASELINE_SPECS',
        'spec_version': SPEC_VERSION,
        'governance': ('DIAGNOSTICS ONLY. No baseline in this document may be '
                       'adopted, promoted, or wired into a projection path. '
                       'A baseline is a comparison object.'),
        'lawful_seasons': list(P.LAWFUL_SEASONS),
        'estimation_seasons': list(F.ESTIMATION_SEASONS),
        'evaluation_seasons': list(F.EVALUATION_SEASONS),
        'excluded_seasons_and_why': {
            '2025': 'no play-by-play blob exists in this repository',
            '2026': ('the live season. One week-1 game (DEN@KC) is still '
                     'unplayed and the rest are this season\'s own outcomes. '
                     'panel.blob_for refuses the season by raising '
                     'ChronologyRefused, so it is unreachable from this '
                     'package rather than merely discouraged.'),
        },
        'frames': frame_def,
        'quantities': sorted(list(F.QUANTITY_POSITIONS) +
                             list(F.TEAM_QUANTITIES)),
        'data_identity': identity,
        'constants': constants,
        'windows': windows,
        'baselines': {},
    }
    for name, d in BASELINE_DEFINITIONS.items():
        body = dict(d)
        body['name'] = name
        body['spec_version'] = SPEC_VERSION
        body['frames'] = frame_def
        body['data_identity'] = identity
        body['constants_frozen'] = {
            q: {k: v for k, v in constants[q].items()}
            for q in sorted(constants)
        } if d['constants'] else {}
        body['windows_frozen'] = {
            q: windows[q] for q in sorted(windows)
        } if any(c in ('recent_n', 'ewma_half_life_games')
                 for c in d['constants']) else {}
        body['spec_sha256'] = sha256_of_obj(body)
        doc['baselines'][name] = body
    doc['document_sha256'] = sha256_of_obj(
        {k: v for k, v in doc.items() if k != 'document_sha256'})
    return doc


def verify(doc) -> list:
    """Re-derive every hash. Returns the list of mismatches (empty is good)."""
    bad = []
    for name, body in doc['baselines'].items():
        stated = body.get('spec_sha256')
        recomputed = sha256_of_obj(
            {k: v for k, v in body.items() if k != 'spec_sha256'})
        if stated != recomputed:
            bad.append((name, stated, recomputed))
    stated = doc.get('document_sha256')
    recomputed = sha256_of_obj(
        {k: v for k, v in doc.items() if k != 'document_sha256'})
    if stated != recomputed:
        bad.append(('__document__', stated, recomputed))
    return bad


def load() -> dict:
    if not os.path.exists(SPEC_PATH):
        raise FileNotFoundError(
            f'BASELINE_SPECS_ABSENT: {SPEC_PATH} does not exist. The '
            f'evaluation refuses to run against constants that were never '
            f'frozen.')
    with open(SPEC_PATH, encoding='utf-8') as fh:
        doc = json.load(fh)
    bad = verify(doc)
    if bad:
        raise ValueError(f'BASELINE_SPEC_HASH_MISMATCH: {bad}')
    return doc
