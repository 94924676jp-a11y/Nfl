"""The one remaining G0A requirement, named and evidenced from the artifacts.

    python3.12 -m nfl.prospective.q9shadow.g0a

WHY THIS IS GENERATED RATHER THAN TYPED. The gate reads `11/12` and a reader
then has to go and find WHICH one. A hand-written answer goes stale the moment
a capture lands; this reads the checklist, the reconciliation artifact and the
live capture registry and reports what they currently say.

NOTHING HERE WAIVES ANYTHING. The requirement is reported with its owner
verdict intact, its two open sub-points named, and the remedy identified as an
external dependency rather than more code. `waiver_requested` is False and this
module has no code path that can set it True.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome            # noqa: E402
from nfl.production import authorization as AUTH                        # noqa: E402

SPEC_VERSION = 'q9-g0a-remaining-item-1'
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'
OUT = HERE / 'Q9_G0A_REMAINING_ITEM.json'

CHECKLIST = _REPO / 'nfl' / 'NFL_G0A_CHECKLIST.md'
ROADMAP = _REPO / 'nfl' / 'NFL_EXPERIMENTAL_ROADMAP.md'
ADJUDICATION = _REPO / 'NFL_G0A_ADJUDICATION_2026-09-10.md'
RECONCILIATION = _REPO / 'nfl' / 'capture' / 't90_obligation_reconciliation.json'

# The twelve requirements, read from the roadmap table so the numbering here
# cannot drift from the numbering there.
_ROW = re.compile(r'^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$')


def requirements():
    """The twelve G0A requirements, in order, from the roadmap's own table."""
    out = {}
    for line in ROADMAP.read_text().splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= 12 and n not in out:
            out[n] = {'requirement': m.group(2).strip(),
                      'roadmap_state_2026_09_06': m.group(3).strip()}
        if len(out) == 12:
            break
    return out


def checklist_verdicts():
    """Each item's CURRENT verdict from the checklist's own verdict table."""
    out = {}
    for line in CHECKLIST.read_text().splitlines():
        m = _ROW.match(line.replace('**', ''))
        if not m:
            continue
        parts = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        n = int(parts[0])
        if 1 <= n <= 12 and n not in out:
            out[n] = {'requirement': parts[1].replace('**', '').strip(),
                      'state': parts[2].replace('**', '').replace('¹', '')
                                       .replace('²', '').replace('³', '')
                                       .strip(),
                      'evidence': (parts[3] if len(parts) > 3 else '')[:400]}
    return out


def reconciliation():
    """The T-90 obligation reconciliation as it currently stands."""
    if not RECONCILIATION.exists():
        return None
    d = json.loads(RECONCILIATION.read_text())
    missed = [o for o in d.get('obligations', [])
              if o.get('status') == 'MISSED']
    kinds = sorted({o['kind'] for o in missed})
    return {
        'artifact': str(RECONCILIATION.relative_to(_REPO)),
        'generated_at_utc': d.get('generated_at_utc'),
        'season': d.get('season'), 'week': d.get('week'),
        'status_tally': d.get('status_tally'),
        'n_obligations': d.get('n_obligations'),
        'manifest_rows_pass': d.get('manifest_rows_pass'),
        'attributed_captures': d.get('attributed_captures'),
        'n_missed': len(missed),
        'missed_kinds': kinds,
        'n_missed_with_a_nonqualifying_capture_in_window': sum(
            1 for o in missed
            if (o.get('nonqualifying_in_window_captures') or 0) > 0),
        'failing_predicate': (
            'qualifying_captures == 0 on every MISSED obligation, and '
            'nonqualifying_in_window_captures == 0 as well -- so this is not a '
            'capture taken and rejected on a technicality, and not a readiness '
            'implementation defect. Nothing was captured in the window.'),
    }


def live_registry():
    """What the capture registry says is still unmet, right now."""
    try:
        from nfl.capture import registry as REG
        o = REG.unmet_targets()
    except Exception as exc:                                  # noqa: BLE001
        return {'error': f'{type(exc).__name__}: {exc}'}
    return {k: o.get(k) for k in ('unmet', 'met', 'captured_sources',
                                  'pending_sources', 'evidence')}


