"""The 2026 evidence input Stage 6 was missing, with its PIT contract.

THE CONTRACT, AND IT IS THE WHOLE POINT

For a forecast at week N, only weeks **strictly less than N** may contribute.
Enforced twice and refused loudly, not filtered quietly:

1. `usage_vintage.usage_season(season, as_of, before_week=N)` selects the
   widest LAWFUL play-by-play capture -- one whose retrieval clock is at or
   before the information cut -- and drops every week >= N.
2. `assert_pit(...)` below re-derives the maximum week present and REFUSES if
   anything at or after N survived. A silent filter that worked yesterday and
   stops working tomorrow is the defect class this project pays for most, so
   the assertion is separate from the filter and does not trust it.

WHY `usage_vintage` AND NOT `current_season_nonqb_panel`

They implement the same counting rules -- `usage_vintage` imports them by
reference rather than restating them -- but they read different stores.
Measured at cut 2026-09-21T23:05Z: the accepted panel globs
`nfl/research/postgame/` and sees 10 of week 1's 16 games, covering 20 clubs.
`usage_vintage` reads the governed vintage store as well and sees all 16, all
32 clubs. **`2026_01_DAL_NYG` is one of the six the accepted panel cannot
see**, so on the narrower source Cam Skattebo's 18 carries do not exist and
the repair would have failed silently on the very player it was built for.

Absence from a corpus is not zero usage. The wider source is used and the
discrepancy is carried on the outcome.

SNAPS ARE A SEPARATE AXIS AND STAY SEPARATE

PFR snap counts give `offense_pct` and `offense_snaps`; play-by-play gives
carries and targets. They answer different questions -- how much of the
offence he was on the field for, versus how much of it came to him -- and a
player can be high on one and low on the other. They are returned as separate
fields on the same row, never merged into a single "usage" number.
"""
from __future__ import annotations

import collections
import pathlib
import sys
from typing import Any, Dict, List, Optional

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import role_state as RS               # noqa: E402
from nfl.production.universe import usage_vintage as UV            # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'current-season-evidence-1'

#: States this module can report about a season's evidence. `ABSENT` is a real
#: and legitimate state -- week 1 has no prior week -- and is not an error.
PRESENT = 'CURRENT_SEASON_EVIDENCE_PRESENT'
ABSENT = 'CURRENT_SEASON_EVIDENCE_ABSENT_NO_PRIOR_WEEK'
STALE = 'CURRENT_SEASON_INPUT_STALE'


def assert_pit(rows, *, before_week: int) -> Outcome:
    """Re-derive that nothing at or after the forecast week survived.

    Deliberately does not trust the filter that produced `rows`.
    """
    weeks = sorted({int(w) for (w, _t, _p) in rows}) if rows else []
    leaked = [w for w in weeks if w >= int(before_week)]
    if leaked:
        return Outcome.fail(
            'CURRENT_SEASON_EVIDENCE_LEAKS_FORWARD',
            f'week(s) {leaked} are at or after the forecast week '
            f'{before_week} and would put a game inside its own evidence. '
            f'This is checked here rather than assumed from the filter above.',
            value={'weeks_present': weeks, 'before_week': int(before_week)})
    return Outcome.ok(
        'CURRENT_SEASON_EVIDENCE_IS_POINT_IN_TIME',
        {'weeks_present': weeks, 'before_week': int(before_week),
         'max_week_used': max(weeks) if weeks else None},
        detail=f'weeks {weeks} all strictly before {before_week}')


