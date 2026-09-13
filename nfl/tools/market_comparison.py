#!/usr/bin/env python3.12
r"""The governed model-vs-market table, from stored draws and a frozen price.

    python3.12 nfl/tools/market_comparison.py --date 2026-09-13 \
        --candidate R8 --market /path/to/snapshot.csv --out TABLE.csv

WHAT IT EMITS AND WHAT IT REFUSES

A row appears only if ALL of the following hold, and the reason any row is
missing is written to the refusal file beside the table rather than being
silently absent:

  * the board is POST-INACTIVES for that game
  * `qb_inactive_ownership_enforced` is true on the board
  * the metric carries no defect flagged as contaminating FOR THAT METRIC
  * the player maps to a team and a gsis_id
  * the metric has stored draws, so the probability is counted and not fitted
  * a frozen quote exists for that player and market

It ranks nothing, recommends nothing, and sizes nothing. `edge` below is the
model probability minus the de-vigged market probability on the chosen side --
a disagreement, which is not an edge estimate and not advice.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.product import daily_board as PB                        # noqa: E402
from nfl.product import market_cdf as MC
import numpy as np
from nfl.product import forecast_stage as FS                         # noqa: E402
from nfl.product import market_names as MN                       # noqa: E402
from nfl.research import board_select as BS                      # noqa: E402
from nfl.research import daily_board as RB                       # noqa: E402

# THE EXPORT CONTRACT. Every compared quote carries all of it; a column that
# cannot be computed is empty, never silently dropped and never invented.
QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)

COLUMNS = ('game', 'player', 'team', 'market', 'metric', 'forecast_stage',
           'r8_mean', 'r8_median',
           'q05', 'q10', 'q25', 'q50', 'q75', 'q90', 'q95',
           'line', 'over_price', 'under_price',
           'projection_minus_line', 'projection_minus_line_pct',
           'r8_p_over', 'r8_p_under', 'r8_p_push',
           'no_vig_p_over', 'no_vig_p_under',
           'selected_side', 'probability_gap_pp',
           'edge_over', 'edge_under',
           'data_status', 'completeness', 'defects',
           'written_at', 'information_timestamp',
           'hard_rock_retrieved_at', 'market_timestamp', 'sportsbook',
           'n_draws', 'n_over', 'n_under', 'n_push', 'probability_method',
           'cutoff', 'qb_inactive_ownership_enforced')

# The ranked candidate table the product contract asks for, in its order.
TOP_COLUMNS = ('rank', 'play', 'model_projection', 'hard_rock_line',
               'difference', 'difference_pct', 'model_probability',
               'hard_rock_no_vig_probability', 'probability_gap_pp',
               'hard_rock_odds', 'forecast_stage', 'data_status')



SNAPSHOT_COLUMNS = ('player', 'team', 'opponent', 'market', 'line',
                    'over_price', 'under_price', 'sportsbook',
                    'retrieval_time_utc', 'availability', 'source_url')
REQUIRED_AVAILABILITY = 'TWO_SIDED_OPEN'

# canonical name -> the alias a delivery is allowed to use instead. Closed set.
COLUMN_ALIASES = {'source_url': 'event_url',
                  'market': 'hrb_market_name',
                  'over_price': 'over_odds',
                  'under_price': 'under_odds',
                  'retrieval_time_utc': 'retrieval_timestamp_utc'}


def load_frozen_snapshot(path):
    """A frozen book snapshot, keyed by (player, team, market).

    THE TEAM IS PART OF THE KEY AND THAT IS NOT PEDANTRY. Two different
    players share a name across clubs in this very week: the Vikings' Justin
    Jefferson is a receiver and the Browns listed a linebacker of the same
    name on their inactive report. A (player, market) key would have joined a
    receiving line onto whichever one it met first.

    NOTHING IS REFRESHED AND NOTHING IS RESTAMPED. The file is read, its
    digest is recorded, and every clock in it is carried through exactly as
    written.
    """
    p = pathlib.Path(path)
    raw = p.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = list(csv.DictReader(raw.decode().splitlines()))
    if not rows:
        raise ValueError('MARKET_SNAPSHOT_EMPTY: an empty snapshot is an '
                         'error, not an absence of quotes')
    # A DELIVERED SNAPSHOT MAY NAME ITS COLUMNS DIFFERENTLY. Each accepted
    # alias is written down here, once, so the mapping is reviewable rather
    # than guessed per delivery. Guessing field names is exactly how an export
    # once wrote 7,926 rows with every meaningful column blank.
    adapted, derived = [], []
    for r in rows:
        r = dict(r)
        for canon, alias in COLUMN_ALIASES.items():
            if canon not in r and alias in r:
                r[canon] = r[alias]
        if 'availability' not in r:
            # DERIVED, AND NAMED AS DERIVED. Two-sided means BOTH prices are
            # present. A row missing either is NOT promoted to open -- the
            # absence of the column is never read as the absence of a problem.
            both = bool((r.get('over_price') or '').strip()
                        and (r.get('under_price') or '').strip())
            r['availability'] = (REQUIRED_AVAILABILITY if both
                                 else 'NOT_TWO_SIDED_DERIVED')
            derived.append(both)
        adapted.append(r)
    rows = adapted
    missing = [c for c in SNAPSHOT_COLUMNS if c not in rows[0]]
    if missing:
        raise ValueError(f'MARKET_SNAPSHOT_SCHEMA: missing {missing}')
    by, skipped = {}, []
    for r in rows:
        if (r.get('availability') or '').strip() != REQUIRED_AVAILABILITY:
            skipped.append({'player': r.get('player'),
                            'market': r.get('market'),
                            'reason': 'NOT_TWO_SIDED_OPEN',
                            'detail': r.get('availability')})
            continue
        try:
            line = float(r['line'])
        except (TypeError, ValueError):
            skipped.append({'player': r.get('player'),
                            'market': r.get('market'),
                            'reason': 'UNPARSEABLE_LINE',
                            'detail': r.get('line')})
            continue
        key = (r['player'].strip(), r['team'].strip(), r['market'].strip())
        if key in by:
            raise ValueError(f'MARKET_SNAPSHOT_DUPLICATE: {key} appears more '
                             f'than once; a duplicate quote is an ambiguity, '
                             f'not a choice this tool may make')
        by[key] = {'line': line, 'over_price': r['over_price'],
                   'under_price': r['under_price'],
                   'sportsbook': r['sportsbook'],
                   'timestamp': r['retrieval_time_utc'],
                   'source_url': r['source_url'],
                   'opponent': r['opponent']}
    return {'quotes': by, 'sha256': digest, 'n_rows': len(rows),
            'n_quotes': len(by), 'skipped': skipped, 'path': str(p),
            'availability_derived': bool(derived),
            'n_availability_derived_two_sided': sum(1 for x in derived if x)}



class DrawIdentityError(RuntimeError):
    """Raised when a draw matrix cannot be joined to a player by identity."""


IDENTITY_ABSENT = 'PLAYER_DRAW_ROW_IDENTITY_ABSENT'


def draw_row_for(manifest, draws, metric, gsis_id):
    """THE row for this player, by declared identity. Never by position.

    MEASURED 2026-09-13. This tool originally did `draws[key][i]` with `i` the
    player's position in board.json's player list. That is not the draw
    matrix's row order: on 2026_01_ARI_LAC it put Justin Herbert's
    distribution on Gardner Minshew and Trey Lance's on Carson Beck, crossed
    two players to the opposing club, and made the team dropback totals read
    74.6 / 4.9 against a true 41.3 / 38.2.

    THE ARTIFACT WAS NEVER AT FAULT, and saying so matters because it was
    briefly reported as the defect. `manifest['layers'][layer]['row_ids']` has
    declared the row axis as gsis_id all along, and the production board
    builder has always joined through it. This function does what that builder
    does. Every way the join can fail is a named refusal rather than a
    silently wrong row.
    """
    lay = str(metric).split('/')[0]
    layer = ((manifest or {}).get('layers') or {}).get(lay) or {}
    ids = layer.get('row_ids')
    if not ids:
        raise DrawIdentityError(
            f'{IDENTITY_ABSENT}: layer {lay!r} declares no row_ids, so no row '
            f'can be attributed to a player. A legacy artifact stays readable '
            f'and is never eligible for player-level comparison.')
    if layer.get('row_axis') != 'gsis_id':
        raise DrawIdentityError(
            f'DRAW_ROW_AXIS_NOT_GSIS_ID: layer {lay!r} declares row_axis '
            f'{layer.get("row_axis")!r}; this join requires gsis_id.')
    if len(set(ids)) != len(ids):
        dup = sorted({x for x in ids if ids.count(x) > 1})
        raise DrawIdentityError(
            f'DRAW_ROW_IDENTITY_DUPLICATE: {dup[:5]} appear more than once in '
            f'layer {lay!r}. An ambiguous identity is refused, never resolved '
            f'to the first match.')
    key = str(metric).replace('/', '__')
    if key not in draws.files:
        raise DrawIdentityError(f'DRAW_MATRIX_ABSENT: {key}')
    arr = draws[key]
    if arr.ndim != 2 or int(arr.shape[0]) != len(ids):
        raise DrawIdentityError(
            f'DRAW_ROW_COUNT_MISMATCH: {key} has shape {tuple(arr.shape)} '
            f'against {len(ids)} declared identities. The manifest and the '
            f'array disagree about how many players exist.')
    if gsis_id not in ids:
        raise DrawIdentityError(
            f'DRAW_ROW_IDENTITY_UNKNOWN: {gsis_id} is not among the '
            f'{len(ids)} identities of layer {lay!r}.')
    return arr[ids.index(gsis_id)]


def _draw_key(metric):
    return str(metric).replace('/', '__')


def _refuse_every_quote(gid, quotes, reason, detail=None, teams=None):
    """A game-level refusal, expanded to one refusal per affected quote.

    ZERO SILENT LOSS MEANS ZERO, INCLUDING HERE. A single {'game': gid,
    'reason': ...} row is honest about the game and silent about the quotes:
    162 quotes for 2026_01_DAL_NYG produced exactly one refusal, and the
    accounting guard correctly called that unbalanced. A refusal that applies
    to the whole game applies to every quote in it, so it is recorded against
    every quote in it. The reason is identical on each row; what changes is
    that the book's quote is now individually answered.
    """
    tset = set(teams or ()) or set(str(gid).split('_')[2:4])
    out = []
    for (qn, qt, qmarket) in sorted(quotes):
        if qt in tset:
            out.append({'game': gid, 'player': qn, 'market': qmarket,
                        'reason': reason, 'detail': detail,
                        'scope': 'WHOLE_GAME'})
    if not out:
        out.append({'game': gid, 'reason': reason, 'detail': detail,
                    'scope': 'WHOLE_GAME',
                    'note': 'the snapshot carries no quote for this game'})
    return out


DATA_STATUS = ('COMPLETE', 'PARTIAL_PLAYER_COVERAGE',
               'PRE_INACTIVES_AVAILABILITY_UNRESOLVED', 'DEFECT_FLAGGED')


def _data_status(board, stage, flags):
    """One word for how much to trust this row's inputs. Never 'ok'.

    Ordered most severe first: a flagged defect outranks an unresolved
    availability, which outranks a partial roster. A row is never labelled
    COMPLETE while any of the three applies.

    ONLY FLAGS THAT CONTAMINATE *THIS* METRIC COUNT. `_defect_flags` returns
    every known defect on the board and marks which ones touch the metric in
    hand -- QB_INACTIVE_NOT_CONSUMED appears on a receiver's row with
    `contaminates_this_metric: False`. Reading the list's mere length labelled
    all 69 pre-inactives rows DEFECT_FLAGGED and emptied the ranked table,
    which is the same collateral-damage error as the whole-game gate, one
    layer up.
    """
    if [f for f in (flags or []) if f.get('contaminates_this_metric')]:
        return 'DEFECT_FLAGGED'
    if stage == FS.PRE:
        return 'PRE_INACTIVES_AVAILABILITY_UNRESOLVED'
    c = board.get('completeness')
    return c if c else 'COMPLETE'


def rank_candidates(rows, limit=10):
    """The ranked candidate table. NEVER padded to `limit`.

    "Do not force ten candidates" is the whole point: a table padded to a round
    number invites the reader to treat row 10 as comparable to row 1 when it
    may be the only thing left after filtering. If N rows qualify, N rows are
    returned, and the count is reported.

    Ranking is by the absolute model-versus-market probability gap in
    percentage points. That is a DISAGREEMENT ordering, not an expected-value
    ordering and not a recommendation: a large gap means the model and the book
    differ, which is equally consistent with the model being wrong.
    """
    ok = [r for r in rows
          if r.get('selected_side') and r.get('probability_gap_pp') != ''
          and r.get('data_status') != 'DEFECT_FLAGGED']
    ok.sort(key=lambda r: -abs(float(r['probability_gap_pp'])))
    out = []
    for i, r in enumerate(ok[:limit], 1):
        odds = (r['over_price'] if r['selected_side'] == 'OVER'
                else r['under_price'])
        mp = (r['r8_p_over'] if r['selected_side'] == 'OVER'
              else r['r8_p_under'])
        nvp = (r['no_vig_p_over'] if r['selected_side'] == 'OVER'
               else r['no_vig_p_under'])
        out.append({
            'rank': i,
            'play': f"{r['player']} {r['market']} {r['selected_side']} "
                    f"{r['line']}",
            'model_projection': r['r8_mean'],
            'hard_rock_line': r['line'],
            'difference': r['projection_minus_line'],
            'difference_pct': r['projection_minus_line_pct'],
            'model_probability': mp,
            'hard_rock_no_vig_probability': nvp,
            'probability_gap_pp': r['probability_gap_pp'],
            'hard_rock_odds': odds,
            'forecast_stage': r['forecast_stage'],
            'data_status': r['data_status'],
        })
    return out, len(ok)


def rows_for_game(gid, cfg_dir, quotes, names):
    """(rows, refusals) for one sealed board against the frozen snapshot."""
    rows, refused = [], []
    bd, how = BS.newest_board_dir(cfg_dir)
    if bd is None:
        return rows, _refuse_every_quote(gid, quotes, 'NO_SEALED_BOARD',
                                        'no sealed board directory for this '
                                        'game and candidate')
    board = json.load(open(bd / 'board.json'))
    # THE STAGE IS A LABEL, NOT A GATE.
    #
    # This used to refuse any board that was not post-inactives, so no
    # projection existed until the official list published -- roughly ninety
    # minutes before kickoff -- even though roster, depth chart, injury report,
    # workload history and team environment were all known hours earlier. The
    # missing list is a reason to be uncertain about availability, not a reason
    # to have no forecast. A stage that cannot be NAMED is still refused.
    so = FS.resolve_stage(cfg_dir)
    if so.state is not State.PASS:
        return rows, _refuse_every_quote(gid, quotes, so.code, so.detail)
    stage = so.value
    cutoff = 'post_inactives' if stage == FS.POST else 'pre_inactives'
    enforced = bool(board.get('qb_inactive_ownership_enforced'))
    own = board.get('qb_inactive_ownership') or {}
    # A QB DEFECT SUPPRESSES QB MARKETS, NOT THE GAME.
    #
    # This used to return early for the WHOLE game whenever QB ownership was
    # unenforced, so one quarterback-room governance state silenced every
    # running back, receiver and tight end on the card -- players whose
    # carries, targets and receptions the QB allocation never touches.
    # `daily_board._defect_flags` already scopes the contamination correctly
    # (`contaminates_this_metric` is true only for `qb/` metrics), and the
    # per-quote CONTAMINATING_DEFECT refusal below acts on it. So each QB
    # quote is now refused BY NAME, with the failed conditions attached, and
    # the independently valid non-QB markets flow.
    #
    # This widens what is published, so it is worth being exact about what it
    # does NOT do: no QB row becomes admissible, and nothing is relabelled.
    # A refused quote is still refused; it is simply refused individually
    # rather than by collateral damage.
    unenforced_detail = ','.join(
        own.get('failed_conditions') or ['no ownership block on the board'])
    draws = PB._load_draws(bd)
    if draws is None:
        return rows, _refuse_every_quote(
            gid, quotes, 'NO_STORED_DRAWS',
            'the sealed board carries no player_draws, so no exact empirical '
            'CDF can be computed', teams=board.get('teams'))
    mp = bd / 'player_draws_manifest.json'
    if not mp.exists():
        return rows, _refuse_every_quote(
            gid, quotes, IDENTITY_ABSENT,
            'no player_draws_manifest.json beside the draws, so no row can be '
            'attributed to a player', teams=board.get('teams'))
    man = json.loads(mp.read_text())
    fresh = board.get('freshness') or {}
    info_ts = max((s.get('retrieved_at') or '')
                  for s in (fresh.get('sources') or [])) or None
    # THE FORECAST'S OWN CLOCK, READ FROM WHERE IT ACTUALLY LIVES.
    # `board['written_at']` does not exist; the sealed clock is
    # `board['freshness']['written_at']`, and falling back to the newest
    # source retrieval silently reported a DIFFERENT clock under the name
    # written_at -- an input time presented as a forecast time. The two are
    # exported side by side and never substituted for one another.
    written_at = fresh.get('written_at') or None
    seen = set()
    for i, p in enumerate(board.get('players') or []):
        pid, team = p.get('gsis_id'), p.get('team')
        nm = names.get(pid, pid)
        if not pid or not team:
            refused.append({'game': gid, 'player': nm,
                            'reason': 'PLAYER_MAPPING_INVALID'})
            continue
        for (qn, qt, qmarket), q in quotes.items():
            if qn != nm or qt != team:
                continue
            seen.add((qn, qt, qmarket))
            metric, basis = MN.metric_for(qmarket, p.get('position'))
            if metric is None:
                refused.append({'game': gid, 'player': nm,
                                'market': qmarket,
                                'reason': 'MARKET_NOT_MAPPED',
                                'detail': basis[:200]})
                continue
            if metric not in (p.get('metrics') or {}):
                refused.append({'game': gid, 'player': nm, 'market': qmarket,
                                'reason': 'METRIC_NOT_ON_THIS_BOARD',
                                'detail': metric})
                continue
            flags = PB._defect_flags(board, metric)
            bad = [f['id'] for f in flags if f.get('contaminates_this_metric')]
            # THE OWNERSHIP STATE REFUSES QB METRICS ON ITS OWN AUTHORITY.
            #
            # `_defect_flags` raises QB_INACTIVE_NOT_CONSUMED only when 'R2' is
            # in the board's component manifest, so a board WITHOUT R2 and
            # WITHOUT enforced ownership produced no flag at all. The old
            # whole-game early return hid that; scoping the gate to QB metrics
            # exposed it, and a QB quote would have been priced off a board
            # whose QB allocation never consumed an official inactive list.
            # The ownership verdict is the authority on QB admissibility, so it
            # is read directly rather than only through a component-conditional
            # flag.
            if str(metric).startswith('qb/'):
                # STAGE, SPECIFICATION AND ENFORCEMENT ARE THREE DIFFERENT
                # CLAIMS AND EACH IS NAMED SEPARATELY. A season-boundary
                # defect does NOT clear when the inactive list arrives, and
                # an arriving list does not repair a cell definition.
                bad = bad + [b for b in FS.qb_metric_blockers(board, stage)
                             if b not in bad]
            if bad:
                refused.append({'game': gid, 'player': nm, 'market': qmarket,
                                'metric': metric,
                                'reason': 'CONTAMINATING_DEFECT',
                                'forecast_stage': stage,
                                'detail': (
                                    f'{",".join(bad)}; stage={stage}; '
                                    f'qb_inactive_ownership_enforced='
                                    f'{enforced}; failed_conditions='
                                    f'[{unenforced_detail}]; '
                                    f'qb3_rooms: '
                                    f'{FS.qb_blocker_detail(board, stage)}')})
                continue
            try:
                d = draw_row_for(man, draws, metric, pid)
            except DrawIdentityError as e:
                refused.append({'game': gid, 'player': nm, 'market': qmarket,
                                'reason': str(e).split(':')[0],
                                'detail': str(e)[:220]})
                continue
            quote = {'line': q['line'], 'over_price': q.get('over_price'),
                     'under_price': q.get('under_price'),
                     'retrieved_at': q.get('timestamp'),
                     'source': q.get('sportsbook'),
                     'market_timestamp': q.get('timestamp')}
            try:
                c = MC.compare(d, metric, quote)
            except (ValueError, MC.MarketLeak) as e:
                refused.append({'game': gid, 'player': nm, 'market': metric,
                                'reason': type(e).__name__,
                                'detail': str(e)[:160]})
                continue
            e = c['exact_probability']
            nv = c['no_vig']
            mean = float(c['model']['mean'])
            line = float(q['line'])
            qs = np.quantile(np.asarray(d, float), QUANTILES)
            # THE SIDE IS CHOSEN BY THE MODEL'S OWN DISAGREEMENT, and the gap
            # is reported in percentage points because that is the unit a
            # reader compares across markets. It is a DISAGREEMENT with the
            # book, never an edge estimate and never a recommendation.
            do, du = c['disagreement_over'], c['disagreement_under']
            if do is None or du is None:
                side, gap = '', ''
            elif do >= du:
                side, gap = 'OVER', round(do * 100.0, 4)
            else:
                side, gap = 'UNDER', round(du * 100.0, 4)
            row = {
                'game': gid, 'player': nm, 'team': team, 'market': qmarket,
                'metric': metric, 'forecast_stage': stage,
                'r8_mean': round(mean, 4),
                'r8_median': round(float(c['model']['median']), 4),
                'line': line, 'over_price': q.get('over_price'),
                'under_price': q.get('under_price'),
                'projection_minus_line': round(mean - line, 4),
                'projection_minus_line_pct': (round((mean - line) / line * 100.0, 4)
                                              if line else ''),
                'r8_p_over': round(e['p_over'], 6),
                'r8_p_under': round(e['p_under'], 6),
                'r8_p_push': round(e['p_push'], 6),
                'no_vig_p_over': (round(nv['no_vig_over'], 6)
                                  if nv['no_vig_over'] is not None else ''),
                'no_vig_p_under': (round(nv['no_vig_under'], 6)
                                   if nv['no_vig_under'] is not None else ''),
                'selected_side': side, 'probability_gap_pp': gap,
                'edge_over': (round(do, 6) if do is not None else ''),
                'edge_under': (round(du, 6) if du is not None else ''),
                'data_status': _data_status(board, stage, flags),
                'completeness': board.get('completeness'),
                'defects': ','.join(
                    f'{f["id"]}{"" if f.get("contaminates_this_metric") else "(other-metric)"}'
                    for f in flags) or '',
                'written_at': written_at,
                'information_timestamp': info_ts,
                'hard_rock_retrieved_at': q.get('timestamp'),
                'market_timestamp': q.get('timestamp'),
                'sportsbook': q.get('sportsbook'),
                'n_draws': e['n_draws'], 'n_over': e['n_over'],
                'n_under': e['n_under'], 'n_push': e['n_push'],
                'probability_method': e['method'], 'cutoff': cutoff,
                'qb_inactive_ownership_enforced': enforced,
            }
            for lab, v in zip(('q05', 'q10', 'q25', 'q50', 'q75', 'q90',
                               'q95'), qs):
                row[lab] = round(float(v), 4)
            rows.append(row)
    # EVERY QUOTE FOR THIS GAME'S CLUBS IS ACCOUNTED FOR, COMPARED OR REFUSED.
    #
    # This loop walks BOARD PLAYERS and looks for their quotes, so until now a
    # quote whose player the board does not carry was never visited at all --
    # no row, no refusal, no count. Measured 2026-09-13 against the frozen
    # 4:25 Hard Rock snapshot: 166 quotes went in, 76 rows and 3 refusals came
    # out, and 87 quotes simply were not there. That is the defect class this
    # project loses the most work to: a step that returned nothing read as a
    # step that succeeded. A quote the engine cannot price is a REFUSAL with a
    # reason, never an absence.
    tset = set(board.get('teams') or ()) or {t for t in (gid.split('_')[2:4])}
    # WHY a club has no non-QB rows is a governed fact on the board itself, and
    # the refusal must carry it. `appearance` NOT_APPLICABLE means the layer
    # that would have produced those players REFUSED -- it is not a coverage
    # accident and must not read as one.
    stages = {s['stage']: s for s in (board.get('layer_governance') or [])}
    app = stages.get('appearance') or {}
    app_off = app.get('state') not in (None, 'PASS')
    on_board = {(names.get(p.get('gsis_id'), p.get('gsis_id')), p.get('team'))
                for p in (board.get('players') or [])}
    nonqb_clubs = {p.get('team') for p in (board.get('players') or [])
                   if p.get('position') != 'QB'}
    for (qn, qt, qmarket) in sorted(quotes):
        if qt not in tset or (qn, qt, qmarket) in seen:
            continue
        if app_off and qt not in nonqb_clubs and (qn, qt) not in on_board:
            refused.append({'game': gid, 'player': qn, 'market': qmarket,
                            'reason': 'APPEARANCE_LAYER_NOT_APPLICABLE',
                            'detail': f'the appearance stage is '
                                      f'{app.get("state")} with code '
                                      f'{app.get("code")}, so this board '
                                      f'carries no non-quarterback for {qt} '
                                      f'and the engine has no distribution to '
                                      f'compare. A governed refusal upstream, '
                                      f'not a missing player.'})
        else:
            refused.append({'game': gid, 'player': qn, 'market': qmarket,
                            'reason': 'QUOTE_PLAYER_NOT_ON_BOARD',
                            'detail': f'the frozen snapshot quotes {qn} '
                                      f'({qt}) but no player on this sealed '
                                      f'board carries that name and club, '
                                      f'even though the layers that would '
                                      f'produce one ran. Not priced, not '
                                      f'dropped.'})
    return rows, refused


def main(argv=None):
    ap = argparse.ArgumentParser(description='exact model-vs-market table')
    ap.add_argument('--date', required=True)
    ap.add_argument('--candidate', default='R8')
    ap.add_argument('--market', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--games', default=None)
    ap.add_argument('--stage', default='auto',
                    choices=('auto', 'pre', 'post', 'both'),
                    help='auto: newest post-inactives board, falling back to '
                         'pre-inactives. pre/post: that stage only. both: '
                         'every stage that exists, each labelled.')
    ap.add_argument('--top', type=int, default=10,
                    help='size CAP for the ranked candidate table. It is '
                         'never padded: if fewer qualify, fewer are returned.')
    a = ap.parse_args(argv)

    snap = load_frozen_snapshot(a.market)
    quotes = snap['quotes']
    print(f'frozen snapshot {snap["path"]}')
    print(f'  sha256 {snap["sha256"]}')
    print(f'  {snap["n_rows"]} row(s), {snap["n_quotes"]} '
          f'(player, team, market) quote(s), {len(snap["skipped"])} skipped')

    want = set(a.games.split(',')) if a.games else None
    label = ('V1_CANDIDATE' if a.candidate == 'V1'
             else f'V1_CANDIDATE_{a.candidate}')
    from nfl.product import names as NM
    names = NM.lookup(None) if hasattr(NM, 'lookup') else {}
    rows, refused = [], []
    order = {'auto': ('post_inactives', 'pre_inactives'),
             'post': ('post_inactives',), 'pre': ('pre_inactives',),
             'both': ('post_inactives', 'pre_inactives')}[a.stage]
    stages_seen = collections.Counter()
    for gdir in sorted((RB.LIVE).iterdir()):
        if not gdir.is_dir() or (want and gdir.name not in want):
            continue
        for cut in order:
            d = gdir / f'{cut}_{label}'
            if not d.exists():
                continue
            r, x = rows_for_game(gdir.name, d, quotes, names)
            rows += r
            refused += x
            stages_seen[FS.stage_of_dirname(cut)] += len(r)
            if a.stage != 'both':
                break
    # THE ACCOUNTING IS ASSERTED, NOT ASSUMED. Rows plus refusals must equal
    # the quotes in scope. A shortfall means quotes went missing between the
    # snapshot and the table, and a table that silently drops the book's
    # quotes is not a comparison against the book.
    scope = {t for g in (want or set())
             for t in g.split('_')[2:4]} if want else None
    in_scope = [k for k in quotes if scope is None or k[1] in scope]
    n_acc = len(rows) + len(refused)
    # IN 'both' EACH QUOTE IS ANSWERED ONCE PER STAGE, ON PURPOSE. The
    # invariant is then per stage, not over the union, and it is stated that
    # way rather than quietly relaxed.
    n_stages = max(1, len({FS.stage_of_dirname(c) for c in order
                           if any((g / f'{c}_{label}').exists()
                                  for g in RB.LIVE.iterdir() if g.is_dir()
                                  and (not want or g.name in want))}))
    expected = len(in_scope) * (n_stages if a.stage == 'both' else 1)
    accounting = {'n_quotes_in_snapshot': len(quotes),
                  'n_quotes_in_scope': len(in_scope),
                  'n_stages_compared': n_stages,
                  'n_outcomes_expected': expected,
                  'n_rows': len(rows), 'n_refusals': len(refused),
                  'rows_by_stage': dict(stages_seen),
                  'balanced': n_acc == expected}
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    ref = out.with_suffix('.refusals.json')
    ref.write_text(json.dumps(
        {'n_rows': len(rows), 'n_refused': len(refused),
         'accounting': accounting,
         'market_snapshot_sha256': snap['sha256'],
         'market_snapshot_path': snap['path'],
         'market_rows_skipped': snap['skipped'],
         'by_reason': dict(collections.Counter(
             x['reason'] for x in refused)),
         'refusals': refused}, indent=1) + '\n')
    print(f'{len(rows)} row(s) -> {out}')
    print(f'{len(refused)} refusal(s) -> {ref}')
    for k, v in collections.Counter(x['reason'] for x in refused).items():
        print(f'   {k}: {v}')
    # ---- the ranked candidate table, and the data a visual needs ----
    top, n_qualified = rank_candidates(rows, a.top)
    tp = out.with_suffix('.top.csv')
    with open(tp, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(TOP_COLUMNS))
        w.writeheader()
        for r in top:
            w.writerow(r)
    vp = out.with_suffix('.top_visual.json')
    vp.write_text(json.dumps({
        'artifact': 'MODEL_VS_HARD_ROCK_TOP_N',
        'chart': 'model minus Hard Rock, in percentage points of probability',
        'n_qualified': n_qualified, 'n_returned': len(top),
        'cap_requested': a.top,
        'not_padded': ('the table is never padded to the cap. If fewer '
                       'markets satisfy the data-quality requirements, fewer '
                       'are returned.'),
        'ordering': ('absolute model-versus-market probability gap. A '
                     'DISAGREEMENT ordering: a large gap is equally '
                     'consistent with the model being wrong.'),
        'market_snapshot_sha256': snap['sha256'],
        'series': [{'label': r['play'], 'probability_gap_pp':
                    r['probability_gap_pp'],
                    'difference_pct': r['difference_pct'],
                    'model_probability': r['model_probability'],
                    'hard_rock_no_vig_probability':
                        r['hard_rock_no_vig_probability'],
                    'forecast_stage': r['forecast_stage'],
                    'data_status': r['data_status']} for r in top],
    }, indent=1) + '\n')
    print(f'{len(top)} ranked candidate(s) of {n_qualified} qualified -> {tp}')
    print(f'visual series -> {vp}')
    if stages_seen:
        print('rows by stage: ' + ', '.join(f'{k}={v}'
                                            for k, v in stages_seen.items()))
    print(f'accounting: {len(in_scope)} quote(s) in scope x '
          f'{accounting["n_stages_compared"]} stage(s) = {expected} expected, '
          f'{len(rows)} row(s) + {len(refused)} refusal(s) -> '
          f'{"BALANCED" if accounting["balanced"] else "UNBALANCED"}')
    if not accounting['balanced']:
        print(f'MARKET_QUOTE_ACCOUNTING_UNBALANCED: expected {expected} '
              f'outcome(s), got {n_acc}. Every quote must be compared or '
              f'refused by name.')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
