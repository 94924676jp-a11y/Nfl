"""V1 production: the A1 single-owner rushing allocator.

WHAT THIS IS, AND WHAT IT IS NOT

This is ENGINEERING INTEGRATION of an already-validated research architecture.
Nothing here is fitted, searched or swept. The estimator family, the category
set, the shrinkage constant and the half-life are OWN-9's, imported from
`nfl/research/own9/a1_lib.py` rather than retyped, so a drift between the
production allocator and the arm that was scored is a broken import instead of
a silent divergence.

Promotion is NOT claimed. `PATH_C_STATE` is untouched by this module.

THE OWNERSHIP GRAPH, frozen by OWN-8 (predeclaration sha256 90f6ecc3...)

    team_carries                      D1 -- ONE level, exactly one owner
      |- scrambles                    DROPBACK-owned. Comes from the QB layer.
      |                               This module NEVER draws or re-draws it;
      |                               it is a PRIOR CLAIM that is subtracted.
      `- rush_play_budget = team_carries - scrambles
           |- kneel                   carry-owned, EXPLICIT, never folded
           |- designed_qb             carry-owned  (A0 drew this on DROPBACKS,
           |                          which is the sign error OWN-8 proved)
           |- rb
           |- wr
           |- te
           `- fringe                  a NAMED residual, never a silent drop

A1 partitions `rush_play_budget` across those six categories with ONE
multinomial per draw. Every carry therefore lands in exactly one category BY
CONSTRUCTION, not by reconciliation afterwards. There is no clipping, no
survivor renormalisation, no dumping of an overflow into `fringe`, and no
deletion of a violating draw. Those are the four repairs OWN-8 forbids and
none of them exists in this file.

WHAT A1 DOES NOT DO

*   It does not touch scrambles. They arrive as a level and leave unchanged.
*   It does not carry a latent. A2 -- one per-team-game latent on the
    designed-QB share -- was built, scored on a pre-registered grid and
    REJECTED by OWN-10: the criterion is optimised at tau = 0, which is A1.
    `A2_LATENT_REJECTED` is asserted by the test suite so a future edit that
    reopens it fails loudly rather than arriving unannounced.

THE ONE FLOOR IN HERE, NAMED RATHER THAN HIDDEN

The share for a category is `max(centre + additive_residual, 0)`. That floor is
inherited from `a1_lib.draw_a1` unchanged and is COUNTED in the evidence as
`share_floor_binds`. It moves a probability, never a carry: closure is enforced
by the multinomial on the same budget regardless of what the share vector is.
OWN-10 section 3 diagnoses it as a mis-specification of the residual family for
small-share categories (it binds 20.68% of share draws league-wide, against
0.07% for RB) and offers it as the successor candidate. It is left exactly as
scored, because changing it here would make this an unregistered refit.

INTERFACE THE ENGINE CALLS

    par = rushing_a1.params(season, week)          # frozen, chronological
    out = rushing_a1.allocate(
        season, week, teams,
        team_carries_draws={team: (m,) array},     # D1 level, per draw
        scramble_draws={team: (m,) array},         # QB layer, per draw
        m=m, seed=seed, params=par.value, game_id=game_id,
        level_rounding=None)

`out.value['carries'][(team, category)]` is an (m,) int64 vector.

LEVELS ARE NOT THIS MODULE'S TO ROUND. `team_volume_v1.forecast` returns
CONTINUOUS draws. A multinomial needs an integer budget, and turning a level
into a count is a D1 decision, not an allocation decision. So a non-integer
input is REFUSED by default and the caller must declare `level_rounding` to opt
in, which is then counted in the evidence. Silently rounding somebody else's
level is how a layer starts owning a quantity it was not given.
"""
from __future__ import annotations

import glob as _glob
import hashlib
import json
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
_OWN9 = _REPO / 'nfl' / 'research' / 'own9'
for _q in (str(_REPO), str(_OWN9)):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import (Cause, Outcome,    # noqa: E402
                                               State)
from nfl.production import derived as DERIVED                     # noqa: E402
from nfl.production import seeds as SEEDS                         # noqa: E402

import a1_lib as A                                                # noqa: E402

SPEC_VERSION = 'rushing-a1-production-v1'

# --- inherited, not re-chosen. Imported so a drift is an ImportError. -------
CATEGORIES = A.CATEGORIES            # kneel designed_qb rb wr te fringe
K_SHRINK = A.K_SHRINK                # 4.0, P4C's constant
EWMA_HALFLIFE = A.EWMA_HALFLIFE      # 2.0, Stage-2's accepted half-life
EPS = A.EPS

# scrambles are DROPBACK-owned; they are not a category this module partitions
DROPBACK_OWNED = ('scramble',)
# OWN-10: the latent was built, scored and rejected. Do not reopen.
A2_LATENT_REJECTED = True

PREDECLARATION = _REPO / 'nfl' / 'research' / 'own8' / 'predeclaration_own8.md'
PREDECLARATION_SHA256 = (
    '90f6ecc37bcee427177f183be03374c13ec87fe1e14d667a4457c797748789db')

# The pbp source is not committed to this repository -- see `pbp_sources`.
PBP_GLOB_ENV = ('NFL_A1_PBP_GLOB', 'INTEL1_PBP_GLOB')
PARAMS_ENV = 'NFL_A1_PARAMS'

