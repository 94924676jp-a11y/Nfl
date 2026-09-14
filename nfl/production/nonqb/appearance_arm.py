"""WHICH appearance model produced this number, recorded on the number.

THE PROBLEM THIS SOLVES

`appearance_r8` is KNOWN DEFECTIVE and is still the incumbent. Candidate B is
authorised for LIVE EVALUATION and is not promoted. Both of those are true at
once, which means two things have to be impossible:

1. Candidate B silently replacing the incumbent. An import swap, a default
   changed in one place, a fallback that fires when the candidate errors --
   each would run an unpromoted model under the promoted one's name.
2. A number arriving without its arm attached. A board row that says
   `p_appear = 0.84` and nothing else cannot be audited later, and "which model
   made this" is precisely the question the whole remediation is about.

So the arm is a DECLARED STATE, not a boolean, the caller must name it, and
every prediction comes back with the state stamped on the row.

THE FOUR STATES, AND WHY TWO OF THEM REFUSE

    INCUMBENT_KNOWN_DEFECTIVE     runs. appearance_r8, with its defect named.
    CANDIDATE_B_LIVE_EVALUATION   runs. appearance_b, recorded as an
                                  evaluation, not as a promotion.
    CANDIDATE_B_CONFIRMED         REFUSES. Confirmation needs games that were
                                  not used to select the hypothesis, and the
                                  WS-A evaluation ran on the same historical
                                  panel the hypothesis was selected from.
    CANDIDATE_B_PROMOTED          REFUSES. Promotion is an owner decision
                                  recorded in an owner artifact. No code path
                                  can produce one, and this one will not
                                  pretend to.

The last two exist as NAMED REFUSALS rather than as absent options on purpose.
An unknown name would be a typo; a declared name that refuses with its reason
is a statement about what has and has not been established. `resolve` returns
BLOCKED with `cause=Cause.GOVERNANCE` for both -- a rule refused it, which is a
decision, not a defect.

NOTHING HERE FALLS BACK. An unrecognised arm is a FAIL. A candidate arm that
errors is that arm's error, returned as it is. Falling back to the incumbent
would put an unrequested model behind a requested name, which fails in the
dangerous direction: the operator believes they are evaluating B and is reading
the incumbent's defect.

WHAT THIS MODULE DOES NOT DO. It does not edit, wrap, monkey-patch or shadow
`layers.py`, and it is imported by nothing in the existing production chain.
The incumbent path is byte-for-byte what it was.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'appearance-arm-switch-1'

INCUMBENT_KNOWN_DEFECTIVE = 'INCUMBENT_KNOWN_DEFECTIVE'
CANDIDATE_B_LIVE_EVALUATION = 'CANDIDATE_B_LIVE_EVALUATION'
CANDIDATE_B_CONFIRMED = 'CANDIDATE_B_CONFIRMED'
CANDIDATE_B_PROMOTED = 'CANDIDATE_B_PROMOTED'

STATES = (INCUMBENT_KNOWN_DEFECTIVE, CANDIDATE_B_LIVE_EVALUATION,
          CANDIDATE_B_CONFIRMED, CANDIDATE_B_PROMOTED)

# The default is the incumbent and stays the incumbent. Changing this line is
# a promotion, which is not a code decision.
DEFAULT_ARM = INCUMBENT_KNOWN_DEFECTIVE

ARMS = {
    INCUMBENT_KNOWN_DEFECTIVE: {
        'module': 'nfl.production.nonqb.appearance_r8',
        'runs': True,
        'what': 'the incumbent reliability-weighted logistic, V1 block keyed '
                'on the frozen P3 panel',
        'known_defect': 'V1 feature presence nearly encodes the label in '
                        'training (present 53,626 rows at 0.7119, absent '
                        '6,158 rows at 0.0000) and is a constant at serve',
        'defect_evidence': 'nfl/research/remediation/ws_a/WS_A_RESULTS.json',
        'governance': 'INCUMBENT -- in use, and known defective',
    },
    CANDIDATE_B_LIVE_EVALUATION: {
        'module': 'nfl.production.nonqb.appearance_b',
        'runs': True,
        'what': 'the same estimator with the V1 block recomputed over the '
                'union candidate universe, so block presence is a constant '
                'in training and at serve alike',
        'known_defect': 'the candidate universe is panel-or-depth-listed, not '
                        'the 53-man roster; a player with history who is not '
                        'depth-listed and does not play still produces no '
                        'frame row',
        'defect_evidence': 'nfl/research/remediation/l2/'
                           'L2_CANDIDATE_B_VALIDATION.md',
        'governance': 'LIVE EVALUATION -- authorised to run and to be '
                      'recorded. NOT promoted, NOT confirmed. Tonight\'s '
                      'outcome is not evidence about whether B is better.',
    },
    CANDIDATE_B_CONFIRMED: {
        'module': None,
        'runs': False,
        'refusal': 'Confirmation requires games that took no part in '
                   'selecting the hypothesis. The WS-A evaluation ran on the '
                   'same historical panel the hypothesis was selected from, '
                   'so every score in it is EXPLORATORY by its own '
                   'preregistration (PREREG_appearance_leak.md section 6). A '
                   'forward window, a sealed holdout or nested cross-fitting '
                   'would establish this; nothing available today does.',
        'governance': 'NOT ESTABLISHED',
    },
    CANDIDATE_B_PROMOTED: {
        'module': None,
        'runs': False,
        'refusal': 'Promotion is an owner decision recorded in an owner '
                   'artifact. No code path produces one. Selecting this arm '
                   'would be code claiming an authority it does not have.',
        'governance': 'NOT AUTHORISED',
    },
}


def _module(path):
    import importlib
    return importlib.import_module(path)


def resolve(arm=None) -> Outcome:
    """Name -> the arm's declaration, or a named refusal. Never a fallback."""
    name = arm or DEFAULT_ARM
    if name not in ARMS:
        return Outcome.fail(
            'APPEARANCE_ARM_UNKNOWN',
            f'appearance arm {name!r} names no mechanism this switch '
            f'implements. Choose from {list(STATES)}. Falling back to the '
            f'default would run an unrequested model behind a requested name.',
            arm=name, known=list(STATES))
    spec = ARMS[name]
    if not spec['runs']:
        return Outcome.blocked(
            f'APPEARANCE_ARM_{name}', spec['refusal'],
            cause=Cause.GOVERNANCE, arm=name,
            governance=spec['governance'])
    return Outcome.ok('APPEARANCE_ARM_RESOLVED', value=dict(spec, arm=name),
                      spec_version=SPEC_VERSION, arm=name,
                      governance=spec['governance'])


