"""Active-roster status for the allocation pool. R5.

THE DEFECT THIS EXISTS FOR, MEASURED RATHER THAN ARGUED.

The P4C weight `C` is an EWMA of a player's prior **appeared** class shares --
a share CONDITIONAL ON HIM PLAYING. The allocator consumes it as a relative
weight over whatever player list it is handed. Historically those two agree,
because the fitting panel contains only players who actually appeared: 14.6
WR/TE/RB per team-game, and their C values sum to 1.24.

Prospectively the entrypoint hands it the whole weekly roster. For
2026_01_SF_LA that is 22 and 23 players, whose C values sum to **2.25 and
2.04**. The simplex normalises by that sum, so every genuine starter share is
divided by roughly two. Measured consequence on the sealed forecast: the lead
receiver draws 15.9% of his team's targets against a historical realised 29.3%,
and the top three draw 31-34% against a realised 65.5%.

The surplus is not "backups". Of the 45 SF/LA WR/TE/RB rows in the roster
capture, **29 are ACT, 10 are DEV (practice squad), 3 are RES (reserve/injured)
and 3 are CUT.** Players who have been cut were competing for targets.

Filtering to ACT returns the pool to 14 and 15 -- the size the estimator was
fitted on -- WITHOUT deleting anyone who could take a snap. That is the
difference between removing contamination and forcing concentration.

WHY THIS NEEDS ITS OWN MODULE AND ITS OWN REFUSAL.

`status` exists in the raw nflverse weekly-roster download and is DROPPED by
the vintage reduction, which keeps only season/week/team/gsis_id/position. So
the field is available for a capture whose raw blob was retained and absent
otherwise, and this module says which rather than guessing. Retaining `status`
in the reduction is a capture-layer change and is NOT made here.
"""
from __future__ import annotations

import csv
import pathlib

from sportsplatform.governance.outcome import Cause, Outcome

_REPO = pathlib.Path(__file__).resolve().parents[3]
RAW = _REPO / 'nfl_vintage' / 'raw'

# nflverse roster status codes. ACT is the active roster; everything else is a
# player who cannot take an offensive snap this week.
ACTIVE = 'ACT'
EXCLUDED = {'DEV': 'practice squad / developmental',
            'RES': 'reserve or injured reserve',
            'CUT': 'released',
            'EXE': 'exempt list'}

# POST-HOC, AND IT MUST NEVER REACH A PREGAME POOL.
#
# `weekly_rosters.status` is quarantined in nfl/ingest/allowlist.py as POSTHOC
# because INA is a GAMEDAY OUTCOME: measured ACT -> 0.9715 snap rate, INA -> 0
# of 3,438. This module's use of the field is lawful only for the codes that
# describe roster membership BEFORE the game -- DEV, RES, CUT, EXE -- and INA
# is not one of them.
#
# Measured on the live mirror at 2026-09-10T21:08Z, three and a half hours
# before the SF@LA kickoff: 14 INA rows league-wide in week 1, all belonging to
# teams whose games had ALREADY been played, and ZERO for SF or LA. So an INA
# row for a team in scope is not merely undesirable data -- it is proof that
# the capture is post-kickoff for that team.
#
# Before this guard, `active_pool` dropped any non-ACT code and labelled it
# "not on the active roster", so an INA player would have been filtered out
# silently, under a generic label, using the outcome. It did not bite tonight
# only because SF and LA have not played yet.
POSTHOC = {'INA': 'inactive for a game that has already been played -- a '
                  'gameday outcome, not roster membership'}

SPEC_VERSION = 'roster-status-active-pool-r5'


def _raw_rosters():
    return sorted(RAW.glob('weekly_rosters.*.csv'))


