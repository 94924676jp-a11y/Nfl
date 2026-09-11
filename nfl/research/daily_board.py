"""A read-only research slate export over SEALED candidate artifacts.

    python3.12 -m nfl.research.daily_board --date 2026-09-11 --candidate R8
    python3.12 -m nfl.research.daily_board --date 2026-09-11 --candidate all

THE SEPARATION THIS MODULE EXISTS TO KEEP.

    production board  = the promoted model only
    research board    = sealed candidates only

They share a schema so a reader can put them side by side, and they share
NOTHING else. This module imports the product board's primitives -- the
column list, the correlation grouping, the de-vig, the eligibility gate -- so
the two cannot drift apart silently, and it writes exclusively under
nfl/research/daily/. A write into nfl/product from here is a bug, and
`assert_never_writes_into_product` refuses before a byte is written.

WHAT IT WILL NOT DO. It reads already-sealed artifacts. It never invokes
training, never touches a parameter, never re-runs a forecast, and never
flips `promoted`, which stays False on every row because none of these
candidates is promoted.

VOCABULARY IS LOAD-BEARING HERE. Nothing in this module is called a bet, an
edge, or EV. The comparison against a book is a DISAGREEMENT -- a hypothesis
about the book, not a claim about money -- and `PRIORITY_MARKETS.csv` is a
REDUCED CANDIDATE SET, not a tier list and not a recommendation. No
subjective threshold is applied anywhere: a row is in that file only if it
already passed the deterministic gates.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import pathlib
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from nfl.product import daily_board as PB                             # noqa: E402
from nfl.research import completeness as CP                           # noqa: E402

SPEC_VERSION = 'research-daily-board-1'

LIVE = _REPO / 'nfl' / 'research' / 'live'
OUT_ROOT = _REPO / 'nfl' / 'research' / 'daily'

CANDIDATES = ('V1', 'R5', 'R6', 'R7', 'R8')

# post_inactives_V1_CANDIDATE_R8 -> cutoff 'post_inactives', candidate 'R8'
_LABEL = re.compile(r'^(?P<cutoff>pre_inactives|post_inactives)'
                    r'_V1_CANDIDATE(?:_(?P<cand>R\d+))?$')

# Words this module may never emit, checked by the suite rather than by hope.
FORBIDDEN_VOCABULARY = ('bet', 'edge', 'ev', 'wager', 'pick', 'lock')


def assert_never_writes_into_product(path) -> Outcome:
    """Refuse before writing if a destination escapes the research tree."""
    p = pathlib.Path(path).resolve()
    product = (_REPO / 'nfl' / 'product').resolve()
    if p == product or product in p.parents:
        return Outcome.fail(
            'RESEARCH_WRITE_INTO_PRODUCT',
            f'{p} is inside {product}. The research export may never write '
            f'into the production namespace; that separation is the point of '
            f'having two boards.')
    return Outcome.ok('RESEARCH_WRITE_TARGET_OK', value=str(p))


def parse_label(name):
    """('post_inactives', 'R8') for a sealed directory name, or (None, None)."""
    m = _LABEL.match(name)
    if not m:
        return None, None
    return m.group('cutoff'), (m.group('cand') or 'V1')


def discover(date_str):
    """Every sealed research board for games kicking off on `date`.

    Returns {(game_id, cutoff, candidate): {...}}. Nothing is run and nothing
    is fitted; a board that is not already on disk simply is not here.
    """
    found = {}
    if not LIVE.exists():
        return found
    for gdir in sorted(LIVE.iterdir()):
        if not gdir.is_dir():
            continue
        for bdir in sorted(gdir.iterdir()):
            if not bdir.is_dir():
                continue
            cutoff, cand = parse_label(bdir.name)
            if cutoff is None:
                continue
            bj = list(bdir.glob('**/board.json'))
            if not bj:
                continue
            board = json.load(open(bj[0]))
            fresh = board.get('freshness') or {}
            ko = str(fresh.get('kickoff_utc') or '')
            if ko[:10] != date_str:
                continue
            mj = list(bdir.glob('**/player_draws_manifest.json'))
            found[(gdir.name, cutoff, cand)] = {
                'game_id': gdir.name, 'cutoff': cutoff, 'candidate': cand,
                'dir': bj[0].parent, 'board': board,
                'manifest': json.load(open(mj[0])) if mj else None,
                'run_id': bj[0].parent.name if bj[0].parent != bdir else None,
                'written_at': str(fresh.get('written_at') or ''),
                'kickoff_utc': ko,
            }
    return found


def _idx_row(entry):
    """The product row-builder expects an index row; synthesise one.

    `promoted` is hard-coded False rather than read from anywhere. None of
    these candidates is promoted, and a research export is not a place where
    that could become true by accident.
    """
    return {'game_id': entry['game_id'], 'kickoff_utc': entry['kickoff_utc'],
            'written_at': entry['written_at'], 'run_id': entry['run_id'],
            'promoted': False}


def rows_for(entry, market, names, teams, inactive_ids):
    """Rows in the PRODUCT schema, plus the research identity columns."""
    # THE BOARD'S OWN DIRECTORY, AND NOTHING ABOVE IT.
    #
    # This read `entry['dir'].parent` first. The post-inactives boards nest a
    # run_id directory so the parent was still the board; the pre-inactives
    # boards do not, so the parent was the GAME directory and the recursive
    # glob returned whichever candidate's draws it reached first -- R8 rows
    # read against another candidate's array, which surfaced as an IndexError
    # rather than as a wrong number, by luck.
    draws = PB._load_draws(entry['dir'])
    rows = PB.build_rows(entry['game_id'], _idx_row(entry), entry['board'],
                         entry['manifest'], draws, market, names, teams,
                         inactive_ids)
    matrix = CP.layer_matrix(entry['board'], entry['manifest'], draws)
    for r in rows:
        # COMPLETENESS IS PER MARKET, NOT PER GAME. A quarterback's passing
        # yards can stand in a game whose carry allocation never ran, because
        # the causal path behind THAT market is intact. Making it binary per
        # game would throw away usable forecasts for no reason.
        ok, miss = CP.market_rankable(r['metric'], matrix)
        r['causal_path_complete'] = ok
        r['causal_layers_missing'] = miss
        r['forecast_completeness'] = CP.forecast_completeness(matrix)
        r['candidate'] = entry['candidate']
        r['cutoff'] = entry['cutoff']
        r['research_label'] = f"{entry['cutoff']}_{entry['candidate']}"
        r['promoted'] = False
        r['namespace'] = 'research'
    return rows


# --------------------------------------------- candidate comparison
COMPARISON_COLS = ['game_id', 'cutoff', 'player', 'metric', 'market_line',
                   'V1', 'R5', 'R6', 'R7', 'R8', 'actual_if_known',
                   'actual_source']


def load_actuals(game_id):
    """Realised outcomes for a game, or {} when the game has not been played.

    EMPTY IS THE HONEST ANSWER BEFORE KICKOFF. `actual_if_known` stays blank
    rather than being filled with a zero, and the artifact says which file a
    populated value came from so a reader can judge its provenance rather
    than inheriting our confidence in it.
    """
    p = LIVE / game_id / 'REALIZED_OUTCOMES.json'
    if not p.exists():
        return {}, None
    d = json.loads(p.read_text())
    src = (d.get('provenance') or {}).get('kind') or 'UNLABELLED'
    out = {}
    for who, st in (d.get('passing') or {}).items():
        for k, m in (('att', 'qb/att'), ('cmp', 'qb/cmp'),
                     ('pyds', 'qb/pyds'), ('ptd', 'qb/ptd'), ('int', 'qb/int')):
            if k in st:
                out[(who, m)] = st[k]
    for who, st in (d.get('rushing') or {}).items():
        if 'carries' in st:
            out[(who, 'rushing/carries')] = st['carries']
    for who, st in (d.get('receiving') or {}).items():
        for k, m in (('receptions', 'receiving/receptions'),
                     ('receiving_yards', 'receiving/receiving_yards')):
            if k in st:
                out[(who, m)] = st[k]
    return out, src


def comparison_rows(all_rows, actuals_by_game):
    """One row per (game, cutoff, player, metric) with every candidate's mean.

    SAME CUTOFF ONLY. Candidates are comparable when they saw the same
    information; a pre-inactives R7 against a post-inactives R8 would differ
    by the official inactive list as well as by architecture, and the
    difference could not be attributed to either. The cutoff is therefore
    part of the key rather than something averaged over.
    """
    keyed = collections.defaultdict(dict)
    meta = {}
    for r in all_rows:
        k = (r['game_id'], r['cutoff'], r['player'], r['metric'])
        keyed[k][r['candidate']] = r['model_mean']
        meta.setdefault(k, {'market_line': r.get('market_line')})
        if meta[k]['market_line'] is None:
            meta[k]['market_line'] = r.get('market_line')
    out = []
    for (gid, cutoff, player, metric), by_cand in sorted(keyed.items()):
        act, src = actuals_by_game.get(gid, ({}, None))
        a = act.get((player, metric))
        row = {'game_id': gid, 'cutoff': cutoff, 'player': player,
               'metric': metric,
               'market_line': meta[(gid, cutoff, player, metric)]['market_line'],
               'actual_if_known': a,
               'actual_source': src if a is not None else None}
        for c in CANDIDATES:
            row[c] = by_cand.get(c)
        out.append(row)
    return out


# ------------------------------------------------- reduced candidate set
PRIORITY_COLS = PB._MARKET_COLS + ['candidate', 'cutoff', 'namespace',
                                   'source_freshness', 'promoted',
                                   'forecast_completeness',
                                   'causal_path_complete',
                                   'causal_layers_missing']


def priority_rows(rows, max_input_age_hours=None):
    """The REDUCED CANDIDATE SET. Not a tier list, not a recommendation.

    Every row here already passed the deterministic gates; nothing is scored,
    ranked or thresholded. Four conditions, each of which is a fact about the
    row rather than a judgement about it:

      ranking eligible      -- the existing gate, unchanged
      distribution-backed   -- stored draws exist, not only a point mean
      fresh                 -- the inputs are not older than the caller's
                               declared bound; with no bound, freshness is
                               reported and nothing is dropped for it
      not contaminated      -- no known defect touches THIS metric

    NO SUBJECTIVE THRESHOLD IS APPLIED. In particular no minimum disagreement,
    no price filter and no ordering: the decision layer ranks, this reduces.
    """
    out, dropped = [], collections.Counter()
    for r in rows:
        if not r.get('RANKING_ELIGIBLE'):
            dropped['not_ranking_eligible'] += 1
            continue
        if not r.get('has_distribution'):
            dropped['no_distribution'] += 1
            continue
        if any(f.get('contaminates_this_metric')
               for f in (r.get('known_defect_flags') or [])):
            dropped['known_defect_contaminates_metric'] += 1
            continue
        # THE CAUSAL LAYER BEHIND THIS MARKET MUST HAVE RUN.
        # A receiving-yards row whose targets layer deferred is not a
        # forecast of receiving yards; it is the absence of one.
        if not r.get('causal_path_complete', True):
            dropped['causal_layer_incomplete'] += 1
            continue
        age = r.get('source_freshness')
        if (max_input_age_hours is not None and age is not None
                and float(age) > float(max_input_age_hours)):
            dropped['inputs_older_than_declared_bound'] += 1
            continue
        out.append(r)
    return out, dict(dropped)


# ----------------------------------------------------------------- main
RESEARCH_COLS = PB._CSV_COLS + ['candidate', 'cutoff', 'research_label',
                                'namespace', 'forecast_completeness',
                                'causal_path_complete',
                                'causal_layers_missing']


def build(date_str, candidate='R8', market_path=None, out_dir=None,
          cutoff=None, max_input_age_hours=None):
    out = pathlib.Path(out_dir or (OUT_ROOT / date_str))
    guard = assert_never_writes_into_product(out)
    if guard.state is not State.PASS:
        return guard
    out.mkdir(parents=True, exist_ok=True)

    wanted = (list(CANDIDATES) if str(candidate).lower() == 'all'
              else [c.upper() for c in str(candidate).split(',')])
    bad = [c for c in wanted if c not in CANDIDATES]
    if bad:
        return Outcome.fail(
            'RESEARCH_UNKNOWN_CANDIDATE',
            f'{bad} is not among {CANDIDATES}. A candidate this export has '
            f'never sealed is a refusal, not an empty file.', unknown=bad)

    found = discover(date_str)
    if not found:
        return Outcome.blocked(
            'RESEARCH_NO_SEALED_BOARDS',
            f'no sealed research board kicks off on {date_str}. This export '
            f'reads sealed artifacts only and will not run a forecast to '
            f'create one.', cause=Cause.DATA, date=date_str)

    mk = PB.load_market(market_path) if market_path else Outcome.blocked(
        'MARKET_SNAPSHOT_NOT_SUPPLIED',
        'no --market was given; rows carry no quote and none is rankable.',
        cause=Cause.DATA)
    market = mk.value if mk.state is State.PASS else {}
    names, teams = PB.roster_names()

    selected, rows, all_rows = [], [], []
    for key, entry in sorted(found.items()):
        if cutoff and entry['cutoff'] != cutoff:
            continue
        inact = PB.official_inactive_ids(entry['game_id'])
        r = rows_for(entry, market, names, teams, inact)
        all_rows.extend(r)
        if entry['candidate'] in wanted:
            selected.append(entry)
            rows.extend(r)

    actuals = {g: load_actuals(g) for g in {e['game_id'] for e in found.values()}}
    comp = comparison_rows(all_rows, actuals)
    prio, dropped = priority_rows(rows, max_input_age_hours)

    n_elig = sum(1 for r in rows if r['RANKING_ELIGIBLE'])
    doc = {
        'artifact': 'NFL_RESEARCH_DAILY_BOARD', 'spec_version': SPEC_VERSION,
        'namespace': 'research', 'date': date_str,
        'candidates_requested': wanted,
        'candidates_found': sorted({e['candidate'] for e in found.values()}),
        'cutoffs_found': sorted({e['cutoff'] for e in found.values()}),
        'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'read_only': True, 'promoted': False,
        'separation': ('production board = promoted model only; research '
                       'board = sealed candidates only. This export writes '
                       'only under nfl/research/ and never into nfl/product.'),
        'what_this_is_not': (
            'No row here is a bet, an edge or an expected value. The market '
            'column is a comparator and model_minus_market_probability is '
            + PB.DISAGREEMENT_LABEL + '. PRIORITY_MARKETS.csv is a reduced '
            'candidate set produced by deterministic gates, not a tier list '
            'and not a recommendation.'),
        'sealed_boards_read': [
            {'game_id': e['game_id'], 'cutoff': e['cutoff'],
             'candidate': e['candidate'], 'run_id': e['run_id'],
             'written_at': e['written_at'], 'kickoff_utc': e['kickoff_utc'],
             'model_configuration': e['board'].get('model_configuration')}
            for e in selected],
        'n_rows': len(rows), 'n_ranking_eligible': n_elig,
        'n_priority_rows': len(prio),
        'priority_dropped_because': dropped,
        'n_comparison_rows': len(comp),
        'actuals_present_for': [g for g, (a, _s) in actuals.items() if a],
        'market_snapshot': {'state': mk.state.name, 'code': mk.code},
        'rows': rows,
    }
    (out / 'RESEARCH_DAILY_BOARD.json').write_text(
        json.dumps(doc, indent=1, default=str) + '\n')
    PB.write_csv(out / 'RESEARCH_DAILY_BOARD.csv', rows, RESEARCH_COLS)
    PB.write_csv(out / 'RESEARCH_CANDIDATE_COMPARISON.csv', comp,
                 COMPARISON_COLS)
    PB.write_csv(out / 'PRIORITY_MARKETS.csv', prio, PRIORITY_COLS)
    return Outcome.ok(
        'RESEARCH_DAILY_BOARD_BUILT', value=str(out),
        spec_version=SPEC_VERSION, n_rows=len(rows),
        n_boards=len(selected), n_ranking_eligible=n_elig,
        n_priority=len(prio), n_comparison=len(comp),
        candidates=wanted, out_dir=str(out),
        priority_dropped_because=dropped)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--date', required=True)
    ap.add_argument('--candidate', default='R8',
                    help="V1|R5|R6|R7|R8, a comma list, or 'all' for a "
                         "side-by-side export")
    ap.add_argument('--cutoff', default=None,
                    choices=['pre_inactives', 'post_inactives'],
                    help='restrict to one information cutoff; candidates are '
                         'only comparable within one')
    ap.add_argument('--market', default=None)
    ap.add_argument('--max-input-age-hours', type=float, default=None,
                    help='freshness bound for PRIORITY_MARKETS.csv. With no '
                         'bound nothing is dropped for age and freshness is '
                         'reported instead.')
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    o = build(a.date, a.candidate, a.market, a.out, a.cutoff,
              a.max_input_age_hours)
    if o.state is not State.PASS:
        print(f'{o.state.name}[{o.code}] {o.detail[:200]}')
        return 1
    e = o.evidence
    print(f'{o.state.name}[{o.code}] {e["n_rows"]} row(s) from '
          f'{e["n_boards"]} sealed board(s); {e["n_ranking_eligible"]} '
          f'rankable; {e["n_priority"]} in the reduced set; '
          f'{e["n_comparison"]} comparison row(s)')
    for k, v in (e.get('priority_dropped_because') or {}).items():
        print(f'  reduced set excluded {v}: {k}')
    print(f'  -> {e["out_dir"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
