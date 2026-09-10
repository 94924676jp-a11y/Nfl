"""Assemble the pregame player board from a sealed forecast.

READ-ONLY OVER THE FROZEN ENGINE. This module imports no model layer and
computes no projection. It reads a sealed artifact and its draws, joins the
identity and status information that was already captured, and arranges it.

GOVERNANCE TRAVELS WITH THE NUMBERS. Every board carries its authorization
state, and an unauthorized forecast is labelled SHADOW / NOT AUTHORIZED in the
header and in the machine-readable payload. It is never described as published,
prospective or production, whatever else is true of it.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import pathlib

from nfl.product import confidence as CONF
from nfl.product import distributions as D
from nfl.product import metrics as M
from nfl.product import thresholds as TH

_REPO = pathlib.Path(__file__).resolve().parents[2]


def _parse(t):
    if not t:
        return None
    d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def roster_identity(season, week, teams, blob=None):
    """gsis_id -> position/team, from the same vintage the forecast used."""
    out = {}
    paths = ([_REPO / blob] if blob else
             sorted((_REPO / 'nfl' / 'vintage').glob(
                 'weekly_rosters.*.reduced.csv.gz')))
    for p in paths:
        if not p.exists():
            continue
        for r in csv.DictReader(gzip.open(p, 'rt')):
            if (r.get('season') == str(season) and r.get('week') == str(week)
                    and r.get('team') in teams and r.get('gsis_id')):
                out.setdefault(r['gsis_id'],
                               {'position': r.get('position'),
                                'team': r.get('team')})
        if blob:
            break
    return out


def depth_rank(season, week, teams, blob=None):
    """gsis_id -> (pos_abb, rank) from the newest depth chart in the vintage."""
    out = {}
    paths = ([_REPO / blob] if blob else
             sorted((_REPO / 'nfl' / 'vintage').glob(
                 'depth_charts.*.reduced.csv.gz')))
    for p in paths:
        if not p.exists():
            continue
        rows = [r for r in csv.DictReader(gzip.open(p, 'rt'))
                if r.get('team') in teams and r.get('gsis_id')]
        if not rows:
            continue
        newest = max(r['dt'] for r in rows)
        for r in rows:
            if r['dt'] != newest:
                continue
            try:
                out[r['gsis_id']] = (r['pos_abb'], int(r['pos_rank']))
            except (TypeError, ValueError):
                continue
        if blob:
            break
    return out


def freshness(artifact) -> dict:
    """How old each input was AT THE MOMENT THE FORECAST WAS WRITTEN.

    Age against the wall clock would drift every time the board is re-rendered
    and would describe the reader's afternoon rather than the forecast's
    information set.
    """
    wrote = _parse(artifact.get('written_at'))
    ko = _parse(artifact.get('kickoff_utc'))
    rows = []
    for c in artifact.get('source_captures') or []:
        got = _parse(c.get('retrieved_at'))
        rows.append({
            'source': c.get('source'),
            'retrieved_at': c.get('retrieved_at'),
            'sha256_16': (c.get('sha256') or '')[:16],
            'hours_before_written_at':
                round((wrote - got).total_seconds() / 3600.0, 2)
                if wrote and got else None,
            'hours_before_kickoff':
                round((ko - got).total_seconds() / 3600.0, 2)
                if ko and got else None})
    rows.sort(key=lambda r: r['source'] or '')
    return {'written_at': artifact.get('written_at'),
            'kickoff_utc': artifact.get('kickoff_utc'),
            'lead_time_hours':
                round((ko - wrote).total_seconds() / 3600.0, 2)
                if ko and wrote else None,
            'sources': rows,
            'oldest_input_hours_before_kickoff':
                max([r['hours_before_kickoff'] for r in rows
                     if r['hours_before_kickoff'] is not None] or [None])
                if rows else None}


def authorization_state(artifact) -> dict:
    """What this forecast is allowed to be called. Never softened."""
    from nfl.production import authorization as AUTH
    pub = AUTH.may_publish()
    authorized = pub.state.name == 'PASS'
    return {
        'nfl1': 'AUTHORIZED' if authorized else 'NOT AUTHORIZED',
        'code': pub.code,
        'detail': (pub.detail or '')[:300],
        'promoted': bool(artifact.get('promoted')),
        'prospective_eligible': bool(artifact.get('prospective_eligible')),
        'test_only': bool(artifact.get('TEST_ONLY')),
        'label': ('LIVE NFL-1 FORECAST' if authorized
                  else 'SHADOW / NOT AUTHORIZED'),
        'may_be_called_published': authorized,
        'note': ('This forecast is not published, not prospective evidence '
                 'and not production output. It was executed internally under '
                 'a frozen candidate configuration.' if not authorized else
                 'Authorization was derived from the canonical gate, not set '
                 'by hand.'),
    }


def layer_governance(directory) -> list:
    """Each stage's own spec version and warnings, verbatim.

    THE MODEL DECLARES ITS OWN LIMITATIONS AND THE BOARD REPEATS THEM. Writing
    my own summary of what a layer can be trusted for would put a second,
    unversioned opinion next to the governed one, and the two would drift.
    """
    p = pathlib.Path(directory) / 'run_status.json'
    if not p.exists():
        return []
    st = json.loads(p.read_text()).get('stages') or []
    out = []
    for s in st:
        spec = s.get('spec_version') or ''
        warns = [str(w) for w in (s.get('warnings') or [])]
        if not spec and not warns:
            continue
        out.append({'stage': s.get('stage'), 'state': s.get('state'),
                    'code': s.get('code'), 'spec_version': spec,
                    'warnings': warns})
    return out


def build(directory, season, week, readiness_by_team=None,
          roster_blob=None, depth_blob=None) -> dict:
    """The whole board, as data. Rendering is a separate concern."""
    fc = D.Forecast(directory)
    art = fc.artifact
    teams = art.get('team_ids') or []
    ident = roster_identity(season, week, teams, roster_blob)
    depth = depth_rank(season, week, teams, depth_blob)
    ready = readiness_by_team or {}

    players = []
    for pid, layers in fc.players().items():
        info = ident.get(pid) or {}
        pos = info.get('position')
        if pos not in M.POSITION_LAYERS:
            # A player the forecast covers but the roster does not name is
            # reported, not dropped -- silently losing him is how a board
            # under-reports and looks complete.
            pos = pos or 'UNKNOWN'
        team = info.get('team')
        mets = {}
        for layer in sorted(layers):
            for key in layers[layer]:
                spec = M.SUPPORTED.get((layer, key))
                if spec is None:
                    continue          # not a declared product metric
                v = fc.vector(layer, key, pid)
                if v is None:
                    continue
                status, caveat = M.status_of(layer, key)
                mets[f'{layer}/{key}'] = {
                    'label': spec['label'], 'kind': spec['kind'],
                    'status': status, 'caveat': caveat,
                    **D.summary(v),
                    'thresholds': TH.probabilities(v, layer, key)}
        if not mets:
            continue
        dr = depth.get(pid)
        row = {
            'gsis_id': pid, 'position': pos, 'team': team,
            'depth_chart': f'{dr[0]}{dr[1]}' if dr else None,
            'layers': sorted(layers), 'metrics': mets,
            'touchdown': TH.td_probability(fc, pid, layers),
            'unavailable': M.unavailable_for(pos),
            'opportunity_share': _shares(fc, pid, layers),
        }
        row['confidence'] = CONF.score_player(
            fc, pid, pos, sorted(layers), ready.get(team))
        players.append(row)

    players.sort(key=lambda r: (M.POSITION_ORDER.index(r['position'])
                                if r['position'] in M.POSITION_ORDER else 99,
                                -r['confidence']['score']))
    return {
        'artifact': 'NFL_V1_PREGAME_PLAYER_BOARD',
        'game_id': fc.game_id, 'teams': teams,
        'season': season, 'week': week,
        'run_id': fc.run_id,
        'draw_content_digest': fc.content_digest,
        'draws_sha256': fc.draws_sha256,
        'draws_file': str(fc.draws_path.name),
        'n_draws': fc.n_draws,
        'model_configuration': art.get('model_configuration'),
        'component_manifest': {
            'applied': art.get('candidate_components_applied') or [],
            'not_reached': art.get('candidate_components_not_reached') or []},
        'code_commit': art.get('code_commit'),
        'completeness': art.get('completeness'),
        'eligibility_verdict': art.get('eligibility_verdict'),
        'authorization': authorization_state(art),
        'freshness': freshness(art),
        'readiness': ready,
        'players': players,
        'n_players': len(players),
        'confidence_board': CONF.board(players),
        'layer_governance': layer_governance(directory),
        'threshold_disclaimer': TH.DISCLAIMER,
        'unavailable_metrics': [dict(v, metric=f'{k[0]}/{k[1]}')
                                for k, v in sorted(M.UNSUPPORTED.items())],
    }


def _shares(fc, pid, layers):
    """This player's share of his game's opportunity pool, per metric."""
    out = {}
    for layer, key in (('qb', 'db'), ('receiving', 'targets'),
                       ('rushing', 'carries')):
        if layer not in layers:
            continue
        v = fc.vector(layer, key, pid)
        tot = fc.arrays.get(f'{layer}__{key}')
        if v is None or tot is None:
            continue
        denom = float(tot.sum(0).mean())
        if denom <= 0:
            continue
        out[f'{layer}/{key}'] = {
            'share_of_game_pool': round(float(v.mean()) / denom, 4),
            'basis': 'mean of the player\'s draws over the mean of the '
                     'game-wide pool on the same draw index'}
    return out
