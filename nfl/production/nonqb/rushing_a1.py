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
    # THE COMMITTED CORPUS IS A DECLARED SOURCE, NOT A FALLBACK GUESS.
    #
    # The docstring above said play-by-play "is NOT committed to this
    # repository". That went stale: nfl/research/postgame carries
    # pbp_{season}.{sha16}.csv.gz for 2021-2026, each with a
    # .provenance.json sidecar naming the nflverse release URL, the retrieval
    # time and the sha256 of the bytes. Requiring an environment variable to
    # find files that are sitting in the tree made the QB layer BLOCK on
    # A1_PBP_SOURCE_NOT_LOCATED for 2026 week 2 -- a binding defect reported as
    # a missing input.
    #
    # THIS IS NOT A CHRONOLOGY HOLE. The frame is cut STRICTLY BEFORE
    # `season * 100 + week` by `_history_from_frame`, and the caller asserts
    # the cut held rather than trusting it. Handing it the whole corpus
    # therefore cannot leak DET-BUF's own play-by-play into DET-BUF's forecast:
    # ordinal 202602 is excluded by construction and the guard checks it.
    # Historical play-by-play through games already played is exactly what this
    # frame is for.
    committed = sorted(_glob.glob(str(
        _REPO / 'nfl' / 'research' / 'postgame' / 'pbp_*.csv.gz')))
    if committed:
        return Outcome.ok(
            'A1_PBP_SOURCES', value=committed,
            detail=f'{len(committed)} committed play-by-play file(s) from '
                   f'nfl/research/postgame',
            env=None, pattern='nfl/research/postgame/pbp_*.csv.gz',
            source='COMMITTED_CORPUS',
            sha256={os.path.basename(f): _sha_file(f)[:16]
                    for f in committed})
    return Outcome.blocked(
        'A1_PBP_SOURCE_NOT_LOCATED',
        f'no committed play-by-play under nfl/research/postgame, and none of '
        f'{PBP_GLOB_ENV} is set to the nflverse play-by-play files '
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
    # COMMITTED FALLBACK. `derived.cache_dir()` is gitignored and the six pbp
    # files a refit needs are not in this repository, so on a fresh checkout
    # both the parameters AND the means of rebuilding them were absent -- the
    # shape of the failure that left the sibling project's M0 baseline
    # permanently non-reproducible. The frozen file is committed gzipped
    # beside this module so a checkout can FORECAST and can verify what
    # produced the parameters. A refit still needs pbp and `pbp_sources()`
    # still BLOCKS by name without it: that debt is real and is reported, not
    # papered over by this fallback.
    cand.append(pathlib.Path(__file__).resolve().parent / 'frozen'
                / f'rushing_a1_params_{season}w{int(week):02d}.json.gz')
    for c in cand:
        if not c.exists():
            continue
        if c.suffix == '.gz':
            import gzip as _gz
            d = json.loads(_gz.decompress(c.read_bytes()).decode())
        else:
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


def _partition_given(par, team, budget, designed_qb, rng, m):
    """The SAME multinomial, CONDITIONED on the designed-QB count being known.

    WHY THIS EXISTS. `allocate` drew `designed_qb` itself, and the QB layer
    drew `rush_opp` itself, and nothing ever made the two agree. They are one
    football quantity -- how many of this team's carries its quarterbacks took
    -- with two owners, and the board published both: A1's answer sized the
    `rb` budget the named backs were dealt from, and the QB layer's answer is
    what `qb/rush_opp` seals. Measured on 2026_01_DEN_KC run d1e2727743c93990,
    Kansas City: A1 designed_qb mean 0.7090 against the QB layer's
    `rush_opp - scr` mean 0.6150, per draw differing by -11 to +10, which put
    the named owners above the team's own carry level in 149 of 1,000 draws by
    up to 9.6915 carries.

    THIS IS NOT A REPAIR OF A DRAWN RESULT. If
    (X_1..X_6) ~ Multinomial(B, p) then, conditional on the designed-QB
    component taking the value d, the remaining five are distributed exactly
    as Multinomial(B - d, p_{-dq} / (1 - p_dq)). That conditional law is drawn
    here directly. The division by (1 - p_dq) is the conditional probability
    vector of A1's own partition, not a renormalisation applied after the
    fact: no count is drawn and then moved, nothing is clipped, and no
    parameter is fitted. The share matrix `_shares` produces is untouched.

    A draw whose five remaining weights are all zero has no partition to make;
    it is NAMED, COUNTED and given to the fringe, which is the convention
    `_shares` already declares for a degenerate draw rather than a second one
    invented here.
    """
    p, floor_binds, degenerate = _shares(par, team, rng, m)
    j_fix = CATEGORIES.index('designed_qb')
    rest = [j for j in range(len(CATEGORIES)) if j != j_fix]
    b = np.asarray(budget, np.int64)
    d = np.asarray(designed_qb, np.int64)
    q = p[rest].copy()
    tot = q.sum(0)
    cond_degenerate = tot <= EPS
    q[:, cond_degenerate] = 0.0
    q[rest.index(CATEGORIES.index('fringe')), cond_degenerate] = 1.0
    q = q / np.where(cond_degenerate, 1.0, tot)
    out = np.empty((len(CATEGORIES), m), np.int64)
    out[j_fix] = d
    rest_ix = np.asarray(rest, np.int64)
    rest_b = b - d
    for j in range(m):
        out[rest_ix, j] = rng.multinomial(int(rest_b[j]), q[:, j])
    return ({c: out[j] for j, c in enumerate(CATEGORIES)},
            floor_binds, degenerate, int(cond_degenerate.sum()))


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
             params=None, game_id=None, level_rounding=None,
             qb_designed_rush=None) -> Outcome:
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
    qb_designed_rush    {team: (m,) integer array} -- the QB layer's OWN
                        designed-rush count, i.e. `rush_opp - scr` summed over
                        the team's quarterbacks. Supplying it makes the QB
                        layer the single owner of that quantity: `designed_qb`
                        is no longer drawn here, it IS this count, and the
                        remaining five categories are drawn from the exact
                        conditional multinomial on what is left of the budget.
                        Omitting it keeps A1 drawing its own designed_qb, in
                        which case the board carries TWO answers to one
                        question and the named owners can exceed the team's
                        carry level -- see `_partition_given`.

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

    # THE SECOND OWNER, REFUSED BY NAME RATHER THAN RECONCILED LATER.
    # `qb_designed_rush` is a COUNT the QB layer already drew. It is not
    # rounded here: rounding somebody else's count is how a quantity acquires
    # a third value.
    dq = {}
    if qb_designed_rush is not None:
        miss = [t for t in teams if t not in qb_designed_rush]
        if miss:
            return Outcome.fail(
                'A1_QB_DESIGNED_RUSH_TEAM_MISSING',
                f'no QB designed-rush count for {miss}. A missing count is '
                f'not a count of zero, and falling back to drawing it here '
                f'would reinstate the second owner for exactly those teams.',
                missing=miss)
        bad_shape, non_int, neg = [], {}, {}
        for t in teams:
            a = np.asarray(qb_designed_rush[t], np.float64).reshape(-1)
            if a.size != m:
                bad_shape.append(f'qb_designed_rush/{t}: {a.size} draws, '
                                 f'expected {m}')
                continue
            off = int((np.abs(a - np.rint(a)) > 1e-9).sum())
            if off:
                non_int[t] = off
            n = int((a < 0).sum())
            if n:
                neg[t] = n
            dq[t] = np.rint(a).astype(np.int64)
        if bad_shape:
            return Outcome.fail(
                'A1_QB_DESIGNED_RUSH_DRAW_MISMATCH',
                f'{len(bad_shape)} QB designed-rush vector(s) are not {m} '
                f'draws long: {bad_shape[:4]}. These layers share one draw '
                f'index, so a mismatch is refused rather than reshaped.',
                problems=bad_shape[:20])
        if non_int:
            return Outcome.fail(
                'A1_QB_DESIGNED_RUSH_NOT_INTEGER',
                f'{sum(non_int.values())} non-integer cell(s) across '
                f'{len(non_int)} team(s) in the QB designed-rush count. A '
                f'designed run is an event; a fractional one is not a small '
                f'one, and rounding another layer`s count here would give the '
                f'quantity a third value. {dict(sorted(non_int.items())[:6])}',
                teams=non_int)
        if neg:
            return Outcome.fail(
                'A1_QB_DESIGNED_RUSH_NEGATIVE',
                f'{sum(neg.values())} negative cell(s) across {len(neg)} '
                f'team(s). A negative count of designed runs is not a small '
                f'count. {dict(sorted(neg.items())[:6])}', teams=neg)
        short = {}
        for t in teams:
            n = int((dq[t] > counts[('tc', t)] - counts[('scr', t)]).sum())
            if n:
                short[t] = n
        if short:
            return Outcome.fail(
                'A1_QB_DESIGNED_RUSH_EXCEEDS_BUDGET',
                f'{sum(short.values())} draw cell(s) across {len(short)} '
                f'team(s) where the QB layer`s designed-rush count is larger '
                f'than the whole rush-play budget it has to fit inside, so '
                f'the five remaining categories would have a negative budget. '
                f'Refused by name rather than clipped: clipping would move a '
                f'carry between two owners silently. The coupling that '
                f'prevents this is upstream -- SC1 must couple the carry '
                f'level against `rush_opp`, not against `scr` alone, because '
                f'a designed quarterback run is a team carry exactly as a '
                f'scramble is. {dict(sorted(short.items())[:6])}',
                teams=short, n_cells=int(sum(short.values())))

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
    cond_degenerate = 0
    no_history = []
    for t in teams:
        tc, scr = counts[('tc', t)], counts[('scr', t)]
        budget = tc - scr
        tcomp = team_component(t)
        if tcomp.state is not State.PASS:
            return tcomp
        rng = np.random.default_rng(
            [int(seed), ordinal, gc, int(tcomp.value), int(sid.value)])
        if qb_designed_rush is None:
            alloc, fb, deg = _partition(params, t, budget, rng, m)
            cdeg = 0
        else:
            alloc, fb, deg, cdeg = _partition_given(
                params, t, budget, dq[t], rng, m)
        floor_binds += fb
        degenerate += deg
        cond_degenerate += cdeg
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
        conditional_degenerate_draws_named_and_given_to_fringe=int(
            cond_degenerate),
        designed_qb_owner=('the QB layer, supplied as qb_designed_rush'
                           if qb_designed_rush is not None
                           else 'A1 -- DRAWN HERE, so qb/rush_opp is a SECOND '
                                'answer to the same quantity and the named '
                                'rush owners are not bounded by the team '
                                'carry level'),
        qb_designed_rush_supplied=qb_designed_rush is not None,
        rush_opportunity_single_owner=qb_designed_rush is not None,
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


