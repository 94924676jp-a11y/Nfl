#!/usr/bin/env python3.12
"""Requirement-driven product readiness. A missing component is RED, not absent.

WHY THIS REPLACES THE OLD GATE'S ROLE. `nfl/production/pregame_readiness.py` builds one row
per *declared layer*. A layer nobody wrote declares nothing, produces no row, and therefore
cannot be RED. Measured: that file contains **zero** occurrences of "DST" or "position". So
team defence -- which has no projection component anywhere in the repository -- was
invisible to the readiness matrix by construction. Three Sundays of GREEN boards were
honest about the components that existed and silent about the ones that did not.

This gate inverts the direction. It starts from a DECLARED LIST OF REQUIREMENTS and asks
each one to prove itself. Nothing proves itself by not being mentioned.

It also fixes the second half of the same failure: the old board validated a 156-player
universe while the DraftKings product needs 457. Here the universe size is a requirement
with an expected value, so a scope mismatch is a RED row rather than a footnote.
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

from sportsplatform.governance.outcome import Outcome  # noqa: E402

SPEC_VERSION = 'product-readiness-1'

GREEN, AMBER, RED = 'GREEN', 'AMBER', 'RED'

#: Positions that must have a projection pathway for a DK NFL Classic product.
REQUIRED_POSITIONS = ('QB', 'RB', 'WR', 'TE', 'DST')
OPTIONAL_POSITIONS = ('K',)

#: Stages the product requires, in dependency order. Every one gets a row every run.
REQUIRED_STAGES = (
    ('universe_identity', 'every rosterable player exists and maps correctly'),
    ('availability', 'current availability resolved or explicitly unresolved'),
    ('current_role', 'starter / backup / committee / replacement / returning / cold-start'),
    ('role_consumed_by_projection', 'the projection READS current role, not just records it'),
    ('player_prior', 'multi-season player prior with recency weighting and cold-start path'),
    ('current_usage', 'current-season observations update the prior rather than replace it'),
    ('team_volume', 'plays, dropbacks, attempts, carries, scoring environment'),
    ('opportunity', 'carries, targets, receptions, red-zone and goal-line'),
    ('efficiency', 'player/team/opponent efficiency with declared shrinkage'),
    ('td_allocation', 'shrunk rate with a floor, never a raw small-sample count'),
    ('positional_completeness', 'every required position has a pathway'),
    ('distribution', 'quantiles, not a mean alone'),
    ('joint_simulation', 'player outputs reconcile to team football within each draw'),
    ('fallback', 'declared external fallback when proprietary coverage fails'),
    ('slice_level_checks', 'level validated per position and per salary/projection tier'),
    ('historical_validation', 'forward-chained replay per layer'),
)

#: The product universe. A gate that validates a smaller universe than the product needs is
#: measuring something else -- this is why 156-vs-457 was invisible for three weeks.
EXPECTED_UNIVERSE = 457

POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
LEDGER = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJECTION_SOURCE_LEDGER.json'
V0 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V0_VS_FC.json'


def _row(stage, why, state, detail, *, blocks=True, evidence=None):
    return {'stage': stage, 'requirement': why, 'state': state, 'detail': detail,
            'blocks_product': blocks and state == RED, 'evidence': evidence or {}}


def build():
    rows, notes = [], {}
    post = json.loads(POST.read_text()) if POST.exists() else None
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else None
    v0 = json.loads(V0.read_text()) if V0.exists() else None
    players = (post or {}).get('players') or {}
    recs = (v0 or {}).get('records') or {}

    # universe
    n = len(players)
    rows.append(_row('universe_identity', REQUIRED_STAGES[0][1],
                     GREEN if n == EXPECTED_UNIVERSE else RED,
                     f'{n} rosterable rows against an expected {EXPECTED_UNIVERSE}'
                     + ('' if n == EXPECTED_UNIVERSE else
                        '. A universe smaller than the product needs means every other '
                        'row below is about a different population'),
                     evidence={'n': n, 'expected': EXPECTED_UNIVERSE}))

    # availability
    unresolved = sum(1 for v in players.values()
                     if str(v.get('current_availability', {}).get('status', ''))
                     .startswith('UNKNOWN'))
    rows.append(_row('availability', REQUIRED_STAGES[1][1],
                     GREEN if unresolved == 0 else AMBER,
                     f'{n - unresolved} of {n} resolved; {unresolved} explicitly '
                     f'unresolved (a state, not a zero)',
                     blocks=False, evidence={'unresolved': unresolved}))

    # current role exists
    with_role = sum(1 for v in players.values() if v.get('today_expected_role'))
    rows.append(_row('current_role', REQUIRED_STAGES[2][1],
                     GREEN if with_role == n else RED,
                     f'{with_role} of {n} carry a role state'))

    # role CONSUMED -- the distinction that produced Drew Lock at 17.88
    consumed = None
    if recs:
        from nfl.tools import projection_guards as G
        starters = {(v['name'], v['team']) for v in players.values()
                    if (v.get('predicted_lineup_context') or {})
                    .get('in_predicted_starting_group')}
        g = G.assert_no_stale_replacement_role(recs, players, starters)
        consumed = g.state.value == 'PASS'
        rows.append(_row('role_consumed_by_projection', REQUIRED_STAGES[3][1],
                         GREEN if consumed else RED,
                         'role state is consumed' if consumed else
                         f'{g.evidence.get("n_violations")} non-starter(s) projected at '
                         f'starter level behind an available starter, so role state is '
                         f'recorded but not read',
                         evidence={'guard': g.code}))
    else:
        rows.append(_row('role_consumed_by_projection', REQUIRED_STAGES[3][1], RED,
                         'no projection exists, so role state cannot be consumed'))

    # player prior
    rows.append(_row('player_prior', REQUIRED_STAGES[4][1], RED,
                     'no multi-season player prior is wired into any projection. The '
                     'existing V0 shrank toward a positional mean, which is what produced '
                     '62 established-role violations'))

    # current usage
    obs = sum(1 for v in players.values()
              if ((v.get('observed_2026') or {}).get('weeks')))
    rows.append(_row('current_usage', REQUIRED_STAGES[5][1],
                     GREEN if obs > 0 else RED,
                     f'{obs} of {n} players carry observed 2026 weeks',
                     blocks=False, evidence={'n_observed': obs}))

    # team volume -- RED since 2026-09-22 per the Thursday board
    rows.append(_row('team_volume', REQUIRED_STAGES[6][1], RED,
                     'denom_panel / team_volume_history newest ordinal 202518: an EWMA '
                     'whose most recent observation is 2025 week 18. Flagged RED on '
                     '2026-09-22 and unchanged'))

    # opportunity, efficiency, TD
    rows.append(_row('opportunity', REQUIRED_STAGES[7][1],
                     AMBER if recs else RED,
                     'computable from measured shares without routes, at a stated cost in '
                     'discrimination among same-snap-share receivers'
                     if recs else 'no opportunity projection exists', blocks=False))
    rows.append(_row('efficiency', REQUIRED_STAGES[8][1], AMBER,
                     'fields present for two games; needs declared shrinkage to the '
                     'existing multi-season panel', blocks=False))
    td_ok = None
    if recs:
        from nfl.tools import projection_guards as G
        g = G.assert_td_rate_not_raw_count(recs)
        td_ok = g.state.value == 'PASS'
        rows.append(_row('td_allocation', REQUIRED_STAGES[9][1],
                         GREEN if td_ok else RED,
                         'shrunk rate with a floor' if td_ok else
                         f'{g.evidence.get("n_violations")} player(s) with real volume '
                         f'carry a zero touchdown expectation'))
    else:
        rows.append(_row('td_allocation', REQUIRED_STAGES[9][1], RED,
                         'no TD allocation exists'))

    # POSITIONAL COMPLETENESS -- one row per required position, always
    cover = collections.Counter()
    fb = collections.Counter()
    for k, v in players.items():
        pos = v.get('position')
        m = (recs.get(k) or {}).get('mean')
        if isinstance(m, (int, float)):
            cover[pos] += 1
        mode = ((ledger or {}).get('records', {}).get(k) or {}).get('projection_mode')
        if mode == 'EXTERNAL_FC_FALLBACK':
            fb[pos] += 1
    pos_rows = []
    worst = GREEN
    for pos in REQUIRED_POSITIONS:
        present = sum(1 for v in players.values() if v.get('position') == pos)
        st = (GREEN if cover[pos] > 0 else
              AMBER if fb[pos] > 0 else RED)
        worst = RED if RED in (worst, st) else (AMBER if AMBER in (worst, st) else GREEN)
        pos_rows.append({'position': pos, 'rosterable': present,
                         'proprietary': cover[pos], 'fallback': fb[pos], 'state': st,
                         'detail': ('proprietary coverage' if st == GREEN else
                                    'fallback only, no proprietary component'
                                    if st == AMBER else
                                    'NO pathway of any kind')})
    for pos in OPTIONAL_POSITIONS:
        pos_rows.append({'position': pos, 'rosterable': 0, 'proprietary': 0, 'fallback': 0,
                         'state': 'NOT_REQUIRED_BY_THIS_SURFACE',
                         'detail': 'declared in advance so the gap is not discovered on a '
                                   'slate that needs it'})
    rows.append(_row('positional_completeness', REQUIRED_STAGES[10][1], worst,
                     '; '.join(f'{r["position"]}={r["state"]}' for r in pos_rows
                               if r['position'] in REQUIRED_POSITIONS),
                     evidence={'positions': pos_rows}))
    notes['positions'] = pos_rows

    # distribution
    has_q = any(isinstance((r or {}).get('p90_approx'), (int, float))
                for r in recs.values()) if recs else False
    rows.append(_row('distribution', REQUIRED_STAGES[11][1],
                     AMBER if has_q else RED,
                     'a declared normal approximation around a mean is not a simulated '
                     'distribution; quantiles are not calibrated'
                     if has_q else 'means only'))

    rows.append(_row('joint_simulation', REQUIRED_STAGES[12][1], RED,
                     'nothing built. Player outputs do not reconcile to team football '
                     'within a draw, so correlation cannot emerge from football'))

    mode = (ledger or {}).get('slate_projection_mode')
    rows.append(_row('fallback', REQUIRED_STAGES[13][1],
                     GREEN if mode else RED,
                     f'declared four-mode contract, slate running {mode}' if mode
                     else 'no declared fallback', blocks=False,
                     evidence={'mode': mode}))

    # slice level checks
    slice_ok = None
    if recs:
        from nfl.tools import fc_context as FC
        from nfl.tools import projection_guards as G
        fcr = FC.load()
        ext = {}
        if fcr.state.value == 'PASS':
            by, _, _ = FC.join_to_dk(fcr.value, players)
            ext = {k: ((x.get(FC.CONTEXT_KEY) or {}).get('FC Proj'))
                   for k, x in by.items()}
        g = G.assert_level_within_band(
            recs, ext, salaries={k: v.get('salary') for k, v in players.items()})
        slice_ok = g.state.value == 'PASS'
        rows.append(_row('slice_level_checks', REQUIRED_STAGES[14][1],
                         GREEN if slice_ok else RED,
                         'all slices in band' if slice_ok else
                         f'worst slice {g.evidence.get("worst", {}).get("slice")} at '
                         f'ratio {g.evidence.get("worst", {}).get("ratio")}',
                         evidence={'guard': g.code}))
    else:
        rows.append(_row('slice_level_checks', REQUIRED_STAGES[14][1], RED,
                         'no projection to level-check'))

    rows.append(_row('historical_validation', REQUIRED_STAGES[15][1], RED,
                     'no forward-chained replay exists for the receiving, rushing or DST '
                     'layers, because those layers do not exist'))

    have = {r['stage'] for r in rows}
    for stage, why in REQUIRED_STAGES:
        if stage not in have:
            rows.append(_row(stage, why, RED,
                             'REQUIRED STAGE PRODUCED NO ROW. A stage that reports nothing '
                             'is RED, never absent -- this is the property the old gate '
                             'lacked'))

    counts = collections.Counter(r['state'] for r in rows)
    blocking = [r['stage'] for r in rows if r['blocks_product']]
    overall = (RED if blocking else AMBER if counts[AMBER] else GREEN)
    return {
        'artifact': 'PRODUCT_READINESS',
        'spec_version': SPEC_VERSION,
        'generated_at_utc': dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'WHY_REQUIREMENT_DRIVEN': (
            'the previous gate built one row per declared layer, so a component nobody '
            'wrote produced no row and could not be RED. It contains zero occurrences of '
            '"DST" or "position". Here the requirements are declared first and each must '
            'prove itself; nothing passes by not being mentioned.'),
        'overall': overall,
        'counts': dict(counts),
        'blocking_stages': blocking,
        'n_required_stages': len(REQUIRED_STAGES),
        'n_rows': len(rows),
        'rows': rows,
        'positions': notes.get('positions'),
        'product_verdict': (
            'PRODUCT_NOT_PROPRIETARY_READY. A labelled fallback product is permitted; a '
            'proprietary one is not.' if blocking else 'PROPRIETARY_READY'),
    }


def main() -> int:
    m = build()
    out = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PRODUCT_READINESS.json'
    out.write_text(json.dumps(m, indent=2) + '\n')
    print(f"overall {m['overall']}  {m['counts']}  rows={m['n_rows']}/"
          f"{m['n_required_stages']} required stages")
    print(f"verdict: {m['product_verdict']}\n")
    for r in m['rows']:
        mark = {'GREEN': ' ', 'AMBER': '~', 'RED': 'X'}.get(r['state'], '?')
        print(f" {mark} {r['state']:6s} {r['stage']:32s} {r['detail'][:88]}")
    print('\npositional completeness:')
    for p in m['positions']:
        print(f"   {p['position']:4s} rosterable {p['rosterable']:4d}  "
              f"proprietary {p['proprietary']:4d}  fallback {p['fallback']:4d}  "
              f"{p['state']:28s} {p['detail']}")
    print(f"\nblocking: {m['blocking_stages']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


# --- stop-work rule 8: assurance may not outgrow what it assures ---------------
ASSURANCE_PAT = ('governance', 'guard', 'refus', 'invariant', 'contract', 'audit',
                 'artifact', 'manifest', 'provenance', 'seal', 'census', 'proof')
PROJECTION_PAT = ('projection', 'opportunity', 'efficiency', 'draw', 'simulat', 'prior',
                  'role', 'usage', 'volume')
MAX_RATIO = 2.0


def assurance_ratio():
    """STOP-WORK RULE 8. When assurance tests outnumber projection tests beyond the
    declared ratio, assurance work stops until the ratio recovers.

    TWO DEFENSIBLE MEASUREMENTS, AND BOTH ARE REPORTED BECAUSE THE DEFINITION MOVES THE
    NUMBER. Under the narrow reading used in the postmortem -- projection tests being only
    those matching projection/opportunity/efficiency/draw/simulat -- it is 51 against 10, a
    ratio of 5.1. Under the broader reading this function uses, which also counts
    prior/role/usage/volume as projection work, it is 53 against 20, a ratio of 2.65. The
    function deliberately uses the GENEROUS definition, so the rule fires only when the
    inversion is undeniable. Both numbers exceed the maximum; the narrow one is the more
    honest description of how little of the assurance effort was aimed at the football.
    """
    d = _REPO / 'nfl/tests'
    files = sorted(p.name for p in d.glob('test_*.py'))
    a = [f for f in files if any(k in f.lower() for k in ASSURANCE_PAT)]
    p = [f for f in files if any(k in f.lower() for k in PROJECTION_PAT)]
    ratio = (len(a) / len(p)) if p else float('inf')
    if ratio > MAX_RATIO:
        return Outcome.fail(
            'ASSURANCE_OUTGREW_WHAT_IT_ASSURES',
            f'{len(a)} assurance test files against {len(p)} projection test files, a '
            f'ratio of {ratio:.1f} above the declared maximum {MAX_RATIO}. New audit, '
            f'census and proof tooling stops until the ratio recovers.',
            n_assurance=len(a), n_projection=len(p), ratio=round(ratio, 2),
            max_ratio=MAX_RATIO, n_test_files=len(files))
    return Outcome.ok('ASSURANCE_RATIO_HEALTHY', round(ratio, 2),
                      f'{len(a)} assurance to {len(p)} projection, ratio {ratio:.1f}',
                      n_assurance=len(a), n_projection=len(p))
