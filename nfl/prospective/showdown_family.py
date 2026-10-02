"""The Showdown model family's OWN prospective identity and admissibility lane. Owner ruling 2.

proj_v1 + nfl.sim.game (joint simulator) is a different model family from the frozen Q9 target
allocator. Q9's `candidate_freeze_identity` control recognises Q9's module hashes and nothing else,
so a Showdown seal could never be admissible however complete it became. The ruling: do not reuse
Q9's identity; give Showdown its own lane. This module is that lane, built on the SAME machinery --
sealed_index discovery, the DrawSet draw artifact, the postgame grader, and reuse's disposition loop
-- with a family-specific control set. Nothing here is a second ledger.

WHAT A SHOWDOWN SEAL ASSERTS (the owner's required fields, each read from an input, never typed in):
  model_family            the family identifier
  code_identity           sha16 of the source of every module on the execution path
  projection_sha256       the projection artifact's bytes
  draw_artifact           the layered DrawSet's content digest and file hashes
  game_id / kickoff_utc   slate identity
  written_at              the seal clock, with its basis stated (live clock, or a git commit time
                          when sealed retrospectively -- and then prospective_evidence is False)
  data_cutoff             information_set.observed_before: the newest consumed capture
  availability_vintage    the official-inactive list's hash and the state build clock
  roster_vintage          every roster capture the identity resolver globs, with hashes
  depth_vintage           USAGE_DERIVED: this family ranks depth from panel usage, not from a
                          depth-chart capture, so the vintage IS the play-by-play blob
  prospective_evidence    explicit; True only when sealed before kickoff by a live clock

TIME BASIS: every source capture's retrieved_at <= written_at < kickoff_utc, through
timebasis.assert_prospective_order, the same check Q9 uses.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import inspect
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.prospective.q9shadow import timebasis as TB  # noqa: E402

SPEC_VERSION = 'showdown-family-1'
MODEL_FAMILY = 'SHOWDOWN_PROJ_V1_JOINT_SIM'
NAMESPACE = 'showdown_live'
ROOT = _REPO / 'nfl' / 'research' / 'showdown_live'

ADMISSIBLE, LEGACY_UNVERIFIED, REFUSED = 'ADMISSIBLE', 'LEGACY_UNVERIFIED', 'REFUSED'

#: Every module on the Showdown execution path. Adding one strengthens the identity.
EXECUTION_PATH = (
    'nfl.tools.proj_v1', 'nfl.sim.game', 'nfl.tools.showdown_draws',
    'nfl.tools.showdown_slate_state', 'nfl.tools.showdown_to_portfolio',
    'nfl.tools.football_sanity', 'nfl.tools.kicker_model', 'nfl.tools.player_prior',
    'nfl.tools.role_state_history',
)

MANDATORY_CONTROLS = (
    'model_family_declared', 'code_identity_matches_current', 'projection_hash_matches_disk',
    'draw_artifact_hash_matches_disk', 'slate_identity', 'time_basis', 'data_cutoff_declared',
    'availability_vintage_declared', 'roster_depth_vintage_declared',
    'prospective_evidence_eligibility',
)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _file_sha(p) -> str:
    return _sha(pathlib.Path(p).read_bytes())


def code_identity() -> dict:
    import importlib
    out = {}
    for name in EXECUTION_PATH:
        mod = importlib.import_module(name)
        out[name] = _sha(inspect.getsource(mod).encode())[:16]
    return out


def identity_sha256(ident: dict) -> str:
    return _sha(json.dumps(ident, sort_keys=True).encode())


def _mtime_utc(p) -> str:
    return dt.datetime.fromtimestamp(pathlib.Path(p).stat().st_mtime,
                                     dt.timezone.utc).isoformat()


def roster_vintage() -> list:
    from nfl.tools import player_prior as PP
    files = sorted(glob.glob(str(_REPO / PP.ROSTERS)))
    return [{'path': str(pathlib.Path(f).relative_to(_REPO)), 'sha256': _file_sha(f),
             'retrieved_at': _mtime_utc(f), 'retrieved_at_basis': 'FILE_MTIME'} for f in files]


def panel_cutoff(season=2026) -> dict:
    from nfl.tools import player_prior as PP
    d = json.loads(pathlib.Path(PP.PANEL).read_text())
    pv = (d.get('provenance') or {}).get(str(season)) or {}
    blob = pv.get('blob')
    return {'season': season, 'blob': blob, 'sha16': pv.get('sha256'),
            'week_span': pv.get('week_span'),
            'retrieved_at': _mtime_utc(_REPO / blob) if blob else None,
            'retrieved_at_basis': 'FILE_MTIME'}


def seal(game_id: str, *, proj_path, draws_path, state_path, export_path, inactives_path,
         kickoff_utc: str, written_at: str, written_at_basis: str, prospective_evidence: bool,
         model_configuration: str, reason: str = '', out_root=None, stat_draws=None,
         stat_fields=None) -> Outcome:
    """Write one Showdown seal: forecast_artifact.json + the layered draw artifact."""
    from nfl.production import draws_artifact as DA
    import numpy as np
    proj_path, draws_path, state_path = map(pathlib.Path, (proj_path, draws_path, state_path))
    export_path, inactives_path = pathlib.Path(export_path), pathlib.Path(inactives_path)
    for p in (proj_path, draws_path, state_path, export_path, inactives_path):
        if not p.exists():
            return Outcome.blocked('SHOWDOWN_SEAL_INPUT_ABSENT', f'{p} not found', cause=Cause.DATA)
    proj = json.loads(proj_path.read_text())
    draws = json.loads(draws_path.read_text())
    state = json.loads(state_path.read_text())
    ident = code_identity()
    cutoff = panel_cutoff(int(game_id.split('_')[0]))
    rosters = roster_vintage()
    inact_sha = _file_sha(inactives_path)
    export_sha = _file_sha(export_path)

    # gsis map for the draw rows (DSTs have none and live on a team axis)
    players = state.get('players') or {}
    by_key = {}
    for v in players.values():
        by_key[f"{v['name']}|{v['team']}"] = v
    gsis_rows, gsis_teams, dk_mat, kick_rows, kick_mat, dst_rows, dst_mat = [], {}, [], [], [], [], []
    for key, vec in sorted(draws['draws'].items()):
        v = by_key.get(key)
        if v is None:
            continue
        if v.get('position') == 'DST':
            dst_rows.append(v['team']); dst_mat.append(vec); continue
        g = v.get('gsis_id')
        if not g:
            continue
        if v.get('position') == 'K':
            kick_rows.append(g); kick_mat.append(vec); gsis_teams[g] = v['team']; continue
        gsis_rows.append(g); gsis_teams[g] = v['team']; dk_mat.append(vec)
    n_draws = int(draws['n_sims'])
    ds = DA.DrawSet(run_id=f'{game_id}:{model_configuration}', game_id=game_id,
                    seed=draws.get('seed'), seed_protocol='showdown_draws.SEED, one stream',
                    n_draws=n_draws)
    o = ds.add_layer('dk_scoring', gsis_rows, {'dk_points': np.asarray(dk_mat)},
                     spec_version=SPEC_VERSION, rng_stream='joint', row_teams=gsis_teams)
    if o.state is not State.PASS:
        return o
    if kick_rows:
        o = ds.add_layer('kicking', kick_rows, {'dk_points': np.asarray(kick_mat)},
                         spec_version=SPEC_VERSION, rng_stream='kicker', row_teams=gsis_teams)
        if o.state is not State.PASS:
            return o
    if dst_rows:
        o = ds.add_layer('dst', dst_rows, {'dk_points': np.asarray(dst_mat)},
                         spec_version=SPEC_VERSION, rng_stream='joint', row_axis='team')
        if o.state is not State.PASS:
            return o
    per_stat = 'ABSENT_AT_SEAL_TIME'
    if stat_draws and stat_fields:
        # stat_draws: {name|club: [(...STAT_FIELDS...), ...]} -> layers the grader's MAP names
        lay = {'qb': {'att': 'pass_att', 'pyds': 'pass_yards', 'ptd': 'pass_td'},
               'rushing': {'carries': 'carries', 'rushing_td': 'rush_td'},
               'rushing_total': {'rushing_yards': 'rush_yards'},
               'receiving': {'targets': 'targets', 'receptions': 'receptions',
                             'receiving_yards': 'rec_yards', 'receiving_td': 'rec_td'}}
        idx = {f: i for i, f in enumerate(stat_fields)}
        rows_g = [g for g in gsis_rows]
        key_of = {v.get('gsis_id'): k for k, v in by_key.items() if v.get('gsis_id')}
        for layer, metrics in lay.items():
            mats = {}
            for metric, field in metrics.items():
                m = []
                for g in rows_g:
                    sd = stat_draws.get(key_of.get(g))
                    m.append([t[idx[field]] for t in sd] if sd else [0.0] * n_draws)
                mats[metric] = np.asarray(m)
            o = ds.add_layer(layer, rows_g, mats, spec_version=SPEC_VERSION,
                             rng_stream='joint', row_teams=gsis_teams)
            if o.state is not State.PASS:
                return o
        per_stat = 'PRESENT'
    root = pathlib.Path(out_root) if out_root else ROOT
    pre = {'game_id': game_id, 'model_configuration': model_configuration,
           'projection_sha256': _file_sha(proj_path), 'draws_sha256': _file_sha(draws_path),
           'code_identity_sha256': identity_sha256(ident)}
    h16 = _sha(json.dumps(pre, sort_keys=True).encode())[:16]
    out_dir = root / game_id / model_configuration / h16
    out_dir.mkdir(parents=True, exist_ok=True)
    w = ds.write(out_dir)
    if w.state is not State.PASS:
        return w
    man = w.value if isinstance(w.value, dict) else ds.manifest()
    captures = [{'source': 'play_by_play_panel', 'sha256': cutoff.get('sha16'),
                 'retrieved_at': cutoff.get('retrieved_at')},
                {'source': 'dk_export', 'sha256': export_sha, 'retrieved_at': _mtime_utc(export_path)},
                {'source': 'official_inactives', 'sha256': inact_sha,
                 'retrieved_at': _mtime_utc(inactives_path)}] + [
                {'source': 'weekly_rosters', 'sha256': r['sha256'], 'retrieved_at': r['retrieved_at']}
                for r in rosters]
    observed_before = max(c['retrieved_at'] for c in captures if c.get('retrieved_at'))
    art = {
        'artifact': 'SHOWDOWN_FORECAST_ARTIFACT', 'spec_version': SPEC_VERSION,
        'model_family': MODEL_FAMILY, 'model_configuration': model_configuration,
        'game_id': game_id, 'kickoff_utc': kickoff_utc,
        'written_at': written_at, 'written_at_basis': written_at_basis,
        'code_identity': ident, 'code_identity_sha256': identity_sha256(ident),
        'projection_artifact': {'path': str(proj_path.relative_to(_REPO)) if proj_path.is_relative_to(_REPO) else str(proj_path),
                                'sha256': _file_sha(proj_path)},
        'draw_artifact': {'file': DA.DRAW_FILE_NAME, 'manifest': DA.MANIFEST_FILE_NAME,
                          'content_digest': man.get('content_digest'),
                          'file_sha256': (man.get('file') or {}).get('sha256'),
                          'n_draws': n_draws, 'per_stat_layers': per_stat,
                          'source_dk_draws_sha256': _file_sha(draws_path)},
        'information_set': {'observed_before': observed_before,
                            'newest_observation': observed_before},
        'data_cutoff': cutoff,
        'availability_vintage': {'official_inactives_sha256': inact_sha,
                                 'state_built_at_utc': state.get('built_at_utc'),
                                 'status_applied': ((state.get('official_inactives') or {})
                                                    .get('STATUS_APPLIED'))},
        'roster_vintage': rosters,
        'depth_vintage': {'basis': 'USAGE_DERIVED_FROM_PANEL',
                          'MEANING': ('this family ranks depth from panel usage '
                                      '(role_state_history.pregame_depth); no depth-chart capture '
                                      'is read, so the depth vintage is the play-by-play blob'),
                          'blob': cutoff.get('blob'), 'sha16': cutoff.get('sha16')},
        'source_captures': captures,
        'prospective_evidence': bool(prospective_evidence),
        'prospective_eligible': bool(prospective_evidence),
        'eligibility_reason': reason,
        'PROJECTION_SYSTEM_STATE': 'NOT_VALIDATED',
    }
    (out_dir / 'forecast_artifact.json').write_text(json.dumps(art, indent=1, sort_keys=True))
    return Outcome.ok('SHOWDOWN_SEALED', {'dir': str(out_dir), 'artifact': art},
                      f'{game_id} {model_configuration} sealed at {out_dir.name}',
                      dir=str(out_dir), per_stat_layers=per_stat, n_rows=len(gsis_rows))


# ------------------------------------------------------------------- the family's controls

def _c_family(art):
    f = art.get('model_family')
    if f != MODEL_FAMILY:
        return REFUSED, 'MODEL_FAMILY_NOT_SHOWDOWN', str(f)
    return ADMISSIBLE, 'MODEL_FAMILY_DECLARED', f


def _c_code(art):
    got = art.get('code_identity') or {}
    if not got:
        return LEGACY_UNVERIFIED, 'CODE_IDENTITY_UNRECORDED', ''
    now = code_identity()
    drift = sorted(m for m in now if got.get(m) != now[m])
    missing = sorted(m for m in now if m not in got)
    if missing:
        return REFUSED, 'CODE_IDENTITY_MODULE_MISSING', str(missing)
    if drift:
        return REFUSED, 'CODE_IDENTITY_DRIFT', str(drift)
    return ADMISSIBLE, 'CODE_IDENTITY_MATCHES_CURRENT', art.get('code_identity_sha256', '')


def _c_proj(art):
    pa = art.get('projection_artifact') or {}
    p = _REPO / str(pa.get('path') or '')
    if not pa.get('sha256') or not p.exists():
        return REFUSED, 'PROJECTION_ARTIFACT_ABSENT', str(pa.get('path'))
    if _file_sha(p) != pa['sha256']:
        return REFUSED, 'PROJECTION_HASH_MISMATCH', f'{_file_sha(p)[:16]} != {pa["sha256"][:16]}'
    return ADMISSIBLE, 'PROJECTION_HASH_MATCHES', pa['sha256'][:16]


def _c_draws(art):
    da = art.get('draw_artifact') or {}
    d = art.get('_dir')
    if not da.get('file_sha256'):
        return LEGACY_UNVERIFIED, 'DRAW_ARTIFACT_UNRECORDED', ''
    if d:
        p = pathlib.Path(d) / da.get('file', 'player_draws.npz')
        if not p.exists():
            return REFUSED, 'DRAW_ARTIFACT_FILE_ABSENT', str(p)
        if _file_sha(p) != da['file_sha256']:
            return REFUSED, 'DRAW_ARTIFACT_HASH_MISMATCH', f'{_file_sha(p)[:16]} != {da["file_sha256"][:16]}'
    return ADMISSIBLE, 'DRAW_ARTIFACT_HASH_MATCHES', da['file_sha256'][:16]


def _c_slate(art):
    g, k = art.get('game_id'), art.get('kickoff_utc')
    if not g or not k:
        return REFUSED, 'SLATE_IDENTITY_INCOMPLETE', f'game_id={g} kickoff_utc={k}'
    return ADMISSIBLE, 'SLATE_IDENTIFIED', f'{g}@{k}'


def _c_time(art):
    caps = art.get('source_captures') or []
    if not caps:
        return REFUSED, 'TIME_BASIS_NO_SOURCE_CAPTURES', 'no input capture'
    o = TB.assert_prospective_order([c.get('retrieved_at') for c in caps],
                                    art.get('written_at'), art.get('kickoff_utc'))
    if o.state is not State.PASS:
        return REFUSED, o.code, (o.detail or '')[:200]
    return ADMISSIBLE, o.code, o.detail


def _c_cutoff(art):
    v = (art.get('information_set') or {}).get('observed_before')
    if not v:
        return REFUSED, 'DATA_CUTOFF_UNDECLARED', ''
    return ADMISSIBLE, 'DATA_CUTOFF_DECLARED', str(v)


def _c_avail(art):
    a = art.get('availability_vintage') or {}
    if not a.get('official_inactives_sha256') or not a.get('state_built_at_utc'):
        return REFUSED, 'AVAILABILITY_VINTAGE_UNDECLARED', str(sorted(a))
    return ADMISSIBLE, 'AVAILABILITY_VINTAGE_DECLARED', a['official_inactives_sha256'][:16]


def _c_roster_depth(art):
    r, d = art.get('roster_vintage') or [], art.get('depth_vintage') or {}
    if not r or not d.get('sha16'):
        return REFUSED, 'ROSTER_DEPTH_VINTAGE_UNDECLARED', f'{len(r)} roster(s), depth={bool(d)}'
    return ADMISSIBLE, 'ROSTER_DEPTH_VINTAGE_DECLARED', f'{len(r)} roster capture(s), depth {d.get("basis")}'


def _c_evidence(art):
    v = art.get('prospective_evidence')
    if v is None:
        return LEGACY_UNVERIFIED, 'EVIDENCE_FLAG_UNRECORDED', ''
    if v is not True:
        return REFUSED, 'ARTIFACT_DECLARES_ITSELF_NOT_EVIDENCE', str(art.get('eligibility_reason') or v)
    return ADMISSIBLE, 'ARTIFACT_DECLARES_ITSELF_EVIDENCE', 'true'


CONTROL_EVALUATORS = {
    'model_family_declared': _c_family, 'code_identity_matches_current': _c_code,
    'projection_hash_matches_disk': _c_proj, 'draw_artifact_hash_matches_disk': _c_draws,
    'slate_identity': _c_slate, 'time_basis': _c_time, 'data_cutoff_declared': _c_cutoff,
    'availability_vintage_declared': _c_avail, 'roster_depth_vintage_declared': _c_roster_depth,
    'prospective_evidence_eligibility': _c_evidence,
}


def is_showdown(art) -> bool:
    return (art or {}).get('model_family') == MODEL_FAMILY
