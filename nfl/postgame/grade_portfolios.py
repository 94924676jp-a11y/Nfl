"""Phases 6 and 7: what the two portfolios actually scored, and the regret.

THE CONCLUSION THIS MODULE REFUSES TO DRAW

"Portfolio A outscored portfolio B, therefore architecture A is better." One
showdown slate is one draw from a distribution whose spread is enormous, and
the two portfolios overlap heavily -- the measured mean pairwise uniqueness
distance on the delivered set is about 2.5 players out of 6, so forty lineups
are nowhere near forty independent samples.

So the output separates four things and never merges them:

  RESULT              what scored what.
  PROCESS             what the construction rule was.
  KNOWN_PREGAME_DEFECT what was already recorded as wrong before kickoff.
  VARIANCE            everything left over, which on one slate is most of it.

A player who was rostered for a bad reason and scored well is still rostered
for a bad reason. That is the whole point of keeping the columns apart.
"""
from __future__ import annotations

import csv
import itertools
import json
import pathlib
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.postgame import outcome as OC                                 # noqa: E402
from nfl.dfs.scoring import statline as SL                             # noqa: E402
from nfl.dfs.scoring import draftkings as DK                           # noqa: E402
from nfl.dfs.showdown import universe as U                             # noqa: E402

SPEC_VERSION = 'nfl-postgame-grade-portfolios-1'
FIX = _REPO / 'nfl/research/dfs/DET_BUF_2026W2'
PORTFOLIOS = {'CLAUDE': 'PORTFOLIO_CLAUDE_40.csv',
              'ALTERNATE': 'PORTFOLIO_ALTERNATE_40.csv'}


def _nm(s):
    return re.sub(r'\s*\(\d+\)$', '', s).strip()


def actual_dk(players_actual):
    """Real DK points per NORMALISED player name, from the real stat line.

    KEYED BY `universe.norm`, NOT BY THE RAW STRING. DraftKings calls him
    'James Cook III' and the stat feed calls him 'James Cook'; a raw-string
    join drops him, and a zero-by-absence rule on top of a dropped join would
    then have scored the week's best running back as nothing. The same
    mismatch hits 'Joshua Palmer' against 'Josh Palmer'. Identity is resolved
    once, here.
    """
    out = {}
    for raw, a in players_actual.items():
        nm = U.norm(raw)
        k = a.get('kicking') or {}
        sl = SL.from_line(
            1, pass_yards=a.get('pass_yards') or 0,
            pass_td=a.get('pass_td') or 0,
            interceptions=a.get('interceptions') or 0,
            rush_yards=a.get('rush_yards') or 0, rush_td=a.get('rush_td') or 0,
            rec_yards=a.get('rec_yards') or 0,
            receptions=a.get('receptions') or 0, rec_td=a.get('rec_td') or 0,
            fg_made=k.get('fg_made') or 0, fg_att=k.get('fg_att') or 0,
            xp_made=k.get('xp_made') or 0, xp_att=k.get('xp_att') or 0,
            fg_made_by_bucket=k.get('fg_made_by_bucket') or {})
        # KICKING IS SCORED. Scoring a kicker 0 because the model cannot name
        # him confuses two different things: the MODEL refuses the (team,
        # position) join, and it is right to. The BOX SCORE names him. Leaving
        # it out scored Jake Bates -- a 31-yard field goal and four extra
        # points -- as nothing, in fifteen of forty delivered lineups.
        out[nm] = float(DK.score(sl)[0] + DK.score_kicker(sl)[0])
    return out


def optimal_lineup(scores, players):
    """The actual optimal DK Showdown lineup, solved exactly under the cap."""
    pool = [p for p in players if U.norm(p['name']) in scores]
    if len(pool) < U.N_FLEX + 1:
        return None
    best = None
    for c in pool:
        budget = U.SALARY_CAP - c['cpt_salary']
        rest = [p for p in pool if p['name'] != c['name']]
        # exact 5-item knapsack by DP over salary in 100s
        B = budget // 100
        NEG = -1e18
        dp = np.full((U.N_FLEX + 1, B + 1), NEG)
        dp[0, 0] = 0.0
        pick = [[[] for _ in range(B + 1)] for _ in range(U.N_FLEX + 1)]
        for p in rest:
            s = p['salary'] // 100
            if s > B:
                continue
            for k in range(U.N_FLEX - 1, -1, -1):
                for b in range(B - s, -1, -1):
                    if dp[k, b] <= NEG / 2:
                        continue
                    cand = dp[k, b] + scores[U.norm(p['name'])]
                    if cand > dp[k + 1, b + s]:
                        dp[k + 1, b + s] = cand
                        pick[k + 1][b + s] = pick[k][b] + [p['name']]
        row = dp[U.N_FLEX]
        b = int(np.argmax(row))
        if row[b] <= NEG / 2:
            continue
        total = row[b] + 1.5 * scores[U.norm(c['name'])]
        if best is None or total > best['score']:
            best = {'captain': c['name'], 'flex': sorted(pick[U.N_FLEX][b]),
                    'score': float(total),
                    'salary': int(c['cpt_salary'] + b * 100)}
    return best


