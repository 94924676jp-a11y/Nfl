#!/usr/bin/env python3.12
"""Governed projection-source contract. One missing component must not kill the product.

THE FAILURE MODE THIS EXISTS TO PREVENT. Today the proprietary player-outcome layer is
incomplete, and the consequence was that the whole slate produced nothing. That is the
wrong product behaviour. A missing positional model should degrade the product's *label*,
not its existence, and it must never silently remove a position or turn a player into a
zero.

FOUR MODES, AND THE MODE IS RECORDED PER PLAYER, NOT PER SLATE.

    PROPRIETARY            our own distribution
    EXTERNAL_FC_FALLBACK   an authorised external number, labelled as external
    BLENDED_RESEARCH_MODE  a declared combination -- NOT AUTHORISED, see below
    PROJECTION_UNAVAILABLE neither exists. This is a state, never 0.00

`PROJECTION_UNAVAILABLE` is the whole point. A player with no proprietary number and no
authorised fallback is not worth zero points; he is a player we cannot project. Zero is a
football claim and we are not entitled to make it.

BLENDED_RESEARCH_MODE IS DEFINED AND REFUSED. It is in the enum because the owner named
it, and `resolve` raises on it, because blending FC into a proprietary number is exactly
the contamination the firewall exists to stop. It stays unreachable until an owner ruling
says otherwise and says how the blend is weighted and audited.

WHAT FALLBACK MODE DOES NOT TOUCH. In EXTERNAL_FC_FALLBACK the external source supplies
*numbers only*. The player universe, identity resolution, availability, post-inactives
role redistribution, game environment, correlation structure, stacking, scenario
generation, ownership and portfolio construction all remain ours. FC is a column, not a
model, and it never becomes a feature: the values are read through `fc_context`, which
refuses outright if a proprietary module is on the import graph.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import fc_context as FC  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'projection-source-1'

MODE_PROPRIETARY = 'PROPRIETARY'
MODE_FC_FALLBACK = 'EXTERNAL_FC_FALLBACK'
MODE_BLENDED = 'BLENDED_RESEARCH_MODE'
MODE_UNAVAILABLE = 'PROJECTION_UNAVAILABLE'
MODES = (MODE_PROPRIETARY, MODE_FC_FALLBACK, MODE_BLENDED, MODE_UNAVAILABLE)

#: Modes an owner has authorised for this slate.
AUTHORISED_TODAY = (MODE_PROPRIETARY, MODE_FC_FALLBACK, MODE_UNAVAILABLE)

NEVER_ZERO = (
    'a missing projection is PROJECTION_UNAVAILABLE. It is never 0.00, never dropped and '
    'never omitted from a count. Zero points is a football claim; absence of a number is '
    'not.')

FALLBACK_SCOPE = (
    'in EXTERNAL_FC_FALLBACK the external source supplies the numerical mean, floor and '
    'ceiling only. Player universe, identity, availability, post-inactives '
    'redistribution, game environment, correlation, stacking, scenario generation, '
    'ownership and portfolio construction remain entirely ours.')

#: DraftKings NFL Classic roster. There is no kicker slot, so K is not required by this
#: product surface -- but the pathway is documented rather than left undefined, because
#: "we never built it" and "this slate does not need it" are different answers.
ROSTER_POSITIONS = ('QB', 'RB', 'WR', 'TE', 'DST')
POSITIONS_DOCUMENTED = ROSTER_POSITIONS + ('K',)

POSITION_PATHWAYS = {
    'QB': {'required_by_dk_classic': True, 'proprietary_component': 'QB v1 / R2 level',
           'status': 'PRE_R2_INTERMEDIATE_ONLY',
           'why': ('the held QB layer is a conditional pre-R2 intermediate containing no '
                   '2026 information, so it is not a week-3 per-player expectation.')},
    'RB': {'required_by_dk_classic': True, 'proprietary_component': 'rushing layer',
           'status': 'CONTRACT_DECLARED_LAYER_ABSENT',
           'why': 'player_draws reports the rushing layer absent.'},
    'WR': {'required_by_dk_classic': True, 'proprietary_component': 'receiving layer',
           'status': 'CONTRACT_DECLARED_LAYER_ABSENT',
           'why': ('receiving is absent and its accepted arm needs participation, which '
                   'is 404 for 2026.')},
    'TE': {'required_by_dk_classic': True, 'proprietary_component': 'receiving layer',
           'status': 'CONTRACT_DECLARED_LAYER_ABSENT',
           'why': 'same layer as WR.'},
    'DST': {'required_by_dk_classic': True, 'proprietary_component': 'none built',
            'status': 'NEVER_IMPLEMENTED',
            'why': ('no team-defence projection component exists at all. This is the '
                    'position most likely to be silently forgotten, because it has no '
                    'player-level features to notice the absence of.')},
    'K': {'required_by_dk_classic': False, 'proprietary_component': 'none built',
          'status': 'NOT_REQUIRED_BY_THIS_SLATE_PATHWAY_UNDEFINED',
          'why': ('DK NFL Classic has no kicker slot, so today nothing is missing. If a '
                  'product surface ever needs kickers, this row is the record that no '
                  'pathway exists yet -- so the gap is declared in advance rather than '
                  'discovered on a slate that needs it.')},
}


class BlendedModeRefused(RuntimeError):
    """BLENDED_RESEARCH_MODE is defined but not authorised."""


def resolve(player, proprietary=None, fc=None, *, mode_preference=MODE_PROPRIETARY):
    """One player's projection record with explicit provenance.

    `proprietary` is our own distribution dict, or None. `fc` is the external context
    block, or None. The returned record always carries a mode and never a bare number.
    """
    if mode_preference == MODE_BLENDED:
        raise BlendedModeRefused(
            'BLENDED_RESEARCH_MODE is not authorised. Combining an external projection '
            'with a proprietary one is the contamination the firewall exists to prevent, '
            'and no ruling defines the weighting or the audit trail for it.')
    av = player['current_availability']
    base = {
        'dk_id': player['dk_id'], 'player': player['name'],
        'position': player['position'], 'team': player['team'],
        'salary': player['salary'],
        'availability_state': av['status'],
        'availability_tier': av['evidence_tier'],
        'NEVER_ZERO': NEVER_ZERO,
    }
    if proprietary and mode_preference == MODE_PROPRIETARY:
        return base | {
            'projection_mode': MODE_PROPRIETARY,
            'is_proprietary': True,
            'source': 'nfl proprietary player-outcome layer',
            'source_timestamp': proprietary.get('generated_at_utc'),
            'mean': proprietary.get('mean'), 'median': proprietary.get('median'),
            'p75': proprietary.get('p75'), 'p90': proprietary.get('p90'),
            'floor': proprietary.get('floor'), 'ceiling': proprietary.get('ceiling'),
            'uncertainty_treatment': proprietary.get(
                'uncertainty_treatment', 'FULL_SIMULATED_DISTRIBUTION'),
        }
    ctx = (fc or {}).get(FC.CONTEXT_KEY) or {}
    mean = ctx.get('FC Proj')
    if mean is not None:
        return base | {
            'projection_mode': MODE_FC_FALLBACK,
            'is_proprietary': False,
            'source': (fc or {}).get('source'),
            'source_sha256': (fc or {}).get('source_sha256'),
            'source_timestamp': (fc or {}).get('retrieved'),
            'mean': mean, 'median': None, 'p75': None, 'p90': None,
            'floor': ctx.get('Floor'), 'ceiling': ctx.get('Ceiling'),
            'uncertainty_treatment': (
                'EXTERNAL_POINT_PLUS_EXTERNAL_FLOOR_CEILING. A floor and a ceiling are '
                'not a distribution: they carry no shape, no quantiles and no '
                'correlation. Treat this as a point estimate with a declared range, and '
                'do not compute a percentile from it.'),
            'FALLBACK_SCOPE': FALLBACK_SCOPE,
            'NOT_OUR_MODEL': (
                'this number is FantasyCruncher. It is authorised as a temporary '
                'numerical baseline and must never be described as our projection.'),
        }
    return base | {
        'projection_mode': MODE_UNAVAILABLE,
        'is_proprietary': False,
        'source': None, 'source_timestamp': None,
        'mean': MODE_UNAVAILABLE, 'median': MODE_UNAVAILABLE,
        'p75': MODE_UNAVAILABLE, 'p90': MODE_UNAVAILABLE,
        'floor': MODE_UNAVAILABLE, 'ceiling': MODE_UNAVAILABLE,
        'uncertainty_treatment': 'NONE_HELD',
        'why_unavailable': (
            'no proprietary distribution and no row in the authorised external source. '
            'He remains in the universe with an explicit state rather than being dropped '
            'or scored zero.'),
    }


# --- guards ------------------------------------------------------------------
def assert_no_silent_zero(records):
    """A record may not present 0.0 as a projection when its mode is UNAVAILABLE."""
    bad = [r['player'] for r in records
           if r['projection_mode'] == MODE_UNAVAILABLE
           and any(r.get(f) in (0, 0.0) for f in ('mean', 'floor', 'ceiling'))]
    if bad:
        return Outcome.fail(
            'PROJECTION_UNAVAILABLE_RENDERED_AS_ZERO',
            f'{len(bad)} unavailable projections carry a numeric zero: {bad[:8]}',
            players=bad[:40], n=len(bad))
    return Outcome.ok('NO_SILENT_ZERO', len(records),
                      f'{len(records)} records, no unavailable projection shown as zero')


def assert_fallback_is_labelled(records):
    """Every external number must be marked non-proprietary and carry its source."""
    bad = []
    for r in records:
        if r['projection_mode'] != MODE_FC_FALLBACK:
            continue
        if r.get('is_proprietary') is not False or not r.get('source') \
                or 'NOT_OUR_MODEL' not in r:
            bad.append(r['player'])
    if bad:
        return Outcome.fail(
            'EXTERNAL_PROJECTION_NOT_LABELLED',
            f'{len(bad)} fallback records could be mistaken for proprietary output: '
            f'{bad[:8]}', players=bad[:40], n=len(bad))
    return Outcome.ok('FALLBACK_LABELLED', len(records),
                      'every external number is marked non-proprietary with its source')


def assert_no_position_silently_dropped(records, players):
    """Every rosterable position must still be represented after resolution."""
    have = {r['position'] for r in records}
    want = {v['position'] for v in players.values()}
    lost = sorted(want - have)
    if lost:
        return Outcome.fail(
            'POSITION_SILENTLY_DROPPED',
            f'positions present in the universe but absent from the projection layer: '
            f'{lost}. A position must degrade to PROJECTION_UNAVAILABLE, never vanish.',
            lost=lost)
    counts = collections.Counter(r['position'] for r in records)
    return Outcome.ok('ALL_POSITIONS_PRESENT', dict(counts),
                      f'{len(have)} positions represented: {sorted(have)}')


def readiness_matrix(records, players):
    rows = []
    for pos in sorted({v['position'] for v in players.values()}):
        recs = [r for r in records if r['position'] == pos]
        n = len(recs)
        prop = sum(1 for r in recs if r['projection_mode'] == MODE_PROPRIETARY)
        fb = sum(1 for r in recs if r['projection_mode'] == MODE_FC_FALLBACK)
        un = sum(1 for r in recs if r['projection_mode'] == MODE_UNAVAILABLE)
        cold = sum(1 for r in recs
                   if (players[r['dk_id']].get('coverage_state') or '')
                   .startswith('FEATURES_NO_PRIOR'))
        resolved = sum(1 for r in recs
                       if r['availability_state'] != AV.UNKNOWN_NOT_RELAYED)
        path = POSITION_PATHWAYS.get(pos, {})
        rows.append({
            'position': pos, 'rosterable_players': n,
            'proprietary_projection_count': prop,
            'external_fallback_count': fb,
            'unavailable_count': un,
            'cold_start_count': cold,
            'availability_resolved_count': resolved,
            'projection_source_coverage_pct': round(100 * (prop + fb) / n, 1) if n else 0,
            'proprietary_coverage_pct': round(100 * prop / n, 1) if n else 0,
            'simulation_ready_pct': 0.0,
            'simulation_ready_note': (
                'zero by construction: simulation readiness needs a distribution, and a '
                'point estimate with a floor and a ceiling is not one. Fallback mode can '
                'score a lineup; it cannot simulate a joint outcome.'),
            'blocker': path.get('status', 'UNDOCUMENTED_POSITION'),
            'blocker_why': path.get('why'),
        })
    # K is documented even though the slate has none, so the gap is declared not found
    rows.append({
        'position': 'K', 'rosterable_players': 0,
        'proprietary_projection_count': 0, 'external_fallback_count': 0,
        'unavailable_count': 0, 'cold_start_count': 0,
        'availability_resolved_count': 0,
        'projection_source_coverage_pct': None, 'proprietary_coverage_pct': None,
        'simulation_ready_pct': None,
        'simulation_ready_note': 'not applicable to DK NFL Classic, which has no K slot',
        'blocker': POSITION_PATHWAYS['K']['status'],
        'blocker_why': POSITION_PATHWAYS['K']['why'],
    })
    return rows


def run(mode=MODE_FC_FALLBACK):
    post_p = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
    post = json.loads(post_p.read_text())
    players = post['players']
    fcr = FC.load()
    if fcr.state is not State.PASS:
        return fcr
    fc_by_id, _, _ = FC.join_to_dk(fcr.value, players)

    records = [resolve(v, proprietary=None, fc=fc_by_id.get(dk_id),
                       mode_preference=MODE_PROPRIETARY)
               for dk_id, v in players.items()]

    guards = {}
    for name, fn in (('no_silent_zero', lambda: assert_no_silent_zero(records)),
                     ('fallback_labelled',
                      lambda: assert_fallback_is_labelled(records)),
                     ('no_position_dropped',
                      lambda: assert_no_position_silently_dropped(records, players))):
        r = fn()
        guards[name] = r.as_dict()
        if r.state is not State.PASS:
            return r

    counts = collections.Counter(r['projection_mode'] for r in records)
    art = {
        'artifact': 'DK_WEEK3_PROJECTION_SOURCE_LEDGER',
        'spec_version': SPEC_VERSION,
        'generated_at_utc': dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'slate_projection_mode': mode,
        'MODE_AUTHORISATION': {
            'authorised_today': list(AUTHORISED_TODAY),
            'blended_refused': (
                'BLENDED_RESEARCH_MODE is defined and unreachable. resolve() raises on '
                'it because no ruling defines its weighting or audit trail.'),
            'slate_is_not_proprietary': (
                'this slate may NOT be described as proprietary. '
                f'{counts[MODE_PROPRIETARY]} of {len(records)} players carry a '
                f'proprietary number.')},
        'NEVER_ZERO': NEVER_ZERO,
        'FALLBACK_SCOPE': FALLBACK_SCOPE,
        'MY_PROJ_IS_FC': FC.MY_PROJ_IS_FC,
        'mode_counts': dict(counts),
        'guards': guards,
        'readiness_matrix': readiness_matrix(records, players),
        'position_pathways': POSITION_PATHWAYS,
        'records': {r['dk_id']: r for r in records},
        'upstream': {'post_state_sha256': __import__('hashlib').sha256(
            post_p.read_bytes()).hexdigest(), 'fc_sha256': fcr.evidence['sha256']},
    }
    out = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJECTION_SOURCE_LEDGER.json'
    out.write_text(json.dumps(art, indent=2) + '\n')
    return Outcome.ok('PROJECTION_SOURCE_LEDGER', art,
                      f'{len(records)} records in {mode}', counts=dict(counts))


def main() -> int:
    r = run()
    print(r)
    if r.state is not State.PASS:
        return 1
    v = r.value
    print('\nmode counts:', v['mode_counts'])
    print('\n{:5s} {:>6s} {:>6s} {:>6s} {:>6s} {:>6s} {:>7s}  {}'.format(
        'pos', 'n', 'prop', 'fb', 'unav', 'cold', 'cov%', 'blocker'))
    for row in v['readiness_matrix']:
        print('{:5s} {:>6} {:>6} {:>6} {:>6} {:>6} {:>7}  {}'.format(
            row['position'], row['rosterable_players'],
            row['proprietary_projection_count'], row['external_fallback_count'],
            row['unavailable_count'], row['cold_start_count'],
            str(row['projection_source_coverage_pct']), row['blocker']))
    for name, g in v['guards'].items():
        print(f'  guard {name:22s} {g["state"]} {g["code"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
