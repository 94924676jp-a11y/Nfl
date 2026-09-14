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

WHICH COMPARISONS GET GRADED IS DECIDED PREGAME. Version 1.0.0 refused a quote
whenever `actuals` carried no record for the player: `NO_REALISED_VALUE`, "not
imputed". `actuals` emits a record only for a player who recorded at least one
target, carry or dropback, so in a COMPLETED game an absent record is not an
unknown -- for a count estimand it is the observed value ZERO.

THE DIRECTION THIS BIASES IS NOT NEUTRAL, AND IT FLATTERS US. A priced player
who recorded nothing settles UNDER at every line the book offered on him. The
model's selected side on such a player is very often OVER, because the forecast
that put volume on him is what generated the disagreement in the first place.
Deleting those rows therefore deletes a set enriched in comparisons the model
LOSES, and a hit rate, a mean gap or a bucket table computed on the survivors
reads better than the same statistic computed on every comparison the model
actually made. A disagreement diagnostic that quietly discards its own losses
is worse than no diagnostic.

MEASURED EXPOSURE ON THE ONLY GRADABLE SLATE: ZERO. On the frozen 1 PM
snapshot (343 quotes, 8 games) 161 quotes reached the realised-value check and
all 161 carried a record, so the refusal never fired and the published figures
are NOT contaminated by it. The defect was real in code and latent in effect.
It is repaired anyway, because "it has not bitten yet" is not a property of the
code, and because the first priced player who is inactive, ejected, or simply
never touches the ball would have triggered it silently and in one direction.

NOTHING ABOUT WHAT IS COMPARED CHANGES. The repair governs WHICH comparisons
are graded. A price is still an external disagreement diagnostic on a sealed
forecast -- never a target, a label, a prior, or a calibration anchor -- and no
projection, draw or probability is altered by anything in this module.
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
# ONE DEFINITION OF ABSENCE SEMANTICS, NOT TWO. The four-class classification,
# its derivations, the refusal codes and the cluster-robust SE all live in
# `same_day_retrospective` and are imported here. A second copy would drift,
# and the two scorers disagreeing about what an absent record means is how
# this defect reached two files in the first place.
from nfl.research import same_day_retrospective as SDR              # noqa: E402
from nfl.research.shadow import actuals as ACT                      # noqa: E402
from nfl.tools import market_comparison as MC                       # noqa: E402

# 2.0.0, not 1.0.1: which comparisons are graded is part of what a hit rate
# MEANS, so a figure from this module may not be compared with one from 1.0.0.
SPEC_VERSION = 'market-outcome-audit/2.0.0'

COLUMNS = ('slate', 'game_id', 'player', 'team', 'market', 'metric',
           'model_mean', 'model_median', 'hardrock_line',
           'over_odds', 'under_odds',
           'model_p_over_exact_line', 'model_p_under_exact_line',
           'hardrock_novig_p_over', 'hardrock_novig_p_under',
           'selected_side', 'probability_gap_pp', 'actual',
           'actual_basis', 'absence_class', 'result',
           'model_written_at', 'hardrock_retrieved_at', 'data_status',
           'stratum', 'refusal_reason')

# Refusal codes this module can emit for a realised value. Every one is NAMED
# and counted; a quote that is neither graded nor named is a defect.
R_UNOBSERVED = 'REALISED_VALUE_UNOBSERVED_NOT_ZERO'
R_NOT_APPLICABLE = 'ESTIMAND_NOT_APPLICABLE_TO_THIS_ROW'
R_UNRESOLVED = 'ABSENCE_SEMANTICS_UNRESOLVED'
R_FIELD_NOT_IN_ACTUALS = 'ESTIMAND_FIELD_NOT_IN_ACTUALS'
R_LEGACY_LEAK = 'NO_REALISED_VALUE'

SELECTION_COMPLETE = SDR.SELECTION_COMPLETE
SELECTION_LEAKED = SDR.SELECTION_LEAKED
LEAK_WARNING = (
    'THIS RUN REPRODUCES A KNOWN SELECTION LEAK ON PURPOSE. A quote whose '
    'player recorded nothing was deleted rather than graded. The deleted set '
    'is enriched in comparisons the model LOSES, so every hit rate, gap and '
    'bucket below flatters the model by an unmeasured amount. It exists only '
    'to reproduce the superseded artifact.')

BUCKETS = ((0, 5, '<5pp'), (5, 10, '5-10pp'), (10, 20, '10-20pp'),
           (20, 30, '20-30pp'), (30, 1e9, '>30pp'))


