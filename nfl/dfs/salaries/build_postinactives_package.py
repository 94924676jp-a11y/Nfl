"""Assemble the POST-INACTIVES package from finished candidate runs.

WHAT THIS IS

A reader over `player_draws.npz`. It computes nothing the football model did
not already emit, and every number it reports is a statistic of a draw vector
it opened. No projection is stored anywhere else and none is invented here.

THE THREE THINGS IT REFUSES TO DO

1. It will not call a position SUPPORTED on team totals. `team_volume` carries
   `team_targets`; that says how many targets a club throws and nothing about
   who catches them. Support requires a per-player row.
2. It will not let an officially inactive player reach a playable row. The
   audit is a GATE returning FAIL, not a column, and it checks the EMITTED
   rows rather than trusting that the fixture excluded them.
3. It will not evaluate a prop by fitting a distribution. `market/evaluate`
   counts P(over), P(under) and P(push) from the draws, and a market with no
   declared mapping is UNSUPPORTED rather than approximated.

DFS AND PROPS READ THE SAME ARRAYS. That is not a claim, it is the structure:
both adapters are handed the same npz path and the same `row_ids`, and
`assert_shared_draws` re-checks that every DK-scored player is a player the
football layers emitted.
"""
from __future__ import annotations

import collections
import glob
import json
import pathlib
import sys

import numpy as np
from nfl.production.contracts import registry as _reg

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'postinactives-package-1'
PCTS = (5, 10, 25, 50, 75, 80, 90, 95)

#: Per-player football layers. `team_volume`, `rush_category` and
#: `rush_player_pool` are team-axis and are NOT player support.
PLAYER_LAYERS = ('qb', 'receiving', 'rushing', 'rushing_total', 'kicking',
                 'gadget_rush')


def summarise(v) -> dict:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {'n_draws': 0}
    q = np.percentile(v, PCTS)
    return {'mean': round(float(v.mean()), 4),
            'median': round(float(np.median(v)), 4),
            'sd': round(float(v.std(ddof=1)) if v.size > 1 else 0.0, 4),
            **{f'p{p}': round(float(x), 4) for p, x in zip(PCTS, q)},
            'p_zero': round(float((v == 0).mean()), 4),
            'max': round(float(v.max()), 4),
            'n_draws': int(v.size)}


def read_run(run_dir, review_dir=None) -> dict:
    """GATED. This is a publication path -- the package it builds is what a
    card is written from -- so the draws come through the player-review gate
    rather than straight off disk. `review_dir` defaults beside the run so an
    existing caller keeps working; a missing review REFUSES, it does not fall
    back to an ungated read."""
    run_dir = pathlib.Path(run_dir)
    from nfl.production.review import gated_projection as _GP
    _rd = pathlib.Path(review_dir) if review_dir else (
        _REPO / 'nfl/research/player_review' /
        json.loads((run_dir / 'player_draws_manifest.json').read_text()
                   ).get('game_id', ''))
    _g = _GP.load(run_dir, _rd)
    if _g.state.name != 'PASS':
        raise SystemExit(f'{_g.code}: {_g.detail}')
    m = _g.value['manifest']
    s = json.loads((run_dir / 'run_status.json').read_text())
    z = _g.value['arrays']
    n = int(m.get('n_draws') or 0)

    stats = collections.defaultdict(dict)      # pid -> 'layer/metric' -> vec
    for lname, layer in sorted((m.get('layers') or {}).items()):
        if layer.get('row_axis') != 'gsis_id':
            continue
        ids = layer.get('row_ids') or []
        for metric in (layer.get('metrics') or []):
            arr = None
            for k in (f'{lname}__{metric}', f'{lname}/{metric}'):
                if k in z:
                    arr = np.asarray(z[k])
                    break
            if arr is None:
                continue
            for i, pid in enumerate(ids):
                if i < arr.shape[0]:
                    v = np.asarray(arr[i], float)
                    if v.size == n and np.isfinite(v).all():
                        stats[pid][f'{lname}/{metric}'] = v
    return {'run_dir': str(run_dir), 'run_id': s.get('run_id'),
            'game_id': m.get('game_id'), 'status': s.get('status'),
            'n_draws': n, 'written_at': s.get('written_at'),
            'execution_identity': s.get('execution_identity'),
            'code_commit': s.get('code_commit'),
            'content_digest': (s.get('draw_artifact') or {}).get(
                'content_digest'),
            'first_failure': (s.get('first_failure') or {}).get('stage'),
            'layers': sorted((m.get('layers') or {})),
            'manifest': m, 'npz_path': str(run_dir / 'player_draws.npz'),
            'stats': stats}


