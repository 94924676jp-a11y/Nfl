"""Model -> frozen market -> realised outcome, on three independently frozen objects.

THE JOIN, AND WHY EACH PIECE IS FROZEN SEPARATELY. A sealed pregame forecast
whose `written_at` precedes kickoff; a sportsbook quote whose retrieval clock
precedes kickoff; and a final outcome observed after the game. None is
regenerated, none is refreshed, and no missing row is imputed. If any of the
three is absent for a quote, the quote is REFUSED by name -- it never becomes a
silently smaller table.

WHAT THIS CAN AND CANNOT SETTLE. Actual football performance is truth. The
sportsbook is a SECOND COMPARATOR and nothing more: a market that beat us on a
Sunday has not been shown to be right, and a market we beat has not been shown
to be wrong. One slate is not a sample, nothing here is clustered, and no
threshold may be selected because it would have won today.

CONTAMINATION IS HELD OUT, NOT AVERAGED IN. Week-1 quarterback rows carry the
QB3 season-boundary defect and are reported in their own stratum. Their wins
and losses are not evidence about the layers that are working.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import forecast_stage as FS                        # noqa: E402
from nfl.product import market_cdf as MCDF                          # noqa: E402
from nfl.product import market_names as MN                          # noqa: E402
from nfl.product import names as NM                                 # noqa: E402
from nfl.research import postgame as PG                             # noqa: E402
from nfl.research.shadow import actuals as ACT                      # noqa: E402
from nfl.tools import market_comparison as MC                       # noqa: E402

SPEC_VERSION = 'market-outcome-audit/1.0.0'

COLUMNS = ('slate', 'game_id', 'player', 'team', 'market', 'metric',
           'model_mean', 'model_median', 'hardrock_line',
           'over_odds', 'under_odds',
           'model_p_over_exact_line', 'model_p_under_exact_line',
           'hardrock_novig_p_over', 'hardrock_novig_p_under',
           'selected_side', 'probability_gap_pp', 'actual', 'result',
           'model_written_at', 'hardrock_retrieved_at', 'data_status',
           'stratum', 'refusal_reason')

BUCKETS = ((0, 5, '<5pp'), (5, 10, '5-10pp'), (10, 20, '10-20pp'),
           (20, 30, '20-30pp'), (30, 1e9, '>30pp'))


def bucket_of(gap):
    for lo, hi, lab in BUCKETS:
        if lo <= abs(gap) < hi:
            return lab
    return '>30pp'


def grade(side, actual, line):
    """WIN / LOSS / PUSH for the model-selected side at the book's exact line."""
    if actual is None:
        return None
    if float(actual) == float(line):
        return 'PUSH'
    over = float(actual) > float(line)
    if side == 'OVER':
        return 'WIN' if over else 'LOSS'
    return 'LOSS' if over else 'WIN'


def pregame_seal(gdir, kickoff, label='V1_CANDIDATE_R8'):
    cands = []
    for cfg in sorted(gdir.glob(f'*_{label}')):
        for b in sorted(cfg.glob('*/board.json')):
            j = json.loads(b.read_text())
            wa = (j.get('freshness') or {}).get('written_at')
            if wa and str(wa) < str(kickoff):
                cands.append((str(wa), b.parent))
    cands.sort()
    return cands[-1] if cands else (None, None)


