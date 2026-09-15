"""Stage-0 eligibility gate: who may enter the allocation choice set at all.

THE RULE

An authoritatively inactive, out, or legally ineligible player holds **zero**
modelled opportunity, and that is enforced by never putting him in the choice
set -- not by allocating to him and zeroing him afterwards.

WHY THE ORDER MATTERS, AND IT IS NOT A STYLE PREFERENCE

`layers._run_real` (layers.py:224-241) draws the appearance Bernoullis first and
applies `inactives.apply_to_appearance` after, so an ineligible player is
allocated and then zeroed. D7 measured what that costs: in the four week-1 games
carrying both a PRE and a POST seal, `n_pre_only_rows = 0` and
`n_post_only_rows = 0` -- the pool is identical, only the numbers move. The
mass he held has to go somewhere, and it goes back through a renormalisation.
Every renormalisation is a denominator, and a wrong denominator is the defect
class this project has already paid for twice (R5's C-sum of 2.25 against 1.24;
C1's denominator work). Removing him upstream means the denominator is right the
first time and no compensating step exists to get wrong.

THE THREE STATES, WHICH ARE NOT TWO

    DETERMINED_INELIGIBLE   an authority states outright that he cannot play
    UNRESOLVED              nothing lawful says either way
    ELIGIBLE_SO_FAR         no lawful evidence of ineligibility, which is NOT
                            a positive claim that he will dress

Collapsing UNRESOLVED into either neighbour is the error. Folding it into
DETERMINED_INELIGIBLE fabricates an authority nobody issued; folding it into
ELIGIBLE_SO_FAR reads absence of evidence as evidence. `ELIGIBLE_SO_FAR` is
named the way it is so no caller can quote it as "available".

ABSENCE OF EVIDENCE IS NOT EVIDENCE OF ELIGIBILITY, IN EITHER DIRECTION

A player who appears on no injury report is `NO_DESIGNATION`, and that is a
statement about the report, not about the player. The same holds for a game with
no official inactive list: the gate records `GAMEDAY_ACTIVITY_UNRESOLVED` for
every player in it and refuses to call the board final. It does not infer that
nobody is out.

WHAT COUNTS AS A DETERMINATION, AND BY WHOSE AUTHORITY

    rank 1  official gameday inactive list       OFFICIAL_INACTIVE
    rank 2  official injury report, status Out   INJURY_OUT
    rank 2  league suspension / exempt ruling    SUSPENDED
    rank 3  weekly roster status RES / CUT / EXE ROSTER_RES / _CUT / _EXE

Ranks are the ordering already declared in this tree: `layers.py:226` records
the inactive list as "registry authority_rank 1", and `roster_status.py`
documents the roster codes. A higher-ranked statement wins; two statements at
the same rank that disagree are a REFUSAL, never a silent precedence.

`DEV` IS DELIBERATELY NOT A DETERMINATION

A practice-squad player can be elevated on gameday, so `DEV` is not legal
ineligibility. R5 removes him from the pool anyway, for a denominator reason
that has nothing to do with eligibility (`roster_status.py` header). This module
keeps that removal and labels it `EXCLUDED_BY_POOL_RULE` with
`determination='uncertain'`, so nobody can later read the R5 filter as a
statement that the league said he could not play. Naming it is the point: a
declared exclusion is not a silent zero.

UNCERTAINTY IS CARRIED AS DISCRETE WORLDS, NOT AS A MULTIPLIER

`scenarios()` returns eligibility worlds -- each a label, an excluded id set and
a weight -- because the engine already simulates discrete worlds
(`layers.py:222` draws a per-player Bernoulli). Multiplying every downstream
projection by an availability probability is the other thing, and it is wrong in
a different way: it produces a number no single world ever realises.

The gate will not invent a weight. Where the worlds cannot be weighted from
evidence it returns ONE world, says `weights_estimated=False`, and lists the
unresolved players by name. A fabricated 0.5 is worse than an admitted unknown.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (Cause, Outcome,     # noqa: E402
                                               State)
from nfl.production.nonqb import roster_status as RS               # noqa: E402
from nfl.production.nonqb import vintage_selector as VS            # noqa: E402

SPEC_VERSION = 'stage0-eligibility-gate-1'

# ------------------------------------------------------------------ vocabulary
DETERMINED = 'determined'
UNCERTAIN = 'uncertain'

# simulation_eligibility -- what the choice-set builder does with the row.
EXCLUDED_DETERMINISTIC = 'EXCLUDED_DETERMINISTIC'
EXCLUDED_BY_POOL_RULE = 'EXCLUDED_BY_POOL_RULE'
IN_CHOICE_SET = 'IN_CHOICE_SET'

AUTHORITY_RANK = {
    'OFFICIAL_INACTIVE_LIST': 1,
    'OFFICIAL_INJURY_REPORT': 2,
    'LEAGUE_SUSPENSION': 2,
    'WEEKLY_ROSTER_STATUS': 3,
}

# status -> (authority, determination, simulation_eligibility, reason)
STATUS = {
    'OFFICIAL_INACTIVE': (
        'OFFICIAL_INACTIVE_LIST', DETERMINED, EXCLUDED_DETERMINISTIC,
        'named on the official gameday inactive list for this game; he cannot '
        'take a snap'),
    'INJURY_OUT': (
        'OFFICIAL_INJURY_REPORT', DETERMINED, EXCLUDED_DETERMINISTIC,
        'the official injury report designates him Out, which is the league '
        'vocabulary for will not play'),
    'SUSPENDED': (
        'LEAGUE_SUSPENSION', DETERMINED, EXCLUDED_DETERMINISTIC,
        'under a league suspension or exempt ruling covering this game'),
    'ROSTER_RES': (
        'WEEKLY_ROSTER_STATUS', DETERMINED, EXCLUDED_DETERMINISTIC,
        'reserve or injured reserve; not on the active roster this week'),
    'ROSTER_CUT': (
        'WEEKLY_ROSTER_STATUS', DETERMINED, EXCLUDED_DETERMINISTIC,
        'released; not on the roster'),
    'ROSTER_EXE': (
        'WEEKLY_ROSTER_STATUS', DETERMINED, EXCLUDED_DETERMINISTIC,
        'exempt list; not available to this club for this game'),
    'ROSTER_DEV': (
        'WEEKLY_ROSTER_STATUS', UNCERTAIN, EXCLUDED_BY_POOL_RULE,
        'practice squad. NOT a determination of ineligibility -- he may be '
        'elevated on gameday. He is removed from the pool by the R5 '
        'denominator rule, which is a different rule with a different reason, '
        'and that removal is declared here rather than left silent'),
    'INJURY_DOUBTFUL': (
        'OFFICIAL_INJURY_REPORT', UNCERTAIN, IN_CHOICE_SET,
        'designated Doubtful. A designation is not a status; he stays in the '
        'choice set and his uncertainty belongs in a scenario'),
    'INJURY_QUESTIONABLE': (
        'OFFICIAL_INJURY_REPORT', UNCERTAIN, IN_CHOICE_SET,
        'designated Questionable. A designation is not a status; he stays in '
        'the choice set and his uncertainty belongs in a scenario'),
    'ROSTER_ACT': (
        'WEEKLY_ROSTER_STATUS', UNCERTAIN, IN_CHOICE_SET,
        'on the active roster and carrying no adverse designation. This is '
        'the ABSENCE of evidence against him, not evidence that he will '
        'dress: 53 are rostered and 48 may dress'),
    'NO_EVIDENCE': (
        None, UNCERTAIN, IN_CHOICE_SET,
        'no lawful source in the information set says anything about him. '
        'Absence from a report is a fact about the report'),
}

# The league's own designation vocabulary, matched to
# `nfl/capture/delivered_injuries.REPORT_STATUS_VOCAB` rather than re-invented.
_DESIGNATION = {'Out': 'INJURY_OUT',
                'Doubtful': 'INJURY_DOUBTFUL',
                'Questionable': 'INJURY_QUESTIONABLE'}

_ROSTER_STATUS = {'ACT': 'ROSTER_ACT', 'RES': 'ROSTER_RES',
                  'CUT': 'ROSTER_CUT', 'EXE': 'ROSTER_EXE',
                  'DEV': 'ROSTER_DEV'}

# INA is a GAMEDAY OUTCOME and is refused upstream by `roster_status`. It is
# named here so that a future caller reading this table cannot conclude the
# gate simply forgot about it.
_POSTHOC_ROSTER_STATUS = {'INA'}


def _iso(d):
    if d is None:
        return None
    if isinstance(d, str):
        return d
    return d.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def _hours(a, b):
    a, b = VS.parse_ts(a), VS.parse_ts(b)
    if a is None or b is None:
        return None
    return round((b - a).total_seconds() / 3600.0, 2)


# ----------------------------------------------------------------- injuries
def injury_designations(season, week, teams, *, kickoff_utc=None,
                        observed_before=None) -> Outcome:
    """Point-in-time official injury designations, with their own vintage.

    The gate reads this itself instead of accepting whatever rows a caller
    happens to hold, because a designation without a vintage and a hash cannot
    be audited later, and "it was on the report" is exactly the claim that has
    to survive an audit.
    """
    cut = VS.as_of_cut(kickoff_utc=kickoff_utc, written_at=observed_before)
    if cut is None:
        return Outcome.blocked(
            'ELIGIBILITY_NO_CLOCK',
            'neither observed_before nor kickoff_utc was supplied, so the '
            'injury report cannot be selected point-in-time and the newest '
            'capture would silently be used',
            cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION)
    sel = VS.select('injuries', as_of=cut)
    if sel.state is not State.PASS:
        return sel
    v = sel.value
    blob = _REPO / v.blob
    if not blob.exists():
        return Outcome.blocked(
            'ELIGIBILITY_INJURY_BLOB_MISSING',
            f'the selected injury vintage {v.blob} is not on disk, so the '
            f'designations it carries cannot be read. An unreadable source is '
            f'not an empty one.',
            cause=Cause.DATA, spec_version=SPEC_VERSION, blob=v.blob)
    rows, kept, bad = {}, 0, {}
    with gzip.open(blob, 'rb') as fh:
        for r in csv.DictReader(io.TextIOWrapper(fh)):
            if (r.get('season') != str(season) or r.get('week') != str(week)
                    or r.get('team') not in teams or not r.get('gsis_id')):
                continue
            kept += 1
            st = (r.get('report_status') or '').strip()
            if not st:
                # A BLANK IS NOT A CLEARANCE. `STATUS_EVIDENCE_CONTRACT_
                # EVALUATION.json` settled this: blank and UNSPECIFIED are
                # neither a designation nor an active status. The row is
                # counted and dropped, never read as "fit to play".
                bad['BLANK'] = bad.get('BLANK', 0) + 1
                continue
            if st not in _DESIGNATION:
                bad[st] = bad.get(st, 0) + 1
                continue
            rows[r['gsis_id']] = {
                'report_status': st,
                'report_primary_injury': (r.get('report_primary_injury')
                                          or '').strip(),
                'practice_status': (r.get('practice_status') or '').strip(),
                'team': r.get('team'),
                'full_name': (r.get('full_name') or '').strip()}
    if not kept:
        # AN EMPTY SLICE IS AN ERROR, NOT A CLEAN BILL OF HEALTH.
        return Outcome.blocked(
            'ELIGIBILITY_INJURY_SLICE_EMPTY',
            f'{v.blob} carries no {season} week {week} row for '
            f'{sorted(teams)}. Zero rows is a statement about this capture, '
            f'and reading it as "no club has an injury" is the '
            f'absence-as-success defect. Refusing.',
            cause=Cause.DATA, spec_version=SPEC_VERSION,
            blob=v.blob, content_sha256=v.content_sha256)
    return Outcome.ok(
        'ELIGIBILITY_DESIGNATIONS_OK', value=rows, spec_version=SPEC_VERSION,
        n_rows_in_scope=kept, n_designated=len(rows),
        non_vocabulary_or_blank=bad,
        vocabulary=sorted(_DESIGNATION),
        vintage=v.record(), content_sha256=v.content_sha256,
        known_from=v.published_at, known_from_authority=v.published_authority,
        retrieved_at=v.retrieved_at,
        blank_is_not_a_clearance='a blank report_status is neither a '
                                 'designation nor an active status')


def _delivered_publication_time(sha256):
    """The publication clock a DELIVERED capture carries and the selector drops.

    `vintage_selector.FAMILIES['injuries']['publication_clock']` is
    `effective_scope.valid_from`, which a native mirror capture has and an
    externally delivered artifact does not. The delivered row instead carries
    `provenance.publication_time` -- the league's own stated publication instant,
    authority `DELIVERED_EXPLICIT` -- and `Vintage.published_at` therefore comes
    back None for the strongest clock in the tree. Measured on
    `injuries.0bc645a4b9aa6255`: published_authority `DELIVERED_EXPLICIT`,
    published_at `None`, `provenance.publication_time`
    `2026-09-11T21:02:00Z`.

    This reads it for the gate's own use only. The selector is not patched from
    here; see R2_ELIGIBILITY_GATE.md, which hands that patch over.
    """
    import json as _json
    man = _REPO / 'nfl' / 'vintage_manifest.jsonl'
    if not man.exists() or not sha256:
        return None, None
    for line in man.read_text().splitlines():
        if not line.strip() or sha256[:16] not in line:
            continue
        try:
            row = _json.loads(line)
        except ValueError:
            continue
        v = row.get('value') or {}
        if v.get('sha256') != sha256:
            continue
        pt = (v.get('provenance') or {}).get('publication_time')
        if pt:
            return pt, 'DELIVERED_EXPLICIT (provenance.publication_time)'
    return None, None


def first_seen(season, week, teams, *, kickoff_utc, observed_before=None,
               designations=('Out',)) -> Outcome:
    """The EARLIEST lawful capture that already carried each designation.

    "It was on the report" and "we have known since Friday" are different
    claims, and only the second answers the D7 question -- lawful evidence that
    existed, was available, and did not reach the simulation. The point-in-time
    selector answers the first, because it returns the newest lawful capture and
    says nothing about how long the statement has stood.

    Every lawful vintage at or before the cut is read, not just the chosen one.
    """
    cut = VS.as_of_cut(kickoff_utc=kickoff_utc, written_at=observed_before)
    if cut is None:
        return Outcome.blocked(
            'ELIGIBILITY_NO_CLOCK',
            'first_seen needs a cutoff; without one it would scan captures '
            'that did not exist at prediction time',
            cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION)
    lawful, _ = VS.candidates('injuries', as_of=cut)
    if not lawful:
        return Outcome.blocked(
            'ELIGIBILITY_NO_LAWFUL_INJURY_VINTAGE',
            f'no injury capture was retrieved at or before {cut.isoformat()}',
            cause=Cause.DATA, spec_version=SPEC_VERSION)
    want = set(designations)
    seen, scanned = {}, []
    for v in lawful:
        blob = _REPO / v.blob
        if not blob.exists():
            continue
        pub, auth = v.published_at, v.published_authority
        if pub is None:
            pub, alt = _delivered_publication_time(v.content_sha256)
            if pub is not None:
                auth = alt
        known = pub or v.retrieved_at
        basis = ('PUBLICATION' if pub else
                 'OBSERVATION_UPPER_BOUND (no publication clock)')
        scanned.append({'blob': v.blob, 'content_sha256': v.content_sha256,
                        'retrieved_at': v.retrieved_at, 'known_from': known,
                        'known_from_authority': auth, 'clock_basis': basis})
        with gzip.open(blob, 'rb') as fh:
            for r in csv.DictReader(io.TextIOWrapper(fh)):
                if (r.get('season') != str(season)
                        or r.get('week') != str(week)
                        or r.get('team') not in teams
                        or not r.get('gsis_id')):
                    continue
                st = (r.get('report_status') or '').strip()
                if st not in want:
                    continue
                pid = r['gsis_id']
                prev = seen.get(pid)
                # EARLIEST wins. The candidate list is newest-first, so every
                # further hit overwrites -- which is the intent.
                if prev is None or VS.parse_ts(known) <= VS.parse_ts(
                        prev['known_from']):
                    seen[pid] = {
                        'gsis_id': pid, 'team': r.get('team'),
                        'full_name': (r.get('full_name') or '').strip(),
                        'report_status': st,
                        'first_vintage': v.blob,
                        'content_hash': v.content_sha256,
                        'known_from': known,
                        'known_from_authority': auth,
                        'clock_basis': basis,
                        'hours_known_before_kickoff': _hours(known,
                                                            kickoff_utc),
                        'n_vintages_carrying': (prev or {}).get(
                            'n_vintages_carrying', 0) + 1}
                else:
                    prev['n_vintages_carrying'] += 1
    if not scanned:
        return Outcome.blocked(
            'ELIGIBILITY_NO_READABLE_INJURY_VINTAGE',
            'every lawful injury vintage is missing from disk',
            cause=Cause.DATA, spec_version=SPEC_VERSION)
    return Outcome.ok(
        'ELIGIBILITY_FIRST_SEEN_OK', value=seen, spec_version=SPEC_VERSION,
        n_players=len(seen), n_vintages_scanned=len(scanned),
        designations=sorted(want), as_of=cut.isoformat(),
        vintages=scanned,
        what_this_is='the earliest lawful capture carrying the designation, '
                     'which is how long the statement has stood -- not the '
                     'capture the point-in-time selector would choose')


# ----------------------------------------------------------------- snapshot
def snapshot(season, week, teams, players, *, kickoff_utc,
             observed_before=None, game_id=None,
             official_inactive_ids=None, official_inactives_vintage=None,
             suspensions=None, suspensions_vintage=None) -> Outcome:
    """The Stage-0 `eligibility_snapshot`: one audited row per player.

    `official_inactive_ids=None` means NO LIST WAS AVAILABLE and is recorded as
    such. It is not the same as `official_inactive_ids=()`, which is a list
    that was read and named nobody. The first is ignorance; the second is
    evidence. Collapsing them is how "nobody is out" gets manufactured.
    """
    if not players:
        return Outcome.fail(
            'ELIGIBILITY_NO_PLAYERS',
            'snapshot was handed an empty player list. An empty choice set is '
            'a refusal, not an eligibility finding.')
    ids = [q.get('gsis_id') for q in players]
    missing = [i for i, q in enumerate(players) if not q.get('gsis_id')]
    if missing:
        return Outcome.fail(
            'ELIGIBILITY_IDENTITY_UNRESOLVED',
            f'{len(missing)} player(s) carry no gsis_id. Eligibility is keyed '
            f'on identity and fuzzy name matching is forbidden, so this is a '
            f'refusal rather than a best effort.',
            n_missing=len(missing))
    if len(set(ids)) != len(ids):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        return Outcome.fail(
            'ELIGIBILITY_DUPLICATE_PLAYER',
            f'{len(dup)} gsis_id(s) appear more than once in the pool, so one '
            f'player would carry two eligibility rows and the later would win '
            f'silently', duplicates=dup[:10])

    rs = RS.status_map(season, week, teams, observed_before=observed_before,
                       kickoff_utc=kickoff_utc)
    # ROSTER STATUS IS AUTHORITY RANK 3, AND A RANK THAT CANNOT BE READ IS AN
    # UNAVAILABLE AUTHORITY, NOT AN EMPTY LEAGUE.
    #
    # This returned the refusal, so a week with no raw status capture killed
    # the snapshot and every stage downstream of it. Measured on 2026 week 2:
    # ROSTER_STATUS_EMPTY propagated into appearance, participation,
    # targets_carries, conversion, td_layer and qb_layer, and DET-BUF produced
    # no skill-position board at all.
    #
    # Ranks 1 and 2 -- the official inactive list and the official injury
    # report -- do not depend on rank 3 and still exclude exactly who they
    # excluded before. What is lost is the ability to say a player is on the
    # ACTIVE ROSTER, and that loss is now RECORDED rather than fatal:
    # `participant_class` supplies the graded participation probability the
    # missing rank would otherwise have decided, and the caller can see which
    # of the two it got.
    roster_status_authority = 'READ'
    if rs.state is not State.PASS:
        roster_status_authority = f'UNAVAILABLE:{rs.code}'
        statuses = {}
    else:
        statuses = rs.value

    inj = injury_designations(season, week, teams, kickoff_utc=kickoff_utc,
                              observed_before=observed_before)
    # AUTHORITY RANK 2, GRADED THE SAME WAY AS RANK 3.
    #
    # The refusal it returns is CORRECT and stays: an empty injury slice is a
    # statement about a capture, and reading it as "no club has an injury" is
    # the absence-as-success defect. But that is a fact for the caller to
    # GRADE, not to die on. On the Tuesday before a Thursday game the week's
    # official injury report has not been published yet -- that is an EARLY
    # forecast vintage, not a broken pipeline, and refusing it means the
    # product has nothing to show until Wednesday.
    #
    # What is lost is the ability to say a player is OUT or DOUBTFUL, and it
    # is recorded. Rank 1, the official inactive list, is unaffected; so is the
    # graded participation class. Nobody is silently promoted to healthy: an
    # unavailable rank means UNKNOWN at that rank, and the publication state
    # downstream is what tells a reader how much evidence stands behind the
    # number.
    injury_authority = 'READ'
    if inj.state is not State.PASS:
        injury_authority = f'UNAVAILABLE:{inj.code}'
        # EVERY KEY THE CONSUMER READS IS SUPPLIED, EXPLICITLY UNAVAILABLE.
        # Omitting them raised KeyError: 'vintage' inside the appearance stage
        # -- an unnamed crash two layers from the cause, which is exactly the
        # shape this repair exists to remove. An absent authority has to be
        # SHAPED like the authority it replaces, or every downstream reader
        # becomes a place the pipeline can die.
        _why = inj.code
        inj = Outcome.ok(
            'ELIGIBILITY_DESIGNATIONS_UNAVAILABLE', value={},
            spec_version=SPEC_VERSION, n_rows_in_scope=0, n_designated=0,
            unavailable_reason=_why,
            vintage={'blob': None, 'unavailable_reason': _why},
            content_sha256=None, retrieved_at=None,
            known_from=None, known_from_authority='UNAVAILABLE',
            non_vocabulary_or_blank=0, vocabulary=sorted(_DESIGNATION))

    inactive = None if official_inactive_ids is None \
        else set(official_inactive_ids)
    susp = dict(suspensions or {})

    roster_vintage = {
        'source': rs.evidence.get('source'),
        'content_sha256': rs.evidence.get('content_sha256'),
        'observed_at': rs.evidence.get('observed_at'),
        'known_from': (rs.evidence.get('vintage') or {}).get('published_at'),
        'known_from_authority': (rs.evidence.get('vintage')
                                 or {}).get('published_authority')}
    injury_vintage = {
        'source': inj.evidence['vintage']['blob'],
        'content_sha256': inj.evidence['content_sha256'],
        'observed_at': inj.evidence['retrieved_at'],
        'known_from': inj.evidence['known_from'],
        'known_from_authority': inj.evidence['known_from_authority']}
    inactives_vintage = dict(official_inactives_vintage or {})

    out, counts = {}, {}
    conflicts = []
    for q in players:
        pid = q['gsis_id']
        claims = []
        if inactive is not None and pid in inactive:
            claims.append(('OFFICIAL_INACTIVE', inactives_vintage))
        if pid in susp:
            claims.append(('SUSPENDED', dict(suspensions_vintage or {},
                                             detail=susp[pid])))
        d = inj.value.get(pid)
        if d is not None:
            claims.append((_DESIGNATION[d['report_status']], injury_vintage))
        st = statuses.get(pid)
        if st in _POSTHOC_ROSTER_STATUS:
            # Unreachable through `status_map`, which refuses the whole capture
            # on a POSTHOC code. Named so a future caller supplying statuses
            # directly cannot slip one past the gate.
            return Outcome.fail(
                'ELIGIBILITY_POSTHOC_STATUS',
                f'{pid} carries roster status {st!r}, which is assigned after '
                f'a game is played. That is an outcome, not pregame '
                f'eligibility, and using it would put the answer into the '
                f'question.', player=pid, status=st)
        if st in _ROSTER_STATUS:
            claims.append((_ROSTER_STATUS[st], roster_vintage))

        if not claims:
            status = 'NO_EVIDENCE'
            vintage = {}
        else:
            ranked = sorted(
                claims,
                key=lambda c: AUTHORITY_RANK[STATUS[c[0]][0]])
            best_rank = AUTHORITY_RANK[STATUS[ranked[0][0]][0]]
            tied = [c for c in ranked
                    if AUTHORITY_RANK[STATUS[c[0]][0]] == best_rank]
            kinds = {c[0] for c in tied}
            if len(kinds) > 1:
                # TWO AUTHORITIES OF EQUAL RANK DISAGREEING IS A REFUSAL.
                # Picking one by dict order is a precedence rule nobody
                # declared, and it would be invisible in the artifact.
                conflicts.append({'gsis_id': pid, 'rank': best_rank,
                                  'claims': sorted(kinds)})
                continue
            status, vintage = ranked[0]

        authority, determination, sim, reason = STATUS[status]
        rec = {
            'gsis_id': pid,
            'team': q.get('team'),
            'position': q.get('position'),
            'status': status,
            'determination': determination,
            'authority': authority,
            'authority_rank': (AUTHORITY_RANK.get(authority)
                               if authority else None),
            'source_vintage': vintage.get('source'),
            'content_hash': vintage.get('content_sha256'),
            'known_from': vintage.get('known_from'),
            'known_from_authority': vintage.get('known_from_authority'),
            # RETRIEVAL IS NEVER EARLIER THAN PUBLICATION, so the observation
            # clock is an upper bound on when the statement became knowable and
            # is the honest fallback where no publication clock exists at all
            # (the raw roster family has none). It is a SEPARATE field: writing
            # an observation time into `known_from` would dress a retrieval
            # clock up as the league's.
            'known_by_no_later_than': (vintage.get('known_from')
                                       or vintage.get('observed_at')),
            'hours_known_before_kickoff': _hours(
                vintage.get('known_from') or vintage.get('observed_at'),
                kickoff_utc),
            'reason': reason,
            'simulation_eligibility': sim,
            'gameday_activity': ('RESOLVED' if inactive is not None
                                 else 'UNRESOLVED'),
        }
        if inactive is None and sim == IN_CHOICE_SET:
            # The whole-game ignorance, written on every row it touches rather
            # than in a footnote nobody reads.
            rec['unresolved_note'] = (
                'no official gameday inactive list was available for this '
                'game, so whether he dresses is UNKNOWN. He is in the choice '
                'set because unresolved is not ineligible, and the board is '
                'not final')
        out[pid] = rec
        counts[status] = counts.get(status, 0) + 1

    if conflicts:
        return Outcome.fail(
            'ELIGIBILITY_AUTHORITY_CONFLICT',
            f'{len(conflicts)} player(s) carry two statements of equal '
            f'authority rank that disagree. There is no declared tiebreak, so '
            f'this refuses rather than choosing one silently.',
            conflicts=conflicts[:10], spec_version=SPEC_VERSION)

    determined_out = sorted(p for p, r in out.items()
                            if r['simulation_eligibility']
                            == EXCLUDED_DETERMINISTIC)
    pool_out = sorted(p for p, r in out.items()
                      if r['simulation_eligibility'] == EXCLUDED_BY_POOL_RULE)
    unresolved = sorted(p for p, r in out.items()
                        if r['determination'] == UNCERTAIN
                        and r['simulation_eligibility'] == IN_CHOICE_SET)
    return Outcome.ok(
        'ELIGIBILITY_SNAPSHOT_OK', value=out, spec_version=SPEC_VERSION,
        game_id=game_id, season=season, week=week, teams=sorted(teams),
        kickoff_utc=_iso(kickoff_utc), observed_before=_iso(observed_before),
        n_players=len(out), status_counts=dict(sorted(counts.items())),
        n_determined_ineligible=len(determined_out),
        determined_ineligible=determined_out,
        n_excluded_by_pool_rule=len(pool_out),
        excluded_by_pool_rule=pool_out,
        n_unresolved_in_choice_set=len(unresolved),
        official_inactive_list=('READ' if inactive is not None
                                else 'NOT_AVAILABLE'),
        gameday_activity=('RESOLVED' if inactive is not None
                          else 'UNRESOLVED'),
        board_finality=('FINAL_ELIGIBILITY_INPUTS_PRESENT'
                        if inactive is not None
                        else 'PRELIMINARY_PROVISIONAL -- no official gameday '
                             'inactive list; final eligibility is NOT '
                             'inferred and no player is assumed to dress'),
        roster_status_authority=roster_status_authority,
        injury_authority=injury_authority,
        roster_vintage=roster_vintage, injury_vintage=injury_vintage,
        designation_scan=inj.evidence['non_vocabulary_or_blank'],
        absence_is_not_evidence='a player absent from the injury report is '
                                'NO_DESIGNATION, which is a fact about the '
                                'report and not about the player')


# --------------------------------------------------------------- choice set
def choice_set(players, snap: Outcome) -> Outcome:
    """The pool the allocator is allowed to see. Removal happens HERE.

    Every removal is named with its authority and its reason, and the two kinds
    of removal are reported apart: a determination of ineligibility and the R5
    denominator rule are not the same act and must not be totalled together.
    """
    if snap.state is not State.PASS:
        return Outcome.blocked(
            'BLOCKED_UPSTREAM_ELIGIBILITY',
            f'the choice set needs an eligibility snapshot; upstream is '
            f'{snap.state.value}[{snap.code}]', cause=Cause.DEPENDENCY)
    rec = snap.value
    unknown = [q.get('gsis_id') for q in players
               if q.get('gsis_id') not in rec]
    if unknown:
        # A PLAYER THE SNAPSHOT NEVER SAW CANNOT BE JUDGED BY IT. Passing him
        # through would mean the gate silently covers only part of the pool.
        return Outcome.fail(
            'CHOICE_SET_PLAYER_NOT_IN_SNAPSHOT',
            f'{len(unknown)} player(s) in the pool carry no eligibility row. '
            f'The gate would then govern only part of the choice set, which '
            f'is indistinguishable from not governing it at all.',
            players=[u for u in unknown[:10]])
    keep, removed = [], {}
    for q in players:
        r = rec[q['gsis_id']]
        if r['simulation_eligibility'] == IN_CHOICE_SET:
            keep.append(q)
        else:
            removed.setdefault(r['simulation_eligibility'], []).append({
                'gsis_id': r['gsis_id'], 'team': r['team'],
                'position': r['position'], 'status': r['status'],
                'authority': r['authority'],
                'authority_rank': r['authority_rank'],
                'known_from': r['known_from'],
                'known_by_no_later_than': r['known_by_no_later_than'],
                'hours_known_before_kickoff':
                    r['hours_known_before_kickoff'],
                'content_hash': r['content_hash'],
                'reason': r['reason']})
    if not keep:
        return Outcome.fail(
            'CHOICE_SET_EMPTY',
            'every player was removed, so there is nobody to allocate to. An '
            'empty choice set is a refusal, not an allocation of nothing.',
            n_in=len(players))
    det = removed.get(EXCLUDED_DETERMINISTIC, [])
    pool = removed.get(EXCLUDED_BY_POOL_RULE, [])
    return Outcome.ok(
        'CHOICE_SET_OK', value=keep, spec_version=SPEC_VERSION,
        n_in=len(players), n_kept=len(keep),
        n_removed_determined_ineligible=len(det),
        n_removed_by_pool_rule=len(pool),
        removed_determined_ineligible=det,
        removed_by_pool_rule=pool,
        enforcement='CHOICE_SET_CONSTRUCTION',
        not_allocate_then_zero='a removed player has no row in any allocation, '
                               'so no mass is created for him and none has to '
                               'be renormalised away afterwards',
        determined_and_pool_rule_are_different='the first is a statement by an '
                                               'authority that he cannot play; '
                                               'the second is R5 keeping the '
                                               'C-denominator the size it was '
                                               'fitted on')


# ---------------------------------------------------------------- scenarios
def scenarios(snap: Outcome, *, weights=None) -> Outcome:
    """Discrete eligibility worlds, or an honest refusal to invent them.

    A world is `{'label', 'excluded', 'weight'}`. The engine already draws
    per-player Bernoullis, so a world is something it can simulate directly.
    Nothing here multiplies a projection by an availability probability: that
    produces a number no world realises and hides which world it came from.
    """
    if snap.state is not State.PASS:
        return Outcome.blocked(
            'BLOCKED_UPSTREAM_ELIGIBILITY',
            f'scenarios need an eligibility snapshot; upstream is '
            f'{snap.state.value}[{snap.code}]', cause=Cause.DEPENDENCY)
    rec = snap.value
    det = sorted(p for p, r in rec.items()
                 if r['simulation_eligibility'] == EXCLUDED_DETERMINISTIC)
    unresolved = sorted(
        (p for p, r in rec.items()
         if r['determination'] == UNCERTAIN
         and r['simulation_eligibility'] == IN_CHOICE_SET
         and r['status'] in ('INJURY_DOUBTFUL', 'INJURY_QUESTIONABLE')))
    base = {'label': 'BASE', 'excluded': det, 'weight': 1.0,
            'basis': 'every determined ineligibility, and nothing else'}
    if not weights:
        return Outcome.ok(
            'ELIGIBILITY_SCENARIOS_SINGLE', value=[base],
            spec_version=SPEC_VERSION, n_worlds=1,
            weights_estimated=False,
            unresolved_not_modelled=unresolved,
            n_unresolved_not_modelled=len(unresolved),
            detail='no evidence-based weights were supplied, so ONE world is '
                   'returned and the unresolved players are named rather than '
                   'given an invented probability. A fabricated weight would '
                   'be indistinguishable in the artifact from a measured one.')
    bad = [p for p in weights if p not in rec]
    if bad:
        return Outcome.fail(
            'SCENARIO_UNKNOWN_PLAYER',
            f'{len(bad)} weighted player(s) are not in the snapshot',
            players=sorted(bad)[:10])
    fixed = [p for p in weights if p in det]
    if fixed:
        return Outcome.fail(
            'SCENARIO_WEIGHTS_A_DETERMINATION',
            f'{len(fixed)} player(s) are determined ineligible and were given '
            f'a scenario weight. A determination is not a coin flip; weighting '
            f'it would put mass back on a player an authority ruled out.',
            players=sorted(fixed)[:10])
    worlds, wsum = [], 0.0
    # Worlds are the product over independently weighted players, which is a
    # declared independence assumption and is recorded as one.
    import itertools
    keys = sorted(weights)
    for bits in itertools.product((0, 1), repeat=len(keys)):
        w, ex = 1.0, list(det)
        for k, b in zip(keys, bits):
            p_out = float(weights[k])
            if not 0.0 <= p_out <= 1.0:
                return Outcome.fail(
                    'SCENARIO_WEIGHT_OUT_OF_RANGE',
                    f'{k} carries weight {p_out}, which is not a probability',
                    player=k, weight=p_out)
            if b:
                w *= p_out
                ex.append(k)
            else:
                w *= (1.0 - p_out)
        if w <= 0.0:
            continue
        worlds.append({'label': 'OUT:' + ','.join(sorted(set(ex) - set(det)))
                                or 'BASE',
                       'excluded': sorted(ex), 'weight': w,
                       'basis': 'supplied per-player weights'})
        wsum += w
    return Outcome.ok(
        'ELIGIBILITY_SCENARIOS_OK', value=worlds, spec_version=SPEC_VERSION,
        n_worlds=len(worlds), weight_sum=round(wsum, 12),
        weights_estimated=True, weighted_players=keys,
        independence_assumed='worlds are the product over independently '
                             'weighted players; correlated absences are NOT '
                             'modelled and this is a declared limitation')


# ------------------------------------------------- the invariant, over draws
def assert_zero_opportunity_over_draws(layers, arrays, ineligible_ids,
                                       *, atol=0.0) -> Outcome:
    """Every determined-ineligible player holds EXACTLY zero in EVERY draw.

    `layers` is the draw manifest's per-layer block: {layer: {'row_axis',
    'row_ids', 'metrics'}}. `arrays` maps 'layer/metric' to the stored matrix.

    THIS READS THE DRAWS. It does not read a config flag, a summary, or an
    evidence key, because every one of those can say zero while the matrix does
    not. Two ways to hold zero are accepted and reported apart:

        ABSENT     he has no row at all -- the choice-set gate worked
        ZERO_ROW   he has a row and every cell of it is zero

    ABSENT is the state this gate is for. ZERO_ROW is what allocate-then-zero
    produces, and it is accepted as a pass on the invariant while being counted
    separately, because the invariant is about opportunity and the two differ in
    denominator handling rather than in his own number.
    """
    ids = sorted(set(ineligible_ids or ()))
    if not ids:
        return Outcome.blocked(
            'ZERO_OPPORTUNITY_NOTHING_TO_CHECK',
            'no determined-ineligible player was supplied, so this assertion '
            'has no content. Reporting it as a pass would be a vacuous green.',
            cause=Cause.DATA, spec_version=SPEC_VERSION)
    if not layers:
        return Outcome.fail(
            'ZERO_OPPORTUNITY_NO_LAYERS',
            'no draw layers were supplied. An empty check is not a passing '
            'check.')
    player_layers = {n: L for n, L in layers.items()
                     if L.get('row_axis') == 'gsis_id'}
    if not player_layers:
        # A CHECK WITH NOTHING TO CHECK IS NOT A PASS. Every layer here is
        # team-axis, so no player-level opportunity was read at all.
        return Outcome.fail(
            'ZERO_OPPORTUNITY_NO_PLAYER_AXIS',
            f'none of the {len(layers)} supplied layer(s) carries '
            f"row_axis == 'gsis_id', so no player-level opportunity exists to "
            f'read. Returning PASS here would be a vacuous green.',
            layers=sorted(layers))
    checked, verdicts, violations = 0, {}, []
    n_rows_scanned = 0
    for pid in ids:
        placed = []
        for lname, L in sorted(player_layers.items()):
            rows = list(L.get('row_ids') or ())
            n_rows_scanned += len(rows)
            if pid not in rows:
                continue
            i = rows.index(pid)
            for metric in sorted(L.get('metrics') or ()):
                key = _array_key(arrays, lname, metric)
                if key is None:
                    return Outcome.fail(
                        'ZERO_OPPORTUNITY_MATRIX_MISSING',
                        f'the manifest declares {lname}/{metric} but no '
                        f'matrix was supplied for it, so the invariant cannot '
                        f'be read off the draws for {pid}',
                        layer=lname, metric=metric, player=pid,
                        supplied=sorted(arrays)[:20])
                M = np.asarray(arrays[key])
                if M.ndim != 2 or M.shape[0] != len(rows):
                    return Outcome.fail(
                        'ZERO_OPPORTUNITY_SHAPE_MISMATCH',
                        f'{lname}/{metric} has shape {tuple(M.shape)} against '
                        f'{len(rows)} declared row(s); the row index cannot be '
                        f'trusted', layer=lname, metric=metric,
                        shape=list(M.shape), n_rows=len(rows))
                row = np.asarray(M[i], dtype=np.float64)
                checked += int(row.size)
                nz = int(np.count_nonzero(np.abs(row) > atol))
                if nz:
                    violations.append({
                        'gsis_id': pid, 'layer': lname, 'metric': metric,
                        'n_draws': int(row.size), 'n_nonzero_draws': nz,
                        'max_abs': float(np.max(np.abs(row))),
                        'mean': float(row.mean())})
                placed.append(key)
        verdicts[pid] = 'ABSENT' if not placed else (
            'ZERO_ROW' if not any(v['gsis_id'] == pid for v in violations)
            else 'NONZERO')
    absent = sorted(p for p, v in verdicts.items() if v == 'ABSENT')
    zero_row = sorted(p for p, v in verdicts.items() if v == 'ZERO_ROW')
    if violations:
        return Outcome.fail(
            'ZERO_OPPORTUNITY_VIOLATED',
            f'{len({v["gsis_id"] for v in violations})} determined-ineligible '
            f'player(s) hold strictly positive modelled opportunity in the '
            f'stored draws. This is read off the matrices, not off a flag.',
            spec_version=SPEC_VERSION, n_violations=len(violations),
            violations=violations[:20],
            n_players_checked=len(ids), n_cells_read=checked)
    return Outcome.ok(
        'ZERO_OPPORTUNITY_HOLDS', value=verdicts, spec_version=SPEC_VERSION,
        n_players_checked=len(ids), n_cells_read=checked,
        n_player_layers=len(player_layers),
        n_row_slots_scanned=n_rows_scanned,
        zero_cells_read_means=('every ineligible player is ABSENT from every '
                               'row index, so there is no cell of his to read. '
                               'That is the gate working, and it is reported '
                               'as its own number rather than hidden inside a '
                               'green'),
        n_absent_from_every_layer=len(absent),
        n_present_but_all_zero=len(zero_row),
        absent=absent, zero_row=zero_row,
        read_from='the stored draw matrices, cell by cell',
        absent_is_the_gate='ABSENT means he never entered the choice set. '
                           'ZERO_ROW means he entered and was zeroed, which '
                           'passes this invariant and still leaves the '
                           'renormalisation the gate exists to avoid')


def _array_key(arrays, layer, metric):
    """The stored artifact spells it `layer__metric`; the manifest spells it
    `layer/metric`. Both are accepted, and neither is guessed at: a key that
    matches nothing returns None and the caller refuses by name."""
    for k in (f'{layer}/{metric}', f'{layer}__{metric}'):
        if k in arrays:
            return k
    return None


def load_draw_arrays(npz_path):
    """Every matrix in a stored draw artifact, under both spellings."""
    out = {}
    with np.load(npz_path) as z:
        for k in z.files:
            M = np.asarray(z[k])
            out[k] = M
            if '__' in k:
                out[k.replace('__', '/', 1)] = M
    return out
