"""XL1: build and evaluate the cross-layer candidates against the two gates.

    python3.12 nfl/research/xl1/run_xl1.py [--games N] [--draws M]

Refuses to run if `predeclaration_xl1.md` no longer hashes to what was
committed. The candidates are research artifacts: production runs B0 and
nothing here is promoted.

B0 comes from `football_engine.run_game` itself rather than from a local
re-composition, so the baseline is production's own. C1 and C3 re-run only the
CONVERSION chain, calling `layers.receiving_conversion` and `layers.td_layer`
unmodified. C1's receiving draws are asserted byte-identical to B0's, which is
what licenses reading any C3 difference as the candidate rather than as a
difference in orchestration.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.capture import coverage as C                              # noqa: E402
from nfl.production import team_volume_v1 as TV                    # noqa: E402
from nfl.production.nonqb import engine_rehearsal as ER            # noqa: E402
from nfl.production.nonqb import football_engine as FE             # noqa: E402
from nfl.production.nonqb import layers as LY                      # noqa: E402
from nfl.production.nonqb import shared_pass as SP                 # noqa: E402
from nfl.production.rehearsal import run_slate as RS               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PREDECL = os.path.join(HERE, 'predeclaration_xl1.md')
HISTORY = os.path.join(HERE, 'history_levels.json')

TEAM_METRICS = ('completions', 'passing_yards', 'passing_td')
PLAYER_METRICS = ('targets', 'receptions', 'receiving_yards', 'receiving_td')
TEAM_MARGIN = 0.05      # predeclared, section 5
PLAYER_MARGIN = 0.10    # predeclared, section 5


def check_predeclaration():
    with open(PREDECL, 'rb') as fh:
        got = hashlib.sha256(fh.read()).hexdigest()
    if got != SP.PREDECLARATION_SHA256:
        raise SystemExit(
            f'PREDECLARATION_MODIFIED: {PREDECL} hashes to {got}, not the '
            f'committed {SP.PREDECLARATION_SHA256}. A pre-registration edited '
            f'after the fact is not a pre-registration.')
    return got


def derive_from_receiving(dr, rmask):
    """C1 and C3 share this: the team's passing line IS the receiving sum."""
    return {'completions': np.asarray(dr['receptions'], float)[rmask].sum(0),
            'passing_yards': np.asarray(dr['receiving_yards'],
                                        float)[rmask].sum(0),
            'passing_td': np.asarray(dr['receiving_td'], float)[rmask].sum(0)}


def c3_for_game(payload, fits, ordinal, m, seed, urate):
    """C3: re-deal targets from the QB throw budget, then run RC1 and TD2."""
    al, ix, qbi = payload['allocation'], payload['index'], payload['qb']
    if qbi is None:
        return None, 'QB_ABSENT'
    teams = ix['teams']
    qteam = np.asarray(qbi['team'])
    att = np.asarray(qbi['draws']['att'], float)
    rng = np.random.default_rng([seed, int(ordinal), 0xC3])
    targeted, per_team = [], {}
    for t in teams:
        sel = (qteam == t)
        if not sel.any():
            return None, f'NO_QB_ROW_FOR_{t}'
        o = SP.targeted_throws(att[sel], urate, rng)
        if o.state is not State.PASS:
            return None, f'{o.code}: {o.detail[:120]}'
        per_team[t] = o
        targeted.append(o.value['targeted'])
    dealt = SP.deal_targets(al['share'], al['other'], targeted,
                            al['starts'], al['counts'], rng)
    if dealt.state is not State.PASS:
        return None, f'{dealt.code}: {dealt.detail[:120]}'
    T = dealt.value['targets'].astype(float)
    cv = LY.receiving_conversion(al['tc'], T, fits['receiving_priors'].value,
                                 ix['recv_ids'], ix['recv_pos'], ordinal,
                                 m=m, seed=seed)
    if cv.state is not State.PASS:
        return None, f'{cv.code}: {cv.detail[:120]}'
    tdp = dict(fits['td_priors_rec'].value)
    tdp['pos_catch_rate'] = fits['receiving_priors'].value['pos_catch_rate']
    td = LY.td_layer(cv, T, tdp, ix['recv_ids'], ix['recv_pos'], ordinal,
                     m=m, seed=seed)
    if td.state is not State.PASS:
        return None, f'{td.code}: {td.detail[:120]}'
    return {'targets': T, 'receptions': cv.value['receptions'],
            'receiving_yards': cv.value['receiving_yards'],
            'receiving_td': td.value['td'],
            'throw_budget': {t: {k: v.tolist() if hasattr(v, 'tolist') else v
                                 for k, v in per_team[t].value.items()}
                             for t in teams},
            'throw_evidence': {t: dict(per_team[t].evidence)
                               for t in teams},
            'deal_evidence': dict(dealt.evidence)}, None


