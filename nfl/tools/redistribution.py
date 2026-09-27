#!/usr/bin/env python3.12
"""Post-inactives role trees: what opportunity is vacated, and who could absorb it.

WHAT THIS DELIBERATELY DOES NOT DO. It never assigns a vacated share to a player. Not
as a point estimate, not as a percentage, not as a "likely" number. Every absence
produces a *candidate set* with a declared ranking basis and an explicit
`UNRESOLVED_DISTRIBUTION`, because the honest answer to "who gets Dowdle's fifteen
carries" is that we do not know, and a number would hide that.

The project has a live example of why. Pittsburgh's observed weeks 1-2 are Warren 21
carries and Dowdle 15 -- a near-split with no incumbent. A one-for-one transfer would
hand Warren a workhorse role that the measured data does not support, and the research
thread independently reached the same conclusion from the other direction ("Do not
assign Warren a guaranteed bell-cow share"). Two sources, one answer: the split is the
finding.

VACATED OPPORTUNITY IS MEASURED. Every number under `vacated` is an observed weeks 1-2
count from play-by-play and snap counts, not a projection. Routes are absent from every
count because `pbp_participation_2026` has 404ed on every probe through
2026-09-27T06:34:57Z; they read UNKNOWN_SOURCE_UNAVAILABLE and are never inferred from
pass snaps.

COMPETING SINKS ARE FIRST-CLASS. A vacated carry can go to another back, to the
quarterback on a designed run or a scramble, or out of the backfield entirely when the
team throws more. A vacated route can go to a receiver, into an extra tight end, or
into fewer three-receiver snaps. Those non-player destinations sit in the tree beside
the player candidates instead of being silently rounded into them.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'redistribution-2026w3-1'

UNRESOLVED = 'UNRESOLVED_DISTRIBUTION'

#: the observed-2026 material-activity snap threshold, same value the PRE state used
ACTIVE_SNAP_PCT = 0.25
ROUTES_UNAVAILABLE = 'UNKNOWN_SOURCE_UNAVAILABLE'

#: Which DK positions can plausibly absorb which vacated work. Stated, not inferred.
ABSORBS = {
    'WR': {'same': ('WR',), 'adjacent': ('TE', 'RB')},
    'TE': {'same': ('TE',), 'adjacent': ('WR', 'RB')},
    'RB': {'same': ('RB',), 'adjacent': ('QB', 'WR', 'TE')},
    'QB': {'same': ('QB',), 'adjacent': ()},
}

#: Non-player destinations for vacated work, by the vacating position.
COMPETING_SINKS = {
    'WR': (
        'heavier personnel -- fewer three-receiver snaps, more tight end or extra '
        'lineman, so some routes leave the receiver room entirely',
        'run rate -- a thinner receiver group can shift pass/run tendency rather than '
        'redistribute routes',
        'team pass efficiency -- targets can be reallocated while yards per target '
        'falls, so target count and production move apart'),
    'TE': (
        'blocking packages -- a blocking tight end\'s snaps can go to a sixth lineman '
        'or a fullback and produce no receiving opportunity at all',
        'three-receiver personnel -- the snaps can leave the tight end room upward '
        'into an extra receiver'),
    'RB': (
        'quarterback rushing -- designed runs and scrambles absorb carries without any '
        'back gaining them',
        'pass rate -- a thinner backfield can mean more dropbacks instead of more '
        'carries for the remaining backs',
        'goal-line personnel -- short-yardage carries can go to a quarterback, a '
        'fullback or a tight end rather than to the nominal backup'),
    'QB': (
        'designed-run share is quarterback-specific and does not transfer: a new '
        'starter\'s rushing profile is his own, not the absent starter\'s',
        'team pass efficiency, sack rate and turnover distribution all move together '
        'with a quarterback change and none of them is a receiver-level reallocation'),
}

MEASURED = ('offense_snaps', 'carries', 'targets', 'rz_opportunities',
            'gl_opportunities', 'air_yards', 'receptions', 'rushing_yards',
            'receiving_yards')


UNKNOWN_NO_ROW = 'UNKNOWN_NO_OBSERVED_ROW'


def _obs(row):
    """Observed weeks 1-2, keeping a real zero and an absent row apart.

    Three states, and collapsing any two of them is the defect this project keeps
    paying for:

      * the player has an observed row and a count key -> the measured number
      * the player has an observed row and NO count key -> a real OBSERVED ZERO. The
        observed layer builds `combined` from plays that happened, so a receiver with
        no `carries` key carried the ball zero times. That is football, not a gap.
      * the player has NO observed row at all -> UNKNOWN_NO_OBSERVED_ROW. Darius
        Slayton is the live case: empty `combined`, empty `weeks`. Rendering him as
        zero vacated opportunity would say Indianapolis loses nothing by his absence,
        which is a claim about football made out of a missing file.

    `gl_opportunities` is never present in `combined` -- the observed layer carries it
    per week only -- so it is summed here rather than read as absent.
    """
    obs = row.get('observed_2026') or {}
    combined = obs.get('combined') or {}
    weeks = obs.get('weeks') or {}
    if not combined and not weeks:
        out = {k: UNKNOWN_NO_ROW for k in MEASURED}
        out.update({k: UNKNOWN_NO_ROW for k in
                    ('mean_offense_pct', 'rush_share', 'target_share')})
        out['n_weeks_observed'] = 0
        out['observed_state'] = UNKNOWN_NO_ROW
        out['routes'] = out['route_participation'] = ROUTES_UNAVAILABLE
        return out
    gl = sum((w.get('gl_opportunities') or 0) for w in weeks.values())
    out = {k: (combined.get(k) if combined.get(k) is not None else 0.0)
           for k in MEASURED}
    out['gl_opportunities'] = gl
    out.update({k: combined.get(k) for k in
                ('mean_offense_pct', 'rush_share', 'target_share')})
    out['n_weeks_observed'] = combined.get('n_weeks_observed') or len(weeks)
    out['observed_state'] = 'OBSERVED'
    out['routes'] = out['route_participation'] = ROUTES_UNAVAILABLE
    return out


def _num(v):
    """A count for ordering only. The UNKNOWN sentinel sorts last and stays UNKNOWN
    everywhere it is reported; this never converts it to a displayed zero."""
    return v if isinstance(v, (int, float)) else 0.0


def _rank_key(row):
    """Declared ranking basis: observed snap share, then observed target share.

    This orders candidates by how much football they were measurably doing. It is NOT a
    share of the vacancy and must never be read as one.
    """
    o = (row.get('observed_2026') or {}).get('combined') or {}
    return (-_num(o.get('mean_offense_pct')), -_num(o.get('target_share')),
            -_num(o.get('carries')), row.get('name') or '')


RANK_BASIS = ('observed 2026 weeks 1-2 mean offensive snap share, then observed target '
              'share, then observed carries. An ordering of how much football each '
              'candidate was measurably doing before today. NOT a share of the '
              'vacancy and not a probability.')


def _source_beneficiaries(rec):
    """Beneficiaries the research named, kept apart from our own ranking."""
    out = {}
    for row in rec.get('reported_inactive', ()):
        named = []
        for k in ('route_increase_candidates', 'target_concentration_candidates',
                  'predicted_replacement', 'predicted_replacements',
                  'primary_beneficiary'):
            v = row.get(k)
            if isinstance(v, str):
                named.append(v)
            elif isinstance(v, (list, tuple)):
                named.extend(v)
        out[(row['player'], row['club'])] = named
    return out


#: Beneficiaries the second pass names in prose, per club. Recorded as the source's
#: claim so it can be compared against our measured ranking and disagree visibly.
SOURCE_NAMED = {
    ('Nico Collins', 'HOU'): ['Xavier Hutchinson', 'Kayshon Boutte', 'Jaylin Noel',
                              'Dalton Schultz', 'Jared Wayne'],
    ('Xavier Legette', 'CAR'): ['Brycen Tremayne', 'Tetairoa McMillan', 'Jalen Coker',
                                'Tommy Tremble', 'Darren Waller'],
    ('Darius Slayton', 'IND'): ['Josh Downs', 'Keenan Allen', 'Tyler Warren',
                                'Laquon Treadwell'],
    ('Ashton Dulin', 'IND'): ['Josh Downs', 'Keenan Allen', 'Tyler Warren',
                              'Laquon Treadwell'],
    ('Alec Pierce', 'IND'): ['Josh Downs', 'Keenan Allen', 'Tyler Warren',
                             'Laquon Treadwell'],
    ('Rico Dowdle', 'PIT'): ['Jaylen Warren'],
    ('Jaylen Wright', 'MIA'): ["De'Von Achane", 'Malik Willis', 'Ollie Gordon II'],
    ('Adonai Mitchell', 'NYJ'): ['Isaiah Williams', 'Malik McClain', 'Garrett Wilson',
                                 'Kenyon Sadiq'],
    ('Mason Taylor', 'NYJ'): ['Kenyon Sadiq'],
    ('Eli Raridon', 'NE'): ['Hunter Henry'],
    ('Devin Singletary', 'NYG'): ['Cam Skattebo'],
    ('Jayden Daniels', 'WAS'): ['Marcus Mariota', 'Terry McLaurin', 'Stefon Diggs',
                                'Jacory Croskey-Merritt', 'Ben Sinnott'],
    ('Chig Okonkwo', 'WAS'): ['Ben Sinnott'],
}

TEN_QUESTIONS = (
    'what_observed_opportunity_disappears',
    'who_gains_snap_probability',
    'who_gains_carry_probability',
    'who_gains_target_probability',
    'who_gains_redzone_or_goalline_probability',
    'does_personnel_usage_plausibly_change',
    'does_qb_or_team_efficiency_change',
    'does_pass_run_tendency_plausibly_change',
    'are_newly_relevant_depth_players_in_the_dk_universe',
    'does_dst_expectation_materially_change',
)


def build(players, reported_index, rec):
    """One tree per absent DK player. `players` is the PRE artifact's player map."""
    by_club = {}
    for row in players.values():
        by_club.setdefault(row['team'], []).append(row)

    absent = []
    for (name, club), av in reported_index.items():
        if av['status'] in AV.ABSENT_STATUSES:
            absent.append((name, club, av))

    trees = {}
    for name, club, av in sorted(absent, key=lambda t: (t[1], t[0])):
        row = next((r for r in by_club.get(club, ()) if r['name'] == name), None)
        if row is None:
            continue
        pos = row['position']
        vac = _obs(row)
        rules = ABSORBS.get(pos, {'same': (pos,), 'adjacent': ()})
        same, adj = [], []
        for cand in by_club.get(club, ()):
            if cand['name'] == name or cand['position'] == 'DST':
                continue
            cav = reported_index.get((cand['name'], club))
            if cav and cav['status'] in AV.ABSENT_STATUSES:
                continue  # an absent player cannot inherit
            entry = {
                'name': cand['name'], 'dk_id': cand['dk_id'],
                'position': cand['position'], 'salary': cand['salary'],
                'observed_2026': _obs(cand),
                'availability': (cav or AV.unknown_not_relayed())['status'],
                'availability_tier': (cav or AV.unknown_not_relayed())['evidence_tier'],
                'named_by_source': cand['name'] in SOURCE_NAMED.get((name, club), ()),
                'historical_role_class': cand.get('historical_role_class'),
                'historical_role_valid_for_current_role':
                    cand.get('historical_role_class_valid_for_current_role'),
            }
            (same if cand['position'] in rules['same'] else adj).append((cand, entry))
        same = [e for _, e in sorted(same, key=lambda t: _rank_key(t[0]))]
        adj = [e for _, e in sorted(adj, key=lambda t: _rank_key(t[0]))
               if e['position'] in rules['adjacent']]

        named = list(SOURCE_NAMED.get((name, club), ()))
        in_dk = {c['name'] for c in same + adj}
        named_missing = [n for n in named if n not in in_dk]

        # NEWLY RELEVANT means plausibly in line for this specific vacancy, not merely
        # low-usage. A first cut that only tested "snap share under 0.35" returned 128
        # names across the slate -- effectively every deep reserve on any club with an
        # absence -- which is not a finding, it is a roster. Two ways in, both narrow:
        # the source names him as a beneficiary, or he is top-3 in the vacating
        # position group once the absent player is removed while having been a
        # bit-part player. A depth player who is fourth or lower in his own group has
        # not become relevant because someone ahead of two others sat down.
        cand = [(i, c) for i, c in enumerate(same)] + [(99, c) for c in adj]
        shortlist = [c for i, c in cand
                     if c['named_by_source']
                     or (i < 3
                         and _num(c['observed_2026'].get('mean_offense_pct')) < 0.35)]
        # Two different football things, and lumping them cost a pass. A receiver who
        # already played 78% of snaps does not become "newly relevant" when a teammate
        # sits -- he gains CONCENTRATION. A reserve at 15% who is now third in the room
        # becomes NEWLY RELEVANT. Both matter; they matter in opposite directions for a
        # lineup, because one is a known quantity at a known price and the other is a
        # role that may not exist.
        newly = [c for c in shortlist
                 if _num(c['observed_2026'].get('mean_offense_pct')) < ACTIVE_SNAP_PCT]
        gainers = [c for c in shortlist
                   if _num(c['observed_2026'].get('mean_offense_pct'))
                   >= ACTIVE_SNAP_PCT]

        trees[f'{club}:{name}'] = {
            'player': name, 'club': club, 'dk_id': row['dk_id'], 'position': pos,
            'salary': row['salary'],
            'availability': av,
            'vacated': vac,
            'VACATED_IS_MEASURED': (
                'every count above is an observed weeks 1-2 total from play-by-play '
                'and snap counts. It is what this player DID, not what he was '
                'projected to do today, and it is the only quantity in this tree that '
                'is a number rather than an ordering.'),
            'inheritance': UNRESOLVED,
            'INHERITANCE_IS_UNRESOLVED': (
                'no share of the vacated work is assigned to any candidate. The '
                'candidates are ranked, the competing sinks are listed, and the '
                'distribution across them is not established by held evidence.'),
            'rank_basis': RANK_BASIS,
            'candidates_same_position_group': same,
            'candidates_adjacent_position_group': adj,
            'competing_non_player_sinks': list(COMPETING_SINKS.get(pos, ())),
            'source_named_beneficiaries': named,
            'source_named_but_not_in_dk_universe': named_missing,
            'newly_relevant_candidates': [c['name'] for c in newly],
            'concentration_gainer_candidates': [c['name'] for c in gainers],
            'NEWLY_RELEVANT_VS_CONCENTRATION': (
                'newly_relevant is a reserve below the material-activity snap threshold '
                'who is now plausibly in line: a role that may not exist. '
                'concentration_gainer is an established contributor above it whose '
                'existing role may get denser. Neither is an assigned share.'),
            'ten_questions': _answer_ten(row, pos, vac, same, adj, club, name),
        }
    return trees


