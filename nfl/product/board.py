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

from sportsplatform.governance.outcome import Cause, Outcome, State
from nfl.product import confidence as CONF
from nfl.product import distributions as D
from nfl.product import metrics as M
from nfl.product import names as NM
from nfl.product import thresholds as TH

_REPO = pathlib.Path(__file__).resolve().parents[2]

from nfl.production.nonqb import vintage_selector as VS       # noqa: E402
from nfl.production.nonqb import depth_vintage as _DV  # noqa: E402


def _parse(t):
    if not t:
        return None
    d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _sha16_of(path) -> str:
    """The content hash the capture layer put in the filename. Not a guess.

    Used ONLY as a deterministic tiebreak between two blobs carrying the same
    vendor `dt`. It is never a selection criterion on its own -- ordering by a
    content hash is exactly what `team_volume_v1.coaches` does, and WS12 lists
    that as a selector with no clock.
    """
    parts = pathlib.Path(path).name.split('.')
    return parts[1] if len(parts) > 1 else ''


def roster_identity_outcome(season, week, teams, blob=None,
                            as_of=VS.UNSET) -> Outcome:
    """gsis_id -> position/team, from the vintage lawful at the cut.

    The old form globbed every reduced roster blob and merged them in filename
    order, `setdefault` letting whichever file sorted first win. That is the
    same defect class as L3: a selection resolved by filesystem ordering. The
    reduced roster carries no row-level clock (season, week, team, gsis_id,
    position and nothing else), so the capture's `retrieved_at` is the only
    clock available and the canonical selector applies it.

    N1, 2026-09-14. THE DISPLAY NAME IS READ FROM THE SAME BYTES.

    `quality_gates.IDENTITY_DEPTH_ROLE_CONFLICT` withheld all 19 rows of the
    DEN@KC board because none carried a human-readable name. The name is not a
    forecast input and nothing downstream of it changes, but a row that renders
    a gsis_id where a person belongs is not a product row, and the gate is
    right to refuse it.

    The name is taken from THE ROSTER BLOB THIS FUNCTION IS ALREADY READING,
    not from a second source selected separately. That matters for chronology:
    reading one more column out of bytes already admitted at this cut admits no
    information the board did not already have, so there is nothing new to
    date. A separately selected name source would need its own cut, its own
    refusal path and its own provenance line, for a field no projection
    consumes.

    `full_name` IS ABSENT FROM THE REDUCED VINTAGE, AND THAT IS DELIBERATE.
    `capture/registry.py:185` declares `reduce_cols` for weekly_rosters as
    (season, week, team, gsis_id, position) under `durability="reduce"`, and
    `tools/capture_vintage._reduce_frame` warns in its own docstring that its
    output bytes ARE the artifact identity and that changing the column set is
    a TRANSFORM_VERSION change. Widening `reduce_cols` would also do nothing
    for any blob already stored. So the reduction is not undone here. Instead:
    when the selected blob carries a name column it is read, and when it does
    not, `build()` falls back to `nfl.product.names` under the SAME cut and
    says on the row which of the two answered.

    An id no lawful capture names stays unresolved and says so. Inventing a
    name -- from a hardcoded table, a fuzzy match on another feed, or the
    football_name short form -- would be worse than printing the id.
    """
    cut = VS.resolve_as_of(as_of, caller='board.roster_identity')
    if blob:
        paths = [_REPO / blob]
        chosen = {'blob': str(blob), 'basis': 'CALLER_SUPPLIED_BLOB'}
    else:
        sel = VS.select('weekly_rosters', as_of=cut)
        if sel.state is not State.PASS:
            return sel
        paths = [sel.value.path()]
        chosen = {'blob': sel.value.blob,
                  'retrieved_at': sel.value.retrieved_at,
                  'content_sha256': sel.value.content_sha256,
                  'basis': 'VINTAGE_SELECTOR'}
    out = {}
    name_cols, n_named = [], 0
    for p in paths:
        if not p or not p.exists():
            continue
        rdr = csv.DictReader(gzip.open(p, 'rt'))
        rows = list(rdr)
        cols = [c for c in NM.NAME_COLUMNS if c in (rdr.fieldnames or [])]
        name_cols = sorted(set(name_cols) | set(cols))
        for r in rows:
            if not (r.get('season') == str(season)
                    and r.get('week') == str(week)
                    and r.get('team') in teams and r.get('gsis_id')):
                continue
            nm, ncol = None, None
            for c in cols:
                v = (r.get(c) or '').strip()
                if v:
                    nm, ncol = v, c
                    break
            out.setdefault(r['gsis_id'],
                           {'position': r.get('position'),
                            'team': r.get('team'),
                            'name': nm, 'name_column': ncol})
    n_named = sum(1 for v in out.values() if v.get('name'))
    chosen = dict(chosen,
                  name_columns_present=name_cols,
                  name_column_absent=not name_cols,
                  n_named=n_named)
    if not out:
        return Outcome.blocked(
            'ROSTER_IDENTITY_EMPTY',
            f'the roster vintage lawful at {cut.isoformat()} carries no '
            f'{season} week {week} row for {sorted(teams)}. An empty identity '
            f'map is a refusal, not a board with no players.',
            cause=Cause.DATA, as_of=cut.isoformat(), chosen=chosen)
    return Outcome.ok('ROSTER_IDENTITY_OK', value=out,
                      spec_version=VS.SPEC_VERSION, as_of=cut.isoformat(),
                      n_players=len(out), n_named=n_named, chosen=chosen)