def assert_no_inactive_in_playable(runs, inactive_by_club, roster) -> dict:
    """THE GATE. Checks EMITTED rows, not the fixture's intent."""
    survivors = []
    checked = 0
    for r in runs:
        emitted = set(r['stats'])
        parts = (r['game_id'] or '').split('_')
        clubs = (parts[2], parts[3]) if len(parts) >= 4 else ()
        ids = {i for c in clubs for i in inactive_by_club.get(c, [])}
        checked += len(ids)
        for pid in sorted(emitted & ids):
            survivors.append({'game_id': r['game_id'], 'gsis_id': pid,
                              'name': roster.get(pid, {}).get('full_name')})
    if not inactive_by_club:
        # AN EMPTY LIST AND A VERIFIED-EMPTY LIST ARE DIFFERENT FACTS. With no
        # official declarations ingested, `survivors` is empty because nothing
        # was compared, not because the board was found clean. Returning PASS
        # here would certify an unchecked board -- exactly the collapse this
        # module's docstring forbids. The 1pm slate never reached this branch
        # because it had real evidence; a slate whose inactives have not been
        # published yet reaches it on every call.
        return {'state': 'NOT_CERTIFIED',
                'code': 'NO_OFFICIAL_INACTIVE_EVIDENCE',
                'n_inactive_ids_checked': 0,
                'n_emitted_player_rows': sum(len(r['stats']) for r in runs),
                'survivors': [],
                'method': 'no official inactive declarations were supplied '
                          'for this slate, so no intersection was computed. '
                          'The board is NOT certified inactive-clean.'}
    return {'state': 'FAIL' if survivors else 'PASS',
            'code': ('OFFICIALLY_INACTIVE_PLAYER_IN_PLAYABLE_BOARD'
                     if survivors
                     else '0_OFFICIALLY_INACTIVE_PLAYERS_IN_PLAYABLE_BOARD'),
            'n_inactive_ids_checked': checked,
            'n_emitted_player_rows': sum(len(r['stats']) for r in runs),
            'survivors': survivors,
            'method': 'intersection of officially-declared ids with the '
                      'gsis_id row_ids the runs actually emitted'}


def assert_shared_draws(runs) -> dict:
    """DK-scored players must be players the football layers emitted."""
    bad = []
    for r in runs:
        L = r['manifest'].get('layers') or {}
        # EVERY DK-BEARING LAYER, DISCOVERED. Reading `dk_scoring` alone made
        # this check blind to exactly the rows most worth checking: a kicker's
        # DK row lives in `kicking`, so it was never tested against the
        # football layers at all. The assertion passed because the rows it
        # should have examined were not in the set it examined.
        dk = set()
        for _dl in _reg.dk_bearing_layers(r['manifest']):
            dk |= set((L.get(_dl) or {}).get('row_ids') or [])
        foot = set()
        for ln in PLAYER_LAYERS:
            foot |= set((L.get(ln) or {}).get('row_ids') or [])
        extra = sorted(dk - foot)
        if extra:
            bad.append({'game_id': r['game_id'], 'dk_only_rows': extra})
    return {'state': 'FAIL' if bad else 'PASS',
            'code': ('DK_ROWS_NOT_BACKED_BY_FOOTBALL_DRAWS' if bad
                     else 'DFS_AND_PROP_OUTPUTS_SHARE_IDENTICAL_FOOTBALL_DRAWS'),
            'offenders': bad,
            'method': 'one npz per game feeds both adapters; every dk_scoring '
                      'row_id must appear in a per-player football layer'}


