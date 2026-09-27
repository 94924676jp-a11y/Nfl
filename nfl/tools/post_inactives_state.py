#!/usr/bin/env python3.12
"""Build DK_WEEK3_TODAY_STATE_POST_INACTIVES from the PRE state plus relayed evidence.

THE PRE ARTIFACT IS OPENED READ-ONLY AND NEVER WRITTEN. It is the before-image for the
semantic comparator, and a before-image that can be edited is not a before-image. Its
digest is recorded in the POST artifact so `state_compare.assert_pre_artifact_unchanged`
can refuse if the bytes ever move.

WHAT THE NAME OF THIS FILE DOES AND DOES NOT CLAIM. It says POST_INACTIVES because a
post-inactives pass has happened: fifteen absences and eight availabilities are now
named, which is a different football world from the one the PRE state describes. It does
NOT claim that an official game-day inactive list has been captured. None has. No player
in it carries CONFIRMED_INACTIVE, the state label says so, and OUT-035 has the request.

THE COMPLETENESS PROBLEM, STATED WHERE IT CANNOT BE MISSED. The source says all nine
lists are populated and relays the names that matter. It never enumerates a list in
full. So 23 of 457 rows resolve and the rest stay UNKNOWN_NOT_RELAYED. Reading "not
mentioned" as "not on the list" would activate roughly 420 players on silence, which is
the same defect as reading missing as zero, and it is the single biggest thing still
missing today.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import external_research as EX  # noqa: E402
from nfl.tools import redistribution as RD  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'dk-post-inactives-state-1'
STATE_LABEL = 'POST_REPORTED_INACTIVES / NO_OFFICIAL_DOCUMENT_CAPTURED'

PRE = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE.json'
OUT_JSON = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
OUT_MD = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.md'
ENTRIES = _REPO / 'nfl/dfs/salaries/raw/DKEntries_EARLY_ONLY_2026W3_62.csv'

CARRY = (
    'dk_id', 'name', 'team', 'opponent', 'position', 'salary', 'gsis_id', 'identity',
    'coverage_state', 'historical_role_class', 'historical_role_rank',
    'historical_role_rank_basis', 'historical_trail_snap', 'historical_own_share',
    'historical_participation_ewma', 'historical_target_freq',
    'historical_prior_depth_bucket', 'historical_provenance',
    'historical_role_class_valid_for_current_role', 'historical_role_class_warning',
    'observed_2026', 'materially_active_2026', 'materially_active_2026_evidence',
    'depth_source', 'depth_vintage', 'depth_rank', 'depth_source_caveat',
    'injury_row_present', 'injury_row_status', 'injury_row_practice',
    'external_fc_context', 'qb_layer_pre_r2_context',
)

ROLE_NOT_PLAYING = 'NOT_PLAYING_REPORTED'
ROLE_PREDICTED_STARTER = 'PREDICTED_STARTER_NOT_CONFIRMED'
ROLE_UNKNOWN = 'UNKNOWN_CURRENT_STATE'


def _digest(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _predicted_index(rec, dk_names_by_club):
    idx, unresolved = {}, []
    block = rec.get('rotowire_predicted_lineups') or {}
    for club, names in (block.get('clubs') or {}).items():
        for raw in names:
            name = AV.NAME_ALIASES.get((raw, club), raw)
            if name in dk_names_by_club.get(club, set()):
                idx[(name, club)] = {'relayed_name': raw,
                                     'alias_applied': (name if name != raw else None)}
            else:
                unresolved.append({
                    'club': club, 'relayed_name': raw,
                    'reason': AV.UNRESOLVED_RELAYED_NAMES.get(
                        (raw, club), 'no DK row under this name for this club'),
                })
    return idx, unresolved


def build():
    if not PRE.exists():
        return Outcome.fail('PRE_STATE_ABSENT', 'the PRE artifact is not in the tree')
    pre = json.loads(PRE.read_text())
    pre_digest = _digest(PRE)

    sp = AV.second_pass()
    if sp.state is not State.PASS:
        return sp
    rec = sp.value

    players_pre = pre['players']
    by_club_names = {}
    for v in players_pre.values():
        by_club_names.setdefault(v['team'], set()).add(v['name'])

    reported, unmatched = AV.reported_index(rec, by_club_names)
    predicted, predicted_unresolved = _predicted_index(rec, by_club_names)
    trees = RD.build(players_pre, reported, rec)

    # which trees does each player appear in, and in what capacity
    appears = {}
    for key, t in trees.items():
        for grp, label in (('candidates_same_position_group', 'SAME_POSITION_GROUP'),
                           ('candidates_adjacent_position_group', 'ADJACENT_GROUP')):
            for c in t[grp]:
                appears.setdefault((c['name'], t['club']), []).append({
                    'vacancy': key, 'as': label,
                    'rank_within_group': t[grp].index(c) + 1,
                    'named_by_source': c['named_by_source'],
                    'inheritance': t['inheritance'],
                })

    capture = AV.official_capture_index()
    players = {}
    for dk_id, row in players_pre.items():
        club, name = row['team'], row['name']
        out = {k: row.get(k) for k in CARRY}
        av = reported.get((name, club)) or AV.unknown_not_relayed()
        out['current_availability'] = av
        out['current_availability_provenance'] = {
            'evidence_tier': av['evidence_tier'],
            'document_held': av.get('document_held', False),
            'source': av.get('source'),
            'source_timestamp': av.get('source_timestamp'),
            'retrieval_timestamp': av.get('retrieval_timestamp'),
            'resolution_method': av['resolution_method'],
            'source_quote': av.get('source_quote'),
            'note': av.get('note'),
        }
        pred = predicted.get((name, club))
        out['predicted_lineup_context'] = (
            {'state': 'ROTOWIRE_PREDICTED', 'in_predicted_starting_group': True,
             'relayed_name': pred['relayed_name'],
             'alias_applied': pred['alias_applied'],
             'NOT_A_CONFIRMED_STARTER': (
                 'named in a predicted lineup. That is a projection of who starts, not '
                 'a declaration, and it confers no availability status.')}
            if pred else
            {'state': 'ROTOWIRE_PREDICTED', 'in_predicted_starting_group': False,
             'NOT_A_CLAIM': ('absence from a six-man predicted group is not a claim '
                             'about this player. Most of a 53-man roster is not in it.')})

        if av['status'] in AV.ABSENT_STATUSES:
            out['today_expected_role'] = ROLE_NOT_PLAYING
            out['role_confidence'] = ('REPORTED_HIGH_CONFIDENCE'
                                      if av['evidence_tier'] == AV.TIER_AGGREGATOR_REPORTED
                                      else 'OFFICIAL_RELEASE_CITED')
        elif pred and av['status'] in AV.PRESENT_STATUSES:
            out['today_expected_role'] = ROLE_PREDICTED_STARTER
            out['role_confidence'] = 'PREDICTED_PLUS_REPORTED_AVAILABLE'
        elif pred:
            out['today_expected_role'] = ROLE_PREDICTED_STARTER
            out['role_confidence'] = 'PREDICTED_ONLY_AVAILABILITY_UNRESOLVED'
        else:
            out['today_expected_role'] = ROLE_UNKNOWN
            out['role_confidence'] = 'NOT_ESTABLISHED_FROM_HELD_EVIDENCE'
        out['today_expected_role_note'] = (
            'role state is built from a reported availability plus a RotoWire predicted '
            'lineup. Neither is an official starting declaration, so no row here says '
            'CONFIRMED anything. Historical role labels are not promoted into it -- the '
            'observed 2026 layer showed them stale for a number of active players.')
        out['today_role_evidence'] = {
            'dk_roster_position': row['position'],
            'in_rotowire_predicted_group': bool(pred),
            'availability_status': av['status'],
            'availability_tier': av['evidence_tier'],
            'observed_2026_snap_share':
                ((row.get('observed_2026') or {}).get('combined') or {})
                .get('mean_offense_pct'),
            'observed_2026_target_share':
                ((row.get('observed_2026') or {}).get('combined') or {})
                .get('target_share'),
            'historical_role_class': row.get('historical_role_class'),
            'historical_role_valid_for_current_role':
                row.get('historical_role_class_valid_for_current_role'),
        }
        out['workload_limitation'] = (
            {'reported': True, 'detail': av['workload_note'],
             'SEPARATE_FROM_AVAILABILITY': (
                 'a workload limitation is not an availability state. This player is '
                 'reported available and separately reported limited; the two fields '
                 'never collapse into one.')}
            if av.get('workload_note') else
            {'reported': False, 'detail': None})
        out['conditional_opportunity_redistribution'] = appears.get((name, club), [])
        out['is_vacancy_owner'] = f'{club}:{name}' in trees
        out['unknown_fields'] = [
            f for f, v in (('routes', 'UNKNOWN_SOURCE_UNAVAILABLE'),
                           ('route_participation', 'UNKNOWN_SOURCE_UNAVAILABLE'))
            if v] + ([] if av['status'] not in (AV.UNKNOWN_NOT_RELAYED, AV.UNKNOWN)
                     else ['current_availability'])
        out['data_quality_warnings'] = list(row.get('data_quality_warnings') or [])
        if ((row.get('observed_2026') or {}).get('combined') or {}) == {} and \
                not ((row.get('observed_2026') or {}).get('weeks') or {}):
            out['data_quality_warnings'].append(
                'NO_OBSERVED_2026_ROW: absent from both play-by-play and snap counts '
                'for weeks 1-2. That is UNKNOWN, never zero.')
        players[dk_id] = out

    n_by_status = {}
    for v in players.values():
        n_by_status[v['current_availability']['status']] = \
            n_by_status.get(v['current_availability']['status'], 0) + 1

    newly = sorted({c for t in trees.values() for c in t['newly_relevant_candidates']})
    gainers = sorted({c for t in trees.values()
                      for c in t['concentration_gainer_candidates']})
    art = {
        'artifact': 'DK_WEEK3_TODAY_STATE_POST_INACTIVES',
        'state_label': STATE_LABEL,
        'spec_version': SPEC_VERSION,
        'generated_at_utc': dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'season': 2026, 'week': 3,
        'slate': pre.get('slate'),
        'WHAT_THIS_IS': (
            'the football state after a post-inactives research pass, snapshot '
            '2026-09-27 12:04 ET. Fifteen absences and eight availabilities are named '
            'and each carries the sentence and the URL it came from.'),
        'WHAT_THIS_IS_NOT': (
            'a capture of any official game-day inactive list. Zero bytes of any NFL or '
            'club release for 2026-09-27 are held in this repository, so NO player '
            'carries CONFIRMED_INACTIVE or CONFIRMED_ACTIVE. The source asked for '
            'exactly this distinction: everything from RotoWire stays '
            'REPORTED_HIGH_CONFIDENCE rather than CONFIRMED_OFFICIAL until matched to '
            'an NFL or team release.'),
        'COMPLETENESS': rec['COMPLETENESS'],
        'official_capture_state': capture.as_dict(),
        'evidence_policy': rec['evidence_policy_as_stated_by_the_source'],
        'availability_counts': n_by_status,
        'availability_tiers': {t: sum(
            1 for v in players.values()
            if v['current_availability']['evidence_tier'] == t) for t in AV.TIERS},
        'availability_semantics': AV.SEMANTICS,
        'ROUTES_UNAVAILABLE': (
            'pbp_participation_2026 has returned 404 on every probe through '
            '2026-09-27T06:34:57Z, so routes and route participation read '
            'UNKNOWN_SOURCE_UNAVAILABLE for every player and are never inferred from '
            'pass snaps.'),
        'OBSERVED_2026_CORRECTION_PRESERVED': {
            'finding': (
                'historical role labels are stale for a number of players who were '
                'materially active in weeks 1-2. 19 of 53 FEATURES_NO_PRIOR_HISTORY '
                'players cleared the material-activity thresholds, so their historical '
                '"fringe" classification is not valid for their current role.'),
            'named_examples': ['Carnell Tate', 'Denzel Boston', 'Caleb Douglas',
                               'Malachi Fields', 'KC Concepcion Jr.', 'Jadarian Price'],
            'consequence': (
                'current opportunity is described from observed 2026 usage, never from '
                'a historical role label. Every row carries '
                'historical_role_class_valid_for_current_role so the two cannot be '
                'confused.'),
            'not_altered': 'Q9 itself is untouched by this artifact.'},
        'upstream_artifacts': {
            'pre_inactives_state': {
                'path': str(PRE.relative_to(_REPO)), 'sha256': pre_digest,
                'state_label': pre.get('state_label'),
                'role': 'BEFORE_IMAGE_READ_ONLY_NEVER_WRITTEN'},
            'second_pass_evidence': {
                'path': str(AV.SECOND_PASS.relative_to(_REPO)),
                'sha256': _digest(AV.SECOND_PASS)},
            'first_pass_research': EX.provenance(),
            'dk_entries': ({'path': str(ENTRIES.relative_to(_REPO)),
                            'sha256': _digest(ENTRIES)} if ENTRIES.exists() else None),
        },
        'identity_conflicts': rec['identity_conflicts'],
        'relayed_names_not_in_dk_universe': unmatched,
        'predicted_lineup_names_unresolved': predicted_unresolved,
        'redistribution': trees,
        'newly_relevant_players': newly,
        'concentration_gainers': gainers,
        'NEWLY_RELEVANT_VS_CONCENTRATION': (
            'newly_relevant_players are reserves below the 0.25 observed snap threshold '
            'who are now plausibly in line -- a role that may not exist at all. '
            'concentration_gainers are established contributors whose existing role may '
            'get denser. A first cut lumped them and returned 128 names, which is a '
            'roster rather than a finding.'),
        'environment': rec['environment_second_pass'],
        'hard_stops': rec['hard_stops_restated_by_the_source'],
        'proprietary_projection_board': {
            'exists': False,
            'code': 'STAGE_DECLARED_UNIMPLEMENTED',
            'detail': (
                'feature_build is DEFERRED and does not halt the pipeline; player_draws '
                'then FAILs DECLARED_DRAW_ARTIFACT_INCOMPLETE because the receiving and '
                'rushing layers are CONTRACT_DECLARED_LAYER_ABSENT, which traces to '
                'participation_prior BLOCKED PARTICIPATION_HISTORY_STALE, which traces '
                'to pbp_participation_2026 404. No projection is produced here and none '
                'is simulated.'),
            'not_bypassed': True},
        'players': players,
    }
    return Outcome.ok('POST_STATE_BUILT', art,
                      f'{len(players)} players, {len(trees)} trees',
                      n_players=len(players), n_trees=len(trees),
                      counts=n_by_status)


def main() -> int:
    r = build()
    print(r)
    if r.state is not State.PASS:
        return 1
    OUT_JSON.write_text(json.dumps(r.value, indent=2, sort_keys=False) + '\n')
    print(f'wrote {OUT_JSON.relative_to(_REPO)}')
    for k, v in sorted(r.value['availability_counts'].items(), key=lambda kv: -kv[1]):
        print(f'  {k:44s} {v:4d}')
    print('\nnewly relevant (reserve, role may not exist):')
    print('  ', r.value['newly_relevant_players'])
    print('concentration gainers (established, role may get denser):')
    print('  ', r.value['concentration_gainers'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