# --- stream identity -------------------------------------------------------
# `seeds.py` is the registry and this task may not edit it, so the namespace
# below is NOT declared there yet. That is recorded as a DEFERRED debt by
# `registry_debt()` rather than left implicit, and the component is derived the
# way `seeds.game_component` derives an open-set id: sha256 over the seed
# contract. Python's builtin hash() appears nowhere in this file -- the test
# suite proves that on the AST, not on the text.
STREAM_NAMESPACE = 'rushing_a1'
STREAMS = {'rush_play_budget_partition': 1}

_PARAM_CACHE: dict = {}


# ---------------------------------------------------------------- provenance
def _sha_file(p) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def predeclaration() -> Outcome:
    """Refuse to run against a modified OWN-8 pre-registration."""
    if not PREDECLARATION.exists():
        return Outcome.blocked(
            'A1_PREDECLARATION_ABSENT',
            f'{PREDECLARATION} is not present, so the ownership graph this '
            f'module implements cannot be shown to be the one that was '
            f'registered.', cause=Cause.DATA)
    got = _sha_file(PREDECLARATION)
    if got != PREDECLARATION_SHA256:
        return Outcome.fail(
            'A1_PREDECLARATION_MODIFIED',
            f'the OWN-8 pre-registration hashes to {got}, not '
            f'{PREDECLARATION_SHA256}. The allocator implements a frozen '
            f'graph; if the graph moved, this module is implementing a '
            f'different experiment than the one that was scored.',
            got=got, want=PREDECLARATION_SHA256)
    return Outcome.ok('A1_PREDECLARATION_UNMODIFIED', value=got,
                      detail='ownership graph frozen by OWN-8')


def estimator_identity() -> dict:
    """Exactly what this allocator inherits, and from which bytes."""
    return {
        'spec_version': SPEC_VERSION,
        'family': 'league share + additive residual pool + team ewma shrunk '
                  'by n/(n+K)',
        'categories': list(CATEGORIES),
        'k_shrink': float(K_SHRINK),
        'ewma_halflife': float(EWMA_HALFLIFE),
        'reference_implementation': 'nfl/research/own9/a1_lib.py',
        'reference_sha256': _sha_file(A.__file__.replace('.pyc', '.py')),
        'predeclaration_sha256': PREDECLARATION_SHA256,
        'dropback_owned': list(DROPBACK_OWNED),
        'a2_latent_rejected': A2_LATENT_REJECTED,
        'fitted_here': [],
        'clipping': 'none', 'survivor_renormalisation': 'none',
        'post_hoc_repair': 'none',
    }


def registry_debt() -> Outcome:
    """The seed namespace is not in `nfl/production/seeds.py`. Say so.

    DEFERRED, not PASS and not a quiet fallback: the stream is deterministic
    today, and it still OWES an entry in the one table a reader is supposed to
    be able to check by eye.
    """
    probe = SEEDS.stream_id(STREAM_NAMESPACE, next(iter(STREAMS)))
    if probe.state is State.PASS:
        return Outcome.ok('A1_SEED_NAMESPACE_DECLARED', value=probe.value,
                          detail=f'{STREAM_NAMESPACE} resolves from the '
                                 f'registry')
    return Outcome.deferred(
        'A1_SEED_NAMESPACE_NOT_IN_REGISTRY',
        f'{STREAM_NAMESPACE!r} is not a declared namespace in '
        f'nfl/production/seeds.py ({probe.code}). The component is derived '
        f'deterministically by sha256 over the seed contract, exactly as '
        f'seeds.game_component derives an open-set id, so no draw depends on '
        f'Python hash(). The debt is the registry entry itself.',
        owed=f'add STREAMS[{STREAM_NAMESPACE!r}] = {STREAMS!r} to '
             f'nfl/production/seeds.py, appending the next free integer',
        probe_code=probe.code, uses_python_hash=False)


def _sha_component(*parts: str) -> int:
    d = hashlib.sha256(
        ('|'.join((SEEDS.SEED_CONTRACT,) + parts)).encode()).digest()
    return int.from_bytes(d[:4], 'big')


def stream_component(name: str = 'rush_play_budget_partition') -> Outcome:
    """A stable integer for one named A1 stream. Refuses an unknown name."""
    sid = STREAMS.get(name)
    if sid is None:
        return Outcome.fail(
            'A1_STREAM_UNDECLARED',
            f'{name!r} has no declared A1 stream id. Declared: '
            f'{sorted(STREAMS)}. Refusing rather than defaulting, because two '
            f'layers sharing a stream is a correlation nobody declared.',
            known=sorted(STREAMS))
    reg = SEEDS.stream_id(STREAM_NAMESPACE, name)
    if reg.state is State.PASS:
        return Outcome.ok('A1_STREAM_ID', value=int(reg.value),
                          detail=f'{STREAM_NAMESPACE}/{name} from the registry',
                          source='seeds.STREAMS',
                          derived_from_python_hash=False)
    return Outcome.ok(
        'A1_STREAM_ID', value=_sha_component(STREAM_NAMESPACE, name, str(sid)),
        detail=f'{STREAM_NAMESPACE}/{name} derived by sha256 over the seed '
               f'contract; the registry entry is OWED (see registry_debt)',
        source='sha256(seed_contract|namespace|name|id)',
        derived_from_python_hash=False, stable_across_processes=True,
        registry_entry_owed=True)