def roster_identity(season, week, teams, blob=None, as_of=VS.UNSET):
    """The dict form. Raises rather than returning a silent empty."""
    o = roster_identity_outcome(season, week, teams, blob, as_of)
    if o.state is not State.PASS:
        raise VS.NoLawfulVintage(f'{o.code}: {o.detail}')
    return o.value


def depth_rank_outcome(season, week, teams, blob=None,
                       as_of=VS.UNSET) -> Outcome:
    """gsis_id -> (pos_abb, rank), from the newest chart LAWFUL AT THE CUT.

    L3. WHAT WAS WRONG.

    The old form accepted `season` and `week` and used neither. With
    `blob=None` it globbed every reduced depth blob, iterated in filename
    order and did NOT break, so the answer came from the LAST blob in
    content-hash order that carried rows for those teams. Measured at HEAD
    837d52f for DAL/NYG, the six blobs carry max `dt` of 2026-09-06, -07, -08,
    -09, -10 and -13, and the one that answered was 2026-09-08 -- neither the
    newest nor the point-in-time one. Which error you got depended on a
    content hash. `run_forecast.py:679` wraps the call in
    `except Exception: dr = {}`, so a total failure was indistinguishable from
    every player lacking a rank.

    WHAT CHANGED, AND WHAT DELIBERATELY DID NOT.

    Changed: WHICH chart. The candidate blobs come from the canonical selector
    rather than from a glob, rows are bounded by the vendor `dt` inside them
    -- a real publication clock, preferred over retrieval for this family --
    and the newest lawful `dt` is taken PER TEAM, which is how
    `depth_vintage.daily_point_in_time` already does it, so the two selectors
    agree by construction.

    Not changed: HOW a rank is read. This still returns the vendor's raw
    `pos_abb` and `pos_rank`. `depth_vintage` re-ranks onto a common ordinal
    scale to bridge the 2020-2024 / 2025-2026 vendor break, and swapping that
    in here would move R6 tier assignments for a reason that has nothing to do
    with chronology. One repair, one effect.
    """
    cut = VS.resolve_as_of(as_of, caller='board.depth_rank')
    if blob:
        paths = [_REPO / blob]
    else:
        lawful, rejected = VS.candidates('depth_charts', as_of=cut)
        if not lawful:
            return Outcome.blocked(
                'DEPTH_RANK_CAPTURE_ABSENT',
                f'no depth capture is lawful at {cut.isoformat()}; '
                f'{len(rejected)} capture(s) exist and every one is later, '
                f'unclocked or missing from disk. A later chart is not '
                f'evidence about an earlier game.',
                cause=Cause.DATA, as_of=cut.isoformat(),
                n_rejected=len(rejected),
                evidence_ceiling=VS.FAMILIES['depth_charts']['ceiling'])
        paths = [v.path() for v in lawful]
    # (dt, blob sha16) per team. The sha is a tiebreak between two blobs
    # carrying the same dt and is never the primary key.
    best, rows_by_team = {}, {}
    seen_dt = 0
    for p in paths:
        if not p or not p.exists():
            continue
        sha = _sha16_of(p)
        for r in csv.DictReader(gzip.open(p, 'rt')):
            t = r.get('team')
            if t not in teams or not r.get('gsis_id'):
                continue
            d = _parse(r.get('dt'))
            if d is None:
                continue
            seen_dt += 1
            if d >= cut:                 # STRICTLY before the cut, as
                continue                 # depth_vintage.daily_point_in_time
            k = (d, sha)
            if t not in best or k > best[t]:
                best[t] = k
                rows_by_team[t] = []
            if k == best[t]:
                rows_by_team[t].append(r)
    missing = [t for t in teams if t not in best]
    if missing:
        return Outcome.deferred(
            'DEPTH_RANK_NOT_POINT_IN_TIME',
            f'{len(missing)} of {len(teams)} team(s) have no depth chart '
            f'stamped before {cut.isoformat()}; {seen_dt} dated row(s) were '
            f'read and all of them for these teams are later. The rank is '
            f'refused rather than filled from a later chart.',
            owed={'teams': sorted(missing), 'as_of': cut.isoformat(),
                  'n_dated_rows_considered': seen_dt})
    out, chosen = {}, {}
    for t, (d, sha) in sorted(best.items()):
        chosen[t] = {'dt': d.isoformat().replace('+00:00', 'Z'),
                     'blob_sha16': sha,
                     'hours_before_cut': round(
                         (cut - d).total_seconds() / 3600.0, 2),
                     'n_listed': len(rows_by_team[t])}
        for r in rows_by_team[t]:
            # R3 DEFECT 1, CLOSED HERE. A return slot is a special-teams
            # listing, not an offensive depth position, and this dict is keyed
            # on player alone -- so a receiver listed both at WR and at PR had
            # whichever row the vendor wrote last, and a `PR 1` silently became
            # his offensive depth rank. `depth_vintage.daily_point_in_time`
            # already excludes these from its ordering (RETURN_SLOTS, line
            # 129); this selector did not, so the two disagreed. Skipped, never
            # re-ranked: a player listed ONLY at a return slot has no
            # offensive depth evidence, and absence is the honest answer.
            if (r.get('pos_abb') or '').upper() in _DV.RETURN_SLOTS:
                continue
            try:
                out[r['gsis_id']] = (r['pos_abb'], int(r['pos_rank']))
            except (TypeError, ValueError, KeyError):
                continue
    if not out:
        return Outcome.blocked(
            'DEPTH_RANK_EMPTY',
            f'a lawful chart was found for every team at {cut.isoformat()} '
            f'and no row carried a usable pos_abb/pos_rank pair',
            cause=Cause.DATA, as_of=cut.isoformat(), chosen=chosen)
    return Outcome.ok(
        'DEPTH_RANK_OK', value=out, spec_version=VS.SPEC_VERSION,
        as_of=cut.isoformat(), n_players=len(out), chosen=chosen,
        n_blobs_considered=len(paths),
        composite_sha256=VS.composite_hash(
            {(t, f'{v["dt"]}:{v["blob_sha16"]}') for t, v in chosen.items()}
        )[:16],
        selection_rule='per team: max(vendor dt strictly before the cut), '
                       'tiebroken by blob content hash. Never glob order, '
                       'never filesystem mtime.')


