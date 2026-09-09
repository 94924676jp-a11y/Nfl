"""D1 team environment: prospective team-volume draws.

RESEARCH-TO-PRODUCTION EQUIVALENCE BY CONSTRUCTION, NOT BY REIMPLEMENTATION.

This module does not re-derive P4B. It IMPORTS `p4b_volume` and calls its own
`attach`, `baselines`, `build_forms` and `draw`. There is therefore no second
copy of the mathematics to drift from the first, and the equivalence test in
nfl/tests/test_v1_nonqb_production.py checks that identical inputs and seeds
give identical numbers rather than merely similar ones.

WHAT THE ACCEPTED RESEARCH SAYS, PRESERVED RATHER THAN IMPROVED

P4 found team volume close to unforecastable -- the best simple baseline was
the league mean in two seasons of four, and correlation peaked at 0.167. P4B's
job was to make that uncertainty explicit rather than to reduce it. The
selected point estimators for 2025, the most recent evaluated season, are:

    team_off_snaps        league_mean
    team_dropbacks_part   coach_prior
    team_targets          ewma
    team_carries          coach_prior
    team_rz_carries       coach_prior

Those selections are READ from the frozen research output, never re-chosen
here. Re-selecting an estimator inside production would be exactly the retuning
this packet forbids.

CHRONOLOGY. The prospective row for an upcoming week is appended to the
historical panel at its own ordinal and the research `attach` is re-run over
the whole sorted list, so each row inherits the frozen strictly-earlier cut.
The same discipline as the QB layer, for the same reason.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import pathlib
import sys
import zlib

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production import seeds as SEEDS                         # noqa: E402

SPEC_VERSION = 'team-volume-v1-p4b-frozen-1'
METRICS = ('team_off_snaps', 'team_dropbacks_part', 'team_targets',
           'team_carries', 'team_rz_carries')
RESULTS = _REPO / 'nfl' / 'research' / 'p4b' / 'volume_results.json'
PANEL = _REPO / 'nfl' / 'research' / 'inputs' / 'denom_panel.csv.gz'
SCHED_GLOB = 'schedules.*.csv.gz'

KNOWN_LIMITATIONS = {
    'team_volume_is_near_unforecastable': {
        'source': 'P4 / P4B, accepted',
        'note': 'the best simple baseline was the league mean in two seasons '
                'of four and correlation peaked at 0.167. These draws are '
                'honest about that width; they do not narrow it.',
        'policy': 'reported on every run, never presented as skill',
    },
}


def _panel():
    rows = []
    with gzip.open(PANEL, 'rt') as fh:
        for r in csv.DictReader(fh):
            for k in ('season', 'week', 'ord'):
                r[k] = int(r[k])
            for k in METRICS:
                r[k] = int(r[k])
            rows.append(r)
    rows.sort(key=lambda x: (x['ord'], x['team']))
    return rows


def coaches(season, week):
    """Head coach per team for an upcoming week, from the captured schedule.

    `coach_prior` is the selected estimator for three of the five metrics, so
    this is a load-bearing prediction-time input, not a convenience.
    """
    import glob
    snaps = sorted(glob.glob(str(_REPO / 'nfl' / 'vintage' / SCHED_GLOB)))
    if not snaps:
        return Outcome.blocked('NO_SCHEDULE_SNAPSHOT',
                               'no schedules artifact has been captured',
                               cause=Cause.DEPENDENCY)
    out = {}
    with gzip.open(snaps[-1], 'rt') as fh:
        for r in csv.DictReader(fh):
            if (r.get('season') != str(season) or r.get('week') != str(week)
                    or r.get('game_type') != 'REG'):
                continue
            for side in ('home', 'away'):
                t, c = r.get(f'{side}_team'), (r.get(f'{side}_coach') or '')
                if t and c.strip():
                    out[t] = c.strip()
    if not out:
        return Outcome.blocked(
            'NO_COACH_FOR_SLATE',
            f'the captured schedule carries no head coach for {season} week '
            f'{week}; three of five volume metrics select coach_prior, so an '
            f'absent coach is a missing model input rather than a cosmetic gap',
            cause=Cause.DATA)
    return Outcome.ok('COACHES_RESOLVED', value=out, n_teams=len(out),
                      snapshot=os.path.basename(snaps[-1]))


def selected(metric, season):
    """The estimator and form chosen by the frozen research walk-forward.

    Read, never re-chosen. The latest evaluated season's selection is used for
    a season the research never evaluated, which is the same rule the research
    applied to itself: choose on prior seasons only.
    """
    res = json.loads(RESULTS.read_text())[metric]
    ev = max(int(k) for k in res if int(k) < season)
    r = res[str(ev)]
    return {'estimator': r['point_estimator'],
            'form': r.get('form_C') or r.get('form_B') or 'empirical',
            'selected_on_season': ev}


# PER-SLATE FIT CACHE (s.J). The fit depends ONLY on history -- the attached
# panel, the league mean and the residual pools -- and not on which teams are
# being forecast. So it can be computed once per (season, week, metric) and
# reused across all 16 games, while `V.draw` still runs per game with the same
# rng seed and the same row count as before.
#
# THIS IS WHY IT IS DRAW-EQUIVALENT: nothing cached touches the random stream.
# A cache that also hoisted the draw would change every number, because the rng
# is consumed row by row; that version was rejected rather than shipped.
_FIT_CACHE: dict = {}


def _fit_for(metric, season, week, ordinal):
    key = (metric, season, week)
    if key in _FIT_CACHE:
        return _FIT_CACHE[key]
    import p4b_volume as V
    sel = selected(metric, season)
    panel = _panel()
    hist = [r for r in panel if r['ord'] < ordinal and r[metric] > 0]
    lm = float(np.mean([r[metric] for r in hist]))
    _FIT_CACHE[key] = (sel, panel, lm, None)
    return _FIT_CACHE[key]


def cache_clear():
    _FIT_CACHE.clear()


# J1: the five metrics were drawn INDEPENDENTLY -- a separate RNG stream per
# metric -- which reproduced corr(team_carries, team_dropbacks) = -0.004
# against a historical -0.393. J1 tested four architectures walk-forward over
# 2,174 team-games and the winner was the cheapest: draw ONE historical
# team-game index per simulation draw and take every residual from that same
# game. Marginals are untouched to three decimal places, the accounting
# invariants go to zero, clipping goes to zero, and the reproduced correlation
# becomes -0.406.
#
# IT IS OFF BY DEFAULT AND THAT IS DELIBERATE. No fit changes, but every drawn
# number changes, so switching it on is an owner decision rather than an
# engineering one. See nfl/research/j1/J1_FINDING.md.
JOINT_RESIDUALS_DEFAULT = False

# ---------------------------------------------------------------------------
# A3G: the GAME-level extension of A3. Owner ruling B10.
#
# A3 made the five metrics of ONE TEAM share a historical team-game index. It
# left the two teams of a game drawn independently, which is what B10 names:
#
#     within-game corr(home, away)   historical      A3 as it stands
#     team_off_snaps                 -0.4647         ~-0.008
#     team_carries                   -0.5347         ~+0.015
#
#     SD(total game plays)           9.265           12.32   (+33%)
#     drawn games outside the entire 2020-2025 observed range [106, 173]: 2.00%
#
# Two percent of simulated games are longer or shorter than any NFL game of the
# last six seasons. That is not a correlation nicety; it is a distributional
# impossibility manufactured by drawing two dependent quantities apart.
#
# THE MECHANISM IS A RANK COPULA ON THE INDEX, AND IT MOVES NO MARGINAL.
# Each side still resamples from its OWN coach pool. All that changes is WHICH
# key each side receives: a bivariate normal (z_A, z_B) with correlation `rho`
# is mapped to uniforms, and side s takes the pool key at ordinal position
# floor(u_s * n_s) in its own pool ordered by a coupling score. u_s is exactly
# Uniform(0,1), so floor(u_s * n_s) is exactly uniform on {0..n_s-1} -- the
# same law as the incumbent `rng.integers(0, n_s, m)`. The marginal is
# preserved BY CONSTRUCTION, not by measurement, and nothing is clipped,
# truncated or renormalised to make that true.
#
# `rho` IS ESTIMATED, NEVER CHOSEN. See `coupling_rho`. There is no other
# parameter in this mechanism.
#
# IT IS OFF BY DEFAULT and requires the caller to declare the pairs. A slate is
# a list of teams; which two of them are playing each other is knowledge this
# module does not have and must not guess.
#
# Pre-registration: nfl/research/a3g/predeclaration_a3g.md
GAME_COUPLINGS = ('none', 'off_snaps', 'zmean', 'pc1')
GAME_COUPLING_DEFAULT = 'none'

# A frozen stream integer for the game-coupling normals, in the same spirit as
# the 4242 above. It is NOT in nfl/production/seeds.py because that table is
# frozen and append-only and this mode is not yet promoted; if the lead adopts
# the mode, the id moves there.
_COUPLING_STREAM = 4243


def _pair_stream(lo: str, hi: str) -> int:
    """A per-game substream integer that is the same in every process.

    Python's builtin `hash()` of a string is randomised per process, which is
    the exact defect nfl/production/seeds.py exists to end. crc32 is not a
    hash of convenience here -- it is a fixed, published, deterministic
    function of the two team codes, so two games on one slate get different
    normals and the same game gets the same normals on every run.
    """
    return int(zlib.crc32(f'{lo}|{hi}'.encode()) & 0x7FFFFFFF)


_ERFC = np.frompyfunc(math.erfc, 1, 1)


def _norm_cdf(z):
    """Phi(z), exactly, with no scipy on this box and no approximation."""
    return _ERFC(-np.asarray(z, float) / math.sqrt(2.0)).astype(float) / 2.0


def _rank_avg(x):
    """Ranks with ties averaged. Spearman needs this and numpy has no rankdata."""
    x = np.asarray(x, float)
    order = np.argsort(x, kind='stable')
    r = np.empty(len(x), float)
    r[order] = np.arange(len(x), dtype=float)
    # average the ranks inside each tied run
    s = x[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return r


# ----------------------------------------------------------------- guards
# Each of these is a module-level function returning an Outcome or None, so
# nfl/tests/bypass.py can replace it with a permissive stub and prove the
# refusal came from the guard rather than from something downstream.

def assert_coupling_is_declared(game_coupling):
    if game_coupling not in GAME_COUPLINGS:
        return Outcome.fail(
            'GAME_COUPLING_UNKNOWN',
            f'{game_coupling!r} is not a declared coupling; the declared ones '
            f'are {list(GAME_COUPLINGS)}. An unknown name is refused rather '
            f'than defaulted to none, because a typo that silently disables '
            f'the coupling would be reported as a run that had it on.')
    return None


def assert_coupling_has_joint_index(game_coupling, joint):
    if game_coupling != 'none' and not joint:
        return Outcome.fail(
            'GAME_COUPLING_WITHOUT_JOINT_INDEX',
            'game coupling permutes the shared historical team-game index, '
            'and the independent per-metric mode has no such index. Asking '
            'for one without the other is a contradiction, not a no-op.')
    return None


def assert_pairs_are_usable(game_coupling, game_pairs, teams):
    """Pairs must exist, be pairs, name teams on the slate, and not repeat."""
    if game_coupling == 'none':
        return None
    if not game_pairs:
        return Outcome.fail(
            'GAME_COUPLING_WITHOUT_PAIRS',
            'a coupling was requested but no game_pairs were supplied. This '
            'module is given a list of teams and cannot infer which two of '
            'them are playing each other. Silently coupling nothing would '
            'report a coupled run that was not coupled.')
    seen, tset = set(), set(teams)
    for pr in game_pairs:
        if len(tuple(pr)) != 2:
            return Outcome.fail(
                'GAME_PAIR_MALFORMED',
                f'{pr!r} is not a pair of two teams')
        a, b = tuple(pr)
        if a == b:
            return Outcome.fail('GAME_PAIR_SELF',
                                f'{a} cannot be paired with itself')
        for t in (a, b):
            if t not in tset:
                return Outcome.fail(
                    'GAME_PAIR_TEAM_NOT_ON_SLATE',
                    f'{t} appears in game_pairs but not in the teams supplied '
                    f'to this call')
            if t in seen:
                return Outcome.fail(
                    'GAME_PAIR_TEAM_REPEATED',
                    f'{t} appears in more than one pair')
            seen.add(t)
    return None


# ------------------------------------------------------- coupling machinery

def coupling_scores(kind, keyed, common):
    """One scalar per historical pool key: the axis the coupling acts on.

    The score is a property of a historical team-game, so ordering a pool by it
    is a permutation of that pool. It moves no mass.
    """
    if kind == 'off_snaps':
        return Outcome.ok('COUPLING_SCORE_OFF_SNAPS',
                          value={k: float(keyed['team_off_snaps'][k])
                                 for k in common},
                          detail='the team_off_snaps residual')
    Z = np.empty((len(common), len(METRICS)), float)
    for j, met in enumerate(METRICS):
        col = np.array([keyed[met][k] for k in common], float)
        sd = float(col.std(ddof=0))
        if not np.isfinite(sd) or sd == 0.0:
            return Outcome.blocked(
                'COUPLING_SCORE_DEGENERATE',
                f'{met} has zero spread across the {len(common)} pooled '
                f'team-games, so it cannot be standardised', cause=Cause.DATA)
        Z[:, j] = (col - col.mean()) / sd
    if kind == 'zmean':
        s = Z.mean(axis=1)
        ev = {'loadings': {m: 1.0 / len(METRICS) for m in METRICS}}
    elif kind == 'pc1':
        C = np.corrcoef(Z, rowvar=False)
        w, v = np.linalg.eigh(C)
        vec = v[:, int(np.argmax(w))]
        if vec[METRICS.index('team_off_snaps')] < 0:
            vec = -vec
        s = Z @ vec
        ev = {'loadings': {m: float(vec[j]) for j, m in enumerate(METRICS)},
              'explained_variance_share': float(np.max(w) / np.sum(w))}
    else:
        return Outcome.fail('COUPLING_SCORE_UNKNOWN', f'{kind!r}')
    return Outcome.ok(f'COUPLING_SCORE_{kind.upper()}',
                      value={k: float(s[i]) for i, k in enumerate(common)},
                      detail=f'{kind} over {len(common)} pooled team-games',
                      **ev)


def coupling_rho(score, common, opponent_of):
    """Estimate the copula correlation from historical PAIRED games.

    Spearman on the symmetrised sample -- each game contributes (A,B) and
    (B,A), so the estimate cannot depend on which side is called home -- then
    the standard Gaussian-copula inversion rho = 2 sin(pi rho_s / 6).

    This is the ONLY parameter of the mechanism and it is read out of history.
    """
    have = set(common)
    x, y = [], []
    for k in common:
        opp = opponent_of.get(k)
        if opp is None:
            continue
        k2 = (opp, k[1])
        if k2 in have:
            x.append(score[k])
            y.append(score[k2])
    n_ordered = len(x)
    if n_ordered < 2:
        return Outcome.blocked(
            'COUPLING_NO_PAIRED_HISTORY',
            f'only {n_ordered} historical team-game(s) have their opponent in '
            f'the same residual pool, so the within-game dependence cannot be '
            f'estimated. An unestimable parameter is a refusal, not a zero.',
            cause=Cause.DATA)
    rs = float(np.corrcoef(_rank_avg(x), _rank_avg(y))[0, 1])
    if not np.isfinite(rs):
        return Outcome.blocked(
            'COUPLING_RHO_NOT_FINITE',
            'the rank correlation of the paired scores is not finite',
            cause=Cause.DATA)
    rho = 2.0 * math.sin(math.pi * rs / 6.0)
    return Outcome.ok('COUPLING_RHO_ESTIMATED', value=rho,
                      detail=f'rho={rho:.4f} from rho_spearman={rs:.4f} on '
                             f'{n_ordered // 2} paired games',
                      rho_spearman=rs, rho_gaussian=rho,
                      paired_games=n_ordered // 2,
                      ordered_pairs=n_ordered)


def coupled_index(u, pool_keys, score):
    """The pool position each draw receives: floor(u * n) in score order.

    EXACTLY uniform over the n pool keys because u is exactly Uniform(0,1).
    The sort key carries the pool key itself so that float ties resolve the
    same way on every run and in every process.
    """
    n = len(pool_keys)
    order = sorted(range(n), key=lambda j: (score[pool_keys[j]], pool_keys[j]))
    pos = np.minimum((np.asarray(u, float) * n).astype(np.int64), n - 1)
    return np.asarray(order, np.int64)[pos]


def forecast(season: int, week: int, teams, m: int = 200,
             seed: int = 20260908, joint_residuals: bool = None,
             game_pairs=None, game_coupling: str = None) -> Outcome:
    """Prospective team-volume draws for one slate. Returns (metric, team) ->
    an (m,) draw vector.

    `joint_residuals` selects the J1 draw mode. None means the module default.

    `game_coupling` selects the A3G within-game mode and defaults to `'none'`,
    which reproduces the previous draws bit for bit. Anything else requires
    `joint_residuals` and requires `game_pairs` -- an explicit list of
    `(team, team)` tuples saying which two teams on this slate are playing each
    other. See GAME_COUPLINGS and the block above.
    """
    import p4b_volume as V
    game_coupling = (GAME_COUPLING_DEFAULT if game_coupling is None
                     else game_coupling)
    _g = assert_coupling_is_declared(game_coupling)
    if _g is not None:
        return _g
    if not teams:
        return Outcome.blocked('TEAM_VOLUME_NO_TEAMS',
                               'no teams supplied for the slate',
                               cause=Cause.DATA)
    co = coaches(season, week)
    if co.state.name != 'PASS':
        return co
    panel = _panel()
    ordinal = season * 100 + week
    if any(r['ord'] >= ordinal for r in panel):
        return Outcome.fail(
            'TEAM_VOLUME_HISTORY_NOT_STRICTLY_EARLIER',
            f'the volume panel already contains rows at or after ordinal '
            f'{ordinal}')
    missing = [t for t in teams if t not in co.value]
    if missing:
        return Outcome.blocked(
            'NO_COACH_FOR_SLATE',
            f'no head coach resolved for {missing}', cause=Cause.DATA,
            teams=missing)
    joint = (JOINT_RESIDUALS_DEFAULT if joint_residuals is None
             else bool(joint_residuals))
    for _g in (assert_coupling_has_joint_index(game_coupling, joint),
               assert_pairs_are_usable(game_coupling, game_pairs, teams)):
        if _g is not None:
            return _g
    out, meta = {}, {}
    fits = {}
    for metric in METRICS:
        sel, panel_c, lm, fit_c = _fit_for(metric, season, week, ordinal)
        pros = [{'season': season, 'week': week, 'ord': ordinal, 'team': t,
                 'coach': co.value[t], **{k: 0 for k in METRICS}}
                for t in teams]
        rows = sorted([dict(r) for r in panel_c] + pros,
                      key=lambda x: (x['ord'], x['team']))
        V.attach(rows, metric)                      # the FROZEN research cut
        hist = [r for r in rows if r['ord'] < ordinal and r[metric] > 0]
        for r in rows:
            r['_b'] = V.baselines(r, lm)
        for r in hist:
            r['_resid'] = r[metric] - r['_b'][sel['estimator']]
        # The fit is history-only: `hist` and every `_resid` in it are
        # unaffected by which teams are prospective, because attach processes
        # in ordinal order and the prospective rows sort last. So it is
        # identical across the 16 games of a slate and is computed once.
        fit = fit_c if fit_c is not None else V.build_forms(hist, metric,
                                                            V.SEED)
        _FIT_CACHE[(metric, season, week)] = (sel, panel_c, lm, fit)
        pr = [r for r in rows if r['ord'] == ordinal]
        fits[metric] = (sel, fit, pr, hist)
        if joint:
            continue                      # assembled jointly, below
        # STABLE STREAM IDENTITY -- see nfl/production/seeds.py. This was
        # `hash(metric) % 9973`, which changed every process.
        _sid = SEEDS.stream_id('team_volume', metric)
        if _sid.state is not State.PASS:
            return _sid
        rng = np.random.default_rng([seed, ordinal, _sid.value])
        res = V.draw(sel['form'], fit, pr, rng)[:, :m]
        for i, r in enumerate(pr):
            out[(metric, r['team'])] = np.maximum(
                r['_b'][sel['estimator']] + res[i], 0.0)
        meta[metric] = {**sel, 'league_mean': lm, 'n_train': len(hist),
                        'negative_draws_clipped_to_zero': int(
                            (np.array([r['_b'][sel['estimator']]
                                       for r in pr]).reshape(-1, 1)
                             + res < 0).sum())}
    if joint:
        # ONE historical team-game per draw, every residual from that game.
        #
        # THE INDEX MUST BE DRAWN FROM THE SAME POOL THE FITTED FORM USES.
        # All five metrics select `coach_empirical`, so the residual for a
        # prospective row is resampled from THAT COACH's residuals. A first
        # version of this drew the shared index from the global pool, which is
        # a different distribution: it moved the team_rz_carries mean by 5.2%
        # and put 0.49% of its draws on the zero floor, while claiming no
        # marginal had been touched. Sharing an index across metrics is only
        # legitimate if each metric still draws from its own fitted pool.
        keyed = {}
        for metric, (sel, fit, pr, hist) in fits.items():
            keyed[metric] = {(h['team'], h['ord']):
                             h[metric] - h['_b'][sel['estimator']]
                             for h in hist}
        common = [k for k in keyed[METRICS[0]]
                  if all(k in keyed[mm] for mm in METRICS)]
        if not common:
            return Outcome.fail(
                'JOINT_RESIDUAL_POOL_EMPTY',
                'no historical team-game carries a residual for every metric, '
                'so a joint resample is impossible')
        coach_of = {}
        for _m, (_s, _f, _p, hh) in fits.items():
            for h in hh:
                coach_of[(h['team'], h['ord'])] = h.get('coach')
        by_coach = {}
        for k in common:
            by_coach.setdefault(coach_of.get(k), []).append(k)
        # A3G. `u_by_team` is empty unless a coupling was asked for, and the
        # `rng.integers` path below is then reached for every row in the same
        # order as before, so game_coupling='none' is bit-identical to J1.
        score, cmeta, u_by_team = None, {}, {}
        if game_coupling != 'none':
            opponent_of = {}
            for _m2, (_s2, _f2, _p2, hh) in fits.items():
                for h in hh:
                    opponent_of[(h['team'], h['ord'])] = h.get('opponent')
            sc = coupling_scores(game_coupling, keyed, common)
            if sc.state is not State.PASS:
                return sc
            score = sc.value
            rh = coupling_rho(score, common, opponent_of)
            if rh.state is not State.PASS:
                return rh
            rho = float(rh.value)
            cmeta = {'game_coupling': game_coupling,
                     'rho_gaussian': rho,
                     'rho_spearman': rh.evidence['rho_spearman'],
                     'coupling_paired_games': rh.evidence['paired_games'],
                     'coupling_score_evidence': {
                         k: v for k, v in sc.evidence.items()
                         if k in ('loadings', 'explained_variance_share')}}
            root = math.sqrt(max(0.0, 1.0 - rho * rho))
            for _pair in game_pairs:
                lo, hi = sorted(tuple(_pair))
                grng = np.random.default_rng(
                    [seed, ordinal, _COUPLING_STREAM, _pair_stream(lo, hi)])
                z1 = grng.standard_normal(m)
                z2 = rho * z1 + root * grng.standard_normal(m)
                u_by_team[lo] = _norm_cdf(z1)
                u_by_team[hi] = _norm_cdf(z2)
        rng = np.random.default_rng([seed, ordinal, 4242])
        pr0 = fits[METRICS[0]][2]
        n_fallback = n_coupled = 0
        for i, r0 in enumerate(pr0):
            pool_keys = by_coach.get(r0.get('coach'))
            if not pool_keys:
                pool_keys = common          # the same fallback V.draw uses
                n_fallback += 1
            u = u_by_team.get(r0['team'])
            if u is None:
                pick = rng.integers(0, len(pool_keys), m)
            else:
                pick = coupled_index(u, pool_keys, score)
                n_coupled += 1
            chosen = [pool_keys[j] for j in pick]
            for metric in METRICS:
                sel, fit, pr, _h = fits[metric]
                res_v = np.array([keyed[metric][k] for k in chosen])
                out[(metric, pr[i]['team'])] = np.maximum(
                    pr[i]['_b'][sel['estimator']] + res_v, 0.0)
        for metric, (sel, fit, pr, hist) in fits.items():
            meta[metric] = {**sel, 'league_mean': lm, 'n_train': len(hist),
                            'draw_mode': 'joint_residuals',
                            'joint_pool_team_games': len(common),
                            'coaches_with_a_pool': len(by_coach),
                            'rows_on_global_fallback': n_fallback,
                            'rows_game_coupled': n_coupled,
                            'rows_not_game_coupled': len(pr0) - n_coupled,
                            **cmeta}
    return Outcome.ok('TEAM_VOLUME_OK', value=out,
                      detail=f'{len(teams)} team(s), {len(METRICS)} metrics, '
                             f'{m} draws',
                      spec_version=SPEC_VERSION, selections=meta,
                      draw_mode=('joint_residuals' if joint
                                 else 'independent_per_metric'),
                      game_coupling=game_coupling,
                      coach_snapshot=co.evidence['snapshot'],
                      known_limitations=list(KNOWN_LIMITATIONS))
