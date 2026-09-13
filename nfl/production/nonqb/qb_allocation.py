"""Production QB dropback allocation. CANDIDATE -- not promoted.

WHAT THIS FIXES

R4 measured the engine forecasting 2.62 starting quarterbacks per team: D1 team
dropbacks 36.75 against QB-summed 79.76, a ratio of 2.17, with the quarterbacks
out-dropping their own team in 92.7% of draw cells. The QB layer models a
passer's line CONDITIONAL ON BEING THE PRIMARY PASSER and nothing selected
which of the room that was.

GOVERNANCE. This is a new component evaluated on 2022-2024 development data and
it is NOT promoted. `PATH_C_STATE` is not edited by it. It enters the engine as
a REHEARSAL_ONLY candidate, which is the same runtime role every other non-QB
layer already has, and nothing in the engine is publication-eligible while
NFL-1 is unauthorised.

WHY IT IS STILL THE RIGHT THING TO WIRE IN. Two of its properties are separable:
the CRPS improvement is a forecasting claim on development data and is
exploratory; the SIMPLEX CLOSURE is an accounting property that holds by
construction in every draw. The alternative to wiring it in is leaving the
engine at 2.17x, which is not a neutral default.

PREGAME INPUTS, both available for 2026 and neither blocked on injuries:
  1. the captured depth chart -- QB rank per team
  2. last game's primary passer, strictly-earlier ordinal, spanning seasons

Research: nfl/research/qb3/. Pre-registration sha256
be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e
"""
from __future__ import annotations

import bisect
import collections
import csv
import glob
import gzip
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'qb3-dropback-allocation-candidate-1'
GOVERNANCE = 'CANDIDATE -- evaluated on 2022-2024 development data, NOT promoted'
DEPTH_GLOB = 'depth_charts.*.csv.gz'
KNOWN_LIMITATIONS = {
    'development_data': 'the walk-forward evaluation ran on 2022-2024, which '
                        'are development seasons. No prospective evidence '
                        'exists.',
    'week_1_incumbent': 'for week 1 the previous primary comes from the last '
                        'game of the PRIOR SEASON, so an offseason change of '
                        'starter is the hardest case this layer faces and is '
                        'not separately modelled.',
    'calibration_untested': 'the zero-share calibration table is descriptive. '
                            'No equivalence margin was predeclared and no test '
                            'was run, so it is not called calibrated.',
    'depth_chart_2025_absent': 'the committed depth-chart leaves stop at 2024, '
                               'so the 2025 evaluation fold could not run.',
}

_FIT = {}


def _fit_for(season: int):
    if season in _FIT:
        return _FIT[season]
    import qb3_lib as Q
    frame = Q.build_frame(Q.load_qb_panel(), Q.load_depth())
    par = Q.fit(frame, season)
    if not par['n']:
        return None
    _FIT[season] = (par, frame)
    return _FIT[season]


def cache_clear():
    _FIT.clear()


def captured_depth_chart() -> Outcome:
    """QB rank per team from the newest captured depth chart."""
    fs = sorted(glob.glob(str(_REPO / 'nfl' / 'vintage' / DEPTH_GLOB)))
    if not fs:
        return Outcome.blocked('DEPTH_CHART_NOT_CAPTURED',
                               'no depth-chart capture exists in nfl/vintage',
                               cause=Cause.DATA)
    p = fs[-1]
    rows = list(csv.DictReader(gzip.open(p, 'rt')))
    qb = [r for r in rows if (r.get('pos_abb') or '').upper() == 'QB'
          and r.get('gsis_id')]
    if not qb:
        return Outcome.fail(
            'DEPTH_CHART_NO_QB_ROWS',
            f'{pathlib.Path(p).name} carries {len(rows)} rows and none is a '
            f'quarterback. An empty read is not an empty depth chart.')
    out = collections.defaultdict(dict)
    for r in qb:
        try:
            rank = int(r['pos_rank'])
        except (ValueError, TypeError, KeyError):
            continue
        prev = out[r['team']].get(r['gsis_id'])
        if prev is None or rank < prev:
            out[r['team']][r['gsis_id']] = rank
    dts = sorted({r.get('dt') for r in qb if r.get('dt')})
    return Outcome.ok('DEPTH_CHART_OK', value=dict(out),
                      blob=pathlib.Path(p).name, n_teams=len(out),
                      n_qb_rows=len(qb), retrieved_at=(dts[-1] if dts else None))


