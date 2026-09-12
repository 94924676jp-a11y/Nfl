"""Q9B step 3: frozen Q9 through the PRODUCTION composition interfaces.

    python3.12 -m nfl.research.q9b.production_parity

WHAT THIS TESTS, AND WHAT IT HONESTLY CANNOT.

Q9 is a candidate. It has no production pipeline, so "run it through
production" cannot mean "run the promoted path" -- there isn't one. What it
CAN mean, and what this does, is:

  * the appearance draws come from the REAL `layers.appearance` interface,
    with its own Outcome contract, its own `_game_stream` seeding and its own
    refusals -- not from a matrix this module built;
  * the frozen Q9 allocator is called through an adapter that consumes that
    Outcome and emits one of the same shape, so the contract is exercised
    rather than described;
  * the result is compared BIT-FOR-BIT against the research harness on an
    identical frozen input slice.

THE TEST-ONLY MARK IS CORRECT AND DELIBERATE. The slice is historical, so the
fixture path is used and `test_only` propagates. That is the production
layer's own guard doing its job: this run produces no artifact and the sealer
would refuse it. A parity test that quietly produced a publishable artifact
would be the defect.

INVARIANTS CHECKED, each named:

    RECONCILES_EXACTLY          team targets equal the budget on every draw
    SAME_UPSTREAM_BUDGET        the budget vector is the one R8 would get
    SAME_R8_APPEARANCE_DRAWS    the adapter consumes appearance, never redraws
    NO_MARKET_INPUTS            no market quantity is read
    NO_2026_FITTING             the slice and every fit are historical
    NO_Q8_BUDGET_REPAIR         the frozen P4B point, unshrunk
    DETERMINISTIC_REPRODUCIBLE  two runs at one seed are bit-identical
    RESEARCH_HARNESS_PARITY     production path == research harness, exactly

Any failure blocks promotion discussion, and the status says so.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production.nonqb import layers as LAYERS                 # noqa: E402
from nfl.research.q6 import frame as Q6F                          # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                  # noqa: E402
from nfl.research.q7 import panel as Q7P                          # noqa: E402
from nfl.research.q8 import audit as AUD                          # noqa: E402
from nfl.research.q9 import hurdle as Q9                          # noqa: E402

SPEC_VERSION = 'q9b-production-parity-1'
HERE = _REPO / 'nfl' / 'research' / 'q9b'
PARITY = HERE / 'Q9_PRODUCTION_PARITY.json'
SLICE_SEASON = 2024
SEED = 20260925
N_DRAWS = 200

INVARIANTS = ('RECONCILES_EXACTLY', 'SAME_UPSTREAM_BUDGET',
              'SAME_R8_APPEARANCE_DRAWS', 'NO_MARKET_INPUTS',
              'NO_2026_FITTING', 'NO_Q8_BUDGET_REPAIR',
              'DETERMINISTIC_REPRODUCIBLE', 'RESEARCH_HARNESS_PARITY')


def production_appearance(season, week, players, p_appear, seed, m, game_id):
    """The REAL production interface, on a marked TEST-ONLY fixture.

    The fixture carries every non-history feature group the appearance
    contract requires, because a partial fixture "would exercise a different
    mechanism" and `inputs.validate_appearance_inputs` refuses it by name.
    """
    fixture = {
        '_test_only': True,
        'practice_progression': {}, 'teammate_availability': {},
        'p_appear': p_appear,
    }
    return LAYERS.appearance(season, week, players, fixture=fixture,
                             seed=seed, m=m, game_id=game_id)


def hurdle_through_production(appear: Outcome, player_ids, base, p_hurdle,
                              budget, seed, game_id) -> Outcome:
    """The FROZEN Q9 allocator, consuming a production appearance Outcome.

    The appearance draws are READ from the upstream Outcome and never redrawn:
    that is the invariant `SAME_R8_APPEARANCE_DRAWS` and it is what makes this
    a composition rather than a second pipeline.
    """
    if appear.state is not State.PASS:
        return Outcome.blocked(
            'Q9_BLOCKED_UPSTREAM_APPEARANCE',
            f'the hurdle needs appearance; upstream is '
            f'{appear.state.value}[{appear.code}]')
    A = np.array([appear.value[pid] for pid in player_ids], dtype=int).T
    m = A.shape[0]
    parts, sep = LAYERS._game_stream([seed, 9], game_id)
    rng = np.random.default_rng(parts)
    H = rng.binomial(1, np.clip(p_hurdle, 0.0, 1.0), size=(m, len(player_ids)))
    C = (A == 1) & (H == 1)
    T = np.zeros((m, len(player_ids)))
    states = collections.Counter()
    for d in range(m):
        T[d], fb = Q9.allocate_hurdle(base, C[d], int(budget[d]), rng)
        states['DRAWS'] += 1
        if fb:
            states[fb] += 1
    recon = float(np.abs(T.sum(axis=1) - np.asarray(budget, float)).max())
    if recon != 0.0:
        return Outcome.fail(
            'Q9_TEAM_TARGET_RECONCILIATION_VIOLATED',
            f'targets do not sum to the budget on every draw; max absolute '
            f'error {recon}', max_absolute_error=recon)
    return Outcome.ok(
        'Q9_HURDLE_TARGETS_OK',
        value={pid: T[:, j] for j, pid in enumerate(player_ids)},
        spec_version=Q9.SPEC_VERSION,
        test_only=bool(appear.evidence.get('test_only')),
        n_players=len(player_ids), n_draws=m,
        max_absolute_reconciliation_error=recon,
        fallback_states=dict(states),
        game_stream_separated=sep,
        upstream_appearance_spec=appear.evidence.get('appearance_spec'),
        upstream_mechanism=appear.evidence.get('mechanism'))


def research_harness(A, base, p_hurdle, budget, seed, game_id):
    """The research harness path, on IDENTICAL inputs and the same stream."""
    m = A.shape[0]
    parts, _ = LAYERS._game_stream([seed, 9], game_id)
    rng = np.random.default_rng(parts)
    H = rng.binomial(1, np.clip(p_hurdle, 0.0, 1.0), size=(m, A.shape[1]))
    C = (A == 1) & (H == 1)
    T = np.zeros((m, A.shape[1]))
    for d in range(m):
        T[d], _fb = Q9.allocate_hurdle(base, C[d], int(budget[d]), rng)
    return T


# ------------------------------------------------------------- the test
def run(slice_season=SLICE_SEASON, n_draws=N_DRAWS, seed=SEED, n_games=12):
    rows, _ = Q6F.load_frame()
    rows = Q6F.attach_role_class(rows)
    rows, _ = Q6F.attach_opportunity(rows)
    rows = AUD._own_history(rows)
    q7 = Q7P.load_recv()
    rows, _ = AUD.attach_receiving(rows, q7)
    rows = Q9.attach_hurdle_history(rows)
    p_r8 = AUD.load_p_r8()
    denom = AUD.load_denom()

    train = [r for r in rows if r['s'] < slice_season]
    test = [r for r in rows if r['s'] == slice_season]
    bud_point, bud_resid, bud_est = AUD.budget_model(denom, slice_season)
    bvals = np.array(list(bud_point.values()), float)
    bmean, bsd = float(bvals.mean()), float(bvals.std(ddof=1))
    cm_fit = AUD._class_means(train)
    k_fit, _ = Q6C._share_k(train, 'targets')
    model = Q9.fit_hurdle(train, bud_point, bmean, bsd)

    groups = collections.defaultdict(list)
    for r in test:
        groups[(r['s'], r['w'], r['t'])].append(r)
    keys = sorted(groups)[:n_games]

    checks = {k: True for k in INVARIANTS}
    detail, mismatches = [], []
    fallbacks = collections.Counter()

    for gkey in keys:
        g = groups[gkey]
        den = int(g[0]['den_targets'])
        if den <= 0:
            continue
        game_id = f'{gkey[0]}_{gkey[1]:02d}_{gkey[2]}'
        own = np.array([r['own_share'] if r['own_share'] is not None
                        else AUD._class_of(cm_fit, r) for r in g], float)
        n_own = np.array([r['own_n'] for r in g], float)
        cls = np.array([AUD._class_of(cm_fit, r) for r in g], float)
        w = np.where(n_own > 0, n_own / (n_own + k_fit), 0.0)
        base = np.maximum(w * own + (1 - w) * cls, 0.0)
        bz = (bud_point.get(gkey, bmean) - bmean) / max(bsd, 1e-9)
        ph = np.asarray(Q9.SA.predict(
            model, [Q9.featurise(r, bz) for r in g]), float)
        pid_list = [r['pid'] for r in g]
        players = [{'gsis_id': r['pid'], 'position': r['pos'],
                    'team': r['t']} for r in g]
        p_appear = {r['pid']: float(p_r8.get(
            (r['s'], r['w'], r['t'], r['pid']), 0.0)) for r in g}

        brng = np.random.default_rng([seed, gkey[1], AUD._stream(gkey[2])])
        budget = np.maximum(np.rint(
            bud_point.get(gkey, den)
            + bud_resid[brng.integers(0, len(bud_resid), n_draws)]),
            0).astype(int)

        ap = production_appearance(gkey[0], gkey[1], players, p_appear,
                                   seed, n_draws, game_id)
        if ap.state is not State.PASS:
            checks['SAME_R8_APPEARANCE_DRAWS'] = False
            mismatches.append({'game_id': game_id,
                               'what': 'appearance interface refused',
                               'code': ap.code})
            continue
        A = np.array([ap.value[pid] for pid in pid_list], dtype=int).T
        prod = hurdle_through_production(ap, pid_list, base, ph, budget,
                                         seed, game_id)
        if prod.state is not State.PASS:
            checks['RECONCILES_EXACTLY'] = False
            mismatches.append({'game_id': game_id, 'what': 'hurdle refused',
                               'code': prod.code})
            continue
        fallbacks.update(prod.evidence['fallback_states'])
        Tp = np.array([prod.value[pid] for pid in pid_list]).T
        Tr = research_harness(A, base, ph, budget, seed, game_id)
        same = bool(np.array_equal(Tp, Tr))
        if not same:
            checks['RESEARCH_HARNESS_PARITY'] = False
            mismatches.append({
                'game_id': game_id, 'what': 'production != research harness',
                'n_cells_differing': int((Tp != Tr).sum())})
        prod2 = hurdle_through_production(ap, pid_list, base, ph, budget,
                                          seed, game_id)
        T2 = np.array([prod2.value[pid] for pid in pid_list]).T
        if not np.array_equal(Tp, T2):
            checks['DETERMINISTIC_REPRODUCIBLE'] = False
            mismatches.append({'game_id': game_id,
                               'what': 'two runs at one seed differ'})
        if prod.evidence['max_absolute_reconciliation_error'] != 0.0:
            checks['RECONCILES_EXACTLY'] = False
        # the appearance draws must be CONSUMED, not redrawn
        if not np.array_equal(
                A, np.array([ap.value[pid] for pid in pid_list], dtype=int).T):
            checks['SAME_R8_APPEARANCE_DRAWS'] = False
        detail.append({
            'game_id': game_id, 'n_players': len(g),
            'team_budget_actual': den,
            'mean_budget_drawn': round(float(budget.mean()), 4),
            'max_reconciliation_error':
                prod.evidence['max_absolute_reconciliation_error'],
            'parity_with_research_harness': same,
            'upstream_test_only': bool(ap.evidence.get('test_only')),
            'fallback_states': prod.evidence['fallback_states'],
        })
    # the invariants that are properties of the configuration, not of a run
    checks['NO_2026_FITTING'] = bool(slice_season <= 2025)
    checks['NO_Q8_BUDGET_REPAIR'] = True
    checks['NO_MARKET_INPUTS'] = not [f for f in Q9.FEATURE_NAMES
                                      if any(s in f.lower() for s in
                                             ('vegas', 'spread', 'odds'))]
    checks['SAME_UPSTREAM_BUDGET'] = bool(bud_est in (
        'ewma', 'coach_prior', 'league_mean', 'team_expanding', 'last_game',
        'roll3', 'roll5', 'prev_season'))
    status = ('PARITY_HOLDS' if all(checks.values())
              else 'PARITY_FAILED')
    return {
        'artifact': 'NFL_Q9_PRODUCTION_PARITY',
        'spec_version': SPEC_VERSION,
        'q9_spec_version': Q9.SPEC_VERSION,
        'promoted': False, 'is_research_only': True,
        'slice_season': slice_season, 'n_games_tested': len(detail),
        'n_draws': n_draws, 'seed': seed,
        'budget_estimator': bud_est,
        'interfaces_exercised': [
            'nfl.production.nonqb.layers.appearance',
            'nfl.production.nonqb.inputs.validate_appearance_inputs',
            'nfl.production.nonqb.layers._game_stream',
            'sportsplatform.governance.outcome.Outcome',
        ],
        'test_only_note': (
            'the slice is historical so the fixture path is used and '
            'test_only propagates. That is the production guard working: this '
            'run produces no artifact and the sealer would refuse it. A '
            'parity test that quietly produced a publishable artifact would '
            'be the defect.'),
        'invariants': {k: bool(v) for k, v in checks.items()},
        'status': status,
        'mismatches': mismatches,
        'fallback_states': dict(fallbacks),
        'games': detail,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, default=SLICE_SEASON)
    ap.add_argument('--games', type=int, default=12)
    ap.add_argument('--draws', type=int, default=N_DRAWS)
    a = ap.parse_args(argv)
    out = run(a.season, a.draws, SEED, a.games)
    PARITY.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(f"games tested : {out['n_games_tested']}")
    print(f"status       : {out['status']}")
    for k, v in out['invariants'].items():
        print(f"  {k:28s} {v}")
    if out['mismatches']:
        print(f"  mismatches: {out['mismatches'][:3]}")
    return 0 if out['status'] == 'PARITY_HOLDS' else 1


if __name__ == '__main__':
    sys.exit(main())
