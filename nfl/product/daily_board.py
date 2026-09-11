"""A read-only daily decision feed over the sealed, governed forecasts.

    python3.12 -m nfl.product.daily_board --date 2026-09-11

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT.

It is a CONSUMER. It reads sealed boards and a frozen market snapshot and
emits one standardised slate-wide artifact, so a full Sunday is one command
instead of interrogating each game by hand. It never runs a forecast, never
writes into a sealed board, and never lets a price touch the football model.

It is NOT a betting strategy, a bankroll layer, or an edge engine. The column
that compares us to a book is named `model_minus_market_probability` and is
labelled MODEL-MARKET DISAGREEMENT, NOT PROVEN EV in the artifact itself,
because a disagreement is a hypothesis about the book and nothing more. No
tiers are assigned here: the primitives a ranking would need are exposed and
the ranking is left to the decision layer.

THE ONE-WAY RULE. Prices enter this module and stop. Nothing computed from a
line, a price or a market probability is written back into a forecast, a
prior, or any file under nfl/production. The direction is enforced by the
fact that this module is downstream of everything and imports no writer.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import io
import json
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (Cause, Outcome,      # noqa: E402
                                                State)
from nfl.product import store as ST                                 # noqa: E402

SPEC_VERSION = 'daily-board-1'

DISAGREEMENT_LABEL = 'MODEL-MARKET DISAGREEMENT, NOT PROVEN EV'

# Market names in the snapshot -> the metric key on a board.
MARKET_TO_METRIC = {
    'Passing yards': 'qb/pyds',
    'Pass attempts': 'qb/att',
    'Carries': 'rushing/carries',
    'Receptions': 'receiving/receptions',
    'Receiving yards': 'receiving/receiving_yards',
}

# CORRELATION GROUPS. Stafford under attempts and Stafford under passing yards
# are one bet on one game script wearing two hats, and a decision layer that
# counted them as two independent signals would double-count its own
# confidence. Grouping is by (player, driver): everything a quarterback's
# dropback volume drives is one group, everything a receiver's target volume
# drives is another.
_DRIVER = {
    'qb/att': 'qb_volume', 'qb/db': 'qb_volume', 'qb/cmp': 'qb_volume',
    'qb/pyds': 'qb_volume', 'qb/ptd': 'qb_efficiency', 'qb/int': 'qb_efficiency',
    'receiving/targets': 'target_volume',
    'receiving/receptions': 'target_volume',
    'receiving/receiving_yards': 'target_volume',
    'receiving/receiving_td': 'receiving_efficiency',
    'rushing/carries': 'carry_volume',
    'rushing/rushing_td': 'rushing_efficiency',
}


def correlation_group(player_id: str, metric: str) -> str:
    """Signals that move together carry one group id."""
    return f'{player_id}:{_DRIVER.get(metric, "other")}'


# --------------------------------------------------------------- market
def american_to_prob(odds):
    """Implied probability of an American price, before the vig is removed."""
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if o == 0:
        return None
    return 100.0 / (o + 100.0) if o > 0 else (-o) / ((-o) + 100.0)


def devig(p_over, p_under):
    """Proportional de-vig. Returns (fair_over, fair_under, hold) or Nones.

    BOTH SIDES OR NOTHING. A one-sided quote cannot be de-vigged: the hold is
    unobservable, and halving a guessed margin would invent the number this
    column exists to measure. One-sided rows keep a raw implied probability
    and are marked as not de-vigged rather than quietly treated as fair.
    """
    if p_over is None or p_under is None:
        return None, None, None
    s = p_over + p_under
    if s <= 0:
        return None, None, None
    return p_over / s, p_under / s, s - 1.0


def load_market(path):
    """The frozen pregame snapshot, as {(player, market): [quote, ...]}."""
    p = pathlib.Path(path)
    if not p.exists():
        return Outcome.blocked(
            'MARKET_SNAPSHOT_ABSENT',
            f'no market snapshot at {p}. The board is still produced; every '
            f'row simply carries no market columns and is not rankable.',
            cause=Cause.DATA, path=str(p))
    rows = list(csv.DictReader(open(p)))
    if not rows:
        return Outcome.fail('MARKET_SNAPSHOT_EMPTY',
                            f'{p} parsed to zero rows; an empty snapshot is '
                            f'an error, not an absence of quotes')
    by = collections.defaultdict(list)
    for r in rows:
        if (r.get('availability') or '').strip() not in ('returned', ''):
            continue
        try:
            line = float(r['line'])
        except (KeyError, TypeError, ValueError):
            continue
        by[(r.get('player'), r.get('market'))].append({
            'line': line,
            'over_price': r.get('over_price'), 'under_price': r.get('under_price'),
            'sportsbook': r.get('sportsbook'),
            'timestamp': r.get('retrieval_time_utc'),
            'snapshot': r.get('snapshot')})
    return Outcome.ok('MARKET_SNAPSHOT_READ', value=dict(by),
                      n_rows=len(rows), n_keys=len(by), path=str(p))


def consensus_quote(quotes):
    """One quote per (player, market): the median line, latest snapshot.

    The median is used rather than any single book because a daily feed should
    not inherit one book's idiosyncrasy, and because this project's comparator
    is the market rather than a counterparty. The book whose line equals the
    median is named so the row stays traceable to a real quote.
    """
    if not quotes:
        return None
    latest = max((q.get('snapshot') or '') for q in quotes)
    pool = [q for q in quotes if (q.get('snapshot') or '') == latest] or quotes
    lines = sorted(q['line'] for q in pool)
    med = lines[len(lines) // 2] if len(lines) % 2 else (
        (lines[len(lines) // 2 - 1] + lines[len(lines) // 2]) / 2.0)
    exact = [q for q in pool if q['line'] == med]
    pick = dict(exact[0]) if exact else dict(pool[0])
    pick['line'] = med
    pick['n_books'] = len(pool)
    pick['book_is_exact_match'] = bool(exact)
    return pick


# --------------------------------------------------------------- boards
def _load_draws(board_dir: pathlib.Path):
    """The stored draws for a sealed board, plain or gzipped."""
    f = list(board_dir.glob('**/player_draws.npz'))
    if f:
        return np.load(f[0], allow_pickle=True)
    g = list(board_dir.glob('**/player_draws.npz.gz'))
    if g:
        return np.load(io.BytesIO(gzip.open(g[0], 'rb').read()),
                       allow_pickle=True)
    return None


def _board_files(board_dir: pathlib.Path):
    b = list(board_dir.glob('**/board.json'))
    m = list(board_dir.glob('**/player_draws_manifest.json'))
    if not b:
        return None, None, None
    return (json.load(open(b[0])),
            json.load(open(m[0])) if m else None,
            _load_draws(board_dir))


def games_on(date_str: str, index_rows):
    """{game_id: [index rows]} for every game kicking off on `date`.

    The date is matched against KICKOFF, not against when a board was written.
    A Sunday slate is the games played that day; a board written on Saturday
    for a Sunday game belongs to Sunday.
    """
    out = collections.defaultdict(list)
    for r in index_rows:
        ko = str(r.get('kickoff_utc') or '')
        if ko[:10] == date_str:
            out[r['game_id']].append(r)
    return dict(out)


def latest_lawful(rows):
    """The newest board whose written_at is strictly before kickoff.

    A board written after kickoff is not a pregame forecast, whatever it
    contains, so it may not lead a decision feed. It is not deleted or hidden
    -- it simply cannot be the one this feed reads.
    """
    lawful = [r for r in rows
              if str(r.get('written_at') or '') < str(r.get('kickoff_utc') or '')]
    if not lawful:
        return None, 'NO_LAWFUL_BOARD: every sealed board for this game was ' \
                     'written at or after kickoff'
    return max(lawful, key=lambda r: str(r.get('written_at'))), None


# ----------------------------------------------------------- eligibility
def eligibility(row) -> tuple:
    """(RANKING_ELIGIBLE, [named reasons]). Ineligible rows stay VISIBLE.

    Hiding an ineligible row would make the feed look cleaner and make the
    slate look better covered than it is. Every row is emitted; the ones that
    cannot be ranked say why, by name, so a reader can tell a missing quote
    from a contaminated metric from a player who is not dressed.
    """
    why = []
    if not row.get('forecast_predates_kickoff'):
        why.append('FORECAST_NOT_BEFORE_KICKOFF')
    if row.get('market_line') is None:
        why.append('MARKET_QUOTE_ABSENT')
    elif not row.get('market_predates_kickoff'):
        why.append('MARKET_QUOTE_NOT_BEFORE_KICKOFF')
    if row.get('metric_status') not in ('MODELED', 'PROVISIONAL'):
        why.append(f"LAYER_INCOMPLETE:{row.get('metric_status')}")
    if row.get('official_inactive'):
        why.append('PLAYER_OFFICIALLY_INACTIVE')
    if row.get('identity_unresolved'):
        why.append('IDENTITY_UNRESOLVED')
    for flag in (row.get('known_defect_flags') or []):
        if flag.get('contaminates_this_metric'):
            why.append(f"KNOWN_DEFECT:{flag.get('id')}")
    if not row.get('has_distribution'):
        why.append('NO_DISTRIBUTION_ONLY_A_POINT_MEAN')
    return (not why), why


def _defect_flags(board, metric):
    """Known defects at forecast time, and whether each touches THIS metric.

    A defect that contaminates passing volume does not contaminate a running
    back's carries, and marking every row with every defect would make the
    flag meaningless. The QB-inactive defect is recorded against the board's
    own component list: boards sealed before the repair carry it.
    """
    out = []
    comps = set((board.get('component_manifest') or {}).get('applied') or [])
    if 'R2' in comps and not board.get('qb_inactive_ownership_enforced'):
        out.append({
            'id': 'QB_INACTIVE_NOT_CONSUMED',
            'detail': 'this board was sealed before official_inactive_ids '
                      'reached the QB allocation, so an officially inactive '
                      'quarterback may hold dropback share',
            'contaminates_this_metric': metric.startswith('qb/')})
    return out


# ------------------------------------------------------------- row build
def build_rows(game_id, idx_row, board, manifest, draws, market,
               names, teams, inactive_ids):
    """One row per modelled player/metric on one game."""
    rows = []
    ko = str(idx_row.get('kickoff_utc') or '')
    wa = str(idx_row.get('written_at') or '')
    fresh = board.get('freshness') or {}
    latest_info = max((s.get('retrieved_at') or '')
                      for s in (fresh.get('sources') or [])) or None
    post_inactives = bool(inactive_ids)
    for p in board.get('players') or []:
        pid = p.get('gsis_id')
        nm = names.get(pid, pid)
        team = teams.get(pid)
        for metric, m in (p.get('metrics') or {}).items():
            vec = _vector(draws, manifest, metric, pid)
            row = {
                'game_id': game_id, 'team': team, 'player': nm,
                'player_id': pid, 'metric': metric,
                'model_mean': m.get('mean'),
                'p10': m.get('p10'), 'p25': m.get('p25'), 'p50': m.get('p50'),
                'p75': m.get('p75'), 'p90': m.get('p90'),
                'model_sd': (round(float(np.std(vec, ddof=1)), 4)
                             if vec is not None and vec.size > 1 else None),
                'metric_status': m.get('status'),
                'forecast_written_at': wa,
                'kickoff_utc': ko,
                'latest_information_timestamp': latest_info,
                'source_freshness': fresh.get('oldest_input_hours_before_kickoff'),
                'POST_INACTIVES_COMPLETE': post_inactives,
                'official_inactive': pid in (inactive_ids or set()),
                'identity_unresolved': pid is None,
                'candidate_version': board.get('model_configuration'),
                'run_id': idx_row.get('run_id'),
                'promoted': bool(idx_row.get('promoted')),
                'has_distribution': vec is not None and vec.size > 0,
                'forecast_predates_kickoff': bool(wa and ko and wa < ko),
                'correlation_group': correlation_group(pid, metric),
                'known_defect_flags': _defect_flags(board, metric),
            }
            _attach_market(row, market, nm, metric, vec, ko)
            ok, why = eligibility(row)
            row['RANKING_ELIGIBLE'] = ok
            row['ranking_ineligible_reasons'] = why
            rows.append(row)
    return rows


def _vector(draws, manifest, metric, pid):
    if draws is None or manifest is None or pid is None:
        return None
    lay = metric.split('/')[0]
    ids = ((manifest.get('layers') or {}).get(lay) or {}).get('row_ids') or []
    if pid not in ids:
        return None
    key = metric.replace('/', '__')
    if key not in draws:
        return None
    i = ids.index(pid)
    arr = draws[key]
    # THE MANIFEST AND THE ARRAY MUST AGREE, AND WHEN THEY DO NOT, SAY SO.
    # Indexing blind raised IndexError from inside the reader -- an unnamed
    # failure. A disagreement here means the manifest describes a different
    # draw set from the one on disk, so no vector is returned and the row
    # becomes NO_DISTRIBUTION_ONLY_A_POINT_MEAN: visible, not silent.
    if i >= arr.shape[0]:
        return None
    return np.asarray(arr[i], float)


def _attach_market(row, market, player, metric, vec, kickoff):
    """Join the frozen quote and compute the DISAGREEMENT, never an edge."""
    row.update({'market_line': None, 'over_price': None, 'under_price': None,
                'sportsbook': None, 'market_timestamp': None,
                'market_predates_kickoff': None,
                'model_probability_over_market_line': None,
                'model_probability_under_market_line': None,
                'market_probability_over_no_vig': None,
                'market_probability_under_no_vig': None,
                'market_hold': None, 'no_vig_available': False,
                'model_minus_market_probability': None,
                'model_minus_market_label': DISAGREEMENT_LABEL,
                'abs_probability_disagreement': None,
                'line_minus_mean_native_units': None,
                'line_minus_mean_in_model_sds': None,
                'line_percentile_in_model_distribution': None})
    mk = next((k for k, v in MARKET_TO_METRIC.items() if v == metric), None)
    if mk is None or not market:
        return
    q = consensus_quote(market.get((player, mk)) or [])
    if q is None:
        return
    row.update({'market_line': q['line'], 'over_price': q.get('over_price'),
                'under_price': q.get('under_price'),
                'sportsbook': q.get('sportsbook'),
                'market_timestamp': q.get('timestamp'),
                'n_books_at_quote': q.get('n_books')})
    ts = str(q.get('timestamp') or '')
    row['market_predates_kickoff'] = bool(ts and kickoff and ts < kickoff)
    if vec is None or vec.size == 0:
        return
    # P(over the EXACT line) straight from the stored draws. Nothing smoothed,
    # nothing fitted, nothing interpolated.
    p_over = float((vec > q['line']).mean())
    row['model_probability_over_market_line'] = round(p_over, 4)
    row['model_probability_under_market_line'] = round(1.0 - p_over, 4)
    mean = float(vec.mean())
    sd = float(np.std(vec, ddof=1)) if vec.size > 1 else 0.0
    row['line_minus_mean_native_units'] = round(q['line'] - mean, 4)
    row['line_minus_mean_in_model_sds'] = (round((q['line'] - mean) / sd, 4)
                                           if sd > 0 else None)
    row['line_percentile_in_model_distribution'] = round(
        float((vec < q['line']).mean() + 0.5 * (vec == q['line']).mean()), 4)
    fo, fu, hold = devig(american_to_prob(q.get('over_price')),
                         american_to_prob(q.get('under_price')))
    if fo is None:
        return
    row.update({'market_probability_over_no_vig': round(fo, 4),
                'market_probability_under_no_vig': round(fu, 4),
                'market_hold': round(hold, 4), 'no_vig_available': True,
                'model_minus_market_probability': round(p_over - fo, 4),
                'abs_probability_disagreement': round(abs(p_over - fo), 4)})


# --------------------------------------------------------- game summary
def game_summary(game_id, idx_row, board, manifest, draws, names, teams,
                 inactive_ids):
    """Team environment and ownership for one game, distributions and all."""
    def dist(metric, rid):
        v = _vector(draws, manifest, metric, rid)
        if v is None or v.size == 0:
            return None
        return {'mean': round(float(v.mean()), 3),
                'p10': round(float(np.percentile(v, 10)), 2),
                'p50': round(float(np.percentile(v, 50)), 2),
                'p90': round(float(np.percentile(v, 90)), 2),
                'sd': round(float(np.std(v, ddof=1)), 3) if v.size > 1 else None}

    out = {'artifact': 'NFL_GAME_SUMMARY', 'spec_version': SPEC_VERSION,
           'game_id': game_id, 'kickoff_utc': idx_row.get('kickoff_utc'),
           'forecast_written_at': idx_row.get('written_at'),
           'run_id': idx_row.get('run_id'), 'promoted': bool(idx_row.get('promoted')),
           'candidate_version': board.get('model_configuration'),
           'components_applied': (board.get('component_manifest') or {}).get('applied'),
           'POST_INACTIVES_COMPLETE': bool(inactive_ids),
           'n_official_inactive': len(inactive_ids or ()),
           'team_environment': {}, 'qb_ownership': {},
           'player_opportunity': {}}
    tv = (manifest.get('layers') or {}).get('team_volume') or {}
    for t in (tv.get('row_ids') or []):
        out['team_environment'][t] = {
            'plays': dist('team_volume/team_off_snaps', t),
            'carries': dist('team_volume/team_carries', t),
            'dropbacks': dist('team_volume/team_dropbacks_part', t),
            'targets': dist('team_volume/team_targets', t),
            'rz_carries': dist('team_volume/team_rz_carries', t)}
    # QB OWNERSHIP, with the inactive check stated rather than assumed.
    qb_ids = ((manifest.get('layers') or {}).get('qb') or {}).get('row_ids') or []
    for pid in qb_ids:
        d = dist('qb/db', pid)
        if d is None:
            continue
        out['qb_ownership'][names.get(pid, pid)] = {
            'team': teams.get(pid), 'dropbacks': d,
            'attempts': dist('qb/att', pid),
            'official_inactive': pid in (inactive_ids or set())}
    inact_owning = {n: v for n, v in out['qb_ownership'].items()
                    if v['official_inactive']
                    and (v['dropbacks'] or {}).get('mean', 0) > 0}
    out['inactive_quarterbacks_still_owning_dropbacks'] = inact_owning
    out['qb_inactive_ownership_clean'] = not inact_owning
    for pid in set(qb_ids) | set(
            ((manifest.get('layers') or {}).get('rushing') or {}).get('row_ids') or []) | set(
            ((manifest.get('layers') or {}).get('receiving') or {}).get('row_ids') or []):
        opp = {k: dist(m, pid) for k, m in
               (('carries', 'rushing/carries'),
                ('targets', 'receiving/targets'),
                ('receptions', 'receiving/receptions'))}
        opp = {k: v for k, v in opp.items() if v}
        if opp:
            out['player_opportunity'][names.get(pid, pid)] = {
                'team': teams.get(pid),
                'official_inactive': pid in (inactive_ids or set()), **opp}
    return out


# ---------------------------------------------------------------- names
def roster_names():
    """gsis_id -> (name, team) from the raw roster captures."""
    names, teams = {}, {}
    import glob as _g
    for f in sorted(_g.glob(str(_REPO / 'nfl_vintage' / 'raw'
                                / 'weekly_rosters.*.csv'))):
        for r in csv.DictReader(open(f)):
            pid = r.get('gsis_id')
            if pid:
                names[pid] = r.get('full_name') or r.get('football_name') or pid
                teams[pid] = r.get('team')
    return names, teams


def official_inactive_ids(game_id):
    """The resolved official inactive set for a game, or an empty set."""
    p = (_REPO / 'nfl' / 'research' / 'live' / game_id
         / 'INACTIVES_INGESTION.json')
    if not p.exists():
        return set()
    rec = json.loads(p.read_text())
    for s in rec.get('steps') or []:
        ib = s.get('inactive_by_team')
        if isinstance(ib, dict):
            return {pid for v in ib.values() for pid in v}
    return set()


# ----------------------------------------------------------------- CSV
_CSV_COLS = [
    'game_id', 'team', 'player', 'metric', 'model_mean',
    'p10', 'p25', 'p50', 'p75', 'p90',
    'model_probability_over_market_line', 'model_probability_under_market_line',
    'market_line', 'over_price', 'under_price', 'sportsbook',
    'market_timestamp', 'forecast_written_at', 'latest_information_timestamp',
    'source_freshness', 'POST_INACTIVES_COMPLETE', 'known_defect_flags',
    'candidate_version', 'run_id', 'promoted',
    'RANKING_ELIGIBLE', 'ranking_ineligible_reasons', 'correlation_group',
    'model_minus_market_probability', 'abs_probability_disagreement',
    'line_minus_mean_native_units', 'line_minus_mean_in_model_sds',
    'line_percentile_in_model_distribution', 'model_sd',
    'market_probability_over_no_vig', 'market_hold', 'no_vig_available',
]


def _flat(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, sort_keys=True) if v else ''
    return '' if v is None else v


def write_csv(path, rows, cols):
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([_flat(r.get(c)) for c in cols])


_MARKET_COLS = [
    'game_id', 'team', 'player', 'metric', 'market_line', 'sportsbook',
    'over_price', 'under_price', 'market_probability_over_no_vig',
    'market_probability_under_no_vig', 'market_hold', 'no_vig_available',
    'model_probability_over_market_line', 'model_minus_market_probability',
    'model_minus_market_label', 'abs_probability_disagreement',
    'line_minus_mean_native_units', 'line_minus_mean_in_model_sds',
    'line_percentile_in_model_distribution', 'model_mean', 'model_sd',
    'correlation_group', 'RANKING_ELIGIBLE', 'ranking_ineligible_reasons',
    'market_timestamp', 'forecast_written_at',
]


# ----------------------------------------------------------------- main
def build(date_str, market_path=None, out_dir=None):
    """Everything for one slate date. Read-only; nothing is forecast here."""
    out = pathlib.Path(out_dir or (_REPO / 'nfl' / 'product' / 'daily'
                                   / date_str))
    out.mkdir(parents=True, exist_ok=True)
    idx = ST.read_index()
    by_game = games_on(date_str, idx)
    mk = load_market(market_path) if market_path else Outcome.blocked(
        'MARKET_SNAPSHOT_NOT_SUPPLIED',
        'no --market was given, so no row carries a quote and none is '
        'rankable. The board is still emitted.', cause=Cause.DATA)
    market = mk.value if mk.state is State.PASS else {}
    names, teams = roster_names()

    rows, summaries, skipped = [], {}, {}
    for gid, grows in sorted(by_game.items()):
        pick, why = latest_lawful(grows)
        if pick is None:
            skipped[gid] = why
            continue
        bdir = _REPO / pick['board_dir'] if not os.path.isabs(
            str(pick['board_dir'])) else pathlib.Path(pick['board_dir'])
        board, manifest, draws = _board_files(bdir)
        if board is None:
            skipped[gid] = f'BOARD_FILES_MISSING: nothing readable at {bdir}'
            continue
        inact = official_inactive_ids(gid)
        rows.extend(build_rows(gid, pick, board, manifest, draws, market,
                               names, teams, inact))
        summaries[gid] = game_summary(gid, pick, board, manifest, draws,
                                      names, teams, inact)

    n_elig = sum(1 for r in rows if r['RANKING_ELIGIBLE'])
    reasons = collections.Counter(
        w for r in rows for w in r['ranking_ineligible_reasons'])
    doc = {
        'artifact': 'NFL_DAILY_BOARD', 'spec_version': SPEC_VERSION,
        'date': date_str,
        'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'read_only': True,
        'what_this_is_not': (
            'Not a betting strategy, a bankroll layer or an edge engine. '
            'model_minus_market_probability is ' + DISAGREEMENT_LABEL + '. No '
            'tier is assigned here; the primitives a ranking needs are '
            'exposed and the ranking belongs to the decision layer.'),
        'one_way_rule': (
            'Prices enter this module and stop. Nothing derived from a line, '
            'a price or a market probability is written back into any '
            'forecast, prior or file under nfl/production.'),
        'games_found': len(by_game), 'games_read': len(summaries),
        'games_skipped': skipped,
        'market_snapshot': {'state': mk.state.name, 'code': mk.code,
                            'path': mk.evidence.get('path'),
                            'n_keys': mk.evidence.get('n_keys')},
        'n_rows': len(rows), 'n_ranking_eligible': n_elig,
        'n_ranking_ineligible': len(rows) - n_elig,
        'ineligible_reason_counts': dict(reasons),
        'ranking_primitives': [
            'abs_probability_disagreement',
            'line_minus_mean_native_units',
            'line_minus_mean_in_model_sds',
            'line_percentile_in_model_distribution',
            'over_price / under_price / market_hold',
            'source_freshness / latest_information_timestamp',
            'candidate_version / promoted',
            'known_defect_flags',
            'correlation_group'],
        'rows': rows,
    }
    (out / 'DAILY_BOARD.json').write_text(json.dumps(doc, indent=1,
                                                     default=str) + '\n')
    write_csv(out / 'DAILY_BOARD.csv', rows, _CSV_COLS)
    write_csv(out / 'MARKET_COMPARISON.csv',
              [r for r in rows if r.get('market_line') is not None],
              _MARKET_COLS)
    for gid, s in summaries.items():
        d = out / gid
        d.mkdir(parents=True, exist_ok=True)
        (d / 'GAME_SUMMARY.json').write_text(
            json.dumps(s, indent=1, default=str) + '\n')
    return Outcome.ok(
        'DAILY_BOARD_BUILT', value=str(out), spec_version=SPEC_VERSION,
        n_games=len(summaries), n_rows=len(rows), n_ranking_eligible=n_elig,
        games_skipped=skipped, out_dir=str(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--date', required=True, help='slate date, YYYY-MM-DD, '
                                                  'matched against KICKOFF')
    ap.add_argument('--market', default=None,
                    help='frozen pregame market snapshot CSV. Comparator '
                         'only; never an input to a forecast.')
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    o = build(a.date, a.market, a.out)
    print(f'{o.state.name}[{o.code}] {o.evidence.get("n_rows")} row(s) across '
          f'{o.evidence.get("n_games")} game(s); '
          f'{o.evidence.get("n_ranking_eligible")} rankable')
    for gid, why in (o.evidence.get('games_skipped') or {}).items():
        print(f'  skipped {gid}: {why}')
    print(f'  -> {o.evidence.get("out_dir")}')
    return 0 if o.state is State.PASS else 1


if __name__ == '__main__':
    sys.exit(main())