def _answer_ten(row, pos, vac, same, adj, club, name):
    """The ten Phase-4 questions. Each answer is measured, ranked, or UNRESOLVED."""
    def names(lst, n=5):
        return [c['name'] for c in lst[:n]]

    unknown_row = vac.get('observed_state') == UNKNOWN_NO_ROW
    rz, gl = _num(vac.get('rz_opportunities')), _num(vac.get('gl_opportunities'))
    car, tgt = _num(vac.get('carries')), _num(vac.get('targets'))
    snaps = _num(vac.get('offense_snaps'))
    return {
        'what_observed_opportunity_disappears': (
            {'measured': UNKNOWN_NO_ROW,
             'basis': 'no observed 2026 row in play-by-play or snap counts',
             'why_this_is_not_zero': (
                 'an absent row means we did not observe him, not that he did '
                 'nothing. Reporting zero vacated opportunity here would assert that '
                 'his club loses nothing by his absence, which is a football claim '
                 'built out of a missing file.'),
             'what_would_resolve_it': (
                 'a weeks 1-2 snap or play-by-play row under this identity, or the '
                 'club depth chart establishing the role he held')}
            if unknown_row else
            {'measured': {'offense_snaps': snaps, 'carries': car, 'targets': tgt,
                          'rz_opportunities': rz, 'gl_opportunities': gl,
                          'air_yards': vac.get('air_yards'),
                          'routes': ROUTES_UNAVAILABLE},
             'basis': 'observed 2026 weeks 1-2'}),
        'who_gains_snap_probability': {
            'ranked_candidates': names(same) + names(adj, 3),
            'assignment': UNRESOLVED,
            'note': 'snap access is the part of a vacancy that transfers most reliably; '
                    'target and carry share are much less certain than snap share.'},
        'who_gains_carry_probability': (
            {'ranked_candidates': names([c for c in same + adj
                                         if c['position'] in ('RB', 'QB')]),
             'assignment': UNRESOLVED,
             'competing_sink': 'quarterback designed runs and scrambles'}
            if car > 0 and not unknown_row else
            {'unresolved': UNKNOWN_NO_ROW,
             'detail': f'{name} has no observed 2026 row, so vacated carry volume is '
                       f'unknown rather than zero'} if unknown_row else
            {'not_applicable': f'{name} recorded {car:.0f} observed carries, so no '
                               f'carry volume is vacated'}),
        'who_gains_target_probability': (
            {'ranked_candidates': names([c for c in same + adj
                                         if c['position'] in ('WR', 'TE', 'RB')]),
             'assignment': UNRESOLVED,
             'note': 'routes are unavailable, so this ranks measured target volume '
                     'rather than route participation. An increase in routes does not '
                     'establish a proportional increase in targets.'}
            if tgt > 0 and not unknown_row else
            {'unresolved': UNKNOWN_NO_ROW,
             'detail': f'{name} has no observed 2026 row, so vacated target volume is '
                       f'unknown rather than zero'} if unknown_row else
            {'not_applicable': f'{name} recorded {tgt:.0f} observed targets'}),
        'who_gains_redzone_or_goalline_probability': (
            {'vacated_rz_opportunities': rz, 'vacated_gl_opportunities': gl,
             'ranked_candidates': names(same + adj, 4),
             'assignment': UNRESOLVED,
             'note': 'red-zone and goal-line work is the least transferable opportunity '
                     'in football: it is personnel-specific and a quarterback, '
                     'fullback or tight end can take it out of the position group '
                     'entirely.'}
            if (rz or gl) and not unknown_row else
            {'unresolved': UNKNOWN_NO_ROW,
             'detail': f'{name} has no observed 2026 row'} if unknown_row else
            {'not_applicable': f'{name} recorded {rz:.0f} red-zone and {gl:.0f} '
                               f'goal-line opportunities, so none is vacated'}),
        'does_personnel_usage_plausibly_change': {
            'answer': 'PLAUSIBLE_NOT_ESTABLISHED',
            'mechanisms': list(COMPETING_SINKS.get(pos, ())),
            'why_not_established': 'personnel rate requires participation data, which '
                                   'is unavailable for 2026.'},
        'does_qb_or_team_efficiency_change': {
            'answer': ('YES_BY_CONSTRUCTION' if pos == 'QB'
                       else 'PLAUSIBLE_NOT_ESTABLISHED'),
            'note': ('a quarterback change moves pass efficiency, designed rushing, '
                     'sack rate and turnover distribution together, and none of those '
                     'is a reallocation between receivers.' if pos == 'QB' else
                     'losing a primary contributor can lower yards per opportunity '
                     'while target counts are preserved. Reallocating volume without '
                     'an efficiency penalty would assume the replacement is as good, '
                     'which is not evidence.')},
        'does_pass_run_tendency_plausibly_change': {
            'answer': 'PLAUSIBLE_NOT_ESTABLISHED',
            'note': 'two games is not a stable tendency, and today\'s market moved, so '
                    'script is a wider distribution rather than a point.'},
        'are_newly_relevant_depth_players_in_the_dk_universe': {
            'answer': True,
            'candidates_with_low_observed_usage': [
                c['name'] for c in same + adj
                if _num(c['observed_2026'].get('mean_offense_pct')) < 0.35],
            'note': 'a depth player being in the DK pool is eligibility, not a role.'},
        'does_dst_expectation_materially_change': {
            'answer': ('PLAUSIBLE_NOT_ESTABLISHED' if pos == 'QB'
                       else 'NOT_ESTABLISHED'),
            'note': ('a quarterback change moves the opposing pass-rush and turnover '
                     'distribution, which is a DST input.' if pos == 'QB' else
                     'a skill-position absence changes opposing DST expectation only '
                     'through team efficiency, which held evidence does not quantify.')},
    }