# ------------------------------------------- P3: the composition, in one place
def assert_named_owner_containment(teams, team_carries_published,
                                   named_back_carries, qb_rush_opportunity,
                                   tolerance=0.0) -> Outcome:
    """Named rush owners <= the PUBLISHED team carry level, DECOMPOSED.

    THE DEFECT THIS EXISTS TO CATCH, AND WHY ONE SUMMED CHECK MISSED IT.

    `quality_gates.gate_rush_accounting` compares one quantity -- RB carries
    plus QB scrambles plus QB designed runs -- against the team level. It is
    the correct quantity to gate on and the wrong one to repair from: it sums
    two layers and names neither. Decomposed against the sealed arrays of
    board 96954efc523bd7d3 (2026_01_DEN_KC, V1_CANDIDATE_R9, 1,000 draws):

        RB carries only      DEN 2 draws positive, max +0.2619
                             KC  2 draws positive, max +0.0854
        RB + QB rush opp     DEN 206 positive, max +6.1219
                             KC  237 positive, max +9.6915

    The multinomial deal is sound. The impossibility enters with the
    quarterback. So this returns BOTH series, always, and the refusal carries
    both -- a reader of a fired verdict must be able to see which half moved.

    THE LEVEL IS THE PUBLISHED ONE, ON PURPOSE. A containment check against a
    denominator the run did not seal cannot be attributed between a carry with
    two owners and a level that was never used, which is exactly why
    `draw_coherence.team_qb_rush_opportunity_within_team_carries` is a
    diagnostic rather than a gate. Pass the vector the board carries.

    It REPAIRS NOTHING. It counts and it names. `tolerance` defaults to ZERO
    because the composition this fence guards makes the bound exact; the
    product gate's half-carry tolerance exists to separate rounding from a real
    over-deal on boards whose level and owners are on different draw indices,
    and importing that slack here would hide the thing this asserts.
    """
    if not teams:
        return Outcome.blocked(
            'A1_CONTAINMENT_NO_TEAMS',
            'no team was supplied, so there is nothing to contain. An empty '
            'check is not a passing check.', cause=Cause.DEPENDENCY)
    ev, bad = {}, []
    for t in teams:
        for name, src in (('team_carries_published', team_carries_published),
                          ('named_back_carries', named_back_carries),
                          ('qb_rush_opportunity', qb_rush_opportunity)):
            if t not in src:
                return Outcome.fail(
                    'A1_CONTAINMENT_INPUT_MISSING',
                    f'no {name} for {t}. A missing vector is not a vector of '
                    f'zero, and treating it as one would report containment '
                    f'for a quantity nobody measured.', team=t, input=name)
        lvl = np.asarray(team_carries_published[t], np.float64).reshape(-1)
        rb = np.asarray(named_back_carries[t], np.float64)
        rb = rb.sum(0) if rb.ndim == 2 else rb.reshape(-1)
        q = np.asarray(qb_rush_opportunity[t], np.float64).reshape(-1)
        if not (lvl.size == rb.size == q.size):
            return Outcome.fail(
                'A1_CONTAINMENT_DRAW_MISMATCH',
                f'{t}: level {lvl.size}, backs {rb.size}, QB rush {q.size}. '
                f'These share one draw index; a mismatch is refused rather '
                f'than broadcast.', team=t)
        rb_only, both = rb - lvl, rb + q - lvl
        rec = {
            'n_draws': int(lvl.size),
            'rb_only_draws_over': int((rb_only > tolerance).sum()),
            'rb_only_max_excess': float(rb_only.max()),
            'qb_only_draws_over': int((q - lvl > tolerance).sum()),
            'qb_only_max_excess': float((q - lvl).max()),
            'rb_plus_qb_draws_over': int((both > tolerance).sum()),
            'rb_plus_qb_max_excess': float(both.max()),
            'level_is_integer': bool(
                not (np.abs(lvl - np.rint(lvl)) > 1e-9).any())}
        ev[t] = rec
        if rec['rb_plus_qb_draws_over']:
            bad.append(t)
    flat = {'rb_only_draws_over': sum(v['rb_only_draws_over']
                                      for v in ev.values()),
            'qb_only_draws_over': sum(v['qb_only_draws_over']
                                      for v in ev.values()),
            'rb_plus_qb_draws_over': sum(v['rb_plus_qb_draws_over']
                                         for v in ev.values()),
            'rb_only_max_excess': max(v['rb_only_max_excess']
                                      for v in ev.values()),
            'rb_plus_qb_max_excess': max(v['rb_plus_qb_max_excess']
                                         for v in ev.values()),
            'per_team': ev, 'tolerance': float(tolerance),
            'decomposed': True}
    if bad:
        return Outcome.fail(
            'A1_NAMED_OWNERS_EXCEED_TEAM_CARRIES',
            f'{bad}: the named rush owners are dealt more carries than the '
            f'published team level in at least one draw. Decomposed, the '
            f'running-back deal is over by at most '
            f'{flat["rb_only_max_excess"]:+.4f} and the running backs plus '
            f'the quarterbacks by {flat["rb_plus_qb_max_excess"]:+.4f}, so '
            f'the difference between those two numbers is where the repair '
            f'belongs. Reported, never clipped.', **flat)
    return Outcome.ok(
        'A1_NAMED_OWNERS_WITHIN_TEAM_CARRIES', value=ev,
        detail=f'{len(teams)} team(s): named backs plus quarterback rush '
               f'opportunity fit inside the published carry level in every '
               f'draw, decomposed into both halves',
        **flat)