def module_identity(arm=None) -> Outcome:
    """The sha256 of the module source the named arm would actually run."""
    r = resolve(arm)
    if r.state is not State.PASS:
        return r
    rel = r.value['module'].replace('.', '/') + '.py'
    p = _REPO / rel
    if not p.exists():
        return Outcome.blocked(
            'APPEARANCE_ARM_MODULE_MISSING',
            f'{rel} does not exist, so the arm names a model that is not '
            f'present in this checkout', cause=Cause.DEPENDENCY, path=rel)
    return Outcome.ok('APPEARANCE_ARM_IDENTITY',
                      value={'path': rel,
                             'sha256': hashlib.sha256(
                                 p.read_bytes()).hexdigest()},
                      arm=r.value['arm'])


def predict(arm, season, week, players, injuries_rows, observed_before=None,
            kickoff_utc=None, depth=None) -> Outcome:
    """Run the named arm and STAMP IT ON EVERY ROW.

    `value` is `{gsis_id: {'p_appear': float, 'appearance_arm': str,
    'appearance_spec_version': str, 'appearance_coef_sha256': str,
    'appearance_module_sha256': str}}` -- a dict per player rather than a bare
    float, so a row cannot be carried downstream, written to a board or read
    back out of an artifact without the arm that produced it travelling with
    it. A float would separate from its provenance the first time anyone put
    it in a table.
    """
    r = resolve(arm)
    if r.state is not State.PASS:
        return r
    ident = module_identity(arm)
    if ident.state is not State.PASS:
        return ident
    mod = _module(r.value['module'])
    o = mod.predict(season, week, players, injuries_rows,
                    observed_before=observed_before,
                    kickoff_utc=kickoff_utc, depth=depth)
    if o.state is not State.PASS:
        # The arm's own refusal, returned as the arm's own refusal. No other
        # arm is tried: a fallback here is the failure mode this module exists
        # to make impossible.
        return o
    if not o.value:
        return Outcome.blocked(
            'APPEARANCE_ARM_EMPTY',
            f'arm {r.value["arm"]} returned PASS with no player probabilities. '
            f'An empty result is an absence, not a prediction.',
            cause=Cause.DATA, arm=r.value['arm'], inner_code=o.code)
    stamped = {}
    for pid, p in o.value.items():
        if not isinstance(p, (int, float)) or not (0.0 <= float(p) <= 1.0):
            return Outcome.fail(
                'APPEARANCE_ARM_PROBABILITY_OUT_OF_RANGE',
                f'arm {r.value["arm"]} returned {p!r} for {pid}',
                gsis_id=pid, arm=r.value['arm'])
        stamped[pid] = {
            'p_appear': float(p),
            'appearance_arm': r.value['arm'],
            'appearance_arm_governance': r.value['governance'],
            'appearance_spec_version': o.evidence.get('spec_version')
                                       or getattr(mod, 'SPEC_VERSION', None),
            'appearance_coef_sha256': o.evidence.get('coef_sha256'),
            'appearance_module_sha256': ident.value['sha256'][:16],
        }
    # The arm's own evidence is carried through, MINUS the keys this return
    # sets itself. `Outcome.ok` refuses a duplicate keyword, which is the right
    # behaviour: two different values for `n_players` in one artifact is
    # exactly the kind of quiet disagreement that has to raise.
    _MINE = ('value', 'spec_version', 'rows', 'n_players', 'arm',
             'arm_governance', 'arm_known_defect', 'arm_module',
             'arm_module_sha256', 'inner_code', 'inner_spec_version')
    ev = {k: v for k, v in o.evidence.items() if k not in _MINE}
    return Outcome.ok(
        'APPEARANCE_ARM_PREDICTED', value=stamped,
        spec_version=SPEC_VERSION, arm=r.value['arm'],
        arm_governance=r.value['governance'],
        arm_known_defect=r.value.get('known_defect'),
        arm_module=ident.value['path'],
        arm_module_sha256=ident.value['sha256'],
        inner_code=o.code, inner_spec_version=getattr(mod, 'SPEC_VERSION',
                                                      None),
        n_players=len(stamped), **ev)