def resolve_realised(src, field, metric, final, legacy_outcome_selection=False):
    """The realised value for one quote, or a NAMED refusal.

    THE LADDER IS NOT HERE. `same_day_retrospective.resolve_realised` is the
    single decision point for what an absent realised record means, and this
    function does one thing: render its verdict into THIS artifact's refusal
    vocabulary. Two copies of a classification ladder held equivalent by an
    assertion in a test is a second source of truth waiting to drift, and the
    drift is not hypothetical -- it is the same shape as the defect WS-D
    confirmed elsewhere in this pass.

    The vocabularies genuinely differ and are preserved: this module's legacy
    code is `NO_REALISED_VALUE`, the retrospective's is
    `NO_REALISED_VALUE_FOR_THIS_PLAYER`, and both appear in already-published
    artifacts that must stay reproducible. The STRINGS are artifact
    vocabulary; the DECISION is what may not diverge.

    Returns `(actual, basis, absence_class)` when gradable, or
    `(None, ('REFUSED', code, detail), absence_class)` when not.
    """
    actual, basis, cls = SDR.resolve_realised(
        src, field, metric, final,
        legacy_outcome_selection=legacy_outcome_selection)
    if actual is not None or basis in ('OBSERVED', 'ZERO_BY_COMPLETION'):
        return actual, basis, cls
    _, kind, why = basis
    return None, ('REFUSED',) + _render_refusal(kind, why), cls


def _render_refusal(kind, why):
    """A refusal KIND in THIS module's published vocabulary. Strings preserved.

    Every kind the shared resolver can return must be rendered here. An
    unrendered kind raises rather than falling through to a generic string:
    a refusal this module cannot name is a quote that would vanish from the
    `balanced` accounting, which is exactly what that invariant exists to
    catch.
    """
    if kind == SDR.KIND_LEGACY_OUTCOME_SELECTION:
        return R_LEGACY_LEAK, 'not imputed'
    if kind == SDR.KIND_FIELD_NOT_IN_ACTUALS:
        return R_FIELD_NOT_IN_ACTUALS, (
            f'{why!r} is not a key of a realised record that DOES exist for '
            f'this player')
    if kind == SDR.KIND_UNOBSERVED:
        return R_UNOBSERVED, str(why)[:180]
    if kind == SDR.KIND_NOT_APPLICABLE:
        return R_NOT_APPLICABLE, str(why)[:180]
    if kind == SDR.KIND_UNRESOLVED:
        return R_UNRESOLVED, str(why)[:180]
    raise ValueError(
        f'UNRENDERED_REFUSAL_KIND: {kind!r} has no rendering in this module.')


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


def audit_slate(slate, games, snapshot, season=2026, label='V1_CANDIDATE_R8',
                outcome_blob=None, legacy_outcome_selection=False):
    snap = MC.load_frozen_snapshot(snapshot)
    quotes = snap['quotes']
    # A REPRODUCTION MUST NOT DEPEND ON THE NETWORK, and must not silently
    # score against restated upstream bytes. `stored_outcome` re-derives the
    # digest at load rather than trusting the provenance file beside it.
    o = (PG.stored_outcome(outcome_blob) if outcome_blob
         else PG.fetch_outcomes(season))
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
            actual, abasis, cls = resolve_realised(
                src, field, metric, fin,
                legacy_outcome_selection=legacy_outcome_selection)
            if actual is None:
                _, code, detail = abasis
                rows.append(_refusal(slate, gid, k, q, code, detail))
                continue
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
                'actual_basis': abasis, 'absence_class': cls,
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
            'actual_basis': '', 'absence_class': '',
            'result': '', 'model_written_at': '',
            'hardrock_retrieved_at': q.get('timestamp', ''),
            'data_status': 'REFUSED', 'stratum': 'REFUSED',
            'refusal_reason': f'REFUSED:{reason}'
                              + (f' | {detail}' if detail else '')}