def status_map(season: int, week: int, teams, observed_before=None) -> Outcome:
    """gsis_id -> roster status, from a raw roster capture.

    `observed_before` is the chronology cut. A status read from a capture taken
    after kickoff is not pre-kickoff information, and this refuses rather than
    quietly using it.
    """
    files = _raw_rosters()
    if not files:
        return Outcome.blocked(
            'ROSTER_STATUS_UNAVAILABLE',
            'no raw weekly-roster capture is retained, and the reduced vintage '
            'drops the `status` column. The active-roster pool cannot be '
            'formed. Retaining `status` in the vintage reduction is a '
            'capture-layer change and is not made from here.',
            cause=Cause.DATA, spec_version=SPEC_VERSION)

    from nfl.research.shadow import information_set as IS
    try:
        first = IS.first_observation()
    except Exception:                                        # noqa: BLE001
        first = {}
    by_sha = {sha: o for (src, sha), o in first.items()
              if src == 'weekly_rosters'}

    chosen, chosen_at = None, None
    for f in files:
        stem = f.name.split('.')[1]
        obs = next((o for sha, o in by_sha.items() if sha.startswith(stem)),
                   None)
        if obs is None:
            continue
        at = obs['observed_at'].isoformat().replace('+00:00', 'Z')
        if observed_before and at >= observed_before:
            continue
        if chosen_at is None or at > chosen_at:
            chosen, chosen_at = f, at
    if chosen is None:
        return Outcome.blocked(
            'ROSTER_STATUS_NO_ELIGIBLE_VINTAGE',
            f'no raw roster capture was observed before {observed_before}. A '
            f'later capture exists but using it would put post-cut information '
            f'into a pregame pool.',
            cause=Cause.DATA, spec_version=SPEC_VERSION)

    out, counts = {}, {}
    for r in csv.DictReader(open(chosen, 'rt')):
        if (r.get('season') != str(season) or r.get('week') != str(week)
                or r.get('team') not in teams or not r.get('gsis_id')):
            continue
        st = (r.get('status') or '').strip().upper()
        out[r['gsis_id']] = st
        counts[st] = counts.get(st, 0) + 1
    if not out:
        return Outcome.blocked(
            'ROSTER_STATUS_EMPTY',
            f'{chosen.name} carries no {season} week {week} rows for '
            f'{sorted(teams)}', cause=Cause.DATA, spec_version=SPEC_VERSION)
    contaminated = {st: n for st, n in counts.items() if st in POSTHOC}
    if contaminated:
        who = sorted(pid for pid, st in out.items() if st in POSTHOC)
        return Outcome.fail(
            'ROSTER_STATUS_POSTHOC_CONTAMINATION',
            f'{chosen.name} carries {contaminated} for {sorted(teams)}. That '
            f'status is assigned AFTER a game is played, so this capture is '
            f'not pregame information for these teams and using it would put '
            f'the outcome into the pool. Refusing rather than filtering.',
            statuses=counts, posthoc=contaminated,
            posthoc_meaning={k: POSTHOC[k] for k in contaminated},
            players=who[:10], observed_at=chosen_at, source=chosen.name)
    if ACTIVE not in counts:
        return Outcome.fail(
            'ROSTER_STATUS_NO_ACTIVE_PLAYERS',
            f'{chosen.name} lists no {ACTIVE} player for {sorted(teams)}; the '
            f'status column is present but carries nothing usable',
            statuses=counts)
    return Outcome.ok('ROSTER_STATUS_OK', value=out,
                      spec_version=SPEC_VERSION,
                      source=chosen.name, observed_at=chosen_at,
                      status_counts=counts)


def active_pool(players, statuses) -> Outcome:
    """Keep the players on the active roster. Everyone else is NAMED."""
    keep, dropped = [], {}
    unknown = []
    unrecognised = {}
    for q in players:
        st = statuses.get(q.get('gsis_id'))
        if st is None:
            # AN UNKNOWN STATUS IS NOT AN IMPLIED ACTIVE STATUS. He is kept --
            # dropping a player the roster does not describe would be the
            # forcing-concentration move this repair exists to avoid -- and he
            # is counted so the artifact records how many.
            unknown.append(q.get('gsis_id'))
            keep.append(q)
            continue
        if st == ACTIVE:
            keep.append(q)
        elif st in EXCLUDED:
            dropped.setdefault(st, []).append(q.get('gsis_id'))
        else:
            # A CODE THIS MODULE DOES NOT RECOGNISE IS NOT AN EXCLUSION.
            # `dropped_meaning` used to fall back to "not on the active roster"
            # for anything unlisted, which turned every future or unexpected
            # code -- INA among them -- into a silent removal justified by a
            # sentence rather than by knowing what the code meant. Keeping him
            # and naming the code is the conservative direction: this repair
            # exists to remove contamination, not to force concentration.
            unrecognised.setdefault(st, []).append(q.get('gsis_id'))
            keep.append(q)
    if not keep:
        return Outcome.fail(
            'ACTIVE_POOL_EMPTY',
            'no player survived the active-roster filter; an empty pool is a '
            'refusal, not an allocation of nothing')
    return Outcome.ok(
        'ACTIVE_POOL_OK', value=keep, spec_version=SPEC_VERSION,
        n_in=len(players), n_kept=len(keep),
        n_unknown_status_kept=len(unknown),
        dropped_by_status={k: len(v) for k, v in sorted(dropped.items())},
        dropped_meaning={k: EXCLUDED[k] for k in sorted(dropped)},
        kept_unrecognised_status={k: len(v)
                                  for k, v in sorted(unrecognised.items())},
        only_declared_codes_are_dropped=sorted(EXCLUDED))