def team_component(team: str) -> Outcome:
    """A stable integer per team. sha256, never Python hash()."""
    if not team or not isinstance(team, str):
        return Outcome.fail(
            'A1_TEAM_ID_MISSING',
            f'a per-team stream component needs a team; got {team!r}. '
            f'Refusing rather than defaulting to a shared stream.', team=team)
    return Outcome.ok('A1_TEAM_COMPONENT', value=_sha_component('team', team),
                      detail=f'{team} -> stable 32-bit component',
                      derived_from_python_hash=False,
                      stable_across_processes=True)


def seed_contract() -> dict:
    return {'seed_contract': SEEDS.SEED_CONTRACT,
            'namespace': STREAM_NAMESPACE, 'streams': dict(STREAMS),
            'uses_python_hash': False,
            'declared_in_seeds_registry':
                SEEDS.stream_id(STREAM_NAMESPACE,
                                next(iter(STREAMS))).state is State.PASS,
            'stable_across': ['process', 'machine', 'invocation order',
                              'PYTHONHASHSEED']}


# ---------------------------------------------------------------- the inputs
def pbp_sources() -> Outcome:
    """The historical play-by-play the frame is built from, or a named block.

    Play-by-play is NOT committed to this repository. It is resolved from
    `NFL_A1_PBP_GLOB` (or the project's existing `INTEL1_PBP_GLOB`). When it is
    absent this BLOCKS with cause DATA and says exactly what is needed. It does
    not fall back to the panel: the panel carries no kneel column, so a frame
    built from it would have to fold kneels into an unnamed residual, which is
    the one thing OWN-8 section 2 forbids.
    """
    for env in PBP_GLOB_ENV:
        pat = os.environ.get(env, '')
        if not pat:
            continue
        files = sorted(_glob.glob(pat))
        if files:
            return Outcome.ok(
                'A1_PBP_SOURCES', value=files,
                detail=f'{len(files)} play-by-play file(s) from {env}',
                env=env, pattern=pat,
                sha256={os.path.basename(f): _sha_file(f)[:16] for f in files})
        return Outcome.blocked(
            'A1_PBP_GLOB_MATCHED_NOTHING',
            f'{env}={pat!r} matched no file. An empty match is an absence, '
            f'not an empty season.', cause=Cause.DATA, env=env, pattern=pat)
    return Outcome.blocked(
        'A1_PBP_SOURCE_NOT_LOCATED',
        f'set one of {PBP_GLOB_ENV} to the nflverse play-by-play files '
        f'(pbp{{season}}.csv.gz, seasons 2020..latest). The fields consumed '
        f'are season, week, posteam, season_type, two_point_attempt, '
        f'qb_dropback, passer_player_id, rush_attempt, rusher_player_id, '
        f'qb_scramble, qb_kneel. Nothing is stubbed and no substitute source '
        f'is used.', cause=Cause.DATA, checked=list(PBP_GLOB_ENV))


def positions() -> Outcome:
    """gsis_id -> position, resolved through the DERIVED artifact cache.

    Read-only, and through `nfl.production.derived.artifacts()` rather than by
    reaching into nfl/research, so production never depends on a research-tree
    copy. Identity is by id only; a rusher with no known position becomes
    FRINGE, which is a named category rather than a dropped carry.
    """
    import pickle
    ready = DERIVED.artifacts()
    if ready.state is not State.PASS:
        return ready
    p = pathlib.Path(ready.value) / 'panel_enriched.pkl'
    if not p.exists():
        return Outcome.blocked(
            'A1_PANEL_ABSENT', f'{p} is not in the verified derived cache',
            cause=Cause.DEPENDENCY)
    with open(p, 'rb') as fh:
        rows = pickle.load(fh)
    pos = {}
    for r in rows:
        g = r.get('gsis_id')
        if g and g not in pos and r.get('position'):
            pos[g] = r['position']
    if not pos:
        return Outcome.blocked(
            'A1_POSITIONS_EMPTY',
            f'{p} yielded no gsis_id -> position mapping. An empty mapping '
            f'would silently send every rusher to FRINGE.', cause=Cause.DATA)
    return Outcome.ok('A1_POSITIONS', value=pos,
                      detail=f'{len(pos)} player positions from the derived '
                             f'panel',
                      source=str(p), source_sha256=_sha_file(p)[:16],
                      n_rows=len(rows))


# ------------------------------------------------------------------ the fit
def _history_from_frame(frame, cut_ord: int):
    """Per-team prior category shares, ordinal prefix cut STRICTLY before cut.

    Identical in construction to `a1_lib.attach_prior`: `n` counts every prior
    team-game, the share series carries only games with a positive budget.

    Returns (history, highest_ordinal_consumed). The second value is returned
    rather than assumed so the caller can ASSERT the cut held, instead of
    trusting that the `continue` below is still there after a future edit.
    """
    hist: dict = {}
    hi = None
    for r in sorted(frame, key=lambda x: (x['ord'], x['team'])):
        if r['ord'] >= cut_ord:
            continue
        hi = r['ord'] if hi is None else max(hi, r['ord'])
        h = hist.setdefault(r['team'],
                            {'n': 0, **{c: [] for c in CATEGORIES}})
        h['n'] += 1
        if r['rush_play_budget'] > 0:
            for c in CATEGORIES:
                h[c].append(r[c] / r['rush_play_budget'])
    return hist, hi


