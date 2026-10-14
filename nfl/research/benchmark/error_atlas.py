"""FORECAST_ERROR_ATLAS (mandate b0540a52 phase 2), DEVELOPMENT SEASON 2024 ONLY.

    python3.12 nfl/research/benchmark/error_atlas.py > nfl/research/benchmark/FORECAST_ERROR_ATLAS.json

Production settings (STRICT vintage, appearance ON, D1 off). Cohorts are defined at the cutoff (the allocation pool and
the projection), never by the outcome, EXCEPT the explicitly labelled conditional components (production given an
appearance), which are the standard decomposition E[pts] = P(appear) x E[pts | appear] and are scored as such.

Sections
  appearance    P(appear) forecast (the allocator's p_plays) vs the naive appearance rate, against whether he
                appeared: Brier, log loss, calibration by forecast decile. Pool cohort.
  team_volume   per club-week: projected club targets / carries / pass attempts (sum over the pool, as allocated) vs
                the realised club totals.
  share         per player who played: projected share of his club's projected targets vs realised share.
  efficiency    per position, given play: catch rate, yards per target / carry, TDs per opportunity.
  cold_start    players with fewer than 2 prior appearances this season vs the rest.
  cases         the 20 largest top-decile over-projections given play (receivers), with their components.
2025 is not read."""
import collections
import json
import math
import statistics
import sys

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402

F.VINTAGE[0], F.APPLY_APPEARANCE[0], F.D1_W[0] = 'STRICT', True, None
F.PER_PLAYER_SINK, F.PER_PLAYER_SINK_DFS, F.PROJ_COMPONENT_SINK = [], [], []
po = P.load_panel()
panel, pos_of = po.value, P.position_index()
F.evaluate(panel, pos_of, [2024], [('PROD', 1.0, None)])
comp = {(r['season'], r['week'], r['gsis']): r for r in F.PROJ_COMPONENT_SINK}
unc = [(s, wk, g, pos, pr, a, ap, c) for (s, wk, _l, g, pos, pr, a, ap, c) in F.PER_PLAYER_SINK_DFS]
names = {}
for nm, d in P.name_index().items():
    for g in d:
        names.setdefault(g, nm)


def wk_rows(g, s, w):
    return ((panel['players'].get(g) or {}).get(str(s)) or {}).get(str(w)) or {}


# ------------------------------------------------------------------ appearance
def p_appear(c):
    pp = (c or {}).get('p_plays') or {}
    v = [x for x in pp.values() if isinstance(x, (int, float))]
    return max(v) if v else None


club_weeks = collections.defaultdict(set)
for g, ss in panel['players'].items():
    for s, ws in ss.items():
        for w, r in ws.items():
            if r.get('team'):
                club_weeks[(r['team'], int(s))].add(int(w))


def naive_rate(g, s, wk, club):
    n = sum(1 for w, r in ((panel['players'].get(g) or {}).get(str(s)) or {}).items() if int(w) < wk and r.get('team'))
    played = len([w for w in club_weeks[(club, s)] if w < wk])
    return (n / played) if played else None


def in_last_club_game(g, s, wk, club):
    prev = [w for w in club_weeks[(club, s)] if w < wk]
    if not prev:
        return None
    r = ((panel['players'].get(g) or {}).get(str(s)) or {}).get(str(max(prev))) or {}
    return bool(r.get('team'))


ap_rows = []
for (s, wk, g, pos, pr, a, ap, club) in unc:
    p = p_appear(comp.get((s, wk, g)))
    q = naive_rate(g, s, wk, club)
    if p is not None and q is not None:
        ap_rows.append((min(max(p, 1e-6), 1 - 1e-6), min(max(q, 1e-6), 1 - 1e-6), 1.0 if ap else 0.0, pos,
                        in_last_club_game(g, s, wk, club)))


def brier(rows, i):
    return round(statistics.fmean((r[i] - r[2]) ** 2 for r in rows), 5)


def logloss(rows, i, eps=1e-6):
    cl = lambda x: min(max(x, eps), 1 - eps)  # noqa: E731
    return round(-statistics.fmean(r[2] * math.log(cl(r[i])) + (1 - r[2]) * math.log(1 - cl(r[i])) for r in rows), 5)