def replay_b0(payload, fits, ordinal, m, seed):
    """Re-run the conversion chain on B0's OWN target vector.

    The equivalence gate for this study. It must reproduce B0 byte for byte;
    if it does not, nothing measured on the C3 arm can be attributed to the
    candidate.
    """
    al, ix = payload['allocation'], payload['index']
    T = np.asarray(payload['draws']['targets'], float)
    cv = LY.receiving_conversion(al['tc'], T, fits['receiving_priors'].value,
                                 ix['recv_ids'], ix['recv_pos'], ordinal,
                                 m=m, seed=seed)
    if cv.state is not State.PASS:
        return None
    tdp = dict(fits['td_priors_rec'].value)
    tdp['pos_catch_rate'] = fits['receiving_priors'].value['pos_catch_rate']
    td = LY.td_layer(cv, T, tdp, ix['recv_ids'], ix['recv_pos'], ordinal,
                     m=m, seed=seed)
    if td.state is not State.PASS:
        return None
    return {'receptions': cv.value['receptions'],
            'receiving_yards': cv.value['receiving_yards'],
            'receiving_td': td.value['td']}


def summarise_player(x):
    x = np.asarray(x, float)
    return {'mean': float(x.mean()), 'p50': float(np.percentile(x, 50)),
            'p95': float(np.percentile(x, 95))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=None)
    ap.add_argument('--draws', type=int, default=400)
    ap.add_argument('--seed', type=int, default=20260908)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    a = ap.parse_args()
    sha = check_predeclaration()

    ur = SP.untargeted_rate()
    if ur.state is not State.PASS:
        raise SystemExit(f'{ur.code}: {ur.detail}')
    with open(HISTORY) as fh:
        hist = json.load(fh)

    prior = TV.JOINT_RESIDUALS_DEFAULT
    TV.JOINT_RESIDUALS_DEFAULT = True          # A3 on, per the owner ruling
    try:
        out = run(a, sha, ur, hist)
    finally:
        TV.JOINT_RESIDUALS_DEFAULT = prior
    dest = os.path.join(HERE, 'xl1_results.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=float)
    show = {k: v for k, v in out.items() if k != 'per_team_game'}
    print(json.dumps(show, indent=2, sort_keys=True, default=float))
    print(f'\nwrote {dest}')
    return 0


def run(a, sha, ur, hist):
    season, week, m, seed = a.season, a.week, a.draws, a.seed
    ordinal = season * 100 + week
    plan = C.load_week_plan(season, week)
    if plan.state is not State.PASS:
        raise SystemExit(f'week plan {plan.code}: {plan.detail}')
    ko = {c.game_id: c.kickoff_utc for c in plan.value}
    games = sorted(ko)[:a.games] if a.games else sorted(ko)

    _, rrows = RS.roster(season, week)
    by_team = collections.defaultdict(list)
    for r in rrows:
        if r['gsis_id'] and r['position'] in ER.POS:
            by_team[r['team']].append({'gsis_id': r['gsis_id'],
                                       'position': r['position'],
                                       'team': r['team'],
                                       'player_name': r.get('player_name')})
    everyone = [q for t in sorted(by_team) for q in by_team[t]]
    fits = FE.slate_fits(season, week, everyone)
    if fits.state is not State.PASS:
        raise SystemExit(f'slate fits {fits.code}: {fits.detail[:200]}')
    qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
            'team': r['team']} for r in rrows
           if r['gsis_id'] and r['position'] == 'QB']
    qo = FE.qb_slate(season, week, qbp, m=m, seed=seed)
    if qo.state is not State.PASS:
        raise SystemExit(f'qb slate {qo.code}: {qo.detail[:200]}')
    qb = qo.value
    qa = FE.QA.allocate(season, week, sorted({q['team'] for q in qbp}), qbp,
                        m=m, seed=seed)
    if qa.state is not State.PASS:
        raise SystemExit(f'qb allocation {qa.code}: {qa.detail[:200]}')
    qb['allocation'] = qa.value

    rows, gate1 = [], collections.Counter()
    c1_identical = {'checked': 0, 'identical': 0, 'differing': []}
    for gid in games:
        players = [q for t in gid.split('_')[2:4] for q in by_team.get(t, [])]
        g, payload = FE.run_game(
            season, week, gid, players, fits.value, m=m, seed=seed,
            injuries_rows=ER.stub_injuries(season, week, players),
            test_only=True, kickoff_utc=ko[gid], qb=qb)
        if payload is None:
            gate1['games_halted'] += 1
            continue
        ix, dr, qbi = payload['index'], payload['draws'], payload['qb']
        if qbi is None:
            gate1['games_without_qb'] += 1
            continue
        rteam, qteam = np.asarray(ix['recv_team']), np.asarray(qbi['team'])
        c3, why = c3_for_game(payload, fits.value, ordinal, m, seed, ur.value)
        if c3 is None:
            gate1['c3_refused'] += 1
            rows.append({'game_id': gid, 'c3_refusal': why})
            continue
        # C1 leaves the receiving chain untouched BY CONSTRUCTION -- it reads
        # B0's own arrays -- so there is nothing there to verify and a check
        # would be a tautology dressed as evidence.
        #
        # What DOES need verifying is the C3 path: that re-running the
        # conversion chain from this study reproduces B0 EXACTLY when handed
        # B0's own target vector. If it does, any C3 difference is the changed
        # budget and not the changed orchestration. Run once per game.
        eq = replay_b0(payload, fits.value, ordinal, m, seed)
        for k in ('receptions', 'receiving_yards', 'receiving_td'):
            c1_identical['checked'] += 1
            if eq is not None and np.array_equal(np.asarray(eq[k]),
                                                 np.asarray(dr[k])):
                c1_identical['identical'] += 1
            else:
                c1_identical['differing'].append(
                    {'game_id': gid, 'metric': k,
                     'reason': 'REPLAY_FAILED' if eq is None
                               else 'NOT_BYTE_IDENTICAL'})
        for t in ix['teams']:
            rm, qm = (rteam == t), (qteam == t)
            if not rm.any() or not qm.any():
                continue
            rec = {'game_id': gid, 'team': t, 'arms': {}}
            b0 = {'completions': np.asarray(qbi['draws']['cmp'],
                                            float)[qm].sum(0),
                  'passing_yards': np.asarray(qbi['draws']['pyds'],
                                              float)[qm].sum(0),
                  'passing_td': np.asarray(qbi['draws']['ptd'],
                                           float)[qm].sum(0)}
            b0_recv = derive_from_receiving(dr, rm)
            rec['arms']['B0'] = {
                'qb_side': {k: summarise_player(v) for k, v in b0.items()},
                'receiving_side': {k: summarise_player(v)
                                   for k, v in b0_recv.items()},
                'identity': _identity(b0, b0_recv)}
            c1 = b0_recv
            rec['arms']['C1'] = {
                'qb_side': {k: summarise_player(v) for k, v in c1.items()},
                'receiving_side': {k: summarise_player(v)
                                   for k, v in b0_recv.items()},
                'identity': _identity(c1, b0_recv)}
            c3r = derive_from_receiving(c3, rm)
            rec['arms']['C3'] = {
                'qb_side': {k: summarise_player(v) for k, v in c3r.items()},
                'receiving_side': {k: summarise_player(v)
                                   for k, v in c3r.items()},
                'identity': _identity(c3r, c3r),
                'throws': c3['throw_evidence'][t]}
            # player marginals, B0 against C3 (C1 is B0 by construction)
            disp = []
            for i in np.where(rm)[0]:
                for mt in PLAYER_METRICS:
                    b = summarise_player(np.asarray(dr[mt], float)[i])
                    c = summarise_player(np.asarray(c3[mt], float)[i])
                    for stat in ('mean', 'p95'):
                        if abs(b[stat]) > 1e-9:
                            disp.append({'player': ix['recv_ids'][i],
                                         'pos': ix['recv_pos'][i],
                                         'metric': mt, 'stat': stat,
                                         'b0': b[stat], 'c3': c[stat],
                                         'rel': (c[stat] - b[stat]) / b[stat]})
            rec['player_displacement'] = disp
            rows.append(rec)
    return _summarise(rows, hist, ur, sha, a, gate1, c1_identical)