def assert_frame_closes(frame):
    """team_carries - scramble == sum(categories), in the DATA, or a FAIL.

    Returns None when the frame closes, so a caller can write
    `g = assert_frame_closes(f); if g is not None: return g`. It is checked in
    BOTH entry points -- `build_frame` and a caller-supplied frame handed to
    `fit_frozen` -- because a frame that does not close would put a carry with
    no owner into the residual pool itself, and the per-draw counters
    downstream would report zero violations while the parameters were built on
    a broken ledger.
    """
    if not frame:
        return Outcome.blocked(
            'A1_FRAME_EMPTY',
            'the frame holds zero team-games. An empty frame is an absence, '
            'not a season with no rushing.', cause=Cause.DATA)
    resid = [r['team_carries'] - r['scramble'] - sum(r[c] for c in CATEGORIES)
             for r in frame]
    bad = sum(1 for v in resid if v != 0)
    if bad:
        return Outcome.fail(
            'A1_FRAME_CATEGORIES_DO_NOT_CLOSE',
            f'{bad} of {len(frame)} team-games do not satisfy '
            f'team_carries - scramble == sum(categories). The categorisation '
            f'must close in the DATA before any model runs.',
            n_bad=bad, max_abs=int(max(abs(v) for v in resid)))
    return None


def build_frame(pbp_files, pos) -> Outcome:
    """The per-team-game frame, every carry classified exactly once."""
    if not pbp_files:
        return Outcome.blocked('A1_FRAME_NO_SOURCES',
                               'no play-by-play file was supplied',
                               cause=Cause.DATA)
    frame = A.attach_prior(A.build_frame(list(pbp_files), pos))
    g = assert_frame_closes(frame)
    if g is not None:
        return g
    return Outcome.ok(
        'A1_FRAME', value=frame,
        detail=f'{len(frame)} team-games, categories close exactly',
        n_team_games=len(frame), closure_exact=len(frame), closure_max_abs=0,
        seasons=sorted({r['season'] for r in frame}))


def fit_frozen(season: int, week: int = 0, *, frame=None,
               pbp_files=None, pos=None, provenance=None) -> Outcome:
    """Frozen A1 parameters for a forecast at (season, week), chronologically.

    Two different cuts, and they are not the same cut:

    *   the LEAGUE share and the RESIDUAL POOL train on seasons STRICTLY
        BEFORE `season` -- `a1_lib.fit`, called unchanged;
    *   the per-team EWMA history is cut at ordinal `season * 100 + week`, so
        a mid-season forecast may use that season's completed weeks and never
        the week being forecast.

    2020-2021 are OWN-9's burn-in and are never an evaluation season here
    either; a request for one is refused rather than fitted on nothing.
    """
    if season <= 2021:
        return Outcome.blocked(
            'A1_SEASON_IS_BURN_IN',
            f'{season} is inside OWN-9 burn-in (2020-2021). A team cannot be '
            f'shown to have no prior history when the coverage itself is new, '
            f'so no burn-in season is fitted or scored.', cause=Cause.DATA)
    prov = {}
    if frame is not None:
        g = assert_frame_closes(frame)
        if g is not None:
            return g
        # A caller-supplied frame must still carry provenance. Recording only
        # "supplied by caller" would produce a frozen parameter file that
        # cannot say which bytes it came from, which is the whole point of
        # freezing it.
        prov = {'built_from': 'frame supplied by caller',
                'frame_team_games': len(frame),
                'frame_seasons': sorted({r['season'] for r in frame}),
                'frame_closure_exact': len(frame),
                **(dict(provenance) if provenance else {})}
        if not provenance:
            prov['provenance_gap'] = (
                'the caller supplied a frame and no source provenance, so '
                'these parameters cannot name the bytes they were fitted on')
    if frame is None:
        src = pbp_sources() if pbp_files is None else Outcome.ok(
            'A1_PBP_SOURCES', value=list(pbp_files), detail='caller supplied')
        if src.state is not State.PASS:
            return src
        p = positions() if pos is None else Outcome.ok(
            'A1_POSITIONS', value=dict(pos), detail='caller supplied')
        if p.state is not State.PASS:
            return p
        fr = build_frame(src.value, p.value)
        if fr.state is not State.PASS:
            return fr
        frame = fr.value
        prov = {'built_from': 'play-by-play',
                'pbp_files': [os.path.basename(f) for f in src.value],
                'pbp_sha256': {os.path.basename(f): _sha_file(f)
                               for f in src.value},
                'positions_source': p.evidence.get('source'),
                'positions_sha256': p.evidence.get('source_sha256'),
                'n_positions': len(p.value),
                'frame_team_games': fr.evidence['n_team_games'],
                'frame_closure_exact': fr.evidence['closure_exact']}
    par = A.fit(frame, season)
    if par is None:
        return Outcome.blocked(
            'A1_NO_TRAINING_SEASONS',
            f'no team-game strictly before {season} carries a positive rush '
            f'play budget, so there is nothing to fit.', cause=Cause.DATA,
            season=season)
    cut = season * 100 + int(week)
    hist, hi_ord = _history_from_frame(frame, cut)

    # LEAKAGE GUARD, asserted rather than assumed. Two cuts, both checked.
    leaked_season = [s for s in par['seasons_used'] if s >= season]
    leaked_ord = hi_ord is not None and hi_ord >= cut
    if leaked_season or leaked_ord:
        return Outcome.fail(
            'A1_CHRONOLOGY_VIOLATED',
            f'the fit consumed seasons {leaked_season} at or after the '
            f'forecast season {season}, or history at ordinal {hi_ord} at or '
            f'after the cut {cut}. A parameter set that has seen the week it '
            f'forecasts is not a forecast.',
            seasons_used=par['seasons_used'], highest_history_ord=hi_ord,
            history_cut_ord=cut)

    out = {
        'spec_version': SPEC_VERSION,
        'season': int(season), 'week': int(week), 'history_cut_ord': cut,
        'categories': list(CATEGORIES),
        'k_shrink': float(K_SHRINK), 'ewma_halflife': float(EWMA_HALFLIFE),
        'league': {c: float(par['league'][c]) for c in CATEGORIES},
        'resid': {c: np.asarray(par['resid'].get(c, np.zeros(0, np.float32)),
                                np.float32) for c in CATEGORIES},
        'history': hist,
        'n_train': int(par['n_train']),
        'seasons_used': [int(s) for s in par['seasons_used']],
        'estimator': estimator_identity(),
        'provenance': prov,
    }
    return Outcome.ok(
        'A1_PARAMS_FITTED', value=out,
        detail=f'season {season} week {week}: trained on '
               f'{out["seasons_used"]}, {out["n_train"]} team-games, history '
               f'cut at ordinal {cut}',
        seasons_used=out['seasons_used'], n_train=out['n_train'],
        n_teams_with_history=len(hist),
        history_cut_ord=cut, highest_history_ord=hi_ord,
        resid_pool_sizes={c: int(out['resid'][c].size) for c in CATEGORIES},
        consumed_outcome_at_or_after_cut=False)