def grade(outcome_path=None) -> Outcome:
    got = OC.require(outcome_path)
    if got.state is not State.PASS:
        return got
    intact = OC.assert_pregame_untouched()
    if intact.state is not State.PASS:
        return intact
    uni = U.build()
    if uni.state is not State.PASS:
        return uni
    players = uni.value['playable']
    scores = actual_dk(got.value['players'])
    # A board player with no outcome row whose CLUB is covered recorded
    # nothing, and nothing is zero DK points. Leaving him unscorable dropped
    # 26 of 40 ALTERNATE lineups on this slate -- ten of them for Frank Gore
    # Jr. alone -- which would have graded each portfolio only on the subset
    # that avoided its own worst pick. That is not a kindness, it is the
    # survivorship error with extra steps.
    zeroed = []
    for pl in uni.value['players']:
        key = U.norm(pl['name'])
        if key in scores:
            continue
        line, code = OC.resolve_absent(pl['name'], pl.get('team'), got.value)
        if line is not None:
            scores[key] = 0.0
            zeroed.append({'player': pl['name'], 'team': pl.get('team'),
                           'code': code})
    # THE ACTUAL OPTIMAL IS A FACT ABOUT THE SLATE, not about the model, so
    # its pool is every salaried entrant -- kickers included. `playable`
    # excludes them because the MODEL cannot name a kicker; that refusal is
    # right and it has nothing to do with what the best lineup actually was.
    pool = {}
    for pl in uni.value['players']:
        row = pool.setdefault(U.norm(pl['name']),
                              {'name': pl['name'], 'team': pl.get('team')})
        row['cpt_salary' if pl['slot'] == 'CPT' else 'salary'] = pl['salary']
    full = [r for r in pool.values()
            if 'salary' in r and 'cpt_salary' in r]
    opt = optimal_lineup(scores, full)
    # v3, NOT the original. v1 optimised without the both-teams rule and over
    # a universe with no named kicker; both are corrected, and citing v1 here
    # would set a lawful grade beside an unlawful pregame frequency.
    opt_src = next((FIX / n for n in ('OPTIMAL_WORLDS_v3.json',
                                      'OPTIMAL_WORLDS_v2.json',
                                      'OPTIMAL_WORLDS.json')
                    if (FIX / n).exists()), None)
    opt_freq = {r['name']: r for r in json.loads(
        opt_src.read_text())['rows']}
    out = {}
    for label, fn in PORTFOLIOS.items():
        lus, unscorable = [], []
        for r in csv.reader(open(FIX / fn)):
            if not (r and r[0].isdigit()):
                continue
            cap, flex = _nm(r[4]), [_nm(x) for x in r[5:10]]
            cap, flex = U.norm(cap), [U.norm(x) for x in flex]
            missing = [n for n in [cap] + flex if n not in scores]
            if missing:
                unscorable.append({'captain': cap, 'missing': missing})
                continue
            s = 1.5 * scores[cap] + sum(scores[n] for n in flex)
            lus.append({'captain': cap, 'flex': flex, 'score': float(s),
                        'captain_points': 1.5 * scores[cap],
                        'contribution': {n: scores[n] for n in flex}})
        lus.sort(key=lambda x: -x['score'])
        arr = np.array([x['score'] for x in lus]) if lus else np.array([0.0])
        out[label] = {
            'n_lineups_scored': len(lus),
            'n_unscorable': len(unscorable), 'unscorable': unscorable[:5],
            'best': lus[0] if lus else None,
            'median_score': float(np.median(arr)),
            'worst': lus[-1] if lus else None,
            'mean_score': float(arr.mean()),
            'contains_optimal': bool(
                opt and any(x['captain'] == opt['captain']
                            and sorted(x['flex']) == opt['flex'] for x in lus)),
            'regret_vs_optimal': (float(opt['score'] - arr.max())
                                  if opt and lus else None),
        }
    ev = {
        'spec_version': SPEC_VERSION,
        'actual_optimal': opt,
        'optimal_captain_pregame': (
            {'p_optimal_captain': opt_freq.get(opt['captain'], {}).get(
                'p_optimal_captain'),
             'p_optimal': opt_freq.get(opt['captain'], {}).get('p_optimal'),
             'tag': opt_freq.get(opt['captain'], {}).get('tag')}
            if opt else None),
        'optimal_flex_pregame': (
            {n: {'p_optimal': opt_freq.get(n, {}).get('p_optimal'),
                 'tag': opt_freq.get(n, {}).get('tag')} for n in opt['flex']}
            if opt else None),
        'one_slate_cannot_rank_architectures': (
            'the two portfolios overlap heavily -- mean pairwise uniqueness '
            'distance about 2.5 of 6 players on the delivered set -- so forty '
            'lineups are not forty independent samples, and a score difference '
            'between them is mostly variance. RESULT, PROCESS, '
            'KNOWN_PREGAME_DEFECT and VARIANCE are reported apart and must '
            'stay apart.'),
        'a_player_rostered_for_a_bad_reason_who_scores': (
            'is still rostered for a bad reason. Scoring does not retire the '
            'ROLE_STATE_CONCERN tag, and nothing here promotes an exposure '
            'because it worked once.'),
        'is_measurement_not_development': True,
    }
    return Outcome.ok(
        'PORTFOLIOS_GRADED', value={'portfolios': out, 'actual_dk': scores,
                                    'zero_by_absence': zeroed},
        pregame_optimal_frequencies_from=opt_src.name,
        detail=(f'optimal {opt["score"]:.2f} '
                f'(CPT {opt["captain"]}); ' if opt else 'no optimal solved; ')
               + '; '.join(f'{k} best {v["best"]["score"]:.2f}'
                           if v['best'] else f'{k} none'
                           for k, v in out.items()),
        **ev)


def main() -> int:
    o = grade()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    out = OC.DIR / 'GRADE_PORTFOLIOS.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         **o.value}, indent=1, sort_keys=True))
    c = AC.claim(out, schema=['portfolios', 'actual_dk'], label=out.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
