#!/usr/bin/env python3.12
"""Contest-specific DraftKings Classic portfolios from ONE frozen football world.

    python3.12 nfl/opt/classic_portfolio.py 2026W4

WHAT IT CONSUMES, AND ONLY THAT
  DK_<slate>_EARLY_STATE.json   universe, salaries, DK ids, availability, roles (no market number read)
  DK_<slate>_EARLY_PROJ.json    the football-only projection (market_arm FOOTBALL_ONLY, refused otherwise)
  DK_<slate>_EARLY_DRAWS.json   joint DK-point worlds per player (2000), projection-centred
  the owner's DK entries export  Entry IDs and contest ids, read, never modified
It never reads the FantasyCruncher file, a Hard Rock price, an implied total or AvgPointsPerGame.

HOW A PORTFOLIO IS CHOSEN
  candidates   the exact optimiser's best legal lineup in each of a sample of simulated worlds, plus
               the same under a blend toward the mean (robustness to one world's luck), plus the mean
               optimum. Every candidate is legal by construction and re-verified below.
  objective    E_w[ max_i (S_iw - T_w)+ ]: in each world, how far the portfolio's best entry clears a
               tournament bar T_w, averaged over 2000 worlds. T_w is the (1-q) quantile of the
               candidate set's scores IN THAT WORLD -- a field proxy, because NO OWNERSHIP DATA EXISTS
               for this slate. Duplication risk is therefore NOT MODELLED, and the artifact says so.
  selection    greedy by marginal gain, under declared exposure caps and a pairwise-overlap limit.
               Each contest is optimised as its own portfolio from its own candidate pool; the 20-max
               set is NOT the best 20 of the 150-max set.

EVERY LIMIT BELOW IS A DECLARED PORTFOLIO POLICY, NOT A MEASURED QUANTITY. Nothing here has measured
an optimal exposure cap, overlap limit or tournament quantile for this contest, and the artifact
carries them as choices.

It submits nothing, uploads nothing, and the owner's entries file is not modified. The upload-format
CSV it writes is a new file for the owner to review.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import pathlib
import random
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import early_only as EO  # noqa: E402
from nfl.opt import exact  # noqa: E402
from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'classic-portfolio-1'
OUT_DIR = _REPO / 'nfl/dfs/salaries'
SALARY_CAP = 50000
SLOTS = ('QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST')
PLAYABLE_STATES = ('PROJECTED', 'PROJECTED_DST')

#: DECLARED POLICY per contest profile. Read the module docstring: choices, not measurements.
PROFILES = {
    'MAX150': {
        'meaning': '150-max: broad, controlled diversification; exposure must be earned by portfolio value',
        'pool': 'STANDARD', 'q': 0.01, 'exposure_cap': 0.45, 'qb_exposure_cap': 0.35, 'dst_exposure_cap': 0.30,
        'max_shared': 6, 'n_worlds_for_candidates': 360, 'blend': (1.0, 0.6),
    },
    'MAX20': {
        'meaning': '20-max: conviction; stronger roles only, fewer thin punts, more concentration allowed',
        'pool': 'CONVICTION', 'q': 0.01, 'exposure_cap': 0.65, 'qb_exposure_cap': 0.50, 'dst_exposure_cap': 0.45,
        'max_shared': 7, 'n_worlds_for_candidates': 240, 'blend': (1.0, 0.6),
    },
    'MAX3': {
        'meaning': '3-entry: the conviction pool, three lineups chosen as a set',
        'pool': 'CONVICTION', 'q': 0.01, 'exposure_cap': 1.0, 'qb_exposure_cap': 0.67, 'dst_exposure_cap': 0.67,
        'max_shared': 6, 'n_worlds_for_candidates': 0, 'blend': (),   # reuses the MAX20 candidates
    },
}

#: Pool filters, DECLARED. STANDARD drops only players who cannot plausibly matter (simulated P90 under
#: 8 DK points AND mean under 3), so a thin punt with a real ceiling stays. CONVICTION also drops
#: FRINGE and ROTATIONAL roles, cold starts, and any non-DST player projected under 5 points.
STANDARD_MIN_P90, STANDARD_MIN_MEAN = 8.0, 3.0
CONVICTION_MIN_MEAN = 5.0
CONVICTION_EXCLUDED_BANDS = ('FRINGE', 'ROTATIONAL')

#: Stack rules, DECLARED and reported: every lineup carries its QB with at least one of his own WR/TE;
#: no defence faces the lineup's own quarterback. Bring-backs are NOT required -- they appear where the
#: joint worlds make them pay, and their frequency is reported.
QB_STACK_MIN = 1
FORBID_DST_AGAINST_QB = True

#: The owner's contests on this slate, read from the export and mapped to a profile by entry count.
#: An unrecognised count REFUSES rather than defaulting.
PROFILE_BY_ENTRY_COUNT = {150: 'MAX150', 20: 'MAX20', 3: 'MAX3'}


def _paths(slate_id):
    b = OUT_DIR / f'DK_{slate_id}_EARLY'
    return {'state': pathlib.Path(f'{b}_STATE.json'), 'proj': pathlib.Path(f'{b}_PROJ.json'),
            'draws': pathlib.Path(f'{b}_DRAWS.json'), 'out': pathlib.Path(f'{b}_PORTFOLIOS.json')}


def research_book_gate(slate_id, P):
    """None when lineups may be built; otherwise the refusal.

    OWNER football_intelligence_graph (2026-10-03): the game research book comes BEFORE lineup
    optimisation, and if team accounting does not reconcile, downstream publication is refused.
    The book must exist, be built from these exact projection and draws, and carry ACCOUNTING PASS.
    """
    bp = OUT_DIR / f'DK_{slate_id}_EARLY_RESEARCH_BOOK.json'
    if not bp.exists():
        return Outcome.blocked('PORTFOLIO_NO_RESEARCH_BOOK', f'{bp.name} not built; run classic_research_book first',
                               cause=Cause.NOT_EXECUTED)
    book = json.loads(bp.read_text())
    want = {'PROJ.json': hashlib.sha256(P['proj'].read_bytes()).hexdigest(),
            'DRAWS.json': hashlib.sha256(P['draws'].read_bytes()).hexdigest()}
    have = {k: (book.get('inputs_sha256') or {}).get(k) for k in want}
    if have != want:
        return Outcome.fail('PORTFOLIO_RESEARCH_BOOK_STALE',
                            'the research book was built from a different projection or draws; rebuild it')
    if (book.get('ACCOUNTING') or {}).get('state') != 'PASS':
        return Outcome.fail('PORTFOLIO_REFUSES_ACCOUNTING_FAILURE',
                            f"team accounting failed: {(book.get('ACCOUNTING') or {}).get('failures')}")
    return None


def load(slate_id):
    P = _paths(slate_id)
    st = json.loads(P['state'].read_text())
    proj = json.loads(P['proj'].read_text())
    dr = json.loads(P['draws'].read_text())
    if proj.get('market_arm') != 'FOOTBALL_ONLY' or dr.get('market_arm') != 'FOOTBALL_ONLY':
        return Outcome.fail('PORTFOLIO_REFUSES_MARKET_ARM',
                            'the projection or the draws are not the football-only arm; a market-arm number '
                            'is a prohibited proprietary input under the owner production contract')
    if dr['football_sanity']['state'] != 'PASS':
        return Outcome.fail('PORTFOLIO_REFUSES_INSANE_PROJECTION',
                            f'football sanity gate {dr["football_sanity"]["code"]}: selection is gated on it')
    if dr.get('projection_sha256') != hashlib.sha256(P['proj'].read_bytes()).hexdigest():
        return Outcome.fail('PORTFOLIO_DRAWS_NOT_FROM_THIS_PROJECTION',
                            'the draws were built from a different projection file')
    gate = research_book_gate(slate_id, P)
    if gate is not None:
        return gate
    ids, mat, meta = [], [], {}
    for dk, p in st['players'].items():
        r = proj['rows'].get(dk) or {}
        if r.get('projection_state') not in PLAYABLE_STATES:
            continue
        if 'INACTIVE' in p['current_availability']['status']:
            continue
        k = S.player_key(p['name'], p['team'])
        v = dr['draws'].get(k)
        if v is None:
            return Outcome.fail('PORTFOLIO_PLAYER_WITHOUT_DRAWS', f'{p["name"]} {p["team"]} projected but not drawn')
        ids.append(dk)
        mat.append(v)
        meta[dk] = {'name': p['name'], 'team': p['team'], 'opp': p['opponent'], 'pos': p['position'],
                    'salary': p['salary'], 'game': p['game_id'], 'role_band': r.get('role_band'),
                    'state': r.get('projection_state'), 'designation': p['current_availability'].get('designation')}
    M = np.asarray(mat, dtype=np.float64)
    return Outcome.ok('PORTFOLIO_INPUTS_LOADED', {'ids': ids, 'M': M, 'meta': meta, 'state': st, 'proj': proj,
                                                  'draws_doc': {k: v for k, v in dr.items() if k != 'draws'}},
                      f'{len(ids)} playable players x {M.shape[1]} worlds')


def pool_filter(kind, ids, M, meta):
    mean, p90 = M.mean(1), np.percentile(M, 90, axis=1)
    keep, why = [], {}
    for i, dk in enumerate(ids):
        m = meta[dk]
        if m['pos'] == 'DST':
            keep.append(i)
            continue
        if mean[i] < STANDARD_MIN_MEAN and p90[i] < STANDARD_MIN_P90:
            why[dk] = 'THIN_NO_CEILING'
            continue
        if kind == 'CONVICTION':
            if m['role_band'] in CONVICTION_EXCLUDED_BANDS:
                why[dk] = f'CONVICTION_EXCLUDES_{m["role_band"]}'
                continue
            if mean[i] < CONVICTION_MIN_MEAN:
                why[dk] = 'CONVICTION_EXCLUDES_UNDER_5_POINTS'
                continue
            if m['designation'] in ('QUESTIONABLE', 'DOUBTFUL'):
                why[dk] = f'CONVICTION_EXCLUDES_{m["designation"]}'
                continue
        keep.append(i)
    return keep, why


def _solve(ids, idx, values, meta):
    pool = [{'id': ids[i], 'position': meta[ids[i]]['pos'], 'salary': meta[ids[i]]['salary'],
             'value': float(values[i])} for i in idx]
    team_of = {ids[i]: meta[ids[i]]['team'] for i in idx}
    opp_of = {ids[i]: meta[ids[i]]['opp'] for i in idx}
    o = exact.solve_structured(pool, cap=SALARY_CAP, team_of=team_of, opp_of=opp_of,
                               qb_stack_min=QB_STACK_MIN, forbid_dst_against_qb_opp=FORBID_DST_AGAINST_QB)
    if o.state.value != 'PASS':
        return None
    # exact.solve_structured returns {'value', 'ids', 'salary', 'optimality', ...} on .value.
    got = (o.value or {}).get('ids')
    if not got or len(got) != 9:
        raise RuntimeError(f'optimiser PASS without a 9-player ids list: {o.code} {str(o.value)[:120]}')
    return frozenset(got)


def candidates(ids, M, meta, idx, n_worlds, blends, seed):
    rng = random.Random(seed)
    worlds = rng.sample(range(M.shape[1]), min(n_worlds, M.shape[1]))
    mean = M.mean(1)
    out = set()
    base = _solve(ids, idx, mean, meta)
    if base:
        out.add(base)
    for w in worlds:
        for b in blends:
            v = mean + b * (M[:, w] - mean)
            lu = _solve(ids, idx, v, meta)
            if lu:
                out.add(lu)
    return sorted(out, key=lambda s: sorted(s))


def verify_lineup(lu, meta):
    """Every DK Classic rule, checked on the lineup itself. Returns a list of violations."""
    v = []
    ps = [meta[i] for i in lu]
    if len(lu) != 9:
        v.append(f'{len(lu)} players, not 9')
    if len(set(lu)) != len(lu):
        v.append('a player appears twice')
    pos = collections.Counter(p['pos'] for p in ps)
    if pos['QB'] != 1 or pos['DST'] != 1 or pos['TE'] < 1 or pos['RB'] < 2 or pos['WR'] < 3 \
            or pos['RB'] + pos['WR'] + pos['TE'] != 7:
        v.append(f'positions {dict(pos)} fit no QB/RB2/WR3/TE/FLEX/DST shape')
    sal = sum(p['salary'] for p in ps)
    if sal > SALARY_CAP:
        v.append(f'salary {sal} over the {SALARY_CAP} cap')
    if len({p['game'] for p in ps}) < 2:
        v.append('players from fewer than 2 games')
    if any(p['state'] not in PLAYABLE_STATES for p in ps):
        v.append('a non-playable projection state')
    if any(p['designation'] == 'OUT' for p in ps):
        v.append('a player reported OUT')
    qb = next((p for p in ps if p['pos'] == 'QB'), None)
    if qb:
        if sum(1 for p in ps if p['team'] == qb['team'] and p['pos'] in ('WR', 'TE')) < QB_STACK_MIN:
            v.append('QB without a same-team WR/TE (declared stack rule)')
        if FORBID_DST_AGAINST_QB and any(p['pos'] == 'DST' and p['team'] == qb['opp'] for p in ps):
            v.append('DST facing the lineup quarterback (declared rule)')
    return v


def select(cands, ids, M, meta, n, prof):
    col = {dk: i for i, dk in enumerate(ids)}
    S_ = np.stack([M[[col[d] for d in c]].sum(0) for c in cands])          # candidates x worlds
    T = np.quantile(S_, 1 - prof['q'], axis=0)                             # per-world bar
    best = np.full(M.shape[1], -np.inf)
    chosen, expo = [], collections.Counter()
    for _ in range(n):
        top, top_gain = None, -1.0
        for j, c in enumerate(cands):
            if j in chosen:
                continue
            k = len(chosen) + 1
            ok = True
            for d in c:
                cap = (prof['qb_exposure_cap'] if meta[d]['pos'] == 'QB' else
                       prof['dst_exposure_cap'] if meta[d]['pos'] == 'DST' else prof['exposure_cap'])
                if (expo[d] + 1) > max(1, int(cap * n + 1e-9)):
                    ok = False
                    break
            if not ok or any(len(c & cands[i]) > prof['max_shared'] for i in chosen):
                continue
            gain = float(np.maximum(np.maximum(best, S_[j]) - T, 0).mean()
                         - np.maximum(best - T, 0).mean()) if chosen else float(np.maximum(S_[j] - T, 0).mean())
            gain += 1e-6 * float(S_[j].mean())                              # tie-break on mean
            if gain > top_gain:
                top, top_gain = j, gain
        if top is None:
            break
        chosen.append(top)
        best = np.maximum(best, S_[top])
        expo.update(cands[top])
    return chosen, S_, T


def slot_assign(lu, meta):
    # salary, then DK id: a frozenset iterates in hash order, so equal salaries need a total order
    # or the same lineup is written with two players' slots swapped from one process to the next
    ps = sorted(lu, key=lambda d: (-meta[d]['salary'], d))
    by = collections.defaultdict(list)
    for d in ps:
        by[meta[d]['pos']].append(d)
    out = {'QB': by['QB'][:1], 'RB': by['RB'][:2], 'WR': by['WR'][:3], 'TE': by['TE'][:1], 'DST': by['DST'][:1]}
    extra = by['RB'][2:] + by['WR'][3:] + by['TE'][1:]
    return [out['QB'][0], out['RB'][0], out['RB'][1], out['WR'][0], out['WR'][1], out['WR'][2],
            out['TE'][0], extra[0], out['DST'][0]]


def report(chosen_lus, M, ids, meta, T):
    col = {dk: i for i, dk in enumerate(ids)}
    n = len(chosen_lus)
    expo = collections.Counter(d for lu in chosen_lus for d in lu)
    slot = collections.defaultdict(collections.Counter)
    stacks, games, sal, qbs, dsts = collections.Counter(), collections.Counter(), [], collections.Counter(), collections.Counter()
    bring = collections.Counter()
    for lu in chosen_lus:
        sl = slot_assign(lu, meta)
        for s, d in zip(SLOTS, sl):
            slot[d][s] += 1
        qb = next(d for d in lu if meta[d]['pos'] == 'QB')
        q = meta[qb]
        mates = [d for d in lu if meta[d]['team'] == q['team'] and meta[d]['pos'] in ('WR', 'TE')]
        rb_same = sum(1 for d in lu if meta[d]['team'] == q['team'] and meta[d]['pos'] == 'RB')
        opp = [d for d in lu if meta[d]['team'] == q['opp'] and meta[d]['pos'] in ('WR', 'TE', 'RB')]
        stacks[f'QB+{len(mates)}'] += 1
        bring[f'bring_back_{len(opp)}'] += 1
        stacks[f'same_team_RB_{rb_same}'] += 1
        qbs[q['name']] += 1
        dst = next(d for d in lu if meta[d]['pos'] == 'DST')
        dsts[meta[dst]['name']] += 1
        for g in {meta[d]['game'] for d in lu}:
            games[g] += 1
        sal.append(sum(meta[d]['salary'] for d in lu))
    ov = [len(a & b) for i, a in enumerate(chosen_lus) for b in chosen_lus[i + 1:]]
    scores = np.stack([M[[col[d] for d in lu]].sum(0) for lu in chosen_lus]) if chosen_lus else np.zeros((0, M.shape[1]))
    best = scores.max(0) if n else np.zeros(M.shape[1])
    return {
        'n_lineups': n, 'n_unique': len(set(chosen_lus)),
        'p_any_entry_clears_bar': round(float((best >= T).mean()), 4),
        'expected_best_entry_score': round(float(best.mean()), 2),
        'player_exposure': {meta[d]['name'] + ' ' + meta[d]['team']: {
            'dk_id': d, 'pos': meta[d]['pos'], 'salary': meta[d]['salary'],
            'overall': round(c / n, 3), 'by_slot': {s: round(k / n, 3) for s, k in slot[d].items()}}
            for d, c in expo.most_common()},
        'qb_exposure': {k: round(v / n, 3) for k, v in qbs.most_common()},
        'dst_exposure': {k: round(v / n, 3) for k, v in dsts.most_common()},
        'stack_table': {k: round(v / n, 3) for k, v in sorted(stacks.items())},
        'bring_back_table': {k: round(v / n, 3) for k, v in sorted(bring.items())},
        'game_exposure': {k: round(v / n, 3) for k, v in games.most_common()},
        'salary_used': {'min': min(sal) if sal else None, 'median': float(np.median(sal)) if sal else None,
                        'max': max(sal) if sal else None,
                        'histogram': dict(collections.Counter((s // 500) * 500 for s in sal))},
        'overlap_distribution': dict(collections.Counter(ov)),
    }


def build(slate_id: str, *, seed: int = 20261004, write: bool = True, exclude=(), tag: str = '') -> Outcome:
    """`exclude`: DK ids removed from every candidate pool (a sensitivity run). `tag`: write to
    nfl/dfs/salaries/sensitivity/ under that tag instead of the production files, which a tagged
    or excluding run never touches."""
    if exclude and not tag:
        return Outcome.fail('PORTFOLIO_EXCLUSION_NEEDS_TAG',
                            'a run with players removed must not write the production portfolio')
    lo = load(slate_id)
    if lo.state.value != 'PASS':
        return lo
    L = lo.value
    ids, M, meta = L['ids'], L['M'], L['meta']
    files = EO.slate_files(slate_id)
    eo = EO.entries(files['entries_blob'], files['entries_sha'])
    if eo.state.value != 'PASS':
        return eo
    by_contest = collections.defaultdict(list)
    for e in eo.value:
        by_contest[(e['contest_id'], e['contest_name'], e['entry_fee'])].append(e['entry_id'])
    contests = []
    for (cid, cname, fee), eids in sorted(by_contest.items()):
        prof = PROFILE_BY_ENTRY_COUNT.get(len(eids))
        if prof is None:
            return Outcome.fail('PORTFOLIO_CONTEST_SIZE_UNMAPPED',
                                f'{cname} has {len(eids)} entries and no declared profile')
        contests.append({'contest_id': cid, 'contest_name': cname, 'entry_fee': fee,
                         'entry_ids': eids, 'profile': prof})

    pools = {}
    for kind in ('STANDARD', 'CONVICTION'):
        idx_, exc_ = pool_filter(kind, ids, M, meta)
        if exclude:
            drop = {i for i in idx_ if ids[i] in set(exclude)}
            idx_ = [i for i in idx_ if i not in drop]
        pools[kind] = (idx_, exc_)
    cand_cache = {}
    out_contests, all_ok = [], True
    for c in contests:
        prof = PROFILES[c['profile']]
        idx, excluded = pools[prof['pool']]
        key = prof['pool']
        if key not in cand_cache:
            src = PROFILES['MAX150' if key == 'STANDARD' else 'MAX20']
            cand_cache[key] = candidates(ids, M, meta, idx, src['n_worlds_for_candidates'], src['blend'],
                                         seed + (0 if key == 'STANDARD' else 1))
        cands = cand_cache[key]
        n = len(c['entry_ids'])
        chosen, S_, T = select(cands, ids, M, meta, n, prof)
        lus = [cands[j] for j in chosen]
        bad = {i: verify_lineup(lu, meta) for i, lu in enumerate(lus)}
        bad = {i: v for i, v in bad.items() if v}
        filled = len(lus) == n
        all_ok &= filled and not bad
        rows = []
        for eid, lu in zip(c['entry_ids'], lus):
            sl = slot_assign(lu, meta)
            rows.append({'entry_id': eid, 'slots': [{'slot': s, 'dk_id': d, 'name': meta[d]['name'],
                                                    'team': meta[d]['team'], 'salary': meta[d]['salary']}
                                                   for s, d in zip(SLOTS, sl)],
                         'salary': sum(meta[d]['salary'] for d in lu),
                         'sim_mean': round(float(M[[ids.index(d) for d in lu]].sum(0).mean()), 2)})
        out_contests.append({**{k: c[k] for k in ('contest_id', 'contest_name', 'entry_fee', 'profile')},
                             'n_entries': n, 'n_filled': len(lus), 'policy': prof,
                             'n_candidates': len(cands), 'pool_size': len(idx),
                             'pool_exclusions': excluded, 'violations': bad,
                             'FILLED': filled, 'lineups': rows, 'report': report(lus, M, ids, meta, T)})
    doc = {
        'ARTIFACT': 'CLASSIC_PORTFOLIOS', 'spec_version': SPEC_VERSION, 'slate_id': slate_id,
        'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'inputs': {k: str(v.relative_to(_REPO)) for k, v in _paths(slate_id).items() if k != 'out'},
        'inputs_sha256': {k: hashlib.sha256(v.read_bytes()).hexdigest()
                          for k, v in _paths(slate_id).items() if k != 'out'},
        'research_book_sha256': hashlib.sha256((OUT_DIR / f'DK_{slate_id}_EARLY_RESEARCH_BOOK.json').read_bytes()).hexdigest(),
        'market_arm': 'FOOTBALL_ONLY', 'objective': 'E_w[max_i (S_iw - T_w)+], T_w = (1-q) quantile of candidate scores in world w',
        'OWNERSHIP': 'UNAVAILABLE: no ownership data for this slate. Duplication risk is not modelled.',
        'stack_rules': {'qb_stack_min': QB_STACK_MIN, 'forbid_dst_against_qb': FORBID_DST_AGAINST_QB,
                        'bring_back': 'not required; reported'},
        'pool_filters': {'STANDARD': {'drop_if_mean_below': STANDARD_MIN_MEAN, 'and_p90_below': STANDARD_MIN_P90},
                         'CONVICTION': {'also_drop_bands': CONVICTION_EXCLUDED_BANDS,
                                        'also_drop_mean_below': CONVICTION_MIN_MEAN,
                                        'also_drop_designations': ['QUESTIONABLE', 'DOUBTFUL']}},
        'POLICY_NOT_MEASURED': 'every cap, overlap limit, quantile and pool filter here is a declared choice',
        'contests': out_contests,
        'NOT_SUBMITTED': 'nothing is uploaded or entered; the owner entries file is not modified',
    }
    doc['sensitivity'] = {'exclude': sorted(exclude), 'tag': tag} if (exclude or tag) else None
    P = _paths(slate_id)
    up = OUT_DIR / f'DK_{slate_id}_EARLY_UPLOAD.csv'
    if tag:
        sd = OUT_DIR / 'sensitivity'
        sd.mkdir(exist_ok=True)
        P = {**P, 'out': sd / f'DK_{slate_id}_EARLY_PORTFOLIOS.{tag}.json'}
        up = sd / f'DK_{slate_id}_EARLY_UPLOAD.{tag}.csv'
    if write:
        P['out'].write_text(json.dumps(doc, indent=1, default=str))
    if write and not all_ok and up.exists():
        up.unlink()   # an upload file from an earlier build must not survive a refused one
    if write and all_ok:   # an upload-shaped file exists ONLY for a full, legal portfolio
        with open(up, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['Entry ID', 'Contest Name', 'Contest ID', 'Entry Fee'] + list(SLOTS))
            for c in out_contests:
                for r in c['lineups']:
                    w.writerow([r['entry_id'], c['contest_name'], c['contest_id'], c['entry_fee']]
                               + [s['dk_id'] for s in r['slots']])
    if not all_ok:
        return Outcome.fail('PORTFOLIO_INCOMPLETE_OR_ILLEGAL',
                            '; '.join(f"{c['contest_name']}: {c['n_filled']}/{c['n_entries']} filled, "
                                      f"{len(c['violations'])} illegal" for c in out_contests),
                            path=str(P['out'].relative_to(_REPO)))
    return Outcome.measured('CLASSIC_PORTFOLIOS_BUILT', {'n_contests': len(out_contests)},
                            n_measured=sum(c['n_filled'] for c in out_contests), what='legal lineups written',
                            detail=', '.join(f"{c['profile']} {c['n_filled']}/{c['n_entries']}" for c in out_contests),
                            path=str(P['out'].relative_to(_REPO)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--exclude', default='', help='comma-separated DK ids removed from every pool (needs --tag)')
    ap.add_argument('--tag', default='', help='write to nfl/dfs/salaries/sensitivity/ under this tag')
    a = ap.parse_args()
    o = build(a.slate_id, exclude=tuple(x for x in a.exclude.split(',') if x), tag=a.tag)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