def audit_slate(slate, games, snapshot, season=2026, label='V1_CANDIDATE_R8'):
    snap = MC.load_frozen_snapshot(snapshot)
    quotes = snap['quotes']
    o = PG.fetch_outcomes(season)
    allrows = PG._rows(o.evidence['blob'])
    names = NM.lookup(None)
    pbp_names = ACT.names(allrows)
    from nfl.capture import coverage as CV
    plan = CV.load_week_plan(season, 1)
    ko_of = {}
    for g in plan.value or []:
        k = g.kickoff_utc
        ko_of[g.game_id] = (k.isoformat().replace('+00:00', 'Z')
                            if hasattr(k, 'isoformat') else str(k))
    rows = []
    scope = {t for g in games for t in g.split('_')[2:4]}
    handled = set()
    for gid in games:
        ko = ko_of.get(gid)
        sub = [r for r in allrows if r.get('game_id') == gid]
        gdir = _REPO / 'nfl' / 'research' / 'live' / gid
        wa, sd = pregame_seal(gdir, ko, label)
        teams = set(gid.split('_')[2:4])
        gq = {k: v for k, v in quotes.items() if k[1] in teams}
        if not sub:
            for k in gq:
                handled.add(k)
                rows.append(_refusal(slate, gid, k, quotes[k],
                                     'OUTCOME_NOT_PUBLISHED'))
            continue
        fin = PG.game_finality(sub)
        if not fin['final']:
            for k in gq:
                handled.add(k)
                rows.append(_refusal(slate, gid, k, quotes[k],
                                     PG.NOT_FINAL, ','.join(fin['unmet'])))
            continue
        if sd is None:
            for k in gq:
                handled.add(k)
                rows.append(_refusal(slate, gid, k, quotes[k],
                                     'NO_PREGAME_SEAL'))
            continue
        board = json.loads((sd / 'board.json').read_text())
        man = json.loads((sd / 'player_draws_manifest.json').read_text())
        draws = np.load(sd / 'player_draws.npz')
        stage = FS.stage_of_dirname(sd.parent.name)
        qb_block = FS.qb_metric_blockers(board, stage)
        qa = ACT.qb_actuals(sub)
        rr = ACT.receiving_rushing_actuals(sub)
        by_name = {}
        for p in board.get('players') or []:
            by_name[(names.get(p['gsis_id'], p['gsis_id']), p['team'])] = p
        for k in sorted(gq):
            handled.add(k)
            qn, qt, qmarket = k
            q = quotes[k]
            # CLOCK CHECK, ON EVERY ROW. A quote retrieved after kickoff is
            # not a pregame quote and is refused, not quietly included.
            if str(q['timestamp']) >= str(ko):
                rows.append(_refusal(slate, gid, k, q,
                                     'MARKET_QUOTE_NOT_PREGAME',
                                     f"retrieved {q['timestamp']} >= kickoff {ko}"))
                continue
            p = by_name.get((qn, qt))
            if p is None:
                rows.append(_refusal(slate, gid, k, q,
                                     'QUOTE_PLAYER_NOT_ON_BOARD'))
                continue
            metric, basis = MN.metric_for(qmarket, p.get('position'))
            if metric is None:
                rows.append(_refusal(slate, gid, k, q, 'MARKET_NOT_MAPPED',
                                     basis[:180]))
                continue
            if metric in PG.REFUSED_ESTIMANDS:
                rows.append(_refusal(slate, gid, k, q, 'ESTIMAND_REFUSED',
                                     PG.REFUSED_ESTIMANDS[metric][:180]))
                continue
            if metric not in PG.EXACT_ESTIMANDS:
                rows.append(_refusal(slate, gid, k, q, 'ESTIMAND_NOT_SCOREABLE',
                                     f'{metric} has no exact realised match'))
                continue
            if metric not in (p.get('metrics') or {}):
                rows.append(_refusal(slate, gid, k, q,
                                     'METRIC_NOT_ON_THIS_BOARD', metric))
                continue
            try:
                v = np.asarray(MC.draw_row_for(man, draws, metric,
                                               p['gsis_id']), float)
            except MC.DrawIdentityError as e:
                rows.append(_refusal(slate, gid, k, q,
                                     str(e).split(':')[0], str(e)[:180]))
                continue
            fam, field = PG.EXACT_ESTIMANDS[metric]
            src = (qa if fam == 'qb' else rr).get(p['gsis_id'])
            if src is None or src.get(field) is None:
                rows.append(_refusal(slate, gid, k, q,
                                     'NO_REALISED_VALUE', 'not imputed'))
                continue
            actual = float(src[field])
            c = MCDF.compare(v, metric, {
                'line': q['line'], 'over_price': q.get('over_price'),
                'under_price': q.get('under_price'),
                'retrieved_at': q.get('timestamp'),
                'source': q.get('sportsbook'),
                'market_timestamp': q.get('timestamp')})
            e, nv = c['exact_probability'], c['no_vig']
            do, du = c['disagreement_over'], c['disagreement_under']
            if do is None or du is None:
                rows.append(_refusal(slate, gid, k, q, 'NO_DEVIG_PRICES'))
                continue
            sidel = 'OVER' if do >= du else 'UNDER'
            gap = round((do if sidel == 'OVER' else du) * 100.0, 4)
            contaminated = (metric.startswith('qb/') and bool(qb_block))
            rows.append({
                'slate': slate, 'game_id': gid, 'player': qn, 'team': qt,
                'market': qmarket, 'metric': metric,
                'model_mean': round(float(v.mean()), 4),
                'model_median': round(float(np.median(v)), 4),
                'hardrock_line': q['line'],
                'over_odds': q.get('over_price'),
                'under_odds': q.get('under_price'),
                'model_p_over_exact_line': round(e['p_over'], 6),
                'model_p_under_exact_line': round(e['p_under'], 6),
                'hardrock_novig_p_over': round(nv['no_vig_over'], 6),
                'hardrock_novig_p_under': round(nv['no_vig_under'], 6),
                'selected_side': sidel, 'probability_gap_pp': gap,
                'actual': actual,
                'result': grade(sidel, actual, q['line']),
                'model_written_at': (board.get('freshness') or {}).get('written_at'),
                'hardrock_retrieved_at': q.get('timestamp'),
                'data_status': board.get('completeness'),
                'stratum': 'CONTAMINATED_QB3' if contaminated else 'CLEAN',
                'refusal_reason': '',
            })
    # EVERY QUOTE IN THE SNAPSHOT IS ACCOUNTED FOR, NOT EVERY QUOTE IN SCOPE.
    #
    # The frozen 1 PM file carries 5 rows whose `team` is the literal string
    # 'unresolved' -- Kenneth Gainwell and Andrei Iosivas, both real players in
    # 2026_01_TB_CIN. Scoping by team silently dropped them: 343 quotes became
    # "338 in scope" and five disappeared from the arithmetic entirely.
    #
    # THE CLUB IS NOT INFERRED. The join key is (player, team, market), and the
    # snapshot is frozen evidence that says it could not attribute these rows.
    # Filling the club in from a roster would be guessing an identity, which is
    # the defect class this project has paid for repeatedly. They are refused
    # by name and counted.
    for k in sorted(quotes):
        if k in handled:
            continue
        if str(k[1]).strip().lower() == 'unresolved':
            rows.append(_refusal(
                slate, 'UNRESOLVED_CLUB', k, quotes[k],
                'MARKET_QUOTE_TEAM_UNRESOLVED',
                'the frozen snapshot records this quote with team '
                '"unresolved". The club is NOT inferred, because the join key '
                'is (player, team, market) and attributing it would be '
                'guessing an identity.'))
        elif k[1] in scope:
            rows.append(_refusal(slate, 'UNASSIGNED', k, quotes[k],
                                 'QUOTE_TEAM_NOT_IN_AUDITED_GAMES'))
        else:
            rows.append(_refusal(
                slate, 'OUT_OF_SLATE', k, quotes[k],
                'QUOTE_TEAM_NOT_IN_THIS_SLATE',
                f'team {k[1]} is not a club of the audited games'))
    return rows, snap


