"""Q9B step 4: the prospective freeze. Record the candidate; consume nothing.

    python3.12 -m nfl.research.q9b.freeze

WHAT A FREEZE IS FOR. Q9 has to earn evidence on games nobody has seen. That
is only meaningful if the thing evaluated later is provably the thing frozen
now, so this records the identity of the candidate rather than a description
of it: the source hash of every module the mechanism executes, the feature
schema in order, the hash of each fitted parameter block, the production
interface version, the fallback counters and the decision metrics as they
stood.

NO FUTURE OUTCOME IS CONSUMED HERE, and none may be. The artifact records what
WOULD be evaluated and against what. Opening a 2026 outcome to compute any
number in it would make the freeze a post-hoc description of a result.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import layers as LAYERS                 # noqa: E402
from nfl.research.q6 import frame as Q6F                          # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                  # noqa: E402
from nfl.research.q8 import audit as AUD                          # noqa: E402
from nfl.research.q9 import hurdle as Q9                          # noqa: E402
from nfl.research.q9b import family as FAM                        # noqa: E402
from nfl.research.q9b import production_parity as PAR             # noqa: E402

SPEC_VERSION = 'q9b-prospective-freeze-1'
HERE = _REPO / 'nfl' / 'research' / 'q9b'
FREEZE = HERE / 'Q9_PROSPECTIVE_FREEZE.json'
FREEZE_SEASON = 2026


def _sha(text):
    return hashlib.sha256(str(text).encode()).hexdigest()


def _module_hash(mod):
    return _sha(inspect.getsource(mod))[:16]


def _array_hash(a):
    b = np.asarray(a, float)
    return _sha(np.array2string(b, precision=12, threshold=b.size))[:16]


def fitted_parameter_hashes(season=FREEZE_SEASON):
    """Hashes of the parameter blocks a prospective run would consume.

    Fitted on seasons STRICTLY BEFORE the freeze season, which for a 2026
    freeze is every historical season this repository holds. No 2026 row is
    read to produce any of them.
    """
    rows, _ = Q6F.load_frame()
    rows = Q6F.attach_role_class(rows)
    rows, _ = Q6F.attach_opportunity(rows)
    rows = AUD._own_history(rows)
    rows = Q9.attach_hurdle_history(rows)
    train = [r for r in rows if r['s'] < season]
    denom = AUD.load_denom()
    bud_point, bud_resid, bud_est = AUD.budget_model(denom, season)
    bvals = np.array(list(bud_point.values()), float)
    bmean, bsd = float(bvals.mean()), float(bvals.std(ddof=1))
    model = Q9.fit_hurdle(train, bud_point, bmean, bsd)
    cm = AUD._class_means(train)
    k_fit, k_ev = Q6C._share_k(train, 'targets')
    if model is None:
        raise SystemExit('Q9_FREEZE_NO_HURDLE_MODEL: the stage-1 fit returned '
                         'nothing, so there is no candidate to freeze.')
    return {
        'training_seasons': sorted({r['s'] for r in train}),
        'n_training_rows': len(train),
        'n_appeared_training_rows': sum(1 for r in train if r['appeared']),
        'hurdle_coefficients_sha16': _array_hash(model['w']),
        'hurdle_standardiser_mu_sha16': _array_hash(model['mu']),
        'hurdle_standardiser_sd_sha16': _array_hash(model['sd']),
        'class_prior_sha16': _sha(json.dumps(
            {f'{k[0]}|{k[1]}': round(v, 10) for k, v in sorted(cm.items())},
            sort_keys=True))[:16],
        'share_shrinkage_k': round(float(k_fit), 8),
        'share_shrinkage_basis': k_ev.get('basis'),
        'budget_estimator': bud_est,
        'budget_point_sha16': _sha(json.dumps(
            {f'{k[0]}-{k[1]}-{k[2]}': round(v, 8)
             for k, v in sorted(bud_point.items())}, sort_keys=True))[:16],
        'budget_residual_pool_sha16': _array_hash(bud_resid),
        'budget_residual_pool_size': int(len(bud_resid)),
        'q8_budget_repair_applied': False,
    }


def build(season=FREEZE_SEASON):
    fam = json.loads((HERE / 'Q9B_FAMILY_RESULTS.json').read_text())
    par = json.loads((HERE / 'Q9_PRODUCTION_PARITY.json').read_text())
    ident = json.loads((HERE / 'Q9B_IDENTIFIABILITY.json').read_text())
    q9 = json.loads(
        (_REPO / 'nfl' / 'research' / 'q9'
         / 'Q9_FORWARD_CHAIN_RESULTS.json').read_text())
    arm = fam['by_arm']['Q9_HURDLE']
    base = fam['by_arm']['BASELINE']
    return {
        'artifact': 'NFL_Q9_PROSPECTIVE_FREEZE',
        'spec_version': SPEC_VERSION,
        'frozen_at_season': season,
        'promoted': False,
        'no_future_outcome_consumed': True,
        'consumption_note': (
            'this artifact records what WOULD be evaluated and against what. '
            'No 2026 outcome is read to compute any number in it; doing so '
            'would make the freeze a post-hoc description of a result.'),

        'candidate_identity': {
            'mechanism_spec_version': Q9.SPEC_VERSION,
            'module_source_sha16': {
                'nfl.research.q9.hurdle': _module_hash(Q9),
                'nfl.research.q9b.family': _module_hash(FAM),
                'nfl.research.q9b.production_parity': _module_hash(PAR),
                'nfl.production.nonqb.layers': _module_hash(LAYERS),
            },
            'allocator': 'nfl.research.q9.hurdle.allocate_hurdle',
            'one_target_floor': True,
            'named_fallbacks': [Q9.NO_CLEARERS, Q9.MORE_CLEARERS_THAN_BUDGET],
        },
        'feature_schema': {
            'stage_1_features_in_order': list(Q9.FEATURE_NAMES),
            'n_features': len(Q9.FEATURE_NAMES),
            'schema_sha16': _sha('|'.join(Q9.FEATURE_NAMES))[:16],
            'refused_inputs': list(Q9.FORBIDDEN_INPUTS),
            'appearance_is_upstream_and_separate': True,
        },
        'parameter_hashes': fitted_parameter_hashes(season),
        'production_interface': {
            'version_sha16': _module_hash(LAYERS),
            'interfaces': par['interfaces_exercised'],
            'parity_status': par['status'],
            'invariants': par['invariants'],
        },
        'fallback_counters_at_freeze': fam['fallback_audit']['states'],
        'decision_metrics_at_freeze': {
            'zero_brier': [base['zero_target_probability']['brier'],
                           arm['zero_target_probability']['brier']],
            'zero_log_loss': [base['zero_target_probability']['log_loss'],
                              arm['zero_target_probability']['log_loss']],
            'zero_rate_gap': [base['zero_target_probability']['zero_rate_gap'],
                              arm['zero_target_probability']['zero_rate_gap']],
            'marginal_crps': [
                base['full_marginal_target_distribution']['mean_crps'],
                arm['full_marginal_target_distribution']['mean_crps']],
            'marginal_crps_delta_pct':
                fam['paired']['Q9_HURDLE']['marginal_crps']['delta_pct'],
            'q9_own_run_decision': q9['decision']['decision'],
            'identifiability_structural_excess':
                ident['verdict']['structural_excess'],
            'hurdle_identified_as_structural':
                ident['verdict']['hurdle_identified_as_structural'],
            'plain_family_closed_fraction_of_zero_shortfall':
                fam['falsifiable_check']['by_arm']['MNL_PLUS'][
                    'fraction_of_shortfall_closed'],
            'hurdle_closed_fraction_of_zero_shortfall':
                fam['falsifiable_check']['by_arm']['Q9_HURDLE'][
                    'fraction_of_shortfall_closed'],
        },
        'prospective_plan': {
            'unit': 'player-game on unseen 2026 regular-season games',
            'arms': ['BASELINE', 'Q9_HURDLE'],
            'primary': ['zero-target Brier and log loss',
                        'zero-rate gap against observed',
                        'full marginal target CRPS'],
            'secondary': ['positive-target CRPS',
                          'downstream receiving-yard CRPS with efficiency '
                          'held fixed'],
            'strata': ['RB/WR/TE', 'starter/rotational/fringe',
                       'appearance certainty', 'prior opportunity depth'],
            'clustering': 'block bootstrap over whole team-games',
            'refit_policy': ('the frozen parameter hashes above are what a '
                             'prospective run must reproduce. A refit is a '
                             'different candidate and needs its own freeze.'),
            'what_would_falsify': (
                'the zero-rate gap failing to narrow on unseen games, or the '
                'marginal CRPS gain not reproducing outside the seasons that '
                'selected it'),
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, default=FREEZE_SEASON)
    a = ap.parse_args(argv)
    out = build(a.season)
    FREEZE.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(f"frozen at season      : {out['frozen_at_season']}")
    print(f"mechanism spec        : "
          f"{out['candidate_identity']['mechanism_spec_version']}")
    print(f"feature schema sha16  : "
          f"{out['feature_schema']['schema_sha16']} "
          f"({out['feature_schema']['n_features']} features)")
    print(f"hurdle coef sha16     : "
          f"{out['parameter_hashes']['hurdle_coefficients_sha16']}")
    print(f"production parity     : "
          f"{out['production_interface']['parity_status']}")
    print(f"no future outcome read: {out['no_future_outcome_consumed']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