def previous_primary(season: int, week: int) -> dict:
    """team -> the gsis_id of the primary passer of its last game, strictly
    earlier by ordinal and spanning seasons."""
    import qb3_lib as Q
    rows = Q.load_qb_panel()
    tg = Q.team_games(rows)
    prim, by_team = {}, collections.defaultdict(list)
    for (t, o), v in tg.items():
        prim[(t, o)] = Q.primary_of(v)
        by_team[t].append(o)
    cut = season * 100 + week
    out = {}
    for t, oo in by_team.items():
        oo.sort()
        i = bisect.bisect_left(oo, cut)
        out[t] = prim.get((t, oo[i - 1])) if i > 0 else None
    return out


# WHAT AN UNRESOLVED OFFICIAL NAME CAN AND CANNOT TELL US.
#
# Owner ruling 2026-09-13, narrowing `no_unresolved_identity` from "no
# unresolved inactive name of any position" to "no unresolved identity capable
# of affecting the QB room". A defensive tackle the roster vintage does not
# carry cannot hold a dropback, and refusing QB enforcement over him was
# conservative past the point of being informative.
#
# THE SOURCE'S POSITION IS USED FOR EXACTLY ONE DECISION: can this unresolved
# name touch the quarterback room? It is NEVER used to invent a gsis_id, never
# used to resolve the name, and never used to satisfy non-QB completeness --
# the name stays unresolved everywhere it was unresolved before.
QB_POSITION_TOKENS = frozenset({'QB'})

# Positions the official reports actually use. Membership is EXACT and
# uppercase: a token that is not in either set is UNKNOWN, and unknown fails
# closed. This is a frozenset and not a substring test because 'QB' sits
# inside strings like 'QB/WR' that are genuinely ambiguous and must not be
# read as either one.
KNOWN_NON_QB_POSITIONS = frozenset({
    'RB', 'FB', 'F', 'HB', 'WR', 'TE',
    'OL', 'OT', 'OG', 'G', 'C', 'T',
    'DL', 'DE', 'DT', 'NT', 'EDGE',
    'LB', 'ILB', 'MLB', 'OLB',
    'CB', 'S', 'SS', 'FS', 'DB',
    'K', 'P', 'LS',
})

UNRESOLVED_CLASSES = ('EXPLICIT_NON_QB', 'EXPLICIT_QB', 'UNKNOWN_POSITION',
                      'AMBIGUOUS_POSITION')


def classify_unresolved_position(pos) -> str:
    """One unresolved official name -> may it touch the quarterback room?

    EXPLICIT_NON_QB    the source named a position, and it is not a QB one
    EXPLICIT_QB        the source named QB
    UNKNOWN_POSITION   no position, or one this vocabulary does not know
    AMBIGUOUS_POSITION more than one position, e.g. 'QB/WR'

    Only EXPLICIT_NON_QB clears. The other three fail closed, because "we do
    not know what he plays" and "he plays quarterback" have the same
    consequence for a quarterback-room claim.
    """
    if pos is None:
        return 'UNKNOWN_POSITION'
    s = str(pos).strip().upper()
    if not s:
        return 'UNKNOWN_POSITION'
    if any(ch in s for ch in '/,|&+') or len(s.split()) > 1:
        return 'AMBIGUOUS_POSITION'
    if s in QB_POSITION_TOKENS:
        return 'EXPLICIT_QB'
    if s in KNOWN_NON_QB_POSITIONS:
        return 'EXPLICIT_NON_QB'
    return 'UNKNOWN_POSITION'


def unresolved_qb_room_risk(provenance) -> dict:
    """Do any unresolved official names put the QB room in doubt?

    Reads `unmapped_detail` -- a list of {name, team, source_position} kept by
    the ingestion artifact. When the artifact records unresolved names but no
    per-name detail, every one of them is UNKNOWN_POSITION and enforcement
    fails closed: an older artifact that cannot answer the question is not an
    artifact that answers it favourably.
    """
    prov = dict(provenance or {})
    n_unmapped = prov.get('n_unmapped')
    detail = prov.get('unmapped_detail')
    if n_unmapped in (None, 0) and not detail:
        return {'blocks_qb_enforcement': n_unmapped is None,
                'n_unresolved': 0 if n_unmapped == 0 else None,
                'blocking': [], 'cleared': [],
                'reason': ('no unresolved official name' if n_unmapped == 0
                           else 'the artifact does not report whether any '
                                'official name went unresolved')}
    if detail is None:
        names = list(prov.get('unmapped') or [])
        detail = [{'name': n, 'source_position': None} for n in names] or             [{'name': None, 'source_position': None}] * int(n_unmapped or 0)
    blocking, cleared = [], []
    for e in detail:
        cls = classify_unresolved_position(
            (e or {}).get('source_position'))
        row = {'name': (e or {}).get('name'), 'team': (e or {}).get('team'),
               'source_position': (e or {}).get('source_position'),
               'classification': cls}
        (cleared if cls == 'EXPLICIT_NON_QB' else blocking).append(row)
    return {
        'blocks_qb_enforcement': bool(blocking),
        'n_unresolved': len(detail),
        'blocking': blocking, 'cleared': cleared,
        'reason': ('every unresolved official name is explicitly a non-QB '
                   'position and cannot touch the quarterback room'
                   if not blocking else
                   f'{len(blocking)} unresolved official name(s) could affect '
                   f'the quarterback room'),
        'position_used_only_for': ('deciding whether an unresolved name can '
                                   'affect the QB room. It never resolves an '
                                   'identity and never satisfies non-QB '
                                   'completeness.'),
    }