# NAIVE BINOMIAL SEs ARE REFUSED, NOT COMPUTED AND LABELLED.
#
# Markets inside one player-game move together -- Receptions and Receiving
# Yards on the same afternoon are two views of one set of catches, and a
# player who is shadowed out of a game loses both. Games move together too.
# Treating 81 quotes as 81 independent trials understates the spread; measured
# elsewhere in this project, by roughly threefold. Emitting a naive SE beside
# a clustered one invites the smaller number to be quoted, so it is not
# emitted at all.
NAIVE_SE_REFUSED = (
    'A NAIVE BINOMIAL SE IS NOT EMITTED. Markets within a player-game, and '
    'player-games within a game, are not independent trials. Only '
    'game-clustered and player-game-clustered standard errors appear here, '
    'each beside its cluster count. With cluster counts in single figures no '
    'interval here is trustworthy at its nominal level.')


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
    # Cluster-robust SE of the hit rate, over DECIDED comparisons only: a
    # push is not a trial. `_cluster_se` is imported, not re-implemented, so
    # this module and the retrospective use one convention.
    d = [r for r in g if r['result'] in ('WIN', 'LOSS')]
    wins01 = [1.0 if r['result'] == 'WIN' else 0.0 for r in d]
    g_lab = [r['game_id'] for r in d]
    pg_lab = [(r['game_id'], r['player'], r['team']) for r in d]
    se_g = SDR._cluster_se(wins01, g_lab) if d else None
    se_pg = SDR._cluster_se(wins01, pg_lab) if d else None
    n_zero = sum(1 for r in g if r.get('actual_basis') == 'ZERO_BY_COMPLETION')
    return {
        'n': len(g), 'n_over': len(g) - u, 'n_under': u,
        'pct_under': round(u / len(g), 4),
        'wins': w, 'losses': l, 'pushes': p,
        'hit_rate_excl_push': round(w / dec, 4) if dec else None,
        'n_rows_is_not_a_sample_size': (
            'n counts QUOTES. The units these results vary in are the '
            'player-game and the game; both cluster counts are below.'),
        'n_game_clusters': len(set(g_lab)),
        'n_player_game_clusters': len(set(pg_lab)),
        'n_zero_by_completion': n_zero,
        'n_observed': len(g) - n_zero,
        'se_convention': NAIVE_SE_REFUSED,
        'se_hit_rate_game_clustered': (
            round(se_g, 4) if se_g is not None else None),
        'se_hit_rate_player_game_clustered': (
            round(se_pg, 4) if se_pg is not None else None),
        'player_game_clustering_degenerate': len(set(pg_lab)) == len(d),
        'player_game_clustering_note': (
            'one decided comparison per player-game in this stratum: the '
            'player-game SE here IS the naive SE and must not be read as '
            'clustered. Read the game-clustered figure.'
            if len(set(pg_lab)) == len(d) else
            'several markets share a player-game in this stratum, so the '
            'player-game SE is a genuine second clustering.'),
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
    ap.add_argument('--outcome-blob', default=None,
                    help='grade against an ALREADY-STORED outcome blob '
                         'instead of re-fetching, so a reproduction does not '
                         'depend on the network and cannot silently score '
                         'against restated upstream bytes.')
    ap.add_argument('--legacy-outcome-selection', action='store_true',
                    help='REPRODUCE THE KNOWN SELECTION LEAK: delete every '
                         'quote whose player recorded nothing, as version '
                         '1.0.0 did. For reproducing the superseded artifact '
                         'only. The output stamps itself as not a '
                         'measurement.')
    a = ap.parse_args(argv)
    games = a.games.split(',')
    rows, snap = audit_slate(a.slate, games, a.market,
                             outcome_blob=a.outcome_blob,
                             legacy_outcome_selection=a.legacy_outcome_selection)
    # A STAGE THAT PRODUCED NOTHING HAS NOT SUCCEEDED.
    if not rows:
        raise SystemExit(
            f'EMPTY_MARKET_AUDIT_RESULT: no row was produced from '
            f'{snap["n_quotes"]} quote(s) over {len(games)} game(s). An empty '
            f'result is an error, not a finding.')
    missing_cols = sorted({c for c in COLUMNS if c not in rows[0]})
    if missing_cols:
        raise SystemExit(
            f'MARKET_AUDIT_SCHEMA_INCOMPLETE: rows are missing '
            f'{missing_cols}. A column guessed at write time is how this '
            f'project exported 7,926 rows with every meaningful field blank.')
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
        'outcome_selection_basis': (SELECTION_LEAKED
                                    if a.legacy_outcome_selection
                                    else SELECTION_COMPLETE),
        'outcome_selection_note': (
            LEAK_WARNING if a.legacy_outcome_selection else
            'A quote is graded because the player is on a pregame board, the '
            'market maps to an exact estimand, and an identified draw row '
            'exists -- all decided before kickoff. An absent realised record '
            'in a COMPLETED game is read as the value its estimand defines, '
            'zero for a count or a sum over events, so a priced player who '
            'recorded nothing is graded rather than deleted. Nothing is '
            'imputed: every graded row is OBSERVED or ZERO_BY_COMPLETION and '
            'says which.'),
        'absence_semantics_source': (
            'nfl.research.same_day_retrospective.ABSENCE_SEMANTICS -- imported, '
            'not copied, so the two scorers cannot drift apart about what an '
            'absent record means.'),
        'n_zero_by_completion': sum(
            1 for r in rows if r.get('actual_basis') == 'ZERO_BY_COMPLETION'),
        'market_is_a_comparator_not_a_target': (
            'this repair governs WHICH comparisons are graded and nothing '
            'about what is compared. No price is a target, a label, a prior '
            'or a calibration anchor here, and no projection, draw or '
            'probability is altered by this module.'),
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
    print(f"selection: {summary['outcome_selection_basis']}  "
          f"zero_by_completion={summary['n_zero_by_completion']}")
    for k, v in summary['refusals_by_reason'].items():
        print(f'   {k}: {v}')
    if a.legacy_outcome_selection:
        print('WARNING: ' + LEAK_WARNING)
    return 0 if summary['accounting']['balanced'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