def collect(season: int, week: int, as_of: str, *,
            clubs=None) -> Outcome:
    """Per-player current-season measured evidence, strictly before `week`.

    Returns one record per (player, week) with the usage axis and the snap
    axis kept apart, plus the provenance of both sources.
    """
    if int(week) <= 1:
        return Outcome.ok(
            ABSENT,
            {'by_player': {}, 'n_players': 0, 'n_rows': 0,
             'weeks_present': [], 'sources': {},
             'spec_version': SPEC_VERSION},
            detail=f'{season} week {week} has no prior week in the same '
                   f'season; this is a state, not a failure')

    uo = UV.usage_season(season, as_of, before_week=week)
    if uo.state.name != 'PASS':
        return uo
    usage = uo.value

    pit = assert_pit(usage, before_week=week)
    if pit.state.name != 'PASS':
        return pit

    so = RS.load_snaps(season, week)
    snaps_by_pfr: Dict[str, List[dict]] = collections.defaultdict(list)
    snap_state = {'state': so.state.name, 'code': so.code}
    if so.state.name == 'PASS':
        for r in so.value:
            w = r.get('week')
            try:
                wi = int(w)
            except (TypeError, ValueError):
                continue
            if wi >= int(week):
                continue
            if r.get('pfr_player_id'):
                snaps_by_pfr[r['pfr_player_id']].append({
                    'week': wi, 'team': r.get('team'),
                    'offense_pct': r.get('offense_pct'),
                    'offense_snaps': r.get('offense_snaps'),
                    'st_pct': r.get('st_pct'),
                    'position_in_snap_file': (r.get('position') or '').upper()})
        snap_state['n_players'] = len(snaps_by_pfr)
        snap_state['weeks'] = sorted({s['week'] for v in snaps_by_pfr.values()
                                      for s in v})

    by_player: Dict[str, List[dict]] = collections.defaultdict(list)
    for (w, club, pid), row in sorted(usage.items()):
        if clubs and club not in clubs:
            continue
        by_player[pid].append({
            'week': int(w), 'team': club,
            'carries': float(row.get('carries') or 0.0),
            'targets': float(row.get('targets') or 0.0),
            'receptions': float(row.get('receptions') or 0.0),
            'carry_share': row.get('carry_share'),
            'target_share': row.get('target_share'),
            'rz_carries': float(row.get('rz_carries') or 0.0),
            'appeared_by_opportunity': (float(row.get('carries') or 0.0)
                                        + float(row.get('targets') or 0.0)) > 0,
        })

    if not by_player:
        return Outcome.fail(
            'CURRENT_SEASON_EVIDENCE_EMPTY',
            f'the lawful capture for {season} before week {week} produced no '
            f'player rows. An empty evidence set read as "nobody did '
            f'anything" is the failure mode this project pays for most.',
            value={'sources': {'usage': uo.code}})

    return Outcome.ok(
        PRESENT,
        {'by_player': dict(by_player),
         'snaps_by_pfr': dict(snaps_by_pfr),
         'n_players': len(by_player),
         'n_rows': sum(len(v) for v in by_player.values()),
         'weeks_present': pit.value['weeks_present'],
         'max_week_used': pit.value['max_week_used'],
         'sources': {
             'usage': {
                 'code': uo.code, 'blob': uo.evidence.get('blob'),
                 'clock': uo.evidence.get('clock'),
                 'store': uo.evidence.get('store'),
                 'n_games': uo.evidence.get('n_games'),
                 'clubs': len(uo.evidence.get('clubs') or []),
                 'accepted_panel_sees_n_games':
                     uo.evidence.get('accepted_panel_sees_n_games'),
                 'games_the_accepted_panel_cannot_see':
                     uo.evidence.get('games_the_accepted_panel_cannot_see'),
                 'counting_imported_from':
                     uo.evidence.get('counting_imported_from')},
             'snaps': snap_state},
         'pit': pit.value,
         'spec_version': SPEC_VERSION},
        detail=f'{len(by_player)} player(s), weeks '
               f'{pit.value["weeks_present"]}, from {uo.evidence.get("blob")}')


def declared_blocked_inputs() -> Dict[str, str]:
    """Registered current-season inputs that are DECLARED stale, by name.

    These are knowable before a single world is drawn -- they are a property
    of the registry, not of this run -- so a forecast that will certainly
    refuse at sealing can refuse here instead. `denom_panel` is the live
    example: `CURRENT_SEASON_SOURCE_UNVERIFIED`, blocked deliberately because
    the 2026 source's vintage, completeness and identity behaviour are not
    established and a partial denominator produces confidently wrong shares
    rather than a nameable refusal.
    """
    from nfl.production import freshness as FRESH
    return {k: v['declared_blocked'] for k, v in FRESH.REGISTRY.items()
            if v.get('declared_blocked')}