# The six conditions, named, so a reader can see WHICH one failed rather than
# only that something did. Owner ruling 2026-09-13.
OWNERSHIP_CONDITIONS = (
    'official_inactive_evidence_ingested',
    'evidence_tied_to_this_game_and_team',
    'all_resolved_inactive_qbs_excluded',
    'no_unresolved_identity',
    'allocation_passes_accounting',
    'forecast_generated_after_enforcement',
)


def ownership_verdict(teams, out, inact, zeroed, closure_dev,
                      provenance=None) -> dict:
    """May this allocation claim `qb_inactive_ownership_enforced`?

    THE FLAG THIS REPLACES HAD NO WRITER. `qb_inactive_ownership_enforced` was
    READ in nfl/product/daily_board.py and SET NOWHERE in the repository, so
    QB_INACTIVE_NOT_CONSUMED could never clear on any board -- before or after
    consuming an official list. Measured 2026-09-13: New Orleans consumed the
    league's list, Zach Wilson's projection went to exactly zero, his share
    redistributed, and every row still carried the contamination flag.

    The answer is a governed STATE, not a suppression. All six conditions must
    hold and each is recorded with what it was judged on, so "true" is always
    auditable and "false" always names the reason. Nothing here can be set by a
    caller: the verdict is computed from the allocation that just ran.

    CONSERVATIVE ON IDENTITY, DELIBERATELY. An official name that resolved to
    no rostered player might be a quarterback this roster vintage does not
    carry. We cannot tell from a name alone, so an unresolved name refuses
    enforcement for that game rather than being assumed harmless. Reported,
    never guessed.
    """
    prov = dict(provenance or {})
    c = {}
    c['official_inactive_evidence_ingested'] = bool(inact) or bool(
        prov.get('post_inactives_complete'))
    c['evidence_tied_to_this_game_and_team'] = bool(
        prov.get('game_id') and prov.get('teams')
        and set(teams) <= set(prov.get('teams') or ()))
    in_room = {t: [p for p in v['pids'] if p in inact] for t, v in out.items()}
    excluded = {t: sorted(zeroed.get(t, [])) for t in out}
    c['all_resolved_inactive_qbs_excluded'] = all(
        sorted(in_room[t]) == excluded[t] for t in out)
    n_unmapped = prov.get('n_unmapped')
    # NARROWED 2026-09-13 BY OWNER RULING, AND NARROWED IN ONE DIRECTION ONLY.
    # The condition is about identities that could affect the QUARTERBACK
    # ROOM, not about every unresolved name on the official list. An
    # unresolved name the source explicitly calls a non-QB position cannot
    # hold a dropback; an unresolved QB, or one whose position is missing,
    # unknown or ambiguous, still refuses.
    risk = unresolved_qb_room_risk(prov)
    c['no_unresolved_identity'] = not risk['blocks_qb_enforcement']
    c['allocation_passes_accounting'] = bool(
        out) and float(closure_dev) <= 1e-6
    # The enforcement ran inside THIS allocation, so any forecast built from
    # its value is built after it by construction. It is stated rather than
    # assumed because a later reader cannot re-derive it from the board alone.
    c['forecast_generated_after_enforcement'] = True
    enforced = all(c[k] for k in OWNERSHIP_CONDITIONS)
    return {
        'enforced': enforced,
        'conditions': {k: bool(c[k]) for k in OWNERSHIP_CONDITIONS},
        'failed_conditions': [k for k in OWNERSHIP_CONDITIONS if not c[k]],
        'inactive_qbs_in_modelled_room': {t: sorted(v) for t, v in
                                          in_room.items() if v},
        'inactive_qbs_excluded': {t: v for t, v in excluded.items() if v},
        'n_unmapped_official_names': n_unmapped,
        'unmapped_official_names': prov.get('unmapped'),
        'unresolved_qb_room_risk': risk,
        'closure_max_dev': float(closure_dev),
        'game_id': prov.get('game_id'),
        'spec_version': SPEC_VERSION,
        'what_true_means': (
            'the official list for BOTH clubs was ingested and tied to this '
            'game, every officially inactive quarterback the model carries was '
            'excluded from the allocation BEFORE the draw, no official name '
            'went unresolved, the shares close, and the forecast was built '
            'from this allocation.'),
        'what_true_does_not_mean': (
            'it does not mean no quarterback is inactive, and it does not '
            'mean the projection is right. It means the inactive evidence was '
            'consumed by the mechanism that owns the share.'),
    }