def depth_rank(season, week, teams, blob=None, as_of=VS.UNSET):
    """The dict form, kept for callers that hold one.

    IT RAISES. A dict cannot express "no lawful chart exists", and the one
    production caller wrapped this in `except Exception: dr = {}` -- so under
    the old code a refusal and a chart full of unranked players were the same
    observation. `depth_rank_outcome` is the governed form and new callers
    should take it; this one refuses loudly so that the failure-open wrapper
    at least records something rather than silently ranking nobody.
    """
    o = depth_rank_outcome(season, week, teams, blob, as_of)
    if o.state is not State.PASS:
        raise VS.NoLawfulVintage(f'{o.code}: {o.detail}')
    return o.value


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
    # THE BOARD'S CUT COMES FROM THE FORECAST IT IS RENDERING, not from the
    # clock on the wall. A board re-rendered a week later must show the
    # information set the forecast was written against, or it is describing
    # the reader's afternoon -- the same argument `freshness()` already makes
    # for ages, applied to selection.
    as_of = VS.as_of_cut(art.get('kickoff_utc'), art.get('written_at'))
    vintage_refusals = []
    if as_of is None:
        vintage_refusals.append(
            {'input': 'ALL', 'code': 'BOARD_CLOCK_UNRESOLVED',
             'detail': 'the sealed artifact carries neither written_at nor '
                       'kickoff_utc, so no cutoff can be derived and no '
                       'perishable input may be selected'})
        ident, depth = {}, {}
    else:
        io_ = roster_identity_outcome(season, week, teams, roster_blob, as_of)
        ident = io_.value if io_.state is State.PASS else {}
        if io_.state is not State.PASS:
            vintage_refusals.append({'input': 'weekly_rosters',
                                     'code': io_.code,
                                     'detail': io_.detail[:300]})
        do_ = depth_rank_outcome(season, week, teams, depth_blob, as_of)
        depth = do_.value if do_.state is State.PASS else {}
        if do_.state is not State.PASS:
            vintage_refusals.append({'input': 'depth_charts',
                                     'code': do_.code,
                                     'detail': do_.detail[:300]})
    ready = readiness_by_team or {}

    # THE DISPLAY NAME. Primary: the roster vintage this board already
    # selected and already read, which is the only source that costs no extra
    # chronology argument -- one more column out of bytes already admitted at
    # this cut admits no information the board did not have. The fallback is
    # consulted ONLY when the primary leaves an id unnamed, which is the
    # reduced-vintage case; a board whose own roster blob names everyone opens
    # no second file.
    roster_chosen = (io_.evidence.get('chosen')
                     if as_of is not None and io_.state is State.PASS
                     else None) or {}

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
        nm = (info.get('name') or '').strip() or None
        row = {
            'gsis_id': pid, 'position': pos, 'team': team,
            'name': nm,
            'name_provenance': (
                {'source': 'weekly_rosters',
                 'blob': roster_chosen.get('blob'),
                 'column': info.get('name_column'),
                 'basis': roster_chosen.get('basis'),
                 'selected_for': 'the roster vintage this board already '
                                 'selected, read for its own name column'}
                if nm else None),
            'depth_chart': f'{dr[0]}{dr[1]}' if dr else None,
            'layers': sorted(layers), 'metrics': mets,
            'touchdown': TH.td_probability(fc, pid, layers),
            'unavailable': M.unavailable_for(pos),
            'opportunity_share': _shares(fc, pid, layers),
        }
        row['confidence'] = CONF.score_player(
            fc, pid, pos, sorted(layers), ready.get(team))
        players.append(row)

    name_fallback = _name_fallback(players, as_of, vintage_refusals)

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
        'vintage_selection': {
            'as_of': as_of.isoformat() if as_of is not None else None,
            'basis': 'min(written_at, kickoff - 1us) from the sealed artifact',
            'spec_version': VS.SPEC_VERSION,
            'roster': (io_.evidence.get('chosen')
                       if as_of is not None and io_.state is State.PASS
                       else None),
            'depth': (do_.evidence.get('chosen')
                      if as_of is not None and do_.state is State.PASS
                      else None),
            # NAMED, NOT ABSENT. A board that could not select a perishable
            # input says so on its face; the column going blank is not the
            # report.
            'refusals': vintage_refusals},
        'readiness': ready,
        # WHERE EVERY NAME ON THIS BOARD CAME FROM, and which ids have none.
        # A count of resolved rows with no list of the unresolved ones is the
        # shape of report that lets an empty join look like a complete board.
        'name_resolution': {
            'as_of': as_of.isoformat() if as_of is not None else None,
            'rule': 'the roster vintage this board selected, read for its own '
                    'name column; then any capture lawful at the same cut. '
                    'Never a hardcoded map, never a fuzzy match, never a '
                    'name carried over from another cut.',
            'display_only': 'No projection reads this field. An unresolved id '
                            'is rendered as the id and is reported here by '
                            'name, because inventing one is worse.',
            'primary': {'source': 'weekly_rosters',
                        'blob': roster_chosen.get('blob'),
                        'basis': roster_chosen.get('basis'),
                        'columns_present':
                            roster_chosen.get('name_columns_present'),
                        'name_column_absent':
                            roster_chosen.get('name_column_absent'),
                        'n_named': roster_chosen.get('n_named')},
            'fallback': name_fallback,
            'n_rows': len(players),
            'n_resolved': sum(1 for r in players if r['name']),
            'n_unresolved': sum(1 for r in players if not r['name']),
            'unresolved': sorted(r['gsis_id'] for r in players
                                 if not r['name'])},
        'players': players,
        'n_players': len(players),
        'confidence_board': CONF.board(players),
        'layer_governance': layer_governance(directory),
        'threshold_disclaimer': TH.DISCLAIMER,
        'unavailable_metrics': [dict(v, metric=f'{k[0]}/{k[1]}')
                                for k, v in sorted(M.UNSUPPORTED.items())],
    }


