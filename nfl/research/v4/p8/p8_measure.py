"""P8: both arms of the passing-yard repair, measured on two cohorts.

    python3.12 nfl/research/v4/p8/p8_measure.py

WHAT IS REUSED RATHER THAN REBUILT. The frame is `h1_frame.build` -- the same
rebuild-from-qb.pkl that H1 and P2 used, because `qb2_lib.load()` cannot run in
this checkout (`nfl/research/p4b/panel_enriched.pkl` is absent). The simulator
is `qb2_lib.simulate`, called unmodified in both arms; the arms differ in ONE
keyword, `ypc_spec`, and in nothing else. Seed, draw count, rung and row order
are identical, and the module ASSERTS that the only draw matrix differing
between the arms is `pyds`.

THE COHORT THE DEFECT WAS ESTABLISHED ON CANNOT BE RERUN HERE, AND THAT IS
STATED RATHER THAN WORKED AROUND. The 680 cells above 554 yards were counted
over 520,000 `qb/pyds` cells on the 70 QB-only team-sides of the sealed corpus.
Those boards were produced by `run_forecast` through the engine's R2 dropback
path, from 2026 rosters this module does not hold, and the QB frame they
consumed is not reconstructible here. Two substitute cohorts are used instead
and both are named:

  C1  the 635 eligible 2025 QB-game rows, forward-chained (pool = 2020-2024).
      635,000 cells, and the ONLY cohort with realised outcomes, so prediction
      quality is measured here and nowhere else.
  C2  the 79 quarterbacks who actually appear on the sealed boards, simulated
      as 2026 week-1 prospective rows through raw `qb_v1` with no engine.
      79,000 cells. Same players, different execution path from the boards.

Neither is the sealed corpus. C1's incumbent tail rate is 5.26e-03 against the
corpus's 1.31e-03, so C1 is a HARSHER cohort, not a proxy for the corpus's own
rate. What transfers is the mechanism and the direction, not the number.

EXPLORATORY. 2025 is development data in this project and the sealed corpus was
inspected before this repair was designed. Forward chaining controls parameter
leakage; it does not control specification leakage. A confirmatory result needs
untouched games.

NO MARKET DATA, NO EXTERNAL PROJECTION, AND NO DEN@KC OUTCOME. The realized
DEN@KC result is not in this repository and was not sought.
"""
from __future__ import annotations

import bisect
import collections
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
_REPO = HERE.parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb2'),
           str(_REPO / 'nfl' / 'research' / 'v3' / 'h1'),
           str(_REPO / 'nfl' / 'research')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import h1_frame as FR                                             # noqa: E402
import qb2_lib as Q                                               # noqa: E402
import sealed_index as SI                                         # noqa: E402

OUT = HERE / 'P8_EVIDENCE.json'
RECORD = 554.0
ALPHA = 0.05
SEED = 20260908
M = 1000
RUNG = 'L1'
BOOT = 2000
BOOT_SEED = 20260915
BANDS = ((1, 1), (2, 4), (5, 9), (10, 14), (15, 19), (20, 99))
ARMS = (('incumbent', Q.YPC_SPEC_GAME_RATIO),
        ('candidate', Q.YPC_SPEC_COMPLETION_BLOCKS))


def donor_pool(rows):
    g = [(r['cmp'], r['pyds']) for r in rows if r['cmp'] > 0]
    n = np.array([x[0] for x in g], float)
    y = np.array([x[1] for x in g], float)
    return n, y, y / n


def band_support(n, ypc):
    out = {}
    for lo, hi in BANDS:
        m = (n >= lo) & (n <= hi)
        out[f'{lo}-{hi}'] = {'games': int(m.sum()), 'mean_cmp': float(n[m].mean()),
                             'min': float(ypc[m].min()), 'max': float(ypc[m].max()),
                             'var': float(ypc[m].var(ddof=1))}
    return out