# ======================================================================= DFS
def dfs_rows(runs, roster, dk_salary=None) -> list:
    """DK distribution per player, read from `dk_scoring/dk_points`.

    DK SALARY IS NEVER READ HERE. It is attached downstream for the portfolio
    layer and has no path into any number on this board.
    """
    out = []
    for r in runs:
        for pid, met in sorted(r['stats'].items()):
            # ANY LAYER'S dk_points, NOT dk_scoring's ALONE.
            #
            # THIS LINE DROPPED EVERY KICKER FROM THE BOARD. A kicker's
            # distribution arrives as 'kicking/dk_points', so `met.get` returned
            # None and the `continue` skipped him -- silently, with no row, no
            # warning, and a board that simply had no kickers on it.
            _k = next((k for k in sorted(met) if k.endswith('/dk_points')), None)
            v = met.get(_k) if _k else None
            if v is None:
                continue
            info = roster.get(pid, {})
            s = summarise(v)
            out.append({
                'game_id': r['game_id'], 'run_id': r['run_id'],
                'gsis_id': pid, 'player': info.get('full_name'),
                'team': info.get('team'), 'position': info.get('position'),
                'opponent': _opp(r['game_id'], info.get('team')),
                'status': 'ACTIVE',
                'dk': s,
                'p_ge_10': round(float((np.asarray(v) >= 10).mean()), 4),
                'p_ge_15': round(float((np.asarray(v) >= 15).mean()), 4),
                'p_ge_20': round(float((np.asarray(v) >= 20).mean()), 4),
                'p_ge_30': round(float((np.asarray(v) >= 30).mean()), 4),
                'draw_reference': {'npz': r['npz_path'],
                                   'key': 'dk_scoring__dk_points',
                                   'content_digest': r['content_digest']},
            })
    return out


def _opp(game_id, team):
    p = (game_id or '').split('_')
    if len(p) < 4 or not team:
        return None
    return p[3] if team == p[2] else (p[2] if team == p[3] else None)


def football_rows(runs, roster) -> list:
    """Every per-player football statistic the run emitted, summarised."""
    out = []
    for r in runs:
        for pid, met in sorted(r['stats'].items()):
            foot = {k: summarise(v) for k, v in sorted(met.items())
                    if not k.startswith('dk_scoring/')}
            if not foot:
                continue
            info = roster.get(pid, {})
            out.append({
                'game_id': r['game_id'], 'run_id': r['run_id'],
                'gsis_id': pid, 'player': info.get('full_name'),
                'team': info.get('team'), 'position': info.get('position'),
                'opponent': _opp(r['game_id'], info.get('team')),
                'status': 'ACTIVE',
                'n_draws': r['n_draws'],
                'stats': foot,
                'support': 'PER_PLAYER_SIMULATION_DRAWS',
                'draw_reference': {'npz': r['npz_path'],
                                   'content_digest': r['content_digest']},
            })
    return out


def position_support(runs, roster) -> dict:
    """Per position, per game: is there a PER-PLAYER distribution?"""
    out = {}
    for r in runs:
        counts = collections.Counter()
        for pid, met in r['stats'].items():
            if any(not k.startswith('dk_scoring/') for k in met):
                counts[(roster.get(pid, {}).get('position') or '?')] += 1
        out[r['game_id']] = {
            'QB': counts.get('QB', 0), 'RB': counts.get('RB', 0),
            'WR': counts.get('WR', 0), 'TE': counts.get('TE', 0),
            'K': counts.get('K', 0),
            'DST': 0,
            'dst_note': 'DST_UNSUPPORTED: the engine emits no team-defence '
                        'outputs at all, and points allowed has no scoreboard '
                        'to read.',
            'other_positions': {k: v for k, v in counts.items()
                                if k not in ('QB', 'RB', 'WR', 'TE', 'K')},
        }
    return out