def assert_fresh(ev: Outcome, *, season: int, week: int,
                 claims_current_season: bool = True,
                 check_declared_blocked: bool = True,
                 allow_known_stale_for_diagnostic: bool = False,
                 verified_inputs=None) -> Outcome:
    """The upstream freshness gate. Refuse BEFORE simulation, not at sealing.

    `current_season_input_freshness` already refused the old run -- at
    artifact sealing, after 318 seconds of worlds nobody could use. This is
    the same protection moved to where it costs nothing.
    """
    if not claims_current_season:
        return Outcome.not_applicable(
            'DOES_NOT_CLAIM_CURRENT_SEASON_OPPORTUNITY',
            'this run does not claim to model current-season opportunity, so '
            'current-season input freshness is not a requirement of it')
    if ev.state.name != 'PASS':
        return Outcome.blocked(
            STALE,
            f'current-season evidence is {ev.state.name}[{ev.code}] and this '
            f'forecast claims to model current-season opportunity. Refusing '
            f'before simulation rather than after it.',
            cause=Cause.DATA, value={'evidence_code': ev.code})
    if ev.code == ABSENT:
        return Outcome.ok(
            'CURRENT_SEASON_INPUT_NOT_REQUIRED_IN_WEEK_1',
            {'week': int(week)},
            detail=f'{season} week {week} has no prior week; there is nothing '
                   f'stale about evidence that cannot exist yet')
    mx = ev.value.get('max_week_used')
    if mx is None or int(mx) != int(week) - 1:
        return Outcome.blocked(
            STALE,
            f'the newest current-season week available is {mx}, and a week-'
            f'{week} forecast needs week {int(week) - 1}. Producing worlds '
            f'from evidence that stops short of the forecast is spending time '
            f'on a run already known to be invalid.',
            cause=Cause.DATA,
            value={'max_week_used': mx, 'week': int(week),
                   'weeks_present': ev.value.get('weeks_present')})
    # THE SEALING GATE IS BROADER THAN THE OPPORTUNITY EVIDENCE, and an
    # upstream gate narrower than the one it was meant to move earlier is not
    # the protection it claims to be. Measured: the CS6 run passed this check
    # on opportunity evidence and then refused at sealing anyway, after 302
    # seconds, on `denom_panel` and `team_volume_history`. Those are a
    # property of the registry and knowable now.
    blocked = declared_blocked_inputs() if check_declared_blocked else {}
    # A declared block that THIS RUN has verified is not a block. The
    # verification is a passing Outcome from a verifier that measured
    # completeness, not a flag.
    verified = {k: v for k, v in (verified_inputs or {}).items()
                if getattr(getattr(v, 'state', None), 'name', None) == 'PASS'}
    blocked = {k: v for k, v in blocked.items() if k not in verified}
    if blocked and not allow_known_stale_for_diagnostic:
        return Outcome.blocked(
            STALE,
            f'{len(blocked)} registered current-season input(s) are DECLARED '
            f'stale and will refuse at sealing: '
            f'{sorted(blocked)} ({sorted(set(blocked.values()))}). Refusing '
            f'now rather than after a full simulation. A measurement run may '
            f'pass allow_known_stale_for_diagnostic=True; what it produces is '
            f'NOT PUBLISHABLE.',
            cause=Cause.DATA,
            value={'declared_blocked': blocked, 'max_week_used': mx,
                   'opportunity_evidence': 'FRESH'})
    return Outcome.ok(
        'CURRENT_SEASON_INPUT_FRESH',
        {'max_week_used': mx, 'week': int(week),
         'n_players': ev.value.get('n_players'),
         'sources': ev.value.get('sources'),
         'declared_blocked': blocked,
         'verified_this_run': {k: getattr(v, 'code', None)
                               for k, v in verified.items()},
         'publishable': not blocked,
         'diagnostic_override_used': bool(blocked and
                                          allow_known_stale_for_diagnostic)},
        detail=(f'week {mx} evidence present for a week-{week} forecast'
                + (f'; NON-PUBLISHABLE diagnostic override over '
                   f'{sorted(blocked)}' if blocked else '')))
