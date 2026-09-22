"""Availability semantics. Absence from a negative list is not affirmative.

THE DEFECT THIS EXISTS TO CLOSE

The dossier read a non-empty `inactive_ids` set as proof that the official
inactive board was COMPLETE for the game, and then called every unlisted
player ACTIVE. Two separate errors are stacked there. The first is using a
container's shape as evidence: "somebody passed me a non-empty set" is not
"both clubs have published". The second is bigger and it survives fixing the
first.

EVEN A COMPLETE BOARD DOES NOT LICENSE ACTIVE, AND THIS REPOSITORY ALREADY
RULED SO

Owner ruling 2026-09-10 item 4, implemented in
`nfl/production/nonqb/inactives.py`, which deliberately returns no set named
`active` and says why in `sets()`:

    The inactives publication is an assertion about who is OUT. It is not an
    assertion that everybody else is dressing. A roster carries 52-53 names,
    about 48 dress, and roughly 7 are listed inactive -- so "not on the list"
    covers players who will dress AND practice-squad members who were never
    going to, and the page does not distinguish them.

The arithmetic is the whole argument. 53 rostered minus 7 inactive is 46, and
about 48 dress including elevations; the complement of the inactive list is
not the dressing list and does not have the same size as it. So completeness
is NECESSARY for any positive claim and it is not SUFFICIENT, and the
question "what makes ACTIVE lawful" has an answer this checkout cannot meet:
a source that asserts who IS dressing. GAME_ACTIVE therefore exists in the
vocabulary below, is never produced by `classify`, and names the evidence it
would need.

WHAT AN INJURY DESIGNATION IS AND IS NOT

A designation is not a status -- `inactives.py` keeps them apart and so does
this module. But OUT, DOUBTFUL and QUESTIONABLE are AFFIRMATIVE club
statements, unlike absence from a list, so they are usable where the inactive
board does not decide. OUT is a declaration that the player will not play.
DOUBTFUL and QUESTIONABLE are declarations of uncertainty, and they reduce
confidence without establishing anything.

Order of authority: the official inactive board decides whom it lists. For a
player it does not list, the club's own designation is the next best
evidence. Absence from the board is last, and it is not evidence of activity
at any completeness level.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional, Sequence, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import evidence as EV                      # noqa: E402

SPEC_VERSION = 'nfl-availability-semantics-0'

# --- completeness of the inactive evidence --------------------------------
#: Both clubs in the game have published and the capture is pregame.
COMPLETE = 'COMPLETE'
#: Something was supplied, but it is not established that both clubs have
#: published. A bare set of ids lands here: it carries no completeness claim.
PARTIAL = 'PARTIAL'
#: Nothing was supplied.
ABSENT = 'ABSENT'
#: Supplied but unusable -- retrieved at or after kickoff, or describing
#: clubs that are not in this game. An invalid capture is not a partial one.
INVALID = 'INVALID'
COMPLETENESS = (COMPLETE, PARTIAL, ABSENT, INVALID)

# --- availability states --------------------------------------------------
#: Named on the official pre-kickoff inactive list. He will not play.
OFFICIAL_INACTIVE = 'OFFICIAL_INACTIVE'
#: The club designated him OUT on the injury report. Affirmative, negative.
INJURY_OUT = 'INJURY_OUT'
#: Affirmative statements of UNCERTAINTY. They establish nothing either way
#: and they are not a reason to treat the player as available.
INJURY_DOUBTFUL = 'INJURY_DOUBTFUL'
INJURY_QUESTIONABLE = 'INJURY_QUESTIONABLE'
#: He is dressing. Requires a source that asserts who IS playing. NEVER
#: produced by `classify` -- see `WHY_GAME_ACTIVE_IS_UNREACHABLE`.
GAME_ACTIVE = 'GAME_ACTIVE'
#: An inactive board exists and he is not on it. THIS IS NOT A POSITIVE
#: CLAIM. It is the absence of a negative one.
NOT_ON_INACTIVE_LIST = 'NOT_ON_INACTIVE_LIST'
#: No usable availability evidence at all.
UNKNOWN = 'UNKNOWN'
STATES = (OFFICIAL_INACTIVE, INJURY_OUT, INJURY_DOUBTFUL,
          INJURY_QUESTIONABLE, GAME_ACTIVE, NOT_ON_INACTIVE_LIST, UNKNOWN)

#: States that assert the player will not take the field.
WILL_NOT_PLAY = (OFFICIAL_INACTIVE, INJURY_OUT)
#: States that assert nothing about whether he plays.
ASSERTS_NOTHING = (NOT_ON_INACTIVE_LIST, UNKNOWN, INJURY_DOUBTFUL,
                   INJURY_QUESTIONABLE)

WHY_GAME_ACTIVE_IS_UNREACHABLE = (
    'GAME_ACTIVE requires a source that asserts who IS dressing. The official '
    'inactives publication asserts only who is OUT, and its complement '
    'contains both players who will dress and practice-squad members who were '
    'never going to -- the page does not distinguish them. No source in this '
    'checkout makes the positive assertion, so no derivation here can produce '
    'GAME_ACTIVE. Adding one is a data-acquisition task, not a logic change.')

#: Injury report designations, uppercased, mapped to the state they support.
#: Anything not listed here supports nothing and is ignored.
_DESIGNATION = {
    'OUT': INJURY_OUT,
    'DOUBTFUL': INJURY_DOUBTFUL,
    'QUESTIONABLE': INJURY_QUESTIONABLE,
}


@dataclass(frozen=True)
class InactiveEvidence:
    """What is actually known about the official inactive declaration.

    COMPLETENESS IS CARRIED, NEVER INFERRED FROM SHAPE. `clubs` is the two
    clubs in the game; `clubs_declared` is the ones a list was resolved for.
    COMPLETE means those sets match and the capture is pregame. Nothing about
    the size of `inactive_ids` contributes.
    """
    game_id: Optional[str] = None
    clubs: Tuple[str, ...] = ()
    clubs_declared: Tuple[str, ...] = ()
    inactive_ids: FrozenSet[str] = frozenset()
    completeness_verdict: str = ABSENT
    source: Optional[str] = None
    retrieved_at: Optional[str] = None
    declaration_timestamp: Optional[str] = None
    kickoff_utc: Optional[str] = None
    content_hash: Optional[str] = None
    why: Optional[str] = None

    def declares_inactive(self, gsis_id: str) -> bool:
        return gsis_id in self.inactive_ids

    @property
    def usable(self) -> bool:
        """Whether this evidence may decide anything at all."""
        return self.completeness_verdict in (COMPLETE, PARTIAL)

    def as_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d['inactive_ids'] = sorted(self.inactive_ids)
        d['n_inactive'] = len(self.inactive_ids)
        d['spec_version'] = SPEC_VERSION
        return d

    # -- constructors ------------------------------------------------------
    @staticmethod
    def absent(game_id: str = None, why: str = None) -> 'InactiveEvidence':
        return InactiveEvidence(
            game_id=game_id, completeness_verdict=ABSENT,
            why=why or 'no official inactive declaration was supplied for '
                       'this game')

    @staticmethod
    def from_ids(inactive_ids, *, game_id: str = None,
                 clubs: Sequence[str] = (), source: str = None,
                 retrieved_at: str = None) -> 'InactiveEvidence':
        """A bare set of ids. ALWAYS PARTIAL, however many ids it holds.

        This is the constructor that closes the original defect. A caller who
        hands over ids has said who is out; it has not said that both clubs
        have published, and this function will not pretend otherwise. To
        claim COMPLETE, build the evidence from an `inactives.sets()` outcome
        or state `clubs_declared` explicitly.
        """
        ids = frozenset(inactive_ids or ())
        return InactiveEvidence(
            game_id=game_id, clubs=tuple(clubs), clubs_declared=(),
            inactive_ids=ids, completeness_verdict=PARTIAL,
            source=source or 'caller-supplied inactive ids',
            retrieved_at=retrieved_at,
            why='a set of ids carries no claim about whether both clubs have '
                'published. Completeness must be stated, never inferred from '
                'the size or emptiness of a container.')

    @staticmethod
    def from_inactives_outcome(outcome, *, game_id: str = None,
                               clubs: Sequence[str] = (),
                               content_hash: str = None) -> 'InactiveEvidence':
        """From `nonqb.inactives.sets()`, which already decides completeness.

        That function emits POST_INACTIVES_COMPLETE only when BOTH clubs are
        represented and the capture is pregame, and defers with
        POST_INACTIVES_INCOMPLETE otherwise. This reads its verdict rather
        than forming a second opinion.
        """
        ev = getattr(outcome, 'evidence', None) or {}
        code = getattr(outcome, 'code', '')
        by_team = ev.get('inactive_by_team') or {}
        ids = frozenset(p for lst in by_team.values() for p in (lst or ()))
        game = game_id or ev.get('game_id')
        declared = tuple(sorted(t for t, lst in by_team.items() if lst))
        clubs = tuple(clubs) or tuple(sorted(by_team))
        missing = ev.get('teams_without_a_list') or []
        if code == 'INACTIVES_POST_KICKOFF':
            verdict, why = INVALID, (
                f'the list was retrieved at or after kickoff '
                f'({ev.get("retrieved_at")} vs {ev.get("kickoff_utc")}), so '
                f'it is not pregame information about who would dress')
        elif code == 'POST_INACTIVES_COMPLETE':
            verdict, why = COMPLETE, (
                'both clubs in this game have a resolved inactive list and '
                'the capture is pregame. This establishes who is OUT; it '
                'still establishes nothing about who is dressing.')
        elif code == 'POST_INACTIVES_INCOMPLETE':
            verdict, why = PARTIAL, (
                f'{missing} has no resolved inactive list, so the game is '
                f'covered on one side only')
        else:
            verdict, why = INVALID, (
                f'the inactives layer returned {code!r}, which is not a '
                f'verdict this module can read')
        return InactiveEvidence(
            game_id=game, clubs=clubs, clubs_declared=declared,
            inactive_ids=ids, completeness_verdict=verdict,
            source='official_inactives', retrieved_at=ev.get('retrieved_at'),
            declaration_timestamp=ev.get('retrieved_at'),
            kickoff_utc=ev.get('kickoff_utc'), content_hash=content_hash,
            why=why)


def designation_state(injury_report_status) -> Optional[str]:
    """The state an injury designation supports, or None if it supports none."""
    s = (injury_report_status or '').strip().upper()
    return _DESIGNATION.get(s)


def classify(gsis_id: str, *, evidence: InactiveEvidence,
             injury_report_status=None,
             already_flagged_inactive: bool = False) -> EV.Axis:
    """The availability axis for one player. The only place this is decided.

    `already_flagged_inactive` is the universe layer's own stamp, honoured
    alongside the evidence set because either source saying INACTIVE is
    enough: the failure worth preventing is a player read as available when
    something said he is not.
    """
    ev = evidence or InactiveEvidence.absent()
    desig = designation_state(injury_report_status)

    def ax(value, grade, note, conflict=None):
        n = note
        if conflict:
            n = f'{note} {conflict}'
        return EV.Axis(name='availability', value=value, grade=grade,
                       source=ev.source, observed_at=ev.retrieved_at, note=n)

    if ev.completeness_verdict == INVALID:
        return ax(UNKNOWN, EV.UNAVAILABLE,
                  f'the inactive evidence is INVALID and may decide nothing: '
                  f'{ev.why}. An invalid capture is not a partial one, so it '
                  f'is not used at a lower confidence -- it is not used.')

    listed = already_flagged_inactive or (ev.usable
                                          and ev.declares_inactive(gsis_id))
    if listed:
        return ax(OFFICIAL_INACTIVE, EV.DECLARED,
                  'named on the official inactive list for this game.')

    if desig == INJURY_OUT:
        conflict = None
        if ev.completeness_verdict == COMPLETE:
            conflict = ('NOTE: the inactive board is COMPLETE for this game '
                        'and does not list him, which disagrees with an OUT '
                        'designation. Both facts are recorded; resolving '
                        'them is not this layer\'s job.')
        return ax(INJURY_OUT, EV.DECLARED,
                  'the club designated him OUT. That is an affirmative '
                  'statement that he will not play, unlike absence from a '
                  'list.', conflict)
    if desig in (INJURY_DOUBTFUL, INJURY_QUESTIONABLE):
        return ax(desig, EV.DECLARED,
                  f'the club designated him {desig.split("_")[1].title()}. '
                  f'That is an affirmative statement of UNCERTAINTY: it '
                  f'establishes nothing either way and is not a reason to '
                  f'treat him as available.')

    if ev.completeness_verdict == COMPLETE:
        return ax(NOT_ON_INACTIVE_LIST, EV.DECLARED,
                  'both clubs have published and he is not among those '
                  'declared out. THIS IS NOT A CLAIM THAT HE IS DRESSING. '
                  'The complement of the inactive list contains players who '
                  'will dress and practice-squad members who were never '
                  'going to, and the publication does not distinguish them. '
                  + WHY_GAME_ACTIVE_IS_UNREACHABLE)
    if ev.completeness_verdict == PARTIAL:
        return ax(NOT_ON_INACTIVE_LIST, EV.UNAVAILABLE,
                  f'he is not among the ids supplied, but it is not '
                  f'established that both clubs have published: {ev.why} '
                  f'Absence from an incomplete negative list is not evidence '
                  f'of anything.')
    return ax(UNKNOWN, EV.UNAVAILABLE,
              f'{ev.why}. Availability is unknown, and it may not be '
              f'inferred from roster status or from DraftKings salary '
              f'presence.')