def compose_rush_ownership(season: int, week: int, teams, *,
                           team_carry_level, qb_scrambles,
                           qb_rush_opportunity, m: int,
                           seed: int = 20260908, params=None, game_id=None,
                           level_rounding='round_half_even') -> Outcome:
    """THE WHOLE RUSH COMPOSITION, in one named function with one owner.

    WHAT WAS WRONG. Three steps used to live at the `run_forecast` call site
    and each was individually defensible:

      1. SC1 coupled the carry level against the SCRAMBLES. A designed
         quarterback run is a team carry exactly as a scramble is, so the
         bound was too weak and `rush_opp > team_carries` stayed reachable --
         1 of 1,000 Kansas City draws on sealed board 96954efc523bd7d3.
      2. `allocate` was called WITHOUT `qb_designed_rush`, so A1 drew its own
         `designed_qb` while the QB layer drew `rush_opp`. One football
         quantity, two owners, two values: DEN 2.2960 against 1.6270, KC
         0.7090 against 0.6150, disagreeing in 814 and 528 of 1,000 cells and
         differing per draw by -10 to +15 carries.
      3. The run sealed D1's RAW continuous level while the engine partitioned
         the SC1-coupled, integerised one, so the board published a
         denominator the game never used and a breach could not be attributed
         between a doubled carry and a wrong vector.

    Together those put the named rush owners above the team's own carry level
    in 149 of 1,000 DEN draws and 148 of 1,000 KC draws, by up to 6.12 and
    9.69 carries -- the product gate's `RUSH_ACCOUNTING_FAILURE`.

    WHAT THIS DOES. The same three steps, composed in the order that makes the
    constraint an identity rather than a hope:

        coupled   = SC1.couple(qb_rush_opportunity, team_carry_level)
        published = rint(coupled)                      # A1's own rounding
        designed  = qb_rush_opportunity - qb_scrambles
        alloc     = allocate(..., qb_designed_rush=designed)

    and then, because `qb_rush_opportunity` is integral and SC1 only permutes,

        rb_category + qb_rush_opportunity
            = (published - scr - designed - kneel - wr - te - fringe)
              + (scr + designed)
            = published - (kneel + wr + te + fringe)
            <= published

    in EVERY draw, for EVERY input this function accepts. Nothing is clipped,
    nothing is truncated, no drawn result is renormalised and no draw is
    deleted: SC1 chooses which draw index receives which carry value and the
    multiset of carry values is unchanged element for element, and A1 draws
    the five remaining categories from the EXACT conditional multinomial given
    the designed-QB count rather than adjusting a partition after the fact.

    WHAT IT REFUSES, BY NAME. A non-integral or negative quarterback rush
    count; a rush opportunity smaller than the scrambles inside it; a draw
    whose carry level cannot be permuted to clear the rush opportunity
    (SC1's own `SC1_NO_DONOR_DRAW`); and any allocation whose containment
    verification does not close. Each is a refusal, and a refusal is not a
    repair.

    Returns an Outcome whose value is

        {'allocation':             allocate(...).value,
         'team_carries_published': {team: (m,) int64},   # SEAL THIS ONE
         'qb_rush_opportunity':    {team: (m,) int64},   # passed through
         'qb_designed_rush':       {team: (m,) int64},
         'sc1':                    {team: SC1 evidence}}
    """
    from nfl.production.nonqb import scramble_coherence as SC1
    if not teams:
        return Outcome.blocked(
            'A1_COMPOSE_NO_TEAMS',
            'no team was supplied for this slate; an empty slate from an '
            'upstream stage is not a composition of zero.',
            cause=Cause.DEPENDENCY)
    if int(m) <= 0:
        return Outcome.fail('A1_COMPOSE_NO_DRAWS',
                            f'm={m}; a composition needs at least one draw.')
    miss = {name: [t for t in teams if t not in src]
            for name, src in (('team_carry_level', team_carry_level),
                              ('qb_scrambles', qb_scrambles),
                              ('qb_rush_opportunity', qb_rush_opportunity))}
    if any(miss.values()):
        return Outcome.fail(
            'A1_COMPOSE_INPUT_TEAM_MISSING',
            f'missing per-team vectors: '
            f'{ {k: v for k, v in miss.items() if v} }. A missing level or a '
            f'missing quarterback rush count is not a level of zero, and '
            f'falling back would reinstate the second owner for exactly those '
            f'teams.', missing=miss)

    # THE QUARTERBACK'S COUNTS ARE NOT ROUNDED HERE. Rounding another layer's
    # count is how a quantity acquires a third value; a fractional rush
    # attempt is not a small one.
    bad_shape, non_int, neg, inverted = [], {}, {}, {}
    ro, scr = {}, {}
    for t in teams:
        a = np.asarray(qb_rush_opportunity[t], np.float64).reshape(-1)
        s = np.asarray(qb_scrambles[t], np.float64).reshape(-1)
        lv = np.asarray(team_carry_level[t], np.float64).reshape(-1)
        for nm, v in (('qb_rush_opportunity', a), ('qb_scrambles', s),
                      ('team_carry_level', lv)):
            if v.size != m:
                bad_shape.append(f'{nm}/{t}: {v.size} draws, expected {m}')
        if a.size != m or s.size != m:
            continue
        off = int((np.abs(a - np.rint(a)) > 1e-9).sum()
                  + (np.abs(s - np.rint(s)) > 1e-9).sum())
        if off:
            non_int[t] = off
        n = int((a < 0).sum() + (s < 0).sum())
        if n:
            neg[t] = n
        inv = int((a < s - 1e-9).sum())
        if inv:
            inverted[t] = inv
        ro[t], scr[t] = a, s
    if bad_shape:
        return Outcome.fail(
            'A1_COMPOSE_DRAW_MISMATCH',
            f'{len(bad_shape)} input vector(s) are not {m} draws long: '
            f'{bad_shape[:4]}. These layers share one draw index, so a '
            f'mismatch is refused rather than reshaped.',
            problems=bad_shape[:20])
    if non_int:
        return Outcome.fail(
            'A1_COMPOSE_QB_RUSH_NOT_INTEGER',
            f'{sum(non_int.values())} non-integer quarterback rush cell(s) '
            f'across {len(non_int)} team(s). A rush attempt is an event; a '
            f'fractional one is not a small one, and rounding another layer`s '
            f'count here would give the quantity a third value. '
            f'{dict(sorted(non_int.items())[:6])}', teams=non_int)
    if neg:
        return Outcome.fail(
            'A1_COMPOSE_QB_RUSH_NEGATIVE',
            f'{sum(neg.values())} negative quarterback rush cell(s) across '
            f'{len(neg)} team(s). A negative count of rushes is not a small '
            f'count. {dict(sorted(neg.items())[:6])}', teams=neg)
    if inverted:
        return Outcome.fail(
            'A1_COMPOSE_SCRAMBLES_EXCEED_RUSH_OPPORTUNITY',
            f'{sum(inverted.values())} cell(s) across {len(inverted)} team(s) '
            f'carry more scrambles than rush opportunity, so the implied '
            f'designed-run count is negative. The QB layer owns both and the '
            f'identity `rush_opp = scrambles + designed` is its own; it is '
            f'refused here rather than absorbed. '
            f'{dict(sorted(inverted.items())[:6])}', teams=inverted)

    # STEP 1. SC1, BOUNDED BY THE WHOLE RUSH OPPORTUNITY RATHER THAN BY THE
    # SCRAMBLES. `couple` is generic in its first argument -- it is a per-draw
    # lower bound on carries -- so raising the bound needs no change inside
    # SC1 and no clipping anywhere: it reorders which draw receives which
    # carry value and the marginal is a multiset invariant it checks itself.
    coupled, sc1_ev, swaps = {}, {}, 0
    for t in teams:
        o = SC1.couple(ro[t], np.asarray(team_carry_level[t],
                                         np.float64).reshape(-1))
        if o.state is not State.PASS:
            return Outcome.fail(
                'A1_COMPOSE_SC1_REFUSED',
                f'{t}: {o.code}: {o.detail[:200]} -- the carry level cannot '
                f'be permuted to hold this team`s quarterback rush '
                f'opportunity. Refused rather than clipped: clipping the '
                f'level would silently move a carry between two owners.',
                team=t, sc1_code=o.code)
        coupled[t] = np.asarray(o.value, np.float64)
        sc1_ev[t] = {k: v for k, v in o.evidence.items() if k != 'value'}
        swaps += int(o.evidence.get('n_swaps', 0) or 0)

    # STEP 2. ONE OWNER FOR THE DESIGNED RUNS: the QB layer's, handed to A1.
    designed = {t: np.rint(ro[t] - scr[t]).astype(np.int64) for t in teams}

    alloc = allocate(season, week, teams, coupled, scr, m=m, seed=seed,
                     params=params, game_id=game_id,
                     level_rounding=level_rounding,
                     qb_designed_rush=designed)
    if alloc.state is not State.PASS:
        return alloc

    # STEP 3. THE LEVEL THE BOARD PUBLISHES IS THE LEVEL THAT WAS PARTITIONED.
    published = {t: np.asarray(alloc.value['team_carries'][t], np.int64)
                 for t in teams}
    qbo = {t: np.rint(ro[t]).astype(np.int64) for t in teams}

    # VERIFIED, NOT ASSERTED. The bound is an identity above; this is the
    # executable statement of it, decomposed, and a failure here is a defect
    # in this composition rather than a residual to report.
    cont = assert_named_owner_containment(
        list(teams), published,
        {t: np.asarray(alloc.value['carries'][(t, 'rb')], np.float64)
         for t in teams}, qbo)
    if cont.state is not State.PASS:
        return cont
    for t in teams:
        tot = sum(np.asarray(alloc.value['carries'][(t, c)], np.int64)
                  for c in CATEGORIES)
        openc = int((tot + np.rint(scr[t]).astype(np.int64)
                     != published[t]).sum())
        if openc:
            return Outcome.fail(
                'A1_COMPOSE_PARTITION_DOES_NOT_CLOSE',
                f'{t}: the six categories plus the scrambles do not equal the '
                f'published level in {openc} draw(s). A1 closes by '
                f'construction, so a gap here means this composition handed '
                f'it a level or a draw index it did not partition.',
                team=t, cells=openc)

    return Outcome.ok(
        'A1_RUSH_OWNERSHIP_COMPOSED',
        value={'allocation': alloc.value,
               'team_carries_published': published,
               'qb_rush_opportunity': qbo,
               'qb_designed_rush': designed,
               'sc1': sc1_ev},
        detail=f'{len(teams)} team(s) x {m} draws: the carry level is '
               f'permuted to hold the quarterbacks` whole rush opportunity, '
               f'the QB layer is the single owner of the designed runs, and '
               f'the level the board publishes is the level A1 partitioned',
        spec_version=SPEC_VERSION, season=int(season), week=int(week),
        n_teams=len(teams), n_draws=int(m),
        sc1_bound='qb_rush_opportunity',
        sc1_bound_was='qb_scrambles',
        sc1_total_swaps=int(swaps),
        sc1_marginal_preserved=True,
        rush_opportunity_single_owner=True,
        designed_qb_owner='the QB layer, via qb_rush_opportunity - scrambles',
        published_level_is_the_partitioned_level=True,
        named_owner_containment=cont.code,
        named_owner_containment_evidence={
            k: v for k, v in cont.evidence.items() if k != 'per_team'},
        clipping_applied=0, survivor_renormalisation_applied=0,
        post_hoc_repairs=0, deleted_draws=0,
        allocation_evidence={k: alloc.evidence.get(k) for k in (
            'share_floor_binds', 'degenerate_draws_named_and_given_to_fringe',
            'conditional_degenerate_draws_named_and_given_to_fringe',
            'level_cells_rounded', 'closure_violations',
            'ledger_violations', 'carries_with_two_owners')})



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