def run():
    pre = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE.json'
    if not pre.exists():
        return Outcome.fail('PRE_STATE_ABSENT', 'the PRE artifact is not in the tree')
    players = json.loads(pre.read_text())['players']
    sp = AV.second_pass()
    if sp.state is not State.PASS:
        return sp
    by_club = {}
    for v in players.values():
        by_club.setdefault(v['team'], set()).add(v['name'])
    idx, unmatched = AV.reported_index(sp.value, by_club)
    trees = build(players, idx, sp.value)
    if not trees:
        return Outcome.fail('NO_TREES_BUILT',
                            'no absent DK player produced a tree; an absence list that '
                            'yields no redistribution record is a defect, not a result')
    return Outcome.ok('REDISTRIBUTION_BUILT',
                      {'trees': trees, 'unmatched': unmatched, 'reported_index': idx},
                      f'{len(trees)} trees', n_trees=len(trees))


def main() -> int:
    r = run()
    print(r)
    if r.state is not State.PASS:
        return 1
    for key, t in r.value['trees'].items():
        v = t['vacated']
        print(f'\n{key}  {t["position"]}  ${t["salary"]}  [{t["availability"]["status"]}]')
        if v.get('observed_state') == UNKNOWN_NO_ROW:
            print(f'  vacated: {UNKNOWN_NO_ROW} -- not zero')
        else:
            print(f'  vacated: {v["offense_snaps"]:.0f} snaps, {v["carries"]:.0f} car, '
                  f'{v["targets"]:.0f} tgt, rz {v["rz_opportunities"]:.0f}, gl '
                  f'{v["gl_opportunities"]:.0f}, routes {v["routes"]}')
        print(f'  same-group ranked: '
              f'{[c["name"] for c in t["candidates_same_position_group"][:4]]}')
        print(f'  adjacent ranked:   '
              f'{[c["name"] for c in t["candidates_adjacent_position_group"][:3]]}')
        print(f'  inheritance: {t["inheritance"]}   '
              f'source-named missing from DK: {t["source_named_but_not_in_dk_universe"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