def params_to_json(par) -> dict:
    d = dict(par)
    d['resid'] = {c: [float(x) for x in np.asarray(par['resid'][c])]
                  for c in CATEGORIES}
    return d


def params_from_json(d) -> dict:
    p = dict(d)
    p['resid'] = {c: np.asarray(d['resid'].get(c, []), np.float32)
                  for c in CATEGORIES}
    p['history'] = {t: {'n': int(h['n']),
                        **{c: list(h.get(c, [])) for c in CATEGORIES}}
                    for t, h in d.get('history', {}).items()}
    return p


def freeze(season: int, week: int = 0, dest=None, **kw) -> Outcome:
    """Fit and write the frozen parameters into PRODUCTION's own cache.

    The destination defaults to `derived.cache_dir()`, which is gitignored and
    production-owned. Nothing is written into nfl/research: a production run
    that mutates the research tree is a FAIL elsewhere in this suite, and this
    module must not be the thing that trips it.
    """
    fit = fit_frozen(season, week, **kw)
    if fit.state is not State.PASS:
        return fit
    d = pathlib.Path(dest) if dest else DERIVED.cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f'rushing_a1_params_{season}w{int(week):02d}.json'
    p.write_text(json.dumps(params_to_json(fit.value), indent=1,
                            sort_keys=True))
    return Outcome.ok('A1_PARAMS_FROZEN', value=str(p),
                      detail=f'{p.stat().st_size} bytes',
                      sha256=_sha_file(p), **fit.evidence)


def params(season: int, week: int = 0, *, path=None, **kw) -> Outcome:
    """Resolve frozen parameters. Explicit path, env, cache, then fit.

    Memoised per (season, week) in-process. `cache_clear()` resets it.
    """
    key = (int(season), int(week))
    if key in _PARAM_CACHE and path is None:
        return Outcome.ok('A1_PARAMS_CACHED', value=_PARAM_CACHE[key],
                          detail=f'in-process cache for {key}', cached=True)
    cand = []
    if path:
        cand.append(pathlib.Path(path))
    if os.environ.get(PARAMS_ENV):
        cand.append(pathlib.Path(os.environ[PARAMS_ENV]))
    cand.append(DERIVED.cache_dir()
                / f'rushing_a1_params_{season}w{int(week):02d}.json')
    for c in cand:
        if not c.exists():
            continue
        d = json.loads(c.read_text())
        if int(d.get('season', -1)) != int(season):
            return Outcome.fail(
                'A1_PARAMS_SEASON_MISMATCH',
                f'{c} carries season {d.get("season")}, not {season}. A '
                f'parameter file for the wrong season would silently make the '
                f'forecast chronologically invalid.', path=str(c))
        p = params_from_json(d)
        _PARAM_CACHE[key] = p
        return Outcome.ok('A1_PARAMS_LOADED', value=p,
                          detail=f'frozen parameters from {c}',
                          path=str(c), sha256=_sha_file(c)[:16],
                          seasons_used=d.get('seasons_used'))
    fit = fit_frozen(season, week, **kw)
    if fit.state is not State.PASS:
        return fit
    _PARAM_CACHE[key] = fit.value
    return fit


