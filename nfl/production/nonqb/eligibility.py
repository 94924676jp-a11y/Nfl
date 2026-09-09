"""Production eligibility per layer. PATH_C_STATE.json is authoritative.

WHY THIS MODULE EXISTS

R2 found the pipeline carrying stage strings like `P4C system C ACCEPTED` and
`Stage2 ewma_hl2 ACCEPTED` while the registered governance artifact recorded
those same subsystems as DEVELOPING and INFORMATION_CONSTRAINED. Prose in a
spec string is not a governance state, and when the two disagree the prose is
what gets read by whoever is in a hurry.

So the mapping is computed here, from PATH_C_STATE, and every production-facing
label is derived from it rather than written by hand. `assert_no_stale_labels`
fails the suite if a production string ever claims ACCEPTED or PROMOTED for a
subsystem the governance artifact does not.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

STATE = _REPO / 'nfl' / 'research' / 'PATH_C_STATE.json'

# Owner actions that do NOT license a production forecast anyone may act on.
NON_PRODUCTION_ACTIONS = (
    'INVESTIGATE', 'DEVELOPING', 'CANDIDATE', 'INFORMATION_CONSTRAINED',
    'CALIBRATION_DEFECT', 'ESTIMATOR_DEFECT', 'DATA_BLOCKED',
    'HOLD_TENTATIVE', 'HOLD_CHARACTERIZED',
)
# The only two that would.
PRODUCTION_ACTIONS = ('PROSPECTIVELY_VALIDATED', 'PROMOTED')

# Which governance subsystem governs which pipeline layer.
LAYER_SUBSYSTEM = {
    'team_environment': 'team_volume',
    'appearance': 'appearance',
    'participation': 'appearance',
    'targets_carries': 'target_allocation',
    'receiving_conversion': 'receiving_conversion',
    'rushing_conversion': 'rushing_conversion',
    'td_layer': 'td_red_zone',
    'qb_layer': None,                       # QB V1: owner baseline selection
    'joint_accounting': 'joint_dependence',
}

# What each layer needs at prediction time, and where it comes from.
REQUIRED_INPUTS = {
    'team_environment': ['denom_panel (history)', 'schedules.home_coach/away_coach'],
    'appearance': ['injuries_{season} (practice_progression, teammate_availability)',
                   'panel history (absence_history, role_volatility)'],
    'participation': ['appearance output', 'panel_p3 prior pass-snap shares'],
    'targets_carries': ['appearance output (availability A)',
                        'participation share point forecast C',
                        'team_environment volume draws'],
    'receiving_conversion': ['targets_carries opportunity draws'],
    'rushing_conversion': ['targets_carries carry draws'],
    'td_layer': ['targets_carries / conversion opportunity'],
    'qb_layer': ['qb.pkl history', 'weekly_rosters'],
    'joint_accounting': ['every layer above, on one draw index'],
}

RUNTIME_ROLE = {
    'PRODUCTION': 'may contribute to a forecast artifact',
    'REHEARSAL_ONLY': 'may execute, but the artifact is not publishable',
    'BLOCKED': 'may not execute; a named refusal is returned',
}


def _state():
    return json.loads(STATE.read_text())


def matrix(input_states: dict | None = None) -> dict:
    """The eligibility matrix. `input_states` maps a required input to
    AVAILABLE / MISSING; anything unlisted is treated as UNKNOWN."""
    st = _state()
    subs = st.get('subsystems', {})
    inp = input_states or {}
    out = {}
    for layer, sub in LAYER_SUBSYSTEM.items():
        s = subs.get(sub, {}) if sub else {}
        action = s.get('action')
        research = s.get('knowledge')
        needs = REQUIRED_INPUTS.get(layer, [])
        missing = [n for n in needs if inp.get(n) == 'MISSING']
        if sub is None:
            owner, publishable = 'OWNER_BASELINE_SELECTION', False
            reason = ('QB V1 was accepted by the owner as a production '
                      'baseline selection, explicitly not a promotion')
        elif action in PRODUCTION_ACTIONS:
            owner, publishable = action, True
            reason = 'governance permits a production role'
        else:
            owner, publishable = action, False
            reason = (f'governance records {sub} as {action}, which is not a '
                      f'production state')
        if missing:
            role = 'BLOCKED'
            reason = f'required input unavailable: {missing}'
        elif publishable:
            role = 'PRODUCTION'
        else:
            role = 'REHEARSAL_ONLY'
        out[layer] = {
            'subsystem': sub,
            'research_state': research,
            'owner_state': owner,
            'production_implementation_state': None,   # filled by the runtime
            'prospective_validation_state': (
                'VALIDATED' if action == 'PROSPECTIVELY_VALIDATED'
                else 'NOT_PROSPECTIVELY_VALIDATED'),
            'required_inputs': needs,
            'current_input_state': ('MISSING' if missing else
                                    ('AVAILABLE' if needs and all(
                                        inp.get(n) == 'AVAILABLE' for n in needs)
                                     else 'UNKNOWN')),
            'allowed_runtime_role': role,
            'publication_eligible': False,     # NFL-1 gates everything anyway
            'reason': reason,
        }
    return out


def assert_no_stale_labels(paths=None) -> Outcome:
    """No production-facing string may call a non-production subsystem
    ACCEPTED or PROMOTED."""
    import re
    st = _state().get('subsystems', {})
    bad_words = re.compile(r'\b(ACCEPTED|PROMOTED)\b')
    paths = paths or [_REPO / 'nfl' / 'production' / 'run_forecast.py']
    offences = []
    for p in paths:
        p = pathlib.Path(p)
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if not bad_words.search(line) or line.strip().startswith('#'):
                continue
            for layer, sub in LAYER_SUBSYSTEM.items():
                if sub and layer in line:
                    act = st.get(sub, {}).get('action')
                    if act not in PRODUCTION_ACTIONS:
                        offences.append({'file': p.name, 'line': i,
                                         'layer': layer, 'subsystem': sub,
                                         'governance_action': act,
                                         'text': line.strip()[:120]})
    if offences:
        return Outcome.fail(
            'STALE_GOVERNANCE_LABEL',
            f'{len(offences)} production string(s) call a non-production '
            f'subsystem ACCEPTED or PROMOTED. PATH_C_STATE is authoritative.',
            offences=offences)
    return Outcome.ok('NO_STALE_GOVERNANCE_LABELS', value=len(paths),
                      detail='no production string overstates a governance '
                             'state')