# ===================================================================== PROPS
def prop_rows(runs, roster, market_csv, inactive_ids, delta_csv=None,
              model_cut=None) -> dict:
    """Exact empirical probability at the exact sportsbook line.

    P(over), P(under) and P(push) are COUNTED from the same draws that scored
    DK. Nothing is fitted. A market with no declared mapping is UNSUPPORTED by
    name; an approximation would be worse than a refusal.

    TWO CLOCKS TRAVEL WITH EVERY ROW. A model that learned something after the
    price was captured is not comparable to it without saying so, and the
    alignment label is computed rather than assumed.
    """
    import csv as _csv

    import numpy as _np

    from nfl.market import evaluate as EV
    from nfl.market import odds as OD

    by_pid = {}
    for r in runs:
        for pid, met in r['stats'].items():
            by_pid.setdefault(pid, (r, met))

    name_idx = collections.defaultdict(list)
    for pid, info in roster.items():
        for k in ('full_name', 'football_name'):
            v = (info.get(k) or '').strip()
            if v:
                name_idx[(_norm(v), info.get('team'))].append(pid)

    # MARKET MOVEMENT, 04:52Z -> 16:35Z, so a reader can separate model
    # disagreement from a book that has already absorbed the news. Keyed on
    # (game, market, displayed selection) because a LINE can move and the row
    # is still the same market.
    moved = {}
    if delta_csv:
        with open(delta_csv, newline='') as fh:
            for d in _csv.DictReader(fh):
                k = (d['game'], d['market'], d['displayed_selection'])
                # THE COLUMN IS `delta_status`, NOT `change`. The first
                # version of this reader asked for 'change', got None on every
                # row, and still produced a movement block -- a field that is
                # present and always empty reads as "nothing moved" when in
                # fact nothing was read. Named explicitly so it cannot recur.
                moved[k] = {
                    'delta_status': d.get('delta_status'),
                    'line_0452Z': d.get('line_0452Z'),
                    'line_1635Z': d.get('line_1635Z'),
                    'over_0452Z': d.get('over_0452Z'),
                    'over_1635Z': d.get('over_1635Z'),
                    'under_0452Z': d.get('under_0452Z'),
                    'under_1635Z': d.get('under_1635Z'),
                    'selection_price_0452Z': d.get('selection_price_0452Z'),
                    'selection_price_1635Z': d.get('selection_price_1635Z'),
                }

    rows, counts = [], collections.Counter()
    with open(market_csv, newline='') as fh:
        for m in _csv.DictReader(fh):
            if m.get('market_class') != 'player_prop' \
                    or m.get('is_main_line') != 'True':
                continue
            mk, team = m['market'], m['team']
            hits = name_idx.get((_norm(m['player']), team)) or []
            pid = hits[0] if len(hits) == 1 else None
            base = {'game': m['game'], 'player': m['player'], 'gsis_id': pid,
                    'team': team, 'opponent': m['opponent'],
                    'position': m['position'], 'market': mk,
                    'line': m['line'], 'over_price': m['over_price'],
                    'under_price': m['under_price'],
                    'sportsbook': m['book'],
                    'market_snapshot_time': m['retrieved_at_utc'],
                    'book_line_timestamp_utc': m['book_line_timestamp_utc'],
                    'model_information_cut': model_cut,
                    'time_alignment': _align(model_cut,
                                             m['retrieved_at_utc']),
                    'market_status': m['market_status'],
                    'market_movement': moved.get(
                        (m['game'], mk, m['displayed_selection']))}
            if pid is None:
                base.update(support='IDENTITY_UNRESOLVED',
                            why=f'{len(hits)} roster rows answer to this '
                                f'displayed name on {team}')
                counts['IDENTITY_UNRESOLVED'] += 1
                rows.append(base)
                continue
            if pid in inactive_ids:
                base.update(support='PLAYER_INACTIVE',
                            flag='MARKET_FOR_INACTIVE_PLAYER',
                            why='officially declared inactive; the book still '
                                'lists this market')
                counts['PLAYER_INACTIVE'] += 1
                rows.append(base)
                continue
            if mk in EV.UNSUPPORTED_MARKETS:
                base.update(support='UNSUPPORTED',
                            why=EV.UNSUPPORTED_MARKETS[mk])
                counts['UNSUPPORTED'] += 1
                rows.append(base)
                continue
            r, met = by_pid.get(pid, (None, None))
            if met is None:
                base.update(support='UNSUPPORTED',
                            why='no simulated draws for this player')
                counts['UNSUPPORTED'] += 1
                rows.append(base)
                continue
            spec = EV.MARKET_MAP.get(mk)
            if spec is None:
                base.update(support='UNSUPPORTED',
                            why=f'{mk!r} has no declared mapping')
                counts['UNSUPPORTED'] += 1
                rows.append(base)
                continue
            if 'sum' in spec:
                parts = [met.get(f'{l}/{me}') for l, me in spec['sum']]
                if any(p is None for p in parts):
                    base.update(support='UNSUPPORTED',
                                why='a component layer is absent for this '
                                    'player')
                    counts['UNSUPPORTED'] += 1
                    rows.append(base)
                    continue
                x = _np.sum(parts, axis=0)
                src = '+'.join(f'{l}/{me}' for l, me in spec['sum'])
            else:
                x = met.get(f"{spec['layer']}/{spec['metric']}")
                src = f"{spec['layer']}/{spec['metric']}"
                if x is None:
                    base.update(support='UNSUPPORTED',
                                why=f'{src} absent for this player')
                    counts['UNSUPPORTED'] += 1
                    rows.append(base)
                    continue
            ev = EV.evaluate_line(x, float(m['line']))
            dv = OD.devig(m['over_price'] or None, m['under_price'] or None)
            base.update(
                support='EXACT_SIMULATION_SUPPORTED', draw_source=src,
                model_mean=round(ev['mean'], 4),
                model_median=round(ev['median'], 4),
                model_sd=round(ev['sd'], 4) if ev.get('sd') else None,
                model_p25=round(ev['p25'], 4), model_p75=round(ev['p75'], 4),
                model_p95=round(ev['p95'], 4),
                model_p_over=round(ev['p_over'], 6),
                model_p_under=round(ev['p_under'], 6),
                model_p_push=round(ev['p_push'], 6),
                mcse_over=round(ev['mcse_over'], 6),
                n_draws=ev['n_draws'],
                method=ev['method'],
                # odds.devig returns novig_p_over / novig_p_under /
                # devig_status. Reading 'p_over'/'p_under'/'code' here
                # returned None on EVERY row while the market was in fact
                # two-sided, which reads as 'the book gave no price' when the
                # truth was 'the key was guessed'. Names taken from the
                # module, not from memory.
                novig_p_over=(round(dv['novig_p_over'], 6)
                              if dv.get('novig_p_over') is not None else None),
                novig_p_under=(round(dv['novig_p_under'], 6)
                               if dv.get('novig_p_under') is not None
                               else None),
                book_hold=(round(dv['hold'], 6)
                           if dv.get('hold') is not None else None),
                devig_code=dv.get('devig_status'),
                devig_method=dv.get('devig_method'))
            if dv.get('novig_p_over') is not None:
                base['edge_over'] = round(
                    ev['p_over'] - dv['novig_p_over'], 6)
                base['edge_under'] = round(
                    ev['p_under'] - dv['novig_p_under'], 6)
                base['ev_over_per_unit'] = OD.ev_per_unit(
                    ev['p_over'], ev['p_push'], m['over_price'])
                base['ev_under_per_unit'] = OD.ev_per_unit(
                    ev['p_under'], ev['p_push'], m['under_price'])
            counts['EXACT_SIMULATION_SUPPORTED'] += 1
            rows.append(base)
    return {'rows': rows, 'counts': dict(counts)}


