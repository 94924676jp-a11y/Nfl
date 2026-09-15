"""Who can lawfully compete for opportunity this week, and how certain we are.

WHY THIS EXISTS. R5 restricted the allocation pool to roster status ACT and
measured what that was worth: an unfiltered pool of 22-23 made the P4C simplex
divide by a sum of 2.25/2.04, halving every real starter's share. That filter
reads `weekly_rosters.status`, and for 2026 week 2 there is NO capture carrying
it -- the only raw blob is week 1, because the vintage reduction drops the
column. `status_map` therefore returns ROSTER_STATUS_EMPTY, and
`run_forecast` treats that as fatal to the entire non-QB chain: no running
back, no receiver and no tight end for either club.

THE OBVIOUS REPAIR IS THE WRONG ONE, AND IT WAS MEASURED BEFORE BEING REJECTED.
"Use week-2 membership and let the injury report and the inactives list do the
excluding" recreates R5's defect exactly. Injury designations and inactives are
statements ABOUT THE GAME ROSTER; they say nothing about someone who was never
on it. Measured on the 2026 week-2 membership file, skill positions:

    league   810 rows: 487 ACT, 173 DEV, 71 RES, 64 INA, 9 RET, 3 CUT, 2 EXE
    DET       23 rows:  15 ACT,   5 DEV,  2 RES,          1 RET
    BUF       23 rows:  15 ACT,   4 DEV,  1 RES,  2 INA,         1 CUT

DET's week-2 skill membership contains a RETIRED player. Membership is not
game-participation eligibility, and no injury report was ever going to say so.

WHAT PARTICIPATION ACTUALLY LOOKS LIKE BY STATUS, measured over 30 teams,
2026 week 1, skill positions, joined pfr_id -> pfr_player_id:

    ACT   361/417  0.8657        DEV     0/120   RES  0/63
    INA     0/62   (tautology)   CUT     0/53    RET  0/6

Zero of 305 non-ACT skill players took a single offensive snap. And ACT is
0.8657, NOT 1.0 -- 56 of 417 active players took no offensive snap at all, so
"on the active roster" is not "has an offensive role" either.

The rates live in PARTICIPATION_RATE_BY_STATUS.json with their n, their source
blob hashes and their join. Nothing here is a chosen number.

THREE THINGS THIS REFUSES TO DO.

  * It does not read INA's 0/62 as a week-2 prior. That zero is TRUE BY
    CONSTRUCTION -- a week-1 inactive did not take a week-1 snap -- and says
    nothing about week 2. A week-1 INA player is a 53-man roster member, so his
    week-2 class is ACTIVE_ROSTER_EXPECTED at the ACT rate. The
    injury-persistence adjustment that would sharpen this is not identified
    from one week of data, so it is left unmeasured rather than invented.

  * It does not use a measured 0/120 as a hard zero. Every rate is carried as
    its Jeffreys mean, so a class nobody was observed in keeps a small positive
    probability rather than an impossibility the sample cannot support.

  * It does not resolve UNKNOWN. A player known only to be on the membership
    file is neither active nor excluded; he carries the MARGINAL participation
    rate over all members, 0.5000 [361/722]. Uncertainty is represented, not
    decided.

ELEVATION IS UNREACHABLE AND SAYS SO. `official_transactions` is registered
with no verified endpoint -- 459 manifest rows, every one
BLOCKED/ENDPOINT_NOT_YET_VERIFIED -- so gameday elevations, practice-squad
signings and IR activations cannot be read at all. ELEVATION_CONFIRMED is
therefore a class this module can never currently assign, and it reports that
as UNAVAILABLE rather than quietly never using it.
"""
from __future__ import annotations

import csv
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'participant-class-1'
RATES_PATH = pathlib.Path(__file__).with_name(
    'PARTICIPATION_RATE_BY_STATUS.json')

#: The participation classes, most determined first. `participates` is the
#: probability the player takes at least one OFFENSIVE SNAP -- it is not a
#: role, and it is not a target share.
ACTIVE_ROSTER_CONFIRMED = 'ACTIVE_ROSTER_CONFIRMED'
ACTIVE_ROSTER_EXPECTED = 'ACTIVE_ROSTER_EXPECTED'
ELEVATION_CONFIRMED = 'ELEVATION_CONFIRMED'
PRACTICE_SQUAD = 'PRACTICE_SQUAD'
RESERVE = 'RESERVE'
RELEASED = 'RELEASED'
RETIRED = 'RETIRED'
UNKNOWN = 'UNKNOWN'

CLASSES = (ACTIVE_ROSTER_CONFIRMED, ACTIVE_ROSTER_EXPECTED,
           ELEVATION_CONFIRMED, PRACTICE_SQUAD, RESERVE, RELEASED,
           RETIRED, UNKNOWN)

#: Which measured status each class draws its rate from. ACTIVE_ROSTER_EXPECTED
#: and ELEVATION_CONFIRMED both draw ACT: an elevated practice-squad player and
#: a 53-man player are both game-roster participants on the day.
_RATE_KEY = {
    ACTIVE_ROSTER_CONFIRMED: 'ACT',
    ACTIVE_ROSTER_EXPECTED: 'ACT',
    ELEVATION_CONFIRMED: 'ACT',
    PRACTICE_SQUAD: 'DEV',
    RESERVE: 'RES',
    RELEASED: 'CUT',
    RETIRED: 'RET',
}

#: nflverse status -> the class it implies FOR A LATER WEEK.
#: INA maps to ACTIVE_ROSTER_EXPECTED deliberately: it means the player was on
#: the 53 and did not dress, which is a statement about ONE game.
_CARRY = {
    'ACT': ACTIVE_ROSTER_EXPECTED,
    'INA': ACTIVE_ROSTER_EXPECTED,
    'DEV': PRACTICE_SQUAD,
    'RES': RESERVE,
    'EXE': RESERVE,
    'PUP': RESERVE,
    'NON': RESERVE,
    'CUT': RELEASED,
    'RET': RETIRED,
}