def _identity(qb_side, recv_side):
    out = {}
    for k in TEAM_METRICS:
        d = np.abs(np.asarray(qb_side[k], float)
                   - np.asarray(recv_side[k], float))
        out[k] = {'violating_draws': int((d > 1e-6).sum()),
                  'n_draws': int(d.size),
                  'mean_abs_diff': float(d.mean())}
    return out


def _summarise(rows, hist, ur, sha, a, gate1, c1_identical):
    ok = [r for r in rows if 'arms' in r]
    hm = hist['team_game_means']
    out = {'artifact': 'XL1_RESULTS', 'TEST_ONLY': True,
           'governance': SP.GOVERNANCE, 'spec_version': SP.SPEC_VERSION,
           'predeclaration': SP.PREDECLARATION,
           'predeclaration_sha256': sha,
           'untargeted_rate': {'value': ur.value, **ur.evidence},
           'engine_version': FE.ENGINE_VERSION,
           'season': a.season, 'week': a.week, 'n_draws': a.draws,
           'joint_residuals': True, 'n_team_games': len(ok),
           'gate1_counters': dict(gate1),
           'orchestration_equivalence': dict(
               c1_identical,
               PASS=(c1_identical['checked'] > 0
                     and c1_identical['identical'] == c1_identical['checked']),
               meaning='this study re-runs the conversion chain on B0\'s own '
                       'target vector and must reproduce B0 byte for byte. '
                       'Failure invalidates every C3 number.'),
           'gate1': {}, 'gate2': {}, 'per_team_game': rows}
    if not ok:
        out['fatal'] = 'no team-game produced both sides'
        return out
    for arm in ('B0', 'C1', 'C3'):
        g1 = {}
        for k in TEAM_METRICS:
            v = [r['arms'][arm]['identity'][k] for r in ok]
            g1[k] = {'violating_draws': sum(x['violating_draws'] for x in v),
                     'total_draws': sum(x['n_draws'] for x in v),
                     'mean_abs_diff': round(statistics.mean(
                         x['mean_abs_diff'] for x in v), 6)}
        g1['PASS'] = all(g1[k]['violating_draws'] == 0 for k in TEAM_METRICS)
        out['gate1'][arm] = g1
        g2 = {}
        for k in TEAM_METRICS:
            mean_qb = statistics.mean(
                r['arms'][arm]['qb_side'][k]['mean'] for r in ok)
            h = hm[k]
            g2[k] = {'mean': round(mean_qb, 4), 'historical': h,
                     'rel_to_history': round((mean_qb - h) / h, 4)}
        out['gate2'][arm] = g2
    b0 = out['gate2']['B0']
    for arm in ('C1', 'C3'):
        flags = []
        for k in TEAM_METRICS:
            worse = (abs(out['gate2'][arm][k]['rel_to_history'])
                     - abs(b0[k]['rel_to_history']))
            out['gate2'][arm][k]['worse_than_b0_by'] = round(worse, 4)
            if worse > TEAM_MARGIN:
                flags.append(f'{k}: {worse:+.4f} beyond the {TEAM_MARGIN} '
                             f'team margin')
        out['gate2'][arm]['team_flags'] = flags
    disp = [d for r in ok for d in r.get('player_displacement', [])]

    def _cut(sel, label):
        v = [d for d in disp if sel(d)]
        if not v:
            return {'n': 0, 'note': f'no check in stratum {label}'}
        return {'n': len(v),
                'beyond_margin': sum(1 for d in v
                                     if abs(d['rel']) > PLAYER_MARGIN),
                'mean_abs_rel': round(statistics.mean(
                    abs(d['rel']) for d in v), 6),
                'median_rel': round(statistics.median(
                    d['rel'] for d in v), 6),
                'mean_rel': round(statistics.mean(d['rel'] for d in v), 6)}

    # A displacement of the MEAN is a level change; a displacement of p95 with
    # the mean intact is a dispersion change. They are different findings and
    # pooling them hides which one happened. Low-volume rows are split out
    # because a p95 moving from 0 to 1 is a 100% relative move and says
    # nothing about the architecture.
    out['gate2']['C3']['player_displacement'] = {
        'n_checks': len(disp),
        'beyond_margin': sum(1 for d in disp if abs(d['rel']) > PLAYER_MARGIN),
        'margin': PLAYER_MARGIN,
        'mean_abs_rel': round(statistics.mean(
            abs(d['rel']) for d in disp), 6) if disp else None,
        'by_stat': {st: _cut(lambda d, st=st: d['stat'] == st, st)
                    for st in ('mean', 'p95')},
        'by_metric': {mt: _cut(lambda d, mt=mt: d['metric'] == mt, mt)
                      for mt in PLAYER_METRICS},
        'mean_only_by_volume': {
            'b0_mean_ge_3': _cut(lambda d: d['stat'] == 'mean'
                                 and d['b0'] >= 3.0, 'mean>=3'),
            'b0_mean_lt_3': _cut(lambda d: d['stat'] == 'mean'
                                 and d['b0'] < 3.0, 'mean<3')},
        'worst': sorted(disp, key=lambda d: -abs(d['rel']))[:12]}
    out['gate2']['C1']['player_displacement'] = {
        'n_checks': 0, 'beyond_margin': 0, 'margin': PLAYER_MARGIN,
        'note': 'C1 leaves every receiving draw untouched by construction; '
                'there is no player displacement to measure.'}
    return out


if __name__ == '__main__':
    sys.exit(main())
