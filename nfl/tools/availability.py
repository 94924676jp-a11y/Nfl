#!/usr/bin/env python3.12
"""Current availability, classified by the strength of the evidence behind it.

WHY THIS IS A SEPARATE MODULE. Availability is the one field on a DFS slate where a
wrong value is not a small error: it silently reassigns a player's entire opportunity
tree. Every wrong answer this project has produced in this area had the same shape --
something that was *reported*, *predicted*, or *absent* got stored in the same field
as something that was *confirmed*, and by the time it was read nobody could tell them
apart. So a status here is never a bare string. It is a status plus the tier of
evidence that supports it, and the pair is checked.

THE STATUS SET, AND ONE CORRECTION TO THE OWNER'S LIST.

The owner asked for `CONFIRMED_ACTIVE`, `CONFIRMED_INACTIVE`,
`ACTIVE_NOT_ON_INACTIVE_LIST`, `UNKNOWN`. Three of those four are right. The fourth
cannot come from an inactive list at all, and this repository already knew it:
`ingest_inactives.py` records, as its own step 4b, "absence from the list carries no
positive claim", and its docstring says pregame ACT "stays ROSTER_ACTIVE and nothing
here promotes it to GAME_ACTIVE".

An inactive list is a list of absences. A player not on it is *not named as out* --
which is `ACTIVE_NOT_ON_INACTIVE_LIST`, exactly as the owner wrote it. It is not the
same as confirmed to be playing: he can still be a late scratch, or dress and take
zero snaps. `CONFIRMED_ACTIVE` therefore stays in the set but is reachable only from a
positive document -- observed participation, or an official active/dress list -- and
never by elimination. Collapsing the two would recreate the defect the existing
pipeline already guards.

THE GUARD. `resolve_universe` will not return classified rows if any row carries a
CONFIRMED_* or ACTIVE_NOT_ON_* status without a captured official document behind it.
Not a warning next to the rows -- no rows. That is the difference between a guard that
reports and a guard that is load-bearing, and the bypass test proves the protected
action does not occur.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'availability-2026w3-1'

# --- evidence tiers, strongest first -----------------------------------------
TIER_OFFICIAL_CAPTURED = 'OFFICIAL_DOCUMENT_CAPTURED'
TIER_OBSERVED = 'OBSERVED_PARTICIPATION'
#: a club's own release, cited by URL in relayed research. We do not hold the bytes.
TIER_OFFICIAL_RELEASE_CITED = 'OFFICIAL_TEAM_RELEASE_CITED'
#: a populated aggregator inactive list (RotoWire), relayed. Real, not a document.
TIER_AGGREGATOR_REPORTED = 'AGGREGATOR_REPORTED'
TIER_EXTERNAL_SECONDHAND = 'EXTERNAL_RESEARCH_SECONDHAND'
TIER_INTERNAL_INJURY_FEED = 'INTERNAL_INJURY_FEED'
TIER_PREDICTED = 'PREDICTED_NOT_OFFICIAL'
TIER_NONE = 'NO_EVIDENCE_HELD'

TIERS = (TIER_OFFICIAL_CAPTURED, TIER_OBSERVED, TIER_OFFICIAL_RELEASE_CITED,
         TIER_AGGREGATOR_REPORTED, TIER_EXTERNAL_SECONDHAND,
         TIER_INTERNAL_INJURY_FEED, TIER_PREDICTED, TIER_NONE)

# --- statuses ----------------------------------------------------------------
CONFIRMED_INACTIVE = 'CONFIRMED_INACTIVE'
CONFIRMED_ACTIVE = 'CONFIRMED_ACTIVE'
ACTIVE_NOT_ON_INACTIVE_LIST = 'ACTIVE_NOT_ON_INACTIVE_LIST'
REPORTED_OUT_UNVERIFIED = 'REPORTED_OUT_UNVERIFIED'
REPORTED_DOUBTFUL_UNVERIFIED = 'REPORTED_DOUBTFUL_UNVERIFIED'
UNKNOWN_ACTIVE_STATE = 'UNKNOWN_ACTIVE_STATE'
UNKNOWN = 'UNKNOWN'
#: named inactive on a club's own release, cited but not captured here.
REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED = 'REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED'
#: named inactive on a populated aggregator list, relayed.
REPORTED_INACTIVE_HIGH_CONFIDENCE = 'REPORTED_INACTIVE_HIGH_CONFIDENCE'
#: reported as NOT appearing on a populated inactive list.
REPORTED_ACTIVE_NOT_ON_LIST = 'REPORTED_ACTIVE_NOT_ON_LIST'
#: the lists exist but their full contents were never relayed to us. NOT active.
UNKNOWN_NOT_RELAYED = 'UNKNOWN_NOT_RELAYED'

STATUSES = (CONFIRMED_INACTIVE, CONFIRMED_ACTIVE, ACTIVE_NOT_ON_INACTIVE_LIST,
            REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED,
            REPORTED_INACTIVE_HIGH_CONFIDENCE, REPORTED_ACTIVE_NOT_ON_LIST,
            REPORTED_OUT_UNVERIFIED, REPORTED_DOUBTFUL_UNVERIFIED,
            UNKNOWN_ACTIVE_STATE, UNKNOWN_NOT_RELAYED, UNKNOWN)

#: A status may only be used when its evidence reaches at least this tier.
STATUS_REQUIRES_TIER = {
    CONFIRMED_INACTIVE: (TIER_OFFICIAL_CAPTURED,),
    ACTIVE_NOT_ON_INACTIVE_LIST: (TIER_OFFICIAL_CAPTURED,),
    CONFIRMED_ACTIVE: (TIER_OFFICIAL_CAPTURED, TIER_OBSERVED),
    REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED: (TIER_OFFICIAL_RELEASE_CITED,),
    REPORTED_INACTIVE_HIGH_CONFIDENCE: (TIER_AGGREGATOR_REPORTED,
                                        TIER_OFFICIAL_RELEASE_CITED),
    REPORTED_ACTIVE_NOT_ON_LIST: (TIER_AGGREGATOR_REPORTED,
                                  TIER_OFFICIAL_RELEASE_CITED),
}

#: Statuses that mean "he is not playing" for the purpose of a redistribution tree.
#: REPORTED_* is included deliberately: a named absence on a populated list is the
#: strongest evidence available today, and refusing to build a role tree on it would
#: mean refusing to do the football work at all. The tree records its own tier.
ABSENT_STATUSES = (CONFIRMED_INACTIVE, REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED,
                   REPORTED_INACTIVE_HIGH_CONFIDENCE, REPORTED_OUT_UNVERIFIED)

#: Statuses that are NOT a claim of absence and must never be treated as one.
NOT_A_CLAIM_OF_ABSENCE = (UNKNOWN, UNKNOWN_NOT_RELAYED, UNKNOWN_ACTIVE_STATE,
                          REPORTED_DOUBTFUL_UNVERIFIED)

#: Statuses that are a claim the player is available. None of them is CONFIRMED_ACTIVE.
PRESENT_STATUSES = (CONFIRMED_ACTIVE, ACTIVE_NOT_ON_INACTIVE_LIST,
                    REPORTED_ACTIVE_NOT_ON_LIST)

SEMANTICS = {
    'UNKNOWN_IS_NOT_ZERO': (
        'UNKNOWN means the evidence does not resolve the state. It does not mean '
        'healthy, it does not mean out, and it must never be rendered as 0, as '
        'ACTIVE, or as a reason to drop a row.'),
    'QUESTIONABLE_IS_NOT_ACTIVE': (
        'A QUESTIONABLE designation is UNKNOWN_ACTIVE_STATE. It resolves only when an '
        'official game-day list or observed participation says so.'),
    'REPORTED_IS_NOT_CONFIRMED': (
        'REPORTED_OUT_UNVERIFIED is a secondhand claim that a club designated a player '
        'OUT. A final OUT designation does in practice mean a player will not play, so '
        'this is the strongest absence signal short of the list -- but we hold no '
        'captured document, so it is not CONFIRMED_INACTIVE and does not get that '
        'name.'),
    'NOT_RELAYED_IS_NOT_ACTIVE': (
        'The second pass says the nine lists are populated but never enumerates one in '
        'full. A DK player it does not mention is UNKNOWN_NOT_RELAYED, not active. '
        'Reading silence as activation would promote about 420 of 457 rows on no '
        'evidence, which is the same defect as reading missing as zero.'),
    'REPORTED_INACTIVE_IS_ACTIONABLE_BUT_NOT_CONFIRMED': (
        'A name on a populated aggregator inactive list is strong enough to build a '
        'role tree on and is treated that way. It is still not CONFIRMED_INACTIVE, '
        'because that name is reserved for a captured document, and the source itself '
        'asked for exactly this distinction.'),
    'NOT_ON_THE_LIST_IS_NOT_CONFIRMED_ACTIVE': (
        'An inactive list enumerates absences. Absence from it is '
        'ACTIVE_NOT_ON_INACTIVE_LIST, never CONFIRMED_ACTIVE; a late scratch and a '
        'healthy scratch both defeat the stronger reading.'),
}


class ConfirmationWithoutEvidence(RuntimeError):
    """Raised when a CONFIRMED_* status is asserted with no captured document."""


# --- official captures -------------------------------------------------------
LIVE = _REPO / 'nfl/research/live'
EARLY_GAMES = ('CAR@CLE', 'CIN@PIT', 'HOU@IND', 'KC@MIA', 'LAC@BUF',
               'NE@JAX', 'NYJ@DET', 'SEA@WAS', 'TEN@NYG')
SEASON, WEEK = 2026, 3


def _game_id(key: str) -> str:
    away, home = key.split('@')
    return f'{SEASON}_{WEEK:02d}_{away}_{home}'


def official_capture_index():
    """Captured official inactive documents for the nine Early Only games.

    Reads `nfl/research/live/<game_id>/INACTIVES_INGESTION.json`, which is the path
    `ingest_inactives.py` already writes. No new plumbing: the moment a capture lands
    there this function finds it and the whole POST state fills in.
    """
    found, absent = {}, []
    for key in EARLY_GAMES:
        gid = _game_id(key)
        p = LIVE / gid / 'INACTIVES_INGESTION.json'
        if not p.exists():
            absent.append({'game': key, 'game_id': gid,
                           'expected_at': str(p.relative_to(_REPO))})
            continue
        rec = json.loads(p.read_text())
        by_team = {}
        for step in rec.get('steps', ()):
            if step.get('code') == 'POST_INACTIVES_COMPLETE':
                by_team = step.get('inactive_by_team') or {}
        if not by_team:
            return Outcome.fail(
                'OFFICIAL_CAPTURE_MALFORMED',
                f'{gid} has an ingestion record with no POST_INACTIVES_COMPLETE '
                f'inactive_by_team; a capture that parsed to nothing is not a capture',
                game=key, path=str(p.relative_to(_REPO)))
        found[key] = {
            'game_id': gid,
            'inactive_gsis_by_club': by_team,
            'result': rec.get('result'),
            'provenance': rec.get('provenance'),
            'kickoff_utc': rec.get('kickoff_utc'),
            'path': str(p.relative_to(_REPO)),
        }
    if not found:
        return Outcome.blocked(
            'OFFICIAL_INACTIVES_NOT_CAPTURED',
            f'no official inactive capture exists for any of the {len(EARLY_GAMES)} '
            f'Early Only games. Checked {len(EARLY_GAMES)} paths under '
            f'nfl/research/live/. This is OUT-035 and it is assigned to the networked '
            f'agent, not blocked for the project.',
            cause=Cause.DATA, games_absent=absent, n_absent=len(absent))
    return Outcome.ok('OFFICIAL_CAPTURE_INDEX', {'found': found, 'absent': absent},
                      f'{len(found)} of {len(EARLY_GAMES)} games captured',
                      n_found=len(found), n_absent=len(absent))


# --- classification ----------------------------------------------------------
def classify(*, gsis_id, club, captures, external_claim=None, injury_row=None,
             observed=None):
    """One player's current availability, with the tier that justifies it.

    Order of authority is fixed and does not depend on what would be convenient:
    a captured official list first, then observed participation, then a secondhand
    external designation, then the internal injury feed, then nothing.
    """
    cap = captures.get(club) if captures else None
    if cap is not None:
        inactive = set(cap.get('inactive_gsis', ()))
        if gsis_id and gsis_id in inactive:
            return {
                'status': CONFIRMED_INACTIVE,
                'evidence_tier': TIER_OFFICIAL_CAPTURED,
                'resolution_method': 'NAMED_ON_CAPTURED_OFFICIAL_INACTIVE_LIST',
                'source': cap.get('source_url'),
                'source_timestamp': cap.get('published_at'),
                'retrieval_timestamp': cap.get('retrieved_at'),
                'source_sha256': cap.get('sha256'),
                'authoritative_for_absence': True,
                'note': None,
            }
        return {
            'status': ACTIVE_NOT_ON_INACTIVE_LIST,
            'evidence_tier': TIER_OFFICIAL_CAPTURED,
            'resolution_method': 'ABSENT_FROM_CAPTURED_OFFICIAL_INACTIVE_LIST',
            'source': cap.get('source_url'),
            'source_timestamp': cap.get('published_at'),
            'retrieval_timestamp': cap.get('retrieved_at'),
            'source_sha256': cap.get('sha256'),
            'authoritative_for_absence': False,
            'note': SEMANTICS['NOT_ON_THE_LIST_IS_NOT_CONFIRMED_ACTIVE'],
        }

    if external_claim is not None:
        st = external_claim.get('external_status')
        mapped = {'REPORTED_OUT': REPORTED_OUT_UNVERIFIED,
                  'REPORTED_OUT_IR': REPORTED_OUT_UNVERIFIED,
                  'REPORTED_DOUBTFUL': REPORTED_DOUBTFUL_UNVERIFIED,
                  'QUESTIONABLE': UNKNOWN_ACTIVE_STATE}.get(st, UNKNOWN)
        return {
            'status': mapped,
            'evidence_tier': TIER_EXTERNAL_SECONDHAND,
            'resolution_method': 'EXTERNAL_RESEARCH_CLAIM_VERIFIED_AGAINST_ITS_SOURCE',
            'source': external_claim.get('source'),
            'source_timestamp': external_claim.get('source_timestamp_et'),
            'retrieval_timestamp': external_claim.get('source_timestamp_et'),
            'source_sha256': external_claim.get('source_sha256'),
            'source_quote': external_claim.get('source_quote'),
            'claim_id': external_claim.get('claim_id'),
            'authoritative_for_absence': False,
            'note': SEMANTICS['REPORTED_IS_NOT_CONFIRMED'],
        }

    if injury_row and (injury_row.get('status') or injury_row.get('practice')):
        raw = (injury_row.get('status') or '').strip()
        mapped = {'Out': UNKNOWN_ACTIVE_STATE, 'Doubtful': UNKNOWN_ACTIVE_STATE,
                  'Questionable': UNKNOWN_ACTIVE_STATE}.get(raw, UNKNOWN)
        return {
            'status': mapped,
            'evidence_tier': TIER_INTERNAL_INJURY_FEED,
            'resolution_method': 'INTERNAL_INJURY_FEED_ROW_PRESENT',
            'source': 'nflverse injuries capture',
            'source_timestamp': injury_row.get('observed_at'),
            'retrieval_timestamp': injury_row.get('observed_at'),
            'source_sha256': None,
            'raw_report_status': raw or None,
            'raw_practice_status': injury_row.get('practice') or None,
            'authoritative_for_absence': False,
            'note': ('an injury-report row is a practice/designation record from before '
                     'the game-day list. A row is not a status and a status is not the '
                     'list.'),
        }

    return {
        'status': UNKNOWN,
        'evidence_tier': TIER_NONE,
        'resolution_method': 'NO_EVIDENCE_HELD',
        'source': None, 'source_timestamp': None, 'retrieval_timestamp': None,
        'source_sha256': None,
        'authoritative_for_absence': False,
        'note': SEMANTICS['UNKNOWN_IS_NOT_ZERO'],
    }


# --- the guard ---------------------------------------------------------------
def assert_no_unauthorised_confirmation(rows):
    """Every CONFIRMED_* / ACTIVE_NOT_ON_* status must rest on the required tier.

    Returns an Outcome. `resolve_universe` refuses to return rows on a FAIL, which is
    what makes this load-bearing rather than advisory.
    """
    bad = []
    for key, r in (rows.items() if isinstance(rows, dict) else enumerate(rows)):
        av = r.get('current_availability') if isinstance(r, dict) else None
        if not isinstance(av, dict):
            continue
        st, tier = av.get('status'), av.get('evidence_tier')
        if st not in STATUSES:
            bad.append({'key': key, 'status': st, 'tier': tier,
                        'why': 'STATUS_NOT_IN_DECLARED_SET'})
            continue
        need = STATUS_REQUIRES_TIER.get(st)
        if need and tier not in need:
            bad.append({'key': key, 'status': st, 'tier': tier,
                        'why': f'STATUS_REQUIRES_TIER_IN_{need}'})
    if bad:
        return Outcome.fail(
            'AVAILABILITY_CONFIRMED_WITHOUT_EVIDENCE',
            f'{len(bad)} row(s) claim a confirmed availability state without the '
            f'captured document that state requires. No rows are returned.',
            violations=bad[:40], n_violations=len(bad))
    return Outcome.ok('AVAILABILITY_TIERS_CONSISTENT', len(rows),
                      f'{len(rows)} rows: every confirmed status has its document',
                      n_rows=len(rows))


def captures_for_classify(index_value):
    """Flatten the capture index into the per-club shape `classify` consumes."""
    out = {}
    for game, cap in (index_value.get('found') or {}).items():
        prov = cap.get('provenance') or {}
        for club, gsis in (cap.get('inactive_gsis_by_club') or {}).items():
            out[club] = {
                'inactive_gsis': list(gsis),
                'source_url': prov.get('official_source_url'),
                'published_at': prov.get('official_published_at'),
                'retrieved_at': prov.get('retrieved_at'),
                'sha256': prov.get('delivered_artifact_sha256'),
                'game': game,
            }
    return out


SECOND_PASS = (_REPO / 'nfl/research/external_benchmarks'
               / 'PERPLEXITY_EARLY_2026W3_POST_INACTIVES'
               / 'REPORTED_AVAILABILITY_SECOND_PASS.json')

#: Declared aliases only. A relayed name that is not an exact DK name and not in this
#: table does NOT get matched. Fuzzy matching is how the wrong player gets flagged
#: inactive, and the wrong player flagged inactive silently rewrites a role tree.
NAME_ALIASES = {
    # suffix and capitalisation variants, each verified against the DK 457 by lookup
    ('Michael Pittman', 'PIT'): 'Michael Pittman Jr.',
    ('Kenneth Walker', 'KC'): 'Kenneth Walker III',
    ('James Cook', 'BUF'): 'James Cook III',
    ('KC Concepcion', 'CLE'): 'KC Concepcion Jr.',
    ('Demario Douglas', 'NE'): 'DeMario Douglas',
}

#: Relayed names that could not be resolved and must stay unresolved, with the reason.
UNRESOLVED_RELAYED_NAMES = {
    ('Matthew McClain', 'NYJ'): (
        'no Matthew McClain in the DK 457. The universe carries Malik McClain NYJ WR '
        '3000. Probably a first-name slip, but not established, so not renamed. '
        'IDC-02.'),
}


def second_pass():
    """The relayed second-pass availability evidence, or a refusal."""
    if not SECOND_PASS.exists():
        return Outcome.blocked(
            'SECOND_PASS_EVIDENCE_ABSENT',
            f'{SECOND_PASS.name} is not in the tree, so no reported availability '
            f'exists and every row stays UNKNOWN', cause=Cause.DATA)
    rec = json.loads(SECOND_PASS.read_text())
    need = ('reported_inactive', 'reported_active_not_on_inactive_list',
            'evidence_policy_as_stated_by_the_source', 'COMPLETENESS', 'snapshot_utc')
    missing = [k for k in need if k not in rec]
    if missing:
        return Outcome.fail('SECOND_PASS_SCHEMA',
                            f'second-pass evidence lacks {missing}')
    if not rec['reported_inactive']:
        return Outcome.fail('SECOND_PASS_EMPTY',
                            'reported_inactive is empty; a pass that resolved nothing '
                            'is not a second pass')
    return Outcome.ok('SECOND_PASS_READ', rec,
                      f'{len(rec["reported_inactive"])} reported inactive, '
                      f'{len(rec["reported_active_not_on_inactive_list"])} reported '
                      f'active',
                      n_inactive=len(rec['reported_inactive']),
                      n_active=len(rec['reported_active_not_on_inactive_list']))


_TIER_MAP = {'OFFICIAL_TEAM_RELEASE_CITED': TIER_OFFICIAL_RELEASE_CITED,
             'AGGREGATOR_REPORTED': TIER_AGGREGATOR_REPORTED}


def reported_index(rec, dk_names_by_club):
    """Resolve relayed names onto the DK universe. Returns (index, unmatched).

    `index` is keyed (dk_name, club). `unmatched` records every relayed name that has
    no DK row, with why -- a non-DK-eligible player, or an unresolved identity.
    """
    index, unmatched = {}, []
    groups = (('reported_inactive', 'INACTIVE'),
              ('reported_active_not_on_inactive_list', 'ACTIVE'))
    for field, kind in groups:
        for row in rec.get(field, ()):
            club = row.get('club')
            raw = row.get('player')
            alias = NAME_ALIASES.get((raw, club))
            name = alias or raw
            known = dk_names_by_club.get(club, set())
            if name not in known:
                why = UNRESOLVED_RELAYED_NAMES.get((raw, club))
                unmatched.append({
                    'relayed_name': raw, 'club': club, 'kind': kind,
                    'dk_eligible_per_source': row.get('dk_eligible'),
                    'reason': why or ('not in the DK 457 for this club; treated as a '
                                      'football fact with no DK player row'),
                    'affects': 'team efficiency / DST layer only' if not why
                               else 'nothing until the identity is settled',
                })
                continue
            tier = _TIER_MAP.get(row.get('tier'))
            if tier is None:
                unmatched.append({'relayed_name': raw, 'club': club, 'kind': kind,
                                  'reason': f'undeclared tier {row.get("tier")!r}'})
                continue
            if kind == 'INACTIVE':
                status = (REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED
                          if tier is TIER_OFFICIAL_RELEASE_CITED
                          or tier == TIER_OFFICIAL_RELEASE_CITED
                          else REPORTED_INACTIVE_HIGH_CONFIDENCE)
            else:
                status = REPORTED_ACTIVE_NOT_ON_LIST
            index[(name, club)] = {
                'status': status, 'evidence_tier': tier,
                'resolution_method': ('NAMED_ON_RELAYED_CLUB_RELEASE'
                                      if tier == TIER_OFFICIAL_RELEASE_CITED
                                      else 'NAMED_ON_RELAYED_AGGREGATOR_LIST'),
                'source': row.get('cited_source') or 'rotowire live inactives, relayed',
                'source_timestamp': rec['snapshot_et'],
                'retrieval_timestamp': rec['snapshot_utc'],
                'source_sha256': None,
                'source_quote': row.get('quote'),
                'authoritative_for_absence': False,
                'document_held': False,
                'relayed_name': raw,
                'alias_applied': alias,
                'workload_note': row.get('workload_note'),
                'note': (SEMANTICS['REPORTED_INACTIVE_IS_ACTIONABLE_BUT_NOT_CONFIRMED']
                         if kind == 'INACTIVE'
                         else SEMANTICS['NOT_ON_THE_LIST_IS_NOT_CONFIRMED_ACTIVE']),
            }
    return index, unmatched


def unknown_not_relayed():
    """The state for a DK row the second pass never mentions."""
    return {
        'status': UNKNOWN_NOT_RELAYED,
        'evidence_tier': TIER_NONE,
        'resolution_method': 'NOT_NAMED_IN_ANY_RELAYED_LIST',
        'source': None, 'source_timestamp': None, 'retrieval_timestamp': None,
        'source_sha256': None, 'document_held': False,
        'authoritative_for_absence': False,
        'note': SEMANTICS['NOT_RELAYED_IS_NOT_ACTIVE'],
    }


def main() -> int:
    idx = official_capture_index()
    print(idx)
    if idx.state is State.BLOCKED:
        print(f'\ngames without a capture: {idx.evidence["n_absent"]}')
        for g in idx.evidence['games_absent']:
            print(f'  {g["game"]:10s} expected at {g["expected_at"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
