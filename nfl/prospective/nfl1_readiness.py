"""Stage 13: NFL-1 readiness report, and the guard that keeps it a decision.

THE ANSWER TO QUESTION 8 MUST BE NO.

No code path may transition NFL-1 from NOT AUTHORIZED to AUTHORIZED because a
test passed. A gate that authorizes itself is not a gate. `assert_no_auto_authorization`
refuses any transition that does not carry an explicit owner decision record,
and the test suite proves that refusal is load-bearing by deleting it.
"""
from __future__ import annotations

import json
import re
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

STATE = _REPO / 'nfl' / 'research' / 'PATH_C_STATE.json'
CHECKLIST = _REPO / 'nfl' / 'NFL_G0A_CHECKLIST.md'


def assert_no_auto_authorization(transition: dict) -> Outcome:
    """NFL-1 may change status ONLY on an explicit owner decision."""
    frm, to = transition.get('from'), transition.get('to')
    if to != 'AUTHORIZED':
        return Outcome.ok('NO_AUTHORIZATION_CLAIMED', value=to)
    basis = transition.get('basis')
    if basis != 'OWNER_DECISION' or not transition.get('owner_decision_id'):
        return Outcome.fail(
            'NFL1_AUTO_AUTHORIZATION_ATTEMPTED',
            f'a transition {frm!r} -> AUTHORIZED was attempted on basis '
            f'{basis!r}. NFL-1 is authorized by an explicit owner decision and '
            f'by nothing else -- not by a passing test, not by a discharged '
            f'checklist item, not by a green suite. A gate that can authorize '
            f'itself is not a gate.',
            basis=basis)
    return Outcome.ok('OWNER_AUTHORIZED', value=transition['owner_decision_id'])


def assert_no_artifact_claims_12_of_12() -> Outcome:
    """No artifact may ASSERT that G0A is currently complete.

    PRECISION MATTERS HERE, and the first version of this guard got it wrong.
    Matching the bare string "12/12" flagged three legitimate artifacts: two
    saying "the gate REQUIRES 12/12" and one recording an owner overrule. A
    guard that fires on every run is ignored, which is worse than no guard.

    So the structured state is checked structurally, and prose is matched only
    on an ASSERTION of current status -- "G0A is/=/: 12/12" -- never on a
    requirement, a quotation or a history.
    """
    bad = []

    # 1. Structured state is authoritative and is checked structurally.
    try:
        st = json.loads(STATE.read_text())
        g = str(st.get('gates', {}).get('G0A', ''))
        if g.strip() not in ('11/12',):
            bad.append(f'PATH_C_STATE.json gates.G0A == {g!r}, expected 11/12')
    except (OSError, ValueError) as exc:
        bad.append(f'PATH_C_STATE.json unreadable: {exc}')

    for p2 in (_REPO / 'nfl').rglob('*.json'):
        if '.git' in str(p2):
            continue
        try:
            doc = json.loads(p2.read_text())
        except (OSError, ValueError, UnicodeDecodeError):
            continue

        def walk(o, path=''):
            if isinstance(o, dict):
                for k, v in o.items():
                    if 'g0a' in str(k).lower() and str(v).strip() == '12/12':
                        bad.append(f'{p2.relative_to(_REPO)}:{path}.{k} = 12/12')
                    walk(v, f'{path}.{k}')
            elif isinstance(o, list):
                for v in o:
                    walk(v, path)
        walk(doc)

    # 2. Prose: an ASSERTION of current status only.
    claim = re.compile(r'G0A\s*(?:is|=|:|status)?\s*(?:now\s+)?12\s*/\s*12',
                       re.IGNORECASE)
    excuse = re.compile(r'requir|must|never|not\b|overrul|would|until|before|'
                        r'cannot|only when|unless|target', re.IGNORECASE)
    for p2 in list((_REPO / 'nfl').rglob('*.md')) + list(_REPO.glob('*.md')):
        try:
            t = p2.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for ln in t.splitlines():
            if claim.search(ln) and not excuse.search(ln):
                bad.append(f'{p2.relative_to(_REPO)}: {ln.strip()[:100]}')

    if bad:
        return Outcome.fail(
            'ARTIFACT_CLAIMS_G0A_COMPLETE',
            f'{len(bad)} artifact(s) assert G0A is 12/12: {bad[:5]}',
            examples=bad[:10])
    return Outcome.ok(
        'NO_12_OF_12_CLAIM', value=0,
        detail='no artifact asserts G0A is complete; structured state reads '
               '11/12 and prose mentions of 12/12 are requirements or history')


def report() -> dict:
    state = json.loads(STATE.read_text())
    return {
        'q1_items': 12,
        'q2_discharged': 11,
        'q3_evidence': (
            'nfl/NFL_G0A_CHECKLIST.md records the per-item evidence. The '
            'eleven discharged items are supported by committed artifacts: '
            'source registry, capture states, provenance validation, effective '
            'scope, schedule anchoring, discharge identity, coverage, '
            'quarantine, seal ordering, identifier mapping and preflight.'),
        'q4_remaining': (
            'The real event-anchored T-90 capture proof. It requires a capture '
            'taken inside a real acceptance window, attributed to the game it '
            'was taken for, from a source authorized to serve that kind.'),
        'q5_discharging_event': {
            'game': 'NE @ SEA',
            'kickoff_utc': '2026-09-10T00:20:00Z',
            'acceptance_window_utc': '2026-09-09T22:50:00Z -> 2026-09-10T00:10:00Z',
            'requirement': 'an unattended, event-anchored run inside that '
                           'window producing a capture carrying the game_id, '
                           'from official_inactives or official_injury_report, '
                           'with raw bytes stored before parsing'},
        'q6_failure_modes': [
            'GitHub drops or delays the scheduled run past the window',
            'the origin returns a JS shell rather than data, which the HTML '
            'guard correctly refuses',
            'the capture lands in the window but carries no game_id, so it '
            'cannot be attributed and does not discharge',
            'a manual dispatch is taken inside the window -- this can NEVER '
            'discharge, by design',
            'credentials or the executor path fail'],
        'q7_any_artifact_claims_12_of_12':
            assert_no_artifact_claims_12_of_12().state.value,
        'q8_can_code_authorize_nfl1_without_owner': 'NO',
        'q8_enforced_by': 'nfl.prospective.nfl1_readiness.'
                          'assert_no_auto_authorization',
        'current_gates': state['gates'],
    }