# `allocate` takes a keyword called `params`, which shadows the resolver above
# inside its body. The alias makes the call site say what it means instead of
# reaching into globals().
resolve_params = params


def cache_clear():
    _PARAM_CACHE.clear()


# ------------------------------------------------------------- the allocator
def _centre(hist_row, cat, league) -> float:
    """The team's own prior ewma shrunk toward the league share, n/(n+K).

    `a1_lib._centre` is called, not reimplemented.
    """
    return float(A._centre(hist_row, cat, {'league': league}))


def _hist_row(par, team):
    h = par['history'].get(team)
    if h is None:
        return {'h_n': 0, **{f'h_{c}': [] for c in CATEGORIES}}, False
    return ({'h_n': int(h['n']),
             **{f'h_{c}': list(h.get(c, [])) for c in CATEGORIES}}, True)


def _shares(par, team, rng, m):
    """The (6, m) share matrix, built exactly as `a1_lib.draw_a1` builds it.

    Returns (p, n_floor_binds, n_degenerate). The category loop order, the
    residual resampling call and the degenerate handling are the reference
    implementation's, so the same rng state reproduces it bit for bit.
    """
    row, _known = _hist_row(par, team)
    p = np.empty((len(CATEGORIES), m), np.float64)
    floor_binds = 0
    for j, cat in enumerate(CATEGORIES):
        c = _centre(row, cat, par['league'])
        pool = par['resid'].get(cat)
        add = (pool[rng.integers(0, len(pool), m)]
               if pool is not None and len(pool) else np.zeros(m, np.float32))
        raw = c + add
        floor_binds += int((raw < 0).sum())
        p[j] = np.maximum(raw, 0.0)
    tot = p.sum(0)
    # A draw whose every category weight is zero has no partition to make. It
    # is NAMED and COUNTED and given to the fringe -- never silently rescaled.
    degenerate = tot <= EPS
    p[:, degenerate] = 0.0
    p[CATEGORIES.index('fringe'), degenerate] = 1.0
    tot = np.where(degenerate, 1.0, tot)
    return p / tot, floor_binds, int(degenerate.sum())


def _partition(par, team, budget, rng, m):
    """One multinomial per draw on that draw's own budget."""
    p, floor_binds, degenerate = _shares(par, team, rng, m)
    out = np.empty((len(CATEGORIES), m), np.int64)
    b = np.asarray(budget, np.int64)
    for j in range(m):
        out[:, j] = rng.multinomial(int(b[j]), p[:, j])
    return ({c: out[j] for j, c in enumerate(CATEGORIES)},
            floor_binds, degenerate)


def verify_allocation(alloc, budget, team_carries, scrambles) -> dict:
    """The hard requirements, COUNTED. Never repaired.

    Kept a module-level function on purpose so a bypass test can stub it and
    prove the counts in the evidence come from here rather than from an
    assumption. It returns counts; the caller decides what a non-zero count
    means. It changes nothing.
    """
    b = np.asarray(budget, np.int64)
    stack = np.vstack([np.asarray(alloc[c], np.int64) for c in CATEGORIES])
    total = stack.sum(0)
    return {
        'draws': int(b.size),
        'closure_violations': int((total != b).sum()),
        'negative_allocations': int((stack < 0).sum()),
        'category_budget_overruns': int((stack > b[None, :]).sum()),
        'ledger_violations': int(
            (total + np.asarray(scrambles, np.int64)
             != np.asarray(team_carries, np.int64)).sum()),
        'carries_with_no_owner': int(np.maximum(b - total, 0).sum()),
        'carries_with_two_owners': int(np.maximum(total - b, 0).sum()),
    }


