"""The prospective input contract for the non-QB chain, and its gate.

THE RULE THIS ENFORCES

D2's accepted appearance mechanism consumes an injuries feed that does not yet
exist for 2026. The temptation in that situation is to emit *something* -- a
positional prior, a reduced-feature fit, last season's rate. Each would run,
each would look plausible, and each would be a different model wearing an
accepted model's name.

So the contract is explicit and the gate is structural: when a required source
is absent, the layer returns a NAMED DEFERRED state carrying the exact missing
condition, and no downstream layer will accept that as input.

FIXTURES ARE STRUCTURALLY QUARANTINED. A fixture carries `TEST_ONLY = True`
through every layer that touches it, and the artifact sealer refuses to write
any run whose inputs carry that flag. A test proves the refusal fires.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

TEST_ONLY_KEY = '_test_only'

# What the frozen appearance mechanism needs, per P3 feature group.
APPEARANCE_CONTRACT = {
    'practice_progression': {
        'source': 'injuries_{season}',
        'fields': ['season', 'week', 'gsis_id', 'report_status',
                   'practice_status'],
        'why': 'cross-week practice transition',
        'history_only': False,
    },
    'teammate_availability': {
        'source': 'injuries_{season}',
        'fields': ['season', 'week', 'team', 'gsis_id', 'report_status'],
        'why': 'vacated share by opportunity class needs to know who is out',
        'history_only': False,
    },
    'absence_history': {
        'source': 'panel history',
        'fields': ['prior appearance and workload'],
        'why': 'workload before absence, volatility',
        'history_only': True,
    },
    'role_volatility': {
        'source': 'panel history',
        'fields': ['prior share series'],
        'why': 'prior swing and instability',
        'history_only': True,
    },
}

PARTICIPATION_CONTRACT = {
    'share_history': {
        'source': 'panel_p3 (pbp_participation derived)',
        'fields': ['pass_snaps', 'team_dropbacks_part'],
        'why': 'the accepted Stage-2 estimator is ewma_hl2 over prior shares',
        'history_only': True,
    },
}


def injuries_state(season: int) -> Outcome:
    """Is a legitimate injuries feed available for this season?

    Read from the capture manifest -- the same record the capture workflow
    writes -- so this cannot drift from what was actually captured.
    """
    man = _REPO / 'nfl' / 'vintage_manifest.jsonl'
    if not man.exists():
        return Outcome.blocked('NO_MANIFEST', 'no capture manifest',
                               cause=Cause.DATA)
    seen, ok = [], []
    for line in man.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get('source') != 'injuries':
            continue
        seen.append(r.get('code'))
        v = r.get('value') or {}
        if r.get('state') == 'PASS' and str(season) in str(v.get('url', '')):
            ok.append(r)
    if ok:
        return Outcome.ok('INJURIES_AVAILABLE', value=len(ok),
                          detail=f'{len(ok)} captured injuries row(s) for '
                                 f'{season}')
    return Outcome.deferred(
        'WAITING_FOR_INJURIES_%d' % season,
        f'the injuries feed for {season} has not been published. The frozen '
        f'appearance mechanism needs practice_progression and '
        f'teammate_availability, and both come from it. No substitute is '
        f'used: a reduced-feature fit would run and would be a different '
        f'model wearing an accepted model name.',
        owed={'source': f'injuries_{season}',
              'codes_seen': sorted(set(seen))[:5],
              'unblocks': ['appearance', 'participation', 'targets_carries',
                           'receiving_conversion', 'rushing_conversion',
                           'td_layer']})


def validate_appearance_inputs(fixture: dict | None, season: int) -> Outcome:
    """Either a legitimate source, or an explicitly-marked TEST-ONLY fixture,
    or a named deferral. Never a fabricated probability."""
    if fixture is not None:
        if not fixture.get(TEST_ONLY_KEY):
            return Outcome.fail(
                'UNMARKED_FIXTURE',
                'an appearance fixture was supplied without '
                f'{TEST_ONLY_KEY}=True. A fixture that is not marked cannot '
                f'be kept out of a forecast artifact, so it is refused.')
        missing = [g for g, c in APPEARANCE_CONTRACT.items()
                   if not c['history_only'] and g not in fixture]
        if missing:
            return Outcome.fail(
                'FIXTURE_INCOMPLETE',
                f'the fixture omits required feature group(s) {missing}; a '
                f'partial fixture would exercise a different mechanism',
                missing=missing)
        return Outcome.ok('APPEARANCE_INPUTS_FIXTURE', value=fixture,
                          detail='TEST-ONLY fixture accepted for engineering '
                                 'rehearsal; it cannot reach an artifact',
                          test_only=True)
    return injuries_state(season)
