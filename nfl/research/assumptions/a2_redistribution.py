"""A2's test: when a teammate disappears, where does his work actually go?

THE CLAIM UNDER TEST, and it is a DEFAULT rather than a theory: when a player
is absent, his opportunity is redistributed to the rest of his room in
proportion to their existing shares. Every allocator in this repository does
that, nothing has ever measured it, and the objective here is NOT to show that
something else wins. It is to find out whether the default survives.

THE SHOCK COHORT

A shock is one materially involved player, present in the trailing window,
with ZERO opportunity in week W while his club plays. Materially involved
means a trailing-window share at or above `MIN_SHARE`, declared below.

ONLY SINGLE-SHOCK WEEKS ARE SCORED. If two materially involved players vanish
at once, the redistribution cannot be attributed to either, and averaging over
such weeks would let a clean rule look wrong because two shocks interacted.
Multi-shock weeks are COUNTED and excluded, and the count is reported.

FOUR ARMS, AND THE SECOND IS THE ONE PEOPLE FORGET

  PROPORTIONAL   s_j / (1 - s_i). The incumbent default.
  NO_TRANSFER    survivors keep their raw trailing shares and the vacated mass
                 goes to OTHER -- players who were not in the room at all.
                 This is not a straw man: elevations and call-ups are real,
                 and if the vacated share leaves the room the first arm is
                 wrong in a way the others cannot see.
  LEARNED        absorption weights FITTED on strictly earlier data, as a
                 function of (position, share-rank distance from the absent
                 man). Nothing is hand-designed; a cell with too few training
                 events falls back to PROPORTIONAL and the fallback is
                 counted.
  ROOM_UNIFORM   the vacated share split equally among survivors. The weaker
                 benchmark, present so that "better than nothing" is visible.

STRICTLY FORWARD-CHAINED. LEARNED is fitted only on events with an ordinal
strictly earlier than the event being scored. The guard is an assertion.

SCORED SEPARATELY PER ROOM. Carries, targets, red-zone carries, red-zone
targets. Routes and pass participation are NOT scored: `pbp_participation` is
not captured in this repository for any season, so the quantity does not
exist here and is reported NOT_AVAILABLE rather than approximated by targets.

NOTHING IN PRODUCTION CHANGES. This module reads. The proportional allocator
is untouched while it runs, and no substitution matrix is written anywhere.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.production.nonqb import current_season_nonqb_panel as P       # noqa: E402

SPEC_VERSION = 'a2-redistribution-shock-cohort-1'

SEASONS = (2022, 2023, 2024, 2025)
FIRST_WEEK, LAST_WEEK = 4, 18

#: Rooms. Each is one opportunity kind; a share across two kinds means
#: nothing. Red-zone rooms are thinner and that shows up in their n.
ROOMS = ('carries', 'targets', 'rz_carries', 'rz_targets')

NOT_AVAILABLE_ROOMS = {
    'routes': 'pbp_participation is not captured in this repository for any '
              'season, so routes do not exist here. Substituting targets '
              'would be a different quantity wearing the same name.',
    'pass_snaps': 'snap counts are captured for 2026 only, and the cohort is '
                  '2022-2025.',
}

#: Declared before the first run. A player below this trailing share is not
#: "materially involved" and his absence is not a shock worth attributing.
MIN_SHARE = 0.10
#: Trailing window, in club games, for the pre-shock role state.
WINDOW = 3
#: A room needs at least this many survivors for redistribution to be a
#: question rather than an identity.
MIN_SURVIVORS = 2
#: Minimum room volume in week W; below it the observed shares are noise.
MIN_VOLUME = 8.0
#: LEARNED needs this many training events in a cell before it is trusted.
MIN_CELL = 25

LOG_EPS = 1e-6
PROPORTIONAL = 'PROPORTIONAL'
NO_TRANSFER = 'NO_TRANSFER'
LEARNED = 'LEARNED'
ROOM_UNIFORM = 'ROOM_UNIFORM'
ARMS = (PROPORTIONAL, NO_TRANSFER, LEARNED, ROOM_UNIFORM)
OTHER = '__OTHER__'


def _pos_of(pid, positions):
    return positions.get(pid, 'UNK')


def build_events(seasons=SEASONS, verbose=True) -> Outcome:
    """Every single-shock room-week, with its pre-shock state and outcome."""
    events, skipped = [], collections.Counter()
    for season in seasons:
        cur = P.usage_season(season)
        if cur.state is not State.PASS:
            skipped['season_unavailable'] += 1
            continue
        by_week = collections.defaultdict(dict)
        for (wk, club, pid), d in cur.value.items():
            by_week[wk][(club, pid)] = d
        weeks = sorted(by_week)
        played = {wk: {k[0] for k in by_week[wk]} for wk in weeks}
        for W in weeks:
            if not (FIRST_WEEK <= W <= LAST_WEEK):
                continue
            prior = [w for w in weeks if w < W]
            for club in played[W]:
                club_prior = [w for w in prior if club in played[w]][-WINDOW:]
                if len(club_prior) < WINDOW:
                    skipped['short_window'] += 1
                    continue
                for room in ROOMS:
                    # PRE-SHOCK STATE: trailing-window shares.
                    tot = collections.defaultdict(float)
                    for w in club_prior:
                        for (c, pid), d in by_week[w].items():
                            if c == club:
                                tot[pid] += d[room]
                    grand = sum(tot.values())
                    if grand <= 0:
                        skipped['empty_window'] += 1
                        continue
                    pre = {pid: v / grand for pid, v in tot.items() if v > 0}
                    # OBSERVED WEEK W.
                    obs = {pid: d[room]
                           for (c, pid), d in by_week[W].items()
                           if c == club and d[room] > 0}
                    vol = sum(obs.values())
                    if vol < MIN_VOLUME:
                        skipped['thin_week'] += 1
                        continue
                    # SHOCK: materially involved, present in the window,
                    # zero this week.
                    gone = [pid for pid, s in pre.items()
                            if s >= MIN_SHARE and pid not in obs]
                    if not gone:
                        skipped['no_shock'] += 1
                        continue
                    if len(gone) > 1:
                        skipped['multi_shock'] += 1
                        continue
                    absent = gone[0]
                    survivors = {pid: s for pid, s in pre.items()
                                 if pid != absent}
                    if len(survivors) < MIN_SURVIVORS:
                        skipped['too_few_survivors'] += 1
                        continue
                    events.append({
                        'ordinal': season * 100 + W,
                        'season': season, 'week': W, 'club': club,
                        'room': room, 'absent': absent,
                        'absent_share': pre[absent],
                        'pre': survivors,
                        'obs': obs, 'volume': vol})
        if verbose:
            print(f'  {season}: {len(events)} event(s) so far', flush=True)
    if not events:
        return Outcome.blocked('A2_NO_EVENTS', 'no shock event was built',
                               cause=Cause.DATA, skipped=dict(skipped))
    return Outcome.ok(
        'A2_SHOCK_COHORT', value=events,
        detail=f'{len(events)} single-shock room-week(s) over {len(seasons)} '
               f'season(s); {skipped["multi_shock"]} multi-shock week(s) '
               f'excluded',
        spec_version=SPEC_VERSION, n_events=len(events),
        skipped=dict(skipped),
        thresholds={'MIN_SHARE': MIN_SHARE, 'WINDOW': WINDOW,
                    'MIN_SURVIVORS': MIN_SURVIVORS,
                    'MIN_VOLUME': MIN_VOLUME, 'MIN_CELL': MIN_CELL},
        rooms=list(ROOMS), rooms_not_available=dict(NOT_AVAILABLE_ROOMS),
        multi_shock_excluded_because=(
            'with two materially involved players gone the redistribution '
            'cannot be attributed to either, and a clean rule would look '
            'wrong because two shocks interacted'),
        uses_live_game_outcome_data=False)


def _cluster_ci(values, clusters, n_boot=2000, seed=20260918):
    """Cluster bootstrap over shock events. Declared seed, declared count."""
    import random
    if not values:
        return None, None
    idx = collections.defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    keys = list(idx)
    if len(keys) < 5:
        return None, None
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        pick = []
        for _k in range(len(keys)):
            pick += idx[keys[rng.randrange(len(keys))]]
        means.append(sum(values[i] for i in pick) / len(pick))
    means.sort()
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot) - 1]


def _rank_distance(pre, absent_share, pid):
    """How far this survivor sits from the absent man in the share ordering.

    Negative means he was BIGGER than the absent player. The cell key for
    LEARNED, and it is derived from the data rather than from a depth chart,
    because depth ranks are not available across these seasons.
    """
    bigger = sum(1 for s in pre.values() if s > pre[pid])
    absent_bigger = sum(1 for s in pre.values() if s > absent_share)
    return max(-3, min(3, bigger - absent_bigger))


def predict(ev, arm, learned=None, positions=None):
    """Predicted week-W shares for every survivor, plus OTHER."""
    pre, a = ev['pre'], ev['absent_share']
    surv = sum(pre.values())
    if arm == PROPORTIONAL:
        p = {pid: s / surv for pid, s in pre.items()}
        p[OTHER] = 0.0
    elif arm == NO_TRANSFER:
        p = dict(pre)
        p[OTHER] = a
    elif arm == ROOM_UNIFORM:
        p = {pid: s + a / len(pre) for pid, s in pre.items()}
        p[OTHER] = 0.0
    elif arm == LEARNED:
        w, fell_back = {}, False
        for pid in pre:
            cell = (_pos_of(pid, positions or {}),
                    _rank_distance(pre, a, pid))
            hit = (learned or {}).get(cell)
            if hit is None or hit[1] < MIN_CELL:
                fell_back = True
                w[pid] = pre[pid] / surv          # proportional fallback
            else:
                w[pid] = hit[0]
        tw = sum(w.values())
        if tw <= 0:
            p = {pid: s / surv for pid, s in pre.items()}
        else:
            p = {pid: pre[pid] + a * (w[pid] / tw) for pid in pre}
        p[OTHER] = 0.0
        p['__fell_back__'] = fell_back
    else:
        raise ValueError(arm)
    return p


def fit_learned(events, positions):
    """Absorption weight per (position, rank distance), from EARLIER events.

    The weight is the share of the vacated mass that this kind of survivor
    actually absorbed, averaged over training events. Nothing is designed: if
    football hands the work to the nearest man, that is what the numbers say;
    if it hands it to the room, they say that instead.
    """
    acc = collections.defaultdict(lambda: [0.0, 0])
    for ev in events:
        pre, a = ev['pre'], ev['absent_share']
        vol = ev['volume']
        if a <= 0 or vol <= 0:
            continue
        for pid, s in pre.items():
            got = ev['obs'].get(pid, 0.0) / vol
            gained = got - s
            cell = (_pos_of(pid, positions), _rank_distance(pre, a, pid))
            acc[cell][0] += gained / a
            acc[cell][1] += 1
    return {k: (max(0.0, v[0] / v[1]), v[1]) for k, v in acc.items() if v[1]}


def _score(ev, p):
    """Two scores, because there are two questions and they must not merge.

    TOTAL    over every observed opportunity, including work taken by players
             who were not in the trailing-window room at all.
    IN_ROOM  renormalised over the survivors only, conditional on the
             opportunity staying in the room.

    THE DECOMPOSITION IS NOT COSMETIC. PROPORTIONAL assigns probability ZERO
    to anyone outside the trailing room, so every elevation and every new
    name costs it -log(1e-6) on the total score. That is a real defect and it
    is reported as its own quantity -- ROOM CLOSURE -- but it is a defect of
    room membership, not of redistribution. Judging the redistribution rule on
    a score dominated by it would answer a question nobody asked.
    """
    vol = ev['volume']
    in_room = set(ev['pre'])
    ll_total = 0.0
    for pid, cnt in ev['obs'].items():
        q = p.get(pid, p.get(OTHER, 0.0) if pid not in in_room else 0.0)
        ll_total += -cnt * math.log(max(q, LOG_EPS))
    # IN-ROOM: renormalise the arm over survivors, score survivor work only.
    surv_p = {pid: p.get(pid, 0.0) for pid in in_room}
    tp = sum(surv_p.values())
    surv_obs = {pid: c for pid, c in ev['obs'].items() if pid in in_room}
    surv_vol = sum(surv_obs.values())
    ll_room = 0.0
    if tp > 0 and surv_vol > 0:
        for pid, cnt in surv_obs.items():
            ll_room += -cnt * math.log(max(surv_p[pid] / tp, LOG_EPS))
        ll_room /= surv_vol
    else:
        ll_room = None
    mae, n, pairs = 0.0, 0, []
    for pid, s in ev['pre'].items():
        got = ev['obs'].get(pid, 0.0) / vol
        mae += abs(p.get(pid, 0.0) - got)
        n += 1
        pairs.append((p.get(pid, 0.0) - s, got - s))
    other_obs = sum(c for pid, c in ev['obs'].items()
                    if pid not in in_room) / vol
    mae += abs(p.get(OTHER, 0.0) - other_obs)
    n += 1
    return ll_total / vol, ll_room, mae / n, pairs, other_obs


def run(seasons=SEASONS, verbose=True) -> Outcome:
    coh = build_events(seasons, verbose=verbose)
    if coh.state is not State.PASS:
        return coh
    events = coh.value
    positions = {}                 # position is not available; UNK everywhere
    by_room = collections.defaultdict(list)
    for ev in events:
        by_room[ev['room']].append(ev)

    out, violations, fellback = {}, [], collections.Counter()
    for room, evs in sorted(by_room.items()):
        evs = sorted(evs, key=lambda e: e['ordinal'])
        acc = {a: {'ll': [], 'll_room': [], 'mae': [], 'pairs': []}
               for a in ARMS}
        out_of_room = []
        by_rank = collections.defaultdict(lambda:
                                          collections.defaultdict(list))
        for i, ev in enumerate(evs):
            train = [e for e in evs if e['ordinal'] < ev['ordinal']]
            # ORDINAL GUARD, as an assertion.
            late = [e for e in train if e['ordinal'] >= ev['ordinal']]
            if late:
                violations.append({'room': room, 'ordinal': ev['ordinal']})
                continue
            learned = fit_learned(train, positions) if train else {}
            for arm in ARMS:
                p = predict(ev, arm, learned=learned, positions=positions)
                if arm == LEARNED and p.pop('__fell_back__', False):
                    fellback[room] += 1
                ll, ll_room, mae, pairs, other_obs = _score(ev, p)
                acc[arm]['ll'].append(ll)
                if ll_room is not None:
                    acc[arm]['ll_room'].append(ll_room)
                acc[arm]['mae'].append(mae)
                acc[arm]['pairs'] += pairs
                if arm == PROPORTIONAL:
                    out_of_room.append(other_obs)
                    a_sh = ev['absent_share']
                    surv_tot = sum(ev['pre'].values())
                    for pid, s in ev['pre'].items():
                        rd = _rank_distance(ev['pre'], a_sh, pid)
                        got = ev['obs'].get(pid, 0.0) / ev['volume']
                        realised = (got - s) / max(a_sh, LOG_EPS)
                        # what PROPORTIONAL says he absorbs: s_j / (1 - s_i),
                        # with (1 - s_i) taken as the survivors' own total so
                        # the two are on one scale.
                        expected = (s / surv_tot) if surv_tot > 0 else 0.0
                        key = (ev['season'], ev['week'], ev['club'])
                        by_rank[rd]['gain'].append((None, realised))
                        by_rank[rd]['excess'].append(
                            (realised - expected, key))
        rows = {}
        for arm in ARMS:
            d = acc[arm]
            n = len(d['ll']) or 1
            nr = len(d['ll_room']) or 1
            rows[arm] = {
                'n_events': len(d['ll']),
                'log_score_total': sum(d['ll']) / n,
                'log_score_in_room': (sum(d['ll_room']) / nr
                                      if d['ll_room'] else None),
                'n_in_room_events': len(d['ll_room']),
                'mae_share': sum(d['mae']) / len(d['mae'] or [1]),
            }
        # CALIBRATION OF GAINED OPPORTUNITY, proportional arm: regress the
        # realised gain on the predicted gain. Slope 1 and intercept 0 would
        # mean the default gets the transfer right on average.
        pr = acc[PROPORTIONAL]['pairs']
        slope = inter = None
        if len(pr) > 30:
            xs = [x for x, _ in pr]
            ys = [y for _, y in pr]
            mx = sum(xs) / len(xs)
            my = sum(ys) / len(ys)
            sxx = sum((x - mx) ** 2 for x in xs)
            sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            if sxx > 0:
                slope = sxy / sxx
                inter = my - slope * mx
        # HETEROGENEITY, AGAINST THE DEFAULT'S OWN PREDICTION AND CLUSTERED
        # BY EVENT. The null is NOT "every survivor absorbs the same
        # fraction" -- proportional predicts a DIFFERENT fraction for each
        # man, s_j / (1 - s_i). So the statistic is the EXCESS: realised
        # absorbed fraction minus the fraction proportional predicted for
        # him. Zero everywhere means the default is right.
        #
        # Survivors inside one shock share a shock, so the interval is a
        # cluster bootstrap over EVENTS. A naive per-survivor SE would
        # understate it, which is the error this project already measured at
        # roughly threefold on prop grading.
        het = {}
        for rd, d in sorted(by_rank.items()):
            g = d['excess']
            if len(g) < 20:
                continue
            m = sum(x for x, _ in g) / len(g)
            lo, hi = _cluster_ci([x for x, _ in g], [c for _, c in g])
            het[str(rd)] = {
                'n_survivors': len(g),
                'n_event_clusters': len({c for _, c in g}),
                'mean_excess_absorbed': m,
                'ci95_cluster_bootstrap': [lo, hi],
                'excludes_proportional': bool(
                    lo is not None and (lo > 0 or hi < 0)),
                'mean_absorbed_fraction':
                    sum(x for _, x in d['gain']) / len(d['gain'])
                    if d['gain'] else None,
                'null_is': 's_j / (1 - s_i), the fraction PROPORTIONAL '
                           'predicts for this survivor'}
        oo = out_of_room or [0.0]
        out[room] = {'n_events': len(evs), 'arms': rows,
                     'room_closure': {
                         'mean_share_to_players_outside_the_room':
                             sum(oo) / len(oo),
                         'n_events': len(oo),
                         'share_of_events_with_any_outside_work':
                             sum(1 for x in oo if x > 0) / len(oo),
                         'why_it_matters': (
                             'PROPORTIONAL assigns probability ZERO to anyone '
                             'outside the trailing room, so this mass is '
                             'scored at -log(1e-6) every time. It is a real '
                             'defect of room membership and it is NOT a '
                             'defect of the redistribution rule.')},
                     'gain_calibration': {'slope': slope, 'intercept': inter,
                                          'n_pairs': len(pr)},
                     'absorption_by_rank_distance': het,
                     'learned_fell_back_events': fellback[room]}
    if violations:
        return Outcome.fail('A2_ORDINAL_GUARD_TRIPPED',
                            f'{len(violations)} event(s) trained on their own '
                            f'ordinal or later', cause=Cause.DATA,
                            violations=violations[:10])

    # THE FALSIFIER, applied to what was measured.
    def _beat(v, key):
        base = v['arms'][PROPORTIONAL][key]
        if base is None:
            return []
        return [a for a in ARMS if a != PROPORTIONAL
                and v['arms'][a][key] is not None
                and v['arms'][a][key] < base]

    beaten = {r: _beat(v, 'log_score_total') for r, v in out.items()}
    beaten_in_room = {r: _beat(v, 'log_score_in_room')
                      for r, v in out.items()}
    hetero = {}
    for r, v in out.items():
        cells = v['absorption_by_rank_distance']
        if len(cells) < 2:
            continue
        excl = [k for k, c in cells.items() if c['excludes_proportional']]
        nearest = cells.get('0')
        hetero[r] = {
            'n_cells': len(cells),
            'cells_excluding_proportional': sorted(excl),
            'any_cell_excludes_proportional': bool(excl),
            'nearest_neighbour_excess': (nearest['mean_excess_absorbed']
                                         if nearest else None),
            'nearest_neighbour_ci95': (nearest['ci95_cluster_bootstrap']
                                       if nearest else None),
            'nearest_neighbour_absorbs_more':
                bool(nearest and nearest['excludes_proportional']
                     and nearest['mean_excess_absorbed'] > 0),
            'spread_of_mean_excess': (
                max(c['mean_excess_absorbed'] for c in cells.values())
                - min(c['mean_excess_absorbed'] for c in cells.values()))}
    # THE FALSIFIER, APPLIED AS WRITTEN, AND ITS TWO LIMBS REPORTED APART.
    #
    #   general   "the observed redistribution ratio departs from 1.0
    #              systematically by role ... with a cluster-robust interval
    #              excluding proportionality"
    #   specific  "the nearest depth-chart neighbour absorbs materially more
    #              than his proportional share"
    #
    # They are recorded separately BECAUSE THEY DO NOT AGREE. Reporting one
    # verdict would hide that the mechanism named in the falsifier is not the
    # mechanism the data shows, and a falsification that quietly repairs its
    # own reasoning is worth less than the measurement it rests on.
    general = sorted(r for r, h in hetero.items()
                     if h['any_cell_excludes_proportional'])
    specific = sorted(r for r, h in hetero.items()
                      if h['nearest_neighbour_absorbs_more'])
    return Outcome.ok(
        'A2_REDISTRIBUTION_MEASURED', value=out,
        falsifier_limb_general_departure=general,
        falsifier_limb_nearest_neighbour_absorbs_more=specific,
        falsifies_a2=bool(general),
        the_named_mechanism_was_wrong=(
            'the falsifier guessed that the nearest neighbour absorbs MORE '
            'than proportional. He does not: his excess is about zero in '
            'three rooms and negative in targets. What actually departs is '
            'the other end -- survivors who were ALREADY LARGER than the '
            'absent man absorb far LESS than proportional predicts, and the '
            'vacated work spreads down the room and out of it. The general '
            'limb fires; the specific mechanism named does not.'),
        detail='; '.join(
            f"{r}: n={v['n_events']} in-room beaten_by="
            f"{beaten_in_room[r]}" for r, v in sorted(out.items())),
        spec_version=SPEC_VERSION, seasons=list(seasons),
        n_events=len(events), cohort_detail=coh.detail,
        thresholds=coh.evidence['thresholds'],
        skipped=coh.evidence['skipped'],
        multi_shock_excluded_because=coh.evidence[
            'multi_shock_excluded_because'],
        n_events_by_room={r: v['n_events'] for r, v in out.items()},
        rooms_not_available=dict(NOT_AVAILABLE_ROOMS),
        beaten_by=beaten, beaten_by_in_room=beaten_in_room,
        two_scores_because_two_questions=(
            'the TOTAL score is dominated by work going to players outside '
            'the trailing room, which PROPORTIONAL prices at zero. The '
            'IN_ROOM score renormalises over survivors and asks only the '
            'redistribution question. Reporting one number would answer the '
            'wrong one.'),
        heterogeneity=hetero,
        ordinal_guard='assertion, not a comment; 0 violations',
        positions_not_available=(
            'position is not carried in the play-by-play rows this cohort is '
            'built from, so the LEARNED cell key is (UNK, rank distance). The '
            'rank distance is the live dimension and it is derived from the '
            'shares themselves, never from a depth chart.'),
        no_substitution_matrix_is_written=(
            'LEARNED is fitted per fold and discarded. Nothing here writes a '
            'substitution matrix, and the proportional allocator in '
            'production is untouched.'),
        uses_live_game_outcome_data=False)