def build():
    reqs, verds = requirements(), checklist_verdicts()
    gates = AUTH.gate_state()
    failing = sorted(n for n, v in verds.items()
                     if not v['state'].upper().startswith('PASS'))
    n = failing[0] if failing else None
    return {
        'artifact': 'NFL_Q9_G0A_REMAINING_ITEM',
        'spec_version': SPEC_VERSION,
        'gate_state': gates,
        'gate_reads': gates.get('G0A'),
        'n_requirements': len(reqs),
        'n_passing': len(verds) - len(failing),
        'failing_item_numbers': failing,

        'remaining_item': {
            'number': n,
            'name': reqs.get(n, {}).get('requirement')
                    or verds.get(n, {}).get('requirement'),
            'state': verds.get(n, {}).get('state'),
            'source_artifacts': {
                'numbering_and_requirement_text':
                    str(ROADMAP.relative_to(_REPO)) + ' (exit gate G0A table)',
                'current_verdict_and_evidence':
                    str(CHECKLIST.relative_to(_REPO)) + ' (Verdicts table, '
                    'footnote 1)',
                'most_recent_adjudication':
                    str(ADJUDICATION.relative_to(_REPO)),
                'machine_readable_obligations':
                    str(RECONCILIATION.relative_to(_REPO)),
                'gate_state_read_by_code':
                    'nfl/research/PATH_C_STATE.json via '
                    'nfl.production.authorization.gate_state',
            },
            'evidence': verds.get(n, {}).get('evidence'),
        },

        # The two sub-points of the owner's twelve-point discharge proof that
        # item 1 has not cleared. Named separately because they have different
        # owners and different remedies.
        'open_sub_points': {
            'point_7_attribute_the_capture_to_a_game': {
                'state': 'PARTIAL -> PROVEN ON CAPTURED BYTES',
                'what': 'a captured page must be attributed to the correct '
                        'game / team / week rather than being file-level',
                'evidence': 'TASK_REPORT_2026-09-07_G0A_ITEM1.md section 11: '
                            'the parser is proven on real captured bytes with '
                            '85 adversarial assertions and four '
                            'guard-deletion proofs',
                'blocks_item_1_now': False,
            },
            'point_12_event_anchored_execution_against_a_real_kickoff': {
                'state': 'NOT DISCHARGED',
                'what': 'an authorised, in-window, game-attributed capture '
                        'inside a real T-90 window',
                'evidence': 'the reconciliation artifact below: every MISSED '
                            'obligation has qualifying_captures == 0',
                'blocks_item_1_now': True,
            },
        },

        'root_cause': {
            'named': 'EGRESS',
            'measured': 'CONNECT www.nfl.com:443 -> 403 from the agent proxy '
                        'and from a cloud session, recorded in '
                        'NFL_G0A_CHECKLIST.md footnote 1 as measured rather '
                        'than inferred',
            'consequence': 'item 1 fails on the endpoint, and would still '
                           'fail with a perfect scheduler. More code here '
                           'moves nothing.',
            'owner_of_the_remedy': 'the agent that holds network egress',
        },

        'reconciliation': reconciliation(),
        'live_registry': live_registry(),

        'waiver_requested': False,
        'waiver_note': (
            'no waiver is requested and none is implied. The item is reported '
            'so the owner can see exactly what is outstanding and decide. '
            'This module has no code path that can mark it cleared, and a '
            'passing test suite is not a discharge.'),
        'effect_on_q9': (
            'protocol section 1: no forecast written before G0A is discharged '
            'counts toward promotion. A Q9 shadow forecast may still be '
            'COMPUTED and SEALED -- authorization.may_compute() allows that '
            'and always has -- but it accrues no promotion evidence.'),
        'independent_of': [
            'INJURY_REPORT_INCOMPLETE -- a different blocker with a different '
            'remedy; clearing G0A does not fill an unfiled report_status',
            'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED -- internal work, '
            'unaffected by either',
        ],
    }


def check() -> Outcome:
    """PASS only when nothing is outstanding. Today it is BLOCKED."""
    d = build()
    if not d['failing_item_numbers']:
        return Outcome.ok('G0A_ALL_TWELVE_PASS', value=d['gate_reads'])
    return Outcome.blocked(
        'G0A_ITEM_NOT_CLEARED',
        f'G0A reads {d["gate_reads"]}; item {d["remaining_item"]["number"]} '
        f'({d["remaining_item"]["name"]}) is '
        f'{d["remaining_item"]["state"]}. Root cause {d["root_cause"]["named"]}'
        f': {d["root_cause"]["consequence"]}',
        cause=Cause.NETWORK, item=d['remaining_item']['number'],
        gate=d['gate_reads'])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)
    d = build()
    OUT.write_text(json.dumps(d, indent=1, default=str) + '\n')
    r = d['remaining_item']
    print(f"gate reads        : {d['gate_reads']}")
    print(f"requirements      : {d['n_requirements']}, "
          f"passing {d['n_passing']}")
    print(f"remaining item    : #{r['number']}  {r['name']}")
    print(f"  state           : {r['state']}")
    print(f"  root cause      : {d['root_cause']['named']}")
    for k, v in d['open_sub_points'].items():
        print(f"  {k}: {v['state']} "
              f"(blocks now: {v['blocks_item_1_now']})")
    rec = d['reconciliation'] or {}
    print(f"  obligations     : {rec.get('status_tally')}")
    print(f"  unmet targets   : {d['live_registry'].get('unmet')}")
    print(f"  waiver requested: {d['waiver_requested']}")
    print(f"written           : {OUT}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
