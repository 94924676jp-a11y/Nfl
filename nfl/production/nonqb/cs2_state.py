"""CS2 stage 2: current non-QB role STATE. Two quantities, never one.

WHAT STAGE 1 LEFT OPEN AND HOW IT IS CLOSED

`current_season_nonqb_panel.stage2_state` refused for want of three choices
`predeclaration_cs2.md` did not fix. Amendment B1 (`nfl/research/cs2/
AMENDMENT_B1.md`) resolves each one prospectively, and two of them turn out to
be non-choices:

  half_life          REMOVED for the 2026 week-2 forecast, exactly as OAS1
                     amendment A1 removed it: with ONE current-season week in
                     the conditioning set there is nothing for a decay to act
                     on. Re-declared before any fit with two or more weeks.
  min_opportunity    REMOVED as a selection axis and RETAINED as a reported
                     field. The predeclaration's own sentence about it is a
                     reporting rule, and a reporting rule cannot move a score.
  shrinkage_target   DECLARED, because this one is a real choice: the target
                     is the player's OWN prior-season share, with the room
                     mean only as the fallback for a man with no prior-season
                     history, and every fallback COUNTED. The predeclaration
                     already says depth rank "orders a room; it does not set a
                     share", which rules out the depth-rank target, and it
                     names prior-season role history as the shrunk prior.

THE SHAPE, AND WHY IT IS TWO ESTIMATES

    P(appears)                 will he take a carry or a target at all
    share | appears            what fraction of the room's work he gets

The P2 diagnostic is the argument. James Cook carried an unconditional 0.454
of Buffalo's carries against a conditional 0.692 -- the conditional figure was
defensible against week-1 evidence and the absence mass was not, and a single
"role" number averages the two so that neither is visible. They are estimated
apart here and reported apart.

    p_appears   = (kappa_a * a0 + appeared) / (kappa_a + n_weeks)
    share       = (kappa_s * s0 + opportunity) normalised over the room

Both are posterior means under a conjugate prior: a Beta on appearance and a
Dirichlet on the room split. `kappa_a` and `kappa_s` are prior strengths in
pseudo-observations -- the same idiom OAS1 uses for its prior-season
strengths -- and they are FITTED out of sample, not chosen, which is what
"a declared, tuned quantity, not a constant" requires.

WHAT IS DELIBERATELY NOT IMPOSED

No monotonicity in depth rank. `role_invariants` REPORTS an inversion; it does
not repair one, and nothing here forces RB1 above RB2. A short-yardage back
who plays rarely and dominates his room when he does is a HIGH conditional
share with a LOW appearance probability, and a monotonicity shortcut would
erase exactly that player. The objective is not to raise James Cook. It is to
let current-season evidence reach the layer at all.

CONSERVATION. Room shares sum to 1 to 1e-9, by construction and by assertion.
Appearance probabilities do NOT sum to anything: they are marginal
probabilities of separate events, and asserting a simplex there is the error
that creates an inversion.
"""
from __future__ import annotations

import collections
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402

SPEC_VERSION = 'nonqb-current-season-role-state-1'
AMENDMENT = 'B1'

#: The two rooms. A room is one club and one kind of opportunity, because a
#: carry and a target are not interchangeable and a share across both would
#: mean nothing.
CARRIES = 'carries'
TARGETS = 'targets'
ROOMS = (CARRIES, TARGETS)

#: Prior strengths, in pseudo-observations. DECLARED GRID, fitted out of
#: sample. 0 is "ignore the prior entirely" and is kept in the grid so that a
#: fit which prefers it is visible rather than impossible.
KAPPA_A_GRID = (0.0, 1.0, 2.0, 4.0, 8.0, 16.0)
KAPPA_S_GRID = (0.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0)

FALLBACK_ROOM_MEAN = 'NO_PRIOR_SEASON_HISTORY_ROOM_MEAN'


def _room_totals(rows, room):
    out = collections.Counter()
    for (club, pid), d in rows.items():
        out[club] += d[room]
    return out


def prior_from_season(season_rows, room) -> dict:
    """(club, player) -> (prior share, prior appearance rate), prior season.

    `season_rows` is {(week, club, pid): counts} for ONE season.
    """
    opp = collections.defaultdict(float)
    weeks_with_opp = collections.defaultdict(set)
    club_weeks = collections.defaultdict(set)
    for (wk, club, pid), d in season_rows.items():
        club_weeks[club].add(wk)
        if d[room] > 0:
            opp[(club, pid)] += d[room]
            weeks_with_opp[(club, pid)].add(wk)
    club_tot = collections.defaultdict(float)
    for (club, pid), v in opp.items():
        club_tot[club] += v
    out = {}
    for (club, pid), v in opp.items():
        n = len(club_weeks[club]) or 1
        out[(club, pid)] = (v / club_tot[club] if club_tot[club] else 0.0,
                            len(weeks_with_opp[(club, pid)]) / n)
    return out


