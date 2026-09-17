"""One team-code normalization table, declared once, asserted total.

WHY A SEPARATE MODULE AND NOT A DICT AT A CALL SITE. A multi-season join keyed
on club is wrong in a way that does not raise: if one franchise appears under
two codes, its prior-season strength splits across two rows, the carryover
prior for that club silently becomes half-weight or empty, and its Week-2
estimate is pure current-season noise while every other club's is properly
shrunk. Nothing in the arithmetic complains. `assert_total` is what turns that
into a refusal.

WHAT WAS MEASURED, AND IT CORRECTS THE RESEARCH GUIDANCE ON ONE POINT
--------------------------------------------------------------------
Read from the captured blobs on 2026-09-17, not recalled.

`pbp` (2024, 2025, 2026 -- 49,492 + 48,771 + 2,756 rows over
`posteam`/`defteam`/`home_team`/`away_team`):

    EXACTLY 32 codes, IDENTICAL in all three seasons. No LAR. No OAK. No SD.
    No STL.

`schedules` (7,548 rows, 1999 onward):

    35 codes. The three extra are OAK, SD and STL. STILL NO LAR.
      2016: LA and SD, no LAC, no LV
      2017: LA and LAC, no SD
      2019: OAK
      2020: LV, no OAK
      2024, 2025, 2026: the same 32 as pbp

So the specific hazard the guidance names -- "inconsistent LA versus LAR usage
across nflverse datasets" producing a 33rd club -- **is not present in either
source this project has captured.** `LAR` is kept in the table below anyway,
mapping to `LA`, because the guidance reports it in other nflverse datasets and
a defensive entry costs nothing; it is labelled as NOT OBSERVED HERE so that
nobody later reads its presence as evidence it occurred.

The hazards that ARE present are the three relocations, and they only bite if
OAS1's scope reaches back to 2019 or earlier. At the declared V1 scope --
2025 prior season plus 2026 current -- **normalization is the identity map**,
and saying that plainly is more useful than implying work was done.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'oas1-team-normalization-1'

#: The 32 current franchises, in the code each one is normalized TO.
CANONICAL = (
    'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN',
    'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC', 'LA', 'LAC', 'LV', 'MIA', 'MIN',
    'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS',
)

#: Every non-canonical code that maps into a canonical one, with the reason.
#: `observed` records whether this project has actually seen the code in a
#: captured file, so a defensive entry is never mistaken for a measurement.
ALIASES = {
    'OAK': {'to': 'LV', 'why': 'Oakland Raiders relocated to Las Vegas, 2020',
            'observed': 'schedules, seasons through 2019'},
    'SD': {'to': 'LAC', 'why': 'San Diego Chargers relocated to Los Angeles, '
                               '2017',
           'observed': 'schedules, seasons through 2016'},
    'STL': {'to': 'LA', 'why': 'St. Louis Rams relocated to Los Angeles, 2016',
            'observed': 'schedules, seasons through 2015'},
    'LAR': {'to': 'LA',
            'why': 'an alternative spelling of the Los Angeles Rams used by '
                   'some nflverse datasets',
            'observed': 'NOT OBSERVED in any file this project has captured. '
                        'Declared defensively on external report only, and '
                        'labelled so that its presence here is not read as '
                        'evidence it occurred.'},
}

#: Codes that are lawfully NOT a club and must not be silently mapped to one.
#: `pbp` leaves `posteam` and `defteam` empty on timeouts and end-of-quarter
#: rows, and an empty string coerced to a club is a fabricated observation.
NON_CLUB = ('', 'NA', 'nan', 'None', 'UNK')

CODE_OK = 'OAS1_TEAM_NORMALIZED'
CODE_TOTAL = 'OAS1_TEAM_NORMALIZATION_TOTAL'
CODE_UNRESOLVED = 'OAS1_TEAM_UNRESOLVED'
CODE_NOT_A_CLUB = 'OAS1_TEAM_NOT_A_CLUB'
CODE_WRONG_COUNT = 'OAS1_TEAM_COUNT_NOT_32'

_MAP = {**{c: c for c in CANONICAL},
        **{k: v['to'] for k, v in ALIASES.items()}}
assert set(ALIASES) & set(CANONICAL) == set(), \
    'an alias may not also be canonical; the table would be ambiguous'
assert all(v['to'] in CANONICAL for v in ALIASES.values()), \
    'every alias must map INTO the canonical set'


def normalize(code: str) -> Outcome:
    """One code. Returns an Outcome; never a silently passed-through string.

    An unknown code is REFUSED rather than returned unchanged. Passing it
    through is what creates a 33rd club, and the club count check downstream
    would then be the only thing standing between that and a fitted model.
    """
    raw = code
    c = (code or '').strip().upper()
    if c in NON_CLUB or (code or '').strip() in NON_CLUB:
        return Outcome.fail(
            CODE_NOT_A_CLUB,
            f'{raw!r} is not a club code. `pbp` leaves the possession team '
            f'empty on timeouts and end-of-period rows, and coercing that to '
            f'a club would invent an observation.',
            cause=Cause.DATA, input_code=raw)
    if c not in _MAP:
        return Outcome.fail(
            CODE_UNRESOLVED,
            f'{raw!r} is not in the normalization table. An unknown code is '
            f'refused rather than passed through: a code that survives '
            f'unmapped into a design matrix is a 33rd club, and it splits one '
            f'franchise`s prior-season strength without raising anything.',
            cause=Cause.DATA, input_code=raw, n_known=len(_MAP))
    return Outcome.ok(CODE_OK, value=_MAP[c],
                      detail=f'{raw!r} -> {_MAP[c]}',
                      input_code=raw, normalized=_MAP[c],
                      was_alias=c in ALIASES,
                      alias_reason=(ALIASES[c]['why'] if c in ALIASES
                                    else None))


def assert_total(codes, *, label: str = 'frame') -> Outcome:
    """Every observed code maps exactly once, or this refuses.

    TOTALITY IS THE PROPERTY, not coverage. A table that maps 31 of 32 clubs
    is not 97% correct; it produces one club with no prior and 31 with one,
    which is a worse state than having no table at all because it looks fine.
    """
    seen = sorted({(c or '').strip().upper() for c in codes
                   if (c or '').strip() not in NON_CLUB})
    unresolved = [c for c in seen if c not in _MAP]
    mapped = sorted({_MAP[c] for c in seen if c in _MAP})
    ev = {'spec_version': SPEC_VERSION, 'label': label,
          'n_observed': len(seen), 'observed': seen,
          'n_canonical_after': len(mapped), 'canonical_after': mapped,
          'unresolved': unresolved,
          'aliases_used': sorted(c for c in seen if c in ALIASES),
          'is_identity_map': all(c in CANONICAL for c in seen)}
    if unresolved:
        return Outcome.fail(
            CODE_UNRESOLVED,
            f'{label}: {unresolved} do not map. Normalization is not total '
            f'over this frame, so no multi-season join on club may proceed.',
            cause=Cause.DATA, **ev)
    return Outcome.ok(
        CODE_TOTAL, value=dict(ev),
        detail=f'{label}: {len(seen)} observed code(s) map onto '
               f'{len(mapped)} franchise(s)'
               + ('; the map is the identity over this frame'
                  if ev['is_identity_map'] else
                  f'; aliases used: {ev["aliases_used"]}'),
        **ev)


def assert_thirty_two(codes, *, label: str = 'season') -> Outcome:
    """After normalization a full season must hold exactly 32 clubs.

    This is the check that catches an alias nobody declared: if `LAR` and `LA`
    both survive, the count is 33 and this refuses. It is deliberately separate
    from `assert_total`, because a code can be perfectly mappable and still
    leave the wrong number of clubs standing.
    """
    t = assert_total(codes, label=label)
    if t.state.value != 'PASS':
        return t
    n = t.evidence['n_canonical_after']
    if n != 32:
        return Outcome.fail(
            CODE_WRONG_COUNT,
            f'{label}: {n} club(s) after normalization, not 32. '
            + ('More than 32 means an undeclared alias survived as its own '
               'franchise.' if n > 32 else
               'Fewer than 32 means the frame does not cover the league, '
               'which is a different claim from being normalized.'),
            cause=Cause.DATA, **t.evidence)
    return Outcome.ok(
        CODE_TOTAL, value=t.value,
        detail=f'{label}: exactly 32 clubs after normalization', **t.evidence)