def calib(rows, i):
    srt = sorted(rows, key=lambda r: r[i]); n = len(srt); out = {}
    for k in range(10):
        seg = srt[k * n // 10:(k + 1) * n // 10]
        if seg:
            out[f'D{k + 1}'] = {'n': len(seg), 'mean_forecast': round(statistics.fmean(r[i] for r in seg), 3),
                               'observed_rate': round(statistics.fmean(r[2] for r in seg), 3)}
    return out


_base = statistics.fmean(r[2] for r in ap_rows)
appearance = {'n': len(ap_rows), 'base_rate': round(_base, 4),
              'REFERENCE_constant_base_rate_brier': round(_base * (1 - _base), 5),
              'REFERENCE_NOTE': 'brier of forecasting the in-sample base rate for everyone; in-sample, so a reference, not an arm',
              'share_of_rows_incumbent_p_plays_eq_1': round(statistics.fmean(1.0 if r[0] >= 1 - 1e-6 else 0.0 for r in ap_rows), 4),
              'LOG_LOSS_NOTE': 'log_loss clips at 1e-6, so a p=1 forecast for an absent player costs 13.8 nats; log_loss_clip_0_01 clips at 0.01',
              'incumbent_p_plays': {'brier': brier(ap_rows, 0), 'log_loss': logloss(ap_rows, 0),
                                    'log_loss_clip_0_01': logloss(ap_rows, 0, 0.01), 'calibration': calib(ap_rows, 0)},
              'naive_rate_before_W': {'brier': brier(ap_rows, 1), 'log_loss': logloss(ap_rows, 1),
                                      'log_loss_clip_0_01': logloss(ap_rows, 1, 0.01), 'calibration': calib(ap_rows, 1)},
              'WHAT_P_PLAYS_IS': ('proj_v1.depth_shares appearance_rate = share of club-weeks in which the club had at least k '
                                  'players with volume at the position (a SLOT occupancy rate, ranks taken from realised '
                                  'volume order); allocate_opportunity assigns it to the player predicted at rank k as his '
                                  'own P(plays). The two coincide only if the predicted rank-k player is always the one who '
                                  'fills slot k.'),
              'by_position': {p: {'n': len(v), 'brier_incumbent': brier(v, 0), 'brier_naive': brier(v, 1)}
                              for p, v in ((p, [r for r in ap_rows if r[3] == p]) for p in ('QB', 'RB', 'WR', 'TE')) if v},
              # PREDICTION-DEFINED: did he appear in his club's most recent game before W? A player who did not is the
              # one a roster capture (release, reserve list) most often removes in production; one who did is mostly
              # an active player, so the incumbent's error there is not a harness artefact of the missing news.
              'by_appeared_in_last_club_game': {
                  str(k): {'n': len(v), 'observed_rate': round(statistics.fmean(r[2] for r in v), 4),
                           'brier_incumbent': brier(v, 0), 'brier_naive': brier(v, 1),
                           'mean_p_incumbent': round(statistics.fmean(r[0] for r in v), 4),
                           'mean_p_naive': round(statistics.fmean(r[1] for r in v), 4)}
                  for k, v in ((k, [r for r in ap_rows if r[4] is k]) for k in (True, False)) if v}}

# ------------------------------------------------------------------ team volume
proj_club = collections.defaultdict(lambda: collections.Counter())
for (s, wk, g), c in comp.items():
    for k in ('targets', 'carries', 'pass_attempts'):
        proj_club[(s, wk, c.get('club'))][k] += float(c.get(k) or 0.0)
act_club = collections.defaultdict(lambda: collections.Counter())
for g, ss in panel['players'].items():
    for w, r in (ss.get('2024') or {}).items():
        if r.get('team'):
            for k in ('targets', 'carries', 'pass_attempts'):
                act_club[(2024, int(w), r['team'])][k] += float(r.get(k) or 0.0)
tv = {}
for k in ('targets', 'carries', 'pass_attempts'):
    pairs = [(proj_club[key][k], act_club[key][k]) for key in proj_club if key in act_club and act_club[key][k] > 0]
    tv[k] = {'n_club_weeks': len(pairs), 'mean_projected': round(statistics.fmean(p for p, _ in pairs), 2),
             'mean_actual': round(statistics.fmean(a for _, a in pairs), 2),
             'ratio_of_sums': round(sum(p for p, _ in pairs) / sum(a for _, a in pairs), 4),
             'mae': round(statistics.fmean(abs(p - a) for p, a in pairs), 2)}

# ------------------------------------------------------------------ share, efficiency, cases (given play)
cond = [(s, wk, g, pos, pr, a) for (s, wk, _l, g, pos, pr, a) in F.PER_PLAYER_SINK]
srt = sorted(cond, key=lambda r: r[4]); top = set((r[0], r[1], r[2]) for r in srt[int(0.9 * len(srt)):])
share = {}
for pos in ('WR', 'TE', 'RB'):
    for lbl, keyset in (('top_decile', top), ('all', None)):
        ps, as_ = [], []
        for (s, wk, g, p_, pr, a) in cond:
            if p_ != pos or (keyset is not None and (s, wk, g) not in keyset):
                continue
            c = comp.get((s, wk, g)); w = wk_rows(g, s, wk)
            pt, at = proj_club[(s, wk, c.get('club'))]['targets'], act_club[(s, wk, w.get('team'))]['targets']
            if c and pt and at:
                ps.append((c.get('targets') or 0) / pt); as_.append((w.get('targets') or 0) / at)
        if ps:
            share[f'{pos}_{lbl}'] = {'n': len(ps), 'mean_projected_target_share': round(statistics.fmean(ps), 4),
                                     'mean_actual_target_share': round(statistics.fmean(as_), 4),
                                     'ratio': round(sum(ps) / sum(as_), 4)}
eff = {}
for pos in ('WR', 'TE', 'RB', 'QB'):
    seg = [(comp.get((s, wk, g)), wk_rows(g, s, wk)) for (s, wk, g, p_, pr, a) in cond if p_ == pos and comp.get((s, wk, g))]
    sp = lambda k: sum(float(c.get(k) or 0) for c, _ in seg)  # noqa: E731
    sa = lambda k: sum(float(w.get(k) or 0) for _, w in seg)  # noqa: E731
    e = {'n': len(seg)}
    if sp('targets') and sa('targets'):
        e.update(catch_rate=[round(sp('receptions') / sp('targets'), 4), round(sa('receptions') / sa('targets'), 4)],
                 yards_per_target=[round(sp('rec_yards') / sp('targets'), 3), round(sa('rec_yards') / sa('targets'), 3)],
                 rec_td_per_target=[round(sp('rec_td') / sp('targets'), 4), round(sa('rec_td') / sa('targets'), 4)])
    if sp('carries') and sa('carries'):
        e.update(yards_per_carry=[round(sp('rush_yards') / sp('carries'), 3), round(sa('rush_yards') / sa('carries'), 3)],
                 rush_td_per_carry=[round(sp('rush_td') / sp('carries'), 4), round(sa('rush_td') / sa('carries'), 4)])
    if pos == 'QB' and sp('pass_attempts') and sa('pass_attempts'):
        e.update(yards_per_attempt=[round(sp('pass_yards') / sp('pass_attempts'), 3), round(sa('pass_yards') / sa('pass_attempts'), 3)],
                 pass_td_per_attempt=[round(sp('pass_td') / sp('pass_attempts'), 4), round(sa('pass_td') / sa('pass_attempts'), 4)])
    e['FORMAT'] = '[projected, actual], ratio of sums given play'
    eff[pos] = e


def prior_n(g, s, wk):
    return sum(1 for w, r in ((panel['players'].get(g) or {}).get(str(s)) or {}).items() if int(w) < wk and r.get('team'))


cold = {}
for lbl, f in (('cold_start_lt2_prior', lambda r: prior_n(r[2], r[0], r[1]) < 2), ('established', lambda r: prior_n(r[2], r[0], r[1]) >= 2)):
    seg = [r for r in unc if f(r)]
    if seg:
        cold[lbl] = {'n': len(seg), 'mae': round(statistics.fmean(abs(r[4] - r[5]) for r in seg), 4),
                     'bias': round(statistics.fmean(r[4] - r[5] for r in seg), 4)}
# DIAGNOSTIC ONLY (split on the outcome): where the unconditional absolute error sits
err_split = {}
for lbl, f in (('did_not_appear', lambda r: not r[6]), ('appeared', lambda r: bool(r[6]))):
    seg = [r for r in unc if f(r)]
    if seg:
        err_split[lbl] = {'n': len(seg), 'sum_abs_error': round(sum(abs(r[4] - r[5]) for r in seg), 1),
                          'mean_projection': round(statistics.fmean(r[4] for r in seg), 3)}
_tot = sum(v['sum_abs_error'] for v in err_split.values())
for v in err_split.values():
    v['share_of_total_abs_error'] = round(v['sum_abs_error'] / _tot, 4)
err_split['LABEL'] = 'DIAGNOSTIC: conditioned on the outcome; locates error, is not a score'
cases = []
for (s, wk, g, pos, pr, a) in cond:
    if (s, wk, g) in top and pos in ('WR', 'TE'):
        c, w = comp[(s, wk, g)], wk_rows(g, s, wk)
        cases.append({'player': names.get(g, g), 'week': wk, 'pos': pos, 'proj_pts': round(pr, 2), 'actual_pts': round(a, 2),
                      'proj_targets': round(float(c.get('targets') or 0), 2), 'actual_targets': w.get('targets'),
                      'proj_rec_yards': round(float(c.get('rec_yards') or 0), 1), 'actual_rec_yards': w.get('rec_yards'),
                      'p_plays': p_appear(c)})
cases = sorted(cases, key=lambda x: x['actual_pts'] - x['proj_pts'])[:20]
print(json.dumps({'artifact': 'FORECAST_ERROR_ATLAS', 'season': 2024, 'scope': 'DEVELOPMENT ONLY; production settings; 2025 not read',
                  'appearance': appearance, 'team_volume': tv, 'share': share, 'efficiency_given_play': eff,
                  'cold_start': cold, 'unconditional_error_by_appearance_DIAGNOSTIC': err_split, 'cases_top_decile_receivers_largest_overprojection': cases,
                  'UNSUPPORTED_FAMILIES': {'snaps_routes': 'no sourced per-game route or snap participation in the panel for 2024 (FTN participation is CC-BY-SA but injury-conditioning use unresolved)',
                                           'air_yards_redzone': 'air_yards / rz / gl present in the panel; not yet decomposed here',
                                           'injury_news': 'historical pregame designations withheld (RES-010)'}}, indent=1))