RAW = _REPO / 'nfl' / 'vintage'


def rates() -> Outcome:
    """The measured participation rates, or a refusal naming what is absent."""
    if not RATES_PATH.exists():
        return Outcome.blocked(
            'PARTICIPATION_RATES_ABSENT',
            f'{RATES_PATH.name} does not exist, so every class would need an '
            f'invented participation probability. Refused.',
            cause=Cause.DATA)
    doc = json.loads(RATES_PATH.read_text())
    if not doc.get('rates'):
        return Outcome.blocked(
            'PARTICIPATION_RATES_EMPTY',
            'the rate artifact carries no rates.', cause=Cause.DATA)
    return Outcome.ok('PARTICIPATION_RATES_READ', value=doc)


def participation_prior(cls: str, doc: dict):
    """Jeffreys mean for the class, or the marginal for UNKNOWN.

    JEFFREYS, NOT THE RAW RATE. DEV measured 0/120. Carrying that as 0.0 would
    assert a practice-squad snap is IMPOSSIBLE, which 120 observations cannot
    establish; the Jeffreys mean says 0.0041 instead -- small, and not a claim
    of impossibility.
    """
    if cls == UNKNOWN:
        return (doc.get('frame') or {}).get('marginal_rate_any_member')
    key = _RATE_KEY.get(cls)
    row = (doc.get('rates') or {}).get(key or '')
    return row.get('jeffreys_mean') if row else None


def _raw_status_map(season: int, week: int):
    """gsis_id -> status, from any RAW roster capture carrying that week."""
    out, src = {}, []
    for f in sorted(RAW.glob('weekly_rosters.*raw.csv*')):
        op = gzip.open(f, 'rt') if f.name.endswith('.gz') else open(f, 'rt')
        try:
            rows = list(csv.DictReader(op))
        except Exception:                                        # noqa: BLE001
            continue
        if not rows or 'status' not in rows[0]:
            continue
        hit = [r for r in rows
               if str(r.get('season')) == str(season)
               and str(r.get('week')) == str(week)]
        if not hit:
            continue
        src.append(f.name)
        for r in hit:
            g = (r.get('gsis_id') or '').strip()
            if g:
                out[g] = (r.get('status') or '').strip().upper()
    return out, src


def classify(season: int, week: int, members, *, observed_before=None):
    """Assign every MEMBER a participation class and a participation prior.

    `members` are rows carrying at least gsis_id, team and position -- the
    week's membership file. Membership decides who is CONSIDERED; it never
    decides who PARTICIPATES.
    """
    ro = rates()
    if not ro.ok:
        return ro
    doc = ro.value

    same, same_src = _raw_status_map(season, week)
    prior_wk, prior_src = ({}, [])
    if week > 1:
        prior_wk, prior_src = _raw_status_map(season, week - 1)

    if not same and not prior_wk:
        return Outcome.blocked(
            'NO_ROSTER_STATUS_FOR_THIS_WEEK_OR_THE_LAST',
            f'no raw weekly-roster capture carries status for {season} week '
            f'{week} or {week - 1}, so every member would be UNKNOWN and the '
            f'pool would be membership by another name. That is the dilution '
            f'this module exists to prevent, so it refuses instead.',
            cause=Cause.DATA, season=season, week=week)

    rows, counts = [], {}
    for m in members:
        g = (m.get('gsis_id') or '').strip()
        cls, basis, grade = UNKNOWN, None, 'NO_STATUS_EVIDENCE'
        if g and g in same:
            st = same[g]
            if st == 'INA':
                # A gameday outcome for THIS week is not pregame evidence.
                cls, basis, grade = (ACTIVE_ROSTER_EXPECTED, f'{st}@w{week}',
                                     'SAME_WEEK_GAMEDAY_OUTCOME_NOT_USED')
            else:
                cls = (ACTIVE_ROSTER_CONFIRMED if st == 'ACT'
                       else _CARRY.get(st, UNKNOWN))
                basis, grade = f'{st}@w{week}', 'SAME_WEEK_STATUS'
        elif g and g in prior_wk:
            st = prior_wk[g]
            cls = _CARRY.get(st, UNKNOWN)
            basis, grade = f'{st}@w{week - 1}', 'CARRIED_FORWARD_ONE_WEEK'
        p = participation_prior(cls, doc)
        if p is None:
            return Outcome.blocked(
                'PARTICIPATION_PRIOR_MISSING',
                f'class {cls} has no measured rate in {RATES_PATH.name}.',
                cause=Cause.DATA, participant_class=cls)
        rows.append({'gsis_id': g, 'team': m.get('team'),
                     'position': m.get('position'),
                     'participant_class': cls, 'participation_prior': p,
                     'status_basis': basis, 'evidence_grade': grade})
        counts[cls] = counts.get(cls, 0) + 1

    return Outcome.ok(
        'PARTICIPANT_CLASSES_ASSIGNED', value=rows,
        detail=f'{len(rows)} member(s): '
               + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())),
        spec_version=SPEC_VERSION, counts=counts,
        same_week_status_sources=same_src,
        prior_week_status_sources=prior_src,
        n_same_week=len(same), n_prior_week=len(prior_wk),
        # NAMED, NOT SILENTLY UNUSED. There is no transactions endpoint, so
        # nothing here can ever observe an elevation.
        elevation_authority='UNAVAILABLE_NO_TRANSACTIONS_ENDPOINT',
        rate_artifact=RATES_PATH.name)