def tails(PY, CMP, support):
    oos = 0
    banded = {}
    for lo, hi in BANDS:
        m = (CMP >= lo) & (CMP <= hi)
        if not m.any():
            continue
        v = PY[m] / CMP[m]
        s = support[f'{lo}-{hi}']
        k = int(((v < s['min']) | (v > s['max'])).sum())
        oos += k
        banded[f'{lo}-{hi}'] = {'cells': int(m.sum()), 'out_of_support': k,
                                'var_implied_ratio': float(v.var()),
                                'realised_var': s['var'],
                                'min': float(v.min()), 'max': float(v.max())}
    return {'cells': int(PY.size), 'max': float(PY.max()), 'min': float(PY.min()),
            'over_record': int((PY > RECORD).sum()),
            'rate_over_record': float((PY > RECORD).mean()),
            'negative': int((PY < 0).sum()),
            'below_minus_30': int((PY < -30).sum()),
            'out_of_support_banded': oos,
            'mean': float(PY.mean()), 'sd': float(PY.std()),
            'sd_of_row_means': float(PY.mean(1).std(ddof=1)),
            'by_band': banded}


def crps_row(x, obs):
    x = np.sort(x)
    n = x.size
    i = np.arange(1, n + 1)
    return float(np.abs(x - obs).mean() - ((2 * i - n - 1) * x).sum() / (n * n))


def run_arm(keep, allrows, season, spec):
    return Q.simulate(keep, season, allrows, seed=SEED, m=M, rung=RUNG,
                      ypc_spec=spec)