# ------------------------------------------------------ R4: the sealed ledger
def _dist(x) -> dict:
    """A residual reported as a DISTRIBUTION, because a mean hides a sign change.

    D6's finding in one function: Kansas City's rush residual has a mean of
    +0.1555 -- 0.6% of the level, the most closed allocation of the fifteen
    games -- and is NEGATIVE in 464 of 1,000 draws with an sd of 3.99 and a
    range of [-9.96, +28.08]. The mean is what is left after the two halves
    cancel. Any summary that prints the mean alone ranks boards close to
    backwards, so no residual leaves this module as a scalar.
    """
    a = np.asarray(x, np.float64).reshape(-1)
    return {'mean': float(a.mean()), 'sd': float(a.std(ddof=0)),
            'min': float(a.min()), 'max': float(a.max()),
            'p05': float(np.percentile(a, 5)),
            'p50': float(np.percentile(a, 50)),
            'p95': float(np.percentile(a, 95)),
            'draws': int(a.size),
            'draws_negative': int((a < -1e-9).sum()),
            'draws_positive': int((a > 1e-9).sum()),
            'draws_zero': int((np.abs(a) <= 1e-9).sum()),
            'sign_changes': bool((a < -1e-9).any() and (a > 1e-9).any())}


def ownership_ledger(teams, team_carries, scrambles, categories,
                     player_carries=None, player_other=None,
                     qb_rush_opportunity=None) -> Outcome:
    """Team rush opportunity -> category -> player -> unowned, per draw.

    WHAT THIS EXISTS FOR. `allocate` already gives every carry exactly one
    owner in every draw -- six categories, one multinomial, closure verified
    by `verify_allocation`. Only `rb` ever reached a sealed artifact, so a
    reader of the artifact could measure that a quarter of the team's carries
    had no modelled owner and could not say whose they were. D6 measured it
    across 102 sealed runs: frame mean 24.1% unowned, range 0.6%-45.3%, all 67
    team-runs with a rushing layer changing sign, 6,650 of 95,000 draws
    dealing MORE carries than the team's level.

    This function composes the ledger that makes the same quantity
    ATTRIBUTED. It computes two residuals and reports both:

      `unowned_before`  team_carries - (named RBs + QB scrambles + QB designed)
                        -- the D6 quantity, i.e. what a reader of the previous
                        artifact could see. It is NOT a defect: its owners are
                        kneel, wr, te, fringe and the unmodelled-back pool,
                        which are real football.

      `unowned_after`   team_carries - (every category + every named back +
                        the named other pool). Zero in every draw, by
                        construction, and a non-zero value is a FAILURE of
                        this composition rather than a residual to report.

    It changes nothing. No draw is written, no category is rescaled, and the
    quarterback containment breach is SURFACED with its counts rather than
    repaired -- `qb_rush_opportunity_within_team_carries` breaches on 60 of
    204 sealed team-runs and 371 of 232,000 cells, and the J-13 stored-vector
    defect blocks attributing the negative tail. That is an open item with an
    owner, not a number to adjust.
    """
    if not teams:
        return Outcome.blocked(
            'A1_LEDGER_NO_TEAMS',
            'no team was supplied, so there is no ownership graph to compose. '
            'An empty ledger is not a ledger of zero.', cause=Cause.DEPENDENCY)
    out, bad = {}, []
    for t in teams:
        miss = [c for c in CATEGORIES if (t, c) not in categories]
        if miss:
            return Outcome.fail(
                'A1_LEDGER_CATEGORY_MISSING',
                f'{t} carries no {miss} category. The whole partition is the '
                f'point of this ledger; composing it from a subset would '
                f'reproduce the defect it exists to close.',
                team=t, missing=miss)
        tc = np.asarray(team_carries[t], np.float64).reshape(-1)
        scr = np.asarray(scrambles[t], np.float64).reshape(-1)
        cat = {c: np.asarray(categories[(t, c)], np.float64).reshape(-1)
               for c in CATEGORIES}
        m = tc.size
        if scr.size != m or any(v.size != m for v in cat.values()):
            return Outcome.fail(
                'A1_LEDGER_DRAW_MISMATCH',
                f'{t}: the level, the scrambles and the categories are not on '
                f'one draw index.', team=t)
        named = (np.asarray(player_carries[t], np.float64).sum(0)
                 if player_carries is not None and t in player_carries
                 else np.zeros(m))
        n_backs = (int(np.asarray(player_carries[t]).shape[0])
                   if player_carries is not None and t in player_carries
                   else 0)
        oth = (np.asarray(player_other[t], np.float64).reshape(-1)
               if player_other is not None and t in player_other
               else np.zeros(m))
        # The `rb` CATEGORY is what the named backs and the unmodelled-back
        # pool partition. TWO CLOSURES, AND THEY ARE DIFFERENT QUESTIONS.
        #
        #   the A1 closure       team_carries == scrambles + the six
        #                        categories. Exact in every draw by
        #                        construction, for EVERY team, whether or not
        #                        any player layer ran for it.
        #   the player closure   the `rb` category == named backs + the
        #                        unmodelled-back pool. Only askable of a team
        #                        whose appearance layer ran. A team deferred
        #                        under APPEARANCE_TEAM_DEFERRED has a fully
        #                        attributed CATEGORY ledger and no player
        #                        split, and collapsing those two into one
        #                        residual would report a deferral as a
        #                        conservation defect.
        has_players = (player_carries is not None and t in player_carries)
        rb_resid = cat['rb'] - (named + oth)
        rec = {
            'team': t, 'n_draws': m, 'n_named_backs': n_backs,
            'team_carries_mean': float(tc.mean()),
            'scrambles_mean': float(scr.mean()),
            'rush_play_budget_mean': float((tc - scr).mean()),
            'categories': {c: {'mean': float(v.mean()),
                               'share_of_team_carries': float(
                                   v.mean() / max(tc.mean(), 1e-9))}
                           for c, v in cat.items()},
            'rb_category_split': {
                'state': 'ALLOCATED' if has_players else 'NOT_ALLOCATED',
                'why_not_allocated': (None if has_players else
                                      'no player layer ran for this team, so '
                                      'the rb category is attributed at '
                                      'category level and has no player '
                                      'split. This is not unowned mass.'),
                'named_backs_mean': float(named.mean()),
                'unmodelled_back_pool_mean': float(oth.mean()),
                'residual': _dist(rb_resid) if has_players else None},
            'unowned_before': _dist(
                tc - (named + scr + cat['designed_qb'])),
            'unowned_after': _dist(
                tc - (scr + sum(cat[c] for c in CATEGORIES))),
        }
        rec['unowned_before']['share_of_team_carries'] = float(
            rec['unowned_before']['mean'] / max(tc.mean(), 1e-9))
        rec['unowned_after']['share_of_team_carries'] = float(
            rec['unowned_after']['mean'] / max(tc.mean(), 1e-9))
        if qb_rush_opportunity is not None and t in qb_rush_opportunity:
            q = np.asarray(qb_rush_opportunity[t], np.float64).reshape(-1)
            head = tc - q
            # ONE QUANTITY, AND THE LEDGER SAYS WHETHER IT HAS ONE OWNER.
            #
            # A1's own answer to "how many carries did this team's
            # quarterbacks take" is `scrambles + designed_qb`, and it is the
            # answer the `rb` budget was carved out of. `qb_rush_opportunity`
            # is the QB layer's answer. When `allocate` is given
            # `qb_designed_rush` the two are one array by construction and
            # `cells_disagreeing` is 0. When it is not, they are independent
            # draws, and the difference is the exact amount by which the
            # NAMED rush owners can exceed the team's carry level -- less
            # whatever slack kneel / wr / te / fringe and the
            # unmodelled-back pool happen to hold in that draw.
            #
            # Measured, 2026_01_DEN_KC run d1e2727743c93990, Kansas City:
            # 149 of 1,000 draws over-allocated by up to 9.6915 carries.
            a1q = scr + cat['designed_qb']
            excess = q - a1q
            slack = (cat['kneel'] + cat['wr'] + cat['te'] + cat['fringe']
                     + oth)
            rec['qb_rush_opportunity_single_owner'] = {
                'a1_answer_mean': float(a1q.mean()),
                'qb_layer_answer_mean': float(q.mean()),
                'cells_disagreeing': int((np.abs(excess) > 1e-9).sum()),
                'qb_layer_excess': _dist(excess),
                'state': ('ONE_OWNER' if not (np.abs(excess) > 1e-9).any()
                          else 'TWO_OWNERS'),
                'implied_named_owner_over_allocation': _dist(excess - slack),
                'implied_draws_over_allocated': int(
                    ((excess - slack) > 0.5).sum()),
                'owner': ('the QB layer -- A1 was given qb_designed_rush and '
                          'drew the other five categories from the exact '
                          'conditional multinomial'
                          if not (np.abs(excess) > 1e-9).any() else
                          'NOBODY -- A1 drew designed_qb and the QB layer '
                          'drew rush_opp, so the board carries two answers '
                          'to one quantity. Pass qb_designed_rush to '
                          'allocate() to make the QB layer the single '
                          'owner.')}
            rec['qb_rush_opportunity_within_team_carries'] = {
                'qb_rush_opportunity_mean': float(q.mean()),
                'headroom': _dist(head),
                'breaching_cells': int((head < -1e-9).sum()),
                'state': 'BREACHED' if (head < -1e-9).any() else 'HELD',
                'surfaced_not_repaired': (
                    'DIAGNOSTIC in draw_coherence pending the J-13 stored-'
                    'vector defect: the SC1-coupled carry vector the engine '
                    'partitioned is not the vector run_forecast seals, so a '
                    'breach cannot today be split between a carry dealt twice '
                    'and a denominator that was never used. Reported with its '
                    'counts; nothing here adjusts it.')}
        if (rec['unowned_after']['draws_negative']
                or rec['unowned_after']['draws_positive']):
            bad.append(t)
        if has_players and (rb_resid_bad := int((np.abs(rb_resid)
                                                 > 1e-9).sum())):
            return Outcome.fail(
                'A1_LEDGER_RB_SPLIT_DOES_NOT_CLOSE',
                f'{t}: the named backs plus the unmodelled-back pool do not '
                f'sum to the `rb` category in {rb_resid_bad} draw(s). The '
                f'player deal partitions that category by construction, so a '
                f'gap means the player layer ran on a different budget from '
                f'the one A1 dealt -- a wrong vector or a wrong draw index, '
                f'not unowned mass.', team=t, cells=rb_resid_bad)
        out[t] = rec
    if bad:
        return Outcome.fail(
            'A1_LEDGER_DOES_NOT_CLOSE',
            f'{bad}: the full ownership graph leaves a non-zero residual. '
            f'`allocate` gives every carry exactly one owner by construction, '
            f'so a residual here is a defect in this composition -- a wrong '
            f'level, a wrong draw index, or a category read from a different '
            f'run -- and is refused rather than reported as unowned mass.',
            teams=bad, ledger=out)
    return Outcome.ok(
        'A1_OWNERSHIP_LEDGER', value=out,
        detail=f'{len(teams)} team(s): team carries -> six A1 categories -> '
               f'named backs and the unmodelled-back pool, with every carry '
               f'attributed in every draw',
        spec_version=SPEC_VERSION, categories=list(CATEGORIES),
        unowned_after_is_zero_by_construction=True,
        unowned_before_owners=('kneel', 'wr', 'te', 'fringe',
                               'unmodelled_back_pool'),
        teams=list(teams))
