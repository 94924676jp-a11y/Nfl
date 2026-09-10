"""Decide whether a game deserves a new board, and produce it if so.

SAFE TO RUN ON ANY CADENCE. Every run is one of four outcomes, and three of
them write nothing:

  WRITTEN            newer legitimate inputs existed; a new board was sealed
  NO_NEW_INPUTS      the vintages are byte-identical to the last board's
  PAST_KICKOFF       pregame is over; a pregame board can no longer be written
  REFUSED            the pipeline itself refused, with its own named code

So the schedule can be as tight as you like without manufacturing boards. The
refresh decision is made by comparing INPUT FINGERPRINTS, never by comparing
clocks: a scheduler that fires more often must not be able to produce more
boards, because that would restamp stale inputs as fresh.

THIS MODULE CANNOT REACH CAPTURE OR GOVERNANCE. It writes only under
`nfl/product/boards/`, it never invokes a capture tool, and it never writes a
manifest, a G0A artifact or a model file. A product run that fails leaves both
untouched -- there is no path from here to there.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import store as ST                              # noqa: E402

LOCK = ST.ROOT / '.orchestrator.lock'
LOCK_STALE_SECONDS = 3600


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _parse(t):
    d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _iso(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ')


class Lock:
    """One orchestrator at a time. Two concurrent runs on the same game would
    race to create the same directory, and the loser's refusal would look like
    a defect rather than the collision it is."""

    def __enter__(self):
        ST.ROOT.mkdir(parents=True, exist_ok=True)
        if LOCK.exists():
            age = (_now() - dt.datetime.fromtimestamp(
                LOCK.stat().st_mtime, dt.timezone.utc)).total_seconds()
            if age < LOCK_STALE_SECONDS:
                raise RuntimeError(
                    f'ORCHESTRATOR_ALREADY_RUNNING: {LOCK} is {age:.0f}s old. '
                    f'Refusing to run twice over one board directory.')
            LOCK.unlink()          # stale; the previous run died
        LOCK.write_text(_iso(_now()))
        return self

    def __exit__(self, *a):
        if LOCK.exists():
            LOCK.unlink()
        return False


def plan(game_id, season=2026, week=1, now=None):
    """What a run would do, without doing it. Pure, so it can be tested."""
    from nfl.research.shadow import information_set as IS
    from nfl.tools.make_board import kickoff_for

    now = now or _now()
    ko = kickoff_for(season, week, game_id)
    if now >= _parse(ko):
        return {'status': 'PAST_KICKOFF', 'game_id': game_id,
                'kickoff_utc': ko, 'checked_at': _iso(now),
                'detail': 'pregame is over; a pregame board written now would '
                          'carry a post-kickoff clock'}

    info = IS.build(ko, observed_before=_iso(now))
    fp = ST.input_fingerprint(info)
    prev = ST.latest(game_id)
    if prev and prev.get('input_fingerprint') == fp:
        return {'status': 'NO_NEW_INPUTS', 'game_id': game_id,
                'kickoff_utc': ko, 'checked_at': _iso(now),
                'input_fingerprint': fp,
                'previous_board': prev.get('board_dir'),
                'previous_written_at': prev.get('written_at'),
                'detail': 'every source vintage is byte-identical to the last '
                          'board. Writing another would restamp stale inputs '
                          'as fresh.'}
    return {'status': 'WOULD_WRITE', 'game_id': game_id, 'kickoff_utc': ko,
            'checked_at': _iso(now), 'input_fingerprint': fp,
            'newest_observation': info['newest_observation'],
            'previous_fingerprint': (prev or {}).get('input_fingerprint'),
            'information_set': info}


def refresh(game_id, season=2026, week=1, draws=1000, seed=20260908,
            model_configuration='V1_CANDIDATE', now=None) -> dict:
    """One orchestration pass over one game."""
    # plan() reaches the week plan and the vintage manifest, and both raise
    # rather than return on a bad input. Contained here so `refresh` always
    # answers with a status.
    try:
        p = plan(game_id, season, week, now)
    except SystemExit as e:
        return {'game_id': game_id, 'status': 'REFUSED',
                'refusal': str(e)[:300]}
    if p['status'] != 'WOULD_WRITE':
        return p

    now = now or _now()
    written_at = _iso(now)
    # THE CLOCK IS CHECKED AGAINST KICKOFF ONE MORE TIME, HERE, because plan()
    # and the run are not simultaneous and a scheduler can fire at the boundary.
    if _parse(written_at) >= _parse(p['kickoff_utc']):
        return {**p, 'status': 'PAST_KICKOFF',
                'detail': 'kickoff passed between planning and execution'}

    from nfl.tools.make_board import build_one
    import tempfile
    tmp = tempfile.mkdtemp(prefix='board_')
    try:
        summary, bd, run_dir = build_one(
            season, week, game_id, written_at, tmp, draws, seed,
            model_configuration)
    except SystemExit as e:
        return {**{k: v for k, v in p.items() if k != 'information_set'},
                'status': 'REFUSED', 'written_at': written_at,
                'refusal': str(e)[:400]}
    if bd is None:
        first = next((s for s in summary['stages']
                      if s['state'] not in ('PASS', 'NOT_APPLICABLE')), {})
        return {**{k: v for k, v in p.items() if k != 'information_set'},
                'status': 'REFUSED', 'written_at': written_at,
                'run_id': summary.get('run_id'),
                'refusal': f'{first.get("stage")}: {first.get("code")}',
                'detail': (first.get('detail') or '')[:300]}

    files = {}
    for name in ('forecast_artifact.json', 'player_draws_manifest.json',
                 'run_status.json', 'board.json', 'BOARD.md'):
        src = pathlib.Path(run_dir) / name
        if src.exists():
            files[name] = src.read_bytes()
    npz = pathlib.Path(run_dir) / 'player_draws.npz'
    if npz.exists():
        import gzip
        files['player_draws.npz.gz'] = gzip.compress(npz.read_bytes())

    auth = bd['authorization']
    meta = {
        'artifact': 'NFL_PREGAME_BOARD_RECORD',
        'game_id': game_id, 'kickoff_utc': p['kickoff_utc'],
        'written_at': written_at,
        'lead_time_hours': bd['freshness']['lead_time_hours'],
        'run_id': bd['run_id'],
        'draw_content_digest': bd['draw_content_digest'],
        'n_draws': bd['n_draws'],
        'input_fingerprint': p['input_fingerprint'],
        'input_vintages': [
            {'source': s['source'], 'retrieved_at': s['retrieved_at'],
             'sha256_16': s['sha256_16'],
             'hours_before_kickoff': s['hours_before_kickoff']}
            for s in bd['freshness']['sources']],
        'model_configuration': bd['model_configuration'],
        'component_manifest': bd['component_manifest'],
        'code_commit': bd['code_commit'],
        'authorization_state': auth,
        'label': auth['label'],
        'promoted': auth['promoted'],
        'prospective_eligible': auth['prospective_eligible'],
        'readiness': {t: r.get('state')
                      for t, r in (bd.get('readiness') or {}).items()},
        'supersedes': (ST.latest(game_id) or {}).get('board_dir'),
        'superseding_note':
            'A LATER BOARD NEVER REPLACES AN EARLIER ONE. The earlier board '
            'stays exactly as it was written, under its own authorization '
            'state, and remains the record of what was forecast at that time.',
    }
    d = ST.write(game_id, written_at, bd['run_id'], files, meta)

    row = {'game_id': game_id, 'status': 'WRITTEN', 'written_at': written_at,
           'run_id': bd['run_id'], 'kickoff_utc': p['kickoff_utc'],
           'input_fingerprint': p['input_fingerprint'],
           'draw_content_digest': bd['draw_content_digest'],
           'label': auth['label'], 'nfl1': auth['nfl1'],
           'promoted': auth['promoted'],
           'model_configuration': bd['model_configuration'],
           'components_applied': bd['component_manifest']['applied'],
           'n_players': bd['n_players'],
           'board_dir': str(d.relative_to(_REPO)),
           'board_sha256': hashlib.sha256(
               (d / 'BOARD.md').read_bytes()).hexdigest()}
    ST.append_index(row)
    ST.set_latest(game_id, row)
    return {**row, 'status': 'WRITTEN', 'newest_observation':
            p['newest_observation']}


def run(game_ids, **kw) -> list:
    """Every game, under one lock."""
    out = []
    with Lock():
        for gid in game_ids:
            try:
                out.append(refresh(gid, **kw))
            except ST.BoardExists as e:
                out.append({'game_id': gid, 'status': 'ALREADY_WRITTEN',
                            'detail': str(e)[:300]})
            except (Exception, SystemExit) as e:          # noqa: BLE001
                # A PRODUCT FAILURE IS A PRODUCT FAILURE. It is recorded and
                # the pass continues; it never propagates anywhere, and there
                # is nothing outside this directory for it to damage.
                #
                # SystemExit IS CAUGHT DELIBERATELY. The helpers this calls
                # raise SystemExit for a bad game id or an unusable week plan,
                # and SystemExit is a BaseException -- so `except Exception`
                # let it through, one bad game killed the whole scheduled pass,
                # and every later game in the list was silently never checked.
                # An unattended job that dies on its first bad input is worse
                # than one that reports the bad input.
                out.append({'game_id': gid, 'status': 'ERROR',
                            'error': f'{type(e).__name__}: {e}'[:300]})
    return out
