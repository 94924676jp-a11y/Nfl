#!/usr/bin/env python3.12
"""Current role state, CONSUMED by the projection rather than merely recorded beside it.

THE DEFECT THIS EXISTS TO PREVENT. V0 projected Drew Lock at 17.88 DK points because he held
95% of Seattle's snaps in weeks 1-2 -- snaps he held only because Sam Darnold was injured.
Darnold is reported available again. The role field existed and said Lock was a backup; nothing
read it. `today_expected_role` was descriptive.

So this module answers one question with authority: WHAT ROLE BAND MAY THE PRIOR BE ASKED
ABOUT FOR THIS PLAYER TODAY. The prior is good at answering "what does an alpha receiver who
is Ja'Marr Chase look like". It has no opinion on whether today's question should be asked, and
asked about a starter role Lock returns a near-starter share at LOW confidence. The fix is to
never ask.

THE CAP IS THE MECHANISM. A player who is not his club's starter at his position CANNOT be
asked about ALPHA or PRIMARY, whatever his own history says. That is a hard ceiling, applied
before the prior is consulted, and it is what makes an injury-replacement share expire when the
starter returns.

THE CIRCULARITY THIS AVOIDS, CAUGHT ON THE FIRST RUN. A first version set the role band from
observed 2026 usage and then used that band to query the prior. Ja'Marr Chase came back
PRIMARY rather than ALPHA and Sam Darnold came back ROTATIONAL despite being his club's
predicted starting quarterback -- because a two-game sample decided the role, and the role then
decided which slice of history the prior was allowed to see. Two quiet games therefore
downgraded the role, which downgraded the prior, which is V0's defect in a new place.

The band is now the STRONGER of what a player has historically been and what he is currently
doing, capped by what current evidence permits. History says who he is; current evidence says
what he is allowed to be today. Neither alone is right: history alone keeps a demoted starter
at alpha, and current usage alone demotes a star having a slow fortnight.

EVIDENCE ORDER, strongest first, and the source of the decision is recorded:
    1  reported absent            -> NOT_PLAYING, no projection at all
    2  predicted starting group   -> may be asked about ALPHA/PRIMARY
    3  held depth chart rank      -> capped by rank
    4  observed 2026 usage        -> capped, and only where the starter above him is absent
    5  nothing                    -> FRINGE, and flagged
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import player_prior as PP  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'role-state-1'
POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
OUT = _REPO / 'nfl/derived/ROLE_STATE.json'

BANDS = ('FRINGE', 'ROTATIONAL', 'SECONDARY', 'PRIMARY', 'ALPHA')

#: The ceiling a player may be asked about, by the strongest evidence he has. Declared.
CEILING_BY_EVIDENCE = {
    'PREDICTED_STARTER': 'ALPHA',
    'DEPTH_RANK_1': 'ALPHA',
    'DEPTH_RANK_2': 'SECONDARY',
    'DEPTH_RANK_3': 'ROTATIONAL',
    'DEPTH_RANK_4_PLUS': 'FRINGE',
    'OBSERVED_ONLY': 'SECONDARY',
    'NO_EVIDENCE': 'FRINGE',
}

#: One starter per club per position may hold ALPHA. A second cannot, because two alphas in
#: one receiver room is not a football state -- it is two priors that did not know about each
#: other.
ALPHA_LIMIT = {'QB': 1, 'RB': 1, 'WR': 1, 'TE': 1}

REPLACEMENT_EXPIRES = (
    'observed usage is capped at SECONDARY when it is the ONLY evidence, because a large '
    'observed share held while the starter was injured is not a claim on the role once he '
    'returns. This is the rule that expires an injury-replacement workload.')


def _cap(band, ceiling):
    return band if BANDS.index(band) <= BANDS.index(ceiling) else ceiling


def _observed_band(row, pos):
    o = ((row.get('observed_2026') or {}).get('combined') or {})
    share = o.get('target_share') if pos in ('WR', 'TE') else (
        o.get('rush_share') if pos == 'RB' else o.get('mean_offense_pct'))
    if not isinstance(share, (int, float)):
        return None, None
    cuts = (((0.22, 'ALPHA'), (0.15, 'PRIMARY'), (0.08, 'SECONDARY'), (0.03, 'ROTATIONAL'))
            if pos in ('WR', 'TE') else
            ((0.55, 'ALPHA'), (0.35, 'PRIMARY'), (0.18, 'SECONDARY'), (0.06, 'ROTATIONAL'))
            if pos == 'RB' else
            ((0.70, 'ALPHA'), (0.40, 'PRIMARY'), (0.15, 'SECONDARY'), (0.02, 'ROTATIONAL')))
    for cut, name in cuts:
        if share >= cut:
            return name, round(share, 4)
    return 'FRINGE', round(share, 4)


def _historical_band(panel, gsis, pos, club):
    """The role this player has most often actually held, weighted by recency and sample."""
    if not gsis or not panel:
        return None
    obs = PP._observations(panel, gsis, pos, 2026, 2025)
    if not obs:
        return None
    w = collections.Counter()
    for o in obs:
        w[o['role_band']] += (PP._recency(o['seasons_back'])
                              * min(1.0, o['touches'] / 8.0))
    if not w:
        return None
    # the highest band holding at least a quarter of the weighted evidence, so one outlier
    # week cannot crown a reserve an alpha
    total = sum(w.values())
    for band in reversed(BANDS):
        if w.get(band, 0.0) / total >= 0.25:
            return band
    return w.most_common(1)[0][0]


def _position_scoped_ranks(players):
    """Re-rank the supplied depth order WITHIN club and position.

    A UNIT MISMATCH WITH LARGE CONSEQUENCES. The supplied `depth_rank` is CLUB-WIDE: Buffalo's rows
    run (1, WR), (3, RB), (4, TE), (6, TE), (7, WR), so a club's second receiver sits at club rank 7
    and its third at 10. CEILING_BY_EVIDENCE reads that number as POSITION depth -- rank 1 is an
    alpha, rank 4 or worse is a fringe player -- so every club's WR2 and beyond was capped at
    FRINGE, and only one player per club could clear rank 3 at all.

    The damage compounds downstream rather than stopping at the label. A FRINGE cap makes a player's
    own ALPHA history count as off-role, which discounts it to the role-similarity floor, which
    leaves the hierarchical prior almost no weight, which lets one current week decide the
    projection. A.J. Brown came out of that chain at 2.7 DK points with 0.06 expected touchdowns
    against a career 0.487 per game, at club-wide rank 19.

    The ordering in the source is real information; only its scope was wrong. So it is preserved and
    re-indexed within each club and position.
    """
    # AN ABSENT PLAYER HOLDS NO RANK (2026-10-09, engine dependency audit). He was ranked with everyone else, so the
    # healthy replacement of an OUT starter was numbered 2 at his position and capped at DEPTH_RANK_2 (SECONDARY):
    # Kamara on ATL@NO, Braelon Allen / Wicks / Ertz on the W4 Early slate. Absent rows get no projection anyway.
    buckets = {}
    for dk_id, row in players.items():
        r = row.get('depth_rank')
        if (row.get('current_availability') or {}).get('status') in AV.ABSENT_STATUSES:
            continue
        if isinstance(r, int):
            buckets.setdefault((row.get('team'), row.get('position')), []).append((r, dk_id))
    scoped = {}
    for key, rows in buckets.items():
        for i, (_r, dk_id) in enumerate(sorted(rows), start=1):
            scoped[dk_id] = i
    return scoped


def assign(players, panel=None):
    out = {}
    scoped_rank = _position_scoped_ranks(players)
    for dk_id, row in players.items():
        pos, club = row['position'], row['team']
        av = row['current_availability']['status']
        pred = bool((row.get('predicted_lineup_context') or {})
                    .get('in_predicted_starting_group'))
        club_wide_rank = row.get('depth_rank')
        rank = scoped_rank.get(dk_id)
        obs_band, obs_share = _observed_band(row, pos)

        if av in AV.ABSENT_STATUSES:
            out[dk_id] = {
                'dk_id': dk_id, 'name': row['name'], 'position': pos, 'team': club,
                'role_band': None, 'askable_ceiling': None,
                'state': 'NOT_PLAYING', 'evidence': 'REPORTED_ABSENT',
                'availability': av,
                'why': 'reported absent, so no role and no projection'}
            continue

        if pos == 'DST':
            out[dk_id] = {'dk_id': dk_id, 'name': row['name'], 'position': pos,
                          'team': club, 'role_band': 'ALPHA',
                          'askable_ceiling': 'ALPHA', 'state': 'TEAM_UNIT',
                          'evidence': 'TEAM_DEFENCE', 'availability': av,
                          'why': 'a team defence has no depth competition'}
            continue

        if pred:
            ev, ceiling = 'PREDICTED_STARTER', CEILING_BY_EVIDENCE['PREDICTED_STARTER']
        elif isinstance(rank, int) and rank >= 1:
            key = ('DEPTH_RANK_1' if rank == 1 else 'DEPTH_RANK_2' if rank == 2
                   else 'DEPTH_RANK_3' if rank == 3 else 'DEPTH_RANK_4_PLUS')
            ev, ceiling = key, CEILING_BY_EVIDENCE[key]
        elif obs_band:
            ev, ceiling = 'OBSERVED_ONLY', CEILING_BY_EVIDENCE['OBSERVED_ONLY']
        else:
            ev, ceiling = 'NO_EVIDENCE', CEILING_BY_EVIDENCE['NO_EVIDENCE']

        hist_band = _historical_band(panel, row.get('gsis_id'), pos, club)
        # the stronger of who he has been and what he is doing; never the ceiling by default,
        # because a predicted starter with no history is not automatically an alpha
        cands = [b for b in (hist_band, obs_band) if b]
        proposed = (max(cands, key=BANDS.index) if cands else
                    ('SECONDARY' if ev == 'PREDICTED_STARTER' else 'FRINGE'))
        band = _cap(proposed, ceiling)
        # NEVER SILENTLY CAP AN ESTABLISHED ROLE AWAY.
        #
        # When a player's own history says ALPHA and the supplied evidence says FRINGE, the system
        # does NOT know his role -- and a confident low projection is the worst of the three
        # available answers. Inventing the historical role would override current state, which this
        # layer exists to consume; hiding the disagreement is how A.J. Brown reached 2.7 DK points
        # in silence. So the evidence still governs the band, and the disagreement is NAMED so it
        # reaches the board and the outbox instead of only the number.
        # The flag is NOT raised for quarterbacks. A backup quarterback genuinely has ALPHA history
        # -- he was a starter when he played -- and a FRINGE role today, and that is not a data
        # problem: it is the exclusive-role case the appearance-probability model already handles
        # explicitly. Raising it here would bury the informative cases under 40 backup passers.
        conflict = None
        if pos != 'QB' and hist_band and BANDS.index(hist_band) - BANDS.index(band) >= 2:
            conflict = {
                'kind': 'HISTORY_ABOVE_EVIDENCE_CEILING',
                'history_band': hist_band,
                'assigned_band': band,
                'evidence': ev, 'ceiling': ceiling,
                'depth_rank_club_wide': club_wide_rank,
                'depth_rank_within_position': rank,
                'MEANING': ('this player has held a materially higher role than the supplied depth '
                            'evidence allows. Either the depth ordering is stale or his role has '
                            'genuinely changed, and this checkout cannot tell which.'),
                'CONSEQUENCE': ('his own history is discounted as off-role, so the projection rests '
                                'mostly on current-season data and should be read as low '
                                'confidence, not as a verdict.'),
            }
        out[dk_id] = {
            'dk_id': dk_id, 'name': row['name'], 'position': pos, 'team': club,
            'role_band': band, 'askable_ceiling': ceiling, 'state': 'PLAYING_ROLE_ASSIGNED',
            'evidence': ev, 'availability': av,
            'observed_band': obs_band, 'observed_share': obs_share,
            'depth_rank_club_wide': club_wide_rank,
            'depth_rank_within_position': rank,
            'RANK_SEMANTICS': ('the supplied depth_rank is club-wide; the ceiling table reads '
                              'position depth, so it is re-indexed within club and position. '
                              'Reading the club-wide number directly capped every WR2 and beyond '
                              'at FRINGE.'),
            'historical_band': hist_band,
            'role_evidence_conflict': conflict,
            'band_basis': ('HISTORY' if hist_band and proposed == hist_band
                           and hist_band != obs_band else
                           'OBSERVED' if obs_band and proposed == obs_band
                           and hist_band != obs_band else
                           'HISTORY_AND_OBSERVED_AGREE' if hist_band == obs_band
                           and hist_band else
                           'PREDICTED_STARTER_NO_HISTORY' if ev == 'PREDICTED_STARTER'
                           else 'NO_EVIDENCE'),
            'depth_rank': rank, 'in_predicted_group': pred,
            'capped': band != proposed,
            'cap_reason': (f'observed usage suggested {proposed} but evidence {ev} ceilings '
                           f'at {ceiling}. {REPLACEMENT_EXPIRES}'
                           if band != proposed else None),
        }

    # one ALPHA per club per position
    by = collections.defaultdict(list)
    for dk_id, r in out.items():
        if r.get('role_band') == 'ALPHA' and r['position'] in ALPHA_LIMIT:
            by[(r['team'], r['position'])].append((dk_id, r))
    demoted = []
    for (club, pos), rows in by.items():
        if len(rows) <= ALPHA_LIMIT[pos]:
            continue
        rows.sort(key=lambda t: (not t[1]['in_predicted_group'],
                                 t[1].get('depth_rank') or 99,
                                 -(t[1].get('observed_share') or 0)))
        for dk_id, r in rows[ALPHA_LIMIT[pos]:]:
            r['role_band'] = 'PRIMARY'
            r['capped'] = True
            r['cap_reason'] = (
                f'{club} already has an ALPHA {pos}. Two alphas in one room is not a '
                f'football state, it is two priors that did not know about each other.')
            demoted.append(r['name'])
    return out, demoted


def run():
    if not POST.exists():
        return Outcome.fail('POST_STATE_ABSENT', f'{POST.name} not built')
    players = json.loads(POST.read_text())['players']
    pr = PP.load_panel()
    panel = pr.value if pr.state.value == 'PASS' else None
    states, demoted = assign(players, panel=panel)
    c = collections.Counter(r['state'] for r in states.values())
    bands = collections.Counter(r['role_band'] for r in states.values()
                               if r.get('role_band'))
    ev = collections.Counter(r['evidence'] for r in states.values())
    capped = [r for r in states.values() if r.get('capped')]
    art = {
        'artifact': 'ROLE_STATE', 'spec_version': SPEC_VERSION,
        'CONSUMED_NOT_DESCRIPTIVE': (
            'the askable_ceiling on each row is a HARD LIMIT on the role band the prior may '
            'be asked about. V0 recorded a role and then ignored it, which is how a backup '
            'kept a starter projection after the starter returned.'),
        'REPLACEMENT_EXPIRES': REPLACEMENT_EXPIRES,
        'ceiling_by_evidence': CEILING_BY_EVIDENCE,
        'alpha_limit': ALPHA_LIMIT,
        'counts': {'state': dict(c), 'role_band': dict(bands), 'evidence': dict(ev),
                   'band_basis': dict(collections.Counter(
                       r.get('band_basis') for r in states.values() if r.get('band_basis')))},
        'panel_available': panel is not None,
        'n_capped': len(capped),
        'n_demoted_duplicate_alpha': len(demoted),
        'demoted_duplicate_alpha': sorted(demoted)[:20],
        'states': states,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=2) + '\n')
    st = _stamp_output(OUT, POST)
    if st.state is not State.PASS:
        return Outcome.fail('ROLE_STATE_NOT_STAMPED',
                            'the artifact was written but could not be stamped with its lineage',
                            stamp_code=st.code, stamp_evidence=st.evidence,
                            note=('an unstamped artifact cannot be proven current downstream, so '
                                  'this fails rather than leaving a silent gap in the chain.'))
    return Outcome.ok('ROLE_STATE_ASSIGNED', art, f'{len(states)} players',
                      n=len(states), counts=dict(c), n_capped=len(capped))


def _stamp_output(out_path, post_path):
    """Record what produced this artifact, by content hash.

    This is the artifact whose staleness was invisible: role_state.py was corrected and the
    projection kept producing the old numbers because ROLE_STATE.json had not been rebuilt.
    Stamping it means the next edit to this module invalidates the artifact immediately.
    """
    from nfl.production import lineage
    return lineage.stamp(out_path,
                         inputs=[post_path],
                         code=[pathlib.Path(__file__).resolve(),
                               pathlib.Path(__file__).resolve().with_name('player_prior.py')])


def main() -> int:
    r = run()
    print(r)
    if r.state.value != 'PASS':
        return 1
    a = r.value
    print('  state   ', a['counts']['state'])
    print('  bands   ', a['counts']['role_band'])
    print('  evidence', a['counts']['evidence'])
    print(f"  capped {a['n_capped']}, duplicate-alpha demotions "
          f"{a['n_demoted_duplicate_alpha']}")
    # the case this module exists for
    for nm in ('Drew Lock', 'Sam Darnold', 'Jaylen Warren', 'Brycen Tremayne',
               "Ja'Marr Chase"):
        for s in a['states'].values():
            if s['name'] == nm:
                print(f"  {nm:18s} band {str(s['role_band']):10s} ceiling "
                      f"{str(s['askable_ceiling']):10s} hist {str(s.get('historical_band')):10s} "
                      f"obs {str(s.get('observed_band')):10s} basis "
                      f"{str(s.get('band_basis')):28s} capped {s['capped']}")
                break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
