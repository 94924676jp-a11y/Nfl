#!/usr/bin/env python3.12
"""D7 -- central-tendency diagnostic over the forward-valid sealed frame.

DIAGNOSTIC ONLY. Not a promotion test, not prospective evidence, not a ledger
row. Nothing here tunes, promotes or adjusts anything.

WHAT IT ADDS TO THE REPAIRED SCORER, AND WHAT IT REUSES UNCHANGED.

Every realised value, every refusal and every pregame role tier comes from
`same_day_retrospective` at spec 2.0.0 -- the repaired module. The absence
ladder (`resolve_realised`) is imported, not reimplemented, so no second
definition of "what an absent record means" exists in this file. What is added
is four things the scorer does not carry:

  1. PARTICIPATION, SEPARATED FROM VOLUME. For a count or a sum over events,
     E[Y] = P(opportunity > 0) * E[Y | opportunity > 0] exactly, because a
     player with zero opportunity contributes zero. Both factors are computed
     from the SAME stored draws the mean came from, so the identity holds by
     construction rather than by assumption, and the bias splits into a
     participation term and a conditional-volume term. That split is the
     question "where does the engine mis-project" answered arithmetically.

     THE OPPORTUNITY METRIC IS THE LAYER'S OWN: qb/db for the qb layer,
     receiving/targets for receiving, rushing/carries for rushing. It is NOT
     the metric being scored. Using the scored metric would call a quarterback
     who threw twice for zero yards a non-participant.

  2. DEPTH CHART, which the board carries per player (`QB1`, `WR3`, ...) and
     the scorer drops. Rank 1 is read as STARTER and rank >= 2 as BACKUP. This
     is the board's own pregame claim, not a postgame snap count.

  3. INJURY STATE, from two pregame byte-stored sources only: the official
     game-day inactive lists ingested per game, and the delivered week-1
     injury report published 2026-09-11T21:02Z. Both predate every kickoff
     here. `weekly_rosters.status` is NOT used: it is post-hoc and the
     repository's open `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` finding says
     so explicitly.

  4. SEASON BOUNDARY, recomputed from `previous_primary_detail` rather than
     read from a board field that the 1 PM seals predate -- the same reason
     the scorer recomputes its own contamination flag.

UNITS ARE NOT POOLED. A mean signed error that averages passing yards with
interceptions is not a quantity. Every cell in the primary table is one
(position, metric) pair. Pooled rows appear only where explicitly labelled
UNIT_MIXED and they are not interpretable as a bias.

CLUSTERING. Rows within a game move together. Every figure carries its game
cluster count and its player-game cluster count, and the standard error of a
mean signed error is the CRVE with the G/(G-1) finite-cluster correction --
the same convention `same_day_retrospective._cluster_se` uses, reused by
import so the two cannot drift. No naive standard error is emitted.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve()
while _REPO.name and not (_REPO / 'nfl' / 'tests' / 'run_suite.py').exists():
    _REPO = _REPO.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.research import postgame as PG                              # noqa: E402
from nfl.research import same_day_retrospective as SDR               # noqa: E402
from nfl.research.shadow import actuals as ACT                       # noqa: E402

SPEC_VERSION = 'd7-central-tendency/1.0.0'
NOT_EVIDENCE = ('DIAGNOSTIC ONLY. Not a promotion test. Not prospective '
                'evidence, not a ledger row, clears no blocker, and nothing '
                'in it may be used to tune, promote or adjust any layer.')

# The opportunity metric of each layer -- the denominator of participation.
OPP_OF_LAYER = {'qb': 'qb/db',
                'receiving': 'receiving/targets',
                'rushing': 'rushing/carries'}

# The realised-side field of each layer's opportunity metric, taken from the
# governed estimand map so it cannot drift from what the scorer reads.
OPP_FIELD = {lay: PG.EXACT_ESTIMANDS[m][1] for lay, m in OPP_OF_LAYER.items()}

INJURY_BLOB = 'nfl/vintage/injuries.0bc645a4b9aa6255.csv.gz'
INJURY_INGEST = 'nfl/research/live/DELIVERED_INJURY_INGEST_2026-09-13.json'


# ------------------------------------------------------------------ inputs
def injury_report():
    """gsis_id -> report_status, from the delivered week-1 report.

    PUBLISHED 2026-09-11T21:02:00Z, which precedes every kickoff in this
    frame, so using it is chronologically lawful. It is also THIN -- the file
    carries 48 rows for the whole league -- and a player's absence from it is
    therefore NOT a claim that he was healthy. The class emitted for an absent
    player is NOT_ON_REPORT, never ACTIVE or HEALTHY.
    """
    p = _REPO / INJURY_BLOB
    if not p.exists():
        raise SystemExit(f'D7_INJURY_BLOB_MISSING: {p}')
    ing = json.loads((_REPO / INJURY_INGEST).read_text())
    rows = list(csv.DictReader(gzip.open(p, 'rt')))
    if not rows:
        raise SystemExit('D7_INJURY_BLOB_EMPTY: an empty parse is an error.')
    out = {}
    for r in rows:
        if str(r.get('season')) == '2026' and str(r.get('week')) == '1':
            out[r['gsis_id']] = (r.get('report_status') or '').upper()
    return out, {'blob': INJURY_BLOB,
                 'sha256': ing['csv_sha256'],
                 'publication_time': ing['clocks']['publication_time'],
                 'n_rows_total': len(rows),
                 'n_week1_2026': len(out),
                 'n_teams_represented': len({r['team'] for r in rows}),
                 'absence_means': 'NOT_ON_REPORT, which is not a health claim'}


def inactives(gid):
    """gsis_ids on the official game-day inactive list, per club.

    Step 4b of the ingestion says it outright: absence from the list carries no
    positive claim. So this returns only the positive set.
    """
    p = _REPO / 'nfl' / 'research' / 'live' / gid / 'INACTIVES_INGESTION.json'
    if not p.exists():
        return None, {'game_id': gid, 'status': 'NO_INACTIVES_INGESTION'}
    j = json.loads(p.read_text())
    step = next((s for s in j['steps']
                 if s.get('code') == 'POST_INACTIVES_COMPLETE'), None)
    if not step:
        return None, {'game_id': gid, 'status': 'INACTIVES_NOT_COMPLETE'}
    ids = {pid for lst in step['inactive_by_team'].values() for pid in lst}
    return ids, {'game_id': gid, 'status': 'OK', 'n_inactive': len(ids),
                 'hours_before_kickoff': step.get('hours_before_kickoff'),
                 'n_unmapped': j['steps'][2].get('n_unmapped')}


def season_openers(season, week):
    """team -> is_season_opener, from the governed allocation helper.

    Recomputed, never read from the board: `qb3_configuration` was added to the
    board after the 1 PM seals were written, so reading it off those boards
    returns a false negative for every club.
    """
    from nfl.production.nonqb import qb_allocation as QA
    detail = QA.previous_primary_detail(season, week)
    return {k: bool((v or {}).get('is_season_opener'))
            for k, v in detail.items()}


def prior_history_counts(season, week):
    """The engine's OWN trailing-history count per player, at this cut.

    WHY IT IS RECOMPUTED HERE RATHER THAN APPROXIMATED. `role_prior.weight`
    returns the tier mean exactly when `n_own` is zero, so for a player with
    no trailing history the TIER IS THE WHOLE FORECAST. Three separately
    reported week-1 mechanisms key on this same variable, so a week-1 number
    pooled over players with and without history averages the affected against
    the unaffected. Splitting on it is the only way to see the effect.

    The count is rebuilt with the identical filter `p4c_params` uses --
    position in the class, `ord < cut`, a non-null share, and `appeared` --
    so it is the same quantity the forecast consumed, not a proxy for it.

    CHRONOLOGY IS ENFORCED BY THE FILTER: `ord < cut` admits only team-games
    strictly before this season-week, so no row of the week being forecast,
    and nothing after it, can enter.
    """
    from nfl.production.nonqb import p4c_params as PP
    a = PP.ensure_artifacts()
    if a.state is not State.PASS:
        raise SystemExit(f'D7_PANEL_UNAVAILABLE: {a.code} {a.detail}')
    import p4c_build as B
    import p4c_lib as L
    rows = B.load_panel()
    if not rows:
        raise SystemExit('D7_PANEL_EMPTY: an empty panel is an error.')
    cut = season * 100 + week
    n = {'targets': collections.Counter(), 'carries': collections.Counter(),
         'qb': collections.Counter()}
    for r in rows:
        if r['ord'] >= cut:
            continue
        for cls in ('targets', 'carries'):
            if r['position'] in L.CLASSES[cls]['pos']:
                if r.get(L.CLASSES[cls]['share']) is not None and r['appeared']:
                    n[cls][r['gsis_id']] += 1
        if (r.get('dropbacks_as_passer') or 0) > 0:
            n['qb'][r['gsis_id']] += 1
    return {k: dict(v) for k, v in n.items()}, {
        'source': 'p4c_build.load_panel()',
        'cut_ordinal': cut,
        'filter': "ord < cut, position in class, share not null, appeared",
        'n_panel_rows': len(rows),
        'panel_ord_min': min(r['ord'] for r in rows),
        'panel_ord_max': max(r['ord'] for r in rows),
        'qb_basis': 'team-games with dropbacks_as_passer > 0 before the cut',
        'n_players_with_target_history': len(n['targets']),
        'n_players_with_carry_history': len(n['carries']),
        'n_players_with_dropback_history': len(n['qb']),
    }


def history_bucket(k):
    """NONE / THIN / ESTABLISHED. The boundaries are stated, not tuned.

    NONE is n_own == 0, which is the exact point at which `role_prior.weight`
    stops using the player at all and returns the tier mean. THIN is 1-4 and
    ESTABLISHED is 5 or more; those two are a readable split of the remainder
    and nothing in this artifact turns on where they fall. No threshold here
    was chosen because it produced a result.
    """
    if k is None:
        return 'UNKNOWN'
    if k == 0:
        return 'NONE'
    return 'THIN_1_4' if k <= 4 else 'ESTABLISHED_5PLUS'


def depth_rank(dc):
    if not dc:
        return None
    digits = ''.join(ch for ch in str(dc) if ch.isdigit())
    return int(digits) if digits else None


# ------------------------------------------------------------- draw-derived
def participation_from_draws(draws, manifest, layer, pid):
    """(p_nonzero, opportunity vector) for one player-layer, by row id.

    Rows are addressed through the manifest's `row_ids`, never positionally.
    """
    opp_metric = OPP_OF_LAYER[layer]
    ids = ((manifest.get('layers') or {}).get(layer) or {}).get('row_ids') or []
    key = opp_metric.replace('/', '__')
    if pid not in ids or key not in draws.files:
        return None, None
    v = np.asarray(draws[key][ids.index(pid)], float)
    return float((v > 0).mean()), v


# ------------------------------------------------------------------ scoring
def build(season, games, blob, seal_choice):
    o = PG.stored_outcome(blob)
    if o.state is not State.PASS:
        raise SystemExit(f'OUTCOME_REFUSED: {o.code} {o.detail}')
    allrows = PG._rows(o.evidence['blob'])
    outcome_sha = o.evidence['sha256']
    names = ACT.names(allrows)

    from nfl.capture import coverage as CV
    plan = CV.load_week_plan(season, 1)
    ko_of = {}
    for g in plan.value or []:
        k = g.kickoff_utc
        ko_of[g.game_id] = (k.isoformat().replace('+00:00', 'Z')
                            if hasattr(k, 'isoformat') else str(k))

    inj, inj_prov = injury_report()
    openers = season_openers(season, 1)
    nown, nown_prov = prior_history_counts(season, 1)

    rows, seals, skipped, inact_prov = [], [], [], []
    for gid in games:
        sub = [r for r in allrows if r.get('game_id') == gid]
        if not sub:
            skipped.append({'game_id': gid,
                            'status': 'NOT_IN_AUTHORITATIVE_OUTCOME_SOURCE'})
            continue
        fin = PG.game_finality(sub)
        if not fin['final']:
            skipped.append({'game_id': gid, 'status': PG.NOT_FINAL,
                            'unmet': fin['unmet']})
            continue
        ko = ko_of.get(gid)
        if not ko:
            skipped.append({'game_id': gid, 'status': 'NO_KICKOFF_IN_PLAN'})
            continue
        # BOARD DISCOVERY IS THE SCORER'S, AT ANY DEPTH. The previous
        # `cfg.glob('*/board.json')` hard-coded one directory level and saw
        # 104 of 121 sealed boards -- which is why this module's own
        # D7_ROWS_ALL_SEALS artifact carried ONE seal for 2026_01_SF_LA
        # against four to eight for every other game, with ten board.json on
        # that game's disk. Imported, not reimplemented, for the reason this
        # module already imports the absence ladder: a second copy drifts.
        cands = []
        for sd in SDR.sealed_board_dirs(game_id=gid, label='V1_CANDIDATE_R8'):
            j = json.loads((sd / 'board.json').read_text())
            wa = (j.get('freshness') or {}).get('written_at')
            if wa and str(wa) < str(ko):
                cands.append((str(wa), sd))
        if not cands:
            skipped.append({'game_id': gid, 'status': 'NO_PREGAME_SEAL'})
            continue
        cands.sort()
        pick = ([cands[0]] if seal_choice == 'first'
                else [cands[-1]] if seal_choice == 'last' else cands)
        ina, iprov = inactives(gid)
        inact_prov.append(iprov)
        qb_act = ACT.qb_actuals(sub)
        rr_act = ACT.receiving_rushing_actuals(sub)
        for rank, (wa, sd) in enumerate(pick):
            base, status = SDR.score_seal(gid, ko, sd, sub, outcome_sha, names,
                                          finality=fin)
            seals.append(status)
            if not base:
                continue
            board = json.loads((sd / 'board.json').read_text())
            man = json.loads((sd / 'player_draws_manifest.json').read_text())
            # EITHER ENCODING: SF_LA's pre-inactives seals store
            # `player_draws.npz.gz`, and a literal `.npz` here would raise on
            # exactly the five boards the depth repair just made visible.
            draws = SDR.load_sealed_draws(sd)
            meta = {p['gsis_id']: p for p in board.get('players') or []}
            pcache = {}
            for r in base:
                pid, lay = r['gsis_id'], r['layer']
                if (pid, lay) not in pcache:
                    pcache[(pid, lay)] = participation_from_draws(
                        draws, man, lay, pid)
                p_m, opp_v = pcache[(pid, lay)]
                # THE SCORED METRIC'S OWN DRAWS, re-read by row id so the
                # conditional mean and the unconditional mean come from the
                # same vector the scorer used.
                ids = ((man.get('layers') or {}).get(lay) or {}).get(
                    'row_ids') or []
                key = r['metric'].replace('/', '__')
                v = np.asarray(draws[key][ids.index(pid)], float)
                cond = (float(v[opp_v > 0].mean())
                        if opp_v is not None and (opp_v > 0).any() else None)
                # REALISED PARTICIPATION, from the layer's opportunity field.
                src = qb_act.get(pid) if lay == 'qb' else rr_act.get(pid)
                of = OPP_FIELD[lay]
                if src is None:
                    opp_a, opp_a_basis = 0.0, 'ZERO_BY_COMPLETION'
                elif src.get(of) is None:
                    opp_a, opp_a_basis = None, 'FIELD_NOT_IN_ACTUALS'
                else:
                    opp_a, opp_a_basis = float(src[of]), 'OBSERVED'
                mp = meta.get(pid) or {}
                dc = mp.get('depth_chart')
                dr = depth_rank(dc)
                st = inj.get(pid)
                if ina is not None and pid in ina:
                    istate = 'OFFICIAL_INACTIVE'
                elif st:
                    istate = st
                elif ina is None:
                    istate = 'NO_INACTIVE_LIST_FOR_THIS_GAME'
                else:
                    istate = 'NOT_ON_REPORT'
                r = dict(r)
                e = r['model_mean'] - r['actual']
                hk = ('qb' if lay == 'qb'
                      else 'carries' if lay == 'rushing' else 'targets')
                n_own = nown[hk].get(pid, 0)
                r.update({
                    'season': season,
                    'week': int(str(gid).split('_')[1]),
                    'seal_rank': rank,
                    'seal_dir': str(sd.relative_to(_REPO)),
                    'depth_chart': dc,
                    'depth_rank': dr,
                    # A PLAYER WITH NO DEPTH-CHART ENTRY IS A THIRD CLASS,
                    # not a missing value. The board carried him into the
                    # forecast pool anyway, so he has a projection and he
                    # belongs in the accounting under his own name.
                    'starter_or_backup': (
                        'NOT_ON_DEPTH_CHART' if dr is None else
                        'STARTER' if dr == 1 else 'BACKUP'),
                    'opportunity_metric': OPP_OF_LAYER[lay],
                    'p_participate_model': (None if p_m is None
                                            else round(p_m, 6)),
                    'opportunity_actual': opp_a,
                    'opportunity_actual_basis': opp_a_basis,
                    'participated_actual': (None if opp_a is None
                                            else int(opp_a > 0)),
                    'model_mean_conditional_on_participation': (
                        None if cond is None else round(cond, 4)),
                    'p_metric_nonzero_model': round(float((v > 0).mean()), 6),
                    'injury_state': istate,
                    'on_official_inactive_list': (
                        None if ina is None else int(pid in ina)),
                    'injury_report_status': st or '',
                    'season_boundary': int(bool(openers.get(r['team'], False))),
                    'n_own_prior_games': n_own,
                    'prior_history_bucket': history_bucket(n_own),
                    'prior_history_basis': hk,
                    'sq_error': round(e * e, 6),
                })
                rows.append(r)
    if not rows:
        raise SystemExit(
            'D7_EMPTY_RESULT: no row was scored. An empty result is an error, '
            f'not a finding. seals={[s.get("status") for s in seals]} '
            f'skipped={[s.get("status") for s in skipped]}')
    return {'rows': rows, 'seals': seals, 'skipped': skipped,
            'prior_history_provenance': nown_prov,
            'outcome': {'blob': str(o.evidence['blob']), 'sha256': outcome_sha,
                        'n_pbp_rows': len(allrows)},
            'injury_provenance': inj_prov,
            'inactives_provenance': inact_prov,
            'season_openers': openers}


# -------------------------------------------------------------- aggregation
def agg(rows, unit_mixed=None):
    """Descriptive cell. No adequacy word. Cluster counts always present."""
    if not rows:
        return None
    e = np.array([r['forecast_minus_actual'] for r in rows], float)
    a = np.array([r['abs_error'] for r in rows], float)
    y = np.array([r['actual'] for r in rows], float)
    mu = np.array([r['model_mean'] for r in rows], float)
    md = np.array([r['model_median'] for r in rows], float)
    g_lab = [r['game_id'] for r in rows]
    pg_lab = [(r['game_id'], r['gsis_id']) for r in rows]
    se_g = SDR._cluster_se(e, g_lab)
    se_pg = SDR._cluster_se(e, pg_lab)
    metrics = sorted({r['metric'] for r in rows})
    mixed = len(metrics) > 1 if unit_mixed is None else unit_mixed

    # ---------------------------------------------------- THE DECOMPOSITION
    # EXACT, NOT APPROXIMATE, AND THE DIFFERENCE MATTERS.
    #
    # Row-wise the model satisfies mu_i = p_i * c_i exactly, because a draw
    # with zero opportunity contributes zero to a count or to a sum over
    # events. That identity is CHECKED below, not assumed.
    #
    # Aggregating it, the mean of a product is not the product of the means,
    # so the stratum's conditional projection is the PARTICIPATION-WEIGHTED
    # one, C_M = mean(mu) / mean(p). With C_A = mean(y) / P_A on the realised
    # side -- also an identity, since a non-participant contributes 0 -- the
    # bias splits without residual:
    #
    #     bias = P_M*C_M - P_A*C_A = (P_M - P_A)*C_M + P_A*(C_M - C_A)
    #
    # The first term is the bias the engine would have if its conditional
    # volume were right and only its participation were wrong; the second is
    # the reverse. They sum to the bias exactly, and the residual is reported
    # so a reader can see that they do.
    #
    # C_A IS CONDITIONED ON THE OUTCOME. It averages realised values over the
    # players who actually participated, which is a set the outcome chose. It
    # is a decomposition term, not a measurement of a forecast, and the
    # participation term beside it is where the outcome-free comparison lives:
    # P_M against P_A uses every forecast row in the stratum.
    have = [r for r in rows
            if r['p_participate_model'] is not None
            and r['participated_actual'] is not None]
    P_M = P_A = C_M = C_A = part_term = cond_term = resid = None
    max_identity_gap = None
    if len(have) == len(rows) and rows:
        p_i = np.array([r['p_participate_model'] for r in rows], float)
        c_i = np.array([(r['model_mean_conditional_on_participation']
                         if r['model_mean_conditional_on_participation']
                         is not None else 0.0) for r in rows], float)
        max_identity_gap = round(float(np.max(np.abs(mu - p_i * c_i))), 6)
        P_M = float(p_i.mean())
        P_A = float(np.mean([r['participated_actual'] for r in rows]))
        C_M = float(mu.mean() / P_M) if P_M else None
        C_A = float(y.mean() / P_A) if P_A else None
        if None not in (C_M, C_A):
            part_term = (P_M - P_A) * C_M
            cond_term = P_A * (C_M - C_A)
            resid = float(e.mean()) - (part_term + cond_term)

    out = {
        'n_rows': len(rows),
        'n_game_clusters': len(set(g_lab)),
        'n_player_game_clusters': len(set(pg_lab)),
        'n_players': len({r['gsis_id'] for r in rows}),
        'unit_mixed': bool(mixed),
        'metrics_in_cell': metrics if mixed else metrics[0],
        'projected_mean': round(float(mu.mean()), 4),
        'projected_median_mean': round(float(md.mean()), 4),
        'actual_mean': round(float(y.mean()), 4),
        'bias': round(float(e.mean()), 4),
        'mae': round(float(a.mean()), 4),
        'rmse': round(float(np.sqrt((e ** 2).mean())), 4),
        'se_bias_game_clustered': (round(se_g, 4) if se_g is not None
                                   else None),
        'z_bias_game_clustered': (round(float(e.mean() / se_g), 3)
                                  if se_g else None),
        'p_two_sided_t_G_minus_1': (
            round(t_two_sided(e.mean() / se_g, len(set(g_lab)) - 1), 4)
            if se_g else None),
        'reference_distribution_note': (
            'the z is a cluster-robust ratio, not a standard normal deviate '
            'at this cluster count. p_two_sided_t_G_minus_1 is the t(G-1) '
            'tail and is the weaker, and here the more defensible, reference.'),
        'se_bias_player_game_clustered': (round(se_pg, 4)
                                          if se_pg is not None else None),
        'player_game_clustering_degenerate': len(set(pg_lab)) == len(rows),
        'p_participate_model_mean': (round(P_M, 4) if P_M is not None
                                     else None),
        'participation_rate_actual': (round(P_A, 4) if P_A is not None
                                      else None),
        'participation_gap_model_minus_actual': (
            round(P_M - P_A, 4) if None not in (P_M, P_A) else None),
        'n_participated_actual': int(sum(
            1 for r in rows if r.get('participated_actual'))),
        'conditional_projection_model': (round(C_M, 4) if C_M is not None
                                         else None),
        'conditional_actual_among_participants': (
            round(C_A, 4) if C_A is not None else None),
        'conditional_actual_is_outcome_conditioned': True,
        'bias_from_participation': (round(part_term, 4)
                                    if part_term is not None else None),
        'bias_from_conditional_volume': (round(cond_term, 4)
                                         if cond_term is not None else None),
        'decomposition_residual': (round(resid, 8) if resid is not None
                                   else None),
        'mu_equals_p_times_c_max_abs_gap': max_identity_gap,
        'coverage_50': round(float(np.mean([r['in_50'] for r in rows])), 4),
        'coverage_80': round(float(np.mean([r['in_80'] for r in rows])), 4),
        'coverage_90': round(float(np.mean([r['in_90'] for r in rows])), 4),
        'n_model_above_actual': int((e > 0).sum()),
        'n_model_below_actual': int((e < 0).sum()),
        'n_zero_by_completion': sum(
            1 for r in rows if r.get('actual_basis') == 'ZERO_BY_COMPLETION'),
    }
    if out['unit_mixed']:
        out['unit_mixed_warning'] = (
            'this cell averages estimands measured in different units '
            '(yards with counts). bias, mae and rmse here are arithmetic on '
            'incommensurable quantities and are NOT interpretable as an '
            'error magnitude. Read the per-(position, metric) cells.')
    if out['n_game_clusters'] < 5:
        out['thin'] = (f"{out['n_game_clusters']} game cluster(s): below the "
                       f"point where a clustered SE means anything. No claim "
                       f"may rest on this cell.")
    z = out['z_bias_game_clustered']
    if z is not None and abs(z) > 10 and out['n_game_clusters'] < 20:
        # A CLUSTER-ROBUST SE COLLAPSES WHEN EVERY CLUSTER SAYS THE SAME THING.
        # The CRVE measures BETWEEN-cluster spread of the cluster totals. When
        # a stratum contains, say, players who were all projected some volume
        # and all recorded exactly zero, each game contributes nearly the same
        # per-row error, the between-cluster spread goes to zero and the ratio
        # explodes. The huge z is then an artefact of a near-deterministic gap
        # on a handful of clusters, not precision. The BIAS is the number to
        # read in such a cell; the z is not a test statistic.
        out['se_collapsed'] = (
            f'|z| = {abs(z):.1f} on {out["n_game_clusters"]} clusters: the '
            f'between-cluster spread has collapsed because every cluster '
            f'shows almost the same gap. Read the bias, not the z or the p.')
    if out['player_game_clustering_degenerate']:
        out['player_game_clustering_note'] = (
            'one row per player-game here, so the player-game SE IS the naive '
            'SE. Read the game-clustered figure.')
    return out


def t_two_sided(z, df):
    """Two-sided tail of Student t, computed here so no reference is guessed.

    WHY IT IS REPORTED BESIDE EVERY z. A cluster-robust z is only standard
    normal as the number of CLUSTERS grows. At G = 5 or G = 9 it is not, and
    the small-cluster reference commonly used is t(G-1). The two disagree by
    an order of magnitude on this frame -- the carries figure is p = 0.0007
    against a normal and p = 0.0275 against t(4) -- so quoting the normal tail
    alone would overstate every result in this artifact. Neither is a licence
    to say a cell is adequate: no equivalence margin was predeclared.
    """
    if z is None or df is None or df < 1:
        return None
    x = df / (df + float(z) * float(z))

    def betacf(a, b, x):
        maxit, eps, fpmin = 300, 3e-16, 1e-300
        qab, qap, qam = a + b, a + 1.0, a - 1.0
        c, d = 1.0, 1.0 - qab * x / qap
        if abs(d) < fpmin:
            d = fpmin
        d = 1.0 / d
        h = d
        for m in range(1, maxit + 1):
            m2 = 2 * m
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1.0 + aa * d
            if abs(d) < fpmin:
                d = fpmin
            c = 1.0 + aa / c
            if abs(c) < fpmin:
                c = fpmin
            d = 1.0 / d
            h *= d * c
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1.0 + aa * d
            if abs(d) < fpmin:
                d = fpmin
            c = 1.0 + aa / c
            if abs(c) < fpmin:
                c = fpmin
            d = 1.0 / d
            de = d * c
            h *= de
            if abs(de - 1.0) < eps:
                break
        return h

    def betai(a, b, x):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        import math
        bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log(1 - x))
        if x < (a + 1) / (a + b + 2):
            return bt * betacf(a, b, x) / a
        return 1.0 - bt * betacf(b, a, 1 - x) / b

    return float(betai(df / 2.0, 0.5, x))


def by(rows, keyfn, unit_mixed=None):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyfn(r)].append(r)
    return {str(k): agg(v, unit_mixed)
            for k, v in sorted(g.items(), key=lambda kv: str(kv[0]))}


def participation_calibration(rows, layer):
    """Forecast participation probability against the realised rate.

    OUTCOME-FREE ON THE SELECTION SIDE: every forecast row in the layer enters
    a bin, and the bin is chosen by the FORECAST's own probability. What is
    compared is how often the players in a bin actually took the field's
    opportunity. One row per player-layer, not per metric, so a quarterback
    does not enter seven times.
    """
    seen, pts = set(), []
    for r in rows:
        if r['layer'] != layer:
            continue
        k = (r['game_id'], r['seal_rank'], r['gsis_id'])
        if k in seen or r['p_participate_model'] is None:
            continue
        if r['participated_actual'] is None:
            continue
        seen.add(k)
        pts.append(r)
    if not pts:
        return None
    edges = [0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0001]
    labs = ['[0,0.05)', '[0.05,0.25)', '[0.25,0.5)', '[0.5,0.75)',
            '[0.75,0.95)', '[0.95,1]']
    out = {'layer': layer, 'opportunity_metric': OPP_OF_LAYER[layer],
           'unit': 'one row per player-game-seal', 'bins': {}}
    for i, lab in enumerate(labs):
        sel = [r for r in pts
               if edges[i] <= r['p_participate_model'] < edges[i + 1]]
        if not sel:
            continue
        pm = np.array([r['p_participate_model'] for r in sel], float)
        pa = np.array([float(r['participated_actual']) for r in sel], float)
        se = SDR._cluster_se(pm - pa, [r['game_id'] for r in sel])
        out['bins'][lab] = {
            'n': len(sel),
            'n_game_clusters': len({r['game_id'] for r in sel}),
            'mean_forecast_p': round(float(pm.mean()), 4),
            'realised_rate': round(float(pa.mean()), 4),
            'gap_model_minus_actual': round(float((pm - pa).mean()), 4),
            'se_gap_game_clustered': round(se, 4) if se is not None else None,
            'z_gap_game_clustered': (round(float((pm - pa).mean() / se), 3)
                                     if se else None),
        }
    return out


def qb_room_concentration(rows):
    """How much of a club's dropback mass the engine puts on its top passer.

    GROUPED BY (game_id, posteam), never by game: the two clubs in a game have
    separate rooms and pooling them would invent a 16-quarterback room.

    The model side is the share of the club's SUMMED projected dropbacks held
    by its largest projection -- the engine's own claim about concentration,
    computed from the same means it published. The realised side is the same
    ratio on realised dropbacks. Both are shares, so they are directly
    comparable with the historical figure in d7_boundary_outcome.py.

    A share is undefined when the denominator is zero; such a club is counted
    and excluded by name rather than scored as 0 or 1.
    """
    by = collections.defaultdict(list)
    for r in rows:
        if r['metric'] == 'qb/db':
            by[(r['game_id'], r['team'])].append(r)
    m_sh, a_sh, m5, a5, per = [], [], [], [], []
    undefined = []
    for key, v in sorted(by.items()):
        m = [float(x['model_mean']) for x in v]
        a = [float(x['actual']) for x in v]
        e = {'game_id': key[0], 'posteam': key[1], 'n_qbs_on_board': len(v),
             'model_sum_dropbacks': round(sum(m), 3),
             'actual_sum_dropbacks': round(sum(a), 3)}
        if sum(m) > 0:
            e['model_top_passer_share'] = round(max(m) / sum(m), 4)
            m_sh.append(max(m) / sum(m))
            m5.append(sum(1 for x in m if x >= 5))
        else:
            undefined.append({'unit': key, 'side': 'model'})
        if sum(a) > 0:
            e['actual_top_passer_share'] = round(max(a) / sum(a), 4)
            a_sh.append(max(a) / sum(a))
            a5.append(sum(1 for x in a if x >= 5))
        else:
            undefined.append({'unit': key, 'side': 'actual'})
        per.append(e)
    if not m_sh or not a_sh:
        return {'status': 'NO_QB_DB_ROWS'}
    return {
        'unit': '(game_id, posteam)',
        'n_team_games': len(per),
        'n_game_clusters': len({k[0] for k in by}),
        'model_mean_top_passer_share': round(float(np.mean(m_sh)), 4),
        'actual_mean_top_passer_share': round(float(np.mean(a_sh)), 4),
        'model_mean_n_qbs_with_5plus': round(float(np.mean(m5)), 4),
        'actual_mean_n_qbs_with_5plus': round(float(np.mean(a5)), 4),
        'model_share_of_team_games_with_2plus_qbs_at_5plus': round(
            float(np.mean([x >= 2 for x in m5])), 4),
        'actual_share_of_team_games_with_2plus_qbs_at_5plus': round(
            float(np.mean([x >= 2 for x in a5])), 4),
        'undefined_shares': undefined,
        'per_team_game': per,
        'reading': ('this is a DESCRIPTION of one week of boards against one '
                    'week of outcomes on 9 game clusters. It is not a test '
                    'and no equivalence margin was predeclared.'),
    }


def paired_pre_post(rows):
    """Within-game PRE-inactives vs POST-inactives, on the SAME player-metrics.

    The information set differs; the game does not. A between-game comparison
    of the two stages would be confounded by which games happened to carry a
    post-inactives seal, and in this frame that confound is total -- the four
    quarterback-only games are not the same games as the five that carry a
    receiving layer. So only games holding BOTH a pregame PRE seal and a
    pregame POST seal enter, and only rows present in both.
    """
    per = collections.defaultdict(dict)
    for r in rows:
        st = r['forecast_stage']
        if st not in ('PRE_INACTIVES', 'POST_INACTIVES_FINAL'):
            continue
        g = r['game_id']
        cur = per[g].get(st)
        if cur is None or r['seal_rank'] > cur:
            per[g][st] = r['seal_rank']
    games = sorted(g for g, d in per.items() if len(d) == 2)
    if not games:
        return {'status': 'NO_GAME_CARRIES_BOTH_STAGES_PREGAME'}
    idx = {}
    for r in rows:
        g = r['game_id']
        if g not in games:
            continue
        if r['seal_rank'] != per[g].get(r['forecast_stage']):
            continue
        idx[(g, r['gsis_id'], r['metric'], r['forecast_stage'])] = r
    keys = {(g, p, m) for (g, p, m, st) in idx}
    pairs = [(idx[(g, p, m, 'PRE_INACTIVES')],
              idx[(g, p, m, 'POST_INACTIVES_FINAL')])
             for (g, p, m) in sorted(keys)
             if (g, p, m, 'PRE_INACTIVES') in idx
             and (g, p, m, 'POST_INACTIVES_FINAL') in idx]
    if not pairs:
        return {'status': 'NO_MATCHED_ROWS_ACROSS_STAGES', 'games': games}
    pre_only = sorted(k for k in keys
                      if (k[0], k[1], k[2], 'PRE_INACTIVES') in idx
                      and (k[0], k[1], k[2], 'POST_INACTIVES_FINAL') not in idx)
    post_only = sorted(k for k in keys
                       if (k[0], k[1], k[2], 'POST_INACTIVES_FINAL') in idx
                       and (k[0], k[1], k[2], 'PRE_INACTIVES') not in idx)
    out = {'games': games, 'n_game_clusters': len(games),
           'n_matched_rows': len(pairs),
           'n_pre_only_rows': len(pre_only),
           'n_post_only_rows': len(post_only),
           'unmatched_warning': (
               'THE MATCHED SET IS THE SURVIVORS. A player the inactive list '
               'removed from the post-inactives board has no post row and so '
               'cannot be paired; a player added has no pre row. The paired '
               'change therefore measures what the new information did to the '
               'players who stayed, and says nothing about the players whose '
               'presence in the pool the information CHANGED -- which is most '
               'of what an inactive list is for. n_pre_only_rows and '
               'n_post_only_rows size that blind spot.'),
           'thin': (f'{len(games)} game clusters. This contrast cannot '
                    f'support a claim; it is reported so the direction is on '
                    f'the record.'),
           'by_metric': {}}
    bym = collections.defaultdict(list)
    for a_, b_ in pairs:
        bym[a_['metric']].append((a_, b_))
    for m, ps in sorted(bym.items()):
        d = np.array([b_['forecast_minus_actual'] - a_['forecast_minus_actual']
                      for a_, b_ in ps], float)
        se = SDR._cluster_se(d, [a_['game_id'] for a_, b_ in ps])
        out['by_metric'][m] = {
            'n': len(ps),
            'n_game_clusters': len({a_['game_id'] for a_, b_ in ps}),
            'bias_pre': round(float(np.mean(
                [a_['forecast_minus_actual'] for a_, b_ in ps])), 4),
            'bias_post': round(float(np.mean(
                [b_['forecast_minus_actual'] for a_, b_ in ps])), 4),
            'mae_pre': round(float(np.mean(
                [a_['abs_error'] for a_, b_ in ps])), 4),
            'mae_post': round(float(np.mean(
                [b_['abs_error'] for a_, b_ in ps])), 4),
            'mean_paired_change_in_signed_error': round(float(d.mean()), 4),
            'se_paired_change_game_clustered': (round(se, 4)
                                                if se is not None else None),
            'z_paired_change_game_clustered': (
                round(float(d.mean() / se), 3) if se else None),
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='D7 central-tendency diagnostic')
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--games', required=True)
    ap.add_argument('--outcome-blob', required=True)
    ap.add_argument('--seal', default='last', choices=('first', 'last', 'all'))
    ap.add_argument('--out-csv', required=True)
    ap.add_argument('--out-json', required=True)
    a = ap.parse_args(argv)

    # BUILT ONCE WITH EVERY PREGAME SEAL, then the primary frame is DERIVED
    # from it, so the paired stage contrast and the headline table cannot come
    # from two different reads of the same bytes.
    b = build(a.season, a.games.split(','), a.outcome_blob, 'all')
    allrows = b['rows']
    last_rank = {}
    for r in allrows:
        g = r['game_id']
        if g not in last_rank or r['seal_rank'] > last_rank[g]:
            last_rank[g] = r['seal_rank']
    first_rank = {}
    for r in allrows:
        g = r['game_id']
        if g not in first_rank or r['seal_rank'] < first_rank[g]:
            first_rank[g] = r['seal_rank']
    pick = (last_rank if a.seal == 'last'
            else first_rank if a.seal == 'first' else None)
    rows = (allrows if pick is None
            else [r for r in allrows if r['seal_rank'] == pick[r['game_id']]])
    if not rows:
        raise SystemExit('D7_PRIMARY_FRAME_EMPTY: seal selection kept nothing.')

    cols = list(SDR.COLUMNS) + [
        'season', 'week', 'seal_rank', 'seal_dir', 'depth_chart',
        'depth_rank', 'starter_or_backup', 'opportunity_metric',
        'p_participate_model', 'opportunity_actual',
        'opportunity_actual_basis', 'participated_actual',
        'model_mean_conditional_on_participation', 'p_metric_nonzero_model',
        'injury_state', 'on_official_inactive_list', 'injury_report_status',
        'season_boundary', 'n_own_prior_games', 'prior_history_bucket',
        'prior_history_basis', 'sq_error']
    missing = sorted({c for c in cols if c not in rows[0]})
    if missing:
        raise SystemExit(f'D7_SCHEMA_INCOMPLETE: {missing}')
    p = pathlib.Path(a.out_csv)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in cols})

    summary = {
        'artifact': 'D7_CENTRAL_TENDENCY_SCORECARD',
        'spec_version': SPEC_VERSION,
        'governance': NOT_EVIDENCE,
        'scorer': {'module': 'nfl/research/same_day_retrospective.py',
                   'spec_version': SDR.SPEC_VERSION,
                   'outcome_selection_basis': SDR.SELECTION_COMPLETE,
                   'reused': ['resolve_realised', 'score_seal', 'role_tiers',
                              '_cluster_se']},
        'outcome_source': b['outcome'],
        'injury_provenance': b['injury_provenance'],
        'prior_history_provenance': b['prior_history_provenance'],
        'inactives_provenance': b['inactives_provenance'],
        'seal_selection': a.seal,
        'seals_used': b['seals'],
        'games_skipped': b['skipped'],
        'n_rows': len(rows),
        'n_game_clusters': len({r['game_id'] for r in rows}),
        'n_player_game_clusters': len({(r['game_id'], r['gsis_id'])
                                       for r in rows}),
        'season_boundary_census': dict(collections.Counter(
            r['season_boundary'] for r in rows)),
        'season_openers': b['season_openers'],
        'overall_UNIT_MIXED': agg(rows, unit_mixed=True),
        'by_position_metric': by(rows, lambda r: (r['position'], r['metric'])),
        'by_metric': by(rows, lambda r: r['metric']),
        'by_position_UNIT_MIXED': by(rows, lambda r: r['position'],
                                     unit_mixed=True),
        'by_starter_backup_metric': by(
            rows, lambda r: (r['starter_or_backup'], r['metric'])),
        'by_role_tier_metric': by(rows,
                                  lambda r: (r['role_tier'], r['metric'])),
        'by_week_UNIT_MIXED': by(rows, lambda r: r['week'], unit_mixed=True),
        'by_season_boundary_metric': by(
            rows, lambda r: (r['season_boundary'], r['metric'])),
        'by_injury_state_metric': by(
            rows, lambda r: (r['injury_state'], r['metric'])),
        'by_injury_state_UNIT_MIXED': by(rows, lambda r: r['injury_state'],
                                         unit_mixed=True),
        'by_forecast_stage_metric': by(
            rows, lambda r: (r['forecast_stage'], r['metric'])),
        'by_actual_basis_metric': by(
            rows, lambda r: (r['actual_basis'], r['metric'])),
        'by_depth_rank_metric': by(
            rows, lambda r: (r['depth_rank'], r['metric'])),
        'by_injury_report_status_metric': by(
            rows, lambda r: (r['injury_report_status'] or 'NOT_ON_REPORT',
                             r['metric'])),
        'by_prior_history_metric': by(
            rows, lambda r: (r['prior_history_bucket'], r['metric'])),
        'by_prior_history_depth_rank_opportunity_only': by(
            [r for r in rows if r['metric'] in OPP_OF_LAYER.values()],
            lambda r: (r['prior_history_bucket'], r['starter_or_backup'],
                       r['metric'])),
        'qb_room_concentration': qb_room_concentration(rows),
        'participation_calibration': {
            lay: participation_calibration(rows, lay)
            for lay in ('qb', 'receiving', 'rushing')},
        'paired_pre_post_within_game': paired_pre_post(allrows),
        'what_cannot_be_concluded': [
            'THIS IS NOT A PROMOTION TEST. Nothing here may be used to tune, '
            'promote, adjust or select any layer, threshold or constant.',
            'One week is not a sample. The largest cell rests on 9 game '
            'clusters and the non-quarterback cells on 5.',
            'No equivalence margin was predeclared and no two-one-sided test '
            'was run, so no cell here supports the words unbiased, stable, '
            'closed or correct -- including the cells whose z is small.',
            'Every game in this frame is a season opener, so the '
            'season-boundary contrast is NOT IDENTIFIED: the non-boundary '
            'stratum is empty and no comparison exists to make.',
            'conditional_actual_among_participants conditions on the '
            'outcome. It is a decomposition term, not a forecast score.',
            'PIT is carried by the upstream scorer and is not interpretable '
            '(one shared uniform per run); it is not used here.',
            'A forecast that was wrong in week 1 is not thereby a defect, and '
            'one that was right is not thereby correct.'],
    }
    j = pathlib.Path(a.out_json)
    j.parent.mkdir(parents=True, exist_ok=True)
    j.write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(f'{len(rows)} rows -> {p}')
    print(f'summary -> {j}')
    ov = summary['overall_UNIT_MIXED']
    print(f"games={ov['n_game_clusters']} players={ov['n_players']} "
          f"rows={ov['n_rows']} zero_by_completion={ov['n_zero_by_completion']}")
    print(f"skipped: {[(s['game_id'], s['status']) for s in b['skipped']]}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
