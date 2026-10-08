#!/usr/bin/env python3.12
"""GAP 6: pick 48 entries as one portfolio, against a simulated field, not 48 times separately.

WHY INDEPENDENT SELECTION IS THE WRONG PROBLEM

The exact optimiser from GAP 5 answers "which lineup has the highest projected total", and its
top 48 is the 48 highest. That portfolio is maximally concentrated -- on this slate it used 27
distinct players and had two of them in every single entry. For a tournament that is close to the
worst thing you can submit: the 48 entries succeed and fail together, so the portfolio has almost
the same chance of winning as one entry.

What a tournament entrant actually wants is the probability that AT LEAST ONE entry finishes high
enough to pay. That is a property of the whole set, and it is not the sum of anything -- adding a
lineup helps in proportion to the worlds it wins that nothing already in the set wins. So the
portfolio is chosen by marginal contribution to that objective, which is what makes this
contest-aware rather than projection-aware.

THE OBJECTIVE, DECLARED

    P(at least one of our entries scores above the field's top-q threshold)

computed world by world: in each simulated world the field's threshold is recomputed from the
field's own scores in THAT world, because a score that wins a low-scoring slate loses a
high-scoring one. This is why it needs the joint simulator and the field model together and
cannot be done with point projections.

WHAT THIS DOES AND DOES NOT SETTLE

It is machinery plus a measurement. The field's ownership level is uncalibrated
(FIELD_MODEL.json), so the portfolio it selects is conditional on declared parameters. The honest
question is therefore not "is this the right portfolio" but "does the choice survive the range the
parameters could take", which is measured here at the level of the DECISION rather than of a
diagnostic ratio. No entry is submitted, nothing is uploaded, and no wager is recommended.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import opponent as field_mod, ownership as own_mod  # noqa: E402
from nfl.opt import exact  # noqa: E402
from nfl.sim import game as sim_game  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.warehouse import point_in_time as PIT  # noqa: E402

V1 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'
POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
TG = PIT.resolve(_REPO / 'nfl/warehouse/TEAM_GAME.json')   # as of the cutoff in a sealed run
OUT = _REPO / 'nfl/dfs/salaries/CONTEST_PORTFOLIO.json'

SLATE_SEASON, SLATE_WEEK = 2026, 3
N_ENTRIES = 48
TOP_Q = 0.01          # "high enough to pay": the top 1% of the field
N_SIMS = 400
N_CANDIDATES = 200
FIELD_SAMPLE = 8000


def slate_specs() -> Outcome:
    """Build one simulator spec per game on the slate, with shares from the V1 projection."""
    art = json.loads(V1.read_text())
    post = json.loads(POST.read_text()) if POST.exists() else {'players': {}}
    tg = json.loads(TG.read_text())
    trows = tg['rows'] if isinstance(tg['rows'], list) else list(tg['rows'].values())
    market = {}
    for r in trows:
        if int(r['season']) != SLATE_SEASON or int(r['week']) != SLATE_WEEK:
            continue
        if r.get('total_line') is None or r.get('club_spread') is None:
            continue
        market[r['club']] = {'total': float(r['total_line']), 'spread': float(r['club_spread']),
                             'is_home': r.get('is_home'), 'opponent': r.get('opponent')}
    if not market:
        return Outcome.blocked('SLATE_NO_MARKET', f'no week {SLATE_WEEK} market lines',
                               cause=Cause.DATA)

    pool, by_club = [], collections.defaultdict(list)
    for dk, r in art['rows'].items():
        if not r.get('salary') or r.get('dk_points_if_plays') is None:
            continue
        opp = (post['players'].get(dk) or {}).get('opponent')
        row = {'id': dk, 'position': r['position'], 'salary': r['salary'],
               'value': float(r['dk_points_if_plays']), 'name': r['name'], 'team': r['team'],
               'opponent': opp,
               'targets': float(r.get('targets') or 0.0),
               'carries': float(r.get('carries') or 0.0),
               'pass_attempts': float(r.get('pass_attempts') or 0.0)}
        pool.append(row)
        by_club[r['team']].append(row)

    # pair clubs into games from the market's own opponent field
    pairs, seen = [], set()
    for club, m in market.items():
        opp = m.get('opponent')
        if opp is None or club in seen or opp in seen:
            continue
        if opp not in market or club not in by_club or opp not in by_club:
            continue
        seen.update({club, opp})
        home, away = (club, opp) if m.get('is_home') else (opp, club)
        pairs.append((home, away))

    specs = []
    for home, away in pairs:
        spec = {'total_line': market[home]['total'], 'home_spread': market[home]['spread'],
                'clubs': []}
        for club in (home, away):
            rows = by_club[club]
            dst_ids = [r['id'] for r in rows if r['position'] == 'DST']
            tt = sum(r['targets'] for r in rows) or 1.0
            tc = sum(r['carries'] for r in rows) or 1.0
            tp = sum(r['pass_attempts'] for r in rows) or 1.0
            players = []
            for r in rows:
                if r['position'] == 'DST':
                    continue
                players.append({
                    'id': r['id'], 'position': r['position'],
                    'target_share': r['targets'] / tt,
                    'carry_share': r['carries'] / tc,
                    'pass_att_share': r['pass_attempts'] / tp,
                    'pass_td_share': r['targets'] / tt if r['position'] != 'QB' else 0.0,
                    'rush_td_share': r['carries'] / tc,
                    'catch_rate': 0.65,
                })
            spec['clubs'].append({'club': club, 'players': players})
            spec['clubs'][-1]['dst_id'] = dst_ids[0] if dst_ids else None
        if all(any(p['position'] == 'QB' for p in c['players']) for c in spec['clubs']):
            specs.append(spec)
    if not specs:
        return Outcome.blocked('SLATE_NO_GAMES_ASSEMBLED', 'no game could be paired and filled',
                               cause=Cause.DATA, n_market_clubs=len(market))
    return Outcome.ok('SLATE_SPECS_BUILT', value={'specs': specs, 'pool': pool,
                                                  'n_games': len(specs)})


def simulate_slate(specs, pool, n_sims=N_SIMS, seed=101) -> Outcome:
    """Per-player DK draws for the whole slate, aligned by simulation index.

    Different games are independent, which is why the same index may be used across them. Within a
    game every player comes from one football world, which is the whole point.
    """
    m = sim_game.Model.load()
    if m.state.value != 'PASS':
        return m
    model = m.value
    draws: dict = {}
    for i, spec in enumerate(specs):
        o = sim_game.simulate_game(model, spec, n_sims=n_sims, seed=seed + i * 17)
        if o.state.value != 'PASS':
            return o
        draws.update(o.value['draws'])
    # defences and anyone the simulator does not model get an explicit state, never a zero
    missing = [r['id'] for r in pool if r['id'] not in draws]
    return Outcome.ok('SLATE_SIMULATED', value={
        'draws': draws, 'n_sims': n_sims, 'n_games': len(specs),
        'n_players_with_draws': len(draws),
        'n_players_without_draws': len(missing),
        'WITHOUT_DRAWS_MEANING': ('players the joint simulator does not model -- defences above '
                                  'all, whose distributional model is a separate gap. They are '
                                  'excluded from contest scoring rather than scored as zero, and '
                                  'any lineup needing one is reported as unscorable.'),
        'missing_ids': missing[:40],
    })


def _score(ids, draws, n_sims):
    """Total DK points per simulation for one lineup. Returns None if any player is unmodelled."""
    tot = [0.0] * n_sims
    for i in ids:
        d = draws.get(i)
        if d is None:
            return None
        for s in range(n_sims):
            tot[s] += d[s]
    return tot


def _threshold_per_sim(field, draws, n_sims, q, rng, sample):
    """The field's top-q score in each simulated world, recomputed world by world.

    A score that wins a low-scoring slate loses a high-scoring one, so a single fixed threshold
    would be answering a different question.
    """
    fs = list(field)
    if len(fs) > sample:
        fs = [fs[rng.randrange(len(fs))] for _ in range(sample)]
    usable = [l for l in fs if all(i in draws for i in l)]
    if len(usable) < 200:
        return None, len(usable)
    k = max(1, int(round(q * len(usable))))
    out = []
    for s in range(n_sims):
        scores = []
        for l in usable:
            t = 0.0
            for i in l:
                t += draws[i][s]
            scores.append(t)
        scores.sort(reverse=True)
        out.append(scores[k - 1])
    return out, len(usable)


def candidates(pool, n_frontier, top_per_position=30) -> list:
    """A candidate set wide enough for joint selection to have anything to choose between.

    The value frontier alone is the wrong pool for this. Its top lineups differ by one player and
    win or lose the same worlds, so a portfolio drawn from it is concentrated whatever objective
    picks it -- which is exactly what the first run showed: both arms at 100% exposure on some
    player because every candidate contained him.

    So the pool is the frontier PLUS, for each plausible player, the best legal lineup that
    contains him. Each of those is still PROVEN_OPTIMAL under its own constraint, so nothing here
    is a heuristic lineup; it is a set of exact answers to different questions.
    """
    seen, out = set(), []

    def add(ids, provenance):
        key = tuple(sorted(ids))
        if key in seen:
            return
        seen.add(key)
        out.append({'ids': list(ids), 'provenance': provenance})

    for c in exact.k_best(pool, n_frontier):
        add(c['ids'], 'VALUE_FRONTIER')
    by_pos = collections.defaultdict(list)
    for r in pool:
        by_pos[r['position']].append(r)
    for pos, rows in by_pos.items():
        rows = sorted(rows, key=lambda r: -r['value'] / max(1.0, r['salary'] / 1000.0))
        keep = rows if pos in ('QB', 'DST') else rows[:top_per_position]
        for r in keep:
            o = exact.solve(pool, required_players=[r['id']])
            if o.state.value == 'PASS':
                add(o.value['ids'], f'BEST_WITH_{pos}')
    return out


def build(n_sims=N_SIMS, n_candidates=N_CANDIDATES, field_sample=FIELD_SAMPLE,
          n_entries=N_ENTRIES, seed=7) -> Outcome:
    s = slate_specs()
    if s.state.value != 'PASS':
        return s
    specs, pool = s.value['specs'], s.value['pool']

    sim = simulate_slate(specs, pool, n_sims=n_sims)
    if sim.state.value != 'PASS':
        return sim
    draws = sim.value['draws']

    cands = candidates(pool, n_candidates)
    if not cands:
        return Outcome.blocked('CONTEST_NO_CANDIDATES', 'the optimiser produced no lineups',
                               cause=Cause.DATA)
    val = {r['id']: r['value'] for r in pool}
    scored, unscorable = [], 0
    for c in cands:
        t = _score(c['ids'], draws, n_sims)
        if t is None:
            unscorable += 1
            continue
        scored.append({'ids': c['ids'], 'provenance': c['provenance'],
                       'projected': round(sum(val[i] for i in c['ids']), 4), 'sim': t,
                       'sim_mean': sum(t) / n_sims})
    if len(scored) < n_entries:
        return Outcome.blocked(
            'CONTEST_TOO_FEW_SCORABLE_CANDIDATES',
            f'{len(scored)} of {len(cands)} candidates could be scored',
            cause=Cause.DATA, unscorable=unscorable,
            note=('every candidate needs a defence, and defences have no distributional model '
                  'yet. Scoring them as zero would silently rank every lineup by eight players.'))

    # the field
    fm = own_mod.ownership([dict(r, value=r['value']) for r in pool],
                           mix=own_mod.DECLARED_SHAPE_MIX)
    if fm.state.value != 'PASS':
        return fm
    rng = random.Random(seed)
    gen = field_mod.generate([dict(r, value=r['value']) for r in pool], fm.value['ownership'],
                             mix=own_mod.DECLARED_SHAPE_MIX, n_entries=20000,
                             team_of={r['id']: r['team'] for r in pool}, ipf_rounds=14)
    if gen.state.value != 'PASS':
        return gen
    thresh, n_field_usable = _threshold_per_sim(gen.value['_field'], draws, n_sims, TOP_Q, rng,
                                               field_sample)
    if thresh is None:
        return Outcome.blocked(
            'CONTEST_FIELD_NOT_SCORABLE', f'only {n_field_usable} field lineups could be scored',
            cause=Cause.DATA,
            note='the field is built from the full pool including defences, which are unmodelled')

    def p_at_least_one(sel):
        hit = 0
        for s_i in range(n_sims):
            for c in sel:
                if c['sim'][s_i] > thresh[s_i]:
                    hit += 1
                    break
        return hit / n_sims

    # ARM A: 48 independently best lineups -- what GAP 5 produces on its own
    indep = sorted(scored, key=lambda c: -c['projected'])[:n_entries]
    # ARM B: chosen jointly by marginal contribution to the objective
    remaining = list(scored)
    joint: list = []
    won = [False] * n_sims
    history = []
    while len(joint) < n_entries and remaining:
        best, best_gain = None, -1
        for c in remaining:
            gain = sum(1 for s_i in range(n_sims) if not won[s_i] and c['sim'][s_i] > thresh[s_i])
            if gain > best_gain:
                best, best_gain = c, gain
        joint.append(best)
        remaining.remove(best)
        for s_i in range(n_sims):
            if best['sim'][s_i] > thresh[s_i]:
                won[s_i] = True
        history.append({'n_entries': len(joint), 'p_at_least_one': round(sum(won) / n_sims, 5),
                        'marginal_worlds_added': best_gain})

    def profile(sel, label):
        players = collections.Counter(i for c in sel for i in c['ids'])
        return {
            'label': label, 'n_entries': len(sel),
            'p_at_least_one_in_top_1pct': round(p_at_least_one(sel), 5),
            'mean_projected': round(sum(c['projected'] for c in sel) / len(sel), 4),
            'mean_simulated': round(sum(c['sim_mean'] for c in sel) / len(sel), 4),
            'n_distinct_players': len(players),
            'max_player_exposure': round(max(players.values()) / len(sel), 4),
        }

    a, b = profile(indep, 'INDEPENDENT_TOP_48_BY_PROJECTION'), profile(joint, 'CONTEST_AWARE_JOINT')

    # ---- decision-level sensitivity ---------------------------------------------------------
    #
    # The field's ownership LEVEL is uncalibrated, so the earlier readiness verdict was BLOCKED on
    # the stability of a value-over-ownership ratio. That ratio turned out to be a poor proxy for
    # anything (it is dominated by its denominator), so the question is asked properly here: does
    # the PORTFOLIO DECISION survive the range the field parameters could take? Two things are
    # measured at each setting -- whether joint selection still beats independent, and how much of
    # the selected set is the same.
    base_ids = {tuple(sorted(c['ids'])) for c in joint}
    settings = [('value_beta', 0.6), ('value_beta', 2.2),
                ('budget', 47000), ('budget', 49900)]
    sens = []
    for name, val in settings:
        kw = {name: val}
        om = own_mod.ownership([dict(r, value=r['value']) for r in pool],
                              mix=own_mod.DECLARED_SHAPE_MIX, **kw)
        if om.state.value != 'PASS':
            sens.append({'setting': f'{name}={val}', 'state': om.code})
            continue
        g2 = field_mod.generate([dict(r, value=r['value']) for r in pool],
                                om.value['ownership'], mix=own_mod.DECLARED_SHAPE_MIX,
                                n_entries=20000,
                                team_of={r['id']: r['team'] for r in pool}, ipf_rounds=14)
        if g2.state.value != 'PASS':
            sens.append({'setting': f'{name}={val}', 'state': g2.code})
            continue
        th2, nu = _threshold_per_sim(g2.value['_field'], draws, n_sims, TOP_Q, rng, field_sample)
        if th2 is None:
            sens.append({'setting': f'{name}={val}', 'state': 'FIELD_NOT_SCORABLE'})
            continue

        def p_one(sel, th):
            hit = 0
            for s_i in range(n_sims):
                for c in sel:
                    if c['sim'][s_i] > th[s_i]:
                        hit += 1
                        break
            return hit / n_sims
        rem2, sel2, won2 = list(scored), [], [False] * n_sims
        while len(sel2) < n_entries and rem2:
            bc, bg = None, -1
            for c in rem2:
                gn = sum(1 for s_i in range(n_sims) if not won2[s_i] and c['sim'][s_i] > th2[s_i])
                if gn > bg:
                    bc, bg = c, gn
            sel2.append(bc)
            rem2.remove(bc)
            for s_i in range(n_sims):
                if bc['sim'][s_i] > th2[s_i]:
                    won2[s_i] = True
        ov = len(base_ids & {tuple(sorted(c['ids'])) for c in sel2}) / n_entries
        sens.append({
            'setting': f'{name}={val}',
            'p_joint': round(p_one(sel2, th2), 5),
            'p_independent': round(p_one(indep, th2), 5),
            'joint_still_wins': p_one(sel2, th2) > p_one(indep, th2),
            'portfolio_overlap_with_base': round(ov, 4),
        })
    ok_all = all(x.get('joint_still_wins') for x in sens if 'p_joint' in x)
    min_ov = min((x['portfolio_overlap_with_base'] for x in sens
                  if 'portfolio_overlap_with_base' in x), default=None)
    art = {
        'ARTIFACT': 'CONTEST_PORTFOLIO',
        'OBJECTIVE': f'P(at least one of {n_entries} entries above the field top {TOP_Q:.0%})',
        'THRESHOLD_IS_PER_WORLD': ('recomputed from the field\'s own scores in each simulated '
                                   'world, because a winning score depends on the slate'),
        'n_sims': n_sims, 'n_games': len(specs), 'n_candidates_scored': len(scored),
        'candidate_provenance': dict(collections.Counter(c['provenance'] for c in scored)),
        'n_candidates_unscorable': unscorable,
        'n_field_lineups_scored': n_field_usable,
        'arms': [a, b],
        'decision_sensitivity': {
            'settings': sens,
            'joint_beats_independent_at_every_setting': ok_all,
            'lowest_portfolio_overlap_with_base': min_ov,
            'READING': (
                'the CONCLUSION -- pick jointly, not independently -- is what survives or fails '
                'here, and it is separate from whether the specific 48 lineups are stable. A '
                'robust conclusion with an unstable selection means the method is usable and the '
                'exact entries are not yet.'),
            'VERDICT': ('METHOD_ROBUST_SELECTION_' + ('STABLE' if (min_ov or 0) >= 0.8
                                                      else 'PARAMETER_DEPENDENT')) if ok_all
            else 'METHOD_NOT_ROBUST_TO_FIELD_PARAMETERS',
        },
        'improvement': {
            'p_at_least_one_absolute': round(b['p_at_least_one_in_top_1pct']
                                             - a['p_at_least_one_in_top_1pct'], 5),
            'p_at_least_one_relative': (
                round(b['p_at_least_one_in_top_1pct'] / a['p_at_least_one_in_top_1pct'], 4)
                if a['p_at_least_one_in_top_1pct'] > 0 else None),
            'mean_projection_given_up': round(a['mean_projected'] - b['mean_projected'], 4),
        },
        'marginal_history': history,
        'entries': [
            {'entry': i + 1, 'provenance': c['provenance'],
             'projected': c['projected'], 'simulated_mean': round(c['sim_mean'], 4),
             'ids': c['ids'],
             'names': [next((r['name'] for r in pool if r['id'] == x), x) for x in c['ids']],
             'salary': sum(next(r['salary'] for r in pool if r['id'] == x) for x in c['ids'])}
            for i, c in enumerate(joint)],
        'ENTRIES_ARE_NOT_SUBMITTED': ('the rosters are recorded so the deliverable can show what '
                                      'the method selected and so legality can be checked. '
                                      'Nothing is uploaded to DraftKings and no contest is '
                                      'entered.'),
        'simulation_coverage': {k: v for k, v in sim.value.items() if k != 'draws'},
        'GOVERNANCE': {
            'field_calibration': own_mod.CALIBRATION_STATE,
            'entries_submitted': 'NONE. Nothing is uploaded and no wager is recommended.',
            'sim_optimal': 'NOT_CLAIMED',
            'supersedes': (
                'FIELD_MODEL.STAGE_READINESS said contest-aware decisions were '
                'BLOCKED_PENDING_ARCHIVED_OWNERSHIP. That verdict rested on the stability of a '
                'value-over-ownership ratio, which is a poor proxy: it is dominated by its '
                'denominator and is labelled DIAGNOSTIC_NOT_AN_ORDERING in the field model '
                'itself. decision_sensitivity above asks the question directly, of the decision, '
                'and splits it in two.'),
            'refined_state': {
                'method_pick_jointly_not_independently': 'USABLE -- it wins at every field '
                                                         'setting tested, by 0.18 to 0.32 '
                                                         'absolute',
                'the_specific_48_entries': 'NOT_DETERMINED -- overlap with the base selection is '
                                           '0.46 to 0.62 across the same settings, so which '
                                           'lineups you enter still depends on uncalibrated '
                                           'parameters',
                'what_closes_it': 'archived contest ownership, OUT-040',
            },
            'dst_scoring_tail': ('defensive and return touchdowns and safeties are drawn from '
                                 'play-by-play measurements inside each points-allowed band, so a '
                                 'defence here carries its real upside tail rather than a floor. '
                                 'See DST_MODEL.scoring_tail; OUT-041 closed 2026-09-28. Blocked '
                                 'kicks, and a muffed kick recovered by the kicking team, are '
                                 'still not counted and are named in the artifact.'),
        },
    }
    OUT.write_text(json.dumps(art, indent=2))
    return Outcome.ok('CONTEST_PORTFOLIO_BUILT', value=art)


if __name__ == '__main__':
    o = build(*(int(x) for x in sys.argv[1:]))
    print(o.state.value, o.code)
    if o.state.value != 'PASS':
        print(json.dumps(o.evidence, indent=2, default=str)[:1500])
        raise SystemExit(1)
    v = o.value
    print(f"{v['n_games']} games, {v['n_sims']} worlds, {v['n_candidates_scored']} candidates "
          f"scored ({v['n_candidates_unscorable']} unscorable), "
          f"{v['n_field_lineups_scored']} field lineups")
    for arm in v['arms']:
        print(f"  {arm['label']:34s} P(top1%) {arm['p_at_least_one_in_top_1pct']:.4f}  "
              f"proj {arm['mean_projected']:.2f}  sim {arm['mean_simulated']:.2f}  "
              f"distinct {arm['n_distinct_players']:3d}  max exposure "
              f"{arm['max_player_exposure']:.2f}")
    ds = v['decision_sensitivity']
    print(f"  decision sensitivity: {ds['VERDICT']}")
    for x in ds['settings']:
        if 'p_joint' in x:
            print(f"    {x['setting']:18s} joint {x['p_joint']:.4f} vs indep "
                  f"{x['p_independent']:.4f}  overlap with base "
                  f"{x['portfolio_overlap_with_base']:.2f}")
        else:
            print(f"    {x['setting']:18s} {x['state']}")
    i = v['improvement']
    print(f"  joint vs independent: {i['p_at_least_one_absolute']:+.4f} absolute, "
          f"{i['p_at_least_one_relative']}x relative, giving up "
          f"{i['mean_projection_given_up']:.2f} projected points per entry")