def allocate(season: int, week: int, teams, team_carries_draws,
             scramble_draws, m: int = 200, seed: int = 20260908, *,
             params=None, game_id=None, level_rounding=None) -> Outcome:
    """Partition each team's rush-play budget across the six categories.

    Parameters
    ----------
    teams               sequence of team abbreviations on this slate.
    team_carries_draws  {team: (m,) array} -- the D1 team-carry level.
    scramble_draws      {team: (m,) array} -- the QB layer's scrambles,
                        DROPBACK-owned. Passed through untouched.
    params              a params dict from `params()` / `fit_frozen()`. When
                        omitted it is resolved for (season, week).
    level_rounding      None refuses a non-integer level. 'round_half_even'
                        is the caller DECLARING that rounding somebody else's
                        level is acceptable here; the moved cells are counted.

    Returns an Outcome whose value is

        {'carries': {(team, category): (m,) int64},
         'rush_play_budget': {team: (m,) int64},
         'team_carries': {team: (m,) int64},
         'scrambles': {team: (m,) int64},          # bit-identical to input
         'qb_rush_opportunity': {team: (m,) int64}}   # scramble + designed_qb
    """
    pre = predeclaration()
    if pre.state is not State.PASS:
        return pre
    if not teams:
        return Outcome.blocked(
            'A1_NO_TEAMS', 'no team was supplied for this slate; an empty '
            'slate from an upstream stage is not an allocation of zero.',
            cause=Cause.DEPENDENCY)
    if int(m) <= 0:
        return Outcome.fail('A1_NO_DRAWS',
                            f'm={m}; a partition needs at least one draw.')
    if params is None:
        got = resolve_params(season, week)
        if got.state is not State.PASS:
            return got
        params = got.value
    for k in ('league', 'resid', 'history'):
        if k not in params:
            return Outcome.fail(
                'A1_PARAMS_MALFORMED',
                f'the supplied parameters carry no {k!r}; a partial parameter '
                f'set is not a parameter set.', keys=sorted(params))

    missing = ([t for t in teams if t not in team_carries_draws],
               [t for t in teams if t not in scramble_draws])
    if any(missing):
        return Outcome.fail(
            'A1_INPUT_TEAM_MISSING',
            f'no team_carries draws for {missing[0]}; no scramble draws for '
            f'{missing[1]}. A missing level is not a level of zero.',
            missing_team_carries=missing[0], missing_scrambles=missing[1])

    if level_rounding not in (None, 'round_half_even'):
        return Outcome.fail(
            'A1_LEVEL_ROUNDING_UNDECLARED',
            f'level_rounding={level_rounding!r} is not one of '
            f'(None, "round_half_even").')

    counts, n_rounded, shape_bad = {}, 0, []
    for name, src in (('tc', team_carries_draws), ('scr', scramble_draws)):
        for t in teams:
            a = np.asarray(src[t], np.float64).reshape(-1)
            if a.size != m:
                shape_bad.append(f'{name}/{t}: {a.size} draws, expected {m}')
                continue
            r = np.rint(a)
            off = int((np.abs(a - r) > 1e-9).sum())
            if off and level_rounding is None:
                return Outcome.fail(
                    'A1_LEVEL_NOT_INTEGER',
                    f'{name} for {t} has {off} non-integer draw cell(s). A '
                    f'multinomial needs an integer budget, and turning a '
                    f'continuous level into a count is a D1 decision, not an '
                    f'allocation decision. Pass '
                    f'level_rounding="round_half_even" to declare it here, or '
                    f'integerise upstream where the level is owned.',
                    team=t, level=name, n_non_integer=off)
            n_rounded += off
            counts[(name, t)] = r.astype(np.int64)
    if shape_bad:
        return Outcome.fail(
            'A1_DRAW_COUNT_MISMATCH',
            f'{len(shape_bad)} input vector(s) are not {m} draws long: '
            f'{shape_bad[:4]}', problems=shape_bad[:20])

    # THE NAMED REFUSAL OWN-8 section 5 requires. No clipping, ever.
    over = {}
    for t in teams:
        n = int((counts[('scr', t)] > counts[('tc', t)]).sum())
        if n:
            over[t] = n
    if over:
        return Outcome.fail(
            'A1_SCRAMBLES_EXCEED_TEAM_CARRIES',
            f'{sum(over.values())} draw cell(s) across {len(over)} team(s) '
            f'have more scrambles than team carries, so the rush-play budget '
            f'is negative and there is nothing to partition. Refused by name '
            f'rather than clipped: clipping would silently move a carry '
            f'between two owners. {dict(sorted(over.items())[:6])}',
            teams=over, n_cells=int(sum(over.values())))

    sid = stream_component()
    if sid.state is not State.PASS:
        return sid
    gc = 0
    if game_id:
        g = SEEDS.game_component(game_id)
        if g.state is not State.PASS:
            return g
        gc = int(g.value)
    ordinal = int(season) * 100 + int(week)

    carries, budgets, qbo = {}, {}, {}
    ev = {'draws': 0, 'closure_violations': 0, 'negative_allocations': 0,
          'category_budget_overruns': 0, 'ledger_violations': 0,
          'carries_with_no_owner': 0, 'carries_with_two_owners': 0}
    floor_binds = degenerate = 0
    no_history = []
    for t in teams:
        tc, scr = counts[('tc', t)], counts[('scr', t)]
        budget = tc - scr
        tcomp = team_component(t)
        if tcomp.state is not State.PASS:
            return tcomp
        rng = np.random.default_rng(
            [int(seed), ordinal, gc, int(tcomp.value), int(sid.value)])
        alloc, fb, deg = _partition(params, t, budget, rng, m)
        floor_binds += fb
        degenerate += deg
        if t not in params['history']:
            no_history.append(t)
        cnt = verify_allocation(alloc, budget, tc, scr)
        for k in ev:
            ev[k] += int(cnt[k])
        for c in CATEGORIES:
            carries[(t, c)] = alloc[c]
        budgets[t] = budget
        qbo[t] = scr + alloc['designed_qb']

    hard = ('closure_violations', 'negative_allocations',
            'category_budget_overruns', 'ledger_violations',
            'carries_with_no_owner', 'carries_with_two_owners')
    broken = {k: ev[k] for k in hard if ev[k]}
    if broken:
        return Outcome.fail(
            'A1_HARD_REQUIREMENT_VIOLATED',
            f'{broken} across {ev["draws"]} draw cells. Reported, not '
            f'repaired: a violated partition is a defect in the allocator, '
            f'and rescaling it would hide the defect and move a carry.',
            **ev)

    value = {'carries': carries, 'rush_play_budget': budgets,
             'team_carries': {t: counts[('tc', t)] for t in teams},
             'scrambles': {t: counts[('scr', t)] for t in teams},
             'qb_rush_opportunity': qbo}
    return Outcome.ok(
        'A1_RUSH_ALLOCATION', value=value,
        detail=f'{len(teams)} team(s) x {m} draws partitioned into '
               f'{len(CATEGORIES)} categories; every carry has exactly one '
               f'owner in every draw',
        spec_version=SPEC_VERSION, season=int(season), week=int(week),
        n_teams=len(teams), n_draws=int(m), categories=list(CATEGORIES),
        every_carry_exactly_one_owner=True,
        share_floor_binds=int(floor_binds),
        degenerate_draws_named_and_given_to_fringe=int(degenerate),
        clipping_applied=0, survivor_renormalisation_applied=0,
        post_hoc_repairs=0, deleted_draws=0,
        scrambles_redrawn=0, scrambles_dropback_owned=True,
        kneel_is_an_explicit_category=True,
        kneel_in_qb_rush_opportunity=False,
        a2_latent_present=False,
        level_rounding=level_rounding, level_cells_rounded=int(n_rounded),
        teams_without_prior_history=no_history,
        seasons_used=params.get('seasons_used'),
        history_cut_ord=params.get('history_cut_ord'),
        game_stream_separated=bool(game_id),
        seed_contract=SEEDS.SEED_CONTRACT, uses_python_hash=False,
        predeclaration_sha256=pre.value, **ev)