def _refusal(slate, gid, key, q, reason, detail=''):
    qn, qt, qmarket = key
    return {'slate': slate, 'game_id': gid, 'player': qn, 'team': qt,
            'market': qmarket, 'metric': '', 'model_mean': '',
            'model_median': '', 'hardrock_line': q.get('line', ''),
            'over_odds': q.get('over_price', ''),
            'under_odds': q.get('under_price', ''),
            'model_p_over_exact_line': '', 'model_p_under_exact_line': '',
            'hardrock_novig_p_over': '', 'hardrock_novig_p_under': '',
            'selected_side': '', 'probability_gap_pp': '', 'actual': '',
            'result': '', 'model_written_at': '',
            'hardrock_retrieved_at': q.get('timestamp', ''),
            'data_status': 'REFUSED', 'stratum': 'REFUSED',
            'refusal_reason': f'REFUSED:{reason}'
                              + (f' | {detail}' if detail else '')}


def perf(rows):
    """Descriptive performance of the model-selected side. Never a strategy."""
    g = [r for r in rows if r['result']]
    if not g:
        return None
    w = sum(1 for r in g if r['result'] == 'WIN')
    l = sum(1 for r in g if r['result'] == 'LOSS')
    p = sum(1 for r in g if r['result'] == 'PUSH')
    dec = w + l
    u = sum(1 for r in g if r['selected_side'] == 'UNDER')
    mp = [float(r['model_p_over_exact_line']) if r['selected_side'] == 'OVER'
          else float(r['model_p_under_exact_line']) for r in g]
    kp = [float(r['hardrock_novig_p_over']) if r['selected_side'] == 'OVER'
          else float(r['hardrock_novig_p_under']) for r in g]
    return {
        'n': len(g), 'n_over': len(g) - u, 'n_under': u,
        'pct_under': round(u / len(g), 4),
        'wins': w, 'losses': l, 'pushes': p,
        'hit_rate_excl_push': round(w / dec, 4) if dec else None,
        'mean_model_probability': round(float(np.mean(mp)), 4),
        'mean_market_novig_probability': round(float(np.mean(kp)), 4),
        'mean_probability_gap_pp': round(
            float(np.mean([abs(float(r['probability_gap_pp'])) for r in g])), 4),
    }