def state(current_rows, prior, room, *, kappa_a, kappa_s,
          n_weeks, roster=None) -> Outcome:
    """The role state for every club, from weeks already played.

    `current_rows`  {(week, club, pid): counts} for the season SO FAR.
    `prior`         {(club, pid): (share, appearance_rate)} from the season
                    before. A player absent from it falls back to the room
                    mean and the fallback is counted.
    `roster`        optional {(club, pid)} of men eligible this week. Without
                    it the room is whoever has appeared, which under-covers a
                    player who has not touched the ball yet.
    """
    if room not in ROOMS:
        return Outcome.fail('CS2_UNKNOWN_ROOM', f'{room!r} is not a room',
                            cause=Cause.DATA, rooms=list(ROOMS))
    opp = collections.defaultdict(float)
    weeks_with_opp = collections.defaultdict(set)
    clubs = collections.defaultdict(set)
    for (wk, club, pid), d in current_rows.items():
        clubs[club].add(pid)
        if d[room] > 0:
            opp[(club, pid)] += d[room]
            weeks_with_opp[(club, pid)].add(wk)
    if roster:
        for club, pid in roster:
            clubs[club].add(pid)

    rows, fallbacks = {}, 0
    for club, members in clubs.items():
        # Room mean is the fallback target. It is 1/|room|, the only
        # uninformative split, and it is used ONLY for a man with no
        # prior-season history.
        k = len(members) or 1
        num = {}
        for pid in members:
            pr = prior.get((club, pid))
            if pr is None:
                s0, a0 = 1.0 / k, 0.0
                fallbacks += 1
                why = FALLBACK_ROOM_MEAN
            else:
                s0, a0 = pr
                why = None
            seen = opp.get((club, pid), 0.0)
            appeared = len(weeks_with_opp.get((club, pid), ()))
            p_app = ((kappa_a * a0 + appeared) / (kappa_a + n_weeks)
                     if (kappa_a + n_weeks) > 0 else 0.0)
            num[pid] = (kappa_s * s0 + seen, p_app, seen, appeared, why)
        tot = sum(v[0] for v in num.values())
        for pid, (nu, p_app, seen, appeared, why) in num.items():
            rows[(club, pid)] = {
                'team': club, 'player_id': pid, 'room': room,
                'share_given_appears': (nu / tot) if tot else 1.0 / k,
                'p_appears': min(max(p_app, 0.0), 1.0),
                'n_opportunity': seen, 'n_weeks_with_opportunity': appeared,
                'n_weeks_conditioned_on': n_weeks,
                'prior_fallback': why,
                'room_size': k}
    # SATURATION, REPORTED AND NOT REPAIRED. A Beta posterior mean is exactly
    # 1.0 for a man whose prior-season appearance rate is 1 and who has
    # appeared in every week so far -- James Cook is such a man. A probability
    # of exactly one says he CANNOT miss, which is not a plausible football
    # state and must not reach a simulator. Putting a floor on it is a new
    # modelling choice and belongs in a preregistration, not here, so the
    # count is surfaced and nothing is clipped.
    saturated_one = sorted(k for k, r in rows.items() if r['p_appears'] >= 1.0)
    saturated_zero = sorted(k for k, r in rows.items() if r['p_appears'] <= 0.0)

    # CONSERVATION, asserted rather than assumed.
    bad = []
    for club in clubs:
        s = sum(r['share_given_appears'] for r in rows.values()
                if r['team'] == club)
        if abs(s - 1.0) > 1e-9:
            bad.append({'team': club, 'sum': s})
    if bad:
        return Outcome.fail(
            'CS2_SHARES_DO_NOT_CONSERVE',
            f'{len(bad)} club room(s) do not sum to 1.0 to 1e-9',
            cause=Cause.DATA, offending=bad)
    return Outcome.ok(
        'CS2_ROLE_STATE', value=rows,
        detail=f'{len(rows)} player-room row(s) across {len(clubs)} club(s), '
               f'room {room}, kappa_a={kappa_a} kappa_s={kappa_s}, '
               f'{fallbacks} prior fallback(s)',
        spec_version=SPEC_VERSION, amendment=AMENDMENT, room=room,
        kappa_a=kappa_a, kappa_s=kappa_s, n_weeks=n_weeks,
        n_rows=len(rows), n_clubs=len(clubs),
        n_prior_fallbacks=fallbacks,
        fallbacks_are_counted_not_silent=True,
        n_p_appears_at_one=len(saturated_one),
        n_p_appears_at_zero=len(saturated_zero),
        p_appears_saturates=(
            'CS2_APPEARANCE_SATURATES_AT_ONE: a Beta posterior mean is '
            'exactly 1.0 for a man who has never missed, and exactly 0.0 for '
            'one who has never played. Neither is a plausible football state '
            'and neither may reach a simulator unfloored. The floor is a new '
            'modelling choice and belongs in a preregistration; nothing is '
            'clipped here, and the counts are reported so the gap is visible '
            'rather than absorbed.'),
        appearance_is_not_a_simplex=(
            'p_appears are marginal probabilities of separate events and do '
            'NOT sum to one. Asserting a simplex here is the error that '
            'creates an appearance inversion.'),
        no_monotonicity_imposed=(
            'nothing forces RB1 above RB2. A short-yardage back is a high '
            'conditional share with a low appearance probability, and a '
            'monotonicity shortcut would erase him.'))
