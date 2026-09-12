"""The frozen Q9 candidate, as an identity a later run must reproduce.

    python3.12 -m nfl.prospective.q9shadow.candidate

WHAT THIS MODULE IS FOR, AND THE ONE SENTENCE THAT MOTIVATES IT

A prospective test is only worth running if the thing scored months from now
is provably the thing frozen today. So this does not describe the candidate --
it IDENTIFIES it: the source hash of every module the mechanism executes, the
feature schema in declaration order, the hash of each fitted coefficient
block, the upstream appearance artifact, the team-budget artifact, the seed
protocol and draw count, and the production interface version.

WHAT IT MAY NOT DO, taken from the directive verbatim: no refitting of
coefficients, no change to features, no change to the one-target floor, no
change to fallback logic, no change to thresholds, and no tuning on any 2026
result. Any such change creates a NEW candidate and requires a NEW freeze.
`assert_identical_to_freeze` is how that is enforced rather than promised:
the identity recomputed at forecast time is compared field by field against
the freeze written before the season, and a single differing hash refuses.

SHADOW MEANS SHADOW. `promoted` is False, `prospective_candidate` is True,
`shadow_only` is True, and the registry refuses the combination that would let
one of those three drift away from the other two.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402
from nfl.prospective import registries as REG                        # noqa: E402
from nfl.production.nonqb import layers as LAYERS                    # noqa: E402
from nfl.research.q6 import frame as Q6F                             # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                     # noqa: E402
from nfl.research.q8 import audit as AUD                             # noqa: E402
from nfl.research.q9 import hurdle as Q9                             # noqa: E402
from nfl.research.q9b import family as FAM                           # noqa: E402
from nfl.research.q9b import freeze as FRZ                           # noqa: E402
from nfl.research.q9b import production_parity as PAR                # noqa: E402

SPEC_VERSION = 'q9-prospective-candidate-1'
CANDIDATE_NAME = 'Q9_TARGET_HURDLE'
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'
CANDIDATE_JSON = HERE / 'Q9_PROSPECTIVE_CANDIDATE.json'
FREEZE_JSON = (_REPO / 'nfl' / 'research' / 'q9b'
               / 'Q9_PROSPECTIVE_FREEZE.json')

# THE PROSPECTIVE SEED PROTOCOL, DECLARED HERE AND NOWHERE ELSE.
#
# It is NOT the Q9B research seed. That is deliberate and it is not a change
# to the candidate: a seed is an execution parameter, not a coefficient, and
# reusing the seed that produced the development result would make the
# prospective draws a replay of it rather than an independent sample from the
# same frozen mechanism. What must not move -- and does not -- is the
# mechanism: features, coefficients, the one-target floor, the fallbacks and
# the thresholds are read from the frozen module.
SEED = 20260912
N_DRAWS = 1000

# The arms, and the rule that they are never pooled. R8 is the production
# composition as it stands; Q9_HURDLE is the frozen candidate. Both consume
# the SAME upstream appearance draws and the SAME team-budget draws, so the
# only difference between them is the allocation mechanism.
ARM_PRODUCTION = 'R8_PRODUCTION'
ARM_CANDIDATE = 'Q9_HURDLE'
ARMS = (ARM_PRODUCTION, ARM_CANDIDATE)

# The fields of the candidate identity that a prospective run must reproduce
# bit for bit. A field absent from this tuple is not part of the identity and
# cannot silently become part of it.
IDENTITY_FIELDS = (
    'candidate_name', 'mechanism_spec_version', 'module_source_sha16',
    'feature_schema_sha16', 'n_features', 'coefficient_sha16',
    'standardiser_sha16', 'class_prior_sha16', 'share_shrinkage_k',
    'budget_point_sha16', 'budget_residual_pool_sha16', 'budget_estimator',
    'appearance_artifact', 'appearance_spec_sha16', 'one_target_floor',
    'named_fallbacks', 'production_interface_sha16',
)


def _sha(text):
    return hashlib.sha256(str(text).encode()).hexdigest()


def _module_hash(mod):
    return _sha(inspect.getsource(mod))[:16]


def identity(season=2026):
    """Recompute the candidate identity from the code and fitted blocks.

    Every hash here is produced by re-running the frozen fit on seasons
    strictly before `season`. No row of `season` is read, which is what makes
    this callable before kickoff without consuming an outcome.
    """
    ph = FRZ.fitted_parameter_hashes(season)
    return {
        'candidate_name': CANDIDATE_NAME,
        'mechanism_spec_version': Q9.SPEC_VERSION,
        # EVERY MODULE THE MECHANISM EXECUTES, WHICH IS MORE THAN THE
        # FREEZE RECORDED. The freeze hashed the allocator, the production
        # layer and the two Q9B harness modules. It did NOT hash the modules
        # that build the features and the team budget -- q6.frame,
        # q6.forward_chain and q8.audit -- and those are part of the
        # execution path whether or not they were written down. They are
        # added here, and `assert_identical_to_freeze` treats the freeze's
        # set as a REQUIRED SUBSET rather than an exact match: a module the
        # freeze recorded may not be missing or changed, and a module it
        # omitted may be added. Adding a hash strengthens an identity; it
        # cannot weaken one.
        'module_source_sha16': {
            'nfl.research.q9.hurdle': _module_hash(Q9),
            'nfl.production.nonqb.layers': _module_hash(LAYERS),
            'nfl.research.q9b.family': _module_hash(FAM),
            'nfl.research.q9b.production_parity': _module_hash(PAR),
            'nfl.research.q8.audit': _module_hash(AUD),
            'nfl.research.q6.frame': _module_hash(Q6F),
            'nfl.research.q6.forward_chain': _module_hash(Q6C),
        },
        'feature_schema_sha16': _sha('|'.join(Q9.FEATURE_NAMES))[:16],
        'n_features': len(Q9.FEATURE_NAMES),
        'coefficient_sha16': ph['hurdle_coefficients_sha16'],
        'standardiser_sha16': (ph['hurdle_standardiser_mu_sha16'] + ':'
                               + ph['hurdle_standardiser_sd_sha16']),
        'class_prior_sha16': ph['class_prior_sha16'],
        'share_shrinkage_k': ph['share_shrinkage_k'],
        'budget_point_sha16': ph['budget_point_sha16'],
        'budget_residual_pool_sha16': ph['budget_residual_pool_sha16'],
        'budget_estimator': ph['budget_estimator'],
        # The upstream appearance model is a SEPARATE artifact and is named as
        # one. Q9 stage 1 is P(targeted | appears); collapsing it with
        # P(appears) is the error Q6 was built to prevent.
        'appearance_artifact': 'nfl.production.nonqb.layers.appearance (R8)',
        'appearance_spec_sha16': _sha(LAYERS.SPEC['appearance'])[:16],
        'one_target_floor': True,
        'named_fallbacks': [Q9.NO_CLEARERS, Q9.MORE_CLEARERS_THAN_BUDGET],
        'production_interface_sha16': _module_hash(LAYERS),
        # Recorded, and deliberately NOT part of IDENTITY_FIELDS: the seed and
        # draw count are execution parameters of a run, not properties of the
        # mechanism. Two runs at different seeds are the same candidate.
        'seed_protocol': {'seed': SEED, 'n_draws': N_DRAWS,
                          'policy': 'shared upstream draws, per-arm allocation '
                                    'stream keyed by arm name via crc32, '
                                    'never Python hash()'},
        'training_seasons': ph['training_seasons'],
        'n_training_rows': ph['n_training_rows'],
        'q8_budget_repair_applied': ph['q8_budget_repair_applied'],
    }


def identity_sha256(ident):
    """One digest over the identity fields, in declared order."""
    payload = {k: ident.get(k) for k in IDENTITY_FIELDS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     default=str).encode()).hexdigest()


def freeze_identity():
    """The identity as the pre-season freeze recorded it, or a refusal."""
    if not FREEZE_JSON.exists():
        return None
    fz = json.loads(FREEZE_JSON.read_text())
    ci, fs, ph, pi = (fz['candidate_identity'], fz['feature_schema'],
                      fz['parameter_hashes'], fz['production_interface'])
    return {
        'candidate_name': CANDIDATE_NAME,
        'mechanism_spec_version': ci['mechanism_spec_version'],
        'module_source_sha16': ci['module_source_sha16'],
        'feature_schema_sha16': fs['schema_sha16'],
        'n_features': fs['n_features'],
        'coefficient_sha16': ph['hurdle_coefficients_sha16'],
        'standardiser_sha16': (ph['hurdle_standardiser_mu_sha16'] + ':'
                               + ph['hurdle_standardiser_sd_sha16']),
        'class_prior_sha16': ph['class_prior_sha16'],
        'share_shrinkage_k': ph['share_shrinkage_k'],
        'budget_point_sha16': ph['budget_point_sha16'],
        'budget_residual_pool_sha16': ph['budget_residual_pool_sha16'],
        'budget_estimator': ph['budget_estimator'],
        'appearance_artifact': 'nfl.production.nonqb.layers.appearance (R8)',
        'appearance_spec_sha16': _sha(LAYERS.SPEC['appearance'])[:16],
        'one_target_floor': ci['one_target_floor'],
        'named_fallbacks': ci['named_fallbacks'],
        'production_interface_sha16': pi['version_sha16'],
    }


def assert_identical_to_freeze(ident=None, season=2026) -> Outcome:
    """Refuse if the live identity differs from the frozen one, field by field.

    THIS IS THE PROHIBITION MADE STRUCTURAL. "Do not refit the coefficients"
    is a sentence; a coefficient hash compared against the freeze is a gate.
    A differing field is named, because "the candidate changed" without saying
    WHICH part changed sends the next reader back to guessing.
    """
    fz = freeze_identity()
    if fz is None:
        return Outcome.blocked(
            'Q9_FREEZE_ARTIFACT_ABSENT',
            f'{FREEZE_JSON} does not exist, so there is nothing to compare a '
            f'live identity against. A prospective forecast written without a '
            f'pre-existing freeze cannot later be shown to be the candidate '
            f'that was frozen.', cause=Cause.GOVERNANCE)
    ident = ident or identity(season)
    diffs = []
    for f in IDENTITY_FIELDS:
        a, b = ident.get(f), fz.get(f)
        if f == 'module_source_sha16':
            # REQUIRED SUBSET, not exact match. See the comment in
            # `identity`: the freeze's modules must all be present and
            # unchanged; additional modules are a stronger identity.
            for mod, want in sorted((b or {}).items()):
                got = (a or {}).get(mod)
                if got is None:
                    diffs.append({'field': f'{f}:{mod}',
                                  'frozen': want, 'live': 'ABSENT'})
                elif got != want:
                    diffs.append({'field': f'{f}:{mod}',
                                  'frozen': want, 'live': got})
            continue
        if json.dumps(a, sort_keys=True, default=str) != \
                json.dumps(b, sort_keys=True, default=str):
            diffs.append({'field': f, 'frozen': b, 'live': a})
    if diffs:
        return Outcome.fail(
            'Q9_CANDIDATE_DIFFERS_FROM_FREEZE',
            f'{len(diffs)} identity field(s) differ from the freeze: '
            + ', '.join(d['field'] for d in diffs)
            + '. A changed coefficient, feature schema, floor, fallback or '
              'threshold is a NEW candidate and needs its own freeze; it may '
              'not inherit this one\'s prospective standing.',
            differing=diffs)
    return Outcome.ok(
        'Q9_CANDIDATE_MATCHES_FREEZE', value=identity_sha256(ident),
        detail=f'all {len(IDENTITY_FIELDS)} identity fields reproduce the '
               f'freeze; candidate sha {identity_sha256(ident)[:16]}; '
               f'{len(ident["module_source_sha16"]) - len(fz["module_source_sha16"])} '
               f'module hash(es) added beyond the freeze',
        n_fields=len(IDENTITY_FIELDS),
        modules_added=sorted(set(ident['module_source_sha16'])
                             - set(fz['module_source_sha16'])))


def build(season=2026):
    """The Q9_PROSPECTIVE_CANDIDATE.json payload. Reads no outcome."""
    reg = REG.check_candidate(CANDIDATE_NAME)
    entry = REG.CANDIDATES[CANDIDATE_NAME]
    ident = identity(season)
    match = assert_identical_to_freeze(ident, season)
    prohibited_ok = tuple(entry['prohibited_inputs']) == Q9.FORBIDDEN_INPUTS
    return {
        'artifact': 'NFL_Q9_PROSPECTIVE_CANDIDATE',
        'spec_version': SPEC_VERSION,
        'candidate_name': CANDIDATE_NAME,

        # The three flags the directive fixes, and they are the first thing a
        # reader sees.
        'promoted': False,
        'prospective_candidate': True,
        'shadow_only': True,

        'registry': {
            'home': 'nfl/prospective/registries.py::CANDIDATES',
            'state': f'{reg.state.value}[{reg.code}]',
            'status': entry['status'],
            'prohibited_inputs_match_module': bool(prohibited_ok),
            'promotion_rulebook': entry['promotion_rulebook'],
            'may_promote_on_2022_2025': entry['may_promote_on_2022_2025'],
        },
        'freeze': {
            'artifact': entry['freeze_artifact'],
            'comparison': f'{match.state.value}[{match.code}]',
            'detail': match.detail,
            'identity_fields_compared': list(IDENTITY_FIELDS),
        },
        'identity': ident,
        'identity_sha256': identity_sha256(ident),
        'frozen_prohibitions': {
            'no_coefficient_refit': 'coefficient_sha16 is compared to the '
                                    'freeze on every seal',
            'no_feature_change': 'feature_schema_sha16 is compared on every '
                                 'seal',
            'no_floor_change': 'one_target_floor is part of the identity',
            'no_fallback_change': 'named_fallbacks is part of the identity',
            'no_threshold_change': 'the thresholds live inside the hashed '
                                   'module source',
            'no_2026_tuning': 'every fitted block is estimated on seasons '
                              'strictly before the forecast season, and the '
                              'training season list is recorded above',
            'consequence': 'any such change is a NEW candidate requiring a '
                           'NEW freeze; it cannot inherit this standing',
        },
        'arms': {
            'production': ARM_PRODUCTION,
            'candidate': ARM_CANDIDATE,
            'never_pooled': True,
            'shared': ['upstream appearance draws', 'team budget draws',
                       'draw index', 'player frame', 'input captures'],
            'differs': ['the allocation mechanism, and nothing else'],
        },
        'primary_metrics': [
            'zero-target Brier', 'zero-target log loss',
            'zero-mass calibration gap', 'marginal target CRPS',
            'positive-target CRPS'],
        'secondary_metrics': [
            'downstream receiving-yard CRPS, preserved for diagnosis and NOT '
            'a promotion criterion',
            'randomized PIT, emitted so protocol S9.6 is evaluable'],
        'evidence_units': ['ROW', 'PLAYER_GAME', 'TEAM_GAME', 'GAME'],
        'no_future_outcome_consumed': True,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, default=2026)
    a = ap.parse_args(argv)
    out = build(a.season)
    CANDIDATE_JSON.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(f"candidate      : {out['candidate_name']}")
    print(f"registry       : {out['registry']['state']}")
    print(f"freeze         : {out['freeze']['comparison']}")
    print(f"identity sha   : {out['identity_sha256'][:16]}")
    print(f"promoted       : {out['promoted']}")
    print(f"shadow_only    : {out['shadow_only']}")
    print(f"written        : {CANDIDATE_JSON}")
    return 0 if out['freeze']['comparison'].startswith('PASS') else 1


if __name__ == '__main__':
    sys.exit(main())