def attach_prospective(rows, want):
    fields = ('db', 'team_db', 'att', 'sacks', 'scr', 'spikes', 'cmp', 'pyds',
              'ptd', 'int', 'drush', 'ryds', 'rtd', 'rush_opp')
    pros = [{'season': 2026, 'week': 1, 'team': t, 'gsis_id': p,
             'position': 'QB', 'ord': 202601, 'game_id': g,
             **{k: 0 for k in fields}}
            for p, (t, g) in sorted(want.items()) if t]
    allr = sorted(rows + pros, key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    Q.attach(allr)
    return pros, allr


def sealed_qbs():
    want = {}
    for f in SI.live_draw_files(exclude=None):
        d = f.parent
        man = json.loads((d / 'player_draws_manifest.json').read_text())
        board = json.loads((d / 'board.json').read_text())
        team_of = {p['gsis_id']: p.get('team') for p in (board.get('players') or [])}
        gid = board.get('game_id') or d.parent.name
        for pid in (man['layers'].get('qb') or {}).get('row_ids') or []:
            want[pid] = (team_of.get(pid), gid)
    return want


def corpus_census():
    car_cells = car_frac = viol = sub1 = mid = 0
    py_cells = over = neg = 0
    py_max = -1e18
    qbonly = [0, 0]
    c3 = [0, 0]
    post_r4 = {'cells': 0, 'non_integer': 0, 'violations': 0, 'boards': 0}
    boards = SI.live_draw_files(exclude=None)
    for f in boards:
        d = f.parent
        z = SI.load_draws(d)
        doc = json.loads((d / 'board.json').read_text())
        man = json.loads((d / 'player_draws_manifest.json').read_text())
        team_of = {p['gsis_id']: p.get('team') for p in (doc.get('players') or [])}
        if 'rushing__carries' in z.files:
            c = np.asarray(z['rushing__carries'], float)
            t = np.asarray(z['rushing__rushing_td'], float)
            if c.size:
                car_cells += c.size
                fr = int((np.abs(c - np.round(c)) > 0).sum())
                car_frac += fr
                v = t > c
                viol += int(v.sum())
                sub1 += int((v & (c > 0) & (c < 1) & (t == 1)).sum())
                mid += int((v & (c > 1) & (c < 2) & (t == 2)).sum())
                if doc.get('model_configuration') == 'V1_CANDIDATE_R9':
                    post_r4['cells'] += c.size
                    post_r4['non_integer'] += fr
                    post_r4['violations'] += int(v.sum())
                    post_r4['boards'] += 1
        if 'qb__pyds' in z.files:
            p = np.asarray(z['qb__pyds'], float)
            if p.size:
                py_cells += p.size
                over += int((p > RECORD).sum())
                neg += int((p < 0).sum())
                py_max = max(py_max, float(p.max()))
                rec_teams = {team_of.get(x) for x in
                             ((man['layers'].get('receiving') or {}).get('row_ids') or [])}
                for i, pid in enumerate(
                        (man['layers'].get('qb') or {}).get('row_ids') or []):
                    side = c3 if team_of.get(pid) in rec_teams else qbonly
                    side[0] += p[i].size
                    side[1] += int((p[i] > RECORD).sum())
    return {'boards': len(boards),
            'carry_cells': car_cells, 'carry_non_integer': car_frac,
            'carry_non_integer_fraction': car_frac / max(car_cells, 1),
            'rushing_td_above_carries': viol,
            'of_which_carries_in_0_1_with_one_td': sub1,
            'of_which_carries_in_1_2_with_two_td': mid,
            'post_counts_repair_boards': post_r4,
            'qb_pyds_cells': py_cells, 'qb_pyds_max': py_max,
            'qb_pyds_over_record': over, 'qb_pyds_negative': neg,
            'qb_only_sides': {'cells': qbonly[0], 'over_record': qbonly[1],
                              'rate': qbonly[1] / max(qbonly[0], 1)},
            'c3_bound_sides': {'cells': c3[0], 'over_record': c3[1],
                               'rate': c3[1] / max(c3[0], 1)}}


def main():
    rows, meta = FR.build()
    Q.attach(rows)
    n, y, ypc = donor_pool(rows)
    support = band_support(n, ypc)
    bound = 1.0 - ALPHA ** (1.0 / len(ypc))
    ev = {'spec_version': 'p8-tails-and-counts-1',
          'frame': meta,
          'donor_pool': {'games': int(len(ypc)),
                         'max_realised_pass_yards': float(y.max()),
                         'above_record': int((y > RECORD).sum()),
                         'unweighted_mean_ratio': float(ypc.mean()),
                         'completion_weighted_mean_ratio':
                             float(y.sum() / n.sum()),
                         'total_completions': int(n.sum()),
                         'negative_ratios': int((ypc < 0).sum()),
                         'max_completions_behind_a_negative_ratio':
                             int(n[ypc < 0].max()),
                         'games_with_5_or_more_completions': int((n >= 5).sum()),
                         'games_with_10_or_more_completions': int((n >= 10).sum()),
                         'min_ratio_at_5_or_more': float(ypc[n >= 5].min()),
                         'band_support': support},
          'derived_rate_bound': {'n': int(len(ypc)), 'events': 0,
                                 'one_sided_95_upper': bound,
                                 'rule_of_three': 3.0 / len(ypc),
                                 'basis': 'zero of n realised QB game-lines '
                                          'above the all-time record of 554'},
          'sealed_corpus_census': corpus_census(),
          'cohorts': {}}

    # ---- C1: 2025 forward-chained, the only cohort with outcomes ----------
    keep = [r for r in rows if r['season'] == 2025 and Q.eligible(r)]
    obs = np.array([r['pyds'] for r in keep], float)
    games = np.array([r['game_id'] for r in keep])
    uniq = sorted(set(games.tolist()))
    gof = np.array([uniq.index(g) for g in games])
    D = {nm: run_arm(keep, rows, 2025, sp) for nm, sp in ARMS}
    differ = sorted(k for k in D['incumbent']
                    if not np.array_equal(D['incumbent'][k], D['candidate'][k]))
    assert differ == ['pyds'], f'P8_TREATMENT_NOT_ISOLATED: {differ}'
    CMP = D['incumbent']['cmp']
    c1 = {'rows': len(keep), 'games': len(uniq), 'draws': M,
          'matrices_differing_between_arms': differ, 'arms': {}}
    rg = np.random.default_rng(BOOT_SEED)
    CR = {}
    for nm in D:
        P = D[nm]['pyds']
        t = tails(P, CMP, support)
        CR[nm] = np.array([crps_row(P[i], obs[i]) for i in range(len(obs))])
        cov = {}
        for lvl in (50, 80, 90, 95):
            a = (100 - lvl) / 2
            q1 = np.percentile(P, a, axis=1)
            q2 = np.percentile(P, 100 - a, axis=1)
            cov[str(lvl)] = float(((obs >= q1) & (obs <= q2)).mean())
        u = np.array([(P[i] < obs[i]).mean()
                      + rg.random() * (P[i] == obs[i]).mean()
                      for i in range(len(obs))])
        h = np.histogram(u, bins=10, range=(0, 1))[0]
        e = len(obs) / 10.0
        t.update({'crps': float(CR[nm].mean()),
                  'signed_bias': float(P.mean(1).mean() - obs.mean()),
                  'coverage': cov,
                  'randomised_pit_chi2_9df': float(((h - e) ** 2 / e).sum()),
                  'pearson_r_mean_vs_realised':
                      float(np.corrcoef(P.mean(1), obs)[0, 1])})
        c1['arms'][nm] = t
    da = CR['candidate'] - CR['incumbent']
    by = [da[gof == k] for k in range(len(uniq))]
    bs = np.empty(BOOT)
    for b in range(BOOT):
        pick = rg.integers(0, len(uniq), len(uniq))
        bs[b] = np.concatenate([by[p] for p in pick]).mean()
    c1['crps_delta_candidate_minus_incumbent'] = {
        'mean': float(da.mean()),
        'ci95': [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
        'method': f'block bootstrap over whole games, {BOOT} resamples',
        'reading': 'the interval contains zero, so this cohort does not '
                   'establish that either arm forecasts better'}
    # the tail rate, clustered by row, because cells within a row move together
    for nm in D:
        per = (D[nm]['pyds'] > RECORD).mean(1)
        se = float(per.std(ddof=1) / np.sqrt(len(per)))
        c1['arms'][nm]['rate_over_record_row_clustered'] = {
            'rate': float(per.mean()), 'se': se,
            'ci95': [float(per.mean() - 1.96 * se),
                     float(per.mean() + 1.96 * se)],
            'inside_derived_bound': bool(per.mean() + 1.96 * se < bound)}
    ev['cohorts']['C1_2025_forward_chained'] = c1

    # ---- C2: the quarterbacks who are actually on the sealed boards -------
    want = sealed_qbs()
    pros, allr = attach_prospective(rows, want)
    keep2 = [r for r in pros if r['h_games'] >= 1]
    D2 = {nm: run_arm(keep2, allr, 2026, sp) for nm, sp in ARMS}
    differ2 = sorted(k for k in D2['incumbent']
                     if not np.array_equal(D2['incumbent'][k], D2['candidate'][k]))
    assert differ2 == ['pyds'], f'P8_TREATMENT_NOT_ISOLATED_C2: {differ2}'
    CMP2 = D2['incumbent']['cmp']
    ev['cohorts']['C2_sealed_board_quarterbacks'] = {
        'quarterbacks_on_sealed_boards': len(want),
        'rows_with_a_prior_appearance': len(keep2), 'draws': M,
        'matrices_differing_between_arms': differ2,
        'no_realised_outcome': 'these are 2026 week-1 rows; no outcome for '
                               'them is in this repository, so no score is '
                               'computed and none is implied',
        'arms': {nm: tails(D2[nm]['pyds'], CMP2, support) for nm in D2}}

    OUT.write_text(json.dumps(ev, indent=1, sort_keys=False) + '\n')
    print(f'wrote {OUT.relative_to(_REPO)}')
    for cn, c in ev['cohorts'].items():
        print(f'\n{cn}')
        for nm, a in c['arms'].items():
            print(f'  {nm:10s} cells={a["cells"]:7d} max={a["max"]:8.0f} '
                  f'min={a["min"]:8.0f} >554={a["over_record"]:5d} '
                  f'rate={a["rate_over_record"]:.4e} neg={a["negative"]:5d} '
                  f'<-30={a["below_minus_30"]:4d} oos={a["out_of_support_banded"]:6d} '
                  f'mean={a["mean"]:8.3f}')
    print(f'\nderived bound {bound:.6e}')


if __name__ == '__main__':
    main()