def _name_fallback(players, as_of, refusals) -> dict:
    """Name the rows the board's own roster blob could not, or say why not.

    CONSULTED ONLY WHEN SOMETHING IS MISSING. `nfl/capture/registry.py:185`
    reduces weekly_rosters to (season, week, team, gsis_id, position), so a
    board that selects the reduced vintage gets no name from it at all and
    needs a second lawful source. A board that selects the raw vintage already
    has every name and must not open twelve more files to confirm it.

    THE UNRESOLVED CASE IS A RETURN VALUE, NOT A BLANK. A board that prints an
    empty cell where a name belongs has made the same claim as one that prints
    a wrong name: that it looked, and this is the answer. Every id no lawful
    capture names is listed by id, on the row and on the board.
    """
    missing = [r for r in players if not r['name']]
    base = {'module': 'nfl.product.names',
            'n_rows_needing_it': len(missing)}
    if not missing:
        return {**base, 'consulted': False,
                'why': 'the roster vintage this board selected named every '
                       'row; no second source was opened'}
    if as_of is None:
        return {**base, 'consulted': False,
                'why': 'the board has no resolved cut, so no capture may be '
                       'selected for a name either'}
    try:
        resolved, consulted = NM.resolve(as_of.isoformat())
    except Exception as e:                                   # noqa: BLE001
        refusals.append({'input': 'player_names',
                         'code': 'NAME_FALLBACK_UNREADABLE',
                         'detail': f'{type(e).__name__}: {e}'[:300]})
        return {**base, 'consulted': False,
                'why': f'NAME_FALLBACK_UNREADABLE: {type(e).__name__}'}
    n_filled = 0
    for r in missing:
        hit = resolved.get(r['gsis_id']) or {}
        nm = (hit.get('name') or '').strip()
        if not nm:
            r['name_provenance'] = {
                'source': None, 'code': 'NAME_UNRESOLVED_AT_CUT',
                'detail': f'no capture lawful at {as_of.isoformat()} carries '
                          f'a name for {r["gsis_id"]}. The row renders the '
                          f'gsis_id. This is a real state and is not repaired '
                          f'by guessing.'}
            continue
        n_filled += 1
        r['name'] = nm
        r['name_provenance'] = {'source': hit.get('source'),
                                'blob': hit.get('blob'),
                                'column': hit.get('column'),
                                'observed_at': hit.get('observed_at'),
                                'basis': 'NAME_FALLBACK_LAWFUL_CAPTURE',
                                'selected_for': 'the selected roster blob '
                                                'named no one for this id'}
    return {**base, 'consulted': True, 'n_filled': n_filled,
            'n_available': len(resolved),
            'captures': [{'source': c['source'], 'blob': c['blob'],
                          'observed_at': c['observed_at'],
                          'n_named': c['n_named']} for c in consulted],
            'precedence': 'newest lawful capture wins; ties broken by blob '
                          'path, never by glob order'}


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