def by(rows, keyfn):
    d = collections.defaultdict(list)
    for r in rows:
        d[keyfn(r)].append(r)
    return {str(k): perf(v) for k, v in sorted(d.items(), key=lambda x: str(x[0]))}


def buckets(rows):
    out = {}
    for lo, hi, lab in BUCKETS:
        s = [r for r in rows
             if r['result'] and lo <= abs(float(r['probability_gap_pp'])) < hi]
        out[lab] = perf(s) or {'n': 0, 'wins': 0, 'losses': 0, 'pushes': 0,
                               'hit_rate_excl_push': None}
    return out


def side_perf(rows, side):
    return perf([r for r in rows if r['selected_side'] == side])


def main(argv=None):
    ap = argparse.ArgumentParser(description='model -> market -> outcome audit')
    ap.add_argument('--slate', required=True)
    ap.add_argument('--games', required=True)
    ap.add_argument('--market', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    games = a.games.split(',')
    rows, snap = audit_slate(a.slate, games, a.market)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in COLUMNS})
    clean = [r for r in rows if r['stratum'] == 'CLEAN']
    cont = [r for r in rows if r['stratum'] == 'CONTAMINATED_QB3']
    ref = [r for r in rows if r['stratum'] == 'REFUSED']
    scope = {t for g in games for t in g.split('_')[2:4]}
    n_scope = sum(1 for k in snap['quotes'] if k[1] in scope)
    summary = {
        'artifact': 'SUNDAY_MARKET_OUTCOME_AUDIT', 'spec_version': SPEC_VERSION,
        'slate': a.slate, 'games': games,
        'market_snapshot': {'path': snap['path'], 'sha256': snap['sha256'],
                            'n_quotes': snap['n_quotes']},
        'accounting': {
            'n_quotes_in_snapshot': snap['n_quotes'],
            'n_quotes_in_scope': n_scope,
            'n_quotes_team_unresolved': sum(
                1 for k in snap['quotes']
                if str(k[1]).strip().lower() == 'unresolved'),
            'n_retrospective_compared': len(clean) + len(cont),
            'n_clean': len(clean), 'n_contaminated_qb3': len(cont),
            'n_refused': len(ref),
            # THE INVARIANT IS OVER THE WHOLE SNAPSHOT, not over a scoped
            # subset chosen by this run.
            'balanced': len(clean) + len(cont) + len(ref) == snap['n_quotes']},
        'refusals_by_reason': dict(collections.Counter(
            r['refusal_reason'].split('|')[0].strip() for r in ref)),
        'clean_overall': perf(clean),
        'clean_by_market': by(clean, lambda r: r['market']),
        'clean_probability_gap_buckets': buckets(clean),
        'clean_over_performance': side_perf(clean, 'OVER'),
        'clean_under_performance': side_perf(clean, 'UNDER'),
        'contaminated_qb3_overall': perf(cont),
        'contaminated_qb3_by_market': by(cont, lambda r: r['market']),
        'truth_source': 'actual football outcomes from authoritative '
                        'play-by-play. The sportsbook is a second comparator '
                        'and is never treated as truth.',
        'no_cutoff_was_optimised': True,
    }
    sp = out.with_suffix('.summary.json')
    sp.write_text(json.dumps(summary, indent=1, default=str) + '\n')
    ac = summary['accounting']
    print(f"{a.slate}: {ac['n_quotes_in_snapshot']} quote(s) in snapshot = "
          f"{ac['n_clean']} clean + {ac['n_contaminated_qb3']} contaminated + "
          f"{ac['n_refused']} refused -> "
          f"{'BALANCED' if ac['balanced'] else 'UNBALANCED'}")
    print(f'rows -> {out}')
    print(f'summary -> {sp}')
    if summary['clean_overall']:
        c = summary['clean_overall']
        print(f"clean: n={c['n']} under={c['pct_under']:.1%} "
              f"W-L-P {c['wins']}-{c['losses']}-{c['pushes']} "
              f"hit={c['hit_rate_excl_push']}")
    for k, v in summary['refusals_by_reason'].items():
        print(f'   {k}: {v}')
    return 0 if summary['accounting']['balanced'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