def _norm(s):
    from nfl.dfs.salaries import dk_universe as DK
    return DK._norm_name(s)


#: The inactive declarations published ~15:30Z. A model cut and a market
#: capture BOTH after that instant carry the same inactive information, which
#: is what makes them comparable at all.
INACTIVES_PUBLISHED_UTC = '2026-09-20T15:30:00Z'


def _align(model_cut, market_retrieved):
    """Two clocks, compared -- never assumed equal.

    TIME_ALIGNED_POST_INACTIVES means both sides are after the inactive
    publication, so neither is missing that news. It does NOT mean the clocks
    are identical, and where the book is later the gap is stated in seconds
    rather than waved away: anything the market learned in that window is
    information the model does not have.
    """
    import datetime as _d

    def _p(t):
        if not t:
            return None
        return _d.datetime.fromisoformat(t.replace('Z', '+00:00'))
    mc, mr, ia = _p(model_cut), _p(market_retrieved), _p(
        INACTIVES_PUBLISHED_UTC)
    if mc is None or mr is None:
        return 'UNKNOWN_ALIGNMENT'
    both_post = mc >= ia and mr >= ia
    gap = int((mr - mc).total_seconds())
    if both_post:
        return {'label': 'TIME_ALIGNED_POST_INACTIVES',
                'model_cut': model_cut, 'market_retrieved': market_retrieved,
                'market_minus_model_seconds': gap,
                'note': ('both sides postdate the ~15:30Z inactive '
                         'publication, so both carry the inactive '
                         'information. The book was captured '
                         f'{gap} seconds after the model cut; anything it '
                         'absorbed in that window is NOT in the model.')
                if gap > 0 else
                ('both sides postdate the inactive publication and the model '
                 'cut is at or after the market capture.')}
    if mc >= ia > mr:
        return {'label': 'MODEL_NEWER_THAN_MARKET',
                'note': 'the market capture predates the inactive '
                        'publication; the book had not repriced.'}
    return {'label': 'UNKNOWN_ALIGNMENT'}