# ----------------------------------------------------- dependence, per draw
def per_draw_dependence(X, y) -> Outcome:
    """corr(one draw per team-game, realised series), as a DISTRIBUTION.

    THE DEFECT THIS EXISTS TO PREVENT, and this project has found it six times.
    Correlating per-team-game predictive MEANS against a realised series is a
    different statistic and it is INFLATED: reality supplies one draw per
    team-game carrying its full idiosyncratic noise, and averaging m draws
    removes exactly that noise while leaving the budget-aligned component
    intact. OWN-10 measured the size of it -- a mean-based +0.5070 against a
    per-draw +0.3065 for a realised +0.3140 -- and the mean-based number was
    the headline of an accepted return before it was withdrawn.

    `X` is (n_team_games, m). `y` is (n_team_games,) realised.
    """
    X = np.asarray(X, np.float64)
    y = np.asarray(y, np.float64).reshape(-1)
    if X.ndim != 2 or X.shape[0] != y.size:
        return Outcome.fail(
            'A1_DEPENDENCE_SHAPE',
            f'X is {X.shape} and y is {y.shape}; X must be '
            f'(n_team_games, n_draws) with one row per realised observation.')
    if X.shape[1] < 2:
        return Outcome.fail(
            'A1_DEPENDENCE_NEEDS_DRAWS',
            f'{X.shape[1]} draw(s): a distribution over draws cannot be '
            f'formed from a point, and a point here is the mean-based defect '
            f'wearing another name.')
    if float(y.std()) == 0.0:
        return Outcome.not_applicable(
            'A1_DEPENDENCE_REALISED_CONSTANT',
            'the realised series is constant, so no dependence against it is '
            'defined. Reported as nothing-to-measure rather than as a zero.')
    v = []
    for j in range(X.shape[1]):
        col = X[:, j]
        if col.std() == 0:
            continue
        v.append(np.corrcoef(col, y)[0, 1])
    v = np.asarray([x for x in v if np.isfinite(x)], np.float64)
    if v.size == 0:
        return Outcome.not_applicable(
            'A1_DEPENDENCE_NO_VARYING_DRAW',
            'every draw column is constant, so no correlation is defined in '
            'any of them.')
    return Outcome.ok(
        'A1_PER_DRAW_DEPENDENCE',
        value={'per_draw_mean': float(v.mean()), 'per_draw_sd': float(v.std()),
               'p05': float(np.percentile(v, 5)),
               'p95': float(np.percentile(v, 95)),
               'n_draws_used': int(v.size)},
        detail='one draw per team-game, reported as a distribution over draws',
        statistic='per_draw', comparable_with_realised=True,
        mean_based=False,
        n_team_games=int(X.shape[0]), n_draws=int(X.shape[1]))


def mean_based_dependence(X, y) -> Outcome:
    """The inflated statistic, computed ONLY under a name that says so.

    It exists so the old number stays auditable and cannot be lifted as a
    measurement. It is never PASS.
    """
    X = np.asarray(X, np.float64)
    y = np.asarray(y, np.float64).reshape(-1)
    mu = X.mean(1)
    r = float(np.corrcoef(mu, y)[0, 1]) if mu.std() and y.std() else float('nan')
    return Outcome.fail(
        'A1_MEAN_BASED_DEPENDENCE_NOT_COMPARABLE',
        f'{r:.4f} is the correlation of per-team-game predictive MEANS '
        f'against a realised series. It has no realised counterpart, it is '
        f'inflated relative to the per-draw statistic, and it must not be '
        f'compared with an observed correlation. Use per_draw_dependence.',
        value_not_comparable=r, statistic='mean_based',
        comparable_with_realised=False)