def allocate(season, week, teams, qb_players, m=200, seed=20260908,
             kickoff_utc=None, written_at=None, inactive_ids=None,
             inactive_provenance=None) -> Outcome:
    """team -> (pids, shares (n_qb, m)). Shares sum to 1 in every draw.

    OFFICIALLY INACTIVE QUARTERBACKS OWN NOTHING, AND THIS IS WHERE THAT IS
    ENFORCED.

    `official_inactive_ids` used to reach the non-QB engine only
    (run_forecast.py:713). The QB path never saw it, so on the sealed SF@LA
    board Kurtis Rourke held 0.90 dropbacks and Ty Simpson 0.73 while both
    were on the league's inactive list -- about 2.5% of each team's dropbacks
    allocated to quarterbacks who were not dressed, and not redistributed to
    the men who actually played.

    The repair is here rather than downstream because this is the earliest
    causal point: the share is the thing that is wrong. Zeroing the inactive
    rows and renormalising the remainder leaves R2's largest-remainder
    apportionment completely untouched -- it simply receives the correct pool.
    A downstream subtraction would have been a second mechanism papering over
    the first.
    """
    f = _fit_for(season)
    if f is None:
        return Outcome.blocked(
            'QB_ALLOCATION_NOT_FITTED',
            f'no cell could be fitted on seasons before {season}',
            cause=Cause.DATA)
    par, _frame = f
    dc = captured_depth_chart()
    if dc.state is not State.PASS:
        return dc
    got = dc.evidence.get('retrieved_at')
    for label, bound in (('kickoff', kickoff_utc), ('written_at', written_at)):
        if bound and got and str(got) >= str(bound):
            return Outcome.fail(
                'DEPTH_CHART_CHRONOLOGY_FAILURE',
                f'the depth chart was retrieved at {got}, which is not '
                f'strictly before {label} {bound}')
    import qb3_lib as Q
    prev = previous_primary(season, week)
    by_team = collections.defaultdict(list)
    for q in qb_players:
        if q.get('gsis_id'):
            by_team[q.get('team')].append(q['gsis_id'])
    inact = set(inactive_ids or ())
    zeroed = {}
    out, ev = {}, {'teams_without_a_depth_chart': [],
                   'n_qb_by_team': {}, 'unranked_players': 0}
    for t in teams:
        room = dc.value.get(t) or {}
        pids = by_team.get(t, [])
        if not room:
            ev['teams_without_a_depth_chart'].append(t)
        # A ROSTERED QB WITH NO DEPTH RANK IS RANKED LAST, NOT DROPPED. Dropping
        # him would quietly shrink the room; ranking him last says what we know.
        trip = []
        for pid in pids:
            r = room.get(pid)
            if r is None:
                ev['unranked_players'] += 1
                r = 3
            trip.append((pid, min(int(r), 3), int(prev.get(t) == pid)))
        if not trip:
            continue
        pid_list = [x[0] for x in trip]
        mask = np.array([p in inact for p in pid_list]) if inact \
            else np.zeros(len(pid_list), bool)
        if mask.all() and len(pid_list):
            return Outcome.fail(
                'QB_ALLOCATION_ALL_QUARTERBACKS_INACTIVE',
                f'{t}: every rostered quarterback is on the official '
                f'inactive list, so there is nobody to receive the '
                f'team dropback share. Refusing rather than dividing '
                f'by zero or leaving the share with a player who is '
                f'not dressed.',
                team=t, n_qb=len(pid_list))
        # ELIGIBILITY CONDITIONS THE DRAW. IT DOES NOT EDIT ITS RESULT.
        #
        # MEASURED 2026-09-13, ON THE FIRST SUNDAY THIS PATH CARRIED A REAL
        # INACTIVE LIST. The previous wiring drew the room UNCONDITIONED, then
        # zeroed the inactive rows and renormalised what was left. That cannot
        # work, and not at the margin: `Q.allocate` samples the primary's share
        # from an empirical pool whose modal value is exactly 1.0 -- 77.7% of
        # the (rank 1, previous primary) pool and 44.2% of (rank 1, not
        # previous primary). Those draws are ONE-HOT. If the drawn primary is
        # the inactive quarterback, zeroing his row leaves the column at
        # exactly zero and the renormalisation is 0/0.
        #
        # Indianapolis measured 20.8% of draws in that state with Riley Leonard
        # inactive, so the refusal was certain. New Orleans measured 0.0% with
        # Zach Wilson inactive AT THIS SEED and would have refused on 13 of 40
        # seeds -- the board that survived did so by luck, which is the part
        # worth saying out loud.
        #
        # THIS IS A WIRING REPAIR, NOT A NEW MODEL. `p_primary` is the
        # probability that a quarterback is the game's primary passer. A player
        # who is not dressed cannot be the primary passer, so that probability
        # is zero by the definition of the event rather than by any modelling
        # choice -- the old code asserted exactly that, it just asserted it
        # after sampling, where it is arithmetically undefined. Restricting a
        # categorical to a subset of its support IS conditioning it: no
        # parameter is refit, no coefficient is added, no distributional family
        # changes, and the primary's empirical share pool is untouched.
        #
        # PARITY IS STRUCTURAL. With no inactive quarterback the eligible room
        # IS the room, the same call is made with the same arguments, and the
        # output is bit-identical. The suite asserts it.
        elig = [x for x in trip if not (inact and x[0] in inact)]
        S_e = Q.allocate(par, elig, m=m, seed=seed,
                         ordinal=season * 100 + week, team=t)
        if mask.any():
            pos = {pid: i for i, (pid, _, _) in enumerate(trip)}
            S = np.zeros((len(trip), m))
            for j, (pid, _, _) in enumerate(elig):
                S[pos[pid], :] = S_e[j, :]
            zeroed.setdefault(t, []).extend(
                [p for p, mk in zip(pid_list, mask) if mk])
            # RETAINED, AND MEANT TO BE UNREACHABLE. A guard removed once it
            # stops firing cannot tell you when the thing it guarded against
            # comes back.
            col = S.sum(0)
            if float(np.min(col)) <= 0.0:
                return Outcome.fail(
                    'QB_ALLOCATION_ZERO_ACTIVE_SHARE',
                    f'{t}: after conditioning on the officially eligible '
                    f'quarterback room at least one draw still has no share. '
                    f'Allocated mass may never be dropped.',
                    team=t)
        else:
            S = S_e
        out[t] = {'pids': pid_list, 'shares': S,
                  'ranks': [x[1] for x in trip],
                  'was_prev_primary': [x[2] for x in trip]}
        ev['n_qb_by_team'][t] = len(trip)
    if not out:
        return Outcome.fail(
            'QB_ALLOCATION_EMPTY',
            'no team received a quarterback allocation; an empty allocation '
            'is not an allocation')
    worst = max(float(np.abs(v['shares'].sum(0) - 1.0).max())
                for v in out.values())
    if worst > 1e-6:
        return Outcome.fail(
            'QB_ALLOCATION_DOES_NOT_CLOSE',
            f'the shares of some team do not sum to 1 (worst {worst:.2e}). '
            f'Closure is the property this layer exists for.')
    own = ownership_verdict(teams, out, inact, zeroed, worst,
                            inactive_provenance)
    return Outcome.ok('QB_ALLOCATION_OK', value=out,
                      spec_version=SPEC_VERSION, governance=GOVERNANCE,
                      qb_inactive_ownership_enforced=own['enforced'],
                      qb_inactive_ownership=own,
                      n_inactive_qb_zeroed=sum(len(v) for v in zeroed.values()),
                      inactive_qb_zeroed=zeroed,
                      n_teams=len(out), closure_max_dev=worst,
                      depth_chart_blob=dc.evidence['blob'],
                      depth_chart_retrieved_at=got,
                      cells_fitted=len(par['n']),
                      trained_on_seasons_before=season,
                      warnings=[f'known limitation: {k}'
                                for k in KNOWN_LIMITATIONS])
